"""Aggregate the balanced MNIST benchmark and generate figures and table."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import ttest_1samp

matplotlib.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})

from .aggregate_results import student_t_interval
from .artifact_utils import (
    sha256_file,
    validate_sha256_sidecar,
    write_json_artifact,
    write_provenance_sidecar,
    write_sha256_sidecar,
)
from .logging_utils import canonical_json


REFERENCE = "current_full_ggn_cg"
DISPLAY_NAMES = {
    "current_full_ggn_cg": "Current full GGN (dense)",
    "historical_neural_ucb": "Historical NeuralUCB",
    "neural_ts": "NeuralTS",
    "neural_linear": "NeuralLinear",
    "frozen_last_layer_ucb": "Frozen last-layer UCB",
    "all_layer_diagonal": "All-layer diagonal",
    "block_laplace": "Block Laplace",
    "lofi": "LO-FI style",
    "linucb_frozen": "LinUCB (frozen)",
    "greedy": "Greedy",
    "context_free_ucb": "Context-free UCB",
    "context_free_ts": "Context-free TS",
}


def _read_json(path: Path) -> Any:
    validate_sha256_sidecar(path)
    return json.loads(path.read_text(encoding="ascii"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    validate_sha256_sidecar(path)
    return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines() if line]


def _holm(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    result = [1.0] * len(values)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (len(values) - rank) * values[index]))
        result[index] = running
    return result


def build_artifacts(
    raw_root: str | Path,
    derived_path: str | Path,
    regret_figure: str | Path,
    compute_figure: str | Path,
    table_path: str | Path,
) -> dict[str, Any]:
    raw = Path(raw_root)
    selection = _read_json(raw / "selection.json")
    manifest = _read_json(raw / "manifest.json")
    summaries = _read_jsonl(raw / "evaluation_summaries.jsonl")
    rounds = _read_jsonl(raw / "rounds.jsonl")
    if selection.get("evaluation_seeds_inspected") is not False:
        raise ValueError("evaluation seeds may have been used for selection")
    if set(selection["tuning_seeds"]) & set(manifest["evaluation_seeds"]):
        raise ValueError("tuning/evaluation seed overlap")
    methods = list(selection["selected"])
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for summary in summaries:
        grouped[str(summary["method"])].append(summary)
    expected_seeds = set(manifest["evaluation_seeds"])
    if set(grouped) != set(methods):
        raise ValueError("method coverage mismatch")
    for method, records in grouped.items():
        if {int(record["seed"]) for record in records} != expected_seeds:
            raise ValueError(f"evaluation seed coverage mismatch for {method}")

    metrics: list[dict[str, Any]] = []
    for method in methods:
        records = grouped[method]
        full_gram = method in {
            "current_full_ggn_cg",
            "historical_neural_ucb",
            "neural_ts",
        }
        metrics.append(
            {
                "method": method,
                "regret": student_t_interval(float(row["cumulative_pseudo_regret"]) for row in records),
                "accuracy": student_t_interval(float(row["accuracy"]) for row in records),
                "coverage": student_t_interval(float(row["empirical_coverage"]) for row in records),
                "wall_seconds": student_t_interval(float(row["wall_seconds"]) for row in records),
                "peak_rss_bytes": student_t_interval(float(row["peak_rss_bytes"]) for row in records),
                "sample_cvps": student_t_interval(float(row["sample_cvps"]) for row in records),
                "maximum_original_relative_residual": (
                    max(
                        float(row["maximum_cg_original_relative_residual"])
                        for row in records
                    )
                    if full_gram
                    else None
                ),
                "full_gram_solver": (
                    str(records[0]["full_gram_solver"]) if full_gram else None
                ),
                "selected_hyperparameters": selection["selected"][method],
            }
        )

    reference = {int(row["seed"]): row for row in grouped[REFERENCE]}
    comparisons: list[dict[str, Any]] = []
    p_values: list[float] = []
    for method in methods:
        if method == REFERENCE:
            continue
        indexed = {int(row["seed"]): row for row in grouped[method]}
        differences = np.asarray(
            [
                float(indexed[seed]["cumulative_pseudo_regret"])
                - float(reference[seed]["cumulative_pseudo_regret"])
                for seed in sorted(reference)
            ]
        )
        if np.all(differences == differences[0]):
            p_value = 1.0 if differences[0] == 0.0 else 0.0
        else:
            p_value = float(ttest_1samp(differences, 0.0).pvalue)
        p_values.append(p_value)
        comparisons.append(
            {
                "method": method,
                "reference": REFERENCE,
                "difference": "method_minus_full_regret",
                "interval": student_t_interval(differences.tolist()),
                "raw_p_value": p_value,
            }
        )
    for comparison, adjusted in zip(comparisons, _holm(p_values), strict=True):
        comparison["holm_adjusted_p_value"] = adjusted
        comparison["significant_at_0.05"] = adjusted < 0.05

    report = {
        "schema_version": 1,
        "study": "mnist_contextual_benchmark",
        "manifest": manifest,
        "selection": selection,
        "metrics": metrics,
        "paired_comparisons": comparisons,
        "inputs": [
            {"path": (raw / name).as_posix(), "sha256": sha256_file(raw / name)}
            for name in ("selection.json", "manifest.json", "evaluation_summaries.jsonl", "rounds.jsonl")
        ],
    }
    derived, derived_hash = write_json_artifact(derived_path, report)

    evaluation_rounds = [row for row in rounds if row["phase"] == "evaluation"]
    by_method_seed: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in evaluation_rounds:
        by_method_seed[(str(row["method"]), int(row["seed"]))].append(row)
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 3.8), constrained_layout=True)
    for method in methods:
        trajectories = [
            np.asarray([row["cumulative_pseudo_regret"] for row in by_method_seed[(method, seed)]], dtype=float)
            for seed in sorted(expected_seeds)
        ]
        accuracy = [
            np.cumsum([row["accuracy"] for row in by_method_seed[(method, seed)]])
            / np.arange(1, len(by_method_seed[(method, seed)]) + 1)
            for seed in sorted(expected_seeds)
        ]
        label = DISPLAY_NAMES.get(method, method)
        axes[0].plot(np.mean(trajectories, axis=0), label=label, linewidth=1)
        axes[1].plot(np.mean(accuracy, axis=0), label=label, linewidth=1)
    axes[0].set(xlabel="Round", ylabel="Cumulative pseudo-regret")
    axes[1].set(xlabel="Round", ylabel="Online accuracy")
    axes[1].legend(fontsize=5, ncol=2)
    regret_path = Path(regret_figure)
    regret_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(regret_path, metadata={"Creator":"mnist_contextual_benchmark","CreationDate":None,"ModDate":None})
    plt.close(figure)
    write_sha256_sidecar(regret_path)

    figure, axis = plt.subplots(figsize=(6.4, 4.4), constrained_layout=True)
    for row in metrics:
        axis.scatter(row["wall_seconds"]["mean"], row["regret"]["mean"], s=25)
        axis.annotate(
            DISPLAY_NAMES.get(str(row["method"]), str(row["method"])),
            (row["wall_seconds"]["mean"], row["regret"]["mean"]),
            fontsize=6,
        )
    axis.set(xlabel="Mean wall time (s, log scale)", ylabel="Mean cumulative pseudo-regret", xscale="log")
    compute_path = Path(compute_figure)
    compute_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(compute_path, metadata={"Creator":"mnist_contextual_benchmark","CreationDate":None,"ModDate":None})
    plt.close(figure)
    write_sha256_sidecar(compute_path)

    table = Path(table_path)
    table.parent.mkdir(parents=True, exist_ok=True)
    lines = [r"\begin{tabular}{lrrrrr}", r"\toprule", r"Method & Regret & Accuracy & Time (s) & Peak MB & Max res. \\", r"\midrule"]
    for row in metrics:
        method_label = DISPLAY_NAMES.get(
            str(row["method"]), str(row["method"])
        ).replace("_", r"\_")
        lines.append(
            f"{method_label} & {row['regret']['mean']:.2f} & "
            f"{row['accuracy']['mean']:.3f} & {row['wall_seconds']['mean']:.2f} & "
            f"{row['peak_rss_bytes']['mean'] / 2**20:.1f} & "
            + (
                "--"
                if row["maximum_original_relative_residual"] is None
                else f"{row['maximum_original_relative_residual']:.1e}"
            )
            + " \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    table.write_text("\n".join(lines) + "\n", encoding="ascii")
    write_sha256_sidecar(table)
    publication_inputs = [
        {"path": derived.as_posix(), "sha256": sha256_file(derived)},
        {
            "path": derived_hash.as_posix(),
            "sha256": sha256_file(derived_hash),
        },
    ]
    for artifact, artifact_kind in (
        (regret_path, "regret_accuracy_figure"),
        (compute_path, "compute_regret_figure"),
        (table, "benchmark_table"),
    ):
        write_provenance_sidecar(
            artifact,
            publication_inputs,
            generation_parameters={
                "artifact_kind": artifact_kind,
                "study": "mnist_contextual_benchmark",
            },
        )
    return {"derived":derived.as_posix(),"regret_figure":regret_path.as_posix(),"compute_figure":compute_path.as_posix(),"table":table.as_posix()}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--derived", type=Path, required=True)
    parser.add_argument("--regret-figure", type=Path, required=True)
    parser.add_argument("--compute-figure", type=Path, required=True)
    parser.add_argument("--table", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    print(canonical_json(build_artifacts(args.raw_root,args.derived,args.regret_figure,args.compute_figure,args.table)))


if __name__ == "__main__":
    main()
