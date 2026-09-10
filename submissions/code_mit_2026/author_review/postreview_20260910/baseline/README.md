# CODE@MIT 2026 extended abstract

> **Current status: revised draft for author review.** The current `main.tex` is the proposed revision prepared from `cce-experiments@1eb91932d89bb5df428052767884e199f2abfe3b`, now published to GitHub at the author's request. It still contains the author-information marker and is not submission-ready.
>
> Start with the [author-review index](author_review/README.md), [change log](author_review/records/CHANGELOG.md), and [approval ledger](author_review/records/AUTHOR_APPROVAL.md). The original drafting provenance below is preserved; its historical SHAs have not been relabelled as revision or publication SHAs.

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
