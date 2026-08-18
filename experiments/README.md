# Experiment pipelines

This directory contains the four experiment paths that remain relevant to the
current paper. Historical benchmark drivers and their generated artifacts were
removed from the working tree. They remain available in Git history.

All checked-in `.yaml` files contain JSON, which is valid YAML and can be read
without PyYAML. Run repository commands through Buck2 from the repository root.

## Tests

```bash
buck2 test //experiments/tests:tests -- --timeout=1200
```

## Nonlinear confidence-transport instantiation

`TRANSPORT_INSTANTIATION_PROTOCOL.md` preregisters the first direct experiment
for the revised theorem. It uses a finite-dimensional scaled-tanh Gaussian
bandit, exact dense frozen and current metrics, exact Cholesky solves, and four
fixed policies. The Hessian/\(Q_t\) method is the operational theorem
instantiation. The endpoint method is a dense diagnostic oracle, and the naive
current-width method is intentionally uncertified.

Resolve and run the smoke protocol first:

```bash
buck2 run //experiments:config -- \
  experiments/configs/transport_instantiation.yaml \
  --profile smoke --seed-set development --print
buck2 run //experiments:run_transport_instantiation_study -- \
  --config experiments/configs/transport_instantiation.yaml \
  --profile smoke --phase development \
  --output-root results/raw/transport_instantiation/smoke --overwrite
buck2 run //experiments:run_transport_instantiation_study -- \
  --config experiments/configs/transport_instantiation.yaml \
  --profile smoke --phase tuning \
  --output-root results/raw/transport_instantiation/smoke \
  --selection-output results/derived/transport_instantiation/smoke_selection.json \
  --overwrite
buck2 run //experiments:run_transport_instantiation_study -- \
  --config experiments/configs/transport_instantiation.yaml \
  --profile smoke --phase evaluation \
  --selection results/derived/transport_instantiation/smoke_selection.json \
  --output-root results/raw/transport_instantiation/smoke --overwrite
```

Smoke results are never publication evidence. After the protocol and code are
committed, run the full tuning and evaluation phases, then invoke the strict
aggregator:

```bash
buck2 run //experiments:aggregate_transport_instantiation -- \
  --config experiments/configs/transport_instantiation.yaml \
  --profile full \
  --selection results/derived/transport_instantiation/selection.json \
  --raw-root results/raw/transport_instantiation/full \
  --output results/derived/transport_instantiation/full_aggregate.json
```

The aggregator rejects incomplete Cartesian products, mixed revisions or
configurations, selection mismatches, nonfinite values, and deterministic
audit failures. Statistical confidence failures remain in the aggregate.
Raw run directories remain untracked.

## Linear confidence audit

`linear_audit.yaml` defines disjoint tuning and evaluation seeds. The study
tunes ridge and bonus values only on tuning seeds, then starts fresh policies
on evaluation seeds.

Resolve the configuration and run a bounded smoke audit:

```bash
buck2 run //experiments:config -- \
  experiments/configs/linear_audit.yaml --profile smoke --seed-set tuning
buck2 run //experiments:run_linear_audit -- \
  --config experiments/configs/linear_audit.yaml \
  --profile smoke --seed-set tuning --rounds 16 \
  --output-dir results/raw/linear_audit/smoke --overwrite
```

Run the frozen tuning/evaluation protocol:

```bash
buck2 run //experiments:run_linear_study -- \
  --config experiments/configs/linear_audit.yaml \
  --profile full --output-root results/raw/linear_audit --overwrite
```

Build the strict seed-level aggregate, then generate the certification and
bound artifacts:

```bash
buck2 run //experiments:aggregate_linear_audit -- \
  --config experiments/configs/linear_audit.yaml \
  --profile full --raw-root results/raw/linear_audit \
  --output results/derived/linear_audit_full.json
buck2 run //experiments:make_certification_audit
buck2 run //experiments:make_linear_bound_artifact
```

The aggregator rechecks every tuning result and selected hyperparameter before
accepting evaluation runs. It rejects incomplete method, comparison, or seed
grids and binds every raw input to the aggregate provenance sidecar.

The exact small-scale matrices are diagnostic oracles. The executed CG policy
uses the fixed operator and recomputes residuals against that operator.

## Closed-rate accounting artifact

This deterministic generator converts the checked-in rational exponents into
JSON and a LaTeX table. It performs no empirical estimation.

```bash
buck2 run //experiments:make_closed_rate_artifact -- \
  --config experiments/configs/closed_rate_predictions.json
```

## Autodiff GGN benchmark

The benchmark applies a real squared-loss GGN with `torch.func.jvp` and
`torch.func.vjp`. Small models include an explicit dense reference. Large
models remain matrix-free. PyTorch is provided by the Buck-managed Conda
runtime rather than the base Python dependencies.

```bash
buck2 run //experiments:run_autodiff_ggn_benchmark_conda -- \
  --config experiments/configs/autodiff_ggn_benchmark.yaml \
  --profile smoke --seed-set evaluation \
  --output-root results/raw/autodiff_ggn --overwrite
```

After a complete raw grid, regenerate the checked-in aggregate and paper table:

```bash
buck2 run //experiments:make_autodiff_ggn_artifacts -- \
  --config experiments/configs/autodiff_ggn_benchmark.yaml \
  --profile full --raw-root results/raw/autodiff_ggn \
  --aggregate results/derived/autodiff_ggn_benchmark/full/aggregate.json \
  --table paper/tables/autodiff_ggn_summary.tex
```

Every retained writer records the resolved configuration, seed, runtime
metadata, and SHA-256 provenance. A missing optional runtime produces an
explicit `not_run` record. It is never treated as a timing result.
