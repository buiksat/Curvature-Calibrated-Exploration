"""Create the compact, provenance-bound Covertype horizon report."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .aggregate_results import write_aggregate_with_provenance
from .logging_utils import canonical_json

DEFAULT_AGGREGATE = Path("results/derived/covertype_rerun_1500_full_aggregate.json")
DEFAULT_DIAGNOSTICS = Path("results/derived/covertype_test_class_counts.json")
DEFAULT_OUTPUT = Path("results/derived/covertype_horizon_results.json")
DEFAULT_TABLE = Path("paper/tables/covertype_horizon_results.tex")
HORIZONS = (200, 500, 1000, 1500)

POLICY_TYPES = {
    "full_network_ggn_cg": "contextual full-network GGN-CG UCB",
    "frozen_full_gram": "contextual frozen acquisition-gradient Gram UCB",
    "diagonal_full_network": "contextual diagonal full-network GGN UCB",
    "last_layer_full": "contextual full last-layer Gram UCB",
    "last_layer_diagonal": "contextual diagonal last-layer Gram UCB",
    "greedy_full_network": "contextual greedy full-network policy",
    "ucb1": "deployable non-contextual seven-arm UCB1",
    "thompson_sampling": (
        "deployable non-contextual independent Beta-Bernoulli Thompson sampling"
    ),
}

DISPLAY_NAMES = {
    "full_network_ggn_cg": "full GGN-CG",
    "frozen_full_gram": "frozen Gram",
    "diagonal_full_network": "diagonal full",
    "last_layer_full": "last-layer full",
    "last_layer_diagonal": "last-layer diagonal",
    "greedy_full_network": "greedy",
    "ucb1": "UCB1",
    "thompson_sampling": "Beta--Bernoulli TS",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _stats(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"missing statistics for {name}")
    required = ("mean", "ci95_low", "ci95_high", "ci95_half_width", "n")
    if any(not isinstance(value.get(key), (int, float)) for key in required):
        raise ValueError(f"malformed statistics for {name}")
    return {key: value[key] for key in value}


def derive(aggregate: Mapping[str, Any], diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "event": "executed_policy_aggregate",
        "experiments": ["covertype_rerun"],
        "profiles": ["full"],
        "seed_sets": ["evaluation"],
        "all_groups_complete": True,
        "all_paired_comparisons_complete": True,
        "all_runs_executed_policy": True,
        "all_seed_provenance_disjoint": True,
        "run_count": 80,
        "group_count": 8,
    }
    for key, expected in required.items():
        if aggregate.get(key) != expected:
            raise ValueError(f"Covertype aggregate failed strict gate: {key}")
    if diagnostics.get("event") != "covertype_test_class_count_diagnostics":
        raise ValueError("invalid Covertype class-count diagnostic")

    groups = aggregate.get("groups")
    pairs = aggregate.get("paired_comparisons")
    if not isinstance(groups, Sequence) or not isinstance(pairs, Sequence):
        raise ValueError("Covertype aggregate groups are malformed")
    by_method = {
        str(group.get("method")): group
        for group in groups
        if isinstance(group, Mapping)
    }
    if set(by_method) != set(POLICY_TYPES):
        raise ValueError("Covertype method set differs from the release protocol")
    pair_by_method = {
        str(pair.get("method")): pair
        for pair in pairs
        if isinstance(pair, Mapping)
        and pair.get("reference_method") == "full_network_ggn_cg"
    }
    if set(pair_by_method) != set(POLICY_TYPES) - {"full_network_ggn_cg"}:
        raise ValueError("Covertype paired comparisons are incomplete")

    rows: list[dict[str, Any]] = []
    for method in POLICY_TYPES:
        group = by_method[method]
        horizon_records = group.get("horizons")
        if not isinstance(horizon_records, Sequence):
            raise ValueError(f"{method} has no horizon records")
        pair_records: dict[int, Mapping[str, Any]] = {}
        if method in pair_by_method:
            raw_pairs = pair_by_method[method].get("horizons")
            if not isinstance(raw_pairs, Sequence):
                raise ValueError(f"{method} has no paired horizon records")
            pair_records = {
                int(item["horizon"]): item
                for item in raw_pairs
                if isinstance(item, Mapping)
            }
        results: list[dict[str, Any]] = []
        for item in horizon_records:
            if not isinstance(item, Mapping):
                continue
            horizon = int(item["horizon"])
            metrics = item.get("metrics")
            if not isinstance(metrics, Mapping):
                raise ValueError(f"{method}/{horizon} metrics are malformed")
            record: dict[str, Any] = {
                "horizon": horizon,
                "cumulative_pseudo_regret": _stats(
                    metrics.get("cumulative_pseudo_regret"),
                    name=f"{method}/{horizon}/regret",
                ),
                "accuracy": _stats(
                    metrics.get("accuracy"), name=f"{method}/{horizon}/accuracy"
                ),
                "runtime_seconds": _stats(
                    metrics.get("runtime_seconds"),
                    name=f"{method}/{horizon}/runtime",
                ),
            }
            if method == "full_network_ggn_cg":
                record["paired_method_minus_full_regret"] = None
            else:
                paired_metrics = pair_records[horizon].get("metrics")
                if not isinstance(paired_metrics, Mapping):
                    raise ValueError(f"{method}/{horizon} paired metrics are malformed")
                record["paired_method_minus_full_regret"] = _stats(
                    paired_metrics.get("cumulative_pseudo_regret"),
                    name=f"{method}/{horizon}/paired regret",
                )
            results.append(record)
        if tuple(record["horizon"] for record in results) != HORIZONS:
            raise ValueError(f"{method} horizons differ from {HORIZONS}")
        rows.append(
            {
                "method": method,
                "display_name": DISPLAY_NAMES[method],
                "policy_type": POLICY_TYPES[method],
                "certification_category": "uncertified",
                "certification_reason": (
                    "Binary rewards use Gaussian squared-loss curvature, outside "
                    "Theorem 1; no energy-error/transfer/confidence certificate is supplied."
                ),
                "solver_observation": (
                    "All evaluation CG calls reached their configured relative-residual "
                    "stopping rule, but this is not an energy-error solver certificate."
                    if method == "full_network_ggn_cg"
                    else "not_applicable"
                ),
                "results": results,
            }
        )

    diag = diagnostics.get("diagnostics")
    if not isinstance(diag, Mapping):
        raise ValueError("class diagnostic has no baselines")
    return {
        "schema_version": 1,
        "event": "covertype_horizon_report",
        "experiment": "covertype_rerun",
        "evaluation_seeds": list(range(150, 160)),
        "horizons": list(HORIZONS),
        "test_split": {
            "sample_count": diagnostics["test_sample_count"],
            "classes": diagnostics["classes"],
        },
        "baseline_diagnostics": {
            "uniform_random": diag["uniform_random"],
            "fixed_test_split_majority_arm_oracle": diag[
                "fixed_test_split_majority_arm_oracle"
            ],
        },
        "paired_interval_definition": (
            "Two-sided 95% Student-t interval for method minus full-network GGN-CG "
            "on common evaluation seeds and dataset-index streams."
        ),
        "theorem_scope": (
            "No Covertype policy is certified by Theorem 1 because the binary rewards "
            "are routed through Gaussian squared-loss curvature."
        ),
        "methods": rows,
    }


def _latex_table(report: Mapping[str, Any]) -> str:
    lines = [
        "% Auto-generated by experiments.make_covertype_horizon_artifact; do not edit.",
        r"\begin{tabular}{@{}lrrrr@{}}",
        r"\toprule",
        r"Policy & $T=200$ & $T=500$ & $T=1000$ & $T=1500$ \\",
        r"\midrule",
    ]
    for method in report["methods"]:
        cells = []
        for result in method["results"]:
            regret = float(result["cumulative_pseudo_regret"]["mean"])
            accuracy = float(result["accuracy"]["mean"])
            cells.append(f"{regret:.1f} / {accuracy:.3f}")
        lines.append(f"{method['display_name']} & " + " & ".join(cells) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    return "\n".join(lines)


def generate(
    aggregate_path: Path = DEFAULT_AGGREGATE,
    diagnostics_path: Path = DEFAULT_DIAGNOSTICS,
    output_path: Path = DEFAULT_OUTPUT,
    table_path: Path = DEFAULT_TABLE,
) -> dict[str, str]:
    aggregate = _load(aggregate_path)
    diagnostics = _load(diagnostics_path)
    report = derive(aggregate, diagnostics)
    inputs = sorted([
        {"path": aggregate_path.as_posix(), "sha256": _sha256(aggregate_path)},
        {"path": diagnostics_path.as_posix(), "sha256": _sha256(diagnostics_path)},
    ], key=lambda item: item["path"])
    report["inputs"] = inputs
    report["raw_input_set_sha256"] = aggregate.get("input_set_sha256")
    report["input_set_sha256"] = hashlib.sha256(
        canonical_json(inputs).encode("ascii")
    ).hexdigest()
    _, output_sidecar = write_aggregate_with_provenance(report, output_path)
    table_path.parent.mkdir(parents=True, exist_ok=True)
    table_path.write_text(_latex_table(report), encoding="ascii")

    table_inputs = [{"path": output_path.as_posix(), "sha256": _sha256(output_path)}]
    table_sidecar = table_path.with_suffix(table_path.suffix + ".provenance.json")
    table_sidecar.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "artifact": table_path.as_posix(),
                "artifact_sha256": _sha256(table_path),
                "inputs": table_inputs,
                "input_set_sha256": hashlib.sha256(
                    canonical_json(table_inputs).encode("ascii")
                ).hexdigest(),
                "raw_input_set_sha256": aggregate.get("input_set_sha256"),
            },
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "artifact": output_path.as_posix(),
        "artifact_provenance": output_sidecar.as_posix(),
        "table": table_path.as_posix(),
        "table_provenance": table_sidecar.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, default=DEFAULT_AGGREGATE)
    parser.add_argument("--diagnostics", type=Path, default=DEFAULT_DIAGNOSTICS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    args = parser.parse_args()
    print(
        json.dumps(
            generate(args.aggregate, args.diagnostics, args.output, args.table),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
