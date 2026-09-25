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
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        # Table Header Mapping
        th_elements = table.find_all("th")
        col_map = {"name": 0, "gmp": 1, "sub": 3, "price": 4, "size": 5, "lot": 6, "open": 7, "close": 8}
        
        if th_elements:
            for idx, th in enumerate(th_elements):
                th_text = th.text.strip().lower()
                if "ipo" in th_text or "name" in th_text:
                    col_map["name"] = idx
                elif "gmp" in th_text and "sub" not in th_text:
                    col_map["gmp"] = idx
                elif "sub" in th_text:
                    col_map["sub"] = idx
                elif "price" in th_text:
                    col_map["price"] = idx
                elif "size" in th_text:
                    col_map["size"] = idx
                elif "lot" in th_text:
                    col_map["lot"] = idx
                elif "open" in th_text:
                    col_map["open"] = idx
                elif "close" in th_text:
                    col_map["close"] = idx

        rows = table.find_all("tr")
        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue

            raw_name = clean_txt(cols[col_map["name"]].text)
            if not raw_name or len(raw_name) < 2 or ("GMP" in raw_name.upper() and len(raw_name) < 6):
                continue

            # 1. CATEGORY: SME vs MAINBOARD
            is_sme = "SME" in raw_name.upper()

            # 2. STRICT STATUS IDENTIFICATION
            name_upper = raw_name.upper()
            row_upper = row.text.upper()

            # Close / Open Dates check
            close_dt = clean_txt(cols[col_map["close"]].text) if len(cols) > col_map["close"] else ""
            open_dt = clean_txt(cols[col_map["open"]].text) if len(cols) > col_map["open"] else ""

            # Pehle CLOSED aur LISTED alag karein
            if (
                any(name_upper.endswith(tag) for tag in [" C", " L", "CL", "CLOSED", "LISTED"]) or
                "LISTED" in row_upper or 
                "CLOSED" in row_upper or
                "ALLOTTED" in row_upper or
                re.search(r'\b(C|L)\b', name_upper)
            ):
                status = "CLOSED"
            elif (
                any(name_upper.endswith(tag) for tag in [" U", "UPCOMING"]) or 
                "UPCOMING" in row_upper or 
                "PRE-APPLY" in row_upper
            ):
                status = "UPCOMING"
            elif (
                any(name_upper.endswith(tag) for tag in [" O", " CT", "OPEN"]) or 
                "OPEN" in row_upper or
                "CLOSING TODAY" in row_upper
            ):
                status = "OPEN"
            else:
                status = "CLOSED"

            # Clean Display Name
            clean_name = re.sub(r'\[email&#160;protected\]|\[email\s*protected\]', '', raw_name, flags=re.IGNORECASE)
            clean_name = re.sub(r'(\(?(BSE\s+|NSE\s+)?SME\)?[UOCLCT]*|IPO[UOCLCT]*$|IPO[A-Z@\d\.\s\(\)%]*$)', '', clean_name, flags=re.IGNORECASE).strip()
            clean_name = re.sub(r'\s*@\d+(\.\d+)?\s*\(\d+(\.\d+)?%\)', '', clean_name)
            clean_name = clean_name.strip(' -–@')

            if not clean_name:
                continue

            c_id = re.sub(r'[^a-zA-Z0-9]', '-', clean_name.lower())[:35].strip('-')
            if not c_id or c_id in seen_ids:
                continue

            # 3. EXACT GMP & PERCENTAGE
            gmp_cell = clean_txt(cols[col_map["gmp"]].text)
            gmp_val = 0.0
            gmp_percent = 0.0

            if "--" not in gmp_cell and re.search(r'\d', gmp_cell):
                pct_match = re.search(r'\(([+-]?\d+(?:\.\d+)?)%\)', gmp_cell)
                if pct_match:
                    gmp_percent = abs(float(pct_match.group(1)))
                
                cell_no_pct = re.sub(r'\(.*?\)', '', gmp_cell)
                gmp_val = parse_num(cell_no_pct)

            # 4. SUBSCRIPTION MULTIPLE
            sub_str = "--"
            if len(cols) > col_map["sub"]:
                sub_raw = clean_txt(cols[col_map["sub"]].text)
                if "x" in sub_raw or parse_num(sub_raw) > 0:
                    sub_str = sub_raw if "x" in sub_raw else f"{sub_raw}x"

            # 5. PRICE
            base_price = 0.0
            if len(cols) > col_map["price"]:
                base_price = parse_num(cols[col_map["price"]].text)

            if gmp_percent == 0.0 and base_price > 0 and gmp_val > 0:
                gmp_percent = round((gmp_val / base_price) * 100, 2)

            # 6. ISSUE SIZE
            size_str = "--"
            if len(cols) > col_map["size"]:
                s_txt = clean_txt(cols[col_map["size"]].text)
                if "Cr" in s_txt or "₹" in s_txt:
                    size_str = s_txt

            # 7. LOT SIZE
            lot_size = 0
            if len(cols) > col_map["lot"]:
                lot_txt = clean_txt(cols[col_map["lot"]].text).replace(',', '')
                if lot_txt.isdigit():
                    lot_size = int(lot_txt)

            if lot_size == 0:
                lot_size = 1200 if is_sme else (50 if base_price > 100 else 100)

            # 8. DATE RANGE
            date_range = f"{open_dt} - {close_dt}" if open_dt and close_dt else "Live"

            # 9. ACCURATE PROFITS
            retail_profit = round(gmp_val * lot_size, 2) if gmp_val > 0 else 0.0
            hni_profit = round(retail_profit * 14, 2) if retail_profit > 0 else 0.0

            # Indian Time (IST)
            ist_zone = timezone(timedelta(hours=5, minutes=30))
            last_heard_time = datetime.now(ist_zone).strftime("%d %b, %I:%M %p")

            scraped_list.append({
                "id": c_id,
                "name": clean_name,
                "category": "SME" if is_sme else "MAINBOARD",
                "date_range": date_range,
                "price": f"₹{int(base_price) if base_price.is_integer() else base_price}" if base_price > 0 else "--",
                "lot_size": lot_size,
                "issue_size": size_str,
                "gmp": gmp_val,
                "gmp_percentage": gmp_percent,
                "last_heard": last_heard_time,
                "allotment_date": "--",
                "listing_date": "--",
                "retail_profit": retail_profit,
                "hni_profit": hni_profit,
                "status": status,
                "listing_price": "--",
                "current_price": "--",
                "subscription": {
                    "total": sub_str,
                    "qib": "--",
                    "hni": "--",
                    "retail": "--"
                },
                "anchor": "Live Data",
                "registrar": "Link Intime / KFin"
            })
            seen_ids.add(c_id)

    except Exception as e:
        print(f"Scraper Error: {e}")

    return scraped_list