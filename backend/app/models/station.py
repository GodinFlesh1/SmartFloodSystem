from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
from uuid import UUID

class Location(BaseModel):
    latitude: float
    longitude: float

class StationCreate(BaseModel):
    ea_station_id: str
    station_name: str
    location: Location
    town: Optional[str] = None
    river_name: Optional[str] = None
    typical_range_high: Optional[float] = None
    typical_range_low: Optional[float] = None

class StationResponse(BaseModel):
    id: UUID
    ea_station_id: str
    station_name: str
    location: Location
    town: Optional[str] = None
    river_name: Optional[str] = None
    typical_range_high: Optional[float] = None
    typical_range_low: Optional[float] = None
    created_at: datetime