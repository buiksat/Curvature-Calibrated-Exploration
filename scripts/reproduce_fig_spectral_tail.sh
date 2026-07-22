#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROFILE="${PROFILE:-full}"
CONFIG="experiments/configs/spectral_tail_study.yaml"
RAW_ROOT="results/raw/spectral_tail_study"
DERIVED_ROOT="results/derived/spectral_tail_study/$PROFILE"
SELECTION="$DERIVED_ROOT/tuning_selection.json"

if [[ "$PROFILE" != "smoke" && "$PROFILE" != "full" ]]; then
  printf 'PROFILE must be smoke or full, got %s\n' "$PROFILE" >&2
  exit 2
fi

rm -rf "$RAW_ROOT/$PROFILE" "$DERIVED_ROOT"
mkdir -p "$DERIVED_ROOT"

buck2 run //experiments:run_spectral_tail_study -- \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --phase tuning \
  --output-root "$RAW_ROOT" \
  --selection "$SELECTION"

buck2 run //experiments:run_spectral_tail_study -- \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --phase evaluation \
  --output-root "$RAW_ROOT" \
  --selection "$SELECTION"

buck2 run //experiments:make_spectral_tail_artifacts -- \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --raw-root "$RAW_ROOT" \
  --selection "$SELECTION" \
  --aggregate "$DERIVED_ROOT/aggregate.json" \
  --regret-figure "paper/figures/spectral_tail_regret.pdf" \
  --complexity-figure "paper/figures/spectral_tail_complexity.pdf" \
  --decision-figure "paper/figures/spectral_tail_decisions.pdf" \
  --table "tables/generated/spectral_tail_summary.tex"
