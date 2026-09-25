from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import re
from datetime import datetime, timezone, timedelta
from scrapers.gmp_scraper import fetch_live_gmp

app = FastAPI(title="IPO GMP Tracker API", version="2.0.0")

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

def parse_date(d_str, default_year=2026):
    if not d_str or d_str == "--":
        return None
    clean_s = re.sub(r'[^a-zA-Z0-9]', ' ', d_str).strip()
    parts = clean_s.split()
    if len(parts) >= 2:
        try:
            day = int(parts[0])
            mon = MONTH_MAP.get(parts[1][:3].upper())
            year = int(parts[2]) if len(parts) >= 3 and len(parts[2]) == 4 else default_year
            if mon:
                return datetime(year, mon, day).date()
        except Exception:
            pass
    return None

def process_and_sort_ipos(ipo_list):
    ist = timezone(timedelta(hours=5, minutes=30))
    today = datetime.now(ist).date()

    for item in ipo_list:
        open_dt = parse_date(item.get("open_date"))
        close_dt = parse_date(item.get("close_date"))
        listing_dt = parse_date(item.get("listing_date"))
        raw_name = item.get("name", "").upper()

        # 1. Listed IPOs
        if (listing_dt and listing_dt <= today) or "LISTED" in raw_name:
            item["status"] = "CLOSED"
            item["gmp"] = 0.0
            item["gmp_percentage"] = 0.0
            item["retail_profit"] = 0.0
            item["hni_profit"] = 0.0
            continue

        # 2. Closed Date passed
        if close_dt and close_dt < today:
            item["status"] = "CLOSED"
            continue

        # 3. Upcoming Date
        if open_dt and open_dt > today:
            item["status"] = "UPCOMING"
            continue

        # 4. Currently Active
        if open_dt and close_dt:
            if open_dt <= today <= close_dt:
                item["status"] = "OPEN"
            else:
                item["status"] = "CLOSED"
        else:
            item["status"] = "OPEN"

    # EXACT SORTING RULE:
    # 1. Status priority: OPEN first, then UPCOMING, then CLOSED
    # 2. GMP priority: Highest GMP (₹) on top (even if date is 26th vs 25th)
    status_order = {"OPEN": 1, "UPCOMING": 2, "CLOSED": 3}
    
    ipo_list.sort(
        key=lambda x: (
            status_order.get(x.get("status", "CLOSED"), 4),
            -float(x.get("gmp", 0.0)),
            -float(x.get("gmp_percentage", 0.0))
        )
    )

    return ipo_list

@app.get("/")
def home():
    return {"status": "online", "message": "Live IPO API Ready"}

@app.get("/api/ipos/live")
def get_live_ipos(force_refresh: bool = False):
    raw_data = fetch_live_gmp()
    return process_and_sort_ipos(raw_data)

@app.get("/api/ipos/{status}")
def get_ipos_by_status(status: str):
    raw_data = fetch_live_gmp()
    processed = process_and_sort_ipos(raw_data)
    status_upper = status.upper()
    return [x for x in processed if x.get("status") == status_upper]