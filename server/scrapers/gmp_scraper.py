import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone, timedelta

def clean_txt(t):
    return re.sub(r'\s+', ' ', t).strip() if t else ""

def parse_num(val_str):
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?', val_str.replace(',', '').replace('₹', ''))
    return float(nums[0]) if nums else 0.0

def fetch_live_gmp():
    url = f"https://www.investorgain.com/report/ipo-gmp-live/331/?v={int(datetime.now().timestamp())}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    scraped_list = []
    seen_ids = set()
    ist = timezone(timedelta(hours=5, minutes=30))

    try:
        resp = requests.get(url, headers=headers, timeout=15)
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

            # कंपनी का नाम सीधे <a> लिंक से लें
            a_tag = cols[0].find("a")
            raw_name = clean_txt(a_tag.text) if a_tag else clean_txt(cols[0].text)

            # हेडर और फ़ालतू पंक्तियों को सीधे फ़िल्टर करें
            name_check = raw_name.upper()
            if not raw_name or len(raw_name) < 2 or "NAME" in name_check or "IPO NAME" in name_check:
                continue

            open_str = clean_txt(cols[7].text)
            close_str = clean_txt(cols[8].text)
            if "OPEN" in open_str.upper() or "CLOSE" in close_str.upper():
                continue

            is_sme = "SME" in cols[0].text.upper() or "SME" in name_check
            category = "SME" if is_sme else "MAINBOARD"

            clean_title = raw_name
            clean_title = re.sub(r'\[email&#160;protected\]', '', clean_title, flags=re.IGNORECASE)
            clean_title = re.sub(r'\([+-]?\d+(?:\.\d+)?%\)', '', clean_title)
            clean_title = re.sub(r'(?:BSE\s+|NSE\s+)?SME.*$', '', clean_title, flags=re.IGNORECASE).strip()
            clean_title = re.sub(r'IPO.*$', '', clean_title, flags=re.IGNORECASE).strip()
            clean_title = clean_title.strip(' -–@*🔥')
            if len(clean_title) < 2:
                clean_title = raw_name.strip()

            # साफ़ तारीखें
            if open_str and close_str and open_str != "--" and close_str != "--":
                display_date = f"{open_str} - {close_str}"
            elif open_str and open_str != "--":
                display_date = open_str
            else:
                display_date = "Date TBA"

            gmp_text = clean_txt(cols[1].text)
            gmp_val = 0.0
            gmp_pct = 0.0
            if "--" not in gmp_text and re.search(r'\d', gmp_text):
                pct_m = re.search(r'\(([+-]?\d+(?:\.\d+)?)%\)', gmp_text)
                if pct_m:
                    gmp_pct = abs(float(pct_m.group(1)))
                cell_no_pct = re.sub(r'\(.*?\)', '', gmp_text)
                gmp_val = parse_num(cell_no_pct)

            price_val = parse_num(cols[4].text)
            if gmp_pct == 0.0 and price_val > 0 and gmp_val > 0:
                gmp_pct = round((gmp_val / price_val) * 100, 2)

            sz_txt = clean_txt(cols[5].text)
            size_val = sz_txt if ("Cr" in sz_txt or "₹" in sz_txt) else "--"

            l_txt = clean_txt(cols[6].text).replace(',', '')
            lot_val = int(l_txt) if l_txt.isdigit() else (1200 if is_sme else (50 if price_val > 100 else 100))

            ret_prof = round(gmp_val * lot_val, 2) if gmp_val > 0 else 0.0
            hni_prof = round(ret_prof * 14, 2) if ret_prof > 0 else 0.0

            if clean_title.upper() in ["NAME", "IPO NAME", ""] or (display_date == "Date TBA" and price_val == 0.0 and gmp_val == 0.0):
                continue

            c_id = re.sub(r'[^a-zA-Z0-9]', '-', clean_title.lower()).strip('-') + f"-{idx}"
            if c_id in seen_ids:
                continue
            seen_ids.add(c_id)

            now_str = datetime.now(ist).strftime("%d %b, %I:%M %p")
            allot_str = clean_txt(cols[9].text) if len(cols) > 9 else "--"
            list_str = clean_txt(cols[10].text) if len(cols) > 10 else "--"

            scraped_list.append({
                "id": c_id,
                "name": clean_title,
                "raw_tag": cols[0].text,
                "category": category,
                "date_range": display_date,
                "open_raw": open_str,
                "close_raw": close_str,
                "price": f"₹{int(price_val) if price_val.is_integer() else price_val}" if price_val > 0 else "--",
                "lot_size": lot_val,
                "issue_size": size_val,
                "gmp": gmp_val,
                "gmp_percentage": gmp_pct,
                "last_heard": now_str,
                "allotment_date": allot_str if "BOA" not in allot_str.upper() else "--",
                "listing_date": list_str if "LISTING" not in list_str.upper() else "--",
                "retail_profit": ret_prof,
                "hni_profit": hni_prof,
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

    return scraped_list