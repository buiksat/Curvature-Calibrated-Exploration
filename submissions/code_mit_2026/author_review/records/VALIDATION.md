# Candidate build and validation

**Executed work:** isolated LaTeX revision, compilation, page rendering, source comparison, patch application test, and evidence/approval record preparation. This is not a generated Codex handoff. No commit, push, publication synchronization, or submission occurred.

## Build result

Command, executed from the candidate directory:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

Final result: **3 pages**, including references and the visible author-review marker. The PDF is letter-sized, 612 by 792 points, and 192,094 bytes. Body text remains 10pt and margins remain 0.95in. Table footnote size and bibliography small size are unchanged from the original formatting. No margin, body-font, display-skip, or paragraph-skip reduction was used to obtain the page count.

Toolchain: latexmk 4.86; pdfTeX 3.141592653-2.6-1.40.26 (TeX Live 2025/dev/Debian); Git 2.47.3. No new dependency was required.

The final LaTeX log contains no unresolved citations/references, package warnings, errors, overfull boxes, or underfull boxes. All three final pages were rendered and visually inspected: equations, inequality factors, table headings, cells, and captions are readable and unclipped, with no overlap or missing glyphs. The theorem continues from page 1 to page 2 without lost text. The final references are on page 3.

## Mathematical and empirical transcription checks

The original reference-recursion, regret-RHS, pseudo-response/ridge/center equations match the candidate after whitespace normalization. The original transported-score expression and corrected-radius expression occur unchanged, including historical 1/sigma scaling, addition of historical envelopes before squaring, the factor sigma^2+G^2/lambda, transport coefficient, additive 2 sum b, and additive sum xi.

The candidate includes the path premise, both operator bounds, all-action solver validity, played-action sharpness, the same realized width map, the oracle inequality, and the pathwise joint event. Probability is stated through the union bound, not conditional on the certificate event. The abstract theorem does not assume reward noise or a reference parameter; those enter the corrected-center specialization.

All 16 mean-regret values match their exact method/target table positions and round to the requested two decimals from existing committed mean fields. Diagnostic units are checked in the source ledger and table caption: eligible checkpoints, trajectory maxima, and pooled seed-round inflation are distinct. Coverage cells and regret contrasts are not conflated. No interval-exclusion count, adjusted intervals, new statistic, or causal explanation was added.

`VALIDATION.json` records 45 completed local assertions. `SYMBOLS.md` records the manual definition/transcription checklist. These are validation of the proposed text and packet, not a new proof review, verified numerical certification, or raw experiment reproduction.

## Diff and patch

`git diff --no-index --check original/main.tex candidate/main.tex` emitted no whitespace diagnostics. It exits 1 because the two non-indexed files differ; this was distinguished from a whitespace failure using a local control example. Native repository `git diff --check` was unavailable because there is no checkout.

`git apply --check --whitespace=error-all` exited 0 in a temporary directory containing the baseline at `submissions/code_mit_2026/main.tex`. Applying the patch there also exited 0 and reproduced the candidate byte-for-byte. The temporary directory was removed. No shared work was changed.

## Resolved build/validation development errors

Build 01 exposed an amsthm/newtxmath openbox-definition collision; loading amsthm before newtxmath resolved it. Build 02 treated the author marker after a line break as an optional dimension; grouping the marker resolved it. Build 03 produced four pages. Removing repetition and condensing prose, without removing theorem conditions or shrinking text/margins, produced three pages from build 04 onward. Final build 06 includes the completed definition wording. All six build outputs are retained so failed intermediate builds are not represented as successes.

The newly written packet checker initially used the wrong name for a transcribed display-value field, assumed no-index diff returned zero for different files, and matched a package description containing the word warning. These checker errors were corrected to use the actual field, distinguish diff and whitespace status, and match actual LaTeX diagnostics. No repository tests were edited or weakened.

## Skipped or unavailable checks

There is no native repository checkout. The prior local artifact directory's `git status --short --branch` returns the error retained in `logs/git-status.txt`. Native Git access failed DNS. Read-only GitHub reads pinned to the canonical HEAD supplied source and evidence. The original local CODE files were matched to their live Git blob IDs and remained unchanged.

The repository-wide paper validator and CI were not run because their native checkout/dependencies were not assembled for this isolated candidate. No unrelated CI repair or locked-artifact regeneration was attempted. The large aggregate's recorded hash was read, not independently recomputed from its bytes. Raw trajectories were unavailable.

The linked public submission form returned 401; required fields and author/anonymity instructions remain unverified. The author block remains unresolved. Recheck page count after the final author metadata and any approved edits are inserted.
