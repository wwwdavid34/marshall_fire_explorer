# Marshall Fire — Project Scaffold Design

**Date:** 2026-03-04
**Scope:** Skeleton scaffolding only — directory structure, config, stubs, tooling. No real implementation.
**Tooling:** uv + pyproject.toml, Python 3.11, Vite + React + TypeScript for frontend.

---

## Decisions

- **Package manager:** uv with pyproject.toml as single source of truth
- **Python version:** 3.11 (best geospatial wheel compatibility)
- **Frontend CSS:** Deferred — bare Vite scaffold only
- **Scope:** All directories, config files, CLI stub, dbt skeleton, frontend scaffold, CI, deploy script

## Structure

```
marshall-fire/
├── pyproject.toml              # deps in groups: core, dev, ml, notebooks
├── .python-version             # 3.11
├── docker-compose.yml          # LocalStack + MLflow
├── .env.example                # credential template
├── .gitignore
├── CLAUDE.md
├── disaster-monitor-plan.md    # existing
│
├── config/
│   └── settings.py             # EnvironmentConfig dataclass, dev/prod, get_s3_client()
│
├── pipeline/
│   ├── run.py                  # Click CLI with skip flags — calls stubs
│   ├── acquire/
│   │   ├── sentinel1.py        # stub functions
│   │   ├── landsat.py
│   │   ├── lidar.py
│   │   └── parcels_permits.py
│   ├── process/
│   │   ├── sar.py
│   │   ├── landsat.py
│   │   └── lidar.py
│   └── output/
│       ├── parcel_json.py
│       ├── timeline_json.py
│       └── registry.py
│
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml            # DuckDB local
│   ├── packages.yml
│   └── models/
│       ├── staging/.gitkeep
│       ├── intermediate/.gitkeep
│       └── marts/.gitkeep
│
├── ml/
│   ├── training/.gitkeep
│   ├── models/.gitkeep         # gitignored weights
│   └── inference/
│       ├── damage.py           # stub
│       └── rebuild.py          # stub
│
├── notebooks/
│   └── exploration.ipynb       # empty scratch notebook
│
├── frontend/                   # Vite + React + TypeScript
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── public/_redirects
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       └── vite-env.d.ts
│
├── scripts/
│   └── deploy.sh               # R2 sync + wrangler pages deploy
│
├── .github/workflows/
│   └── test.yml                # ruff + pytest + npm build
│
└── data/                       # gitignored
    ├── raw/{sentinel1,landsat,lidar,parcels,permits}/
    ├── processed/{sar,landsat,lidar}/
    ├── tabular/
    └── results/{layers,parcels/detail}/
```

## Pipeline CLI Stub

`pipeline/run.py` is a working Click command that calls stub functions in sequence. Each stub logs what it would do and returns. Running `uv run python pipeline/run.py` succeeds immediately — gives a runnable entry point from day one.

## Config

`config/settings.py` implements the EnvironmentConfig dataclass from plan Section 5. Dev points to LocalStack (localhost:4566), prod points to Cloudflare R2. `get_s3_client()` returns a boto3 client configured for the active environment.

## Frontend

Bare Vite + React + TypeScript scaffold. `package.json` includes leaflet, react-leaflet, zustand, @tanstack/react-query, recharts as dependencies — not yet used in code. CSS approach deferred.

## What This Does NOT Include

- No real data acquisition code
- No raster processing
- No dbt SQL models (just empty directories)
- No ML training or inference logic
- No frontend components beyond App.tsx shell
- No CSS system
