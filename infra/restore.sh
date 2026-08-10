#!/usr/bin/env bash
# =============================================================
# Identyx — PostgreSQL restore (production)
# =============================================================
# Restores the three databases from a compressed backup produced
# by backup.sh.
#
# Usage:
#   ./restore.sh                     # latest backup for each database
#   ./restore.sh BACKUP_DIR/file.gz  # same file for all three databases
#
# Env overrides: BACKUP_DIR (default: ./backups)
#
# WARNING: restoring DROPS the current data. Use with care.
# =============================================================

set -euo pipefail

COMPOSE_FILE="docker-compose.prod.yml"
COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$COMPOSE_DIR/backups}"

# "container-name:database-name"
DATABASES=(
  "postgres-auth:identyx_auth"
  "postgres-users:identyx_users"
  "postgres-sessions:identyx_sessions"
)

if [ $# -gt 1 ]; then
  echo "Usage: $0 [single_backup_file.sql.gz]" >&2
  exit 1
fi

SINGLE_FILE=""
if [ $# -eq 1 ]; then
  SINGLE_FILE="$1"
  if [ ! -f "$SINGLE_FILE" ]; then
    echo "ERROR: backup file not found: $SINGLE_FILE" >&2
    exit 1
  fi
fi

for entry in "${DATABASES[@]}"; do
  container="${entry%%:*}"
  database="${entry##*:}"

  if [ -n "$SINGLE_FILE" ]; then
    file="$SINGLE_FILE"
  else
    file="$(ls -t "$BACKUP_DIR"/${database}_*.sql.gz 2>/dev/null | head -1 || true)"
  fi

  if [ -z "$file" ] || [ ! -f "$file" ]; then
    echo "ERROR: no backup file found for $database" >&2
    exit 1
  fi

  echo "[$(date +%F\ %T)] Restoring $database from $file ..."

  # 1. Terminate active connections (the restore drops the database content).
  docker compose -f "$COMPOSE_DIR/$COMPOSE_FILE" exec -T "$container" \
    psql -U identyx -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$database' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true

  # 2. Drop + recreate the target database (schema included).
  docker compose -f "$COMPOSE_DIR/$COMPOSE_FILE" exec -T "$container" \
    psql -U identyx -d postgres -c "DROP DATABASE IF EXISTS $database;"
  docker compose -f "$COMPOSE_DIR/$COMPOSE_FILE" exec -T "$container" \
    psql -U identyx -d postgres -c "CREATE DATABASE $database OWNER identyx;"

  # 3. Restore from the compressed dump.
  gzip -dc "$file" | docker compose -f "$COMPOSE_DIR/$COMPOSE_FILE" exec -T "$container" \
    psql -U identyx -d "$database"

  echo "[$(date +%F\ %T)] OK: $database restored."
done

echo "[$(date +%F\ %T)] Restore completed."
