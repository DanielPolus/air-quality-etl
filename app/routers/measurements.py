from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from app.db import get_db
from app.models import Measurement, Station
from app.schemas import MeasurementOut
from typing import List
from app.schemas import CityOut

router = APIRouter(prefix="/measurements", tags=["measurements"])

@router.get("/latest", response_model=MeasurementOut)
def get_latest(city: str, parameter: str, db=Depends(get_db)):
    stmt = (
        select(Measurement, Station)
        .join(Station, Station.id == Measurement.station_id)
        .where(Station.city == city, Measurement.parameter == parameter)
        .order_by(Measurement.measured_at.desc())
        .limit(1)
    )
    row = db.execute(stmt).first()

    if not row:
        raise HTTPException(404, detail="No data")

    m, s = row

    param_value = getattr(m.parameter, "value", m.parameter)

    return {
        "city": s.city,
        "station": s.name,
        "lat": s.lat,
        "lon": s.lon,
        "parameter": param_value,
        "value": m.value,
        "unit": m.unit,
        "measured_at": m.measured_at,
    }

@router.get("/cities", response_model=List[CityOut])
def list_cities(db=Depends(get_db)):
    q = (select(Station.city)
         .where(Station.city.is_not(None))
         .distinct()
         .order_by(Station.city.asc()))

    rows = db.execute(q).all()

    return [{"city": c} for (c,) in rows]
