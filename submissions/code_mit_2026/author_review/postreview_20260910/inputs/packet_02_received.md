**A and C are verified.** The candidate zero-path means and paired Hessian-minus-naive statistics are correct at the proposed rounding. **B is incomplete in this packet:** I did not finish extracting and validating all 200 terminal records, so I report no terminal quantiles.

## 1. Live Git state and evidence inspected

**Research branch:** `cce-experiments`
**Resolved HEAD:** `5718995cae80f34b5b98b464f3d9090758be4871`
All scientific reads were pinned to that revision; `main` was not used.

The current editing locations are `submissions/code_mit_2026/main.tex`, the **Controlled audit** section, table `tab:audit` and its caption, the paragraph immediately after that table, and **Implications for adaptive experimentation**. The current caption already labels the existing inflation medians as pooled over seeds and all rounds. Historical `main_revised.tex` locations are not needed.

I inspected the current approval and optional-analysis records; the controlled protocol and configuration; `confidence_radius`, `policy_scores`, stream construction, and bound-decomposition code; aggregation definitions; the review index; all four terminal mean-decomposition records; all 16 policy-outcome records; terminal-horizon validity and certificate-tightness records; selected path-checkpoint records; and the generated validity, tightness, and performance tables. The approval preference remains descriptive regret reporting without the bootstrap zero-exclusion count.

**Downloads:** [Full-precision calculations and verification limits](sandbox:/mnt/data/cce_code_postreview/postreview_packet.json), [read-only calculation script](sandbox:/mnt/data/cce_code_postreview/calculate_packet.py), and [complete packet](sandbox:/mnt/data/cce_code_postreview_packet.zip).

The following newly derived quantities are **"Post-review descriptive analysis of the locked evaluation."**

## 2. Verified terminal bound decomposition

### Algebra and attribution

Write

```math
\beta_t=\beta_{{\rm stat},t}+h_t,
```

where the implementation defines

```math
\beta_{{\rm stat},t} = \sqrt{\gamma_{t-1}+2\log(1/\delta)} +\sqrt{\lambda}R, \qquad h_t=\frac{\sqrt{\sum_{s<t}\epsilon_{\rm lin}(s)^2}}{\sigma}.
```

Thus, `beta_statistical` includes the **regularization/norm-bound term**, not just the noise-dependent square root.

For each primary-policy trajectory, the implemented decomposition is

```math
\begin{aligned} S_T&=2\sqrt{P_T\sum_t\beta_{{\rm stat},t}^{\,2}},\\ H_T&=2\sqrt{P_T\sum_t\beta_t^2}-S_T,\\ I_T&=\sqrt{P_T\sum_t\beta_t^2(1+e^{D_{Q,t}})^2} -2\sqrt{P_T\sum_t\beta_t^2},\\ C_T&=2\sum_t b_t. \end{aligned}
```

These correspond to `statistical_bound_component`, `historical_bound_component`, `path_inflation_component`, and `current_bias_cumulative`. Therefore

```math
\boxed{B_D=S_T+H_T+I_T+C_T}, \qquad \boxed{B_0=B_D-I_T=S_T+H_T+C_T}.
```

This matches the executable definitions.

The attribution is **ordered**: historical error is added at zero path inflation, then transport is added using the full radius. Consequently, interaction between historical radius and transport is assigned to `path_inflation_component`. These are not unique, orthogonal, or causal contributions.

### What the terminal records contain

The committed decomposition records are **means over 50 primary-policy seeds**, after evaluating the nonlinear bound separately on each trajectory. The aggregator stacks each trajectory's per-round components and averages along the seed axis. They are not per-seed records.

Because subtraction is linear,

```math
\overline{B_0}=\overline{B_D}-\overline{I_T}.
```

This calculation does **not** move a mean inside a square root.

### Results at `T=1000`

All rows use the original Hessian-policy trajectories. Bars denote means over 50 seeds.

| `D_{\rm target}\overline{B_D}`Mean path increment `\overline{I_T}\overline{B_0}100(\overline{B_D}/\overline{B_0}-1)\overline{B_0}/2000\overline{B_0}/\overline{R_H}` |           |          |               |            |        |          |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | ------------- | ---------- | ------ | -------- |
| 0.25                                                                                                                                                                 | 10,221.77 | 205.39   | **10,016.38** | **2.05%**  | 5.0082 | 123.5834 |
| 0.5                                                                                                                                                                  | 10,518.88 | 425.16   | **10,093.72** | **4.21%**  | 5.0469 | 122.4437 |
| 1                                                                                                                                                                    | 11,163.97 | 911.47   | **10,252.50** | **8.89%**  | 5.1262 | 117.7927 |
| 2                                                                                                                                                                    | 12,607.98 | 2,051.74 | **10,556.24** | **19.44%** | 5.2781 | 112.3137 |

The source records are `bound_decomposition.part-000.jsonl` lines 1000 and 2000, and `part-001.jsonl` lines 608 and 1608.

The calculated `B_0` means at stored float64 precision are:

```text
10016.382663153612
10093.716955391708
10252.498924226129
10556.242952839799
```

The corresponding percentage increases are:

```text
2.050531566434133
4.212112966395898
8.890192875433623
19.43625636452535
```

The full-precision inputs and all ratios are in the downloadable JSON. Summing the four stored mean components reproduces the stored mean sharp RHS to within `3.64\times10^{-12}`; this is an aggregate arithmetic check, not independent validation of the original trajectories.

**Supported interpretation:** removing the *explicit* transport factors leaves a large mean zero-path expression—5.01–5.28 times the deterministic cap and 112.31–123.58 times mean realized pseudo-regret. Explicit transport inflation therefore amplifies an already large expression.

**Not supported:** that every trajectory's `B_0` exceeds `2T`, that `B_0` is a valid guarantee for the executed Hessian policy, or that residual looseness is "the standard OFUL constant." The calculation retains the recorded histories, `\gamma_T`, confidence radii, and bias terms. It is neither a policy rerun nor an observed baseline.

The last three columns are **ratios of means**, not means or medians of per-run ratios. In particular, they must not replace the manuscript's existing median-per-run `B_D/R_T` statistic.

## 3. Terminal inflation: precise verification limitation

### What is verified

The existing values **1.02, 1.04, 1.09, 1.18 are pooled seed–round medians**. The aggregation code appends `\exp(D_{Q,t}/2)` for every round of every primary-policy run before summarizing. Each `T=1000` condition therefore has 50,000 seed–round values, not 50 terminal values.

| `D_{\rm target}`Existing pooled medianNumber of seed–round pairs |                    |        |
| ---------------------------------------------------------------- | ------------------ | ------ |
| 0.25                                                             | 1.0205263637773605 | 50,000 |
| 0.5                                                              | 1.0409388460308655 | 50,000 |
| 1                                                                | 1.085454149598788  | 50,000 |
| 2                                                                | 1.1785579103036254 | 50,000 |

These are stored in `certificate_tightness.jsonl`, records 9–12, field `exp_D_Q_over_2.median`. They are descriptive pooled summaries; the 50,000 pairs are not independent experimental units.

### What remains incomplete

**The checkpoint inputs are committed; this is not a missing-data finding against the repository.** The index lists 13 checkpoint shards containing 35,000 records. I did not complete retrieval and validation of the full 200-record terminal subset in this session.

| `D_{\rm target}`Terminal records extracted in this sessionSeeds not yet extracted |                      |         |
| --------------------------------------------------------------------------------- | -------------------- | ------- |
| 0.25                                                                              | 39/50, seeds 100–138 | 139–149 |
| 0.5                                                                               | 0/50                 | 100–149 |
| 1                                                                                 | 0/50                 | 100–149 |
| 2                                                                                 | 11/50, seeds 139–149 | 100–138 |

Accordingly, **no terminal median, quartile, minimum, or maximum is proposed**. Partial-seed summaries would not satisfy the requested analysis.

The supplied script reads all indexed shards, selects `horizon == round == 1000`, rejects duplicates and any seed/target mismatch, then computes the requested statistics. Raw trajectories are **not** required to finish this particular calculation.

The correct statistic is

```math
\operatorname{quantile}_p \left( \left\{e^{D_{Q,1000}^{(j)}/2}:j=100,\ldots,149\right\} \right),
```

with exponentiation **before** quantiles. The repository uses NumPy's default linear quantile convention; the script specifies `method="linear"` explicitly. ([NumPy](https://numpy.org/doc/2.2/reference/generated/numpy.quantile.html "https://numpy.org/doc/2.2/reference/generated/numpy.quantile.html"))

For an even sample, the median is the average of the two central **transformed** observations, generally not the exponential of the median `D_Q`. Neither this terminal statistic nor the pooled median determines the cumulative bound, which depends on the entire `\beta_t`-weighted path.

## 4. Paired policy comparison

Define

```math
\Delta_j=R_{H,j}-R_{N,j},
```

where `H=\texttt{transport\_hessian}` and `N=\texttt{naive\_current}`.

The stored paired field uses **naive minus Hessian**. I negated its mean, retained its paired SD and SE, and transformed its stored interval `[L,U]` to `[-U,-L]`.

| `D_{\rm target}`Mean `R_H`Mean `R_N`Mean paired `\Delta`Paired SDPaired SEStored 95% interval, sign-reversed`100\bar\Delta/\bar R_N` |           |           |               |          |              |                        |            |
| ------------------------------------------------------------------------------------------------------------------------------------ | --------- | --------- | ------------- | -------- | ------------ | ---------------------- | ---------- |
| 0.25                                                                                                                                 | 81.049561 | 79.003452 | **2.046108**  | 5.312015 | **0.751232** | [0.584106, 3.511934]   | **2.59%**  |
| 0.5                                                                                                                                  | 82.435547 | 79.489562 | **2.945985**  | 4.681694 | **0.662092** | [1.676612, 4.207852]   | **3.71%**  |
| 1                                                                                                                                    | 87.038497 | 80.097462 | **6.941035**  | 4.654294 | **0.658217** | [5.680470, 8.235519]   | **8.67%**  |
| 2                                                                                                                                    | 93.988891 | 81.882902 | **12.105988** | 5.766886 | **0.815561** | [10.506210, 13.701438] | **14.78%** |

All four cells have `n=50`. The stored values support both candidate endpoint examples.

The check

```math
\mathrm{SE}(\Delta)=\frac{\mathrm{SD}(\Delta)}{\sqrt{50}}
```

matches the stored SE in every cell at the precision used in the calculation. **No independent-method SE combination was used.** The percentages are ratios of means, not averages of per-seed percentage differences.

The means, paired SD/SE, and bootstrap intervals are existing prespecified summaries; sign reversal is a reporting transformation. The relative percentages are newly derived descriptive reporting. I did not replay the bootstrap or independently reconstruct the paired differences from raw trajectories.

### What is matched

At a common decision state, the two rules are

```math
U_H(a)=m^{\rm corr}(a)+\beta^{\rm corr}e^{D_Q/2}s(a)+b(a), \qquad U_N(a)=m^{\rm corr}(a)+\beta^{\rm corr}s(a)+b(a).
```

The score implementation differs only by the transport multiplier. Both calls use the same-form updater and method-independent context/noise child seeds. Each run initializes and maintains its own history.

This supports a **within-condition matched comparison of policy rules**, allowing downstream actions, histories, centers, radii, and widths to diverge. It does not compare identical realized quantities throughout the trajectories.

Across conditions, `D_{\rm target}` also changes `W`, hence the model. The cross-condition pattern therefore does not identify a transport-multiplier dose response.

The intervals remain **comparisonwise**, not simultaneous. They are included here for verification, not as a recommendation to restore the rejected zero-exclusion claim. Similar endpoint and naive sample means likewise do not establish equivalence.

## 5. Paste-ready results paragraphs

### Bound attribution

> In a post-review descriptive analysis of the locked evaluation, we set the explicit path factors to one while retaining each recorded Hessian-policy trajectory, including its confidence radii, information gain, and bias terms. At `T=1000`, the resulting mean zero-path expressions were 10,016.38, 10,093.72, 10,252.50, and 10,556.24 for `D_{\rm target}=0.25,0.5,1,2`, respectively. Explicit transport increased these means by 2.05%, 4.21%, 8.89%, and 19.44%. The zero-path means themselves remained 5.01–5.28 times the deterministic `2T` cap. Thus explicit transport inflation amplifies an already large expression; this same-trajectory calculation is neither a baseline-policy rerun nor a claimed guarantee with transport removed.

### Within-condition policy comparison

> On the 50 paired evaluation streams per condition, Hessian and naive-current mean pseudo-regrets were respectively 81.05 versus 79.00, 82.44 versus 79.49, 87.04 versus 80.10, and 93.99 versus 81.88. The paired Hessian-minus-naive differences were 2.05, 2.95, 6.94, and 12.11, with paired standard errors 0.75, 0.66, 0.66, and 0.82. The rules differ only in the explicit transport multiplier at a common state, but their adaptive histories may diverge. These are descriptive within-condition comparisons; changing `D_{\rm target}` also changes the model scale and does not isolate a cross-condition dose response.

The first paragraph is new descriptive analysis. The second combines existing means and paired uncertainty summaries without a significance claim. Inclusion of either paragraph remains an author decision.

## 6. Provenance ledger

All entries below use source revision
`5718995cae80f34b5b98b464f3d9090758be4871`.

Let `A/` denote `review/transport_instantiation/aggregate/`. The review index binds these extracts to the locked aggregate SHA-256
`0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02`.

| QuantityFile and record selectorField/statisticUnit and calculation |                                                                                                             |                                                                        |                                                           |
| ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | --------------------------------------------------------- |
| Mean `B_D,S,H,I,C` and mean regret                                  | `A/bound_decomposition.part-000.jsonl`: lines 1000, 2000; `part-001`: lines 608, 1608; `horizon=round=1000` | `sharp_theorem_rhs`; four named components; `cumulative_pseudo_regret` | Existing trajectory means; cumulative pseudo-regret units |
| Mean `B_0`                                                          | Same four records                                                                                           | Sharp RHS minus path component                                         | Newly derived mean; pseudo-regret units                   |
| Relative explicit path contribution                                 | Same records                                                                                                | `\overline{B_D}/\overline{B_0}-1`                                      | Ratio of means, multiplied by 100 for percent             |
| Zero-path expression relative to cap                                | Same records; `T=1000`                                                                                      | `\overline{B_0}/2000`                                                  | Dimensionless                                             |
| Zero-path expression relative to regret                             | Same records                                                                                                | `\overline{B_0}/\texttt{cumulative\_pseudo\_regret}`                   | Ratio of means; dimensionless                             |
| Hessian and naive means                                             | `A/policy_outcomes.jsonl`: Hessian lines 1,5,9,13; naive lines 4,8,12,16                                    | `cumulative_pseudo_regret.mean`                                        | Existing mean cumulative pseudo-regret                    |
| Paired mean `\Delta`                                                | Same naive records                                                                                          | Negative of `paired_difference_from_transport_hessian.mean`            | Pseudo-regret units                                       |
| Paired SD and SE                                                    | Same naive records, same paired field                                                                       | `standard_deviation`, `standard_error`                                 | Pseudo-regret units; check SD/`\sqrt{50}`                 |
| Paired interval                                                     | Same naive records                                                                                          | `bootstrap_mean_interval.ci_low/ci_high`                               | Stored `[L,U]\rightarrow[-U,-L]`; no replay               |
| Relative regret excess                                              | Paired and naive mean fields                                                                                | `100\bar\Delta/\bar R_N`                                               | Newly derived percentage, ratio of means                  |
| Existing pooled inflation medians                                   | `A/certificate_tightness.jsonl`, lines 9–12                                                                 | `exp_D_Q_over_2.median`; `n=50000`                                     | Dimensionless; pooled seed–round median                   |
| Requested terminal inflation                                        | All 13 indexed `A/path_checkpoints.part-*.jsonl` shards; select `horizon=round=1000`                        | Per-seed `exp(D_Q/2)`, then linear quantiles                           | **Not completed in this packet**                          |

The checkpoint records have no method column. Their primary-policy scope follows from the aggregator creating `path_points` inside the `PRIMARY_METHOD` loop; the index identifies the checkpoint extracts as those path points with `D_path_quad` present.

## 7. Reproducible calculation code

The [read-only script](sandbox:/mnt/data/cce_code_postreview/calculate_packet.py) reads SHA-pinned Git objects, checks extract hashes against the committed index, validates the terminal seed/target grid, and prints JSON. It does not import or execute experiment code.

```bash
python /path/to/calculate_packet.py \
  --repo /path/to/Curvature-Calibrated-Exploration \
  > /tmp/cce_code_postreview.json
```

Its essential calculations are:

```python
mean_B0 = record["sharp_theorem_rhs"] - record["path_inflation_component"]
uplift_pct = 100 * (record["sharp_theorem_rhs"] / mean_B0 - 1)
B0_over_cap = mean_B0 / 2000
B0_over_mean_regret = mean_B0 / record["cumulative_pseudo_regret"]

paired = naive["paired_difference_from_transport_hessian"]
mean_delta = -paired["mean"]
sd, se = paired["standard_deviation"], paired["standard_error"]
assert math.isclose(se, sd / math.sqrt(50))
ci = paired["bootstrap_mean_interval"]
reversed_ci = [-ci["ci_high"], -ci["ci_low"]]

# Only after exact seed coverage and uniqueness are established:
inflation = [math.exp(r["D_Q"] / 2) for r in terminal_records]
q25, median, q75 = np.quantile(inflation, [0.25, 0.5, 0.75], method="linear")
```

The numerical A/C functions were executed successfully. The terminal function was checked to reject the incomplete input set. The full Git-object reader and complete terminal calculation were **not** executed end-to-end here; that limitation is recorded in the packet's calculation log.

## 8. Verification packet for 05

| StatusFinding / handling              |                                                                                                                                                                                                                                          |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **VERIFIED**                          | The implemented ordered decomposition closes; `B_0=B_D-I_T` on the same recorded trajectory. Terminal decomposition rows are seed means. The four candidate `B_0` means and percentage uplifts are correct at manuscript rounding.       |
| **VERIFIED**                          | Stored paired means, SDs, SEs, and sign-reversed intervals agree with the supplied endpoint candidates. SE equals paired SD/`\sqrt{50}` in all four cells.                                                                               |
| **VERIFIED**                          | Existing inflation values 1.02, 1.04, 1.09, 1.18 are pooled seed–round medians. The current CODE caption already labels them correctly.                                                                                                  |
| **CORRECTED INTERPRETATION**          | `B_0` is a same-trajectory algebraic expression, not a baseline run or an automatic guarantee. Bound percentages and relative regret percentages are ratios of means. The "statistical" component includes the norm/regularization term. |
| **CORRECTED INTERPRETATION**          | Hessian and naive differ only in the multiplier **as rules at a common state**, not in otherwise identical realized trajectories. Cross-condition differences also involve changes to `W`.                                               |
| **UNAVAILABLE IN THIS PACKET**        | Complete terminal-inflation quantiles. The committed shards exist, but 150 terminal records remain unextracted here. Do not insert terminal statistics from partial data, pooled summaries, or trajectory maxima.                        |
| **UNAVAILABLE FROM THE MEAN RECORDS** | Per-seed `B_0` distribution and the count of trajectories with `B_0>2T`. No such count is inferred.                                                                                                                                      |
| **REQUIRES AUTHOR DECISION**          | Whether to add the new zero-path attribution and paired-SE reporting to CODE. Preserve the existing preference for descriptive regret and do not restore the bootstrap zero-exclusion count.                                             |

These calculations do not strengthen tolerance-based float64 diagnostics into exact mathematical-event verification, supply simultaneous inference across reused-seed cells, or identify why the policy regrets differ. No new `W=1`, `W=10`, or other experiment was run.