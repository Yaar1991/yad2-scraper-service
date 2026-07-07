#!/usr/bin/env bash
# Run docker compose with repo-root .env (for API_PORT, POSTGRES_PORT, etc.)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/infra/compose/docker-compose.yml}"

exec docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
