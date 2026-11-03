select
    s_suppkey   as supplier_key,
    s_name      as supplier_name,
    s_nationkey as nation_key
from {{ source('tpch', 'supplier') }}
