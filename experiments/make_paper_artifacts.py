"""Generate paper-ready tables, figures, and derived result files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .aggregate_results import AggregationError, aggregate_results
from .logging_utils import canonical_json


DEFAULT_DERIVED_DIR = Path("results/derived")
DEFAULT_TABLE_PATH = Path("paper/tables/results_summary.tex")
DEFAULT_FIGURE_DIR = Path("paper/figures")
LOG_PLOT_FLOOR = 1e-12


class ArtifactError(ValueError):
    """Raised when an aggregate is not eligible for the requested artifacts."""


def _validate_input_binding(record: Mapping[str, Any], *, label: str) -> None:
    inputs = record.get("inputs")
    digest = record.get("input_set_sha256")
    if not isinstance(inputs, list) or not inputs or not isinstance(digest, str):
        raise ArtifactError(f"{label} is not bound to input hashes")
    actual = hashlib.sha256(canonical_json(inputs).encode("ascii")).hexdigest()
    if actual != digest:
        raise ArtifactError(f"{label} input hash binding is invalid")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_aggregate(source: Mapping[str, Any] | str | Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    if isinstance(source, Mapping):
        aggregate = dict(source)
        source_inputs: list[dict[str, str]] = []
    else:
        path = Path(source)
        if path.is_dir():
            try:
                aggregate = aggregate_results(path, seed_set="evaluation")
            except AggregationError as exc:
                raise ArtifactError(str(exc)) from exc
            source_inputs = []
        else:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ArtifactError(f"cannot load aggregate {path}: {exc}") from exc
            if not isinstance(value, dict):
                raise ArtifactError("aggregate JSON must contain an object")
            aggregate = value
            source_inputs = [{"path": str(path), "sha256": _sha256(path)}]
    raw_inputs = aggregate.get("inputs", [])
    if isinstance(raw_inputs, Sequence) and not isinstance(raw_inputs, (str, bytes)):
        for item in raw_inputs:
            if (
                isinstance(item, Mapping)
                and isinstance(item.get("path"), str)
                and isinstance(item.get("sha256"), str)
            ):
                source_inputs.append(
                    {"path": str(item["path"]), "sha256": str(item["sha256"])}
                )
    deduplicated = {
        (item["path"], item["sha256"]): item for item in source_inputs
    }
    return aggregate, sorted(
        deduplicated.values(), key=lambda item: (item["path"], item["sha256"])
    )


def validate_primary_aggregate(aggregate: Mapping[str, Any]) -> None:
    """Reject smoke, legacy, tuning-only, or incomplete evaluation aggregates."""

    if aggregate.get("schema_version") != 1:
        raise ArtifactError("primary artifacts require schema_version 1; legacy input refused")
    if aggregate.get("event") != "executed_policy_aggregate":
        raise ArtifactError("primary artifacts require an executed-policy aggregate")
    if aggregate.get("all_runs_executed_policy") is not True:
        raise ArtifactError("primary artifacts require only executed online policies")
    if aggregate.get("all_seed_provenance_disjoint") is not True:
        raise ArtifactError("primary artifacts require disjoint tuning/evaluation provenance")
    profiles = aggregate.get("profiles")
    if profiles != ["full"]:
        raise ArtifactError("primary artifacts require the full profile; smoke input refused")
    seed_sets = aggregate.get("seed_sets")
    if seed_sets != ["evaluation"]:
        raise ArtifactError("primary artifacts require evaluation runs, not tuning runs")
    groups = aggregate.get("groups")
    if not isinstance(groups, Sequence) or isinstance(groups, (str, bytes)) or not groups:
        raise ArtifactError("primary artifacts require at least one evaluation group")
    for index, group in enumerate(groups):
        if not isinstance(group, Mapping):
            raise ArtifactError(f"aggregate group {index} is malformed")
        if group.get("profile") != "full" or group.get("seed_set") != "evaluation":
            raise ArtifactError("primary group is not a full-profile evaluation")
        if group.get("complete_declared_seed_set") is not True:
            raise ArtifactError(
                f"evaluation group {index} is missing one or more declared seeds"
            )
        seeds = group.get("seeds")
        declared = group.get("declared_seeds")
        if not isinstance(seeds, list) or not isinstance(declared, list) or set(seeds) != set(declared):
            raise ArtifactError(f"evaluation group {index} has incomplete seed provenance")
        inputs = group.get("inputs")
        digest = group.get("input_set_sha256")
        if not isinstance(inputs, list) or not inputs or not isinstance(digest, str):
            raise ArtifactError(f"evaluation group {index} lacks input hash binding")
        actual = hashlib.sha256(canonical_json(inputs).encode("ascii")).hexdigest()
        if actual != digest:
            raise ArtifactError(f"evaluation group {index} input hash is invalid")
    offline_groups = aggregate.get("offline_diagnostic_groups", [])
    if not isinstance(offline_groups, Sequence) or isinstance(
        offline_groups, (str, bytes)
    ):
        raise ArtifactError("offline_diagnostic_groups must be a list")
    for index, group in enumerate(offline_groups):
        if not isinstance(group, Mapping):
            raise ArtifactError(f"offline diagnostic group {index} is malformed")
        if (
            group.get("executed_policy") is not False
            or group.get("offline_diagnostic") is not True
            or group.get("causal_regret_claim") is not False
            or group.get("regret_reported") is not False
        ):
            raise ArtifactError(f"offline diagnostic group {index} has unsafe claims")
        inputs = group.get("inputs")
        digest = group.get("input_set_sha256")
        if not isinstance(inputs, list) or not inputs or not isinstance(digest, str):
            raise ArtifactError(f"offline diagnostic group {index} lacks input hashes")
        actual = hashlib.sha256(canonical_json(inputs).encode("ascii")).hexdigest()
        if actual != digest:
            raise ArtifactError(f"offline diagnostic group {index} input hash is invalid")
    paired = aggregate.get("paired_comparisons", [])
    if not isinstance(paired, Sequence) or isinstance(paired, (str, bytes)):
        raise ArtifactError("paired_comparisons must be a list")
    for index, comparison in enumerate(paired):
        if not isinstance(comparison, Mapping):
            raise ArtifactError(f"paired comparison {index} is malformed")
        if comparison.get("complete_common_seed_set") is not True:
            raise ArtifactError(f"paired comparison {index} lacks a complete common seed set")
        inputs = comparison.get("inputs")
        digest = comparison.get("input_set_sha256")
        if not isinstance(inputs, list) or not inputs or not isinstance(digest, str):
            raise ArtifactError(f"paired comparison {index} is not bound to input hashes")
        actual = hashlib.sha256(canonical_json(inputs).encode("ascii")).hexdigest()
        if actual != digest:
            raise ArtifactError(f"paired comparison {index} input hash binding is invalid")
    audits = aggregate.get("hypothesis_audits", [])
    if not isinstance(audits, Sequence) or isinstance(audits, (str, bytes)):
        raise ArtifactError("hypothesis_audits must be a list")
    for index, audit in enumerate(audits):
        if not isinstance(audit, Mapping):
            raise ArtifactError(f"hypothesis audit {index} is malformed")
        inputs = audit.get("inputs")
        digest = audit.get("input_set_sha256")
        if not isinstance(inputs, list) or not inputs or not isinstance(digest, str):
            raise ArtifactError(f"hypothesis audit {index} is not bound to input hashes")
        actual = hashlib.sha256(canonical_json(inputs).encode("ascii")).hexdigest()
        if actual != digest:
            raise ArtifactError(f"hypothesis audit {index} input hash binding is invalid")


def _flatten_rows(aggregate: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    groups = aggregate.get("groups", [])
    if not isinstance(groups, Sequence):
        return rows
    for group in groups:
        if not isinstance(group, Mapping):
            continue
        base = {
            "experiment": group.get("experiment", ""),
            "profile": group.get("profile", ""),
            "seed_set": group.get("seed_set", ""),
            "comparison": group.get("comparison", ""),
            "method": group.get("method", ""),
            "reference_method": "",
            "difference_direction": "",
            "variant_json": canonical_json(group.get("variant", {})),
            "hyperparameters_json": canonical_json(group.get("hyperparameters", {})),
            "run_count": group.get("run_count", 0),
        }
        sections: list[tuple[str, int | str, Any]] = [
            ("summary", "", group.get("summary_metrics", {}))
        ]
        horizons = group.get("horizons", [])
        if isinstance(horizons, Sequence):
            for horizon in horizons:
                if isinstance(horizon, Mapping):
                    sections.append(
                        ("horizon", horizon.get("horizon", ""), horizon.get("metrics", {}))
                    )
        for scope, horizon_value, metrics in sections:
            if not isinstance(metrics, Mapping):
                continue
            for metric, stats in sorted(metrics.items()):
                if not isinstance(stats, Mapping):
                    continue
                rows.append(
                    {
                        **base,
                        "scope": scope,
                        "horizon": horizon_value,
                        "metric": metric,
                        "n": stats.get("n", ""),
                        "mean": stats.get("mean", ""),
                        "standard_deviation": stats.get("standard_deviation", ""),
                        "standard_error": stats.get("standard_error", ""),
                        "ci95_low": stats.get("ci95_low", ""),
                        "ci95_high": stats.get("ci95_high", ""),
                        "ci95_half_width": stats.get("ci95_half_width", ""),
                    }
                )
    offline_groups = aggregate.get("offline_diagnostic_groups", [])
    if isinstance(offline_groups, Sequence):
        for group in offline_groups:
            if not isinstance(group, Mapping):
                continue
            base = {
                "experiment": group.get("experiment", ""),
                "profile": group.get("profile", ""),
                "seed_set": group.get("seed_set", ""),
                "comparison": "offline_common_trajectory_diagnostic",
                "method": group.get("method", ""),
                "reference_method": "",
                "difference_direction": "offline_noncausal_not_executed_policy",
                "variant_json": canonical_json(group.get("variant", {})),
                "hyperparameters_json": canonical_json(group.get("hyperparameters", {})),
                "run_count": group.get("run_count", 0),
            }
            sections: list[tuple[str, int | str, Any]] = [
                ("offline_summary", "", group.get("summary_metrics", {}))
            ]
            horizons = group.get("horizons", [])
            if isinstance(horizons, Sequence):
                for horizon in horizons:
                    if isinstance(horizon, Mapping):
                        sections.append(
                            (
                                "offline_horizon",
                                horizon.get("horizon", ""),
                                horizon.get("metrics", {}),
                            )
                        )
            for scope, horizon_value, metrics in sections:
                if not isinstance(metrics, Mapping):
                    continue
                for metric, stats in sorted(metrics.items()):
                    if not isinstance(stats, Mapping):
                        continue
                    rows.append(
                        {
                            **base,
                            "scope": scope,
                            "horizon": horizon_value,
                            "metric": metric,
                            "n": stats.get("n", ""),
                            "mean": stats.get("mean", ""),
                            "standard_deviation": stats.get("standard_deviation", ""),
                            "standard_error": stats.get("standard_error", ""),
                            "ci95_low": stats.get("ci95_low", ""),
                            "ci95_high": stats.get("ci95_high", ""),
                            "ci95_half_width": stats.get("ci95_half_width", ""),
                        }
                    )
    benchmark_groups = aggregate.get("benchmark_diagnostic_groups", [])
    if isinstance(benchmark_groups, Sequence):
        for group in benchmark_groups:
            if not isinstance(group, Mapping):
                continue
            metrics = group.get("summary_metrics", {})
            if not isinstance(metrics, Mapping):
                continue
            base = {
                "experiment": group.get("experiment", ""),
                "profile": group.get("profile", ""),
                "seed_set": group.get("seed_set", ""),
                "comparison": "benchmark_diagnostic",
                "method": group.get("method", ""),
                "reference_method": "",
                "difference_direction": "diagnostic_not_executed_policy",
                "variant_json": canonical_json(group.get("variant", {})),
                "hyperparameters_json": "{}",
                "run_count": group.get("run_count", 0),
                "scope": "benchmark_summary",
                "horizon": "",
            }
            for metric, stats in sorted(metrics.items()):
                if not isinstance(stats, Mapping):
                    continue
                rows.append(
                    {
                        **base,
                        "metric": metric,
                        "n": stats.get("n", ""),
                        "mean": stats.get("mean", ""),
                        "standard_deviation": stats.get("standard_deviation", ""),
                        "standard_error": stats.get("standard_error", ""),
                        "ci95_low": stats.get("ci95_low", ""),
                        "ci95_high": stats.get("ci95_high", ""),
                        "ci95_half_width": stats.get("ci95_half_width", ""),
                    }
                )
    benchmark_audits = aggregate.get("benchmark_diagnostic_audits", [])
    if isinstance(benchmark_audits, Sequence):
        for audit in benchmark_audits:
            if not isinstance(audit, Mapping):
                continue
            common = {
                "experiment": audit.get("experiment", ""),
                "profile": audit.get("profile", ""),
                "seed_set": audit.get("seed_set", ""),
                "comparison": audit.get("name", ""),
                "run_count": len(audit.get("run_directories", [])),
                "horizon": "",
            }
            totals = audit.get("validation_totals", {})
            if isinstance(totals, Mapping):
                for metric, value in sorted(totals.items()):
                    rows.append(
                        {
                            **common,
                            "method": "",
                            "reference_method": "",
                            "difference_direction": "diagnostic_validation",
                            "variant_json": "{}",
                            "hyperparameters_json": "{}",
                            "scope": "benchmark_validation",
                            "metric": metric,
                            "n": "",
                            "mean": value,
                            "standard_deviation": "",
                            "standard_error": "",
                            "ci95_low": "",
                            "ci95_high": "",
                            "ci95_half_width": "",
                        }
                    )
            warm = audit.get("warm_start_comparisons", [])
            if isinstance(warm, Sequence):
                for comparison in warm:
                    if not isinstance(comparison, Mapping):
                        continue
                    variant = {
                        key: comparison[key]
                        for key in (
                            "condition_number",
                            "target_relative_energy_error",
                            "preconditioner",
                        )
                    }
                    for metric in (
                        "mean_cg_iterations_difference",
                        "mean_initial_relative_energy_error_difference",
                    ):
                        stats = comparison.get(metric)
                        if not isinstance(stats, Mapping):
                            continue
                        rows.append(
                            {
                                **common,
                                "method": "warm",
                                "reference_method": "zero",
                                "difference_direction": "warm_minus_zero",
                                "variant_json": canonical_json(variant),
                                "hyperparameters_json": "{}",
                                "scope": "benchmark_paired",
                                "metric": metric,
                                "n": stats.get("n", ""),
                                "mean": stats.get("mean", ""),
                                "standard_deviation": stats.get(
                                    "standard_deviation", ""
                                ),
                                "standard_error": stats.get("standard_error", ""),
                                "ci95_low": stats.get("ci95_low", ""),
                                "ci95_high": stats.get("ci95_high", ""),
                                "ci95_half_width": stats.get("ci95_half_width", ""),
                            }
                        )
            if "width_sandwich_violation_count" in audit:
                rows.append(
                    {
                        **common,
                        "method": "",
                        "reference_method": "",
                        "difference_direction": "diagnostic_validation",
                        "variant_json": "{}",
                        "hyperparameters_json": "{}",
                        "scope": "benchmark_validation",
                        "metric": "width_sandwich_violation_count",
                        "n": "",
                        "mean": audit["width_sandwich_violation_count"],
                        "standard_deviation": "",
                        "standard_error": "",
                        "ci95_low": "",
                        "ci95_high": "",
                        "ci95_half_width": "",
                    }
                )
    paired = aggregate.get("paired_comparisons", [])
    if isinstance(paired, Sequence):
        for comparison in paired:
            if not isinstance(comparison, Mapping):
                continue
            base = {
                "experiment": comparison.get("experiment", ""),
                "profile": comparison.get("profile", ""),
                "seed_set": comparison.get("seed_set", ""),
                "comparison": comparison.get("comparison", ""),
                "method": comparison.get("method", ""),
                "reference_method": comparison.get("reference_method", ""),
                "difference_direction": comparison.get("difference_direction", ""),
                "variant_json": canonical_json(comparison.get("variant", {})),
                "hyperparameters_json": canonical_json(
                    comparison.get("hyperparameters", {})
                ),
                "run_count": comparison.get("pair_count", 0),
            }
            sections: list[tuple[str, int | str, Any]] = [
                ("paired_summary", "", comparison.get("summary_metrics", {}))
            ]
            horizons = comparison.get("horizons", [])
            if isinstance(horizons, Sequence):
                for horizon in horizons:
                    if isinstance(horizon, Mapping):
                        sections.append(
                            (
                                "paired_horizon",
                                horizon.get("horizon", ""),
                                horizon.get("metrics", {}),
                            )
                        )
            for scope, horizon_value, metrics in sections:
                if not isinstance(metrics, Mapping):
                    continue
                for metric, stats in sorted(metrics.items()):
                    if not isinstance(stats, Mapping):
                        continue
                    rows.append(
                        {
                            **base,
                            "scope": scope,
                            "horizon": horizon_value,
                            "metric": metric,
                            "n": stats.get("n", ""),
                            "mean": stats.get("mean", ""),
                            "standard_deviation": stats.get(
                                "standard_deviation", ""
                            ),
                            "standard_error": stats.get("standard_error", ""),
                            "ci95_low": stats.get("ci95_low", ""),
                            "ci95_high": stats.get("ci95_high", ""),
                            "ci95_half_width": stats.get("ci95_half_width", ""),
                        }
                    )
    audits = aggregate.get("hypothesis_audits", [])
    if isinstance(audits, Sequence):
        for audit in audits:
            if not isinstance(audit, Mapping):
                continue
            common = {
                "experiment": audit.get("experiment", ""),
                "profile": audit.get("profile", ""),
                "seed_set": audit.get("seed_set", ""),
                "comparison": audit.get("name", ""),
                "variant_json": "{}",
                "hyperparameters_json": "{}",
                "run_count": audit.get("n_cells", 0),
                "scope": "hypothesis_audit",
                "horizon": "",
            }
            correlations = audit.get("correlations", [])
            if isinstance(correlations, Sequence):
                for correlation in correlations:
                    if not isinstance(correlation, Mapping):
                        continue
                    rows.append(
                        {
                            **common,
                            "method": correlation.get("predictor", ""),
                            "reference_method": audit.get("outcome", ""),
                            "difference_direction": "descriptive_noncausal_nonindependent",
                            "metric": "spearman_rho",
                            "n": correlation.get("n", ""),
                            "mean": correlation.get("spearman_rho", ""),
                            "standard_deviation": "",
                            "standard_error": "",
                            "ci95_low": "",
                            "ci95_high": "",
                            "ci95_half_width": "",
                        }
                    )
            hypotheses = audit.get("hypotheses", [])
            if isinstance(hypotheses, Sequence):
                for hypothesis in hypotheses:
                    if not isinstance(hypothesis, Mapping):
                        continue
                    rows.append(
                        {
                            **common,
                            "method": hypothesis.get("name", ""),
                            "reference_method": "",
                            "difference_direction": hypothesis.get("status", ""),
                            "metric": "hypothesis_status",
                            "n": audit.get("n_cells", ""),
                            "mean": "",
                            "standard_deviation": "",
                            "standard_error": "",
                            "ci95_low": "",
                            "ci95_high": "",
                            "ci95_half_width": "",
                        }
                    )
    return rows


CSV_FIELDS = (
    "experiment",
    "profile",
    "seed_set",
    "comparison",
    "method",
    "reference_method",
    "difference_direction",
    "variant_json",
    "hyperparameters_json",
    "run_count",
    "scope",
    "horizon",
    "metric",
    "n",
    "mean",
    "standard_deviation",
    "standard_error",
    "ci95_low",
    "ci95_high",
    "ci95_half_width",
)


def _csv_text(aggregate: Mapping[str, Any]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(_flatten_rows(aggregate))
    return stream.getvalue()


def _tex_escape(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(character, character) for character in text)


def _short_experiment(name: Any) -> str:
    aliases = {
        "linear_audit": "Linear",
        "nonlinear_audit": "Nonlinear",
        "nonlinear_drift": "Nonlinear",
        "covertype_rerun": "Covertype",
    }
    text = str(name)
    return aliases.get(text, text.replace("_", " ").title())


def _format_estimate(stats: Any) -> str:
    if not isinstance(stats, Mapping):
        return "--"
    mean = stats.get("mean")
    half = stats.get("ci95_half_width")
    if not isinstance(mean, (int, float)) or not math.isfinite(float(mean)):
        return "--"
    if not isinstance(half, (int, float)) or not math.isfinite(float(half)):
        return f"{float(mean):.3g}"
    return f"{float(mean):.3g} $\\pm$ {float(half):.2g}"


def _final_horizon(group: Mapping[str, Any]) -> Mapping[str, Any] | None:
    horizons = group.get("horizons")
    if not isinstance(horizons, Sequence) or not horizons:
        return None
    valid = [item for item in horizons if isinstance(item, Mapping)]
    return max(valid, key=lambda item: int(item.get("horizon", 0))) if valid else None


def _format_scaled_estimate(stats: Any, *, scale: float = 1.0) -> str:
    if not isinstance(stats, Mapping):
        return "--"
    mean = stats.get("mean")
    half = stats.get("ci95_half_width")
    if not isinstance(mean, (int, float)) or not math.isfinite(float(mean)):
        return "--"
    scaled_mean = float(mean) * scale
    if (
        not isinstance(half, (int, float))
        or not math.isfinite(float(half))
        or float(half) == 0.0
    ):
        return f"{scaled_mean:.3g}"
    return f"{scaled_mean:.3g} $\\pm$ {float(half) * scale:.2g}"


def _cg_benchmark_latex_table(
    groups: Sequence[Any], audits: Sequence[Any]
) -> str | None:
    cells: dict[tuple[float, float, str], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for group in groups:
        if not isinstance(group, Mapping) or group.get("experiment") != "cg_accuracy":
            continue
        variant = group.get("variant")
        if not isinstance(variant, Mapping):
            continue
        try:
            key = (
                float(variant["condition_number"]),
                float(variant["target_relative_energy_error"]),
                str(variant["preconditioner"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
        initialization = str(variant.get("initialization", ""))
        if initialization in {"zero", "warm"}:
            cells[key][initialization] = group
    if not cells:
        return None

    differences: dict[tuple[float, float, str], Mapping[str, Any]] = {}
    validation_ok = False
    for audit in audits:
        if not isinstance(audit, Mapping) or audit.get("experiment") != "cg_accuracy":
            continue
        validation_ok = (
            audit.get("all_target_residual_sandwich_optimism_violations_zero") is True
        )
        comparisons = audit.get("warm_start_comparisons", [])
        if not isinstance(comparisons, Sequence):
            continue
        for comparison in comparisons:
            if not isinstance(comparison, Mapping):
                continue
            try:
                key = (
                    float(comparison["condition_number"]),
                    float(comparison["target_relative_energy_error"]),
                    str(comparison["preconditioner"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            differences[key] = comparison

    lines = [
        "% CG accuracy diagnostic: evaluation-seed means and 95% Student-t intervals.",
        r"\begin{tabular}{rrlrrrrr}",
        r"\toprule",
        r"$\kappa$ & Target & Prec. & Iter. (zero) & Iter. (warm) & $\Delta$ iter. & Time zero (ms) & Time warm (ms) \\",
        r"\midrule",
    ]
    for key in sorted(cells, key=lambda item: (item[0], -item[1], item[2])):
        pair = cells[key]
        zero_metrics = pair.get("zero", {}).get("summary_metrics", {})
        warm_metrics = pair.get("warm", {}).get("summary_metrics", {})
        zero_metrics = zero_metrics if isinstance(zero_metrics, Mapping) else {}
        warm_metrics = warm_metrics if isinstance(warm_metrics, Mapping) else {}
        difference = differences.get(key, {})
        lines.append(
            "{} & {} & {} & {} & {} & {} & {} & {} \\\\".format(
                f"{key[0]:g}",
                f"{key[1]:g}",
                _tex_escape(key[2]),
                _format_scaled_estimate(zero_metrics.get("mean_cg_iterations")),
                _format_scaled_estimate(warm_metrics.get("mean_cg_iterations")),
                _format_scaled_estimate(
                    difference.get("mean_cg_iterations_difference")
                ),
                _format_scaled_estimate(
                    zero_metrics.get("mean_wall_time_seconds"), scale=1000.0
                ),
                _format_scaled_estimate(
                    warm_metrics.get("mean_wall_time_seconds"), scale=1000.0
                ),
            )
        )
    lines.append(r"\midrule")
    if validation_ok:
        lines.append(
            r"\multicolumn{8}{l}{All target, residual-certificate, width-sandwich, and optimism violations: 0.} \\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    return "\n".join(lines)


def _systems_benchmark_latex_table(
    groups: Sequence[Any], audits: Sequence[Any]
) -> str | None:
    systems = [
        group
        for group in groups
        if isinstance(group, Mapping) and group.get("experiment") == "systems_scaling"
    ]
    if not systems:
        return None

    variants = [
        group.get("variant")
        for group in systems
        if isinstance(group.get("variant"), Mapping)
    ]
    if not variants:
        return None
    max_n = max(int(variant.get("sample_count", 0)) for variant in variants)
    max_k = max(int(variant.get("action_count", 0)) for variant in variants)
    max_i = max(int(variant.get("iteration_budget", 0)) for variant in variants)
    selected = [
        group
        for group in systems
        if isinstance(group.get("variant"), Mapping)
        and int(group["variant"].get("sample_count", 0)) == max_n
        and int(group["variant"].get("action_count", 0)) == max_k
        and int(group["variant"].get("iteration_budget", 0)) == max_i
    ]

    validation_ok = any(
        isinstance(audit, Mapping)
        and audit.get("experiment") == "systems_scaling"
        and audit.get("all_width_sandwich_checks_hold") is True
        for audit in audits
    )
    lines = [
        "% Systems scaling diagnostic: largest n/K/I slice; full grid is in JSON/CSV.",
        r"\begin{tabular}{rlrrrrrr}",
        r"\toprule",
        r"$d$ & Method & $n$ & $K$ & $I$ & Time (ms) & Working memory (KiB) & Width rel. error \\",
        r"\midrule",
    ]
    for group in sorted(
        selected,
        key=lambda item: (
            int(item["variant"].get("dimension", 0)),
            str(item.get("method", "")),
        ),
    ):
        variant = group["variant"]
        metrics = group.get("summary_metrics", {})
        metrics = metrics if isinstance(metrics, Mapping) else {}
        lines.append(
            "{} & {} & {} & {} & {} & {} & {} & {} \\\\".format(
                int(variant.get("dimension", 0)),
                _tex_escape(group.get("method", "")),
                int(variant.get("sample_count", 0)),
                int(variant.get("action_count", 0)),
                int(variant.get("iteration_budget", 0)),
                _format_scaled_estimate(
                    metrics.get("wall_time_seconds"), scale=1000.0
                ),
                _format_scaled_estimate(
                    metrics.get("estimated_working_memory_bytes"), scale=1.0 / 1024.0
                ),
                _format_scaled_estimate(
                    metrics.get("predictive_width_relative_error")
                ),
            )
        )
    lines.append(r"\midrule")
    lines.append(
        rf"\multicolumn{{8}}{{l}}{{Largest slice: $n={max_n}$, $K={max_k}$, $I={max_i}$; complete grid in JSON/CSV.}} \\"
    )
    if validation_ok:
        lines.append(r"\multicolumn{8}{l}{All logged width-sandwich checks hold.} \\")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    return "\n".join(lines)


def _benchmark_latex_table(aggregate: Mapping[str, Any]) -> str | None:
    groups = aggregate.get("benchmark_diagnostic_groups", [])
    audits = aggregate.get("benchmark_diagnostic_audits", [])
    if not isinstance(groups, Sequence) or isinstance(groups, (str, bytes)):
        return None
    if not isinstance(audits, Sequence) or isinstance(audits, (str, bytes)):
        audits = []
    tables = [
        table
        for table in (
            _cg_benchmark_latex_table(groups, audits),
            _systems_benchmark_latex_table(groups, audits),
        )
        if table is not None
    ]
    if not tables:
        return None
    return (
        "% Auto-generated by experiments.make_paper_artifacts; do not edit.\n"
        + "\n\n".join(tables)
        + "\n"
    )


def _latex_table(aggregate: Mapping[str, Any]) -> str:
    benchmark_table = _benchmark_latex_table(aggregate)
    groups = aggregate.get("groups", [])
    if benchmark_table is not None and not groups:
        return benchmark_table
    lines = [
        "% Auto-generated by experiments.make_paper_artifacts; do not edit.",
        r"\begin{tabular}{lllrrrr}",
        r"\toprule",
        r"Study & Policy & Comparison & $T$ & Regret & Reported RHS & Runtime (s) \\",
        r"\midrule",
    ]
    drift_order = {"frozen_head": 0, "mild": 1, "medium": 2, "aggressive": 3}

    def group_order(group: Any) -> tuple[Any, ...]:
        if not isinstance(group, Mapping):
            return ("", 99, "", "")
        method = str(group.get("method", ""))
        variant = group.get("variant", {})
        center = str(variant.get("center", "")) if isinstance(variant, Mapping) else ""
        return (
            str(group.get("experiment", "")),
            drift_order.get(method, 10),
            method,
            0 if center == "original" else 1,
            center,
            str(group.get("comparison", "")),
        )

    ordered_groups = sorted(groups, key=group_order) if isinstance(groups, Sequence) else []
    for group in ordered_groups:
        if not isinstance(group, Mapping):
            continue
        final = _final_horizon(group)
        if final is None:
            continue
        metrics = final.get("metrics", {})
        if not isinstance(metrics, Mapping):
            metrics = {}
        variant = group.get("variant", {})
        method = str(group.get("method", ""))
        if isinstance(variant, Mapping) and variant.get("center"):
            method += f"/{variant['center']}"
        lines.append(
            "{} & {} & {} & {} & {} & {} & {} \\\\".format(
                _tex_escape(_short_experiment(group.get("experiment", ""))),
                _tex_escape(method),
                _tex_escape(group.get("comparison", "default")),
                int(final.get("horizon", 0)),
                _format_estimate(metrics.get("cumulative_pseudo_regret")),
                _format_estimate(metrics.get("theorem_rhs")),
                _format_estimate(metrics.get("runtime_seconds")),
            )
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    return "\n".join(lines)


def _nonlinear_plot_points(
    aggregate: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], bool]:
    groups = aggregate.get("groups", [])
    nonlinear = [
        group
        for group in groups
        if isinstance(group, Mapping)
        and "nonlinear" in str(group.get("experiment", "")).lower()
    ] if isinstance(groups, Sequence) else []
    points: list[dict[str, Any]] = []
    metric_candidates = {
        "regret": ("cumulative_pseudo_regret",),
        "optimism": (
            "optimism_violation_rate",
            "policy_optimism_violation_rate",
        ),
        "linearization": ("E_T", "posthoc_E_including_round"),
        "centering": ("psi_t", "psi_T", "posthoc_primitive_psi"),
        "transfer": (
            "max_diagnostic_u_t",
            "diagnostic_u_t",
            "u_T",
            "max_u_t",
            "u_t",
        ),
        "information": ("Lambda_alg_T", "posthoc_Lambda_algorithmic"),
        "variation": ("V_alg_T", "posthoc_V_variation_charge"),
    }

    def find_stats(sources: Sequence[Mapping[str, Any]], names: Sequence[str]) -> dict[str, float] | None:
        for source in sources:
            for name in names:
                stats = source.get(name)
                if not isinstance(stats, Mapping) or not isinstance(
                    stats.get("mean"), (int, float)
                ):
                    continue
                mean = float(stats["mean"])
                low = float(stats.get("ci95_low", mean))
                high = float(stats.get("ci95_high", mean))
                if all(math.isfinite(value) for value in (mean, low, high)):
                    return {"mean": mean, "low": low, "high": high}
        return None

    for group in nonlinear:
        final = _final_horizon(group)
        if final is None or not isinstance(final.get("metrics"), Mapping):
            continue
        metrics = final["metrics"]
        summary = group.get("summary_metrics", {})
        summary = summary if isinstance(summary, Mapping) else {}
        variant = group.get("variant", {})
        variant = variant if isinstance(variant, Mapping) else {}
        points.append(
            {
                "regime": str(
                    variant.get("drift_name")
                    or variant.get("drift_level")
                    or group.get("method", "unknown")
                ),
                "center": str(variant.get("center", group.get("comparison", "default"))),
                "metrics": {
                    metric: stats
                    for metric, names in metric_candidates.items()
                    if (stats := find_stats((metrics, summary), names)) is not None
                },
            }
        )
    return points, bool(nonlinear)


def _make_theory_factor_plot(
    aggregate: Mapping[str, Any], pdf_path: Path, png_path: Path
) -> bool:
    points, nonlinear_exists = _nonlinear_plot_points(aggregate)
    if not nonlinear_exists:
        return False
    if not points:
        raise ArtifactError(
            "nonlinear artifacts exist but contain no theory-transfer factor metric"
        )
    try:
        import matplotlib

        matplotlib.use("Agg")
        matplotlib.rcParams["pdf.fonttype"] = 42
        matplotlib.rcParams["ps.fonttype"] = 42
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - matplotlib is pinned.
        raise ArtifactError("matplotlib is required for nonlinear paper artifacts") from exc

    preferred_order = ["frozen_head", "mild", "medium", "aggressive"]
    regimes = sorted(
        {point["regime"] for point in points},
        key=lambda name: (
            preferred_order.index(name) if name in preferred_order else len(preferred_order),
            name,
        ),
    )
    positions = {name: index for index, name in enumerate(regimes)}
    by_center: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for point in points:
        by_center[point["center"]].append(point)

    from matplotlib.lines import Line2D

    center_order = sorted(
        by_center,
        key=lambda center: (0 if center == "original" else 1, center),
    )
    colors = {"original": "#0072B2", "corrected": "#D55E00"}
    markers = {"original": "o", "corrected": "s"}
    fallback_colors = ("#009E73", "#CC79A7")
    for index, center in enumerate(center_order):
        colors.setdefault(center, fallback_colors[index % len(fallback_colors)])
        markers.setdefault(center, ("^", "D")[index % 2])

    fig, axes = plt.subplots(
        2,
        3,
        figsize=(10.2, 6.15),
        sharex=True,
        constrained_layout=True,
    )

    def draw_metric(
        axis: Any,
        metric: str,
        title: str,
        ylabel: str,
        *,
        scale: float = 1.0,
        log_scale: bool = False,
    ) -> None:
        plotted = False
        for center in center_order:
            available = [
                point
                for point in by_center[center]
                if metric in point.get("metrics", {})
            ]
            ordered = sorted(available, key=lambda point: positions[point["regime"]])
            if not ordered:
                continue
            x = [positions[point["regime"]] for point in ordered]
            stats = [point["metrics"][metric] for point in ordered]
            raw_y = [item["mean"] * scale for item in stats]
            raw_low = [item["low"] * scale for item in stats]
            raw_high = [item["high"] * scale for item in stats]
            if log_scale:
                y = [max(LOG_PLOT_FLOOR, value) for value in raw_y]
                plotted_low = [max(LOG_PLOT_FLOOR, value) for value in raw_low]
                plotted_high = [max(LOG_PLOT_FLOOR, value) for value in raw_high]
            else:
                y = raw_y
                plotted_low = raw_low
                plotted_high = raw_high
            lower = [max(0.0, mean - low) for mean, low in zip(y, plotted_low, strict=True)]
            upper = [max(0.0, high - mean) for mean, high in zip(y, plotted_high, strict=True)]
            axis.errorbar(
                x,
                y,
                yerr=[lower, upper],
                color=colors[center],
                marker=markers[center],
                linewidth=1.45,
                markersize=4.5,
                capsize=2.5,
            )
            plotted = True
        axis.set_title(title, fontsize=10)
        axis.set_ylabel(ylabel, fontsize=9)
        if log_scale and plotted:
            axis.set_yscale("log")
        if not plotted:
            axis.text(0.5, 0.5, "not recorded", ha="center", va="center", transform=axis.transAxes)
        axis.grid(axis="y", color="#D9D9D9", linewidth=0.65)
        axis.spines[["top", "right"]].set_visible(False)
        axis.tick_params(labelsize=8)

    draw_metric(
        axes[0, 0],
        "regret",
        "(a) Executed-policy outcome",
        "Cumulative pseudo-regret",
    )
    draw_metric(
        axes[0, 1],
        "optimism",
        "(b) Executed-policy coverage",
        "All-action violations (%)",
        scale=100.0,
    )
    draw_metric(
        axes[0, 2],
        "linearization",
        "(c) Linearization audit",
        r"Post-hoc $E_T$ (log scale)",
        log_scale=True,
    )
    draw_metric(
        axes[1, 0],
        "centering",
        "(d) Post-hoc centering discrepancy",
        r"Primitive $\psi_T^{\rm audit}$ (log scale)",
        log_scale=True,
    )
    draw_metric(
        axes[1, 1],
        "transfer",
        "(e) Feature-drift transfer audit",
        r"Max post-hoc $u_t$",
    )

    dynamic_axis = axes[1, 2]
    variation_axis = dynamic_axis.twinx()
    dynamic_plotted = False
    for center in center_order:
        ordered = sorted(by_center[center], key=lambda point: positions[point["regime"]])
        for metric, axis, linestyle, marker in (
            ("information", dynamic_axis, "-", markers[center]),
            ("variation", variation_axis, "--", "^"),
        ):
            available = [point for point in ordered if metric in point.get("metrics", {})]
            if not available:
                continue
            x = [positions[point["regime"]] for point in available]
            stats = [point["metrics"][metric] for point in available]
            y = [item["mean"] for item in stats]
            lower = [max(0.0, item["mean"] - item["low"]) for item in stats]
            upper = [max(0.0, item["high"] - item["mean"]) for item in stats]
            axis.errorbar(
                x,
                y,
                yerr=[lower, upper],
                color=colors[center],
                linestyle=linestyle,
                marker=marker,
                linewidth=1.35,
                markersize=4.2,
                capsize=2.2,
            )
            dynamic_plotted = True
    dynamic_axis.set_title("(f) Dynamic-complexity audit", fontsize=10)
    dynamic_axis.set_ylabel(r"Post-hoc $\Lambda_T$", fontsize=9)
    variation_axis.set_ylabel(r"Post-hoc $V_T$", fontsize=9)
    dynamic_axis.grid(axis="y", color="#D9D9D9", linewidth=0.65)
    dynamic_axis.spines["top"].set_visible(False)
    variation_axis.spines["top"].set_visible(False)
    dynamic_axis.tick_params(labelsize=8)
    variation_axis.tick_params(labelsize=8)
    if not dynamic_plotted:
        dynamic_axis.text(
            0.5, 0.5, "not recorded", ha="center", va="center", transform=dynamic_axis.transAxes
        )
    dynamic_axis.legend(
        handles=[
            Line2D([0], [0], color="#333333", linestyle="-", marker="o", label=r"$\Lambda_T$"),
            Line2D([0], [0], color="#333333", linestyle="--", marker="^", label=r"$V_T$"),
        ],
        loc="upper left",
        frameon=False,
        fontsize=7.5,
    )

    labels = [name.replace("_", " ") for name in regimes]
    for axis in axes[1, :]:
        axis.set_xticks(range(len(regimes)), labels)
        axis.set_xlabel("Drift regime", fontsize=9)
        axis.tick_params(axis="x", labelrotation=18)
    fig.legend(
        handles=[
            Line2D(
                [0],
                [0],
                color=colors[center],
                marker=markers[center],
                linewidth=1.5,
                label=center.replace("_", " "),
            )
            for center in center_order
        ],
        loc="upper right",
        bbox_to_anchor=(0.99, 1.04),
        ncol=max(1, len(center_order)),
        frameon=False,
        fontsize=9,
    )
    fig.suptitle(
        "Executed nonlinear policies with post-hoc decomposition audits",
        fontsize=12,
        x=0.01,
        y=1.035,
        ha="left",
    )
    fig.text(
        0.5,
        -0.015,
        "Means over evaluation seeds; bars are 95% Student-t intervals. "
        "Post-hoc audits are diagnostics, not policy certificates.",
        ha="center",
        va="top",
        fontsize=8,
    )
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        pdf_path,
        bbox_inches="tight",
        metadata={
            "Creator": "experiments.make_paper_artifacts",
            "Title": "Executed nonlinear policies with post-hoc decomposition audits",
            "Subject": "Post-hoc diagnostics; not policy certification",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    fig.savefig(
        png_path,
        dpi=220,
        bbox_inches="tight",
        metadata={"Software": "experiments.make_paper_artifacts"},
    )
    plt.close(fig)
    return True


def _write_sidecar(
    path: Path,
    inputs: Sequence[Mapping[str, str]],
    *,
    generation_parameters: Mapping[str, Any] | None = None,
) -> Path:
    sidecar = path.with_suffix(path.suffix + ".provenance.json")
    record = {
        "schema_version": 1,
        "artifact": str(path),
        "artifact_sha256": _sha256(path),
        "inputs": [
            {"path": str(item["path"]), "sha256": str(item["sha256"])}
            for item in sorted(inputs, key=lambda item: (item["path"], item["sha256"]))
        ],
    }
    if generation_parameters:
        record["generation_parameters"] = dict(generation_parameters)
    sidecar.write_text(
        json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return sidecar


def make_paper_artifacts(
    source: Mapping[str, Any] | str | Path,
    *,
    derived_dir: str | Path = DEFAULT_DERIVED_DIR,
    table_path: str | Path = DEFAULT_TABLE_PATH,
    figure_dir: str | Path = DEFAULT_FIGURE_DIR,
    primary: bool = True,
    output_stem: str = "paper_results",
) -> dict[str, Any]:
    """Create deterministic JSON, CSV, LaTeX, and optional nonlinear figures."""

    aggregate, provenance_inputs = _load_aggregate(source)
    for section_name in (
        "groups",
        "offline_diagnostic_groups",
        "benchmark_diagnostic_groups",
        "paired_comparisons",
        "hypothesis_audits",
        "benchmark_diagnostic_audits",
    ):
        section = aggregate.get(section_name, [])
        if isinstance(section, Sequence) and not isinstance(section, (str, bytes)):
            for index, record in enumerate(section):
                if isinstance(record, Mapping):
                    _validate_input_binding(
                        record, label=f"{section_name}[{index}]"
                    )
    if primary:
        validate_primary_aggregate(aggregate)
    nonlinear_points, nonlinear_exists = _nonlinear_plot_points(aggregate)
    if nonlinear_exists and not nonlinear_points:
        raise ArtifactError(
            "nonlinear artifacts exist but contain no theory-transfer factor metric"
        )

    derived = Path(derived_dir)
    table = Path(table_path)
    figures = Path(figure_dir)
    if (
        not output_stem
        or output_stem in {".", ".."}
        or Path(output_stem).name != output_stem
    ):
        raise ArtifactError("output_stem must be a nonempty filename stem")
    json_path = derived / f"{output_stem}.json"
    csv_path = derived / f"{output_stem}.csv"
    pdf_path = figures / "theory_factor_drift.pdf"
    png_path = figures / "theory_factor_drift.png"
    derived.mkdir(parents=True, exist_ok=True)
    table.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    csv_path.write_text(_csv_text(aggregate), encoding="utf-8", newline="")
    table.write_text(_latex_table(aggregate), encoding="ascii")
    made_plot = _make_theory_factor_plot(aggregate, pdf_path, png_path)

    artifacts = [json_path, csv_path, table]
    if made_plot:
        artifacts.extend((pdf_path, png_path))
    sidecars = [
        _write_sidecar(
            path,
            provenance_inputs,
            generation_parameters={"log_plot_floor": LOG_PLOT_FLOOR}
            if path in {pdf_path, png_path}
            else None,
        )
        for path in artifacts
    ]
    return {
        "schema_version": 1,
        "primary": primary,
        "artifacts": [str(path) for path in artifacts],
        "provenance_sidecars": [str(path) for path in sidecars],
    }


def make_executed_policy_table(
    linear_source: Mapping[str, Any] | str | Path,
    nonlinear_source: Mapping[str, Any] | str | Path,
    destination: str | Path = Path("paper/tables/executed_policy_results.tex"),
) -> dict[str, Any]:
    """Write the compact main-paper table from two completed primary aggregates."""

    linear, linear_inputs = _load_aggregate(linear_source)
    nonlinear, nonlinear_inputs = _load_aggregate(nonlinear_source)
    validate_primary_aggregate(linear)
    validate_primary_aggregate(nonlinear)

    def final_metrics(group: Mapping[str, Any]) -> Mapping[str, Any]:
        final = _final_horizon(group)
        if final is None or not isinstance(final.get("metrics"), Mapping):
            raise ArtifactError("table group lacks final-horizon metrics")
        return final["metrics"]

    def choose_stats(
        group: Mapping[str, Any], *names: str, prefer_summary: bool = True
    ) -> Mapping[str, Any] | None:
        summary = group.get("summary_metrics", {})
        summary = summary if isinstance(summary, Mapping) else {}
        final = final_metrics(group)
        sources = (summary, final) if prefer_summary else (final, summary)
        for source in sources:
            for name in names:
                stats = source.get(name)
                if isinstance(stats, Mapping) and isinstance(
                    stats.get("mean"), (int, float)
                ):
                    return stats
        return None

    def estimate(stats: Mapping[str, Any] | None, digits: int) -> str:
        if stats is None:
            return "--"
        mean = float(stats["mean"])
        half = float(stats.get("ci95_half_width", 0.0))
        return f"{mean:.{digits}f} $\\pm$ {half:.{digits}f}"

    linear_methods = (
        ("dense_full", "Dense"),
        ("cg_full", "CG"),
        ("diagonal", "Diagonal"),
        ("unrescaled_window", "Window-64"),
        ("rescaled_subsample", "Subsample-64"),
    )
    nonlinear_methods = (
        ("frozen_head", "original", "Frozen/orig."),
        ("mild", "original", "Mild/orig."),
        ("mild", "corrected", "Mild/corr."),
        ("medium", "corrected", "Medium/corr."),
        ("aggressive", "corrected", "Aggressive/corr."),
    )
    linear_groups = {
        str(group.get("method")): group
        for group in linear.get("groups", [])
        if isinstance(group, Mapping) and group.get("comparison") == "fixed_reference"
    }
    nonlinear_groups = {
        (
            str(group.get("method")),
            str(group.get("variant", {}).get("center", "")),
        ): group
        for group in nonlinear.get("groups", [])
        if isinstance(group, Mapping) and isinstance(group.get("variant"), Mapping)
    }
    missing_linear = [method for method, _ in linear_methods if method not in linear_groups]
    missing_nonlinear = [
        (method, center)
        for method, center, _ in nonlinear_methods
        if (method, center) not in nonlinear_groups
    ]
    if missing_linear or missing_nonlinear:
        raise ArtifactError(
            f"representative table rows are missing: linear={missing_linear}, "
            f"nonlinear={missing_nonlinear}"
        )

    rows: list[tuple[str, str, Mapping[str, Any], bool]] = [
        ("Linear", label, linear_groups[method], False)
        for method, label in linear_methods
    ] + [
        ("Nonlinear", label, nonlinear_groups[(method, center)], True)
        for method, center, label in nonlinear_methods
    ]
    lines = [
        "% Auto-generated by experiments.make_paper_artifacts; do not edit.",
        r"\begingroup",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{2.6pt}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}llrrrrrr@{}}",
        r"\toprule",
        r"Env. & Method & Regret & Viol. (\%) & $\Lambda_T^{\mathcal C}$ & $u_{\max}$ & CG it./action & Time (s) \\",
        r"\midrule",
    ]
    for index, (environment, label, group, is_nonlinear) in enumerate(rows):
        if index == len(linear_methods):
            lines.append(r"\midrule")
        regret = choose_stats(group, "cumulative_pseudo_regret")
        optimism = choose_stats(
            group,
            "policy_optimism_violation_rate",
            "all_action_optimism_violation_rate",
            "optimism_violation_rate",
        )
        information = choose_stats(group, "Lambda_alg_T")
        transfer = choose_stats(
            group,
            *("max_diagnostic_u_t", "u_T")
            if is_nonlinear
            else ("max_u_t", "u_t"),
            prefer_summary=False,
        )
        cg_iterations = choose_stats(group, "mean_cg_iterations")
        runtime = choose_stats(group, "runtime_seconds")
        optimism_scaled = None
        if optimism is not None:
            optimism_scaled = dict(optimism)
            for key in ("mean", "ci95_half_width", "ci95_low", "ci95_high"):
                if key in optimism_scaled:
                    optimism_scaled[key] = float(optimism_scaled[key]) * 100.0
        lines.append(
            "{} & {} & {} & {} & {} & {} & {} & {} \\\\".format(
                _tex_escape(environment),
                _tex_escape(label),
                estimate(regret, 2),
                estimate(optimism_scaled, 2),
                estimate(information, 1),
                estimate(transfer, 1),
                estimate(cg_iterations, 1),
                estimate(runtime, 2),
            )
        )
    lines.extend([r"\bottomrule", r"\end{tabular*}", r"\endgroup", ""])
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="ascii")
    inputs = sorted(
        {
            (item["path"], item["sha256"]): item
            for item in (*linear_inputs, *nonlinear_inputs)
        }.values(),
        key=lambda item: (item["path"], item["sha256"]),
    )
    sidecar = _write_sidecar(path, inputs)
    return {
        "artifact": str(path),
        "provenance_sidecar": str(sidecar),
        "row_count": len(rows),
    }


# Backward-friendly verb for scripts.
generate_artifacts = make_paper_artifacts


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="aggregate JSON or raw artifact root")
    parser.add_argument("--derived-dir", type=Path, default=DEFAULT_DERIVED_DIR)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE_PATH)
    parser.add_argument("--figure-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--output-stem", default="paper_results")
    parser.add_argument(
        "--nonprimary",
        action="store_true",
        help="allow explicitly labeled development outputs from smoke/incomplete data",
    )
    args = parser.parse_args(argv)
    result = make_paper_artifacts(
        args.source,
        derived_dir=args.derived_dir,
        table_path=args.table,
        figure_dir=args.figure_dir,
        primary=not args.nonprimary,
        output_stem=args.output_stem,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ArtifactError",
    "generate_artifacts",
    "make_paper_artifacts",
    "validate_primary_aggregate",
]
