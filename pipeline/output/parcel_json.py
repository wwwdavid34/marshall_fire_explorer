"""Write per-parcel detail JSON files and index GeoJSON from the dbt mart.

Outputs:
  - data/results/parcels/detail/{parcel_idx}.json  (full metrics per parcel)
  - data/results/parcels/index.geojson             (lightweight for map rendering)
"""

import json
import logging
from pathlib import Path

import duckdb
import geopandas as gpd

logger = logging.getLogger(__name__)

RESULTS_DIR = Path("data/results/parcels")
PARCELS_PATH = Path("data/raw/Parcel/Parcel.shp")


def _get_db_path() -> str:
    """Resolve DuckDB path from environment."""
    import os
    return os.getenv("DBT_DUCKDB_PATH", "data/marshall.duckdb")


def write_parcel_json() -> None:
    """Write data/results/parcels/detail/{parcel_idx}.json for each parcel."""
    logger.info("write_parcel_json: mart → detail JSON files")

    db_path = _get_db_path()
    try:
        conn = duckdb.connect(db_path, read_only=True)
    except Exception:
        logger.warning("  DuckDB not available at %s — skipping", db_path)
        return

    # Check if mart table exists
    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]
    if "marshall_parcel_change" not in table_names:
        logger.warning("  mart table not found — run dbt first")
        conn.close()
        return

    # Read all mart rows
    df = conn.execute("SELECT * FROM marshall_parcel_change").fetchdf()
    conn.close()

    if df.empty:
        logger.warning("  mart is empty — no parcels to write")
        return

    detail_dir = RESULTS_DIR / "detail"
    detail_dir.mkdir(parents=True, exist_ok=True)

    # Group by parcel_idx, write one JSON per parcel
    parcel_count = 0
    for parcel_idx, group in df.groupby("parcel_idx"):
        record = {
            "parcel_idx": int(parcel_idx),
            "observations": [],
        }
        for _, row in group.iterrows():
            obs = {
                "observation_date": row.get("observation_date"),
                "vv_change_db": _safe_float(row.get("vv_change_db_mean")),
                "vh_change_db": _safe_float(row.get("vh_change_db_mean")),
                "sar_change_class": row.get("sar_change_class"),
                "sar_confidence": row.get("sar_confidence"),
                "dnbr": _safe_float(row.get("dnbr_mean")),
                "ndvi": _safe_float(row.get("ndvi_mean")),
                "tir_anomaly": _safe_float(row.get("tir_anomaly_mean")),
                "swir2": _safe_float(row.get("swir2_mean")),
                "burn_severity_class": row.get("burn_severity_class"),
            }
            record["observations"].append(obs)

        # Add static fields from first row
        first = group.iloc[0]
        record["chm_mean_pre"] = _safe_float(first.get("chm_mean_pre"))
        record["vv_pixel_count"] = _safe_int(first.get("vv_pixel_count"))

        dest = detail_dir / f"{int(parcel_idx)}.json"
        with open(dest, "w") as f:
            json.dump(record, f, separators=(",", ":"))
        parcel_count += 1

    logger.info("  wrote %d parcel detail files to %s", parcel_count, detail_dir)

    # Write index GeoJSON (lightweight — just parcel_idx + geometry)
    _write_index_geojson()


def _write_index_geojson() -> None:
    """Write a lightweight GeoJSON index of all parcels for map rendering."""
    if not PARCELS_PATH.exists():
        logger.warning("  parcels GeoJSON not found — skipping index")
        return

    gdf = gpd.read_file(PARCELS_PATH)
    # Keep only geometry + row index for lightweight loading
    gdf["parcel_idx"] = range(len(gdf))
    index_gdf = gdf[["parcel_idx", "geometry"]]

    dest = RESULTS_DIR / "index.geojson"
    dest.parent.mkdir(parents=True, exist_ok=True)
    index_gdf.to_file(dest, driver="GeoJSON")
    logger.info("  wrote parcel index to %s (%d parcels)", dest, len(index_gdf))


def _safe_float(val) -> float | None:
    """Convert to float, returning None for NaN/None."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if f != f else round(f, 4)  # NaN check
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    """Convert to int, returning None for NaN/None."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
