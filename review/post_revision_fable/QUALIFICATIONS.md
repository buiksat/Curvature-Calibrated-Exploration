# Source-checked interpretation of the new Fable review

The complete response is retained separately in [review.md](review.md) and
[verbatim_review.json](verbatim_review.json). The corrections below do not alter
it. They distinguish useful revision advice from statements that should not be
transferred into the manuscript.

Sources below refer to the reviewed research snapshot
`5f00be1b537eef476150c3115822f00cd95461ae`, whose scientific manuscript inputs
match main `fb95a696863326345be0823de399937fcbdb8af8`. These are targeted checks,
not a fresh experimental run or a comprehensive independent proof review.

## 1. The mechanism table does not describe every policy's own score

Fable's detailed experimental assessment and final item 5 say that all policies
are width-dominated, and suggest that the regret gap therefore traces to
inflated-radius trajectory divergence. The premise misreads the table.
`paper/transport_followup_appendix.tex:107–121` explicitly says that every row
evaluates the **Hessian score** on the row behavior's states. Different behavior
histories are not different diagnostic score rules.

The full relative-audit artifact contains each rule's own recommendation
statistics. Its own-history width-argmax agreement percentages are:

| Behavior and evaluated score | W=16 | W=1 | W=0.25 |
| --- | ---: | ---: | ---: |
| Hessian | 99.382 | 99.962 | 99.982 |
| Endpoint | 23.644 | 40.628 | 63.768 |
| Frozen reference | 23.204 | 40.286 | 66.938 |
| Naive current | 23.404 | 40.006 | 61.664 |

On Hessian's saved histories, Hessian and naive recommendations agree on only
29.646%, 40.522%, and 60.790% of rounds, respectively. A shared current-width
argmax does not imply matching score argmaxes: the prediction center and bonus
coefficient also matter. No causal decomposition of adaptive regret was
identified by these comparisons. Source:
`review/transport_relative_diagnostics/full/analysis.json`, grouped score-rule
counts, supported by its 600 per-seed records. Fable did not inspect those
per-seed records or the analyzer.

## 2. A width floor is not a policy-performance ceiling

Reject the proposed introduction sentence saying that “no outcome in the other
direction was available to the certificate,” and the stop/go phrase “the floor
already proves the ceiling.” `prop:reference-width-floor` compares widths on
the same history with the stated center/radius/bias and certificate conditions.
It does not prohibit a larger bonus from changing actions beneficially, nor
order adaptive regret on different histories.

The decision not to launch another large study remains reasonable because no
concrete additional statistical information or end-to-end computational benefit
has been established. That is a research-prioritization judgment, not a theorem
that a new policy cannot improve regret.

The review also carries the original grid's five-to-six-order path-certificate
conservatism language into discussion of the new relative-width audit. Keep
those quantities and populations separate: a ratio of distance certificates
is not a ratio of effective widths, and the original grid is not the follow-up.

## 3. The analytic counterexample is useful, but only at its stated level

A valid abstract example is: take D>0, reference metric I, current metric
`diag(exp(D), exp(-D))`, query e1, center and bias zero, and beta>0. The reference
width is one and current width is exp(-D/2). A mean equal to beta lies at the
upper endpoint of the reference confidence band, while the naive current score
is beta*exp(-D/2), strictly smaller.

This illustrates why the reference band alone does not justify replacing its
width by a smaller current width. It is already implicit in the manuscript's
limited-information necessity proposition. It does **not** construct a
realizable scaled-tanh learning trajectory, prove that transport is necessary
in the observed runs, or establish necessity of this particular certificate
family. Calling its absence the one essential scientific hole is the reviewer's
opinion, not a demonstrated flaw in the existing theorem.

The suggestion about exact actionwise transport also needs careful wording:
“Evaluating the displayed ratio as written uses the reference width and supplies
no computational shortcut.” A universal complexity impossibility does not
follow. For example, if V=rho*Vbar with known rho, the exact multiplier is
sqrt(rho), directly available from that structure. The equality characterization
should not be presented as a newly evaluated algorithm.

## 4. Counts, intervals, and proposed numerical additions

**The review's “750 total evaluated trajectories across both studies” is wrong.**
The original grid contains 3 horizons × 4 conditions × 4 policies × 50 seeds =
2,400 trajectories; the follow-up has 3 conditions × 4 policies × 50 seeds =
600. Thus 750 is the combined count *per method*, not the combined total of
3,000. The populations must not be pooled into an independence or coverage claim.

The retained original aggregate explicitly reports optimism for 600 primary
trajectories and 200 T=1000 trajectories for each of three comparators: 1,200
unique original trajectories. Together with the 600 follow-up trajectories,
those retained summaries establish the reported check outcomes for 1,800 unique
method-trajectories. The other 1,200 original short-horizon comparator trajectories
exist in the original grid, but their optimism outcomes cannot be independently
asserted from this retained aggregate without the missing raw evidence. The
paper's scoped statements should remain scoped.

**Context-free comparisons are a useful suggestion and are supported.** The
follow-up's context-free mean-only and best-fixed-action regrets are retained
as environment diagnostics. Hessian and context-free sample means are close:

| W | Hessian | Context-free mean-only |
| --- | ---: | ---: |
| 16 | 185.100601 | 185.255508 |
| 1 | 182.900414 | 183.060480 |
| 0.25 | 176.439138 | 176.672150 |

The W=16 best-fixed-action mean is 180.009575. These are descriptive sample
means, not a tested equivalence claim. Fable flagged that it had not re-opened
this field; the source check here confirms the numbers. Source:
`review/transport_review_followup/full-cce-full-local/aggregate_compact.json`,
`environment_diagnostics[*].context_free_mean_only_regret.mean` and
`best_fixed_action_regret.mean`; match the condition through the recorded
target-label/W mapping rather than treating the target label as realized drift.

**The CI shortcut is inaccurate.** Fable's “10–60× the CI half-width” claim
understates the actual W=16 ratios (about 62.78–71.89); W=1 ratios are about
28.68–34.00. W=0.25 ratios are about 4.23–5.66. These ratios do not make
multiplicity a formally irrelevant issue. Retain the paper's explicit pointwise,
unadjusted qualification and do not replace it with a simultaneous statement.

**The proposed Decimal extension is numerically supported, after checking.**
The paper reports the below-0.629-ULP statement for the 16 primary-history
ranking changes. The independent saved analysis shows that the maximum across
all 65 changes is also 0.6283498985722342. Thus Fable's below-0.63 rewrite can be
supported, even though it did not inspect that source in this review. Preserve
the limitation: this re-evaluates final score arithmetic from stored doubles
and an already rounded coefficient; it does not recompute upstream learning,
solves, exponentials or coefficients, or measure propagation through later
histories. Source: `review/post_full_fable/independent/analysis.json`, stored-input
ranking-mismatch records.

**The proposed misspecification switch does not implement that experiment.**
Fable suggests `exact_realizability:false` with a controlled mismatch or lower
W. The current resolved configuration does not use that declaration as a reward
generator switch; `experiments/transport_instantiation.py:543` generates means
from the teacher model. A misspecification experiment requires an explicit
modified reward generator and valid historical/current error envelopes.
Larger mismatch or smaller W can also enlarge radii and bias bounds, so neither
setting guarantees naive optimism failure. Specify an analytic failure mechanism
first, then a locked protocol and fresh seeds if a test is informative. Do not
search settings until the preferred failure appears. No such run was performed.

## 5. Editorial advice and readiness need judgment

The replacement abstract should not be pasted verbatim. It drops certified
parameter-region and approximation-error qualifications, says ambiguous “exact
transport” instead of “exact actionwise transport,” and omits “pointwise” for
the intervals. Shortening is useful only if those distinctions survive.

The 36-state timing results are a paragraph in the appendix, not a timing table.
Demoting or shortening that paragraph is an editorial choice. The recorded
measurements do not demonstrate end-to-end speedup, but their restricted scope
is already stated. The comparison can remain in the external audit record.
Similarly, removing the assumption ledger is optional; retaining a concise
assumption summary may help readers assess a conditional theorem. Consolidate
repetition without separating critical qualifications from their claims.

The two inactive 2026 bibliography records remain unverified, not disproved.
Pruning them from a submission-only bibliography is an editorial option; no
venue prohibition on unused database entries was established. Verify any
weighted/nonstationary-bandit comparison against primary sources before adding
it, rather than citing an unverified claim until camera-ready.

Fable's favorable “revise, then submit” recommendation is advisory. Narrow model
and teacher coverage and incomplete raw-data availability remain material
scientific scope and reproducibility limits. Anonymous evidence packaging is
still incomplete, and no submission has been made. A completed API response
and the model's “line-by-line verified” wording do not constitute formal proof
certification or independent experimental reproduction.

## 6. Actual coverage takes precedence over self-description

The tool record confirms all 838 theory lines, all 572 proof lines and all five
new tables were returned. It also records partial implementation/configuration
reads and shallow JSON inspection. Fable's prior-review read stopped at line
120 of 130, rather than reaching 130 as its verification section says. The
scientific source read ended at line 359, not 360. More substantively, it did
not inspect the replay analyzer, table generator, full protocol, per-seed audit
or drift/decomposition JSONs. Apparent consistency with an earlier review does
not replace direct inspection in this one. See [source_coverage.json](source_coverage.json)
for every actual call and returned range.
