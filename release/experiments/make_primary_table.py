"""Generate the compact main-paper executed-policy table from strict aggregates."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"aggregate must be a JSON object: {path}")
    required = {
        "event": "executed_policy_aggregate",
        "all_runs_executed_policy": True,
        "all_seed_provenance_disjoint": True,
        "profiles": ["full"],
        "seed_sets": ["evaluation"],
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise ValueError(f"{path} is not a strict full evaluation aggregate: {key}")
    return value


def _group(
    aggregate: Mapping[str, Any],
    *,
    method: str,
    comparison: str = "default",
    center: str | None = None,
) -> Mapping[str, Any]:
    matches = []
    groups = aggregate.get("groups", [])
    if not isinstance(groups, Sequence):
        raise ValueError("aggregate groups are malformed")
    for item in groups:
        if not isinstance(item, Mapping):
            continue
        variant = item.get("variant", {})
        variant = variant if isinstance(variant, Mapping) else {}
        if (
            item.get("method") == method
            and item.get("comparison") == comparison
            and (center is None or variant.get("center") == center)
        ):
            matches.append(item)
    if len(matches) != 1:
        raise ValueError(
            f"expected one group for method={method}, comparison={comparison}, "
            f"center={center}; found {len(matches)}"
        )
    return matches[0]


def _final_metrics(group: Mapping[str, Any]) -> Mapping[str, Any]:
    horizons = group.get("horizons", [])
    if not isinstance(horizons, Sequence) or not horizons:
        raise ValueError("aggregate group has no horizons")
    final = max(
        (item for item in horizons if isinstance(item, Mapping)),
        key=lambda item: int(item.get("horizon", 0)),
    )
    metrics = final.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError("final horizon has no metrics")
    return metrics


def _stats(metrics: Mapping[str, Any], *names: str) -> Mapping[str, Any]:
    for name in names:
        value = metrics.get(name)
        if isinstance(value, Mapping) and isinstance(value.get("mean"), (int, float)):
            return value
    raise ValueError(f"none of the required metrics are present: {names}")


def _estimate(stats: Mapping[str, Any], *, digits: int = 1) -> str:
    mean = float(stats["mean"])
    half = float(stats["ci95_half_width"])
    return f"{mean:.{digits}f} $\\pm$ {half:.{digits}f}"


def _number(stats: Mapping[str, Any], *, digits: int = 1) -> str:
    return f"{float(stats['mean']):.{digits}f}"


def _row(
    environment: str,
    policy: str,
    group: Mapping[str, Any],
    *,
    nonlinear: bool,
) -> str:
    final = _final_metrics(group)
    summary = group.get("summary_metrics", {})
    summary = summary if isinstance(summary, Mapping) else {}
    regret = _stats(final, "cumulative_pseudo_regret")
    violation = _stats(
        summary if nonlinear else final,
        "policy_optimism_violation_rate",
        "all_action_optimism_violation_rate",
        "optimism_violation_rate",
    )
    complexity = _stats(final, "Lambda_alg_T", "Lambda_alg_cumulative")
    transfer = _stats(
        final,
        "max_diagnostic_u_t" if nonlinear else "max_u_t",
        "u_t",
    )
    runtime = _stats(final, "runtime_seconds")
    if nonlinear:
        iterations = "--"
    else:
        iterations = _number(_stats(final, "mean_cg_iterations"), digits=1)
    violation_percent = 100.0 * float(violation["mean"])
    return (
        f"{environment} & {policy} & {_estimate(regret)} & "
        f"{violation_percent:.2f} & {_number(complexity)} & "
        f"{_number(transfer)} & {iterations} & {_number(runtime, digits=2)} \\\\"
    )


def generate(
    linear_path: Path,
    nonlinear_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    linear = _load(linear_path)
    nonlinear = _load(nonlinear_path)
    rows = [
        _row(
            "Linear",
            "full dense",
            _group(linear, method="dense_full", comparison="fixed_reference"),
            nonlinear=False,
        ),
        _row(
            "Linear",
            "full CG",
            _group(linear, method="cg_full", comparison="fixed_reference"),
            nonlinear=False,
        ),
        _row(
            "Linear",
            "diagonal",
            _group(linear, method="diagonal", comparison="fixed_reference"),
            nonlinear=False,
        ),
        _row(
            "Linear",
            "window 64",
            _group(
                linear,
                method="unrescaled_window",
                comparison="fixed_reference",
            ),
            nonlinear=False,
        ),
        _row(
            "Nonlinear",
            "frozen/orig.",
            _group(nonlinear, method="frozen_head", center="original"),
            nonlinear=True,
        ),
        _row(
            "Nonlinear",
            "mild/orig.",
            _group(nonlinear, method="mild", center="original"),
            nonlinear=True,
        ),
        _row(
            "Nonlinear",
            "mild/corr.",
            _group(nonlinear, method="mild", center="corrected"),
            nonlinear=True,
        ),
        _row(
            "Nonlinear",
            "aggr./corr.",
            _group(nonlinear, method="aggressive", center="corrected"),
            nonlinear=True,
        ),
    ]
    table = "\n".join(
        [
            "% Auto-generated by experiments.make_primary_table; do not edit.",
            r"\begin{tabular}{@{}llrrrrrr@{}}",
            r"\toprule",
            r"Environment & Policy & Regret & Viol. (\%) & $\Lambda_T^{\mathcal C}$ & $u_{\max}$ & CG it./action & Time (s) \\",
            r"\midrule",
            *rows[:4],
            r"\midrule",
            *rows[4:],
            r"\bottomrule",
            r"\end{tabular}",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(table, encoding="ascii")
    inputs = [
        {
            "path": str(path),
            "sha256": _sha256(path),
            "raw_input_set_sha256": aggregate.get("input_set_sha256"),
        }
        for path, aggregate in ((linear_path, linear), (nonlinear_path, nonlinear))
    ]
    sidecar = output_path.with_suffix(output_path.suffix + ".provenance.json")
    provenance = {
        "schema_version": 1,
        "artifact": str(output_path),
        "artifact_sha256": _sha256(output_path),
        "inputs": inputs,
        "selection": {
            "linear": "fixed-reference configurations at T=1000",
            "nonlinear": "predetermined default schedules at T=100 with post-hoc audits",
        },
    }
    sidecar.write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--linear", type=Path, default=Path("results/derived/linear_audit_full.json")
    )
    parser.add_argument(
        "--nonlinear",
        type=Path,
        default=Path("results/derived/nonlinear_drift_full.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("paper/tables/executed_policy_results.tex"),
    )
    args = parser.parse_args()
    print(json.dumps(generate(args.linear, args.nonlinear, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
