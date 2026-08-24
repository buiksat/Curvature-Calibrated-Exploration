"""Study orchestration for the preregistered realistic transport benchmark."""

from __future__ import annotations

import argparse
import json
import os
import resource
import threading
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .benchmark import BenchmarkSettings, OptimizerSpec, run_policy_trajectory
from .configuration import (
    EXPECTED_METHODS,
    EXPECTED_TASKS,
    config_digest,
    load_config,
    seed_set,
)
from .data import load_prepared_dataset
from .environment import build_stream, build_task_environment
from .io import run_directory, utc_timestamp, write_failure, write_run
from .preprocessing import deterministic_split, fit_preprocessing
from .provenance import (
    assert_source_inventory,
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
        self.peak_bytes = 0

    def _sample(self) -> None:
        assert self._process is not None
        while not self._stop.wait(self._interval_seconds):
            self.peak_bytes = max(self.peak_bytes, int(self._process.memory_info().rss))

    def __enter__(self) -> "PeakRSSSampler":
        try:
            import psutil

            self._process = psutil.Process(os.getpid())
            self.peak_bytes = int(self._process.memory_info().rss)
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
                return
            except OSError:
                pass
        peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        self.peak_bytes = max(self.peak_bytes, peak * 1024)


def _selection(path: str | Path | None) -> tuple[dict[str, Any] | None, str | None]:
    if path is None:
        return None, None
    selected_path = Path(path)
    try:
        document = json.loads(selected_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StudyError(f"cannot read selection artifact: {error}") from error
    if not isinstance(document, dict):
        raise StudyError("selection artifact must be a JSON object")
    if document.get("status") != "selected":
        raise StudyError("selection artifact does not contain locked selections")
    inventory = document.get("source_inventory")
    if not isinstance(inventory, list):
        raise StudyError("selection artifact lacks a frozen source inventory")
    assert_source_inventory(inventory)
    return document, sha256_file(selected_path)


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


def _profile_phase(profile: str) -> str:
    if profile in {"smoke", "covtype_pilot"}:
        return "development"
    return "evaluation"


def _profile_seeds(config: Mapping[str, Any], profile: str) -> tuple[int, ...]:
    explicit = config.get("seeds")
    if isinstance(explicit, list):
        return tuple(int(value) for value in explicit)
    if profile == "full":
        return seed_set(config, "evaluation")
    raise StudyError(f"profile {profile!r} does not define its seed list")


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
) -> dict[str, Any]:
    inventory = source_inventory()
    requested_workers = int(config.get("workers", config["execution"]["workers"]))
    runtime = runtime_metadata(
        workers=1,
        blas_threads=int(config["execution"]["blas_threads_per_worker"]),
    )
    runtime["execution"]["requested_workers"] = requested_workers
    runtime["execution"]["execution_model"] = "sequential_cells"
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
        "task": task,
        "method": method,
        "base_seed": int(seed),
        "rounds": int(stream.rounds),
        "config_digest": config_digest(config),
        "resolved_config": dict(config),
        "prepared_data": {
            "dataset_name": prepared.dataset_name,
            "semantic_digest": prepared.content_digest,
            "artifact_sha256": prepared.artifact_sha256,
            "smoke_only": bool(prepared.manifest.get("smoke_only", False)),
            "row_count": prepared.row_count,
            "source_feature_dimension": prepared.source_feature_dimension,
            "class_count": prepared.action_count,
            "original_classes": list(prepared.manifest.get("original_classes", [])),
            "loader": dict(prepared.manifest.get("loader", {})),
            "source_cache_files": list(prepared.manifest.get("source_cache_files", [])),
        },
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
        "source_inventory": inventory,
        "source_inventory_sha256": input_set_sha256(inventory),
        "source_branch": git["branch"],
        "source_revision": git["revision"],
        "source_dirty": git["dirty"],
        "selection_artifact_sha256": selection_digest,
        "freeze_revision": selection.get("freeze_revision") if selection else None,
        "selection_lock_revision": (runtime["git"]["revision"] if selection else None),
        "runtime": runtime,
        "status": "running",
    }


def run_profile(
    *,
    config_path: str | Path,
    profile: str,
    prepared_artifact: str | Path,
    output_root: str | Path | None = None,
    selection_path: str | Path | None = None,
    phase: str | None = None,
    methods: Sequence[str] = EXPECTED_METHODS,
    tasks: Sequence[str] = EXPECTED_TASKS,
    seeds: Sequence[int] | None = None,
    overwrite: bool = False,
    continue_on_failure: bool = False,
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
    selected_phase = phase or _profile_phase(profile)
    if selected_phase not in {"development", "tuning", "evaluation"}:
        raise StudyError(f"invalid phase {selected_phase!r}")
    selected_seeds = (
        tuple(int(value) for value in seeds)
        if seeds is not None
        else _profile_seeds(config, profile)
    )
    if not selected_seeds or len(selected_seeds) != len(set(selected_seeds)):
        raise StudyError("seeds must be nonempty and unique")
    rounds = int(config["rounds"])
    selection, selection_digest = _selection(selection_path)
    if profile in {"full", "resource_fallback"} and selection is None:
        raise StudyError(f"profile {profile!r} requires a locked selection artifact")

    load_started = time.perf_counter()
    required_digest = config["dataset"].get("required_semantic_digest")
    prepared = load_prepared_dataset(
        prepared_artifact,
        required_digest=required_digest,
    )
    data_loading_seconds = time.perf_counter() - load_started
    if config.get("dataset_mode") == "covtype" and prepared.manifest.get("smoke_only"):
        raise StudyError("a smoke-only dataset cannot be used for a Covertype profile")
    if config.get("dataset_mode") == "digits_smoke" and not prepared.manifest.get(
        "smoke_only"
    ):
        raise StudyError("the smoke profile requires the explicit smoke artifact")

    split_started = time.perf_counter()
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
    if selection is not None:
        if selection.get("prepared_data_digest") != prepared.content_digest:
            raise StudyError("selection artifact is bound to another prepared dataset")
        if selection.get("preprocessing_digest") != transform.digest:
            raise StudyError(
                "selection artifact is bound to another preprocessing transform"
            )
        if profile == "full" and selection.get("config_digest") != config_digest(
            config
        ):
            raise StudyError(
                "selection artifact is bound to another full configuration"
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

    root = Path(output_root or config["execution"]["raw_root"])
    completed = 0
    failed = 0
    cell_inventory: list[dict[str, Any]] = []
    for task in selected_tasks:
        environment_started = time.perf_counter()
        environment = build_task_environment(
            prepared,
            task,
            config,
            split=split,
            preprocessing=transform,
        )
        environment_seconds = time.perf_counter() - environment_started
        if config.get("dataset_mode") == "covtype":
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
                )
                started_at = utc_timestamp()
                wall_started = time.perf_counter()
                cpu_started = time.process_time()
                try:
                    with PeakRSSSampler() as memory:
                        result = run_policy_trajectory(
                            environment, stream, method, settings
                        )
                    wall_seconds = time.perf_counter() - wall_started
                    cpu_seconds = time.process_time() - cpu_started
                    manifest = dict(base_manifest)
                    manifest.update(
                        {
                            "status": "completed",
                            "started_at": started_at,
                            "ended_at": utc_timestamp(),
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
                            "data_loading_seconds": data_loading_seconds,
                            "preprocessing_seconds": preprocessing_seconds,
                            "teacher_environment_seconds": environment_seconds,
                            "policy_execution_wall_seconds": wall_seconds,
                            "policy_execution_cpu_seconds": cpu_seconds,
                            "policy_peak_rss_bytes": int(memory.peak_bytes),
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
                        overwrite=overwrite,
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
                        overwrite=overwrite,
                    )
                    if not continue_on_failure:
                        raise
    return {
        "schema_version": 1,
        "profile": profile,
        "phase": selected_phase,
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
        choices=("smoke", "covtype_pilot", "resource_fallback", "full"),
        required=True,
    )
    parser.add_argument("--prepared-artifact", type=Path, required=True)
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
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    args = parser.parse_args(argv)
    result = run_profile(
        config_path=args.config,
        profile=args.profile,
        prepared_artifact=args.prepared_artifact,
        output_root=args.output_root,
        selection_path=args.selection,
        phase=args.phase,
        methods=args.methods,
        tasks=args.tasks,
        seeds=args.seeds,
        overwrite=args.overwrite,
        continue_on_failure=args.continue_on_failure,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["failed_cells"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
