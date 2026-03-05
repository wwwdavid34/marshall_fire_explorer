"""LiDAR processing: LAZ → DEM → DSM → CHM → COG + zonal stats.

Uses PDAL to classify and grid LAZ point clouds:
  - DEM (Digital Elevation Model): ground-classified returns
  - DSM (Digital Surface Model): first returns (highest surface)
  - CHM (Canopy Height Model): DSM - DEM
"""

import json
import logging
import subprocess
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterstats import zonal_stats

logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/lidar")
OUT_DIR = Path("data/processed/lidar")
TABULAR_DIR = Path("data/tabular")
PARCELS_PATH = Path("data/raw/parcels/boulder_county_parcels.geojson")
RESOLUTION = 1.0  # 1m grid


def _build_pdal_pipeline(
    laz_path: str, out_tif: str, returns_filter: str,
) -> list[dict]:
    """Build a PDAL pipeline JSON for gridding LAZ to GeoTIFF."""
    pipeline = [
        {"type": "readers.las", "filename": laz_path},
        {"type": "filters.reprojection", "out_srs": "EPSG:4326"},
    ]
    if returns_filter == "ground":
        pipeline.append({"type": "filters.smrf"})  # ground classification
        pipeline.append({
            "type": "filters.range",
            "limits": "Classification[2:2]",  # ground class
        })
    elif returns_filter == "first":
        pipeline.append({
            "type": "filters.range",
            "limits": "ReturnNumber[1:1]",
        })
    pipeline.append({
        "type": "writers.gdal",
        "filename": out_tif,
        "resolution": RESOLUTION,
        "output_type": "mean",
        "gdaldriver": "GTiff",
        "gdalopts": "COMPRESS=DEFLATE",
    })
    return pipeline


def _run_pdal(pipeline: list[dict]) -> bool:
    """Execute a PDAL pipeline via subprocess."""
    pipe_json = json.dumps({"pipeline": pipeline})
    try:
        subprocess.run(
            ["pdal", "pipeline", "--stdin"],
            input=pipe_json,
            capture_output=True,
            text=True,
            check=True,
            timeout=300,
        )
        return True
    except FileNotFoundError:
        logger.error("  pdal not found — install with: uv pip install pdal")
        return False
    except subprocess.CalledProcessError as e:
        logger.error("  PDAL failed: %s", e.stderr[:200])
        return False


def _write_chm(dem_path: Path, dsm_path: Path, chm_path: Path) -> None:
    """Compute CHM = DSM - DEM and write as COG."""
    with rasterio.open(dsm_path) as dsm_src, rasterio.open(dem_path) as dem_src:
        dsm = dsm_src.read(1).astype(np.float32)
        dem = dem_src.read(1).astype(np.float32)
        profile = dsm_src.profile.copy()

    chm = dsm - dem
    chm[chm < 0] = 0  # clip negative values (noise)

    profile.update(dtype="float32", count=1)
    chm_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(chm_path, "w", **profile) as dst:
        dst.write(chm, 1)
    logger.info("  wrote %s", chm_path)


def process_lidar() -> None:
    """Process raw LAZ point clouds to elevation model COGs."""
    logger.info("process_lidar: LAZ → DEM → DSM → CHM → COG")

    laz_files = list(RAW_DIR.glob("*.laz")) + list(RAW_DIR.glob("*.LAZ"))
    if not laz_files:
        logger.warning("  no LAZ files found in %s — skipping", RAW_DIR)
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zonal_records = []

    for laz_path in laz_files:
        stem = laz_path.stem
        dem_path = OUT_DIR / f"dem_{stem}.cog.tif"
        dsm_path = OUT_DIR / f"dsm_{stem}.cog.tif"
        chm_path = OUT_DIR / f"chm_{stem}.cog.tif"

        # DEM (ground returns)
        if not dem_path.exists():
            logger.info("  gridding DEM from %s", laz_path.name)
            pipeline = _build_pdal_pipeline(str(laz_path), str(dem_path), "ground")
            if not _run_pdal(pipeline):
                continue

        # DSM (first returns)
        if not dsm_path.exists():
            logger.info("  gridding DSM from %s", laz_path.name)
            pipeline = _build_pdal_pipeline(str(laz_path), str(dsm_path), "first")
            if not _run_pdal(pipeline):
                continue

        # CHM = DSM - DEM
        if not chm_path.exists() and dem_path.exists() and dsm_path.exists():
            _write_chm(dem_path, dsm_path, chm_path)

        # Zonal stats per parcel
        if PARCELS_PATH.exists() and chm_path.exists():
            parcels = gpd.read_file(PARCELS_PATH)
            for product, path in [
                ("dem", dem_path), ("dsm", dsm_path), ("chm", chm_path),
            ]:
                if not path.exists():
                    continue
                stats = zonal_stats(
                    parcels, str(path),
                    stats=["mean", "std", "max"],
                    nodata=np.nan,
                )
                for i, row in enumerate(stats):
                    zonal_records.append({
                        "parcel_idx": i,
                        "tile": stem,
                        f"{product}_mean": row.get("mean"),
                        f"{product}_std": row.get("std"),
                        f"{product}_max": row.get("max"),
                    })

    # Write zonal stats
    if zonal_records:
        TABULAR_DIR.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(zonal_records)
        df = df.groupby(["parcel_idx", "tile"]).first().reset_index()
        dest = TABULAR_DIR / "lidar_zonal_stats.parquet"
        df.to_parquet(dest, index=False)
        logger.info("  wrote %d rows to %s", len(df), dest)

    logger.info("process_lidar: done")
