import re

def sort_and_assign_status(ipo_list):
    """
    InvestorGain ke official status tags:
    - O / CT -> OPEN
    - U      -> UPCOMING
    - C / L  -> CLOSED
    """
    for item in ipo_list:
        raw_name = item.get("name", "").strip()

        # 1. Listed ya Closed
        if re.search(r'(L@|LISTED|\bL\b|\bC\b|CLOSED)', raw_name, re.IGNORECASE) or raw_name.endswith('C') or raw_name.endswith('L'):
            item["status"] = "CLOSED"

        # 2. Upcoming
        elif re.search(r'(\bU\b|UPCOMING|PRE-APPLY)', raw_name, re.IGNORECASE) or raw_name.endswith('U'):
            item["status"] = "UPCOMING"

        # 3. Open ya Closing Today
        elif re.search(r'(\bCT\b|\bO\b|OPEN|CLOSING TODAY)', raw_name, re.IGNORECASE) or raw_name.endswith('O') or raw_name.endswith('CT'):
            item["status"] = "OPEN"

        else:
            item["status"] = "OPEN"

        # Clean display name for Flutter App UI
        clean_name = re.sub(r'\[email&#160;protected\]', '', raw_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'L@[\d\.\(\)\%\+\-]+', '', clean_name)
        clean_name = re.sub(r'(\(?(BSE\s+|NSE\s+)?SME\)?[UOCLCT]*|IPO[UOCLCT]*$)', '', clean_name, flags=re.IGNORECASE).strip()
        item["name"] = clean_name.strip(' -–@')

    return ipo_list