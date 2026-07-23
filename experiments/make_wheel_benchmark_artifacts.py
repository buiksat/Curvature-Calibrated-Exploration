"""Build a provenance-bound report from executed Wheel benchmark policies."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib
import numpy as np
from matplotlib.lines import Line2D

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .aggregate_results import student_t_interval, write_aggregate_with_provenance
from .artifact_utils import (
    input_set_sha256,
    sha256_file,
    write_json_artifact,
    write_sha256_sidecar,
)
from .config import get_seed_set, load_config
from .logging_utils import canonical_json
from .run_wheel_benchmark import (
    CONTROL_METHODS,
    FIXED_HYPERPARAMETER_METHODS,
    FULL_NETWORK_METHODS,
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
DEFAULT_REGRET_FIGURE = Path("paper/figures/wheel_benchmark_policy_quality.pdf")
DEFAULT_COMPUTE_FIGURE = Path("paper/figures/wheel_benchmark_compute.pdf")
DEFAULT_TABLE = Path("tables/generated/wheel_benchmark_summary.tex")
DEFAULT_SMOKE_ROOT = Path("results/derived/wheel_benchmark/smoke")

DISPLAY_NAMES = {
    "cc_ucb_full_ggn_cg": "Current-GGN UCB",
    "local_neural_ucb": "Local neural UCB",
    "local_neural_ts": "Local neural TS",
    "all_layer_diagonal_ucb": "All-layer diagonal UCB",
    "local_neural_linear": "Local NeuralLinear-style",
    "frozen_backbone_last_layer_ucb": "Frozen last-layer UCB",
    "linucb": "LinUCB",
    "linear_ts": "Linear TS",
    "greedy": "Greedy",
    "random": "Random",
    "safe": "Safe",
    "oracle": "Oracle",
}
METHOD_COLORS = {
    "cc_ucb_full_ggn_cg": "#0072B2",
    "local_neural_ucb": "#D55E00",
    "local_neural_ts": "#CC79A7",
    "all_layer_diagonal_ucb": "#E6AB02",
    "local_neural_linear": "#6A3D9A",
    "frozen_backbone_last_layer_ucb": "#1F9E89",
    "linucb": "#009E73",
    "linear_ts": "#56B4E9",
    "greedy": "#A65628",
    "random": "#7F7F7F",
    "safe": "#E69F00",
    "oracle": "#111111",
}
METHOD_MARKERS = {
    "cc_ucb_full_ggn_cg": "o",
    "local_neural_ucb": "D",
    "local_neural_ts": "v",
    "all_layer_diagonal_ucb": "P",
    "local_neural_linear": "<",
    "frozen_backbone_last_layer_ucb": ">",
    "linucb": "s",
    "linear_ts": "^",
    "greedy": "h",
    "random": "X",
    "safe": "+",
    "oracle": "*",
}
DELTA_MARKERS = {0.5: "o", 0.7: "s", 0.9: "^", 0.95: "D"}
DELTA_POSITIONS = {delta: index for index, delta in enumerate(DELTA_MARKERS)}


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


def _optional_interval(
    rows: Sequence[Mapping[str, Any]], key: str
) -> dict[str, Any] | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    if not values:
        return None
    interval = student_t_interval(values)
    interval["requested_seed_count"] = len(rows)
    interval["undefined_seed_count"] = len(rows) - len(values)
    return interval


def _seed_diagnostics(
    specification: WheelSpecification,
    rows: Sequence[Mapping[str, Any]],
    *,
    method: str,
    bonus_scale: float,
) -> dict[str, Any]:
    metrics = [_metrics(row) for row in rows]
    outer = [row for row in metrics if bool(row["outer_region"])]
    inner = [row for row in metrics if not bool(row["outer_region"])]
    outside_rate = (
        float(
            np.mean(
                [
                    int(row["selected_action"]) == int(row["optimal_action_posthoc"])
                    and int(row["selected_action"]) != SAFE_ACTION
                    for row in outer
                ],
                dtype=np.float64,
            )
        )
        if outer
        else None
    )
    inside_rate = (
        float(
            np.mean(
                [int(row["selected_action"]) == SAFE_ACTION for row in inner],
                dtype=np.float64,
            )
        )
        if inner
        else None
    )

    coverage: float | None = None
    if method not in CONTROL_METHODS:
        hits = 0
        total = 0
        for row in metrics:
            context = np.asarray(row["context"], dtype=np.float64)
            predictions = np.asarray(
                row["predicted_means_all_actions"], dtype=np.float64
            )
            widths = np.asarray(row["predictive_widths_all_actions"], dtype=np.float64)
            if predictions.shape != (ACTION_COUNT,) or widths.shape != (ACTION_COUNT,):
                raise ValueError("Wheel prediction diagnostics have the wrong shape")
            if (
                np.any(widths < 0.0)
                or not np.all(np.isfinite(widths))
                or not np.all(np.isfinite(predictions))
            ):
                raise ValueError("Wheel prediction diagnostics are invalid")
            true_means = specification.mean_rewards(context)
            radii = specification.high_mean * bonus_scale * widths
            hits += int(np.count_nonzero(np.abs(true_means - predictions) <= radii))
            total += ACTION_COUNT
        coverage = float(hits / total)

    return {
        "outside_optimal_risky_rate": outside_rate,
        "inside_safe_action_rate": inside_rate,
        "empirical_all_action_coverage": coverage,
        "outer_round_count": len(outer),
        "inner_round_count": len(inner),
    }


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
    if profile == "full" and evaluation_seeds != tuple(range(3000, 3030)):
        raise ValueError("the full Wheel report requires evaluation seeds 3000--3029")
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
    seed_diagnostics: dict[tuple[float, str, int], dict[str, Any]] = {}
    stream_digests: dict[int, set[str]] = {seed: set() for seed in evaluation_seeds}
    seed_level: list[dict[str, Any]] = []
    for cell in configured_cells:
        specification = WheelSpecification.from_mapping(
            {**config["environment"], "delta": cell.delta}
        )
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
                    or summary.get("method_implementation")
                    != METHOD_IMPLEMENTATIONS[method]
                    or summary.get("published_implementation_claim") is not False
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
                    raise ValueError(
                        "evaluation summary lacks pooled-tuning provenance"
                    )
                expected_updates = (
                    int(config["rounds"]) if method in FULL_NETWORK_METHODS else 0
                )
                if (
                    summary.get("full_network_method")
                    is not (method in FULL_NETWORK_METHODS)
                    or int(summary.get("full_network_update_count", -1))
                    != expected_updates
                    or summary.get("matched_full_network_update_budget") is not True
                ):
                    raise ValueError(
                        "evaluation summary violates the neural update budget"
                    )
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
                    item.get("environment_stream_sha256") != digest for item in metrics
                ):
                    raise ValueError("raw stream digest disagrees with the summary")
                stream_digests[seed].add(digest)
                summaries[(cell.delta, method)].append(summary)
                raw[(cell.delta, method, seed)] = rows
                diagnostics = _seed_diagnostics(
                    specification,
                    rows,
                    method=method,
                    bonus_scale=bonus,
                )
                seed_diagnostics[(cell.delta, method, seed)] = diagnostics
                seed_level.append(
                    {
                        "delta": cell.delta,
                        "method": method,
                        "seed": seed,
                        "ridge": ridge,
                        "bonus_scale": bonus,
                        "cumulative_pseudo_regret": summary["cumulative_pseudo_regret"],
                        "cumulative_reward": summary["cumulative_reward"],
                        "optimal_action_rate": summary["optimal_action_rate"],
                        "environment_stream_sha256": digest,
                        **diagnostics,
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
        raise ValueError(
            "oracle control is not an exact privileged zero-regret control"
        )
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
    if any(
        item.get("uses_privileged_pre_action_oracle") is not False
        for item in random_metrics
    ):
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
            diagnostics = [
                seed_diagnostics[(cell.delta, method, seed)]
                for seed in evaluation_seeds
            ]
            horizon_rows: list[dict[str, Any]] = []
            for horizon in config["horizons"]:
                horizon_rows.append(
                    {
                        "horizon": horizon,
                        "cumulative_pseudo_regret": student_t_interval(
                            float(
                                _metrics(raw[(cell.delta, method, seed)][horizon - 1])[
                                    "cumulative_pseudo_regret"
                                ]
                            )
                            for seed in evaluation_seeds
                        ),
                        "optimal_action_rate": student_t_interval(
                            float(
                                _metrics(raw[(cell.delta, method, seed)][horizon - 1])[
                                    "cumulative_optimal_action_rate"
                                ]
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
                        **{
                            name: _interval(rows, name) for name in summary_metric_names
                        },
                        "outside_optimal_risky_rate": _optional_interval(
                            diagnostics, "outside_optimal_risky_rate"
                        ),
                        "inside_safe_action_rate": _optional_interval(
                            diagnostics, "inside_safe_action_rate"
                        ),
                        "empirical_all_action_coverage": _optional_interval(
                            diagnostics, "empirical_all_action_coverage"
                        ),
                    },
                    "horizons": horizon_rows,
                }
            )
        method_results[method] = {
            "method_implementation": METHOD_IMPLEMENTATIONS[method],
            "published_implementation_claim": False,
            "privileged_pre_action_oracle": method == "oracle",
            "selected_hyperparameters": summaries[(configured_cells[0].delta, method)][
                0
            ]["hyperparameters"],
            "selection_was_pooled_over_all_deltas": True,
            "full_network_method": method in FULL_NETWORK_METHODS,
            "full_network_updates_per_round": (
                1 if method in FULL_NETWORK_METHODS else 0
            ),
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
                    int(row["seed"]): row for row in summaries[(cell.delta, method)]
                }
                control_by_seed = {
                    int(row["seed"]): row for row in summaries[(cell.delta, control)]
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
        "evidence_scope": (
            "main-paper evaluation"
            if profile == "full"
            else "smoke-only engineering verification; not main-paper evidence"
        ),
        "seed_set": "evaluation",
        "rounds": int(config["rounds"]),
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
        "interval": {
            "confidence": 0.95,
            "method": "two-sided Student t interval",
            "unit": "one complete evaluation-seed trajectory",
            "regional_rates_computed_within_seed_before_aggregation": True,
        },
        "metric_definitions": {
            "outside_optimal_risky_rate": (
                "fraction of outer-region rounds selecting the quadrant-optimal "
                "risky action, computed within each seed"
            ),
            "inside_safe_action_rate": (
                "fraction of inner-region rounds selecting action zero, computed "
                "within each seed"
            ),
            "empirical_all_action_coverage": (
                "fraction of all action-round true means inside the reported reward-"
                "scale prediction plus-or-minus high_mean times bonus_scale times "
                "predictive width; controls are not applicable"
            ),
            "runtime_seconds": "complete evaluation-trajectory wall time",
            "peak_host_memory_bytes": "peak resident host memory during the run",
        },
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
            "Current-GGN, neural UCB/TS, all-layer diagonal, NeuralLinear-style, frozen-last-layer, and greedy policies are local diagnostic implementations; none is claimed to be an official or faithful published baseline implementation.",
            "LO-FI is excluded because this repository has no faithful pinned implementation.",
            "KFAC is excluded rather than presenting a local block approximation under a fidelity claim.",
            "The oracle is a privileged non-learner sanity control and is not a deployable contextual-bandit policy.",
        ],
        "inputs": input_records,
        "input_set_sha256": input_set_sha256,
    }


def _configure_pdf_fonts() -> None:
    matplotlib.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})


def _save_figure(figure: plt.Figure, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output,
        bbox_inches="tight",
        metadata={
            "Creator": "wheel_benchmark",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    plt.close(figure)
    write_sha256_sidecar(output)


def _method_rows(report: Mapping[str, Any], method: str) -> Sequence[Mapping[str, Any]]:
    method_results = report["method_results"]
    if not isinstance(method_results, Mapping):
        raise ValueError("Wheel report lacks method results")
    result = method_results[method]
    if not isinstance(result, Mapping) or not isinstance(result.get("by_delta"), list):
        raise ValueError(f"Wheel report lacks delta rows for {method}")
    return result["by_delta"]


def _plot_interval_series(
    axis: plt.Axes,
    rows: Sequence[Mapping[str, Any]],
    *,
    metric: str,
    method: str,
) -> None:
    defined = [
        row for row in rows if isinstance(row.get("metrics", {}).get(metric), Mapping)
    ]
    if not defined:
        return
    x = np.asarray(
        [DELTA_POSITIONS[float(row["delta"])] for row in defined],
        dtype=np.float64,
    )
    intervals = [row["metrics"][metric] for row in defined]
    means = np.asarray([float(item["mean"]) for item in intervals])
    low = np.asarray([float(item["ci95_low"]) for item in intervals])
    high = np.asarray([float(item["ci95_high"]) for item in intervals])
    linestyle = "--" if method in CONTROL_METHODS else "-"
    axis.errorbar(
        x,
        means,
        yerr=np.vstack((np.maximum(means - low, 0.0), np.maximum(high - means, 0.0))),
        color=METHOD_COLORS[method],
        marker=METHOD_MARKERS[method],
        linestyle=linestyle,
        linewidth=1.15,
        markersize=4.0,
        capsize=2.0,
        elinewidth=0.75,
        alpha=0.95,
    )


def _method_legend_handles(*, marker_by_method: bool = True) -> list[Line2D]:
    return [
        Line2D(
            [],
            [],
            color=METHOD_COLORS[method],
            marker=METHOD_MARKERS[method] if marker_by_method else None,
            linestyle=(
                ("--" if method in CONTROL_METHODS else "-")
                if marker_by_method
                else "-"
            ),
            linewidth=1.15 if marker_by_method else 2.5,
            markersize=4.5,
            label=DISPLAY_NAMES[method],
        )
        for method in METHODS
    ]


def make_policy_quality_figure(report: Mapping[str, Any], output: Path) -> None:
    _configure_pdf_fonts()
    figure, axes = plt.subplots(1, 3, figsize=(11.2, 4.15), sharex=True)
    specifications = (
        ("cumulative_pseudo_regret", "Terminal cumulative pseudo-regret"),
        ("outside_optimal_risky_rate", "Outer optimal-risky rate"),
        ("inside_safe_action_rate", "Inner safe-action rate"),
    )
    for axis, (metric, title) in zip(axes, specifications, strict=True):
        for method in METHODS:
            _plot_interval_series(
                axis,
                _method_rows(report, method),
                metric=metric,
                method=method,
            )
        axis.set_title(title, fontsize=9)
        axis.set_xlabel(r"Wheel radius $\delta$")
        axis.set_xticks(list(DELTA_POSITIONS.values()))
        axis.set_xticklabels(["0.50", "0.70", "0.90", "0.95"])
        axis.grid(alpha=0.22, linewidth=0.5)
    axes[0].set_ylabel("Cumulative pseudo-regret")
    axes[1].set_ylabel("Rate")
    for axis in axes[1:]:
        axis.set_ylim(-0.04, 1.04)
        axis.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
    top = 0.91
    if report["profile"] == "smoke":
        figure.suptitle(
            "Smoke verification only; not main-paper evidence",
            fontsize=9,
            color="#A12A2A",
        )
        top = 0.84
    figure.legend(
        handles=_method_legend_handles(),
        loc="lower center",
        bbox_to_anchor=(0.5, 0.015),
        ncol=4,
        frameon=False,
        fontsize=7.2,
        columnspacing=1.5,
        handlelength=2.0,
    )
    figure.subplots_adjust(left=0.07, right=0.99, bottom=0.36, top=top, wspace=0.28)
    _save_figure(figure, output)


def _scaled_interval(
    interval: Mapping[str, Any], scale: float
) -> tuple[float, float, float]:
    return (
        float(interval["mean"]) * scale,
        float(interval["ci95_low"]) * scale,
        float(interval["ci95_high"]) * scale,
    )


def _interval_error(
    mean: float, low: float, high: float, *, positive_axis: bool = False
) -> np.ndarray:
    lower = max(mean - low, 0.0)
    if positive_axis and mean > 0.0:
        lower = min(lower, mean * 0.95)
    upper = max(high - mean, 0.0)
    return np.asarray([[lower], [upper]], dtype=np.float64)


def make_compute_figure(report: Mapping[str, Any], output: Path) -> None:
    _configure_pdf_fonts()
    rounds = int(report["rounds"])
    figure, axes = plt.subplots(1, 2, figsize=(8.6, 4.25), sharey=True)
    for method in METHODS:
        for row in _method_rows(report, method):
            metrics = row["metrics"]
            regret = metrics["cumulative_pseudo_regret"]
            latency = metrics.get("runtime_seconds")
            memory = metrics.get("peak_host_memory_bytes")
            if not isinstance(regret, Mapping):
                continue
            regret_mean, regret_low, regret_high = _scaled_interval(regret, 1.0)
            yerr = _interval_error(regret_mean, regret_low, regret_high)
            delta = float(row["delta"])
            marker = DELTA_MARKERS[delta]
            for axis, interval, scale, positive_axis in (
                (axes[0], latency, 1000.0 / rounds, True),
                (axes[1], memory, 1.0 / 2**20, False),
            ):
                if not isinstance(interval, Mapping):
                    continue
                x_mean, x_low, x_high = _scaled_interval(interval, scale)
                if x_mean <= 0.0:
                    continue
                axis.errorbar(
                    x_mean,
                    regret_mean,
                    xerr=_interval_error(
                        x_mean, x_low, x_high, positive_axis=positive_axis
                    ),
                    yerr=yerr,
                    color=METHOD_COLORS[method],
                    marker=marker,
                    linestyle="none",
                    markersize=4.5,
                    capsize=1.8,
                    elinewidth=0.7,
                    alpha=0.85,
                )
    axes[0].set_xlabel("Mean latency (ms/round, log scale)")
    axes[0].set_xscale("log")
    axes[0].set_title("Latency versus regret", fontsize=9)
    axes[0].set_ylabel("Terminal cumulative pseudo-regret")
    axes[1].set_xlabel("Peak host RSS (MiB)")
    axes[1].set_title("Memory versus regret", fontsize=9)
    for axis in axes:
        axis.grid(alpha=0.22, linewidth=0.5)
    axes[1].legend(
        handles=[
            Line2D(
                [],
                [],
                color="#333333",
                marker=marker,
                linestyle="none",
                markersize=5,
                label=f"{delta:g}",
            )
            for delta, marker in DELTA_MARKERS.items()
        ],
        title=r"$\delta$",
        loc="upper right",
        frameon=False,
        fontsize=7,
        title_fontsize=7,
        ncol=2,
    )
    top = 0.92
    if report["profile"] == "smoke":
        figure.suptitle(
            "Smoke verification only; not main-paper evidence",
            fontsize=9,
            color="#A12A2A",
        )
        top = 0.84
    figure.legend(
        handles=_method_legend_handles(marker_by_method=False),
        loc="lower center",
        bbox_to_anchor=(0.5, 0.015),
        ncol=4,
        frameon=False,
        fontsize=7.2,
        columnspacing=1.4,
        handlelength=1.8,
    )
    figure.subplots_adjust(left=0.1, right=0.98, bottom=0.37, top=top, wspace=0.1)
    _save_figure(figure, output)


def _format_interval(
    interval: Mapping[str, Any] | None,
    *,
    digits: int,
    scale: float = 1.0,
) -> str:
    if interval is None:
        return "--"
    mean = float(interval["mean"]) * scale
    half_width = float(interval["ci95_half_width"]) * scale
    return rf"${mean:.{digits}f}\mathbin{{\pm}}{half_width:.{digits}f}$"


def make_table(report: Mapping[str, Any], output: Path) -> None:
    lines = [
        r"\begingroup",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{2.8pt}",
        r"\resizebox{0.98\linewidth}{!}{%",
        r"\begin{tabular}{llrrrrrrl}",
        r"\toprule",
        (
            r"Method & $\delta$ & Regret & Outer opt.-risky & Inner safe & "
            r"All-act. cov. & ms/round & Peak RSS MiB & $(\lambda,\beta)$ \\"
        ),
        r"\midrule",
    ]
    if report["profile"] == "smoke":
        lines.extend(
            (
                r"\multicolumn{9}{c}{\emph{Smoke verification only; not main-paper evidence.}} \\",
                r"\midrule",
            )
        )
    rounds = int(report["rounds"])
    method_results = report["method_results"]
    for method_index, method in enumerate(METHODS):
        selected = method_results[method]["selected_hyperparameters"]
        hyperparameters = (
            r"\textit{fixed}"
            if method in FIXED_HYPERPARAMETER_METHODS
            else rf"$({float(selected['ridge']):g},\,{float(selected['bonus_scale']):g})$"
        )
        for row in _method_rows(report, method):
            metrics = row["metrics"]
            lines.append(
                f"{DISPLAY_NAMES[method]} & {float(row['delta']):.2f} & "
                f"{_format_interval(metrics['cumulative_pseudo_regret'], digits=1)} & "
                f"{_format_interval(metrics['outside_optimal_risky_rate'], digits=3)} & "
                f"{_format_interval(metrics['inside_safe_action_rate'], digits=3)} & "
                f"{_format_interval(metrics['empirical_all_action_coverage'], digits=3)} & "
                f"{_format_interval(metrics['runtime_seconds'], digits=2, scale=1000.0 / rounds)} & "
                f"{_format_interval(metrics['peak_host_memory_bytes'], digits=1, scale=1.0 / 2**20)} & "
                f"{hyperparameters} \\\\"
            )
        if method_index != len(METHODS) - 1:
            lines.append(r"\addlinespace[1pt]")
    lines.extend((r"\bottomrule", r"\end{tabular}%", r"}", r"\endgroup"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="ascii")
    write_sha256_sidecar(output)


def _write_publication_provenance(
    artifact: Path,
    *,
    aggregate: Path,
    aggregate_provenance: Path,
    report: Mapping[str, Any],
) -> Path:
    inputs = sorted(
        [
            {"path": aggregate.as_posix(), "sha256": sha256_file(aggregate)},
            {
                "path": aggregate_provenance.as_posix(),
                "sha256": sha256_file(aggregate_provenance),
            },
        ],
        key=lambda item: item["path"],
    )
    provenance = artifact.with_name(artifact.name + ".provenance.json")
    write_json_artifact(
        provenance,
        {
            "schema_version": 1,
            "experiment": "wheel_benchmark",
            "artifact": artifact.as_posix(),
            "artifact_sha256": sha256_file(artifact),
            "profile": report["profile"],
            "evidence_scope": report["evidence_scope"],
            "inputs": inputs,
            "input_set_sha256": input_set_sha256(inputs),
            "generation_parameters": {
                "generator_source_sha256": sha256_file(Path(__file__)),
                "interval": report["interval"],
                "selection_artifact_sha256": report["selection_artifact_sha256"],
                "pdf_fonttype": 42 if artifact.suffix == ".pdf" else None,
            },
        },
    )
    return provenance


def write_artifacts(
    report: Mapping[str, Any],
    *,
    aggregate_path: Path,
    regret_figure_path: Path,
    compute_figure_path: Path,
    table_path: Path,
) -> dict[str, Any]:
    aggregate, aggregate_provenance = write_aggregate_with_provenance(
        report, aggregate_path
    )
    write_sha256_sidecar(aggregate)
    write_sha256_sidecar(aggregate_provenance)
    make_policy_quality_figure(report, regret_figure_path)
    make_compute_figure(report, compute_figure_path)
    make_table(report, table_path)
    artifacts = (regret_figure_path, compute_figure_path, table_path)
    publication_provenance = [
        _write_publication_provenance(
            artifact,
            aggregate=aggregate,
            aggregate_provenance=aggregate_provenance,
            report=report,
        )
        for artifact in artifacts
    ]
    return {
        "aggregate": aggregate.as_posix(),
        "aggregate_provenance": aggregate_provenance.as_posix(),
        "regret_figure": regret_figure_path.as_posix(),
        "compute_figure": compute_figure_path.as_posix(),
        "table": table_path.as_posix(),
        "publication_provenance": [path.as_posix() for path in publication_provenance],
        "evaluation_run_count": report["evaluation_run_count"],
        "input_set_sha256": report["input_set_sha256"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--profile", choices=("smoke", "full"), default="full")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--regret-figure", type=Path)
    parser.add_argument("--compute-figure", type=Path)
    parser.add_argument("--table", type=Path)
    args = parser.parse_args(argv)
    if args.profile == "full":
        aggregate_path = args.output or DEFAULT_OUTPUT
        regret_figure_path = args.regret_figure or DEFAULT_REGRET_FIGURE
        compute_figure_path = args.compute_figure or DEFAULT_COMPUTE_FIGURE
        table_path = args.table or DEFAULT_TABLE
    else:
        aggregate_path = args.output or Path(
            "results/derived/wheel_benchmark_smoke.json"
        )
        regret_figure_path = args.regret_figure or (
            DEFAULT_SMOKE_ROOT / DEFAULT_REGRET_FIGURE.name
        )
        compute_figure_path = args.compute_figure or (
            DEFAULT_SMOKE_ROOT / DEFAULT_COMPUTE_FIGURE.name
        )
        table_path = args.table or (DEFAULT_SMOKE_ROOT / DEFAULT_TABLE.name)
    artifact = build_artifact(
        config_path=args.config,
        raw_root=args.raw_root,
        selection_path=args.selection,
        profile=args.profile,
    )
    result = write_artifacts(
        artifact,
        aggregate_path=aggregate_path,
        regret_figure_path=regret_figure_path,
        compute_figure_path=compute_figure_path,
        table_path=table_path,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "build_artifact",
    "make_compute_figure",
    "make_policy_quality_figure",
    "make_table",
    "write_artifacts",
]
