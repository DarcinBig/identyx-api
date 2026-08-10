#!/usr/bin/env bash
# =============================================================
# Identyx — PostgreSQL backups (production)
# =============================================================
# Dumps the three databases into infra/backups/ as compressed
# SQL files, then applies a retention policy.
#
# Run manually or via cron, e.g. every night at 02:00:
#   0 2 * * * /path/to/identyx/infra/backup.sh >> /var/log/identyx-backup.log 2>&1
#
# Env overrides: BACKUP_DIR (default: ./backups), RETENTION_DAYS (default: 14)
# =============================================================

set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$COMPOSE_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DATE="$(date +%Y%m%d_%H%M%S)"

# "container-name:database-name"
DATABASES=(
  "postgres-auth:identyx_auth"
  "postgres-users:identyx_users"
  "postgres-sessions:identyx_sessions"
)

mkdir -p "$BACKUP_DIR"

for entry in "${DATABASES[@]}"; do
  container="${entry%%:*}"
  database="${entry##*:}"
  out="$BACKUP_DIR/${database}_${DATE}.sql.gz"

  echo "[$(date +%F\ %T)] Backing up $database from $container ..."
  docker compose -f "$COMPOSE_DIR/$COMPOSE_FILE" exec -T "$container" \
    pg_dump -U identyx "$database" | gzip > "$out"

  if [ -s "$out" ]; then
    echo "[$(date +%F\ %T)] OK: $out"
  else
    echo "[$(date +%F\ %T)] ERROR: backup $out is empty" >&2
    exit 1
  fi
done

# Retention: prune backups older than RETENTION_DAYS
find "$BACKUP_DIR" -name '*.sql.gz' -mtime "+$RETENTION_DAYS" -delete
echo "[$(date +%F\ %T)] Retention applied ($RETENTION_DAYS days)."
echo "[$(date +%F\ %T)] Backup completed."
