# CODE@MIT 2026 extended abstract

> **Current status: four-page CODE@MIT candidate.** The current `main.tex` is based on
> `cce-experiments@5718995cae80f34b5b98b464f3d9090758be4871`.
> It builds successfully but occupies four pages against the three-page limit, so it is
> **PAGE-BUDGET BLOCKED**. AUTH01 is resolved as Bahram Behzadian, Meta. AUTH02,
> ledger:C01, ledger:C02, and the optional analysis decisions remain unresolved. The
> author-review banner remains, and no push, publication, or submission is authorized.

- Submission: CODE@MIT 2026, Conference on Digital Experimentation at MIT.
- Deliverable: standalone extended abstract, maximum 3 pages.
- Relationship to the full manuscript: this is a short, audience-specific derivative of the canonical AISTATS manuscript under `paper/`; no file under `paper/` was edited.
- Source repository: `https://github.com/buiksat/Curvature-Calibrated-Exploration`.
- Canonical source branch: `cce-experiments`.
- Resolved starting SHA: `df8802dfacc1f8db61a0bbad9442f2c3037a8338`.
- Generated: 2026-09-09.
- Controlled experiment source/review revision: `93eaa537d2702d5d18b05905913b0b879e3d608f` (the completed nonlinear transport-instantiation study documented in `TRANSPORT_INSTANTIATION_COMPLETION_REPORT.md`).

## Empirical provenance

The CODE paper uses only the completed controlled scaled-tanh experiment. Numerical claims are sourced from unchanged committed evidence:

- `paper/tables/transport_instantiation_validity.tex`: 50/50 cellwise reference-confidence and optimism diagnostics, exact Clopper-Pearson interval, zero deterministic failures, endpoint-distance scale, and displayed theorem RHS summaries.
- `paper/tables/transport_instantiation_tightness.tex`: `D_Q / D_quad` ratios and bound-tightness summaries.
- `paper/tables/transport_instantiation_performance.tex`: primary-horizon mean pseudo-regret and paired comparison intervals.
- `review/transport_instantiation/locked_claims.json`: independent recomputation of selected locked claims and full-grid completion metadata.
- `review/transport_instantiation/aggregate/bound_nonvacuity.jsonl`: per-cell bound/nonvacuity summaries derived from the locked aggregate.
- `results/derived/transport_instantiation/full_aggregate.json`: locked aggregate, SHA-256 `0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02`.

The full raw experiment tree is not committed. This submission therefore does not claim independent raw-data reproduction.

The unfinished realistic Covertype benchmark and its Digits smoke evidence are excluded. No smoke, pilot, approximate-operator, CG, Nystr\"om/Lanczos, legacy MNIST/Covertype/Wheel, or matrix-free scalability result appears in this submission.

## Build

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

A plain professional `article` format is used; no venue-specific LaTeX template is invented.

Final PDF page count: **3**.
