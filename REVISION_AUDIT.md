# Revision Audit

Audit date: 2026-07-23

Audited source revision: `bf5fa236297091e1b80dede777dfb03f8b3fdc72`

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
  attempt, and 27 from the clean 300-iteration `a999319c` attempt. A periodic
  residual-replacement development diagnostic also failed. No evaluation
  policy or evaluation seed was read.
- **End-to-end systems:** one full-profile **development-seed** diagnostic at
  clean revision `95fe2d2a` completed 48/48 cells on CUDA in 2210.240383 s.
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

## Paper Packaging

- The main body ends on numbered page 6.
- The compiled PDF has 71 physical pages at `bf5fa236`.
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

The source tree at `bf5fa236` is the audited state. Only these revision records
were modified during this documentation pass.
