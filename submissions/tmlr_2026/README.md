# TMLR manuscript on main

**Status: anonymous manuscript draft; not submitted.**

`main.tex` is the TMLR entry point. This directory is a self-contained snapshot
of the TMLR manuscript already present on `cce-experiments` at
`7bd8e4d78b62e1ea510da51deac7cc2c4624637d`. The AISTATS and CODE sources under
`paper/` and `submissions/code_mit_2026/` remain unchanged. Research code,
results, and test infrastructure stay on the research branch.

The October 14 revision addresses the scientific-review findings: it clarifies
method scope, adds a frozen-width guarantee with an explicit own-history caveat,
foregrounds the existing bound decomposition, and removes the historical
one-sided appendix cluster from the active paper. Those sources remain in Git;
`legacy_scope.tex` explains their exclusion. The original reported experiment
values are unchanged. Scientific source changes are synchronized to the
`cce-review-revisions` research branch, where the follow-up experiment workflow
lives. See [REVISION_STATUS.md](REVISION_STATUS.md) for completed work and
remaining evidence requirements.

## Format and provenance

The official [TMLR template](https://github.com/JmlrOrg/tmlr-style-file/tree/7bf90efe3a0debbba703c05c43f3ff7e4d4a2992)
was checked on 2026-10-13. `tmlr.sty`, `tmlr.bst`, `fancyhdr.sty`, and `LICENSE`
are unchanged upstream files; `STYLE_SHA256SUMS` records their hashes.

The manuscript uses a 10pt article, the default anonymous TMLR mode, native
single-column layout and fonts, author/year citations, and appendices after
references. The wide evidence tables retain body-size text on landscape
floats. Captions appear above tables, and the first page discloses the
Codex and Claude assistance. The availability statement describes retained
research materials without claiming that a supplement has already been built
or attached. The anonymous PDF contains no author contact details or
identifying metadata.

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
appendices, code supplement, internal review notes, or portal declarations. See `BUILD.md` for
the non-cloud build instructions.

## Validation on 2026-10-14

The revised PDF builds to 29 Letter pages, with 16 pages before the references
(the preceding draft was 68 pages). The final log has no unresolved citations,
missing characters, overfull boxes, or LaTeX warnings; one underfull box remains.
The title page, shorter abstract, and assistance disclosure were visually checked.

A clean extraction of `source.zip` builds without manuscript-checkout inputs
and produces a byte-identical PDF, SHA-256
`5e6ea1c9229d090e350987ae851fa49238b36d1a20a84839b43c34e52303d8eb`.
These checks validate the manuscript build, not the experimental results.

## Before submission

The manuscript build does not establish readiness of the research code or
empirical claims. [IMPLEMENTATION_REVIEW.md](IMPLEMENTATION_REVIEW.md) records
the initial branch inspection and remaining reproducibility checks.

Before uploading, the authors must review the manuscript, confirm the full
author list and OpenReview declarations, and confirm that the work is not
published, accepted, or under concurrent review at another archival venue.
An AISTATS-formatted source file alone says nothing about its submission status.
Prepare and verify any anonymous evidence supplement separately; TMLR allows
up to 100 MB in PDF or ZIP format. Nothing in this directory submits a paper
or changes a remote branch.
