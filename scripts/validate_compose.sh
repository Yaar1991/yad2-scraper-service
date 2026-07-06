#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE=(bash "$ROOT_DIR/scripts/compose.sh")

export API_PORT="${API_PORT:-8000}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export REDIS_PORT="${REDIS_PORT:-6379}"

cleanup() {
  "${COMPOSE[@]}" down >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[validate] checking for legacy host processes..."
legacy_pids="$(pgrep -f "python(3)? .*api\.py|python(3)? .*scraper\.py|gunicorn api:app" || true)"
if [ -n "$legacy_pids" ]; then
  echo "[validate] WARN: legacy host processes detected:"
  for pid in $legacy_pids; do
    ps -p "$pid" -o pid=,command= || true
  done
  if [ "$API_PORT" = "8000" ] || [ "$POSTGRES_PORT" = "5432" ] || [ "$REDIS_PORT" = "6379" ]; then
    export API_PORT=8010
    export POSTGRES_PORT=5433
    export REDIS_PORT=6380
    echo "[validate] using alternate host ports: api=$API_PORT postgres=$POSTGRES_PORT redis=$REDIS_PORT"
  fi
fi

echo "[validate] ensuring env file exists..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "[validate] created .env from .env.example"
fi

echo "[validate] building compose images..."
"${COMPOSE[@]}" build

echo "[validate] starting postgres/redis..."
"${COMPOSE[@]}" up -d postgres redis

echo "[validate] starting app services (migrate runs automatically first)..."
"${COMPOSE[@]}" up -d --build api worker scheduler notifier

echo "[validate] checking port $API_PORT ownership..."
listener="$(lsof -nP -iTCP:"$API_PORT" -sTCP:LISTEN || true)"
if ! printf "%s" "$listener" | grep -q "com.docke"; then
  echo "[validate] FAIL: port $API_PORT is not owned by Docker"
  printf "%s\n" "$listener"
  exit 1
fi

echo "[validate] waiting for API readiness..."
for attempt in $(seq 1 20); do
  if curl -fsS "http://localhost:${API_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" -eq 20 ]; then
    echo "[validate] FAIL: API did not become ready in time"
    "${COMPOSE[@]}" logs --no-color --tail=120 api
    exit 1
  fi
  sleep 1
done

echo "[validate] smoke testing endpoints..."
health="$(curl -fsS "http://localhost:${API_PORT}/health")"
listings="$(curl -fsS "http://localhost:${API_PORT}/listings?limit=10&offset=0")"
stats="$(curl -fsS "http://localhost:${API_PORT}/stats")"
runs="$(curl -fsS "http://localhost:${API_PORT}/runs?limit=5")"
cities="$(curl -fsS "http://localhost:${API_PORT}/cities")"
price_changes="$(curl -fsS "http://localhost:${API_PORT}/price-changes?limit=5&days=30")"
market_summary="$(curl -fsS "http://localhost:${API_PORT}/analytics/market-summary")"
dashboard_code="$(curl -sS -o /dev/null -w '%{http_code}' "http://localhost:${API_PORT}/dashboard")"
openapi="$(curl -fsS "http://localhost:${API_PORT}/openapi.json")"

echo "[validate] /health => $health"
echo "[validate] /listings => $listings"
echo "[validate] /stats => $stats"
echo "[validate] /runs => $runs"
echo "[validate] /cities => $cities"
echo "[validate] /price-changes => $price_changes"
echo "[validate] /analytics/market-summary => $market_summary"
echo "[validate] /dashboard HTTP => $dashboard_code"
if [ "$dashboard_code" != "200" ]; then
  echo "[validate] FAIL: /dashboard did not return 200"
  exit 1
fi
if ! printf "%s" "$openapi" | grep -q "\"openapi\""; then
  echo "[validate] FAIL: openapi.json response is invalid"
  exit 1
fi
if ! printf "%s" "$health" | grep -q "healthy"; then
  echo "[validate] FAIL: /health did not report healthy database"
  exit 1
fi
if ! printf "%s" "$listings" | grep -q '"listings"'; then
  echo "[validate] FAIL: /listings response missing listings key"
  exit 1
fi

echo "[validate] checking migration tables..."
"${COMPOSE[@]}" exec -T postgres psql -U "${POSTGRES_USER:-yad2}" -d "${POSTGRES_DB:-yad2}" -c "\dt" >/tmp/yad2_validate_tables.txt
if ! grep -q "alembic_version" /tmp/yad2_validate_tables.txt; then
  echo "[validate] FAIL: alembic_version table missing"
  cat /tmp/yad2_validate_tables.txt
  exit 1
fi
if ! grep -q "listings" /tmp/yad2_validate_tables.txt; then
  echo "[validate] FAIL: listings table missing"
  cat /tmp/yad2_validate_tables.txt
  exit 1
fi

echo "[validate] PASS: compose stack is isolated and functioning on port $API_PORT"
