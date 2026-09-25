import re

def clean_pure_date(date_str):
    """Date ke beech se GMP, %, aur faltu text hatakar sirf saaf date rakhta hai"""
    if not date_str or date_str == "Live" or date_str == "--":
        return date_str
    
    # GMP, %, ₹ aur numbers with % ko saaf karein
    cleaned = re.sub(r'₹?\s*[-+]?\d+(?:\.\d+)?\s*%', '', date_str)
    cleaned = re.sub(r'₹\s*[-+]?\d+(?:\.\d+)?', '', cleaned)
    cleaned = re.sub(r'\[.*?\]|\(.*?\)', '', cleaned)
    
    # Sirf Dates pakdein (jaise '23-Sep', '25 Sep')
    dates = re.findall(r'\b\d{1,2}(?:st|nd|rd|th)?[\s\-]*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*(?:[\s\-]*\d{2,4})?\b', cleaned, re.IGNORECASE)
    
    if len(dates) >= 2:
        return f"{dates[0]} - {dates[1]}"
    elif len(dates) == 1:
        return dates[0]
    
    return date_str.strip()

def sort_and_assign_status(ipo_list):
    """
    Sirf 3 Status:
    - O -> OPEN
    - U -> UPCOMING
    - C ya L -> CLOSED
    Aur Date Range ko bilkul saaf rakhna.
    """
    for item in ipo_list:
        raw_name = item.get("name", "").strip()
        name_upper = raw_name.upper()

        # 1. CLOSED (C ya Listed L)
        if name_upper.endswith("C") or name_upper.endswith("L") or "CLOSED" in name_upper or "LISTED" in name_upper:
            item["status"] = "CLOSED"

        # 2. UPCOMING (U)
        elif name_upper.endswith("U") or "UPCOMING" in name_upper:
            item["status"] = "UPCOMING"

        # 3. OPEN (O)
        elif name_upper.endswith("O") or "OPEN" in name_upper:
            item["status"] = "OPEN"

        else:
            item["status"] = "CLOSED"

        # Date Range se GMP ka kachra saaf karein (Sirf Date bachegi)
        item["date_range"] = clean_pure_date(item.get("date_range", ""))

        # App UI ke liye naam saaf karna
        clean_name = re.sub(r'\[email&#160;protected\]', '', raw_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'L@[\d\.\(\)\%\+\-]+', '', clean_name)
        clean_name = re.sub(r'(\(?(BSE\s+|NSE\s+)?SME\)?[UOCL]*|IPO[UOCL]*$)', '', clean_name, flags=re.IGNORECASE).strip()
        item["name"] = clean_name.strip(' -–@')

    return ipo_list