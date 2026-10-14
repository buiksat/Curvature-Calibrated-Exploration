# Revision status: checked Fable readability fixes

Updated 2026-10-14. The manuscript now applies the checked advice from the fresh
Fable readability review. It has **47 pages**, with scientific sources
synchronized with `paper/` on `cce-review-revisions`. No TMLR submission has been
made.

## What changed

A notation table collects the matrices, widths and score terms. A chronological
guide precedes the formal protocol; finite-action readers can skim general
selection details while retaining the timing and certificate assumptions. The
abstract and policy descriptions explain their terms locally. The empirical
section gives the existing mean bound magnitudes with explicit own-history
populations. The outcomes chart labels its zero comparator “Hessian = 0.” The
first render exposed a line crossing that label; the final annotation sits
clear of the zero guide.

Existing formal statements, proof blocks, displayed theory equations, scientific
data and plotted outcomes are preserved. The added numbers describe means,
not individual-trajectory ratios. Comparisons between policies with different
histories are not treated as a decomposition of transport's effect. The
near-linear corollary remains a statement about an asymptotic scaling family.

The research branch records the
[implementation](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/review/readability_followup/IMPLEMENTATION_REPORT.md),
[checked advice](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/review/readability_assessment_fable/CHECKED_ADVICE.md)
and [validation](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/submissions/tmlr_2026/REVISION_VALIDATION.md).
No experiment or new Fable API request was run for this implementation. The
prior review is advisory and is bound to its recorded earlier source snapshot.

## Main-branch build

The final build at `/workspace/cce-build/tmlr-clarity-final-main` uses the
unmodified official TMLR style at 10pt. The notation table is on page 5, figures
on pages 3, 10, 20 and 21, and references begin on page 26. Final visual checks
cover the abstract, notation, protocol guide, bound-magnitude explanation and
revised labels. The final label clears the guide; no clipping or data overlap
was observed. The other figure pages are unchanged in rendering from the
inspected candidate.

- `main.pdf`: 691,418 bytes; SHA-256
  `7ee8ab1b323434333108c88382c0f457fc3ea59e5f3e768eab1df7227f50f2d5`.
- `source.zip`: 190,109 bytes, 49 members,
  672,685 unpacked bytes; SHA-256
  `1d23ab13ec6105162e99ce0b74edb04280980ec4e8ff3c209945544af093e0ff`.

A fresh independent extraction rebuilt the PDF byte for byte. All four official
style/licence pins pass. The recorder contains 44 archived project inputs,
three regenerated inputs and 291 environment inputs, with no original-checkout
or prior-build dependencies. Identifying PDF metadata is empty. There are no
unresolved references/citations, missing characters, overfull boxes or compiler
warnings; four underfull horizontal and two underfull vertical boxes remain.
The report is `/workspace/cce-build/tmlr-clarity-final-main-clean/verification.json`.
The template's default review header is not a submission-status assertion.

## Research release and regression

The matched final research release is at
`/workspace/cce-build/tmlr-clarity-final-release`:

- `main.pdf`: 691,388 bytes;
  `f3d809c81247961058fe498a25048365d3f3a3b53c3f677cbb283fafdf688a70`.
- `source.zip`: 3,412,620 bytes, 101 members;
  `1f07ef7dbdcac50b97a8783dc82653c40fc4ae2002e5a7af3fe780f1e3d20fda`.
- `supplement.zip`: 93,812,058 bytes, 178 members;
  `3635fd755e8a2af17c438ed0c702552cf26434d7ec6f59ca45658c8497850ea0`.

The strict release build passes its layout, identity, archive-member, size and
digest checks. The actual compiled closure retains 93 project inputs and 240
protected external inputs. The supplement is below the decimal 100 MB limit by
6,187,942 bytes. The strict source includes the exact declared vendor files;
its PDF bytes differ from the main mirror's because their dependency sets differ.
Use each PDF with its matching source archive.

An independent clean extraction reproduces the strict PDF byte for byte, with
all four official and 54 vendor pins passing. Its recorder has exactly the
93 project and 240 protected external inputs recorded in the manifest, plus two
generated auxiliary inputs. There are no original-checkout or user-environment
dependencies, identifying metadata, unresolved references, missing characters
or overfull boxes. Four underfull horizontal and two underfull vertical boxes
remain, along with the known deprecated `package/after/fontspec` hook warning.

Fresh extracted-supplement verification passes: **24/24 contract checks** and
**23 shipped tests**, with all generated artifacts reproduced exactly and all
24 terminal intervals recomputed from 600 summaries. Its numerical ledger
reports **600 PASS, 37 PASS_ANON, three NOT_EXECUTED, zero FAIL**. The unexecuted
checks concern raw/upstream operations and original raw/bootstrap inputs;
the shipped tests report 1,202 existing pytest AST deprecation warnings.

The complete final regression reports **716 passed, three skipped, zero failed
and two warnings** in **384.00 seconds**. The skips cover two host-specific TeX
checks and a legacy clean-bibliography test using an old workstation path; both
final source archives and bibliographies were independently rebuilt. The warnings
come from deliberate duplicate-ZIP-member mutation tests, which pass. The log is
`/workspace/cce-build/tmlr-clarity-final-tests.log`. Only internal documentation
changed afterward. The final scope audit confirms that scientific source hashes,
all active manuscript mirrors, historical evidence and protected files agree
with the recorded preservation scope.

## Publication scope and remaining limits

Fable's source review finds the main story readable and recommends targeted
changes; it did not inspect rendered pages or perform experiments. Its proposed
wording was checked before use, and several scope errors were excluded.
The publication case remains a focused methodological and diagnostic study.
Novelty and significance remain reviewer judgments. Empirical coverage is one
synthetic model and teacher, and the paper claims no practical regret improvement,
end-to-end speedup or large-model scalability. The same-history width result
does not order adaptive regret.

The follow-up raw tree is retained locally, but no anonymous raw archive or
durable anonymous hosting location has been completed. Compact terminal-interval
verification does not establish raw-dependent roundwise replay. The original
study's missing raw trajectories and historical runtime gaps remain unresolved.
The authors must review the final materials and supply the OpenReview
declarations before submission.
