# DisasterMonitor — Full Project Plan
**Multi-Modal Satellite Disaster Change Detection Platform**  
*Reference Implementation: 2021 Marshall Fire, Superior & Louisville, CO*

---

## 1. Vision

An open source framework for satellite-based disaster damage assessment and recovery monitoring. Contributors define a disaster event in YAML. The framework auto-generates a full ingestion pipeline, transformation layer, ML inference workflow, and interactive map visualization — deployable locally or to Cloudflare at zero cost.

**The goal is not just a portfolio project.** A working public framework usable by FEMA, UNOSAT, university remote sensing groups, and independent researchers for any disaster worldwide.

---

## 2. Reference Implementation — Marshall Fire 2021

**Why Marshall Fire:**
- Precise ignition date: December 30, 2021 — clean before/after boundary
- Mixed urban/grassland interface — SAR behaves differently across both
- 1,084 structures officially destroyed — ground truth for ML validation
- 4-year recovery arc available (2022–2024) — temporal series, not just binary change
- Boulder County parcel + permit data publicly available
- Local to Colorado — easy to ground-truth visually

**AOI:** `[-105.16, 39.93, -105.07, 40.01]` — Superior and Louisville, CO

**Timeline:**

| Phase | Date | Purpose |
|---|---|---|
| Pre-fire baseline | Nov 2021 | Urban SAR signature, vegetation state |
| Immediate post-fire | Jan 2022 | Structure loss, bare soil exposure |
| Early recovery | Jun 2022 | Debris cleared, foundation slabs |
| Mid restoration | Jun 2023 | Reconstruction begins |
| Late restoration | Jun 2024 | Rebuilt neighborhoods, new vegetation |

---

## 3. Data Sources

| Layer | Source | Access | Cost | Purpose |
|---|---|---|---|---|
| Sentinel-1 SAR (GRD) | Copernicus / Planetary Computer | `pystac-client` + PC SDK | Free | Structural change detection |
| Landsat 8/9 L2 | USGS / Planetary Computer | `pystac-client` + PC SDK | Free | dNBR burn severity, NDVI recovery |
| USGS 3DEP LiDAR | The National Map | TNM API | Free | Canopy height, elevation change |
| Boulder County Parcels | Boulder County Open Data | GeoJSON download | Free | Asset-level damage assessment |
| Marshall Fire Loss List | Boulder County / State | Public record | Free | ML ground truth labels |
| Boulder County Permits | Boulder County Open Data | GeoJSON | Free | Rebuild completion tracking |
| ESRI Wayback | ArcGIS Living Atlas | WMTS tile API | Free | Historical basemap per date |
| NLCD Land Cover | USGS | Direct download | Free | Pixel classification reference |

**Planetary Computer access — zero cost, zero download:**
```python
import pystac_client, planetary_computer

catalog = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=planetary_computer.sign_inplace,
)
search = catalog.search(
    collections=["landsat-c2-l2"],
    bbox=[-105.16, 39.93, -105.07, 40.01],
    datetime="2021-11-01/2021-12-29",
    query={"eo:cloud_cover": {"lt": 10}}
)
```

---

## 4. Project Structure

Single-event MVP — no plugin framework, no community contributions. One well-structured Python project.

```
marshall-fire/
├── pipeline/
│   ├── run.py                    # single entry point — one command runs everything
│   ├── acquire/
│   │   ├── sentinel1.py          # Planetary Computer SDK
│   │   ├── landsat.py            # Planetary Computer SDK
│   │   ├── lidar.py              # USGS TNM API
│   │   └── parcels_permits.py    # Boulder County open data
│   ├── process/
│   │   ├── sar.py                # GRD → sigma0 → backscatter change → COG
│   │   ├── landsat.py            # calibration → dNBR → NDVI → TIR anomaly → COG
│   │   └── lidar.py              # LAZ → DEM → CHM → COG
│   └── output/
│       ├── parcel_json.py        # mart → detail/{parcel_id}.json
│       ├── timeline_json.py      # timeline.json per observation date
│       └── registry.py           # registry.json
│
├── dbt/
│   ├── profiles.yml              # DuckDB local only
│   └── models/
│       ├── staging/
│       ├── intermediate/
│       └── marts/
│
├── ml/
│   ├── training/                 # notebooks — run once offline, never by pipeline
│   │   ├── 01_siamese_unet.ipynb
│   │   └── 02_fusion_classifier.ipynb
│   ├── models/                   # saved weights — gitignored, stored in R2
│   │   ├── siamese_unet_best.pt
│   │   └── fusion_classifier.keras
│   └── inference/
│       ├── damage.py             # loads weights, runs damage assessment
│       └── rebuild.py            # loads weights, runs rebuild monitoring
│
├── notebooks/                    # exploration only — never imported by pipeline
│   ├── 01_duckdb_columnar_intuition.ipynb
│   ├── 02_sar_first_look.ipynb
│   └── ...                       # see Section 17
│
├── frontend/                     # React + Vite
│   ├── public/
│   │   └── _redirects            # /data/* → R2 proxy — eliminates CORS
│   ├── src/
│   └── vite.config.ts
│
├── config/
│   └── settings.py               # dev | prod only
│
├── scripts/
│   └── deploy.sh                 # push results to R2, then wrangler pages deploy
│
└── docker-compose.yml            # LocalStack + MLflow only
```

**Single pipeline entry point:**

```python
# pipeline/run.py
@click.command()
@click.option('--skip-acquisition', is_flag=True)
@click.option('--skip-processing',  is_flag=True)
@click.option('--skip-ml',          is_flag=True)
@click.option('--env', default='dev')
def run_pipeline(skip_acquisition, skip_processing, skip_ml, env):
    if not skip_acquisition:
        acquire_sentinel1()
        acquire_landsat()
        acquire_lidar()
        acquire_parcels_permits()
    if not skip_processing:
        process_sar()
        process_landsat()
        process_lidar()
    run_dbt()
    if not skip_ml:
        run_damage_inference()
        run_rebuild_inference()
    write_output_json()
```

Skip flags provide partial rerun capability — the main practical value Airflow would have offered.

---

## 5. Pipeline Architecture

A single Python script orchestrates the full pipeline locally. No scheduler, no DAG framework, no persistent services beyond a DuckDB file and a local R2 emulation via LocalStack during dev.

```
python pipeline/run.py
        ↓
acquire_sentinel1()     fetch 5 VV/VH scenes via Planetary Computer
acquire_landsat()       fetch 5 L2 scenes via Planetary Computer
acquire_lidar()         fetch LAZ tiles via USGS TNM API
acquire_parcels()       download Boulder County GeoJSON + permits CSV
        ↓
process_sar()           GRD → sigma0 → terrain correction → change → COG
process_landsat()       calibration → dNBR → NDVI → TIR anomaly → COG
process_lidar()         LAZ → DEM → DSM → CHM → COG
        ↓
run_dbt()               parquet zonal stats → dbt → DuckDB mart
        ↓
run_damage_inference()  load siamese_unet weights → pixel change → parcel scores
run_rebuild_inference() load lstm weights → VV time series → rebuild stages
        ↓
write_output_json()     mart → detail/{parcel_id}.json + timeline.json + registry.json
        ↓
verify locally          npm run dev — inspect map, parcels, charts, time slider
        ↓
scripts/deploy.sh       push results to R2 → wrangler pages deploy → live
```

The last two steps — local verify then deploy — are the entire release process. One review, one command.

**R2 is S3-compatible — pipeline uses boto3 throughout:**

```python
# config/settings.py

@dataclass
class EnvironmentConfig:
    s3_endpoint_url: str
    data_bucket: str
    r2_account_id: str = None

CONFIGS = {
    'dev': EnvironmentConfig(
        s3_endpoint_url='http://localhost:4566',   # LocalStack
        data_bucket='dm-dev-data',
    ),
    'prod': EnvironmentConfig(
        s3_endpoint_url='https://{ACCOUNT_ID}.r2.cloudflarestorage.com',
        data_bucket='dm-prod-data',
    ),
}

# All pipeline code uses this — never touches env vars directly
def get_s3_client(config: EnvironmentConfig):
    return boto3.client(
        's3',
        endpoint_url=config.s3_endpoint_url,
        aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
    )
```

Every `s3.put_object()` and `s3.upload_file()` call works identically in dev and prod — only the endpoint changes.

**docker-compose.yml — LocalStack + MLflow only:**
```yaml
services:
  localstack:
    image: localstack/localstack
    ports: ["4566:4566"]
    environment:
      SERVICES: s3

  mlflow:
    image: ghcr.io/mlflow/mlflow
    ports: ["5000:5000"]
    command: mlflow server --host 0.0.0.0 --backend-store-uri sqlite:///mlflow.db
    volumes: ["./mlflow:/mlflow"]
```

---

## 6. Storage Design

**Local pipeline working directories** — never committed to git:

```
data/
├── raw/
│   ├── sentinel1/             # raw GRD scenes (.tif)
│   ├── landsat/               # raw L2 scenes (.tif)
│   ├── lidar/                 # raw LAZ point clouds
│   ├── parcels/               # Boulder County GeoJSON
│   └── permits/               # Boulder County permits CSV
├── processed/
│   ├── sar/                   # sigma0, terrain-corrected COG
│   ├── landsat/               # calibrated bands COG
│   └── lidar/                 # DEM, DSM, CHM COG
└── tabular/
    ├── sar_zonal_stats.parquet      # pipeline intermediate — DuckDB reads these
    ├── landsat_zonal_stats.parquet
    └── lidar_zonal_stats.parquet
```

**`data/results/` — written locally, verified locally, then pushed to R2:**

```
data/results/
├── registry.json                    # site index
├── timeline.json                    # observation dates + layer URLs per date
├── layers/
│   ├── sar_change_{date}.cog.tif    # served directly, COG range requests
│   ├── dnbr_{date}.cog.tif
│   └── ndvi_{date}.cog.tif
└── parcels/
    ├── index.geojson                # all parcels, lightweight properties
    └── detail/
        └── {parcel_id}.json         # full metrics + time series, loaded on click
```

**Cloudflare R2 — identical layout, zero egress cost:**

```
r2://dm-prod-data/
└── results/                         # exact mirror of data/results/ above
    ├── registry.json
    ├── timeline.json
    ├── layers/*.cog.tif
    └── parcels/...

r2://dm-prod-data/models/            # ML weights — pulled at inference time
    ├── siamese_unet_best.pt
    └── fusion_classifier.keras
```

**Cloudflare Pages — frontend static assets:**

```
marshallfire.yourdomain.com/         # Pages: React bundle
marshallfire.yourdomain.com/data/*   # Pages _redirects: proxied from R2
```

The `_redirects` file makes R2 same-origin from the browser's perspective — no CORS:

```
# frontend/public/_redirects
/data/*  https://dm-prod-data.youraccount.r2.dev/:splat  200
```

**Pre-computed parcel detail — written by pipeline, fetched on click:**
```json
{
  "parcel_id": "12345",
  "address": "123 Elm St, Superior CO",
  "land_use_code": "residential",
  "structure_value": 450000,
  "parcel_area_m2": 720,
  "sar_pixel_count": 7,

  "damage_assessment": {
    "damage_class": "total_loss",
    "confidence": "high",
    "confidence_note": "SAR, SWIR, and TIR signals agree",
    "sar_vv_change_db": -4.2,
    "swir_b7_post": 0.71,
    "tir_b10_anomaly": 2.4,
    "dnbr": 0.68,
    "burn_severity_class": "high",
    "officially_destroyed": true,
    "detection_result": "true_positive"
  },

  "rebuild_monitoring": {
    "rebuild_stage": "complete",
    "rebuild_stage_date": "2024-06",
    "permit_issued_date": "2023-03",
    "timeline": [
      { "date": "2021-11", "vv_db": -5.2, "stage": "baseline" },
      { "date": "2022-01", "vv_db": -9.4, "stage": "destroyed" },
      { "date": "2022-06", "vv_db": -8.1, "stage": "cleared_lot" },
      { "date": "2023-06", "vv_db": -6.8, "stage": "framing" },
      { "date": "2024-06", "vv_db": -5.8, "stage": "complete" }
    ],
    "vv_recovery_pct": 0.94
  }
}
```

**Cloud Optimized GeoTIFF (COG):** All raster outputs converted to COG before R2 upload. Leaflet reads only needed tile via HTTP range requests — no tile server required.

---

## 7. Sensor Strategy — Task Separation

Damage assessment and rebuild monitoring are treated as physically distinct problems requiring different sensor strategies.

### Task 1 — Damage Assessment (Jan 2022): SAR + Landsat IR Fusion

SAR backscatter alone is ambiguous at the damage detection stage — disturbed soil, ash, and wind-scattered debris produce backscatter changes that can mimic structural loss. Landsat SWIR and TIR remove this ambiguity:

```
SAR VV backscatter change    Structural presence/absence (double-bounce loss)
Landsat SWIR Band 7 (2.2μm)  Char and ash — unambiguous fire indicator
Landsat TIR Band 10 (10.9μm) Residual heat signature days post-fire

Fusion resolves ambiguity:
  SAR weak  + SWIR high  →  collapsed burned structure    (total loss)
  SAR strong + SWIR high  →  standing scorched structure   (partial damage)
  SAR strong + SWIR low   →  unburned surviving structure  (survived)
  SAR weak  + SWIR low   →  non-fire structural loss      (other cause)
```

### Task 2 — Rebuild Monitoring (Jun 2022 → 2024): SAR Backscatter Only

Once construction begins, optical sensors become physically blind to progress. All construction materials — concrete, lumber, OSB, Tyvek, roofing — share similar broadband visible/NIR/SWIR albedo. Landsat cannot discriminate a cleared lot from a completed roof.

SAR backscatter responds to corner reflector geometry and dielectric properties, which change unambiguously at each construction phase:

| Stage | VV Return | Physical reason |
|---|---|---|
| Structure destroyed | -9 to -12 dB | Corner reflector gone, soil return only |
| Debris present | -7 to -9 dB | Chaotic rubble scatter, no coherent geometry |
| Lot cleared | -14 to -16 dB | Flat specular surface — return minimum |
| Foundation poured | -12 to -14 dB | Flat concrete, largely specular |
| Framing rising | -8 to -10 dB | Vertical surfaces emerging, double-bounce starting |
| Walls complete | -5 to -7 dB | Strong corner reflector geometry restored |
| Rebuild complete | -4 to -6 dB | Full building geometry, approaches pre-fire baseline |

The cleared-lot stage produces the **lowest** backscatter in the entire sequence — lower than post-fire rubble — because flat concrete eliminates even the chaotic scatter debris provides. This dip is a detectable signal confirming debris removal and aligning with permit issuance dates.

SAR rebuild monitoring is additionally superior to optical because it operates independently of cloud cover, snow, and seasonal illumination — capturing winter construction that optical sensors miss entirely.

### SAR Spatial Resolution — Honest Assessment

Sentinel-1 GRD at 10m provides 6–9 pixels per typical residential lot in the Superior/Louisville AOI. This is marginal for parcel-level classification. Mitigation strategy:

- Landsat dNBR (30m, 3–6 pixels/parcel) is the **primary damage signal**
- SAR contributes as structural presence/absence indicator and **primary rebuild signal**
- Parcels with fewer than 4 SAR pixels are flagged `sar_confidence: low` in parcel detail JSON
- The TF fusion classifier receives `sar_pixel_count` and `parcel_area_m2` as explicit features so it can learn confidence-aware fusion automatically

SAR coherence (SLC mode) is noted as a v2 upgrade — phase decorrelation is more sensitive to structural collapse than backscatter alone and provides better urban discrimination.

---

## 8. dbt Transformation Layer

```
dbt/
├── profiles.yml              # dev=DuckDB, stage/prod=Athena
└── models/
    ├── staging/
    │   ├── stg_sar_backscatter.sql
    │   ├── stg_landsat_indices.sql
    │   ├── stg_lidar_dem.sql
    │   ├── stg_parcels.sql
    │   ├── stg_permits.sql           # Boulder County permits → earliest date per stage per parcel
    │   └── stg_loss_list.sql         # official 1,084-structure loss list
    ├── intermediate/
    │   ├── int_sar_change.sql
    │   ├── int_dnbr.sql
    │   ├── int_ndvi_time_series.sql
    │   ├── int_elevation_change.sql
    │   ├── int_nlcd_join.sql
    │   ├── int_permit_timeline.sql   # one row per parcel — dated stage transitions
    │   └── int_rebuild_labels.sql    # stage label + confidence per parcel per obs date
    └── marts/
        └── marshall_parcel_change.sql    # one row per parcel per date
```

**Mart output — parcel × date grain, task-separated:**

| Column | Source | Task |
|---|---|---|
| parcel_id, address, geom | Boulder County | Identity |
| parcel_area_m2, sar_pixel_count | Derived | Confidence inputs |
| sar_vv_change_db, sar_vh_change_db | Sentinel-1 | Damage assessment |
| swir_b7_post, tir_b10_anomaly | Landsat IR | Damage assessment |
| dnbr_mean, burn_severity_class | Landsat | Damage assessment |
| damage_class, damage_confidence | Derived | Damage assessment output |
| officially_destroyed | Ground truth | ML training label |
| detection_result | Derived | Validation |
| vv_nov2021 → vv_jun2024 | Sentinel-1 time series | Rebuild monitoring |
| vv_recovery_slope, vv_recovery_pct | Derived | Rebuild monitoring |
| rebuild_stage, rebuild_stage_date | Derived | Rebuild monitoring output |
| demo_date, foundation_date, framing_date, coo_date | Boulder County permits | Ground truth labels |
| label_stage_per_obs_date | int_rebuild_labels | LSTM training target |
| label_confidence | int_rebuild_labels | Sample weight source |
| total_permits, max_permit_valuation | Boulder County permits | Data quality indicators |
| chm_mean_pre | LiDAR | Pre-fire canopy context |
| ndvi_2022/2023/2024 | Landsat | Vegetation recovery (supporting) |

---

## 9. ML Stack

Two models, two tasks, two frameworks — each matched to the physical problem it solves.

### PyTorch — Siamese U-Net (pixel-level SAR change, damage assessment)

Two-branch CNN processing pre/post SAR image pairs → per-pixel change probability.

```
Pre-fire SAR patch  → [Encoder Branch A] ─┐
                                           ├→ [Change Head] → change probability map
Post-fire SAR patch → [Encoder Branch B] ─┘
```

- Backbone: ResNet50 pretrained on BigEarthNet via `torchgeo`
- Fine-tuned on Marshall Fire SAR patches (Jan 2022 post-fire)
- Output: per-pixel change probability → aggregated to parcel level
- Used for: damage detection signal fed into fusion classifier

### TensorFlow/Keras — Two-Head Fusion Classifier (parcel-level)

**Head 1 — Damage assessment** (trained on Jan 2022 snapshot features):

```
SAR features (4)     → Dense(32) ─┐
IR/Optical features (5) → Dense(32)─┼→ concatenate → Dense(3, softmax)
Parcel features (5)  → Dense(16) ─┘

Output: [survived, partial_damage, total_loss]

SAR features:       sar_vv_change_db, sar_vh_change_db,
                    sar_pixel_count, sar_vv_vh_ratio_change
IR/Optical:         swir_b7_post, tir_b10_anomaly, dnbr,
                    burn_severity_class_encoded, siamese_change_prob
Parcel:             parcel_area_m2, living_sqft, land_use_encoded,
                    year_built, density_class
```

**Head 2 — Rebuild monitoring** (trained on VV backscatter time series):

```
VV time series (5)   → LSTM(32) ─┐
Recovery metrics (2) → Dense(16) ─┼→ concatenate → Dense(5, softmax)

Output: [cleared_lot, foundation_framing, structure_substantial,
         rebuild_complete, not_applicable (survived parcels)]

VV series:          vv_nov2021, vv_jan2022, vv_jun2022,
                    vv_jun2023, vv_jun2024
Recovery metrics:   vv_recovery_slope, vv_recovery_pct
```

Note: Head 2 uses an LSTM rather than dense layers because rebuild stage is a temporal sequence — the trajectory matters, not just the final value. A parcel whose backscatter dips then rises is rebuilding; one that stays low is not.

Training labels: official 1,084-structure loss list (Head 1) + Boulder County permit timeline via parcel_id join (Head 2) — see Section 9a.

### MLflow — experiment tracking (local, training only)

```python
# MLflow runs locally during notebook training sessions
# Backend: SQLite file — no server needed
# mlflow ui --backend-store-uri sqlite:///mlflow.db

with mlflow.start_run(run_name=f"siamese_unet_v{version}"):
    mlflow.log_params(params)
    mlflow.log_metrics({"precision": 0.91, "recall": 0.88, "f1": 0.89})
    mlflow.pytorch.log_model(model, "siamese_unet")
    mlflow.tensorflow.log_model(model, "fusion_classifier")
```

MLflow is a training-time tool only — it is never called by `pipeline/run.py`. Once training is complete and weights are saved to `ml/models/`, MLflow's job is done. Model weights are pushed to R2 once and pulled down at inference time.

### Accuracy validation — task-separated gates

```python
# Head 1 — damage assessment gate (blocks prod if below threshold)
f1_damage    ≥ 0.75    # wildfire events
precision    ≥ 0.70    # false positives are costly
recall       ≥ 0.70    # false negatives miss real losses

# Head 2 — rebuild monitoring gate (advisory, does not block prod)
# Ground truth is permit dates, which are noisy and delayed
# Reported as informational accuracy metric only
stage_accuracy ≥ 0.65  # advisory threshold
```

---

## 9a. ML Fine-Tuning Plan, Classification Criteria, and Ground Truth Pipeline

### Ground Truth Pipeline — Permit Join (No Geocoding)

Boulder County publishes two datasets that share a common key:

```
Parcel boundaries (GeoJSON)    key: parcel_id (12-digit APN)
Building permits (CSV)         key: parcel_id (same APN)
```

This is a direct table join — no geocoding, no address string parsing, no coordinate matching. Geocoding would introduce address normalization errors, multi-unit ambiguity, and API dependencies that a structured key join never has.

```python
parcels = gpd.read_file("boulder_county_parcels.geojson")
permits = pd.read_csv("boulder_county_permits.csv")

# Direct join on parcel_id — deterministic, exact, no ambiguity
parcels_with_permits = parcels.merge(
    permits[permits['permit_type'].isin(REBUILD_PERMIT_TYPES)],
    on='parcel_id',
    how='left'
)
```

**Permit filter — rebuild-relevant types only:**

```python
REBUILD_PERMIT_TYPES = [
    'New Single Family Dwelling',
    'New Multi-Family Dwelling',
    'Addition/Alteration Residential',
    'Foundation Only',
    'Framing Inspection',
    'Demolition',
]
# Date window: 2022-01-01 → 2024-12-31
```

**Multiple permits per parcel — exploit the full sequence:**

A complete rebuild generates 3–5 permits in sequence. Each maps to a distinct rebuild stage, providing dated transitions rather than a single timestamp:

```
2022-03-15  Demolition permit          → cleared_lot confirmed
2022-08-20  Foundation permit          → foundation_framing confirmed
2023-01-10  Framing inspection         → structure_substantial confirmed
2023-09-05  Certificate of Occupancy   → rebuild_complete confirmed
```

**dbt model — `stg_permits.sql`:**

```sql
with raw_permits as (
    select
        parcel_id,
        permit_type,
        cast(issue_date as date)   as issue_date,
        cast(finaled_date as date) as finaled_date,
        valuation,
        case
            when permit_type ilike '%demolition%'              then 'cleared_lot'
            when permit_type ilike '%foundation%'              then 'foundation_framing'
            when permit_type ilike '%framing%'
              or permit_type ilike '%structural%'              then 'structure_substantial'
            when permit_type ilike '%certificate of occupancy%'
              or permit_type ilike '%final%'                   then 'rebuild_complete'
            when permit_type ilike '%new single family%'
              or permit_type ilike '%new multi%'               then 'rebuild_start'
            else 'other'
        end as implied_stage
    from {{ source('raw', 'boulder_county_permits') }}
    where issue_date between '2022-01-01' and '2024-12-31'
),
parcel_permit_timeline as (
    select
        parcel_id,
        min(case when implied_stage = 'cleared_lot'
            then issue_date end)          as demo_date,
        min(case when implied_stage = 'foundation_framing'
            then issue_date end)          as foundation_date,
        min(case when implied_stage = 'structure_substantial'
            then issue_date end)          as framing_date,
        min(case when implied_stage = 'rebuild_complete'
            then issue_date end)          as coo_date,
        count(permit_number)              as total_permits,
        max(valuation)                    as max_permit_valuation
    from raw_permits
    group by parcel_id
)
select * from parcel_permit_timeline
```

**`int_rebuild_labels.sql` — stage label + confidence per parcel per observation date:**

Each parcel × observation date gets a stage label and a confidence weight. The LSTM is trained with sample weights so high-confidence permit-confirmed labels drive learning, low-confidence inferred labels contribute but don't dominate:

```
Label confidence → sample weight
high   (permit confirmed)          1.0
medium (partial permit evidence)   0.6
low    (inferred, no permit)        0.3
```

**Data quality reality — known gaps:**

```
Fully permitted rebuilds      ~70% of destroyed parcels  → high confidence labels
Partial permit records        ~20%                        → medium confidence
No permit record              ~10%                        → low confidence
    (non-rebuilt parcels OR permits not yet in public data)
    (these form the negative class for rebuild completion)
```

The 10% with no permits are useful training data — they represent parcels that remained unbuilt through 2024, anchoring the negative end of the rebuild spectrum.

**Note for framework contributors:** The parcel_id join approach requires the target jurisdiction to publish parcel + permit data with a shared key. Boulder County's open data infrastructure is unusually clean. Contributors using this framework for other disasters should document their ground truth join method and label confidence strategy explicitly.

---

### PyTorch Siamese U-Net — Fine-Tuning Protocol

**Patch extraction:**

```python
PATCH_SIZE = 64    # 64×64 pixels = 640m × 640m at 10m resolution
                   # includes parcel + neighborhood context
                   # pre-fire: Nov 2021 VV+VH, post-fire: Jan 2022 VV+VH
# ~4,800 patch pairs total
# 1,084 positive (destroyed), ~3,700 negative (survived + grassland)
```

**Spatial train/val/test split — not random:**

```
Block 1: West Superior (McCaslin corridor)     train
Block 2: East Superior (Sagamore)              train
Block 3: West Louisville (downtown)            train
Block 4: East Louisville                       held-out test (never seen during training)
~70% train / 15% val / 15% test by parcel count
```

Random splitting leaks spatial autocorrelation — Sentinel-1 SAR has systematic azimuth/range patterns across adjacent pixels. Spatial blocking is the methodologically correct approach and eliminates 5–10 point inflation in apparent validation accuracy.

**Class imbalance — 1:3.4 positive:negative:**

```python
# Weighted loss + oversampling augmented positives
pos_weight = torch.tensor([3.4])
criterion  = CombinedLoss(bce_weight=0.5, dice_weight=0.5, pos_weight=3.4)

# SAR-valid augmentations only:
#   horizontal/vertical flip, 90° rotation, speckle noise addition
# NOT: color jitter, brightness — meaningless for SAR backscatter
```

**Two-stage fine-tuning:**

```
Stage 1 (10 epochs)   Freeze backbone, train change head only
                      LR = 1e-3
                      Head learns Marshall Fire damage signature
                      against stable pretrained spatial features

Stage 2 (20 epochs)   Unfreeze top 2 encoder blocks (layer3 + layer4)
                      LR = 1e-4 — conservative, preserve pretrained weights
                      Upper encoder fine-tunes to Marshall Fire geometry
                      Lower encoder stays frozen (generic edge/texture detection)
                      CosineAnnealingLR scheduler
                      Early stopping patience = 5 on val F1
```

**Loss function — combined BCE + Dice:**

BCE handles pixel-level class imbalance. Dice directly optimizes spatial overlap — the metric that matters for change masks. Combined loss is standard for segmentation tasks.

---

### Classification Criteria — Task 1: SAR + Landsat IR Fusion (Damage Assessment)

**Signal definitions:**

```
VV_CHANGE_DB     = VV_post_db - VV_pre_db
                   Negative → backscatter loss → structure likely absent
SWIR_B7_POST     = Landsat Band 7 (2.2μm) surface reflectance, Jan 2022
                   High → char and ash present → fire indicator
TIR_B10_ANOMALY  = TIR_B10_post - TIR_B10_multi_year_jan_baseline
                   Positive → elevated surface temperature above seasonal norm
DNBR             = NBR_pre - NBR_post
                   Standard USGS MTBS burn severity composite index
```

**Decision tree — fusion resolves SAR ambiguity:**

```
STEP 1 — SWIR screen (fire exposure?)

    SWIR_B7_POST < 0.15 AND dNBR < 0.10
        → class = survived_no_fire_exposure   confidence = high
        → exit (optical alone sufficient, no SAR needed)

    SWIR_B7_POST >= 0.15 OR dNBR >= 0.10
        → fire exposure confirmed → proceed to Step 2

STEP 2 — SAR structural signal

    VV_CHANGE_DB > -2.0 dB
        → class = survived_fire_exposed       confidence = medium
        → (scorched but standing)

    -2.0 to -4.0 dB
        → moderate backscatter loss → proceed to Step 3

    VV_CHANGE_DB <= -4.0 dB
        → strong loss → class = total_loss
        → confidence = high   if SWIR_B7_POST >= 0.30
        → confidence = medium if SWIR_B7_POST < 0.30
        → exit

STEP 3 — TIR disambiguation (moderate SAR loss zone)

    TIR_B10_ANOMALY >= 1.5 K AND SWIR_B7_POST >= 0.25
        → class = total_loss      confidence = medium

    otherwise
        → class = partial_damage  confidence = low
        → flag for manual review
```

**Threshold rationale:**

```
VV_CHANGE_DB = -2.0 dB    Published C-band structural change floor
                           (Trianni & Gamba 2009, Brunner et al. 2010)
                           Below = within speckle noise for residential structures
VV_CHANGE_DB = -4.0 dB    Strong double-bounce loss
                           >70% structural footprint loss at Marshall Fire density
SWIR_B7_POST = 0.15        Conservative lower bound for post-fire char/ash
SWIR_B7_POST = 0.30        Moderate char — active combustion confirmed
TIR_B10_ANOMALY = 1.5 K   Conservative residual heat threshold, 3–5 days post-fire
DNBR = 0.10                USGS MTBS unburned/low-severity boundary
DNBR = 0.44                USGS MTBS moderate-high severity boundary
```

**Confidence score — continuous signal for TF classifier:**

Signal agreement ratio × SAR spatial confidence. Four signals (SAR, SWIR, TIR, dNBR) each contribute. Pixel count penalty applied for parcels with fewer than 6 SAR pixels. All four agreeing on a 7-pixel parcel = 1.0. One signal on a 3-pixel parcel = ~0.17.

**Classification summary table:**

| Class | VV Change | SWIR B7 | TIR Anomaly | dNBR | Confidence |
|---|---|---|---|---|---|
| survived_no_fire | > -2.0 dB | < 0.15 | any | < 0.10 | high |
| survived_fire_exposed | > -2.0 dB | ≥ 0.15 | any | ≥ 0.10 | medium |
| partial_damage | -2.0 to -4.0 dB | any | < 1.5 K | any | low |
| total_loss | ≤ -4.0 dB | ≥ 0.30 | ≥ 1.5 K | ≥ 0.44 | high |
| total_loss | ≤ -4.0 dB | ≥ 0.30 | < 1.5 K | any | medium |
| uncertain | ambiguous combination | — | — | — | low |

---

### Classification Criteria — Task 2: SAR Only (Rebuild Monitoring)

**Baseline normalization — applied before all thresholds:**

```python
# Parcel-relative normalization removes acquisition geometry and
# seasonal soil moisture variation without absolute calibration
VV_NORM(t) = VV(t) - VV_BASELINE
VV_BASELINE = median(Nov 2021, Oct 2021, Sep 2021)   # 3-scene speckle reduction
```

**Rebuild stage thresholds (normalized values):**

| Stage | Delta from Baseline | Recovery % | Physical reason |
|---|---|---|---|
| destroyed | < -6.0 dB | < 0.05 | Corner reflector gone, soil return only |
| cleared_lot | < -8.0 dB | < 0.10 | Flat surface — specular minimum, lower than rubble |
| foundation_framing | -4.0 to -8.0 dB | 0.10–0.35 | Vertical surfaces emerging, double-bounce starting |
| structure_substantial | -1.5 to -4.0 dB | 0.35–0.75 | Walls up, corner reflectors forming |
| rebuild_complete | > -1.5 dB | ≥ 0.75 | Full building geometry, approaches pre-fire baseline |

The cleared_lot stage produces the **lowest** backscatter in the entire sequence — flat concrete eliminates even the chaotic scatter that debris provides. This dip is a detectable confirmatory signal aligning with demolition permit dates.

**Trajectory validation — monotonic enforcement:**

Buildings don't un-build. Spurious speckle spikes (construction equipment, wet soil, adjacent activity) are caught by enforcing valid stage transitions. An impossible jump is held at the previous stage and flagged as uncertain in the parcel detail JSON.

```
Valid transitions:
destroyed           → cleared_lot, foundation_framing
cleared_lot         → cleared_lot, foundation_framing
foundation_framing  → foundation_framing, structure_substantial
structure_substantial → structure_substantial, rebuild_complete
rebuild_complete    → rebuild_complete
```

**LSTM training — label assignment from permit timeline:**

```
obs_date ≤ 2022-01   → destroyed           (all confirmed losses)    conf = high
2022-06              → stage from permit    demo/foundation dates     conf = high/medium
2023-06              → stage from permit    framing/COO dates         conf = high/medium
2024-06              → stage from permit    COO + 12-month lag        conf = high/medium
no permit record     → inferred from SAR    trajectory only           conf = low
```

LSTM input features: `(vv_norm, vv_delta_from_prev, acquisition_doy)` per timestep. `acquisition_doy` normalizes for seasonal soil moisture variation between Jan and Jun acquisitions. Parcel context (area, pixel count, land use) fed in parallel dense branch, not through LSTM.

---

## 10. Frontend — Exhibition Design

The site is a National Geographic-style scrollytelling feature. The story is told first; the interactive tools appear only after the reader understands what they are looking at. It demonstrates full-stack taste as clearly as the pipeline demonstrates engineering depth.

---

### Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Framework | React 18 + TypeScript | Complex interdependent scroll + map + chart state |
| Build | Vite 5 | Fast dev server, optimized Pages deploy |
| Styling | CSS custom properties + CSS modules | Ghibli palette as design tokens, no Tailwind class soup |
| Scroll engine | Intersection Observer API | No ScrollMagic, no GSAP — native, zero weight |
| Map | Leaflet + react-leaflet | Open source, COG range requests, no API billing |
| COG rendering | georaster-layer-for-leaflet | R2 COG → browser tiles, no tile server |
| Historical basemap | ESRI Wayback WMTS | Weekly snapshots since 2014 — pre/post fire optical |
| State | Zustand | Scroll stage × map layer × parcel selection |
| Data fetching | TanStack Query | Caches timeline.json + parcel detail JSON |
| Charts | recharts | SAR VV time series sparklines in parcel popup |
| Typography | Lora (display) + Source Sans 3 (body) | Lora has the editorial authority of a magazine headline — not Inter, not Roboto |

---

### Ghibli Color System — 70 / 20 / 10

Studio Ghibli's palette is distinctive for the same reason it works here: it is naturalistic and muted, never garish. It makes data feel like landscape rather than dashboard. The films consistently use desaturated earth tones as dominant, warm amber-greens as mid-layer, and single luminous accents for the thing that matters.

```css
/* design-tokens.css — the single source of truth */
:root {

  /* ── 70% DOMINANT — Deep Totoro Forest ───────────────────────────── */
  /* Inspired by the forest floor and night sky in My Neighbor Totoro   */
  /* and Princess Mononoke. Dark, organic, serious. Not pure black.     */
  --color-base-900: #0d1117;   /* page background — near-black with blue undertone */
  --color-base-800: #161c26;   /* section backgrounds */
  --color-base-700: #1e2a38;   /* card backgrounds, popup backgrounds */
  --color-base-600: #2a3a4e;   /* borders, dividers */
  --color-base-100: #e8e0d4;   /* body text — warm off-white, not pure white */
  --color-base-200: #c4b9a8;   /* secondary text, captions */
  --color-base-300: #8a7d6b;   /* muted labels, metadata */

  /* ── 20% ACCENT — Mononoke Ash and Moss ─────────────────────────── */
  /* The mid-tones that give the palette its naturalistic character.    */
  /* Desaturated olive and dusty sage — never bright green.             */
  --color-accent-moss:   #4a5e3a;   /* survived parcels, positive state */
  --color-accent-olive:  #6b7a3e;   /* rebuilt parcels, recovery state */
  --color-accent-ash:    #8b6f4e;   /* fire/damage indicator — muted amber-brown */
  --color-accent-smoke:  #5a6472;   /* neutral parcel borders, inactive states */
  --color-accent-fog:    #3d4e5c;   /* timeline track, slider backgrounds */

  /* ── 10% HIGHLIGHT — Kiki Amber ─────────────────────────────────── */
  /* One luminous color. Used sparingly — findings callout, active      */
  /* parcel ring, the one number that matters, interactive hover state. */
  /* Inspired by Kiki's bow and the golden light in Spirited Away.      */
  --color-highlight:      #e8a030;  /* primary highlight — warm amber */
  --color-highlight-soft: #c4852a;  /* hover state, secondary emphasis */
  --color-highlight-dim:  #8a5a1a;  /* disabled highlight, background tint */

  /* ── Semantic damage palette (maps to above, never new colors) ───── */
  --color-total-loss:         var(--color-accent-ash);
  --color-partial-damage:     #7a6040;     /* between ash and olive */
  --color-survived:           var(--color-accent-smoke);
  --color-rebuild-complete:   var(--color-accent-olive);
  --color-rebuild-active:     #5a7040;     /* between moss and olive */
  --color-cleared-lot:        var(--color-base-600);

  /* ── Typography ─────────────────────────────────────────────────── */
  --font-display: 'Lora', Georgia, serif;        /* section headlines */
  --font-body:    'Source Sans 3', sans-serif;   /* body, UI, labels */
  --font-mono:    'JetBrains Mono', monospace;   /* dB values, coordinates */

  /* ── Motion ─────────────────────────────────────────────────────── */
  --transition-reveal:  opacity 0.8s ease, transform 0.8s ease;
  --transition-map:     0.6s ease-in-out;
  --transition-hover:   0.15s ease;
}
```

**The constraint that makes it work:** `--color-highlight` appears in at most one element per viewport at any time. When everything competes for attention nothing has it. In a NatGeo feature the amber accent is used for exactly the thing the editor wants you to read — then not again until the next section.

---

### Typography Decisions

```css
/* Section headlines — Lora gives editorial weight without pomposity */
.section-headline {
  font-family: var(--font-display);
  font-size: clamp(2rem, 5vw, 3.5rem);
  font-weight: 600;
  color: var(--color-base-100);
  line-height: 1.15;
  letter-spacing: -0.02em;
}

/* The key finding — one per section, in amber */
.finding-stat {
  font-family: var(--font-display);
  font-size: clamp(3rem, 8vw, 6rem);
  font-weight: 700;
  color: var(--color-highlight);
  line-height: 1;
}

/* Body copy — Source Sans 3 is readable and invisible */
.body-copy {
  font-family: var(--font-body);
  font-size: 1.125rem;
  color: var(--color-base-200);
  line-height: 1.75;
  max-width: 65ch;         /* editorial column width */
}

/* Data annotations — monospace for values, not body */
.data-label {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--color-base-300);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
```

---

### Scroll Architecture — Six Sections

The site is a single vertical scroll. No routing, no page transitions, no tabs. The depth gate pattern — story first, tools second — is enforced by layout, not logic.

```
SECTION 1 — THE NIGHT         Full viewport. One image. One line. No chrome.
SECTION 2 — WHAT WAS LOST     SAR reveal. Annotation. "This is not a photograph."
SECTION 3 — THE RECOVERY      Auto-animated time lapse. The 38% number.
SECTION 4 — WHAT WE FOUND     Three finding cards. Scroll-revealed one at a time.
SECTION 5 — EXPLORE           Depth gate opens. Interactive map + Ask panel.
SECTION 6 — HOW IT WAS BUILT  One pipeline diagram. GitHub link.
```

```typescript
// hooks/useScrollReveal.ts — the entire scroll engine

export function useScrollReveal(threshold = 0.35) {
  const ref  = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true) },
      // Once revealed, stays revealed — no re-hide on scroll back
      { threshold }
    )
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])

  return { ref, visible }
}
```

```css
/* The only animation class pair needed */
.reveal        { opacity: 0; transform: translateY(28px); }
.reveal.visible {
  opacity: 1;
  transform: translateY(0);
  transition: var(--transition-reveal);
}

/* Staggered children — finding cards appear 200ms apart */
.reveal.visible:nth-child(2) { transition-delay: 0.2s; }
.reveal.visible:nth-child(3) { transition-delay: 0.4s; }
```

---

### Section 1 — The Hook

```tsx
// components/sections/HookSection.tsx

export function HookSection() {
  return (
    <section className="hook-section">
      {/* Full-viewport pre-fire ESRI Wayback image — Dec 2021 */}
      <div className="hook-image">
        <WaybackBasemap
          date="2021-12"
          interactive={false}
          className="hook-map"
        />
        {/* Grain overlay — adds editorial texture, softens the satellite image */}
        <div className="grain-overlay" />
      </div>

      <div className="hook-text">
        <p className="hook-dateline">Superior & Louisville, Colorado</p>
        <h1 className="hook-headline">
          On December 30, 2021,<br />
          a wind-driven fire consumed<br />
          <span className="hook-number">1,084 homes</span><br />
          in four hours.
        </h1>
        <p className="hook-subhead">
          This is a satellite record of what burned — and what came after.
        </p>
        <div className="hook-scroll-hint">
          <span>↓</span>
        </div>
      </div>
    </section>
  )
}
```

```css
.hook-section {
  position: relative;
  height: 100vh;
  display: flex;
  align-items: flex-end;
  padding: 0 0 8vh 8vw;
  overflow: hidden;
}

.hook-map {
  position: absolute;
  inset: 0;
  filter: saturate(0.6) brightness(0.55);  /* desaturate to Ghibli muted range */
  pointer-events: none;
}

.grain-overlay {
  position: absolute;
  inset: 0;
  background-image: url('/noise.svg');     /* SVG noise texture — 2kb */
  opacity: 0.04;
  pointer-events: none;
}

/* Bottom gradient — text reads against map without a box */
.hook-section::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 65%;
  background: linear-gradient(to top,
    var(--color-base-900) 0%,
    transparent 100%
  );
  pointer-events: none;
}

.hook-text { position: relative; z-index: 2; }

.hook-dateline {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--color-highlight);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin-bottom: 1.5rem;
}

.hook-headline {
  font-family: var(--font-display);
  font-size: clamp(2.5rem, 6vw, 4.5rem);
  font-weight: 600;
  color: var(--color-base-100);
  line-height: 1.2;
  margin-bottom: 1.5rem;
}

.hook-number {
  color: var(--color-highlight);
  /* No other styling — amber on off-white is enough */
}

.hook-scroll-hint {
  color: var(--color-base-300);
  font-size: 1.5rem;
  animation: nudge 2.5s ease-in-out infinite;
}

@keyframes nudge {
  0%, 100% { transform: translateY(0); opacity: 0.4; }
  50%       { transform: translateY(8px); opacity: 0.8; }
}
```

---

### Section 2 — The SAR Reveal

The burn scar appears as the user scrolls in. An annotation explains that this is not a photograph — the most important single sentence in the exhibition.

```tsx
// components/sections/LossSection.tsx

export function LossSection() {
  const { ref, visible } = useScrollReveal(0.3)

  return (
    <section className="loss-section" ref={ref}>
      <div className={`loss-map-container reveal ${visible ? 'visible' : ''}`}>
        {/* Locked, non-interactive SAR change image */}
        <ScrollMap
          layer="sar_change"
          date="2022-01"
          interactive={false}
        />
        <SARAnnotation visible={visible} />
      </div>

      <div className="loss-text">
        <p className="section-eyebrow">January 2022 — Two weeks after the fire</p>
        <h2 className="section-headline">
          Sentinel-1 radar captured the damage through smoke and cloud.
        </h2>
        <p className="body-copy">
          The amber areas lost structural radar backscatter — the physical
          signature of a building collapsing. Red is not fire. It is silence
          where a corner reflector used to be.
        </p>
        <div className="sar-explainer">
          <span className="data-label">What SAR measures</span>
          <p>
            C-band radar reflects strongly off building corners.
            When a structure burns, the double-bounce geometry disappears.
            The signal drops 4–8 dB — detectable from 700km altitude,
            regardless of smoke, cloud, or time of day.
          </p>
        </div>
      </div>
    </section>
  )
}

// The "This is not a photograph" annotation — appears 600ms after section reveal
function SARAnnotation({ visible }: { visible: boolean }) {
  return (
    <div className={`sar-annotation ${visible ? 'annotation-visible' : ''}`}>
      <div className="annotation-line" />
      <p className="annotation-text">
        This is not a photograph.<br />
        <span>Sentinel-1 SAR — 10m resolution — January 15 2022</span>
      </p>
    </div>
  )
}
```

```css
.loss-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 100vh;
  gap: 0;
}

/* Map occupies left half, locked */
.loss-map-container {
  position: sticky;
  top: 0;
  height: 100vh;
}

/* Text scrolls on the right */
.loss-text {
  padding: 15vh 6vw 15vh 5vw;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2rem;
}

.section-eyebrow {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--color-highlight);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

/* Annotation fades in with delay */
.sar-annotation {
  position: absolute;
  bottom: 8%;
  left: 5%;
  opacity: 0;
  transition: opacity 0.8s ease 0.6s;
}
.annotation-visible { opacity: 1; }

.annotation-line {
  width: 32px;
  height: 1px;
  background: var(--color-highlight);
  margin-bottom: 0.75rem;
}

.annotation-text {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--color-base-200);
  letter-spacing: 0.04em;
  line-height: 1.7;
}
.annotation-text span {
  color: var(--color-base-300);
  font-size: 0.62rem;
}
```

---

### Section 3 — The Recovery Arc

The time lapse auto-plays on scroll entry. Parcels shift from amber-ash to olive as rebuilds complete. The finding number counts up on reveal.

```tsx
// components/sections/RecoverySection.tsx

const DATES = ['2022-01', '2022-06', '2023-06', '2024-06']

export function RecoverySection() {
  const { ref, visible }        = useScrollReveal(0.3)
  const [dateIndex, setDateIndex] = useState(0)
  const [counting, setCounting]   = useState(false)
  const [displayPct, setDisplayPct] = useState(0)

  // Auto-play time lapse once section is visible
  useEffect(() => {
    if (!visible) return
    const interval = setInterval(() => {
      setDateIndex(i => {
        if (i >= DATES.length - 1) { clearInterval(interval); return i }
        return i + 1
      })
    }, 1400)
    setTimeout(() => setCounting(true), 800)
    return () => clearInterval(interval)
  }, [visible])

  // Count up to 38 over 1.2s once triggered
  useEffect(() => {
    if (!counting) return
    const target = 38
    const steps  = 40
    let step = 0
    const timer = setInterval(() => {
      step++
      setDisplayPct(Math.round((target * step) / steps))
      if (step >= steps) clearInterval(timer)
    }, 30)
    return () => clearInterval(timer)
  }, [counting])

  return (
    <section className="recovery-section" ref={ref}>
      <div className="recovery-map-container">
        <ScrollMap
          layer="parcel_damage"
          date={DATES[dateIndex]}
          interactive={false}
          showParcelColors
        />
        <div className="date-badge">
          <span className="data-label">Observation</span>
          <span className="date-value">{DATES[dateIndex].replace('-', ' / ')}</span>
        </div>
      </div>

      <div className="recovery-text">
        <p className="section-eyebrow">2022 — 2024</p>
        <h2 className="section-headline">
          The recovery is still unfinished.
        </h2>

        <div className={`finding-stat-block reveal ${visible ? 'visible' : ''}`}>
          <span className="finding-stat">{displayPct}%</span>
          <p className="finding-caption">
            of destroyed homes have not rebuilt<br />
            as of June 2024
          </p>
        </div>

        <p className="body-copy">
          Three years after the fire, 415 of the 1,084 destroyed structures
          remain unbuilt. The permits exist. The lots are cleared.
          The radar signal confirms the absence.
        </p>

        {/* Small recovery pace bar chart */}
        <RecoveryBarChart visible={visible} />
      </div>
    </section>
  )
}
```

```css
.finding-stat {
  font-family: var(--font-display);
  font-size: clamp(4rem, 10vw, 7rem);
  font-weight: 700;
  color: var(--color-highlight);
  line-height: 1;
  display: block;
}

.finding-caption {
  font-family: var(--font-body);
  font-size: 1rem;
  color: var(--color-base-200);
  margin-top: 0.5rem;
  line-height: 1.5;
}

.date-badge {
  position: absolute;
  top: 1.5rem;
  right: 1.5rem;
  background: var(--color-base-800);
  border: 1px solid var(--color-base-600);
  padding: 0.5rem 0.75rem;
  border-radius: 2px;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.date-value {
  font-family: var(--font-mono);
  font-size: 0.9rem;
  color: var(--color-base-100);
}
```

---

### Section 4 — Findings

Three cards, each a self-contained finding. Staggered reveal — one every 200ms. Each card has a micro-visualization that supports the text.

```tsx
// components/sections/FindingsSection.tsx

const FINDINGS = [
  {
    id: 'demolition-dip',
    eyebrow: 'SAR Signature',
    headline: 'The demolished-lot dip.',
    body: `After demolition, radar backscatter drops below the post-fire
           rubble level. Concrete slabs are more specularly reflective
           than debris — the signal briefly gets quieter before rebuilding
           begins. This 8-week window is visible from orbit and aligns
           precisely with demolition permit dates.`,
    viz: <DemolitionDipSparkline />,
    // The sparkline shows the VV time series dipping lower post-demolition
    // than post-fire — the physically unexpected finding
  },
  {
    id: 'parcel-size',
    eyebrow: 'Recovery Pattern',
    headline: 'Smaller lots rebuilt at lower rates.',
    body: `Properties under 500m² completed rebuilds at 40% lower rates
           than properties over 800m². Satellite data alone cannot explain
           why — but the signal is consistent across all neighborhoods.
           Financial constraint is the most plausible hypothesis.`,
    viz: <ParcelSizeScatter />,
  },
  {
    id: 'creek-anomaly',
    eyebrow: 'Sensor Fusion',
    headline: 'The creek corridor needed infrared.',
    body: `Soil moisture along Coal Creek caused SAR to misclassify
           intact structures as damaged. Adding Landsat thermal infrared
           reduced false positives by 8 percentage points in that corridor.
           This is why the project fuses two sensors rather than relying
           on SAR alone.`,
    viz: <CreekAnomalyMap />,
  },
]

export function FindingsSection() {
  const { ref, visible } = useScrollReveal(0.2)

  return (
    <section className="findings-section" ref={ref}>
      <div className="findings-header">
        <p className="section-eyebrow">What the data reveals</p>
        <h2 className="section-headline">
          Three things only satellite radar could show.
        </h2>
      </div>

      <div className="findings-grid">
        {FINDINGS.map((f, i) => (
          <div
            key={f.id}
            className={`finding-card reveal ${visible ? 'visible' : ''}`}
            style={{ transitionDelay: `${i * 0.2}s` }}
          >
            <div className="finding-viz">{f.viz}</div>
            <p className="finding-eyebrow">{f.eyebrow}</p>
            <h3 className="finding-headline">{f.headline}</h3>
            <p className="finding-body">{f.body}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
```

```css
.findings-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 2px;                            /* hairline gaps between cards */
  margin-top: 4rem;
}

.finding-card {
  background: var(--color-base-800);
  padding: 2rem 1.75rem 2.5rem;
  border-top: 2px solid var(--color-base-600);
  transition: border-color var(--transition-hover);
}

.finding-card:hover {
  border-top-color: var(--color-highlight);
}

.finding-viz {
  height: 120px;
  margin-bottom: 1.75rem;
  /* Each viz is a small recharts component — 
     same muted Ghibli palette, no axis chrome */
}

.finding-eyebrow {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--color-highlight);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 0.5rem;
}

.finding-headline {
  font-family: var(--font-display);
  font-size: 1.3rem;
  color: var(--color-base-100);
  line-height: 1.3;
  margin-bottom: 1rem;
}

.finding-body {
  font-family: var(--font-body);
  font-size: 0.9rem;
  color: var(--color-base-200);
  line-height: 1.7;
}
```

---

### Section 5 — Explore (Depth Gate)

The full interactive map and RAG panel appear here — after the story has been told. The transition into this section is the only moment that feels like a "product" rather than a feature article.

```tsx
// components/sections/ExploreSection.tsx

export function ExploreSection() {
  const { ref, visible } = useScrollReveal(0.15)

  return (
    <section className="explore-section" ref={ref}>
      <div className={`explore-header reveal ${visible ? 'visible' : ''}`}>
        <p className="section-eyebrow">Every parcel. Every observation.</p>
        <h2 className="section-headline">Explore the full dataset.</h2>
        <p className="body-copy">
          Click any parcel to see its radar signature, permit timeline,
          and rebuild stage. Use the time slider to move through five
          years of observations. Ask the data a question.
        </p>
      </div>

      <div className={`explore-map-wrapper reveal ${visible ? 'visible' : ''}`}
           style={{ transitionDelay: '0.25s' }}>
        <ExploreMap />           {/* fully interactive Leaflet instance */}
        <TimelineSlider />
        <LayerPanel />
      </div>

      <div className={`ask-wrapper reveal ${visible ? 'visible' : ''}`}
           style={{ transitionDelay: '0.4s' }}>
        <AskPanel />
      </div>
    </section>
  )
}
```

**Parcel popup — exhibition quality:**

```tsx
// components/ParcelPopup.tsx

export function ParcelPopup({ parcel }: { parcel: ParcelDetail }) {
  const { damage, rebuild, permits } = parcel

  return (
    <div className="parcel-popup">
      <div className="popup-header">
        <h4 className="popup-address">{parcel.address}</h4>
        <span
          className="popup-damage-badge"
          data-class={damage.damage_class}
        >
          {damage.damage_class.replace('_', ' ')}
        </span>
      </div>

      {/* VV time series sparkline — the demolished-lot dip visible here */}
      <div className="popup-sparkline">
        <VVSparkline
          series={rebuild.vv_series}
          stages={rebuild.stage_annotations}
          baseline={0}
        />
        <span className="data-label">SAR VV backscatter — normalized</span>
      </div>

      {/* Permit timeline — horizontal, dates as tick marks */}
      {damage.damage_class === 'total_loss' && (
        <div className="popup-permits">
          <PermitTimeline permits={permits} />
        </div>
      )}

      <div className="popup-metrics">
        <Metric label="VV Change"  value={`${damage.sar_vv_change_db} dB`} />
        <Metric label="SWIR B7"    value={damage.swir_b7_post.toFixed(2)} />
        <Metric label="Confidence" value={damage.confidence} />
        {rebuild.months_to_completion && (
          <Metric label="Time to rebuild"
                  value={`${rebuild.months_to_completion} months`}
                  highlight />
        )}
      </div>

      <button
        className="popup-ask-btn"
        onClick={() => openAskPanel(parcel.address)}
      >
        Ask about this parcel →
      </button>
    </div>
  )
}
```

```css
.parcel-popup {
  background: var(--color-base-700);
  border: 1px solid var(--color-base-600);
  border-top: 2px solid var(--color-highlight);
  padding: 1.25rem;
  width: 300px;
  font-family: var(--font-body);
}

.popup-address {
  font-family: var(--font-display);
  font-size: 1rem;
  color: var(--color-base-100);
  margin-bottom: 0.5rem;
}

.popup-damage-badge {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 0.2rem 0.5rem;
  border-radius: 2px;
}

/* Badge color maps to semantic damage palette */
[data-class="total_loss"]        { background: var(--color-accent-ash);    color: var(--color-base-900); }
[data-class="survived"]          { background: var(--color-accent-smoke);  color: var(--color-base-100); }
[data-class="rebuild_complete"]  { background: var(--color-accent-olive);  color: var(--color-base-900); }

.popup-sparkline {
  margin: 1.25rem 0;
  height: 72px;
}

.popup-metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin: 1rem 0;
  padding-top: 1rem;
  border-top: 1px solid var(--color-base-600);
}

.popup-ask-btn {
  width: 100%;
  padding: 0.6rem;
  background: transparent;
  border: 1px solid var(--color-highlight-dim);
  color: var(--color-highlight);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  letter-spacing: 0.06em;
  cursor: pointer;
  transition: background var(--transition-hover),
              border-color var(--transition-hover);
}

.popup-ask-btn:hover {
  background: var(--color-highlight-dim);
  border-color: var(--color-highlight);
}
```

---

### Section 6 — Methodology

Minimal. One diagram, four callouts, two links. The visual proves the engineering happened — it doesn't explain it in full.

```
[ Sentinel-1 GRD ]  [ Landsat 8/9 ]  [ USGS LiDAR ]
        ↓                  ↓                ↓
   SAR processing     IR calibration    DEM/CHM
   sigma0 → COG       dNBR, SWIR, TIR   canopy height
              ↓              ↓
          Zonal stats  →  dbt / DuckDB
                               ↓
              Siamese U-Net + Fusion Classifier + LSTM
                               ↓
                    Pre-computed JSON + COG
                               ↓
            Cloudflare Pages  +  R2  +  Workers AI
```

Links: `[View on GitHub]`  `[Full methodology]`

---

### Component Tree

```
App
└── ScrollStory
    ├── HookSection           full viewport, locked Wayback map, no chrome
    ├── LossSection           sticky SAR map (left) + scrolling text (right)
    ├── RecoverySection       auto-animated parcel time lapse + 38% counter
    ├── FindingsSection       three staggered finding cards with micro-charts
    ├── ExploreSection        ← depth gate — full interactivity appears here
    │   ├── ExploreMap
    │   │   ├── COGLayers     (SAR change, dNBR, NDVI — toggleable)
    │   │   ├── ParcelLayer   (colored by damage/rebuild stage)
    │   │   └── ParcelPopup   (VV sparkline, permit timeline, metrics)
    │   ├── TimelineSlider    (5 observation dates)
    │   ├── LayerPanel
    │   └── AskPanel          (RAG chat — appears last)
    └── MethodologySection    pipeline diagram + GitHub link
```

---

### Data Access

No backend. All fetches are same-origin via the Pages `_redirects` R2 proxy:

```typescript
const BASE = import.meta.env.VITE_DATA_BASE_URL
// dev:  http://localhost:4566/dm-dev-data
// prod: https://marshallfire.yourdomain.com/data

// Timeline and COG layer URLs — loaded once on mount
const timeline = await fetch(`${BASE}/results/timeline.json`)

// Parcel detail — loaded on click, cached by TanStack Query
const parcel = await fetch(`${BASE}/results/parcels/detail/${parcelId}.json`)

// RAG — same-origin Workers route
const answer = await fetch('/api/ask', {
  method: 'POST',
  body: JSON.stringify({ question })
})
```

**Bundle size target:** under 250kb gzipped. The noise texture SVG is 2kb. Leaflet is the largest dependency at ~45kb. No animation library, no CSS framework, no icon pack.

---

## 11. Environment Separation

| Concern | Dev | Prod |
|---|---|---|
| Object storage | LocalStack (S3-compatible, port 4566) | Cloudflare R2 |
| Site serving | Vite dev server (`npm run dev`) | Cloudflare Pages |
| Data access | `localhost:4566/dm-dev-data/` | `marshallfire.yourdomain.com/data/` |
| Pipeline trigger | `python pipeline/run.py` | `python pipeline/run.py --env prod` |
| Data volume | 2 scenes max | Full AOI, all 5 dates |
| ML inference | Optional (`--skip-ml`) | Full inference |
| dbt target | DuckDB local file | DuckDB local file (same) |
| Verify before deploy | `npm run dev` against local results | — |
| Deploy | — | `scripts/deploy.sh` |
| Cost | $0 | $0 |

**Single config — `config/settings.py`:**

```python
ENV = os.getenv('DEPLOY_ENV', 'dev')  # dev | prod

CONFIGS = {
    'dev': EnvironmentConfig(
        s3_endpoint_url='http://localhost:4566',
        data_bucket='dm-dev-data',
        data_base_url='http://localhost:4566/dm-dev-data',
    ),
    'prod': EnvironmentConfig(
        s3_endpoint_url='https://{CF_ACCOUNT_ID}.r2.cloudflarestorage.com',
        data_bucket='dm-prod-data',
        data_base_url='https://marshallfire.yourdomain.com/data',
    ),
}
```

`data_base_url` is what the frontend writes into `timeline.json` for COG layer URLs. In dev it points at LocalStack; in prod it points at the Pages-proxied R2 path — same origin, no CORS either way.

---

## 12. Deploy Workflow

Local verify then one push. No staging environment, no approval gates.

**The full release sequence:**

```bash
# 1. Run pipeline locally
python pipeline/run.py --env prod

# 2. Verify locally — inspect the real output data in the browser
npm run dev --prefix frontend
# open http://localhost:5173 — check map, parcels, time slider, charts

# 3. One command deploys everything
scripts/deploy.sh
```

**`scripts/deploy.sh`:**

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

Two operations, one script. R2 sync is incremental — only changed files upload. Wrangler deploy takes ~10 seconds.

**GitHub Actions — test only, no deploy:**

```yaml
# .github/workflows/test.yml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements-dev.txt
      - run: ruff check pipeline/ ml/ config/
      - run: pytest tests/ -v
      - run: cd frontend && npm ci && npm run build
```

CI validates that the code is clean and the frontend builds — it does not deploy. Deployment is a deliberate manual act after local verification. This is the right boundary for a project where data quality judgement matters.

---

## 13. Security

| Concern | Approach |
|---|---|
| Cloudflare credentials | `CF_API_TOKEN` + `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` in `.env` — gitignored |
| Accidental secret commit | pre-commit hooks: `detect-secrets` + `gitleaks` |
| Planetary Computer / EarthData | Personal free accounts — in `.env`, never committed |
| R2 bucket access | Private by default — Pages proxy is the only public path |
| HTTPS | Cloudflare handles TLS for both Pages and R2 proxy — nothing to configure |
| No AWS credentials anywhere | Not in `.env`, not in GitHub secrets, not in CI |

**`.env` (gitignored):**
```bash
CF_ACCOUNT_ID=...
CF_API_TOKEN=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
PC_SDK_SUBSCRIPTION_KEY=...      # Planetary Computer
EARTHDATA_USERNAME=...
EARTHDATA_PASSWORD=...
```

**`.env.example` (committed — shows structure, no values):**
```bash
CF_ACCOUNT_ID=
CF_API_TOKEN=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
PC_SDK_SUBSCRIPTION_KEY=
EARTHDATA_USERNAME=
EARTHDATA_PASSWORD=
```

---

## 14. Infrastructure Setup

No CDK. No AWS account. One-time Cloudflare dashboard setup — takes about 15 minutes total.

**Cloudflare R2 (data bucket):**
```
1. Cloudflare dashboard → R2 → Create bucket: dm-prod-data
2. Settings → Public access: off (Pages proxy is the access path)
3. Manage R2 API tokens → Create token (Object Read & Write on dm-prod-data)
   → save R2_ACCESS_KEY_ID + R2_SECRET_ACCESS_KEY to .env
```

**Cloudflare Pages (frontend):**
```
4. Pages → Create project: marshall-fire
5. Connect to GitHub repo
6. Build settings:
     Framework:        Vite
     Build command:    npm run build
     Build output:     dist
     Root directory:   frontend/
7. Deploy — Pages assigns marshallfire.pages.dev initially
```

**Custom subdomain (you already own the domain in CF):**
```
8. Pages project → Custom domains → Add: marshallfire.yourdomain.com
   Cloudflare auto-creates the CNAME — no manual DNS record needed
```

**`_redirects` — R2 same-origin proxy (no CORS):**
```
# frontend/public/_redirects
/data/*  https://dm-prod-data.CF_ACCOUNT_ID.r2.dev/:splat  200
```

That is the entire infrastructure. No YAML templates, no CDK synth, no account bootstrapping.

---

## 15. Cost Model

```
Cloudflare Pages      free tier: unlimited requests, 500 deploys/month
Cloudflare R2         free tier: 10GB storage, 1M write ops, 10M read ops/month
Cloudflare DNS        included with your existing domain — $0
Pipeline (local)      your laptop — $0
                      ───────────
Monthly total         $0
Annual total          $0
```

Marshall Fire dataset is under 2GB total (5 COG rasters ~300MB each + JSON ~50MB). Well inside the R2 free tier indefinitely. A new observation date once a year adds ~350MB — free tier accommodates roughly 25 years of annual updates before any cost.

The only scenario that incurs cost is exceptional traffic causing R2 read ops to exceed 10M/month — a good problem to have, and trivially addressable by enabling R2 caching at that point.

---

## 16. Full Technology Stack

```
Data Ingestion       pystac-client, planetary-computer, USGS TNM API
Orchestration        pipeline/run.py — single Click script, skip flags for partial rerun
Transformation       dbt-core + dbt-duckdb (local only)
Raster Processing    rasterio, pyrosar, pdal, laspy, numpy
ML — PyTorch         torchgeo, Siamese U-Net, two-stage fine-tuning
ML — TensorFlow      Keras two-head classifier (Dense damage + LSTM rebuild)
Ground Truth         Boulder County parcels + permits (parcel_id join), official loss list
Experiment Tracking  MLflow (local SQLite backend during training)
Storage              Cloudflare R2 (COG rasters + JSON, S3-compatible)
                     Parquet (pipeline intermediate, local only)
                     DuckDB file (local dbt target)
Frontend             React 18, TypeScript, Vite 5, Tailwind CSS
Map                  Leaflet, react-leaflet, georaster-layer-for-leaflet
State                Zustand, TanStack Query
Charts               recharts
Historical Basemap   ESRI Wayback WMTS
Serving              Cloudflare Pages (frontend) + R2 proxy via _redirects (data)
Deploy               wrangler CLI — one command
DNS                  Cloudflare (existing domain, subdomain CNAME auto-created)
Local Dev            LocalStack (R2/S3 emulation), MLflow (local), docker-compose
CI                   GitHub Actions — lint + test + build only, no deploy
```

---

## 17. Hands-On Notebook Curriculum

Notebooks live in `notebooks/` — separate from pipeline code and never imported by it. Their sole purpose is building intuition before that intuition gets encoded into production code. Each notebook has a single question it is trying to answer. When the question is answered, the notebook is done.

```
notebooks/
├── 01_duckdb_columnar_intuition.ipynb
├── 02_sar_first_look.ipynb
├── 03_sar_preprocessing.ipynb
├── 04_sar_change_detection.ipynb
├── 05_landsat_ir_fusion.ipynb
├── 06_parcel_zonal_stats.ipynb
├── 07_permit_ground_truth.ipynb
├── 08_siamese_pretrained_inference.ipynb
├── 09_siamese_finetuning.ipynb
├── 10_lstm_signal_exploration.ipynb
├── 11_lstm_training.ipynb
└── exploration.ipynb              # scratch space — never cleaned up
```

---

### Notebook 01 — DuckDB Columnar Intuition

**Question to answer:** What does columnar storage actually feel like compared to row storage?

**Setup:**
```python
import duckdb
import pandas as pd
import time

conn = duckdb.connect()

# Generate synthetic zonal stats — realistic MVP scale
conn.execute("""
    CREATE TABLE zonal_stats AS
    SELECT
        parcel_id,
        observation_date,
        (random() * -10 - 2)::FLOAT  as vv_change_db,
        (random() * -8  - 1)::FLOAT  as vh_change_db,
        (random() * 0.8)::FLOAT      as dnbr,
        (random() * 0.4 + 0.1)::FLOAT as swir_b7,
        (random() * 0.6 + 0.1)::FLOAT as ndvi,
        (random() * 800 + 200)::FLOAT  as parcel_area_m2,
        (random() > 0.77)::BOOL       as officially_destroyed
    FROM range(4800) t(parcel_id)
    CROSS JOIN ['2021-11','2022-01','2022-06','2023-06','2024-06'] d(observation_date)
""")

# Write to both formats
conn.execute("COPY zonal_stats TO 'zonal_stats.parquet' (FORMAT PARQUET)")
conn.execute("COPY zonal_stats TO 'zonal_stats.csv'     (FORMAT CSV, HEADER)")
```

**Exercise 1 — feel the scan difference:**
```python
# Query touching 2 of 8 columns
query = """
    SELECT observation_date, AVG(vv_change_db) as mean_vv
    FROM '{}' GROUP BY observation_date ORDER BY observation_date
"""

t0 = time.perf_counter()
conn.execute(query.format('zonal_stats.parquet')).df()
parquet_ms = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
conn.execute(query.format('zonal_stats.csv')).df()
csv_ms = (time.perf_counter() - t0) * 1000

print(f"Parquet: {parquet_ms:.1f}ms  CSV: {csv_ms:.1f}ms")
# At 4,800 rows the difference is small — try with 500,000 rows
# The ratio grows as table width grows and query touches fewer columns
```

**Exercise 2 — dbt profiles.yml pointing at DuckDB:**
```yaml
# dbt/profiles.yml
marshall_fire:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: "{{ env_var('DBT_DUCKDB_PATH', 'data/marshall.duckdb') }}"
      threads: 4
```

```bash
# Run dbt against the synthetic data
dbt debug   # confirms connection
dbt run     # executes staging models
dbt test    # runs schema tests
```

**What you should observe:** DuckDB reads `zonal_stats.parquet` from the filesystem with no configuration beyond the path. The `.duckdb` file is the mart output — inspect it directly with `duckdb data/marshall.duckdb` to confirm dbt wrote the tables. Everything is a file you can open, inspect, and delete.

---

### Notebook 02 — SAR First Look

**Question to answer:** What do raw Sentinel-1 GRD values look like over the Marshall Fire AOI before any processing?

**Data:** Download one pre-fire (Nov 2021) and one post-fire (Jan 2022) Sentinel-1 GRD scene via Planetary Computer. Start with a single small AOI chip — no need to process the full scene.

```python
import pystac_client
import planetary_computer
import rasterio
import numpy as np
import matplotlib.pyplot as plt
from rasterio.windows import from_bounds

catalog = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=planetary_computer.sign_inplace,
)

AOI = [-105.16, 39.93, -105.07, 40.01]  # Marshall Fire AOI

# Fetch pre-fire scene
pre_items = catalog.search(
    collections=["sentinel-1-grd"],
    bbox=AOI,
    datetime="2021-11-01/2021-11-30",
).item_collection()

# Fetch post-fire scene
post_items = catalog.search(
    collections=["sentinel-1-grd"],
    bbox=AOI,
    datetime="2022-01-01/2022-01-31",
).item_collection()

print(f"Pre-fire scenes found:  {len(pre_items)}")
print(f"Post-fire scenes found: {len(post_items)}")

# Inspect the raw asset URLs and metadata
item = pre_items[0]
print(f"Scene date:      {item.datetime}")
print(f"Pass direction:  {item.properties.get('sat:orbit_state')}")
print(f"Available bands: {list(item.assets.keys())}")
```

**Exercise — open raw DN values and understand what they are:**
```python
# Read raw VV band — Digital Numbers, not yet backscatter
with rasterio.open(item.assets['VV'].href) as src:
    # Read just the AOI chip
    window = from_bounds(*AOI, transform=src.transform)
    vv_raw = src.read(1, window=window).astype(float)
    profile = src.profile

print(f"VV DN range:  {vv_raw.min():.0f} — {vv_raw.max():.0f}")
print(f"VV DN mean:   {vv_raw.mean():.0f}")
print(f"Pixel size:   {src.res[0]:.1f}m × {src.res[1]:.1f}m")
print(f"Scene CRS:    {src.crs}")

# Visualize raw DN — will look noisy (speckle)
plt.figure(figsize=(10, 8))
plt.imshow(vv_raw, cmap='gray',
           vmin=np.percentile(vv_raw, 2),
           vmax=np.percentile(vv_raw, 98))
plt.colorbar(label='DN value')
plt.title('Sentinel-1 VV — Raw DN (pre-fire Nov 2021)')
plt.show()
```

**What you should observe:** The raw image looks grainy — this is speckle, the coherent noise inherent to SAR. Bright pixels are strong scatterers (buildings, metal). Dark pixels are weak scatterers (water, smooth soil). You cannot yet read structure from this image — that requires the next notebook's preprocessing. This is the starting point intuition: raw SAR looks nothing like an optical image.

---

### Notebook 03 — SAR Preprocessing

**Question to answer:** What does radiometric calibration do to the numbers, and why does terrain correction matter for the Marshall Fire AOI?

```python
# Step 1: DN to sigma0 (linear)
def dn_to_sigma0_linear(dn: np.ndarray) -> np.ndarray:
    """
    Convert Sentinel-1 GRD DN to sigma0 linear scale.
    Sentinel-1 GRD data uses a fixed calibration constant.
    """
    return dn.astype(float) ** 2 / (10 ** (83.0 / 10))

# Step 2: linear to dB
def linear_to_db(sigma0_linear: np.ndarray,
                 nodata_threshold: float = 1e-10) -> np.ndarray:
    sigma0_linear = np.where(
        sigma0_linear > nodata_threshold,
        sigma0_linear,
        np.nan
    )
    return 10 * np.log10(sigma0_linear)

vv_sigma0_linear = dn_to_sigma0_linear(vv_raw)
vv_sigma0_db     = linear_to_db(vv_sigma0_linear)

print(f"Sigma0 dB range: {np.nanmin(vv_sigma0_db):.1f} — {np.nanmax(vv_sigma0_db):.1f} dB")
print(f"Sigma0 dB mean:  {np.nanmean(vv_sigma0_db):.1f} dB")
```

**Exercise — compare before/after calibration visually:**
```python
fig, axes = plt.subplots(1, 3, figsize=(18, 6))

axes[0].imshow(vv_raw, cmap='gray',
    vmin=np.percentile(vv_raw[vv_raw>0], 2),
    vmax=np.percentile(vv_raw[vv_raw>0], 98))
axes[0].set_title('Raw DN')

axes[1].imshow(vv_sigma0_linear, cmap='gray',
    vmin=np.percentile(vv_sigma0_linear[vv_sigma0_linear>0], 2),
    vmax=np.percentile(vv_sigma0_linear[vv_sigma0_linear>0], 98))
axes[1].set_title('Sigma0 Linear')

axes[2].imshow(vv_sigma0_db, cmap='gray', vmin=-20, vmax=0)
axes[2].set_title('Sigma0 dB — physically meaningful scale')
plt.show()
```

**Exercise — measure land cover backscatter classes manually:**
```python
# Draw small bounding boxes over known land cover types
# Use ESRI Wayback imagery as reference to identify areas

land_cover_samples = {
    'intact_urban':    (row1, col1, row2, col2),  # surviving neighborhood
    'burned_urban':    (row1, col1, row2, col2),  # destroyed block
    'grassland':       (row1, col1, row2, col2),  # open field
    'creek_corridor':  (row1, col1, row2, col2),  # Coal Creek area
}

print("Pre-fire backscatter by land cover class (dB):")
for name, (r1, c1, r2, c2) in land_cover_samples.items():
    sample = vv_pre_db[r1:r2, c1:c2]
    print(f"  {name:20s}: {np.nanmean(sample):6.1f} dB  "
          f"(std: {np.nanstd(sample):.1f})")
```

**What you should observe:** Intact urban backscatter should read approximately -5 to -8 dB. Grassland should read approximately -12 to -15 dB. The difference between urban and grassland in dB becomes your physical intuition for why the classification thresholds in Section 9a are where they are. If your numbers differ significantly from the plan's thresholds, note the deviation — it will inform threshold calibration later.

---

### Notebook 04 — SAR Change Detection

**Question to answer:** Can you see the fire damage in the change image, and does it align with the official loss list?

```python
# Load both pre and post calibrated VV
vv_pre_db  = load_calibrated_vv('2021-11')
vv_post_db = load_calibrated_vv('2022-01')

# Compute change image
vv_change  = vv_post_db - vv_pre_db   # negative = loss

# Load parcel boundaries and official loss list
parcels = gpd.read_file('data/raw/parcels/boulder_county_parcels.geojson')
parcels = parcels[parcels.within(aoi_polygon)]

losses  = pd.read_csv('data/raw/ground_truth/marshall_fire_losses.csv')
parcels = parcels.merge(losses[['parcel_id','officially_destroyed']],
                        on='parcel_id', how='left')
parcels['officially_destroyed'] = parcels['officially_destroyed'].fillna(False)
```

**Exercise 1 — visualize change image with parcel overlay:**
```python
fig, ax = plt.subplots(figsize=(12, 10))

# Change image — diverging colormap
im = ax.imshow(vv_change, cmap='RdBu',
               vmin=-8, vmax=8,
               extent=[aoi[0], aoi[2], aoi[1], aoi[3]])
plt.colorbar(im, ax=ax, label='VV Change (dB)')

# Overlay parcel boundaries colored by ground truth
destroyed = parcels[parcels['officially_destroyed']]
survived  = parcels[~parcels['officially_destroyed']]
destroyed.boundary.plot(ax=ax, color='red',   linewidth=0.8, label='Destroyed')
survived.boundary.plot(ax=ax,  color='green', linewidth=0.4, label='Survived')
ax.legend()
ax.set_title('SAR VV Change — Jan 2022 vs Nov 2021\nRed parcels = officially destroyed')
plt.show()
```

**Exercise 2 — compute per-parcel zonal stats and plot distribution:**
```python
from rasterstats import zonal_stats

stats = zonal_stats(
    parcels,
    vv_change,
    affine=transform,
    stats=['mean', 'std', 'count'],
    nodata=np.nan
)

parcels['vv_change_mean'] = [s['mean'] for s in stats]
parcels['vv_change_std']  = [s['std']  for s in stats]
parcels['sar_pixel_count']= [s['count']for s in stats]

# Distribution plot — do destroyed parcels separate from survived?
fig, ax = plt.subplots(figsize=(10, 6))
parcels[parcels['officially_destroyed']]['vv_change_mean'].hist(
    bins=40, ax=ax, alpha=0.6, color='red',   label='Destroyed (n=1084)')
parcels[~parcels['officially_destroyed']]['vv_change_mean'].hist(
    bins=40, ax=ax, alpha=0.6, color='blue',  label='Survived')
ax.axvline(-2.0, color='orange', linestyle='--', label='Threshold -2.0 dB')
ax.axvline(-4.0, color='red',    linestyle='--', label='Threshold -4.0 dB')
ax.set_xlabel('Mean VV Change (dB)')
ax.set_ylabel('Parcel count')
ax.legend()
ax.set_title('SAR change distribution — does it separate by damage class?')
plt.show()
```

**What you should observe:** Two overlapping but distinct distributions. The destroyed parcels should cluster more negative than survived parcels but with meaningful overlap — this overlap is exactly why SAR alone is insufficient and IR fusion is necessary. The -2.0 dB and -4.0 dB thresholds from Section 9a should sit at or near the distribution intersection. If your data shows the thresholds are poorly placed, recalibrate them now — before touching the ML model.

---

### Notebook 05 — Landsat IR Fusion

**Question to answer:** Where do SAR and SWIR agree, and where do they disagree? Are the disagreements physically interpretable?

```python
# Load all four signals for Jan 2022
vv_change  = load_sar_change('2022-01')         # from notebook 04
swir_b7    = load_landsat_band('2022-01', 'B7') # surface reflectance
tir_b10    = load_landsat_band('2022-01', 'B10')# brightness temperature
dnbr       = compute_dnbr('2021-11', '2022-01') # from Landsat B5, B7

# Compute TIR anomaly vs multi-year January baseline
tir_baseline = compute_tir_baseline(['2019-01', '2020-01', '2021-01'])
tir_anomaly  = tir_b10 - tir_baseline

# Compute parcel-level stats for all four signals
for signal_name, signal_raster in [
    ('vv_change_db', vv_change),
    ('swir_b7',      swir_b7),
    ('tir_anomaly',  tir_anomaly),
    ('dnbr',         dnbr),
]:
    stats = zonal_stats(parcels, signal_raster, ...)
    parcels[signal_name] = [s['mean'] for s in stats]
```

**Exercise 1 — four-signal scatter matrix:**
```python
import seaborn as sns

signals = ['vv_change_db', 'swir_b7', 'tir_anomaly', 'dnbr']
colors  = parcels['officially_destroyed'].map({True: 'red', False: 'steelblue'})

pd.plotting.scatter_matrix(
    parcels[signals],
    c=colors,
    alpha=0.4,
    figsize=(14, 14),
    diagonal='hist',
)
plt.suptitle('Signal correlation matrix — red=destroyed, blue=survived')
plt.show()
```

**Exercise 2 — find the ambiguous parcels manually:**
```python
# These are the cases that matter most — where SAR misleads

# SAR says destroyed, optical says maybe not
sar_yes_optical_no = parcels[
    (parcels['vv_change_db'] <= -4.0) &   # SAR: strong loss
    (parcels['swir_b7'] < 0.15) &          # SWIR: no char
    (parcels['dnbr'] < 0.10)               # dNBR: unburned
]
print(f"SAR false alarm candidates: {len(sar_yes_optical_no)}")
print(sar_yes_optical_no[['parcel_id','address','officially_destroyed',
                           'vv_change_db','swir_b7','dnbr']].head(10))

# SAR says survived, optical says burned
sar_no_optical_yes = parcels[
    (parcels['vv_change_db'] > -2.0) &    # SAR: no change
    (parcels['swir_b7'] >= 0.30) &         # SWIR: heavy char
    (parcels['dnbr'] >= 0.44)              # dNBR: high severity
]
print(f"\nSAR miss candidates: {len(sar_no_optical_yes)}")
print(sar_no_optical_yes[['parcel_id','address','officially_destroyed',
                           'vv_change_db','swir_b7','dnbr']].head(10))
```

**Exercise 3 — apply the decision tree manually and measure accuracy:**
```python
def apply_decision_tree(row) -> str:
    if row['swir_b7'] < 0.15 and row['dnbr'] < 0.10:
        return 'survived_no_fire'
    if row['vv_change_db'] > -2.0:
        return 'survived_fire_exposed'
    if row['vv_change_db'] <= -4.0:
        return 'total_loss'
    if row['tir_anomaly'] >= 1.5 and row['swir_b7'] >= 0.25:
        return 'total_loss'
    return 'partial_damage'

parcels['predicted_class'] = parcels.apply(apply_decision_tree, axis=1)
parcels['predicted_loss']  = parcels['predicted_class'] == 'total_loss'

from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

precision = precision_score(parcels['officially_destroyed'],
                            parcels['predicted_loss'])
recall    = recall_score(parcels['officially_destroyed'],
                         parcels['predicted_loss'])
f1        = f1_score(parcels['officially_destroyed'],
                     parcels['predicted_loss'])

print(f"Decision tree — no ML, just thresholds:")
print(f"  Precision: {precision:.3f}")
print(f"  Recall:    {recall:.3f}")
print(f"  F1:        {f1:.3f}")

print("\nConfusion matrix:")
print(confusion_matrix(parcels['officially_destroyed'],
                       parcels['predicted_loss']))
```

**What you should observe:** The decision tree alone — no ML at all — should achieve F1 somewhere in the 0.70–0.80 range. This is a critical baseline. The ML model's value is in pushing above this threshold and handling edge cases. If the decision tree already achieves 0.78 F1, the ML model needs to justify its complexity by reaching at least 0.82. If the decision tree achieves only 0.60, it means your thresholds need recalibration before training — the ML model cannot compensate for poorly designed features.

---

### Notebook 06 — Parcel Zonal Stats Pipeline

**Question to answer:** What does the full zonal stats computation look like at MVP scale, and does the output match what the dbt models expect?

```python
# This notebook bridges the raster world and the tabular world
# It is essentially a dry run of pipeline/process/zonal_stats.py

import rasterio
import geopandas as gpd
from rasterstats import zonal_stats
import duckdb

# All five observation dates × all four rasters
DATES   = ['2021-11', '2022-01', '2022-06', '2023-06', '2024-06']
RASTERS = ['sar_vv', 'sar_vh', 'swir_b7', 'tir_anomaly', 'dnbr', 'ndvi']

rows = []
for date in DATES:
    for raster_name in RASTERS:
        raster_path = f'data/processed/{raster_name}_{date}.cog.tif'
        if not os.path.exists(raster_path):
            continue

        with rasterio.open(raster_path) as src:
            arr       = src.read(1)
            transform = src.transform

        stats = zonal_stats(
            parcels, arr,
            affine=transform,
            stats=['mean', 'std', 'count', 'min', 'max'],
            nodata=np.nan,
        )

        for parcel, stat in zip(parcels.itertuples(), stats):
            rows.append({
                'parcel_id':       parcel.parcel_id,
                'observation_date': date,
                'raster':          raster_name,
                'mean':            stat['mean'],
                'std':             stat['std'],
                'pixel_count':     stat['count'],
            })

df = pd.DataFrame(rows)

# Write to Parquet — this is exactly what the pipeline produces
df.to_parquet('data/tabular/zonal_stats_long.parquet', index=False)
print(f"Wrote {len(df):,} rows × {len(df.columns)} columns")
print(f"File size: {os.path.getsize('data/tabular/zonal_stats_long.parquet') / 1024:.0f} KB")

# Verify dbt can read it
conn = duckdb.connect()
result = conn.execute("""
    SELECT raster, observation_date, COUNT(*) as n_parcels,
           AVG(mean) as grand_mean
    FROM 'data/tabular/zonal_stats_long.parquet'
    GROUP BY raster, observation_date
    ORDER BY raster, observation_date
""").df()
print(result.to_string())
```

**What you should observe:** The long-format Parquet file is compact — at 4,800 parcels × 5 dates × 6 rasters, approximately 144,000 rows, likely under 2MB on disk. DuckDB reads and aggregates it in milliseconds. This gives you the physical intuition for why Parquet is the right pipeline intermediate format and why you do not need a database server.

---

### Notebook 07 — Permit Ground Truth

**Question to answer:** What is the actual quality of the permit-derived training labels, and how many parcels have high-confidence labels?

```python
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

# Load datasets
parcels = gpd.read_file('data/raw/parcels/boulder_county_parcels.geojson')
permits = pd.read_csv('data/raw/permits/boulder_county_permits.csv')
losses  = pd.read_csv('data/raw/ground_truth/marshall_fire_losses.csv')

# Verify the join works — no geocoding
print(f"Parcels:               {len(parcels):,}")
print(f"Permits (post-fire):   {len(permits):,}")
print(f"Officially destroyed:  {losses['parcel_id'].nunique():,}")

# Check parcel_id format consistency
print(f"\nParcel ID sample (parcels): {parcels['parcel_id'].iloc[0]}")
print(f"Parcel ID sample (permits): {permits['parcel_id'].iloc[0]}")
# If formats differ — zero-pad, strip dashes — fix here before proceeding

# Join
destroyed = parcels.merge(losses, on='parcel_id', how='inner')
with_permits = destroyed.merge(
    permits[REBUILD_PERMIT_TYPES], on='parcel_id', how='left'
)
```

**Exercise — label quality audit:**
```python
# Build permit timeline per parcel
timeline = build_permit_timeline(with_permits)

# Classify label confidence
def label_confidence(row):
    if pd.notna(row['coo_date']):     return 'high'
    if pd.notna(row['framing_date']): return 'high'
    if pd.notna(row['foundation_date']): return 'medium'
    if pd.notna(row['demo_date']):    return 'medium'
    return 'low'

timeline['label_confidence'] = timeline.apply(label_confidence, axis=1)

# Confidence distribution
conf_counts = timeline['label_confidence'].value_counts()
print("Label confidence distribution:")
print(conf_counts)
print(f"\nHigh + medium confidence: "
      f"{(conf_counts.get('high',0) + conf_counts.get('medium',0)) / len(timeline):.1%}")

# Visualize on map — are low confidence parcels spatially clustered?
fig, ax = plt.subplots(figsize=(12, 10))
colors = {'high': 'green', 'medium': 'orange', 'low': 'red'}
for conf, group in timeline.groupby('label_confidence'):
    gpd.GeoDataFrame(group, geometry='geometry').plot(
        ax=ax, color=colors[conf], alpha=0.7, label=conf
    )
ax.legend()
ax.set_title('Permit label confidence by parcel\n'
             'Spatial clustering of low-confidence = data gap, not random noise')
plt.show()
```

**What you should observe:** High + medium confidence labels should cover approximately 85–90% of destroyed parcels if Boulder County's open data is current. Low-confidence parcels often cluster spatially — a block that rebuilt slowly, or a section where permits were filed under a developer rather than individual owners. Spatial clustering of low-confidence labels is important to note — it means the LSTM may learn poorly for those geographic areas specifically, not randomly.

---

### Notebook 08 — Siamese U-Net: Pretrained Inference Before Fine-Tuning

**Question to answer:** What does the BigEarthNet-pretrained model predict on Marshall Fire SAR patches before any fine-tuning? Where does it fail and why?

```python
import torch
import numpy as np
import matplotlib.pyplot as plt
from torchgeo.models import ResNet50_Weights

# Load pretrained model — no fine-tuning
model = SiameseUNet(
    backbone='resnet50',
    weights=ResNet50_Weights.SENTINEL2_ALL_MOCO,
    in_channels=2,      # VV + VH
    num_classes=1,
)
model.eval()

# Extract patches for 20 known-destroyed and 20 known-survived parcels
destroyed_ids = losses['parcel_id'].sample(20, random_state=42).tolist()
survived_ids  = parcels[~parcels['parcel_id'].isin(
                    losses['parcel_id'])]['parcel_id'].sample(20, random_state=42).tolist()

def extract_patch(parcel_id, date, patch_size=64):
    centroid = parcels[parcels['parcel_id']==parcel_id].geometry.centroid.iloc[0]
    # Extract 64×64 patch centered on parcel centroid
    # Returns tensor of shape (2, 64, 64) — VV + VH channels
    ...

results = []
for parcel_id in destroyed_ids + survived_ids:
    pre  = extract_patch(parcel_id, '2021-11')
    post = extract_patch(parcel_id, '2022-01')

    with torch.no_grad():
        pred = torch.sigmoid(model(
            pre.unsqueeze(0),
            post.unsqueeze(0)
        )).squeeze().numpy()

    results.append({
        'parcel_id':    parcel_id,
        'destroyed':    parcel_id in destroyed_ids,
        'mean_change_prob': pred.mean(),
        'max_change_prob':  pred.max(),
    })

df_results = pd.DataFrame(results)
```

**Exercise — visualize prediction vs ground truth:**
```python
fig, axes = plt.subplots(4, 6, figsize=(18, 12))
# Show pre-patch, post-patch, change-prob map for 4 random parcels
# Two destroyed, two survived
# Annotate with ground truth and prediction score

for i, row in df_results.sample(4).iterrows():
    pre   = extract_patch(row['parcel_id'], '2021-11')
    post  = extract_patch(row['parcel_id'], '2022-01')
    pred  = run_inference(model, pre, post)

    col = i * 3
    axes[0][col].imshow(pre[0],   cmap='gray')
    axes[0][col].set_title(f"Pre VV\n{row['parcel_id'][:8]}")
    axes[0][col+1].imshow(post[0], cmap='gray')
    axes[0][col+1].set_title('Post VV')
    axes[0][col+2].imshow(pred,    cmap='hot', vmin=0, vmax=1)
    truth = 'DESTROYED' if row['destroyed'] else 'survived'
    axes[0][col+2].set_title(f'P(change)={row["mean_change_prob"]:.2f}\n{truth}')

plt.suptitle('Pretrained inference — before fine-tuning', fontsize=14)
plt.tight_layout()
plt.show()

# Score on all 40 samples
from sklearn.metrics import roc_auc_score
auc = roc_auc_score(df_results['destroyed'],
                    df_results['mean_change_prob'])
print(f"Pretrained AUC (40 samples): {auc:.3f}")
print("Expected: ~0.55–0.70 — better than chance but not calibrated")
print("This is what fine-tuning needs to improve")
```

**What you should observe:** The pretrained model will be better than random (AUC > 0.5) because SAR spatial patterns are partially universal. But it will misfire on Marshall Fire's specific signatures — Colorado shortgrass prairie looks different from BigEarthNet's European land cover, and the model has no concept of wildfire-specific damage geometry. Document the specific failure patterns. These become the justification for fine-tuning and the story you tell in interviews.

---

### Notebook 09 — Siamese U-Net Fine-Tuning

**Question to answer:** How much does fine-tuning improve the pretrained model, and at what stage do the training curves plateau?

```python
# Build the full training dataset
# ~4,800 patch pairs with binary labels from official loss list

from torch.utils.data import Dataset, DataLoader
import torch.nn as nn

class MarshallFireDataset(Dataset):
    def __init__(self, parcel_ids, labels, augment=False):
        self.parcel_ids = parcel_ids
        self.labels     = labels
        self.augment    = augment
        self.transform  = sar_augmentation if augment else None

    def __len__(self):
        return len(self.parcel_ids)

    def __getitem__(self, idx):
        pid   = self.parcel_ids[idx]
        pre   = extract_patch(pid, '2021-11')
        post  = extract_patch(pid, '2022-01')
        label = torch.tensor(self.labels[idx], dtype=torch.float32)

        if self.transform:
            stacked = torch.cat([pre, post], dim=0)  # (4, 64, 64)
            stacked = self.transform(stacked)
            pre, post = stacked[:2], stacked[2:]

        return pre, post, label

# Spatial block split — see Section 9a
train_ids, train_labels = get_spatial_block_split('train')
val_ids,   val_labels   = get_spatial_block_split('val')

train_ds = MarshallFireDataset(train_ids, train_labels, augment=True)
val_ds   = MarshallFireDataset(val_ids,   val_labels,   augment=False)
train_dl = DataLoader(train_ds, batch_size=16, shuffle=True,  num_workers=4)
val_dl   = DataLoader(val_ds,   batch_size=16, shuffle=False, num_workers=4)
```

**Stage 1 — freeze backbone, train head:**
```python
# Freeze encoder
for param in model.encoder.parameters():
    param.requires_grad = False

optimizer = torch.optim.Adam(
    filter(lambda p: p.requires_grad, model.parameters()), lr=1e-3
)
criterion = CombinedLoss(bce_weight=0.5, dice_weight=0.5, pos_weight=3.4)

train_history = {'loss': [], 'f1': [], 'val_loss': [], 'val_f1': []}

for epoch in range(10):
    train_loss, train_f1 = run_epoch(model, train_dl, optimizer, criterion)
    val_loss,   val_f1   = evaluate(model, val_dl, criterion)

    train_history['loss'].append(train_loss)
    train_history['f1'].append(train_f1)
    train_history['val_loss'].append(val_loss)
    train_history['val_f1'].append(val_f1)

    print(f"Epoch {epoch+1:2d} | "
          f"train loss: {train_loss:.4f} f1: {train_f1:.3f} | "
          f"val loss: {val_loss:.4f} f1: {val_f1:.3f}")
```

**Stage 2 — unfreeze top encoder blocks:**
```python
for param in model.encoder.layer3.parameters():
    param.requires_grad = True
for param in model.encoder.layer4.parameters():
    param.requires_grad = True

optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=20)

best_val_f1 = 0
patience_counter = 0

for epoch in range(20):
    train_loss, train_f1 = run_epoch(model, train_dl, optimizer, criterion)
    val_loss,   val_f1   = evaluate(model, val_dl, criterion)
    scheduler.step()

    if val_f1 > best_val_f1:
        best_val_f1 = val_f1
        torch.save(model.state_dict(), 'ml/models/siamese_unet_best.pt')
        patience_counter = 0
    else:
        patience_counter += 1
        if patience_counter >= 5:
            print(f"Early stopping at epoch {epoch+1}")
            break

# Plot training curves
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
axes[0].plot(train_history['loss'],     label='Train loss')
axes[0].plot(train_history['val_loss'], label='Val loss')
axes[0].axvline(10, color='gray', linestyle='--', label='Unfreeze')
axes[0].legend(); axes[0].set_title('Loss curves')

axes[1].plot(train_history['f1'],     label='Train F1')
axes[1].plot(train_history['val_f1'], label='Val F1')
axes[1].axvline(10, color='gray', linestyle='--', label='Unfreeze')
axes[1].legend(); axes[1].set_title('F1 curves')
plt.show()
```

**Log to MLflow:**
```python
import mlflow

with mlflow.start_run(run_name="siamese_unet_stage2"):
    mlflow.log_params({
        "backbone": "resnet50",
        "patch_size": 64,
        "stage1_epochs": 10,
        "stage2_epochs": epoch + 1,
        "pos_weight": 3.4,
    })
    mlflow.log_metrics({
        "best_val_f1": best_val_f1,
        "final_train_f1": train_history['f1'][-1],
    })
    mlflow.pytorch.log_model(model, "siamese_unet")
```

**What you should observe:** Stage 1 training (frozen backbone) should show rapid F1 improvement in the first 3–4 epochs then plateau. Stage 2 unfreezing should produce a second improvement wave. If Stage 2 shows no improvement over Stage 1, the pretrained features are already sufficient and no backbone fine-tuning is needed. Record this observation — it is a finding, not a failure.

---

### Notebook 10 — LSTM Signal Exploration

**Question to answer:** Can you visually read rebuild stage from the VV time series before training the model?

```python
# Load VV time series for all destroyed parcels
# Normalized relative to parcel's own pre-fire baseline

vv_series = {}
for parcel_id in losses['parcel_id']:
    series = []
    for date in DATES:
        vv = get_vv_for_parcel(parcel_id, date)
        series.append(vv)
    baseline        = np.median(series[:1])    # Nov 2021
    vv_series[parcel_id] = np.array(series) - baseline

# Load permit timeline for ground truth
timeline = load_permit_timeline()
```

**Exercise — plot representative examples of each rebuild stage:**
```python
fig, axes = plt.subplots(2, 4, figsize=(20, 10))

stage_examples = {
    'rebuild_complete':      find_parcel_with_stage('rebuild_complete', timeline),
    'structure_substantial': find_parcel_with_stage('structure_substantial', timeline),
    'foundation_framing':    find_parcel_with_stage('foundation_framing', timeline),
    'cleared_lot':           find_parcel_with_stage('cleared_lot', timeline),
}

for col, (stage, parcel_id) in enumerate(stage_examples.items()):
    series = vv_series[parcel_id]
    axes[0][col].plot(DATES, series, 'o-', color='steelblue', linewidth=2)
    axes[0][col].axhline(0, color='gray', linestyle='--', label='Baseline')
    axes[0][col].fill_between(DATES, series, 0,
                               alpha=0.3,
                               color='red' if min(series) < -2 else 'green')
    axes[0][col].set_title(f'{stage}\n{parcel_id[:8]}')
    axes[0][col].set_ylabel('VV normalized (dB)')
    axes[0][col].set_ylim(-12, 4)

# Row 2: 4 random unknown parcels — can you guess the stage?
for col, parcel_id in enumerate(losses['parcel_id'].sample(4)):
    series = vv_series[parcel_id]
    axes[1][col].plot(DATES, series, 'o-', color='orange', linewidth=2)
    axes[1][col].axhline(0, color='gray', linestyle='--')
    axes[1][col].set_title(f'Unknown — what stage?\n{parcel_id[:8]}')
    axes[1][col].set_ylim(-12, 4)

plt.suptitle('VV backscatter time series by rebuild stage\n'
             'Bottom row: guess the stage before checking permit data',
             fontsize=12)
plt.tight_layout()
plt.show()
```

**Exercise — cluster the time series unsupervised before supervised training:**
```python
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

# Stack all series into matrix — (n_parcels, 5 timesteps)
X = np.stack([vv_series[pid] for pid in losses['parcel_id']])

# PCA to 2D for visualization
pca  = PCA(n_components=2)
X_2d = pca.fit_transform(StandardScaler().fit_transform(X))

# K-means with 4 clusters — do they correspond to rebuild stages?
kmeans  = KMeans(n_clusters=4, random_state=42)
clusters = kmeans.fit_predict(X)

plt.figure(figsize=(10, 8))
scatter = plt.scatter(X_2d[:,0], X_2d[:,1], c=clusters,
                      cmap='Set1', alpha=0.6)
plt.colorbar(scatter, label='Cluster')
plt.xlabel('PC1')
plt.ylabel('PC2')
plt.title('Unsupervised clustering of VV time series\n'
          'Do 4 clusters align with 4 rebuild stages?')
plt.show()

# Compare cluster assignments to permit-derived labels
for cluster_id in range(4):
    mask = clusters == cluster_id
    stage_dist = timeline.loc[losses['parcel_id'][mask], 'final_stage'].value_counts()
    print(f"\nCluster {cluster_id} (n={mask.sum()}):")
    print(stage_dist.head(3))
```

**What you should observe:** The PCA clusters should partially align with rebuild stages — complete rebuilds grouping separately from cleared lots. Imperfect alignment is expected and informative — it shows which stages are spectrally similar from a SAR perspective (cleared lot vs foundation look similar) and which are distinct (rebuild complete is clearly separable). This tells you where the LSTM will need the most labeled examples.

---

### Notebook 11 — LSTM Training

**Question to answer:** Does the LSTM learn meaningful rebuild stage classification, and how do confidence-weighted labels affect training?

```python
import tensorflow as tf
import mlflow.tensorflow

# Prepare sequences
# Input: (n_parcels, 5 timesteps, 3 features)
# Features per timestep: vv_norm, vv_delta_from_prev, acquisition_doy

def prepare_sequences(parcel_ids, labels, confidence_weights):
    X_seq     = []
    X_parcel  = []
    y         = []
    weights   = []

    for pid, label, weight in zip(parcel_ids, labels, confidence_weights):
        series = vv_series[pid]   # (5,) normalized VV

        # Build 3-feature sequence
        vv_delta = np.diff(series, prepend=series[0])
        doy      = np.array([day_of_year(d) / 365.0 for d in DATES])

        seq = np.stack([series, vv_delta, doy], axis=1)  # (5, 3)
        X_seq.append(seq)

        # Parcel context features
        row = parcels[parcels['parcel_id']==pid].iloc[0]
        X_parcel.append([
            row['parcel_area_m2'] / 1000.0,   # normalized
            row['sar_pixel_count'] / 10.0,
            row['land_use_encoded'] / 5.0,
        ])

        y.append(label)
        weights.append(weight)

    return (np.array(X_seq), np.array(X_parcel),
            np.array(y), np.array(weights))

X_seq, X_parcel, y_train, w_train = prepare_sequences(
    train_ids, train_labels, train_weights
)
```

**Training run — log everything to MLflow:**
```python
with mlflow.start_run(run_name="lstm_rebuild_v1"):

    mlflow.log_params({
        "lstm_units":          32,
        "lstm_dropout":        0.2,
        "parcel_branch_units": 16,
        "merged_units":        32,
        "merged_dropout":      0.3,
        "epochs":              30,
        "batch_size":          64,
        "optimizer":           "adam",
        "lr":                  1e-3,
        "use_sample_weights":  True,
    })

    history = model.fit(
        [X_seq_train, X_parcel_train],
        y_train,
        sample_weight=w_train,
        validation_data=(
            [X_seq_val, X_parcel_val],
            y_val
        ),
        epochs=30,
        batch_size=64,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                patience=5,
                restore_best_weights=True,
                monitor='val_accuracy'
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                patience=3, factor=0.5
            ),
        ]
    )

    # Evaluate
    val_preds = model.predict([X_seq_val, X_parcel_val]).argmax(axis=1)

    from sklearn.metrics import classification_report, confusion_matrix
    report = classification_report(
        y_val, val_preds,
        target_names=['cleared_lot','foundation_framing',
                      'structure_substantial','rebuild_complete',
                      'not_applicable']
    )
    print(report)
    mlflow.log_text(report, "classification_report.txt")

    # Confusion matrix
    cm = confusion_matrix(y_val, val_preds)
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', ax=ax,
                xticklabels=['cleared','framing','substantial','complete','N/A'],
                yticklabels=['cleared','framing','substantial','complete','N/A'])
    ax.set_title('LSTM Rebuild Stage — Confusion Matrix')
    mlflow.log_figure(fig, "confusion_matrix.png")

    # Compare weighted vs unweighted training
    mlflow.log_metrics({
        "val_accuracy":            history.history['val_accuracy'][-1],
        "val_accuracy_best_epoch": max(history.history['val_accuracy']),
    })

    mlflow.tensorflow.log_model(model, "lstm_rebuild")
```

**Exercise — compare weighted vs unweighted training:**

Run the notebook twice — once with `sample_weight=w_train` and once without. Compare the confusion matrices. The expected finding is that weighted training improves performance on stages where permit data is sparse (foundation_framing typically), because the model is penalized less for uncertain labels and focuses more on high-confidence examples. If weighted training shows no improvement, your label confidence assignment may need recalibration.

---

### Notebook Organization Notes

**`exploration.ipynb`** — never cleaned up. A running scratch pad for unexpected findings: anomalous backscatter values, parcels that don't match expectations, visualizations that reveal something new. The most important notebook in the project. Findings documented here become the README's "Observations and Limitations" section and interview talking points.

**Running order matters:** Each notebook builds on the previous. Do not jump to notebook 09 without having done 02 through 05 first. The SAR intuition from 02–04 is what makes the training curves in 09 interpretable. The label quality audit in 07 is what makes the confusion matrix in 11 meaningful.

**Keep notebooks out of the pipeline:** Nothing in `pipeline/` imports from `notebooks/`. They are exploration tools, not production code. Findings from notebooks get distilled into `pipeline/process/` and `ml/inference/` — never the reverse.

---

## 18. Build Roadmap

### Before Coding — Notebook Exploration (Weeks 1–5)
Work through notebooks 01–11 in order before writing any pipeline code. See Section 17 for the full curriculum. The notebooks establish the physical intuition that makes the pipeline code meaningful rather than mechanical.

### Weekend 1 — Foundation
- Repo structure committed to GitHub (`marshall-fire/`)
- `config/settings.py` with dev/prod abstraction
- `docker-compose.yml`: LocalStack + MLflow only
- `.env` + `.env.example` structure in place
- Planetary Computer SDK authenticated, first Sentinel-1 scene downloaded in notebook 02
- `pipeline/run.py` stub with click entry point and skip flags
- Cloudflare: R2 bucket created, Pages project connected to GitHub repo, subdomain live

### Weekend 2 — SAR + Landsat Processing
- SAR: GRD → sigma0 → terrain correction → backscatter change (`pyrosar` / `rasterio`)
- Landsat: radiometric calibration → dNBR → NDVI → TIR anomaly
- COG conversion for all processed rasters
- `pipeline/acquire/sentinel1.py` and `pipeline/acquire/landsat.py` complete
- `pipeline/process/sar.py` and `pipeline/process/landsat.py` complete

### Weekend 3 — LiDAR + dbt + Parcels + Ground Truth
- LiDAR: LAZ → DEM / DSM / CHM via `pdal`
- Boulder County parcel GeoJSON + permits CSV joined via parcel_id
- Zonal stats written to `data/tabular/*.parquet`
- dbt project running on DuckDB: `stg_permits` → `int_permit_timeline` → `int_rebuild_labels` → mart
- `parcels/detail/{parcel_id}.json` written by `pipeline/output/parcel_json.py`

### Weekend 4 — ML Training (Notebooks) + Inference Pipeline
- Notebooks 08–11: pretrained inference → fine-tune Siamese U-Net → train LSTM
- Model weights saved to `ml/models/`, pushed to R2 `models/`
- `ml/inference/damage.py` and `ml/inference/rebuild.py` callable from pipeline
- `pipeline/run.py --skip-acquisition --skip-processing` runs dbt + ML + output end to end
- MLflow experiment runs recorded, best weights identified

### Weekend 5 — Frontend + Local Verify
- React + Vite scaffolded with `_redirects` pointing at R2
- Leaflet map + ESRI Wayback basemap switcher
- COG layers via georaster-layer-for-leaflet
- Timeline slider (Zustand) + parcel click → detail JSON → recharts popup
- `npm run dev` against local `data/results/` — full verification pass before any deploy
- Every layer, every parcel, every chart confirmed working

### Weekend 6 — First Deploy
- `scripts/deploy.sh` written and tested: R2 sync → wrangler pages deploy
- Full run: `python pipeline/run.py --env prod` → verify locally → `scripts/deploy.sh`
- Live at `marshallfire.yourdomain.com`
- GitHub Actions: ruff + pytest + `npm run build` on every push

### Post-MVP (v2 Considerations)
- SAR coherence (SLC mode) for improved structural collapse detection
- Additional disaster events with per-event model adaptation
- Automated annual re-run triggered by new Sentinel-1 acquisition
- DuckDB WASM in-browser parcel queries
- `.gitlab-ci.yml` mirror for portfolio breadth

---

## 19. CV Statement

> *"Built Marshall Fire Damage and Recovery Tracker — end-to-end satellite change detection for the 2021 Marshall Fire. Fuses Sentinel-1 SAR + Landsat SWIR/TIR at parcel level for damage assessment; SAR VV backscatter time series with LSTM for rebuild stage monitoring (optical sensors cannot discriminate construction materials — SAR corner reflector geometry provides unambiguous phase-by-phase signal). Ground truth pipeline via Boulder County parcel/permit join — no geocoding. PyTorch Siamese U-Net fine-tuned on Marshall Fire patches; TensorFlow two-head classifier with LSTM rebuild head. Transformation via dbt on DuckDB, experiment tracking via MLflow. Pre-computed COG rasters and parcel JSON served via Cloudflare Pages + R2 at $0/month — no backend, no AWS, no CORS."*

---

## 20. Design Principles

1. **No hardcoded values** — all config flows from `settings.py`, one variable switches dev/prod
2. **No shared credentials** — personal free API keys in `.env`; never committed
3. **No idle compute** — pipeline runs locally on demand; Cloudflare serves static files only
4. **No premature complexity** — Airflow, Step Functions, Aurora, DuckDB WASM all deferred until the problem actually requires them
5. **Environment parity** — LocalStack mirrors R2 exactly via S3-compatible API; switching to prod is one env var
6. **Verify before deploy** — `npm run dev` against local results before every `scripts/deploy.sh`
7. **Notebooks are not pipeline** — exploration code never imported by production code; intuition first, implementation second
8. **Accuracy before modeling** — decision tree baseline established in notebook 05 before any ML training; the model must beat it to justify its complexity
