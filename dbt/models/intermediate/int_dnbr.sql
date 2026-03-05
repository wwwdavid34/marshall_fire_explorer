-- Burn severity classification from dNBR.
-- dNBR > 0.27 = moderate-high severity (USGS standard thresholds).

with landsat as (
    select * from {{ ref('stg_landsat_indices') }}
)

select
    parcel_idx,
    observation_date,
    dnbr_mean,
    ndvi_mean,
    tir_anomaly_mean,
    swir2_mean,
    case
        when dnbr_mean >= 0.66 then 'high_severity'
        when dnbr_mean >= 0.44 then 'moderate_high_severity'
        when dnbr_mean >= 0.27 then 'moderate_low_severity'
        when dnbr_mean >= 0.1  then 'low_severity'
        else 'unburned'
    end as burn_severity_class
from landsat
