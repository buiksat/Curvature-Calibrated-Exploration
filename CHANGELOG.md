# Revision Changelog

> **Historical snapshot.** The validation counts and anonymous-release claims
> below describe the 2026-07-21 tree. They predate the closed-rate/scaling
> revision and are not current submission-release evidence. See
> `REVISION_REPORT.md` and rebuild both release tiers from the final reviewed
> tree before using those counts or hashes.

## 2026-07-21 - Audited revision

This entry records implemented and executed revision work.  It does not claim
that the unrun external-baseline or accelerator studies below were completed.

### Theory and operational certificates

- Added an online `O(d)` path-certificate state with pre-action schedules for drift, mismatch, Taylor remainder, observable information gain, confidence radii, and width certificates. The implementation uses float64 vector Welford updates and scalar accumulators, with reward-dependent state updated only after the action and reward.
- Added focused tests for direct-history agreement, roundoff handling, dense drift and mismatch domination, all-action centering, Taylor and information-gain bounds, filtration order, and the absence of teacher or post-hoc score inputs.
- Integrated bounded-path and scalar tanh specializations with explicit dependence on horizon, width, regularization, noise, gradient scale, residuals, and information conditioning. The text now states that width alone does not imply sublinear regret.
- Added rank-sensitive refresh and endpoint statements, including the normalized spectral floor and the restrictions needed for frozen-window, relinearized, stale, and geometric comparisons.
- Restricted scalar-width invariance to a common history with predictable scaling and a coupled trajectory; it is not presented as a general regret equivalence.

### Executed experiments

- **Certified tanh instance:** ran the fixed bounded nonlinear protocol on 50 disjoint evaluation seeds for both centers, producing 100 policy runs and 10,000 round records. No sampled transfer, centering, linearization, information, CG, confidence, optimism, or regret-event failures were observed. The result is labelled `posthoc_theorem_event_verified`, not verified-enclosure certification; the reported regret bounds remain highly vacuous. The controlled grid is descriptive tuning evidence only.
- **Phase diagram:** executed the preregistered zero-representation-drift bounded-linear map across 8 cells, 7 methods, and 30 evaluation seeds, plus separately tagged common-trajectory diagnostics. The results show no uniform curvature ordering: diagonal wins all eight online cells against exact full curvature, block wins six with two unresolved, and exact full beats windowed and stale approximations in all eight. Nonzero representation drift was not run.
- **Balanced contextual benchmark:** executed 11 methods on a synthetic normalized Rademacher contextual task using separate tuning and 30-seed evaluation sets. LinUCB passes the context-use sanity check against both context-free controls. Several baselines outperform full curvature, so these rows do not support uniform full-curvature superiority. Local neural methods are not claimed as validated reproductions of published implementations.
- **Systems scaling:** recorded 384 synthetic CPU groups over dimensions 32 to 8192, action counts 4 to 10, and sample counts 32 to 512. The study includes separate CG, row-batched CG, row-batched Jacobi-PCG, dense, diagonal, block, and Lanczos paths; recorded width-sandwich checks pass. The matrix-free case at dimension 8192 avoids a dense allocation. These are float64 operator diagnostics, not accelerator or trained-large-model evidence.

### Evidence and manuscript disposition

- Retained Covertype only as a negative appendix audit. Although its cached source and hash were validated, deployable context-free controls beat every contextual method at every reported horizon, and the Gaussian squared-loss theorem does not certify its binary-reward rows.
- Removed the unrecovered legacy oracle-selected study from the evidentiary chain. Its complete raw data and code were not recovered, and it must not be regenerated or used as new support.
- Revised the abstract, contribution statement, assumption ledger, experiment discussion, limitations, and conclusion to distinguish theorem-certified, post-hoc checked, uncertified, and legacy evidence. Full curvature is treated as a reference method rather than a universal winner.
- Expanded related work and bibliography coverage for neural contextual bandits, curvature approximations, and uncertainty methods. Generated manuscript tables and figures are limited to validated revision sources.

### Provenance and packaging

- Added strict aggregation and manuscript-artifact generation with input validation and SHA-256 provenance sidecars. Stale or altered derived inputs are rejected.
- Added per-run metadata and manifests covering resolved configuration, seed, UTC time, git state, package and hardware information, raw JSONL records, summaries, and file hashes.
- Added anonymous-supplement tooling that stages a fresh tree, sanitizes paths and revision identifiers, regenerates manifests and sidecars, and fails on missing provenance or detected identity leaks. Tests cover stale-input rejection, tampering, sanitization, and hash validity.

### Remaining or unrun

- No external contextual benchmark currently passes the context-free-control sanity check; the balanced passing benchmark is synthetic.
- Published baseline implementations have not been independently reproduced or validated. NeuralLinear/UCB/TS variants, EKF, LMC-TS, KFAC, block-Laplace, matched wall-clock retuning, and nonzero representation-drift cells remain unrun.
- Verified interval enclosures, accelerator experiments, and actual large-model runs at the claimed scalability range remain unrun; no broad large-model systems claim is made.
- Final validation passed: 143 tests; clean 38-page PDF; Algorithm 1/Figure 1/Table 1/references on pages 3/6/7/8; zero content-generated overfull boxes and zero Type 3 fonts; blank author/title metadata; verified archival and review release manifests, hashes, zstd streams, provenance references, and identity scans.
- The archival release contains 11,370 files (503.1 MiB); the review tier contains 201 files (89.8 MiB) with every omitted raw file hash-indexed.
