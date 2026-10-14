# Revision status after the Claude Fable 5 review

The review is advisory. Two of its stronger claims needed correction: comparable
regret upper bounds do not imply realized policy dominance, and the original
appendix already reported the bound decomposition. The revisions below use the
source-checked interpretation of those findings.

## Manuscript changes

- Rewrote legacy CC-UCB/CG descriptions around the current transport theorem and
  the dense Cholesky implementation actually evaluated.
- Added the frozen-width guarantee and proof, with an explicit warning that
  policies generate different histories and comparable rates do not order regret.
- Moved the existing decomposition into the main narrative. At the terminal
  horizon, the base component accounts for 79.39–97.33% and explicit path
  inflation for 2.01–16.27% of the mean sharp bound. These are ratios of means
  over the primary-policy runs, not pooled medians or frozen-policy outcomes.
- Shortened the abstract, defined the four geometric/numerical objects more
  directly, clarified table comparisons and entropy units, and removed stale
  cross-references.
- Removed the entire historical one-sided appendix cluster from the active
  submission without deleting its source history. The PDF shrank from 68 to 29
  pages; all current-theorem proofs and controlled-study diagnostics remain.
- Updated the assistance disclosure and packaged only active LaTeX inputs.

## Follow-up evidence

The research branch `cce-review-revisions` contains the stronger-drift protocol,
a pinned Python environment, a resumable CPU launcher, and compact per-seed
exports with an independent bootstrap verifier. See
`experiments/REVIEW_EXPERIMENTS.md` on that branch for the current run commands
and validation status. Development/pilot results are engineering checks, not
publication results, and are not inserted into this manuscript.

The current controlled study consists of small NumPy/SciPy calculations. A host
with two A100 GPUs should run this workflow on its CPU cores; no GPU speedup is
claimed. Larger neural or real-data studies remain separate extensions, and the
paper makes no claims based on them.

## Items that cannot be closed by prose edits

- The original paired bootstrap still needs its original per-seed observations.
  Those absent data cannot be recovered or invented from aggregate summaries.
  Fresh follow-up exports prevent the same gap for the new study; they do not
  retroactively reproduce the historical study.
- Full follow-up results must be produced and reviewed before adding new
  empirical claims. Pre-evaluation numerical refinements and failed development
  checks must remain in the run record.
- Two flagged bibliography entries require external metadata verification.
  Scholarly endpoints were blocked in this cloud environment; no unverified
  bibliography correction was made. See [BIBLIOGRAPHY_APPENDIX_AUDIT.md](BIBLIOGRAPHY_APPENDIX_AUDIT.md).
- The authors must review the final scientific claims, anonymity, and venue
  declarations. No submission has been made.
