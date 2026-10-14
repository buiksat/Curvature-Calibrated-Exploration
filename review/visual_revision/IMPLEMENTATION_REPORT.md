# Explanatory visual revision

This revision uses the requested precise technical communication skill to
explain the paper with four native LaTeX figures. It changes presentation and
adds reproducible views of retained evidence; it runs no new experiment.
The formal results and original experimental evidence are unchanged in the
diff. The exact outcomes table moves from the main empirical section to the
protocol appendix.

| Figure | Question answered | Governing source |
| --- | --- | --- |
| Certificate interfaces | Which obligations connect reference confidence to the numerical score width? | `asm:abstract-transport`, `eq:transported-score-new`, `prop:reference-width-floor` |
| Abstract confidence geometry | Why can a smaller current width fail to cover a mean allowed by the reference band? | `rem:naive-width-band-counterexample`, with the explicitly illustrative slice D = log(4), beta = 1 |
| Policy outcomes | How do all evaluated policies compare within each condition? | All 12 mean outcomes and nine paired intervals in the full follow-up aggregate |
| Bound scale | How large are the mean own-history theorem bounds relative to the deterministic cap? | Terminal bound decomposition and drift/reference diagnostics for Hessian and frozen reference in all three conditions |

The schematic arrows mean conditional certificate comparisons. The geometric
ellipses are metric unit balls, not two asserted statistical confidence sets.
The naive candidate misses the permitted mean in the abstract construction;
the figure does not claim such a failure occurred in the study.

The empirical charts use all prespecified conditions, stable method names,
distinct markers as well as colors, and common scales within each comparison.
The outcome intervals remain pointwise paired intervals, without multiplicity
adjustment. Changing W also changes the reward task. The bound chart displays
log10(arithmetic mean RHS / cap), using each policy's own histories, rather than
averaging logarithms or removing a term from another policy's trajectory.

## Reproduction and verification

`tools/make_transport_explanatory_figures.py` generates two PGFPlots sources,
three CSVs and a provenance record from three fixed evidence files. Original
input hashes, selectors, interval definitions, the bound transformation and
output hashes are recorded in the provenance JSON. Anonymous package mode uses
the existing authenticated metadata transformation; scientific values are
unchanged. The two manually authored diagrams are separately identified and
pinned as schematics, not described as regenerated empirical evidence.

The first outcome render exposed incorrect TikZ coordinate handling for the
interval caps. The plotted endpoint data were correct; explicit data-coordinate
cap segments repaired the rendering. The corrected images were viewed, and an
independent audit matched all 12 means, nine paired means, 18 interval endpoints
and six transformed bound values to the retained evidence. The four standalone
figures passed independent scientific and visual review before integration.

Final integrated build, archive, regression and page-inspection results are
recorded in `submissions/tmlr_2026/REVISION_VALIDATION.md`. The retained raw-data
limitations remain as disclosed in the paper. No new model review or TMLR
submission was performed for this revision.
