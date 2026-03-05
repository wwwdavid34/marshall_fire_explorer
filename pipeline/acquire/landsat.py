"""Fetch Landsat 8/9 L2 scenes from Planetary Computer (free, no auth required).

Downloads spectral bands needed for burn severity and recovery analysis:
  - SR_B4 (Red), SR_B5 (NIR) → NDVI
  - SR_B7 (SWIR2) → dNBR, burn scar detection
  - ST_B10 (TIR) → thermal anomaly
"""

import logging
from pathlib import Path

import planetary_computer
import pystac_client
import rasterio
from rasterio.windows import from_bounds

from config.settings import AOI, OBSERVATION_DATES

logger = logging.getLogger(__name__)

PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "landsat-c2-l2"
# Bands for damage/recovery: Red, NIR, SWIR2, TIR
BANDS = ["red", "nir08", "swir22", "lwir11"]
MAX_CLOUD_COVER = 10
OUT_DIR = Path("data/raw/landsat")


def _date_range(year_month: str) -> str:
    """Convert '2022-01' to a STAC datetime range covering that month."""
    year, month = year_month.split("-")
    month_int = int(month)
    if month_int == 12:
        end = f"{int(year) + 1}-01-01"
    else:
        end = f"{year}-{month_int + 1:02d}-01"
    return f"{year_month}-01/{end}"


def _download_band(asset_href: str, bbox: list[float], dest: Path) -> None:
    """Read a single band from a COG asset, windowed to the AOI bbox."""
    with rasterio.open(asset_href) as src:
        window = from_bounds(*bbox, transform=src.transform)
        data = src.read(1, window=window)
        profile = src.profile.copy()
        profile.update(
            width=window.width,
            height=window.height,
            transform=rasterio.windows.transform(window, src.transform),
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(dest, "w", **profile) as dst:
        dst.write(data, 1)
    logger.info("  saved %s (%d x %d)", dest.name, profile["width"], profile["height"])


def acquire_landsat() -> None:
    """Download Landsat L2 scenes for all observation dates."""
    logger.info("acquire_landsat: fetching %d dates for AOI %s", len(OBSERVATION_DATES), AOI)

    catalog = pystac_client.Client.open(
        PC_STAC_URL,
        modifier=planetary_computer.sign_inplace,
    )

    for date_str in OBSERVATION_DATES:
        dt_range = _date_range(date_str)
        logger.info("  searching %s for %s (cloud < %d%%)", COLLECTION, dt_range, MAX_CLOUD_COVER)

        search = catalog.search(
            collections=[COLLECTION],
            bbox=AOI,
            datetime=dt_range,
            query={"eo:cloud_cover": {"lt": MAX_CLOUD_COVER}},
            sortby=[{"field": "properties.eo:cloud_cover", "direction": "asc"}],
            max_items=5,
        )

        items = list(search.items())
        if not items:
            logger.warning(
                "  no scenes found for %s (cloud < %d%%) — skipping",
                date_str, MAX_CLOUD_COVER,
            )
            continue

        # Pick the least cloudy scene
        item = items[0]
        cloud = item.properties.get("eo:cloud_cover", "?")
        scene_date = item.datetime.strftime("%Y-%m-%d")
        logger.info("  selected scene %s from %s (cloud=%.1f%%)", item.id, scene_date, cloud)

        for band in BANDS:
            if band not in item.assets:
                logger.warning("  band %s not in assets — skipping", band)
                continue
            href = item.assets[band].href
            dest = OUT_DIR / date_str / f"{band}_{scene_date}.tif"
            if dest.exists():
                logger.info("  %s already exists — skipping", dest)
                continue
            _download_band(href, AOI, dest)

    logger.info("acquire_landsat: done")
