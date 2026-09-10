# Candidate validation

## Source and input gates

- Execution worktree: detached at
  `5718995cae80f34b5b98b464f3d9090758be4871`, clean before editing.
- `START_CCE == REVIEWED`; there were no intervening changes to reconcile.
- Baseline `main.tex` blob and SHA-256 matched the task values.
- Baseline `sha256sum -c SHA256SUMS`: exit 0, 24 of 24 entries passed.
- Packet 01 and packet 02 do not match their original attachment digests. The received
  sizes, hashes, quote counts, diagnosed relay normalization, and proceed ruling are in
  `PACKET_INTEGRITY.md`.

## Manuscript checks

A parser extracted the packet-01 LaTeX blocks and compared them with current `main.tex`.
ABSTRACT, A02, A01, F02, C01, B01, B02, D01, and CONCLUSION each occur exactly once.
The F01 replacement and Nussbaum page completion are present. E01 is absent from
`main.tex`. AUTH01 is resolved as Bahram Behzadian, Meta; the review banner remains.

Citation and label scan:

```text
citations=abbasi2011improved,nussbaum1994finsler,riquelme2018deep,zhou2020neural
bibitems=abbasi2011improved,nussbaum1994finsler,riquelme2018deep,zhou2020neural
missing=
uncited=
unresolved_labels=
```

The table's 28 retained numerical cells and all new internal calculations are covered by
`CLAIM_TO_SOURCE.md`. The calculation script completed with exit 0 and reproduced the
same deterministic JSON on rerun.

## Build and rendering

See `BUILD_VALIDATION.md` for commands, hashes, and logs. Baseline build: exit 0, three
pages. First edit batch: exit 0, four pages. Final build: exit 0, four pages. The final log
has no unresolved citation/reference, package, overfull, underfull, or fatal diagnostics.

Ghostscript counted pages, extracted text, and rendered all four AUTH01 pages at 150 dpi.
All rendered pages were visually inspected. No clipping, overlap, broken symbol, or table
overflow was found.

Result: **PAGE-BUDGET BLOCKED**.

## Repository checks

- `git diff --check`: exit 0 before final manifest generation.
- Modified tracked files before manifest generation: current `README.md`,
  `author_review/README.md`, and `main.tex` only.
- Untracked project content is confined to `submissions/code_mit_2026/`: `main.pdf` and
  `author_review/postreview_20260910/`.
- No ignored build output remains in the execution worktree after `latexmk -c`.
- Historical `author_review/original/`, `records/`, `evidence/`, old patches, logs, and
  `PUBLICATION_CHECKS.md` are unchanged.
- No path outside `submissions/code_mit_2026/` differs from the execution baseline.

The final manifest checks and final status are recorded in the execution report after all
files are complete.

## Deliberately skipped

- No experiment, bootstrap, artifact generator, Buck suite, or pytest suite was run.
- No terminal-inflation quantile was computed.
- No network operation followed the single required fetch attempt.
- Live end-of-task remote resolution is unavailable to the `agent:codex` identity and must
  be performed by the coordinator.
