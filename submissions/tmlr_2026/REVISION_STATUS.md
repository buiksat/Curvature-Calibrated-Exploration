# Revision status: readability rewrite

Updated 2026-10-14. The anonymous manuscript and compact research supplement
have been built; no TMLR submission has been made. Scientific sources are
synchronized with `paper/` on `cce-review-revisions`.

## What changed

The abstract and introduction explain why retraining can change uncertainty
without adding observations. The theory teaches the exact-matrix case before
introducing the general protocol, then explains what each certificate and
regret factor does. The empirical section leads with findings and answers
questions about policy regret, useful bounds and recorded checks. Related work
is grouped by how methods construct uncertainty. The conclusion states the
observed comparisons directly. Repeated caveats are consolidated while their
material conditions stay with the affected claims.

Existing formal results, proofs, numerical outcomes, figure data and citations
are preserved. One introductory display specializes the existing score to
exact matrices and widths. The four figures appear on pages 3, 9, 19 and 20.
No new experiments or Fable API review were performed for this rewrite.

The research branch's
[readability revision record](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/review/readability_revision/IMPLEMENTATION_REPORT.md)
records the changes and preservation checks. Its
[validation record](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/submissions/tmlr_2026/REVISION_VALIDATION.md)
records actual executions, including earlier failures and repairs.

The final full repository regression for these frozen source and verification
bytes reports **713 passed, three skipped, zero failed**, in 368.95 seconds.
The skips concern two host-specific TeX configurations and a legacy clean-build
path; the current clean source rebuilds were verified separately. Two warnings
come from intentional duplicate-ZIP-member mutation tests, which passed.

## Main-branch build

The main mirror builds in the unmodified official TMLR style at 10pt:
**46 pages**, references beginning on page 25. There are no unresolved references
or citations, missing characters, overfull boxes or compiler warnings. Four
underfull horizontal-box and three underfull vertical-box diagnostics remain.
Final visual inspection covered pages 1–4, 7–9 and 17–20, including the opening,
theorem interpretation, comparison table, empirical prose and all four figures;
there is no clipping or overlap. Identifying PDF metadata is empty. The template's
default review header is not a submission-status assertion.

- `/workspace/cce-build/tmlr-readable-main/main.pdf`:
  685,705 bytes; SHA-256
  `a4f982c9569cf7f453b5346715f407149e1308b6f27830100abc6b38931cac2c`.
- `/workspace/cce-build/tmlr-readable-main/source.zip`:
  188,508 bytes; SHA-256
  `aa649bde2c604a27230d73e117e4f99973a928ee3ea68b93548dc6097681b959`.

An independent extraction of all 49 source members rebuilt the PDF byte for
byte under the documented local TeX activation. The recorder contains 44
archived project inputs, three regenerated inputs and 291 environment inputs;
there are no original-checkout or prior-build dependencies. All four official
style/licence pins pass. The report is
`/workspace/cce-build/tmlr-readable-main-clean/verification.json`.

## Strict research release

Use the matched research release at `/workspace/cce-build/tmlr-readable-release`:

- `main.pdf`: 685,695 bytes;
  `93538407dc6203a490d08b6f2b2d702635de491822d403ea7a951e49e1234331`.
- `source.zip`: 3,407,211 bytes, 101 members;
  `d884ec8b852490a3999162389cc1cd1897ddfe7f29f6249cb9ff60ee884bef19`.
- `supplement.zip`: 93,803,092 bytes, 178 members;
  `18ac06949e9b9a8f2c0830f4df130bcbba4846db39776a21c155f4d228fdfa53`.

The build passes layout, identity, archive-member, size and digest checks.
Its actual closure has 93 project inputs and 240 protected external inputs.
An independent clean extraction rebuilt the PDF byte for byte. All 93 project
records, 240 protected external records, four official style/licence pins and
54 vendor pins match. There are no original-checkout or prior-build inputs,
unresolved references, missing characters or overfull boxes. The log retains
four underfull horizontal boxes, three underfull vertical boxes and the existing
package-hook deprecation. The report is
`/workspace/cce-build/tmlr-readable-strict-clean/verification.json`.

Fresh extracted-supplement verification also passed: 24/24 contract checks,
588 PASS and 37 PASS_ANON ledger checks, exact artifact regeneration,
24 terminal intervals recomputed from 600 summaries, and 23 shipped tests.
Three raw/upstream checks remain NOT_EXECUTED. The run used the locked Python
environment with no inherited repository import path; its log is
`/workspace/cce-build/tmlr-readable-reviewer-verify.log`.

The strict build vendors exact runtime/source/licence files for its additional
TeX packages. Its PDF bytes differ from the main mirror's because their declared
TeX dependency sets differ; the scientific sources are synchronized. Use each
matched PDF and source archive together. The compact supplement preserves
scientific values while explicitly recording metadata anonymization and the
original/packaged digests. Its checks distinguish the original near-linear
study from the complete follow-up export.

## Publication judgment and remaining limits

Fable's preceding review recommended publication and a light readability pass.
That advisory verdict concerns the prior manuscript snapshot; it is not a fresh
review of this rewrite. The publication case remains a focused methodological
and diagnostic study. Novelty and significance remain reviewer judgments:
most ingredients are established, and empirical coverage is one synthetic model
and teacher. The same-history width comparison does not order adaptive regret.
The paper claims no practical regret improvement, end-to-end speedup or
large-model scalability.

The follow-up raw tree is retained locally, but no anonymous raw archive or
durable anonymous hosting location has been completed. Compact terminal-interval
verification does not establish raw-dependent roundwise replay. The original
study's missing raw trajectories and historical runtime gaps remain unresolved.
Broader claims need a separate research question and new evidence. The authors
must review the final materials and supply the OpenReview declarations before
submission.
