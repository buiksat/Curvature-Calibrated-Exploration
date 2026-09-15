"""Frozen tuning and selection for the realistic transport benchmark."""

from __future__ import annotations

import argparse
import itertools
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .benchmark import BenchmarkSettings, OptimizerSpec
from .configuration import (
    APPROXIMATE_METHODS,
    config_digest,
    EXPECTED_TASKS,
    load_config,
    method_spec,
    profile_policy,
    scientific_config_digest,
)
from .environment import build_stream, build_task_environment
from .integrity import (
    authenticate_prepared_data,
    IntegrityError,
    selection_payload_sha256,
    SELECTION_SCHEMA,
    verify_clean_freeze,
    verify_derived_data_identities,
)
from .preprocessing import deterministic_split, fit_preprocessing
from .provenance import input_set_sha256, sha256_file, write_json
from .study import run_isolated_policy_trajectory, run_isolated_tuning_trajectory


class TuningError(RuntimeError):
    """Raised when a frozen tuning cell is incomplete or invalid."""


def _refuse_existing_output(path: str | Path) -> None:
    destination = Path(path)
    existing = [
        candidate
        for candidate in (
            destination,
            destination.with_name(destination.name + ".sha256"),
        )
        if candidate.exists() or candidate.is_symlink()
    ]
    if existing:
        raise TuningError(
            f"refusing to overwrite evidence output: {[str(path) for path in existing]}"
        )


def _prepare(
    config: Mapping[str, Any], prepared: Any
) -> tuple[Any, Any, dict[str, Any]]:
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
    environments = {
        task: build_task_environment(
            prepared, task, config, split=split, preprocessing=transform
        )
        for task in EXPECTED_TASKS
    }
    return split, transform, environments


def _execution_metadata(execution: Mapping[str, Any]) -> dict[str, Any]:
    runtime = dict(execution["runtime"])
    runtime_execution = dict(runtime["execution"])
    runtime_execution.update(
        {
            "actual_concurrent_workers": 1,
            "execution_model": "fresh_spawned_process_per_tuning_cell",
            "worker_pid": int(execution["process_id"]),
            "memory_measurement": dict(execution["memory"]),
        }
    )
    runtime["execution"] = runtime_execution
    return runtime


def _optimizer_grid(config: Mapping[str, Any]) -> tuple[OptimizerSpec, ...]:
    update = config["representation_update"]
    return tuple(
        OptimizerSpec(float(rate), int(steps))
        for rate, steps in itertools.product(
            update["learning_rate_grid"], update["steps_per_round_grid"]
        )
    )


def _optimizer_key(spec: OptimizerSpec) -> tuple[int, float]:
    return spec.steps_per_round, spec.learning_rate


def run_tuning_suite(
    *,
    config_path: str | Path,
    prepared_artifact: str | Path,
    output_path: str | Path,
    freeze_revision: str,
    data_lock_path: str | Path,
    repository_root: str | Path = Path(__file__).resolve().parents[2],
) -> dict[str, Any]:
    """Execute the complete preregistered tuning grid and choose settings."""

    _refuse_existing_output(output_path)
    config = load_config(config_path, "tuning")
    policy = profile_policy(config, "tuning")
    try:
        frozen_inventory = verify_clean_freeze(
            freeze_revision,
            repo_root=repository_root,
            require_head=True,
        )
        prepared, data_lock = authenticate_prepared_data(
            config=config,
            config_path=config_path,
            prepared_artifact=prepared_artifact,
            data_lock_path=data_lock_path,
            freeze_revision=freeze_revision,
            repo_root=repository_root,
        )
    except IntegrityError as error:
        raise TuningError(f"freeze/data-lock verification failed: {error}") from error
    split, transform, environments = _prepare(config, prepared)
    try:
        verify_derived_data_identities(
            data_lock,
            split_digest=split.digest,
            preprocessing_digest=transform.digest,
        )
    except IntegrityError as error:
        raise TuningError(f"data-lock verification failed: {error}") from error
    seeds = policy.seeds
    rounds = policy.rounds
    burn_in = int(config["representation_update"]["burn_in_rounds"])
    blas_threads = int(config["execution"]["blas_threads_per_worker"])
    optimizer_records: list[dict[str, Any]] = []
    for task, optimizer, seed in itertools.product(
        EXPECTED_TASKS, _optimizer_grid(config), seeds
    ):
        environment = environments[task]
        stream = build_stream(environment, "tuning", seed, rounds)
        execution = run_isolated_tuning_trajectory(
            environment,
            stream,
            optimizer,
            ridge=float(config["model"]["ridge"]),
            training_ridge=float(config["model"]["training_ridge"]),
            theta_radius=float(config["model"]["theta_radius"]),
            burn_in=burn_in,
            blas_threads=blas_threads,
        )
        result = execution["result"]
        optimizer_records.append(
            {
                **dict(result.summary),
                "memory_measurement": execution["memory"],
                "thread_control": execution["thread_control"],
                "worker_pid": int(execution["process_id"]),
                "runtime": _execution_metadata(execution),
            }
        )

    def optimizer_mean(tasks: set[str], candidate: OptimizerSpec) -> float:
        values = [
            float(row["mean_all_action_prediction_mse"])
            for row in optimizer_records
            if row["task"] in tasks
            and float(row["learning_rate"]) == candidate.learning_rate
            and int(row["steps_per_round"]) == candidate.steps_per_round
        ]
        expected = len(tasks) * len(seeds)
        if len(values) != expected:
            raise TuningError("optimizer tuning grid is incomplete")
        return float(np.mean(values))

    candidates = _optimizer_grid(config)
    label_optimizer = min(
        candidates,
        key=lambda candidate: (
            optimizer_mean({EXPECTED_TASKS[0]}, candidate),
            *_optimizer_key(candidate),
        ),
    )
    controlled_optimizer = min(
        candidates,
        key=lambda candidate: (
            optimizer_mean(set(EXPECTED_TASKS[1:]), candidate),
            *_optimizer_key(candidate),
        ),
    )
    selected_optimizer = {
        "label": {
            "learning_rate": label_optimizer.learning_rate,
            "steps_per_round": label_optimizer.steps_per_round,
        },
        "controlled_shared": {
            "learning_rate": controlled_optimizer.learning_rate,
            "steps_per_round": controlled_optimizer.steps_per_round,
        },
    }

    linucb_records: list[dict[str, Any]] = []
    selected_alphas: dict[str, float] = {}
    for task in EXPECTED_TASKS:
        environment = environments[task]
        optimizer = (
            label_optimizer if task == EXPECTED_TASKS[0] else controlled_optimizer
        )
        for alpha in config["linucb"]["alpha_grid"]:
            for seed in seeds:
                execution = run_isolated_policy_trajectory(
                    environment,
                    build_stream(environment, "tuning", seed, rounds),
                    "linucb_fixed_features",
                    BenchmarkSettings.from_config(
                        config, optimizer=optimizer, linucb_alpha=float(alpha)
                    ),
                    blas_threads=blas_threads,
                )
                result = execution["result"]
                linucb_records.append(
                    {
                        "task": task,
                        "seed": seed,
                        "alpha": float(alpha),
                        "cumulative_regret": float(
                            result.summary["cumulative_pseudo_regret"]
                        ),
                        "deterministic_failure": bool(
                            result.summary["deterministic_failure"]
                        ),
                        "peak_rss_bytes": int(execution["memory"]["peak_rss_bytes"]),
                        "memory_measurement": execution["memory"],
                        "thread_control": execution["runtime"]["execution"][
                            "thread_control"
                        ],
                        "worker_pid": int(execution["process_id"]),
                        "runtime": _execution_metadata(execution),
                    }
                )
        selected_alphas[task] = min(
            (float(value) for value in config["linucb"]["alpha_grid"]),
            key=lambda alpha: (
                float(
                    np.mean(
                        [
                            row["cumulative_regret"]
                            for row in linucb_records
                            if row["task"] == task and row["alpha"] == alpha
                        ]
                    )
                ),
                alpha,
            ),
        )

    approximate_records: list[dict[str, Any]] = []
    practical: dict[str, str] = {}
    for task in EXPECTED_TASKS:
        environment = environments[task]
        optimizer = (
            label_optimizer if task == EXPECTED_TASKS[0] else controlled_optimizer
        )
        for method in APPROXIMATE_METHODS:
            for seed in seeds:
                execution = run_isolated_policy_trajectory(
                    environment,
                    build_stream(environment, "tuning", seed, rounds),
                    method,
                    BenchmarkSettings.from_config(
                        config,
                        optimizer=optimizer,
                        linucb_alpha=selected_alphas[task],
                    ),
                    blas_threads=blas_threads,
                )
                result = execution["result"]
                approximate_records.append(
                    {
                        "task": task,
                        "seed": seed,
                        "method": method,
                        "cumulative_regret": float(
                            result.summary["cumulative_pseudo_regret"]
                        ),
                        "deterministic_failure": bool(
                            result.summary["deterministic_failure"]
                        ),
                        "algorithm_seconds": float(
                            result.summary["total_algorithm_seconds"]
                        ),
                        "logical_operator_bytes": int(
                            result.summary["maximum_logical_operator_bytes"]
                        ),
                        "peak_rss_bytes": int(execution["memory"]["peak_rss_bytes"]),
                        "memory_measurement": execution["memory"],
                        "thread_control": execution["runtime"]["execution"][
                            "thread_control"
                        ],
                        "worker_pid": int(execution["process_id"]),
                        "runtime": _execution_metadata(execution),
                    }
                )
        method_summaries: list[tuple[str, float, float, float]] = []
        for method in APPROXIMATE_METHODS:
            cells = [
                row
                for row in approximate_records
                if row["task"] == task and row["method"] == method
            ]
            if len(cells) != len(seeds):
                raise TuningError("approximate-method tuning grid is incomplete")
            if any(bool(row["deterministic_failure"]) for row in cells):
                continue
            method_summaries.append(
                (
                    method,
                    float(np.mean([row["cumulative_regret"] for row in cells])),
                    float(np.median([row["algorithm_seconds"] for row in cells])),
                    float(np.median([row["peak_rss_bytes"] for row in cells])),
                )
            )
        if not method_summaries:
            raise TuningError(
                f"every approximate-method candidate failed deterministically for {task}"
            )
        best_regret = min(row[1] for row in method_summaries)
        eligible = [row for row in method_summaries if row[1] <= 1.05 * best_regret]
        practical[task] = min(
            eligible,
            key=lambda row: (
                row[2],
                row[3],
                int(method_spec(row[0]).rank or 0),
                -float(method_spec(row[0]).cg_tolerance or 0.0),
            ),
        )[0]

    try:
        post_tuning_inventory = verify_clean_freeze(
            freeze_revision,
            repo_root=repository_root,
            require_head=True,
        )
    except IntegrityError as error:
        raise TuningError(f"post-tuning freeze verification failed: {error}") from error
    if post_tuning_inventory != frozen_inventory:
        raise TuningError("scientific source inventory changed during tuning")
    inventory = frozen_inventory
    document = {
        "schema_version": 1,
        "status": "complete",
        "profile": policy.name,
        "phase": policy.phase,
        "evidence_role": policy.evidence_role,
        "seed_set_identity": policy.seed_set_identity,
        "freeze_revision": freeze_revision,
        "config_digest": config_digest(config),
        "scientific_config_digest": scientific_config_digest(config),
        "prepared_data_digest": prepared.content_digest,
        "approved_data_lock_sha256": sha256_file(data_lock_path),
        "split_digest": split.digest,
        "preprocessing_digest": transform.digest,
        "source_inventory": inventory,
        "source_inventory_sha256": input_set_sha256(inventory),
        "optimizer_records": optimizer_records,
        "linucb_records": linucb_records,
        "approximate_records": approximate_records,
        "selection": {
            "optimizer": selected_optimizer,
            "linucb_alpha": selected_alphas,
            "practical_nystrom": practical,
        },
    }
    write_json(output_path, document)
    return document


def lock_selection(
    *,
    tuning_path: str | Path,
    output_path: str | Path,
    repository_root: str | Path = Path(__file__).resolve().parents[2],
) -> dict[str, Any]:
    _refuse_existing_output(output_path)
    tuning_file = Path(tuning_path)
    tuning = json.loads(tuning_file.read_text(encoding="utf-8"))
    if tuning.get("status") != "complete":
        raise TuningError("tuning artifact is incomplete")
    selected = tuning.get("selection")
    if not isinstance(selected, Mapping):
        raise TuningError("tuning artifact lacks selections")
    tuning_sha = sha256_file(tuning_file)
    sidecar = tuning_file.with_name(tuning_file.name + ".sha256")
    try:
        sidecar_fields = sidecar.read_text(encoding="ascii").split()
    except OSError as error:
        raise TuningError(f"cannot read tuning sidecar: {error}") from error
    if sidecar_fields != [tuning_sha, tuning_file.name]:
        raise TuningError("tuning artifact SHA-256 sidecar is invalid")
    try:
        inventory = verify_clean_freeze(
            str(tuning["freeze_revision"]),
            repo_root=repository_root,
            require_head=True,
        )
    except (IntegrityError, KeyError) as error:
        raise TuningError(
            f"pre-selection freeze verification failed: {error}"
        ) from error
    if tuning.get("source_inventory") != inventory:
        raise TuningError("tuning source inventory does not match F")
    document: dict[str, Any] = {
        "schema_version": 2,
        "schema": SELECTION_SCHEMA,
        "status": "selected",
        "freeze_revision": tuning["freeze_revision"],
        "config_digest": tuning["config_digest"],
        "scientific_config_digest": tuning["scientific_config_digest"],
        "prepared_data_digest": tuning["prepared_data_digest"],
        "preprocessing_digest": tuning["preprocessing_digest"],
        "source_inventory": tuning["source_inventory"],
        "source_inventory_sha256": tuning["source_inventory_sha256"],
        "tuning_input_inventory": [{"path": tuning_file.name, "sha256": tuning_sha}],
        "tuning_input_inventory_sha256": input_set_sha256(
            [{"path": tuning_file.name, "sha256": tuning_sha}]
        ),
        "optimizer": selected["optimizer"],
        "linucb_alpha": selected["linucb_alpha"],
        "practical_nystrom": selected["practical_nystrom"],
    }
    document["selection_payload_sha256"] = selection_payload_sha256(document)
    write_json(output_path, document)
    return document


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    tune = subparsers.add_parser("tune")
    tune.add_argument(
        "--config",
        type=Path,
        default=Path("experiments/configs/realistic_transport_covtype.yaml"),
    )
    tune.add_argument("--prepared-artifact", type=Path, required=True)
    tune.add_argument("--data-lock", type=Path, required=True)
    tune.add_argument("--freeze-revision", required=True)
    tune.add_argument(
        "--output",
        type=Path,
        default=Path("results/derived/realistic_transport/TUNING.json"),
    )
    lock = subparsers.add_parser("lock")
    lock.add_argument("--tuning", type=Path, required=True)
    lock.add_argument(
        "--output",
        type=Path,
        default=Path("review/realistic_transport/SELECTION.json"),
    )
    args = parser.parse_args(argv)
    if args.command == "tune":
        result = run_tuning_suite(
            config_path=args.config,
            prepared_artifact=args.prepared_artifact,
            output_path=args.output,
            freeze_revision=args.freeze_revision,
            data_lock_path=args.data_lock,
        )
    else:
        result = lock_selection(tuning_path=args.tuning, output_path=args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
