"""SAR processing: GRD → sigma0 → terrain correction → backscatter change → COG."""

import logging

logger = logging.getLogger(__name__)


def process_sar() -> None:
    """Process raw Sentinel-1 GRD to calibrated backscatter change COGs."""
    logger.info("process_sar: GRD → sigma0 → terrain correction → change → COG")
    logger.info("process_sar: not yet implemented — skipping")
