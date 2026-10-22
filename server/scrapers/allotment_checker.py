"""
Allotment check — registrar ki site par OCR se automatic (auto_allotment.py).

Purana LinkIntime wala direct-API check hata diya gaya: uska domain
(linkintime.co.in) ab 'connection refused' deta hai, aur har IPO ke liye alag
company-ID + CAPTCHA chahiye hota hai.
"""
import asyncio

try:
    from scrapers.auto_allotment import check_pans_auto
    AUTO_ALLOTMENT_AVAILABLE = True
except ImportError:
    AUTO_ALLOTMENT_AVAILABLE = False

# Ek waqt par sirf ek browser-run (har run Chromium kholta hai, memory bhaari hai)
_BROWSER_LOCK = asyncio.Lock()


def _to_app_result(r):
    status = r.get("status")
    if status in ("ALLOTTED", "NON_ALLOTTEE", "NOT_APPLIED"):
        return {"status": status, "shares": r.get("message", "")}
    # AUTO_FAILED -> honest "verify nahi hua" (kabhi galat result nahi)
    return {
        "status": "UNVERIFIED",
        "shares": r.get("message") or "Auto-check nahi ho paya — registrar site se check karo",
        "debug_step": r.get("debug_step"),
    }


async def verify_family_allotments_async(ipo_name, pan_list, lot_size=50, max_concurrent=1, registrar_url=None):
    if not (AUTO_ALLOTMENT_AVAILABLE and registrar_url):
        return {
            item["id"]: {
                "status": "UNVERIFIED",
                "shares": "Registrar link abhi available nahi — registrar site se check karo",
            }
            for item in pan_list
        }

    async with _BROWSER_LOCK:
        raw = await asyncio.to_thread(check_pans_auto, pan_list, ipo_name, registrar_url)

    for pid, r in raw.items():
        if r.get("status") == "AUTO_FAILED":
            print(f"Auto-allotment UNVERIFIED for {pid} at '{r.get('debug_step')}': {r.get('message')}")
    return {pid: _to_app_result(r) for pid, r in raw.items()}


# Sync wrapper (purane imports ke liye)
def verify_family_allotments(ipo_name, pan_list, lot_size=50, registrar_url=None):
    return asyncio.run(verify_family_allotments_async(ipo_name, pan_list, lot_size, registrar_url=registrar_url))
