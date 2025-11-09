from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db import get_db

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/")
def root():
    return {"ok": True}

@router.get("/db")
def db_health(db: Session = Depends(get_db)):
    now = db.scalar(text("SELECT now()"))
    return {"ok": True, "now": str(now)}
