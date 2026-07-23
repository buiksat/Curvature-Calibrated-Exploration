"""Aggregate end-to-end systems runs and build timing/memory artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from scipy import stats

from .artifact_utils import (
    input_set_sha256,
    sha256_file,
    validate_sha256_sidecar,
    write_json_artifact,
    write_sha256_sidecar,
)
from .config import config_digest, get_seed_set, load_config
from .logging_utils import canonical_json
from .run_autodiff_systems import mlp_parameter_count
from .run_end_to_end_systems_benchmark import (
    COMPONENTS,
    METHODS,
    benchmark_grid,
    validate_benchmark_config,
)


DISPLAY_NAMES = {
    "current_replay_ggn_cg": "Current replay GGN-CG",
    "historical_gradient_cg": "Historical-gradient CG",
    "empirical_diagonal": "Empirical diagonal",
    "exact_last_layer": "Exact last layer",
    "local_tensor_block_isotropic": "Local tensor-block isotropic (not KFAC)",
    "greedy": "Greedy",
}
METHOD_COLORS = {
    method: plt.get_cmap("tab10")(index) for index, method in enumerate(DISPLAY_NAMES)
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _interval(values: Sequence[float]) -> dict[str, float | int]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("interval input must be a nonempty finite vector")
    mean = float(np.mean(array))
    if array.size == 1:
        low = high = mean
    else:
        standard_error = float(np.std(array, ddof=1) / np.sqrt(array.size))
        half_width = float(stats.t.ppf(0.975, array.size - 1) * standard_error)
        low, high = mean - half_width, mean + half_width
    return {"mean": mean, "ci95_low": low, "ci95_high": high, "n": int(array.size)}


def _run_directory(
    phase_root: Path,
    model_name: str,
    action_count: int,
    replay_size: int,
    method: str,
    seed: int,
) -> Path:
    return (
        phase_root
        / f"model-{model_name}_K-{action_count}_replay-{replay_size}"
        / method
        / f"seed-{seed}"
    )


def _load_run(
    directory: Path,
    *,
    config: Mapping[str, Any],
    profile: str,
    model: Mapping[str, Any],
    action_count: int,
    replay_size: int,
    method: str,
    seed: int,
) -> tuple[dict[str, Any], list[Path]]:
    manifest_path = directory / "manifest.json"
    summary_path = directory / "summary.json"
    timings_path = directory / "timings.npz"
    paths = [manifest_path, summary_path, timings_path]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"missing systems artifact {path}")
        validate_sha256_sidecar(path)
    manifest = _load_json(manifest_path)
    summary = _load_json(summary_path)
    identity = {
        "model": str(model["name"]),
        "parameter_count": mlp_parameter_count(
            tuple(int(value) for value in model["architecture"])
        ),
        "action_count": action_count,
        "replay_size": replay_size,
        "method": method,
        "seed": seed,
    }
    if manifest.get("experiment") != "end_to_end_systems_benchmark":
        raise ValueError(f"wrong experiment in {manifest_path}")
    if manifest.get("profile") != profile or manifest.get("seed_set") != "evaluation":
        raise ValueError(f"wrong profile/seed set in {manifest_path}")
    if manifest.get("config_digest") != config_digest(config):
        raise ValueError(f"config digest mismatch in {manifest_path}")
    if manifest.get("identity") != identity:
        raise ValueError(f"run identity mismatch in {manifest_path}")
    if manifest.get("summary_sha256") != sha256_file(summary_path):
        raise ValueError(f"summary hash mismatch in {manifest_path}")
    if manifest.get("timings_sha256") != sha256_file(timings_path):
        raise ValueError(f"timing hash mismatch in {manifest_path}")
    if (
        summary.get("status") != "completed"
        or summary.get("full_online_loop") is not True
    ):
        raise ValueError(f"incomplete online loop in {summary_path}")
    if summary.get("profile") != profile or summary.get("seed_set") != "evaluation":
        raise ValueError(f"summary profile/seed-set mismatch in {summary_path}")
    if summary.get("config_digest") != config_digest(config):
        raise ValueError(f"summary config digest mismatch in {summary_path}")
    for key, expected in identity.items():
        if summary.get(key) != expected:
            raise ValueError(f"summary identity mismatch for {key}: {summary_path}")
    latency = summary.get("latency_components")
    if not isinstance(latency, Mapping) or set(latency) != set(COMPONENTS):
        raise ValueError(f"latency component coverage mismatch: {summary_path}")
    measured_rounds = int(config["rounds"]) - int(config["warmup_rounds"])
    if any(int(latency[name]["count"]) != measured_rounds for name in COMPONENTS):
        raise ValueError(f"latency count mismatch: {summary_path}")
    with np.load(timings_path, allow_pickle=False) as archive:
        if set(COMPONENTS) - set(archive.files):
            raise ValueError(f"timing archive lacks components: {timings_path}")
        if any(archive[name].shape != (measured_rounds,) for name in COMPONENTS):
            raise ValueError(
                f"timing archive has wrong measured horizon: {timings_path}"
            )
        for name in (
            "host_rss_bytes",
            "device_allocated_bytes",
            "device_reserved_bytes",
        ):
            if name not in archive.files or archive[name].shape != (measured_rounds,):
                raise ValueError(
                    f"memory trace {name} has wrong horizon: {timings_path}"
                )
            if np.any(archive[name] < 0):
                raise ValueError(f"memory trace {name} is negative: {timings_path}")
    for name in (
        "peak_measured_host_rss_bytes",
        "peak_device_allocated_bytes",
        "peak_device_reserved_bytes",
    ):
        if int(summary.get(name, -1)) < 0:
            raise ValueError(f"invalid {name} in {summary_path}")
    expanded = paths + [path.with_name(path.name + ".sha256") for path in paths]
    return summary, expanded


def aggregate_runs(
    config: Mapping[str, Any],
    *,
    profile: str,
    raw_root: Path,
) -> dict[str, Any]:
    validate_benchmark_config(config)
    phase_root = raw_root / profile / "evaluation"
    grid_manifest_path = phase_root / "manifest.json"
    validate_sha256_sidecar(grid_manifest_path)
    grid_manifest = _load_json(grid_manifest_path)
    expected_run_count = len(benchmark_grid(config, "evaluation"))
    if grid_manifest.get("status") != "completed":
        raise ValueError(
            f"systems grid is not complete: {grid_manifest.get('status', 'unknown')}"
        )
    if grid_manifest.get("reportable_complete") is not True:
        raise ValueError("systems grid is not marked reportable-complete")
    if int(grid_manifest.get("expected_run_count", -1)) != expected_run_count:
        raise ValueError("systems grid expected-run count mismatch")
    if int(grid_manifest.get("completed_run_count", -1)) != expected_run_count:
        raise ValueError("systems grid completed-run count mismatch")
    if grid_manifest.get("config_digest") != config_digest(config):
        raise ValueError("systems grid config digest mismatch")

    records: dict[tuple[str, int, int, str], list[tuple[int, dict[str, Any]]]] = {}
    inputs = [
        {
            "path": grid_manifest_path.as_posix(),
            "sha256": sha256_file(grid_manifest_path),
        },
        {
            "path": grid_manifest_path.with_name("manifest.json.sha256").as_posix(),
            "sha256": sha256_file(grid_manifest_path.with_name("manifest.json.sha256")),
        },
    ]
    for model in config["models"]:
        for action_count in config["action_counts"]:
            for replay_size in config["replay_sizes"]:
                for method in METHODS:
                    key = (
                        str(model["name"]),
                        int(action_count),
                        int(replay_size),
                        method,
                    )
                    rows = []
                    for seed in get_seed_set(config, "evaluation"):
                        directory = _run_directory(
                            phase_root,
                            str(model["name"]),
                            int(action_count),
                            int(replay_size),
                            method,
                            int(seed),
                        )
                        summary, run_paths = _load_run(
                            directory,
                            config=config,
                            profile=profile,
                            model=model,
                            action_count=int(action_count),
                            replay_size=int(replay_size),
                            method=method,
                            seed=int(seed),
                        )
                        rows.append((int(seed), summary))
                        inputs.extend(
                            {"path": path.as_posix(), "sha256": sha256_file(path)}
                            for path in run_paths
                        )
                    records[key] = rows

    groups: list[dict[str, Any]] = []
    for (model_name, action_count, replay_size, method), rows in records.items():
        rows.sort(key=lambda item: item[0])
        summaries = [summary for _, summary in rows]
        component_summary: dict[str, Any] = {}
        for component in COMPONENTS:
            component_summary[component] = {
                "per_run_p50_seconds": _interval(
                    [
                        float(summary["latency_components"][component]["p50_seconds"])
                        for summary in summaries
                    ]
                ),
                "per_run_p95_seconds": _interval(
                    [
                        float(summary["latency_components"][component]["p95_seconds"])
                        for summary in summaries
                    ]
                ),
                "per_run_total_seconds": _interval(
                    [
                        float(summary["latency_components"][component]["total_seconds"])
                        for summary in summaries
                    ]
                ),
            }
        groups.append(
            {
                "model": model_name,
                "architecture": summaries[0]["architecture"],
                "parameter_count": int(summaries[0]["parameter_count"]),
                "action_count": action_count,
                "replay_size": replay_size,
                "method": method,
                "method_label": DISPLAY_NAMES[method],
                "method_semantics": str(config["method_semantics"][method]),
                "run_count": len(summaries),
                "latency_components": component_summary,
                "complete_policy_wall_seconds": _interval(
                    [
                        float(summary["complete_policy_wall_seconds"])
                        for summary in summaries
                    ]
                ),
                "measured_rounds_per_second": _interval(
                    [
                        float(summary["measured_rounds_per_second"])
                        for summary in summaries
                    ]
                ),
                "terminal_pseudo_regret": _interval(
                    [float(summary["terminal_pseudo_regret"]) for summary in summaries]
                ),
                "sample_cvp_count": _interval(
                    [float(summary["sample_cvp_count"]) for summary in summaries]
                ),
                "maximum_cg_relative_residual": float(
                    max(
                        float(summary["maximum_cg_relative_residual"])
                        for summary in summaries
                    )
                ),
                "all_cg_solves_converged": bool(
                    all(
                        bool(summary["all_cg_solves_converged"])
                        for summary in summaries
                    )
                ),
                "peak_measured_host_rss_bytes": _interval(
                    [
                        float(summary["peak_measured_host_rss_bytes"])
                        for summary in summaries
                    ]
                ),
                "peak_device_allocated_bytes": _interval(
                    [
                        float(summary["peak_device_allocated_bytes"])
                        for summary in summaries
                    ]
                ),
                "peak_device_reserved_bytes": _interval(
                    [
                        float(summary["peak_device_reserved_bytes"])
                        for summary in summaries
                    ]
                ),
            }
        )

    normalized_inputs = sorted(inputs, key=lambda item: item["path"])
    first_summary = next(iter(records.values()))[0][1]
    return {
        "schema_version": 1,
        "experiment": "end_to_end_systems_benchmark",
        "profile": profile,
        "config": dict(config),
        "config_digest": config_digest(config),
        "expected_run_count": expected_run_count,
        "validated_run_count": sum(int(group["run_count"]) for group in groups),
        "evaluation_seeds": list(get_seed_set(config, "evaluation")),
        "tuning_seeds": list(get_seed_set(config, "tuning")),
        "tuning_evaluation_seeds_disjoint": bool(
            set(get_seed_set(config, "evaluation")).isdisjoint(
                get_seed_set(config, "tuning")
            )
        ),
        "groups": groups,
        "unavailable_baselines": dict(config["unavailable_baselines"]),
        "hardware_and_timing_provenance": grid_manifest["provenance"],
        "memory_measurement_scope": {
            "host": first_summary["host_memory_scope"],
            "device": first_summary["device_memory_scope"],
        },
        "aggregation_source": {
            "path": "experiments/make_end_to_end_systems_artifacts.py",
            "sha256": sha256_file(Path(__file__)),
        },
        "input_set_sha256": input_set_sha256(normalized_inputs),
        "raw_inputs": normalized_inputs,
        "claim_scope": (
            "Executed systems measurements only. Local controls are labeled by their "
            "implemented algebra and no regret superiority or faithful LO-FI/KFAC claim is made."
        ),
    }


def make_figure(report: Mapping[str, Any], output: Path) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(12.0, 3.7), constrained_layout=True)
    markers = {2: "o", 5: "s", 10: "^"}
    replay_sizes = tuple(int(value) for value in report["config"]["replay_sizes"])
    for group in report["groups"]:
        parameters = float(group["parameter_count"])
        method = str(group["method"])
        marker = markers.get(int(group["action_count"]), "o")
        color = METHOD_COLORS[method]
        filled = int(group["replay_size"]) == replay_sizes[0]
        scatter_style = {
            "marker": marker,
            "s": 30,
            "edgecolors": [color],
            "facecolors": [color] if filled else "none",
        }
        axes[0].scatter(
            parameters,
            max(
                float(
                    group["latency_components"]["round_total_seconds"][
                        "per_run_p50_seconds"
                    ]["mean"]
                ),
                1e-12,
            ),
            **scatter_style,
        )
        axes[1].scatter(
            parameters,
            max(
                float(
                    group["latency_components"]["curvature_seconds"][
                        "per_run_p95_seconds"
                    ]["mean"]
                ),
                1e-12,
            ),
            **scatter_style,
        )
        axes[2].scatter(
            parameters,
            float(group["peak_device_allocated_bytes"]["mean"]) / 2**20,
            **scatter_style,
        )
    axes[0].set(
        xlabel="Parameters",
        ylabel="Round latency p50 (s)",
        xscale="log",
        yscale="log",
    )
    axes[1].set(
        xlabel="Parameters",
        ylabel="Curvature latency p95 (s)",
        xscale="log",
        yscale="log",
    )
    axes[2].set(
        xlabel="Parameters",
        ylabel="Peak device allocation (MiB)",
        xscale="log",
    )
    method_handles = [
        Line2D(
            [],
            [],
            marker="o",
            linestyle="none",
            color=METHOD_COLORS[method],
            label=label,
            markersize=5,
        )
        for method, label in DISPLAY_NAMES.items()
    ]
    action_handles = [
        Line2D(
            [],
            [],
            marker=markers.get(int(action_count), "o"),
            linestyle="none",
            color="black",
            label=f"K={int(action_count)}",
            markersize=5,
        )
        for action_count in report["config"]["action_counts"]
    ]
    replay_handles = [
        Line2D(
            [],
            [],
            marker="o",
            linestyle="none",
            markeredgecolor="black",
            markerfacecolor="black" if index == 0 else "none",
            color="black",
            label=f"Replay={replay_size}",
            markersize=5,
        )
        for index, replay_size in enumerate(replay_sizes)
    ]
    axes[0].legend(handles=method_handles, fontsize=5.5, ncol=2)
    axes[1].legend(handles=action_handles, fontsize=6)
    axes[2].legend(handles=replay_handles, fontsize=6)
    for axis in axes:
        axis.grid(alpha=0.2)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output,
        metadata={
            "Creator": "end_to_end_systems_benchmark",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    plt.close(figure)
    write_sha256_sidecar(output)


def make_table(report: Mapping[str, Any], output: Path) -> None:
    lines = [
        r"\begin{tabular}{lrrrrrrr}",
        r"\toprule",
        r"Method & Params & $K$ & Replay & Round p50 & Curv. p95 & Host MiB & Device MiB \\",
        r"\midrule",
    ]
    for group in report["groups"]:
        round_p50 = group["latency_components"]["round_total_seconds"]
        curvature_p95 = group["latency_components"]["curvature_seconds"]
        lines.append(
            f"{group['method_label']} & {int(group['parameter_count'])} & "
            f"{int(group['action_count'])} & {int(group['replay_size'])} & "
            f"{float(round_p50['per_run_p50_seconds']['mean']):.4f} & "
            f"{float(curvature_p95['per_run_p95_seconds']['mean']):.4f} & "
            f"{float(group['peak_measured_host_rss_bytes']['mean']) / 2**20:.1f} & "
            f"{float(group['peak_device_allocated_bytes']['mean']) / 2**20:.1f} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="ascii")
    write_sha256_sidecar(output)


def _write_provenance(
    artifact: Path,
    *,
    aggregate: Path,
    config: Mapping[str, Any],
) -> None:
    inputs = [{"path": aggregate.as_posix(), "sha256": sha256_file(aggregate)}]
    write_json_artifact(
        artifact.with_name(artifact.name + ".provenance.json"),
        {
            "schema_version": 1,
            "artifact": artifact.as_posix(),
            "artifact_sha256": sha256_file(artifact),
            "inputs": inputs,
            "input_set_sha256": input_set_sha256(inputs),
            "generation_parameters": {
                "experiment": "end_to_end_systems_benchmark",
                "config_digest": config_digest(config),
                "generator_source_sha256": sha256_file(Path(__file__)),
            },
        },
    )


def build_artifacts(
    config: Mapping[str, Any],
    *,
    profile: str,
    raw_root: Path,
    aggregate_path: Path,
    figure_path: Path,
    table_path: Path,
) -> dict[str, Any]:
    report = aggregate_runs(config, profile=profile, raw_root=raw_root)
    aggregate, _ = write_json_artifact(aggregate_path, report)
    make_figure(report, figure_path)
    make_table(report, table_path)
    for artifact in (figure_path, table_path):
        _write_provenance(artifact, aggregate=aggregate, config=config)
    return {
        "aggregate": aggregate.as_posix(),
        "figure": figure_path.as_posix(),
        "table": table_path.as_posix(),
        "validated_run_count": report["validated_run_count"],
        "input_set_sha256": report["input_set_sha256"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--figure", type=Path, required=True)
    parser.add_argument("--table", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = load_config(args.config, profile=args.profile)
    result = build_artifacts(
        config,
        profile=args.profile,
        raw_root=args.raw_root,
        aggregate_path=args.aggregate,
        figure_path=args.figure,
        table_path=args.table,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["aggregate_runs", "build_artifacts", "make_figure", "make_table"]
