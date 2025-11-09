# 🌍 Air Quality ETL & Analytics API

A full **FastAPI + PostgreSQL** backend for collecting and analyzing open air-quality data from **OpenAQ**.

Includes:
- 🧠 ETL pipeline with rate-limiting, retries, and upsert
- 🗄️ PostgreSQL schema (Stations, Measurements)
- 📊 Analytics endpoints: average, trends, custom date ranges
- 🔎 Health checks and quick metrics
- ⚡ Seed/demo scripts

---

## 🚀 Quick Start

```bash
git clone https://github.com/<your_username>/air-quality-etl.git
cd air-quality-etl

# create .env from example
cp .env.example .env
# edit with your OpenAQ API key and DB URL

pip install -r requirements.txt
alembic upgrade head

python -m etl.seed_demo   # optional
python -m etl.run_etl_force_hours
uvicorn app.main:app --reload
```

## API endpoints:

/health/ – service check

/metrics/quick – total / recent data count

/analytics/avg_range?city=Bucharest&parameter=pm25 – all-time avg

/analytics/trend – daily averages

/analytics/now – latest readings

## 🧩 Tech Stack

- FastAPI, SQLAlchemy, Alembic

- PostgreSQL

- Requests, dotenv

- (optional) Docker for containerized setup

