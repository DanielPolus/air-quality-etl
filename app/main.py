from fastapi import FastAPI
from app.routers.health import router as health_router
from app.routers.metrics_quick import router as metrics_quick_router
from app.routers.measurements import router as meas_router
from app.routers.analytics import router as analytics_router

app = FastAPI(title="Air Quality ETL API")
app.include_router(health_router)
app.include_router(metrics_quick_router)
if 'meas_router' in globals(): app.include_router(meas_router)
if 'analytics_router' in globals(): app.include_router(analytics_router)




# git add .
# git commit -m "message"
# git push origin main
