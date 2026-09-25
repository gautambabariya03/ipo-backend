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
    clean_s = val_str.replace(',', '').replace('₹', '').strip()
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?', clean_s)
    return float(nums[0]) if nums else 0.0

def fetch_live_gmp():
    url = f"https://www.ipopremium.in/?v={int(datetime.now().timestamp())}"
    scraped_list = []
    seen_ids = set()

    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # IPO Premium list blocks
        all_text = soup.get_text()
        
        # Cards search across all potential blocks
        cards = soup.find_all(lambda tag: tag.name in ["div", "tr", "li"] and ("Mainboard" in tag.text or "SME" in tag.text) and len(tag.text) < 600)
        
        # If standard card tags aren't isolated, extract rows directly
        if not cards:
            cards = soup.find_all(["tr", "div"])

        for card in cards:
            text = clean_txt(card.text)
            if not text or len(text) < 15:
                continue

            if not ("Mainboard" in text or "SME" in text):
                continue

            # Extract Category
            is_sme = "SME" in text
            category = "SME" if is_sme else "MAINBOARD"

            # Extract Company Name
            name_match = re.search(r'([A-Za-z0-9\s\.\&\(\)\'-]+?)\s*(?:Mainboard|BSE SME|NSE SME)', text)
            if not name_match:
                continue
            
            raw_name = clean_txt(name_match.group(1))
            if len(raw_name) < 3 or any(w in raw_name.upper() for w in ["SEARCH", "PREMIUM", "SIGN IN", "CALENDAR"]):
                continue

            c_id = re.sub(r'[^a-zA-Z0-9]', '-', raw_name.lower())[:35].strip('-')
            if not c_id or c_id in seen_ids:
                continue

            # Extract Status
            text_u = text.upper()
            if any(w in text_u for w in ["CLOSED", "LISTED", "AWAITING ALLOTMENT"]):
                status = "CLOSED"
            elif any(w in text_u for w in ["OPENS IN", "PRE-APPLY"]):
                status = "UPCOMING"
            elif any(w in text_u for w in ["CLOSES IN", "CLOSES TODAY", "APPLY"]):
                status = "OPEN"
            else:
                status = "OPEN"

            # Extract Dates (e.g., Sep 24 – Sep 28)
            date_m = re.search(r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s*[–-]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\s*\d{1,2})', text, re.IGNORECASE)
            date_range = date_m.group(1) if date_m else "Live"

            # Extract GMP and Percentage (e.g. ₹15.5+45.6% or ₹0)
            gmp_m = re.search(r'₹\s*([0-9\.]+)\s*(?:[+–-]\s*([0-9\.]+)%)?', text)
            gmp_val = 0.0
            gmp_pct = 0.0
            if gmp_m:
                gmp_val = parse_num(gmp_m.group(1))
                if gmp_m.group(2):
                    gmp_pct = parse_num(gmp_m.group(2))

            # Extract Price (e.g. ₹32–34 or ₹258–272)
            price_m = re.search(r'₹\s*(\d+)(?:[–-]\s*(\d+))?', text[gmp_m.end():] if gmp_m else text)
            base_price = 0.0
            price_display = "--"
            if price_m:
                p1 = parse_num(price_m.group(1))
                p2 = parse_num(price_m.group(2)) if price_m.group(2) else p1
                base_price = max(p1, p2)
                price_display = f"₹{int(base_price)}"

            if gmp_pct == 0.0 and base_price > 0 and gmp_val > 0:
                gmp_pct = round((gmp_val / base_price) * 100, 2)

            # Extract Lot Size (e.g. 441, 55, 1200)
            lot_size = 0
            lot_m = re.search(r'\b(441|1200|1600|2000|1000|600|85|115|49|55|37|41|111|101|150|50|100)\b', text)
            if lot_m:
                lot_size = int(lot_m.group(1))
            else:
                lot_size = 1200 if is_sme else (50 if base_price > 100 else 100)

            # Extract Issue Size (e.g. ₹1,091.68 cr)
            size_m = re.search(r'₹\s*([0-9,]+(?:\.[0-9]+)?\s*cr)', text, re.IGNORECASE)
            issue_size = f"₹{size_m.group(1)}" if size_m else "--"

            # IST Timestamp
            ist = timezone(timedelta(hours=5, minutes=30))
            last_heard = datetime.now(ist).strftime("%d %b, %I:%M %p")

            # Profit Calculations
            ret_profit = round(gmp_val * lot_size, 2) if gmp_val > 0 else 0.0
            hni_profit = round(ret_profit * 14, 2) if ret_profit > 0 else 0.0

            scraped_list.append({
                "id": c_id,
                "name": raw_name,
                "category": category,
                "date_range": date_range,
                "price": price_display,
                "lot_size": lot_size,
                "issue_size": issue_size,
                "gmp": gmp_val,
                "gmp_percentage": gmp_pct,
                "last_heard": last_heard,
                "allotment_date": "--",
                "listing_date": "--",
                "retail_profit": ret_profit,
                "hni_profit": hni_profit,
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