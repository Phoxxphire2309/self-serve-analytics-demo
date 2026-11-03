# Self-serve analytics demo

A small dbt project on the TPC-H sample data, set up so Claude can answer business questions
accurately. It follows the pattern in Anthropic's "How Anthropic enables self-service data
analytics with Claude": governed models, a semantic layer, skills that route to them, evals,
and CI that keeps the skills in step with the models.

## Layout
- `models/marts/` — governed models (`fct_order_lines`, `fct_orders`, `dim_customers`)
- `models/semantic/` — semantic layer metric definitions (MetricFlow)
- `models/legacy/` — deprecated models, kept for an old dashboard; never use for answers
- `.claude/skills/tpch-warehouse/` — knowledge skill: where answers live, plus `references/`
- `.claude/skills/analytics-runbook/` — process skill: clarify → query → review → report
- `.claude/agents/sql-reviewer.md` — adversarial reviewer subagent
- `evals/` — question/answer evals and the runner

## Answering data questions
Use the `tpch-warehouse` and `analytics-runbook` skills. Run commands from the project root.

## Changing models
Any change under `models/marts/` or `models/semantic/` must update the matching file in
`.claude/skills/tpch-warehouse/` in the same change. CI fails the PR otherwise.
After changing models: `dbt build`, then `python evals/run_evals.py --only <affected ids>`.

## Commands
- Build and test: `dbt build`
- After switching `TPCH_TARGET` or editing YAML: `dbt parse`
- Evals: `python evals/run_evals.py` (see README.md)
