# Phase 1 implementation audit of the 600-run nonlinear study

Branch `cce-transport-audit-v3`, based on `origin/cce-review-revisions` at
`2453a402`. No trajectory was run for this audit.

## Result

- The raw evaluation trajectories of the 600-run study are not on this host.
  Their recorded location, `/workspace/cce-full-local`
  (`review/post_fable_revision/RAW_ARCHIVE_STATUS.md`), does not exist here, and
  no `raw.jsonl` was found under `$HOME` or `/data/users/buiksat`. A
  host-wide search was blocked by the sandbox, so other paths were not searched.
- Committed per-seed derived artifacts of the same 600 runs answer A1, A3, A5
  and A6 per condition and policy, and bracket A2 at t = 1000. A4, and A2 at
  t = 10, 100 and 500, need per-round values that only the raw logs contain.
  These checks were not run on the evaluation data.
- One retained development trajectory (W = 0.25, Hessian policy, seed 30000,
  T = 1000) has every per-round field. It gives A2 at all four rounds and A4 as
  a proxy. It is one run in one condition, not evaluation evidence.
- H-a holds in the qualified sense below: the code envelope is
  norm-dependent and equals the H-a value at ‖θ_t‖ = R; its realized per-run
  mean is 0.983–0.985 of the H-a value (median over seeds; minimum 0.817).
- A4 is untested on the evaluation data. On the development proxy at W = 0.25,
  all 5,000 state-action pairs satisfy zero-width optimism.

**Decision rule outcome: not determinable as written.** Its first branch needs
A4 at W ≤ 1 on the study's pairs, which cannot be computed without the raw
logs. The envelopes are not materially tighter than H-a, so the stop branch is
not triggered by A1. Per the task's instruction for missing trajectories,
work continued to Phase 2. The A4 proxy supports the continue branch only at
W = 0.25 and only for one trajectory.

## Inputs and their integrity

| Input | Content | Check run | Outcome |
|---|---|---|---|
| `review/transport_review_followup/full-cce-full-local/seed_summaries.jsonl` | 600 per-run summaries | SHA-256 against `export_manifest.json` | match |
| `review/transport_relative_diagnostics/full/per_seed.jsonl` | 600 per-history score diagnostics | `sha256sum -c ARTIFACTS.sha256` | match |
| `review/transport_review_followup/development_refinement_raw.zip` | one 1000-round development trajectory | `sha256sum -c` sidecar | match |
| `experiments/*` at `2453a402` vs the 32 source hashes in `run_manifest.json` | code that produced the 600 runs | SHA-256 | 30 match; `experiments/BUCK` absent; `experiments/README.md` differs |

`experiments/transport_instantiation.py`, the configuration and the analyzer
inputs are among the 30 matching files, so `file:line` references below point
to the code that produced the runs. The derived artifacts were computed from
the raw logs by earlier analyses; their byte integrity is checked here, not the
raw content they summarize.

Reproduce every number below:

```bash
PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  "$CCE_VENV/bin/python" -B review/v3_audit/phase1_audit.py OUT.json
```

The committed output is `review/v3_audit/phase1_audit.json`. "Median [min, max]"
is over the 50 seeds of a cell unless stated otherwise.

## A1. Envelopes used by the code

| Quantity | Code value | Location |
|---|---|---|
| c_h | 4B_φ²/(3√3) = 0.769800 | `experiments/transport_instantiation.py:146-148` |
| L_μ = L_g | c_h/√W | `experiments/transport_instantiation.py:522-528` |
| ε_lin,t(a) (current) | ½ L_μ (R + ‖θ_t‖)², one scalar for all actions | `:193-204`, `:1564-1568` |
| ε_lin(s) (historical) | the round-s current envelope, ½ L_μ (R + ‖θ_s‖)² | `:1761`, `:1763-1772`; energy Σε² at `:909-911` |
| ε_mis(s), ε_mis,t(a) | absent, so 0; the teacher is the model mean at θ° | config `exact_realizability: true` (`experiments/configs/transport_review_followup.yaml:27`); `:543-549` |
| β_t^corr | √(γ_{t-1} + 2log(1/δ)) + √λR + √(Σ_{s<t} ε_lin(s)²)/σ | `:234-256`, called at `:1556-1563` |
| score | m_t(a) + β_t w_t(a) + ε_lin,t | `:1590-1597` |

With R = B_φ = 1, ‖θ_t‖ ≤ R by projection, the code envelope lies in
[c_h/(2√W), 2c_h/√W]. Its upper end is H-a's value. Realized per-run mean of
the current envelope, as a fraction of H-a's value
(`current_bias_cumulative / (2T) / (2c_h/√W)`):

| W | Policy | H-a value | Code value at θ = 0 | Mean envelope / H-a |
|---:|---|---:|---:|---|
| 16 | Hessian | 0.3849 | 0.0962 | 0.983 [0.907, 0.991] |
| 16 | endpoint | 0.3849 | 0.0962 | 0.984 [0.878, 0.991] |
| 16 | frozen | 0.3849 | 0.0962 | 0.985 [0.884, 0.991] |
| 16 | naive | 0.3849 | 0.0962 | 0.983 [0.870, 0.990] |
| 1 | Hessian | 1.5396 | 0.3849 | 0.984 [0.936, 0.991] |
| 1 | endpoint | 1.5396 | 0.3849 | 0.984 [0.879, 0.990] |
| 1 | frozen | 1.5396 | 0.3849 | 0.984 [0.917, 0.990] |
| 1 | naive | 1.5396 | 0.3849 | 0.984 [0.874, 0.990] |
| 0.25 | Hessian | 3.0792 | 0.7698 | 0.984 [0.951, 0.990] |
| 0.25 | endpoint | 3.0792 | 0.7698 | 0.985 [0.831, 0.990] |
| 0.25 | frozen | 3.0792 | 0.7698 | 0.985 [0.911, 0.990] |
| 0.25 | naive | 3.0792 | 0.7698 | 0.985 [0.817, 0.990] |

The historical envelope at round s equals the current envelope at round s, so
the same ratio describes Σ_s ε_lin(s). In the development proxy, ‖θ_t‖ reaches
the projection radius 1 by round 100 (`dev_proxy.A2` in the JSON).

**H-a: confirmed with a qualification.** The code does not use the constant
2c_μR²/√W; it uses the Taylor bound at the current norm, which reaches that
constant at ‖θ_t‖ = R. Realized envelopes are within 2% of the constant for the
median run.

## A2. β_t^corr and its three terms

**Evaluation runs, t = 1000 (bracketed, not computed exactly).** The
summaries record γ_T and Σ_{s≤T} ε_lin(s) but not γ_{T-1} or Σ_{s<T} ε_lin(s)².
Brackets: γ_{T-1} ∈ [γ_T − log(1 + G²/(λσ²)), γ_T] because s̄_T² ≤ G²/λ, and
(Σ_{s<T}ε)²/(T−1) ≤ Σ_{s<T}ε² ≤ ε_max Σ_{s<T}ε. The ridge term is √λR = 1
exactly. Brackets are medians over seeds; the last column is the outer range
over seeds.

| W | Policy | Stochastic | Ridge | Historical (median bracket) | Historical (range) |
|---:|---|---|---:|---|---|
| 16 | Hessian | 12.52–12.64 | 1 | 47.9–48.3 | 44.1–48.5 |
| 16 | endpoint | 12.51–12.62 | 1 | 47.9–48.3 | 42.7–48.5 |
| 16 | frozen | 12.51–12.62 | 1 | 47.9–48.3 | 43.0–48.5 |
| 16 | naive | 12.51–12.62 | 1 | 47.8–48.3 | 42.3–48.4 |
| 1 | Hessian | 12.49–12.61 | 1 | 191.6–193.2 | 182.1–193.8 |
| 1 | endpoint | 12.49–12.61 | 1 | 191.5–193.2 | 171.2–193.8 |
| 1 | frozen | 12.49–12.61 | 1 | 191.6–193.2 | 178.4–193.8 |
| 1 | naive | 12.49–12.61 | 1 | 191.6–193.2 | 170.1–193.8 |
| 0.25 | Hessian | 12.41–12.53 | 1 | 383.1–386.4 | 370.3–387.5 |
| 0.25 | endpoint | 12.41–12.53 | 1 | 383.3–386.5 | 323.6–387.5 |
| 0.25 | frozen | 12.42–12.53 | 1 | 383.3–386.4 | 354.7–387.5 |
| 0.25 | naive | 12.41–12.53 | 1 | 383.4–386.5 | 317.9–387.5 |

At t = 1000 the historical term is about 4, 15 and 31 times the stochastic
term at W = 16, 1, 0.25.

**t = 10, 100, 500: not run on evaluation data** (needs per-round raw logs).

**Development proxy (one run, W = 0.25, Hessian, seed 30000), exact:**

| t | β_t^corr | Stochastic | Ridge | Historical | ε_lin,t | ‖θ_t‖ |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 17.53 | 5.53 | 1 | 11.00 | 1.224 | 0.261 |
| 100 | 116.26 | 9.96 | 1 | 105.30 | 3.079 | 1.000 |
| 500 | 280.71 | 11.81 | 1 | 267.90 | 3.079 | 1.000 |
| 1000 | 396.98 | 12.53 | 1 | 383.45 | 2.962 | 0.961 |

## A3. Bonus dominance of each policy's own score on its own history

Source: `per_seed.jsonl`, rows whose behavior policy equals the score rule.
"Gap" is β_t·factor·(w₍₁₎ − w₍₂₎) > max_a m_t(a) − min_a m_t(a), with the
policy's own width and transport factor
(`tools/analyze_relative_transport.py:214-216`). "Argmax" is agreement of the
selected action with the argmax of the policy's own width
(`:204-208`). Fractions of the 1,000 rounds of each seed.

| W | Policy | Gap exceeds center range | Action = width argmax |
|---:|---|---|---|
| 16 | Hessian | 0.973 [0.929, 0.986] | 0.994 [0.988, 0.999] |
| 16 | endpoint | 0.027 [0.016, 0.040] | 0.239 [0.205, 0.263] |
| 16 | frozen | 0.028 [0.017, 0.041] | 0.229 [0.206, 0.266] |
| 16 | naive | 0.028 [0.017, 0.039] | 0.234 [0.214, 0.252] |
| 1 | Hessian | 0.994 [0.991, 0.996] | 1.000 [0.998, 1.000] |
| 1 | endpoint | 0.070 [0.052, 0.093] | 0.407 [0.364, 0.460] |
| 1 | frozen | 0.069 [0.051, 0.082] | 0.403 [0.361, 0.444] |
| 1 | naive | 0.066 [0.053, 0.089] | 0.401 [0.364, 0.443] |
| 0.25 | Hessian | 0.995 [0.993, 0.996] | 1.000 [0.997, 1.000] |
| 0.25 | endpoint | 0.168 [0.132, 0.228] | 0.636 [0.573, 0.693] |
| 0.25 | frozen | 0.167 [0.125, 0.214] | 0.669 [0.613, 0.719] |
| 0.25 | naive | 0.146 [0.112, 0.200] | 0.612 [0.564, 0.671] |

Only Hessian is width-dominated. The other three policies' actions depend on
the corrected centers on most rounds.

## A4. Zero-width optimism

**Evaluation data: not run.** It needs m_t(a), μ*_t(a), b_t and s̄_t(a) per
round; the summaries and per-seed files do not contain them.

**Development proxy (one run, W = 0.25, Hessian):** 5,000 of 5,000 recorded
state-action pairs satisfy m_t(a) + b_t ≥ μ*_t(a). The least width multiplier
max(0, (μ* − m − b)/(β s̄)) is 0 at every pair (quantiles 0.5, 0.9, 0.99 and
1.0 all 0).

**Sufficient condition (derived, not a check).** Over the 80 categories at the
configured teacher (seed 1729), max|μ*| is 0.2304, 0.2267 and 0.2156 at
W = 16, 1, 0.25 (`teacher_extremes` in the JSON). The interaction-only teacher
gives |φᵀθ°| = |xᵀv_a|/√15 ≤ 1/√15 = 0.2582 for unit simplex vertex v_a and
‖x‖ = 1; the realized maximum is 0.2307. Because b_t ≥ c_h/(2√W), zero-width
optimism holds at an action whenever m_t(a) ≥ −0.158 at W = 1 or
m_t(a) ≥ −0.554 at W = 0.25, for every θ_t in the radius-1 ball. Whether the
evaluation runs' centers met this was not checked.

## A5. Realized γ_T and the frozen-type statistical quantity

A5 := 2√((σ² + G²/λ) γ_T Σ_t (γ_{t-1} + 2log(1/δ))), with σ = 0.25,
G = λ = 1, δ = 0.05. The summaries record
`statistical_bound_component` = 2√(P Σ_t(a_t + 1)²) with P = (σ²+G²/λ)γ_T and
a_t = √(γ_{t-1} + 2log(1/δ)). With K = Σ(a_t+1)², the exact A5 lies in
[2√P(√K − √T), 2√(P(K − T(2a_min + 1)))], a_min = √(2log 20); the lower end
uses Σa_t ≤ √(TΣa_t²). Cap = 2T·min(B_φR, √W)
(`drift_and_reference_diagnostics.json`). The last column is
`statistical + historical + current_bias_cumulative` on that history; it is the
frozen policy's own bound (`prop:frozen-width-ucb`) only in the frozen rows.

| W | Policy | γ_T | A5 range over seeds | Cap | Runs with A5 lower end > cap | Frozen-form RHS (median) |
|---:|---|---|---|---:|---:|---:|
| 16 | Hessian | 153.7 [153.7, 153.7] | 9363–9989 | 2000 | 50/50 | 37787 |
| 16 | endpoint | 153.4 [153.3, 153.4] | 9340–9969 | 2000 | 50/50 | 37770 |
| 16 | frozen | 153.4 [153.3, 153.4] | 9339–9968 | 2000 | 50/50 | 37810 |
| 16 | naive | 153.4 [153.2, 153.4] | 9340–9970 | 2000 | 50/50 | 37745 |
| 1 | Hessian | 152.9 [152.8, 153.0] | 9307–9940 | 2000 | 50/50 | 121247 |
| 1 | endpoint | 152.9 [152.8, 153.0] | 9305–9936 | 2000 | 50/50 | 121134 |
| 1 | frozen | 152.9 [152.8, 153.0] | 9307–9940 | 2000 | 50/50 | 121326 |
| 1 | naive | 152.9 [152.8, 153.0] | 9307–9937 | 2000 | 50/50 | 121220 |
| 0.25 | Hessian | 151.0 [150.8, 151.2] | 9178–9823 | 1000 | 50/50 | 231140 |
| 0.25 | endpoint | 151.0 [150.8, 151.6] | 9173–9824 | 1000 | 50/50 | 231320 |
| 0.25 | frozen | 151.0 [150.9, 151.5] | 9184–9836 | 1000 | 50/50 | 231384 |
| 0.25 | naive | 151.0 [150.8, 151.7] | 9176–9831 | 1000 | 50/50 | 231339 |

The A5 term alone exceeds the cap in all 600 runs. It contains no Taylor or
nonlinearity term.

**Linear-model comparison (derived; each step checked).** Fix any recorded
context and action sequence. With ω_s = sech²(φ_sᵀθ_s/√W) ∈ (0, 1], the
linear-model frozen matrix with queries φ_s exceeds the scaled-tanh one:
V̄_t^lin − V̄_t^tanh = σ⁻²Σ_{s<t}(1 − ω_s²)φ_sφ_sᵀ ⪰ 0. Log-determinant is
monotone on the positive-definite cone, so γ^lin_{t-1} ≥ γ^tanh_{t-1} for every
t, and A5 is increasing in every γ. A linear model has ε_lin = 0 and the same
‖φ‖ ≤ 1 and cap 2T = 2000. Its frozen bound on the same sequence is therefore at
least A5^tanh > 2000. This covers the 600 recorded sequences; a linear-model
policy would select different actions, which this argument does not cover.

## A6. s_t(a)/s̄_t(a) over scored actions

Source: `per_seed.jsonl`, `effective_width_over_frozen_width.naive_current` on
each policy's own history, 5,000 scored actions per seed. Columns: per-seed
median (median [min, max] over seeds), lowest per-seed 10th percentile, highest
per-seed 90th percentile, and extreme values over all seeds.

| W | Policy | Per-seed median | min p10 | max p90 | Min | Max |
|---:|---|---|---:|---:|---:|---:|
| 16 | Hessian | 1.0000 [0.9998, 1.0000] | 0.9991 | 1.0006 | 0.9914 | 1.0211 |
| 16 | endpoint | 1.0000 [0.9998, 1.0000] | 0.9993 | 1.0006 | 0.9942 | 1.0211 |
| 16 | frozen | 1.0000 [0.9998, 1.0000] | 0.9992 | 1.0006 | 0.9938 | 1.0211 |
| 16 | naive | 1.0000 [0.9999, 1.0000] | 0.9993 | 1.0006 | 0.9939 | 1.0211 |
| 1 | Hessian | 0.9997 [0.9969, 1.0008] | 0.9876 | 1.0104 | 0.9039 | 1.3591 |
| 1 | endpoint | 1.0000 [0.9978, 1.0008] | 0.9889 | 1.0108 | 0.8906 | 1.2740 |
| 1 | frozen | 1.0000 [0.9983, 1.0011] | 0.9886 | 1.0105 | 0.9099 | 1.3513 |
| 1 | naive | 0.9997 [0.9978, 1.0010] | 0.9893 | 1.0103 | 0.8906 | 1.3513 |
| 0.25 | Hessian | 1.0045 [0.9996, 1.0079] | 0.9695 | 1.0529 | 0.7117 | 1.9942 |
| 0.25 | endpoint | 1.0049 [0.9921, 1.0088] | 0.9680 | 1.0492 | 0.7117 | 1.9942 |
| 0.25 | frozen | 1.0066 [0.9984, 1.0100] | 0.9750 | 1.0639 | 0.7250 | 2.1349 |
| 0.25 | naive | 1.0046 [0.9926, 1.0102] | 0.9715 | 1.0516 | 0.7117 | 1.9942 |

Corollary 13's uniform certificate gives s/s̄ ∈ [ℓ, 1/ℓ] with
ℓ = sech²(1/√W); at W = 16 that interval is [0.9400, 1.0638] for any history.

## Context: regret against the context-free benchmark

From the same summaries; used later to set Phase 3a hypotheses.

| W | Policy | Mean regret | Context-free mean | Runs below context-free |
|---:|---|---:|---:|---:|
| 16 | Hessian | 185.10 | 185.26 | 26/50 |
| 16 | endpoint | 152.59 | 185.26 | 50/50 |
| 16 | frozen | 151.78 | 185.26 | 50/50 |
| 16 | naive | 152.75 | 185.26 | 50/50 |
| 1 | Hessian | 182.90 | 183.06 | 30/50 |
| 1 | endpoint | 173.19 | 183.06 | 50/50 |
| 1 | frozen | 173.20 | 183.06 | 50/50 |
| 1 | naive | 173.05 | 183.06 | 50/50 |
| 0.25 | Hessian | 176.44 | 176.67 | 24/50 |
| 0.25 | endpoint | 172.09 | 176.67 | 42/50 |
| 0.25 | frozen | 171.88 | 176.67 | 41/50 |
| 0.25 | naive | 172.58 | 176.67 | 37/50 |

## Checks not run

- A2 at t = 10, 100, 500 and A4 on evaluation runs: raw logs absent.
- A3 and A6 were not recomputed from raw logs; they come from the committed
  per-seed counts and summaries of an earlier analysis
  (`tools/analyze_relative_transport.py`), checked here only for byte
  integrity.
- No test suite was run for this phase; the commit adds two files and edits
  none.
