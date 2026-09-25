from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import asyncio

from scrapers.gmp_scraper import fetch_live_gmp
from scrapers.allotment_checker import verify_family_allotments

app = FastAPI(title="IPO GMP Tracker API")

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

# ----------------- In-memory State -----------------
CACHED_IPOS = []

async def sync_data_safe():
    """Network fetch ko non-blocking thread me chalata hai."""
    global CACHED_IPOS
    try:
        data = await asyncio.to_thread(fetch_live_gmp)
        if data:
            CACHED_IPOS = data
            print(f"[{asyncio.get_event_loop().time():.1f}] Live Sync Complete: {len(CACHED_IPOS)} IPOs cached.")
    except Exception as e:
        print(f"Background Sync Error: {e}")

async def auto_updater_task():
    """Har 10 minute me background me live GMP fetch karega."""
    while True:
        await asyncio.sleep(600)
        print("Syncing live GMP data in background...")
        await sync_data_safe()

@app.on_event("startup")
async def on_startup():
    print("Initial server startup: Loading live IPO dataset...")
    await sync_data_safe()
    asyncio.create_task(auto_updater_task())

# ----------------- Endpoints -----------------
@app.get("/api/ipos/live")
async def get_live_ipos(force_refresh: bool = Query(False, description="Set True for manual pull-to-refresh")):
    global CACHED_IPOS
    if force_refresh or not CACHED_IPOS:
        await sync_data_safe()
    return CACHED_IPOS

@app.post("/api/allotment/check-batch")
def check_allotment_batch_api(payload: AllotmentBatchRequest):
    acc_list = [{"id": a.id, "name": a.name, "pan": a.pan} for a in payload.accounts]
    res = verify_family_allotments(payload.ipo_name, acc_list, payload.lot_size)
    return {"success": True, "results": res}