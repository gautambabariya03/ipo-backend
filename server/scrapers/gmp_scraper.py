import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}

def clean_txt(t):
    return re.sub(r'\s+', ' ', t).strip() if t else ""

def parse_num(val_str):
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?', val_str.replace(',', ''))
    return float(nums[0]) if nums else 0.0

def fetch_live_gmp():
    # Cache-busting timestamp parameter to always get fresh data from web
    url = f"https://www.investorgain.com/report/ipo-gmp-live/331/?_t={int(datetime.now().timestamp())}"
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
                    if len(cols) < 6:
                        continue

                    raw_name = clean_txt(cols[0].text)
                    if not raw_name or len(raw_name) < 3 or "IPO" not in raw_name.upper():
                        continue

                    # IPO Name Clean
                    clean_name = re.sub(r'(\(?(BSE\s+|NSE\s+)?SME\)?|IPO[A-Z@\d\.\s\(\)%]*$)', '', raw_name, flags=re.IGNORECASE).strip()
                    clean_name = re.sub(r'\[email&#160;protected\]', '', clean_name).strip()
                    c_id = re.sub(r'[^a-zA-Z0-9]', '-', clean_name.lower())[:35].strip('-')

                    if not c_id or c_id in seen_ids:
                        continue

                    is_sme = "SME" in raw_name.upper()

                    # Live GMP value
                    gmp_text = clean_txt(cols[1].text)
                    gmp_val = parse_num(gmp_text)

                    # Price & Base Price
                    price_text = clean_txt(cols[2].text)
                    base_price = parse_num(price_text)

                    # GMP %
                    gmp_prcnt_text = clean_txt(cols[3].text) if len(cols) > 3 else ""
                    gmp_percent = parse_num(gmp_prcnt_text)
                    if gmp_percent == 0.0 and base_price > 0:
                        gmp_percent = round((gmp_val / base_price) * 100, 2)

                    # Dynamic Real Updated Time directly from Table column
                    # Usually col 6 or 7 contains last updated time on site
                    last_updated_live = ""
                    for c in cols:
                        txt = clean_txt(c.text)
                        if re.search(r'\d{1,2}\s+[A-Za-z]{3}|\d{1,2}:\d{2}', txt):
                            if any(m in txt for m in ["AM", "PM", "mins", "hours", "ago", "Today"]):
                                last_updated_live = txt
                                break
                    if not last_updated_live:
                        last_updated_live = datetime.now().strftime("%d %b, %I:%M %p")

                    # Lot Size
                    lot_text = ""
                    for c in cols[3:]:
                        t = clean_txt(c.text)
                        if t.isdigit() and int(t) >= 10:
                            lot_text = t
                            break
                    lot_size = int(lot_text) if lot_text else (1200 if is_sme else 50)

                    # Dynamic Status Detection
                    row_txt = row.text.upper()
                    if "LISTED" in row_txt or "CLOSED" in row_txt:
                        status = "CLOSED"
                    elif "PRE-APPLY" in row_txt or "UPCOMING" in row_txt:
                        status = "UPCOMING"
                    else:
                        status = "OPEN"

                    scraped_list.append({
                        "id": c_id,
                        "name": clean_name,
                        "category": "SME" if is_sme else "MAINBOARD",
                        "date_range": "Live",
                        "price": price_text if "₹" in price_text else f"₹{price_text}",
                        "lot_size": lot_size,
                        "issue_size": "--",
                        "gmp": gmp_val,
                        "gmp_percentage": gmp_percent,
                        "last_heard": last_updated_live,
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
        print(f"Scraper Live Error: {e}")

    return scraped_list