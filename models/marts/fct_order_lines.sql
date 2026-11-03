-- Canonical sales fact. Grain: one row per order line.
-- The ONLY governed source for revenue. See .claude/skills/tpch-warehouse/references/sales.md
with lines as (
    select * from {{ ref('stg_tpch__lineitem') }}
),

orders as (
    select * from {{ ref('stg_tpch__orders') }}
),

customers as (
    select * from {{ ref('stg_tpch__customers') }}
),

suppliers as (
    select * from {{ ref('stg_tpch__suppliers') }}
),

geo as (
    select * from {{ ref('int_nation_regions') }}
)

select
    cast(lines.order_key as varchar) || '-' || cast(lines.line_number as varchar) as order_line_id,
    lines.order_key,
    lines.line_number,
    orders.customer_key,
    lines.supplier_key,
    lines.part_key,

    orders.order_date,
    lines.ship_date,
    orders.order_status,
    lines.line_status,
    lines.ship_mode,

    customers.market_segment,
    cust_geo.nation_name                                       as customer_nation,
    cust_geo.region_name                                       as customer_region,
    supp_geo.nation_name                                       as supplier_nation,
    supp_geo.region_name                                       as supplier_region,

    lines.return_flag,
    lines.return_flag = 'R'                                    as is_returned,

    lines.quantity,
    lines.discount_rate,
    lines.tax_rate,
    lines.extended_price                                       as gross_amount,
    lines.extended_price * (1 - lines.discount_rate)           as net_amount,
    lines.extended_price * (1 - lines.discount_rate) * lines.tax_rate as tax_amount

from lines
join orders              on lines.order_key = orders.order_key
join customers           on orders.customer_key = customers.customer_key
join geo as cust_geo     on customers.nation_key = cust_geo.nation_key
join suppliers           on lines.supplier_key = suppliers.supplier_key
join geo as supp_geo     on suppliers.nation_key = supp_geo.nation_key
