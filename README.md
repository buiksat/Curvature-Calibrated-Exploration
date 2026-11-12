# Confidence transport: TMLR manuscript mirror

This branch contains the self-contained anonymous TMLR manuscript for coauthor
review and Overleaf synchronization. The canonical research branch is
[`cce-review-revisions`](https://github.com/buiksat/Curvature-Calibrated-Exploration/tree/cce-review-revisions),
which contains the experiment implementation, evidence, tests, and strict
reproducibility packager.

## Manuscript

- Entry point: [`submissions/tmlr_2026/main.tex`](submissions/tmlr_2026/main.tex).
- Build instructions and submission status:
  [`submissions/tmlr_2026/README.md`](submissions/tmlr_2026/README.md).
- Current validation record:
  [`submissions/tmlr_2026/REVISION_STATUS.md`](submissions/tmlr_2026/REVISION_STATUS.md).

For Overleaf, set the Main document to `submissions/tmlr_2026/main.tex` when
importing this repository, or `main.tex` when importing the generated source ZIP.
Build outside the checkout:

```bash
TMLR_OUT=/tmp/cce-tmlr-main bash submissions/tmlr_2026/build.sh
```

The build produces a PDF and a standalone source archive. It does not generate
an experiment supplement or submit the paper. The manuscript is recorded as
not submitted.

## Research and review

Run experiments and build the strict anonymous supplement on
`cce-review-revisions`; follow its `PYTHON_SETUP.md` and
`experiments/REVIEW_EXPERIMENTS.md`. Selectively synchronize scientific manuscript
updates into this branch.

The optional scientific review runner is documented in
[`tools/CLAUDE_REVIEW.md`](tools/CLAUDE_REVIEW.md).

## Archived material

Historical AISTATS and CODE@MIT manuscripts, inactive legacy appendices, and
superseded numerical tables remain available at the immutable pre-cleanup commit
[`93c5b23`](https://github.com/buiksat/Curvature-Calibrated-Exploration/tree/93c5b23d62b05cdc147783d5a7f61e463a035de1),
tagged `archive/main-before-tmlr-cleanup-2026-11-12`. Current result charts remain
in this tree; the corresponding numerical tables remain in the research
supplement.
