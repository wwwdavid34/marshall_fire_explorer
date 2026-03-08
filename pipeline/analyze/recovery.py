"""Recovery detection via sustained threshold crossing on Wiener-filtered coherence.

Methodology:
  1. Compute pre-fire baseline: 75th percentile of pre-fire coherence
  2. Set recovery threshold: 70% of baseline
  3. Apply Wiener filter to smooth post-fire coherence series
  4. Per-parcel minimum delay = max(vertex_months from curvature, 6 months)
  5. Detect first sustained crossing: 5 consecutive pairs above threshold

Only runs on Destroyed parcels (damage_class from coherence timeseries).

Outputs:
  - data/results/recovery_detection.parquet
    Columns: ParcelNo, damage_class, pre_baseline, recovery_date,
             recovery_months_post_fire, smile_curvature, vertex_months, smile_valid,
             recovery_tau, recovery_cmin, recovery_r2
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

from config.settings import FIRE_DATE
from pipeline.analyze.curvature import smooth_series

logger = logging.getLogger(__name__)

RESULTS_DIR = Path("data/results")

# Detection parameters
BASELINE_QUANTILE = 0.75     # pre-fire baseline percentile
THRESHOLD_FRACTION = 0.90    # fraction of baseline for recovery
THRESHOLD_CAP = 1.05         # max absolute threshold (high-baseline parcels can't exceed this)
SUSTAIN_PAIRS = 5            # consecutive pairs above threshold (~60 days)
MIN_DELAY_MONTHS = 6         # minimum months before recovery can be declared


def find_sustained_crossing(
    smoothed: np.ndarray, threshold: float, sustain: int, skip_first: int = 0,
) -> int | None:
    """Find first index where smoothed series stays above threshold for `sustain` pairs."""
    above = smoothed >= threshold
    run = 0
    for i in range(skip_first, len(above)):
        if above[i]:
            run += 1
            if run >= sustain:
                return i - sustain + 1
        else:
            run = 0
    return None


def fit_recovery_model(
    post_months: np.ndarray, smoothed: np.ndarray, baseline: float,
) -> dict:
    """Fit exponential relaxation model to post-fire smoothed coherence.

    Model: coh(t) = c_min + (baseline - c_min) * [1 - exp(-(t - t0) / tau)]
    where t0 = first post-fire month.

    Returns dict with recovery_tau, recovery_cmin, recovery_r2.
    """
    valid = np.isfinite(smoothed) & np.isfinite(post_months)
    if valid.sum() < 10:
        return {"recovery_tau": np.nan, "recovery_cmin": np.nan, "recovery_r2": np.nan}

    m = post_months[valid]
    s = smoothed[valid]
    t0 = m[0]

    def recovery_curve(t, c_min, tau):
        return c_min + (baseline - c_min) * (1 - np.exp(-(t - t0) / tau))

    try:
        popt, _ = curve_fit(
            recovery_curve, m, s,
            p0=[s.min(), 12.0],
            bounds=([0, 1], [baseline, 60]),
            maxfev=500,
        )
        c_min, tau = popt

        # R² goodness of fit
        predicted = recovery_curve(m, c_min, tau)
        ss_res = np.sum((s - predicted) ** 2)
        ss_tot = np.sum((s - np.mean(s)) ** 2)
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        if r2 < 0.3:
            tau = np.nan

        return {
            "recovery_tau": round(float(tau), 2) if np.isfinite(tau) else np.nan,
            "recovery_cmin": round(float(c_min), 4),
            "recovery_r2": round(float(r2), 3),
        }
    except (RuntimeError, ValueError):
        return {"recovery_tau": np.nan, "recovery_cmin": np.nan, "recovery_r2": np.nan}


def run_recovery_detection() -> pd.DataFrame:
    """Detect recovery for Destroyed parcels only.

    Requires coherence_timeseries.parquet and parcel_curvature.parquet.
    """
    logger.info("recovery: detecting sustained coherence recovery")

    ts_path = RESULTS_DIR / "coherence_timeseries.parquet"
    curv_path = RESULTS_DIR / "parcel_curvature.parquet"

    if not ts_path.exists():
        logger.error("  coherence_timeseries.parquet not found")
        return pd.DataFrame()

    ts = pd.read_parquet(ts_path)

    # Filter to Destroyed parcels only
    destroyed_parcels = ts[ts["damage_class"] == "Destroyed"]["ParcelNo"].unique()
    ts_destroyed = ts[ts["ParcelNo"].isin(destroyed_parcels)]
    logger.info("  %d Destroyed parcels for recovery detection", len(destroyed_parcels))

    # Load curvature data for vertex-based min delay
    curv_df = pd.read_parquet(curv_path) if curv_path.exists() else pd.DataFrame()
    curv_lookup = {}
    if not curv_df.empty:
        curv_lookup = curv_df.set_index("ParcelNo").to_dict("index")

    # Find fire pair index using date1 column
    sample_parcel = ts_destroyed["ParcelNo"].iloc[0]
    sample = ts_destroyed[ts_destroyed["ParcelNo"] == sample_parcel].sort_values("pair_idx")
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

    # Build pair mid-dates for recovery date lookup
    pair_months = sample.sort_values("pair_idx")["months_post_fire"].values

    # Check if raw coherence column is available for weighting
    has_raw_coh = "raw_coh" in ts_destroyed.columns

    records = []
    n_good_fits = 0
    for parcel_no, grp in ts_destroyed.groupby("ParcelNo"):
        grp = grp.sort_values("pair_idx")
        series = grp["norm_coh"].values

        # Pre-fire baseline
        pre_vals = series[:fire_pair_idx]
        pre_vals = pre_vals[np.isfinite(pre_vals)]
        if len(pre_vals) < 3:
            continue
        baseline = float(np.percentile(pre_vals, BASELINE_QUANTILE * 100))
        threshold = min(baseline * THRESHOLD_FRACTION, THRESHOLD_CAP)

        # Post-fire Wiener smoothing (with MAD rejection + optional weighting)
        post_series = series[fire_pair_idx:]
        raw_coh = grp["raw_coh"].values[fire_pair_idx:] if has_raw_coh else None
        smoothed, _ = smooth_series(post_series, raw_coh=raw_coh)

        # Per-parcel min delay from curvature vertex (smile_valid gate)
        curv_info = curv_lookup.get(parcel_no, {})
        smile_valid = curv_info.get("smile_valid", False)
        vertex_months = curv_info.get("vertex_months", MIN_DELAY_MONTHS)
        if not np.isfinite(vertex_months) or vertex_months < MIN_DELAY_MONTHS:
            vertex_months = MIN_DELAY_MONTHS

        post_months = grp["months_post_fire"].values[fire_pair_idx:]
        skip_first = int(np.searchsorted(post_months, vertex_months))

        # Only detect recovery for parcels with confirmed destruction (smile_valid)
        recovery_date = None
        recovery_months = None
        if smile_valid:
            crossing_idx = find_sustained_crossing(smoothed, threshold, SUSTAIN_PAIRS, skip_first)
            if crossing_idx is not None:
                recovery_months = float(post_months[crossing_idx])
                recovery_date = FIRE_DATE + timedelta(days=recovery_months * 30.44)

        # Exponential relaxation model fit
        model_info = fit_recovery_model(post_months, smoothed, baseline)
        if np.isfinite(model_info.get("recovery_tau", np.nan)):
            n_good_fits += 1

        records.append({
            "ParcelNo": parcel_no,
            "damage_class": "Destroyed",
            "pre_baseline": round(baseline, 4),
            "recovery_date": recovery_date,
            "recovery_months_post_fire": round(recovery_months, 1) if recovery_months else None,
            "smile_curvature": curv_info.get("smile_curvature", np.nan),
            "vertex_months": curv_info.get("vertex_months", np.nan),
            "smile_valid": curv_info.get("smile_valid", False),
            **model_info,
        })

    df = pd.DataFrame(records)
    out_path = RESULTS_DIR / "recovery_detection.parquet"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    n_recovered = df["recovery_date"].notna().sum()
    n_valid = df["smile_valid"].sum()
    logger.info("  %d parcels: %d recovered, %d valid smile", len(df), n_recovered, n_valid)
    logger.info("  exponential model: %d/%d parcels with good fit (R² ≥ 0.3)",
                n_good_fits, len(df))
    logger.info("  saved %s", out_path)

    return df
