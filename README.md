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
| [`submissions/tmlr_2026/main.tex`](submissions/tmlr_2026/main.tex) | TMLR | current submission candidate, anonymous, **not submitted** |

The entry point reads the shared scientific sources under `paper/`:

- `paper/macros.tex` and `paper/notation.tex` for notation;
- `paper/body_intro.tex`, `paper/body_related.tex`, `paper/body_conclusion.tex`
  for the narrative sections;
- `paper/transport_theory.tex` for the headline theorem stack;
- `paper/transport_proofs.tex` for complete proofs;
- `paper/transport_experiment.tex` and `paper/transport_experiment_appendix.tex`
  for the controlled study;
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

The original near-linear study and the stronger-drift follow-up are controlled
audits of the transported policies. Auxiliary linear and autodiff artifacts
remain diagnostics, not validation of the headline theorem.

## Validation

Install the exact Python 3.12 package lock using
[`PYTHON_SETUP.md`](PYTHON_SETUP.md), then run the tests and the static manuscript
validation directly:

```bash
"$CCE_VENV/bin/python" tools/check_python_environment.py
"$CCE_VENV/bin/python" -m pytest -q tests experiments/tests
"$CCE_VENV/bin/python" paper/validate.py
```

The active build uses direct Python and TeX Live. Historical Buck infrastructure
and the deferred realistic-transport extension are archived; see
[ARCHIVE.md](ARCHIVE.md).

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

## Archives and evidence

Historical AISTATS and CODE@MIT manuscripts, the frozen pre-rewrite PDF and its
rendered audit, the duplicate selection export, and the deferred Covertype
workstream are preserved at `archive/research-before-tmlr-cleanup-2026-11-12`.
[ARCHIVE.md](ARCHIVE.md) explains retrieval and the checks retained against
that immutable snapshot. Current theory, experiment configurations, measured
results, and the strict TMLR source/evidence closure are retained.

The original near-linear aggregate and its provenance remain current TMLR
appendix evidence. The smaller GitHub review bundle is an inspection aid, not
replacement raw data. The current follow-up summaries and numerical tables
remain available for verification and exact numerical lookup.
