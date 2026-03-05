"""Load Siamese U-Net weights and run damage assessment inference.

Weights source: ml/models/siamese_unet_best.pt (produced by notebook 09)
"""

import logging

logger = logging.getLogger(__name__)


def run_damage_inference() -> None:
    """Load siamese_unet weights, run pixel change detection, aggregate to parcel scores."""
    logger.info("run_damage_inference: not yet implemented — skipping")
