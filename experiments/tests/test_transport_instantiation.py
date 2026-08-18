from __future__ import annotations

import math

import numpy as np
import pytest

import experiments.transport_instantiation as transport
from experiments.transport_instantiation import (
    ACTION_COUNT,
    FEATURE_DIMENSION,
    OptimizerSpec,
    PotentialOutcomeStream,
    ScaledTanhEnvironment,
    TransportHistory,
    build_potential_outcome_stream,
    certified_linearization_envelope,
    cholesky_solve,
    confidence_radius,
    corrected_center,
    derive_child_seed,
    factor_path_length,
    hessian_q_path_certificate,
    information_gain,
    inverse_quadratic_widths,
    policy_scores,
    run_policy_trajectory,
    scaled_tanh_gradient,
    scaled_tanh_hessian_vector_product,
    scaled_tanh_mean,
    smoothness_constant,
    thompson_distance,
)


def _unit_vector(rng: np.random.Generator) -> np.ndarray:
    value = rng.normal(size=FEATURE_DIMENSION)
    return value / np.linalg.norm(value)


def _tiny_config() -> dict[str, object]:
    return {
        "profile": "unit",
        "horizons": [2],
        "environment": {
            "context_dimension": 4,
            "action_count": 5,
            "feature_bound": 1.0,
            "noise_std": 0.25,
        },
        "teacher": {"theta_radius": 1.0, "seed": 1729},
        "ridge": 1.0,
        "training_ridge": 1.0,
        "confidence": {"delta": 0.05},
        "transport": {
            "quadrature": {
                "frozen_order": 16,
                "full_checkpoint_period": 10,
                "inequality_absolute_tolerance": 1e-9,
                "inequality_relative_tolerance": 1e-8,
            }
        },
        "representation_update": {
            "projection_radius": 1.0,
            "tuning": {"burn_in_rounds": 1},
        },
        "numerics": {
            "algebra_tolerance_constant": 4096.0,
            "fail_on_deterministic_violation": False,
        },
    }


def test_scaled_tanh_mean_gradient_hvp_and_global_bounds() -> None:
    rng = np.random.default_rng(909001)
    theta = 0.7 * _unit_vector(rng)
    feature = _unit_vector(rng)
    direction = _unit_vector(rng)
    width = 3.0
    step = 2e-6

    mean = scaled_tanh_mean(theta, feature, width)
    gradient = scaled_tanh_gradient(theta, feature, width)
    finite_gradient = (
        scaled_tanh_mean(theta + step * direction, feature, width)
        - scaled_tanh_mean(theta - step * direction, feature, width)
    ) / (2.0 * step)
    assert float(gradient @ direction) == pytest.approx(
        finite_gradient, rel=2e-8, abs=2e-10
    )

    hvp = scaled_tanh_hessian_vector_product(theta, feature, direction, width)
    finite_hvp = (
        scaled_tanh_gradient(theta + step * direction, feature, width)
        - scaled_tanh_gradient(theta - step * direction, feature, width)
    ) / (2.0 * step)
    np.testing.assert_allclose(hvp, finite_hvp, rtol=2e-7, atol=2e-9)

    assert abs(mean) <= math.sqrt(width)
    assert np.linalg.norm(gradient) <= 1.0 + 1e-14
    assert np.linalg.norm(hvp) <= (
        smoothness_constant(1.0) * np.linalg.norm(direction) / math.sqrt(width)
        + 1e-14
    )


def test_corrected_center_pseudo_response_normal_equation_and_one_over_sigma() -> None:
    rng = np.random.default_rng(909002)
    environment = ScaledTanhEnvironment(width=4.0, noise_std=0.4)
    theta = 0.35 * _unit_vector(rng)
    feature = environment.features[3, 2]
    query = environment.gradient(theta, feature)
    true_mean = float(environment.mean(environment.theta_star, feature))
    collection_mean = float(environment.mean(theta, feature))
    remainder = true_mean - collection_mean - float(
        query @ (environment.theta_star - theta)
    )
    noise = -0.13
    reward = true_mean + noise
    pseudo_response = reward - collection_mean + float(query @ theta)
    assert pseudo_response == pytest.approx(
        float(query @ environment.theta_star) + remainder + noise,
        abs=2e-15,
    )

    envelope = certified_linearization_envelope(
        theta,
        theta_radius=1.0,
        lipschitz_mean=environment.lipschitz_mean,
    )
    history = TransportHistory(ridge=1.3, noise_std=environment.noise_std)
    history.append(
        category=3 * ACTION_COUNT + 2,
        collection_theta=theta,
        collection_query=query,
        pseudo_response=pseudo_response,
        reward=reward,
        noise=noise,
        certified_envelope=envelope,
        actual_remainder=remainder,
    )
    theta_hat = cholesky_solve(history.frozen_metric, history.frozen_rhs)
    np.testing.assert_allclose(
        history.frozen_metric @ theta_hat,
        history.frozen_rhs,
        rtol=2e-13,
        atol=2e-13,
    )

    action_features = environment.features[5]
    action_queries = environment.gradient(theta, action_features)
    centers = corrected_center(theta, theta_hat, action_features, environment)
    true_means = np.asarray(
        environment.mean(environment.theta_star, action_features), dtype=np.float64
    )
    current_means = np.asarray(environment.mean(theta, action_features))
    current_remainders = (
        true_means
        - current_means
        - action_queries @ (environment.theta_star - theta)
    )
    np.testing.assert_allclose(
        true_means - centers,
        action_queries @ (environment.theta_star - theta_hat)
        + current_remainders,
        rtol=3e-13,
        atol=3e-13,
    )

    beta, statistical, historical = confidence_radius(
        0.7,
        delta=0.05,
        ridge=1.3,
        theta_radius=1.0,
        historical_error_energy=envelope**2,
        noise_std=environment.noise_std,
    )
    assert historical == pytest.approx(envelope / environment.noise_std)
    assert beta == pytest.approx(statistical + historical)
    assert historical != pytest.approx(envelope / environment.noise_std**2)


def test_initial_round_zero_query_and_exact_realizability_edge_cases() -> None:
    environment = ScaledTanhEnvironment(width=2.0)
    assert environment.features.shape == (16, ACTION_COUNT, FEATURE_DIMENSION)
    np.testing.assert_allclose(
        np.linalg.norm(environment.features, axis=2),
        np.ones((16, ACTION_COUNT)),
        rtol=0.0,
        atol=2e-15,
    )
    history = TransportHistory(ridge=1.7, noise_std=environment.noise_std)
    expected = 1.7 * np.eye(FEATURE_DIMENSION)
    np.testing.assert_array_equal(history.frozen_metric, expected)
    np.testing.assert_array_equal(
        history.statistics.current_metric(
            np.zeros(FEATURE_DIMENSION), environment, ridge=1.7
        ),
        expected,
    )
    assert history.path_q(np.zeros(FEATURE_DIMENSION)) == 0.0
    assert information_gain(expected, 1.7) == pytest.approx(0.0, abs=1e-14)
    zero_queries = np.zeros((ACTION_COUNT, FEATURE_DIMENSION))
    np.testing.assert_array_equal(
        inverse_quadratic_widths(expected, zero_queries),
        np.zeros(ACTION_COUNT),
    )
    assert factor_path_length(
        history, np.zeros(FEATURE_DIMENSION), environment, ridge=1.7, order=8
    ) == 0.0


def test_frozen_and_current_metric_replay_and_path_q() -> None:
    environment = ScaledTanhEnvironment(width=2.5, noise_std=0.5)
    history = TransportHistory(ridge=0.8, noise_std=environment.noise_std)
    collection_thetas = [
        np.zeros(FEATURE_DIMENSION),
        0.2 * np.eye(FEATURE_DIMENSION)[1],
    ]
    categories = [0, 7]
    manual_frozen = 0.8 * np.eye(FEATURE_DIMENSION)
    for index, (theta, category) in enumerate(
        zip(collection_thetas, categories, strict=True)
    ):
        feature = environment.category_features[category]
        query = environment.gradient(theta, feature)
        manual_frozen += np.outer(query, query) / environment.noise_std**2
        history.append(
            category=category,
            collection_theta=theta,
            collection_query=query,
            pseudo_response=0.1 * (index + 1),
            reward=0.2 * (index + 1),
            noise=0.0,
            certified_envelope=0.03,
            actual_remainder=0.0,
        )
    np.testing.assert_allclose(history.frozen_metric, manual_frozen, atol=2e-15)

    theta_t = 0.15 * np.eye(FEATURE_DIMENSION)[2]
    manual_current = 0.8 * np.eye(FEATURE_DIMENSION)
    for category in categories:
        query = environment.gradient(theta_t, environment.category_features[category])
        manual_current += np.outer(query, query) / environment.noise_std**2
    np.testing.assert_allclose(
        history.statistics.current_metric(theta_t, environment, ridge=0.8),
        manual_current,
        rtol=2e-14,
        atol=2e-14,
    )
    expected_q = sum(
        float((theta_t - theta) @ (theta_t - theta))
        for theta in collection_thetas
    )
    assert history.path_q(theta_t) == pytest.approx(expected_q, abs=2e-16)


def test_thompson_distance_sandwich_transport_and_extreme_spd_cases() -> None:
    distance = 6.0
    reference = np.eye(2)
    current = np.diag([math.exp(distance), math.exp(-distance)])
    measured, eigenvalues = thompson_distance(reference, current)
    assert measured == pytest.approx(distance, rel=2e-15)
    np.testing.assert_allclose(
        eigenvalues, [math.exp(-distance), math.exp(distance)], rtol=2e-15
    )

    angle = 0.47
    rotation = np.array(
        [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
    )
    noncommuting_reference = rotation @ np.diag([0.2, 4.0]) @ rotation.T
    noncommuting_current = np.diag([3.0, 0.4])
    noncommuting_distance, _ = thompson_distance(
        noncommuting_reference, noncommuting_current
    )
    lower = noncommuting_current - math.exp(-noncommuting_distance) * noncommuting_reference
    upper = math.exp(noncommuting_distance) * noncommuting_reference - noncommuting_current
    assert np.linalg.eigvalsh(lower)[0] >= -2e-14
    assert np.linalg.eigvalsh(upper)[0] >= -2e-14

    queries = np.eye(2)
    frozen_widths = inverse_quadratic_widths(noncommuting_reference, queries)
    current_widths = inverse_quadratic_widths(noncommuting_current, queries)
    inflation = math.exp(noncommuting_distance / 2.0)
    assert np.all(frozen_widths <= inflation * current_widths + 2e-14)
    assert np.all(current_widths <= inflation * frozen_widths + 2e-14)

    ill_conditioned = np.diag([1e-10, 1e10])
    ill_widths = inverse_quadratic_widths(ill_conditioned, queries)
    assert np.all(np.isfinite(ill_widths))
    np.testing.assert_allclose(ill_widths, [1e5, 1e-5], rtol=2e-15)


def test_factor_path_quadrature_converges_and_is_bounded_by_hessian_q() -> None:
    environment = ScaledTanhEnvironment(width=1.7, noise_std=0.35)
    history = TransportHistory(ridge=1.1, noise_std=environment.noise_std)
    theta_s = 0.25 * np.eye(FEATURE_DIMENSION)[0]
    # Keep the scalar replay projection on one side of zero so the operator-norm
    # integrand is smooth.  A sign crossing creates a harmless absolute-value
    # kink and is a poor fixture for testing quadrature convergence.
    theta_t = 0.1 * np.eye(FEATURE_DIMENSION)[0]
    category = 0
    query = environment.gradient(theta_s, environment.category_features[category])
    history.append(
        category=category,
        collection_theta=theta_s,
        collection_query=query,
        pseudo_response=0.0,
        reward=0.0,
        noise=0.0,
        certified_envelope=0.0,
        actual_remainder=0.0,
    )
    current = history.statistics.current_metric(theta_t, environment, ridge=1.1)
    endpoint, _ = thompson_distance(history.frozen_metric, current)
    path_16 = factor_path_length(history, theta_t, environment, ridge=1.1, order=16)
    path_32 = factor_path_length(history, theta_t, environment, ridge=1.1, order=32)
    d_q = hessian_q_path_certificate(
        history.path_q(theta_t),
        lipschitz_gradient=environment.lipschitz_gradient,
        noise_std=environment.noise_std,
        ridge=1.1,
    )
    assert path_32 == pytest.approx(path_16, rel=2e-10, abs=2e-12)
    assert endpoint <= path_32 + 2e-12
    assert path_32 <= d_q + 2e-12

    stationary = TransportHistory(ridge=1.1, noise_std=environment.noise_std)
    stationary_query = environment.gradient(theta_s, environment.category_features[1])
    stationary.append(
        category=1,
        collection_theta=theta_s,
        collection_query=stationary_query,
        pseudo_response=0.0,
        reward=0.0,
        noise=0.0,
        certified_envelope=0.0,
        actual_remainder=0.0,
    )
    stationary_current = stationary.statistics.current_metric(
        theta_s, environment, ridge=1.1
    )
    zero_distance, _ = thompson_distance(
        stationary.frozen_metric, stationary_current
    )
    assert zero_distance == pytest.approx(0.0, abs=3e-15)
    assert factor_path_length(
        stationary, theta_s, environment, ridge=1.1, order=16
    ) == pytest.approx(0.0, abs=3e-15)


def test_policy_formulas_smallest_index_tie_and_roles() -> None:
    centers = np.zeros(ACTION_COUNT)
    frozen = np.ones(ACTION_COUNT)
    current = np.full(ACTION_COUNT, 0.5)
    beta = 2.0
    bias = 0.3
    d_q = 1.4
    endpoint = 0.4

    hessian = policy_scores(
        "transport_hessian",
        centers,
        beta=beta,
        current_bias=bias,
        frozen_widths=frozen,
        current_widths=current,
        hessian_path_bound=d_q,
        endpoint_distance=endpoint,
    )
    endpoint_scores = policy_scores(
        "transport_endpoint",
        centers,
        beta=beta,
        current_bias=bias,
        frozen_widths=frozen,
        current_widths=current,
        hessian_path_bound=d_q,
        endpoint_distance=endpoint,
    )
    frozen_scores = policy_scores(
        "frozen_reference",
        centers,
        beta=beta,
        current_bias=bias,
        frozen_widths=frozen,
        current_widths=current,
        hessian_path_bound=d_q,
        endpoint_distance=endpoint,
    )
    naive = policy_scores(
        "naive_current",
        centers,
        beta=beta,
        current_bias=bias,
        frozen_widths=frozen,
        current_widths=current,
        hessian_path_bound=d_q,
        endpoint_distance=endpoint,
    )
    np.testing.assert_allclose(hessian, beta * math.exp(d_q / 2.0) * current + bias)
    np.testing.assert_allclose(
        endpoint_scores, beta * math.exp(endpoint / 2.0) * current + bias
    )
    np.testing.assert_allclose(frozen_scores, beta * frozen + bias)
    np.testing.assert_allclose(naive, beta * current + bias)
    assert not np.array_equal(hessian, endpoint_scores)
    assert int(np.argmax(np.ones(ACTION_COUNT))) == 0

    trajectory = run_policy_trajectory(
        _tiny_config(),
        "naive_current",
        seed=909101,
        horizon=2,
        target_d=0.7,
        optimizer=OptimizerSpec(learning_rate=1e-4, steps_per_round=1),
        diagnostic_mode="none",
    )
    assert trajectory.rounds[0]["selected_action"] == 0
    assert trajectory.rounds[0]["method_certified"] is False
    assert trajectory.summary["method_certified"] is False
    np.testing.assert_allclose(
        trajectory.rounds[0]["scores"],
        trajectory.rounds[0]["naive_current_scores"],
    )


def test_common_potential_outcomes_across_methods_and_no_current_reward_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _tiny_config()
    optimizer = OptimizerSpec(learning_rate=1e-4, steps_per_round=1)
    first = run_policy_trajectory(
        config,
        "transport_hessian",
        seed=909102,
        horizon=2,
        target_d=0.7,
        optimizer=optimizer,
        diagnostic_mode="none",
    )
    second = run_policy_trajectory(
        config,
        "transport_endpoint",
        seed=909102,
        horizon=2,
        target_d=0.7,
        optimizer=optimizer,
        diagnostic_mode="none",
    )
    assert first.child_seeds == second.child_seeds
    assert [record["context"] for record in first.rounds] == [
        record["context"] for record in second.rounds
    ]
    environment = ScaledTanhEnvironment(
        width=first.width, teacher_seed=1729, noise_std=0.25
    )
    shared = build_potential_outcome_stream(
        environment,
        2,
        context_seed=first.child_seeds["context_stream"],
        noise_seed=first.child_seeds["potential_noise_table"],
    )
    for trajectory in (first, second):
        for index, record in enumerate(trajectory.rounds):
            action = int(record["selected_action"])
            assert record["selected_noise"] == pytest.approx(
                shared.noises[index, action]
            )
            assert record["selected_reward"] == pytest.approx(
                shared.rewards[index, action]
            )

    original_builder = transport.build_potential_outcome_stream
    base_stream = original_builder(
        environment,
        2,
        context_seed=derive_child_seed(909103, "transport_instantiation/context/v1"),
        noise_seed=derive_child_seed(
            909103, "transport_instantiation/potential_noise/v1"
        ),
    )

    def fixed_builder(*args: object, **kwargs: object) -> PotentialOutcomeStream:
        return base_stream

    monkeypatch.setattr(transport, "build_potential_outcome_stream", fixed_builder)
    baseline = run_policy_trajectory(
        config,
        "transport_hessian",
        seed=909103,
        horizon=2,
        target_d=0.7,
        optimizer=optimizer,
        diagnostic_mode="none",
    )
    altered_noises = base_stream.noises.copy()
    altered_noises[0] += np.linspace(-100.0, 100.0, ACTION_COUNT)
    altered_rewards = base_stream.true_means + altered_noises
    altered_stream = PotentialOutcomeStream(
        context_indices=base_stream.context_indices,
        contexts=base_stream.contexts,
        true_means=base_stream.true_means,
        noises=altered_noises,
        rewards=altered_rewards,
    )

    def altered_builder(*args: object, **kwargs: object) -> PotentialOutcomeStream:
        return altered_stream

    monkeypatch.setattr(transport, "build_potential_outcome_stream", altered_builder)
    altered = run_policy_trajectory(
        config,
        "transport_hessian",
        seed=909103,
        horizon=2,
        target_d=0.7,
        optimizer=optimizer,
        diagnostic_mode="none",
    )
    assert altered.rounds[0]["selected_action"] == baseline.rounds[0]["selected_action"]
