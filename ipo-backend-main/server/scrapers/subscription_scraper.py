"""
Live category-wise subscription scraper — QIB / HNI(NII) / Retail / Total
(+ Employee / Shareholder quota, sirf un IPOs ke liye jinke source me ye
column ho).

Source: investorgain.com/report/ipo-subscription-live/333/all/
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from scrapers.listing_price_scraper import normalize_name

URL = "https://www.investorgain.com/report/ipo-subscription-live/333/all/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Header na mile toh investorgain ka confirmed column order:
# Name | Total | QIB | SHNI | BHNI | NII | RII | Anchor | ...
DEFAULT_MAP = {"total": 1, "qib": 2, "nii": 5, "rii": 6}


def clean_txt(t):
    return re.sub(r"\s+", " ", t).strip() if t else ""


def _parse_x(raw):
    """'4.0x', '52.76', '21.3 19-Oct 11:30' jaise text se subscription number
    nikaalta hai. Pehle 'number + x' dhoondta hai, warna pehla number."""
    t = clean_txt(raw)
    if not t or t in ("--", "-", "NA", "N/A"):
        return None
    m = re.search(r"(\d[\d,]*\.?\d*)\s*[xX]", t) or re.search(r"(\d[\d,]*\.?\d*)", t)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _cell_value(cell):
    """Cell ke andar bold/strong value ko priority (investorgain Total cell me
    value bold hoti hai aur uske saath updated-time bhi likha hota hai)."""
    for tag in cell.find_all(["b", "strong"]):
        v = _parse_x(tag.get_text(" "))
        if v is not None:
            return v
    return _parse_x(cell.get_text(" "))


def _classify_header(text):
    t = clean_txt(text).lower()
    if not t:
        return None
    if "total" in t:
        return "total"
    if "qib" in t or "institutional" in t:
        return "qib"
    if "shni" in t or "snii" in t or "s-nii" in t or "bhni" in t or "bnii" in t or "b-nii" in t:
        return None  # sub-categories; NII (combined) hi dikhate hain
    if "nii" in t or t == "hni" or "non-inst" in t or "non inst" in t:
        return "nii"
    if "rii" in t or "retail" in t:
        return "rii"
    if "employee" in t or t.startswith("emp"):
        return "emp"
    if "shareholder" in t or "share holder" in t or t in ("sh", "sh quota"):
        return "sh"
    return None


def _build_header_map(rows):
    for row in rows[:3]:
        cells = row.find_all(["th", "td"])
        hmap = {}
        for idx, c in enumerate(cells):
            key = _classify_header(c.get_text(" "))
            if key and key not in hmap:
                hmap[key] = idx
        if len(hmap) >= 2:
            return hmap
    return dict(DEFAULT_MAP)


def _fmt(v):
    return f"{v:g}x" if v is not None else "N/A"


def fetch_subscription_data():
    """Returns { normalized_name: {qib, hni, retail, total[, emp][, sh]} }.
    emp/sh keys sirf tab aati hain jab us IPO ke liye value mili ho."""
    results = {}
    rows = []

    # investorgain kabhi-kabhi khaali shell bhejta hai — 3 baar try
    for attempt in range(3):
        try:
            resp = requests.get(URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                time.sleep(2)
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table")
            found = table.find_all("tr") if table else []
            if len(found) < 2:
                time.sleep(2)
                continue
            rows = found
            break
        except Exception as e:
            print(f"Subscription Scraper Error (attempt {attempt + 1}): {e}")
            time.sleep(2)

    if not rows:
        print("Subscription Scraper: no table data after retries")
        return results

    try:
        hmap = _build_header_map(rows)

        for row in rows:
            cols = row.find_all(["td", "th"])
            if len(cols) < 3:
                continue

            a_tag = cols[0].find("a")
            raw_name = clean_txt(a_tag.text) if a_tag else clean_txt(cols[0].text)
            if not raw_name or raw_name.upper() == "NAME":
                continue

            def val(key):
                idx = hmap.get(key)
                if idx is None or idx >= len(cols):
                    return None
                return _cell_value(cols[idx])

            total, qib, nii, rii = val("total"), val("qib"), val("nii"), val("rii")
            emp, sh = val("emp"), val("sh")

            if total is None and qib is None and nii is None and rii is None:
                continue

            key = normalize_name(raw_name)
            if not key:
                continue

            entry = {
                "qib": _fmt(qib),
                "hni": _fmt(nii),
                "retail": _fmt(rii),
                "total": _fmt(total),
            }
            if emp is not None:
                entry["emp"] = _fmt(emp)
            if sh is not None:
                entry["sh"] = _fmt(sh)
            results[key] = entry

        return results

    except Exception as e:
        print(f"Subscription Scraper Parse Error: {e}")
        return results


def fetch_live_subscription(ipo_url_name=None):
    # Backward compatibility wrapper
    return {}


if __name__ == "__main__":
    data = fetch_subscription_data()
    print(f"{len(data)} IPOs with subscription data")
    for k, v in list(data.items())[:5]:
        print(k, v)
