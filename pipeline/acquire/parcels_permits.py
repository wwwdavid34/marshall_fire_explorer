"""Download Boulder County parcel boundaries, building permits, and FEMA damage data.

Data sources (all free, no auth):
  - Parcels: Colorado GIS MapServer Layer 3 (Boulder County)
  - Permits: Boulder County Assessor data download
  - Ground truth: FEMA Marshall Fire Final Damage Assessment
"""

import logging
from pathlib import Path

import geopandas as gpd
import requests

from config.settings import AOI

logger = logging.getLogger(__name__)

# Colorado statewide parcel service — Layer 3 = Boulder County
PARCELS_BASE_URL = (
    "https://gis.colorado.gov/public/rest/services/"
    "Parcels/Public_Parcel_Map_Services/MapServer/3/query"
)

# FEMA Remotely Sensed Building Level Damage Assessments (nationwide, Layer 1)
# Filtered by AOI bbox to get Marshall Fire records
FEMA_DAMAGE_URL = (
    "https://gis.fema.gov/arcgis/rest/services/FEMA/"
    "FEMA_Damage_Assessments/FeatureServer/1/query"
)

# Boulder County Assessor data download (CSV)
ASSESSOR_DATA_URL = "https://bouldercounty.gov/property-and-land/assessor/data-download/"

OUT_PARCELS = Path("data/raw/parcels")
OUT_PERMITS = Path("data/raw/permits")
OUT_GROUND_TRUTH = Path("data/raw/ground_truth")

MAX_RECORDS_PER_PAGE = 2000


def _query_arcgis_geojson(
    base_url: str, bbox: list[float], extra_params: dict | None = None,
) -> gpd.GeoDataFrame:
    """Query an ArcGIS REST endpoint with bbox, paginating to get all features."""
    west, south, east, north = bbox
    all_features = []
    offset = 0

    while True:
        params = {
            "where": "1=1",
            "geometry": f"{west},{south},{east},{north}",
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "f": "geojson",
            "resultRecordCount": MAX_RECORDS_PER_PAGE,
            "resultOffset": offset,
        }
        if extra_params:
            params.update(extra_params)

        resp = requests.get(base_url, params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            break

        all_features.extend(features)
        logger.info("  fetched %d features (offset=%d)", len(features), offset)

        if len(features) < MAX_RECORDS_PER_PAGE:
            break
        offset += len(features)

    if not all_features:
        return gpd.GeoDataFrame()

    geojson = {"type": "FeatureCollection", "features": all_features}
    return gpd.GeoDataFrame.from_features(geojson, crs="EPSG:4326")


def acquire_parcels(bbox: list[float] | None = None) -> Path | None:
    """Download Boulder County parcel boundaries as GeoJSON."""
    bbox = bbox or AOI
    dest = OUT_PARCELS / "boulder_county_parcels.geojson"
    if dest.exists():
        logger.info("  %s already exists — skipping", dest)
        return dest

    logger.info("  querying Colorado GIS for parcels in AOI")
    gdf = _query_arcgis_geojson(PARCELS_BASE_URL, bbox)
    if gdf.empty:
        logger.warning("  no parcels returned — check AOI or endpoint")
        return None

    dest.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(dest, driver="GeoJSON")
    logger.info("  saved %d parcels to %s", len(gdf), dest)
    return dest


def acquire_fema_damage(bbox: list[float] | None = None) -> Path | None:
    """Download FEMA Marshall Fire damage assessment as GeoJSON."""
    bbox = bbox or AOI
    dest = OUT_GROUND_TRUTH / "marshall_fire_fema_damage.geojson"
    if dest.exists():
        logger.info("  %s already exists — skipping", dest)
        return dest

    logger.info("  querying FEMA damage assessment for AOI")
    gdf = _query_arcgis_geojson(FEMA_DAMAGE_URL, bbox)
    if gdf.empty:
        logger.warning("  no FEMA damage records returned — check AOI or endpoint")
        return None

    dest.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(dest, driver="GeoJSON")
    logger.info("  saved %d damage records to %s", len(gdf), dest)
    return dest


def acquire_permits() -> Path | None:
    """Download Boulder County building permits CSV.

    Boulder County publishes assessor data at a known download page.
    This function fetches the permits dataset. If the direct CSV URL
    changes, update PERMITS_CSV_URL.
    """
    dest = OUT_PERMITS / "boulder_county_permits.csv"
    if dest.exists():
        logger.info("  %s already exists — skipping", dest)
        return dest

    # Boulder County publishes permit data through their open data portal.
    # The exact CSV URL may change; log instructions if download fails.
    logger.warning(
        "  Automated permit download not yet available. "
        "Please download manually from: %s "
        "and save to %s",
        ASSESSOR_DATA_URL,
        dest,
    )
    return None


def acquire_parcels_permits() -> None:
    """Download parcel GeoJSON, permits CSV, and FEMA damage data."""
    logger.info("acquire_parcels_permits: downloading parcel boundaries, permits, and ground truth")

    acquire_parcels()
    acquire_fema_damage()
    acquire_permits()

    logger.info("acquire_parcels_permits: done")
