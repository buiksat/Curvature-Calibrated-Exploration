# TMLR submission candidate

**Status: revised anonymous manuscript and compact evidence package built; not submitted.**

The current revision applies the checked Fable readability advice: a notation
table and chronological protocol guide, clearer abstract and policy descriptions,
explicit own-history mean bound magnitudes, and an unambiguous chart comparator
label. It builds on the earlier problem-first rewrite. Existing formal results,
proofs and experimental evidence are preserved. See
[the implementation record](../../review/readability_followup/IMPLEMENTATION_REPORT.md),
[the checked Fable advice](../../review/readability_assessment_fable/CHECKED_ADVICE.md)
and [the earlier readability rewrite](../../review/readability_revision/IMPLEMENTATION_REPORT.md).

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
  TMLR_OUT=/workspace/cce-build/tmlr-clarity-final-release \
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

Final build directory: `/workspace/cce-build/tmlr-clarity-final-release`.
The PDF has **47 pages**, in anonymous official TMLR style. The four explanatory
figures appear on pages 3, 10, 20 and 21; references begin on page 26.
The notation table is on page 5.

| Artifact | Bytes | Members | Unpacked bytes |
|---|---:|---:|---:|
| `main.pdf` | 691,388 | — | — |
| `source.zip` | 3,412,620 | 101 | 3,399,248 |
| `supplement.zip` | 93,812,058 | 178 | 93,779,332 |
| `release_manifest.json` | 113,268 | — | — |

The supplement occupies 93.8% of the 100,000,000-byte limit, leaving
6,187,942 bytes. Both ZIPs use fixed-order, fixed-time uncompressed
(`ZIP_STORED`) entries. No unpinned compressor determines their bytes.
The size gate remains enforced.

The compiled closure contains 93 entries: 42 whose bytes the supplement
carries, 50 in `source.zip`, and `main.bbl` in neither archive. BibTeX
regenerates the latter from the shipped bibliography and style. The manifest
also records 240 protected external TeX inputs by distribution variable
and content hash under `external_tex_inputs`. Those distribution files are
recorded, not redistributed.

- `main.pdf`: `f3d809c81247961058fe498a25048365d3f3a3b53c3f677cbb283fafdf688a70`.
- `source.zip`: `1f07ef7dbdcac50b97a8783dc82653c40fc4ae2002e5a7af3fe780f1e3d20fda`.
- `supplement.zip`: `3635fd755e8a2af17c438ed0c702552cf26434d7ec6f59ca45658c8497850ea0`.

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
/workspace/cce-research-env/bin/python tools/make_transport_explanatory_figures.py --check
/workspace/cce-research-env/bin/python tools/verify_transport_committed_evidence.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  TMLR_OUT=/workspace/cce-build/tmlr-clarity-final-release \
  /workspace/cce-research-env/bin/python -m pytest -q tests experiments/tests
```

After extracting `supplement.zip`, run `PYTHON=/path/to/supported/python bash
verify.sh` with the supported Python environment. Its mandatory anonymous-package gates authenticate
both contracts before the ledger, artifact regeneration, terminal interval
reconstruction, evidence coverage and shipped study tests. The follow-up
contract requires all 20 compact evidence files, the six original follow-up
table/provenance artifacts, six explanatory chart artifacts, and two separately
pinned schematic sources. Chart regeneration is distinct from checking the
manually authored schematics. Scientific values are unchanged. Metadata transforms and dependent hash updates
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
