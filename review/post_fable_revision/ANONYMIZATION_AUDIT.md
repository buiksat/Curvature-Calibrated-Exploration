# Independent anonymous follow-up evidence audit

Reviewed on 2026-10-14 in `/workspace/cce-research`. This review made no repository edits. The evidence transformations, package assembly, numerical adapter, and helper-import boundary were checked independently; a complete trusted TeX release was not produced by this audit.

## Result

No unresolved blocker was found in the anonymous follow-up evidence implementation. One standalone helper-import gap was found, reproduced, fixed by the implementation owner, and independently retested. At this audit snapshot, the compiled source-closure record, final archive-size gate, and complete supplement verification were still pending. The subsequent strict build, extracted-supplement verification and independent clean source rebuild passed; their final artifact hashes and results are recorded in [REVISION_VALIDATION.md](../../submissions/tmlr_2026/REVISION_VALIDATION.md). The sizes and test counts below remain the historical audit measurements.

The reviewed child helper is `tools/followup_anonymous_contract.py`, SHA-256 `8c0410993e78112101b07b66b01df469f7d822b7de201ea6c55178933b0b21b9`. The reviewed table generator is `tools/make_transport_followup_paper.py`, SHA-256 `153da33c998c3074e6fdabb9dc241157da5ff2bf0e9f401350699fa87a540496`. Both match independent pins in the parent anonymous-package contract. The parent contract and numerical text pins were being finalized separately; their whole-file hashes are not frozen by this report.

## Independent evidence checks

- Staged all 20 evidence inputs, comprising the complete 14-file full export, two independent-analysis files, and four relative-audit files, plus six pinned generated artifacts and the declaration.
- Compared parsed original and anonymous JSON recursively with an independent comparison, not the transformation's own allowlist. There were no schema, type, or scientific-number changes. Six numerical differences were confined to export-manifest file-size metadata. Changed strings were metadata paths, revision tokens, and their dependent digest references. The original JSONL observations were retained.
- Checked all three external-input inventories: 3,483 full-export rows, 3,004 independent-analysis rows, and 3,005 relative-audit rows. Original byte counts and SHA-256 values were retained, and renamed paths had no collisions. These hashes describe original unshipped bytes, not anonymous raw trajectories.
- Removed each of the 20 evidence files individually from an external staged fixture. Every omission failed package validation and prevented `original_digest` from attributing the original source hash.
- The unchanged export verifier recomputed all 24 terminal intervals from the 600 shipped seed summaries. This verifies those intervals; it does not independently replay the optimizer or reconstruct raw roundwise audits.
- The table generator's `--check` verified all six follow-up artifacts and retained historical artifacts unchanged.

The declaration has exact fixed contents. Its digests cannot be selected by editing the declaration itself. The child checks the full evidence and artifact set before original-source attribution; the parent, generator, and numerical adapter authenticate the exact root-relative helper before importing it. The ledger accepts anonymous mappings only in explicit required-package mode and still binds original hashes to its independently fixed original evidence pins. Repository mode retains its exact-original requirement.

## Package integration

Used the production `supplement_entries` and `anonymize` functions to stage an external reviewer tree. The inventory had 166 entries before the two declarations and 168 afterward, with no duplicate archive names. Preflight, post-transformation scrub, revision/identity scan, and the child contract all returned no findings. The original-input scrub exemption applies only before transformation; transformed files pass the full scan.

The production ZIP writer produced a stored archive of **93,664,308 bytes**, below the **100,000,000-byte** limit by **6,335,692 bytes**. CRC validation passed. This is before the compiled `SOURCE_CLOSURE` record and later finalization changes. It reaches the existing near-limit warning threshold, so the actual final archive must be checked again. An exploratory compressed ZIP also exists in the audit directory but is not the production-size result.

The packaging code retains its trusted external-input recorder checks, compiled-layout and reference checks, shipped-tool digest checks, full post-transformation identity scan, archive-size gate, and atomic pending-release publication. This audit did not relax or substitute for those gates. It did not claim a durable external raw-data URL or include the roughly 4.18 GB raw archive.

## Found and resolved

`anonymous_package_contract.py --list-pinned` originally used an ordinary unauthenticated child-module import and ignored `--root` for module location. A harmless marker in a disposable fixture demonstrated execution of a replaced helper through that standalone command. The normal supplement verifier was already protected by its explicit step-zero contract gate, so this was not a bypass of the normal full verification sequence.

The owner introduced `load_followup_contract(root)` and reused it in both the normal contract check and list mode. It requires the independent helper digest and loads the exact root-relative file before using any child constants. Independent rerun of the three new tests passed: pinned helper accepted, missing helper rejected, replaced helper rejected without executing its marker.

## Test results run by this reviewer

- Child contract tests: **14 passed**.
- Explicit package-mode and missing/replaced ledger-helper tests: **3 passed, 537 deselected** at that collection snapshot.
- Final exact-root list-mode tests: **3 passed, 542 deselected** at that collection snapshot.
- Direct generator and parent-contract missing/replaced-helper mutation checks rejected replacements before executing their markers.
- All 20 individual evidence omission checks rejected incomplete packages.
- Production-staged terminal export verification: **600 summaries, 24 recomputed intervals, passed**.
- Production-staged table regeneration check: **six follow-up artifacts verified**.

Fixtures remain external to the repository:

- `/workspace/cce-build/followup-independent-review-s5tlh0yh`
- `/workspace/cce-build/followup-integration-review-xkkjfcl_/reviewer`
- `/workspace/cce-build/followup-integration-review-xkkjfcl_/manual-stored-supplement.zip`

These are audit fixtures without a compiled source-closure manifest, not submission deliverables. Final full-suite counts and the trusted release build belong to the coordinating agent's final validation record.
