#!/usr/bin/env bash
# Copy the legacy host Postgres `yad2` database into Compose Postgres.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="infra/compose/docker-compose.yml"
COMPOSE=(bash scripts/compose.sh)
BACKUP_DIR="${1:-./backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DUMP_FILE="${BACKUP_DIR}/host_to_compose_${TIMESTAMP}.sql"

# Host DB connection (legacy). Override with LEGACY_DATABASE_URL if needed.
SOURCE_HOST="${SOURCE_HOST:-localhost}"
SOURCE_PORT="${SOURCE_PORT:-5432}"
SOURCE_DB="${SOURCE_DB:-yad2}"
SOURCE_USER="${SOURCE_USER:-$(whoami)}"

mkdir -p "$BACKUP_DIR"

echo "[migrate-db] source: ${SOURCE_USER}@${SOURCE_HOST}:${SOURCE_PORT}/${SOURCE_DB}"

echo "[migrate-db] dumping host database..."
if command -v pg_dump >/dev/null 2>&1; then
  set +e
  pg_dump \
    -h "$SOURCE_HOST" \
    -p "$SOURCE_PORT" \
    -U "$SOURCE_USER" \
    -d "$SOURCE_DB" \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    > "$DUMP_FILE" 2>/tmp/yad2_pg_dump_err.txt
  dump_rc=$?
  set -e
fi

if [ "${dump_rc:-1}" -ne 0 ]; then
  echo "[migrate-db] local pg_dump failed, using postgres:16 container..."
  docker run --rm postgres:16 pg_dump \
    "postgresql://${SOURCE_USER}@host.docker.internal:${SOURCE_PORT}/${SOURCE_DB}" \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    > "$DUMP_FILE"
fi

echo "[migrate-db] dump written: $DUMP_FILE ($(wc -c < "$DUMP_FILE") bytes)"

echo "[migrate-db] starting compose postgres..."
"${COMPOSE[@]}" up -d postgres

for attempt in $(seq 1 30); do
  if "${COMPOSE[@]}" exec -T postgres pg_isready -U "${POSTGRES_USER:-yad2}" -d "${POSTGRES_DB:-yad2}" >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" -eq 30 ]; then
    echo "[migrate-db] FAIL: compose postgres not ready"
    exit 1
  fi
  sleep 1
done

echo "[migrate-db] restoring into compose postgres..."
"${COMPOSE[@]}" exec -T postgres \
  psql -U "${POSTGRES_USER:-yad2}" -d "${POSTGRES_DB:-yad2}" < "$DUMP_FILE"

echo "[migrate-db] stamping alembic to head..."
"${COMPOSE[@]}" run --rm migrate alembic stamp head

echo "[migrate-db] verifying row counts in compose..."
"${COMPOSE[@]}" exec -T postgres \
  psql -U "${POSTGRES_USER:-yad2}" -d "${POSTGRES_DB:-yad2}" -c \
  "SELECT COUNT(*) AS listings FROM listings; SELECT COUNT(*) AS scrape_runs FROM scrape_runs;"

echo "[migrate-db] PASS: host database copied to compose volume yad2_postgres_data"
echo "[migrate-db] next: point legacy scraper/api at compose postgres if you want both stacks on same DB:"
echo "  export DATABASE_URL=postgresql://yad2:yad2@localhost:${POSTGRES_PORT:-5433}/yad2"
