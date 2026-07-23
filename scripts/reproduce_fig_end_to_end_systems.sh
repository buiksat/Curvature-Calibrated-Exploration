#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROFILE="${PROFILE:-full}"
THREADS="${THREADS:-1}"
CPU_AFFINITY="${CPU_AFFINITY:-}"
CONFIG="experiments/configs/end_to_end_systems_benchmark.yaml"
RAW_ROOT="results/raw/end_to_end_systems_benchmark"
DERIVED_ROOT="results/derived/end_to_end_systems_benchmark/$PROFILE"

if [[ "$PROFILE" != "smoke" && "$PROFILE" != "full" ]]; then
  printf 'PROFILE must be smoke or full, got %s\n' "$PROFILE" >&2
  exit 2
fi

export OMP_NUM_THREADS="$THREADS"
export OPENBLAS_NUM_THREADS="$THREADS"
export MKL_NUM_THREADS="$THREADS"
export KMP_AFFINITY="${KMP_AFFINITY:-disabled}"
export CUBLAS_WORKSPACE_CONFIG="${CUBLAS_WORKSPACE_CONFIG:-:4096:8}"

AFFINITY_PREFIX=()
if [[ -n "$CPU_AFFINITY" ]]; then
  if ! command -v taskset >/dev/null 2>&1; then
    printf 'CPU_AFFINITY requires taskset\n' >&2
    exit 2
  fi
  AFFINITY_PREFIX=(taskset --cpu-list "$CPU_AFFINITY")
fi

if [[ "$PROFILE" == "full" ]]; then
  FIGURE="${FIGURE:-paper/figures/end_to_end_systems_benchmark.pdf}"
  TABLE="${TABLE:-tables/generated/end_to_end_systems_benchmark.tex}"
else
  FIGURE="${FIGURE:-$DERIVED_ROOT/end_to_end_systems_benchmark.pdf}"
  TABLE="${TABLE:-$DERIVED_ROOT/end_to_end_systems_benchmark.tex}"
fi

rm -rf "$RAW_ROOT/$PROFILE" "$DERIVED_ROOT"
mkdir -p "$DERIVED_ROOT"

"${AFFINITY_PREFIX[@]}" buck2 run //experiments:run_conda_module -- \
  experiments.run_end_to_end_systems_benchmark \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --seed-set evaluation \
  --output-root "$RAW_ROOT"

buck2 run //experiments:run_conda_module -- \
  experiments.make_end_to_end_systems_artifacts \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --raw-root "$RAW_ROOT" \
  --aggregate "$DERIVED_ROOT/aggregate.json" \
  --figure "$FIGURE" \
  --table "$TABLE"
