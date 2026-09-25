import sys
import os
import re
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    """Parses date like '25-Sep' or '29-Sep' into date object"""
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

    # Aaj ki Live Tareekh (IST: 25 Sep 2026)
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

            raw_name = clean_txt(cols[0].text)
            if not raw_name or len(raw_name) < 2 or "IPO NAME" in raw_name.upper():
                continue

            # Category
            is_sme = "SME" in raw_name.upper()
            category = "SME" if is_sme else "MAINBOARD"

            # Clean Name (Naam gayab hone se bachane ka safe tarika)
            name_clean = re.sub(r'\[email&#160;protected\]|\[email\s*protected\]', '', raw_name, flags=re.IGNORECASE)
            name_clean = re.sub(r'L@[\d\.\(\)\%\+\-]+', '', name_clean)
            name_clean = re.sub(r'\([+-]?\d+(?:\.\d+)?%\)', '', name_clean)
            name_clean = re.sub(r'(?:BSE\s+|NSE\s+)?SME[UOCLCT]*', '', name_clean, flags=re.IGNORECASE)
            name_clean = re.sub(r'IPO[UOCLCT]*$', '', name_clean, flags=re.IGNORECASE)
            clean_title = clean_txt(name_clean.strip(' -–@*🔥'))
            
            # Agar kisi wajah se naam zyada chhota ho gaya ho, toh raw se fallback karein
            if len(clean_title) < 2:
                clean_title = raw_name.split()[0]

            # Dates directly from Col 7 (Open) and Col 8 (Close)
            open_str = clean_txt(cols[7].text)
            close_str = clean_txt(cols[8].text)

            open_d = parse_date(open_str)
            close_d = parse_date(close_str)

            # Clean Date Range Display (Sirf tareekh, koi GMP nahi)
            if open_str and close_str and open_str != "--" and close_str != "--":
                display_date = f"{open_str} - {close_str}"
            elif open_str and open_str != "--":
                display_date = open_str
            else:
                display_date = "Live"

            # ---------------- STATUS LOGIC ----------------
            # 1. Closed: Jo aaj (25) se pehle hi close ho chuke hain
            if close_d and close_d < today:
                status = "CLOSED"
            # 2. Upcoming: Jo aaj ke baad shuru honge (jaise 28 Sep, 30 Sep ya aage)
            elif open_d and open_d > today:
                status = "UPCOMING"
            # 3. Open: Jo shuru ho chuke hain aur 29 tak chalne wale hain (Open <= today <= Close)
            elif (open_d and open_d <= today and (close_d is None or close_d >= today)) or (close_d and close_d >= today):
                status = "OPEN"
            else:
                # Agar tareekh na ho, toh InvestorGain ke tag se le
                raw_u = raw_name.upper()
                if raw_u.endswith("U"):
                    status = "UPCOMING"
                elif raw_u.endswith("C") or raw_u.endswith("L") or "LISTED" in raw_u:
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