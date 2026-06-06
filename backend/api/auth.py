from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
import secrets
import uuid
import json

from database import get_db
import models
import schemas
import auth
from tasks import send_magic_link_email

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/verify")

@router.post("/magic-link", status_code=status.HTTP_200_OK)
async def request_magic_link(request: schemas.MagicLinkRequest, db: AsyncSession = Depends(get_db)):
    # Check if user exists, if not create
    result = await db.execute(select(models.User).where(models.User.email == request.email))
    user = result.scalar_one_or_none()
    
    if not user:
        count_result = await db.execute(
            select(func.count()).select_from(models.User)
        )
        user_count = count_result.scalar() or 0
        role = models.UserRole.superadmin if user_count == 0 else models.UserRole.participant

        user = models.User(
            email=request.email,
            name=request.email.split("@")[0],
            role=role,
        )
        db.add(user)
        await db.flush()
    
    # Generate token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=30)
    
    magic_link = models.MagicLink(
        user_id=user.id,
        token=token,
        expires_at=expires_at
    )
    db.add(magic_link)
    await db.commit()
    
    # Send email asynchronously
    send_magic_link_email.delay(user.email, token)
    
    return {"message": "Magic link sent if email exists"}

@router.get("/magic")
async def magic_link_browser(token: str, db: AsyncSession = Depends(get_db)):
    """Browser-Endpoint für Magic-Links aus E-Mails.
    Verarbeitet das Token und antwortet mit einer HTML-Seite, die den JWT
    in localStorage speichert und zur App weiterleitet — kein Redirect,
    der durch Cloudflare Access-Redirect-URL-Validierung scheitern könnte.
    """
    result = await db.execute(
        select(models.MagicLink)
        .where(models.MagicLink.token == token)
        .where(models.MagicLink.is_used == False)
        .where(models.MagicLink.expires_at > datetime.utcnow())
    )
    magic_link = result.scalar_one_or_none()

    if not magic_link:
        return HTMLResponse("""
<!DOCTYPE html><html><head><meta charset="utf-8"><title>EventFinder</title></head>
<body style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:#080b14;font-family:system-ui;color:#fff;">
  <div style="text-align:center;">
    <div style="font-size:48px;margin-bottom:16px;">⚠️</div>
    <h2 style="margin-bottom:8px;">Link ungültig oder abgelaufen</h2>
    <p style="color:rgba(255,255,255,0.5);margin-bottom:24px;">Bitte fordere einen neuen Magic-Link an.</p>
    <a href="/login" style="color:#06b6d4;text-decoration:none;border:1px solid #06b6d444;padding:10px 20px;border-radius:10px;">Zur Anmeldung</a>
  </div>
</body></html>
""", status_code=400)

    magic_link.is_used = True
    magic_link.used_at = datetime.utcnow()

    result = await db.execute(select(models.User).where(models.User.id == magic_link.user_id))
    user = result.scalar_one()
    await db.commit()

    access_token = auth.create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})
    safe_token = json.dumps(access_token)

    return HTMLResponse(f"""
<!DOCTYPE html><html><head><meta charset="utf-8"><title>EventFinder – Anmelden…</title></head>
<body style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:#080b14;font-family:system-ui;color:#fff;">
  <div style="text-align:center;">
    <div style="font-size:48px;margin-bottom:16px;">🗓️</div>
    <p style="color:rgba(255,255,255,0.6);">Anmeldung läuft…</p>
  </div>
  <script>
    try {{
      localStorage.setItem('token', {safe_token});
      window.location.replace('/');
    }} catch(e) {{
      document.body.innerHTML = '<p style="color:#f43f5e;padding:24px;">Fehler: ' + e.message + '</p>';
    }}
  </script>
</body></html>
""")


@router.get("/verify", response_model=schemas.Token)
async def verify_magic_link(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.MagicLink)
        .where(models.MagicLink.token == token)
        .where(models.MagicLink.is_used == False)
        .where(models.MagicLink.expires_at > datetime.utcnow())
    )
    magic_link = result.scalar_one_or_none()
    
    if not magic_link:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    
    # Mark as used
    magic_link.is_used = True
    magic_link.used_at = datetime.utcnow()
    
    # Get user
    result = await db.execute(select(models.User).where(models.User.id == magic_link.user_id))
    user = result.scalar_one()
    
    await db.commit()
    
    # Create JWT
    access_token = auth.create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})

    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/calendar-token")
async def get_calendar_token(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    payload = auth.verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = payload.get("sub")
    result = await db.execute(select(models.User).where(models.User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.calendar_token:
        user.calendar_token = secrets.token_urlsafe(32)
        await db.commit()
        await db.refresh(user)

    return {"calendar_token": user.calendar_token}
