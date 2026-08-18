# Theory generalization audit

Original theory baseline: `9128276162c0fcb1d267c0a9043f8beed11f192e`
(`9128276`).
Final-pass starting commit: `47037a2df6b81befd4a0cb3c5974e3565d8f61b6`
(`47037a2`).
The audit describes the source tree containing this file. The resulting commit
SHA is reported in the completion report.

This audit compares the previous headline theorem with the revised theorem
derived in `THEORY_TRANSPORT_DERIVATIONS.md`. It also records restrictions that
were not removed and claims that remain out of scope.
The abstract result is titled “Estimator- and solver-agnostic confidence
transport”; the corrected center is its primary squared-loss specialization,
not an assumption of the abstract theorem.

## 1. Headline theorem comparison

| Topic | Previous headline theorem | Revised headline theorem | Status |
|---|---|---|---|
| Predictive center | Original nonlinear center plus an optimizer-centering certificate | Generic pre-reward center; concrete result uses the corrected center | Removed from headline |
| Representation update | Warm-started optimizer for the full-history nonlinear loss | Any predictable parameter sequence inside the certified region | Relaxed |
| Current/reference transport | One-sided endpoint comparison; two-sided closure needs `chi_t<1` | Classical Thompson-Finsler selected-path comparison for every finite path length | Removed smallness from primary exact-current closure |
| Action domain | Finite enumeration and exact argmax | Standard-Borel space, graph-measurable random correspondence, measurable finite suprema, and measurable `xi_t`-approximate selector | Generalized under explicit formal premises |
| Solver | Uniform relative CG energy error over all actions | Any simultaneous upper-width certificate plus played-action sharpness | Solver-agnostic |
| Realizability | Exact realizability | Fixed ex-ante reference model plus historical and current misspecification envelopes | Relaxed, with explicit bias cost |
| Algorithmic operator | Exact current or one-sided pre-reward comparison | Two-sided pre-reward comparison to current curvature | Stronger closure, but adds a lower-factor requirement |
| Width complexity | Dynamic realized `Lambda_T^C` remains in the general theorem | Sequential frozen `gamma_T` closes the main theorem | Closed under the two-sided certificate |
| Main additive terms | Linearization and centering errors | Current linearization, misspecification, and score-oracle errors | Optimizer term removed |
| Statistical model | Gaussian/squared-loss construction | Abstract confidence theorem plus a squared-loss corrected-center construction | Estimator-agnostic headline |

The revised theorem is not a strict superset of the old one-sided dynamic
theorem. The new frozen-potential closure requires a positive lower operator
factor. The old result remains useful when only one-sided optimism transfer is
available. The paper now states this distinction instead of claiming universal
dominance.

## 2. Assumptions removed from the primary result

1. Exact or approximate stationarity of the nonlinear optimizer.
2. The optimizer residual `zeta_t` and the action-scaled centering certificate.
3. A finite action set.
4. Exact score maximization.
5. CG as the theorem interface.
6. Uniform all-action solver sharpness. Only all-action upper validity remains;
   sharpness is required at the played action.
7. Exact realizability.
8. `chi_t<1` for the primary exact-current transport.
9. A supplied fixed tangent subspace for the primary finite-dimensional rate.
10. An uncontrolled dynamic-width quantity in the main regret display.

## 3. Assumptions still required

1. The reference metric is a predictable sequential rank-one update formed
   from collection-time queries, with `lambda>0` and `sigma>0`.
2. The action space is standard Borel. The random action correspondence has an
   `H_t^- \otimes B`-measurable graph.
3. The mean, query, center, bias, solver width, and score maps are jointly
   measurable on that graph. Both mean-reward and score suprema are finite
   measurable random variables.
4. The abstract reference-metric confidence event and every certificate event,
   including universal all-action events, are measurable.
5. The oracle returns an `H_t`-measurable selector in the random domain.
6. The Thompson-Finsler path has a finite pre-reward upper envelope. A finite
   but large value may be numerically vacuous.
7. The algorithmic operator has lower and upper pre-reward comparison factors
   relative to exact current curvature.
8. The solver upper width is valid for every action considered by the oracle.
   Finite sharpness is required only at the played action.
9. The solver-upper, played-sharpness, and score-oracle inequalities use the
   same realized width map.
10. The query norm is bounded for the displayed potential constant.
11. The corrected-center specialization uses a fixed ex-ante reference
    parameter in the certified smoothness region and a zero-centered ridge in
    the chosen coordinates. For a pretrained model, those are displacement
    coordinates from initialization.
12. Historical and current linearization and misspecification envelopes are
    supplied before the reward where they are used.
13. Randomized certificate budgets are `H_t^-`-measurable and allocated before
    their random objects are drawn. Validity is conditioned on the sigma-field
    immediately before each draw. The certificate-source index set is finite or
    countable.

## 4. New restrictions and tradeoffs

### Two-sided operator certification

The lower factor `kappa_{-,t}>0` is new in the headline closed theorem. It is
what transports the played algorithmic width back to the frozen potential. An
upper-only surrogate still fits the old dynamic fallback theorem, but not the
new closed result. No lower factor is inferred from an upper factor.

### All-domain upper solver validity

Played-action sharpness is sufficient, but optimism still requires an upper
solver certificate over every action searched by the score oracle. For an
uncountable action domain this must be a simultaneous functional certificate,
not a pointwise union bound.

### Fixed reference model under misspecification

The reference parameter must be fixed before data collection. Selecting it
after observing rewards needs a separate model-selection argument. A fixed
nonzero current misspecification envelope can produce a linear cumulative
additive term. A constant historical envelope makes the confidence radius grow
as $\Theta(\sqrt{t})$; after multiplication by widths and summation, its
exploration contribution can be linear up to logarithmic factors.

### Corrected-center access cost

The theorem removes optimizer convergence from the statistical proof, but the
algorithm needs access to the frozen-feature ridge estimator. That can require
stored frozen queries, replay with historical checkpoints, an explicit
low-dimensional representation, or a separately certified approximation.

### Filtration and random domains

`H_t^-` is the history after the context and action correspondence are observed
but before fresh round-`t` randomization. `H_t` adds the aggregate pre-reward
randomization. The reference metric, representation parameter, exact current
metric, confidence radius, and certificate budgets are predictable when stated
as `H_t^-`-measurable. The realized randomized operator, path envelope,
condition factors, solver outputs, oracle tolerance, and selected action may be
only `H_t`-measurable. The reward is observed afterward.

A finite random action set is not automatically measurable. The repaired
corollary assumes an `H_t^-`-measurable size `K_t` and an `H_t^-`-measurable
enumeration `a_{t,1},...,a_{t,K_t}`. The smallest maximizing index is then an
`H_t`-measurable exact selector. Without such a premise, a singleton-valued
correspondence can encode a non-Borel set and have no measurable selector.
The retained one-sided theorem now uses the same measurable enumeration for its
learner and true-mean comparator. Its finite score vector is pre-reward
measurable, and both smallest-index rules are measurable.

### Certificate status

| Certificate | Status |
|---|---|
| Reference confidence event | Statistical or model-specific premise |
| Path-length envelope | Analytic or separately certified |
| Two-sided operator comparison | Deterministic, analytic, or randomized with failure allocation |
| All-domain solver upper validity | Exact-arithmetic or verified numerical certificate |
| Played-action sharpness | Exact-arithmetic or verified selected-action certificate |
| Linearization and misspecification envelopes | Supplied pre-reward bounds |
| Measurable approximate selector | Oracle premise |

“Supplied” or “valid” does not mean efficiently computable. Float64 residuals,
empirical eigenvalues, and unenclosed numerical point checks remain diagnostics.

## 5. Proof-obligation audit

| Obligation | Result | Notes |
|---|---|---|
| Standard-Borel random-domain formalism | Resolved in current source | Measurable graph, joint maps, both finite measurable suprema, measurable selector, and measurable universal events are explicit |
| Measurably enumerated finite domains | Resolved in current source | The headline corollary and legacy fallback use `H_t^-`-measurable sizes/enumerations and smallest-index rules for learner and comparator |
| Filtration classification | Repaired and verified | Predictable means `H_t^-`; action-dependent realized designs are `G_t`-measurable before reward noise, while randomized score objects may be `H_t` pre-reward measurable |
| Certificate failure allocation | Repaired and verified | The source index set is finite or countable, so the joint event is measurable and the union bound is countable |
| Logarithmic SPD path sandwich | Verified | Uses absolute continuity and fixed-vector log differentiation |
| Thompson endpoint consequence | Verified | `d_Th(V(0),V(1))<=D(V)`; endpoint, path, and factor bounds are distinguished |
| Symmetric exponential-factor sharpness | Verified | The diagonal two-dimensional path attains each one-way `exp(D/2)` factor in a different query direction |
| Rectangular factor-path bound | Repaired and verified | `B in R^{m x d}`; `nu_t>=0`, measurable, and `L^1` before integration |
| Scalar Hessian/`Q_t` certificate | Verified | Gives `2 L_g sqrt(Q_t)/(sigma sqrt(lambda))`; stacked path is synthetic |
| Vector-output factor dimensions | Verified | Uses `R_s J_s in R^{r_s x d}` |
| Weighted Fisher path | Conditional but verified | Requires an explicit absolutely continuous weight factor and controls both derivative terms |
| Current/reference width transport | Verified | Every Loewner inversion direction checked |
| Two-sided approximate-operator transport | Verified | Exact current is the unit-factor case |
| Generic solver interface | Verified | Upper validity is global; sharpness is played-action only; a fixed-query CG certificate needs a jointly measurable family and simultaneous all-action validity to instantiate the global interface |
| Concrete inverse-quadratic certificate | Repaired in exact arithmetic | Covers `L>0`, `L<=0<U`, `U=0`, and `q=0`; float64 point residuals are not enclosures |
| Standard-Borel approximate oracle | Resolved in current source | Uses measurable finite suprema and an explicitly assumed measurable selector |
| Instantaneous regret constants | Verified | Sharp factor is `1+alpha exp(D)sqrt(Kappa)`; bias twice, oracle error once |
| Frozen potential closure | Verified | One Cauchy-Schwarz step after the per-round bound |
| Corrected-center identity | Verified | Holds for any predictable representation path |
| Historical misspecification contraction | Verified | Uses `Phi^T bar V^{-1} Phi <= I`; factor is `1/sigma` |
| Finite-dimensional information bound | Verified | Uses `min(d,T)` rank and trace; no supplied subspace |
| Global near-linearity corollary | Verified | The radius-`R` trust region gives `Q_t<=4R^2(t-1)`; the requested exponential rate follows without `D_t<1` |
| Frozen linear reduction | Verified | Recovers the standard LinUCB determinant-potential form |
| Exponential-family confidence theorem | Not attempted | Factor geometry alone is insufficient; retained as future work |
| Unrestricted neural-training guarantee | Not attempted | Outside the proved scope |

## 6. Constant check against the proposed target

The prompt proposed a leading term with coefficient `2 alpha_t`. Direct proof
first yields

```text
beta_t [1 + alpha_t exp(bar D_t)
              sqrt(kappa_{+,t}/kappa_{-,t})] bar s_t(a_t).
```

This is sharper. Since all multiplicative quantities in the second term are at
least one, it is bounded by

```text
2 alpha_t beta_t exp(bar D_t)
  sqrt(kappa_{+,t}/kappa_{-,t}) bar s_t(a_t).
```

The paper states both versions. The symmetric actionwise model-bias envelope
appears twice at the played action. The approximate score-oracle error appears
once. These counts follow directly from upper confidence at the comparator and
lower confidence at the played action.

## 7. Adversarial checks

### Rotating features

Rotating rank-one replay gradients can defeat pairwise collinearity and local
endpoint lower bounds. The logarithmic metric proof does not match individual
features; it compares the complete SPD path. Positive damping keeps the path
invertible. The certificate may still be large under rapid rotations or severe
conditioning, which is reported as vacuity rather than hidden.

### Large path length

No proof step assumes `D_t<1`. The exponential comparison remains correct for
large finite `D_t`. A large factor is not described as useful merely because it
is finite.

### Sharpness of the exponential metric factor

For `bar V=I_2` and
`V(tau)=diag(exp(D tau),exp(-D tau))`, both the Thompson endpoint distance and
selected-path length equal `D`. The `e_1` query attains
`bar s=exp(D/2)s`, while the `e_2` query attains
`s=exp(D/2)bar s`. Thus the two one-way factors, and the resulting uniform
round trip, cannot be improved using only the symmetric distance information.
This is not a bandit regret lower bound and does not say every trajectory pays
the worst-case factor.

### Global near-linearity scale

With `||theta^circ||,||theta_t||<=R`,
`L_mu<=c_mu/sqrt(W)`, and `L_g<=c_g/sqrt(W)`, the exact corrected-center
specialization has `Q_t<=4R^2(t-1)` and
`bar D_t<=4c_gR sqrt(t-1)/(sigma sqrt(lambda W))`. The Taylor envelopes are at
most `2c_mu R^2/sqrt(W)`. Substitution into the finite-dimensional rate gives
the displayed exponential corollary. Taking `W=Omega(T)` keeps the path factor
bounded without any `D_t<1` condition. Here `W` is an abstract smoothness scale,
not network width or parameter count.

### Approximate-operator condition ratio

The bound deteriorates as the certified ratio
`kappa_{+,t}/kappa_{-,t}` becomes large. A common scalar rescaling
`C_t=c_t V_t` may use `kappa_-=kappa_+=c_t`, leaving the ratio equal to one
even if `c_t` tends to zero. An upper-only comparison still cannot close the
played algorithmic width through the frozen potential.

### Zero and empty cases

- `t=1`: the replay factor has zero rows, the exact and reference metrics are
  `lambda I`, `D_1=0`, and `gamma_0=0`.
- `q_t(a)=0`: every exact width is zero. A finite multiplicative solver factor
  requires the reported upper width to be zero.
- `bar D_t=0`: the selected path has zero length, the endpoints agree, and the
  exponential path factor is one.
- `d_Th(bar V_t,V_t)=0`: the endpoints agree, but a selected loop may still
  have positive path length.
- Exact operator and exact solver set
  `kappa_{-,t}=kappa_{+,t}=1` and `alpha_t=1`. The reference-to-current path
  factor `exp(bar D_t)` remains and becomes one only when `bar D_t=0`.
- Exact realizability: every misspecification envelope vanishes.
- Frozen linear model: linearization and representation-drift terms vanish.

### Measurability and randomization

All score inputs are fixed before reward observation. Objects selected before
fresh randomization are `H_t^-`-measurable; realized randomized objects may be
`H_t`-measurable. Played-action designs are `G_t`-measurable before the reward
noise, which is the pre-increment condition used by the self-normalized bound.
Conditional failure budgets may be predictable and random but must be allocated
before the relevant draw. The finite or countable source family is conditioned
source-by-source on the sigma-algebra immediately before each draw. Independence
is not assumed.
Terminal spectral quantities never enter an action-time confidence radius.

### Weighted Fisher factors

For `J_s in R^{p_s x d}` and `R_s in R^{r_s x p_s}`, both
`Rdot_s J_s` and `R_s Jdot_s` lie in `R^{r_s x d}`. Omitting the weight-factor
derivative would make the path certificate false for data-dependent weights.

### Counterexamples that force the repaired premises

- **Negative `nu_t`.** Constant `B` and `nu_t=-1` satisfy the squared PSD
  inequality but would assert `0=D(V)<=-2`. Nonnegativity and `L^1`
  integrability are explicit.
- **No all-action solver upper validity.** With two scalar actions, identity
  metrics, `beta=1`, zero bias, an optimal unit-query action of mean one, and a
  zero-query action of mean zero, reporting both widths as zero can make a tie
  rule select the zero-query action. Played sharpness holds, but regret is one
  while the played frozen width is zero.
- **No lower operator factor.** For `bar V=V=I_2` and
  `C=diag(epsilon,1)`, the upper comparison holds while the `e_1` algorithmic
  width is `epsilon^{-1/2}`. A bad action can win the UCB score by this width,
  and no frozen-potential bound independent of a lower factor follows.
- **Finite but nonmeasurable random domain.** A singleton correspondence that
  selects `{1}` on a non-Borel subset of `[0,1]` and `{0}` elsewhere has no
  measurable selector. Finiteness alone is not a replacement for graph
  measurability or a measurable enumeration.

## 8. Transport comparison table

| Transport route | Assumption | Width factor | Smallness required | Gradient rotation allowed |
|---|---|---:|---:|---:|
| Thompson-Finsler metric path | Finite normalized selected-path length `bar D_t` | `exp(bar D_t/2)` per one-way width comparison | No | Yes |
| Additive endpoint drift | Whitened stacked-design error `chi_t<1` | `(1+chi_t)/(1-chi_t)` for two-way width use | Yes | Yes, within endpoint norm control |
| Scalar-link relative | Fixed features and bounded derivative ratios | Relative derivative-ratio factor | Depends on lower ratio | Only scalar rescaling per feature |
| Exact current curvature | `C_t=V_t` | Operator factor one | No | Yes |
| Approximate curvature | `kappa_- V_t<=C_t<=kappa_+ V_t` | `sqrt(kappa_+/kappa_-)` in regret | `kappa_->0` | Yes |

Neither the local additive factor nor the exponential factor uniformly dominates
the other numerically because they summarize different geometric information.

## 9. Scope decisions

- The abstract theorem is estimator-agnostic. Squared loss is one concrete
  confidence construction, not a headline restriction.
- The normalized SPD path length and endpoint Thompson distance are classical.
  The paper claims novelty for their operational composition with frozen bandit
  confidence, replayed GGN/Fisher curvature, approximate operators, certified
  solver widths, approximate selection, and frozen-information closure.
- Weighted Fisher/GGN geometry is included only as a factor-path statement.
  No exponential-family confidence or regret corollary is claimed.
- CG and PCG give pointwise solver certificates. They instantiate the
  all-domain interface only with a jointly measurable family and simultaneous
  upper validity over every scored action; they are not theorem assumptions.
- The theory revision did not reinterpret legacy numerical values. A later
  repository cleanup retained only the compact diagnostics used by the paper;
  removed experiment code and detailed artifacts remain available in Git
  history.
- Retained negative findings remain in the appendix without numerical edits and
  are explicitly not evidence for the logarithmic-transport theorem.
- The full policy has no end-to-end scalability theorem.

## 10. Theory freeze

The confidence-transport theorem API is frozen in this source tree. No
additional theorem family will be added unless a concrete mathematical error is
found. Remaining work is empirical instantiation and presentation. This freeze
does not turn numerical diagnostics into proof and does not broaden any scope
claim below.

## 11. Current formal status and remaining scope limits

The baseline had unresolved formal obligations involving random action domains,
filtration terminology, the sign of `nu_t`, the `L<0` solver case, and width-map
consistency. The current source repairs those items, and the independent checks
recorded above found no remaining algebraic blocker
for the abstract theorem, path lemmas, corrected-center squared-loss
specialization, finite-dimensional rate, metric-factor sharpness statement, or
global near-linearity corollary. The following remain deliberately outside the
result:

1. unrestricted neural-network training or generic fine-tuning guarantees;
2. a complete exponential-family confidence theorem;
3. sublinear regret under fixed nonzero misspecification;
4. floating-point verified solver certification from ordinary residual checks;
5. uniform regret improvement from full curvature;
6. two-sided guarantees for arbitrary diagonal, low-rank, stale, or sketched
   operators;
7. empirical validation of the revised transported theorem;
8. end-to-end scalability of the full policy.

An earlier exact-current stable-excitation route was also abandoned rather than
stated as a theorem.  Its constrained approximate-minimizer proof still lacks a
complete normal-cone argument for distance and path stability, followed by a
time-uniform vector-martingale allocation with constants propagated through the
path and residual schedules.  No result in the manuscript relies on that
unfinished route.
