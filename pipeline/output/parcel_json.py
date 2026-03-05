"""Write per-parcel detail JSON files from the dbt mart."""

import logging

logger = logging.getLogger(__name__)


def write_parcel_json() -> None:
    """Write data/results/parcels/detail/{parcel_id}.json for each parcel."""
    logger.info("write_parcel_json: mart → detail JSON files")
    logger.info("write_parcel_json: not yet implemented — skipping")
