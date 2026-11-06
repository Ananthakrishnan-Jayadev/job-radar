#!/usr/bin/env bash
# Update Job Radar on the server to the latest code on GitHub.
#   On the server:     ~/job-radar/deploy/deploy.sh
#   From the laptop:   ssh <you>@<server> '~/job-radar/deploy/deploy.sh'
# Backs up the database first, so an update can always be undone.
set -euo pipefail
cd "$(dirname "$0")/.."

if docker compose ps --status running --services 2>/dev/null | grep -qx jobradar; then
  echo "Backing up the database..."
  docker compose exec -T jobradar jobradar backup --note before-deploy
fi

echo "Fetching the latest code..."
git pull --ff-only

echo "Building and restarting (the first build takes a few minutes)..."
docker compose up -d --build

# Old images from earlier builds take space; drop the dangling ones.
docker image prune -f >/dev/null

echo -n "Waiting for Job Radar to answer"
for _ in $(seq 1 30); do
  if curl -fs -o /dev/null http://127.0.0.1:8000/api/meta 2>/dev/null; then
    echo " - up at http://$(hostname -I | awk '{print $1}'):8000"
    exit 0
  fi
  echo -n "."; sleep 2
done
echo
echo "Job Radar didn't answer within a minute. Its log:" >&2
docker compose logs --tail 40 jobradar >&2
exit 1
