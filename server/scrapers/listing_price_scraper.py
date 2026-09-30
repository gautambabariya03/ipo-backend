"""
Listing Price + Current Price (LTP) scraper — for IPOs jo already list ho chuke
hain (CLOSED status wali IPOs jinki listing ho chuki hai).

Source: investorgain.com/report/ipo-gmp-performance-tracker (real, verified
working structure — checked live before building this).

Columns confirmed live: IPO | Symbol | Listing Dt | Size | Sub | GMP | Price |
Est Price | Listing Price | Listing Day Close | Closing Price (LTP)
"""
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def clean_txt(t):
    return re.sub(r"\s+", " ", t).strip() if t else ""


def normalize_name(name: str) -> str:
    """'Moneyview Ltd. (Mainboard)' / 'Moneyview SME' / 'Moneyview' -> 'moneyview'
    so GMP-list names and performance-tracker names can be matched reliably.
    Only the category tag is stripped — a real name segment like '(India)' in
    'Adroit Industries (India)' is kept so both sides normalize the same way."""
    n = re.sub(r"\((?:mainboard|sme|bse\s*sme|nse\s*sme)\)", "", name, flags=re.IGNORECASE)
    n = re.sub(r"\b(Ltd\.?|Limited|IPO|SME|BSE|NSE)\b", "", n, flags=re.IGNORECASE)
    n = re.sub(r"[^a-zA-Z0-9]", "", n).strip().lower()
    return n


def fetch_listing_performance(year=None):
    """Returns { normalized_name: {listing_price, current_price} } for the most
    recently listed IPOs (page 1 covers the last ~40 listings — more than
    enough for anything our app currently shows as CLOSED)."""
    year = year or datetime.now().year
    url = f"https://www.investorgain.com/report/ipo-gmp-performance-tracker/377/all/?year={year}"
    results = {}
    rows = []

    # investorgain kabhi-kabhi "Loading..." wala JS-shell bhej deta hai —
    # isliye yahan bhi retry karte hain
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
            print(f"Listing Price Scraper Error (attempt {attempt+1}): {e}")
            time.sleep(2)

    if not rows:
        print("Listing Price Scraper: all retries failed, returning empty")
        return results

    try:
        for row in rows:
            cols = row.find_all(["td", "th"])
            if len(cols) < 11:
                continue

            a_tag = cols[0].find("a")
            raw_name = clean_txt(a_tag.text) if a_tag else clean_txt(cols[0].text)
            if not raw_name or raw_name.upper() in ("IPO", "NAME"):
                continue

            listing_price = clean_txt(cols[8].text)
            current_price = clean_txt(cols[10].text)
            if not listing_price or listing_price == "--":
                continue

            key = normalize_name(raw_name)
            if key:
                results[key] = {
                    "listing_price": listing_price,
                    "current_price": current_price,
                }

        return results

    except Exception as e:
        print(f"Listing Price Scraper Parse Error: {e}")
        return results


if __name__ == "__main__":
    data = fetch_listing_performance()
    print(f"{len(data)} listed IPOs found")
    for k, v in list(data.items())[:5]:
        print(k, v)
