# Results of the exploratory relative-weight audit

All **600 existing evaluation histories and 600,000 rounds passed** the audit
in 434.736 seconds on four workers. There are 50 seeds per W/behavior cell and
1,000 rounds per seed. No adaptive policy was rerun: the original optimizer was
replayed on each history's fixed recorded actions and selected rewards to
recover the parameters omitted from the raw logs. These are post-outcome
diagnostics, not a held-out evaluation of the new score rules.

The [aggregate](full/analysis.json), [600 per-seed rows](full/per_seed.jsonl),
[hashed input inventory](full/input_inventory.jsonl), and
[definitions/reproduction instructions](README.md) provide the complete record.
The inventory binds 3,005 inputs, totaling 3,724,135,561 bytes. The analyzer's
SHA-256 is `d226b98c4a10f6f1905c2c23556540ab41e062eb27c58ab67efe417f7daccf56`.
Python 3.12.14, NumPy 2.2.3 and SciPy 1.15.2 match the original run; worker BLAS
and OpenMP settings were one thread each. The original source run is complete;
its retained `KeyboardInterrupt` text records the earlier user pause.

## Reconstruction and numerical checks

All 600,000 pre-update norms, post-update norms and optimizer displacements
match the recorded numbers exactly. At 3,600 fixed checkpoints, the largest
direct-versus-category frozen Gram entry difference is 4.093e-12; the largest
corrected-center difference is 6.106e-16, frozen-width difference 3.331e-16,
endpoint-distance difference 2.883e-15, and generalized-eigenvalue difference
1.339e-13. Recomputed current widths match exactly. The largest discrepancy
divided by its original, scale-dependent tolerance is 0.004995. No tolerance
was increased.

The endpoint/category/uniform and width-sandwich checks pass for every round.
The largest literal float excess of frozen width above the asymmetric converted
width is 3.331e-16, explicitly retained rather than clipped. These are ordinary
floating-point diagnostics, not verified enclosures. An independent review also
matched all 2,400 consumed per-trajectory raw/manifest/summary/checksum files to
the previously committed full-study input hashes. The original four-rule
conditional regret summaries and Hessian width-dominance counts reproduce the
earlier independent scan in all 12 cells.

## Width overhead and variation across seeds

The following means use the **Hessian behavior's saved states**: 50 seeds,
50,000 rounds and 250,000 candidate-action widths per row. Each entry is the
effective bonus width divided by the direct frozen width. This measures
conversion overhead, not regret or confidence-radius improvement.

| W | Hessian/Q | Dense endpoint | Category symmetric | Category asymmetric | Uniform endpoint | Direct frozen |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 16 | 6,303.286 | 1.001641 | 1.003326 | 1.002783 | 1.063792 | 1 |
| 1 | 4.409e16 | 1.026386 | 1.055541 | 1.042708 | 2.381921 | 1 |
| 0.25 | 8.475e37 | 1.121320 | 1.331306 | 1.126764 | 14.298405 | 1 |

The maximum symmetric category endpoint certificates on these primary
histories are 0.049865, 0.736105 and 2.427738. The corresponding uniform
certificates are 0.123719, 1.735123 and 5.300011. The inexpensive category
comparison removes most of the Hessian/Q conversion overhead in this model.
Keeping the asymmetric factor helps further; it is not universally ordered
against the symmetric dense endpoint factor. Neither comparison supplies an
interval narrower than the existing frozen interval on the same state.

The earlier width-dominance diagnosis also holds across seeds. Percentages
below summarize each seed's 1,000 rounds; brackets give the minimum and maximum
of the 50 seed fractions, not confidence intervals.

| W | Hessian recommendation equals first current-width maximum | Sufficient strict width dominance |
| ---: | ---: | ---: |
| 16 | 99.382% [98.8%, 99.9%] | 97.104% [92.9%, 98.6%] |
| 1 | 99.962% [99.8%, 100%] | 99.372% [99.1%, 99.6%] |
| 0.25 | 99.982% [99.7%, 100%] | 99.508% [99.3%, 99.6%] |

The exact numerator counts are 49,691 / 49,981 / 49,991 and
48,552 / 49,686 / 49,754, respectively, each with denominator 50,000.
Per-seed quantiles and the same quantities for every candidate score on every
behavior history are retained in the JSON. The sufficient condition concerns
a fixed state's ranking; it does not attribute the adaptive regret gap to a
single cause.

## Symmetric comparison of conditional recommendations

Each entry below is mean **one-step** pseudo-regret after rescoring a behavior's
saved states. H/E/F/N denote Hessian, endpoint, frozen and naive behavior.
Columns H/E/F/N retain the original scores; U/Cs/Ca use uniform, symmetric
category and asymmetric category endpoint factors. Every entry averages 50,000
saved rounds. Only the matching original behavior column is its observed
average regret. Off-diagonal sums are not alternate adaptive-policy outcomes.

| W | Saved behavior | H | E | F | N | U | Cs | Ca |
| ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 16 | H | .185101 | .029032 | .029066 | .029027 | .029524 | .029052 | .029047 |
| 16 | E | .336227 | .152593 | .152155 | .151549 | .207016 | .153968 | .153583 |
| 16 | F | .337046 | .152483 | .151785 | .151323 | .207973 | .153922 | .153540 |
| 16 | N | .336677 | .153759 | .153626 | .152746 | .207575 | .155201 | .154795 |
| 1 | H | .182900 | .049506 | .059206 | .048660 | .086686 | .050706 | .050322 |
| 1 | E | .309781 | .173187 | .173884 | .167143 | .284027 | .179783 | .178043 |
| 1 | F | .311620 | .174602 | .173195 | .169051 | .287655 | .181040 | .178498 |
| 1 | N | .310986 | .179028 | .177323 | .173052 | .286464 | .185739 | .183695 |
| 0.25 | H | .176439 | .101773 | .144606 | .097656 | .168958 | .109173 | .102158 |
| 0.25 | E | .243915 | .172089 | .170811 | .164566 | .240351 | .185030 | .172500 |
| 0.25 | F | .232988 | .175617 | .171876 | .169862 | .229143 | .184080 | .175357 |
| 0.25 | N | .249712 | .180425 | .174521 | .172584 | .246257 | .192599 | .181015 |

All seven score rules satisfy the numerical all-action optimism check on all
600,000 states, including naive current. That observation is neither a
population coverage estimate nor evidence that a correction is necessary.
Different saved behavior histories produce materially different recommendations
and regret values. The table does not identify the effect of changing a policy
throughout learning. W also changes the task, so comparisons across W are not a
controlled causal drift treatment.

The new uniform/symmetric-category/asymmetric-category scores have respectively
2,482 / 2,523 / 2,540 float top-score ties among 600,000 states. Their rankings
change on 8 / 11 / 32 states when written in normalized float form. The audit
uses the smallest-index tie rule and does not recompute exact-real states.
The earlier stored-input Decimal audit is a separate final-score arithmetic
check; neither analysis rules out propagation of a rare early action change.

## Fixed-state costs and go/no-go decision

Across 36 fixed states, the median of the per-state five-batch median call
times is 27.72 microseconds for category ratios with precomputed multipliers,
34.79 microseconds including the 80 current projections, and 213.28
microseconds for the original dense endpoint routine with both metrics
preassembled. The respective state-median ranges are 14.60–30.81,
18.29–37.61 and 107.79–1,469.59 microseconds. Parallel audit load and timing
noise are present. Uniform factors are precomputed constants. These measurements
exclude learning, matrix construction, estimator construction, width solves,
storage and orchestration; they establish no end-to-end speedup.

**No-go for another large adaptive regret study justified solely by these
diagnostics.** The model-specific certificate is a useful mathematical and
mechanistic addition, and its kernel is cheaper than dense endpoint evaluation.
The current implementation already has the frozen estimator and frozen widths,
however. A tighter valid conversion adds no new confidence information beyond
that frozen interval. This is not a theorem ordering policy regret: wider
scores can change rankings and future data, sometimes beneficially. The present
analysis simply supplies no independent empirical basis for predicting an
advantage over the already available frozen policy.

A further computational study would need an explicit application where frozen
width evaluation is costly, honest accounting for the frozen estimator used by
the corrected center, and a prespecified end-to-end cost/accuracy target. A new
statistical study would need a justified new confidence construction; the
existing frozen bound is already vacuous in all three full-study cells, so
conversion tightening alone does not solve that issue. Any new policy selected
using these outcomes needs disjoint development/tuning and fresh evaluation
seeds under a locked protocol, with all failures and negative outcomes retained.
No such adaptive study has been launched.
