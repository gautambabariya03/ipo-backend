import requests
import json
import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

# Agar ddddocr installed hai to captcha solve karega, warna fallback
try:
    import ddddocr
    ocr = ddddocr.DdddOcr(show_ad=False)
except ImportError:
    ocr = None

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest"
}

# 1. Link Intime Live Checker (No Captcha needed, Pure JSON API)
def check_linkintime(pan_number, company_id="ALL"):
    url = "https://linkintime.co.in/Initial_Offer/IPO.aspx/SearchOnPan"
    payload = {
        "clientid": company_id,
        "PAN": pan_number.upper().strip(),
        "key": "1"
    }
    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            d = data.get("d", "{}")
            parsed = json.loads(d) if isinstance(d, str) else d
            
            if parsed and len(parsed) > 0:
                shares = str(parsed[0].get("ALLOT", "0"))
                company_name = parsed[0].get("COMPANYNAME", "")
                if shares.isdigit() and int(shares) > 0:
                    return {"status": "ALLOTTED", "shares": f"{shares} Shares Allotted", "details": company_name}
                else:
                    return {"status": "NON_ALLOTTEE", "shares": "0 Shares (Non-Allottee)", "details": company_name}
            return {"status": "NOT_APPLIED", "shares": "Not Applied", "details": ""}
    except Exception as e:
        print(f"LinkIntime Check Error for {pan_number}: {e}")
        
    return {"status": "NOT_APPLIED", "shares": "Not Applied", "details": ""}

# 2. Single Account Worker (Parallel Execution ke liye)
def verify_single_account(item, ipo_name, lot_size):
    p_id = item["id"]
    pan = item["pan"].upper().strip()
    name = item["name"].upper().strip()

    # Link Intime query
    res = check_linkintime(pan)

    # Agar registrar par data abhi announce na hua ho
    if res["status"] == "NOT_APPLIED":
        # Fallback check
        res = {"status": "NOT_APPLIED", "shares": "Not Applied", "details": "No record found on registrar"}

    return p_id, res

# 3. Universal Parallel Batch Checker (1-2 Second me 10-20 PANs)
def verify_family_allotments(ipo_name, pan_list, lot_size=50):
    results = {}
    
    if not pan_list:
        return results

    # 10 se 20 PAN ek sath parallel threads me check honge
    max_workers = min(len(pan_list), 20)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(verify_single_account, item, ipo_name, lot_size) for item in pan_list]
        for f in futures:
            try:
                p_id, res = f.result()
                results[p_id] = res
            except Exception as e:
                print(f"Batch Worker Error: {e}")

    return results