# Revision Checkpoint Report

Checkpoint date: 2026-07-22

Branch: `codex/closed-rates-20260721`

Starting revision: `df3aa4dc298e3828f857c63d00ca10442275062d`

## Current status

The Buck2 implementation, complete theorem-scaling Cartesian grid, strict
aggregation, generated paper artifacts, and manuscript integration are complete
in the current working tree.
All nine scaling cells and all 3,600 expected trajectories were validated. The
2.1 GB full-grid raw tree remains on the execution host but is intentionally
ignored by Git; the derived aggregate, its hash, and generated paper artifacts
are versioned. The retained `d=128`, `r=4`, `T=2048` primary slice was not rerun
or overwritten. The actual-autodiff benchmark remains an explicit `not_run`
because the declared Buck PyTorch dependency cannot be configured on this host.

The central regret theorem and its assumptions were not changed. The stronger
unproved stable-excitation statement remains outside the manuscript. Covertype
remains a failed appendix baseline check, and no new faithful published-baseline
claim was started.

## Buck2 support

The repository now has a pinned Buck2 manifest, standalone cell configuration,
local execution platform, host Python toolchain bindings, declared wheel hashes,
and targets for experiment libraries, both test suites, scaling execution and
aggregation, off-diagonal and closed-rate artifacts, the actual-autodiff driver,
its deterministic blocker recorder, manuscript generators, and static paper
validation. Configs and repository data are declared resources. All output
arguments in the documented commands are repository-relative.

Clean-checkout prerequisites and every supported command are in
`BUCK2_SETUP.md`; `experiments/README.md` contains the study-specific commands.
This host requires `/data/repos/fbsource`. No Python, pip, virtualenv, or direct
pytest command was used.

A clean checkout contains the Buck definitions, retained primary raw slice,
full-grid derived aggregate, and generated manuscript artifacts. It does not
contain the ignored 2.1 GB full-grid raw tree. Full-grid reaggregation therefore
requires rerunning the fixed protocol or restoring that tree from artifact
storage; tests and paper generation do not require it.

Core validated commands were:

```bash
buck2 --version
buck2 root
buck2 targets //...
buck2 test //tests:tests //experiments/tests:tests -- --timeout=1200
buck2 run //tools:pytest_runner -- -q tests experiments/tests
buck2 run //experiments:aggregate_theory_scaling -- \
  --config experiments/configs/theory_scaling.json \
  --profile full --seed-set evaluation \
  --input-root results/raw/theory_scaling_compact \
  --scope full-grid \
  --output results/derived/theory_scaling_full_grid.json
buck2 run //experiments:make_theory_scaling_paper_artifacts
buck2 run //paper:validate
```

## Host

- Buck2: `4b1af7328ff43271e1a3f23d7587680dbbb23c77`
- CPU: 22 logical Intel Xeon Platinum 8339HC CPUs
- Memory: 189,775,360,000 physical bytes; 176 GiB displayed by the OS
- Accelerator: NVIDIA PG509-210, 81,920 MiB, driver 580.126.09
- Scaling execution: CPU, with `OMP_NUM_THREADS=1`,
  `OPENBLAS_NUM_THREADS=1`, and `MKL_NUM_THREADS=1` on new evaluation shards
- Python toolchain: platform010 CPython 3.12, invoked only by Buck2

## Scaling execution and coverage

The development smoke used the unexecuted `d=128`, `r=8`, development seed 40
cell. Exact current took 82.24 s internally with the default BLAS environment
and a 3.25 GB process high-water mark; the separate one-thread seed-41 smoke
took 59.66 s wall time. Full CG took 64.26 s internally, used a 3.31 GB
high-water mark, and made
4,192,256 sample-CVPs. A worst-cell smoke at `d=2048`, `r=16` took 194.55 s for
full CG with a 2.96 GB high-water mark. Those development records are separate
from evaluation.

The local evaluation tree contains 3,600 maximum-horizon run directories and
10,800 raw SHA-256 sidecars. The 3,200 newly executed shards also have hashed
timing logs. The ignored raw scaling tree is 2.1 GB; the ignored timing-log tree
is 25 MB. Strict aggregation reports exactly nine cells and 3,600 runs, with no
missing, duplicate, unexpected, or hash-failing run. No scaling cell is unrun.

The separate aggregate is
`results/derived/theory_scaling_full_grid.json` (about 11 MB), SHA-256:

```text
69c3d8cc7d6f2c588963b2af8b1be9a04351e1c394f2b8c84855287800b86d9d
```

It preserves seed-level regret and diagnostics as well as aggregate estimates.
The original `results/derived/theory_scaling_primary.json` remains unchanged.

## Numerical findings

The following `T=2048`, `d=2048` mean regrets use the same 50 fixed evaluation
seeds. Active-coordinate outcomes agree across ambient dimensions; diagonal
curvature changes with the ambient embedding.

| Rank | Exact | Full CG | q=1/2 | q=2/3 | q=1 | Frozen | Diagonal | Greedy |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 1.800 | 1.848 | 98.298 | 17.229 | 1.800 | 153.600 | 153.600 | 0.816 |
| 8 | 7.497 | 7.817 | 108.612 | 106.444 | 7.497 | 108.612 | 108.612 | 2.126 |
| 16 | 43.947 | 45.238 | 76.800 | 76.800 | 43.947 | 76.800 | 76.800 | 6.273 |

Exact-current regret means and paired-bootstrap 95% intervals are 1.800
[1.575, 2.073], 7.497 [6.820, 8.169], and 43.947 [42.244, 45.591] for ranks
4, 8, and 16. Their log-log regret slopes are 0.000 [0.000, 0.000], 0.134
[0.115, 0.153], and 0.818 [0.804, 0.831]. The q=1/2 regret slopes are 0.851
[0.843, 0.859], 1.000 [1.000, 1.000], and 1.000 [1.000, 1.000]; q=2/3 gives
0.309 [0.292, 0.326], 0.994 [0.993, 0.995], and 1.000 [1.000, 1.000].

Exact-current dynamic-width slopes are 0.106 [0.105, 0.107], 0.099
[0.098, 0.100], and 0.117 [0.117, 0.118]. For ranks 4/8/16, q=1/2 dynamic
width slopes are 0.465/0.383/0.406, q=2/3 gives 0.334/0.304/0.278, and q=1
matches exact current at 0.106/0.099/0.117. All fits are finite-horizon
diagnostics, not asymptotic-rate proofs.

Observed maximum rank information gains versus analytic rank bounds are
40.825/43.372, 76.795/81.199, and 149.136/151.309 for ranks 4/8/16. The
pre-action excitation-floor minimum is 13.500 in every rank; maxima are
6397.874, 3199.437, and 1600.219. Across theorem methods, maximum optimizer
residuals are `1.216e-6`, `2.448e-5`, and `3.221`. Maximum
`psi/lambda` tightness ratios are `8.361e-6`, `7.016e-5`, and 17.457;
maximum `psi/excitation` ratios are `6.358e-4`, `3.014e-3`, and 64.689.
These are float64 audits, never certificates or enclosures.

Full CG uses one iteration per action in this construction. At `d=2048`, its
maximum relative residual is at most `1.715e-14`, maximum energy error is at
most `4.126e-15`, selected-width relative error is at most `3.796e-15`, and
each run uses 4,192,256 sample-CVPs. Exact/full-CG action disagreement rises
from 0.00082 to 0.00630 to 0.03343 with rank; paired final-regret differences
are 0.048 [-0.027, 0.132], 0.320 [0.064, 0.569], and 1.291
[0.798, 1.822].

At `d=2048`, mean complete-run seconds for exact/full-CG/diagonal are
136.74/305.04/225.73 at rank 4, 151.93/306.12/233.72 at rank 8, and
179.63/331.46/252.85 at rank 16. The largest measured process high-water mark
anywhere in the new grid is 3,714,514,944 bytes. Runtime intervals reflect
concurrent shard contention and are not matched-wall-clock policy comparisons.

## Theorem-event audits

The retained `d=128`, `r=4` primary theorem methods have zero failures. At
rank 4, full CG has one optimizer-residual field failure at each of `d=512` and
`d=2048`. At rank 8, q=1/2, frozen, and diagonal each have one optimizer field
failure per ambient dimension. At rank 16, every theorem method has 140 failed
field instances per cell: 49 optimizer, 46 `psi`-excitation, and 45
`psi`-lambda. Greedy is uncertified and has 13,767 failed field instances over
the full grid. Consequently, ranks 8 and 16 cannot be described as uniformly
theorem-event verified.

Greedy often has lower regret, but it is an uncertified control. The
off-diagonal witness remains existential: it does not establish uniform
superiority of full curvature.

## Actual-autodiff systems benchmark

The host alias `fbsource//third-party/pypi/torch:torch` exists, but
`buck2 cquery //experiments:run_autodiff_systems` fails through
`fbcode//caffe2:torch`, `fbcode//caffe2:_torch`, and
`fbsource//third-party/python/3.12:python-for-embedding`. Evaluation of
`feature_rollout_utils.bzl` ends with `Starlark call stack overflow`.

No undeclared PyTorch was installed and no timing was fabricated. Buck2 wrote
the deterministic current-host full-profile status under
`results/raw/autodiff_systems/full/development/seed-31`; it records
`reason_code: missing_buck_dependency`, `timing_executed: false`, and
`numerical_result_reportable: false`, with a valid SHA-256 sidecar. Both the
smoke and configured 131,841-parameter benchmark are unrun.

## Manuscript and artifacts

Buck2 regenerated the full-grid figure/table, off-diagonal figure/table, and
closed-rate artifact. Every new full-grid artifact validates the aggregate and
its sidecar before generation; its provenance names the aggregate hash above.
The main paper now contains the full-grid figure and table, while the
off-diagonal witness and broader legacy audit figures/tables remain in the
appendix. Numerical values are generated, not copied into TeX.

`//experiments:make_revision_paper_artifacts` correctly refuses to regenerate
its retained historical artifact because this compact checkout excludes
`results/raw/certified_tanh/full/evaluation/corrected/seed-160/summary.jsonl`.
That missing raw tree is recorded as a blocker; validation was not bypassed.

The direct LaTeX build passed after `latexmk -C`. `paper/main.pdf` has 42 pages;
Algorithm 1 is on page 3, Figure 1 and Table 1 are on page 7, and references
begin on page 9. Ghostscript renders all pages, reports only Type 0/Type 1 font
resources, and confirms empty title/author metadata. The sole overfull warning
is the pre-existing 5.12 pt style-generated abstract box at the environment
boundary; there are no content-generated overfull boxes. `pdfinfo`, `pdffonts`,
and `pdftotext` are not installed, so Ghostscript `pdf_info.ps`, `nullpage`,
`txtwrite`, and `PDFDEBUG` were used for the corresponding checks. The build is
still provisional because the official target-year AISTATS checklist is absent.

## Validation

- `buck2 test //tests:tests //experiments/tests:tests -- --timeout=1200`: two
  targets passed, no failures.
- Combined Buck-built runner: 241 passed, one pre-existing unclosed-file
  `ResourceWarning` in `test_anonymous_supplement.py`.
- Full grid: 9/9 cells and 3,600/3,600 raw runs validated; aggregate sidecar
  matches.
- Retained primary: 400/400 runs revalidated in validation-only mode and not
  overwritten.
- Paper static validation: 154 labels with no duplicates, 112 reference
  targets with none unresolved, and 34 citation keys with none missing.
- LaTeX: successful 42-page build; no Type 3 fonts; required page positions
  preserved.
- `git diff --check`: passed.

## Changed files

The changed paths are:

- Buck/toolchain: `.buck2`, `.buckconfig`, `.buck/fbsource_cell/`, `BUCK`,
  `PACKAGE`, `third_party/`, `tools/BUCK`, `tools/build_defs`, and
  `tools/pytest_main.py`.
- Targets/tests: `experiments/BUCK`, `tests/BUCK`, `experiments/tests/BUCK`,
  both `run_buck_pytest.sh` wrappers, `tests/test_theory_scaling.py`,
  `tests/test_theory_scaling_paper_artifacts.py`, and
  `experiments/tests/test_autodiff_systems.py`.
- Experiment code: `experiments/aggregate_theory_scaling.py`,
  `experiments/theory_scaling_compact.py`,
  `experiments/run_autodiff_systems.py`, and
  `experiments/make_theory_scaling_paper_artifacts.py`.
- Results: `results/derived/theory_scaling_full_grid.json` plus sidecar. The
  eight new raw evaluation cells, development smoke records, current-host
  autodiff `not_run` record, and hashed scheduler logs remain local and ignored.
- Paper/docs: `paper/BUCK`, `paper/main.tex`, `paper/main.pdf`, `paper/validate.py`,
  generated scaling and off-diagonal assets/provenance, `.gitignore`,
  `BUCK2_SETUP.md`, `experiments/README.md`, `RESULTS_STATUS.md`, and this report.

No main-branch or remote state was changed.

## Remaining blockers and scope gaps

- Declared Buck PyTorch cannot configure, so the actual-autodiff benchmark has
  no CPU or GPU measurements.
- The compact checkout lacks historical raw tanh inputs required by
  `make_revision_paper_artifacts`.
- The official target-year AISTATS checklist/style pack is absent.
- No external published implementation has been verified for the neural-bandit
  baselines; existing local implementations retain that explicit limitation.
- No verified interval enclosure is available for the float64 audit points.
- The anonymous release should be rebuilt and identity-scanned after the final
  branch state is settled.
- Full-grid raw trajectories are not distributed through Git; reproducing the
  aggregate requires rerunning the fixed protocol or restoring artifact storage.

## Provenance caveat

The retained primary runs honestly record their original dirty-tree revision,
machine, packages, hardware, and absolute working path. Newly executed shards
record this branch's starting commit and dirty state plus the current host and
one-thread BLAS environment. Protected manifests were not edited in place.
