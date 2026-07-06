#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <backup.sql>"
  exit 1
fi

BACKUP_FILE="$1"
if [ ! -f "$BACKUP_FILE" ]; then
  echo "File not found: $BACKUP_FILE"
  exit 1
fi

docker compose -f infra/compose/docker-compose.yml exec -T postgres \
  psql -U "${POSTGRES_USER:-yad2}" "${POSTGRES_DB:-yad2}" < "$BACKUP_FILE"

echo "Restore completed from: $BACKUP_FILE"
