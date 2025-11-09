from fastapi import FastAPI
from app.routers import health, analytics, metrics_quick
from app.routers import metrics

app = FastAPI(title="Air Quality ETL")

app.include_router(health.router)
app.include_router(analytics.router)
app.include_router(metrics_quick.router)
app.include_router(metrics.router)
