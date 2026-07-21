"""Build the compact certified-tanh report from evaluation-seed summaries."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .aggregate_results import student_t_interval, write_aggregate_with_provenance
from .config import get_seed_set, load_config
from .logging_utils import canonical_json


DEFAULT_CONFIG = Path("experiments/configs/certified_tanh.yaml")
DEFAULT_RAW_ROOT = Path("results/raw/certified_tanh/full/evaluation")
DEFAULT_AGGREGATE = Path("results/derived/certified_tanh_full.json")
DEFAULT_GRID_AGGREGATE = Path("results/derived/certified_tanh_controlled_grid.json")
DEFAULT_OUTPUT = Path("results/derived/certified_tanh_report.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _metric_interval(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, Any]:
    values = [float(row[key]) for row in rows]
    return student_t_interval(values)


def build_artifact(
    *,
    config_path: Path = DEFAULT_CONFIG,
    raw_root: Path = DEFAULT_RAW_ROOT,
    aggregate_path: Path = DEFAULT_AGGREGATE,
    grid_aggregate_path: Path = DEFAULT_GRID_AGGREGATE,
) -> dict[str, Any]:
    config = load_config(config_path, profile="full")
    expected_seeds = tuple(get_seed_set(config, "evaluation"))
    aggregate = _load_object(aggregate_path)
    grid_aggregate = _load_object(grid_aggregate_path)
    if int(aggregate.get("run_count", -1)) != 2 * len(expected_seeds):
        raise ValueError("aggregate run count does not match the full evaluation protocol")

    by_center: dict[str, list[dict[str, Any]]] = {}
    if int(grid_aggregate.get("run_count", -1)) != 160 or int(
        grid_aggregate.get("group_count", -1)
    ) != 16:
        raise ValueError("controlled-grid aggregate is incomplete")
    inputs = [config_path, aggregate_path, grid_aggregate_path]
    for center in ("original", "corrected"):
        rows: list[dict[str, Any]] = []
        for seed in expected_seeds:
            path = raw_root / center / f"seed-{seed}" / "summary.jsonl"
            row = _load_object(path)
            if int(row.get("seed", -1)) != seed or row.get("center") != center:
                raise ValueError(f"summary identity mismatch: {path}")
            if row.get("certification_category") != "posthoc_theorem_event_verified":
                raise ValueError(f"unexpected certification category: {path}")
            rows.append(row)
            inputs.append(path)
        by_center[center] = rows

    metric_keys = (
        "cumulative_pseudo_regret",
        "theorem_rhs_observable",
        "rhs_divided_by_regret",
        "runtime_seconds",
        "certificate_seconds",
        "cg_seconds",
        "Lambda_algorithmic_exact",
        "Lambda_algorithmic_observable_upper",
        "final_chi_exact",
        "final_chi_bar",
        "final_psi_exact",
        "final_psi_bar",
        "final_F_exact_prior",
        "final_F_bar_prior",
        "final_gamma_exact",
        "final_gamma_hat",
    )
    policies: dict[str, Any] = {}
    for center, rows in by_center.items():
        policies[center] = {
            "run_count": len(rows),
            "seeds": list(expected_seeds),
            "certification_category": "posthoc_theorem_event_verified",
            "mathematical_schedule_status": "all_theorem_schedules_predictable_pre_action",
            "all_observed_theorem_event_checks_hold": all(
                bool(row["all_observed_theorem_event_checks_hold"]) for row in rows
            ),
            "certificate_failure_count": sum(
                int(row["certificate_failure_count"]) for row in rows
            ),
            "optimism_violation_count": sum(
                int(row["optimism_violation_count"]) for row in rows
            ),
            "confidence_violation_count": sum(
                int(row["confidence_violation_count"]) for row in rows
            ),
            "metrics": {key: _metric_interval(rows, key) for key in metric_keys},
            "seed_level": [
                {
                    "seed": int(row["seed"]),
                    **{key: row[key] for key in metric_keys},
                    "certificate_failure_count": int(row["certificate_failure_count"]),
                    "optimism_violation_count": int(row["optimism_violation_count"]),
                    "confidence_violation_count": int(row["confidence_violation_count"]),
                }
                for row in rows
            ],
        }

    paired_metrics: dict[str, Any] = {}
    for key in ("cumulative_pseudo_regret", "theorem_rhs_observable", "runtime_seconds"):
        differences = [
            float(corrected[key]) - float(original[key])
            for original, corrected in zip(
                by_center["original"], by_center["corrected"], strict=True
            )
        ]
        paired_metrics[key] = student_t_interval(differences)

    input_records = [
        {"path": str(path), "sha256": _sha256(path)}
        for path in sorted(set(inputs), key=lambda item: str(item))
    ]
    input_set_sha256 = hashlib.sha256(
        canonical_json(input_records).encode("ascii")
    ).hexdigest()
    grid_results = []
    for group in grid_aggregate.get("groups", []):
        horizons = group.get("horizons", [])
        if not horizons:
            raise ValueError("controlled-grid group has no horizon result")
        final = horizons[-1]
        metrics = final.get("metrics", {})
        grid_results.append(
            {
                "method": group.get("method"),
                "run_count": group.get("run_count"),
                "hyperparameters": group.get("hyperparameters"),
                "horizon": final.get("horizon"),
                "cumulative_pseudo_regret": metrics.get(
                    "cumulative_pseudo_regret"
                ),
                "theorem_rhs_observable": metrics.get("theorem_rhs_observable"),
                "certificate_failure_count": metrics.get(
                    "cumulative_certificate_failure_count"
                ),
            }
        )
    return {
        "schema_version": 1,
        "experiment": "certified_tanh",
        "profile": "full",
        "seed_set": "evaluation",
        "evaluation_seed_count": len(expected_seeds),
        "policies": policies,
        "paired_corrected_minus_original": paired_metrics,
        "controlled_grid_execution_status": config["controlled_grid"][
            "execution_status"
        ],
        "controlled_grid_seed_set": "tuning",
        "controlled_grid_results": grid_results,
        "numerical_semantics": (
            "Schedules are predictable; float64 residuals are point computations, "
            "so the executed rows are post-hoc theorem-event verified rather than "
            "verified-enclosure theorem certified."
        ),
        "inputs": input_records,
        "input_set_sha256": input_set_sha256,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--aggregate", type=Path, default=DEFAULT_AGGREGATE)
    parser.add_argument(
        "--grid-aggregate", type=Path, default=DEFAULT_GRID_AGGREGATE
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    artifact = build_artifact(
        config_path=args.config,
        raw_root=args.raw_root,
        aggregate_path=args.aggregate,
        grid_aggregate_path=args.grid_aggregate,
    )
    output, sidecar = write_aggregate_with_provenance(artifact, args.output)
    print(json.dumps({"output": str(output), "sidecar": str(sidecar)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_artifact", "main"]
