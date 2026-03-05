-- Boulder County building characteristics joined to parcel numbers.
-- Source: data/raw/Buildings.csv + data/raw/Account_Parcels.csv

with buildings as (
    select * from {{ source('raw', 'buildings') }}
),

account_parcels as (
    select * from {{ source('raw', 'account_parcels') }}
),

joined as (
    select
        b.strap,
        ap."Parcelno" as parcel_no,
        b.bld_num,
        b.designCodeDscr as design_type,
        b.qualityCodeDscr as quality,
        b.bldgClassDscr as building_class,
        b.builtYear as built_year,
        b."EffectiveYear" as effective_year,
        b."TotalFinishedSF" as total_finished_sf,
        b.mainfloorSF as main_floor_sf,
        b.bsmtSF as basement_sf,
        b.nbrBedRoom as bedrooms,
        b."Stories" as stories,
        b.status_cd
    from buildings b
    left join account_parcels ap on b.strap = ap.strap
)

select * from joined
where status_cd = 'A '  -- Active records only
