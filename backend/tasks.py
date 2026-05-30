import os
from celery import Celery
import asyncio
from aiosmtplib import send
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery(
    "tasks",
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL")
)

MAIL_SERVER = os.getenv("MAIL_SERVER")
MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM")

async def _send_email(subject: str, recipient: str, body: str):
    message = EmailMessage()
    message["From"] = MAIL_FROM
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    try:
        await send(
            message,
            hostname=MAIL_SERVER,
            port=MAIL_PORT,
            username=MAIL_USERNAME,
            password=MAIL_PASSWORD,
            start_tls=True if MAIL_PORT == 587 else False
        )
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

@celery_app.task
def send_magic_link_email(email: str, token: str):
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    magic_link = f"{frontend_url}/login?token={token}"
    subject = "Dein Magic Link für EventFinder"
    body = f"Klicke auf den folgenden Link, um dich anzumelden: {magic_link}\nDer Link ist 1 Stunde gültig."
    
    # Run async function in sync task
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(_send_email(subject, email, body))
