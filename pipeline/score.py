"""
LQRP v2.0 Scorer — Implements the updated model formulas.
Reads from database, computes scores, writes results back.
"""
import numpy as np
import pandas as pd


def safe_float(v, default=None):
    if v is None: return default
    try: return float(v)
    except: return default


def percentile_rank(series):
    """Rank 0-100. NaN gets 50."""
    series = pd.Series(series).astype(float)
    clean = series.dropna()
    if len(clean) < 2:
        return pd.Series(50.0, index=series.index)
    ranks = clean.rank(pct=True) * 100
    result = pd.Series(50.0, index=series.index)
    result.loc[ranks.index] = ranks
    return result


def pct_rank_grouped(series, groups):
    """Percentile rank within group."""
    series = pd.Series(series).astype(float)
    result = pd.Series(50.0, index=series.index)
    for grp in set(groups):
        mask = groups == grp
        sub = series[mask]
        result[mask] = percentile_rank(sub)
    return result


def goldilocks(series, lo, hi):
    """Goldilocks scoring: 100 at center of [lo, hi], falls off toward edges."""
    series = pd.Series(series).astype(float)
    result = 100 - abs(50 - 100 * (series - lo) / (hi - lo))
    return result.clip(0, 100)


def compute_ratios(df_market, df_prices, df_fin):
    """Compute all financial ratios and price-derived metrics."""
    data = {}

    # Market cap and valuation
    data["market_cap"] = safe_float(df_market.get("market_cap"))
    data["enterprise_value"] = safe_float(df_market.get("enterprise_value"))
    data["shares_outstanding"] = safe_float(df_market.get("shares_outstanding"))
    data["sector"] = str(df_market.get("sector", "Unknown"))

    # --- Financial ratios ---
    rev = safe_float(df_fin.get("revenue"))
    gp = safe_float(df_fin.get("gross_profit"))
    ebitda = safe_float(df_fin.get("ebitda"))
    ocf = safe_float(df_fin.get("operating_cf"))
    fcf = safe_float(df_fin.get("free_cf"))
    capex = safe_float(df_fin.get("capital_expenditure"))
    cash_val = safe_float(df_fin.get("cash"))
    debt_val = safe_float(df_fin.get("total_debt"))
    ca = safe_float(df_fin.get("current_assets"))
    cl = safe_float(df_fin.get("current_liabilities"))
    ta = safe_float(df_fin.get("total_assets"))
    ppe = safe_float(df_fin.get("ppe"))
    shares_q = safe_float(df_fin.get("shares_outstanding"))

    # Margins
    data["gross_margin"] = (gp / rev) if rev and gp else None
    data["ebitda_margin"] = (ebitda / rev) if rev and ebitda else None
    data["ocf_to_revenue"] = (ocf / rev) if rev and ocf else None
    data["fcf_to_revenue"] = (fcf / rev) if rev and fcf else None

    # Leverage/liquidity
    data["current_ratio"] = (ca / cl) if ca and cl else None
    nd = (debt_val or 0) - (cash_val or 0)
    data["nd_to_ebitda"] = (nd / ebitda) if ebitda and ebitda != 0 else None

    # Asset intensity
    data["capex_to_revenue"] = (abs(capex) / rev) if rev and capex else None
    data["ppe_to_revenue"] = (ppe / rev) if rev and ppe else None

    # Cash burn & runway
    if ocf and ocf < 0 and cash_val:
        data["cash_burn_rate"] = abs(ocf)
        data["cash_runway_months"] = (cash_val / abs(ocf)) * 3
    else:
        data["cash_burn_rate"] = 0
        data["cash_runway_months"] = 36  # positive OCF = max runway

    # Growth (from df_market which has revenue_growth from yfinance info)
    data["revenue_growth_yoy"] = safe_float(df_market.get("revenue_growth"))

    # --- Price-derived metrics ---
    if df_prices is not None and len(df_prices) >= 60:
        px_close = df_prices.get("Close", pd.Series(dtype=float))
        if len(px_close) >= 126:
            # 6-month momentum (price / price_6m_ago - 1)
            px_6m = px_close.tail(126)
            data["price_momentum_6m"] = (px_6m.iloc[-1] / px_6m.iloc[0] - 1) if px_6m.iloc[0] > 0 else 0
            data["volatility_6m"] = px_6m.pct_change().std() * np.sqrt(252)

        vol = df_prices.get("Volume", pd.Series(dtype=float))
        if len(vol) >= 60 and shares_q:
            data["avg_daily_volume"] = vol.tail(126).mean()
            data["share_turnover"] = data["avg_daily_volume"] / shares_q

    # --- Revenue volatility ---
    data["revenue_volatility_cv"] = safe_float(df_fin.get("revenue_volatility_cv"))

    # --- Share count growth ---
    data["share_count_growth_yoy"] = safe_float(df_fin.get("share_count_growth_yoy"))
    data["share_count_growth_6m"] = safe_float(df_fin.get("share_count_growth_6m"))

    # --- EBITDA margin change ---
    data["ebitda_margin_change"] = safe_float(df_fin.get("ebitda_margin_change"))

    return data


def score_stock(market_data, price_data, fin_data, archetype="Unknown"):
    """
    Score a single stock with the LQRP v2.0 model.
    Returns dict with all scores, data coverage flags, and role.
    """
    d = compute_ratios(market_data, price_data, fin_data)
    flags = {}

    # === L1: Valuation compression (30% of L) ===
    ev = d.get("enterprise_value")
    rev = d.get("market_cap")  # will be overridden if revenue available
    if ev and d.get("market_cap"):
        d["L1_raw"] = -np.log(max(ev, 1) / max(d.get("market_cap", 1), 1))
        flags["L1"] = "OK"
    else:
        d["L1_raw"] = 0
        flags["L1"] = "PROXY"

    # === L2: Growth velocity (20% of L) ===
    rg = d.get("revenue_growth_yoy")
    if rg is not None:
        d["L2_raw"] = rg
        flags["L2"] = "OK"
    else:
        d["L2_raw"] = 0
        flags["L2"] = "MISSING"

    # === L3: Growth acceleration (20% of L) ===
    accel = d.get("revenue_growth_accel", 0)
    d["L3_raw"] = accel if accel else 0
    flags["L3"] = "OK" if accel else "PROXY"

    # === L4: Operating leverage (15% of L) ===
    d["L4_gm"] = d.get("gross_margin", 0) or 0
    d["L4_ebitda_change"] = d.get("ebitda_margin_change", 0) or 0
    flags["L4"] = "OK" if d.get("gross_margin") else "PROXY"

    # === L5: Commercial maturity (15% of L) ===
    d["L5_raw"] = 0
    flags["L5"] = "WEAK"  # Requires manual checklist — proxy is very weak

    # === Q1: Revenue quality (34% of Q) ===
    d["Q1_raw"] = d.get("revenue_volatility_cv", None)
    if d["Q1_raw"] is not None:
        d["Q1_raw"] = -d["Q1_raw"]  # lower CV = higher quality
        flags["Q1"] = "PROXY"  # Volatility proxy, not actual recurring %
    else:
        d["Q1_raw"] = 0
        flags["Q1"] = "MISSING"

    # === Q2: Gross margin (28% of Q) ===
    gm = d.get("gross_margin", 0) or 0
    gm_change = d.get("ebitda_margin_change", 0) or 0
    d["Q2_raw"] = 0.7 * gm + 0.3 * gm_change
    flags["Q2"] = "OK" if d.get("gross_margin") else "PROXY"

    # === Q3: Cash conversion (22% of Q) ===
    ocf_r = d.get("ocf_to_revenue")
    if ocf_r is not None:
        d["Q3_raw"] = ocf_r
        flags["Q3"] = "OK"
    else:
        d["Q3_raw"] = 0
        flags["Q3"] = "MISSING"

    # === Q4: Commercial scale (16% of Q) ===
    rev_val = d.get("market_cap")  # Use MC as proxy for scale when revenue unavailable
    d["Q4_raw"] = np.log(max(rev_val or 1, 1))
    flags["Q4"] = "OK"

    # === R1: Cash runway (30% of R) ===
    runway = d.get("cash_runway_months")
    if runway and runway >= 24: d["R1_raw"] = 100
    elif runway and runway >= 18: d["R1_raw"] = 80
    elif runway and runway >= 12: d["R1_raw"] = 60
    elif runway and runway >= 6: d["R1_raw"] = 30
    elif runway: d["R1_raw"] = 0
    else: d["R1_raw"] = 50
    flags["R1"] = "OK" if runway else "PROXY"

    # === R2: Leverage/liquidity (20% of R) ===
    d["R2_lev"] = 1 / (abs(d.get("nd_to_ebitda", 0) or 0.5) + 0.01)
    d["R2_liq"] = d.get("current_ratio", 1.0) or 1.0
    flags["R2"] = "OK"

    # === R3: Dilution risk (20% of R) ===
    d["R3_dil"] = d.get("share_count_growth_yoy", 0) or 0
    d["R3_burn"] = d.get("cash_burn_rate", 0) or 0
    flags["R3"] = "OK" if d.get("share_count_growth_yoy") is not None else "PROXY"

    # === R4: Asset intensity (15% of R) ===
    d["R4_capex"] = d.get("capex_to_revenue", 0) or 0
    d["R4_ppe"] = d.get("ppe_to_revenue", 0) or 0
    flags["R4"] = "OK"

    # === R5: Cash flow stability (15% of R) ===
    d["R5_raw"] = d.get("ocf_stability", 50) or 50
    flags["R5"] = "PROXY"

    # === P1: Insider ownership (35% of P) ===
    d["P1_raw"] = d.get("insider_pct", 0) or 0
    flags["P1"] = "WEAK"  # Ownership, not buying activity

    # === P2: Register quality (25% of P) ===
    d["P2_raw"] = 0.5 * goldilocks(pd.Series([d.get("insider_pct", 0) or 0]), 10, 30).iloc[0] + \
                  0.5 * goldilocks(pd.Series([d.get("inst_pct", 0) or 0]), 10, 40).iloc[0]
    flags["P2"] = "OK" if d.get("inst_pct") else "PROXY"

    # === P3: Crowding / share turnover (20% of P) ===
    turnover = d.get("share_turnover")
    if turnover is not None:
        d["P3_raw"] = -turnover  # lower turnover = better
        flags["P3"] = "OK"
    else:
        d["P3_raw"] = 0
        flags["P3"] = "MISSING"

    # === P4: Supply overhang (20% of P) ===
    sg6 = d.get("share_count_growth_6m", 0) or 0
    d["P4_raw"] = -sg6  # lower share growth = better
    flags["P4"] = "OK" if d.get("share_count_growth_6m") is not None else "PROXY"

    # === Scoring (single stock — will be percentile-ranked across cohort) ===
    # Placeholder: assign neutral scores, cohort-level ranking happens in score_cohort()

    # Calculate data coverage
    weights = {
        "L1": 0.30*0.45, "L2": 0.20*0.45, "L3": 0.20*0.45, "L4": 0.15*0.45, "L5": 0.15*0.45,
        "Q1": 0.34*0.25, "Q2": 0.28*0.25, "Q3": 0.22*0.25, "Q4": 0.16*0.25,
        "R1": 0.30*0.20, "R2": 0.20*0.20, "R3": 0.20*0.20, "R4": 0.15*0.20, "R5": 0.15*0.20,
        "P1": 0.35*0.10, "P2": 0.25*0.10, "P3": 0.20*0.10, "P4": 0.20*0.10,
    }
    total_w = sum(weights.values())
    covered_w = sum(weights[k] for k, v in flags.items() if v in ("OK", "MANUAL"))
    d["data_coverage_pct"] = round(covered_w / total_w * 100, 1) if total_w > 0 else 0
    d["coverage_flags"] = flags
    d["archetype"] = archetype

    return d


def score_cohort(rows):
    """Score a cohort of stocks together (percentile rank across cohort)."""
    df = pd.DataFrame(rows)
    if df.empty: return df

    # Archetype proxy = sector
    sector = df["sector"].fillna("Unknown")

    # --- L ---
    df["L1_score"] = pct_rank_grouped(df["L1_raw"], sector)
    df["L2_score"] = pct_rank_grouped(df["L2_raw"], sector)
    df["L3_score"] = pct_rank_grouped(df["L3_raw"], sector)
    df["L4_score"] = 0.6 * pct_rank_grouped(df["L4_gm"], sector) + \
                     0.4 * pct_rank_grouped(df["L4_ebitda_change"], sector)
    df["L5_score"] = percentile_rank(df["L5_raw"])
    df["L_score"] = 0.30*df["L1_score"] + 0.20*df["L2_score"] + 0.20*df["L3_score"] + \
                    0.15*df["L4_score"] + 0.15*df["L5_score"]

    # --- Q ---
    df["Q1_score"] = pct_rank_grouped(df["Q1_raw"], sector)
    df["Q2_score"] = pct_rank_grouped(df["Q2_raw"], sector)
    df["Q3_score"] = percentile_rank(df["Q3_raw"])
    df["Q4_score"] = pct_rank_grouped(df["Q4_raw"], sector)
    df["Q_score"] = 0.34*df["Q1_score"] + 0.28*df["Q2_score"] + 0.22*df["Q3_score"] + 0.16*df["Q4_score"]

    # --- R ---
    df["R1_score"] = percentile_rank(df["R1_raw"])
    df["R2_score"] = 0.6*percentile_rank(df["R2_lev"]) + 0.4*percentile_rank(df["R2_liq"])
    df["R3_score"] = 0.4*(100-percentile_rank(df["R3_dil"])) + \
                     0.3*percentile_rank(df["R3_cap"] if "R3_cap" in df.columns else pd.Series(50,index=df.index)) + \
                     0.3*(100-percentile_rank(df["R3_burn"]))
    df["R4_score"] = 0.5*(100-percentile_rank(df["R4_capex"].abs())) + \
                     0.5*(100-percentile_rank(df["R4_ppe"].abs()))
    df["R5_score"] = percentile_rank(df["R5_raw"])
    df["R_score"] = 0.30*df["R1_score"] + 0.20*df["R2_score"] + 0.20*df["R3_score"] + \
                    0.15*df["R4_score"] + 0.15*df["R5_score"]

    # --- P ---
    df["P1_score"] = percentile_rank(df["P1_raw"])
    df["P2_score"] = percentile_rank(df["P2_raw"])
    df["P3_score"] = percentile_rank(df["P3_raw"])
    df["P4_score"] = percentile_rank(df["P4_raw"])
    df["P_score"] = 0.35*df["P1_score"] + 0.25*df["P2_score"] + 0.20*df["P3_score"] + 0.20*df["P4_score"]

    # --- LQRP ---
    df["LQRP_score"] = 0.45*df["L_score"] + 0.25*df["Q_score"] + 0.20*df["R_score"] + 0.10*df["P_score"]

    # --- Gates ---
    df["gate_status"] = "passed"
    df.loc[df["R_score"] < 35, "gate_status"] = "hard_excluded"
    df.loc[df["Q_score"] < 35, "gate_status"] = "hard_excluded"
    df.loc[df["P_score"] < 20, "gate_status"] = "hard_excluded"
    df.loc[(df["R_score"] < 50) & (df["gate_status"] == "passed"), "gate_status"] = "soft_gated"
    df.loc[(df["Q_score"] < 50) & (df["gate_status"] == "passed"), "gate_status"] = "soft_gated"
    df.loc[(df["P_score"] < 40) & (df["gate_status"] == "passed"), "gate_status"] = "soft_gated"

    # --- Role ---
    def assign_role(r):
        l, q, r_score, p = r["L_score"], r["Q_score"], r["R_score"], r["P_score"]
        if r_score < 50 or q < 50: return "Optionality"
        if l >= 70: return "LiftoffEngine"
        if l >= 55: return "CoreBridge"
        return "Anchor"

    df["role"] = df.apply(assign_role, axis=1)

    # --- Sizing ---
    role_caps = {"LiftoffEngine": 17.5, "CoreBridge": 17.5, "Anchor": 20.0, "Optionality": 10.0}
    df["role_cap"] = df["role"].map(role_caps)
    df["gate_cap"] = 17.5
    df.loc[df["R_score"] < 50, "gate_cap"] = 10.0
    df.loc[df["Q_score"] < 50, "gate_cap"] = 10.0
    df.loc[df["P_score"] < 40, "gate_cap"] = 8.0
    df["cap"] = df[["role_cap", "gate_cap"]].min(axis=1)

    T = 65
    df["conviction"] = np.maximum(df["LQRP_score"] - T, 0) ** 2
    tc = df.loc[df["gate_status"] != "hard_excluded", "conviction"].sum()
    df["raw_weight"] = np.where(df["gate_status"] != "hard_excluded",
                                df["conviction"] / tc * 100 if tc > 0 else 100 / len(df), 0)
    df["capped_weight"] = np.minimum(df["raw_weight"], df["cap"])
    total_c = df.loc[df["gate_status"] != "hard_excluded", "capped_weight"].sum()
    df["final_weight"] = np.where(df["gate_status"] != "hard_excluded",
                                  df["capped_weight"] / total_c * 100 if total_c > 0 else 0, 0)

    df["model_version"] = "lqrp_v2"

    # Compute real data coverage
    coverage_flags = {}
    for _, r in df.iterrows():
        ticker = r['ticker']
        flags = {}
        # Check which raw values are non-zero/non-default → real data
        flags['L1'] = 'OK' if (r.get('L1_raw') and r['L1_raw'] != 0) else 'PROXY'
        flags['L2'] = 'OK' if (r.get('L2_raw') and r['L2_raw'] != 0) else 'MISSING'
        flags['L3'] = 'OK' if (r.get('L3_raw') and r['L3_raw'] != 0) else 'MISSING'
        flags['L4'] = 'OK' if (r.get('L4_gm') and r['L4_gm'] > 0) else 'PROXY'
        flags['L5'] = 'MANUAL' if (r.get('L5_raw') and r['L5_raw'] > 0) else 'WEAK'
        flags['Q1'] = 'OK' if (r.get('Q1_raw') and r['Q1_raw'] != 0) else 'MISSING'
        flags['Q2'] = 'OK' if (r.get('Q2_raw') and r['Q2_raw'] != 0) else 'PROXY'
        flags['Q3'] = 'OK' if (r.get('Q3_raw') and r['Q3_raw'] != 0) else 'MISSING'
        flags['Q4'] = 'OK'
        flags['R1'] = 'OK' if (r.get('R1_raw') and r['R1_raw'] > 0) else 'PROXY'
        flags['R2'] = 'OK' if (r.get('R2_lev') and r['R2_lev'] != 0.5) else 'PROXY'
        flags['R3'] = 'OK' if (r.get('R3_dil') and r['R3_dil'] != 0) else 'MISSING'
        flags['R4'] = 'OK' if (r.get('R4_capex') and r['R4_capex'] != 0) else 'MISSING'
        flags['R5'] = 'OK' if (r.get('R5_raw') and r['R5_raw'] != 50) else 'PROXY'
        flags['P1'] = 'OK' if (r.get('P1_raw') and r['P1_raw'] != 0) else 'PROXY'
        flags['P2'] = 'OK' if (r.get('P2_raw') and r['P2_raw'] != 0) else 'PROXY'
        flags['P3'] = 'OK' if (r.get('P3_raw') and r['P3_raw'] != 0) else 'MISSING'
        flags['P4'] = 'OK' if (r.get('P4_raw') and r['P4_raw'] != 0) else 'MISSING'
        # Scraper data upgrades flags
        ticket_flags = coverage_flags.get(ticker, {})
        ticket_flags.update(flags)
        coverage_flags[ticker] = flags

    # Weights for coverage calculation
    wts = {'L1':0.30*0.45,'L2':0.20*0.45,'L3':0.20*0.45,'L4':0.15*0.45,'L5':0.15*0.45,
           'Q1':0.34*0.25,'Q2':0.28*0.25,'Q3':0.22*0.25,'Q4':0.16*0.25,
           'R1':0.30*0.20,'R2':0.20*0.20,'R3':0.20*0.20,'R4':0.15*0.20,'R5':0.15*0.20,
           'P1':0.35*0.10,'P2':0.25*0.10,'P3':0.20*0.10,'P4':0.20*0.10}
    total_w = sum(wts.values())
    cov_pcts = {}
    for ticker, flags in coverage_flags.items():
        covered = sum(wts[k] for k, v in flags.items() if v in ('OK', 'MANUAL'))
        cov_pcts[ticker] = round(covered / total_w * 100, 1)
    df['data_coverage_pct'] = df['ticker'].map(cov_pcts).fillna(0)

    return df.sort_values("LQRP_score", ascending=False)


def read_scoring_data(conn):
    """Read scoring data from the database and build the DataFrame score_cohort expects.
    All data comes from DB tables — no yfinance calls, no in-memory construction."""
    import json

    # Get all tickers with company data
    companies = {r['ticker']: dict(r) for r in conn.execute("SELECT * FROM companies").fetchall()}
    tickers = list(companies.keys())
    if not tickers:
        return pd.DataFrame()

    rows = []
    for ticker in tickers:
        co = companies[ticker]
        sector = co.get('sector', 'Unknown') or 'Unknown'

        # Get latest financial ratios
        ratios_row = conn.execute(
            "SELECT * FROM financial_ratios WHERE ticker = ? ORDER BY period_end DESC LIMIT 1", (ticker,)
        ).fetchone()
        ratios = dict(ratios_row) if ratios_row else {}

        # Get latest info snapshot
        info_row = conn.execute(
            "SELECT * FROM info_snapshots WHERE ticker = ? ORDER BY snapshot_date DESC LIMIT 1", (ticker,)
        ).fetchone()
        info = dict(info_row) if info_row else {}

        # Get insider transactions for P1
        insider_txns = conn.execute("""
            SELECT transaction_type, SUM(shares) as total_shares
            FROM insider_transactions
            WHERE ticker = ? AND on_market = 1
            GROUP BY transaction_type
        """, (ticker,)).fetchall()

        # Get revenue announcements for L5 + extracted data
        rev_anns = conn.execute("""
            SELECT date, type, extracted_data FROM announcements
            WHERE ticker = ? AND type IN ('4C','FINANCIAL_REPORT','PRESENTATION','TRADING_UPDATE')
            AND extracted_data IS NOT NULL
            ORDER BY date DESC LIMIT 20
        """, (ticker,)).fetchall()

        # Extract scraped 4C data (most recent first)
        scraped_ocf_values = []
        scraped_capex = None
        scraped_cash = None
        scraped_customer_receipts = None
        scraped_arr = None
        scraped_recurring_pct = None
        scraped_customer_count = None

        for a in rev_anns:
            try:
                ed = json.loads(a['extracted_data'])
                if a['type'] == '4C':
                    if ed.get('operating_cf') and len(scraped_ocf_values) < 4:
                        scraped_ocf_values.append(ed['operating_cf'])
                    if not scraped_cash and ed.get('cash_balance'):
                        scraped_cash = ed['cash_balance']
                    if not scraped_capex and ed.get('capex'):
                        scraped_capex = ed['capex']
                    if not scraped_customer_receipts and ed.get('customer_receipts'):
                        scraped_customer_receipts = ed['customer_receipts']
                elif a['type'] in ('PRESENTATION', 'TRADING_UPDATE', 'FINANCIAL_REPORT'):
                    if not scraped_arr and ed.get('arr_millions'):
                        scraped_arr = ed['arr_millions']
                    if not scraped_recurring_pct and ed.get('recurring_pct'):
                        scraped_recurring_pct = ed['recurring_pct']
                    if not scraped_customer_count and ed.get('customer_count'):
                        scraped_customer_count = ed['customer_count']
            except: pass

        # --- Build raw values ---
        mc = co.get('market_cap') or 1
        ev = co.get('enterprise_value')

        # L1: Valuation compression
        l1_raw = -np.log(max(ev or 1, 1) / max(mc, 1))

        # L2: Growth velocity
        l2_raw = ratios.get('revenue_growth_yoy') or 0

        # L3: Growth acceleration
        l3_raw = ratios.get('revenue_growth_accel') or 0

        # L4: Operating leverage
        l4_gm = ratios.get('gross_margin') or 0
        l4_ebitda_change = ratios.get('ebitda_margin_change') or 0

        # L5: Commercial maturity (from scraped announcements)
        l5_raw = 0
        if rev_anns:
            l5_raw = 20  # commercially launched (has announcements)
            # Customer evidence
            total_anns = len([a for a in rev_anns if a['type']=='4C']) + len([a for a in rev_anns if a['type']!='4C'])
            if total_anns >= 4: l5_raw += 20  # sales motion proven
            if scraped_customer_count and scraped_customer_count >= 3: l5_raw += 20  # 3+ paying customers
            if scraped_arr and scraped_arr > 0: l5_raw += 20  # ARR evidence = commercial validation
            # Milestone-driven conversion: check if ARR or revenue is growing
            revs = []
            for r in rev_anns:
                try:
                    d = json.loads(r['extracted_data'])
                    v = d.get('revenue') or d.get('revenue_millions')
                    if v: revs.append(v)
                except: pass
            if len(revs) >= 2 and revs[0] > revs[-1]: l5_raw += 20
            if len(rev_anns) >= 6: l5_raw += 20
            l5_raw = min(l5_raw, 100)
        if l5_raw == 0:
            # Fallback to old L5 logic (from rev_anns only)
            old_anns = conn.execute("""
                SELECT date, extracted_data FROM announcements
                WHERE ticker = ? AND type IN ('FINANCIAL_REPORT', 'PRESENTATION', 'TRADING_UPDATE')
                AND extracted_data IS NOT NULL ORDER BY date DESC LIMIT 20
            """, (ticker,)).fetchall()
            if old_anns:
                l5_raw = 20
                if len(old_anns) >= 4: l5_raw += 20
                revs2 = []
                for r2 in old_anns:
                    try:
                        d = json.loads(r2['extracted_data'])
                        v = d.get('revenue') or d.get('revenue_millions')
                        if v: revs2.append(v)
                    except: pass
                if len(revs2) >= 2 and revs2[0] > revs2[-1]: l5_raw += 20
                if len(old_anns) >= 6: l5_raw += 20
                l5_raw = min(l5_raw, 100)

        # Q1: Revenue quality — use scraped recurring% if available, else volatility
        if scraped_recurring_pct:
            q1_raw = 0.7 * scraped_recurring_pct + 0.3 * (-(ratios.get('revenue_volatility_cv') or 0))
        else:
            q1_raw = -(ratios.get('revenue_volatility_cv') or 0)

        # Q2: Gross margin level + trend
        q2_raw = 0.7 * (ratios.get('gross_margin') or 0) + 0.3 * (ratios.get('ebitda_margin_change') or 0)

        # Q3: Cash conversion
        q3_raw = ratios.get('ocf_to_revenue') or 0

        # Q4: Commercial scale
        q4_raw = np.log(max(mc, 1))

        # R1: Cash runway (from scraped 4C data if available, else current ratio)
        if scraped_cash and scraped_ocf_values:
            latest_ocf = scraped_ocf_values[0]
            if latest_ocf < 0:
                r1_raw = (scraped_cash / abs(latest_ocf)) * 3  # runway in months
            else:
                r1_raw = 36  # positive OCF
        else:
            r1_raw = ratios.get('current_ratio') or 0

        # R4: Asset intensity (use quarterly data if available, else scraped)
        if not ratios.get('capex_to_revenue') and scraped_capex:
            # Use scraped capex with revenue from announcements
            rev_for_capex = None
            for a in rev_anns:
                try:
                    ed = json.loads(a['extracted_data'])
                    rev_for_capex = ed.get('revenue') or ed.get('revenue_millions')
                    if rev_for_capex: break
                except: pass
            if rev_for_capex and rev_for_capex > 0 and scraped_capex:
                r4_capex = scraped_capex / rev_for_capex
            else:
                r4_capex = abs(ratios.get('capex_to_revenue') or 0)
        else:
            r4_capex = abs(ratios.get('capex_to_revenue') or 0)
        r4_ppe = abs(ratios.get('ppe_to_revenue') or 0)

        # R5: Cash flow stability (from scraped 4C data)
        if scraped_ocf_values:
            pos_count = sum(1 for v in scraped_ocf_values if v > 0)
            if len(scraped_ocf_values) >= 4:
                r5_raw = (pos_count / len(scraped_ocf_values)) * 100
            elif len(scraped_ocf_values) == 3:
                r5_raw = (pos_count / 3) * 100
            else:
                r5_raw = 100 if pos_count > 0 else 50
        else:
            r5_raw = ratios.get('ocf_stability') if ratios_row else 50
        if r5_raw is None: r5_raw = 50

        # P1: Insider net buying (from scraped 3Y) or fallback to ownership %
        p1_raw = 0
        if insider_txns:
            buy_shares = sum(t['total_shares'] for t in insider_txns if t['transaction_type'] == 'buy')
            sell_shares = sum(t['total_shares'] for t in insider_txns if t['transaction_type'] == 'sell')
            net_buy = buy_shares - sell_shares
            if net_buy > 0 and mc > 1:
                p1_raw = (net_buy / mc) * 1e8
        if p1_raw == 0:
            p1_raw = info.get('insider_pct') or co.get('insider_pct') or 0

        # P2: Register quality (Goldilocks)
        ins_pct = info.get('insider_pct') or co.get('insider_pct') or 0
        inst_pct = info.get('inst_pct') or co.get('institution_pct') or 0
        p2_raw = 0
        if ins_pct > 0:
            p2_raw += 0.5 * max(0, 100 - abs(50 - 100 * (ins_pct / 100 - 0.10) / (0.30 - 0.10)))
        else:
            p2_raw += 25
        if inst_pct > 0:
            p2_raw += 0.5 * max(0, 100 - abs(50 - 100 * (inst_pct / 100 - 0.10) / (0.40 - 0.10)))
        else:
            p2_raw += 25

        # P3: Crowding (inverse share turnover)
        p3_raw = -(ratios.get('share_turnover') or 0)

        # P4: Supply overhang (inverse share growth)
        p4_raw = -(ratios.get('share_count_growth_6m') or 0)

        # R2 computed values
        nd_ebitda_val = ratios.get('nd_to_ebitda')
        r2_lev_val = 1 / (abs(nd_ebitda_val or 0.5) + 0.01)
        r2_liq_val = ratios.get('current_ratio') or 1.0

        # R3: Dilution
        r3_dil = ratios.get('share_count_growth_yoy') or 0
        r3_burn = ratios.get('cash_burn_rate') or 0

        rows.append(dict(
            ticker=ticker, sector=sector,
            L1_raw=l1_raw, L2_raw=l2_raw, L3_raw=l3_raw,
            L4_gm=l4_gm, L4_ebitda_change=l4_ebitda_change, L5_raw=l5_raw,
            Q1_raw=q1_raw, Q2_raw=q2_raw, Q3_raw=q3_raw, Q4_raw=q4_raw,
            R1_raw=r1_raw, R2_lev=r2_lev_val, R2_liq=r2_liq_val,
            R3_dil=r3_dil, R3_cap=0, R3_burn=r3_burn,
            R4_capex=r4_capex, R4_ppe=r4_ppe,
            R5_raw=r5_raw,
            P1_raw=p1_raw, P2_raw=p2_raw, P3_raw=p3_raw, P4_raw=p4_raw,
        ))

    return pd.DataFrame(rows)