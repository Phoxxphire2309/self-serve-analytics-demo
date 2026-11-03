"""Fail a PR that changes a governed model without updating the skill docs that describe it.

    python scripts/check_skill_drift.py origin/main

The article's lesson: skill docs describe a data model that changes constantly, so they rot
within weeks unless the PR that changes a model also updates the doc. This check enforces that.

Rules:
- A change to a governed model's SQL (models/marts/*.sql) must come with a change to at least
  one skill file that mentions that model by name.
- A change to governed YAML (models/marts/*.yml, models/semantic/*.yml) must come with a change
  to at least one file under .claude/skills/.
- Escape hatch: set SKIP_SKILL_CHECK=true (the workflow does this when the PR carries the
  `no-skill-change` label) for changes that genuinely don't affect meaning, e.g. a refactor.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOVERNED_SQL = ("models/marts/",)
GOVERNED_YAML = ("models/marts/", "models/semantic/")
SKILLS_DIR = ".claude/skills/"


def changed_files(base: str) -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def skill_files_mentioning(model: str) -> list[str]:
    hits = []
    for f in (ROOT / SKILLS_DIR).rglob("*.md"):
        if model in f.read_text(encoding="utf-8"):
            hits.append(f.relative_to(ROOT).as_posix())
    return sorted(hits)


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BASE_REF", "origin/main")
    files = changed_files(base)
    skill_changes = {f for f in files if f.startswith(SKILLS_DIR)}
    problems: list[str] = []

    for f in files:
        path = Path(f)
        if f.startswith(GOVERNED_SQL) and path.suffix == ".sql":
            model = path.stem
            docs = skill_files_mentioning(model)
            if not docs:
                problems.append(f"`{f}`: no skill file mentions `{model}` yet. Add it to the "
                                f"tpch-warehouse skill or a reference doc.")
            elif not skill_changes.intersection(docs):
                problems.append(f"`{f}` changed, but none of the docs that describe `{model}` did: "
                                + ", ".join(f"`{d}`" for d in docs))
        elif f.startswith(GOVERNED_YAML) and path.suffix in (".yml", ".yaml") and not skill_changes:
            problems.append(f"`{f}` changed, but nothing under `{SKILLS_DIR}` did.")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not problems:
        msg = "✅ Skill docs are in step with the governed models in this PR."
        print(msg)
        if summary:
            Path(summary).open("a", encoding="utf-8").write(msg + "\n")
        return 0

    report = ("❌ Governed models changed without their skill docs.\n\n"
              + "\n".join(f"- {p}" for p in problems)
              + "\n\nUpdate the docs in this PR so Claude's answers stay right, or add the "
                "`no-skill-change` label if the change doesn't affect meaning.\n")
    print(report)
    if summary:
        Path(summary).open("a", encoding="utf-8").write(report)
    if os.environ.get("SKIP_SKILL_CHECK", "").lower() == "true":
        print("SKIP_SKILL_CHECK is set (no-skill-change label) — not failing.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
