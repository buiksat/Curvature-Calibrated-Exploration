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
an online confidence radius. The existing observable `hat_gamma_t` schedule
remains valid without consulting the tail. Alternatively, a fixed `r` and a
deterministic or history-measurable prefix envelope `bar_Delta_{t,r}` can define
an operational prefix schedule.

The approximate-rank result does not imply a supplied eigenspace. Therefore it
does not inherit the projected `r x r` implementation: full-dimensional CG can
remain necessary when tail directions affect action ordering.
