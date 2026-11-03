-- Canonical order fact. Grain: one row per order.
-- Deliberately carries NO money columns: revenue lives only in fct_order_lines,
-- so there is exactly one place an agent can find it.
with orders as (
    select * from {{ ref('stg_tpch__orders') }}
),

customers as (
    select * from {{ ref('stg_tpch__customers') }}
),

geo as (
    select * from {{ ref('int_nation_regions') }}
),

line_counts as (
    select order_key, count(*) as line_count
    from {{ ref('stg_tpch__lineitem') }}
    group by order_key
)

select
    orders.order_key,
    orders.customer_key,
    orders.order_date,
    orders.order_status,
    orders.order_priority,
    customers.market_segment,
    geo.nation_name        as customer_nation,
    geo.region_name        as customer_region,
    line_counts.line_count
from orders
join customers   on orders.customer_key = customers.customer_key
join geo         on customers.nation_key = geo.nation_key
join line_counts on orders.order_key = line_counts.order_key
