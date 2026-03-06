"""Download OPERA CSLC (Coregistered Single Look Complex) from ASF.

OPERA L2 CSLC products are derived from Sentinel-1 IW SLC and provide
coregistered, burst-level complex radar data needed for InSAR coherence
computation.  We download all available dates for a single burst covering
the Marshall Fire AOI.

Data source: Alaska Satellite Facility (ASF) — requires EarthData credentials.
"""

import logging
import os
from pathlib import Path

import asf_search as asf

from config.settings import AOI

logger = logging.getLogger(__name__)

BURST_ID = "T056-118973-IW1"
OUT_DIR = Path("data/raw/sentinel1/cslc")


def _get_existing_dates(out_dir: Path) -> set[str]:
    """Return set of YYYYMMDD strings already downloaded."""
    dates = set()
    for f in out_dir.glob(f"OPERA_L2_CSLC-S1_{BURST_ID}_*.h5"):
        for part in f.stem.split("_"):
            if part.startswith("20") and "T" in part and part.endswith("Z"):
                dates.add(part[:8])
                break
    return dates


def acquire_sentinel1() -> None:
    """Download all OPERA CSLC files for the project burst."""
    logger.info("acquire_sentinel1: downloading CSLC for burst %s", BURST_ID)

    username = os.environ.get("EARTHDATA_USERNAME")
    password = os.environ.get("EARTHDATA_PASSWORD")
    if not username or not password:
        logger.error("Set EARTHDATA_USERNAME and EARTHDATA_PASSWORD in .env")
        return

    session = asf.ASFSession()
    session.auth_with_creds(username, password)
    logger.info("  authenticated with EarthData")

    # Search for all CSLC on our burst
    center_lon = (AOI[0] + AOI[2]) / 2
    center_lat = (AOI[1] + AOI[3]) / 2
    results = asf.search(
        shortName="OPERA_L2_CSLC-S1_V1",
        start="2021-06-01",
        end="2025-12-31",
        intersectsWith=f"POINT({center_lon} {center_lat})",
        maxResults=500,
    )

    # Filter to our burst and deduplicate by date
    seen: dict[str, asf.ASFProduct] = {}
    for r in results:
        fid = r.properties["fileID"]
        if BURST_ID not in fid:
            continue
        dt = r.properties["startTime"][:10]
        if dt not in seen:
            seen[dt] = r

    all_dates = sorted(seen.keys())
    logger.info("  found %d unique dates (%s → %s)", len(all_dates), all_dates[0], all_dates[-1])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = _get_existing_dates(OUT_DIR)
    to_download = [(dt, seen[dt]) for dt in all_dates if dt.replace("-", "") not in existing]
    logger.info("  already have: %d, to download: %d", len(all_dates) - len(to_download), len(to_download))

    for i, (dt, result) in enumerate(to_download, 1):
        fid = result.properties["fileID"]
        logger.info("  [%d/%d] %s  %s", i, len(to_download), dt, fid)
        try:
            result.download(str(OUT_DIR), session=session)
        except Exception as e:
            logger.error("  FAILED: %s", e)

    count = len(list(OUT_DIR.glob("*.h5")))
    logger.info("acquire_sentinel1: done — %d HDF5 files in %s", count, OUT_DIR)
