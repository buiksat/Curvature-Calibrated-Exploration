# Revision Checkpoint Report

Checkpoint date: 2026-07-21

Branch: `codex/closed-rates-20260721`

Baseline revision: `aa0e5f2625bed70bbcf2eb215ab398bd5a8620d8`

## Purpose

This is a portable work-in-progress checkpoint for continuing the theory and
experiment revision on another machine. It is not a submission-ready claim.
The repository contains the manuscript, code, configurations, tests, derived
artifacts, and the compact raw evidence generated specifically for the
closed-rate and off-diagonal studies.

## Included checkpoint data

- `results/raw/theory_scaling_compact/`: 400 complete maximum-horizon runs
  (8 methods, 50 evaluation seeds) for the primary `d=128`, `r=4`, `T=2048`
  slice. Five preregistered horizon prefixes are extracted during aggregation.
- `results/raw/offdiagonal_witness/`: 3,606 complete runs: three noisy cells,
  200 evaluation seeds, six methods, plus one deterministic analytic cell.
- `results/raw/autodiff_systems/`: the hashed `not_run` record produced because
  PyTorch was unavailable on this laptop. It is not a timing result.
- `results/derived/`: the compact aggregates and provenance used by the current
  manuscript and generated paper assets.

The 5.6 GB historical raw tree, downloaded datasets, virtual environment,
LaTeX intermediates, old release directories, and old ZIP bundles are excluded.
They are not required to resume the current scaling grid. Historical aggregate
artifacts remain present under `results/derived/`.

## Theory completed

- Rank and statistical-effective-dimension log-determinant bounds.
- A fixed tangent-rank closure of the bounded-path near-linear result with an
  explicit sublinear exact-current-GGN rate.
- A current-parameter growing-window theorem with burn-in, explicit dynamic
  width bound, and sample-CVP computation/regret tradeoff.
- Predictable `O(d)` Welford path certificates for feature transfer, centering,
  linearization, and confidence schedules.
- Rank-sensitive refresh and endpoint bounds.
- A checked two-dimensional off-diagonal separation proposition.

The stronger exact-current stable-excitation theorem is intentionally omitted.
The unresolved normal-cone, time-uniform vector-martingale, and path-rate steps
are recorded in `THEORY_BLOCKERS.md`.

## Executed revision studies

### Primary theorem-scaling slice

The aggregate `results/derived/theory_scaling_primary.json` validates exactly
400 of 400 expected runs. At horizons 128 through 2048:

- exact-current dynamic-width log-log slope: `0.1057`;
- `q=1/2` window dynamic-width slope: `0.4646`;
- `q=2/3` window dynamic-width slope: `0.3338`;
- `q=1` window dynamic-width slope: `0.1057` (log-like over this range);
- exact-current mean regret is `1.80` at `T=2048` and its fitted slope is
  numerically zero over these prefixes.

These are finite-horizon scaling diagnostics, not proofs. The exact-current,
CG, and window theorem-event audit fields have zero recorded failures. Greedy
is an uncertified control and fails optimizer/centering audit fields on some
prefixes; it must not be described as theorem-certified.

### Off-diagonal witness

At `T=10000` in the deterministic analytic cell, exact full Gram, full CG, and
the action-wise reference each have cumulative pseudo-regret `0.9`. Raw
diagonal, uniformly transfer-inflated diagonal, and greedy each have cumulative
pseudo-regret `9000` up to floating-point display precision. This is a
constructive witness, not a universal full-curvature superiority claim.

## Validation on this checkpoint

- `.venv/bin/python -m pytest -q`: `234 passed`.
- `latexmk -C` followed by
  `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex`: passed.
- Compiled `paper/main.pdf`: 41 pages, anonymous title/author metadata, no Type
  3 fonts.
- Algorithm 1: page 3; Figure 1: page 7; Table 1: page 8; References: page 9.
- The only overfull box is the known 5.12 pt style-generated abstract warning.
- The build remains provisional because the official target-year AISTATS
  checklist file is not present.

## Resume on the larger CPU machine

```bash
git fetch origin
git switch codex/closed-rates-20260721
python3 -m venv .venv
.venv/bin/python -m pip install -r experiments/requirements.txt
.venv/bin/python -m pytest -q
```

Exact study commands are in `experiments/README.md`. For the remaining scaling
grid, run `experiments.theory_scaling_compact` over the unexecuted Cartesian
product of ambient dimensions `{128,512,2048}`, active ranks `{4,8,16}`, all
eight methods, and the fixed 50 evaluation seeds. Do not overwrite the retained
`d=128`, `r=4` slice unless intentionally reproducing it.

Install a compatible CPU build of PyTorch separately before running
`experiments.run_autodiff_systems`; PyTorch is optional and deliberately absent
from `experiments/requirements.txt`.

## Remaining acceptance-critical work

- Run and aggregate the remaining ambient-dimension/active-rank scaling cells.
- Run the actual-autodiff systems benchmark on hardware with PyTorch; report
  only measured results.
- Integrate the retained scaling aggregate and off-diagonal generated assets
  into the manuscript experiment narrative and regenerate the primary layout.
- Add faithful published neural-bandit baselines or keep the corresponding
  limitation explicit.
- Obtain the official target-year style/checklist and revalidate the page limit.
- Rebuild and rescan the anonymous release after the manuscript and experiments
  are final.

## Provenance caveat

The retained raw runs were generated from the dirty working tree based on
`aa0e5f2`; their manifests honestly record that revision, dirty flag, original
machine, package versions, and original absolute working path. The source that
generated them is included in this checkpoint commit, but the manifests do not
pretend that the later checkpoint commit existed at execution time. Anonymous
release artifacts must be regenerated through
`tools/build_anonymous_supplement.py`, which sanitizes paths and recomputes
hashes rather than editing protected manifests in place.
