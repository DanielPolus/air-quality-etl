import os
import time
from typing import Dict, List
from datetime import datetime, timezone

from app.db import db_session
from etl.sources.openaq import fetch_city_measurements_v3
from etl.load import upsert_batch_hours

HOURS_BACK = int(os.getenv("ETL_HOURS_BACK", "8"))
MAX_LOCATIONS = int(os.getenv("ETL_MAX_LOCATIONS", "5"))
MAX_SENSORS = int(os.getenv("ETL_MAX_SENSORS", "12"))
SLEEP_BETWEEN_CALLS = float(os.getenv("ETL_SLEEP", "0.4"))

CITIES: Dict[str, Dict] = {
    "Bucharest": {"lat": 44.4268, "lon": 26.1025},
}

def _parse_iso_utc(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s).astimezone(timezone.utc)

def limit_latest_per_sensor(rows: List[Dict], max_sensors: int = None) -> List[Dict]:
    latest = {}
    for r in rows:
        key = (r["sensor_id"], r["parameter"])
        ts = _parse_iso_utc(r["measured_at"])
        if key not in latest or _parse_iso_utc(latest[key]["measured_at"]) < ts:
            latest[key] = r
    out = list(latest.values())
    if max_sensors:
        out = out[:max_sensors]
    return out

def run_once():
    total = 0
    with db_session() as db:
        for city, coords in CITIES.items():
            print(f"[ETL] City={city} hours_back={HOURS_BACK}")
            rows = fetch_city_measurements_v3(
                city_name=city,
                lat=coords["lat"],
                lon=coords["lon"],
                hours_back=HOURS_BACK,
                max_locations=MAX_LOCATIONS,
                max_sensors=MAX_SENSORS,
                max_rows_total=2000,
            )
            print(f"[ETL] fetched {len(rows)} rows")
            if not rows:
                print("[ETL] nothing to insert"); continue
            n = upsert_batch_hours(db, rows)
            db.commit()
            total += n
            print(f"[ETL] inserted/updated={n}")
            time.sleep(SLEEP_BETWEEN_CALLS)
    print(f"[ETL] DONE. total_inserted_or_updated={total}")

if __name__ == "__main__":
    run_once()
