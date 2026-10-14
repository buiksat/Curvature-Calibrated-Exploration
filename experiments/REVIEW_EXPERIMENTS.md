# Running the new transport follow-up on the Meta server

The new study probes stronger realized curvature drift at fixed nonlinear
scales `W = 16, 1, 0.25`. It preserves the earlier locked study. Its scientific
design, seeds and interpretation are in
[TRANSPORT_REVIEW_FOLLOWUP_PROTOCOL.md](TRANSPORT_REVIEW_FOLLOWUP_PROTOCOL.md).

The two A100s are not used: the current experiment performs exact dense
29-dimensional NumPy/SciPy linear algebra and independent CPU trajectories.
Parallel CPU processes are the useful unit of work. A CUDA rewrite or a new
real-data study would require separate implementation and validation; neither
is claimed by this workflow.

## Pull and run

Use your existing repository checkout. Check for local changes and save any
existing work before switching branches; do not discard it to make the checkout
clean. Fetch and switch to the published revision branch:

```bash
git status --short
git fetch origin
git switch cce-review-revisions
git pull --ff-only origin cce-review-revisions
```

If the branch is not local yet, `git switch` creates its tracking branch from
`origin/cce-review-revisions`. Start the full run from a clean checkout. Keep
the code, protocol, dependencies and configuration fixed while a run is in progress.
The server needs Linux x86-64, Python 3.12 with `venv`, Git, and access to PyPI
for the first installation. The wrapper creates a virtual environment inside
the specified external output directory and installs the exact, hash-checked
wheel lock. No Buck build or GPU package installation is needed. See
[PYTHON_SETUP.md](../PYTHON_SETUP.md) for manual environment setup.

Run the full study with one command from the repository root:

```bash
bash tools/run_review_experiments.sh --profile full \
  --output "$HOME/cce-runs/strong-drift-full"
```

The default uses at most eight available logical CPUs. Set `--workers N` to
match the CPU allocation for this job. BLAS uses one thread per worker, avoiding
nested thread pools. The full grid first runs all 24 declared development trajectories and
checks full-order versus half-order quadrature, then runs 270 tuning trajectories
and 600 fresh evaluation trajectories at horizon 1000. The complete full-study
runtime has not been measured. One strongest-condition development trajectory
at horizon 1000 took about 46 seconds locally; that single trajectory does not
establish the runtime of the full grid. Quadrature diagnostics are a substantial
part of the workload.

For a smaller feasibility run, use a separate directory:

```bash
bash tools/run_review_experiments.sh --profile pilot \
  --output "$HOME/cce-runs/strong-drift-pilot"
```

The pilot first runs 24 development trajectories, followed by 54 tuning
trajectories and 24 evaluation trajectories at horizon 64. It is not publication
evidence and does not select the full-study optimizer.

The complete 102-trajectory pilot passed locally with four workers in about
8 minutes 35 seconds, including strict aggregation. This timing comes from the
[original exported run manifest](../review/transport_review_followup/pilot-cce-review-pilot/run_manifest.json),
before the successful resume check. Server timings can differ.

Full tuning uses its own disjoint seeds before any full evaluation. Commit or
move a completed pilot export before starting a full run: a new full run
requires a clean checkout and a committed protocol/configuration.

To inspect the workload first, append `--plan` to the wrapper command. It prepares
the external virtual environment and prints the grid without running trajectories:

```bash
bash tools/run_review_experiments.sh --profile full \
  --output "$HOME/cce-runs/strong-drift-full" --plan
```

Use the server's scheduler or a persistent terminal session for long jobs.
`progress.json` and `run.json` in the output directory expose progress and state.
Do not assume the process finished merely because a terminal disconnected.
Append `--development-only` to benchmark the complete declared development grid
without starting tuning or evaluation. Rerun without that flag to continue.

## Resume and provenance

Rerun the identical command after interruption. A per-trajectory completion
receipt permits reuse only when every required file still matches its SHA-256
digest. Partial writes are moved to an `interrupted/` directory before being
recomputed. They are never mistaken for successful runs. Tuning selection and
aggregate writes have separate completion receipts.

Deterministic audit failures are preserved and stop the workflow. They are not
silently discarded or retried until a favorable result appears. Keep the failed
output directory and diagnose the cause; a justified change needs a new
configuration/revision and a new output directory. Ordinary statistical
confidence failures are retained by the existing strict aggregator.

The execution manifest binds the actual follow-up config, resolved settings,
protocol, launcher, source files, dependency versions and Git revision. Changing
the worker count also changes the resolved config digest, so retain it on resume.
Do not `git pull` into a running or partially completed study. Use a fresh output
directory after updating code. The original study's config, selections, raw-data
hashes, aggregate, and publication artifacts are never overwritten.

Each worker caches NumPy's Gauss–Legendre nodes for repeated quadrature orders.
This reuses exactly the same computed array bytes and makes cached arrays
read-only; it does not change the quadrature rule, order, tolerances or policy.
The optimization is recorded in the execution manifest and tested independently.

Raw trajectories, full aggregates, interruption records and virtual environments
remain outside Git. The selected optimizer is frozen before evaluation, bound to
the complete tuning input inventory, and reused by all four methods. The existing
strict aggregator rechecks the full Cartesian product, config/revision/selection
bindings, raw hashes and deterministic audits before any compact export is made.

## Send the results back through GitHub

After successful aggregation, the launcher creates a new folder such as
`review/transport_review_followup/full-strong-drift-full/`. It does not commit or
push. The folder contains:

- Exact development/tuning/evaluation summaries and all per-method terminal bound components.
- Aggregate outcome, paired-bootstrap, confidence, nonvacuity and tightness results.
- Per-seed roundwise endpoint-drift threshold counts, their explicitly denominated
  fractions, and reference-geometry bound accounting
  on each method's own trajectory. Only `frozen_reference` describes the frozen
  policy's trajectory; subtracting transport inflation from another policy's
  bound does not simulate the frozen policy.
- The source/resolved configs, frozen selection, source and raw-input inventories,
  execution manifest, and portable file checksums.

Verify the transferable outcome evidence, then commit that folder and push the
current revision branch:

```bash
"$HOME/cce-runs/strong-drift-full/.venv/bin/python" \
  tools/verify_review_experiment_export.py \
  review/transport_review_followup/full-strong-drift-full
git add review/transport_review_followup/full-strong-drift-full
git commit -m "experiments: add strong-drift follow-up results"
git push origin cce-review-revisions
```

The command explicitly uses the run's locked virtual environment. The verifier
can replay terminal regret means and paired confidence intervals from transferred
seed summaries. It cannot replay
per-round audits or curve confidence intervals without the raw trajectories.
The compact export does not claim independent raw-data verification after
transfer. Keep the complete external output directory on the server, including
all raw data, even after pushing the compact results.
