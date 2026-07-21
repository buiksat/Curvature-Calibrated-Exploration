# Revision Plan

Audit date: 2026-07-21

## Objective

Repair the acceptance-critical theory, implementation, and empirical gaps in
`Curvature-Calibrated Exploration for Differentiable-Model Bandits` without
inventing results.  The work order is deliberately gated: manuscript claims are
changed only after the corresponding proof, executable policy, and artifact are
available.

## Baseline established before editing

- Root manuscript: `paper/main.tex`; bibliography: `paper/references.bib`.
- `paper/true_ggn.tex` is standalone and is not included by the root source.
- Existing suite: 96 tests passed with `.venv/bin/python -m pytest -q`.
- Existing clean build: `latexmk -C` followed by `latexmk -pdf
  -interaction=nonstopmode -halt-on-error main.tex` succeeded in `paper/`.
- Existing PDF: 36 pages; main text ends on page 7, references start on page 8,
  Algorithm 1 is on page 3, Figure 1 on page 6, and Table 1 on page 7.
- Current hardware: Apple M4 Max, 64 GiB unified memory, 40-core integrated GPU.
  The experiment environment has NumPy/SciPy but no PyTorch or JAX accelerator
  backend.  Existing systems results are CPU-only synthetic microbenchmarks.
- The local Covertype cache is present.  Its source remains an external UCI data
  dependency and its current contextual policies fail the noncontextual sanity
  check.

## Work order

### 0. Audit and freeze the evidentiary baseline

**Status: completed.**  The baseline files remain preserved, and the new
reports retain separate executed-policy, offline-diagnostic, post-hoc, and
legacy classifications.

- Complete `THEORY_AUDIT.md`, `THEORY_BLOCKERS.md`, `EXPERIMENT_AUDIT.md`, and
  `RESULTS_STATUS.md`.
- Preserve all existing raw artifacts and seed partitions.
- Keep executed-policy, common-trajectory, post-hoc, certified, and legacy
  records separate.
- Do not edit `paper/aistats2026.sty`.

### 1. Operational O(d)-state certificates

**Status: completed in code and tests.**  `experiments/path_certificates.py`
implements the Welford/path state and pre-action schedules.  The tanh driver
records policy-available and post-hoc quantities separately.

- Implement a float64 `PathCertificateState` using vector Welford updates plus
  scalar residual, linearization, and observable information-gain accumulators.
- Implement pre-action `Q_t`, `chi_bar_t`, `M_bar_t`, `psi_bar_t`,
  `epsilon_bar_lin(t)`, `F_bar_t`, `gamma_hat`, `beta_bar_t`, and `u_t`.
- Encode the round filtration explicitly: compute schedules, choose action,
  observe reward, update certificate state, optimize, then certify the next
  optimizer residual.
- Add direct-history, dense-operator, centering, linearization, information-gain,
  and filtration tests before integrating a new policy.
- Repair current Corollary 13 and certificate-event bookkeeping only after the
  revised statements and tests agree.

### 2. Checked theory extensions

**Status: implemented, integrated, and independently proof-audited.**
The operational, near-linear, tanh-link, rank-sensitive refresh, endpoint, and
scalar-invariance results are in the manuscript and derivation audit.  They
must not be promoted beyond their explicit bounded-path and smoothness
assumptions.

- Prove the operational certificate result and trust-region refinement.
- Derive the bounded-path near-linear rate with every dependence on
  `T`, network-width parameter `W`, `lambda`, `sigma`, `R`, `G`, and residual
  energy explicit.
- State the required width lower bound obtained from the calculation; do not
  assume `W >= T^2` without the full constants and polylogarithmic terms.
- Add the analytically checkable `tanh(phi^T theta)` specialization.
- Add the rank-sensitive refresh and endpoint log-determinant bounds.
- Add scalar width-rescaling invariance.
- Record any failed derivation in `THEORY_BLOCKERS.md` and omit it from the paper.

### 3. Certified nonlinear execution

**Status: completed with a numerical-category qualification.**  Both fixed
centers were run on 50 evaluation seeds, with zero observed certificate,
confidence, or optimism failures.  All schedules are pre-action, but float64
checks are not verified enclosures; the rows are therefore
`posthoc_theorem_event_verified` rather than ex-ante theorem certified.

- Add a bounded tanh-link Gaussian bandit with analytic smoothness constants,
  projected iterates, exact pre-action optimizer residual, analytic CG condition
  bound, and no teacher access in action selection.
- Pre-register tuning and evaluation grids and use disjoint seeds.
- Run at least 30 evaluation seeds (50 when runtime permits).
- Save every predictable certificate and its exact post-hoc counterpart per
  round.  Gate success on zero observed certificate failures, not on a small
  regret bound.

### 4. Curvature mechanism and dynamic complexity

**Status: completed for the preregistered bounded-linear, zero-drift grid.**
Eight cells, seven methods, and 30 evaluation seeds were run online and on
separately labelled common trajectories.  Representation drift was fixed at
zero and remains an unrun extension.

- Add the anisotropy/rotation/gap/nuisance/effective-rank phase-diagram family.
- Run independent online policies and separately labelled common-trajectory
  diagnostics.
- Add actionwise width-ratio variation, rank correlations, score/action
  disagreement, normalized decision-margin distortion, eigenspace alignment,
  action-set transfer, effective rank, and conditioning.
- Do not select evaluation cells based on whether full curvature wins.

### 5. Fair baselines and contextual benchmark

**Status: completed for the required local baselines and a balanced synthetic
benchmark.**  Eleven methods were tuned on seeds 70--79 and rerun on 30 disjoint
evaluation seeds.  LinUCB passes the two context-free sanity comparisons.
NeuralUCB/NeuralTS are local matched implementations, not validated replicas of
published code; no external real-data replacement benchmark has passed.

- Add LinUCB, linear Thompson sampling, NeuralLinear, NeuralUCB or NeuralTS,
  diagonal and last-layer neural UCB, greedy, UCB1, and context-free Thompson
  sampling under matched streams and budgets.
- Add Wheel and/or a balanced supervised-to-bandit benchmark with deterministic
  data preparation, licenses, checksums, and independent evaluation seeds.
- Treat a benchmark as positive contextual evidence only when a competent
  contextual baseline beats both UCB1 and context-free Thompson sampling.
- Keep Covertype as a negative appendix sanity check unless that prerequisite is
  met on a new, independently evaluated protocol.

### 6. Solver and systems evidence

**Status: partially completed and claims restricted accordingly.**  Batched
independent CG and Jacobi-preconditioned batched CG are measured through
dimension 8192 in a five-seed synthetic CPU operator study.  No accelerator,
actual large neural model, KFAC, or block preconditioner result exists, so the
manuscript explicitly makes no large-model feasibility claim.

- Implement batched independent CG or block/recycled solves with per-action
  residual checks.
- Add symmetric preconditioned CG where valid, retaining checks in the original
  full-curvature system.
- Benchmark a substantially larger model only with an available, validated
  execution backend.  Otherwise retain CPU measurements and remove broader
  scalability claims.

### 7. Manuscript and release regeneration

**Status: completed for the executed scope.**  The manuscript, replacement
figure/table, provenance sidecars, independent proof review, 143-test suite,
clean LaTeX build, archival/review releases, identity scans, `CHANGELOG.md`, and
`CODEX_REPORT.md` are current.  Scope-expanding experiments remain unrun as
listed in `RESULTS_STATUS.md`.

- Rewrite the abstract, contributions, assumptions, experiments, related work,
  limitations, and conclusion only from completed artifacts.
- Remove the unrecovered legacy study from the evidentiary chain.
- Regenerate all included figures/tables and their provenance sidecars.
- Rebuild both anonymous supplement tiers and rerun text, binary, metadata, and
  hash scans.
- Produce `CHANGELOG.md` and `CODEX_REPORT.md` with exact reproduction commands.

## Acceptance-gate status

| Gate | Status on 2026-07-21 |
|---|---|
| 1. Fully computable `beta_bar_t`, `psi_bar_t`, and `u_t` | **Satisfied.** Implemented from pre-action path state and tested. |
| 2. Genuinely nonlinear predictable execution | **Satisfied in observed-event terms.** Two tanh centers x 50 evaluation seeds have zero observed failures.  Numerical classification remains post-hoc event verified. |
| 3. Explicit nonlinear rate or conditional-only reframing | **Satisfied.** The bounded-path near-linear corollary is explicit and independently proof-audited. |
| 4. Contextual benchmark passes noncontextual sanity check | **Satisfied narrowly.** The balanced synthetic benchmark passes on 30 evaluation seeds; Covertype still fails and no external replacement has passed. |
| 5. NeuralLinear plus a full neural-bandit baseline | **Satisfied locally.** NeuralLinear, NeuralUCB, and NeuralTS are evaluated under matched streams/budgets, without a published-code equivalence claim. |
| 6. Scalability claims supported or removed | **Satisfied by restriction.** Measured evidence is CPU-only through dimension 8192, and broad model/accelerator feasibility language is excluded. |
| 7. Legacy oracle study removed from evidentiary chain | **Satisfied in the current manuscript.** The unrecovered study no longer supports any claim. |

The proof, empirical, build, and release checks for the executed scope pass.
Optional or scope-expanding experiments remain labelled unrun; the report does
not claim an external passing benchmark, verified floating-point enclosure, or
accelerator/large-model validation.
