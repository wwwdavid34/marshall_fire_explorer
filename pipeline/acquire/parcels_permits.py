"""Acquire Boulder County parcel boundaries, building permits, and FEMA damage data.

NOTE: Parcel vector data (Shapefile) and assessor CSVs are downloaded manually
from https://bouldercounty.gov/property-and-land/assessor/data-download/
and placed in data/raw/. See data/raw/Parcel/ and data/raw/*.csv.

Data sources (all free, no auth):
  - Parcels: Boulder County Assessor Shapefile (data/raw/Parcel/Parcel.shp)
  - Permits: Boulder County Assessor CSV (data/raw/Permits.csv)
  - Account→Parcel map: data/raw/Account_Parcels.csv (strap → Parcelno)
  - Ground truth: FEMA Marshall Fire Final Damage Assessment (ArcGIS REST)
"""

import logging
from pathlib import Path

import geopandas as gpd
import requests

from config.settings import AOI

logger = logging.getLogger(__name__)

# Local paths for manually downloaded Boulder County data
PARCEL_SHP = Path("data/raw/Parcel/Parcel.shp")
PERMITS_CSV = Path("data/raw/Permits.csv")
ACCOUNT_PARCELS_CSV = Path("data/raw/Account_Parcels.csv")
BUILDINGS_CSV = Path("data/raw/Buildings.csv")
VALUES_CSV = Path("data/raw/Values.csv")
SALES_CSV = Path("data/raw/Sales.csv")

# FEMA Remotely Sensed Building Level Damage Assessments (nationwide, Layer 1)
# Filtered by AOI bbox to get Marshall Fire records
FEMA_DAMAGE_URL = (
    "https://gis.fema.gov/arcgis/rest/services/FEMA/"
    "FEMA_Damage_Assessments/FeatureServer/1/query"
)

# Boulder County Assessor data download page
ASSESSOR_DATA_URL = "https://bouldercounty.gov/property-and-land/assessor/data-download/"

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


def check_local_data() -> dict[str, bool]:
    """Check which local data files are present."""
    return {
        "parcel_shp": PARCEL_SHP.exists(),
        "permits_csv": PERMITS_CSV.exists(),
        "account_parcels_csv": ACCOUNT_PARCELS_CSV.exists(),
        "buildings_csv": BUILDINGS_CSV.exists(),
        "values_csv": VALUES_CSV.exists(),
        "sales_csv": SALES_CSV.exists(),
    }


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


def acquire_parcels_permits() -> None:
    """Verify local parcel/permit data and download FEMA damage data."""
    logger.info("acquire_parcels_permits: checking local data and fetching FEMA damage")

    # Check local files
    status = check_local_data()
    if status["parcel_shp"]:
        gdf = gpd.read_file(PARCEL_SHP)
        logger.info("  Parcel shapefile: %d parcels (EPSG:%s)", len(gdf), gdf.crs.to_epsg())
    else:
        logger.warning(
            "  Parcel shapefile not found at %s — download from %s",
            PARCEL_SHP, ASSESSOR_DATA_URL,
        )

    if status["permits_csv"]:
        n = sum(1 for _ in open(PERMITS_CSV)) - 1
        logger.info("  Permits CSV: %d records", n)
    else:
        logger.warning(
            "  Permits CSV not found at %s — download from %s",
            PERMITS_CSV, ASSESSOR_DATA_URL,
        )

    if status["account_parcels_csv"]:
        logger.info("  Account_Parcels.csv found (strap → Parcelno join table)")
    else:
        logger.warning("  Account_Parcels.csv not found — needed to join permits to parcels")

    # FEMA damage is the only thing we download programmatically
    acquire_fema_damage()

    logger.info("acquire_parcels_permits: done")
