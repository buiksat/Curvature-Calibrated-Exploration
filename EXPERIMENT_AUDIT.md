# Experiment Audit

Audit date: 2026-07-21

## Scope

This audit covers the versioned protocols in `experiments/configs/`, all
drivers and aggregation scripts in `experiments/`, the raw trees under
`results/raw/`, the derived artifacts under `results/derived/`, the paper table
and figure generators, and both test trees.  The baseline observations below
are retained as a historical checkpoint; the later sections include the
operational-certificate and new-experiment results completed on July 20--21.

Before the revision, the baseline suite passed (`96 passed`) and the 36-page PDF
built from a clean LaTeX state.  That baseline did not close the new acceptance
gates.  Final post-revision test, proof, manuscript, and release validation is
tracked separately and must not be inferred from the baseline run.

## Algorithm-to-code map

The paper's Algorithm 1 is a generic policy specification rather than one
callable.  Algorithm 2 expands its filtration and update order.  Their executed
specializations are distributed as follows.

| Paper component | Implementation |
|---|---|
| O(d)-state predictable certificates | `experiments/path_certificates.py`; formula, direct-history, and filtration tests in `tests/test_path_certificates.py` |
| Bounded nonlinear tanh execution | `experiments/run_certified_tanh.py`; `experiments/configs/certified_tanh.yaml` |
| Bounded linear CC-UCB specialization | `experiments/run_linear_audit.py:706` (`run_method`) and `experiments/run_linear_study.py:211` |
| Predetermined nonlinear full-curvature policy | `experiments/run_nonlinear_audit.py:626` and `:986` |
| Dense full Gram / exact full curvature | `CurvatureStrategy.build` in `run_linear_audit.py`; dense audit matrices in `run_nonlinear_audit.py`; full builders in both operator-ablation drivers |
| Full GGN-CG widths | `experiments/curvature_operators.py:395`; nonlinear calls through `theory_metrics.cg_width`; Covertype through `run_covertype.py:_policy_widths` |
| Diagonal curvature | `run_linear_audit.py:CurvatureStrategy`; `run_operator_ablation.py`; `nonlinear_operator_ablation.py`; `run_covertype.py` |
| Unrescaled window | `run_linear_audit.py:CurvatureStrategy`; both operator-ablation builders |
| Rescaled fixed-size subsample | `run_linear_audit.py:CurvatureStrategy`; both operator-ablation builders |
| Lanczos/Ritz low rank | `_lanczos_surrogate` in `run_linear_audit.py` and `nonlinear_operator_ablation.py`; `lanczos_ritz` in `run_systems_scaling.py` |
| Stale/periodic refresh | `run_linear_audit.py:CurvatureStrategy`; both operator-ablation builders |
| Nonlinear drift ladder and original/corrected centers | `experiments/run_nonlinear_audit.py`; `experiments/configs/nonlinear_drift.yaml` |
| Linear/nonlinear online operator comparison | `run_operator_ablation.py` and `nonlinear_operator_ablation.py` |
| Common-trajectory diagnostics | `run_operator_ablation.py:763-1156` and `nonlinear_operator_ablation.py:923-1140` |
| Covertype executed policies | `experiments/run_covertype.py`; `experiments/configs/covertype_rerun.yaml` |
| Balanced contextual benchmark and local neural baselines | `experiments/run_balanced_benchmark.py`; `experiments/configs/balanced_benchmark.yaml` |
| Preregistered curvature-mechanism phase map | `experiments/curvature_phase_diagram.py`; `experiments/configs/curvature_phase_diagram.yaml` |
| Fixed-SPD and executed-policy CG audits | `experiments/run_cg_accuracy.py` |
| Determinant, width-sum, transfer, and CG theorem checks | `experiments/theory_metrics.py` plus linear/nonlinear drivers |
| Batched/Jacobi-CG CPU systems microbenchmark | `experiments/run_systems_scaling.py`; `experiments/configs/systems_scaling.yaml` |
| Strict aggregation and paired intervals | `experiments/aggregate_results.py`, `aggregate_cg_policy.py` |
| Revision figure and executed-policy table | `experiments/make_revision_paper_artifacts.py`; sources are validated before output and each output has a SHA-256 provenance sidecar |
| Other paper artifacts | `make_primary_table.py`, `make_paper_artifacts.py`, `make_linear_bound_artifact.py`, and `make_covertype_horizon_artifact.py` |

The nonlinear driver performs full replay at the current parameter and computes
dense exact matrices for audit quantities.  Its action rule uses only the
predetermined time schedules, CG widths, and selected center; teacher-dependent
values are written under `posthoc_*` keys and are not fed back to the policy.

## Protocols and seed partitions

All configured tuning and evaluation sets are disjoint, as enforced by
`tests/test_experiment_pipeline.py`.

| Protocol | Full evaluation seeds | Main status |
|---|---:|---|
| Linear audit | 100--119 (20) | Executed policies; fixed and validation-tuned configurations |
| Nonlinear drift | 110--129 (20) | Executed policies with post-hoc theorem diagnostics |
| Operator ablation | 120--139 (20) | Independent online policies plus separately tagged offline diagnostics |
| CG accuracy/policy | 130--139 (10) | Fixed-SPD diagnostics and executed linear policies |
| Systems scaling | 140--144 (5) | CPU-only synthetic diagnostic benchmark |
| Covertype | 150--159 (10) | Independently evaluated executed policies after tuning on 50--59 |
| Certified tanh | 160--209 (50) | Two fixed-schedule centers; predictable schedules with post-hoc theorem-event verification |
| Certified tanh controlled grid | 60--69 (10 tuning only) | Eight one-factor cells x two centers; descriptive tuning study, not an evaluation estimate |
| Curvature phase diagram | 200--229 (30) | Preregistered eight-cell evaluation; independent online policies plus offline common-trajectory diagnostics |
| Balanced contextual benchmark | 260--289 (30) | Selected only on tuning seeds 70--79; 11 independently rerun policies |

The certified-tanh and balanced partitions do not overlap.  The phase diagram is
a separate bounded-linear mechanism study and shares no raw trajectory with the
balanced benchmark.  Every new aggregate records its declared seed set and
input hashes.

## Raw and derived inventory

| Raw tree | Run directories | Approx. size | Interpretation |
|---|---:|---:|---|
| `linear_audit` | 700 | 1.5 GiB | tuning candidates plus 280 final evaluation runs |
| `nonlinear_drift` | 160 | 104 MiB | 4 regimes x 2 centers x 20 evaluation seeds |
| `operator_ablation` | 894 | 1.1 GiB | online linear/nonlinear runs and common-trajectory diagnostics |
| `cg_accuracy` | 10 | 1.1 GiB | fixed-SPD solver diagnostics |
| `cg_policy_accuracy` | 10 containers | 165 MiB | 200 policy cells encoded within seed outputs |
| `covertype_rerun` | 370 | 206 MiB | earlier T=200 protocol |
| `covertype_rerun_1500` | 410 | 500 MiB | tuning plus 80 selected evaluation runs |
| `certified_tanh` | fixed evaluation plus controlled tuning grid | 177 MiB | 100 fixed evaluation policies and 160 tuning-grid policies |
| `balanced_benchmark` | tuning candidates plus 330 selected evaluation policies | 234 MiB | 11 validation-tuned methods x 30 evaluation seeds |
| `curvature_phase_diagram` | 30 seed containers | 298 MiB | 1,680 online and 1,680 common-trajectory method/cell records |
| `systems_scaling` | 5 | 4.7 MiB | 384 synthetic CPU benchmark groups, including dimensions 512--8192 |
| `smoke` | 38 | 9.9 MiB | wiring checks; not reportable |

Strict full aggregates include 280 linear runs, 160 nonlinear-drift runs, 220
linear operator runs, 220 nonlinear operator runs, and 80 long-horizon
Covertype runs.  Their sidecars bind the aggregate, raw manifests, raw records,
and summaries by SHA-256.  The revision figure is generated from the certified-
tanh and phase-diagram reports, and the revision table is generated from the
certified-tanh and balanced-benchmark reports.  The bound-ratio and Covertype
appendix tables each retain a dedicated derived artifact.

The internal Covertype class-count provenance contains absolute local paths.
That is acceptable only in the internal tree; the anonymous release builder must
rewrite them and regenerate all hashes.

The four new report sidecars currently validate against 103 tanh inputs, 2,732
balanced-benchmark inputs, nine phase-diagram inputs, and 15 systems inputs,
respectively.  The compact revision figure reads only the tanh and phase
reports; the revision table reads only the tanh and balanced reports.  Their
sidecars bind the exact derived JSON and source-provenance files used.

## Certification and diagnostic status

The authoritative primary-policy ledger is
`results/derived/certification_audit.json`.

- `dense_full`, `unrescaled_window`, and `stale_refresh` are classified
  `ex_ante_theorem_certified` in the bounded linear setting.  Linear features do
  not drift, and these operators have analytic one-sided transfer factor one.
- `cg_full`, `diagonal`, `rescaled_subsample`, and `lanczos_ritz` are classified
  `posthoc_theorem_event_verified`.  Their floating-point condition numbers or
  generalized eigenvalues are point estimates, not verified upper enclosures.
- The nonlinear-drift runs are executed online policies but their exact
  `chi`, `psi`, `F`, transfer, and teacher quantities are post-hoc audits.  Their
  predetermined schedules fail in some regimes, so they are not certified.
- The common-trajectory operator records are offline diagnostics and contain no
  online regret outcome.
- Raw CG summaries that use the word `certified` are not sufficient evidence of
  a rigorous condition-number enclosure.  The newer certification ledger and
  manuscript qualification supersede those raw labels.
- Covertype policies use binary rewards with Gaussian squared-loss curvature;
  Theorem 1 does not certify them.
- The new tanh policies compute every mathematical schedule before action
  selection and all 100 evaluation trajectories satisfy the checked theorem
  events.  Because float64 residual and matrix checks are point computations,
  both centers are classified `posthoc_theorem_event_verified`, not verified-
  enclosure ex-ante certified.
- All 11 balanced-benchmark rows are executed but `uncertified_diagnostic` in
  substance.  The CC-UCB row checks original-system CG residuals, but does not
  certify an energy-error enclosure.  NeuralUCB and NeuralTS are explicitly
  local linearized implementations, not claimed reproductions of all details of
  the published algorithms.
- Phase-diagram online rows are independent executed policies; the companion
  common-trajectory rows are offline diagnostics with no causal regret claim.
  The systems rows are synthetic feasibility diagnostics, not policies.

## Reproducibility classification

### Fully reproducible from present local inputs

- Linear audit, nonlinear drift, operator ablations, CG audits, and systems
  microbenchmarks have code, resolved configs, seeds, raw records, summaries,
  strict aggregates, and regeneration scripts.
- Certified tanh, the balanced contextual benchmark, and the curvature phase
  diagram have code, resolved configs, seed-level outputs, derived reports, and
  validating sidecars.  Their fixed evaluation sets contain 50, 30, and 30
  seeds, respectively.
- Paper Figure 1, Table 1, the linear bound-ratio table, and all currently
  generated appendix tables have provenance sidecars and present source inputs.
- The local Covertype rerun is reproducible from the validated local cache and
  stored split indices.

### Reproducible only with an external data dependency when the cache is absent

- Covertype requires the UCI Covertype data fetched through scikit-learn.  The
  repository records dataset and file checksums, split seed 20260717, and the
  train/validation/test indices.  Tests do not download data silently.

### Unrecovered legacy evidence

- The 18 legacy oracle-selected point estimates and 11 intervals have no
  complete surviving raw records or exact executable reconstruction.  They are
  retrospective, oracle-selected, interpolated, selection-unadjusted, noncausal,
  and incomplete.  They cannot support new executed-policy claims.

## Current empirical conclusions

- The bounded linear audit reproduces the determinant, transfer, CG, width-sum,
  and realized regret checks, but its theorem bounds are hundreds to thousands
  of times realized regret and are numerically vacuous.
- The original nonlinear stress test demonstrates failures of its fixed
  schedules and remains uncertified; it is distinct from the new bounded tanh
  predictable-schedule execution.
- Full curvature is a reference operator and is not uniformly best in regret.
- The certified tanh fixed schedule has zero observed certificate, confidence,
  and optimism failures for both centers across 50 evaluation seeds.  Mean
  regret is 7.86 for the original center and 5.69 for the corrected center, but
  the mean observable RHS/regret ratios are 6,956.7 and 1,328.9.  These are
  predictable-schedule executions with post-hoc event verification, and the
  bounds remain numerically vacuous.
- The balanced synthetic benchmark passes its preregistered noncontextual sanity
  check: LinUCB minus UCB1 has mean paired regret difference -79.77 with 95%
  interval [-82.25, -77.30], and LinUCB minus context-free Gaussian Thompson
  sampling is -78.82 [-81.63, -76.01].  CC-UCB full GGN-CG has mean regret
  21.94; diagonal full-network UCB has 16.11, NeuralLinear 10.01, LinUCB 10.58,
  and frozen last-layer UCB 7.44.  This supports a contextual sanity check, not
  uniform full-curvature superiority.
- In the eight-cell fixed-representation phase diagram, diagonal has lower
  regret than exact full in all eight paired cells; block diagonal is lower in
  six and unresolved in two.  Exact full is lower than window and stale refresh
  in all eight cells and lower than low-rank Lanczos in seven, with one
  unresolved.  Full-CG has zero paired regret difference in all cells, and its
  common-trajectory top-action disagreement with exact full is zero.  No
  evaluation cell was selected post hoc.
- Covertype fails the basic contextual sanity check.  At T=1500, UCB1 reaches
  0.403 accuracy and Beta--Bernoulli Thompson sampling 0.465, while the best
  contextual row reaches 0.223.  The fixed test-split majority oracle is 0.4883.
- Systems results now cover float64 synthetic parameter-vector operators from
  dimension 32 through 8192, including batched independent CG and Jacobi-
  preconditioned batched CG, on five evaluation seeds.  All recorded width-
  sandwich checks pass.  They are CPU diagnostics, not a neural-model or
  accelerator deployment, and substantiate no large-model feasibility claim.

## Remaining unrun or blocked work

- No Wheel, Mushroom, or balanced real-data benchmark has been run.  The new
  sanity-check-passing benchmark is synthetic.
- NeuralLinear, NeuralUCB, and NeuralTS are local matched implementations; no
  external implementation equivalence study has been performed.  NN-UCB,
  NN-TS, EKF, LMC-TS, KFAC, and block-Laplace comparisons remain unrun.
- The phase diagram fixes representation drift to zero.  The requested drift
  axis and matched-wall-clock policy reruns remain unrun.
- Batched independent and Jacobi-preconditioned CG are measured, but no KFAC or
  block preconditioner, accelerator backend, or actual 10^5--10^7-parameter
  model benchmark is available.
- Verified interval or directed-rounding numerical enclosures have not been
  implemented.  The nonlinear schedules are mathematically predictable, while
  their observed floating-point validity remains a post-hoc event statement.
- Final independent proof review, complete test/build validation, anonymous
  release regeneration, and identity/hash scans remain release tasks.  No
  unrun result may be inferred from the completed diagnostic artifacts.
