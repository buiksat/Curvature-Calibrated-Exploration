# Checked revisions after Fable review

This revision implements the source-checked recommendations from
`review/post_revision_fable/QUALIFICATIONS.md`. The external review is advisory;
its incorrect policy-mechanism and performance-ceiling interpretations are not
adopted. No experiment or additional external model review was run for this
revision.

## Scientific and editorial changes

- Added a short abstract confidence-band example: the reference interval can
  hold while a narrower naive current-width score underestimates its mean. The
  text explicitly distinguishes this illustration from a realizable scaled-tanh
  trajectory, a new necessity theorem, or evidence of necessity in the study.
- Made the abstract's certified-region and Taylor/misspecification-envelope
  conditions explicit. Condensed the introduction and conclusion while retaining
  same-history, fixed-teacher, pointwise-interval and floating-point scope.
- Clarified that evaluating the displayed actionwise ratio requires the reference
  width as written. No general computational impossibility is claimed.
- Added descriptive context-free mean-only and best-fixed-action regrets from
  the retained follow-up aggregate, with precise benchmark definitions and no
  equivalence inference. Each new displayed number has a source-bound ledger
  entry. New mutation checks reject a changed baseline or an invented equivalence
  conclusion.
- Clarified that every mechanism-table row diagnoses the Hessian score on the
  named behavior histories. It does not demonstrate width dominance of all four
  policies' own scores. Removed repeated counts and shortened the noisy kernel
  timing discussion while preserving its cost limitations.
- Extended the stored-input arithmetic statement to all 65 ranking changes after
  checking their maximum score gap. Upstream learning, solves and coefficients
  remain outside that numerical recomputation.
- Added a verified weighted-Gram connection and retained the distinction between
  representation changes and a nonstationary reward model. The proposed new
  nonstationary-bandit citation was not added because its primary sources could
  not be accessed. See `LITERATURE_CHECK.md` for the bounded lookup and its limits.

The table-generator adaptation for anonymous packaging changes original-source
attribution metadata, not scientific cells. Frozen experiments, selected
configurations, original evidence exports and the historical PDF are preserved.

## Publication assessment

The paper is worth considering for TMLR as a narrowly scoped methodological and
diagnostic study. The useful contribution is its operational accounting of
reference confidence, replayed curvature, applied operators and the actual solver
width used for selection, together with a concrete corrected-center construction
and an audit separating validity, certificate tightness and policy behavior.

The main risk is significance and novelty. The geometry, regression confidence,
PSD comparisons and UCB argument are established; the width floor is elementary.
A reviewer may regard the negative result as a consequence of a conservative
certificate in a small synthetic model. The relative certificate reduces
conversion overhead, but establishes no new statistical information, adaptive
regret improvement or end-to-end computational advantage. A targeted source
review finding no central proof error is not a formal proof certification or an
acceptance prediction.

Large new experiments are not necessary for the paper's present narrow claims.
Additional teachers would test breadth, a numerically stabilized adaptive run
would test sensitivity to early ranking changes, and full-cost measurements
would be needed for a speed claim. Any such extension needs a specific question,
a separately fixed protocol and fresh evaluation data; the review is not a
reason to search for a setting where the naive policy fails.

## Validation and delivery

Final build, package and test results are recorded in
`submissions/tmlr_2026/REVISION_VALIDATION.md`. The main-branch manuscript mirror
has its corresponding record in `submissions/tmlr_2026/REVISION_STATUS.md`.
The original study's missing raw data cannot be repaired by this revision.
Compact evidence verification and full raw-trajectory replay remain separate
claims. No submission to TMLR has been made.
