"""SAR processing: GRD → sigma0 dB → backscatter change → COG + zonal stats.

Sentinel-1 GRD from Planetary Computer is already radiometrically calibrated
to sigma0 (linear power). This module:
  1. Converts linear power to dB (10 * log10)
  2. Computes pre/post change for each observation date vs. pre-fire baseline
  3. Writes change COGs to data/processed/sar/
  4. Computes zonal stats per parcel → data/tabular/sar_zonal_stats.parquet
"""

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterstats import zonal_stats

from config.settings import OBSERVATION_DATES

logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/sentinel1")
OUT_DIR = Path("data/processed/sar")
TABULAR_DIR = Path("data/tabular")
PARCELS_PATH = Path("data/raw/parcels/boulder_county_parcels.geojson")
PRE_FIRE_DATE = OBSERVATION_DATES[0]  # 2021-11
BANDS = ["vv", "vh"]


def _linear_to_db(arr: np.ndarray) -> np.ndarray:
    """Convert linear power to decibels, handling zeros."""
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10.0 * np.log10(arr)
    db[~np.isfinite(db)] = np.nan
    return db


def _find_band_file(date_str: str, band: str) -> Path | None:
    """Find the downloaded TIF for a given date and band."""
    date_dir = RAW_DIR / date_str
    if not date_dir.exists():
        return None
    matches = list(date_dir.glob(f"{band}_*.tif"))
    return matches[0] if matches else None


def _read_as_db(path: Path) -> tuple[np.ndarray, dict]:
    """Read a raw GRD band and return as dB with profile."""
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float32)
        profile = src.profile.copy()
    return _linear_to_db(data), profile


def _write_cog(arr: np.ndarray, profile: dict, dest: Path) -> None:
    """Write a single-band array as a Cloud Optimized GeoTIFF."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    profile.update(dtype="float32", count=1, driver="GTiff", compress="deflate")
    with rasterio.open(dest, "w", **profile) as dst:
        dst.write(arr.astype(np.float32), 1)
    logger.info("  wrote %s", dest)


def _compute_change(pre_db: np.ndarray, post_db: np.ndarray) -> np.ndarray:
    """Compute change in dB (post - pre). Negative = backscatter loss."""
    return post_db - pre_db


def process_sar() -> None:
    """Process raw Sentinel-1 GRD to calibrated backscatter change COGs."""
    logger.info("process_sar: GRD → sigma0 dB → change → COG")

    # Load pre-fire baseline
    pre_files = {b: _find_band_file(PRE_FIRE_DATE, b) for b in BANDS}
    if not all(pre_files.values()):
        logger.warning("  pre-fire baseline files missing — skipping SAR processing")
        return

    pre_data = {}
    pre_profile = None
    for band, path in pre_files.items():
        db, profile = _read_as_db(path)
        pre_data[band] = db
        pre_profile = profile

    # Process each post-fire date
    change_records = []
    for date_str in OBSERVATION_DATES[1:]:
        for band in BANDS:
            post_path = _find_band_file(date_str, band)
            if post_path is None:
                logger.warning("  no %s file for %s — skipping", band, date_str)
                continue

            post_db, _ = _read_as_db(post_path)
            change = _compute_change(pre_data[band], post_db)

            dest = OUT_DIR / f"{band}_change_{date_str}.cog.tif"
            if not dest.exists():
                _write_cog(change, pre_profile, dest)

        # Compute zonal stats if parcels exist
        if PARCELS_PATH.exists():
            for band in BANDS:
                cog_path = OUT_DIR / f"{band}_change_{date_str}.cog.tif"
                if not cog_path.exists():
                    continue
                parcels = gpd.read_file(PARCELS_PATH)
                stats = zonal_stats(
                    parcels, str(cog_path),
                    stats=["mean", "std", "count"],
                    nodata=np.nan,
                )
                for i, row in enumerate(stats):
                    change_records.append({
                        "parcel_idx": i,
                        "observation_date": date_str,
                        f"{band}_change_db_mean": row.get("mean"),
                        f"{band}_change_db_std": row.get("std"),
                        f"{band}_pixel_count": row.get("count"),
                    })

    # Write zonal stats to parquet
    if change_records:
        TABULAR_DIR.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(change_records)
        # Pivot so each row = (parcel_idx, observation_date) with all band stats
        df = df.groupby(["parcel_idx", "observation_date"]).first().reset_index()
        dest = TABULAR_DIR / "sar_zonal_stats.parquet"
        df.to_parquet(dest, index=False)
        logger.info("  wrote %d rows to %s", len(df), dest)

    logger.info("process_sar: done")
