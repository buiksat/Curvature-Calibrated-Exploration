# Full-profile development gate: completed, no tuning or evaluation

The full T1000 **development-only gate passed all 24 declared trajectories**: three W values (16, 1, 0.25), four methods, and development seeds 30000–30001. The predeclared development optimizer was learning rate 0.0003 with 20 steps per round. This is a numerical and execution feasibility check; it is not a tuned policy comparison or publication evidence.

The clean starting source revision was `dc2e2dc9e3f9f7ace8d5335fdf634cd31159c41a`. The retained run root is `/workspace/cce-full-development-check`; the source config SHA-256 is `caa289be9f6f95b4bf808af29238eccee4cebbbc4b2a6ac0f7f2a69edd46566d`, and the resolved full execution digest is `662bd97b87c523dd7168ed057004002a583aa4cb50759fdc24df027adc695117`. The run used four CPU workers, one BLAS thread each, and the recorded read-only quadrature-node cache. No GPU was required.

The original `run_manifest.json` reports `status=development_complete` and `evaluation_complete=false`. Its plan also lists 270 tuning and 600 evaluation trajectories for the full study, but **zero tuning and zero evaluation trajectories were run here**; there is no selection or aggregate artifact. All 24 development trajectories were new (`reused=0`). Development-phase elapsed time in `progress.json` was **358.36767304999967 seconds (5m 58.368s)**; summed per-trajectory elapsed times were 1392.1138693789994 seconds. The development-only launcher does not record `completed_at`; no total-study elapsed time is inferred.

A separate standard-library audit checked all 32 recorded source-file hashes, source-to-execution config resolution, run signatures and all 24 completion receipts, 120 raw/receipt file hashes, the exact Cartesian cell/seed grid, 24,000 raw rounds, and 2,400 declared quadrature checkpoints. It reconciled each summary with raw endpoint maxima, D_Q, terminal quantities, confidence prefixes and quadrature diagnostics; recomputed descriptive threshold counts; and checked stored finite values and reported failures. All checks passed. This audit reads stored values and checks their consistency; it does not rerun policies or independently recompute matrix factorizations.

The largest 1024-versus-2048 quadrature difference was `2.016374418545297e-7`; the largest difference divided by its unchanged configured scaled tolerance was `0.3125167135849128`. All stored convergence and path-inequality checks passed. Reference-confidence and method-optimism events held in all 24 development runs, including the naive control. These observations do not establish population coverage or verified numerical enclosures.

Descriptive drift counts below pool 8,000 rounds per W (four methods x two development seeds x 1000 rounds). They are dependent observations, not 8,000 independent replicates. Per-method/per-seed counts and exact maxima are preserved in `round_drift_summaries.jsonl`.

| W | Maximum endpoint d_Th | Maximum D_Q | d_Th>=0.01 rounds /8000 | d_Th>=0.1 rounds /8000 | d_Th>=1 rounds /8000 |
|---:|---:|---:|---:|---:|---:|
| 16 | 0.020528984 | 20.822190172 | 298 | 0 | 0 |
| 1 | 0.476822442 | 87.539746587 | 7959 | 617 | 0 |
| 0.25 | 0.990087861 | 175.792962026 | 7976 | 7329 | 0 |

Changing W changes the reward function as well as geometry. Large development drift does not imply that independently tuned evaluation policies will exhibit the same drift, or that transport improves regret. Full-profile tuning/evaluation remain pending and must use the prespecified disjoint tuning/evaluation seeds. This gate does not certify that every future trajectory will converge or avoid overflow.

The bundle preserves the original run/source/execution/progress documents, all 24 exact summary objects, original completion-receipt objects, raw hash inventory, derived drift summaries, audit report, and read-only verifier. `export_manifest.json` binds all transferred files. Raw trajectories remain external and must be retained; hashes alone cannot replay roundwise checks. The ordinary evaluation-export verifier is not applicable to this development-only schema.

Run the self-contained transferred-file integrity and internal-consistency check after GitHub transfer (no raw directory or third-party Python packages needed):

```sh
python3 review/transport_review_followup/full-development-check/audit_development.py
```

On a machine retaining the raw directory and a checkout with matching scientific source hashes, additionally repeat the stored-data audit:

```sh
python3 review/transport_review_followup/full-development-check/audit_development.py \
  --raw-root /workspace/cce-full-development-check \
  --repository /workspace/cce-research
```

The second command is a raw-log audit, not an experiment rerun. Paths can be adjusted after copying the retained raw directory; the recorded original run identity remains unchanged.
