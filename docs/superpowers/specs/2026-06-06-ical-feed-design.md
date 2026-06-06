# iCal-Feed Design — EventFinder

**Datum:** 2026-06-06  
**Status:** Approved

## Ziel

Teilnehmer können ein Event als Kalender-Abonnement in Outlook, Apple Calendar und Google Calendar einbinden. Der Organisator kann allen Teilnehmern ihren persönlichen Kalender-Link per E-Mail zuschicken.

---

## Entscheidungen

| Frage | Entscheidung |
|---|---|
| Authentifizierung | Persönlicher, dauerhafter `calendar_token` pro User (in DB) |
| Feed-Scope | Pro Event (eine URL pro Event) |
| Feed-Inhalt | Alle Terminvorschläge als TENTATIVE + Finaltermin als CONFIRMED |
| Organizer-Push | E-Mail an alle Teilnehmer mit persönlicher Webcal-URL |

---

## Datenbank

**Migration 1:** `calendar_token` Feld zur `users`-Tabelle hinzufügen.

```sql
ALTER TABLE users ADD COLUMN calendar_token VARCHAR(64) UNIQUE;
```

- Typ: `String(64)`, nullable, unique
- Wert: `secrets.token_urlsafe(32)`, lazy generiert beim ersten Abruf
- Revoke: Token auf `NULL` setzen → Abo stirbt beim nächsten Sync

**Migration 2:** Optionale Zeitfelder zur `events`-Tabelle hinzufügen.

```sql
ALTER TABLE events ADD COLUMN event_start_time VARCHAR(5);  -- z.B. "14:00"
ALTER TABLE events ADD COLUMN event_end_time   VARCHAR(5);  -- z.B. "18:00"
```

- Typ: `String(5)`, nullable (Format HH:MM)
- Nur für den Finaltermin relevant; Terminvorschläge bleiben immer Ganztages-Einträge
- Gesetzt über bestehenden `PATCH /events/{id}` (neue optionale Felder im Schema)

---

## Backend

### Neue Endpoints

#### `POST /auth/calendar-token`
- **Auth:** JWT Bearer (normaler Login)
- **Verhalten:** Gibt `calendar_token` zurück; generiert ihn lazy falls noch nicht vorhanden
- **Response:** `{ "calendar_token": "..." }`
- **Hinweis:** Das Frontend baut die Webcal-URL selbst: `webcal://<window.location.host>/events/{id}/calendar.ics?token=<token>`

#### `GET /events/{event_id}/calendar.ics?token=<calendar_token>`
- **Auth:** `token` Query-Parameter gegen `users.calendar_token` prüfen — der Token muss existieren und mit einem User übereinstimmen (kein Lazy-Generate hier)
- **Zusatzprüfung:** User muss Teilnehmer des Events sein (`EventParticipant`)
- **Content-Type:** `text/calendar; charset=utf-8`
- **Content-Disposition:** `attachment; filename="event.ics"`
- **Fehler:** 401 bei fehlendem/ungültigem Token, 403 wenn User kein Teilnehmer, 404 wenn Event nicht gefunden

**iCal-Inhalt:**

```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//EventFinder//EventFinder//DE
X-WR-CALNAME:<Event-Titel>
REFRESH-INTERVAL;VALUE=DURATION:PT1H

BEGIN:VEVENT   (pro DateProposal — immer Ganztag)
  UID:proposal-{date}-{event_id}@eventfinder
  DTSTART;VALUE=DATE:{YYYYMMDD}
  DTEND;VALUE=DATE:{YYYYMMDD+1}
  SUMMARY:[Vorschlag] <Event-Titel>
  STATUS:TENTATIVE
  TRANSP:TRANSPARENT
  LOCATION:<Adresse oder location_name>
  DESCRIPTION: Abstimmung:\n✓✓ Perfekt: Anna, Bob\n~ Möglich: Clara\n✗ Nicht möglich: David\n? Ausstehend: Eve
END:VEVENT

BEGIN:VEVENT   (nur wenn final_date gesetzt — ohne Uhrzeit: Ganztag)
  UID:final-{event_id}@eventfinder
  DTSTART;VALUE=DATE:{YYYYMMDD}
  DTEND;VALUE=DATE:{YYYYMMDD+1}
  SUMMARY:<Event-Titel>
  STATUS:CONFIRMED
  TRANSP:OPAQUE
  LOCATION:<Adresse oder location_name>
END:VEVENT

BEGIN:VEVENT   (nur wenn final_date + event_start_time gesetzt — mit Uhrzeit)
  UID:final-{event_id}@eventfinder
  DTSTART:{YYYYMMDD}T{HHMMSS}
  DTEND:{YYYYMMDD}T{HHMMSS}
  SUMMARY:<Event-Titel>
  STATUS:CONFIRMED
  TRANSP:OPAQUE
  LOCATION:<Adresse oder location_name>
END:VEVENT

END:VCALENDAR
```

**Regeln:**
- `REFRESH-INTERVAL:PT1H` — empfiehlt Kalender-Apps stündliche Aktualisierung
- Vorschläge: immer `VALUE=DATE` (Ganztag), unabhängig von `event_start_time`
- Finaltermin ohne Uhrzeit → `VALUE=DATE`; mit Uhrzeit → `DTSTART:{DATE}T{HHMMSS}` (Europe/Berlin, kein UTC-Z damit die lokale Zeit korrekt bleibt)
- Die `DESCRIPTION` jedes Vorschlag-VEVENT enthält die aktuelle Abstimmung aller Teilnehmer (Namen nach Status gruppiert, Ausstehende am Ende)
- Beim Setzen des Finaltermins bleibt die `final-{event_id}` UID stabil → Kalender aktualisiert statt doppelten Eintrag anzulegen
- Wird ein Teilnehmer via `DELETE /events/{id}/participants/{user_id}` entfernt, schlägt der Teilnehmer-Check im `.ics`-Endpoint fehl (403) → Abo stirbt beim nächsten automatischen Sync

#### `POST /events/{event_id}/send-calendar-links`
- **Auth:** JWT Bearer, nur Organizer
- **Verhalten:** Startet Celery-Task `send_calendar_subscription_emails`
- **Response:** `{ "message": "Kalender-Links werden versendet" }`

### Neuer Celery-Task: `send_calendar_subscription_emails`

- Iteriert über alle `EventParticipant` des Events
- Pro Teilnehmer: generiert/holt `calendar_token` lazy
- Baut persönliche Webcal-URL: `webcal://<FRONTEND_URL_HOST>/events/{event_id}/calendar.ics?token=<token>`
- Sendet E-Mail mit:
  - Direktem `webcal://`-Link
  - `https://`-Fallback-URL (für Browser-Download)
  - Kurzanleitung für Google Calendar, Outlook, Apple Calendar
  - Hinweis: "Dieser Link ist persönlich — bitte nicht weitergeben"

---

## Frontend

### `EventDetails.vue` — Für alle Teilnehmer

**"Kalender abonnieren"-Sektion** (Toggle/Aufklapper):

1. User klickt "Kalender abonnieren"
2. Frontend ruft `POST /auth/calendar-token` auf
3. Zeigt Webcal-URL an
4. Zwei Buttons:
   - **"In Kalender öffnen"** → öffnet `webcal://`-URL (triggert Kalender-App)
   - **"URL kopieren"** → URL in Clipboard

Hinweistext unter der URL:
> "Diese URL ist persönlich — teile sie nicht. Google Calendar: Andere Kalender → Per URL. Outlook: Kalender hinzufügen → Aus dem Internet. Apple Calendar: Ablage → Kalenderabonnement."

### `EventDetails.vue` — Nur für Organizer

**"Kalender-Link an alle senden"-Button** (neben oder unterhalb der Abonnieren-Sektion):
- Ruft `POST /events/{event_id}/send-calendar-links` auf
- Zeigt kurz "Wird gesendet..." → "Versendet!" Bestätigung

---

## Dateien die geändert werden

| Datei | Änderung |
|---|---|
| `backend/models.py` | `calendar_token` Feld zu `User` |
| `backend/migrations/versions/xxxx_add_calendar_token.py` | Alembic-Migration |
| `backend/api/auth.py` | `POST /auth/calendar-token` Endpoint |
| `backend/api/events.py` | `GET /{id}/calendar.ics` + `POST /{id}/send-calendar-links` |
| `backend/schemas.py` | `EventPatch` um `event_start_time` / `event_end_time` erweitern |
| `backend/tasks.py` | `send_calendar_subscription_emails` Celery-Task |
| `frontend/src/views/EventDetails.vue` | Abonnieren-Sektion + Organizer-Push-Button |

---

## Frontend — Uhrzeit-Eingabe (Organizer)

Im Organizer-Bereich von `EventDetails.vue` (wo auch Finaltermin gesetzt wird):
- Zwei optionale Zeitfelder: "Beginn" und "Ende" (HH:MM, type="time")
- Nur sichtbar/aktiv wenn `final_date` gesetzt ist
- Speichern via `PATCH /events/{id}` mit `event_start_time` / `event_end_time`
- Hinweis: "Ohne Uhrzeit wird ein Ganztages-Termin im Kalender eingetragen"

---

## Nicht im Scope

- Token widerrufen / rotieren (UI dafür)
- Feed für alle Events eines Users (separates Feature)
- WhatsApp-Versand
- Uhrzeit für Terminvorschläge (nur Finaltermin bekommt Uhrzeit)
