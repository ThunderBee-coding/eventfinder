# iCal Vote Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jeder Terminvorschlag im iCal-Feed bekommt eine URL, die eine mobile-optimierte Abstimmungsseite öffnet — Nutzer können direkt aus Apple Calendar für alle Termine abstimmen, ohne Login.

**Architecture:** Neuer FastAPI-Router `vote.py` mit zwei Endpunkten (GET + POST), beide authentifiziert via `calendar_token` Query-Parameter. Frontend `VoteView.vue` ersetzt den Mockup. iCal-Feed in `events.py` bekommt eine `URL:`-Property pro VEVENT.

**Tech Stack:** FastAPI + SQLAlchemy (async) + Vue 3 (Composition API) — alle bereits im Projekt vorhanden.

---

## File Map

| Aktion | Datei | Zweck |
|---|---|---|
| Create | `backend/api/vote.py` | GET + POST `/vote/{event_id}` Endpunkte |
| Modify | `backend/schemas.py` | Neue Schemas: VoteRequest, VotePageResponse |
| Modify | `backend/main.py` | Vote-Router registrieren |
| Modify | `backend/api/events.py` | URL-Property im iCal-VEVENT ergänzen |
| Modify | `frontend/src/views/MockupView.vue` | → Zur echten VoteView umschreiben |
| Modify | `frontend/src/router/index.ts` | `/vote/:eventId` Route (kein Auth-Guard), Mockup-Route entfernen |

---

## Task 1: Backend — Neue Schemas in `schemas.py`

**Files:**
- Modify: `backend/schemas.py`

- [ ] **Schritt 1: Schemas am Ende von `backend/schemas.py` hinzufügen**

```python
# --- Vote Page Schemas ---

class VoteRequest(BaseModel):
    status: AvailabilityStatus  # "best" | "possible" | "impossible"

class VoteStatusEntry(BaseModel):
    best: List[str] = []
    possible: List[str] = []
    impossible: List[str] = []
    pending: List[str] = []

class ProposalVoteState(BaseModel):
    date: date
    my_vote: Optional[str] = None  # "best" | "possible" | "impossible" | None
    votes: VoteStatusEntry

class VoteEventInfo(BaseModel):
    id: uuid.UUID
    title: str

class VotePageResponse(BaseModel):
    event: VoteEventInfo
    proposals: List[ProposalVoteState]
```

- [ ] **Schritt 2: Prüfen ob alle Imports vorhanden**

`AvailabilityStatus` ist bereits in `schemas.py` definiert. `date` kommt aus `from datetime import date` — prüfen ob das bereits importiert ist:

```bash
grep "from datetime" /docker/eventfinder/backend/schemas.py
```

Falls `date` fehlt: `from datetime import date` oben ergänzen.

- [ ] **Schritt 3: Commit**

```bash
cd /docker/eventfinder
git add backend/schemas.py
git commit -m "feat: add VoteRequest, VotePageResponse schemas"
```

---

## Task 2: Backend — Vote Router (`backend/api/vote.py`)

**Files:**
- Create: `backend/api/vote.py`

- [ ] **Schritt 1: `backend/api/vote.py` erstellen**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date as date_type
import uuid

from database import get_db
import models
import schemas

router = APIRouter()


async def _get_user_and_participant(
    event_id: uuid.UUID,
    token: str,
    db: AsyncSession,
) -> tuple[models.User, models.EventParticipant]:
    """Gemeinsame Auth-Logik für beide Vote-Endpunkte."""
    user_result = await db.execute(
        select(models.User).where(models.User.calendar_token == token)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid calendar token")

    part_result = await db.execute(
        select(models.EventParticipant)
        .where(models.EventParticipant.event_id == event_id)
        .where(models.EventParticipant.user_id == user.id)
    )
    participant = part_result.scalar_one_or_none()
    if not participant:
        raise HTTPException(status_code=403, detail="Not a participant of this event")

    return user, participant


async def _build_proposals_response(
    event_id: uuid.UUID,
    my_participant_id: uuid.UUID,
    db: AsyncSession,
) -> list[schemas.ProposalVoteState]:
    """Baut die Proposals-Liste mit Abstimmungsstand für die Response."""
    # Alle Terminvorschläge des Events
    prop_result = await db.execute(
        select(models.DateProposal)
        .where(models.DateProposal.event_id == event_id)
        .order_by(models.DateProposal.proposed_date)
    )
    proposals = prop_result.scalars().all()

    # Alle Teilnehmer mit Namen
    parts_result = await db.execute(
        select(models.User, models.EventParticipant)
        .join(models.EventParticipant, models.User.id == models.EventParticipant.user_id)
        .where(models.EventParticipant.event_id == event_id)
    )
    participants = parts_result.all()
    ep_to_name = {ep.id: u.name for u, ep in participants}
    all_ep_ids = {ep.id for _, ep in participants}

    # Alle Availabilities des Events
    avail_result = await db.execute(
        select(models.Availability)
        .join(models.EventParticipant, models.EventParticipant.id == models.Availability.participant_id)
        .where(models.EventParticipant.event_id == event_id)
    )
    availabilities = avail_result.scalars().all()

    result = []
    for p in proposals:
        day_avails = [a for a in availabilities if a.event_date == p.proposed_date]
        voted_ep_ids = {a.participant_id for a in day_avails}

        my_avail = next((a for a in day_avails if a.participant_id == my_participant_id), None)
        my_vote = my_avail.status.value if my_avail else None

        result.append(schemas.ProposalVoteState(
            date=p.proposed_date,
            my_vote=my_vote,
            votes=schemas.VoteStatusEntry(
                best=[ep_to_name.get(a.participant_id, "?") for a in day_avails if a.status.value == "best"],
                possible=[ep_to_name.get(a.participant_id, "?") for a in day_avails if a.status.value == "possible"],
                impossible=[ep_to_name.get(a.participant_id, "?") for a in day_avails if a.status.value == "impossible"],
                pending=[ep_to_name.get(ep_id, "?") for ep_id in all_ep_ids if ep_id not in voted_ep_ids],
            ),
        ))
    return result


@router.get("/{event_id}", response_model=schemas.VotePageResponse)
async def get_vote_page(
    event_id: uuid.UUID,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    user, participant = await _get_user_and_participant(event_id, token, db)

    ev_result = await db.execute(select(models.Event).where(models.Event.id == event_id))
    event = ev_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    proposals = await _build_proposals_response(event_id, participant.id, db)

    return schemas.VotePageResponse(
        event=schemas.VoteEventInfo(id=event.id, title=event.title),
        proposals=proposals,
    )


@router.post("/{event_id}/{vote_date}", response_model=list[schemas.ProposalVoteState])
async def post_vote(
    event_id: uuid.UUID,
    vote_date: date_type,
    vote_in: schemas.VoteRequest,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    user, participant = await _get_user_and_participant(event_id, token, db)

    # Prüfen ob DateProposal für dieses Datum existiert
    prop_result = await db.execute(
        select(models.DateProposal)
        .where(models.DateProposal.event_id == event_id)
        .where(models.DateProposal.proposed_date == vote_date)
    )
    if not prop_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="No proposal found for this date")

    # UPSERT: bestehende Availability suchen
    avail_result = await db.execute(
        select(models.Availability)
        .where(models.Availability.participant_id == participant.id)
        .where(models.Availability.event_date == vote_date)
    )
    existing = avail_result.scalar_one_or_none()

    if existing:
        existing.status = vote_in.status
    else:
        db.add(models.Availability(
            participant_id=participant.id,
            event_date=vote_date,
            status=vote_in.status,
        ))

    await db.commit()

    return await _build_proposals_response(event_id, participant.id, db)
```

- [ ] **Schritt 2: Commit**

```bash
cd /docker/eventfinder
git add backend/api/vote.py
git commit -m "feat: add vote router with GET/POST endpoints (calendar_token auth)"
```

---

## Task 3: Vote Router in `main.py` registrieren

**Files:**
- Modify: `backend/main.py`

- [ ] **Schritt 1: Import und `include_router` ergänzen**

In `backend/main.py` nach der Zeile `from api import geocode as api_geocode`:

```python
from api import vote as api_vote
```

Und nach `app.include_router(api_geocode.router, tags=["geocode"])`:

```python
app.include_router(api_vote.router, prefix="/vote", tags=["vote"])
```

- [ ] **Schritt 2: Endpunkt manuell testen**

```bash
# Token aus DB holen
docker exec eventfinder-db psql -U eventfinder -d eventfinder \
  -c "SELECT calendar_token FROM users WHERE email = 'thunderbee732@gmail.com';"

# GET testen (TOKEN durch echten Wert ersetzen)
EVENT_ID=$(docker exec eventfinder-db psql -U eventfinder -d eventfinder -t \
  -c "SELECT id FROM events LIMIT 1;" | tr -d ' ')
TOKEN="<calendar_token aus DB>"

curl -s "http://127.0.0.1:8000/vote/${EVENT_ID}?token=${TOKEN}" | python3 -m json.tool
```

Erwartete Ausgabe: JSON mit `event.title` und `proposals`-Array.

```bash
# Fehlerfall testen
curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000/vote/${EVENT_ID}?token=falscher-token"
# Erwartet: 401
```

- [ ] **Schritt 3: POST testen**

```bash
DATE=$(docker exec eventfinder-db psql -U eventfinder -d eventfinder -t \
  -c "SELECT proposed_date FROM date_proposals LIMIT 1;" | tr -d ' ')

curl -s -X POST \
  "http://127.0.0.1:8000/vote/${EVENT_ID}/${DATE}?token=${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"status": "best"}' | python3 -m json.tool
```

Erwartet: Array von ProposalVoteState mit aktualisiertem `my_vote: "best"`.

- [ ] **Schritt 4: Commit**

```bash
cd /docker/eventfinder
git add backend/main.py
git commit -m "feat: register vote router at /vote prefix"
```

---

## Task 4: iCal-Feed — URL-Property pro VEVENT

**Files:**
- Modify: `backend/api/events.py` (Zeilen ~689–725, im VEVENT-Block der Terminvorschläge)

- [ ] **Schritt 1: `base_url` aus app_settings lesen**

In `backend/api/events.py`, in der Funktion `get_calendar_feed`, direkt nach dem `if not part_result.scalar_one_or_none():` Block:

```python
    # Frontend-URL für Vote-Links aus app_settings lesen
    settings_result = await db.execute(select(models.AppSettings))
    app_settings_row = settings_result.scalar_one_or_none()
    frontend_url = (app_settings_row.settings.get("frontend_url", "https://eventfinder.thunderbee.uk") if app_settings_row else "https://eventfinder.thunderbee.uk").rstrip("/")
```

- [ ] **Schritt 2: `URL:`-Property im VEVENT ergänzen**

Im selben `get_calendar_feed`, im `for p in proposals:` Block, direkt vor `"END:VEVENT"`:

```python
        # Vote-URL für diesen Terminvorschlag
        date_param = d.strftime("%Y-%m-%d")
        vote_url = f"{frontend_url}/vote/{event_id}?token={token}&date={date_param}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:proposal-{date_str}-{event_id}@eventfinder",
            f"DTSTART;VALUE=DATE:{date_str}",
            f"DTEND;VALUE=DATE:{next_day}",
            f"SUMMARY:[Vorschlag] {title}",
            "STATUS:TENTATIVE",
            "TRANSP:TRANSPARENT",
            f"LOCATION:{location}",
            f"DESCRIPTION:{description}",
            f"URL:{vote_url}",
            "END:VEVENT",
        ]
```

Achtung: Die bestehenden `lines +=`-Blöcke für Vorschläge **ersetzen**, nicht doppelt anhängen.

- [ ] **Schritt 3: iCal-Feed testen**

```bash
TOKEN="<calendar_token aus DB>"
EVENT_ID="<event_id>"

curl -s "http://127.0.0.1:8000/events/${EVENT_ID}/calendar.ics?token=${TOKEN}" | grep "URL:"
```

Erwartet: `URL:https://eventfinder.thunderbee.uk/vote/...?token=...&date=...` pro Vorschlag.

- [ ] **Schritt 4: Commit**

```bash
cd /docker/eventfinder
git add backend/api/events.py
git commit -m "feat: add URL property to iCal VEVENT proposals for vote page"
```

---

## Task 5: Frontend — `VoteView.vue` (echte Implementierung)

**Files:**
- Modify: `frontend/src/views/MockupView.vue` → Inhalt durch echte Implementierung ersetzen

Der Mockup-View wird direkt zur echten `VoteView` umgeschrieben (gleicher Dateiname, kein Copy).

- [ ] **Schritt 1: `MockupView.vue` mit echter Implementierung überschreiben**

```vue
<template>
  <div class="vote-root">
    <!-- Ladestate -->
    <div v-if="loading" class="loading">
      <div class="spinner" />
    </div>

    <!-- Fehler -->
    <div v-else-if="error" class="error-state">
      <div style="font-size:48px;margin-bottom:16px">⚠️</div>
      <h2>{{ error }}</h2>
      <a :href="eventLink" style="color:#06b6d4;margin-top:16px;display:block">Zum EventFinder →</a>
    </div>

    <!-- Inhalt -->
    <template v-else-if="data">
      <div class="header">
        <div class="event-title">{{ data.event.title }}</div>
        <div class="event-sub">{{ data.proposals.length }} Terminvorschläge</div>
      </div>

      <div class="proposals">
        <div
          v-for="p in data.proposals"
          :key="String(p.date)"
          class="card"
          :class="{ highlighted: String(p.date) === highlightDate }"
        >
          <div class="date-label">
            <span class="date-text">{{ formatDate(p.date) }}</span>
            <span v-if="String(p.date) === highlightDate" class="badge">Dieser Termin</span>
          </div>

          <div class="vote-buttons">
            <button
              v-for="opt in options"
              :key="opt.value"
              class="vote-btn"
              :class="[opt.cls, { active: p.my_vote === opt.value }, { loading: votingDate === String(p.date) }]"
              :disabled="votingDate === String(p.date)"
              @click="castVote(p, opt.value)"
            >
              <span class="btn-icon">{{ opt.icon }}</span>
              <span class="btn-label">{{ opt.label }}</span>
            </button>
          </div>

          <div class="vote-status">
            <div v-if="p.votes.best.length" class="status-row best">
              <span class="status-icon">✓</span>
              <span class="names">{{ p.votes.best.join(', ') }}</span>
            </div>
            <div v-if="p.votes.possible.length" class="status-row possible">
              <span class="status-icon">~</span>
              <span class="names">{{ p.votes.possible.join(', ') }}</span>
            </div>
            <div v-if="p.votes.impossible.length" class="status-row impossible">
              <span class="status-icon">✗</span>
              <span class="names">{{ p.votes.impossible.join(', ') }}</span>
            </div>
            <div v-if="p.votes.pending.length" class="status-row pending">
              <span class="status-icon">⏳</span>
              <span class="names">{{ p.votes.pending.join(', ') }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Toast -->
      <div v-if="toast" class="toast" :class="toast.type">{{ toast.msg }}</div>

      <div class="footer-link">
        <a :href="eventLink">Alle Details im EventFinder →</a>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const eventId = computed(() => route.params.eventId as string)
const token = computed(() => route.query.token as string)
const highlightDate = computed(() => route.query.date as string ?? '')
const eventLink = computed(() => `/event/${eventId.value}`)

interface VoteStatusEntry { best: string[]; possible: string[]; impossible: string[]; pending: string[] }
interface ProposalVoteState { date: string; my_vote: string | null; votes: VoteStatusEntry }
interface VotePageResponse { event: { id: string; title: string }; proposals: ProposalVoteState[] }

const data = ref<VotePageResponse | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const votingDate = ref<string | null>(null)
const toast = ref<{ msg: string; type: 'success' | 'error' } | null>(null)

const options = [
  { value: 'best',       icon: '✓', label: 'Perfekt',        cls: 'btn-best' },
  { value: 'possible',   icon: '~', label: 'Möglich',        cls: 'btn-possible' },
  { value: 'impossible', icon: '✗', label: 'Nicht möglich',  cls: 'btn-impossible' },
]

function formatDate(d: string): string {
  const dt = new Date(d + 'T00:00:00')
  return dt.toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' })
}

function showToast(msg: string, type: 'success' | 'error') {
  toast.value = { msg, type }
  setTimeout(() => { toast.value = null }, 3000)
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch(`/vote/${eventId.value}?token=${token.value}`)
    if (!res.ok) {
      error.value = res.status === 401 ? 'Ungültiger Link — bitte neuen Kalender-Link anfordern.' : 'Fehler beim Laden.'
      return
    }
    data.value = await res.json()
  } catch {
    error.value = 'Keine Verbindung zum Server.'
  } finally {
    loading.value = false
  }
}

async function castVote(proposal: ProposalVoteState, status: string) {
  if (votingDate.value) return
  votingDate.value = String(proposal.date)
  const prevVote = proposal.my_vote
  proposal.my_vote = status  // Optimistic update

  try {
    const res = await fetch(`/vote/${eventId.value}/${proposal.date}?token=${token.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    })
    if (!res.ok) throw new Error('Fehler')
    const updatedProposals: ProposalVoteState[] = await res.json()
    if (data.value) data.value.proposals = updatedProposals
    showToast('Stimme gespeichert ✓', 'success')
  } catch {
    proposal.my_vote = prevVote  // Rollback
    showToast('Fehler beim Speichern — bitte erneut versuchen.', 'error')
  } finally {
    votingDate.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.vote-root {
  min-height: 100vh;
  background: #080b14;
  color: #fff;
  font-family: system-ui, sans-serif;
  padding: 0 0 60px;
  max-width: 480px;
  margin: 0 auto;
}
.loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 60vh;
}
.spinner {
  width: 36px; height: 36px;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: #06b6d4;
  border-radius: 50%;
  animation: spin .8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.error-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; height: 60vh; text-align: center; padding: 24px;
}
.header {
  padding: 28px 20px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.event-title { font-size: 20px; font-weight: 700; color: #06b6d4; }
.event-sub   { font-size: 13px; color: rgba(255,255,255,0.45); margin-top: 4px; }
.proposals   { display: flex; flex-direction: column; gap: 12px; padding: 16px; }
.card {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px; padding: 16px;
}
.card.highlighted { border-color: #06b6d4; background: rgba(6,182,212,0.06); }
.date-label  { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.date-text   { font-size: 15px; font-weight: 600; }
.badge       { font-size: 11px; padding: 2px 8px; border-radius: 20px; background: rgba(6,182,212,0.2); color: #06b6d4; font-weight: 500; }
.vote-buttons { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 14px; }
.vote-btn {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 12px 4px; min-height: 60px;
  border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.04);
  color: rgba(255,255,255,0.5); cursor: pointer;
  transition: all .15s; font-size: 12px;
}
.vote-btn:disabled { opacity: 0.6; cursor: wait; }
.btn-icon  { font-size: 18px; }
.btn-label { font-size: 11px; font-weight: 500; }
.btn-best.active      { background: rgba(16,185,129,0.2); border-color: #10b981; color: #10b981; }
.btn-possible.active  { background: rgba(245,158,11,0.2); border-color: #f59e0b; color: #f59e0b; }
.btn-impossible.active{ background: rgba(239,68,68,0.2);  border-color: #ef4444; color: #ef4444; }
.vote-status { display: flex; flex-direction: column; gap: 4px; }
.status-row  { display: flex; align-items: baseline; gap: 8px; font-size: 12px; }
.status-icon { font-size: 11px; min-width: 14px; }
.names       { color: rgba(255,255,255,0.55); }
.best       .status-icon { color: #10b981; }
.possible   .status-icon { color: #f59e0b; }
.impossible .status-icon { color: #ef4444; }
.pending    .status-icon { color: rgba(255,255,255,0.3); }
.toast {
  position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
  padding: 10px 20px; border-radius: 20px; font-size: 13px;
  font-weight: 500; white-space: nowrap; z-index: 999;
}
.toast.success { background: rgba(16,185,129,0.9); color: #fff; }
.toast.error   { background: rgba(239,68,68,0.9);  color: #fff; }
.footer-link   { text-align: center; padding: 16px 0 0; }
.footer-link a { color: rgba(6,182,212,0.7); font-size: 13px; text-decoration: none; }
</style>
```

- [ ] **Schritt 2: Commit**

```bash
cd /docker/eventfinder
git add frontend/src/views/MockupView.vue
git commit -m "feat: implement VoteView with real API, optimistic updates, toast feedback"
```

---

## Task 6: Frontend Router — Route umbenennen, Mockup entfernen

**Files:**
- Modify: `frontend/src/router/index.ts`

- [ ] **Schritt 1: Router aktualisieren**

In `frontend/src/router/index.ts` die MockupView-Einträge ersetzen:

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Dashboard from '../views/Dashboard.vue'
import EventDetails from '../views/EventDetails.vue'
import AdminSettings from '../views/AdminSettings.vue'
import VoteView from '../views/MockupView.vue'   // Datei heißt noch MockupView.vue

const routes = [
  { path: '/login', name: 'Login', component: Login },
  { path: '/', name: 'Dashboard', component: Dashboard, meta: { requiresAuth: true } },
  { path: '/event/:id', name: 'EventDetails', component: EventDetails, meta: { requiresAuth: true } },
  { path: '/admin/settings', name: 'AdminSettings', component: AdminSettings, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/vote/:eventId', name: 'VoteView', component: VoteView },
]
```

Hinweis: Die Vue-Datei heißt weiterhin `MockupView.vue` — nur der Import-Alias und die Route ändern sich. Ein Umbenennen der Datei wäre optional, ist aber kein Blocker.

- [ ] **Schritt 2: Frontend bauen und deployen**

```bash
cd /docker/eventfinder
docker compose build frontend
docker compose up -d frontend
```

Erwartete Ausgabe: `Container eventfinder-frontend Started`

- [ ] **Schritt 3: Vote-Route testen**

```bash
# calendar_token aus DB holen
TOKEN=$(docker exec eventfinder-db psql -U eventfinder -d eventfinder -t \
  -c "SELECT calendar_token FROM users WHERE email = 'thunderbee732@gmail.com';" | tr -d ' ')
EVENT_ID=$(docker exec eventfinder-db psql -U eventfinder -d eventfinder -t \
  -c "SELECT id FROM events LIMIT 1;" | tr -d ' ')
DATE=$(docker exec eventfinder-db psql -U eventfinder -d eventfinder -t \
  -c "SELECT proposed_date FROM date_proposals LIMIT 1;" | tr -d ' ')

echo "Vote-URL: https://eventfinder.thunderbee.uk/vote/${EVENT_ID}?token=${TOKEN}&date=${DATE}"
curl -s -o /dev/null -w "%{http_code}" \
  "https://eventfinder.thunderbee.uk/vote/${EVENT_ID}?token=${TOKEN}&date=${DATE}"
```

Erwartet: `200` (Vue SPA-Route, kein Auth-Guard)

- [ ] **Schritt 4: Commit**

```bash
cd /docker/eventfinder
git add frontend/src/router/index.ts
git commit -m "feat: add /vote/:eventId route, remove /mockup route"
```

---

## Task 7: End-to-End Test

- [ ] **Schritt 1: Vote-URL aus iCal-Feed extrahieren**

```bash
TOKEN=$(docker exec eventfinder-db psql -U eventfinder -d eventfinder -t \
  -c "SELECT calendar_token FROM users WHERE email = 'thunderbee732@gmail.com';" | tr -d ' ')
EVENT_ID=$(docker exec eventfinder-db psql -U eventfinder -d eventfinder -t \
  -c "SELECT id FROM events LIMIT 1;" | tr -d ' ')

curl -s "http://127.0.0.1:8000/events/${EVENT_ID}/calendar.ics?token=${TOKEN}" | grep "^URL:"
```

Erwartet: Eine `URL:`-Zeile pro Terminvorschlag, jeweils auf `/vote/...` zeigend.

- [ ] **Schritt 2: Vote-Seite im Browser öffnen**

Die URL aus Schritt 1 direkt aufrufen: `https://eventfinder.thunderbee.uk/vote/{event_id}?token={token}&date={YYYY-MM-DD}`

Erwartetes Ergebnis:
- Seite lädt ohne Login
- Event-Titel und Terminvorschläge sichtbar
- Hervorgehobener Termin hat `„Dieser Termin"`-Badge
- Eigene bisherige Stimmen sind vorausgefüllt

- [ ] **Schritt 3: Abstimmung testen**

Einen Button antippen → Stimme wechselt sofort → Toast „Stimme gespeichert ✓" erscheint → Abstimmungsstand aktualisiert sich.

- [ ] **Schritt 4: Fehlerfall testen**

```bash
curl -s -o /dev/null -w "%{http_code}" \
  "https://eventfinder.thunderbee.uk/vote/${EVENT_ID}?token=falscher-token"
```

Erwartet: Vue-Seite zeigt Fehlermeldung „Ungültiger Link…" (kein leerer Bildschirm, kein 500er).

- [ ] **Schritt 5: Finaler Commit**

```bash
cd /docker/eventfinder
git add -A
git commit -m "feat: complete iCal vote page — abstimmung direkt aus Apple Calendar"
git push origin master
```
