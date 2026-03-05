-- LiDAR elevation model statistics per parcel.
-- Source: pipeline/process/lidar.py → data/tabular/lidar_zonal_stats.parquet

with source as (
    select * from {{ source('raw', 'lidar_zonal_stats') }}
)

select
    parcel_idx,
    tile,
    dem_mean,
    dem_std,
    dem_max,
    dsm_mean,
    dsm_std,
    dsm_max,
    chm_mean,
    chm_std,
    chm_max
from source
