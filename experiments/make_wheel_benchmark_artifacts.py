"""Build a provenance-bound report from executed Wheel benchmark policies."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .aggregate_results import student_t_interval, write_aggregate_with_provenance
from .config import get_seed_set, load_config
from .logging_utils import canonical_json
from .run_wheel_benchmark import (
    CONTROL_METHODS,
    METHODS,
    METHOD_IMPLEMENTATIONS,
    cells,
    hyperparameter_grid,
    load_tuning_selection,
    validate_tuning_selection,
    validate_wheel_config,
)
from .wheel_environment import ACTION_COUNT, SAFE_ACTION, WheelSpecification


DEFAULT_CONFIG = Path("experiments/configs/wheel_benchmark.yaml")
DEFAULT_RAW_ROOT = Path("results/raw/wheel_benchmark/full/evaluation")
DEFAULT_SELECTION = Path("results/raw/wheel_benchmark/full/tuning_selection.json")
DEFAULT_OUTPUT = Path("results/derived/wheel_benchmark_full.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"{path} must contain JSON-object records")
    return rows


def _load_single(path: Path) -> dict[str, Any]:
    rows = _load_jsonl(path)
    if len(rows) != 1:
        raise ValueError(f"{path} must contain exactly one record")
    return rows[0]


def _metrics(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("metrics")
    if not isinstance(value, Mapping):
        raise ValueError("raw record lacks a metrics object")
    return value


def _interval(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, Any]:
    return student_t_interval(float(row[key]) for row in rows)


def _bind_tuning_inputs(
    config: Mapping[str, Any],
    selection: Mapping[str, Any],
    tuning_root: Path,
    input_paths: set[Path],
) -> None:
    raw_candidates = selection.get("candidates")
    if not isinstance(raw_candidates, list):
        raise ValueError("selection artifact lacks tuning candidates")
    candidates = {
        (str(item["method"]), float(item["ridge"]), float(item["bonus_scale"])): item
        for item in raw_candidates
    }
    streams: dict[int, set[str]] = {
        seed: set() for seed in get_seed_set(config, "tuning")
    }
    for method in METHODS:
        for ridge, bonus in hyperparameter_grid(config, method):
            candidate = candidates[(method, ridge, bonus)]
            per_cell = {
                (float(row["delta"]), int(row["seed"])): float(
                    row["cumulative_pseudo_regret"]
                )
                for row in candidate["per_cell_cumulative_pseudo_regret"]
            }
            for cell in cells(config):
                for seed in get_seed_set(config, "tuning"):
                    directory = (
                        tuning_root
                        / cell.token
                        / method
                        / f"ridge-{ridge:g}_bonus-{bonus:g}"
                        / f"seed-{seed}"
                    )
                    row = _load_single(directory / "summary.jsonl")
                    manifest = _load_single(directory / "manifest.jsonl")
                    execution = manifest.get("config", {}).get("execution", {})
                    if (
                        row.get("method") != method
                        or row.get("phase") != "tuning"
                        or int(row.get("seed", -1)) != seed
                        or float(row.get("delta", -1.0)) != cell.delta
                        or row.get("hyperparameters")
                        != {"ridge": ridge, "bonus_scale": bonus}
                        or execution.get("cell")
                        != {"delta": cell.delta, "token": cell.token}
                    ):
                        raise ValueError(
                            f"tuning summary identity mismatch: {directory}"
                        )
                    if not math.isclose(
                        float(row["cumulative_pseudo_regret"]),
                        per_cell[(cell.delta, seed)],
                        rel_tol=0.0,
                        abs_tol=1.0e-12,
                    ):
                        raise ValueError(
                            "selection value disagrees with its tuning raw row"
                        )
                    streams[seed].add(str(row["environment_stream_sha256"]))
                    for name in ("manifest.jsonl", "raw.jsonl", "summary.jsonl"):
                        input_paths.add(directory / name)
    if any(len(digests) != 1 for digests in streams.values()):
        raise ValueError("tuning cells do not share one stream within each seed")


def build_artifact(
    *,
    config_path: Path = DEFAULT_CONFIG,
    raw_root: Path = DEFAULT_RAW_ROOT,
    selection_path: Path = DEFAULT_SELECTION,
    profile: str = "full",
) -> dict[str, Any]:
    config = load_config(config_path, profile=profile)
    validate_wheel_config(config)
    configured_cells = cells(config)
    evaluation_seeds = tuple(get_seed_set(config, "evaluation"))
    tuning_seeds = tuple(get_seed_set(config, "tuning"))
    if set(evaluation_seeds) & set(tuning_seeds):
        raise ValueError("tuning and evaluation seeds overlap")
    if profile == "full" and evaluation_seeds != tuple(range(3000, 3050)):
        raise ValueError("the full Wheel report requires evaluation seeds 3000--3049")
    if profile == "full" and tuning_seeds != tuple(range(2000, 2010)):
        raise ValueError("the full Wheel report requires tuning seeds 2000--2009")
    if profile == "full" and int(config["rounds"]) != 5000:
        raise ValueError("the full Wheel report requires horizon 5000")
    if profile == "full" and int(config["tuning_rounds"]) != 5000:
        raise ValueError("the full Wheel tuning runs require horizon 5000")
    selection = load_tuning_selection(selection_path)
    selected = validate_tuning_selection(config, selection)
    selection_payload_sha256 = hashlib.sha256(
        canonical_json(selection).encode("ascii")
    ).hexdigest()
    if selection.get("evaluation_outcomes_used") is not False:
        raise ValueError("evaluation outcomes must not enter model selection")

    input_paths = {config_path, selection_path}
    _bind_tuning_inputs(config, selection, raw_root.parent / "tuning", input_paths)
    summaries: dict[tuple[float, str], list[dict[str, Any]]] = {
        (cell.delta, method): [] for cell in configured_cells for method in METHODS
    }
    raw: dict[tuple[float, str, int], list[dict[str, Any]]] = {}
    stream_digests: dict[int, set[str]] = {seed: set() for seed in evaluation_seeds}
    seed_level: list[dict[str, Any]] = []
    for cell in configured_cells:
        for method in METHODS:
            ridge, bonus = selected[method]
            for seed in evaluation_seeds:
                directory = raw_root / cell.token / method / f"seed-{seed}"
                summary = _load_single(directory / "summary.jsonl")
                manifest = _load_single(directory / "manifest.jsonl")
                rows = _load_jsonl(directory / "raw.jsonl")
                execution = manifest.get("config", {}).get("execution", {})
                if (
                    summary.get("method") != method
                    or int(summary.get("seed", -1)) != seed
                    or float(summary.get("delta", -1.0)) != cell.delta
                    or summary.get("phase") != "evaluation"
                    or summary.get("executed_policy") is not True
                    or execution.get("cell")
                    != {"delta": cell.delta, "token": cell.token}
                    or execution.get("tuning_selection_sha256")
                    != selection_payload_sha256
                    or execution.get("pooled_over_all_declared_deltas") is not True
                ):
                    raise ValueError(
                        f"evaluation summary identity mismatch: {directory}"
                    )
                if summary.get("hyperparameters") != {
                    "ridge": ridge,
                    "bonus_scale": bonus,
                }:
                    raise ValueError(
                        "evaluation hyperparameters were not selected by pooled tuning"
                    )
                if summary.get("pooled_tuning_setting") is not True:
                    raise ValueError("evaluation summary lacks pooled-tuning provenance")
                if len(rows) != int(config["rounds"]):
                    raise ValueError(
                        f"evaluation trajectory is incomplete: {directory}"
                    )
                metrics = [_metrics(row) for row in rows]
                if any(
                    item.get("method") != method
                    or float(item.get("delta", -1.0)) != cell.delta
                    for item in metrics
                ):
                    raise ValueError("raw method/cell identity mismatch")
                digest = str(summary["environment_stream_sha256"])
                if any(
                    item.get("environment_stream_sha256") != digest
                    for item in metrics
                ):
                    raise ValueError("raw stream digest disagrees with the summary")
                stream_digests[seed].add(digest)
                summaries[(cell.delta, method)].append(summary)
                raw[(cell.delta, method, seed)] = rows
                seed_level.append(
                    {
                        "delta": cell.delta,
                        "method": method,
                        "seed": seed,
                        "ridge": ridge,
                        "bonus_scale": bonus,
                        "cumulative_pseudo_regret": summary[
                            "cumulative_pseudo_regret"
                        ],
                        "cumulative_reward": summary["cumulative_reward"],
                        "optimal_action_rate": summary["optimal_action_rate"],
                        "environment_stream_sha256": digest,
                    }
                )
                for name in ("manifest.jsonl", "raw.jsonl", "summary.jsonl"):
                    input_paths.add(directory / name)
    if any(len(values) != 1 for values in stream_digests.values()):
        raise ValueError("methods do not share one Wheel stream within each seed")

    oracle_metrics = [
        _metrics(row)
        for cell in configured_cells
        for seed in evaluation_seeds
        for row in raw[(cell.delta, "oracle", seed)]
    ]
    if any(
        float(item["instantaneous_pseudo_regret"]) != 0.0
        or item.get("selected_action") != item.get("optimal_action_posthoc")
        or item.get("uses_privileged_pre_action_oracle") is not True
        for item in oracle_metrics
    ):
        raise ValueError("oracle control is not an exact privileged zero-regret control")
    safe_metrics = [
        _metrics(row)
        for cell in configured_cells
        for seed in evaluation_seeds
        for row in raw[(cell.delta, "safe", seed)]
    ]
    if any(
        int(item["selected_action"]) != SAFE_ACTION
        or item.get("uses_privileged_pre_action_oracle") is not False
        for item in safe_metrics
    ):
        raise ValueError("safe control is not fixed and oracle-free")
    random_metrics = [
        _metrics(row)
        for cell in configured_cells
        for seed in evaluation_seeds
        for row in raw[(cell.delta, "random", seed)]
    ]
    if any(item.get("uses_privileged_pre_action_oracle") is not False for item in random_metrics):
        raise ValueError("random control used privileged oracle information")

    summary_metric_names = (
        "cumulative_pseudo_regret",
        "cumulative_reward",
        "mean_reward",
        "optimal_action_rate",
        "runtime_seconds",
        "state_update_seconds",
        "uncertainty_seconds",
        "peak_host_memory_bytes",
        "peak_host_rss_delta_bytes",
        "maximum_persistent_numeric_policy_state_bytes",
    )
    method_results: dict[str, Any] = {}
    for method in METHODS:
        by_delta: list[dict[str, Any]] = []
        for cell in configured_cells:
            rows = summaries[(cell.delta, method)]
            horizon_rows: list[dict[str, Any]] = []
            for horizon in config["horizons"]:
                horizon_rows.append(
                    {
                        "horizon": horizon,
                        "cumulative_pseudo_regret": student_t_interval(
                            float(
                                _metrics(
                                    raw[(cell.delta, method, seed)][horizon - 1]
                                )["cumulative_pseudo_regret"]
                            )
                            for seed in evaluation_seeds
                        ),
                        "optimal_action_rate": student_t_interval(
                            float(
                                _metrics(
                                    raw[(cell.delta, method, seed)][horizon - 1]
                                )["cumulative_optimal_action_rate"]
                            )
                            for seed in evaluation_seeds
                        ),
                    }
                )
            by_delta.append(
                {
                    "delta": cell.delta,
                    "evaluation_seed_count": len(rows),
                    "metrics": {
                        name: _interval(rows, name) for name in summary_metric_names
                    },
                    "horizons": horizon_rows,
                }
            )
        method_results[method] = {
            "method_implementation": METHOD_IMPLEMENTATIONS[method],
            "published_implementation_claim": False,
            "privileged_pre_action_oracle": method == "oracle",
            "selected_hyperparameters": summaries[
                (configured_cells[0].delta, method)
            ][0]["hyperparameters"],
            "selection_was_pooled_over_all_deltas": True,
            "evaluation_seed_count_per_delta": len(evaluation_seeds),
            "by_delta": by_delta,
        }
        if method == "cc_ucb_full_ggn_cg":
            method_results[method]["all_cg_solves_converged"] = all(
                bool(row["all_cg_solves_converged"])
                for cell in configured_cells
                for row in summaries[(cell.delta, method)]
            )

    paired_against_controls: list[dict[str, Any]] = []
    for cell in configured_cells:
        for control in ("random", "safe", "oracle"):
            for method in METHODS:
                if method == control:
                    continue
                method_by_seed = {
                    int(row["seed"]): row
                    for row in summaries[(cell.delta, method)]
                }
                control_by_seed = {
                    int(row["seed"]): row
                    for row in summaries[(cell.delta, control)]
                }
                differences = [
                    float(method_by_seed[seed]["cumulative_pseudo_regret"])
                    - float(control_by_seed[seed]["cumulative_pseudo_regret"])
                    for seed in evaluation_seeds
                ]
                paired_against_controls.append(
                    {
                        "delta": cell.delta,
                        "method": method,
                        "reference_control": control,
                        "difference_direction": "method_minus_control",
                        "pair_count": len(differences),
                        "cumulative_pseudo_regret": student_t_interval(differences),
                    }
                )
    input_records = [
        {"path": str(path), "sha256": _sha256(path)}
        for path in sorted(input_paths, key=lambda value: str(value))
    ]
    input_set_sha256 = hashlib.sha256(
        canonical_json(input_records).encode("ascii")
    ).hexdigest()
    return {
        "schema_version": 1,
        "event": "wheel_benchmark_report",
        "experiment": "wheel_benchmark",
        "profile": profile,
        "seed_set": "evaluation",
        "evaluation_seed_count": len(evaluation_seeds),
        "delta_count": len(configured_cells),
        "evaluation_run_count": len(configured_cells)
        * len(METHODS)
        * len(evaluation_seeds),
        "tuning_seed_count": len(tuning_seeds),
        "tuning_evaluation_seeds_disjoint": True,
        "evaluation_outcomes_used_for_tuning": False,
        "evaluation_policies_rerun_from_scratch": True,
        "common_context_and_noise_stream_within_seed_across_deltas": True,
        "pooled_tuning_over_all_deltas": True,
        "selection_artifact_sha256": _sha256(selection_path),
        "canonical_environment": {
            "context_distribution": "uniform_by_area_on_unit_disk",
            "action_count": ACTION_COUNT,
            "deltas": [cell.delta for cell in configured_cells],
            "inner_disk_probabilities": [
                {"delta": cell.delta, "probability": cell.delta * cell.delta}
                for cell in configured_cells
            ],
            "quadrant_actions": config["environment"]["quadrant_actions"],
            "strict_outer_threshold": True,
        },
        "control_invariants": {
            "oracle_zero_regret": True,
            "oracle_is_privileged_nonlearner": True,
            "safe_always_action_zero": True,
            "random_is_context_and_oracle_independent": True,
            "analytic_expected_one_round_pseudo_regret_by_delta": [
                {
                    "delta": cell.delta,
                    **{
                        method: WheelSpecification.from_mapping(
                            {**config["environment"], "delta": cell.delta}
                        ).expected_control_regret(method)
                        for method in ("random", "safe", "oracle")
                    },
                }
                for cell in configured_cells
            ],
        },
        "method_results": method_results,
        "seed_level_results": seed_level,
        "paired_comparisons_against_controls": paired_against_controls,
        "omitted_methods": config["omitted_methods"],
        "limitations": [
            "Local neural UCB/TS and current-GGN policies are diagnostic local implementations, not pinned reproductions of published NeuralUCB or NeuralTS code.",
            "LO-FI is excluded because this repository has no faithful pinned implementation.",
            "KFAC is excluded rather than presenting a local block approximation under a fidelity claim.",
            "The oracle is a privileged non-learner sanity control and is not a deployable contextual-bandit policy.",
        ],
        "inputs": input_records,
        "input_set_sha256": input_set_sha256,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--profile", choices=("smoke", "full"), default="full")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    artifact = build_artifact(
        config_path=args.config,
        raw_root=args.raw_root,
        selection_path=args.selection,
        profile=args.profile,
    )
    output, sidecar = write_aggregate_with_provenance(artifact, args.output)
    print(canonical_json({"output": str(output), "provenance_sidecar": str(sidecar)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_artifact"]
