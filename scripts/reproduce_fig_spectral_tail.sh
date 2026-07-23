#!/usr/bin/env bash
set -euo pipefail

# This entry point only reanalyzes the retained evaluation trajectories. It
# intentionally never removes raw data, reruns policies, or selects bonuses.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROFILE="${PROFILE:-full}"
CONFIG="experiments/configs/spectral_tail_study.yaml"
RAW_ROOT="results/raw/spectral_tail_study"
DERIVED_ROOT="results/derived/spectral_tail_study/$PROFILE"
SELECTION="$DERIVED_ROOT/tuning_selection.json"
BOUND_AGGREGATE="$DERIVED_ROOT/bound_reanalysis.json"
BOUND_FIGURE="paper/figures/spectral_tail_bound_reanalysis.pdf"
BOUND_TABLE="tables/generated/spectral_tail_bound_reanalysis.tex"

if [[ "$PROFILE" != "smoke" && "$PROFILE" != "full" ]]; then
  printf 'PROFILE must be smoke or full, got %s\n' "$PROFILE" >&2
  exit 2
fi

if [[ ! -d "$RAW_ROOT/$PROFILE/evaluation" ]]; then
  printf 'missing retained evaluation trajectories: %s\n' \
    "$RAW_ROOT/$PROFILE/evaluation" >&2
  exit 1
fi
if [[ ! -f "$SELECTION" || ! -f "$SELECTION.sha256" ]]; then
  printf 'missing frozen tuning selection or sidecar: %s\n' "$SELECTION" >&2
  exit 1
fi

buck2 run //experiments:make_spectral_tail_artifacts -- \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --raw-root "$RAW_ROOT" \
  --selection "$SELECTION" \
  --bound-reanalysis \
  --bound-aggregate "$BOUND_AGGREGATE" \
  --bound-figure "$BOUND_FIGURE" \
  --bound-table "$BOUND_TABLE"
