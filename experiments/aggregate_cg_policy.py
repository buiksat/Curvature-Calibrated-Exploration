"""Strict aggregation for the multi-cell executed CG policy audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scipy.stats import t as student_t

from .logging_utils import canonical_json
from .run_cg_accuracy import ENERGY_TARGETS, INITIALIZATIONS, PRECONDITIONERS


class CGPolicyAggregationError(ValueError):
    """Raised when an artifact tree cannot support a policy comparison."""


def _jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise CGPolicyAggregationError(f"cannot read {path}: {error}") from error
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise CGPolicyAggregationError(
                f"invalid JSON in {path}:{number}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise CGPolicyAggregationError(f"{path}:{number} is not an object")
        records.append(value)
    if not records:
        raise CGPolicyAggregationError(f"{path} contains no records")
    return records


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _interval(values: Sequence[float]) -> dict[str, float | int]:
    if not values:
        raise CGPolicyAggregationError("cannot summarize an empty sample")
    mean = float(statistics.mean(values))
    if len(values) == 1:
        half_width = 0.0
    else:
        half_width = float(
            student_t.ppf(0.975, len(values) - 1)
            * statistics.stdev(values)
            / math.sqrt(len(values))
        )
    return {
        "n": len(values),
        "mean": mean,
        "ci95_low": mean - half_width,
        "ci95_high": mean + half_width,
    }


def aggregate_policy_artifacts(
    input_root: str | Path, *, expected_seed_set: str = "evaluation"
) -> dict[str, Any]:
    root = Path(input_root)
    directories = sorted(path.parent for path in root.rglob("manifest.jsonl"))
    if not directories:
        raise CGPolicyAggregationError(f"no policy runs below {root}")

    expected_cells = {
        (epsilon, initialization, preconditioner)
        for epsilon in ENERGY_TARGETS
        for initialization in INITIALIZATIONS
        for preconditioner in PRECONDITIONERS
    }
    by_cell: dict[tuple[float, str, str], dict[int, dict[str, Any]]] = defaultdict(dict)
    input_files: list[dict[str, str]] = []
    declared_seeds: tuple[int, ...] | None = None
    profile: str | None = None
    rounds: int | None = None
    git_revisions: set[str] = set()

    for directory in directories:
        manifest_path = directory / "manifest.jsonl"
        raw_path = directory / "raw.jsonl"
        summary_path = directory / "summary.jsonl"
        if not raw_path.is_file() or not summary_path.is_file():
            raise CGPolicyAggregationError(f"incomplete policy run: {directory}")
        manifests = _jsonl(manifest_path)
        summaries = _jsonl(summary_path)
        raw = _jsonl(raw_path)
        if len(manifests) != 1:
            raise CGPolicyAggregationError(f"expected one manifest in {directory}")
        manifest = manifests[0]
        config = manifest.get("config")
        if not isinstance(config, Mapping):
            raise CGPolicyAggregationError(f"manifest lacks config: {directory}")
        execution = config.get("execution")
        if not isinstance(execution, Mapping) or execution.get("audit") != "executed_policy":
            raise CGPolicyAggregationError(f"not an executed CG policy run: {directory}")
        seed = manifest.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise CGPolicyAggregationError(f"invalid seed in {directory}")
        seed_sets = config.get("seed_sets")
        if not isinstance(seed_sets, Mapping):
            raise CGPolicyAggregationError(f"missing seed sets in {directory}")
        current_declared = tuple(seed_sets.get(expected_seed_set, ()))
        if not current_declared or seed not in current_declared:
            raise CGPolicyAggregationError(
                f"seed {seed} is not declared in {expected_seed_set}"
            )
        if set(seed_sets.get("tuning", ())) & set(seed_sets.get("evaluation", ())):
            raise CGPolicyAggregationError("tuning and evaluation seeds overlap")
        if declared_seeds is None:
            declared_seeds = current_declared
        elif declared_seeds != current_declared:
            raise CGPolicyAggregationError("manifests disagree on declared seeds")
        current_profile = str(config.get("profile", ""))
        if profile is None:
            profile = current_profile
        elif profile != current_profile:
            raise CGPolicyAggregationError("profiles are mixed")
        current_rounds = int(config.get("rounds", 0))
        if current_rounds <= 0:
            raise CGPolicyAggregationError("invalid round count")
        if rounds is None:
            rounds = current_rounds
        elif rounds != current_rounds:
            raise CGPolicyAggregationError("round counts are mixed")

        if len(summaries) != len(expected_cells):
            raise CGPolicyAggregationError(
                f"{directory} has {len(summaries)} summaries, expected {len(expected_cells)}"
            )
        if len(raw) != current_rounds * len(expected_cells):
            raise CGPolicyAggregationError(
                f"{directory} has {len(raw)} rounds, expected "
                f"{current_rounds * len(expected_cells)}"
            )
        observed_cells: set[tuple[float, str, str]] = set()
        for summary in summaries:
            key = (
                float(summary.get("epsilon_bar")),
                str(summary.get("initialization")),
                str(summary.get("preconditioner")),
            )
            if key not in expected_cells or key in observed_cells:
                raise CGPolicyAggregationError(f"invalid or duplicate cell {key}")
            observed_cells.add(key)
            if (
                summary.get("seed") != seed
                or summary.get("executed_policy") is not True
                or summary.get("certified_execution") is not True
                or summary.get("target_failure_count") != 0
                or summary.get("residual_certificate_violation_count") != 0
                or summary.get("sandwich_violation_count") != 0
            ):
                raise CGPolicyAggregationError(f"uncertified summary in {directory}: {key}")
            if seed in by_cell[key]:
                raise CGPolicyAggregationError(f"duplicate seed {seed} for {key}")
            by_cell[key][seed] = summary
        if observed_cells != expected_cells:
            raise CGPolicyAggregationError(f"incomplete policy grid in {directory}")

        for index, record in enumerate(raw):
            metrics = record.get("metrics")
            if not isinstance(metrics, Mapping):
                raise CGPolicyAggregationError(f"raw record {index} lacks metrics")
            if (
                metrics.get("executed_policy") is not True
                or metrics.get("same_fixed_operator_reused_across_action_solves") is not True
                or metrics.get("full_action_enumeration") is not True
            ):
                raise CGPolicyAggregationError(
                    f"raw record {index} violates executed-policy invariants"
                )

        git_revisions.add(str(manifest.get("git_revision", "unknown")))
        for path in (manifest_path, raw_path, summary_path):
            input_files.append(
                {"path": str(path), "sha256": _sha256(path)}
            )

    assert declared_seeds is not None and rounds is not None
    observed_seeds = sorted({seed for values in by_cell.values() for seed in values})
    if tuple(observed_seeds) != tuple(sorted(declared_seeds)):
        raise CGPolicyAggregationError(
            f"observed seeds {observed_seeds} do not equal declared seeds "
            f"{sorted(declared_seeds)}"
        )
    for key, values in by_cell.items():
        if set(values) != set(declared_seeds):
            raise CGPolicyAggregationError(f"cell {key} has incomplete seeds")

    metric_names = (
        "cumulative_pseudo_regret",
        "all_action_optimism_violation_rate",
        "mean_initial_relative_energy_error",
        "mean_exact_relative_energy_error",
        "max_exact_relative_energy_error",
        "mean_cg_iterations_per_action",
        "total_operator_matvecs",
        "runtime_seconds",
        "solver_wall_time_seconds",
        "peak_host_memory_bytes",
        "theorem_rhs",
    )
    cells: list[dict[str, Any]] = []
    for key in sorted(expected_cells):
        epsilon, initialization, preconditioner = key
        values = by_cell[key]
        cells.append(
            {
                "epsilon_bar": epsilon,
                "initialization": initialization,
                "preconditioner": preconditioner,
                "metrics": {
                    metric: _interval(
                        [float(values[seed][metric]) for seed in declared_seeds]
                    )
                    for metric in metric_names
                },
            }
        )

    paired_warm_minus_zero: list[dict[str, Any]] = []
    for epsilon in ENERGY_TARGETS:
        for preconditioner in PRECONDITIONERS:
            warm = by_cell[(epsilon, "warm", preconditioner)]
            zero = by_cell[(epsilon, "zero", preconditioner)]
            paired_warm_minus_zero.append(
                {
                    "epsilon_bar": epsilon,
                    "preconditioner": preconditioner,
                    "contrast": "warm_minus_zero",
                    "metrics": {
                        metric: _interval(
                            [
                                float(warm[seed][metric])
                                - float(zero[seed][metric])
                                for seed in declared_seeds
                            ]
                        )
                        for metric in (
                            "cumulative_pseudo_regret",
                            "mean_cg_iterations_per_action",
                            "total_operator_matvecs",
                            "runtime_seconds",
                        )
                    },
                }
            )

    paired_epsilon_minus_001: list[dict[str, Any]] = []
    for epsilon in ENERGY_TARGETS:
        if epsilon == 0.01:
            continue
        for initialization in INITIALIZATIONS:
            for preconditioner in PRECONDITIONERS:
                candidate = by_cell[(epsilon, initialization, preconditioner)]
                reference = by_cell[(0.01, initialization, preconditioner)]
                paired_epsilon_minus_001.append(
                    {
                        "epsilon_bar": epsilon,
                        "reference_epsilon_bar": 0.01,
                        "initialization": initialization,
                        "preconditioner": preconditioner,
                        "contrast": "epsilon_minus_0.01",
                        "metrics": {
                            metric: _interval(
                                [
                                    float(candidate[seed][metric])
                                    - float(reference[seed][metric])
                                    for seed in declared_seeds
                                ]
                            )
                            for metric in (
                                "cumulative_pseudo_regret",
                                "mean_cg_iterations_per_action",
                                "total_operator_matvecs",
                                "runtime_seconds",
                            )
                        },
                    }
                )

    paired_jacobi_minus_none: list[dict[str, Any]] = []
    for epsilon in ENERGY_TARGETS:
        for initialization in INITIALIZATIONS:
            jacobi = by_cell[(epsilon, initialization, "jacobi")]
            unpreconditioned = by_cell[(epsilon, initialization, "none")]
            paired_jacobi_minus_none.append(
                {
                    "epsilon_bar": epsilon,
                    "initialization": initialization,
                    "contrast": "jacobi_minus_none",
                    "metrics": {
                        metric: _interval(
                            [
                                float(jacobi[seed][metric])
                                - float(unpreconditioned[seed][metric])
                                for seed in declared_seeds
                            ]
                        )
                        for metric in (
                            "cumulative_pseudo_regret",
                            "mean_cg_iterations_per_action",
                            "total_operator_matvecs",
                            "runtime_seconds",
                        )
                    },
                }
            )

    payload: dict[str, Any] = {
        "schema_version": 1,
        "experiment": "cg_policy_accuracy",
        "profile": profile,
        "seed_set": expected_seed_set,
        "seeds": sorted(declared_seeds),
        "seed_count": len(declared_seeds),
        "rounds_per_policy": rounds,
        "policy_cell_count": len(expected_cells),
        "executed_policy_count": len(expected_cells) * len(declared_seeds),
        "raw_round_count": rounds * len(expected_cells) * len(declared_seeds),
        "all_executions_certified": True,
        "all_residual_certificates_valid": True,
        "all_width_sandwiches_valid": True,
        "warm_start_advantage_assumed": False,
        "cells": cells,
        "paired_warm_minus_zero": paired_warm_minus_zero,
        "paired_epsilon_minus_001": paired_epsilon_minus_001,
        "paired_jacobi_minus_none": paired_jacobi_minus_none,
        "git_revisions": sorted(git_revisions),
        "inputs": sorted(input_files, key=lambda item: item["path"]),
    }
    payload["input_manifest_sha256"] = hashlib.sha256(
        canonical_json(payload["inputs"]).encode("utf-8")
    ).hexdigest()
    return payload


def validate_policy_provenance_sidecar(
    artifact: str | Path, sidecar: str | Path | None = None
) -> dict[str, Any]:
    """Validate an aggregate sidecar and every raw-input digest it binds."""

    artifact_path = Path(artifact)
    sidecar_path = (
        artifact_path.with_suffix(artifact_path.suffix + ".provenance.json")
        if sidecar is None
        else Path(sidecar)
    )
    try:
        record = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CGPolicyAggregationError(f"cannot parse sidecar {sidecar_path}: {error}") from error
    if not isinstance(record, dict):
        raise CGPolicyAggregationError(f"sidecar is not an object: {sidecar_path}")
    if record.get("schema_version") != 1:
        raise CGPolicyAggregationError("unsupported provenance sidecar schema")
    if record.get("artifact") != str(artifact_path):
        raise CGPolicyAggregationError("sidecar artifact path does not match")
    if record.get("artifact_sha256") != _sha256(artifact_path):
        raise CGPolicyAggregationError("sidecar artifact digest does not match")
    inputs = record.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise CGPolicyAggregationError("sidecar must bind at least one raw input")
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(inputs):
        if not isinstance(item, Mapping):
            raise CGPolicyAggregationError(f"invalid sidecar input {index}")
        path_value = item.get("path")
        digest_value = item.get("sha256")
        if not isinstance(path_value, str) or not isinstance(digest_value, str):
            raise CGPolicyAggregationError(f"invalid sidecar input {index}")
        input_path = Path(path_value)
        if not input_path.is_file():
            raise CGPolicyAggregationError(f"sidecar input is missing: {input_path}")
        if _sha256(input_path) != digest_value:
            raise CGPolicyAggregationError(
                f"sidecar input digest does not match: {input_path}"
            )
        normalized.append({"path": path_value, "sha256": digest_value})
    if normalized != sorted(normalized, key=lambda item: item["path"]):
        raise CGPolicyAggregationError("sidecar inputs are not in canonical path order")
    try:
        artifact_record = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CGPolicyAggregationError(f"cannot parse aggregate artifact: {error}") from error
    if not isinstance(artifact_record, Mapping):
        raise CGPolicyAggregationError("aggregate artifact is not an object")
    artifact_inputs = artifact_record.get("inputs")
    if artifact_inputs != normalized:
        raise CGPolicyAggregationError(
            "sidecar inputs do not match the aggregate's complete raw-input inventory"
        )
    expected_input_digest = hashlib.sha256(
        canonical_json(normalized).encode("utf-8")
    ).hexdigest()
    if artifact_record.get("input_manifest_sha256") != expected_input_digest:
        raise CGPolicyAggregationError("aggregate raw-input inventory digest does not match")
    return record


def write_policy_aggregate(
    aggregate: Mapping[str, Any], destination: str | Path
) -> tuple[Path, Path]:
    """Write a derived aggregate and a SHA-256 sidecar over all raw inputs."""

    path = Path(destination)
    inputs = aggregate.get("inputs")
    if not isinstance(inputs, Sequence) or isinstance(inputs, (str, bytes)) or not inputs:
        raise CGPolicyAggregationError("aggregate has no raw-input provenance")
    normalized_inputs: list[dict[str, str]] = []
    for index, item in enumerate(inputs):
        if not isinstance(item, Mapping):
            raise CGPolicyAggregationError(f"invalid aggregate input {index}")
        input_path = item.get("path")
        input_digest = item.get("sha256")
        if not isinstance(input_path, str) or not isinstance(input_digest, str):
            raise CGPolicyAggregationError(f"invalid aggregate input {index}")
        normalized_inputs.append({"path": input_path, "sha256": input_digest})
    normalized_inputs.sort(key=lambda item: item["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    sidecar = path.with_suffix(path.suffix + ".provenance.json")
    sidecar_record = {
        "schema_version": 1,
        "artifact": str(path),
        "artifact_sha256": _sha256(path),
        "inputs": normalized_inputs,
    }
    sidecar.write_text(
        json.dumps(sidecar_record, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    validate_policy_provenance_sidecar(path, sidecar)
    return path, sidecar


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_root", type=Path)
    parser.add_argument("--seed-set", choices=("tuning", "evaluation"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = aggregate_policy_artifacts(
        args.input_root, expected_seed_set=args.seed_set
    )
    artifact, sidecar = write_policy_aggregate(payload, args.output)
    print(
        canonical_json(
            {
                "output": str(artifact),
                "output_sha256": _sha256(artifact),
                "provenance_sidecar": str(sidecar),
                "provenance_sidecar_sha256": _sha256(sidecar),
                "seed_count": payload["seed_count"],
                "policy_cell_count": payload["policy_cell_count"],
                "raw_round_count": payload["raw_round_count"],
                "input_manifest_sha256": payload["input_manifest_sha256"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CGPolicyAggregationError",
    "aggregate_policy_artifacts",
    "validate_policy_provenance_sidecar",
    "write_policy_aggregate",
]
