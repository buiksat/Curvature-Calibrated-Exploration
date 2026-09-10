# Execution and provenance

## Repository state

- Repository: `/home/buiksat/Curvature-Calibrated-Exploration`
- Origin: `https://github.com/buiksat/Curvature-Calibrated-Exploration.git`
- Original checkout: branch `cce-experiments`, clean, HEAD
  `5718995cae80f34b5b98b464f3d9090758be4871`
- Execution worktree: `/tmp/cce-codemit-QimOGs/worktree`, detached and initially clean
- Reviewed revision: `5718995cae80f34b5b98b464f3d9090758be4871`
- Execution baseline: `5718995cae80f34b5b98b464f3d9090758be4871`
- Coordinator-resolved starting `origin/cce-experiments`:
  `5718995cae80f34b5b98b464f3d9090758be4871`
- Coordinator-resolved starting `origin/main`:
  `5aa2fcebb542f576fe93b1d6b1441824e11b2c35`

`START_CCE == REVIEWED`; no intervening-change reconciliation was needed. The original
checkout had no CODE edits to incorporate.

The required proxied `git fetch origin` was attempted once and failed with exit 128:

```text
fatal: unable to access 'https://github.com/buiksat/Curvature-Calibrated-Exploration.git/': CONNECT tunnel failed, response 403
```

The coordinator established that `fwdproxy` denies `github.com` to `agent:codex`. No other
network access was attempted. End-of-task live remote resolution is unavailable in this
pane and must be performed by the coordinator. Local remote-tracking refs were not changed
by this task.

## Baseline identity

- `main.tex` Git blob: `da83925c52e22ba76f6338d959cc3152364f38f4`
- `main.tex` SHA-256: `c5aaafdcb5049e5b91b1d92582cf149f50dc7a271d5a3d90175c6a62467cf1cc`
- Existing CODE `SHA256SUMS`: 24 of 24 entries passed before any edit
- Exact baseline source and manifest: `baseline/main.tex` and `baseline/SHA256SUMS`
- All baseline tracked CODE hashes: `baseline/tracked_sha256.txt`

Packet identity and the quote-normalization exception are recorded separately in
`PACKET_INTEGRITY.md`.

## Revision roles

- Original CODE drafting SHA: `df8802dfacc1f8db61a0bbad9442f2c3037a8338`
- Historical execution/aggregation revision:
  `0cd6264c1f8b8751728f3c4a198207e8289aed74`
- Later implementation/reporting completion checkpoint:
  `93eaa537d2702d5d18b05905913b0b879e3d608f`
- Reviewed source and execution baseline:
  `5718995cae80f34b5b98b464f3d9090758be4871`
- Working candidate publication SHA: none
- Commit authorization: granted directly by the author on 2026-09-10 for this scoped
  candidate; the resulting detached commit is recorded in Git history and the execution
  report

The later completion checkpoint is not labeled as the execution revision. The working
candidate remains detached. Commit authorization does not authorize a push, branch move,
publication, or conference submission.
