# Revision Audit

Audit date: 2026-07-23

Audited source revision: `10a22079a58ffecbc17448aa864c8ad0eb58b297`

## Verdict

The structured scalar-link, scaled-tanh, split spectral-tail, gap-dependent,
and fixed-preconditioner CG statements are present. No new theorem correctness
failure was found in this audit. The evidence does **not** support a nonvacuous
scaled-tanh instantiation, a full Wheel result, or an end-to-end CG scalability
claim.

## Executed Evidence

- **Scaled tanh:** 8,000/8,000 full-profile runs validated. Relative transfer
  is below one and tighter than Welford, and dense/CG actions agree. The primary
  theorem-instantiation criterion fails because exact-relative has 43 failed
  trajectories and full-CG has 51. The aggregate explicitly sets
  `supports_nonavacuous_instantiation_claim=false`.
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

The 10,937,302-byte inventory and its checksum are tracked under
`results/derived/raw_bundles/scaled_tanh_instantiation/`. The 4.43 GB archive
payload remains outside Git and has no public fetch URL. The full gap tree,
Wheel failure trees, and end-to-end development tree also remain ignored local
data.

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

## Paper Packaging

- The main body occupies pages 1--7; references begin on page 8.
- The compiled PDF has 71 physical pages at the audited source revision.
- The only material overfull warning is a 5.1225 pt abstract/style box.
- No unresolved references, citations, duplicate labels, missing figures, or
  Type 3 fonts were reported by the final checks.
- The official target-year style/checklist package is unavailable. The build
  uses the repository's AISTATS 2026 style provisionally and emits a missing
  target-year checklist warning.

## Submission Constraints

Do not claim:

- a nonvacuous scaled-tanh theorem instantiation;
- a completed full Wheel benchmark or any Wheel full-GGN superiority result;
- an evaluation result from the end-to-end development seed;
- end-to-end CG accuracy or scalability from solves with failed residuals;
- faithful LO-FI/KFAC comparisons where those implementations are absent;
- verified numerical enclosure from ordinary float64 checks;
- that the tracked scaled-tanh inventory contains the archive payload; or
- final target-year AISTATS compliance until the official style and checklist
  are installed and validated.

The source and generated-artifact tree at `10a22079` is the audited state. This
documentation pass adds only the revision records and history-rewrite map.
