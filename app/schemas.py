from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class MeasurementOut(BaseModel):
    city: Optional[str]
    station: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    parameter: str
    value: float
    unit: str
    measured_at: datetime

    class Config:
        from_attributes = True

class CityOut(BaseModel):
    city: str
