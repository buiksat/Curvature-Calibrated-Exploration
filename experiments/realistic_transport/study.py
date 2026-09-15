"""Study orchestration for the preregistered realistic transport benchmark."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import multiprocessing
import os
import resource
import threading
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .benchmark import (
    BenchmarkSettings,
    OptimizerSpec,
    run_policy_trajectory,
    run_tuning_trajectory,
)
from .configuration import (
    config_digest,
    EXPECTED_METHODS,
    EXPECTED_TASKS,
    load_config,
    scientific_config_digest,
    validate_profile_request,
)
from .data import load_prepared_dataset
from .environment import build_stream, build_task_environment
from .integrity import (
    authenticate_prepared_data,
    IntegrityError,
    validate_selection_policy,
    verify_clean_freeze,
    verify_derived_data_identities,
    verify_selection_lock,
)
from .io import (
    refuse_existing_run_outputs,
    run_directory,
    utc_timestamp,
    write_failure,
    write_run,
)
from .preprocessing import deterministic_split, fit_preprocessing
from .provenance import (
    enforced_numerical_threads,
    input_set_sha256,
    runtime_metadata,
    sha256_file,
    source_inventory,
)


class StudyError(RuntimeError):
    """Raised when a locked study condition is not satisfied."""


class PeakRSSSampler:
    """Sample process RSS during one policy trajectory."""

    def __init__(self, interval_seconds: float = 0.01) -> None:
        self._interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._process: Any = None
        self.start_bytes = 0
        self.peak_bytes = 0
        self.backend = "resource_ru_maxrss"

    def _sample(self) -> None:
        assert self._process is not None
        while not self._stop.wait(self._interval_seconds):
            self.peak_bytes = max(self.peak_bytes, int(self._process.memory_info().rss))

    def __enter__(self) -> "PeakRSSSampler":
        try:
            import psutil

            self._process = psutil.Process(os.getpid())
            self.start_bytes = int(self._process.memory_info().rss)
            self.peak_bytes = self.start_bytes
            self.backend = "psutil_rss_sampler"
            self._thread = threading.Thread(target=self._sample, daemon=True)
            self._thread.start()
        except (ImportError, OSError):
            # ru_maxrss is a process-lifetime high-water mark. It is less precise,
            # but preserves a portable measurement when psutil is unavailable.
            self._process = None
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._process is not None:
            try:
                self.peak_bytes = max(
                    self.peak_bytes, int(self._process.memory_info().rss)
                )
            except OSError:
                pass
        peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        self.peak_bytes = max(self.peak_bytes, peak * 1024)

    def metadata(self) -> dict[str, Any]:
        return {
            "metric": "fresh_process_peak_resident_set_size_bytes",
            "backend": (
                "psutil_rss_sampler_plus_process_ru_maxrss"
                if self._process is not None
                else self.backend
            ),
            "start_rss_bytes": self.start_bytes,
            "peak_rss_bytes": self.peak_bytes,
            "includes": [
                "interpreter_startup",
                "deserialized_dataset_and_environment",
                "model_optimizer_and_replay_state",
                "operational_computation",
                "checkpoint_diagnostics",
            ],
            "includes_startup_and_deserialization_peak": True,
            "isolation": "one_fresh_spawned_process_per_cell",
        }


def _isolated_policy_worker(
    environment: Any,
    stream: Any,
    method: str,
    settings: BenchmarkSettings,
    blas_threads: int,
) -> dict[str, Any]:
    """Execute exactly one cell in a fresh spawned process."""

    started_at = utc_timestamp()
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    with enforced_numerical_threads(blas_threads) as thread_control:
        with PeakRSSSampler() as memory:
            result = run_policy_trajectory(environment, stream, method, settings)
    return {
        "result": result,
        "started_at": started_at,
        "ended_at": utc_timestamp(),
        "wall_seconds": time.perf_counter() - wall_started,
        "cpu_seconds": time.process_time() - cpu_started,
        "memory": memory.metadata(),
        "runtime": runtime_metadata(
            workers=1,
            blas_threads=blas_threads,
            thread_control=thread_control,
        ),
        "process_id": os.getpid(),
    }


def run_isolated_policy_trajectory(
    environment: Any,
    stream: Any,
    method: str,
    settings: BenchmarkSettings,
    *,
    blas_threads: int,
) -> dict[str, Any]:
    """Run one cell in a process that is never reused by another cell."""

    context = multiprocessing.get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=1,
        mp_context=context,
        max_tasks_per_child=1,
    ) as executor:
        return executor.submit(
            _isolated_policy_worker,
            environment,
            stream,
            method,
            settings,
            blas_threads,
        ).result()


def _isolated_tuning_worker(
    environment: Any,
    stream: Any,
    optimizer: OptimizerSpec,
    parameters: Mapping[str, Any],
    blas_threads: int,
) -> dict[str, Any]:
    with enforced_numerical_threads(blas_threads) as thread_control:
        with PeakRSSSampler() as memory:
            result = run_tuning_trajectory(
                environment,
                stream,
                optimizer,
                ridge=float(parameters["ridge"]),
                training_ridge=float(parameters["training_ridge"]),
                theta_radius=float(parameters["theta_radius"]),
                burn_in=int(parameters["burn_in"]),
            )
    return {
        "result": result,
        "memory": memory.metadata(),
        "thread_control": thread_control,
        "runtime": runtime_metadata(
            workers=1,
            blas_threads=blas_threads,
            thread_control=thread_control,
        ),
        "process_id": os.getpid(),
    }


def run_isolated_tuning_trajectory(
    environment: Any,
    stream: Any,
    optimizer: OptimizerSpec,
    *,
    ridge: float,
    training_ridge: float,
    theta_radius: float,
    burn_in: int,
    blas_threads: int,
) -> dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    parameters = {
        "ridge": ridge,
        "training_ridge": training_ridge,
        "theta_radius": theta_radius,
        "burn_in": burn_in,
    }
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=1,
        mp_context=context,
        max_tasks_per_child=1,
    ) as executor:
        return executor.submit(
            _isolated_tuning_worker,
            environment,
            stream,
            optimizer,
            parameters,
            blas_threads,
        ).result()


def _selection(
    path: str | Path | None,
    *,
    freeze_revision: str | None,
    selection_lock_revision: str | None,
    repository_root: str | Path,
) -> tuple[dict[str, Any] | None, str | None]:
    if path is None:
        return None, None
    if freeze_revision is None or selection_lock_revision is None:
        raise StudyError("selection verification requires explicit F and L")
    try:
        return verify_selection_lock(
            selection_path=path,
            freeze_revision=freeze_revision,
            selection_lock_revision=selection_lock_revision,
            repo_root=repository_root,
        )
    except IntegrityError as error:
        raise StudyError(f"selection-lock verification failed: {error}") from error


def _optimizer_for_task(
    config: Mapping[str, Any],
    task: str,
    selection: Mapping[str, Any] | None,
) -> OptimizerSpec:
    if selection is None:
        raw = config["representation_update"]["development_optimizer"]
    else:
        optimizer = selection.get("optimizer")
        if not isinstance(optimizer, Mapping):
            raise StudyError("selection artifact lacks optimizer selections")
        key = "label" if task == "covtype_label_bandit" else "controlled_shared"
        raw = optimizer.get(key)
        if not isinstance(raw, Mapping):
            raise StudyError(f"selection artifact lacks optimizer.{key}")
    return OptimizerSpec.from_mapping(raw)


def _linucb_alpha_for_task(task: str, selection: Mapping[str, Any] | None) -> float:
    if selection is None:
        return 1.0
    values = selection.get("linucb_alpha")
    if not isinstance(values, Mapping) or task not in values:
        raise StudyError(f"selection artifact lacks LinUCB alpha for {task}")
    return float(values[task])


def _common_manifest(
    *,
    config: Mapping[str, Any],
    prepared: Any,
    split: Any,
    transform: Any,
    environment: Any,
    stream: Any,
    profile: str,
    phase: str,
    task: str,
    method: str,
    seed: int,
    selection_digest: str | None,
    selection: Mapping[str, Any] | None,
    split_class_counts: Mapping[str, Any],
    dataset_mode: str,
    evidence_role: str,
    seed_set_identity: str,
    data_authentication: Mapping[str, Any],
    frozen_source_inventory: Sequence[Mapping[str, str]],
    freeze_revision: str | None,
    selection_lock_revision: str | None,
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    inventory = [dict(item) for item in frozen_source_inventory]
    misspecification_digest = (
        environment.misspecification.digest
        if environment.misspecification is not None
        else None
    )
    git = runtime["git"]
    return {
        "schema_version": 1,
        "protocol_version": config["protocol_version"],
        "profile": profile,
        "phase": phase,
        "dataset_mode": dataset_mode,
        "evidence_role": evidence_role,
        "publication_evidence": False,
        "seed_set_identity": seed_set_identity,
        "task": task,
        "method": method,
        "base_seed": int(seed),
        "rounds": int(stream.rounds),
        "config_digest": config_digest(config),
        "scientific_config_digest": scientific_config_digest(config),
        "resolved_config": dict(config),
        "prepared_data": {
            "dataset_name": prepared.dataset_name,
            "semantic_digest": prepared.content_digest,
            "artifact_sha256": prepared.artifact_sha256,
            "manifest_sha256": data_authentication["manifest_sha256"],
            "smoke_only": prepared.manifest["smoke_only"],
            "row_count": prepared.row_count,
            "source_feature_dimension": prepared.source_feature_dimension,
            "class_count": prepared.action_count,
            "original_classes": list(prepared.manifest.get("original_classes", [])),
            "loader": dict(prepared.manifest.get("loader", {})),
            "runtime_provenance": dict(prepared.manifest.get("runtime_provenance", {})),
            "source_cache_files": list(prepared.manifest.get("source_cache_files", [])),
            "fixture_only": prepared.manifest["fixture_only"],
            "publication_evidence": prepared.manifest["publication_evidence"],
        },
        "data_authentication": dict(data_authentication),
        "split": {
            "digest": split.digest,
            "counts": {
                "development": int(split.development.size),
                "tuning": int(split.tuning.size),
                "evaluation": int(split.evaluation.size),
            },
            "class_counts": dict(split_class_counts),
        },
        "preprocessing_digest": transform.digest,
        "preprocessing_artifact": {
            "mean": transform.mean.tolist(),
            "scale": transform.scale.tolist(),
            "zero_variance_coordinates": np.flatnonzero(transform.zero_variance)
            .astype(int)
            .tolist(),
            "projection": transform.projection.tolist(),
            "eigenvalues": transform.eigenvalues.tolist(),
            "sign_anchors": transform.sign_anchors.astype(int).tolist(),
            "covariance_divisor": int(transform.covariance_divisor),
        },
        "teacher_digest": environment.teacher.digest,
        "misspecification_function_digest": misspecification_digest,
        "stream_digest": stream.digest,
        "exogenous_stream_identity": {
            **stream.component_digests,
            "stream": stream.digest,
            "teacher": environment.teacher.digest,
            "misspecification": misspecification_digest,
            "prepared_data": prepared.content_digest,
            "preprocessing": transform.digest,
            "split": split.digest,
        },
        "source_inventory": inventory,
        "source_inventory_sha256": input_set_sha256(inventory),
        "source_branch": git["branch"],
        "source_revision": git["revision"],
        # Production authorization checks only the scientific-source scope.
        # Raw outputs are intentionally outside that scope and make the broad
        # Git worktree dirty after the first completed cell.
        "source_dirty": False if freeze_revision is not None else git["dirty"],
        "worktree_dirty_outside_scientific_scope_allowed": git["dirty"],
        "selection_artifact_sha256": selection_digest,
        "freeze_revision": freeze_revision,
        "selection_lock_revision": selection_lock_revision,
        "evaluation_state_revision": runtime["git"]["revision"],
        "runtime": dict(runtime),
        "status": "running",
    }


def run_profile(
    *,
    config_path: str | Path,
    profile: str,
    prepared_artifact: str | Path,
    output_root: str | Path | None = None,
    selection_path: str | Path | None = None,
    data_lock_path: str | Path | None = None,
    freeze_revision: str | None = None,
    selection_lock_revision: str | None = None,
    phase: str | None = None,
    methods: Sequence[str] = EXPECTED_METHODS,
    tasks: Sequence[str] = EXPECTED_TASKS,
    seeds: Sequence[int] | None = None,
    continue_on_failure: bool = False,
    repository_root: str | Path = Path(__file__).resolve().parents[2],
) -> dict[str, Any]:
    """Run a complete profile grid and preserve each cell independently."""

    config = load_config(config_path, profile)
    selected_methods = tuple(methods)
    if not selected_methods or len(selected_methods) != len(set(selected_methods)):
        raise StudyError("methods must be a nonempty unique sequence")
    unknown = sorted(set(selected_methods) - set(EXPECTED_METHODS))
    if unknown:
        raise StudyError(f"unknown methods: {unknown}")
    selected_tasks = tuple(tasks)
    if not selected_tasks or len(selected_tasks) != len(set(selected_tasks)):
        raise StudyError("tasks must be a nonempty unique sequence")
    unknown_tasks = sorted(set(selected_tasks) - set(EXPECTED_TASKS))
    if unknown_tasks:
        raise StudyError(f"unknown tasks: {unknown_tasks}")
    try:
        policy = validate_profile_request(
            config,
            profile,
            phase=phase,
            methods=selected_methods,
            tasks=selected_tasks,
            seeds=seeds,
        )
    except ValueError as error:
        raise StudyError(str(error)) from error
    selected_phase = policy.phase
    selected_seeds = (
        tuple(int(value) for value in seeds) if seeds is not None else policy.seeds
    )
    if not selected_seeds or len(selected_seeds) != len(set(selected_seeds)):
        raise StudyError("seeds must be nonempty and unique")
    rounds = policy.rounds
    if policy.requires_selection_lock and selection_path is None:
        raise StudyError(f"profile {profile!r} requires a locked selection artifact")

    root = Path(output_root or config["execution"]["raw_root"])
    for task in selected_tasks:
        for seed in selected_seeds:
            for method in selected_methods:
                refuse_existing_run_outputs(
                    run_directory(
                        root,
                        phase=profile,
                        task=task,
                        method=method,
                        seed=seed,
                    )
                )

    load_started = time.perf_counter()
    blas_threads = int(config["execution"]["blas_threads_per_worker"])
    if policy.requires_data_lock:
        try:
            prepared, data_lock = authenticate_prepared_data(
                config=config,
                config_path=config_path,
                prepared_artifact=prepared_artifact,
                data_lock_path=data_lock_path,
                freeze_revision=freeze_revision,
                repo_root=repository_root,
            )
            assert freeze_revision is not None
            frozen_inventory = verify_clean_freeze(
                freeze_revision,
                repo_root=repository_root,
                require_head=profile in {"covtype_pilot", "tuning"},
            )
        except (IntegrityError, OSError) as error:
            raise StudyError(f"data-lock verification failed: {error}") from error
        data_authentication = {
            "status": "verified_against_committed_freeze_lock",
            "freeze_revision": freeze_revision,
            "data_lock_path": str(config["dataset"]["approved_data_lock"]["path"]),
            "data_lock_sha256": sha256_file(data_lock_path),
            "manifest_sha256": data_lock["manifest_sha256"],
        }
    else:
        prepared = load_prepared_dataset(prepared_artifact)
        data_lock = None
        frozen_inventory = source_inventory()
        data_authentication = {
            "status": "smoke_only_not_approved",
            "freeze_revision": None,
            "data_lock_path": None,
            "data_lock_sha256": None,
            "manifest_sha256": sha256_file(
                Path(prepared_artifact).with_suffix(
                    Path(prepared_artifact).suffix + ".manifest.json"
                )
            ),
        }
    data_loading_seconds = time.perf_counter() - load_started
    if policy.dataset_mode == "covtype" and prepared.manifest.get("smoke_only"):
        raise StudyError("a smoke-only dataset cannot be used for a Covertype profile")
    if policy.dataset_mode == "covtype" and prepared.manifest.get("fixture_only"):
        raise StudyError("fixture-only data cannot be used for a Covertype profile")
    if policy.dataset_mode == "digits_smoke" and not prepared.manifest.get(
        "smoke_only"
    ):
        raise StudyError("the smoke profile requires the explicit smoke artifact")

    split_started = time.perf_counter()
    with enforced_numerical_threads(blas_threads):
        split = deterministic_split(
            prepared.row_count,
            prepared.content_digest,
            namespace=str(config["dataset"]["split_namespace"]),
        )
        transform = fit_preprocessing(
            prepared.features,
            split.development,
            prepared_data_digest=prepared.content_digest,
            rank=int(config["preprocessing"]["projection_dimension"]),
        )
    preprocessing_seconds = time.perf_counter() - split_started
    if data_lock is not None:
        try:
            verify_derived_data_identities(
                data_lock,
                split_digest=split.digest,
                preprocessing_digest=transform.digest,
            )
        except IntegrityError as error:
            raise StudyError(f"data-lock verification failed: {error}") from error
    selection, selection_digest = _selection(
        selection_path,
        freeze_revision=freeze_revision,
        selection_lock_revision=selection_lock_revision,
        repository_root=repository_root,
    )
    if selection is not None:
        try:
            validate_selection_policy(selection, config)
        except IntegrityError as error:
            raise StudyError(f"selection policy is invalid: {error}") from error
        if selection.get("prepared_data_digest") != prepared.content_digest:
            raise StudyError("selection artifact is bound to another prepared dataset")
        if selection.get("preprocessing_digest") != transform.digest:
            raise StudyError(
                "selection artifact is bound to another preprocessing transform"
            )
        if selection.get("scientific_config_digest") != scientific_config_digest(
            config
        ):
            raise StudyError(
                "selection artifact is bound to another scientific configuration"
            )
    transformed = transform.transform(prepared.features)
    preprocessing_summaries = {
        name: transform.summary(transformed[split.phase_indices(name)])
        for name in ("development", "tuning", "evaluation")
    }
    split_class_counts = {}
    for name in ("development", "tuning", "evaluation"):
        indices = split.phase_indices(name)
        counts = np.bincount(
            prepared.labels[indices], minlength=prepared.action_count
        ).astype(int)
        split_class_counts[name] = {
            "counts": counts.tolist(),
            "proportions": (counts / counts.sum()).tolist(),
        }

    completed = 0
    failed = 0
    cell_inventory: list[dict[str, Any]] = []
    for task in selected_tasks:
        environment_started = time.perf_counter()
        with enforced_numerical_threads(blas_threads):
            environment = build_task_environment(
                prepared,
                task,
                config,
                split=split,
                preprocessing=transform,
            )
        environment_seconds = time.perf_counter() - environment_started
        if policy.dataset_mode == "covtype":
            expected_dimension = (
                environment.context_dimension
                + environment.action_count
                + environment.context_dimension * environment.action_count
            )
            if environment.context_dimension != 16 or environment.action_count != 7:
                raise StudyError(
                    "prepared Covertype dimensions do not match the canonical task"
                )
            if environment.feature_dimension != expected_dimension:
                raise StudyError("feature-dimension formula failed")
        optimizer = _optimizer_for_task(config, task, selection)
        linucb_alpha = _linucb_alpha_for_task(task, selection)
        settings = BenchmarkSettings.from_config(
            config, optimizer=optimizer, linucb_alpha=linucb_alpha
        )
        for seed in selected_seeds:
            stream = build_stream(environment, selected_phase, seed, rounds)
            for method in selected_methods:
                directory = run_directory(
                    root, phase=profile, task=task, method=method, seed=seed
                )
                try:
                    execution = run_isolated_policy_trajectory(
                        environment,
                        stream,
                        method,
                        settings,
                        blas_threads=blas_threads,
                    )
                    result = execution["result"]
                    runtime = dict(execution["runtime"])
                    runtime_execution = dict(runtime["execution"])
                    runtime_execution.update(
                        {
                            "requested_workers": int(
                                config.get("workers", config["execution"]["workers"])
                            ),
                            "actual_concurrent_workers": 1,
                            "execution_model": (
                                "sequential_parent_with_fresh_spawned_process_per_cell"
                            ),
                            "worker_pid": int(execution["process_id"]),
                            "memory_measurement": dict(execution["memory"]),
                        }
                    )
                    runtime["execution"] = runtime_execution
                    base_manifest = _common_manifest(
                        config=config,
                        prepared=prepared,
                        split=split,
                        transform=transform,
                        environment=environment,
                        stream=stream,
                        profile=profile,
                        phase=selected_phase,
                        task=task,
                        method=method,
                        seed=seed,
                        selection_digest=selection_digest,
                        selection=selection,
                        split_class_counts=split_class_counts,
                        dataset_mode=policy.dataset_mode,
                        evidence_role=policy.evidence_role,
                        seed_set_identity=policy.seed_set_identity,
                        data_authentication=data_authentication,
                        frozen_source_inventory=frozen_inventory,
                        freeze_revision=freeze_revision,
                        selection_lock_revision=selection_lock_revision,
                        runtime=runtime,
                    )
                    manifest = dict(base_manifest)
                    manifest.update(
                        {
                            "status": "completed",
                            "started_at": execution["started_at"],
                            "ended_at": execution["ended_at"],
                            "optimizer": {
                                "learning_rate": optimizer.learning_rate,
                                "steps_per_round": optimizer.steps_per_round,
                            },
                            "linucb_alpha": linucb_alpha,
                        }
                    )
                    summary = dict(result.summary)
                    summary.update(
                        {
                            "status": "completed",
                            "profile": profile,
                            "phase": selected_phase,
                            "publication_evidence": False,
                            "data_loading_seconds": data_loading_seconds,
                            "preprocessing_seconds": preprocessing_seconds,
                            "teacher_environment_seconds": environment_seconds,
                            "policy_execution_wall_seconds": execution["wall_seconds"],
                            "policy_execution_cpu_seconds": execution["cpu_seconds"],
                            "policy_peak_rss_bytes": int(
                                execution["memory"]["peak_rss_bytes"]
                            ),
                            "policy_memory_measurement": dict(execution["memory"]),
                            "preprocessing_summaries": preprocessing_summaries,
                            "prefix_summaries": {
                                str(prefix): value
                                for prefix, value in sorted(
                                    result.prefix_summaries.items()
                                )
                            },
                        }
                    )
                    written = write_run(
                        directory,
                        manifest=manifest,
                        rounds=result.rounds,
                        summary=summary,
                    )
                    cell_inventory.append(
                        {
                            "task": task,
                            "method": method,
                            "seed": seed,
                            "summary_sha256": sha256_file(written["summary"]),
                        }
                    )
                    completed += 1
                except Exception as error:
                    failed += 1
                    write_failure(
                        directory,
                        context={
                            "profile": profile,
                            "phase": selected_phase,
                            "task": task,
                            "method": method,
                            "seed": seed,
                            "config_digest": config_digest(config),
                            "prepared_data_digest": prepared.content_digest,
                        },
                        error=error,
                    )
                    if not continue_on_failure:
                        raise
    if policy.requires_data_lock:
        assert freeze_revision is not None
        try:
            post_execution_inventory = verify_clean_freeze(
                freeze_revision,
                repo_root=repository_root,
                require_head=profile in {"covtype_pilot", "tuning"},
            )
        except IntegrityError as error:
            raise StudyError(
                f"post-execution scientific-freeze verification failed: {error}"
            ) from error
        if post_execution_inventory != frozen_inventory:
            raise StudyError("scientific source inventory changed during execution")
    return {
        "schema_version": 1,
        "profile": profile,
        "phase": selected_phase,
        "evidence_role": policy.evidence_role,
        "seed_set_identity": policy.seed_set_identity,
        "publication_evidence": False,
        "rounds": rounds,
        "expected_cells": len(selected_tasks)
        * len(selected_methods)
        * len(selected_seeds),
        "completed_cells": completed,
        "failed_cells": failed,
        "prepared_data_digest": prepared.content_digest,
        "preprocessing_digest": transform.digest,
        "cell_inventory_sha256": input_set_sha256(
            [
                {
                    "path": f"{item['task']}/{item['method']}/seed-{item['seed']}",
                    "sha256": item["summary_sha256"],
                }
                for item in cell_inventory
            ]
        ),
    }


def _parse_csv_strings(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_csv_ints(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(item) for item in _parse_csv_strings(value))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "seeds must be comma-separated integers"
        ) from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("experiments/configs/realistic_transport_covtype.yaml"),
    )
    parser.add_argument(
        "--profile",
        choices=("smoke", "covtype_pilot", "tuning", "resource_fallback", "full"),
        required=True,
    )
    parser.add_argument("--prepared-artifact", type=Path, required=True)
    parser.add_argument("--data-lock", type=Path, default=None)
    parser.add_argument("--freeze-revision", default=None)
    parser.add_argument("--selection-lock-revision", default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--selection", type=Path, default=None)
    parser.add_argument(
        "--phase", choices=("development", "tuning", "evaluation"), default=None
    )
    parser.add_argument(
        "--methods",
        type=_parse_csv_strings,
        default=EXPECTED_METHODS,
        help="comma-separated method names; defaults to the frozen full grid",
    )
    parser.add_argument(
        "--tasks",
        type=_parse_csv_strings,
        default=EXPECTED_TASKS,
        help="comma-separated task names; defaults to all three tasks",
    )
    parser.add_argument("--seeds", type=_parse_csv_ints, default=None)
    parser.add_argument("--continue-on-failure", action="store_true")
    args = parser.parse_args(argv)
    result = run_profile(
        config_path=args.config,
        profile=args.profile,
        prepared_artifact=args.prepared_artifact,
        output_root=args.output_root,
        selection_path=args.selection,
        data_lock_path=args.data_lock,
        freeze_revision=args.freeze_revision,
        selection_lock_revision=args.selection_lock_revision,
        phase=args.phase,
        methods=args.methods,
        tasks=args.tasks,
        seeds=args.seeds,
        continue_on_failure=args.continue_on_failure,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["failed_cells"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
