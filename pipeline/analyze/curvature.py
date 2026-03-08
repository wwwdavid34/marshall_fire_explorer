"""Polynomial curvature validation ("smile test") for InSAR coherence.

Destroyed parcels exhibit a characteristic U-shaped ("smile") coherence
pattern post-fire: initial drop followed by gradual recovery.  We fit a
degree-2 polynomial to the Wiener-smoothed post-fire coherence series and
extract the quadratic coefficient as "smile curvature" (a × 1e4).

Positive curvature = genuine destruction/rebuild pattern.
Flat or negative curvature = vegetation, open land, or misclassification.

Outputs:
  - data/results/parcel_curvature.parquet
    Columns: ParcelNo, smile_curvature, vertex_months, smile_valid,
             curvature_ci_lower, curvature_ci_upper, n_outliers
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
COHERENCE_WINDOW = 5         # spatial multilook window (5×5 = 25 looks)
N_LOOKS = COHERENCE_WINDOW ** 2
N_BOOT = 200                 # bootstrap resamples for curvature CI


def reject_outliers_mad(series: np.ndarray, sigma: float = 3.0) -> tuple[np.ndarray, int]:
    """Flag anomalous acquisitions using Median Absolute Deviation.

    Returns a copy with outliers set to NaN and the count of outliers detected.
    """
    s = series.copy()
    finite = s[np.isfinite(s)]
    if len(finite) < 5:
        return s, 0
    med = np.median(finite)
    residuals = s - med
    mad = np.median(np.abs(residuals[np.isfinite(residuals)]))
    threshold = sigma * 1.4826 * mad
    outlier_mask = np.abs(residuals) > threshold
    outlier_mask[~np.isfinite(s)] = False  # don't count existing NaNs
    n_outliers = int(outlier_mask.sum())
    s[outlier_mask] = np.nan
    return s, n_outliers


def coherence_to_weights(raw_coh: np.ndarray) -> np.ndarray:
    """Convert raw coherence to observation weights via Touzi et al. 1999 variance.

    variance = (1 - coh^2) / (2 * N_looks * coh^2)
    weight = 1 / variance
    """
    coh = np.clip(raw_coh, 0.01, 0.999)  # avoid division by zero
    variance = (1 - coh**2) / (2 * N_LOOKS * coh**2)
    return 1.0 / variance


def smooth_series(
    series: np.ndarray,
    window: int = WIENER_WINDOW,
    raw_coh: np.ndarray | None = None,
) -> tuple[np.ndarray, int]:
    """Wiener filter a 1-D coherence series with MAD outlier rejection.

    If raw_coh is provided, applies coherence-derived variance weighting
    via weighted interpolation before the Wiener pass.

    Returns (smoothed_series, n_outliers).
    """
    # MAD outlier rejection before any smoothing
    cleaned, n_outliers = reject_outliers_mad(series)

    s = pd.Series(cleaned)

    # Weighted interpolation when coherence weights are available
    if raw_coh is not None and len(raw_coh) == len(series):
        weights = coherence_to_weights(raw_coh)
        weights[~np.isfinite(cleaned)] = 0.0  # zero weight for NaN/outlier points
        # Weighted rolling mean as pre-filter before Wiener
        ws = pd.Series(cleaned * weights)
        ww = pd.Series(weights)
        roll_ws = ws.rolling(window, center=True, min_periods=1).sum()
        roll_ww = ww.rolling(window, center=True, min_periods=1).sum()
        weighted_filled = (roll_ws / roll_ww.replace(0, np.nan)).values
        # Fill remaining NaNs with standard interpolation
        filled = pd.Series(weighted_filled).interpolate(limit_direction="both").values
    else:
        filled = s.interpolate(limit_direction="both").values

    if len(filled) < window or np.all(np.isnan(filled)):
        return np.full(len(series), np.nan), n_outliers

    smoothed = wiener(filled, mysize=window)
    # Restore NaN where original had too many gaps
    nan_mask = s.rolling(window, center=True, min_periods=1).count() < max(1, window // 2)
    smoothed[nan_mask.values] = np.nan
    return smoothed, n_outliers


def compute_curvature(post_months: np.ndarray, smoothed: np.ndarray) -> dict:
    """Fit degree-2 polynomial and extract curvature metrics with bootstrap CI.

    Returns dict with: smile_curvature, vertex_months, smile_valid,
                       curvature_ci_lower, curvature_ci_upper
    """
    valid = np.isfinite(smoothed) & np.isfinite(post_months)
    n_valid = valid.sum()
    if n_valid < 10:
        return {
            "smile_curvature": np.nan, "vertex_months": np.nan, "smile_valid": False,
            "curvature_ci_lower": np.nan, "curvature_ci_upper": np.nan,
        }

    m = post_months[valid]
    s = smoothed[valid]

    coeffs = np.polyfit(m, s, 2)
    a = coeffs[0]
    curv = a * 1e4

    # Vertex = -b / 2a (trough location in months)
    vertex = -coeffs[1] / (2 * a) if a != 0 else np.nan

    # Bootstrap CI on curvature
    rng = np.random.default_rng(42)
    boot_curvatures = np.empty(N_BOOT)
    for b in range(N_BOOT):
        idx = rng.choice(n_valid, size=n_valid, replace=True)
        boot_coeffs = np.polyfit(m[idx], s[idx], 2)
        boot_curvatures[b] = boot_coeffs[0] * 1e4
    ci_lower = float(np.percentile(boot_curvatures, 2.5))
    ci_upper = float(np.percentile(boot_curvatures, 97.5))

    return {
        "smile_curvature": round(float(curv), 2),
        "vertex_months": round(float(vertex), 2) if np.isfinite(vertex) else np.nan,
        "smile_valid": ci_lower >= CURVATURE_THRESHOLD,
        "curvature_ci_lower": round(ci_lower, 2),
        "curvature_ci_upper": round(ci_upper, 2),
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

    # Check if raw coherence column is available for weighting
    has_raw_coh = "raw_coh" in ts.columns

    results = []
    total_outliers = 0
    for parcel_no, grp in ts.groupby("ParcelNo"):
        grp = grp.sort_values("pair_idx")
        series = grp["norm_coh"].values
        post_series = series[fire_pair_idx:]

        raw_coh = grp["raw_coh"].values[fire_pair_idx:] if has_raw_coh else None
        smoothed, n_outliers = smooth_series(post_series, raw_coh=raw_coh)
        total_outliers += n_outliers

        post_months = grp["months_post_fire"].values[fire_pair_idx:]
        curv_info = compute_curvature(post_months, smoothed)
        curv_info["n_outliers"] = n_outliers
        results.append({"ParcelNo": parcel_no, **curv_info})

    df = pd.DataFrame(results)
    out_path = RESULTS_DIR / "parcel_curvature.parquet"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    n_valid = df["smile_valid"].sum()
    logger.info("  %d parcels, %d valid smile (CI lower ≥%.1f), %d below threshold",
                len(df), n_valid, CURVATURE_THRESHOLD, len(df) - n_valid)
    logger.info("  MAD outlier rejection: %d total outliers flagged across all parcels",
                total_outliers)
    logger.info("  saved %s", out_path)

    return df
