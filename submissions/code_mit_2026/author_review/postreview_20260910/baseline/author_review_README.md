# CODE@MIT proposed revision: author review

The revised source is [../main.tex](../main.tex). It is the exact candidate previously prepared in isolation, now published as readable repository files at the author's request. It is a **review draft**, not an approved submission. The author-information marker and all four unresolved approval items remain.

## Read the revision

| Purpose | File |
| --- | --- |
| Changes with original lines, old text, new text, and reasons | [CHANGELOG.md](records/CHANGELOG.md) |
| Pending author decisions | [AUTHOR_APPROVAL.md](records/AUTHOR_APPROVAL.md) |
| Mathematical definitions and empirical claim provenance | [CLAIM_TO_SOURCE.md](records/CLAIM_TO_SOURCE.md) |
| Symbol checklist | [SYMBOLS.md](records/SYMBOLS.md) |
| Bound decomposition, terminal inflation, confidence-slack availability | [OPTIONAL_ANALYSES.md](records/OPTIONAL_ANALYSES.md) |
| Reference verification | [VERIFIED_BIBLIOGRAPHY.md](records/VERIFIED_BIBLIOGRAPHY.md) |
| Recorded venue/form check | [VENUE_CHECK.md](records/VENUE_CHECK.md) |
| Preparation provenance and inspected source ranges | [PROVENANCE.md](records/PROVENANCE.md), [SOURCE_READS.json](records/SOURCE_READS.json) |
| Original preparation validation | [VALIDATION.md](records/VALIDATION.md), [VALIDATION.json](records/VALIDATION.json), [final build log](logs/final-build.txt) |
| Publication-stage checks | [PUBLICATION_CHECKS.md](PUBLICATION_CHECKS.md) |
| Unified manuscript patch | [code_revision.patch](code_revision.patch) |
| Unchanged baseline | [original/main.tex](original/main.tex), [original/README.md](original/README.md) |
| Transcribed evidence fields | [evidence/](evidence/) |
| Published-file checksums | [../SHA256SUMS](../SHA256SUMS) |

## Historical records versus publication

The files under `records/`, `evidence/`, `original/`, the patch, and the original final build log are unchanged preparation records. Their statements that no commits, pushes, or synchronization occurred describe the **earlier isolated revision task**. The subsequent author instruction authorized this GitHub publication, not resolution of the scientific approvals or conference submission. Repository commit history records publication separately.

References in those records to `candidate/main.tex` now correspond to `../main.tex`. The prior packet's binary PDF, page renders, intermediate build logs, and packet-level inventories are not included in this text-only publication. The original validation record describes the intermediate failures; it does not imply they were successful. A fresh build and three-page inspection were completed again for publication. No PDF is committed, consistent with the author's earlier instruction that compiling TeX is sufficient.

To build from the repository root:

```bash
cd submissions/code_mit_2026
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

Use `submissions/code_mit_2026/main.tex` as the CODE compilation entry point, not the historical copy under `author_review/original/`. Recheck the page count after adding final author metadata or making approved edits.

`cce-experiments` remains canonical. `main` receives only this submission folder by selective synchronization. The AISTATS manuscript, experiment source, canonical review bundle, and locked evidence are outside this publication change. Publishing files on GitHub does not establish that the Overleaf project has pulled them.
