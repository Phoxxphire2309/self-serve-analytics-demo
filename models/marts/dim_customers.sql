-- Canonical customer dimension. Grain: one row per customer (including those who never ordered).
with customers as (
    select * from {{ ref('stg_tpch__customers') }}
),

geo as (
    select * from {{ ref('int_nation_regions') }}
),

order_stats as (
    select
        customer_key,
        min(order_date) as first_order_date,
        max(order_date) as last_order_date,
        count(*)        as lifetime_orders
    from {{ ref('stg_tpch__orders') }}
    group by customer_key
)

select
    customers.customer_key,
    customers.customer_name,
    customers.market_segment,
    geo.nation_name                          as nation,
    geo.region_name                          as region,
    customers.account_balance,
    order_stats.first_order_date,
    order_stats.last_order_date,
    coalesce(order_stats.lifetime_orders, 0) as lifetime_orders,
    order_stats.customer_key is not null     as has_ordered
from customers
join geo              on customers.nation_key = geo.nation_key
left join order_stats on customers.customer_key = order_stats.customer_key
