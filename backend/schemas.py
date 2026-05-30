from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, date
from typing import List, Optional
import uuid
from models import UserRole, AvailabilityStatus, NotificationType

class UserBase(BaseModel):
    email: EmailStr
    name: str
    bundesland: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: uuid.UUID
    role: UserRole
    is_owner: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class MagicLinkRequest(BaseModel):
    email: EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str

class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class EventCreate(EventBase):
    pass

class EventResponse(EventBase):
    id: uuid.UUID
    organizer_id: uuid.UUID
    final_date: Optional[date] = None
    is_closed: bool
    created_at: datetime

    class Config:
        from_attributes = True

class AvailabilityBase(BaseModel):
    event_date: date
    status: AvailabilityStatus
    comment: Optional[str] = None

class AvailabilityResponse(AvailabilityBase):
    id: uuid.UUID
    participant_id: uuid.UUID

    class Config:
        from_attributes = True
