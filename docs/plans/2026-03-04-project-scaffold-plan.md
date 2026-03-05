# Marshall Fire — Project Scaffold Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create the full directory structure, config files, tooling, stubs, and scaffolds so the project is ready for notebook exploration and incremental implementation.

**Architecture:** Single Python project with uv for dependency management. Pipeline is a Click CLI calling stub functions. dbt on DuckDB for transformations. Vite + React + TypeScript frontend. LocalStack + MLflow via docker-compose for local dev. Cloudflare Pages + R2 for prod.

**Tech Stack:** Python 3.11, uv, Click, boto3, dbt-duckdb, PyTorch, TensorFlow/Keras, React 18, TypeScript, Vite 5, Leaflet, Zustand, Recharts

---

### Task 0: Install uv and Create Python Virtual Environment

**Prerequisites:** Ensure uv is installed. Do NOT install packages into the system Python.

**Step 1: Verify or install uv**

```bash
# Check if uv is available
uv --version
```

If not installed:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On macOS with Homebrew:
```bash
brew install uv
```

**Step 2: Pin Python 3.11 and create the venv**

Run from the project root (`/Users/fhsu/Documents/projects/marshall_fire`):

```bash
# Tell uv which Python version this project uses
echo "3.11" > .python-version

# Create a .venv in the project directory using Python 3.11
# uv will download Python 3.11 automatically if not already available
uv venv --python 3.11
```

This creates `.venv/` in the project root. All subsequent `uv run` and `uv sync` commands automatically use this venv — you never need to `source .venv/bin/activate` manually when using `uv run`.

**Step 3: Verify the venv is isolated from system Python**

```bash
# Should show the .venv Python, NOT /usr/bin/python3
uv run python --version
uv run python -c "import sys; print(sys.prefix)"
```

Expected: Python 3.11.x and a path containing `.venv` (e.g., `/Users/fhsu/Documents/projects/marshall_fire/.venv`).

**Step 4: Verify system Python is untouched**

```bash
# System python should still be whatever it was before
/usr/bin/python3 --version
which python3
```

These should NOT point to the project `.venv`.

**Note:** `.venv/` is already in `.gitignore` (created in Task 1). All later tasks use `uv run` or `uv sync` which automatically target this venv. Never run `pip install` directly — always go through uv.

---

### Task 1: Root Config Files (.gitignore, .env.example, .python-version)

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `.python-version`

**Step 1: Create .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
.venv/

# Environment
.env

# Data (large, pipeline-generated)
data/

# ML weights (stored in R2)
ml/models/*.pt
ml/models/*.keras
ml/models/*.h5

# DuckDB
*.duckdb
*.duckdb.wal

# MLflow
mlflow/
mlruns/

# Node
frontend/node_modules/
frontend/dist/

# OS
.DS_Store
Thumbs.db

# IDE
.idea/
.vscode/
*.swp

# Misc
firebase-debug.log
```

**Step 2: Create .env.example**

```bash
# Cloudflare
CF_ACCOUNT_ID=
CF_API_TOKEN=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=

# Planetary Computer
PC_SDK_SUBSCRIPTION_KEY=

# USGS EarthData
EARTHDATA_USERNAME=
EARTHDATA_PASSWORD=

# Pipeline
DEPLOY_ENV=dev
DBT_DUCKDB_PATH=data/marshall.duckdb
```

**Step 3: Create .python-version**

```
3.11
```

**Step 4: Commit**

```bash
git add .gitignore .env.example .python-version
git commit -m "chore: add gitignore, env template, and python version pin"
```

---

### Task 2: pyproject.toml

**Files:**
- Create: `pyproject.toml`

**Step 1: Create pyproject.toml with dependency groups**

```toml
[project]
name = "marshall-fire"
version = "0.1.0"
description = "Satellite-based disaster damage assessment and recovery monitoring — Marshall Fire 2021"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1",
    "boto3>=1.28",
    "pystac-client>=0.7",
    "planetary-computer>=1.0",
    "rasterio>=1.3",
    "geopandas>=0.14",
    "pandas>=2.0",
    "numpy>=1.24",
    "duckdb>=0.9",
    "pyarrow>=14.0",
    "rasterstats>=0.19",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.4",
    "pytest>=8.0",
    "pre-commit>=3.5",
    "detect-secrets>=1.4",
]
ml = [
    "torch>=2.1",
    "torchvision>=0.16",
    "torchgeo>=0.5",
    "tensorflow>=2.15",
    "mlflow>=2.10",
    "scikit-learn>=1.3",
]
notebooks = [
    "jupyter>=1.0",
    "matplotlib>=3.8",
    "seaborn>=0.13",
]
geo = [
    "pyrosar>=0.20",
    "pdal>=3.2",
    "laspy>=2.5",
]

[project.scripts]
marshall-fire = "pipeline.run:run_pipeline"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

**Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pyproject.toml with dependency groups"
```

---

### Task 3: docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

**Step 1: Create docker-compose.yml (LocalStack + MLflow)**

```yaml
services:
  localstack:
    image: localstack/localstack
    ports:
      - "4566:4566"
    environment:
      SERVICES: s3

  mlflow:
    image: ghcr.io/mlflow/mlflow
    ports:
      - "5000:5000"
    command: mlflow server --host 0.0.0.0 --backend-store-uri sqlite:///mlflow/mlflow.db
    volumes:
      - ./mlflow:/mlflow
```

**Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "chore: add docker-compose for LocalStack and MLflow"
```

---

### Task 4: config/settings.py

**Files:**
- Create: `config/__init__.py`
- Create: `config/settings.py`

**Step 1: Create config/__init__.py**

Empty file.

**Step 2: Create config/settings.py**

```python
"""Environment configuration for dev (LocalStack) and prod (Cloudflare R2)."""

import os
from dataclasses import dataclass

import boto3
from dotenv import load_dotenv

load_dotenv()


@dataclass
class EnvironmentConfig:
    s3_endpoint_url: str
    data_bucket: str
    data_base_url: str
    r2_account_id: str | None = None


CONFIGS = {
    "dev": EnvironmentConfig(
        s3_endpoint_url="http://localhost:4566",
        data_bucket="dm-dev-data",
        data_base_url="http://localhost:4566/dm-dev-data",
    ),
    "prod": EnvironmentConfig(
        s3_endpoint_url=f"https://{os.getenv('CF_ACCOUNT_ID', '')}.r2.cloudflarestorage.com",
        data_bucket="dm-prod-data",
        data_base_url="https://marshallfire.yourdomain.com/data",
        r2_account_id=os.getenv("CF_ACCOUNT_ID"),
    ),
}

AOI = [-105.16, 39.93, -105.07, 40.01]

OBSERVATION_DATES = ["2021-11", "2022-01", "2022-06", "2023-06", "2024-06"]


def get_config(env: str | None = None) -> EnvironmentConfig:
    env = env or os.getenv("DEPLOY_ENV", "dev")
    return CONFIGS[env]


def get_s3_client(config: EnvironmentConfig):
    return boto3.client(
        "s3",
        endpoint_url=config.s3_endpoint_url,
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
    )
```

**Step 3: Commit**

```bash
git add config/
git commit -m "feat: add environment config with dev/prod S3 abstraction"
```

---

### Task 5: Pipeline Stubs — acquire/

**Files:**
- Create: `pipeline/__init__.py`
- Create: `pipeline/acquire/__init__.py`
- Create: `pipeline/acquire/sentinel1.py`
- Create: `pipeline/acquire/landsat.py`
- Create: `pipeline/acquire/lidar.py`
- Create: `pipeline/acquire/parcels_permits.py`

**Step 1: Create pipeline/__init__.py and pipeline/acquire/__init__.py**

Empty files.

**Step 2: Create pipeline/acquire/sentinel1.py**

```python
"""Fetch Sentinel-1 GRD scenes from Planetary Computer."""

import logging

from config.settings import AOI, OBSERVATION_DATES

logger = logging.getLogger(__name__)


def acquire_sentinel1() -> None:
    """Download Sentinel-1 GRD VV/VH scenes for all observation dates."""
    logger.info("acquire_sentinel1: fetching %d dates for AOI %s", len(OBSERVATION_DATES), AOI)
    logger.info("acquire_sentinel1: not yet implemented — skipping")
```

**Step 3: Create pipeline/acquire/landsat.py**

```python
"""Fetch Landsat 8/9 L2 scenes from Planetary Computer."""

import logging

from config.settings import AOI, OBSERVATION_DATES

logger = logging.getLogger(__name__)


def acquire_landsat() -> None:
    """Download Landsat L2 scenes for all observation dates."""
    logger.info("acquire_landsat: fetching %d dates for AOI %s", len(OBSERVATION_DATES), AOI)
    logger.info("acquire_landsat: not yet implemented — skipping")
```

**Step 4: Create pipeline/acquire/lidar.py**

```python
"""Fetch USGS 3DEP LiDAR tiles from The National Map API."""

import logging

from config.settings import AOI

logger = logging.getLogger(__name__)


def acquire_lidar() -> None:
    """Download LAZ tiles covering the AOI."""
    logger.info("acquire_lidar: fetching tiles for AOI %s", AOI)
    logger.info("acquire_lidar: not yet implemented — skipping")
```

**Step 5: Create pipeline/acquire/parcels_permits.py**

```python
"""Download Boulder County parcel boundaries and building permits."""

import logging

logger = logging.getLogger(__name__)


def acquire_parcels_permits() -> None:
    """Download parcel GeoJSON and permits CSV from Boulder County open data."""
    logger.info("acquire_parcels_permits: downloading parcel boundaries and permits")
    logger.info("acquire_parcels_permits: not yet implemented — skipping")
```

**Step 6: Commit**

```bash
git add pipeline/__init__.py pipeline/acquire/
git commit -m "feat: add pipeline acquire stubs (sentinel1, landsat, lidar, parcels)"
```

---

### Task 6: Pipeline Stubs — process/

**Files:**
- Create: `pipeline/process/__init__.py`
- Create: `pipeline/process/sar.py`
- Create: `pipeline/process/landsat.py`
- Create: `pipeline/process/lidar.py`

**Step 1: Create pipeline/process/__init__.py**

Empty file.

**Step 2: Create pipeline/process/sar.py**

```python
"""SAR processing: GRD → sigma0 → terrain correction → backscatter change → COG."""

import logging

logger = logging.getLogger(__name__)


def process_sar() -> None:
    """Process raw Sentinel-1 GRD to calibrated backscatter change COGs."""
    logger.info("process_sar: GRD → sigma0 → terrain correction → change → COG")
    logger.info("process_sar: not yet implemented — skipping")
```

**Step 3: Create pipeline/process/landsat.py**

```python
"""Landsat processing: calibration → dNBR → NDVI → TIR anomaly → COG."""

import logging

logger = logging.getLogger(__name__)


def process_landsat() -> None:
    """Process raw Landsat L2 to calibrated indices COGs."""
    logger.info("process_landsat: calibration → dNBR → NDVI → TIR anomaly → COG")
    logger.info("process_landsat: not yet implemented — skipping")
```

**Step 4: Create pipeline/process/lidar.py**

```python
"""LiDAR processing: LAZ → DEM → DSM → CHM → COG."""

import logging

logger = logging.getLogger(__name__)


def process_lidar() -> None:
    """Process raw LAZ point clouds to elevation model COGs."""
    logger.info("process_lidar: LAZ → DEM → DSM → CHM → COG")
    logger.info("process_lidar: not yet implemented — skipping")
```

**Step 5: Commit**

```bash
git add pipeline/process/
git commit -m "feat: add pipeline process stubs (sar, landsat, lidar)"
```

---

### Task 7: Pipeline Stubs — output/

**Files:**
- Create: `pipeline/output/__init__.py`
- Create: `pipeline/output/parcel_json.py`
- Create: `pipeline/output/timeline_json.py`
- Create: `pipeline/output/registry.py`

**Step 1: Create all output stubs**

`pipeline/output/parcel_json.py`:
```python
"""Write per-parcel detail JSON files from the dbt mart."""

import logging

logger = logging.getLogger(__name__)


def write_parcel_json() -> None:
    """Write data/results/parcels/detail/{parcel_id}.json for each parcel."""
    logger.info("write_parcel_json: mart → detail JSON files")
    logger.info("write_parcel_json: not yet implemented — skipping")
```

`pipeline/output/timeline_json.py`:
```python
"""Write timeline.json mapping observation dates to layer URLs."""

import logging

logger = logging.getLogger(__name__)


def write_timeline_json() -> None:
    """Write data/results/timeline.json with observation dates and COG URLs."""
    logger.info("write_timeline_json: writing timeline index")
    logger.info("write_timeline_json: not yet implemented — skipping")
```

`pipeline/output/registry.py`:
```python
"""Write registry.json — the site-level index file."""

import logging

logger = logging.getLogger(__name__)


def write_registry_json() -> None:
    """Write data/results/registry.json."""
    logger.info("write_registry_json: writing site registry")
    logger.info("write_registry_json: not yet implemented — skipping")
```

**Step 2: Commit**

```bash
git add pipeline/output/
git commit -m "feat: add pipeline output stubs (parcel_json, timeline, registry)"
```

---

### Task 8: pipeline/run.py — Click CLI

**Files:**
- Create: `pipeline/run.py`

**Step 1: Create the CLI entry point**

```python
"""Single entry point for the Marshall Fire pipeline."""

import logging
import subprocess

import click

from pipeline.acquire.landsat import acquire_landsat
from pipeline.acquire.lidar import acquire_lidar
from pipeline.acquire.parcels_permits import acquire_parcels_permits
from pipeline.acquire.sentinel1 import acquire_sentinel1
from pipeline.output.parcel_json import write_parcel_json
from pipeline.output.registry import write_registry_json
from pipeline.output.timeline_json import write_timeline_json
from pipeline.process.landsat import process_landsat
from pipeline.process.lidar import process_lidar
from pipeline.process.sar import process_sar

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run_dbt() -> None:
    logger.info("run_dbt: executing dbt run")
    logger.info("run_dbt: not yet implemented — skipping")


def run_damage_inference() -> None:
    logger.info("run_damage_inference: loading weights and running damage model")
    logger.info("run_damage_inference: not yet implemented — skipping")


def run_rebuild_inference() -> None:
    logger.info("run_rebuild_inference: loading weights and running rebuild model")
    logger.info("run_rebuild_inference: not yet implemented — skipping")


@click.command()
@click.option("--skip-acquisition", is_flag=True, help="Skip data download step")
@click.option("--skip-processing", is_flag=True, help="Skip raster processing step")
@click.option("--skip-ml", is_flag=True, help="Skip ML inference step")
@click.option("--env", default="dev", type=click.Choice(["dev", "prod"]), help="Target environment")
def run_pipeline(skip_acquisition: bool, skip_processing: bool, skip_ml: bool, env: str) -> None:
    """Run the Marshall Fire data pipeline end to end."""
    logger.info("Starting pipeline (env=%s)", env)

    if not skip_acquisition:
        acquire_sentinel1()
        acquire_landsat()
        acquire_lidar()
        acquire_parcels_permits()
    else:
        logger.info("Skipping acquisition")

    if not skip_processing:
        process_sar()
        process_landsat()
        process_lidar()
    else:
        logger.info("Skipping processing")

    run_dbt()

    if not skip_ml:
        run_damage_inference()
        run_rebuild_inference()
    else:
        logger.info("Skipping ML inference")

    write_parcel_json()
    write_timeline_json()
    write_registry_json()

    logger.info("Pipeline complete")


if __name__ == "__main__":
    run_pipeline()
```

**Step 2: Test that it runs**

Run: `uv run python pipeline/run.py --help`
Expected: Click help output showing --skip-acquisition, --skip-processing, --skip-ml, --env options

Run: `uv run python pipeline/run.py`
Expected: Series of INFO log lines, each stub saying "not yet implemented — skipping", exits 0

**Step 3: Commit**

```bash
git add pipeline/run.py
git commit -m "feat: add Click CLI entry point with skip flags"
```

---

### Task 9: ML Inference Stubs

**Files:**
- Create: `ml/__init__.py`
- Create: `ml/inference/__init__.py`
- Create: `ml/inference/damage.py`
- Create: `ml/inference/rebuild.py`
- Create: `ml/training/.gitkeep`
- Create: `ml/models/.gitkeep`

**Step 1: Create ml stubs**

`ml/inference/damage.py`:
```python
"""Load Siamese U-Net weights and run damage assessment inference."""

import logging

logger = logging.getLogger(__name__)


def run_damage_inference() -> None:
    """Load siamese_unet weights, run pixel change detection, aggregate to parcel scores."""
    logger.info("run_damage_inference: not yet implemented — skipping")
```

`ml/inference/rebuild.py`:
```python
"""Load LSTM weights and run rebuild stage monitoring inference."""

import logging

logger = logging.getLogger(__name__)


def run_rebuild_inference() -> None:
    """Load LSTM weights, process VV time series, classify rebuild stages."""
    logger.info("run_rebuild_inference: not yet implemented — skipping")
```

**Step 2: Commit**

```bash
git add ml/
git commit -m "feat: add ML inference stubs and training/models directories"
```

---

### Task 10: dbt Project Skeleton

**Files:**
- Create: `dbt/dbt_project.yml`
- Create: `dbt/profiles.yml`
- Create: `dbt/packages.yml`
- Create: `dbt/models/staging/.gitkeep`
- Create: `dbt/models/intermediate/.gitkeep`
- Create: `dbt/models/marts/.gitkeep`

**Step 1: Create dbt/dbt_project.yml**

```yaml
name: marshall_fire
version: "0.1.0"
config-version: 2

profile: marshall_fire

model-paths: ["models"]
test-paths: ["tests"]

clean-targets:
  - target
  - dbt_packages
```

**Step 2: Create dbt/profiles.yml**

```yaml
marshall_fire:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: "{{ env_var('DBT_DUCKDB_PATH', '../data/marshall.duckdb') }}"
      threads: 4
```

**Step 3: Create dbt/packages.yml**

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: ">=1.1.0"
```

**Step 4: Create .gitkeep files for model subdirectories**

Touch: `dbt/models/staging/.gitkeep`, `dbt/models/intermediate/.gitkeep`, `dbt/models/marts/.gitkeep`

**Step 5: Commit**

```bash
git add dbt/
git commit -m "feat: add dbt project skeleton with DuckDB profile"
```

---

### Task 11: Notebooks Directory — Learning Curriculum

The notebooks serve three purposes and no others:

1. **Image inspection** — Load, visualize, and manually interpret SAR and Landsat imagery so you understand what the data physically looks like before writing any processing code.
2. **Hyperparameter tuning** — Systematically explore model parameters, log every run to MLflow, compare results, and select the best weights for the pipeline.
3. **Learn MLflow and SAR** — Treat MLflow as a first-class learning objective. Every notebook that runs a model logs to MLflow. SAR imagery concepts (speckle, backscatter, dB scale, double-bounce) are learned by looking at real data, not by reading about them.

Notebooks are never imported by the pipeline. They produce two artifacts that the pipeline consumes: `ml/models/siamese_unet_best.pt` and `ml/models/fusion_classifier.keras`. Everything else is learning.

**Files:**
- Create: `notebooks/exploration.ipynb`
- Create: `notebooks/01_duckdb_columnar_intuition.ipynb`
- Create: `notebooks/02_sar_first_look.ipynb`
- Create: `notebooks/03_sar_preprocessing.ipynb`
- Create: `notebooks/04_sar_change_detection.ipynb`
- Create: `notebooks/05_landsat_ir_fusion.ipynb`
- Create: `notebooks/06_parcel_zonal_stats.ipynb`
- Create: `notebooks/07_permit_ground_truth.ipynb`
- Create: `notebooks/08_siamese_pretrained_inference.ipynb`
- Create: `notebooks/09_siamese_finetuning.ipynb`
- Create: `notebooks/10_lstm_signal_exploration.ipynb`
- Create: `notebooks/11_lstm_training.ipynb`
- Create: `ml/training/.gitkeep`

Each notebook is a valid .ipynb with: (1) a markdown cell stating the learning goal and question to answer, (2) markdown section headers for each exercise, (3) empty code cells under each header. The developer fills in cells as they work.

---

#### Goal 1: Image Inspection — "What am I looking at?"

Notebooks 02–05 are entirely about loading satellite imagery and understanding it visually. No models, no training — just looking at pictures and numbers.

**Step 1: Create exploration.ipynb**

Scratch pad. Markdown cell: "# Exploration Scratch Pad — Document anomalies, unexpected findings here. Never cleaned up." One empty code cell.

**Step 2: Create Notebook 01 — DuckDB Columnar Intuition**

Learning goal: Feel the difference between columnar and row storage before touching real data. Learn to connect dbt to DuckDB.

Exercises:
- **Generate synthetic zonal stats** — 4,800 parcels × 5 dates. Write to both Parquet and CSV.
- **Feel the scan difference** — Time a 2-column query on Parquet vs CSV. Scale to 500K rows.
- **Connect dbt to DuckDB** — Run `dbt debug` against the synthetic data.

**Step 3: Create Notebook 02 — SAR First Look**

Learning goal: See what raw Sentinel-1 GRD data looks like. Learn that SAR looks nothing like a photograph — it's noisy, grainy, and the brightness means something physical (scattering strength, not color).

Exercises:
- **Fetch one pre-fire and one post-fire scene** — Via Planetary Computer. Just the AOI chip.
- **Inspect raw values** — Print DN range, mean, pixel size, CRS. These are Digital Numbers, not yet physically meaningful.
- **Visualize with percentile stretch** — Display with 2nd/98th percentile. See speckle noise for the first time. Learn: bright = buildings/metal (strong scatterers), dark = water/smooth soil (weak scatterers).
- **Compare to optical** — Load an ESRI Wayback image of the same area. Place them side-by-side. The SAR image is unrecognizable — this is the point.

**Step 4: Create Notebook 03 — SAR Preprocessing & Calibration**

Learning goal: Understand radiometric calibration (DN → sigma0 → dB). Learn that the dB scale is the physically meaningful one, and that different land cover types have characteristic backscatter values you can measure.

Exercises:
- **Implement DN → sigma0 → dB** — Two small functions. Print the dB range (should be roughly -20 to 0 dB).
- **Side-by-side comparison** — Raw DN vs Sigma0 Linear vs Sigma0 dB. The dB image is the one where you can start reading structure.
- **Measure land cover backscatter** — Draw boxes over known areas (intact urban, burned urban, grassland, creek corridor). Print mean dB per class. Learn the numbers: intact urban = -5 to -8 dB, grassland = -12 to -15 dB. These become your physical intuition for every threshold used later.

**Step 5: Create Notebook 04 — SAR Change Detection**

Learning goal: See fire damage in the SAR change image. Learn whether the signal separates from noise, and where the classification thresholds should sit.

Exercises:
- **Compute change image** — `vv_post_db - vv_pre_db`. Negative = structure gone.
- **Overlay parcels on change image** — Red = officially destroyed, green = survived. Can you see the burn scar?
- **Zonal stats per parcel** — Mean VV change, pixel count per parcel.
- **Histogram: destroyed vs survived** — Plot both distributions. Mark -2.0 dB and -4.0 dB thresholds. See the overlap — this is why SAR alone fails and IR fusion is needed.

**Step 6: Create Notebook 05 — Landsat IR Fusion & Decision Tree Baseline**

Learning goal: Understand multi-sensor fusion by seeing where SAR and optical signals agree and disagree. Establish a no-ML baseline accuracy that the model must beat.

Exercises:
- **Load four signals side-by-side** — VV change, SWIR B7, TIR anomaly, dNBR. Visualize each as a map.
- **Scatter matrix** — Four signals colored by destroyed/survived. Which pairs separate best?
- **Find SAR false alarms** — Parcels where SAR says destroyed but SWIR says no fire. These are the Coal Creek wet-soil cases — look at them on the map.
- **Apply the decision tree** — Implement the threshold logic from Section 9a. No ML — just if/else. Compute precision, recall, F1.
- **Record the baseline** — Expected F1 ~0.70–0.80. Write it down. If the ML model can't beat this, it doesn't justify its complexity.

---

#### Goal 2: Learn MLflow — "Track every experiment"

MLflow is introduced in Notebook 08 and used in every subsequent notebook. The goal is to build the habit of logging parameters, metrics, and artifacts for every training run.

**Step 7: Create Notebook 06 — Parcel Zonal Stats Pipeline**

Learning goal: Bridge raster and tabular worlds. See that Parquet at this scale is tiny and DuckDB reads it instantly.

Exercises:
- **Full zonal stats** — 5 dates × 6 rasters × all parcels → long-format Parquet.
- **DuckDB verification** — Aggregate query by raster and date.
- **File size check** — ~144K rows should be < 2MB.

**Step 8: Create Notebook 07 — Permit Ground Truth**

Learning goal: Understand training label quality before using labels to train anything.

Exercises:
- **Parcel-permit join** — Join on `parcel_id`. Print match rate. No geocoding.
- **Stage distribution** — Apply `implied_stage` mapping. How many parcels per stage?
- **Label confidence audit** — Full permit chain (high ~70%), partial (medium ~20%), none (low ~10%).
- **Timeline plots** — 10 parcels with full chains. Visualize dated stage transitions.

**Step 9: Create Notebook 08 — Pretrained Inference + First MLflow Run**

Learning goal: (a) See what a pretrained model does on your data before fine-tuning. (b) **First time using MLflow** — learn `mlflow.start_run()`, `log_params()`, `log_metrics()`, `log_figure()`.

Exercises:
- **Load pretrained Siamese U-Net** — `torchgeo` ResNet50 backbone, SENTINEL2_ALL_MOCO weights. 2 input channels (VV + VH).
- **Extract 64×64 patches** — 20 destroyed + 20 survived parcels.
- **Run inference and visualize** — Grid: pre/post/prediction for 4 parcels. Annotate with truth label and score.
- **Compute pretrained AUC** — Expected ~0.55–0.70.
- **Log to MLflow** — This is the teaching moment. Start MLflow tracking server (`docker compose up mlflow`). Log:
  - `mlflow.log_params({"model": "siamese_unet", "fine_tuned": False, "backbone": "resnet50"})`
  - `mlflow.log_metrics({"auc": auc, "n_samples": 40})`
  - `mlflow.log_figure(fig, "pretrained_predictions.png")`
  - Open `http://localhost:5000` and see your first run in the MLflow UI.
- **Document failure patterns** — Where does the pretrained model misfire? Log these as MLflow artifacts (text notes).

---

#### Goal 3: Hyperparameter Tuning — "Which settings produce the best model?"

Notebooks 09 and 11 are structured around systematic hyperparameter exploration. Every combination is logged to MLflow so you can compare runs in the UI.

**Step 10: Create Notebook 09 — Siamese U-Net Fine-Tuning**

Learning goal: Fine-tune the pretrained model. Learn two-stage training (freeze then unfreeze). Systematically tune hyperparameters and compare runs in MLflow.

Exercises:
- **Build dataset** — PyTorch Dataset: (pre_patch, post_patch, label). SAR-valid augmentations only (flip, 90° rotation, speckle noise — NOT color jitter or brightness, which are meaningless for SAR).
- **Spatial block split** — West/East Superior = train, East Louisville = held-out test. NOT random — prevents spatial autocorrelation leakage.
- **Stage 1: freeze backbone, train head** — 10 epochs, LR=1e-3, BCE+Dice loss, pos_weight=3.4.
- **Stage 2: unfreeze top encoder** — 20 epochs, LR=1e-4, CosineAnnealingLR, early stopping patience=5.

**Hyperparameter tuning grid** — run each combination as a separate MLflow run:

| Param | Default | Try These | What It Affects |
|---|---|---|---|
| `patch_size` | 64 | 32, 64, 128 | Context vs sample count. Larger patches = more neighborhood info but fewer training examples |
| `pos_weight` | 3.4 | 2.0, 3.4, 5.0 | Class imbalance correction. Higher = model works harder to find destroyed parcels (recall↑, precision↓) |
| `stage1_lr` | 1e-3 | 5e-4, 1e-3, 2e-3 | Head learning speed. Too high = unstable, too low = slow |
| `stage2_lr` | 1e-4 | 5e-5, 1e-4, 3e-4 | Backbone fine-tuning aggressiveness. Too high = forget pretrained features |
| `stage2_unfreeze` | layer3+4 | layer4-only, layer3+4, all | How much of the backbone adapts. More = more capacity but risks catastrophic forgetting |
| `bce_dice_ratio` | 0.5/0.5 | 0.3/0.7, 0.5/0.5, 0.7/0.3 | Loss function balance. Dice directly optimizes spatial overlap of change masks |

**MLflow logging for each run:**
```python
with mlflow.start_run(run_name=f"siamese_patch{patch_size}_pw{pos_weight}_lr{lr}"):
    mlflow.log_params({...all hyperparams...})
    # ... training loop ...
    mlflow.log_metrics({"best_val_f1": best_f1, "precision": p, "recall": r})
    mlflow.log_figure(training_curves_fig, "training_curves.png")
    mlflow.pytorch.log_model(model, "siamese_unet")
```

- **Compare runs in MLflow UI** — Open `http://localhost:5000`. Sort by `best_val_f1`. Compare training curves. Pick the winner.
- **Save best weights** — `torch.save(best_model.state_dict(), 'ml/models/siamese_unet_best.pt')`

**How fine-tuned weights flow into the pipeline:**
```
Notebook 09 (tuning) → picks best run → saves ml/models/siamese_unet_best.pt
                                                        ↓
pipeline/run.py → run_damage_inference()
                                                        ↓
ml/inference/damage.py → loads siamese_unet_best.pt
                       → runs pixel change detection on all parcels
                       → outputs per-parcel change probability
                       → fed into fusion classifier for final damage class
```

**Step 11: Create Notebook 10 — LSTM Signal Exploration**

Learning goal: Visually read rebuild stages from VV time series. Build intuition for what the LSTM needs to learn — the trajectory shape, not just the final value.

Exercises:
- **Load and normalize VV time series** — `VV_NORM(t) = VV(t) - median(Nov 2021)` per parcel.
- **Plot one example per rebuild stage** — cleared_lot, foundation_framing, structure_substantial, rebuild_complete. See each trajectory signature.
- **Blind guessing** — Plot 4 unknown parcels. Guess the stage from the curve shape before checking permits. This builds the intuition the LSTM will formalize.
- **Unsupervised clustering** — PCA → KMeans(4). Compare clusters to permit labels. Expect cleared_lot ≈ foundation (hard to distinguish), rebuild_complete clearly separable.
- **Spot the cleared-lot dip** — Post-demolition backscatter drops BELOW post-fire rubble. Flat concrete is more specular than debris. This is a real finding.

**Step 12: Create Notebook 11 — LSTM Training & Tuning**

Learning goal: Train the rebuild classifier. Learn confidence-weighted training. Systematically tune LSTM hyperparameters with MLflow, same discipline as Notebook 09.

Exercises:
- **Prepare sequences** — Shape: `(n_parcels, 5 timesteps, 3 features)`. Per timestep: `vv_norm`, `vv_delta_from_prev`, `acquisition_doy`.
- **Build model** — LSTM(32) for time series + Dense(16) for parcel context → merged → Dense(5, softmax) → [cleared_lot, foundation_framing, structure_substantial, rebuild_complete, not_applicable].
- **Confidence-weighted training** — Sample weights: permit-confirmed = 1.0, partial evidence = 0.6, inferred = 0.3.

**Hyperparameter tuning grid** — each combination is an MLflow run:

| Param | Default | Try These | What It Affects |
|---|---|---|---|
| `lstm_units` | 32 | 16, 32, 64 | Sequence model capacity. 5 timesteps is short — small may suffice |
| `lstm_dropout` | 0.2 | 0.1, 0.2, 0.3 | Regularize the short sequence |
| `parcel_branch_units` | 16 | 8, 16, 32 | Context branch complexity |
| `merged_dropout` | 0.3 | 0.2, 0.3, 0.4 | Post-merge regularization |
| `batch_size` | 64 | 32, 64, 128 | Gradient noise level |
| `lr` | 1e-3 | 5e-4, 1e-3, 2e-3 | Adam learning rate |
| `confidence_weights` | [1.0, 0.6, 0.3] | [1.0, 0.8, 0.5], [1.0, 0.5, 0.1] | How aggressively to discount uncertain labels |

**MLflow logging for each run:**
```python
with mlflow.start_run(run_name=f"lstm_u{units}_lr{lr}_cw{weights}"):
    mlflow.log_params({...all hyperparams...})
    # ... training loop ...
    mlflow.log_metrics({"val_accuracy": acc, "best_epoch": best_ep})
    mlflow.log_text(classification_report, "classification_report.txt")
    mlflow.log_figure(confusion_matrix_fig, "confusion_matrix.png")
    mlflow.tensorflow.log_model(model, "lstm_rebuild")
```

- **Weighted vs unweighted comparison** — Train twice (with and without sample weights). Compare confusion matrices in MLflow. Expect weighted to improve foundation_framing where permits are sparse.
- **Confusion matrix sanity check** — Confusion should be between adjacent stages (cleared↔foundation is OK). Non-adjacent confusion (cleared↔complete) means a feature is broken.
- **Compare all runs in MLflow UI** — Sort by `val_accuracy`. Check that the best run also has a sensible confusion matrix — highest accuracy isn't always best if it's right for the wrong reasons.
- **Save best weights** — `model.save('ml/models/fusion_classifier.keras')`

**How fine-tuned weights flow into the pipeline:**
```
Notebook 11 (tuning) → picks best run → saves ml/models/fusion_classifier.keras
                                                        ↓
pipeline/run.py → run_rebuild_inference()
                                                        ↓
ml/inference/rebuild.py → loads fusion_classifier.keras
                        → processes VV time series per parcel
                        → classifies rebuild stage (5 classes)
                        → enforces monotonic transitions (buildings don't un-build)
                        → writes rebuild_stage + rebuild_stage_date per parcel
```

---

#### Notebook → Pipeline Summary

```
LEARNING (notebooks)                          PRODUCTION (pipeline)
─────────────────────                         ────────────────────
NB 02–05: Inspect imagery, learn SAR          (informs threshold choices)
NB 08: First MLflow run, pretrained baseline  (establishes what fine-tuning must beat)
NB 09: Tune Siamese U-Net hyperparams        → ml/models/siamese_unet_best.pt
    └─ MLflow UI: compare runs, pick best         → ml/inference/damage.py loads it
NB 11: Tune LSTM hyperparams                  → ml/models/fusion_classifier.keras
    └─ MLflow UI: compare runs, pick best         → ml/inference/rebuild.py loads it
```

The notebooks are the workshop. The pipeline consumes only the finished products (two weight files). MLflow is the logbook that records how you got there.

---

**Step 13: Create all notebooks as .ipynb files**

Each notebook should be a valid Jupyter notebook containing:
1. A markdown cell with the title, learning goal, and "Question to answer"
2. Markdown section headers for each exercise
3. Empty code cells under each section header

Use the `NotebookEdit` tool or write valid .ipynb JSON.

**Step 14: Commit**

```bash
git add notebooks/ ml/training/
git commit -m "feat: scaffold notebook curriculum (01-11) with exercise structure"
```

---

### Task 12: Frontend Scaffold (Vite + React + TypeScript)

**Files:**
- Create: `frontend/` via `npm create vite@latest`
- Modify: `frontend/package.json` — add project dependencies
- Create: `frontend/public/_redirects`

**Step 1: Scaffold Vite project**

Run from project root:
```bash
cd frontend || npm create vite@latest frontend -- --template react-ts
```

If the directory doesn't exist yet, scaffold it. If it does (from Vite), proceed.

**Step 2: Add project dependencies to package.json**

```bash
cd frontend && npm install leaflet react-leaflet zustand @tanstack/react-query recharts
npm install -D @types/leaflet
```

**Step 3: Create frontend/public/_redirects**

```
/data/*  https://dm-prod-data.CF_ACCOUNT_ID.r2.dev/:splat  200
```

**Step 4: Verify build works**

Run: `cd frontend && npm run build`
Expected: Successful build, `frontend/dist/` created

**Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold Vite + React + TypeScript frontend with map dependencies"
```

---

### Task 13: scripts/deploy.sh

**Files:**
- Create: `scripts/deploy.sh`

**Step 1: Create deploy script**

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "→ Pushing results to R2..."
aws s3 sync data/results/ s3://dm-prod-data/results/ \
    --endpoint-url "https://${CF_ACCOUNT_ID}.r2.cloudflarestorage.com" \
    --delete

echo "→ Building frontend..."
cd frontend && npm ci && npm run build && cd ..

echo "→ Deploying to Cloudflare Pages..."
npx wrangler pages deploy frontend/dist \
    --project-name marshall-fire \
    --commit-dirty=true

echo "✓ Live at https://marshallfire.yourdomain.com"
```

**Step 2: Make executable**

```bash
chmod +x scripts/deploy.sh
```

**Step 3: Commit**

```bash
git add scripts/
git commit -m "feat: add deploy script (R2 sync + wrangler pages deploy)"
```

---

### Task 14: GitHub Actions CI

**Files:**
- Create: `.github/workflows/test.yml`

**Step 1: Create CI workflow**

```yaml
name: Test
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Install Python dependencies
        run: uv sync --extra dev

      - name: Lint
        run: uv run ruff check pipeline/ ml/ config/

      - name: Test
        run: uv run pytest tests/ -v

      - uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Build frontend
        run: cd frontend && npm ci && npm run build
```

**Step 2: Commit**

```bash
git add .github/
git commit -m "ci: add GitHub Actions workflow for lint, test, and frontend build"
```

---

### Task 15: Data Directories with .gitkeep

**Files:**
- Create: `data/raw/sentinel1/.gitkeep`
- Create: `data/raw/landsat/.gitkeep`
- Create: `data/raw/lidar/.gitkeep`
- Create: `data/raw/parcels/.gitkeep`
- Create: `data/raw/permits/.gitkeep`
- Create: `data/processed/sar/.gitkeep`
- Create: `data/processed/landsat/.gitkeep`
- Create: `data/processed/lidar/.gitkeep`
- Create: `data/tabular/.gitkeep`
- Create: `data/results/layers/.gitkeep`
- Create: `data/results/parcels/detail/.gitkeep`

**Note:** Since `data/` is in `.gitignore`, these directories will NOT be tracked by git. They exist only for local development. Create them but do NOT attempt to `git add` them. Instead, add a `Makefile` or a note in CLAUDE.md about running a setup command.

**Step 1: Create all data directories**

```bash
mkdir -p data/raw/{sentinel1,landsat,lidar,parcels,permits}
mkdir -p data/processed/{sar,landsat,lidar}
mkdir -p data/tabular
mkdir -p data/results/layers
mkdir -p data/results/parcels/detail
```

**Step 2: No commit needed — gitignored**

---

### Task 16: CLAUDE.md

**Files:**
- Create: `CLAUDE.md`

**Step 1: Create CLAUDE.md with project conventions**

```markdown
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

## Testing

- `tests/` mirrors `pipeline/` structure
- Run full suite: `uv run pytest tests/ -v`
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md with project conventions"
```

---

### Task 17: Tests Directory Skeleton

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_settings.py`

**Step 1: Create a minimal test to verify config works**

`tests/test_settings.py`:
```python
from config.settings import AOI, OBSERVATION_DATES, get_config


def test_dev_config_defaults():
    config = get_config("dev")
    assert config.s3_endpoint_url == "http://localhost:4566"
    assert config.data_bucket == "dm-dev-data"


def test_aoi_is_valid_bbox():
    assert len(AOI) == 4
    west, south, east, north = AOI
    assert west < east
    assert south < north


def test_observation_dates_count():
    assert len(OBSERVATION_DATES) == 5
    assert OBSERVATION_DATES[0] == "2021-11"
    assert OBSERVATION_DATES[-1] == "2024-06"
```

**Step 2: Run the test**

Run: `uv run pytest tests/test_settings.py -v`
Expected: 3 tests PASS

**Step 3: Commit**

```bash
git add tests/
git commit -m "test: add config settings smoke tests"
```

---

### Task 18: Initial Commit of Plan Doc

**Files:**
- Stage: `disaster-monitor-plan.md`
- Stage: `docs/plans/2026-03-04-project-scaffold-design.md`
- Stage: `docs/plans/2026-03-04-project-scaffold-plan.md`

**Step 1: Commit documentation**

```bash
git add disaster-monitor-plan.md docs/
git commit -m "docs: add project plan and scaffold design documents"
```

---

### Task 19: Final Verification

**Step 1: Verify full project runs**

```bash
# Pipeline CLI works
uv run python pipeline/run.py --help
uv run python pipeline/run.py

# Lint passes
uv run ruff check pipeline/ ml/ config/

# Tests pass
uv run pytest tests/ -v

# Frontend builds
cd frontend && npm run build
```

**Step 2: Verify git is clean**

```bash
git status
git log --oneline
```

Expected: All files committed, clean working tree, ~10 commits representing the scaffold.
