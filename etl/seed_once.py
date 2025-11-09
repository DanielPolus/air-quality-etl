from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from app.db import db_session
from app.models import Station, Measurement

def main():
    with db_session() as db:
        st = db.execute(
            select(Station).where(Station.external_id == 999999)
        ).scalar_one_or_none()

        if not st:
            st = Station(
                source="openaq",
                external_id=999999,
                city="Bucharest",
                name="Test",
                lat=44.43,
                lon=26.10,
            )
            db.add(st)
            db.flush()

        db.add(Measurement(
            station_id=st.id,
            parameter="pm25",
            value=12.3,
            unit="µg/m³",
            measured_at=datetime.now(timezone.utc) - timedelta(hours=1),
        ))
        db.commit()
    print("Seeded one pm25 row for Bucharest.")

if __name__ == "__main__":
    main()
