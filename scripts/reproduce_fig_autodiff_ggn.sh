#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROFILE="${PROFILE:-full}"
CONFIG="experiments/configs/autodiff_ggn_benchmark.yaml"
RAW_ROOT="results/raw/autodiff_ggn_benchmark"
DERIVED_ROOT="results/derived/autodiff_ggn_benchmark/$PROFILE"

if [[ "$PROFILE" != "smoke" && "$PROFILE" != "full" ]]; then
  printf 'PROFILE must be smoke or full, got %s\n' "$PROFILE" >&2
  exit 2
fi

rm -rf "$RAW_ROOT/$PROFILE" "$DERIVED_ROOT"
mkdir -p "$DERIVED_ROOT"

buck2 run //experiments:run_autodiff_ggn_benchmark_conda -- \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --output-root "$RAW_ROOT"

buck2 run //experiments:make_autodiff_ggn_artifacts -- \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --raw-root "$RAW_ROOT" \
  --aggregate "$DERIVED_ROOT/aggregate.json" \
  --systems-figure "paper/figures/autodiff_ggn_systems.pdf" \
  --accuracy-figure "paper/figures/autodiff_ggn_accuracy.pdf" \
  --table "tables/generated/autodiff_ggn_summary.tex"
