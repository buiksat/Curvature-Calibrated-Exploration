# Confidence transport derivations

This file derives the theory used by the revised manuscript. It is deliberately
more explicit than the paper. No theorem is promoted to `paper/main.tex` unless
its proof is complete here.

## 1. Objects, timing, and dimensions

At the start of round `t`, let `H_t^-` be the sigma-algebra before any fresh
algorithmic randomization and let `H_t = H_t^- \/ sigma(Omega_t)` include that
randomization but not reward `r_t`. The context, available action domain, score
oracle, representation parameter, query map, centers, bias envelopes, metrics,
solver outputs, and certificate budgets used to choose `a_t` are `H_t`-measurable.
The reward noise is revealed only after the action is selected.

For a parameter dimension `d`:

- `bar V_t in S_{++}^d` is the predictable sequential reference metric;
- `V_t in S_{++}^d` is the exact current relinearized metric;
- `C_t in S_{++}^d` is the algorithmic approximate metric;
- `q_t(a) in R^d` is the prediction query;
- `bar s_t(a)^2 = q_t(a)^T bar V_t^{-1} q_t(a)`;
- `s_t(a)^2 = q_t(a)^T V_t^{-1} q_t(a)`;
- `s_{C,t}(a)^2 = q_t(a)^T C_t^{-1} q_t(a)`;
- `hat s_t(a)` is a certified solver-produced upper width.

The reference metric updates sequentially:

```text
bar V_1 = lambda I_d,
bar V_{t+1} = bar V_t + sigma^{-2} q_t(a_t) q_t(a_t)^T.
```

The associated frozen information gain is

```text
gamma_T = log det(bar V_{T+1}) / det(bar V_1)
        = sum_t log(1 + sigma^{-2} bar s_t(a_t)^2).
```

For a general action space, regret is defined against a supremum:

```text
reg_t = sup_{a in A_t} mu_t^*(a) - mu_t^*(a_t),
R_T = sum_t reg_t.
```

No maximizing action needs to exist. The theorem assumes that the displayed
suprema are measurable and finite and that a measurable approximate score
oracle exists. Finite enumeration with a deterministic tie rule is a special
case.

## 2. Logarithmic transport along an SPD path

### Lemma 1: logarithmic SPD path comparison

Let `V:[0,1] -> S_{++}^d` be entrywise absolutely continuous and define

```text
D(V) = integral_0^1 ||V(tau)^{-1/2} Vdot(tau) V(tau)^{-1/2}||_op d tau.
```

Then

```text
exp(-D(V)) V(0) <= V(1) <= exp(D(V)) V(0).
```

Proof. Fix nonzero `v` and set `f_v(tau)=v^T V(tau)v`. Continuity and positive
definiteness on a compact interval imply that `f_v` is absolutely continuous
and bounded away from zero. For almost every `tau`,

```text
d/dtau log f_v(tau) = v^T Vdot(tau) v / (v^T V(tau) v).
```

With `y=V(tau)^{1/2}v`, the absolute value of this derivative is at most
`||V^{-1/2} Vdot V^{-1/2}||_op`. Integration gives

```text
exp(-D) v^T V(0)v <= v^T V(1)v <= exp(D) v^T V(0)v.
```

Since this holds for every `v`, it is exactly the Loewner sandwich. Inversion
reverses Loewner order and gives, for every query `q`,

```text
exp(-D) q^T V(0)^{-1}q
  <= q^T V(1)^{-1}q
  <= exp(D) q^T V(0)^{-1}q.
```

The proof does not assume commutativity, simultaneous diagonalization, or
`D<1`. Absolute continuity is sufficient and is preferable to a `C^1`
assumption because a globally Lipschitz Jacobian is differentiable only almost
everywhere.

### Lemma 2: rectangular factor-path certificate

Let `B:[0,1] -> R^{m x d}` be absolutely continuous and

```text
V(tau) = lambda I_d + B(tau)^T B(tau),  lambda > 0.
```

Then

```text
D(V) <= 2 integral_0^1 ||Bdot(tau) V(tau)^{-1/2}||_op d tau.
```

Proof. Almost everywhere,

```text
Vdot = Bdot^T B + B^T Bdot.
```

Put `E=Bdot V^{-1/2}` and `G=B V^{-1/2}`. The normalized derivative is
`E^T G + G^T E`. Moreover,

```text
G^T G = V^{-1/2} B^T B V^{-1/2} = I - lambda V^{-1} <= I,
```

so `||G||_op<=1`. Hence the normalized speed is at most `2||E||_op`.
Integrating and applying Lemma 1 proves the result. The dimensions are
`E,G in R^{m x d}` and `E^T G+G^T E in R^{d x d}`.

An equivalent coordinate-free sufficient condition is

```text
Bdot(tau)^T Bdot(tau) <= nu_t(tau)^2 V(tau).
```

Congruence by `V^{-1/2}` shows that this is equivalent to
`||Bdot V^{-1/2}||_op<=nu_t`. It gives

```text
D(V) <= 2 integral_0^1 nu_t(tau) d tau.
```

This condition needs neither a fixed tangent subspace nor known rank. Excitation
already present in `V(tau)` can make the relative speed small even when the
ridge-only estimate `V^{-1}<=lambda^{-1}I` is loose.

### Corollary 3: Hessian certificate for scalar means

Let `z_s=(x_s,a_s)`, define

```text
theta_{s,t}(tau) = theta_s + tau(theta_t-theta_s),
B_t(tau) = sigma^{-1} [grad mu_{theta_{1,t}(tau)}(z_1)^T; ...;
                       grad mu_{theta_{t-1,t}(tau)}(z_{t-1})^T],
V_t(tau) = lambda I + B_t(tau)^T B_t(tau).
```

Then `V_t(0)=bar V_t` and `V_t(1)=V_t`. If
`||nabla^2 mu_theta(z)||_op<=L_g` on the line segments, set

```text
Q_t = sum_{s<t} ||theta_t-theta_s||_2^2.
```

The `s`th row derivative is

```text
sigma^{-1} [nabla^2 mu_{theta_{s,t}(tau)}(z_s)
             (theta_t-theta_s)]^T.
```

Therefore `||Bdot_t||_F^2 <= L_g^2 Q_t/sigma^2`, so

```text
D_t <= 2 L_g sqrt(Q_t) / (sigma sqrt(lambda)).
```

No smallness assumption is used. At `t=1`, the factor has zero rows, `Q_1=0`,
and both metrics equal `lambda I`.

### Vector outputs and weighted Fisher factors

For output dimension `p_s`, let `J_s(theta) in R^{p_s x d}` and
`W_s(theta) in S_+^{p_s}`. Supply a factor
`R_s(theta) in R^{r_s x p_s}` with `R_s^T R_s=W_s`. Then

```text
B_s(theta)=R_s(theta)J_s(theta) in R^{r_s x d},
B(theta) in R^{(sum_s r_s) x d},
lambda I+B^T B = lambda I + sum_s J_s^T W_s J_s.
```

Along an absolutely continuous path,

```text
Bdot_s = Rdot_s J_s + R_s Jdot_s.
```

The factor-path lemma applies if this complete derivative has a finite relative
bound. A Hessian bound on the prediction map controls only `Jdot_s`; it does
not control path-dependent Fisher weights. For singular or rank-changing
weights, differentiability of the principal square root cannot be assumed. The
theorem therefore requires an explicit absolutely continuous factor. This
geometric statement alone is not an exponential-family confidence theorem.

## 3. Current, reference, and algorithmic width comparisons

Suppose a certified path satisfies `D_t<=bar D_t` and a two-sided operator
certificate satisfies

```text
kappa_{-,t} V_t <= C_t <= kappa_{+,t} V_t,
0 < kappa_{-,t} <= kappa_{+,t} < infinity.
```

Inverting each inequality in the correct direction yields

```text
bar s_t(a)^2 <= exp(bar D_t) s_t(a)^2,
s_t(a)^2 <= exp(bar D_t) bar s_t(a)^2,
s_t(a)^2 <= kappa_{+,t} s_{C,t}(a)^2,
s_{C,t}(a)^2 <= kappa_{-,t}^{-1} s_t(a)^2.
```

Consequently,

```text
bar s_t(a)^2
  <= exp(bar D_t) kappa_{+,t} s_{C,t}(a)^2,
s_{C,t}(a)^2
  <= exp(bar D_t) kappa_{-,t}^{-1} bar s_t(a)^2.
```

Exact current curvature is `kappa_-=kappa_+=1`. A nontrivial operational
approximate-operator certificate is

```text
||V_t^{-1/2}(C_t-V_t)V_t^{-1/2}||_op <= epsilon_t < 1,
```

which gives `kappa_-=1-epsilon_t` and `kappa_+=1+epsilon_t`. An upper
comparison alone does not imply the lower comparison.

## 4. Generic certified solver interface

The score theorem assumes

```text
s_{C,t}(a) <= hat s_t(a)                  for every scored action,
hat s_t(a_t) <= alpha_t s_{C,t}(a_t)      at the played action,
alpha_t >= 1.
```

All-action upper validity supplies optimism. Only played-action sharpness is
needed for regret. For an uncountable action domain, the upper-validity event
must already hold simultaneously over the domain; pointwise failure bounds
cannot be union-bounded.

### Exact-arithmetic inverse-quadratic certificate

Let `C=C^T >= lambda_C I`, solve `Cu=q` approximately by `utilde`, and recompute
the original residual `r=q-C utilde`. Exact algebra gives

```text
q^T C^{-1}q
  = q^T utilde + utilde^T r + r^T C^{-1}r.
```

Therefore

```text
L = q^T utilde + utilde^T r,
U = L + ||r||_2^2/lambda_C
```

enclose the inverse quadratic form. Set `hat s=sqrt(max(0,U))`. If the played
lower endpoint is positive, an observable sharpness factor is

```text
alpha_t = sqrt(U_t(a_t) / max(0,L_t(a_t))).
```

If `L=0<U`, this multiplicative interface has no finite sharpness certificate;
the algorithm may continue the solve or use an additive-width theorem. For a
zero query, require `hat s=0` and skip the solve. CG and PCG may instantiate
this interface, but a preconditioned recurrence must still recompute the
residual of the original operator. These are exact-arithmetic claims. A
floating-point implementation needs verified interval arithmetic or a separate
engineering safeguard; an ordinary float64 point residual is not a proof.

For the standard CG/PCG relative-energy interface, let `u=C^{-1}q` and suppose

```text
||u-utilde||_C <= epsilon ||u||_C,  epsilon<1.
```

Because `q^T u=||u||_C^2=s_C^2`, Cauchy-Schwarz in the original `C` metric
gives

```text
|q^T utilde-s_C^2|
 = |<u,utilde-u>_C|
 <= epsilon s_C^2.
```

Thus `(1-epsilon)s_C^2 <= q^T utilde <= (1+epsilon)s_C^2`. The choices

```text
hat s = sqrt(q^T utilde/(1-epsilon)),
alpha = sqrt((1+epsilon)/(1-epsilon))
```

instantiate upper validity and played-action sharpness. PCG changes the
recurrence, not this proof; its certificate must be expressed in the original
operator energy norm.

## 5. Abstract transported-UCB theorem

Assume the uniform reference-metric confidence event

```text
|mu_t^*(a)-m_t(a)| <= beta_t bar s_t(a)+b_t(a)
```

for every action in the score domain, where `beta_t` and the nonnegative
action-dependent `b_t(a)` are predictable. Define

```text
U_t(a) = m_t(a)
       + beta_t exp(bar D_t/2) sqrt(kappa_{+,t}) hat s_t(a)
       + b_t(a).
```

Let a measurable oracle return `a_t` satisfying

```text
U_t(a_t) >= sup_a U_t(a) - xi_t,
```

with predictable `xi_t>=0`.

### Instantaneous bound

For every action,

```text
mu_t^*(a)
 <= m_t(a)+beta_t bar s_t(a)+b_t(a)
 <= U_t(a),
```

by path transport, the upper operator comparison, and solver upper validity.
Taking suprema and applying the approximate score oracle gives

```text
sup_a mu_t^*(a) <= U_t(a_t)+xi_t.
```

At the played action, lower confidence gives

```text
m_t(a_t)-mu_t^*(a_t)
 <= beta_t bar s_t(a_t)+b_t(a_t).
```

Hence

```text
reg_t <= beta_t bar s_t(a_t)
     + beta_t exp(bar D_t/2) sqrt(kappa_+) hat s_t(a_t)
     + 2 b_t(a_t) + xi_t.
```

Played-action sharpness, the lower operator comparison, and transport back to
the frozen metric give the sharp coefficient

```text
reg_t <= beta_t [1 + alpha_t exp(bar D_t)
                    sqrt(kappa_+/kappa_-)] bar s_t(a_t)
       + 2 b_t(a_t) + xi_t.
```

Because `bar D_t>=0`, `alpha_t>=1`, and `kappa_+/kappa_->=1`, the simpler
but looser form is

```text
reg_t <= 2 alpha_t beta_t exp(bar D_t)
             sqrt(kappa_+/kappa_-) bar s_t(a_t)
       + 2 b_t(a_t) + xi_t.
```

The model-bias envelope is counted twice: once because it appears in the
optimistic score and once in lower confidence at the played action. The oracle
error appears once.

### Frozen-potential closure

If `||q_t(a)||<=G`, then `bar s_t(a_t)^2<=G^2/lambda`. Set
`x_t=sigma^{-2}bar s_t(a_t)^2`. For
`0<=x_t<=G^2/(lambda sigma^2)`,

```text
x_t <= [1+G^2/(lambda sigma^2)] log(1+x_t).
```

Thus

```text
sum_t bar s_t(a_t)^2
 <= (sigma^2+G^2/lambda) gamma_T.
```

One Cauchy-Schwarz application gives

```text
R_T <= sqrt{(sigma^2+G^2/lambda) gamma_T
            sum_t beta_t^2
              [1+alpha_t exp(bar D_t)
                 sqrt(kappa_+/kappa_-)]^2}
       + 2 sum_t b_t(a_t) + sum_t xi_t.
```

The requested display follows as the looser corollary

```text
R_T <= 2 sqrt{(sigma^2+G^2/lambda) gamma_T
              sum_t alpha_t^2 beta_t^2
                exp(2 bar D_t) kappa_+/kappa_-}
       + 2 sum_t b_t(a_t) + sum_t xi_t.
```

No uncontrolled dynamic-width term remains.

For a finite action set, choose the score maximum with a deterministic tie
rule. The maximum and selector are measurable, the supremum is attained, and
`xi_t=0`. The abstract theorem then specializes to exact full enumeration; it
is not an assumption of the headline result.

### Randomized certificate allocation

For each certificate source `j`, it suffices that, before drawing its random
object,

```text
P(E_{j,t}^c | H_t^-) <= delta_{j,t},
sum_{j,t} delta_{j,t} <= delta_cert almost surely.
```

The budgets may be predictable and random. Independence is unnecessary. The
tower property and a union bound give simultaneous certificate probability at
least `1-delta_cert`. A sharpness check applied after action selection must be
deterministically verified at the played action, uniformly valid, or based on
fresh post-selection randomness with the correct conditioning.

## 6. Corrected-center differentiable-model confidence

Fix a reference parameter `theta^circ` with `||theta^circ||<=S` and allow
approximate realizability

```text
mu^*(z) = mu_{theta^circ}(z) + m^circ(z),
|m^circ(z)| <= epsilon_mis(z).
```

The predictable representation sequence `theta_t` is arbitrary inside a
certified convex region. Take `sigma>0` and condition the sub-Gaussian noise
bound on the pre-reward sigma-algebra after action selection. Every historical
or current linearization and misspecification envelope used at round `t` is
deterministic or pre-reward measurable. Fix `delta in (0,1)`, define the
collection-time query `q_s=grad mu_{theta_s}(z_s)`, and use pseudo-response

```text
y_s = r_s - mu_{theta_s}(z_s) + q_s^T theta_s.
```

Taylor expansion around `theta_s` gives

```text
y_s = q_s^T theta^circ + eta_s + e_s,
e_s = rho_s^circ + m^circ(z_s),
|e_s| <= epsilon_lin(s)+epsilon_mis(s).
```

Define the frozen ridge estimator

```text
hat theta_t^lin
 = bar V_t^{-1} sigma^{-2} sum_{s<t} q_s y_s.
```

Let `Phi_t=[q_1/sigma,...,q_{t-1}/sigma]`. Since
`bar V_t=lambda I+Phi_t Phi_t^T`,

```text
Phi_t^T bar V_t^{-1} Phi_t <= I.
```

The deterministic historical bias therefore satisfies

```text
||sigma^{-2} sum q_s e_s||_{bar V_t^{-1}}
 = sigma^{-1} ||Phi_t e||_{bar V_t^{-1}}
 <= sigma^{-1} sqrt(sum e_s^2).
```

Combining this with the standard self-normalized noise bound and ridge bias
gives, simultaneously over rounds, a valid radius of the form

```text
beta_t = sqrt(gamma_{t-1}+2 log(1/delta))
       + sqrt(lambda) S
       + sigma^{-1} sqrt(sum_{s<t}
           [epsilon_lin(s)+epsilon_mis(s)]^2).
```

Use the corrected center

```text
m_t^corr(a) = mu_{theta_t}(x_t,a)
            + q_t(a)^T(hat theta_t^lin-theta_t).
```

Direct algebra gives

```text
mu_t^*(a)-m_t^corr(a)
 = q_t(a)^T(theta^circ-hat theta_t^lin)
   + rho_t^circ(a) + m^circ(x_t,a).
```

Thus the abstract confidence condition holds with

```text
b_t(a)=epsilon_lin,t(a)+epsilon_mis,t(a).
```

No exact ERM, stationarity residual, optimizer rate, or relationship between
`theta_t` and `hat theta_t^lin` is used. The representation parameter only
needs to be predictable and remain inside the certified smoothness region.

Exact realizability is recovered by setting every misspecification envelope to
zero. Fixed nonvanishing misspecification generally makes both the historical
radius and the current additive term grow too quickly for a sublinear result;
this is graceful degradation, not a robust misspecified-bandit theorem.

## 7. Finite-dimensional rate and sanity reductions

With `r_T=min(d,T)` and `||q_t(a)||<=G`, trace-rank concavity gives

```text
gamma_T <= r_T log(1 + T G^2/(r_T lambda sigma^2)).
```

If `bar D_t<=D`, `alpha_t<=alpha`, and
`kappa_{+,t}/kappa_{-,t}<=Kappa`, then

```text
R_T <= 2 alpha exp(D) sqrt(Kappa) beta_T
       sqrt{(sigma^2+G^2/lambda) T gamma_T}
       + 2 sum_t b_t(a_t) + sum_t xi_t.
```

When historical deterministic bias is absent and problem constants are fixed,
`beta_T=O(sqrt(d log T))` and `gamma_T=O(d log T)`, giving

```text
R_T = O(exp(D) sqrt(Kappa) d sqrt(T) log T)
```

plus cumulative linearization, misspecification, and oracle errors.

Sanity reductions:

1. A frozen linear model has `D=0` and zero linearization error.
2. Exact current curvature has `kappa_-=kappa_+=1`.
3. Exact linear solves have `alpha=1`.
4. Exact score maximization has `xi_t=0`.
5. Combining all four gives the standard LinUCB determinant-potential bound.

For the local additive alternative, suppose

```text
(1-chi_t)^2 bar V_t <= V_t <= (1+chi_t)^2 bar V_t,
chi_t<1.
```

Inversion gives `bar s_t <= (1+chi_t)s_t` and
`s_t <= (1-chi_t)^{-1}bar s_t`. Use score multiplier `1+chi_t` in place of
`exp(bar D_t/2)`. Repeating the abstract proof yields the coefficient

```text
1 + alpha_t [(1+chi_t)/(1-chi_t)]
    sqrt(kappa_{+,t}/kappa_{-,t})
```

on the played frozen width, followed by the same Cauchy-Schwarz and frozen
potential step. The logarithmic two-way factor is `exp(bar D_t)`; the local
factor is `(1+chi_t)/(1-chi_t)`. Neither uniformly dominates numerically
because the certificates summarize different paths.

## 8. Dependency graph

```text
self-normalized frozen confidence ----+
                                      +--> corrected-center confidence
historical bias contraction ----------+                |
                                                       v
SPD path lemma --> factor path --> width transport --> transported-UCB
                              |                         |
Hessian/Q_t certificate ------+                         v
operator two-sided certificate -----------------> frozen potential
solver upper + played sharpness -----------------------+
                                                       |
rank/trace log-det closure ----------------------------+--> finite-d rate
```

The old one-sided dynamic theorem is not implied by this graph because it does
not require a lower operator comparison. It remains a fallback result. The new
closed theorem is stronger for exact-current and certified two-sided operators,
but it is not a strict superset of the old theorem.

## 9. Adversarial proof audit

- **Rotating rank-one gradients.** Pairwise endpoint gradients need not be
  collinear and an additive endpoint lower sandwich can fail. Damping keeps the
  path SPD, and Lemma 1 remains valid because it integrates normalized metric
  speed rather than matching individual gradient directions.
- **Ill-conditioned metrics.** For
  `V(tau)=R(theta(tau)) diag(a,b) R(theta(tau))^T`, the normalized speed is
  `|theta_dot||a-b|/sqrt(ab)`. The theorem remains correct but the certificate
  can be large and vacuous.
- **Large finite path length.** The result remains valid for `D>=1`; a finite
  exponential factor is not automatically meaningful.
- **Small lower operator factor.** As `kappa_-` approaches zero, the regret
  factor diverges. This is expected: an upper-only surrogate cannot close the
  frozen potential.
- **Bias accounting.** `b_t(a_t)` enters twice and `xi_t` once. Reversing either
  count breaks the instantaneous inequality.
- **Played-action sharpness.** It is sufficient because only the selected
  score is expanded after approximate maximization. Upper solver validity must
  still hold for every action considered by the oracle.
- **Zero query.** Every exact width is zero. A finite multiplicative sharpness
  certificate forces the reported upper width to be zero.
- **Empty history.** At `t=1`, all three exact/reference GGN metrics reduce to
  their damped priors when the approximate operator is exact; `gamma_0=0` and
  the path length is zero.
- **Weighted factors.** `R_s J_s` has shape `r_s x d`; both `Rdot_s J_s` and
  `R_s Jdot_s` have the same shape. Omitting either term is invalid.
- **Spectral floor.** A uniform positive floor is essential. Positive damping
  supplies it automatically. With zero damping, the path lemma applies only if
  the factor Gram remains uniformly positive definite along the entire path.
