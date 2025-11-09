# etl/load.py
from typing import Dict, List, Tuple, Any
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import Station, Measurement, ParameterEnum

def upsert_batch_hours(db, items: List[Dict[str, Any]]) -> int:
    """
    items — результаты transform.clean_hours(...).
    1) upsert Station по (source, external_id),
    2) bulk insert Measurement с ON CONFLICT DO NOTHING по (station_id, parameter, measured_at).
    """
    if not items:
        return 0

    stations_map: Dict[Tuple[str, str], int] = {}

    # 1) станции
    for it in items:
        key = (it["source"], it["external_id"])
        if key in stations_map:
            continue

        st = db.execute(
            select(Station).where(
                Station.source == it["source"],
                Station.external_id == it["external_id"],
            )
        ).scalar_one_or_none()

        if not st:
            st = Station(
                source=it["source"],
                external_id=it["external_id"],
                city=it.get("city"),
                name=it.get("station_name"),
                lat=it.get("lat"),
                lon=it.get("lon"),
            )
            db.add(st)
            db.flush()  # получаем st.id

        stations_map[key] = st.id

    # 2) measurements (bulk)
    rows = []
    for it in items:
        rows.append({
            "station_id": stations_map[(it["source"], it["external_id"])],
            "parameter": ParameterEnum(it["parameter"]),
            "value": it["value"],
            "unit": it["unit"],
            "measured_at": it["measured_at"],  # ISO UTC -> timestamptz
        })

    ins = insert(Measurement).values(rows)
    do_nothing = ins.on_conflict_do_nothing(
        index_elements=["station_id", "parameter", "measured_at"]
    )
    db.execute(do_nothing)
    db.commit()
    return len(rows)
