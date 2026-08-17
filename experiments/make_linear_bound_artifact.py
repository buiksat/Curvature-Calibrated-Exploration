"""Derive horizon-wise linear regret-bound diagnostics from a strict aggregate."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .artifact_utils import write_aggregate_with_provenance
from .linear_environment import (
    ACTION_COUNT,
    LinearBanditEnvironment,
    enumerate_rademacher_contexts,
)
from .logging_utils import canonical_json


DEFAULT_SOURCE = Path("results/derived/linear_audit_full.json")
DEFAULT_CERTIFICATION = Path("results/derived/certification_audit.json")
DEFAULT_OUTPUT = Path("results/derived/linear_bound_metrics.json")
DEFAULT_TABLE = Path("paper/tables/linear_bound_ratios.tex")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("linear aggregate must be a JSON object")
    required = {
        "event": "executed_policy_aggregate",
        "all_groups_complete": True,
        "all_runs_executed_policy": True,
        "all_seed_provenance_disjoint": True,
        "profiles": ["full"],
        "seed_sets": ["evaluation"],
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise ValueError(f"linear aggregate is not a strict full evaluation artifact: {key}")
    if value.get("experiments") != ["linear_audit"]:
        raise ValueError("source must contain only the linear_audit experiment")
    return value


def _load_certification(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("certification audit must be a JSON object")
    if value.get("event") != "linear_policy_certification_audit":
        raise ValueError("certification input is not a linear policy audit")
    return value


def _mean(metrics: Mapping[str, Any], name: str) -> float:
    stats = metrics.get(name)
    if not isinstance(stats, Mapping) or not isinstance(stats.get("mean"), (int, float)):
        raise ValueError(f"missing aggregate mean for {name}")
    return float(stats["mean"])


def _reward_support() -> dict[str, float | int]:
    environment = LinearBanditEnvironment(0)
    means = np.concatenate(
        [environment.mean_rewards(context) for context in enumerate_rademacher_contexts()]
    )
    per_context = np.stack(
        [environment.mean_rewards(context) for context in enumerate_rademacher_contexts()]
    )
    maximum_gap = float(np.max(np.max(per_context, axis=1) - np.min(per_context, axis=1)))
    return {
        "context_count": int(per_context.shape[0]),
        "action_count": ACTION_COUNT,
        "minimum_mean_reward": float(np.min(means)),
        "maximum_mean_reward": float(np.max(means)),
        "mean_reward_range": float(np.max(means) - np.min(means)),
        "maximum_instantaneous_pseudo_regret": maximum_gap,
    }


def _certification_lookup(
    certification: Mapping[str, Any] | None,
) -> dict[tuple[str, str], str]:
    if certification is None:
        return {}
    if certification.get("event") != "linear_policy_certification_audit":
        raise ValueError("certification input is not a linear policy audit")
    policies = certification.get("policies")
    if not isinstance(policies, Sequence):
        raise ValueError("certification audit policies are malformed")
    lookup: dict[tuple[str, str], str] = {}
    for policy in policies:
        if not isinstance(policy, Mapping):
            continue
        key = (str(policy.get("comparison")), str(policy.get("method")))
        category = policy.get("certification_category")
        if not isinstance(category, str):
            raise ValueError(f"certification category is missing for {key}")
        lookup[key] = category
    return lookup


def derive(
    source: Mapping[str, Any],
    certification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    groups = source.get("groups")
    if not isinstance(groups, Sequence):
        raise ValueError("linear aggregate groups are malformed")
    certification_by_policy = _certification_lookup(certification)
    rows: list[dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, Mapping):
            continue
        horizons = group.get("horizons")
        if not isinstance(horizons, Sequence):
            continue
        for horizon_record in horizons:
            if not isinstance(horizon_record, Mapping):
                continue
            metrics = horizon_record.get("metrics")
            if not isinstance(metrics, Mapping):
                raise ValueError("linear horizon record has no metrics")
            horizon = int(horizon_record["horizon"])
            regret = _mean(metrics, "cumulative_pseudo_regret")
            theorem_rhs = _mean(metrics, "theorem_rhs")
            comparison = str(group.get("comparison"))
            method = str(group.get("method"))
            category = certification_by_policy.get((comparison, method), "not_supplied")
            rows.append(
                {
                    "comparison": comparison,
                    "method": method,
                    "horizon": horizon,
                    "certification_category": category,
                    "rhs_certification_status": (
                        "conditional_theorem_bound_on_ex_ante_schedules"
                        if category == "ex_ante_theorem_certified"
                        else "posthoc_decomposition_rhs"
                        if category == "posthoc_theorem_event_verified"
                        else "certification_not_supplied"
                    ),
                    "R_T": regret,
                    "theorem_rhs": theorem_rhs,
                    "R_T_over_T": regret / horizon,
                    "theorem_rhs_over_T": theorem_rhs / horizon,
                    "theorem_rhs_over_R_T": theorem_rhs / regret,
                }
            )
    if not rows:
        raise ValueError("linear aggregate contains no horizon records")
    rows.sort(key=lambda row: (row["comparison"], row["method"], row["horizon"]))

    reward_support = _reward_support()
    maximum_gap = float(reward_support["maximum_instantaneous_pseudo_regret"])
    for row in rows:
        maximum_possible_regret = maximum_gap * int(row["horizon"])
        row["maximum_possible_pseudo_regret"] = maximum_possible_regret
        row["rhs_exceeds_maximum_possible_pseudo_regret"] = bool(
            float(row["theorem_rhs"]) > maximum_possible_regret
        )

    return {
        "schema_version": 1,
        "event": "linear_bound_horizon_audit",
        "experiment": "linear_audit",
        "interpretation": (
            "Finite-horizon trajectory diagnostics; decreasing normalized RHS is not "
            "evidence of asymptotic sublinearity. Rows whose policy category is "
            "posthoc_theorem_event_verified report a decomposition RHS, not a "
            "rigorously certified theorem bound."
        ),
        "numerical_nonavacuity_definition": (
            "RHS is nonvacuous only if it does not exceed horizon times the exact "
            "maximum one-round pseudo-regret on the finite context support."
        ),
        "reward_support": reward_support,
        "all_reported_bounds_numerically_nonavacuous": not any(
            bool(row["rhs_exceeds_maximum_possible_pseudo_regret"]) for row in rows
        ),
        "all_reported_bounds_numerically_vacuous": all(
            bool(row["rhs_exceeds_maximum_possible_pseudo_regret"]) for row in rows
        ),
        "all_reported_rhs_numerically_nonavacuous": not any(
            bool(row["rhs_exceeds_maximum_possible_pseudo_regret"]) for row in rows
        ),
        "all_reported_rhs_numerically_vacuous": all(
            bool(row["rhs_exceeds_maximum_possible_pseudo_regret"]) for row in rows
        ),
        "rows": rows,
    }


def _latex_table(artifact: Mapping[str, Any]) -> str:
    fixed = [
        row
        for row in artifact["rows"]
        if row["comparison"] == "fixed_reference"
    ]
    horizons = sorted({int(row["horizon"]) for row in fixed})
    methods = sorted({str(row["method"]) for row in fixed})
    aliases = {
        "cg_full": "full CG",
        "dense_full": "full dense",
        "diagonal": "diagonal",
        "lanczos_ritz": "Lanczos--Ritz",
        "rescaled_subsample": "subsample 64",
        "stale_refresh": "refresh 20",
        "unrescaled_window": "window 64",
    }
    lookup = {
        (str(row["method"]), int(row["horizon"])): float(row["theorem_rhs_over_R_T"])
        for row in fixed
    }
    column_spec = "l" + "r" * len(horizons)
    lines = [
        "% Auto-generated by experiments.make_linear_bound_artifact; do not edit.",
        rf"\begin{{tabular}}{{@{{}}{column_spec}@{{}}}}",
        r"\toprule",
        "Method & " + " & ".join(rf"$T={horizon}$" for horizon in horizons) + r" \\",
        r"\midrule",
    ]
    for method in methods:
        values = " & ".join(f"{lookup[(method, horizon)]:.1f}" for horizon in horizons)
        lines.append(f"{aliases.get(method, method.replace('_', ' '))} & {values}" + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    return "\n".join(lines)


def generate(
    source_path: Path = DEFAULT_SOURCE,
    certification_path: Path = DEFAULT_CERTIFICATION,
    output_path: Path = DEFAULT_OUTPUT,
    table_path: Path = DEFAULT_TABLE,
) -> dict[str, Any]:
    source = _load(source_path)
    certification = _load_certification(certification_path)
    artifact = derive(source, certification)
    artifact["source"] = {
        "path": source_path.as_posix(),
        "sha256": _sha256(source_path),
        "raw_input_set_sha256": source.get("input_set_sha256"),
    }
    artifact["certification_audit"] = {
        "path": certification_path.as_posix(),
        "sha256": _sha256(certification_path),
    }
    inputs = sorted(
        [
            {"path": source_path.as_posix(), "sha256": _sha256(source_path)},
            {
                "path": certification_path.as_posix(),
                "sha256": _sha256(certification_path),
            },
        ],
        key=lambda item: item["path"],
    )
    artifact["inputs"] = inputs
    artifact["input_set_sha256"] = hashlib.sha256(
        canonical_json(inputs).encode("ascii")
    ).hexdigest()
    _, sidecar_path = write_aggregate_with_provenance(artifact, output_path)
    table_path.parent.mkdir(parents=True, exist_ok=True)
    table_path.write_text(_latex_table(artifact), encoding="ascii")
    table_sidecar_path = table_path.with_suffix(table_path.suffix + ".provenance.json")
    table_sidecar = {
        "schema_version": 1,
        "artifact": table_path.as_posix(),
        "artifact_sha256": _sha256(table_path),
        "inputs": [
            {
                "path": output_path.as_posix(),
                "sha256": _sha256(output_path),
            }
        ],
    }
    table_sidecar["input_set_sha256"] = hashlib.sha256(
        canonical_json(table_sidecar["inputs"]).encode("ascii")
    ).hexdigest()
    table_sidecar_path.write_text(
        json.dumps(table_sidecar, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return {
        "artifact": output_path.as_posix(),
        "provenance": sidecar_path.as_posix(),
        "table": table_path.as_posix(),
        "table_provenance": table_sidecar_path.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--certification", type=Path, default=DEFAULT_CERTIFICATION
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    args = parser.parse_args()
    print(
        json.dumps(
            generate(args.source, args.certification, args.output, args.table),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
