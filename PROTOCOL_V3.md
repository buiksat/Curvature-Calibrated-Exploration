# Protocol v3: an informative-bound study of confidence transport

Status: **draft for author approval. No tuning or evaluation run has been made.**
Only development seeds were used (pilot below). Nothing in this file may change
after the first evaluation run starts; any change before that must be recorded
here with its reason.

Harness: `experiments/transport_v3.py`; analysis: `experiments/analyze_transport_v3.py`
(test, outside the pinned suites: `review/v3_protocol/test_transport_v3.py`). Every phase run writes
`manifest.json` with its arguments, commit, a dirty flag and SHA-256 of both
scientific modules. Pilot code state: commit `56d259a1`, stated by the drafting
agent; the pilot predates the manifest and records no commit. Its scoring,
confidence and UCB-GLM code paths are unchanged at the protocol commit; later
commits changed replay tolerances to per-check values, record failures that
were silent, and catch crashes. Pilot output:
`review/v3_protocol/dev_pilot_runs.jsonl`
(SHA-256 `b100027dae925a8b3f216a3ab47afe852a921b829089d68f395bc080d71d8573`).

## 1. Model and scale

| Item | Value |
|---|---|
| Contexts | x uniform on {(±1, ±1)/√2} (4 contexts), i.i.d. |
| Actions | K = 3, fixed order 0, 1, 2; ties to the smallest index |
| Features | φ(x, a) = x ⊗ e_a ∈ R⁶, ‖φ‖ = B_φ = 1; 12 categories |
| Teacher | regular-simplex interactions, θ°[iK + a] = v_a[i]/√3 with unit vertices v_a ∈ R² rotated by `default_rng(1729)`; ‖θ°‖ = R = 1 (`teacher` in the harness) |
| Mean | μ*(x, a) = √W tanh(φ(x, a)ᵀθ°/√W) |
| Noise | Gaussian, σ = 0.25; potential-outcome table shared across policies within a seed |
| d, T | d = 6, T = 20,000 |
| W | W = cT with **c = 1**, so W = 20,000 |
| λ, δ, projection radius | λ = 1 (confidence and training ridge), δ = 0.05, R = 1 |

**Why this scale.** The a priori bound on the A5 quantity depends on d, T, σ,
λ, δ and G, not on W (realized A5 varies slightly with W through the
trajectory). It uses γ_{t-1} ≤ Γ_{T,d} = d log(1 + T/(dλσ²)) = 65.31:
A5 ≤ 2√((σ² + 1)Γ·T(Γ + 2log(1/δ))) = 19,894, below the cap
2T·min(B_φR, √W) = 40,000 for every trajectory. The frozen policy's full
own-history bound (`prop:frozen-width-ucb`, with corrected-center β_t and
envelopes) has the deterministic a priori bound
2β̄√((σ² + 1)ΓT) + 4c_hR²T/√W with
β̄ = √(Γ + 2log(1/δ)) + √λR + 2c_hR²√T/(σ√W): 37,195, 26,976 and 23,745 at
c = 1, 10, 100, that is 0.93, 0.67 and 0.59 of the cap. The 29-parameter model
of the earlier study would need T of order 10⁵ for A5 alone to fall below its
cap (realized γ_T ≈ 151–154 at T = 1,000; `AUDIT_REPORT.md`, A5).

**Selection rule for c** (stated by the drafting agent to have been fixed
before the pilot output was read; no record predates the pilot output). The
smallest c in {1, 10, 100} for which the frozen policy's full own-history
bound is at most 0.9 × cap on every development seed. Result: c = 1.

**Pilot numbers** (development seeds 41000–41009, T = 20,000, optimizer
learning rate 1e-5, 20 steps per round; 150 runs, 0 recorded failures).
Columns: mean pseudo-regret (SD over 10 seeds), largest frozen-form bound/cap
over seeds, largest A5/cap, mean γ_T.

| c | Policy | Regret | Bound/cap max | A5/cap max | γ_T |
|---:|---|---|---:|---:|---:|
| 1 | Hessian | 78.47 (6.88) | 0.766 | 0.456 | 62.1 |
| 1 | endpoint | 66.01 (4.85) | 0.763 | 0.453 | 61.8 |
| 1 | frozen | 66.46 (5.31) | 0.762 | 0.453 | 61.7 |
| 1 | naive | 66.12 (4.76) | 0.763 | 0.453 | 61.8 |
| 1 | UCB-GLM | 29.53 (8.62) | — | — | — |
| 10 | Hessian | 52.63 (6.60) | 0.587 | 0.451 | 61.3 |
| 10 | endpoint | 49.71 (6.70) | 0.584 | 0.449 | 61.1 |
| 10 | frozen | 49.98 (5.15) | 0.584 | 0.449 | 61.1 |
| 10 | naive | 49.42 (6.93) | 0.584 | 0.449 | 61.1 |
| 10 | UCB-GLM | 30.55 (6.94) | — | — | — |
| 100 | Hessian | 44.65 (4.45) | 0.530 | 0.448 | 60.9 |
| 100 | endpoint | 44.96 (6.85) | 0.530 | 0.448 | 60.8 |
| 100 | frozen | 44.66 (4.33) | 0.530 | 0.449 | 60.9 |
| 100 | naive | 44.66 (6.72) | 0.530 | 0.448 | 60.9 |
| 100 | UCB-GLM | 30.17 (7.28) | — | — | — |

The context-free benchmark's mean regret on the same streams is 9,383.6 in
every cell. Other pilot observations at c = 1: for the frozen policy,
zero-width optimism holds on 0.823–0.929 of state-action pairs (range over
seeds) and the bonus-gap condition of A3 holds on at most 0.0002 of rounds on
any seed; over all four corrected policies s/s̄ lies in
[1 − 1.11 × 10⁻⁶, 1 + 1.28 × 10⁻⁵]; for the frozen policy at round 20,000 of seed 41000,
β = 15.36 with stochastic 8.23, ridge 1 and historical 6.13 terms.

**Curvature at this scale is negligible, so H2 is expected by construction.**
At W = 20,000 the relative weights differ from 1 by at most
1 − sech²(1/√W) = 5.0 × 10⁻⁵, and Corollary 13 bounds d_Th by
4 log cosh(1/√W) = 1.0 × 10⁻⁴ for every history. Equivalence of frozen,
endpoint and naive here tests whether score perturbations of order 10⁻⁵ move
regret by Δ; it says nothing about regimes where curvature matters. This
follows from the task's constraints: for these constants the frozen bound is
below the cap only when W is of order T. The c effect in the pilot appears in
the frozen arm too (66.5 at c = 1 to 44.7 at c = 100) and tracks the Taylor
envelopes: over the corrected-policy runs, the largest historical β term at
round 20,000 falls from 6.15 to 0.61 and the largest b_t at the recorded
rounds from 0.0109 to 0.0011.

## 2. Policies

All five use the same streams and observe only the selected reward.

**Corrected-center policies** (code reused unchanged from
`experiments/transport_instantiation.py`: `confidence_radius`,
`policy_scores`, `inverse_quadratic_widths`, `information_gain`,
`thompson_distance`, `cholesky_solve`). Center
m_t(a) = μ_{θ_t}(x_t, a) + q_t(a)ᵀ(θ̂_t − θ_t) with θ̂_t the frozen ridge
estimate on pseudo-responses; radius β_t^corr with ε_mis = 0 and
ε_lin(s) = ½(c_h/√W)(R + ‖θ_s‖)²; bias b_t = ½(c_h/√W)(R + ‖θ_t‖)²;
score m_t(a) + β_t w_t(a) + b_t with

| Policy | w_t(a) |
|---|---|
| Hessian | e^{D̄_t/2} s_t(a), D̄_t = 2(c_h/√W)√Q_t/(σ√λ) |
| endpoint | e^{d_Th(V̄_t, V_t)/2} s_t(a) |
| frozen | s̄_t(a) |
| naive | s_t(a) (uncertified control) |

θ_t: projected full-batch gradient descent on
Σ(r_s − μ_θ)²/(2σ²) + ‖θ‖²/2 from θ_1 = 0, `steps_per_round` steps per round
then one projection onto ‖θ‖ ≤ 1; learning rate and steps from tuning (§5).

**UCB-GLM** (Li, Lu and Zhou 2017, Algorithm 1; arXiv:1703.00048v2).
Link μ(u) = √W tanh(u/√W). Random uniform actions until
λ_min(Σ_{i≤τ} X_iX_iᵀ) ≥ 1, the premise λ_min(V_{τ+1}) ≥ 1 of their Lemma 3;
their Theorem 2 fixes τ only up to an unspecified universal constant, so this
operationalization is ours. Then θ̂_t solves Σ_{i<t}(Y_i − μ(X_iᵀθ))X_i = 0
(Newton, warm start, at most 50 iterations; nonconvergence is recorded, not
hidden), and a_t = argmax_a X_{t,a}ᵀθ̂_t + α‖X_{t,a}‖_{V_t⁻¹} with
V_t = Σ_{i<t} X_iX_iᵀ, α = (σ/κ)√((d/2)log(1 + 2T/d) + log(1/δ)), and
κ = sech²((R + 1)/√W) (their Assumption 1 with ‖θ°‖ ≤ R). Their Theorem 2
does not apply as stated (it assumes rewards in [0, 1]); this baseline is an
exactly specified algorithm, not a certified one.

**Context-free benchmark** (as in the earlier study): pull actions 0, 1, 2
once, then the smallest-index largest empirical mean of selected rewards,
ignoring context.

## 3. Hypotheses and tests

Unit of analysis: evaluation seed (n = 50); outcome: cumulative pseudo-regret
at T. All tests are paired by seed.

- **H1. Every policy beats the context-free benchmark.** For each of the five
  policies, one-sided paired t-test of mean(policy − context-free) < 0.
  Holm–Bonferroni across the five at familywise α = 0.05.
- **H2. Frozen, endpoint and naive are equivalent within Δ.** Two one-sided
  tests (TOST) for each of endpoint − frozen, naive − frozen and
  endpoint − naive: equivalence is concluded for a pair when the two-sided 90%
  paired-t interval lies inside (−Δ, Δ). H2 holds only if all three pairs pass
  (intersection–union test, level 0.05 without adjustment).
  Failure to reject a difference is never reported as equivalence.
- **H3. The frozen bound is below the cap on every run.** For each evaluation
  run of the frozen policy, check frozen-form bound < 40,000; H3 fails if any
  run does not. The a priori bound above (0.93 of the cap at c = 1) already
  implies this in exact arithmetic, so H3 is a numerical confirmation, not a
  stochastic test. A5 < cap is reported for every run of every corrected policy.

**Failed runs.** Every run is retained. The harness records replay-check
excesses, a negative running Q, Newton nonconvergence and an unreached τ as
run failures; such runs stay in all analyses and are listed. An exception in a
run is recorded as a crash and does not stop the phase. A crashed
policy–seed pair is excluded from every test involving that policy and
listed; H3 fails if any frozen run crashed. Evaluation seeds are never rerun.

**Margin Δ = 6.65 regret units, fixed now and never recomputed.** Rule
(stated by the drafting agent to have been fixed before the pilot output was
read; no record predates it): 10% of the frozen policy's mean pilot regret at
the selected c, 0.1 × 66.464 = 6.646, rounded to 6.65. Justification from development data: the paired-difference SDs
are 2.31 (endpoint − frozen), 2.47 (naive − frozen) and 0.33
(endpoint − naive), with dev means −0.45, −0.35 and −0.10. At n = 50 the
normal-approximation TOST power at a true difference of 0 exceeds 0.999 for
each pair. These SDs come from 10 seeds and are themselves uncertain.

## 4. Primary comparison and multiplicity

- **Primary:** endpoint − frozen, TOST at Δ = 6.65, α = 0.05 (one of the H2
  pairs). Motivated by Draft T3 (`paper/drafts/v3_theory_positioning.tex`),
  which bounds the endpoint exploration term relative to the frozen one as
  bound expressions; T3 does not predict equivalence of realized regret.
- H1: Holm across 5. H2: intersection–union, no adjustment. H3: deterministic.
- **Secondary, unadjusted, labeled as such:** Hessian − frozen and
  UCB-GLM − frozen, with 95% percentile intervals from 10,000 resamples of
  seed-paired differences, `np.random.default_rng(derive_child_seed(41200,
  "transport_v3/bootstrap"))`.
- All of H1–H3, the primary and secondary comparisons and the tuning
  selection are implemented in `experiments/analyze_transport_v3.py`, which is
  committed before any tuning or evaluation run. A dry run on the c = 1 pilot
  runs (development data, n = 10) executed without error; its outputs are not
  evidence for the hypotheses.
- **Descriptive:** per-run γ_T, A5/cap, bound/cap, β_t terms at rounds 1, 10,
  100, 1,000, 10,000, 20,000, zero-width-optimism fraction, bonus-gap and
  width-argmax fractions, s/s̄ quantiles, replay checks, runtime, failures.

## 5. Seeds and phases

Order, as the task specifies: development, tuning, evaluation.

| Phase | Seeds | Runs | Rule |
|---|---|---:|---|
| Development | 41000–41009 | 50 at c = 1, learning rate 1e-5, 20 steps | stop and report to the author, with no tuning or evaluation, if any replay check fails or any frozen bound exceeds 0.9 × cap |
| Tuning | 41100–41109 | 60 at c = 1, uniform behavior | learning rate ∈ {3e-6, 1e-5, 3e-5} × steps ∈ {5, 20}; score = mean over the 10 seeds of per-run all-action prediction MSE after a 10% burn-in; a configuration with any failed or nonfinite seed is disqualified; ties to the smaller rate, then fewer steps (`analyze_transport_v3 tuning`) |
| Evaluation | 41200–41249 | 250 at c = 1 with the tuned optimizer | the tests above; the CLI has no optimizer default, and the values used are recorded in `manifest.json` |

All ranges are disjoint from 30000–30249; `parse_seeds` rejects that range
and empty ranges. The pilot already used the development seeds; tuning and
evaluation seeds have not been used.

## 6. Current matrix from category counts

V_t = λI + σ⁻² Σ_c n_{t,c} sech⁴(φ_cᵀθ_t/√W) φ_cφ_cᵀ over the 12 categories;
the frozen matrix is accumulated by rank-one updates and checked against its
category form λI + σ⁻²Σ_c F_{t,c}φ_cφ_cᵀ, F_{t,c} = Σ_{s<t: c} sech⁴(φ_cᵀθ_s/√W);
Q_t uses running sums. At rounds 1, 10, 100, 1,000, 10,000 and 20,000 each run
rebuilds V_t by dense per-observation replay and Q_t directly. Tolerance, per check: 4096·ε_mach·d·max(1, largest absolute entry of the two
compared objects), adapted from the earlier study's rule, which uses the
operator norm. Any excess is recorded as a run failure.
**Pilot result** (pooled tolerance over the three checks, as the pilot code
computed it): 120 corrected-policy runs × 6 checkpoints, 0 failures; the
largest discrepancy/tolerance ratio was 3.13 × 10⁻².

## 7. Compute estimate

Measured in the pilot (16 worker processes, one BLAS thread each): 120
corrected-policy runs took 3,015 CPU-seconds (about 25 s each) and 30 UCB-GLM
runs took 124 CPU-seconds; wall time 3 min 30 s. Projection: development
50 runs ≈ 0.3 CPU-h, tuning 60 runs not yet measured at T = 20,000, evaluation 250 runs ≈ 1.4 CPU-h; under 15 minutes wall with 16
workers. Storage: about 2.6 kB per run summary.

## 8. Differences from `PHASE2_PLAN.md`

| `PHASE2_PLAN.md` | This protocol | Reason |
|---|---|---|
| d = 2, φ = (1, aξ)/√2 | d = 6, kron features, 3 actions, 4 contexts | the d = 2 design has two orthogonal feature vectors, so it reduces to a two-armed bandit with gap ≈ 1.41 ≈ 5.7σ and context only relabels actions |
| c = 100 | c = 1 by a prespecified dev rule | smallest c meeting the bound margin; larger Taylor envelopes at the same cost; curvature is negligible at either c (d_Th ≤ 1.0 × 10⁻⁴ at c = 1) |
| no GLM baseline | UCB-GLM | required by the task |
| primary: Hessian − frozen difference | primary: endpoint − frozen TOST | the task's equivalence hypothesis and Draft T3 |
| development 41000–41001 | 41000–41009 | variance estimate for Δ |
| Section A necessity instance | not included | outside this task |
