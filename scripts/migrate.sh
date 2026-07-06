#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="infra/compose/docker-compose.yml"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

docker compose -f "$COMPOSE_FILE" up -d postgres
docker compose -f "$COMPOSE_FILE" run --rm migrate

echo "Migrations applied."
