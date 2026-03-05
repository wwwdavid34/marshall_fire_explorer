"""Fetch USGS 3DEP LiDAR tiles from The National Map API (requires EarthData token)."""

import logging

from config.settings import AOI

logger = logging.getLogger(__name__)


def acquire_lidar() -> None:
    """Download LAZ tiles covering the AOI."""
    logger.info("acquire_lidar: fetching tiles for AOI %s", AOI)
    logger.info("acquire_lidar: not yet implemented — skipping")
