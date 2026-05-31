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
    r = redis_lib.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
    raw = r.hgetall("app:settings")
    if raw:
        return {k.decode(): v.decode() for k, v in raw.items()}
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
def send_magic_link_email(email: str, token: str):
    settings = _get_smtp_settings()
    frontend_url = settings.get("frontend_url", "http://localhost:5173")
    magic_link = f"{frontend_url}/login?token={token}"
    subject = "Dein Magic Link für EventFinder"
    body = (
        f"Klicke auf den folgenden Link, um dich anzumelden:\n"
        f"{magic_link}\n\n"
        f"Der Link ist 1 Stunde gültig."
    )
    return asyncio.run(_send_email(subject, email, body, settings))
