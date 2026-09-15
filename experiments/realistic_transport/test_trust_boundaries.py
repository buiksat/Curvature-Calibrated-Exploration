from __future__ import annotations

import copy
import hashlib
import inspect
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import experiments.realistic_transport.aggregate as aggregate_module
import experiments.realistic_transport.artifacts as artifacts_module
import experiments.realistic_transport.benchmark as benchmark_module
import experiments.realistic_transport.data as data_module
import experiments.realistic_transport.provenance as provenance_module
import numpy as np
import pytest
from experiments.realistic_transport.aggregate import (
    _semantic_status,
    _validate_manifest_identity,
    _validate_paired_streams,
    _validate_round_semantics,
    aggregate_profile,
    AggregateError,
    publication_eligibility,
    write_statistics_csv,
)
from experiments.realistic_transport.artifacts import generate_artifacts
from experiments.realistic_transport.benchmark import (
    BenchmarkSettings,
    derive_float64_diagnostic_status,
    derive_theorem_bound_status,
    OptimizerSpec,
    run_policy_trajectory,
    THEOREM_BOUND_COMPARISON_RULE,
    THEOREM_METHODS,
)
from experiments.realistic_transport.configuration import (
    canonical_json,
    config_digest,
    EXPECTED_METHODS,
    EXPECTED_TASKS,
    load_config,
    method_spec,
    profile_policy,
    ProfilePolicy,
    RealisticConfigError,
    scientific_config_digest,
    validate_config,
    validate_profile_request,
)
from experiments.realistic_transport.data import (
    load_prepared_dataset,
    prepare_covtype_artifact,
    prepare_dataset,
    prepare_digits_artifact,
    prepare_loaded_dataset,
    sha256_file,
)
from experiments.realistic_transport.environment import (
    CONTROLLED_MISSPECIFIED_TASK,
    PotentialOutcomeStream,
    REALIZABLE_TASK,
)
from experiments.realistic_transport.features import FeatureMapSpec
from experiments.realistic_transport.integrity import (
    authenticate_prepared_data,
    DATA_LOCK_SCHEMA,
    IntegrityError,
    selection_payload_sha256,
    SELECTION_SCHEMA,
    source_inventory_at_revision,
    validate_selection_policy,
    verify_clean_freeze,
    verify_evaluation_lineage,
    verify_selection_lock,
)
from experiments.realistic_transport.io import (
    _rewrite_run_fixture,
    run_directory,
    write_failure,
    write_run,
)
from experiments.realistic_transport.model import scaled_tanh_mean
from experiments.realistic_transport.prepare_dataset import main as prepare_dataset_main
from experiments.realistic_transport.provenance import (
    ALLOWED_SCIENTIFIC_SYMLINKS,
    atomic_write_text,
    enforced_numerical_threads,
    input_set_sha256,
    is_scientific_path,
    runtime_metadata,
    SCIENTIFIC_PREFIXES,
    sha256_bytes,
    source_inventory,
    write_json,
)
from experiments.realistic_transport.run import main as run_main
from experiments.realistic_transport.statistics import (
    controlled_task_average_bootstrap,
    paired_seed_bootstrap,
)
from experiments.realistic_transport.study import (
    main as study_main,
    run_profile,
    StudyError,
)
from experiments.realistic_transport.tuning import (
    lock_selection,
    run_tuning_suite,
    TuningError,
)


CONFIG = Path("experiments/configs/realistic_transport_covtype.yaml")


class _EnvelopeTestEnvironment:
    def __init__(self, task_name: str, *, current_misspecification: float) -> None:
        self.task_name = task_name
        self.feature_map = FeatureMapSpec(context_dimension=16, action_count=2)
        self.theta_star = np.linspace(-1.0, 1.0, self.feature_map.feature_dimension)
        self.theta_star /= np.linalg.norm(self.theta_star)
        self.width = 100.0
        self.noise_proxy = 0.25
        self.theorem_applicable = True
        self.historical_misspecification_envelope = (
            0.025 if task_name == CONTROLLED_MISSPECIFIED_TASK else 0.0
        )
        self.current_misspecification_envelope = current_misspecification

    @property
    def context_dimension(self) -> int:
        return self.feature_map.context_dimension

    @property
    def action_count(self) -> int:
        return self.feature_map.action_count

    @property
    def feature_dimension(self) -> int:
        return self.feature_map.feature_dimension

    def feature_matrix(self, context: np.ndarray) -> np.ndarray:
        return self.feature_map.all_action_features(context)


def _envelope_test_trajectory(
    *,
    task: str,
    current_misspecification: float,
) -> tuple[_EnvelopeTestEnvironment, PotentialOutcomeStream]:
    environment = _EnvelopeTestEnvironment(
        task, current_misspecification=current_misspecification
    )
    generator = np.random.default_rng(8102)
    contexts = generator.normal(size=(3, environment.context_dimension))
    contexts /= np.maximum(1.0, np.linalg.norm(contexts, axis=1))[:, None]
    labels = np.asarray([0, 1, 0], dtype=np.int64)
    means = np.stack(
        [
            scaled_tanh_mean(
                environment.theta_star,
                environment.feature_matrix(context),
                environment.width,
            )
            for context in contexts
        ]
    )
    if task == CONTROLLED_MISSPECIFIED_TASK:
        phases = np.arange(environment.action_count, dtype=np.float64)
        means += np.stack(
            [0.025 * np.sin(phases + float(np.sum(context))) for context in contexts]
        )
    stream = PotentialOutcomeStream(
        task_name=task,
        seed=100,
        phase="evaluation",
        row_indices=np.arange(3, dtype=np.int64),
        contexts=contexts,
        _labels=labels,
        means=means,
        noises=np.zeros_like(means),
        rewards=means.copy(),
        _feature_map=environment.feature_map,
    )
    return environment, stream


def _run_git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _fixture_repository(path: Path) -> tuple[Path, str]:
    repo = path / "repo"
    (repo / ".buck/fbsource_cell").mkdir(parents=True)
    (repo / "experiments/realistic_transport").mkdir(parents=True)
    (repo / "experiments/configs").mkdir(parents=True)
    (repo / "experiments/tests").mkdir(parents=True)
    (repo / "nested/build").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "third_party/wheels").mkdir(parents=True)
    (repo / ".buck/fbsource_cell/.buckconfig").write_text(
        "[repositories]\nroot = ../..\n", encoding="utf-8"
    )
    (repo / "PACKAGE").write_text("# fixture package policy\n", encoding="utf-8")
    (repo / "experiments/__init__.py").write_text(
        '"""Fixture experiments package."""\n', encoding="utf-8"
    )
    (repo / "experiments/realistic_transport/core.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    (repo / "experiments/configs/realistic_transport_covtype.yaml").write_text(
        "{}\n", encoding="utf-8"
    )
    (repo / "experiments/requirements.txt").write_text(
        "numpy==2.2.3\n", encoding="utf-8"
    )
    (repo / "nested/build/BUCK").write_text(
        "# fixture recursive build file\n", encoding="utf-8"
    )
    (
        repo / "third_party/wheels/numpy-2.2.3-cp312-cp312-manylinux_x86_64.whl"
    ).write_bytes(b"fixture numpy wheel\n")
    for driver in (
        repo / "experiments/tests/run_buck_pytest.sh",
        repo / "tests/run_buck_pytest.sh",
    ):
        driver.write_text('#!/bin/sh\nexec "$@"\n', encoding="utf-8")
        driver.chmod(0o755)
    (repo / ".buck2").write_text("pinned build tool\n", encoding="utf-8")
    (repo / ".gitignore").write_text(
        "experiments/realistic_transport/ignored.py\n"
        "notes/*.py\n"
        "notes/ignored_bytecode.pyo\n"
        "ignoredshadow\n",
        encoding="utf-8",
    )
    _run_git(repo, "init", "-q", "-b", "main")
    _run_git(repo, "config", "commit.gpgsign", "false")
    _run_git(repo, "config", "user.email", "fixture@example.com")
    _run_git(repo, "config", "user.name", "Fixture")
    _run_git(repo, "config", "core.excludesFile", "/dev/null")
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-q", "-m", "freeze")
    return repo, _run_git(repo, "rev-parse", "HEAD")


_FIXTURE_NUMPY_WHEEL = "third_party/wheels/numpy-2.2.3-cp312-cp312-manylinux_x86_64.whl"
_TRACKED_BUCK_INPUTS = (
    ".buck/fbsource_cell/.buckconfig",
    _FIXTURE_NUMPY_WHEEL,
    "experiments/tests/run_buck_pytest.sh",
    "nested/build/BUCK",
    "tests/run_buck_pytest.sh",
)
_ABSENT_BUCK_INPUTS = (
    ".buckconfig.local",
    ".buckconfig.d/override.bcfg",
    ".buck/fbsource_cell/.buckconfig.local",
    ".buck/fbsource_cell/.buckconfig.d/override.bcfg",
    ".buckroot",
    ".buck/fbsource_cell/.buckroot",
    "nested/PACKAGE",
    "nested/BUCK_TREE",
    "fresh/deep/BUCK",
    ".buck2-previous",
    ".buck2-versions/stable",
    "tools/buck2-versions/stable",
)


def _base_stream_identity(
    task: str, *, prepared_data: str = "9" * 64
) -> dict[str, str | None]:
    misspecification = "c" * 64 if task == EXPECTED_TASKS[2] else None
    return {
        "context_order": "1" * 64,
        "contexts": "2" * 64,
        "labels": "3" * 64,
        "potential_means": ("4" if task == EXPECTED_TASKS[1] else "5") * 64,
        "noise": "6" * 64,
        "potential_rewards": ("7" if task == EXPECTED_TASKS[1] else "8") * 64,
        "prepared_data": prepared_data,
        "teacher": "a" * 64,
        "misspecification": misspecification,
        "preprocessing": "d" * 64,
        "split": "e" * 64,
        "stream": "f" * 64,
    }


def _manifest_with_stream_identity(
    task: str, identity: dict[str, str | None] | None = None
) -> dict[str, Any]:
    selected = dict(identity or _base_stream_identity(task))
    return {
        "exogenous_stream_identity": selected,
        "prepared_data": {"semantic_digest": selected["prepared_data"]},
        "preprocessing_digest": selected["preprocessing"],
        "split": {"digest": selected["split"]},
        "teacher_digest": selected["teacher"],
        "misspecification_function_digest": selected["misspecification"],
        "stream_digest": selected["stream"],
    }


def _fixture_runtime(config: dict[str, Any]) -> dict[str, Any]:
    pool = {
        "user_api": "blas",
        "internal_api": "openblas",
        "num_threads": 1,
        "prefix": "libopenblas",
        "version": "fixture",
        "filepath": "libopenblas-fixture.so",
    }
    memory = {
        "metric": "fresh_process_peak_resident_set_size_bytes",
        "backend": "resource.getrusage",
        "includes": [
            "interpreter_startup",
            "deserialized_dataset_and_environment",
            "model_optimizer_and_replay_state",
            "operational_computation",
            "checkpoint_diagnostics",
        ],
        "includes_startup_and_deserialization_peak": True,
        "isolation": "one_fresh_spawned_process_per_cell",
        "peak_rss_bytes": 1_048_576,
    }
    execution = config["execution"]
    assert isinstance(execution, dict)
    return {
        "python": {"version": "fixture"},
        "packages": {"numpy": "fixture", "scipy": "fixture"},
        "module_origins": {"numpy": {"path": "fixture/numpy.py", "sha256": "1" * 64}},
        "platform": {"system": "fixture"},
        "execution": {
            "workers": 1,
            "requested_workers": int(config.get("workers", execution["workers"])),
            "actual_concurrent_workers": 1,
            "execution_model": (
                "sequential_parent_with_fresh_spawned_process_per_cell"
            ),
            "blas_threads_per_worker": int(execution["blas_threads_per_worker"]),
            "worker_pid": 1234,
            "thread_control": {
                "requested_limit": int(execution["blas_threads_per_worker"]),
                "verified": True,
                "active_pools_before": [dict(pool)],
                "active_pools_after": [dict(pool)],
            },
            "memory_measurement": memory,
        },
    }


def _fixture_round(
    *, task: str, method: str, seed: int, round_number: int, rounds: int
) -> dict[str, object]:
    checkpoint = round_number in {1, rounds}
    spec = method_spec(method)
    theorem_applicable = task != EXPECTED_TASKS[0] and method in THEOREM_METHODS
    controlled_method = task != EXPECTED_TASKS[0] and method != "linucb_fixed_features"
    solver_converged: bool | None = None if spec.solver == "none" else True
    taylor_valid: bool | None = True if controlled_method else None
    misspecification_valid: bool | None = True if controlled_method else None
    reasons, diagnostic_pass = derive_float64_diagnostic_status(
        solver_all_actions_converged=solver_converged,
        current_taylor_envelope_valid=taylor_valid,
        current_misspecification_envelope_valid=misspecification_valid,
    )
    instantaneous_regret = 0.1
    cumulative_regret = instantaneous_regret * round_number
    tolerance = 4096.0 * np.finfo(np.float64).eps * 50
    instantaneous_rhs = 1.0 if theorem_applicable else None
    cumulative_rhs = float(round_number) if theorem_applicable else None
    coverage = True
    instantaneous_status = derive_theorem_bound_status(
        theorem_applicable=theorem_applicable,
        confidence_event=coverage,
        regret=instantaneous_regret,
        rhs=instantaneous_rhs,
        comparison_tolerance=tolerance,
    )
    cumulative_status = derive_theorem_bound_status(
        theorem_applicable=theorem_applicable,
        confidence_event=coverage,
        regret=cumulative_regret,
        rhs=cumulative_rhs,
        comparison_tolerance=tolerance,
    )

    current_widths: list[float] | None = None
    if spec.metric == "current_exact" and spec.solver == "cholesky":
        current_widths = [2.0, 4.0]
    elif checkpoint and spec.solver == "cg":
        current_widths = [2.0, 4.0]
    if spec.solver == "cg":
        upper_widths = [1.2, 2.4]
        solver_width_upper: float | None = upper_widths[0]
        solver_width_lower: float | None = 1.0
        solver_alpha: float | None = 1.2
        if checkpoint:
            exact_widths = [1.0, 2.0]
            solver_ratio: float | None = 1.2
            solver_omitted: bool | None = False
            solver_ratio_all: list[float | None] | None = [1.2, 1.2]
            solver_omitted_all: list[bool] | None = [False, False]
            operator_ratio: float | None = 0.5
            operator_omitted: bool | None = False
            operator_ratio_all: list[float | None] | None = [0.5, 0.5]
            operator_omitted_all: list[bool] | None = [False, False]
            total_ratio: float | None = 0.6
            total_omitted: bool | None = False
            total_ratio_all: list[float | None] | None = [0.6, 0.6]
            total_omitted_all: list[bool] | None = [False, False]
            solver_exact_width: float | None = 1.0
        else:
            exact_widths = None
            solver_ratio = None
            solver_omitted = None
            solver_ratio_all = None
            solver_omitted_all = None
            operator_ratio = None
            operator_omitted = None
            operator_ratio_all = None
            operator_omitted_all = None
            total_ratio = None
            total_omitted = None
            total_ratio_all = None
            total_omitted_all = None
            solver_exact_width = None
    elif spec.solver == "cholesky":
        upper_widths = None
        exact_widths = None
        solver_width_upper = 1.0
        solver_width_lower = 1.0
        solver_alpha = 1.0
        solver_exact_width = 1.0
        solver_ratio = 1.0
        solver_omitted = False
        solver_ratio_all = None
        solver_omitted_all = None
        operator_ratio = None
        operator_omitted = None
        total_ratio = None
        total_omitted = None
        operator_ratio_all = None
        operator_omitted_all = None
        total_ratio_all = None
        total_omitted_all = None
    else:
        upper_widths = None
        exact_widths = None
        solver_width_upper = None
        solver_width_lower = None
        solver_alpha = None
        solver_exact_width = None
        solver_ratio = None
        solver_omitted = None
        solver_ratio_all = None
        solver_omitted_all = None
        operator_ratio = None
        operator_omitted = None
        operator_ratio_all = None
        operator_omitted_all = None
        total_ratio = None
        total_omitted = None
        total_ratio_all = None
        total_omitted_all = None

    is_nystrom = method.startswith("transport_nystrom_")
    confidence_role = (
        "theorem_reference_event" if theorem_applicable else "fixture_diagnostic"
    )
    if spec.metric == "current_exact" and spec.solver == "cholesky":
        score_widths = [2.0, 4.0]
    elif spec.solver == "cg":
        score_widths = [1.2, 2.4]
    else:
        score_widths = [1.0, 1.0]
    return {
        "round": round_number,
        "seed": seed,
        "task": task,
        "method": method,
        "selected_action": 0,
        "score_widths": score_widths,
        "true_means": [0.1, 0.2],
        "selected_mean": 0.1,
        "optimal_mean": 0.2,
        "instantaneous_pseudo_regret": instantaneous_regret,
        "cumulative_pseudo_regret": cumulative_regret,
        "action_correct": True if task == EXPECTED_TASKS[0] else None,
        "reference_confidence_all_actions": coverage,
        "prefix_simultaneous_reference_confidence": coverage,
        "method_optimism_all_actions": True,
        "confidence_role": confidence_role,
        "theorem_applicable": theorem_applicable,
        "method_certified_under_exact_arithmetic": theorem_applicable,
        "analytic_certificate_valid_in_exact_arithmetic": theorem_applicable,
        "deterministic_failure": bool(reasons),
        "deterministic_failure_reasons": reasons,
        "float64_diagnostic_pass": diagnostic_pass,
        "verified_numerical_certificate": False,
        "solver_all_actions_converged": solver_converged,
        "current_taylor_envelope_valid": taylor_valid,
        "current_misspecification_envelope_valid": misspecification_valid,
        "corrected_centers": (
            [0.1, 0.2] if method != "linucb_fixed_features" else None
        ),
        "instantaneous_theorem_rhs": instantaneous_rhs,
        "instantaneous_theorem_bound_status": instantaneous_status,
        "sharp_theorem_rhs": cumulative_rhs,
        "cumulative_theorem_bound_status": cumulative_status,
        "theorem_bound_comparison_rule": THEOREM_BOUND_COMPARISON_RULE,
        "theorem_bound_comparison_tolerance": tolerance,
        "cumulative_trivial_regret_bound": float(round_number),
        "algorithm_seconds": 0.01,
        "operator_construction_seconds": 0.002,
        "replay_gradient_construction_seconds": 0.001,
        "transport_certificate_seconds": 0.001,
        "action_scoring_seconds": 0.001,
        "representation_update_seconds": 0.003,
        "diagnostic_seconds": 0.002 if checkpoint else 0.0,
        "end_to_end_round_seconds": 0.011,
        "operator_storage_bytes": 128,
        "solver_iterations_all_actions": 2 if spec.solver == "cg" else 0,
        "solver_algorithm_matvecs_all_actions": 2 if spec.solver == "cg" else 0,
        "solver_audit_matvecs_all_actions": 1 if spec.solver == "cg" else 0,
        "solver_seconds_all_actions": 0.001 if spec.solver != "none" else 0.0,
        "D_Q": 1.0 if method != "linucb_fixed_features" else None,
        "d_Th": 1.0 if checkpoint and method != "linucb_fixed_features" else None,
        "D_Q_minus_d_Th": (
            0.0 if checkpoint and method != "linucb_fixed_features" else None
        ),
        "nystrom_trace_tail": 1.0 if checkpoint and is_nystrom else None,
        "nystrom_operator_tail": 1.0 if checkpoint and is_nystrom else None,
        "nystrom_oracle_generalized_kappa_minus": (
            1.0 if checkpoint and is_nystrom else None
        ),
        "kappa_minus": 1.0 if method != "linucb_fixed_features" else None,
        "solver_width_upper": solver_width_upper,
        "solver_width_lower": solver_width_lower,
        "solver_alpha": solver_alpha,
        "solver_exact_width": solver_exact_width,
        "solver_upper_over_exact": solver_ratio,
        "solver_upper_over_exact_A": solver_ratio,
        "solver_upper_over_exact_A_denominator_omitted": solver_omitted,
        "exact_A_width_over_exact_V_width": operator_ratio,
        "exact_A_width_over_exact_V_width_denominator_omitted": operator_omitted,
        "operational_upper_width_over_exact_V_width": total_ratio,
        "operational_upper_width_over_exact_V_width_denominator_omitted": (
            total_omitted
        ),
        "solver_upper_widths_all_actions": upper_widths,
        "solver_exact_widths_all_actions": exact_widths,
        "solver_upper_over_exact_all_actions": solver_ratio_all,
        "solver_upper_over_exact_A_all_actions": solver_ratio_all,
        "solver_upper_over_exact_A_denominator_omitted_all_actions": (
            solver_omitted_all
        ),
        "exact_A_width_over_exact_V_width_all_actions": operator_ratio_all,
        "exact_A_width_over_exact_V_width_denominator_omitted_all_actions": (
            operator_omitted_all
        ),
        "operational_upper_width_over_exact_V_width_all_actions": total_ratio_all,
        "operational_upper_width_over_exact_V_width_denominator_omitted_all_actions": (
            total_omitted_all
        ),
        "current_exact_widths": current_widths,
        "current_widths": current_widths,
        "bonus_below_true_action_gap": False,
        "selected_confidence_bonus": 0.5,
        "reward_range": 1.0,
        "historical_misspecification_envelope": (0.0 if controlled_method else None),
        "current_misspecification_envelope": 0.0 if controlled_method else None,
        "diagnostic_checkpoint": checkpoint,
    }


def _install_full_shaped_fixture_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], ProfilePolicy]:
    config = load_config(CONFIG, "full")
    config["dataset_mode"] = "digits_smoke"
    config["rounds"] = 3
    config["seeds"] = [100]
    policy = ProfilePolicy(
        name="full",
        dataset_mode="digits_smoke",
        phase="evaluation",
        evidence_role="publication_candidate",
        seeds=(100,),
        rounds=3,
        requires_data_lock=False,
        requires_selection_lock=False,
        publication_candidate=True,
    )

    def load_fixture_config(_path: object, _profile: str) -> dict[str, Any]:
        return copy.deepcopy(config)

    def fixture_policy(_config: object, _profile: str) -> ProfilePolicy:
        return policy

    monkeypatch.setattr(aggregate_module, "load_config", load_fixture_config)
    monkeypatch.setattr(aggregate_module, "profile_policy", fixture_policy)
    monkeypatch.setattr(artifacts_module, "load_config", load_fixture_config)
    monkeypatch.setattr(artifacts_module, "profile_policy", fixture_policy)
    return config, policy


def _write_full_shaped_fixture_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[str, Any], ProfilePolicy]:
    config, policy = _install_full_shaped_fixture_policy(monkeypatch)
    raw_root = tmp_path / "raw"
    prepared_path = tmp_path / "prepared" / "fixture.npz"
    prepared_manifest = prepare_loaded_dataset(
        np.arange(24, dtype=np.float64).reshape(12, 2),
        np.arange(12, dtype=np.int64) % 2,
        dataset_name="sklearn_covtype",
        destination=prepared_path,
        loader_metadata={"callable": "synthetic_fixture"},
        smoke_only=True,
        fixture_only=True,
    )
    prepared_metadata = {
        "dataset_name": prepared_manifest["dataset_name"],
        "semantic_digest": prepared_manifest["array_content_sha256"],
        "artifact_sha256": prepared_manifest["artifact_sha256"],
        "manifest_sha256": sha256_file(prepared_path.with_suffix(".npz.manifest.json")),
        "smoke_only": prepared_manifest["smoke_only"],
        "fixture_only": prepared_manifest["fixture_only"],
        "publication_evidence": prepared_manifest["publication_evidence"],
        "row_count": prepared_manifest["row_count"],
        "source_feature_dimension": prepared_manifest["source_feature_dimension"],
        "class_count": prepared_manifest["class_count"],
        "original_classes": prepared_manifest["original_classes"],
        "loader": prepared_manifest["loader"],
        "runtime_provenance": prepared_manifest["runtime_provenance"],
        "source_cache_files": prepared_manifest["source_cache_files"],
    }
    memory = _fixture_runtime(config)["execution"]["memory_measurement"]
    for task in EXPECTED_TASKS:
        stream_identity = _base_stream_identity(
            task, prepared_data=prepared_metadata["semantic_digest"]
        )
        for method in EXPECTED_METHODS:
            manifest = {
                "schema_version": 1,
                "protocol_version": config["protocol_version"],
                "profile": "full",
                "phase": "evaluation",
                "dataset_mode": "digits_smoke",
                "evidence_role": "publication_candidate",
                "publication_evidence": False,
                "seed_set_identity": policy.seed_set_identity,
                "task": task,
                "method": method,
                "base_seed": 100,
                "rounds": 3,
                "config_digest": config_digest(config),
                "scientific_config_digest": scientific_config_digest(config),
                "resolved_config": copy.deepcopy(config),
                "prepared_data": prepared_metadata,
                "data_authentication": {
                    "status": "fixture_only_not_approved",
                    "freeze_revision": None,
                    "data_lock_path": None,
                    "data_lock_sha256": None,
                    "manifest_sha256": prepared_metadata["manifest_sha256"],
                },
                "split": {
                    "digest": stream_identity["split"],
                    "counts": {"evaluation": 100},
                },
                "preprocessing_digest": stream_identity["preprocessing"],
                "preprocessing_artifact": {"fixture": True},
                "teacher_digest": stream_identity["teacher"],
                "misspecification_function_digest": stream_identity["misspecification"],
                "stream_digest": stream_identity["stream"],
                "selection_artifact_sha256": None,
                "freeze_revision": None,
                "selection_lock_revision": None,
                "evaluation_state_revision": "4" * 40,
                "source_inventory_sha256": input_set_sha256([]),
                "source_inventory": [],
                "source_branch": "fixture",
                "source_revision": "4" * 40,
                "source_dirty": True,
                "runtime": _fixture_runtime(config),
                "exogenous_stream_identity": stream_identity,
                "status": "completed",
            }
            summary = {
                "status": "completed",
                "profile": "full",
                "phase": "evaluation",
                "publication_evidence": False,
                "task": task,
                "method": method,
                "seed": 100,
                "rounds": 3,
                "data_loading_seconds": 0.01,
                "preprocessing_seconds": 0.01,
                "teacher_environment_seconds": 0.01,
                "policy_peak_rss_bytes": 1_048_576,
                "policy_memory_measurement": copy.deepcopy(memory),
            }
            records = [
                _fixture_round(
                    task=task,
                    method=method,
                    seed=100,
                    round_number=round_number,
                    rounds=3,
                )
                for round_number in range(1, 4)
            ]
            write_run(
                run_directory(
                    raw_root,
                    phase="full",
                    task=task,
                    method=method,
                    seed=100,
                ),
                manifest=manifest,
                rounds=records,
                summary=summary,
            )
    return raw_root, config, policy


def test_profile_policy_rejects_development_or_tuning_disguised_as_full() -> None:
    config = load_config(CONFIG, "full")
    for phase in ("development", "tuning"):
        with pytest.raises(ValueError, match="requires phase 'evaluation'"):
            validate_profile_request(config, "full", phase=phase)
    with pytest.raises(ValueError, match="does not permit seeds"):
        validate_profile_request(config, "full", seeds=(200,))
    policy = profile_policy(config, "full")
    assert policy.seeds == tuple(range(100, 130))
    assert policy.rounds == 500
    assert policy.evidence_role == "publication_candidate"


def test_configuration_and_runtime_require_exactly_one_blas_thread(
    tmp_path: Path,
) -> None:
    document = json.loads(CONFIG.read_text(encoding="utf-8"))
    document["base"]["execution"]["blas_threads_per_worker"] = 2
    with pytest.raises(RealisticConfigError, match="blas_threads_per_worker must be 1"):
        validate_config(document)

    invalid_config = tmp_path / "invalid-config.json"
    invalid_config.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(RealisticConfigError, match="blas_threads_per_worker must be 1"):
        aggregate_profile(
            config_path=invalid_config,
            profile="smoke",
            raw_root=tmp_path / "raw",
            output_path=tmp_path / "aggregate.json",
        )
    with pytest.raises(ValueError, match="exactly one"):
        with enforced_numerical_threads(2):
            pytest.fail("invalid thread limit entered the numerical scope")
    with pytest.raises(ValueError, match="exactly one"):
        runtime_metadata(workers=1, blas_threads=2)


@pytest.mark.parametrize("profile", ("full", "resource_fallback"))
@pytest.mark.parametrize("subset", ("methods", "tasks", "seeds"))
def test_complete_profiles_reject_partial_grid_before_data_loading(
    tmp_path: Path, profile: str, subset: str
) -> None:
    policy = profile_policy(load_config(CONFIG, profile), profile)
    arguments: dict[str, object] = {
        "methods": EXPECTED_METHODS,
        "tasks": EXPECTED_TASKS,
        "seeds": policy.seeds,
    }
    if subset == "methods":
        arguments[subset] = EXPECTED_METHODS[:-1]
        message = "complete ordered method grid"
    elif subset == "tasks":
        arguments[subset] = EXPECTED_TASKS[:-1]
        message = "complete ordered task grid"
    else:
        arguments[subset] = policy.seeds[:-1]
        message = "exact seed partition"
    with pytest.raises(StudyError, match=message):
        run_profile(
            config_path=CONFIG,
            profile=profile,
            prepared_artifact=tmp_path / "must-not-load.npz",
            output_root=tmp_path / "raw",
            selection_path=tmp_path / "must-not-load-selection.json",
            **arguments,
        )
    assert not (tmp_path / "raw").exists()


@pytest.mark.parametrize(
    ("profile", "seed"),
    (("full", 200), ("resource_fallback", 100)),
)
def test_complete_profiles_reject_out_of_partition_seed_before_data_loading(
    tmp_path: Path, profile: str, seed: int
) -> None:
    with pytest.raises(StudyError, match="does not permit seeds"):
        run_profile(
            config_path=CONFIG,
            profile=profile,
            prepared_artifact=tmp_path / "must-not-load.npz",
            output_root=tmp_path / "raw",
            selection_path=tmp_path / "must-not-load-selection.json",
            methods=EXPECTED_METHODS,
            tasks=EXPECTED_TASKS,
            seeds=(seed,),
        )
    assert not (tmp_path / "raw").exists()


@pytest.mark.parametrize("profile", ("full", "resource_fallback"))
def test_single_cell_cli_rejects_complete_profiles(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    profile: str,
) -> None:
    with pytest.raises(SystemExit) as raised:
        run_main(
            [
                "--profile",
                profile,
                "--prepared-artifact",
                str(tmp_path / "must-not-load.npz"),
                "--task",
                EXPECTED_TASKS[0],
                "--method",
                EXPECTED_METHODS[0],
                "--seed",
                str(profile_policy(load_config(CONFIG, profile), profile).seeds[0]),
            ]
        )
    assert raised.value.code == 2
    assert "requires the complete study entry point" in capsys.readouterr().err


@pytest.mark.parametrize("profile", ("full", "resource_fallback"))
def test_study_cli_rejects_partial_complete_profile(
    tmp_path: Path, profile: str
) -> None:
    policy = profile_policy(load_config(CONFIG, profile), profile)
    with pytest.raises(StudyError, match="complete ordered method grid"):
        study_main(
            [
                "--profile",
                profile,
                "--prepared-artifact",
                str(tmp_path / "must-not-load.npz"),
                "--output-root",
                str(tmp_path / "raw"),
                "--selection",
                str(tmp_path / "must-not-load-selection.json"),
                "--methods",
                EXPECTED_METHODS[0],
                "--tasks",
                ",".join(EXPECTED_TASKS),
                "--seeds",
                ",".join(str(seed) for seed in policy.seeds),
            ]
        )
    assert not (tmp_path / "raw").exists()


def test_full_profile_wrong_phase_is_rejected_before_later_attack_layers(
    tmp_path: Path,
) -> None:
    dirty_selection = tmp_path / "selection.json"
    dirty_selection.write_text('{"status":"selected","dirty":true}\n')
    output = tmp_path / "raw"
    with pytest.raises(StudyError, match="requires phase 'evaluation'"):
        run_profile(
            config_path=CONFIG,
            profile="full",
            prepared_artifact=tmp_path / "totally_fabricated_not_covertype.npz",
            output_root=output,
            selection_path=dirty_selection,
            phase="development",
        )
    assert not output.exists()


def _sentinel_cell(output_root: Path) -> tuple[Path, dict[str, bytes]]:
    directory = run_directory(
        output_root,
        phase="smoke",
        task=EXPECTED_TASKS[0],
        method=EXPECTED_METHODS[0],
        seed=0,
    )
    directory.mkdir(parents=True)
    payloads = {
        "manifest.json": b"sentinel manifest\n",
        "manifest.json.sha256": b"sentinel manifest sidecar\n",
        "rounds.jsonl": b"sentinel rounds\n",
        "rounds.jsonl.sha256": b"sentinel rounds sidecar\n",
        "summary.json": b"sentinel summary\n",
        "summary.json.sha256": b"sentinel summary sidecar\n",
        "failure.json": b"sentinel failure\n",
        "failure.json.sha256": b"sentinel failure sidecar\n",
    }
    for name, payload in payloads.items():
        (directory / name).write_bytes(payload)
    return directory, payloads


def test_run_profile_refuses_existing_cell_before_loading_or_execution(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "raw"
    directory, payloads = _sentinel_cell(output_root)
    with pytest.raises(FileExistsError, match="refusing to overwrite run files"):
        run_profile(
            config_path=CONFIG,
            profile="smoke",
            prepared_artifact=tmp_path / "missing-prepared.npz",
            output_root=output_root,
            methods=(EXPECTED_METHODS[0],),
            tasks=(EXPECTED_TASKS[0],),
            seeds=(0,),
        )
    assert {name: (directory / name).read_bytes() for name in payloads} == payloads


def test_production_evidence_writers_expose_no_overwrite_switch() -> None:
    assert "overwrite" not in inspect.signature(run_profile).parameters
    assert "overwrite" not in inspect.signature(write_run).parameters
    assert "overwrite" not in inspect.signature(write_failure).parameters


def test_atomic_writer_ignores_planted_predictable_temporary_symlink(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "evidence.json"
    victim = tmp_path / "victim.txt"
    victim.write_bytes(b"victim survives\n")
    planted = tmp_path / ".evidence.json.tmp"
    planted.symlink_to(victim)

    atomic_write_text(destination, "new evidence\n")

    assert destination.read_bytes() == b"new evidence\n"
    assert planted.is_symlink()
    assert planted.readlink() == victim
    assert victim.read_bytes() == b"victim survives\n"
    assert list(tmp_path.glob(".evidence.json.tmp-*")) == []


@pytest.mark.parametrize("occupant", ("file", "directory", "dangling_symlink"))
def test_atomic_writer_refuses_final_boundary_races(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    occupant: str,
) -> None:
    destination = tmp_path / "evidence.txt"
    victim = tmp_path / "victim.txt"
    victim.write_bytes(b"victim survives\n")
    dangling_target = tmp_path / "absent-target"
    real_link = provenance_module.os.link

    def inject_occupant(
        source: str | bytes | Path,
        target: str | bytes | Path,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        assert Path(target) == destination
        if occupant == "file":
            destination.write_bytes(b"destination sentinel\n")
        elif occupant == "directory":
            destination.mkdir()
        else:
            destination.symlink_to(dangling_target)
        real_link(
            source,
            target,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )

    monkeypatch.setattr(provenance_module.os, "link", inject_occupant)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        atomic_write_text(destination, "replacement\n")

    if occupant == "file":
        assert destination.read_bytes() == b"destination sentinel\n"
    elif occupant == "directory":
        assert destination.is_dir()
    else:
        assert destination.is_symlink()
        assert destination.readlink() == dangling_target
    assert victim.read_bytes() == b"victim survives\n"
    assert list(tmp_path.glob(".evidence.txt.tmp-*")) == []


@pytest.mark.parametrize("occupant", ("file", "directory", "dangling_symlink"))
def test_json_sidecar_writer_refuses_final_boundary_races(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    occupant: str,
) -> None:
    destination = tmp_path / "evidence.json"
    sidecar = tmp_path / "evidence.json.sha256"
    dangling_target = tmp_path / "absent-sidecar-target"
    real_link = provenance_module.os.link

    def inject_sidecar(
        source: str | bytes | Path,
        target: str | bytes | Path,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        if Path(target) == sidecar:
            if occupant == "file":
                sidecar.write_bytes(b"sidecar sentinel\n")
            elif occupant == "directory":
                sidecar.mkdir()
            else:
                sidecar.symlink_to(dangling_target)
        real_link(
            source,
            target,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )

    monkeypatch.setattr(provenance_module.os, "link", inject_sidecar)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_json(destination, {"status": "fixture"})

    assert destination.is_file()
    if occupant == "file":
        assert sidecar.read_bytes() == b"sidecar sentinel\n"
    elif occupant == "directory":
        assert sidecar.is_dir()
    else:
        assert sidecar.is_symlink()
        assert sidecar.readlink() == dangling_target
    assert list(tmp_path.glob(".evidence.json.sha256.tmp-*")) == []


@pytest.mark.parametrize("producer", ("run", "failure", "aggregate", "tuning"))
def test_evidence_producers_refuse_injected_final_file_races(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    producer: str,
) -> None:
    output = tmp_path / f"{producer}.json"
    if producer == "run":
        directory = tmp_path / "run-cell"
        raced_path = directory / "manifest.json"
        call = lambda: write_run(
            directory,
            manifest={"status": "completed"},
            rounds=({"round": 1},),
            summary={"status": "completed", "rounds": 1},
        )
    elif producer == "failure":
        directory = tmp_path / "failure-cell"
        raced_path = directory / "failure.json"
        call = lambda: write_failure(
            directory,
            context={"task": "fixture"},
            error=RuntimeError("fixture failure"),
        )
    elif producer == "aggregate":
        raw_root, _config, _policy = _write_full_shaped_fixture_raw(
            tmp_path, monkeypatch
        )
        raced_path = output
        call = lambda: aggregate_profile(
            config_path=CONFIG,
            profile="full",
            raw_root=raw_root,
            output_path=output,
        )
    else:
        repo, freeze = _fixture_repository(tmp_path)
        inventory = source_inventory_at_revision(freeze, repo_root=repo)
        tuning_path = tmp_path / "tuning-input.json"
        write_json(
            tuning_path,
            {
                "status": "complete",
                "freeze_revision": freeze,
                "config_digest": "1" * 64,
                "scientific_config_digest": "2" * 64,
                "prepared_data_digest": "3" * 64,
                "preprocessing_digest": "4" * 64,
                "source_inventory": inventory,
                "source_inventory_sha256": input_set_sha256(inventory),
                "selection": {
                    "optimizer": {},
                    "linucb_alpha": {},
                    "practical_nystrom": {},
                },
            },
        )
        raced_path = output
        call = lambda: lock_selection(
            tuning_path=tuning_path,
            output_path=output,
            repository_root=repo,
        )

    real_link = provenance_module.os.link

    def inject_file(
        source: str | bytes | Path,
        target: str | bytes | Path,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        if Path(target) == raced_path and not raced_path.exists():
            raced_path.write_bytes(b"racing sentinel\n")
        real_link(
            source,
            target,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )

    monkeypatch.setattr(provenance_module.os, "link", inject_file)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        call()
    assert raced_path.read_bytes() == b"racing sentinel\n"
    assert list(raced_path.parent.glob(f".{raced_path.name}.tmp-*")) == []


def test_public_preparation_apis_reject_overwrite_requests(tmp_path: Path) -> None:
    calls = (
        lambda: prepare_loaded_dataset(
            np.arange(12, dtype=np.float64).reshape(6, 2),
            np.arange(6, dtype=np.int64) % 2,
            dataset_name="fixture",
            destination=tmp_path / "loaded.npz",
            overwrite=True,
        ),
        lambda: prepare_covtype_artifact(
            cache_root=tmp_path / "cache",
            destination=tmp_path / "covtype.npz",
            overwrite=True,
        ),
        lambda: prepare_digits_artifact(
            destination=tmp_path / "digits.npz", overwrite=True
        ),
        lambda: prepare_dataset(
            "digits", None, tmp_path / "facade.npz", overwrite=True
        ),
    )
    for call in calls:
        with pytest.raises(ValueError, match="overwrite is not supported"):
            call()


def test_fixture_rewrite_helper_rejects_repository_paths() -> None:
    with pytest.raises(ValueError, match="cannot target the repository"):
        _rewrite_run_fixture(
            Path("results/raw/not-a-fixture"),
            manifest={"status": "completed"},
            rounds=({"round": 1},),
            summary={"status": "completed", "rounds": 1},
        )


@pytest.mark.parametrize("entrypoint", [study_main, run_main])
def test_production_clis_reject_overwrite_and_preserve_existing_cell(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], entrypoint: Any
) -> None:
    output_root = tmp_path / "raw"
    directory, payloads = _sentinel_cell(output_root)
    common = [
        "--config",
        str(CONFIG),
        "--profile",
        "smoke",
        "--prepared-artifact",
        str(tmp_path / "missing-prepared.npz"),
        "--output-root",
        str(output_root),
    ]
    if entrypoint is study_main:
        common.extend(
            [
                "--methods",
                EXPECTED_METHODS[0],
                "--tasks",
                EXPECTED_TASKS[0],
                "--seeds",
                "0",
            ]
        )
    else:
        common.extend(
            [
                "--method",
                EXPECTED_METHODS[0],
                "--task",
                EXPECTED_TASKS[0],
                "--seed",
                "0",
            ]
        )
    with pytest.raises(SystemExit) as raised:
        entrypoint([*common, "--overwrite"])
    assert raised.value.code == 2
    assert "unrecognized arguments: --overwrite" in capsys.readouterr().err
    assert {name: (directory / name).read_bytes() for name in payloads} == payloads


class _ArrayReadMustNotOccur:
    def __array__(self, *_args: object, **_kwargs: object) -> np.ndarray:
        raise AssertionError("array loading occurred before output preflight")


@pytest.mark.parametrize("occupied_name", ("artifact", "manifest", "sidecar"))
@pytest.mark.parametrize("occupied_kind", ("file", "directory", "dangling_symlink"))
def test_prepare_loaded_dataset_preflights_every_output_without_replacement(
    tmp_path: Path, occupied_name: str, occupied_kind: str
) -> None:
    artifact = tmp_path / "prepared.npz"
    paths = {
        "artifact": artifact,
        "manifest": artifact.with_suffix(".npz.manifest.json"),
        "sidecar": artifact.with_suffix(".npz.sha256"),
    }
    occupied = paths[occupied_name]
    if occupied_kind == "file":
        occupied.write_bytes(b"sentinel bytes\n")
    elif occupied_kind == "directory":
        occupied.mkdir()
    else:
        occupied.symlink_to(tmp_path / "absent-target")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        prepare_loaded_dataset(
            _ArrayReadMustNotOccur(),
            _ArrayReadMustNotOccur(),
            dataset_name="fixture",
            destination=artifact,
        )

    if occupied_kind == "file":
        assert occupied.read_bytes() == b"sentinel bytes\n"
    elif occupied_kind == "directory":
        assert occupied.is_dir()
    else:
        assert occupied.is_symlink()
        assert occupied.readlink() == tmp_path / "absent-target"


@pytest.mark.parametrize("occupied_name", ("artifact", "manifest", "sidecar"))
@pytest.mark.parametrize("entrypoint", ("covtype", "digits", "facade"))
def test_public_preparation_entrypoints_reject_before_loading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    occupied_name: str,
    entrypoint: str,
) -> None:
    artifact = tmp_path / f"{entrypoint}.npz"
    paths = {
        "artifact": artifact,
        "manifest": artifact.with_suffix(".npz.manifest.json"),
        "sidecar": artifact.with_suffix(".npz.sha256"),
    }
    occupied = paths[occupied_name]
    occupied.symlink_to(tmp_path / "absent-target")

    if entrypoint == "covtype":
        import sklearn.datasets

        monkeypatch.setattr(
            sklearn.datasets,
            "fetch_covtype",
            lambda **_kwargs: pytest.fail("fetch_covtype ran before output preflight"),
        )
        call = lambda: prepare_covtype_artifact(
            cache_root=tmp_path / "cache",
            destination=artifact,
            download_if_missing=False,
        )
    elif entrypoint == "digits":
        import sklearn.datasets

        monkeypatch.setattr(
            sklearn.datasets,
            "load_digits",
            lambda **_kwargs: pytest.fail("load_digits ran before output preflight"),
        )
        call = lambda: prepare_digits_artifact(destination=artifact)
    else:
        monkeypatch.setattr(
            data_module,
            "prepare_covtype_artifact",
            lambda **_kwargs: pytest.fail(
                "preparation dispatch ran before output preflight"
            ),
        )
        call = lambda: prepare_dataset(
            "covtype",
            tmp_path / "cache",
            artifact,
            download_if_missing=False,
        )
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        call()
    assert occupied.is_symlink()
    assert occupied.readlink() == tmp_path / "absent-target"
    assert not (tmp_path / "cache").exists()


def test_prepare_dataset_cli_is_write_once_and_rejects_overwrite_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact = tmp_path / "prepared.npz"
    artifact.write_bytes(b"sentinel artifact\n")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        prepare_dataset_main(["--dataset", "digits", "--output", str(artifact)])
    assert artifact.read_bytes() == b"sentinel artifact\n"

    with pytest.raises(SystemExit) as raised:
        prepare_dataset_main(
            ["--dataset", "digits", "--output", str(artifact), "--overwrite"]
        )
    assert raised.value.code == 2
    assert "unrecognized arguments: --overwrite" in capsys.readouterr().err
    assert artifact.read_bytes() == b"sentinel artifact\n"


def test_preparation_rechecks_without_replacing_a_racing_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "racing.npz"
    target = tmp_path / "absent-race-target"
    original_write = data_module._write_once
    first_write = True

    def inject_symlink(path: Path, payload: bytes) -> None:
        nonlocal first_write
        if first_write:
            first_write = False
            path.symlink_to(target)
        original_write(path, payload)

    monkeypatch.setattr(data_module, "_write_once", inject_symlink)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        prepare_loaded_dataset(
            np.arange(12, dtype=np.float64).reshape(6, 2),
            np.arange(6, dtype=np.int64) % 2,
            dataset_name="fixture",
            destination=artifact,
        )
    assert artifact.is_symlink()
    assert artifact.readlink() == target
    assert not artifact.with_suffix(".npz.manifest.json").exists()
    assert not artifact.with_suffix(".npz.sha256").exists()


@pytest.mark.parametrize("slot", ("output", "sidecar"))
@pytest.mark.parametrize(
    "producer",
    ("aggregate", "statistics", "tuning", "selection"),
)
def test_derived_production_outputs_reject_dangling_symlinks(
    tmp_path: Path, producer: str, slot: str
) -> None:
    output = tmp_path / f"{producer}.json"
    occupied = output if slot == "output" else output.with_name(output.name + ".sha256")
    target = tmp_path / f"absent-{producer}-{slot}"
    occupied.symlink_to(target)

    if producer == "aggregate":
        call = lambda: aggregate_profile(
            config_path=CONFIG,
            profile="smoke",
            raw_root=tmp_path / "raw",
            output_path=output,
        )
        error_type: type[Exception] = FileExistsError
    elif producer == "statistics":
        call = lambda: write_statistics_csv({"method_statistics": []}, output)
        error_type = FileExistsError
    elif producer == "tuning":
        call = lambda: run_tuning_suite(
            config_path=CONFIG,
            prepared_artifact=tmp_path / "missing.npz",
            output_path=output,
            freeze_revision="0" * 40,
            data_lock_path=tmp_path / "missing-lock.json",
        )
        error_type = TuningError
    else:
        call = lambda: lock_selection(
            tuning_path=tmp_path / "missing-tuning.json",
            output_path=output,
        )
        error_type = TuningError

    with pytest.raises(error_type, match="refusing to overwrite"):
        call()
    assert occupied.is_symlink()
    assert occupied.readlink() == target


def test_covtype_profiles_fail_closed_when_identity_or_lock_is_missing(
    tmp_path: Path,
) -> None:
    output = tmp_path / "raw"
    with pytest.raises(StudyError, match="approved data lock"):
        run_profile(
            config_path=CONFIG,
            profile="covtype_pilot",
            prepared_artifact=tmp_path / "fabricated.npz",
            output_root=output,
        )
    assert not output.exists()


def test_fixture_only_is_recorded_independently_from_smoke_only(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "fixture.npz"
    manifest = prepare_loaded_dataset(
        np.arange(12, dtype=np.float64).reshape(6, 2),
        np.arange(6, dtype=np.int64) % 2,
        dataset_name="synthetic_fixture",
        destination=artifact,
        smoke_only=False,
        fixture_only=True,
    )
    loaded = load_prepared_dataset(artifact)
    assert manifest["smoke_only"] is False
    assert manifest["fixture_only"] is True
    assert manifest["publication_evidence"] is False
    assert loaded.manifest["smoke_only"] is False
    assert loaded.manifest["fixture_only"] is True


def test_full_profile_rejects_missing_selection_before_execution(
    tmp_path: Path,
) -> None:
    output = tmp_path / "raw"
    with pytest.raises(StudyError, match="requires a locked selection"):
        run_profile(
            config_path=CONFIG,
            profile="full",
            prepared_artifact=tmp_path / "fabricated.npz",
            output_root=output,
        )
    assert not output.exists()


def test_full_aggregation_rejects_missing_selection_before_grid_read(
    tmp_path: Path,
) -> None:
    with pytest.raises(AggregateError, match="requires a selection artifact and L"):
        aggregate_profile(
            config_path=CONFIG,
            profile="full",
            raw_root=tmp_path / "raw",
            output_path=tmp_path / "aggregate.json",
            data_lock_path=tmp_path / "lock.json",
            freeze_revision="0" * 40,
        )
    assert not (tmp_path / "aggregate.json").exists()


def _data_lock_fixture(
    tmp_path: Path,
    *,
    dataset_name: str,
    features: np.ndarray | None = None,
    labels: np.ndarray | None = None,
) -> tuple[Path, str, Path, Path, dict[str, object]]:
    repo, _ = _fixture_repository(tmp_path)
    artifact = tmp_path / "candidate.npz"
    loader = {
        "callable": "sklearn.datasets.fetch_covtype",
        "scikit_learn_version": "fixture",
        "parameters": {
            "as_frame": False,
            "download_if_missing": True,
            "return_X_y": True,
            "shuffle": False,
        },
    }
    if features is None:
        features = np.arange(140, dtype=np.float64).reshape(20, 7)
    if labels is None:
        labels = np.arange(features.shape[0], dtype=np.int64) % 7
    manifest = prepare_loaded_dataset(
        features,
        labels,
        dataset_name=dataset_name,
        destination=artifact,
        loader_metadata=loader,
        smoke_only=False,
    )
    preprocessing = {"projection_dimension": 16}
    split_identity = {
        "namespace": "realistic-transport-covtype-v1",
        "buckets": {
            "development": [0, 20],
            "tuning": [20, 40],
            "evaluation": [40, 100],
        },
    }
    lock = {
        "schema": DATA_LOCK_SCHEMA,
        "status": "approved",
        "fixture_only": False,
        "dataset_name": "sklearn_covtype",
        "semantic_digest": manifest["array_content_sha256"],
        "artifact_sha256": manifest["artifact_sha256"],
        "manifest_sha256": sha256_file(artifact.with_suffix(".npz.manifest.json")),
        "loader_provenance": manifest["loader"],
        "runtime_provenance": manifest["runtime_provenance"],
        "source_cache_files": manifest["source_cache_files"],
        "split_identity": split_identity,
        "split_digest": "f" * 64,
        "preprocessing_policy_sha256": hashlib.sha256(
            canonical_json(preprocessing).encode("ascii")
        ).hexdigest(),
        "preprocessing_digest": "0" * 64,
    }
    lock_path = repo / "experiments/configs/covtype-data-lock.json"
    lock_path.write_text(
        json.dumps(lock, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    config = {
        "dataset": {
            "required_semantic_digest": manifest["array_content_sha256"],
            "approved_data_lock": {
                "path": "experiments/configs/covtype-data-lock.json",
                "sha256": sha256_file(lock_path),
            },
            "split_namespace": split_identity["namespace"],
            "split_buckets": split_identity["buckets"],
        },
        "preprocessing": preprocessing,
    }
    config_path = repo / "experiments/configs/realistic_transport_covtype.yaml"
    config_path.write_text(json.dumps(config, sort_keys=True) + "\n")
    _run_git(repo, "add", "experiments")
    _run_git(repo, "commit", "-q", "-m", "bind data")
    freeze = _run_git(repo, "rev-parse", "HEAD")
    return repo, freeze, artifact, lock_path, config


def test_internally_consistent_fabricated_covtype_is_not_approved(
    tmp_path: Path,
) -> None:
    repo, freeze, artifact, lock_path, config = _data_lock_fixture(
        tmp_path, dataset_name="sklearn_covtype"
    )
    with pytest.raises(IntegrityError, match="canonical Covertype dimensions"):
        authenticate_prepared_data(
            config=config,
            config_path=repo / "experiments/configs/realistic_transport_covtype.yaml",
            prepared_artifact=artifact,
            data_lock_path=lock_path,
            freeze_revision=freeze,
            repo_root=repo,
        )


def test_covtype_pilot_rejects_a_lock_without_explicit_f(tmp_path: Path) -> None:
    repo, _freeze, artifact, lock_path, config = _data_lock_fixture(
        tmp_path, dataset_name="sklearn_covtype"
    )
    with pytest.raises(IntegrityError, match="requires --freeze-revision"):
        authenticate_prepared_data(
            config=config,
            config_path=repo / "experiments/configs/realistic_transport_covtype.yaml",
            prepared_artifact=artifact,
            data_lock_path=lock_path,
            freeze_revision=None,
            repo_root=repo,
        )


def test_data_authentication_rejects_null_missing_and_modified_locks(
    tmp_path: Path,
) -> None:
    repo, freeze, artifact, lock_path, config = _data_lock_fixture(
        tmp_path, dataset_name="sklearn_covtype"
    )
    config_path = repo / "experiments/configs/realistic_transport_covtype.yaml"

    null_identity = copy.deepcopy(config)
    null_identity["dataset"]["required_semantic_digest"] = None
    with pytest.raises(IntegrityError, match="semantic digest is null"):
        authenticate_prepared_data(
            config=null_identity,
            config_path=config_path,
            prepared_artifact=artifact,
            data_lock_path=lock_path,
            freeze_revision=freeze,
            repo_root=repo,
        )

    with pytest.raises(IntegrityError, match="requires --data-lock"):
        authenticate_prepared_data(
            config=config,
            config_path=config_path,
            prepared_artifact=artifact,
            data_lock_path=None,
            freeze_revision=freeze,
            repo_root=repo,
        )

    lock_path.write_text(lock_path.read_text() + " ", encoding="utf-8")
    with pytest.raises(IntegrityError, match="bytes do not match"):
        authenticate_prepared_data(
            config=config,
            config_path=config_path,
            prepared_artifact=artifact,
            data_lock_path=lock_path,
            freeze_revision=freeze,
            repo_root=repo,
        )


def test_digits_masquerading_as_covtype_is_rejected(tmp_path: Path) -> None:
    repo, freeze, artifact, lock_path, config = _data_lock_fixture(
        tmp_path, dataset_name="sklearn_digits"
    )
    with pytest.raises(IntegrityError, match="wrong dataset identity"):
        authenticate_prepared_data(
            config=config,
            config_path=repo / "experiments/configs/realistic_transport_covtype.yaml",
            prepared_artifact=artifact,
            data_lock_path=lock_path,
            freeze_revision=freeze,
            repo_root=repo,
        )


def test_digits_bytes_self_labeled_as_covtype_are_rejected(tmp_path: Path) -> None:
    from sklearn.datasets import load_digits

    features, labels = load_digits(n_class=7, return_X_y=True)
    repo, freeze, artifact, lock_path, config = _data_lock_fixture(
        tmp_path,
        dataset_name="sklearn_covtype",
        features=np.asarray(features, dtype=np.float64),
        labels=np.asarray(labels, dtype=np.int64),
    )
    with pytest.raises(IntegrityError, match="canonical Covertype dimensions"):
        authenticate_prepared_data(
            config=config,
            config_path=repo / "experiments/configs/realistic_transport_covtype.yaml",
            prepared_artifact=artifact,
            data_lock_path=lock_path,
            freeze_revision=freeze,
            repo_root=repo,
        )


def test_fabricated_arrays_that_differ_from_lock_are_rejected(tmp_path: Path) -> None:
    repo, freeze, _artifact, lock_path, config = _data_lock_fixture(
        tmp_path, dataset_name="sklearn_covtype"
    )
    replacement = tmp_path / "replacement.npz"
    prepare_loaded_dataset(
        np.ones((20, 7)),
        np.arange(20, dtype=np.int64) % 7,
        dataset_name="sklearn_covtype",
        destination=replacement,
        loader_metadata=json.loads(lock_path.read_text())["loader_provenance"],
        smoke_only=False,
    )
    with pytest.raises(IntegrityError, match="differs from the approved data lock"):
        authenticate_prepared_data(
            config=config,
            config_path=repo / "experiments/configs/realistic_transport_covtype.yaml",
            prepared_artifact=replacement,
            data_lock_path=lock_path,
            freeze_revision=freeze,
            repo_root=repo,
        )


@pytest.mark.parametrize(
    "change",
    [
        "unstaged",
        "staged",
        "package_unstaged",
        "package_staged",
        "experiments_init_unstaged",
        "experiments_init_staged",
        "untracked",
        "ignored",
        "ignored_outside",
        "untracked_bytecode",
        "ignored_bytecode",
        "root_startup_untracked",
        "root_shadow_staged",
        "root_symlink_untracked",
        "root_symlink_ignored",
        "nested_symlink_untracked",
        "dependency",
    ],
)
def test_tuning_freeze_rejects_dirty_scientific_sources(
    tmp_path: Path, change: str
) -> None:
    repo, freeze = _fixture_repository(tmp_path)
    if change in {"unstaged", "staged"}:
        source = repo / "experiments/realistic_transport/core.py"
        source.write_text("VALUE = 2\n", encoding="utf-8")
        if change == "staged":
            _run_git(repo, "add", str(source.relative_to(repo)))
    elif change in {"package_unstaged", "package_staged"}:
        source = repo / "PACKAGE"
        source.write_text("# changed package policy\n", encoding="utf-8")
        if change == "package_staged":
            _run_git(repo, "add", str(source.relative_to(repo)))
    elif change in {"experiments_init_unstaged", "experiments_init_staged"}:
        source = repo / "experiments/__init__.py"
        source.write_text('"""Changed fixture package."""\n', encoding="utf-8")
        if change == "experiments_init_staged":
            _run_git(repo, "add", str(source.relative_to(repo)))
    elif change == "untracked":
        (repo / "experiments/realistic_transport/new_source.py").write_text(
            "VALUE = 2\n", encoding="utf-8"
        )
    elif change == "dependency":
        (repo / "experiments/requirements.txt").write_text(
            "numpy==0.0.0\n", encoding="utf-8"
        )
    elif change == "ignored_outside":
        source = repo / "notes/injected.py"
        source.parent.mkdir()
        source.write_text("VALUE = 2\n", encoding="utf-8")
    elif change == "untracked_bytecode":
        (repo / "sitecustomize.pyc").write_bytes(b"fixture bytecode")
    elif change == "ignored_bytecode":
        source = repo / "notes/ignored_bytecode.pyo"
        source.parent.mkdir()
        source.write_bytes(b"fixture optimized bytecode")
    elif change == "root_startup_untracked":
        (repo / "sitecustomize.py").write_text(
            "RAISED_AT_STARTUP = True\n", encoding="utf-8"
        )
    elif change == "root_shadow_staged":
        source = repo / "numpy.py"
        source.write_text("SHADOWS_NUMPY = True\n", encoding="utf-8")
        _run_git(repo, "add", source.name)
    elif change in {
        "root_symlink_untracked",
        "root_symlink_ignored",
        "nested_symlink_untracked",
    }:
        target = tmp_path / f"evil-{change}"
        target.mkdir()
        (target / "__init__.py").write_text("SHADOW = True\n", encoding="utf-8")
        name = {
            "root_symlink_untracked": "numpy",
            "root_symlink_ignored": "ignoredshadow",
            "nested_symlink_untracked": "numpy/linalg",
        }[change]
        source = repo / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.symlink_to(target, target_is_directory=True)
    else:
        (repo / "experiments/realistic_transport/ignored.py").write_text(
            "VALUE = 2\n", encoding="utf-8"
        )
    with pytest.raises(IntegrityError, match="scientific"):
        verify_clean_freeze(freeze, repo_root=repo, require_head=True)


@pytest.mark.parametrize("relative", _TRACKED_BUCK_INPUTS)
def test_freeze_rejects_tracked_buck_input_byte_changes(
    tmp_path: Path, relative: str
) -> None:
    repo, freeze = _fixture_repository(tmp_path)
    source = repo / relative
    source.write_bytes(source.read_bytes() + b"changed after F\n")

    with pytest.raises(IntegrityError, match="scientific sources differ from freeze"):
        verify_clean_freeze(freeze, repo_root=repo, require_head=True)


def test_freeze_rejects_tracked_cell_config_mode_change(tmp_path: Path) -> None:
    repo, freeze = _fixture_repository(tmp_path)
    cell_config = repo / ".buck/fbsource_cell/.buckconfig"
    cell_config.chmod(0o755)

    with pytest.raises(IntegrityError, match="scientific sources differ from freeze"):
        verify_clean_freeze(freeze, repo_root=repo, require_head=True)


@pytest.mark.parametrize("state", ("untracked", "staged"))
@pytest.mark.parametrize("relative", _ABSENT_BUCK_INPUTS)
def test_freeze_rejects_absent_at_f_buck_inputs(
    tmp_path: Path, relative: str, state: str
) -> None:
    repo, freeze = _fixture_repository(tmp_path)
    source = repo / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"repository-local Buck input added after F\n")
    if state == "staged":
        _run_git(repo, "add", relative)

    with pytest.raises(IntegrityError, match="scientific"):
        verify_clean_freeze(freeze, repo_root=repo, require_head=True)


def test_freeze_allows_explicit_nonscientific_raw_output(tmp_path: Path) -> None:
    repo, freeze = _fixture_repository(tmp_path)
    output = repo / "results/raw/realistic_transport/cell/summary.json"
    output.parent.mkdir(parents=True)
    output.write_text("{}\n", encoding="utf-8")
    assert verify_clean_freeze(freeze, repo_root=repo, require_head=True)


def test_scientific_path_policy_is_recursive_and_exempts_only_outputs() -> None:
    scientific_paths = (
        "sitecustomize/__init__.py",
        "numpy/__init__.py",
        "nested/package/module.pyi",
        "nested/cache/module.pyc",
        "nested/native/module.so",
        "nested/build/rules.bzl",
        "BUCK",
        "nested/package/BUCK",
        "nested/BUCK_TREE",
        "nested/PACKAGE",
        ".buckconfig",
        "nested/.buckconfig",
        ".buckconfig.local",
        "nested/.buckconfig.local",
        ".buckroot",
        "nested/.buckroot",
        ".buckconfig.d/override.bcfg",
        "nested/.buckconfig.d/deeper/override.bcfg",
        ".buck2",
        ".buck2-previous",
        ".buck2-versions/stable",
        "tools/buck2-versions/stable-users",
        "third_party/wheels/numpy.whl",
        "tests/run_buck_pytest.sh",
        "experiments/tests/run_buck_pytest.sh",
    )
    for path in scientific_paths:
        assert is_scientific_path(path)
    assert is_scientific_path("numpy", is_symlink=True)
    assert is_scientific_path("sitecustomize", is_symlink=True)
    assert is_scientific_path("numpy/linalg", is_symlink=True)
    for path in (
        "numpy",
        "BUCK.backup",
        "nested/BUCK_TREE.json",
        "nested/PACKAGE.lock",
        ".buckignore",
        ".buckversion",
        ".buckconfiguration",
        "nested/.buck2",
        "nested/.buck2-previous",
        "tools/not-buck2-versions/stable",
        "third_party/wheels-backup/numpy.whl",
        "/BUCK",
        "../BUCK",
    ):
        assert not is_scientific_path(path)
    for path in (
        "results/raw/BUCK",
        "results/logs/.buckconfig.local",
        "buck-out/v2/third_party/wheels/numpy.whl",
        "results/raw/.buckconfig.d/override.bcfg",
    ):
        assert not is_scientific_path(path, is_symlink=True)


def test_source_inventory_digest_binds_entry_mode() -> None:
    payload = [{"path": "sitecustomize.py", "sha256": "1" * 64}]
    regular = [{**payload[0], "mode": "100644"}]
    executable = [{**payload[0], "mode": "100755"}]
    symlink = [{**payload[0], "mode": "120000"}]
    assert (
        len(
            {
                input_set_sha256(payload),
                input_set_sha256(regular),
                input_set_sha256(executable),
                input_set_sha256(symlink),
            }
        )
        == 4
    )


def test_freeze_rejects_regular_to_allowlisted_symlink_with_same_blob(
    tmp_path: Path,
) -> None:
    repo, _ = _fixture_repository(tmp_path)
    build_defs = repo / "tools/build_defs"
    build_defs.parent.mkdir(parents=True)
    build_defs.write_bytes(b"target")
    (repo / "tools/target").write_bytes(b"extensionless dependency target\n")
    _run_git(repo, "add", "tools/build_defs", "tools/target")
    _run_git(repo, "commit", "-q", "-m", "regular build dependency")
    freeze = _run_git(repo, "rev-parse", "HEAD")
    frozen_entry = next(
        item
        for item in source_inventory_at_revision(freeze, repo_root=repo)
        if item["path"] == "tools/build_defs"
    )

    build_defs.unlink()
    build_defs.symlink_to("target")
    _run_git(repo, "add", "tools/build_defs")
    _run_git(repo, "commit", "-q", "-m", "change entry type")
    evaluation = _run_git(repo, "rev-parse", "HEAD")
    evaluation_entry = next(
        item
        for item in source_inventory_at_revision(evaluation, repo_root=repo)
        if item["path"] == "tools/build_defs"
    )

    assert (
        frozen_entry["sha256"] == evaluation_entry["sha256"] == sha256_bytes(b"target")
    )
    assert frozen_entry["mode"] == "100644"
    assert evaluation_entry["mode"] == "120000"
    with pytest.raises(IntegrityError, match="scientific sources differ from freeze"):
        verify_clean_freeze(freeze, repo_root=repo, require_head=False)


def test_freeze_rejects_executable_mode_change(tmp_path: Path) -> None:
    repo, freeze, lock_revision, _selection_path = _selection_fixture(tmp_path)
    source = repo / "experiments/realistic_transport/core.py"
    source.chmod(0o755)
    _run_git(repo, "add", "experiments/realistic_transport/core.py")
    _run_git(repo, "commit", "-q", "-m", "change executable mode")
    evaluation = _run_git(repo, "rev-parse", "HEAD")

    frozen_entry = next(
        item
        for item in source_inventory_at_revision(freeze, repo_root=repo)
        if item["path"] == "experiments/realistic_transport/core.py"
    )
    evaluation_entry = next(
        item
        for item in source_inventory_at_revision(evaluation, repo_root=repo)
        if item["path"] == "experiments/realistic_transport/core.py"
    )
    assert frozen_entry["sha256"] == evaluation_entry["sha256"]
    assert frozen_entry["mode"] == "100644"
    assert evaluation_entry["mode"] == "100755"
    with pytest.raises(IntegrityError, match="scientific sources differ from freeze"):
        verify_clean_freeze(freeze, repo_root=repo, require_head=False)
    with pytest.raises(IntegrityError, match="at E differ from F"):
        verify_evaluation_lineage(
            freeze_revision=freeze,
            selection_lock_revision=lock_revision,
            evaluation_state_revision=evaluation,
            repo_root=repo,
        )


def test_freeze_revision_rejects_preexisting_nonallowlisted_symlink(
    tmp_path: Path,
) -> None:
    repo, _ = _fixture_repository(tmp_path)
    target = repo / "stable_target"
    target.write_bytes(b"first target bytes\n")
    (repo / "numpy").symlink_to("stable_target")
    _run_git(repo, "add", "stable_target", "numpy")
    _run_git(repo, "commit", "-q", "-m", "unsafe frozen symlink")
    freeze = _run_git(repo, "rev-parse", "HEAD")

    with pytest.raises(IntegrityError, match="unsafe scientific symlink"):
        source_inventory_at_revision(freeze, repo_root=repo)

    target.write_bytes(b"changed extensionless target bytes\n")
    _run_git(repo, "add", "stable_target")
    _run_git(repo, "commit", "-q", "-m", "change symlink target bytes")
    with pytest.raises(IntegrityError, match="unsafe scientific symlink"):
        verify_clean_freeze(freeze, repo_root=repo, require_head=False)


def _buck_filegroup_block(path: str, name: str) -> str:
    content = Path(path).read_text(encoding="utf-8")
    match = re.search(rf'name\s*=\s*"{re.escape(name)}"', content)
    assert match is not None
    name_offset = match.start()
    start = content.rfind("filegroup(", 0, name_offset)
    assert start >= 0
    end = content.index("\n)\n", name_offset) + len("\n)\n")
    return content[start:end]


def test_buck_resource_filegroups_cover_the_package_aware_inventory() -> None:
    assert "experiments/realistic_transport/" in SCIENTIFIC_PREFIXES
    root_block = _buck_filegroup_block("BUCK", "realistic_transport_resources")
    package_blocks = {
        "experiments/realistic_transport/": _buck_filegroup_block(
            "experiments/realistic_transport/BUCK",
            "realistic_transport_package_inventory_resources",
        ),
        "experiments/tests/": _buck_filegroup_block(
            "experiments/tests/BUCK",
            "realistic_transport_experiment_tests_inventory_resources",
        ),
        "experiments/": _buck_filegroup_block(
            "experiments/BUCK", "realistic_transport_experiments_inventory_resources"
        ),
        "tests/": _buck_filegroup_block(
            "tests/BUCK", "realistic_transport_root_tests_inventory_resources"
        ),
        "third_party/": _buck_filegroup_block(
            "third_party/BUCK",
            "realistic_transport_third_party_inventory_resources",
        ),
        "tools/": _buck_filegroup_block(
            "tools/BUCK", "realistic_transport_tools_inventory_resources"
        ),
    }
    aggregate_edges = {
        "experiments/realistic_transport/": "//experiments/realistic_transport:realistic_transport_package_inventory_resources",
        "experiments/tests/": "//experiments/tests:realistic_transport_experiment_tests_inventory_resources",
        "experiments/": "//experiments:realistic_transport_experiments_inventory_resources",
        "tests/": "//tests:realistic_transport_root_tests_inventory_resources",
        "third_party/": "//third_party:realistic_transport_third_party_inventory_resources",
        "tools/": "//tools:realistic_transport_tools_inventory_resources",
    }
    for label in aggregate_edges.values():
        assert f'"{label}"' in root_block

    current_buck_inputs = {
        ".buck/fbsource_cell/.buckconfig",
        ".buck2",
        ".buckconfig",
        "BUCK",
        "PACKAGE",
        "experiments/BUCK",
        "experiments/realistic_transport/BUCK",
        "experiments/tests/BUCK",
        "experiments/tests/run_buck_pytest.sh",
        "paper/BUCK",
        "tests/BUCK",
        "tests/run_buck_pytest.sh",
        "third_party/BUCK",
        "third_party/wheels/SHA256SUMS",
        "third_party/wheels/numpy-2.2.3-cp312-cp312-manylinux_x86_64.whl",
        "third_party/wheels/scipy-1.13.1-cp312-cp312-manylinux_x86_64.whl",
        "tools/BUCK",
    }
    tracked_paths = set(
        subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    )
    assert current_buck_inputs <= tracked_paths
    inventory_paths = {item["path"] for item in source_inventory()}
    assert current_buck_inputs <= inventory_paths
    importable_suffixes = (".bzl", ".py", ".pyc", ".pyi", ".pyo", ".so")
    package_exact_inputs = {
        "experiments/": {
            "BUCK",
            "REALISTIC_TRANSPORT_PROTOCOL.md",
            "configs/realistic_transport_covtype.yaml",
            "requirements.txt",
        },
        "experiments/realistic_transport/": {"BUCK"},
        "experiments/tests/": {"BUCK", "run_buck_pytest.sh"},
        "tests/": {"BUCK", "run_buck_pytest.sh"},
        "third_party/": {"BUCK"},
        "tools/": {"BUCK", "build_defs"},
    }
    for prefix, exact_inputs in package_exact_inputs.items():
        block = package_blocks[prefix]
        for relative in exact_inputs:
            assert f'"{relative}"' in block
    for prefix in (
        "experiments/",
        "experiments/tests/",
        "tests/",
        "tools/",
    ):
        block = package_blocks[prefix]
        for suffix in importable_suffixes:
            assert f'"*{suffix}"' in block
            assert f'"**/*{suffix}"' in block

    realistic_package_block = package_blocks["experiments/realistic_transport/"]
    assert re.search(
        r'glob\(\s*\[\s*"\*\*"\s*\]\s*,\s*exclude\s*=\s*\[\s*"BUCK"\s*\]\s*\)',
        realistic_package_block,
    )
    assert {
        "experiments/realistic_transport/README.md",
        "experiments/realistic_transport/run_buck_pytest.sh",
        "experiments/realistic_transport/tests/test_environment.py",
    } <= inventory_paths

    third_party_wheels = _buck_filegroup_block(
        "third_party/BUCK", "realistic_transport_wheel_resources"
    )
    assert 'srcs = glob(["wheels/**"])' in third_party_wheels
    assert '":realistic_transport_wheel_resources"' in package_blocks["third_party/"]
    tools_versions = _buck_filegroup_block(
        "tools/BUCK", "realistic_transport_buck2_version_resources"
    )
    assert 'srcs = glob(["buck2-versions/**"])' in tools_versions
    assert '":realistic_transport_buck2_version_resources"' in package_blocks["tools/"]

    optional_root_inputs = {
        ".buck/fbsource_cell/.buckconfig.d/**",
        ".buck/fbsource_cell/.buckconfig.local",
        ".buck/fbsource_cell/.buckroot",
        ".buck2-previous",
        ".buck2-versions/**",
        ".buckconfig.d/**",
        ".buckconfig.local",
        ".buckroot",
        "BUCK_TREE",
    }
    for pattern in optional_root_inputs:
        assert f'"{pattern}"' in root_block

    def declared_by_package(relative: str) -> bool:
        if relative in {"paper/BUCK", "paper/validate.py"}:
            return f'"{relative}"' in root_block
        for prefix, block in package_blocks.items():
            if not relative.startswith(prefix):
                continue
            local = relative.removeprefix(prefix)
            if f'"{local}"' in block:
                return True
            if prefix == "experiments/realistic_transport/":
                return bool(
                    re.search(
                        r'glob\(\s*\[\s*"\*\*"\s*\]\s*,\s*exclude\s*=\s*\[\s*"BUCK"\s*\]\s*\)',
                        block,
                    )
                )
            if prefix == "third_party/" and local.startswith("wheels/"):
                return (
                    '":realistic_transport_wheel_resources"' in block
                    and 'srcs = glob(["wheels/**"])' in third_party_wheels
                )
            return any(
                local.endswith(suffix)
                and f'"*{suffix}"' in block
                and f'"**/*{suffix}"' in block
                for suffix in importable_suffixes
            )
        if f'"{relative}"' in root_block:
            return True
        return any(
            relative.endswith(suffix)
            and f'"*{suffix}"' in root_block
            and f'"**/*{suffix}"' in root_block
            for suffix in importable_suffixes
        )

    missing = sorted(
        item["path"]
        for item in source_inventory()
        if not declared_by_package(item["path"])
    )
    assert missing == []
    assert '"experiments/realistic_transport/**"' not in root_block
    for suffix in importable_suffixes:
        assert f'"*{suffix}"' in root_block
        assert f'"**/*{suffix}"' in root_block
    workflow = Path(".github/workflows/transport-committed-evidence.yml").read_text(
        encoding="utf-8"
    )
    assert workflow.count('- "**"') == 2
    for excluded in ("buck-out/**", "results/logs/**", "results/raw/**"):
        assert workflow.count(f'- "!{excluded}"') == 2


def test_scientific_symlink_allowlist_is_exactly_present_and_mode_bound() -> None:
    inventory = {item["path"]: item for item in source_inventory()}
    assert ALLOWED_SCIENTIFIC_SYMLINKS
    for relative in sorted(ALLOWED_SCIENTIFIC_SYMLINKS):
        path = Path(relative)
        assert path.is_symlink(), relative
        assert inventory[relative]["mode"] == "120000"
        assert inventory[relative]["sha256"] == sha256_bytes(
            str(path.readlink()).encode()
        )


def test_workflow_required_pipelines_enable_pipefail() -> None:
    workflow = Path(".github/workflows/transport-committed-evidence.yml").read_text(
        encoding="utf-8"
    )
    for step_name in (
        "Collect realistic trust-boundary tests",
        "Run realistic trust-boundary tests",
        "Detached committed-evidence verifier",
        "PDF structural checks",
        "Attempt the clean PDF rebuild",
    ):
        block = workflow.split(f"- name: {step_name}", 1)[1].split("- name:", 1)[0]
        assert "set -euo pipefail" in block


def test_tuning_freeze_rejects_wrong_f(tmp_path: Path) -> None:
    repo, _ = _fixture_repository(tmp_path)
    with pytest.raises(IntegrityError, match="git rev-parse"):
        verify_clean_freeze("0" * 40, repo_root=repo, require_head=True)


def _selection_fixture(
    tmp_path: Path, *, extra_at_l: bool = False
) -> tuple[Path, str, str, Path]:
    repo, freeze = _fixture_repository(tmp_path)
    inventory = source_inventory_at_revision(freeze, repo_root=repo)
    selection: dict[str, object] = {
        "schema_version": 2,
        "schema": SELECTION_SCHEMA,
        "status": "selected",
        "freeze_revision": freeze,
        "scientific_config_digest": "1" * 64,
        "prepared_data_digest": "2" * 64,
        "preprocessing_digest": "3" * 64,
        "source_inventory": inventory,
        "source_inventory_sha256": input_set_sha256(inventory),
        "optimizer": {
            "label": {"learning_rate": 0.0001, "steps_per_round": 5},
            "controlled_shared": {"learning_rate": 0.0001, "steps_per_round": 5},
        },
        "linucb_alpha": {task: 1.0 for task in EXPECTED_TASKS},
        "practical_nystrom": {
            task: "transport_nystrom_r32_cg_1e-4" for task in EXPECTED_TASKS
        },
    }
    selection["selection_payload_sha256"] = selection_payload_sha256(selection)
    selection_path = repo / "review/realistic_transport/SELECTION.json"
    write_json(selection_path, selection)
    _run_git(repo, "add", "review/realistic_transport/SELECTION.json")
    _run_git(repo, "add", "review/realistic_transport/SELECTION.json.sha256")
    if extra_at_l:
        (repo / "notes.txt").write_text("not selection\n")
        _run_git(repo, "add", "notes.txt")
    _run_git(repo, "commit", "-q", "-m", "selection lock")
    return repo, freeze, _run_git(repo, "rev-parse", "HEAD"), selection_path


def test_selection_lock_verifies_exact_bytes_f_and_selection_only_l(
    tmp_path: Path,
) -> None:
    repo, freeze, lock_revision, selection_path = _selection_fixture(tmp_path)
    document, digest = verify_selection_lock(
        selection_path=selection_path,
        freeze_revision=freeze,
        selection_lock_revision=lock_revision,
        repo_root=repo,
    )
    assert document["freeze_revision"] == freeze
    assert digest == sha256_file(selection_path)
    verify_evaluation_lineage(
        freeze_revision=freeze,
        selection_lock_revision=lock_revision,
        evaluation_state_revision=lock_revision,
        repo_root=repo,
    )
    assert not publication_eligibility(
        profile="resource_fallback",
        phase="evaluation",
        evidence_role="pilot_only_non_publication",
        prepared_data={
            "dataset_name": "sklearn_covtype",
            "smoke_only": False,
            "fixture_only": False,
            "publication_evidence": False,
        },
        data_authorized=True,
        selection_authorized=True,
        deterministic_failure_count=0,
    )


def test_selection_lock_rejects_uncommitted_bytes_and_nonselection_l(
    tmp_path: Path,
) -> None:
    repo, freeze, lock_revision, selection_path = _selection_fixture(tmp_path)
    selection_path.write_text(selection_path.read_text() + " ", encoding="utf-8")
    with pytest.raises(IntegrityError, match="not committed unchanged"):
        verify_selection_lock(
            selection_path=selection_path,
            freeze_revision=freeze,
            selection_lock_revision=lock_revision,
            repo_root=repo,
        )

    other_root = tmp_path / "other"
    other_root.mkdir()
    other_repo, other_freeze, other_l, other_selection = _selection_fixture(
        other_root, extra_at_l=True
    )
    with pytest.raises(IntegrityError, match="not selection-only"):
        verify_selection_lock(
            selection_path=other_selection,
            freeze_revision=other_freeze,
            selection_lock_revision=other_l,
            repo_root=other_repo,
        )


def test_selection_lock_rejects_wrong_f(
    tmp_path: Path,
) -> None:
    repo, freeze, lock_revision, selection_path = _selection_fixture(tmp_path)
    wrong = json.loads(selection_path.read_text())
    wrong["freeze_revision"] = lock_revision
    selection_path.write_text(json.dumps(wrong, sort_keys=True) + "\n")
    with pytest.raises(IntegrityError, match="wrong F"):
        verify_selection_lock(
            selection_path=selection_path,
            freeze_revision=freeze,
            selection_lock_revision=lock_revision,
            repo_root=repo,
        )


def test_selection_lock_rejects_wrong_payload_hash_and_e_before_l(
    tmp_path: Path,
) -> None:
    repo, freeze, lock_revision, selection_path = _selection_fixture(tmp_path)
    selection = json.loads(selection_path.read_text())
    selection["selection_payload_sha256"] = "0" * 64
    selection_path.write_text(json.dumps(selection, sort_keys=True) + "\n")
    with pytest.raises(IntegrityError, match="payload hash"):
        verify_selection_lock(
            selection_path=selection_path,
            freeze_revision=freeze,
            selection_lock_revision=lock_revision,
            repo_root=repo,
        )
    with pytest.raises(IntegrityError, match="does not descend from L"):
        verify_evaluation_lineage(
            freeze_revision=freeze,
            selection_lock_revision=lock_revision,
            evaluation_state_revision=freeze,
            repo_root=repo,
        )


@pytest.mark.parametrize(
    "relative",
    (
        "experiments/realistic_transport/core.py",
        "PACKAGE",
        "experiments/__init__.py",
        "sitecustomize.py",
        "numpy.pyc",
        "sitecustomize/__init__.py",
        "numpy/__init__.py",
        "nested/importable.py",
        "nested/cache/shadow.pyc",
    ),
)
def test_evaluation_lineage_rejects_scientific_changes_after_l(
    tmp_path: Path, relative: str
) -> None:
    repo, freeze, lock_revision, _selection_path = _selection_fixture(tmp_path)
    source = repo / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        source.write_text(source.read_text(encoding="utf-8") + "# changed at E\n")
    elif source.suffix in {".pyc", ".pyo"}:
        source.write_bytes(b"committed sourceless bytecode")
    else:
        source.write_text("ROOT_IMPORT_SHADOW = True\n", encoding="utf-8")
    _run_git(repo, "add", str(source.relative_to(repo)))
    _run_git(repo, "commit", "-q", "-m", "invalid evaluation source change")
    evaluation = _run_git(repo, "rev-parse", "HEAD")
    with pytest.raises(IntegrityError, match="scientific sources differ from freeze"):
        verify_clean_freeze(freeze, repo_root=repo, require_head=False)
    with pytest.raises(IntegrityError, match="at E differ from F"):
        verify_evaluation_lineage(
            freeze_revision=freeze,
            selection_lock_revision=lock_revision,
            evaluation_state_revision=evaluation,
            repo_root=repo,
        )


@pytest.mark.parametrize("relative", (*_TRACKED_BUCK_INPUTS, *_ABSENT_BUCK_INPUTS))
def test_evaluation_lineage_rejects_buck_inputs_committed_after_l(
    tmp_path: Path, relative: str
) -> None:
    repo, freeze, lock_revision, _selection_path = _selection_fixture(tmp_path)
    source = repo / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        source.write_bytes(source.read_bytes() + b"changed after L\n")
    else:
        source.write_bytes(b"repository-local Buck input added after L\n")
    _run_git(repo, "add", relative)
    _run_git(repo, "commit", "-q", "-m", "change Buck input after L")
    evaluation = _run_git(repo, "rev-parse", "HEAD")

    with pytest.raises(IntegrityError, match="scientific sources differ from freeze"):
        verify_clean_freeze(freeze, repo_root=repo, require_head=False)
    with pytest.raises(IntegrityError, match="at E differ from F"):
        verify_evaluation_lineage(
            freeze_revision=freeze,
            selection_lock_revision=lock_revision,
            evaluation_state_revision=evaluation,
            repo_root=repo,
        )


def test_evaluation_lineage_rejects_cell_config_mode_change_after_l(
    tmp_path: Path,
) -> None:
    repo, freeze, lock_revision, _selection_path = _selection_fixture(tmp_path)
    cell_config = repo / ".buck/fbsource_cell/.buckconfig"
    cell_config.chmod(0o755)
    _run_git(repo, "add", ".buck/fbsource_cell/.buckconfig")
    _run_git(repo, "commit", "-q", "-m", "change cell config mode after L")
    evaluation = _run_git(repo, "rev-parse", "HEAD")

    with pytest.raises(IntegrityError, match="at E differ from F"):
        verify_evaluation_lineage(
            freeze_revision=freeze,
            selection_lock_revision=lock_revision,
            evaluation_state_revision=evaluation,
            repo_root=repo,
        )


@pytest.mark.parametrize("name", ("sitecustomize", "numpy", "numpy/linalg"))
def test_symlink_package_added_after_l_is_scientific(tmp_path: Path, name: str) -> None:
    repo, freeze, lock_revision, _selection_path = _selection_fixture(tmp_path)
    target = tmp_path / f"evil-{name.replace('/', '-')}"
    target.mkdir()
    (target / "__init__.py").write_text("SHADOW = True\n", encoding="utf-8")
    shadow = repo / name
    shadow.parent.mkdir(parents=True, exist_ok=True)
    shadow.symlink_to(target, target_is_directory=True)
    _run_git(repo, "add", name)
    _run_git(repo, "commit", "-q", "-m", "invalid symlink package shadow")
    evaluation = _run_git(repo, "rev-parse", "HEAD")

    with pytest.raises(IntegrityError, match="unsafe scientific symlink"):
        verify_clean_freeze(freeze, repo_root=repo, require_head=False)
    with pytest.raises(IntegrityError, match="unsafe scientific symlink"):
        verify_evaluation_lineage(
            freeze_revision=freeze,
            selection_lock_revision=lock_revision,
            evaluation_state_revision=evaluation,
            repo_root=repo,
        )


def test_selection_lock_rejects_selection_absent_from_l(tmp_path: Path) -> None:
    repo, freeze, lock_revision, _selection_path = _selection_fixture(tmp_path)
    absent = repo / "review/realistic_transport/ABSENT.json"
    original = json.loads(
        _run_git(
            repo, "show", f"{lock_revision}:review/realistic_transport/SELECTION.json"
        )
    )
    absent.write_text(json.dumps(original, sort_keys=True) + "\n")
    with pytest.raises(IntegrityError, match="git show"):
        verify_selection_lock(
            selection_path=absent,
            freeze_revision=freeze,
            selection_lock_revision=lock_revision,
            repo_root=repo,
        )


def test_selection_policy_rejects_choices_outside_frozen_grids() -> None:
    config = load_config(CONFIG, "full")
    selection = {
        "optimizer": {
            "label": {"learning_rate": 0.0001, "steps_per_round": 5},
            "controlled_shared": {
                "learning_rate": 0.0001,
                "steps_per_round": 5,
            },
        },
        "linucb_alpha": {task: 1.0 for task in EXPECTED_TASKS},
        "practical_nystrom": {
            task: "transport_nystrom_r32_cg_1e-4" for task in EXPECTED_TASKS
        },
    }
    validate_selection_policy(selection, config)
    selection["practical_nystrom"][
        EXPECTED_TASKS[1]
    ] = "transport_exact_corrected_cholesky"
    with pytest.raises(IntegrityError, match="outside the grid"):
        validate_selection_policy(selection, config)


@pytest.mark.parametrize(
    "field", ["context_order", "noise", "prepared_data", "preprocessing", "split"]
)
def test_aggregation_rejects_each_independent_mixed_stream(
    field: str,
) -> None:
    task = EXPECTED_TASKS[1]
    first = _base_stream_identity(task)
    second = dict(first)
    second[field] = "f" * 64
    manifests = {
        (task, "method_a", 100): _manifest_with_stream_identity(task, first),
        (task, "method_b", 100): _manifest_with_stream_identity(task, second),
    }
    with pytest.raises(AggregateError, match="mixed exogenous streams"):
        _validate_paired_streams(manifests)


def test_controlled_tasks_share_noise_but_keep_distinct_mean_constructions() -> None:
    manifests = {}
    for task in EXPECTED_TASKS[1:]:
        for method in ("method_a", "method_b"):
            manifests[(task, method, 100)] = _manifest_with_stream_identity(task)
    _validate_paired_streams(manifests)
    broken = copy.deepcopy(manifests)
    broken[(EXPECTED_TASKS[2], "method_b", 100)]["exogenous_stream_identity"][
        "noise"
    ] = ("0" * 64)
    with pytest.raises(AggregateError, match="mixed exogenous streams"):
        _validate_paired_streams(broken)


def test_method_specific_sketch_randomness_is_not_a_pairing_identity() -> None:
    task = EXPECTED_TASKS[1]
    identity = _base_stream_identity(task)
    manifests = {
        (task, "transport_nystrom_r16_cg_1e-2", 100): {
            **_manifest_with_stream_identity(task, identity),
            "nystrom_sketch_seed": 16,
        },
        (task, "transport_nystrom_r64_cg_1e-2", 100): {
            **_manifest_with_stream_identity(task, dict(identity)),
            "nystrom_sketch_seed": 64,
        },
    }
    _validate_paired_streams(manifests)


def test_manifest_policy_rejects_wrong_horizon_and_identity() -> None:
    config = load_config(CONFIG, "full")
    policy = profile_policy(config, "full")
    manifest = {
        "status": "completed",
        "profile": "full",
        "phase": "evaluation",
        "evidence_role": "publication_candidate",
        "publication_evidence": False,
        "dataset_mode": "covtype",
        "seed_set_identity": policy.seed_set_identity,
        "task": EXPECTED_TASKS[0],
        "method": "transport_exact_corrected_cholesky",
        "base_seed": 100,
        "rounds": 250,
        "config_digest": config_digest(config),
    }
    summary = {
        "status": "completed",
        "profile": "full",
        "phase": "evaluation",
        "publication_evidence": False,
        "task": EXPECTED_TASKS[0],
        "method": "transport_exact_corrected_cholesky",
        "seed": 100,
    }
    with pytest.raises(AggregateError, match="wrong horizon"):
        _validate_manifest_identity(
            manifest,
            summary,
            profile="full",
            phase="evaluation",
            evidence_role="publication_candidate",
            dataset_mode="covtype",
            seed_set_identity=policy.seed_set_identity,
            task=EXPECTED_TASKS[0],
            method="transport_exact_corrected_cholesky",
            seed=100,
            rounds=500,
            expected_config_digest=config_digest(config),
            expected_resolved_config=config,
        )
    manifest["rounds"] = 500
    manifest["status"] = "running"
    with pytest.raises(AggregateError, match="manifest is not completed"):
        _validate_manifest_identity(
            manifest,
            summary,
            profile="full",
            phase="evaluation",
            evidence_role="publication_candidate",
            dataset_mode="covtype",
            seed_set_identity=policy.seed_set_identity,
            task=EXPECTED_TASKS[0],
            method="transport_exact_corrected_cholesky",
            seed=100,
            rounds=500,
            expected_config_digest=config_digest(config),
            expected_resolved_config=config,
        )
    manifest["status"] = "completed"
    manifest["config_digest"] = "0" * 64
    with pytest.raises(AggregateError, match="config digest"):
        _validate_manifest_identity(
            manifest,
            summary,
            profile="full",
            phase="evaluation",
            evidence_role="publication_candidate",
            dataset_mode="covtype",
            seed_set_identity=policy.seed_set_identity,
            task=EXPECTED_TASKS[0],
            method="transport_exact_corrected_cholesky",
            seed=100,
            rounds=500,
            expected_config_digest=config_digest(config),
            expected_resolved_config=config,
        )


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("profile", "smoke"),
        ("phase", "tuning"),
        ("task", EXPECTED_TASKS[1]),
        ("method", "greedy_corrected"),
        ("seed", 101),
    ],
)
def test_manifest_policy_rejects_each_summary_identity(
    field: str, wrong: object
) -> None:
    config = load_config(CONFIG, "full")
    policy = profile_policy(config, "full")
    method = "transport_exact_corrected_cholesky"
    manifest = {
        "status": "completed",
        "profile": "full",
        "phase": "evaluation",
        "evidence_role": "publication_candidate",
        "publication_evidence": False,
        "dataset_mode": "covtype",
        "seed_set_identity": policy.seed_set_identity,
        "task": EXPECTED_TASKS[0],
        "method": method,
        "base_seed": 100,
        "rounds": 500,
        "config_digest": config_digest(config),
    }
    summary = {
        "status": "completed",
        "profile": "full",
        "phase": "evaluation",
        "publication_evidence": False,
        "task": EXPECTED_TASKS[0],
        "method": method,
        "seed": 100,
    }
    summary[field] = wrong
    with pytest.raises(AggregateError, match=f"summary {field} mismatch"):
        _validate_manifest_identity(
            manifest,
            summary,
            profile="full",
            phase="evaluation",
            evidence_role="publication_candidate",
            dataset_mode="covtype",
            seed_set_identity=policy.seed_set_identity,
            task=EXPECTED_TASKS[0],
            method=method,
            seed=100,
            rounds=500,
            expected_config_digest=config_digest(config),
            expected_resolved_config=config,
        )


@pytest.mark.parametrize(
    ("field", "wrong", "message"),
    [
        ("phase", "development", "wrong phase"),
        ("phase", "tuning", "wrong phase"),
        ("dataset_mode", "digits_smoke", "wrong dataset_mode"),
        ("evidence_role", "pilot_only", "wrong evidence_role"),
        ("seed_set_identity", "0" * 64, "wrong seed_set_identity"),
    ],
)
def test_aggregation_rejects_full_manifest_policy_spoofing(
    field: str, wrong: str, message: str
) -> None:
    config = load_config(CONFIG, "full")
    policy = profile_policy(config, "full")
    manifest = {
        "status": "completed",
        "profile": "full",
        "phase": "evaluation",
        "evidence_role": "publication_candidate",
        "publication_evidence": False,
        "dataset_mode": "covtype",
        "seed_set_identity": policy.seed_set_identity,
        "task": EXPECTED_TASKS[0],
        "method": "transport_exact_corrected_cholesky",
        "base_seed": 100,
        "rounds": 500,
        "config_digest": config_digest(config),
    }
    summary = {
        "status": "completed",
        "profile": "full",
        "phase": "evaluation",
        "publication_evidence": False,
        "task": EXPECTED_TASKS[0],
        "method": "transport_exact_corrected_cholesky",
        "seed": 100,
    }
    manifest[field] = wrong
    with pytest.raises(AggregateError, match=message):
        _validate_manifest_identity(
            manifest,
            summary,
            profile="full",
            phase="evaluation",
            evidence_role="publication_candidate",
            dataset_mode="covtype",
            seed_set_identity=policy.seed_set_identity,
            task=EXPECTED_TASKS[0],
            method="transport_exact_corrected_cholesky",
            seed=100,
            rounds=500,
            expected_config_digest=config_digest(config),
            expected_resolved_config=config,
        )


def test_aggregate_rejects_an_extra_method_seed_cell(tmp_path: Path) -> None:
    extra = tmp_path / "raw/smoke/unexpected/method/seed-999"
    extra.mkdir(parents=True)
    (extra / "summary.json").write_text("{}\n")
    with pytest.raises(AggregateError, match=r"extra=.*999"):
        aggregate_profile(
            config_path=CONFIG,
            profile="smoke",
            raw_root=tmp_path / "raw",
            output_path=tmp_path / "aggregate.json",
        )


def test_semantic_failures_and_event_violations_are_preserved() -> None:
    status = _semantic_status(
        [
            {
                "analytic_certificate_valid_in_exact_arithmetic": True,
                "deterministic_failure": False,
                "float64_diagnostic_pass": True,
                "verified_numerical_certificate": False,
                "instantaneous_theorem_bound_status": "satisfied",
                "cumulative_theorem_bound_status": "satisfied",
            },
            {
                "analytic_certificate_valid_in_exact_arithmetic": True,
                "deterministic_failure": True,
                "float64_diagnostic_pass": False,
                "verified_numerical_certificate": False,
                "instantaneous_theorem_bound_status": "bound_violation_on_event",
                "cumulative_theorem_bound_status": "bound_violation_on_event",
            },
        ]
    )
    assert status == {
        "analytic_certificate_valid_in_exact_arithmetic": True,
        "deterministic_failure": True,
        "float64_diagnostic_pass": False,
        "verified_numerical_certificate": False,
        "instantaneous_theorem_event_violation_count": 1,
        "cumulative_theorem_event_violation_count": 1,
    }


def test_negative_theorem_outcome_is_not_an_integrity_failure() -> None:
    status = _semantic_status(
        [
            {
                "analytic_certificate_valid_in_exact_arithmetic": True,
                "deterministic_failure": False,
                "float64_diagnostic_pass": True,
                "verified_numerical_certificate": False,
                "instantaneous_theorem_bound_status": "bound_violation_on_event",
                "cumulative_theorem_bound_status": "bound_violation_on_event",
            }
        ]
    )
    assert not status["deterministic_failure"]
    assert status["float64_diagnostic_pass"]
    assert status["instantaneous_theorem_event_violation_count"] == 1
    assert status["cumulative_theorem_event_violation_count"] == 1


def test_rederived_negative_theorem_outcome_remains_valid() -> None:
    record = _fixture_round(
        task=EXPECTED_TASKS[1],
        method="transport_exact_corrected_cholesky",
        seed=100,
        round_number=1,
        rounds=1,
    )
    record["instantaneous_pseudo_regret"] = 2.0
    record["cumulative_pseudo_regret"] = 2.0
    record["true_means"] = [0.0, 2.0]
    record["selected_mean"] = 0.0
    record["optimal_mean"] = 2.0
    record["theorem_bound_comparison_tolerance"] = (
        4096.0 * np.finfo(np.float64).eps * 50 * 2.0
    )
    record["instantaneous_theorem_rhs"] = 1.0
    record["sharp_theorem_rhs"] = 1.0
    record["instantaneous_theorem_bound_status"] = "bound_violation_on_event"
    record["cumulative_theorem_bound_status"] = "bound_violation_on_event"
    _validate_round_semantics(
        [record],
        task=EXPECTED_TASKS[1],
        method="transport_exact_corrected_cholesky",
        feature_dimension=50,
        action_count=2,
    )
    status = _semantic_status([record])
    assert status["instantaneous_theorem_event_violation_count"] == 1
    assert status["cumulative_theorem_event_violation_count"] == 1


def test_controlled_secondary_statistic_averages_tasks_within_seed_first() -> None:
    result = controlled_task_average_bootstrap(
        {
            EXPECTED_TASKS[1]: {100: 0.0, 101: 0.0, 102: 30.0},
            EXPECTED_TASKS[2]: {100: 30.0, 101: 0.0, 102: 0.0},
        },
        {
            EXPECTED_TASKS[1]: {100: 0.0, 101: 0.0, 102: 0.0},
            EXPECTED_TASKS[2]: {100: 0.0, 101: 0.0, 102: 0.0},
        },
        tasks=EXPECTED_TASKS[1:],
        bootstrap_seed=7,
        resamples=1000,
    )
    assert result["first_within_seed"] == {100: 15.0, 101: 0.0, 102: 15.0}
    assert result["second_within_seed"] == {100: 0.0, 101: 0.0, 102: 0.0}
    assert result["seed_keys"] == [100, 101, 102]
    assert result["paired_difference"]["mean"] == 10.0
    pooled = paired_seed_bootstrap(
        {0: 0.0, 1: 0.0, 2: 30.0, 3: 30.0, 4: 0.0, 5: 0.0},
        {index: 0.0 for index in range(6)},
        bootstrap_seed=7,
        resamples=1000,
    )
    assert (
        result["paired_difference"]["bootstrap_mean_interval"]
        != pooled["paired_difference"]["bootstrap_mean_interval"]
    )

    generator = np.random.default_rng(7)
    b_differences = np.asarray([0.0, 0.0, 30.0])
    c_differences = np.asarray([30.0, 0.0, 0.0])
    independent_draws = 0.5 * (
        np.mean(b_differences[generator.integers(0, 3, size=(1000, 3))], axis=1)
        + np.mean(c_differences[generator.integers(0, 3, size=(1000, 3))], axis=1)
    )
    independent_interval = np.quantile(
        independent_draws, (0.025, 0.975), method="linear"
    ).tolist()
    assert (
        result["paired_difference"]["bootstrap_mean_interval"]["ci"]
        != independent_interval
    )


def test_full_shaped_fixture_remains_nonpublication_through_real_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)
    fixture_cell = run_directory(
        raw_root,
        phase="full",
        task=EXPECTED_TASKS[0],
        method=EXPECTED_METHODS[0],
        seed=100,
    )
    fixture_manifest = json.loads(
        (fixture_cell / "manifest.json").read_text(encoding="utf-8")
    )
    fixture_summary = json.loads(
        (fixture_cell / "summary.json").read_text(encoding="utf-8")
    )
    assert fixture_manifest["prepared_data"]["smoke_only"] is True
    assert fixture_manifest["prepared_data"]["fixture_only"] is True
    assert fixture_manifest["prepared_data"]["publication_evidence"] is False
    assert fixture_manifest["publication_evidence"] is False
    assert fixture_summary["publication_evidence"] is False
    aggregate_path = tmp_path / "aggregate.json"
    aggregate_profile(
        config_path=CONFIG,
        profile="full",
        raw_root=raw_root,
        output_path=aggregate_path,
    )
    serialized = json.loads(aggregate_path.read_text(encoding="utf-8"))
    assert serialized["accepted_cell_count"] == len(EXPECTED_TASKS) * len(
        EXPECTED_METHODS
    )
    assert serialized["common_provenance"]["prepared_data"]["fixture_only"] is True
    assert serialized["publication_evidence"] is False

    review_root = tmp_path / "rendered"
    generate_artifacts(
        aggregate_path=aggregate_path,
        review_root=review_root,
        config_path=CONFIG,
        profile="full",
        raw_root=raw_root,
    )
    provenance = json.loads(
        (review_root / "DATA_PROVENANCE.json").read_text(encoding="utf-8")
    )
    statistical = json.loads(
        (review_root / "STATISTICAL_RESULTS.json").read_text(encoding="utf-8")
    )
    assert provenance["common_provenance"]["prepared_data"]["fixture_only"] is True
    assert provenance["publication_evidence"] is False
    assert statistical["publication_evidence"] is False


def test_forged_full_aggregate_cannot_create_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)
    accepted_path = tmp_path / "accepted.json"
    aggregate_profile(
        config_path=CONFIG,
        profile="full",
        raw_root=raw_root,
        output_path=accepted_path,
    )
    forged = json.loads(accepted_path.read_text(encoding="utf-8"))
    forged["publication_evidence"] = True
    prepared = forged["common_provenance"]["prepared_data"]
    prepared["dataset_name"] = "sklearn_covtype"
    prepared["smoke_only"] = False
    prepared["fixture_only"] = False
    forged["common_provenance"]["data_authentication"] = {
        "status": "verified_against_committed_freeze_lock",
        "freeze_revision": "a" * 40,
        "data_lock_path": "experiments/configs/forged-lock.json",
        "data_lock_sha256": "b" * 64,
        "manifest_sha256": "c" * 64,
    }
    forged["common_provenance"]["selection_artifact_sha256"] = "d" * 64
    forged["common_provenance"]["selection_lock_revision"] = "e" * 40
    forged_path = tmp_path / "forged.json"
    write_json(forged_path, forged)

    review_root = tmp_path / "forged-output"
    with pytest.raises(ValueError, match="independently validated raw grid"):
        generate_artifacts(
            aggregate_path=forged_path,
            review_root=review_root,
            config_path=CONFIG,
            profile="full",
            raw_root=raw_root,
        )
    assert not review_root.exists()


def test_artifact_generator_refuses_an_existing_output_root(tmp_path: Path) -> None:
    review_root = tmp_path / "existing"
    review_root.mkdir()
    sentinel = review_root / "sentinel.txt"
    sentinel.write_text("preserve me\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="existing evidence root"):
        generate_artifacts(
            aggregate_path=tmp_path / "missing.json",
            review_root=review_root,
            config_path=CONFIG,
            profile="smoke",
            raw_root=tmp_path / "raw",
        )
    assert sentinel.read_text(encoding="utf-8") == "preserve me\n"


def test_artifact_generator_refuses_an_empty_directory_final_boundary_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)
    aggregate_path = tmp_path / "aggregate.json"
    aggregate_profile(
        config_path=CONFIG,
        profile="full",
        raw_root=raw_root,
        output_path=aggregate_path,
    )
    review_root = tmp_path / "raced-review"
    publish = artifacts_module._publish_directory_no_replace

    def inject_empty_directory(source: Path, destination: Path) -> None:
        assert destination == review_root
        destination.mkdir()
        publish(source, destination)

    monkeypatch.setattr(
        artifacts_module, "_publish_directory_no_replace", inject_empty_directory
    )
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        generate_artifacts(
            aggregate_path=aggregate_path,
            review_root=review_root,
            config_path=CONFIG,
            profile="full",
            raw_root=raw_root,
        )

    assert review_root.is_dir()
    assert list(review_root.iterdir()) == []
    assert list(tmp_path.glob(".raced-review.staging-*")) == []


def test_aggregation_rejects_swapped_summary_identity_before_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)
    first, second = sorted(EXPECTED_METHODS)[:2]
    first_directory = run_directory(
        raw_root,
        phase="full",
        task=EXPECTED_TASKS[0],
        method=first,
        seed=100,
    )
    second_directory = run_directory(
        raw_root,
        phase="full",
        task=EXPECTED_TASKS[0],
        method=second,
        seed=100,
    )
    first_summary = (first_directory / "summary.json").read_bytes()
    first_sidecar = (first_directory / "summary.json.sha256").read_bytes()
    second_summary = (second_directory / "summary.json").read_bytes()
    second_sidecar = (second_directory / "summary.json.sha256").read_bytes()
    (first_directory / "summary.json").write_bytes(second_summary)
    (first_directory / "summary.json.sha256").write_bytes(second_sidecar)
    (second_directory / "summary.json").write_bytes(first_summary)
    (second_directory / "summary.json.sha256").write_bytes(first_sidecar)

    def metrics_must_not_run(*_args: object, **_kwargs: object) -> dict[str, object]:
        pytest.fail("metrics ran before summary identity validation")

    monkeypatch.setattr(aggregate_module, "_run_metrics", metrics_must_not_run)
    with pytest.raises(AggregateError, match="summary method mismatch"):
        aggregate_profile(
            config_path=CONFIG,
            profile="full",
            raw_root=raw_root,
            output_path=tmp_path / "aggregate.json",
        )


def _rewrite_fixture_rounds(
    raw_root: Path,
    *,
    task: str,
    method: str,
    mutate: Any,
) -> None:
    directory = run_directory(
        raw_root, phase="full", task=task, method=method, seed=100
    )
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (directory / "rounds.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    mutate(records)
    _rewrite_run_fixture(
        directory,
        manifest=manifest,
        rounds=records,
        summary=summary,
    )


def _rewrite_fixture_manifest(
    raw_root: Path,
    *,
    task: str,
    method: str,
    mutate: Any,
) -> None:
    directory = run_directory(
        raw_root, phase="full", task=task, method=method, seed=100
    )
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (directory / "rounds.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    mutate(manifest)
    _rewrite_run_fixture(
        directory,
        manifest=manifest,
        rounds=records,
        summary=summary,
    )


def test_aggregation_rejects_mutated_embedded_resolved_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_root, config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)

    def mutate(manifest: dict[str, Any]) -> None:
        manifest["resolved_config"]["rounds"] = 999
        assert manifest["config_digest"] == config_digest(config)

    _rewrite_fixture_manifest(
        raw_root,
        task=EXPECTED_TASKS[0],
        method=EXPECTED_METHODS[0],
        mutate=mutate,
    )
    with pytest.raises(AggregateError, match="resolved_config differs"):
        aggregate_profile(
            config_path=CONFIG,
            profile="full",
            raw_root=raw_root,
            output_path=tmp_path / "aggregate.json",
        )


@pytest.mark.parametrize("invalid", [None, "ABC", "0" * 63])
def test_aggregation_rejects_invalid_stream_component_digests_across_methods(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: object
) -> None:
    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)
    task = EXPECTED_TASKS[1]
    for method in EXPECTED_METHODS:
        _rewrite_fixture_manifest(
            raw_root,
            task=task,
            method=method,
            mutate=lambda manifest: manifest["exogenous_stream_identity"].update(
                {
                    field: invalid
                    for field in manifest["exogenous_stream_identity"]
                    if field != "misspecification"
                }
            ),
        )
    with pytest.raises(AggregateError, match="must be a lowercase SHA-256"):
        aggregate_profile(
            config_path=CONFIG,
            profile="full",
            raw_root=raw_root,
            output_path=tmp_path / "aggregate.json",
        )


def test_aggregation_rejects_malformed_controlled_misspecification_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)
    for method in EXPECTED_METHODS:
        _rewrite_fixture_manifest(
            raw_root,
            task=EXPECTED_TASKS[2],
            method=method,
            mutate=lambda manifest: manifest["exogenous_stream_identity"].__setitem__(
                "misspecification", "not-a-digest"
            ),
        )
    with pytest.raises(AggregateError, match="misspecification identity.*SHA-256"):
        aggregate_profile(
            config_path=CONFIG,
            profile="full",
            raw_root=raw_root,
            output_path=tmp_path / "aggregate.json",
        )


def test_aggregation_rejects_invalid_stream_digest_even_when_redundant_fields_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)

    def invalidate(manifest: dict[str, Any]) -> None:
        manifest["stream_digest"] = "invalid"
        manifest["exogenous_stream_identity"]["stream"] = "invalid"

    for method in EXPECTED_METHODS:
        _rewrite_fixture_manifest(
            raw_root, task=EXPECTED_TASKS[1], method=method, mutate=invalidate
        )
    with pytest.raises(AggregateError, match="stream identity.*SHA-256"):
        aggregate_profile(
            config_path=CONFIG,
            profile="full",
            raw_root=raw_root,
            output_path=tmp_path / "aggregate.json",
        )


@pytest.mark.parametrize(
    ("field", "producer"),
    [
        (
            "prepared_data",
            lambda manifest: manifest["prepared_data"].__setitem__(
                "semantic_digest", "0" * 64
            ),
        ),
        (
            "preprocessing",
            lambda manifest: manifest.__setitem__("preprocessing_digest", "0" * 64),
        ),
        ("split", lambda manifest: manifest["split"].__setitem__("digest", "0" * 64)),
        ("teacher", lambda manifest: manifest.__setitem__("teacher_digest", "0" * 64)),
        (
            "misspecification",
            lambda manifest: manifest.__setitem__(
                "misspecification_function_digest", "0" * 64
            ),
        ),
        ("stream", lambda manifest: manifest.__setitem__("stream_digest", "0" * 64)),
    ],
)
def test_aggregation_rejects_each_redundant_manifest_identity_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    producer: Any,
) -> None:
    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)
    task = EXPECTED_TASKS[2] if field == "misspecification" else EXPECTED_TASKS[1]
    cells = (
        [
            (cell_task, method)
            for cell_task in EXPECTED_TASKS
            for method in EXPECTED_METHODS
        ]
        if field in {"prepared_data", "preprocessing", "split"}
        else [(task, EXPECTED_METHODS[0])]
    )
    for cell_task, method in cells:
        _rewrite_fixture_manifest(
            raw_root,
            task=cell_task,
            method=method,
            mutate=producer,
        )
    with pytest.raises(AggregateError, match=rf"exogenous {field} identity"):
        aggregate_profile(
            config_path=CONFIG,
            profile="full",
            raw_root=raw_root,
            output_path=tmp_path / "aggregate.json",
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda records: records[0].__setitem__("deterministic_failure", True),
            "failure status disagrees",
        ),
        (
            lambda records: records[0].__setitem__(
                "deterministic_failure_reasons", ["invented_failure"]
            ),
            "failure reasons disagree",
        ),
        (
            lambda records: records[0].__setitem__("float64_diagnostic_pass", False),
            "float64 diagnostic status disagrees",
        ),
        (
            lambda records: records[0].__setitem__(
                "instantaneous_theorem_bound_status", "premise_false"
            ),
            "instantaneous theorem status disagrees",
        ),
        (
            lambda records: records[0].__setitem__(
                "theorem_bound_comparison_tolerance", 1.0
            ),
            "wrong theorem comparison tolerance",
        ),
    ],
)
def test_aggregation_rederives_semantic_statuses_from_primitives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: Any,
    message: str,
) -> None:
    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)
    _rewrite_fixture_rounds(
        raw_root,
        task=EXPECTED_TASKS[1],
        method="transport_exact_corrected_cholesky",
        mutate=mutation,
    )
    with pytest.raises(AggregateError, match=message):
        aggregate_profile(
            config_path=CONFIG,
            profile="full",
            raw_root=raw_root,
            output_path=tmp_path / "aggregate.json",
        )


@pytest.mark.parametrize(
    ("task", "field", "replacement", "message"),
    [
        (
            EXPECTED_TASKS[1],
            "instantaneous_theorem_rhs",
            None,
            "theorem-applicable round lacks finite theorem RHS",
        ),
        (
            EXPECTED_TASKS[1],
            "sharp_theorem_rhs",
            None,
            "theorem-applicable round lacks finite theorem RHS",
        ),
        (
            EXPECTED_TASKS[0],
            "instantaneous_theorem_rhs",
            1.0,
            "theorem-inapplicable round records theorem RHS",
        ),
        (
            EXPECTED_TASKS[0],
            "sharp_theorem_rhs",
            1.0,
            "theorem-inapplicable round records theorem RHS",
        ),
    ],
)
def test_aggregation_rejects_missing_or_inapplicable_theorem_rhs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    task: str,
    field: str,
    replacement: object,
    message: str,
) -> None:
    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)
    _rewrite_fixture_rounds(
        raw_root,
        task=task,
        method="transport_exact_corrected_cholesky",
        mutate=lambda records: records[0].__setitem__(field, replacement),
    )
    with pytest.raises(AggregateError, match=message):
        aggregate_profile(
            config_path=CONFIG,
            profile="full",
            raw_root=raw_root,
            output_path=tmp_path / "aggregate.json",
        )


def test_aggregation_requires_theorem_rhs_even_when_confidence_premise_is_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)

    def remove_rhs_under_false_premise(records: list[dict[str, Any]]) -> None:
        records[0]["reference_confidence_all_actions"] = False
        records[0]["prefix_simultaneous_reference_confidence"] = False
        records[0]["instantaneous_theorem_rhs"] = None
        records[0]["sharp_theorem_rhs"] = None
        records[0]["instantaneous_theorem_bound_status"] = "premise_false"
        records[0]["cumulative_theorem_bound_status"] = "premise_false"
        for record in records[1:]:
            record["prefix_simultaneous_reference_confidence"] = False
            record["cumulative_theorem_bound_status"] = "premise_false"

    _rewrite_fixture_rounds(
        raw_root,
        task=EXPECTED_TASKS[1],
        method="transport_exact_corrected_cholesky",
        mutate=remove_rhs_under_false_premise,
    )
    with pytest.raises(AggregateError, match="theorem-applicable round lacks finite"):
        aggregate_profile(
            config_path=CONFIG,
            profile="full",
            raw_root=raw_root,
            output_path=tmp_path / "aggregate.json",
        )


def test_valid_deterministic_failure_is_preserved_by_aggregation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)

    def record_solver_failure(records: list[dict[str, Any]]) -> None:
        records[0]["solver_all_actions_converged"] = False
        records[0]["deterministic_failure_reasons"] = ["solver_nonconvergence"]
        records[0]["deterministic_failure"] = True
        records[0]["float64_diagnostic_pass"] = False

    _rewrite_fixture_rounds(
        raw_root,
        task=EXPECTED_TASKS[1],
        method="transport_exact_corrected_cg_1e-4",
        mutate=record_solver_failure,
    )
    aggregate = aggregate_profile(
        config_path=CONFIG,
        profile="full",
        raw_root=raw_root,
        output_path=tmp_path / "aggregate.json",
    )
    assert aggregate["semantic_status"]["deterministic_failure_count"] == 1
    assert aggregate["publication_evidence"] is False


@pytest.mark.parametrize(
    ("failure", "task", "reason"),
    [
        (
            "taylor",
            REALIZABLE_TASK,
            "current_taylor_envelope_violation",
        ),
        (
            "misspecification",
            CONTROLLED_MISSPECIFIED_TASK,
            "current_misspecification_envelope_violation",
        ),
    ],
)
def test_production_envelope_failures_complete_and_remain_scoped_in_aggregate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    task: str,
    reason: str,
) -> None:
    environment, stream = _envelope_test_trajectory(
        task=task,
        current_misspecification=(0.0 if failure == "misspecification" else 0.025),
    )
    if failure == "taylor":
        monkeypatch.setattr(
            benchmark_module,
            "linearization_envelope",
            lambda *_args, **_kwargs: 0.0,
        )
    result = run_policy_trajectory(
        environment,
        stream,
        "transport_exact_corrected_cholesky",
        BenchmarkSettings(
            optimizer=OptimizerSpec(learning_rate=1e-4, steps_per_round=1),
            prefixes=(1, 3),
            diagnostic_checkpoints=(1, 3),
        ),
    )
    failed_rounds = [
        record
        for record in result.rounds
        if reason in record["deterministic_failure_reasons"]
    ]
    assert failed_rounds
    assert all(record["deterministic_failure"] is True for record in failed_rounds)
    assert all(record["float64_diagnostic_pass"] is False for record in failed_rounds)

    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)
    directory = run_directory(
        raw_root,
        phase="full",
        task=task,
        method="transport_exact_corrected_cholesky",
        seed=100,
    )
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    summary.update(result.summary)
    summary.update(
        {
            "status": "completed",
            "profile": "full",
            "phase": "evaluation",
            "publication_evidence": False,
        }
    )
    _rewrite_run_fixture(
        directory,
        manifest=manifest,
        rounds=result.rounds,
        summary=summary,
    )
    aggregate = aggregate_profile(
        config_path=CONFIG,
        profile="full",
        raw_root=raw_root,
        output_path=tmp_path / "aggregate.json",
    )
    events = aggregate["semantic_status"]["deterministic_failure_events"]
    assert any(
        event["task"] == task
        and event["method"] == "transport_exact_corrected_cholesky"
        and event["seed"] == 100
        and reason in event["reasons"]
        for event in events
    )
    assert aggregate["publication_evidence"] is False


def _ratio_mutation(records: list[dict[str, Any]], name: str) -> None:
    if name == "finite_omitted":
        records[0]["solver_upper_over_exact_A_denominator_omitted"] = True
    elif name == "null_not_omitted":
        records[0]["solver_upper_over_exact_A"] = None
    elif name == "legacy_alias":
        records[0]["solver_upper_over_exact"] = 1.3
    elif name == "selected_scalar":
        records[0]["solver_upper_over_exact_A_all_actions"][0] = 1.3
        records[0]["solver_upper_over_exact_all_actions"][0] = 1.3
    elif name == "operational_product":
        records[0]["operational_upper_width_over_exact_V_width"] = 0.7
    elif name == "outside_checkpoint":
        records[1]["exact_A_width_over_exact_V_width"] = 0.5
        records[1]["exact_A_width_over_exact_V_width_denominator_omitted"] = False
    elif name == "off_checkpoint_exact_a_family":
        records[1].update(
            {
                "solver_exact_width": 1.0,
                "solver_upper_over_exact": 1.2,
                "solver_upper_over_exact_A": 1.2,
                "solver_upper_over_exact_A_denominator_omitted": False,
                "solver_exact_widths_all_actions": [1.0, 2.0],
                "solver_upper_over_exact_all_actions": [1.2, 1.2],
                "solver_upper_over_exact_A_all_actions": [1.2, 1.2],
                "solver_upper_over_exact_A_denominator_omitted_all_actions": [
                    False,
                    False,
                ],
            }
        )
    elif name == "off_checkpoint_exact_v_arrays":
        records[1]["current_exact_widths"] = [2.0, 4.0]
        records[1]["current_widths"] = [2.0, 4.0]
    elif name == "checkpoint_missing_scalar":
        records[0]["solver_exact_width"] = None
    elif name == "checkpoint_missing_vector":
        records[0]["solver_exact_widths_all_actions"] = None
    elif name == "checkpoint_missing_exact_v":
        records[0]["current_exact_widths"] = None
        records[0]["current_widths"] = None
    elif name == "exact_zero_rule":
        records[0]["solver_exact_width"] = 0.0
    else:  # pragma: no cover - protects the test table itself
        raise AssertionError(name)


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("finite_omitted", "finite solver_upper_over_exact_A"),
        ("null_not_omitted", "null solver_upper_over_exact_A"),
        ("legacy_alias", "legacy solver ratio alias"),
        ("selected_scalar", "selected solver_upper_over_exact_A"),
        ("operational_product", "inconsistent operational_upper"),
        ("outside_checkpoint", "outside a dense checkpoint"),
        ("off_checkpoint_exact_a_family", "outside a dense checkpoint"),
        ("off_checkpoint_exact_v_arrays", "exact-V diagnostic.*outside"),
        ("checkpoint_missing_scalar", "lacks the selected exact-A width"),
        ("checkpoint_missing_vector", "lacks all-action width primitives"),
        ("checkpoint_missing_exact_v", "lacks exact V widths"),
        ("exact_zero_rule", "exact-zero denominator rule"),
    ],
)
def test_aggregation_rejects_invalid_ratio_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    message: str,
) -> None:
    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)
    _rewrite_fixture_rounds(
        raw_root,
        task=EXPECTED_TASKS[1],
        method="transport_exact_corrected_cg_1e-4",
        mutate=lambda records: _ratio_mutation(records, name),
    )
    with pytest.raises(AggregateError, match=message):
        aggregate_profile(
            config_path=CONFIG,
            profile="full",
            raw_root=raw_root,
            output_path=tmp_path / "aggregate.json",
        )


def test_aggregation_accepts_operational_exact_v_widths_on_current_exact_cholesky(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)
    aggregate = aggregate_profile(
        config_path=CONFIG,
        profile="full",
        raw_root=raw_root,
        output_path=tmp_path / "aggregate.json",
    )
    assert aggregate["accepted_cell_count"] == len(EXPECTED_TASKS) * len(
        EXPECTED_METHODS
    )


@pytest.mark.parametrize(
    ("method", "mutation", "message"),
    (
        (
            "transport_exact_corrected_cholesky",
            "missing",
            "lacks operational exact V widths",
        ),
        (
            "transport_exact_corrected_cholesky",
            "alias",
            "inconsistent current-width aliases",
        ),
        (
            "transport_exact_corrected_cholesky",
            "score_mismatch",
            "differ from score_widths",
        ),
        (
            "frozen_reference_corrected_cholesky",
            "injected",
            "non-current-exact record",
        ),
    ),
)
def test_aggregation_enforces_method_dependent_exact_v_widths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    mutation: str,
    message: str,
) -> None:
    raw_root, _config, _policy = _write_full_shaped_fixture_raw(tmp_path, monkeypatch)

    def mutate(records: list[dict[str, Any]]) -> None:
        if mutation == "missing":
            records[1]["current_exact_widths"] = None
            records[1]["current_widths"] = None
        elif mutation == "alias":
            records[1]["current_widths"] = [2.0, 5.0]
        elif mutation == "score_mismatch":
            records[1]["current_exact_widths"] = [2.0, 5.0]
            records[1]["current_widths"] = [2.0, 5.0]
        else:
            records[0]["current_exact_widths"] = [2.0, 4.0]
            records[0]["current_widths"] = [2.0, 4.0]

    _rewrite_fixture_rounds(
        raw_root,
        task=EXPECTED_TASKS[1],
        method=method,
        mutate=mutate,
    )
    with pytest.raises(AggregateError, match=message):
        aggregate_profile(
            config_path=CONFIG,
            profile="full",
            raw_root=raw_root,
            output_path=tmp_path / "aggregate.json",
        )


def test_resource_fallback_is_never_publication_evidence() -> None:
    assert not publication_eligibility(
        profile="resource_fallback",
        phase="evaluation",
        evidence_role="pilot_only_non_publication",
        prepared_data={
            "dataset_name": "sklearn_covtype",
            "smoke_only": False,
            "fixture_only": False,
            "publication_evidence": False,
        },
        data_authorized=True,
        selection_authorized=True,
        deterministic_failure_count=0,
    )
