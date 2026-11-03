# Orders and Customers Tables

## Quick Reference
### Business Context
Customers are businesses in one of five market segments, each based in one nation. An order is
placed by one customer on one date and has 1–7 lines.
### Entity Grain
`fct_orders`: one row per order. `dim_customers`: one row per customer.
### Standard Hygiene Filter
None. Note that about a third of customers have never ordered — keep or drop them deliberately.

## Dimensions
- `order_status`: F = fulfilled, O = open, P = partially fulfilled. All statuses count as orders.
- `order_priority`: 1-URGENT, 2-HIGH, 3-MEDIUM, 4-NOT SPECIFIED, 5-LOW.
- `market_segment`, `customer_region`, `customer_nation` / `region`, `nation`: the customer's.

## Key Tables
### fct_orders
- **Grain:** one row per order · **Scope:** all orders 1992-01-01 to 1998-08-02
- **Usage:** order counts and active customers, dated by `order_date`. Has `line_count`.
- **Not for:** revenue. It has no money columns on purpose — use `fct_order_lines`.

### dim_customers
- **Grain:** one row per customer · **Scope:** every customer, including those who never ordered
- **Usage:** customer base counts, first/last order dates, `lifetime_orders`, `has_ordered`.
- **Join key:** `customer_key`.

## Gotchas
- **"Active customers" ≠ "customers".** Active = placed ≥1 order in the period (metric
  `active_customers`). The customer base (`dim_customers`) includes ~50,000 customers with no orders.
- **Count orders from `fct_orders`, never from `fct_order_lines`** (that counts lines, ~4× too many).
- **Order date vs ship date:** order counts use order date; revenue uses ship date. A "revenue per
  order" figure mixes the two — say so if asked for one.

## Best Practices / Common Query Patterns
- Orders per year: `mf query --metrics order_count --group-by metric_time__year --order metric_time__year`
- Active customers in a year: `mf query --metrics active_customers --where "{{ TimeDimension('metric_time', 'day') }} between '1997-01-01' and '1997-12-31'"`
- Orders for one nation (nation isn't in the orders semantic model, so use SQL):
  `dbt show --inline "select count(*) as orders from {{ ref('fct_orders') }} where customer_nation = 'UNITED KINGDOM' and order_date between date '1995-01-01' and date '1995-12-31'" --quiet`
- Customers who never ordered:
  `dbt show --inline "select count(*) as n from {{ ref('dim_customers') }} where not has_ordered" --quiet`

## Cross-References
- Revenue, discounts, regions and suppliers → `sales.md`
