"""Build the balanced-benchmark report with seed-level and paired provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .aggregate_results import (
    aggregate_results,
    student_t_interval,
    write_aggregate_with_provenance,
)
from .config import get_seed_set, load_config
from .logging_utils import canonical_json
from .run_balanced_benchmark import (
    CONTEXT_FREE_METHODS,
    configured_methods,
    hyperparameter_grid,
    load_tuning_selection,
    validate_tuning_selection,
    winner_counts,
)


DEFAULT_CONFIG = Path("experiments/configs/balanced_benchmark.yaml")
DEFAULT_RAW_ROOT = Path("results/raw/balanced_benchmark/full/evaluation")
DEFAULT_SELECTION = Path("results/raw/balanced_benchmark/full/tuning_selection.json")
DEFAULT_OUTPUT = Path("results/derived/balanced_benchmark_full.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_single_jsonl(path: Path) -> dict[str, Any]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    if len(lines) != 1:
        raise ValueError(f"{path} must contain exactly one JSON record")
    value = json.loads(lines[0])
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"{path} must contain JSON-object records")
    return rows


def _metric_interval(
    rows: Sequence[Mapping[str, Any]], name: str
) -> dict[str, Any]:
    return student_t_interval(float(row[name]) for row in rows)


def _record_metrics(record: Mapping[str, Any]) -> Mapping[str, Any]:
    metrics = record.get("metrics")
    return metrics if isinstance(metrics, Mapping) else record


def _bind_tuning_inputs(
    config: Mapping[str, Any],
    selection: Mapping[str, Any],
    tuning_root: Path,
    input_paths: set[Path],
) -> None:
    candidates = selection.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("selection artifact lacks tuning candidates")
    indexed = {
        (
            str(item["method"]),
            float(item["ridge"]),
            float(item["bonus_scale"]),
        ): item
        for item in candidates
    }
    for method in configured_methods(config):
        for ridge, bonus in hyperparameter_grid(config, method):
            candidate = indexed[(method, ridge, bonus)]
            per_seed = candidate["per_seed_cumulative_pseudo_regret"]
            for seed in get_seed_set(config, "tuning"):
                cell = f"ridge-{ridge:g}_bonus-{bonus:g}"
                run_directory = tuning_root / method / cell / f"seed-{seed}"
                summary_path = run_directory / "summary.jsonl"
                row = _load_single_jsonl(summary_path)
                if (
                    row.get("method") != method
                    or int(row.get("seed", -1)) != seed
                    or row.get("phase") != "tuning"
                    or row.get("hyperparameters")
                    != {"ridge": ridge, "bonus_scale": bonus}
                ):
                    raise ValueError(f"tuning summary identity mismatch: {summary_path}")
                if not math.isclose(
                    float(row["cumulative_pseudo_regret"]),
                    float(per_seed[str(seed)]),
                    rel_tol=0.0,
                    abs_tol=1e-12,
                ):
                    raise ValueError(
                        f"selection value disagrees with tuning raw input: {summary_path}"
                    )
                for filename in ("manifest.jsonl", "raw.jsonl", "summary.jsonl"):
                    input_paths.add(run_directory / filename)


def build_artifact(
    *,
    config_path: Path = DEFAULT_CONFIG,
    raw_root: Path = DEFAULT_RAW_ROOT,
    selection_path: Path = DEFAULT_SELECTION,
    profile: str = "full",
) -> dict[str, Any]:
    config = load_config(config_path, profile=profile)
    methods = configured_methods(config)
    seeds = tuple(get_seed_set(config, "evaluation"))
    if profile == "full" and len(seeds) < 30:
        raise ValueError("the full benchmark requires at least 30 evaluation seeds")
    if set(get_seed_set(config, "tuning")) & set(seeds):
        raise ValueError("tuning and evaluation seeds overlap")

    selection = load_tuning_selection(selection_path)
    selected = validate_tuning_selection(config, selection)
    aggregate = aggregate_results(raw_root, seed_set="evaluation")
    if aggregate.get("experiments") != ["balanced_benchmark"]:
        raise ValueError("aggregate does not contain only the balanced benchmark")
    if int(aggregate.get("run_count", -1)) != len(methods) * len(seeds):
        raise ValueError("evaluation aggregate is incomplete")
    if int(aggregate.get("group_count", -1)) != len(methods):
        raise ValueError("evaluation aggregate has the wrong method count")
    if int(aggregate.get("paired_comparison_count", -1)) != len(methods) - 1:
        raise ValueError("paired comparison coverage is incomplete")
    if not aggregate.get("all_groups_complete") or not aggregate.get(
        "all_paired_comparisons_complete"
    ):
        raise ValueError("evaluation aggregate has incomplete seed coverage")

    groups = {str(group["method"]): group for group in aggregate["groups"]}
    if set(groups) != set(methods):
        raise ValueError("aggregate method inventory disagrees with the config")
    summaries: dict[str, list[dict[str, Any]]] = {method: [] for method in methods}
    raw_by_method_seed: dict[tuple[str, int], list[dict[str, Any]]] = {}
    input_paths = {config_path, selection_path}
    _bind_tuning_inputs(
        config, selection, raw_root.parent / "tuning", input_paths
    )
    stream_by_seed: dict[int, set[str]] = {seed: set() for seed in seeds}
    seed_level: list[dict[str, Any]] = []
    metric_names = (
        "cumulative_pseudo_regret",
        "cumulative_reward",
        "mean_reward",
        "runtime_seconds",
        "state_update_seconds",
        "model_update_seconds",
        "posterior_update_seconds",
        "uncertainty_seconds",
        "peak_host_memory_bytes",
        "host_rss_at_start_bytes",
        "peak_host_rss_delta_bytes",
        "maximum_persistent_numeric_policy_state_bytes",
        "action_disagreement_rate",
    )
    for method in methods:
        ridge, bonus = selected[method]
        group = groups[method]
        if group.get("hyperparameters") != {
            "bonus_scale": bonus,
            "ridge": ridge,
        }:
            raise ValueError(f"evaluation hyperparameters disagree for {method}")
        for seed in seeds:
            run_directory = raw_root / method / f"seed-{seed}"
            summary_path = run_directory / "summary.jsonl"
            row = _load_single_jsonl(summary_path)
            if row.get("method") != method or int(row.get("seed", -1)) != seed:
                raise ValueError(f"summary identity mismatch: {summary_path}")
            if row.get("phase") != "evaluation" or row.get("executed_policy") is not True:
                raise ValueError(f"non-evaluation or non-executed row: {summary_path}")
            if row.get("hyperparameters") != {
                "ridge": ridge,
                "bonus_scale": bonus,
            }:
                raise ValueError(
                    "summary setting was not selected on tuning seeds: "
                    f"{summary_path}"
                )
            summaries[method].append(row)
            raw_by_method_seed[(method, seed)] = _load_jsonl(
                run_directory / "raw.jsonl"
            )
            digest = str(row["environment_stream_sha256"])
            stream_by_seed[seed].add(digest)
            seed_level.append(
                {
                    "method": method,
                    "seed": seed,
                    "policy_type": row["policy_type"],
                    "method_implementation": row["method_implementation"],
                    "ridge": ridge,
                    "bonus_scale": bonus,
                    **{name: row[name] for name in metric_names},
                    "environment_stream_sha256": digest,
                }
            )
            for filename in ("manifest.jsonl", "raw.jsonl", "summary.jsonl"):
                input_paths.add(run_directory / filename)
    if any(len(digests) != 1 for digests in stream_by_seed.values()):
        raise ValueError("methods do not share one context/noise stream within each seed")

    sanity_config = config.get("sanity_check")
    if not isinstance(sanity_config, Mapping):
        raise ValueError("config lacks the predefined sanity check")
    contextual_method = str(sanity_config.get("predefined_contextual_method"))
    baselines = tuple(str(value) for value in sanity_config.get("context_free_methods", ()))
    if contextual_method not in methods or set(baselines) != CONTEXT_FREE_METHODS:
        raise ValueError("sanity-check method inventory is invalid")
    contextual_regret = {
        int(row["seed"]): float(row["cumulative_pseudo_regret"])
        for row in summaries[contextual_method]
    }
    paired_sanity: dict[str, Any] = {}
    for baseline in baselines:
        baseline_regret = {
            int(row["seed"]): float(row["cumulative_pseudo_regret"])
            for row in summaries[baseline]
        }
        differences = [
            contextual_regret[seed] - baseline_regret[seed] for seed in seeds
        ]
        paired_sanity[baseline] = student_t_interval(differences)
    sanity_passes = all(
        float(result["mean"]) < 0.0 for result in paired_sanity.values()
    )

    method_results: dict[str, Any] = {}
    for method in methods:
        rows = summaries[method]
        group = groups[method]
        method_results[method] = {
            "policy_type": rows[0]["policy_type"],
            "method_implementation": rows[0]["method_implementation"],
            "published_implementation_claim": False,
            "representation_update_protocol": rows[0][
                "representation_update_protocol"
            ],
            "selected_hyperparameters": rows[0]["hyperparameters"],
            "evaluation_seed_count": len(rows),
            "metrics": {
                name: _metric_interval(rows, name) for name in metric_names
            },
            "horizons": group["horizons"],
        }
        if method == "cc_ucb_full_ggn_cg":
            method_results[method]["cg_metrics"] = {
                name: _metric_interval(rows, name)
                for name in (
                    "cg_total_iterations",
                    "cg_iterations_per_action",
                    "cg_total_operator_calls",
                    "cg_maximum_relative_residual",
                )
            }
            method_results[method]["all_cg_solves_converged"] = all(
                bool(row["all_cg_solves_converged"]) for row in rows
            )
            method_results[method]["cg_solver_status"] = rows[0][
                "cg_solver_status"
            ]

    horizon_metrics = (
        "cumulative_pseudo_regret",
        "cumulative_reward",
        "mean_reward",
        "cumulative_runtime_seconds",
        "cumulative_model_update_seconds",
        "cumulative_posterior_update_seconds",
        "cumulative_uncertainty_seconds",
        "persistent_numeric_policy_state_bytes",
        "cumulative_action_disagreement_rate",
    )
    reference_methods = (
        "cc_ucb_full_ggn_cg",
        "gaussian_ucb1",
        "gaussian_context_free_ts",
    )
    paired_horizon_comparisons: list[dict[str, Any]] = []
    for reference in reference_methods:
        for method in methods:
            if method == reference:
                continue
            horizon_rows: list[dict[str, Any]] = []
            for horizon in config["horizons"]:
                differences: dict[str, Any] = {}
                for metric in horizon_metrics:
                    differences[metric] = student_t_interval(
                        float(
                            _record_metrics(
                                raw_by_method_seed[(method, seed)][horizon - 1]
                            )[metric]
                        )
                        - float(
                            _record_metrics(
                                raw_by_method_seed[(reference, seed)][horizon - 1]
                            )[metric]
                        )
                        for seed in seeds
                    )
                horizon_rows.append({"horizon": horizon, "metrics": differences})
            paired_horizon_comparisons.append(
                {
                    "method": method,
                    "reference_method": reference,
                    "difference_direction": "method_minus_reference",
                    "pair_count": len(seeds),
                    "horizons": horizon_rows,
                }
            )

    negative_comparators = (
        "diagonal_full_network_ucb",
        "linucb",
        "linear_ts",
        "frozen_last_layer_ucb",
    )
    regret_means = {
        method: float(
            method_results[method]["metrics"]["cumulative_pseudo_regret"]["mean"]
        )
        for method in ("cc_ucb_full_ggn_cg", *negative_comparators)
    }

    input_records = [
        {"path": str(path), "sha256": _sha256(path)}
        for path in sorted(input_paths, key=lambda value: str(value))
    ]
    input_set_sha256 = hashlib.sha256(
        canonical_json(input_records).encode("ascii")
    ).hexdigest()
    counts = winner_counts()
    return {
        "schema_version": 1,
        "event": "balanced_contextual_benchmark_report",
        "experiment": "balanced_benchmark",
        "profile": profile,
        "seed_set": "evaluation",
        "evaluation_seed_count": len(seeds),
        "tuning_seed_count": len(get_seed_set(config, "tuning")),
        "tuning_evaluation_seeds_disjoint": True,
        "selection_criterion": selection["criterion"],
        "selection_artifact_sha256": _sha256(selection_path),
        "winner_counts_on_exact_16_context_support": list(counts),
        "all_actions_win_on_exact_context_support": all(count > 0 for count in counts),
        "common_context_and_noise_stream_within_seed": True,
        "method_results": method_results,
        "seed_level_results": seed_level,
        "paired_comparisons_against_cc_ucb_full_ggn_cg": aggregate[
            "paired_comparisons"
        ],
        "paired_horizon_comparisons": paired_horizon_comparisons,
        "contextual_sanity_check": {
            "predefined_contextual_method": contextual_method,
            "context_free_methods": list(baselines),
            "difference_direction": "contextual_minus_context_free",
            "paired_95_percent_intervals": paired_sanity,
            "passes_mean_regret_prerequisite": sanity_passes,
        },
        "empirical_finding": {
            "full_curvature_uniform_superiority_supported": False,
            "metric": "mean_cumulative_pseudo_regret",
            "means": regret_means,
            "cc_ucb_worse_than_each_listed_comparator": all(
                regret_means["cc_ucb_full_ggn_cg"] > regret_means[method]
                for method in negative_comparators
            ),
        },
        "limitations": [
            "NeuralUCB and NeuralTS are local linearized implementations, not "
            "claimed faithful reproductions of all published training protocols.",
            "The NeuralLinear and last-layer UCB policies freeze the initialized "
            "representation; this is favorable on this teacher because the teacher "
            "shares that backbone.",
            "All rows are executed but uncertified diagnostic policies.",
            "Absolute host RSS is measured inside a process reused across runs; "
            "start-relative RSS and persistent numeric state are supplied for resource "
            "comparison, and absolute RSS is not treated as a paired allocation metric.",
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
    print(json.dumps({"output": str(output), "sidecar": str(sidecar)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_artifact", "main"]
