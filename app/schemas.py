from pydantic import BaseModel
from typing import Optional

class AvgOut(BaseModel):
    city: str
    parameter: str
    window_hours: int
    avg_value: Optional[float]
    n: int

class TrendPoint(BaseModel):
    date: str
    avg: Optional[float]
    n: int
