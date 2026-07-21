from __future__ import annotations

import numpy as np

from experiments.run_operator_ablation import (
    OperatorSpec,
    action_set_width_ratios,
    exact_global_kappa_plus,
    run_operator_ablation,
)
from experiments.nonlinear_operator_ablation import (
    _NonlinearOperatorBuilder,
    run_nonlinear_operator,
    run_nonlinear_operator_ablation,
)


def _short_config() -> dict[str, object]:
    return {
        "name": "operator_ablation_test",
        "rounds": 5,
        "noise_std": 0.2,
        "damping": 1.0,
        "operators": {
            "full": {"kind": "full"},
            "diagonal": {"kind": "diagonal"},
            "windowed": {"kind": "windowed", "buffer_sizes": [2]},
        },
        "common_trajectory": {"enabled": True},
        "seed_sets": {"tuning": [3], "evaluation": [103]},
    }


def test_exact_global_factor_and_action_set_factor_have_the_intended_direction() -> None:
    reference = np.array(
        [[2.0, 0.2, -0.1], [0.2, 1.4, 0.15], [-0.1, 0.15, 1.1]],
        dtype=np.float64,
    )
    cholesky = np.linalg.cholesky(reference)
    rotation, _ = np.linalg.qr(
        np.array([[1.0, 2.0, -1.0], [2.0, -1.0, 0.5], [0.3, 0.7, 2.0]])
    )
    generalized = np.array([0.4, 1.6, 3.2], dtype=np.float64)
    approximate = (
        cholesky @ rotation @ np.diag(generalized) @ rotation.T @ cholesky.T
    )
    actions = np.array(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [1.0, -0.5, 0.2]],
        dtype=np.float64,
    )

    global_factor = exact_global_kappa_plus(approximate, reference)
    action_factor = action_set_width_ratios(approximate, reference, actions)

    np.testing.assert_allclose(global_factor, generalized[-1], rtol=2e-13, atol=2e-13)
    assert action_factor.maximum_squared_ratio <= global_factor + 1e-12
    np.testing.assert_allclose(
        action_factor.width_ratios**2, action_factor.squared_ratios, rtol=2e-15, atol=2e-15
    )
    assert action_factor.cbar_widths_squared.dtype == np.float64
    assert action_factor.chat_widths_squared.dtype == np.float64


def test_online_windows_are_unrescaled_and_full_equals_frozen() -> None:
    result = run_operator_ablation(
        _short_config(), 103, include_common_trajectory=False, retain_matrices=True
    )
    by_name = {run.spec.name: run for run in result.online_runs}

    assert result.summary["full_frozen_identical_in_linear_environment"] is True
    assert by_name["full"].actions == by_name["frozen"].actions
    np.testing.assert_array_equal(by_name["full"].contexts, by_name["frozen"].contexts)
    assert all(matrix.algorithmic.dtype == np.float64 for matrix in by_name["full"].matrices)

    window = by_name["unrescaled_window_2"]
    assert window.summary["window_global_kappa_le_one_all_rounds"] is True
    assert all(record["exact_global_kappa_plus"] <= 1.0 + 2e-10 for record in window.rounds)
    assert all(record["kappa_plus"] == record["exact_global_kappa_plus"] for record in window.rounds)
    assert all("policy_transfer_factor" in record for record in window.rounds)
    assert all(record["action_set_ratio_bounded_by_global_kappa"] for record in window.rounds)
    assert all(record["executed_policy"] for record in window.rounds)


def test_common_trajectory_is_identical_and_carries_no_causal_regret_claim() -> None:
    result = run_operator_ablation(_short_config(), 103)
    common = result.common_trajectory
    assert common is not None
    assert common.summary["offline_diagnostic"] is True
    assert common.summary["causal_regret_claim"] is False
    assert common.summary["regret_reported"] is False

    assert {diagnostic.trajectory.digest for diagnostic in common.diagnostics} == {
        common.trajectory.digest
    }
    for diagnostic in common.diagnostics:
        assert diagnostic.trajectory is common.trajectory
        assert diagnostic.actions == common.trajectory.actions
        np.testing.assert_array_equal(diagnostic.contexts, common.trajectory.contexts)
        np.testing.assert_array_equal(diagnostic.checkpoints, common.trajectory.checkpoints)
        assert diagnostic.summary["same_fixed_trajectory"] is True
        assert diagnostic.summary["causal_regret_claim"] is False
        assert all(record["logged_action"] == action for record, action in zip(
            diagnostic.rounds, common.trajectory.actions, strict=True
        ))
        assert all(record["executed_policy"] is False for record in diagnostic.rounds)
        assert all("pseudo_regret" not in record for record in diagnostic.rounds)
        assert all("cumulative_pseudo_regret" not in record for record in diagnostic.rounds)

    full = next(item for item in common.diagnostics if item.spec.kind == "full")
    assert all(record["diagnostic_action_matches_logged_action"] for record in full.rounds)


def _short_nonlinear_config() -> dict[str, object]:
    return {
        "name": "nonlinear_operator_ablation_test",
        "rounds": 4,
        "noise_std": 0.1,
        "ridge": 1.0,
        "nonlinear_audit": {
            "rounds": 4,
            "regime": "medium",
            "center": "corrected",
            "noise_std": 0.1,
            "damping": 1.0,
        },
        "operators": [
            {"name": "full", "kind": "full"},
            {"name": "frozen", "kind": "frozen"},
            {"name": "diagonal", "kind": "diagonal"},
            {"name": "lanczos2", "kind": "lanczos_ritz", "rank": 2},
            {"name": "window2", "kind": "unrescaled_window", "size": 2},
            {"name": "subsample2", "kind": "rescaled_subsample", "size": 2},
            {"name": "stale2", "kind": "stale_refresh", "period": 2},
        ],
        "common_trajectory": {"enabled": True},
        "seed_sets": {"tuning": [3], "evaluation": [103]},
    }


def test_nonlinear_operators_are_symmetric_spd_and_fixed_per_checkpoint() -> None:
    current = np.array(
        [[1.0, 0.2, -0.3], [0.4, -0.8, 0.5], [-0.2, 0.9, 0.7]],
        dtype=np.float64,
    )
    frozen = current + np.array(
        [[0.05, 0.0, -0.02], [0.0, 0.03, 0.0], [-0.01, 0.0, 0.04]]
    )
    specs = (
        OperatorSpec("full"),
        OperatorSpec("frozen"),
        OperatorSpec("diagonal"),
        OperatorSpec("lanczos", 2),
        OperatorSpec("unrescaled_window", 2),
        OperatorSpec("rescaled_subsample", 2),
        OperatorSpec("stale_refresh", 2),
    )
    for spec in specs:
        first_builder = _NonlinearOperatorBuilder(
            spec, dimension=3, damping=1.0, noise_variance=0.25, seed=9
        )
        second_builder = _NonlinearOperatorBuilder(
            spec, dimension=3, damping=1.0, noise_variance=0.25, seed=9
        )
        first, metadata = first_builder.build(3, current, frozen)
        second, _ = second_builder.build(3, current, frozen)
        np.testing.assert_allclose(first, first.T, rtol=0.0, atol=1e-14)
        np.linalg.cholesky(first)
        np.testing.assert_array_equal(first, second)
        assert metadata["fixed_within_all_action_solves"] is True


def test_nonlinear_ablation_executes_online_and_separates_common_trajectory() -> None:
    result = run_nonlinear_operator_ablation(_short_nonlinear_config(), 103)
    assert len(result.online_runs) == 7
    assert result.summary["common_random_contexts_across_methods"] is True
    assert result.summary["common_random_noise_across_methods"] is True
    assert all(run.summary["executed_policy"] for run in result.online_runs)
    assert all(
        abs(run.summary["dynamic_identity_residual"]) < 1e-9
        for run in result.online_runs
    )
    window = next(run for run in result.online_runs if run.spec.kind == "unrescaled_window")
    assert window.summary["window_global_kappa_le_one_all_rounds"] is True
    assert all(
        record["action_set_current_ratio_bounded_by_global_kappa"]
        for run in result.online_runs
        for record in run.records
    )

    common = result.common_trajectory
    assert common is not None
    assert common.summary["causal_regret_claim"] is False
    assert common.summary["regret_reported"] is False
    assert all(diagnostic.summary["executed_policy"] is False for diagnostic in common.diagnostics)
    assert all(
        "cumulative_pseudo_regret" not in record
        for diagnostic in common.diagnostics
        for record in diagnostic.records
    )
    full = next(item for item in common.diagnostics if item.spec.kind == "full")
    assert all(record["diagnostic_action_matches_logged_action"] for record in full.records)


def test_nonlinear_operator_policy_is_reproducible_without_runtime_telemetry() -> None:
    spec = OperatorSpec("rescaled_subsample", 2)
    first = run_nonlinear_operator(_short_nonlinear_config(), spec, 103)
    second = run_nonlinear_operator(_short_nonlinear_config(), spec, 103)
    assert first.trajectory.digest == second.trajectory.digest
    assert first.records == second.records
