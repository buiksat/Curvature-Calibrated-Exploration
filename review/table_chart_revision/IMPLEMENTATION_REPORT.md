# Numerical tables replaced with charts

The manuscript now uses charts for all eight numerical result tables. The
three compact textual tables (notation, assumptions, certificate interfaces)
remain as reference material. The original numerical tables stay unchanged in
the reproducibility supplement for exact lookup.

| Former table | Reader-facing replacement | PDF page |
| --- | --- | ---: |
| Follow-up outcomes | Existing policy means and paired confidence intervals | 20 |
| Follow-up drift/bounds | Maximum distance and threshold-frequency panels; existing bound-scale chart | 22, 21 |
| Same-history recommendations | Separate condition panels; behavior policy's own score ringed | 50 |
| Mechanism variation | Median dots and minimum–maximum seed ranges | 51 |
| Relative certificates | Width-inflation and immediate-regret panels | 52 |
| Original-study validity | Logarithmic distance and terminal-bound comparisons; common coverage counts stated once | 36 |
| Original-study performance | Mean/paired-interval panels, plus median and IQR panels | 38, 47 |
| Original-study tightness | Path ratios/exclusions, multiplier/error summaries, and terminal bound ratios | 40, 48, 49 |

Ten new figures use native body-size text in portrait floats, without resizing.
Color and marker shapes distinguish series. Unconnected points represent
categorical conditions. Shared scales support comparisons within a figure;
logarithmic axes are labeled explicitly. Confidence intervals are distinguished
from descriptive seed ranges. Fixed-history recommendations remain distinct
from adaptive policy outcomes. Captions and footers retain aggregation
populations, sample sizes, missing-raw-data limits and other qualifications.

`tools/make_transport_table_charts.py` deterministically renders seven reviewed
numerical-table inputs at their published precision; the eighth table already
has a full-precision outcome chart. Fixed input hashes reject changed values.
The new provenance record binds the generator, inputs and all ten outputs.
The original table generators and numerical values remain unchanged.

The package includes the new generator and charts. Its shell verifier now
reads the complete pinned-path list: an early-exiting grep previously caused
a broken pipe under `pipefail` when the list grew. A large-inventory regression
test checks that recognized pinned files remain accepted. Its independent byte pins,
regeneration checks and compiler-input inventory cover the replacements.
Layout mutation tests now exercise all ten charts, including shrink commands,
missing inputs and bypassed figure wrappers. New tests independently compare
all data marks against the original table cells and reject altered inputs,
changed points with rewritten provenance and an unreviewed generator.

## Validation

The main manuscript is 52 pages. Every new chart was inspected at rendered
page size, including a second pass after resolving crowded panel labels.
The clean main source-archive rebuild is byte-identical to the delivered PDF;
its final log has no warnings, unresolved references, missing characters or
overfull boxes. The official TMLR style files are unchanged.

Preservation checks find 206 previously tracked scientific files unchanged,
including implementation, configurations, experimental results, all original
tables and figures, formal theory/proofs and the historical PDF. All 218
numerical-ledger entries are unchanged. Seventeen manuscript/chart files match
between the research checkout and main mirror.

Release artifacts and detailed logs live outside the repositories under
`/workspace/cce-build/tmlr-charts-*`. Final package and regression results are
recorded in `submissions/tmlr_2026/REVISION_VALIDATION.md`.

No new experiments or external model review were run, and no submission was
made. Retained aggregate precision is not new measurement precision; original
raw-trajectory replay remains outside this revision.
