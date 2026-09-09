# Curvature-Calibrated Exploration — paper mirror

This `main` branch is intentionally lightweight for coauthor review and Overleaf synchronization.

The canonical live research branch is **`cce-experiments`**. It contains the complete research repository: manuscript source, experiments, configs, results, review/provenance material, tests, and tooling. Do not treat `main` as the source of truth for ongoing research work.

## Papers

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
- `main`: paper-only coauthor/Overleaf mirror at selected checkpoints.

Heavy experiment code, result aggregates, review bundles, test infrastructure, Buck configuration, and other research-engineering files are intentionally omitted from the current `main` tree. They remain available on `cce-experiments` and are not deleted from the canonical research branch.

Future paper updates should be selectively synchronized from `cce-experiments` into `main`; do not wholesale mirror the full research tree back into `main`.
