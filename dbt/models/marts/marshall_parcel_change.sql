-- Marshall Fire parcel-level change mart.
-- One row per parcel × observation date with all sensor signals joined.
-- This is the primary table consumed by the output layer and ML inference.

with sar as (
    select * from {{ ref('int_sar_change') }}
),

dnbr as (
    select * from {{ ref('int_dnbr') }}
),

ndvi_ts as (
    select * from {{ ref('int_ndvi_time_series') }}
),

lidar as (
    select * from {{ ref('stg_lidar_dem') }}
),

parcels as (
    select * from {{ ref('stg_parcels') }}
)

select
    -- Parcel identity
    p.parcel_idx,

    -- SAR signals (per observation date)
    s.observation_date,
    s.vv_change_db_mean,
    s.vh_change_db_mean,
    s.vv_pixel_count,
    s.sar_change_class,
    s.sar_confidence,

    -- Landsat signals (per observation date)
    d.dnbr_mean,
    d.ndvi_mean,
    d.tir_anomaly_mean,
    d.swir2_mean,
    d.burn_severity_class,

    -- NDVI time series (per parcel, pivoted)
    n.ndvi_2022_01,
    n.ndvi_2022_06,
    n.ndvi_2023_06,
    n.ndvi_2024_06,

    -- LiDAR (per parcel)
    l.chm_mean as chm_mean_pre,
    l.dem_mean,
    l.dsm_mean

from parcels p
left join sar s on p.parcel_idx = s.parcel_idx
left join dnbr d on p.parcel_idx = d.parcel_idx
    and s.observation_date = d.observation_date
left join ndvi_ts n on p.parcel_idx = n.parcel_idx
left join lidar l on p.parcel_idx = l.parcel_idx
