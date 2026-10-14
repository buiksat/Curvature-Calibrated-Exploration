# Revision status after checked Fable feedback

Updated 2026-10-14. The anonymous manuscript and compact research supplement
have been built; no TMLR submission has been made. Scientific sources are
synchronized with `paper/` on `cce-review-revisions`.

## Current manuscript

The revision adds a short abstract confidence-band example, clarifies the
certified-region and approximation-error requirements, reduces repetition,
and explains the exact actionwise ratio's computational meaning. It adds
source-checked descriptive context-free and best-fixed-action comparisons and
makes explicit that every mechanism-table row evaluates the Hessian score on
the named behavior histories. No new experiments were run.

The strongest publication case is a focused methodological and diagnostic
study separating conditional validity, certificate conservatism and policy
behavior. Its significance remains a reviewer judgment: the ingredients are
largely established and the empirical scope is one synthetic model and teacher.
The same-history width floor does not order adaptive regret. No practical
regret-improvement, end-to-end speedup or large-model scalability is claimed.

The research branch's
[implementation and publication assessment](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/review/post_fable_revision/IMPLEMENTATION_REPORT.md)
records the revisions and remaining scientific limits. Its
[validation record](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/submissions/tmlr_2026/REVISION_VALIDATION.md)
records actual execution results, including earlier failed checks and repairs.

The final research regression run passed **694 tests**, with **3 skipped** and
no failures. An independently extracted supplement passed its advertised checks,
including reconstruction of all 24 follow-up terminal intervals and regeneration
of six artifacts. An independently extracted strict source archive rebuilt its
38-page PDF byte for byte. The research validation record retains the exact
skip reasons and toolchain warnings; these checks do not establish raw replay.

## Main-branch build

The main mirror builds with the unmodified official TMLR style at 10pt:
**38 pages**, references beginning on page 18, no unresolved references or
citations, missing characters, overfull boxes or LaTeX warnings. Eight
underfull-box diagnostics remain. The first page, analytic example and main
empirical table were visually checked; the final availability page was checked
in the strict build. PDF author, title, subject, keywords, creator and producer
metadata are empty. The template's default review header is not a submission
status assertion.

- `/workspace/cce-build/tmlr-fable-revision/main.pdf`:
  644,620 bytes; SHA-256
  `21c6e0a031d4255376806349ef570fc11fec9cc5360d8ad7e3828902718e15d5`.
- `/workspace/cce-build/tmlr-fable-revision/source.zip`:
  SHA-256 `e76c616993c646254312f4acab598373bc9c118d447f3ebccb54d51ab3088e8d`.

An independent clean extraction of all 45 source members rebuilt the PDF byte
for byte under the declared local TeX activation. The recorder has no original
checkout or build-directory dependencies. All four official style/licence
hashes match their independently pinned upstream values. The local report is
`/workspace/cce-build/tmlr-fable-main-clean/rebuild_report.md`.

## Strict research release

The research branch builds a matched PDF, source archive and anonymous compact
supplement at `/workspace/cce-build/tmlr-fable-final-release`:

- `main.pdf`: `158c98e99f2665d0c804a7f13a8c8d76fe0c6ae1d18f3c45bfae21caf3e64822`.
- `source.zip`: `da0e004d58b3198da3e3526c4c9a36921f665d60e0e4dac93d25d889ad0e5fa3`.
- `supplement.zip`: 93,693,136 bytes;
  `8be0424f9fdc98387dde264d8e2dc8fe7bb3ea3eb3438c9fdf86aa3180fff81a`.

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
