-- SAR change classification per parcel per observation date.
-- Negative VV change = backscatter loss = structure likely absent.

with sar as (
    select * from {{ ref('stg_sar_backscatter') }}
)

select
    parcel_idx,
    observation_date,
    vv_change_db_mean,
    vh_change_db_mean,
    vv_pixel_count,
    case
        when vv_change_db_mean > -2.0 then 'minimal_change'
        when vv_change_db_mean between -4.0 and -2.0 then 'moderate_loss'
        when vv_change_db_mean < -4.0 then 'severe_loss'
        else 'unknown'
    end as sar_change_class,
    case
        when vv_pixel_count >= 6 then 'high'
        when vv_pixel_count >= 4 then 'medium'
        else 'low'
    end as sar_confidence
from sar
