# TMLR submission candidate

**Status: revised anonymous manuscript and compact evidence package built; not submitted.**

The current revision incorporates the checked Fable feedback: an abstract
confidence-band example, more concise framing, descriptive context-free and
best-fixed-action comparisons, and an explicit distinction between Hessian-score
diagnostics and the policies that generated their histories. See
[the implementation and publication assessment](../../review/post_fable_revision/IMPLEMENTATION_REPORT.md).

This entry point uses canonical scientific sources under `paper/`. The main
branch carries a self-contained LaTeX mirror. The historical `paper/main.pdf`,
original experiment sources, locked configurations and evidence exports remain
unchanged. The current supplement includes metadata-anonymized copies of the
follow-up evidence, with separate original and packaged digests.

## Build

From the prepared research checkout:

```bash
cd /workspace/cce-research
PYTHON=/workspace/cce-research-env/bin/python \
  TMLR_OUT=/workspace/cce-build/tmlr-fable-final-release \
  bash submissions/tmlr_2026/build.sh
```

`TMLR_OUT` must be outside the repository. The build stages, compiles, checks
references and layout, validates the evidence inventory, anonymizes metadata,
checks identity strings and archive size, and publishes the local deliverables
only after their manifest and member checks pass. It uploads nothing.

The source ZIP contains the project-local compiler inputs and required BibTeX,
style, source and licence extras. The supplement contains compact evidence and
verification tools. `release_manifest.json` is an internal release record and
must not be uploaded as anonymous material. The staged `src/` is retained for
inspection. The historical `FINALIZATION_REPORT.md` describes an earlier release;
[REVISION_VALIDATION.md](REVISION_VALIDATION.md) records the current checks.

## Current release

Final build directory: `/workspace/cce-build/tmlr-fable-final-release`.
The PDF has **38 pages**, in anonymous official TMLR style.

| Artifact | Bytes | Members | Unpacked bytes |
|---|---:|---:|---:|
| `main.pdf` | 644,571 | — | — |
| `source.zip` | 3,364,042 | 97 | 3,351,306 |
| `supplement.zip` | 93,693,136 | 169 | 93,661,942 |
| `release_manifest.json` | 110,726 | — | — |

The supplement occupies 93.7% of the 100,000,000-byte limit, leaving
6,306,864 bytes. Both ZIPs use fixed-order, fixed-time uncompressed
(`ZIP_STORED`) entries. No unpinned compressor determines their bytes.
The size gate remains enforced.

The compiled closure contains 89 entries: 38 whose bytes the supplement
carries, 50 in `source.zip`, and `main.bbl` in neither archive. BibTeX
regenerates the latter from the shipped bibliography and style. The manifest
also records 240 protected external TeX inputs by distribution variable
and content hash under `external_tex_inputs`. Those distribution files are
recorded, not redistributed.

- `main.pdf`: `158c98e99f2665d0c804a7f13a8c8d76fe0c6ae1d18f3c45bfae21caf3e64822`.
- `source.zip`: `da0e004d58b3198da3e3526c4c9a36921f665d60e0e4dac93d25d889ad0e5fa3`.
- `supplement.zip`: `8be0424f9fdc98387dde264d8e2dc8fe7bb3ea3eb3438c9fdf86aa3180fff81a`.

## Dependencies and trust

The current cloud build uses pdfTeX 1.40.26 / TeX Live 2025-dev (Debian),
latexmk 4.86 and BibTeX 0.99d. Evidence validation uses CPython 3.12 with the
hash-pinned wheel environment in `experiments/requirements-python312.lock`.
Run `tools/check_python_environment.py` to check installed package versions.

The project vendors exact copies of pgfplots, microtype, mathtools/mhsetup,
cleveref and the algorithms bundle. The latter includes both runtime styles,
the source files needed to regenerate them, and its LGPL text. These packages
contribute 50 runtime/source files and four licence texts, separate from the
venue template. Source/archive copies are bound to exact digests; see
[the vendoring record](../../paper/texmf_vendor/VENDORED-PACKAGES.md).

| Package | In `source.zip`? | Role or external dependency |
|---|---|---|
| Venue template | **bundled** | Official `tmlr.sty`, `tmlr.bst`, `fancyhdr.sty` and licence |
| `mathtools` | **bundled** | Includes `mhsetup` |
| `cleveref` | **bundled** | Cross-reference formatting |
| `pgfplots` | **bundled** | Plotting inputs |
| `microtype` | **bundled** | Typography inputs |
| `algorithms` | **bundled** | `algorithm.sty`, `algorithmic.sty`, regeneration sources and LGPL text |
| `rotating` | external | Supplies `sidewaystable`; `texlive-latex-base` owns `rotating.sty` in the recorded Debian installation |
| `cm-super` | external | Not bundled; its font package is not used by this recorded build |

No font is vendored. Remaining TeX inputs must be canonical, unlinked and
write-protected at every path component. Debian's `TEXMFDEBIAN` tree is subject
to these same checks. Writable user TeX trees are excluded from the strict build.

Clean source rebuilds are checked against the recorded toolchain. Different
TeX distributions can produce different PDF bytes; the recorded closure and
external hashes expose that difference rather than claiming universal byte
identity.

## Verification

```bash
/workspace/cce-research-env/bin/python tools/verify_tmlr_submission_numbers.py
/workspace/cce-research-env/bin/python tools/transport_artifact_expectations.py --root .
/workspace/cce-research-env/bin/python tools/verify_transport_committed_evidence.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  TMLR_OUT=/workspace/cce-build/tmlr-fable-final-release \
  /workspace/cce-research-env/bin/python -m pytest -q tests experiments/tests
```

After extracting `supplement.zip`, run `bash verify.sh` with the supported
Python environment on `PATH`. Its mandatory anonymous-package gates authenticate
both contracts before the ledger, artifact regeneration, terminal interval
reconstruction, evidence coverage and shipped study tests. The follow-up
contract requires all 20 compact evidence files and six generated artifacts;
scientific values are unchanged. Metadata transforms and dependent hash updates
are explicit, and original external-input hashes continue to describe original,
unshipped raw files. The 14-file compact export reconstructs the reported
terminal intervals from all 600 evaluation summaries.

## Remaining limits

The original near-linear study lacks its raw trajectories and per-seed bootstrap
inputs. The follow-up raw tree is retained locally, but is not in the compact
supplement, has not been transformed into an anonymous raw archive, and has no
verified durable anonymous download location. Raw-dependent scans and optimizer
replay therefore remain separate from compact evidence verification. See
[the raw archive status](../../review/post_fable_revision/RAW_ARCHIVE_STATUS.md).

The Buck2/host-monorepo runtime remains an unverified historical route. The
commands above use the supported portable Python environment. The separate
Covertype/Nyström extension is outside this submission and retains its own
open evidence-integrity issues.

The authors still need to review the final materials and supply the required
OpenReview declarations. A successful build and evidence verification establish
neither acceptance nor an actual submission.
