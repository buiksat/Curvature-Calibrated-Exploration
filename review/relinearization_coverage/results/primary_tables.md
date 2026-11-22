# Primary study: seed-level simultaneous coverage

Seeds completed 256, crashed 0. delta = 0.05; alpha = 0.05, each one-sided Clopper-Pearson bound at alpha/3 = 0.016667; tau = 1e-09.

Classification: **confidence repair with informative intervals**

## Envelope: new certified-envelope variant (sharp)

| tau | naive fails | L_naive | frozen fails | U_frozen | endpoint fails | U_endpoint |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 256/256 | 0.9841 | 0/256 | 0.0159 | 0/256 | 0.0159 |
| 1e-09 | 256/256 | 0.9841 | 0/256 | 0.0159 | 0/256 | 0.0159 |
| 1e-06 | 256/256 | 0.9841 | 0/256 | 0.0159 | 0/256 | 0.0159 |
| 0.001 | 256/256 | 0.9841 | 0/256 | 0.0159 | 0/256 | 0.0159 |

| construction | upper fails | optimal-action upper fails | max margin (median) | half-width at T (median) | length/span at T (median) | length/span at first naive failure (max) |
|---|---:|---:|---:|---:|---:|---:|
| frozen | 0 | 0 | -0.0165 | 0.2871 | 0.3023 | 0.3023 |
| naive | 256 | 0 | 0.0177 | 0.2529 | 0.2662 | 0.2662 |
| endpoint | 0 | 0 | -0.0165 | 0.2871 | 0.3023 | 0.3023 |

Frozen-policy regret bounds (own trajectory): direct sum of instantaneous bounds median 6624.5; determinant-potential bound median 36633.7; caps: paper 16386, feasible range 15564.6.

## Envelope: manuscript's original envelope

| tau | naive fails | L_naive | frozen fails | U_frozen | endpoint fails | U_endpoint |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 0/256 | 0.0000 | 0/256 | 0.0159 | 0/256 | 0.0159 |
| 1e-09 | 0/256 | 0.0000 | 0/256 | 0.0159 | 0/256 | 0.0159 |
| 1e-06 | 0/256 | 0.0000 | 0/256 | 0.0159 | 0/256 | 0.0159 |
| 0.001 | 0/256 | 0.0000 | 0/256 | 0.0159 | 0/256 | 0.0159 |

| construction | upper fails | optimal-action upper fails | max margin (median) | half-width at T (median) | length/span at T (median) | length/span at first naive failure (max) |
|---|---:|---:|---:|---:|---:|---:|
| frozen | 0 | 0 | -0.6199 | 0.8907 | 0.9377 | n/a |
| naive | 0 | 0 | -0.5135 | 0.7844 | 0.8258 | n/a |
| endpoint | 0 | 0 | -0.6199 | 0.8907 | 0.9377 | n/a |

Frozen-policy regret bounds (own trajectory): direct sum of instantaneous bounds median 20628.6; determinant-potential bound median 112774.1; caps: paper 16386, feasible range 15564.6.

Realized pseudo-regret of the behavior policy: median 1.900 (min 1.900, max 1.900).
Width ratio s/sbar at T: median 0.85564; endpoint factor exp(d_Th/2) at T: median 1.16872.

Checks: argmax_agree_all_seeds=True, envelope_valid_current_all_seeds=True, theta_in_region_all_seeds=True, projection_occurred_seeds=0, replay_rel_max_below_1e-10=True, thompson_check_within_tolerance=True, stored_query_error_zero=True
