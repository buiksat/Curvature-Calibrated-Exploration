# Results Status

Status date: 2026-07-22

## Revision progress after the baseline audit

The new `certified_tanh` fixed protocol has now been executed for 50 independent
evaluation seeds and both original and corrected centers (100 policies, 10,000
round records). All schedules were computed from pre-action quantities, and all
observed transfer, centering, linearization, information, CG, confidence, and
regret events passed. The actual float64 rows remain conservatively classified
`posthoc_theorem_event_verified`, because their residual calculations are not
verified interval enclosures.

Derived artifacts in the compact checkout:

- `results/derived/certified_tanh_full.json`
- `results/derived/certified_tanh_report.json`

The historical raw tanh tree is stored outside the compact Git checkout; it
must be restored before rebuilding its full provenance chain.

At T=100, mean pseudo-regret is 7.86 (original) and 5.69 (corrected). The
observable theorem RHS remains highly vacuous: mean RHS/regret is 6,956.7 and
1,328.9, respectively. The eight-cell one-factor controlled design was also
executed for both centers on the 10 tuning seeds only; all 160 runs passed the
observed theorem-event checks and are reported descriptively, not as evaluation
estimates.

The preregistered balanced contextual benchmark, bounded-linear curvature phase
diagram, and expanded synthetic CPU systems study are also complete.  Each
derived report and provenance sidecar validates against its current source
inventory.

## Closed-rate theorem-scaling grid

The separate full-grid artifact
`results/derived/theory_scaling_full_grid.json` validates all 3,600 expected
maximum-horizon trajectories: three ambient dimensions, three active ranks,
eight methods, and 50 fixed evaluation seeds. Its SHA-256 is
`69c3d8cc7d6f2c588963b2af8b1be9a04351e1c394f2b8c84855287800b86d9d`.
The original 400-run `d=128`, `r=4` primary slice was preserved and revalidated
without replacement.

At `d=2048`, exact-current mean regret at `T=2048` is 1.80 [1.57, 2.07],
7.50 [6.82, 8.17], and 43.95 [42.24, 45.59] for ranks 4, 8, and 16. The
corresponding finite-horizon regret slopes are 0.000, 0.134 [0.115, 0.153], and
0.818 [0.804, 0.831]; exact dynamic-width slopes are 0.106, 0.099, and 0.117.
These fits are diagnostics, not asymptotic-rate proofs. The rank-16 executions
also have optimizer/path audit failures, so they are not theorem-event verified.
Greedy has lower regret in these cells but is an uncertified control.

The actual-autodiff benchmark was not run. Although the host exposes a declared
PyTorch alias, Buck configuration reaches
`fbsource//third-party/python/3.12:python-for-embedding` and fails in
`feature_rollout_utils.bzl` with `Starlark call stack overflow`. The hashed
current-host `not_run` record has no fabricated timing.

## New balanced contextual benchmark

The balanced benchmark uses a normalized-Rademacher context stream, five
actions, a fixed width-four tanh teacher, common context/noise streams within a
seed, and one matched full-network update per round where applicable.  The
ridge/bonus grid was selected by mean pseudo-regret on tuning seeds 70--79; all
11 selected methods were rerun from scratch on evaluation seeds 260--289.

At T=200, mean cumulative pseudo-regret and 95% intervals are:

| Method | Mean [95% CI] | Mean measured run time (s) |
|---|---:|---:|
| CC-UCB full GGN-CG | 21.94 [20.64, 23.23] | 0.966 |
| Diagonal full network | 16.11 [14.62, 17.61] | 0.024 |
| LinUCB | 10.58 [9.82, 11.33] | 0.015 |
| Linear Thompson sampling | 12.67 [12.02, 13.31] | 0.017 |
| NeuralLinear | 10.01 [9.33, 10.68] | 0.014 |
| NeuralUCB | 23.04 [21.81, 24.27] | 0.027 |
| NeuralTS | 25.07 [23.40, 26.75] | 0.032 |
| Frozen last-layer UCB | 7.44 [6.90, 7.99] | 0.012 |
| Greedy full network | 16.26 [14.44, 18.09] | 0.017 |
| Gaussian UCB1 | 90.35 [87.95, 92.75] | 0.003 |
| Context-free Gaussian Thompson sampling | 89.40 [86.53, 92.26] | 0.004 |

The preregistered LinUCB sanity check passes against both context-free policies.
Its paired regret difference is -79.77 [-82.25, -77.30] versus UCB1 and -78.82
[-81.63, -76.01] versus context-free Thompson sampling.  All rows are executed
but uncertified.  NeuralUCB and NeuralTS are local linearized implementations;
the artifact makes no claim that they reproduce every published training
detail.  The frozen representation is favorable on this synthetic teacher and
must not be generalized to unrelated data.

## Curvature-mechanism phase diagram

`results/derived/curvature_phase_diagram_report.json` contains the preregistered
eight-cell, 30-evaluation-seed bounded-linear study: 1,680 independent online
method/cell/seed records, 1,680 separately tagged common-trajectory diagnostic
records, and 48 paired comparisons against exact full curvature.  No cell was
selected based on its evaluation result and representation drift was fixed at
zero.

Diagonal has lower regret than exact full in all eight cells; block diagonal is
lower in six and unresolved in two.  Exact full is lower than window and stale
refresh in all eight cells and lower than low-rank Lanczos in seven, with one
unresolved.  Full-CG has zero paired regret difference in all eight cells, and
its common-trajectory top-action disagreement with exact full is zero.  Thus
the study resolves regions where curvature surrogates help or hurt, but
provides no uniform ordering and no evidence about nonzero representation
drift.

## Expanded systems diagnostics

`results/derived/systems_scaling_full.json` contains 384 complete synthetic CPU
benchmark groups over five evaluation seeds, dimensions 32--8192, action counts
4/5/10, and sample counts 32/128/512.  It includes batched independent CG and
Jacobi-preconditioned batched CG in addition to the earlier dense, scalar-CG,
diagonal, block, and Lanczos diagnostics.  All recorded width-sandwich checks
hold.  These are float64 parameter-vector/operator diagnostics with no
accelerator and no executed neural model; they do not support a foundation-
model or large-model feasibility claim.

## Completed and reproducible

| Result family | Artifact | Status |
|---|---|---|
| Bounded linear executed-policy audit | `results/derived/linear_audit_full.json` | 280 evaluation runs; complete raw/manifests/summaries |
| Primary linear certification ledger | `results/derived/certification_audit.json` | Current authoritative classification for 14 policy/configuration rows |
| Linear bound scale | `results/derived/linear_bound_metrics.json` | T=250, 500, 1000; all bounds numerically vacuous |
| Nonlinear drift stress test | `results/derived/nonlinear_drift_full.json` | 160 executed policies; theorem quantities are post-hoc |
| Predictable-schedule tanh execution | `results/derived/certified_tanh_report.json` | 2 centers x 50 evaluation seeds; zero observed checked-event failures; floating-point category is post-hoc event verified |
| Tanh controlled grid | `results/derived/certified_tanh_controlled_grid.json` | 8 cells x 2 centers x 10 tuning seeds; descriptive tuning results only |
| Linear operator audit | `results/derived/operator_ablation_full.json` | 220 online runs plus separately validated common-trajectory diagnostics |
| Nonlinear operator audit | `results/derived/operator_ablation_nonlinear_full.json` | 220 online runs plus separately validated diagnostics |
| Curvature phase diagram | `results/derived/curvature_phase_diagram_report.json` | 8 preregistered cells x 7 methods x 30 seeds online, plus separately tagged common-trajectory diagnostics |
| Balanced contextual benchmark | `results/derived/balanced_benchmark_full.json` | 11 validation-tuned methods x 30 evaluation seeds; sanity check passes |
| Fixed-SPD CG audit | `results/derived/cg_accuracy_full.json` | 10 seeds, 60 diagnostic groups |
| Executed CG policy audit | `results/derived/cg_policy_accuracy_full.json` | 10 seeds, 200 policy cells; numerical condition factors are not verified enclosures |
| Covertype long-horizon rerun | `results/derived/covertype_rerun_1500_full_aggregate.json` | 8 methods x 10 evaluation seeds x four horizons |
| Covertype class imbalance | `results/derived/covertype_test_class_counts.json` | Exact fixed test-split counts and majority oracle |
| CPU systems audit | `results/derived/systems_scaling_full.json` | 5 seeds, 384 synthetic groups through dimension 8192; no model or accelerator claim |
| Theorem-scaling full grid | `results/derived/theory_scaling_full_grid.json` | 9 cells x 8 methods x 50 evaluation seeds; 3,600/3,600 raw trajectories and hashes validated |
| Revision paper artifacts | `paper/figures/theory_factor_drift.pdf`, `paper/tables/executed_policy_results.tex` | Generated only after validating tanh, balanced, phase, and systems reports; output sidecars bind direct inputs |

The primary figure and generated tables are reproducible from these artifacts.
Final validation passed: 241 tests, a clean 42-page LaTeX build, zero
content-generated overfull boxes, zero Type 3 fonts, and anonymous PDF metadata.

## Failed or negative experiments

- The predetermined nonlinear confidence, transfer, and centering schedules do
  not hold uniformly.  These runs remain useful stress tests but are not
  certified nonlinear policies.
- Covertype fails its baseline prerequisite.  Context-free UCB1 and
  Beta--Bernoulli Thompson sampling beat every contextual method at all reported
  horizons.  It is not positive evidence about curvature fidelity.
- The finite-horizon linear theorem RHS is numerically vacuous.  At T=1000 the
  fixed-reference RHS/regret ratios range from 260.2 (window 64) to 13,456.0
  (diagonal).
- The operational tanh schedules pass every observed check, but their theorem
  RHS is also vacuous: mean RHS/regret is 6,956.7 for the original center and
  1,328.9 for the corrected center.
- Full GGN-CG is not the best balanced-benchmark method.  Its mean regret 21.94
  exceeds diagonal full-network UCB (16.11), LinUCB (10.58), NeuralLinear
  (10.01), and frozen last-layer UCB (7.44).
- The phase diagram rejects a uniform curvature ranking: diagonal beats exact
  full in all eight cells, while exact full beats window and stale refresh in
  all eight.  These comparisons are descriptive paired intervals on a
  preregistered bounded-linear grid.

## External-data dependent

- Covertype is locally cached and hash-validated, but a fresh machine needs the
  UCI dataset.  The download is explicit, not part of tests.
- No Wheel, Mushroom, or balanced real-data pipeline is present.  The new
  sanity-check-passing balanced benchmark is synthetic and needs no download.

## Missing legacy records

The complete raw data and exact policy-construction code for the legacy
oracle-selected matched-coverage study were not recovered.  Its 18 point
estimates and 11 intervals must not be regenerated, altered, or used as support
for new conclusions.

## Not run or not established

- Wheel, Mushroom, or another standard external contextual benchmark that
  passes the two context-free baselines.
- Validation against external published implementations of NeuralLinear,
  NeuralUCB, or NeuralTS.  NN-UCB/NN-TS, EKF, LMC-TS, KFAC, and block-Laplace
  comparisons are also unrun.
- A matched-wall-clock policy-budget rerun; the balanced study matches update
  budgets and reports runtime, but does not retune each policy under an equal
  wall-clock budget.
- Nonzero representation-drift cells in the curvature phase diagram.
- KFAC or block preconditioning for the full target system, verified interval
  enclosures for numerical certificates, and an actual-autodiff
  131,841-parameter systems benchmark. The latter is blocked by the declared
  Buck PyTorch dependency and has a deterministic `not_run` record.

## Resource constraints

The current host has 22 logical Intel Xeon Platinum 8339HC CPUs, 176 GiB of OS
memory, and one detected NVIDIA PG509-210 with 81,920 MiB. Scaling used CPU
only. The repository's declared Buck PyTorch target does not configure in this
standalone cell, so no CPU or GPU actual-autodiff timing was executed and no
result may be inferred from operation counts.

## Acceptance gates

| Gate | Current evidence and qualification |
|---|---|
| 1. Computable schedules | **Satisfied.** `PathCertificateState` supplies `beta_bar_t`, `psi_bar_t`, and `u_t` from pre-action state, with direct-history and filtration tests. |
| 2. Nonlinear predictable execution | **Satisfied in the required observed-event sense.** Both tanh centers have zero observed failures across 50 evaluation seeds.  Float64 point checks remain `posthoc_theorem_event_verified`, not verified-enclosure ex-ante certificates. |
| 3. Explicit nonlinear rate or conditional reframing | **Satisfied conditionally.** Corollary 9 is framed as fixed-subspace adaptation and exposes its bounded-path, width, residual, and optimizer premises; it is not an end-to-end neural-training theorem. |
| 4. Contextual sanity benchmark | **Satisfied narrowly by the balanced synthetic benchmark.** LinUCB beats both context-free baselines on 30 untouched seeds.  No external real-data benchmark passes this test. |
| 5. NeuralLinear plus a full neural baseline | **Satisfied by local matched implementations.** NeuralLinear, NeuralUCB, and NeuralTS are included, but are not claimed exact reproductions of published code. |
| 6. Scalability claims | **Restricted, not empirically established.** The manuscript limits evidence to synthetic CPU resource accounting and states that the defining autodiff JVP/VJP benchmark was not run. |
| 7. Legacy evidence | **Satisfied in the current manuscript.** The unrecovered oracle-selected study is absent from the evidentiary chain. |

The historical anonymous bundles and hashes recorded in `CODEX_REPORT.md`
predate the closed-rate/scaling revision and are not current release artifacts.
No final `release/` or `release_review/` directory is present in this checkout.
Restore every provenance-bound raw input, rebuild both tiers from the final
reviewed commit, and rerun identity/hash scans before making a release claim.
No external passing benchmark, verified floating-point enclosure, actual-autodiff
timing, or accelerator/large-model result is claimed.
