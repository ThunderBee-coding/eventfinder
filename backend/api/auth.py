from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
import secrets
import uuid

from database import get_db
import models
import schemas
import auth
from tasks import send_magic_link_email

router = APIRouter()

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
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
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
