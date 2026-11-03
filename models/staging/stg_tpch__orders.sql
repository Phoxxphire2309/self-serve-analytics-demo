select
    o_orderkey      as order_key,
    o_custkey       as customer_key,
    o_orderstatus   as order_status,
    o_totalprice    as total_price_incl_tax,
    o_orderdate     as order_date,
    o_orderpriority as order_priority,
    o_clerk         as clerk
from {{ source('tpch', 'orders') }}
