"""Download Boulder County parcel boundaries and building permits (free, no auth)."""

import logging

logger = logging.getLogger(__name__)


def acquire_parcels_permits() -> None:
    """Download parcel GeoJSON and permits CSV from Boulder County open data."""
    logger.info("acquire_parcels_permits: downloading parcel boundaries and permits")
    logger.info("acquire_parcels_permits: not yet implemented — skipping")
