#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROFILE="${PROFILE:-full}"
WORKERS="${WORKERS:-16}"
CONFIG="experiments/configs/certified_scaling.yaml"
RAW_ROOT="results/raw/certified_scaling"
DERIVED_ROOT="results/derived/certified_scaling/$PROFILE"

if [[ "$PROFILE" != "smoke" && "$PROFILE" != "full" ]]; then
  printf 'PROFILE must be smoke or full, got %s\n' "$PROFILE" >&2
  exit 2
fi

rm -rf "$RAW_ROOT/$PROFILE" "$DERIVED_ROOT"
mkdir -p "$DERIVED_ROOT"

buck2 run //experiments:run_certified_scaling -- \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --output-root "$RAW_ROOT" \
  --workers "$WORKERS"

buck2 run //experiments:make_certified_scaling_artifacts -- \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --raw-root "$RAW_ROOT" \
  --aggregate "$DERIVED_ROOT/aggregate.json" \
  --figure "paper/figures/certified_scaling.pdf" \
  --premise-table "tables/generated/certified_scaling_premises.tex" \
  --fits-table "tables/generated/certified_scaling_fits.tex"
