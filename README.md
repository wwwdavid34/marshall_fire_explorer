# Marshall Fire Recovery Monitor

Satellite-based damage assessment and recovery monitoring for the [2021 Marshall Fire](https://en.wikipedia.org/wiki/Marshall_Fire) — the most destructive wildfire in Colorado history — using InSAR coherence time series analysis with Wiener filter smoothing and polynomial curvature validation.

The pipeline processes 127 Sentinel-1 CSLC acquisitions into per-parcel coherence time series, detects genuine destruction via "smile curvature" validation, and identifies rebuild recovery through sustained threshold crossing. Results are served through a React-based Parcel Explorer frontend.

## Study Area

- **Location:** Superior and Louisville, CO
- **AOI:** `[-105.23, 39.915, -105.12, 39.98]`
- **Fire date:** December 30, 2021
- **Parcels tracked:** 1,793 labeled (1,093 Destroyed, 236 Damaged, 464 Unaffected)

## Methodology

### InSAR Coherence Time Series

Interferometric Synthetic Aperture Radar (InSAR) coherence measures how similar the radar signal is between two acquisitions. When a building is destroyed and rebuilt, coherence drops sharply and recovers gradually — a signature invisible to optical sensors under cloud cover.

1. **CSLC pairs:** 126 consecutive 12-day Sentinel-1 pairs (Sep 2021 – Dec 2025)
2. **Costco normalization:** Each pair's coherence is divided by the Costco parking lot reference target to remove atmospheric and seasonal effects
3. **Wiener filtering:** Noise-adaptive smoothing (window=11, ~132 days) that preserves sharp rebuild transitions better than rolling median
4. **Smile curvature:** Degree-2 polynomial fit on post-fire smoothed coherence; curvature ≥ 2.0 validates genuine destruction (U-shaped dip-then-recovery pattern)
5. **Recovery detection:** Sustained threshold crossing (90% of pre-fire 75th percentile, 5 consecutive pairs) with vertex-based minimum delay

### Data Flow

```
CSLC HDF5 (127 files)
  → process/coherence.py  → coherence_timeseries.parquet  (225K rows)
  → analyze/curvature.py  → parcel_curvature.parquet      (1,793 rows)
  → analyze/recovery.py   → recovery_detection.parquet     (1,093 rows)
  → output/frontend_data.py → parcels.geojson + timeseries/*.json
```

## Project Structure

```
marshall_fire/
├── config/
│   └── settings.py              # AOI, fire date, Costco reference, env config
├── pipeline/
│   ├── acquire/                  # Data download (Sentinel-1, Landsat, parcels)
│   │   ├── sentinel1.py          # CSLC from ASF (EarthData credentials)
│   │   ├── landsat.py            # Landsat from Planetary Computer (free)
│   │   └── parcels.py            # Boulder County open data (free)
│   ├── process/
│   │   ├── coherence.py          # CSLC → coherence → zonal stats → Costco norm
│   │   └── landsat.py            # dNBR, NDVI indices
│   ├── analyze/
│   │   ├── curvature.py          # Smile test (polynomial curvature validation)
│   │   └── recovery.py           # Sustained threshold crossing detection
│   ├── output/
│   │   └── frontend_data.py      # GeoJSON + per-parcel timeseries JSON
│   └── run.py                    # Click CLI orchestrator
├── frontend/                     # React + Vite Parcel Explorer
│   ├── src/
│   │   ├── components/
│   │   │   ├── ParcelMap.tsx      # Leaflet map with damage-colored parcels
│   │   │   ├── DetailPanel.tsx    # Parcel detail sidebar
│   │   │   ├── MapControls.tsx    # Filter/layer controls
│   │   │   └── TitleBar.tsx       # App header
│   │   ├── store.ts              # Zustand state management
│   │   ├── types.ts              # TypeScript interfaces
│   │   └── App.tsx               # Root component
│   └── public/data/              # Static data served to frontend
│       ├── parcels.geojson
│       ├── timeseries/*.json
│       ├── perimeter.geojson
│       └── crops/                # ESRI Wayback 30cm imagery
├── notebooks/                    # Exploration and analysis (01–09)
├── scripts/                      # Standalone utilities
├── tests/                        # pytest suite
├── data/                         # Working directories (gitignored)
│   ├── raw/                      # Downloaded satellite data
│   ├── processed/                # Intermediate rasters
│   └── results/                  # Analysis outputs (Parquet)
└── pyproject.toml                # Python 3.11+, uv package manager
```

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 18+ (for frontend)
- EarthData credentials (for Sentinel-1 CSLC download)

### Setup

```bash
# Clone and install Python dependencies
git clone <repo-url> && cd marshall_fire
uv sync

# Copy environment config
cp .env.example .env
# Edit .env with your EarthData token

# Install frontend dependencies
cd frontend && npm install && cd ..
```

### Run the Pipeline

```bash
# Full pipeline (downloads data, processes, analyzes, generates frontend data)
uv run python pipeline/run.py

# From existing raw data (skip download, ~15 min for coherence processing)
uv run python pipeline/run.py --skip-acquisition

# Include optional Landsat processing
uv run python pipeline/run.py --skip-acquisition --include-landsat

# Skip individual stages
uv run python pipeline/run.py --skip-acquisition --skip-processing  # analysis + output only
uv run python pipeline/run.py --skip-acquisition --skip-processing --skip-analysis  # output only
```

### Run the Frontend

```bash
cd frontend
npm run dev     # Development server at http://localhost:5173
npm run build   # Production build
```

### Regenerate Frontend Data Only

```bash
.venv/bin/python scripts/prep_frontend_data.py
```

## Pipeline Stages

### 1. Acquire (`--skip-acquisition` to bypass)

| Source | Data | Auth |
|--------|------|------|
| ASF (Alaska Satellite Facility) | Sentinel-1 CSLC HDF5 | EarthData token |
| Planetary Computer | Landsat (dNBR, NDVI) | None (free) |
| Boulder County | Parcel boundaries + damage labels | None (free) |

### 2. Process (`--skip-processing` to bypass)

**`process/coherence.py`** — The core module:
- Loads each CSLC HDF5, clips to AOI in UTM (EPSG:32613)
- Computes interferometric coherence: γ = |⟨s1·s2*⟩| / √(⟨|s1|²⟩·⟨|s2|²⟩)
- Runs zonal stats per parcel (min 3 pixels)
- Normalizes by Costco parking lot (parcel `157713021001`) reference coherence
- Outputs `coherence_timeseries.parquet` (~225K rows: 1,793 parcels × 126 pairs)

**`process/landsat.py`** (optional, `--include-landsat`) — dNBR and NDVI indices

### 3. Analyze (`--skip-analysis` to bypass)

**`analyze/curvature.py`** — Smile curvature validation:
- Wiener filter (window=11) each parcel's post-fire coherence
- Fit degree-2 polynomial; extract curvature = a × 10⁴
- Threshold ≥ 2.0 confirms genuine destruction pattern
- Vertex location provides minimum delay for recovery detection

**`analyze/recovery.py`** — Recovery detection (Destroyed parcels only):
- Pre-fire baseline: 75th percentile of pre-fire coherence
- Recovery threshold: 90% of baseline
- Sustained crossing: 5 consecutive pairs above threshold
- Per-parcel minimum delay from curvature vertex (≥ 6 months)

### 4. Output (`--skip-output` to bypass)

Generates static files for the frontend:
- `parcels.geojson` — Labeled parcels with recovery info and curvature
- `timeseries/{ParcelNo}.json` — Per-parcel raw + Wiener-smoothed coherence
- `perimeter.geojson` — Fire perimeter outline
- `crops/` — Symlink to ESRI Wayback pre/post imagery

## Output Schemas

### coherence_timeseries.parquet

| Column | Type | Description |
|--------|------|-------------|
| ParcelNo | string | Boulder County parcel ID |
| pair_idx | int | Sequential pair index (0–125) |
| date1 | string | First acquisition date (YYYY-MM-DD) |
| date2 | string | Second acquisition date |
| mid_date | string | Pair midpoint date |
| months_post_fire | float | Months since 2021-12-30 |
| raw_coh | float | Mean coherence within parcel |
| costco_coh | float | Costco reference coherence for this pair |
| norm_coh | float | raw_coh / costco_coh |
| damage_class | string | Destroyed, Damaged, or Unaffected |

### parcel_curvature.parquet

| Column | Type | Description |
|--------|------|-------------|
| ParcelNo | string | Parcel ID |
| smile_curvature | float | Quadratic coefficient × 10⁴ |
| vertex_months | float | Trough location (months post-fire) |
| smile_valid | bool | curvature ≥ 2.0 |

### recovery_detection.parquet

| Column | Type | Description |
|--------|------|-------------|
| ParcelNo | string | Parcel ID |
| damage_class | string | Always "Destroyed" |
| pre_baseline | float | Pre-fire 75th percentile coherence |
| recovery_date | datetime | Date of sustained threshold crossing |
| recovery_months_post_fire | float | Months from fire to recovery |
| smile_curvature | float | From curvature analysis |
| vertex_months | float | Curvature trough location |
| smile_valid | bool | Curvature validation flag |

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

Notebooks are for exploration only and are never imported by the pipeline.

## Frontend

The Parcel Explorer is a React + Vite application using:

- **Leaflet** — Interactive map with damage-colored parcel polygons
- **Recharts** — Coherence time series charts with raw + smoothed overlay
- **Zustand** — Lightweight state management
- **TanStack Query** — Data fetching with caching

Features:
- Click any parcel to view its coherence time series and recovery status
- Filter by damage class (Destroyed/Damaged/Unaffected)
- ESRI Wayback pre/post satellite imagery crops
- Fire perimeter overlay

## Testing

```bash
uv run pytest tests/ -v
```

Tests mirror the `pipeline/` structure:
- `test_settings.py` — Config loading
- `test_acquire.py` — Data download modules
- `test_process.py` — Coherence processing
- `test_output.py` — Frontend data generation

## Configuration

Key constants in `config/settings.py`:

| Constant | Value | Description |
|----------|-------|-------------|
| `AOI` | `[-105.23, 39.915, -105.12, 39.98]` | Study area bounds (WGS84) |
| `FIRE_DATE` | `2021-12-30` | Marshall Fire date |
| `COSTCO_PARCEL` | `157713021001` | Reference target for normalization |
| `BURST_ID` | `T056-118973-IW1` | Sentinel-1 burst covering AOI |

## Data Access

| Source | Access | Auth Required |
|--------|--------|---------------|
| Sentinel-1 CSLC | [ASF DAAC](https://search.asf.alaska.edu/) | EarthData token |
| Landsat | [Planetary Computer](https://planetarycomputer.microsoft.com/) | None |
| Parcels | [Boulder County Open Data](https://opendata-bouldercounty.hub.arcgis.com/) | None |
| ESRI Wayback | Pre-downloaded 30cm crops | N/A |

## License

Private research project.
