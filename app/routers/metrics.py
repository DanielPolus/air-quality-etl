from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import get_db

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/quick")
def quick(db: Session = Depends(get_db)):
    total = db.scalar(text("SELECT COUNT(*) FROM measurements"))
    last24 = db.scalar(text("""
        SELECT COUNT(*) FROM measurements
        WHERE measured_at >= now() - interval '24 hours'
    """))
    return {"total": int(total or 0), "last24h": int(last24 or 0)}
