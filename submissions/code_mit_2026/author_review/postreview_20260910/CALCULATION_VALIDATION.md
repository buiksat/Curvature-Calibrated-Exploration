# Calculation validation

Label for all newly derived empirical material:

**Post-review descriptive analysis of the locked evaluation.**

Command:

```text
python3 author_review/postreview_20260910/calculate_postreview.py
```

Exit status: 0. The deterministic output is `calculations.json`, SHA-256
`4b0d17ce08162eaad168c243c426306e1c024651e0a01bb48e394c352f885841`.

The standard-library script reads scientific inputs with `git show` at
`5718995cae80f34b5b98b464f3d9090758be4871`. It validated six consumed
extracts against the actual `aggregate/index.json` schema, then independently hashed the
77,035,403-byte aggregate to
`0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02`.
It imports no experiment module, runs no experiment, and does not replay the bootstrap.
It also verified all 28 retained numerical cells in the manuscript table against pinned
aggregate extracts.

## Same-trajectory decomposition

| $D_{\rm target}$ | Mean $B_0$ | $100(B_D/B_0-1)$ | $100I/B_D$ | $B_0/(2T)$ | $B_0/\bar R_H$ |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.25 | 10016.382663153612 | 2.050531566434133% | 2.009329628135488% | 5.008191331576806 | 123.58342915963865 |
| 0.5 | 10093.716955391708 | 4.212112966395898% | 4.0418650447612885% | 5.046858477695854 | 122.443743188143 |
| 1 | 10252.498924226129 | 8.890192875433623% | 8.164365073357592% | 5.126249462113065 | 117.79269319224301 |
| 2 | 10556.242952839799 | 19.43625636452535% | 16.273330189791732% | 5.2781214764199 | 112.31373056969217 |

The first percentage uses $B_0$ as denominator and measures uplift. The second uses $B_D$
and measures the path component's share of the full mean RHS. Both are ratios of aggregate
means. The decomposition closure residual is below `3.64e-12` in every condition.

$B_0$ retains the recorded Hessian-policy history, confidence radii, information gain, and
bias. It is an algebraic attribution diagnostic, not a policy rerun or a guarantee for a
policy executed without transport. The mean records cannot establish a per-seed $B_0$
distribution or count trajectories with $B_0>2T$.

## Paired Hessian-minus-naive comparison

| $D_{\rm target}$ | Mean $\Delta$ | Paired SD | Paired SE | Sign-reversed stored 95% interval |
| ---: | ---: | ---: | ---: | --- |
| 0.25 | 2.0461084126570315 | 5.312015140750025 | 0.751232385557991 | [0.5841057013488111, 3.511933768875755] |
| 0.5 | 2.945984831023014 | 4.681694036627014 | 0.6620915201479164 | [1.676612459409258, 4.207852282222003] |
| 1 | 6.941034910841148 | 4.654294462001184 | 0.6582166351440062 | [5.680469619725013, 8.235519009728673] |
| 2 | 12.105988402353873 | 5.7668863179995205 | 0.8155608843578763 | [10.506209898311521, 13.701437775604242] |

All cells have `n=50`; every stored SE equals paired SD divided by `sqrt(50)`. The intervals
are sign reversals of stored comparisonwise intervals, not fresh bootstrap results. These
values and relative percentages remain outside `main.tex` pending author inclusion approval.

## Pooled inflation and near-linearity

The existing `exp(D_Q/2)` medians are 1.0205263637773605, 1.0409388460308655,
1.085454149598788, and 1.1785579103036254. Each pools 50,000 seed-round values. They are
not terminal summaries or independent experimental units.

At `T=1000`, the exact design rule gives:

| $D_{\rm target}$ | $W$ | Exact $1/(3W)$ | Decimal bound |
| ---: | ---: | --- | ---: |
| 0.25 | 2424832 | 1/7274496 | 1.3746656813063063e-7 |
| 0.5 | 606208 | 1/1818624 | 5.498662725225225e-7 |
| 1 | 151552 | 1/454656 | 2.19946509009009e-6 |
| 2 | 37888 | 1/113664 | 8.79786036036036e-6 |

These are analytic design-rule calculations, not estimates. Complete terminal-inflation
quantiles are excluded because packet 02 did not finish the 200-record terminal extraction.
