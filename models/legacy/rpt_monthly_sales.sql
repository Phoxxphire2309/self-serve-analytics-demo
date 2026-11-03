-- DEPRECATED. Kept only because an old dashboard still reads it.
-- Its "revenue" is tax-inclusive and dated by ORDER date,
-- so it does not match the governed revenue metric. Do not use for new analysis.
select
    date_trunc('month', order_date) as order_month,
    count(*)                        as orders,
    sum(total_price_incl_tax)       as revenue
from {{ ref('stg_tpch__orders') }}
group by 1
