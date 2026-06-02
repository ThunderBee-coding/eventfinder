import uuid
from datetime import datetime, date
from typing import List, Optional
from sqlalchemy import String, ForeignKey, DateTime, Boolean, Enum, Float, Date, Integer, SmallInteger, UniqueConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
import enum

class UserRole(str, enum.Enum):
    superadmin = "superadmin"
    organizer = "organizer"
    participant = "participant"

class AvailabilityStatus(str, enum.Enum):
    best = "best"
    possible = "possible"
    impossible = "impossible"

class NotificationType(str, enum.Enum):
    invitation = "invitation"
    reminder = "reminder"
    update = "update"
    final_date = "final_date"

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.participant)
    bundesland: Mapped[Optional[str]] = mapped_column(String(50))
    is_owner: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    magic_links: Mapped[List["MagicLink"]] = relationship(back_populates="user", cascade="all, delete-orphan", foreign_keys="[MagicLink.user_id]")
    events_organized: Mapped[List["Event"]] = relationship(back_populates="organizer")
    event_participations: Mapped[List["EventParticipant"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class MagicLink(Base):
    __tablename__ = "magic_links"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    is_used: Mapped[bool] = mapped_column(default=False)
    used_at: Mapped[Optional[datetime]] = mapped_column()
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="magic_links", foreign_keys=[user_id])

class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    location_name: Mapped[Optional[str]] = mapped_column(String(255))
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    organizer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    final_date: Mapped[Optional[date]] = mapped_column(Date)
    is_closed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    accent_color: Mapped[str] = mapped_column(String(7), default='#06b6d4')
    cover_image_path: Mapped[Optional[str]] = mapped_column(String(255))
    address: Mapped[Optional[str]] = mapped_column(Text)
    bundesland: Mapped[Optional[str]] = mapped_column(String(10))
    background_image_path: Mapped[Optional[str]] = mapped_column(String(255))
    background_blur: Mapped[int] = mapped_column(SmallInteger, default=4)
    background_overlay: Mapped[float] = mapped_column(Float, default=0.55)

    organizer: Mapped["User"] = relationship(back_populates="events_organized")
    participants: Mapped[List["EventParticipant"]] = relationship(back_populates="event", cascade="all, delete-orphan")
    proposals: Mapped[List["DateProposal"]] = relationship(back_populates="event", cascade="all, delete-orphan")

class EventParticipant(Base):
    __tablename__ = "event_participants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    event: Mapped["Event"] = relationship(back_populates="participants")
    user: Mapped["User"] = relationship(back_populates="event_participations")
    availabilities: Mapped[List["Availability"]] = relationship(back_populates="participant", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_user"),)

class Availability(Base):
    __tablename__ = "availabilities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event_participants.id", ondelete="CASCADE"), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[AvailabilityStatus] = mapped_column(Enum(AvailabilityStatus), default=AvailabilityStatus.possible)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    participant: Mapped["EventParticipant"] = relationship(back_populates="availabilities")

    __table_args__ = (UniqueConstraint("participant_id", "event_date", name="uq_participant_date"),)

class OrganizerRotation(Base):
    __tablename__ = "organizer_rotation"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_organized_at: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    message: Mapped[Optional[str]] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(default=False)
    sent_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="notifications")

class DateProposal(Base):
    __tablename__ = "date_proposals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    proposed_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    event: Mapped["Event"] = relationship(back_populates="proposals")

    __table_args__ = (UniqueConstraint("event_id", "proposed_date", name="uq_event_date_proposal"),)

class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    is_encrypted: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

class WeatherHistory(Base):
    __tablename__ = "weather_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lat_grid: Mapped[float] = mapped_column(Float, nullable=False)
    lon_grid: Mapped[float] = mapped_column(Float, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    temp_max_median: Mapped[Optional[float]] = mapped_column(Float)
    temp_min_median: Mapped[Optional[float]] = mapped_column(Float)
    precip_median: Mapped[Optional[float]] = mapped_column(Float)
    sample_years: Mapped[Optional[int]] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("lat_grid", "lon_grid", "month", "day", name="uq_weather_grid_day"),)
