# TMLR submission candidate

**Status: revised anonymous manuscript and compact evidence package built; not submitted.**

The latest revision rewrites the abstract as a 250-word narrative with explicit
contextual-bandit scope, theorem conditions, a limited synthetic study, and
negative findings. The title remains aligned, and small introduction edits
clarify the same scope. See the [online guidance and editorial rationale](ABSTRACT_REVISION.md).

The preceding chart revision replaces all eight numerical result tables with focused
charts, retaining the original numerical tables in the reproducibility
supplement. Ten new figures show policy intervals, fixed-history comparisons,
seed ranges, drift frequencies and certificate diagnostics at native text size.
The outcome table is consolidated into the existing outcome chart. See the
[chart revision record](../../review/table_chart_revision/IMPLEMENTATION_REPORT.md).

The preceding revision applied the checked Fable readability advice: a notation
table and chronological protocol guide, clearer abstract and policy descriptions,
explicit own-history mean bound magnitudes, and an unambiguous chart comparator
label. A further local pass defines the empirical certificate notation by
cross-reference, separates strict seed thresholds from non-strict round thresholds,
and fixes grammar, score punctuation and an unused equation number. It builds on
the earlier problem-first rewrite. Existing formal results, proofs and
experimental evidence are preserved. See
[the local-fix record](../../review/readability_polish/IMPLEMENTATION_REPORT.md),
[the checked Fable advice](../../review/readability_followup_fable/CHECKED_ADVICE.md)
and [the earlier readability rewrite](../../review/readability_revision/IMPLEMENTATION_REPORT.md).

This entry point uses canonical scientific sources under `paper/`. The main
branch carries a self-contained LaTeX mirror. The historical `paper/main.pdf`,
original experiment sources, locked configurations and evidence exports remain
unchanged. The current supplement includes metadata-anonymized copies of the
follow-up evidence, with separate original and packaged digests.

## Build

From the prepared research checkout:

```bash
cd /path/to/Curvature-Calibrated-Exploration
PYTHON=/path/to/pinned-python312/bin/python \
  TMLR_OUT=/home/bahram/Documents/Codex/2026-10-15/continue-work-on-buiksat-curvature-calibrated/work/abstract-release \
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

Final build directory: `/home/bahram/Documents/Codex/2026-10-15/continue-work-on-buiksat-curvature-calibrated/work/abstract-release`.
The PDF has **52 pages**, in anonymous official TMLR style. All eight numerical
tables have chart replacements; all pages are portrait. The compact notation
table remains on page 5. The chart revision record maps each result to its page.

| Artifact | Bytes | Members | Unpacked bytes |
|---|---:|---:|---:|
| `main.pdf` | 722,007 | — | — |
| `source.zip` | 3,459,637 | 103 | 3,445,945 |
| `supplement.zip` | 93,902,070 | 190 | 93,867,286 |
| `release_manifest.json` | 115,720 | — | — |

The supplement occupies 93.9% of the 100,000,000-byte limit, leaving
6,097,930 bytes. Both ZIPs use fixed-order, fixed-time uncompressed
(`ZIP_STORED`) entries. The size gate remains enforced.

The compiled closure contains 95 entries: 44 whose bytes the supplement
carries, 50 in `source.zip`, and `main.bbl` in neither archive. BibTeX
regenerates the latter from the shipped bibliography and style. The manifest
also records 239 protected external TeX inputs by distribution variable and
content hash under `external_tex_inputs`. Those distribution files are
recorded, not redistributed.

## Dependencies and trust

The current local build uses pdfTeX 1.40.28 / TeX Live 2025 (Debian),
latexmk 4.87 and BibTeX 0.99d. Evidence validation uses CPython 3.12 with the
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
/path/to/pinned-python312/bin/python tools/verify_tmlr_submission_numbers.py
/path/to/pinned-python312/bin/python tools/transport_artifact_expectations.py --root .
/path/to/pinned-python312/bin/python tools/make_transport_explanatory_figures.py --check
/path/to/pinned-python312/bin/python tools/verify_transport_committed_evidence.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  TMLR_OUT=/home/bahram/Documents/Codex/2026-10-15/continue-work-on-buiksat-curvature-calibrated/work/abstract-release \
  /path/to/pinned-python312/bin/python -m pytest -q tests experiments/tests
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
