import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone, timedelta
from scrapers.listing_price_scraper import fetch_listing_performance, normalize_name

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}

def clean_txt(t):
    return re.sub(r'\s+', ' ', t).strip() if t else ""

def parse_num(val_str):
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?', val_str.replace(',', '').replace('₹', ''))
    return float(nums[0]) if nums else 0.0

def parse_price(price_str):
    nums = re.findall(r'\d+(?:\.\d+)?', price_str.replace(',', ''))
    if nums:
        return float(nums[-1])
    return 0.0

def parse_date(date_str, default_year=2026):
    if not date_str or date_str in ["--", "", "Live", "Date TBA"]:
        return None
    parts = re.split(r'[\s\-]+', date_str.strip())
    if len(parts) >= 2:
        try:
            day = int(parts[0])
            mon = parts[1].upper()[:3]
            if mon in MONTH_MAP:
                return datetime(default_year, MONTH_MAP[mon], day).date()
        except Exception:
            return None
    return None

def fetch_live_gmp():
    url = f"https://www.investorgain.com/report/ipo-gmp-live/331/?v={int(datetime.now().timestamp())}"
    scraped_list = []
    seen_ids = set()

    ist = timezone(timedelta(hours=5, minutes=30))
    today = datetime.now(ist).date()

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
            if len(cols) < 9:
                continue

            # 1. Company Name Anchor Tag से सुरक्षित रूप से लें
            a_tag = cols[0].find("a")
            raw_name = clean_txt(a_tag.text) if a_tag else clean_txt(cols[0].text)

            name_upper = raw_name.upper()
            if not raw_name or len(raw_name) < 2 or "NAME" in name_upper or "IPO NAME" in name_upper:
                continue

            open_str = clean_txt(cols[7].text)
            close_str = clean_txt(cols[8].text)

            # Header Row को छोड़ें
            if "OPEN" in open_str.upper() or "CLOSE" in close_str.upper():
                continue

            is_sme = "SME" in cols[0].text.upper() or "SME" in name_upper
            category = "SME" if is_sme else "MAINBOARD"

            # कंपनी नाम की सफ़ाई
            clean_name = re.sub(r'\[email&#160;protected\]', '', raw_name, flags=re.IGNORECASE)
            clean_name = re.sub(r'\([+-]?\d+(?:\.\d+)?%\)', '', clean_name)
            clean_name = re.sub(r'(?:BSE\s+|NSE\s+)?SME.*$', '', clean_name, flags=re.IGNORECASE).strip()
            clean_name = re.sub(r'IPO.*$', '', clean_name, flags=re.IGNORECASE).strip()
            clean_title = clean_name.strip(' -–@*🔥')
            if len(clean_title) < 2:
                clean_title = raw_name.strip()

            # साफ़ तारीख
            open_d = parse_date(open_str)
            close_d = parse_date(close_str)

            if open_str and close_str and open_str != "--" and close_str != "--":
                display_date = f"{open_str} - {close_str}"
            elif open_str and open_str != "--":
                display_date = open_str
            else:
                display_date = "Date TBA"

            # 2. Strict Status Sorting (OPEN, UPCOMING, CLOSED)
            raw_cell = cols[0].text.upper()
            if close_d and close_d < today:
                status = "CLOSED"
            elif open_d and open_d > today:
                status = "UPCOMING"
            elif (open_d and open_d <= today and (close_d is None or close_d >= today)) or (close_d and close_d >= today):
                status = "OPEN"
            else:
                if raw_cell.endswith("U") or "UPCOMING" in raw_cell:
                    status = "UPCOMING"
                elif raw_cell.endswith("C") or raw_cell.endswith("L") or "LISTED" in raw_cell or "CLOSED" in raw_cell:
                    status = "CLOSED"
                else:
                    status = "OPEN"

            # 3. GMP वैल्यू
            gmp_text = clean_txt(cols[1].text)
            gmp_val = 0.0
            gmp_pct = 0.0
            if "--" not in gmp_text and re.search(r'\d', gmp_text):
                pct_m = re.search(r'\(([+-]?\d+(?:\.\d+)?)%\)', gmp_text)
                if pct_m:
                    gmp_pct = abs(float(pct_m.group(1)))
                cell_no_pct = re.sub(r'\(.*?\)', '', gmp_text)
                gmp_val = parse_num(cell_no_pct)

            # 4. प्राइस
            price_val = parse_price(cols[4].text)
            if price_val == 0.0 and len(cols) > 2:
                price_val = parse_price(cols[2].text)

            if gmp_pct == 0.0 and price_val > 0 and gmp_val > 0:
                gmp_pct = round((gmp_val / price_val) * 100, 2)

            # 5. इश्यू साइज और लॉट साइज
            sz_txt = clean_txt(cols[5].text)
            size_val = sz_txt if ("Cr" in sz_txt or "₹" in sz_txt) else "--"

            l_txt = clean_txt(cols[6].text).replace(',', '')
            lot_val = int(l_txt) if l_txt.isdigit() else (1200 if is_sme else (50 if price_val > 100 else 100))

            ret_prof = round(gmp_val * lot_val, 2) if gmp_val > 0 else 0.0
            hni_prof = round(ret_prof * 14, 2) if ret_prof > 0 else 0.0

            # फ़ालतू या हेडर कार्ड्स को बाहर निकालें
            if clean_title.upper() in ["NAME", "IPO NAME", ""] or (display_date == "Date TBA" and price_val == 0.0 and gmp_val == 0.0):
                continue

            base_id = re.sub(r'[^a-zA-Z0-9]', '-', clean_title.lower()).strip('-')
            c_id = base_id
            dup_n = 1
            while c_id in seen_ids:
                dup_n += 1
                c_id = f"{base_id}-{dup_n}"
            seen_ids.add(c_id)

            now_str = datetime.now(ist).strftime("%d %b, %I:%M %p")
            allot_str = clean_txt(cols[9].text) if len(cols) > 9 else "--"
            list_str = clean_txt(cols[10].text) if len(cols) > 10 else "--"
            final_allot_str = allot_str if "BOA" not in allot_str.upper() else "--"

            # Allotment is only "declared" once that date has actually arrived
            # (used to decide which IPOs are eligible for the allotment checker)
            allot_d = parse_date(final_allot_str)
            allotment_declared = bool(allot_d and allot_d <= today)

            scraped_list.append({
                "id": c_id,
                "name": clean_title,
                "category": category,
                "date_range": display_date,
                "price": f"₹{int(price_val) if price_val.is_integer() else price_val}" if price_val > 0 else "--",
                "lot_size": lot_val,
                "issue_size": size_val,
                "gmp": gmp_val,
                "gmp_percentage": gmp_pct,
                "last_heard": now_str,
                "allotment_date": final_allot_str,
                "allotment_declared": allotment_declared,
                "listing_date": list_str if "LISTING" not in list_str.upper() else "--",
                "retail_profit": ret_prof,
                "hni_profit": hni_prof,
                "status": status,
                "listing_price": "--",
                "current_price": "--",
                "subscription": {
                    "total": clean_txt(cols[3].text) if len(cols) > 3 else "--",
                    "qib": "--",
                    "hni": "--",
                    "retail": "--"
                },
                "anchor": "Live Data",
                "registrar": "Link Intime / KFin"
            })

    except Exception as e:
        print(f"Scraper Error: {e}")

    # CLOSED IPOs ke liye asli Listing Price aur Current Price (LTP) fetch karo
    # (sirf ek extra request, sab CLOSED items ke liye ek saath match karke)
    if any(item["status"] == "CLOSED" for item in scraped_list):
        try:
            listing_data = fetch_listing_performance()
            for item in scraped_list:
                if item["status"] != "CLOSED":
                    continue
                key = normalize_name(item["name"])
                match = listing_data.get(key)
                if match:
                    item["listing_price"] = match["listing_price"]
                    item["current_price"] = match["current_price"]
        except Exception as e:
            print(f"Listing Price Merge Error: {e}")

    return scraped_list