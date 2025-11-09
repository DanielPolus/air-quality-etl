# etl/transform.py
from typing import Dict, Iterable, List

ALLOWED_PARAMS = {"pm25", "pm10", "no2", "o3"}

def clean_hours(rows: List[Dict], allowed_params: Iterable[str] = ALLOWED_PARAMS) -> List[Dict]:
    """
    Фильтрует и приводит «часовки» из sources.openaq.fetch_city_hours(...).
    Возвращает словари, готовые к загрузке.
    """
    allowed = set(allowed_params)
    out: List[Dict] = []
    for r in rows:
        p = r.get("parameter")
        v = r.get("value")
        ts = r.get("measured_at")
        ext_id = r.get("external_location_id")
        if p not in allowed:
            continue
        if v is None or ts is None or ext_id is None:
            continue

        out.append({
            "source": r.get("source", "openaq"),
            "external_id": str(ext_id),
            "city": r.get("city"),
            "station_name": r.get("station_name"),
            "lat": r.get("lat"),
            "lon": r.get("lon"),
            "parameter": p,          # 'pm25'|'pm10'|'no2'|'o3'
            "value": float(v),
            "unit": r.get("unit") or "",
            "measured_at": ts,       # ISO UTC
        })
    return out
