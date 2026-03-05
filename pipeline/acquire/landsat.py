"""Fetch Landsat 8/9 L2 scenes from Planetary Computer (free, no auth required)."""

import logging

from config.settings import AOI, OBSERVATION_DATES

logger = logging.getLogger(__name__)


def acquire_landsat() -> None:
    """Download Landsat L2 scenes for all observation dates."""
    logger.info("acquire_landsat: fetching %d dates for AOI %s", len(OBSERVATION_DATES), AOI)
    logger.info("acquire_landsat: not yet implemented — skipping")
