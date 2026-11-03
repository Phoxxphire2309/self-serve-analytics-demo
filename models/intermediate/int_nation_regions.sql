-- One row per nation, with its region. Used for both customer and supplier geography.
select
    n.n_nationkey as nation_key,
    n.n_name      as nation_name,
    r.r_name      as region_name
from {{ source('tpch', 'nation') }} n
join {{ source('tpch', 'region') }} r
    on n.n_regionkey = r.r_regionkey
