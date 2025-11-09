from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import get_db

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/quick")
def quick(db: Session = Depends(get_db)):
    stations = db.scalar(text("SELECT COUNT(*) FROM stations"))
    total_meas = db.scalar(text("SELECT COUNT(*) FROM measurements"))

    last_24 = db.scalar(text("""
        SELECT COUNT(*) FROM measurements
        WHERE measured_at >= now() - INTERVAL '24 hours'
    """))
    return {
        "stations": stations or 0,
        "measurements_total": total_meas or 0,
        "measurements_last_24h": last_24 or 0,
    }
