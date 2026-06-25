"""
LQRP Pilot Runner — End-to-end pipeline for a handful of test stocks.
Downloads data from yfinance, scores with LQRP v2.0, stores in SQLite.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings("ignore")

from db import init_db, get_db, insert_company, insert_prices, insert_financials, insert_ratios, insert_scores
from score import score_stock, score_cohort

# Pilot stocks — 15 from the paper with good yfinance coverage
PILOT_TICKERS = [
    "AV1", "AIM", "RZI", "M7T", "ACE", "XRF", "CHL", "AMX",
    "ALC", "AHC", "LBL", "ACF", "VEE", "ONE", "AL3",
]


def fetch_one(ticker):
    """Fetch all yfinance data for one stock."""
    ticker_ax = f"{ticker}.AX"
    try:
        s = yf.Ticker(ticker_ax)
        info = s.info
        if not info or not info.get("marketCap"):
            return None

        px = s.history(period="2y")
        if px.empty or len(px) < 60:
            return None

        qf = s.quarterly_financials
        bs = s.quarterly_balance_sheet
        cf = s.quarterly_cashflow

        return {
            "ticker": ticker,
            "info": info,
            "prices": px,
            "quarterly_fin": qf if qf is not None and not qf.empty else None,
            "balance_sheet": bs if bs is not None and not bs.empty else None,
            "cashflow": cf if cf is not None and not cf.empty else None,
        }
    except Exception as e:
        print(f"  {ticker}: Error - {e}")
        return None


def extract_financials(data):
    """Extract financial data from yfinance statements, with info fallback."""
    info = data.get("info", {})
    fin = {}
    qf = data.get("quarterly_fin")
    bs = data.get("balance_sheet")
    cf = data.get("cashflow")

    # === Info fallback (used when quarterly data missing) ===
    def _info(key, default=None):
        v = info.get(key)
        if v is None: return default
        if isinstance(v, (int, float)) and (np.isnan(v) or np.isinf(v)): return default
        return v

    # Revenue
    fin["revenue"] = _info("totalRevenue")
    fin["gross_profit"] = fin["revenue"] * _info("grossMargins", 0) if fin["revenue"] and _info("grossMargins") else None
    fin["ebitda"] = fin["revenue"] * _info("ebitdaMargins", 0) if fin["revenue"] and _info("ebitdaMargins") else None
    fin["revenue_growth_yoy"] = _info("revenueGrowth")  # fractional
    fin["operating_cf"] = _info("operatingCashflow")
    fin["free_cf"] = _info("freeCashflow")
    fin["cash"] = _info("totalCash")
    fin["total_debt"] = _info("totalDebt")
    fin["current_assets"] = _info("totalCash")  # rough — CA is broader
    fin["current_liabilities"] = None
    fin["total_assets"] = _info("totalAssets")
    fin["shares_outstanding"] = _info("sharesOutstanding")
    fin["current_ratio"] = _info("currentRatio")

    # Latest quarter
    if qf is not None and not qf.empty:
        latest = qf.columns[0]
        fin["period_end"] = str(latest.date())

        def _get(df, keys):
            for k in keys:
                if k in df.index:
                    v = df.loc[k, latest]
                    if pd.notna(v): return float(v)
            return None

        fin["revenue"] = _get(qf, ["Total Revenue", "Revenue", "Operating Revenue"])
        fin["gross_profit"] = _get(qf, ["Gross Profit"])
        fin["ebitda"] = _get(qf, ["EBITDA", "Normalized EBITDA"])
        fin["net_income"] = _get(qf, ["Net Income", "Net Income Common Stockholders"])
        fin["operating_expense"] = _get(qf, ["Operating Expense", "Total Operating Expenses"])

        # Compute GM change and EBITDA margin change (need 5+ quarters)
        rev_cols = qf.columns[:min(8, len(qf.columns))]
        for rk in ["Total Revenue", "Revenue", "Operating Revenue"]:
            if rk in qf.index:
                rev_series = qf.loc[rk, rev_cols].dropna()
                if len(rev_series) >= 8:
                    cur = rev_series.iloc[:4].sum()
                    prior = rev_series.iloc[4:8].sum()
                    if prior > 0:
                        fin["revenue_growth_yoy"] = cur / prior - 1
                        if len(rev_series) >= 12:
                            pp = rev_series.iloc[8:12].sum()
                            if pp > 0:
                                gp_yoy = prior / pp - 1
                                fin["revenue_growth_accel"] = fin["revenue_growth_yoy"] - gp_yoy
                break

        for gk in ["Gross Profit"]:
            if gk in qf.index:
                gp_series = qf.loc[gk, rev_cols].dropna()
                rev_series = qf.loc[qf.index[qf.index.str.contains("Revenue")][0], rev_cols].dropna() if any("Revenue" in str(x) for x in qf.index) else None
                if rev_series is not None and len(gp_series) >= 8 and len(rev_series) >= 8:
                    cur_gm = gp_series.iloc[:4].sum() / rev_series.iloc[:4].sum() if rev_series.iloc[:4].sum() > 0 else 0
                    prior_gm = gp_series.iloc[4:8].sum() / rev_series.iloc[4:8].sum() if rev_series.iloc[4:8].sum() > 0 else 0
                    fin["gross_margin_change"] = cur_gm - prior_gm
                break

        for ek in ["EBITDA", "Normalized EBITDA"]:
            if ek in qf.index:
                ebitda_series = qf.loc[ek, rev_cols].dropna()
                rev_for_margin = None
                for rk in ["Total Revenue", "Revenue", "Operating Revenue"]:
                    if rk in qf.index:
                        rev_for_margin = qf.loc[rk, rev_cols].dropna()
                        break
                if rev_for_margin is not None and len(ebitda_series) >= 8 and len(rev_for_margin) >= 8:
                    cur_em = ebitda_series.iloc[:4].sum() / rev_for_margin.iloc[:4].sum() if rev_for_margin.iloc[:4].sum() > 0 else 0
                    prior_em = ebitda_series.iloc[4:8].sum() / rev_for_margin.iloc[4:8].sum() if rev_for_margin.iloc[4:8].sum() > 0 else 0
                    fin["ebitda_margin_change"] = cur_em - prior_em
                break

    # Cash flow
    if cf is not None and not cf.empty:
        latest_cf = cf.columns[0]
        def _get_cf(keys):
            for k in keys:
                if k in cf.index:
                    v = cf.loc[k, latest_cf]
                    if pd.notna(v): return float(v)
            return None

        fin["operating_cf"] = _get_cf(["Operating Cash Flow", "Cash Flow From Operating Activities"])
        fin["capital_expenditure"] = _get_cf(["Capital Expenditure", "Capital Expenditures"])
        capex = fin.get("capital_expenditure", 0) or 0
        ocf = fin.get("operating_cf", 0) or 0
        fin["free_cf"] = ocf + capex  # capex is negative in CF

        # OCF stability
        cf_cols = cf.columns[:min(4, len(cf.columns))]
        for ok in ["Operating Cash Flow", "Cash Flow From Operating Activities"]:
            if ok in cf.index:
                vals = cf.loc[ok, cf_cols].dropna()
                if len(vals) > 0:
                    fin["ocf_stability"] = (vals > 0).sum() / len(vals) * 100
                break

    # Balance sheet
    if bs is not None and not bs.empty:
        latest_bs = bs.columns[0]
        def _get_bs(keys):
            for k in keys:
                if k in bs.index:
                    v = bs.loc[k, latest_bs]
                    if pd.notna(v): return float(v)
            return None

        fin["cash"] = _get_bs(["Cash", "Cash And Cash Equivalents"])
        fin["total_debt"] = _get_bs(["Total Debt", "Long Term Debt"])
        fin["current_assets"] = _get_bs(["Current Assets", "Total Current Assets"])
        fin["current_liabilities"] = _get_bs(["Current Liabilities", "Total Current Liabilities"])
        fin["total_assets"] = _get_bs(["Total Assets"])
        fin["ppe"] = _get_bs(["Property Plant And Equipment", "Gross PPE"])
        fin["shares_outstanding"] = _get_bs(["Ordinary Shares Number", "Share Issued", "Shares Outstanding"])

        # Share count growth
        for sk in ["Ordinary Shares Number", "Share Issued", "Shares Outstanding"]:
            if sk in bs.index:
                shares = bs.loc[sk].dropna()
                if len(shares) >= 5:
                    cur_s = shares.iloc[0]
                    prior_s = shares.iloc[4] if len(shares) > 4 else shares.iloc[-1]
                    if prior_s > 0:
                        fin["share_count_growth_yoy"] = cur_s / prior_s - 1
                    if len(shares) >= 3:
                        prior_6m = shares.iloc[2] if len(shares) > 2 else shares.iloc[-1]
                        if prior_6m > 0:
                            fin["share_count_growth_6m"] = cur_s / prior_6m - 1
                break

    # Revenue volatility (CV of quarterly revenue)
    if qf is not None and not qf.empty:
        for rk in ["Total Revenue", "Revenue", "Operating Revenue"]:
            if rk in qf.index:
                revs = qf.loc[rk].dropna()
                if len(revs) >= 4:
                    fin["revenue_volatility_cv"] = revs.iloc[:min(8,len(revs))].std() / revs.iloc[:min(8,len(revs))].mean() if revs.iloc[:min(8,len(revs))].mean() > 0 else 0
                break

    return fin


def main():
    print("=" * 60)
    print("LQRP PILOT — 15 stocks")
    print("=" * 60)

    # Initialize DB
    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "lqrp_pilot.db")
    init_db(db_path)
    conn = get_db(db_path)

    # Fetch all stocks
    print("\n─── Fetching data ───")
    results = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(fetch_one, t): t for t in PILOT_TICKERS}
        for f in as_completed(futures):
            r = f.result()
            if r:
                results[r["ticker"]] = r
                print(f"  {r['ticker']}: MC=${r['info'].get('marketCap','?')/1e6:.0f}M  {r['info'].get('sector','?')}")

    print(f"\n  Fetched: {len(results)}/{len(PILOT_TICKERS)}")

    # Store in DB
    print("\n─── Storing in database ───")
    scored_rows = []
    for ticker, data in results.items():
        info = data["info"]

        # Company
        insert_company(conn, ticker,
                       info.get("shortName", ticker),
                       info.get("industry"),
                       info.get("sector"),
                       info.get("marketCap"))

        # Prices
        insert_prices(conn, ticker, data["prices"])

        # Financials (with info fallback)
        fin = extract_financials(data)
        if fin.get("revenue") or fin.get("shares_outstanding"):
            fin["period_end"] = fin.get("period_end") or date.today().isoformat()
            insert_financials(conn, ticker, fin["period_end"], fin)
            insert_ratios(conn, ticker, fin["period_end"], fin)

        # Score
        market_data = {
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "sector": info.get("sector", "Unknown"),
            "revenue_growth": info.get("revenueGrowth"),
            "insider_pct": info.get("heldPercentInsiders"),
            "inst_pct": info.get("heldPercentInstitutions"),
        }
        scored = score_stock(market_data, data["prices"], fin,
                             info.get("sector", "Unknown"))
        scored["ticker"] = ticker
        scored_rows.append(scored)

        info_fields = sum(1 for v in fin.values() if v is not None)
        print(f"  {ticker}: stored ({len(data['prices'])} prices, {info_fields} info fields)")

    # Cohort scoring
    print("\n─── Cohort scoring ───")
    df = score_cohort(scored_rows)
    today = date.today().isoformat()

    for _, row in df.iterrows():
        scores = row.to_dict()
        scores["scoring_date"] = today
        insert_scores(conn, row["ticker"], today, scores)

    # Rankings
    print("\n" + "=" * 60)
    print("RANKINGS")
    print("=" * 60)

    rankings = df[df["gate_status"] != "hard_excluded"].head(20)
    print(f"\n{'#':<3} {'Ticker':<6} {'LQRP':>6} {'L':>5} {'Q':>5} {'R':>5} {'P':>5} {'Role':<16} {'Gate':<12} {'Cov%':>5}")
    print("-" * 80)
    for i, (_, r) in enumerate(rankings.iterrows()):
        print(f"{i+1:<3} {r['ticker']:<6} {r['LQRP_score']:>5.1f} {r['L_score']:>4.0f} {r['Q_score']:>4.0f} {r['R_score']:>4.0f} {r['P_score']:>4.0f} {r['role']:<16} {r['gate_status']:<12} {r['data_coverage_pct']:>4.0f}%")

    # Portfolio
    print("\n" + "=" * 60)
    print("SUGGESTED PORTFOLIO (Top 7 + optionality, formula-sized)")
    print("=" * 60)

    portfolio = rankings[rankings["final_weight"] > 0.5].head(10)
    print(f"\n{'Ticker':<6} {'Role':<16} {'LQRP':>6} {'L':>5} {'Q':>5} {'R':>5} {'P':>5} {'Weight':>7} {'$20k':>7}")
    print("-" * 75)
    total_w = 0
    for _, r in portfolio.iterrows():
        alloc = r["final_weight"] / 100 * 20000
        total_w += r["final_weight"]
        print(f"{r['ticker']:<6} {r['role']:<16} {r['LQRP_score']:>5.1f} {r['L_score']:>4.0f} {r['Q_score']:>4.0f} {r['R_score']:>4.0f} {r['P_score']:>4.0f} {r['final_weight']:>6.1f}% ${alloc:>5.0f}")
    print(f"{'Total':<6} {'':<16} {'':>6} {'':>5} {'':>5} {'':>5} {'':>5} {total_w:>6.1f}% ${total_w/100*20000:>5.0f}")

    # Data coverage summary
    print("\n─── Data Coverage ───")
    for _, r in df.iterrows():
        flags = r.get("coverage_flags", {})
        if isinstance(flags, str):
            import json; flags = json.loads(flags)
        flag_summary = ", ".join(f"{k}:{v}" for k, v in sorted(flags.items()) if v != "OK")
        if flag_summary:
            print(f"  {r['ticker']:<6} {r['data_coverage_pct']:.0f}%  [{flag_summary}]")
        else:
            print(f"  {r['ticker']:<6} {r['data_coverage_pct']:.0f}%  [all OK]")

    conn.close()
    print(f"\nDone. Database: {db_path}")
    print(f"Total stocks scored: {len(df)}")


if __name__ == "__main__":
    main()