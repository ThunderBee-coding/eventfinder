#!/bin/bash
# Tägliches pg_dump Backup für EventFinder
# Speichert in /docker/eventfinder/backups/, hält 14 Tage

set -e

BACKUP_DIR="/docker/eventfinder/backups"
DATE=$(date +%Y-%m-%d)
BACKUP_FILE="${BACKUP_DIR}/eventfinder_${DATE}.sql"

mkdir -p "$BACKUP_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starte Backup → $BACKUP_FILE"

docker exec eventfinder-db pg_dump \
  -U eventfinder \
  -d eventfinder \
  --no-owner \
  --no-acl \
  --format=plain \
  > "$BACKUP_FILE"

# Komprimieren
gzip -f "$BACKUP_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup fertig: ${BACKUP_FILE}.gz ($(du -sh "${BACKUP_FILE}.gz" | cut -f1))"

# Backups älter als 14 Tage löschen
find "$BACKUP_DIR" -name "eventfinder_*.sql.gz" -mtime +14 -delete
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Alte Backups bereinigt. Vorhandene Backups:"
ls -lh "$BACKUP_DIR"/eventfinder_*.sql.gz 2>/dev/null || echo "  (keine)"
