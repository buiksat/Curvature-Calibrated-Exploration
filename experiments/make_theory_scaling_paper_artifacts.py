"""Generate provenance-bound paper artifacts from the validated scaling grid."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from .logging_utils import canonical_json


DEFAULT_SOURCE = Path("results/derived/theory_scaling_full_grid.json")
DEFAULT_FIGURE = Path("paper/figures/theory_scaling_full_grid.pdf")
DEFAULT_TABLE = Path("paper/tables/theory_scaling_full_grid.tex")
DEFAULT_SLOPES_TABLE = Path("paper/tables/theory_scaling_slopes.tex")
DIMENSION = 2048
RANKS = (4, 8, 16)
PANEL_CELLS = ((128, 4), (2048, 4), (2048, 8), (2048, 16))
METHODS = (
    "exact_current",
    "full_cg",
    "window_q_1_2",
    "window_q_2_3",
    "window_q_1",
    "frozen",
    "diagonal_current",
    "greedy",
)
THEOREM_METHODS = (
    "exact_current",
    "full_cg",
    "window_q_1_2",
    "window_q_2_3",
    "window_q_1",
)
METHOD_LABELS = {
    "exact_current": "Exact current",
    "full_cg": "Full CG",
    "window_q_1_2": r"Window $q=1/2$",
    "window_q_2_3": r"Window $q=2/3$",
    "window_q_1": r"Window $q=1$",
    "frozen": "Frozen",
    "diagonal_current": "Diagonal",
    "greedy": "Greedy",
}
PLAIN_METHOD_LABELS = {
    "exact_current": "Exact",
    "full_cg": "Full CG",
    "window_q_1_2": "Window 1/2",
    "window_q_2_3": "Window 2/3",
    "window_q_1": "Window 1",
    "frozen": "Frozen",
    "diagonal_current": "Diagonal",
    "greedy": "Greedy",
}
EVENT_LABELS = {
    "optimizer_residual": r"$O$",
    "psi_excitation": r"$P_e$",
    "psi_lambda": r"$P_\lambda$",
    "rank_information": "rank-info",
    "chi_lambda": r"$\chi_\lambda$",
    "chi_excitation": r"$\chi_E$",
    "linearization": "linearization",
    "F": r"$F$",
    "dynamic_width": "dyn.-width",
    "cg": "CG",
}


class ScalingPaperArtifactError(ValueError):
    """Raised when the aggregate cannot support the requested artifacts."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScalingPaperArtifactError(f"{label} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ScalingPaperArtifactError(f"{label} is not finite")
    return result


def _load_validated(path: Path) -> tuple[dict[str, Any], Path]:
    sidecar = path.with_name(path.name + ".sha256")
    try:
        tokens = sidecar.read_text(encoding="ascii").strip().split()
    except OSError as error:
        raise ScalingPaperArtifactError(f"missing aggregate sidecar: {error}") from error
    if len(tokens) != 2 or tokens[1] != path.name or tokens[0] != _sha256(path):
        raise ScalingPaperArtifactError("scaling aggregate hash validation failed")
    try:
        report = json.loads(path.read_text(encoding="ascii"))
    except (OSError, json.JSONDecodeError) as error:
        raise ScalingPaperArtifactError(f"cannot parse scaling aggregate: {error}") from error
    if not isinstance(report, dict):
        raise ScalingPaperArtifactError("scaling aggregate must be an object")
    return report, sidecar


def _validate_source(report: Mapping[str, Any]) -> tuple[list[int], Mapping[str, Any]]:
    coverage = report.get("coverage")
    protocol = report.get("protocol")
    cells = report.get("cells")
    if (
        report.get("schema_version") != 1
        or report.get("experiment") != "theory_scaling_full_grid_aggregate"
        or not isinstance(coverage, Mapping)
        or coverage.get("exact") is not True
        or coverage.get("validated_cells") != 9
        or coverage.get("validated_runs") != 3600
        or not isinstance(protocol, Mapping)
        or not isinstance(cells, Mapping)
    ):
        raise ScalingPaperArtifactError("source is not the complete full-grid aggregate")
    horizons_value = protocol.get("checkpoints")
    if not isinstance(horizons_value, Sequence) or isinstance(horizons_value, (str, bytes)):
        raise ScalingPaperArtifactError("checkpoint horizons are malformed")
    horizons = [int(value) for value in horizons_value]
    if horizons != [128, 256, 512, 1024, 2048]:
        raise ScalingPaperArtifactError("checkpoint horizons do not match the protocol")
    if protocol.get("methods") != list(METHODS):
        raise ScalingPaperArtifactError("aggregate methods do not match the paper protocol")
    expected_cells = {
        f"d-{dimension}_r-{rank}_T-2048"
        for dimension in (128, 512, 2048)
        for rank in RANKS
    }
    if set(cells) != expected_cells:
        raise ScalingPaperArtifactError("cell coverage does not match the Cartesian grid")
    for dimension, rank in PANEL_CELLS:
        cell = cells[f"d-{dimension}_r-{rank}_T-2048"]
        if not isinstance(cell, Mapping):
            raise ScalingPaperArtifactError(
                f"dimension-{dimension}/rank-{rank} cell is malformed"
            )
        estimates = cell.get("estimates")
        failures = cell.get("theorem_event_failure_counts_float64_audit")
        if not isinstance(estimates, Mapping) or not isinstance(failures, Mapping):
            raise ScalingPaperArtifactError(
                f"dimension-{dimension}/rank-{rank} cell lacks estimates or audits"
            )
        for method in METHODS:
            method_estimates = estimates.get(method)
            method_failures = failures.get(method)
            if not isinstance(method_estimates, Mapping) or not isinstance(
                method_failures, Mapping
            ):
                raise ScalingPaperArtifactError(
                    f"dimension-{dimension}/rank-{rank}/{method} is malformed"
                )
            for event, count in method_failures.items():
                if (
                    event not in EVENT_LABELS
                    or isinstance(count, bool)
                    or not isinstance(count, int)
                    or count < 0
                ):
                    raise ScalingPaperArtifactError(
                        f"invalid audit count for {dimension}/{rank}/{method}/{event}"
                    )
            for horizon in horizons:
                try:
                    stats = method_estimates[str(horizon)]["regret"]["mean_interval"]
                except (KeyError, TypeError) as error:
                    raise ScalingPaperArtifactError(
                        f"missing regret interval for {dimension}/{rank}/{method}/{horizon}"
                    ) from error
                mean = _number(stats.get("sample_mean"), f"{rank}/{method}/{horizon}.mean")
                lower = _number(stats.get("lower_95"), f"{rank}/{method}/{horizon}.lower")
                upper = _number(stats.get("upper_95"), f"{rank}/{method}/{horizon}.upper")
                if mean <= 0.0 or not lower <= mean <= upper:
                    raise ScalingPaperArtifactError("regret interval is invalid for log plotting")
    return horizons, cells


def _failure_items(cell: Mapping[str, Any], method: str) -> list[tuple[str, int]]:
    failures = cell["theorem_event_failure_counts_float64_audit"][method]
    return [
        (event, int(failures.get(event, 0)))
        for event in EVENT_LABELS
        if int(failures.get(event, 0)) > 0
    ]


def _method_status(cell: Mapping[str, Any], method: str) -> str:
    if method == "greedy":
        return "CONTROL"
    return "FAIL" if _failure_items(cell, method) else "PASS"


def _format_method_status(cell: Mapping[str, Any], method: str) -> str:
    status = _method_status(cell, method)
    if method == "greedy":
        return status
    failures = _failure_items(cell, method)
    if not failures:
        return status
    details = ", ".join(f"{EVENT_LABELS[event]}={count}" for event, count in failures)
    return f"{status} [{details}]"


def _panel_status(cell: Mapping[str, Any]) -> tuple[str, str]:
    failed = [
        method for method in THEOREM_METHODS if _method_status(cell, method) == "FAIL"
    ]
    if not failed:
        return f"PASS: {len(THEOREM_METHODS)}/{len(THEOREM_METHODS)} theorem methods", "#176B3A"
    if len(failed) == len(THEOREM_METHODS):
        detail = "all theorem methods"
    else:
        detail = ", ".join(PLAIN_METHOD_LABELS[method] for method in failed)
    return (
        f"FAIL: {len(failed)}/{len(THEOREM_METHODS)} theorem methods\n{detail}",
        "#A12A2A",
    )


def _write_provenance(
    artifact: Path,
    inputs: Sequence[Path],
    generation_parameters: Mapping[str, Any],
) -> Path:
    normalized = sorted(
        ({"path": str(path), "sha256": _sha256(path)} for path in inputs),
        key=lambda item: item["path"],
    )
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
        encoding="ascii",
    )
    return sidecar


def _make_figure(
    horizons: Sequence[int], cells: Mapping[str, Any], output: Path
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    matplotlib.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})
    import matplotlib.pyplot as plt

    colors = {
        "exact_current": "#0072B2",
        "full_cg": "#009E73",
        "window_q_1_2": "#D55E00",
        "window_q_2_3": "#E69F00",
        "window_q_1": "#56B4E9",
        "frozen": "#882255",
        "diagonal_current": "#CC79A7",
        "greedy": "#555555",
    }
    markers = ("o", "s", "^", "v", "D", "h", "P", "X")
    fig, axes_grid = plt.subplots(2, 2, figsize=(7.15, 4.10), sharex=True)
    axes = tuple(axes_grid.flat)
    x = np.asarray(horizons, dtype=np.float64)
    panel_letters = ("a", "b", "c", "d")
    for axis, (dimension, rank), letter in zip(
        axes, PANEL_CELLS, panel_letters, strict=True
    ):
        cell = cells[f"d-{dimension}_r-{rank}_T-2048"]
        for method, marker in zip(METHODS, markers, strict=True):
            records = [
                cell["estimates"][method][str(horizon)]["regret"]["mean_interval"]
                for horizon in horizons
            ]
            means = np.asarray([_number(item["sample_mean"], "mean") for item in records])
            lows = np.asarray([_number(item["lower_95"], "lower") for item in records])
            highs = np.asarray([_number(item["upper_95"], "upper") for item in records])
            axis.plot(
                x,
                means,
                color=colors[method],
                marker=marker,
                markersize=3.0,
                linewidth=1.0,
                label=METHOD_LABELS[method],
            )
            axis.fill_between(x, lows, highs, color=colors[method], alpha=0.10, linewidth=0)
        axis.set_xscale("log", base=2)
        axis.set_yscale("log")
        clean_label = " (clean slice)" if (dimension, rank) == (128, 4) else ""
        axis.set_title(
            rf"({letter}) $d={dimension}$, $r={rank}${clean_label}", fontsize=8.5
        )
        axis.set_xlabel(r"Horizon $T$", fontsize=8)
        axis.grid(color="#D8D8D8", linewidth=0.45, which="both")
        axis.spines[["top", "right"]].set_visible(False)
        axis.tick_params(labelsize=7)
        status, status_color = _panel_status(cell)
        axis.text(
            0.98,
            0.04,
            status,
            transform=axis.transAxes,
            ha="right",
            va="bottom",
            color=status_color,
            fontsize=6.2,
            fontweight="bold",
            bbox={
                "boxstyle": "square,pad=0.22",
                "facecolor": "white",
                "edgecolor": status_color,
                "linewidth": 0.55,
                "alpha": 0.92,
            },
        )
    axes[0].set_ylabel("Mean cumulative regret", fontsize=8)
    axes[2].set_ylabel("Mean cumulative regret", fontsize=8)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        ncol=4,
        frameon=False,
        fontsize=6.7,
        bbox_to_anchor=(0.5, 0.995),
    )
    fig.subplots_adjust(
        left=0.075,
        right=0.995,
        bottom=0.095,
        top=0.875,
        hspace=0.34,
        wspace=0.20,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output,
        metadata={
            "Creator": "experiments.make_theory_scaling_paper_artifacts",
            "Title": "Finite-horizon theorem-scaling diagnostics",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    plt.close(fig)


def _slope(cell: Mapping[str, Any], method: str, metric: str) -> tuple[float, float, float]:
    value = cell["slopes"][method][metric]
    return (
        _number(value["slope"], "slope"),
        _number(value["lower_95"], "slope lower"),
        _number(value["upper_95"], "slope upper"),
    )


def _format_slope(value: tuple[float, float, float]) -> str:
    return f"{value[0]:.3f} [{value[1]:.3f}, {value[2]:.3f}]"


def _terminal_regret(cell: Mapping[str, Any], method: str) -> str:
    regret = cell["estimates"][method]["2048"]["regret"]["mean_interval"]
    mean = _number(regret["sample_mean"], "terminal regret mean")
    return f"{mean:.2f}"


def _make_table(cells: Mapping[str, Any], output: Path) -> None:
    lines = [
        "% Auto-generated by experiments.make_theory_scaling_paper_artifacts; do not edit.",
        r"\begingroup",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{2.0pt}",
        r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lrrrrrrrr@{}}",
        r"\toprule",
        r"Cell $(d/r)$ & Exact & CG & $q=1/2$ & $q=2/3$ & $q=1$ & Frozen & Diag. & Greedy \\",
        r"\midrule",
    ]
    for dimension, rank in PANEL_CELLS:
        cell = cells[f"d-{dimension}_r-{rank}_T-2048"]
        regrets = [_terminal_regret(cell, method) for method in METHODS]
        lines.append(" & ".join((f"${dimension}/{rank}$", *regrets)) + r" \\")
    lines.extend(
        (
            r"\bottomrule",
            r"\end{tabular*}",
            r"\vspace{3pt}",
            r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lllll@{}}",
            r"\toprule",
            r"& \multicolumn{4}{c}{Theorem-event status and failed round--event categories} \\",
            r"\cmidrule(lr){2-5}",
            r"Method & $d=128,r=4$ & $d=2048,r=4$ & $d=2048,r=8$ & $d=2048,r=16$ \\",
            r"\midrule",
        )
    )
    for method in THEOREM_METHODS:
        statuses = [
            _format_method_status(
                cells[f"d-{dimension}_r-{rank}_T-2048"], method
            )
            for dimension, rank in PANEL_CELLS
        ]
        lines.append(" & ".join((METHOD_LABELS[method], *statuses)) + r" \\")
    lines.extend(
        (
            r"\multicolumn{5}{@{}l@{}}{PASS means that all recorded float64 theorem-event fields passed for that method and cell.} \\",
            r"\multicolumn{5}{@{}l@{}}{Failure counts are round--event fields: $O$ is optimizer residual, $P_e$ is $\psi$-excitation, and $P_\lambda$ is $\psi$-lambda.} \\",
            r"\bottomrule",
            r"\end{tabular*}",
            r"\endgroup",
            "",
        )
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="ascii")


def _loglog_diagnostics(
    cell: Mapping[str, Any], method: str, horizons: Sequence[int]
) -> tuple[float, float]:
    x = np.log(np.asarray(horizons, dtype=np.float64))
    means = np.asarray(
        [
            _number(
                cell["estimates"][method][str(horizon)]["regret"]["mean_interval"][
                    "sample_mean"
                ],
                f"{method}/{horizon}.regret mean",
            )
            for horizon in horizons
        ],
        dtype=np.float64,
    )
    y = np.log(means)
    slope, intercept = np.polyfit(x, y, 1)
    stored_slope = _slope(cell, method, "regret")[0]
    if not math.isclose(
        float(slope), stored_slope, rel_tol=1.0e-10, abs_tol=1.0e-12
    ):
        raise ScalingPaperArtifactError(
            f"stored and recomputed regret slopes disagree for {method}"
        )
    residuals = y - (slope * x + intercept)
    residual_sum = float(residuals @ residuals)
    centered = y - float(np.mean(y))
    total_sum = float(centered @ centered)
    numerical_floor = np.finfo(np.float64).eps * max(1.0, float(y @ y))
    if total_sum <= numerical_floor:
        r_squared = 1.0 if residual_sum <= numerical_floor else 0.0
    else:
        r_squared = 1.0 - residual_sum / total_sum
    return float(r_squared), float(np.max(np.abs(residuals)))


def _make_slopes_table(
    horizons: Sequence[int], cells: Mapping[str, Any], output: Path
) -> None:
    lines = [
        "% Auto-generated by experiments.make_theory_scaling_paper_artifacts; do not edit.",
        r"\begingroup",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{2.8pt}",
        r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}rlrrrr@{}}",
        r"\toprule",
        r"$r$ & Method & Regret slope [95\% interval] & $R^2$ & Max. $|\log R-\widehat{\log R}|$ & $\Lambda$ slope [95\% interval] \\",
        r"\midrule",
    ]
    for rank_index, rank in enumerate(RANKS):
        if rank_index:
            lines.append(r"\midrule")
        cell = cells[f"d-{DIMENSION}_r-{rank}_T-2048"]
        for method in METHODS:
            r_squared, max_log_residual = _loglog_diagnostics(
                cell, method, horizons
            )
            lines.append(
                f"{rank} & {METHOD_LABELS[method]} & "
                f"{_format_slope(_slope(cell, method, 'regret'))} & "
                f"{r_squared:.4f} & {max_log_residual:.3e} & "
                f"{_format_slope(_slope(cell, method, 'Lambda'))} " + r"\\"
            )
    lines.extend(
        (
            r"\bottomrule",
            r"\end{tabular*}",
            r"\endgroup",
            "",
        )
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="ascii")


def generate_theory_scaling_paper_artifacts(
    *,
    source: str | Path = DEFAULT_SOURCE,
    figure: str | Path = DEFAULT_FIGURE,
    table: str | Path = DEFAULT_TABLE,
    slopes_table: str | Path = DEFAULT_SLOPES_TABLE,
) -> dict[str, Any]:
    source_path = Path(source)
    figure_path = Path(figure)
    table_path = Path(table)
    slopes_table_path = Path(slopes_table)
    report, source_sidecar = _load_validated(source_path)
    horizons, cells = _validate_source(report)
    _make_figure(horizons, cells, figure_path)
    _make_table(cells, table_path)
    _make_slopes_table(horizons, cells, slopes_table_path)
    direct_inputs = (source_path, source_sidecar)
    figure_sidecar = _write_provenance(
        figure_path,
        direct_inputs,
        {
            "panels": [
                {"ambient_dimension": dimension, "active_rank": rank}
                for dimension, rank in PANEL_CELLS
            ],
            "methods": list(METHODS),
            "horizons": list(horizons),
            "uncertainty": "pointwise percentile-bootstrap 95 percent intervals",
            "status": (
                "PASS iff all recorded float64 theorem-event failure counts are "
                "zero for the five theorem methods shown in the status matrix"
            ),
            "interpretation": "finite-horizon diagnostic, not a proof",
        },
    )
    table_sidecar = _write_provenance(
        table_path,
        direct_inputs,
        {
            "panels": [
                {"ambient_dimension": dimension, "active_rank": rank}
                for dimension, rank in PANEL_CELLS
            ],
            "methods": list(METHODS),
            "bootstrap_replicates": 2000,
            "uncertainty": "pointwise percentile-bootstrap 95 percent intervals",
            "contents": (
                "all-method terminal regret means and per-method theorem-event "
                "status with failure categories and counts"
            ),
            "interpretation": "finite-horizon diagnostic, not a proof",
        },
    )
    slopes_sidecar = _write_provenance(
        slopes_table_path,
        direct_inputs,
        {
            "ambient_dimension": DIMENSION,
            "active_ranks": list(RANKS),
            "methods": list(METHODS),
            "horizons": list(horizons),
            "regression": "unweighted OLS of log(seed-mean metric) on log(horizon)",
            "uncertainty": (
                "percentile intervals from paired whole-seed resampling across "
                "the five horizon prefixes"
            ),
            "diagnostics": [
                "R-squared",
                "maximum absolute log-space residual",
            ],
            "interpretation": "five-point finite-horizon diagnostic, not a proof",
        },
    )
    return {
        "schema_version": 1,
        "source": {"path": str(source_path), "sha256": _sha256(source_path)},
        "artifacts": [
            str(figure_path),
            str(table_path),
            str(slopes_table_path),
        ],
        "provenance_sidecars": [
            str(figure_sidecar),
            str(table_sidecar),
            str(slopes_sidecar),
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--figure", type=Path, default=DEFAULT_FIGURE)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--slopes-table", type=Path, default=DEFAULT_SLOPES_TABLE)
    args = parser.parse_args(argv)
    print(
        canonical_json(
            generate_theory_scaling_paper_artifacts(
                source=args.source,
                figure=args.figure,
                table=args.table,
                slopes_table=args.slopes_table,
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ScalingPaperArtifactError",
    "generate_theory_scaling_paper_artifacts",
    "main",
]
