#!/bin/sh
set -eu

PROJECT_DIR="${PROJECT_DIR:-/opt/meattrack}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/meattrack}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${BACKUP_DIR}/meattrack-${TIMESTAMP}.dump"
TEMP_FILE="${BACKUP_FILE}.tmp"

cleanup() {
	rm -f "$TEMP_FILE"
}
trap cleanup EXIT INT TERM

cd "$PROJECT_DIR"
umask 077
mkdir -p "$BACKUP_DIR"

docker compose exec -T db sh -ec \
    'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump --format=custom --compress=9 --no-owner --no-privileges --username="$POSTGRES_USER" "$POSTGRES_DB"' \
    > "$TEMP_FILE"
mv "$TEMP_FILE" "$BACKUP_FILE"
trap - EXIT INT TERM
sha256sum "$BACKUP_FILE" > "${BACKUP_FILE}.sha256"

find "$BACKUP_DIR" -type f -name 'meattrack-*.dump' -mtime "+$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -type f -name 'meattrack-*.dump.sha256' -mtime "+$RETENTION_DAYS" -delete

if [ -n "${RESTIC_REPOSITORY:-}" ]; then
    restic backup "$BACKUP_FILE" "${BACKUP_FILE}.sha256"
    restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
else
    echo "Local backup created. Configure RESTIC_REPOSITORY for an off-site copy." >&2
fi

echo "$BACKUP_FILE"
