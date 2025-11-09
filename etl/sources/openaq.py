import os
import time
import datetime as dt
from typing import Dict, List, Tuple, Optional
import requests
from dotenv import load_dotenv
from typing import Dict, List
import time

load_dotenv()

API = "https://api.openaq.org/v3"

CFG_RADIUS_M = int(os.getenv("OPENAQ_RADIUS_M", "12000"))
CFG_MIN_DELAY_SEC = float(os.getenv("OPENAQ_MIN_DELAY_SEC", "0.4"))
CFG_PAGE_LIMIT = int(os.getenv("OPENAQ_PAGE_LIMIT", "200"))
CFG_MAX_PAGES = int(os.getenv("OPENAQ_MAX_PAGES", "5"))
CFG_SENSORS_PER_LOCATION = int(os.getenv("OPENAQ_SENSORS_PER_LOCATION", "8"))
PARAM_NAMES = {"pm25", "pm10", "no2", "o3"}

def _get_api_key() -> str:
    key = os.getenv("OPENAQ_API_KEY")
    if not key:
        raise RuntimeError("OPENAQ_API_KEY is missing. Put it into your .env")
    return key

def _headers() -> Dict[str, str]:
    return {"X-API-Key": _get_api_key()}

def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

def _iso_utc(ts: dt.datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    else:
        ts = ts.astimezone(dt.timezone.utc)
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")

_session = requests.Session()
_LAST_CALL_TS = 0.0

def _rate_gate():
    global _LAST_CALL_TS
    now = time.time()
    dt_wait = CFG_MIN_DELAY_SEC - (now - _LAST_CALL_TS)
    if dt_wait > 0:
        time.sleep(dt_wait)
    _LAST_CALL_TS = time.time()

def _get(url: str, params: Optional[Dict] = None, max_attempts: int = 6) -> Dict:
    backoff = 1.0
    for _ in range(max_attempts):
        _rate_gate()
        r = _session.get(url, params=params or {}, headers=_headers(), timeout=20)

        if r.status_code == 429:
            ra = r.headers.get("Retry-After")
            wait = float(ra) if ra and ra.isdigit() else backoff
            time.sleep(wait); backoff = min(backoff * 2.0, 12.0); continue

        if r.status_code in (408, 502, 503, 504):
            time.sleep(backoff); backoff = min(backoff * 2.0, 12.0); continue

        r.raise_for_status()
        return r.json()
    r.raise_for_status()
    return {}

def get_locations_near(lat: float, lon: float, radius_m: int = CFG_RADIUS_M, limit: int = 40) -> List[Dict]:
    params = {"coordinates": f"{lat},{lon}", "radius": radius_m, "limit": limit}
    data = _get(f"{API}/locations", params=params)
    return data.get("results", [])

_SENSORS_CACHE: Dict[int, tuple[float, List[Dict]]] = {}
_SENSORS_TTL_SEC = 600  # 10 минут

def get_sensors_for_location(location_id: int) -> List[Dict]:
    now = time.time()
    cached = _SENSORS_CACHE.get(location_id)
    if cached and (now - cached[0] < _SENSORS_TTL_SEC):
        return cached[1]
    data = _get(f"{API}/locations/{location_id}/sensors")
    results = data.get("results", [])
    _SENSORS_CACHE[location_id] = (now, results)
    return results

def get_hours(sensor_id: int, date_from: dt.datetime, date_to: dt.datetime,
              per_page: int = CFG_PAGE_LIMIT, max_pages: int = CFG_MAX_PAGES) -> List[Dict]:
    results: List[Dict] = []
    page = 1
    while page <= max_pages:
        params = {
            "date_from": _iso_utc(date_from),
            "date_to": _iso_utc(date_to),
            "limit": per_page,
            "page": page,
        }
        data = _get(f"{API}/sensors/{sensor_id}/hours", params=params)
        chunk = data.get("results", [])
        if not chunk:
            break
        results.extend(chunk)
        if len(chunk) < per_page:
            break
        page += 1
    return results

def get_locations_near(lat: float, lon: float, radius_m: int = CFG_RADIUS_M, limit: int = 40) -> List[Dict]:
    params = {"coordinates": f"{lat},{lon}", "radius": radius_m, "limit": limit}
    data = _get(f"{API}/locations", params=params)
    return data.get("results", [])

_SENSORS_CACHE: Dict[int, Tuple[float, List[Dict]]] = {}
SENSORS_TTL_SEC = 600

def get_sensors_for_location(location_id: int) -> List[Dict]:
    now = time.time()
    cached = _SENSORS_CACHE.get(location_id)
    if cached and (now - cached[0] < SENSORS_TTL_SEC):
        return cached[1]
    data = _get(f"{API}/locations/{location_id}/sensors")
    results = data.get("results", [])
    _SENSORS_CACHE[location_id] = (now, results)
    return results

def get_measurements_for_sensor(
    sensor_id: int,
    date_from: dt.datetime,
    date_to: dt.datetime,
    per_page: int = CFG_PAGE_LIMIT,
    max_pages: int = CFG_MAX_PAGES,
) -> List[Dict]:
    results: List[Dict] = []
    page = 1
    while page <= max_pages:
        params = {
            "date_from": _iso_utc(date_from),
            "date_to": _iso_utc(date_to),
            "limit": per_page,
            "page": page,
            "sort": "desc",
        }
        data = _get(f"{API}/sensors/{sensor_id}/measurements", params=params)
        chunk = data.get("results", [])
        if not chunk:
            break
        results.extend(chunk)
        if len(chunk) < per_page:
            break
        page += 1
    return results

def fetch_city_measurements_v3(
    city_name: str,
    lat: float,
    lon: float,
    hours_back: int = 24,
    max_locations: int = 6,
    max_sensors: int = 20,
    max_rows_total: int = 4000,
) -> List[Dict]:
    now = _now_utc()
    frm = now - dt.timedelta(hours=hours_back)

    locs = get_locations_near(lat, lon, radius_m=CFG_RADIUS_M, limit=40)
    if max_locations and len(locs) > max_locations:
        locs = locs[:max_locations]

    sensor_rows: List[Dict] = []
    for loc in locs:
        if max_sensors and len(sensor_rows) >= max_sensors:
            break
        loc_id = loc.get("id")
        loc_city = loc.get("city") or city_name
        loc_name = loc.get("name") or f"location-{loc_id}"
        coords = loc.get("coordinates") or {}
        loc_lat = coords.get("latitude")
        loc_lon = coords.get("longitude")

        for s in get_sensors_for_location(loc_id):
            if max_sensors and len(sensor_rows) >= max_sensors:
                break
            p = (s.get("parameter") or {}).get("name")
            if p not in PARAM_NAMES:
                continue
            sensor_rows.append({
                "location_id": loc_id,
                "city": loc_city,
                "station_name": loc_name,
                "lat": loc_lat,
                "lon": loc_lon,
                "sensor_id": s.get("id"),
                "parameter": p,
                "unit": (s.get("parameter") or {}).get("units", "") or "µg/m³",
            })

    out: List[Dict] = []
    for i, row in enumerate(sensor_rows, start=1):
        sid = row["sensor_id"]
        print(f"[OpenAQ] sensor {i}/{len(sensor_rows)} id={sid} param={row['parameter']} …")
        for m in get_measurements_for_sensor(sid, frm, now):
            value = m.get("value")
            if value is None:
                continue
            dt_dict = m.get("date") or {}
            ts = dt_dict.get("utc") or m.get("timestamp")
            if not ts:
                continue
            out.append({
                "source": "openaq",
                "external_location_id": row["location_id"],
                "sensor_id": sid,
                "city": row["city"],
                "station_name": row["station_name"],
                "lat": row["lat"],
                "lon": row["lon"],
                "parameter": row["parameter"],
                "unit": row["unit"],
                "value": float(value),
                "measured_at": ts,
            })
            if max_rows_total and len(out) >= max_rows_total:
                return out
    return out

def get_latest_measurements_for_sensor(
    sensor_id: int,
    per_sensor: int = 1,
) -> List[Dict]:
    params = {"limit": max(per_sensor, 1), "page": 1, "sort": "desc"}
    data = _get(f"{API}/sensors/{sensor_id}/measurements", params=params)
    return data.get("results", [])


def _pick_latest_from_hours(sensor_id: int, hours_back: int = 365*24) -> Optional[Dict]:
    now = _now_utc()
    frm = now - dt.timedelta(hours=hours_back)
    rows = get_hours(sensor_id, frm, now, per_page=min(CFG_PAGE_LIMIT, 200), max_pages=min(CFG_MAX_PAGES, 5))
    if not rows:
        return None
    def _ts(row: Dict) -> Optional[dt.datetime]:
        p = row.get("period") or {}
        s = (p.get("datetimeTo") or {}).get("utc") or (p.get("datetimeFrom") or {}).get("utc")
        if not s: return None
        if s.endswith("Z"): s = s[:-1] + "+00:00"
        try:
            return dt.datetime.fromisoformat(s).astimezone(dt.timezone.utc)
        except Exception:
            return None

    rows = [r for r in rows if r.get("value") is not None and _ts(r) is not None]
    if not rows:
        return None
    best = max(rows, key=_ts)
    p = best.get("period") or {}
    measured_at = (p.get("datetimeTo") or {}).get("utc") or (p.get("datetimeFrom") or {}).get("utc")
    return {
        "value": float(best["value"]),
        "date": {"utc": measured_at},
        "unit": best.get("unit") or "µg/m³",
    }


def fetch_city_latest_v3(
    city_name: str,
    lat: float,
    lon: float,
    max_locations: int = 6,
    max_sensors: int = 20,
    per_sensor: int = 1,
    max_rows_total: int = 4000,
) -> List[Dict]:
    locs = get_locations_near(lat, lon, radius_m=CFG_RADIUS_M, limit=40)
    if max_locations and len(locs) > max_locations:
        locs = locs[:max_locations]

    sensor_rows: List[Dict] = []
    for loc in locs:
        if max_sensors and len(sensor_rows) >= max_sensors: break
        loc_id = loc.get("id")
        loc_city = loc.get("city") or city_name
        loc_name = loc.get("name") or f"location-{loc_id}"
        coords = loc.get("coordinates") or {}
        loc_lat = coords.get("latitude"); loc_lon = coords.get("longitude")

        for s in get_sensors_for_location(loc_id):
            if max_sensors and len(sensor_rows) >= max_sensors: break
            p = (s.get("parameter") or {}).get("name")
            if p not in PARAM_NAMES: continue
            sensor_rows.append({
                "location_id": loc_id,
                "city": loc_city,
                "station_name": loc_name,
                "lat": loc_lat,
                "lon": loc_lon,
                "sensor_id": s.get("id"),
                "parameter": p,
                "unit": (s.get("parameter") or {}).get("units", "") or "µg/m³",
            })

    out: List[Dict] = []
    for i, row in enumerate(sensor_rows, start=1):
        sid = row["sensor_id"]
        print(f"[OpenAQ/latest] sensor {i}/{len(sensor_rows)} id={sid} param={row['parameter']} …")
        got = get_latest_measurements_for_sensor(sid, per_sensor=per_sensor)

        if not got:
            fb = _pick_latest_from_hours(sid, hours_back=365*24)
            if fb:
                got = [fb]

        for m in got or []:
            value = m.get("value")
            if value is None: continue
            dt_dict = m.get("date") or {}
            ts = dt_dict.get("utc") or m.get("timestamp")
            if not ts: continue

            out.append({
                "source": "openaq",
                "external_location_id": row["location_id"],
                "sensor_id": sid,
                "city": row["city"],
                "station_name": row["station_name"],
                "lat": row["lat"],
                "lon": row["lon"],
                "parameter": row["parameter"],
                "unit": row.get("unit") or m.get("unit") or "µg/m³",
                "value": float(value),
                "measured_at": ts,
            })
            if max_rows_total and len(out) >= max_rows_total:
                return out
    return out
