from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from app.db import get_db
from app.models import Station, Measurement

router = APIRouter(prefix="/metrics", tags=["metrics-quick"])

@router.get("/quick")
def quick(db = Depends(get_db)):
    # есть ли станции/измерения — через EXISTS (быстро)
    has_st = db.scalar(select(func.exists().where(Station.id.isnot(None))))
    has_m  = db.scalar(select(func.exists().where(Measurement.id.isnot(None))))
    # последние метки по 5 свежим городам/параметрам (ограничение — быстро)
    latest = db.execute(
        select(Station.city, Measurement.parameter, func.max(Measurement.measured_at))
        .join(Station, Station.id == Measurement.station_id)
        .group_by(Station.city, Measurement.parameter)
        .order_by(func.max(Measurement.measured_at).desc())
        .limit(5)
    ).all()
    return {
        "stations_exist": bool(has_st),
        "measurements_exist": bool(has_m),
        "latest": [{"city": c, "parameter": p, "ts": ts} for c, p, ts in latest],
    }

@router.get("/latest")
def latest(
    city: str = Query(...),
    parameter: str = Query(...),
    db = Depends(get_db),
):
    row = db.execute(
        select(Measurement.value, Measurement.unit, Measurement.measured_at)
        .join(Station, Station.id == Measurement.station_id)
        .where(Station.city == city, Measurement.parameter == parameter)
        .order_by(Measurement.measured_at.desc())
        .limit(1)
    ).first()
    if not row:
        return {"city": city, "parameter": parameter, "value": None, "unit": None, "measured_at": None}
    v, u, ts = row
    return {"city": city, "parameter": parameter, "value": float(v), "unit": u, "measured_at": ts}
