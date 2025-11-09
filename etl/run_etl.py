# etl/run_etl.py
import os
from typing import Dict, Tuple
from dotenv import load_dotenv

from app.db import SessionLocal
from etl.sources.openaq import fetch_city_hours
from etl.transform import clean_hours
from etl.load import upsert_batch_hours

load_dotenv()

# .env:
# AIRQ_CITY_COORDS=Bucharest:44.4268,26.1025;București:44.4268,26.1025
# INGEST_PARAMETERS=pm25,pm10,no2,o3
# HOURS_BACK=24

def _parse_city_coords(env_val: str) -> Dict[str, Tuple[float, float]]:
    out: Dict[str, Tuple[float, float]] = {}
    if not env_val:
        return out
    pairs = [p.strip() for p in env_val.split(";") if p.strip()]
    for pair in pairs:
        name, coords = pair.split(":", 1)
        lat_s, lon_s = coords.split(",", 1)
        out[name.strip()] = (float(lat_s), float(lon_s))
    return out

CITY_COORDS = _parse_city_coords(os.getenv(
    "AIRQ_CITY_COORDS",
    "Bucharest:44.4268,26.1025"
))
INGEST_PARAMETERS = [p.strip() for p in os.getenv("INGEST_PARAMETERS", "pm25,pm10,no2,o3").split(",") if p.strip()]
HOURS_BACK = int(os.getenv("HOURS_BACK", "24"))

def run_once():
    total_inserted = 0
    with SessionLocal() as db:
        for city, (lat, lon) in CITY_COORDS.items():
            raw_rows = fetch_city_hours(
                city_name=city, lat=lat, lon=lon, hours_back=HOURS_BACK,
                max_locations=6, sleep_between_sensors=0.15
            )
            items = clean_hours(raw_rows, allowed_params=INGEST_PARAMETERS)
            n = upsert_batch_hours(db, items)
            print(f"{city}: fetched={len(items)} inserted={n}")
            total_inserted += n
    print(f"TOTAL inserted: {total_inserted}")

if __name__ == "__main__":
    run_once()
