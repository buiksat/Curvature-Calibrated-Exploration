# Reader-first manuscript revision

The author asked for a substantial readability rewrite after Fable's publication
assessment. The intended reader knows machine learning but is new to this
confidence-transport argument. The precise technical communication skill guided
the edit: explain the problem before its machinery, introduce terminology when
needed, and preserve the conditions that make each claim true.

## What changed

The abstract now opens with the practical problem: retraining can change an
uncertainty estimate without adding observations. The introduction explains
bandit action selection, uses a recommender as an explicitly illustrative
example, distinguishes stored collection-time gradients from recomputed ones,
and states why transport is studied even though direct reference scoring is
available. It defines the width, confidence radius and certificate before
presenting the formal interfaces. The conclusion states the observed policy
comparison directly and separates it from possible causal explanations.

The theory starts with a finite-action example and exact matrix/width
calculation. Its one added display is a direct specialization of the existing
transported score. It then introduces the matrices and their widths before the
general measurable-action protocol. Short explanations before and after the
results identify each certificate's job, why both comparison directions matter,
what the corrected center corrects, how historical and current errors enter,
and what a tighter endpoint certificate can and cannot improve. All existing
formal results and displayed theory formulas remain present.

The empirical section leads with findings and explains pseudo-regret. Its
paragraphs answer reader questions about the four policies, the regret
comparisons, the usefulness of bounds, and the recorded checks. It defines a
vacuous bound through the deterministic regret cap before using the term.
Protocol details follow the interpretation rather than interrupting the opening.
The appendix gives purpose statements before its more technical diagnostics.
Related work is grouped by how each method constructs uncertainty, while
preserving every existing citation and scoped comparison.

An independent reader pass prompted three final clarifications: the algorithm
now points to the main follow-up experiment; the comparison-table caption says
that its final two rows account only for operator approximation; and the local
comparison no longer refers vaguely to a "previous" result. These changes
clarify references and interpretation, without altering mathematical formulas.

## Meaning and evidence preserved

The preservation baseline is research commit
`650c072548f950c5b13bf58146c983a8ef88eadd`. The independent comparison records
240 unchanged protected evidence, configuration, generator, figure, table and
historical-PDF files. All 21 theory formal statements, all 59 existing theory
displays, all 18 proof blocks and all 44 proof displays are retained. The only
new theory display is the introductory exact-case score. Empirical numeric
and mathematical-expression inventories are unchanged. The abstract is identical
in both research entry points and in the main-branch mirror.

The paper still distinguishes widths on a fixed history from regret on different
adaptive histories, benchmark outcomes from available contextual headroom,
pointwise intervals from simultaneous inference, numerical diagnostics from
verified enclosures, and source-package checks from raw-trajectory replay.
The original raw-data limitations remain. No theorem, experiment, figure data,
reported result or citation was added, removed or changed; the extra formula
explains an existing theorem specialization. No new Fable review was requested.

The numerical ledger retains all 212 entries, 175 phrase/count contracts and
123 classified literal keys, with unchanged scientific selectors and aggregation
rules. It binds the rewritten statements to new reviewed source contexts.
Detached evidence checks retain their scientific requirements with equivalent
wording; an existing mutation-test anchor was updated for the changed line break.
The validation record documents actual focused and full-suite results, including
the initial anchor failure and repair.

## Rendered paper and reproducibility

The main build has 46 pages in the unchanged official TMLR style. Its added
space is used for explanations, with native body-size text. Root inspected
pages 1–4, including the abstract, introduction, diagram and exact-case guide.
An independent reader checked the main prose for comprehension and scope.
Final independent render inspection covered pages 1–4, 7–9 and 17–20, including
the theorem interpretation, comparison table, empirical prose and all four
figures, with no clipping or overlap. Source-archive reproduction, strict package
checks and final test results (713 passed, three skipped, zero failed) are recorded in
`submissions/tmlr_2026/REVISION_VALIDATION.md`. `SOURCE_STATE.json` binds the
reviewed scientific source bytes; `PRESERVATION.json` records the independent
comparison with the baseline.

The earlier Fable verdict concerned the preceding manuscript snapshot. This
revision implements its readability advice and the author's stronger request;
it does not turn that earlier review into a new assessment of these final bytes.
No TMLR submission has been made.
