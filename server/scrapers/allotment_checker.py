import asyncio
import requests
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest"
}


# 1. Link Intime Registrar Live Checker (one real network call, no simulated data)
def check_linkintime(pan_number, company_id="ALL"):
    url = "https://linkintime.co.in/Initial_Offer/IPO.aspx/SearchOnPan"
    payload = {
        "clientid": company_id,
        "PAN": pan_number.upper().strip(),
        "key": "1"
    }
    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return {"status": "CHECK_FAILED", "shares": "Registrar busy, try again"}

        data = resp.json()
        d = data.get("d", "{}")
        parsed = json.loads(d) if isinstance(d, str) else d

        if parsed and len(parsed) > 0:
            shares_raw = parsed[0].get("ALLOT", "0")
            try:
                shares = int(shares_raw)
            except (TypeError, ValueError):
                shares = 0
            if shares > 0:
                return {"status": "ALLOTTED", "shares": f"{shares} Shares Allotted"}
            return {"status": "NON_ALLOTTEE", "shares": "0 Shares (Non-Allottee)"}

        return {"status": "NOT_APPLIED", "shares": "No record found for this PAN"}

    except Exception as e:
        print(f"LinkIntime Check Error for {pan_number}: {e}")
        return {"status": "CHECK_FAILED", "shares": "Could not reach registrar"}


# 2. Run one PAN's blocking `requests` call on a worker thread so many PANs
#    can be in flight to the registrar at the same time instead of one by one.
async def _check_one(item, semaphore):
    p_id = item["id"]
    pan = item["pan"].upper().strip()
    async with semaphore:
        res = await asyncio.to_thread(check_linkintime, pan)
    return p_id, res


# 3. Real, concurrent batch check for every saved PAN (12-20+ accounts fire
#    together, capped by max_concurrent so the registrar isn't hammered).
async def verify_family_allotments_async(ipo_name, pan_list, lot_size=50, max_concurrent=20):
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [_check_one(item, semaphore) for item in pan_list]
    completed = await asyncio.gather(*tasks)
    return {p_id: res for p_id, res in completed}


# Sync wrapper kept so anything importing the old sync name still works.
def verify_family_allotments(ipo_name, pan_list, lot_size=50):
    return asyncio.run(verify_family_allotments_async(ipo_name, pan_list, lot_size))