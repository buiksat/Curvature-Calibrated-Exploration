# Author approval ledger

**Status: proposed revision, not submission-ready.** A visible author marker remains in the candidate. The underlying committed draft and historical README are retained unchanged in `original/`.

## Decisions requiring author action

|ID|Type|Decision / missing information|Candidate treatment|
|---|---|---|---|
|AUTH01|Missing author metadata|[AUTHOR: supply final author order and affiliations]|Visible marker, no inferred names or affiliations|
|AUTH02|Venue confirmation|[AUTHOR: confirm the linked submission form's required fields and author/anonymity instructions]|Official call has no explicit anonymity instruction; linked form returned 401. Do not remove the review marker or claim venue readiness without this check|
|C01|Proposed evidence addition|[AUTHOR: approve including the four pooled exp(D_Q/2) medians in Table 1]|Included in the proposed candidate, with seed-round pooling explicitly identified; no new statistic computed|
|C02|Contribution positioning|[AUTHOR: confirm the two-contribution wording: explicit finite-action confidence transfer and corrected-center confidence without nonlinear optimizer convergence]|Included as proposed positioning of existing canonical results, with no novelty claim for the underlying geometry or standard machinery|

The author requested descriptive absolute regret reporting and removal of the bootstrap zero-exclusion count. Those instructions are implemented with source-verified values; no new interval analysis or unresolved statistical choice was introduced. Approval of the proposed manuscript remains the author's decision.

## Title choice recorded separately

Retained: **Confidence Transport for Adaptive Experimentation: Theory and a Controlled Audit**. The alternative wording “simulation study” was not adopted. No title decision is needed to review this candidate; a later change requires explicit author approval.

## Optional analyses: resolved by omission, not pending manuscript blockers

Existing terminal bound components are documented in `OPTIONAL_ANALYSES.md` but not added to the paper. A new terminal-inflation summary and normalized confidence slack were not computed. No attribution of bound vacuity to transport alone is made. Thus no additional analysis approval is needed to read or approve the present candidate.

No unsupported category-D mathematical or analytical change was implemented. No new experiment, stronger-nonlinearity condition, future five-page result promise, or named NeuralUCB convergence comparison was added.
