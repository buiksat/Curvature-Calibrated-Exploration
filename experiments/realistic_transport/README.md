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
  --prepared-artifact /tmp/cce-realistic-transport/digits.npz
```

Aggregate and render standalone evidence:

```bash
buck2 run //experiments/realistic_transport:aggregate -- --profile smoke
buck2 run //experiments/realistic_transport:artifacts
```

Run focused tests with:

```bash
buck2 test //experiments/realistic_transport:tests -- --timeout=1200
```

The Covertype pilot, tuning, selection lock, and evaluation commands are
defined by `../REALISTIC_TRANSPORT_PROTOCOL.md`. Digits output is engineering
evidence only.
