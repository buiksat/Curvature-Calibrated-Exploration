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
The 4.6 GB replay tree was deleted after the checks below; rerun the commands above to recreate `OUT` and `SRC`.
Seeds 30000-30249 were reused only to reproduce recorded runs; nothing from the replay is new evaluation data.

"Identical" below means exactly equal values after `compare_tree.py` skips the keys it names as volatile:
filesystem locations (`path`, `summary_path`, `selection_path`, `protocol_path`, `output`, `outputs`), keys
containing `sha256` or `digest`, timings, worker count, git and Python details, and the run's `error` text.
`compare_tree.py` exits 1 whenever any other value differs; the expected differences are listed.

| Check | Command | Exit | Result |
|---|---|---|---|
| Tuning selection | field diff of `selection.json` without path, hash and digest keys | | identical: candidate-008, lr 3e-4, 20 steps, same MSE |
| 600 evaluation summaries | `compare_summaries.py COMMITTED/seed_summaries.jsonl OUT` | 0 | 600 identical on every field except `runtime_seconds`, `config_digest` (hashes the worker count) and `selection_sha256` (the file embeds the output path) |
| Export | `compare_tree.py COMMITTED SRC/review/transport_review_followup/full-out` | 1 | development, tuning and seed summaries, selection, execution and source config, drift and reference diagnostics, round drift summaries, terminal bound decomposition, raw input inventory and run manifest identical. Expected differences: 87 in `aggregate_compact.json`, all bootstrap child seeds and bootstrap intervals (the bootstrap seed comes from the config digest, which includes the worker count, 4 then 32); 8 in `export_manifest.json`, all file byte counts (the files embed the output path). |
| Published intervals | `tools/verify_review_experiment_export.py review/transport_review_followup/full-cce-full-local` | 0 | 24 terminal intervals recomputed with the original seed from the summaries, which the replay reproduces |
| Relative-width audit | `tools/analyze_relative_transport.py --raw-root OUT --output-dir NEW`, then `compare_tree.py review/transport_relative_diagnostics/full NEW kernel_time timings benchmark elapsed` | 1 | `per_seed.jsonl` identical (600 records; the extra arguments skip kernel timings). Expected differences: 5 in `analysis.json` (input bytes, raw root, run signature, Python build, the run's error text) and 924 in `input_inventory.jsonl`, all byte counts |
| Stored-score scans | `symmetric_scan.py --raw-root OUT --repository SRC --output-dir NEW`, then `compare_tree.py review/post_full_fable/independent NEW kernel_time timings benchmark elapsed`; `primary_scan_original.py` and `primary_recommendations_original.py` with their hard-coded raw root replaced by OUT, compared count by count with `primary_original_results.json` | 1 | Expected differences: 3 in `analysis.json` (raw root, run signature, the run's error text), 923 inventory byte counts, and `primary_original_results.json` reported missing because it is a transcription compared separately. All 90 and 33 transcribed values identical, including 5/5/6 decimal rank mismatches with a largest gap of 0.628 ULP |
| Per-round recomputation | `check_raw.py OUT COMMITTED/seed_summaries.jsonl check_raw_600.json` | 0 | 600 runs, 600,000 rounds, no mismatch: radius terms, envelope, D_Q, the four policies' scores (exact binary64 equality), the selected action (exact first maximum), regret, and the summary sums `current_bias_cumulative` (= 2 sum b_t) and `frozen_width_sum` (= sum of squared played frozen widths), against both the replayed and the committed summaries |

`check_raw.py` uses only the logged fields and the paper's formulas; it does not import the harness. It
reconstructs each score with the simulator's association, centers + (beta * factor) * width + bias, so the
scores must match exactly. Other quantities must agree within 1e-10 * max(1, |a|, |b|) (an absolute 1e-10 below magnitude 1) and have the same shape. Every logged numeric field it reads must be finite, the optimism flag must be a JSON boolean, each record's round labels must match its position and its seed the run's, and the replayed and committed runs must be the same set with no duplicates.
It takes the logged centers, widths, gamma and Q_t as given; it does not rebuild those from the observations.
It also runs the two Phase 1 checks that needed raw logs (`AUDIT_REPORT.md`, A2 and A4):

- A2 medians per cell at t = 10, 100, 500, 1000 are in `check_raw_600.json`; the t = 1000 values lie in the
  Phase 1 brackets.
- A4, zero-width optimism m_t(a) + b_t >= mu*_t(a), over 1,000,000 action-round pairs per W:
  all hold at W = 0.25 (smallest margin 0.336); 16 fail at W = 1 (smallest -0.139); 7,382 (0.74%) fail at
  W = 16 (smallest -0.807). The paper makes no zero-width-optimism claim.

## Code review and fixes

Two read-only Codex reviewers read the simulation core and the analysis-to-paper pipeline. Both found no
defect that changes a published result. Their four should-fix findings are fixed:

- `eebaf5be`: the raw fields `D_Q_over_d_Th` and `D_Q_over_path_quad` use `numerics.ratio_denominator_tolerance`
  (1e-12), as the aggregator does; `policy_scores` evaluates only the selected policy's factor.
- `0b7a464e`: the study source inventory no longer requires `experiments/BUCK`, archived in `e3f41962`.
- `dc001d0e` and its follow-up: a run that resumes to success moves each earlier `error` into the list
  `resumed_after_errors`, oldest first, instead of leaving it next to status "complete".

`test_old_study_fixes.py` fails on the unfixed code and passes on the fixed code.
`regress_fixed.py OUT` reruns 12 evaluation trajectories (seed 30200, every W and method) with the fixed
code: every per-round field (presence and value) and summary equals the original-code replay, and
`policy_scores` is bitwise equal to the version at `d8c97288` on 8,000 random finite inputs.

With the author's approval, `tools/verify_transport_committed_evidence.py` acknowledges the two changed study
sources in `CURRENT_STUDY_SOURCE_COMPATIBILITY`, pinned to exact snapshot and current hashes, so the detached
verifier still fails closed on any other edit. The review bundle regenerates byte-identically.

Left unchanged:

- `tools/analyze_relative_transport.py` and `review/post_full_fable/independent/symmetric_scan.py` read the run
  manifest's `error` with `.get`, so for a run that resumes under the fixed driver they record `null` and do not
  report `resumed_after_errors`. Neither fails. Changing them would invalidate the script hashes recorded in their
  committed outputs, which were produced from the 2026-10-14 raw tree, whose manifest still has `error`.
- `submissions/tmlr_2026/release_manifest.json` still records the old hashes of
  `experiments/transport_instantiation.py` and `experiments/run_transport_instantiation_study.py`; the audit task
  forbids edits under `submissions/tmlr_2026/`.
