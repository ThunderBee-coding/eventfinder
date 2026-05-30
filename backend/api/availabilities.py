from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid
from datetime import date

from database import get_db
import models
import schemas
from .events import get_current_user

router = APIRouter()

@router.post("/{event_id}/availability", response_model=schemas.AvailabilityResponse)
async def set_availability(
    event_id: uuid.UUID,
    availability_in: schemas.AvailabilityBase,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if user is participant
    result = await db.execute(
        select(models.EventParticipant)
        .where(models.EventParticipant.event_id == event_id)
        .where(models.EventParticipant.user_id == current_user.id)
    )
    participant = result.scalar_one_or_none()
    
    if not participant:
        raise HTTPException(status_code=403, detail="User is not a participant of this event")
    
    # Check if availability already exists for this date
    result = await db.execute(
        select(models.Availability)
        .where(models.Availability.participant_id == participant.id)
        .where(models.Availability.event_date == availability_in.event_date)
    )
    db_availability = result.scalar_one_or_none()
    
    if db_availability:
        db_availability.status = availability_in.status
        db_availability.comment = availability_in.comment
    else:
        db_availability = models.Availability(
            participant_id=participant.id,
            **availability_in.dict()
        )
        db.add(db_availability)
    
    await db.commit()
    await db.refresh(db_availability)
    return db_availability

@router.get("/{event_id}/availability", response_model=List[schemas.AvailabilityResponse])
async def get_event_availabilities(
    event_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Get all availabilities for this event
    result = await db.execute(
        select(models.Availability)
        .join(models.EventParticipant)
        .where(models.EventParticipant.event_id == event_id)
    )
    return result.scalars().all()
