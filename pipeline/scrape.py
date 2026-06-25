"""
ASX Announcement Scraper — Multi-stock
1. Fetch ASX listings for all pilot tickers (2024+2025+2026)
2. Classify by type from headline
3. Download target PDFs
4. Parse with pdfplumber → structured data
5. Store in local SQLite (announcements + insider_transactions)
"""
import requests
from bs4 import BeautifulSoup
import pdfplumber
import os, sys, re, time, sqlite3, json
from datetime import datetime
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(__file__))

ASX_BASE = "https://www.asx.com.au"
ASX_LISTING = f"{ASX_BASE}/asx/v2/statistics/announcements.do"
PDF_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "pdfs")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stockanalysis.db")
os.makedirs(PDF_DIR, exist_ok=True)

HEADERS = {'User-Agent': 'StockAnalysis/1.0'}

PILOT_TICKERS = ["AV1","AIM","RZI","M7T","ACE","XRF","CHL","AMX","ALC","AHC","LBL","ACF","VEE","ONE","AL3"]
TARGET_TYPES = {'3Y', '4C', 'TRADING_UPDATE', 'PRESENTATION', 'CLEANSING', 'FINANCIAL_REPORT'}
YEARS = [2024, 2025, 2026]


def classify_type(headline):
    h = headline.lower()
    if 'change of director' in h or "director's interest" in h:
        return '3Y'
    if 'quarterly' in h and ('cash' in h or 'activities' in h or 'trading report' in h or '4c' in h):
        return '4C'
    if 'trading update' in h or 'market update' in h:
        return 'TRADING_UPDATE'
    if 'investor presentation' in h or 'investor briefing' in h:
        return 'PRESENTATION'
    if 'cleansing' in h:
        return 'CLEANSING'
    if 'substantial' in h and 'holding' in h:
        return 'SUBSTANTIAL_HOLDER'
    if 'application for quotation' in h or 'proposed issue of securities' in h:
        return 'SHARE_ISSUE'
    if 'annual report' in h or 'preliminary final' in h or 'half-year' in h or 'appendix 4d' in h or 'appendix 4e' in h:
        return 'FINANCIAL_REPORT'
    if 'dividend' in h or 'distribution' in h:
        return 'DIVIDEND'
    if 'results of meeting' in h or 'agm' in h or 'notice of annual' in h:
        return 'MEETING'
    return 'OTHER'


def fetch_announcements(ticker, year):
    url = f"{ASX_LISTING}?by=asxCode&asxCode={ticker}&timeframe=Y&year={year}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    soup = BeautifulSoup(r.text, 'lxml')
    results = []

    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if not cells or len(cells) < 2: continue
        links = row.find_all('a')
        if not links: continue
        href = links[0].get('href', '')
        if 'displayAnnouncement' not in href and 'idsId' not in href: continue

        text = row.get_text(' | ', strip=True)
        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', text)
        date_str = date_match.group(1) if date_match else None
        if date_str:
            try:
                date_str = datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d')
            except: pass

        ids_match = re.search(r'idsId=(\d+)', href)
        ids_id = ids_match.group(1) if ids_match else None
        pdf_url = f"{ASX_BASE}/asx/v2/statistics/displayAnnouncement.do?display=pdf&idsId={ids_id}" if ids_id else None

        headline = text
        for p in [r'\d{2}/\d{2}/\d{4}', r'\d{1,2}:\d{2}\s*(am|pm|AM|PM)', r'\d+\s*pages?\s*[\d.]+[KM]B?']:
            headline = re.sub(p, '', headline, flags=re.IGNORECASE)
        headline = re.sub(r'\s+\|\s+', ' ', headline).strip().strip('|').strip()

        results.append({
            'ticker': ticker, 'date': date_str, 'headline': headline,
            'type': classify_type(headline), 'ids_id': ids_id, 'pdf_url': pdf_url,
        })
    return results


def download_pdf(ticker, ids_id):
    path = os.path.join(PDF_DIR, ticker, f"{ids_id}.pdf")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path): return path

    viewer_url = f"{ASX_BASE}/asx/v2/statistics/displayAnnouncement.do?display=pdf&idsId={ids_id}"
    try:
        r = requests.get(viewer_url, headers=HEADERS, timeout=30)
        if 'application/pdf' in r.headers.get('Content-Type', ''):
            with open(path, 'wb') as f: f.write(r.content)
            return path
        pdf_match = re.search(r'(https?://announcements\.asx\.com\.au/asxpdf/\d+/pdf/\w+\.pdf)', r.text)
        if not pdf_match:
            pdf_match = re.search(r'(https?://www\.asx\.com\.au/asxpdf/\d+/pdf/\w+\.pdf)', r.text)
        if not pdf_match:
            m = re.search(r'asxpdf/(\d+)/pdf/(\w+\.pdf)', r.text)
            pdf_match = m
        if pdf_match:
            pdf_url = pdf_match.group(0) if hasattr(pdf_match, 'group') and pdf_match.group(0).startswith('http') else f"https://www.asx.com.au/asxpdf/{pdf_match.group(1)}/pdf/{pdf_match.group(2)}"
        else:
            return None
        r2 = requests.get(pdf_url, headers=HEADERS, timeout=30)
        if r2.status_code == 200 and len(r2.content) > 500:
            with open(path, 'wb') as f: f.write(r2.content)
            return path
        return None
    except: return None


def extract_pdf_text(filepath):
    try:
        with pdfplumber.open(filepath) as pdf:
            return '\n'.join(page.extract_text() or '' for page in pdf.pages[:8])
    except: return ''


def parse_3y(text):
    results = []
    # Names: "Name of Director" or "Director" followed by name
    names = re.findall(r'(?:Name of Director|Director)\s*[:\-]?\s*\n?\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)', text)
    if not names:
        names = re.findall(r'(?:Mr|Mrs|Ms|Dr|Miss)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', text)
    names = [n for n in names if len(n)>3 and n.lower() not in ('the','for','and','not','date','last','notice')]

    acquired = re.findall(r'(?:acquired|purchased|received)\s*(?:the following)?\s*:?\s*(\d[\d,]*)', text, re.IGNORECASE)
    disposed = re.findall(r'(?:disposed|sold|transferred)\s*(?:the following)?\s*:?\s*(\d[\d,]*)', text, re.IGNORECASE)
    on_market = 'on-market' in text.lower() or 'on market' in text.lower()
    # Value
    values = re.findall(r'\$([\d,]+\.?\d*)', text)

    for name in names[:3]:
        acq = int(acquired[0].replace(',','')) if acquired and acquired[0].replace(',','').strip() else None
        disp = int(disposed[0].replace(',','')) if disposed and disposed[0].replace(',','').strip() else None
        avg_p = float(values[0].replace(',','')) if values and values[0].replace(',','').strip() else None
        results.append({
            'director_name': name.strip(),
            'acquired_shares': acq,
            'disposed_shares': disp,
            'on_market': on_market,
            'avg_price': avg_p,
        })
    return results if results else [{'raw_text': text[:400], 'parsed': False}]


def parse_4c(text):
    results = {}
    m = re.search(r'(?:receipts from|from)\s*(?:customers|clients|sales).*?\$?[\s]*([\d,]+)', text, re.IGNORECASE)
    if not m:
        m = re.search(r'(?:customer receipts|cash receipts).*?\$([\d,]+)', text, re.IGNORECASE)
    if m:
        try: results['customer_receipts'] = int(m.group(1).replace(',',''))
        except: pass

    m = re.search(r'net (?:cash|operating).*?(?:from|provided).*?(?:operating|activities).*?\$?[\s]*\(?([\d,]+)\)?', text, re.IGNORECASE)
    if not m:
        m = re.search(r'operating (?:activities|cash flow).*?\$?[\s]*([\d,]+)', text, re.IGNORECASE)
    if m:
        try: results['operating_cf'] = int(m.group(1).replace(',',''))
        except: pass

    m = re.search(r'cash and cash equivalents.*?\$?[\s]*([\d,]+)', text, re.IGNORECASE)
    if m:
        try: results['cash_balance'] = int(m.group(1).replace(',',''))
        except: pass

    results['parsed'] = len(results) > 0
    return results


def parse_presentation(text):
    results = {}
    # Revenue
    m = re.search(r'(?:revenue|sales).*?(?:up|of|to)\s+\d+%?\s+to\s+\$?([\d,.]+)\s*(million|m|billion|b)?', text, re.IGNORECASE)
    if not m:
        m = re.search(r'(?:Revenue|Sales).*?\$([\d,]+(?:\.\d+)?)', text)
    if m:
        try:
            raw = m.group(1).replace(',','').strip()
            if raw: results['revenue_millions'] = float(raw)
        except: pass

    # ARR
    m = re.search(r'ARR.*?\$?([\d,.]+)\s*(million|m|billion|b)?', text, re.IGNORECASE)
    if m:
        try:
            raw = m.group(1).replace(',','').strip()
            if raw: results['arr_millions'] = float(raw)
        except: pass

    # Recurring %
    m = re.search(r'(\d+)\s*%\s*(?:recurring|recurring revenue)', text, re.IGNORECASE)
    if m: results['recurring_pct'] = int(m.group(1))

    results['parsed'] = len(results) > 0
    return results


def parse_financial_report(text):
    """Parse half-year/full-year reports for revenue, profit, OCF."""
    results = {}
    # Revenue
    m = re.search(r'(?:revenue|sales).*?(?:up|of|to)\s+\d+%?\s+to\s+\$?([\d,.]+)\s*(million|m|billion|b)?', text, re.IGNORECASE)
    if not m:
        m = re.search(r'(?:Revenue|Sales).*?\$([\d,]+(?:\.\d+)?)', text)
    if m:
        try:
            raw = m.group(1).replace(',','').strip()
            if raw: results['revenue'] = float(raw)
        except: pass

    # NPAT
    m = re.search(r'(?:net profit|NPAT).*?(?:up|of)\s+\d+%?\s+to\s+\$?([\d,.]+)\s*(million|m)?', text, re.IGNORECASE)
    if m:
        try:
            raw = m.group(1).replace(',','').strip()
            if raw: results['npat'] = float(raw)
        except: pass

    # Operating cash flow
    m = re.search(r'(?:operating cash|net cash from operating).*?\$([\d,]+)', text, re.IGNORECASE)
    if m: results['operating_cf'] = int(m.group(1).replace(',',''))

    results['parsed'] = len(results) > 0
    return results


def store_announcement(conn, ann, extracted_data):
    """Store announcement and any insider transactions in DB."""
    conn.execute("""
        INSERT OR REPLACE INTO announcements (ticker, date, type, headline, document_key, raw_text, extracted_data, extraction_confidence, processed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (ann['ticker'], ann['date'], ann['type'], ann['headline'],
          ann['ids_id'], extracted_data.get('raw_text', ''),
          json.dumps({k:v for k,v in extracted_data.items() if k != 'raw_text'}),
          'medium'))
    conn.commit()

    # Insider transactions from 3Y
    if ann['type'] == '3Y' and 'director_name' in extracted_data:
        # extracted_data might be dict or list
        txs = extracted_data if isinstance(extracted_data, list) else [extracted_data]
        for tx in txs:
            if tx.get('director_name') and tx.get('director_name') not in ('Unknown', ''):
                # Determine buy/sell
                if tx.get('acquired_shares'):
                    ttype, shares = 'buy', tx['acquired_shares']
                elif tx.get('disposed_shares'):
                    ttype, shares = 'sell', tx['disposed_shares']
                else:
                    continue
                conn.execute("""
                    INSERT OR REPLACE INTO insider_transactions (ticker, date, director_name, transaction_type, shares, on_market, source_document_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (ann['ticker'], ann['date'], tx['director_name'],
                      ttype, shares, 1 if tx.get('on_market') else 0, ann['ids_id']))
        conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print(f"{'='*60}")
    print(f"ASX Announcement Scraper — {len(PILOT_TICKERS)} stocks, {min(YEARS)}-{max(YEARS)}")
    print(f"{'='*60}")

    all_stats = []

    for ticker in PILOT_TICKERS:
        print(f"\n─── {ticker} ───")

        # Fetch listings
        all_anns = []
        for year in YEARS:
            anns = fetch_announcements(ticker, year)
            all_anns.extend(anns)
            time.sleep(0.3)

        type_counts = Counter(a['type'] for a in all_anns)
        targets = [a for a in all_anns if a['type'] in TARGET_TYPES]

        sum_parts = []
        for t in ['3Y','4C','PRESENTATION','FINANCIAL_REPORT']:
            if type_counts.get(t,0) > 0:
                sum_parts.append(f"{t}:{type_counts[t]}")
        print(f"  Total: {len(all_anns)} ({', '.join(sum_parts)})")

        if not targets:
            all_stats.append({'ticker': ticker, 'total': len(all_anns), 'targets': 0, 'downloaded': 0, 'parsed': 0})
            continue

        # Download in parallel
        def process_one(ann):
            if not ann['pdf_url']: return None
            filepath = download_pdf(ann['ticker'], ann['ids_id'])
            if not filepath: return None
            text = extract_pdf_text(filepath)
            if len(text) < 50: return None

            if ann['type'] == '3Y':
                data = parse_3y(text)
                ok = isinstance(data, list) and len(data) > 0 and data[0].get('director_name') and data[0].get('director_name') != 'Unknown'
            elif ann['type'] == '4C':
                data = parse_4c(text); ok = data.get('parsed')
            elif ann['type'] in ('PRESENTATION', 'TRADING_UPDATE'):
                data = parse_presentation(text); ok = data.get('parsed')
            elif ann['type'] == 'FINANCIAL_REPORT':
                data = parse_financial_report(text); ok = data.get('parsed')
            else:
                return None

            # Store
            store_data = data if isinstance(data, dict) else (data[0] if isinstance(data, list) and len(data)>0 else {})
            store_data['raw_text'] = text[:2000]
            conn = sqlite3.connect(DB_PATH)
            store_announcement(conn, ann, store_data)
            conn.close()
            return (ann['ticker'], ann['type'], ok, store_data)

        downloaded, parsed_count = 0, 0
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(process_one, ann): ann for ann in targets}
            for f in as_completed(futures):
                result = f.result()
                if result is None: continue
                downloaded += 1
                if result[2]: parsed_count += 1

        print(f"  Downloaded: {downloaded}, Parsed: {parsed_count}")
        all_stats.append({'ticker': ticker, 'total': len(all_anns), 'targets': len(targets), 'downloaded': downloaded, 'parsed': parsed_count})

        time.sleep(1)  # polite pause between tickers

    # ================================================================
    # SUMMARY
    # ================================================================
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"\n{'Ticker':<6} {'Total':>6} {'Targets':>8} {'DL':>5} {'Parsed':>7}")
    print(f"{'-'*40}")
    tot_ann, tot_tar, tot_dl, tot_par = 0, 0, 0, 0
    for s in all_stats:
        print(f"{s['ticker']:<6} {s['total']:>6} {s['targets']:>8} {s['downloaded']:>5} {s['parsed']:>7}")
        tot_ann += s['total']; tot_tar += s['targets']; tot_dl += s['downloaded']; tot_par += s['parsed']
    print(f"{'-'*40}")
    print(f"{'TOTAL':<6} {tot_ann:>6} {tot_tar:>8} {tot_dl:>5} {tot_par:>7}")

    # Insider transactions breakdown
    txs = conn.execute("SELECT COUNT(*) as n FROM insider_transactions").fetchone()
    tx_detail = conn.execute("""
        SELECT ticker, COUNT(*) as n, SUM(shares) as total_shares
        FROM insider_transactions WHERE transaction_type='buy'
        GROUP BY ticker ORDER BY n DESC
    """).fetchall()
    print(f"\nInsider buy transactions stored: {txs['n']}")
    for row in tx_detail[:5]:
        print(f"  {row['ticker']}: {row['n']} buys, {row['total_shares']:,.0f} shares")

    # Revenue extracted
    rev_data = conn.execute("""
        SELECT ticker, date, extracted_data FROM announcements
        WHERE type IN ('FINANCIAL_REPORT', 'PRESENTATION', 'TRADING_UPDATE')
        ORDER BY ticker, date DESC
    """).fetchall()
    print(f"\nRevenue data extracted ({len(rev_data)} reports):")
    for row in rev_data[:8]:
        try:
            d = json.loads(row['extracted_data'])
            rev = d.get('revenue') or d.get('revenue_millions')
            if rev: print(f"  {row['ticker']} {row['date']}: ${rev:,.0f}")
        except: pass

    conn.close()
    print(f"\nDone. DB: {DB_PATH}")


if __name__ == '__main__':
    main()