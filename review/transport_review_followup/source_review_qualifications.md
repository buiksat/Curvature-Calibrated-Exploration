# Claude Fable 5 review: reading notes

The review was requested from the Anthropic API using **`claude-fable-5`** and the repository's saved scientific-review prompt. The reviewer inspected immutable manuscript and implementation snapshots using read-only tools. It did not run tests, reproduce experiments, build the PDF, or check live literature or venue policies.

Read [the complete review](source_review.md) together with the qualifications below. The review includes a claim-to-evidence map, prioritized findings, an experimental program, a revised abstract, writing edits, and a revision plan. Its finding of no P0 issue in inspected material is an external model's assessment, not an independent proof certification.

## Findings to act on

- Update related work and cross-references that still describe the legacy CC-UCB/CG method as the current contribution.
- Bring the existing bound decomposition into the main narrative so readers can separate base confidence-bound looseness from transport inflation.
- Simplify the abstract and reduce the legacy appendix burden while retaining the proofs needed for the current claims.
- Make the paired statistical results reproducible by releasing the necessary per-run data and reconciling dependency/provenance documentation.
- Consider larger-drift experiments if extending claims beyond the present controlled regime. Treat numerical operator/solver and real-data extensions according to the intended claim scope.

## Source-check qualifications

**F5 overstates what comparable bounds imply.** A frozen-width UCB policy can achieve the same worst-case rate under common uniform assumptions without the explicit transport overhead. This does not imply an ordering of realized regret, show transport cannot outperform it, or prove transport is unnecessary. The policies generate different trajectories, radii, and information gains. Also, the width-scaling condition is sufficient, not a necessary characterization of all informative certificates. The manuscript itself discusses trajectory differences in `submissions/tmlr_2026/transport_experiment.tex:121`.

**F3 overstates an omission.** The appendix already presents the decomposition and explicitly says the base confidence component dominates (`submissions/tmlr_2026/transport_experiment_appendix.tex:71`). Moving that result into the main narrative is a useful improvement. Marginal medians of inflation factors alone cannot establish attribution of the cumulative bound, and the base component includes more than the confidence radius. A separate frozen-policy bound comparison would be an additional analysis, not an existing result.

Do not apply proposed writing edit E.3 verbatim: its claim that the decomposition has not been reported conflicts with the existing appendix.

**F4 requires external verification.** A citation key that contains a different year from the entry is not itself a scientific or bibliographic error. Lack of browsing access does not establish that a reference is fictitious. Verify actual titles, authors, dates, identifiers, and relevance before editing references.

The continuation includes Claude's own qualifications to the earlier findings. These notes additionally record the independent source check that the vacuity decomposition already exists.

**Coverage wording:** section G puts the implementation configuration under "Read in full" while also reporting that only 200 of its 242 lines were read. It was partially inspected. The recorded coverage table checks the supplied line counts directly from the inspection log.

## Provenance

- Manuscript: `846987748046a372458b6cadcda352263469e486` (`main`).
- Implementation: `7bd8e4d78b62e1ea510da51deac7cc2c4624637d` (`origin/cce-experiments`).
- Original request: 42 inspection calls; response truncated while writing the revised abstract. Its original output and incomplete manifest remain preserved.
- Completion: one follow-up request with the same saved prompt, identical replayed inspection evidence, and the partial review. It requested the remaining sections and qualifications, rather than restarting the inspection loop.
- `review.md` joins the original text before the unfinished abstract with the continuation verbatim. `manifest.json` records the original incomplete run; `continuation-manifest.json` records completion status.
- No manuscript or implementation source was changed during this review.
