"""Run the preregistered coverage-matched curvature-operator study."""

from __future__ import annotations

import argparse
import math
import shutil
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import ttest_1samp

from .artifact_utils import (
    atomic_write_text,
    sha256_file,
    write_json_artifact,
    write_sha256_sidecar,
)
from .config import config_digest, load_config
from .curvature_phase_diagram import (
    SUPPORTED_METHODS,
    Cell,
    cells_from_config,
    generate_environment,
    run_common_trajectory_diagnostic,
    run_online_policy,
    validate_config as validate_phase_config,
)
from .logging_utils import canonical_json, collect_run_metadata
from .aggregate_results import student_t_interval


PROTOCOLS = (
    "identical_theoretical",
    "matched_95_coverage",
    "matched_mean_bonus",
)
REFERENCE = "current_full_ggn"


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> Path:
    payload = "".join(canonical_json(dict(record)) + "\n" for record in records)
    artifact = atomic_write_text(path, payload, encoding="ascii")
    write_sha256_sidecar(artifact)
    return artifact


def validate_study_config(config: Mapping[str, Any], *, full: bool) -> None:
    validate_phase_config(config, require_30_seeds=full)
    seed_sets = config["seed_sets"]
    tuning = tuple(int(seed) for seed in seed_sets["tuning"])
    evaluation = tuple(int(seed) for seed in seed_sets["evaluation"])
    if set(tuning) & set(evaluation):
        raise ValueError("tuning and evaluation seeds overlap")
    if tuple(int(seed) for seed in config["study"]["evaluation_seeds"]) != evaluation:
        raise ValueError("study evaluation seeds disagree with seed_sets")
    if full and (len(tuning) != 20 or len(evaluation) != 50):
        raise ValueError("full profile requires 20 tuning and 50 evaluation seeds")
    calibration = config.get("calibration")
    if not isinstance(calibration, Mapping):
        raise ValueError("calibration must be a mapping")
    if tuple(calibration.get("protocols", ())) != PROTOCOLS:
        raise ValueError(f"calibration protocols must be exactly {PROTOCOLS}")
    target = float(calibration.get("coverage_target", math.nan))
    if not 0.0 < target < 1.0:
        raise ValueError("coverage_target must lie in (0,1)")
    semantic = config.get("semantic_methods")
    if not isinstance(semantic, Mapping) or REFERENCE not in semantic:
        raise ValueError("semantic_methods must include current_full_ggn")
    if any(str(method) not in SUPPORTED_METHODS for method in semantic.values()):
        raise ValueError("semantic_methods contains an unknown operator")


def _semantic_methods(config: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple((str(name), str(method)) for name, method in config["semantic_methods"].items())


def calibrate(
    config: Mapping[str, Any], cells: Sequence[Cell]
) -> dict[str, Any]:
    required: dict[str, list[float]] = defaultdict(list)
    operator_bonus: dict[str, float] = defaultdict(float)
    reference_bonus: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    semantic_methods = _semantic_methods(config)
    tuning_seeds = tuple(int(seed) for seed in config["seed_sets"]["tuning"])

    for cell in cells:
        for seed in tuning_seeds:
            environment = generate_environment(config, cell, seed)
            baseline = run_online_policy(
                config,
                cell,
                seed,
                "exact_full",
                environment=environment,
            )
            for semantic_name, underlying in semantic_methods:
                diagnostic = run_common_trajectory_diagnostic(
                    config,
                    cell,
                    seed,
                    underlying,
                    baseline,
                    environment=environment,
                )
                for record in diagnostic.rounds:
                    required[semantic_name].extend(
                        float(value)
                        for value in record["coverage_required_multipliers"]
                    )
                    operator_bonus[semantic_name] += float(
                        record["average_bonus_magnitude"]
                    )
                    reference_bonus[semantic_name] += float(
                        record["reference_average_bonus_magnitude"]
                    )
                    counts[semantic_name] += 1

    target = float(config["calibration"]["coverage_target"])
    multipliers: dict[str, dict[str, float]] = {protocol: {} for protocol in PROTOCOLS}
    diagnostics: dict[str, Any] = {}
    for semantic_name, _ in semantic_methods:
        values = np.asarray(required[semantic_name], dtype=np.float64)
        if values.size == 0 or not np.all(np.isfinite(values)):
            raise ValueError(f"invalid coverage calibration values for {semantic_name}")
        coverage_multiplier = max(
            float(np.quantile(values, target, method="higher")), 1e-12
        )
        bonus_multiplier = reference_bonus[semantic_name] / operator_bonus[semantic_name]
        if not math.isfinite(bonus_multiplier) or bonus_multiplier <= 0.0:
            raise ValueError(f"invalid bonus calibration for {semantic_name}")
        multipliers["identical_theoretical"][semantic_name] = 1.0
        multipliers["matched_95_coverage"][semantic_name] = coverage_multiplier
        multipliers["matched_mean_bonus"][semantic_name] = bonus_multiplier
        diagnostics[semantic_name] = {
            "prediction_count": int(values.size),
            "coverage_multiplier": coverage_multiplier,
            "coverage_at_multiplier": float(np.mean(values <= coverage_multiplier)),
            "operator_mean_base_bonus": operator_bonus[semantic_name] / counts[semantic_name],
            "reference_mean_base_bonus": reference_bonus[semantic_name] / counts[semantic_name],
            "mean_bonus_multiplier": bonus_multiplier,
        }
    return {
        "schema_version": 1,
        "event": "coverage_matched_operator_selection",
        "selection_phase": "tuning_common_trajectory_only",
        "tuning_seeds": list(tuning_seeds),
        "evaluation_seeds_inspected": False,
        "coverage_target": target,
        "pooling": config["calibration"]["pooling"],
        "multipliers": multipliers,
        "diagnostics": diagnostics,
        "fixed_feature_identity": (
            "current_full_ggn and historical_frozen_gram are algebraically identical "
            "in this fixed-feature linear environment; separate labels audit the protocol"
        ),
    }


def _holm_adjust(p_values: Sequence[float]) -> list[float]:
    count = len(p_values)
    order = sorted(range(count), key=lambda index: p_values[index])
    adjusted = [1.0] * count
    running = 0.0
    for rank, index in enumerate(order):
        candidate = min(1.0, (count - rank) * float(p_values[index]))
        running = max(running, candidate)
        adjusted[index] = running
    return adjusted


def aggregate(
    summaries: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for summary in summaries:
        grouped[
            (
                str(summary["calibration_protocol"]),
                str(summary["cell_id"]),
                str(summary["semantic_method"]),
            )
        ].append(summary)

    aggregates: list[dict[str, Any]] = []
    metric_names = (
        "cumulative_pseudo_regret",
        "empirical_coverage_all_actions",
        "average_bonus_magnitude",
        "width_spearman_mean",
        "top_action_disagreement_rate",
        "normalized_margin_distortion_abs_mean",
        "reference_leading_alignment_mean",
        "reference_discarded_alignment_mean",
    )
    for (protocol, cell_id, method), records in sorted(grouped.items()):
        aggregate_record: dict[str, Any] = {
            "protocol": protocol,
            "cell_id": cell_id,
            "semantic_method": method,
            "underlying_method": records[0]["underlying_method"],
            "seed_count": len(records),
            "seeds": sorted(int(record["seed"]) for record in records),
            "calibration_multiplier": records[0]["calibration_multiplier"],
        }
        for metric in metric_names:
            aggregate_record[metric] = student_t_interval(
                float(record[metric]) for record in records
            )
        aggregates.append(aggregate_record)

    comparisons: list[dict[str, Any]] = []
    p_values: list[float] = []
    for protocol, cell_id, method in sorted(grouped):
        if method == REFERENCE:
            continue
        method_by_seed = {int(row["seed"]): row for row in grouped[(protocol, cell_id, method)]}
        reference_by_seed = {
            int(row["seed"]): row for row in grouped[(protocol, cell_id, REFERENCE)]
        }
        if set(method_by_seed) != set(reference_by_seed):
            raise ValueError("paired comparison seed coverage mismatch")
        differences = np.asarray(
            [
                float(method_by_seed[seed]["cumulative_pseudo_regret"])
                - float(reference_by_seed[seed]["cumulative_pseudo_regret"])
                for seed in sorted(method_by_seed)
            ],
            dtype=np.float64,
        )
        if np.all(differences == differences[0]):
            p_value = 1.0 if differences[0] == 0.0 else 0.0
        else:
            p_value = float(ttest_1samp(differences, 0.0).pvalue)
        p_values.append(p_value)
        comparisons.append(
            {
                "protocol": protocol,
                "cell_id": cell_id,
                "semantic_method": method,
                "reference_method": REFERENCE,
                "difference": "method_minus_current_full_ggn_regret",
                "interval": student_t_interval(differences.tolist()),
                "raw_two_sided_p_value": p_value,
                "test": "two_sided_paired_student_t_on_seed_level_differences",
                "zero_variance_rule": (
                    "p=1 for an identically zero difference; p=0 for a constant "
                    "nonzero difference"
                ),
                "seeds": sorted(method_by_seed),
                "causal_operator_interpretation": False,
            }
        )
    adjusted = _holm_adjust(p_values)
    for record, adjusted_p in zip(comparisons, adjusted, strict=True):
        record["holm_adjusted_p_value"] = adjusted_p
        record["holm_family"] = "all_prespecified_protocol_cell_surrogate_comparisons"
        record["familywise_alpha"] = 0.05
        mean = float(record["interval"]["mean"])
        if adjusted_p < 0.05:
            record["classification"] = (
                "surrogate_lower_regret" if mean < 0.0 else "current_full_lower_regret"
            )
        else:
            record["classification"] = "unresolved"
    return aggregates, comparisons


def run_study(
    config: Mapping[str, Any], output_root: str | Path, *, overwrite: bool = False
) -> dict[str, Any]:
    validate_study_config(config, full=len(config["seed_sets"]["evaluation"]) == 50)
    destination = Path(output_root)
    if destination.exists() and overwrite:
        shutil.rmtree(destination)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    cells = cells_from_config(config)
    selection = calibrate(config, cells)
    selection["config_digest"] = config_digest(dict(config))
    selection_path, _ = write_json_artifact(destination / "selection.json", selection)
    selection_sha256 = sha256_file(selection_path)

    summaries: list[dict[str, Any]] = []
    rounds: list[dict[str, Any]] = []
    started = time.perf_counter()
    for cell in cells:
        for seed in (int(value) for value in config["seed_sets"]["evaluation"]):
            environment = generate_environment(config, cell, seed)
            for protocol in PROTOCOLS:
                for semantic_name, underlying in _semantic_methods(config):
                    multiplier = float(selection["multipliers"][protocol][semantic_name])
                    result = run_online_policy(
                        config,
                        cell,
                        seed,
                        underlying,
                        environment=environment,
                        bonus_multiplier=multiplier,
                        calibration_protocol=protocol,
                    )
                    summary = dict(result.summary)
                    summary.update(
                        {
                            "semantic_method": semantic_name,
                            "underlying_method": underlying,
                            "calibration_protocol": protocol,
                            "calibration_multiplier": multiplier,
                            "selection_sha256": selection_sha256,
                        }
                    )
                    summaries.append(summary)
                    for source in result.rounds:
                        record = dict(source)
                        record.update(
                            {
                                "semantic_method": semantic_name,
                                "underlying_method": underlying,
                                "calibration_protocol": protocol,
                                "calibration_multiplier": multiplier,
                            }
                        )
                        rounds.append(record)

    aggregates, comparisons = aggregate(summaries)
    _write_jsonl(destination / "evaluation_summaries.jsonl", summaries)
    _write_jsonl(destination / "evaluation_rounds.jsonl", rounds)
    write_json_artifact(destination / "aggregates.json", aggregates)
    write_json_artifact(destination / "paired_comparisons.json", comparisons)
    manifest = {
        "schema_version": 1,
        "study": "coverage_matched_operator",
        "config_digest": config_digest(dict(config)),
        "tuning_seeds": list(config["seed_sets"]["tuning"]),
        "evaluation_seeds": list(config["seed_sets"]["evaluation"]),
        "evaluation_seeds_inspected_during_selection": False,
        "cell_count": len(cells),
        "protocols": list(PROTOCOLS),
        "semantic_methods": dict(config["semantic_methods"]),
        "evaluation_run_count": len(summaries),
        "elapsed_seconds": time.perf_counter() - started,
        "holm_family_size": int(config["calibration"]["holm_family_size"]),
        "lofi_status": "implemented_low_rank_plus_diagonal_batch_refit_not_official_lofi",
        "interpretation": (
            "independently executed policy comparisons; paired seed intervals do not "
            "identify a causal operator effect"
        ),
        "provenance": collect_run_metadata(
            repository=Path(__file__).resolve().parents[1],
            packages=("numpy", "scipy"),
        ),
    }
    write_json_artifact(destination / "manifest.json", manifest)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("experiments/configs/coverage_matched_operator.yaml")
    )
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    config = load_config(args.config, args.profile)
    manifest = run_study(config, args.output_root, overwrite=args.overwrite)
    print(canonical_json(manifest))


if __name__ == "__main__":
    main()
