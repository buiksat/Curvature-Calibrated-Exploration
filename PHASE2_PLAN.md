# Phase 2 plan

Planning only. No simulation, new evaluation data, or experiment implementation
was performed for this document. All proposed settings and seeds below are new
protocol choices, not observed results. The Phase 1 manuscript contains none of
the candidate necessity calculations below.

## A. A realizable necessity instance

A proof and a numerical demonstration both look feasible. A finite-sample
proof is still owed. The existing Claude lead's preparation report supplied a
hand-derived saturated-collection/unsaturated-query route with teacher −R;
that report explicitly left the finite-N proof unverified. The construction
below is the writer's algebraic planning assessment of that route, not a
reviewed theorem or measured finding.

### Candidate and score

Use d = 1, one context and one measurably enumerated action with φ = 1,
B_φ = R = λ = 1, σ = 0.25, δ = 0.05, W = 0.25. The teacher θ° = −R is fixed
before collection. Use the deterministic, hence predictable, path θ_s = +R
for n collection rounds, then θ_(n+1) = 0. It stays in the certified convex
region. Zero noise is σ-sub-Gaussian and offers a deterministic proof route;
Gaussian noise with the same σ offers a subsequent probabilistic variant.
No optimizer-convergence assumption is needed by Corollary 10.

Write x = R/√W, ℓ = sech²x, N = n/σ², and M = √W tanh x. At the query round,

    V̄ = λ + Nℓ²,       V = λ + N,
    s̄ = (λ + Nℓ²)^(-1/2),       s = (λ + N)^(-1/2).

Thus V ≥ V̄, and s/s̄ tends to ℓ. This is consistent with Corollary 13's
allowed shrink; an asymptotic attainment/sharpness assertion would be a new
Phase 2 result requiring proof.

With zero noise, each collection-time pseudo-response is −2M + ℓR. The
corrected center at θ = 0 is the frozen ridge estimate

    m^corr = Nℓ(−2M + ℓR)/(λ + Nℓ²),       μ* = −M.

Use the experiment's actual envelopes, rather than secretly replacing them
with tighter remainders: ε_h = 2c_hR²/√W at collection and
b_0 = c_hR²/(2√W) at the query, where c_h = 4/(3√3). Its exact radius is

    β^corr = √[log(1 + Nℓ²/λ) + 2log(1/δ)] + √λR + ε_h√N.

The proposed test is exactly μ* > m^corr + β^corr s + b_0, with no transport
factor. The reference event is |μ* − m^corr| ≤ β^corr s̄ + b_0, with the same
center, radius and envelopes at every round.

### Why a finite instance looks feasible

As N grows, the true-minus-center gap tends to
√W[sinh(2x) − x − tanh x], while the naive uncertainty allowance tends to
ε_h + b_0 = √W(5/2)c_h x². At x = 2 the first bracket exceeds the second.
This positive limiting margin suggests a finite n can be bounded analytically;
it is not an executed search for n. The wider reference allowance remains
consistent with the deterministic Taylor bound and Corollary 10. There is no
impossibility conclusion under the paper's arbitrary predictable-path
assumption.

The proof work is to bound the finite-N ridge terms and the
√(log N)/√N statistical term explicitly, choose a concrete finite integer n,
and verify the simultaneous reference-confidence inequalities over the whole
path. For Gaussian noise, additionally bound the normalized historical noise
and exhibit an event on which reference confidence holds and naive optimism
fails; do not replace an intersection event with two unrelated probability
claims. A numerical demonstration should check the same inequalities with
adequate precision and preserve its seed/configuration. It is evidence for
that constructed instance, not a proof of population failure rates.

This one-action instance addresses a score's optimism, not regret or the need
for transport on the Section 6 optimizer's trajectory. A two-action extension
and an optimizer-generated path are separate questions. The current scientific
code fixes a 29-dimensional feature map and a projected-gradient path; Phase 2
would need a dedicated low-dimensional/path-controlled harness. Saturated
collection at fixed small W also differs from Corollary 12's near-linearity
regime. None of this should be added as a Phase 1 manuscript finding.

## B. An informative experimental condition

### Proposed protocol and hypothesis

Use a two-dimensional scaled-tanh model, T = 20,000 and W = 100T = 2,000,000,
with R = B_φ = λ = 1, σ = 0.25 and δ = 0.05. Context ξ is equally likely
±1; actions a are ±1; set φ(ξ,a) = (1,aξ)/√2 and fix the teacher θ° = (0,1).
The best action switches with context. The mean rewards are
±√W tanh[1/√(2W)], so a context-free action rule cannot exploit that switch.
This symmetric design is a deliberate test of useful confidence and learning,
not a promise that transported policies will separate.

Compare the same four corrected-center policies and the same context-free
benchmark on paired contexts/potential-noise streams. Retain selected-reward
feedback, the shared prediction-MSE optimizer-selection rule, projection,
exact dense operators, smallest-index ties, and the actual norm-dependent
Taylor envelopes. Prespecify a single condition and do not select it using
evaluation outcomes. Freeze optimizer and numerical checks on separate
development/tuning seeds. The hypothesis is that contextual policies learn
the switching action pattern, obtain regret well below the context-free
benchmark, and have a frozen-policy bound below the deterministic cap.
An advantage of transport remains an open question.

Primary comparison: paired Hessian-minus-frozen cumulative pseudo-regret at T,
with a prespecified 95% paired seed-bootstrap interval. Separately report each
policy versus the context-free benchmark and the fraction of frozen-policy
own-history bounds below the cap. Record all secondary endpoint/naive
comparisons as secondary. Do not infer equivalence from overlapping intervals
or failure to reject a difference. Report interval multiplicity explicitly.

Proposed disjoint seeds: development 41000–41001, tuning 41100–41109,
evaluation 41200–41249; keep the teacher fixed. These avoid the entire
30000–30249 range. They have not been used in this task; check the complete
future-run inventory before launching Phase 2.

### A priori bound feasibility

Using the uniform frozen-width counterpart of the existing finite-dimensional
rate, Γ = 2log(1 + T/(2λσ²)) ≈ 23.96587. The upper radius, including historical
Taylor error, is at most

    √[Γ + 2log(1/δ)] + √λR + 2c_hR²√T/(σ√W) ≈ 7.08917.

The resulting complete frozen bound, including current bias, is at most

    2√[(σ² + 1/λ)TΓ] · 7.08917 + 4c_hR²T/√W ≈ 10,161.70,

below the deterministic cap 2T = 40,000. These are algebraic planning
calculations from the displayed bound and proposed constants, not evaluation
results. They concern the confidence event and exact arithmetic; float64
checks alone will not become numerical certificates. The bounded-region
Hessian envelope is also controlled (approximately 1.23165), but the condition
does not promise improved transported regret.

### Compute and implementation work owed

The evaluation has 200 trajectories and four million decision rounds. With
the existing 20-step shared optimizer candidate, that is 80 million small
gradient steps. Four fixed feature categories permit exact squared-loss
category sufficient statistics; current matrices and Q_t can also use category
counts/running parameter sums. Verify parity with full-history calculations
before relying on these computational reductions. Use analytic Hessian and
direct endpoint certificates, without per-round numerical path quadrature.

Existing retained T = 1000 runtime fields range from 20.36 to 87.73 seconds,
with median 38.49 seconds per trajectory, for the different 29-parameter
implementation and its diagnostics. They do not measure the proposed harness.
A provisional 12–60 CPU-hour evaluation budget (about 3–15 wall hours on four
workers), plus development/tuning and storage, assumes 10–50 ms per proposed
round including optimization and logging. This is an engineering estimate.
A development-only pilot must measure actual cost and revise the budget
before evaluation. Reusing the full-history/quadrature implementation can grow
quadratically with T and invalidate that estimate. No pilot or new harness has
been run or written here.
