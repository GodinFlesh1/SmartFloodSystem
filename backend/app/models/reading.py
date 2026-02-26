from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
from uuid import UUID

class ReadingCreate(BaseModel):
    station_id: UUID
    water_level: float
    timestamp: datetime
    velocity: Optional[float] = None
    risk_level: Optional[str] = None  # e.g. "low", "medium", "high"

class ReadingResponse(BaseModel):
    id: int
    station_id: UUID
    water_level: float
    timestamp: datetime
    velocity: Optional[float] = None
    risk_level: Optional[str] = None
    created_at: datetime