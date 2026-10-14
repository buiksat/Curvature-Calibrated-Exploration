#!/usr/bin/env bash
# One-command Linux CPU workflow; dependencies and raw files stay outside Git.
set -euo pipefail
review_repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
review_args=("$@")
review_output=""
while (($#)); do
  case "$1" in
    --output) review_output="${2:?--output requires an external directory}"; shift 2 ;;
    --output=*) review_output="${1#--output=}"; shift ;;
    *) shift ;;
  esac
done
if [[ -z "$review_output" ]]; then
  echo "Usage: bash tools/run_review_experiments.sh --profile pilot|full --output /scratch/cce-run --workers 8" >&2
  exit 2
fi
if command -v python3.12 >/dev/null 2>&1; then
  review_python="$(command -v python3.12)"
elif command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))'; then
  review_python="$(command -v python3)"
else
  echo "Python 3.12 is required. Load the server's Python 3.12 module/environment, then rerun." >&2
  exit 1
fi
review_output="$("$review_python" -c 'from pathlib import Path; import sys; p=Path(sys.argv[1]).expanduser().resolve(); r=Path(sys.argv[2]).resolve(); assert p != r and not p.is_relative_to(r), "--output must be outside checkout"; print(p)' "$review_output" "$review_repo")"
mkdir -p -- "$review_output"
review_venv="$review_output/.venv"
if [[ ! -x "$review_venv/bin/python" ]]; then
  "$review_python" -m venv "$review_venv"
fi
export PYTHONDONTWRITEBYTECODE=1
if ! "$review_venv/bin/python" "$review_repo/tools/check_python_environment.py" >/dev/null 2>&1; then
  "$review_venv/bin/python" -m pip install --disable-pip-version-check --progress-bar off \
    --index-url https://pypi.org/simple --only-binary=:all: --require-hashes \
    -r "$review_repo/experiments/requirements-python312.lock"
fi
cd -- "$review_repo"
exec "$review_venv/bin/python" tools/run_review_experiments.py "${review_args[@]}"
