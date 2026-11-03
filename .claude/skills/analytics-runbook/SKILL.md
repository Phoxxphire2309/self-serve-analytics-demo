---
name: analytics-runbook
description: "IF the user wants a number, trend, comparison or breakdown from the company's data — THEN follow this runbook alongside the tpch-warehouse skill. It is the process a senior analyst follows: clarify, find the source, query, get the SQL reviewed, report with provenance. DO NOT use for dbt development or CI work."
metadata:
  version: 1.0.0
  owner: data-team
---

# Analytics runbook

Act as a careful data analyst. Load the `tpch-warehouse` skill for *where* answers live; this
runbook is *how* to produce one.

## 1. Clarify (only what changes the answer)
- Time period, and which date it uses (ship date for revenue, order date for orders/customers).
- Population: which region/segment, and whose region (customer by default).
- If a reasonable default exists in `tpch-warehouse`, use it and state it instead of asking.
  Ask only when two readings would give materially different answers and no default applies.

## 2. Find the source
Semantic layer first. Governed marts via `dbt show` only if no metric covers the question.
Never raw sources or deprecated models.

## 3. Run the query
One command per call, from the project root. Keep the exact command you ran — it goes in the answer.

## 4. Adversarial review (MANDATORY for SQL, recommended for semantic-layer answers)
For any answer that used hand-written SQL, spawn the `sql-reviewer` subagent with: the user's
question, the exact query, and the result. Fix every BLOCKING finding and send it back for
another round. Do not self-certify. If you only used `mf query` with a documented metric, a
review is optional — use it when the question involved a filter or dimension you had to interpret.

## 5. Deliver
- Lead with the answer in one sentence, with the number formatted for a reader
  (e.g. "33.12 billion"; the data has no currency, so don't add one).
- Then the method in two or three lines: metric/table, filters, date basis, assumptions made.
- Separate what the data shows ("revenue fell 0.3%") from interpretation ("this suggests…").
  Don't speculate about causes the data can't show.
- Use safe division and say what the denominator is for any rate.
- End every answer with the provenance footer:

> **Source:** semantic layer `metric_name` | governed table `model_name` · **Freshness:** data to <max date in the data> · **Reviewed:** sql-reviewer ✓ round N | not needed (semantic layer) · **Owner:** data-team

## Reusable patterns
- **Period-over-period growth:** query both periods with the same metric and filters;
  growth % = (current / prior − 1) × 100. Flag partial periods (1998).
- **Mix / share:** metric grouped by the dimension, then each row ÷ total. Check the shares sum to 100%.
- **Top N:** order by the metric descending; report the gap between #1 and #2 when it's under 2%
  (close calls deserve a mention).
