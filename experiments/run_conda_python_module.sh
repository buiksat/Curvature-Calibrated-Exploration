#!/usr/bin/env bash
set -euo pipefail

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA_ROOT="$SCRIPT_ROOT/conda/buck_integration/toolchains/third-party/_conda_fbpkg"

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$PWD"
export CUBLAS_WORKSPACE_CONFIG=:4096:8
exec "$CONDA_ROOT/bin/python" -m experiments.run_autodiff_systems "$@"
