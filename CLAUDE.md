# Marshall Fire — Project Conventions

## Overview

Satellite-based disaster damage assessment and recovery monitoring for the 2021 Marshall Fire using InSAR coherence time series analysis with Wiener filter smoothing and polynomial curvature validation.

## Quick Commands

- Run pipeline: `uv run python pipeline/run.py`
- Pipeline skip flags: `--skip-acquisition`, `--skip-processing`, `--skip-analysis`, `--skip-output`
- Prep frontend data: `.venv/bin/python scripts/prep_frontend_data.py`
- Lint: `uv run ruff check pipeline/ config/`
- Test: `uv run pytest tests/ -v`
- Frontend dev: `cd frontend && npm run dev`
- Frontend build: `cd frontend && npm run build`

## Project Structure

- `pipeline/` — InSAR recovery pipeline (Click CLI)
  - `acquire/` — CSLC from ASF, Landsat from Planetary Computer, parcel verification
  - `process/` — InSAR coherence computation, Landsat indices
  - `analyze/` — Curvature validation ("smile test"), Wiener-filtered recovery detection
  - `output/` — Static frontend data generation (GeoJSON, timeseries JSON)
- `config/settings.py` — environment config, AOI, observation dates
- `notebooks/` — exploration and analysis (01-09, never imported by pipeline)
- `scripts/` — standalone utilities (CSLC bulk download, frontend data prep)
- `frontend/` — React + Vite Parcel Explorer (leaflet, recharts, zustand)
- `data/` — gitignored working directories (raw, processed, results)

## Methodology

- **InSAR coherence**: 126 consecutive 12-day Sentinel-1 CSLC pairs normalized against Costco reference target
- **Wiener filter**: noise-adaptive smoothing (window=11) preserving sharp rebuild transitions
- **Smile curvature**: degree-2 polynomial fit on smoothed post-fire coherence; threshold ≥ 2.0 validates genuine destruction
- **Recovery detection**: sustained threshold crossing (90% of pre-fire 75th percentile, 5 consecutive pairs) with vertex-based minimum delay

## Conventions

- All raster outputs must be Cloud Optimized GeoTIFF (COG)
- Analysis outputs go to Parquet in `data/results/`
- Frontend reads static files from `frontend/public/data/`
- AOI: `[-105.23, 39.915, -105.12, 39.98]` (Superior/Louisville, CO)
- Fire date: 2021-12-30
- Reference target: Costco parking lot (39.9597, -105.1742)

## Data Access

- Sentinel-1 CSLC: ASF (EarthData credentials in .env)
- Landsat: Planetary Computer (free, no auth)
- Parcels: Boulder County open data (free, no auth)
- ESRI Wayback crops: pre-downloaded 30cm imagery

## Notebooks

| # | Name | Purpose |
|---|------|---------|
| 01 | duckdb_columnar_intuition | DuckDB/columnar storage intro |
| 02 | sar_first_look | SAR data exploration |
| 03 | sar_preprocessing | Linear→dB conversion |
| 04 | sar_change_detection | VV amplitude change (exploratory) |
| 04b | insar_coherence | InSAR coherence pre/post fire |
| 04c | insar_temporal | 126-pair temporal coherence series |
| 05 | landsat_ir_fusion | Optical complement (dNBR, NDVI) |
| 06 | parcel_zonal_stats | Raster→tabular bridge |
| 07 | permit_ground_truth | Ground truth audit |
| 07b | esri_opencv_prototype | ESRI Wayback + OpenCV features |
| 08 | damage_classifier | Multi-sensor XGBoost classifier |
| 09 | recovery_tracking | Wiener filter + curvature + detection |

## Testing

- `tests/` mirrors `pipeline/` structure
- Run full suite: `uv run pytest tests/ -v`
