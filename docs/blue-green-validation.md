# Blue-Green Validation Workflow

Use this to validate legacy (blue) before porting features to the new FastAPI stack (green).

## Architecture

```mermaid
flowchart TB
  subgraph blue [Blue - Legacy]
    ScraperOld[scraper.py]
    ApiOld[api.py Flask :8000]
  end
  subgraph green [Green - New]
    ApiNew[FastAPI :8010]
    WorkerNew[worker - future]
  end
  subgraph shared [Shared]
    Pg[(PostgreSQL - one database)]
  end
  ScraperOld --> Pg
  ApiOld --> Pg
  ApiNew --> Pg
```

Both stacks must use the **same PostgreSQL data**. Different code, one source of truth.

## Step 1 — Pick one database

| Setup | Legacy `DATABASE_URL` (host) | Compose `.env` `DATABASE_URL` (containers) |
|-------|------------------------------|--------------------------------------------|
| Compose Postgres (recommended for testing) | `postgresql://yad2:yad2@localhost:5433/yad2` | `postgresql://yad2:yad2@postgres:5432/yad2` |
| Host Postgres | `postgresql://user@localhost/yad2` | `postgresql://user@host.docker.internal:5432/yad2` |

Start Compose Postgres (if used):

```bash
docker compose -f infra/compose/docker-compose.yml up -d postgres
bash scripts/migrate.sh
```

## Step 2 — Run blue (legacy)

```bash
export DATABASE_URL="postgresql://yad2:yad2@localhost:5433/yad2"  # adjust if needed
python scraper.py &   # optional: populate data
python api.py        # or: gunicorn api:app --bind 0.0.0.0:8000
```

## Step 3 — Validate blue works

```bash
export LEGACY_API_URL=http://localhost:8000
bash scripts/validate_legacy.sh
```

Exit codes:

- `0` — legacy API healthy and DB has listings
- `1` — endpoints failing
- `2` — endpoints OK but DB empty (scraper not writing or wrong DB)

**Do not port analytics to green until this passes with real data.**

## Step 4 — Run green alongside blue

```bash
# .env already has API_PORT=8010, POSTGRES_PORT=5433, etc.
docker compose -f infra/compose/docker-compose.yml up -d --build api
```

Blue stays on `:8000`, green on `:8010`.

## Step 5 — Compare parity

```bash
export LEGACY_API_URL=http://localhost:8000
export GREEN_API_URL=http://localhost:8010
python3 scripts/compare_parity.py
```

- **PASS** — green matches blue for ported routes
- **SKIP** — analytics not ported yet (expected until Phase 2b)
- **FAIL** — fix before continuing

## Step 6 — Port and re-check

For each analytics route:

1. Port SQL from `api.py` to `packages/data/repositories/` + FastAPI router
2. Mark route as ported in `scripts/compare_parity.py`
3. Re-run `compare_parity.py` until PASS

## Step 7 — Cutover (later)

When all routes PASS and worker replaces scraper:

1. Point `API_PORT=8000` for green
2. Stop legacy `api.py` / `scraper.py`
3. Green becomes production
