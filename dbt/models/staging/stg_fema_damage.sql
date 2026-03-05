-- FEMA Marshall Fire damage assessment records.
-- Source: data/raw/ground_truth/marshall_fire_fema_damage.geojson

with source as (
    select * from {{ source('raw', 'fema_damage') }}
)

select * from source
