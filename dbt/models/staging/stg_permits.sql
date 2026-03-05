-- Boulder County building permits joined to parcel numbers via Account_Parcels.
-- Source: data/raw/Permits.csv + data/raw/Account_Parcels.csv

with permits as (
    select * from {{ source('raw', 'permits') }}
),

account_parcels as (
    select * from {{ source('raw', 'account_parcels') }}
),

joined as (
    select
        p.strap,
        ap."Parcelno" as parcel_no,
        p.permit_num,
        p.permit_category,
        p.issue_dt,
        p.estimated_value,
        p.description,
        p.issued_by
    from permits p
    left join account_parcels ap on p.strap = ap.strap
)

select * from joined
