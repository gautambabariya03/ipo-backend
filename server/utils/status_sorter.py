import re
from datetime import datetime, timezone, timedelta

MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}

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

def sort_and_assign_status(ipo_list):
    ist = timezone(timedelta(hours=5, minutes=30))
    today = datetime.now(ist).date()

    for item in ipo_list:
        open_d = parse_date(item.get("open_raw", ""))
        close_d = parse_date(item.get("close_raw", ""))
        raw_cell = item.get("raw_tag", "").upper()

        # 1. Closed: जो आज से पहले बंद हो चुके हैं
        if close_d and close_d < today:
            item["status"] = "CLOSED"
        # 2. Upcoming: जो आज के बाद शुरू होंगे
        elif open_d and open_d > today:
            item["status"] = "UPCOMING"
        # 3. Open: जो आज चल रहे हैं (24-29, 25-29 आदि)
        elif (open_d and open_d <= today and (close_d is None or close_d >= today)) or (close_d and close_d >= today):
            item["status"] = "OPEN"
        else:
            if raw_cell.endswith("U") or "UPCOMING" in raw_cell:
                item["status"] = "UPCOMING"
            elif raw_cell.endswith("C") or raw_cell.endswith("L") or "LISTED" in raw_cell or "CLOSED" in raw_cell:
                item["status"] = "CLOSED"
            else:
                item["status"] = "OPEN"

    return ipo_list