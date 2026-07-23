#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMMAND="${1:-create}"
PROFILE="${PROFILE:-smoke}"
CONFIG="${CONFIG:-experiments/configs/wheel_benchmark.yaml}"
RAW_ROOT="${RAW_ROOT:-results/raw/wheel_benchmark}"
BUNDLE_DIR="${BUNDLE_DIR:-results/raw/bundles/wheel_benchmark}"
BUNDLE="${BUNDLE:-$BUNDLE_DIR/wheel_benchmark-$PROFILE.tar.gz}"
INVENTORY="${INVENTORY:-$BUNDLE.inventory.json}"
DESTINATION="${DESTINATION:-results/raw/restored/wheel_benchmark-$PROFILE}"

if [[ "$PROFILE" != "smoke" && "$PROFILE" != "full" ]]; then
  printf 'PROFILE must be smoke or full, got %s\n' "$PROFILE" >&2
  exit 2
fi

case "$COMMAND" in
  create)
    ARGS=(
      create-wheel
      --config "$CONFIG"
      --profile "$PROFILE"
      --raw-root "$RAW_ROOT"
      --bundle "$BUNDLE"
      --inventory "$INVENTORY"
    )
    if [[ "${OVERWRITE:-0}" == "1" ]]; then
      ARGS+=(--overwrite)
    fi
    buck2 run //experiments:run_conda_module -- \
      experiments.raw_artifact_bundle "${ARGS[@]}"
    ;;
  verify)
    buck2 run //experiments:run_conda_module -- \
      experiments.raw_artifact_bundle verify \
      --bundle "$BUNDLE" \
      --inventory "$INVENTORY"
    ;;
  extract)
    buck2 run //experiments:run_conda_module -- \
      experiments.raw_artifact_bundle extract \
      --bundle "$BUNDLE" \
      --inventory "$INVENTORY" \
      --destination "$DESTINATION"
    ;;
  *)
    printf 'usage: %s [create|verify|extract]\n' "$0" >&2
    exit 2
    ;;
esac
