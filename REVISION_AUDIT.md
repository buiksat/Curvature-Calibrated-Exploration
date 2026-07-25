# Revision Audit

Audit date: 2026-07-24

Audited functional revision: `997380155855d547a0f9cc1ca6b05efabf18c2ff`

## Verdict

The structured scalar-link, scaled-tanh, split spectral-tail, gap-dependent,
and fixed-preconditioner CG statements are present. No new theorem correctness
failure was found in this audit. The evidence does **not** support a nonvacuous
scaled-tanh instantiation, a full Wheel result, or an end-to-end CG scalability
claim.

Anonymous-release identity and provenance remediation is implemented and tested,
but the canonical clean hydrated review archive has not yet been assembled from
this revision. Its final hash and upload remain pending.

## Executed Evidence

- **Scaled tanh:** 8,000/8,000 full-profile runs validated. This is a fresh final
  holdout after two disclosed pre-freeze diagnostic splits: seeds `1000--1049`
  were abandoned after optimizer diagnostics, replacement seeds `1100--1149`
  were abandoned after only `1100--1101` were read, the residual threshold came
  from development diagnostics, and damping was selected on tuning seeds `0--9`.
  The protocol was then frozen before fresh seeds `1200--1249` were reserved;
  no final-holdout metric was read during selection. Relative transfer is below
  one and tighter than Welford, and dense/CG actions agree. The recorded
  theorem-event criterion fails in 43 exact-relative, 51 full-CG, 40 Welford,
  and 14 corrected-center trajectories. These split into 106 analytic-premise
  failures and 42 float64 transfer-audit failures, with no mixed trajectory.
  For the latter, `min_t(rho_exact-chi)=-1.917976003212528e-9` is within the
  declared `2e-9` tolerance, `min_t(rho_W-rho_exact)=0.009840595939588748`, and
  the maximum replayed trust-region violation is
  `1.1102230246251565e-16`. All raw flags and failures remain retained, and the
  aggregate explicitly sets `supports_nonavacuous_instantiation_claim=false`.
- **Gap dependent:** 1,000/1,000 full-profile runs validated. Every recorded
  exact/full-CG gap, linearization, confidence, operator, and solver premise
  passes. The bounds dominate regret but are numerically loose.
- **Spectral-tail split:** the full reanalysis is complete and analysis-only;
  policies were neither rerun nor retuned.
- **Wheel:** the feasible local baseline inventory was expanded to 12 methods,
  with KFAC and LO-FI still omitted. Full tuning failed before selection:
  56 checksum-bound failure records were retained from the 100-iteration
  attempt, and 27 from the clean 300-iteration `6bbe855a` attempt. A periodic
  residual-replacement development diagnostic also failed. No full-profile
  evaluation policy or evaluation seed was read. A separate current-contract
  smoke check ran 96 tuning and 96 evaluation trajectories; it is an
  engineering check, not full-profile evidence.
- **End-to-end systems:** one full-profile **development-seed** diagnostic at
  clean revision `b7e39b44` completed 48/48 cells on CUDA in 2210.240383 s.
  It is not evaluation evidence: maximum original-system CG residuals were
  13.7298908 for current replay and 15.4970188 for historical gradients.
  No full evaluation grid was run.

## Reproducibility Status

The deterministic full scaled-tanh archive was verified locally:

- archive bytes: `4,425,351,907`;
- validated runs: `8,000`;
- files: `48,002`;
- SHA-256:
  `47674276eff5b84eb002cff39ac0a11facea6bc3fdd7416a0e60e695c7ec8c7d`.

The 10,941,309-byte inventory and its checksum are tracked under
`results/derived/raw_bundles/scaled_tanh_instantiation/`. The 4.43 GB archive
payload remains outside Git and has no public fetch URL. The full gap tree,
Wheel failure trees, and end-to-end development tree also remain ignored local
data. The inventory SHA-256 is
`f3394c70e22820e30fe4bfcd9552f9313c24b86da424f562f39e886ccfa9c97e`;
it records both current and immutable execution config digests and accepts only
the exact known description-wording migration.

The release-source audit records 51,289 provenance occurrences for 8,017 unique
raw files absent from the current source tree. They retain recorded hashes and
are declared `not_in_source_tree`, not `indexed_not_released`; hydrated mode has
zero indexed omissions. No such gap feeds a main-body artifact through tracked
provenance. Four appendix artifacts depend on 4,600 unique missing files, while
the remaining 3,417 occur in legacy derived/provenance artifacts that do not
feed a currently included figure or table.

The Wheel smoke archive was regenerated under the current 12-method contract
and verified twice with byte-identical output: 192 runs, 577 files, 1,850,306
archive bytes, and SHA-256
`eadf27a41ab21f32ac8188f93c7e75beb35e8b95e605dae8cf3c6e752320299d`.
Its tracked inventory has SHA-256
`66871634b4e4862cca7535c9443b4d55eb22adb6906e779e3ce81bef0bbc063e`.
Selection uses tuning seeds only and records
`evaluation_outcomes_used=false`.

## Git History Cleanup

The feature branch was rewritten from base `aa0e5f26` to remove historical
`results/raw/` blobs. The final source tree was unchanged, all 56 rewritten
commit author/email/subject tuples matched their predecessors, and no
`results/raw/` object remains reachable from the rewritten branch. The
old-to-new mapping and verification record are in `HISTORY_REWRITE_MAP.json`.
The complete pre-rewrite branch is retained outside the repository in the
checksum-recorded backup bundle named there.

The direct regression test
`test_raw_results_are_absent_from_reachable_git_history` checks both reachable
objects and path history under `results/raw/` and requires both to be empty when
Git metadata is available.

## Anonymity Remediation

Commits `c80fe1a8..99738015` close reconstructible-identity, mutable-input, and
archive-integrity channels in the release path.
Identity terms are discovered locally from Git, account, and host metadata;
Python literal concatenations and structured NumPy payloads are scanned; private
release tooling is excluded; sidecars are rebound to sanitized payloads; absent
legacy inputs receive a manifest-bound inventory; raw inputs are snapshotted and
rehashed; and each archived member is checked against the release manifest.
Full- and review-tier tests cover these behaviors.

This remediation status is not an assembly claim. Final clean hydrated-review
construction and the resulting archive hash are **pending**.

## Paper Packaging

- The main body occupies pages 1--7; references begin on page 8.
- The compiled PDF has 72 physical pages at the audited source revision.
- The only material overfull warning is a 5.1225 pt abstract/style box.
- No unresolved references, citations, duplicate labels, missing figures, or
  Type 3 fonts were reported by the final checks.
- The official AISTATS 2027 kit remains unavailable. The build uses the
  repository's AISTATS 2026 style only as a provisional formatting baseline and
  emits warnings for the missing official 2027 style and checklist.

## Submission Constraints

Do not claim:

- a nonvacuous scaled-tanh theorem instantiation;
- a completed full Wheel benchmark or any Wheel full-GGN superiority result;
- an evaluation result from the end-to-end development seed;
- end-to-end CG accuracy or scalability from solves with failed residuals;
- faithful LO-FI/KFAC comparisons where those implementations are absent;
- verified numerical enclosure from ordinary float64 checks;
- that the tracked scaled-tanh inventory contains the archive payload;
- final AISTATS 2027 compliance until the official style and checklist
  are installed and validated; or
- completed hydrated anonymous archive assembly, upload, or final archive hash.

The source and generated-artifact tree at `99738015` is the audited state. The
direct noncommuting-Jacobi PCG regression verifies equality of original and
symmetrically transformed energy errors to `2e-14`, and the raw-history test
directly guards the rewritten-history claim. Main-body artifact provenance and
hydrated-release regressions are included. `REVISION_CHANGELOG.json` is refreshed
through this audited functional revision; the documentation commit follows it.
