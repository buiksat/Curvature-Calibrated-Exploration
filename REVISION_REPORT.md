# Resubmission Revision Report

Date: 2026-07-22

Branch: `codex/closed-rates-20260721`

Baseline revision: `d6279816`

## Status

The theory work requested in Tasks A--H is implemented, tested, and integrated
into the manuscript, except that no architecture-specific `W^{-1/2}` theorem
was added: the required full-Hessian conclusion does not follow from the draft's
parameterization and norm assumptions. `W` is now an abstract near-linearity
scale and optimizer-residual scaling is not attributed to width.

Three P0 experiment pipelines have deterministic configurations, seed manifests,
raw/derived separation, hash sidecars, tests, and one-command reproduction
scripts. Their smoke profiles pass. The real-autodiff pipeline also ran
preregistered development-pilot cells on the two target model sizes. The full
P0 evaluation grids have not run, so none of their smoke or pilot outputs is used
as main-paper evidence. The separate coverage-matched operator grid did run in
full and is now included as main-paper mechanism evidence.

The legacy main scaling figure remains in the manuscript and is explicitly
labelled a failed-premise, one-step-equivalence diagnostic. It has not been
silently replaced by smoke output. Coverage-matched operator evaluation and the
balanced MNIST pipeline are implemented; the former ran in full, while the
latter now passes its real-data smoke profile after the canonical archives were
retrieved through the approved forward proxy. The full MNIST grid has not run,
and the dataset cache is intentionally not tracked by Git. The anonymous release
also remains blocked by historical raw inputs and Covertype fixtures absent from
this checkout.

## Commits

- `bce0c117` records the pre-edit baseline.
- `504e3b6a` sharpens feature drift and adds spectral-tail regret closure.
- `40c51dca` adds corrected-center, bounded-output, architecture-obstruction,
  and lower-bound statements.
- `98745976` adds the spectral-tail experiment pipeline.
- `03dfe082` adds the premise-clean rotated scaling pipeline.
- `69c2971c` adds the real `torch.func` GGN benchmark pipeline.

## Theory Changes

### Sharpened feature drift

For the principal frozen whitening, the manuscript now defines stacked matrices
`A_t` and `B_t`, checks their dimensions, proves `A_t^T A_t = I`, identifies
`B_t^T B_t` with the whitened current GGN, and proves

```text
(1 - chi_t)^2 Cbar_t <= C_t <= (1 + chi_t)^2 Cbar_t
```

for `chi_t < 1` by singular-value perturbation. The unconditional one-sided
upper inequality is retained. Downstream drift factors use
`rho_- = (1-x_T)^2` and `rho_+ = (1+x_T)^2`.

### Frozen-potential regret

The exact-current corollary keeps the time-varying factor inside one
Cauchy--Schwarz step:

```text
sum_t alpha_t^2 omega_t^2 ((1+bar_chi_t)/(1-bar_chi_t))^2.
```

This replaces the nonmonotone dynamic-width complexity by the frozen elliptic
potential only in the exact-current, small-drift regime. A corrected-center
version removes the centering premise but requires frozen-feature access.

### Spectral-tail closure

For eigenvalues `nu_i` of `Cbar_{T+1}-lambda I`, the new log-determinant lemma
proves

```text
gamma_T <= r_T log(1 + T G^2/(r_T lambda sigma^2))
           + Delta_{T,r}/lambda,
```

with explicit `r=0`, zero-gradient, and exact-rank conventions. The combined
corollary does not assume a supplied tangent subspace. A realized terminal tail
is used only for a posteriori complexity; only a deterministic or predictable
prefix envelope may replace the online information-gain schedule.

### Additional closures and limits

- The corrected-center near-linear corollary removes optimizer and
  collection-residual assumptions, requires `W = Omega(T)` for bounded
  transfer, and displays its replay/memory requirement.
- The bounded-output lemma gives a simultaneous finite-horizon
  collection-residual envelope under conditional sub-Gaussian noise.
- The exact-rank linear subclass is related to the standard
  `Omega(r sqrt(T))` stochastic linear-bandit lower bound; no lower bound is
  claimed for the nonlinear or spectral-tail class.
- The attempted two-layer width theorem is documented as an obstruction. No
  full-Hessian rate or optimizer-residual rate is fabricated.

Independent derivations and edge cases are recorded in
`THEORY_DERIVATIONS.md`. Tests cover random drift sandwiches, Loewner inversion
directions, spectral-tail log determinants, `r=0`, exact rank, zero gradients,
and `chi` approaching one.

## Experiment Pipelines

### Spectral tail

Files:

- `experiments/run_spectral_tail_study.py`
- `experiments/make_spectral_tail_artifacts.py`
- `experiments/configs/spectral_tail_study.yaml`
- `scripts/reproduce_fig_spectral_tail.sh`

The fixed full configuration uses `d=256`, `K=8`, five horizons, four target
ranks, three decay exponents, random rotations, and prespecified tail-alignment
cells. It includes dense full Gram, residual-checked full CG, rank truncation,
diagonal, block diagonal, Frequent Directions, and greedy. Tuning seeds `0--9`
and evaluation seeds `1000--1049` are disjoint. The smoke run executed 312
tuning and 168 evaluation trajectories. The full grid was not run.

### Premise-clean scaling

Files:

- `experiments/run_certified_scaling.py`
- `experiments/make_certified_scaling_artifacts.py`
- `experiments/configs/certified_scaling.yaml`
- `scripts/reproduce_fig_certified_scaling.sh`

The construction is a rotated sign-symmetric linear bandit with analytic cyclic
window excitation after burn-in, condition numbers `10`, `100`, and `1000`, a
closed-form ridge optimizer, and nontrivial Krylov spectra. The smoke run
executed 14 trajectories; every declared premise passed and 98.4% of CG rounds
used more than one iteration. The requested 50-seed full grid was not run and
has not replaced Figure 1.

### Real autodiff GGN

Files:

- `experiments/run_autodiff_ggn_benchmark.py`
- `experiments/make_autodiff_ggn_artifacts.py`
- `experiments/configs/autodiff_ggn_benchmark.yaml`
- `scripts/reproduce_fig_autodiff_ggn.sh`

The benchmark uses real `torch.func.jvp`, `torch.func.vjp`, and `torch.vmap`
through a Buck-managed Conda/PyTorch toolchain. Matrix-free methods do not retain
an explicit sample-by-parameter Jacobian. The configured MLPs contain 131,841
and 9,972,737 parameters. Methods include separate CG, batched CG, streaming
Jacobi-PCG, diagonal, last-layer, and a small-model dense reference.

The smoke JVP/VJP operator matched the explicit Jacobian to approximately
`1e-16`. One development-pilot cell (`m=32`, `K=5`, target `0.1`) ran for each
model on an NVIDIA accelerator. Approximate single-repetition pilot times were
0.025 seconds for small-model batched CG and 0.096 seconds for large-model
batched CG. The large model used roughly 2.25 GB peak accelerator memory in
that cell. These are development measurements without evaluation-seed intervals
and are not reported as comparative paper results. The full 10-seed evaluation
grid and 24-accelerator-hour study were not run.

### Coverage-matched operator study

Files:

- `experiments/run_coverage_matched_operator_study.py`
- `experiments/make_coverage_matched_operator_artifacts.py`
- `experiments/configs/coverage_matched_operator.yaml`
- `scripts/reproduce_fig_coverage_matched_operator.sh`

The fixed eight-cell condition/rotation/gap design compares seven operator
labels under identical theoretical coefficients, tuning-selected 95% one-step
coverage, and tuning-selected mean bonus magnitude. Coefficients are pooled over
all cells and tuning seeds 2000--2019, then frozen before evaluation seeds
2100--2149. The complete run contains 8,400 evaluation trajectories. Holm
adjustment covers all 144 prespecified method/cell/protocol comparisons.

Significant comparisons remain mixed under every protocol. The identical
coefficient has 35 significant cells (13 lower regret for a surrogate, 22 for
full); coverage matching has 20 (8/12); mean-bonus matching has 27 (11/16).
Evaluation coverage under the coverage-matched protocol averages 94.6% across
method/cell means. Current and historical full Grams are separate audit labels
but algebraically identical in this fixed-feature linear environment. LO-FI is
not included because no compatible recursive precision implementation exists in
the repository. These independently executed policy differences are not given a
causal operator interpretation.

### Balanced MNIST benchmark

Files:

- `experiments/run_mnist_contextual_benchmark.py`
- `experiments/make_mnist_contextual_benchmark_artifacts.py`
- `experiments/configs/mnist_contextual_benchmark.yaml`
- `scripts/reproduce_fig_mnist_contextual_benchmark.sh`

The pipeline fixes deterministic label-stratified, disjoint
supervised-pretraining, tuning, and evaluation splits, tuning seeds 3000--3009,
evaluation seeds 3100--3119, equal four-cell tuning budgets, `T=5000`, and
twelve explicitly local method implementations.
The all-layer tanh reward model has manually derived full-parameter Jacobians;
finite differences validate them. Current full GGN recomputes every historical
selected Jacobian rather than silently substituting a window. Tests execute all
twelve methods on a balanced synthetic fixture, but that fixture is test-only.

No full MNIST outcome is reported. The four canonical archives from
`storage.googleapis.com/cvdf-datasets/mnist` passed their published MD5 checks
and IDX header checks. The real-data smoke profile completed all twelve methods
and reported a 10% context-free optimum for both tuning and evaluation. Smoke
outputs are not used as paper evidence, and the code does not substitute sklearn
digits or synthetic images under the MNIST name.

## Reproducibility

Raw outputs from new runs are ignored under `results/raw/`; derived artifacts
and hash/provenance inventories are the intended Git surface. Main-study entry
points generate derived JSON/CSV, figures, table fragments, and SHA-256
sidecars. The repository resource target now includes `scripts/**` and
`tables/generated/**`.

Every run manifest records the resolved configuration, PCG64/Torch seed, Git
revision and dirty state, UTC timestamp, package versions, and hardware.
PyTorch deterministic behavior is enabled where supported. Evaluation seeds do
not appear in tuning manifests, and no reported environment or hyperparameter
was selected from evaluation output.

The legacy 2.1 GB scaling raw tree is absent from Git. Historical tanh raw
inputs and two required Covertype fixtures are also absent, so the current
checkout cannot rebuild every legacy raw-to-figure chain or either anonymous
release tier. This is disclosed in the manuscript rather than bypassed.

## Manuscript Changes

- The abstract distinguishes conditionally sub-Gaussian data from the Gaussian
  squared-loss quasi-likelihood and leads with the approximate-rank,
  small-drift result.
- The introduction explains current-parameter relinearization relative to the
  predictable historical-gradient Gram.
- Contributions put the full-dimensional spectral-tail result first and the
  generic transfer theorem second; exact supplied subspaces are computational
  shortcuts.
- Related work positions the method against matrix-free predictive variance,
  NeuralUCB/NeuralTS, NTK and regression approaches, EKF/LO-FI, structured
  Laplace, Frequent Directions, and dyadic sketching.
- The conclusion states the strongest proved regime and the open problem of
  controlling feature drift and spectral tail during unrestricted training.
- Autodiff language now says smoke/development pilots ran but the evaluation
  systems grid did not.
- The main mechanism figure reports the full coverage-matched grid and the text
  reports all Holm-adjusted direction counts, including cells unfavorable to
  full curvature.
- The MNIST text distinguishes the validated real-data smoke path from the unrun
  full benchmark.

The abstract makes no claim based on the unrun new grids and no longer cites a
run count whose complete raw chain is absent.

## Validation

- `buck2 test //tests:tests //experiments/tests:tests -- --timeout=1200`:
  2 targets passed, 0 failed.
- `buck2 run //paper:validate`: 173 unique labels, 124 resolved reference
  targets, 36 valid citation keys, no blockers.
- `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex`: passed;
  references and citations stabilized, and `paper/main.pdf` has 48 pages.
- `buck2 run //tools:pytest_runner -- -q
  experiments/tests/test_mnist_contextual_benchmark.py`: 4 tests passed.
- `PROFILE=smoke scripts/reproduce_fig_mnist_contextual_benchmark.sh`: passed on
  canonical MNIST, including all twelve methods and artifact generation.
- The only overfull box is the pre-existing 5.12 pt style-generated abstract
  boundary. No changed theorem display causes an overfull box.
- A detached literal checkout at `928f2a64` passed both Buck test targets and a
  from-scratch `latexmk` build with stable references and citations.
- The clean-checkout review-tier command
  `buck2 run //tools:build_anonymous_supplement -- --tier review ...` stopped at
  the first missing required fixture,
  `experiments/data/sklearn/covertype/samples_py3`. Release validation was not
  bypassed.

## Deliberately Unmade Claims

- No unrestricted neural-network regret theorem.
- No theorem that generic network width implies `W^{-1/2}` smoothness or
  optimizer residual.
- No online use of terminal rank, eigenspace, or spectral-tail statistics.
- No theorem validation claim for a cell with a failed premise.
- No practical or foundation-model scalability claim from development pilots.
- No uniform regret advantage for full curvature.
- No causal operator interpretation of independently executed policy regret.
- No complete anonymous or clean raw-to-figure release claim.
- No full MNIST result or claim from the real-data smoke output.

## Remaining Work

P0 work still requiring substantial compute or external inputs:

- run the full spectral-tail evaluation grid;
- run the full premise-clean scaling grid and replace Figure 1 only after all
  required premises validate;
- run the full real-autodiff evaluation grid and generate systems artifacts;
- restore legacy raw inputs or explicitly remove those legacy main-paper claims;
- rebuild and identity-scan the anonymous release from a literal clean checkout.

P1 work still blocked or incomplete:

- run the full balanced MNIST benchmark and provide a redistributable fixture or
  source manifest for clean-checkout reproduction; all neural baselines are
  currently local matched implementations, not verified official reproductions;
- add a compatible LO-FI implementation to the coverage study;
- run matched-compute tuning for MNIST using the now-available canonical data.

External submission prerequisites still missing are the official target-year
AISTATS style/checklist package and the data required by the release builder.
