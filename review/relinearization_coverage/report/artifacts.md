# Artifacts and reproduction

## In the repository (branch `cce-relin-coverage`)

| Path | Content |
|---|---|
| `experiments/relin_coverage.py` | primary study: model class, envelopes, learner, evaluator, runner |
| `experiments/relin_policy.py` | secondary study: own-history policies on the `transport_v3` environment |
| `experiments/analyze_relin_coverage.py` | analysis from saved run records only |
| `experiments/plot_relin_coverage.py` | figures from the analysis CSV/JSON (matplotlib venv) |
| `experiments/tests/test_relin_coverage.py` | 22 verification tests |
| `review/relinearization_coverage/DEVELOPMENT_PLAN.md` | written before development runs |
| `review/relinearization_coverage/PROTOCOL.md`, `PROTOCOL.sha256` | frozen before evaluation |
| `review/relinearization_coverage/report/development.md` | every development candidate and result |
| `review/relinearization_coverage/report/development_outputs/` | development analysis summaries |
| `review/relinearization_coverage/results/` | evaluation summaries, seed- and run-level CSVs, tables, figures, manifests, archive hashes |
| `review/relinearization_coverage/report/REPORT.md` | report |
| `review/relinearization_coverage/proposed_paragraph.tex` | proposed manuscript text (not inserted in `paper/`) |

No existing module, table, figure or manuscript file was modified.

## Outside the repository

`RUNS` is `~/cce-relin-runs` on the run host. Run directories:
`primary_deterministic`, `primary_dev`, `primary_eval`, `secondary_dev`,
`secondary_eval`. Each holds one compressed `.npz` of roundwise records and
one `.json` of run metadata per seed (primary) or per policy-seed (secondary),
plus `manifest_*.json` with argv, commit, dirty flag, source SHA-256 and, for
evaluation, the protocol SHA-256. `RUNS/archives/*.tar` packs each directory;
their SHA-256 are in `results/archive_SHA256SUMS`.

Re-running a runner into an existing directory resumes: it skips seeds with a
complete record written with the same configuration and refuses partial or
mismatched records and manifests. The analysis checks every record against
the directory's manifests and counts planned seeds without a complete record
as missing.

Roundwise records sufficient to recompute every reported coverage and width
number:
- primary, per round t and action: `center`, `mu_star`, `sbar`, `s`,
  `b_sharp`, `b_original`, `q`, `remainder_current`; per round: `theta`,
  `beta_sharp`, `beta_original`, `d_th`, `vbar`, `vcur`, `gamma`, `action`,
  `reward`, replay discrepancies and argmax agreement;
- secondary, per round t and action: `center`, `sbar`, `s`, `b`; per round:
  `context`, `action`, `beta`, `d_th`, `theta_norm`; the mean table follows
  from the fixed teacher (`relin_policy.mean_table`).

## Environment

CPython 3.12.16 venv built from `experiments/requirements-python312.lock`
(`pip install --require-hashes`, `pip check` clean,
`tools/check_python_environment.py`: PASS, 13 exact pins). Figures use a
separate venv with NumPy 2.2.3 and matplotlib 3.10.8, which reads only the
analysis outputs. All runs: OPENBLAS/OMP/MKL/NUMEXPR threads = 1, at most 4
worker processes.

## Commands

```
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
PY=~/.cce-py312-venv/bin/python
# tests
$PY -B -c "import sys,pytest; sys.exit(pytest.main(['-q','-p','no:cacheprovider','experiments/tests/test_relin_coverage.py']))"
# development
$PY -B -m experiments.relin_coverage --phase deterministic --output RUNS/primary_deterministic
$PY -B -m experiments.relin_coverage --phase development --seeds 50000-50015 --output RUNS/primary_dev
$PY -B -m experiments.relin_policy --phase development --seeds 51000-51015 --widths 1 10 100 \
  --output RUNS/secondary_dev --workers 3
$PY -B -m experiments.analyze_relin_coverage select-width RUNS/secondary_dev
# evaluation (after the protocol was frozen)
$PY -B -m experiments.relin_coverage --phase evaluation --seeds 50100-50355 --output RUNS/primary_eval \
  --workers 4 --protocol review/relinearization_coverage/PROTOCOL.md
$PY -B -m experiments.relin_policy --phase evaluation --seeds 51100-51163 --widths 100 \
  --output RUNS/secondary_eval --workers 4 --protocol review/relinearization_coverage/PROTOCOL.md
# analysis and figures
SHA=$(cut -d' ' -f1 review/relinearization_coverage/PROTOCOL.sha256)
$PY -B -m experiments.analyze_relin_coverage primary RUNS/primary_eval --out OUT --expected-seeds 256 \
  --seeds 50100-50355 --expected-protocol-sha256 $SHA
$PY -B -m experiments.analyze_relin_coverage secondary RUNS/secondary_eval --out OUT --seeds 51100-51163 \
  --expected-protocol-sha256 $SHA
~/.cce-fig-venv/bin/python experiments/plot_relin_coverage.py OUT
```
