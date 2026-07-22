# Revision Baseline

Baseline captured before the resubmission edits on 2026-07-22 at Git revision
`d62798160c8e08f4c5c9ebc21beb93a59f73a957`.

## Repository map

- Main manuscript: `paper/main.tex`
- Bibliography: `paper/references.bib`
- Paper build rules: `Makefile`, `paper/BUCK`
- Experiment configuration loader: `experiments/config.py`
- Versioned experiment configurations: `experiments/configs/`
- Experiment entry points and artifact builders: `experiments/`
- Unit and artifact tests: `tests/`, `experiments/tests/`
- Raw records: `results/raw/`
- Derived records: `results/derived/`
- Existing paper figures: `paper/figures/`
- Existing generated paper tables: `paper/tables/`

No top-level `scripts/` directory or one-command-per-main-figure reproduction
entry points existed at this baseline.

## Tests

Command:

```text
buck2 test //tests:tests //experiments/tests:tests -- --timeout=1200
```

Result: **pass**. Two targets passed; zero failures, timeouts, skips, build
failures, or infrastructure failures.

Static manuscript validation command:

```text
buck2 run //paper:validate
```

Result: **pass**. The validator reported 156 labels with no duplicates, 112
distinct reference targets with no unresolved references, and 35 citation keys
with no missing bibliography entries.

## Paper build

Command, run from `paper/`:

```text
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

Result: **pass**. The build produced a 42-page PDF. `latexmk` stabilized all
references and citations.

Pre-existing nonblocking diagnostics:

- one 5.1225 pt overfull `\hbox` at `paper/main.tex:80`;
- repeated `fancyhdr` warnings that the style sets `\footskip` to 0 pt;
- underfull boxes in prose, algorithms, the assumptions table, and the
  bibliography;
- the official target-year AISTATS reproducibility checklist file is absent,
  so the style marks the build provisional.

No undefined references, undefined citations, multiply defined labels, or
missing figures were reported. These baseline warnings are not silently
reclassified as regressions in later verification.

## Existing reproducibility limitations

- Main-paper artifacts do not yet have one end-to-end shell entry point per
  figure.
- Generated tables currently live under `paper/tables/`, not the requested
  `tables/generated/` location.
- The repository already documents missing raw scaling/provenance inputs and a
  not-run neural autodiff benchmark; those limitations remain open at this
  baseline.
- Rebuilding `paper/main.pdf` changes the tracked PDF working-tree entry even
  when the TeX sources are unchanged; final artifact checks must compare
  content and provenance deliberately rather than assuming byte identity.
