import os
import asyncio
import uuid
import redis as redis_lib
from celery import Celery
from aiosmtplib import send
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery(
    "tasks",
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL"),
)


def _get_smtp_settings() -> dict:
    try:
        r = redis_lib.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
        raw = r.hgetall("app:settings")
        r.close()
        if raw:
            return {k.decode(): v.decode() for k, v in raw.items()}
    except (redis_lib.ConnectionError, redis_lib.TimeoutError) as e:
        print(f"Redis connection failed: {e}, using .env fallback")
    # Fallback auf .env
    return {
        "mail_server": os.getenv("MAIL_SERVER", ""),
        "mail_port": os.getenv("MAIL_PORT", "587"),
        "mail_username": os.getenv("MAIL_USERNAME", ""),
        "mail_password": os.getenv("MAIL_PASSWORD", ""),
        "mail_from": os.getenv("MAIL_FROM", ""),
        "frontend_url": os.getenv("FRONTEND_URL", "http://localhost:5173"),
    }


async def _send_email(
    subject: str, recipient: str, body: str, settings: dict
) -> bool:
    message = EmailMessage()
    message["From"] = settings.get("mail_from") or settings.get("mail_username", "")
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    try:
        await send(
            message,
            hostname=settings["mail_server"],
            port=int(settings.get("mail_port", 587)),
            username=settings["mail_username"],
            password=settings["mail_password"],
            start_tls=int(settings.get("mail_port", 587)) == 587,
        )
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


@celery_app.task
def send_invitation_email(recipient_email: str, inviter_name: str, event_title: str, token: str, event_id: str = "", message: str = ""):
    settings = _get_smtp_settings()
    base_url = settings.get("frontend_url", "http://localhost:5173").rstrip("/")
    magic_link = f"{base_url}/login?token={token}"
    if event_id:
        magic_link += f"&event={event_id}"
    subject = f"Einladung zum Event: {event_title}"
    personal = f"\nPersönliche Nachricht von {inviter_name}:\n{message}\n" if message and message.strip() else ""
    body = (
        f"Hallo,\n\n"
        f"{inviter_name} hat dich zum Event \"{event_title}\" eingeladen.\n"
        f"{personal}\n"
        f"Klicke auf den folgenden Link, um die Einladung anzunehmen:\n"
        f"{magic_link}\n\n"
        f"Du wirst direkt zum Event weitergeleitet, wo du deine Verfügbarkeit eintragen kannst.\n"
        f"Der Link ist 24 Stunden gültig und kann nur einmal verwendet werden.\n\n"
        f"Falls du diese Einladung nicht erwartet hast, kannst du diese E-Mail ignorieren."
    )
    return asyncio.run(_send_email(subject, recipient_email, body, settings))


def schedule_organizer_summary(event_id: str, action_text: str):
    """Debounced: sendet frühestens 30 Min nach der letzten Aktion."""
    import time
    r = redis_lib.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
    version = int(time.time() * 1000)
    r.set(f"summary_v:{event_id}", version, ex=7200)
    r.set(f"summary_txt:{event_id}", action_text, ex=7200)
    r.close()
    send_organizer_summary.apply_async(args=[event_id, version], countdown=1800)


@celery_app.task
def send_organizer_summary(event_id: str, version: int):
    import time
    r = redis_lib.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
    stored = r.get(f"summary_v:{event_id}")
    action_text_raw = r.get(f"summary_txt:{event_id}")
    r.close()
    if not stored or int(stored) != version:
        return  # Neuere Aktion hat diesen Task überholt
    action_text = action_text_raw.decode() if action_text_raw else "Neue Aktivität"
    asyncio.run(_send_organizer_summary_async(event_id, action_text))


async def _send_organizer_summary_async(event_id: str, action_text: str):
    import sys
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    import models
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select

    engine = create_async_engine(os.getenv("DATABASE_URL"), echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            event_result = await session.execute(
                select(models.Event).where(models.Event.id == uuid.UUID(event_id))
            )
            event = event_result.scalar_one_or_none()
            if not event:
                return

            organizer_result = await session.execute(
                select(models.User).where(models.User.id == event.organizer_id)
            )
            organizer = organizer_result.scalar_one_or_none()
            if not organizer:
                return

            proposals_result = await session.execute(
                select(models.DateProposal)
                .where(models.DateProposal.event_id == event.id)
                .order_by(models.DateProposal.proposed_date)
            )
            proposals = proposals_result.scalars().all()

            parts_result = await session.execute(
                select(models.User, models.EventParticipant)
                .join(models.EventParticipant, models.User.id == models.EventParticipant.user_id)
                .where(models.EventParticipant.event_id == event.id)
            )
            participants = parts_result.all()

            avail_result = await session.execute(
                select(models.Availability)
                .join(models.EventParticipant, models.EventParticipant.id == models.Availability.participant_id)
                .where(models.EventParticipant.event_id == event.id)
            )
            availabilities = avail_result.scalars().all()

        # Terminübersicht aufbauen
        WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
        MONTHS = ['', 'Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']
        prop_lines = []
        for p in proposals:
            d = p.proposed_date
            date_str = f"{WEEKDAYS[d.weekday()]}, {d.day:02d}. {MONTHS[d.month]} {d.year}"
            day_avails = [a for a in availabilities if a.event_date == d]
            best = sum(1 for a in day_avails if a.status == 'best')
            possible = sum(1 for a in day_avails if a.status == 'possible')
            impossible = sum(1 for a in day_avails if a.status == 'impossible')
            voted_ids = {a.participant_id for a in day_avails}
            pending = sum(1 for _, ep in participants if ep.id not in voted_ids)
            prop_lines.append(f"  {date_str:<22}  ✓✓ {best}  ~ {possible}  ✗ {impossible}  ? {pending}")

        # Teilnehmerliste aufbauen
        part_lines = []
        for user, ep in participants:
            count = sum(1 for a in availabilities if a.participant_id == ep.id)
            is_org = user.id == event.organizer_id
            tag = ' (Organisator)' if is_org else ''
            mark = '★' if is_org else '○'
            part_lines.append(f"  {mark} {user.name}{tag} — {count}/{len(proposals)} bewertet")

        sep = '─' * 52
        body = (
            f"Hallo {organizer.name},\n\n"
            f"Aktion: {action_text}\n\n"
            f"{sep}\n"
            f"TERMINÜBERSICHT  ({len(proposals)} Vorschläge)\n"
            f"{sep}\n"
            + ("\n".join(prop_lines) if prop_lines else "  Keine Terminvorschläge") +
            f"\n\n{sep}\n"
            f"TEILNEHMER ({len(participants)})\n"
            f"{sep}\n"
            + ("\n".join(part_lines) if part_lines else "  Keine Teilnehmer") +
            f"\n\n── EventFinder"
        )

        settings = _get_smtp_settings()
        await _send_email(f"{event.title} – Aktueller Stand", organizer.email, body, settings)
    finally:
        await engine.dispose()


@celery_app.task
def send_calendar_invites(event_id: str, start_time: str, end_time: str, description: str):
    asyncio.run(_send_calendar_invites_async(event_id, start_time, end_time, description))


async def _send_calendar_invites_async(event_id: str, start_time: str, end_time: str, description: str):
    import sys
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    import models
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select

    engine = create_async_engine(os.getenv("DATABASE_URL"), echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            event_result = await session.execute(
                select(models.Event).where(models.Event.id == uuid.UUID(event_id))
            )
            event = event_result.scalar_one_or_none()
            if not event or not event.final_date:
                return

            parts_result = await session.execute(
                select(models.User)
                .join(models.EventParticipant, models.User.id == models.EventParticipant.user_id)
                .where(models.EventParticipant.event_id == event.id)
            )
            participants = parts_result.scalars().all()

        # ICS aufbauen
        def _fmt(hhmm: str) -> str:
            h, m = hhmm.split(':')
            return h.zfill(2) + m.zfill(2) + '00'

        d = event.final_date
        date_str = f"{d.year}{str(d.month).zfill(2)}{str(d.day).zfill(2)}"
        dtstart = f"{date_str}T{_fmt(start_time)}"
        dtend   = f"{date_str}T{_fmt(end_time)}"
        location = event.address or event.location_name or ""
        desc = (description or "").replace('\n', '\\n')
        summary = event.title

        ics_content = (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "PRODID:-//EventFinder//EventFinder//DE\r\n"
            "METHOD:REQUEST\r\n"
            "BEGIN:VEVENT\r\n"
            f"DTSTART:{dtstart}\r\n"
            f"DTEND:{dtend}\r\n"
            f"SUMMARY:{summary}\r\n"
            f"DESCRIPTION:{desc}\r\n"
            f"LOCATION:{location}\r\n"
            f"UID:{event_id}@eventfinder\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )

        settings = _get_smtp_settings()
        import aiosmtplib

        for participant in participants:
            msg = MIMEMultipart('mixed')
            msg['From'] = settings.get("mail_from") or settings.get("mail_username", "")
            msg['To'] = participant.email
            msg['Subject'] = f"Termin: {summary}"

            body_text = (
                f"Hallo {participant.name},\n\n"
                f"der Termin für \"{summary}\" wurde festgelegt:\n\n"
                f"📅 {d.day:02d}.{d.month:02d}.{d.year}  {start_time} – {end_time} Uhr\n"
                + (f"📍 {location}\n" if location else "") +
                (f"\n{description}\n" if description and description.strip() else "") +
                f"\nDer angehängte Kalendereintrag kann direkt in deinen Kalender importiert werden.\n\n"
                f"── EventFinder"
            )
            msg.attach(MIMEText(body_text, 'plain', 'utf-8'))

            ics_part = MIMEBase('text', 'calendar', method='REQUEST', name='termin.ics')
            ics_part.set_payload(ics_content.encode('utf-8'))
            encoders.encode_base64(ics_part)
            ics_part.add_header('Content-Disposition', 'attachment', filename='termin.ics')
            msg.attach(ics_part)

            try:
                await aiosmtplib.send(
                    msg,
                    hostname=settings["mail_server"],
                    port=int(settings.get("mail_port", 587)),
                    username=settings["mail_username"],
                    password=settings["mail_password"],
                    start_tls=int(settings.get("mail_port", 587)) == 587,
                )
            except Exception as e:
                print(f"Calendar invite failed for {participant.email}: {e}")
    finally:
        await engine.dispose()


@celery_app.task
def send_magic_link_email(email: str, token: str):
    settings = _get_smtp_settings()
    base_url = settings.get("frontend_url", "http://localhost:5173").rstrip("/")
    magic_link = f"{base_url}/login?token={token}"
    subject = "Dein Anmelde-Link für EventFinder"
    body = (
        f"Klicke auf den folgenden Link, um dich bei EventFinder anzumelden:\n"
        f"{magic_link}\n\n"
        f"Der Link ist 30 Tage gültig und kann nur einmal verwendet werden.\n\n"
        f"Falls du keinen Anmelde-Link angefordert hast, kannst du diese E-Mail ignorieren."
    )
    return asyncio.run(_send_email(subject, email, body, settings))


@celery_app.task
def fetch_weather_history(event_id: str, lat: float, lon: float):
    """Fetches 20 years of ERA5 climate data and stores daily medians per grid point."""
    asyncio.run(_fetch_weather_history_async(lat, lon))


async def _fetch_weather_history_async(lat: float, lon: float):
    import sys
    import httpx
    import statistics
    from collections import defaultdict
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select, text

    # Ensure the app directory is on sys.path so 'models' can be imported
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    import models

    lat_grid = round(lat * 4) / 4
    lon_grid = round(lon * 4) / 4

    engine = create_async_engine(os.getenv("DATABASE_URL"), echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Skip if data already exists for this grid point
    async with async_session() as session:
        result = await session.execute(
            select(models.WeatherHistory)
            .where(models.WeatherHistory.lat_grid == lat_grid)
            .where(models.WeatherHistory.lon_grid == lon_grid)
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing and existing.sample_years and existing.sample_years >= 10:
            print(f"Weather history already complete for {lat_grid},{lon_grid}")
            await engine.dispose()
            return

    # Fetch 20 years from Open-Meteo ERA5 Archive (single API call)
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat_grid,
        "longitude": lon_grid,
        "start_date": "2005-01-01",
        "end_date": "2024-12-31",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "Europe/Berlin",
    }
    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        print(f"Weather archive fetch failed for {lat_grid},{lon_grid}: {e}")
        await engine.dispose()
        return

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    temp_max_list = daily.get("temperature_2m_max", [])
    temp_min_list = daily.get("temperature_2m_min", [])
    precip_list = daily.get("precipitation_sum", [])

    # Aggregate by (month, day)
    buckets: dict = defaultdict(lambda: {"temp_max": [], "temp_min": [], "precip": []})
    for i, d in enumerate(dates):
        try:
            parts = d.split("-")
            month, day = int(parts[1]), int(parts[2])
            if i < len(temp_max_list) and temp_max_list[i] is not None:
                buckets[(month, day)]["temp_max"].append(temp_max_list[i])
            if i < len(temp_min_list) and temp_min_list[i] is not None:
                buckets[(month, day)]["temp_min"].append(temp_min_list[i])
            if i < len(precip_list) and precip_list[i] is not None:
                buckets[(month, day)]["precip"].append(precip_list[i])
        except (IndexError, ValueError):
            continue

    if not buckets:
        print(f"No weather data received for {lat_grid},{lon_grid}")
        await engine.dispose()
        return

    # UPSERT medians using raw SQL (avoid dialect-specific imports)
    async with async_session() as session:
        for (month, day), vals in buckets.items():
            if not vals["temp_max"]:
                continue
            tmax = round(statistics.median(vals["temp_max"]), 1)
            tmin = round(statistics.median(vals["temp_min"]), 1) if vals["temp_min"] else None
            prec = round(statistics.median(vals["precip"]), 1) if vals["precip"] else None
            years = max(1, len(vals["temp_max"]) // 30)
            await session.execute(text("""
                INSERT INTO weather_history (lat_grid, lon_grid, month, day, temp_max_median, temp_min_median, precip_median, sample_years, updated_at)
                VALUES (:lat_grid, :lon_grid, :month, :day, :tmax, :tmin, :prec, :years, NOW())
                ON CONFLICT ON CONSTRAINT uq_weather_grid_day
                DO UPDATE SET temp_max_median=:tmax, temp_min_median=:tmin, precip_median=:prec, sample_years=:years, updated_at=NOW()
            """), {"lat_grid": lat_grid, "lon_grid": lon_grid, "month": month, "day": day,
                   "tmax": tmax, "tmin": tmin, "prec": prec, "years": years})
        await session.commit()

    await engine.dispose()
    print(f"Weather history stored for {lat_grid},{lon_grid}: {len(buckets)} day-buckets")


@celery_app.task
def send_calendar_subscription_emails(event_id: str):
    asyncio.run(_send_calendar_subscription_emails_async(event_id))


async def _send_calendar_subscription_emails_async(event_id: str):
    import sys
    import secrets as secrets_mod
    from urllib.parse import urlparse
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    import models
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select

    engine = create_async_engine(os.getenv("DATABASE_URL"), echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            event_result = await session.execute(
                select(models.Event).where(models.Event.id == uuid.UUID(event_id))
            )
            event = event_result.scalar_one_or_none()
            if not event:
                return

            parts_result = await session.execute(
                select(models.User)
                .join(models.EventParticipant, models.User.id == models.EventParticipant.user_id)
                .where(models.EventParticipant.event_id == event.id)
            )
            participants = parts_result.scalars().all()

            settings = _get_smtp_settings()
            base_url = settings.get("frontend_url", "http://localhost:5173").rstrip("/")
            webcal_host = urlparse(base_url).netloc

            for participant in participants:
                if not participant.calendar_token:
                    participant.calendar_token = secrets_mod.token_urlsafe(32)
                    await session.commit()
                    await session.refresh(participant)

                ics_path = f"/events/{event_id}/calendar.ics?token={participant.calendar_token}"
                webcal_url = f"webcal://{webcal_host}{ics_path}"
                https_url = f"{base_url}{ics_path}"

                body = (
                    f"Hallo {participant.name},\n\n"
                    f"Du kannst das Event \"{event.title}\" in deinen Kalender abonnieren.\n"
                    f"Der Kalender aktualisiert sich automatisch, wenn sich Termine aendern.\n\n"
                    f"Klicke hier, um das Abo in deiner Kalender-App zu oeffnen:\n"
                    f"{webcal_url}\n\n"
                    f"Oder trage diese URL manuell ein:\n"
                    f"{https_url}\n\n"
                    f"Anleitung:\n"
                    f"  Google Calendar: Andere Kalender -> Per URL hinzufuegen\n"
                    f"  Outlook: Kalender hinzufuegen -> Aus dem Internet abonnieren\n"
                    f"  Apple Calendar: Ablage -> Kalenderabonnement\n\n"
                    f"Wichtig: Dieser Link ist persoenlich - bitte nicht weitergeben.\n\n"
                    f"-- EventFinder"
                )
                await _send_email(
                    f"Kalender abonnieren: {event.title}",
                    participant.email,
                    body,
                    settings,
                )
    finally:
        await engine.dispose()
