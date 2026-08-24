"""Deterministic standalone artifacts for realistic transport evidence."""

from __future__ import annotations

import argparse
import csv
import io
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .provenance import atomic_write_text, sha256_file, write_json


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("aggregate has an unsupported schema")
    return value


def _write_csv(
    path: Path,
    fields: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field) for field in fields})
    destination = atomic_write_text(path, output.getvalue())
    atomic_write_text(
        destination.with_name(destination.name + ".sha256"),
        f"{sha256_file(destination)}  {destination.name}\n",
    )


def _metric(cell: Mapping[str, Any], name: str, statistic: str = "mean") -> Any:
    value = cell["metrics"].get(name)
    return None if value is None else value.get(statistic)


def _method_rows(aggregate: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell in aggregate["method_statistics"]:
        rows.append(
            {
                "task": cell["task"],
                "method": cell["method"],
                "prefix": cell["prefix"],
                "seed_count": cell["seed_count"],
                "regret_mean": _metric(cell, "cumulative_regret"),
                "regret_se": _metric(cell, "cumulative_regret", "standard_error"),
                "regret_median": _metric(cell, "cumulative_regret", "median"),
                "runtime_mean_seconds": _metric(cell, "algorithm_seconds"),
                "memory_mean_bytes": _metric(cell, "peak_rss_bytes"),
                "reference_coverage": cell["reference_confidence"]["proportion"],
                "reference_coverage_low": cell["reference_confidence"][
                    "clopper_pearson_95"
                ]["ci_low"],
                "reference_coverage_high": cell["reference_confidence"][
                    "clopper_pearson_95"
                ]["ci_high"],
                "optimism": cell["method_optimism"]["proportion"],
                "optimism_low": cell["method_optimism"]["clopper_pearson_95"]["ci_low"],
                "optimism_high": cell["method_optimism"]["clopper_pearson_95"][
                    "ci_high"
                ],
            }
        )
    return rows


def _selected_run_rows(
    aggregate: Mapping[str, Any], predicate: Callable[[Mapping[str, Any]], bool]
) -> list[dict[str, Any]]:
    return [dict(row) for row in aggregate["run_level_metrics"] if predicate(row)]


def _write_publication_data(aggregate: Mapping[str, Any], root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    method_rows = _method_rows(aggregate)
    common = ("task", "method", "prefix", "seed_count")
    _write_csv(
        root / "cumulative_regret_curves.csv",
        (*common, "regret_mean", "regret_se", "regret_median"),
        method_rows,
    )
    maximum = int(max(aggregate["prefixes"]))
    final_rows = [row for row in method_rows if int(row["prefix"]) == maximum]
    _write_csv(
        root / "runtime_regret_pareto.csv",
        ("task", "method", "seed_count", "regret_mean", "runtime_mean_seconds"),
        final_rows,
    )
    _write_csv(
        root / "memory_regret_pareto.csv",
        ("task", "method", "seed_count", "regret_mean", "memory_mean_bytes"),
        final_rows,
    )
    _write_csv(
        root / "confidence_optimism.csv",
        (
            "task",
            "method",
            "seed_count",
            "reference_coverage",
            "reference_coverage_low",
            "reference_coverage_high",
            "optimism",
            "optimism_low",
            "optimism_high",
        ),
        final_rows,
    )

    run_rows = aggregate["run_level_metrics"]
    diagnostic_specs = {
        "path_vs_endpoint.csv": (
            (
                "task",
                "method",
                "seed",
                "prefix",
                "D_Q_minus_d_Th",
                "D_Q_over_d_Th",
                "D_Q_over_d_Th_zero_denominators",
            ),
            lambda row: row.get("D_Q_minus_d_Th") is not None,
        ),
        "operator_tail_kappa.csv": (
            (
                "task",
                "method",
                "seed",
                "prefix",
                "trace_tail_over_operator_tail",
                "kappa_minus",
                "oracle_kappa_minus",
            ),
            lambda row: row.get("trace_tail_over_operator_tail") is not None,
        ),
        "certified_width_inflation.csv": (
            (
                "task",
                "method",
                "seed",
                "prefix",
                "width_upper_over_exact",
                "solver_alpha",
                "cg_iterations",
                "cg_matvecs",
            ),
            lambda row: row.get("width_upper_over_exact") is not None,
        ),
        "theorem_bound_nonvacuity.csv": (
            (
                "task",
                "method",
                "seed",
                "prefix",
                "cumulative_regret",
                "sharp_theorem_rhs",
                "trivial_regret_bound",
                "theorem_bound_nonvacuous",
                "zero_regret",
            ),
            lambda row: row.get("theorem_bound_nonvacuous") is not None,
        ),
        "controlled_misspecification_decomposition.csv": (
            (
                "task",
                "method",
                "seed",
                "prefix",
                "historical_misspecification_envelope",
                "current_misspecification_envelope",
            ),
            lambda row: row["task"] == "covtype_semisynthetic_misspecified",
        ),
        "real_label_baseline_comparison.csv": (
            (
                "task",
                "method",
                "seed",
                "prefix",
                "cumulative_regret",
                "action_accuracy",
                "algorithm_seconds",
                "peak_rss_bytes",
            ),
            lambda row: row["task"] == "covtype_label_bandit",
        ),
    }
    for name, (fields, predicate) in diagnostic_specs.items():
        _write_csv(root / name, fields, _selected_run_rows(aggregate, predicate))

    source_hash = aggregate["raw_input_inventory_sha256"]
    latex = """% Deterministic standalone PGFPlots input.
% Raw aggregate inventory SHA-256: {source_hash}
\\begin{{tikzpicture}}
\\begin{{axis}}[
  xlabel={{Round}}, ylabel={{Mean cumulative pseudo-regret}},
  legend style={{font=\\scriptsize}},
]
% Choose a task/method by filtering cumulative_regret_curves.csv before inclusion.
\\addplot table [x=prefix,y=regret_mean,col sep=comma] {{cumulative_regret_curves.csv}};
\\end{{axis}}
\\end{{tikzpicture}}
""".format(
        source_hash=source_hash
    )
    destination = atomic_write_text(root / "cumulative_regret_plot.tex", latex)
    atomic_write_text(
        destination.with_name(destination.name + ".sha256"),
        f"{sha256_file(destination)}  {destination.name}\n",
    )
    readme = """# Realistic transport publication-artifact data

These deterministic CSV files derive from one accepted aggregate. The
aggregate input inventory SHA-256 is `{source_hash}`. A file from a smoke or
pilot profile is engineering evidence only and must not be cited as Covertype
publication evidence.
""".format(
        source_hash=source_hash
    )
    destination = atomic_write_text(root / "README.md", readme)
    atomic_write_text(
        destination.with_name(destination.name + ".sha256"),
        f"{sha256_file(destination)}  {destination.name}\n",
    )


def _results_markdown(aggregate: Mapping[str, Any]) -> str:
    maximum = int(max(aggregate["prefixes"]))
    final = [
        cell
        for cell in aggregate["method_statistics"]
        if int(cell["prefix"]) == maximum
    ]
    lines = [
        "# Realistic confidence-transport benchmark results",
        "",
        f"Profile: `{aggregate['profile']}`",
        "",
        f"Accepted cells: {aggregate['accepted_cell_count']} / {aggregate['expected_cell_count']}",
        "",
        f"Raw-input inventory SHA-256: `{aggregate['raw_input_inventory_sha256']}`",
        "",
    ]
    if not aggregate["publication_evidence"]:
        lines.extend(
            [
                "This result is not publication evidence. It uses a smoke or pilot "
                "profile and cannot answer the preregistered Covertype acceptance question.",
                "",
            ]
        )
    lines.extend(
        [
            "| Task | Method | n | Mean regret | SE | Coverage | Optimism | Algorithm s | Peak MiB |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for cell in final:
        regret = cell["metrics"]["cumulative_regret"]
        runtime = cell["metrics"]["algorithm_seconds"]
        memory = cell["metrics"]["peak_rss_bytes"]
        lines.append(
            "| {task} | {method} | {n} | {regret:.6g} | {se:.3g} | {coverage:.3f} | {optimism:.3f} | {runtime:.4g} | {memory:.2f} |".format(
                task=cell["task"],
                method=cell["method"],
                n=cell["seed_count"],
                regret=float(regret["mean"]),
                se=float(regret["standard_error"]),
                coverage=float(cell["reference_confidence"]["proportion"]),
                optimism=float(cell["method_optimism"]["proportion"]),
                runtime=float(runtime["mean"]),
                memory=float(memory["mean"]) / (1024.0 * 1024.0),
            )
        )
    lines.extend(
        [
            "",
            "Float64 residual and Loewner checks are exact-arithmetic certificate "
            "diagnostics, not verified numerical certificates.",
            "",
        ]
    )
    return "\n".join(lines)


def generate_artifacts(
    *, aggregate_path: str | Path, review_root: str | Path
) -> dict[str, Any]:
    aggregate = _load(aggregate_path)
    root = Path(review_root)
    root.mkdir(parents=True, exist_ok=True)
    results = atomic_write_text(root / "RESULTS.md", _results_markdown(aggregate))
    atomic_write_text(
        results.with_name(results.name + ".sha256"),
        f"{sha256_file(results)}  {results.name}\n",
    )
    statistical = {
        "schema_version": 1,
        "profile": aggregate["profile"],
        "raw_input_inventory_sha256": aggregate["raw_input_inventory_sha256"],
        "method_statistics": aggregate["method_statistics"],
        "paired_primary_comparisons": aggregate["paired_primary_comparisons"],
        "rank_tolerance_effects": aggregate["rank_tolerance_effects"],
    }
    write_json(root / "STATISTICAL_RESULTS.json", statistical)
    provenance = {
        "schema_version": 1,
        "profile": aggregate["profile"],
        "publication_evidence": aggregate["publication_evidence"],
        "config_digest": aggregate["config_digest"],
        "common_provenance": aggregate["common_provenance"],
        "raw_input_inventory_sha256": aggregate["raw_input_inventory_sha256"],
        "raw_input_count": len(aggregate["raw_input_inventory"]),
    }
    write_json(root / "DATA_PROVENANCE.json", provenance)
    _write_publication_data(aggregate, root / "publication_artifacts")
    return {
        "results_sha256": sha256_file(root / "RESULTS.md"),
        "statistics_sha256": sha256_file(root / "STATISTICAL_RESULTS.json"),
        "data_provenance_sha256": sha256_file(root / "DATA_PROVENANCE.json"),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--aggregate",
        type=Path,
        default=Path("review/realistic_transport/AGGREGATE.json"),
    )
    parser.add_argument(
        "--review-root",
        type=Path,
        default=Path("review/realistic_transport"),
    )
    args = parser.parse_args(argv)
    print(
        json.dumps(
            generate_artifacts(
                aggregate_path=args.aggregate, review_root=args.review_root
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
