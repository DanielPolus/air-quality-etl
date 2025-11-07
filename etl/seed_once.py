from datetime import datetime, timezone
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Station, Measurement, ParameterEnum

with SessionLocal() as db:
    st = db.execute(
        select(Station).where(Station.source=="openaq", Station.external_id=="demo-1")
    ).scalar_one_or_none()
    if not st:
        st = Station(source="openaq", external_id="demo-1",
                     city="Bucharest", name="Demo Station", lat=44.43, lon=26.10)
        db.add(st); db.flush()

    m = Measurement(
        station_id=st.id,
        parameter=ParameterEnum.pm25,
        value=12.3,
        unit="µg/m³",
        measured_at=datetime.now(timezone.utc)
    )
    db.add(m)
    db.commit()
print("OK: seeded one measurement")
