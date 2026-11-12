# Experiment pipeline

This directory contains versioned experiment protocols and the shared
reproducibility/logging layer. The protocol files use JSON syntax inside
`.yaml` files: JSON is a YAML subset, so they load with the Python standard
library. General YAML is accepted only when PyYAML is installed.

## Profiles and seed splits

- `smoke` reduces rounds, dimensions, grids, and seeds. It checks wiring and is
  not a reportable experiment.
- `full` contains the reportable protocol and complete sweeps.
- `tuning` seeds select hyperparameters and coverage-matched bonus values.
- `evaluation` seeds are disjoint and are the only seeds used for final metrics.

Never select a setting on `evaluation` seeds. In particular,
`covertype_rerun.yaml` replaces the old same-seed selection/reporting procedure
with pooled tuning-seed selection followed by an independent evaluation run.

## Exact validation commands

Run the smoke/tuning checks from the repository root:

```bash
.venv/bin/python -m experiments.config experiments/configs/linear_audit.yaml --profile smoke --seed-set tuning
.venv/bin/python -m experiments.config experiments/configs/certified_tanh.yaml --profile smoke --seed-set tuning
.venv/bin/python -m experiments.config experiments/configs/curvature_phase_diagram.yaml --profile smoke --seed-set evaluation
.venv/bin/python -m experiments.config experiments/configs/nonlinear_drift.yaml --profile smoke --seed-set tuning
.venv/bin/python -m experiments.config experiments/configs/operator_ablation.yaml --profile smoke --seed-set tuning
.venv/bin/python -m experiments.config experiments/configs/cg_accuracy.yaml --profile smoke --seed-set tuning
.venv/bin/python -m experiments.config experiments/configs/systems_scaling.yaml --profile smoke --seed-set tuning
.venv/bin/python -m experiments.config experiments/configs/covertype_rerun.yaml --profile smoke --seed-set tuning
```

Resolve the full evaluation protocols with these commands:

```bash
.venv/bin/python -m experiments.config experiments/configs/balanced_benchmark.yaml --profile full --seed-set evaluation
.venv/bin/python -m experiments.config experiments/configs/linear_audit.yaml --profile full --seed-set evaluation
.venv/bin/python -m experiments.config experiments/configs/certified_tanh.yaml --profile full --seed-set evaluation
.venv/bin/python -m experiments.config experiments/configs/curvature_phase_diagram.yaml --profile full --seed-set evaluation
.venv/bin/python -m experiments.config experiments/configs/nonlinear_drift.yaml --profile full --seed-set evaluation
.venv/bin/python -m experiments.config experiments/configs/operator_ablation.yaml --profile full --seed-set evaluation
.venv/bin/python -m experiments.config experiments/configs/cg_accuracy.yaml --profile full --seed-set evaluation
.venv/bin/python -m experiments.config experiments/configs/systems_scaling.yaml --profile full --seed-set evaluation
.venv/bin/python -m experiments.config experiments/configs/covertype_rerun.yaml --profile full --seed-set evaluation
```

Execute the reportable studies from the repository root:

```bash
.venv/bin/python -m experiments.run_balanced_benchmark --config experiments/configs/balanced_benchmark.yaml --profile full --seed-set tuning --tuning-selection results/raw/balanced_benchmark/full/tuning_selection.json --overwrite
.venv/bin/python -m experiments.run_balanced_benchmark --config experiments/configs/balanced_benchmark.yaml --profile full --seed-set evaluation --tuning-selection results/raw/balanced_benchmark/full/tuning_selection.json --overwrite
.venv/bin/python -m experiments.make_balanced_benchmark_artifact --config experiments/configs/balanced_benchmark.yaml --profile full --raw-root results/raw/balanced_benchmark/full/evaluation --selection results/raw/balanced_benchmark/full/tuning_selection.json --output results/derived/balanced_benchmark_full.json
.venv/bin/python -m experiments.run_linear_study --config experiments/configs/linear_audit.yaml --profile full --output-root results/raw/linear_audit --overwrite
.venv/bin/python -m experiments.run_certified_tanh --config experiments/configs/certified_tanh.yaml --profile full --seed-set evaluation --output-root results/raw/certified_tanh --overwrite
.venv/bin/python -m experiments.run_certified_tanh --config experiments/configs/certified_tanh.yaml --profile full --seed-set tuning --controlled-grid --output-root results/raw/certified_tanh --overwrite
.venv/bin/python -m experiments.make_curvature_phase_diagram_artifact --config experiments/configs/curvature_phase_diagram.yaml --output results/raw/curvature_phase_diagram/full/evaluation --derived-report results/derived/curvature_phase_diagram_report.json --write-round-records
.venv/bin/python -m experiments.run_nonlinear_audit --config experiments/configs/nonlinear_drift.yaml --profile full --seed-set evaluation --output-root results/raw/nonlinear_drift --overwrite
.venv/bin/python -m experiments.run_operator_ablation --config experiments/configs/operator_ablation.yaml --profile full --seed-set evaluation --environment both --output-root results/raw/operator_ablation --overwrite
.venv/bin/python -m experiments.run_cg_accuracy --config experiments/configs/cg_accuracy.yaml --profile full --seed-set evaluation --audit solver --output-root results/raw/cg_accuracy --overwrite
.venv/bin/python -m experiments.run_cg_accuracy --config experiments/configs/cg_accuracy.yaml --profile full --seed-set evaluation --audit policy --output-root results/raw --overwrite
.venv/bin/python -m experiments.run_systems_scaling --config experiments/configs/systems_scaling.yaml --profile full --seed-set evaluation --output-root results/raw/systems_scaling --overwrite
.venv/bin/python -m experiments.run_covertype --config experiments/configs/covertype_rerun.yaml --profile full --seed-set tuning --download --output-root results/raw/covertype_rerun_1500 --tuning-selection results/raw/covertype_rerun_1500/full/tuning_selection.json --overwrite
.venv/bin/python -m experiments.run_covertype --config experiments/configs/covertype_rerun.yaml --profile full --seed-set evaluation --output-root results/raw/covertype_rerun_1500 --tuning-selection results/raw/covertype_rerun_1500/full/tuning_selection.json --test-diagnostics-output results/derived/covertype_test_class_counts.json --overwrite
```

In the balanced benchmark, `neural_linear` is a Gaussian Bayesian linear head
with a frozen initialized tanh representation; `frozen_last_layer_ucb` uses the
same posterior with a UCB rule. `cc_ucb_full_ggn_cg` relinearizes the selected
history at the current parameters and runs residual-checked matrix-free CG.
The `neural_ucb` and `neural_ts` rows are explicitly local linearized
implementations, not claims of exact reproduction of every published training
protocol. All full-network rows receive one identical clipped SGD update per
round. Tuning uses only the declared tuning seeds, and evaluation reruns each
selected policy from scratch on disjoint seeds.

`--download` only authorizes the public Covertype download when the cache is
absent. Evaluation refuses to run without a validated tuning-selection artifact.
The nonlinear schedules are fixed in advance, so their tuning seed set is not
used for data-dependent selection; their exact teacher quantities remain post-hoc
audit fields. The operator driver defaults to its legacy linear-only execution;
pass `--environment both` for the complete configured linear and smooth nonlinear
audit. Nonlinear operator outputs are nested under
`<profile>/<seed-set>/nonlinear/<regime>/<center>/`. Operator-ablation directories under `offline_common_trajectory/`
are diagnostics and must never be aggregated as executed policies.
The CG solver audit and CG executed-policy audit are distinct artifacts:
`results/raw/cg_accuracy/` contains fixed-SPD solve diagnostics, whereas
`results/raw/cg_policy_accuracy/` contains separately executed linear-bandit
policies for every tolerance, initialization, and preconditioner cell.

The `certified_tanh` action rule uses the O(d)-state path schedules before
selection and commits the selected CG width before observing reward. Its
float64 rows are conservatively classified `posthoc_theorem_event_verified`:
all audited theorem events hold, but residual calculations are not verified
interval enclosures. The one-factor controlled design is executed only on
tuning seeds with `--controlled-grid`; the fixed full protocol performs no
evaluation-seed model selection.

Aggregate only complete evaluation trees:

```bash
.venv/bin/python -m experiments.aggregate_results results/raw/linear_audit/full/evaluation --seed-set evaluation --output results/derived/linear_audit_full.json
.venv/bin/python -m experiments.aggregate_results results/raw/certified_tanh/full/evaluation --seed-set evaluation --output results/derived/certified_tanh_full.json
.venv/bin/python -m experiments.aggregate_results results/raw/certified_tanh/controlled_grid/full/tuning --seed-set tuning --output results/derived/certified_tanh_controlled_grid.json
.venv/bin/python -m experiments.make_certified_tanh_artifact
.venv/bin/python -m experiments.aggregate_results results/raw/systems_scaling/systems_scaling/full/evaluation --seed-set evaluation --output results/derived/systems_scaling_full.json
.venv/bin/python -m experiments.aggregate_results results/raw/nonlinear_drift/nonlinear_audit/full/evaluation --seed-set evaluation --output results/derived/nonlinear_drift_full.json
.venv/bin/python -m experiments.aggregate_cg_policy results/raw/cg_policy_accuracy/full/evaluation --seed-set evaluation --output results/derived/cg_policy_accuracy_full.json
.venv/bin/python -m experiments.aggregate_results results/raw/covertype_rerun_1500 --output results/derived/covertype_rerun_1500_full_aggregate.json
```

Generate the linear action-selection certification ledger after the strict
linear aggregate is current:

```bash
.venv/bin/python -m experiments.make_certification_audit
```

This validates all full-profile evaluation manifests and summaries before
writing `results/derived/certification_audit.json` and its SHA-256 provenance
sidecar.

Generate the linear bound-scale and compact Covertype report artifacts after
their strict aggregates are current:

```bash
.venv/bin/python -m experiments.make_linear_bound_artifact
.venv/bin/python -m experiments.make_covertype_horizon_artifact
.venv/bin/python -m experiments.make_revision_paper_artifacts
```

Build the anonymous compact supplement into a fresh directory only after the
paper and all derived artifacts are final:

```bash
.venv/bin/python tools/build_anonymous_supplement.py --output release
```

Build the smaller review tier only after the same artifacts are final:

```bash
.venv/bin/python tools/build_anonymous_supplement.py --tier review
```

Review mode defaults to `release_review`. It retains every source, config,
test, derived artifact, paper table/figure input, and small raw support file,
but selects only the lexicographically first complete raw run in each top-level
study. The deterministic selection and SHA-256 bindings for every omitted raw
file are recorded in `manifests/full-raw-index.json`; indexed files are not
claimed to be present in the review bundle.

Add `--print` to any command to inspect the fully resolved configuration. Run
the pipeline tests exactly as follows:

```bash
.venv/bin/python -m pytest -q tests/test_experiment_pipeline.py
```

## Driver integration

Experiment drivers should load one resolved profile, enumerate one named seed
set, seed every stochastic component, and create one output directory per seed:

```python
from pathlib import Path

from experiments.config import get_seed_set, load_config
from experiments.logging_utils import ExperimentLogger, derive_seed, seed_everything

config = load_config("experiments/configs/linear_audit.yaml", profile="smoke")
for seed in get_seed_set(config, "tuning"):
    seed_everything(seed)
    output = Path("experiments/results") / config["name"] / config["profile"] / f"seed-{seed}"
    with ExperimentLogger(output, config, seed, repository=".") as logger:
        # Pass derived seeds to independent samplers/operators instead of sharing state.
        operator_seed = derive_seed(seed, "curvature_operator")
        for round_index in range(config["rounds"]):
            metrics = run_one_round(round_index, operator_seed)  # supplied by the driver
            logger.log_round(round_index, metrics)
```

Each seed directory contains:

- `manifest.jsonl`: one immutable record with the full resolved config, seed,
  UTC timestamp, config digest, Git revision/dirty flag, package versions,
  Python runtime, and hardware details.
- `raw.jsonl`: one canonical record per round. Records include run ID, seed,
  round, UTC timestamp, and the complete metric mapping supplied by the driver.

Both files are strict JSONL: keys are sorted, NaN/infinity are rejected, and
round indices must increase. `experiments/data/` and `experiments/results/` are
tracked only as empty destinations; their generated contents are ignored.
