---
name: tpch-warehouse
description: "IF the user asks a business question that needs numbers from the TPC-H sales warehouse (revenue, sales, discounts, orders, customers, market segments, regions, nations, suppliers) — THEN use this skill. DO NOT use it for editing dbt models, CI or pipeline work, or questions with no data component."
metadata:
  version: 1.0.0
  owner: data-team
---

# TPC-H warehouse — where the right answer lives

This skill is the router: it narrows the warehouse down to the few governed places an answer
can come from. The `analytics-runbook` skill covers *how* to run an analysis end to end.

## Running queries

Run every command from the project root, one command per call (no `cd ... &&` chains).
The active warehouse is chosen by the `TPCH_TARGET` environment variable (`dev` = local
DuckDB, `snowflake` = Snowflake). Do not pass `--target`; just run the commands as written.

1. **Semantic layer (always try first):** `mf query ...` (see below)
2. **Governed SQL (fallback):**
   `dbt show --inline "<sql using {{ ref('model') }}>" --limit 200 --quiet`
3. **Neither works:** report the error to the user and stop. Common causes:
   - "database is locked" → another program has `analytics.duckdb` open; ask the user to close it.
   - "metric/table does not exist" → the project needs `dbt parse` (or `dbt build`) after a
     target switch or model change. Say so; don't guess around it.

---

# Semantic layer (REQUIRED first step)

The semantic layer gives the same numbers every other surface gives. Raw SQL via the reference
docs is the fallback, used only after the semantic layer is shown not to cover the question.

| Metric | Means | Time basis |
|---|---|---|
| `revenue` | Net revenue: price after discount, before tax. **The** revenue number. | ship date |
| `gross_sales` | Price before discount. Only for discount analysis. Not revenue. | ship date |
| `order_count` | Distinct orders placed | order date |
| `active_customers` | Distinct customers who placed ≥1 order in the period | order date |

## Required workflow
1. **Discover:** `mf list metrics` and `mf list dimensions --metrics <metric>`
2. **Query:** e.g.
   `mf query --metrics revenue --group-by metric_time__year --order metric_time__year --decimals 2`
3. **Filter:** `--where "{{ Dimension('order_line__customer_region') }} = 'EUROPE'"`, and dates with
   `--where "{{ TimeDimension('metric_time', 'day') }} between '1996-01-01' and '1996-12-31'"` (repeat `--where` to combine filters).
   Don't use `--start-time`/`--end-time`: they return an empty result in this project.
4. **Fallback:** only if no metric fits, or the query errors → governed SQL via `references/*.md`

> **Don't bail early.** These are NOT reasons to skip the semantic layer:
> - "I need a region / segment / nation filter" → use `--where` with `Dimension(...)`
> - "I need a custom date range or a quarter" → a `TimeDimension('metric_time', 'day')` filter, `metric_time__quarter`
> - "I need a join to customers" → customer region, nation and segment are already dimensions
> - "I need a growth rate" → query both periods from the semantic layer and do the arithmetic

## Date windows — decide before you query
- **The data is historical.** Orders run 1992-01-01 → 1998-08-02; shipments 1992-01-02 → 1998-12-01.
  Never anchor on today's date.
- **"Last year" / "this year" / "latest year"** → the latest *complete* calendar year in the data,
  which is **1997** (1998 is partial). State this assumption in the answer.
- **Quarters** are calendar quarters (Q4 1996 = 1996-10-01 to 1996-12-31).
- `metric_time` follows each metric's own time basis automatically (revenue → ship date,
  orders/customers → order date). If you fall back to SQL, use the same basis.

---

# Entity disambiguation (MUST get right)
- **"Revenue" / "sales" / "turnover"** → metric `revenue`. Not `gross_sales`, not
  `total_price_incl_tax`, never `rpt_monthly_sales`.
- **"Region" / "nation"** → the **customer's** region/nation by default. Use `supplier_region` /
  `supplier_nation` only when the question is about where goods were supplied from.
- **"Active customers" in a period** → metric `active_customers`.
- **"Customers" as a base / "how many customers do we have"** → `dim_customers`, which includes
  customers who have never ordered. Ask which they mean if it's unclear.
- **"Orders"** → metric `order_count` (by order date), not order lines.
- **"Discount given" / "cost of discounts"** → `gross_sales − revenue` for the period.

---

# Knowledge base navigation
### Sales, revenue, discounts, regions, suppliers → [references/sales.md](references/sales.md)
- Key tables: `fct_order_lines`
### Orders, customers, segments → [references/customers.md](references/customers.md)
- Key tables: `fct_orders`, `dim_customers`

# Never
- Never query raw sources (`source('tpch', ...)`, `stg_*` views) or `rpt_monthly_sales` (deprecated).
- Never make up columns or values. If unsure, read the reference doc or `models/marts/_marts.yml`.
- Never present a number without saying which source tier it came from (see the runbook's footer).
