-- Net amount (after discount) can never exceed gross amount. Returns failing rows.
select order_line_id, gross_amount, net_amount
from {{ ref('fct_order_lines') }}
where net_amount > gross_amount
