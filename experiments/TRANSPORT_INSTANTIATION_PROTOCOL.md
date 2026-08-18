# Transport-instantiation experiment protocol

Protocol version: 1

Status: preregistered. This protocol and
`experiments/configs/transport_instantiation.yaml` must be committed before any
full-profile evaluation run. The full configuration, selection artifact, code
revision, and raw-input inventory are immutable once locked evaluation starts.

## 1. Scientific purpose

This study executes the revised corrected-center transported-UCB score in a
controlled finite-dimensional nonlinear model. It answers five questions.

1. Does the float64 implementation satisfy the corrected-center algebra and
   deterministic metric-transport inequalities within a fixed, scale-aware
   tolerance?
2. How conservative is the analytic Hessian/\(Q_t\) certificate relative to
   the exact endpoint Thompson distance and a high-accuracy numerical integral
   along the selected synthetic factor path?
3. Does the transported score exhibit the theorem's simultaneous reference
   confidence and optimism behavior?
4. Is the cumulative theorem bound informative or vacuous across controlled
   near-linearity conditions, including a finite path bound above one?
5. How does the primary certified policy compare descriptively with a frozen
   reference score, a dense endpoint-distance oracle, and an intentionally
   uncertified current-width score?

The study audits a theorem instantiation. It does not prove the theorem, claim
that full curvature uniformly improves regret, or turn ordinary floating-point
checks into verified numerical certificates.

## 2. Scope

The experiment uses exact dense frozen and current matrices, float64 Cholesky
solves, exact finite action enumeration, and exact score maximization with the
smallest-index tie rule. In theorem notation,

\[
\alpha_t=1,\qquad
\kappa_{-,t}=\kappa_{+,t}=1,\qquad
\xi_t=0.
\]

It deliberately excludes CG and PCG, approximate operators, diagonal or
low-rank curvature, stale or windowed curvature, subsampling, action screening,
generic MLPs, large networks, real data, legacy benchmarks, exponential-family
rewards, and verified floating-point interval arithmetic. Operator and solver
approximation are reserved for a later experiment.

## 3. Frozen configuration

The checked-in configuration uses JSON syntax valid as YAML and schema version
1. The full profile fixes:

| Quantity | Value |
| --- | ---: |
| Maximum and primary horizon | 1000 |
| Reported horizons | 250, 500, 1000 |
| Context dimension \(p\) | 4 |
| Action count \(K\) | 5 |
| Parameter dimension \(d=p+K+pK\) | 29 |
| Feature bound \(B_\phi\) | 1 |
| Parameter radius \(R\) | 1 |
| Noise standard deviation \(\sigma\) | 0.25 |
| Statistical ridge \(\lambda\) | 1 |
| Training ridge \(\lambda_{\rm train}\) | 1 |
| Confidence failure level \(\delta\) | 0.05 |
| Target path labels | 0.25, 0.5, 1, 2 |
| Bootstrap resamples | 10,000 |

Each horizon is an independent run. Its model scale \(W\) depends on that
horizon, so a horizon-250 result is not extracted as a prefix of a horizon-1000
run. The full locked grid has

\[
50\text{ seeds}\times3\text{ horizons}\times4\text{ target conditions}
\times4\text{ methods}=2400
\]

evaluation trajectories.

The smoke profile fixes 32 maximum rounds, horizons 16 and 32, target labels
0.5 and 2, and one seed per split. Smoke evaluation therefore contains 16
trajectories. Smoke output is never publication evidence.

## 4. Environment

### 4.1 Contexts and features

At round \(t\), sample

\[
x_t\in\{-1,+1\}^4/2.
\]

For action \(a\in\{0,1,2,3,4\}\), form

\[
\widetilde\phi(x_t,a)
=
\begin{bmatrix}
x_t\\ e_a\\ x_t\otimes e_a
\end{bmatrix},
\qquad
\phi(x_t,a)
=
B_\phi
\frac{\widetilde\phi(x_t,a)}{\|\widetilde\phi(x_t,a)\|_2}.
\]

The implementation uses the exact NumPy ordering of
`numpy.kron(x, one_hot_action)` everywhere, including teacher construction and
tests. Every feature has norm exactly \(B_\phi=1\), up to float64 roundoff.

### 4.2 Structured teacher

The teacher puts zero mass in the context-only and action-only blocks and all
mass in the context-action interaction block. Five regular-simplex vectors in
\(\mathbb R^4\) define the five action interactions. Construct the canonical
simplex from the four-column Helmert basis for the subspace orthogonal to the
all-ones vector in \(\mathbb R^5\), then scale its rows to unit norm. Generate
a \(4\times4\) standard-normal matrix with NumPy `PCG64` at teacher seed 1729,
take its QR factorization, and flip each column of \(Q\) so the corresponding
diagonal entry of \(R\) is nonnegative. Right-multiply the simplex by this
orthogonal matrix. Insert the five rotated rows using the exact feature-map
ordering above, then scale the complete parameter once so that
\(\|\theta^\circ\|_2=R\).

The same teacher is used for every method, target condition, horizon, and study
seed. No evaluation seed is selected or rejected based on teacher behavior.
The aggregate reports, without filtering:

- entropy of the optimal action;
- number of distinct optimal actions;
- average optimality gap;
- regret of the best fixed action;
- regret of a context-free mean-only baseline.

The context-free baseline is an online policy, not an oracle. In its first
five rounds it selects actions 0, 1, 2, 3, and 4 once in index order. On every
later round it selects the smallest index attaining the largest empirical mean
of that action's previously selected rewards. It observes only its selected
reward and ignores every context. It uses the same context and potential-noise
streams for its `(seed, horizon, target_D)` cell. The baseline is computed once
per cell as an environment diagnostic and is not a fifth study method or part
of the 2400-method-run grid.

### 4.3 Scaled-tanh mean and noise

For \(z=(x,a)\),

\[
\mu_{\theta,W}(z)
=
\sqrt W\tanh\!\left(\frac{\phi(z)^\top\theta}{\sqrt W}\right),
\]

with gradient

\[
q_\theta(z)
=
\operatorname{sech}^2\!\left(
\frac{\phi(z)^\top\theta}{\sqrt W}
\right)\phi(z).
\]

Writing \(u=\phi(z)^\top\theta/\sqrt W\), its Hessian is

\[
\nabla_\theta^2\mu_{\theta,W}(z)
=
-\frac{2}{\sqrt W}\operatorname{sech}^2(u)\tanh(u)
\phi(z)\phi(z)^\top.
\]

Thus

\[
G=B_\phi,
\qquad
L_\mu=L_g=\frac{c_h}{\sqrt W},
\qquad
c_h=\frac{4B_\phi^2}{3\sqrt3}.
\]

Exact realizability holds:

\[
\mu^*(z)=\mu_{\theta^\circ,W}(z).
\]

For each horizon \(T\) and target label \(D_{\rm target}\), set

\[
W(T,D_{\rm target})
=
\left[
\frac{4c_hR\sqrt{T-1}}
{\sigma\sqrt\lambda D_{\rm target}}
\right]^2.
\]

Use this positive real value directly in float64. Do not round \(W\) to an
integer or identify it with a hidden-layer width or parameter count.

The label is a worst-case trust-region design value. It is not the realized
path certificate. The \(D_{\rm target}=2\) condition is intentional. The
theorem permits any finite path length, while its score or regret bound may be
vacuous there.

Before interaction, generate a \(T\times K\) table of independent
\(N(0,\sigma^2)\) potential noises. A policy observes only the chosen entry:

\[
r_t=\mu_{\theta^\circ,W}(z_{t,a_t})+\eta_{t,a_t}.
\]

Contexts and potential-noise tables are common across methods for a fixed
study seed and are also shared across target labels. Only selected rewards
enter each policy's history. This preserves conditional independence of the
revealed noise and gives paired common random numbers.

## 5. Representation update and tuning

Each method owns its history and representation path. Set \(\theta_1=0\). At
the end of round \(t\), after observing only the selected reward, define

\[
\mathcal L_{t+1}(\theta)
=
\frac{1}{2\sigma^2}
\sum_{s\le t}
\left[r_s-\mu_{\theta,W}(z_{s,a_s})\right]^2
+\frac{\lambda_{\rm train}}2\|\theta\|_2^2.
\]

Starting at \(\theta_t\), take a fixed number of full-batch gradient steps at
a fixed learning rate, then project onto \(\{\theta:\|\theta\|_2\le R\}\).
This produces \(\theta_{t+1}\). The current reward never enters the current
round's score. The optimizer objective, gradient norm, projection occurrence,
and parameter displacement are logged. No optimizer residual enters the
confidence radius or theorem score.

Only two optimizer values are tuned:

```text
learning_rate:   [0.00003, 0.0001, 0.0003]
steps_per_round: [1, 5, 20]
```

Development policy runs that precede an optimizer selection use the frozen
bootstrap setting `learning_rate=0.0001` and `steps_per_round=5`. This setting
exists only to exercise policy code and quadrature before selection. Smoke
evaluation consumes the smoke selection artifact, and full evaluation consumes
the full selection artifact. The development setting is never used for locked
full evaluation unless the tuning rule independently selects that exact pair.

The initially suggested larger grid was optional. This protocol uses a smaller
scale because the loss is a sum, not a sample average. At
\(T=1000\), the positive semidefinite Jacobian contribution has operator norm
at most

\[
\frac{TG^2}{\sigma^2}+\lambda_{\rm train}=16001.
\]

Its reciprocal is about \(6.25\times10^{-5}\). The frozen grid brackets that
scale and includes one faster stress candidate. The nonlinear residual-Hessian
term can increase realized curvature, so finite values alone do not make a
candidate valid. The deterministic rejection rules below remain binding.

Tuning uses a separate uniformly random behavior policy. For a fixed tuning
seed, horizon, and target condition, every optimizer candidate receives the
same contexts, potential outcomes, and behavior actions. Candidate selection
does not depend on any UCB method's choices.

Full tuning uses seeds 10 through 19 and a burn-in of 100 rounds. Smoke tuning
uses seed 10 and a burn-in of 8 rounds. A candidate is rejected if any tuning
run has a nonfinite value, failed SPD check, radius violation, deterministic
algebra failure beyond tolerance, or optimizer divergence. Among candidates
that pass every seed, horizon, and target condition, select the smallest grand
mean all-action prediction MSE after burn-in. First average over
post-burn-in rounds and actions within each `(seed, horizon, target_D)` cell.
At round \(t\), this MSE uses prefix-trained \(\theta_t\) and all current-action
simulator means before revealing the round-\(t\) reward.
Then give every cell equal weight when averaging its mean. This prevents the
longer horizons from contributing more observations and dominating selection.
Exact ties are broken by fewer steps, then smaller learning rate.

Simulator truth is used only on tuning seeds and only for this representation
stability criterion. It does not change \(\delta\), the bonus, \(W\), either
ridge, methods, horizons, evaluation seeds, or reporting endpoints.

The selection JSON records all nine candidates, every component and pooled
criterion, rejection reasons, the deterministic ordering, the selected pair,
the resolved-config digest, a hash inventory of every study source file, and
the complete hashed tuning-input inventory. Before starting, evaluation must
verify the selection byte hash and config digest, recompute the eligible
minimum and deterministic tie-break from the hashed tuning summaries, and
confirm that the frozen source-file inventory has not changed.

## 6. Corrected center, confidence radius, and metrics

For each selected historical item, store \(z_s\), collection parameter
\(\theta_s\), collection query \(q_s=q_{\theta_s}(z_s)\), pseudo-response, and
certified historical envelope. At round \(t\), form

\[
\bar V_t
=
\lambda I
+\sigma^{-2}\sum_{s<t}q_sq_s^\top,
\]

\[
y_s
=
r_s-\mu_{\theta_s,W}(z_s)+q_s^\top\theta_s,
\qquad
\widehat\theta_t^{\rm lin}
=
\bar V_t^{-1}\sigma^{-2}\sum_{s<t}q_sy_s.
\]

For every current action,

\[
m_t^{\rm corr}(a)
=
\mu_{\theta_t,W}(z_{t,a})
+q_t(a)^\top(\widehat\theta_t^{\rm lin}-\theta_t).
\]

The exact current replay metric is

\[
V_t
=
\lambda I
+\sigma^{-2}\sum_{s<t}
q_{\theta_t}(z_s)q_{\theta_t}(z_s)^\top.
\]

Policy code uses float64 Cholesky solves and never forms an explicit inverse.
At \(t=1\), \(\bar V_1=V_1=\lambda I\), \(Q_1=D_1=\gamma_0=0\).

With \(S=R\), store

\[
\epsilon_{\rm lin}(s)
=
\frac{L_\mu}{2}(R+\|\theta_s\|_2)^2,
\qquad
b_t(a)
=
\frac{L_\mu}{2}(R+\|\theta_t\|_2)^2.
\]

The action-indexed interface is retained even though this global envelope is
constant across current actions. Define

\[
\gamma_{t-1}=\log\det\bar V_t-d\log\lambda
\]

and

\[
\beta_t^{\rm corr}
=
\sqrt{\gamma_{t-1}+2\log(1/\delta)}
+\sqrt\lambda R
+\frac1\sigma
\sqrt{\sum_{s<t}\epsilon_{\rm lin}(s)^2}.
\]

The multiplier is exactly one. Actual historical and current Taylor
remainders are logged ex post but never replace certified envelopes in a
policy score.

Specifically, the historical diagnostic is

\[
\rho_s^\circ
=
\mu_{\theta^\circ,W}(z_s)-\mu_{\theta_s,W}(z_s)
-q_s^\top(\theta^\circ-\theta_s),
\]

and the current diagnostic applies the same expression actionwise with
\(\theta_t\) and \(q_t(a)\). Their magnitudes and certified-envelope slacks are
reported separately.

## 7. Path quantities

The primary operational certificate is

\[
Q_t=\sum_{s<t}\|\theta_t-\theta_s\|_2^2,
\qquad
\bar D_t^Q
=
\frac{2L_g\sqrt{Q_t}}{\sigma\sqrt\lambda}.
\]

The endpoint diagnostic uses a symmetric generalized eigensolver:

\[
d_{{\rm Th},t}
=
\max_i\left|\log\lambda_i(V_t,\bar V_t)\right|.
\]

The implementation checks the endpoint Loewner sandwich without silently
clamping eigenvalues or violations.

The selected synthetic factor path interpolates each replay parameter
separately:

\[
\theta_{s,t}(\tau)=\theta_s+\tau(\theta_t-\theta_s).
\]

It is not the curvature of one common intermediate model parameter. The
diagnostic integral is

\[
\mathcal D_t
=
\int_0^1
\left\|V_t(\tau)^{-1/2}\dot V_t(\tau)V_t(\tau)^{-1/2}\right\|_{\rm op}
\,d\tau.
\]

The implementation uses analytic scaled-tanh gradients and Hessians. Smoke
policy runs evaluate 32-point Gauss-Legendre quadrature every round; smoke
development additionally evaluates order 16 at every round. Development
comparisons of orders 16 and 32 must meet the frozen absolute \(10^{-9}\) and
relative \(10^{-8}\) convergence tolerances. Full development uses both orders
at every tenth round and the terminal horizon. Full evaluation uses only the
frozen order 32 at those checkpoints. Uniform-behavior tuning streams do not
compute policy path diagnostics. Quadrature is a dense diagnostic, not a
policy certificate.

At each checkpoint the code checks, up to the separately declared quadrature
tolerance,

\[
d_{{\rm Th},t}
\le \mathcal D_t^{\rm quad}
\le \bar D_t^Q.
\]

No violation is clamped. A failure beyond tolerance invalidates the run.

## 8. Policies

All policies enumerate the same five actions and choose the smallest index at
the maximum score. They share optimizer hyperparameters but maintain separate
histories and parameter paths.

### `transport_hessian`

The primary theorem method uses

\[
U_t^Q(a)
=
m_t^{\rm corr}(a)
+\beta_t^{\rm corr}e^{\bar D_t^Q/2}s_t(a)+b_t(a),
\qquad
s_t(a)^2=q_t(a)^\top V_t^{-1}q_t(a).
\]

### `transport_endpoint`

The dense diagnostic oracle replaces \(\bar D_t^Q\) by
\(d_{{\rm Th},t}\). It measures path-certificate conservatism. It is not
presented as a scalable method.

### `frozen_reference`

The certified reference-geometry comparison uses

\[
U_t^{\rm frozen}(a)
=
m_t^{\rm corr}(a)+\beta_t^{\rm corr}\bar s_t(a)+b_t(a),
\qquad
\bar s_t(a)^2=q_t(a)^\top\bar V_t^{-1}q_t(a).
\]

### `naive_current`

The negative control uses

\[
U_t^{\rm naive}(a)
=
m_t^{\rm corr}(a)+\beta_t^{\rm corr}s_t(a)+b_t(a).
\]

It is marked uncertified unless the path distortion is zero.

No method-specific bonus or optimizer is tuned.

## 9. Seeds and reproducibility

The full seed splits are disjoint:

```text
development: 0, 1, 2
tuning:      10, 11, 12, 13, 14, 15, 16, 17, 18, 19
evaluation:  100, 101, ..., 149
```

The smoke profile uses development seed 0, tuning seed 10, and evaluation seed
100 as required. A smoke-profile run with numeric seed 100 is not a
full-profile evaluation run. It may be used to expose code defects, but neither
its outcomes nor any smoke metric may change the scientific configuration or
enter the paper. No full-profile evaluation command may run before the protocol
and experiment-code commit.

Child seeds are derived without Python's randomized hash. For context,
potential noise, and behavior actions, hash the UTF-8 payload
`transport-instantiation-v1\0<base-seed>\0<namespace>` with SHA-256, interpret
the first eight digest bytes in big-endian order, and clear the high bit. The
frozen namespaces are:

```text
transport_instantiation/context/v1
transport_instantiation/potential_noise/v1
transport_instantiation/teacher/v1
transport_instantiation/behavior_policy/v1
transport_instantiation/bootstrap/v1
```

The teacher uses the literal configured seed 1729. Context, potential-noise,
and behavior-action child seeds depend only on the study seed, which makes
their prefixes common across horizons and target labels. Paired-bootstrap
seeds instead use the repository `derive_seed` helper with a master integer
from the first 16 hexadecimal digits of the resolved-config SHA-256 digest and
the tuple `("transport_instantiation", "bootstrap", horizon, target_D)`.

Every run manifest records the base seed, stream child seeds, teacher seed, and
the actual paired-bootstrap seed for its condition.

## 10. Per-round logging

Each method logs the following fields for every round.

Environment and action:

- context and all-action true means;
- optimal and selected action;
- instantaneous and cumulative pseudo-regret;
- optimality gap.

Representation:

- \(\|\theta_t\|_2\) and \(\|\theta_t-\theta_{t-1}\|_2\);
- optimizer objective and gradient norm;
- projection indicator;
- \(Q_t\).

Confidence:

- \(\gamma_{t-1}\), \(\beta_t^{\rm corr}\), historical certified error
  energy, and current \(b_t\);
- actual historical and current remainders, labeled diagnostic only.

Metrics and transport:

- minimum and maximum eigenvalues and condition numbers of \(\bar V_t\) and
  \(V_t\);
- all-action frozen and current widths;
- \(\bar D_t^Q\), endpoint Thompson distance, and checkpoint path integral;
- both exponential half-factors;
- \(D_Q-d_{\rm Th}\), \(D_Q/d_{\rm Th}\) when
  \(d_{\rm Th}>10^{-12}\), and \(D_Q/\mathcal D^{\rm quad}\) when available.

Confidence and optimism:

- the all-action reference-confidence check;
- all-action transported optimism for `transport_hessian`;
- maximum signed margins;
- prefix simultaneous confidence and optimism indicators.

## 11. Deterministic and stochastic checks

The implementation checks:

1. pseudo-response identity;
2. corrected-center identity;
3. frozen Gram recursion;
4. determinant and information-gain recursion;
5. endpoint Thompson sandwich;
6. \(d_{{\rm Th},t}\le\bar D_t^Q\);
7. path-integral inequalities at quadrature checkpoints;
8. both all-action width-transport inequalities;
9. frozen width-sum potential closure;
10. instantaneous regret inequality when its confidence premise holds;
11. sharp and simple cumulative regret bounds when the joint prefix event
    holds.

The all-action stochastic confidence check is

\[
|\mu_t^*(a)-m_t^{\rm corr}(a)|
\le\beta_t^{\rm corr}\bar s_t(a)+b_t(a).
\]

A failure of this statistical event is retained as data. It is not an
implementation failure. A theorem-bound check whose premise is false receives
status `premise_false`, never `bound_violation_on_event`.

For `transport_hessian`, the checked instantaneous bound is

\[
\operatorname{reg}_t
\le
\beta_t^{\rm corr}(1+e^{\bar D_t^Q})\bar s_t(a_t)
+2b_t(a_t).
\]

The sharp cumulative RHS is

\[
\sqrt{
\left(\sigma^2+\frac{G^2}{\lambda}\right)
\gamma_T
\sum_{t=1}^T
\left[\beta_t^{\rm corr}(1+e^{\bar D_t^Q})\right]^2
}
+2\sum_{t=1}^T b_t(a_t).
\]

The simple RHS is

\[
2\sqrt{
\left(\sigma^2+\frac{G^2}{\lambda}\right)
\gamma_T
\sum_{t=1}^T(\beta_t^{\rm corr})^2e^{2\bar D_t^Q}
}
+2\sum_{t=1}^T b_t(a_t).
\]

Both are reported, along with the realized frozen width sum and its potential
upper bound.

## 12. Numerical policy

All arithmetic is float64. Dense solves use Cholesky factors. Endpoint
distances use symmetric generalized eigenvalues. The base algebra tolerance is

\[
\operatorname{tol}(A,b)
=
4096\,\epsilon_{\rm mach}\max\{1,d\}
\max\{1,\|A\|_{\rm op},|b|\}.
\]

The implementation documents which \(A\) and \(b\) scale each check. Path
quadrature uses the absolute and relative tolerances in Section 7. Tolerances
are fixed before full evaluation and are not changed after observing an
evaluation outcome.

Checks are labeled as one of:

```text
exact algebra checked numerically
dense floating-point diagnostic
quadrature diagnostic
statistical confidence event
```

Ordinary float64 residuals and eigensolver output are not called verified
certificates. Nonfinite output, a non-SPD matrix beyond tolerance, or a
deterministic identity or inequality failure beyond its declared tolerance
invalidates the complete run. A policy run writes its completed raw records and
failure details before the study driver aborts, so the failure is inspectable.

## 13. Primary and secondary outcomes

Primary outcomes are:

1. run-level simultaneous reference-confidence coverage for
   `transport_hessian`;
2. run-level simultaneous transported-optimism coverage for
   `transport_hessian`;
3. number of deterministic algebra or certificate failures;
4. conservatism of \(\bar D_t^Q\) relative to endpoint Thompson distance and
   the numerical selected-path length;
5. sharp cumulative theorem RHS divided by realized cumulative pseudo-regret,
   with zero-regret runs counted separately.

Secondary outcomes are cumulative pseudo-regret, paired method differences,
action and score disagreement, loss of optimism for `naive_current`, effects
of the target label, frozen/current width ratios, and historical/current bias
contributions. They are descriptive and do not support a uniform curvature
advantage claim.

## 14. Statistical summaries

For each target label and horizon, simultaneous coverage is a run-level binary
outcome over the 50 evaluation seeds. Report the proportion and exact 95%
Clopper-Pearson interval.

For policy regret and paired differences, pair by evaluation seed, horizon,
and target condition. Use 10,000 deterministic paired bootstrap resamples. The
bootstrap child seed is derived from the resolved-config digest and comparison
key. Report mean, standard error, median, IQR, 10th and 90th percentiles, and
the paired 95% interval. Pointwise curve intervals use the same paired-resample
principle and are labeled pointwise.

No large family of uncorrected \(p\)-values is reported.

For theorem-RHS/regret ratios, never divide by an epsilon. Report the count of
exact zero-regret runs, omit their ratios, and report RHS and regret separately.
For positive-regret runs, report median and quantiles of the ratio.
Path-tightness ratios follow the same rule: if the denominator is at most the
frozen \(10^{-12}\) diagnostic threshold, report the numerator and a
zero-denominator count instead of an epsilon-regularized ratio.

## 15. Raw output and provenance

`ExperimentLogger` writes each run with:

```text
manifest.jsonl
raw.jsonl
summary.json
summary.json.sha256
```

The manifest records the exact Git revision and dirty state, resolved config
and digest, profile and phase, seed and every child seed, method, horizon,
target label and resulting \(W\), selected optimizer artifact hash, package
versions, hardware, and runtime metadata.

Raw runs remain untracked under:

```text
results/raw/transport_instantiation/smoke/
results/raw/transport_instantiation/full/
```

Reviewed derived output belongs under:

```text
results/derived/transport_instantiation/
```

Canonical selection paths are:

```text
results/derived/transport_instantiation/smoke_selection.json
results/derived/transport_instantiation/selection.json
results/derived/transport_instantiation/selection.json.provenance.json
```

The task also requires the following selection export paths:

```text
results/derived/transport_instantiation_selection.json
results/derived/transport_instantiation_selection.json.provenance.json
```

The full tuning command writes the canonical nested artifact. The study driver
then writes the required export with identical selection JSON bytes and a
provenance sidecar that binds the export to the canonical SHA-256. Evaluation
and aggregation consume the canonical nested artifact.

The full aggregate is:

```text
results/derived/transport_instantiation/full_aggregate.json
```

Every aggregate includes and hashes the complete raw-input inventory. The
aggregator rejects missing or duplicate cells, missing rounds, mixed revisions,
mixed config digests, mixed profiles, selection mismatch, nonfinite values,
deterministic audit failures, or tuning/evaluation overlap. It expects exactly
2400 full evaluation trajectories and all 2400
seed-method-horizon-target summary cells.

## 16. Execution gates and stopping rules

The ordered gates are binding.

1. Theory validation and the theory-freeze commit complete before experiment
   execution.
2. Unit tests and resolved smoke-config inspection pass.
3. Smoke development and tuning run. Smoke selection is frozen before smoke
   evaluation.
4. Smoke aggregate passes. No smoke result enters the manuscript.
5. This protocol, the config, implementation, and tests are inspected and
   committed. No full-profile evaluation run has executed.
6. Full tuning runs on seeds 10 through 19. The complete candidate table and
   selection artifacts are inspected without executing full evaluation.
7. Locked full evaluation runs all 2400 cells against the exact selection
   artifact.
8. Strict aggregation accepts the complete grid.
9. Only then may deterministic paper tables, figures, and prose be generated.

Development and smoke runs may expose implementation defects. They may not be
used to add methods, remove target conditions, tune the UCB bonus, or alter
outcome definitions.

Once full evaluation starts, a deterministic failure invalidates the affected
run and the aggregate. The failing raw run is retained. Fix the code, create
the appropriate new revision, and rerun the complete locked evaluation grid
from scratch. Never remove only the failing seed. A stochastic confidence
failure is retained and summarized.

If an external dependency blocks execution, write an explicit `not_run` record
with the command, time, revision, config digest, and blocker. Do not fabricate,
extrapolate, or report partial results as complete. Runtime is not a reason to
shrink the locked grid.

The default full runner uses four workers with one BLAS thread per worker. The
smoke runner uses one worker. Worker count is operational metadata and does not
change seeds, but any override must be recorded in every manifest.

## 17. Publication artifacts

After strict full aggregation, generate:

```text
paper/tables/transport_instantiation_validity.tex
paper/tables/transport_instantiation_performance.tex
paper/tables/transport_instantiation_tightness.tex
paper/figures/transport_instantiation_regret.tex
paper/figures/transport_instantiation_regret.csv
paper/figures/transport_instantiation_tightness.tex
paper/figures/transport_instantiation_tightness.csv
paper/figures/transport_instantiation_bound.tex
paper/figures/transport_instantiation_bound.csv
```

The validity table reports every target label and horizon, evaluation count,
simultaneous confidence and optimism coverage with exact intervals,
deterministic failures, on-event bound violations, median maximum realized
\(D_Q\), median maximum endpoint distance, median sharp RHS, and median regret.

At the primary horizon \(T=1000\), the performance table reports each method's
mean regret, 95% interval, median, IQR, paired difference from
`transport_hessian`, paired interval, and simultaneous optimism rate. It labels
`transport_endpoint` a dense endpoint oracle and `naive_current` an
uncertified negative control.

The appendix tightness table reports the three path ratios, path inflation,
historical radius contribution, current additive bias, frozen width-sum ratio,
and sharp/simple RHS ratio. Figures show regret curves, endpoint distance
against \(D_Q\) with the identity line, and the theorem-bound decomposition.
Poor-performing methods and vacuous bounds remain visible.

Tables and figures are deterministic functions of the accepted aggregate and
embed its SHA-256. Figures are versioned PGFPlots TeX backed by deterministic
CSV, so this study adds no Matplotlib dependency. The manuscript build compiles
them as part of `paper/main.pdf`; no generated standalone PDF is committed.
Labels are escaped and ordering is fixed. Smoke or tuning input causes artifact
generation to fail.

The paper separates deterministic identities, stochastic coverage, bound
nonvacuity, and policy performance. Acceptable language is that the study
executes and audits the revised score in a controlled model. It must not say
that the experiment proves the theorem, that full curvature improves regret,
that float64 checks are verified certificates, that the endpoint oracle is
scalable, or that the result covers unrestricted neural networks. The legacy
experiments remain historical diagnostics and are labeled separately.
