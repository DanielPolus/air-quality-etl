import os
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/airdb")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)

@contextmanager
def db_session() -> Session:
    db: Session = SessionLocal()
    try:
        db.execute(text("SET LOCAL statement_timeout = '3000ms'"))
        yield db
    finally:
        db.close()

def get_db():
    db: Session = SessionLocal()
    try:
        db.execute(text("SET LOCAL statement_timeout = '3000ms'"))
        yield db
    finally:
        db.close()
