# Confidence Transport for Relinearized Curvature in Contextual Bandits

This repository contains a theory-first contextual-bandit manuscript about
transporting confidence from predictable collection-time tangent features to a
current, relinearized GGN or Fisher metric.  The main result uses logarithmic
metric-path transport, two-sided approximate-operator certificates, a generic
certified solver width, a corrected prediction center, and an approximate
score-maximization oracle.

## Manuscript

The manuscript sources under `paper/` are shared by two venue entry points, so
the mathematics exists in exactly one copy:

| Entry point | Venue | State |
|---|---|---|
| [`paper/main.tex`](paper/main.tex) | AISTATS | historical, two-column |
| [`submissions/tmlr_2026/main.tex`](submissions/tmlr_2026/main.tex) | TMLR | current submission candidate, anonymous, **not submitted** |

Both are thin shells. The shared sources are:

- `paper/macros.tex` and `paper/notation.tex` for notation;
- `paper/body_intro.tex`, `paper/body_related.tex`, `paper/body_conclusion.tex`
  for the narrative sections;
- `paper/transport_theory.tex` for the headline theorem stack;
- `paper/transport_proofs.tex` for complete proofs;
- `paper/transport_experiment.tex` and `paper/transport_experiment_appendix.tex`
  for the controlled study;
- `paper/appendix_*.tex` for the deferred derivations, protocol, and the
  one-sided proofs;
- `paper/legacy_dynamic.tex` for the older one-sided result;
- `paper/legacy_experiments.tex` for the limited scope of retained diagnostics
  (AISTATS entry point only);
- `paper/references.bib` for bibliography data;
- `paper/tmlr_style/` for the official, unmodified TMLR stylefile bundle.

See [`submissions/tmlr_2026/README.md`](submissions/tmlr_2026/README.md) for the
one-command submission build and its verification commands.

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

Run the tests and the static manuscript validation directly:

```bash
python -m pytest -q tests experiments/tests
python paper/validate.py
```

Buck2 is **not** a verified path right now.  `buck2 test` and `buck2 run` fail
during prelude evaluation with an unresolved `root_values` block on the declared
host setup, as [`BUCK2_SETUP.md`](BUCK2_SETUP.md) records; the `BUCK` targets are
kept for the Meta host checkout but must not be reported as passing until that
block is fixed.  Generated Buck output is written under `buck-out/` and ignored
by Git.

### Building the manuscript

To build the current manuscript, build the TMLR submission entry point and send
its output to a directory outside the repository:

```bash
TMLR_OUT=/tmp/cce-tmlr-release bash submissions/tmlr_2026/build.sh
```

`package.py` refuses to write inside the repository, so this cannot touch a
protected path.  See
[`submissions/tmlr_2026/README.md`](submissions/tmlr_2026/README.md) for what it
produces and how to verify it.

`paper/main.pdf` is a frozen pre-rewrite snapshot, pinned by
`paper/main.pdf.sha256` and verified by CI.  The historical AISTATS entry point
`paper/main.tex`, `make pdf`, and any other command that can overwrite that file
may be run **only in a disposable copy of the repository**, for example:

```bash
work=$(mktemp -d) && git archive HEAD | tar -x -C "$work"
( cd "$work/paper" && latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex )
```

Refreshing `paper/main.pdf` in place would break the sidecar and the committed
evidence checks, so do not do it as part of ordinary work.
