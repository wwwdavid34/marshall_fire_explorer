"""Landsat processing: L2 → surface reflectance → dNBR, NDVI, TIR anomaly → COG + zonal stats.

Landsat Collection 2 Level-2 scale factors:
  - Surface reflectance: DN * 0.0000275 + (-0.174), clipped to [0, 1]
  - Surface temperature (ST_B10): DN * 0.00341802 + 149.0 (Kelvin)

Derived products:
  - NBR = (NIR - SWIR2) / (NIR + SWIR2)
  - dNBR = NBR_pre - NBR_post  (positive = burn severity)
  - NDVI = (NIR - Red) / (NIR + Red)
  - TIR anomaly = TIR_post - TIR_pre  (positive = elevated temperature)
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

RAW_DIR = Path("data/raw/landsat")
OUT_DIR = Path("data/processed/landsat")
TABULAR_DIR = Path("data/tabular")
PARCELS_PATH = Path("data/raw/parcels/boulder_county_parcels.geojson")
PRE_FIRE_DATE = OBSERVATION_DATES[0]  # 2021-11

# Landsat C2 L2 scale factors
SR_SCALE = 0.0000275
SR_OFFSET = -0.174
ST_SCALE = 0.00341802
ST_OFFSET = 149.0

# Band name mapping (Planetary Computer asset keys)
BAND_MAP = {
    "red": "red",
    "nir": "nir08",
    "swir2": "swir22",
    "tir": "lwir11",
}


def _find_band_file(date_str: str, asset_key: str) -> Path | None:
    """Find a downloaded Landsat band TIF."""
    date_dir = RAW_DIR / date_str
    if not date_dir.exists():
        return None
    matches = list(date_dir.glob(f"{asset_key}_*.tif"))
    return matches[0] if matches else None


def _read_band(path: Path) -> tuple[np.ndarray, dict]:
    """Read a single band as float32."""
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float32)
        profile = src.profile.copy()
    return data, profile


def _apply_sr_scale(dn: np.ndarray) -> np.ndarray:
    """Convert Landsat L2 DN to surface reflectance [0, 1]."""
    sr = dn * SR_SCALE + SR_OFFSET
    return np.clip(sr, 0.0, 1.0)


def _apply_st_scale(dn: np.ndarray) -> np.ndarray:
    """Convert Landsat L2 DN to surface temperature (Kelvin)."""
    return dn * ST_SCALE + ST_OFFSET


def _normalized_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute (a - b) / (a + b), handling division by zero."""
    with np.errstate(divide="ignore", invalid="ignore"):
        nd = (a - b) / (a + b)
    nd[~np.isfinite(nd)] = np.nan
    return nd


def _write_cog(arr: np.ndarray, profile: dict, dest: Path) -> None:
    """Write a single-band array as COG."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    profile.update(dtype="float32", count=1, driver="GTiff", compress="deflate")
    with rasterio.open(dest, "w", **profile) as dst:
        dst.write(arr.astype(np.float32), 1)
    logger.info("  wrote %s", dest)


def _load_calibrated(date_str: str) -> dict[str, tuple[np.ndarray, dict]] | None:
    """Load and calibrate all bands for a date. Returns {name: (array, profile)}."""
    result = {}
    for name, asset_key in BAND_MAP.items():
        path = _find_band_file(date_str, asset_key)
        if path is None:
            logger.warning("  missing %s for %s", name, date_str)
            return None
        dn, profile = _read_band(path)
        if name == "tir":
            result[name] = (_apply_st_scale(dn), profile)
        else:
            result[name] = (_apply_sr_scale(dn), profile)
    return result


def process_landsat() -> None:
    """Process raw Landsat L2 to calibrated indices COGs."""
    logger.info("process_landsat: calibration → dNBR → NDVI → TIR anomaly → COG")

    # Load pre-fire baseline
    pre = _load_calibrated(PRE_FIRE_DATE)
    if pre is None:
        logger.warning("  pre-fire baseline missing — skipping Landsat processing")
        return

    pre_nbr = _normalized_difference(pre["nir"][0], pre["swir2"][0])
    profile = pre["nir"][1]

    zonal_records = []

    for date_str in OBSERVATION_DATES[1:]:
        post = _load_calibrated(date_str)
        if post is None:
            continue

        # dNBR = NBR_pre - NBR_post (positive = burn severity)
        post_nbr = _normalized_difference(post["nir"][0], post["swir2"][0])
        dnbr = pre_nbr - post_nbr
        dnbr_path = OUT_DIR / f"dnbr_{date_str}.cog.tif"
        if not dnbr_path.exists():
            _write_cog(dnbr, profile, dnbr_path)

        # NDVI for this date
        ndvi = _normalized_difference(post["nir"][0], post["red"][0])
        ndvi_path = OUT_DIR / f"ndvi_{date_str}.cog.tif"
        if not ndvi_path.exists():
            _write_cog(ndvi, profile, ndvi_path)

        # TIR anomaly = post - pre (positive = elevated temperature)
        tir_anomaly = post["tir"][0] - pre["tir"][0]
        tir_path = OUT_DIR / f"tir_anomaly_{date_str}.cog.tif"
        if not tir_path.exists():
            _write_cog(tir_anomaly, profile, tir_path)

        # SWIR2 post (char/ash indicator)
        swir_path = OUT_DIR / f"swir2_{date_str}.cog.tif"
        if not swir_path.exists():
            _write_cog(post["swir2"][0], profile, swir_path)

        # Zonal stats per parcel
        if PARCELS_PATH.exists():
            parcels = gpd.read_file(PARCELS_PATH)
            products = {
                "dnbr": str(dnbr_path),
                "ndvi": str(ndvi_path),
                "tir_anomaly": str(tir_path),
                "swir2": str(swir_path),
            }
            for prod_name, prod_path in products.items():
                stats = zonal_stats(
                    parcels, prod_path,
                    stats=["mean", "std"],
                    nodata=np.nan,
                )
                for i, row in enumerate(stats):
                    zonal_records.append({
                        "parcel_idx": i,
                        "observation_date": date_str,
                        f"{prod_name}_mean": row.get("mean"),
                        f"{prod_name}_std": row.get("std"),
                    })

    # Write zonal stats
    if zonal_records:
        TABULAR_DIR.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(zonal_records)
        df = df.groupby(["parcel_idx", "observation_date"]).first().reset_index()
        dest = TABULAR_DIR / "landsat_zonal_stats.parquet"
        df.to_parquet(dest, index=False)
        logger.info("  wrote %d rows to %s", len(df), dest)

    logger.info("process_landsat: done")
