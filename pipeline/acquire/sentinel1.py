"""Fetch Sentinel-1 GRD scenes from Planetary Computer (free, no auth required)."""

import logging

from config.settings import AOI, OBSERVATION_DATES

logger = logging.getLogger(__name__)


def acquire_sentinel1() -> None:
    """Download Sentinel-1 GRD VV/VH scenes for all observation dates."""
    logger.info("acquire_sentinel1: fetching %d dates for AOI %s", len(OBSERVATION_DATES), AOI)
    logger.info("acquire_sentinel1: not yet implemented — skipping")
