from typing import Dict, List
from sqlalchemy import text
from sqlalchemy.orm import Session

STATION_UPSERT_SQL = text("""
INSERT INTO stations (source, external_id, city, name, lat, lon)
VALUES (:source, :external_id, :city, :name, :lat, :lon)
ON CONFLICT (external_id)
DO UPDATE SET
  city = EXCLUDED.city,
  name = EXCLUDED.name,
  lat = EXCLUDED.lat,
  lon = EXCLUDED.lon
RETURNING id
""")

STATION_ID_SQL = text("""
SELECT id FROM stations WHERE external_id = :external_id
""")

MEAS_UPSERT_SQL = text("""
INSERT INTO measurements (station_id, parameter, value, unit, measured_at)
VALUES (:station_id, :parameter, :value, :unit, :measured_at)
ON CONFLICT (station_id, parameter, measured_at)
DO UPDATE SET
  value = EXCLUDED.value,
  unit  = EXCLUDED.unit
""")

def _ensure_station(db: Session, row: Dict) -> int:
    res = db.execute(STATION_UPSERT_SQL, {
        "source": row["source"],
        "external_id": int(row["external_location_id"]),
        "city": row["city"],
        "name": row["station_name"],
        "lat": float(row["lat"]),
        "lon": float(row["lon"]),
    })
    sid = res.scalar()
    if sid is not None:
        return int(sid)
    sid2 = db.execute(STATION_ID_SQL, {"external_id": int(row["external_location_id"])}).scalar_one()
    return int(sid2)

def upsert_batch_hours(db: Session, rows: List[Dict]) -> int:
    inserted_or_updated = 0
    station_id_cache: Dict[int, int] = {}

    for r in rows:
        ext_id = int(r["external_location_id"])
        if ext_id in station_id_cache:
            station_id = station_id_cache[ext_id]
        else:
            station_id = _ensure_station(db, r)
            station_id_cache[ext_id] = station_id

        db.execute(MEAS_UPSERT_SQL, {
            "station_id": station_id,
            "parameter": r["parameter"],
            "value": float(r["value"]),
            "unit": r.get("unit") or "",
            "measured_at": r["measured_at"],
        })
        inserted_or_updated += 1

    return inserted_or_updated
