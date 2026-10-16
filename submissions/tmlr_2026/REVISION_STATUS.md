# Revision status: precise contextual-bandit abstract

Updated 2026-10-15 (America/Los_Angeles). The abstract is now a 250-word,
single-paragraph narrative with contextual-bandit scope in the first sentence.
It states the problem and gap, explains the conditional approach, reports the
principal theoretical and experimental findings, and distinguishes validity,
bound tightness and useful decisions. The title already matches; small
introduction edits clarify the valid starting band and one-model empirical scope.

The [guidance and editorial record](ABSTRACT_REVISION.md) cites authoritative
sources read directly online, including current TMLR requirements. The official
style files still match current upstream bytes. This is an anonymous manuscript;
no TMLR submission has been made.

All three active abstract copies and 44 active scientific source files match.
The main and strict research PDFs have **52 portrait pages** and are byte-identical.
Pages 1–4 were inspected at reading resolution, and all pages in rendered contact
sheets. No clipping, overlaps, missing characters or overfull boxes were found.
Two TeX compatibility warnings and underfull spacing diagnostics remain.

The strict source archive rebuilds the PDF byte for byte in a fresh extraction
without using either checkout. The fresh supplement passes every advertised
step, 25 anonymous-contract checks and 23 study tests. It remains below the
100 MB limit at 93,902,070 bytes. Its numerical ledger records 616 PASS,
38 PASS_ANON and 3 NOT_EXECUTED, with no failures. The raw-data limitations remain.

The full research repository rerun on `189e9ce` reports **739 passed, 3 skipped, 0 failed, 2 warnings in 187.33s**. The prior run's sole failure
was a committed-history whitespace guard on the preceding handoff; the updated
handoff fixes it. The three skips are documented host/path cases; fresh archive
validation separately covers the legacy rebuild-path check. A packaging scanner
false positive was corrected with a regression; no measured evidence was changed.

All 270 checked scientific/evidence files and all 218 prior numerical-ledger
entries remain unchanged. The explicitly stated 95% interval level adds one
entry derived from the existing locked configuration. Semantic pins, changed
source/tool hashes and the research release manifest were refreshed.

| Matching artifact | SHA-256 |
| --- | --- |
| PDF | `a586d20810255d42f320bd1f8f346e881f41d095d134b0456d7a051ec388caef` |
| Source ZIP | `a2d69ef63f44920be07fe6b26720308a47f41d53993f1734bb9d1bcbde33f652` |
| Supplement ZIP | `c90bed4eeafd18c707bbff18b2832f55ff4d242ae7cd2841e9a7633505ad701e` |

Matching deliverables are in the local chat's `outputs/` directory. Detailed
[implementation](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/review/abstract_revision/IMPLEMENTATION_REPORT.md)
and [verification](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/review/abstract_revision/VERIFICATION.json)
records live on the research branch. No new experiments, raw-trajectory replay,
external model review or submission were performed. Author review and OpenReview
declarations remain required before submission.
