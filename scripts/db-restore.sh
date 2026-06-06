#!/bin/bash
# Stellt ein EventFinder-Backup wieder her und wendet neue Migrationen an.
#
# Verwendung:
#   ./scripts/db-restore.sh backups/eventfinder_2026-06-05.sql.gz
#
# Ablauf:
#   1. Backup einspielen (Schema + Daten vom Backup-Datum)
#   2. alembic upgrade head (neue Code-Migrationen anwenden)
#   3. Container neu starten

set -e

BACKUP_FILE="$1"
COMPOSE_DIR="/docker/eventfinder"

if [ -z "$BACKUP_FILE" ]; then
  echo "Verwendung: $0 <backup-datei>"
  echo ""
  echo "Verfügbare Backups:"
  ls -lh "${COMPOSE_DIR}/backups"/eventfinder_*.sql.gz 2>/dev/null || echo "  Keine Backups gefunden in ${COMPOSE_DIR}/backups/"
  exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Fehler: Datei nicht gefunden: $BACKUP_FILE"
  exit 1
fi

echo "============================================================"
echo "  EventFinder DB-Restore"
echo "  Backup: $BACKUP_FILE"
echo "  Datum:  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""
echo "WARNUNG: Die aktuelle Datenbank wird ÜBERSCHRIEBEN."
echo "Alle aktuellen Daten gehen verloren!"
echo ""
read -p "Fortfahren? (ja/nein): " CONFIRM
if [ "$CONFIRM" != "ja" ]; then
  echo "Abgebrochen."
  exit 0
fi

echo ""
echo "[1/5] Backend und Worker stoppen..."
cd "$COMPOSE_DIR"
docker compose stop backend worker

echo "[2/5] Datenbank zurücksetzen..."
docker exec eventfinder-db psql -U eventfinder -d postgres -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = 'eventfinder' AND pid <> pg_backend_pid();
" > /dev/null 2>&1 || true

docker exec eventfinder-db psql -U eventfinder -d postgres -c "DROP DATABASE IF EXISTS eventfinder;" > /dev/null
docker exec eventfinder-db psql -U eventfinder -d postgres -c "CREATE DATABASE eventfinder OWNER eventfinder;" > /dev/null

echo "[3/5] Backup einspielen: $BACKUP_FILE ..."
if [[ "$BACKUP_FILE" == *.gz ]]; then
  gunzip -c "$BACKUP_FILE" | docker exec -i eventfinder-db psql -U eventfinder -d eventfinder > /dev/null
else
  docker exec -i eventfinder-db psql -U eventfinder -d eventfinder < "$BACKUP_FILE" > /dev/null
fi
echo "      Backup eingespielt."

echo "[4/5] Neue Migrationen anwenden (alembic upgrade head)..."
docker compose run --rm --no-deps backend bash -c "cd /app && alembic upgrade head"

echo "[5/5] Backend und Worker neu starten..."
docker compose start backend worker
sleep 5
docker compose ps

echo ""
echo "============================================================"
echo "  Restore abgeschlossen!"
echo "  Daten: Stand vom Backup"
echo "  Code:  Aktuelle Version (alle Migrationen angewendet)"
echo "============================================================"
