"""Database connection and helpers for SQLite."""
import sqlite3
import os
import json

DB_PATH = os.environ.get("LQRP_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "lqrp.db"))


def get_db(db_path=None):
    """Get a database connection with row factory."""
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path=None):
    """Initialize the database schema."""
    conn = get_db(db_path)
    schema_path = os.path.join(os.path.dirname(__file__), "..", "model", "schema.sql")
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path or DB_PATH}")


def insert_company(conn, ticker, name, gics_industry=None, sector=None, market_cap=None):
    conn.execute("""
        INSERT OR REPLACE INTO companies (ticker, name, gics_industry, sector, market_cap, last_updated)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (ticker, name, gics_industry, sector, market_cap))
    conn.commit()


def insert_prices(conn, ticker, df_prices):
    """Insert price data from a DataFrame with columns: Open, High, Low, Close, Volume."""
    rows = []
    for date, row in df_prices.iterrows():
        rows.append((
            ticker,
            date.strftime("%Y-%m-%d") if hasattr(date, 'strftime') else str(date)[:10],
            float(row.get("Open", 0) or 0),
            float(row.get("High", 0) or 0),
            float(row.get("Low", 0) or 0),
            float(row.get("Close", 0) or 0),
            float(row.get("Volume", 0) or 0),
        ))
    conn.executemany("""
        INSERT OR REPLACE INTO prices_daily (ticker, date, open, high, low, close, volume, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'yfinance')
    """, rows)
    conn.commit()


def insert_financials(conn, ticker, period_end, data):
    """Insert quarterly financial data."""
    conn.execute("""
        INSERT OR REPLACE INTO financials_quarterly
        (ticker, period_end, revenue, gross_profit, operating_expense, ebitda, net_income,
         operating_cf, free_cf, capital_expenditure,
         cash, total_debt, current_assets, current_liabilities, total_assets, ppe, shares_outstanding,
         source, data_quality)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'yfinance', 'partial')
    """, (
        ticker, period_end,
        data.get("revenue"), data.get("gross_profit"), data.get("opex"),
        data.get("ebitda"), data.get("net_income"),
        data.get("operating_cf"), data.get("free_cf"), data.get("capex"),
        data.get("cash"), data.get("debt"), data.get("current_assets"),
        data.get("current_liabilities"), data.get("total_assets"), data.get("ppe"),
        data.get("shares_outstanding"),
    ))
    conn.commit()


def insert_ratios(conn, ticker, period_end, ratios):
    """Insert computed financial ratios."""
    cols = [
        "gross_margin", "ebitda_margin", "net_margin",
        "revenue_growth_yoy", "revenue_growth_qoq", "revenue_growth_accel",
        "ocf_to_revenue", "fcf_to_revenue",
        "current_ratio", "debt_to_equity", "nd_to_ebitda",
        "revenue_volatility_cv",
        "share_count_growth_yoy", "share_count_growth_6m",
        "cash_burn_rate", "cash_runway_months",
        "ebitda_margin_change",
        "capex_to_revenue", "ppe_to_revenue",
        "avg_daily_volume", "share_turnover",
    ]
    values = [ratios.get(c) for c in cols]
    placeholders = ", ".join(["?"] * len(cols))
    conn.execute(f"""
        INSERT OR REPLACE INTO financial_ratios
        (ticker, period_end, {', '.join(cols)}, data_quality)
        VALUES (?, ?, {placeholders}, 'computed')
    """, [ticker, period_end] + values)
    conn.commit()


def insert_scores(conn, ticker, scoring_date, data):
    """Insert LQRP scores for a stock."""
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
        VALUES (?, ?, ?,
         ?, ?, ?, ?, ?,
         ?, ?, ?, ?, ?,
         ?, ?, ?, ?,
         ?, ?, ?, ?, ?,
         ?, ?, ?, ?,
         ?, ?,
         ?, ?, ?, ?,
         ?, ?, ?)
    """, (
        ticker, scoring_date, data.get("model_version", "v2.0"),
        data.get("L_score"), data.get("Q_score"), data.get("R_score"), data.get("P_score"), data.get("LQRP_score"),
        data.get("L1_score"), data.get("L2_score"), data.get("L3_score"), data.get("L4_score"), data.get("L5_score"),
        data.get("Q1_score"), data.get("Q2_score"), data.get("Q3_score"), data.get("Q4_score"),
        data.get("R1_score"), data.get("R2_score"), data.get("R3_score"), data.get("R4_score"), data.get("R5_score"),
        data.get("P1_score"), data.get("P2_score"), data.get("P3_score"), data.get("P4_score"),
        data.get("data_coverage_pct"),
        json.dumps(data.get("coverage_flags", {})),
        data.get("role"), data.get("raw_weight"), data.get("final_weight"), data.get("gate_status"),
        data.get("archetype"), data.get("announcement_scraped", 0), data.get("notes"),
    ))
    conn.commit()


def get_rankings(conn, model_version="v2.0", limit=100):
    """Get current LQRP rankings."""
    rows = conn.execute("""
        SELECT c.ticker, c.name, c.sector, c.gics_industry, c.market_cap,
               s.L_score, s.Q_score, s.R_score, s.P_score, s.LQRP_score,
               s.role, s.final_weight, s.gate_status, s.data_coverage_pct,
               s.announcement_scraped, s.archetype
        FROM lqrp_scores s
        JOIN companies c ON c.ticker = s.ticker
        WHERE s.model_version = ?
        ORDER BY s.LQRP_score DESC
        LIMIT ?
    """, (model_version, limit))
    return [dict(r) for r in rows]


def get_company_detail(conn, ticker, model_version="v2.0"):
    """Get full detail for one company."""
    score = conn.execute("""
        SELECT * FROM lqrp_scores
        WHERE ticker = ? AND model_version = ?
        ORDER BY scoring_date DESC LIMIT 1
    """, (ticker, model_version)).fetchone()

    company = conn.execute("SELECT * FROM companies WHERE ticker = ?", (ticker,)).fetchone()

    ratios = conn.execute("""
        SELECT * FROM financial_ratios
        WHERE ticker = ?
        ORDER BY period_end DESC LIMIT 4
    """, (ticker,)).fetchall()

    announcements = conn.execute("""
        SELECT date, type, headline, extracted_data, extraction_confidence
        FROM announcements WHERE ticker = ?
        ORDER BY date DESC LIMIT 20
    """, (ticker,)).fetchall()

    return {
        "score": dict(score) if score else None,
        "company": dict(company) if company else None,
        "ratios": [dict(r) for r in ratios],
        "announcements": [dict(a) for a in announcements],
    }


def get_portfolio(conn, model_version="v2.0"):
    """Get the current suggested portfolio with sizing."""
    rows = conn.execute("""
        SELECT c.ticker, c.name, c.sector, s.LQRP_score, s.L_score, s.Q_score,
               s.R_score, s.P_score, s.role, s.final_weight, s.gate_status,
               s.data_coverage_pct
        FROM lqrp_scores s
        JOIN companies c ON c.ticker = s.ticker
        WHERE s.model_version = ?
          AND s.final_weight > 0
        ORDER BY s.final_weight DESC
    """, (model_version,))
    return [dict(r) for r in rows]