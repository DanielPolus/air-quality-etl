# etl/sources/openaq.py
import os
import time
import datetime as dt
from typing import Dict, List, Tuple, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

API = "https://api.openaq.org/v3"

# ---- Конфиг из окружения (подкручивай в .env) ----
# сколько локаций брать за прогон (чем меньше — тем меньше шанс 429)
CFG_MAX_LOCATIONS = int(os.getenv("OPENAQ_MAX_LOCATIONS", "4"))
# сколько сенсоров брать на одну локацию
CFG_SENSORS_PER_LOCATION = int(os.getenv("OPENAQ_SENSORS_PER_LOCATION", "2"))
# радиус поиска локаций (метры)
CFG_RADIUS_M = int(os.getenv("OPENAQ_RADIUS_M", "12000"))
# задержка между запросами к разным сенсорам
CFG_SLEEP_BETWEEN_SENSORS = float(os.getenv("OPENAQ_SLEEP_BETWEEN_SENSORS", "0.25"))
# размер страницы при пагинации /hours
CFG_PAGE_LIMIT = int(os.getenv("OPENAQ_PAGE_LIMIT", "200"))          # 200 безопаснее, чем 1000
# ограничение числа страниц, чтобы не «копать» слишком глубоко
CFG_MAX_PAGES = int(os.getenv("OPENAQ_MAX_PAGES", "10"))             # 10 страниц * 200 = 2000 записей на сенсор макс
# минимальный интервал между любыми HTTP-вызовами (глобальный троттлинг)
CFG_MIN_DELAY_SEC = float(os.getenv("OPENAQ_MIN_DELAY_SEC", "0.35"))

# допустимые параметры
PARAM_NAMES = {"pm25", "pm10", "no2", "o3"}

# ---- ключ / заголовки ----
def _get_api_key() -> str:
    key = os.getenv("OPENAQ_API_KEY")
    if not key:
        raise RuntimeError("OPENAQ_API_KEY is missing. Put it into your .env")
    return key

def _headers() -> Dict[str, str]:
    return {"X-API-Key": _get_api_key()}

# ---- утилиты времени ----
def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

def _iso_utc(ts: dt.datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    else:
        ts = ts.astimezone(dt.timezone.utc)
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")

# ---- HTTP helper: троттлинг + бэкофф + Retry-After ----
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
    for attempt in range(1, max_attempts + 1):
        _rate_gate()
        r = _session.get(url, params=params or {}, headers=_headers(), timeout=20)

        # 429 — уважаем Retry-After, иначе экспоненциальный бэкофф
        if r.status_code == 429:
            ra = r.headers.get("Retry-After")
            wait = float(ra) if ra and ra.isdigit() else backoff
            time.sleep(wait)
            backoff = min(backoff * 2.0, 12.0)
            continue

        # 408/5xx — временные проблемы (таймаут/сервер)
        if r.status_code in (408, 502, 503, 504):
            time.sleep(backoff)
            backoff = min(backoff * 2.0, 12.0)
            continue

        r.raise_for_status()
        return r.json()

    # если исчерпали попытки — бросим последнюю ошибку
    r.raise_for_status()  # type: ignore[name-defined]
    return {}

# ---- API v3: locations → sensors → hours ----
def get_locations_near(lat: float, lon: float, radius_m: int = CFG_RADIUS_M, limit: int = 30) -> List[Dict]:
    params = {
        "coordinates": f"{lat},{lon}",
        "radius": radius_m,
        "limit": limit,
    }
    data = _get(f"{API}/locations", params=params)
    return data.get("results", [])

# кэш сенсоров на локацию, чтобы не дёргать одно и то же
_SENSORS_CACHE: Dict[int, Tuple[float, List[Dict]]] = {}
SENSORS_TTL_SEC = 600  # 10 минут

def get_sensors_for_location(location_id: int) -> List[Dict]:
    now = time.time()
    cached = _SENSORS_CACHE.get(location_id)
    if cached and (now - cached[0] < SENSORS_TTL_SEC):
        return cached[1]

    data = _get(f"{API}/locations/{location_id}/sensors")
    results = data.get("results", [])
    _SENSORS_CACHE[location_id] = (now, results)
    return results

def get_hours(sensor_id: int, date_from: dt.datetime, date_to: dt.datetime,
              per_page: int = CFG_PAGE_LIMIT, max_pages: int = CFG_MAX_PAGES) -> List[Dict]:
    results: List[Dict] = []
    page = 1
    while True:
        if page > max_pages:
            break
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

def fetch_city_hours(
    city_name: str,
    lat: float,
    lon: float,
    hours_back: int = 24,
    max_locations: int = CFG_MAX_LOCATIONS,
    sensors_per_location: int = CFG_SENSORS_PER_LOCATION,
    sleep_between_sensors: float = CFG_SLEEP_BETWEEN_SENSORS,
) -> List[Dict]:
    """
    Возвращает нормализованные «часовки» по городу.
    Ограничивает число локаций и сенсоров, уменьшает лимит/страницы, делает паузы — чтобы не ловить 429/408.
    """
    # 1) ближайшие локации
    locs = get_locations_near(lat, lon)
    locs = locs[:max_locations]

    # 2) сенсоры нужных параметров (ограничим их число на локацию)
    sensor_rows: List[Dict] = []
    for loc in locs:
        loc_id = loc.get("id")
        loc_city = loc.get("city") or city_name
        loc_name = loc.get("name") or f"location-{loc_id}"
        coords = loc.get("coordinates") or {}
        loc_lat = coords.get("latitude")
        loc_lon = coords.get("longitude")

        sensors = get_sensors_for_location(loc_id)
        picked = 0
        for s in sensors:
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
                "unit": (s.get("parameter") or {}).get("units", ""),
            })
            picked += 1
            if picked >= sensors_per_location:
                break

    # 3) часовки за окно
    now = _now_utc()
    frm = now - dt.timedelta(hours=hours_back)

    out: List[Dict] = []
    for row in sensor_rows:
        time.sleep(sleep_between_sensors)
        sid = row["sensor_id"]
        hours = get_hours(sid, frm, now)
        for h in hours:
            value = h.get("value")
            if value is None:
                continue
            period = h.get("period", {})
            ts = ((period.get("datetimeTo") or {}).get("utc")) or ((period.get("datetimeFrom") or {}).get("utc"))
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
                "measured_at": ts,  # ISO UTC
            })
    return out
