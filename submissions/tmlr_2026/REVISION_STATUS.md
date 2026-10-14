# Revision status: explanatory figures

Updated 2026-10-14. The anonymous manuscript and compact research supplement
have been built; no TMLR submission has been made. Scientific sources are
synchronized with `paper/` on `cce-review-revisions`.

## Current manuscript

Four figures explain the paper's argument: the conditional certificate
interfaces (page 2), an abstract confidence-geometry example (page 7), all
policy outcomes and paired comparisons (page 15), and the scale of mean
own-history bounds relative to the deterministic regret caps (page 16).
The detailed outcome table remains in the appendix. The figures retain native
10pt text, uncertainty definitions and the full set of evaluated conditions.
The diagrams state their analytic scope. No new experiments were run.

The strongest publication case remains a focused methodological and diagnostic
study separating conditional validity, certificate conservatism and policy
behavior. Its significance remains a reviewer judgment: the ingredients are
largely established and the empirical scope is one synthetic model and teacher.
The same-history width floor does not order adaptive regret. No practical
regret-improvement, end-to-end speedup or large-model scalability is claimed.

The research branch's
[visual revision record](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/review/visual_revision/IMPLEMENTATION_REPORT.md)
records the figure claims and evidence sources. Its
[validation record](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/submissions/tmlr_2026/REVISION_VALIDATION.md)
records actual execution results, including earlier failed checks and repairs.

The final full repository regression run passed **713 tests**, with **three
skipped**, zero failures and two expected duplicate-ZIP mutation warnings. An
independently extracted supplement passed its advertised checks, including
reconstruction of all 24 follow-up terminal intervals and exact regeneration
of both six-artifact sets. Its ledger reports 588 PASS, 37 PASS_ANON and three
NOT_EXECUTED checks. These checks do not establish raw replay.

## Main-branch build

The main mirror builds with the unmodified official TMLR style at 10pt:
**40 pages**, references beginning on page 20, no unresolved references or
citations, missing characters, overfull boxes or LaTeX warnings. Nine
underfull-box diagnostics remain. All four new figures were inspected both
individually and on their final pages. PDF author, title, subject, keywords,
creator and producer metadata are empty. The template's default review header
is not a submission status assertion.

- `/workspace/cce-build/tmlr-visual-main/main.pdf`:
  660,363 bytes; SHA-256
  `0e910f8fc70aa07238a10937b2028a4b1e426a6d81054430fef470fa68d5eedb`.
- `/workspace/cce-build/tmlr-visual-main/source.zip`:
  181,445 bytes; SHA-256
  `cf1e8731e1d4e9763134974d1c55384d4efa9b9089dfa424c9fe3f9612d435c4`.

An independent clean extraction of all 49 source members rebuilt the PDF byte
for byte under the declared local TeX activation. The actual recorder contains
44 archived project inputs, three regenerated inputs and 291 environment
inputs; it has no original-checkout or prior-build dependencies. All four
official style/licence hashes match their independently pinned upstream values.
The local report is `/workspace/cce-build/tmlr-visual-main/verification.json`.
Its broad source-hash inventory is distinct from the actual compiler closure.

## Strict research release

The research branch builds a matched PDF, source archive and anonymous compact
supplement at `/workspace/cce-build/tmlr-visual-release`:

- `main.pdf`: 660,312 bytes;
  `c50a5bfbd19b2cbe63766c1c07e70fa2f087f8a21bcf118d793bb63d3485b659`.
- `source.zip`: 3,386,125 bytes, 101 members;
  `9fe9eb68c01829c7c34210282df70293afaf9a983f40ad15b99139d8eed5e935`.
- `supplement.zip`: 93,770,633 bytes, 178 members;
  `a2c63ce2bbacb5b52d17dc7f7339200a4cf47163aa1c2c4a23c17cc9cb45f95a`.

An independent clean extraction rebuilt the strict 40-page PDF byte for byte.
The final release PDF, source archive and all 240 protected external input
records match that independently checked candidate exactly. The final rebuild
changed only supplement verification tools. The strict build has nine
underfull-box diagnostics and one existing package-hook deprecation warning;
no unresolved references, citations, missing characters or overfull boxes.

Use these matched release files together. The strict build vendors exact
runtime/source/licence files for its additional TeX packages and records every
protected external compiler input. Its PDF bytes differ from the main mirror's
build because their declared TeX dependency sets differ; the scientific sources
are synchronized. The exact archives and checks are described in the research
branch's release README and validation record.

The compact supplement covers the complete follow-up export and authoritative
exploratory outputs. Metadata-anonymized copies have explicit transformation
records and original/packaged digests; scientific values are preserved. The
original study's aggregate evidence is kept distinct from the follow-up.

## Remaining submission work

The follow-up raw tree is retained locally, but no anonymous raw archive or
durable anonymous hosting location has been completed. Compact terminal-interval
verification does not establish raw-dependent roundwise replay. The original
study's missing raw trajectories and historical runtime gaps remain unresolved;
the follow-up does not recover them.

Broader adaptive or computational claims would require a distinct research
hypothesis and new evidence. Two A100 GPUs do not resolve that conceptual issue
for this CPU-based 29-parameter study. The authors must review the final
materials and make the required OpenReview declarations before submission.
