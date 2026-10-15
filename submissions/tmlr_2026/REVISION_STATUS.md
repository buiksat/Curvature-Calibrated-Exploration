# Revision status: charts replace numerical tables

Updated 2026-10-15 (UTC). The **52-page** manuscript replaces all eight numerical
result tables with charts. Scientific sources match `paper/` on
`cce-review-revisions`. No TMLR submission has been made.

Ten new figures present policy confidence intervals, fixed-history comparisons,
seed ranges, drift frequencies and logarithmic certificate diagnostics. The
outcome table is consolidated into the existing outcome chart. Original
numerical tables remain in the research supplement for exact lookup. Compact
notation and assumption tables remain as textual references.

The chart captions distinguish adaptive outcomes from fixed-history diagnostics,
confidence intervals from descriptive ranges, and trajectory summaries from
pooled observations. The generator uses retained numerical-table precision;
it adds no experimental data or new uncertainty estimates. Formal results,
proofs, configurations and experimental outcomes are unchanged.

The final manuscript is `/workspace/cce-build/tmlr-charts-main/main.pdf`; its
LaTeX archive is `/workspace/cce-build/tmlr-charts-main/source.zip`.
A clean archive extraction reproduces the PDF byte for byte. The final log has
no warnings, unresolved references, missing characters or overflowing boxes.
Every new chart was visually inspected, and every page is portrait. The
unmodified official TMLR style files pass their checksum checks.

The strict research release is `/workspace/cce-build/tmlr-charts-release`.
Research-branch records describe the
[implementation](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/review/table_chart_revision/IMPLEMENTATION_REPORT.md)
and final
[validation](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/submissions/tmlr_2026/REVISION_VALIDATION.md).
The supplement verifies retained evidence; it does not replay the missing
original-study raw trajectories. No experiment or Fable API review was run for
this chart revision.
