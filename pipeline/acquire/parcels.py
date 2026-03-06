"""Verify local parcel data and download FEMA damage assessment.

Boulder County parcel/assessor data must be downloaded manually from
https://bouldercounty.gov/property-and-land/assessor/data-download/

The damage-labeled parcel GeoJSON is the primary ground truth source,
manually curated from FEMA assessment + Boulder County records.
"""

import logging
from pathlib import Path

import geopandas as gpd
import requests

from config.settings import AOI

logger = logging.getLogger(__name__)

PARCEL_SHP = Path("data/raw/Parcel/Parcel.shp")
DAMAGE_PARCELS = Path("data/raw/ground_truth/marshall_fire_damage_parcels.geojson")
PERIMETER = Path("data/raw/ground_truth/marshall_fire_perimeter.geojson")

FEMA_DAMAGE_URL = (
    "https://gis.fema.gov/arcgis/rest/services/FEMA/"
    "FEMA_Damage_Assessments/FeatureServer/1/query"
)


def _query_arcgis_geojson(base_url: str, bbox: list[float]) -> gpd.GeoDataFrame:
    """Query an ArcGIS REST endpoint with bbox pagination."""
    west, south, east, north = bbox
    all_features: list[dict] = []
    offset = 0

    while True:
        params = {
            "where": "1=1",
            "geometry": f"{west},{south},{east},{north}",
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "f": "geojson",
            "resultRecordCount": 2000,
            "resultOffset": offset,
        }
        resp = requests.get(base_url, params=params, timeout=120)
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if not features:
            break
        all_features.extend(features)
        logger.info("  fetched %d features (offset=%d)", len(features), offset)
        if len(features) < 2000:
            break
        offset += len(features)

    if not all_features:
        return gpd.GeoDataFrame()
    return gpd.GeoDataFrame.from_features(
        {"type": "FeatureCollection", "features": all_features}, crs="EPSG:4326"
    )


def acquire_parcels() -> None:
    """Verify local data and download FEMA damage assessment if needed."""
    logger.info("acquire_parcels: checking local data")

    if PARCEL_SHP.exists():
        gdf = gpd.read_file(PARCEL_SHP)
        logger.info("  parcel shapefile: %d parcels", len(gdf))
    else:
        logger.warning("  parcel shapefile not found at %s", PARCEL_SHP)

    if DAMAGE_PARCELS.exists():
        gdf = gpd.read_file(DAMAGE_PARCELS)
        labeled = gdf[gdf["Condition"].isin(["Destroyed", "Damaged", "Unaffected"])]
        logger.info("  damage parcels: %d labeled (%d total)", len(labeled), len(gdf))
    else:
        logger.warning("  damage parcels not found at %s", DAMAGE_PARCELS)

    if PERIMETER.exists():
        logger.info("  fire perimeter: found")
    else:
        logger.warning("  fire perimeter not found at %s", PERIMETER)

    # Download FEMA damage if not present
    fema_dest = Path("data/raw/ground_truth/marshall_fire_fema_damage.geojson")
    if not fema_dest.exists():
        logger.info("  downloading FEMA damage assessment")
        gdf = _query_arcgis_geojson(FEMA_DAMAGE_URL, AOI)
        if not gdf.empty:
            fema_dest.parent.mkdir(parents=True, exist_ok=True)
            gdf.to_file(fema_dest, driver="GeoJSON")
            logger.info("  saved %d records to %s", len(gdf), fema_dest)
    else:
        logger.info("  FEMA damage: already downloaded")

    logger.info("acquire_parcels: done")
