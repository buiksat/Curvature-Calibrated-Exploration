"""Generate the revision figure and table from validated derived artifacts only."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .aggregate_results import (
    AggregationError,
    validate_aggregate_provenance_sidecar,
)
from .logging_utils import canonical_json


DEFAULT_TANH = Path("results/derived/certified_tanh_report.json")
DEFAULT_BALANCED = Path("results/derived/balanced_benchmark_full.json")
DEFAULT_PHASE = Path("results/derived/curvature_phase_diagram_report.json")
DEFAULT_SYSTEMS = Path("results/derived/systems_scaling_full.json")
DEFAULT_FIGURE_PDF = Path("paper/figures/theory_factor_drift.pdf")
DEFAULT_TABLE = Path("paper/tables/executed_policy_results.tex")

TANH_METRICS = (
    ("final_chi_exact", "final_chi_bar", r"$\chi_T$"),
    ("final_psi_exact", "final_psi_bar", r"$\psi_T$"),
    ("final_F_exact_prior", "final_F_bar_prior", r"$F_{T-1}$"),
    ("final_gamma_exact", "final_gamma_hat", r"$\gamma_T$"),
)
PHASE_METHODS = (
    ("diagonal", "Diagonal"),
    ("block_diagonal", "Block diagonal"),
    ("low_rank_lanczos", "Low-rank"),
    ("unrescaled_window", "Window"),
    ("stale_refresh", "Stale"),
)
BALANCED_METHODS = (
    ("cc_ucb_full_ggn_cg", "CC-UCB (full GGN-CG)"),
    ("diagonal_full_network_ucb", "Diagonal full network"),
    ("linucb", "LinUCB"),
    ("linear_ts", "LinearTS"),
    ("neural_linear", "NeuralLinear"),
    ("neural_ucb", "NeuralUCB"),
    ("neural_ts", "NeuralTS"),
    ("frozen_last_layer_ucb", "Frozen last layer"),
    ("greedy_full_network", "Greedy"),
    ("gaussian_ucb1", "UCB1"),
    ("gaussian_context_free_ts", "Context-free TS"),
)


class RevisionArtifactError(ValueError):
    """Raised when a source cannot support a requested paper artifact."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _number(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise RevisionArtifactError(f"{label} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise RevisionArtifactError(f"{label} is not finite")
    return result


def _stats(value: Any, label: str, *, positive: bool = False) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise RevisionArtifactError(f"{label} is not a statistics record")
    result = {
        name: _number(value.get(name), f"{label}.{name}")
        for name in ("mean", "ci95_low", "ci95_high", "n")
    }
    if result["n"] <= 0 or result["ci95_low"] > result["mean"] or result["mean"] > result["ci95_high"]:
        raise RevisionArtifactError(f"{label} has an invalid interval")
    if positive and result["ci95_low"] <= 0:
        raise RevisionArtifactError(f"{label} must be positive on a log axis")
    return result


def _load_validated(path: Path, label: str) -> tuple[dict[str, Any], Path]:
    sidecar = path.with_suffix(path.suffix + ".provenance.json")
    try:
        validate_aggregate_provenance_sidecar(path, sidecar)
    except AggregationError as error:
        raise RevisionArtifactError(f"{label} provenance validation failed: {error}") from error
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RevisionArtifactError(f"cannot parse {label}: {error}") from error
    if not isinstance(value, dict):
        raise RevisionArtifactError(f"{label} must contain a JSON object")
    return value, sidecar


def _validate_tanh(report: Mapping[str, Any]) -> None:
    if (
        report.get("schema_version") != 1
        or report.get("experiment") != "certified_tanh"
        or report.get("profile") != "full"
        or report.get("seed_set") != "evaluation"
    ):
        raise RevisionArtifactError("tanh source is not the full evaluation report")
    policies = report.get("policies")
    if not isinstance(policies, Mapping):
        raise RevisionArtifactError("tanh report has no policy records")
    for center in ("original", "corrected"):
        policy = policies.get(center)
        if not isinstance(policy, Mapping):
            raise RevisionArtifactError(f"tanh report is missing {center}")
        if policy.get("certification_category") != "posthoc_theorem_event_verified":
            raise RevisionArtifactError(f"unexpected tanh certification category for {center}")
        if policy.get("all_observed_theorem_event_checks_hold") is not True:
            raise RevisionArtifactError(f"observed tanh theorem event failed for {center}")
        metrics = policy.get("metrics")
        if not isinstance(metrics, Mapping):
            raise RevisionArtifactError(f"tanh metrics are missing for {center}")
        for exact, bound, _ in TANH_METRICS:
            _stats(metrics.get(exact), f"tanh.{center}.{exact}", positive=True)
            _stats(metrics.get(bound), f"tanh.{center}.{bound}", positive=True)
        _stats(metrics.get("cumulative_pseudo_regret"), f"tanh.{center}.regret")
        _stats(metrics.get("runtime_seconds"), f"tanh.{center}.runtime")
        _number(policy.get("certificate_failure_count"), f"tanh.{center}.failures")


def _validate_balanced(report: Mapping[str, Any]) -> None:
    if (
        report.get("schema_version") != 1
        or report.get("event") != "balanced_contextual_benchmark_report"
        or report.get("experiment") != "balanced_benchmark"
        or report.get("profile") != "full"
        or report.get("seed_set") != "evaluation"
        or report.get("tuning_evaluation_seeds_disjoint") is not True
    ):
        raise RevisionArtifactError("balanced source is not the disjoint full evaluation report")
    selection_hash = report.get("selection_artifact_sha256")
    if not isinstance(selection_hash, str) or len(selection_hash) != 64:
        raise RevisionArtifactError("balanced report lacks validation-selection provenance")
    methods = report.get("method_results")
    if not isinstance(methods, Mapping):
        raise RevisionArtifactError("balanced report has no method results")
    for method, _ in BALANCED_METHODS:
        record = methods.get(method)
        if not isinstance(record, Mapping):
            raise RevisionArtifactError(f"balanced report is missing {method}")
        if not isinstance(record.get("selected_hyperparameters"), Mapping):
            raise RevisionArtifactError(f"{method} lacks selected hyperparameters")
        if record.get("published_implementation_claim") is not False:
            raise RevisionArtifactError(f"{method} has an unsupported implementation claim")
        metrics = record.get("metrics")
        if not isinstance(metrics, Mapping):
            raise RevisionArtifactError(f"{method} lacks full-run metrics")
        _stats(metrics.get("cumulative_pseudo_regret"), f"balanced.{method}.regret")
        _stats(metrics.get("runtime_seconds"), f"balanced.{method}.runtime")


def _phase_matrix(report: Mapping[str, Any]) -> tuple[list[str], list[list[float]], bool]:
    if report.get("schema_version") != 1 or report.get("study") != "curvature_mechanism_phase_diagram":
        raise RevisionArtifactError("phase source is not the curvature mechanism report")
    grid = report.get("preregistered_grid")
    if not isinstance(grid, Mapping) or grid.get("cell_count") != 8 or grid.get("phase") != "evaluation":
        raise RevisionArtifactError("phase report lacks the preregistered eight-cell evaluation grid")
    cells_value = grid.get("cells")
    if not isinstance(cells_value, Sequence) or isinstance(cells_value, (str, bytes)):
        raise RevisionArtifactError("phase grid cells are malformed")
    cell_ids = [str(cell.get("cell_id")) for cell in cells_value if isinstance(cell, Mapping)]
    if len(cell_ids) != 8 or len(set(cell_ids)) != 8:
        raise RevisionArtifactError("phase grid does not contain eight unique cells")
    comparisons = report.get("paired_full_comparisons")
    if not isinstance(comparisons, Sequence) or isinstance(comparisons, (str, bytes)):
        raise RevisionArtifactError("phase report lacks paired comparisons")
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    for item in comparisons:
        if not isinstance(item, Mapping):
            continue
        key = (str(item.get("cell_id")), str(item.get("method")))
        if key in indexed:
            raise RevisionArtifactError(f"duplicate phase comparison {key}")
        indexed[key] = item

    matrix: list[list[float]] = []
    for method, _ in PHASE_METHODS:
        row: list[float] = []
        for cell_id in cell_ids:
            item = indexed.get((cell_id, method))
            if not isinstance(item, Mapping):
                raise RevisionArtifactError(f"missing phase comparison for {cell_id}/{method}")
            if (
                item.get("difference") != "method_minus_full_cumulative_pseudo_regret"
                or item.get("reference_method") != "exact_full"
                or item.get("posthoc_cell_or_method_selection") is not False
            ):
                raise RevisionArtifactError(f"unsafe phase comparison for {cell_id}/{method}")
            row.append(_stats(item.get("paired_interval"), f"phase.{cell_id}.{method}")["mean"])
        matrix.append(row)

    full_cg_identical = True
    for cell_id in cell_ids:
        item = indexed.get((cell_id, "full_cg"))
        if not isinstance(item, Mapping):
            full_cg_identical = False
            break
        interval = _stats(item.get("paired_interval"), f"phase.{cell_id}.full_cg")
        full_cg_identical = full_cg_identical and all(
            interval[key] == 0.0 for key in ("mean", "ci95_low", "ci95_high")
        )
    return cell_ids, matrix, full_cg_identical


def _validate_systems(report: Mapping[str, Any]) -> None:
    if (
        report.get("schema_version") != 1
        or report.get("event") != "diagnostic_aggregate"
        or report.get("experiments") != ["systems_scaling"]
        or report.get("profiles") != ["full"]
        or report.get("seed_sets") != ["evaluation"]
        or report.get("all_groups_complete") is not True
    ):
        raise RevisionArtifactError("systems source is not the complete full evaluation diagnostic")
    if _number(report.get("benchmark_diagnostic_group_count"), "systems.group_count") <= 0:
        raise RevisionArtifactError("systems report has no benchmark diagnostics")


def _source_inputs(paths: Sequence[tuple[Path, Path]]) -> list[dict[str, str]]:
    values = [
        {"path": str(path), "sha256": _sha256(path)}
        for pair in paths
        for path in pair
    ]
    return sorted(values, key=lambda item: item["path"])


def _write_provenance(
    artifact: Path,
    inputs: Sequence[Mapping[str, str]],
    generation_parameters: Mapping[str, Any],
) -> Path:
    normalized = [
        {"path": str(item["path"]), "sha256": str(item["sha256"])}
        for item in sorted(inputs, key=lambda item: str(item["path"]))
    ]
    sidecar = artifact.with_suffix(artifact.suffix + ".provenance.json")
    record = {
        "schema_version": 1,
        "artifact": str(artifact),
        "artifact_sha256": _sha256(artifact),
        "input_set_sha256": hashlib.sha256(
            canonical_json(normalized).encode("ascii")
        ).hexdigest(),
        "inputs": normalized,
        "generation_parameters": dict(generation_parameters),
    }
    sidecar.write_text(
        json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return sidecar


def _make_figure(
    tanh: Mapping[str, Any],
    phase: Mapping[str, Any],
    pdf_path: Path,
    png_path: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    matplotlib.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import TwoSlopeNorm
    from matplotlib.lines import Line2D

    cell_ids, matrix_values, full_cg_identical = _phase_matrix(phase)
    matrix = np.asarray(matrix_values, dtype=np.float64)

    fig, (cert_axis, phase_axis) = plt.subplots(
        1,
        2,
        figsize=(7.15, 3.25),
        gridspec_kw={"width_ratios": (1.05, 1.42)},
        constrained_layout=True,
    )
    centers = (("original", "#0072B2", -0.12), ("corrected", "#D55E00", 0.12))
    x = np.arange(len(TANH_METRICS), dtype=np.float64)
    for center, color, offset in centers:
        metrics = tanh["policies"][center]["metrics"]
        for kind, index, marker, linestyle in (
            ("exact", 0, "o", "-"),
            ("predictable", 1, "^", "--"),
        ):
            points = []
            lows = []
            highs = []
            for exact_name, bound_name, _ in TANH_METRICS:
                values = _stats(
                    metrics[(exact_name, bound_name)[index]],
                    f"tanh.{center}.{(exact_name, bound_name)[index]}",
                    positive=True,
                )
                points.append(values["mean"])
                lows.append(values["ci95_low"])
                highs.append(values["ci95_high"])
            y = np.asarray(points)
            cert_axis.errorbar(
                x + offset,
                y,
                yerr=np.vstack((y - np.asarray(lows), np.asarray(highs) - y)),
                color=color,
                marker=marker,
                linestyle=linestyle,
                linewidth=1.25,
                markersize=4.2,
                capsize=2.0,
            )
    cert_axis.set_yscale("log")
    cert_axis.set_xticks(x, [item[2] for item in TANH_METRICS])
    cert_axis.set_ylabel("Final value (log scale)", fontsize=8.5)
    cert_axis.set_title("(a) Exact vs. predictable certificates", fontsize=9.2)
    cert_axis.grid(axis="y", color="#D7D7D7", linewidth=0.55)
    cert_axis.spines[["top", "right"]].set_visible(False)
    cert_axis.tick_params(labelsize=7.5)
    cert_axis.legend(
        handles=[
            Line2D([0], [0], color="#0072B2", marker="o", label="Original"),
            Line2D([0], [0], color="#D55E00", marker="o", label="Corrected"),
            Line2D([0], [0], color="#444444", marker="o", linestyle="-", label="Exact audit"),
            Line2D([0], [0], color="#444444", marker="^", linestyle="--", label="Predictable"),
        ],
        loc="upper left",
        frameon=False,
        fontsize=6.8,
        ncol=2,
    )

    max_abs = max(1e-12, float(np.max(np.abs(matrix))))
    image = phase_axis.imshow(
        matrix,
        cmap="RdBu_r",
        norm=TwoSlopeNorm(vmin=-max_abs, vcenter=0.0, vmax=max_abs),
        aspect="auto",
    )
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            value = float(matrix[row, column])
            phase_axis.text(
                column,
                row,
                f"{value:.2f}",
                ha="center",
                va="center",
                fontsize=5.8,
                color="white" if abs(value) > 0.54 * max_abs else "#171717",
            )
    phase_axis.set_xticks(
        range(len(cell_ids)),
        [cell.removeprefix("ffd_") for cell in cell_ids],
    )
    phase_axis.set_yticks(range(len(PHASE_METHODS)), [label for _, label in PHASE_METHODS])
    phase_axis.set_xlabel("Preregistered cell (condition/rotation/gap code)", fontsize=7.5)
    phase_axis.set_title("(b) Paired method-minus-full regret", fontsize=9.2)
    phase_axis.tick_params(labelsize=6.8, length=0)
    colorbar = fig.colorbar(image, ax=phase_axis, fraction=0.045, pad=0.025)
    colorbar.set_label(r"$\Delta$ cumulative regret", fontsize=7.5)
    colorbar.ax.tick_params(labelsize=6.5)
    if full_cg_identical:
        phase_axis.text(
            0.0,
            -0.19,
            "Full-CG minus exact full: 0 in all eight cells.",
            transform=phase_axis.transAxes,
            fontsize=6.6,
            ha="left",
            va="top",
        )

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        pdf_path,
        bbox_inches="tight",
        metadata={
            "Creator": "experiments.make_revision_paper_artifacts",
            "Title": "Certificate looseness and curvature mechanism phase map",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    fig.savefig(
        png_path,
        dpi=240,
        bbox_inches="tight",
        metadata={"Software": "experiments.make_revision_paper_artifacts"},
    )
    plt.close(fig)


def _estimate(stats: Mapping[str, Any], digits: int = 2) -> str:
    values = _stats(stats, "table estimate")
    return (
        f"{values['mean']:.{digits}f} "
        f"[{values['ci95_low']:.{digits}f}, {values['ci95_high']:.{digits}f}]"
    )


def _make_table(tanh: Mapping[str, Any], balanced: Mapping[str, Any], path: Path) -> None:
    rows: list[tuple[str, str, str, str, str, str]] = []
    for center, label in (("original", "Original center"), ("corrected", "Corrected center")):
        policy = tanh["policies"][center]
        metrics = policy["metrics"]
        runtime = _stats(metrics["runtime_seconds"], f"tanh.{center}.runtime")["mean"]
        failures = int(_number(policy["certificate_failure_count"], f"tanh.{center}.failures"))
        rows.append(
            (
                "Tanh fixed",
                label,
                _estimate(metrics["cumulative_pseudo_regret"]),
                f"{runtime:.3f}",
                f"{failures}/{int(policy['run_count'])}",
                "Post-hoc verified",
            )
        )
    method_results = balanced["method_results"]
    for method, label in BALANCED_METHODS:
        record = method_results[method]
        metrics = record["metrics"]
        runtime = _stats(metrics["runtime_seconds"], f"balanced.{method}.runtime")["mean"]
        rows.append(
            (
                "Balanced tuned",
                label,
                _estimate(metrics["cumulative_pseudo_regret"]),
                f"{runtime:.3f}",
                "--",
                "Uncertified",
            )
        )

    lines = [
        "% Auto-generated by experiments.make_revision_paper_artifacts; do not edit.",
        r"\begingroup",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{2.4pt}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}llrrrl@{}}",
        r"\toprule",
        r"Study & Policy & Regret [95\% CI] & Time (s) & Event fail. & Status \\",
        r"\midrule",
    ]
    for index, row in enumerate(rows):
        if index == 2:
            lines.append(r"\midrule")
        lines.append(" & ".join(row) + r" \\")
    lines.extend((r"\bottomrule", r"\end{tabular*}", r"\endgroup", ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="ascii")


def generate_revision_artifacts(
    *,
    tanh_path: str | Path = DEFAULT_TANH,
    balanced_path: str | Path = DEFAULT_BALANCED,
    phase_path: str | Path = DEFAULT_PHASE,
    systems_path: str | Path = DEFAULT_SYSTEMS,
    figure_pdf: str | Path = DEFAULT_FIGURE_PDF,
    table_path: str | Path = DEFAULT_TABLE,
) -> dict[str, Any]:
    """Validate all revision sources, then write the requested figure and table."""

    tanh_path = Path(tanh_path)
    balanced_path = Path(balanced_path)
    phase_path = Path(phase_path)
    systems_path = Path(systems_path)
    pdf_path = Path(figure_pdf)
    png_path = pdf_path.with_suffix(".png")
    table_path = Path(table_path)

    tanh, tanh_sidecar = _load_validated(tanh_path, "certified tanh report")
    balanced, balanced_sidecar = _load_validated(balanced_path, "balanced benchmark report")
    phase, phase_sidecar = _load_validated(phase_path, "curvature phase report")
    systems, systems_sidecar = _load_validated(systems_path, "systems scaling report")
    _validate_tanh(tanh)
    _validate_balanced(balanced)
    _phase_matrix(phase)
    _validate_systems(systems)

    _make_figure(tanh, phase, pdf_path, png_path)
    _make_table(tanh, balanced, table_path)

    figure_inputs = _source_inputs(((tanh_path, tanh_sidecar), (phase_path, phase_sidecar)))
    table_inputs = _source_inputs(((tanh_path, tanh_sidecar), (balanced_path, balanced_sidecar)))
    figure_parameters = {
        "tanh_metric_pairs": [[exact, bound] for exact, bound, _ in TANH_METRICS],
        "phase_difference": "method_minus_full_cumulative_pseudo_regret",
        "phase_methods": [method for method, _ in PHASE_METHODS],
        "log_axis_numerical_floor": None,
    }
    table_parameters = {
        "balanced_configuration": "validation_tuned_on_disjoint_tuning_seeds",
        "balanced_methods": [method for method, _ in BALANCED_METHODS],
        "regret_interval": "mean_and_two_sided_95_percent_student_t_interval",
        "runtime_definition": "seconds_per_complete_run",
        "tanh_configuration": "fixed_schedule_evaluation",
    }
    sidecars = [
        _write_provenance(pdf_path, figure_inputs, figure_parameters),
        _write_provenance(png_path, figure_inputs, figure_parameters),
        _write_provenance(table_path, table_inputs, table_parameters),
    ]
    validated_sources = [
        {"path": str(path), "sha256": _sha256(path)}
        for path in (tanh_path, balanced_path, phase_path, systems_path)
    ]
    return {
        "schema_version": 1,
        "artifacts": [str(pdf_path), str(png_path), str(table_path)],
        "provenance_sidecars": [str(path) for path in sidecars],
        "validated_sources": validated_sources,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tanh", type=Path, default=DEFAULT_TANH)
    parser.add_argument("--balanced", type=Path, default=DEFAULT_BALANCED)
    parser.add_argument("--phase", type=Path, default=DEFAULT_PHASE)
    parser.add_argument("--systems", type=Path, default=DEFAULT_SYSTEMS)
    parser.add_argument("--figure-pdf", type=Path, default=DEFAULT_FIGURE_PDF)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    args = parser.parse_args(argv)
    result = generate_revision_artifacts(
        tanh_path=args.tanh,
        balanced_path=args.balanced,
        phase_path=args.phase,
        systems_path=args.systems,
        figure_pdf=args.figure_pdf,
        table_path=args.table,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BALANCED_METHODS",
    "PHASE_METHODS",
    "RevisionArtifactError",
    "TANH_METRICS",
    "generate_revision_artifacts",
]
