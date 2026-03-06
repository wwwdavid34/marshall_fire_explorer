"""Bulk download all OPERA CSLC files for burst T056-118973-IW1.

Skips files already present in data/raw/sentinel1/cslc/.
Uses asf_search with EarthData credentials from .env.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import asf_search as asf

load_dotenv()

BURST_ID = "T056-118973-IW1"
CSLC_DIR = Path("data/raw/sentinel1/cslc")
CSLC_DIR.mkdir(parents=True, exist_ok=True)


def get_existing_dates():
    """Return set of YYYYMMDD strings already downloaded."""
    dates = set()
    for f in CSLC_DIR.glob("OPERA_L2_CSLC-S1_T056-118973-IW1_*.h5"):
        for part in f.stem.split("_"):
            if part.startswith("20") and "T" in part and part.endswith("Z"):
                dates.add(part[:8])
                break
    return dates


def main():
    username = os.environ.get("EARTHDATA_USERNAME")
    password = os.environ.get("EARTHDATA_PASSWORD")
    if not username or not password:
        print("ERROR: Set EARTHDATA_USERNAME and EARTHDATA_PASSWORD in .env")
        sys.exit(1)

    session = asf.ASFSession()
    session.auth_with_creds(username, password)
    print("Authenticated with EarthData")

    # Search for all CSLC on our burst
    print("Searching ASF for CSLC granules...")
    results = asf.search(
        shortName="OPERA_L2_CSLC-S1_V1",
        start="2021-06-01",
        end="2025-12-31",
        intersectsWith="POINT(-105.17 39.95)",
        maxResults=500,
    )

    # Filter to our burst and deduplicate by date
    seen = {}
    for r in results:
        fid = r.properties["fileID"]
        if BURST_ID not in fid:
            continue
        dt = r.properties["startTime"][:10]
        if dt not in seen:
            seen[dt] = r

    all_dates = sorted(seen.keys())
    print(f"Found {len(all_dates)} unique dates ({all_dates[0]} → {all_dates[-1]})")

    existing = get_existing_dates()
    to_download = [(dt, seen[dt]) for dt in all_dates if dt.replace("-", "") not in existing]
    print(f"Already have: {len(all_dates) - len(to_download)}")
    print(f"To download: {len(to_download)} (~{len(to_download) * 255 / 1000:.1f} GB)")

    if not to_download:
        print("Nothing to download!")
        return

    for i, (dt, result) in enumerate(to_download, 1):
        fid = result.properties["fileID"]
        print(f"\n[{i}/{len(to_download)}] {dt}  {fid}")
        try:
            result.download(str(CSLC_DIR), session=session)
            print(f"  OK")
        except Exception as e:
            print(f"  FAILED: {e}")

    print(f"\nDone. Files in {CSLC_DIR}:")
    count = len(list(CSLC_DIR.glob("*.h5")))
    print(f"  {count} HDF5 files")


if __name__ == "__main__":
    main()
