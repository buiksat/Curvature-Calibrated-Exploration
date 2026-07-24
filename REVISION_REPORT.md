# Resubmission Revision Report

Date: 2026-07-23

Branch: `codex/closed-rates-20260721`

Audited source revision: `bf5fa236297091e1b80dede777dfb03f8b3fdc72`

This report distinguishes proved statements, full evaluation evidence, failed
premise audits, development-only diagnostics, smoke checks, and unavailable raw
payloads. Ordinary float64 residuals are audits, not verified enclosures.

## Status Summary

| Item | Status | Evidence |
| --- | --- | --- |
| Relative scalar-link drift and centering | Complete | `lem:relative-link-drift` |
| Scaled-tanh conditional corollary | Complete as a theorem | `cor:scaled-tanh-relative` |
| Refined spectral-tail split and tightness | Complete | `lem:spectral-tail-logdet`, `prop:spectral-tail-tightness` |
| Gap-dependent exact-current corollary | Complete | `cor:gap-dependent-exact-current` |
| Fixed-preconditioner CG extension | Complete | `lem:pcg` |
| Full scaled-tanh evaluation | Executed; theorem-instantiation criterion failed | 8,000/8,000 runs |
| Full gap-dependent validation | Executed; recorded exact/full-CG premises passed | 1,000/1,000 runs |
| Refined spectral-tail reanalysis | Executed, analysis-only | Existing full trajectories |
| Full Wheel benchmark | Failed during tuning; evaluation not run | 56 + 27 hashed failure records |
| End-to-end systems full profile | Development seed only; solver residual checks failed | 48/48 cells, seed 7100 |
| Full scaled-tanh raw bundle | Locally verified; inventory tracked, payload outside Git | 4,425,351,907 bytes |
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

## Full Scaled-Tanh Evaluation: Retained Failure

Source: `results/derived/scaled_tanh_instantiation/full/aggregate.json`.

- 8,000 of 8,000 full-profile runs validate.
- The grid has five horizons, four normalized width ratios, eight methods, and
  50 untouched evaluation seeds (`1200--1249`).
- Optimizer damping was selected using tuning seeds only.
- The analytic relative-transfer certificate is below one in every cell and is
  strictly tighter than Welford in every cell.
- Dense exact and full-CG actions agree in every paired trajectory. The largest
  mean relative width-squared error is `1.282047550845858e-12`.
- The displayed RHS per round decreases at every width ratio.

The predeclared theorem-instantiation conjunction fails, so the aggregate sets
`supports_nonavacuous_instantiation_claim=false`.

| Method | Failed trajectories | Failed rounds | Failure fields |
| --- | ---: | ---: | --- |
| Exact current, relative certificate | 43 | 72 | optimizer 58; transfer 14 |
| Full CG, relative certificate | 51 | 80 | optimizer 58; transfer 14; CG convergence 8 |
| Current Welford | 40 | 77 | optimizer 77 |
| Corrected current | 14 | 14 | transfer 14 |

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

Commit `a999319c` expands the feasible local inventory to 12 methods:
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
2. Tuning was restarted cleanly from `a999319c` with a 300-iteration cap. It
   retained 27 hashed failures before the run was stopped. The documented
   example is delta `0.5`, seed `2008`, ridge `0.1`, bonus `0.5`, round 2761,
   residual `4.714088e-6`.
3. A development-only periodic residual-replacement diagnostic also failed at
   round 174 with residual `5.467890e-6`.

The failure logger preserved all observed failures. No evaluation policy was
run, no evaluation seed (`3000--3029`) was read, and no favorable cell or seed
was selected. Historical smoke artifacts predate the expanded inventory and
remain engineering checks only.

## End-to-End Systems: Development Diagnostic Only

A full-profile development run at clean revision
`95fe2d2ae201d4109605072942f9cadc4ad6fda1` completed all 48 configured cells
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

The complete 10,937,302-byte inventory is tracked at
`results/derived/raw_bundles/scaled_tanh_instantiation/` with SHA-256
`83c614b32407ae5d339f97e649346799a1d28c3d3d3454b6c0e8d0571f1bc490`.
The archive payload remains ignored and outside Git; no public URL or automatic
fetch is claimed. The tracked inventory and checksum permit verification once
the payload is supplied, but do not themselves make a clean checkout contain
4.43 GB of raw data.

The full gap raw tree, both failed Wheel tuning trees, and the end-to-end
development tree also remain ignored local data. No full gap, Wheel, or
end-to-end raw bundle is claimed.

## Paper Packaging

- The main body ends on numbered page 6.
- `paper/main.pdf` has 71 physical pages at `bf5fa236`.
- The only material overfull warning is 5.1225 pt in the abstract/style block.
- Final checks report no unresolved reference, citation, duplicate-label,
  missing-figure, or Type 3 font issue.
- The target-year AISTATS package is not available. The source uses the
  repository's AISTATS 2026 style provisionally and emits an explicit warning
  because the official target-year checklist is absent.

This is scientifically reviewable but not final target-year packaging until
the official style and checklist are installed and revalidated.

## Changed Files

The scalar-link revision range `4f94c3e5..bf5fa236` changes:

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
  Wheel/systems artifacts, and their sidecars; and
- the tracked full scaled-tanh inventory and archive checksum.

The machine-readable changelog records the full commit sequence and detailed
file groups.

## Commit Sequence

The revision begins at `4f94c3e5` and includes the theory/experiment/artifact
commits through `aa693eea`, followed by the final availability disclosure
`bf5fa236`. Important terminal commits are:

- `aed39c5a`: retain failed scaled-tanh full evaluation;
- `49159324`: add full gap-dependent result;
- `5d297af7`: freeze efficient Wheel solver implementation;
- `95fe2d2a`: preserve Wheel failure records;
- `51044565`: track full scaled-tanh inventory and archive checksum;
- `a999319c`: expand and harden feasible Wheel baselines;
- `f5d295b0`: record the stopped 300-iteration Wheel tuning attempt;
- `aa693eea`: align manuscript claims with structured-link evidence; and
- `bf5fa236`: disclose exact raw-bundle availability.

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
- The manuscript compiled to the checked PDF; references and citations resolve.

The complete repository test suite was not rerun after `bf5fa236`; this report
does not claim otherwise.

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
- No final target-year style/checklist compliance claim.

## Remaining External Requirement

Install the official target-year AISTATS style and reproducibility checklist,
then rebuild and repeat page, font, reference, citation, and overfull-box checks.
All further Wheel or end-to-end evaluation requires a solver change or a
predeclared failure policy; the existing failed runs must remain retained.
