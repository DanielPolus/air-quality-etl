from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from app.db import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])
ALLOWED_PARAMS = {"pm25", "pm10", "no2", "o3"}

@router.get("/avg")
def avg(
    city: str,
    parameter: str,
    window_hours: int = 24,
    db: Session = Depends(get_db),
):
    if parameter not in ALLOWED_PARAMS:
        return {"city": city, "parameter": parameter, "window_hours": window_hours, "avg_value": None, "n": 0}

    q = text("""
        SELECT AVG(value)::float AS avg_value, COUNT(*)::int AS n
        FROM measurements m
        JOIN stations s ON s.id = m.station_id
        WHERE s.city = :city
          AND m.parameter = :parameter
          AND m.measured_at >= now() - (:wh || ' hours')::interval
    """)
    row = db.execute(q, {"city": city, "parameter": parameter, "wh": str(window_hours)}).mappings().one()
    return {
        "city": city,
        "parameter": parameter,
        "window_hours": window_hours,
        "avg_value": row["avg_value"],
        "n": row["n"],
    }

@router.get("/trend")
def trend(
    city: str,
    parameter: str,
    days: int = 7,
    fill_gaps: bool = True,
    db: Session = Depends(get_db),
):
    if parameter not in ALLOWED_PARAMS:
        return []

    q = text("""
        WITH raw AS (
            SELECT date_trunc('day', m.measured_at) AS d, AVG(m.value)::float AS avg, COUNT(*)::int AS n
            FROM measurements m
            JOIN stations s ON s.id = m.station_id
            WHERE s.city = :city
              AND m.parameter = :parameter
              AND m.measured_at >= now() - (:days || ' days')::interval
            GROUP BY 1
        )
        SELECT d::date AS date, avg, n
        FROM raw
        ORDER BY d
    """)
    rows = [dict(r) for r in db.execute(q, {"city": city, "parameter": parameter, "days": str(days)}).mappings().all()]

    if not fill_gaps or not rows:
        return [{"date": r["date"].isoformat(), "avg": r["avg"], "n": r["n"]} for r in rows]

    from datetime import date, timedelta
    dset = {r["date"]: (r["avg"], r["n"]) for r in rows}
    start = rows[0]["date"]
    end = rows[-1]["date"]
    out = []
    cur = start
    while cur <= end:
        avg_n = dset.get(cur)
        out.append({"date": cur.isoformat(), "avg": (avg_n[0] if avg_n else None), "n": (avg_n[1] if avg_n else 0)})
        cur += timedelta(days=1)
    return out



router = APIRouter(prefix="/analytics", tags=["analytics"])

def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        # fallback: только YYYY-MM-DD
        return datetime.fromisoformat(s + "T00:00:00")

@router.get("/avg_range")
def avg_range(
    city: str = Query(...),
    parameter: str = Query(..., pattern="^(pm25|pm10|no2|o3)$"),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    dt_from = _parse_dt(date_from)
    dt_to = _parse_dt(date_to)

    filters = ["s.city = :city", "m.parameter = :parameter", "m.value >= 0"]
    params = {"city": city, "parameter": parameter}
    if dt_from:
        filters.append("m.measured_at >= :dt_from")
        params["dt_from"] = dt_from
    if dt_to:
        filters.append("m.measured_at <= :dt_to")
        params["dt_to"] = dt_to

    q = text(f"""
        SELECT
          COUNT(*)::int                                AS n,
          AVG(m.value)::float                          AS avg_value,
          MIN(m.value)::float                          AS min_value,
          MAX(m.value)::float                          AS max_value,
          PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY m.value)::float AS p50,
          PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY m.value)::float AS p90
        FROM measurements m
        JOIN stations s ON s.id = m.station_id
        WHERE {" AND ".join(filters)}
    """)

    row = db.execute(q, params).mappings().one()
    return {
        "city": city,
        "parameter": parameter,
        "from": dt_from.isoformat() if dt_from else None,
        "to": dt_to.isoformat() if dt_to else None,
        "n": row["n"] or 0,
        "avg": row["avg_value"],
        "min": row["min_value"],
        "max": row["max_value"],
        "p50": row["p50"],
        "p90": row["p90"],
    }
