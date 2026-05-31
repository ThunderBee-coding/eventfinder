# App Settings — Design Spec
**Datum:** 2026-05-31  
**Status:** Approved

---

## Überblick

Allgemeines Einstellungssystem für EventFinder: Konfigurationswerte (beginnend mit SMTP-Mail) werden verschlüsselt in der PostgreSQL-Datenbank gespeichert und über eine Superadmin-Weboberfläche verwaltet. Damit entfällt die manuelle .env-Bearbeitung für Betriebskonfiguration.

**Scope:** SMTP-Konfiguration als erster Eintrag; System ist generisch erweiterbar für weitere Keys.

---

## Architektur

```
Frontend AdminSettings.vue
      │
      ▼
GET/PUT /api/admin/settings   (FastAPI, superadmin-only)
POST /api/admin/settings/test-mail
      │
      ├──▶ PostgreSQL: app_settings (key/value, Fernet-verschlüsselt)
      │
      └──▶ Redis Hash: app:settings  (Write-Through-Cache für Celery)
                │
                ▼
          Celery Worker: send_magic_link_email
          (liest sync aus Redis, Fallback auf .env)
```

---

## Datenbank

### Migration `003_app_settings`

```sql
CREATE TABLE app_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    is_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### Gespeicherte Keys

| Key | Verschlüsselt | Beschreibung |
|-----|--------------|--------------|
| `mail_server` | Nein | SMTP-Hostname |
| `mail_port` | Nein | SMTP-Port (Standard 587) |
| `mail_username` | Nein | SMTP-Benutzername |
| `mail_password` | **Ja** | SMTP-Passwort, Fernet-verschlüsselt |
| `mail_from` | Nein | Absenderadresse |
| `frontend_url` | Nein | Basis-URL für Magic Links |

---

## Verschlüsselung

**Methode:** `cryptography.fernet.Fernet` (bereits installiert via `python-jose[cryptography]`)

**Schlüsselableitung:**
```python
import hashlib, base64
from cryptography.fernet import Fernet

def get_fernet(secret_key: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode()).digest())
    return Fernet(key)
```

Der Fernet-Schlüssel wird aus dem bestehenden `SECRET_KEY` in `.env` abgeleitet — kein neues Secret nötig. Der Klartext-Wert verlässt niemals das Backend; `GET /api/admin/settings` gibt `mail_password` als `"***"` zurück.

---

## Backend

### Datei: `backend/api/admin_settings.py` (neu)

**Endpoints:**

#### `GET /api/admin/settings`
- Auth: `role == superadmin` — sonst 403
- Liest alle Rows aus `app_settings`
- `mail_password` wird als `"***"` maskiert
- Response: `{ "mail_server": "smtp.web.de", "mail_port": "587", ..., "mail_password": "***" }`

#### `PUT /api/admin/settings`
- Auth: `role == superadmin` — sonst 403
- Body: `{ key: value, ... }` — alle Keys auf einmal
- Für `mail_password`: Fernet-verschlüsseln, `is_encrypted=true`
- Für alle anderen Keys: Plaintext, `is_encrypted=false`
- Upsert via `INSERT ... ON CONFLICT(key) DO UPDATE`
- Nach DB-Commit: Redis-Hash `app:settings` mit Plaintext-Werten befüllen (Passwort entschlüsselt)
- Response: 200 OK

#### `POST /api/admin/settings/test-mail`
- Auth: `role == superadmin` — sonst 403
- Liest aktuelle Settings aus DB
- Sendet Test-E-Mail an `mail_username` mit Subject "EventFinder Test-E-Mail"
- Response: `{ "success": true }` oder `{ "success": false, "error": "..." }`

### Datei: `backend/main.py` — Anpassung

```python
from api.admin_settings import router as admin_settings_router
app.include_router(admin_settings_router, prefix="/api/admin", tags=["admin"])
```

### Datei: `backend/tasks.py` — Anpassung

`_get_smtp_settings()` — liest aus Redis-Hash `app:settings`:
```python
def _get_smtp_settings() -> dict:
    import redis as redis_lib
    r = redis_lib.from_url(os.getenv("REDIS_URL"))
    settings = r.hgetall("app:settings")
    if settings:
        return {k.decode(): v.decode() for k, v in settings.items()}
    # Fallback auf .env
    return {
        "mail_server": os.getenv("MAIL_SERVER"),
        "mail_port": os.getenv("MAIL_PORT", "587"),
        "mail_username": os.getenv("MAIL_USERNAME"),
        "mail_password": os.getenv("MAIL_PASSWORD"),
        "mail_from": os.getenv("MAIL_FROM"),
        "frontend_url": os.getenv("FRONTEND_URL", "http://localhost:5173"),
    }
```

`send_magic_link_email` nutzt `_get_smtp_settings()` statt direkter `os.getenv()`-Aufrufe.

### Datei: `backend/api/auth.py` — Anpassung

Bei Neuanlage eines Users in `POST /auth/magic-link`:
```python
count = await db.scalar(select(func.count()).select_from(models.User))
role = UserRole.superadmin if count == 0 else UserRole.participant
```
Der allererste User bekommt `role=superadmin`, alle weiteren `role=participant`.

---

## Frontend

### Datei: `frontend/src/views/AdminSettings.vue` (neu)

**Felder:**
- SMTP-Server (text)
- SMTP-Port (number, default 587)
- Benutzername (text)
- Passwort (password, Placeholder `●●●●` wenn bereits gesetzt)
- Absender-Adresse (text)
- Frontend-URL (text)

**Buttons:**
- "Speichern" → `PUT /api/admin/settings`
- "Test-E-Mail senden" → `POST /api/admin/settings/test-mail` → zeigt Erfolg/Fehler inline

**Passwort-Handling:** Wenn Backend `"***"` zurückgibt → Placeholder anzeigen. Beim Speichern: leeres Passwort-Feld = "nicht ändern" (Backend überspringt Update für `mail_password`).

### Datei: `frontend/src/router/index.ts` — Anpassung

```typescript
import AdminSettings from '../views/AdminSettings.vue'

{ path: '/admin/settings', name: 'AdminSettings', component: AdminSettings, meta: { requiresAuth: true, requiresAdmin: true } }
```

Router-Guard ergänzt:
```typescript
if (to.meta.requiresAdmin) {
  const token = localStorage.getItem('token')
  const payload = JSON.parse(atob(token.split('.')[1]))
  if (payload.role !== 'superadmin') return next('/')
}
```

### Datei: `frontend/src/views/Dashboard.vue` — Anpassung

Im Header: ⚙️-Button sichtbar wenn `role === 'superadmin'` im JWT. Klick → `/admin/settings`.

---

## Fehlerbehandlung

| Szenario | Verhalten |
|----------|-----------|
| Nicht-Superadmin ruft Settings auf | 403 → Frontend redirect zu `/` |
| SMTP-Verbindung schlägt fehl (Test) | `{ success: false, error: "Connection refused" }` → Inline-Fehlermeldung |
| Redis nicht erreichbar | Celery-Task fällt auf .env zurück |
| Leeres Passwortfeld beim Speichern | Backend überspringt `mail_password`-Update |
| Falscher SECRET_KEY nach Neustart | Fernet-Entschlüsselung schlägt fehl → Fallback auf .env, Log-Warnung |

---

## Implementierungsreihenfolge

1. Alembic-Migration `003_app_settings`
2. `backend/api/admin_settings.py` (Endpoints + Fernet-Logik)
3. `backend/main.py` — Router einbinden
4. `backend/api/auth.py` — Superadmin Auto-Promotion
5. `backend/tasks.py` — Redis-basierter Settings-Abruf
6. `frontend/src/views/AdminSettings.vue`
7. `frontend/src/router/index.ts` — Route + Guard
8. `frontend/src/views/Dashboard.vue` — ⚙️-Icon
