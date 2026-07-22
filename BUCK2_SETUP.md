# Buck2 setup

## Host prerequisites

This checkout is configured for the Meta host toolchain available on the
revision machine. A clean checkout requires:

- `buck2` on `PATH` (the checked-in `.buck2` DotSlash manifest pins the Buck2
  build);
- `/data/repos/fbsource` with the platform010 Python 3.12 toolchain, Prelude,
  and declared third-party targets;
- Linux x86-64 with glibc compatible with the checked-in CPython 3.12 wheels.

The `.buck/fbsource_cell` links intentionally expose only the required host
cell. Buck actions are local because remote execution cannot dereference these
host links. If `/data/repos/fbsource` is absent, that is an exact build blocker;
do not replace the missing dependencies with pip or a virtual environment.

From the repository root, validate the checkout before running Python code:

```bash
test -d /data/repos/fbsource
buck2 --version
buck2 root
buck2 audit cell
buck2 targets //...
(cd third_party/wheels && sha256sum -c SHA256SUMS)
```

All output arguments below are repository-relative. Do not invoke `python`,
`python3`, pip, a virtual environment, or pytest directly.

## Tests

The two Buck test targets cover the complete suite (241 pytest cases: the
previous 234 plus four full-grid validation, one Buck-PyTorch blocker, and two
paper-artifact cases added in this revision):

```bash
buck2 test //tests:tests //experiments/tests:tests -- --timeout=1200
```

For a single combined case-count report, the same suites can be run through the
Buck-built runner:

```bash
buck2 run //tools:pytest_runner -- -q tests experiments/tests
```

## Experiment targets

Resolve any versioned protocol without executing it:

```bash
buck2 run //experiments:config -- \
  experiments/configs/theory_scaling.json \
  --profile full --seed-set evaluation --print
```

The reportable scaling driver and deterministic aggregator are:

```bash
buck2 run //experiments:theory_scaling_compact -- \
  --config experiments/configs/theory_scaling.json \
  --profile full --seed-set development \
  --output-root results/raw/theory_scaling_smoke \
  --dimension 128 --rank 8 --horizon 2048

buck2 run //experiments:aggregate_theory_scaling -- \
  --config experiments/configs/theory_scaling.json \
  --profile full --seed-set evaluation \
  --input-root results/raw/theory_scaling_compact \
  --scope full-grid \
  --output results/derived/theory_scaling_full_grid.json
```

The full-grid raw tree is intentionally not stored in Git. The aggregation
command requires a locally executed or externally restored 3,600-run tree. A
clean checkout retains the validated derived aggregate and its SHA-256 sidecar,
and can regenerate the paper artifacts without the full raw tree.

The primary `d=128`, `r=4`, `T=2048` raw slice and
`results/derived/theory_scaling_primary.json` are retained checkpoints. Do not
rerun or overwrite them merely to validate Buck support.

Validate that retained slice and all hash sidecars without writing an artifact:

```bash
buck2 run //experiments:aggregate_theory_scaling -- \
  --config experiments/configs/theory_scaling.json \
  --profile full --seed-set evaluation \
  --input-root results/raw/theory_scaling_compact \
  --scope primary --validate-only
```

Each evaluation shard is one method/seed process with a distinct run directory.
Use fixed one-thread BLAS scheduling when launching shards in parallel:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
buck2 run //experiments:theory_scaling_compact -- \
  --config experiments/configs/theory_scaling.json \
  --profile full --seed-set evaluation \
  --seed 240 --method exact_current \
  --output-root results/raw/theory_scaling_reproduction \
  --dimension 128 --rank 8 --horizon 2048
```

The off-diagonal and closed-rate artifact chain is:

```bash
buck2 run //experiments:run_offdiagonal_witness -- \
  --config experiments/configs/offdiagonal_witness.yaml \
  --profile full --seed-set evaluation \
  --output results/raw/offdiagonal_witness
buck2 run //experiments:make_offdiagonal_witness_artifact -- \
  --raw results/raw/offdiagonal_witness/full/evaluation \
  --output results/derived/offdiagonal_witness.json
buck2 run //experiments:make_offdiagonal_witness_paper_artifacts
buck2 run //experiments:make_closed_rate_artifact
```

The actual-autodiff benchmark is a separate target with an explicit host
PyTorch dependency. Inspect its configured dependency before execution:

```bash
buck2 cquery //experiments:run_autodiff_systems
buck2 run //experiments:run_autodiff_systems -- \
  --config experiments/configs/autodiff_systems.yaml \
  --profile smoke --seed-set development \
  --output-root results/raw
```

On this host the cquery fails through `fbcode//caffe2:torch` and
`fbsource//third-party/python/3.12:python-for-embedding` with a Starlark call
stack overflow. After verifying that exact failure, preserve the deterministic
non-result without linking PyTorch:

```bash
buck2 run //experiments:record_autodiff_systems_not_run -- \
  --config experiments/configs/autodiff_systems.yaml \
  --profile full --seed-set development \
  --output-root results/raw --record-buck-torch-blocker
```

This record has `status: not_run`, executes no timing, and must not be described
as a systems result.

Additional deterministic manuscript generators are all Buck binaries:

```bash
buck2 run //experiments:make_balanced_benchmark_artifact
buck2 run //experiments:make_certification_audit
buck2 run //experiments:make_certified_tanh_artifact
buck2 run //experiments:make_covertype_horizon_artifact
buck2 run //experiments:make_curvature_phase_diagram_artifact
buck2 run //experiments:make_linear_bound_artifact
buck2 run //experiments:make_offdiagonal_witness_paper_artifacts
buck2 run //experiments:make_theory_scaling_paper_artifacts
buck2 run //experiments:make_paper_artifacts -- --help
buck2 run //experiments:make_primary_table -- --help
buck2 run //paper:validate
```

Generators that require non-default arguments retain their normal CLI; inspect
it with `buck2 run //<package>:<target> -- --help`. The complete commands for
the existing studies are also listed in `experiments/README.md`.

`//experiments:make_revision_paper_artifacts` additionally requires the
historical raw tanh tree excluded from this compact checkout. Its first missing
input here is
`results/raw/certified_tanh/full/evaluation/corrected/seed-160/summary.jsonl`;
do not bypass that validation or replace the retained generated artifact.
