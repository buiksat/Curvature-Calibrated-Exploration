# Supported Python environment

The supported path for new review runs is direct CPython 3.12 on Linux x86_64.
It does not require Buck, an external Meta checkout, or the legacy wheel links.
Run commands from the repository root and keep environments, caches, and new
experiment outputs outside the checkout.

## Install and check

`experiments/requirements-python312.lock` pins all direct and transitive
dependencies and the SHA-256 of each selected PyPI wheel. Its six direct
dependencies retain the versions in `experiments/requirements.txt`, including
NumPy 2.2.3 and SciPy 1.15.2. These are the dependencies for new runs; the lock
does not establish the environment used to generate historical evidence.

Create a fresh environment so pip verifies each downloaded wheel:

```bash
export CCE_VENV=/tmp/cce-python312
export PYTHONPYCACHEPREFIX=/tmp/cce-python312-cache
python3.12 -m venv "$CCE_VENV"
"$CCE_VENV/bin/python" -m pip install \
  --index-url https://pypi.org/simple --only-binary=:all: --require-hashes \
  -r experiments/requirements-python312.lock
"$CCE_VENV/bin/python" -m pip check
"$CCE_VENV/bin/python" tools/check_python_environment.py
```

Choose an unused environment path. A pre-existing installation can satisfy a
pip requirement without its installed bytes being checked against the wheel
hash. The preflight checks interpreter/platform and installed package metadata;
hash verification happens during installation, not in that preflight.

The lock covers this platform only. Do not remove hashes, replace versions, or
fall back to compiling another wheel to bypass a failed installation. For a
different platform, prepare and validate a separate lock before collecting
evidence. PyTorch and the historical optional autodiff benchmark are outside
this lock.

## Validate and run

Set numerical libraries to a single thread before starting Python:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
"$CCE_VENV/bin/python" -m pytest -q tests experiments/tests
"$CCE_VENV/bin/python" paper/validate.py
"$CCE_VENV/bin/python" -m experiments.config \
  experiments/configs/transport_instantiation.yaml \
  --profile smoke --seed-set development --print
```

Each ordinary Python Buck entry point in `experiments/README.md` has a direct
module counterpart: replace `buck2 run //experiments:NAME --` with
`"$CCE_VENV/bin/python" -m experiments.NAME`. This translation does not apply to
the optional Conda shell wrapper. Use fresh external paths for `--output-root`,
`--output`, and `--selection-output`; smoke results are engineering checks.
Full experiments must pass the dependency preflight before launching workers.
Keep new evidence separate from the locked historical aggregate and sidecars.

## Historical Buck discrepancy

`experiments/requirements.txt` declares SciPy **1.15.2**. The historical
`third_party:scipy` Buck target instead selects a path named
`scipy-1.13.1-cp312-cp312-manylinux_x86_64.whl`. That path is a symlink to
`/data/repos/fbsource/third-party/pypi/scipy/1.13.1/`, not a self-contained
vendored wheel. It is dangling when the external host checkout is absent.
The tracked NumPy wheel is a regular file; the SciPy entry is different.

The legacy `third_party/BUCK`, symlink, and `SHA256SUMS` remain historical inputs.
Their checksums have not been rewritten to suggest that SciPy 1.15.2 produced
the old evidence. The active direct-Python path installs the locked 1.15.2 wheel
from PyPI and never follows the SciPy 1.13.1 link. Buck remains unsupported for
new reproducible runs until its host-cell, Prelude, and dependency problems
are independently repaired and tested; see [BUCK2_SETUP.md](BUCK2_SETUP.md).

Final-horizon paired bootstrap intervals can be recomputed from exact, ordered
per-seed regret totals, the pairing keys, and the recorded bootstrap seed,
resample count, and level. Per-seed totals alone cannot reconstruct per-round
regret-curve intervals or missing raw diagnostics. Historical aggregate
summaries do not recover those missing individual values.
