-- SAR backscatter change statistics per parcel per observation date.
-- Source: pipeline/process/sar.py → data/tabular/sar_zonal_stats.parquet

with source as (
    select * from {{ source('raw', 'sar_zonal_stats') }}
)

select
    parcel_idx,
    observation_date,
    vv_change_db_mean,
    vv_change_db_std,
    vv_pixel_count,
    vh_change_db_mean,
    vh_change_db_std,
    vh_pixel_count
from source
