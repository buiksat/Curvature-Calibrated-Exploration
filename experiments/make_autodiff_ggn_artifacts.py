"""Build validated systems and accuracy artifacts from autodiff GGN records."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .artifact_utils import (
    input_set_sha256,
    sha256_file,
    validate_sha256_sidecar,
    write_json_artifact,
    write_sha256_sidecar,
)
from .config import config_digest, get_seed_set, load_config
from .logging_utils import canonical_json, derive_seed
from .run_autodiff_ggn_benchmark import METHODS, validate_benchmark_config


FloatArray = NDArray[np.float64]

METHOD_LABELS = {
    "separate_cg": "Separate CG",
    "batched_cg": "Batched CG",
    "jacobi_pcg": "Jacobi-PCG",
    "diagonal": "Diagonal",
    "last_layer": "Last layer",
    "explicit_dense_reference": "Explicit dense reference",
}
METHOD_COLORS = {
    "separate_cg": "#111111",
    "batched_cg": "#2474B5",
    "jacobi_pcg": "#2E8B57",
    "diagonal": "#D9822B",
    "last_layer": "#6B4C9A",
    "explicit_dense_reference": "#777777",
}


class AutodiffArtifactError(ValueError):
    """Raised when the benchmark grid or provenance is incomplete."""


def _token(model: str, buffer_size: int, action_count: int, target: float) -> str:
    return (
        f"model-{model}_m-{buffer_size}_K-{action_count}_"
        f"tol-{target:.0e}"
    )


def _load_json(path: Path) -> dict[str, Any]:
    validate_sha256_sidecar(path)
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (OSError, json.JSONDecodeError) as error:
        raise AutodiffArtifactError(f"cannot parse {path}: {error}") from error
    if not isinstance(value, dict):
        raise AutodiffArtifactError(f"{path} is not a JSON object")
    return value


def _interval(
    values: FloatArray, *, resamples: int, seed_parts: Sequence[object]
) -> dict[str, float | int] | None:
    if values.size == 0:
        return None
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise AutodiffArtifactError("interval input is not a finite vector")
    rng = np.random.Generator(np.random.PCG64(derive_seed(0, *seed_parts)))
    indices = rng.integers(0, values.size, size=(resamples, values.size))
    means = np.mean(values[indices], axis=1)
    low, high = np.quantile(means, (0.025, 0.975))
    return {
        "mean": float(np.mean(values)),
        "ci95_low": float(low),
        "ci95_high": float(high),
        "n": int(values.size),
    }


def _maximum_optional(record: Mapping[str, Any], field: str) -> float | None:
    values = record.get(field)
    if values is None:
        return None
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise AutodiffArtifactError(f"{field} must be a list or null")
    return max(float(value) for value in values) if values else 0.0


def build_aggregate(
    config: dict[str, Any], *, profile: str, raw_root: Path
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    validate_benchmark_config(config)
    seeds = get_seed_set(config, "evaluation")
    resamples = 2000 if profile == "full" else 100
    inputs: list[dict[str, str]] = []
    raw: dict[
        tuple[str, int, int, float, str], list[Mapping[str, Any]]
    ] = {}
    skipped_cells: list[dict[str, Any]] = []

    for seed in seeds:
        for model in config["models"]:
            model_name = str(model["name"])
            for buffer_size in config["buffer_sizes"]:
                for action_count in config["action_counts"]:
                    for target in config["cg_targets"]:
                        token = _token(
                            model_name,
                            int(buffer_size),
                            int(action_count),
                            float(target),
                        )
                        directory = (
                            raw_root
                            / profile
                            / "evaluation"
                            / f"seed-{seed}"
                            / token
                        )
                        result_path = directory / "result.json"
                        manifest_path = directory / "manifest.json"
                        if not result_path.is_file() or not manifest_path.is_file():
                            raise AutodiffArtifactError(f"missing raw cell {directory}")
                        result = _load_json(result_path)
                        manifest = _load_json(manifest_path)
                        if (
                            manifest.get("experiment") != "autodiff_ggn_benchmark"
                            or manifest.get("profile") != profile
                            or manifest.get("phase") != "evaluation"
                            or manifest.get("seed") != seed
                            or manifest.get("cell") != token
                            or manifest.get("config_digest") != config_digest(config)
                            or manifest.get("evaluation_data_used_for_selection") is not False
                        ):
                            raise AutodiffArtifactError(f"manifest mismatch in {directory}")
                        for path in (result_path, manifest_path):
                            sidecar = path.with_name(path.name + ".sha256")
                            inputs.extend(
                                (
                                    {"path": path.as_posix(), "sha256": sha256_file(path)},
                                    {
                                        "path": sidecar.as_posix(),
                                        "sha256": sha256_file(sidecar),
                                    },
                                )
                            )
                        if result.get("status") == "skipped":
                            skipped_cells.append(
                                {
                                    "seed": seed,
                                    "cell": token,
                                    "reason": result.get("skip_reason"),
                                }
                            )
                            continue
                        records = result.get("records")
                        if not isinstance(records, Sequence) or len(records) != len(METHODS):
                            raise AutodiffArtifactError(f"method coverage is invalid in {directory}")
                        by_method = {str(record["method"]): record for record in records}
                        if set(by_method) != set(METHODS):
                            raise AutodiffArtifactError(f"methods are incomplete in {directory}")
                        for method, record in by_method.items():
                            raw.setdefault(
                                (
                                    model_name,
                                    int(buffer_size),
                                    int(action_count),
                                    float(target),
                                    method,
                                ),
                                [],
                            ).append(record)

    groups = []
    for key in sorted(raw):
        model, buffer_size, action_count, target, method = key
        records = raw[key]
        completed = [record for record in records if record.get("status") == "completed"]
        field_values: dict[str, list[float]] = {
            "wall_time_seconds": [],
            "peak_accelerator_memory_bytes": [],
            "peak_host_memory_bytes": [],
            "operator_applications": [],
            "sample_cvps": [],
            "maximum_original_relative_residual": [],
            "maximum_width_squared_relative_error": [],
            "maximum_energy_relative_error": [],
        }
        top_agreement = []
        rank_agreement = []
        for record in completed:
            for field in (
                "wall_time_seconds",
                "peak_accelerator_memory_bytes",
                "peak_host_memory_bytes",
                "operator_applications",
                "sample_cvps",
            ):
                value = record.get(field)
                if value is not None:
                    field_values[field].append(float(value))
            for output_field, source_field in (
                (
                    "maximum_original_relative_residual",
                    "per_action_original_relative_residual",
                ),
                (
                    "maximum_width_squared_relative_error",
                    "per_action_width_squared_relative_error",
                ),
                (
                    "maximum_energy_relative_error",
                    "per_action_energy_relative_error",
                ),
            ):
                value = _maximum_optional(record, source_field)
                if value is not None:
                    field_values[output_field].append(value)
            if record.get("top_action_agreement") is not None:
                top_agreement.append(float(bool(record["top_action_agreement"])))
            if record.get("complete_rank_agreement") is not None:
                rank_agreement.append(float(bool(record["complete_rank_agreement"])))
        groups.append(
            {
                "model": model,
                "buffer_size": buffer_size,
                "action_count": action_count,
                "cg_target": target,
                "method": method,
                "expected_instance_count": len(seeds),
                "completed_instance_count": len(completed),
                "skipped_instance_count": len(records) - len(completed),
                "metrics": {
                    field: _interval(
                        np.asarray(values, dtype=np.float64),
                        resamples=resamples,
                        seed_parts=(profile, *key, field),
                    )
                    for field, values in field_values.items()
                },
                "top_action_agreement": _interval(
                    np.asarray(top_agreement, dtype=np.float64),
                    resamples=resamples,
                    seed_parts=(profile, *key, "top_agreement"),
                ),
                "complete_rank_agreement": _interval(
                    np.asarray(rank_agreement, dtype=np.float64),
                    resamples=resamples,
                    seed_parts=(profile, *key, "rank_agreement"),
                ),
            }
        )

    normalized_inputs = sorted(inputs, key=lambda item: item["path"])
    report = {
        "schema_version": 1,
        "experiment": "autodiff_ggn_benchmark_aggregate",
        "profile": profile,
        "config": config,
        "config_digest": config_digest(config),
        "evaluation_seeds": list(seeds),
        "interval": "operator-instance percentile bootstrap over evaluation seeds",
        "groups": groups,
        "skipped_cells": skipped_cells,
        "raw_inputs": normalized_inputs,
        "input_set_sha256": input_set_sha256(normalized_inputs),
    }
    return report, normalized_inputs


def _index(report: Mapping[str, Any]) -> dict[tuple[str, int, int, float, str], Mapping[str, Any]]:
    return {
        (
            str(group["model"]),
            int(group["buffer_size"]),
            int(group["action_count"]),
            float(group["cg_target"]),
            str(group["method"]),
        ): group
        for group in report["groups"]
    }


def _mean(group: Mapping[str, Any], field: str) -> float | None:
    interval = group["metrics"].get(field)
    return None if interval is None else float(interval["mean"])


def make_systems_figure(report: Mapping[str, Any], output: Path) -> None:
    import matplotlib.pyplot as plt

    config = report["config"]
    models = tuple(str(model["name"]) for model in config["models"])
    buffers = np.asarray(config["buffer_sizes"], dtype=np.float64)
    actions = max(int(value) for value in config["action_counts"])
    target = min(float(value) for value in config["cg_targets"])
    groups = _index(report)
    figure, axes = plt.subplots(len(models), 2, figsize=(7.2, 2.8 * len(models)))
    axes_array = np.atleast_2d(axes)
    for row, model in enumerate(models):
        for method in METHODS:
            times = []
            memories = []
            for buffer_size in buffers.astype(int):
                group = groups.get((model, buffer_size, actions, target, method))
                times.append(None if group is None else _mean(group, "wall_time_seconds"))
                memories.append(
                    None
                    if group is None
                    else _mean(group, "peak_accelerator_memory_bytes")
                )
            if any(value is not None for value in times):
                axes_array[row, 0].plot(
                    buffers,
                    np.asarray([np.nan if value is None else value for value in times]),
                    marker="o",
                    color=METHOD_COLORS[method],
                    label=METHOD_LABELS[method],
                )
            if any(value is not None and value > 0.0 for value in memories):
                axes_array[row, 1].plot(
                    buffers,
                    np.asarray(
                        [np.nan if value is None else value / 2**30 for value in memories]
                    ),
                    marker="o",
                    color=METHOD_COLORS[method],
                    label=METHOD_LABELS[method],
                )
        axes_array[row, 0].set_ylabel(f"{model}\nSeconds")
        axes_array[row, 1].set_ylabel("Peak accelerator GiB")
        for axis in axes_array[row]:
            axis.set_xscale("log", base=2)
            axis.grid(alpha=0.2, linewidth=0.5)
            axis.set_xlabel("Replay buffer size")
        axes_array[row, 0].set_yscale("log")
    handles, labels = axes_array[0, 0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=3, frameon=False, fontsize=8)
    figure.suptitle(f"Real JVP/VJP GGN systems benchmark ($K={actions}$)", y=0.995)
    figure.tight_layout(rect=(0, 0, 1, 0.91))
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(figure)
    write_sha256_sidecar(output)


def make_accuracy_figure(report: Mapping[str, Any], output: Path) -> None:
    import matplotlib.pyplot as plt

    config = report["config"]
    reference_models = [
        str(model["name"]) for model in config["models"] if model["dense_reference"]
    ]
    model = reference_models[0]
    buffer_size = max(int(value) for value in config["buffer_sizes"])
    actions = max(int(value) for value in config["action_counts"])
    targets = np.asarray(config["cg_targets"], dtype=np.float64)
    groups = _index(report)
    figure, axes = plt.subplots(1, 2, figsize=(7.0, 3.0))
    for method in ("separate_cg", "batched_cg", "jacobi_pcg", "diagonal"):
        residuals = []
        width_errors = []
        for target in targets:
            group = groups.get((model, buffer_size, actions, float(target), method))
            residuals.append(
                None
                if group is None
                else _mean(group, "maximum_original_relative_residual")
            )
            width_errors.append(
                None
                if group is None
                else _mean(group, "maximum_width_squared_relative_error")
            )
        axes[0].plot(
            targets,
            [np.nan if value is None else value for value in residuals],
            marker="o",
            color=METHOD_COLORS[method],
            label=METHOD_LABELS[method],
        )
        axes[1].plot(
            targets,
            [np.nan if value is None else value for value in width_errors],
            marker="o",
            color=METHOD_COLORS[method],
            label=METHOD_LABELS[method],
        )
    axes[0].set_ylabel("Original-system relative residual")
    axes[1].set_ylabel("Width-squared relative error")
    for axis in axes:
        axis.set_xscale("log")
        axis.set_yscale("log")
        axis.invert_xaxis()
        axis.set_xlabel("CG target")
        axis.grid(alpha=0.2, linewidth=0.5)
    axes[0].legend(frameon=False, fontsize=8)
    figure.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(figure)
    write_sha256_sidecar(output)


def make_table(report: Mapping[str, Any], output: Path) -> None:
    config = report["config"]
    buffer_size = max(int(value) for value in config["buffer_sizes"])
    actions = max(int(value) for value in config["action_counts"])
    target = min(float(value) for value in config["cg_targets"])
    groups = _index(report)
    lines = [
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Model & Method & Time (s) & Peak GiB & Sample-CVPs & Max residual \\",
        r"\midrule",
    ]
    for model in config["models"]:
        model_name = str(model["name"])
        for method in METHODS:
            group = groups.get((model_name, buffer_size, actions, target, method))
            if group is None or _mean(group, "wall_time_seconds") is None:
                lines.append(
                    f"{model_name} & {METHOD_LABELS[method]} & skipped & -- & -- & -- \\\\"
                )
                continue
            time_value = _mean(group, "wall_time_seconds")
            memory = _mean(group, "peak_accelerator_memory_bytes")
            work = _mean(group, "sample_cvps")
            residual = _mean(group, "maximum_original_relative_residual")
            lines.append(
                f"{model_name} & {METHOD_LABELS[method]} & {time_value:.4g} & "
                f"{(memory or 0.0) / 2**30:.3f} & {(work or 0.0):.0f} & "
                f"{'--' if residual is None else f'{residual:.2e}'} \\\\"
            )
        lines.append(r"\addlinespace")
    lines.extend((r"\bottomrule", r"\end{tabular}"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="ascii")
    write_sha256_sidecar(output)


def _provenance(artifact: Path, aggregate: Path, config: Mapping[str, Any]) -> None:
    sidecar = aggregate.with_name(aggregate.name + ".sha256")
    inputs = [
        {"path": aggregate.as_posix(), "sha256": sha256_file(aggregate)},
        {"path": sidecar.as_posix(), "sha256": sha256_file(sidecar)},
    ]
    write_json_artifact(
        artifact.with_name(artifact.name + ".provenance.json"),
        {
            "schema_version": 1,
            "artifact": artifact.as_posix(),
            "artifact_sha256": sha256_file(artifact),
            "inputs": inputs,
            "input_set_sha256": input_set_sha256(inputs),
            "generation_parameters": {
                "experiment": "autodiff_ggn_benchmark",
                "config_digest": config_digest(config),
            },
        },
    )


def make_artifacts(
    config: dict[str, Any],
    *,
    profile: str,
    raw_root: Path,
    aggregate_path: Path,
    systems_figure: Path,
    accuracy_figure: Path,
    table_path: Path,
) -> dict[str, Any]:
    report, inputs = build_aggregate(config, profile=profile, raw_root=raw_root)
    write_json_artifact(aggregate_path, report)
    make_systems_figure(report, systems_figure)
    make_accuracy_figure(report, accuracy_figure)
    make_table(report, table_path)
    for artifact in (systems_figure, accuracy_figure, table_path):
        _provenance(artifact, aggregate_path, config)
    return {
        "profile": profile,
        "aggregate": aggregate_path.as_posix(),
        "raw_input_count": len(inputs),
        "skipped_cell_count": len(report["skipped_cells"]),
        "artifacts": [
            systems_figure.as_posix(),
            accuracy_figure.as_posix(),
            table_path.as_posix(),
        ],
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--systems-figure", type=Path, required=True)
    parser.add_argument("--accuracy-figure", type=Path, required=True)
    parser.add_argument("--table", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config, profile=args.profile)
    result = make_artifacts(
        config,
        profile=args.profile,
        raw_root=args.raw_root,
        aggregate_path=args.aggregate,
        systems_figure=args.systems_figure,
        accuracy_figure=args.accuracy_figure,
        table_path=args.table,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = ["build_aggregate", "make_artifacts"]
