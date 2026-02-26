from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
from uuid import UUID

from backend.app.models.station import Location

class UserCreate(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    home_location: Optional[Location] = None
    alert_threshold: Optional[float] = 0.5
    notifications_enabled: Optional[bool] = True

class UserResponse(BaseModel):
    id: UUID
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    home_location: Optional[Location] = None
    alert_threshold: float
    notifications_enabled: bool
    created_at: datetime

class UserUpdate(BaseModel):
    phone_number: Optional[str] = None
    home_location: Optional[Location] = None
    alert_threshold: Optional[float] = None
    notifications_enabled: Optional[bool] = None