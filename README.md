# Curvature-Calibrated Exploration — paper mirror

This `main` branch is intentionally lightweight for coauthor review and Overleaf synchronization.

The canonical live research branch is **`cce-experiments`**. It contains the complete research repository: manuscript source, experiments, configs, results, review/provenance material, tests, and tooling. Do not treat `main` as the source of truth for ongoing research work.

## Papers

### TMLR submission draft

- Main source: [`submissions/tmlr_2026/main.tex`](submissions/tmlr_2026/main.tex)
- Build, official-template provenance, and submission status: [`submissions/tmlr_2026/README.md`](submissions/tmlr_2026/README.md)
- Initial implementation-branch review: [`submissions/tmlr_2026/IMPLEMENTATION_REVIEW.md`](submissions/tmlr_2026/IMPLEMENTATION_REVIEW.md)

This anonymous draft incorporates the scientific-review revisions described in
[`REVISION_STATUS.md`](submissions/tmlr_2026/REVISION_STATUS.md).
It is prepared for review and has not been submitted. The build produces a PDF
and a standalone LaTeX source archive outside the checkout.

The matching research revision and stronger-drift experiment workflow are on
[`cce-review-revisions`](https://github.com/buiksat/Curvature-Calibrated-Exploration/tree/cce-review-revisions).
Use that branch on the Meta devserver and follow
[`experiments/REVIEW_EXPERIMENTS.md`](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/cce-review-revisions/experiments/REVIEW_EXPERIMENTS.md).
The controlled study uses CPU workers; two A100 GPUs do not need to be allocated.

For an automated scientific review with Claude Fable, see
[`tools/CLAUDE_REVIEW.md`](tools/CLAUDE_REVIEW.md). The runner supplies the
manuscript and implementation snapshots and saves the review locally.

### AISTATS manuscript

- Main source: [`paper/main.tex`](paper/main.tex)
- Compiled snapshot: [`paper/main.pdf`](paper/main.pdf)
- Supporting theorem/proof/experiment source, bibliography, tables, figures, and style files are retained under [`paper/`](paper/).

For Overleaf, set the project **Main document** to:

```text
paper/main.tex
```

### CODE@MIT 2026 extended abstract

- Source: [`submissions/code_mit_2026/main.tex`](submissions/code_mit_2026/main.tex)
- Provenance/readme: [`submissions/code_mit_2026/README.md`](submissions/code_mit_2026/README.md)

The CODE source is kept separate from the AISTATS manuscript.

## Branch policy

- `cce-experiments`: canonical research branch; continue scientific and experimental work there.
- `cce-review-revisions`: isolated scientific-review revision and new experiment workflow, based on `cce-experiments`.
- `main`: paper-only coauthor/Overleaf mirror at selected checkpoints.

Heavy experiment code, result aggregates, review bundles, test infrastructure, Buck configuration, and other research-engineering files are intentionally omitted from the current `main` tree. They remain available on `cce-experiments` and are not deleted from the canonical research branch.

Future paper updates should be selectively synchronized from `cce-experiments` into `main`; do not wholesale mirror the full research tree back into `main`.
