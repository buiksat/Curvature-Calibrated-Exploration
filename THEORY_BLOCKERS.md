# Theory Blockers

Audit date: 2026-07-21

## Current status

There is no known formal-correctness blocker in a theorem currently stated in
the manuscript.  The new rank information-gain closure, rank-closed
near-linear corollary, growing-window theorem (including its burn-in charge),
and off-diagonal witness were independently checked after implementation.

The stronger proposed exact-current stable-excitation theorem is deliberately
not in the manuscript.  Its complete proof was not finished: in particular,
the constrained approximate-minimizer version still needs a line-by-line
normal-cone treatment for the distance and path-stability arguments, followed
by a time-uniform vector-martingale allocation whose constants are propagated
through `Q_t`, `E_T`, `F_T`, and the refresh series.  The individual candidate
inequalities are plausible, but a sketch is not a theorem.  No rate or
experiment claim relies on that omitted result.

The completed fallback is nontrivial: the exact current-relinearized GGN has
an explicit sublinear rate under a supplied fixed tangent-rank bound and the
existing bounded near-linear path assumptions, while the current-parameter
growing window has a closed rate under a supplied persistent-excitation floor.

## Resolved blockers

### Former B1: observable confidence schedule

Resolved at `paper/main.tex:2213-2257` (`cor:gammahat`, rendered Corollary 18).
The corollary now:

- assumes a nonnegative predictable `bar F_t>=F_t`;
- proves that played-action CG accuracy is enough for
  `hat gamma_{t-1}>=gamma_{t-1}`; and
- invokes Theorem 1 only under uniform pre-selection CG accuracy over every
  candidate action.

The operational choice of `bar F_t` is supplied by Lemma 5.

### Former B2: certificate event and failure allocation

Resolved at `paper/main.tex:2552-2621`.  The filtration now distinguishes the
pre-draw history

```text
H_t^- = F_{t-1} join sigma(x_t,A_t)
```

from `Hist_t`, which also contains the pre-action random draw `Omega_t`.
Randomized certificate events satisfy conditional bounds given `H_t^-`, their
failure budgets sum to `delta_cert`, and the tower property plus a union bound
gives `P(E_cert)>=1-delta_cert`.  This avoids conditioning a sketch/subsample
event on a sigma algebra that already reveals its own random draw.

### Former B3: near-linearity and ordinary information gain

Resolved at `paper/main.tex:1153-1225`.  Corollary 6 proves

```text
gamma_T <= hat gamma_T
        <= alpha_I^2 (rho_+/rho_-) gamma_T,
```

uses the uniform path bound `x_T`, retains the complete width thresholds, and
states that width scaling does not control `gamma_T`.  The main text explicitly
requires `gamma_T=o(sqrt(T))` for the stated sublinear route.  Corollary 7 gives
the exact scalar-tanh constants `4 B_phi^2/(3 sqrt(3))` without claiming that
they decay with network width absent a separate parameterization assumption.

### Former B4: refresh timing and rank

Resolved at `paper/main.tex:1880-1941` (Lemma 12 and its consequences).  The
bound assumes both negative rank and a normalized spectral floor.  It defines
the endpoint weight separately, treats frozen-feature window deletion only
after warm-up, and states that relinearized windows and held-stale operators are
not rank-one canonical updates.  Geometric timing is claimed useful only when
the rank and spectral-floor hypotheses also hold.

### Other integration fixes

- Lemma 5 defines the `t=1` Welford initialization and makes `zeta_t`
  pre-action measurable.
- The near-linear main-text sandwich uses `x_T`, defines
  `omega_max,T^op`, and assumes `P_T>=1`.
- The rank endpoint uses `W_end`; the window charge defines its deleted vector
  and remaining-window matrix.
- Proposition 22 is explicitly roundwise and makes no trajectory/regret claim
  without common histories, centers, optimization, predictable scaling, and
  coupled exogenous randomness.

## Proof-presentation recheck

The five formerly nonblocking items are resolved in the current manuscript:

- Lemma 14 derives the zero-start CG energy-norm rate from the minimax property
  with a scaled Chebyshev polynomial (`paper/main.tex:2021-2028`).
- Lemma 10 states `delta in (0,1)` and `1<=n<=m` explicitly
  (`paper/main.tex:1493-1501`).
- Corollary 25 requires predictable two-sided factors certified before action
  selection (`paper/main.tex:3497-3507`).
- Lemma 12 pads the actual nonzero endpoint eigenvalues with zeros through
  `r_end` before applying concavity (`paper/main.tex:1894-1907`).
- Corollary 2 adopts the theorem's structural hypotheses while explicitly
  instantiating its certificate inputs (`paper/main.tex:537-545`).

No proof-presentation item remains open from this audit.
