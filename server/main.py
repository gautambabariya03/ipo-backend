import sys
import os
import re
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Server path जोड़ें
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = FastAPI(title="IPO Live Backend API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}

def clean_txt(t):
    return re.sub(r'\s+', ' ', t).strip() if t else ""

def parse_num(val_str):
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?', val_str.replace(',', '').replace('₹', ''))
    return float(nums[0]) if nums else 0.0

def parse_date(date_str, default_year=2026):
    """तारीख जैसे '25-Sep' या '29-Sep' को डेट ऑब्जेक्ट में बदलता है"""
    if not date_str or date_str in ["--", "", "Live"]:
        return None
    parts = re.split(r'[\s\-]+', clean_txt(date_str))
    if len(parts) >= 2:
        try:
            day = int(parts[0])
            mon = parts[1].upper()[:3]
            if mon in MONTH_MAP:
                return datetime(default_year, MONTH_MAP[mon], day).date()
        except Exception:
            return None
    return None

def fetch_and_process_ipos():
    url = f"https://www.investorgain.com/report/ipo-gmp-live/331/?v={int(datetime.now().timestamp())}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    scraped_list = []
    seen_ids = set()

    # आज की लाइव तारीख (IST)
    ist = timezone(timedelta(hours=5, minutes=30))
    today = datetime.now(ist).date()

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

            # 1. कंपनी का नाम सीधे <a> लिंक से निकालें ताकि नाम कभी गायब न हो
            a_tag = cols[0].find("a")
            if a_tag:
                raw_name = clean_txt(a_tag.text)
            else:
                raw_name = clean_txt(cols[0].text)

            if not raw_name or len(raw_name) < 2 or "IPO NAME" in raw_name.upper():
                continue

            # Category
            is_sme = "SME" in cols[0].text.upper() or "SME" in raw_name.upper()
            category = "SME" if is_sme else "MAINBOARD"

            # 2. सुरक्षित नाम की सफ़ाई (बिना नाम उड़ाए)
            clean_title = raw_name
            clean_title = re.sub(r'\[email&#160;protected\]', '', clean_title, flags=re.IGNORECASE)
            clean_title = re.sub(r'\([+-]?\d+(?:\.\d+)?%\)', '', clean_title)
            clean_title = re.sub(r'(?:BSE\s+|NSE\s+)?SME.*$', '', clean_title, flags=re.IGNORECASE).strip()
            clean_title = re.sub(r'IPO.*$', '', clean_title, flags=re.IGNORECASE).strip()
            clean_title = clean_title.strip(' -–@*🔥')

            if len(clean_title) < 2:
                clean_title = raw_name.strip()

            # 3. तारीखें Col 7 (Open) और Col 8 (Close) से सीधे उठाएँ (GMP कभी नहीं घुसेगा)
            open_str = clean_txt(cols[7].text)
            close_str = clean_txt(cols[8].text)

            open_d = parse_date(open_str)
            close_d = parse_date(close_str)

            if open_str and close_str and open_str != "--" and close_str != "--":
                display_date = f"{open_str} - {close_str}"
            elif open_str and open_str != "--":
                display_date = open_str
            else:
                display_date = "Live"

            # 4. स्टेटस लॉजिक (OPEN, UPCOMING, CLOSED)
            raw_cell = cols[0].text.upper()

            # Closed: जो आज से पहले बंद हो चुके हैं
            if close_d and close_d < today:
                status = "CLOSED"
            # Upcoming: जो आज के बाद शुरू होंगे
            elif open_d and open_d > today:
                status = "UPCOMING"
            # Open: जो आज चल रहे हैं (24-29, 25-29 आदि)
            elif (open_d and open_d <= today and (close_d is None or close_d >= today)) or (close_d and close_d >= today):
                status = "OPEN"
            else:
                if raw_cell.endswith("U") or "UPCOMING" in raw_cell:
                    status = "UPCOMING"
                elif raw_cell.endswith("C") or raw_cell.endswith("L") or "LISTED" in raw_cell or "CLOSED" in raw_cell:
                    status = "CLOSED"
                else:
                    status = "OPEN"

            # GMP (Col 1)
            gmp_text = clean_txt(cols[1].text)
            gmp_val = 0.0
            gmp_pct = 0.0
            if "--" not in gmp_text and re.search(r'\d', gmp_text):
                pct_m = re.search(r'\(([+-]?\d+(?:\.\d+)?)%\)', gmp_text)
                if pct_m:
                    gmp_pct = abs(float(pct_m.group(1)))
                cell_no_pct = re.sub(r'\(.*?\)', '', gmp_text)
                gmp_val = parse_num(cell_no_pct)

            # Issue Price (Col 4)
            price_val = parse_num(cols[4].text)
            if gmp_pct == 0.0 and price_val > 0 and gmp_val > 0:
                gmp_pct = round((gmp_val / price_val) * 100, 2)

            # Issue Size (Col 5)
            sz_txt = clean_txt(cols[5].text)
            size_val = sz_txt if ("Cr" in sz_txt or "₹" in sz_txt) else "--"

            # Lot Size (Col 6)
            l_txt = clean_txt(cols[6].text).replace(',', '')
            lot_val = int(l_txt) if l_txt.isdigit() else (1200 if is_sme else (50 if price_val > 100 else 100))

            # Profit Calculations
            ret_prof = round(gmp_val * lot_val, 2) if gmp_val > 0 else 0.0
            hni_prof = round(ret_prof * 14, 2) if ret_prof > 0 else 0.0

            # Unique ID
            c_id = re.sub(r'[^a-zA-Z0-9]', '-', clean_title.lower()).strip('-') + f"-{idx}"
            if c_id in seen_ids:
                continue
            seen_ids.add(c_id)

            now_str = datetime.now(ist).strftime("%d %b, %I:%M %p")

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
                "allotment_date": clean_txt(cols[9].text) if len(cols) > 9 else "--",
                "listing_date": clean_txt(cols[10].text) if len(cols) > 10 else "--",
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
        print(f"Error fetching: {e}")

    return scraped_list

@app.get("/")
def root():
    return {"message": "IPO Live Backend is Running Successfully"}

@app.get("/api/ipos/live")
def get_live_ipos(force_refresh: bool = False):
    return fetch_and_process_ipos()

@app.get("/api/ipos")
def get_ipos_alias():
    return fetch_and_process_ipos()