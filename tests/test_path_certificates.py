from __future__ import annotations

import inspect
import math

import numpy as np
import pytest

from experiments.path_certificates import PathCertificateState


TANH_SECOND_DERIVATIVE_MAX = 4.0 / (3.0 * math.sqrt(3.0))


def _mu(theta: np.ndarray, phi: np.ndarray) -> float:
    return float(np.tanh(phi @ theta))


def _gradient(theta: np.ndarray, phi: np.ndarray) -> np.ndarray:
    value = np.tanh(phi @ theta)
    return np.asarray((1.0 - value * value) * phi, dtype=np.float64)


def _append(
    state: PathCertificateState,
    theta: np.ndarray,
    *,
    residual: float = 0.0,
    L_g: float = 0.4,
    L_mu: float = 0.4,
    G: float = 1.0,
    sigma: float = 0.7,
    lambda_: float = 1.2,
    S: float = 1.0,
) -> None:
    snapshot = state.pre_action_schedule(
        theta,
        L_g=L_g,
        L_mu=L_mu,
        G=G,
        sigma=sigma,
        lambda_=lambda_,
        S=S,
        delta=0.05,
        zeta_t=0.0,
        operator_mode="exact_full",
        optimizer_residual_source="test_exact_gradient_norm",
        cg_certificate_source="test_exact_width",
        smoothness_source="analytic_tanh_global_bound",
    )
    state.commit_action_selection(0, np.asarray([0.0]))
    state.update_after_reward(
        theta,
        residual,
        snapshot.epsilon_lin_bar_t,
    )


def _inverse_root(matrix: np.ndarray) -> np.ndarray:
    values, vectors = np.linalg.eigh(matrix)
    return np.asarray((vectors * (1.0 / np.sqrt(values))) @ vectors.T)


def test_running_Q_matches_direct_history_sum() -> None:
    rng = np.random.default_rng(710)
    state = PathCertificateState(7)
    history: list[np.ndarray] = []

    for _ in range(20):
        theta_t = rng.normal(0.0, 0.3, size=7)
        direct = sum(float(np.sum((theta_t - old) ** 2)) for old in history)
        np.testing.assert_allclose(state.compute_Q(theta_t), direct, rtol=2e-15, atol=2e-15)
        _append(state, theta_t)
        history.append(theta_t.copy())

        stacked = np.stack(history)
        np.testing.assert_allclose(state.mean_theta, np.mean(stacked, axis=0), atol=2e-16)
        np.testing.assert_allclose(
            state.theta_scatter,
            float(np.sum((stacked - np.mean(stacked, axis=0)) ** 2)),
            rtol=3e-15,
            atol=3e-15,
        )

    assert state.mean_theta.dtype == np.float64
    assert not state.mean_theta.flags.writeable


def test_Q_clamps_only_tiny_negative_roundoff() -> None:
    state = PathCertificateState(2)
    state._theta_scatter = -1.0e-16  # exercise the defensive audit branch
    assert state.compute_Q(np.zeros(2)) == 0.0
    state._theta_scatter = -1.0e-4
    with pytest.raises(FloatingPointError, match="materially negative"):
        state.compute_Q(np.zeros(2))


def test_chi_bar_dominates_exact_dense_whitened_drift() -> None:
    rng = np.random.default_rng(711)
    dimension = 5
    sigma = 0.6
    lambda_ = 0.9
    B_phi = 0.8
    L_g = TANH_SECOND_DERIVATIVE_MAX * B_phi**2
    state = PathCertificateState(dimension)
    theta_history = [rng.normal(0.0, 0.12, size=dimension) for _ in range(9)]
    phis = rng.normal(size=(len(theta_history), dimension))
    phis *= B_phi / np.maximum(np.linalg.norm(phis, axis=1, keepdims=True), B_phi)

    for theta_s in theta_history:
        _append(state, theta_s, L_g=L_g, L_mu=L_g, G=B_phi, sigma=sigma, lambda_=lambda_)

    theta_t = rng.normal(0.0, 0.12, size=dimension)
    frozen = np.stack([_gradient(theta_s, phi) for theta_s, phi in zip(theta_history, phis, strict=True)])
    replayed = np.stack([_gradient(theta_t, phi) for phi in phis])
    cbar = lambda_ * np.eye(dimension) + frozen.T @ frozen / sigma**2
    whitened = _inverse_root(cbar) @ (replayed - frozen).T / sigma
    exact_chi = float(np.linalg.norm(whitened, ord=2))

    assert exact_chi <= state.compute_chi_bar(theta_t, L_g, sigma, lambda_) + 2e-15


def _centering_problem() -> tuple[
    PathCertificateState,
    list[np.ndarray],
    np.ndarray,
    np.ndarray,
    np.ndarray,
    float,
    float,
    float,
]:
    rng = np.random.default_rng(712)
    dimension = 4
    sigma = 0.8
    lambda_ = 1.1
    B_phi = 0.75
    L_g = TANH_SECOND_DERIVATIVE_MAX * B_phi**2
    theta_history = [rng.normal(0.0, 0.09, size=dimension) for _ in range(7)]
    theta_t = rng.normal(0.0, 0.09, size=dimension)
    phis = rng.normal(size=(len(theta_history), dimension))
    phis *= B_phi / np.maximum(np.linalg.norm(phis, axis=1, keepdims=True), B_phi)
    rewards = np.asarray(
        [_mu(theta, phi) + noise for theta, phi, noise in zip(
            theta_history,
            phis,
            np.linspace(-0.08, 0.06, len(theta_history)),
            strict=True,
        )]
    )
    state = PathCertificateState(dimension)
    for theta_s, phi, reward in zip(theta_history, phis, rewards, strict=True):
        _append(
            state,
            theta_s,
            residual=_mu(theta_s, phi) - float(reward),
            L_g=L_g,
            L_mu=L_g,
            G=B_phi,
            sigma=sigma,
            lambda_=lambda_,
        )
    return state, theta_history, theta_t, phis, rewards, sigma, lambda_, B_phi


def test_M_bar_dominates_direct_mismatch_vector() -> None:
    state, theta_history, theta_t, phis, rewards, sigma, _, B_phi = _centering_problem()
    L_g = TANH_SECOND_DERIVATIVE_MAX * B_phi**2
    mismatch = np.zeros_like(theta_t)

    for theta_s, phi, reward in zip(theta_history, phis, rewards, strict=True):
        g_s = _gradient(theta_s, phi)
        g_st = _gradient(theta_t, phi)
        delta = g_st - g_s
        bar_mu = _mu(theta_s, phi) + float(g_s @ (theta_t - theta_s))
        e_st = _mu(theta_t, phi) - bar_mu
        bar_r = bar_mu - float(reward)
        mismatch += bar_r * delta + e_st * g_s + e_st * delta
    mismatch /= sigma**2

    general = state.compute_M_bar(theta_t, L_g, B_phi, sigma)
    trust = state.compute_M_bar(
        theta_t,
        L_g,
        B_phi,
        sigma,
        trust_region_radius=0.5,
    )
    exact = float(np.linalg.norm(mismatch))
    assert exact <= general + 2e-15
    assert exact <= trust + 2e-15


def test_psi_bar_bounds_all_candidate_centering_discrepancies() -> None:
    state, theta_history, theta_t, phis, rewards, sigma, lambda_, B_phi = _centering_problem()
    L_g = TANH_SECOND_DERIVATIVE_MAX * B_phi**2
    frozen = np.stack([_gradient(theta_s, phi) for theta_s, phi in zip(theta_history, phis, strict=True)])
    replayed = np.stack([_gradient(theta_t, phi) for phi in phis])
    cbar = lambda_ * np.eye(theta_t.size) + frozen.T @ frozen / sigma**2
    pseudo_offsets = np.asarray(
        [
            float(reward) - _mu(theta_s, phi) + float(g_s @ theta_s)
            for theta_s, phi, reward, g_s in zip(
                theta_history, phis, rewards, frozen, strict=True
            )
        ]
    )
    theta_hat = np.linalg.solve(cbar, frozen.T @ pseudo_offsets / sigma**2)
    nonlinear_gradient = (
        replayed.T
        @ np.asarray([_mu(theta_t, phi) for phi in phis] - rewards)
        / sigma**2
        + lambda_ * theta_t
    )
    zeta_t = float(np.linalg.norm(nonlinear_gradient))
    psi_bar = state.compute_psi_bar(
        theta_t,
        zeta_t,
        L_g,
        B_phi,
        sigma,
        lambda_,
        trust_region_radius=0.5,
    )

    rng = np.random.default_rng(713)
    candidates = rng.normal(size=(6, theta_t.size))
    candidates *= B_phi / np.maximum(
        np.linalg.norm(candidates, axis=1, keepdims=True), B_phi
    )
    candidate_gradients = np.stack([_gradient(theta_t, phi) for phi in candidates])
    discrepancies = np.abs(candidate_gradients @ (theta_t - theta_hat))
    widths = np.sqrt(
        np.einsum(
            "ij,ij->i",
            candidate_gradients,
            np.linalg.solve(cbar, candidate_gradients.T).T,
        )
    )
    assert np.all(discrepancies <= psi_bar * widths + 2e-14)


def test_F_bar_and_E_bar_dominate_true_taylor_remainders() -> None:
    rng = np.random.default_rng(714)
    dimension = 5
    B_phi = 0.7
    L_mu = TANH_SECOND_DERIVATIVE_MAX * B_phi**2
    theta_star = rng.normal(0.0, 0.1, size=dimension)
    S = float(np.linalg.norm(theta_star)) + 0.02
    state = PathCertificateState(dimension)
    true_squared = 0.0
    true_absolute = 0.0

    for _ in range(12):
        theta_t = rng.normal(0.0, 0.12, size=dimension)
        phi = rng.normal(size=dimension)
        phi *= B_phi / max(float(np.linalg.norm(phi)), B_phi)
        snapshot = state.pre_action_schedule(
            theta_t,
            L_g=L_mu,
            L_mu=L_mu,
            G=B_phi,
            sigma=0.5,
            lambda_=1.0,
            S=S,
            delta=0.05,
            zeta_t=0.0,
            operator_mode="exact_full",
            optimizer_residual_source="test_exact_gradient_norm",
            cg_certificate_source="test_exact_width",
            smoothness_source="analytic_tanh_global_bound",
        )
        remainder = (
            _mu(theta_star, phi)
            - _mu(theta_t, phi)
            - float(_gradient(theta_t, phi) @ (theta_star - theta_t))
        )
        assert abs(remainder) <= snapshot.epsilon_lin_bar_t + 2e-16
        true_squared += remainder**2
        true_absolute += abs(remainder)
        state.commit_action_selection(0, np.asarray([0.0]))
        state.update_after_reward(
            theta_t,
            0.0,
            snapshot.epsilon_lin_bar_t,
        )

    assert true_squared <= state.F_bar + 2e-16
    assert true_absolute <= state.E_bar + 2e-16


def test_gamma_hat_bounds_frozen_information_gain() -> None:
    rng = np.random.default_rng(715)
    dimension = 6
    sigma = 0.55
    lambda_ = 1.3
    state = PathCertificateState(dimension)
    cbar = lambda_ * np.eye(dimension)

    for _ in range(14):
        theta_t = rng.normal(0.0, 0.05, size=dimension)
        feature = rng.normal(size=dimension)
        feature /= max(1.0, float(np.linalg.norm(feature)))
        width_squared = float(feature @ np.linalg.solve(cbar, feature))
        snapshot = state.pre_action_schedule(
            theta_t,
            L_g=0.0,
            L_mu=0.0,
            G=1.0,
            sigma=sigma,
            lambda_=lambda_,
            S=1.0,
            delta=0.05,
            zeta_t=0.0,
            operator_mode="exact_full",
            optimizer_residual_source="test_exact_gradient_norm",
            cg_certificate_source="test_exact_width",
            smoothness_source="zero_linear_smoothness",
        )
        state.commit_action_selection(0, np.asarray([width_squared]))
        state.update_after_reward(
            theta_t,
            0.0,
            snapshot.epsilon_lin_bar_t,
        )
        cbar += np.outer(feature, feature) / sigma**2

    sign, logdet = np.linalg.slogdet(cbar)
    assert sign > 0
    exact_gamma = float(logdet - dimension * np.log(lambda_))
    np.testing.assert_allclose(state.gamma_hat, exact_gamma, rtol=2e-14, atol=2e-14)


def test_complete_pre_action_schedule_has_no_event_failures_on_tanh_trace() -> None:
    rng = np.random.default_rng(716)
    dimension = 4
    action_count = 3
    horizon = 9
    sigma = 0.65
    lambda_ = 1.0
    B_phi = 0.65
    L_g = TANH_SECOND_DERIVATIVE_MAX * B_phi**2
    theta_star = np.asarray([0.16, -0.11, 0.08, 0.05])
    S = 0.25
    trust_radius = 0.35
    theta_path = [
        0.015 * t * np.asarray([1.0, -0.6, 0.4, -0.2]) for t in range(horizon)
    ]
    state = PathCertificateState(dimension)
    history_theta: list[np.ndarray] = []
    history_phi: list[np.ndarray] = []
    history_reward: list[float] = []
    true_F = 0.0
    cbar = lambda_ * np.eye(dimension)

    for round_index, theta_t in enumerate(theta_path):
        candidate_phis = rng.normal(size=(action_count, dimension))
        candidate_phis *= B_phi / np.maximum(
            np.linalg.norm(candidate_phis, axis=1, keepdims=True), B_phi
        )
        frozen = (
            np.stack(
                [
                    _gradient(theta_s, phi_s)
                    for theta_s, phi_s in zip(history_theta, history_phi, strict=True)
                ]
            )
            if history_theta
            else np.empty((0, dimension))
        )
        replayed = (
            np.stack([_gradient(theta_t, phi_s) for phi_s in history_phi])
            if history_phi
            else np.empty((0, dimension))
        )
        current_curvature = lambda_ * np.eye(dimension) + replayed.T @ replayed / sigma**2
        action_gradients = np.stack([_gradient(theta_t, phi) for phi in candidate_phis])

        if history_theta:
            pseudo_offsets = np.asarray(
                [
                    reward - _mu(theta_s, phi_s) + float(g_s @ theta_s)
                    for theta_s, phi_s, reward, g_s in zip(
                        history_theta,
                        history_phi,
                        history_reward,
                        frozen,
                        strict=True,
                    )
                ]
            )
            theta_hat = np.linalg.solve(cbar, frozen.T @ pseudo_offsets / sigma**2)
            nonlinear_gradient = (
                replayed.T
                @ np.asarray(
                    [
                        _mu(theta_t, phi_s) - reward
                        for phi_s, reward in zip(history_phi, history_reward, strict=True)
                    ]
                )
                / sigma**2
                + lambda_ * theta_t
            )
        else:
            theta_hat = np.zeros(dimension)
            nonlinear_gradient = lambda_ * theta_t
        zeta_t = float(np.linalg.norm(nonlinear_gradient))
        snapshot = state.pre_action_schedule(
            theta_t,
            L_g=L_g,
            L_mu=L_g,
            G=B_phi,
            sigma=sigma,
            lambda_=lambda_,
            S=S,
            delta=0.05,
            zeta_t=zeta_t,
            operator_mode="exact_full",
            optimizer_residual_source="exact_full_objective_gradient_norm",
            cg_certificate_source="exact_dense_width_zero_error",
            smoothness_source="analytic_tanh_global_bound",
            trust_region_radius=trust_radius,
        )

        assert snapshot.gamma_hat_prior + 2e-14 >= float(
            np.linalg.slogdet(cbar)[1] - dimension * np.log(lambda_)
        )
        exact_beta = (
            math.sqrt(
                float(np.linalg.slogdet(cbar)[1] - dimension * np.log(lambda_))
                + 2.0 * math.log(20.0)
            )
            + math.sqrt(lambda_) * S
            + math.sqrt(true_F) / sigma
        )
        assert snapshot.beta_bar_t + 2e-14 >= exact_beta

        if history_theta:
            delta = replayed - frozen
            exact_chi = float(
                np.linalg.norm(_inverse_root(cbar) @ delta.T / sigma, ord=2)
            )
        else:
            exact_chi = 0.0
        assert exact_chi <= snapshot.chi_bar_t + 2e-14

        frozen_widths_sq = np.einsum(
            "ij,ij->i", action_gradients, np.linalg.solve(cbar, action_gradients.T).T
        )
        current_widths_sq = np.einsum(
            "ij,ij->i",
            action_gradients,
            np.linalg.solve(current_curvature, action_gradients.T).T,
        )
        assert np.all(
            frozen_widths_sq
            <= snapshot.transfer_factor * current_widths_sq + 2e-14
        )
        centering = np.abs(action_gradients @ (theta_t - theta_hat))
        assert np.all(
            centering
            <= snapshot.psi_bar_t * np.sqrt(frozen_widths_sq) + 3e-14
        )
        true_remainder = np.max(
            np.abs(
                np.asarray([_mu(theta_star, phi) for phi in candidate_phis])
                - np.asarray([_mu(theta_t, phi) for phi in candidate_phis])
                - action_gradients @ (theta_star - theta_t)
            )
        )
        assert true_remainder <= snapshot.epsilon_lin_bar_t + 2e-16

        action = round_index % action_count
        phi_played = candidate_phis[action]
        reward = _mu(theta_star, phi_played) + 0.03 * math.sin(round_index)
        collection_residual = _mu(theta_t, phi_played) - reward
        state.commit_action_selection(action, current_widths_sq)
        state.update_after_reward(
            theta_t,
            collection_residual,
            snapshot.epsilon_lin_bar_t,
        )
        true_collection_remainder = (
            _mu(theta_star, phi_played)
            - _mu(theta_t, phi_played)
            - float(action_gradients[action] @ (theta_star - theta_t))
        )
        true_F += true_collection_remainder**2
        history_theta.append(theta_t.copy())
        history_phi.append(phi_played.copy())
        history_reward.append(float(reward))
        played_frozen = action_gradients[action]
        cbar += np.outer(played_frozen, played_frozen) / sigma**2

    assert state.F_bar + 2e-16 >= true_F


def test_filtration_order_is_enforced_and_api_has_no_teacher_argument() -> None:
    state = PathCertificateState(3)
    theta = np.zeros(3)
    with pytest.raises(RuntimeError, match="pre_action_schedule"):
        state.update_after_reward(
            theta,
            0.0,
            0.0,
        )

    snapshot = state.pre_action_schedule(
        theta,
        L_g=0.2,
        L_mu=0.2,
        G=1.0,
        sigma=1.0,
        lambda_=1.0,
        S=1.0,
        delta=0.05,
        zeta_t=0.0,
        operator_mode="exact_full",
        optimizer_residual_source="test_exact_gradient_norm",
        cg_certificate_source="test_exact_width",
        smoothness_source="test_smoothness_bound",
    )
    with pytest.raises(RuntimeError, match="previous pre-action"):
        state.pre_action_schedule(
            theta,
            L_g=0.2,
            L_mu=0.2,
            G=1.0,
            sigma=1.0,
            lambda_=1.0,
            S=1.0,
            delta=0.05,
            zeta_t=0.0,
            operator_mode="exact_full",
            optimizer_residual_source="test_exact_gradient_norm",
            cg_certificate_source="test_exact_width",
            smoothness_source="test_smoothness_bound",
        )
    with pytest.raises(RuntimeError, match="commit_action_selection"):
        state.update_after_reward(
            theta,
            0.0,
            snapshot.epsilon_lin_bar_t,
        )
    commitment = state.commit_action_selection(0, np.asarray([0.0, 0.1]))
    assert commitment.action == 0
    with pytest.raises(ValueError, match="theta_t changed"):
        state.update_after_reward(
            np.ones(3),
            0.0,
            snapshot.epsilon_lin_bar_t,
        )
    assert state.count == 0
    state.update_after_reward(
        theta,
        0.0,
        snapshot.epsilon_lin_bar_t,
    )
    assert state.count == 1
    with pytest.raises(ValueError, match="fixed theorem constants changed"):
        state.pre_action_schedule(
            theta,
            L_g=0.2,
            L_mu=0.2,
            G=1.0,
            sigma=2.0,
            lambda_=1.0,
            S=1.0,
            delta=0.05,
            zeta_t=0.0,
            operator_mode="exact_full",
            optimizer_residual_source="test_exact_gradient_norm",
            cg_certificate_source="test_exact_width",
            smoothness_source="test_smoothness_bound",
        )
    with pytest.raises(ValueError, match="requires kappa_plus_t and its source"):
        PathCertificateState(3).pre_action_schedule(
            theta,
            L_g=0.2,
            L_mu=0.2,
            G=1.0,
            sigma=1.0,
            lambda_=1.0,
            S=1.0,
            delta=0.05,
            zeta_t=0.0,
            operator_mode="certified_approximate",
            optimizer_residual_source="test_exact_gradient_norm",
            cg_certificate_source="test_exact_width",
            smoothness_source="test_smoothness_bound",
        )
    assert "theta_star" not in inspect.signature(state.pre_action_schedule).parameters
    assert all(key.startswith("policy_certificate_") for key in snapshot.as_metrics())
