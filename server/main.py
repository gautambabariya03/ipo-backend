import sys
import os
import asyncio
import json
from typing import List, Optional
from datetime import datetime

# Server folder path add karein taaki module import fail na ho
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from scrapers.gmp_scraper import fetch_live_gmp
from scrapers.ipo_detail_scraper import fetch_ipo_detail
try:
    from scrapers.allotment_checker import verify_family_allotments_async
except ImportError:
    async def verify_family_allotments_async(ipo_name, accounts, lot_size, max_concurrent=20):
        return {}

app = FastAPI(title="IPO GMP Tracker API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Models -----------------
class AccountItem(BaseModel):
    id: str
    name: str
    pan: str

class AllotmentBatchRequest(BaseModel):
    ipo_name: str
    lot_size: int = 50
    accounts: List[AccountItem]

# ----------------- In-memory State & Cache -----------------
CACHED_IPOS = []
LAST_SYNC_TIME = None      # kab last successful scrape hua
LAST_SYNC_ERROR = None     # agar scrape fail hua toh uski wajah (debugging ke liye)
SYNC_MIN_INTERVAL_SEC = 60  # isse jaldi dobara scrape nahi karega (investorgain ko spam na ho)

# IPO detail page (subscription, lead manager, registrar) — sirf VIEW tap karne
# par scrape hota hai, aur 5 min tak cache rehta hai taaki baar-baar tap karne se
# choiceindia.com ko spam na ho.
DETAIL_CACHE = {}   # { ipo_id: {"data": {...}, "time": datetime} }
DETAIL_CACHE_TTL_SEC = 300

# Server restart hone par bhi purana data (khaaskar closed IPOs) yaad rahe, isliye
# disk pe bhi save karte hain. NOTE: Render free tier ka filesystem naya deploy
# hone par reset ho jaata hai — ye sirf simple restarts/sleep-wake ke beech bachata
# hai, ek naye deploy ke against guarantee nahi hai (uske liye real DB chahiye hoga).
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ipos_persistent.json")

def load_from_disk():
    global CACHED_IPOS
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                CACHED_IPOS = json.load(f)
                print(f"Loaded {len(CACHED_IPOS)} IPOs from disk cache ({DATA_FILE}).")
        except Exception as e:
            print(f"Disk load error (ignoring, starting fresh): {e}")

def save_to_disk():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(CACHED_IPOS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Disk save error: {e}")

# Notifications: naya IPO aane, GMP change hone, ya status change hone par
# events yahan store hote hain (backend khud generate karta hai — koi external
# scraping dependency nahi, isliye reliable hai). Latest 100 rakhte hain.
NOTIFICATIONS = []
NOTIF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notifications_persistent.json")
MAX_NOTIFICATIONS = 100

def load_notifications_from_disk():
    global NOTIFICATIONS
    if os.path.exists(NOTIF_FILE):
        try:
            with open(NOTIF_FILE, "r", encoding="utf-8") as f:
                NOTIFICATIONS = json.load(f)
        except Exception as e:
            print(f"Notif disk load error: {e}")

def save_notifications_to_disk():
    try:
        with open(NOTIF_FILE, "w", encoding="utf-8") as f:
            json.dump(NOTIFICATIONS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Notif disk save error: {e}")

def add_notification(ntype, message, ipo_id=None, ipo_name=None):
    global NOTIFICATIONS
    NOTIFICATIONS.insert(0, {
        "type": ntype,               # "new_ipo" | "gmp_change" | "status_change"
        "message": message,
        "ipo_id": ipo_id,
        "ipo_name": ipo_name,
        "time": datetime.now().isoformat(),
    })
    NOTIFICATIONS = NOTIFICATIONS[:MAX_NOTIFICATIONS]
    save_notifications_to_disk()

def detect_changes_and_notify(old_ipos, new_ipos):
    """Purane aur naye scrape ke beech compare karke notifications banata hai."""
    old_by_id = {x["id"]: x for x in old_ipos}
    for item in new_ipos:
        old = old_by_id.get(item["id"])
        if old is None:
            add_notification(
                "new_ipo",
                f"🆕 New IPO Added: {item['name']} ({item.get('category', '')})",
                item["id"], item["name"]
            )
            continue

        old_gmp = old.get("gmp")
        new_gmp = item.get("gmp")
        if old_gmp is not None and new_gmp is not None and old_gmp != new_gmp:
            arrow = "🚀" if new_gmp > old_gmp else "🔻"
            add_notification(
                "gmp_change",
                f"{arrow} {item['name']} GMP: ₹{old_gmp} → ₹{new_gmp}",
                item["id"], item["name"]
            )

        if old.get("status") != item.get("status"):
            add_notification(
                "status_change",
                f"📢 {item['name']} is now {item.get('status')}",
                item["id"], item["name"]
            )

async def sync_data_safe():
    """Network fetch ko non-blocking thread me chalata hai aur naye IPOs auto-load karta hai.
    Purane (closed/listed) IPOs jo investorgain ki live page se hat jaate hain, unhe cache se
    hataya nahi jaata — sirf naye/updated IPOs merge kiye jaate hain, taaki allotment check ke
    liye purane closed IPOs bhi list me bane rahein."""
    global CACHED_IPOS, LAST_SYNC_TIME, LAST_SYNC_ERROR
    try:
        data = await asyncio.to_thread(fetch_live_gmp)
        if data:
            existing_by_id = {item["id"]: item for item in CACHED_IPOS}
            previous_snapshot = list(CACHED_IPOS)  # notification diff ke liye purana state
            for item in data:
                existing_by_id[item["id"]] = item  # naya data purane ko overwrite karta hai (same id)
            CACHED_IPOS = list(existing_by_id.values())
            if previous_snapshot:  # pehli hi sync par notifications spam na ho
                detect_changes_and_notify(previous_snapshot, data)
            LAST_SYNC_TIME = datetime.now()
            LAST_SYNC_ERROR = None
            save_to_disk()
            print(f"[{LAST_SYNC_TIME.strftime('%H:%M:%S')}] Live Sync Complete: {len(data)} fetched, {len(CACHED_IPOS)} total cached.")
        else:
            LAST_SYNC_ERROR = "Scraper returned 0 IPOs (investorgain page structure ho sakta hai badal gaya ho, ya block ho gaya ho)"
            print(f"Background Sync Warning: {LAST_SYNC_ERROR}")
    except Exception as e:
        LAST_SYNC_ERROR = str(e)
        print(f"Background Sync Error: {e}")

async def auto_updater_task():
    """Har 10 minute me background me bina app reload kiye live data auto-refresh karega
    (yeh app band/khula dono situation me chalta hai jab tak server process zinda hai)."""
    while True:
        await asyncio.sleep(600)
        print("Syncing live GMP data automatically in background...")
        await sync_data_safe()

@app.on_event("startup")
async def on_startup():
    print("Initial server startup: Loading live IPO dataset...")
    load_from_disk()
    load_notifications_from_disk()
    await sync_data_safe()
    asyncio.create_task(auto_updater_task())

# ----------------- Endpoints -----------------
@app.get("/")
def root():
    return {
        "message": "IPO Live Backend is Running",
        "total_ipos": len(CACHED_IPOS),
        "last_sync_time": LAST_SYNC_TIME.strftime("%d %b, %I:%M:%S %p") if LAST_SYNC_TIME else None,
        "last_sync_error": LAST_SYNC_ERROR,
    }

@app.get("/api/ipos/live")
async def get_live_ipos(force_refresh: bool = Query(False, description="Set True for manual pull-to-refresh")):
    global CACHED_IPOS
    is_stale = (
        not CACHED_IPOS
        or LAST_SYNC_TIME is None
        or (datetime.now() - LAST_SYNC_TIME).total_seconds() > SYNC_MIN_INTERVAL_SEC
    )
    if force_refresh or is_stale:
        await sync_data_safe()
    return CACHED_IPOS

@app.get("/api/ipos")
async def get_ipos_alias(force_refresh: bool = Query(False)):
    return await get_live_ipos(force_refresh=force_refresh)

@app.post("/api/allotment/check-batch")
async def check_allotment_batch_api(payload: AllotmentBatchRequest):
    acc_list = [{"id": a.id, "name": a.name, "pan": a.pan} for a in payload.accounts]
    res = await verify_family_allotments_async(payload.ipo_name, acc_list, payload.lot_size)
    return {"success": True, "results": res}

@app.get("/api/notifications")
def get_notifications(limit: int = Query(50, ge=1, le=100)):
    return NOTIFICATIONS[:limit]
async def get_ipo_detail(ipo_id: str):
    """Subscription breakdown, lead managers, registrar/contact info for one IPO.
    Lazy-fetched (only when the user opens VIEW), cached for 5 minutes."""
    cached = DETAIL_CACHE.get(ipo_id)
    if cached and (datetime.now() - cached["time"]).total_seconds() < DETAIL_CACHE_TTL_SEC:
        return cached["data"]

    ipo = next((x for x in CACHED_IPOS if x["id"] == ipo_id), None)
    if not ipo:
        return {"found": False, "error": "IPO not found in current list"}

    detail = await asyncio.to_thread(fetch_ipo_detail, ipo["name"])
    DETAIL_CACHE[ipo_id] = {"data": detail, "time": datetime.now()}
    return detail