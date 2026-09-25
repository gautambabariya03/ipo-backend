import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/"
}

def clean_txt(t):
    return re.sub(r'\s+', ' ', t).strip() if t else ""

def parse_num(val_str):
    if not val_str:
        return 0.0
    clean_s = str(val_str).replace(',', '').replace('₹', '').strip()
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?', clean_s)
    return float(nums[0]) if nums else 0.0

def fetch_live_gmp():
    # InvestorGain Live Report URL
    url = f"https://www.investorgain.com/report/ipo-gmp-live/331/"
    scraped_list = []
    seen_ids = set()

    # IST Time calculation
    ist_time = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    current_time_str = ist_time.strftime("%d %b, %I:%M %p")

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

                    # 1. IPO Name & Clean Up
                    name_col = cols[0]
                    # Agar link tag hai to link ka text uthao
                    link = name_col.find("a")
                    raw_name = clean_txt(link.text if link else name_col.text)
                    
                    if not raw_name or len(raw_name) < 2:
                        continue

                    clean_name = re.sub(r'\[email&#160;protected\]|\[email\s*protected\]', '', raw_name, flags=re.IGNORECASE)
                    clean_name = re.sub(r'\([+-]?\d+(?:\.\d+)?%\)', '', clean_name)
                    clean_name = re.sub(r'(\(?(BSE\s+|NSE\s+)?SME\)?|IPO[A-Z@\d\.\s\(\)%]*$)', '', clean_name, flags=re.IGNORECASE).strip()
                    clean_name = clean_name.strip(' -–@')

                    c_id = re.sub(r'[^a-zA-Z0-9]', '-', clean_name.lower())[:35].strip('-')
                    if not c_id or c_id in seen_ids:
                        continue

                    # Category Check
                    is_sme = any(k in raw_name.upper() for k in ["SME", "NSE SME", "BSE SME"])

                    # 2. Extract Values Safely
                    # Column 1/2 mein GMP hota hai, Column 2/3 mein Price
                    col_texts = [clean_txt(c.text) for c in cols]
                    
                    # Fire icon ya rating ko hatakar saaf numbers nikalo
                    clean_cells = []
                    for t in col_texts[1:]:
                        filtered = re.sub(r'[🔥⭐★]', '', t).strip()
                        if filtered:
                            clean_cells.append(filtered)

                    # GMP Value
                    gmp_val = parse_num(clean_cells[0]) if len(clean_cells) > 0 else 0.0

                    # Issue Price (skip percentage values)
                    base_price = 0.0
                    for cell in clean_cells[1:]:
                        if "%" not in cell:
                            p = parse_num(cell)
                            if p > 0 and p != gmp_val and p < 50000:
                                base_price = p
                                break

                    # Lot Size
                    lot_size = 0
                    for cell in clean_cells[2:]:
                        if cell.isdigit():
                            num = int(cell)
                            if 10 <= num <= 20000 and num != int(base_price):
                                lot_size = num
                                break
                    if lot_size == 0:
                        lot_size = 1200 if is_sme else (50 if base_price > 50 else 100)

                    # GMP Percentage
                    gmp_percent = 0.0
                    for cell in clean_cells:
                        if "%" in cell:
                            gmp_percent = abs(parse_num(cell))
                            break
                    if gmp_percent == 0.0 and base_price > 0 and gmp_val != 0:
                        gmp_percent = round((abs(gmp_val) / base_price) * 100, 2)

                    # Status Determination
                    row_txt = row.text.upper()
                    if any(w in row_txt for w in ["LISTED", "CLOSED"]):
                        status = "CLOSED"
                    elif any(w in row_txt for w in ["PRE-APPLY", "UPCOMING"]):
                        status = "UPCOMING"
                    else:
                        status = "OPEN"

                    scraped_list.append({
                        "id": c_id,
                        "name": clean_name,
                        "category": "SME" if is_sme else "MAINBOARD",
                        "date_range": "Live",
                        "price": f"₹{int(base_price) if base_price.is_integer() else base_price}" if base_price > 0 else "₹--",
                        "lot_size": lot_size,
                        "issue_size": "--",
                        "gmp": gmp_val,
                        "gmp_percentage": gmp_percent,
                        "last_heard": current_time_str,
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
        print(f"Error fetching: {e}")

    return scraped_list