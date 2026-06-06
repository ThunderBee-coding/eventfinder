# EventFinder — Datenbank Restore & Upgrade Guide

Dieses Dokument beschreibt, wie das Projekt nach einem DB-Backup-Restore auf den aktuellen Code-Stand gebracht wird, **ohne die Datenbank zu zerstören**.

---

## Wichtigste Regel

> **Niemals `docker compose down -v` ausführen.** Das `-v` Flag löscht alle Volumes inklusive der Datenbank. Nur `docker compose down` (ohne `-v`) ist sicher.

---

## Scenario 1: Backup einspielen + Code aktualisieren

Wenn du ein Backup von gestern einspielen und den aktuellen Code draufanwenden willst:

### Schritt 1: Backup-Liste anzeigen
```bash
ls -lh /docker/eventfinder/backups/
```

### Schritt 2: Restore-Script ausführen
```bash
/docker/eventfinder/scripts/db-restore.sh /docker/eventfinder/backups/eventfinder_YYYY-MM-DD.sql.gz
```

Das Script:
- Stoppt Backend und Worker
- Löscht nur die DB (nicht den Volume)
- Spielt das Backup ein
- Führt `alembic upgrade head` aus (wendet alle neuen Migrations an)
- Startet alles wieder

### Schritt 3: Ergebnis prüfen
```bash
docker compose -f /docker/eventfinder/docker-compose.yml ps
docker exec eventfinder-backend bash -c "cd /app && alembic current"
```

---

## Scenario 2: Nur Code aktualisieren (DB bleibt unverändert)

Wenn neue Features/Fixes deployed werden sollen ohne die DB anzufassen:

```bash
cd /docker/eventfinder

# 1. Neuesten Code holen
git pull origin master

# 2. Migrations anwenden (OHNE DB zu löschen)
docker exec eventfinder-backend bash -c "cd /app && alembic upgrade head"

# 3. Container neu bauen und starten
docker compose up -d --build
```

**Kein `down -v`, kein `docker compose down` nötig** — `up -d --build` aktualisiert die Container direkt.

---

## Scenario 3: Container neu starten ohne DB-Verlust

```bash
cd /docker/eventfinder

# Nur Container neu starten (kein Rebuild)
docker compose restart

# Oder: Neu bauen + starten (DB bleibt erhalten)
docker compose up -d --build
```

---

## Migrations-Workflow (für neue DB-Felder)

Wenn neue Spalten/Tabellen hinzukommen:

```bash
# 1. Neue Migration erstellen (NUR wenn models.py geändert wurde)
docker exec -it eventfinder-backend bash -c "cd /app && alembic revision -m 'beschreibung'"

# 2. Migration-Datei in backend/migrations/versions/ bearbeiten
#    upgrade() und downgrade() ausfüllen

# 3. Migration anwenden
docker exec eventfinder-backend bash -c "cd /app && alembic upgrade head"

# 4. Status prüfen
docker exec eventfinder-backend bash -c "cd /app && alembic current"
```

**Wichtig:** Niemals `alembic stamp head` ohne vorherige Migration — das markiert die DB als aktuell ohne die Änderungen anzuwenden.

---

## Backup-System

Tägliches Backup läuft automatisch um **02:00 Uhr** via Cron:
- Backup-Ort: `/docker/eventfinder/backups/eventfinder_YYYY-MM-DD.sql.gz`
- Aufbewahrung: 14 Tage
- Log: `/var/log/eventfinder-backup.log`

Manuelles Backup ausführen:
```bash
/docker/eventfinder/scripts/db-backup.sh
```

---

## Häufige Fehler und Lösungen

### `type "userrole" does not exist`
Die Enum-Namen in PostgreSQL stimmen nicht mit SQLAlchemy überein. Das passiert wenn die DB mit `init.sql` initialisiert wird (nach einem Volume-Reset).

**Ursache:** `init.sql` erstellt `user_role`, SQLAlchemy erwartet `userrole`.

**Fix:** In `backend/models.py` sind die Enum-Namen explizit gesetzt (`name='user_role'`). Falls der Fehler trotzdem auftritt: sicherstellen dass `models.py` den aktuellen Stand hat.

### `FOR UPDATE is not allowed with aggregate functions`
In `backend/api/auth.py` darf `select(func.count())` kein `.with_for_update()` haben. Wurde in Commit `998e8dd` behoben.

### Magic-Link funktioniert aber E-Mail kommt nicht an
SMTP-Credentials prüfen in `/docker/eventfinder/backend/.env` (MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD). Alternativ im Admin-Panel unter `/admin/settings` neu eintragen.

### Kein Login möglich (SMTP defekt)
Magic-Link-Token direkt in DB generieren:
```bash
TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
docker exec eventfinder-db psql -U eventfinder -d eventfinder -c "
  INSERT INTO magic_links (id, user_id, token, expires_at)
  SELECT gen_random_uuid(), id, '${TOKEN}', NOW() + INTERVAL '24 hours'
  FROM users WHERE email = 'deine@email.com';
"
echo "Login-URL: https://eventfinder.thunderbee.uk/auth/magic?token=${TOKEN}"
```

---

## Datenbank-Verbindung

```
Host (intern):  eventfinder-db:5432
Datenbank:      eventfinder
User:           eventfinder
Passwort:       siehe docker-compose.yml
```

Direkte DB-Verbindung:
```bash
docker exec -it eventfinder-db psql -U eventfinder -d eventfinder
```
