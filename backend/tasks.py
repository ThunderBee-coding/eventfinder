import os
import asyncio
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
def send_invitation_email(recipient_email: str, inviter_name: str, event_title: str, token: str, event_id: str = ""):
    settings = _get_smtp_settings()
    base_url = settings.get("frontend_url", "http://localhost:5173").rstrip("/")
    magic_link = f"{base_url}/login?token={token}"
    if event_id:
        magic_link += f"&event={event_id}"
    subject = f"Einladung zum Event: {event_title}"
    body = (
        f"Hallo,\n\n"
        f"{inviter_name} hat dich zum Event \"{event_title}\" eingeladen.\n\n"
        f"Klicke auf den folgenden Link, um die Einladung anzunehmen:\n"
        f"{magic_link}\n\n"
        f"Du wirst direkt zum Event weitergeleitet, wo du deine Verfügbarkeit eintragen kannst.\n"
        f"Der Link ist 24 Stunden gültig und kann nur einmal verwendet werden.\n\n"
        f"Falls du diese Einladung nicht erwartet hast, kannst du diese E-Mail ignorieren."
    )
    return asyncio.run(_send_email(subject, recipient_email, body, settings))


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
