from app.db import db_session
from app.models import Station, Measurement
from datetime import datetime, timedelta, timezone

def main():
    with db_session() as db:
        total = db.query(Measurement).count()
        recent = db.query(Measurement).filter(
            Measurement.measured_at >= datetime.now(timezone.utc) - timedelta(hours=24)
        ).count()

        pm25 = (
            db.query(Measurement)
            .join(Station)
            .filter(Station.city == "Bucharest", Measurement.parameter == "pm25")
            .order_by(Measurement.measured_at.desc())
            .limit(5)
            .all()
        )

        print(f"Всего измерений в таблице: {total}")
        print(f"Измерений за последние 24ч: {recent}")
        print("\nПоследние 5 точек по Bucharest (pm25):")
        for m in pm25:
            print(f"  {m.measured_at} | {m.value} {m.unit}")

if __name__ == "__main__":
    main()
