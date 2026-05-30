from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import date
import uuid

from database import get_db
import models
import schemas
import auth
from fastapi.security import OAuth2PasswordBearer

from weather import get_weather_forecast
from holidays import get_german_holidays

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/verify")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    payload = auth.verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(models.User).where(models.User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user

@router.get("/{event_id}/weather")
async def get_event_weather(
    event_id: uuid.UUID,
    lat: float,
    lon: float,
    start_date: date,
    end_date: date,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await get_weather_forecast(lat, lon, start_date, end_date)

@router.get("/holidays/{year}")
async def get_holidays(
    year: int,
    bundesland: str = "ALL",
    current_user: models.User = Depends(get_current_user)
):
    return await get_german_holidays(year, bundesland)

@router.post("/", response_model=schemas.EventResponse)
async def create_event(event_in: schemas.EventCreate, current_user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    db_event = models.Event(
        **event_in.dict(),
        organizer_id=current_user.id
    )
    db.add(db_event)
    await db.flush()
    
    # Organizer automatically becomes a participant
    participant = models.EventParticipant(
        event_id=db_event.id,
        user_id=current_user.id
    )
    db.add(participant)
    
    await db.commit()
    await db.refresh(db_event)
    return db_event

@router.get("/", response_model=List[schemas.EventResponse])
async def list_events(current_user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # List events where user is organizer or participant
    result = await db.execute(
        select(models.Event)
        .join(models.EventParticipant)
        .where(models.EventParticipant.user_id == current_user.id)
    )
    return result.scalars().all()

@router.post("/{event_id}/invite", status_code=status.HTTP_200_OK)
async def invite_participant(
    event_id: uuid.UUID,
    email: str,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if user is organizer
    result = await db.execute(select(models.Event).where(models.Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event or event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can invite participants")
    
    # Check if user already exists
    result = await db.execute(select(models.User).where(models.User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        user = models.User(email=email, name=email.split("@")[0])
        db.add(user)
        await db.flush()
    
    # Add as participant if not already
    result = await db.execute(
        select(models.EventParticipant)
        .where(models.EventParticipant.event_id == event_id)
        .where(models.EventParticipant.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        participant = models.EventParticipant(event_id=event_id, user_id=user.id)
        db.add(participant)
    
    await db.commit()
    return {"message": f"User {email} invited"}

@router.get("/{event_id}", response_model=schemas.EventResponse)
async def get_event(event_id: uuid.UUID, current_user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Event)
        .join(models.EventParticipant)
        .where(models.Event.id == event_id)
        .where(models.EventParticipant.user_id == current_user.id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return event
