-- Boulder County property values joined to parcel numbers.
-- Source: data/raw/Values.csv + data/raw/Account_Parcels.csv

with vals as (
    select * from {{ source('raw', 'values') }}
),

account_parcels as (
    select * from {{ source('raw', 'account_parcels') }}
),

joined as (
    select
        v.strap,
        ap."Parcelno" as parcel_no,
        v.tax_yr,
        v.bldAcutalVal as building_actual_value,
        v."LandAcutalVal" as land_actual_value,
        v.totalActualVal as total_actual_value,
        v.totalAssessedVal as total_assessed_value,
        v.status_cd
    from vals v
    left join account_parcels ap on v.strap = ap.strap
)

select * from joined
where status_cd = 'A '  -- Active records only
