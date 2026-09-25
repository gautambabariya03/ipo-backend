import sys
import os

# Module paths ensure karein
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scrapers.gmp_scraper import fetch_live_gmp
from utils.status_sorter import sort_and_assign_status

app = FastAPI(title="IPO Live Backend API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "IPO Live Backend is Running Successfully"}

@app.get("/api/ipos/live")
def get_live_ipos(force_refresh: bool = False):
    raw_data = fetch_live_gmp()
    sorted_data = sort_and_assign_status(raw_data)
    return sorted_data

@app.get("/api/ipos")
def get_ipos_alias():
    return get_live_ipos()