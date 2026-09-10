# Proposed revision provenance

Status: proposed CODE revision for author review, not approved or submitted. No GitHub writes were performed in this task.

## Revisions are different objects

| Role | Revision |
| --- | --- |
| Live canonical source HEAD, resolved before work | `1eb91932d89bb5df428052767884e199f2abfe3b` |
| Last observation supplied by author | `1eb91932d89bb5df428052767884e199f2abfe3b` |
| Change since that observation at start | None: exact SHA equality |
| Final canonical HEAD recheck | `1eb91932d89bb5df428052767884e199f2abfe3b`, unchanged |
| Historical execution/aggregation revision, recorded in aggregate metadata | `0cd6264c1f8b8751728f3c4a198207e8289aed74` |
| Later implementation/reporting completion checkpoint | `93eaa537d2702d5d18b05905913b0b879e3d608f` |
| Earlier research source used to draft original CODE derivative, retained in its README | `df8802dfacc1f8db61a0bbad9442f2c3037a8338` |

The aggregate's `git_revision` field was read in [review/transport_instantiation/aggregate/top_level.json](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/1eb91932d89bb5df428052767884e199f2abfe3b/review/transport_instantiation/aggregate/top_level.json). The distinction between the earlier locked selection and the later renderer completion is documented in [GITHUB_ONLY_TRANSPORT_REVIEW.md](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/1eb91932d89bb5df428052767884e199f2abfe3b/GITHUB_ONLY_TRANSPORT_REVIEW.md).

Recorded aggregate SHA-256: `0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02`. This is read from committed source records, not a newly calculated hash of the inaccessible 77 MB file. The raw experiment tree was not available and was not reproduced. No simulation, new bootstrap, adjusted interval, confidence-slack statistic, terminal-inflation summary, or new bound decomposition was computed.

## Original source retained

`original/main.tex` and `original/README.md` are untouched copies of the previously generated local files. Their native Git blob hashes match the live committed CODE files. SHA-256 values:

```
0eacb812076ac18f21d95b2684c19681e392ea8c4831caeb9894b417306e0c03  original/main.tex
3727e862862bd05f6b507575ff8db5e89b39bbfb29e26a83fc5bba757aabad05  original/README.md
```

The patch changes only `submissions/code_mit_2026/main.tex`. Supporting files live solely in this isolated delivery packet. The existing CODE README is copied unchanged into `candidate/README.md`; candidate-specific provenance is here, not substituted into its historical fields.

## Scope and access

The local source location was `/mnt/data/Curvature-Calibrated-Exploration`, a prior artifact directory, not a native Git checkout. `git status --short --branch` returned `fatal: not a git repository (or any of the parent directories): .git`. Native Git remote access failed DNS resolution. We used the live GitHub connector to read pinned source and a temporary copy to edit and compile.

`records/SOURCE_READS.json` records actual read ranges and returned Git blob IDs. The small JSON files under `evidence/` are labeled transcriptions of inspected fields; they are not byte-exact copies of whole canonical JSON files. Their own hashes protect this review packet, not the original raw inputs.

## Branch policy and unchanged sources

`cce-experiments` is canonical. `main` is a paper-only Overleaf/coauthor publication branch and was not used to resolve science. Neither branch was modified or synchronized. No change was made to `paper/`, `experiments/`, `results/`, `review/`, `tests/`, `tools/`, shared bibliography, or any locked artifact. No commit, push, PR, rebase, merge, shared reset, history rewrite, or submission was attempted.

## Existing validation caveat

The documented renderer divergence changes downsampling, histogram binning, and panel CSV filenames at the later completion checkpoint. It is not an input to tuning or aggregation. Its recorded current hash is `5886932695fabfcc174798e94c93d372a09ffa9f51543ce3e1bcdc7c9297ba16`; the recorded study-snapshot hash is `2c950ca777347a47e753f5bc6aa0c3e39bc8d17386de9f9e712b1f0a6733181b`. This task reads the locked tables and exact aggregate extracts; it does not regenerate them or use plot rendering to infer numbers. Unrelated CI was neither rerun nor repaired, and no CI pass is claimed.
