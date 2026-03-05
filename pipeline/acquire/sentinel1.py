"""Fetch Sentinel-1 RTC scenes from Planetary Computer (free, no auth required).

Downloads VV and VH polarisation bands as GeoTIFF for each observation date,
clipped to the project AOI.  RTC (Radiometrically Terrain Corrected) products
are geocoded COGs in UTM with proper CRS, unlike raw GRD.
"""

import logging
from pathlib import Path

import planetary_computer
import pystac_client
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from config.settings import AOI, OBSERVATION_DATES

logger = logging.getLogger(__name__)

PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-1-rtc"
BANDS = ["vv", "vh"]
OUT_DIR = Path("data/raw/sentinel1")


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
    """Read a single band from an RTC COG asset, windowed to the AOI bbox."""
    with rasterio.open(asset_href) as src:
        native_bounds = transform_bounds("EPSG:4326", src.crs, *bbox)
        window = from_bounds(*native_bounds, transform=src.transform)
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


def acquire_sentinel1() -> None:
    """Download Sentinel-1 RTC VV/VH scenes for all observation dates."""
    logger.info("acquire_sentinel1: fetching %d dates for AOI %s", len(OBSERVATION_DATES), AOI)

    catalog = pystac_client.Client.open(
        PC_STAC_URL,
        modifier=planetary_computer.sign_inplace,
    )

    for date_str in OBSERVATION_DATES:
        dt_range = _date_range(date_str)
        logger.info("  searching %s for %s", COLLECTION, dt_range)

        search = catalog.search(
            collections=[COLLECTION],
            bbox=AOI,
            datetime=dt_range,
            sortby=[{"field": "datetime", "direction": "desc"}],
            max_items=5,
        )

        items = list(search.items())
        if not items:
            logger.warning("  no scenes found for %s — skipping", date_str)
            continue

        # Pick the first scene (most recent in the month)
        item = items[0]
        scene_date = item.datetime.strftime("%Y-%m-%d")
        logger.info("  selected scene %s from %s", item.id, scene_date)

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

    logger.info("acquire_sentinel1: done")
