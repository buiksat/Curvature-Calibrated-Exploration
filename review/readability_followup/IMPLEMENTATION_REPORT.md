# Applying the checked Fable readability advice

The author asked to apply the recommendations from the fresh Fable readability
review. This revision implements the useful edits after checking the proposed
wording against the mathematics and evidence. The unchanged model response and
the corrections needed before adopting it remain in
[`readability_assessment_fable`](../readability_assessment_fable/README.md).

## Changes for the reader

- The abstract explains width and the prediction at the center of a confidence
  band, then separates optimizer independence from the conditions on the
  confidence guarantee. The introduction gives a modest motivation for using
  current sensitivities and glosses Thompson–Finsler geometry.
- A compact notation table collects the three matrices, four widths, and
  principal score/certificate terms at native body size. A chronological guide
  introduces the general protocol. Its finite-action skim advice explicitly
  preserves timing, confidence and certificate obligations.
- The first path-certificate explanation identifies an auxiliary comparison
  path. The theory states its cumulative pseudo-regret convention and separates
  the uncertainty-set, same-history and computational qualifications of the
  reference-width comparison. The exact ratio's zero-query convention and the
  distinction from a general computational lower bound remain explicit.
- The empirical section explains the Hessian and Endpoint policies locally,
  gives the existing mean bound magnitudes, and defines feature categories and
  actionwise ratio averaging. The mean figures describe each named policy's own
  50 histories, separately from the fact that every individual bound is vacuous.
  The near-linear bridge describes an asymptotic scaling family; it does not
  treat `W = Omega(T)` as a pass/fail test at a fixed horizon.
- The outcomes chart identifies its zero comparator as “Hessian = 0,” avoiding
  confusion with the Frozen reference policy. The generator produces the label;
  generated data are not edited by hand. A rendered candidate exposed a zero
  guide crossing the new label, prompting a small leftward annotation shift.
- The reading route points to the relevant sections. One redundant conclusion
  sentence was removed; qualifications needed to interpret results and figures
  remain beside those claims.

The revision does not paste Fable's proposed cross-policy attribution or attach
mean magnitudes to individual trajectories. It preserves “can change” and “not
necessarily” in the width-floor discussion. These are scientific scope choices,
not merely stylistic preferences.

## Scientific and artifact scope

The baseline commits are research `a9315960dbbf6e7c81d519872805041f9d8114dc`
and main `890943f9a031ab9d719827ea9446707e609fc450`. All 21 existing formal theory
blocks, 60 displayed theory expressions, 18 proof blocks and 44 proof displays
are preserved. Experiments, configurations, original evidence, table values,
plotted data and historical PDFs remain unchanged. The chart's annotation and
its position change; its plotted observations, intervals and axes do not.

The numerical ledger adds six explicit entries for the displayed mean bound
magnitudes, computed independently from the pinned per-seed terminal summaries.
All 212 preceding entries retain their selectors and scientific definitions.
Three mutation cases reject a changed Hessian magnitude, a changed frozen-policy
magnitude, and a changed own-history population. The chart test also compares
its summary-derived values against those per-seed computations. Existing checks
and mutation cases remain in place. Generated artifact pins, source-context pins
and the actual compiled-source closure are refreshed to the revised bytes.

No new experiment or Fable API request was run for this implementation. The
earlier model verdict applies to the source snapshot it read, not automatically
to this revision. The original raw-data and numerical-certification limitations
remain unchanged. No TMLR submission has been made.

## Validation record

The detailed record, including the initial rendered-label issue, final builds,
archive reproduction and actual test outcomes, is in
[`REVISION_VALIDATION.md`](../../submissions/tmlr_2026/REVISION_VALIDATION.md).
The source hashes and independent preservation report in this directory bind
the final scientific sources to the reviewed state.
