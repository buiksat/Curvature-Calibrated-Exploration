# CODE@MIT 2026 extended abstract

> **Current status: three-page CODE@MIT paper.** Round 3 prose cuts were applied
> locally to `cce-experiments@3a51ddced09a7b13f34b7d309ea00a0c3856aadb`. The
> preceding scientific revision was based on
> `cce-experiments@5718995cae80f34b5b98b464f3d9090758be4871`.
> The final author names, order, and affiliations are unchanged; the author-review
> banner has been removed. The PDF builds to three pages including references.
> The editing/build operation was local. This subsequent source-only GitHub
> publication was separately authorized; it is not a conference submission.

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

Final PDF page count: **3**, including references. All three pages were rendered
and visually inspected. The last page has approximately 53.3 PDF points of unused
space below its final reference inside the text area, about 4.5 ordinary body-line
heights. The final LaTeX log has no unresolved references or citations and no
overfull or underfull box warnings.

The ordered cuts used Blocks 1-10 and fallbacks 11.1-11.4. Font size remains 10pt,
table typography and display spacing are unchanged, paragraph spacing is 2.5pt,
and the letter-paper margins are 0.9in. Every numbered equation/align environment,
Table 1 including its caption, the title/author block, and bibliography entries
match the starting source exactly.

`cut_for_5page.tex` preserves the removed or replaced passages as commented
starting-source lines for the later five-page version. It is not an input to the
submission build. `SHA256SUMS` covers `main.tex`, `cut_for_5page.tex`, and
`README.md`; it does not cover generated build outputs or historical records.

## Historical Round 3 editing environment

Native Git access was unavailable in the editing environment because GitHub DNS
resolution failed. The source, README, and checksum manifest were transferred
through SHA-pinned GitHub reads and matched their Git blob IDs; source and README
also matched their recorded SHA-256 values. The baseline was compiled locally
from that source and had four pages. No native checkout, Git commit, branch
update, experiment run, or locked-evidence regeneration was performed.

## Source-only GitHub publication

The three-page TeX source and commented cut archive are published byte-for-byte
from the Round 3 delivery. The author previously permitted source-only
publication when the TeX compiles. The obsolete four-page CODE PDF is removed
from the current research tree; `main.pdf` is a generated build output, not a
tracked file in this release. The local three-page PDF remains in the delivered
Round 3 bundle. Rebuild with the command above from this folder.

The release changes only `submissions/code_mit_2026/`. `cce-experiments` remains
the canonical research branch. `main` receives only the current CODE publication
files; its root README and AISTATS manuscript remain unchanged. Older preparation
records already present on a branch remain historical, not current author or
approval instructions. No experiment or locked evidence is regenerated.
