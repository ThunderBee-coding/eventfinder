from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete as sql_delete
from typing import List
from datetime import datetime, timedelta, date as date_type
import uuid
import os
import secrets

from database import get_db
import models
import schemas
import auth
from fastapi.security import OAuth2PasswordBearer
from tasks import schedule_organizer_summary

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/verify")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


def _ical_escape(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n")
    )


def _ical_fold(text: str) -> str:
    """RFC 5545 §3.1: Zeilen > 75 Oktetts mit CRLF+Space falten."""
    lines = text.split("\r\n")
    folded = []
    for line in lines:
        encoded = line.encode("utf-8")
        if len(encoded) <= 75:
            folded.append(line)
            continue
        # Falte in 75-Oktett-Blöcke (erste Zeile 75, Fortsetzungen 74 + führendes Leerzeichen)
        chunks = []
        pos = 0
        first = True
        while pos < len(encoded):
            limit = 75 if first else 74
            chunk = encoded[pos:pos + limit]
            # Nicht mitten in einem UTF-8-Multibyte-Zeichen trennen
            while len(chunk) > 0 and (chunk[-1] & 0xC0) == 0x80:
                chunk = chunk[:-1]
            chunks.append(("" if first else " ") + chunk.decode("utf-8"))
            pos += len(chunk)
            first = False
        folded.append("\r\n".join(chunks))
    return "\r\n".join(folded)


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


async def _get_event_as_participant(event_id: uuid.UUID, user: models.User, db: AsyncSession) -> models.Event:
    result = await db.execute(
        select(models.Event)
        .join(models.EventParticipant)
        .where(models.Event.id == event_id)
        .where(models.EventParticipant.user_id == user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/", response_model=schemas.EventResponse)
async def create_event(
    event_in: schemas.EventCreate,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in (models.UserRole.organizer, models.UserRole.superadmin):
        raise HTTPException(status_code=403, detail="Nur Organisatoren und Admins dürfen Events anlegen")
    db_event = models.Event(
        title=event_in.title,
        description=event_in.description,
        location_name=event_in.location_name,
        accent_color=event_in.accent_color,
        organizer_id=current_user.id,
    )
    db.add(db_event)
    await db.flush()

    participant = models.EventParticipant(event_id=db_event.id, user_id=current_user.id)
    db.add(participant)

    for d in event_in.proposed_dates:
        db.add(models.DateProposal(event_id=db_event.id, proposed_date=d))

    await db.commit()
    await db.refresh(db_event)
    return db_event


@router.get("/", response_model=List[schemas.EventResponse])
async def list_events(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.Event)
        .join(models.EventParticipant)
        .where(models.EventParticipant.user_id == current_user.id)
    )
    return result.scalars().all()


@router.get("/{event_id}", response_model=schemas.EventResponse)
async def get_event(
    event_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_event_as_participant(event_id, current_user, db)


@router.patch("/{event_id}", response_model=schemas.EventResponse)
async def patch_event(
    event_id: uuid.UUID,
    patch: schemas.EventPatch,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await _get_event_as_participant(event_id, current_user, db)
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can edit this event")

    patch_data = patch.model_dump(exclude_unset=True)

    # Geocoding: wenn address gesetzt, lat/lon/bundesland automatisch ermitteln
    if "address" in patch_data:
        import httpx as _httpx
        try:
            async with _httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": patch_data["address"], "format": "json", "addressdetails": 1, "limit": 1},
                    headers={"User-Agent": "EventFinder/2.0 (thunderbee732@gmail.com)"},
                    timeout=8.0,
                )
                geo = resp.json()
            if geo:
                patch_data["latitude"] = float(geo[0]["lat"])
                patch_data["longitude"] = float(geo[0]["lon"])
                addr = geo[0].get("address", {})
                iso = addr.get("ISO3166-2-lvl4", "")
                patch_data["bundesland"] = iso[3:] if iso.startswith("DE-") else ""
        except Exception as e:
            print(f"Geocoding failed: {e}")

    for field, value in patch_data.items():
        setattr(event, field, value)

    await db.commit()
    await db.refresh(event)

    # Wetter-Historie abrufen wenn Koordinaten jetzt gesetzt
    if event.latitude and event.longitude:
        try:
            from tasks import fetch_weather_history
            fetch_weather_history.delay(str(event_id), event.latitude, event.longitude)
        except Exception as e:
            print(f"Weather task dispatch failed: {e}")  # nicht kritisch

    return event


@router.post("/{event_id}/cover", response_model=schemas.EventResponse)
async def upload_cover(
    event_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from PIL import Image
    import io

    event = await _get_event_as_participant(event_id, current_user, db)
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can upload a cover")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG, or WebP images are allowed")

    contents = await file.read()
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be smaller than 5 MB")

    img = Image.open(io.BytesIO(contents))
    if img.width > 1200:
        ratio = 1200 / img.width
        img = img.resize((1200, int(img.height * ratio)), Image.LANCZOS)

    ext = file.content_type.split("/")[1].replace("jpeg", "jpg")
    filename = f"{uuid.uuid4()}.{ext}"
    path = f"/app/uploads/{filename}"

    if event.cover_image_path:
        old = f"/app/{event.cover_image_path}"
        if os.path.exists(old):
            os.remove(old)

    img.save(path, quality=85, optimize=True)
    event.cover_image_path = f"uploads/{filename}"
    await db.commit()
    await db.refresh(event)
    return event


@router.delete("/{event_id}/cover", status_code=204)
async def delete_cover(
    event_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await _get_event_as_participant(event_id, current_user, db)
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can delete the cover")
    if event.cover_image_path:
        path = f"/app/{event.cover_image_path}"
        if os.path.exists(path):
            os.remove(path)
        event.cover_image_path = None
        await db.commit()


@router.post("/{event_id}/background", response_model=schemas.EventResponse)
async def upload_background(
    event_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from PIL import Image
    import io

    event = await _get_event_as_participant(event_id, current_user, db)
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can upload a background")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG, or WebP images are allowed")

    contents = await file.read()
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be smaller than 5 MB")

    img = Image.open(io.BytesIO(contents))
    if img.width > 1920:
        ratio = 1920 / img.width
        img = img.resize((1920, int(img.height * ratio)), Image.LANCZOS)

    ext = file.content_type.split("/")[1].replace("jpeg", "jpg")
    filename = f"bg-{uuid.uuid4()}.{ext}"
    path = f"/app/uploads/{filename}"

    if event.background_image_path:
        old = f"/app/{event.background_image_path}"
        if os.path.exists(old):
            os.remove(old)

    img.save(path, quality=85, optimize=True)
    event.background_image_path = f"uploads/{filename}"
    await db.commit()
    await db.refresh(event)
    return event


@router.delete("/{event_id}/background", status_code=204)
async def delete_background(
    event_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await _get_event_as_participant(event_id, current_user, db)
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can delete the background")
    if event.background_image_path:
        path = f"/app/{event.background_image_path}"
        if os.path.exists(path):
            os.remove(path)
        event.background_image_path = None
        await db.commit()


@router.get("/{event_id}/participants", response_model=List[schemas.ParticipantResponse])
async def get_participants(
    event_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_event_as_participant(event_id, current_user, db)

    result = await db.execute(
        select(
            models.User.id,
            models.EventParticipant.id.label("participant_id"),
            models.User.name,
            models.User.email,
            models.User.role,
            models.EventParticipant.joined_at,
            func.count(models.Availability.id).label("availability_count"),
        )
        .join(models.EventParticipant, models.EventParticipant.user_id == models.User.id)
        .outerjoin(models.Availability, models.Availability.participant_id == models.EventParticipant.id)
        .where(models.EventParticipant.event_id == event_id)
        .group_by(models.User.id, models.EventParticipant.id, models.User.name, models.User.email, models.User.role, models.EventParticipant.joined_at)
    )
    rows = result.all()
    return [
        schemas.ParticipantResponse(
            id=r.id, participant_id=r.participant_id, name=r.name, email=r.email,
            joined_at=r.joined_at, availability_count=r.availability_count
        )
        for r in rows
    ]


@router.delete("/{event_id}/participants/{user_id}", status_code=204)
async def remove_participant(
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await _get_event_as_participant(event_id, current_user, db)
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can remove participants")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    result = await db.execute(
        select(models.EventParticipant)
        .where(models.EventParticipant.event_id == event_id)
        .where(models.EventParticipant.user_id == user_id)
    )
    participant = result.scalar_one_or_none()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    await db.delete(participant)
    await db.commit()


@router.patch("/{event_id}/organizer", response_model=schemas.EventResponse)
async def transfer_organizer(
    event_id: uuid.UUID,
    body: schemas.OrganizerTransfer,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await _get_event_as_participant(event_id, current_user, db)
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the current organizer can transfer this role")

    result = await db.execute(
        select(models.EventParticipant)
        .where(models.EventParticipant.event_id == event_id)
        .where(models.EventParticipant.user_id == body.user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User is not a participant of this event")

    event.organizer_id = body.user_id
    await db.commit()
    await db.refresh(event)
    return event


@router.post("/{event_id}/invite", status_code=200)
async def invite_participant(
    event_id: uuid.UUID,
    body: schemas.InviteRequest,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from tasks import send_invitation_email

    event = await _get_event_as_participant(event_id, current_user, db)
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can invite participants")

    email = body.email
    result = await db.execute(select(models.User).where(models.User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        user = models.User(
            id=uuid.uuid4(), email=email, name=email.split("@")[0],
            is_owner=False, is_active=True, created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        )
        db.add(user)
        await db.flush()

    already_participant = await db.execute(
        select(models.EventParticipant)
        .where(models.EventParticipant.event_id == event_id)
        .where(models.EventParticipant.user_id == user.id)
    )
    if not already_participant.scalar_one_or_none():
        db.add(models.EventParticipant(event_id=event_id, user_id=user.id))

    token = secrets.token_urlsafe(32)
    db.add(models.MagicLink(
        user_id=user.id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    ))

    await db.commit()

    send_invitation_email.delay(
        recipient_email=email,
        inviter_name=current_user.name,
        event_title=event.title,
        token=token,
        event_id=str(event_id),
        message=body.message or "",
    )
    schedule_organizer_summary(
        str(event_id),
        f"{current_user.name} hat {email} zum Event eingeladen."
    )

    return {"message": f"{email} eingeladen"}


@router.get("/{event_id}/proposals", response_model=List[schemas.DateProposalResponse])
async def get_proposals(
    event_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_event_as_participant(event_id, current_user, db)
    result = await db.execute(
        select(models.DateProposal)
        .where(models.DateProposal.event_id == event_id)
        .order_by(models.DateProposal.proposed_date)
    )
    return result.scalars().all()


@router.post("/{event_id}/proposals", response_model=List[schemas.DateProposalResponse])
async def set_proposals(
    event_id: uuid.UUID,
    body: schemas.DateProposalsSet,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await _get_event_as_participant(event_id, current_user, db)
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can set date proposals")

    await db.execute(sql_delete(models.DateProposal).where(models.DateProposal.event_id == event_id))

    new_proposals = [
        models.DateProposal(id=uuid.uuid4(), event_id=event_id, proposed_date=d)
        for d in body.dates
    ]
    db.add_all(new_proposals)
    await db.commit()
    schedule_organizer_summary(
        str(event_id),
        f"{current_user.name} hat die Terminvorschläge aktualisiert ({len(body.dates)} Termine)."
    )
    return new_proposals


@router.post("/{event_id}/send-invites", status_code=200)
async def send_calendar_invites_endpoint(
    event_id: uuid.UUID,
    body: schemas.SendCalendarInvitesRequest,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from tasks import send_calendar_invites
    event = await _get_event_as_participant(event_id, current_user, db)
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can send calendar invites")
    if not event.final_date:
        raise HTTPException(status_code=400, detail="No final date set")
    send_calendar_invites.delay(
        str(event_id), body.start_time, body.end_time, body.description or ""
    )
    return {"message": "Kalender-Einladungen werden versendet"}


@router.post("/{event_id}/send-calendar-links", status_code=200)
async def send_calendar_links_endpoint(
    event_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from tasks import send_calendar_subscription_emails
    event = await _get_event_as_participant(event_id, current_user, db)
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can send calendar links")
    send_calendar_subscription_emails.delay(str(event_id))
    return {"message": "Kalender-Links werden versendet"}


@router.get("/{event_id}/holidays")
async def get_holidays(
    event_id: uuid.UUID,
    year: int = 2026,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await _get_event_as_participant(event_id, current_user, db)
    from holidays import get_german_holidays
    bundesland = event.bundesland or "NATIONAL"
    raw = await get_german_holidays(year, bundesland)
    result = {}
    for name, info in raw.items():
        if isinstance(info, dict) and "datum" in info:
            result[info["datum"]] = name.replace("_", " ")
    return result


@router.get("/{event_id}/weather-hints")
async def get_weather_hints(
    event_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import httpx

    event = await _get_event_as_participant(event_id, current_user, db)

    proposals_result = await db.execute(
        select(models.DateProposal)
        .where(models.DateProposal.event_id == event_id)
        .order_by(models.DateProposal.proposed_date)
    )
    proposals = proposals_result.scalars().all()

    if not proposals:
        return []

    today = date_type.today()
    hints = []

    if event.latitude and event.longitude:
        lat_grid = round(event.latitude * 4) / 4
        lon_grid = round(event.longitude * 4) / 4

        wh_result = await db.execute(
            select(models.WeatherHistory)
            .where(models.WeatherHistory.lat_grid == lat_grid)
            .where(models.WeatherHistory.lon_grid == lon_grid)
        )
        wh_map = {(w.month, w.day): w for w in wh_result.scalars().all()}

        # Forecast for dates within 16 days (one API call)
        forecast_map = {}
        forecast_dates = [p.proposed_date for p in proposals if 0 <= (p.proposed_date - today).days <= 16]
        if forecast_dates:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        "https://api.open-meteo.com/v1/forecast",
                        params={
                            "latitude": event.latitude,
                            "longitude": event.longitude,
                            "daily": "temperature_2m_max,temperature_2m_min,weathercode",
                            "timezone": "Europe/Berlin",
                            "start_date": forecast_dates[0].isoformat(),
                            "end_date": forecast_dates[-1].isoformat(),
                        }
                    )
                    fdata = resp.json().get("daily", {})
                    for i, d in enumerate(fdata.get("time", [])):
                        forecast_map[d] = {
                            "temp_max": fdata["temperature_2m_max"][i],
                            "temp_min": fdata["temperature_2m_min"][i],
                            "code": fdata.get("weathercode", [None] * (i + 1))[i],
                        }
            except Exception as e:
                print(f"Forecast fetch failed: {e}")

        for p in proposals:
            d = p.proposed_date
            wh = wh_map.get((d.month, d.day))
            fc = forecast_map.get(d.isoformat())
            hints.append({
                "date": d.isoformat(),
                "temp_max_median": wh.temp_max_median if wh else None,
                "temp_min_median": wh.temp_min_median if wh else None,
                "precip_median": wh.precip_median if wh else None,
                "loading": wh is None,
                "forecast_temp_max": fc["temp_max"] if fc else None,
                "forecast_temp_min": fc["temp_min"] if fc else None,
                "forecast_code": fc["code"] if fc else None,
            })
    else:
        for p in proposals:
            hints.append({
                "date": p.proposed_date.isoformat(),
                "temp_max_median": None, "temp_min_median": None,
                "precip_median": None, "loading": False,
                "forecast_temp_max": None, "forecast_temp_min": None, "forecast_code": None,
            })

    return hints


@router.get("/{event_id}/calendar.ics")
async def get_calendar_feed(
    event_id: uuid.UUID,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.User).where(models.User.calendar_token == token)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid calendar token")

    part_result = await db.execute(
        select(models.EventParticipant)
        .where(models.EventParticipant.event_id == event_id)
        .where(models.EventParticipant.user_id == user.id)
    )
    if not part_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a participant of this event")

    ev_result = await db.execute(select(models.Event).where(models.Event.id == event_id))
    event = ev_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    prop_result = await db.execute(
        select(models.DateProposal)
        .where(models.DateProposal.event_id == event_id)
        .order_by(models.DateProposal.proposed_date)
    )
    proposals = prop_result.scalars().all()

    parts_result = await db.execute(
        select(models.User, models.EventParticipant)
        .join(models.EventParticipant, models.User.id == models.EventParticipant.user_id)
        .where(models.EventParticipant.event_id == event_id)
    )
    participants = parts_result.all()

    avail_result = await db.execute(
        select(models.Availability)
        .join(models.EventParticipant, models.EventParticipant.id == models.Availability.participant_id)
        .where(models.EventParticipant.event_id == event_id)
    )
    availabilities = avail_result.scalars().all()

    ep_to_name = {ep.id: u.name for u, ep in participants}
    location = _ical_escape(event.address or event.location_name or "")
    title = _ical_escape(event.title)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//EventFinder//EventFinder//DE",
        f"X-WR-CALNAME:{title}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
        "X-PUBLISHED-TTL:PT1H",
    ]

    frontend_url = os.getenv("FRONTEND_URL", "https://eventfinder.thunderbee.uk").rstrip("/")

    for p in proposals:
        d = p.proposed_date
        date_str = d.strftime("%Y%m%d")
        next_day = (d + timedelta(days=1)).strftime("%Y%m%d")
        iso_date = d.strftime("%Y-%m-%d")

        day_avails = [a for a in availabilities if a.event_date == d]
        voted_ep_ids = {a.participant_id for a in day_avails}

        best = [ep_to_name.get(a.participant_id, "?") for a in day_avails if a.status.value == "best"]
        possible = [ep_to_name.get(a.participant_id, "?") for a in day_avails if a.status.value == "possible"]
        impossible = [ep_to_name.get(a.participant_id, "?") for a in day_avails if a.status.value == "impossible"]
        pending = [u.name for u, ep in participants if ep.id not in voted_ep_ids]

        desc_parts = []
        if best:
            desc_parts.append(f"Perfekt: {', '.join(best)}")
        if possible:
            desc_parts.append(f"Moeglich: {', '.join(possible)}")
        if impossible:
            desc_parts.append(f"Nicht moeglich: {', '.join(impossible)}")
        if pending:
            desc_parts.append(f"Ausstehend: {', '.join(pending)}")
        description = _ical_escape("Abstimmung:\n" + "\n".join(desc_parts) if desc_parts else "Noch keine Abstimmungen")
        vote_url = f"{frontend_url}/vote/{event_id}?token={token}&date={iso_date}"

        lines += [
            "BEGIN:VEVENT",
            f"UID:proposal-{date_str}-{event_id}@eventfinder",
            f"DTSTART;VALUE=DATE:{date_str}",
            f"DTEND;VALUE=DATE:{next_day}",
            f"SUMMARY:[Vorschlag] {title}",
            "STATUS:TENTATIVE",
            "TRANSP:TRANSPARENT",
            f"LOCATION:{location}",
            f"DESCRIPTION:{description}",
            f"URL:{vote_url}",
            "END:VEVENT",
        ]

    if event.final_date:
        d = event.final_date
        date_str = d.strftime("%Y%m%d")

        if event.event_start_time and event.event_end_time:
            # Normalisiere "HH:MM" → "HHMMSS"
            start_parts = event.event_start_time.split(":")
            end_parts = event.event_end_time.split(":")
            start_hhmm = f"{start_parts[0].zfill(2)}{start_parts[1].zfill(2)}00"
            end_hhmm = f"{end_parts[0].zfill(2)}{end_parts[1].zfill(2)}00"
            lines += [
                "BEGIN:VEVENT",
                f"UID:final-{event_id}@eventfinder",
                f"DTSTART;TZID=Europe/Berlin:{date_str}T{start_hhmm}",
                f"DTEND;TZID=Europe/Berlin:{date_str}T{end_hhmm}",
                f"SUMMARY:{title}",
                "STATUS:CONFIRMED",
                "TRANSP:OPAQUE",
                f"LOCATION:{location}",
                "END:VEVENT",
            ]
        else:
            next_day = (d + timedelta(days=1)).strftime("%Y%m%d")
            lines += [
                "BEGIN:VEVENT",
                f"UID:final-{event_id}@eventfinder",
                f"DTSTART;VALUE=DATE:{date_str}",
                f"DTEND;VALUE=DATE:{next_day}",
                f"SUMMARY:{title}",
                "STATUS:CONFIRMED",
                "TRANSP:OPAQUE",
                f"LOCATION:{location}",
                "END:VEVENT",
            ]

    lines.append("END:VCALENDAR")
    ical_content = _ical_fold("\r\n".join(lines) + "\r\n")

    return Response(
        content=ical_content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="event.ics"'},
    )
