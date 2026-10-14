# Review-revision validation

This record concerns the manuscript revision synchronized on 2026-10-13
(America/Los_Angeles). `FINALIZATION_REPORT.md` remains the historical release
record. A collected test has not necessarily run or passed.

| Collection scope | Current collected cases |
| --- | --- |
| Release-package test collection | 522 collected |
| Repository suite collection | 660 collected |

The counts come from `python -m pytest -q --no-header -p no:cacheprovider
--collect-only -q tests experiments/tests`; the package count is the
`tests/test_tmlr_release_package.py` row. Two regression tests compare these
recorded counts with live collection. Refresh them after adding or removing
cases. They deliberately do not compare collection to the historical report's
`643 passed, 0 skipped` claim.

The initial repository run in this cloud session reported **589 passed,
47 skipped, 7 failed** before the parallel revision work was finalized. Its
failures included missing PyYAML, a new configuration inventory entry, and the
historical-test-count guard. This is a diagnostic baseline, not the final
revised test outcome. Final execution results must retain their actual skip
and failure counts; collection counts cannot substitute for them.

The next full repository regression run, after manuscript synchronization,
reported **606 passed, 46 skipped, 4 failed**. Three failures were stale
abstract/conclusion phrase expectations in the detached evidence verifier;
the fourth mutated a CG appendix that the revised manuscript no longer includes.
The repairs retain the negative-finding requirements and move the numeric
mutation to an active source. Four additional mutation cases check that the
revised abstract and conclusion still reject removal of their qualifications.
This run predates those repairs; targeted repair checks are recorded separately.

The detached-evidence review-bundle module passes after its phrase-contract
repair: **67 passed**, including the four new negative-finding mutation cases.
The repair changes the expected scientifically equivalent wording; it does not
remove the conservative-certificate, vacuous-bound, validity-versus-usefulness,
or no-uniform-regret-ordering requirements.

The inactive-CG test now mutates an active experiment explanation outside every
numeric context window and requires both semantic-unit and whole-file checks
to reject it. That repaired test and its clean baseline pass: **2 passed**.
Both collection-count guards also pass: **2 passed, 520 deselected**.

The final full repository rerun after those repairs completed with **614 passed,
46 skipped, 0 failed** in 173.24 seconds, using the locked Python environment
and single-threaded BLAS. Skips remain environment-dependent release-build and
optional capability checks; this result does not certify the blocked strict
release build described below. The separate launcher safety/cache module also
passes **7 tests**.

The actual local follow-up pilot completed all **24 development, 54 tuning,
and 24 held-out evaluation trajectories**. Its strict aggregate and independent
replay of all 24 terminal paired intervals pass. An identical invocation reuses
the completed trajectories, tuning selection, and aggregate successfully.
See `review/transport_review_followup/PILOT_VALIDATION.md` for the measured
outcomes and limitations; this pilot does not substitute for the full study.

The full-profile development gate also completed successfully from clean
research revision `dc2e2dc9e3f9f7ace8d5335fdf634cd31159c41a`: **24 trajectories
at horizon 1000**, on four CPU workers, with development-phase elapsed time
358.367673 seconds. Tuning and held-out evaluation were not run for this profile.
The separately retained development evidence is under
`review/transport_review_followup/full-development-check/`.

The subsequent complete local follow-up started from clean research revision
`707c8243ea6d5395369ed812a68cf7e27d700596` and completed **24 development,
270 tuning, and 600 evaluation trajectories**, with no failed trajectory records
and all deterministic audits passing. It resumed 16 verified development
trajectories after a user-requested pause. The strict raw-data aggregation passed;
the portable verifier independently replayed all 24 reported terminal intervals
from 600 exact evaluation summaries. Export commit
`65dd4e76efd376c830e2ea7e9dfe23eddd4bf01e` is confirmed on GitHub. These checks do
not imply favorable regret comparisons or manuscript readiness; see
`review/transport_review_followup/FULL_RESULTS.md`. The prior source-test and
ledger counts above have not been represented as new executions.

Focused package-contract validation passes: **10 passed, 511 deselected**.
These checks exercise the evidence anonymization contract and a mutated
declaration, original repository evidence handling, excluded/active artifact
inventory, and both current collection-count records. They are not a full
release-build result.

The revised numerical ledger reports **277 PASS, 3 NOT_EXECUTED, 0 FAIL**,
covering 91 source-derived entries. The three nonexecuted checks remain explicit
limitations; they are not counted as passes. Focused numeric mutation tests
report **32 passed, 1 skipped, 489 deselected**. The skipped test requires a
compiled release. The numeric context digest is pinned by the anonymous-package
contract, whose optional-repository provenance/tool checks pass **5 of 5**.

The synchronized TMLR entry point passes staged static validation and the
repository layout preflight. A diagnostic compile using the cloud's local TeX
packages succeeds; it supplies the exact project-local recorder closure used
to update `COMPILED_CLOSURE`: 80 inputs, including the new `legacy_scope.tex`,
with the nine legacy appendix sources and `tables/growing_window_pareto.tex`
removed. The entry-point/source digests and generated bibliography digest were
updated; venue and vendored-package digests were preserved. The independent
contract still binds exact paths, roles, digests, sizes, and archive membership.

**Strict release build remains blocked.** `package.compile_environment`
intentionally removes writable user TeX trees from the search path. Its compile
fails because this machine lacks the system-installed `algorithm.sty`; the
cloud onboarding installation supplies it only in a writable local tree.
The diagnostic compile does not satisfy the release packager's system-input
trust rule. That rule, its recorder checks, and its mutation tests remain
enforced. No revised strict release or anonymous supplement has been claimed
as verified. Install the required LaTeX packages in system-owned distribution
trees and run the full packager to validate external-input trust and release
checks before publishing a new supplement.

The historical AISTATS PDF and its checksum, frozen experiment sources and
configuration, original aggregate and selection bytes, provenance pins, and
the evidence anonymization transform were not changed by this synchronization.
