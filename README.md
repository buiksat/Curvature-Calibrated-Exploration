# Confidence Transport for Relinearized Curvature in Contextual Bandits

This repository contains a theory-first contextual-bandit manuscript about
transporting confidence from predictable collection-time tangent features to a
current, relinearized GGN or Fisher metric.  The main result uses logarithmic
metric-path transport, two-sided approximate-operator certificates, a generic
certified solver width, a corrected prediction center, and an approximate
score-maximization oracle.

## Manuscript

The canonical source is [`paper/main.tex`](paper/main.tex).  Its main supporting
files are:

- `paper/macros.tex` for notation;
- `paper/transport_theory.tex` for the headline theorem stack;
- `paper/transport_proofs.tex` for complete proofs;
- `paper/legacy_dynamic.tex` for the older one-sided result;
- `paper/legacy_experiments.tex` for the limited scope of retained diagnostics;
- `paper/references.bib` for bibliography data.

The independent derivation and assumption audit live in
`THEORY_TRANSPORT_DERIVATIONS.md` and `THEORY_GENERALIZATION_AUDIT.md`.

## Retained implementation

The implementation is intentionally narrow.  It retains the bounded linear
audit, matrix-free autodiff GGN checks, the shared curvature and theory
utilities needed by those paths, and their artifact generators.  See
[`experiments/README.md`](experiments/README.md) for exact commands and output
semantics.

The checked-in empirical artifacts predate the current confidence-transport
theorem.  They are legacy diagnostics and reproducibility records, not
validation of the headline result.

## Validation

The verified build path uses Buck2 and a Meta host checkout.  Required host
paths and toolchain details are in [`BUCK2_SETUP.md`](BUCK2_SETUP.md).

```bash
buck2 test //tests:tests //experiments/tests:tests -- --timeout=1200
buck2 run //paper:validate
```

To build the PDF with a local TeX installation:

```bash
make pdf
```

Generated Buck output is written under `buck-out/` and ignored by Git. The
compiled manuscript is committed as `paper/main.pdf`; refresh it with
`make pdf` after changing the paper sources.
