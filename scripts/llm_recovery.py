"""LLM-based recovery detection using full-resolution coherence time series.

Prepares batch files with all 117 post-fire observations (12-day cadence)
and NEW CONSTRUCTION permit dates as a lower-bound constraint.

Usage:
    uv run python scripts/llm_recovery.py prepare   # write batch files
    uv run python scripts/llm_recovery.py merge      # combine results → parquet
"""

import json
import sys
from pathlib import Path

import pandas as pd

FIRE_DATE = pd.Timestamp("2021-12-30")
DATA_RAW = Path("data/raw")
RESULTS = Path("data/results")
TS_DIR = Path("frontend/public/data/timeseries")
BATCH_DIR = RESULTS / "llm_batches_v2"
BATCH_SIZE = 45

PROMPT_TEMPLATE = """You are an InSAR coherence analyst examining post-fire recovery.

Read the file at {batch_path}. Format:
ParcelNo|baseline|permit_month|m1:v1|m2:v2|...

where m = months post-fire, v = Wiener-filtered normalized coherence (12-day cadence).
baseline = pre-fire 75th percentile coherence.
permit_month = month the NEW CONSTRUCTION permit was issued (or "none").

For EACH parcel, estimate recovery_llm — the month when coherence recovery begins:

1. Find the post-fire trough (lowest coherence region)
2. Identify where coherence starts a clear, sustained rise after the trough
3. recovery_llm = the month value where the upward trend becomes convincing
   (not first blip — look for sustained inflection)
4. If permit_month is provided, recovery MUST be >= permit_month
   (construction can't recover coherence before the permit is issued)
5. If no clear recovery after the permit date (or ever, if no permit), set null
6. Return an EXACT month value from the series — do not interpolate or round

Write a JSON array to {result_path}:
[{{"ParcelNo": "...", "recovery_llm": 23.1}}, ...]
Process ALL parcels. Use null for no recovery."""


def load_permit_months() -> dict[str, float]:
    """Return {ParcelNo: permit_months_post_fire} for first NEW CONSTRUCTION permit."""
    permits = pd.read_csv(DATA_RAW / "Permits.csv")
    permits["issue_dt"] = pd.to_datetime(
        permits["issue_dt"], format="%m/%d/%Y %I:%M:%S %p", errors="coerce"
    )
    acct = pd.read_csv(DATA_RAW / "Account_Parcels.csv").rename(
        columns={"Parcelno": "ParcelNo"}
    )
    pw = permits.merge(acct, on="strap", how="inner")
    nc = pw[(pw["issue_dt"] > FIRE_DATE) & (pw["permit_category"] == "NEW CONSTRUCTION")]
    first = nc.sort_values("issue_dt").groupby("ParcelNo").first().reset_index()
    first["permit_months"] = (first["issue_dt"] - FIRE_DATE).dt.days / 30.44
    return dict(zip(first["ParcelNo"], first["permit_months"].round(1)))


def prepare():
    """Build compact batch files at full 12-day resolution."""
    rec = pd.read_parquet(RESULTS / "recovery_detection.parquet")
    destroyed = rec[rec["damage_class"] == "Destroyed"]
    parcel_ids = sorted(destroyed["ParcelNo"].unique())
    baselines = dict(zip(destroyed["ParcelNo"], destroyed["pre_baseline"]))
    permit_map = load_permit_months()

    BATCH_DIR.mkdir(parents=True, exist_ok=True)

    lines = []
    skipped = 0
    for pid in parcel_ids:
        ts_file = TS_DIR / f"{pid}.json"
        if not ts_file.exists():
            skipped += 1
            continue
        with open(ts_file) as f:
            ts = json.load(f)

        post = [p for p in ts if p["months_post_fire"] > 0]
        if not post:
            skipped += 1
            continue

        baseline = baselines.get(pid, 0)
        permit_m = permit_map.get(pid)
        permit_str = f"{permit_m:.1f}" if permit_m is not None else "none"

        pairs = "|".join(
            f"{p['months_post_fire']:.2f}:{p['smoothed']:.3f}" for p in post
        )
        lines.append(f"{pid}|{baseline:.3f}|{permit_str}|{pairs}")

    # Split into batches
    header = "ParcelNo|baseline|permit_month|month:smoothed pairs (12-day post-fire)"
    n_batches = 0
    for i in range(0, len(lines), BATCH_SIZE):
        batch = lines[i : i + BATCH_SIZE]
        batch_path = BATCH_DIR / f"b{n_batches}.txt"
        batch_path.write_text(header + "\n" + "\n".join(batch) + "\n")
        n_batches += 1

    print(f"Prepared {len(lines)} parcels in {n_batches} batches ({BATCH_DIR}/)")
    print(f"Skipped {skipped} parcels (no timeseries JSON)")
    print(f"Permit constraint: {sum(1 for p in parcel_ids if p in permit_map)} parcels")
    print(f"No permit (free choice): {sum(1 for p in parcel_ids if p not in permit_map)} parcels")
    print()

    # Print dispatch instructions
    print("--- Dispatch prompt for each batch ---")
    for b in range(n_batches):
        bp = str(BATCH_DIR / f"b{b}.txt")
        rp = str(BATCH_DIR / f"r{b}.json")
        print(f"\nBatch {b}: {bp}")
    print()
    print("Prompt template (substitute paths):")
    print(PROMPT_TEMPLATE.format(
        batch_path="<batch_path>", result_path="<result_path>"
    ))


def merge():
    """Merge all r*.json results into recovery_detection.parquet."""
    results = []
    for rfile in sorted(BATCH_DIR.glob("r*.json")):
        with open(rfile) as f:
            batch = json.load(f)
        results.extend(batch)

    llm_df = pd.DataFrame(results)
    print(f"Loaded {len(llm_df)} LLM results from {len(list(BATCH_DIR.glob('r*.json')))} files")

    # Deduplicate (keep first)
    llm_df = llm_df.drop_duplicates(subset="ParcelNo", keep="first")
    print(f"After dedup: {len(llm_df)}")
    print(f"Non-null recovery_llm: {llm_df['recovery_llm'].notna().sum()}")
    print(f"Unique values: {llm_df['recovery_llm'].nunique()}")

    # Merge into existing parquet
    rec = pd.read_parquet(RESULTS / "recovery_detection.parquet")
    if "recovery_llm" in rec.columns:
        rec = rec.drop(columns=["recovery_llm"])
    rec = rec.merge(llm_df[["ParcelNo", "recovery_llm"]], on="ParcelNo", how="left")

    rec.to_parquet(RESULTS / "recovery_detection.parquet", index=False)
    print(f"\nUpdated {RESULTS / 'recovery_detection.parquet'}")
    print(f"  recovery_llm non-null: {rec['recovery_llm'].notna().sum()} / {len(rec)}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("prepare", "merge"):
        print("Usage: python scripts/llm_recovery.py [prepare|merge]")
        sys.exit(1)

    if sys.argv[1] == "prepare":
        prepare()
    elif sys.argv[1] == "merge":
        merge()
