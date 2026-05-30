# EventFinder Redesign — Design Spec
**Datum:** 2026-05-30  
**Status:** Approved

---

## Überblick

Vollständiges Redesign der EventFinder-App (Vue 3 + FastAPI) mit Premium Dark-Mode-Ästhetik (Glassmorphismus, Neon-Glow, per-Event-Theming) sowie Implementierung aller fehlenden Kernfunktionen: Ort, Teilnehmerverwaltung, Datumsvorschläge mit Abstimmung und Cover-Bild-Upload.

**Zielgruppe:** Freundesgruppen die gemeinsame Events planen  
**Ansatz:** Kompletter Neuaufbau aller Views in einem Zug (Ansatz B), da die App klein genug ist und ein vollständig kohärentes Design erfordert.

---

## Scope

### Enthalten
- Dark-Mode Design-System (Inline-Styles + CSS-Variablen für Akzentfarbe)
- Kompletter Neuaufbau: `Login.vue`, `Dashboard.vue`, `EventDetails.vue`
- Neue Komponenten: `CreateEventModal`, `InviteModal`, `EventHero`, `ParticipantList`, `DateProposals`, `AvailabilityCalendar`
- Neues Composable: `useAuth.ts` (zentralisiertes Token-Handling + 401-Handling)
- Backend: Alembic-Migration (`accent_color`, `cover_image_path`), Cover-Upload-Endpoint, Participants-Endpoint
- Bild-Verarbeitung: Pillow (Resize auf max. 1200px, max. 5 MB Input)

### Explizit ausgeschlossen (Phase 2)
- Echtzeit-Benachrichtigungen (WebSocket)
- Google Maps Integration
- E-Mail-Benachrichtigungen bei Abstimmungsaktivität
- Push-Notifications

---

## Backend-Änderungen

### Migration
```sql
ALTER TABLE events ADD COLUMN accent_color VARCHAR(7) NOT NULL DEFAULT '#06b6d4';
ALTER TABLE events ADD COLUMN cover_image_path VARCHAR(255) NULL;
```

Neue Alembic-Revision: `add_event_theming_fields`

Separate Tabelle für Datumsvorschläge:
```sql
CREATE TABLE date_proposals (
    id UUID PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    proposed_date DATE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(event_id, proposed_date)
);
```
Der Kalender in `EventDetails` zeigt **nur die vom Organisator vorgeschlagenen Daten** zur Abstimmung an. Andere Tage sind nicht anklickbar. Abstimmung läuft weiterhin über die bestehende `availabilities`-Tabelle.

#### `GET /events/{id}/proposals`
- Response: Liste der vorgeschlagenen Daten
- Nur für Event-Teilnehmer sichtbar

#### `POST /events/{id}/proposals`
- Auth: nur Organisator
- Body: `{ dates: ["2026-09-15", "2026-09-16"] }` — ersetzt bisherige Vorschläge komplett

### Neue Endpoints

#### `POST /events/{id}/cover`
- Auth: Bearer Token, nur Organisator des Events
- Body: Multipart `file` (JPEG/PNG/WebP, max. 5 MB)
- Verarbeitung: Pillow resize → max. 1200px Breite, Qualität 85
- Speicherort: `/app/uploads/{uuid4}.{ext}`
- Response: `{ "cover_image_path": "uploads/abc123.jpg" }`
- Fehler: 413 (zu groß), 415 (falsches Format), 403 (nicht Organisator)

#### `GET /events/{id}/participants`
- Auth: Bearer Token, nur Event-Teilnehmer
- Response: Liste von `{ id, name, email, joined_at, availability_count }`

#### `DELETE /events/{id}/cover`
- Auth: Bearer Token, nur Organisator
- Löscht Datei vom Disk + setzt `cover_image_path = NULL`

#### `PATCH /events/{id}`
- Auth: Bearer Token, nur Organisator
- Body: `{ final_date?, accent_color?, location_name?, is_closed? }`
- Bestehender `POST /events/{id}/invite` bleibt unverändert

### Statische Dateien
FastAPI `StaticFiles` mount: `/uploads` → `/app/uploads/`  
Docker-Volume `eventfinder-uploads` gemountet auf `/app/uploads`

### `requirements.txt` Ergänzung
```
Pillow>=10.0.0
python-multipart>=0.0.9
```

---

## Frontend-Struktur

```
src/
├── composables/
│   └── useAuth.ts              ← Token-Getter, axios-Interceptor für 401
├── views/
│   ├── Login.vue               ← Dark Glassmorphismus
│   ├── Dashboard.vue           ← Event-Grid mit Cover-Karten
│   └── EventDetails.vue        ← Hero + 2-Spalten-Layout
└── components/
    ├── EventHero.vue           ← Cover-Bild oder Akzentfarb-Gradient + Overlay
    ├── CreateEventModal.vue    ← Formular mit Ort, Farbe, Daten, Cover
    ├── InviteModal.vue         ← E-Mail-Einladung
    ├── ParticipantList.vue     ← Avatare + Abstimmungsstatus
    ├── DateProposals.vue       ← Datumsvorschläge mit Ampel-Anzeige
    └── AvailabilityCalendar.vue ← Kalender mit Heatmap-Verfügbarkeit
```

---

## Design-System

### Farben (CSS-Variablen)
```css
--bg-base: #080b14
--bg-card: #0d1117
--bg-surface: rgba(255,255,255,0.04)
--border: rgba(255,255,255,0.07)
--border-hover: rgba(255,255,255,0.18)
--text-primary: #ffffff
--text-secondary: rgba(255,255,255,0.45)
--text-muted: rgba(255,255,255,0.2)
--accent: (pro-Event-Variable, default #06b6d4)
```

### Akzentfarben (5 Swatches)
| Name | Hex |
|---|---|
| Cyan (Default) | `#06b6d4` |
| Violet | `#8b5cf6` |
| Rose | `#f43f5e` |
| Amber | `#f59e0b` |
| Emerald | `#10b981` |

### Karten-Stil
- `border-radius: 18px`
- `border: 1px solid var(--border)`
- Hover: `box-shadow: 0 0 32px {accent}44`
- Transition: `all 0.25s`

### Glassmorphismus (Modals/Login)
- `background: rgba(255,255,255,0.04)`
- `backdrop-filter: blur(20px)`
- `border: 1px solid rgba(255,255,255,0.09)`

---

## Komponenten-Details

### `CreateEventModal.vue`
Felder:
1. **Titel** (required, text)
2. **Beschreibung** (optional, textarea)
3. **Ort** (optional, text — Freitext, kein Maps in Phase 1)
4. **Akzentfarbe** (5 Swatches, default Cyan)
5. **Datumsvorschläge** (1–5 Datums-Picker, mindestens 1 required)
6. **Cover-Bild** (optional, File-Input, JPEG/PNG/WebP, max 5 MB — Upload nach Event-Erstellung)

Flow:
1. `POST /events/` → Event-ID
2. Falls Cover gewählt: `POST /events/{id}/cover`
3. Modal schließen, Dashboard aktualisieren

### `EventHero.vue`
Props: `event` (inkl. `cover_image_path`, `accent_color`, `title`, `location_name`, `participants_count`)

Render-Logik:
- Cover vorhanden → `<img>` als Hintergrund + dunkles Overlay
- Kein Cover → Gradient: `linear-gradient(135deg, {accent}22, #080b14)`
- Immer: Glow-Linie am unteren Rand in Akzentfarbe
- Immer: Titel, Ort, Teilnehmeranzahl als Overlay

### `AvailabilityCalendar.vue`
- Ersetzt das bestehende `Calendar.vue`
- Zeigt aggregierte Verfügbarkeit aller Teilnehmer als Heatmap:
  - Alle verfügbar → Grün (`#10b981`)
  - Mehrheit verfügbar → Gelb (`#f59e0b`)
  - Mehrheit nicht verfügbar → Rot (`#f43f5e`)
  - Kein Eintrag → neutral
- Klick auf Tag → eigene Verfügbarkeit setzen (Modal)
- Organisator: Klick mit „Als finales Datum setzen"-Option

### `useAuth.ts`
```ts
export function useAuth() {
  const token = () => localStorage.getItem('token')
  const headers = () => ({ Authorization: `Bearer ${token()}` })
  const logout = () => { localStorage.removeItem('token'); router.push('/login') }
  // axios response interceptor: 401 → logout()
  return { token, headers, logout }
}
```

---

## Fehlerbehandlung

| Szenario | Verhalten |
|---|---|
| 401 (Token abgelaufen) | Automatischer Logout + Redirect `/login` |
| 403 (kein Zugriff auf Event) | Toast-Fehler, zurück zum Dashboard |
| 413 (Bild zu groß) | Inline-Fehler unter Upload-Feld |
| 415 (falsches Format) | Inline-Fehler unter Upload-Feld |
| Netzwerkfehler | Toast-Fehler „Verbindungsproblem" |
| Leerer State | Illustrierter Empty-State mit CTA |

---

## Implementierungsreihenfolge

1. **Backend**: Alembic-Migration + Pillow + Upload-Endpoint + Participants-Endpoint + StaticFiles-Mount + docker-compose Volume
2. **Composable**: `useAuth.ts` + axios-Interceptor
3. **Design-System**: CSS-Variablen in `style.css`
4. **Komponenten**: `EventHero` → `AvailabilityCalendar` → `DateProposals` → `ParticipantList`
5. **Views**: `Login` → `Dashboard` → `EventDetails`
6. **Modals**: `CreateEventModal` → `InviteModal`
7. **Cleanup**: `Mockup.vue` + Route entfernen, altes `Calendar.vue` + `HelloWorld.vue` löschen
