"""Offline eval runner for the analytics agent.

Each case is a question with a pinned answer. The runner asks Claude Code the question in a
fresh, non-interactive session from the project root (so it gets this repo's skills, subagent
and permissions), reads the FINAL_ANSWER line, and grades it.

Usage (from the project root):
    python evals/run_evals.py                       # all cases
    python evals/run_evals.py --only rev_1997 orders_1996
    python evals/run_evals.py --domain sales
    python evals/run_evals.py --ablate skills       # same run with the skills turned off
    python evals/run_evals.py --check-expected      # re-derive pinned answers from gold SQL (no Claude)
    python evals/run_evals.py --dry-run             # show what would run

Every run writes evals/results/<run_id>.jsonl with the git SHA, skill versions, model, target,
per-case pass/fail, cost, tokens and wall-clock, so "did that change help?" is a query.
Add --store to also load the rows into the warehouse (local DuckDB target only).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CASES_FILE = ROOT / "evals" / "cases.yaml"
RESULTS_DIR = ROOT / "evals" / "results"
SKILLS_OFF = ROOT / "evals" / "skills_off.json"

ANSWER_INSTRUCTIONS = (
    "\n\nAnswer from this project's data. End your reply with one final line in the form "
    "`FINAL_ANSWER: <value>` where <value> is the unrounded number with no commas, units or currency "
    "(for a percentage, just the number, e.g. 4.25), or the exact category value for a "
    "'which' question."
)


# ---------------------------------------------------------------- helpers

def target() -> str:
    return os.environ.get("TPCH_TARGET", "dev")


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def skill_versions() -> dict:
    versions = {}
    for skill_md in sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        front = text.split("---")[1] if text.startswith("---") else ""
        meta = yaml.safe_load(front) or {}
        versions[skill_md.parent.name] = str((meta.get("metadata") or {}).get("version", "?"))
    return versions


def load_cases(only: list[str] | None, domain: str | None) -> tuple[list[dict], dict]:
    data = yaml.safe_load(CASES_FILE.read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    cases = data["cases"]
    if only:
        unknown = set(only) - {c["id"] for c in cases}
        if unknown:
            sys.exit(f"Unknown case id(s): {', '.join(sorted(unknown))}")
        cases = [c for c in cases if c["id"] in only]
    if domain:
        cases = [c for c in cases if c["domain"] == domain]
    return cases, defaults


NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
SCALE = {"thousand": 1e3, "k": 1e3, "million": 1e6, "m": 1e6, "mn": 1e6,
         "billion": 1e9, "bn": 1e9, "b": 1e9}


def parse_number(raw: str) -> float | None:
    s = raw.replace(",", "").replace("$", "").replace("£", "").replace("€", "").strip().lower()
    m = NUM_RE.search(s)
    if not m:
        return None
    value = float(m.group())
    rest = s[m.end():].strip().rstrip("%").strip()
    word = rest.split()[0] if rest.split() else ""
    return value * SCALE.get(word, 1)


def extract_final_answer(text: str) -> str | None:
    hits = re.findall(r"FINAL_ANSWER:\s*`?([^`\n]+)`?", text or "")
    return hits[-1].strip() if hits else None


def grade(case: dict, defaults: dict, answer: str | None) -> tuple[bool, object]:
    if answer is None:
        return False, None
    if "expected_text" in case:
        got = answer.strip().strip(".").strip("'\"")
        return got.upper() == str(case["expected_text"]).upper(), got
    got = parse_number(answer)
    if got is None:
        return False, answer
    expected = float(case["expected"])
    if case.get("unit") == "percent" and abs(got) < 1 <= abs(expected):
        got *= 100  # answered as a fraction
    if "tolerance_abs" in case:
        return abs(got - expected) <= case["tolerance_abs"], got
    tol = case.get("tolerance_pct", defaults.get("tolerance_pct", 0.05)) / 100
    if expected == 0:
        return abs(got) < 1e-9, got
    return abs(got - expected) / abs(expected) <= tol, got


# ---------------------------------------------------------------- gold SQL

def run_gold_sql(sql: str):
    """Run a case's gold SQL through dbt (so source() resolves on any target)."""
    proc = subprocess.run(
        ["dbt", "show", "--inline", " ".join(sql.split()), "--limit", "1",
         "--output", "json", "--quiet"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout[-800:] + proc.stderr[-800:])
    rows = json.loads(proc.stdout[proc.stdout.index("{"):])["show"]
    return next(iter(rows[0].values()))


def check_expected(cases: list[dict]) -> int:
    print(f"Re-deriving pinned answers from gold SQL on target '{target()}'\n")
    mismatches = 0
    for c in cases:
        try:
            actual = run_gold_sql(c["gold_sql"])
        except RuntimeError as e:
            print(f"  {c['id']:<26} ERROR {e}")
            mismatches += 1
            continue
        pinned = c.get("expected_text", c.get("expected"))
        if pinned is None:
            ok = False
        elif "expected_text" in c:
            ok = str(actual).upper() == str(pinned).upper()
        elif "tolerance_abs" in c:
            ok = abs(float(actual) - float(pinned)) <= c["tolerance_abs"] / 10
        else:  # pins are stored to the cent; allow rounding only
            ok = abs(float(actual) - float(pinned)) <= 0.01
        mismatches += not ok
        shown = round(float(actual), 4) if isinstance(actual, (int, float)) else actual
        print(f"  {c['id']:<26} {'OK ' if ok else 'DIFF'}  pinned={pinned}  gold_sql={shown}")
    print(f"\n{len(cases) - mismatches}/{len(cases)} pinned answers reproduce.")
    return 1 if mismatches else 0


# ---------------------------------------------------------------- agent runs

def allowed_tools() -> str:
    # Claude Code ignores a repo's own allow rules until someone accepts the workspace-trust
    # dialog (always the case in CI or a fresh clone), so pass them explicitly.
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    return ",".join(settings.get("permissions", {}).get("allow", []))


def claude_cmd(prompt: str, args) -> list[str]:
    cmd = [args.claude_bin, "-p", prompt, "--output-format", "json",
           "--allowedTools", allowed_tools()]
    if args.model:
        cmd += ["--model", args.model]
    if args.ablate == "skills":
        cmd += ["--settings", str(SKILLS_OFF)]
    return cmd


def run_case(case: dict, defaults: dict, args, run_meta: dict) -> dict:
    prompt = case["question"] + ANSWER_INSTRUCTIONS
    row = {**run_meta, "case_id": case["id"], "domain": case["domain"],
           "question": case["question"],
           "expected": case.get("expected_text", case.get("expected"))}
    started = time.time()
    try:
        proc = subprocess.run(claude_cmd(prompt, args), cwd=ROOT, capture_output=True,
                              text=True, timeout=args.timeout, encoding="utf-8")
        out = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {}
        text = out.get("result", "") or proc.stdout
        answer = extract_final_answer(text)
        passed, got = grade(case, defaults, answer)
        usage = out.get("usage") or {}
        row.update(
            passed=passed, got=got, raw_answer=answer,
            is_error=bool(out.get("is_error")) or proc.returncode != 0,
            cost_usd=out.get("total_cost_usd"), num_turns=out.get("num_turns"),
            input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
            cache_read_tokens=usage.get("cache_read_input_tokens"),
            session_id=out.get("session_id"), transcript_tail=text[-1500:],
        )
    except subprocess.TimeoutExpired:
        row.update(passed=False, got=None, is_error=True, error=f"timeout after {args.timeout}s")
    row["wall_clock_s"] = round(time.time() - started, 1)
    return row


def summarise(rows: list[dict], threshold: float) -> tuple[str, bool]:
    by_domain: dict[str, list[dict]] = {}
    for r in rows:
        by_domain.setdefault(r["domain"], []).append(r)
    lines = ["| Domain | Passed | Rate | Gate |", "|---|---|---|---|"]
    all_clear = True
    for d, rs in sorted(by_domain.items()):
        rate = sum(r["passed"] for r in rs) / len(rs)
        ok = rate >= threshold
        all_clear &= ok
        lines.append(f"| {d} | {sum(r['passed'] for r in rs)}/{len(rs)} | {rate:.0%} | "
                     f"{'✅' if ok else '❌'} (≥{threshold:.0%}) |")
    total = sum(r["passed"] for r in rows)
    lines.append(f"| **all** | **{total}/{len(rows)}** | **{total / max(1, len(rows)):.0%}** | |")
    lines += ["", "| Case | Result | Expected | Got | Cost $ | Secs |", "|---|---|---|---|---|---|"]
    for r in rows:
        cost = f"{r['cost_usd']:.3f}" if r.get("cost_usd") is not None else ""
        lines.append(f"| {r['case_id']} | {'pass' if r['passed'] else 'FAIL'} | {r['expected']} | "
                     f"{r.get('got')} | {cost} | {r.get('wall_clock_s')} |")
    return "\n".join(lines), all_clear


def store_rows(rows: list[dict]) -> None:
    if target() != "dev":
        print("--store only writes to the local DuckDB target; skipped.")
        return
    import duckdb

    con = duckdb.connect(str(ROOT / "analytics.duckdb"))
    con.execute("create schema if not exists evals")
    con.execute("""create table if not exists evals.eval_results (
        run_id varchar, run_at timestamp, git_sha varchar, model varchar, target varchar,
        ablation varchar, skill_versions varchar, case_id varchar, domain varchar,
        passed boolean, expected varchar, got varchar, cost_usd double, num_turns integer,
        input_tokens bigint, output_tokens bigint, wall_clock_s double)""")
    con.executemany(
        "insert into evals.eval_results values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(r["run_id"], r["run_at"], r["git_sha"], r["model"], r["target"], r["ablation"],
          json.dumps(r["skill_versions"]), r["case_id"], r["domain"], r["passed"],
          str(r["expected"]), str(r.get("got")), r.get("cost_usd"), r.get("num_turns"),
          r.get("input_tokens"), r.get("output_tokens"), r.get("wall_clock_s")) for r in rows])
    con.close()
    print("Stored in analytics.duckdb → evals.eval_results")


# ---------------------------------------------------------------- main

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", nargs="+", help="case ids to run")
    p.add_argument("--domain", help="run one domain only")
    p.add_argument("--ablate", choices=["skills"], help="turn a component off to measure its effect")
    p.add_argument("--model", help="model alias or id passed to claude --model")
    p.add_argument("--workers", type=int, default=1,
                   help="parallel cases (keep 1 on local DuckDB: it allows one writer at a time)")
    p.add_argument("--timeout", type=int, default=900, help="seconds per case")
    p.add_argument("--threshold", type=float, default=0.9, help="per-domain pass rate gate")
    p.add_argument("--check-expected", action="store_true", help="verify pinned answers via gold SQL")
    p.add_argument("--store", action="store_true", help="also load results into the warehouse")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--claude-bin", default=os.environ.get("CLAUDE_BIN", "claude"))
    args = p.parse_args()

    cases, defaults = load_cases(args.only, args.domain)
    if not cases:
        sys.exit("No cases selected.")
    if args.check_expected:
        return check_expected(cases)

    missing = [c["id"] for c in cases if c.get("expected") is None and c.get("expected_text") is None]
    if missing:
        sys.exit(f"Cases without a pinned answer: {missing}. Run --check-expected and pin them.")

    run_meta = {
        "run_id": dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6],
        "run_at": dt.datetime.now().isoformat(timespec="seconds"),
        "git_sha": git_sha(), "model": args.model or "default", "target": target(),
        "ablation": args.ablate or "none", "skill_versions": skill_versions(),
    }
    print(f"Run {run_meta['run_id']} · {len(cases)} cases · target={run_meta['target']} · "
          f"ablation={run_meta['ablation']} · skills={run_meta['skill_versions']}")
    if args.dry_run:
        for c in cases:
            print(" ", " ".join(claude_cmd(c["question"] + " …", args)[:3]), "…")
        return 0
    if not shutil.which(args.claude_bin):
        sys.exit(f"'{args.claude_bin}' not found on PATH. Install Claude Code first.")

    rows: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_case, c, defaults, args, run_meta): c for c in cases}
        for fut in cf.as_completed(futures):
            r = fut.result()
            rows.append(r)
            print(f"  {'pass' if r['passed'] else 'FAIL'}  {r['case_id']:<26} "
                  f"expected={r['expected']} got={r.get('got')} ({r.get('wall_clock_s')}s)")
    order = {c["id"]: i for i, c in enumerate(cases)}
    rows.sort(key=lambda r: order[r["case_id"]])

    RESULTS_DIR.mkdir(exist_ok=True)
    out_file = RESULTS_DIR / f"{run_meta['run_id']}.jsonl"
    with out_file.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")

    report, all_clear = summarise(rows, args.threshold)
    print("\n" + report + f"\n\nResults: {out_file.relative_to(ROOT)}")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"## Analytics agent evals ({run_meta['ablation']})\n\n{report}\n")
    if args.store:
        store_rows(rows)
    return 0 if all_clear else 1


if __name__ == "__main__":
    sys.exit(main())
