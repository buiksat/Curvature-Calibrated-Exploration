from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from experiments.aggregate_transport_instantiation import (
    METHODS,
    TransportAggregationError,
    aggregate_transport_instantiation,
    condition_directory,
)
from experiments.artifact_utils import (
    input_set_sha256,
    sha256_file,
    validate_aggregate_provenance_sidecar,
    write_aggregate_with_provenance,
    write_json_artifact,
)
from experiments.config import config_digest
from experiments.logging_utils import canonical_json, derive_seed
from experiments.transport_instantiation import derive_child_seed, target_width


TUNING_SEED = 909201
EVALUATION_SEED = 909202
REVISION = "fixture-transport-revision"


def _config() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": "transport_instantiation",
        "description": "unit fixture",
        "profile": "smoke",
        "rounds": 2,
        "horizons": [2],
        "target_D": [0.5],
        "environment": {
            "context_dimension": 4,
            "action_count": 5,
            "feature_dimension": 29,
            "feature_bound": 1.0,
            "noise_std": 0.25,
        },
        "teacher": {"theta_radius": 1.0, "seed": 1729},
        "ridge": 1.0,
        "training_ridge": 1.0,
        "methods": list(METHODS),
        "method_roles": {
            "transport_hessian": "primary_certified_theorem_instantiation",
            "transport_endpoint": "dense_endpoint_diagnostic_oracle",
            "frozen_reference": "certified_reference_geometry_comparison",
            "naive_current": "uncertified_negative_control",
        },
        "representation_update": {
            "tuning": {
                "learning_rate_grid": [0.01],
                "steps_per_round_grid": [1],
                "selection_metric": "mean_all_action_prediction_mse_after_burn_in",
            }
        },
        "statistics": {
            "coverage_level": 0.95,
            "paired_bootstrap_resamples": 40,
            "paired_bootstrap_level": 0.95,
        },
        "reporting": {"primary_horizon": 2},
        "numerics": {"ratio_denominator_tolerance": 1e-12},
        "seed_sets": {
            "development": [909200],
            "tuning": [TUNING_SEED],
            "evaluation": [EVALUATION_SEED],
        },
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(canonical_json(record) + "\n" for record in records),
        encoding="ascii",
    )


def _write_selection(
    root: Path,
    config: dict[str, Any],
    *,
    selection_metric: str = "mean_all_action_prediction_mse_after_burn_in",
) -> Path:
    tuning_directory = (
        root
        / "tuning"
        / "T-2"
        / "D-0p5"
        / "candidate-000"
        / f"seed-{TUNING_SEED}"
    )
    tuning_manifest = tuning_directory / "manifest.jsonl"
    _write_jsonl(
        tuning_manifest,
        [
            {
                "schema_version": 1,
                "phase": "tuning",
                "profile": "smoke",
                "git_revision": REVISION,
                "config_digest": config_digest(config),
                "seed": TUNING_SEED,
            }
        ],
    )
    tuning_raw = tuning_directory / "raw.jsonl"
    _write_jsonl(tuning_raw, [{"round": 0, "metrics": {"fixture": 1.0}}])
    tuning_summary = {
        "schema_version": 1,
        "event": "transport_instantiation_tuning_summary",
        "phase": "tuning",
        "profile": "smoke",
        "config_digest": config_digest(config),
        "candidate_id": "candidate-000",
        "seed": TUNING_SEED,
        "horizon": 2,
        "target_D": 0.5,
        "valid": True,
        "mean_all_action_prediction_mse": 0.125,
        "rejection_reasons": [],
    }
    summary_path, summary_sha_path = write_json_artifact(
        tuning_directory / "summary.json", tuning_summary
    )
    input_paths = sorted(
        (tuning_manifest, tuning_raw, summary_path, summary_sha_path), key=str
    )
    inputs = [
        {"path": str(path), "sha256": sha256_file(path)} for path in input_paths
    ]
    candidate = {
        "candidate_id": "candidate-000",
        "learning_rate": 0.01,
        "steps_per_round": 1,
        "eligible": True,
        "aggregate_mean_all_action_prediction_mse": 0.125,
        "rejection_reasons": [],
        "runs": [
            {
                "seed": TUNING_SEED,
                "horizon": 2,
                "target_D": 0.5,
                "summary_path": str(summary_path),
                "valid": True,
                "mean_all_action_prediction_mse": 0.125,
                "rejection_reasons": [],
            }
        ],
    }
    selection = {
        "schema_version": 1,
        "event": "transport_instantiation_selection",
        "profile": "smoke",
        "config_digest": config_digest(config),
        "git_revision": REVISION,
        "git_dirty": True,
        "tuning_seeds": [TUNING_SEED],
        "evaluation_seeds": [EVALUATION_SEED],
        "seed_sets_disjoint": True,
        "selection_metric": selection_metric,
        "candidate_count": 1,
        "candidates": [candidate],
        "selected": {
            "candidate_id": "candidate-000",
            "learning_rate": 0.01,
            "steps_per_round": 1,
            "aggregate_mean_all_action_prediction_mse": 0.125,
            "tie_break": ["fewer_steps_per_round", "smaller_learning_rate"],
        },
        "complete_tuning_input_inventory": True,
        "inputs": inputs,
        "input_set_sha256": input_set_sha256(inputs),
    }
    path, _ = write_aggregate_with_provenance(
        selection, root / "selection.json"
    )
    return path


def _round_metrics(
    method: str, round_index: int, *, confidence: bool
) -> dict[str, Any]:
    primary = method == "transport_hessian"
    regret = 0.0 if primary else 0.1 * (round_index + 1)
    d_q = 0.0 if round_index == 0 else 0.1
    d_th = 0.0 if round_index == 0 else 0.06
    d_path = 0.0 if round_index == 0 else 0.08
    return {
        "cumulative_pseudo_regret": regret,
        "D_Q": d_q,
        "d_Th": d_th,
        "D_path_quad": d_path,
        "sharp_theorem_rhs": 1.0 + round_index,
        "simple_theorem_rhs": 1.2 + round_index,
        "beta_t_corr": 1.5,
        "historical_radius_contribution": 0.1 * round_index,
        "current_bias": 0.02,
        "current_bias_cumulative": 0.04 * (round_index + 1),
        "statistical_bound_component": 0.4 * (round_index + 1),
        "historical_bound_component": 0.1 * round_index,
        "path_inflation_component": 0.05 * round_index,
        "reference_confidence_all_actions": confidence,
        "transport_optimism_all_actions": confidence,
        "prefix_simultaneous_reference_confidence": confidence,
        "prefix_simultaneous_transport_optimism": confidence,
        "prefix_simultaneous_method_optimism": confidence,
        "deterministic_audit_failure_count": 0,
        "width_sum": 0.1 * (round_index + 1),
        "potential_upper": 0.5 * (round_index + 1),
    }


def _write_evaluation_runs(
    raw_root: Path,
    config: dict[str, Any],
    selection_path: Path,
) -> None:
    selection_sha256 = sha256_file(selection_path)
    digest = config_digest(config)
    bootstrap_seed = derive_seed(
        int(digest[:16], 16),
        "transport_instantiation",
        "bootstrap",
        2,
        0.5,
    )
    width = target_width(
        2,
        0.5,
        feature_bound=1.0,
        theta_radius=1.0,
        noise_std=0.25,
        ridge=1.0,
    )
    for method in METHODS:
        directory = (
            condition_directory(raw_root / "evaluation", 2, 0.5)
            / method
            / f"seed-{EVALUATION_SEED}"
        )
        manifest = {
            "schema_version": 1,
            "phase": "evaluation",
            "profile": "smoke",
            "method": method,
            "seed": EVALUATION_SEED,
            "horizon": 2,
            "target_D": 0.5,
            "W": width,
            "selection_sha256": selection_sha256,
            "git_revision": REVISION,
            "config_digest": digest,
            "config": copy.deepcopy(config),
            "child_seeds": {
                "context_stream": derive_child_seed(
                    EVALUATION_SEED, "transport_instantiation/context/v1"
                ),
                "potential_noise_table": derive_child_seed(
                    EVALUATION_SEED,
                    "transport_instantiation/potential_noise/v1",
                ),
                "teacher_construction": 1729,
                "behavior_policy_tuning_stream": derive_child_seed(
                    EVALUATION_SEED,
                    "transport_instantiation/behavior_policy/v1",
                ),
                "bootstrap_aggregation": bootstrap_seed,
            },
        }
        _write_jsonl(directory / "manifest.jsonl", [manifest])
        confidence = method != "transport_hessian"
        raw = [
            {"round": index, "metrics": _round_metrics(method, index, confidence=confidence)}
            for index in range(2)
        ]
        _write_jsonl(directory / "raw.jsonl", raw)
        final = raw[-1]["metrics"]
        regret = float(final["cumulative_pseudo_regret"])
        summary = {
            "schema_version": 1,
            "event": "transport_instantiation_summary",
            "phase": "evaluation",
            "profile": "smoke",
            "method": method,
            "seed": EVALUATION_SEED,
            "horizon": 2,
            "rounds": 2,
            "target_D": 0.5,
            "W": width,
            "config_digest": digest,
            "selection_sha256": selection_sha256,
            "optimizer": {"learning_rate": 0.01, "steps_per_round": 1},
            "deterministic_audit_failure_count": 0,
            "deterministic_audit_pass": True,
            "simultaneous_reference_confidence": confidence,
            "simultaneous_transport_optimism": confidence,
            "simultaneous_method_optimism": confidence,
            "cumulative_pseudo_regret": regret,
            "sharp_theorem_rhs": final["sharp_theorem_rhs"],
            "simple_theorem_rhs": final["simple_theorem_rhs"],
            "width_sum": final["width_sum"],
            "potential_upper": final["potential_upper"],
            "zero_regret": regret == 0.0,
            "optimal_action_entropy": 1.0,
            "distinct_optimal_actions": 5,
            "average_optimality_gap": 0.2,
            "best_fixed_action_regret": 0.4,
            "context_free_mean_only_regret": 0.5,
        }
        write_json_artifact(directory / "summary.json", summary)


def _fixture(
    tmp_path: Path,
    *,
    selection_metric: str = "mean_all_action_prediction_mse_after_burn_in",
) -> tuple[dict[str, Any], Path, Path]:
    config = _config()
    selection = _write_selection(
        tmp_path, config, selection_metric=selection_metric
    )
    raw_root = tmp_path / "raw"
    _write_evaluation_runs(raw_root, config, selection)
    return config, selection, raw_root


def test_strict_aggregate_retains_stochastic_failure_and_handles_zero_regret(
    tmp_path: Path,
) -> None:
    config, selection, raw_root = _fixture(tmp_path)
    aggregate = aggregate_transport_instantiation(
        config, selection, raw_root, profile="smoke"
    )

    assert aggregate["full_grid_complete"] is True
    assert aggregate["completed_run_count"] == len(METHODS)
    assert aggregate["all_deterministic_audits_pass"] is True
    assert aggregate["stochastic_confidence_failures_retained"] is True
    validity = aggregate["validity"][0]
    assert validity["reference_confidence_coverage"]["successes"] == 0
    assert validity["reference_confidence_coverage"]["n"] == 1
    nonvacuity = aggregate["bound_nonvacuity"][0]
    assert nonvacuity["zero_regret_run_count"] == 1
    assert nonvacuity["positive_regret_run_count"] == 0
    assert nonvacuity["sharp_rhs_over_positive_regret"] is None
    assert "NaN" not in canonical_json(aggregate)
    assert aggregate["input_set_sha256"] == input_set_sha256(aggregate["inputs"])

    aggregate_path, sidecar = write_aggregate_with_provenance(
        aggregate, tmp_path / "aggregate.json"
    )
    validate_aggregate_provenance_sidecar(aggregate_path, sidecar)
    raw_input = next(
        Path(item["path"])
        for item in aggregate["inputs"]
        if str(item["path"]).endswith("raw.jsonl")
        and "/evaluation/" in str(item["path"])
    )
    raw_input.write_text(raw_input.read_text() + "\n", encoding="ascii")
    with pytest.raises(ValueError, match="input digest does not match"):
        validate_aggregate_provenance_sidecar(aggregate_path, sidecar)


def test_incomplete_cartesian_product_is_rejected(tmp_path: Path) -> None:
    config, selection, raw_root = _fixture(tmp_path)
    missing = (
        condition_directory(raw_root / "evaluation", 2, 0.5)
        / "naive_current"
        / f"seed-{EVALUATION_SEED}"
        / "manifest.jsonl"
    )
    missing.unlink()
    with pytest.raises(TransportAggregationError, match="Cartesian product mismatch"):
        aggregate_transport_instantiation(
            config, selection, raw_root, profile="smoke"
        )


@pytest.mark.parametrize("failure", ("overlap", "duplicate"))
def test_invalid_evaluation_seed_sets_are_rejected(
    tmp_path: Path, failure: str
) -> None:
    config, selection, raw_root = _fixture(tmp_path)
    if failure == "overlap":
        config["seed_sets"]["evaluation"] = [TUNING_SEED]
        message = "overlap"
    else:
        config["seed_sets"]["evaluation"] = [EVALUATION_SEED, EVALUATION_SEED]
        message = "duplicates"
    with pytest.raises(ValueError, match=message):
        aggregate_transport_instantiation(
            config, selection, raw_root, profile="smoke"
        )


def test_config_selection_and_deterministic_mismatches_are_rejected(
    tmp_path: Path,
) -> None:
    config, selection, raw_root = _fixture(tmp_path / "config")
    manifest_path = (
        condition_directory(raw_root / "evaluation", 2, 0.5)
        / "transport_hessian"
        / f"seed-{EVALUATION_SEED}"
        / "manifest.jsonl"
    )
    manifest = json.loads(manifest_path.read_text())
    manifest["config_digest"] = "wrong"
    _write_jsonl(manifest_path, [manifest])
    with pytest.raises(TransportAggregationError, match="config digest mismatch"):
        aggregate_transport_instantiation(
            config, selection, raw_root, profile="smoke"
        )

    bad_config, bad_selection, bad_raw = _fixture(
        tmp_path / "selection", selection_metric="posthoc_metric"
    )
    with pytest.raises(TransportAggregationError, match="selection metric"):
        aggregate_transport_instantiation(
            bad_config, bad_selection, bad_raw, profile="smoke"
        )

    audit_config, audit_selection, audit_raw = _fixture(tmp_path / "audit")
    summary_path = (
        condition_directory(audit_raw / "evaluation", 2, 0.5)
        / "transport_hessian"
        / f"seed-{EVALUATION_SEED}"
        / "summary.json"
    )
    summary = json.loads(summary_path.read_text())
    summary["deterministic_audit_failure_count"] = 1
    summary["deterministic_audit_pass"] = False
    write_json_artifact(summary_path, summary)
    with pytest.raises(TransportAggregationError, match="deterministic audit failed"):
        aggregate_transport_instantiation(
            audit_config, audit_selection, audit_raw, profile="smoke"
        )
