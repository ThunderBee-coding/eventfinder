from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from datetime import datetime
from typing import Any
import os
import uuid

import redis as redis_lib

from database import get_db
import models
from encryption import encrypt_value, decrypt_value
from api.events import get_current_user

router = APIRouter()

ENCRYPTED_KEYS = {"mail_password"}
REDIS_SETTINGS_KEY = "app:settings"


async def require_superadmin(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if current_user.role != models.UserRole.superadmin:
        raise HTTPException(status_code=403, detail="Superadmin erforderlich")
    return current_user


@router.get("/settings")
async def get_settings(
    _: models.User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.AppSetting))
    return {
        row.key: ("***" if row.is_encrypted else row.value)
        for row in result.scalars().all()
    }


@router.put("/settings")
async def put_settings(
    body: dict[str, Any],
    _: models.User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    for key, raw_value in body.items():
        value_str = str(raw_value)
        is_encrypted = key in ENCRYPTED_KEYS

        if key == "mail_password" and not value_str:
            continue  # Leeres Passwort = nicht überschreiben

        stored_value = encrypt_value(value_str) if is_encrypted else value_str

        stmt = pg_insert(models.AppSetting).values(
            key=key,
            value=stored_value,
            is_encrypted=is_encrypted,
            updated_at=datetime.utcnow(),
        ).on_conflict_do_update(
            index_elements=["key"],
            set_={
                "value": stored_value,
                "is_encrypted": is_encrypted,
                "updated_at": datetime.utcnow(),
            },
        )
        await db.execute(stmt)

    await db.commit()

    # Redis-Cache aus DB neu aufbauen
    result = await db.execute(select(models.AppSetting))
    redis_data: dict[str, str] = {}
    for row in result.scalars().all():
        plaintext = decrypt_value(row.value) if row.is_encrypted else row.value
        redis_data[row.key] = plaintext

    if redis_data:
        r = redis_lib.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
        try:
            r.hset(REDIS_SETTINGS_KEY, mapping=redis_data)
        finally:
            r.close()

    return {"ok": True}


@router.post("/settings/test-mail")
async def test_mail(
    _: models.User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    from aiosmtplib import send
    from email.message import EmailMessage

    result = await db.execute(select(models.AppSetting))
    rows = {
        row.key: (decrypt_value(row.value) if row.is_encrypted else row.value)
        for row in result.scalars().all()
    }

    required = ["mail_server", "mail_port", "mail_username", "mail_password", "mail_from"]
    missing = [k for k in required if k not in rows]
    if missing:
        return {"success": False, "error": f"Fehlende Einstellungen: {', '.join(missing)}"}

    msg = EmailMessage()
    msg["From"] = rows["mail_from"]
    msg["To"] = rows.get("mail_from") or rows["mail_username"]
    msg["Subject"] = "EventFinder Test-E-Mail"
    msg.set_content("Diese Test-E-Mail bestätigt, dass deine Mail-Konfiguration korrekt ist.")

    try:
        await send(
            msg,
            hostname=rows["mail_server"],
            port=int(rows["mail_port"]),
            username=rows["mail_username"],
            password=rows["mail_password"],
            start_tls=int(rows["mail_port"]) == 587,
        )
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/users")
async def get_all_users(
    _: models.User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.User)
        .where(models.User.role != models.UserRole.superadmin)
        .order_by(models.User.name)
    )
    return [{"id": str(u.id), "name": u.name, "email": u.email} for u in result.scalars().all()]


@router.get("/rotation")
async def get_rotation(
    _: models.User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.OrganizerRotation, models.User)
        .join(models.User, models.OrganizerRotation.user_id == models.User.id)
        .order_by(models.OrganizerRotation.order_index)
    )
    return [
        {
            "user_id": str(rot.user_id),
            "name": user.name,
            "email": user.email,
            "order_index": rot.order_index,
            "is_active": rot.is_active,
            "last_organized_at": rot.last_organized_at,
        }
        for rot, user in result.all()
    ]


@router.put("/rotation")
async def set_rotation(
    body: list[dict],
    _: models.User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(models.OrganizerRotation))
    for i, entry in enumerate(body):
        db.add(models.OrganizerRotation(
            user_id=uuid.UUID(entry["user_id"]),
            order_index=i,
            is_active=entry.get("is_active", True),
        ))
    await db.commit()
    return {"ok": True}
