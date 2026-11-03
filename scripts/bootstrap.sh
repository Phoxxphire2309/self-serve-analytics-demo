#!/usr/bin/env bash
# One-step local setup (macOS / Linux): Python environment, packages, sample data, dbt build.
#
#   bash scripts/bootstrap.sh
#
# Safe to re-run. Takes about 5 minutes the first time, mostly the package install.
set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

ok_version() {  # dbt and MetricFlow support Python 3.10 to 3.13
  "$1" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)' 2>/dev/null
}

say "Finding a supported Python (3.10 to 3.13)"
PY=""
for candidate in python3.12 python3.13 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && ok_version "$candidate"; then
    PY="$candidate"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "No supported Python found. dbt doesn't run on Python 3.14 or newer yet."
  echo "On a Mac: brew install python@3.12   then run this script again."
  exit 1
fi
echo "Using $PY ($("$PY" --version))"

if [ -x .venv/bin/python ] && ok_version .venv/bin/python; then
  echo "Keeping the existing .venv"
else
  say "Creating .venv"
  rm -rf .venv
  "$PY" -m venv .venv
fi

say "Installing packages (a few minutes the first time)"
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt

say "Generating the TPC-H sample data"
.venv/bin/python scripts/setup_data.py

say "Building and testing the dbt models"
.venv/bin/dbt build

say "Checking the semantic layer: 1997 should read 33116752392.08"
.venv/bin/mf query --metrics revenue --group-by metric_time__year --order metric_time__year --decimals 2

say "Done. Now run:"
echo "  source .venv/bin/activate"
echo "  claude"
