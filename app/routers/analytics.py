from fastapi import APIRouter, Depends
from sqlalchemy import text
from datetime import date, timedelta
from app.db import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/trend")
def trend(
    city: str,
    parameter: str,
    days: int = 7,
    tz: str = "Europe/Bucharest",
    fill_gaps: bool = True,
    db = Depends(get_db),
):
    # ИСПРАВЛЕНО:
    # 1) сравниваем со строкой, но кастуем к enum (Postgres): ::parameter_enum
    # 2) фильтр по времени: m.measured_at >= now() - interval  (оставляем timestamptz)
    # 3) группируем по дню в переданной TZ
    q = text("""
    SELECT
      (date_trunc('day', m.measured_at AT TIME ZONE :tz))::date AS d,
      avg(m.value)::float8 AS avg_value,
      count(*) AS n
    FROM measurements m
    JOIN stations s ON s.id = m.station_id
    WHERE s.city = :city
      AND m.parameter = :parameter::parameter_enum
      AND m.measured_at >= now() - (:days || ' days')::interval
    GROUP BY d
    ORDER BY d
    """)
    rows = db.execute(q, {
        "city": city,
        "parameter": parameter,
        "days": days,
        "tz": tz
    }).mappings().all()

    data = { r["d"]: {"date": r["d"].isoformat(), "avg": r["avg_value"], "n": int(r["n"])} for r in rows }

    if fill_gaps:
        end = date.today()
        start = end - timedelta(days=days-1)
        out = []
        cur = start
        while cur <= end:
            out.append(data.get(cur, {"date": cur.isoformat(), "avg": None, "n": 0}))
            cur += timedelta(days=1)
    else:
        out = list(data.values())

    return out


router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/avg")
def avg(city: str, parameter: str, window_hours: int = 24, db=Depends(get_db)):

    q = text("""
    WITH sel AS (
      SELECT m.value
      FROM measurements m
      JOIN stations s ON s.id = m.station_id
      WHERE s.city = :city
        AND m.parameter = :parameter
        AND m.measured_at >= now() - (:window_hours || ' hours')::interval
    )
    SELECT avg(value)::float8 AS avg_value, count(*) AS n FROM sel
    """)
    row = db.execute(q, {
        "city": city,
        "parameter": parameter,
        "window_hours": window_hours
    }).mappings().first()

    avg_value = row["avg_value"] if row and row["avg_value"] is not None else None
    n = int(row["n"]) if row and row["n"] is not None else 0

    return {
        "city": city,
        "parameter": parameter,
        "window_hours": window_hours,
        "avg_value": avg_value,
        "n": n
    }

@router.get("/trend")
def trend(
    city: str,
    parameter: str,
    days: int = 7,
    tz: str = "Europe/Bucharest",
    fill_gaps: bool = True,
    db = Depends(get_db),
):
    q = text("""
    SELECT
      (date_trunc('day', m.measured_at AT TIME ZONE :tz))::date AS d,
      avg(m.value)::float8 AS avg_value,
      count(*) AS n
    FROM measurements m
    JOIN stations s ON s.id = m.station_id
    WHERE s.city = :city
      AND m.parameter::text = :parameter
      AND m.measured_at >= now() - (:days || ' days')::interval
    GROUP BY d
    ORDER BY d
    """)

    rows = db.execute(q, {
        "city": city,
        "parameter": parameter,   # <-- ВАЖНО: теперь реально передаём
        "days": days,
        "tz": tz,
    }).mappings().all()

    # Собираем словарь по дате
    data = {
        r["d"]: {"date": r["d"].isoformat(), "avg": r["avg_value"], "n": int(r["n"])}
        for r in rows
    }

    if fill_gaps:
        end = date.today()
        start = end - timedelta(days=days-1)
        out = []
        cur = start
        while cur <= end:
            out.append(data.get(cur, {"date": cur.isoformat(), "avg": None, "n": 0}))
            cur += timedelta(days=1)
    else:
        out = list(data.values())

    return out
