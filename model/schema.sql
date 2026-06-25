-- LQRP Platform Database Schema
-- SQLite (local) → Cloudflare D1 (production)
-- Covers rockets model + extensible for future models

-- === CORE COMPANY DATA ===
CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    gics_industry TEXT,
    sector TEXT,
    listing_date DATE,
    delisted_date DATE,
    is_equity INTEGER DEFAULT 1,
    market_cap REAL,
    enterprise_value REAL,
    shares_outstanding REAL,
    free_float_pct REAL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- === PRICE HISTORY ===
CREATE TABLE IF NOT EXISTS prices_daily (
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    adjusted_close REAL,
    source TEXT DEFAULT 'yfinance',
    PRIMARY KEY (ticker, date)
);

-- === YFINANCE INFO SNAPSHOTS (full download, nothing discarded) ===
CREATE TABLE IF NOT EXISTS info_snapshots (
    ticker TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    source TEXT DEFAULT 'yfinance',
    -- Valuation
    beta REAL, peg_ratio REAL, price_to_book REAL, price_to_sales REAL,
    trailing_pe REAL, forward_pe REAL, enterprise_to_revenue REAL,
    enterprise_to_ebitda REAL,
    -- Profitability
    return_on_equity REAL, return_on_assets REAL, profit_margins REAL,
    operating_margins REAL,
    -- Growth
    earnings_growth REAL, earnings_quarterly_growth REAL,
    -- Dividends
    dividend_yield REAL, dividend_rate REAL, payout_ratio REAL,
    five_year_avg_dividend_yield REAL,
    -- Short / float
    short_ratio REAL, short_pct_float REAL, shares_short REAL,
    float_shares REAL, implied_shares_outstanding REAL,
    -- Price bands
    fifty_two_week_high REAL, fifty_two_week_low REAL,
    fifty_day_avg REAL, two_hundred_day_avg REAL,
    -- Volume
    average_volume REAL, average_volume_10d REAL,
    -- Analyst
    recommendation_mean REAL, number_analysts INTEGER,
    target_mean_price REAL, target_high_price REAL, target_low_price REAL,
    -- Full JSON catch-all
    raw_json TEXT,
    PRIMARY KEY (ticker, snapshot_date)
);

-- === PRICE HISTORY ===
CREATE TABLE IF NOT EXISTS prices_daily (
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    adjusted_close REAL,
    source TEXT DEFAULT 'yfinance',
    PRIMARY KEY (ticker, date)
);

-- === QUARTERLY FINANCIAL STATEMENTS ===
CREATE TABLE IF NOT EXISTS financials_quarterly (
    ticker TEXT NOT NULL,
    period_end DATE NOT NULL,
    -- Income Statement
    total_revenue REAL,
    revenue REAL,  -- net of operating expenses
    gross_profit REAL,
    operating_expense REAL,
    operating_income REAL,
    sg_and_a REAL,                -- selling, general & admin
    research_and_development REAL,
    ebitda REAL,
    ebit REAL,
    interest_expense REAL,
    depreciation REAL,
    tax_provision REAL,
    net_income REAL,
    -- Cash Flow
    operating_cf REAL,
    free_cf REAL,
    capital_expenditure REAL,
    change_in_cash REAL,
    change_in_working_capital REAL,
    -- Balance Sheet
    cash REAL,
    total_debt REAL,
    long_term_debt REAL,
    short_long_term_debt REAL,
    current_assets REAL,
    current_liabilities REAL,
    other_current_liabilities REAL,
    total_assets REAL,
    ppe REAL,                     -- property, plant & equipment
    goodwill REAL,
    intangible_assets REAL,
    retained_earnings REAL,
    common_stock_equity REAL,
    total_capitalization REAL,
    shares_outstanding REAL,
    -- Source tracking
    source TEXT DEFAULT 'yfinance',
    data_quality TEXT DEFAULT 'full',
    PRIMARY KEY (ticker, period_end)
);

-- === COMPUTED FINANCIAL RATIOS ===
CREATE TABLE IF NOT EXISTS financial_ratios (
    ticker TEXT NOT NULL,
    period_end DATE NOT NULL,
    -- Margins
    gross_margin REAL,
    ebitda_margin REAL,
    net_margin REAL,
    -- Growth
    revenue_growth_yoy REAL,
    revenue_growth_qoq REAL,
    revenue_growth_accel REAL,  -- acceleration: current_yoy - prior_yoy
    -- Cash conversion
    ocf_to_revenue REAL,
    fcf_to_revenue REAL,
    -- Leverage & liquidity
    current_ratio REAL,
    debt_to_equity REAL,
    nd_to_ebitda REAL,  -- net debt / ebitda
    -- Revenue quality
    revenue_volatility_cv REAL,  -- CV of quarterly revenue over 8 quarters
    -- Dilution
    share_count_growth_yoy REAL,
    share_count_growth_6m REAL,
    -- Burn & runway
    cash_burn_rate REAL,  -- quarterly cash burn (for OCF-negative companies)
    cash_runway_months REAL,
    -- Operating leverage
    ebitda_margin_change REAL,
    -- Asset intensity
    capex_to_revenue REAL,
    ppe_to_revenue REAL,
    -- Share turnover
    avg_daily_volume REAL,
    share_turnover REAL,  -- avg_daily_volume / shares_outstanding
    -- Metadata
    data_quality TEXT DEFAULT 'full',
    PRIMARY KEY (ticker, period_end)
);

-- === ANNOUNCEMENTS ===
CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    type TEXT,  -- '3Y', '4C', '2A', 'TRADING_UPDATE', 'PRESENTATION', 'SUBSTANTIAL_HOLDER', 'CLEANSING', 'OTHER'
    headline TEXT,
    document_key TEXT UNIQUE,
    pdf_url TEXT,
    raw_text TEXT,       -- extracted PDF text
    extracted_data TEXT, -- JSON blob: {"arr": 16.3, "customers": 500, ...}
    extraction_confidence TEXT DEFAULT 'low',  -- 'high', 'medium', 'low'
    processed INTEGER DEFAULT 0,  -- 0=pending, 1=processed, 2=failed
    UNIQUE(ticker, document_key)
);

-- === INSIDER TRANSACTIONS ===
CREATE TABLE IF NOT EXISTS insider_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    director_name TEXT,
    transaction_type TEXT,  -- 'buy', 'sell', 'exercise', 'grant', 'other'
    shares REAL,
    value REAL,
    on_market INTEGER,  -- 1 if on-market, 0 if off-market/other
    source_document_key TEXT,
    FOREIGN KEY (source_document_key) REFERENCES announcements(document_key)
);

-- === OWNERSHIP SNAPSHOTS ===
CREATE TABLE IF NOT EXISTS ownership_snapshots (
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    insider_pct REAL,
    institutional_pct REAL,
    top_holder_pct REAL,
    substantial_holders_count INTEGER,
    source TEXT DEFAULT 'yfinance',
    PRIMARY KEY (ticker, date)
);

-- === LQRP SCORES ===
CREATE TABLE IF NOT EXISTS lqrp_scores (
    ticker TEXT NOT NULL,
    scoring_date DATE NOT NULL,
    model_version TEXT NOT NULL,  -- 'v2.0', etc.
    -- Component scores (0-100)
    L_score REAL,
    Q_score REAL,
    R_score REAL,
    P_score REAL,
    LQRP_score REAL,
    -- Sub-factor details
    L1_score REAL, L2_score REAL, L3_score REAL, L4_score REAL, L5_score REAL,
    Q1_score REAL, Q2_score REAL, Q3_score REAL, Q4_score REAL,
    R1_score REAL, R2_score REAL, R3_score REAL, R4_score REAL, R5_score REAL,
    P1_score REAL, P2_score REAL, P3_score REAL, P4_score REAL,
    -- Data quality
    data_coverage_pct REAL,  -- % of sub-factor weight with OK/MANUAL data
    coverage_flags TEXT,     -- JSON: {"L1":"OK","L5":"PROXY",...}
    -- Portfolio
    role TEXT,  -- 'LiftoffEngine', 'CoreBridge', 'Anchor', 'Optionality'
    raw_weight REAL,
    final_weight REAL,
    gate_status TEXT,  -- 'passed', 'soft_gated', 'hard_excluded'
    -- Metadata
    archetype TEXT,
    announcement_scraped INTEGER DEFAULT 0,  -- 0=not yet, 1=scraped
    notes TEXT,
    PRIMARY KEY (ticker, scoring_date, model_version)
);

-- === MODEL VERSIONS ===
CREATE TABLE IF NOT EXISTS model_versions (
    version TEXT PRIMARY KEY,
    applied_date DATE,
    description TEXT,
    weights_json TEXT,   -- top-level and sub-factor weights
    parameter_json TEXT, -- T threshold, caps, gates
    paper_reference TEXT
);

-- === DATA SOURCE TRACKING ===
CREATE TABLE IF NOT EXISTS data_sources (
    source_name TEXT PRIMARY KEY,
    last_fetch TIMESTAMP,
    fetch_status TEXT,  -- 'success', 'partial', 'failed'
    records_fetched INTEGER,
    error_message TEXT,
    rate_limit_until TIMESTAMP
);

-- === INDEXES ===
CREATE INDEX IF NOT EXISTS idx_prices_ticker_date ON prices_daily(ticker, date);
CREATE INDEX IF NOT EXISTS idx_financials_ticker_date ON financials_quarterly(ticker, period_end);
CREATE INDEX IF NOT EXISTS idx_ratios_ticker_date ON financial_ratios(ticker, period_end);
CREATE INDEX IF NOT EXISTS idx_announcements_ticker_date ON announcements(ticker, date);
CREATE INDEX IF NOT EXISTS idx_announcements_type ON announcements(ticker, type);
CREATE INDEX IF NOT EXISTS idx_insider_ticker_date ON insider_transactions(ticker, date);
CREATE INDEX IF NOT EXISTS idx_scores_ticker_version ON lqrp_scores(ticker, model_version);
CREATE INDEX IF NOT EXISTS idx_scores_date ON lqrp_scores(scoring_date);
