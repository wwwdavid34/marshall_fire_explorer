-- Boulder County parcel boundaries with standardized fields.
-- Source: data/raw/Parcel/Parcel.shp (EPSG:2876 — Colorado State Plane North, ft)
-- Columns: OBJECTID, PARCEL_NO, ADDRESS, LOT_NUMBER, BLOCK, SUBCODE,
--          CONDO_UNIT, GIS_SQFT, X_COORD, Y_COORD, geometry

with source as (
    select * from {{ source('raw', 'parcels') }}
)

select
    row_number() over () - 1 as parcel_idx,
    PARCEL_NO as parcel_no,
    ADDRESS as address,
    GIS_SQFT as gis_sqft,
    SUBCODE as subcode,
    geometry
from source
