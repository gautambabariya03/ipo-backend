import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def clean_txt(t):
    return re.sub(r'\s+', ' ', t).strip() if t else ""

def parse_num(val_str):
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?', val_str.replace(',', '').replace('₹', ''))
    return float(nums[0]) if nums else 0.0

def fetch_live_gmp():
    # InvestorGain report link with no-cache timestamp
    url = f"https://www.investorgain.com/report/ipo-gmp-live/331/?v={int(datetime.now().timestamp())}"
    scraped_list = []
    seen_ids = set()

    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("table")
        
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 5:
                    continue

                raw_name = clean_txt(cols[0].text)
                if not raw_name or len(raw_name) < 2:
                    continue
                
                # Header row skip
                if "GMP" in raw_name.upper() and len(raw_name) < 6:
                    continue

                # Category
                is_sme = "SME" in raw_name.upper()

                # Clean Display Name
                clean_name = re.sub(r'\[email&#160;protected\]|\[email\s*protected\]', '', raw_name, flags=re.IGNORECASE)
                clean_name = re.sub(r'\([+-]?\d+(?:\.\d+)?%\)', '', clean_name)
                clean_name = re.sub(r'(\(?(BSE\s+|NSE\s+)?SME\)?[UOCLCT]*|IPO[UOCLCT]*$|IPO[A-Z@\d\.\s\(\)%]*$)', '', clean_name, flags=re.IGNORECASE).strip()
                clean_name = clean_name.strip(' -–@')

                if not clean_name:
                    continue

                c_id = re.sub(r'[^a-zA-Z0-9]', '-', clean_name.lower())[:35].strip('-')
                if not c_id or c_id in seen_ids:
                    continue

                # Exact cell extractions
                gmp_text = clean_txt(cols[1].text)
                gmp_val = 0.0
                gmp_pct = 0.0

                if "--" not in gmp_text and re.search(r'\d', gmp_text):
                    pct_m = re.search(r'\(([+-]?\d+(?:\.\d+)?)%\)', gmp_text)
                    if pct_m:
                        gmp_pct = abs(float(pct_m.group(1)))
                    cell_no_pct = re.sub(r'\(.*?\)', '', gmp_text)
                    gmp_val = parse_num(cell_no_pct)

                # Sub multiple (col 3)
                sub_val = "--"
                if len(cols) > 3:
                    s_txt = clean_txt(cols[3].text)
                    if "x" in s_txt.lower() or parse_num(s_txt) > 0:
                        sub_val = s_txt if "x" in s_txt.lower() else f"{s_txt}x"

                # Price (col 4)
                price_val = 0.0
                if len(cols) > 4:
                    price_val = parse_num(cols[4].text)

                if gmp_pct == 0.0 and price_val > 0 and gmp_val > 0:
                    gmp_pct = round((gmp_val / price_val) * 100, 2)

                # Size (col 5)
                size_val = "--"
                if len(cols) > 5:
                    sz_txt = clean_txt(cols[5].text)
                    if "Cr" in sz_txt or "₹" in sz_txt:
                        size_val = sz_txt

                # Lot (col 6)
                lot_val = 0
                if len(cols) > 6:
                    l_txt = clean_txt(cols[6].text).replace(',', '')
                    if l_txt.isdigit():
                        lot_val = int(l_txt)

                if lot_val == 0:
                    lot_val = 1200 if is_sme else (50 if price_val > 100 else 100)

                # Extract Dates from col 7 to 10
                open_date = clean_txt(cols[7].text) if len(cols) > 7 else ""
                close_date = clean_txt(cols[8].text) if len(cols) > 8 else ""
                listing_date = clean_txt(cols[10].text) if len(cols) > 10 else "--"

                date_range = f"{open_date} - {close_date}" if open_date and close_date else "Live"

                # Profits
                ret_prof = round(gmp_val * lot_val, 2) if gmp_val > 0 else 0.0
                hni_prof = round(ret_prof * 14, 2) if ret_prof > 0 else 0.0

                # IST Time
                ist = timezone(timedelta(hours=5, minutes=30))
                now_str = datetime.now(ist).strftime("%d %b, %I:%M %p")

                scraped_list.append({
                    "id": c_id,
                    "name": clean_name,
                    "category": "SME" if is_sme else "MAINBOARD",
                    "date_range": date_range,
                    "open_date": open_date,
                    "close_date": close_date,
                    "price": f"₹{int(price_val) if price_val.is_integer() else price_val}" if price_val > 0 else "--",
                    "lot_size": lot_val,
                    "issue_size": size_val,
                    "gmp": gmp_val,
                    "gmp_percentage": gmp_pct,
                    "last_heard": now_str,
                    "allotment_date": clean_txt(cols[9].text) if len(cols) > 9 else "--",
                    "listing_date": listing_date,
                    "retail_profit": ret_prof,
                    "hni_profit": hni_prof,
                    "status": "OPEN", # main.py isko date se strictly sort karega
                    "listing_price": "--",
                    "current_price": "--",
                    "subscription": {
                        "total": sub_val,
                        "qib": "--",
                        "hni": "--",
                        "retail": "--"
                    },
                    "anchor": "Live Data",
                    "registrar": "Link Intime / KFin"
                })
                seen_ids.add(c_id)

    except Exception as e:
        print(f"Scraper error: {e}")

    return scraped_list