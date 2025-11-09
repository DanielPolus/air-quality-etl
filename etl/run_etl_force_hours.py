import os, time, datetime as dt
from typing import Dict, List, Optional
from app.db import db_session
from etl.load import upsert_batch_hours
from etl.sources.openaq import (
    get_locations_near,
    get_sensors_for_location,
    get_hours,
)

PARAMS = {"pm25", "pm10", "no2", "o3"}

HOURS_BACK = int(os.getenv("ETL_HOURS_BACK", "24"))
MAX_LOCATIONS = int(os.getenv("ETL_MAX_LOCATIONS", "8"))
MAX_SENSORS = int(os.getenv("ETL_MAX_SENSORS", "20"))
PER_SENSOR = int(os.getenv("ETL_PER_SENSOR", "1"))
SLEEP_BETWEEN = float(os.getenv("ETL_SLEEP", "0.4"))

CITIES: Dict[str, Dict] = {
    "Bucharest": {"lat": 44.4268, "lon": 26.1025},
    # More cities can be added :)
}

def _iso_to_utc(s: str) -> dt.datetime:
    if s.endswith("Z"): s = s[:-1] + "+00:00"
    return dt.datetime.fromisoformat(s).astimezone(dt.timezone.utc)

def _pick_ts(period: Dict) -> Optional[str]:
    to_ = (((period or {}).get("datetimeTo") or {}).get("utc")) if period else None
    fr_ = (((period or {}).get("datetimeFrom") or {}).get("utc")) if period else None
    return to_ or fr_

def run_once():
    total = 0
    now = dt.datetime.now(dt.timezone.utc)
    frm = now - dt.timedelta(hours=HOURS_BACK)

    with db_session() as db:
        for city, coords in CITIES.items():
            print(f"[ETL-FORCE] City={city} hours_back={HOURS_BACK}")
            locs = get_locations_near(coords["lat"], coords["lon"], limit=40)
            if not locs:
                print("  no locations found")
                continue

            sensors: List[Dict] = []
            for loc in locs:
                if MAX_SENSORS and len(sensors) >= MAX_SENSORS:
                    break
                loc_id = loc.get("id")
                loc_name = loc.get("name") or f"loc-{loc_id}"
                coords_loc = loc.get("coordinates") or {}
                loc_lat = coords_loc.get("latitude")
                loc_lon = coords_loc.get("longitude")

                for s in get_sensors_for_location(loc_id):
                    if MAX_SENSORS and len(sensors) >= MAX_SENSORS:
                        break
                    p = (s.get("parameter") or {}).get("name")
                    if p not in PARAMS:
                        continue
                    sensors.append({
                        "location_id": loc_id,
                        "city": loc.get("city") or city,
                        "station_name": loc_name,
                        "lat": loc_lat,
                        "lon": loc_lon,
                        "sensor_id": s.get("id"),
                        "parameter": p,
                        "unit": (s.get("parameter") or {}).get("units", "µg/m³"),
                    })

            print(f"  sensors picked: {len(sensors)}")

            rows_out: List[Dict] = []
            for i, s in enumerate(sensors, 1):
                sid = s["sensor_id"]
                print(f"  [hours] sensor {i}/{len(sensors)} id={sid} param={s['parameter']} …")
                hours = get_hours(sid, frm, now)
                parsed = []
                for h in hours:
                    val = h.get("value")
                    if val is None:
                        continue
                    ts = _pick_ts(h.get("period", {}))
                    if not ts:
                        continue
                    parsed.append(( _iso_to_utc(ts), float(val), ts ))

                parsed.sort(key=lambda t: t[0], reverse=True)
                for j, (ts_dt, val, ts_raw) in enumerate(parsed[:max(PER_SENSOR, 1)], 1):
                    rows_out.append({
                        "source": "openaq",
                        "external_location_id": s["location_id"],
                        "sensor_id": s["sensor_id"],
                        "city": s["city"],
                        "station_name": s["station_name"],
                        "lat": s["lat"],
                        "lon": s["lon"],
                        "parameter": s["parameter"],
                        "unit": s["unit"] or "µg/m³",
                        "value": val,
                        "measured_at": ts_raw,  # ISO UTC
                    })

                time.sleep(SLEEP_BETWEEN)

            print(f"  prepared rows: {len(rows_out)}")

            if rows_out:
                n = upsert_batch_hours(db, rows_out)
                db.commit()
                total += n
                print(f"  inserted/updated={n}")
            else:
                print("  nothing to insert")

    print(f"[ETL-FORCE] DONE. total_inserted_or_updated={total}")

if __name__ == "__main__":
    run_once()
