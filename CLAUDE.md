# Marshall Fire — Project Conventions

## Overview

Satellite-based disaster damage assessment and recovery monitoring for the 2021 Marshall Fire. See `disaster-monitor-plan.md` for the full architecture spec.

## Quick Commands

- Run pipeline: `uv run python pipeline/run.py`
- Pipeline with skip flags: `uv run python pipeline/run.py --skip-acquisition --skip-ml`
- Lint: `uv run ruff check pipeline/ ml/ config/`
- Test: `uv run pytest tests/ -v`
- Frontend dev: `cd frontend && npm run dev`
- Frontend build: `cd frontend && npm run build`
- dbt: `cd dbt && dbt run`
- Local services: `docker compose up -d` (LocalStack on :4566, MLflow on :5000)

## Project Structure

- `pipeline/` — data acquisition, processing, output generation (Click CLI)
- `config/settings.py` — dev/prod environment config, S3 client factory
- `dbt/` — DuckDB transformation layer (staging → intermediate → marts)
- `ml/` — training notebooks, inference modules, model weights (gitignored)
- `notebooks/` — exploration only, never imported by pipeline
- `frontend/` — React + Vite scrollytelling app
- `data/` — gitignored working directories (raw, processed, tabular, results)

## Conventions

- All raster outputs must be Cloud Optimized GeoTIFF (COG)
- Pipeline intermediate data goes to Parquet in `data/tabular/`
- dbt reads Parquet, writes to DuckDB mart
- Output JSON/COG goes to `data/results/` then syncs to R2
- All S3 access goes through `config.settings.get_s3_client()` — never raw boto3
- AOI: `[-105.16, 39.93, -105.07, 40.01]` (Superior/Louisville, CO)
- Observation dates: Nov 2021, Jan 2022, Jun 2022, Jun 2023, Jun 2024

## Data Access

- Sentinel-1 + Landsat: Planetary Computer (free, no auth)
- LiDAR: USGS TNM API (EarthData token in .env)
- Parcels/Permits: Boulder County open data (free, no auth)

## Testing

- `tests/` mirrors `pipeline/` structure
- Run full suite: `uv run pytest tests/ -v`
