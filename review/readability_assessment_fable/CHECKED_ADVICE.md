# Readability feedback checked against the manuscript

Fable's fresh assessment finds the current main story understandable for an ML
reader new to confidence transport. It recommends targeted edits, with the
formal protocol and timing block as the largest remaining obstacle. That is an
advisory reading judgment, not evidence that every reader will understand the
paper. The author's concern remains the reason to improve the teaching sequence.

The complete response is preserved unchanged in [review.md](review.md). The
priorities and qualifications below are our assessment of that response, not
additional statements from Fable. This review round changes no manuscript,
experiment, figure, verification code or release artifact.

## Most useful next edits

1. **Make the route through the formal protocol explicit.** Before
   `paper/transport_theory.tex:114`, explain the order of a decision round and
   tell finite-action readers which general-action-space details they can skim.
   Keep the distinction between predictable quantities and quantities that use
   fresh pre-reward randomness. Point to the finite-enumeration corollary without
   implying that enumeration supplies the statistical or certificate assumptions.
2. **Explain the bound magnitudes in prose.** The existing chart coordinates
   support saying that Hessian's *mean terminal bound divided by the cap* has
   base-ten logarithms approximately 9.51, 37.19 and 80.91 across the three
   conditions. The frozen policy's corresponding mean ratios are approximately
   19, 60 and 231. Each mean uses that policy's own 50 histories. This would make
   the scale of vacuity concrete without requiring readers to decode the plot.
3. **Remove an overloaded chart label.** In
   `paper/figures/transport_explanatory_outcomes.tex:28` and the repeated panels,
   “Hessian: reference” means the comparison's zero baseline, while “Frozen
   reference” names another policy. “Hessian = 0” would remove that ambiguity.
   The file is generated: a future edit should change the generator and regenerate
   its outputs, with the existing numeric and packaging checks updated accordingly.

Fable also suggests a compact symbol table, a clearer account of why directly
evaluating the exact width ratio offers no computational shortcut, a short gloss
for Thompson–Finsler geometry, consistent use of regret/pseudo-regret, and removal
of repeated qualifications where their scope remains clear. These are useful
local candidates, not a reason to rewrite all the formal results again.

Our independent reading also identified an abstract that still stacks unfamiliar
terms, an early “path certificate” mention whose auxiliary-path meaning is
explained much later, and policy/category descriptions that could use local
glosses for readers skipping theory. These observations were made separately
from Fable's response.

## Qualifications before adopting Fable's proposed wording

**The empirical replacement is not safe to paste verbatim.** The six plotted
coordinates are logarithms of arithmetic mean terminal bounds divided by the
condition's deterministic cap. Fable's phrase that all 150 frozen trajectories
exceed their caps “by factors of roughly” the plotted range can be read as a
per-trajectory statement. Those factors concern means, not each trajectory.
Likewise, the statement that the bound exceeds the cap by nine orders of
magnitude must explicitly refer to the mean. The existing separate statement
that every individual bound exceeds its cap remains valid at its recorded scope.
Name the condition as `W = 16` rather than calling it the “mildest” condition;
the conditions change the reward task as well as curvature.

Fable's sentence that the cross-policy gap “shows that transport inflation adds
many orders of magnitude on top of an already-vacuous reference bound” conflates
different adaptive histories. The chart compares two policies' own-history means;
it is not a decomposition of the Hessian policy's bound using the frozen policy's
bound as its base. The existing decomposition establishes path-inflation dominance
within the Hessian bound. Keep these two findings separate; an adjacent caveat
does not repair an incorrectly attributed comparison.

**The near-linear regime needs asymptotic wording.** `W = Omega(T)` in
`paper/transport_theory.tex:931` describes a scaling family with a sufficiently
large problem-dependent constant. It is not a numerical pass/fail criterion at
the single horizon `T = 1000`. A safe bridge would explain that the corollary
studies a near-linearity scale growing with the horizon, while the experiment
evaluates the specified fixed values of `W`. It should neither infer a failed
theorem condition from the values alone nor attribute the observed cross-condition
differences solely to curvature.

**Finite enumeration does not discharge every assumption.** The corollary at
`paper/transport_theory.tex:434` concerns measurable finite action lists, selector
measurability, finite maxima/intersections and zero score-oracle tolerance under
the stated setup. The proposed phrase “satisfies every requirement” is too broad
if it includes confidence, noise, matrix or solver certificates. A skim note
should be limited to the general action-space measurability and selection details.

**Keep the original endpoint qualification.** Fable's theory replacement says
an exact scalar endpoint distance yields a worst-direction multiplier “not the
actionwise equality.” The original says “not necessarily the actionwise
equality,” which permits equality in special cases. Preserve that qualifier.
The exact ratio needs the reference width as written; this is not a general
computational lower bound.
The replacement should also preserve “can change” for extra information about
the mean, rather than asserting that it always changes the uncertainty set.
If it restates the exact width ratio, retain the zero-query case from the
existing piecewise definition; referring to that equation is simpler and safer.

**Do not invent a frequency or a motivation result.** Fable's suggested
motivation says the current metric “often produces” a smaller width. This review
does not establish that frequency. A hypothetical explanation of why a current
matrix might appear attractive can be useful, but it must not imply observed
frequency, improved calibration, or a certified uncertainty advantage.

**Simplify the abstract further if changing it.** Fable's replacement clarifies
the antecedent of “this requires,” but its first sentence still combines the
construction, optimizer independence, predictable path, region and two error
envelopes. Shorter connected sentences and a local explanation of center/width
would better address the author's readability concern while preserving those
conditions. No replacement has been applied in this review round.

## Verification and coverage

The requested and returned model was exactly `claude-fable-5`. Access was verified;
the run completed after nine API responses and 17 successful read-only tool calls,
with `end_turn` and a nonempty final review. There was no model substitution,
continuation or automatic paid-request retry. The manifest records 444,850 input
tokens and 13,484 output tokens across the run; no monetary cost is inferred.

Reviewed commits:

- Manuscript: `890943f9a031ab9d719827ea9446707e609fc450`.
- Research: `ffc092d86db6f1d4077f584a180ae046d9e51980`.

Saved tool responses confirm the full abstract/entry point, introduction,
conclusion, related work, theory, four figure sources and notation macros were
provided. The follow-up source was provided only through line 200 of 205, despite
Fable's claim to have read all 205 lines. The five omitted lines complete the
relative-certificate and adaptive-regret qualifications. The appendix was provided
through line 200 of 254, and the implementation proof through lines 230–359.
`source_coverage.json` and the saved tool results are authoritative for coverage.

We checked the recommendations against the cited source passages and transformed
the six existing bound-chart coordinates to verify the mean-ratio explanation
above. This did not rerun experiments or recompute the original bounds from raw
trajectories. Fable did not inspect rendered pages, execute code/tests, replay raw
data, or search external literature. Its statements about figure clarity are
limited to source logic and labels. The paper's preceding build and regression
results remain records of the unchanged manuscript state, not checks performed
by this model review.

An independent source check agreed with the qualifications above, particularly
the finite-enumeration scope, asymptotic interpretation, mean-versus-individual
distinction and invalid cross-policy decomposition. It also identified the
zero-query and “can change” qualifications in the proposed theory replacement.
