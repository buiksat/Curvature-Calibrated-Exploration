"""Frozen tuning and selection for the realistic transport benchmark."""

from __future__ import annotations

import argparse
import itertools
import json
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
    APPROXIMATE_METHODS,
    EXPECTED_TASKS,
    config_digest,
    load_config,
    method_spec,
    seed_set,
)
from .data import load_prepared_dataset
from .environment import build_stream, build_task_environment
from .preprocessing import deterministic_split, fit_preprocessing
from .provenance import (
    git_state,
    input_set_sha256,
    sha256_file,
    source_inventory,
    write_json,
)
from .study import PeakRSSSampler


class TuningError(RuntimeError):
    """Raised when a frozen tuning cell is incomplete or invalid."""


def _prepare(
    config: Mapping[str, Any], artifact: str | Path
) -> tuple[Any, Any, Any, dict[str, Any]]:
    prepared = load_prepared_dataset(
        artifact, required_digest=config["dataset"].get("required_semantic_digest")
    )
    if prepared.manifest.get("smoke_only"):
        raise TuningError("smoke-only data cannot be used for locked tuning")
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
    return prepared, split, transform, environments


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
) -> dict[str, Any]:
    """Execute the complete preregistered tuning grid and choose settings."""

    config = load_config(config_path, "full")
    state = git_state()
    if state["revision"] != freeze_revision:
        raise TuningError(
            f"HEAD {state['revision']} differs from freeze revision {freeze_revision}"
        )
    prepared, split, transform, environments = _prepare(config, prepared_artifact)
    seeds = seed_set(config, "tuning")
    rounds = int(config["horizons"]["maximum"])
    burn_in = int(config["representation_update"]["burn_in_rounds"])
    optimizer_records: list[dict[str, Any]] = []
    for task, optimizer, seed in itertools.product(
        EXPECTED_TASKS, _optimizer_grid(config), seeds
    ):
        environment = environments[task]
        stream = build_stream(environment, "tuning", seed, rounds)
        result = run_tuning_trajectory(
            environment,
            stream,
            optimizer,
            ridge=float(config["model"]["ridge"]),
            training_ridge=float(config["model"]["training_ridge"]),
            theta_radius=float(config["model"]["theta_radius"]),
            burn_in=burn_in,
        )
        optimizer_records.append(dict(result.summary))

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
                with PeakRSSSampler() as memory:
                    result = run_policy_trajectory(
                        environment,
                        build_stream(environment, "tuning", seed, rounds),
                        "linucb_fixed_features",
                        BenchmarkSettings.from_config(
                            config, optimizer=optimizer, linucb_alpha=float(alpha)
                        ),
                    )
                linucb_records.append(
                    {
                        "task": task,
                        "seed": seed,
                        "alpha": float(alpha),
                        "cumulative_regret": float(
                            result.summary["cumulative_pseudo_regret"]
                        ),
                        "peak_rss_bytes": int(memory.peak_bytes),
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
                with PeakRSSSampler() as memory:
                    result = run_policy_trajectory(
                        environment,
                        build_stream(environment, "tuning", seed, rounds),
                        method,
                        BenchmarkSettings.from_config(
                            config,
                            optimizer=optimizer,
                            linucb_alpha=selected_alphas[task],
                        ),
                    )
                approximate_records.append(
                    {
                        "task": task,
                        "seed": seed,
                        "method": method,
                        "cumulative_regret": float(
                            result.summary["cumulative_pseudo_regret"]
                        ),
                        "algorithm_seconds": float(
                            result.summary["total_algorithm_seconds"]
                        ),
                        "logical_operator_bytes": int(
                            result.summary["maximum_logical_operator_bytes"]
                        ),
                        "peak_rss_bytes": int(memory.peak_bytes),
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
            method_summaries.append(
                (
                    method,
                    float(np.mean([row["cumulative_regret"] for row in cells])),
                    float(np.median([row["algorithm_seconds"] for row in cells])),
                    float(np.median([row["peak_rss_bytes"] for row in cells])),
                )
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

    inventory = source_inventory()
    document = {
        "schema_version": 1,
        "status": "complete",
        "freeze_revision": freeze_revision,
        "config_digest": config_digest(config),
        "prepared_data_digest": prepared.content_digest,
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
    *, tuning_path: str | Path, output_path: str | Path
) -> dict[str, Any]:
    tuning_file = Path(tuning_path)
    tuning = json.loads(tuning_file.read_text(encoding="utf-8"))
    if tuning.get("status") != "complete":
        raise TuningError("tuning artifact is incomplete")
    selected = tuning.get("selection")
    if not isinstance(selected, Mapping):
        raise TuningError("tuning artifact lacks selections")
    document = {
        "schema_version": 1,
        "status": "selected",
        "freeze_revision": tuning["freeze_revision"],
        "config_digest": tuning["config_digest"],
        "prepared_data_digest": tuning["prepared_data_digest"],
        "preprocessing_digest": tuning["preprocessing_digest"],
        "source_inventory": tuning["source_inventory"],
        "source_inventory_sha256": tuning["source_inventory_sha256"],
        "tuning_input_inventory": [
            {"path": tuning_file.name, "sha256": sha256_file(tuning_file)}
        ],
        "tuning_input_inventory_sha256": input_set_sha256(
            [{"path": tuning_file.name, "sha256": sha256_file(tuning_file)}]
        ),
        "optimizer": selected["optimizer"],
        "linucb_alpha": selected["linucb_alpha"],
        "practical_nystrom": selected["practical_nystrom"],
        "selection_lock_revision": None,
    }
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
        )
    else:
        result = lock_selection(tuning_path=args.tuning, output_path=args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
