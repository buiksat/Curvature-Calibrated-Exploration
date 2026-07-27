# Codex Handoff

Updated: 2026-07-27

## Start Here

- Repository: `/home/buiksat/Curvature-Calibrated-Exploration`
- Branch: `codex/closed-rates-20260721`
- Functional head before this handoff commit:
  `27576536f2bea62e5a0d9b49a7e0e010d18623bf`
- Last locally observed remote-tracking head:
  `eb35394c89f2646434fcbb29ee28a57f122dd6d8`
- The functional stack was eight commits ahead of that tracking ref and was a
  fast-forward from it. Recheck the actual remote before making assumptions.
- The worktree was clean before `HANDOFF.md` was added. No experiment, build, or
  shell session was left running.

The paper is **Curvature-Calibrated Exploration: Matrix-Free GGN Widths and
Conditional Regret Bounds**. The requested theory, experiment disclosure,
anonymity, provenance, and release-hardening work is committed. The principal
remaining external tasks are remote synchronization, anonymous artifact upload,
and migration to the official AISTATS 2027 style/checklist when available.

## Recent Commit Stack

From oldest to newest before this handoff:

1. `c80fe1a8` - remove reconstructible identities from anonymous releases.
2. `49c19ad0` - add direct PCG and reachable-raw-history regressions.
3. `de3a9c6f` - classify retained scaled-tanh transfer-audit failures.
4. `9ffac51b` - align paper language with holdout and numerical-audit evidence.
5. `0d74b267` - bind coverage/MNIST main-artifact provenance.
6. `362499a3` - add hydrated anonymous evidence assembly.
7. `99738015` - verify immutable raw inputs and every archive member.
8. `27576536` - reconcile the final revision audit documents.

Use `git log --oneline -12` to include the handoff commit itself.

## Validation State

The last complete code gates passed:

```bash
buck2 test //tests:tests //experiments/tests:tests -- --timeout=1200
```

Result: 2 targets passed, 0 failed, 0 timed out.

Focused release/provenance tests also passed:

```bash
buck2 run //tools:pytest_runner -- -q \
  tests/test_anonymous_supplement.py \
  tests/test_revision_paper_artifacts.py \
  experiments/tests/test_coverage_matched_operator_study.py
```

Result: 55 passed. The anonymous-supplement file alone has 49 passing tests.

The manuscript build and validation passed with the provisional repository
AISTATS 2026 style:

```bash
cd paper
latexmk -gg -pdf -interaction=nonstopmode -halt-on-error main.tex
python3 validate.py
```

The PDF has 72 physical pages, with the main body on pages 1--7 and references
starting on page 8. References/citations resolve, labels are unique, figures are
present, and the checked figures contain no Type 3 fonts. The known 5.1225 pt
abstract/style overfull warning remains. The official AISTATS 2027 kit and
checklist were not available, so final target-year format compliance is not
claimed.

## Final Anonymous Review Archive

The clean canonical assembly completed successfully:

```text
release_review/submission_bundle_final/
```

It was assembled from clean functional head `27576536`. The later handoff-only
commit is intentionally not part of that release payload. Rebuild the archive if
functional source, manuscript, generated evidence, or release tooling changes.

Important values from `ASSEMBLY_REPORT.json`:

- Archive: `anonymous_review_supplement.tar.gz`
- Archive bytes: `10,819,923,242`
- Archive SHA-256:
  `9f0e235bc2233260d95468c6a326b1794ea86dad0b4efdcbc605d4498020c837`
- Release manifest SHA-256:
  `f52719ab7495b9d82e7d7ada9df209829bcab2f8b71be135c964232bb17e390b`
- Released files: `253,635`
- Identity scan: passed over `253,608` manifest-counted files.
- Scaled-tanh files: `48,002`.
- Source worktree clean during assembly: `true`.
- Source-reference status: `passed_with_declared_unavailable_inputs`.
- Upload status: `not_uploaded`.

The final builder console summary additionally reported `253,211` indexed
source raw files across `3,929` selected runs. Those two counters are not fields
in `ASSEMBLY_REPORT.json`.

`REVISION_REPORT.md`, `REVISION_AUDIT.md`, and `REVISION_CHANGELOG.json` were
committed before the final clean assembly and therefore still describe that
assembly as pending. They remain accurate historical scientific/provenance
audits. For final archive status, counts, and hashes, the later local
`ASSEMBLY_REPORT.json` and `SHA256SUMS` are authoritative.

The complete checksum file was rechecked successfully:

```bash
cd release_review/submission_bundle_final
sha256sum -c SHA256SUMS
```

Do not commit `release_review/submission_bundle_final`; it is an ignored local
upload artifact of approximately 11 GiB. Upload the complete directory only
through an approved anonymous reviewer channel.

## Raw-Provenance Semantics

Do not collapse the following two counts:

- The preassembly source audit found `51,289` missing-reference occurrences.
- The transformed release metadata contains `54,361` occurrences after explicit
  rebinding/copying.
- Both resolve to the same `8,017` unique unavailable raw files.

These inputs are marked `not_in_source_tree`, not `indexed_not_released`.
Hydrated mode has zero indexed omissions. No unavailable input feeds a main-body
figure or table through tracked provenance. Four appendix artifacts depend on
`4,600` unique missing files; the remaining `3,417` occur in legacy
derived/provenance artifacts that do not feed a currently included figure or
table. See `REVISION_REPORT.md`, `REVISION_AUDIT.md`, and the release manifest
for the exact scope.

## Scientific Claims That Must Remain Suppressed

- Do not claim a nonvacuous scaled-tanh theorem instantiation. All 8,000 runs
  remain retained, but the joint theorem-event criterion failed.
- The retained scaled-tanh failures split into 106 analytic-premise failures and
  42 float64 transfer-audit failures; no mixed trajectory was observed.
- Do not call ordinary float64 point checks verified numerical enclosures.
- Do not claim a completed full Wheel evaluation. Full-profile tuning terminated
  on residual failures before evaluation; the Wheel smoke run is engineering
  evidence only.
- Do not claim faithful LO-FI/KFAC Wheel comparisons where those implementations
  are absent.
- Do not claim end-to-end scalability from the development-only systems run or
  from isolated JVP/VJP primitives.
- Do not identify the scaled-tanh `W` parameter with generic neural-network
  width.
- Do not claim full curvature is uniformly superior in regret.

## Remote Push Status

The last Codex push attempts did not reach GitHub:

- HTTPS failed DNS resolution for `github.com`.
- SSH through the configured `fwdproxy_ssh_proxy` returned HTTP 403 because
  `github.com` was not allowlisted for the `agent:codex` identity.

This is an execution-identity network restriction, not a Git-key or repository
error. From the user's normal terminal identity, first try the non-forced push:

```bash
git push git@github.com:buiksat/Curvature-Calibrated-Exploration.git \
  HEAD:codex/closed-rates-20260721
```

If it is rejected, fetch and inspect divergence before considering any force:

```bash
git fetch git@github.com:buiksat/Curvature-Calibrated-Exploration.git \
  refs/heads/codex/closed-rates-20260721
git log --oneline --left-right \
  FETCH_HEAD...HEAD
```

Do not force-push blindly. If a history rewrite is actually required, obtain the
current remote object ID and use a single-line `--force-with-lease=<ref>:<oid>`
command.

## Key Files

- Manuscript: `paper/main.tex`, `paper/main.pdf`
- Human audit: `REVISION_REPORT.md`, `REVISION_AUDIT.md`
- Machine audit: `REVISION_CHANGELOG.json`
- Theory derivations: `THEORY_DERIVATIONS.md`
- Anonymous builder: `tools/build_anonymous_supplement.py`
- Final assembly entry point: `scripts/assemble_submission_artifacts.sh`
- Release tests: `tests/test_anonymous_supplement.py`
- Main-artifact provenance test: `tests/test_revision_paper_artifacts.py`
- Local final report:
  `release_review/submission_bundle_final/ASSEMBLY_REPORT.json`

## Recommended Next Session Order

1. Run `git status --short --branch` and inspect the latest log.
2. Verify/push the branch from a network identity permitted to reach GitHub.
3. Confirm the remote head equals the local handoff commit.
4. Upload the complete anonymous review artifact through the approved channel
   and record the resulting reviewer-access location outside the anonymous paper
   if policy requires it.
5. When the official AISTATS 2027 kit appears, rebuild and repeat page, font,
   reference, citation, checklist, and overfull-box checks.
6. Preserve every failed experiment and all claim-suppression language unless a
   new, properly separated experiment changes the evidence.
