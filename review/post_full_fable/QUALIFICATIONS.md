# Corrections and limits of the Fable follow-up

The [original response](review.md) is preserved unchanged. Its central advice is
useful: report the stronger-drift negative study, explain what transporting the
same confidence information can accomplish, and investigate the decision
mechanism before running large benchmarks. Its proposed prose and some research
recommendations require the corrections below.

## 1. A width comparison does not order policy performance

For the existing transport construction, the certified effective width is at
least the frozen width on the **same history, query, center, radius, and bias**.
This follows directly from the two metric comparisons and the solver upper
bound in `transport_theory.tex`, equations `two-way-width-new` and
`solver-interface-new`. With exact current widths and nonzero query, the exact
actionwise multiplier is `frozen_width/current_width`; it reproduces the frozen
score. For zero queries both widths vanish.

The endpoint Thompson-distance multiplier is an action-independent worst-case
factor. Even when computed exactly, it need not reproduce the frozen width for
every action. Distinguish **exact actionwise transport** from this endpoint
oracle. Pointwise score inflation does not imply a ranking of selected-action
reward, future histories, cumulative regret, or computational cost. Delete
Fable's phrase "cannot out-explore-exploit" and avoid the title "Validity Without
Advantage" as a universal conclusion.

For a concrete endpoint counterexample already present in the paper, take
`Vbar=I`, `V=diag(exp(D),exp(-D))`, and `q=e2`, with `D>0`. The exact endpoint
factor gives `exp(d_Th/2)*s(q)=exp(D)>1=bar_s(q)`. Equality in a different
extremal direction does not imply equality for every action.

The stronger necessity statement needs an explicit quantifier: if the sole
information is the stated symmetric confidence interval, its upper endpoint is
admissible, and the center, bias, and positive radius are fixed, a UCB valid for
every admissible mean cannot be below that endpoint. Known reward bounds,
additional statistical constraints, or a different center can change this
argument. A zero radius is a degenerate case. This observation is an elementary
limitation of that information set, not a universal impossibility theorem for
current-curvature algorithms or a novelty claim by itself.

## 2. Distinguish nested bounds from new confidence information

Taking the minimum of the frozen width and its certified transported upper bound
returns the frozen width. Intersecting **genuinely different valid confidence
sets** can improve a bound; it requires establishing both events and accounting
for their joint failure probability. Fable's blanket dismissal of confidence
intersections is too broad. Its generic fallback formula also omits
`sqrt(kappa_plus)`; that omission is harmless in the dense experiment where
`kappa_plus=1`, but not in the abstract approximate-operator setting.

## 3. Scope the mechanism to the implementation

The implemented Hessian policy is current-width scoring with a scalar inflated
exploration coefficient and action-constant bias. This is not the general form
of every transported score with approximate operators or solver widths.
Width-argmax agreement alone can also arise when reward predictions and widths
favor the same action. The independent diagnostic therefore checks a stronger
sufficient condition: the bonus gap between the largest and second-largest
width exceeds the entire range of corrected centers.

Existing-log diagnostics directly measure this mechanism. They still do not
identify how much of the difference in adaptive cumulative regret it causes.
Similarity to a context-free baseline is descriptive, not proof that the policy
literally ignores context. A large terminal bound alone also does not establish
how frequently the per-round inflation was large.
Widths themselves depend on the context and history; "width-dominated" is more
accurate than Fable's "information-blind."

## 4. Correct the proposed abstract before using it

- Replace "instantiate the theorem exactly" with "audit a dense mathematical
  specialization using floating-point diagnostics." Ordinary Cholesky,
  eigenvalue, and quadrature calculations are not verified enclosures.
- The new full study has **600 evaluation trajectories**, plus 24 development
  and 270 tuning trajectories. Do not imply 894 independent evaluation runs.
- Restrict numerical comparisons to the cells and methods actually checked.
  The nine significant paired comparisons belong to the new three-condition
  study; they are pointwise intervals, not simultaneous conclusions.
- Scope original base-component dominance to the old near-linear grid. Report
  the new study's path dominance separately. Changing W changes the task as well
  as drift, so "as drift grows" is not a controlled causal conclusion.
- Delete "this certificate family cannot supply [bound tightness or policy
  performance]." The observed bounds are vacuous and the evaluated policy loses;
  that does not rule out useful bounds or policies in other instances. With
  fixed linear features and exact solves the theorem recovers ordinary UCB.

## 5. Better next research decisions

Fable understates the relevance of base confidence errors in the new study.
Even the frozen policy's own-trajectory bound exceeds the deterministic cap in
every cell. Improving transport does not remove this remaining obstacle. Tighter
statistical and historical-error control therefore remains relevant in the new
regime too.
The reported path contribution also contains the confidence radius, so a valid
radius reduction can reduce that component directly. The implementation already
uses data-dependent log-determinant information gain; it is not a missing fix.

A tighter transport certificate may matter when frozen widths are expensive,
not only literally unavailable. Any computational case must include the cost of
the corrected center, stored history, certificate, and all required solves. The
current experiment demonstrates no such advantage.

The independent note derives a cheap relative-weight certificate specific to
the scaled-tanh model. It improves the available mathematical bound, but it
does not predict an adaptive regret improvement and does not generalize to
arbitrary rotating neural gradients.

Do not automatically run Fable's suggested `W<=0.1` or misspecification stress
cells. Smaller W and added misspecification can enlarge valid radii too, so this
does not ensure a failure of naive optimism. First construct a clear mathematical
example or mechanism, then define a new protocol if an empirical test answers a
remaining question. Do not search evaluation conditions until a preferred
failure appears. In particular, `exact_realizability:false` is not an implemented
misspecification switch: the current environment still generates means from its
teacher model. Such a study needs a changed generator and valid historical and
current error envelopes, not just a configuration edit.
The previous **whole three-condition evaluation** took about
100 minutes locally; Fable's per-cell cost suggestion was not measured.

## 6. Actual review coverage

The [coverage log](source_coverage.json) records exact returned ranges. Fable read
theory lines **1–599 of 722**, implementation lines **1500–1629 of 2496** plus
search matches, and protocol lines **1–200 of 232**. The protocol was not read in
full despite its placement in the review's "Read in full" list. No call read
`transport_proofs.tex`, the study runner, or the follow-up YAML configuration.
JSON inspection was selective; the review did not independently recompute
intervals or examine all per-seed outcomes. Its verdict that the theorem appears
correct must not be described as a complete proof verification.

External literature and the outstanding bibliography entries remain unverified.
The claimed novelty, TMLR fit, and usefulness of the proposed reframing require
substantive scientific judgment and comparison with prior work. An AI reviewer
endorsing the direction does not settle those questions.
