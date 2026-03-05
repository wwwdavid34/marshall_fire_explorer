"""Fetch USGS 3DEP LiDAR tiles from The National Map API.

Downloads LAZ point cloud tiles covering the project AOI. Requires an
EarthData token set as EARTHDATA_TOKEN in .env.
"""

import logging
import os
from pathlib import Path

import requests

from config.settings import AOI

logger = logging.getLogger(__name__)

TNM_API_URL = "https://tnmaccess.nationalmap.gov/api/v1/products"
OUT_DIR = Path("data/raw/lidar")


def _search_3dep_products(bbox: list[float]) -> list[dict]:
    """Query TNM API for 3DEP Lidar Point Cloud (LPC) products covering bbox."""
    west, south, east, north = bbox
    params = {
        "datasets": "Lidar Point Cloud (LPC)",
        "bbox": f"{west},{south},{east},{north}",
        "prodFormats": "LAZ",
        "max": 50,
    }
    resp = requests.get(TNM_API_URL, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("items", [])
    logger.info("  TNM API returned %d products", len(items))
    return items


def _download_file(url: str, dest: Path, token: str | None) -> None:
    """Download a file with optional EarthData bearer token."""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers=headers, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
    size_mb = dest.stat().st_size / (1024 * 1024)
    logger.info("  saved %s (%.1f MB)", dest.name, size_mb)


def acquire_lidar() -> None:
    """Download LAZ tiles covering the AOI."""
    logger.info("acquire_lidar: fetching tiles for AOI %s", AOI)

    token = os.getenv("EARTHDATA_TOKEN")
    if not token:
        logger.warning("EARTHDATA_TOKEN not set — some downloads may fail")

    items = _search_3dep_products(AOI)
    if not items:
        logger.warning("  no 3DEP products found for AOI — skipping")
        return

    for item in items:
        title = item.get("title", "unknown")
        urls = item.get("urls", {})
        download_url = urls.get("downloadURL")
        if not download_url:
            logger.warning("  no downloadURL for %s — skipping", title)
            continue

        filename = Path(download_url).name
        dest = OUT_DIR / filename
        if dest.exists():
            logger.info("  %s already exists — skipping", dest)
            continue

        logger.info("  downloading %s", filename)
        _download_file(download_url, dest, token)

    logger.info("acquire_lidar: done")
