# App Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allgemeines Einstellungssystem — SMTP-Konfiguration wird verschlüsselt in PostgreSQL gespeichert, per Superadmin-UI verwaltet und via Redis-Cache an Celery-Worker übergeben.

**Architecture:** `app_settings`-Tabelle (key/value, Fernet-verschlüsselt) + Write-Through-Cache in Redis. Superadmin-Guard auf FastAPI-Ebene. Erster registrierter User wird automatisch Superadmin.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy asyncpg, Alembic, cryptography.fernet, redis-py (sync), Vue 3, TypeScript

---

## Datei-Übersicht

### Backend — neu
- `backend/encryption.py` — Fernet-Schlüsselableitung, `encrypt_value`, `decrypt_value`
- `backend/api/admin_settings.py` — GET/PUT `/api/admin/settings`, POST `/api/admin/settings/test-mail`
- `backend/migrations/versions/003_app_settings.py` — Alembic-Migration

### Backend — geändert
- `backend/models.py` — `AppSetting`-Klasse hinzufügen
- `backend/main.py` — `admin_settings`-Router einbinden
- `backend/api/auth.py` — Superadmin Auto-Promotion bei erstem User
- `backend/tasks.py` — `_get_smtp_settings()` aus Redis, `_send_email` akzeptiert Settings-Dict

### Frontend — neu
- `frontend/src/views/AdminSettings.vue` — Einstellungsformular

### Frontend — geändert
- `frontend/src/router/index.ts` — Route + Admin-Guard
- `frontend/src/views/Dashboard.vue` — ⚙️-Button für Superadmin

---

## Task 1: Alembic-Migration `003_app_settings`

**Files:**
- Create: `backend/migrations/versions/003_app_settings.py`

- [ ] **Schritt 1: Migrationsdatei erstellen**

Datei: `backend/migrations/versions/003_app_settings.py`

```python
"""Add app_settings table

Revision ID: 003_app_settings
Revises: 002_event_theming
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = '003_app_settings'
down_revision = '002_event_theming'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('is_encrypted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('app_settings')
```

- [ ] **Schritt 2: Migration ausführen**

```bash
docker exec eventfinder-backend alembic upgrade head
```

Erwartete Ausgabe: `Running upgrade 002_event_theming -> 003_app_settings, Add app_settings table`

- [ ] **Schritt 3: Tabelle verifizieren**

```bash
docker exec eventfinder-db psql -U user -d eventfinder -c "\d app_settings"
```

Erwartet: Spalten `key`, `value`, `is_encrypted`, `updated_at`.

- [ ] **Schritt 4: Commit**

```bash
cd /docker/eventfinder
git add backend/migrations/versions/003_app_settings.py
git commit -m "feat: add app_settings migration"
```

---

## Task 2: Encryption Helper + AppSetting Model

**Files:**
- Create: `backend/encryption.py`
- Modify: `backend/models.py`

- [ ] **Schritt 1: `backend/encryption.py` erstellen**

```python
import os
import hashlib
import base64
from cryptography.fernet import Fernet


def get_fernet() -> Fernet:
    secret = os.getenv("SECRET_KEY", "fallback-insecure-key")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_value(value: str) -> str:
    return get_fernet().encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    return get_fernet().decrypt(encrypted.encode()).decode()
```

- [ ] **Schritt 2: Fernet-Import im laufenden Container prüfen**

```bash
docker exec eventfinder-backend python3 -c "from cryptography.fernet import Fernet; print('ok')"
```

Erwartet: `ok`

- [ ] **Schritt 3: `AppSetting`-Klasse zu `backend/models.py` hinzufügen**

Am Ende von `backend/models.py` nach der `DateProposal`-Klasse einfügen:

```python
class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    is_encrypted: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
```

- [ ] **Schritt 4: Backend neu starten und prüfen**

```bash
docker restart eventfinder-backend && sleep 5
docker logs eventfinder-backend 2>&1 | tail -5
```

Erwartet: `Application startup complete.` — kein Traceback.

- [ ] **Schritt 5: Commit**

```bash
cd /docker/eventfinder
git add backend/encryption.py backend/models.py
git commit -m "feat: add encryption helper and AppSetting model"
```

---

## Task 3: Admin Settings API

**Files:**
- Create: `backend/api/admin_settings.py`

- [ ] **Schritt 1: `backend/api/admin_settings.py` erstellen**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from datetime import datetime
from typing import Any
import os

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
        r.hset(REDIS_SETTINGS_KEY, mapping=redis_data)

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
    msg["To"] = rows["mail_username"]
    msg["Subject"] = "EventFinder Test-E-Mail"
    msg.set_content("Diese Test-E-Mail bestätigt, dass deine Mail-Konfiguration korrekt ist.")

    try:
        await send(
            msg,
            hostname=rows["mail_server"],
            port=int(rows["mail_port"]),
            username=rows["mail_username"],
            password=rows["mail_password"],
            start_tls=int(rows.get("mail_port", "587")) == 587,
        )
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

- [ ] **Schritt 2: Commit**

```bash
cd /docker/eventfinder
git add backend/api/admin_settings.py
git commit -m "feat: add admin settings API with Fernet encryption and Redis cache"
```

---

## Task 4: Router einbinden + Auth Superadmin Auto-Promotion

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/api/auth.py`

- [ ] **Schritt 1: Router in `backend/main.py` einbinden**

Nach den bestehenden `from api import ...`-Imports folgende Zeile hinzufügen:

```python
from api import admin_settings as api_admin_settings
```

Nach den bestehenden `app.include_router(...)`-Zeilen hinzufügen:

```python
app.include_router(api_admin_settings.router, prefix="/api/admin", tags=["admin"])
```

- [ ] **Schritt 2: `backend/api/auth.py` — Superadmin Auto-Promotion**

Am Anfang der Datei den Import erweitern:

```python
from sqlalchemy import select, func
```

Den bestehenden Block zur User-Erstellung (nach `if not user:`) wie folgt ersetzen:

```python
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
```

- [ ] **Schritt 3: Backend neu starten und Endpoints verifizieren**

```bash
docker restart eventfinder-backend && sleep 5
docker logs eventfinder-backend 2>&1 | tail -5
```

Erwartet: `Application startup complete.`

```bash
curl -s http://localhost:8000/openapi.json | python3 -c "import json,sys; paths=json.load(sys.stdin)['paths']; print([p for p in paths if 'admin' in p])"
```

Erwartet: `['/api/admin/settings', '/api/admin/settings/test-mail']`

- [ ] **Schritt 4: Commit**

```bash
cd /docker/eventfinder
git add backend/main.py backend/api/auth.py
git commit -m "feat: register admin router, auto-promote first user to superadmin"
```

---

## Task 5: tasks.py — Redis-basierter Settings-Abruf

**Files:**
- Modify: `backend/tasks.py`

- [ ] **Schritt 1: `backend/tasks.py` vollständig ersetzen**

```python
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
```

- [ ] **Schritt 2: Worker neu starten**

```bash
docker restart eventfinder-worker && sleep 4
docker logs eventfinder-worker 2>&1 | tail -5
```

Erwartet: `celery@... ready.` — kein ImportError.

- [ ] **Schritt 3: Commit**

```bash
cd /docker/eventfinder
git add backend/tasks.py
git commit -m "feat: tasks.py reads SMTP settings from Redis with .env fallback"
```

---

## Task 6: Frontend — AdminSettings.vue

**Files:**
- Create: `frontend/src/views/AdminSettings.vue`

- [ ] **Schritt 1: `frontend/src/views/AdminSettings.vue` erstellen**

```vue
<!-- frontend/src/views/AdminSettings.vue -->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'

const { headers } = useAuth()

const form = ref({
  mail_server: '',
  mail_port: '587',
  mail_username: '',
  mail_password: '',
  mail_from: '',
  frontend_url: '',
})
const passwordSet = ref(false)
const saving = ref(false)
const testing = ref(false)
const saveMsg = ref('')
const testResult = ref<{ success: boolean; error?: string } | null>(null)

async function load() {
  try {
    const res = await axios.get('/api/admin/settings', { headers: headers() })
    const d = res.data
    form.value.mail_server = d.mail_server ?? ''
    form.value.mail_port = d.mail_port ?? '587'
    form.value.mail_username = d.mail_username ?? ''
    form.value.mail_from = d.mail_from ?? ''
    form.value.frontend_url = d.frontend_url ?? ''
    passwordSet.value = d.mail_password === '***'
    form.value.mail_password = ''
  } catch (e: any) {
    if (e.response?.status === 403) window.location.href = '/'
  }
}

async function save() {
  saving.value = true; saveMsg.value = ''
  try {
    const payload: Record<string, string> = {
      mail_server: form.value.mail_server,
      mail_port: form.value.mail_port,
      mail_username: form.value.mail_username,
      mail_from: form.value.mail_from,
      frontend_url: form.value.frontend_url,
    }
    if (form.value.mail_password) payload.mail_password = form.value.mail_password
    await axios.put('/api/admin/settings', payload, { headers: headers() })
    saveMsg.value = 'Gespeichert ✓'
    passwordSet.value = true
    form.value.mail_password = ''
  } catch (e: any) {
    saveMsg.value = e.response?.data?.detail ?? 'Fehler beim Speichern'
  } finally {
    saving.value = false
  }
}

async function testMail() {
  testing.value = true; testResult.value = null
  try {
    const res = await axios.post('/api/admin/settings/test-mail', {}, { headers: headers() })
    testResult.value = res.data
  } catch (e: any) {
    testResult.value = { success: false, error: e.response?.data?.detail ?? 'Netzwerkfehler' }
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>

<template>
  <div style="min-height:100vh; background:var(--bg-base);">
    <div style="padding:16px 32px; border-bottom:1px solid var(--border); background:rgba(8,11,20,0.8); backdrop-filter:blur(12px); position:sticky; top:0; z-index:10; display:flex; align-items:center; gap:12px;">
      <router-link to="/" style="color:var(--text-secondary); text-decoration:none; font-size:14px;">← Dashboard</router-link>
      <span style="color:var(--border);">|</span>
      <span style="font-weight:600; font-size:14px;">⚙️ Einstellungen</span>
    </div>

    <main style="max-width:600px; margin:0 auto; padding:40px 24px;">
      <h1 style="font-size:24px; font-weight:700; margin-bottom:8px;">App-Einstellungen</h1>
      <p style="color:var(--text-secondary); font-size:14px; margin-bottom:32px;">
        Konfiguration wird verschlüsselt in der Datenbank gespeichert.
      </p>

      <div style="background:var(--bg-surface); border:1px solid var(--border); border-radius:16px; padding:28px; display:flex; flex-direction:column; gap:18px;">
        <p style="font-size:11px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:.08em;">E-Mail / SMTP</p>

        <div v-for="field in [
          { key: 'mail_server',   label: 'SMTP-Server',    placeholder: 'smtp.web.de',                         type: 'text'   },
          { key: 'mail_port',     label: 'SMTP-Port',      placeholder: '587',                                  type: 'number' },
          { key: 'mail_username', label: 'Benutzername',   placeholder: 'du@web.de',                            type: 'email'  },
          { key: 'mail_from',     label: 'Absender',       placeholder: 'du@web.de',                            type: 'email'  },
          { key: 'frontend_url',  label: 'Frontend-URL',   placeholder: 'https://eventfinder.thunderbee.uk',    type: 'text'   },
        ]" :key="field.key">
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">{{ field.label }}</label>
          <input v-model="(form as any)[field.key]" :type="field.type" :placeholder="field.placeholder"
            style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none; box-sizing:border-box;" />
        </div>

        <!-- Passwort -->
        <div>
          <label style="font-size:12px; color:rgba(255,255,255,0.4); display:block; margin-bottom:6px;">Passwort</label>
          <input v-model="form.mail_password" type="password"
            :placeholder="passwordSet ? '●●●●●●●● (unverändert lassen)' : 'Passwort eingeben'"
            style="width:100%; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:10px; padding:10px 14px; color:#fff; font-size:14px; outline:none; box-sizing:border-box;" />
          <p style="font-size:11px; color:rgba(255,255,255,0.3); margin-top:5px;">
            Leer lassen um das bestehende Passwort nicht zu ändern
          </p>
        </div>

        <p v-if="saveMsg" :style="{ fontSize:'13px', color: saveMsg.includes('✓') ? '#10b981' : '#f43f5e' }">
          {{ saveMsg }}
        </p>

        <div style="display:flex; gap:10px; margin-top:8px;">
          <button @click="save" :disabled="saving"
            :style="{
              flex:1, padding:'11px', borderRadius:'10px', border:'none', cursor:'pointer',
              fontWeight:600, fontSize:'14px', color:'#000', background:'#06b6d4',
              boxShadow:'0 0 20px rgba(6,182,212,0.3)', opacity: saving ? 0.7 : 1,
            }">
            {{ saving ? 'Speichern...' : 'Speichern' }}
          </button>
          <button @click="testMail" :disabled="testing"
            :style="{
              flex:1, padding:'11px', borderRadius:'10px',
              background:'transparent', border:'1px solid rgba(255,255,255,0.15)',
              color:'rgba(255,255,255,0.7)', cursor:'pointer', fontSize:'14px',
              opacity: testing ? 0.7 : 1,
            }">
            {{ testing ? 'Sende...' : 'Test-E-Mail senden' }}
          </button>
        </div>

        <div v-if="testResult" :style="{
          padding:'12px 16px', borderRadius:'10px', fontSize:'13px',
          background: testResult.success ? 'rgba(16,185,129,0.1)' : 'rgba(244,63,94,0.1)',
          border: `1px solid ${testResult.success ? 'rgba(16,185,129,0.3)' : 'rgba(244,63,94,0.3)'}`,
          color: testResult.success ? '#10b981' : '#f43f5e',
        }">
          {{ testResult.success ? '✓ Test-E-Mail erfolgreich gesendet!' : `✗ Fehler: ${testResult.error}` }}
        </div>
      </div>
    </main>
  </div>
</template>
```

- [ ] **Schritt 2: Commit**

```bash
cd /docker/eventfinder
git add frontend/src/views/AdminSettings.vue
git commit -m "feat: AdminSettings view with SMTP form, encrypted save, test-mail"
```

---

## Task 7: Vite-Proxy + Router-Guard + Dashboard ⚙️-Button

**Files:**
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/views/Dashboard.vue`

- [ ] **Schritt 0: `/api`-Proxy in `frontend/vite.config.ts` ergänzen**

Die `proxy`-Sektion um einen Eintrag erweitern (Zeile nach `/uploads`-Proxy einfügen):

```typescript
'/api': { target: 'http://backend:8000', changeOrigin: true },
```

Die vollständige `proxy`-Sektion sieht danach so aus:

```typescript
proxy: {
  '/auth':    { target: 'http://backend:8000', changeOrigin: true },
  '/events':  { target: 'http://backend:8000', changeOrigin: true },
  '/uploads': { target: 'http://backend:8000', changeOrigin: true },
  '/api':     { target: 'http://backend:8000', changeOrigin: true },
},
```

- [ ] **Schritt 1: `frontend/src/router/index.ts` vollständig ersetzen**

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Dashboard from '../views/Dashboard.vue'
import EventDetails from '../views/EventDetails.vue'
import AdminSettings from '../views/AdminSettings.vue'

const routes = [
  { path: '/login', name: 'Login', component: Login },
  { path: '/', name: 'Dashboard', component: Dashboard, meta: { requiresAuth: true } },
  { path: '/event/:id', name: 'EventDetails', component: EventDetails, meta: { requiresAuth: true } },
  { path: '/admin/settings', name: 'AdminSettings', component: AdminSettings, meta: { requiresAuth: true, requiresAdmin: true } },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) return next('/login')
  if (to.meta.requiresAdmin) {
    try {
      const payload = JSON.parse(atob(token!.split('.')[1]))
      if (payload.role !== 'superadmin') return next('/')
    } catch {
      return next('/login')
    }
  }
  next()
})

export default router
```

- [ ] **Schritt 2: `frontend/src/views/Dashboard.vue` — Script erweitern**

Die erste Zeile des `<script setup>`-Blocks ersetzen (merged imports):

```typescript
import { ref, onMounted, computed } from 'vue'
```

Direkt danach (nach der `import axios`-Zeile) hinzufügen:

```typescript
import { useRouter } from 'vue-router'
```

Vor `onMounted(fetchEvents)` am Ende des Script-Blocks einfügen:

```typescript
const router = useRouter()

const isAdmin = computed(() => {
  try {
    const token = localStorage.getItem('token') ?? ''
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.role === 'superadmin'
  } catch { return false }
})
```

- [ ] **Schritt 3: Dashboard-Header — ⚙️-Button hinzufügen**

Im `<template>` des Dashboards, im Header-`<div>` mit den Buttons (vor dem "Abmelden"-Button):

```vue
<button v-if="isAdmin" @click="router.push('/admin/settings')"
  style="background:transparent; border:1px solid rgba(255,255,255,0.1); color:rgba(255,255,255,0.5); padding:9px 12px; border-radius:10px; cursor:pointer; font-size:14px;"
  title="Einstellungen">
  ⚙️
</button>
```

- [ ] **Schritt 4: Commit**

```bash
cd /docker/eventfinder
git add frontend/vite.config.ts frontend/src/router/index.ts frontend/src/views/Dashboard.vue
git commit -m "feat: add /api proxy, admin settings route with guard and settings icon in dashboard"
```

---

## Task 8: End-to-End Verifizierung

**Files:** keine Änderungen

- [ ] **Schritt 1: Frontend-Container neu starten**

```bash
docker restart eventfinder-frontend && sleep 6
docker logs eventfinder-frontend 2>&1 | tail -5
```

Erwartet: Vite startet ohne Fehler.

- [ ] **Schritt 2: Magic Link für erste E-Mail anfordern (wird Superadmin)**

```bash
curl -s -X POST http://localhost:8000/auth/magic-link \
  -H "Content-Type: application/json" \
  -d '{"email": "sander-familie@web.de"}' | python3 -m json.tool
```

Erwartet: `{"message": "Magic link sent if email exists"}`

- [ ] **Schritt 3: User-Rolle in DB prüfen**

```bash
docker exec eventfinder-db psql -U user -d eventfinder -c \
  "SELECT email, role FROM users ORDER BY created_at LIMIT 5;"
```

Erwartet: `sander-familie@web.de | superadmin`

- [ ] **Schritt 4: Finaler Commit**

```bash
cd /docker/eventfinder
git add -A
git commit -m "feat: complete app settings system with encrypted DB storage and admin UI"
```
