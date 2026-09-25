import sys
import os
import asyncio
import time
import json
import json
from typing import List, Optional
from datetime import datetime

# Server folder path add karein taaki module import fail na ho
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from scrapers.gmp_scraper import fetch_live_gmp
try:
    from scrapers.allotment_checker import verify_family_allotments
except ImportError:
    def verify_family_allotments(ipo_name, accounts, lot_size):
        return []

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
# ----------------- Persistent Storage -----------------
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ipos_persistent.json")

def load_from_disk():
    global CACHED_IPOS
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                CACHED_IPOS = json.load(f)
                print(f"Loaded {len(CACHED_IPOS)} IPOs from persistent storage.")
        except Exception as e:
            print(f"Disk load error: {e}")
            # ----------------- Persistent Storage & Rate-Limited Cache -----------------
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ipos_persistent.json")
LAST_SCRAPE_TIME = 0
LAST_SYNC_STATUS = {"status": "Never Synced", "time": "", "error": None}
SCRAPE_TTL_SECONDS = 60  # Minimum 60 seconds gap between live scrapes

def load_from_disk():
    global CACHED_IPOS
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                CACHED_IPOS = json.load(f)
                print(f"Loaded {len(CACHED_IPOS)} IPOs from persistent storage.")
        except Exception as e:
            print(f"Disk load error: {e}")
            CACHED_IPOS = []

def save_to_disk():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(CACHED_IPOS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Disk save error: {e}")

def merge_scraped_data(new_items):
    global CACHED_IPOS
    existing_map = {item["id"]: item for item in CACHED_IPOS}
    for item in new_items:
        existing_map[item["id"]] = item
    CACHED_IPOS = list(existing_map.values())
    save_to_disk()

CACHED_IPOS = []

def save_to_disk():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(CACHED_IPOS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Disk save error: {e}")

def merge_scraped_data(new_items):
    global CACHED_IPOS
    existing_map = {item["id"]: item for item in CACHED_IPOS}
    for item in new_items:
        existing_map[item["id"]] = item
    CACHED_IPOS = list(existing_map.values())
    save_to_disk()

# ----------------- Persistent Storage & Rate-Limited Cache -----------------
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ipos_persistent.json")
LAST_SCRAPE_TIME = 0
LAST_SYNC_STATUS = {"status": "Never Synced", "time": "", "error": None}
SCRAPE_TTL_SECONDS = 60  # Minimum 60 seconds gap between live scrapes

def load_from_disk():
    global CACHED_IPOS
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                CACHED_IPOS = json.load(f)
                print(f"Loaded {len(CACHED_IPOS)} IPOs from persistent storage.")
        except Exception as e:
            print(f"Disk load error: {e}")
            CACHED_IPOS = []

def save_to_disk():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(CACHED_IPOS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Disk save error: {e}")

def merge_scraped_data(new_items):
    global CACHED_IPOS
    existing_map = {item["id"]: item for item in CACHED_IPOS}
    for item in new_items:
        existing_map[item["id"]] = item
    CACHED_IPOS = list(existing_map.values())
    save_to_disk()

CACHED_IPOS = []

async def sync_data_safe():
    """Network fetch ko non-blocking thread me chalata hai aur naye IPOs auto-load karta hai."""
    global CACHED_IPOS
    try:
        data = await asyncio.to_thread(fetch_live_gmp)
        if data:
            merge_scraped_data(data)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Live Sync Complete: {len(CACHED_IPOS)} IPOs cached successfully.")
    except Exception as e:
        print(f"Background Sync Error: {e}")

async def auto_updater_task():
    """Har 10 minute me background me bina app reload kiye live data auto-refresh karega."""
    while True:
        await asyncio.sleep(600)
        print("Syncing live GMP data automatically in background...")
        await sync_data_safe()

@app.on_event("startup")
async def on_startup():
    load_from_disk()
    print("Initial server startup: Loading live IPO dataset...")
    await sync_data_safe()
    asyncio.create_task(auto_updater_task())

# ----------------- Endpoints -----------------
@app.get("/")
def root():
    return {"message": "IPO Live Backend is Running", "total_ipos": len(CACHED_IPOS)}

@app.get("/api/ipos/live")
async def get_live_ipos(force_refresh: bool = Query(False, description="Set True for manual pull-to-refresh")):
    global CACHED_IPOS, LAST_SCRAPE_TIME
    time_since_last = time.time() - LAST_SCRAPE_TIME
    # Agar 60s se zyada ho gaya ya force_refresh hai ya cache khali hai toh naya live scrape hoga
    if force_refresh or not CACHED_IPOS or time_since_last > SCRAPE_TTL_SECONDS:
        await sync_data_safe()
    return CACHED_IPOS

@app.get("/api/ipos")
async def get_ipos_alias(force_refresh: bool = Query(False)):
    return await get_live_ipos(force_refresh=force_refresh)

@app.post("/api/allotment/check-batch")
def check_allotment_batch_api(payload: AllotmentBatchRequest):
    acc_list = [{"id": a.id, "name": a.name, "pan": a.pan} for a in payload.accounts]
    res = verify_family_allotments(payload.ipo_name, acc_list, payload.lot_size)
    return {"success": True, "results": res}