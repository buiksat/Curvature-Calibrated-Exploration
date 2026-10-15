# Revision status: local fixes after Fable follow-up

Updated 2026-10-15 (UTC). The checked local recommendations are applied to the
**47-page** manuscript, with scientific sources synchronized with `paper/` on
`cce-review-revisions`. No TMLR submission has been made.

## What changed

The empirical section now identifies the Hessian certificate notation by a
corollary reference, separates the strict seed threshold from the non-strict
round threshold, and improves the development/tuning sentence. The central
score display ends with a period; the applied-matrix definition no longer has
an unused equation number. LaTeX regenerates subsequent numbers and references.

Formal mathematical expressions, theorem conditions, proofs, scientific data,
figures and experimental outcomes are preserved. The two theory edits affect
punctuation and equation numbering only. The abstract is unchanged because the
review did not give a concrete improvement to its sentence structure. No new
experiment or Fable API request was run for this implementation.

The research branch records the
[implementation](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/review/readability_polish/IMPLEMENTATION_REPORT.md),
[checked advice](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/review/readability_followup_fable/CHECKED_ADVICE.md)
and [validation](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/submissions/tmlr_2026/REVISION_VALIDATION.md).
The earlier Fable verdict remains advisory and bound to the snapshot it read.

## Main-branch build

The final build is `/workspace/cce-build/tmlr-polish-main`, using the unmodified
official TMLR style at 10pt. The notation table is on page 5, figures on pages
3, 10, 20 and 21, and references begin on page 26. Two rendered-page inspections
cover the affected passages on pages 5, 7, 18 and 21. The certificate pointer,
threshold conventions and regenerated references resolve clearly, with no
clipping, overlap or visible reference issue.

- `main.pdf`: 691,558 bytes; SHA-256
  `1085e8882544a31d6609d5ec2efed5ed82b49906ac8ee6874f0292991728f568`.
- `source.zip`: 190,154 bytes, 49 members, 672,810 unpacked bytes; SHA-256
  `c63227d2aafdfbfdff6fa464e453827e78883f16e0ebeee29e330e789b0c398c`.

A fresh archive extraction reproduces the PDF byte for byte. All four official
style/licence pins pass. The recorder has 44 archived project inputs, three
regenerated inputs and 291 environment inputs, with no original-checkout or
prior-build dependencies. Identifying PDF metadata is empty. There are no
compiler warnings, unresolved references/citations, missing characters or
overfull boxes; four underfull horizontal and three underfull vertical boxes
remain. The report is
`/workspace/cce-build/tmlr-polish-main-clean/verification.json`.
The template's default review header is not a submission-status assertion.

## Research release and checks

The matched strict release is `/workspace/cce-build/tmlr-polish-release`:

- `main.pdf`: 691,514 bytes;
  `56bb4aa967ddfc98643add811b70813626e5c79a40254ecb2a03aa7108b6124a`.
- `source.zip`: 3,412,745 bytes, 101 members;
  `890aafc6579081d4d750ca36bd54decfcbeadbfa5d17a885a59c681283cf17bf`.
- `supplement.zip`: 93,812,230 bytes, 178 members;
  `cfec83f2cb6e20f769a7123e71d1008d60d37286bd21f98e926b787ca83d77ac`.

The build passes its layout, identity, archive-member, size and digest gates.
The supplement leaves 6,187,770 bytes below the decimal 100 MB limit. Independent
strict source extraction reproduces its matched PDF byte for byte. All four
official and 54 vendor pins pass; the recorder matches 93 project and 240
protected external records, plus two generated auxiliaries. Metadata is empty;
there are no checkout/user-environment dependencies, unresolved references,
missing characters or overfull boxes. Four underfull horizontal and three
underfull vertical boxes remain, with the existing deprecated fontspec-hook
warning. Use each PDF with its matching source archive; their exact declared
TeX dependency sets differ.

The affected existing checks pass: **50 numerical/package mutation tests** and
**67 detached-evidence tests**. All 218 numerical-ledger entries, values and
selectors are unchanged. No test files, cases or thresholds were changed, and
no checks were weakened.
Only reviewed source-context bindings and an equivalent manuscript-guard phrase
were refreshed, with their dependent byte/hash records.

Fresh extracted-supplement verification passes in 18.304 seconds: **24/24
contract checks and 23 shipped tests**. All generated artifacts reproduce exactly,
and all 24 terminal intervals are recomputed from 600 summaries. The ledger
reports **600 PASS, 37 PASS_ANON, three NOT_EXECUTED, zero FAIL**. The unexecuted
checks concern raw/upstream operations and original raw/bootstrap inputs;
the shipped tests report 1,202 existing pytest AST deprecation warnings.

The full 719-case suite was not rerun for these local prose, presentation and
context-binding changes. Its preceding result of 716 passed and three skipped
remains historical evidence for the earlier state, not a fresh pass. Current
checks exercise the affected verifiers and final packages. Preservation checks
confirm unchanged scientific results, evidence, old reviews and historical PDFs.

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
