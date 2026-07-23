#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROFILE="${PROFILE:-full}"
WORKERS="${WORKERS:-4}"
CONFIG="experiments/configs/gap_dependent_validation.yaml"
RAW_ROOT="results/raw/gap_dependent_validation"
DERIVED_ROOT="results/derived/gap_dependent_validation/$PROFILE"

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"

if [[ "$PROFILE" != "smoke" && "$PROFILE" != "full" ]]; then
  printf 'PROFILE must be smoke or full, got %s\n' "$PROFILE" >&2
  exit 2
fi

if [[ "$PROFILE" == "full" ]]; then
  FIGURE="${FIGURE:-paper/figures/gap_dependent_validation.pdf}"
  TABLE="${TABLE:-tables/generated/gap_dependent_validation.tex}"
else
  FIGURE="${FIGURE:-$DERIVED_ROOT/gap_dependent_validation.pdf}"
  TABLE="${TABLE:-$DERIVED_ROOT/gap_dependent_validation.tex}"
fi

rm -rf "$RAW_ROOT/$PROFILE" "$DERIVED_ROOT"
mkdir -p "$DERIVED_ROOT"

buck2 run //experiments:run_conda_module -- \
  experiments.run_gap_dependent_validation \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --seed-set evaluation \
  --output-root "$RAW_ROOT" \
  --workers "$WORKERS"

buck2 run //experiments:run_conda_module -- \
  experiments.make_gap_dependent_validation_artifacts \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --raw-root "$RAW_ROOT" \
  --aggregate "$DERIVED_ROOT/aggregate.json" \
  --figure "$FIGURE" \
  --table "$TABLE"
