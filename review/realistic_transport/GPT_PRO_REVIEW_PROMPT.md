# GPT Pro prompt: review the realistic confidence-transport benchmark

Act as a skeptical AISTATS reviewer, mathematical machine-learning researcher,
and research software engineer. Review the implementation and evidence in a
local clone of:

```text
https://github.com/buiksat/Curvature-Calibrated-Exploration
```

Use branch:

```text
cce-experiments
```

The benchmark was added relative to:

```text
d00594a80517cdca84f97a95056669f48c6a1be4
```

The functional benchmark head before the handoff-only documentation change is:

```text
dbd0b4388ba4b441a0854642b48f87939ffbaf43
```

Verify the actual local and remote branch state before reviewing. If the remote
cannot be reached, record the exact failure and distinguish the local
remote-tracking ref from a live remote observation. Do not reset the branch to
one of the SHAs above. Review the actual current `cce-experiments` head and
identify any changes after `dbd0b43` separately.

This is a read-only review. Do not edit files, regenerate committed evidence,
push, open a pull request, or start the full Covertype evaluation. Safe tests
and temporary outputs outside the repository are allowed. Preserve the working
tree and report if it was already dirty.

## Review objective

Decide whether the changes from `d00594a` through the current head correctly
implement the preregistered realistic confidence-transport benchmark and are
ready for the Covertype pilot, tuning, selection lock, and evaluation.

The main question is:

> Does the implementation faithfully test corrected-center operational
> confidence transport on real-data context geometry with approximate current
> curvature and fixed-operator CG, without data leakage, oracle leakage,
> invalid certificates, or post hoc selection?

Do not evaluate the paper based on the one-seed Digits smoke result. The full
Covertype experiment has not run.

## Read first

Read these files completely before judging the diff:

```text
handoff.md
README.md
BUCK2_SETUP.md
GITHUB_ONLY_TRANSPORT_REVIEW.md
TRANSPORT_INSTANTIATION_COMPLETION_REPORT.md
THEORY_TRANSPORT_DERIVATIONS.md
THEORY_GENERALIZATION_AUDIT.md

paper/main.tex
paper/macros.tex
paper/transport_theory.tex
paper/transport_proofs.tex
paper/transport_experiment.tex
paper/transport_experiment_appendix.tex

experiments/REALISTIC_TRANSPORT_PROTOCOL.md
experiments/configs/realistic_transport_covtype.yaml
experiments/realistic_transport/README.md
experiments/realistic_transport/BUCK
experiments/realistic_transport/*.py
experiments/realistic_transport/tests/*.py

tools/prepare_covtype_benchmark.py
tools/verify_transport_committed_evidence.py
tests/test_experiment_pipeline.py

review/realistic_transport/CLAIM_TRACE.md
review/realistic_transport/COMMAND_LOG.md
review/realistic_transport/COMMAND_LOG.json
review/realistic_transport/DATA_PROVENANCE.json
review/realistic_transport/SELECTION.json
review/realistic_transport/RESULTS.md
review/realistic_transport/covtype_not_run.json
```

Follow every relevant `\input`, import, Buck dependency, configuration
reference, and generated-artifact reference. Treat the paper as authoritative
for theorem-facing formulas and the new protocol as authoritative for the
preregistered benchmark.

## Establish the diff and repository state

At minimum, run and record:

```bash
git status --short --branch
git branch --show-current
git rev-parse HEAD
git rev-parse origin/cce-experiments
git ls-remote origin refs/heads/cce-experiments
git log --oneline --decorate -12
git diff --check d00594a80517cdca84f97a95056669f48c6a1be4..HEAD
git diff --stat d00594a80517cdca84f97a95056669f48c6a1be4..HEAD
git diff --name-status d00594a80517cdca84f97a95056669f48c6a1be4..HEAD
```

Review all source changes, not only the handoff or generated result files.
Confirm that no paper source, old locked result, or legacy evidence source was
silently changed.

## Required review lenses

### 1. Equation-to-code correctness

Trace these objects from the paper into executable code and tests:

1. frozen metric `Vbar_t`;
2. exact current replay metric `V_t`;
3. pseudo-response;
4. frozen linearized estimator;
5. corrected and uncorrected centers;
6. historical and current Taylor envelopes;
7. historical and current misspecification envelopes;
8. corrected confidence radius, including the outer `1/sigma` and
   sum-before-square convention;
9. `Q_t` and operational path certificate;
10. endpoint Thompson distance;
11. two-sided operator factors;
12. all-action CG upper-width map;
13. played-action sharpness factor;
14. score maximization and smallest-index tie-breaking;
15. instantaneous and cumulative regret bounds;
16. coverage, optimism, nonvacuity, runtime, memory, and provenance metrics.

For each item, state whether the implementation matches the paper, matches only
the protocol, or introduces a new lemma that requires an independent argument.
Do not accept comments or tests as proof that the implementation is correct.

### 2. Data preparation and leakage

Verify:

- `fetch_covtype` is isolated to preparation and the locked runtime consumes a
  digest-checked prepared artifact;
- the semantic digest is independent of NPZ or ZIP timestamps;
- split assignment depends only on the semantic digest and row index;
- all rows are covered exactly once and splits do not overlap;
- preprocessing and the teacher use development rows only;
- evaluation labels cannot enter preprocessing, teacher fitting, tuning,
  scoring, or action selection;
- label mapping, PCA sign convention, degenerate-boundary handling, context
  normalization, feature norms, and row-major Kronecker ordering are correct;
- potential outcomes and contexts are paired across methods while policies see
  only selected rewards.

### 3. Task definitions and statistical assumptions

Check all three tasks separately. In particular:

- Task A uses a valid conditional sub-Gaussian proxy for Bernoulli rewards and
  never presents its heuristic confidence fields as theorem-valid;
- Task B is exactly realizable through the learner model up to declared
  float64 tolerance;
- Task C constructs `rho` from development data only and uses uniform `rho` in
  policy envelopes rather than realized perturbations;
- no evaluation outcome influences the optimizer, LinUCB alpha, rank,
  tolerance, horizon, seeds, or practical-method selection.

### 4. Predictable timing and policy semantics

Audit the round order. The current reward and label must remain unavailable
until every action score and the selected action are fixed. Check that each
method has an independent representation path and history. Verify exact method
names and semantics for all 13 preregistered methods, including which methods
are oracle, operational, baseline, or uncertified.

### 5. Nyström construction

Independently verify the argument:

```text
0 <= H_r <= H
E = H - H_r >= 0
E <= trace(E) I
A = lambda I + H_r
[lambda/(lambda+trace(E))] V <= A <= V
```

Check the pseudoinverse cutoff, truncation, symmetry handling, negative
eigenvalue policy, empty history, rank-zero behavior, exact-rank behavior, and
scale-aware tolerances. Confirm that the operational approximate method does
not form dense `H` or compute oracle eigenspectra except at separately timed
diagnostic checkpoints. Assess whether algorithm-only runtime and memory
comparisons are fair.

### 6. CG width map

Independently verify the exact-arithmetic bounds based on the recomputed true
residual:

```text
e = ||r|| / sqrt(lambda_lower)
n = sqrt(x_tilde.T A x_tilde)
upper = n + e
lower = max(0, n-e, ||q||/sqrt(lambda_max_upper))
alpha = upper/lower
```

Check zero queries, exact initial solutions, nonconvergence, maximum iterations,
matvec counts, scale extremes, immutable operators, recursive-versus-true
residual discrepancies, and lower-bound zero handling. Confirm that scores for
all actions, action selection, and the selected-action `alpha` use the same
precomputed width map with no post-selection refinement.

The paper explicitly distinguishes float64 diagnostics from verified numerical
certificates. Reject any code, artifact, or prose that claims interval-quality
certification without enclosed arithmetic.

### 7. Tuning, freeze, and provenance

Check that:

- tuning, selection, and evaluation seed sets are disjoint;
- the two controlled tasks share one representation optimizer and Task A uses
  a separate optimizer;
- LinUCB selection and practical Nyström selection follow the frozen tie rules;
- deterministic failures reject candidates and remain visible;
- a selection-only commit can follow the freeze commit without invalidating the
  frozen source inventory;
- evaluation requires unchanged source and configuration hashes plus exact
  selection hashes;
- raw and aggregate provenance rejects duplicates, incomplete grids, mixed
  revisions, mixed configuration digests, missing rounds, and nonfinite values;
- paths and metadata do not leak machine-specific absolute paths or personal
  information.

Inspect the distinction among `source_revision`, `freeze_revision`, and
`selection_lock_revision`. The smoke aggregate and data-provenance file contain
a `null` common `freeze_revision` while recording the freeze commit elsewhere.
Determine whether this is correct smoke semantics, a reporting defect, or a
future full-run blocker.

The committed smoke artifacts name the execution-time branch
`codex/realistic-transport-benchmark`, although those commits are now on
`cce-experiments`. Treat this as historical provenance unless a bound artifact
incorrectly claims to describe the current branch.

### 8. Aggregation and statistics

Verify seed-level independence, paired comparisons, deterministic 10,000-draw
bootstrap resampling, exact Clopper-Pearson intervals, zero-denominator counts,
four-corner rank/tolerance contrasts, and task-specific reporting. Confirm that
Task A is never pooled into theorem-validity claims and that one 500-round
trajectory supplies prefixes without changing the environment or `W`.

Check that artifact generation is deterministic and that every aggregate binds
its complete raw-input inventory. Confirm that smoke and pilot profiles cannot
be mislabeled as publication evidence.

### 9. Test and build integration

Run the documented checks where the environment supports them:

```bash
buck2 test //tests:tests //experiments/tests:tests \
  //experiments/realistic_transport:tests -- --timeout=1200
buck2 run //paper:validate
python3 tools/verify_transport_committed_evidence.py
make pdf
```

If the configured Buck2 binary fails because of the documented Prelude/API
mismatch, record that exact blocker. A different Buck2 binary or direct pytest
run is supplementary evidence, not automatically equivalent. Do not install
packages, edit global configuration, or overwrite committed artifacts for this
review.

Inspect test quality, not only test count. Identify missing adversarial cases,
tests that merely repeat implementation logic, and assertions too weak to
detect scientific leakage or certificate invalidity.

### 10. Scientific design and AISTATS relevance

Assess whether the fixed design can answer its stated question. Address these
known risks:

- Covertype acquisition, pilot, tuning, selection, and evaluation are unrun;
- the required semantic digest is not frozen yet;
- the scaled-tanh `W` values make the model nearly linear and may underpower
  corrected-center and curvature-transport ablations;
- the Digits smoke showed very large operational `D_Q` to endpoint-distance
  ratios and vacuous theorem bounds, but has only one seed and is not
  publication evidence;
- the current study driver may require external sharding to realize its stated
  four-worker wall-time estimate;
- at dimension 135, dense Cholesky may outperform low-rank CG, so compute claims
  must include construction and certification cost.

State whether these are implementation defects, protocol limitations, or open
empirical questions. Do not infer equivalence from null results and do not use
smoke outcomes to change the preregistered grid.

## Finding standard

Report a finding only after verifying it against the implementation, tests,
paper, and protocol. For every finding include:

- severity: blocking, major, moderate, or minor;
- exact file and line;
- the violated formula, invariant, or preregistered rule;
- a concrete counterexample, execution trace, or reproducible test when
  possible;
- scientific or engineering impact;
- the smallest correct fix;
- whether existing smoke evidence would need regeneration.

Reject speculative findings that do not survive adversarial checking. Separate
correctness problems from design limitations and optional improvements.

## Required output

Return one review with these sections:

1. **Verdict**: `ready for Covertype pilot`, `ready after fixes`, or `not ready`.
2. **Blocking and major findings**, ordered by severity.
3. **Moderate and minor findings**.
4. **Equation-to-code audit**, covering all 16 objects above.
5. **Data-leakage and temporal-order audit**.
6. **Nyström and CG certificate audit**.
7. **Tuning, aggregation, statistics, and provenance audit**.
8. **Tests and commands run**, with exit status and environment limitations.
9. **Checks cleared**, naming the high-risk areas inspected with no surviving
   finding.
10. **AISTATS interpretation**, separating facts, evidence, and inference for:
    corrected-center validity, operational transport, approximate curvature,
    CG practicality, misspecification robustness, real-data competitiveness,
    and the overall acceptance case.
11. **Single next action** with the highest expected effect on correctness or
    the AISTATS decision.

Do not end with a generic offer to do more work. Do not edit the manuscript or
reinterpret smoke evidence as a completed experiment.
