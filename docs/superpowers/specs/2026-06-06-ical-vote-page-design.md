# Spec: iCal Vote Page — Abstimmung direkt aus Apple Calendar

**Datum:** 2026-06-06  
**Status:** Approved  
**Scope:** EventFinder — `/vote/:eventId` Route + 2 Backend-Endpunkte + iCal-Feed-Erweiterung

---

## Ziel

Jeder Terminvorschlag im iCal-Feed erhält eine `URL:`-Property, die eine mobile-optimierte Abstimmungsseite öffnet. Der User kann direkt aus Apple Calendar heraus für alle Terminvorschläge abstimmen — ohne Login, ohne die EventFinder-App zu öffnen.

---

## Fluss

```
Apple Calendar
  → Termin-Vorschlag antippen
  → URL im Termin antippen
  → Browser öffnet /vote/{event_id}?token={calendar_token}&date={YYYY-MM-DD}

Vote-Seite:
  → Lädt alle Terminvorschläge des Events
  → Eigene bisherige Stimmen vorausgefüllt
  → Tippen auf Button → sofortiger UPSERT in availabilities
  → Abstimmungsstand erscheint direkt darunter
```

Der `calendar_token` ist pro User eindeutig und steckt bereits im iCal-Abo-Link. Kein separates Login, kein Magic-Link nötig.

---

## Backend

### Authentifizierung

Beide neuen Endpunkte akzeptieren `?token={calendar_token}` als Query-Parameter (kein Bearer-Auth). Der Token wird gegen `users.calendar_token` geprüft — gleiche Logik wie der bestehende `/events/{id}/calendar.ics`-Endpunkt.

### Endpunkt 1: GET `/vote/{event_id}`

**Query-Parameter:** `token` (Pflicht)

**Response:**
```json
{
  "event": {
    "id": "uuid",
    "title": "Studententreffen 2026"
  },
  "proposals": [
    {
      "date": "2026-08-15",
      "my_vote": "best",
      "votes": {
        "best":       ["Anna", "Bob"],
        "possible":   ["Clara"],
        "impossible": [],
        "pending":    ["David"]
      }
    }
  ]
}
```

Liefert alle `DateProposal`-Einträge des Events, jeweils mit:
- `my_vote`: Stimme des authentifizierten Users (`"best"` / `"possible"` / `"impossible"` / `null`)
- `votes`: Namen aller Teilnehmer gruppiert nach Status + `pending` (noch nicht abgestimmt)

**Fehlerbehandlung:**
- `401` — ungültiger oder fehlender Token
- `403` — User ist kein Teilnehmer des Events
- `404` — Event nicht gefunden

### Endpunkt 2: POST `/vote/{event_id}/{date}`

**Query-Parameter:** `token` (Pflicht)  
**Path:** `date` im Format `YYYY-MM-DD`  
**Body:**
```json
{ "status": "best" }
```
Erlaubte Werte: `"best"`, `"possible"`, `"impossible"`

**Verhalten:** UPSERT in `availabilities`-Tabelle (UniqueConstraint `participant_id + event_date` existiert bereits). Gibt den aktualisierten Proposals-Stand zurück (gleiche Struktur wie GET-Response, nur `proposals`-Array).

**Fehlerbehandlung:**
- `400` — ungültiger Status-Wert oder ungültiges Datumsformat
- `401` / `403` / `404` — wie oben
- `404` — kein `DateProposal` für dieses Datum in diesem Event

---

## Frontend

### Route

```
/vote/:eventId
```

Kein `requiresAuth`-Guard — Authentifizierung erfolgt via `?token`-Parameter.

### Komponente: `VoteView.vue`

**Kein Navbar, kein Footer** — fokussierte Single-Purpose-Seite.

**Aufbau (von oben nach unten):**

1. **Header** — Event-Titel + „X Terminvorschläge" (cyan, kompakt)
2. **Proposal-Cards** (eine pro Datum):
   - Datum als Überschrift
   - Badge „Dieser Termin" wenn `?date=` übereinstimmt (cyan hervorgehoben)
   - 3 Buttons: **✓ Perfekt** (grün) · **~ Möglich** (gelb) · **✗ Nicht möglich** (rot)
   - Aktiver Button farbig ausgefüllt, inaktive grau
   - Abstimmungsstand darunter: Namen gruppiert nach Status mit Icon-Prefix
3. **Footer** — Link „Alle Details im EventFinder →"

**Interaktion:**
- Tap auf Button → sofortiger `POST /vote/{event_id}/{date}?token=...`
- Optimistic Update: Button wechselt sofort, Stand wird aus Response aktualisiert
- Fehler: Toast-Meldung, Button-State wird zurückgesetzt

**Ladestate:** Spinner auf Card-Ebene beim ersten Load, nicht fullscreen.

**Mobile-first:** Max-Width 480px, Touch-freundliche Button-Größe (min. 44px Höhe).

---

## iCal-Feed-Änderung

In `GET /events/{event_id}/calendar.ics`, für jedes `VEVENT` eines Terminvorschlags wird eine zusätzliche Zeile eingefügt:

```
URL:https://eventfinder.thunderbee.uk/vote/{event_id}?token={calendar_token}&date={YYYY-MM-DD}
```

Die `date`-Parameter entspricht dem jeweiligen `proposed_date` im Format `YYYY-MM-DD`.

**Keine weiteren Änderungen** am Feed — Beschreibung und alle anderen Properties bleiben unverändert.

---

## Datenbankänderungen

Keine. Die bestehende `availabilities`-Tabelle mit `UniqueConstraint("participant_id", "event_date")` reicht aus. Der UPSERT nutzt SQLAlchemy's `merge()` oder ein explizites `ON CONFLICT DO UPDATE`.

---

## Nicht in Scope

- Stimme zurückziehen (kein „Keine Angabe"-Button) — Abstimmung ist immer eine der drei Optionen
- Push-Benachrichtigungen bei neuen Stimmen
- Kommentarfeld pro Datum
- Anzeige von Profilbildern im Abstimmungsstand

---

## Mockup

Interaktiver Mockup verfügbar unter:  
`https://eventfinder.thunderbee.uk/mockup`

(Route `/mockup` in `frontend/src/router/index.ts`, View `MockupView.vue` — nach Feature-Abschluss entfernen)
