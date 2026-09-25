import re
from datetime import datetime, timezone, timedelta

MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}

def parse_ipo_date(date_str, default_year=2026):
    """Parses date like '24-Sep', '24 Sep', '24-Sep-2026' into a comparable datetime object."""
    if not date_str or date_str == "--":
        return None
    
    clean_s = re.sub(r'[^a-zA-Z0-9]', ' ', date_str).strip()
    parts = clean_s.split()
    
    if len(parts) >= 2:
        try:
            day = int(parts[0])
            mon_txt = parts[1][:3].upper()
            month = MONTH_MAP.get(mon_txt)
            year = int(parts[2]) if len(parts) >= 3 and len(parts[2]) == 4 else default_year
            if month:
                return datetime(year, month, day).date()
        except Exception:
            pass
    return None

def sort_and_assign_status(ipo_list):
    """Sorts IPOs strictly into OPEN, UPCOMING, and CLOSED based on today's live calendar date."""
    ist = timezone(timedelta(hours=5, minutes=30))
    today = datetime.now(ist).date()

    for item in ipo_list:
        date_range = item.get("date_range", "")
        raw_status = item.get("status", "OPEN")
        
        # Check if already tagged as listed/closed by explicit tags
        if raw_status == "CLOSED" or "LISTED" in date_range.upper():
            item["status"] = "CLOSED"
            continue

        open_date = None
        close_date = None

        # Parse date_range like "24 Sep - 28 Sep"
        if " - " in date_range:
            parts = date_range.split(" - ")
            open_date = parse_ipo_date(parts[0])
            close_date = parse_ipo_date(parts[1])
        elif date_range and date_range != "Live":
            close_date = parse_ipo_date(date_range)

        # STRICT DATE RULES:
        if close_date:
            if close_date < today:
                item["status"] = "CLOSED"
            elif open_date and open_date > today:
                item["status"] = "UPCOMING"
            else:
                item["status"] = "OPEN"
        elif open_date:
            if open_date > today:
                item["status"] = "UPCOMING"
            else:
                item["status"] = "OPEN"
        else:
            # Fallback if no dates exist
            item["status"] = raw_status

    return ipo_list