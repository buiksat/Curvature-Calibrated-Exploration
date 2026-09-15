# TMLR 2026 submission candidate

**Status: prepared, not submitted.** Nothing here has been uploaded anywhere.
`FINALIZATION_REPORT.md` lists the release holds that still need a human
decision before anything is sent.

This directory is a thin entry point. It contains no mathematics of its own:
`main.tex` `\input`s the shared canonical sources under `paper/`, which are the
same files the historical AISTATS entry point `paper/main.tex` reads. The two
venues differ in their shell, their abstract and one `\newif` switch, not in
their theorems.

```
main.tex                 the anonymous TMLR entry point
build.sh                 one command: build, package, hash
package.py               staging, .fls dependency closure, zips, scrub, manifest
supplement_README.md     becomes README.md inside supplement.zip
supplement_verify.sh     becomes verify.sh inside supplement.zip
FINALIZATION_REPORT.md   internal; NOT uploaded
PORTAL.md                private portal text; NOT uploaded
```

## Build

```bash
bash submissions/tmlr_2026/build.sh
```

Output goes to `${TMLR_OUT:-$TMPDIR/cce-tmlr-2026-release}`, which must be
outside the repository; `package.py` refuses otherwise, so the build cannot
touch a protected path. It produces:

| File | What it is |
|---|---|
| `main.pdf` | the anonymous submission PDF |
| `source.zip` | the staged project-local compile closure, flat, plus the permitted style and licence inputs |
| `supplement.zip` | the anonymous reproducibility material |
| `release_manifest.json` | deliverable and per-file hashes; never hashes itself |
| `src/` | the staged flat build tree, kept for inspection |

`source.zip` is not a copy of the repository, and it is not everything pdfTeX
opened either. It is the **project-local** part of the compile closure: every
file the recorder lists that lives inside the staged tree, which is the
manuscript sources, the generated table and figure inputs, the venue template,
and the four vendored third-party packages. On top of that it carries the
inputs a compile needs but pdfTeX itself never opens or the recorder does not
list — `references.bib` and `tmlr.bst`, which bibtex reads, and the four licence
texts. Unpacking it into an empty directory and running `latexmk -pdf main.tex`
reproduces the submitted PDF byte for byte.

The rest of the closure is the TeX distribution: 249 files in the recorded
build, under `/usr/share/texlive`, `/var/lib/texmf` and `/etc/texlive/web2c`.
Those are **not** in `source.zip` — redistributing a TeX installation is not
what a paper source archive is for — but they are not unrecorded either. Every
one is listed in `release_manifest.json` under `external_tex_inputs`, named by
the kpathsea variable whose tree holds it and bound to its SHA-256, so a
reviewer can see exactly which bytes outside the project the PDF depended on.
`package.py` admits an external input only from a system distribution tree that
is write-protected, unlinked and canonical at every path component; see
`paper/texmf_vendor/VENDORED-PACKAGES.md` for why four packages had to be
carried instead.

### Both archives store their members; they do not compress them

`write_zip` writes `ZIP_STORED` entries with fixed names, order, timestamps and
modes. That is a deliberate trade, and the thing it buys is that the deliverable
hash in `release_manifest.json` is a function of the members alone.

A deflate stream is whatever the linked zlib decided to emit. Two hosts with
different zlib builds, or one host after a zlib upgrade, produce different
archive bytes from byte-identical members, and the recorded hash drifts for a
reason that has nothing to do with the submission. Nothing in the declared build
closure pins zlib, so the honest choices were to pin a compressor or to stop
using one. Storing is the second.

The cost is size. `source.zip` also grew when the four third-party packages
were vendored into it, which is a separate change with its own reason; both are
in the current numbers below.

`supplement.zip` is dominated by one 77 MB evidence file, `full_aggregate.json`,
which is committed evidence and is not going to be trimmed to fit.
`package.check_archive_size` enforces TMLR's limit as a build failure, using
100,000,000 bytes rather than 100 MiB so it cannot pass on a generous reading,
and warns once the archive is within 10% of it. If a future change pushes the
supplement over, the trade has to be revisited -- by pinning a compressor into
the build closure, not by quietly turning deflate back on.

## Current release

Every figure here is read from the built artifacts themselves;
`tests/test_tmlr_release_package.py` recomputes each one against
`release_manifest.json` rather than trusting this table.

| Artifact | Bytes | Members | Unpacked |
|---|---:|---:|---:|
| `main.pdf` | 931,804 | 68 pages | — |
| `source.zip` | 3,420,977 | 94 | 3,408,765 |
| `supplement.zip` | 84,190,529 | 140 | 84,165,371 |
| `release_manifest.json` | 95,432 | — | — |

`supplement.zip` is 84.2% of the 100,000,000-byte limit, leaving 15,809,471
bytes of headroom. Compiled closure: 89 entries — 40 whose bytes the supplement
carries, 48 in `source.zip`, and `main.bbl`, which is in neither.

## Environment

| Requirement | Version used |
|---|---|
| pdfTeX | 3.14159265-2.6-1.40.21 (TeX Live 2020) |
| latexmk | 4.70b |
| bibtex | 0.99d |
| Python | 3.12 |
| NumPy / SciPy | 2.2.3 / 1.13.1 (the evidence checks; the study declared SciPy 1.15.2) |

LaTeX packages beyond a base TeX Live, where each comes from, and — the part
that matters when you unpack the archive — whether `source.zip` carries it:

| Package | In `source.zip`? | TeX Live package | Debian/Ubuntu | RHEL/EL |
|---|---|---|---|---|
| venue template (`tmlr.sty`, `tmlr.bst`, `fancyhdr.sty`) | **bundled** | n/a, ships with the submission | n/a | n/a |
| `mathtools` (with `mhsetup`) | **bundled** | `mathtools` | `texlive-latex-recommended` | `texlive-mathtools` |
| `cleveref` | **bundled** | `cleveref` | `texlive-latex-extra` | `texlive-cleveref` |
| `pgfplots` | **bundled** | `pgfplots` | `texlive-pictures` | `texlive-pgfplots` |
| `microtype` | **bundled** | `microtype` | `texlive-latex-recommended` | `texlive-microtype` |
| `rotating` | external | `rotating` | `texlive-latex-recommended` | `texlive-graphics` |
| `cm-super` (fonts) | external | `cm-super` | `cm-super` | `texlive-cm-super` |

Four third-party packages are bundled, not just the venue template: 46 files
plus three licence texts, vendored into `paper/texmf_vendor/` and staged flat.
The reason is the trusted-root rule, not convenience — this host's TeX Live does
not package them, so they were living in a user-writable tree, which the build
refuses. `paper/texmf_vendor/VENDORED-PACKAGES.md` records each package's
licence: GPL v3 for `pgfplots`, LPPL 1.3c for `microtype` and `mathtools`, LPPL
1.2 for `cleveref`. Nothing else is bundled; the remaining 249 compiled inputs
come from the system TeX distribution and are recorded, not shipped.

`rotating` supplies `sidewaystable`, which is how the three wide evidence tables
are set at the body font size instead of being scaled down. It is **not**
bundled: it is stock TeX Live and this host's distribution has it, so the
trusted-root rule is satisfied without carrying it. On this host `rotating.sty`
resolves to `texmf-dist/tex/latex/graphics/rotating.sty`, and the clean
`source.zip` unpack rebuilds the submitted PDF byte for byte with nothing
installed beyond the two external rows above. Without `cm-super` the document
typesets and then dies at font embedding on a missing `cm-super-ts1.enc`. No
font is bundled.

The build pins `SOURCE_DATE_EPOCH`, sets `\pdfinfoomitdate`, empties
`\pdftrailerid` and suppresses the pdfTeX banner, so two builds of the same
source produce identical bytes and the PDF carries no date, file ID, producer
string or author metadata.

## Verification

From the repository root, with NumPy and SciPy available:

```bash
python3 paper/validate.py                                   # static TeX validation
python3 tools/verify_tmlr_submission_numbers.py             # numerical-provenance ledger
python3 tools/transport_artifact_expectations.py --root .   # regenerate all 21 artifacts
python3 tools/verify_transport_committed_evidence.py        # detached committed-evidence verifier
```

Also run the release-package suite against a real build, which is what CI does:

```bash
TMLR_OUT=/tmp/cce-tmlr-release bash submissions/tmlr_2026/build.sh
TMLR_OUT=/tmp/cce-tmlr-release python3 -m pytest -q tests/test_tmlr_release_package.py
```

Inside an unpacked `supplement.zip`, `bash verify.sh` runs the required-package
contract gate and then four checks: the ledger, the artifact regeneration, the
sidecars of every shipped evidence file, and the study tests.

The declared native runtime is Buck2 against a host monorepo checkout
(`BUCK2_SETUP.md`). It does not currently work on this host: the pinned buck2
revision rejects a newer construct in the host prelude, so
`buck2 targets //...` fails before any target is analyzed. The commands above
are a portable route, not the declared build, and they are labelled as such in
`FINALIZATION_REPORT.md`. Buck2 is not a verified path and must not be reported
as one until that prelude block is fixed.

Nothing above rebuilds `paper/main.pdf`. That file is frozen, pinned by its
sidecar, and any command that could overwrite it belongs in a disposable copy
of the repository; the root `README.md` says how.

## Evidence

Every empirical claim comes from one locked aggregate,
`results/derived/transport_instantiation/full_aggregate.json`, SHA-256
`0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02`, produced at
execution revision `0cd6264c1f8b8751728f3c4a198207e8289aed74`. The ledger lists
each reported number with its selector, unit, aggregation rule, population,
unrounded value and display rounding.

## Limitations that are part of the submission, not bugs

- Raw per-run trajectories are not distributed and were never committed. Checks
  that would need them are reported NOT EXECUTED, including recomputation of the
  paired bootstrap.
- The realistic Covertype/Nyström extension is **not** part of this submission
  and is **not** cleared. It stays in `experiments/realistic_transport/` with its
  open evidence-integrity blockers, and CI runs it in a separate job so that its
  real status neither blocks nor is hidden by the submission checks.
- `paper/main.pdf` is a frozen pre-rewrite AISTATS snapshot. It is not this
  submission's PDF and is never rebuilt by anything here.
