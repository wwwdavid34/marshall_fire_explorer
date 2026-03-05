"""Write timeline.json mapping observation dates to available COG layer URLs.

The frontend fetches this once on mount to populate the time slider
and know which raster layers are available for each date.
"""

import json
import logging
from pathlib import Path

from config.settings import OBSERVATION_DATES, get_config

logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed")
RESULTS_DIR = Path("data/results")

# Layer types and their file patterns in data/processed/
LAYER_PATTERNS = {
    "sar_vv_change": ("sar", "vv_change_{date}.cog.tif"),
    "sar_vh_change": ("sar", "vh_change_{date}.cog.tif"),
    "dnbr": ("landsat", "dnbr_{date}.cog.tif"),
    "ndvi": ("landsat", "ndvi_{date}.cog.tif"),
    "tir_anomaly": ("landsat", "tir_anomaly_{date}.cog.tif"),
    "swir2": ("landsat", "swir2_{date}.cog.tif"),
}


def write_timeline_json() -> None:
    """Write data/results/timeline.json with observation dates and COG URLs."""
    logger.info("write_timeline_json: writing timeline index")

    config = get_config()
    base_url = config.data_base_url

    timeline = {
        "observation_dates": OBSERVATION_DATES,
        "pre_fire_date": OBSERVATION_DATES[0],
        "dates": {},
    }

    for date_str in OBSERVATION_DATES[1:]:
        layers = {}
        for layer_name, (subdir, pattern) in LAYER_PATTERNS.items():
            filename = pattern.format(date=date_str)
            local_path = PROCESSED_DIR / subdir / filename
            if local_path.exists():
                layers[layer_name] = f"{base_url}/results/layers/{filename}"

        timeline["dates"][date_str] = {
            "layers": layers,
            "layer_count": len(layers),
        }

    # Copy COGs to results/layers/ for deployment
    layers_dir = RESULTS_DIR / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for date_str in OBSERVATION_DATES[1:]:
        for layer_name, (subdir, pattern) in LAYER_PATTERNS.items():
            filename = pattern.format(date=date_str)
            src = PROCESSED_DIR / subdir / filename
            dst = layers_dir / filename
            if src.exists() and not dst.exists():
                import shutil
                shutil.copy2(src, dst)
                copied += 1

    if copied:
        logger.info("  copied %d COGs to %s", copied, layers_dir)

    dest = RESULTS_DIR / "timeline.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w") as f:
        json.dump(timeline, f, indent=2)
    logger.info("  wrote %s", dest)
