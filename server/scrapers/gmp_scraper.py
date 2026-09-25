import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def clean_txt(t):
    return re.sub(r'\s+', ' ', t).strip() if t else ""

def parse_price(price_str):
    """प्राइस रेंज से अपर प्राइस बैंड निकालता है (उदा: '₹32 - ₹34' -> 34.0)"""
    nums = re.findall(r'\d+(?:\.\d+)?', price_str)
    if nums:
        return float(nums[-1])
    return 0.0

def fetch_live_gmp():
    url = "https://www.investorgain.com/report/ipo-gmp-live/331/"
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

                    raw_name = clean_txt(cols[0].text)
                    if not raw_name or len(raw_name) < 3:
                        continue

                    # क्लीन कंपनी नाम
                    clean_name = re.sub(r'(\(?(BSE\s+|NSE\s+)?SME\)?|IPO[A-Z@\d\.\s\(\)%]*$)', '', raw_name, flags=re.IGNORECASE).strip()
                    c_id = re.sub(r'[^a-zA-Z0-9]', '-', clean_name.lower())[:35].strip('-')

                    if c_id in seen_ids:
                        continue

                    is_sme = "SME" in raw_name.upper() or "SME" in str(cols[0]).upper()

                    # 1. GMP वैल्यू
                    gmp_text = clean_txt(cols[1].text)
                    gmp_match = re.search(r'[-+]?\d+(?:\.\d+)?', gmp_text.replace(',', ''))
                    gmp_val = float(gmp_match.group(0)) if gmp_match else 0.0

                    # 2. प्राइस
                    price_text = clean_txt(cols[2].text) if len(cols) > 2 else "₹100"
                    if not re.search(r'\d', price_text) and len(cols) > 4:
                        price_text = clean_txt(cols[4].text)
                    base_price = parse_price(price_text)

                    # 3. लॉट साइज
                    lot_text = ""
                    for c in cols[3:]:
                        t = clean_txt(c.text)
                        if t.isdigit() and int(t) >= 10:
                            lot_text = t
                            break
                    lot_size = int(lot_text) if lot_text else (1200 if is_sme else 50)

                    # 4. GMP पर्सेंटेज
                    if base_price > 0:
                        gmp_percent = round((gmp_val / base_price) * 100, 2)
                    else:
                        gmp_percent = 0.0

                    # 5. डेट रेंज / स्टेटस
                    date_range = "Open Now"
                    status = "OPEN"
                    u_row = row.text.upper()
                    if "LISTED" in u_row:
                        status = "CLOSED"
                    elif "UPCOMING" in u_row or "PRE-APPLY" in u_row:
                        status = "UPCOMING"

                    scraped_list.append({
                        "id": c_id,
                        "name": clean_name,
                        "category": "SME" if is_sme else "MAINBOARD",
                        "date_range": date_range,
                        "price": price_text if "₹" in price_text else f"₹{price_text}",
                        "lot_size": lot_size,
                        "issue_size": "--",
                        "gmp": gmp_val,
                        "gmp_percentage": gmp_percent,
                        "last_heard": datetime.now().strftime("%d %b, %I:%M %p"),
                        "allotment_date": "--",
                        "listing_date": "--",
                        "retail_profit": round(gmp_val * lot_size, 2),
                        "hni_profit": round(gmp_val * lot_size * 14, 2),
                        "status": status,
                        "listing_price": "--",
                        "current_price": "--",
                        "subscription": {"total": "--", "qib": "--", "hni": "--", "retail": "--"},
                        "anchor": "Available",
                        "registrar": "Link Intime / KFin"
                    })
                    seen_ids.add(c_id)

    except Exception as e:
        print(f"Scraper Live Error: {e}")

    if scraped_list:
        print(f"Successfully fetched {len(scraped_list)} live IPOs from web.")
        return scraped_list

    print("Warning: Live scraper returned empty, using fallback.")
    return []