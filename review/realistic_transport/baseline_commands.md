# Realistic transport baseline command ledger

Recorded on 2026-08-24 before benchmark implementation.

The clean source checkout was `cce-experiments` at
`d00594a80517cdca84f97a95056669f48c6a1be4`. The local
`origin/cce-experiments` ref matched. A live `git ls-remote` check could not run
because DNS resolution for `github.com` was unavailable. Work continues on
`codex/realistic-transport-benchmark` from that exact commit.

## Results

| Command | Status | Wall time | Peak RSS | Result |
|---|---:|---:|---:|---|
| `python tools/verify_transport_committed_evidence.py` | 126 | 0.00 s | 776 KiB | The `python` executable was unavailable. |
| `python3 tools/verify_transport_committed_evidence.py` | 0 | 13.53 s | 436136 KiB | Passed with 0 failures. The verifier retained its declared raw-input and rendering `NOT_EXECUTED` entries. |
| `buck2 test //tests:tests //experiments/tests:tests -- --timeout=1200` | 3 | 13.32 s | 317324 KiB | No tests ran. The host Prelude requires `BuckRegex.any_match`, which the active Buck2 API does not expose. |
| `buck2 run //paper:validate` | 3 | 0.10 s | 87720 KiB | Failed on the same Buck2/Prelude incompatibility. |
| `python3 paper/validate.py` | 0 | 0.22 s | 54656 KiB | Non-Buck execution of the same validation source passed. |
| `make pdf` | 2 | 0.38 s | 29024 KiB | `cleveref.sty` is missing. The committed PDF remained unchanged and matched `paper/main.pdf.sha256`. |
| `$CCE_PYTHON_BOOTSTRAP -m pytest -q tests experiments/tests` | 1 | 95.81 s | 1629432 KiB | Non-Buck fallback: 113 passed, 2 failed. Both failures were byte-regeneration differences in five tightness CSV files under NumPy 2.2.1. Buck pins NumPy 2.2.3, so this is not classified as an equivalent clean baseline. |

The fallback runtime reported Python 3.14.7+meta, NumPy 2.2.1, SciPy 1.16.1,
scikit-learn 1.6.1, pytest 7.2.2, and psutil 7.2.2. The host has 44 logical
CPUs and 353 GiB of physical memory. No source or locked evidence file changed
during these commands.
