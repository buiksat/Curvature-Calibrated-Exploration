"""Orchestrate development, tuning, and locked evaluation for transport study."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .artifact_utils import (
    input_set_sha256,
    sha256_file,
    validate_aggregate_provenance_sidecar,
    write_aggregate_with_provenance,
    write_sha256_sidecar,
)
from .config import config_digest, get_seed_set, load_config
from .logging_utils import canonical_json, collect_git_state
from .run_transport_instantiation import (
    DEFAULT_CONFIG_PATH,
    REQUIRED_RUN_FILES,
    run_and_save_policy,
    run_and_save_tuning,
    run_directory,
)
from .transport_instantiation import (
    SUPPORTED_METHODS,
    OptimizerSpec,
    condition_token,
)


class TransportStudyError(RuntimeError):
    """Raised when the preregistered study protocol is incomplete or invalid."""


STUDY_SOURCE_PATHS = (
    "experiments/BUCK",
    "experiments/README.md",
    "experiments/TRANSPORT_INSTANTIATION_PROTOCOL.md",
    "experiments/__init__.py",
    "experiments/aggregate_transport_instantiation.py",
    "experiments/artifact_utils.py",
    "experiments/config.py",
    "experiments/configs/transport_instantiation.yaml",
    "experiments/curvature_operators.py",
    "experiments/logging_utils.py",
    "experiments/make_transport_instantiation_artifacts.py",
    "experiments/run_transport_instantiation.py",
    "experiments/run_transport_instantiation_study.py",
    "experiments/theory_metrics.py",
    "experiments/transport_instantiation.py",
)


def study_source_inventory() -> list[dict[str, str]]:
    repository = Path(__file__).resolve().parents[1]
    inventory: list[dict[str, str]] = []
    for relative in STUDY_SOURCE_PATHS:
        path = repository / relative
        if not path.is_file():
            raise TransportStudyError(f"missing frozen study source {relative}")
        inventory.append({"path": relative, "sha256": sha256_file(path)})
    return inventory


def _sequence(value: Any, *, name: str) -> tuple[Any, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise TransportStudyError(f"{name} must be a nonempty list")
    return tuple(value)


def _finite_positive(value: Any, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise TransportStudyError(f"{name} must be finite and positive")
    return result


def validate_transport_config(config: Mapping[str, Any]) -> None:
    """Validate experiment-specific invariants after generic profile resolution."""

    if config.get("name") != "transport_instantiation":
        raise TransportStudyError("wrong experiment name")
    environment = config.get("environment")
    if not isinstance(environment, Mapping):
        raise TransportStudyError("environment must be an object")
    expected_dimensions = {
        "context_dimension": 4,
        "action_count": 5,
        "feature_dimension": 29,
    }
    for key, expected in expected_dimensions.items():
        if environment.get(key) != expected:
            raise TransportStudyError(f"environment.{key} must be {expected}")
    methods = tuple(str(value) for value in _sequence(config.get("methods"), name="methods"))
    if methods != SUPPORTED_METHODS:
        raise TransportStudyError(
            f"methods must be exactly {list(SUPPORTED_METHODS)} in that order"
        )
    horizons = tuple(int(value) for value in _sequence(config.get("horizons"), name="horizons"))
    if any(value <= 1 for value in horizons) or len(set(horizons)) != len(horizons):
        raise TransportStudyError("horizons must be distinct integers above one")
    rounds = int(config.get("rounds", 0))
    if max(horizons) != rounds:
        raise TransportStudyError("rounds must equal the largest horizon")
    targets = tuple(
        _finite_positive(value, name="target_D")
        for value in _sequence(config.get("target_D"), name="target_D")
    )
    if len(set(targets)) != len(targets):
        raise TransportStudyError("target_D contains duplicates")
    confidence = config.get("confidence")
    if not isinstance(confidence, Mapping) or float(
        confidence.get("bonus_multiplier", float("nan"))
    ) != 1.0:
        raise TransportStudyError("the confidence bonus multiplier must remain one")
    get_seed_set(config, "tuning")
    get_seed_set(config, "evaluation")
    if "development" in config.get("seed_sets", {}):
        get_seed_set(config, "development")
    optimizer_grid(config)


def study_cells(config: Mapping[str, Any]) -> tuple[tuple[int, float], ...]:
    return tuple(
        (int(horizon), float(target_d))
        for horizon, target_d in itertools.product(
            config["horizons"], config["target_D"]
        )
    )


def optimizer_grid(config: Mapping[str, Any]) -> tuple[tuple[str, OptimizerSpec], ...]:
    representation = config.get("representation_update")
    tuning = representation.get("tuning") if isinstance(representation, Mapping) else None
    if not isinstance(tuning, Mapping):
        raise TransportStudyError("representation_update.tuning must be an object")
    rates = tuple(
        _finite_positive(value, name="learning_rate_grid")
        for value in _sequence(
            tuning.get("learning_rate_grid"), name="learning_rate_grid"
        )
    )
    steps = tuple(
        int(value)
        for value in _sequence(
            tuning.get("steps_per_round_grid"), name="steps_per_round_grid"
        )
    )
    if any(value <= 0 for value in steps):
        raise TransportStudyError("steps_per_round_grid values must be positive")
    if len(set(rates)) != len(rates) or len(set(steps)) != len(steps):
        raise TransportStudyError("optimizer grid contains duplicates")
    return tuple(
        (f"candidate-{index:03d}", OptimizerSpec(rate, step_count))
        for index, (rate, step_count) in enumerate(itertools.product(rates, steps))
    )


def development_optimizer(config: Mapping[str, Any]) -> OptimizerSpec:
    representation = config.get("representation_update")
    value = (
        representation.get("development_optimizer")
        if isinstance(representation, Mapping)
        else None
    )
    if not isinstance(value, Mapping):
        raise TransportStudyError("development_optimizer must be configured")
    return OptimizerSpec.from_mapping(value)


def _workers(config: Mapping[str, Any]) -> int:
    execution = config.get("execution")
    value = execution.get("workers", 1) if isinstance(execution, Mapping) else 1
    workers = int(value)
    if workers <= 0:
        raise TransportStudyError("execution.workers must be positive")
    return workers


def _configure_blas_threads(config: Mapping[str, Any]) -> None:
    execution = config.get("execution")
    value = (
        execution.get("blas_threads_per_worker", 1)
        if isinstance(execution, Mapping)
        else 1
    )
    threads = int(value)
    if threads <= 0:
        raise TransportStudyError("execution.blas_threads_per_worker must be positive")
    encoded = str(threads)
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[name] = encoded


def _map_tasks(function: Any, tasks: Sequence[tuple[Any, ...]], workers: int) -> list[Any]:
    if workers == 1:
        return [function(task) for task in tasks]
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(function, tasks, chunksize=1))


def _policy_task(task: tuple[Any, ...]) -> dict[str, Any]:
    (
        config,
        method,
        seed,
        horizon,
        target_d,
        optimizer,
        phase,
        diagnostic_mode,
        output_root,
        selection_sha256,
        overwrite,
    ) = task
    _configure_blas_threads(config)
    return run_and_save_policy(
        config,
        method=method,
        seed=seed,
        horizon=horizon,
        target_d=target_d,
        optimizer=optimizer,
        phase=phase,
        diagnostic_mode=diagnostic_mode,
        output_root=output_root,
        selection_sha256=selection_sha256,
        overwrite=overwrite,
    )


def _tuning_task(task: tuple[Any, ...]) -> dict[str, Any]:
    (
        config,
        candidate_id,
        seed,
        horizon,
        target_d,
        optimizer,
        output_root,
        overwrite,
    ) = task
    _configure_blas_threads(config)
    return run_and_save_tuning(
        config,
        candidate_id=candidate_id,
        seed=seed,
        horizon=horizon,
        target_d=target_d,
        optimizer=optimizer,
        output_root=output_root,
        overwrite=overwrite,
    )


def run_development(
    config: Mapping[str, Any],
    output_root: str | Path,
    *,
    overwrite: bool,
) -> dict[str, Any]:
    validate_transport_config(config)
    optimizer = development_optimizer(config)
    seeds = get_seed_set(config, "development")
    tasks = [
        (
            dict(config),
            method,
            seed,
            horizon,
            target_d,
            optimizer,
            "development",
            "development",
            str(output_root),
            None,
            overwrite,
        )
        for seed in seeds
        for horizon, target_d in study_cells(config)
        for method in SUPPORTED_METHODS
    ]
    results = _map_tasks(_policy_task, tasks, _workers(config))
    return {
        "phase": "development",
        "profile": config["profile"],
        "run_count": len(results),
        "seeds": list(seeds),
        "optimizer": {
            "learning_rate": optimizer.learning_rate,
            "steps_per_round": optimizer.steps_per_round,
        },
        "output_root": str(output_root),
    }


def _run_input_inventory(
    output_root: str | Path,
    *,
    phase: str,
    candidate_ids: Sequence[str],
    seeds: Sequence[int],
    cells: Sequence[tuple[int, float]],
) -> list[dict[str, str]]:
    inventory: list[dict[str, str]] = []
    for candidate_id in candidate_ids:
        for seed in seeds:
            for horizon, target_d in cells:
                directory = run_directory(
                    output_root,
                    phase=phase,
                    horizon=horizon,
                    target_d=target_d,
                    run_key=candidate_id,
                    seed=seed,
                )
                for filename in REQUIRED_RUN_FILES:
                    path = directory / filename
                    if not path.is_file():
                        raise TransportStudyError(f"missing tuning input {path}")
                    inventory.append(
                        {"path": str(path), "sha256": sha256_file(path)}
                    )
    return sorted(inventory, key=lambda item: item["path"])


def _summary_at(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TransportStudyError(f"cannot read summary {path}: {error}") from error
    if not isinstance(value, dict):
        raise TransportStudyError(f"summary is not an object: {path}")
    return value


def _write_selection_alias(
    selection: Mapping[str, Any], primary: Path, config: Mapping[str, Any]
) -> list[str]:
    outputs = config.get("outputs")
    alias = (
        Path(str(outputs.get("required_selection_export")))
        if isinstance(outputs, Mapping)
        and outputs.get("required_selection_export")
        else None
    )
    written: list[str] = []
    if alias is not None and alias != primary and config.get("profile") == "full":
        artifact, sidecar = write_aggregate_with_provenance(selection, alias)
        write_sha256_sidecar(artifact)
        written.extend((str(artifact), str(sidecar)))
    return written


def run_tuning(
    config: Mapping[str, Any],
    output_root: str | Path,
    selection_output: str | Path,
    *,
    config_path: str | Path,
    overwrite: bool,
) -> dict[str, Any]:
    validate_transport_config(config)
    source_inputs_before = study_source_inventory()
    candidates = optimizer_grid(config)
    seeds = get_seed_set(config, "tuning")
    evaluation_seeds = get_seed_set(config, "evaluation")
    cells = study_cells(config)
    tasks = [
        (
            dict(config),
            candidate_id,
            seed,
            horizon,
            target_d,
            optimizer,
            str(output_root),
            overwrite,
        )
        for candidate_id, optimizer in candidates
        for seed in seeds
        for horizon, target_d in cells
    ]
    _map_tasks(_tuning_task, tasks, _workers(config))
    if study_source_inventory() != source_inputs_before:
        raise TransportStudyError("study source tree changed during tuning")

    candidate_records: list[dict[str, Any]] = []
    for candidate_id, optimizer in candidates:
        run_records: list[dict[str, Any]] = []
        criterion_values: list[float] = []
        rejection_reasons: list[str] = []
        for seed in seeds:
            for horizon, target_d in cells:
                directory = run_directory(
                    output_root,
                    phase="tuning",
                    horizon=horizon,
                    target_d=target_d,
                    run_key=candidate_id,
                    seed=seed,
                )
                summary = _summary_at(directory / "summary.json")
                valid = summary.get("valid") is True
                criterion = summary.get("mean_all_action_prediction_mse")
                if valid and isinstance(criterion, (int, float)) and not isinstance(
                    criterion, bool
                ) and math.isfinite(float(criterion)):
                    criterion_values.append(float(criterion))
                else:
                    reasons = summary.get("rejection_reasons", ())
                    rejection_reasons.append(
                        f"seed={seed},T={horizon},D={target_d}: {list(reasons)}"
                    )
                run_records.append(
                    {
                        "seed": seed,
                        "horizon": horizon,
                        "target_D": target_d,
                        "valid": valid,
                        "mean_all_action_prediction_mse": criterion,
                        "rejection_reasons": summary.get("rejection_reasons", ()),
                        "summary_path": str(directory / "summary.json"),
                    }
                )
        eligible = not rejection_reasons and len(criterion_values) == len(seeds) * len(cells)
        aggregate_criterion = (
            float(sum(criterion_values) / len(criterion_values))
            if eligible
            else None
        )
        candidate_records.append(
            {
                "candidate_id": candidate_id,
                "learning_rate": optimizer.learning_rate,
                "steps_per_round": optimizer.steps_per_round,
                "eligible": eligible,
                "aggregate_mean_all_action_prediction_mse": aggregate_criterion,
                "rejection_reasons": rejection_reasons,
                "runs": run_records,
            }
        )
    eligible_records = [record for record in candidate_records if record["eligible"]]
    if not eligible_records:
        raise TransportStudyError("all optimizer candidates were rejected")
    winner = min(
        eligible_records,
        key=lambda record: (
            float(record["aggregate_mean_all_action_prediction_mse"]),
            int(record["steps_per_round"]),
            float(record["learning_rate"]),
            str(record["candidate_id"]),
        ),
    )
    inputs = _run_input_inventory(
        output_root,
        phase="tuning",
        candidate_ids=[candidate_id for candidate_id, _ in candidates],
        seeds=seeds,
        cells=cells,
    )
    source_config = Path(config_path)
    inputs.append({"path": str(source_config), "sha256": sha256_file(source_config)})
    inputs.sort(key=lambda item: item["path"])
    git_state = collect_git_state(Path(__file__).resolve().parents[1])
    selection: dict[str, Any] = {
        "schema_version": 1,
        "event": "transport_instantiation_selection",
        "profile": str(config["profile"]),
        "config_digest": config_digest(config),
        "git_revision": git_state["revision"],
        "git_dirty": git_state["dirty"],
        "tuning_seeds": list(seeds),
        "evaluation_seeds": list(evaluation_seeds),
        "seed_sets_disjoint": set(seeds).isdisjoint(evaluation_seeds),
        "selection_metric": "mean_all_action_prediction_mse_after_burn_in",
        "selection_metric_description": (
            "equal-weight mean of per-(seed,horizon,target_D) all-action "
            "prediction MSE after burn-in"
        ),
        "candidate_count": len(candidate_records),
        "candidates": candidate_records,
        "selected": {
            "candidate_id": winner["candidate_id"],
            "learning_rate": winner["learning_rate"],
            "steps_per_round": winner["steps_per_round"],
            "aggregate_mean_all_action_prediction_mse": winner[
                "aggregate_mean_all_action_prediction_mse"
            ],
            "tie_break": ["fewer_steps_per_round", "smaller_learning_rate"],
        },
        "complete_tuning_input_inventory": True,
        "study_source_inputs": source_inputs_before,
        "inputs": inputs,
        "input_set_sha256": input_set_sha256(inputs),
    }
    selection["study_source_input_set_sha256"] = input_set_sha256(
        selection["study_source_inputs"]
    )
    output, provenance = write_aggregate_with_provenance(
        selection, selection_output
    )
    sha_sidecar = write_sha256_sidecar(output)
    aliases = _write_selection_alias(selection, output, config)
    return {
        "phase": "tuning",
        "profile": config["profile"],
        "run_count": len(tasks),
        "selection": str(output),
        "selection_sha256": sha256_file(output),
        "provenance": str(provenance),
        "sha256_sidecar": str(sha_sidecar),
        "aliases": aliases,
        "selected": selection["selected"],
    }


def load_selection(
    selection_path: str | Path, config: Mapping[str, Any]
) -> tuple[OptimizerSpec, str, dict[str, Any]]:
    path = Path(selection_path)
    validate_aggregate_provenance_sidecar(path)
    try:
        selection = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TransportStudyError(f"cannot parse selection: {error}") from error
    if not isinstance(selection, dict):
        raise TransportStudyError("selection must be a JSON object")
    expected = {
        "schema_version": 1,
        "event": "transport_instantiation_selection",
        "profile": str(config["profile"]),
        "config_digest": config_digest(config),
        "tuning_seeds": list(get_seed_set(config, "tuning")),
        "evaluation_seeds": list(get_seed_set(config, "evaluation")),
        "seed_sets_disjoint": True,
    }
    for key, value in expected.items():
        if selection.get(key) != value:
            raise TransportStudyError(f"selection mismatch for {key}")
    if (
        selection.get("selection_metric")
        != "mean_all_action_prediction_mse_after_burn_in"
    ):
        raise TransportStudyError("selection metric is not preregistered")
    if selection.get("complete_tuning_input_inventory") is not True:
        raise TransportStudyError("selection lacks a complete tuning inventory")
    current_source_inputs = study_source_inventory()
    if selection.get("study_source_inputs") != current_source_inputs or selection.get(
        "study_source_input_set_sha256"
    ) != input_set_sha256(current_source_inputs):
        raise TransportStudyError("study source tree changed after tuning")
    inputs = selection.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise TransportStudyError("selection has no tuning input inventory")
    evaluation_tokens = {
        f"seed-{seed}" for seed in get_seed_set(config, "evaluation")
    }
    for item in inputs:
        if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
            raise TransportStudyError("selection input inventory is malformed")
        parts = set(Path(str(item["path"])).parts)
        if "evaluation" in parts or parts & evaluation_tokens:
            raise TransportStudyError("evaluation data appears in tuning selection")
    selected = selection.get("selected")
    if not isinstance(selected, Mapping):
        raise TransportStudyError("selection has no selected optimizer")
    candidates = selection.get("candidates")
    if not isinstance(candidates, list) or not any(
        isinstance(candidate, Mapping)
        and candidate.get("candidate_id") == selected.get("candidate_id")
        for candidate in candidates
    ):
        raise TransportStudyError("selected optimizer is absent from candidates")
    try:
        from .aggregate_transport_instantiation import (
            TransportAggregationError,
            _validate_selection_candidates,
        )

        _validate_selection_candidates(selection, config)
    except TransportAggregationError as error:
        raise TransportStudyError(
            f"selection winner failed independent replay: {error}"
        ) from error
    return OptimizerSpec.from_mapping(selected), sha256_file(path), selection


def run_evaluation(
    config: Mapping[str, Any],
    output_root: str | Path,
    selection_path: str | Path,
    *,
    overwrite: bool,
) -> dict[str, Any]:
    validate_transport_config(config)
    optimizer, selection_sha256, selection = load_selection(selection_path, config)
    current_revision = collect_git_state(
        Path(__file__).resolve().parents[1]
    )["revision"]
    if selection.get("git_revision") != current_revision:
        raise TransportStudyError("evaluation revision differs from tuning revision")
    source_inputs_before = study_source_inventory()
    seeds = get_seed_set(config, "evaluation")
    tasks = [
        (
            dict(config),
            method,
            seed,
            horizon,
            target_d,
            optimizer,
            "evaluation",
            "smoke" if config.get("profile") == "smoke" else "evaluation",
            str(output_root),
            selection_sha256,
            overwrite,
        )
        for seed in seeds
        for horizon, target_d in study_cells(config)
        for method in SUPPORTED_METHODS
    ]
    results = _map_tasks(_policy_task, tasks, _workers(config))
    if study_source_inventory() != source_inputs_before:
        raise TransportStudyError("study source tree changed during evaluation")
    failures = [
        result
        for result in results
        if result.get("deterministic_audit_passed") is not True
    ]
    if failures:
        raise TransportStudyError(
            f"evaluation produced {len(failures)} deterministic audit failures"
        )
    return {
        "phase": "evaluation",
        "profile": config["profile"],
        "run_count": len(results),
        "expected_run_count": len(seeds) * len(study_cells(config)) * len(SUPPORTED_METHODS),
        "selection_sha256": selection_sha256,
        "git_revision": current_revision,
        "deterministic_audit_failure_count": 0,
        "output_root": str(output_root),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument(
        "--phase", choices=("development", "tuning", "evaluation"), required=True
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--selection-output", type=Path)
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config, profile=args.profile)
    _configure_blas_threads(config)
    if args.phase == "development":
        result = run_development(config, args.output_root, overwrite=args.overwrite)
    elif args.phase == "tuning":
        if args.selection_output is None:
            parser.error("--selection-output is required for tuning")
        result = run_tuning(
            config,
            args.output_root,
            args.selection_output,
            config_path=args.config,
            overwrite=args.overwrite,
        )
    else:
        if args.selection is None:
            parser.error("--selection is required for evaluation")
        result = run_evaluation(
            config,
            args.output_root,
            args.selection,
            overwrite=args.overwrite,
        )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "TransportStudyError",
    "development_optimizer",
    "load_selection",
    "optimizer_grid",
    "run_development",
    "run_evaluation",
    "run_tuning",
    "study_cells",
    "validate_transport_config",
]
