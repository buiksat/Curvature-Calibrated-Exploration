from __future__ import annotations

import numpy as np

from experiments.logging_utils import canonical_json
from experiments.nonlinear_environment import (
    ACTION_COUNT,
    NonlinearBanditEnvironment,
    SmallTanhMLP,
    enumerate_rademacher_contexts,
)
from experiments.run_nonlinear_audit import (
    active_parameter_indices,
    deterministic_online_update,
    run_single_audit,
)


def test_analytic_mlp_jacobian_matches_central_finite_difference() -> None:
    model = SmallTanhMLP()
    rng = np.random.default_rng(812)
    theta = rng.normal(0.0, 0.08, size=model.parameter_dimension)
    context = enumerate_rademacher_contexts()[11]
    analytic = model.jacobians(theta, context)
    numerical = np.empty_like(analytic)
    step = 1.0e-6

    for coordinate in range(model.parameter_dimension):
        offset = np.zeros(model.parameter_dimension, dtype=np.float64)
        offset[coordinate] = step
        numerical[:, coordinate] = (
            model.means(theta + offset, context)
            - model.means(theta - offset, context)
        ) / (2.0 * step)

    assert analytic.dtype == np.float64
    assert analytic.shape == (ACTION_COUNT, model.parameter_dimension)
    np.testing.assert_allclose(analytic, numerical, rtol=2.0e-9, atol=2.0e-10)


def test_teacher_has_bounded_contexts_and_context_dependent_rankings() -> None:
    environment = NonlinearBanditEnvironment(0)
    contexts = enumerate_rademacher_contexts()
    winners = np.asarray(
        [np.argmax(environment.mean_rewards(context)) for context in contexts]
    )

    np.testing.assert_allclose(np.linalg.norm(contexts, axis=1), 1.0)
    np.testing.assert_array_equal(np.unique(winners), np.arange(ACTION_COUNT))


def test_corrected_center_identity_holds_exactly() -> None:
    run = run_single_audit(
        seed=17,
        rounds=4,
        regime="medium",
        center="corrected",
    )
    snapshot = run.snapshots[-1]
    environment = NonlinearBanditEnvironment(17)
    theta_star = environment.teacher_displacement[snapshot.active_indices]
    current = snapshot.parameters
    jacobians = snapshot.action_jacobians
    remainder = snapshot.teacher_means - snapshot.original_centers - jacobians @ (
        theta_star - current
    )
    corrected_error = snapshot.teacher_means - snapshot.corrected_centers

    np.testing.assert_allclose(
        corrected_error,
        jacobians @ (theta_star - snapshot.theta_hat_lin) + remainder,
        rtol=2.0e-13,
        atol=2.0e-14,
    )
    assert run.records[-1]["posthoc_corrected_center_identity_error"] < 1.0e-13


def test_nonlinear_audit_is_deterministically_reproducible() -> None:
    first = run_single_audit(
        seed=29,
        rounds=5,
        regime="medium",
        center="corrected",
        cg_max_iterations=9,
    )
    second = run_single_audit(
        seed=29,
        rounds=5,
        regime="medium",
        center="corrected",
        cg_max_iterations=9,
    )

    assert first.deterministic_signature() == second.deterministic_signature()
    assert canonical_json(first.records) == canonical_json(second.records)
    np.testing.assert_array_equal(first.parameter_path, second.parameter_path)


def test_frozen_head_exact_ridge_has_zero_remainder_drift_and_centering() -> None:
    run = run_single_audit(
        seed=41,
        rounds=8,
        regime="frozen_head",
        center="original",
    )
    model = SmallTanhMLP()

    assert np.max(np.abs(run.parameter_path[:, model.backbone_indices])) == 0.0
    for record, snapshot in zip(run.records, run.snapshots, strict=True):
        assert record["posthoc_epsilon_lin"] < 1.0e-14
        assert record["posthoc_chi_operator_norm"] == 0.0
        assert record["posthoc_centering_ratio"] < 2.0e-13
        assert record["posthoc_primitive_psi"] < 1.0e-12
        np.testing.assert_allclose(
            snapshot.current_curvature,
            snapshot.frozen_curvature,
            rtol=0.0,
            atol=0.0,
        )

    contexts = run.contexts[:4]
    actions = run.actions[:4]
    rewards = run.rewards[:4]
    update = deterministic_online_update(
        model,
        np.zeros(model.parameter_dimension),
        contexts,
        actions,
        rewards,
        regime="frozen_head",
        damping=1.0,
        noise_variance=0.01,
    )
    assert update.gradient_norm < 1.0e-12
    np.testing.assert_array_equal(
        active_parameter_indices(model, "frozen_head"), model.head_indices
    )


def test_drift_ladder_increases_controlled_raw_parameter_movement_only() -> None:
    path_lengths: list[float] = []
    backbone_lengths: list[float] = []
    for regime in ("mild", "medium", "aggressive"):
        run = run_single_audit(
            seed=53,
            rounds=6,
            regime=regime,
            center="original",
        )
        path_lengths.append(run.records[-1]["cumulative_parameter_path_length"])
        backbone_lengths.append(
            run.records[-1]["cumulative_backbone_path_length"]
        )

    assert path_lengths[0] < path_lengths[1] < path_lengths[2]
    assert backbone_lengths[0] < backbone_lengths[1] < backbone_lengths[2]
    # No ordering is imposed on E, chi, regret, or any other empirical hypothesis.


def test_dynamic_metrics_and_policy_posthoc_labels_are_complete() -> None:
    run = run_single_audit(
        seed=67,
        rounds=5,
        regime="aggressive",
        center="original",
        cg_max_iterations=8,
    )
    final = run.records[-1]

    assert final["executed_policy"] is True
    assert final["execution_mode"] == "online_adaptive"
    assert final["policy_schedule_source"] == "predetermined_time_only"
    assert final["posthoc_diagnostic_status"] == "audit_only_not_a_certification_claim"
    assert final["certified_run_claim"] is False
    assert len(final["policy_optimism_margin_all_actions"]) == ACTION_COUNT
    assert len(final["posthoc_cg_energy_error_all_actions"]) == ACTION_COUNT
    assert abs(final["posthoc_dynamic_identity_residual"]) < 2.0e-10
    assert final["posthoc_Gamma_dynamic"] + 1.0e-12 >= final[
        "posthoc_Lambda_algorithmic"
    ]
    assert final["posthoc_theorem_rhs_using_policy_schedule"] >= 0.0
    canonical_json(run.records)
