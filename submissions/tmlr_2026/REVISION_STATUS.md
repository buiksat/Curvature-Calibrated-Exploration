# Revision status: completed study and certificate audit

Updated 2026-10-14. This anonymous TMLR manuscript is a revised draft, not a
submitted paper. Scientific sources are synchronized with `paper/` on
`cce-review-revisions`; the research branch holds the executable analyses and
full verification record.

## Scientific changes

- Reframed the title, abstract, introduction and conclusion around conditional
  guarantees, certificate conservatism and observed policy behavior. The paper
  makes no practical regret-improvement or large-model scalability claim.
- Added the same-history width-floor proposition, including exact actionwise
  equality and a limited-information necessity statement. It does not establish
  an ordering of adaptive policies' realized regret.
- Added direct two-sided endpoint transport and a scaled-tanh relative-weight
  certificate, with proofs and a distinction from the original factor-path
  length. The uniform bound is independent of the horizon; category weights
  provide a tighter, asymmetric comparison.
- Made the completed 600-trajectory follow-up the main empirical study. Its 294
  development/tuning trajectories are separate. All nine paired pointwise
  intervals favor the comparators over Hessian transport. Both the primary
  policy's and frozen policy's own regret bounds are vacuous.
- Retained the original near-linear study separately in the appendix, including
  its missing-raw-data and dependency-provenance limitations. Its aggregate
  evidence was not changed or pooled with the new study.
- Added clearly labeled exploratory diagnostics on all 600 saved histories:
  per-seed width-dominance variation, fixed-history alternative recommendations,
  numerical tie sensitivity and relative-certificate overhead. All 600,000
  recorded rounds passed the original numerical consistency checks during
  optimizer replay on fixed actions and rewards. This is not a new adaptive
  policy evaluation.
- Checked close related work against publisher sources. Removed two peripheral
  active claims whose 2026 sources could not be verified; their historical
  bibliography entries remain. No novelty guarantee is claimed.

The research branch's
[implementation report](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/review/post_full_revision/IMPLEMENTATION_REPORT.md)
links the data, proofs, numerical verification and research decision.

## Manuscript build

The final manuscript builds with the unmodified official TMLR style at 10pt.
It has **38 pages**, with references beginning on page 18. The compile log has
no unresolved references or citations, missing characters, overfull boxes or
LaTeX warnings. Four underfull-box diagnostics remain (three horizontal and one
vertical); inspected main-result and appendix tables fit at body font size.
The first page, theorem layout and key empirical tables were visually checked.
PDF author, title, subject, keywords, creator and producer metadata are empty.
The official template's default “under review” header does not indicate that
an actual submission has been made.

Final build artifacts in the prepared workspace:

- `/workspace/cce-build/tmlr-full-revision/main.pdf`: 642,844 bytes;
  SHA-256 `8cc566123e1fe13bdb23b5f7929f1d3bb22df9d8f847007b350b61840ddac5d7`.
- `/workspace/cce-build/tmlr-full-revision/source.zip`:
  SHA-256 `4872f6e2da31318ec7263573ec6737f49aa0d8ff6c9bb25ac453f840b8cc47a5`.

An independent clean extraction of all 45 source-archive entries rebuilt the
PDF byte for byte under the same TeX environment. Its recorder has no input
from either original checkout; all external inputs resolve to the installed
TeX distribution or the declared local TeX environment. All four official
style/licence hashes match the pinned upstream version.

The source archive contains the active LaTeX compile inputs and build
instructions. It excludes internal review documents, code/evidence supplements
and inactive legacy appendices. It is a manuscript source archive, not a
complete research reproduction bundle.

## Remaining submission work

The new relative certificate brings width overhead close to the available
frozen-reference score, but supplies no additional confidence information and
has no established end-to-end speed or adaptive-regret advantage. The recorded
research decision is to stop further adaptive experiments until a distinct
computational or statistical hypothesis is specified. The current 29-parameter
NumPy study runs on CPU; two A100 GPUs do not resolve that scientific gap.

The compact Git export supports independent terminal-interval verification.
Full roundwise replay also requires the retained external raw archive (about
3.7 GB of audited inputs); a durable anonymous distribution path remains open.
The original study's absent raw trajectories cannot be recreated from its
aggregate.

The strict research supplement has not been rebuilt. Its protected-system-TeX
requirement is unchanged: `algorithm.sty` and `algorithmic.sty` are missing from
those system trees, and installing the authenticated Debian package failed
because this session has no operating-system administrator privileges. This
was not an automatic approval rejection. The compiled-source contract has been
refreshed from a diagnostic research build, but the expanded anonymous evidence
inventory and provenance handling
remain incomplete. The research release now stops before staging or publishing
when those required inputs are absent; the historical supplement is insufficient.

The authors still need to judge scientific submission readiness, review the
final anonymous materials and make the required OpenReview declarations. No
submission or venue-eligibility assertion has been made by this revision.
