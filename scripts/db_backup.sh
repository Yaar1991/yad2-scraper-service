#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${1:-./backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

docker compose -f infra/compose/docker-compose.yml exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-yad2}" "${POSTGRES_DB:-yad2}" \
  > "${BACKUP_DIR}/yad2_${TIMESTAMP}.sql"

echo "Backup written: ${BACKUP_DIR}/yad2_${TIMESTAMP}.sql"
