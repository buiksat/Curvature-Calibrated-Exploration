# Publication-stage checks

This is a publication of an existing proposed revision, not another scientific review. The author explicitly requested updating GitHub because coauthors cannot access the chat ZIP. Author approval of claim-affecting changes, final author metadata, and conference submission remain separate.

## Live starting refs

```
cce-experiments  1eb91932d89bb5df428052767884e199f2abfe3b
main             85e4399f380a329e0ea9fa6ac95c79ba3c6a59f0
```

Both were resolved through GitHub before preparing publication. Their CODE subtrees were identical (`299c967c20a5a07510242a6c13b9c28b2ef7cdf9`). The original CODE source blob was `9837cd16e04fbb803ebe77d3d76b766b8631a43e`; the original README blob was `d5f1c580ee3fb2570782c23923830fbe8e7fa9f8`. They match the retained baseline bytes.

## Artifact identity and build

The supplied revision archive's SHA-256 was verified as `958750ab839bec9db2154506e50c9c8ae4a58cae888be27cee6eef5b152f943d`. Every entry in its `SHA256SUMS` matched after extraction into a new temporary directory. No existing work was reset, cleaned, or stashed.

The published manuscript source is unchanged from that candidate:

```
SHA-256: c5aaafdcb5049e5b91b1d92582cf149f50dc7a271d5a3d90175c6a62467cf1cc
Git blob: da83925c52e22ba76f6338d959cc3152364f38f4
```

A fresh isolated build ran:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

Exit status: 0. Output: 3 pages, 192094 bytes, letter paper (612 by 792 points), including references and the visible review/author marker. The final LaTeX log has no unresolved citations or references, overfull boxes, or underfull boxes. All three pages were rendered and inspected. Extracted text matches the packet PDF exactly. The source retains 10pt text and 0.95-inch margins.

`git apply --check --whitespace=error-all` and `git apply` both exited 0 against an isolated copy of the baseline under the repository path. The result matched the candidate byte-for-byte. The manuscript patch introduces no whitespace errors; it is not to be reapplied on top of the already revised source. The archival `.patch` itself contains standard diff-context blank lines and is preserved byte-for-byte.

## Scope and publication mechanism

Changes are confined to `submissions/code_mit_2026/`: the revised source, a navigation/status addition to its README, and submission-local author-review records. The original README's historical provenance remains intact below the new status note; an exact baseline copy is retained in `author_review/original/README.md`.

The same submission subtree is used for the two publication commits. Each commit has exactly one parent on its own branch. No branch merge, full-research-tree synchronization, rebase, force update, experiment, locked-evidence regeneration, or conference submission is part of this operation. No change to the AISTATS `paper/` subtree is intended or authorized.

No native remote checkout was available: the local artifact directory is not a Git repository, and native `git ls-remote` failed to resolve github.com. GitHub tree/commit/ref APIs are used instead, with non-force ref updates and before/after remote checks. No native full-repository worktree or CI pass is claimed. This file records the checks before the ref updates; the final commit identities and remote state are reported after the updates.
