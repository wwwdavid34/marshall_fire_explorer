"""Polynomial curvature validation ("smile test") for InSAR coherence.

Destroyed parcels exhibit a characteristic U-shaped ("smile") coherence
pattern post-fire: initial drop followed by gradual recovery.  We fit a
degree-2 polynomial to the Wiener-smoothed post-fire coherence series and
extract the quadratic coefficient as "smile curvature" (a × 1e4).

Positive curvature = genuine destruction/rebuild pattern.
Flat or negative curvature = vegetation, open land, or misclassification.

Outputs:
  - data/results/parcel_curvature.parquet
    Columns: ParcelNo, smile_curvature, vertex_months, smile_valid
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import wiener

logger = logging.getLogger(__name__)

RESULTS_DIR = Path("data/results")
WIENER_WINDOW = 11           # ~132 days noise-adaptive smoothing
CURVATURE_THRESHOLD = 2.0    # a × 1e4; below = likely not real destruction


def smooth_series(series: np.ndarray, window: int = WIENER_WINDOW) -> np.ndarray:
    """Wiener filter a 1-D coherence series, interpolating NaN gaps first.

    Restores NaN where the original had too many gaps in the local window,
    preventing the Wiener filter from hallucinating values in sparse regions.
    """
    s = pd.Series(series)
    filled = s.interpolate(limit_direction="both").values
    if len(filled) < window or np.all(np.isnan(filled)):
        return np.full(len(series), np.nan)
    smoothed = wiener(filled, mysize=window)
    # Restore NaN where original had too many gaps
    nan_mask = s.rolling(window, center=True, min_periods=1).count() < max(1, window // 2)
    smoothed[nan_mask.values] = np.nan
    return smoothed


def compute_curvature(post_months: np.ndarray, smoothed: np.ndarray) -> dict:
    """Fit degree-2 polynomial and extract curvature metrics.

    Returns dict with: smile_curvature, vertex_months, smile_valid
    """
    valid = np.isfinite(smoothed) & np.isfinite(post_months)
    if valid.sum() < 10:
        return {"smile_curvature": np.nan, "vertex_months": np.nan, "smile_valid": False}

    coeffs = np.polyfit(post_months[valid], smoothed[valid], 2)
    a = coeffs[0]
    curv = a * 1e4

    # Vertex = -b / 2a (trough location in months)
    vertex = -coeffs[1] / (2 * a) if a != 0 else np.nan

    return {
        "smile_curvature": round(float(curv), 2),
        "vertex_months": round(float(vertex), 2) if np.isfinite(vertex) else np.nan,
        "smile_valid": curv >= CURVATURE_THRESHOLD,
    }


def run_curvature_analysis() -> pd.DataFrame:
    """Compute smile curvature for all labeled parcels.

    Reads coherence_timeseries.parquet, computes curvature per parcel,
    writes parcel_curvature.parquet.
    """
    logger.info("curvature: computing smile curvature for all labeled parcels")

    ts_path = RESULTS_DIR / "coherence_timeseries.parquet"
    if not ts_path.exists():
        logger.error("  coherence_timeseries.parquet not found")
        return pd.DataFrame()

    ts = pd.read_parquet(ts_path)

    # Find fire pair index: the pair where date1 is Dec 19, 2021
    # (last pre-fire acquisition, pair spans the fire date)
    sample_parcel = ts["ParcelNo"].iloc[0]
    sample = ts[ts["ParcelNo"] == sample_parcel].sort_values("pair_idx")
    fire_pair_idx = None
    for _, row in sample.iterrows():
        d1 = row["date1"]
        if isinstance(d1, str):
            d1_parsed = pd.Timestamp(d1)
        else:
            d1_parsed = pd.Timestamp(d1)
        if d1_parsed.year == 2021 and d1_parsed.month == 12 and d1_parsed.day == 19:
            fire_pair_idx = int(row["pair_idx"])
            break
    if fire_pair_idx is None:
        logger.error("  could not find fire pair (date1 = 2021-12-19)")
        return pd.DataFrame()

    logger.info("  fire pair index: %d", fire_pair_idx)

    results = []
    for parcel_no, grp in ts.groupby("ParcelNo"):
        grp = grp.sort_values("pair_idx")
        series = grp["norm_coh"].values
        post_series = series[fire_pair_idx:]
        smoothed = smooth_series(post_series)

        post_months = grp["months_post_fire"].values[fire_pair_idx:]
        curv_info = compute_curvature(post_months, smoothed)
        results.append({"ParcelNo": parcel_no, **curv_info})

    df = pd.DataFrame(results)
    out_path = RESULTS_DIR / "parcel_curvature.parquet"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    n_valid = df["smile_valid"].sum()
    logger.info("  %d parcels, %d valid smile (≥%.1f), %d below threshold",
                len(df), n_valid, CURVATURE_THRESHOLD, len(df) - n_valid)
    logger.info("  saved %s", out_path)

    return df
