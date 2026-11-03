# Sales Tables

## Quick Reference
### Business Context
Sales are recorded per order line: each order has 1–7 lines, each for one part from one
supplier. Revenue is what we earned after discount and before tax, recognised when the line ships.
### Entity Grain
`fct_order_lines`: one row per order line (`order_key`, `line_number`).
### Standard Hygiene Filter
None needed — the mart is already clean. Do **not** exclude returned lines from revenue.

## Dimensions
- **Customer geography:** `customer_region` (AFRICA, AMERICA, ASIA, EUROPE, MIDDLE EAST),
  `customer_nation` (upper case, e.g. GERMANY, UNITED KINGDOM).
- **Supplier geography:** `supplier_region`, `supplier_nation`. Same values as customer geography,
  different meaning. A European customer can buy from an Asian supplier.
- **Segment:** `market_segment` (AUTOMOBILE, BUILDING, FURNITURE, HOUSEHOLD, MACHINERY) — the
  *customer's* segment.
- **Dates:** `ship_date` (revenue date), `order_date` (when ordered). Lines ship 1–121 days after
  the order, so the same order can land in different years depending on which date you use.

## Key Tables
### fct_order_lines
- **Grain:** one row per order line · **Scope:** all lines, all statuses, returned or not
- **Usage:** revenue = `sum(net_amount)`, dated by `ship_date`. Gross sales = `sum(gross_amount)`.
  Discount given = `sum(gross_amount) - sum(net_amount)`.
- **Join keys:** `customer_key` → `dim_customers`; `order_key` → `fct_orders`.
- **Not for:** counting orders (use `fct_orders`; one order has many lines).

## Gotchas
- **Tax is never revenue.** `tax_amount` exists for completeness only. The old order total
  (`total_price_incl_tax` in staging, `revenue` in `rpt_monthly_sales`) includes tax — never use it.
- **`rpt_monthly_sales` is deprecated** and disagrees with the governed number: about 4% higher in
  full years (it includes tax), and far off in 1992 and 1998 (it is dated by order date). If a user
  quotes a revenue figure that doesn't match, this is the usual reason.
- **Returns:** `is_returned` is only meaningful for lines received up to 1995-06-17. Every later
  line has `return_flag = 'N'`. Don't report return trends past mid-1995, and don't net returns
  off revenue.
- **1998 is partial** (orders stop 1998-08-02). Don't compare 1998 to full years without saying so.
- **Region means customer region** unless the question says otherwise.

## Best Practices / Common Query Patterns
- Revenue by year (semantic layer):
  `mf query --metrics revenue --group-by metric_time__year --order metric_time__year --decimals 2`
- Revenue for one region in one year:
  `mf query --metrics revenue --where "{{ Dimension('order_line__customer_region') }} = 'EUROPE'" --where "{{ TimeDimension('metric_time', 'day') }} between '1996-01-01' and '1996-12-31'" --decimals 2`
- Revenue by supplier region:
  `mf query --metrics revenue --group-by order_line__supplier_region --where "{{ TimeDimension('metric_time', 'day') }} between '1995-01-01' and '1995-12-31'" --decimals 2`
- Discount given: `mf query --metrics gross_sales,revenue --where "{{ TimeDimension('metric_time', 'day') }} between '1997-01-01' and '1997-12-31'" --decimals 2`, then gross_sales − revenue.
- SQL fallback (same definition):
  `dbt show --inline "select sum(net_amount) as revenue from {{ ref('fct_order_lines') }} where ship_date between date '1997-01-01' and date '1997-12-31'" --quiet`
- Growth: query each period separately, then `(current / prior - 1) * 100`.

## Cross-References
- Order counts, active customers, customer base → `customers.md`
