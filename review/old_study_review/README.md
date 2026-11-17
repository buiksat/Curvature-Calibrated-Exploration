# Review and replay of the 600-run study code (2026-11-17)

Checks run on branch `cce-transport-audit-v3` against the code behind Section 6's
600-trajectory study (run 2026-10-14 from `707c8243`, exported in
`review/transport_review_followup/full-cce-full-local/`). No published number changed.

## Replay

The whole original workflow (24 development, 270 tuning, 600 evaluation runs) was rerun from
a clean clone at `707c8243`, outside the repository, with the pinned numpy 2.2.3 and scipy 1.15.2
(Python 3.12.16 instead of the original 3.12.14) and 32 workers instead of 4:

```sh
git clone <repo> SRC && git -C SRC checkout --detach 707c8243ea6d5395369ed812a68cf7e27d700596
cd SRC && python -B tools/run_review_experiments.py --profile full --output OUT --workers 32
```

It exited 0 after 32 minutes and wrote its export to `SRC/review/transport_review_followup/full-out/`.
Seeds 30000-30249 were reused only to reproduce recorded runs; nothing from the replay is new evaluation data.

| Check | Command | Result |
|---|---|---|
| Tuning selection | field diff of `selection.json` without path, hash and digest keys | identical: candidate-008, lr 3e-4, 20 steps, same MSE |
| 600 evaluation summaries | `compare_summaries.py COMMITTED/seed_summaries.jsonl OUT` | 600 identical on every field except `runtime_seconds`, `config_digest` (hashes the worker count) and `selection_sha256` (the file embeds the output path) |
| Export | `compare_tree.py COMMITTED SRC/review/transport_review_followup/full-out` | development, tuning and seed summaries, selection, drift and reference diagnostics, round drift summaries, terminal bound decomposition and raw input inventory identical. `aggregate_compact.json` differs only in bootstrap child seeds and bootstrap intervals, because the bootstrap seed comes from the config digest. |
| Published intervals | `tools/verify_review_experiment_export.py review/transport_review_followup/full-cce-full-local` | exit 0; 24 terminal intervals recomputed with the original seed from the summaries, which the replay reproduces |
| Relative-width audit | `tools/analyze_relative_transport.py --raw-root OUT --output-dir NEW`, then `compare_tree.py` against `review/transport_relative_diagnostics/full` | `per_seed.jsonl` identical (600 records); `analysis.json` differs only in raw root, input bytes, run signature, Python build and the run's error text |
| Stored-score scans | `symmetric_scan.py`, `primary_scan_original.py`, `primary_recommendations_original.py` on OUT | `analysis.json` differs only in metadata; 90 and 33 transcribed counts identical, including 5/5/6 decimal rank mismatches with a largest gap of 0.628 ULP |
| Per-round recomputation | `check_raw.py OUT COMMITTED/seed_summaries.jsonl check_raw_600.json` | 600 runs, 600,000 rounds, no mismatch: radius terms, envelope, D_Q, the four policies' scores, argmax (exact ties go to the lowest index), regret, and the summary sums `current_bias_cumulative` (= 2 sum b_t) and `frozen_width_sum` (= sum of squared played frozen widths) |

`check_raw.py` uses only the logged fields and the paper's formulas; it does not import the harness.
It also runs the two Phase 1 checks that needed raw logs (`AUDIT_REPORT.md`, A2 and A4):

- A2 medians per cell at t = 10, 100, 500, 1000 are in `check_raw_600.json`; the t = 1000 values lie in the
  Phase 1 brackets.
- A4, zero-width optimism m_t(a) + b_t >= mu*_t(a), over 1,000,000 action-round pairs per W:
  all hold at W = 0.25 (smallest margin 0.336); 16 fail at W = 1 (smallest -0.139); 7,382 (0.74%) fail at
  W = 16 (smallest -0.807). The paper makes no zero-width-optimism claim.

## Code review and fixes

Two read-only Codex reviewers read the simulation core and the analysis-to-paper pipeline. Both found no
defect that changes a published result. The four should-fix findings are fixed in `eebaf5be`, `0b7a464e`
and `dc001d0e`; `test_old_study_fixes.py` fails on the unfixed code (4 of 4) and passes on the fixed code.
`regress_fixed.py OUT` reruns 12 evaluation trajectories (seed 30200, every W and method) with the fixed
code: every per-round field and summary equals the original-code replay, and `policy_scores` is bitwise
equal to the old version on 8,000 random finite inputs.

The fixes change `experiments/transport_instantiation.py` and
`experiments/run_transport_instantiation_study.py`, whose hashes `submissions/tmlr_2026/release_manifest.json`
pins; the manifest was not repinned.
