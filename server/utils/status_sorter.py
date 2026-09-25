import re
from datetime import datetime, timezone, timedelta

MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}

def parse_date_flexible(val_str, default_year=2026):
    """तारीख जैसे '24-Sep', '29 Sep', '24-Sep-2026' को डेट ऑब्जेक्ट में बदलता है"""
    if not val_str or val_str.strip() in ["--", "", "Live"]:
        return None

    clean = val_str.strip().replace('/', '-').replace(' ', '-')
    parts = [p for p in clean.split('-') if p]

    if len(parts) >= 2:
        try:
            day = int(parts[0])
            mon_part = parts[1].upper()[:3]
            
            if mon_part in MONTH_MAP:
                month = MONTH_MAP[mon_part]
            elif parts[1].isdigit():
                month = int(parts[1])
            else:
                return None

            year = default_year
            if len(parts) >= 3:
                yr_num = int(parts[2])
                year = 2000 + yr_num if yr_num < 100 else yr_num

            return datetime(year, month, day).date()
        except Exception:
            return None
    return None

def sort_and_assign_status(ipo_list):
    """
    सख्त कैलेंडर नियम:
    - 24 Sep से 29 Sep वाला IPO आज 25 Sep को सीधा OPEN में रहेगा।
    - जो 25 Sep से पहले क्लोज हो चुका है, वह CLOSED में जाएगा।
    - जो 25 Sep के बाद शुरू होगा, सिर्फ वही UPCOMING में जाएगा।
    """
    ist = timezone(timedelta(hours=5, minutes=30))
    today = datetime.now(ist).date()

    for item in ipo_list:
        date_range = item.get("date_range", "")
        raw_name = item.get("name", "").upper()
        
        open_date = None
        close_date = None

        # तारीख अलग करें: जैसे "24 Sep - 29 Sep"
        if " - " in date_range:
            parts = date_range.split(" - ")
            open_date = parse_date_flexible(parts[0])
            close_date = parse_date_flexible(parts[1])
        elif date_range and date_range != "Live":
            close_date = parse_date_flexible(date_range)

        # 1. सबसे पहले चेक: क्या IPO पहले ही बंद हो चुका है?
        if close_date and close_date < today:
            item["status"] = "CLOSED"

        # 2. क्या IPO भविष्य में शुरू होगा? (आज के बाद)
        elif open_date and open_date > today:
            item["status"] = "UPCOMING"

        # 3. क्या IPO शुरू हो चुका है और आज या आगे तक चलेगा? (जैसे 24 से 29 Sep)
        elif open_date and open_date <= today and (close_date is None or close_date >= today):
            item["status"] = "OPEN"

        # 4. अगर सिर्फ क्लोज डेट है और वह आज या आगे की है
        elif close_date and close_date >= today:
            item["status"] = "OPEN"

        # 5. अगर तारीख न मिले, तो नाम के टैग से पहचानें
        else:
            if any(w in raw_name for w in ["LISTED", "CLOSED", "(L)"]):
                item["status"] = "CLOSED"
            elif any(w in raw_name for w in ["UPCOMING", "PRE-APPLY", "(U)"]):
                item["status"] = "UPCOMING"
            else:
                item["status"] = "OPEN"

    return ipo_list