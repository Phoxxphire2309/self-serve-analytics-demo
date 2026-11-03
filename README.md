# Self-serve analytics with Claude — working demo

A small, complete implementation of the approach in Anthropic's article
[How Anthropic enables self-service data analytics with Claude](https://claude.com/resources/articles/how-anthropic-enables-self-service-data-analytics-with-claude),
built on the public TPC-H sample data so anyone can run it.

The article's argument in one line: **analytics accuracy is a context problem, not a SQL problem.**
If Claude can map "revenue" to the one right table, column and filter, the SQL is easy. Each
folder in this repo exists to stop one of the three ways that mapping goes wrong:

| Failure mode | What stops it here |
|---|---|
| **Ambiguity** — many plausible tables for one concept | Three governed marts and a semantic layer (`models/marts`, `models/semantic`); the near-duplicate is marked deprecated (`models/legacy`) |
| **Retrieval** — the answer is documented but Claude doesn't find it | A router skill that points straight at a few curated reference docs (`.claude/skills/tpch-warehouse`) and a runbook skill for the process (`.claude/skills/analytics-runbook`) |
| **Staleness** — docs drift as models change | Skill docs live in the same repo as the models; CI fails a PR that changes a model without its doc (`.github/workflows/skill-drift.yml`) |
| **Knowing whether any of it works** | Question/answer evals with pinned answers, a runner that records every run, and an ablation switch (`evals/`) |

Plus the online safeguards: an adversarial `sql-reviewer` subagent (`.claude/agents`) and a
provenance footer on every answer (source tier, freshness, reviewer, owner).

---

## Set up (about 5 minutes)

Needs Python 3.10+ and [Claude Code](https://code.claude.com/docs/en/setup).

```bash
git clone <this repo> && cd self-serve-analytics-demo
python -m venv .venv
source .venv/bin/activate            # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

python scripts/setup_data.py         # generates TPC-H data locally (~10 s, ~350 MB)
dbt build                            # builds and tests every model (~20 s)
mf query --metrics revenue --group-by metric_time__year --order metric_time__year --decimals 2
```

dbt Core and MetricFlow are free and open source; no dbt Cloud account is needed. The default
target is a local DuckDB file, so nothing here touches a real warehouse.

Then open Claude Code in the folder and ask a question:

```bash
claude
> What was revenue from European customers in 1996?
```

The first time, accept the workspace-trust prompt so the project's permission rules load.

## Run it on Snowflake instead

The same project runs against Snowflake's built-in sample share and builds into a schema of yours.

```bash
export SNOWFLAKE_ACCOUNT=<org-account>   SNOWFLAKE_USER=<you@company.com>
export SNOWFLAKE_ROLE=<role>             SNOWFLAKE_WAREHOUSE=<wh>
export SNOWFLAKE_DATABASE=<db you can create schemas in>
export SNOWFLAKE_SCHEMA=TPCH_DEMO
export TPCH_TARGET=snowflake             # dbt AND MetricFlow follow this
dbt build                                # signs in through your browser (SSO)
```

PowerShell: `$env:TPCH_TARGET = "snowflake"` and so on. If your account has no
`SNOWFLAKE_SAMPLE_DATA` database, an admin can add it with
`create database SNOWFLAKE_SAMPLE_DATA from share SFC_SAMPLES.SAMPLE_DATA;`.
After switching target, always run `dbt build` (or at least `dbt parse`) first: MetricFlow
reads the last compiled manifest and will otherwise query the old target's tables.

## Evals

```bash
python evals/run_evals.py --check-expected          # pinned answers still reproduce (no Claude, free)
python evals/run_evals.py                           # all 13 questions through Claude Code
python evals/run_evals.py --ablate skills           # the same with the skills switched off
python evals/run_evals.py --only rev_1997 orders_1996
python evals/run_evals.py --store                   # also load results into the warehouse
```

Each case is pinned to a value computed from the **raw** tables, so a bug in the marts shows up
as a failure too. Every run writes `evals/results/<run_id>.jsonl` with git SHA, skill versions,
model, per-case pass/fail, cost, tokens and time. With `--store` the rows land in
`evals.eval_results`, so "did that change help?" becomes a query. The run exits non-zero if any
domain falls below the 90% gate (`--threshold`).

Keep evaluation tolerance tighter than the gap between right and wrong answers: TPC-H is so
uniform that revenue by order date is only 0.2% off revenue by ship date. The default is 0.05%.

## How we work

Branch, pull request, review, merge — never straight to `main`. The full loop, naming, commit
style, review checklist and what to do when things go wrong are in [CONTRIBUTING.md](CONTRIBUTING.md).

## CI (GitHub Actions)

| Workflow | When | What |
|---|---|---|
| `dbt-ci.yml` | every PR and push to main | build + test on DuckDB, validate the semantic layer, check pinned eval answers |
| `skill-drift.yml` | every PR | fails if a governed model or metric changed and the skill docs that describe it didn't (`no-skill-change` label overrides) |
| `evals.yml` | PRs touching models/skills/evals, or on demand | runs the evals through Claude Code; needs an `ANTHROPIC_API_KEY` repository secret |

## Layout

```
models/staging/        raw TPC-H, renamed (agents never query these)
models/marts/          governed: fct_order_lines, fct_orders, dim_customers (+ tests, owners, grain)
models/semantic/       metric definitions: revenue, gross_sales, order_count, active_customers
models/legacy/         rpt_monthly_sales — deprecated near-duplicate, deliberately a trap
.claude/skills/tpch-warehouse/     knowledge skill (router) + references/sales.md, customers.md
.claude/skills/analytics-runbook/  process skill: clarify → query → review → report
.claude/agents/sql-reviewer.md     adversarial reviewer subagent
.claude/settings.json              lets Claude run dbt show / mf query without prompting
evals/                             cases.yaml, run_evals.py, skills_off.json (ablation)
scripts/                           setup_data.py, check_skill_drift.py
```

## Troubleshooting

- **"Could not set lock on file analytics.duckdb"** — something else (DBeaver, a Python shell)
  has the file open. Close it. DuckDB allows one writer at a time, which is also why evals run
  one at a time locally (`--workers` > 1 is fine on Snowflake).
- **dbt complains about a metric or model that no longer exists** — stale partial parse;
  run `dbt parse --no-partial-parse`.
- **`mf query` returns nothing with `--start-time/--end-time`** — use a
  `TimeDimension('metric_time', 'day')` filter instead, as the skill docs do.
- **Claude asks permission for every `dbt show`** — accept the workspace-trust prompt once,
  or start Claude Code from the project root.
