# Event-Bearbeitung & Hintergrundbild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Organisatoren können Titel, Beschreibung, Akzentfarbe und ein Hintergrundbild (mit Blur/Overlay-Slidern) jederzeit über ein neues Edit-Modal bearbeiten.

**Architecture:** Backend erhält 3 neue DB-Spalten via Alembic-Migration und 2 neue Endpoints (POST/DELETE `/background`) nach dem bestehenden Cover-Upload-Pattern. Frontend erweitert EventHero um einen "✏️ Bearbeiten"-Button und EventDetails um das kombinierte Edit-Modal sowie fixierte Hintergrund-Rendering-Schichten mit Live-Preview.

**Tech Stack:** FastAPI, SQLAlchemy async (Mapped), Alembic, Pillow, Vue 3 Composition API, nginx (Multi-Stage Build)

---

## Datei-Übersicht

| Datei | Art | Änderung |
|-------|-----|----------|
| `backend/models.py` | Modify | 3 neue Felder in `Event` |
| `backend/schemas.py` | Modify | `EventPatch` + `EventResponse` erweitern |
| `backend/api/events.py` | Modify | `POST/DELETE /{id}/background` Endpoints |
| `backend/migrations/versions/004_background_image.py` | Create | Alembic-Migration |
| `frontend/src/components/EventHero.vue` | Modify | `editMeta` Emit + Button |
| `frontend/src/views/EventDetails.vue` | Modify | Refs, Funktionen, Hintergrund-Rendering, Edit-Modal |

---

## Task 1: DB-Migration und Model-Update

**Files:**
- Create: `backend/migrations/versions/004_background_image.py`
- Modify: `backend/models.py`

- [ ] **Schritt 1: Alembic-Migrationsdatei anlegen**

Datei `backend/migrations/versions/004_background_image.py` mit folgendem Inhalt erstellen:

```python
"""add background image fields

Revision ID: 004_background_image
Revises: 2b80ad745b7e
Create Date: 2026-06-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '004_background_image'
down_revision: Union[str, Sequence[str], None] = '2b80ad745b7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('events', sa.Column('background_image_path', sa.String(255), nullable=True))
    op.add_column('events', sa.Column('background_blur', sa.SmallInteger(), nullable=False, server_default='4'))
    op.add_column('events', sa.Column('background_overlay', sa.Float(), nullable=False, server_default='0.55'))


def downgrade() -> None:
    op.drop_column('events', 'background_overlay')
    op.drop_column('events', 'background_blur')
    op.drop_column('events', 'background_image_path')
```

- [ ] **Schritt 2: `backend/models.py` — 3 neue Felder in `Event` hinzufügen**

Nach Zeile 73 (`address: Mapped[Optional[str]] = mapped_column(Text)`) einfügen:

```python
    background_image_path: Mapped[Optional[str]] = mapped_column(String(255))
    background_blur: Mapped[int] = mapped_column(Integer, default=4)
    background_overlay: Mapped[float] = mapped_column(Float, default=0.55)
```

- [ ] **Schritt 3: Migration im Container ausführen**

```bash
docker exec eventfinder-backend sh -c "cd /app && alembic upgrade head"
```

Erwartete Ausgabe:
```
INFO  [alembic.runtime.migration] Running upgrade 2b80ad745b7e -> 004_background_image, add background image fields
```

- [ ] **Schritt 4: Felder in DB prüfen**

```bash
docker exec eventfinder-db psql -U eventfinder -d eventfinder -c "\d events" | grep background
```

Erwartete Ausgabe (3 Zeilen):
```
 background_image_path | character varying(255) |
 background_blur       | smallint               |
 background_overlay    | double precision       |
```

- [ ] **Schritt 5: Commit**

```bash
cd /docker/eventfinder
git add backend/models.py backend/migrations/versions/004_background_image.py
git commit -m "feat: add background image fields to Event model and migration"
```

---

## Task 2: Backend — Schemas erweitern

**Files:**
- Modify: `backend/schemas.py`

- [ ] **Schritt 1: `EventPatch` um 2 Felder erweitern**

In `backend/schemas.py`, `EventPatch` (ab Zeile 41) — die zwei neuen Felder anhängen:

```python
class EventPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location_name: Optional[str] = None
    address: Optional[str] = None
    accent_color: Optional[str] = None
    final_date: Optional[date] = None
    is_closed: Optional[bool] = None
    background_blur: Optional[int] = None
    background_overlay: Optional[float] = None
```

- [ ] **Schritt 2: `EventResponse` um 3 Felder erweitern**

`EventResponse` (ab Zeile 50) — die drei neuen Felder anhängen:

```python
class EventResponse(EventBase):
    id: uuid.UUID
    organizer_id: uuid.UUID
    final_date: Optional[date] = None
    is_closed: bool
    cover_image_path: Optional[str] = None
    address: Optional[str] = None
    bundesland: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    background_image_path: Optional[str] = None
    background_blur: int = 4
    background_overlay: float = 0.55
    created_at: datetime
    class Config:
        from_attributes = True
```

- [ ] **Schritt 3: Backend neu starten und Smoke-Test**

```bash
docker restart eventfinder-backend
sleep 3
# JWT minten für Test
JWT=$(docker exec eventfinder-backend python3 -c "
import sys; sys.path.insert(0,'/app')
import auth
print(auth.create_access_token(data={'sub':'82fa16a0-729e-40b3-92c5-f900db2f3a02','email':'bjoern.sander@gmx.de','role':'organizer'}))
")
# EventResponse prüfen — background_blur und background_overlay müssen erscheinen
curl -s -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/events/ | python3 -c "import sys,json; data=json.load(sys.stdin); print(json.dumps({k:data[0].get(k) for k in ['background_image_path','background_blur','background_overlay']}, indent=2))"
```

Erwartete Ausgabe:
```json
{
  "background_image_path": null,
  "background_blur": 4,
  "background_overlay": 0.55
}
```

- [ ] **Schritt 4: Commit**

```bash
cd /docker/eventfinder
git add backend/schemas.py
git commit -m "feat: extend EventPatch and EventResponse with background fields"
```

---

## Task 3: Backend — POST/DELETE /background Endpoints

**Files:**
- Modify: `backend/api/events.py`

- [ ] **Schritt 1: POST /background Endpoint hinzufügen**

In `backend/api/events.py` nach dem bestehenden `delete_cover` Endpoint (nach Zeile 208) einfügen:

```python
@router.post("/{event_id}/background", response_model=schemas.EventResponse)
async def upload_background(
    event_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from PIL import Image
    import io

    event = await _get_event_as_participant(event_id, current_user, db)
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can upload a background")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG, or WebP images are allowed")

    contents = await file.read()
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be smaller than 5 MB")

    img = Image.open(io.BytesIO(contents))
    if img.width > 1920:
        ratio = 1920 / img.width
        img = img.resize((1920, int(img.height * ratio)), Image.LANCZOS)

    ext = file.content_type.split("/")[1].replace("jpeg", "jpg")
    filename = f"bg-{uuid.uuid4()}.{ext}"
    path = f"/app/uploads/{filename}"

    if event.background_image_path:
        old = f"/app/{event.background_image_path}"
        if os.path.exists(old):
            os.remove(old)

    img.save(path, quality=85, optimize=True)
    event.background_image_path = f"uploads/{filename}"
    await db.commit()
    await db.refresh(event)
    return event


@router.delete("/{event_id}/background", status_code=204)
async def delete_background(
    event_id: uuid.UUID,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await _get_event_as_participant(event_id, current_user, db)
    if event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can delete the background")
    if event.background_image_path:
        path = f"/app/{event.background_image_path}"
        if os.path.exists(path):
            os.remove(path)
        event.background_image_path = None
        await db.commit()
```

- [ ] **Schritt 2: Backend neu starten**

```bash
docker restart eventfinder-backend
sleep 3
```

- [ ] **Schritt 3: Smoke-Test Upload**

```bash
JWT=$(docker exec eventfinder-backend python3 -c "
import sys; sys.path.insert(0,'/app')
import auth
print(auth.create_access_token(data={'sub':'82fa16a0-729e-40b3-92c5-f900db2f3a02','email':'bjoern.sander@gmx.de','role':'organizer'}))
")
EVENT_ID="46e2ed97-5a97-4b2d-9f13-cfcfbc33ef03"

# Test mit 1x1 px JPEG
python3 -c "
import io
from PIL import Image
img = Image.new('RGB', (100, 100), color=(30, 40, 80))
img.save('/tmp/test_bg.jpg', 'JPEG')
"
curl -s -X POST \
  -H "Authorization: Bearer $JWT" \
  -F "file=@/tmp/test_bg.jpg;type=image/jpeg" \
  http://127.0.0.1:8000/events/$EVENT_ID/background | python3 -c "import sys,json; d=json.load(sys.stdin); print('background_image_path:', d.get('background_image_path'))"
```

Erwartete Ausgabe: `background_image_path: uploads/bg-<uuid>.jpg`

- [ ] **Schritt 4: Smoke-Test Delete**

```bash
curl -s -o /dev/null -w "%{http_code}" -X DELETE \
  -H "Authorization: Bearer $JWT" \
  http://127.0.0.1:8000/events/$EVENT_ID/background
```

Erwartete Ausgabe: `204`

- [ ] **Schritt 5: Commit**

```bash
cd /docker/eventfinder
git add backend/api/events.py
git commit -m "feat: add POST/DELETE background endpoints for event background image"
```

---

## Task 4: Frontend — EventHero Button

**Files:**
- Modify: `frontend/src/components/EventHero.vue`

- [ ] **Schritt 1: `editMeta` Emit hinzufügen**

In `EventHero.vue` Zeile 17 (`const emit = defineEmits<{`):

```typescript
const emit = defineEmits<{
  invite: []
  editCover: []
  editLocation: []
  editMeta: []
  updateLocation: [value: string]
}>()
```

- [ ] **Schritt 2: "✏️ Bearbeiten"-Button einfügen**

Im Template-Block (Zeile 61–68), den Button-Container für Organisatoren erweitern — `editMeta`-Button vor `editCover` einfügen:

```html
<div v-if="isOrganizer" style="display:flex; flex-direction:column; gap:8px; flex-shrink:0;">
  <button @click="emit('invite')" :style="{
    background: accentColor, boxShadow: `0 0 20px ${accentColor}66`, color: '#000',
    padding: '9px 16px', borderRadius: '10px', border: 'none', cursor: 'pointer',
    fontWeight: 600, fontSize: '13px', whiteSpace: 'nowrap',
  }">+ Einladen</button>
  <button @click="emit('editMeta')" style="background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.7); padding:9px 16px; border-radius:10px; cursor:pointer; font-size:13px; font-weight:500; white-space:nowrap;">✏️ Bearbeiten</button>
  <button @click="emit('editCover')" style="background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.7); padding:9px 16px; border-radius:10px; cursor:pointer; font-size:13px; font-weight:500;">🖼 Cover</button>
</div>
```

- [ ] **Schritt 3: Commit**

```bash
cd /docker/eventfinder
git add frontend/src/components/EventHero.vue
git commit -m "feat: add editMeta emit and button to EventHero"
```

---

## Task 5: Frontend — Hintergrund-Rendering und neue Refs/Funktionen in EventDetails.vue

**Files:**
- Modify: `frontend/src/views/EventDetails.vue`

- [ ] **Schritt 1: Neue Refs nach Zeile 30 (`const showCoverUpload = ref(false)`) einfügen**

```typescript
// --- Hintergrundbild / Event-Meta-Edit ---
const showEditMeta = ref(false)
const editTitle = ref('')
const editDesc = ref('')
const editColor = ref('#06b6d4')
const editBlur = ref(4)
const editOverlay = ref(55)   // 0–100 für den Slider; beim Speichern ÷ 100
const editSaving = ref(false)
```

- [ ] **Schritt 2: Computed-Refs für Live-Preview nach den neuen Refs einfügen**

`computed` ist bereits in Zeile 2 importiert.

```typescript
const bgBlur = computed(() =>
  showEditMeta.value ? editBlur.value : (event.value?.background_blur ?? 4)
)
const bgOverlay = computed(() =>
  showEditMeta.value ? editOverlay.value / 100 : (event.value?.background_overlay ?? 0.55)
)
```

- [ ] **Schritt 3: Vier neue Funktionen nach `uploadCover` (nach Zeile 255) einfügen**

```typescript
function openEditMeta() {
  editTitle.value = event.value?.title ?? ''
  editDesc.value = event.value?.description ?? ''
  editColor.value = event.value?.accent_color ?? '#06b6d4'
  editBlur.value = event.value?.background_blur ?? 4
  editOverlay.value = Math.round((event.value?.background_overlay ?? 0.55) * 100)
  showEditMeta.value = true
}

async function saveEditMeta() {
  editSaving.value = true
  try {
    await axios.patch(`/events/${eventId}`, {
      title: editTitle.value,
      description: editDesc.value || null,
      accent_color: editColor.value,
      background_blur: editBlur.value,
      background_overlay: editOverlay.value / 100,
    }, { headers: headers() })
    showEditMeta.value = false
    await load()
  } catch (e) {
    console.error('Edit meta failed', e)
  } finally {
    editSaving.value = false
  }
}

async function uploadBackground(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const fd = new FormData()
  fd.append('file', file)
  try {
    await axios.post(`/events/${eventId}/background`, fd, { headers: headers() })
    await load()
    editBlur.value = event.value?.background_blur ?? editBlur.value
    editOverlay.value = Math.round((event.value?.background_overlay ?? 0.55) * 100)
  } catch (err) {
    console.error('Background upload failed', err)
  }
}

async function deleteBackground() {
  try {
    await axios.delete(`/events/${eventId}/background`, { headers: headers() })
    await load()
  } catch (err) {
    console.error('Background delete failed', err)
  }
}
```

- [ ] **Schritt 4: `@edit-meta` Wire-up an EventHero in Template (Zeile ~402) hinzufügen**

Die EventHero-Einbindung um `@edit-meta="openEditMeta"` erweitern:

```html
<EventHero
  :title="event.title"
  :description="event.description"
  :location-name="event.location_name"
  :address="event.address"
  :accent-color="event.accent_color"
  :cover-image-path="event.cover_image_path"
  :participant-count="participants.length"
  :is-organizer="isOrganizer"
  @invite="showInvite = true"
  @edit-cover="showCoverUpload = true"
  @edit-meta="openEditMeta"
  @edit-location="locationSearch = event.address || event.location_name || ''"
  @update-location="updateLocation"
  style="margin-bottom:28px;"
/>
```

- [ ] **Schritt 5: Hintergrund-Rendering-Ebenen in Template einfügen**

Direkt nach dem öffnenden `<div style="min-height:100vh; background:var(--bg-base);">` (Zeile 374) einfügen:

```html
<!-- Hintergrundbild-Ebenen (position:fixed, hinter allem) -->
<template v-if="event?.background_image_path">
  <div :style="{
    position: 'fixed', inset: '0', zIndex: '-2',
    backgroundImage: `url(/${event.background_image_path})`,
    backgroundSize: 'cover', backgroundPosition: 'center',
    filter: `blur(${bgBlur}px)`,
    transform: 'scale(1.05)',
    pointerEvents: 'none',
  }" />
  <div :style="{
    position: 'fixed', inset: '0', zIndex: '-1',
    background: `rgba(8,11,20,${bgOverlay})`,
    pointerEvents: 'none',
  }" />
</template>
```

- [ ] **Schritt 6: Commit**

```bash
cd /docker/eventfinder
git add frontend/src/views/EventDetails.vue
git commit -m "feat: add background rendering and edit-meta refs/functions to EventDetails"
```

---

## Task 6: Frontend — Edit-Modal in EventDetails.vue

**Files:**
- Modify: `frontend/src/views/EventDetails.vue`

- [ ] **Schritt 1: Edit-Modal-HTML vor der letzten `</div></template>` (Zeile 787) einfügen**

Das Modal direkt vor dem schließenden `</div>` des Kalender-Einladungs-Modals (nach Zeile 786) einfügen:

```html
    <!-- Edit-Meta-Modal (Titel, Beschreibung, Farbe, Hintergrundbild) -->
    <div v-if="showEditMeta"
      style="position:fixed; inset:0; background:rgba(0,0,0,0.75); display:flex; align-items:center; justify-content:center; padding:16px; z-index:100; backdrop-filter:blur(4px);"
      @click.self="showEditMeta = false">
      <div style="background:#0d1117; border:1px solid rgba(255,255,255,0.1); border-radius:20px; padding:32px; width:100%; max-width:480px; max-height:90vh; overflow-y:auto;">
        <h2 style="font-size:18px; font-weight:700; margin-bottom:24px;">Event bearbeiten</h2>

        <!-- Abschnitt: Inhalt -->
        <p style="font-size:11px; color:rgba(255,255,255,0.35); text-transform:uppercase; letter-spacing:.08em; margin-bottom:14px;">Inhalt</p>

        <label style="font-size:12px; color:rgba(255,255,255,0.45); display:block; margin-bottom:5px;">Titel</label>
        <input v-model="editTitle" maxlength="255" placeholder="Event-Titel"
          style="width:100%; background:rgba(255,255,255,0.07); border:1px solid rgba(255,255,255,0.15); border-radius:8px; padding:9px 14px; color:#fff; font-size:14px; outline:none; box-sizing:border-box; margin-bottom:14px;" />

        <label style="font-size:12px; color:rgba(255,255,255,0.45); display:block; margin-bottom:5px;">Beschreibung <span style="color:rgba(255,255,255,0.2);">(optional)</span></label>
        <textarea v-model="editDesc" rows="3" placeholder="Kurze Beschreibung des Events…"
          style="width:100%; background:rgba(255,255,255,0.07); border:1px solid rgba(255,255,255,0.15); border-radius:8px; padding:9px 14px; color:#fff; font-size:14px; outline:none; box-sizing:border-box; resize:vertical; font-family:inherit; margin-bottom:14px;"></textarea>

        <label style="font-size:12px; color:rgba(255,255,255,0.45); display:block; margin-bottom:8px;">Akzentfarbe</label>
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:24px;">
          <input type="color" v-model="editColor"
            style="width:40px; height:36px; border:none; background:transparent; cursor:pointer; padding:0;" />
          <span style="font-size:13px; color:rgba(255,255,255,0.5); font-family:monospace;">{{ editColor }}</span>
        </div>

        <!-- Abschnitt: Hintergrundbild -->
        <p style="font-size:11px; color:rgba(255,255,255,0.35); text-transform:uppercase; letter-spacing:.08em; margin-bottom:14px; border-top:1px solid rgba(255,255,255,0.08); padding-top:20px;">Hintergrundbild</p>

        <!-- Vorschau + Löschen -->
        <div v-if="event?.background_image_path" style="display:flex; align-items:center; gap:12px; margin-bottom:14px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:10px; padding:10px;">
          <img :src="`/${event.background_image_path}`"
            style="width:64px; height:40px; object-fit:cover; border-radius:6px;" />
          <span style="flex:1; font-size:12px; color:rgba(255,255,255,0.4);">Hintergrundbild gesetzt</span>
          <button @click="deleteBackground"
            style="background:rgba(244,63,94,0.12); border:1px solid rgba(244,63,94,0.3); color:rgba(244,63,94,0.8); padding:5px 10px; border-radius:8px; cursor:pointer; font-size:12px;">
            Löschen
          </button>
        </div>

        <label style="font-size:12px; color:rgba(255,255,255,0.45); display:block; margin-bottom:5px;">
          {{ event?.background_image_path ? 'Neues Bild hochladen' : 'Bild hochladen' }}
        </label>
        <input type="file" accept="image/jpeg,image/png,image/webp" @change="uploadBackground"
          style="width:100%; background:rgba(255,255,255,0.04); border:1.5px dashed rgba(255,255,255,0.15); border-radius:10px; padding:14px; color:rgba(255,255,255,0.5); font-size:13px; cursor:pointer; box-sizing:border-box; margin-bottom:6px;" />
        <p style="font-size:11px; color:rgba(255,255,255,0.25); margin-bottom:20px;">JPEG, PNG oder WebP · max. 5 MB · wird auf max. 1920 px skaliert</p>

        <!-- Blur-Slider -->
        <label style="font-size:12px; color:rgba(255,255,255,0.45); display:flex; justify-content:space-between; margin-bottom:6px;">
          <span>Blur</span>
          <span style="color:rgba(255,255,255,0.6); font-variant-numeric:tabular-nums;">{{ editBlur }} px</span>
        </label>
        <input type="range" min="0" max="20" v-model.number="editBlur"
          style="width:100%; accent-color:var(--accent, #06b6d4); margin-bottom:18px;" />

        <!-- Transparenz-Slider -->
        <label style="font-size:12px; color:rgba(255,255,255,0.45); display:flex; justify-content:space-between; margin-bottom:6px;">
          <span>Overlay-Transparenz</span>
          <span style="color:rgba(255,255,255,0.6); font-variant-numeric:tabular-nums;">{{ editOverlay }} %</span>
        </label>
        <input type="range" min="0" max="100" v-model.number="editOverlay"
          style="width:100%; accent-color:var(--accent, #06b6d4); margin-bottom:28px;" />

        <!-- Aktions-Buttons -->
        <div style="display:flex; justify-content:flex-end; gap:10px;">
          <button @click="showEditMeta = false"
            style="padding:10px 20px; border-radius:10px; background:transparent; border:1px solid rgba(255,255,255,0.12); color:rgba(255,255,255,0.6); cursor:pointer; font-size:14px;">Abbrechen</button>
          <button @click="saveEditMeta" :disabled="!editTitle.trim() || editSaving"
            :style="{
              padding:'10px 24px', borderRadius:'10px', border:'none', fontWeight:600, fontSize:'14px', color:'#000',
              background: event?.accent_color ?? '#06b6d4',
              cursor: (!editTitle.trim() || editSaving) ? 'not-allowed' : 'pointer',
              opacity: (!editTitle.trim() || editSaving) ? 0.6 : 1,
            }">{{ editSaving ? 'Speichere…' : 'Speichern' }}</button>
        </div>
      </div>
    </div>
```

- [ ] **Schritt 2: TypeScript-Build prüfen**

```bash
cd /docker/eventfinder/frontend && npx vue-tsc --noEmit 2>&1 | head -20
```

Erwartete Ausgabe: keine Fehler (leere Ausgabe oder nur Warnungen)

- [ ] **Schritt 3: Commit**

```bash
cd /docker/eventfinder
git add frontend/src/views/EventDetails.vue
git commit -m "feat: add event edit modal with background image, blur and overlay controls"
```

---

## Task 7: Build, Deploy und Abnahme

**Files:**
- Deploy: Docker-Build + Restart

- [ ] **Schritt 1: Frontend bauen und deployen**

```bash
cd /docker/eventfinder
docker compose build frontend
docker compose up -d frontend
```

- [ ] **Schritt 2: Alle Container prüfen**

```bash
docker compose -f /docker/eventfinder/docker-compose.yml ps
```

Erwartete Ausgabe: alle 5 Container `running` — `eventfinder-frontend`, `eventfinder-backend`, `eventfinder-worker`, `eventfinder-db`, `eventfinder-redis`

- [ ] **Schritt 3: Manuelle Abnahme-Checkliste**

Seite `https://eventfinder.thunderbee.uk/event/46e2ed97-5a97-4b2d-9f13-cfcfbc33ef03` aufrufen:

- [ ] Im Hero sind 3 Buttons sichtbar: "+ Einladen", "✏️ Bearbeiten", "🖼 Cover"
- [ ] Klick "✏️ Bearbeiten" öffnet Modal mit Titel, Beschreibung, Akzentfarbe, Hintergrundbild-Bereich, Blur-Slider, Transparenz-Slider
- [ ] Titel- und Beschreibungsfelder sind mit aktuellen Werten vorbelegt
- [ ] Slider "Blur" und "Transparenz" verschieben sofort den Seitenhintergrund (Live-Preview, sofern Bild hochgeladen)
- [ ] Bild hochladen → Vorschau-Thumbnail erscheint im Modal, Hintergrund erscheint auf der Seite
- [ ] "Speichern" sendet PATCH → Modal schließt, Event-Titel im Browser-Tab und Header aktualisiert sich
- [ ] "Löschen" entfernt das Hintergrundbild, Seite sieht wieder aus wie ohne Bild
- [ ] "🖼 Cover" öffnet weiterhin das separate Cover-Modal (unverändert)
- [ ] Teilnehmer (Nicht-Organisator) sehen keinen "✏️ Bearbeiten"-Button

- [ ] **Schritt 4: Git-Tag v1.3.0-beta setzen**

```bash
cd /docker/eventfinder
git tag v1.3.0-beta
```

---

## Selbstreview

**Spec-Abdeckung:**
- ✅ Titel bearbeitbar: Task 6 (Modal, Titel-Input + PATCH)
- ✅ Beschreibung bearbeitbar: Task 6 (Modal, Textarea + PATCH)
- ✅ Coverbild: bereits implementiert, unverändert
- ✅ Hintergrundbild Upload: Task 3 (POST-Endpoint) + Task 6 (Modal-Upload)
- ✅ Hintergrundbild Löschen: Task 3 (DELETE-Endpoint) + Task 6 (Löschen-Button)
- ✅ Blur einstellbar: Task 5 (editBlur-Ref + bgBlur-Computed) + Task 6 (Slider)
- ✅ Transparenz einstellbar: Task 5 (editOverlay-Ref + bgOverlay-Computed) + Task 6 (Slider)
- ✅ Live-Preview: Task 5 (bgBlur/bgOverlay Computed-Refs nutzen showEditMeta)
- ✅ Nur Organisator: Backend 403-Check + Frontend v-if="isOrganizer" in EventHero
- ✅ DB-Migration: Task 1

**Typ-Konsistenz:**
- `editBlur` (ref\<number\>) ↔ `background_blur: Optional[int]` in EventPatch ✅
- `editOverlay / 100` (Float 0.0–1.0) ↔ `background_overlay: Optional[float]` in EventPatch ✅
- `bgBlur` Computed liest `event.value?.background_blur` ↔ `EventResponse.background_blur: int = 4` ✅
- `uploadBackground` / `deleteBackground` nutzen `/events/${eventId}/background` ↔ Task 3 Endpoints ✅
