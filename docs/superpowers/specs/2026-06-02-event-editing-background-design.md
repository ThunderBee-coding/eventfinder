# Design: Event-Bearbeitung & Hintergrundbild (v1.3.0)

**Datum:** 2026-06-02  
**Status:** Genehmigt  
**Version:** v1.3.0

## Ziel

Der Organisator soll Titel, Beschreibung und Coverbild eines Events jederzeit ändern können. Zusätzlich erhält jedes Event ein optionales Hintergrundbild (Seiten-Hintergrund), dessen Blur-Stärke und Overlay-Transparenz vom Organisator frei einstellbar sind.

## Scope

- Titel, Beschreibung, Akzentfarbe: bearbeitbar über neues Edit-Modal
- Hintergrundbild: eigener Upload/Lösch-Endpoint, Slider für Blur (0–20 px) und Overlay-Transparenz (0–100 %)
- Cover-Bild-Upload: bleibt unverändert über bestehenden "🖼 Cover"-Button
- Alle Edit-Funktionen sind ausschließlich für den Organisator sichtbar und zugänglich

## Backend

### DB-Migration

Drei neue Spalten in der Tabelle `events`:

| Spalte | Typ | Default | Bedeutung |
|--------|-----|---------|-----------|
| `background_image_path` | `VARCHAR(255)` | `NULL` | Pfad wie `uploads/bg-uuid.jpg` |
| `background_blur` | `SMALLINT` | `4` | Blur-Stärke in px (0–20) |
| `background_overlay` | `FLOAT` | `0.55` | Overlay-Deckkraft (0.0–1.0) |

Migration als Alembic-Skript, idempotent mit `IF NOT EXISTS`-Logik.

### Neue Endpoints

**`POST /events/{id}/background`**
- Nur Organisator
- Validierung: JPEG/PNG/WebP, max. 5 MB
- Resize auf max. 1920 px Breite (Pillow, LANCZOS)
- Altes `background_image_path`-Bild von Disk löschen
- Datei in `/app/uploads/bg-{uuid}.{ext}` speichern
- Gibt `EventResponse` zurück

**`DELETE /events/{id}/background`**
- Nur Organisator
- Datei von Disk löschen, Feld auf `null` setzen
- Status 204

### PATCH-Erweiterung

`EventPatch` (schemas.py) erhält zwei neue optionale Felder:

```python
background_blur: Optional[int] = None     # 0–20
background_overlay: Optional[float] = None  # 0.0–1.0
```

Slider-Änderungen werden über den bestehenden `PATCH /events/{id}` gespeichert.

### EventResponse-Erweiterung

`EventResponse` erhält drei neue Felder:

```python
background_image_path: Optional[str] = None
background_blur: int = 4
background_overlay: float = 0.55
```

## Frontend

### EventHero — neuer Button

Neben "🖼 Cover" wird ein "✏️ Bearbeiten"-Button für Organisatoren hinzugefügt:

```
[+ Einladen]  [✏️ Bearbeiten]  [🖼 Cover]
```

Klick emittiert `editMeta` → öffnet Edit-Modal in `EventDetails.vue`.

### Edit-Modal "Event bearbeiten"

Ein neues Modal (`showEditMeta`) in `EventDetails.vue` mit zwei Abschnitten:

**Abschnitt "INHALT"**
- Titel: `<input>` (required, max. 255 Zeichen), vorbelegt mit `event.title`
- Beschreibung: `<textarea>` (optional), vorbelegt mit `event.description`
- Akzentfarbe: `<input type="color">`, vorbelegt mit `event.accent_color`

**Abschnitt "HINTERGRUNDBILD"**
- Datei-Upload: `<input type="file">` → sofortiger `POST /background` (unabhängig vom Speichern-Button, gleiche Pattern wie Cover-Upload)
- Vorschau + Löschen-Button (wenn Bild vorhanden)
- Blur-Slider: Range 0–20, Label zeigt aktuellen Wert in px
- Transparenz-Slider: Range 0–100 (intern ÷ 100 → Float), Label zeigt aktuellen Wert in %

**Live-Preview:**  
Blur- und Transparenz-Slider schreiben in temporäre Refs (`editBlur`, `editOverlay`). Das Hintergrund-Rendering nutzt diese Refs solange das Modal offen ist, und fällt auf `event.background_blur` / `event.background_overlay` zurück wenn geschlossen.

**Speichern-Button:**  
Sendet `PATCH /events/{id}` mit Titel, Beschreibung, Akzentfarbe, `background_blur`, `background_overlay`. Danach `await load()`.

**Abbrechen:**  
Preview-Refs zurücksetzen, Modal schließen, kein API-Call.

### Hintergrund-Rendering in EventDetails.vue

Zwei neue `position:fixed`-Ebenen vor dem eigentlichen Seiteninhalt:

```html
<!-- Ebene 1: Bild mit Blur -->
<div v-if="event?.background_image_path"
  style="position:fixed; inset:0; z-index:-2;
         background-image:url(...);
         background-size:cover; background-position:center;
         filter:blur(Xpx);
         transform:scale(1.05);" />

<!-- Ebene 2: Dunkles Overlay -->
<div v-if="event?.background_image_path"
  style="position:fixed; inset:0; z-index:-1;
         background:rgba(8,11,20,Y);" />
```

- `X` = `editBlur` (wenn Modal offen) sonst `event.background_blur`
- `Y` = `editOverlay` (wenn Modal offen) sonst `event.background_overlay`
- `transform:scale(1.05)` verhindert weiße Blur-Ränder an den Seiten
- Wenn kein `background_image_path`: beide Divs nicht gerendert, keine sichtbare Änderung

## Nicht im Scope

- Akzentfarbe war schon editierbar per PATCH, wird ins Modal integriert (kein separater Endpoint)
- Cover-Bild-Workflow bleibt unverändert
- Kein Cropping-Tool für Hintergrundbild
- Keine Animations-/Transition-Effekte für Hintergrundbild

## Datei-Übersicht

| Datei | Änderung |
|-------|----------|
| `backend/models.py` | 3 neue Felder in `Event` |
| `backend/schemas.py` | `EventPatch` + `EventResponse` erweitern |
| `backend/api/events.py` | `POST/DELETE /background` Endpoints |
| `backend/alembic/` | Neue Migration |
| `frontend/src/components/EventHero.vue` | `editMeta`-Emit + Button |
| `frontend/src/views/EventDetails.vue` | Modal + Background-Rendering |
