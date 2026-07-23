# Resubmission Revision Report

Date: 2026-07-23

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
scripts. Their full evaluation grids ran. The spectral-tail study contains
7,440 tuning and 8,400 evaluation trajectories; the premise-clean scaling study
contains 10,800 evaluation trajectories; and the real-autodiff study completes
all 360 cells over ten fixed evaluation instances in 0.167 accelerator-hours.
Their derived aggregates, figures, generated tables, hashes, and provenance are
main-paper evidence; the multi-gigabyte seed-level raw trees remain ignored by
Git.

The branch tip no longer tracks any file under `results/raw/`. The cleanup
removed 13,223 generated paths from the index while retaining all local raw
outputs for analysis. A literal checkout now contains 328 tracked files rather
than 13,551; compact derived aggregates, figures, tables, and hashes remain the
versioned evidence surface.

The new all-premise-pass scaling figure replaces the legacy main figure. The
legacy failed-premise, one-step-equivalence grid is retained in the appendix as
a diagnostic. Coverage-matched operator evaluation also ran in full. The
balanced MNIST pipeline passes its canonical-data smoke profile, and its full
tuning/evaluation run is recorded separately below. Public dataset caches are
not Git inputs and no release tier now depends on a particular scikit-learn
cache serialization.

## Commits

- `bce0c117` records the pre-edit baseline.
- `504e3b6a` sharpens feature drift and adds spectral-tail regret closure.
- `40c51dca` adds corrected-center, bounded-output, architecture-obstruction,
  and lower-bound statements.
- `98745976` adds the spectral-tail experiment pipeline.
- `03dfe082` adds the premise-clean rotated scaling pipeline.
- `69c2971c` adds the real `torch.func` GGN benchmark pipeline.
- `bda79cbf` records the completed evaluation grids and regenerated manuscript.
- `617b5389` removes all generated raw outputs from the Git index.
- `9b5cb592` through `a7d1ed65` make both anonymous tiers build, sanitize, and
  validate honestly from a compact clean checkout.

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
prefix envelope may replace the online information-gain schedule. Because the
deterministic inequality holds simultaneously for every rank, the terminal
report may minimize over rank post hoc, but that choice cannot alter any past
radius, action, or eigenspace.

### Additional closures and limits

- The corrected-center near-linear corollary removes optimizer and
  collection-residual assumptions, requires `W = Omega(T)` for bounded
  transfer, and displays its replay/memory requirement. Its prefix information
  envelope is replaced by the predictable monotone closure
  `G_up(n,r)=max_{j<=n} G(j,r)`; the final rate condition is on
  `G_up(T,r)`, closing the nonmonotone-envelope proof gap identified in review.
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
and evaluation seeds `1000--1049` are disjoint. The full run executed 7,440
tuning and 8,400 evaluation trajectories. At target rank 8 and spectral decay
2, rank truncation has mean terminal regret 0.283 in the head-aligned cell but
88.176 in the decision-relevant-tail cell, versus 0.714 and 1.771 for exact
full. Full CG matches dense full in all paired terminal comparisons. The
spectral construction remains a one-Krylov-step equivalence case; nontrivial
Krylov behavior is supplied by the premise-clean scaling grid.

### Premise-clean scaling

Files:

- `experiments/run_certified_scaling.py`
- `experiments/make_certified_scaling_artifacts.py`
- `experiments/configs/certified_scaling.yaml`
- `scripts/reproduce_fig_certified_scaling.sh`

The construction is a rotated sign-symmetric linear bandit with analytic cyclic
window excitation after burn-in, condition numbers `10`, `100`, and `1000`, a
closed-form ridge optimizer, and nontrivial Krylov spectra. The full run executed
10,800 trajectories: 27 dimension/rank/condition cells, eight methods, and 50
evaluation seeds. Every required premise field passes and every full/window CG
solve converges; all 216 aggregate groups are clean. Full CG uses multiple
iterations in every reported high-condition cell and its maximum measured
energy error remains below `1e-3`. The active-space simulator uses dense
prefix-Gram algebra, so its work totals are replay-equivalent sample-CVP
accounting rather than systems timings. All methods have identical regret in
the sign-symmetric construction; this validates premises and work accounting,
not a policy advantage.

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
`1e-16`. The full study completed all 360 cells with no skips: two model sizes,
three buffers, two action counts, three residual targets, and ten evaluation
instances. At `m=512`, `K=10`, and target residual `1e-3`, mean batched-CG times
are 0.0395 and 0.5674 seconds for the small and large models; peak allocated
accelerator memory is 0.126 and 4.219 GiB. The small-model explicit reference
uses 1.477 GiB in that cell. The large model intentionally has no dense
reference. These are isolated primitive measurements after warm-up on one
accelerator, not model-training or end-to-end bandit throughput.

### Coverage-matched operator study

Files:

- `experiments/run_coverage_matched_operator_study.py`
- `experiments/make_coverage_matched_operator_artifacts.py`
- `experiments/configs/coverage_matched_operator.yaml`
- `scripts/reproduce_fig_coverage_matched_operator.sh`

The fixed eight-cell condition/rotation/gap design compares eight operator
labels under identical theoretical coefficients, tuning-selected 95% one-step
coverage, and tuning-selected mean bonus magnitude. Coefficients are pooled over
all cells and tuning seeds 2000--2019, then frozen before evaluation seeds
2100--2149. The complete run contains 9,600 evaluation trajectories. Holm
adjustment covers all 168 prespecified method/cell/protocol comparisons.
Each marginal test is a two-sided paired Student-t test on the 50 seed-level
terminal-regret differences, with Holm familywise control at 0.05. Identically
zero differences receive `p=1`; constant nonzero differences receive the
limiting value `p=0`. The generated appendix tables report every mean paired
difference, raw p-value, adjusted p-value, and classification.

Significant comparisons remain mixed under every protocol. The identical
coefficient has 35 significant cells (13 lower regret for a surrogate, 22 for
full); coverage matching has 20 (8/12); mean-bonus matching has 27 (11/16).
Evaluation coverage under the coverage-matched protocol averages 94.6% across
method/cell means. Current and historical full Grams are separate audit labels
but algebraically identical in this fixed-feature linear environment. LO-FI is
represented by a rank-three low-rank-plus-diagonal batch refit; it is explicitly
not an official LO-FI reproduction, and none of its 24 comparisons survives
Holm adjustment. These independently executed policy differences are not given
a causal operator interpretation.

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
selected Jacobian rather than silently substituting a window. To keep the full
grid within its fixed compute budget, the online model uses 64 fixed pixels, one
hidden unit, and 85 trainable parameters. The three full-Gram methods use exact
dense float64 solves in this small benchmark; matrix-free CG evidence comes from
the separate real-autodiff study. Maximum original-system relative residual is
below `7e-12`.

The four canonical archives from `storage.googleapis.com/cvdf-datasets/mnist`
passed their published MD5 and IDX header checks. Both online pools are exactly
class-balanced. The full run completed 480 tuning and 240 evaluation policies.
All methods remain at chance: mean accuracy ranges from 9.885% to 10.068%, and
mean terminal regret from 4496.6 to 4505.75. Current full GGN has regret 4501.75
with interval `[4490.97,4512.53]`; none of its 11 paired comparisons survives
Holm adjustment. This is retained as a failed small-model benchmark, not as
evidence of parity or practical utility. The rejected preliminary run with all
10,000 test examples exposed an 11.35% majority class; the final 8,000-example
pool fixes that protocol defect. A float32 draft was also rejected because its
dense-solve residual exceeded `1e-3`.

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

The legacy 2.1 GB scaling raw tree and historical tanh raw inputs are absent
from Git, so the checkout cannot independently rebuild every legacy
raw-to-figure chain. Public dataset caches are optional release accelerators:
the anonymous builder no longer requires a particular scikit-learn cache
serialization. This is disclosed in the manuscript rather than hidden.

When raw inputs are absent, release provenance retains their recorded path and
SHA-256 with availability `not_in_compact_checkout`; public cache inputs use
`public_dataset_cache_not_in_checkout`. The top manifest reports
`passed_with_declared_unavailable_inputs`, not an unqualified provenance pass.

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
- The completed real-autodiff figure and table report the full ten-instance
  systems grid and clearly separate isolated operator timing from training.
- The main mechanism figure reports the full coverage-matched grid and the text
  reports all Holm-adjusted direction counts, including cells unfavorable to
  full curvature.
- The premise-clean scaling figure replaces the failed-premise legacy main
  figure; the old grid remains available in the appendix.
- The full balanced-MNIST result is reported as a chance-level failed benchmark;
  the dense 85-parameter execution is separated from matrix-free systems claims.

The abstract no longer cites a run count whose complete raw chain is absent.

### Submission packaging

- The rendered submission body now occupies seven pages; references start on
  PDF page 8, within the eight-page AISTATS submission limit. The references
  occupy pages 8--9 and the appendix starts on page 10.
- Theorem 1's sublinearity statement, exact-current instantiation, and proof
  sketch now immediately follow Theorem 1, before Corollaries 2--3.
- The growing-window theorem, work accounting, secondary experiment figures,
  premise table, and detailed protocols now render after the references. The
  main experiment section retains the spectral-tail regret figure and a compact
  summary of the premise-clean, autodiff, calibration, and negative benchmark
  findings.
- The appendix distinguishes the batch-refit low-rank-plus-diagonal LO-FI-style
  control from an unavailable official recursive LO-FI implementation.
- Every Matplotlib paper generator forces PDF/PS font type 42. Redundant
  internal suptitles were removed from the spectral-tail, premise-clean
  scaling, and JVP/VJP figures; their two-row legends have reserved top margins,
  and the scaling work axes use at most five major logarithmic ticks.
- Visual inspection of compiled PDF pages 7, 15, and 17 confirms that the
  affected legends, panel titles, and tick labels do not overlap. A Ghostscript
  decompressed-object scan finds 0 Type 3 font objects, 21 Type 0 fonts with
  CIDFontType2 descendants for plotted text, and the expected Type 1 TeX fonts.

## Validation

- `buck2 test //tests:tests //experiments/tests:tests -- --timeout=1200`:
  2 targets passed, 0 failed.
- `buck2 run //paper:validate`: 187 unique labels, 131 resolved reference
  targets, 36 valid citation keys, no blockers.
- `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex`: passed;
  references and citations stabilized, and the revised `paper/main.pdf` has 65
  pages with references beginning on page 8.
- Targeted coverage/phase tests: 9 passed. The full expanded run regenerated
  9,600 policies and complete 168-row appendix comparison tables.
- Full balanced-MNIST reproduction: 480 tuning and 240 evaluation policies,
  exact 10% class priors, all twelve methods, figures, table, and derived report.
- The only overfull box is the pre-existing 5.12 pt style-generated abstract
  boundary. No changed theorem display causes an overfull box.
- Literal detached checkout `a7d1ed65`: both Buck test targets passed; static
  validation found 185 unique labels, 129 resolved reference targets, and 36
  valid citation keys; forced LaTeX compilation produced 64 pages with no
  unresolved reference or citation.
- The clean-checkout review tier built 290 files (98.3 MiB), passed identity
  scanning over 276 files, checked 55 provenance sidecars and 24,203 input
  references, and checked all 28 paper inputs.
- The clean-checkout full tier built 289 files (98.3 MiB), passed identity
  scanning over 275 files, checked the same 55 provenance sidecars and all 28
  paper inputs. Both manifests explicitly mark 24,133 raw and three public-data
  cache references as unavailable rather than claiming they are released.
- After page-limit restructuring and figure regeneration, the compiled PDF has
  65 pages because all displaced material remains in the appendix; references
  begin on page 8 and no Type 3 font object remains.
- A literal detached checkout of the packaging commits passes both Buck test
  targets, static manuscript validation, a forced 65-page LaTeX rebuild, and
  the anonymous review-tier build (290 files, 98.3 MiB, identity scan passed,
  24,203 provenance inputs classified).

## Deliberately Unmade Claims

- No unrestricted neural-network regret theorem.
- No theorem that generic network width implies `W^{-1/2}` smoothness or
  optimizer residual.
- No online use of terminal rank, eigenspace, or spectral-tail statistics.
- No theorem validation claim for a cell with a failed premise.
- No practical or foundation-model scalability claim from the measured models.
- No uniform regret advantage for full curvature.
- No causal operator interpretation of independently executed policy regret.
- No claim that the chance-level MNIST result validates any policy.

## Remaining Work

The new P0/P1 experiment grids are complete. Remaining external or historical
limitations are:

- the absent legacy raw trees cannot be reconstructed from the compact checkout;
- MNIST neural baselines remain local matched implementations rather than
  verified official packages;
- the official target-year AISTATS style/checklist package is not available in
  this checkout and is not fabricated.
