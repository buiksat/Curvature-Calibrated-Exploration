# Optional evidence checks completed

## A. Bound decomposition: existing, inspected, not newly calculated

The implementation already computes an ordered algebraic decomposition on each realized primary-policy trajectory. With

\[
P_t=(\sigma^2+G^2/\lambda)\gamma_t,\quad
S_t=\sqrt{P_t\sum_{i\le t}(2\beta_i^{\rm stat})^2},\quad
N_t=\sqrt{P_t\sum_{i\le t}(2\beta_i)^2},\quad
F_t=\sqrt{P_t\sum_{i\le t}[\beta_i(1+e^{D_{Q,i}})]^2},
\]

its four stored terms are `statistical_bound_component` = S_t, `historical_bound_component` = N_t-S_t, `path_inflation_component` = F_t-N_t, and `current_bias_cumulative` = 2 sum_(i<=t)b_i. Their sum is the sharp RHS. Here beta_stat includes the ridge norm term as well as the self-normalized noise radius. The order assigns the interaction between historical radius and transport to the path component.

Sources: [experiments/transport_instantiation.py#L1829-L1894](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/1eb91932d89bb5df428052767884e199f2abfe3b/experiments/transport_instantiation.py#L1829-L1894) (read lines 1740 to 1990) and [experiments/aggregate_transport_instantiation.py#L1220-L1258](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/1eb91932d89bb5df428052767884e199f2abfe3b/experiments/aggregate_transport_instantiation.py#L1220-L1258) (read 990 to 1260). The generator [experiments/make_transport_instantiation_artifacts.py](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/1eb91932d89bb5df428052767884e199f2abfe3b/experiments/make_transport_instantiation_artifacts.py) only formats/downsamples these already-recorded values.

The committed `bound_decomposition` contains 4000 rows: four targets x 1000 rounds, **means over 50 primary trajectories at each round**, all in the T=1000 experiment. Terminal records were read directly at these locations:

| Target | Committed record |
| --- | --- |
|0.25|[review/transport_instantiation/aggregate/bound_decomposition.part-000.jsonl#L1000](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/1eb91932d89bb5df428052767884e199f2abfe3b/review/transport_instantiation/aggregate/bound_decomposition.part-000.jsonl#L1000)|
|0.5|[review/transport_instantiation/aggregate/bound_decomposition.part-000.jsonl#L2000](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/1eb91932d89bb5df428052767884e199f2abfe3b/review/transport_instantiation/aggregate/bound_decomposition.part-000.jsonl#L2000)|
|1|[review/transport_instantiation/aggregate/bound_decomposition.part-001.jsonl#L608](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/1eb91932d89bb5df428052767884e199f2abfe3b/review/transport_instantiation/aggregate/bound_decomposition.part-001.jsonl#L608)|
|2|[review/transport_instantiation/aggregate/bound_decomposition.part-001.jsonl#L1608](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/1eb91932d89bb5df428052767884e199f2abfe3b/review/transport_instantiation/aggregate/bound_decomposition.part-001.jsonl#L1608)|

Their existing values, displayed here to six decimals for readability (unrounded transcriptions in `evidence/existing_terminal_decomposition.jsonl`):

|Target|Statistical component|Historical increment|Path increment|Current-bias sum|Sharp RHS|
|---:|---:|---:|---:|---:|---:|
|0.25|9948.391361|66.054595|205.389088|1.936707|10221.771751|
|0.5|9957.147286|132.676357|425.158761|3.893312|10518.875716|
|1|9979.499569|265.239259|911.466929|7.760095|11163.965853|
|2|10009.834477|530.935349|2051.738443|15.473126|12607.981396|

**Same-trajectory no-transport status.** `full_no_path_exploration` explicitly computes N_t internally. It is used to define the persisted historical and path increments. The inspected output schema does not separately persist a named no-transport total N_t+2 sum b_i or its standalone summary. No such new total, fraction, distribution, or comparison was computed for this candidate. These are evaluations on the primary policy's realized history, not an observed LinUCB baseline or the outcome of a different policy. This decomposition is more specific than historical-radius, width/potential, or sharp/simple tightness summaries, but does not identify a causal effect on policy regret.

The candidate retains no attribution of bound vacuity to transport alone. These decomposition values are in the review records, not added to the three-page manuscript.

## Terminal inflation: inputs exist, an existing summary was not found

The existing four medians 1.02, 1.04, 1.09, 1.18 summarize `exp(D_Q/2)` pooled over seeds and every round. The aggregator appends one value per seed-round and then calls `_describe`. They are not terminal medians or run-maximum medians.

The raw trajectory schema records `exp_bar_D_over_2` each round, but raw trajectories are not available in GitHub. The committed path-checkpoint extracts include terminal D_Q values. For example, [review/transport_instantiation/aggregate/path_checkpoints.part-012.jsonl#L1013](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/1eb91932d89bb5df428052767884e199f2abfe3b/review/transport_instantiation/aggregate/path_checkpoints.part-012.jsonl#L1013) is seed 149, target 2, T=t=1000 and contains D_Q=0.3872646956563499. This example verifies field availability, not a summary of the population. No exponential or terminal median was calculated from it.

Neither the inspected aggregator schema nor [review/transport_instantiation/aggregate/index.json](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/1eb91932d89bb5df428052767884e199f2abfe3b/review/transport_instantiation/aggregate/index.json) exposes per-condition terminal inflation summaries. A new terminal summary would need a specified seed/horizon/round grouping and author approval. It is omitted without blocking the revision.

## B. Normalized confidence slack: not recorded in accessible summaries

Requested statistic:

\[
\frac{\beta_t\bar s_t(a)+b_t(a)-|\mu_t^*(a)-m_t(a)|}
{\beta_t\bar s_t(a)+b_t(a)}.
\]

The implementation computes unnormalized actionwise confidence margins, then stores minimum/maximum margin, maximum shortfall, and binary all-action/prefix success flags. It does **not** store this normalized slack in the inspected record schema. Raw logs would contain `true_means`, `corrected_centers`, `frozen_widths`, `beta_t_corr`, and `current_bias`, which could support a future calculation. Those raw arrays are absent from the accessible review extracts. The aggregate section inventory contains no normalized-slack summary.

Sources: [experiments/transport_instantiation.py](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/1eb91932d89bb5df428052767884e199f2abfe3b/experiments/transport_instantiation.py) lines 1350 to 1650 and 1990 to 2225, especially `confidence_radii`, `confidence_margins`, and the raw record; [experiments/aggregate_transport_instantiation.py](https://github.com/buiksat/Curvature-Calibrated-Exploration/blob/1eb91932d89bb5df428052767884e199f2abfe3b/experiments/aggregate_transport_instantiation.py) lines 700 to 1260; aggregate index.

No slack was reconstructed from binary success, unnormalized minimum margin, or path diagnostics. No denominator-zero convention or aggregation rule was invented. An additional statistic would require original raw inputs, an explicit definition including zero-denominator behavior, and author approval. The three-page candidate omits it.
