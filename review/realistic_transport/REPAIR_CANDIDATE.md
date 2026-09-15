# Realistic transport repair candidate

## Status and scope

R means the commit containing this report. This candidate has not received
independent 03 clearance.

Pre-commit validation observations recorded on September 15, 2026 PDT:

- START and observed HEAD: `4892b59ba0838e9b39dc28abef304b01989acd14`
- Branch: `cce-experiments`
- Cached `origin/cce-experiments`: `4892b59ba0838e9b39dc28abef304b01989acd14`
- `main`: `336244ddcf0d9e574c0342669721e0a90c69028e`
- Index: empty
- Commit and push during implementation/validation: not performed
- Fetch history: one pass-12 fetch attempt failed on DNS; no later fetch ran
- Authentic data preparation and scientific execution: not performed

The prospective order remains R, independent 03 clearance, authentic
Covertype preparation, clean data-bound freeze F, pilot, tuning,
selection-only lock L, and confirmatory evaluation E. Production profiles
remain closed because the configuration contains no approved semantic digest
or data lock.

## Changed files

```text
.github/workflows/transport-committed-evidence.yml
BUCK
experiments/BUCK
experiments/REALISTIC_TRANSPORT_PROTOCOL.md
experiments/configs/realistic_transport_covtype.yaml
experiments/realistic_transport/BUCK
experiments/realistic_transport/README.md
experiments/realistic_transport/aggregate.py
experiments/realistic_transport/artifacts.py
experiments/realistic_transport/benchmark.py
experiments/realistic_transport/configuration.py
experiments/realistic_transport/data.py
experiments/realistic_transport/environment.py
experiments/realistic_transport/integrity.py
experiments/realistic_transport/io.py
experiments/realistic_transport/prepare_dataset.py
experiments/realistic_transport/provenance.py
experiments/realistic_transport/pytest_main.py
experiments/realistic_transport/run.py
experiments/realistic_transport/statistics.py
experiments/realistic_transport/study.py
experiments/realistic_transport/test_benchmark.py
experiments/realistic_transport/test_pipeline.py
experiments/realistic_transport/test_trust_boundaries.py
experiments/realistic_transport/tuning.py
experiments/requirements.txt
experiments/tests/BUCK
review/realistic_transport/REPAIR_CANDIDATE.md
tests/BUCK
third_party/BUCK
tools/BUCK
tools/prepare_covtype_benchmark.py
tools/verify_transport_committed_evidence.py
```

The pre-commit candidate contains 29 tracked modifications and four untracked
new files. The repair report is the only allowed addition under protected
review paths.

## Implemented trust boundaries

1. Artifact generation accepts only an aggregate exactly reproduced from the
   supplied complete raw grid. It rechecks authorization and lineage before it
   creates the output directory, then stages output and publishes the directory
   with Linux `renameat2(RENAME_NOREPLACE)`. A destination created during
   rendering survives and the staged tree is removed. Forged aggregate JSON
   and self-consistent sidecars cannot be laundered.
2. The positive full-shaped fixture writes a prepared artifact and all 39 raw
   cells through production serializers, runs real aggregation and artifact
   generation, and reloads the aggregate and `DATA_PROVENANCE.json`. Every
   layer remains `fixture_only=true` and `publication_evidence=false`.
3. Every exogenous identity is null only where the task permits it or is a
   lowercase 64-hex SHA-256. The stream, prepared-data, preprocessing, split,
   teacher, and misspecification identities match their redundant manifest
   fields. Pairing preserves shared B/C contexts and noise while requiring
   distinct mean, reward, and misspecification constructions.
4. One scientific-path predicate recursively covers importable and build-source
   suffixes, all repository-local Buck package/config basenames, config-directory
   entries, root and tools Buck binary selectors, bundled wheels, and both Buck
   test drivers. Exact component matching avoids lookalike names. Every
   inventory entry binds its Git-compatible mode and byte or stored-link-text
   digest. Every symlink outside `buck-out/`, `results/logs/`, and
   `results/raw/` is rejected unless its exact path is an existing START
   build/dependency link required by the Buck graph. Revision inventory,
   current inventory, status checks, and untracked/ignored checks all call the
   same predicate without following links. Tests independently cover tracked
   bytes and modes, absent-at-F untracked and staged inputs, committed post-L
   inputs, startup hooks, sourceless bytecode, root packages, and nested package
   links. Documentation requires an external bytecode cache or disabled
   bytecode before F.
5. Aggregation validates summary identity before metrics. It rederives regret,
   deterministic-failure reasons, float64 diagnostic status, theorem status,
   and the exact producer comparison tolerance from primitives. Applicable
   theorem records require finite instantaneous and cumulative RHS values even
   when the confidence premise is false. Inapplicable records require null RHS.
6. Taylor and misspecification envelope failures no longer abort a numerically
   safe trajectory. Raw records and aggregate events retain task, method, seed,
   round, exact reasons, and `float64_diagnostic_pass=false`; publication
   eligibility remains false. Numerical corruption and missing work still fail.
7. R8/R9 validation closes the off-checkpoint exact-A and exact-V paths. CG
   exact-A and exact-V scalars, aliases, omission flags, primitives, and
   all-action arrays are absent off checkpoint and complete and
   cross-consistent at checkpoints. Current-exact Cholesky methods retain both
   exact-V aliases on every round, and aggregation requires them to match the
   all-action score widths. Other non-CG methods cannot inject that map. The
   exact-zero denominator rule is unchanged.
8. Every raw, aggregate, statistics, tuning, selection, and sidecar file is
   written through a unique same-directory temporary file, fsynced, and
   installed with a non-replacing hard link. Injected files, directories, and
   dangling symlinks survive final-boundary races; predictable temporary-name
   symlinks are never followed.
9. Production `study`, `run`, `write_run`, and `write_failure` expose no
   overwrite switch. `run_profile` preflights all requested cells before data
   loading or execution. Dataset preparation rejects the CLI overwrite option
   and every public `overwrite=true` request. It preflights artifact, manifest,
   and sidecar before loading or fetching data and uses a non-replacing write
   boundary that treats files, directories, and dangling symlinks as occupied.
   A private fixture rewrite helper rejects repository paths and accepts only
   the host temporary root.
10. Full and resource-fallback study entry points require the exact ordered
   method/task grids and seed partition before loading data. The one-cell CLI
   rejects both profiles. Manifests carry the complete resolved configuration;
   aggregation compares it to the externally loaded configuration and
   recomputes its digest.
11. Exactly one BLAS/OpenMP thread is a configuration, runtime, and aggregate
    invariant. Required workflow pipelines use `set -euo pipefail`. The built
    verifier declares the numerical experiment library, so a missing NumPy
    import is a failure rather than `NOT_EXECUTED`.
12. `//:realistic_transport_resources` aggregates uniquely named PUBLIC,
    source-only filegroups from every Buck package that owns scientific inputs.
    The realistic package target declares `BUCK` explicitly and uses a
    whole-package glob, excluding `BUCK`, because `SCIENTIFIC_PREFIXES` treats
    every file below that directory as scientific. Other package targets cover
    their exact policy inputs and future importable/native sources. The root
    target explicitly covers protected `paper/BUCK` and `paper/validate.py`.
    The structural test models Buck package boundaries and fails when a package
    target, aggregate edge, whole-package glob, exact policy input, or optional
    family declaration disappears. Broad CI triggers and the three exact output
    exclusions remain unchanged.

The Git freeze cannot authenticate machine-global `/etc/buckconfig*`, user-home
`~/.buckconfig*`, or bytes reached through allowed links into the external
fbsource checkout. Those inputs require separate machine/build-environment
attestation before a production run.

The wrong-phase chained test claims only the first gate it executes. Separate
tests reach the later data, source, selection, lineage, semantic, ratio, and
artifact-generation boundaries.

## Pass-16 Buck action-input correction

Pass 16 changes these project files:

```text
BUCK
experiments/BUCK
experiments/realistic_transport/BUCK
experiments/realistic_transport/test_trust_boundaries.py
experiments/tests/BUCK
review/realistic_transport/REPAIR_CANDIDATE.md
tests/BUCK
third_party/BUCK
tools/BUCK
```

The old root-only textual oracle incorrectly assumed that Buck globs crossed
package boundaries. It is removed. The replacement oracle assigns each live
inventory path to its owning package, checks all six aggregate edges, retains
the 17 exact Buck-policy inputs and optional root families, and requires whole-
package coverage for `experiments/realistic_transport/`.

The authoritative native command
`buck2 cquery 'inputs(deps(//experiments/realistic_transport:tests))'` exits 0.
After normalization it contains 7,050 project-relative inputs. All 111 live
scientific-inventory paths are present, so the exact missing set is `[]`.
Both full preparation closure queries exit 0. Their contamination lists are
also `[]`: neither closure contains an inventory resource target, bundled-wheel
resource label, or root/local NumPy or SciPy target.

## Pass-18 hygiene correction

Pass 18 changes only this project file:

```text
review/realistic_transport/REPAIR_CANDIDATE.md
```

Before deletion, `.pytest_cache/` contained three directories and six regular
files. The pass-18 pre-clean log records every path, mode, size, and file
SHA-256. The external cleanup helper now removes only the exact repository-root
`.pytest_cache/` tree in addition to its existing named bytecode-cache roots,
and refuses a non-directory or any symlink in that tree. The external state
audit now fails if `.pytest_cache`, `__pycache__`, `.pyc`, or `.pyo` remains
anywhere in the working tree outside `.git/` and the exempt `buck-out/` tree.
No scientific test suite was rerun in pass 18; the completed pass-16 results
below are carried forward unchanged.

## R1-R13 status

`20-focused.log` contains the named adversarial and producer tests below.
`21-full-realistic.log` contains the complete package run.

| Requirement | Implementation and representative validation | Result |
| --- | --- | --- |
| R1 | Committed F data-lock authentication and canonical Covertype identity checks. `test_data_authentication_rejects_null_missing_and_modified_locks`, `test_internally_consistent_fabricated_covtype_is_not_approved`, and `test_digits_bytes_self_labeled_as_covtype_are_rejected`; logs 20 and 21. | PASS for synthetic/adversarial validation. Production stays closed pending a future approved lock. |
| R2 | Central phase, evidence-role, data-mode, horizon, method/task grid, and exact seed-partition policy. `test_profile_policy_rejects_development_or_tuning_disguised_as_full`, `test_complete_profiles_reject_partial_grid_before_data_loading`, and `test_single_cell_cli_rejects_complete_profiles`; logs 20 and 21. | PASS |
| R3 | Lowercase SHA-256 validation, redundant manifest binding, B/C sharing, and distinct construction checks. `test_aggregation_rejects_invalid_stream_component_digests_across_methods`, `test_aggregation_rejects_each_redundant_manifest_identity_mismatch`, and `test_aggregation_rejects_each_independent_mixed_stream`; logs 20 and 21. | PASS |
| R4 | Git-object inventory, dirty/staged/untracked/ignored checks, recursive importable and repository-local Buck inputs, entry modes, and fail-closed symlinks. `test_freeze_rejects_tracked_buck_input_byte_changes`, `test_freeze_rejects_tracked_cell_config_mode_change`, `test_freeze_rejects_absent_at_f_buck_inputs`, and the earlier source/symlink tests; logs 20, 21, 48, and 61. | PASS in separate disposable Git repositories. No project F was created. |
| R5 | Exact selection bytes, direct-child selection-only L, and scientific-source-identical E lineage. `test_evaluation_lineage_rejects_buck_inputs_committed_after_l` and `test_evaluation_lineage_rejects_cell_config_mode_change_after_l` now cover every Buck-input family in addition to the earlier selection tests; logs 19, 20, and 21. | PASS with fixture commits only. |
| R6 | Complete-grid and summary checks, semantic rederivation, scoped production envelope failures, and mandatory applicable theorem RHS primitives. `test_aggregation_rejects_swapped_summary_identity_before_metrics`, `test_aggregation_rederives_semantic_statuses_from_primitives`, `test_production_envelope_failures_complete_and_remain_scoped_in_aggregate`, and `test_aggregation_rejects_missing_or_inapplicable_theorem_rhs`; logs 20 and 21. | PASS |
| R7 | Runtime uses one fresh spawned process per cell; actual concurrency; `threadpool_limits(1)` with before/after BLAS/OpenMP pool verification; psutil RSS sampling plus process-lifetime `ru_maxrss`; memory includes interpreter startup/deserialization, model/optimizer/replay, operational work, and checkpoint diagnostics. `test_single_cell_study_writes_a_strict_self_describing_run`, `test_configuration_and_runtime_require_exactly_one_blas_thread`, and `test_nystrom_replay_construction_is_charged_to_algorithm_time`; logs 20, 21, and 44. | PASS in unit and synthetic-fixture validation. No performance study ran. |
| R8 | Exact-arithmetic analytic status remains separate from float64 diagnostics and no verified numerical certificate is claimed. Current-exact Cholesky records bind every operational exact-V width to the score-width map. `test_all_thirteen_methods_run_with_fixed_ties_and_separate_histories`, `test_nystrom_dense_diagnostics_run_only_at_frozen_checkpoints`, and `test_aggregation_rederives_semantic_statuses_from_primitives`; logs 19, 20, and 21. | PASS |
| R9 | Three ratio families, aliases, scalar/vector agreement, product identity, exact-zero omission, CG-checkpoint scope, and method-dependent exact-V width retention. `test_aggregation_rejects_invalid_ratio_records`, `test_aggregation_accepts_operational_exact_v_widths_on_current_exact_cholesky`, and `test_aggregation_enforces_method_dependent_exact_v_widths`; logs 19, 20, and 21. | PASS |
| R10 | Controlled B/C values average within each matched seed before bootstrap; the label task is excluded. `test_controlled_secondary_statistic_averages_tasks_within_seed_first` and `test_paired_bootstrap_is_deterministic_and_preserves_pairing`; logs 20 and 21. | PASS |
| R11 | Real full-shaped fixture aggregation/artifact generation remains fixture-only and nonpublication. The wrong-phase chained test names only its first gate, while independent tests reach later boundaries. Fifty pass-14 cases independently exercise policy membership, tracked bytes/modes, untracked/staged additions, post-L commits, and resource declarations. `test_full_shaped_fixture_remains_nonpublication_through_real_artifacts`, `test_forged_full_aggregate_cannot_create_artifacts`, and `test_full_profile_wrong_phase_is_rejected_before_later_attack_layers`; logs 19, 20, and 21. | PASS |
| R12 | CI path/resource coverage, nonempty collection, explicit pipeline failure propagation, and detached verifier target. `test_buck_resource_filegroups_cover_the_package_aware_inventory` is the package-aware structural oracle; the separate native action-input audit proves 111/111 inventory coverage; logs 19, 22, 30, 31, 35, 38, and 45 through 47. | PARTIAL because the realistic Buck test is externally build-blocked, six verifier checks fail, and GitHub Actions was not run. The action-input omission is fixed. |
| R13 | Both full transitive closures queried and checked for one declared numerical/Python family. Logs 33, 34, 40, 41, and 43. | BUILD BLOCKED. Both preparation builds stop in external `make_par` because `build_info` is unavailable. |

## Validation

Implementation and test logs are preserved under `logs/pass16-final/`.
Pass-18 hygiene and reseal logs are under `logs/pass18-final/`. Each log records
UTC time, cwd, literal argv, ordered PATH and PYTHONPATH, relevant overrides,
resolved executable and hash, version where practical, full output, and exit
code.

The 244 focused and 297 full-package tests are direct fallback validation under
CPython `3.12.14+meta` with a manually assembled declared-version
`PYTHONPATH`: NumPy `2.2.3`, SciPy `1.15.2`, scikit-learn `1.5.1`, joblib
`1.5.3`, psutil `7.2.2`, and threadpoolctl `3.5.0`. They are not Buck-built
runner results and do not establish Buck build clearance. Built preparation
runtime version/origin inspection was NOT EXECUTED because both builds are
blocked. Pass 18 did not rerun either scientific test suite.

### Carried-forward pass-16 validation

Unqualified log names in this table resolve under `logs/pass16-final/`.

| Check | Exit | Result | Log |
| --- | ---: | --- | --- |
| Required input hash | 0 | Prompt 16 matches its supplied SHA-256 | `01-prompt16-hash.log` |
| Native Git and build preflight | mixed | Pass-12 commands remain under `logs/pass12-final/`; one fetch attempt failed on DNS and no later fetch ran. The cached ref remains START. | `logs/pass12-final/01-*.log` through `14-*.log` |
| Original initial records and reconstructed START inventory | 0 | Four original files remain byte-identical; the original baseline has 182 unique paths and the reconstructed final definition has 304 blobs | `logs/pass12-final/15-start-protected-reconstruction.log`, `logs/pass12-final/16-initial-records-audit.log` |
| Package-aware resource oracle | 0 | 1 passed | `19-focused-resource.log` |
| Focused trust and producer tests | 0 | 244 passed | `20-focused.log` |
| Full realistic package | 0 | 297 passed | `21-full-realistic.log` |
| Realistic collection | 0 | 297 collected | `22-collect-realistic.log` |
| Build verifier target | 0 | Built | `30-build-verifier.log` |
| Run built verifier, no bundle skip | 1 | Bundle and artifact regeneration execute; the required `experiments/BUCK` edit is an unpinned historical-source divergence, five protected manuscript checks fail, and 4 raw-dependent checks are `NOT_EXECUTED` | `31-run-built-verifier.log` |
| Direct verifier without NumPy, no bundle skip | 1 | Missing NumPy is a hard artifact-regeneration failure; bundle regeneration still executes | `32-direct-verifier-no-numpy.log` |
| Build both preparation targets | 3 each | BUILD BLOCKED: external `make_par` cannot import `build_info` | `33-build-prepare-dataset.log`, `34-build-prepare-tool.log` |
| Buck realistic test | 3 | BUILD BLOCKED; no test result | `35-buck-test-realistic.log` |
| Buck legacy tests | 32 | Experiment target passes; root target has one historical failure | `36-buck-test-legacy.log` |
| Direct legacy tests | 1 | 114 passed, one historical failure | `37-direct-legacy.log` |
| Direct verifier, no bundle skip | 1 | Bundle and artifact regeneration execute; six checks fail and unavailable historical raw checks remain `NOT_EXECUTED` | `38-direct-verifier.log` |
| Full transitive preparation cqueries | 0 | No inventory resource, bundled-wheel resource, or local/root NumPy/SciPy labels; one fbsource NumPy/SciPy/scikit-learn/threadpoolctl/Python closure | `40-cquery-prepare-dataset.log`, `41-cquery-prepare-tool.log`, `43-closure-audit.log` |
| Verifier dependency cquery | 0 | `//experiments:lib` present | `42-cquery-verifier.log` |
| Direct fallback versions/origins | 0 | Declared versions and origins recorded | `44-fallback-runtime.log` |
| Buck inventory resource build | 0 | The uniquely named package-local resource groups aggregate successfully | `45-build-resource-inventory.log` |
| Native test action-input query and audit | 0 each | 7,050 normalized project inputs; 111 inventory entries; missing set `[]` | `46-cquery-action-inputs.log`, `47-action-input-audit.log` |
| Initial resource build attempt | 3 | Duplicate package target output names collided; preserved and superseded after target names became unique | `45-build-resource-inventory-attempt1.log` |
| Current scientific inventory | 0 | 111 entries after cache cleanup | `48-source-inventory.log` |
| Declared wheel checksums | 0 | NumPy and SciPy wheel hashes verify | `48-wheel-sha256sums.log` |
| Generated source-cache cleanup | 0 | No scientific cache survives final cleanup | `49-clean-generated-caches.log`, `59-final-cache-clean.log` |
| Pyfmt, compileall, workflow parse, diff check | 0 each | PASS | `50-*.log` through `53-*.log` |
| Expanded public added-line scrub | 0 | 9,245 added/untracked text lines scanned, including absolute user paths and private/internal patterns; no findings | `54-public-scrub.log` |
| Sidecar scan | 0 | Protected sidecars and submission checksum entries verify | `55-sidecars.log` |
| Documentation assertions | 0 | Timeless claims, pass-16 graph/failure wording, and no-skip verifier invocations verified | `56-documentation-claims.log` |
| Protected path/blob/mode audit | 0 | 304/304 baseline files exact; two frozen PDFs; no unexpected protected file | `60-protected.log` |
| HEAD/index/ref and untracked/ignored audit | 0 | Dated pre-commit state matches START, index empty, no stray fixture/evidence/importable cache | `61-state.log` |
| Artifact checksum verification | 0 | `SHA256SUMS` verifies from the artifact root | `63-checksums.log` |

### Pass-18 hygiene and reseal validation

| Check | Exit | Result | Log |
| --- | ---: | --- | --- |
| Prompt hash | 0 | Prompt 18 matches its supplied SHA-256 | `logs/pass18-final/01-prompt18-hash.log` |
| Pre-clean cache inventory | 0 | Three directories and six files recorded with modes, sizes, and hashes | `logs/pass18-final/02-pytest-cache-before.log` |
| Explicit cache cleanup | 0 | The six recorded `.pytest_cache` files were removed | `logs/pass18-final/03-explicit-cache-cleanup.log` |
| Final cache cleanup | 0 | No generated cache remained for removal | `logs/pass18-final/04-final-cache-cleanup.log` |
| Final scientific inventory | 0 | 111 entries | `logs/pass18-final/48-source-inventory.log` |
| Diff check and public scrub | 0 each | Clean diff; 9,283 lines scanned with no public-scrub findings | `logs/pass18-final/53-git-diff-check.log`, `logs/pass18-final/54-public-scrub.log` |
| Documentation assertions | 0 | Exact log paths and fetch history verified | `logs/pass18-final/56-documentation-claims.log` |
| Protected audit | 0 | 304/304 protected files and two frozen PDFs exact | `logs/pass18-final/60-protected.log` |
| State and cache audit | 0 | Refs/index/untracked state exact; cache-artifact set empty | `logs/pass18-final/61-state.log` |
| Final snapshot and checksums | 0 each | Final paths and hashes recorded; checksum manifest verifies | `logs/pass18-final/62-final-snapshot.log`, `logs/pass18-final/63-checksums.log` |

The built and direct fallback verifier runs each record 75 PASS,
39 PASS_RECOMPUTED, 2 STRUCTURAL_PASS, 1 KNOWN_DIVERGENCE, 4 NOT_EXECUTED,
6 FAIL, and 1 semantically identical but byte-different PDF rebuild. The
no-NumPy run records 74 PASS, 18 PASS_RECOMPUTED, 2 STRUCTURAL_PASS,
1 KNOWN_DIVERGENCE, 4 NOT_EXECUTED, 7 FAIL, and the same PDF rebuild result.
All three runs invoke review-bundle regeneration; none uses `--skip-bundle`.

Five verifier failures require exact prose absent from
protected `paper/transport_experiment.tex`: dense diagnostic oracle, no uniform
curvature advantage, empirical vacuity, no generic network-width claim, and
descriptive regret direction. This repair does not modify that file or weaken
the checks. The sixth failure is the verifier correctly rejecting the required
uncommitted `experiments/BUCK` resource-target edit as an unpinned divergence
from the historical selection snapshot. Historical raw tuning/evaluation
inputs are unavailable, so their checks remain explicitly `NOT_EXECUTED`.

The original `initial-records/protected-baseline.txt` is preserved unchanged.
Its 182 unique paths cover only 152 of the final 304-path protected definition.
`initial-records/START-protected-inventory-reconstruction.txt` is a separate
304-blob reconstruction generated after editing directly from immutable START;
it is not described as a pre-edit observation. The preserved baseline test log
contains exit 3, `NO TESTS RAN`, and the Buck/Prelude `root_values` error. It
does not contain a literal argv, so this report does not reconstruct one.

## Protected inventory

During an earlier validation attempt, two protected statistical files were
overwritten and then restored byte-for-byte from START; an ignored generated
`paper/main.log` was removed. The final audit compares protected paths, Git
blobs, modes, unexpected additions, and both frozen PDFs against START. The
repair report is the sole allowed new protected-path file.

A1-A8: NOT MAPPED - source report unavailable

NO REAL COVTYPE PILOT/TUNING/EVALUATION WAS RUN

Covertype prepared: NO
Pilot run: NO
Tuning run: NO
Fallback run: NO
Evaluation run: NO
Project F created: NO
Project L created: NO
Independent 03 clearance: NOT CLAIMED
