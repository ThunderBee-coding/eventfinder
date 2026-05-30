# EventFinder Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vollständiges Dark-Mode-Redesign (Glassmorphismus, Neon-Glow, per-Event-Theming) plus fehlende Kernfunktionen: Cover-Upload, Teilnehmerverwaltung, Datumsvorschläge mit Abstimmung.

**Architecture:** FastAPI-Backend (async SQLAlchemy + Alembic) + Vue 3 Frontend (Composition API, Inline-Styles für Design-System). Neue Backend-Felder per Alembic-Migration, Cover-Bilder via Pillow verkleinert in Docker-Volume gespeichert. Frontend ohne externe Komponentenbibliothek — reines CSS via Inline-Styles und CSS-Variablen.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy asyncpg, Alembic, Pillow, Vue 3, Vite, TypeScript, Tailwind v4 (nur für Layout-Helfer), Docker Compose

---

## Datei-Übersicht

### Backend — neu/geändert
- `backend/requirements.txt` — Pillow hinzufügen
- `backend/models.py` — Event + DateProposal erweitern
- `backend/schemas.py` — neue Schemas: EventCreate, EventResponse, ParticipantResponse, DateProposalResponse
- `backend/migrations/versions/002_event_theming_proposals.py` — neue Migration
- `backend/api/events.py` — neue Endpoints: cover-upload, participants, proposals, patch
- `backend/main.py` — StaticFiles mount

### Docker
- `/docker/eventfinder/docker-compose.yml` — uploads-Volume hinzufügen

### Frontend — neu
- `frontend/src/composables/useAuth.ts`
- `frontend/src/components/EventHero.vue`
- `frontend/src/components/AvailabilityCalendar.vue`
- `frontend/src/components/DateProposals.vue`
- `frontend/src/components/ParticipantList.vue`
- `frontend/src/components/CreateEventModal.vue`
- `frontend/src/components/InviteModal.vue`

### Frontend — ersetzt
- `frontend/src/style.css` — CSS-Variablen
- `frontend/src/views/Login.vue` — Dark Redesign
- `frontend/src/views/Dashboard.vue` — Dark Redesign
- `frontend/src/views/EventDetails.vue` — Dark Redesign

### Frontend — gelöscht
- `frontend/src/views/Mockup.vue`
- `frontend/src/components/Calendar.vue`
- `frontend/src/components/HelloWorld.vue`

---

## Task 1: Backend — Pillow + Migration

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/migrations/versions/002_event_theming_proposals.py`

- [ ] **Schritt 1: Pillow zu requirements.txt hinzufügen**

```
# backend/requirements.txt — Zeile hinzufügen:
Pillow>=10.0.0
```

- [ ] **Schritt 2: Pillow im laufenden Container installieren**

```bash
docker exec eventfinder-backend pip install Pillow
```

Erwartete Ausgabe: `Successfully installed Pillow-...`

- [ ] **Schritt 3: Alembic-Migration erstellen**

Datei: `backend/migrations/versions/002_event_theming_proposals.py`

```python
"""Add event theming and date proposals

Revision ID: 002_event_theming
Revises: a4de437b52ec
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa

revision = '002_event_theming'
down_revision = 'a4de437b52ec'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('events', sa.Column('accent_color', sa.String(7), nullable=False, server_default='#06b6d4'))
    op.add_column('events', sa.Column('cover_image_path', sa.String(255), nullable=True))

    op.create_table(
        'date_proposals',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('proposed_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('event_id', 'proposed_date', name='uq_event_date_proposal'),
    )


def downgrade() -> None:
    op.drop_table('date_proposals')
    op.drop_column('events', 'cover_image_path')
    op.drop_column('events', 'accent_color')
```

- [ ] **Schritt 4: Migration ausführen**

```bash
docker exec eventfinder-backend alembic upgrade head
```

Erwartete Ausgabe: `Running upgrade a4de437b52ec -> 002_event_theming, Add event theming and date proposals`

- [ ] **Schritt 5: Verify**

```bash
docker exec eventfinder-db psql -U user -d eventfinder -c "\d events" | grep -E "accent|cover"
docker exec eventfinder-db psql -U user -d eventfinder -c "\dt date_proposals"
```

Erwartet: `accent_color` + `cover_image_path` in events-Tabelle, `date_proposals`-Tabelle existiert.

- [ ] **Schritt 6: Commit**

```bash
cd /root/eventfinder
git add backend/requirements.txt backend/migrations/versions/002_event_theming_proposals.py
git commit -m "feat: add event theming fields and date_proposals table migration"
```

---

## Task 2: Backend — Models + Schemas

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/schemas.py`

- [ ] **Schritt 1: DateProposal-Model zu models.py hinzufügen**

Am Ende von `backend/models.py` nach der `Notification`-Klasse einfügen:

```python
class DateProposal(Base):
    __tablename__ = "date_proposals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    proposed_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    event: Mapped["Event"] = relationship(back_populates="proposals")

    __table_args__ = (UniqueConstraint("event_id", "proposed_date", name="uq_event_date_proposal"),)
```

- [ ] **Schritt 2: Event-Model um neue Felder + Relationship erweitern**

In `backend/models.py`, Klasse `Event`, nach `updated_at` einfügen:

```python
    accent_color: Mapped[str] = mapped_column(String(7), default='#06b6d4')
    cover_image_path: Mapped[Optional[str]] = mapped_column(String(255))
```

Und nach `participants: Mapped[...]` die Relationship:

```python
    proposals: Mapped[List["DateProposal"]] = relationship(back_populates="event", cascade="all, delete-orphan")
```

- [ ] **Schritt 3: Schemas aktualisieren**

`backend/schemas.py` — bestehende Klassen ersetzen/erweitern:

```python
from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from typing import List, Optional
import uuid
from models import UserRole, AvailabilityStatus

class UserBase(BaseModel):
    email: EmailStr
    name: str
    bundesland: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: uuid.UUID
    role: UserRole
    is_owner: bool
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

class MagicLinkRequest(BaseModel):
    email: EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str

class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    location_name: Optional[str] = None
    accent_color: str = '#06b6d4'

class EventCreate(EventBase):
    proposed_dates: List[date] = []

class EventPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location_name: Optional[str] = None
    accent_color: Optional[str] = None
    final_date: Optional[date] = None
    is_closed: Optional[bool] = None

class EventResponse(EventBase):
    id: uuid.UUID
    organizer_id: uuid.UUID
    final_date: Optional[date] = None
    is_closed: bool
    cover_image_path: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class ParticipantResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    joined_at: datetime
    availability_count: int
    class Config:
        from_attributes = True

class DateProposalResponse(BaseModel):
    id: uuid.UUID
    proposed_date: date
    class Config:
        from_attributes = True

class DateProposalsSet(BaseModel):
    dates: List[date]

class AvailabilityBase(BaseModel):
    event_date: date
    status: AvailabilityStatus
    comment: Optional[str] = None

class AvailabilityResponse(AvailabilityBase):
    id: uuid.UUID
    participant_id: uuid.UUID
    class Config:
        from_attributes = True
```

- [ ] **Schritt 4: Backend neu starten und auf Fehler prüfen**

```bash
docker restart eventfinder-backend && sleep 4
docker logs eventfinder-backend 2>&1 | tail -5
```

Erwartet: `Application startup complete.` — kein Traceback.

- [ ] **Schritt 5: Commit**

```bash
cd /root/eventfinder
git add backend/models.py backend/schemas.py
git commit -m "feat: add DateProposal model, extend Event model, update schemas"
```

---

## Task 3: Backend — Neue Endpoints

**Files:**
- Modify: `backend/api/events.py`
- Modify: `backend/main.py`
- Modify: `/docker/eventfinder/docker-compose.yml`

- [ ] **Schritt 1: uploads-Verzeichnis + docker-compose Volume ergänzen**

In `/docker/eventfinder/docker-compose.yml`:

Unter `services.backend.volumes` hinzufügen:
```yaml
      - eventfinder-uploads:/app/uploads
```

Unter `volumes:` am Ende hinzufügen:
```yaml
  eventfinder-uploads:
```

- [ ] **Schritt 2: StaticFiles in main.py mounten**

`backend/main.py` — nach den Imports, vor `app = FastAPI(...)`:

```python
import os
from fastapi.staticfiles import StaticFiles
```

Nach `app.include_router(...)` Zeilen am Ende hinzufügen:

```python
os.makedirs("/app/uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="/app/uploads"), name="uploads")
```

- [ ] **Schritt 3: api/events.py vollständig ersetzen**

```python
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from datetime import date, datetime
import uuid
import os

from database import get_db
import models
import schemas
import auth
from fastapi.security import OAuth2PasswordBearer

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/verify")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


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


# ── CREATE ──────────────────────────────────────────────────────────────
@router.post("/", response_model=schemas.EventResponse)
async def create_event(
    event_in: schemas.EventCreate,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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


# ── LIST ─────────────────────────────────────────────────────────────────
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


# ── GET ──────────────────────────────────────────────────────────────────
@router.get("/{event_id}", response_model=schemas.EventResponse)
async def get_event(
    event_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_event_as_participant(event_id, current_user, db)


# ── PATCH ────────────────────────────────────────────────────────────────
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
    for field, value in patch.model_dump(exclude_none=True).items():
        setattr(event, field, value)
    await db.commit()
    await db.refresh(event)
    return event


# ── COVER UPLOAD ─────────────────────────────────────────────────────────
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

    # Delete old cover if exists
    if event.cover_image_path:
        old = f"/app/{event.cover_image_path}"
        if os.path.exists(old):
            os.remove(old)

    img.save(path, quality=85, optimize=True)
    event.cover_image_path = f"uploads/{filename}"
    await db.commit()
    await db.refresh(event)
    return event


# ── DELETE COVER ─────────────────────────────────────────────────────────
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


# ── PARTICIPANTS ──────────────────────────────────────────────────────────
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
            models.User.name,
            models.User.email,
            models.EventParticipant.joined_at,
            func.count(models.Availability.id).label("availability_count"),
        )
        .join(models.EventParticipant, models.EventParticipant.user_id == models.User.id)
        .outerjoin(models.Availability, models.Availability.participant_id == models.EventParticipant.id)
        .where(models.EventParticipant.event_id == event_id)
        .group_by(models.User.id, models.User.name, models.User.email, models.EventParticipant.joined_at)
    )
    rows = result.all()
    return [
        schemas.ParticipantResponse(
            id=r.id, name=r.name, email=r.email,
            joined_at=r.joined_at, availability_count=r.availability_count
        )
        for r in rows
    ]


# ── INVITE ───────────────────────────────────────────────────────────────
@router.post("/{event_id}/invite", status_code=200)
async def invite_participant(
    event_id: uuid.UUID,
    email: str,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await _get_event_as_participant(event_id, current_user, db)
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can invite participants")

    result = await db.execute(select(models.User).where(models.User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        user = models.User(
            id=uuid.uuid4(), email=email, name=email.split("@")[0],
            is_owner=False, is_active=True, created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        )
        db.add(user)
        await db.flush()

    result = await db.execute(
        select(models.EventParticipant)
        .where(models.EventParticipant.event_id == event_id)
        .where(models.EventParticipant.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        db.add(models.EventParticipant(event_id=event_id, user_id=user.id))

    await db.commit()
    return {"message": f"{email} eingeladen"}


# ── DATE PROPOSALS ────────────────────────────────────────────────────────
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

    # Delete existing
    existing = await db.execute(
        select(models.DateProposal).where(models.DateProposal.event_id == event_id)
    )
    for p in existing.scalars().all():
        await db.delete(p)

    new_proposals = [
        models.DateProposal(id=uuid.uuid4(), event_id=event_id, proposed_date=d)
        for d in body.dates
    ]
    db.add_all(new_proposals)
    await db.commit()
    return new_proposals
```

- [ ] **Schritt 4: docker-compose neu starten mit neuem Volume**

```bash
cd /docker/eventfinder && docker-compose up -d
sleep 5
docker logs eventfinder-backend 2>&1 | tail -5
```

Erwartet: `Application startup complete.`

- [ ] **Schritt 5: Endpoints manuell testen**

```bash
# Uploads-Verzeichnis existiert im Container
docker exec eventfinder-backend ls /app/uploads || echo "leer aber existiert"

# StaticFiles erreichbar
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/uploads/
# Erwartet: 404 (korrekt — kein File angefragt, aber Route existiert)
```

- [ ] **Schritt 6: Commit**

```bash
cd /root/eventfinder
git add backend/api/events.py backend/main.py /docker/eventfinder/docker-compose.yml
git commit -m "feat: cover upload, participants, proposals, patch endpoints"
```

---

## Task 4: Frontend — useAuth + CSS-Variablen

**Files:**
- Create: `frontend/src/composables/useAuth.ts`
- Modify: `frontend/src/style.css`

- [ ] **Schritt 1: useAuth.ts erstellen**

```typescript
// frontend/src/composables/useAuth.ts
import axios from 'axios'
import { useRouter } from 'vue-router'

export function useAuth() {
  const router = useRouter()

  const token = () => localStorage.getItem('token') ?? ''

  const headers = () => ({ Authorization: `Bearer ${token()}` })

  const logout = () => {
    localStorage.removeItem('token')
    router.push('/login')
  }

  // Intercept 401 responses globally
  axios.interceptors.response.use(
    res => res,
    err => {
      if (err.response?.status === 401) logout()
      return Promise.reject(err)
    }
  )

  return { token, headers, logout }
}
```

- [ ] **Schritt 2: CSS-Variablen in style.css setzen**

`frontend/src/style.css` — vollständig ersetzen:

```css
@import "tailwindcss";

:root {
  --bg-base: #080b14;
  --bg-card: #0d1117;
  --bg-surface: rgba(255, 255, 255, 0.04);
  --border: rgba(255, 255, 255, 0.07);
  --border-hover: rgba(255, 255, 255, 0.18);
  --text-primary: #ffffff;
  --text-secondary: rgba(255, 255, 255, 0.45);
  --text-muted: rgba(255, 255, 255, 0.22);
  --accent: #06b6d4;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  background: var(--bg-base);
  color: var(--text-primary);
  font-family: system-ui, -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
}

input, textarea, select, button {
  font-family: inherit;
}

/* Scrollbar dark */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg-base); }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 3px; }
```

- [ ] **Schritt 3: Vite-Proxy auf korrekte Container-Namen prüfen**

`frontend/vite.config.ts` — sicherstellen dass Proxy so aussieht:

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    allowedHosts: ['eventfinder.thunderbee.uk'],
    host: true,
    proxy: {
      '/auth': { target: 'http://backend:8000', changeOrigin: true },
      '/events': { target: 'http://backend:8000', changeOrigin: true },
      '/uploads': { target: 'http://backend:8000', changeOrigin: true },
    },
  },
})
```

- [ ] **Schritt 4: Commit**

```bash
cd /root/eventfinder
git add frontend/src/composables/useAuth.ts frontend/src/style.css frontend/vite.config.ts
git commit -m "feat: useAuth composable, CSS variables, proxy for uploads"
```

---

## Task 5: Komponente — EventHero.vue

**Files:**
- Create: `frontend/src/components/EventHero.vue`

- [ ] **Schritt 1: EventHero.vue erstellen**

```vue
<!-- frontend/src/components/EventHero.vue -->
<script setup lang="ts">
defineProps<{
  title: string
  description?: string
  locationName?: string
  accentColor: string
  coverImagePath?: string
  participantCount?: number
  isOrganizer?: boolean
}>()

const emit = defineEmits<{
  invite: []
  editCover: []
}>()
</script>

<template>
  <div :style="{
    position: 'relative',
    borderRadius: '20px',
    overflow: 'hidden',
    height: '220px',
    boxShadow: `0 20px 60px ${accentColor}33`,
  }">
    <!-- Cover image or gradient background -->
    <img v-if="coverImagePath"
      :src="`/${coverImagePath}`"
      style="position:absolute; inset:0; width:100%; height:100%; object-fit:cover;"
    />
    <div v-else :style="{
      position: 'absolute', inset: 0,
      background: `linear-gradient(135deg, ${accentColor}22 0%, #080b14 100%)`,
    }" />

    <!-- Dark overlay -->
    <div style="position:absolute; inset:0; background:linear-gradient(to top, rgba(8,11,20,0.95) 0%, rgba(8,11,20,0.4) 100%);" />

    <!-- Accent bottom line -->
    <div :style="{
      position: 'absolute', bottom: 0, left: 0, right: 0, height: '1px',
      background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)`,
    }" />

    <!-- Content -->
    <div style="position:absolute; inset:0; padding:28px 32px; display:flex; flex-direction:column; justify-content:flex-end;">
      <div style="display:flex; align-items:flex-end; justify-content:space-between; gap:16px;">
        <div style="flex:1; min-width:0;">
          <p v-if="locationName" style="font-size:13px; color:rgba(255,255,255,0.45); margin-bottom:6px; display:flex; align-items:center; gap:6px;">
            📍 {{ locationName }}
          </p>
          <h1 style="font-size:26px; font-weight:700; letter-spacing:-0.5px; margin-bottom:8px; line-height:1.2;">
            {{ title }}
          </h1>
          <p v-if="description" style="font-size:14px; color:rgba(255,255,255,0.5); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
            {{ description }}
          </p>
          <p v-if="participantCount !== undefined" style="font-size:13px; color:rgba(255,255,255,0.35); margin-top:8px;">
            👥 {{ participantCount }} Teilnehmer
          </p>
        </div>
        <div v-if="isOrganizer" style="display:flex; flex-direction:column; gap:8px; flex-shrink:0;">
          <button @click="emit('invite')"
            :style="{
              background: accentColor,
              boxShadow: `0 0 20px ${accentColor}66`,
              color: '#000', padding: '9px 16px',
              borderRadius: '10px', border: 'none', cursor: 'pointer',
              fontWeight: 600, fontSize: '13px', whiteSpace: 'nowrap',
            }">
            + Einladen
          </button>
          <button @click="emit('editCover')"
            style="background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.7); padding:9px 16px; border-radius:10px; cursor:pointer; font-size:13px; font-weight:500;">
            🖼 Cover
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Schritt 2: Commit**

```bash
cd /root/eventfinder
git add frontend/src/components/EventHero.vue
git commit -m "feat: EventHero component with cover image or accent gradient"
```

---

## Task 6: Komponente — AvailabilityCalendar.vue

**Files:**
- Create: `frontend/src/components/AvailabilityCalendar.vue`

- [ ] **Schritt 1: AvailabilityCalendar.vue erstellen**

```vue
<!-- frontend/src/components/AvailabilityCalendar.vue -->
<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  proposedDates: string[]          // ISO date strings the organizer proposed
  availabilities: Array<{          // all participants' availabilities
    event_date: string
    status: 'best' | 'possible' | 'impossible'
    own?: boolean                  // true = belongs to current user
  }>
  participantCount: number
  accentColor: string
  isOrganizer?: boolean
  finalDate?: string
}>()

const emit = defineEmits<{
  dateClick: [date: string]
  setFinalDate: [date: string]
}>()

const today = new Date()
const currentYear = ref(today.getFullYear())
const currentMonth = ref(today.getMonth()) // 0-based

const monthName = computed(() => new Date(currentYear.value, currentMonth.value).toLocaleString('de-DE', { month: 'long', year: 'numeric' }))

const daysInMonth = computed(() => new Date(currentYear.value, currentMonth.value + 1, 0).getDate())

const firstDayOffset = computed(() => {
  const d = new Date(currentYear.value, currentMonth.value, 1).getDay()
  return d === 0 ? 6 : d - 1 // Mon=0
})

function isoDate(day: number) {
  const m = String(currentMonth.value + 1).padStart(2, '0')
  const d = String(day).padStart(2, '0')
  return `${currentYear.value}-${m}-${d}`
}

function isProposed(day: number) {
  return props.proposedDates.includes(isoDate(day))
}

function scoreForDay(day: number): 'best' | 'possible' | 'impossible' | null {
  const iso = isoDate(day)
  const avails = props.availabilities.filter(a => a.event_date === iso)
  if (avails.length === 0) return null
  const bestCount = avails.filter(a => a.status === 'best').length
  const impossibleCount = avails.filter(a => a.status === 'impossible').length
  if (impossibleCount > props.participantCount / 2) return 'impossible'
  if (bestCount >= props.participantCount / 2) return 'best'
  return 'possible'
}

function ownStatusForDay(day: number) {
  return props.availabilities.find(a => a.event_date === isoDate(day) && a.own)?.status
}

function dayBg(day: number) {
  const iso = isoDate(day)
  if (props.finalDate === iso) return props.accentColor
  if (!isProposed(day)) return 'transparent'
  const score = scoreForDay(day)
  if (score === 'best') return 'rgba(16,185,129,0.2)'
  if (score === 'possible') return 'rgba(245,158,11,0.18)'
  if (score === 'impossible') return 'rgba(244,63,94,0.18)'
  return 'rgba(255,255,255,0.05)'
}

function dayColor(day: number) {
  const iso = isoDate(day)
  if (props.finalDate === iso) return '#000'
  if (!isProposed(day)) return 'rgba(255,255,255,0.2)'
  const score = scoreForDay(day)
  if (score === 'best') return '#10b981'
  if (score === 'possible') return '#f59e0b'
  if (score === 'impossible') return '#f43f5e'
  return 'rgba(255,255,255,0.5)'
}

function prevMonth() {
  if (currentMonth.value === 0) { currentMonth.value = 11; currentYear.value-- }
  else currentMonth.value--
}
function nextMonth() {
  if (currentMonth.value === 11) { currentMonth.value = 0; currentYear.value++ }
  else currentMonth.value++
}
</script>

<template>
  <div>
    <!-- Month navigation -->
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px;">
      <span style="font-weight:600; font-size:16px; text-transform:capitalize;">{{ monthName }}</span>
      <div style="display:flex; gap:6px;">
        <button @click="prevMonth"
          style="background:rgba(255,255,255,0.06); border:none; color:#fff; width:30px; height:30px; border-radius:8px; cursor:pointer; font-size:16px;">‹</button>
        <button @click="nextMonth"
          style="background:rgba(255,255,255,0.06); border:none; color:#fff; width:30px; height:30px; border-radius:8px; cursor:pointer; font-size:16px;">›</button>
      </div>
    </div>

    <!-- Weekday headers -->
    <div style="display:grid; grid-template-columns:repeat(7,1fr); gap:4px; margin-bottom:6px;">
      <span v-for="d in ['Mo','Di','Mi','Do','Fr','Sa','So']" :key="d"
        style="text-align:center; font-size:11px; color:rgba(255,255,255,0.3); padding:4px 0;">{{ d }}</span>
    </div>

    <!-- Days -->
    <div style="display:grid; grid-template-columns:repeat(7,1fr); gap:4px;">
      <div v-for="i in firstDayOffset" :key="'e'+i" />
      <div v-for="day in daysInMonth" :key="day"
        :style="{
          height: '38px', borderRadius: '8px',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '13px', fontWeight: isProposed(day) ? 600 : 400,
          background: dayBg(day),
          color: dayColor(day),
          cursor: isProposed(day) ? 'pointer' : 'default',
          boxShadow: finalDate === isoDate(day) ? `0 0 14px ${accentColor}99` : 'none',
          border: ownStatusForDay(day) ? `1px solid ${accentColor}66` : '1px solid transparent',
          transition: 'all .15s',
          position: 'relative',
        }"
        @click="isProposed(day) && emit('dateClick', isoDate(day))">
        {{ day }}
        <span v-if="finalDate === isoDate(day)"
          style="position:absolute; bottom:2px; font-size:8px; opacity:0.7;">✓</span>
      </div>
    </div>

    <!-- Legend -->
    <div style="display:flex; gap:16px; margin-top:16px; flex-wrap:wrap;">
      <span style="display:flex; align-items:center; gap:6px; font-size:12px; color:rgba(255,255,255,0.4);">
        <span style="width:10px; height:10px; border-radius:50%; background:#10b981; display:inline-block;"/> Mehrheit: gut
      </span>
      <span style="display:flex; align-items:center; gap:6px; font-size:12px; color:rgba(255,255,255,0.4);">
        <span style="width:10px; height:10px; border-radius:50%; background:#f59e0b; display:inline-block;"/> Möglich
      </span>
      <span style="display:flex; align-items:center; gap:6px; font-size:12px; color:rgba(255,255,255,0.4);">
        <span style="width:10px; height:10px; border-radius:50%; background:#f43f5e; display:inline-block;"/> Kaum möglich
      </span>
    </div>
  </div>
</template>
```

- [ ] **Schritt 2: Commit**

```bash
cd /root/eventfinder
git add frontend/src/components/AvailabilityCalendar.vue
git commit -m "feat: AvailabilityCalendar with heatmap and proposed-dates logic"
```

---

## Task 7: Komponenten — DateProposals + ParticipantList

**Files:**
- Create: `frontend/src/components/DateProposals.vue`
- Create: `frontend/src/components/ParticipantList.vue`

- [ ] **Schritt 1: DateProposals.vue erstellen**

```vue
<!-- frontend/src/components/DateProposals.vue -->
<script setup lang="ts">
defineProps<{
  proposals: Array<{ id: string; proposed_date: string }>
  availabilities: Array<{ event_date: string; status: string }>
  participantCount: number
  accentColor: string
  finalDate?: string
}>()

const emit = defineEmits<{ setFinal: [date: string] }>()

function scoreColor(date: string, avails: Array<{event_date:string; status:string}>, total: number) {
  const dayAvails = avails.filter(a => a.event_date === date)
  const best = dayAvails.filter(a => a.status === 'best').length
  const impossible = dayAvails.filter(a => a.status === 'impossible').length
  if (impossible > total / 2) return '#f43f5e'
  if (best >= total / 2) return '#10b981'
  if (dayAvails.length > 0) return '#f59e0b'
  return 'rgba(255,255,255,0.2)'
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'short' })
}
</script>

<template>
  <div>
    <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; margin-bottom:14px;">
      Datumsvorschläge
    </p>
    <div v-if="proposals.length === 0" style="color:rgba(255,255,255,0.25); font-size:13px;">
      Noch keine Vorschläge.
    </div>
    <div v-for="p in proposals" :key="p.id"
      style="display:flex; align-items:center; justify-content:space-between; padding:10px 12px; border-radius:10px; margin-bottom:6px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.07);">
      <div style="display:flex; align-items:center; gap:10px;">
        <span :style="{ width:'10px', height:'10px', borderRadius:'50%', background: scoreColor(p.proposed_date, availabilities, participantCount), display:'inline-block', flexShrink:0 }" />
        <span style="font-size:14px; font-weight:500;">{{ formatDate(p.proposed_date) }}</span>
      </div>
      <div style="display:flex; align-items:center; gap:8px;">
        <span v-if="finalDate === p.proposed_date"
          :style="{ fontSize:'11px', color: accentColor, fontWeight:600 }">✓ Finaldatum</span>
        <button v-else @click="emit('setFinal', p.proposed_date)"
          style="font-size:11px; color:rgba(255,255,255,0.35); background:transparent; border:1px solid rgba(255,255,255,0.1); padding:3px 8px; border-radius:6px; cursor:pointer;">
          Als Final setzen
        </button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Schritt 2: ParticipantList.vue erstellen**

```vue
<!-- frontend/src/components/ParticipantList.vue -->
<script setup lang="ts">
defineProps<{
  participants: Array<{
    id: string; name: string; email: string
    joined_at: string; availability_count: number
  }>
  accentColor: string
  totalProposals: number
}>()

const emit = defineEmits<{ invite: [] }>()

function initials(name: string) {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}
</script>

<template>
  <div>
    <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; margin-bottom:14px;">
      Teilnehmer ({{ participants.length }})
    </p>
    <div v-for="p in participants" :key="p.id"
      style="display:flex; align-items:center; justify-content:space-between; padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.05);">
      <div style="display:flex; align-items:center; gap:10px;">
        <div :style="{
          width:'32px', height:'32px', borderRadius:'50%', display:'flex',
          alignItems:'center', justifyContent:'center', fontSize:'12px', fontWeight:700,
          background: accentColor, color:'#000', flexShrink:0,
        }">{{ initials(p.name) }}</div>
        <div>
          <p style="font-size:14px; font-weight:500; margin-bottom:1px;">{{ p.name }}</p>
          <p style="font-size:11px; color:rgba(255,255,255,0.3);">{{ p.email }}</p>
        </div>
      </div>
      <span :style="{
        fontSize:'12px',
        color: p.availability_count >= totalProposals ? '#10b981' : p.availability_count > 0 ? '#f59e0b' : 'rgba(255,255,255,0.3)',
      }">
        {{ p.availability_count >= totalProposals ? 'Vollständig' : p.availability_count > 0 ? `${p.availability_count}/${totalProposals}` : 'Ausstehend' }}
      </span>
    </div>
    <button @click="emit('invite')"
      style="margin-top:14px; width:100%; padding:9px; border-radius:10px; background:transparent; border:1.5px dashed rgba(255,255,255,0.12); color:rgba(255,255,255,0.35); font-size:13px; cursor:pointer; transition:all .2s;"
      @mouseenter="e => { (e.currentTarget as HTMLElement).style.borderColor='rgba(255,255,255,0.3)'; (e.currentTarget as HTMLElement).style.color='rgba(255,255,255,0.6)' }"
      @mouseleave="e => { (e.currentTarget as HTMLElement).style.borderColor='rgba(255,255,255,0.12)'; (e.currentTarget as HTMLElement).style.color='rgba(255,255,255,0.35)' }">
      + Teilnehmer einladen
    </button>
  </div>
</template>
```

- [ ] **Schritt 3: Commit**

```bash
cd /root/eventfinder
git add frontend/src/components/DateProposals.vue frontend/src/components/ParticipantList.vue
git commit -m "feat: DateProposals and ParticipantList components"
```

---

## Task 8: Modals — CreateEventModal + InviteModal

**Files:**
- Create: `frontend/src/components/CreateEventModal.vue`
- Create: `frontend/src/components/InviteModal.vue`

- [ ] **Schritt 1: CreateEventModal.vue erstellen**

```vue
<!-- frontend/src/components/CreateEventModal.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'

const emit = defineEmits<{ close: []; created: [id: string] }>()
const { headers } = useAuth()

const ACCENTS = ['#06b6d4','#8b5cf6','#f43f5e','#f59e0b','#10b981']

const form = ref({
  title: '', description: '', location_name: '', accent_color: '#06b6d4',
})
const proposedDates = ref<string[]>([''])
const coverFile = ref<File | null>(null)
const coverPreview = ref('')
const loading = ref(false)
const error = ref('')

function addDate() { if (proposedDates.value.length < 5) proposedDates.value.push('') }
function removeDate(i: number) { proposedDates.value.splice(i, 1) }

function onFileChange(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (!f) return
  if (f.size > 5 * 1024 * 1024) { error.value = 'Bild darf max. 5 MB groß sein'; return }
  coverFile.value = f
  coverPreview.value = URL.createObjectURL(f)
}

async function submit() {
  error.value = ''
  if (!form.value.title.trim()) { error.value = 'Titel ist erforderlich'; return }
  const validDates = proposedDates.value.filter(d => d)
  if (validDates.length === 0) { error.value = 'Mindestens ein Datumsvorschlag erforderlich'; return }

  loading.value = true
  try {
    const res = await axios.post('/events/', {
      ...form.value,
      proposed_dates: validDates,
    }, { headers: headers() })

    if (coverFile.value) {
      const fd = new FormData()
      fd.append('file', coverFile.value)
      await axios.post(`/events/${res.data.id}/cover`, fd, { headers: { ...headers(), 'Content-Type': 'multipart/form-data' } })
    }

    emit('created', res.data.id)
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? 'Fehler beim Erstellen'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="position:fixed; inset:0; background:rgba(0,0,0,0.7); display:flex; align-items:center; justify-content:center; padding:16px; z-index:100; backdrop-filter:blur(4px);"
    @click.self="emit('close')">
    <div style="background:#0d1117; border:1px solid rgba(255,255,255,0.1); border-radius:20px; padding:32px; width:100%; max-width:520px; max-height:90vh; overflow-y:auto;">
      <h2 style="font-size:20px; font-weight:700; margin-bottom:24px;">Neues Event erstellen</h2>

      <div style="display:flex; flex-direction:column; gap:16px;">
        <!-- Titel -->
        <div>
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">Titel *</label>
          <input v-model="form.title" placeholder="z.B. Sommerfest 🌞"
            style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none;" />
        </div>

        <!-- Beschreibung -->
        <div>
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">Beschreibung</label>
          <textarea v-model="form.description" rows="2" placeholder="Worum geht es?"
            style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none; resize:none;" />
        </div>

        <!-- Ort -->
        <div>
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">Ort</label>
          <input v-model="form.location_name" placeholder="z.B. München, Olympiastadion"
            style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none;" />
        </div>

        <!-- Akzentfarbe -->
        <div>
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:8px;">Akzentfarbe</label>
          <div style="display:flex; gap:10px;">
            <button v-for="c in ACCENTS" :key="c"
              @click="form.accent_color = c"
              :style="{
                width:'28px', height:'28px', borderRadius:'50%', border:'none', cursor:'pointer',
                background: c,
                boxShadow: form.accent_color === c ? `0 0 14px ${c}` : 'none',
                transform: form.accent_color === c ? 'scale(1.25)' : 'scale(1)',
                transition:'all .2s',
              }" />
          </div>
        </div>

        <!-- Datumsvorschläge -->
        <div>
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:8px;">Datumsvorschläge * (1–5)</label>
          <div v-for="(d, i) in proposedDates" :key="i" style="display:flex; gap:8px; margin-bottom:8px;">
            <input type="date" v-model="proposedDates[i]"
              style="flex:1; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:9px 12px; color:#fff; font-size:14px; outline:none; color-scheme:dark;" />
            <button v-if="proposedDates.length > 1" @click="removeDate(i)"
              style="background:rgba(244,63,94,0.15); border:1px solid rgba(244,63,94,0.3); color:#f43f5e; width:36px; border-radius:8px; cursor:pointer; font-size:16px;">×</button>
          </div>
          <button v-if="proposedDates.length < 5" @click="addDate"
            style="font-size:13px; color:rgba(255,255,255,0.4); background:transparent; border:1px dashed rgba(255,255,255,0.15); padding:7px 14px; border-radius:8px; cursor:pointer;">
            + Datum hinzufügen
          </button>
        </div>

        <!-- Cover Bild -->
        <div>
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:8px;">Cover-Bild (optional, max 5 MB)</label>
          <div v-if="coverPreview" style="margin-bottom:8px;">
            <img :src="coverPreview" style="width:100%; height:100px; object-fit:cover; border-radius:10px;" />
          </div>
          <input type="file" accept="image/jpeg,image/png,image/webp" @change="onFileChange"
            style="width:100%; background:rgba(255,255,255,0.04); border:1px dashed rgba(255,255,255,0.15); border-radius:10px; padding:10px; color:rgba(255,255,255,0.5); font-size:13px; cursor:pointer;" />
        </div>
      </div>

      <p v-if="error" style="color:#f43f5e; font-size:13px; margin-top:16px;">{{ error }}</p>

      <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:24px;">
        <button @click="emit('close')"
          style="padding:10px 20px; border-radius:10px; background:transparent; border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.6); cursor:pointer; font-size:14px;">
          Abbrechen
        </button>
        <button @click="submit" :disabled="loading"
          :style="{
            padding:'10px 24px', borderRadius:'10px', border:'none', cursor:'pointer',
            fontWeight:600, fontSize:'14px', color:'#000',
            background: form.accent_color,
            boxShadow: `0 0 20px ${form.accent_color}66`,
            opacity: loading ? 0.7 : 1,
          }">
          {{ loading ? 'Erstelle...' : 'Event erstellen' }}
        </button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Schritt 2: InviteModal.vue erstellen**

```vue
<!-- frontend/src/components/InviteModal.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'

const props = defineProps<{ eventId: string; accentColor: string }>()
const emit = defineEmits<{ close: []; invited: [] }>()
const { headers } = useAuth()

const email = ref('')
const loading = ref(false)
const error = ref('')
const success = ref('')

async function invite() {
  error.value = ''; success.value = ''
  if (!email.value.trim()) { error.value = 'E-Mail erforderlich'; return }
  loading.value = true
  try {
    await axios.post(`/events/${props.eventId}/invite?email=${encodeURIComponent(email.value)}`, {}, { headers: headers() })
    success.value = `${email.value} wurde eingeladen!`
    email.value = ''
    emit('invited')
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? 'Fehler beim Einladen'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="position:fixed; inset:0; background:rgba(0,0,0,0.7); display:flex; align-items:center; justify-content:center; padding:16px; z-index:100; backdrop-filter:blur(4px);"
    @click.self="emit('close')">
    <div style="background:#0d1117; border:1px solid rgba(255,255,255,0.1); border-radius:20px; padding:32px; width:100%; max-width:400px;">
      <h2 style="font-size:18px; font-weight:700; margin-bottom:20px;">Teilnehmer einladen</h2>

      <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">E-Mail-Adresse</label>
      <input v-model="email" type="email" placeholder="freund@beispiel.de"
        @keyup.enter="invite"
        style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.12); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none; margin-bottom:16px;" />

      <p v-if="error" style="color:#f43f5e; font-size:13px; margin-bottom:12px;">{{ error }}</p>
      <p v-if="success" style="color:#10b981; font-size:13px; margin-bottom:12px;">{{ success }}</p>

      <div style="display:flex; justify-content:flex-end; gap:10px;">
        <button @click="emit('close')"
          style="padding:10px 20px; border-radius:10px; background:transparent; border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.6); cursor:pointer; font-size:14px;">
          Schließen
        </button>
        <button @click="invite" :disabled="loading"
          :style="{
            padding:'10px 24px', borderRadius:'10px', border:'none', cursor:'pointer',
            fontWeight:600, fontSize:'14px', color:'#000', background: accentColor,
            opacity: loading ? 0.7 : 1,
          }">
          {{ loading ? '...' : 'Einladen' }}
        </button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Schritt 3: Commit**

```bash
cd /root/eventfinder
git add frontend/src/components/CreateEventModal.vue frontend/src/components/InviteModal.vue
git commit -m "feat: CreateEventModal with color picker, cover upload, date proposals; InviteModal"
```

---

## Task 9: View — Login.vue

**Files:**
- Modify: `frontend/src/views/Login.vue`

- [ ] **Schritt 1: Login.vue vollständig ersetzen**

```vue
<!-- frontend/src/views/Login.vue -->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const email = ref('')
const loading = ref(false)
const message = ref('')
const error = ref('')
const route = useRoute()
const router = useRouter()

const requestMagicLink = async () => {
  loading.value = true; error.value = ''; message.value = ''
  try {
    await axios.post('/auth/magic-link', { email: email.value })
    message.value = 'Magic Link gesendet! Bitte prüfe dein Postfach.'
  } catch {
    error.value = 'Fehler beim Senden. Bitte versuche es erneut.'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const token = route.query.token as string
  if (!token) return
  loading.value = true
  try {
    const res = await axios.get(`/auth/verify?token=${token}`)
    localStorage.setItem('token', res.data.access_token)
    router.push('/')
  } catch {
    error.value = 'Ungültiger oder abgelaufener Link.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div style="min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px; position:relative; overflow:hidden; background:var(--bg-base);">
    <div style="position:absolute; width:600px; height:600px; border-radius:50%; background:#06b6d4; opacity:0.05; filter:blur(100px); pointer-events:none;" />
    <div style="position:relative; width:100%; max-width:380px; background:var(--bg-surface); backdrop-filter:blur(20px); border-radius:24px; padding:40px; border:1px solid var(--border); box-shadow:0 0 60px rgba(6,182,212,0.1);">
      <div style="text-align:center; margin-bottom:32px;">
        <div style="font-size:44px; margin-bottom:12px;">🗓️</div>
        <h1 style="font-size:26px; font-weight:700; letter-spacing:-0.5px; margin-bottom:6px;">EventFinder</h1>
        <p style="color:var(--text-secondary); font-size:14px;">Plane gemeinsame Events mit deinen Freunden</p>
      </div>

      <div v-if="loading && !error && !message" style="text-align:center; color:var(--text-secondary); padding:20px 0;">
        Einen Moment...
      </div>

      <form v-else @submit.prevent="requestMagicLink">
        <label style="font-size:11px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.08em; display:block; margin-bottom:8px;">E-Mail Adresse</label>
        <input v-model="email" type="email" placeholder="du@beispiel.de" required
          style="width:100%; background:rgba(255,255,255,0.05); border:1px solid var(--border); border-radius:12px; padding:13px 16px; color:#fff; font-size:14px; outline:none; margin-bottom:14px; transition:border-color .2s; box-sizing:border-box;"
          @focus="e => (e.target as HTMLInputElement).style.borderColor = 'rgba(255,255,255,0.25)'"
          @blur="e => (e.target as HTMLInputElement).style.borderColor = 'var(--border)'" />

        <button type="submit" :disabled="loading"
          style="width:100%; padding:13px; border-radius:12px; border:none; cursor:pointer; font-weight:600; font-size:14px; color:#000; background:#06b6d4; box-shadow:0 0 30px rgba(6,182,212,0.4); transition:opacity .2s;">
          {{ loading ? 'Sende...' : 'Magic Link anfordern ✉️' }}
        </button>

        <p v-if="message" style="color:#10b981; font-size:13px; text-align:center; margin-top:16px;">{{ message }}</p>
        <p v-if="error" style="color:#f43f5e; font-size:13px; text-align:center; margin-top:16px;">{{ error }}</p>
      </form>

      <p style="text-align:center; color:var(--text-muted); font-size:12px; margin-top:24px;">Kein Passwort nötig — du bekommst einen sicheren Link per E-Mail.</p>
    </div>
  </div>
</template>
```

- [ ] **Schritt 2: In Browser prüfen**

`https://eventfinder.thunderbee.uk/login` öffnen — Dark Glassmorphismus-Card, zentriert, Glow-Effekt sichtbar.

- [ ] **Schritt 3: Commit**

```bash
cd /root/eventfinder
git add frontend/src/views/Login.vue
git commit -m "feat: Login view dark mode redesign"
```

---

## Task 10: View — Dashboard.vue

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`

- [ ] **Schritt 1: Dashboard.vue vollständig ersetzen**

```vue
<!-- frontend/src/views/Dashboard.vue -->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'
import CreateEventModal from '../components/CreateEventModal.vue'

const { headers, logout } = useAuth()

interface Event {
  id: string; title: string; description?: string
  location_name?: string; accent_color: string
  cover_image_path?: string; is_closed: boolean
  final_date?: string; created_at: string
}

const events = ref<Event[]>([])
const loading = ref(true)
const showCreate = ref(false)

const fetchEvents = async () => {
  try {
    const res = await axios.get('/events/', { headers: headers() })
    events.value = res.data
  } catch { /* 401 handled by interceptor */ }
  finally { loading.value = false }
}

function onCreated(id: string) {
  showCreate.value = false
  fetchEvents()
}

function cardHover(el: HTMLElement, accent: string, enter: boolean) {
  el.style.boxShadow = enter ? `0 0 35px ${accent}33` : 'none'
  el.style.borderColor = enter ? `${accent}44` : 'rgba(255,255,255,0.07)'
  el.style.transform = enter ? 'translateY(-2px)' : 'translateY(0)'
}

onMounted(fetchEvents)
</script>

<template>
  <div style="min-height:100vh; background:var(--bg-base);">
    <!-- Header -->
    <header style="border-bottom:1px solid var(--border); padding:16px 32px; display:flex; align-items:center; justify-content:space-between; backdrop-filter:blur(12px); position:sticky; top:0; z-index:10; background:rgba(8,11,20,0.8);">
      <span style="font-weight:700; font-size:18px; letter-spacing:-0.5px;">EventFinder</span>
      <div style="display:flex; align-items:center; gap:12px;">
        <button @click="showCreate = true"
          style="display:flex; align-items:center; gap:6px; background:#06b6d4; color:#000; border:none; padding:9px 18px; border-radius:10px; font-weight:600; font-size:14px; cursor:pointer; box-shadow:0 0 20px rgba(6,182,212,0.4);">
          ＋ Neues Event
        </button>
        <button @click="logout"
          style="background:transparent; border:1px solid var(--border); color:var(--text-secondary); padding:9px 14px; border-radius:10px; cursor:pointer; font-size:13px;">
          Abmelden
        </button>
      </div>
    </header>

    <main style="max-width:1100px; margin:0 auto; padding:40px 24px;">
      <div style="margin-bottom:32px;">
        <h1 style="font-size:28px; font-weight:700; letter-spacing:-0.5px; margin-bottom:4px;">Meine Events</h1>
        <p style="color:var(--text-secondary); font-size:14px;">{{ events.length }} {{ events.length === 1 ? 'Event' : 'Events' }}</p>
      </div>

      <div v-if="loading" style="text-align:center; color:var(--text-secondary); padding:60px 0;">
        Lade Events...
      </div>

      <div v-else-if="events.length === 0" style="text-align:center; padding:80px 0;">
        <div style="font-size:48px; margin-bottom:16px; opacity:0.3;">🗓️</div>
        <p style="color:var(--text-secondary); margin-bottom:24px;">Noch keine Events. Erstelle dein erstes!</p>
        <button @click="showCreate = true"
          style="background:#06b6d4; color:#000; border:none; padding:12px 28px; border-radius:12px; font-weight:600; cursor:pointer; font-size:15px;">
          ＋ Event erstellen
        </button>
      </div>

      <div v-else style="display:grid; grid-template-columns:repeat(auto-fill, minmax(290px,1fr)); gap:20px;">
        <router-link v-for="ev in events" :key="ev.id" :to="`/event/${ev.id}`"
          style="text-decoration:none; color:inherit; display:block; border-radius:18px; overflow:hidden; background:var(--bg-card); border:1px solid var(--border); transition:all .25s; cursor:pointer;"
          @mouseenter="e => cardHover(e.currentTarget as HTMLElement, ev.accent_color, true)"
          @mouseleave="e => cardHover(e.currentTarget as HTMLElement, ev.accent_color, false)">
          <!-- Cover -->
          <div style="height:110px; position:relative; overflow:hidden;">
            <img v-if="ev.cover_image_path" :src="`/${ev.cover_image_path}`"
              style="width:100%; height:100%; object-fit:cover;" />
            <div v-else :style="{ height:'100%', background:`linear-gradient(135deg, ${ev.accent_color}33, #080b14)` }" />
            <div style="position:absolute; inset:0; background:rgba(0,0,0,0.15);" />
            <div :style="{ position:'absolute', bottom:0, left:0, right:0, height:'1px', background:`linear-gradient(90deg, transparent, ${ev.accent_color}, transparent)` }" />
            <span :style="{
              position:'absolute', top:'10px', right:'10px', fontSize:'11px',
              padding:'3px 9px', borderRadius:'20px', background:'rgba(0,0,0,0.55)',
              backdropFilter:'blur(8px)', color: ev.accent_color, border:'1px solid rgba(255,255,255,0.08)'
            }">{{ ev.is_closed ? 'Abgeschlossen' : ev.final_date ? 'Datum festgelegt' : 'Abstimmung läuft' }}</span>
          </div>
          <!-- Body -->
          <div style="padding:18px;">
            <h2 style="font-size:17px; font-weight:600; margin-bottom:6px;">{{ ev.title }}</h2>
            <p style="color:var(--text-secondary); font-size:13px; margin-bottom:14px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">
              {{ ev.description || 'Keine Beschreibung' }}
            </p>
            <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--text-muted);">
              <span v-if="ev.location_name">📍 {{ ev.location_name }}</span>
              <span v-if="ev.final_date">📅 {{ new Date(ev.final_date).toLocaleDateString('de-DE') }}</span>
            </div>
          </div>
        </router-link>

        <!-- Add card -->
        <div @click="showCreate = true"
          style="border-radius:18px; border:1.5px dashed rgba(255,255,255,0.1); min-height:180px; display:flex; align-items:center; justify-content:center; cursor:pointer; transition:all .2s;"
          @mouseenter="e => { (e.currentTarget as HTMLElement).style.borderColor='rgba(255,255,255,0.25)' }"
          @mouseleave="e => { (e.currentTarget as HTMLElement).style.borderColor='rgba(255,255,255,0.1)' }">
          <div style="text-align:center;">
            <div style="font-size:30px; color:rgba(255,255,255,0.15); margin-bottom:8px;">＋</div>
            <p style="color:var(--text-muted); font-size:13px;">Event erstellen</p>
          </div>
        </div>
      </div>
    </main>

    <CreateEventModal v-if="showCreate" @close="showCreate = false" @created="onCreated" />
  </div>
</template>
```

- [ ] **Schritt 2: In Browser prüfen**

Nach Login Dashboard aufrufen — Event-Grid sichtbar, „Neues Event"-Button öffnet Modal.

- [ ] **Schritt 3: Commit**

```bash
cd /root/eventfinder
git add frontend/src/views/Dashboard.vue
git commit -m "feat: Dashboard view dark mode redesign with event grid"
```

---

## Task 11: View — EventDetails.vue

**Files:**
- Modify: `frontend/src/views/EventDetails.vue`

- [ ] **Schritt 1: EventDetails.vue vollständig ersetzen**

```vue
<!-- frontend/src/views/EventDetails.vue -->
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'
import EventHero from '../components/EventHero.vue'
import AvailabilityCalendar from '../components/AvailabilityCalendar.vue'
import DateProposals from '../components/DateProposals.vue'
import ParticipantList from '../components/ParticipantList.vue'
import InviteModal from '../components/InviteModal.vue'

const route = useRoute()
const { headers } = useAuth()
const eventId = route.params.id as string

const event = ref<any>(null)
const participants = ref<any[]>([])
const proposals = ref<any[]>([])
const availabilities = ref<any[]>([])
const myUserId = ref<string | null>(null)
const loading = ref(true)
const showInvite = ref(false)
const showAvailModal = ref(false)
const selectedDate = ref('')
const availStatus = ref<'best'|'possible'|'impossible'>('possible')
const availComment = ref('')
const showCoverUpload = ref(false)

async function load() {
  const token = localStorage.getItem('token') ?? ''
  const payload = JSON.parse(atob(token.split('.')[1]))
  myUserId.value = payload.sub

  const [evRes, pRes, propRes, avRes] = await Promise.all([
    axios.get(`/events/${eventId}`, { headers: headers() }),
    axios.get(`/events/${eventId}/participants`, { headers: headers() }),
    axios.get(`/events/${eventId}/proposals`, { headers: headers() }),
    axios.get(`/events/${eventId}/availability`, { headers: headers() }),
  ])
  event.value = evRes.data
  participants.value = pRes.data
  proposals.value = propRes.data
  availabilities.value = avRes.data
  loading.value = false
}

const isOrganizer = computed(() => event.value?.organizer_id === myUserId.value)

const proposedDateStrings = computed(() => proposals.value.map((p: any) => p.proposed_date))

const allAvailabilities = computed(() =>
  availabilities.value.map((a: any) => ({ ...a, own: true }))
)

function onDateClick(date: string) {
  selectedDate.value = date
  const existing = availabilities.value.find((a: any) => a.event_date === date)
  availStatus.value = existing?.status ?? 'possible'
  availComment.value = existing?.comment ?? ''
  showAvailModal.value = true
}

async function saveAvailability() {
  await axios.post(`/events/${eventId}/availability`, {
    event_date: selectedDate.value, status: availStatus.value, comment: availComment.value,
  }, { headers: headers() })
  showAvailModal.value = false
  await load()
}

async function setFinalDate(date: string) {
  await axios.patch(`/events/${eventId}`, { final_date: date }, { headers: headers() })
  await load()
}

async function uploadCover(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const fd = new FormData(); fd.append('file', file)
  await axios.post(`/events/${eventId}/cover`, fd, { headers: { ...headers(), 'Content-Type': 'multipart/form-data' } })
  showCoverUpload.value = false
  await load()
}

onMounted(load)
</script>

<template>
  <div style="min-height:100vh; background:var(--bg-base);">
    <!-- Back nav -->
    <div style="padding:16px 32px; border-bottom:1px solid var(--border); background:rgba(8,11,20,0.8); backdrop-filter:blur(12px); position:sticky; top:0; z-index:10; display:flex; align-items:center; gap:12px;">
      <router-link to="/" style="color:var(--text-secondary); text-decoration:none; font-size:14px;">← Dashboard</router-link>
      <span style="color:var(--border);">|</span>
      <span style="font-weight:600; font-size:14px;">{{ event?.title ?? '...' }}</span>
    </div>

    <div v-if="loading" style="display:flex; align-items:center; justify-content:center; height:60vh; color:var(--text-secondary);">
      Lade Event...
    </div>

    <main v-else-if="event" style="max-width:1000px; margin:0 auto; padding:32px 24px;">
      <EventHero
        :title="event.title"
        :description="event.description"
        :location-name="event.location_name"
        :accent-color="event.accent_color"
        :cover-image-path="event.cover_image_path"
        :participant-count="participants.length"
        :is-organizer="isOrganizer"
        @invite="showInvite = true"
        @edit-cover="showCoverUpload = true"
        style="margin-bottom:28px;"
      />

      <!-- Cover upload input (hidden, triggered by hero button) -->
      <input v-if="showCoverUpload" type="file" accept="image/jpeg,image/png,image/webp"
        @change="uploadCover" style="display:none;" ref="coverInput" />

      <div style="display:grid; grid-template-columns:1fr 2fr; gap:20px;">
        <!-- Left -->
        <div style="display:flex; flex-direction:column; gap:16px;">
          <div style="background:var(--bg-surface); border:1px solid var(--border); border-radius:16px; padding:20px;">
            <DateProposals
              :proposals="proposals"
              :availabilities="allAvailabilities"
              :participant-count="participants.length"
              :accent-color="event.accent_color"
              :final-date="event.final_date"
              @set-final="isOrganizer && setFinalDate($event)"
            />
          </div>
          <div style="background:var(--bg-surface); border:1px solid var(--border); border-radius:16px; padding:20px;">
            <ParticipantList
              :participants="participants"
              :accent-color="event.accent_color"
              :total-proposals="proposals.length"
              @invite="showInvite = true"
            />
          </div>
        </div>

        <!-- Right: Calendar -->
        <div style="background:var(--bg-surface); border:1px solid var(--border); border-radius:16px; padding:24px;">
          <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em; margin-bottom:16px;">
            Verfügbarkeit abstimmen
          </p>
          <p style="font-size:13px; color:var(--text-secondary); margin-bottom:20px;">
            Klicke auf einen vorgeschlagenen Termin um deine Verfügbarkeit anzugeben.
          </p>
          <AvailabilityCalendar
            :proposed-dates="proposedDateStrings"
            :availabilities="allAvailabilities"
            :participant-count="participants.length"
            :accent-color="event.accent_color"
            :final-date="event.final_date"
            @date-click="onDateClick"
          />
        </div>
      </div>
    </main>

    <!-- Availability Modal -->
    <div v-if="showAvailModal"
      style="position:fixed; inset:0; background:rgba(0,0,0,0.7); display:flex; align-items:center; justify-content:center; padding:16px; z-index:100; backdrop-filter:blur(4px);"
      @click.self="showAvailModal = false">
      <div style="background:#0d1117; border:1px solid rgba(255,255,255,0.1); border-radius:20px; padding:32px; width:100%; max-width:380px;">
        <h2 style="font-size:18px; font-weight:700; margin-bottom:6px;">Verfügbarkeit</h2>
        <p style="color:var(--text-secondary); font-size:14px; margin-bottom:20px;">{{ selectedDate }}</p>

        <div style="display:flex; flex-direction:column; gap:8px; margin-bottom:16px;">
          <button v-for="opt in [{ v:'best', l:'🟢 Sehr gut / Favorit' },{ v:'possible', l:'🟡 Möglich' },{ v:'impossible', l:'🔴 Nicht möglich' }]"
            :key="opt.v" @click="availStatus = opt.v as any"
            :style="{
              padding:'11px 16px', borderRadius:'10px', border:'1px solid',
              borderColor: availStatus === opt.v ? `${event.accent_color}88` : 'rgba(255,255,255,0.1)',
              background: availStatus === opt.v ? `${event.accent_color}18` : 'transparent',
              color: availStatus === opt.v ? '#fff' : 'rgba(255,255,255,0.6)',
              cursor:'pointer', textAlign:'left', fontSize:'14px', fontWeight: availStatus === opt.v ? 600 : 400,
            }">{{ opt.l }}</button>
        </div>

        <input v-model="availComment" placeholder="Kommentar (optional)"
          style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none; margin-bottom:20px; box-sizing:border-box;" />

        <div style="display:flex; justify-content:flex-end; gap:10px;">
          <button @click="showAvailModal = false"
            style="padding:10px 20px; border-radius:10px; background:transparent; border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.6); cursor:pointer; font-size:14px;">
            Abbrechen
          </button>
          <button @click="saveAvailability"
            :style="{ padding:'10px 24px', borderRadius:'10px', border:'none', cursor:'pointer', fontWeight:600, fontSize:'14px', color:'#000', background: event.accent_color }">
            Speichern
          </button>
        </div>
      </div>
    </div>

    <!-- Cover upload modal -->
    <div v-if="showCoverUpload"
      style="position:fixed; inset:0; background:rgba(0,0,0,0.7); display:flex; align-items:center; justify-content:center; padding:16px; z-index:100; backdrop-filter:blur(4px);"
      @click.self="showCoverUpload = false">
      <div style="background:#0d1117; border:1px solid rgba(255,255,255,0.1); border-radius:20px; padding:32px; width:100%; max-width:400px;">
        <h2 style="font-size:18px; font-weight:700; margin-bottom:16px;">Cover-Bild hochladen</h2>
        <input type="file" accept="image/jpeg,image/png,image/webp" @change="uploadCover"
          style="width:100%; background:rgba(255,255,255,0.04); border:1.5px dashed rgba(255,255,255,0.15); border-radius:10px; padding:14px; color:rgba(255,255,255,0.5); font-size:13px; cursor:pointer; box-sizing:border-box;" />
        <p style="color:var(--text-muted); font-size:12px; margin-top:10px;">JPEG, PNG oder WebP · max. 5 MB</p>
        <button @click="showCoverUpload = false"
          style="margin-top:16px; padding:10px 20px; border-radius:10px; background:transparent; border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.6); cursor:pointer; font-size:14px;">
          Abbrechen
        </button>
      </div>
    </div>

    <InviteModal v-if="showInvite" :event-id="eventId" :accent-color="event?.accent_color ?? '#06b6d4'"
      @close="showInvite = false" @invited="load()" />
  </div>
</template>
```

- [ ] **Schritt 2: In Browser prüfen**

Ein Event aufrufen — Hero-Banner, Datumsvorschläge, Teilnehmerliste und Kalender sichtbar. Verfügbarkeit auf einem vorgeschlagenen Datum klicken und speichern.

- [ ] **Schritt 3: Commit**

```bash
cd /root/eventfinder
git add frontend/src/views/EventDetails.vue
git commit -m "feat: EventDetails view dark mode redesign with all components"
```

---

## Task 12: Cleanup + Router

**Files:**
- Modify: `frontend/src/router/index.ts`
- Delete: `frontend/src/views/Mockup.vue`, `frontend/src/components/Calendar.vue`, `frontend/src/components/HelloWorld.vue`

- [ ] **Schritt 1: Mockup-Route entfernen**

`frontend/src/router/index.ts` — `import Mockup` und die Mockup-Route entfernen:

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Dashboard from '../views/Dashboard.vue'
import EventDetails from '../views/EventDetails.vue'

const routes = [
  { path: '/login', name: 'Login', component: Login },
  { path: '/', name: 'Dashboard', component: Dashboard, meta: { requiresAuth: true } },
  { path: '/event/:id', name: 'EventDetails', component: EventDetails, meta: { requiresAuth: true } },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) next('/login')
  else next()
})

export default router
```

- [ ] **Schritt 2: Nicht mehr benötigte Dateien löschen**

```bash
rm /root/eventfinder/frontend/src/views/Mockup.vue
rm /root/eventfinder/frontend/src/components/Calendar.vue
rm /root/eventfinder/frontend/src/components/HelloWorld.vue
```

- [ ] **Schritt 3: Frontend neu starten**

```bash
docker restart eventfinder-frontend && sleep 4
docker logs eventfinder-frontend 2>&1 | tail -5
```

Erwartet: Vite startet ohne Fehler.

- [ ] **Schritt 4: End-to-End manuell testen**

1. `https://eventfinder.thunderbee.uk/login` → Magic Link anfordern
2. Token-Link direkt aufrufen → Login funktioniert
3. Dashboard → Neues Event erstellen mit Farbe + Datum + Ort
4. Event öffnen → Verfügbarkeit abstimmen
5. Als Organisator: Teilnehmer einladen, Final-Datum setzen
6. Cover-Bild hochladen → Hero zeigt Bild

- [ ] **Schritt 5: Finaler Commit**

```bash
cd /root/eventfinder
git add -A
git commit -m "feat: complete EventFinder Alpha redesign

- Dark mode design system (CSS variables, inline styles)
- Per-event accent color + cover image upload (Pillow resize)
- Glassmorphismus modals (CreateEvent, Invite, Availability, Cover)
- AvailabilityCalendar with heatmap on proposed dates only
- DateProposals with voting status + final date selection
- ParticipantList with voting progress
- useAuth composable with 401 interceptor
- Cleanup: removed Mockup, old Calendar, HelloWorld"
```

---

## Self-Review

**Spec Coverage:**
- ✅ Dark Mode Design-System (CSS-Variablen + Inline-Styles)
- ✅ Cover-Bild Upload (Pillow, max 5MB, resize 1200px)
- ✅ Akzentfarbe pro Event (5 Swatches)
- ✅ Alembic Migration (accent_color, cover_image_path, date_proposals)
- ✅ PATCH /events/{id} (final_date, accent_color, location)
- ✅ GET /events/{id}/participants
- ✅ GET+POST /events/{id}/proposals
- ✅ StaticFiles /uploads mount
- ✅ useAuth composable mit 401-Interceptor
- ✅ CreateEventModal (Ort, Farbe, Cover, Datumsvorschläge)
- ✅ InviteModal
- ✅ Nur vorgeschlagene Daten im Kalender anklickbar
- ✅ Heatmap-Verfügbarkeit (aggregiert über Teilnehmer)
- ✅ Sicherheitslücke get_event bereits gefixt (Task 3 enthält korrekten Code)
- ✅ Cleanup (Mockup, Calendar, HelloWorld)
