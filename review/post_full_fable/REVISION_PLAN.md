# Recommended direction and next decisions

Develop a focused paper about **what transporting existing confidence guarantees,
how conservative certificates affect decisions, and where the construction stops
being useful**. Use the completed negative study as central evidence. Do not make
a regret-improvement or practical scalability claim for the evaluated policy.

This agrees with the broad direction of [Fable's review](review.md), with the
[scientific qualifications](QUALIFICATIONS.md) applied. The width limitation is
an elementary consequence of the present construction. The case for a paper
must come from an informative operational analysis and careful positioning,
not from renaming that consequence as a major new impossibility theorem.

## What we now know

- In the full three-condition study, Hessian transport has higher mean regret
  than all three comparators in every condition. All nine pointwise paired 95%
  intervals exclude zero. These results contradict a performance-improvement
  claim for this policy and design.
- The new primary bounds are dominated by path inflation; removing this problem
  is insufficient because the frozen policy's own bounds are also vacuous.
- `frozen_reference` still learns the representation. "Frozen" describes the
  collection-time metric, not an untrained or fixed-representation baseline.
  Shared prediction-MSE tuning controls one implementation choice; it does not
  establish regret-optimal tuning for every policy.
- On identical states, exact actionwise transport recovers the frozen score.
  Merely tightening this transport cannot create new statistical information.
- The independent raw-log analysis measures extensive width-dominated selection.
  Its reproducible evidence and precise limitations are in
  [the diagnostic record](independent/README.md). It is an exploratory analysis
  informed by the completed evaluation, not a newly prespecified hypothesis test.
  On the Hessian policy's own histories, it selects the width argmax in
  99.382%, 99.962%, and 99.982% of rounds; the strict bonus-gap condition holds
  in 97.104%, 99.372%, and 99.508%. These pooled fractions describe dependent
  rounds. Sixteen primary-state ranking differences under more precise final
  arithmetic occur early; their possible effects on later histories are untested.

## The first three actions

### 1. Integrate the actual results and repair the claims

Update the active TMLR manuscript with the full-study regret table, paired
intervals, realized drift, and bound decomposition. State 600 evaluation
trajectories and distinguish the 294 development/tuning trajectories. Keep the
original near-linear study separate, explicitly disclosing its missing raw
trajectories; do not silently replace or pool its evidence.

Rewrite the abstract, introduction, and conclusion around conditional validity
and measured conservatism. Scope base dominance to the original study and path
dominance to the follow-up. Include confidence/optimism success for the naive
control, pointwise uncertainty, changing reward tasks across W, and the fixed
teacher. Remove any suggestion that passing numerical checks verifies the
theorem or that more drift should favor transport.

**Done when:** each numerical claim traces to committed evidence; neither the
abstract nor the conclusion overstates the theory, experimental independence,
or numerical certification; the TMLR PDF and source archive rebuild cleanly.

### 2. State the precise mathematical limit and explain the mechanism

Add a short proposition: the existing certified effective width is at least the
reference width on the same history; the exact actionwise ratio yields equality.
State the limited-information necessity claim with its assumptions and exclude
any adaptive-regret ordering. Distinguish it from the scalar endpoint oracle.
Do not claim the elementary width comparison is novel without a literature check.

Use the preserved log diagnostics to report width-argmax agreement and the
stronger bonus-gap condition. Report per-seed variation, disagreement with
alternative scores on the same histories, and numerical tie sensitivity. Include
all four behavior histories to show which conclusions depend on the states being
visited. Those one-step recommendations are not reconstructed alternative runs.

**Done when:** the mechanism is supported by reproducible calculations, with
adaptive causal claims left open. The analysis must retain unfavorable findings
and the few ranking disagreements, rather than adjusting tolerances to erase them.

### 3. Prove a tighter certificate before deciding on another experiment

The scaled-tanh gradient is `q_theta(z)=a_theta(z)*phi(z)`, where
`a_theta=sech^2(phi(z)^T theta/sqrt(W))`. Bounded parameters and features give a
termwise relative comparison of current and collection-time weights. With unit
bounds this implies

\[
d_{\rm Th}(\bar V_t,V_t)\le 4\log\cosh(1/\sqrt W).
\]

The resulting deterministic distance bounds are approximately **0.124, 1.735,
and 5.300** at W=16, 1, and 0.25. Category-specific accumulated weight ratios can
tighten the sandwich further. See [the derivation](independent/relative_certificate.md).
This is an endpoint comparison; it must not be mislabeled an upper bound for
the original interpolated factor-path length.

First audit this proposed certificate on existing histories, explicitly as
exploratory analysis. Compare its width overhead and computation with the
direct reference width and existing endpoint oracle. If it is sufficiently
tight and answers a scientific question beyond reproducing the reference score,
freeze a new protocol and evaluate any new policy with fresh seeds. No adaptive
performance improvement from this proposal has been measured.

**Stop/go:** stop algorithmic expansion if the only benefit is approaching the
already available frozen policy without a computational or statistical advantage.
A substantially cheaper certificate or a genuinely stronger confidence event
would justify further research. Keep this gate separate from the paper's honest
negative finding.

## Paper structure and wording

Working title: **Confidence Transport under Relinearization: Guarantees,
Conservatism, and Policy Behavior**.

Suggested structure:

1. The confidence/relinearization mismatch and the precise question being answered.
2. Reference confidence and the transport/operator/solver theorem.
3. The same-history width limitation and the cost of conservative certificates.
4. Corrected centers, assumptions, and the model-specific certificate if validated.
5. The original audit, full follow-up, and separately labeled exploratory diagnostics.
6. Related work, practical limits, and open statistical/computational questions.

A conservative replacement abstract, to finalize after integrating the evidence:

> Retraining a contextual-bandit model changes the gradient features used in
> current curvature, while sequential confidence can be built from features
> frozen when rewards were collected. We study the guarantees and limitations of
> transporting this confidence to relinearized curvature. A conditional UCB
> theorem separates metric transport, approximate operators, and solver widths,
> and bounds regret through the frozen sequential information gain. For squared
> loss, a corrected prediction center supplies reference confidence along
> predictable parameter paths without requiring nonlinear optimizer convergence,
> while retaining explicit approximation-error charges. The transport construction
> also has a simple limitation: its certified width cannot be smaller than the
> direct reference width on the same history, and exact actionwise transport
> reproduces that width. This comparison does not order the realized regret of
> policies with different histories. We examine these distinctions in a
> 29-parameter scaled-tanh model. A prespecified follow-up evaluates four policies
> across three conditions with 50 paired seeds per condition. The Hessian-transport
> policy has higher mean pseudo-regret than every comparator in every condition;
> all nine pointwise paired confidence intervals exclude zero. Its regret bounds
> are vacuous and dominated by path inflation, while the reference policy's own
> bounds are also vacuous. Floating-point confidence and optimism diagnostics pass
> for all evaluated policies, including an uncertified control. The study separates
> conditional validity, certificate usefulness, and observed policy behavior, and
> identifies the limitations of this particular implementation.

## Work that should not block the immediate rewrite

- **New confidence in current geometry:** potentially important, but requires a
  new statistical argument accounting for adaptive relinearization. Treat this
  as a separate research project, not a promised patch.
- **Naive-optimism failure:** first give a clearly scoped mathematical example.
  Distinguish an abstract SPD example from a realizable bandit instance. Only run
  new stress experiments if they test a justified mechanism under a new protocol.
- **Real-data and two-A100 benchmarks:** useful after identifying an operational
  algorithm and a hypothesis about cost or performance. The current dense
  29-dimensional questions run on CPU; more GPU computation does not resolve
  loose certificates or establish novelty.

## Submission gates

Compare the precise claims against misspecified linear-bandit, neural-bandit,
metric-perturbation, and certified-solver literature. Verify outstanding
bibliography entries from authoritative sources. A conditional theorem assembled
from standard arguments plus one synthetic negative result may still be too
limited; seek a broader operational lesson, a nontrivial certificate analysis,
or a clear computational use case before deciding the paper is ready.

Retain the full follow-up raw logs and arrange a durable distribution path for
roundwise replay. The current Git export supports terminal-summary/interval
checks only. Resolve the strict release packager's system TeX dependency without
weakening its trust checks, and verify the anonymous submission bundle. These
are release tasks, separate from scientific support for the claims.

This review package does not change the manuscript, experimental protocol,
algorithm, or frozen evaluation artifacts. It records the next concrete work
and the conditions under which more experiments would be informative.
