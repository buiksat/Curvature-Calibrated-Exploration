"""Validate coverage-matched raw outputs and generate paper artifacts."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from .artifact_utils import (
    sha256_file,
    validate_sha256_sidecar,
    write_json_artifact,
    write_sha256_sidecar,
)
from .logging_utils import canonical_json
from .run_coverage_matched_operator_study import PROTOCOLS, REFERENCE


def _read_json(path: Path) -> Any:
    validate_sha256_sidecar(path)
    return json.loads(path.read_text(encoding="ascii"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    validate_sha256_sidecar(path)
    return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines() if line]


def _latex(value: str) -> str:
    return value.replace("_", r"\_")


def _matrix(
    aggregates: list[dict[str, Any]],
    protocol: str,
    methods: list[str],
    cells: list[str],
    metric: str,
    *,
    difference_from_reference: bool = False,
) -> np.ndarray:
    indexed = {
        (row["protocol"], row["cell_id"], row["semantic_method"]): row
        for row in aggregates
    }
    result = np.empty((len(methods), len(cells)), dtype=np.float64)
    for method_index, method in enumerate(methods):
        for cell_index, cell in enumerate(cells):
            value = float(indexed[(protocol, cell, method)][metric]["mean"])
            if difference_from_reference:
                value -= float(indexed[(protocol, cell, REFERENCE)][metric]["mean"])
            result[method_index, cell_index] = value
    return result


def _heatmap(
    axis: plt.Axes,
    values: np.ndarray,
    methods: list[str],
    cells: list[str],
    *,
    title: str,
    cmap: str,
    symmetric: bool = False,
) -> None:
    limit = float(np.max(np.abs(values))) if symmetric else None
    image = axis.imshow(
        values,
        aspect="auto",
        cmap=cmap,
        vmin=-limit if symmetric and limit else None,
        vmax=limit if symmetric and limit else None,
    )
    axis.set_title(title, fontsize=9)
    axis.set_xticks(range(len(cells)), cells, rotation=45, ha="right", fontsize=6)
    axis.set_yticks(range(len(methods)), methods, fontsize=6)
    axis.figure.colorbar(image, ax=axis, fraction=0.046, pad=0.03)


def build_artifacts(
    raw_root: str | Path,
    derived_path: str | Path,
    mechanism_figure: str | Path,
    heatmap_figure: str | Path,
    table_path: str | Path,
    comparison_table_path: str | Path | None = None,
) -> dict[str, Any]:
    raw = Path(raw_root)
    selection = _read_json(raw / "selection.json")
    aggregates = _read_json(raw / "aggregates.json")
    comparisons = _read_json(raw / "paired_comparisons.json")
    manifest = _read_json(raw / "manifest.json")
    summaries = _read_jsonl(raw / "evaluation_summaries.jsonl")
    if manifest.get("evaluation_seeds_inspected_during_selection") is not False:
        raise ValueError("selection may have inspected evaluation seeds")
    if selection.get("evaluation_seeds_inspected") is not False:
        raise ValueError("selection artifact may have inspected evaluation seeds")
    if set(selection["tuning_seeds"]) & set(manifest["evaluation_seeds"]):
        raise ValueError("tuning/evaluation seed overlap")
    expected_runs = (
        manifest["cell_count"]
        * len(manifest["evaluation_seeds"])
        * len(PROTOCOLS)
        * len(manifest["semantic_methods"])
    )
    if len(summaries) != expected_runs or manifest["evaluation_run_count"] != expected_runs:
        raise ValueError("evaluation run coverage is incomplete")
    comparison_count = int(manifest["holm_family_size"])

    inputs = []
    for name in (
        "selection.json",
        "aggregates.json",
        "paired_comparisons.json",
        "evaluation_summaries.jsonl",
        "manifest.json",
    ):
        path = raw / name
        inputs.append({"path": path.as_posix(), "sha256": sha256_file(path)})
    report = {
        "schema_version": 1,
        "study": "coverage_matched_operator",
        "selection": selection,
        "aggregates": aggregates,
        "paired_comparisons": comparisons,
        "manifest": manifest,
        "inputs": inputs,
        "inference": {
            "test": "two_sided_paired_student_t_on_seed_level_terminal_regret_differences",
            "family": f"all {comparison_count} prespecified protocol-cell-surrogate comparisons",
            "familywise_alpha": 0.05,
            "adjustment": "Holm step-down",
            "zero_variance_rule": (
                "p=1 for an identically zero difference; p=0 for a constant "
                "nonzero difference"
            ),
        },
        "interpretation": (
            "All cells are prespecified. Regret compares independently executed policies "
            "and is not a causal operator contrast."
        ),
    }
    derived, _ = write_json_artifact(derived_path, report)

    methods = list(manifest["semantic_methods"])
    cells = sorted({str(row["cell_id"]) for row in aggregates})
    figure, axes = plt.subplots(1, 3, figsize=(11.5, 3.4), constrained_layout=True)
    for axis, protocol in zip(axes, PROTOCOLS, strict=True):
        values = _matrix(
            aggregates,
            protocol,
            methods,
            cells,
            "cumulative_pseudo_regret",
            difference_from_reference=True,
        )
        _heatmap(
            axis,
            values,
            methods,
            cells,
            title=protocol.replace("_", " "),
            cmap="coolwarm",
            symmetric=True,
        )
    mechanism = Path(mechanism_figure)
    mechanism.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        mechanism,
        metadata={"Creator": "coverage_matched_operator", "CreationDate": None, "ModDate": None},
    )
    plt.close(figure)
    write_sha256_sidecar(mechanism)

    figure, axes = plt.subplots(2, 3, figsize=(11.5, 6.2), constrained_layout=True)
    for column, protocol in enumerate(PROTOCOLS):
        coverage = _matrix(
            aggregates, protocol, methods, cells, "empirical_coverage_all_actions"
        )
        disagreement = _matrix(
            aggregates, protocol, methods, cells, "top_action_disagreement_rate"
        )
        _heatmap(
            axes[0, column], coverage, methods, cells,
            title=f"{protocol.replace('_', ' ')}: coverage", cmap="viridis"
        )
        _heatmap(
            axes[1, column], disagreement, methods, cells,
            title=f"{protocol.replace('_', ' ')}: disagreement", cmap="magma"
        )
    heatmap = Path(heatmap_figure)
    heatmap.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        heatmap,
        metadata={"Creator": "coverage_matched_operator", "CreationDate": None, "ModDate": None},
    )
    plt.close(figure)
    write_sha256_sidecar(heatmap)

    table = Path(table_path)
    table.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Operator & Identical & 95\% coverage & Mean bonus \\",
        r"\midrule",
    ]
    multipliers = selection["multipliers"]
    for method in methods:
        lines.append(
            f"{_latex(method)} & {multipliers['identical_theoretical'][method]:.3f} & "
            f"{multipliers['matched_95_coverage'][method]:.3f} & "
            f"{multipliers['matched_mean_bonus'][method]:.3f} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    table.write_text("\n".join(lines) + "\n", encoding="ascii")
    write_sha256_sidecar(table)

    comparison_table = (
        Path(comparison_table_path)
        if comparison_table_path is not None
        else table.with_name("coverage_matched_comparisons.tex")
    )
    comparison_table.parent.mkdir(parents=True, exist_ok=True)
    comparison_lines: list[str] = []
    protocol_titles = {
        "identical_theoretical": "Identical theoretical coefficient",
        "matched_95_coverage": "Tuning-matched 95\\% coverage",
        "matched_mean_bonus": "Tuning-matched mean bonus",
    }
    classifications = {
        "surrogate_lower_regret": "surrogate lower",
        "current_full_lower_regret": "full lower",
        "unresolved": "unresolved",
    }
    for protocol_index, protocol in enumerate(PROTOCOLS):
        comparison_lines.extend(
            [
                r"\begin{table*}[p]",
                r"\centering\tiny",
                r"\begin{tabular}{llrrrl}",
                r"\toprule",
                r"Cell & Surrogate & Mean diff. & Raw $p$ & Holm $p$ & Classification \\",
                r"\midrule",
            ]
        )
        protocol_rows = sorted(
            (row for row in comparisons if row["protocol"] == protocol),
            key=lambda row: (str(row["cell_id"]), str(row["semantic_method"])),
        )
        for row in protocol_rows:
            comparison_lines.append(
                f"{_latex(str(row['cell_id']))} & "
                f"{_latex(str(row['semantic_method']))} & "
                f"{float(row['interval']['mean']):.3f} & "
                f"{float(row['raw_two_sided_p_value']):.2e} & "
                f"{float(row['holm_adjusted_p_value']):.2e} & "
                f"{classifications[str(row['classification'])]} \\\\"
            )
        label = (
            "tab:coverage-matched-comparisons"
            if protocol_index == 0
            else f"tab:coverage-matched-comparisons-{protocol_index + 1}"
        )
        comparison_lines.extend(
            [
                r"\bottomrule",
                r"\end{tabular}",
                (
                    r"\caption{Paired terminal-regret inference for the "
                    + protocol_titles[protocol]
                    + r" protocol. Differences are surrogate minus current full GGN; "
                    f"Holm adjustment uses the complete {comparison_count}-test family.}}"
                ),
                f"\\label{{{label}}}",
                r"\end{table*}",
                "",
            ]
        )
    comparison_table.write_text("\n".join(comparison_lines), encoding="ascii")
    write_sha256_sidecar(comparison_table)
    return {
        "derived": derived.as_posix(),
        "mechanism_figure": mechanism.as_posix(),
        "heatmap_figure": heatmap.as_posix(),
        "calibration_table": table.as_posix(),
        "comparison_table": comparison_table.as_posix(),
        "evaluation_run_count": expected_runs,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--derived", type=Path, required=True)
    parser.add_argument("--mechanism-figure", type=Path, required=True)
    parser.add_argument("--heatmap-figure", type=Path, required=True)
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--comparison-table", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    result = build_artifacts(
        args.raw_root,
        args.derived,
        args.mechanism_figure,
        args.heatmap_figure,
        args.table,
        args.comparison_table,
    )
    print(canonical_json(result))


if __name__ == "__main__":
    main()
