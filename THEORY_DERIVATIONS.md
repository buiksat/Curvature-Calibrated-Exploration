# Scratch Derivations for the Resubmission

This file records independent constant and edge-case checks for the theorem
changes. It is not a substitute for the formal proofs in `paper/main.tex`.

## Sharpened feature-drift sandwich

Let `n=t-1`, `G,D` be `d x n`, and use the principal inverse square root of
the positive-definite frozen Gram. Define

```text
A = [sqrt(lambda) Cbar^{-1/2}; G^T],
B = [sqrt(lambda) Cbar^{-1/2}; (G+D)^T].
```

Both stacks are `(d+n) x d`. Since

```text
G G^T = I - lambda Cbar^{-1},
```

we have `A^T A=I`. Expanding the replayed Gram gives

```text
B^T B = Cbar^{-1/2} C Cbar^{-1/2}.
```

Only the bottom block changes, so
`||B-A||_op=||D^T||_op=||D||_op=chi`. All `d` singular values of `A` equal
one. Rectangular singular-value perturbation therefore places every singular
value of `B` in `[1-chi,1+chi]`. When `chi<1`, squaring and applying congruence
gives

```text
(1-chi)^2 Cbar <= C <= (1+chi)^2 Cbar.
```

The lower argument is not extended to `chi>=1`: squaring a negative lower
endpoint would be invalid. At `t=1`, `G,D` are `d x 0`, `chi=0`, and both
stacks reduce to `sqrt(lambda) Cbar^{-1/2}=I` because `Cbar=lambda I`.

For a predictable `chi <= bar_chi < 1`, monotonicity yields the usable factors
`(1-bar_chi)^2` and `(1+bar_chi)^2`. Thus the horizon-uniform near-linear
constants are

```text
rho_minus = (1-x_T)^2,
rho_plus  = (1+x_T)^2,
A_inf     = alpha_I^2 ((1+x_T)/(1-x_T))^2,
```

with the sharp admissibility condition `x_T<1`.

## Frozen-potential regret reduction

For exact current curvature, optimism uses
`u_t=(1+bar_chi_t)^2`. The sharpened lower sandwich reverses under inversion:

```text
C_t^{-1} <= (1-bar_chi_t)^{-2} Cbar_t^{-1},
s_t(a) <= bar_s_t(a)/(1-bar_chi_t).
```

The generic per-round argument consequently becomes

```text
regret_t <= 2 alpha_t omega_t
                 ((1+bar_chi_t)/(1-bar_chi_t)) bar_s_t(a_t)
            + 2 epsilon_t.
```

Summing and applying Cauchy--Schwarz once, followed by

```text
sum_t bar_s_t(a_t)^2
  <= (sigma^2+G^2/lambda) gamma_T,
```

gives exactly the time-varying frozen-potential corollary. There is no extra
factor of `T`, `u_t`, or `rho_plus`. The corrected center only replaces
`omega_t` by `bar_beta_t`.

## Spectral-tail log determinant

For `A_T=Cbar_{T+1}-lambda I`, let its descending eigenvalues be `nu_i`, let
`0<=r<=d` be an integer, `r_T=min(r,T)`, and
`Delta_{T,r}=sum_{i>r} nu_i`. The rank-one construction gives
`rank(A_T)<=T`, while bounded features give
`tr(A_T)<=T G^2/sigma^2`.

For `r_T>0`, concavity on the first `r_T` eigenvalues and zero-padding when
`r>T` give

```text
sum_{i<=r} log(1+nu_i/lambda)
  <= r_T log(1 + T G^2/(r_T lambda sigma^2)).
```

For the remaining eigenvalues, `log(1+x)<=x` gives

```text
sum_{i>r} log(1+nu_i/lambda) <= Delta_{T,r}/lambda.
```

The first term is defined as zero, rather than evaluated, when `r_T=0`.
Checks:

- `r=0`: the bound is `gamma_T<=tr(A_T)/lambda`;
- `r>=rank(A_T)`: `Delta_{T,r}=0` and the exact-rank closure is recovered;
- `T=0`: `A_T=0`, so both sides are zero;
- zero gradients: all eigenvalues and both sides are zero.

The head trace cap includes tail mass, so the inequality can be loose but is
valid.

## Online versus terminal spectral information

A realized terminal `Delta_{T,r}` is permitted only in the final pathwise
complexity bound. It is not measurable at earlier action times and must not set
an online confidence radius. Because the deterministic bound holds
simultaneously for the finite set `r=0,...,d`, the terminal report may minimize
over `r` a posteriori; that choice cannot alter past radii, actions, or
eigenspaces. The existing observable `hat_gamma_t` schedule remains valid
without consulting the tail. Alternatively, deterministic or
history-measurable prefix envelopes `bar_Delta_{t,r}` can define an operational
prefix schedule. The pointwise minimum of several valid predictable information
envelopes is also predictable and valid.

The approximate-rank result does not imply a supplied eigenspace. Therefore it
does not inherit the projected `r x r` implementation: full-dimensional CG can
remain necessary when tail directions affect action ordering.

## Corrected-center near-linear closure

On a radius-`R` path with `||theta_star||<=R`,

```text
Q_t <= 4 R^2 (t-1),
bar_chi_t <= 2 c_g R sqrt(t-1)/(sigma sqrt(lambda W)),
bar_epsilon_t <= 2 c_mu R^2/sqrt(W),
bar_F_t <= 4 c_mu^2 R^4 (t-1)/W,
bar_E_T <= 2 c_mu R^2 T/sqrt(W).
```

The corrected center removes `bar_psi_t`, so no optimizer-residual or
collection-residual envelope enters. The condition `x_T<1` requires

```text
W > 4 c_g^2 R^2 (T-1)/(lambda sigma^2),
```

which is linear rather than quadratic in `T`. A predictable information envelope
`G_{t,r}` need not itself be nondecreasing. Define the predictable monotone
closure

```text
G_up(n,r) = max_{0<=j<=n} G_{j,r}.
```

Then `gamma_n <= G_{n,r} <= G_up(n,r)`, and the radius is bounded by

```text
sqrt(G_up(t-1,r)+2 log(1/delta)) + sqrt(lambda) R
  + 2 c_mu R^2 sqrt(t-1)/(sigma sqrt(W)).
```

The running maximum is necessary: the prefix-envelope definition alone permits
`G_{0,r}>G_{T,r}`, so a terminal-only bound does not control every radius.
Substitution into the frozen-potential corollary gives the manuscript's explicit
bound. If `G_up(T,r)=O(r log T)` and `W=Omega(T)` with a constant that keeps
`x_T` below one, the leading product is
`O(r sqrt(T) log T)` and `2 bar_E_T=O(sqrt(T))`.

## Bounded-output residual energy

For `c_s=mu_{theta_s}-mu_star-eta_s`, bounded outputs give
`|mu_{theta_s}-mu_star|<=2 B_mu`. Conditional sub-Gaussianity and a union bound
over `T` rounds yield

```text
|eta_s| <= sigma sqrt(2 log(2T/delta_R))
```

simultaneously with probability at least `1-delta_R`. Therefore

```text
c_s^2 <= 2(2 B_mu)^2
       + 2 sigma^2 [2 log(2T/delta_R)]
       = 8 B_mu^2 + 4 sigma^2 log(2T/delta_R).
```

Summing the first `t-1` terms proves the stated envelope; at `t=1` both sides
are zero. `delta_R` belongs inside the certificate-event allocation, not the
self-normalized confidence failure probability.

## Architecture check and obstruction

For the executed all-weights MLP

```text
f(U,b,V,c;x,a) = v_a^T tanh(Ux+b) + c_a,
```

let `xbar=(x,1)`, `q_i=(U_i,b_i)`, and `z_i=q_i^T xbar`. The Hessian block on
`(q_i,v_{a,i})` is

```text
[[v_{a,i} tanh''(z_i) xbar xbar^T, tanh'(z_i) xbar],
 [tanh'(z_i) xbar^T,                    0]].
```

At `z_i=0` and `v_{a,i}=0`, its operator norm is `||xbar||`, independent of
hidden width. Hence an all-parameter `O(W^-1/2)` Hessian bound is false for the
repository's parameterization. The manuscript consequently treats `W` only as
an abstract near-linearity scale. An explicit `1/sqrt(W)` forward
parameterization would change the optimization coordinates, ridge geometry,
and GGN and is not silently substituted.

## Linear-subclass lower bound

The exact-rank assumptions contain a constant-context linear bandit on the
normalized hypercube `z(a) in {+-1/sqrt(r)}^r`, with parameter coordinates of
order `sqrt(r/T)` and Gaussian noise. For `T` at least order `r^2`, both action
and parameter norms are bounded. Gradients are constant, so `L_mu=L_g=E_T=0`
and `C_t=Cbar_t`. The standard minimax expected-regret lower bound is
`Omega(r sqrt(T))`; this checks only the leading dimension dependence on the
linear exact-rank subclass and says nothing about nonlinear, spectral-tail, or
computational lower bounds.
