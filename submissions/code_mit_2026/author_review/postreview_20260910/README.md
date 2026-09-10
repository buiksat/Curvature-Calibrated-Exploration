# CODE@MIT post-review candidate, 2026-09-10

This directory records the commit-authorized author-review candidate based on
`cce-experiments@5718995cae80f34b5b98b464f3d9090758be4871`.

The approved scientific blocks were applied to `../../main.tex`, but the resulting PDF is
four pages against the three-page limit. The candidate is **PAGE-BUDGET BLOCKED**. No
approved condition or qualification was shortened to force a fit.

The manuscript remains an author-review candidate. Direct author instruction on
2026-09-10 resolved AUTH01 as Bahram Behzadian, Meta, and separately authorized committing
this exact candidate. The review banner remains. AUTH02, ledger:C01, ledger:C02, optional
analysis inclusion, and the page budget remain open. No push, branch update, publication,
or conference submission is authorized by this record.

## Record index

- `inputs/packet_01_received.md` and `inputs/packet_02_received.md`: exact bytes received
  between the embedded packet sentinels, excluding the delimiter newline.
- `PACKET_INTEGRITY.md`: expected-versus-received digest disclosure.
- `PROVENANCE.md`: repository, revision, worktree, and source-identity record.
- `baseline/`: pinned baseline source, manifest, numbered source, and tracked CODE hashes.
- `CHANGELOG.md`: block-by-block manuscript and navigation changes.
- `APPROVAL_ADDENDUM.md`: current approval boundary and review-only proposed text.
- `calculate_postreview.py` and `calculations.json`: bounded read-only reproduction.
- `CALCULATION_VALIDATION.md`: formulas, values, denominators, and interpretation limits.
- `CLAIM_TO_SOURCE.md`: manuscript and internal-analysis claim ledger.
- `main.before.numbered.txt` and `main.after.numbered.txt`: numbered source snapshots.
- `main.patch`: unified manuscript diff against the execution baseline.
- `BUILD_VALIDATION.md` and `build/`: build commands, logs, and extracted text.
- `renders/`: all four final pages rendered at 150 dpi.
- `HASH_CHANGES.md`: baseline and candidate digests for changed current files.
- `VALIDATION.md`: source, manuscript, build, and repository checks.
- `SHA256SUMS`: hashes for this review record, excluding itself.

## Scope

Only `submissions/code_mit_2026/` is changed in this detached worktree. Historical review
records remain unchanged. E01, paired standard errors, relative regret percentages, and
terminal-inflation quantiles are not in the manuscript.
