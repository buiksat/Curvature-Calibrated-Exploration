# Protocol v3: an informative-bound study of confidence transport

Status: **revision 2, draft for author approval. No tuning or evaluation run has
been made.** Only development seeds were used (pilots below). Nothing in this
file may change after the first evaluation run starts; any change before that
must be recorded in §9 with its reason.

Harness: `experiments/transport_v3.py`; analysis: `experiments/analyze_transport_v3.py`
(test, outside the pinned suites: `review/v3_protocol/test_transport_v3.py`).
Every phase run writes `manifest.json` with its arguments, commit, a dirty flag
and the SHA-256 of `experiments/transport_v3.py` and
`experiments/transport_instantiation.py`.

Pilot of record: development pilot 5, commit `1b051a2b`, `dirty: false` in
both manifests. Output: `review/v3_protocol/dev_pilot5_runs.jsonl` (300 runs)
and its analysis `review/v3_protocol/dev_pilot5_analysis.json`; SHA-256 values
are in §8. Pilots 3 (commit `6f041f96`), 4 (`706ff746`) and 5 ran the same
300 jobs before and after the code-review fixes; every
recorded field of all 300 runs is identical across the three except
`runtime_seconds`, and pilot 5's analysis output equals pilot 4's (pilot 3's
lacks only the `available` field that `706ff746` added).
Pilots 1 and 2 are superseded (§9); pilot 1 output stays at
`review/v3_protocol/dev_pilot_runs.jsonl`
(SHA-256 `b100027dae925a8b3f216a3ab47afe852a921b829089d68f395bc080d71d8573`).

## 1. Design: one design cell and three descriptive cells

| Item | Value |
|---|---|
| Contexts | x uniform on {(±1, ±1)/√2} (4 contexts), i.i.d. |
| Actions | K = 3, fixed order 0, 1, 2; ties to the smallest index |
| Features | φ(x, a) = x ⊗ e_a ∈ R⁶, ‖φ‖ = B_φ = 1; 12 categories |
| Teacher | regular-simplex interactions, θ°[iK + a] = v_a[i]/√3 with unit vertices v_a ∈ R² rotated by `default_rng(1729)`; ‖θ°‖ = R = 1 (`teacher` in the harness) |
| Mean | μ*(x, a) = √W tanh(φ(x, a)ᵀθ°/√W) |
| Noise | Gaussian, σ = 0.25; potential-outcome table shared across policies within a seed and cell |
| d, T | d = 6, T = 20,000 |
| λ, δ, projection radius | λ = 1 (confidence and training ridge), δ = 0.05, R = 1 |
| Cells | W = cT with c = 1 (**design cell**, W = 20,000) and c = 0.005, 0.0005, 0.00005 (**descriptive cells**, W = 100, 10, 1) |

**Why two kinds of cell.** In the design cell the frozen policy's bound is
below the cap on every trajectory, but curvature is negligible: the relative
weights differ from 1 by at most 1 − sech²(1/√W) = 5.0 × 10⁻⁵, and
Corollary 13 bounds d_Th by 4 log cosh(1/√W) = 1.0 × 10⁻⁴. Equivalence of
frozen, endpoint and naive there is expected by construction. In the
descriptive cells curvature matters (at W = 1, sech²(1) = 0.42 and
d_Th ≤ 1.735) but every certified bound is vacuous. No single cell has both
properties for these constants, because the frozen bound's historical-radius
and bias terms scale as √T/√W and T/√W. The study reports the design cell as
design checks plus a primary family, and the descriptive cells without tests.

**A priori bounds in the design cell.** With γ_{t−1} ≤ Γ_{T,d} =
d log(1 + T/(dλσ²)) = 65.31, A5 ≤ 2√((σ² + 1)Γ·T(Γ + 2log(1/δ))) = 19,894,
below the cap 2T·min(B_φR, √W) = 40,000 for every trajectory. The frozen
policy's full own-history bound (`prop:frozen-width-ucb`, with corrected-center
β_t and envelopes) is at most 2β̄√((σ² + 1)ΓT) + 4c_hR²T/√W with
β̄ = √(Γ + 2log(1/δ)) + √λR + 2c_hR²√T/(σ√W): 37,195 at c = 1, that is 0.93
of the cap.

**Selection of c.** Design cell: the smallest c in {1, 10, 100} for which the
frozen bound is at most 0.9 × cap on every development seed (stated by the
drafting agent to have been fixed before pilot 1 output was read; no record
predates that output). Result: c = 1. Descriptive cells: W = 100, 10, 1 were
chosen after pilot 2 output was read, on the recommendation of an independent
reviewer consulted by the author, to span near-linear to strongly curved; they
carry no test.

## 2. Policies

Every policy observes only the selected reward, and all policies in a cell
use the same context and potential-outcome streams for a given seed.

| Arm | Cells | Status |
|---|---|---|
| Hessian transport | all | certified (Corollary 12 width) |
| endpoint transport | all | certified (endpoint width) |
| frozen | all | certified on its own trajectory |
| naive | all | uncertified control |
| envelope-free frozen | W = 100, 10, 1 | uncertified ablation |
| envelope-free naive | W = 100, 10, 1 | uncertified ablation |
| LinUCB | all | uncertified linear baseline |
| UCB-GLM | all | exactly specified GLM baseline; its theorem does not apply (below) |

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
| Hessian | e^{D̄_t/2} s_t(a), D̄_t = 2(c_h/√W)√Q_t/(σ√λ), Q_t = Σ_{s<t}‖θ_t − θ_s‖² |
| endpoint | e^{d_Th(V̄_t, V_t)/2} s_t(a) |
| frozen | s̄_t(a) |
| naive | s_t(a) |

θ_t: projected full-batch gradient descent on
Σ(r_s − μ_θ)²/(2σ²) + ‖θ‖²/2 from θ_1 = 0, `steps_per_round` steps per round
then one projection onto ‖θ‖ ≤ 1. One optimizer (learning rate, steps) is
selected in tuning in the design cell (§5) and used in every cell.

**Envelope-free frozen and naive.** As frozen and naive, with
β_t = √(γ_{t−1} + 2log(1/δ)) + √λR and b_t = 0, that is, without the
historical-linearization term and the bias. They are uncertified under the
scaled-tanh misspecification. The harness still records their
`frozen_form_bound` computed from their own β_t and b_t; that number omits
the envelope terms and is **not** a bound on their regret. It is reported only
to show which terms make the certified bound vacuous.

**LinUCB.** The paper's corrected-center construction with the linear model
φᵀθ: ridge regression on raw rewards with metric λI + σ⁻²Σ_{s<t}φ_sφ_sᵀ,
β_t = √(γ_{t−1} + 2log(1/δ)) + √λR, b_t = 0, score φᵀθ̂_t + β_t‖φ‖_{V_t⁻¹}.
This radius has the form of the self-normalized linear confidence set; the
source usually cited for it (Abbasi-Yadkori, Pál and Szepesvári, 2011) was not
opened in this work, so the protocol specifies the construction directly and
does not attribute it. Under the scaled-tanh means it is misspecified and
uncertified.

**UCB-GLM** (Li, Lu and Zhou 2017, Algorithm 1; arXiv:1703.00048v2).
Link μ(u) = √W tanh(u/√W). Uniform random actions, from a stream derived from
the seed, until λ_min(Σ_{i≤τ} X_iX_iᵀ) ≥ 1, the premise λ_min(V_{τ+1}) ≥ 1 of
their Lemma 3; their Theorem 2 fixes τ only up to an unspecified universal
constant, so this operationalization is ours. Then θ̂_t solves
Σ_{i<t}(Y_i − μ(X_iᵀθ))X_i = 0 (`glm_solve`: Newton with Armijo backtracking
on the convex objective Σ_c [n_c W log cosh(u_c/√W) − S_c u_c], warm start,
at most 50 iterations; a singular or nonfinite step or a failed line search
stops at the last accepted iterate and is recorded as nonconvergence), and
a_t = argmax_a X_{t,a}ᵀθ̂_t + α‖X_{t,a}‖_{V_t⁻¹} with V_t = Σ_{i<t} X_iX_iᵀ, α = (σ/κ)√((d/2)log(1 + 2T/d) + log(1/δ)) and
κ = sech²((R + 1)/√W) (their Assumption 1 with ‖θ°‖ ≤ R and the
initialization ball ‖θ − θ°‖ ≤ 1). Their Theorem 2 assumes rewards in [0, 1],
so it does not apply as stated.

| W | κ | α | τ observed in pilot 5 |
|---:|---:|---:|---|
| 20,000 | 0.9998 | 1.356 | 12–50 |
| 100 | 0.9610 | 1.411 | 12–50 |
| 10 | 0.6867 | 1.974 | 12–50 |
| 1 | 0.0707 | 19.190 | 12–50 |

At W = 1 the 1/κ factor makes α about 14 times its W = 20,000 value, which
explains UCB-GLM's regret there (§4 pilot table): the baseline is run exactly
as specified, not retuned per cell.

**Context-free benchmark** (as in the earlier study): pull actions 0, 1, 2
once, then the smallest-index largest empirical mean of selected rewards,
ignoring context.

## 3. Design cell: design checks and primary family

Unit of analysis: evaluation seed (n = 50); outcome: cumulative pseudo-regret
at T. All tests are paired by seed.

**Design checks** (expected to pass by construction; reported as checks of the
setup, not as findings):

- **H1. Every policy beats the context-free benchmark.** For each of the six
  arms in the cell (Hessian, endpoint, frozen, naive, LinUCB, UCB-GLM),
  one-sided paired t-test of mean(policy − context-free) < 0; Holm–Bonferroni
  across the six at familywise α = 0.05.
- **H2. Frozen, endpoint and naive are equivalent within Δ = 3.0.** TOST for
  each of endpoint − frozen, naive − frozen and endpoint − naive: equivalence
  for a pair when the two-sided 90% paired-t interval lies inside (−Δ, Δ). H2
  holds only if all three pairs pass (intersection–union, level 0.05 without
  adjustment). Failure to reject a difference is never reported as
  equivalence.
- **H3. The frozen bound is below the cap on every run.** For each frozen run,
  frozen-form bound < 40,000; H3 fails if any run does not or any frozen run
  crashed. The a priori bound (0.93 of the cap) implies this in exact
  arithmetic, so H3 is a numerical confirmation. A5 < cap is reported for
  every run of every certified arm.

**Margin Δ = 3.0 regret units, fixed now and never recomputed.** Anchor: a
quarter of the pilot's Hessian − frozen mean gap, 12.0/4 = 3.0. A difference
of the size the Hessian width produced is then far outside the margin, and so
is any difference a quarter of that size or larger. Revision 1 used 6.65 (10% of the frozen arm's mean
regret); see §9. Pilot paired-difference means (SD) over 10 seeds:
endpoint − frozen −0.45 (2.31), naive − frozen −0.35 (2.47),
endpoint − naive −0.10 (0.32). At n = 50 the normal-approximation TOST power
at those means exceeds 0.999 for each pair. The SDs come from 10 seeds and
are themselves uncertain.

**Primary family** (the comparisons the paper's claims rest on):

- UCB-GLM − frozen, and Hessian − frozen.
- Each: two-sided paired t-test of mean difference = 0; Holm across the two at
  familywise α = 0.05.
- Pilot values (n = 10, development data, not evidence): Hessian − frozen
  12.0, 95% bootstrap interval [8.65, 15.28]; UCB-GLM − frozen −36.94
  [−42.71, −31.17].

**Intervals.** Decisions use the t-based procedures above. For every paired
difference in every cell, including the primary pairs, the analysis also
reports a 95% percentile bootstrap interval from 10,000 resamples of
seed-paired differences, generated by
`np.random.default_rng(derive_child_seed(41200, "transport_v3/bootstrap/<W>/<pair>"))`.
Bootstrap intervals are descriptive; when they and a t-based decision
disagree, the t-based decision is the reported result and the disagreement is
stated.

## 4. Descriptive cells (W = 100, 10, 1)

No hypothesis test and no multiplicity adjustment. For each cell the analysis
reports mean regret per arm, the context-free benchmark, optimism-failure
pairs, s/s̄ ranges, and these seed-paired differences with bootstrap
intervals: naive − frozen, endpoint − frozen, envelope-free naive −
envelope-free frozen, Hessian − frozen, LinUCB − frozen, UCB-GLM − frozen.
Per-run β_t terms at rounds 1, 10, 100, 1,000, 10,000 and 20,000 show which
term drives the vacuous bound.

**Pilot 5 by cell** (development seeds 41000–41009, learning rate 1e-5, 20
steps per round; 300 runs, 0 crashes, 0 recorded failures, 0 Newton
nonconvergences; 0 optimism-failure pairs for every arm that records the
diagnostic, which UCB-GLM does not). Mean pseudo-regret (SD over 10 seeds);
for corrected-center arms also the largest frozen-form bound/cap and A5/cap
over seeds and mean γ_T.

| W | Arm | Regret | Bound/cap max | A5/cap max | γ_T |
|---:|---|---|---:|---:|---:|
| 20,000 | Hessian | 78.47 (6.88) | 0.766 | 0.456 | 62.1 |
| 20,000 | endpoint | 66.01 (4.85) | 0.763 | 0.453 | 61.8 |
| 20,000 | frozen | 66.46 (5.31) | 0.762 | 0.453 | 61.7 |
| 20,000 | naive | 66.12 (4.76) | 0.763 | 0.453 | 61.8 |
| 20,000 | LinUCB | 43.95 (4.78) | — | — | — |
| 20,000 | UCB-GLM | 29.53 (8.62) | — | — | — |
| 100 | Hessian | 1814.43 (140.55) | 4.278 | 0.475 | 65.2 |
| 100 | endpoint | 440.81 (5.62) | 4.249 | 0.469 | 64.3 |
| 100 | frozen | 443.51 (3.91) | 4.250 | 0.469 | 64.3 |
| 100 | naive | 443.77 (8.58) | 4.249 | 0.469 | 64.3 |
| 100 | envelope-free frozen | 42.32 (5.18) | 0.505* | 0.448 | 60.7 |
| 100 | envelope-free naive | 41.03 (4.60) | 0.504* | 0.447 | 60.7 |
| 100 | LinUCB | 43.03 (5.04) | — | — | — |
| 100 | UCB-GLM | 31.88 (7.98) | — | — | — |
| 10 | Hessian | 3424.79 (114.97) | 12.416 | 0.475 | 65.1 |
| 10 | endpoint | 1003.59 (7.44) | 12.381 | 0.472 | 64.8 |
| 10 | frozen | 1004.02 (7.79) | 12.378 | 0.472 | 64.8 |
| 10 | naive | 1003.42 (7.87) | 12.382 | 0.472 | 64.8 |
| 10 | envelope-free frozen | 39.78 (7.33) | 0.503* | 0.446 | 60.5 |
| 10 | envelope-free naive | 42.96 (4.72) | 0.504* | 0.447 | 60.5 |
| 10 | LinUCB | 42.90 (5.81) | — | — | — |
| 10 | UCB-GLM | 45.53 (6.62) | — | — | — |
| 1 | Hessian | 8671.60 (62.51) | 37.656 | 0.463 | 63.4 |
| 1 | endpoint | 1891.37 (48.55) | 37.637 | 0.462 | 63.3 |
| 1 | frozen | 1895.10 (52.04) | 37.615 | 0.462 | 63.3 |
| 1 | naive | 1885.19 (47.81) | 37.629 | 0.462 | 63.3 |
| 1 | envelope-free frozen | 41.83 (5.61) | 0.492* | 0.436 | 59.0 |
| 1 | envelope-free naive | 40.60 (4.83) | 0.491* | 0.435 | 59.0 |
| 1 | LinUCB | 41.88 (6.20) | — | — | — |
| 1 | UCB-GLM | 342.48 (5.26) | — | — | — |

\* Not a bound; computed without the envelope terms (§2).

Context-free benchmark mean regret on the same streams: 9,383.6, 9,375.7,
9,313.4 and 8,661.6 at W = 20,000, 100, 10, 1.

Other pilot observations:

- s/s̄ over the four certified arms lies in [1 − 1.1 × 10⁻⁶, 1 + 1.3 × 10⁻⁵]
  at W = 20,000 and in [0.9745, 1.306] at W = 1.
- The frozen arm's historical β term at round 20,000 of seed 41000 is 6.13,
  86.6, 274.9 and 867.6 at W = 20,000, 100, 10, 1 (stochastic term 8.2–8.4;
  ridge term 1). The certified arms' regret in the descriptive cells follows
  this term and the bias, not the width choice: certified frozen, endpoint
  and naive stay within 10 regret units of each other in every cell, while
  the envelope-free arms are near 40.
- At W = 1 the Hessian arm's `gap_dominated_fraction` (rounds on which the
  gap between the two largest scores exceeds the range of the centers) reaches
  0.998 on at least one seed, and its regret (8,671.6) is close to the
  context-free benchmark's (8,661.6).

## 5. Seeds, phases and runs

| Phase | Seeds | Runs | Rule |
|---|---|---:|---|
| Development | 41000–41009 | 300 (pilot 5) | done; stop and report if any replay check fails or any design-cell frozen bound exceeds 0.9 × cap |
| Tuning | 41100–41109 | 60, design cell only, uniform behavior | learning rate ∈ {3e-6, 1e-5, 3e-5} × steps ∈ {5, 20}; score = mean over the 10 seeds of per-run all-action prediction MSE after a 10% burn-in; a configuration with any failed or nonfinite seed is disqualified; ties to the smaller rate, then fewer steps (`analyze_transport_v3 tuning`) |
| Evaluation | 41200–41249 | 1,500 = 50 × (6 arms at W = 20,000 + 8 arms × 3 descriptive cells) | the tuned optimizer in every cell; the CLI has no optimizer default, and the values used are recorded in `manifest.json` |

All ranges are disjoint from 30000–30249; `parse_seeds` rejects that range
and empty ranges. Tuning and evaluation seeds have not been used.

**Failed runs.** Every run is retained. The harness records replay-check
excesses, Newton nonconvergence and an unreached τ as run failures; such runs
stay in all analyses and are listed. An exception in a run, including a
nonfinite optimizer iterate or an overflowing Hessian factor e^{D̄_t/2}, is
recorded as a crash and does not stop the phase (in pilot 5 the largest D̄_t/2 at
the recorded checkpoint rounds is 24.5, at W = 1; float64 overflow needs
709.8; other rounds were not recorded). The analysis refuses
input that mixes optimizer settings or phases or repeats a W/arm/seed record,
and reports a primary pair with fewer than two seeds as unavailable, entering
Holm with p = 1. A crashed arm–seed pair is excluded from
every comparison involving that arm and listed; H3 fails if any frozen run
crashed. Evaluation seeds are never rerun.

## 6. Current matrix from category counts

V_t = λI + σ⁻² Σ_c n_{t,c} sech⁴(φ_cᵀθ_t/√W) φ_cφ_cᵀ over the 12 categories;
the frozen matrix is accumulated by rank-one updates and checked against its
category form λI + σ⁻²Σ_c F_{t,c}φ_cφ_cᵀ, F_{t,c} = Σ_{s<t: c} sech⁴(φ_cᵀθ_s/√W).
Q_t uses a running mean and scatter of θ_1, …, θ_{t−1} (Welford), so it is a
sum of nonnegative terms; pilot 2 showed that raw running sums cancel at small
W. At rounds 1, 10, 100, 1,000, 10,000 and 20,000 each run rebuilds V_t by
dense per-observation replay and Q_t directly. Tolerance, per check:
4096·ε_mach·d·max(1, largest absolute entry of the two compared objects),
adapted from the earlier study's operator-norm rule. Any excess is a run
failure. Pilot 5: 3,960 checks over 220 corrected-center runs, 0 failures;
largest discrepancy/tolerance 0.0345.

## 7. Compute estimate

Pilot 5 (20 worker processes, one BLAS thread each): 300 runs in 5 min 45 s
wall and 105 CPU-minutes (pilot 3: 5 min 39 s and 103 CPU-minutes). Mean run
time in pilot 5: 26.9 s for corrected-center arms (cell means 26.4–27.2 s), 5.8 s for LinUCB and 5.5–7.4 s for UCB-GLM by cell.
Projection: evaluation 1,500 runs (1,100 corrected-center, 200 LinUCB, 200
UCB-GLM) ≈ 8.9 CPU-hours, about 27 minutes wall with 20 workers; tuning 60 runs
not yet measured at T = 20,000.

## 8. Artifacts of record

| Artifact | SHA-256 |
|---|---|
| `review/v3_protocol/dev_pilot5_runs.jsonl` | ef94bf39142b0f0f97f05deede8c365add7c1cbaf917c69932b369eeb0db374c |
| `review/v3_protocol/dev_pilot5_analysis.json` | 047c5a80e857012a600a2d67d4359badcf35f1f74c4ad989f9e7b7707c6e95a2 |
| `review/v3_protocol/dev_pilot5_manifest_wT.json` | 0b9c8641c34d5ef831a02b906178e237178c0ff74fc1b132079bd6cf8531a5c3 |
| `review/v3_protocol/dev_pilot5_manifest_small.json` | 3e099c23096b00545e2235513c97dfbabf63cebb6e66244b04697ed85d6ba7aa |

The runs file is the concatenation of the design-cell and descriptive-cell
outputs, in that order. Commands (repository root, `OPENBLAS_NUM_THREADS=1`):

```
python -B -m experiments.transport_v3 --phase development --seeds 41000-41009 --c 1 \
  --learning-rate 1e-5 --steps 20 --methods transport_hessian transport_endpoint \
  frozen_reference naive_current linucb ucb_glm --output <wT> --workers 20
python -B -m experiments.transport_v3 --phase development --seeds 41000-41009 \
  --c 0.005 0.0005 0.00005 --learning-rate 1e-5 --steps 20 --methods transport_hessian \
  transport_endpoint frozen_reference naive_current frozen_reference_no_envelope \
  naive_current_no_envelope linucb ucb_glm --output <small> --workers 20
python -B -m experiments.analyze_transport_v3 evaluation <all.jsonl> --output <analysis.json>
```

## 9. Changes from revision 1

| Revision 1 | Revision 2 | Reason |
|---|---|---|
| one cell, W = T | design cell W = T plus descriptive cells W = 100, 10, 1 | H2 is expected by construction at W = T; the descriptive cells show the regime where curvature matters |
| five arms | adds LinUCB (all cells) and envelope-free frozen and naive (descriptive cells) | separate the width choice from the envelope terms, and compare with an uncertified linear baseline |
| Δ = 6.65 (10% of frozen mean) | Δ = 3.0 (a quarter of the Hessian − frozen gap) | anchors the margin to a difference the study can produce rather than to the regret level |
| primary: endpoint − frozen TOST | primary family: UCB-GLM − frozen and Hessian − frozen, two-sided, Holm over 2; H2 becomes a design check | UCB-GLM's lower regret and the Hessian width's cost are the comparisons the positioning rests on |
| secondary bootstrap intervals for two pairs | bootstrap intervals for every paired difference in every cell, labeled descriptive | one interval method for all reported differences |
| Q_t from raw running sums | Welford running mean and scatter | in pilot 2, 9 of 240 descriptive-cell runs failed the Q_t replay check at round 20,000 from cancellation (the commit message of `6f041f96` says 7; the pilot 2 output has 9) |
| pilot 1 (150 runs, c ∈ {1, 10, 100}) | pilot 5 (300 runs, commit `1b051a2b`) | pilot 2 (commit `6cb058f1`) found the Q_t defect; pilot 3 (`6f041f96`) was the first run of the revision-2 harness with no recorded failure; pilots 4 and 5 reran it after the code-review fixes below |
| no independent code review | read-only Codex review of the harness, analysis, audit script and tests at `6f041f96`, with two follow-ups (fixes in `706ff746` and `1b051a2b`) | non-Hessian arms no longer evaluate e^{D̄_t/2}; a nonfinite optimizer iterate is a crash; UCB-GLM's Newton solve is damped and never applies a rejected step; the analysis refuses mixed optimizer settings, phases and duplicates, survives a missing primary arm, and qualifies tuning only on ten distinct finite design-cell seeds; no pilot trajectory changed |

## 10. Differences from `PHASE2_PLAN.md`

| `PHASE2_PLAN.md` | This protocol | Reason |
|---|---|---|
| d = 2, φ = (1, aξ)/√2 | d = 6, kron features, 3 actions, 4 contexts | the d = 2 design has two orthogonal feature vectors, so it reduces to a two-armed bandit with gap ≈ 1.41 ≈ 5.7σ and context only relabels actions |
| c = 100 | design cell c = 1 by a prespecified dev rule, plus descriptive cells | smallest c meeting the bound margin; curvature is negligible at either c = 1 or c = 100 |
| no GLM baseline | UCB-GLM and LinUCB | required by the task (GLM); LinUCB added in revision 2 |
| primary: Hessian − frozen difference | primary family: UCB-GLM − frozen and Hessian − frozen | revision 2 |
| development 41000–41001 | 41000–41009 | variance estimate for Δ |
| Section A necessity instance | not included | outside this task |
