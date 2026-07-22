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
DIMENSION = 2048
RANKS = (4, 8, 16)
METHODS = (
    "exact_current",
    "full_cg",
    "window_q_1_2",
    "window_q_2_3",
    "window_q_1",
    "diagonal_current",
    "greedy",
)
METHOD_LABELS = {
    "exact_current": "Exact current",
    "full_cg": "Full CG",
    "window_q_1_2": r"Window $q=1/2$",
    "window_q_2_3": r"Window $q=2/3$",
    "window_q_1": r"Window $q=1$",
    "diagonal_current": "Diagonal",
    "greedy": "Greedy",
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
    expected_cells = {
        f"d-{dimension}_r-{rank}_T-2048"
        for dimension in (128, 512, 2048)
        for rank in RANKS
    }
    if set(cells) != expected_cells:
        raise ScalingPaperArtifactError("cell coverage does not match the Cartesian grid")
    for rank in RANKS:
        cell = cells[f"d-{DIMENSION}_r-{rank}_T-2048"]
        if not isinstance(cell, Mapping):
            raise ScalingPaperArtifactError(f"rank-{rank} cell is malformed")
        for method in METHODS:
            for horizon in horizons:
                stats = cell["estimates"][method][str(horizon)]["regret"]["mean_interval"]
                mean = _number(stats.get("sample_mean"), f"{rank}/{method}/{horizon}.mean")
                lower = _number(stats.get("lower_95"), f"{rank}/{method}/{horizon}.lower")
                upper = _number(stats.get("upper_95"), f"{rank}/{method}/{horizon}.upper")
                if mean <= 0.0 or not lower <= mean <= upper:
                    raise ScalingPaperArtifactError("regret interval is invalid for log plotting")
    return horizons, cells


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
        "diagonal_current": "#CC79A7",
        "greedy": "#555555",
    }
    markers = ("o", "s", "^", "v", "D", "P", "X")
    fig, axes = plt.subplots(1, 3, figsize=(7.15, 2.25), sharex=True)
    x = np.asarray(horizons, dtype=np.float64)
    for axis, rank in zip(axes, RANKS, strict=True):
        cell = cells[f"d-{DIMENSION}_r-{rank}_T-2048"]
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
                markersize=2.8,
                linewidth=1.0,
                label=METHOD_LABELS[method],
            )
            axis.fill_between(x, lows, highs, color=colors[method], alpha=0.10, linewidth=0)
        axis.set_xscale("log", base=2)
        axis.set_yscale("log")
        axis.set_title(rf"Active rank $r={rank}$", fontsize=8.5)
        axis.set_xlabel(r"Horizon $T$", fontsize=8)
        axis.grid(color="#D8D8D8", linewidth=0.45, which="both")
        axis.spines[["top", "right"]].set_visible(False)
        axis.tick_params(labelsize=7)
    axes[0].set_ylabel("Mean cumulative regret", fontsize=8)
    handles, labels = axes[-1].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        ncol=4,
        frameon=False,
        fontsize=6.5,
        bbox_to_anchor=(0.5, 1.03),
    )
    fig.subplots_adjust(left=0.075, right=0.995, bottom=0.20, top=0.78, wspace=0.22)
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
    return f"{value[0]:.3f} [{value[1]:.3f},{value[2]:.3f}]"


def _make_table(cells: Mapping[str, Any], output: Path) -> None:
    lines = [
        "% Auto-generated by experiments.make_theory_scaling_paper_artifacts; do not edit.",
        r"\begingroup",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{2.8pt}",
        r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}crrrrrr@{}}",
        r"\toprule",
        r"$r$ & Exact $R_{2048}$ & Exact regret slope & Exact $\Lambda$ slope & $q=1/2$ regret slope & $q=2/3$ regret slope & Audit fail. \\",
        r"\midrule",
    ]
    for rank in RANKS:
        cell = cells[f"d-{DIMENSION}_r-{rank}_T-2048"]
        regret = cell["estimates"]["exact_current"]["2048"]["regret"]["mean_interval"]
        mean = _number(regret["sample_mean"], "table regret mean")
        lower = _number(regret["lower_95"], "table regret lower")
        upper = _number(regret["upper_95"], "table regret upper")
        audit_failures = sum(
            int(value)
            for method in (
                "exact_current",
                "full_cg",
                "window_q_1_2",
                "window_q_2_3",
                "window_q_1",
            )
            for value in cell["theorem_event_failure_counts_float64_audit"][method].values()
        )
        lines.append(
            f"{rank} & {mean:.2f} [{lower:.2f},{upper:.2f}] & "
            f"{_format_slope(_slope(cell, 'exact_current', 'regret'))} & "
            f"{_format_slope(_slope(cell, 'exact_current', 'Lambda'))} & "
            f"{_format_slope(_slope(cell, 'window_q_1_2', 'regret'))} & "
            f"{_format_slope(_slope(cell, 'window_q_2_3', 'regret'))} & "
            f"{audit_failures} " + r"\\"
        )
    lines.extend((r"\bottomrule", r"\end{tabular*}", r"\endgroup", ""))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="ascii")


def generate_theory_scaling_paper_artifacts(
    *,
    source: str | Path = DEFAULT_SOURCE,
    figure: str | Path = DEFAULT_FIGURE,
    table: str | Path = DEFAULT_TABLE,
) -> dict[str, Any]:
    source_path = Path(source)
    figure_path = Path(figure)
    table_path = Path(table)
    report, source_sidecar = _load_validated(source_path)
    horizons, cells = _validate_source(report)
    _make_figure(horizons, cells, figure_path)
    _make_table(cells, table_path)
    direct_inputs = (source_path, source_sidecar)
    figure_sidecar = _write_provenance(
        figure_path,
        direct_inputs,
        {
            "ambient_dimension": DIMENSION,
            "active_ranks": list(RANKS),
            "methods": list(METHODS),
            "horizons": list(horizons),
            "uncertainty": "paired-seed bootstrap 95 percent intervals",
            "interpretation": "finite-horizon diagnostic, not a proof",
        },
    )
    table_sidecar = _write_provenance(
        table_path,
        direct_inputs,
        {
            "ambient_dimension": DIMENSION,
            "active_ranks": list(RANKS),
            "bootstrap_replicates": 2000,
            "interpretation": "finite-horizon diagnostic, not a proof",
        },
    )
    return {
        "schema_version": 1,
        "source": {"path": str(source_path), "sha256": _sha256(source_path)},
        "artifacts": [str(figure_path), str(table_path)],
        "provenance_sidecars": [str(figure_sidecar), str(table_sidecar)],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--figure", type=Path, default=DEFAULT_FIGURE)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    args = parser.parse_args(argv)
    print(
        canonical_json(
            generate_theory_scaling_paper_artifacts(
                source=args.source, figure=args.figure, table=args.table
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
