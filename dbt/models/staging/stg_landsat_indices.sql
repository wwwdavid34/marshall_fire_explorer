-- Landsat-derived spectral indices per parcel per observation date.
-- Source: pipeline/process/landsat.py → data/tabular/landsat_zonal_stats.parquet

with source as (
    select * from {{ source('raw', 'landsat_zonal_stats') }}
)

select
    parcel_idx,
    observation_date,
    dnbr_mean,
    dnbr_std,
    ndvi_mean,
    ndvi_std,
    tir_anomaly_mean,
    tir_anomaly_std,
    swir2_mean,
    swir2_std
from source
