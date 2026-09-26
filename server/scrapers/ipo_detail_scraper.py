"""
Per-IPO detail scraper — subscription breakdown, lead managers, registrar &
company contact info. Source: choiceindia.com/ipo/<slug>-ipo (real, verified
working page structure — checked live before building this).

Ye data GMP list se alag hai, isliye alag se sirf tab fetch hota hai jab user
"VIEW" par tap karta hai (poore IPO list ke liye baar-baar scrape nahi hota).
"""
import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def name_to_slug(ipo_name: str) -> str:
    """'Moneyview Ltd. (Mainboard)' -> 'moneyview-ipo'"""
    n = re.sub(r"\(.*?\)", "", ipo_name)  # drop "(Mainboard)" / "(SME)"
    n = re.sub(r"\b(Ltd\.?|Limited|IPO)\b", "", n, flags=re.IGNORECASE)
    n = re.sub(r"[^a-zA-Z0-9\s-]", "", n).strip().lower()
    n = re.sub(r"\s+", "-", n)
    n = re.sub(r"-+", "-", n).strip("-")
    return f"{n}-ipo"


def _table_after_heading(soup, heading_keywords):
    """Finds a heading (h1-h4) whose text contains any of heading_keywords,
    then returns the first <table> that appears after it in the document."""
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        text = tag.get_text(strip=True).lower()
        if any(k.lower() in text for k in heading_keywords):
            table = tag.find_next("table")
            if table:
                return table
    return None


def _clean(txt):
    return re.sub(r"\s+", " ", txt or "").strip()


def _parse_table(table):
    """Generic table -> list of row dicts using header cells; falls back to
    list of row-cell-lists if there's no clean header row."""
    rows = table.find_all("tr")
    if not rows:
        return []
    data = []
    for row in rows:
        cells = [_clean(c.get_text()) for c in row.find_all(["td", "th"])]
        if any(cells):
            data.append(cells)
    return data


def fetch_ipo_detail(ipo_name: str):
    slug = name_to_slug(ipo_name)
    url = f"https://choiceindia.com/ipo/{slug}"

    result = {
        "source": "choiceindia.com",
        "url": url,
        "subscription": [],       # [{category, percentage, amount_raised}]
        "lead_managers": [],
        "registrar": {"name": None, "phone": None, "email": None, "website": None},
        "company_contact": {"address": None, "phone": None, "email": None, "website": None},
        "found": False,
        "error": None,
    }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            result["error"] = f"Page returned status {resp.status_code}"
            return result

        soup = BeautifulSoup(resp.text, "html.parser")

        # ---- Subscription Breakdown ----
        sub_table = _table_after_heading(soup, ["subscription breakdown"])
        if sub_table:
            rows = _parse_table(sub_table)
            for r in rows[1:]:  # skip header row
                if len(r) >= 3:
                    result["subscription"].append({
                        "category": r[0],
                        "percentage": r[1],
                        "amount_raised": r[2],
                    })

        # ---- Lead Manager(s) ----
        lm_table = _table_after_heading(soup, ["lead manager"])
        if lm_table:
            rows = _parse_table(lm_table)
            for r in rows[1:]:
                if r:
                    names = [n.strip() for n in re.split(r"\||,", r[0]) if n.strip()]
                    result["lead_managers"].extend(names)

        # ---- Registrar Details ----
        for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
            if "registrar details" in tag.get_text(strip=True).lower():
                block = tag.find_next(["div", "section"])
                block_text = _clean(block.get_text(" ")) if block else ""
                name_m = re.search(r"Registrar Name\s*(.*?)\s*(Phone|Email|Website|$)", block_text, re.IGNORECASE)
                phone_m = re.search(r"\+?\d[\d\s-]{8,15}\d", block_text)
                email_m = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", block_text)
                url_m = re.search(r"https?://[^\s]+", block_text)
                if name_m:
                    result["registrar"]["name"] = name_m.group(1).strip()
                if phone_m:
                    result["registrar"]["phone"] = phone_m.group(0).strip()
                if email_m:
                    result["registrar"]["email"] = email_m.group(0).strip()
                if url_m:
                    result["registrar"]["website"] = url_m.group(0).strip()
                break

        # ---- Company Contact Details ----
        for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
            if "contact details" in tag.get_text(strip=True).lower() or "contact & registrar" in tag.get_text(strip=True).lower():
                block = tag.find_next(["div", "section"])
                block_text = _clean(block.get_text(" ")) if block else ""
                phone_m = re.search(r"\+?\d[\d\s-]{8,15}\d", block_text)
                email_m = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", block_text)
                result["company_contact"]["phone"] = phone_m.group(0).strip() if phone_m else None
                result["company_contact"]["email"] = email_m.group(0).strip() if email_m else None
                break

        result["found"] = bool(result["subscription"] or result["lead_managers"])
        if not result["found"]:
            result["error"] = "Detail page structure not recognized (page may not exist yet for this IPO, or layout changed)"

        return result

    except Exception as e:
        result["error"] = str(e)
        return result


if __name__ == "__main__":
    import json
    print(json.dumps(fetch_ipo_detail("Moneyview Ltd. (Mainboard)"), indent=2))
