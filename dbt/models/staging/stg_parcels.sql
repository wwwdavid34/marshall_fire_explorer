-- Boulder County parcel boundaries with standardized fields.
-- Source: data/raw/parcels/boulder_county_parcels.geojson

with source as (
    select * from {{ source('raw', 'parcels') }}
)

select
    row_number() over () - 1 as parcel_idx,
    *
from source
