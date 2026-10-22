import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.chittorgarh.com/",
}

def fetch_chittorgarh_gmp():
    url = "https://www.chittorgarh.com/report/ipo-grey-market-premium-gmp/82/"
    session = requests.Session()
    session.headers.update(HEADERS)
    
    try:
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            print(f"Status Code: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        
        # Chittorgarh uses table with class 'table' or 'table-striped'
        table = soup.find("table", {"class": lambda c: c and "table" in c})
        if not table:
            # Fallback to any table present in the main container
            tables = soup.find_all("table")
            for t in tables:
                if "GMP" in t.text or "Price" in t.text:
                    table = t
                    break

        if not table:
            print("Chittorgarh data table still not found, checking raw length:", len(response.text))
            return []

        ipo_list = []
        rows = table.find_all("tr")
        if not rows:
            return []

        # Find column indexes dynamically
        header_row = rows[0].find_all(["th", "td"])
        headers = [h.text.strip().lower() for h in header_row]

        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) >= 5:
                name_tag = cols[0].find("a")
                raw_name = name_tag.text.strip() if name_tag else cols[0].text.strip()

                if not raw_name or "ipo" not in raw_name.lower() and len(raw_name) < 3:
                    continue

                is_sme = bool(re.search(r"\bSME\b", raw_name, re.IGNORECASE))
                clean_name = re.sub(r"\s*\(?(BSE\s+|NSE\s+)?SME\)?", "", raw_name, flags=re.IGNORECASE).strip()
                category = "SME" if is_sme else "MAINBOARD"

                price_text = cols[1].text.strip()
                gmp_text = cols[2].text.strip()
                est_listing = cols[3].text.strip()
                dates_text = cols[5].text.strip() if len(cols) > 5 else cols[-1].text.strip()

                clean_gmp = re.sub(r"[^\d.-]", "", gmp_text)
                gmp_val = float(clean_gmp) if clean_gmp else 0.0

                gain_match = re.search(r"([\d.]+)%", est_listing)
                gain_pct = float(gain_match.group(1)) if gain_match else 0.0

                lot_size = 1200 if is_sme else 45
                retail_profit = round(gmp_val * lot_size, 2)
                hni_profit = round(retail_profit * 14, 2)

                ipo_list.append({
                    "id": re.sub(r"[^a-zA-Z0-9]", "-", clean_name.lower())[:30],
                    "name": clean_name,
                    "category": category,
                    "date_range": dates_text if dates_text else "TBA",
                    "price": f"₹{price_text}" if not price_text.startswith("₹") else price_text,
                    "lot_size": lot_size,
                    "issue_size": "TBA",
                    "gmp": gmp_val,
                    "gmp_percentage": gain_pct,
                    "last_heard": "Live (Chittorgarh)",
                    "allotment_date": "TBA",
                    "listing_date": "TBA",
                    "retail_profit": retail_profit,
                    "hni_profit": hni_profit,
                    "status": "OPEN"
                })

        return ipo_list

    except Exception as e:
        print(f"Chittorgarh Scraper Error: {e}")
        return []

if __name__ == "__main__":
    print("Fetching live data from Chittorgarh...")
    data = fetch_chittorgarh_gmp()
    print(f"Successfully scraped: {len(data)} IPOs\n")
    if data:
        print("Sample IPO record:")
        for k, v in data[0].items():
            print(f"  {k}: {v}")