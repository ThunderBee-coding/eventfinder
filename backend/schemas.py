from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from typing import List, Optional
import uuid
from models import UserRole, AvailabilityStatus


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
    accent_color: str = '#06b6d4'

class EventCreate(EventBase):
    proposed_dates: List[date] = []

class EventPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location_name: Optional[str] = None
    accent_color: Optional[str] = None
    final_date: Optional[date] = None
    is_closed: Optional[bool] = None

class EventResponse(EventBase):
    id: uuid.UUID
    organizer_id: uuid.UUID
    final_date: Optional[date] = None
    is_closed: bool
    cover_image_path: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class ParticipantResponse(BaseModel):
    id: uuid.UUID
    participant_id: uuid.UUID
    name: str
    email: str
    joined_at: datetime
    availability_count: int
    class Config:
        from_attributes = True

class DateProposalResponse(BaseModel):
    id: uuid.UUID
    proposed_date: date
    class Config:
        from_attributes = True

class DateProposalsSet(BaseModel):
    dates: List[date]

class OrganizerTransfer(BaseModel):
    user_id: uuid.UUID

class AvailabilityBase(BaseModel):
    event_date: date
    status: AvailabilityStatus
    comment: Optional[str] = None

class AvailabilityResponse(AvailabilityBase):
    id: uuid.UUID
    participant_id: uuid.UUID
    class Config:
        from_attributes = True
