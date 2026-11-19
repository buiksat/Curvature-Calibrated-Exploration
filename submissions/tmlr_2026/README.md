# TMLR manuscript and research package

The current manuscript is the approved editorial revision, mapped into the
canonical `paper/` layout on `cce-review-revisions`. `main.tex` is the thin venue
entry point. The `main` branch carries the Overleaf mirror. No submission has
been made.

## Build and verify

Use the direct CPython environment in [PYTHON_SETUP.md](../../PYTHON_SETUP.md).
Keep the output outside the checkout:

```bash
openout_any=a PYTHON=/path/to/pinned-python/bin/python \
  TMLR_OUT=/tmp/cce-current-release bash submissions/tmlr_2026/build.sh
/path/to/pinned-python/bin/python tools/prepare_tmlr_figures.py --check
/path/to/pinned-python/bin/python tools/make_tmlr_outcomes.py --check
/path/to/pinned-python/bin/python tools/verify_tmlr_submission_numbers.py
/path/to/pinned-python/bin/python submissions/tmlr_2026/package.py \
  --compare-manifest /tmp/cce-current-release/release_manifest.json
```

The strict build stages exact source bytes, checks the compiler's actual input
closure, rejects unresolved references and citations, authenticates the anonymous
contracts, checks containment and archive inventories, and publishes local
deliverables only after its gates pass. `source.zip` can be rebuilt in a clean
directory. Extract `supplement.zip` separately and run its own `verify.sh` with
the pinned Python environment. The internal `release_manifest.json` is not
anonymous upload material.

The current PDF has 38 pages in the recorded TeX environment. Build results,
including PDF comparisons and exact test counts, belong to the verification
report for the particular commit; this document does not certify later builds.

## Scientific provenance

`tools/make_tmlr_outcomes.py` reads the existing unchanged per-seed export at
`review/transport_review_followup/full-cce-full-local/`. No duplicate `evidence/`
tree is needed. Its check replays terminal paired-bootstrap intervals.

The original artifact generators retain their scientific calculations.
Their exact original Python source preimages are shipped under
`tools/editorial_originals/` and authenticated before loading. Current outer
adapters have separate hashes from those original generator sources.
`tools/prepare_tmlr_figures.py` authenticates original generated sources and the
approved editorial transforms. Original generation records retain their
original hashes and attribution; a separate editorial record binds current
figure sources. CSV values and scientific exports remain unchanged.

The older near-linear manuscript sources are retained for historical ledger
checks in the repository and must be present there. Only a validated anonymous
package omits those nonshipped historical sources. They are excluded from the current source and
supplement manuscript inventories. The original aggregate, numerical tables
and provenance remain reproducibility material. Historical reports describe
their own source states and do not verify this revision.

Raw trajectories are absent from the compact supplement. Terminal summaries
support the checks described in the manuscript; they do not reconstruct missing
roundwise raw data or establish universal floating-point certificates. The second
prespecified study (Section 6.1) is a new adaptive experiment; its per-run records
and analysis are in `review/v3_results/` and `review/v3_protocol/`. No Phase 2
implementation is part of this port.

## Current release

The release inventory below describes the recorded local package. It does not
claim universal PDF byte identity across TeX distributions or a test-suite pass.
Verification results and limits must be read from the report for the exact source
state. No material has been uploaded or submitted.

| Artifact | Bytes | Members | Unpacked bytes |
|---|---:|---:|---:|
| `main.pdf` | 529,118 | n/a | n/a |
| `source.zip` | 2,984,408 | 84 | 2,974,026 |
| `supplement.zip` | 99,264,865 | 210 | 99,226,933 |
| `release_manifest.json` | 115,303 | n/a | n/a |

The supplement uses 99.3% of the 100,000,000-byte limit,
leaving 735,135 bytes. Both ZIPs use deterministic `ZIP_STORED`
entries; the strict size and inventory gates remain required.

The compiled closure has 75 entries. `source.zip` contains all 74 nongenerated compiled inputs:
24 also present in the supplement and 50 source-only compiled inputs.
The generated `main.bbl` is in neither archive; BibTeX recreates it from the
required bibliography and style. `source.zip` also includes 10 required extras,
including the standalone `BUILD.md`, bibliography, style, source and licence files.
Compiled-input classification and total archive membership are distinct.

`source.zip` contains the project-local compiler inputs and required BibTeX,
style, source and licence extras. `external_tex_inputs` records protected
distribution inputs and their content hashes; those inputs are not redistributed.

| Package | In source.zip? | Role |
|---|---|---|
| Venue template | **bundled** | Official TMLR styles and licence |
| `mathtools` | **bundled** | Includes mhsetup |
| `cleveref` | **bundled** | Cross references |
| `pgfplots` | **bundled** | Plotting runtime and required sources |
| `microtype` | **bundled** | Typography runtime |
| `algorithms` | **bundled** | Runtime styles, regeneration sources and licence |
| `rotating` | external | Historical dependency; unused by the current manuscript |
| `cm-super` | external | No font is vendored |

The vendor inventory contains 50 runtime/source files, plus the separate
licence texts. The historical Debian packaging record identifies `rotating.sty`
as supplied by `texlive-latex-base`; the current build records the installed
external bytes independently. See `paper/texmf_vendor/VENDORED-PACKAGES.md`.
