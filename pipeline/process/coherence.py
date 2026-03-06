"""Compute InSAR coherence from OPERA CSLC pairs and build normalized time series.

Methodology:
  1. Load consecutive CSLC pair (t, t+1) chips clipped to AOI in UTM
  2. Compute interferometric coherence via uniform spatial averaging
  3. Aggregate per-parcel mean coherence via zonal stats
  4. Normalize each pair by Costco parking lot reference coherence
  5. Output: coherence_timeseries.parquet (long format)

Schema: ParcelNo, pair_idx, date1, date2, mid_date, months_post_fire,
        raw_coh, costco_coh, norm_coh, damage_class
"""

import logging
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import h5py
import numpy as np
import pandas as pd
from pyproj import Transformer
from rasterio.transform import Affine
from rasterstats import zonal_stats
from scipy.ndimage import uniform_filter
from shapely.geometry import box as shapely_box

from config.settings import AOI_CSLC, BURST_ID, COSTCO_PARCEL, FIRE_DATE

logger = logging.getLogger(__name__)

CSLC_DIR = Path("data/raw/sentinel1/cslc")
RESULTS_DIR = Path("data/results")
DAMAGE_PARCELS = Path("data/raw/ground_truth/marshall_fire_damage_parcels.geojson")

COHERENCE_WINDOW = 5
MIN_COH_PIXELS = 3


def _parse_date(path: Path) -> datetime:
    """Extract acquisition date from OPERA CSLC filename."""
    for part in path.stem.split("_"):
        if part.startswith("20") and "T" in part and part.endswith("Z"):
            return datetime.strptime(part[:8], "%Y%m%d")
    raise ValueError(f"Cannot parse date from {path.name}")


def _discover_pairs() -> list[tuple[tuple[datetime, Path], tuple[datetime, Path]]]:
    """Find all CSLC files for our burst and form consecutive pairs."""
    pattern = f"OPERA_L2_CSLC-S1_{BURST_ID}_*.h5"
    h5_files = sorted(CSLC_DIR.glob(pattern))
    if not h5_files:
        # Fallback: try without burst filter
        h5_files = sorted(CSLC_DIR.glob("OPERA_L2_CSLC-S1_*.h5"))
    dates_files = sorted([(_parse_date(f), f) for f in h5_files], key=lambda x: x[0])
    return [(dates_files[i], dates_files[i + 1]) for i in range(len(dates_files) - 1)]


def _load_cslc_chip(h5_path: Path, aoi_bounds_utm: tuple) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load complex SLC chip from OPERA CSLC HDF5, clipped to UTM AOI.

    Returns (slc_chip, x_coords, y_coords).
    """
    w, s, e, n = aoi_bounds_utm
    with h5py.File(h5_path, "r") as f:
        x = f["/data/x_coordinates"][:]
        y = f["/data/y_coordinates"][:]
        col_mask = (x >= w) & (x <= e)
        row_mask = (y >= s) & (y <= n)
        c0, c1 = np.where(col_mask)[0][[0, -1]]
        r0, r1 = np.where(row_mask)[0][[0, -1]]
        slc = f["/data/VV"][r0:r1 + 1, c0:c1 + 1]
        x_chip = x[c0:c1 + 1]
        y_chip = y[r0:r1 + 1]
    return slc, x_chip, y_chip


def _compute_coherence(slc1: np.ndarray, slc2: np.ndarray, win: int = COHERENCE_WINDOW) -> np.ndarray:
    """Compute interferometric coherence between two SLC images.

    γ = |⟨s1 · s2*⟩| / sqrt(⟨|s1|²⟩ · ⟨|s2|²⟩)

    NaN pixels are zeroed for computation, then restored.
    """
    s1 = np.where(np.isfinite(slc1), slc1, 0)
    s2 = np.where(np.isfinite(slc2), slc2, 0)
    cross_real = uniform_filter(np.real(s1 * np.conj(s2)), win)
    cross_imag = uniform_filter(np.imag(s1 * np.conj(s2)), win)
    cross = cross_real + 1j * cross_imag
    pow1 = uniform_filter(np.abs(s1) ** 2, win)
    pow2 = uniform_filter(np.abs(s2) ** 2, win)
    denom = np.sqrt(pow1 * pow2)
    coh = np.where(denom > 0, np.abs(cross) / denom, 0)
    valid = np.isfinite(slc1) & np.isfinite(slc2)
    coh[~valid] = np.nan
    return coh.astype(np.float32)


def process_coherence() -> None:
    """Compute coherence for all consecutive CSLC pairs, normalize, and build time series."""
    logger.info("process_coherence: computing InSAR coherence from CSLC pairs")

    pairs = _discover_pairs()
    n_pairs = len(pairs)
    if n_pairs == 0:
        logger.warning("  no consecutive CSLC pairs found")
        return
    logger.info("  %d consecutive pairs (%s → %s)",
                n_pairs, pairs[0][0][0].date(), pairs[-1][1][0].date())

    # Convert AOI to UTM 32613
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32613", always_xy=True)
    aoi_west, aoi_south = to_utm.transform(AOI_CSLC[0], AOI_CSLC[1])
    aoi_east, aoi_north = to_utm.transform(AOI_CSLC[2], AOI_CSLC[3])
    aoi_bounds_utm = (aoi_west, aoi_south, aoi_east, aoi_north)

    # Load parcels
    if not DAMAGE_PARCELS.exists():
        logger.error("  damage parcels not found at %s", DAMAGE_PARCELS)
        return
    gdf_all = gpd.read_file(DAMAGE_PARCELS)
    gdf = gdf_all[gdf_all["Condition"].isin(["Destroyed", "Damaged", "Unaffected"])].copy()
    # Deduplicate: keep worst severity per ParcelNo
    severity = {"Destroyed": 0, "Damaged": 1, "Unaffected": 2}
    gdf["_severity"] = gdf["Condition"].map(severity)
    gdf = gdf.sort_values("_severity").drop_duplicates(subset="ParcelNo", keep="first").drop(columns="_severity")
    gdf = gdf.reset_index(drop=True)
    logger.info("  %d labeled parcels", len(gdf))

    # Compute all coherence maps
    logger.info("  computing coherence for %d pairs...", n_pairs)
    coherence_maps = []
    pair_dates = []
    pair_mid_dates = []

    for idx, ((dt1, f1), (dt2, f2)) in enumerate(pairs):
        slc1, x_coords, y_coords = _load_cslc_chip(f1, aoi_bounds_utm)
        slc2, _, _ = _load_cslc_chip(f2, aoi_bounds_utm)
        coh = _compute_coherence(slc1, slc2, win=COHERENCE_WINDOW)
        coherence_maps.append(coh)
        pair_dates.append((dt1, dt2))
        pair_mid_dates.append(dt1 + (dt2 - dt1) / 2)
        if (idx + 1) % 10 == 0 or idx == n_pairs - 1:
            logger.info("    [%d/%d] %s → %s  mean=%.3f",
                        idx + 1, n_pairs, dt1.strftime("%Y-%m-%d"),
                        dt2.strftime("%Y-%m-%d"), np.nanmean(coh))

    # Build affine transform from pixel coordinates
    dx = float(x_coords[1] - x_coords[0])
    dy = float(y_coords[1] - y_coords[0])
    coh_transform = Affine(dx, 0, x_coords[0] - dx / 2, 0, dy, y_coords[0] - dy / 2)

    # Load parcels in UTM, filter to CSLC coverage
    parcels_utm = gdf.to_crs(epsg=32613)
    cslc_box = shapely_box(*aoi_bounds_utm)
    in_cslc = parcels_utm.intersects(cslc_box)
    parcels_utm = parcels_utm[in_cslc].reset_index(drop=True)
    logger.info("  %d parcels within CSLC coverage", len(parcels_utm))

    # Load Costco parcel separately in UTM
    costco_gdf = gdf_all[gdf_all["ParcelNo"] == COSTCO_PARCEL].to_crs(epsg=32613)

    # Zonal stats for all pairs
    n_parcels = len(parcels_utm)
    coh_array = np.full((n_parcels, n_pairs), np.nan, dtype=np.float32)
    costco_coh = []

    logger.info("  computing zonal stats for %d pairs × %d parcels...", n_pairs, n_parcels)
    for i, coh_map in enumerate(coherence_maps):
        # Costco reference
        cs = zonal_stats(costco_gdf.geometry, coh_map, affine=coh_transform,
                         stats=["mean"], nodata=np.nan)
        costco_coh.append(cs[0]["mean"] if cs[0]["mean"] else np.nan)

        # Per-parcel zonal stats
        stats = zonal_stats(parcels_utm.geometry, coh_map, affine=coh_transform,
                            stats=["mean", "count"], nodata=np.nan)
        for j, s in enumerate(stats):
            mean_val = s["mean"]
            count_val = s["count"] if s["count"] is not None else 0
            if count_val >= MIN_COH_PIXELS and mean_val is not None:
                coh_array[j, i] = mean_val
            # else stays NaN

        if (i + 1) % 10 == 0 or i == n_pairs - 1:
            logger.info("    [%d/%d] Costco=%.3f", i + 1, n_pairs, costco_coh[i] or 0)

    # Normalize by Costco
    costco_arr = np.array(costco_coh)
    costco_safe = np.where(costco_arr > 0.01, costco_arr, np.nan)
    norm_matrix = coh_array / costco_safe[np.newaxis, :]
    logger.info("  Costco coherence range: %.3f – %.3f",
                np.nanmin(costco_arr), np.nanmax(costco_arr))

    # Build long-format DataFrame
    records = []
    parcel_nos = parcels_utm["ParcelNo"].values
    parcel_conditions = parcels_utm["Condition"].values

    for i in range(n_pairs):
        d1, d2 = pair_dates[i]
        mid = pair_mid_dates[i]
        months_post = (mid - FIRE_DATE).days / 30.44
        costco_val = costco_coh[i]
        for j in range(n_parcels):
            raw = coh_array[j, i]
            norm = norm_matrix[j, i]
            records.append({
                "ParcelNo": parcel_nos[j],
                "pair_idx": i,
                "date1": d1.strftime("%Y-%m-%d"),
                "date2": d2.strftime("%Y-%m-%d"),
                "mid_date": mid.strftime("%Y-%m-%d"),
                "months_post_fire": round(months_post, 2),
                "raw_coh": float(raw) if np.isfinite(raw) else np.nan,
                "costco_coh": float(costco_val) if costco_val and np.isfinite(costco_val) else np.nan,
                "norm_coh": float(norm) if np.isfinite(norm) else np.nan,
                "damage_class": parcel_conditions[j],
            })

    ts_df = pd.DataFrame(records)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "coherence_timeseries.parquet"
    ts_df.to_parquet(out_path, index=False)

    logger.info("  saved %s (%d rows, %d parcels × %d pairs)",
                out_path, len(ts_df), ts_df["ParcelNo"].nunique(), n_pairs)
    logger.info("process_coherence: done")
