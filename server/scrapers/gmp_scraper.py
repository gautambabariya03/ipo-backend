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

        rows = table.find_all("tr")
        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue

            raw_name = clean_txt(cols[0].text)
            if not raw_name or len(raw_name) < 2 or ("GMP" in raw_name.upper() and len(raw_name) < 6):
                continue

            # 1. CATEGORY: SME vs MAINBOARD
            is_sme = "SME" in raw_name.upper()

            # 2. STATUS: Open (O), Upcoming (U), Closing Today (CT), Closed (C), Listed (L)
            name_upper = raw_name.upper()
            if any(name_upper.endswith(tag) for tag in ["CT", "O", " OPEN"]) or "OPEN" in name_upper:
                status = "OPEN"
            elif any(name_upper.endswith(tag) for tag in ["U", " UPCOMING"]) or "UPCOMING" in name_upper:
                status = "UPCOMING"
            elif any(name_upper.endswith(tag) for tag in ["C", "L", "LISTED", "ALLOTTED"]) or "CLOSED" in name_upper:
                status = "CLOSED"
            else:
                status = "OPEN"

            # Clean Name for UI Display
            clean_name = re.sub(r'\[email&#160;protected\]|\[email\s*protected\]', '', raw_name, flags=re.IGNORECASE)
            clean_name = re.sub(r'(\(?(BSE\s+|NSE\s+)?SME\)?[UOCLCT]*|IPO[UOCLCT]*$|IPO[A-Z@\d\.\s\(\)%]*$)', '', clean_name, flags=re.IGNORECASE).strip()
            clean_name = re.sub(r'\s*@\d+(\.\d+)?\s*\(\d+(\.\d+)?%\)', '', clean_name)
            clean_name = clean_name.strip(' -–@')

            if not clean_name:
                continue

            c_id = re.sub(r'[^a-zA-Z0-9]', '-', clean_name.lower())[:35].strip('-')
            if not c_id or c_id in seen_ids:
                continue

            # 3. EXACT COLUMN VALUES (InvestorGain Live Table Order)
            # Col 1: GMP cell "₹15.5 (45.59%)" ya "₹-- (0.00%)"
            gmp_cell = clean_txt(cols[1].text)
            gmp_val = 0.0
            gmp_percent = 0.0

            if "--" not in gmp_cell and re.search(r'\d', gmp_cell):
                pct_match = re.search(r'\(([+-]?\d+(?:\.\d+)?)%\)', gmp_cell)
                if pct_match:
                    gmp_percent = abs(float(pct_match.group(1)))
                
                cell_without_pct = re.sub(r'\(.*?\)', '', gmp_cell)
                gmp_val = parse_num(cell_without_pct)

            # Col 3: Subscription (Sub) "1.49x" ya "-"
            sub_str = "--"
            if len(cols) > 3:
                sub_raw = clean_txt(cols[3].text)
                if "x" in sub_raw or parse_num(sub_raw) > 0:
                    sub_str = sub_raw if "x" in sub_raw else f"{sub_raw}x"

            # Col 4: Price "34" ya "127"
            base_price = 0.0
            if len(cols) > 4:
                base_price = parse_num(cols[4].text)

            # Fallback for % if not present in cell: (GMP / Price) * 100
            if gmp_percent == 0.0 and base_price > 0 and gmp_val > 0:
                gmp_percent = round((gmp_val / base_price) * 100, 2)

            # Col 5: IPO Size "₹1091.68 Cr"
            size_str = "--"
            if len(cols) > 5:
                s_txt = clean_txt(cols[5].text)
                if "Cr" in s_txt or "₹" in s_txt:
                    size_str = s_txt

            # Col 6: Lot Size "441"
            lot_size = 0
            if len(cols) > 6:
                lot_txt = clean_txt(cols[6].text).replace(',', '')
                if lot_txt.isdigit():
                    lot_size = int(lot_txt)

            if lot_size == 0:
                lot_size = 1200 if is_sme else (50 if base_price > 100 else 100)

            # Col 7 & 8: Open and Close Dates
            open_dt = clean_txt(cols[7].text) if len(cols) > 7 else ""
            close_dt = clean_txt(cols[8].text) if len(cols) > 8 else ""
            date_range = f"{open_dt} - {close_dt}" if open_dt and close_dt else "Live"

            # Accurate Profits Calculation
            retail_profit = round(gmp_val * lot_size, 2) if gmp_val > 0 else 0.0
            hni_profit = round(retail_profit * 14, 2) if retail_profit > 0 else 0.0

            # Current Indian Time
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
                "allotment_date": clean_txt(cols[9].text) if len(cols) > 9 else "--",
                "listing_date": clean_txt(cols[10].text) if len(cols) > 10 else "--",
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