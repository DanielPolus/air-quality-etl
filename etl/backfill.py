from datetime import datetime, timedelta, timezone
import os
import requests
from typing import List
from dotenv import load_dotenv
from app.db import SessionLocal
from etl.transform import normalize
from etl.load import upsert_batch

load_dotenv()

CITIES = [c.strip() for c in os.getenv("INGEST_CITIES", "București,Bucharest,Kharkiv,Kyiv").split(",") if c.strip()]
PARAMS = [p.strip() for p in os.getenv("INGEST_PARAMETERS", "pm25,pm10,no2,o3").split(",") if p.strip()]

BASE = "https://api.openaq.org/v2/measurements"

def fetch_range(city: str, parameters: List[str], date_from: datetime, date_to: datetime, per_page: int = 100):
    page = 1
    out = []
    while True:
        params = {
            "city": city,
            "parameter": ",".join(parameters),
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "limit": per_page,
            "page": page,
            "sort": "asc",
            "order_by": "date",
        }
        r = requests.get(BASE, params=params, timeout=30)
        r.raise_for_status()
        chunk = r.json().get("results", [])
        if not chunk:
            break
        out.extend(chunk)
        if len(chunk) < per_page:
            break
        page += 1
    return out

def run_backfill(days: int = 14):
    now = datetime.now(timezone.utc)
    frm = now - timedelta(days=days)
    total = 0
    with SessionLocal() as db:
        for city in CITIES:
            raw = fetch_range(city, PARAMS, frm, now, per_page=100)
            items = [normalize(r) for r in raw if r.get("value") is not None]
            n = upsert_batch(db, items)
            print(f"{city}: fetched={len(items)} inserted={n}")
            total += n
    print(f"Backfill total inserted: {total}")

if __name__ == "__main__":
    run_backfill(14)
