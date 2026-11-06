#!/usr/bin/env bash
# Start a scan, as "Scan now" does (run from cron, see crontab.example). The
# app runs it in the background; the Scans page shows it like any other.
# Exits quietly if a scan is already running.
set -euo pipefail
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8000/api/scans)
case "$code" in
  202) echo "$(date '+%F %T') scan started" ;;
  409) echo "$(date '+%F %T') a scan is already running" ;;
  *)   echo "$(date '+%F %T') couldn't start a scan (HTTP $code)" >&2; exit 1 ;;
esac
