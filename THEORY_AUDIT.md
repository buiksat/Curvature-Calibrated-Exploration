# Theory Audit

Audit date: 2026-07-21

## Scope and verdict

This audit covers `paper/main.tex:1-3666`, `paper/macros.tex`, and the compiled
theorem-family numbering in `paper/main.aux`.  The standalone
`paper/true_ggn.tex` is not input by `paper/main.tex` and is outside scope.

All displayed theorem-family conclusions follow from their stated hypotheses.
The main regret formula and its one-shot Cauchy--Schwarz proof are preserved.
The operational path statistics now instantiate the previously external
linearization, centering, transfer, and confidence schedules predictably with
`O(d)` additional certificate state.  The former `gammahat`, probability-event,
near-linear, refresh-rank, endpoint, window, and scalar-invariance blockers are
resolved.  No formal correctness blocker or remaining proof-presentation or
explicitness gap was identified in the audited theorem family.

Status terminology:

- **Pass**: the conclusion follows from the stated hypotheses.

## Numbering semantics

`paper/macros.tex` aliases `lemma`, `corollary`, and `proposition` to the global
`theorem` counter without resetting at the appendix.  The current
`paper/main.aux` therefore gives one visible sequence from 1 through 26:

| Source environment | Current rendered numbers |
|---|---|
| `theorem` | Theorems 1, 21 |
| `lemma` | Lemmas 4, 5, 8, 10, 11, 12, 14, 15, 16, 19, 26 |
| `corollary` | Corollaries 2, 3, 6, 7, 9, 13, 17, 18, 23, 24, 25 |
| `proposition` | Propositions 20, 22 |

The anchors retain their source types, for example `theorem.1`,
`corollary.2`, `lemma.5`, and `proposition.22`.  Assumptions use a separate
counter and remain Assumptions 1--5.

## Assumption and filtration registry

| Item | Location | Content used by proofs |
|---|---|---|
| Assumption 1, noise | `paper/main.tex:805-813` | `eta_t` is conditionally `sigma`-sub-Gaussian given the pre-reward sigma algebra `G_t`. |
| Assumption 2, bounded features | `815-826` | Current, replayed, and frozen gradient features have norm at most `G`. |
| Assumption 3, local linearization | `828-866` | A known convex region contains `theta*` and all iterates; prediction gradients are uniformly `L_mu`-Lipschitz there. |
| Assumption 4, centering | `868-898` | A nonnegative `Hist_t`-measurable optimizer residual and centering certificate control the center error by `bar psi_t bar s_t(a)`. |
| Assumption 5, transfer | `1267-1273` | Predictable `u_t(a)>=1` satisfies `bar s_t^2(a)<=u_t(a)s_C,t^2(a)` for every action. |
| Operator conditions | `1253-1265` | `Calg_t` is predictable, symmetric, SPD, and at least `lambda I`; the dynamic lemma also uses `Calg_1=lambda I`. |
| Filtration | `2552-2621` | `H_t^-` is pre-random-draw, `Hist_t` includes `Omega_t`, and `G_t` is pre-reward; randomized certificate failures are allocated conditional on `H_t^-`. |
| Auxiliary estimator | `2625-2660` | Frozen-feature ridge estimator with predictable design and pseudo-response `g_s^T theta*+rho_s+eta_s`. |

## Complete result inventory

| Visible result | Label; statement | Essential conclusion | Status |
|---|---|---|---|
| Theorem 1 | `thm:regret`; `451-470` | `R_T <= 2 sqrt((sigma^2+G^2/lambda) Lambda_T^C S_T)+2E_T`, with all time-varying factors inside `S_T`. | **Pass** |
| Corollary 2 | `cor:operational`; `537-557` | The online `Q`, residual, smoothness, optimizer, CG, and information schedules instantiate every theorem input and permit the observable `Lambda` upper bound. | **Pass** |
| Corollary 3 | `cor:corrected-center`; `773-790` | The corrected center removes the centering certificate. | **Pass** |
| Lemma 4 | `lem:primitive-pred`; `932-1063` | Optimizer residual plus mismatch vector `M_t` controls action-scaled center discrepancy. | **Pass** |
| Lemma 5 | `lem:path-certificates`; `1065-1131` | Welford `Q_t` and observed residual energy give predictable `bar chi_t`, `bar M_t`, `bar psi_t`, and Taylor schedules using `O(d)` state. | **Pass** |
| Corollary 6 | `cor:near-linear`; `1153-1208` | Gives explicit bounded-path rates, the two-sided reduction, and `gamma_T<=hat gamma_T<=A_inf gamma_T`. | **Pass** |
| Corollary 7 | `cor:tanh-link`; `1227-1247` | For scalar tanh, `G=B_phi` and `L_mu=L_g=4B_phi^2/(3sqrt(3))`. | **Pass** |
| Lemma 8 | `lem:whitened`; `1294-1381` | Whitened feature drift gives one-sided transfer and its primitive parameter-drift bound. | **Pass** |
| Corollary 9 | `cor:drift-sandwich`; `1383-1399` | `2chi_t+chi_t^2<1` gives the two-sided feature sandwich. | **Pass** |
| Lemma 10 | `lem:subsample`; `1493-1590` | Matrix Bernstein yields a conservative subsampled-GGN spectral sandwich. | **Pass** |
| Lemma 11 | `lem:dynamic-potential`; `1772-1853` | Exact endpoint/variation determinant identity and the realized-width sum inequality. | **Pass** |
| Lemma 12 | `lem:rank-refresh`; `1874-1908` | Negative-rank plus spectral-floor bounds control variation; endpoint rank and trace control the endpoint determinant. | **Pass** |
| Corollary 13 | `cor:lam-observable`; `1943-1960` | Played-action CG lower accuracy gives an observable termwise upper bound on `Lambda_T^C`. | **Pass** |
| Lemma 14 | `lem:cg`; `1966-2040` | Standard zero-start CG rate and energy-error-to-quadratic-form sandwich. | **Pass** |
| Lemma 15 | `lem:bonus`; `2061-2085` | Uniform all-action CG accuracy sandwiches the computed bonus between confidence and inflated algorithmic widths. | **Pass** |
| Lemma 16 | `lem:confidence`; `2091-2186` | Simultaneous linearized-ridge confidence radius with noise, ridge, and squared-linearization terms. | **Pass** |
| Corollary 17 | `cor:beta-constructive`; `2188-2206` | Any nonnegative predictable `bar F_t>=F_t` gives `bar beta_t>=beta_t`. | **Pass** |
| Corollary 18 | `cor:gammahat`; `2213-2257` | Played-action accuracy proves `hat gamma>=gamma`; uniform candidate accuracy is separately required to invoke Theorem 1. | **Pass** |
| Lemma 19 | `lem:discrepancy`; `2281-2289` | Restates the action-scaled centering assumption. | **Pass; tautological** |
| Proposition 20 | `prop:window`; `2321-2344` | An unrescaled current-parameter subset satisfies `Chat_t<=C_t`, hence `kappa_+=1`. | **Pass** |
| Theorem 21 | `thm:spectral-distortion`; `2355-2395` | Composes approximate-to-full and full-to-frozen one-sided bounds into `u_t=kappa_+(1+bar chi_t)^2`. | **Pass** |
| Proposition 22 | `prop:scalar-invariance`; `2397-2412` | Positive action-independent width scaling is exactly offset by inverse scalar-bonus scaling at a common round; trajectory scope is stated separately. | **Pass** |
| Corollary 23 | `cor:frozen`; `2988-3019` | Frozen linear features recover `Xi_t=0`, `Lambda_T^C=gamma_T`, and the linear-UCB form. | **Pass** |
| Corollary 24 | `cor:worstcase`; `3259-3271` | Uniform maxima reduce Theorem 1 to the looser `sqrt(T Lambda_T^C)` form. | **Pass** |
| Corollary 25 | `cor:twosided`; `3497-3567` | A time-uniform two-sided sandwich gives inflation `sqrt(rho_+^star/rho_-)` and frozen information gain. | **Pass** |
| Lemma 26 | `lem:ggn-approx`; `3578-3604` | A bounded residual-Hessian term converts GGN to a multiplicative Hessian sandwich. | **Pass** |

## Detailed checks

### Main regret formula

For every candidate action, confidence, centering, transfer, and the CG lower
sandwich imply optimism.  At the played action the CG upper sandwich gives

```text
regret_t <= 2 alpha_t omega_t sqrt(u_t(a_t)) s_C,t(a_t)
            + 2 eps_lin(t).
```

Summing first and applying Cauchy--Schwarz once yields

```text
R_T <= 2 sqrt(sum_t alpha_t^2 omega_t^2 u_t(a_t))
           sqrt(sum_t s_C,t^2(a_t)) + 2E_T.
```

Lemma 11 supplies
`sum_t s_C,t^2(a_t)<=(sigma^2+G^2/lambda)Lambda_T^C`.  This is exactly
Theorem 1; no horizon maximum or altered theorem factor was introduced.

### Operational path certificates

The parallel-axis identity gives

```text
Q_t = J_<t +(t-1)||theta_t-bar theta_<t||^2
    = sum_{s<t}||theta_t-theta_s||^2.
```

The explicit `t=1` initialization removes the empty-mean endpoint ambiguity.
With `d_{s,t}=||theta_t-theta_s||`, each mismatch summand is bounded by

```text
L_g |c_s| d_{s,t} +(3/2)G L_g d_{s,t}^2
 +(1/2)L_g^2 d_{s,t}^3.
```

Cauchy--Schwarz and `sum d^3<=(sum d^2)^(3/2)` give the displayed `bar M_t`.
The trust region replaces the cubic sum by `2R Q_t`.  Division by
`sqrt(lambda)` gives `bar psi_t>=psi_t`.  All inputs use rewards only through
round `t-1`; `zeta_t` is explicitly nonnegative and `Hist_t`-measurable.

The Taylor envelope is predictable, so `bar F_t>=F_t`.  Corollary 18 then
correctly combines the transferred played width with the CG lower sandwich to
obtain `hat gamma>=gamma`; it separately retains uniform all-action CG accuracy
for optimism.  Corollary 2 now adopts only Theorem 1's structural hypotheses
and explicitly instantiates its certificate inputs.

### Near-linear and tanh results

Under `||theta_t||,||theta*||<=R`,
`Q_t<=4R^2(t-1)`.  Substitution produces the stated constants in `bar E_T`,
`bar F_{T+1}`, `bar chi_t`, and `bar psi_t`.  The uniform quantity

```text
x_T = 2 c_g R sqrt(T-1)/(sigma sqrt(lambda W))
```

now drives `rho_+=1+(2x_T+x_T^2)` and
`rho_-=1-(2x_T+x_T^2)`.  The CG upper sandwich and inverse lower operator
bound give

```text
hat gamma_T <= alpha_I^2 (rho_+/rho_-) gamma_T.
```

The manuscript correctly keeps ordinary information gain separate: width
scaling controls drift, centering, and Taylor terms but does not imply
sublinear regret without `gamma_T=o(sqrt(T))` along this route.

For scalar tanh, maximizing `2y(1-y^2)` over `y in [0,1]` gives
`4/(3sqrt(3))`; both smoothness constants and `G<=B_phi` are correct.  This
specialization is operational and is not presented as automatically satisfying
the separate `W^{-1/2}` near-linear premise.

### Dynamic potential and refresh rank

The determinant lemma and the definition of `Xi_t` give the exact telescoping
identity.  For each noncanonical transition, at most `r_t` negative eigenvalues
can contribute positively to `-log det(I+Xi_t)`, and the spectral floor bounds
each by `log(1/(1-nu_t))`.

The endpoint bound follows from concavity of `log(1+x)` and the specified
endpoint trace; the proof pads the actual nonzero eigenvalue list with zeros up
to `r_end`.  The frozen-window calculation now defines the deleted vector and
remaining matrix explicitly and charges only `t>m`; its total charge can be
linear in `T`.  The manuscript correctly denies rank-one status to relinearized
windows and denies a logarithmic charge from geometric timing alone.

### Auxiliary proof presentation

Lemma 10 explicitly states `delta in (0,1)` and `1<=n<=m`.  Lemma 14 derives
the zero-start energy-norm rate from the CG minimax property using a scaled
Chebyshev polynomial and then applies the certified condition-number bound.
Corollary 25 explicitly requires the two-sided factors to be predictable and
certified before action selection.

### Certificate probability and scalar invariance

The filtration now conditions randomized certificates on `H_t^-`, before
`Omega_t` is revealed.  Taking expectations gives each unconditional failure
bound, and the allocated double union bound gives
`P(E_cert)>=1-delta_cert`.  The self-normalized event remains separate.

Proposition 22 is exact by substitution at a common round.  Its accompanying
text now requires predictable scaling, common centers and histories,
proportionality at every subsequent common history, and coupled exogenous
randomness before drawing any trajectory or regret conclusion.

## Findings summary

1. **No open correctness blocker.**  Former blockers B1--B4 and the subsequent
   filtration, uniform-drift, endpoint/window, and scalar-scope findings are
   resolved.
2. **No remaining proof-presentation gap.**  The CG derivation, subsampling
   domains, two-sided-factor predictability, padded endpoint eigenvalues, and
   operational-corollary phrasing have all been supplied.
