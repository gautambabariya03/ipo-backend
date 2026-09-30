"""
Live category-wise subscription scraper — QIB / HNI (NII) / Retail (RII) / Total.

Source: investorgain.com/report/ipo-subscription-live/333/all/ (real, verified
working structure — checked live before building this; covers Mainboard + SME).

Columns confirmed live:
Name | Total | QIB | SHNI | BHNI | NII | RII | Anchor | IPO Size | IPO Price | P/E | Closing Date
"""
import requests
from bs4 import BeautifulSoup
import re
import time
from scrapers.listing_price_scraper import normalize_name

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def clean_txt(t):
    return re.sub(r"\s+", " ", t).strip() if t else ""


def _parse_x(raw):
    t = clean_txt(raw)
    if not t or t == "--":
        return None
    t = t.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def fetch_subscription_data():
    """Returns { normalized_name: {qib, hni, retail, total} } for every IPO
    currently carrying live subscription data (open, or closed-but-recent)."""
    url = "https://www.investorgain.com/report/ipo-subscription-live/333/all/"
    results = {}
    rows = []

    # investorgain kabhi-kabhi "Loading..." wala JS-shell bhej deta hai (jaisa
    # main GMP page mein hota hai) — isliye yahan bhi retry karte hain
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                time.sleep(2)
                continue

            if "Loading..." in resp.text and "<table" not in resp.text.lower():
                time.sleep(2)
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table")
            found_rows = table.find_all("tr") if table else soup.find_all("tr")
            if len(found_rows) < 2:
                time.sleep(2)
                continue

            rows = found_rows
            break

        except Exception as e:
            print(f"Subscription Scraper Error (attempt {attempt+1}): {e}")
            time.sleep(2)

    if not rows:
        print("Subscription Scraper: all retries failed, returning empty")
        return results

    try:
        for row in rows:
            cols = row.find_all(["td", "th"])
            if len(cols) < 12:
                continue

            a_tag = cols[0].find("a")
            raw_name = clean_txt(a_tag.text) if a_tag else clean_txt(cols[0].text)
            if not raw_name or raw_name.upper() == "NAME":
                continue

            total = _parse_x(cols[1].text)
            qib = _parse_x(cols[2].text)
            nii = _parse_x(cols[5].text)
            rii = _parse_x(cols[6].text)
            if total is None:
                continue

            key = normalize_name(raw_name)
            if key:
                results[key] = {
                    "qib": f"{qib}x" if qib is not None else "N/A",
                    "hni": f"{nii}x" if nii is not None else "N/A",
                    "retail": f"{rii}x" if rii is not None else "N/A",
                    "total": f"{total}x",
                }

        return results

    except Exception as e:
        print(f"Subscription Scraper Parse Error: {e}")
        return results


if __name__ == "__main__":
    data = fetch_subscription_data()
    print(f"{len(data)} IPOs with live subscription data")
    for k, v in list(data.items())[:5]:
        print(k, v)
