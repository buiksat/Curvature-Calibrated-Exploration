#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: run_conda_module.sh MODULE [ARGS...]" >&2
  exit 2
fi

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA_ROOT="$SCRIPT_ROOT/conda/buck_integration/toolchains/third-party/_conda_fbpkg"
MODULE="$1"
shift

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$PWD"
export CUBLAS_WORKSPACE_CONFIG=:4096:8
exec "$CONDA_ROOT/bin/python" -m "$MODULE" "$@"
