#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROFILE="${PROFILE:-full}"
WORKERS="${WORKERS:-4}"
CONFIG="experiments/configs/scaled_tanh_instantiation.yaml"
RAW_ROOT="results/raw/scaled_tanh_instantiation"
DERIVED_ROOT="results/derived/scaled_tanh_instantiation/$PROFILE"
SELECTION="$RAW_ROOT/$PROFILE/optimizer_selection.json"

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"

if [[ "$PROFILE" != "smoke" && "$PROFILE" != "full" ]]; then
  printf 'PROFILE must be smoke or full, got %s\n' "$PROFILE" >&2
  exit 2
fi

# Smoke outputs are engineering checks and must not replace paper evidence.
if [[ "$PROFILE" == "full" ]]; then
  CERTIFICATES_FIGURE="paper/figures/scaled_tanh_certificates.pdf"
  REGRET_BOUNDS_FIGURE="paper/figures/scaled_tanh_regret_bounds.pdf"
  COMPUTE_FIGURE="paper/figures/scaled_tanh_compute.pdf"
  TABLE="tables/generated/scaled_tanh_instantiation.tex"
else
  CERTIFICATES_FIGURE="$DERIVED_ROOT/scaled_tanh_certificates.pdf"
  REGRET_BOUNDS_FIGURE="$DERIVED_ROOT/scaled_tanh_regret_bounds.pdf"
  COMPUTE_FIGURE="$DERIVED_ROOT/scaled_tanh_compute.pdf"
  TABLE="$DERIVED_ROOT/scaled_tanh_instantiation.tex"
fi

rm -rf "$RAW_ROOT/$PROFILE" "$DERIVED_ROOT"
mkdir -p "$RAW_ROOT/$PROFILE" "$DERIVED_ROOT"

buck2 run //experiments:run_scaled_tanh_instantiation -- \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --phase tuning \
  --output-root "$RAW_ROOT" \
  --selection "$SELECTION" \
  --workers "$WORKERS"

buck2 run //experiments:run_scaled_tanh_instantiation -- \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --phase evaluation \
  --output-root "$RAW_ROOT" \
  --selection "$SELECTION" \
  --workers "$WORKERS"

buck2 run //experiments:make_scaled_tanh_instantiation_artifacts -- \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --raw-root "$RAW_ROOT" \
  --selection "$SELECTION" \
  --aggregate "$DERIVED_ROOT/aggregate.json" \
  --certificates-figure "$CERTIFICATES_FIGURE" \
  --regret-bounds-figure "$REGRET_BOUNDS_FIGURE" \
  --compute-figure "$COMPUTE_FIGURE" \
  --table "$TABLE"
