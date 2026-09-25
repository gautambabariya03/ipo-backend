import sys
import os

# Server folder path add karein taaki module import error na aaye
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import re
from datetime import datetime, timezone, timedelta
from scrapers.gmp_scraper import fetch_live_gmp

app = FastAPI(title="IPO Live Backend API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def clean_pure_date(date_str: str) -> str:
    """Date ke beech se GMP, %, aur extra kachra hatakar sirf clean date rakhta hai"""
    if not date_str or date_str in ["Live", "--", ""]:
        return date_str
    
    cleaned = re.sub(r'₹?\s*[-+]?\d+(?:\.\d+)?\s*%', '', date_str)
    cleaned = re.sub(r'₹\s*[-+]?\d+(?:\.\d+)?', '', cleaned)
    cleaned = re.sub(r'\[.*?\]|\(.*?\)', '', cleaned)
    
    dates = re.findall(r'\b\d{1,2}(?:st|nd|rd|th)?[\s\-]*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*(?:[\s\-]*\d{2,4})?\b', cleaned, re.IGNORECASE)
    
    if len(dates) >= 2:
        return f"{dates[0]} - {dates[1]}"
    elif len(dates) == 1:
        return dates[0]
    
    return date_str.strip()

def process_and_sort_ipos(ipo_list):
    """
    Sirf 3 Status:
    - O -> OPEN
    - U -> UPCOMING
    - C ya L -> CLOSED
    """
    for item in ipo_list:
        raw_name = item.get("name", "").strip()
        name_upper = raw_name.upper()

        # 1. CLOSED
        if name_upper.endswith("C") or name_upper.endswith("L") or "CLOSED" in name_upper or "LISTED" in name_upper:
            item["status"] = "CLOSED"

        # 2. UPCOMING
        elif name_upper.endswith("U") or "UPCOMING" in name_upper:
            item["status"] = "UPCOMING"

        # 3. OPEN
        elif name_upper.endswith("O") or "OPEN" in name_upper:
            item["status"] = "OPEN"

        else:
            item["status"] = "CLOSED"

        # Clean Date Range
        item["date_range"] = clean_pure_date(item.get("date_range", ""))

        # Clean Company Name
        clean_name = re.sub(r'\[email&#160;protected\]', '', raw_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'L@[\d\.\(\)\%\+\-]+', '', clean_name)
        clean_name = re.sub(r'(\(?(BSE\s+|NSE\s+)?SME\)?[UOCL]*|IPO[UOCL]*$)', '', clean_name, flags=re.IGNORECASE).strip()
        item["name"] = clean_name.strip(' -–@')

    return ipo_list

@app.get("/")
def root():
    return {"message": "IPO Live Backend is Running Successfully"}

@app.get("/api/ipos/live")
def get_live_ipos(force_refresh: bool = False):
    raw_data = fetch_live_gmp()
    sorted_data = process_and_sort_ipos(raw_data)
    return sorted_data

@app.get("/api/ipos")
def get_ipos_alias():
    return get_live_ipos()