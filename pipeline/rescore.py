"""Enriched LQRP Re-Scorer — overlay scraped data onto existing pilot scores."""
import sys, os, sqlite3, json
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stockanalysis.db")


def get_scraped_enrichments(conn, ticker):
    """Get P1 and L5 enrichment data from scraped announcements."""
    # Insider transactions (last 12 months)
    insider_txns = conn.execute("""
        SELECT transaction_type, SUM(shares) as total_shares
        FROM insider_transactions
        WHERE ticker = ? AND date >= date('now', '-12 months') AND on_market = 1
        GROUP BY transaction_type
    """, (ticker,)).fetchall()

    # Revenue announcements
    revenue_anns = conn.execute("""
        SELECT date, extracted_data FROM announcements
        WHERE ticker = ? AND type IN ('FINANCIAL_REPORT', 'PRESENTATION', 'TRADING_UPDATE')
        AND extracted_data IS NOT NULL
        ORDER BY date DESC
    """, (ticker,)).fetchall()

    return insider_txns, revenue_anns


def compute_p1_enrichment(insider_txns, company):
    """Compute enriched P1_raw from insider buy/sell data."""
    if not insider_txns or not company:
        return None, 'PROXY'

    buy_shares = sum(t['total_shares'] for t in insider_txns if t['transaction_type'] == 'buy')
    sell_shares = sum(t['total_shares'] for t in insider_txns if t['transaction_type'] == 'sell')
    net_buy = buy_shares - sell_shares

    if net_buy <= 0:
        return 0, 'PROXY'

    shares_out = company['shares_outstanding'] or 1
    mc = company['market_cap'] or 1
    if mc <= 0:
        return None, 'PROXY'

    # Scale: net buy value relative to market cap (basis points of MC bought by insiders)
    # Proxy for paper's "Net insider buy value / free-float market cap"
    return (net_buy / mc) * 1e8, 'MANUAL'


def compute_l5_enrichment(revenue_anns):
    """Compute enriched L5 checklist score from announcement evidence."""
    if not revenue_anns:
        return 0, 'WEAK'

    score = 20  # commercially launched (has announcements)
    if len(revenue_anns) >= 4:
        score += 20  # sales motion proven

    # Check for growing revenue (milestone conversion)
    revs = []
    for r in revenue_anns:
        try:
            d = json.loads(r['extracted_data'])
            v = d.get('revenue') or d.get('revenue_millions')
            if v: revs.append(v)
        except: pass
    if len(revs) >= 2 and revs[0] > revs[-1]:
        score += 20  # milestone-driven conversion

    if len(revenue_anns) >= 6:
        score += 20  # multi-year customer evidence

    return min(score, 100), 'MANUAL'


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print("=" * 60)
    print("Enriched LQRP Re-Scorer — overlay mode")
    print("=" * 60)

    # Get existing scores
    old_scores = conn.execute("""
        SELECT * FROM lqrp_scores
        WHERE model_version = 'lqrp_v2'
        ORDER BY ticker
    """).fetchall()

    print(f"\nExisting scores: {len(old_scores)} stocks")
    print(f"\n{'Ticker':<6} {'Old P1':>7} {'→ New P1':>10} {'Old L5':>7} {'→ New L5':>10} {'Old Cov':>8} {'→ New Cov':>8}")
    print(f"{'-'*65}")

    updates = []

    for old in old_scores:
        ticker = old['ticker']
        company = conn.execute("SELECT * FROM companies WHERE ticker = ?", (ticker,)).fetchone()
        insider_txns, revenue_anns = get_scraped_enrichments(conn, ticker)

        # Compute enrichments
        p1_raw, p1_flag = compute_p1_enrichment(insider_txns, company)
        l5_raw, l5_flag = compute_l5_enrichment(revenue_anns)

        old_p1 = old['P1_score']
        old_l5 = old['L5_score']
        old_cov = old['data_coverage_pct']

        new_p1 = old_p1
        new_l5 = old_l5

        # P1 enrichment: net buy value / shares outstanding
        if p1_flag == 'MANUAL' and p1_raw is not None:
            # In the original model, P1 is scored via percentile_rank of P1_raw
            # For a single-stock view, we'll estimate: if net buying exists, bump P1
            # But for cohort scoring we need the raw value. Store it for now.
            new_p1 = min(old_p1 + 15, 100)  # bump: insider buying is a strong signal
        else:
            p1_flag = 'WEAK'

        # L5 enrichment: checklist from announcements
        if l5_flag == 'MANUAL' and l5_raw > 0:
            new_l5 = min(l5_raw, 100)
        else:
            l5_flag = 'WEAK'
            new_l5 = old_l5

        # Recalculate coverage
        old_coverage = json.loads(old['coverage_flags']) if isinstance(old['coverage_flags'], str) else (old['coverage_flags'] or {})
        new_coverage = dict(old_coverage)
        new_coverage['P1'] = p1_flag
        new_coverage['L5'] = l5_flag

        # Coverage %
        weights = {
            "L1": 0.30, "L2": 0.20, "L3": 0.20, "L4": 0.15, "L5": 0.15,
            "Q1": 0.34, "Q2": 0.28, "Q3": 0.22, "Q4": 0.16,
            "R1": 0.30, "R2": 0.20, "R3": 0.20, "R4": 0.15, "R5": 0.15,
            "P1": 0.35, "P2": 0.25, "P3": 0.20, "P4": 0.20,
        }
        comp_w = {"L":0.45,"Q":0.25,"R":0.20,"P":0.10}
        full_w = {}
        for k, v in weights.items():
            comp = k[0]
            full_w[k] = v * comp_w[comp]
        total_w = sum(full_w.values())
        covered_w = sum(full_w[k] for k, v in new_coverage.items() if v in ("OK", "MANUAL"))
        new_cov_pct = round(covered_w / total_w * 100, 1)

        # Recompute LQRP with new sub-factor scores
        # We need to recompute L from its sub-factors
        old_L1 = old['L1_score']; old_L2 = old['L2_score']; old_L3 = old['L3_score']
        old_L4 = old['L4_score']
        new_L = 0.30*old_L1 + 0.20*old_L2 + 0.20*old_L3 + 0.15*old_L4 + 0.15*new_l5
        new_LQRP = 0.45*new_L + 0.25*old['Q_score'] + 0.20*old['R_score'] + 0.10*old['P_score']

        old_p1_display = old_p1
        new_p1_display = new_p1

        print(f"{ticker:<6} {old_p1_display:>6.0f}  {new_p1_display:>9.0f} {old_l5:>6.0f}  {new_l5:>9.0f} {old_cov:>7.0f}% {new_cov_pct:>7.0f}%")

        updates.append({
            'ticker': ticker,
            'old': old,
            'new_L': new_L,
            'new_L5': new_l5,
            'new_P1': new_p1,
            'new_LQRP': new_LQRP,
            'new_coverage': new_coverage,
            'new_cov_pct': new_cov_pct,
        })

    # Store updated scores
    today = date.today().isoformat()
    for u in updates:
        old = u['old']
        conn.execute("""
            INSERT OR REPLACE INTO lqrp_scores
            (ticker, scoring_date, model_version,
             L_score, Q_score, R_score, P_score, LQRP_score,
             L1_score, L2_score, L3_score, L4_score, L5_score,
             Q1_score, Q2_score, Q3_score, Q4_score,
             R1_score, R2_score, R3_score, R4_score, R5_score,
             P1_score, P2_score, P3_score, P4_score,
             data_coverage_pct, coverage_flags,
             role, raw_weight, final_weight, gate_status,
             archetype, announcement_scraped, notes)
            VALUES (?, ?, 'lqrp_v2_enriched',
             ?, ?, ?, ?, ?,
             ?, ?, ?, ?, ?,
             ?, ?, ?, ?,
             ?, ?, ?, ?, ?,
             ?, ?, ?, ?,
             ?, ?,
             ?, ?, ?, ?,
             ?, 1, ?)
        """, (
            u['ticker'], today,
            u['new_L'], old['Q_score'], old['R_score'], old['P_score'], u['new_LQRP'],
            old['L1_score'], old['L2_score'], old['L3_score'], old['L4_score'], u['new_L5'],
            old['Q1_score'], old['Q2_score'], old['Q3_score'], old['Q4_score'],
            old['R1_score'], old['R2_score'], old['R3_score'], old['R4_score'], old['R5_score'],
            u['new_P1'], old['P2_score'], old['P3_score'], old['P4_score'],
            u['new_cov_pct'], json.dumps(u['new_coverage']),
            old['role'], old['raw_weight'], old['final_weight'], old['gate_status'],
            old['archetype'], old['notes'],
        ))
    conn.commit()

    # Rankings comparison
    print(f"\n{'='*60}")
    print("BEFORE vs AFTER")
    print(f"{'='*60}")
    old_by_ticker = {o['ticker']: o for o in old_scores}
    new_by_ticker = {u['ticker']: u for u in updates}

    print(f"\n{'Ticker':<6} {'Old LQRP':>8} {'New LQRP':>8} {'Δ':>6} {'Old Cov':>7} {'New Cov':>7}")
    print(f"{'-'*50}")
    for ticker in sorted(old_by_ticker):
        o = old_by_ticker[ticker]
        n = new_by_ticker.get(ticker)
        if n:
            delta = n['new_LQRP'] - o['LQRP_score']
            print(f"{ticker:<6} {o['LQRP_score']:>7.1f} {n['new_LQRP']:>7.1f} {delta:>+5.1f} {o['data_coverage_pct']:>6.0f}% {n['new_cov_pct']:>6.0f}%")

    conn.close()
    print(f"\nDone. Enriched scores stored as model_version='lqrp_v2_enriched'")


if __name__ == '__main__':
    main()