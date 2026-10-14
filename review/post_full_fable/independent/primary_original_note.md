# Original primary-history diagnostic

The two preserved Python scripts reproduce two read-only scans of the existing
150 primary (`transport_hessian`) evaluation histories: 50 seeds per W, T=1000,
150,000 rounds total. They do not rerun any experiment. The compact JSON is a
transcription of captured tool stdout, not the result of a second execution.
The parent audit is independently verifying all behavior histories and creating
an input hash inventory; this original scan did not hash its inputs.

Run each script with `/workspace/cce-research-env/bin/python`. Both print one JSON
object per W plus an elapsed-time line. The original raw-data root is embedded
in the scripts. No repository files or original result files were changed.

## Definitions

For the primary score, `c = corrected_centers`, `w = current_widths`,
`B = beta_t_corr * exp_bar_D_over_2`, and `b = current_bias`.
The coefficient B is multiplied first as a Python float, matching the original
left-associative expression. Reconstructed scores are `(c[j] + B*w[j]) + b`.
Every argmax uses the first maximizing index, as NumPy argmax does.

The sufficient width-dominance condition is
`B*(largest_width - second_largest_width) > max(c) - min(c)`.
The script checks it in float arithmetic and again using 250-digit Decimal
arithmetic applied to the stored doubles. Ties in the top widths make the
condition false. It is sufficient, not necessary.

The high-precision rank uses `Decimal.from_float` on each c, w, B, and b, then
250-digit arithmetic for `c + B*w + b`. This preserves the actual stored binary64
values as inputs. It does not recompute theta, the ridge solve, widths, beta,
exponentiation, or B in higher precision. Consequently it is a final-arithmetic
diagnostic, not a verified enclosure or a high-precision experiment.

The normalized float rank is `argmax(w[j] + c[j]/B)`; it is algebraically
equivalent over real numbers but still subject to binary64 rounding. Its
agreement with logged decisions does not itself establish exact rankings.

"All centers numerically absorbed" means all five stored scores equal
`B*w[j] + b` in binary64. It includes the 50 zero-center initial rounds per W.
"Some centers absorbed" additionally requires the affected center to be nonzero.
Top-score-gap ULP statistics exclude exact score ties, and top-width-gap minima
exclude exact width ties.

The historical/statistical beta ratio median is the ordinary median over all
50,000 dependent rounds per W, including initial zero historical terms. The
rounds are not treated as independent replicates.

Alternative endpoint/frozen/naive recommendations use their logged scores at
the primary behavior policy's states. Their one-step regrets are
`max(true_means) - true_means[recommended_action]`, averaged over all 50,000
rounds. These are not counterfactual cumulative regrets of adaptive policies.

## Findings and limits

For W=16/1/0.25, selected actions match first current-width argmax on
49,691/49,981/49,991 of 50,000 rounds. The sufficient strict width-dominance
condition holds on 48,552/49,686/49,754 rounds. This supports a descriptive
diagnosis of predominantly width-driven choices on the observed histories.

The high-precision final-arithmetic comparison finds 5/5/6 selected-arm
disagreements. All occur in rounds 2-10 and all exact score gaps are below
0.629 of the stored maximum score's ULP. These rare early differences can still
propagate through adaptive histories; neither their rarity nor their small
local score gaps establishes that they are harmless for cumulative regret.
No causal exoneration or causal decomposition follows from this scan.

Scores are reconstructed exactly in binary64 on every round. No nonfinite
score/coefficient or zero width occurs. Large-score absorption of centers is
distinct from tanh gradient saturation: with the declared parameter and feature
norm bounds, scored tanh arguments have magnitude at most 0.25/1/2, giving
gradient multipliers at least 0.9400/0.4200/0.07065.

Relevant original source lines in
`/workspace/cce-research/experiments/transport_instantiation.py`:

- 194-204: scalar certified bias envelope.
- 207-231: corrected center definition.
- 419-438: scaled tanh gradient.
- 779-781: parameter projection after the declared inner optimizer steps.
- 1546-1568: centers, widths, beta, and scalar bias on each behavior history.
- 1588-1605: four score arrays and first-index argmax selection.
- 1931-1938: stored true means, action, and regret.
- 1950-1956, 1974-1985, 2010-2015: stored diagnostic ingredients.
