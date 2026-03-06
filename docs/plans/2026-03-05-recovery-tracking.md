# 09_recovery_tracking.ipynb — Temporal Recovery Scoring

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Compute per-parcel recovery scores (0→1) at each post-fire observation date using NDVI recovery ratios and OpenCV visual similarity, producing a frontend-ready parquet that feeds into the existing pipeline output layer.

**Context:** Notebook 08 established damage classification (Destroyed/Damaged/Unaffected) with XGBoost macro-F1 ≈ 0.65. The ablation study showed parcel metadata is a spatial confound — only sensor-derived features are portable. This notebook builds the temporal dimension: tracking *how* parcels recover over the 2.5-year observation arc (Jan 2022 → Jun 2024).

**Architecture:** For each post-fire date, compute two recovery signals — NDVI recovery ratio (spectral vegetation regrowth) and SSIM vs pre-fire (visual structural recovery from 30cm ESRI Wayback). Combine into a composite recovery score. Output as parquet for dbt ingestion and parcel detail JSON enrichment.

**Naming:** `notebooks/09_recovery_tracking.ipynb`

---

## Task 1: Setup + Load Baselines

**Files:** Create `notebooks/09_recovery_tracking.ipynb`

**Step 1:** Markdown intro cell explaining recovery tracking approach.

**Step 2:** Imports (geopandas, rasterio, rasterstats, planetary_computer, pystac_client, cv2, PIL, skimage, matplotlib). Reuse constants: AOI_BBOX, DATA_RAW, DATA_PROC, DATA_RESULTS.

**Step 3:** Load damage predictions from notebook 08:
```python
pred_df = pd.read_parquet(DATA_RESULTS / "damage_classifier_predictions.parquet")
```

**Step 4:** Load ground truth GeoJSON (deduplicated by ParcelNo, same as notebook 08). Merge damage predictions onto geometry.

**Step 5:** Define observation timeline:
```python
OBSERVATION_DATES = ["2022-01", "2022-06", "2023-06", "2024-06"]
# Months post-fire for display
MONTHS_POST = {"2022-01": 1, "2022-06": 6, "2023-06": 18, "2024-06": 30}
```

**Expected:** ~1,793 parcels with damage_class + geometry.

---

## Task 2: NDVI Recovery Ratio (All Dates)

**Step 1:** Reuse `search_landsat`, `read_landsat_bands`, `safe_ratio` from notebook 08.

**Step 2:** Load pre-fire NDVI (Oct/Nov 2021 — same scene as notebook 08).

**Step 3:** For each post-fire date, search Landsat, read NIR+Red, compute NDVI, then compute recovery ratio per parcel:
```
ndvi_recovery = (NDVI_t - NDVI_post) / (NDVI_pre - NDVI_post)
```
Where:
- `NDVI_pre` = pre-fire (Nov 2021)
- `NDVI_post` = immediate post-fire (Jan 2022)
- `NDVI_t` = current observation date

Clip to [0, 1]. Values >1 mean vegetation exceeded pre-fire baseline.

**Step 4:** Zonal stats per parcel in EPSG:4326 for each date.

**Step 5:** Build DataFrame: `ParcelNo × date → ndvi_recovery_mean`.

**Search dates for Landsat:**
- Pre: `2021-10-01/2021-11-30` (reuse same scene)
- Post: `2022-01-01/2022-02-28`
- 2022-06: `2022-06-01/2022-07-31`
- 2023-06: `2023-06-01/2023-07-31`
- 2024-06: `2024-06-01/2024-07-31`

**Expected:** NDVI recovery near 0 at Jan 2022, increasing toward 1 by Jun 2024 for recovering parcels. Destroyed parcels with new construction may exceed 1 (new landscaping).

---

## Task 3: Visual Recovery via ESRI Wayback (All Dates)

**Step 1:** Define ESRI Wayback release mapping for all observation dates:
```python
ESRI_RELEASES = {
    "pre": 26120,       # 2021-12 pre-fire
    "2022-01": 7110,    # ~2022-11 (closest post-fire available)
    "2022-06": 7110,    # same release (no mid-2022 release available)
    "2023-06": 17632,   # 2023-08 mid-recovery
    "2024-06": 48925,   # 2025-07 late-recovery
}
```
Note: ESRI Wayback releases don't align perfectly with observation dates. Use closest available. Document the temporal mismatch.

**Step 2:** Reuse tile functions from notebook 08 (`latlon_to_tile`, `tile_to_latlon`, `fetch_tile`, `download_parcel_crop`).

**Step 3:** Download crops for observation dates not already cached. Cache to `data/processed/esri_crops/{ParcelNo}_{release}.jpg`. The pre (26120) and post (7110) crops from notebook 08 are already cached.

Additional crops needed:
- Release 17632 (mid-recovery): ~1,793 new crops
- Release 48925 (late-recovery): ~1,793 new crops

Rate limit 0.1s. Print progress every 200. ~6 min per release.

**Step 4:** Reuse `compute_ssim` from notebook 08. For each parcel × date:
```python
visual_recovery = compute_ssim(pre_crop, date_crop)
```
SSIM vs pre-fire measures how much the current view resembles the original state. Range [0, 1] where 1 = identical to pre-fire.

**Step 5:** Build DataFrame: `ParcelNo × date → visual_recovery`.

**Expected:** Destroyed parcels start with low SSIM (~0.2-0.3), gradually increasing as rebuilding progresses. Unaffected parcels should be ~0.4-0.6 throughout (seasonal variation only).

---

## Task 4: Composite Recovery Score

**Step 1:** Merge NDVI recovery and visual recovery into one DataFrame:
```
ParcelNo, date, ndvi_recovery, visual_recovery, damage_class
```

**Step 2:** Compute composite recovery score. This is a design choice — present it as an opportunity for user input:

A simple weighted average:
```python
recovery_score = 0.5 * ndvi_recovery + 0.5 * visual_recovery
```

Clip to [0, 1].

**Step 3:** Pivot to wide format for easy plotting:
```
ParcelNo, damage_class,
recovery_2022_01, recovery_2022_06, recovery_2023_06, recovery_2024_06
```

**Step 4:** Print summary statistics by damage class × date. Expected pattern:
- Destroyed: 0.05 → 0.15 → 0.40 → 0.65
- Damaged: 0.10 → 0.30 → 0.55 → 0.75
- Unaffected: 0.50 → 0.55 → 0.60 → 0.65

---

## Task 5: Recovery Trajectory Visualization

**Step 1:** Line plot — mean recovery score by damage class over time (with std shading). X-axis: months post-fire. Y-axis: recovery score [0, 1]. Three lines: Destroyed, Damaged, Unaffected.

**Step 2:** Histogram — recovery score distribution at latest date (Jun 2024), faceted by damage class. Shows bimodality in Destroyed (some rebuilt, some not).

**Step 3:** Map — parcels colored by recovery score at latest date. Use diverging colormap (red=low, yellow=mid, green=high). Overlay damage class as marker shape or outline color.

**Step 4:** Scatter plot — recovery score vs damage probability (from notebook 08). Do high-confidence Destroyed parcels recover faster or slower?

---

## Task 6: Identify Recovery Outliers

**Step 1:** Flag parcels with notable recovery patterns:
- **Stalled recovery:** Destroyed parcels with recovery < 0.3 at Jun 2024 (30 months)
- **Fast recovery:** Destroyed parcels with recovery > 0.7 at Jun 2024
- **Regression:** Any parcel where recovery decreased between consecutive dates

**Step 2:** Print top 10 stalled and top 10 fast-recovery parcels with addresses.

**Step 3:** For 3 example parcels (1 stalled, 1 fast, 1 regression), show ESRI Wayback image grid (pre → post → mid → late) alongside recovery score timeline. This is the "story" that the frontend tells.

---

## Task 7: Save Recovery Artifacts

**Step 1:** Save main output:
```python
# Long format: one row per parcel × date
recovery_long = pd.DataFrame({
    "ParcelNo": ...,
    "observation_date": ...,
    "months_post_fire": ...,
    "damage_class": ...,
    "damage_prob": ...,  # from notebook 08 xgb_pred probability
    "ndvi_recovery": ...,
    "visual_recovery": ...,
    "recovery_score": ...,
})
recovery_long.to_parquet(DATA_RESULTS / "recovery_scores.parquet", index=False)
```

**Step 2:** Save frontend-ready JSON (one file per parcel, enriching existing schema):
```python
# For each parcel, write/update detail JSON
for parcel_no, group in recovery_long.groupby("ParcelNo"):
    detail = {
        "ParcelNo": parcel_no,
        "damage_class": group["damage_class"].iloc[0],
        "damage_prob": float(group["damage_prob"].iloc[0]),
        "recovery_timeline": [
            {
                "date": row["observation_date"],
                "months_post_fire": int(row["months_post_fire"]),
                "ndvi_recovery": round(float(row["ndvi_recovery"]), 3),
                "visual_recovery": round(float(row["visual_recovery"]), 3),
                "recovery_score": round(float(row["recovery_score"]), 3),
            }
            for _, row in group.iterrows()
        ],
        "latest_recovery": round(float(group["recovery_score"].iloc[-1]), 3),
    }
    out_path = DATA_RESULTS / "parcels" / f"{parcel_no}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(detail, f, indent=2)
```

**Step 3:** Save summary statistics JSON:
```python
summary = {
    "n_parcels": n_parcels,
    "observation_dates": OBSERVATION_DATES,
    "recovery_by_class": {
        cls: {date: {"mean": ..., "std": ..., "median": ...} for date in dates}
        for cls in ["Destroyed", "Damaged", "Unaffected"]
    },
    "stalled_count": len(stalled),
    "fast_recovery_count": len(fast),
}
# Save to data/results/recovery_summary.json
```

---

## Task 8: Conclusions + Frontend Integration Notes

**Step 1:** Conclusions markdown cell:
- Recovery score methodology and limitations
- Key findings (recovery rates by class, outlier patterns)
- Note ESRI Wayback temporal misalignment (dates are approximate)
- Note NDVI recovery ratio limitations (30m resolution, seasonal effects)

**Step 2:** Frontend integration notes:
- `recovery_scores.parquet` can feed into dbt as a new staging model
- Per-parcel JSON in `data/results/parcels/{ParcelNo}.json` is directly consumable
- Recovery score drives map coloring (red→yellow→green gradient)
- Timeline charts show recovery trajectory per parcel on click
- Scrollytelling narrative can highlight outlier parcels as case studies

---

## Verification

1. `python -c "import json; d=json.load(open('notebooks/09_recovery_tracking.ipynb')); print(len(d['cells']), 'cells')"` — valid notebook
2. `python -c "import pandas; df=pandas.read_parquet('data/results/recovery_scores.parquet'); print(df.shape, df.columns.tolist())"` — parquet exists with expected columns
3. Check `data/results/parcels/` has JSON files
4. Check `data/results/recovery_summary.json` exists
5. Visual: recovery trajectory plot shows increasing trend for Destroyed class

## Dependencies

- All notebook 08 outputs must exist (`damage_classifier_predictions.parquet`, ESRI crops)
- Planetary Computer access (free, no auth)
- ESRI Wayback tiles (free, no auth)
- ~12 min for new ESRI crop downloads (2 releases × ~1,793 parcels × 0.1s)
