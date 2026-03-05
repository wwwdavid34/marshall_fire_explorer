"""Load LSTM weights and run rebuild stage monitoring inference.

Weights source: ml/models/fusion_classifier.keras (produced by notebook 11)
"""

import logging

logger = logging.getLogger(__name__)


def run_rebuild_inference() -> None:
    """Load LSTM weights, process VV time series, classify rebuild stages."""
    logger.info("run_rebuild_inference: not yet implemented — skipping")
