"""Strict seed-level aggregation for realistic transport runs."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .configuration import (
    APPROXIMATE_METHODS,
    EXPECTED_METHODS,
    EXPECTED_TASKS,
    config_digest,
    load_config,
    method_spec,
    seed_set,
)
from .environment import derive_seed
from .io import run_directory, validate_run_directory
from .provenance import (
    REPOSITORY_ROOT,
    atomic_write_text,
    input_set_sha256,
    sha256_file,
    write_json,
)
from .statistics import (
    clopper_pearson_interval,
    clopper_pearson_upper_bound,
    describe,
    four_corner_rank_tolerance_contrasts,
    paired_seed_bootstrap,
)


class AggregateError(RuntimeError):
    """Raised when raw evidence is incomplete or internally inconsistent."""


def _assert_finite_json(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _assert_finite_json(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_finite_json(child, path=f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise AggregateError(f"nonfinite value at {path}")


def _profile_seeds(config: Mapping[str, Any], profile: str) -> tuple[int, ...]:
    explicit = config.get("seeds")
    if isinstance(explicit, list):
        return tuple(int(value) for value in explicit)
    if profile == "full":
        return seed_set(config, "evaluation")
    raise AggregateError(f"profile {profile!r} has no seed list")


def _load_rounds(path: Path, expected: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="ascii") as handle:
        for line in handle:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise AggregateError(f"non-object round record in {path}")
            _assert_finite_json(value)
            records.append(value)
    if len(records) != expected:
        raise AggregateError(f"{path} has {len(records)} rounds, expected {expected}")
    return records


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError as error:
        raise AggregateError(f"raw input is outside the repository: {path}") from error


def _mean_or_none(values: Iterable[Any]) -> float | None:
    selected = [float(value) for value in values if value is not None]
    return float(np.mean(selected)) if selected else None


def _ratio_mean(
    records: Sequence[Mapping[str, Any]], numerator: str, denominator: str
) -> tuple[float | None, int]:
    ratios: list[float] = []
    zeros = 0
    for record in records:
        left = record.get(numerator)
        right = record.get(denominator)
        if left is None or right is None:
            continue
        denominator_value = float(right)
        if denominator_value == 0.0:
            zeros += 1
        else:
            ratios.append(float(left) / denominator_value)
    return (float(np.mean(ratios)) if ratios else None), zeros


def _run_metrics(
    records: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    prefix: int,
) -> dict[str, Any]:
    selected = records[:prefix]
    last = selected[-1]
    d_ratio, d_zeros = _ratio_mean(selected, "D_Q", "d_Th")
    tail_ratio, tail_zeros = _ratio_mean(
        selected, "nystrom_trace_tail", "nystrom_operator_tail"
    )
    return {
        "cumulative_regret": float(last["cumulative_pseudo_regret"]),
        "action_accuracy": (
            float(np.mean([bool(record["action_correct"]) for record in selected]))
            if last.get("action_correct") is not None
            else None
        ),
        "simultaneous_reference_confidence": bool(
            all(bool(record["reference_confidence_all_actions"]) for record in selected)
        ),
        "simultaneous_method_optimism": bool(
            all(bool(record["method_optimism_all_actions"]) for record in selected)
        ),
        "theorem_applicable": bool(last["theorem_applicable"]),
        "theorem_bound_nonvacuous": (
            bool(
                float(last["sharp_theorem_rhs"])
                < float(last["cumulative_trivial_regret_bound"])
            )
            if last.get("sharp_theorem_rhs") is not None
            else None
        ),
        "sharp_theorem_rhs": last.get("sharp_theorem_rhs"),
        "trivial_regret_bound": float(last["cumulative_trivial_regret_bound"]),
        "zero_regret": float(last["cumulative_pseudo_regret"]) == 0.0,
        "algorithm_seconds": float(
            sum(float(record["algorithm_seconds"]) for record in selected)
        ),
        "operator_construction_seconds": float(
            sum(float(record["operator_construction_seconds"]) for record in selected)
        ),
        "transport_certificate_seconds": float(
            sum(float(record["transport_certificate_seconds"]) for record in selected)
        ),
        "action_scoring_seconds": float(
            sum(float(record["action_scoring_seconds"]) for record in selected)
        ),
        "representation_update_seconds": float(
            sum(float(record["representation_update_seconds"]) for record in selected)
        ),
        "diagnostic_seconds": float(
            sum(float(record["diagnostic_seconds"]) for record in selected)
        ),
        "end_to_end_round_seconds": float(
            sum(float(record["end_to_end_round_seconds"]) for record in selected)
        ),
        "data_loading_seconds": float(summary["data_loading_seconds"]),
        "preprocessing_seconds": float(summary["preprocessing_seconds"]),
        "teacher_environment_seconds": float(summary["teacher_environment_seconds"]),
        "peak_rss_bytes": int(summary["policy_peak_rss_bytes"]),
        "logical_operator_bytes": int(
            max(int(record["operator_storage_bytes"]) for record in selected)
        ),
        "cg_iterations": int(
            sum(int(record["solver_iterations_all_actions"]) for record in selected)
        ),
        "cg_matvecs": int(
            sum(
                int(record["solver_algorithm_matvecs_all_actions"])
                + int(record["solver_audit_matvecs_all_actions"])
                for record in selected
            )
        ),
        "solver_seconds": float(
            sum(float(record["solver_seconds_all_actions"]) for record in selected)
        ),
        "D_Q_minus_d_Th": _mean_or_none(
            record.get("D_Q_minus_d_Th") for record in selected
        ),
        "D_Q_over_d_Th": d_ratio,
        "D_Q_over_d_Th_zero_denominators": d_zeros,
        "trace_tail_over_operator_tail": tail_ratio,
        "trace_tail_over_operator_tail_zero_denominators": tail_zeros,
        "kappa_minus": _mean_or_none(record.get("kappa_minus") for record in selected),
        "oracle_kappa_minus": _mean_or_none(
            record.get("nystrom_oracle_generalized_kappa_minus") for record in selected
        ),
        "width_upper_over_exact": _mean_or_none(
            record.get("solver_upper_over_exact") for record in selected
        ),
        "solver_alpha": _mean_or_none(
            record.get("solver_alpha") for record in selected
        ),
        "fraction_bonus_below_gap": float(
            np.mean(
                [bool(record["bonus_below_true_action_gap"]) for record in selected]
            )
        ),
        "fraction_bonus_exceeds_range": float(
            np.mean(
                [
                    float(record["selected_confidence_bonus"])
                    > float(record["reward_range"])
                    for record in selected
                ]
            )
        ),
        "historical_misspecification_envelope": _mean_or_none(
            record.get("historical_misspecification_envelope") for record in selected
        ),
        "current_misspecification_envelope": _mean_or_none(
            record.get("current_misspecification_envelope") for record in selected
        ),
        "deterministic_failure": False,
        "float64_diagnostic_pass": True,
        "verified_numerical_certificate": False,
    }


def _metric_summary(
    rows: Sequence[Mapping[str, Any]], field: str
) -> dict[str, Any] | None:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    return describe(values) if values else None


def _method_statistics(run_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for row in run_rows:
        grouped[(str(row["task"]), str(row["method"]), int(row["prefix"]))].append(row)
    output: list[dict[str, Any]] = []
    numeric_fields = (
        "cumulative_regret",
        "action_accuracy",
        "algorithm_seconds",
        "operator_construction_seconds",
        "transport_certificate_seconds",
        "action_scoring_seconds",
        "representation_update_seconds",
        "diagnostic_seconds",
        "end_to_end_round_seconds",
        "data_loading_seconds",
        "preprocessing_seconds",
        "teacher_environment_seconds",
        "peak_rss_bytes",
        "logical_operator_bytes",
        "cg_iterations",
        "cg_matvecs",
        "solver_seconds",
        "D_Q_minus_d_Th",
        "D_Q_over_d_Th",
        "trace_tail_over_operator_tail",
        "kappa_minus",
        "oracle_kappa_minus",
        "width_upper_over_exact",
        "solver_alpha",
        "fraction_bonus_below_gap",
        "fraction_bonus_exceeds_range",
        "historical_misspecification_envelope",
        "current_misspecification_envelope",
    )
    for key in sorted(grouped):
        task, method, prefix = key
        rows = sorted(grouped[key], key=lambda row: int(row["seed"]))
        reference_successes = sum(
            bool(row["simultaneous_reference_confidence"]) for row in rows
        )
        optimism_successes = sum(
            bool(row["simultaneous_method_optimism"]) for row in rows
        )
        total = len(rows)
        output.append(
            {
                "task": task,
                "method": method,
                "prefix": prefix,
                "seed_count": total,
                "metrics": {
                    field: _metric_summary(rows, field) for field in numeric_fields
                },
                "reference_confidence": {
                    "successes": reference_successes,
                    "total": total,
                    "proportion": reference_successes / total,
                    "clopper_pearson_95": clopper_pearson_interval(
                        reference_successes, total
                    ),
                    "one_sided_upper_95": clopper_pearson_upper_bound(
                        reference_successes, total
                    ),
                    "role": rows[0]["confidence_role"],
                },
                "method_optimism": {
                    "successes": optimism_successes,
                    "total": total,
                    "proportion": optimism_successes / total,
                    "clopper_pearson_95": clopper_pearson_interval(
                        optimism_successes, total
                    ),
                    "one_sided_upper_95": clopper_pearson_upper_bound(
                        optimism_successes, total
                    ),
                    "role": rows[0]["confidence_role"],
                },
                "theorem_bound_nonvacuous": {
                    "applicable_runs": sum(
                        row["theorem_bound_nonvacuous"] is not None for row in rows
                    ),
                    "successes": sum(
                        row["theorem_bound_nonvacuous"] is True for row in rows
                    ),
                },
                "zero_regret_count": sum(bool(row["zero_regret"]) for row in rows),
                "D_Q_over_d_Th_zero_denominators": sum(
                    int(row["D_Q_over_d_Th_zero_denominators"]) for row in rows
                ),
                "trace_tail_over_operator_tail_zero_denominators": sum(
                    int(row["trace_tail_over_operator_tail_zero_denominators"])
                    for row in rows
                ),
            }
        )
    return output


def _paired_comparisons(
    run_rows: Sequence[Mapping[str, Any]],
    *,
    maximum_prefix: int,
    selection: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    lookup = {
        (str(row["task"]), str(row["method"]), int(row["seed"])): row
        for row in run_rows
        if int(row["prefix"]) == maximum_prefix
    }
    controlled = EXPECTED_TASKS[1:]
    comparisons: list[tuple[str, str, str]] = []
    for task in controlled:
        comparisons.extend(
            (
                (
                    task,
                    "transport_exact_corrected_cholesky",
                    "frozen_reference_corrected_cholesky",
                ),
                (
                    task,
                    "transport_exact_corrected_cholesky",
                    "naive_current_corrected_cholesky",
                ),
                (
                    task,
                    "transport_exact_corrected_cholesky",
                    "transport_exact_uncorrected_tangent_cholesky",
                ),
                (
                    task,
                    "transport_exact_corrected_cg_1e-4",
                    "transport_exact_corrected_cholesky",
                ),
            )
        )
        if selection is not None:
            practical = selection.get("practical_nystrom", {})
            if isinstance(practical, Mapping) and task in practical:
                comparisons.append(
                    (
                        task,
                        str(practical[task]),
                        "transport_exact_corrected_cholesky",
                    )
                )
    comparisons.append(
        (
            "covtype_label_bandit",
            "transport_exact_corrected_cholesky",
            "linucb_fixed_features",
        )
    )
    output: list[dict[str, Any]] = []
    for task, first, second in comparisons:
        first_values = {
            seed: float(row["cumulative_regret"])
            for (row_task, method, seed), row in lookup.items()
            if row_task == task and method == first
        }
        second_values = {
            seed: float(row["cumulative_regret"])
            for (row_task, method, seed), row in lookup.items()
            if row_task == task and method == second
        }
        result = paired_seed_bootstrap(
            first_values,
            second_values,
            bootstrap_seed=derive_seed(
                0, "realistic_transport/bootstrap/v1", task, first, second
            ),
        )
        output.append(
            {
                "task": task,
                "first": first,
                "second": second,
                "metric": "cumulative_regret",
                "prefix": maximum_prefix,
                "estimate": result,
            }
        )
    return output


def _rank_tolerance_effects(
    run_rows: Sequence[Mapping[str, Any]], maximum_prefix: int
) -> list[dict[str, Any]]:
    corner_methods = tuple(
        method
        for method in APPROXIMATE_METHODS
        if method_spec(method).rank in {16, 64}
        and method_spec(method).cg_tolerance in {1e-2, 1e-6}
    )
    metrics = {
        "cumulative_regret": lambda row: float(row["cumulative_regret"]),
        "log_algorithm_seconds": lambda row: math.log(
            max(float(row["algorithm_seconds"]), np.finfo(float).tiny)
        ),
        "logical_operator_bytes": lambda row: float(row["logical_operator_bytes"]),
        "width_upper_over_exact": lambda row: row["width_upper_over_exact"],
        "theorem_bound_nonvacuous": lambda row: (
            float(row["theorem_bound_nonvacuous"])
            if row["theorem_bound_nonvacuous"] is not None
            else None
        ),
    }
    output: list[dict[str, Any]] = []
    for task in EXPECTED_TASKS:
        task_rows = [
            row
            for row in run_rows
            if row["task"] == task
            and row["method"] in corner_methods
            and int(row["prefix"]) == maximum_prefix
        ]
        for metric, transform in metrics.items():
            observations: list[tuple[int, int, float, float]] = []
            for row in task_rows:
                value = transform(row)
                if value is None:
                    continue
                spec = method_spec(str(row["method"]))
                assert spec.rank is not None and spec.cg_tolerance is not None
                observations.append(
                    (int(row["seed"]), spec.rank, spec.cg_tolerance, float(value))
                )
            if not observations:
                continue
            try:
                estimate = four_corner_rank_tolerance_contrasts(
                    observations,
                    low_rank=16,
                    high_rank=64,
                    loose_tolerance=1e-2,
                    tight_tolerance=1e-6,
                    bootstrap_seed=derive_seed(
                        0,
                        "realistic_transport/rank_tolerance_bootstrap/v1",
                        task,
                        metric,
                    ),
                )
            except ValueError as error:
                raise AggregateError(
                    f"incomplete rank/tolerance cells for {task}/{metric}: {error}"
                ) from error
            output.append({"task": task, "metric": metric, "estimate": estimate})
    return output


def aggregate_profile(
    *,
    config_path: str | Path,
    profile: str,
    raw_root: str | Path,
    output_path: str | Path,
    selection_path: str | Path | None = None,
) -> dict[str, Any]:
    config = load_config(config_path, profile)
    seeds = _profile_seeds(config, profile)
    rounds = int(config["rounds"])
    prefixes = tuple(
        sorted(
            {
                rounds,
                *(
                    int(value)
                    for value in config["horizons"]["prefixes"]
                    if int(value) <= rounds
                ),
            }
        )
    )
    expected = {
        (task, method, seed)
        for task in EXPECTED_TASKS
        for method in EXPECTED_METHODS
        for seed in seeds
    }
    root = Path(raw_root)
    profile_root = root / profile
    actual: set[tuple[str, str, int]] = set()
    if profile_root.exists():
        for summary_path in profile_root.glob("*/*/seed-*/summary.json"):
            task = summary_path.parents[2].name
            method = summary_path.parents[1].name
            seed_text = summary_path.parent.name
            if not seed_text.startswith("seed-"):
                continue
            actual.add((task, method, int(seed_text.removeprefix("seed-"))))
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    failures = (
        sorted(profile_root.glob("*/*/seed-*/failure.json"))
        if profile_root.exists()
        else []
    )
    if missing or extra or failures:
        raise AggregateError(
            f"raw grid mismatch: missing={missing[:5]} ({len(missing)} total), "
            f"extra={extra[:5]} ({len(extra)} total), failures={len(failures)}"
        )

    expected_config_digest = config_digest(config)
    common_fields: dict[str, Any] = {}
    raw_inventory: list[dict[str, str]] = []
    run_rows: list[dict[str, Any]] = []
    for task, method, seed in sorted(expected):
        directory = run_directory(
            root, phase=profile, task=task, method=method, seed=seed
        )
        validated = validate_run_directory(directory)
        manifest = validated["manifest"]
        summary = validated["summary"]
        _assert_finite_json(manifest)
        _assert_finite_json(summary)
        if manifest.get("config_digest") != expected_config_digest:
            raise AggregateError(f"mixed config digest in {directory}")
        if int(manifest.get("rounds", -1)) != rounds:
            raise AggregateError(f"wrong horizon in {directory}")
        for field in (
            "source_inventory_sha256",
            "source_branch",
            "source_revision",
            "source_dirty",
            "prepared_data",
            "split",
            "preprocessing_digest",
            "preprocessing_artifact",
            "selection_artifact_sha256",
            "freeze_revision",
            "selection_lock_revision",
        ):
            value = manifest.get(field)
            if field not in common_fields:
                common_fields[field] = value
            elif common_fields[field] != value:
                raise AggregateError(f"mixed {field} in {directory}")
        if profile == "full" and manifest.get("source_dirty") is not False:
            raise AggregateError(
                f"full evaluation run is not from a clean tree: {directory}"
            )
        records = _load_rounds(directory / "rounds.jsonl", rounds)
        for record in records:
            if (
                record.get("task") != task
                or record.get("method") != method
                or int(record.get("seed", -1)) != seed
            ):
                raise AggregateError(f"run identity mismatch in {directory}")
        for name in (
            "manifest.json",
            "manifest.json.sha256",
            "rounds.jsonl",
            "rounds.jsonl.sha256",
            "summary.json",
            "summary.json.sha256",
        ):
            path = directory / name
            raw_inventory.append({"path": _relative(path), "sha256": sha256_file(path)})
        for prefix in prefixes:
            metrics = _run_metrics(records, summary, prefix)
            run_rows.append(
                {
                    "task": task,
                    "method": method,
                    "seed": seed,
                    "prefix": prefix,
                    "confidence_role": records[prefix - 1]["confidence_role"],
                    **metrics,
                }
            )

    selection: dict[str, Any] | None = None
    if selection_path is not None:
        selection = json.loads(Path(selection_path).read_text(encoding="utf-8"))
        if sha256_file(selection_path) != common_fields["selection_artifact_sha256"]:
            raise AggregateError("selection artifact hash differs from raw manifests")
    aggregate = {
        "schema_version": 1,
        "protocol_version": config["protocol_version"],
        "profile": profile,
        "publication_evidence": profile == "full"
        and config.get("dataset_mode") == "covtype",
        "config_digest": expected_config_digest,
        "expected_cell_count": len(expected),
        "accepted_cell_count": len(expected),
        "rounds_per_cell": rounds,
        "prefixes": list(prefixes),
        "seeds": list(seeds),
        "tasks": list(EXPECTED_TASKS),
        "methods": list(EXPECTED_METHODS),
        "common_provenance": common_fields,
        "raw_input_inventory": sorted(raw_inventory, key=lambda item: item["path"]),
        "raw_input_inventory_sha256": input_set_sha256(raw_inventory),
        "run_level_metrics": run_rows,
        "method_statistics": _method_statistics(run_rows),
        "paired_primary_comparisons": _paired_comparisons(
            run_rows, maximum_prefix=rounds, selection=selection
        ),
        "rank_tolerance_effects": _rank_tolerance_effects(run_rows, rounds),
        "formal_p_values_reported": False,
        "verified_numerical_certificates": False,
    }
    write_json(output_path, aggregate)
    return aggregate


def write_statistics_csv(aggregate: Mapping[str, Any], path: str | Path) -> Path:
    fields = (
        "task",
        "method",
        "prefix",
        "seed_count",
        "metric",
        "mean",
        "standard_error",
        "median",
        "q10",
        "q25",
        "q75",
        "q90",
        "iqr",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for cell in aggregate["method_statistics"]:
        for metric, values in sorted(cell["metrics"].items()):
            if values is None:
                continue
            writer.writerow(
                {
                    "task": cell["task"],
                    "method": cell["method"],
                    "prefix": cell["prefix"],
                    "seed_count": cell["seed_count"],
                    "metric": metric,
                    "mean": values["mean"],
                    "standard_error": values["standard_error"],
                    "median": values["median"],
                    "q10": values["q10"],
                    "q25": values["q25"],
                    "q75": values["q75"],
                    "q90": values["q90"],
                    "iqr": values["iqr"],
                }
            )
    destination = atomic_write_text(path, output.getvalue())
    atomic_write_text(
        destination.with_name(destination.name + ".sha256"),
        f"{sha256_file(destination)}  {destination.name}\n",
    )
    return destination


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
    parser.add_argument(
        "--raw-root", type=Path, default=Path("results/raw/realistic_transport")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("review/realistic_transport/AGGREGATE.json"),
    )
    parser.add_argument(
        "--statistics-csv",
        type=Path,
        default=Path("review/realistic_transport/STATISTICAL_RESULTS.csv"),
    )
    parser.add_argument("--selection", type=Path, default=None)
    args = parser.parse_args(argv)
    aggregate = aggregate_profile(
        config_path=args.config,
        profile=args.profile,
        raw_root=args.raw_root,
        output_path=args.output,
        selection_path=args.selection,
    )
    write_statistics_csv(aggregate, args.statistics_csv)
    print(
        json.dumps(
            {"aggregate": str(args.output), "cells": aggregate["accepted_cell_count"]},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
