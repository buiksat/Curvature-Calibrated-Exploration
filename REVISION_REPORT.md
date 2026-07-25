# Resubmission Revision Report

Date: 2026-07-24

Branch: `codex/closed-rates-20260721`

Audited functional revision: `997380155855d547a0f9cc1ca6b05efabf18c2ff`

This report distinguishes proved statements, full evaluation evidence, failed
premise audits, development-only diagnostics, smoke checks, and unavailable raw
payloads. Ordinary float64 residuals are audits, not verified enclosures. The
scaled-tanh evaluation is a fresh final holdout after two disclosed diagnostic
splits.

## Status Summary

| Item | Status | Evidence |
| --- | --- | --- |
| Relative scalar-link drift and centering | Complete | `lem:relative-link-drift` |
| Scaled-tanh conditional corollary | Complete as a theorem | `cor:scaled-tanh-relative` |
| Refined spectral-tail split and tightness | Complete | `lem:spectral-tail-logdet`, `prop:spectral-tail-tightness` |
| Gap-dependent exact-current corollary | Complete | `cor:gap-dependent-exact-current` |
| Fixed-preconditioner CG extension | Complete | `lem:pcg` |
| Scaled-tanh final holdout | Executed; theorem-instantiation criterion failed | 8,000/8,000 runs |
| Full gap-dependent validation | Executed; recorded exact/full-CG premises passed | 1,000/1,000 runs |
| Refined spectral-tail reanalysis | Executed, analysis-only | Existing full trajectories |
| Full Wheel benchmark | Failed during tuning; evaluation not run | 56 + 27 hashed failure records |
| Wheel smoke reproduction | Complete engineering check | 192 runs; 577 files |
| End-to-end systems full profile | Development seed only; solver residual checks failed | 48/48 cells, seed 7100 |
| Full scaled-tanh raw bundle | Locally verified; inventory tracked, payload outside Git | 4,425,351,907 bytes |
| Anonymous release remediation | Implemented and tested; clean hydrated archive pending | `c80fe1a8..99738015` |
| Full exponential-family theorem | Not added | No complete proof obtained |

## Theory Changes

### Relative scalar-link drift and centering

Lemma `lem:relative-link-drift` specializes the frozen/current transfer to
`mu_theta(z)=h(phi(z)^T theta)`. It proves `chi_t <= rho_t`, the one-sided and
two-sided Loewner transfer factors, the scalar-weight centering identity, and
the frozen-metric centering bound. It records that the structured certificate
needs `O(t)` scalar replay metadata in addition to `O(d)` path-summary and
sequential Krylov state. It does not claim `O(d)` total memory.

### Scaled-tanh specialization

Corollary `cor:scaled-tanh-relative` treats
`sqrt(W) tanh(phi^T theta/sqrt(W))`, derives explicit gradient and Hessian
constants, bounds relative derivative drift, and gives a conditional
original-center rate. Here `W` is an explicit scalar-link near-linearity scale,
not generic neural-network width. The theorem remains valid even though the
full experiment did not satisfy every premise.

### Spectral-tail, gap, and solver results

Lemma `lem:spectral-tail-logdet` gives the refined head/tail split using
observable trace and residual tail mass; the older linear-tail bound remains an
immediate relaxation. Proposition `prop:spectral-tail-tightness` supplies the
equal-eigenvalue exactness construction. Online schedules never subtract an
upper tail envelope from total trace.

Corollary `cor:gap-dependent-exact-current` gives the minimum-gap result under
its additional linearization premise. Lemma `lem:pcg` analyzes a fixed,
history-measurable SPD preconditioner through the symmetric transformed system,
including fixed-iteration and preconditioned-residual stopping conditions. It
does not assert that Jacobi improves conditioning. Independent derivations and
edge cases are retained in `THEORY_DERIVATIONS.md`.

## Scaled-Tanh Final Holdout: Retained Failure

Source: `results/derived/scaled_tanh_instantiation/full/aggregate.json`.

- 8,000 of 8,000 full-profile runs validate.
- The reported evaluation is a final holdout after two disclosed pre-freeze
  diagnostic splits. Nominal seeds `1000--1049` were abandoned after optimizer
  diagnostics. Replacement seeds `1100--1149` were also abandoned after only
  `1100--1101` were read.
- The residual threshold was set from development diagnostics, damping was
  selected using tuning seeds `0--9`, and the protocol was frozen before fresh
  seeds `1200--1249` were reserved as the final holdout. No final-holdout metric
  was read during selection.
- The final-holdout grid has five horizons, four normalized width ratios, eight
  methods, and 50 seeds.
- The analytic relative-transfer certificate is below one in every cell and is
  strictly tighter than Welford in every cell.
- Dense exact and full-CG actions agree in every paired trajectory. The largest
  mean relative width-squared error is `1.282047550845858e-12`.
- The displayed RHS per round decreases at every width ratio.

The recorded theorem-event conjunction fails, so the aggregate sets
`supports_nonavacuous_instantiation_claim=false`.

| Method | Failed trajectories | Analytic premise | Float64 audit | Failed rounds | Failure fields |
| --- | ---: | ---: | ---: | ---: | --- |
| Exact current, relative certificate | 43 | 29 | 14 | 72 | optimizer 58; transfer 14 |
| Full CG, relative certificate | 51 | 37 | 14 | 80 | optimizer 58; transfer 14; CG convergence 8 |
| Current Welford | 40 | 40 | 0 | 77 | optimizer 77 |
| Corrected current | 14 | 0 | 14 | 14 | transfer 14 |

The 42 transfer-flagged trajectories are retained float64 audit failures, not
analytic transfer-premise failures. Across failed trajectories,
`min_t(rho_exact-chi)=-1.917976003212528e-9`, within the declared `2e-9`
float64 audit tolerance; `min_t(rho_W-rho_exact)=0.009840595939588748`; and the
maximum replayed trust-region violation is `1.1102230246251565e-16`. The 106
analytic-premise failures are optimizer-residual or CG-convergence failures.
There are no mixed-classification trajectories. This classification does not
change any raw flag or failure count and does not rescue the failed theorem-event
criterion.

No confidence, information, linearization, optimism, centering,
residual-envelope, or recorded regret-bound failure appears in the associated
aggregate fields. This does not override the failed optimizer, transfer, and CG
premises. The paper and figures describe this as a failed premise audit.

## Full Gap-Dependent Validation

Source: `results/derived/gap_dependent_validation/full/aggregate.json`.

- 1,000 of 1,000 runs validate.
- The grid has four controlled gaps, five methods, and 50 evaluation seeds.
- All eight exact/full-CG gap-by-method groups pass the recorded gap,
  linearization, confidence, exact-current, and solver checks.
- Both recorded regret right-hand sides dominate regret in every applicable
  exact/full-CG run.
- Maximum full-CG energy error is `8.343101809119722e-7`, below the configured
  `1e-6` target.

This validates the recorded premises and inequalities, not tightness. Mean
terminal regret is single-digit while the gap-dependent right-hand sides are
approximately `1.28e6` to `1.00e7`.

## Refined Spectral-Tail Reanalysis

`results/derived/spectral_tail_study/full/bound_reanalysis.json` reuses the
existing full trajectories. It records exact information gain, the old bound,
and the refined split bound, with their numerical ordering checked under the
stored floating-point tolerance. No policy was rerun and no hyperparameter was
reselected.

## Wheel Benchmark: Failed Before Evaluation

Commit `6bbe855a` expands the feasible local inventory to 12 methods:
current full GGN-CG, local neural UCB/TS, all-layer diagonal UCB, a clearly
labeled local NeuralLinear-style sampler, frozen-backbone last-layer UCB,
LinUCB, linear TS, greedy, and random/safe/oracle controls. KFAC and LO-FI remain
omitted rather than being represented by unfaithful local substitutes. Full
network methods receive the same one-step update budget, and tuned methods have
at most six configurations, below the declared cap of 12.

The full study produced no selected configuration and no evaluation result:

1. The initial 100-iteration attempt retained 56 `failure.json` records and
   matching SHA-256 sidecars. Its first failure was delta `0.5`, tuning seed
   `2000`, ridge `0.1`, bonus `0.1`, round 484, relative residual
   `8.647020e-6` against tolerance `1e-6`.
2. Tuning was restarted cleanly from `6bbe855a` with a 300-iteration cap. It
   retained 27 hashed failures before the run was stopped. The documented
   example is delta `0.5`, seed `2008`, ridge `0.1`, bonus `0.5`, round 2761,
   residual `4.714088e-6`.
3. A development-only periodic residual-replacement diagnostic also failed at
   round 174 with residual `5.467890e-6`.

The failure logger preserved all observed failures. No full-profile evaluation
policy was run, no full-profile evaluation seed (`3000--3029`) was read, and no
favorable cell or seed was selected.

After this failure, the smoke profile was regenerated under the current
12-method contract. It contains 96 tuning and 96 evaluation trajectories using
tuning seeds `2000--2001` and smoke evaluation seeds `3000--3001`. The selection
artifact records `evaluation_outcomes_used=false`, and a repeated bundle build
was byte-identical. This smoke run is an engineering pipeline check only; it
does not constitute the missing full Wheel evaluation.

## End-to-End Systems: Development Diagnostic Only

A full-profile development run at clean revision
`b7e39b44ab2d15bab33f53148552a17c660e43d6` completed all 48 configured cells
for development seed `7100` on CUDA. It took `2210.240383006021` seconds and
recorded no skipped cell under the 24-hour cap.

It is not evaluation evidence. Maximum original-system relative residuals were:

- current replay GGN-CG: `13.729890823364258`;
- historical-gradient CG: `15.497018814086914`.

Those values invalidate a solver-accuracy interpretation. The manifest's
development-seed status and the residual failures take precedence over its
generic `reportable_complete` field. No full evaluation seed was run, no full
aggregate or paper systems figure was produced, and no end-to-end scalability
claim is made. The tracked six-policy smoke aggregate remains smoke only.

## Raw Data and Bundle Scope

The deterministic full scaled-tanh archive was created and verified locally.

| Field | Value |
| --- | --- |
| Archive | `scaled_tanh_instantiation-full.tar.gz` |
| Validated runs | 8,000 |
| Files | 48,002 |
| Archive bytes | 4,425,351,907 |
| Uncompressed bytes | 4,635,298,871 |
| Archive SHA-256 | `47674276eff5b84eb002cff39ac0a11facea6bc3fdd7416a0e60e695c7ec8c7d` |
| Input-set SHA-256 | `1e059fa281eae5ba4461ddf359e9ee7d4bdb6adfc7f5d5fa846eee6815aa870f` |

The complete 10,941,309-byte inventory is tracked at
`results/derived/raw_bundles/scaled_tanh_instantiation/` with SHA-256
`f3394c70e22820e30fe4bfcd9552f9313c24b86da424f562f39e886ccfa9c97e`.
The archive payload remains ignored and outside Git; no public URL or automatic
fetch is claimed. The tracked inventory and checksum permit verification once
the payload is supplied, but do not themselves make a clean checkout contain
4.43 GB of raw data. The inventory records both the current description-only
config digest and the immutable execution-config digest; the compatibility
check accepts only that exact known wording migration.

The full gap raw tree, both failed Wheel tuning trees, and the end-to-end
development tree also remain ignored local data. No full gap, Wheel, or
end-to-end raw bundle is claimed.

A preassembly scan found 51,289 provenance-reference occurrences for 8,017
unique raw files absent from the current source tree. They retain recorded
SHA-256 bindings and are classified `not_in_source_tree` in the manifest-bound
`manifests/unavailable-source-inputs.json`. This differs from
`indexed_not_released`: hydrated mode has zero indexed omissions. No gap feeds a
main-body figure or table through tracked provenance. Four appendix artifacts
depend on 4,600 unique missing files: `paper/figures/theory_factor_drift.pdf`
(788), `paper/tables/executed_policy_results.tex` (3,511),
`paper/tables/linear_bound_ratios.tex` (841), and
`paper/tables/covertype_horizon_results.tex` (240); the first two overlap on 780
files. The remaining 3,417 occur in released legacy derived/provenance artifacts
that do not feed any currently included paper figure or table.

The current-contract Wheel smoke archive contains 192 validated runs and 577
files. Its local archive is 1,850,306 bytes with SHA-256
`eadf27a41ab21f32ac8188f93c7e75beb35e8b95e605dae8cf3c6e752320299d`.
The 137,021-byte tracked inventory has SHA-256
`66871634b4e4862cca7535c9443b4d55eb22adb6906e779e3ce81bef0bbc063e`.
The archive payload remains ignored and outside Git.

## Git History Cleanup

The feature branch was rewritten from `aa0e5f26` to remove the previously
committed `results/raw/` tree. The rewrite preserved the final tree hash
`3e0ce44c9eaafb7fee6e73b5c7e4b3b818f9388c`, all 56 commit
author/email/subject tuples, and linear history. No `results/raw/` object is
reachable from the rewritten branch. `HISTORY_REWRITE_MAP.json` records every
old/new commit pair, the observed remote lease, the external backup-bundle
checksum, and the verification results.

Commit `49c19ad0` adds a direct executable guard for this property:
`test_raw_results_are_absent_from_reachable_git_history` checks both
`git rev-list --objects HEAD` and `git log HEAD -- results/raw/` and requires
both searches to be empty when Git metadata is available.

## Anonymous Release and Pending Assembly

Commit `c80fe1a8` removes reconstructible identity channels from the anonymous
release path. The release builder now:

- discovers local identity terms from Git configuration and history plus the
  local account and host without writing those terms into the release;
- scans Python strings reconstructed by literal addition or adjacent literal
  sequences, not only contiguous source text;
- excludes the private release builder and its identity-bearing tests from both
  released tiers and their source manifests;
- structurally removes the leading private editor-alias class from the released
  paper validator while retaining its public validation rules;
- rewrites anonymized auxiliary raw checksum sidecars to bind the released
  sanitized payload; and
- scans every final released file and validates explicit anonymous author,
  address, affiliation, and institution declarations before atomic install.

Follow-up commits `362499a3` and `99738015` add contextual provenance resolution,
a manifest-bound unavailable-source inventory, recursive semantic NPZ scanning,
immutable raw-source snapshots, and archive-level membership, size, and SHA-256
verification. The canonical assembly script refuses a dirty checkout, verifies
the scaled-tanh full and Wheel smoke bundles, hydrates every available source
payload including smoke data, requires all 48,002 scaled-tanh files and zero
indexed omissions, excludes source-bundle workspaces and private release tools,
and emits a deterministic archive, member list, assembly report, and checksum
set. Numeric array bodies are checked for configured identity markers without
treating arbitrary binary bytes as email text.

Tests cover both tiers, reconstructed strings, structured NumPy payloads,
source mutation, unavailable-source semantics, whole-tree rescanning, validator
sanitization, payload rebinding, and archive validation. **The final clean
hydrated anonymous review archive from revision `99738015` is still pending**;
no final archive hash, size, upload, or manifest count is claimed here.

## Paper Packaging

- The main body occupies pages 1--7; references begin on page 8.
- `paper/main.pdf` has 72 physical pages at the audited source revision.
- The only material overfull warning is 5.1225 pt in the abstract/style block.
- Final checks report no unresolved reference, citation, duplicate-label,
  missing-figure, or Type 3 font issue.
- The official AISTATS 2027 kit remains unavailable. The source uses the
  repository's AISTATS 2026 style only as a provisional formatting baseline and
  emits explicit warnings because the official 2027 style and checklist are
  absent.

This is scientifically reviewable but not final AISTATS 2027 packaging until
the official style and checklist are installed and revalidated.

## Changed Files

The rewritten scalar-link revision range `0db89cf0..99738015` changes:

- manuscript sources and outputs: `paper/main.tex`, `paper/macros.tex`,
  `paper/main.pdf`, new/updated figures, generated tables, and provenance files;
- theory/test support: `experiments/theory_metrics.py`,
  `experiments/curvature_operators.py`, `experiments/nonlinear_environment.py`,
  and their tests;
- runners/configurations for scaled tanh, gap-dependent validation, Wheel, and
  end-to-end systems;
- artifact builders, Buck targets, reproduction scripts, and deterministic raw
  bundle tooling;
- full derived scaled-tanh and gap aggregates, spectral-tail reanalysis, smoke
  Wheel/systems artifacts, and their sidecars;
- the tracked full scaled-tanh inventory and archive checksum;
- the refreshed current-contract Wheel smoke outputs and bundle inventory; and
- the history-rewrite map and final audit records;
- hash-bound provenance sidecars for all main-body figures and generated tables;
  and
- hydrated anonymous-release construction, source-gap inventories, source
  snapshots, and final archive-verification logic.

The follow-up range `c80fe1a8..99738015` additionally changes anonymous-release
sanitization and tests, adds direct PCG and raw-history regression checks,
classifies the scaled-tanh transfer audit with provenance-bound per-trajectory
slacks, aligns the manuscript with the final-holdout chronology, binds the
previously missing coverage/MNIST main-artifact provenance, and hardens hydrated
release assembly.

The machine-readable changelog is refreshed through audited functional revision
`99738015`; the documentation commit follows that audited source state.

## Commit Sequence

The revision begins at rewritten commit `0db89cf0`. The complete pre/post
mapping is machine-readable in `HISTORY_REWRITE_MAP.json`. Important rewritten
terminal commits are:

- `d8e3e86e`: retain failed scaled-tanh full evaluation;
- `fdcd2e49`: add full gap-dependent result;
- `58067c35`: freeze efficient Wheel solver implementation;
- `b7e39b44`: preserve Wheel failure records;
- `19215f9f`: track full scaled-tanh inventory and archive checksum;
- `6bbe855a`: expand and harden feasible Wheel baselines;
- `230f0ab5`: record the stopped 300-iteration Wheel tuning attempt;
- `741c7ca5`: align manuscript claims with structured-link evidence;
- `bea1fa5f`: disclose exact raw-bundle availability;
- `98657c55`: finalize the scalar-link audit;
- `10a22079`: refresh the current-contract Wheel smoke reproduction;
- `c80fe1a8`: remove reconstructible identities from anonymous releases;
- `49c19ad0`: add direct PCG and reachable-raw-history tests;
- `de3a9c6f`: classify retained scaled-tanh transfer-audit failures;
- `9ffac51b`: align the paper with final-holdout and numerical-audit semantics;
- `0d74b267`: bind coverage/MNIST main-artifact provenance;
- `362499a3`: assemble hydrated anonymous evidence; and
- `99738015`: verify immutable release inputs and every archive member.

## Validation Performed

- Wheel benchmark module: 10 tests passed.
- Wheel raw-bundle module: 3 tests passed.
- Wheel runner and artifact-builder Buck targets built successfully.
- Gap/end-to-end focused artifact tests: 9 passed in the earlier evidence pass.
- Scaled-tanh artifacts validate all 8,000 raw manifests and sidecars.
- Gap artifacts validate all 1,000 raw manifests and sidecars.
- Full scaled-tanh bundle verification validates 8,000 runs, 48,002 files,
  exact-tree membership, manifest bindings, readable archives, and checksums.
- Both Wheel failed-tuning directories contain the reported number of
  `failure.json` files with matching checksum sidecars.
- The canonical Buck suite `//tests:tests //experiments/tests:tests` passed both
  targets with zero failures or timeouts.
- The main-body provenance test parses the pre-appendix manuscript and validates
  artifact and direct-input hashes for every included figure and generated
  table. Seven coverage/MNIST sidecars were added without changing the generated
  artifacts.
- References and citations resolve, and all 18 figure PDFs embed Type
  42/FontFile2 fonts rather than Type 3.
- Full scaled-tanh and current Wheel smoke bundle verification passed with the
  counts and hashes reported above.
- The direct noncommuting-Jacobi PCG test verifies the original-system and
  symmetrically transformed energy-error identities to `2e-14` tolerance.
- The Git-history regression test directly checks that no reachable object or
  commit path remains under `results/raw/`.
- The scaled-tanh failure audit retains all 148 failed theorem trajectories and
  reports the per-trajectory transfer slacks, trust-region violation, tolerance,
  and analytic-versus-float64 classification summarized above.
- A clean current manuscript build produced 72 pages with the main body on
  pages 1--7.
- Anonymous-release remediation tests pass for both release tiers, including
  numeric-array identity scanning, raw-source mutation rejection, and
  declared-gap semantics. Archive-member verification logic is implemented; its
  final clean execution remains pending.

## Deliberately Unmade Claims

- No unrestricted neural-network regret theorem.
- No claim that generic neural width implies the scaled-tanh premises.
- No nonvacuous scaled-tanh theorem-instantiation claim.
- No full Wheel evaluation, selected Wheel configuration, or superiority claim.
- No faithful LO-FI/KFAC Wheel comparison.
- No end-to-end evaluation or CG-accuracy claim from development seed 7100.
- No full end-to-end systems scalability claim.
- No verified numerical enclosure from ordinary float64 residuals.
- No claim that the tracked inventory embeds or fetches the 4.43 GB archive.
- No final AISTATS 2027 style/checklist compliance claim.
- No claim that the final hydrated anonymous review archive has been assembled,
  uploaded, or assigned a final hash.

## Remaining External Requirement

Install the official AISTATS 2027 style and reproducibility checklist, then
rebuild and repeat page, font, reference, citation, and overfull-box checks.
Separately, run the canonical clean hydrated-review assembly before reporting
final package manifests, sizes, file counts, or upload status.
All further Wheel or end-to-end evaluation requires a solver change or a
predeclared failure policy; the existing failed runs must remain retained.
