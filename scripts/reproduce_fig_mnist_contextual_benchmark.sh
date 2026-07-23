#!/usr/bin/env bash
set -euo pipefail

PROFILE="${PROFILE:-full}"
RAW_ROOT="results/raw/mnist_contextual_benchmark/${PROFILE}"

if [[ "${REUSE_RAW:-0}" != "1" ]]; then
  buck2 run //experiments:run_conda_module -- \
    experiments.run_mnist_contextual_benchmark \
    --config experiments/configs/mnist_contextual_benchmark.yaml \
    --profile "$PROFILE" \
    --output-root "$RAW_ROOT" \
    --overwrite
fi

buck2 run //experiments:make_mnist_contextual_benchmark_artifacts -- \
  --raw-root "$RAW_ROOT" \
  --derived results/derived/mnist_contextual_benchmark.json \
  --regret-figure paper/figures/mnist_contextual_regret.pdf \
  --compute-figure paper/figures/mnist_contextual_compute.pdf \
  --table tables/generated/mnist_contextual_benchmark.tex
