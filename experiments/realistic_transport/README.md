# Realistic transport benchmark

This package is isolated from the source inventory used by the repository's
locked transport-instantiation evidence. Do not move these modules into the
legacy `experiments` library without updating that evidence policy.

Prepare Covertype outside Git:

```bash
export CCE_DATA_ROOT=/path/to/external/cache
buck2 run //tools:prepare_covtype_benchmark -- \
  --dataset covtype \
  --output "$CCE_DATA_ROOT/prepared/covtype_realistic_v1.npz"
```

This command creates a candidate artifact and manifest only. It does not
authorize a Covertype run. After independent review, record the approved
candidate in a repository-relative data-lock JSON, set
`required_semantic_digest` and `approved_data_lock` in every Covertype profile's
`dataset` override, and commit those exact bytes with the scientific sources as
freeze F. Leave the smoke profile's resolved configuration unchanged.
Preparation is write-once: if the artifact, manifest, sidecar, or a dangling
symlink at any of those paths already exists, the command stops before loading
or fetching data. Choose a fresh output path instead of replacing evidence.

Keep interpreter bytecode outside the repository while preparing F. Set
`PYTHONPYCACHEPREFIX` to a project-external directory, or set
`PYTHONDONTWRITEBYTECODE=1`. Before F, audit ignored and untracked files and
remove only generated `__pycache__`, `.pyc`, and `.pyo` files. The freeze check
recursively covers importable and build-source suffixes, repository-local Buck
configuration and package files, Buck binary selectors, bundled wheels, and
the two Buck test drivers. It records every present entry's Git-compatible mode
and rejects a relevant path added after F. It rejects every symlink outside the
three explicit output roots except the exact build/dependency links already
required at START; those links bind their mode and stored link text without
following their targets. Startup hooks, dependency-shadow packages, bytecode,
and package-member symlinks fail even if committed before F.

This freeze covers only repository-local inputs. `/etc/buckconfig*`,
`~/.buckconfig*`, and bytes in the external fbsource checkout are outside F and
require separate machine/build-environment attestation before production use.

Prepare the smoke-only Digits artifact:

```bash
buck2 run //experiments/realistic_transport:prepare_dataset -- \
  --dataset digits \
  --output /tmp/cce-realistic-transport/digits.npz
```

Run the fixed 39-cell smoke grid:

```bash
buck2 run //experiments/realistic_transport:study -- \
  --profile smoke \
  --prepared-artifact /tmp/cce-realistic-transport/digits.npz \
  --output-root /tmp/cce-realistic-transport/raw
```

Aggregate and render standalone evidence:

```bash
buck2 run //experiments/realistic_transport:aggregate -- \
  --profile smoke \
  --raw-root /tmp/cce-realistic-transport/raw \
  --output /tmp/cce-realistic-transport/aggregate.json \
  --statistics-csv /tmp/cce-realistic-transport/statistics.csv
buck2 run //experiments/realistic_transport:artifacts -- \
  --aggregate /tmp/cce-realistic-transport/aggregate.json \
  --config experiments/configs/realistic_transport_covtype.yaml \
  --profile smoke \
  --raw-root /tmp/cce-realistic-transport/raw \
  --review-root /tmp/cce-realistic-transport/review
```

Preparation, raw-run/failure writing, aggregation, tuning, selection, and
artifact generation refuse to overwrite an existing evidence output,
directory, or dangling symlink, including one created after preflight. File
writers fsync a unique same-directory temporary and install it without
replacement. Artifact generation publishes its staged directory with Linux
`renameat2(RENAME_NOREPLACE)`, reloads the complete raw grid,
repeats aggregation and authorization checks, and requires the supplied
aggregate to match that independently reconstructed value. A standalone JSON
file and its sidecar are not sufficient input. Use a fresh output path for each
run.

Run focused tests with:

```bash
buck2 test //experiments/realistic_transport:tests -- --timeout=1200
```

All Covertype entry points require `--data-lock` and `--freeze-revision`.
Evaluation profiles also require `--selection` and
`--selection-lock-revision`. The full gate order and lock schemas are defined
by `../REALISTIC_TRANSPORT_PROTOCOL.md`. Digits output is engineering evidence
only. `full` and `resource_fallback` accept only their complete ordered task,
method, and seed grids through the study entry point. The one-cell runner
rejects both profiles. Every worker uses exactly one BLAS/OpenMP thread and
verifies actual thread-pool state before and after numerical work.
