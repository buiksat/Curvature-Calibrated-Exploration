"""Generate paper artifacts for the off-diagonal linear-Gram witness.

The generator consumes only the validated derived artifact.  It never reads a
trajectory opportunistically or recomputes a reported result from paper text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .aggregate_results import AggregationError, validate_aggregate_provenance_sidecar
from .logging_utils import canonical_json


DEFAULT_SOURCE = Path("results/derived/offdiagonal_witness.json")
DEFAULT_FIGURE = Path("paper/figures/offdiagonal_witness.pdf")
DEFAULT_TABLE = Path("paper/tables/offdiagonal_witness.tex")

METHOD_LABELS = {
    "exact_full": "Exact full",
    "full_cg": "Residual-checked full CG",
    "diagonal_raw": "Diagonal (raw)",
    "diagonal_uniform_transfer": "Diagonal (uniform transfer)",
    "diagonal_actionwise_reference": "Diagonal (actionwise reference)",
    "greedy": "Greedy",
}
TABLE_METHODS = tuple(METHOD_LABELS)
PAIRED_COMPARISONS = (
    ("diagonal_raw_minus_exact_full", "Diagonal (raw)"),
    (
        "diagonal_uniform_transfer_minus_exact_full",
        "Diagonal (uniform transfer)",
    ),
)


class WitnessPaperArtifactError(ValueError):
    """Raised when the source cannot support the requested paper artifacts."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WitnessPaperArtifactError(f"{label} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise WitnessPaperArtifactError(f"{label} is not finite")
    return result


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise WitnessPaperArtifactError(f"{label} is not an integer >= {minimum}")
    return value


def _stats(value: Any, label: str, *, positive: bool = False) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise WitnessPaperArtifactError(f"{label} is not a statistics record")
    result = {
        field: _number(value.get(field), f"{label}.{field}")
        for field in ("mean", "ci95_low", "ci95_high", "n")
    }
    if (
        result["n"] <= 0
        or not result["n"].is_integer()
        or result["ci95_low"] > result["mean"]
        or result["mean"] > result["ci95_high"]
    ):
        raise WitnessPaperArtifactError(f"{label} has an invalid interval")
    if positive and result["ci95_low"] <= 0.0:
        raise WitnessPaperArtifactError(f"{label} must be positive on a log axis")
    return result


def _load_validated(path: Path) -> tuple[dict[str, Any], Path]:
    sidecar = path.with_suffix(path.suffix + ".provenance.json")
    try:
        validate_aggregate_provenance_sidecar(path, sidecar)
    except AggregationError as error:
        raise WitnessPaperArtifactError(
            f"off-diagonal witness provenance validation failed: {error}"
        ) from error
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WitnessPaperArtifactError(f"cannot parse {path}: {error}") from error
    if not isinstance(value, dict):
        raise WitnessPaperArtifactError("off-diagonal witness source is not an object")
    return value, sidecar


def _validate_source(
    report: Mapping[str, Any],
) -> tuple[list[int], dict[tuple[str, str], Mapping[str, Any]], list[str], dict[tuple[str, str], Mapping[str, Any]]]:
    if (
        report.get("schema_version") != 1
        or report.get("experiment") != "offdiagonal_witness"
        or report.get("profile") != "full"
        or report.get("seed_set") != "evaluation"
    ):
        raise WitnessPaperArtifactError("source is not the full evaluation witness")
    if report.get("scope") != (
        "existence witness only; it does not claim uniform full-curvature dominance"
    ):
        raise WitnessPaperArtifactError("source lacks the required witness-only scope")

    checkpoints_value = report.get("checkpoints")
    if not isinstance(checkpoints_value, Sequence) or isinstance(
        checkpoints_value, (str, bytes)
    ):
        raise WitnessPaperArtifactError("checkpoints are malformed")
    checkpoints = [
        _integer(value, f"checkpoints[{index}]", minimum=1)
        for index, value in enumerate(checkpoints_value)
    ]
    if len(checkpoints) < 2 or any(
        right <= left for left, right in zip(checkpoints, checkpoints[1:])
    ):
        raise WitnessPaperArtifactError("checkpoints must be strictly increasing")

    groups_value = report.get("groups")
    if not isinstance(groups_value, Sequence) or isinstance(groups_value, (str, bytes)):
        raise WitnessPaperArtifactError("group records are malformed")
    groups: dict[tuple[str, str], Mapping[str, Any]] = {}
    cells: dict[str, tuple[float, int, str]] = {}
    for index, item in enumerate(groups_value):
        if not isinstance(item, Mapping):
            raise WitnessPaperArtifactError(f"groups[{index}] is malformed")
        cell = str(item.get("cell"))
        method = str(item.get("method"))
        key = (cell, method)
        if key in groups:
            raise WitnessPaperArtifactError(f"duplicate group {cell}/{method}")
        if method not in METHOD_LABELS:
            raise WitnessPaperArtifactError(f"unknown witness method {method}")
        run_count = _integer(item.get("run_count"), f"{cell}/{method}.run_count", minimum=1)
        noise = _number(item.get("noise_std"), f"{cell}/{method}.noise_std")
        classification = str(item.get("classification"))
        identity = (noise, run_count, classification)
        if cell in cells and cells[cell] != identity:
            raise WitnessPaperArtifactError(f"inconsistent cell metadata for {cell}")
        cells[cell] = identity
        expected_classification = (
            "analytic_constructive_witness"
            if noise == 0.0
            else "uncertified_noisy_extension"
        )
        if classification != expected_classification:
            raise WitnessPaperArtifactError(f"unsafe classification for {cell}/{method}")

        horizons = item.get("horizons")
        if not isinstance(horizons, Sequence) or isinstance(horizons, (str, bytes)):
            raise WitnessPaperArtifactError(f"horizons are malformed for {cell}/{method}")
        found_horizons: list[int] = []
        for horizon_index, horizon_item in enumerate(horizons):
            if not isinstance(horizon_item, Mapping):
                raise WitnessPaperArtifactError(f"malformed horizon for {cell}/{method}")
            horizon = _integer(
                horizon_item.get("horizon"),
                f"{cell}/{method}.horizons[{horizon_index}]",
                minimum=1,
            )
            found_horizons.append(horizon)
            stats = _stats(
                horizon_item.get("cumulative_pseudo_regret"),
                f"{cell}/{method}.regret[{horizon}]",
                positive=True,
            )
            if int(stats["n"]) != run_count:
                raise WitnessPaperArtifactError(
                    f"seed count disagrees for {cell}/{method} at {horizon}"
                )
        if found_horizons != checkpoints:
            raise WitnessPaperArtifactError(f"checkpoint coverage differs for {cell}/{method}")

        slope = item.get("log_log_slope")
        if not isinstance(slope, Mapping):
            raise WitnessPaperArtifactError(f"slope is missing for {cell}/{method}")
        _number(slope.get("estimate"), f"{cell}/{method}.slope")
        interval = slope.get("bootstrap_ci95")
        if (
            not isinstance(interval, Sequence)
            or isinstance(interval, (str, bytes))
            or len(interval) != 2
        ):
            raise WitnessPaperArtifactError(f"slope interval is malformed for {cell}/{method}")
        low = _number(interval[0], f"{cell}/{method}.slope_low")
        high = _number(interval[1], f"{cell}/{method}.slope_high")
        if low > high:
            raise WitnessPaperArtifactError(f"slope interval is reversed for {cell}/{method}")
        groups[key] = item

    analytic_cells = [cell for cell, (noise, _, _) in cells.items() if noise == 0.0]
    noisy_cells = [cell for cell, (noise, _, _) in cells.items() if noise > 0.0]
    if analytic_cells != ["analytic"] or not noisy_cells:
        raise WitnessPaperArtifactError("source needs one analytic and at least one noisy cell")
    for cell in cells:
        missing = set(TABLE_METHODS) - {
            method for candidate_cell, method in groups if candidate_cell == cell
        }
        if missing:
            raise WitnessPaperArtifactError(f"{cell} is missing methods {sorted(missing)}")
    deterministic_count = _integer(
        report.get("deterministic_cell_seed_count"),
        "deterministic_cell_seed_count",
        minimum=1,
    )
    noisy_count = _integer(
        report.get("noisy_cell_seed_count"), "noisy_cell_seed_count", minimum=1
    )
    if cells["analytic"][1] != deterministic_count:
        raise WitnessPaperArtifactError("analytic seed count disagrees with source metadata")
    if any(cells[cell][1] != noisy_count for cell in noisy_cells):
        raise WitnessPaperArtifactError("noisy seed count disagrees with source metadata")

    # The combined curve labels below are permitted only when the values agree.
    for left, right in (
        ("exact_full", "full_cg"),
        ("diagonal_raw", "diagonal_uniform_transfer"),
    ):
        left_horizons = groups[("analytic", left)]["horizons"]
        right_horizons = groups[("analytic", right)]["horizons"]
        for horizon_index in range(len(checkpoints)):
            left_mean = _stats(
                left_horizons[horizon_index]["cumulative_pseudo_regret"], "analytic equality"
            )["mean"]
            right_mean = _stats(
                right_horizons[horizon_index]["cumulative_pseudo_regret"], "analytic equality"
            )["mean"]
            if left_mean != right_mean:
                raise WitnessPaperArtifactError(
                    f"analytic curves {left} and {right} cannot be combined"
                )

    paired_value = report.get("paired_final_horizon")
    if not isinstance(paired_value, Sequence) or isinstance(paired_value, (str, bytes)):
        raise WitnessPaperArtifactError("paired final-horizon records are malformed")
    paired: dict[tuple[str, str], Mapping[str, Any]] = {}
    for index, item in enumerate(paired_value):
        if not isinstance(item, Mapping):
            raise WitnessPaperArtifactError(f"paired record {index} is malformed")
        cell = str(item.get("cell"))
        comparison = str(item.get("comparison"))
        key = (cell, comparison)
        if key in paired:
            raise WitnessPaperArtifactError(f"duplicate paired record {key}")
        if item.get("horizon") != checkpoints[-1]:
            raise WitnessPaperArtifactError(f"paired horizon differs for {key}")
        stats = _stats(
            item.get("paired_cumulative_pseudo_regret"),
            f"paired.{cell}.{comparison}",
        )
        if cell not in cells or int(stats["n"]) != cells[cell][1]:
            raise WitnessPaperArtifactError(f"paired seed coverage differs for {key}")
        paired[key] = item
    for cell in noisy_cells:
        for comparison, _ in PAIRED_COMPARISONS:
            if (cell, comparison) not in paired:
                raise WitnessPaperArtifactError(f"missing paired comparison {cell}/{comparison}")

    return checkpoints, groups, noisy_cells, paired


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
        encoding="utf-8",
    )
    return sidecar


def _regret_curve(group: Mapping[str, Any]) -> list[float]:
    return [
        _stats(item["cumulative_pseudo_regret"], "figure regret", positive=True)["mean"]
        for item in group["horizons"]
    ]


def _cell_label(cell: str) -> str:
    return cell.replace("_", " ").title()


def _make_figure(
    checkpoints: Sequence[int],
    groups: Mapping[tuple[str, str], Mapping[str, Any]],
    noisy_cells: Sequence[str],
    paired: Mapping[tuple[str, str], Mapping[str, Any]],
    output: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    matplotlib.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})
    import matplotlib.pyplot as plt
    import numpy as np

    fig, (curve_axis, paired_axis) = plt.subplots(
        1,
        2,
        figsize=(7.1, 2.75),
        gridspec_kw={"width_ratios": (1.0, 1.18)},
        constrained_layout=True,
    )

    curve_axis.plot(
        checkpoints,
        _regret_curve(groups[("analytic", "exact_full")]),
        color="#0072B2",
        marker="o",
        linewidth=1.6,
        markersize=4.2,
        label="Exact full = full CG",
    )
    curve_axis.plot(
        checkpoints,
        _regret_curve(groups[("analytic", "diagonal_raw")]),
        color="#D55E00",
        marker="s",
        linewidth=1.6,
        markersize=4.0,
        label="Raw = uniform-transfer diagonal",
    )
    curve_axis.set_xscale("log")
    curve_axis.set_yscale("log")
    curve_axis.set_xlabel("Horizon $T$", fontsize=8)
    curve_axis.set_ylabel("Cumulative pseudo-regret", fontsize=8)
    curve_axis.set_title("(a) Analytic 45-degree witness", fontsize=9)
    curve_axis.grid(color="#D8D8D8", linewidth=0.55, which="both")
    curve_axis.spines[["top", "right"]].set_visible(False)
    curve_axis.tick_params(labelsize=7)
    curve_axis.legend(frameon=False, fontsize=6.7, loc="upper left")

    colors = ("#CC3311", "#009988")
    offsets = (-0.12, 0.12)
    y = np.arange(len(noisy_cells), dtype=np.float64)
    for (comparison, label), color, offset in zip(
        PAIRED_COMPARISONS, colors, offsets
    ):
        means: list[float] = []
        lows: list[float] = []
        highs: list[float] = []
        for cell in noisy_cells:
            stats = _stats(
                paired[(cell, comparison)]["paired_cumulative_pseudo_regret"],
                f"figure paired {cell}/{comparison}",
                positive=True,
            )
            means.append(stats["mean"])
            lows.append(stats["ci95_low"])
            highs.append(stats["ci95_high"])
        means_array = np.asarray(means)
        paired_axis.errorbar(
            means_array,
            y + offset,
            xerr=np.vstack(
                (means_array - np.asarray(lows), np.asarray(highs) - means_array)
            ),
            marker="o" if offset < 0 else "s",
            color=color,
            linestyle="none",
            capsize=2.0,
            markersize=4.1,
            linewidth=1.1,
            label=label,
        )
    paired_axis.set_xscale("log")
    paired_axis.set_yticks(y, [_cell_label(cell) for cell in noisy_cells])
    paired_axis.set_xlabel(r"Paired $R_T(\mathrm{method})-R_T(\mathrm{full})$", fontsize=8)
    paired_axis.set_title(
        f"(b) Noisy extensions at $T={checkpoints[-1]:,}$",
        fontsize=9,
    )
    paired_axis.grid(axis="x", color="#D8D8D8", linewidth=0.55, which="major")
    paired_axis.spines[["top", "right"]].set_visible(False)
    paired_axis.tick_params(labelsize=7)
    paired_axis.legend(frameon=False, fontsize=6.7, loc="lower right")

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output,
        bbox_inches="tight",
        metadata={
            "Creator": "experiments.make_offdiagonal_witness_paper_artifacts",
            "Title": "Off-diagonal linear-Gram witness",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    plt.close(fig)


def _format_regret(value: float) -> str:
    return f"{value:.2f}"


def _make_table(
    checkpoints: Sequence[int],
    groups: Mapping[tuple[str, str], Mapping[str, Any]],
    output: Path,
) -> None:
    headers = " & ".join(f"$R_{{{horizon}}}$" for horizon in checkpoints)
    lines = [
        "% Auto-generated by experiments.make_offdiagonal_witness_paper_artifacts; do not edit.",
        r"\begingroup",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{3.0pt}",
        r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lrrrrr@{}}",
        r"\toprule",
        f"Policy & {headers} & Log--log slope " + r"\\",
        r"\midrule",
    ]
    for method in TABLE_METHODS:
        group = groups[("analytic", method)]
        values = " & ".join(_format_regret(value) for value in _regret_curve(group))
        slope = _number(group["log_log_slope"]["estimate"], f"table {method} slope")
        displayed_slope = 0.0 if abs(slope) < 0.0005 else slope
        lines.append(
            f"{METHOD_LABELS[method]} & {values} & {displayed_slope:.3f} " + r"\\"
        )
    lines.extend((r"\bottomrule", r"\end{tabular*}", r"\endgroup", ""))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="ascii")


def generate_offdiagonal_witness_paper_artifacts(
    *,
    source: str | Path = DEFAULT_SOURCE,
    figure: str | Path = DEFAULT_FIGURE,
    table: str | Path = DEFAULT_TABLE,
) -> dict[str, Any]:
    """Validate one derived witness artifact and generate its paper outputs."""

    source_path = Path(source)
    figure_path = Path(figure)
    table_path = Path(table)
    report, source_sidecar = _load_validated(source_path)
    checkpoints, groups, noisy_cells, paired = _validate_source(report)

    _make_figure(checkpoints, groups, noisy_cells, paired, figure_path)
    _make_table(checkpoints, groups, table_path)

    direct_inputs = (source_path, source_sidecar)
    figure_parameters = {
        "analytic_cell": "analytic",
        "analytic_curves": [
            ["exact_full", "full_cg"],
            ["diagonal_raw", "diagonal_uniform_transfer"],
        ],
        "noisy_cells": list(noisy_cells),
        "paired_comparisons": [item[0] for item in PAIRED_COMPARISONS],
        "paired_horizon": checkpoints[-1],
        "uncertainty_interval": "paired_two_sided_95_percent_student_t_interval",
        "log_axis_numerical_floor": None,
    }
    table_parameters = {
        "cell": "analytic",
        "checkpoints": list(checkpoints),
        "methods": list(TABLE_METHODS),
        "slope_regression": "OLS log(mean cumulative pseudo-regret) on log(horizon)",
    }
    sidecars = (
        _write_provenance(figure_path, direct_inputs, figure_parameters),
        _write_provenance(table_path, direct_inputs, table_parameters),
    )
    return {
        "schema_version": 1,
        "source": {"path": str(source_path), "sha256": _sha256(source_path)},
        "artifacts": [str(figure_path), str(table_path)],
        "provenance_sidecars": [str(path) for path in sidecars],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--figure", type=Path, default=DEFAULT_FIGURE)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    args = parser.parse_args(argv)
    result = generate_offdiagonal_witness_paper_artifacts(
        source=args.source,
        figure=args.figure,
        table=args.table,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "METHOD_LABELS",
    "PAIRED_COMPARISONS",
    "TABLE_METHODS",
    "WitnessPaperArtifactError",
    "generate_offdiagonal_witness_paper_artifacts",
]
