# Full controlled follow-up results

The full study completed **894 trajectories: 24 development, 270 tuning, and 600 evaluation**, with zero recorded deterministic audit failures. Evaluation used **T=1000, three W values (16, 1, 0.25), four methods, and 50 seeds per method/W cell**. Hessian-certified transport had higher mean regret than every comparator in every cell. These results do not support a regret-improvement claim for that policy.

Development seeds were 30000–30001, tuning seeds 30100–30109, and evaluation seeds 30200–30249. The splits are disjoint. All nine optimizer candidates were eligible. Independent uniform-random tuning selected **candidate-008: learning rate 0.0003, 20 steps per round**, using equal-weight mean prediction MSE over the 30 tuning seed/W cells; its score was `0.003921546618488996`. The same selection was applied to all four evaluation methods. See [selection](full-cce-full-local/selection.json), [configuration](full-cce-full-local/execution_config.json), and [aggregate](full-cce-full-local/aggregate_compact.json).

Mean terminal pseudo-regret is below; smaller is better. Displayed values are rounded, with exact per-seed outcomes retained in [seed summaries](full-cce-full-local/seed_summaries.jsonl). The endpoint method is a dense diagnostic oracle.

| W | Hessian transport | Endpoint oracle | Frozen reference | Naive current |
|---:|---:|---:|---:|---:|
| 16 | 185.100601 | 152.593420 | 151.784608 | 152.745725 |
| 1 | 182.900414 | 173.186939 | 173.195259 | 173.051761 |
| 0.25 | 176.439138 | 172.088840 | 171.875580 | 172.583508 |

All nine paired comparisons below use **comparator minus Hessian transport**, so negative differences favor the comparator. The stored bootstrap uses 10,000 resamples of the 50 matched evaluation seeds within each W, with recorded deterministic child seeds.

| W | Comparator | Mean difference | Pointwise 95% paired bootstrap CI |
|---:|---|---:|---:|
| 16 | Endpoint oracle | -32.507181 | [-33.032611, -31.997041] |
| 16 | Frozen reference | -33.315993 | [-33.787558, -32.860634] |
| 16 | Naive current | -32.354876 | [-32.827710, -31.904417] |
| 1 | Endpoint oracle | -9.713475 | [-10.019311, -9.389132] |
| 1 | Frozen reference | -9.705155 | [-9.987703, -9.416890] |
| 1 | Naive current | -9.848654 | [-10.190415, -9.503709] |
| 0.25 | Endpoint oracle | -4.350297 | [-5.109157, -3.572386] |
| 0.25 | Frozen reference | -4.563557 | [-5.642153, -3.485913] |
| 0.25 | Naive current | -3.855630 | [-4.693710, -3.032446] |

Every reported interval excludes zero, but these are **pointwise intervals without multiplicity adjustment**, not a simultaneous 95% confidence statement over nine comparisons. They quantify seed variability for this fixed synthetic design and tuning selection, not uncertainty over other environments or tuning samples. Changing W also changes the reward function, so across-W trends do not isolate a causal effect of drift. No universal policy-performance ordering follows.

Realized drift increased substantially. Primary-policy endpoint Thompson distance maxima were **0.044910633, 0.627414493, and 1.580971455**. Its exact threshold counts below have denominator **50,000 rounds per W**; these rounds are dependent, not independent replicates. See [drift diagnostics](full-cce-full-local/drift_and_reference_diagnostics.json) and [per-seed counts](full-cce-full-local/round_drift_summaries.jsonl).

| W | d_Th>=0.01 | d_Th>=0.1 | d_Th>=1 |
|---:|---:|---:|---:|
| 16 | 1495/50000 | 0/50000 | 0/50000 |
| 1 | 49789/50000 | 3804/50000 | 0/50000 |
| 0.25 | 49863/50000 | 45623/50000 | 286/50000 |

At W=0.25, 16/50 primary trajectories reached d_Th>=1. Corresponding endpoint-oracle, frozen-reference, and naive counts were 267, 316, and 279 rounds out of 50,000, reached by 16, 17, and 18 seeds out of 50. Target-D labels encode W at this horizon; they are not observed endpoint drift.

The primary mean theorem RHS was **6.51338e12, 3.07441e40, and 8.12281e83**, dominated by path inflation. Every primary trajectory's bound exceeded the applicable deterministic regret cap: **2000, 2000, and 1000**. The frozen policy's own-trajectory reference-geometry RHS means were **37638.629730, 120544.152075, and 230842.313232**; all 150 frozen trajectories also exceeded their caps. The [decomposition](full-cce-full-local/terminal_bound_decomposition.json) preserves each component. Removing a path component from a transport trajectory is accounting, not a counterfactual frozen-policy result; upper-bound comparisons alone imply no performance dominance.

Reference confidence and method optimism held in **all 600 evaluation trajectories, including the uncertified naive control**. Each method/W cell has 50/50 successes and a 95% exact coverage interval of approximately **[0.928878, 1]**. This does not establish nominal coverage or correction necessity. Floating-point audits are not verified numerical enclosures.

The [run manifest](full-cce-full-local/run_manifest.json) records source revision `707c8243ea6d5395369ed812a68cf7e27d700596`, `status=complete`, and `evaluation_complete=true`. Its retained `KeyboardInterrupt` error text documents an earlier user-requested pause; it is not the final run status. The retained external `progress.json` records evaluation-phase elapsed time **6003.685876 seconds (about 100 minutes), 600/600 completed, zero reused**. This excludes other phases and the earlier pause; the roughly two-hour manifest timestamp span includes the pause and is not pure computation time.

The aggregate's static `publication_ready=true` flag identifies its full-profile, 50-seed format; it does not establish TMLR submission readiness. The [portable export](full-cce-full-local/README.md) retains exact terminal outcomes and provenance for reproducibility. Full raw trajectories remain at `/workspace/cce-full-local` and must be retained for roundwise audits and regret-curve reproduction.
