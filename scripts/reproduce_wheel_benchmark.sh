#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROFILE="${PROFILE:-full}"
CONFIG="experiments/configs/wheel_benchmark.yaml"
RAW_ROOT="results/raw/wheel_benchmark"
PROFILE_ROOT="$RAW_ROOT/$PROFILE"
SELECTION="$PROFILE_ROOT/tuning_selection.json"
OUTPUT="results/derived/wheel_benchmark_${PROFILE}.json"

if [[ "$PROFILE" != "smoke" && "$PROFILE" != "full" ]]; then
  printf 'PROFILE must be smoke or full, got %s\n' "$PROFILE" >&2
  exit 2
fi

if [[ "${REUSE_RAW:-0}" != "1" ]]; then
  rm -rf "$PROFILE_ROOT"
  buck2 run //experiments:run_conda_module -- \
    experiments.run_wheel_benchmark \
    --config "$CONFIG" \
    --profile "$PROFILE" \
    --seed-set tuning \
    --output-root "$RAW_ROOT" \
    --tuning-selection "$SELECTION"
  buck2 run //experiments:run_conda_module -- \
    experiments.run_wheel_benchmark \
    --config "$CONFIG" \
    --profile "$PROFILE" \
    --seed-set evaluation \
    --output-root "$RAW_ROOT" \
    --tuning-selection "$SELECTION"
fi

buck2 run //experiments:run_conda_module -- \
  experiments.make_wheel_benchmark_artifacts \
  --config "$CONFIG" \
  --profile "$PROFILE" \
  --raw-root "$PROFILE_ROOT/evaluation" \
  --selection "$SELECTION" \
  --output "$OUTPUT"
