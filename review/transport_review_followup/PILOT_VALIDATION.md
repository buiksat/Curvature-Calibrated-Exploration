# Follow-up pilot validation

The T64 pilot completed **102 trajectories: 24 development, 54 tuning, and 24 evaluation**, with all configured deterministic audits passing. This validates the new execution and diagnostic workflow on the pilot grid. It does **not** establish that transport improves regret, provide publication-level statistical evidence, or validate the full T1000 study.

Evidence is the initial [pilot export](pilot-cce-review-pilot/README.md) and retained raw directory `/workspace/cce-review-pilot`. The export records four CPU workers, one BLAS thread per worker, no GPU, and elapsed time **514.817476 seconds (8m 34.817476s)** from `2026-10-14T00:55:16.602573+00:00` to `2026-10-14T01:03:51.420049+00:00`. These are the initial exported manifest timestamps; a later resume updates the external `run.json` completion time and must not be interpreted as original computation time. Summed per-trajectory runtimes were 1305.840993s development, 17.113965s tuning, and 620.210042s evaluation; concurrent worker times are not elapsed times.

The source config SHA-256 is `caa289be9f6f95b4bf808af29238eccee4cebbbc4b2a6ac0f7f2a69edd46566d`. The pilot started from a dirty checkout at `7bd8e4d78b62e1ea510da51deac7cc2c4624637d`; exact source/config/launcher hashes in [run_manifest.json](pilot-cce-review-pilot/run_manifest.json), rather than that Git revision alone, identify its inputs. Read-only inspection verified all 13 transferred-file hashes and all 315 original-input inventory hashes, confirmed all 102 raw summaries passed, and recomputed all 24 evaluation drift-count exports directly from raw trajectories.

Development seeds were 20000–20001, tuning seeds 20100–20101, and evaluation seeds 20200–20201. All three sets are disjoint. All nine optimizer candidates remained eligible. Independent uniform-random tuning selected **candidate-006, learning rate 0.0003, one step per round**, with equal-cell mean prediction MSE `0.015035873125461846`. The next candidate's MSE was `0.015038431293315668`; this small difference is a selection outcome, not evidence of a reliably superior optimizer. Selection SHA-256: `4878ce49371a2b6a1d93371d5141e91c3316c63295dfe69d7b4caac37f5c5419`.

All 24 development cases passed the 1024-versus-2048 quadrature comparison under the unchanged, scaled numerical tolerance. The largest absolute order difference was `5.97435799498669e-7`. Development uses the predeclared 20-step optimizer; its maximum endpoint Thompson distance across methods/seeds was 0.036850881, 0.491008765, and 1.331062902 at W=16, 1, and 0.25. These stress-run values must not be substituted for evaluation drift. Evaluation uses frozen order 2048; its summaries do not claim a per-run order comparison. These floating-point checks are not verified numerical enclosures.

Mean terminal evaluation pseudo-regret is shown below; each entry averages only two seeds. Displayed decimals are rounded; the linked JSON/JSONL files retain full precision.

| W | Hessian transport | Endpoint diagnostic oracle | Frozen reference | Naive current |
|---:|---:|---:|---:|---:|
| 16 | 10.951258 | 11.068414 | 11.068414 | 11.068414 |
| 1 | 11.141894 | 10.798140 | 10.917111 | 10.798140 |
| 0.25 | 10.759299 | 10.460906 | 10.650769 | 10.457250 |

Evaluation drift counts pool the 128 rounds from two seeds **within each method/W cell**. Counts at each threshold use `d_Th >= threshold`; rounds are not independent statistical replicates.

| W | Method | Maximum d_Th | >=0.01 rounds /128 | >=0.1 rounds /128 | >=1 rounds /128 |
|---:|---|---:|---:|---:|---:|
| 16 | Hessian transport | 0.001774848 | 0 | 0 | 0 |
| 16 | Endpoint oracle | 0.001888213 | 0 | 0 | 0 |
| 16 | Frozen reference | 0.001888213 | 0 | 0 | 0 |
| 16 | Naive current | 0.001888213 | 0 | 0 | 0 |
| 1 | Hessian transport | 0.034072429 | 57 | 0 | 0 |
| 1 | Endpoint oracle | 0.027253771 | 55 | 0 | 0 |
| 1 | Frozen reference | 0.027253771 | 55 | 0 | 0 |
| 1 | Naive current | 0.027253771 | 55 | 0 | 0 |
| 0.25 | Hessian transport | 0.127633795 | 88 | 10 | 0 |
| 0.25 | Endpoint oracle | 0.120451165 | 88 | 6 | 0 |
| 0.25 | Frozen reference | 0.120451165 | 88 | 6 | 0 |
| 0.25 | Naive current | 0.150370762 | 88 | 11 | 0 |

At W=0.25, one of two evaluation seeds per method reached d_Th>=0.1; no evaluation trajectory reached d_Th>=1. The selected one-step optimizer therefore produced appreciably smaller drift than the development optimizer. The primary method's maximum realized D_Q was 2.648041250, 10.385403658, and 20.379751422; the much larger target-D labels (24.440403706, 97.761614826, 195.523229651) encode W at T64 and are not realized drift measurements.

Reference confidence and method optimism held in all 24 evaluation trajectories, including the uncertified naive control. Two successes per cell give a 95% exact coverage interval of approximately [0.1581, 1], so this does not verify population coverage or show that the correction is necessary. Paired bootstrap output is retained for reproducibility, but two seeds cannot support a publication inference, even where a reported bootstrap interval excludes zero.

The primary mean theorem RHS was 5748.001854, 11399955.524430, and 229225235053.9131 at W=16, 1, and 0.25. All six primary theorem bounds exceeded the corresponding deterministic regret caps (128, 128, and 64 respectively). The frozen policy's own-trajectory reference-geometry RHS means were 1750.836780, 2954.254015, and 4555.723445, also above their caps in every seed. The export retains the statistical, historical, path, and current-bias decomposition. Subtracting a path component is accounting on one trajectory, not a counterfactual frozen-policy result; comparing upper bounds does not imply policy-performance dominance.

Changing W also changes the reward function/task, so comparisons across W are not an isolated causal effect of drift. The separate [full T1000 development gate](full-development-check/README.md) subsequently passed all 24 trajectories. Independent 10-seed tuning and 50-seed evaluation remain to be completed; the pilot selection must not replace that tuning. Keep the external raw trajectories: the portable export supports terminal-regret interval reproduction, but cannot independently replay all roundwise audits or regret-curve intervals.
