# Handoff: realistic confidence-transport benchmark

Updated: 2026-08-24

## Repository state

- Repository: `https://github.com/buiksat/Curvature-Calibrated-Exploration`
- Active branch: `cce-experiments`
- Base revision before this benchmark: `d00594a80517cdca84f97a95056669f48c6a1be4`
- Functional benchmark head before this handoff: `dbd0b4388ba4b441a0854642b48f87939ffbaf43`
- Local `origin/cce-experiments` currently resolves to the same functional head.
- A live `git ls-remote` check still fails because this host cannot resolve
  `github.com`, so the actual GitHub ref has not been independently confirmed.
- The former local branch `codex/realistic-transport-benchmark` was
  fast-forwarded into `cce-experiments` and deleted.
- No push or pull request was performed by the implementation session.
- The worktree was clean before adding this handoff and its review prompt.

The benchmark stack contains these commits:

1. `a83e370` - add the preregistered realistic transport benchmark.
2. `40c39fa` - tighten aggregate and source-inventory provenance.
3. `dbd0b43` - record the deterministic Digits smoke evidence.

Use `git diff d00594a80517cdca84f97a95056669f48c6a1be4..HEAD` to review the
complete change. The implementation and smoke artifacts were produced before
the branch fast-forward, so immutable evidence fields that name
`codex/realistic-transport-benchmark` describe the execution-time state. Do not
rewrite those fields without regenerating the bound artifacts and sidecars.

## What was added

The change adds a falsification-oriented Covertype benchmark for the paper's
corrected-center confidence-transport construction:

- preregistration in
  [`experiments/REALISTIC_TRANSPORT_PROTOCOL.md`](experiments/REALISTIC_TRANSPORT_PROTOCOL.md);
- frozen JSON configuration in
  [`experiments/configs/realistic_transport_covtype.yaml`](experiments/configs/realistic_transport_covtype.yaml);
- a self-contained implementation under
  [`experiments/realistic_transport/`](experiments/realistic_transport/);
- the external dataset preparation entry point
  [`tools/prepare_covtype_benchmark.py`](tools/prepare_covtype_benchmark.py);
- focused Buck and pytest coverage for data preparation, preprocessing,
  environments, corrected centers, Nyström operators, CG widths, aggregation,
  statistics, provenance, and temporal leakage;
- smoke evidence and standalone artifacts under
  [`review/realistic_transport/`](review/realistic_transport/).

The package is intentionally isolated from the legacy experiment modules. The
committed-evidence verifier hashes several existing experiment sources. Editing
those files would invalidate the old locked evidence unless its source-lock
policy were changed deliberately.

## Implemented benchmark

The implementation supports three separately reported tasks:

1. `covtype_label_bandit`, a real-label Bernoulli stress test outside the
   theorem's realizability assumptions;
2. `covtype_semisynthetic_realizable`, using a development-only learner-family
   teacher;
3. `covtype_semisynthetic_misspecified`, using the same teacher plus a fixed
   sinusoidal perturbation with uniform envelope `rho`.

It implements the fixed 13-method grid, including exact current curvature,
frozen geometry, the endpoint oracle, the no-transport control, the uncorrected
center ablation, greedy and LinUCB baselines, and five Nyström/CG cells.

The main equation-to-code map is in
[`review/realistic_transport/CLAIM_TRACE.md`](review/realistic_transport/CLAIM_TRACE.md).
Important implementation properties include:

- development-only preprocessing and teacher fitting;
- deterministic hash splits and child seeds;
- common context and potential-outcome streams across methods;
- selected-reward-only observation and post-reward representation updates;
- the paper's corrected pseudo-response, center, historical radius, current
  bias, `Q_t` path certificate, and two-sided transport factors;
- a PSD Nyström construction with a trace-tail operational bound;
- fixed-operator CG with recomputed residuals and one immutable all-action
  width map per decision;
- strict grid aggregation, paired-seed statistics, Clopper-Pearson intervals,
  input-inventory hashes, and deterministic artifact generation.

## Scientific boundaries

Keep these qualifications in every review or future report:

- Task A uses the Hoeffding-safe Bernoulli proxy `sigma=0.5`, zero heuristic
  misspecification in the score, and `theorem_applicable=false`. Its coverage
  and optimism fields are stress diagnostics, not theorem validation.
- Task B is the exact realizability check. Task C uses the predeclared uniform
  envelope `rho`, never the realized perturbation.
- The CG residual and Nyström Loewner checks establish exact-arithmetic
  formulas and float64 diagnostics. They are not verified numerical
  certificates based on interval arithmetic or directed rounding.
- The required target-`D` rule gives approximately `W=75,700` on the controlled
  tasks and `W=18,925` on Task A. The scaled-tanh model is therefore nearly
  linear over the allowed parameter ball. Null differences among corrected,
  tangent, transported, and naive methods would be weak evidence about those
  mechanisms.
- No manuscript theorem, proof, experiment claim, or existing locked artifact
  was changed.

## Execution status

The official Covertype preparation command reached
`sklearn.datasets.fetch_covtype` but failed because this host could not resolve
the upstream Figshare hostname. The failure record is
[`review/realistic_transport/covtype_not_run.json`](review/realistic_transport/covtype_not_run.json).

Consequences:

- no Covertype pilot was run;
- optimizer and LinUCB tuning were not run;
- no practical Nyström/CG point was selected;
- no selection-lock commit exists;
- the 30-seed, 500-round evaluation was not run;
- `required_semantic_digest` remains `null` in the configuration;
- [`review/realistic_transport/SELECTION.json`](review/realistic_transport/SELECTION.json)
  correctly records `status: not_run`.

Digits was used only for the permitted smoke gate. The smoke ran one
development seed, 32 rounds, all three tasks, and all 13 methods:

- accepted cells: 39 of 39;
- recorded rounds: 1,248;
- deterministic failures: 0;
- wall time: 82.10 seconds;
- peak process RSS: 556,856 KiB;
- aggregate raw-input inventory SHA-256:
  `2de4bcb43bb10aec4cc9d7d4a16966696e5cb028dd954eddcb3f9a5c96705e81`.

These results are engineering evidence only. The primary result table is
[`review/realistic_transport/RESULTS.md`](review/realistic_transport/RESULTS.md).
With one smoke seed, its confidence intervals and method differences have no
publication-level inferential value.

## Validation state

The final implementation checks recorded in
[`review/realistic_transport/COMMAND_LOG.md`](review/realistic_transport/COMMAND_LOG.md)
were:

- compatible Buck2: all repository, experiment, and realistic-transport test
  targets passed;
- focused realistic-transport tests: 67 passed;
- compatible Buck2 `//paper:validate`: passed;
- `python3 tools/verify_transport_committed_evidence.py`: passed with zero
  failures;
- two artifact generations: byte-identical;
- `git diff --check`: passed.

Known host blockers:

- the default configured Buck2 binary fails while loading the Prelude because
  its API lacks `BuckRegex.any_match`; a cached compatible Buck2 revision was
  used for the successful test run;
- `make pdf` stops because `cleveref.sty` is unavailable; the committed PDF was
  not modified and still matches its sidecar;
- the non-Buck fallback environment uses NumPy 2.2.1 rather than the
  Buck-pinned 2.2.3 and produced two byte-regeneration failures in legacy
  tightness CSV tests. This fallback is not equivalent to the Buck run.

## High-risk review targets

The next reviewer should verify these points directly rather than trusting the
handoff:

1. Every theorem-facing formula and inequality orientation, especially the
   corrected radius, `Q_t`, Nyström sandwich, and regret closure.
2. Pre-reward measurability, selected-reward-only observation, and absence of
   current-reward leakage.
3. Exact row-major feature ordering and teacher parameter mapping.
4. Development-only fitting and strict separation of development, tuning,
   evaluation, and pilot seeds.
5. Whether the operational Nyström path avoids paying for dense exact
   curvature outside declared diagnostic checkpoints.
6. Whether the same CG width map determines every score, selected action, and
   played-action factor without post-selection refinement.
7. Failure preservation, source locks, selection locks, and complete-grid
   rejection in tuning and aggregation.
8. The distinction among `source_revision`, `freeze_revision`, and
   `selection_lock_revision`, including the `null` freeze field in smoke common
   provenance.
9. Whether runtime and memory accounting separates policy work from dense
   oracle diagnostics and represents worker parallelism honestly.
10. Whether every committed smoke artifact is unmistakably excluded from
    publication evidence.

The paste-ready review instructions are in
[`review/realistic_transport/GPT_PRO_REVIEW_PROMPT.md`](review/realistic_transport/GPT_PRO_REVIEW_PROMPT.md).

## Next execution steps

After the code review clears blocking issues:

1. Prepare the official Covertype artifact under an external `CCE_DATA_ROOT`.
2. Record its semantic digest in the configuration.
3. Create a new freeze commit because this changes the frozen configuration.
4. Run the Covertype pilot and use only runtime, memory, completeness, and
   numerical-stability information to decide whether the full profile is
   feasible.
5. Run tuning, commit the selection lock, then run the complete evaluation or
   the preregistered resource-fallback profile.

Do not edit the paper to match smoke, pilot, or incomplete evaluation results.
