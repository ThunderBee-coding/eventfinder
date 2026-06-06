from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from typing import List, Tuple
from datetime import date
import uuid

from database import get_db
import models
import schemas

router = APIRouter()


async def _get_user_and_participant(
    token: str,
    event_id: uuid.UUID,
    db: AsyncSession,
) -> Tuple[models.User, models.EventParticipant, models.Event]:
    # 1. Resolve user by calendar_token
    result = await db.execute(
        select(models.User).where(models.User.calendar_token == token)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    # 2. Check event exists
    result = await db.execute(
        select(models.Event).where(models.Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # 3. Check user is participant of this event
    result = await db.execute(
        select(models.EventParticipant).where(
            models.EventParticipant.event_id == event_id,
            models.EventParticipant.user_id == user.id,
        )
    )
    participant = result.scalar_one_or_none()
    if participant is None:
        raise HTTPException(status_code=403, detail="Not a participant of this event")

    return user, participant, event


async def _build_proposals_response(
    event: models.Event,
    participant_id: uuid.UUID,
    db: AsyncSession,
) -> List[schemas.ProposalVoteState]:
    # Load all proposals for this event ordered by date
    result = await db.execute(
        select(models.DateProposal)
        .where(models.DateProposal.event_id == event.id)
        .order_by(models.DateProposal.proposed_date)
    )
    proposals = result.scalars().all()

    # Load all participants with their user and availabilities (eager)
    result = await db.execute(
        select(models.EventParticipant)
        .options(
            selectinload(models.EventParticipant.user),
            selectinload(models.EventParticipant.availabilities),
        )
        .where(models.EventParticipant.event_id == event.id)
    )
    participants = result.scalars().all()

    proposal_states: List[schemas.ProposalVoteState] = []

    for proposal in proposals:
        d = proposal.proposed_date

        # Build availability lookup: participant_id -> status for this date
        avail_map: dict[uuid.UUID, models.AvailabilityStatus] = {}
        for p in participants:
            for av in p.availabilities:
                if av.event_date == d:
                    avail_map[p.id] = av.status
                    break

        # my_vote
        my_vote = avail_map.get(participant_id, None)

        # Build vote buckets
        best: List[str] = []
        possible: List[str] = []
        impossible: List[str] = []
        pending: List[str] = []

        for p in participants:
            name = p.user.name
            status = avail_map.get(p.id)
            if status is None:
                pending.append(name)
            elif status == models.AvailabilityStatus.best:
                best.append(name)
            elif status == models.AvailabilityStatus.possible:
                possible.append(name)
            elif status == models.AvailabilityStatus.impossible:
                impossible.append(name)

        proposal_states.append(
            schemas.ProposalVoteState(
                date=d,
                my_vote=my_vote,
                votes=schemas.VoteStatusEntry(
                    best=best,
                    possible=possible,
                    impossible=impossible,
                    pending=pending,
                ),
            )
        )

    return proposal_states


@router.get("/{event_id}", response_model=schemas.VotePageResponse)
async def get_vote_page(
    event_id: uuid.UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user, participant, event = await _get_user_and_participant(token, event_id, db)
    proposals = await _build_proposals_response(event, participant.id, db)
    return schemas.VotePageResponse(
        event=schemas.VoteEventInfo(id=event.id, title=event.title),
        proposals=proposals,
    )


@router.post("/{event_id}/{vote_date}", response_model=List[schemas.ProposalVoteState])
async def post_vote(
    event_id: uuid.UUID,
    vote_date: date,
    body: schemas.VoteRequest,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    user, participant, event = await _get_user_and_participant(token, event_id, db)

    # Check that a DateProposal exists for this date
    result = await db.execute(
        select(models.DateProposal).where(
            models.DateProposal.event_id == event_id,
            models.DateProposal.proposed_date == vote_date,
        )
    )
    proposal = result.scalar_one_or_none()
    if proposal is None:
        raise HTTPException(status_code=404, detail="Date proposal not found")

    # UPSERT availability
    result = await db.execute(
        select(models.Availability).where(
            models.Availability.participant_id == participant.id,
            models.Availability.event_date == vote_date,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        # Use CAST() not :: to avoid SQLAlchemy named-param parser conflict with PostgreSQL cast syntax
        await db.execute(
            text("UPDATE availabilities SET status = CAST(:s AS availabilitystatus), updated_at = NOW() WHERE id = :i"),
            {"s": body.status.value, "i": str(existing.id)},
        )
        # Expire only this object so selectinload re-reads it from DB (raw SQL bypasses ORM identity map)
        db.expire(existing)
    else:
        await db.execute(
            text(
                "INSERT INTO availabilities (id, participant_id, event_date, status, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :pid, :edate, CAST(:s AS availabilitystatus), NOW(), NOW())"
            ),
            {"pid": str(participant.id), "edate": vote_date, "s": body.status.value},
        )
    await db.commit()

    return await _build_proposals_response(event, participant.id, db)
