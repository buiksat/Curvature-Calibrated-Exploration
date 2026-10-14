# TMLR manuscript on main

**Status: revised anonymous manuscript; compact research supplement built; not submitted.**

`main.tex` is the self-contained TMLR entry point. Scientific sources are
synchronized with `paper/` on `cce-review-revisions`; research code and evaluation
artifacts live on that branch. The historical AISTATS and CODE sources on main
remain separate from this submission.

The current revision makes the completed nonlinear-regime follow-up the main
empirical section and retains the original near-linear study in the appendix.
It adds the precise same-history width comparison, direct endpoint and
scaled-tanh relative-weight certificates, and exploratory diagnostics from the
retained follow-up histories. The abstract, introduction, related work,
conclusion, and availability statement now match that evidence. See
[REVISION_STATUS.md](REVISION_STATUS.md) for the checks and remaining limits.

## Format and provenance

The official [TMLR template](https://github.com/JmlrOrg/tmlr-style-file/tree/7bf90efe3a0debbba703c05c43f3ff7e4d4a2992)
was checked on 2026-10-13. `tmlr.sty`, `tmlr.bst`, `fancyhdr.sty`, and `LICENSE`
are unchanged upstream files; `STYLE_SHA256SUMS` records their hashes.

The manuscript uses a 10pt article, the default anonymous TMLR mode, native
single-column layout and fonts, author/year citations, and appendices after
references. The wide evidence tables retain body-size text on landscape
floats. Captions appear above tables, and the first page discloses the
Codex and Claude assistance. The availability statement describes the compact
anonymous evidence supplement and separately states its raw-data limitations.
The anonymous PDF contains no author contact details or identifying metadata.

TMLR is a journal with rolling submissions and no fixed page limit. Manuscripts
over 12 main-text pages have longer review timelines. Policies were checked in
the journal's official website-source revision
`ac4daa6a6d170eb16bcdab0368a02fb0cfbe58c2`, because direct website access was
blocked by this environment's network policy:

- [Author guidelines](https://github.com/JmlrOrg/tmlr/blob/ac4daa6a6d170eb16bcdab0368a02fb0cfbe58c2/templates/author-guide.html)
- [Editorial policies](https://github.com/JmlrOrg/tmlr/blob/ac4daa6a6d170eb16bcdab0368a02fb0cfbe58c2/templates/editorial-policies.html)
- [FAQ, including first-page LLM disclosure](https://github.com/JmlrOrg/tmlr/blob/ac4daa6a6d170eb16bcdab0368a02fb0cfbe58c2/templates/faq.html)

## Build

From the repository root in the prepared cloud environment:

```bash
source /workspace/cce-env/activate.sh
TMLR_OUT=/workspace/cce-build/tmlr-current bash submissions/tmlr_2026/build.sh
```

This creates `main.pdf` and `source.zip` outside the checkout and checks for
unresolved references, citations, and missing characters. The default output
directory is `/tmp/cce-tmlr`. `source.zip` is suitable for a standalone LaTeX
project or Overleaf, with `main.tex` as its Main document. The archive uses the
compiler's input list and contains only active manuscript inputs, required
BibTeX/style files, and build instructions. It contains no inactive legacy
appendices, code supplement, internal review notes, or portal declarations.
See `BUILD.md` for the non-cloud build instructions.

## Current validation

Final build and archive-reproduction facts are recorded in
[REVISION_STATUS.md](REVISION_STATUS.md). Manuscript build checks are separate
from experimental verification and from the strict anonymous code/evidence
supplement built on the research branch. Use its matched release files together;
see the status record for paths and hashes.

## Before submission

The manuscript build does not establish readiness of the research code or
empirical claims. [IMPLEMENTATION_REVIEW.md](IMPLEMENTATION_REVIEW.md) records
the initial branch inspection and remaining reproducibility checks.

Before uploading, the authors must review the manuscript, confirm the full
author list and OpenReview declarations, and confirm that the work is not
published, accepted, or under concurrent review at another archival venue.
An AISTATS-formatted source file alone says nothing about its submission status.
The verified compact supplement is below TMLR's 100 MB limit; its verification
scope and raw-data limitations are recorded in `REVISION_STATUS.md`. No paper
has been submitted.
