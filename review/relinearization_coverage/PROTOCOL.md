# Relinearization coverage study: frozen evaluation protocol

Status: frozen before any evaluation seed was run. Its SHA-256 is recorded in
`PROTOCOL.sha256` and in every evaluation manifest; the analysis refuses run
directories whose manifests record a different hash. Development history is
in `DEVELOPMENT_PLAN.md` and `report/development.md`.

## 1. Questions

Primary: on a realizable learning trajectory, can naive substitution of the
current-metric width invalidate the reference confidence band, while endpoint
transport preserves coverage at informative widths?

Secondary (separate, descriptive): how do frozen-reference, naive-current and
endpoint-transport policies compare in cumulative pseudo-regret and coverage
on their own adaptive histories in the six-dimensional model?

A coverage result does not require, and is not evidence of, a regret
improvement.

## 2. Primary study (fixed)

- Model: h(u) = sqrt(W) tanh(u / sqrt(W)), mu_theta(phi) = h(phi theta),
  actions phi in {-1, +1} (tie-break order -1, +1), region [-R, R], R = 1,
  W = 6.25, lambda = 1, sigma = 0.25, delta = 0.05. Teacher theta_star = -R,
  used only by the environment and evaluator. Independent Gaussian potential
  outcomes with standard deviation sigma; the learner sees only the selected
  reward.
- Learner: theta_t = R for rounds 1..n, n = 8192, frozen-reference UCB with
  the corrected center; gradients q_s and pseudo-responses y_s stored at
  collection time. After round n, one projected batch step of
  L(theta) = (1/(2n)) sum_s (h(phi_s theta) - r_s)^2 from theta = R with
  eta = R / (2 h(R) h'(R)); its gradient is h'(R)(h(R) - (1/n) sum phi_s r_s)
  because h is odd, h' is even and phi_s^2 = 1 (unit test: finite difference
  and closed form). Horizon T = n + 1; round n + 1 is scored and no reward is
  observed. This is an intentionally controlled, delayed-update learner.
- Confidence construction (`experiments/relin_coverage.py`):
  beta_t = sqrt(gamma_{t-1} + 2 log(1/delta)) + sqrt(lambda) R
  + (1/sigma) sqrt(sum_{s<t} eps(s)^2), gamma_{t-1} = log det(Vbar_t / lambda),
  S = R, no misspecification term (exact realizability).
  Widths: sbar = |q| / sqrt(Vbar_t); s = |q| / sqrt(V_t) with V_t by dense
  replay of all historical inputs at theta_t; d_Th = max |log eig(V_t, Vbar_t)|.
  Radii: r_frozen = beta sbar + b, r_naive = beta s + b,
  r_endpoint = beta exp(d_Th / 2) s + b, sharing history, query, center, beta
  and b. The frozen-reference score selects the action.
- Envelopes. Primary: the new certified-envelope variant
  eps(theta, phi) = max_{v in {-A, A, -x, x}} |h(v) - h(x) - h'(x)(v - x)|,
  x = phi theta, A = R |phi|, used for both the historical eps(s) (computed
  before r_s) and the current b_t(a). Comparison, separately labeled: the
  manuscript's envelope 0.5 (c_h / sqrt W)(R + |theta|)^2 on the same
  histories. Each comparison of widths uses one envelope throughout.
- Seeds: evaluation 50100-50355 (256 seeds). No other evaluation seed is run;
  the sample size is not changed after outcomes are seen.

## 3. Primary outcome and inference (fixed)

For seed i and construction j in {frozen, naive, endpoint} with the primary
envelope, F_ij = 1{exists t <= T, a: |mu*_t(a) - m_t(a)| > r_tj(a)}: one
binary observation per seed. Margin = |mu* - m| - r.

- Tolerance tau = 1e-9 (absolute, reward units). A naive failure counts only
  if margin > tau; a frozen or endpoint failure counts if margin > -tau.
  Sensitivity: tau in {0, 1e-6, 1e-3}. Crashed or nonfinite seeds count as
  naive non-failures and as frozen and endpoint failures; none is discarded.
- alpha = 0.05 (Monte Carlo), distinct from delta = 0.05 (confidence target).
  Three one-sided Clopper-Pearson bounds, each at level alpha/3:
  L_naive (lower), U_frozen (upper), U_endpoint (upper).
- Strong confirmed coverage result: L_naive > delta and U_frozen <= delta and
  U_endpoint <= delta. Every count and bound is reported regardless. A control
  upper bound above delta is inconclusive about calibration, not proof of
  invalidity.
- Recorded secondary coverage outcomes: any upper (optimism) failure
  mu* > m + r; upper failure at a truly optimal action; first failure round;
  maximum margin.

## 4. Informativeness and classification (fixed)

Feasible mean span for either action: 2 h(R). Reported: width ratio s/sbar,
endpoint factor exp(d_Th / 2), half-widths and interval length / span at
round T and at each seed's first naive failure state.

Classification, in order:
1. invalid or incomplete: any crash or nonfinite seed, fewer than 256 seeds,
   an endpoint-dominance violation (r_endpoint < r_frozen (1 - 1e-12)), dense
   replay vs sufficient statistics or accumulated vs dense reference matrix
   disagreeing by >= 1e-10 relative, a Thompson value off SciPy's generalized
   eigensolve by more than 1e-12 + 1e-9 |value|, a stored query that differs
   from its recomputation, a parameter outside [-R, R], or a current allowance
   below the realized teacher remainder;
2. no demonstrated naive-confidence failure: L_naive <= delta;
3. naive failure demonstrated, control calibration inconclusive: U_frozen or
   U_endpoint > delta;
4. confidence repair with informative intervals: otherwise, if the endpoint
   interval length / span at the first naive failure state is < 1 in every
   seed with a naive failure;
5. confidence repair achieved only through vacuous intervals: otherwise.

Regret bounds on the frozen behavior policy's own trajectory, labeled
separately: the direct sum of instantaneous bounds
sum_t [2 beta_t sbar_t(a_t) + 2 b_t(a_t)] and the determinant-potential bound
2 sqrt((sigma^2 + G^2/lambda) gamma_T sum_t beta_t^2) + 2 sum_t b_t(a_t),
G = 1, against the cap 2T min(1, sqrt W) and the feasible-range cap 2T h(R).
No regret guarantee is stated for the naive construction.

Scope restriction: both actions receive equal bonuses within each
construction, so all three scores select the same action on these histories.
The primary study tests confidence validity and cannot show a regret
advantage.

## 5. Secondary study (fixed)

- Environment, teacher, streams and optimizer of `experiments/transport_v3.py`:
  d = 6, K = 3, 12 categories, teacher seed 1729, sigma = 0.25, lambda = 1,
  R = 1, delta = 0.05, learning rate 3e-6, 5 steps per round, T = 20,000.
- Width: W = 100 (selected by the rule in `DEVELOPMENT_PLAN.md`;
  see `report/development.md`).
- Policies: frozen reference, naive current, endpoint transport, each on its
  own history, with the corrected center and the new certified-envelope
  variant in beta_t and b_t(a). Context and potential-outcome streams are
  shared within a seed; each learner sees only its selected reward.
- Seeds: evaluation 51100-51163 (64 seeds).
- Outcomes (descriptive, no hypothesis tests): mean cumulative pseudo-regret
  and SD; policy-minus-frozen paired differences with 95% seed-bootstrap
  intervals (10,000 resamples); own-construction coverage failures per seed
  (same tau rule), with two-sided 95% Clopper-Pearson intervals; s/sbar range,
  maximum d_Th; frozen and endpoint bounds (direct sum and determinant
  potential; endpoint uses h_t = 1 + exp(d_Th,t)) against the cap; runtime.
  The naive policy has no certified bound. Conclusions are conditional on this
  environment, teacher, optimizer and horizon.

## 6. Code, environment and commands

- Source snapshot: commit 14dd69585ff18c4ac9ca8aa920d94967bf485830 on branch `cce-relin-coverage`, with the
  SHA-256 of each source file in every manifest.
- Python 3.12 venv from `experiments/requirements-python312.lock`
  (preflight PASS), OPENBLAS/OMP/MKL/NUMEXPR threads = 1, at most 4 workers.
- Commands:

```
python -B -m experiments.relin_coverage --phase evaluation --seeds 50100-50355 \
  --output RUNS/primary_eval --workers 4 --protocol review/relinearization_coverage/PROTOCOL.md
python -B -m experiments.relin_policy --phase evaluation --seeds 51100-51163 \
  --widths 100 --output RUNS/secondary_eval --workers 4 \
  --protocol review/relinearization_coverage/PROTOCOL.md
python -B -m experiments.analyze_relin_coverage primary RUNS/primary_eval --out OUT --expected-seeds 256 \
  --expected-protocol-sha256 $(cut -d' ' -f1 review/relinearization_coverage/PROTOCOL.sha256)
python -B -m experiments.analyze_relin_coverage secondary RUNS/secondary_eval --out OUT \
  --expected-protocol-sha256 $(cut -d' ' -f1 review/relinearization_coverage/PROTOCOL.sha256)
```

- Budget: runtime measured in development (primary about 2.6 s per seed,
  secondary about 20 s per run) projects about 0.2 core-hours for the primary
  and about 1.1 core-hours for the secondary evaluation. A run that cannot
  finish within the eight core-hour total is reported as incomplete.
  Interrupted runs resume by skipping seeds that already have an output or a
  crash record; no seed is rerun.
