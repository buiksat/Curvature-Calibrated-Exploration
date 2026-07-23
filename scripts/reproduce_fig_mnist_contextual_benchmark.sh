#!/usr/bin/env bash
set -euo pipefail

PROFILE="${PROFILE:-full}"
WORKERS="${WORKERS:-4}"
RAW_ROOT="results/raw/mnist_contextual_benchmark/${PROFILE}"

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export KMP_AFFINITY="${KMP_AFFINITY:-disabled}"
export CUBLAS_WORKSPACE_CONFIG="${CUBLAS_WORKSPACE_CONFIG:-:4096:8}"

if [[ "${REUSE_RAW:-0}" != "1" ]]; then
  buck2 run //experiments:run_conda_module -- \
    experiments.run_mnist_contextual_benchmark \
    --config experiments/configs/mnist_contextual_benchmark.yaml \
    --profile "$PROFILE" \
    --output-root "$RAW_ROOT" \
    --workers "$WORKERS" \
    --overwrite
fi

buck2 run //experiments:make_mnist_contextual_benchmark_artifacts -- \
  --raw-root "$RAW_ROOT" \
  --derived results/derived/mnist_contextual_benchmark.json \
  --regret-figure paper/figures/mnist_contextual_regret.pdf \
  --compute-figure paper/figures/mnist_contextual_compute.pdf \
  --table tables/generated/mnist_contextual_benchmark.tex
