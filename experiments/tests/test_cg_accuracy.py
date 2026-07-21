from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest
import scipy.linalg as la

from experiments.aggregate_cg_policy import (
    CGPolicyAggregationError,
    aggregate_policy_artifacts,
    validate_policy_provenance_sidecar,
    write_policy_aggregate,
)
from experiments.run_cg_accuracy import (
    ACTION_COUNT,
    ENERGY_TARGETS,
    make_spd_problem,
    relative_energy_error,
    residual_energy_certificate,
    run_cg_accuracy,
    run_cg_policy_accuracy,
    run_cg_policy_cell,
    save_policy_run,
    save_run,
    solve_certified_cg,
)


def _config() -> dict[str, object]:
    return {
        "name": "cg_accuracy_test",
        "profile": "smoke",
        "dimension": 8,
        "sample_count": 12,
        "noise_std": 0.4,
        "rounds": 2,
        "action_count": 2,
        "condition_numbers": [12.0],
        "damping": [0.5],
        "cg": {
            "max_iterations": 64,
            "record_residual_history": True,
            # The driver must use the experiment's fixed required targets.
            "relative_energy_tolerances": [0.3],
        },
        "provenance": {"packages": ["numpy", "scipy"]},
    }


def _deterministic(record: dict[str, object]) -> dict[str, object]:
    ignored = {
        "wall_time_seconds",
        "dense_inverse_reference_seconds",
        "rss_before_bytes",
        "rss_after_bytes",
        "rss_bytes",
        "rss_delta_bytes",
        "peak_host_memory_bytes",
    }
    return {key: value for key, value in record.items() if key not in ignored}


def _policy_config() -> dict[str, object]:
    return {
        "name": "cg_accuracy_test",
        "profile": "smoke",
        "rounds": 3,
        "action_count": ACTION_COUNT,
        "ridge": 1.0,
        "noise_std": 0.25,
        "policy_audit": {
            "delta": 0.05,
            "bonus_scale": 1.0,
            "max_iterations": 4 * 53,
        },
        "provenance": {"packages": ["numpy", "scipy"]},
    }


def _policy_deterministic(record: dict[str, object]) -> dict[str, object]:
    ignored = {
        "solver_wall_time_seconds",
        "dense_reference_wall_time_seconds",
        "round_runtime_seconds",
        "runtime_seconds",
        "rss_bytes",
        "peak_host_memory_bytes",
        "process_peak_host_memory_bytes",
    }
    return {key: value for key, value in record.items() if key not in ignored}


def test_residual_certificate_and_width_sandwich() -> None:
    matrix, _, right_hand_sides = make_spd_problem(10, 1, 40.0, 0.3, 91)
    rhs = right_hand_sides[0]
    exact = la.inv(matrix, check_finite=False) @ rhs

    for preconditioner in ("none", "jacobi"):
        result = solve_certified_cg(
            matrix,
            rhs,
            target=0.05,
            preconditioner=preconditioner,
            max_iterations=80,
        )
        error = relative_energy_error(matrix, exact, result.solution)
        residual = rhs - matrix @ result.solution
        certificate = residual_energy_certificate(
            matrix, rhs, residual, preconditioner=preconditioner
        )
        exact_width_squared = float(rhs @ exact)
        approximate_width_squared = float(rhs @ result.solution)

        assert result.converged
        assert error <= certificate + 2e-12
        assert certificate <= 0.05 + 2e-12
        assert (1.0 - error) * exact_width_squared <= approximate_width_squared + 2e-12
        assert approximate_width_squared <= (1.0 + error) * exact_width_squared + 2e-12
        assert result.solution.dtype == np.float64
        assert result.residual_history.dtype == np.float64


def test_required_targets_warm_starts_and_determinism() -> None:
    first = run_cg_accuracy(_config(), 17)
    second = run_cg_accuracy(_config(), 17)

    assert first.summary == second.summary
    assert first.summary["energy_targets"] == list(ENERGY_TARGETS)
    assert first.summary["warm_start_advantage_assumed"] is False
    assert first.summary["target_failure_count"] == 0
    assert first.summary["residual_certificate_violation_count"] == 0
    assert first.summary["sandwich_violation_count"] == 0
    assert [_deterministic(record) for record in first.records] == [
        _deterministic(record) for record in second.records
    ]

    expected = 2 * 2 * len(ENERGY_TARGETS) * 2 * 2
    assert len(first.records) == expected
    assert {record["target_energy_error"] for record in first.records} == set(
        ENERGY_TARGETS
    )
    assert {record["initialization"] for record in first.records} == {"zero", "warm"}
    assert {record["preconditioner"] for record in first.records} == {
        "none",
        "jacobi",
    }
    for record in first.records:
        assert record["sample_count"] == 12
        assert record["relative_energy_error"] <= record["residual_certificate"] + 2e-12
        assert record["target_satisfied"] is True
        assert record["sandwich_holds"] is True
        assert record["cvp_count"] == (
            record["operator_matvec_count"] * record["sample_count"]
        )
        assert record["peak_host_memory_bytes"] >= 0
        if record["initialization"] == "zero":
            assert record["initial_relative_energy_error"] == 1.0
        else:
            assert np.isfinite(record["initial_relative_energy_error"])


def test_save_run_writes_jsonl(tmp_path) -> None:
    run = run_cg_accuracy({**_config(), "rounds": 1, "action_count": 1}, 3)
    destination = save_run(run, tmp_path / "cg", _config(), overwrite=True)

    assert (destination / "manifest.jsonl").is_file()
    raw = [
        json.loads(line)
        for line in (destination / "raw.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(raw) == len(run.records)
    assert [record["round"] for record in raw] == list(range(len(raw)))
    summary = json.loads(
        (destination / "summary.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert summary["energy_targets"] == list(ENERGY_TARGETS)


def test_executed_cg_policy_is_certified_and_deterministic() -> None:
    first = run_cg_policy_cell(
        _policy_config(),
        130,
        epsilon_bar=0.1,
        initialization="zero",
        preconditioner="jacobi",
    )
    second = run_cg_policy_cell(
        _policy_config(),
        130,
        epsilon_bar=0.1,
        initialization="zero",
        preconditioner="jacobi",
    )

    assert first.summary["executed_policy"] is True
    assert first.summary["certified_execution"] is True
    assert first.summary["target_failure_count"] == 0
    assert first.summary["residual_certificate_violation_count"] == 0
    assert first.summary["sandwich_violation_count"] == 0
    assert first.summary["theorem_bound_slack"] >= 0.0
    assert first.summary["min_width_information_slack"] >= -1e-9
    assert [_policy_deterministic(record) for record in first.records] == [
        _policy_deterministic(record) for record in second.records
    ]

    for record in first.records:
        assert record["full_action_enumeration"] is True
        assert record["curvature_operator_build_count"] == 1
        assert record["separate_per_action_cg_solves"] == ACTION_COUNT
        assert record["same_fixed_operator_reused_across_action_solves"] is True
        assert record["operator_dense_probe_max_abs"] <= record[
            "operator_dense_probe_tolerance"
        ]
        assert all(record["target_sandwich_holds"])
        assert all(record["exact_error_sandwich_holds"])
        assert all(
            error <= certificate + 1e-12
            for error, certificate in zip(
                record["exact_relative_energy_errors"],
                record["residual_certificates"],
                strict=True,
            )
        )
        assert record["operator_matvec_count"] == sum(
            record["operator_matvec_counts"]
        )
        assert record["sample_cvp_count"] == record["operator_matvec_count"] * (
            record["policy_round"] - 1
        )
        assert record["theorem_bound_slack"] >= 0.0


def test_policy_cells_use_common_random_numbers_and_report_warm_start() -> None:
    zero = run_cg_policy_cell(
        _policy_config(),
        131,
        epsilon_bar=0.25,
        initialization="zero",
        preconditioner="none",
    )
    warm = run_cg_policy_cell(
        _policy_config(),
        131,
        epsilon_bar=0.25,
        initialization="warm",
        preconditioner="none",
    )

    assert [record["context"] for record in zero.records] == [
        record["context"] for record in warm.records
    ]
    assert [record["noise"] for record in zero.records] == [
        record["noise"] for record in warm.records
    ]
    assert warm.summary["warm_start_advantage_assumed"] is False
    assert all(
        np.isfinite(error)
        for record in warm.records
        for error in record["initial_relative_energy_errors"]
    )


def test_policy_grid_and_separate_artifact_path(tmp_path) -> None:
    config = {
        **_policy_config(),
        "profile": "full",
        "rounds": 1,
        "seed_sets": {"tuning": [30], "evaluation": [132]},
    }
    run = run_cg_policy_accuracy(config, 132)
    assert len(run.cells) == len(ENERGY_TARGETS) * 2 * 2
    assert len(run.records) == len(run.cells)

    destination = save_policy_run(
        run, tmp_path / "cg_policy_accuracy" / "seed-132", config, overwrite=True
    )
    raw = [
        json.loads(line)
        for line in (destination / "raw.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    summaries = [
        json.loads(line)
        for line in (destination / "summary.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(raw) == len(run.records)
    assert len(summaries) == len(run.cells)
    assert all(summary["experiment"] == "cg_policy_accuracy" for summary in summaries)

    aggregate = aggregate_policy_artifacts(
        tmp_path / "cg_policy_accuracy", expected_seed_set="evaluation"
    )
    assert aggregate["seed_count"] == 1
    assert aggregate["policy_cell_count"] == len(run.cells)
    assert aggregate["raw_round_count"] == len(run.records)
    assert aggregate["all_executions_certified"] is True

    artifact, sidecar = write_policy_aggregate(
        aggregate, tmp_path / "derived" / "cg_policy_accuracy_full.json"
    )
    provenance = validate_policy_provenance_sidecar(artifact, sidecar)
    assert provenance["artifact_sha256"] == hashlib.sha256(
        artifact.read_bytes()
    ).hexdigest()
    assert len(provenance["inputs"]) == 3

    raw_path = destination / "raw.jsonl"
    raw_bytes = raw_path.read_bytes()
    raw_path.write_bytes(raw_bytes + b"\n")
    with pytest.raises(CGPolicyAggregationError, match="input digest"):
        validate_policy_provenance_sidecar(artifact, sidecar)
    raw_path.write_bytes(raw_bytes)

    artifact.write_text(artifact.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(CGPolicyAggregationError, match="artifact digest"):
        validate_policy_provenance_sidecar(artifact, sidecar)
