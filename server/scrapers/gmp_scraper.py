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
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?', val_str.replace(',', '').replace('₹', ''))
    return float(nums[0]) if nums else 0.0

def fetch_live_gmp():
    url = f"https://www.investorgain.com/report/ipo-gmp-live/331/?v={int(datetime.now().timestamp())}"
    scraped_list = []
    seen_names = set()

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        rows = table.find_all("tr")

        for idx, row in enumerate(rows):
            cols = row.find_all(["td", "th"])
            # अगर सेल बहुत कम हैं या हेडर पंक्ति है तो छोड़ें
            if len(cols) < 3:
                continue

            raw_name = clean_txt(cols[0].text)
            
            # हेडर या खाली नाम छोड़ें
            if not raw_name or len(raw_name) < 2 or raw_name.upper() in ["IPO", "IPO NAME", "COMPANY"]:
                continue

            # 1. SME vs MAINBOARD
            is_sme = "SME" in raw_name.upper()

            # 2. STATUS CHECK (Open, Upcoming, Closed)
            name_u = raw_name.upper()
            row_u = row.text.upper()

            if any(k in name_u for k in ["(L)", "LISTED", "CLOSED"]) or "LISTED" in row_u or "CLOSED" in row_u or name_u.endswith(" C") or name_u.endswith(" L"):
                status = "CLOSED"
            elif "(U)" in name_u or name_u.endswith(" U") or "UPCOMING" in row_u or "PRE-APPLY" in row_u:
                status = "UPCOMING"
            else:
                status = "OPEN"

            # Clean Name
            clean_name = re.sub(r'\[email&#160;protected\]|\[email\s*protected\]', '', raw_name, flags=re.IGNORECASE)
            clean_name = re.sub(r'\([+-]?\d+(?:\.\d+)?%\)', '', clean_name)
            clean_name = re.sub(r'(\(?(BSE\s+|NSE\s+)?SME\)?[UOCLCT]*|IPO[UOCLCT]*$|IPO[A-Z@\d\.\s\(\)%]*$)', '', clean_name, flags=re.IGNORECASE).strip()
            clean_name = clean_name.strip(' -–@')

            if not clean_name or clean_name.lower() in seen_names:
                continue

            # Unique ID
            c_id = re.sub(r'[^a-zA-Z0-9]', '-', clean_name.lower()).strip('-') + f"-{idx}"
            seen_names.add(clean_name.lower())

            # 3. EXTRACT GMP (Col 1)
            gmp_text = clean_txt(cols[1].text) if len(cols) > 1 else ""
            gmp_val = 0.0
            gmp_pct = 0.0

            if "--" not in gmp_text and re.search(r'\d', gmp_text):
                pct_m = re.search(r'\(([+-]?\d+(?:\.\d+)?)%\)', gmp_text)
                if pct_m:
                    gmp_pct = abs(float(pct_m.group(1)))
                cell_no_pct = re.sub(r'\(.*?\)', '', gmp_text)
                gmp_val = parse_num(cell_no_pct)

            # 4. SUBSCRIPTION (Col 3)
            sub_val = "--"
            if len(cols) > 3:
                s_txt = clean_txt(cols[3].text)
                if "x" in s_txt.lower() or parse_num(s_txt) > 0:
                    sub_val = s_txt if "x" in s_txt.lower() else f"{s_txt}x"

            # 5. ISSUE PRICE (Col 4)
            price_val = 0.0
            if len(cols) > 4:
                price_val = parse_num(cols[4].text)

            if gmp_pct == 0.0 and price_val > 0 and gmp_val > 0:
                gmp_pct = round((gmp_val / price_val) * 100, 2)

            # 6. ISSUE SIZE (Col 5)
            size_val = "--"
            if len(cols) > 5:
                sz_txt = clean_txt(cols[5].text)
                if "Cr" in sz_txt or "₹" in sz_txt:
                    size_val = sz_txt

            # 7. LOT SIZE (Col 6)
            lot_val = 0
            if len(cols) > 6:
                l_txt = clean_txt(cols[6].text).replace(',', '')
                if l_txt.isdigit():
                    lot_val = int(l_txt)

            if lot_val == 0:
                lot_val = 1200 if is_sme else (50 if price_val > 100 else 100)

            # Dates (Col 7 & 8)
            open_d = clean_txt(cols[7].text) if len(cols) > 7 else ""
            close_d = clean_txt(cols[8].text) if len(cols) > 8 else ""
            date_range = f"{open_d} - {close_d}" if open_d and close_d else "Live"

            # Accurate Profit Calculation
            ret_prof = round(gmp_val * lot_val, 2) if gmp_val > 0 else 0.0
            hni_prof = round(ret_prof * 14, 2) if ret_prof > 0 else 0.0

            # IST Timestamp
            ist = timezone(timedelta(hours=5, minutes=30))
            now_str = datetime.now(ist).strftime("%d %b, %I:%M %p")

            scraped_list.append({
                "id": c_id,
                "name": clean_name,
                "category": "SME" if is_sme else "MAINBOARD",
                "date_range": date_range,
                "price": f"₹{int(price_val) if price_val.is_integer() else price_val}" if price_val > 0 else "--",
                "lot_size": lot_val,
                "issue_size": size_val,
                "gmp": gmp_val,
                "gmp_percentage": gmp_pct,
                "last_heard": now_str,
                "allotment_date": clean_txt(cols[9].text) if len(cols) > 9 else "--",
                "listing_date": clean_txt(cols[10].text) if len(cols) > 10 else "--",
                "retail_profit": ret_prof,
                "hni_profit": hni_prof,
                "status": status,
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

    except Exception as e:
        print(f"Scraper error: {e}")

    return scraped_list