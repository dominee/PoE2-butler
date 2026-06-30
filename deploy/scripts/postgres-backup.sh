#!/usr/bin/env bash
# Daily Postgres backup for PoE2 Hideout Butler (run on the VM via cron).
# Example crontab (02:15 UTC daily):
#   15 2 * * * /opt/poe2-butler/deploy/scripts/postgres-backup.sh >> /var/log/poe2b-backup.log 2>&1
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="${POE2B_COMPOSE_FILE:-$ROOT/deploy/compose/docker-compose.prod.yml}"
ENV_FILE="${POE2B_ENV_FILE:-$ROOT/deploy/env/.env.prod}"
BACKUP_DIR="${POE2B_BACKUP_DIR:-/var/backups/poe2b}"
RETAIN_DAYS="${POE2B_BACKUP_RETAIN_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/poe2b_${STAMP}.sql.gz"

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres \
  pg_dump -U poe2b poe2b | gzip > "$OUT"

find "$BACKUP_DIR" -name 'poe2b_*.sql.gz' -mtime +"$RETAIN_DAYS" -delete
echo "backup_ok path=$OUT"
