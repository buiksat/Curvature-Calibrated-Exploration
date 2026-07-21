# Closed-Rate Revision Plan

Baseline: commit `aa0e5f2625bed70bbcf2eb215ab398bd5a8620d8` on the
new branch `codex/closed-rates-20260721`.  The branch was created without
resetting the four pre-existing tracked paper changes.  Generated result and
release trees are ignored and will not be overwritten by new experiment runs.

## File map

1. `experiments/theory_metrics.py`, `tests/test_theory_metrics.py`
   - rank and spectral-tail log-determinant bounds;
   - growing-window width and dynamic-complexity bounds;
   - refresh perturbation and Pareto-cost formulas.
2. `experiments/offdiagonal_witness.py`,
   `experiments/configs/offdiagonal_witness.yaml`, focused tests
   - analytic two-action witness;
   - executed full, CG, diagonal, inflated-diagonal, and greedy policies;
   - deterministic raw JSONL and provenance-bound aggregate.
3. `experiments/theory_scaling.py`,
   `experiments/theory_scaling_compact.py`,
   `experiments/aggregate_theory_scaling.py`,
   `experiments/configs/theory_scaling.json`, focused tests
   - low-rank embedded tanh family;
   - exact/current, CG, growing-window, frozen, diagonal, and linear rows;
   - per-round theorem, excitation, certificate, solve, and cost fields.
4. Deterministic artifact generators under `experiments/`
   - seed-level aggregation, prespecified slope regressions, paired intervals,
     figures, tables, and SHA-256 sidecars.
5. `paper/main.tex`, `paper/references.bib`
   - retain the general transfer theorem;
   - add the rank-closed near-linear and growing-window corollaries;
   - add the off-diagonal witness and only executed scaling claims;
   - reposition related work after citation verification.
6. `REVISION_REPORT.md`
   - exact commands, proof status, executed/unrun cells, results, weakened
     claims, and remaining blockers.

## Gates

- No policy may read teacher or post-action audit fields before selection.
- No float64 spectral computation is labelled a certificate.
- Every table/figure value must be generated from retained raw records.
- The stronger exact stable-excitation result is included only if its vector
  martingale, strong-convexity, path, and time-uniform steps all close.
