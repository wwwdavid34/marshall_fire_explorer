-- NDVI values pivoted as time series columns per parcel.
-- Tracks vegetation recovery across the 4-year observation arc.

with landsat as (
    select * from {{ ref('stg_landsat_indices') }}
)

select
    parcel_idx,
    max(case when observation_date = '2022-01' then ndvi_mean end) as ndvi_2022_01,
    max(case when observation_date = '2022-06' then ndvi_mean end) as ndvi_2022_06,
    max(case when observation_date = '2023-06' then ndvi_mean end) as ndvi_2023_06,
    max(case when observation_date = '2024-06' then ndvi_mean end) as ndvi_2024_06
from landsat
group by parcel_idx
