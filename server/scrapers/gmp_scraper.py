import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}

def clean_txt(t):
    return re.sub(r'\s+', ' ', t).strip() if t else ""

def parse_num(val_str):
    clean_s = val_str.replace(',', '').replace('₹', '').strip()
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?', clean_s)
    return float(nums[0]) if nums else 0.0

def fetch_live_gmp():
    url = f"https://www.investorgain.com/report/ipo-gmp-live/331/?v={int(datetime.now().timestamp())}"
    scraped_list = []
    seen_ids = set()

    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table")
            
            if table:
                rows = table.find_all("tr")
                for row in rows[1:]:
                    cols = row.find_all("td")
                    if len(cols) < 5:
                        continue

                    # 1. Clean Company Name
                    raw_name = clean_txt(cols[0].text)
                    if not raw_name or len(raw_name) < 2 or "GMP" in raw_name.upper() and len(raw_name) < 6:
                        continue

                    clean_name = re.sub(r'\[email&#160;protected\]|\[email\s*protected\]', '', raw_name, flags=re.IGNORECASE)
                    clean_name = re.sub(r'\([+-]?\d+(?:\.\d+)?%\)', '', clean_name)
                    clean_name = re.sub(r'(\(?(BSE\s+|NSE\s+)?SME\)?|IPO[A-Z@\d\.\s\(\)%]*$)', '', clean_name, flags=re.IGNORECASE).strip()
                    clean_name = clean_name.strip(' -–@')

                    if not clean_name or len(clean_name) < 2:
                        continue

                    c_id = re.sub(r'[^a-zA-Z0-9]', '-', clean_name.lower())[:35].strip('-')
                    if not c_id or c_id in seen_ids:
                        continue

                    row_full_text = clean_txt(row.text).upper()
                    is_sme = "SME" in row_full_text or "NSE SME" in row_full_text or "BSE SME" in row_full_text

                    # 2. Extract Price, GMP and %
                    all_cells = [clean_txt(c.text) for c in cols[1:]]
                    
                    gmp_val = 0.0
                    base_price = 0.0
                    gmp_percent = 0.0

                    # Detect % directly if printed
                    for txt in all_cells:
                        if "%" in txt:
                            gmp_percent = abs(parse_num(txt))
                            break

                    extracted_numbers = []
                    for txt in all_cells:
                        if any(ch in txt for ch in ["🔥", "⭐", "★"]):
                            continue
                        n = parse_num(txt)
                        if n != 0.0 or txt.strip() == "0":
                            extracted_numbers.append(n)

                    if len(extracted_numbers) >= 2:
                        gmp_val = extracted_numbers[0]
                        base_price = extracted_numbers[1]
                    elif len(extracted_numbers) == 1:
                        base_price = extracted_numbers[0]

                    if gmp_val == 0.0 and gmp_percent > 0 and base_price > 0:
                        gmp_val = round((gmp_percent * base_price) / 100, 1)

                    if gmp_percent == 0.0 and base_price > 0 and gmp_val != 0:
                        gmp_percent = round((abs(gmp_val) / base_price) * 100, 2)

                    # Lot Size
                    lot_size = 0
                    for txt in all_cells[2:]:
                        if txt.isdigit():
                            num = int(txt)
                            if 10 <= num <= 20000 and num != int(base_price) and num != int(gmp_val):
                                lot_size = num
                                break
                    if lot_size == 0:
                        lot_size = 1200 if is_sme else (50 if base_price > 50 else 100)

                    # Indian Time (IST) without external pytz
                    ist_zone = timezone(timedelta(hours=5, minutes=30))
                    now_ist = datetime.now(ist_zone)
                    last_heard_time = now_ist.strftime("%d %b, %I:%M %p")

                    # Status
                    if any(w in row_full_text for w in ["LISTED", "CLOSED", "ALLOTTED"]):
                        status = "CLOSED"
                    elif any(w in row_full_text for w in ["PRE-APPLY", "UPCOMING", "YET TO"]):
                        status = "UPCOMING"
                    else:
                        status = "OPEN"

                    scraped_list.append({
                        "id": c_id,
                        "name": clean_name,
                        "category": "SME" if is_sme else "MAINBOARD",
                        "date_range": "Live",
                        "price": f"₹{int(base_price) if base_price.is_integer() else base_price}" if base_price > 0 else "--",
                        "lot_size": lot_size,
                        "issue_size": "--",
                        "gmp": gmp_val,
                        "gmp_percentage": gmp_percent,
                        "last_heard": last_heard_time,
                        "allotment_date": "--",
                        "listing_date": "--",
                        "retail_profit": round(gmp_val * lot_size, 2),
                        "hni_profit": round(gmp_val * lot_size * 14, 2),
                        "status": status,
                        "listing_price": "--",
                        "current_price": "--",
                        "subscription": {"total": "--", "qib": "--", "hni": "--", "retail": "--"},
                        "anchor": "Live Data",
                        "registrar": "Link Intime / KFin"
                    })
                    seen_ids.add(c_id)
    except Exception as e:
        print(f"Scraper Error: {e}")

    return scraped_list