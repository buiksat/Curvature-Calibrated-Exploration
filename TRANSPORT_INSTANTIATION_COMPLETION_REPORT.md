# Confidence-Transport Theory Freeze and Experiment Completion Report

## Status

The confidence-transport theorem stack is frozen and the first direct nonlinear
theorem-instantiation experiment is complete.

- Branch: `codex/cc-ucb-theory-experiments`
- Required starting commit: `47037a2df6b81befd4a0cb3c5974e3565d8f61b6`
- Original theory baseline: `9128276162c0fcb1d267c0a9043f8beed11f192e`
- Reviewed implementation head: `93eaa537d2702d5d18b05905913b0b879e3d608f`
- Full evaluation grid: 2,400/2,400 trajectories
- Deterministic audit failures: 0
- On-event theorem-bound violations: 0
- Final manuscript: 63 pages, 933,908 bytes
- Final PDF SHA-256:
  `2545c368d6b97393f5c1e5bb61d4696f7fed6b8ae988ce42c9d7bc7ccab717e1`

This file documents the implementation ending at `93eaa53`. It may be stored in
a later documentation-only commit; the implementation review range remains
`47037a2..93eaa53`.

## Commits

1. `2eca895af17b4f32a1ec30ff77568a4de92140b1`
   `paper: freeze confidence transport theory`
2. `0cd6264c1f8b8751728f3c4a198207e8289aed74`
   `experiments: add nonlinear transport theorem instantiation`
3. `93eaa537d2702d5d18b05905913b0b879e3d608f`
   `paper: report nonlinear transport experiment`

No commit was amended or pushed. The obsolete `main` branch was not used.

## Theory freeze

The theory commit changed:

- `paper/transport_theory.tex`
- `paper/transport_proofs.tex`
- `paper/legacy_dynamic.tex`
- `paper/main.tex`
- `THEORY_TRANSPORT_DERIVATIONS.md`
- `THEORY_GENERALIZATION_AUDIT.md`
- `paper/main.pdf`

The audit now states that the confidence-transport theorem API is frozen. No
new theorem family should be added unless a concrete mathematical error is
found.

### Legacy finite-action measurability

The retained fallback theorem now assumes a deterministic `A_max`, an
`H_t^-`-measurable positive integer `K_t <= A_max`, and an `H_t^-`-measurable
padded candidate enumeration. The action domain is

\[
\mathcal A_t=\{a_{t,k}:1\le k\le K_t\}.
\]

The learner and true-mean comparator both use the smallest maximizing index.
The finite score vector is pre-reward measurable; the true-mean vector and its
smallest maximizing index are pre-randomization measurable.

### Certificate-source countability

The certificate-source set `J` is finite or countable. For the sigma-algebra
`P_{j,t}` immediately before the corresponding draw,

\[
\Pr(\mathcal E_{j,t}^c\mid\mathcal P_{j,t})\le\delta_{j,t},
\qquad
\sum_{j\in\mathcal J}\sum_{t=1}^T\delta_{j,t}\le\delta_{\rm cert}.
\]

Countability supplies measurable intersections, a well-defined nonnegative
double sum, and a valid union bound.

### Pre-reward design filtration

Action-dependent designs and intercepts are `G_t`-measurable before the reward
noise, not `H_t^-`-predictable. The self-normalized argument uses

\[
\widetilde{\mathcal F}_{2t-1}=\mathcal G_t,
\qquad
\widetilde{\mathcal F}_{2t}=\mathcal F_t.
\]

### Global near-linearity under exponential transport

Under exact realizability, radius-`R` parameter control, exact current
curvature, exact dense solves, exact maximization, finite parameter dimension,
and

\[
L_\mu\le\frac{c_\mu}{\sqrt W},
\qquad
L_g\le\frac{c_g}{\sqrt W},
\]

define

\[
D_{T,W}=\frac{4c_gR\sqrt{T-1}}{\sigma\sqrt{\lambda W}}.
\]

The new corollary proves

\[
\begin{aligned}
R_T\le{}&
2e^{D_{T,W}}
\left[
\sqrt{\Gamma_{T,d}+2\log(1/\delta)}
+\sqrt\lambda R
+\frac{2c_\mu R^2\sqrt T}{\sigma\sqrt W}
\right]\\
&\times
\sqrt{\left(\sigma^2+\frac{G^2}{\lambda}\right)T\Gamma_{T,d}}
+\frac{4c_\mu R^2T}{\sqrt W}.
\end{aligned}
\]

Thus `W = Omega(T)` keeps `D_{T,W} = O(1)` and gives

\[
R_T=O(d\sqrt T\log T)+O(\sqrt T)
\]

for fixed problem constants, without a `D_t < 1` premise.

For the scaled-tanh model,

\[
G=B_\phi,
\qquad
c_\mu=c_g=\frac{4B_\phi^2}{3\sqrt3}.
\]

### Sharpness of the exponential metric factors

For

\[
\bar V=I_2,
\qquad
V=\operatorname{diag}(e^D,e^{-D}),
\]

the selected diagonal path has

\[
\mathcal D(V)=d_{\rm Th}(\bar V,V)=D.
\]

Queries `e_1` and `e_2` attain the two respective `e^{D/2}` width
comparisons. A uniform proof based only on symmetric Thompson-distance
information therefore cannot improve the round-trip `e^D` factor. This is a
metric-factor sharpness statement, not a contextual-bandit regret lower bound.

### Preserved invariants

The following were independently re-derived and preserved:

- both one-way `e^{bar D_t/2}` transports;
- the round-trip `e^{bar D_t}` factor;
- `sqrt(kappa_+ / kappa_-)`;
- bias twice and oracle error once;
- all-action solver upper validity;
- played-action-only sharpness;
- the same realized width map in the score, upper certificate, and sharpness;
- the frozen-potential constant `sigma^2 + G^2 / lambda`;
- the corrected-center identity;
- historical deterministic scaling `1 / sigma`, not `1 / sigma^2`;
- the finite-dimensional rank-trace closure and LinUCB reduction.

## Experiment implementation

Principal files:

- `experiments/transport_instantiation.py`
- `experiments/run_transport_instantiation.py`
- `experiments/run_transport_instantiation_study.py`
- `experiments/aggregate_transport_instantiation.py`
- `experiments/make_transport_instantiation_artifacts.py`
- `experiments/configs/transport_instantiation.yaml`
- `experiments/TRANSPORT_INSTANTIATION_PROTOCOL.md`
- `experiments/tests/test_transport_instantiation.py`
- `experiments/tests/test_transport_instantiation_aggregate.py`
- `experiments/tests/test_transport_instantiation_artifacts.py`

### Frozen configuration

- Context dimension: 4
- Action count: 5
- Parameter dimension: 29
- `B_phi = R = lambda = lambda_train = 1`
- `sigma = 0.25`
- `delta = 0.05`
- Horizons: `[250, 500, 1000]`
- Target `D`: `[0.25, 0.5, 1.0, 2.0]`
- Methods: `transport_hessian`, `transport_endpoint`, `frozen_reference`,
  `naive_current`
- Exact dense frozen and current metrics
- Float64 Cholesky solves
- Order-32 Gauss-Legendre path diagnostics every 10 rounds
- Smallest-index action tie rule
- Numerical tolerance constant: 4096

Seed sets:

- Development: `[0, 1, 2]`
- Tuning: `[10, ..., 19]`
- Evaluation: `[100, ..., 149]`

The selected optimizer was:

- learning rate: `0.0003`;
- steps per round: `20`;
- tuning MSE: `0.00666914978044266`.

Only representation-update stability was tuned. Evaluation seeds did not enter
the selection.

## Execution and validation

- Smoke development: 16 trajectories
- Smoke tuning: 36 candidate trajectories
- Smoke evaluation: 16/16 trajectories
- Full tuning: 1,080/1,080 trajectories
- Full evaluation: 2,400/2,400 trajectories
- Full evaluation rounds: 1.4 million
- Raw output size: approximately 8.8 GB, ignored and untracked
- Repository tests: 59 passed
- Buck test targets: 2 passed, 0 failed
- Static TeX validation: 261 labels, zero duplicate labels, zero unresolved
  references, and zero missing citations
- Publication artifact SHA sidecars checked: 47, all valid
- Independent adversarial publication review: no surviving finding

## Locked evaluation results

### Confidence, optimism, and deterministic checks

For `transport_hessian`, all 50 runs passed simultaneous reference confidence
and simultaneous transported optimism in every one of the 12 horizon/target
cells. The exact 95% Clopper-Pearson interval in each cell is

\[
[0.9288782635,1].
\]

There were zero deterministic audit failures and zero theorem-bound violations
on the joint confidence event.

### Certificate tightness at `T = 1000`

| Target D | Median max D_Q | Median max d_Th | Median D_Q / D_path | Median D_path / d_Th |
| ---: | ---: | ---: | ---: | ---: |
| 0.25 | 0.04862 | 1.31e-7 | 1.88e6 | 1.200 |
| 0.5 | 0.09844 | 5.23e-7 | 9.77e5 | 1.214 |
| 1 | 0.19778 | 2.10e-6 | 4.82e5 | 1.219 |
| 2 | 0.38389 | 8.74e-6 | 2.51e5 | 1.218 |

The numerical selected path closely tracks endpoint distance. The analytic
Hessian/`Q_t` certificate is the dominant source of conservatism.

### Policy regret at `T = 1000`

Means and deterministic paired-bootstrap 95% intervals:

| Target D | Hessian transport | Endpoint | Frozen | Naive current |
| ---: | ---: | ---: | ---: | ---: |
| 0.25 | 81.05 [79.51, 82.64] | 79.05 [77.68, 80.49] | 79.09 [77.78, 80.48] | 79.00 [77.62, 80.46] |
| 0.5 | 82.44 [81.15, 83.71] | 79.49 [77.94, 81.07] | 80.13 [78.60, 81.69] | 79.49 [77.94, 81.07] |
| 1 | 87.04 [85.52, 88.51] | 80.06 [78.91, 81.24] | 80.25 [78.96, 81.62] | 80.10 [78.83, 81.45] |
| 2 | 93.99 [92.54, 95.50] | 81.89 [80.26, 83.48] | 81.67 [80.19, 83.07] | 81.88 [80.25, 83.48] |

Paired method-minus-Hessian differences ranged from approximately `-2.0` at
target `D = 0.25` to `-12.1` at target `D = 2`, with all reported paired
intervals below zero. These are descriptive paired comparisons, not evidence
of a uniform curvature advantage.

The intentionally uncertified naive-current method remained simultaneously
optimistic in all 200 primary-horizon runs. The negative control did not
separate empirically.

### Bound nonvacuity

| Target D | Median sharp RHS | Median regret | Median RHS / regret |
| ---: | ---: | ---: | ---: |
| 0.25 | 10,217.83 | 80.66 | 126.73 |
| 0.5 | 10,530.51 | 82.50 | 127.68 |
| 1 | 11,162.77 | 87.35 | 128.37 |
| 2 | 12,607.39 | 93.45 | 135.04 |

Across all cells, median ratios ranged from 126.73 to 155.75. No run had zero
regret or a false joint confidence premise. The theorem bound exceeded the
deterministic `2T` regret cap in every cell.

## Derived artifacts and hashes

- Optimizer selection:
  `8c16bec7cc220109df3fd7173c3d06ae6c6e1b95e9db5bc5b8c3377b3564f6f4`
- Full aggregate:
  `0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02`
- Aggregate input inventory:
  `4af9f51467981326c4f99ef171dc21e3fb27beb4d519b65d28d18f678e65ef66`
- Validity table:
  `0ec0451563890ea9373a0710bbcbc33b2db28a14e405a798e6033062fab7634a`
- Performance table:
  `5b2ea6000bfc123d9f52b38f37ddbb5aafb7eeb55139c8876a29d33879ee13ad`
- Tightness table:
  `940106f9f33decab26a9033277c5bc354c6c2e8d09dc629b5b3b6954deb45311`
- Regret figure:
  `239ae5e923801ed1a2f9eafa75ba6a642e8bd2bb14ec2875c8d080f22ea5ec98`
- Tightness figure:
  `828590d0cab45e2621677474acec4ae1216857191d54e816d4f4b24a2fd276c2`
- Bound figure:
  `9c6465521c216fa96fc6536044491684312108c510357f38cc92c0325319af3c`

## Remaining limitations

- The experiment uses exact dense 29-dimensional matrices and solves.
- It does not test approximate operators or iterative solvers.
- Endpoint transport is a dense diagnostic oracle.
- Float64 checks are diagnostics, not verified numerical certificates.
- The Hessian/`Q_t` certificate was severely conservative.
- The cumulative theorem bound was vacuous.
- No real data, generic MLP, large-network, or scalability claim is made.
- No uniform full-curvature regret advantage was observed or claimed.

## GPT Pro review prompt

Copy the prompt below into GPT Pro with access to this repository and the
committed `paper/main.pdf`.

```text
Role

Act as a skeptical senior reviewer for a mathematical machine-learning paper
and its theorem-instantiation experiment. Perform a read-only review. Do not
edit files, commit, push, or use the obsolete main branch.

Repository state

- Repository: buiksat/Curvature-Calibrated-Exploration
- Required branch: codex/cc-ucb-theory-experiments
- Original theory baseline: 9128276162c0fcb1d267c0a9043f8beed11f192e
- Final-pass starting commit: 47037a2df6b81befd4a0cb3c5974e3565d8f61b6
- Implementation head to review: 93eaa537d2702d5d18b05905913b0b879e3d608f
- Review range: 47037a2df6b81befd4a0cb3c5974e3565d8f61b6..93eaa537d2702d5d18b05905913b0b879e3d608f
- Completion report: TRANSPORT_INSTANTIATION_COMPLETION_REPORT.md

The main branch is obsolete. Do not compare against it, merge from it, or use
it as a source of truth.

Goal

Determine whether the theory corrections, frozen theorem API, experiment
implementation, strict aggregate, manuscript claims, and committed PDF are
mathematically and empirically consistent. Find concrete defects that could
change theorem validity, experiment validity, reported numbers, provenance, or
scientific interpretation.

Required reading

Read completely:

- TRANSPORT_INSTANTIATION_COMPLETION_REPORT.md
- paper/main.tex
- paper/transport_theory.tex
- paper/transport_proofs.tex
- paper/legacy_dynamic.tex
- paper/transport_experiment.tex
- paper/transport_experiment_appendix.tex
- THEORY_TRANSPORT_DERIVATIONS.md
- THEORY_GENERALIZATION_AUDIT.md
- experiments/TRANSPORT_INSTANTIATION_PROTOCOL.md
- experiments/configs/transport_instantiation.yaml
- experiments/transport_instantiation.py
- experiments/run_transport_instantiation.py
- experiments/run_transport_instantiation_study.py
- experiments/aggregate_transport_instantiation.py
- experiments/make_transport_instantiation_artifacts.py
- experiments/tests/test_transport_instantiation.py
- experiments/tests/test_transport_instantiation_aggregate.py
- experiments/tests/test_transport_instantiation_artifacts.py
- results/derived/transport_instantiation/selection.json
- results/derived/transport_instantiation/full_aggregate.json
- all generated transport-instantiation tables and figure TeX files
- paper/main.pdf

Review lenses

1. Theory and proof
   - Re-derive both Loewner inversions and both e^(D/2) transports.
   - Verify the e^D round trip, sqrt(kappa_+/kappa_-) factor, bias twice,
     oracle error once, all-action upper validity, and played-action-only
     sharpness.
   - Verify the same realized width map is used by scoring, upper validity, and
     sharpness.
   - Re-derive the corrected-center identity and confirm the historical term is
     1/sigma, not 1/sigma^2.
   - Re-derive the global near-linearity corollary, including every constant.
   - Verify the diagonal Thompson example proves metric-factor sharpness but is
     not overstated as a regret lower bound.
   - Check finite/countable event measurability, finite-action enumeration, and
     the G_t pre-increment filtration.

2. Experiment implementation
   - Check the scaled-tanh mean, gradient, Hessian, smoothness constant, teacher,
     normalized features, potential-noise coupling, and no-reward-leakage order.
   - Check pseudo-responses, corrected center, frozen/current metrics, beta,
     historical/current envelopes, Q_t certificate, endpoint Thompson distance,
     path quadrature, all policy scores, and smallest-index selection.
   - Verify exact dense operators and solves imply kappa_-=kappa_+=alpha=1,
     while path distortion remains.
   - Check sharp and simple cumulative bounds term by term.

3. Tuning, locking, and provenance
   - Verify development, tuning, and evaluation seeds are disjoint.
   - Verify only optimizer learning rate and step count were tuned.
   - Replay the winner selection and deterministic tie break from tuning inputs.
   - Check source-tree fingerprints prevent code changes between tuning and
     evaluation.
   - Confirm the strict aggregate requires the exact 2,400-cell Cartesian grid,
     rejects missing/duplicate/mixed inputs, retains stochastic confidence
     failures, and rejects deterministic failures.
   - Verify every committed aggregate/table/figure hash and provenance input
     inventory.

4. Statistical reporting
   - Recompute Clopper-Pearson intervals and selected paired-bootstrap intervals.
   - Check zero-regret handling and bound ratios.
   - Verify reported coverage, regret, path ratios, baseline diagnostics, and
     bound decomposition against full_aggregate.json.
   - Check that no smoke, development, or tuning result entered the paper.

5. Manuscript and PDF
   - Check every empirical claim against the locked aggregate.
   - Confirm the paper does not claim empirical proof, verified float64
     certification, uniform curvature improvement, scalable endpoint transport,
     unrestricted neural training, or generic-network width guarantees.
   - Inspect the rendered PDF for missing content, clipped tables, overlapping
     labels, unreadable figures, stale references, and mismatch with TeX.
   - Verify paper/main.pdf SHA-256 is
     2545c368d6b97393f5c1e5bb61d4696f7fed6b8ae988ce42c9d7bc7ccab717e1.

Locked evidence

- Full aggregate SHA-256:
  0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02
- Input inventory SHA-256:
  4af9f51467981326c4f99ef171dc21e3fb27beb4d519b65d28d18f678e65ef66
- Expected/completed evaluation trajectories: 2400/2400
- Deterministic failures: 0
- Each primary coverage cell: 50/50, exact 95% CI [0.9288782635, 1]
- The theorem bound is empirically vacuous. Do not reinterpret this as success.
- The naive-current negative control did not lose optimism in this experiment.
  Do not invent a separation that is absent from the data.

Finding standard

Default to rejecting speculative findings. Report an issue only when you can
provide:

- severity: High, Medium, or Low;
- exact file and line or artifact field;
- the violated mathematical, experimental, or reporting invariant;
- a concrete derivation, counterexample, reproduction, or data mismatch;
- the smallest sound repair;
- whether the issue changes the headline theorem, experiment validity, or only
  exposition.

Do not report style preferences, generic suggestions, or concerns already
discharged by explicit assumptions. A stochastic confidence-event failure is
not an implementation defect. Ordinary float64 diagnostics are not verified
certificates, but the manuscript already says so.

Validation

Run, when available:

git branch --show-current
git rev-parse HEAD
git status --short
git diff --check 47037a2df6b81befd4a0cb3c5974e3565d8f61b6..93eaa537d2702d5d18b05905913b0b879e3d608f
buck2 test //tests:tests //experiments/tests:tests -- --timeout=1200
buck2 run //paper:validate
make clean
make pdf

Do not treat successful compilation as mathematical validation.

Output

1. Verdict: clear, or the count of surviving issues by severity.
2. Surviving findings, ordered by severity, using the finding standard above.
3. Checked and cleared: list the important suspected failure modes you examined
   and rejected.
4. Reproduction: commands run and whether they passed.
5. Scope statement: explicitly state which findings, if any, affect the
   headline theorem, corrected-center result, finite-dimensional closure,
   experiment validity, or manuscript wording only.

If no concrete issue survives adversarial verification, say so directly. Do not
manufacture findings to make the review look balanced.
```
