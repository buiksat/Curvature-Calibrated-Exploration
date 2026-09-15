# Realistic confidence-transport benchmark protocol

Protocol version: `realistic-transport-covtype-v1`

This protocol is frozen before tuning or evaluation. It defines a
falsification-oriented benchmark for corrected-center confidence transport on
real Covertype context geometry, low-rank current curvature, and iterative
width solves. Smoke and pilot results are engineering evidence. Only a complete
locked evaluation grid may be used as publication evidence.

## Prospective repair amendment

This amendment applies to future authentic Covertype work. It was introduced
before any authentic Covertype pilot, tuning, or evaluation. Historical Digits
smoke output remains smoke evidence and is not retroactively covered by these
gates.

The required order is:

```text
repair R -> independent 03 clearance -> candidate Covertype preparation
-> clean data-bound freeze F -> pilot -> tuning -> selection-only lock L
-> confirmatory evaluation state E
```

Preparation emits a candidate artifact and manifest. It cannot approve either
one. After an independent authenticity check, the approved data lock records
the exact artifact, manifest, semantic-array, loader, runtime, split, and
preprocessing identities. The configuration records the repository-relative
lock path, the exact lock-file SHA-256, and the same non-null semantic digest in
each Covertype profile override. Keeping those bindings out of the smoke
profile preserves the historical smoke configuration identity.
The lock and configuration must then be committed with the scientific sources
in F. A run accepts the lock only when its current bytes equal the blob at F.
Hashes bind approved bytes; they do not establish dataset authenticity.

Python must not write bytecode into the repository during freeze preparation.
Set `PYTHONPYCACHEPREFIX` to a project-external directory or set
`PYTHONDONTWRITEBYTECODE=1`. Immediately before F, audit ignored and untracked
paths and remove only generated `__pycache__`, `.pyc`, and `.pyo` files. The
scientific inventory recursively includes Python, Python stub, shared-library,
Starlark, and bytecode paths. It also includes every repository-local `BUCK`,
`BUCK_TREE`, `PACKAGE`, `.buckconfig`, `.buckconfig.local`, and `.buckroot`;
every entry below a `.buckconfig.d` directory; the root Buck binary selectors;
the `tools/buck2-versions` selectors; all bundled wheels; and both Buck test
drivers. This class rule rejects a relevant path that was absent at F if it
later appears untracked, staged, or committed. Each present entry binds its
Git-compatible mode as well as its bytes. Every symlink outside `buck-out/`,
`results/logs/`, and `results/raw/` is rejected unless its exact path is one of
the build/dependency links already required at START. Allowed links bind the
stored link text and mode without following the target. This rejects startup
hooks, dependency-shadow packages, and nested package-member links even when
they are already present at F.

F authenticates repository-local inputs only. It does not bind system or user
configuration such as `/etc/buckconfig*` or `~/.buckconfig*`, and it does not
authenticate bytes reached through the allowed links into the external
fbsource checkout. A future production run must attest that machine and
external build environment separately.

The central profile policy is fixed as follows:

| Profile | Dataset | Phase | Seeds | Horizon | Evidence role |
| --- | --- | --- | --- | --- | --- |
| `smoke` | Digits | development | 0 | 32 | smoke only |
| `covtype_pilot` | approved Covertype | development | 0, 1 | 100 | pilot only |
| `tuning` | approved Covertype | tuning | 10 through 19 | 500 | tuning only |
| `resource_fallback` | approved Covertype | evaluation | 200 through 209 | 250 | pilot-only, non-publication |
| `full` | approved Covertype | evaluation | 100 through 129 | 500 | publication candidate |

All Covertype profiles require F and the approved data lock. The resource
fallback and full profiles also require L. The runtime and aggregator both
validate the profile, phase, seed-set identity, horizon, evidence role, data
identity, and relevant lineage from repository objects. The full profile is
publication-eligible only after these checks, a complete grid, clean sources,
valid per-method exogenous-stream pairing, and zero deterministic failures.
The `full` and `resource_fallback` study entry points require the complete
ordered task and method grids and the exact profile seed partition. The
single-cell entry point rejects those profiles; it cannot emit a profile-looking
partial evaluation.

Selection records F and its payload hash. L must be a direct, single-parent
child of F whose only changes are the selection JSON and its SHA-256 sidecar.
Selection does not contain its future L SHA. Evaluation records E separately,
and aggregation verifies that E descends from L while scientific source bytes
remain identical to F.

## Scientific question

The benchmark asks whether corrected-center operational confidence transport
remains statistically valid and useful when:

- contexts come from a standard real dataset;
- the current replay curvature is approximated by a PSD Nyström operator;
- widths use a fixed-operator CG solve and an exact-arithmetic residual bound;
- the reward model is either realizable, uniformly misspecified, or driven by
  real labels outside the theorem's realizability premise.

The three tasks are analyzed separately. The real-label task is an uncertified
stress test. It is never pooled with the controlled tasks for theorem-validity
claims.

## Predeclared limitation

The required scaled-tanh design computes `W` from `T=500` and `target_D=1`.
For the controlled Gaussian tasks this gives approximately `W=75700.15`; for
the Bernoulli task with sub-Gaussian proxy `sigma=0.5`, approximately
`W=18925.04`. With `||phi||<=1` and `||theta||<=1`, the model is very close to
linear. Scaled-tanh replay gradients change only by a small scalar and do not
rotate. Corrected and tangent centers can also be nearly identical. Null
differences between the corrected, tangent, transported, and naive policies do
not establish equivalence of those mechanisms.

## Dataset identity and preparation

The primary dataset is loaded with:

```python
sklearn.datasets.fetch_covtype(
    data_home=CCE_DATA_ROOT,
    as_frame=False,
    shuffle=False,
    return_X_y=True,
)
```

The preparation command records the scikit-learn version, exposed source
metadata, loaded shapes and dtypes, class values, accessible cache-file hashes,
and semantic array digests. Labels are sorted and mapped to zero-based action
indices. The complete dataset is not committed.

The authoritative prepared-data digest is a SHA-256 digest over canonical
little-endian C-order bytes plus array names, shapes, and dtypes. The container
file hash is recorded separately and is not used as the split salt.

The locked runtime reads a prepared artifact below `CCE_DATA_ROOT`, verifies
the semantic digest and manifest, and records only logical paths and digests.
Absolute machine paths are excluded from committed artifacts.
Preparation is write-once. Before loading or fetching data, it rejects an
existing artifact, manifest, sidecar, directory, or dangling symlink, and its
write boundary never replaces an existing path.
All raw, aggregate, statistics, tuning, selection, and sidecar writers use a
unique same-directory temporary file, fsync it, and install it with a
non-replacing final operation. Artifact directories are staged next to their
destination and published with Linux `renameat2(RENAME_NOREPLACE)`.

If Covertype acquisition is unavailable, Digits may be prepared for smoke tests
only. Digits results are never publication evidence and never substitute for
the Covertype pilot, tuning, or evaluation.

Prepared manifests record `smoke_only` and `fixture_only` as independent
booleans. Synthetic test data sets `fixture_only=true` even when a test needs a
Covertype-like identity. A fixture can exercise aggregation and report rendering,
but it can never satisfy the committed data-lock authorization or publication
eligibility checks.

## Deterministic split

For row index `i`, compute:

```text
SHA256("realistic-transport-covtype-v1\0" + semantic_digest + "\0" + i)
```

Convert the first eight digest bytes to an unsigned big-endian integer and
take modulo 100:

- `0..19`: development;
- `20..39`: tuning;
- `40..99`: evaluation.

The split must cover every row exactly once. Evaluation rows are excluded from
preprocessing, teacher fitting, optimizer selection, and baseline selection.

## Preprocessing

All arrays use float64. Fit the transform only on development rows:

1. Compute coordinate means and standard deviations with `ddof=0`.
2. Replace a zero standard deviation by one and record its coordinate.
3. Form standardized development data `Z`.
4. Form `C = Z.T @ Z / n_dev`.
5. Use symmetric `eigh`, order eigenpairs by decreasing eigenvalue, and retain
   16 components.
6. For each component, find the first coordinate attaining the largest
   absolute loading and make that loading positive.
7. Reject a nonfinite decomposition or a rank-16 boundary eigenvalue gap no
   larger than `4096 * eps * max(1, largest_eigenvalue)`.
8. Transform each row and divide by `max(1, ||x||_2)`.

The transform artifact records means, standard deviations, zero-variance
coordinates, projection, eigenvalues, sign anchors, summaries, and digests.

## Feature map

For transformed context `x` and action `a`:

```text
raw_phi(x,a) = [x, one_hot(a), kron(x, one_hot(a))]
phi(x,a) = raw_phi(x,a) / max(1, ||raw_phi(x,a)||_2)
```

The Kronecker order is NumPy row-major order. For Covertype, the expected values
are `p=16`, `K=7`, and `d=p+K+pK=135`; the runtime computes and checks them.
Every feature must satisfy `||phi||<=1`.

## Tasks

### `covtype_label_bandit`

For label `y_t`:

```text
mu*(a) = 0.1 + 0.8 * 1[a=y_t]
```

Generate an independent Bernoulli potential reward for every action and reveal
only the selected reward. The label remains hidden until after selection. The
conditional sub-Gaussian proxy is `sigma=0.5`, by Hoeffding's lemma.

The learner uses the same scaled-tanh family and a task-specific `W` from the
frozen target-D rule. No valid model-misspecification envelope is supplied.
For scoring only, the preregistered heuristic sets misspecification envelopes
to zero and retains the global scaled-tanh Taylor envelope. Every nonlinear
transport method records `theorem_applicable=false`; confidence and optimism
are stress diagnostics.

### `covtype_semisynthetic_realizable`

Fit a multiclass ridge least-squares teacher on development rows only. Center
`X` and one-hot `Y`, then solve:

```text
(Xc.T @ Xc + I) B = Xc.T @ Yc
c = mean(Y) - mean(X) @ B
```

Map `c` to the action block, map `B.reshape(-1, order="C")` to the interaction
block, set the context-only block to zero, then scale the complete parameter
once to Euclidean norm one. The teacher is fixed before tuning and evaluation.

The true mean is the learner-family scaled-tanh mean at this teacher. Potential
noise is Gaussian with `sigma=0.25`. Exact realizability is checked against all
generated action means up to a scale-aware float64 tolerance.

### `covtype_semisynthetic_misspecified`

Use the same teacher and contexts, then add:

```text
m*(x,a) = rho * sin(omega_a.T @ x + b_a)
```

Generate normalized `omega_a` and phases from the fixed namespace seed
`271828`. Compute, on development contexts only, the linear-interpolation
90th percentile of the base all-action range and set `rho=0.25*s_range`.
Nonfinite or nonpositive `s_range` fails preparation.

The operational historical and current misspecification envelopes are both the
uniform value `rho`. Realized `|rho*h_a(x)|` is audit-only and never enters a
score or radius.

## Learner and representation update

- Initial parameter: zero.
- Projection radius and reference norm bound: one.
- Training loss: selected squared residuals divided by `2*sigma^2`, plus
  `0.5*||theta||^2`.
- Update: projected full-batch gradient descent after the selected reward.
- Each method has an independent history and representation path.
- The current reward never enters the current score.
- Each cell runs in one fresh spawned process. The configured and enforced
  BLAS/OpenMP thread count is exactly one, with actual pools checked before and
  after numerical work.
- Peak memory combines sampled process RSS with process-lifetime `ru_maxrss`.
  It includes interpreter startup and deserialization, model, optimizer, replay,
  operational work, and checkpoint diagnostics.

Optimizer candidates are the Cartesian product:

```text
learning_rate   = [0.00003, 0.0001, 0.0003]
steps_per_round = [1, 5, 20]
```

Development smoke uses `(0.0001, 5)`. Tuning selects one shared setting for the
two controlled tasks and one setting for the real-label task. The criterion is
the equal-weight mean of per-task, per-seed all-action prediction MSE after a
100-round burn-in. Any deterministic failure rejects a candidate. Tie order is
fewer steps, then smaller learning rate.

## Corrected estimator and envelopes

For selected history:

```text
q_s = grad_theta mu_theta_s(x_s,a_s)
Vbar_t = lambda I + sigma^-2 sum q_s q_s.T
y_s = r_s - mu_theta_s(x_s,a_s) + q_s.T theta_s
theta_hat_lin = Vbar_t^-1 sigma^-2 sum q_s y_s
m_corr(a) = mu_theta_t(x_t,a) + q_t(a).T(theta_hat_lin-theta_t)
m_tangent(a) = q_t(a).T theta_hat_lin
```

Use `lambda=1`. The operational Taylor envelope is:

```text
epsilon_lin(theta) = 0.5 * L_mu * (1 + ||theta||)^2
```

It is used for both historical collection rounds and the current action. The
controlled misspecified task adds `rho` before squaring historical terms and
adds `rho` to the current bias. The confidence radius is:

```text
sqrt(gamma_previous + 2 log(1/delta))
+ sqrt(lambda) * S
+ sigma^-1 * sqrt(sum (epsilon_lin + epsilon_mis)^2)
```

Use `delta=0.05`. Audit output also reports the linear-only, misspecification-
only, combined, and combined-minus-linear historical contributions.

## Metrics and path transport

The exact current replay metric is formed from replay queries at `theta_t`.
The operational path certificate is:

```text
Q_t = sum ||theta_t-theta_s||^2
D_Q = 2 L_g sqrt(Q_t) / (sigma sqrt(lambda))
```

Maintain `Q_t` by Welford scatter. Endpoint Thompson distance is an oracle
diagnostic and enters only the endpoint-oracle method. Ratios with a zero
denominator are omitted and counted; no epsilon replacement is allowed.

At each declared dense checkpoint, approximate methods record three distinct
selected-action width ratios: the solver upper width over the exact width for
the same approximate operator A, the exact A width over the exact current
operator V width, and the operational upper width over the exact V width. The
corresponding all-action values are retained in the round record. Aggregation
forms each eligible atomic ratio first and then takes the frozen arithmetic
mean across checkpoint records. It records denominator omissions. These fields
are diagnostics, not selection criteria.

Current-exact Cholesky methods retain both `current_exact_widths` and its
legacy `current_widths` alias on every round. These operational exact-V widths
must equal the all-action `score_widths` used to choose the action. For CG
methods, exact-V primitives remain dense-checkpoint diagnostics and are absent
off checkpoint. Other methods do not acquire a current-exact width map merely
for reporting.

Aggregation validates every ratio before using it. A finite ratio must carry
`denominator_omitted=false`; a null ratio must not carry that value. The legacy
solver-ratio alias must equal `solver_upper_over_exact_A`, each selected-action
value must equal its all-action entry, and the operational ratio must equal the
solver and operator factors under the existing scale-aware float64 audit
convention. V-referenced values are forbidden outside the declared dense
checkpoints. Denominator omission continues to use exact `denominator == 0.0`;
this validation adds no scientific threshold.

## Nyström operator

For replay-gradient matrix `J` with rows divided by `sigma`, use a deterministic
Gaussian sketch of size `r+8`, derived from task, base seed, and rank. Construct
the PSD Nyström approximation from `J` without materializing dense `H=J.T@J`
for the operational path. Truncate to target rank `r`.

In exact arithmetic, `0 <= H_r <= H`. Define:

```text
A = lambda I + H_r
tau_trace = trace(H) - trace(H_r)
kappa_plus = 1
kappa_minus = lambda / (lambda + tau_trace)
```

Float64 PSD and sandwich checks are numerical audits. They are not verified
numerical certificates. Dense residual eigenspectra and exact generalized
eigenvalue factors are computed only at rounds 1, 100, 250, and 500, plus the
final round of a shorter profile. They are timed separately from the
approximate algorithm. The operational Nyström path stores and applies the
low-rank factor directly; it does not materialize `H=J.T@J` or a dense
approximate operator before scoring.

The range-sketch numerical rank uses the frozen cutoff
`64*eps*max(shape)*largest_gram_eigenvalue`. A negative trace residual within
the scale-aware float64 tolerance may be set to zero and is logged. A larger
violation fails the run.

## CG width map

The operator remains fixed across every solve. Recompute the original residual
`r=q-A*x_tilde`. Let:

```text
n = sqrt(x_tilde.T @ A @ x_tilde)
e = ||r|| / sqrt(lambda)
upper = n + e
lambda_max_upper = lambda + trace(H_alg)
lower = max(0, n-e, ||q||/sqrt(lambda_max_upper))
alpha = upper/lower
```

For `q=0`, return zero width and `alpha=1`. A zero lower bound for nonzero `q`
is a deterministic failure. Every action score uses the same realized solve
rule. There is no post-selection refinement. The selected-action theorem
factor is the alpha already computed for its score.

The method records three separate statuses:

- `analytic_certificate_valid_in_exact_arithmetic`;
- `float64_diagnostic_pass`;
- `verified_numerical_certificate=false`.

Each round also records the exact float64 theorem comparison rule and its
scale-aware comparison tolerance. Aggregation recomputes theorem-event status
from applicability, the recorded confidence event, regret, right-hand side,
and that tolerance. It independently derives deterministic-failure reasons and
the float64 diagnostic result from solver convergence and the two envelope
checks. A valid negative scientific outcome remains evidence; disagreement
between a status and its primitives is an integrity error.

## Methods

The fixed 13-method grid is:

1. `transport_exact_corrected_cholesky`
2. `transport_exact_corrected_cg_1e-4`
3. `transport_endpoint_corrected_cholesky`
4. `frozen_reference_corrected_cholesky`
5. `naive_current_corrected_cholesky`
6. `transport_exact_uncorrected_tangent_cholesky`
7. `greedy_corrected`
8. `linucb_fixed_features`
9. `transport_nystrom_r16_cg_1e-2`
10. `transport_nystrom_r16_cg_1e-6`
11. `transport_nystrom_r64_cg_1e-2`
12. `transport_nystrom_r64_cg_1e-6`
13. `transport_nystrom_r32_cg_1e-4`

Exact, endpoint, frozen, naive, tangent, and greedy roles follow the task
specification. Task-level theorem applicability is recorded independently of
method identity.

LinUCB uses the static normalized feature map, ridge one, and alpha candidates
`[0.25, 0.5, 1, 2, 4]`. Select alpha per task by mean tuning regret, breaking
exact ties toward the smaller alpha.

All finite-action policies enumerate actions from zero through `K-1`, choose
the smallest exact maximizing index, record exact tie counts and top-two score
margins, and have zero action-oracle error.

## Seeds, horizons, and streams

```text
development: 0,1,2
tuning:      10..19
evaluation:  100..129
pilot-only:  200..209
```

The maximum horizon is 500 and prefixes 100, 250, and 500 are reported from a
single trajectory. Child streams use the repository SHA-256 seed derivation
with separate namespaces for contexts, potential outcomes, teacher,
misspecification, Nyström sketch, baseline randomization, and bootstrap.

Within a task and seed, methods share context order, teacher, misspecification
function, and potential-outcome table. Policies see only selected rewards.
Contexts are sampled without replacement from a deterministic permutation of
the requested split. A run fails if its horizon exceeds the split size.

The fixed-feature LinUCB baseline uses
`V=lambda I+sum phi phi.T`, `rhs=sum phi*r`, ridge prediction
`phi.T@V^-1@rhs`, and bonus `alpha*sqrt(phi.T@V^-1@phi)`. Its confidence
parameter is selected empirically and is not identified with the nonlinear
transport radius.

## Practical configuration selection

All five Nyström/CG cells remain in evaluation. Per task, find cells with mean
tuning regret within 5% of the best approximate cell. Choose the one with the
lowest median algorithm runtime, then lower peak RSS, lower rank, and looser
tolerance. Logical operator bytes remain a reported diagnostic. Bind the result
to a source inventory and tuning-input inventory before evaluation.

The freeze commit contains protocol, configuration, implementation, and tests.
The selection artifact records that freeze revision and its complete source
hash inventory. A later selection-only commit is permitted. Evaluation checks
the frozen source inventory rather than requiring evaluation HEAD to equal the
tuning commit.

## Statistical analysis

The seed is the independent unit. Report each task separately.

- Binary run-level simultaneous coverage: exact two-sided 95% Clopper-Pearson
  interval, numerator, and denominator. Coverage is falsified when the one-sided
  95% binomial upper bound is below 0.95; 30/30 is not called proof of nominal
  95% coverage.
- Continuous outcomes: mean, standard error, median, IQR, 10th/90th
  percentiles, and 10,000 deterministic paired bootstrap resamples over seeds.
- No formal p-values are planned. Primary comparisons use task-specific paired
  intervals. A secondary controlled-task result first averages Tasks B and C
  within each seed, then resamples seeds.
- Rank/tolerance contrasts use the four corner cells and seed-clustered
  resampling. The center cell is reported separately.

## Frozen interpretation thresholds

- Material regret change: at least 10% of comparator mean and paired 95%
  interval excludes zero.
- Practical approximation: regret ratio of means at most 1.05 and at least 20%
  lower median algorithm time or logical operator bytes.
- Equivalent regret: paired interval lies within plus or minus 5% of the
  comparator mean.
- Path certificate orders of magnitude looser: median positive-denominator
  `D_Q/d_Th >= 100`.
- Effectively zero operator lower factor: `kappa_minus <= 1e-3` on at least
  50% of evaluated rounds.
- Unusable width inflation: median upper/exact width at least 1.25, or bonus
  exceeds the all-action reward range on at least 90% of rounds.
- Meaningful nonvacuity: at least 25% of runs have theorem RHS below the
  task-specific cumulative trivial cap.
- Real-label competitiveness: M1 mean regret is no more than 10% above LinUCB,
  and the paired interval does not establish more than 10% harm.

## Falsification rules

The evidence weakens the practical case when one or more preregistered failure
criteria in the configuration survive implementation checks. It strengthens
the practical case only when controlled-task coverage and optimism remain
consistent with the target, one selected approximate cell approaches exact
regret with a preregistered compute reduction, and the operational quantities
remain nonvacuous on the declared fraction of runs. Otherwise the evidence
leaves the relevant claim unchanged.

## Execution gates

1. Commit the repair R without preparing or running authentic Covertype.
2. Obtain independent 03 clearance of R.
3. Prepare the candidate Covertype artifact outside Git by the approved loader.
4. Independently approve its identity, create the data lock, update the null
   config bindings, and commit clean scientific sources plus those bindings as F.
5. Run the two-seed development pilot from F.
6. Run complete tuning from the unchanged clean F and emit a tuning artifact.
7. Derive selection from the complete tuning artifact. Commit only the selection
   JSON and its SHA-256 sidecar as L, a direct child of F.
8. Run either the non-publication resource fallback or the 30-seed, 500-round
   confirmatory evaluation from an E state that descends from L.
9. Reject incomplete, mixed-stream, mixed-identity, or invalid-lineage aggregates.
10. Generate reports only from an accepted aggregate. A full aggregate with a
    deterministic execution failure remains non-publication evidence.

If Covertype acquisition is externally blocked, write a `not_run` record, run
Digits smoke, provide exact Covertype commands and estimates, and do not call
the result a pilot or full experiment. If Covertype is available but full
evaluation is infeasible after the runtime-only pilot, run the fixed resource
fallback of seeds 200 through 209, 250 rounds, every task and method, and label
all output pilot evidence.

## Output and provenance

Raw outputs stay under `results/raw/realistic_transport/` and remain untracked.
Derived and review artifacts use new `results/derived/realistic_transport/`
and `review/realistic_transport/` paths. Every record binds config, data,
transform, teacher, misspecification, source-inventory, and selection digests.
Artifacts use repo-relative logical paths and reject absolute machine paths.

Existing locked paper results and manuscript sources are not modified.
