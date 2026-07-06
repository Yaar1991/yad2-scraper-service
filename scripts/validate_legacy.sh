#!/usr/bin/env bash
# Validate the legacy Flask API (blue) is running and returning usable data.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

LEGACY_API_URL="${LEGACY_API_URL:-http://localhost:8000}"

echo "[legacy] API base: $LEGACY_API_URL"
echo "[legacy] checking process (optional)..."
if pgrep -f "python(3)? .*api\.py|gunicorn api:app" >/dev/null 2>&1; then
  pgrep -af "python(3)? .*api\.py|gunicorn api:app" || true
else
  echo "[legacy] WARN: no legacy api.py/gunicorn process detected on host"
fi

check_endpoint() {
  local path="$1"
  local label="$2"
  local code body
  code="$(curl -sS -o /tmp/yad2_legacy_body.json -w '%{http_code}' "${LEGACY_API_URL}${path}" || echo "000")"
  body="$(cat /tmp/yad2_legacy_body.json 2>/dev/null || true)"

  if [ "$code" != "200" ]; then
    echo "[legacy] FAIL $label HTTP $code"
    echo "$body" | head -c 500
    echo
    return 1
  fi

  echo "[legacy] OK   $label HTTP 200"
  return 0
}

failures=0

check_endpoint "/health" "health" || failures=$((failures + 1))
check_endpoint "/stats" "stats" || failures=$((failures + 1))
check_endpoint "/listings?limit=5&active_only=true&fields=minimal" "listings" || failures=$((failures + 1))
check_endpoint "/runs?limit=5" "runs" || failures=$((failures + 1))
check_endpoint "/analytics/market-summary" "analytics/market-summary" || failures=$((failures + 1))
check_endpoint "/analytics/deals?limit=10" "analytics/deals" || failures=$((failures + 1))
check_endpoint "/analytics/stale?limit=10&min_days=14" "analytics/stale" || failures=$((failures + 1))
check_endpoint "/analytics/price-drops?limit=10" "analytics/price-drops" || failures=$((failures + 1))

echo
echo "[legacy] data sanity (from /stats)..."
python3 - <<'PY'
import json
import os
import sys
import urllib.request

url = os.environ.get("LEGACY_API_URL", "http://localhost:8000") + "/stats"
try:
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.load(resp)
except Exception as exc:
    print(f"[legacy] FAIL could not load stats: {exc}")
    sys.exit(1)

total = data.get("total_listings", 0)
active = data.get("active_listings", 0)
print(f"[legacy] total_listings={total} active_listings={active}")

if total == 0:
    print("[legacy] WARN: database appears empty — analytics will look empty too")
    print("[legacy]       ensure scraper.py is running and DATABASE_URL points to the DB with data")
    sys.exit(2)

print("[legacy] PASS: legacy API responds and database has listings")
PY
stats_rc=$?
if [ "$stats_rc" -eq 1 ]; then
  failures=$((failures + 1))
elif [ "$stats_rc" -eq 2 ]; then
  echo "[legacy] incomplete: endpoints work but no listing data yet"
  exit 2
fi

if [ "$failures" -gt 0 ]; then
  echo "[legacy] FAIL: $failures endpoint check(s) failed"
  exit 1
fi

echo "[legacy] PASS: legacy stack looks healthy"
