# EventFinder — Upgrade nach vollständigem Server-Restore

Diese Anleitung gilt wenn du den **kompletten Server von gestern (vor dem 06.06.2026) wiederhergestellt** hast und alle heutigen Code-Änderungen nachträglich einspielen willst.

**Ziel:** Alte DB-Daten (alle Events) behalten + neuen Code anwenden.

---

## Ausgangslage nach Server-Restore

Nach dem Restore vom Backup haben wir:
- ✅ Alte DB mit allen Events (DB-User: `user`)
- ✅ Alten Code (kein iCal-Feature, keine Rollenprüfung)
- ❌ Neuer Code vom 06.06.2026 noch nicht eingespielt

---

## Schritt 1: Neuen Code holen

```bash
cd /docker/eventfinder
git pull origin master
```

**Achtung:** Git pull holt u.a. Commit `dae2fe9` (POSTGRES_USER: user → eventfinder). Dieser Commit darf NICHT direkt angewendet werden — er würde die DB unzugänglich machen.

---

## Schritt 2: POSTGRES_USER-Problem lösen (kritisch!)

Der neue Code erwartet DB-User `eventfinder`, die wiederhergestellte DB wurde aber mit User `user` erstellt.

**Lösung: DB-User umbenennen** (statt DB neu erstellen):

```bash
# Container mit altem Code starten (docker-compose.yml noch nicht mit neuem Code überschreiben)
# Dafür: docker-compose.yml temporär auf alte Werte zurücksetzen
git diff HEAD~1 docker-compose.yml  # zeigt was sich geändert hat

# POSTGRES_USER und DATABASE_URL im docker-compose.yml zurücksetzen auf 'user':
# (die Datei liegt jetzt im neuen Stand — revert nur diese Datei)
git checkout dae2fe9~1 -- docker-compose.yml
```

Dann Container starten (mit altem docker-compose.yml, alter DB-User 'user'):
```bash
docker compose up -d --build
sleep 10
```

Jetzt User in PostgreSQL umbenennen:
```bash
docker exec eventfinder-db psql -U user -d postgres -c "ALTER USER \"user\" RENAME TO eventfinder;"
docker exec eventfinder-db psql -U eventfinder -d postgres -c "ALTER DATABASE eventfinder OWNER TO eventfinder;"
```

Jetzt docker-compose.yml auf neuen Stand (mit eventfinder) setzen:
```bash
git checkout master -- docker-compose.yml
```

---

## Schritt 3: Vollständiger Rebuild mit neuem Code

```bash
cd /docker/eventfinder
docker compose up -d --build
sleep 15
docker compose ps
```

Alle 5 Container müssen `Up` sein.

---

## Schritt 4: Neue Migrationen anwenden

Der neue Code fügt zwei neue Spalten zur DB hinzu. Diese werden per Alembic-Migration eingespielt — die bestehenden Daten bleiben dabei unverändert:

```bash
docker exec eventfinder-backend bash -c "cd /app && alembic upgrade head"
```

Erwartete neue Migrationen:
- `3ebe823d130a` — `calendar_token` Spalte in `users`
- `08d83bd296b9` — `event_start_time` + `event_end_time` Spalten in `events`

Status prüfen:
```bash
docker exec eventfinder-backend bash -c "cd /app && alembic current"
# Erwartete Ausgabe: 08d83bd296b9 (head)
```

---

## Schritt 5: Ergebnis verifizieren

```bash
# DB-Inhalt prüfen — Events müssen vorhanden sein
docker exec eventfinder-db psql -U eventfinder -d eventfinder \
  -c "SELECT COUNT(*) FROM events; SELECT COUNT(*) FROM users;"

# Neue Spalten vorhanden?
docker exec eventfinder-db psql -U eventfinder -d eventfinder \
  -c "\d users" | grep calendar_token

# Backend-Logs prüfen
docker logs eventfinder-backend 2>&1 | tail -5
```

---

## Schritt 6: Superadmin-Rolle prüfen

```bash
docker exec eventfinder-db psql -U eventfinder -d eventfinder \
  -c "SELECT email, role FROM users;"
```

Falls dein Account die falsche Rolle hat:
```bash
docker exec eventfinder-db psql -U eventfinder -d eventfinder \
  -c "UPDATE users SET role = 'superadmin' WHERE email = 'thunderbee732@gmail.com';"
```

---

## Was der neue Code enthält (Änderungen vom 06.06.2026)

| Commit | Beschreibung |
|---|---|
| `126cb5d` | Nur Organisatoren/Admins dürfen Events anlegen |
| `9f4daec` | DB-Migrationen: calendar_token + Zeitfelder |
| `7a40ef8` | Models: neue Felder |
| `ed5bc30` | Schemas: neue Felder |
| `8850d15` | API: POST /auth/calendar-token |
| `dfdffad` | API: GET /events/{id}/calendar.ics (iCal-Feed) |
| `0d18be7` | Fix: RFC 5545 Konformität |
| `66fd74b` | API: Kalender-Links per E-Mail versenden |
| `cc9357d` | Frontend: Kalender-Abo UI |
| `998e8dd` | Fix: FOR UPDATE Bug + Enum-Namen |
| `da176d4` | Backup-Scripts |

---

## Backup-System aktivieren

Das tägliche Backup läuft automatisch nach dem Restore weiter (Cron-Job prüfen):
```bash
crontab -l | grep eventfinder
# Soll zeigen: 0 2 * * * /docker/eventfinder/scripts/db-backup.sh ...
```

Falls nicht vorhanden, neu anlegen:
```bash
(crontab -l 2>/dev/null; echo "0 2 * * * /docker/eventfinder/scripts/db-backup.sh >> /var/log/eventfinder-backup.log 2>&1") | crontab -
```
