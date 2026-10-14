# Prespecified nonlinear-regime follow-up

Protocol ID: `transport-review-followup-v1.1`. Configuration:
`experiments/configs/transport_review_followup.yaml` (JSON syntax).
This is a new study. The original configuration, implementation, selected
optimizer, aggregate and paper artifacts remain locked and unchanged.

## Question and scope

Does the four-policy comparison change when the same controlled scaled-tanh
family is evaluated at appreciably smaller near-linearity scales? In each
condition compare `transport_hessian`, `transport_endpoint`, `frozen_reference`
and `naive_current` using the unchanged exact-dense implementation, corrected
center and noise model. Record actual endpoint metric motion, validity,
confidence/optimism, pseudo-regret and bound accounting. A high target label
does not establish that realized drift is large, nor does a large certificate
establish that it is necessary.

This study does not test approximate operators, iterative solvers,
misspecification or authentic external data. Those are distinct follow-ups,
not prerequisites for assessing this four-policy controlled comparison.

## Fixed conditions

For the original constants (`R=1`, `sigma=0.25`, `lambda=1`,
`c_h=4/(3 sqrt(3))`), prescribe **W = 16, 1, 0.25**. Encode each W through the
existing implementation's rule without changing that implementation:

```
target_D(T, W) = 4 c_h R sqrt(T - 1) / (sigma sqrt(lambda W))
W(T, target_D) = (4 c_h R sqrt(T - 1) / (sigma sqrt(lambda) target_D))^2
```

| Profile | Horizon | W | Encoded target_D |
|---|---:|---:|---:|
| smoke (pilot) | 64 | 16 | 24.440403706431148 |
| smoke (pilot) | 64 | 1 | 97.76161482572459 |
| smoke (pilot) | 64 | 0.25 | 195.52322965144918 |
| full | 1000 | 16 | 97.32420048477151 |
| full | 1000 | 1 | 389.29680193908604 |
| full | 1000 | 0.25 | 778.5936038781721 |

Each profile has one horizon, so the runner's Cartesian product realizes
exactly these pairs. The encoded target is allowed to change between horizons;
W is the condition matched across profiles. For comparison, arbitrary target
labels 8 and 32 at T=1000 imply W approximately 2368 and 148, respectively,
which need not create a materially nonlinear model.

W changes the reward function as well as tangent geometry and the available
certificate. Consequently comparisons **across W** are descriptive changes of
task, not a causal effect of transport inflation. Policy comparisons **within
W and horizon** share context and potential-noise streams but use separate
adaptive histories. Neither comparable upper bounds nor within-study means
establish uniform policy dominance.

## Seeds, tuning and selection

| Profile | Development seeds | Tuning seeds | Evaluation seeds |
|---|---|---|---|
| smoke | 20000–20001 | 20100–20101 | 20200–20201 |
| full | 30000–30001 | 30100–30109 | 30200–30249 |

All partitions are disjoint from each other and from the locked study's seeds.
The teacher remains the declared fixed seed 1729. Method-independent stream
derivation preserves pairing within each cell. Reusing one evaluation seed
across W conditions does not make those conditions independent observations.

Retain the original nine optimizer candidates: learning rates
`[0.00003, 0.0001, 0.0003]` crossed with steps `[1, 5, 20]`. Tune on uniform-random
behavior trajectories, select by equal-weight mean of per-seed, per-condition
all-action prediction MSE after burn-in (16 rounds for smoke, 100 for full),
reject candidates with deterministic failures, then break ties by fewer steps
and smaller learning rate. One selected candidate is shared across all four
methods and W conditions in that profile. Full selection is independent of
smoke selection. Development alone uses the declared learning rate 0.0003 and
20 steps; that choice is not the result of follow-up evaluation.

The smoke pipeline has 54 tuning and 24 evaluation trajectories. The full
pipeline has 270 tuning and 600 evaluation trajectories (150 primary-policy
trajectories), excluding optional development runs. Smoke results establish
feasibility only and must not be reported as full-study evidence.

## Pilot and numerical failure rules

Before tuning, the launcher must pass the entire declared development grid;
then complete smoke tuning and evaluation before the full study. In development,
the existing code compares quadrature orders 1024 and 2048. Recorded float64
algebra and quadrature checks remain diagnostics, not verified numerical
enclosures. Keep all declared numerical tolerances. The refinement and independent
higher-order comparison are recorded below; passing a single development case
does not clear the entire grid.

The full small-W condition can make exponential bounds enormous. An overflow,
nonfinite output, failed deterministic check or incomplete Cartesian grid is
an explicit failed/incomplete result. Do not clip exponents, silently lower a
certificate, discard affected seeds, relax a tolerance, or call a partially
completed grid publication-ready. If such a failure prevents execution,
record it and introduce any mathematical/numerical remedy in a separately
versioned protocol before new evaluation. Retain failures of the stochastic
confidence or optimism event as scientific outcomes.

Report realized endpoint Thompson distance and Hessian/Q certificate by cell:
the distribution of per-run maxima, plus proportions of rounds with endpoint
distance at least `0.01`, `0.1`, and `1.0`. These thresholds are descriptive,
fixed here, and never select seeds or conditions. Report all three W conditions
even if none crosses a threshold. Do not label a condition strong-drift merely
because its target_D is large.

## Required analysis

1. Per-cell simultaneous reference confidence and method optimism, with exact
   95% Clopper–Pearson intervals over the 50 full evaluation seeds. Separately
   count deterministic failures and premise-false trajectories. Do not pool
   the reused seeds into a claim of 150 independent primary-policy trials.
2. Mean pseudo-regret and paired differences against transport Hessian within
   each condition, using the existing deterministic 10,000-resample, 95%
   paired bootstrap. Intervals are comparisonwise, not simultaneous.
3. Actual endpoint drift, analytic envelope, quadrature path diagnostics and
   confidence-width inflation, with the population and denominator exclusions
   explicit for every ratio.
4. Terminal bound decomposition for every method, including base confidence,
   historical linearization, explicit path inflation and current bias.
   For `frozen_reference`, its own-trajectory frozen-policy RHS equals
   `statistical_bound_component + historical_bound_component +
   current_bias_cumulative`. Compare that quantity with its own regret and
   the deterministic cap `2 T min(G R, sqrt(W))`; with the declared `G=R=1`
   this equals `2T` for W=16 or 1 and `T` for W=0.25. The same arithmetic with the path term removed from
   a transport trajectory is an accounting diagnostic, not a regret guarantee
   for that trajectory or an estimate of the frozen policy's outcome.
5. Paired policy outcomes are not a causal decomposition of path conservatism:
   histories, fitted parameters, corrected centers and widths can all diverge.
   A result in either direction must be scoped to this family, configuration
   and horizon. Comparable worst-case upper bounds do not order actual regret.

## Pre-evaluation numerical amendment

The initial configuration used the locked study's 16/32-point convergence
check. On development seed 20000, T=64 and W=0.25, it recorded 61 convergence
failures (maximum order difference 0.00154316), although the other deterministic
checks passed. The same trajectory had maximum endpoint distance 0.948485;
its stronger nonlinear geometry makes the coarse quadrature unsuitable.

Refinement on that **same development seed**, without changing any tolerance,
policy, condition, seed partition or tuning rule, gave:

| Compared orders | Convergence failures | Maximum difference |
|---|---:|---:|
| 16 / 32 | 61 | 0.00154316 |
| 128 / 256 | 52 | 0.0000229630 |
| 1024 / 2048 | 0 | 0.000000188012 |
| 2048 / 4096, independent higher-order check | 0 | 0.0000000983656 |

The original scaled absolute/relative tolerance is used per checkpoint; the
maximum difference alone is not its pass criterion. The recorded actions,
scores, rewards, parameter norms, regret, endpoint drift and confidence/optimism
outcomes are byte-identical across these four diagnostic refinements. Freeze
order **2048** for this follow-up, with 1024/2048 comparison in development.

A separate declared full-profile development case (seed 30000, T=1000,
W=0.25) also passed all checks at the 100 declared checkpoints, with maximum
1024/2048 difference 0.000000201637, maximum endpoint distance 0.935413 and
maximum Hessian/Q envelope 143.205. It completed without overflow in 46.21
seconds on the onboarding host. These are feasibility observations, not
evaluation evidence or a guarantee for other seeds/methods.

High-order NumPy `leggauss` node construction is expensive. The launcher
memoizes its unchanged node/weight arrays per worker and makes them read-only;
this changes neither the quadrature rule nor the node bytes. One uncached
4096 attempt was interrupted inside node generation after more than five
minutes and replaced by the cached run; it is not reported as a completed
check. Cache settings are recorded in the execution manifest and tested.

`review/transport_review_followup/QUADRATURE_REFINEMENT.json` records all actual
statuses and hashes. Its accompanying 1.7 MB archive preserves the raw logs,
manifests and summaries for both failed refinements and all three completed
checks. The exact initial config is retained as `initial_followup_config.json`.
The archive carries runtime metadata and is an internal reproducibility record,
not an anonymous submission attachment. No tuning or evaluation outcome was
inspected when selecting this diagnostic refinement. The entire declared
development grid must still pass before tuning; any further failure is retained
and diagnosed, not silently bypassed.

## Execution and evidence retention

The resumable launcher is `tools/run_review_experiments.py`; its help
and companion runbook document external output roots, bounded CPU process
counts and transfer between hosts. Raw output must stay outside the checkout.
All legacy experiment files are immutable; the new config disables the old
selection-alias writer by setting `required_selection_export` to null.

The baseline CLI is also available without modifying the old source:

```sh
python -m experiments.run_transport_instantiation_study \
  --config experiments/configs/transport_review_followup.yaml \
  --profile smoke --phase development --output-root /workspace/cce-followup/smoke
python -m experiments.run_transport_instantiation_study \
  --config experiments/configs/transport_review_followup.yaml \
  --profile smoke --phase tuning --output-root /workspace/cce-followup/smoke \
  --selection-output /workspace/cce-followup/smoke-selection.json
python -m experiments.run_transport_instantiation_study \
  --config experiments/configs/transport_review_followup.yaml \
  --profile smoke --phase evaluation --output-root /workspace/cce-followup/smoke \
  --selection /workspace/cce-followup/smoke-selection.json
```

Use `full` and separate full output/selection paths for the complete study.
The old aggregator can check the full raw grid, but its default decomposition
contains only transport-Hessian means. A follow-up export must preserve the
per-seed records needed for all-method bound accounting and paired-bootstrap
recomputation; the locked paper renderer must not be pointed at new results.

The new execution manifest must bind this protocol, the actual new config,
launcher and analysis tools, unchanged scientific source digests, Git revision
and dirty status, dependency versions and thread/worker settings. The existing
selection includes the actual config in its input inventory, but the old
study-source inventory additionally names the original config; that historical
inventory alone is insufficient to bind the new workflow.

Retain all raw round logs externally and hash them. The compact GitHub-transfer
export must include every tuning/evaluation per-seed summary, identities and
selection record, paired terminal outcomes, bootstrap seeds/settings and
verified hashes. This permits recomputation of paired terminal intervals even
when raw round logs exceed GitHub file limits. Such an export does not by
itself establish raw-trajectory integrity; label retained, exported and absent
evidence distinctly. If raw trajectories are archived separately, publish the
archive digest and actual location only after upload succeeds.

Any amendment after reading pilot results must be dated and disclose what was
observed and changed. Preserve the original pilot result and use fresh
evaluation seeds for a scientifically changed design; do not relabel a new
design as this prespecified one.
