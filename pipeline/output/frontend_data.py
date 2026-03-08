"""Generate static data files for the Marshall Fire Parcel Explorer frontend.

Outputs into frontend/public/data/:
  - parcels.geojson     (~2-3MB, labeled parcels with recovery + curvature)
  - timeseries/{ParcelNo}.json  (~1KB each, raw + Wiener-smoothed coherence)
  - crops               (symlink to ESRI crop images)
  - perimeter.geojson   (fire perimeter outline)

This module wraps the logic from scripts/prep_frontend_data.py for use
within the pipeline orchestrator.
"""

import json
import logging
import shutil
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.signal import wiener

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "frontend" / "public" / "data"
RESULTS = ROOT / "data" / "results"
GROUND_TRUTH = ROOT / "data" / "raw" / "ground_truth"
WIENER_W = 11


def _prep_parcels() -> None:
    """Filter labeled parcels, join recovery + curvature, simplify geometry."""
    logger.info("  preparing parcels.geojson")

    gdf = gpd.read_file(GROUND_TRUTH / "marshall_fire_damage_parcels.geojson")
    labeled = gdf[gdf["Condition"].isin(["Destroyed", "Damaged", "Unaffected"])].copy()

    # Join recovery detection (now includes exponential model fields)
    rec_path = RESULTS / "recovery_detection.parquet"
    if rec_path.exists():
        rec = pd.read_parquet(rec_path)
        rec_cols = ["ParcelNo", "recovery_date", "recovery_months_post_fire",
                    "recovery_tau", "recovery_cmin", "recovery_r2", "recovery_llm"]
        # Only include columns that exist (backwards compatible)
        rec_cols = [c for c in rec_cols if c in rec.columns]
        labeled = labeled.merge(rec[rec_cols], on="ParcelNo", how="left")
    else:
        labeled["recovery_date"] = None
        labeled["recovery_months_post_fire"] = None
        labeled["recovery_tau"] = None
        labeled["recovery_cmin"] = None
        labeled["recovery_r2"] = None
        logger.warning("  recovery_detection.parquet not found — no recovery data")

    # Join curvature (now includes bootstrap CI bounds)
    curv_path = RESULTS / "parcel_curvature.parquet"
    if curv_path.exists():
        curv = pd.read_parquet(curv_path)
        curv_cols = ["ParcelNo", "smile_curvature", "smile_valid",
                     "curvature_ci_lower", "curvature_ci_upper"]
        curv_cols = [c for c in curv_cols if c in curv.columns]
        labeled = labeled.merge(curv[curv_cols], on="ParcelNo", how="left")
    else:
        labeled["smile_curvature"] = None
        labeled["smile_valid"] = None
        labeled["curvature_ci_lower"] = None
        labeled["curvature_ci_upper"] = None
        logger.warning("  parcel_curvature.parquet not found — no curvature data")

    # Join building footprint ratio from coherence timeseries
    coh_path = RESULTS / "coherence_timeseries.parquet"
    if coh_path.exists():
        coh = pd.read_parquet(coh_path, columns=["ParcelNo", "building_ratio", "used_footprint"])
        fp_info = coh.drop_duplicates("ParcelNo")[["ParcelNo", "building_ratio", "used_footprint"]]
        labeled = labeled.merge(fp_info, on="ParcelNo", how="left")
    else:
        labeled["building_ratio"] = None
        labeled["used_footprint"] = None
        logger.warning("  coherence_timeseries.parquet not found — no footprint data")

    # Serialize
    labeled["recovery_date"] = labeled["recovery_date"].astype(str).replace("NaT", "")
    labeled["smile_valid"] = labeled["smile_valid"].map(
        {True: True, False: False, "True": True, "False": False}
    )

    keep = ["ParcelNo", "Condition", "recovery_date", "recovery_months_post_fire",
            "recovery_tau", "recovery_cmin", "recovery_r2", "recovery_llm",
            "smile_curvature", "smile_valid", "curvature_ci_lower", "curvature_ci_upper",
            "building_ratio", "used_footprint",
            "StrNum", "Street", "geometry"]
    # Only keep columns that actually exist (backwards compatible)
    keep = [c for c in keep if c in labeled.columns]
    labeled = labeled[keep]
    labeled["geometry"] = labeled["geometry"].simplify(tolerance=0.00001)

    out_path = OUT / "parcels.geojson"
    labeled.to_file(out_path, driver="GeoJSON")
    size_mb = out_path.stat().st_size / 1e6
    logger.info("    %d parcels, %.1fMB", len(labeled), size_mb)


def _prep_timeseries() -> None:
    """Write per-parcel coherence time series with Wiener smoothing."""
    logger.info("  preparing timeseries/")

    ts_path = RESULTS / "coherence_timeseries.parquet"
    if not ts_path.exists():
        logger.warning("  coherence_timeseries.parquet not found — skipping")
        return

    ts_dir = OUT / "timeseries"
    ts_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.read_parquet(ts_path)

    count = 0
    for parcel_no, grp in ts.groupby("ParcelNo"):
        grp = grp.sort_values("months_post_fire")
        raw = grp["norm_coh"].values

        filled = pd.Series(raw).interpolate(limit_direction="both").values
        if len(filled) >= WIENER_W and not np.all(np.isnan(filled)):
            smoothed = wiener(filled, mysize=WIENER_W)
        else:
            smoothed = np.full(len(raw), np.nan)

        records = []
        for i, (_, row) in enumerate(grp.iterrows()):
            records.append({
                "mid_date": row["mid_date"],
                "norm_coh": round(row["norm_coh"], 4) if pd.notna(row["norm_coh"]) else None,
                "smoothed": round(float(smoothed[i]), 4) if np.isfinite(smoothed[i]) else None,
                "months_post_fire": round(row["months_post_fire"], 2),
            })

        with open(ts_dir / f"{parcel_no}.json", "w") as f:
            json.dump(records, f, separators=(",", ":"))
        count += 1

    logger.info("    %d parcel timeseries files", count)


def _prep_crops_symlink() -> None:
    """Create symlink for ESRI crop images."""
    link = OUT / "crops"
    target = Path("../../../data/processed/esri_crops")
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(target)
    logger.info("  crops symlink: %s -> %s", link, target)


def _prep_perimeter() -> None:
    """Copy fire perimeter GeoJSON."""
    src = GROUND_TRUTH / "marshall_fire_perimeter.geojson"
    if not src.exists():
        logger.warning("  fire perimeter not found at %s", src)
        return
    dst = OUT / "perimeter.geojson"
    shutil.copy2(src, dst)
    logger.info("  perimeter: %.0fKB", dst.stat().st_size / 1e3)


def generate_frontend_data() -> None:
    """Generate all static frontend data files."""
    logger.info("frontend_data: generating static data for Parcel Explorer")
    OUT.mkdir(parents=True, exist_ok=True)
    _prep_parcels()
    _prep_timeseries()
    _prep_crops_symlink()
    _prep_perimeter()
    logger.info("frontend_data: done")
