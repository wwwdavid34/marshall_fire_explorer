"""Write registry.json — the site-level index file.

The registry is the entry point for the frontend: it describes what data
is available, the AOI, observation dates, and URLs for timeline and parcel data.
"""

import json
import logging
from pathlib import Path

from config.settings import AOI, OBSERVATION_DATES, get_config

logger = logging.getLogger(__name__)

RESULTS_DIR = Path("data/results")


def write_registry_json() -> None:
    """Write data/results/registry.json."""
    logger.info("write_registry_json: writing site registry")

    config = get_config()
    base_url = config.data_base_url

    # Count available outputs
    parcels_dir = RESULTS_DIR / "parcels" / "detail"
    parcel_count = len(list(parcels_dir.glob("*.json"))) if parcels_dir.exists() else 0

    layers_dir = RESULTS_DIR / "layers"
    layer_count = len(list(layers_dir.glob("*.tif"))) if layers_dir.exists() else 0

    registry = {
        "site": "Marshall Fire 2021",
        "description": (
            "Satellite-based damage assessment and recovery monitoring "
            "for the Marshall Fire, Superior/Louisville CO"
        ),
        "aoi": {
            "bbox": AOI,
            "center": [
                (AOI[0] + AOI[2]) / 2,  # lon
                (AOI[1] + AOI[3]) / 2,  # lat
            ],
        },
        "observation_dates": OBSERVATION_DATES,
        "fire_date": "2021-12-30",
        "data": {
            "timeline_url": f"{base_url}/results/timeline.json",
            "parcels_index_url": f"{base_url}/results/parcels/index.geojson",
            "parcel_detail_url_template": (
                f"{base_url}/results/parcels/detail/{{parcel_idx}}.json"
            ),
            "parcel_count": parcel_count,
            "layer_count": layer_count,
        },
    }

    dest = RESULTS_DIR / "registry.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w") as f:
        json.dump(registry, f, indent=2)
    logger.info("  wrote %s (%d parcels, %d layers)", dest, parcel_count, layer_count)
