# Theory generalization audit

Baseline: `codex/cc-ucb-theory-experiments` at
`7f8cc0a7414f11e61adcd4dc5842c577e043f0a9`.

This audit compares the previous headline theorem with the revised theorem
derived in `THEORY_TRANSPORT_DERIVATIONS.md`. It also records restrictions that
were not removed and claims that remain out of scope.

## 1. Headline theorem comparison

| Topic | Previous headline theorem | Revised headline theorem | Status |
|---|---|---|---|
| Predictive center | Original nonlinear center plus an optimizer-centering certificate | Arbitrary predictable center; concrete result uses the corrected center | Removed from headline |
| Representation update | Warm-started optimizer for the full-history nonlinear loss | Any predictable parameter sequence inside the certified region | Relaxed |
| Current/reference transport | One-sided endpoint comparison; two-sided closure needs `chi_t<1` | Logarithmic SPD path comparison for every finite path length | Removed smallness from primary exact-current closure |
| Action domain | Finite enumeration and exact argmax | Measurable arbitrary action domain and measurable `xi_t`-approximate score oracle | Generalized, with explicit measurability requirement |
| Solver | Uniform relative CG energy error over all actions | Any simultaneous upper-width certificate plus played-action sharpness | Solver-agnostic |
| Realizability | Exact realizability | Fixed ex-ante reference model plus historical and current misspecification envelopes | Relaxed, with explicit bias cost |
| Algorithmic operator | Exact current or one-sided predictable comparison | Two-sided predictable comparison to current curvature | Stronger closure, but adds a lower-factor requirement |
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
   from collection-time queries.
2. The abstract reference-metric confidence event holds simultaneously over
   the score domain.
3. The action supremum and approximate score selector are measurable. A bare
   measurable action space does not guarantee either property.
4. The logarithmic path has a predictable finite upper certificate. A finite
   but large value may be numerically vacuous.
5. The algorithmic operator has both lower and upper predictable comparison
   factors relative to exact current curvature.
6. The solver upper width is valid for every action considered by the oracle.
7. The solver has a finite sharpness certificate at the played action.
8. The query norm is bounded and the reference ridge has `lambda>0` for the
   displayed potential constant.
9. The corrected-center specialization uses a fixed ex-ante reference
   parameter in the certified smoothness region.
10. Historical and current linearization and misspecification envelopes are
    supplied predictably.
11. Randomized certificate failure budgets are allocated before their random
    objects are drawn.

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
after observing rewards needs a separate model-selection argument. Nonvanishing
misspecification generally produces a linear additive term and may also enlarge
the historical radius linearly up to logarithmic factors.

### Corrected-center access cost

The theorem removes optimizer convergence from the statistical proof, but the
algorithm needs access to the frozen-feature ridge estimator. That can require
stored frozen queries, replay with historical checkpoints, an explicit
low-dimensional representation, or a separately certified approximation.

## 5. Proof-obligation audit

| Obligation | Result | Notes |
|---|---|---|
| Logarithmic SPD path sandwich | Complete | Uses absolute continuity and fixed-vector log differentiation |
| Rectangular factor-path bound | Complete | Orientation checked for `B in R^{m x d}` |
| Scalar Hessian/`Q_t` certificate | Complete | Gives `2 L_g sqrt(Q_t)/(sigma sqrt(lambda))` |
| Vector-output factor dimensions | Complete | Uses `R_s J_s in R^{r_s x d}` |
| Weighted Fisher path | Conditional but complete | Requires an explicit absolutely continuous weight factor and controls both derivative terms |
| Current/reference width transport | Complete | Every Loewner inversion direction checked |
| Two-sided approximate-operator transport | Complete | Exact current is the unit-factor case |
| Generic solver interface | Complete | Upper validity is global; sharpness is played-action only |
| Concrete inverse-quadratic certificate | Complete in exact arithmetic | Ordinary float64 residual checks are not verified enclosures |
| Arbitrary-action approximate oracle | Complete | Uses suprema; assumes measurable approximate selector |
| Instantaneous regret constants | Complete | Sharp factor is `1+alpha exp(D)sqrt(Kappa)`; bias twice, oracle error once |
| Frozen potential closure | Complete | One Cauchy-Schwarz step after the per-round bound |
| Corrected-center identity | Complete | Holds for any predictable representation path |
| Historical misspecification contraction | Complete | Uses `Phi^T bar V^{-1} Phi <= I`; factor is `1/sigma` |
| Finite-dimensional information bound | Complete | Uses `min(d,T)` rank and trace; no supplied subspace |
| Frozen linear reduction | Complete | Recovers the standard LinUCB determinant-potential form |
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

### Approximate operator near singularity

As `kappa_{-,t}` tends to zero, the bound diverges. This is unavoidable for the
chosen proof because the algorithmic metric can otherwise make played widths
arbitrarily large relative to the reference potential.

### Zero and empty cases

- `t=1`: the replay factor has zero rows, the exact and reference metrics are
  `lambda I`, `D_1=0`, and `gamma_0=0`.
- `q_t(a)=0`: every exact width is zero. A finite multiplicative solver factor
  requires the reported upper width to be zero.
- `D_t=0`: endpoint metrics agree in the Loewner comparison, though a nonzero
  path length can occur for a loop with equal endpoints.
- Exact operator and exact solver: all distortion factors reduce to one.
- Exact realizability: every misspecification envelope vanishes.
- Frozen linear model: linearization and representation-drift terms vanish.

### Measurability and randomization

All schedules used in the score are fixed before reward observation. Conditional
failure probabilities may be predictable and random but must be allocated
before the relevant random draw. Independence is not assumed. Terminal spectral
quantities never enter an action-time confidence radius.

### Weighted Fisher factors

For `J_s in R^{p_s x d}` and `R_s in R^{r_s x p_s}`, both
`Rdot_s J_s` and `R_s Jdot_s` lie in `R^{r_s x d}`. Omitting the weight-factor
derivative would make the path certificate false for data-dependent weights.

## 8. Transport comparison table

| Transport route | Assumption | Width factor | Smallness required | Gradient rotation allowed |
|---|---|---:|---:|---:|
| Logarithmic metric path | Finite normalized SPD path length `bar D_t` | `exp(bar D_t/2)` per one-way width comparison | No | Yes |
| Additive endpoint drift | Whitened stacked-design error `chi_t<1` | `(1+chi_t)/(1-chi_t)` for two-way width use | Yes | Yes, within endpoint norm control |
| Scalar-link relative | Fixed features and bounded derivative ratios | Relative derivative-ratio factor | Depends on lower ratio | Only scalar rescaling per feature |
| Exact current curvature | `C_t=V_t` | Operator factor one | No | Yes |
| Approximate curvature | `kappa_- V_t<=C_t<=kappa_+ V_t` | `sqrt(kappa_+/kappa_-)` in regret | `kappa_->0` | Yes |

Neither the local additive factor nor the exponential factor uniformly dominates
the other numerically because they summarize different geometric information.

## 9. Scope decisions

- The abstract theorem is estimator-agnostic. Squared loss is one concrete
  confidence construction, not a headline restriction.
- Weighted Fisher/GGN geometry is included only as a factor-path statement.
  No exponential-family confidence or regret corollary is claimed.
- CG and PCG are solver-interface examples, not theorem assumptions.
- The existing experiments are unchanged. They were designed for the previous
  theorem stack and are not evidence for the new logarithmic-transport theorem.
- Existing negative findings remain in the manuscript and appendix without
  numerical edits.

## 10. Unresolved blockers

There is no unresolved algebraic proof obligation for the new abstract theorem,
path lemmas, corrected-center squared-loss specialization, or finite-dimensional
rate. The following are deliberately not claimed:

1. computable nonvacuous path certificates for unrestricted neural training;
2. a complete exponential-family confidence theorem;
3. sublinear regret under fixed nonzero misspecification;
4. floating-point verified solver certification from ordinary residual checks;
5. two-sided guarantees for arbitrary sketches or diagonal approximations;
6. empirical validation of the revised theorem.

