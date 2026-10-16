# Local Codex handoff — 2026-10-16

## Current goal

Improve the TMLR manuscript's abstract and readability. The user wants the
title and first sentence to make the contextual-bandit scope explicit, and
wants published guidance on writing scientific abstracts consulted before a
full rewrite. The user approved saving and pushing these changes before
continuing in local Codex.

## Repository state

Repository: https://github.com/buiksat/Curvature-Calibrated-Exploration

- `main`: submission-facing manuscript under `submissions/tmlr_2026/`.
- `cce-review-revisions`: research code, experiments, validation tools, and
  canonical scientific sources under `paper/`, plus the TMLR entry point.
- This handoff and the latest scope edits are being committed to both branches.
  Use ordinary fetch/pull in a clean local checkout; preserve any local work.

## Changes made in this voice session

Title: **Confidence Transport in Contextual Bandits: Guarantees and Limits
under Relinearization**.

The abstract now starts:

> We study gradient-based confidence estimates for exploration in contextual
> bandits. Further training on the same observations can change these estimates
> without adding new data. We ask when recomputing past gradients at the current
> model preserves the confidence guarantee used to choose actions.

The TMLR entry point is updated on both branches. The research entry point
`paper/main.tex` is updated on the research branch as well.
The remainder of the abstract has not yet been rewritten.

## Next work

1. Consult authoritative scientific-abstract guidance and current TMLR rules.
   Candidate references, not successfully retrieved in the cloud:
   - https://mitcommlab.mit.edu/eecs/commkit/abstract/
   - https://writingcenter.unc.edu/tips-and-tools/abstracts/
   - https://www.nature.com/documents/nature-summary-paragraph.pdf
   - https://jmlr.org/tmlr/author-guide.html
2. Rewrite the abstract as a coherent, self-contained narrative:
   problem and scope → research gap → contribution → principal results →
   interpretation. Around 180–220 words is an editorial suggestion, not a
   verified TMLR requirement.
3. Keep the conditional assumptions and empirical limitations accurate,
   while moving unnecessary technical inventory into the main text.
4. Synchronize the manuscript entry points. Rebuild and inspect the PDF.
   Use the existing validation/release tooling to refresh affected provenance
   and packaging records; do not treat earlier release verification as applying
   to newly edited sources.

## Scientific facts that must survive editing

- This is a contextual-bandit study of gradient-based confidence estimates,
  not a claim about uncertainty estimation for every model.
- Confidence transport starts from a valid reference confidence statement and
  requires explicit conditions/error controls. It is not an unconditional
  guarantee for arbitrary retraining.
- With the same history, center, radius, and bias, the certified transported
  width cannot be smaller than the direct reference width. Exact actionwise
  transport recovers the reference width.
- This does not establish regret ordering across policies with different
  adaptive histories.
- The prespecified study uses a 29-parameter scaled-tanh model, four policies,
  three conditions, and 50 paired seeds per condition.
- Hessian transport has higher mean pseudo-regret than every comparator in
  each condition; all nine pointwise paired confidence intervals exclude zero.
- Transport regret bounds and the reference policy's own bounds are vacuous
  in the study. Passing recorded floating-point confidence/optimism checks
  does not prove universal validity or practical usefulness.
- Preserve these negative results rather than making the paper sound stronger.

## Previous completed work and validation boundary

All eight numerical tables were replaced or consolidated into charts; exact
tables remain supplemental lookup data. Ten new chart files were added.
The chart revision was committed and pushed before this voice session.

Prior validated chart commits:
- main: `39c6d16eb68e55232a63da54e1873beb834891f6`
- research: `0982b19254fc2d481bdde72d3b74ecb8c360bb1b`

The prior PDF had 52 pages. Its release validation is recorded in
`submissions/tmlr_2026/REVISION_VALIDATION.md` and, on the research branch,
`review/table_chart_revision/IMPLEMENTATION_REPORT.md` and
`review/table_chart_revision/VERIFICATION.json`.

This voice session changed source text only. Whitespace/diff checks and
manuscript synchronization checks are performed before committing.
No new PDF, release archive, experiments, full regression run, or external
Claude review has been produced for these title/abstract edits.
Older PDF/archive artifacts therefore do not contain the latest wording.

## Cloud access limitation

Direct attempts to retrieve the sources above failed at the managed network
proxy with HTTP 403 while opening the connection. The precise proxy policy
was not established. Network access was declared enabled. Local network access
may resolve this, but that has not been verified.

No local desktop session has been opened or automatically transferred.
This committed document carries the task context to the local checkout.

