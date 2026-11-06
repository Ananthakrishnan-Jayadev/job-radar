#!/usr/bin/env bash
# Nightly backup (run from cron, see crontab.example): a checked copy of the
# database in data/, keeping the last 14 nightly copies. Backups you make
# yourself (Scans page, or before a deploy) are never deleted here.
# Set BACKUP_COPY_DIR to also copy each one off this disk (a USB drive, say).
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose exec -T jobradar jobradar backup --note nightly
ls -1t data/jobradar-backup-*-nightly.db 2>/dev/null | tail -n +15 | xargs -r rm -f

if [ -n "${BACKUP_COPY_DIR:-}" ]; then
  newest=$(ls -1t data/jobradar-backup-*-nightly.db | head -1)
  mkdir -p "$BACKUP_COPY_DIR"
  cp "$newest" "$BACKUP_COPY_DIR/"
  ls -1t "$BACKUP_COPY_DIR"/jobradar-backup-*-nightly.db 2>/dev/null | tail -n +15 | xargs -r rm -f
fi
