# Anonymous TMLR manuscript

Entry point: `main.tex`. The manuscript presents corrected-center confidence,
the reference-width floor and symmetric-factor sharpness, and scaled-tanh
relative-weight certificates through the transported-UCB framework. Section 6
reports two synthetic studies. The first fixed its protocol before evaluation.
The second (Section 6.1) chose its scale and margin on development runs and fixed
them before held-out evaluation, at a scale where the frozen bound is below the
regret cap; its code, per-run records and analysis live on the
`cce-review-revisions` branch.

## Build

From the repository root, with TeX Live, latexmk and Poppler installed:

```bash
openout_any=a TMLR_OUT=/tmp/cce-tmlr bash submissions/tmlr_2026/build.sh
```

The output directory must be outside the checkout. The script checks official
style hashes, compiles `main.pdf`, rejects undefined references/citations and
missing characters, and packages active manuscript inputs as `source.zip`.
Use `main.tex` with pdfLaTeX in Overleaf. The default anonymous TMLR mode and
the first-page Codex/Claude assistance disclosure are retained.

## Inputs and evidence

`transport_proofs.tex` retains proofs and solver/randomized-certificate
material in Appendix A. General action-space, assumption-ledger, notation,
algorithm and supporting certificate material are also in A. The full-study
protocol, post-outcome diagnostics and the second study's protocol are in
Appendix B. The
sources `transport_experiment.tex`, `transport_experiment_appendix.tex` and
`legacy_scope.tex` remain in Git and are excluded from this build.

The main outcome table is regenerated from unchanged portable per-seed
summaries and execution configuration in `evidence/`, with the existing chart
CSV data providing terminal comparison values. `evidence/` and the `tools/`
scripts below live on the `cce-review-revisions` branch; this branch carries
only the manuscript. There, with NumPy 2.2.3 installed in an external Python
environment, run:

```bash
python3 tools/make_tmlr_outcomes.py
python3 tools/make_tmlr_outcomes.py --check
```

The check independently reconstructs the nine paired bootstrap intervals,
checks the means and differences, and compares generated table/provenance
bytes. This is terminal-summary verification; it does not replay raw
trajectories or reproduce roundwise audits. The manuscript source ZIP includes
the rendered table and figures, and requires no experiment runtime
to compile. It is not the scientific code or raw-data supplement.

`STYLE_SHA256SUMS` pins the unchanged official style, bibliography style,
fancyhdr and license. Earlier audit and revision documents are historical
records; their build/test results do not verify this editorial source state.
Current source-state checks and artifacts are recorded in the assigned writer
report. No paper has been submitted.

Statement counters explicitly retain the manuscript's existing identities.
Any later statement addition or relocation requires comparing the complete
mathematical-environment and label-number inventories; the counters alone do
not detect an incorrect number assignment.

## Editorial figure reproduction

Original figure-generation records are retained unchanged. The current figure
bytes include explicit editorial transforms that remove duplicate caveat notes
and neutralize project comments. With local source history available, run:

```bash
python3 tools/prepare_tmlr_figures.py
python3 tools/prepare_tmlr_figures.py --check
```

`--original-root` can supply a matching scientific git-archive root. The check
validates the original generation hashes, current output hashes, unchanged CSV
data and the exact text transforms. `transport_editorial_provenance.json`
records both original and current figure hashes. The standalone source ZIP
contains the prepared figures; it needs no Git history to compile.
