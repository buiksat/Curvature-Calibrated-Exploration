# Abstract revision validation

Completed locally on 2026-10-15 (America/Los_Angeles). This record covers the
current abstract/introduction sources and the matching release below. Earlier
chart and readability records describe their own snapshots.

## Change and scientific limits

The abstract is now a 250-word, single-paragraph narrative: contextual-bandit
problem and importance, the gap created by recomputing gradients, the conditional
transport approach, principal theoretical and experimental findings, and their
meaning. The title already matches this scope. Minimal introduction edits clarify
that retraining can change representations, transport starts from a valid band,
and the early empirical summary concerns one synthetic model.

The rewrite preserves the same-history/center/radius/bias width limitation,
exact actionwise recovery, no cross-history regret ordering, the 29-parameter
scaled-tanh experiment with four policies/three conditions/50 paired seeds,
all nine adverse pointwise paired comparisons, transport inflation, vacuous
transport and reference-policy bounds, and the limits of floating-point checks.
No improved-performance or universal-model claim is introduced. The 95% level
is drawn from the existing locked configuration, not a new analysis.

The sources actually read online and editorial decisions are recorded in
`submissions/tmlr_2026/ABSTRACT_REVISION.md` on both branches. The official style,
bibliography style, fancyhdr and licence also match their current upstream bytes.

## Preservation and provenance

The original checkout was clean before fetching; no stash, reset or overwrite
of user changes was needed. Fetch confirmed main at `341e191` and research at
`50fee83`. Research work used a separate Git worktree.

All three active abstract copies match. Forty-four active scientific manuscript
files match across the research sources and main mirror. Inactive historical
venue sources remain separate. All 270 checked theory, proof, experiment,
configuration, evidence, chart/table and historical-PDF files remain byte-identical
to the research baseline. All 218 previous numerical-ledger entries retain their
selectors, displays, provenance and recomputed values. One new entry binds the
explicit abstract confidence level to the existing 0.95 configuration value.

The semantic occurrence/file pins, compiled-source/tool hashes and tracked
release manifest were refreshed. All seven negative-finding guards remain;
two mutation phrases were adapted to the equivalent new wording. No assertion,
numerical tolerance or scientific condition was weakened.

The first strict package attempt failed because its identifier scanner treated
`0.09485744750460248` as a Git revision solely from seven shared digits. The
scanner now checks that the entire token is an actual known revision prefix.
One new regression preserves detection of genuine 7/8/12/40-character identifiers
in either case and the independent revision-field rule. Evidence was not edited
to satisfy the scanner. The ordinary strict rebuild then passed.

## Validation on this revision

- Locked CPython 3.12 environment: all 13 package-version pins match.
- Static manuscript checks, strict source closure, references/citations,
  layout, anonymity, provenance, archive membership and size gates: pass.
- Detached-evidence tests: 67 passed. Affected provenance selection: 85 passed,
  5 release-dependent skips before the release existed. Scanner selection:
  64 passed, 2 release-dependent skips before the release existed. Final
  archive integration: 4 passed without skips.
- The initial full repository run reported 738 passed, 3 skipped and 1 failed.
  Its committed-history whitespace guard found a blank line at EOF in the
  preceding handoff commit. The refreshed handoff already removed it; committing
  that correction made the guarded baseline-to-HEAD range clean. This was a
  state-dependent failure, not an unexplained flaky rerun.
- Full repository rerun on commit `189e9ce`: 739 passed, 3 skipped, 0 failed, 2 warnings in 187.33s.
- Current collection: 573 release-package cases, 742 repository cases;
  collection is distinct from execution. The three skips concern an absent user
  TEXMFVAR tree, a non-symlink TEXMFSYSVAR tree, and a historical hard-coded
  rebuild path. The independent fresh archive rebuild validates the bibliography
  and all 95 compiled inputs on this host.
- Repository numerical ledger: 607 PASS, 4 NOT_EXECUTED, 0 FAIL; 219 entries.
  One nonexecuted item is the repository-only source-closure preflight, which
  the separate strict package resolves. The remaining items require raw data.
- Fresh supplement extraction: all nine advertised verification steps pass,
  including 25 anonymous-contract checks, 23 study tests, chart/table and
  sidecar regeneration checks, and follow-up terminal interval reconstruction.
  Its ledger records 616 PASS, 38 PASS_ANON, 3 NOT_EXECUTED, 0 FAIL.
- Fresh source extraction: the 103-member archive rebuilds the PDF byte for
  byte; none of its 336 recorded input paths comes from either checkout.
  All 95 project-local compiled inputs validate.
- Visual review: pages 1–4 inspected at reading resolution; all 52 pages
  reviewed in rendered contact sheets for layout and page flow. Main and strict
  PDFs are byte-identical. No clipping, overlaps, missing glyphs or overfull
  boxes were found. The title, abstract and first-page assistance footnote fit.

Toolchain: CPython 3.12.14, pdfTeX 1.40.28 / TeX Live 2025 (Debian), latexmk
4.87 and BibTeX 0.99d. The user installed the required system Latin Modern
package; protected-input trust rules remained enforced. The final TeX log has
two compatibility warnings (a deprecated fontspec hook and changed showhyphens)
and underfull spacing diagnostics. Pytest emits AST deprecation warnings from
its pinned version. The final full run's two warnings come from intentional duplicate-ZIP-member
mutation tests. These are not unresolved references or test failures.

## Release and remaining limits

The PDF has 52 portrait pages. The strict source ZIP has 103 members; the
supplement has 190 members and uses 93,902,070 of the 100,000,000-byte limit,
leaving 6,097,930 bytes. The release manifest binds 95 project-local compiled
inputs and 239 protected external TeX inputs. Use the matching artifacts together.

| Artifact | SHA-256 |
| --- | --- |
| PDF | `a586d20810255d42f320bd1f8f346e881f41d095d134b0456d7a051ec388caef` |
| Source ZIP | `a2d69ef63f44920be07fe6b26720308a47f41d53993f1734bb9d1bcbde33f652` |
| Supplement ZIP | `c90bed4eeafd18c707bbff18b2832f55ff4d242ae7cd2841e9a7633505ad701e` |

No new experiments, full raw-trajectory replay, or external model review were
run. The original study's missing raw trajectories/per-seed inputs and the
follow-up raw-archive limitations remain. The compact supplement verifies its
retained evidence; it does not erase those limits. The paper has not been
submitted to TMLR. Final author review and OpenReview declarations remain the
authors' submission responsibilities.

Detailed local logs and independent archive records are under `work/abstract-*`;
`review/abstract_revision/VERIFICATION.json` records the checks and source hashes.

The full suite was run with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`, the
supported Python environment, `TMLR_OUT` pointing to the current strict release,
and `python -m pytest -q -ra tests experiments/tests`. The subsequent research commit
adds validation records only; the tested scientific sources and tooling retain
the hashes recorded in `VERIFICATION.json`.

After final record updates, the README artifact facts and both collection-count
guards pass: 3 passed, 570 deselected.
