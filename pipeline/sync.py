"""
Sync local SQLite → Cloudflare D1 via single SQL file.
Generates one INSERT file, uploads via wrangler d1 execute --remote --file.
"""
import sys, os, json, sqlite3, subprocess, tempfile

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stockanalysis.db")
WRANGLER_DIR = os.path.join(os.path.dirname(__file__), "..", "worker")
SQL_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "sync_upload.sql")


def escape(v):
    if v is None: return "NULL"
    if isinstance(v, (int, float)):
        if v != v: return "NULL"
        return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


def main():
    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print("=" * 60)
    print("Generating sync SQL...")
    print("=" * 60)

    lines = ["-- Auto-generated sync SQL"]
    total_rows = 0

    # Companies
    rows = conn.execute("SELECT ticker, name, gics_industry, sector, market_cap FROM companies").fetchall()
    if rows:
        vals = []
        for r in rows:
            vals.append(f"({escape(r['ticker'])}, {escape(r['name'])}, {escape(r['gics_industry'])}, {escape(r['sector'])}, {escape(r['market_cap'])})")
        lines.append(f"-- Companies: {len(rows)}")
        lines.append(f"INSERT OR REPLACE INTO companies (ticker, name, gics_industry, sector, market_cap) VALUES {', '.join(vals)};")
        total_rows += len(rows)
        print(f"  Companies: {len(rows)}")

    # Prices (batched in groups of 50 to keep SQL statements manageable)
    price_rows = conn.execute("SELECT ticker, date, open, high, low, close, volume FROM prices_daily ORDER BY ticker, date").fetchall()
    if price_rows:
        lines.append(f"-- Prices: {len(price_rows)}")
        for i in range(0, len(price_rows), 50):
            batch = price_rows[i:i+50]
            vals = []
            for r in batch:
                vals.append(f"({escape(r['ticker'])}, {escape(r['date'])}, {escape(r['open'])}, {escape(r['high'])}, {escape(r['low'])}, {escape(r['close'])}, {escape(r['volume'])})")
            lines.append(f"INSERT OR REPLACE INTO prices_daily (ticker, date, open, high, low, close, volume) VALUES {', '.join(vals)};")
        total_rows += len(price_rows)
        print(f"  Prices: {len(price_rows)} ({len(price_rows)//50 + 1} statements)")

    # Scores
    score_cols = ["ticker", "scoring_date", "model_version",
                  "L_score", "Q_score", "R_score", "P_score", "LQRP_score",
                  "L1_score", "L2_score", "L3_score", "L4_score", "L5_score",
                  "Q1_score", "Q2_score", "Q3_score", "Q4_score",
                  "R1_score", "R2_score", "R3_score", "R4_score", "R5_score",
                  "P1_score", "P2_score", "P3_score", "P4_score",
                  "data_coverage_pct", "coverage_flags",
                  "role", "raw_weight", "final_weight", "gate_status",
                  "archetype", "announcement_scraped", "notes"]
    score_rows = conn.execute(f"SELECT {', '.join(score_cols)} FROM lqrp_scores").fetchall()
    if score_rows:
        vals = []
        for r in score_rows:
            vals.append("(" + ", ".join(escape(r[c]) for c in score_cols) + ")")
        lines.append(f"-- Scores: {len(score_rows)}")
        lines.append(f"INSERT OR REPLACE INTO lqrp_scores ({', '.join(score_cols)}) VALUES {', '.join(vals)};")
        total_rows += len(score_rows)
        print(f"  Scores: {len(score_rows)}")

    conn.close()

    # Write SQL file
    sql_content = "\n".join(lines)
    with open(SQL_FILE, "w") as f:
        f.write(sql_content)

    size_kb = len(sql_content) / 1024
    print(f"\nSQL file: {SQL_FILE} ({size_kb:.0f} KB)")
    print(f"Total rows to sync: {total_rows}")

    # Upload via wrangler
    print("\nUploading to D1...")
    result = subprocess.run(
        ["npx", "wrangler", "d1", "execute", "stockanalysis-db", "--remote", "--file", SQL_FILE],
        cwd=WRANGLER_DIR, capture_output=True, text=True, timeout=120
    )

    if result.returncode == 0:
        print("Upload successful!")
        # Parse stats
        for line in result.stdout.split("\n"):
            if "Rows read" in line or "Rows written" in line:
                print(f"  {line.strip()}")
    else:
        # Show only relevant error lines
        for line in result.stderr.split("\n"):
            if "error" in line.lower() or "fail" in line.lower():
                print(f"  {line.strip()}")

    print(f"\nVerify: https://stockanalysis-api.eranhor.workers.dev/api/health")
    print(f"        https://3f7438b9.stockanalysis-4cj.pages.dev")


if __name__ == "__main__":
    main()