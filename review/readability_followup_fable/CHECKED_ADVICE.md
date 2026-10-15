# Checked feedback on the revised manuscript

Fable's verdict is **“ready for author review; no further essential readability
rewrite is needed.”** It finds the previous protocol, bound-magnitude and chart
label barriers resolved in the current text, and recommends no new experiment
for the claims currently made. It did not identify a substantive scientific error
in the sources it inspected. These are the model's judgments, not an acceptance
prediction or independent certification of the mathematics.

The complete response is preserved unchanged in [review.md](review.md). The
assessment below is our source check of its advice. This round changes no
manuscript, scientific data, experiment, figure, verification code or release
artifact.

## Useful local edits

1. **Connect the empirical certificate notation to its definition.**
   `paper/transport_followup.tex:34` uses `\bar D_t^Q`, whereas the Hessian
   corollary at `paper/transport_theory.tex:675–691` denotes the same construction
   by `\bar D_t` and defines `Q_t`. A short alias and reference to
   `cor:hessian-path-new` would help readers following the introduction-to-results
   route. Fable's proposed formula agrees with the corollary. The original-study
   section also uses the decorated symbol without defining it and appears later,
   so it does not resolve the local gap. This is a notation clarification, not a
   new certificate or change in assumptions.
2. **State the two threshold conventions separately.** The numerical ledger at
   `tools/verify_tmlr_submission_numbers.py:421–427` counts 16 seeds whose maximum
   endpoint distance is strictly greater than one, but 286 seed-round observations
   whose distance is at least one. A safe wording for
   `paper/transport_followup.tex:151–154` keeps the strict seed statement and adds
   a separate sentence for the non-strict round count. The compact seed summaries
   have 16 maxima above one, 16 at least one, and none exactly one among the 50
   Hessian histories at `W = 0.25`. The round summaries store the non-strict count;
   this check does not establish their separate strict count. Fable's blanket
   assurance that the discrepancy cannot change any conclusion is not a verified
   result of its review.
3. **Optional copyediting.** The score display ends in a comma before a new
   sentence (`paper/transport_theory.tex:258–263`). The applied-matrix definition
   has an unlabeled equation number (`:77–83`); retaining or suppressing it is a
   presentation choice. “294 separate development and tuning trajectories” would
   read more naturally than the current phrase (`paper/transport_followup.tex:15`).
   These suggestions do not require altering formal statements or results.

## Recommendations to qualify

Fable labels the certificate-notation issue optional in its issue list and
required in its final actions. We treat it as the most useful small clarification,
not evidence that the paper needs another substantial rewrite.

The abstract suggestion is not sufficiently specific to adopt. Its cited
conversion sentence actually begins at `submissions/tmlr_2026/main.tex:92`,
already after a sentence ending at line 91. The response gives no concrete
replacement demonstrating a further improvement. Keep the abstract unless an
author identifies a particular remaining ambiguity.

The model's statements about proof correctness, contribution and venue fit remain
source-review judgments. It performed no formal proof verification, experiment
execution, live literature search or current TMLR policy check. We independently
found no material meaning drift in the latest readability edits; that is narrower
than certifying all of the paper's claims or its publication prospects.
Its phrase “certified negative result” must not be read as certifying the
experimental floating-point calculations: the paper distinguishes conditional
theory from numerical diagnostics without rigorous enclosures.

## Coverage and verification

The exact requested and returned model was `claude-fable-5`. The run completed
with `end_turn` after ten API responses and 24 successful read-only tool calls.
It read every line of the 11 required current manuscript sources, including the
1,180-line theory, 230-line follow-up, 254-line empirical appendix and all four
explanatory figure sources. It also read all 572 proof lines, two result tables,
the bound-chart CSV, and then the two historical advice/implementation records.
The saved tool responses substantiate this coverage; the model's explicit list
of unread sources remains in its review.

The manuscript snapshot is `dd0263f37560df411a077be9267f5fb931c280c6`; the research
snapshot is `8c056e27e631232d0a3f1ad1935ec43c4dc37078`. The exact prompt, returned
text, raw responses, commits, usage and source accesses are recorded alongside
this file. There was no model substitution, continuation or duplicate paid
request after the brief local progress-log connection interruption.

This round checks source consistency and review artifacts. It does not rerun
tests or experiments, replay raw trajectories, inspect rendered pages, or
revalidate publication requirements. The earlier build and regression results
remain bound to the unchanged manuscript state; they were not performed by
Fable in this review.
