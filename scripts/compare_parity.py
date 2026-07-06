#!/usr/bin/env python3
"""Compare legacy (blue) vs new FastAPI (green) responses for parity testing."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


BLUE_BASE = os.getenv("LEGACY_API_URL", "http://localhost:8000").rstrip("/")
GREEN_BASE = os.getenv("GREEN_API_URL", "http://localhost:8010").rstrip("/")

# path, green_ported (False = expect 404 on green until Phase 2b)
ENDPOINTS: list[tuple[str, bool]] = [
    ("/health", True),
    ("/stats", True),
    ("/listings?limit=5&active_only=true&fields=minimal", True),
    ("/runs?limit=5", True),
    ("/cities", True),
    ("/price-changes?limit=5&days=30", True),
    ("/analytics/market-summary", True),
    ("/analytics/deals?limit=10", True),
    ("/analytics/stale?limit=10&min_days=14", True),
    ("/analytics/price-drops?limit=10", True),
    ("/analytics/neighborhoods?min_listings=3", True),
    ("/analytics/trends?days=30", True),
    ("/analytics/price-map?limit=100", True),
    ("/telegram/status", True),
    ("/cities/subscriptions", True),
]


def fetch(base: str, path: str) -> tuple[int, Any | None, str | None]:
    url = f"{base}{path}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw), None
            except json.JSONDecodeError:
                return resp.status, raw, None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(body), None
        except json.JSONDecodeError:
            return exc.code, body, None
    except Exception as exc:
        return 0, None, str(exc)


def main() -> int:
    print(f"Blue  (legacy): {BLUE_BASE}")
    print(f"Green (new):    {GREEN_BASE}")
    print()

    failures = 0
    skipped = 0
    passed = 0

    for path, green_ported in ENDPOINTS:
        blue_code, blue_body, blue_err = fetch(BLUE_BASE, path)
        green_code, green_body, green_err = fetch(GREEN_BASE, path)

        label = path.split("?")[0]

        if blue_err:
            print(f"FAIL {label}: blue unreachable ({blue_err})")
            failures += 1
            continue

        if not green_ported:
            if green_code == 404:
                print(f"SKIP {label}: not ported to green yet (blue HTTP {blue_code})")
                skipped += 1
                continue
            print(f"WARN {label}: green unexpectedly returns HTTP {green_code} (not marked ported)")

        if green_err:
            print(f"FAIL {label}: green unreachable ({green_err})")
            failures += 1
            continue

        if blue_code != 200:
            print(f"FAIL {label}: blue HTTP {blue_code} (fix legacy before comparing)")
            failures += 1
            continue

        if green_code != 200:
            print(f"FAIL {label}: green HTTP {green_code}, blue HTTP {blue_code}")
            failures += 1
            continue

        if isinstance(blue_body, dict) and isinstance(green_body, dict):
            blue_keys = set(blue_body.keys())
            green_keys = set(green_body.keys())
            missing = blue_keys - green_keys
            extra = green_keys - blue_keys
            if missing or extra:
                print(f"FAIL {label}: key mismatch missing={sorted(missing)} extra={sorted(extra)}")
                failures += 1
                continue

        print(f"PASS {label}: HTTP 200, top-level keys match")
        passed += 1

    print()
    print(f"Summary: passed={passed} skipped={skipped} failed={failures}")
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
