"""Aggregate controlled-gap runs and build validation artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from .artifact_utils import (
    input_set_sha256,
    sha256_file,
    validate_sha256_sidecar,
    write_json_artifact,
    write_sha256_sidecar,
)
from .config import config_digest, get_seed_set, load_config
from .logging_utils import canonical_json
from .run_gap_dependent_validation import (
    METHODS,
    SMOKE_EVIDENCE_SCOPE,
    validate_study_config,
)


DISPLAY_NAMES = {
    "exact_full": "Exact full",
    "full_cg": "Full CG",
    "rank_truncation": "Rank truncation",
    "diagonal": "Diagonal",
    "greedy": "Greedy",
}


def _gap_token(gap: float) -> str:
    return f"gap-{gap:.8g}".replace(".", "p")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _interval(values: Sequence[float]) -> dict[str, float | int]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("interval input must be a nonempty finite vector")
    mean = float(np.mean(array))
    if array.size == 1:
        low = high = mean
    else:
        standard_error = float(np.std(array, ddof=1) / np.sqrt(array.size))
        half_width = float(stats.t.ppf(0.975, array.size - 1) * standard_error)
        low, high = mean - half_width, mean + half_width
    return {"mean": mean, "ci95_low": low, "ci95_high": high, "n": int(array.size)}


def _load_run(
    directory: Path,
    *,
    config: Mapping[str, Any],
    profile: str,
    seed: int,
    gap: float,
    method: str,
) -> tuple[dict[str, Any], dict[str, np.ndarray[Any, Any]], list[Path]]:
    manifest_path = directory / "manifest.json"
    summary_path = directory / "summary.json"
    rounds_path = directory / "rounds.npz"
    paths = [manifest_path, summary_path, rounds_path]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"missing run artifact {path}")
        validate_sha256_sidecar(path)
    manifest = _load_json(manifest_path)
    summary = _load_json(summary_path)
    expected_identity = {
        "experiment": "gap_dependent_validation",
        "profile": profile,
        "seed_set": "evaluation",
        "seed": seed,
        "controlled_gap": gap,
        "method": method,
        "config_digest": config_digest(config),
    }
    for key, expected in expected_identity.items():
        if manifest.get(key) != expected:
            raise ValueError(f"manifest identity mismatch for {directory}: {key}")
    expected_scope = (
        SMOKE_EVIDENCE_SCOPE
        if profile == "smoke"
        else "full evaluation; eligible for paper reporting after artifact validation"
    )
    if manifest.get("evidence_scope") != expected_scope:
        raise ValueError(f"run manifest evidence scope mismatch: {manifest_path}")
    if manifest.get("deterministic_scientific_payload") is not True:
        raise ValueError(
            f"run manifest lacks deterministic-payload provenance: {manifest_path}"
        )
    timestamp = manifest.get("timestamp_utc")
    if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
        raise ValueError(f"run manifest lacks a UTC timestamp: {manifest_path}")
    provenance = manifest.get("provenance")
    required_provenance = {
        "git_revision",
        "git_dirty",
        "package_versions",
        "hardware",
        "python",
        "source_artifact_hashes",
    }
    if not isinstance(provenance, Mapping) or not required_provenance <= set(
        provenance
    ):
        raise ValueError(f"run manifest has incomplete provenance: {manifest_path}")
    source_hashes = provenance["source_artifact_hashes"]
    if not isinstance(source_hashes, Mapping) or not source_hashes:
        raise ValueError(f"run manifest has no source hashes: {manifest_path}")
    repository = Path(__file__).resolve().parents[1]
    for source, expected_hash in source_hashes.items():
        source_path = repository / str(source)
        if not source_path.is_file() or sha256_file(source_path) != expected_hash:
            raise ValueError(f"source hash mismatch for {source} in {manifest_path}")
    if manifest.get("rounds_sha256") != sha256_file(rounds_path):
        raise ValueError(f"round archive hash mismatch: {rounds_path}")
    if manifest.get("summary_sha256") != sha256_file(summary_path):
        raise ValueError(f"summary hash mismatch: {summary_path}")
    if summary.get("method") != method or summary.get("controlled_gap") != gap:
        raise ValueError(f"summary identity mismatch for {directory}")
    with np.load(rounds_path, allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    required = {
        "cumulative_pseudo_regret",
        "gap_free_rhs",
        "gap_dependent_rhs",
        "action_disagreement",
        "maximum_linearization_error",
        "gap_corollary_applicable",
    }
    if not required <= set(arrays):
        raise ValueError(f"round archive lacks required fields: {rounds_path}")
    rounds = int(config["rounds"])
    if any(arrays[name].shape != (rounds,) for name in required):
        raise ValueError(f"round archive has an invalid horizon: {rounds_path}")
    checks = (
        ("terminal_pseudo_regret", "cumulative_pseudo_regret"),
        ("terminal_gap_free_rhs", "gap_free_rhs"),
        ("terminal_gap_dependent_rhs", "gap_dependent_rhs"),
    )
    for summary_key, array_key in checks:
        if not np.isclose(
            float(summary[summary_key]), float(arrays[array_key][-1]), rtol=0.0, atol=1e-12
        ):
            raise ValueError(f"summary disagrees with round archive: {directory}")
    expanded_paths = paths + [path.with_name(path.name + ".sha256") for path in paths]
    return summary, arrays, expanded_paths


def aggregate_runs(
    config: Mapping[str, Any],
    *,
    profile: str,
    raw_root: Path,
) -> dict[str, Any]:
    validate_study_config(config)
    phase_root = raw_root / profile / "evaluation"
    grid_manifest_path = phase_root / "manifest.json"
    validate_sha256_sidecar(grid_manifest_path)
    grid_manifest = _load_json(grid_manifest_path)
    seeds = tuple(get_seed_set(config, "evaluation"))
    gaps = tuple(float(value) for value in config["gaps"])
    expected_run_count = len(seeds) * len(gaps) * len(METHODS)
    expected_manifest = {
        "experiment": "gap_dependent_validation",
        "profile": profile,
        "seed_set": "evaluation",
        "config_digest": config_digest(config),
        "seeds": list(seeds),
        "gaps": list(gaps),
        "methods": list(METHODS),
        "run_count": expected_run_count,
        "deterministic_scientific_payload": True,
        "evidence_scope": (
            SMOKE_EVIDENCE_SCOPE
            if profile == "smoke"
            else "full evaluation; eligible for paper reporting after artifact validation"
        ),
    }
    for key, expected in expected_manifest.items():
        if grid_manifest.get(key) != expected:
            raise ValueError(f"grid manifest mismatch: {key}")

    records: dict[tuple[float, str], list[tuple[int, dict[str, Any]]]] = {
        (gap, method): [] for gap in gaps for method in METHODS
    }
    inputs = [
        {"path": grid_manifest_path.as_posix(), "sha256": sha256_file(grid_manifest_path)},
        {
            "path": grid_manifest_path.with_name("manifest.json.sha256").as_posix(),
            "sha256": sha256_file(grid_manifest_path.with_name("manifest.json.sha256")),
        },
    ]
    validated_run_count = 0
    for gap in gaps:
        for seed in seeds:
            stream_hashes: set[str] = set()
            for method in METHODS:
                directory = (
                    phase_root / _gap_token(gap) / method / f"seed-{seed}"
                )
                summary, _, run_paths = _load_run(
                    directory,
                    config=config,
                    profile=profile,
                    seed=seed,
                    gap=gap,
                    method=method,
                )
                manifest = _load_json(directory / "manifest.json")
                stream_hashes.add(str(manifest["stream_sha256"]))
                records[(gap, method)].append((seed, summary))
                inputs.extend(
                    {"path": path.as_posix(), "sha256": sha256_file(path)}
                    for path in run_paths
                )
                validated_run_count += 1
            if len(stream_hashes) != 1:
                raise ValueError(f"methods do not share one stream for gap={gap}, seed={seed}")

    groups: list[dict[str, Any]] = []
    for gap in gaps:
        for method in METHODS:
            rows = sorted(records[(gap, method)], key=lambda item: item[0])
            if tuple(seed for seed, _ in rows) != seeds:
                raise ValueError(f"incomplete seed coverage for gap={gap}, method={method}")
            summaries = [summary for _, summary in rows]
            checks = [summary["premise_checks"] for summary in summaries]
            theorem_method = method in {"exact_full", "full_cg"}
            applicable = [
                bool(check["gap_corollary_applicable_all_rounds"])
                for check in checks
            ]
            horizon_metrics = []
            for horizon in config["horizons"]:
                snapshots = [
                    next(
                        item
                        for item in summary["horizon_metrics"]
                        if int(item["horizon"]) == int(horizon)
                    )
                    for summary in summaries
                ]
                horizon_metrics.append(
                    {
                        "horizon": int(horizon),
                        "cumulative_pseudo_regret": _interval(
                            [
                                float(snapshot["cumulative_pseudo_regret"])
                                for snapshot in snapshots
                            ]
                        ),
                        "gap_free_rhs": _interval(
                            [float(snapshot["gap_free_rhs"]) for snapshot in snapshots]
                        ),
                        "gap_dependent_rhs": _interval(
                            [
                                float(snapshot["gap_dependent_rhs"])
                                for snapshot in snapshots
                            ]
                        ),
                        "action_disagreement_rate": _interval(
                            [
                                float(snapshot["action_disagreement_rate"])
                                for snapshot in snapshots
                            ]
                        ),
                    }
                )
            groups.append(
                {
                    "controlled_gap": gap,
                    "method": method,
                    "run_count": len(rows),
                    "horizon_metrics": horizon_metrics,
                    "terminal_pseudo_regret": _interval(
                        [float(summary["terminal_pseudo_regret"]) for summary in summaries]
                    ),
                    "terminal_gap_free_rhs": _interval(
                        [float(summary["terminal_gap_free_rhs"]) for summary in summaries]
                    ),
                    "terminal_gap_dependent_rhs": _interval(
                        [
                            float(summary["terminal_gap_dependent_rhs"])
                            for summary in summaries
                        ]
                    ),
                    "action_disagreement_rate": _interval(
                        [float(summary["action_disagreement_rate"]) for summary in summaries]
                    ),
                    "suboptimal_action_rate": _interval(
                        [float(summary["suboptimal_action_rate"]) for summary in summaries]
                    ),
                    "maximum_linearization_error": float(
                        max(float(summary["maximum_linearization_error"]) for summary in summaries)
                    ),
                    "minimum_realized_candidate_gap": float(
                        min(float(summary["minimum_realized_candidate_gap"]) for summary in summaries)
                    ),
                    "maximum_cg_energy_error": float(
                        max(float(summary["maximum_cg_energy_error"]) for summary in summaries)
                    ),
                    "controlled_gap_premise_pass": bool(
                        all(bool(check["controlled_positive_gap"]) for check in checks)
                    ),
                    "linearization_premise_pass": bool(
                        all(
                            bool(check["linearization_error_le_gap_quarter"])
                            for check in checks
                        )
                    ),
                    "confidence_event_pass": bool(
                        all(
                            bool(check["simultaneous_confidence_event_observed"])
                            for check in checks
                        )
                    ),
                    "exact_current_operator_method": theorem_method,
                    "gap_corollary_applicable_run_count": int(sum(applicable)),
                    "gap_corollary_applicable_all_runs": bool(
                        theorem_method and all(applicable)
                    ),
                    "gap_free_rhs_dominates_all_runs": bool(
                        all(bool(check["gap_free_rhs_dominates_regret"]) for check in checks)
                    ),
                    "gap_dependent_rhs_dominates_all_runs": bool(
                        all(
                            bool(check["gap_dependent_rhs_dominates_regret"])
                            for check in checks
                        )
                    ),
                }
            )

    paired: list[dict[str, Any]] = []
    for gap in gaps:
        exact = {
            seed: float(summary["terminal_pseudo_regret"])
            for seed, summary in records[(gap, "exact_full")]
        }
        for method in METHODS[1:]:
            differences = [
                float(summary["terminal_pseudo_regret"]) - exact[seed]
                for seed, summary in records[(gap, method)]
            ]
            paired.append(
                {
                    "controlled_gap": gap,
                    "method": method,
                    "reference_method": "exact_full",
                    "terminal_regret_difference": _interval(differences),
                }
            )

    normalized_inputs = sorted(inputs, key=lambda item: item["path"])
    return {
        "schema_version": 1,
        "experiment": "gap_dependent_validation",
        "profile": profile,
        "config_digest": config_digest(config),
        "config": dict(config),
        "evaluation_seeds": list(seeds),
        "tuning_seeds": list(get_seed_set(config, "tuning")),
        "tuning_evaluation_seeds_disjoint": bool(
            set(seeds).isdisjoint(get_seed_set(config, "tuning"))
        ),
        "expected_run_count": expected_run_count,
        "validated_run_count": validated_run_count,
        "groups": groups,
        "paired_regret_differences": paired,
        "input_set_sha256": input_set_sha256(normalized_inputs),
        "raw_inputs": normalized_inputs,
        "evidence_scope": (
            SMOKE_EVIDENCE_SCOPE
            if profile == "smoke"
            else "full evaluation; eligible for paper reporting after artifact validation"
        ),
        "interpretation": (
            "The exact/full-CG rows validate the recorded premises. Rank, diagonal, "
            "and greedy rows are decision diagnostics outside the exact-current premise."
        ),
    }


def _group_lookup(report: Mapping[str, Any]) -> dict[tuple[float, str], Mapping[str, Any]]:
    return {
        (float(group["controlled_gap"]), str(group["method"])): group
        for group in report["groups"]
    }


def make_figure(report: Mapping[str, Any], output: Path) -> None:
    groups = _group_lookup(report)
    gaps = tuple(float(value) for value in report["config"]["gaps"])
    figure, axes = plt.subplots(1, 3, figsize=(12.0, 3.7), constrained_layout=True)
    for method in METHODS:
        means = np.asarray(
            [groups[(gap, method)]["terminal_pseudo_regret"]["mean"] for gap in gaps]
        )
        lows = np.asarray(
            [groups[(gap, method)]["terminal_pseudo_regret"]["ci95_low"] for gap in gaps]
        )
        highs = np.asarray(
            [groups[(gap, method)]["terminal_pseudo_regret"]["ci95_high"] for gap in gaps]
        )
        axes[0].plot(gaps, means, marker="o", label=DISPLAY_NAMES[method])
        axes[0].fill_between(gaps, lows, highs, alpha=0.12)
        disagreement = [
            groups[(gap, method)]["action_disagreement_rate"]["mean"]
            for gap in gaps
        ]
        axes[2].plot(gaps, disagreement, marker="o", label=DISPLAY_NAMES[method])

    exact = [groups[(gap, "exact_full")] for gap in gaps]
    axes[1].plot(
        gaps,
        [group["terminal_pseudo_regret"]["mean"] for group in exact],
        marker="o",
        label="Regret",
    )
    axes[1].plot(
        gaps,
        [group["terminal_gap_free_rhs"]["mean"] for group in exact],
        marker="s",
        label="Gap-free RHS",
    )
    axes[1].plot(
        gaps,
        [group["terminal_gap_dependent_rhs"]["mean"] for group in exact],
        marker="^",
        label="Gap-dependent RHS",
    )
    axes[0].set(xlabel="Controlled gap", ylabel="Terminal pseudo-regret")
    axes[1].set(xlabel="Controlled gap", ylabel="Exact-full value", yscale="log")
    axes[2].set(xlabel="Controlled gap", ylabel="Action disagreement with exact")
    axes[0].legend(fontsize=7)
    axes[1].legend(fontsize=7)
    axes[2].set_ylim(bottom=0.0)
    for axis in axes:
        axis.grid(alpha=0.2)
    if report["profile"] == "smoke":
        figure.suptitle(
            SMOKE_EVIDENCE_SCOPE,
            color="#9b2226",
            fontsize=10,
            fontweight="bold",
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output,
        metadata={
            "Creator": "gap_dependent_validation",
            "CreationDate": None,
            "ModDate": None,
            "Subject": str(report["evidence_scope"]),
        },
    )
    plt.close(figure)
    write_sha256_sidecar(output)


def make_table(report: Mapping[str, Any], output: Path) -> None:
    lines = [
        r"\begin{tabular}{llrrrrl}",
        r"\toprule",
    ]
    if report["profile"] == "smoke":
        lines.extend(
            [
                r"\multicolumn{7}{c}{\textbf{SMOKE ONLY --- not main-paper evidence}} \\",
                r"\midrule",
            ]
        )
    lines.extend(
        [
            r"Gap & Method & Regret & Gap-free RHS & Gap RHS & Disagree. & Premise \\",
            r"\midrule",
        ]
    )
    for group in report["groups"]:
        method = str(group["method"])
        if not bool(group["exact_current_operator_method"]):
            premise = "N/A"
        elif bool(group["gap_corollary_applicable_all_runs"]):
            premise = "PASS"
        else:
            premise = "FAIL"
        lines.append(
            f"{float(group['controlled_gap']):.2f} & {DISPLAY_NAMES[method]} & "
            f"{float(group['terminal_pseudo_regret']['mean']):.3f} & "
            f"{float(group['terminal_gap_free_rhs']['mean']):.1f} & "
            f"{float(group['terminal_gap_dependent_rhs']['mean']):.1f} & "
            f"{float(group['action_disagreement_rate']['mean']):.3f} & {premise} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="ascii")
    write_sha256_sidecar(output)


def _write_provenance(
    artifact: Path,
    *,
    aggregate: Path,
    config: Mapping[str, Any],
    profile: str,
) -> None:
    inputs = [{"path": aggregate.as_posix(), "sha256": sha256_file(aggregate)}]
    sidecar = artifact.with_name(artifact.name + ".provenance.json")
    write_json_artifact(
        sidecar,
        {
            "schema_version": 1,
            "artifact": artifact.as_posix(),
            "artifact_sha256": sha256_file(artifact),
            "inputs": inputs,
            "input_set_sha256": input_set_sha256(inputs),
            "generation_parameters": {
                "experiment": "gap_dependent_validation",
                "config_digest": config_digest(config),
                "profile": profile,
                "evidence_scope": (
                    SMOKE_EVIDENCE_SCOPE
                    if profile == "smoke"
                    else "full evaluation"
                ),
                "generator_source_sha256": sha256_file(Path(__file__)),
            },
        },
    )


def build_artifacts(
    config: Mapping[str, Any],
    *,
    profile: str,
    raw_root: Path,
    aggregate_path: Path,
    figure_path: Path,
    table_path: Path,
) -> dict[str, Any]:
    report = aggregate_runs(config, profile=profile, raw_root=raw_root)
    aggregate, _ = write_json_artifact(aggregate_path, report)
    make_figure(report, figure_path)
    make_table(report, table_path)
    for artifact in (figure_path, table_path):
        _write_provenance(
            artifact,
            aggregate=aggregate,
            config=config,
            profile=profile,
        )
    return {
        "aggregate": aggregate.as_posix(),
        "figure": figure_path.as_posix(),
        "table": table_path.as_posix(),
        "validated_run_count": report["validated_run_count"],
        "input_set_sha256": report["input_set_sha256"],
        "evidence_scope": report["evidence_scope"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--figure", type=Path, required=True)
    parser.add_argument("--table", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = load_config(args.config, profile=args.profile)
    result = build_artifacts(
        config,
        profile=args.profile,
        raw_root=args.raw_root,
        aggregate_path=args.aggregate,
        figure_path=args.figure,
        table_path=args.table,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "aggregate_runs",
    "build_artifacts",
    "make_figure",
    "make_table",
]
