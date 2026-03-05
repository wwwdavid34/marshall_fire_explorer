"""LiDAR processing: LAZ → DEM → DSM → CHM → COG."""

import logging

logger = logging.getLogger(__name__)


def process_lidar() -> None:
    """Process raw LAZ point clouds to elevation model COGs."""
    logger.info("process_lidar: LAZ → DEM → DSM → CHM → COG")
    logger.info("process_lidar: not yet implemented — skipping")
