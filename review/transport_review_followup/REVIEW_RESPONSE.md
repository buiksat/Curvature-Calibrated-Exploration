# Response to the scientific review

The manuscript revisions address the presentation and qualified theoretical
requests. Experimental and reproducibility requests are **partly addressed**;
the full follow-up, external reference checks, and strict release remain open.

This response uses the [original machine-generated review](source_review.md)
and its [source-check qualifications](source_review_qualifications.md) from
`20261014T002003.744779Z`. The original review is preserved byte-for-byte as
immutable source text; only local links were updated or removed in the copied
qualifications. API logs, manifests, and credentials are not included.
The machine-generated assessment is not a scientific or proof certification.
Manuscript snapshot:
[`0948574`](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/09485745a189492f0bdc71795acddf8f5cbcaeb7/submissions/tmlr_2026/REVISION_STATUS.md).
Research snapshot: `dc2e2dc9e3f9f7ace8d5335fdf634cd31159c41a`.
The recorded tests and pilot below are execution evidence; the original model
review did not execute tests or experiments and is not a proof certification.

## Requests, changes, and remaining work

| Review request | Response and evidence | Remaining limitation |
| --- | --- | --- |
| **F1–F2: legacy CC-UCB/CG descriptions and stale references** | Related work and active prose now describe the transported-UCB theorem and the dense Cholesky implementation actually audited. Legacy theorem dependencies were removed from the active manuscript; the historical two-sided appendix wording was corrected. | The general operator/solver interfaces are theoretical results, not experimentally evaluated CG or approximate-operator methods. |
| **F3 / E1: explain bound vacuity** | The existing decomposition is now in the main narrative. At T=1000, base terms account for 79.39–97.33% and explicit path inflation for 2.01–16.27% of the mean terminal sharp bound. These are ratios of means over the same transport-Hessian histories. New follow-up exports also record each method's terminal components and the frozen policy's own-trajectory reference bound; see [pilot validation](PILOT_VALIDATION.md). | The historical frozen-policy bound comparison has not been recovered. Removing a path component from a transport trajectory is accounting, not a frozen-policy counterfactual. Base-term size is not attributable to the confidence radius alone, and marginal inflation medians do not establish cumulative shares. |
| **F4: verify flagged references** | A [source and bibliography audit](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/09485745a189492f0bdc71795acddf8f5cbcaeb7/submissions/tmlr_2026/BIBLIOGRAPHY_APPENDIX_AUDIT.md) records the exact entries and failed metadata requests. No unsupported bibliographic change was made. | Authoritative scholarly endpoints were proxy-blocked. The Granziol and Wen entries remain externally unverified. Pascanu's internal key/year difference is not evidence of an error; that citation is outside the active manuscript. |
| **F5: compare frozen and transported guarantees** | Added a frozen-width proposition and proof, plus a comparison under common uniform assumptions. Intro/conclusion distinguish guarantees from observed outcomes. | Comparable worst-case rates do not order realized regret, prove transport unnecessary, or establish that the sufficient near-linearity regime is necessary. Policies generate different histories, radii, and information gains. |
| **F6: reduce legacy appendix burden** | Removed the entire mutually dependent legacy cluster from the active document and source archive, retaining current transport proofs and diagnostics plus a short scope note. The PDF decreased from 68 to 29 pages; historical files remain in Git. | This is a focused submission, not an independent re-verification of every historical theorem. |
| **F7: reproducibility and provenance** | New runs have a hash-checked Python 3.12 lock, recorded source/configuration inventories, retained external raw data, per-seed exports, and an independent terminal-interval verifier. Historical SciPy and two source-digest discrepancies are disclosed; see [Python setup](../../PYTHON_SETUP.md) and [validation](../../submissions/tmlr_2026/REVISION_VALIDATION.md). | Original per-run observations are missing. New exports cannot reproduce the historical paired bootstrap or recover its runtime/source state. Portable seed summaries reproduce terminal-regret intervals, not all roundwise audits or regret-curve intervals; retain the external raw directories. |
| **F8 / E2: stronger realized drift** | A separate [prespecified follow-up](../../experiments/TRANSPORT_REVIEW_FOLLOWUP_PROTOCOL.md) uses W=16, 1, 0.25, disjoint development/tuning/evaluation seeds, measured endpoint drift, and retained numerical failures. The T64 pilot passed 102 trajectories; the separate [T1000 development gate](full-development-check/README.md) passed all 24 trajectories. | Full tuning and 50-seed evaluation are not complete. Pilot evaluation has only two seeds per cell, and none reached endpoint distance 1. Large target labels or development drift do not establish large evaluation drift. No follow-up result has been inserted into the paper. |
| **F9–F12: abstract, notation, captions, diagnostic context** | Shortened the abstract; tied the four objects to their certificates; explained table factors and smallness requirements; gave optimal-action entropy its units and maximum. Preserved the original empirical numbers, theorem conditions, and negative findings. | Author review of the final scientific exposition remains necessary. |
| **E3: localize certificate slack** | Existing endpoint/path diagnostics and the new drift exports expose realized motion. Development quadrature refinements and failures are retained in [the refinement record](QUADRATURE_REFINEMENT.json). | No new decomposition separating relative-form, Frobenius/operator-norm, and ridge-lower-bound slack has been completed. Higher quadrature order improves a numerical diagnostic; it does not produce a sharper analytic certificate or verified enclosure. |
| **E4–E5: approximate operators, CG, and misspecification** | The manuscript explicitly limits the evaluated study to dense exact-current geometry and direct float64 solves. | No new approximate-operator, iterative-solver, or controlled-misspecification experiment was run. Those extensions remain untested. |
| **E6: real-data behavior and scalability** | The runbook documents CPU parallelism for 29-dimensional NumPy/SciPy calculations. | Covertype/Nyström and other real-data benchmarks are not completed. No GPU implementation, A100 speedup, large-model scaling result, or external-validity claim is established. |

## Validation and release boundary

The final repository suite reports **614 passed, 46 skipped, 0 failed**; skips
include environment-dependent release and optional-capability checks. The
separate launcher safety/cache suite passes seven tests. The revised numerical
ledger reports **277 PASS, 3 NOT_EXECUTED, 0 FAIL**. These counts retain their
qualifications in [REVISION_VALIDATION.md](../../submissions/tmlr_2026/REVISION_VALIDATION.md).

The [pilot](PILOT_VALIDATION.md) completed 24 development, 54 tuning, and 24
evaluation trajectories, passed strict raw aggregation and independent terminal
paired-interval replay, and resumed successfully. Its two-seed cells are
engineering evidence, not publication-level statistical evidence. Confidence and
optimism held even for the uncertified naive control; this neither proves
population coverage nor demonstrates that the correction is necessary. Changing
W changes the task as well as its geometry, so across-W comparisons are not a
causal effect of drift.

The main manuscript and its active source archive compile, but the research
branch's **strict release packager remains blocked**: its trust policy excludes
writable user TeX trees, while this host supplies `algorithm.sty` only there.
The diagnostic compile does not satisfy that policy. No new strict release or
anonymous experiment supplement has been verified, and no submission has been
made. Required system-owned TeX dependencies, a complete packager run, external
bibliography checks, and author review remain release work.

Before extending empirical claims, run the frozen workflow on the Meta server,
including its development gate, independent full tuning, all declared evaluation
cells, raw checks, and planned analyses. The local full-profile development gate
passed, but it does not replace those remaining phases. Preserve failures and
the current protocol; do not replace
missing historical data, promote pilot outcomes to paper findings, or infer
policy dominance from upper-bound comparisons.
