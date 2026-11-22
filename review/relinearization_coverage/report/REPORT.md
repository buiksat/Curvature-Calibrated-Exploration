# Relinearization coverage study: report

Date: 2026-11-21. Branch `cce-relin-coverage`; protocol
`PROTOCOL.md` (SHA-256 `742c3f1a58cd4b74819b3e4646dc11540c8ac70b7b306f775ae8526bb17cd2c3`),
frozen at commit `dd391771` before any evaluation seed ran. Code snapshot
`14dd6958`.

## Result

On a realizable scaled-tanh trajectory with a controlled delayed update,
replacing the reference width by the current width invalidated the
reference confidence band in 256 of 256 held-out seeds. The frozen-reference
and endpoint-transported bands covered in 256 of 256, at intervals spanning
0.302 of the feasible mean range. The preregistered strong criterion holds:
with each one-sided Clopper-Pearson bound at level alpha/3 = 0.0167,
L_naive = 0.9841 > delta = 0.05, U_frozen = 0.0159 <= delta and
U_endpoint = 0.0159 <= delta. The preregistered classification is
"confidence repair with informative intervals".

Limits that bound this result:

1. It is a constructed example. The teacher sits on the region boundary
   (theta* = -R), the representation is held at +R for 8192 rounds, and one
   batch step moves it to within 0.0036 of zero. It shows that the failure
   can occur on a realizable trajectory; it says nothing about how often it
   occurs under ordinary training. Because the teacher is on the boundary,
   the new envelope, computed only from theta_s, phi_s, R and W, equals the
   realized teacher remainder at every block round (exactly, all 256 seeds;
   unit test `test_scalar_block_envelope_equals_realized_teacher_remainder`)
   and exceeds it by at most 2e-7 relative at round 8193. The
   envelope is implementable and certified; it is also tight here, which
   leaves the naive band no slack from the allowance.
2. Endpoint transport and the reference width coincide here. In one
   dimension with V_t >= Vbar_t, exp(d_Th/2) s = sbar exactly, so endpoint
   coverage follows from frozen coverage and this example does not test
   endpoint transport as a distinct construction.
3. The failure depends on the envelope. With the manuscript's
   envelope on the same histories, the naive half-width is 0.784 against a
   center error of at most 0.277, and no naive failure occurs in 256 seeds;
   those intervals span 0.94 of the feasible range.
4. No regret consequence. Both actions receive equal bonuses within each
   construction, so all three scores select the same action at every round of
   every seed. Every naive failure is at the post-update round 8193; the
   violated upper bound is at the suboptimal action phi = +1 (with a lower
   violation at the optimal action), and no upper failure occurs at the
   optimal action.
5. The secondary policy study, in its preregistered cell W = 100, is nearly
   linear: current and reference widths differ by at most 0.25%, and
   it does not separate the three policies (details below).

## What was implemented

- `experiments/relin_coverage.py`: scalar scaled-tanh model class without the
  teacher; a learner that stores collection-time gradients, pseudo-responses
  and historical envelopes before each reward; the corrected center and
  confidence multiplier of Corollary "Corrected-center confidence"; dense
  replay of the current metric every round with a sufficient-statistic
  cross-check; Thompson distance; the delayed projected batch step; an
  evaluator that alone knows the teacher. All three widths are scored on the
  same pre-reward prefix; the frozen score selects the action.
- New certified-envelope variant: eps = max over v in {-A, A, -x, x} of
  |h(v) - h(x) - h'(x)(v - x)|, x = phi^T theta, A = R ||phi||, zero for
  phi = 0. Derivation checked: the signed remainder has derivative
  h'(v) - h'(x), and h' = sech^2(./sqrt W) is even and strictly decreasing in
  |v|, so interior critical points are v = +-x, which lie in [-A, A] when
  ||theta|| <= R; as theta* ranges over the radius-R ball, phi^T theta* covers
  [-A, A], so this is the exact supremum. The manuscript's envelope
  0.5 (c_h / sqrt W)(R + ||theta||)^2 is kept as a separately labeled
  comparison on identical histories.
- `experiments/relin_policy.py`: frozen, naive and endpoint policies on their
  own histories in the `transport_v3` environment, with the new envelope.
- `experiments/analyze_relin_coverage.py` and `plot_relin_coverage.py`:
  every reported number is recomputed from saved roundwise records.

The delayed step is the gradient step for L(theta) = (1/(2n)) sum_s
(h(phi_s theta) - r_s)^2: dL/dtheta at R equals
h'(R)(h(R) - (1/n) sum phi_s r_s) because h is odd, h' is even and
phi_s^2 = 1. With mean rewards and theta* = -R, sum phi_s r_s / n = -h(R), so
the step lands exactly on theta = 0.

## Checks run

| Check | Command or source | Result |
|---|---|---|
| Unit tests (16) on the frozen snapshot | `pytest experiments/tests/test_relin_coverage.py` | 16 passed, exit 0 |
| Envelope vs independent numerical supremum (dense grid plus bounded refinement), 160 random (W, A, x), W in {0.25, 1, 6.25, 100} | test | formula never below numerical sup by more than 1e-12 and never above it by more than 1e-9 |
| Envelope never exceeds the manuscript's envelope; zero for phi = 0; rejects parameters outside the region | test | pass |
| Gradient step vs central finite difference of the stated loss and vs the closed form | test | relative error below 1e-7 (finite difference) and 1e-12 (closed form) |
| Linear-model limit: reference and replayed metrics, widths, scores agree | test | exact equality |
| Stored gradients and pseudo-responses use collection-time parameters | test and every evaluation seed | recomputation error 0.0 |
| Future rewards cannot change pre-reward scores | test (rewards perturbed from round 100) | rounds up to 100 identical |
| Teacher and unselected potential outcomes cannot enter the learner | test (teacher changed with outcomes held fixed; unselected outcomes perturbed) | learner records identical |
| Dense replay vs sufficient statistics; accumulated vs dense reference matrix | every round of every evaluation seed | max relative discrepancy 1.04e-14 |
| Thompson distance vs SciPy generalized eigensolve | 8 checkpoints per evaluation seed | within 1e-12 + 1e-9 |value| |
| Spectral orientation: exp(d/2) s >= sbar; sqrt(lambda_max) correct; sqrt(lambda_min) fails | test; every round of every seed | pass; 0 dominance violations |
| Parameters in the certified region; projection | every seed | all in [-R, R]; projection never active |
| Current allowance >= realized teacher remainder | every round of every seed | pass |
| Port of `transport_v3.run_corrected` (original envelope) | test, three policies | identical regret |
| Deterministic sanity values | `--phase deterministic` and test | 0.85564, 0.27038, 0.28711, 0.25290 (targets 0.856, 0.270, 0.287, 0.253) |
| Analysis re-run on artifacts extracted from the archives | `package.sh` | CSVs and tables byte-identical; summaries identical except the run-directory path |

Not run: the repository's full test suite __SUITE__; an independent code
review; an Overleaf compile (no manuscript file changed).

## Primary results (256 evaluation seeds, 50100-50355)

New certified-envelope variant (primary):

| Construction | Seeds failing | One-sided CP bound (level 0.0167) | Max margin: min / median / max | Upper failures | Upper failures at an optimal action | Half-width at T | Length / span at T |
|---|---:|---:|---|---:|---:|---:|---:|
| naive current | 256 / 256 | L = 0.9841 | 0.0095 / 0.0177 / 0.0245 | 256 | 0 | 0.2529 | 0.266 |
| frozen reference | 0 / 256 | U = 0.0159 | -0.0247 / -0.0165 / -0.0097 | 0 | 0 | 0.2871 | 0.302 |
| endpoint transport | 0 / 256 | U = 0.0159 | -0.0247 / -0.0165 / -0.0097 | 0 | 0 | 0.2871 | 0.302 |

Margin = |mu* - m| - r. Every naive first failure is at round 8193. The
counts are identical at tau = 0, 1e-9, 1e-6 and 1e-3; no case fell within
tau = 1e-9 of zero. No seed crashed or produced a nonfinite value.

At round 8193: s/sbar = 0.85564 (all seeds, to five digits),
exp(d_Th/2) = 1.16872, center error 0.2624-0.2774 (median 0.2706),
theta_new in [-0.0032, 0.0036].

Manuscript's envelope on the same histories (comparison): 0 / 256 naive,
0 / 256 frozen and 0 / 256 endpoint failures; median half-widths 0.7844
(naive) and 0.8907 (frozen, endpoint); length / span 0.826 and 0.938; median
max margins -0.5135 and -0.6199.

Regret, frozen behavior policy's own trajectory (T = 8193): realized
pseudo-regret 1.900 in every seed (one pull of phi = +1 at round 1). Bounds
with the new envelope: direct sum of instantaneous bounds 6,624 (below the
caps 2T min(1, sqrt W) = 16,386 and 2T h(R) = 15,565); determinant-potential
bound 36,634 (above both caps). With the manuscript's envelope: 20,629 and
112,774, both above the caps. No bound is stated for the naive construction;
here the naive and endpoint scores select the same actions as the frozen one,
so their policies would have followed the same trajectory.

Figure: `results/primary_halfwidths.pdf`.

## Secondary results (64 evaluation seeds, 51100-51163, W = 100, T = 20,000)

Three policies, each on its own adaptive history; within a seed all three
share the context and potential-outcome streams, and each learner sees only its
selected reward. 192 runs, 0 crashes, 0 replay-check failures, 0 endpoint
dominance violations.

| Policy | Mean regret (SD) | Minus frozen: mean [95% seed bootstrap] | Own-construction coverage failures [95% CP] | Potential bound: median (max) | Direct-sum bound: median | Bound below cap 40,000 |
|---|---:|---:|---:|---:|---:|---:|
| frozen reference | 48.25 (4.92) | --- | 0 / 64 [0, 0.056] | 22,199 (22,348) | 2,990 | 64 / 64 |
| naive current | 47.73 (5.24) | -0.53 [-1.42, 0.36] | 0 / 64 [0, 0.056] | uncertified | uncertified | --- |
| endpoint transport | 47.55 (5.55) | -0.70 [-1.60, 0.20] | 0 / 64 [0, 0.056] | 22,210 (22,351) | 2,990 | 64 / 64 |

Paired-difference SDs: 3.67 (naive) and 3.67 (endpoint). On every policy's
own history, none of the three radii failed coverage in any seed and no upper
failure occurred. Across all runs s/sbar lies in [0.9999, 1.0025] and
d_Th <= 0.0049; median interval length / span of the policy's own radius is
0.070. The context-free benchmark's mean regret is 9,366.7.

Both paired intervals include zero, so this cell does not separate the three
policies. That is expected when current and reference widths differ by at
most 0.25%. The intervals are descriptive; no test was preregistered. This
cell has a non-vacuous frozen bound but negligible curvature, so it does not
supply a cell with both substantial curvature and a non-vacuous bound.
Figure: `results/secondary_paired_W100.pdf`.

## Compute

Primary evaluation 256 seeds in 169 s wall on 4 workers (2.58 s per seed on
average, 0.18 core-hours). Secondary evaluation 192 runs in 984 s wall on 4 workers (20.3 s per run on average, 1.08 core-hours). Development used about 0.05
(primary) and 0.78 (secondary) core-hours. Total about 2.1 core-hours,
within the 8 core-hour budget.

## Still unsupported

- That naive substitution fails under ordinary (non-delayed, non-boundary)
  training; this study constructs the failure.
- That endpoint transport differs from the reference width in coverage; in
  the scalar example they are equal by algebra.
- Any regret advantage of transport. The primary example cannot show one by
  design; the secondary cell shows no paired difference resolvable from zero in a nearly linear cell.
- Any statement about the manuscript's original envelope beyond "no naive
  failure observed in this example".
- Generalization beyond the selected environment, teacher, optimizer,
  horizon and W; changing W also changes the reward function.

## Development

Four configurations were investigated (P1, S1-S3); see `development.md`.
P1 was kept unchanged. W = 100 was selected by the rule written in
`DEVELOPMENT_PLAN.md` before development runs. One analysis defect (a
relative-only tolerance in the Thompson cross-check) was fixed during
development; no run record changed.
