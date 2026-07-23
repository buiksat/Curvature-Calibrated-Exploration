#!/usr/bin/env bash
set -euo pipefail

PROFILE="${PROFILE:-full}"
RAW_ROOT="results/raw/coverage_matched_operator/${PROFILE}"

if [[ "${REUSE_RAW:-0}" != "1" ]]; then
  buck2 run //experiments:run_coverage_matched_operator_study -- \
    --config experiments/configs/coverage_matched_operator.yaml \
    --profile "$PROFILE" \
    --output-root "$RAW_ROOT" \
    --overwrite
fi

buck2 run //experiments:make_coverage_matched_operator_artifacts -- \
  --raw-root "$RAW_ROOT" \
  --derived results/derived/coverage_matched_operator.json \
  --mechanism-figure paper/figures/coverage_matched_mechanism.pdf \
  --heatmap-figure paper/figures/coverage_matched_heatmaps.pdf \
  --table tables/generated/coverage_matched_calibration.tex \
  --comparison-table tables/generated/coverage_matched_comparisons.tex
