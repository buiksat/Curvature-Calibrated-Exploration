# Realistic transport command log

The source branch was `cce-experiments` at
`d00594a80517cdca84f97a95056669f48c6a1be4`. A live remote query failed because
this host could not resolve `github.com`. Work was performed on
`codex/realistic-transport-benchmark`. Nothing was pushed and no pull request
was opened.

The implementation freeze is
`40c39fa3e7b0d7562f308c25a02b7059391614c4`. This supersedes the initial
freeze commit after the aggregate source inventory was made self-contained.

## Validation

| Command | Status | Result |
|---|---:|---|
| `buck2 test //tests:tests //experiments/tests:tests -- --timeout=1200` | 3 | The configured Buck2 binary failed before test execution because its API lacks `BuckRegex.any_match`. |
| `$CCE_COMPAT_BUCK2 ... test //tests:tests //experiments/tests:tests //experiments/realistic_transport:tests` | 0 | All three Buck test targets passed. |
| `$CCE_COMPAT_BUCK2 ... pytest ...` | 0 | 67 focused tests passed. |
| `buck2 run //paper:validate` | 3 | Same Buck2/Prelude mismatch. |
| `$CCE_COMPAT_BUCK2 ... run //paper:validate` | 0 | Static manuscript validation passed. |
| `python3 tools/verify_transport_committed_evidence.py` | 0 | 0 failures; all old locked evidence remained valid. |
| `make pdf` | 2 | `cleveref.sty` is missing. The committed PDF SHA-256 remained unchanged. |

## Data and execution

The official Covertype command failed after 4.94 seconds because DNS could not
resolve the upstream Figshare host. See `covtype_not_run.json`. No Covertype
pilot, tuning, selection, or evaluation result was inspected.

The Digits smoke artifact contains 1,797 rows, 64 source features, and 10
classes. Its semantic digest is
`53cf2b3127206ecf19ef642ee9de0fd6c942f7ed600f543ac13238b898b0df50`.
The clean-revision smoke run completed all 39 cells and 1,248 rounds in 82.10
seconds with peak process RSS of 556,856 KiB. Strict aggregation accepted all
cells. Two consecutive artifact generations were byte-identical.

The smoke raw inventory digest is
`2de4bcb43bb10aec4cc9d7d4a16966696e5cb028dd954eddcb3f9a5c96705e81`.
The result is engineering evidence only.

## Unrun full profile

```bash
$CCE_COMPAT_BUCK2 run //experiments/realistic_transport:study -- \
  --profile full \
  --prepared-artifact "$CCE_DATA_ROOT/prepared/covtype_realistic_v1.npz" \
  --selection review/realistic_transport/SELECTION.json
```

A conservative extrapolation from the Digits smoke gives 167.03 sequential
CPU-hours, 41.76 idealized wall-hours at four workers, and 4.91 GiB of raw
records for evaluation alone. This is not a Covertype pilot estimate. The
current study driver executes cells sequentially, so external sharding is
required to realize the four-worker wall-time estimate.
