"""Low-rank near-linear tanh benchmark for theorem-scaling diagnostics.

The online model is

    mu_theta(x) = sqrt(width) * tanh(x.T @ theta / sqrt(width)).

All policies operate in a fixed active subspace.  Policy schedules use only
analytic constants and pre-action path summaries.  Teacher-dependent values,
dense eigensolves, and exact CG energy errors are recorded only after action
selection; they are float64 audits, not verified numerical enclosures.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .config import get_seed_set, load_config
from .curvature_operators import CurvatureOperator
from .logging_utils import ExperimentLogger, append_jsonl, derive_seed
from .path_certificates import PathCertificateState
from .run_certified_tanh import certified_cg_widths


FloatArray = NDArray[np.float64]
TANH_SECOND_DERIVATIVE_MAX = 4.0 / (3.0 * math.sqrt(3.0))
METHODS = (
    "exact_current",
    "full_cg",
    "window_q_1_2",
    "window_q_2_3",
    "window_q_1",
    "frozen",
    "diagonal_current",
    "greedy",
)
WINDOW_EXPONENTS = {
    "window_q_1_2": 0.5,
    "window_q_2_3": 2.0 / 3.0,
    "window_q_1": 1.0,
}
DEFAULT_CONFIG_PATH = Path(__file__).with_name("configs") / "theory_scaling.json"


def _positive(value: Any, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _section(config: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = config.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"config.{name} must be a mapping")
    return value


def scaled_tanh_mean(
    theta: ArrayLike, features: ArrayLike, network_width: float
) -> FloatArray:
    parameters = np.asarray(theta, dtype=np.float64)
    design = np.asarray(features, dtype=np.float64)
    width = _positive(network_width, name="network_width")
    return np.asarray(
        math.sqrt(width) * np.tanh(design @ parameters / math.sqrt(width)),
        dtype=np.float64,
    )


def scaled_tanh_gradients(
    theta: ArrayLike, features: ArrayLike, network_width: float
) -> FloatArray:
    parameters = np.asarray(theta, dtype=np.float64)
    design = np.asarray(features, dtype=np.float64)
    width = _positive(network_width, name="network_width")
    arguments = design @ parameters / math.sqrt(width)
    factors = 1.0 - np.tanh(arguments) ** 2
    return np.asarray(factors[:, None] * design, dtype=np.float64)


def scaled_tanh_constants(
    feature_bound: float, network_width: float
) -> tuple[float, float, float]:
    """Return the global ``G, L_mu, L_g`` analytic constants."""

    bound = _positive(feature_bound, name="feature_bound")
    width = _positive(network_width, name="network_width")
    lipschitz = TANH_SECOND_DERIVATIVE_MAX * bound * bound / math.sqrt(width)
    return bound, lipschitz, lipschitz


def deterministic_embedding(
    ambient_dimension: int, active_rank: int, seed: int
) -> FloatArray:
    ambient = _positive_int(ambient_dimension, name="ambient_dimension")
    rank = _positive_int(active_rank, name="active_rank")
    if rank > ambient:
        raise ValueError("active_rank cannot exceed ambient_dimension")
    rng = np.random.default_rng(seed)
    raw = rng.normal(size=(ambient, rank))
    basis, triangular = np.linalg.qr(raw, mode="reduced")
    signs = np.where(np.diag(triangular) < 0.0, -1.0, 1.0)
    result = np.asarray(basis * signs[None, :], dtype=np.float64)
    result.setflags(write=False)
    return result


class CyclicActiveTanhEnvironment:
    """Two-action Gaussian bandit with cyclic one-coordinate contexts."""

    def __init__(
        self,
        *,
        seed: int,
        rounds: int,
        ambient_dimension: int,
        active_rank: int,
        action_magnitudes: tuple[float, float],
        teacher_norm: float,
        network_width: float,
        noise_std: float,
    ) -> None:
        self.rounds = _positive_int(rounds, name="rounds")
        self.ambient_dimension = _positive_int(
            ambient_dimension, name="ambient_dimension"
        )
        self.active_rank = _positive_int(active_rank, name="active_rank")
        if self.active_rank > self.ambient_dimension:
            raise ValueError("active_rank cannot exceed ambient_dimension")
        negative, positive = (float(value) for value in action_magnitudes)
        if not negative < 0.0 < positive:
            raise ValueError("action_magnitudes must contain a negative then positive value")
        self.action_magnitudes = (negative, positive)
        self.feature_bound = max(abs(negative), positive)
        self.network_width = _positive(network_width, name="network_width")
        self.noise_std = _positive(noise_std, name="noise_std")
        radius = _positive(teacher_norm, name="teacher_norm")
        signs = np.where(np.arange(self.active_rank) % 2 == 0, 1.0, -1.0)
        self._teacher = np.asarray(
            radius * signs / math.sqrt(self.active_rank), dtype=np.float64
        )
        self.embedding = deterministic_embedding(
            self.ambient_dimension,
            self.active_rank,
            derive_seed(seed, "theory_scaling", "embedding"),
        )
        rng = np.random.default_rng(
            derive_seed(seed, "theory_scaling", "reward_stream")
        )
        self._noise = np.asarray(
            rng.normal(0.0, self.noise_std, size=(self.rounds, 2)),
            dtype=np.float64,
        )
        digest = hashlib.sha256()
        digest.update(np.ascontiguousarray(self.embedding, dtype="<f8").tobytes())
        digest.update(np.ascontiguousarray(self._teacher, dtype="<f8").tobytes())
        digest.update(np.ascontiguousarray(self._noise, dtype="<f8").tobytes())
        self.stream_sha256 = digest.hexdigest()

    def active_features(self, round_index: int) -> FloatArray:
        coordinate = round_index % self.active_rank
        result = np.zeros((2, self.active_rank), dtype=np.float64)
        result[:, coordinate] = self.action_magnitudes
        return result

    def reward_and_audit(
        self, round_index: int, action: int
    ) -> tuple[float, float, FloatArray, int]:
        features = self.active_features(round_index)
        means = scaled_tanh_mean(self._teacher, features, self.network_width)
        noise = float(self._noise[round_index, action])
        return float(means[action] + noise), noise, means, int(np.argmax(means))

    def teacher_for_posthoc_audit(self) -> FloatArray:
        result = self._teacher.copy()
        result.setflags(write=False)
        return result


def _objective_gradient_hessian(
    theta: FloatArray,
    features: FloatArray,
    rewards: FloatArray,
    *,
    network_width: float,
    ridge: float,
    noise_variance: float,
) -> tuple[float, FloatArray, FloatArray]:
    width_root = math.sqrt(network_width)
    if features.shape[0] == 0:
        return (
            0.5 * ridge * float(theta @ theta),
            ridge * theta.copy(),
            ridge * np.eye(theta.size, dtype=np.float64),
        )
    arguments = features @ theta / width_root
    tanh_values = np.tanh(arguments)
    means = width_root * tanh_values
    first = (1.0 - tanh_values**2)[:, None] * features
    second_factors = -2.0 * tanh_values * (1.0 - tanh_values**2) / width_root
    residuals = means - rewards
    gradient = ridge * theta + first.T @ residuals / noise_variance
    # Sum the GGN and residual-Hessian terms with level-3 array operations.
    # The expression is exactly
    # sum_i [g_i g_i^T + residual_i mu_i'' x_i x_i^T] / sigma^2.
    residual_curvature = residuals * second_factors
    hessian = (
        ridge * np.eye(theta.size, dtype=np.float64)
        + first.T @ first / noise_variance
        + (features.T * residual_curvature) @ features / noise_variance
    )
    objective = 0.5 * ridge * float(theta @ theta) + 0.5 * float(
        residuals @ residuals
    ) / noise_variance
    return float(objective), np.asarray(gradient), np.asarray(hessian)


def optimize_separable_cumulative_loss(
    initial: ArrayLike,
    features: ArrayLike,
    rewards: ArrayLike,
    *,
    network_width: float,
    ridge: float,
    noise_variance: float,
    trust_radius: float,
    maximum_iterations: int,
    gradient_tolerance: float,
) -> tuple[FloatArray, float, float, int]:
    """Damped Newton minimization with projection and measured residual."""

    theta = np.asarray(initial, dtype=np.float64).copy()
    design = np.asarray(features, dtype=np.float64)
    outcomes = np.asarray(rewards, dtype=np.float64)
    radius = _positive(trust_radius, name="trust_radius")
    iterations = 0
    for iterations in range(1, maximum_iterations + 1):
        objective, gradient, hessian = _objective_gradient_hessian(
            theta,
            design,
            outcomes,
            network_width=network_width,
            ridge=ridge,
            noise_variance=noise_variance,
        )
        if float(np.linalg.norm(gradient)) <= gradient_tolerance:
            break
        diagonal = np.diag(hessian)
        safe_diagonal = np.maximum(diagonal, ridge * 1.0e-6)
        direction = -gradient / safe_diagonal
        accepted = False
        step = 1.0
        for _ in range(32):
            candidate = theta + step * direction
            norm = float(np.linalg.norm(candidate))
            if norm > radius:
                candidate *= radius / norm
            candidate_objective, _, _ = _objective_gradient_hessian(
                candidate,
                design,
                outcomes,
                network_width=network_width,
                ridge=ridge,
                noise_variance=noise_variance,
            )
            if candidate_objective <= objective - 1.0e-4 * step * float(
                gradient @ (-direction)
            ):
                theta = candidate
                accepted = True
                break
            step *= 0.5
        if not accepted:
            break
    _, final_gradient, final_hessian = _objective_gradient_hessian(
        theta,
        design,
        outcomes,
        network_width=network_width,
        ridge=ridge,
        noise_variance=noise_variance,
    )
    return (
        np.asarray(theta, dtype=np.float64),
        float(np.linalg.norm(final_gradient)),
        float(np.min(np.linalg.eigvalsh(final_hessian))),
        iterations,
    )


def _operator_matrix(
    gradients: FloatArray, *, ridge: float, noise_variance: float
) -> FloatArray:
    dimension = gradients.shape[1]
    return np.asarray(
        ridge * np.eye(dimension) + gradients.T @ gradients / noise_variance,
        dtype=np.float64,
    )


def _logdet_ratio(matrix: FloatArray, ridge: float) -> float:
    sign, value = np.linalg.slogdet(matrix)
    if sign <= 0.0:
        raise FloatingPointError("operator lost positive definiteness")
    return float(value - matrix.shape[0] * math.log(ridge))


def _inverse_root(matrix: FloatArray) -> FloatArray:
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    if float(np.min(eigenvalues)) <= 0.0:
        raise FloatingPointError("matrix is not positive definite")
    return np.asarray(
        (eigenvectors / np.sqrt(eigenvalues)[None, :]) @ eigenvectors.T,
        dtype=np.float64,
    )


def _rank_information_bound(
    sample_count: int,
    active_rank: int,
    gradient_bound: float,
    ridge: float,
    noise_variance: float,
) -> float:
    if sample_count == 0:
        return 0.0
    return float(
        active_rank
        * math.log1p(
            sample_count
            * gradient_bound**2
            / (active_rank * ridge * noise_variance)
        )
    )


def _window_size(round_number: int, exponent: float) -> int:
    return min(round_number - 1, int(math.ceil(round_number**exponent)))


def _chosen_operator(
    method: str,
    *,
    current_active: FloatArray,
    frozen_active: FloatArray,
    window_active: FloatArray | None,
    current_ambient_gradients: FloatArray,
    embedding: FloatArray,
    ridge: float,
    noise_variance: float,
) -> tuple[str, FloatArray]:
    if method in {"exact_current", "full_cg", "greedy"}:
        return "active_dense", current_active
    if method in WINDOW_EXPONENTS:
        assert window_active is not None
        return "active_dense", window_active
    if method == "frozen":
        return "active_dense", frozen_active
    if method == "diagonal_current":
        diagonal = ridge + np.sum(current_ambient_gradients**2, axis=0) / noise_variance
        return "ambient_diagonal", np.asarray(diagonal, dtype=np.float64)
    raise ValueError(f"unknown method {method!r}")


def _widths_for_operator(
    representation: str,
    operator: FloatArray,
    action_gradients_active: FloatArray,
    embedding: FloatArray,
) -> FloatArray:
    if representation == "active_dense":
        solutions = np.linalg.solve(operator, action_gradients_active.T).T
        return np.einsum("ij,ij->i", action_gradients_active, solutions)
    action_gradients_ambient = action_gradients_active @ embedding.T
    return np.sum(action_gradients_ambient**2 / operator[None, :], axis=1)


def _operator_logdet(representation: str, operator: FloatArray, ridge: float) -> float:
    if representation == "active_dense":
        return _logdet_ratio(operator, ridge)
    return float(np.sum(np.log(operator / ridge)))


def _relative_refresh_norm(
    current_plus: FloatArray, next_operator: FloatArray
) -> float:
    inverse_root = _inverse_root(current_plus)
    normalized = inverse_root @ (next_operator - current_plus) @ inverse_root
    return float(np.linalg.norm(normalized, ord=2))


@dataclass(frozen=True)
class TheoryScalingRun:
    seed: int
    method: str
    ambient_dimension: int
    active_rank: int
    horizon: int
    stream_sha256: str
    records: tuple[dict[str, Any], ...]
    summary: dict[str, Any]


def run_theory_scaling_cell(
    config: Mapping[str, Any],
    seed: int,
    *,
    method: str,
    ambient_dimension: int,
    active_rank: int,
    horizon: int,
) -> TheoryScalingRun:
    """Execute one online policy cell with common exogenous randomness."""

    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    environment_config = _section(config, "environment")
    policy_config = _section(config, "policy")
    optimizer_config = _section(config, "optimizer")
    cg_config = _section(config, "cg")
    rounds = _positive_int(horizon, name="horizon")
    network_width = _positive(
        environment_config.get("network_width"), name="network_width"
    )
    noise_std = _positive(environment_config.get("noise_std"), name="noise_std")
    variance = noise_std**2
    magnitudes_raw = environment_config.get("action_magnitudes")
    if not isinstance(magnitudes_raw, Sequence) or len(magnitudes_raw) != 2:
        raise ValueError("environment.action_magnitudes must have length two")
    magnitudes = (float(magnitudes_raw[0]), float(magnitudes_raw[1]))
    teacher_norm = _positive(
        environment_config.get("teacher_norm"), name="teacher_norm"
    )
    ridge = _positive(policy_config.get("ridge"), name="ridge")
    delta = _positive(policy_config.get("delta"), name="delta")
    if delta >= 1.0:
        raise ValueError("delta must be smaller than one")
    trust_radius = _positive(
        policy_config.get("trust_region_radius"), name="trust_region_radius"
    )
    cg_error = _positive(
        cg_config.get("relative_energy_error"), name="relative_energy_error"
    )
    cg_max_iterations = _positive_int(
        cg_config.get("max_iterations"), name="max_iterations"
    )
    optimizer_iterations = _positive_int(
        optimizer_config.get("maximum_iterations"), name="maximum_iterations"
    )
    optimizer_tolerance = _positive(
        optimizer_config.get("gradient_tolerance"), name="gradient_tolerance"
    )
    optimizer_residual_schedule = _positive(
        optimizer_config.get("residual_schedule"), name="residual_schedule"
    )
    environment = CyclicActiveTanhEnvironment(
        seed=seed,
        rounds=rounds,
        ambient_dimension=ambient_dimension,
        active_rank=active_rank,
        action_magnitudes=magnitudes,
        teacher_norm=teacher_norm,
        network_width=network_width,
        noise_std=noise_std,
    )
    feature_bound = environment.feature_bound
    G, L_mu, L_g = scaled_tanh_constants(feature_bound, network_width)
    # On the radius-R region every selected gradient has squared norm at least
    # a_min^2 sech^4(a_max R/sqrt(width)).  Cyclic allocation then gives
    # floor(n/r) observations per coordinate.  For n>=r, floor(n/r)>=n/(2r).
    minimum_magnitude = min(abs(value) for value in magnitudes)
    minimum_gradient_sq = minimum_magnitude**2 / math.cosh(
        feature_bound * trust_radius / math.sqrt(network_width)
    ) ** 4
    excitation_per_sample = minimum_gradient_sq / (2.0 * active_rank * variance)

    theta = np.zeros(active_rank, dtype=np.float64)
    history_features = np.empty((0, active_rank), dtype=np.float64)
    history_rewards = np.empty(0, dtype=np.float64)
    history_thetas = np.empty((0, active_rank), dtype=np.float64)
    history_collection_means = np.empty(0, dtype=np.float64)
    frozen_gradients = np.empty((0, active_rank), dtype=np.float64)
    certificate_state = PathCertificateState(active_rank)
    optimizer_residual_float64_audit = 0.0
    strong_convexity_audit = ridge
    true_f = 0.0
    true_e = 0.0
    dynamic_lambda = 0.0
    variation_charge = 0.0
    refresh_log_upper = 0.0
    refresh_upper_valid = True
    cumulative_regret = 0.0
    cumulative_sample_cvps = 0
    optimism_failures = 0
    records: list[dict[str, Any]] = []
    run_started = time.perf_counter()

    for round_index in range(rounds):
        round_started = time.perf_counter()
        round_number = round_index + 1
        n_history = history_features.shape[0]
        action_features = environment.active_features(round_index)
        action_centers = scaled_tanh_mean(theta, action_features, network_width)
        action_gradients = scaled_tanh_gradients(
            theta, action_features, network_width
        )
        current_gradients = (
            scaled_tanh_gradients(theta, history_features, network_width)
            if n_history
            else np.empty((0, active_rank), dtype=np.float64)
        )
        current_active = _operator_matrix(
            current_gradients, ridge=ridge, noise_variance=variance
        )
        frozen_active = _operator_matrix(
            frozen_gradients, ridge=ridge, noise_variance=variance
        )
        window_exponent = WINDOW_EXPONENTS.get(method)
        window_length = (
            _window_size(round_number, window_exponent)
            if window_exponent is not None
            else n_history
        )
        window_gradients = current_gradients[-window_length:] if window_length else current_gradients[:0]
        window_active = _operator_matrix(
            window_gradients, ridge=ridge, noise_variance=variance
        )
        current_ambient_gradients = current_gradients @ environment.embedding.T
        representation, chosen_operator = _chosen_operator(
            method,
            current_active=current_active,
            frozen_active=frozen_active,
            window_active=window_active,
            current_ambient_gradients=current_ambient_gradients,
            embedding=environment.embedding,
            ridge=ridge,
            noise_variance=variance,
        )
        analytic_kappa = 1.0
        if method in {"frozen", "diagonal_current"}:
            analytic_kappa = 1.0 + n_history * G**2 / (ridge * variance)
        if method in {"exact_current", "full_cg", "greedy"}:
            operator_mode = "exact_full"
            kappa_arguments: dict[str, Any] = {}
        elif method in WINDOW_EXPONENTS:
            operator_mode = "unrescaled_current_subset"
            kappa_arguments = {}
        else:
            operator_mode = "certified_approximate"
            kappa_arguments = {
                "kappa_plus_t": analytic_kappa,
                "kappa_plus_source": "analytic_isotropic_outer_product_bound",
            }
        snapshot = certificate_state.pre_action_schedule(
            theta,
            L_g=L_g,
            L_mu=L_mu,
            G=G,
            sigma=noise_std,
            lambda_=ridge,
            S=teacher_norm,
            delta=delta,
            zeta_t=optimizer_residual_schedule,
            operator_mode=operator_mode,
            optimizer_residual_source="fixed_predeclared_schedule_posthoc_audited",
            cg_certificate_source="analytic_condition_bound_and_explicit_residual",
            smoothness_source="global_analytic_scaled_tanh_bound",
            cg_error_bound=cg_error if method == "full_cg" else 0.0,
            trust_region_radius=trust_radius,
            certificate_failure_probability=0.0,
            **kappa_arguments,
        )
        excitation_active = n_history >= active_rank
        excitation_denominator = (
            ridge + excitation_per_sample * n_history
            if excitation_active
            else ridge
        )
        chi_excitation = float(
            L_g * math.sqrt(snapshot.q_t) / (noise_std * math.sqrt(excitation_denominator))
        )
        psi_excitation = float(
            (optimizer_residual_schedule + snapshot.m_bar_t)
            / math.sqrt(excitation_denominator)
        )
        gamma_rank_bound = _rank_information_bound(
            n_history, active_rank, G, ridge, variance
        )
        beta_rank = float(
            math.sqrt(gamma_rank_bound + 2.0 * math.log(1.0 / delta))
            + math.sqrt(ridge) * teacher_norm
            + math.sqrt(snapshot.f_bar_prior) / noise_std
        )
        transfer_excitation = analytic_kappa * (1.0 + chi_excitation) ** 2
        cg_iterations = (0, 0)
        cg_relative_residual = 0.0
        cg_residual_certificate = 0.0
        cg_energy_error_audit = 0.0
        cg_seconds = 0.0
        action_gradients_ambient = action_gradients @ environment.embedding.T
        if method == "full_cg":
            condition_bound = 1.0 + n_history * G**2 / (ridge * variance)
            operator = CurvatureOperator(
                current_ambient_gradients,
                damping=ridge,
                noise_variance=variance,
            )
            cg_started = time.perf_counter()
            cg_result = certified_cg_widths(
                operator,
                action_gradients_ambient,
                condition_upper_bound=condition_bound,
                energy_error_bound=cg_error,
                max_iterations=cg_max_iterations,
            )
            cg_seconds = time.perf_counter() - cg_started
            widths_squared = np.asarray(cg_result.widths_squared)
            cg_iterations = cg_result.iterations
            cg_relative_residual = max(cg_result.relative_residuals, default=0.0)
            cg_residual_certificate = max(
                cg_result.residual_certificates, default=0.0
            )
            exact_active_solutions = np.linalg.solve(current_active, action_gradients.T).T
            exact_ambient_solutions = exact_active_solutions @ environment.embedding.T
            energy_errors: list[float] = []
            for exact, approximate in zip(
                exact_ambient_solutions, cg_result.solutions, strict=True
            ):
                difference = exact - approximate
                denominator = float(exact @ operator.matvec(exact))
                numerator = float(difference @ operator.matvec(difference))
                energy_errors.append(math.sqrt(max(numerator, 0.0) / denominator))
            cg_energy_error_audit = max(energy_errors, default=0.0)
            round_sample_cvps = n_history * sum(cg_iterations)
            cumulative_sample_cvps += round_sample_cvps
        else:
            widths_squared = _widths_for_operator(
                representation,
                chosen_operator,
                action_gradients,
                environment.embedding,
            )
            condition_bound = 1.0
            round_sample_cvps = 0
        if method == "greedy":
            scores = action_centers.copy()
            bonuses = np.zeros(2, dtype=np.float64)
        else:
            cg_inflation = 1.0 / math.sqrt(1.0 - (cg_error if method == "full_cg" else 0.0))
            bonuses = (
                (beta_rank + psi_excitation)
                * math.sqrt(transfer_excitation)
                * cg_inflation
                * np.sqrt(np.maximum(widths_squared, 0.0))
            )
            scores = action_centers + bonuses
        action = int(np.argmax(scores))
        certificate_state.commit_action_selection(action, widths_squared)

        # Teacher values and exact spectral quantities below are audit-only.
        reward, realized_noise, true_means, optimal_action = environment.reward_and_audit(
            round_index, action
        )
        theta_star = environment.teacher_for_posthoc_audit()
        instantaneous_regret = float(true_means[optimal_action] - true_means[action])
        cumulative_regret += instantaneous_regret
        optimism_violation_count = int(np.count_nonzero(scores + 1.0e-12 < true_means))
        optimism_failures += optimism_violation_count
        exact_widths_current = _widths_for_operator(
            "active_dense", current_active, action_gradients, environment.embedding
        )
        exact_widths_chosen = _widths_for_operator(
            representation, chosen_operator, action_gradients, environment.embedding
        )
        gamma_exact = _logdet_ratio(frozen_active, ridge)
        if n_history:
            delta_gradients = current_gradients - frozen_gradients
            exact_chi = float(
                np.linalg.norm(
                    _inverse_root(frozen_active) @ delta_gradients.T / noise_std,
                    ord=2,
                )
            )
            current_history_means = scaled_tanh_mean(
                theta, history_features, network_width
            )
            mismatch = np.zeros(active_rank, dtype=np.float64)
            for old_theta, old_reward, old_mean, old_gradient, current_gradient, current_mean in zip(
                history_thetas,
                history_rewards,
                history_collection_means,
                frozen_gradients,
                current_gradients,
                current_history_means,
                strict=True,
            ):
                gradient_delta = current_gradient - old_gradient
                bar_mean = old_mean + float(old_gradient @ (theta - old_theta))
                remainder = float(current_mean - bar_mean)
                bar_residual = float(bar_mean - old_reward)
                mismatch += (
                    bar_residual * gradient_delta
                    + remainder * old_gradient
                    + remainder * gradient_delta
                )
            mismatch /= variance
        else:
            exact_chi = 0.0
            mismatch = np.zeros(active_rank, dtype=np.float64)
        exact_mismatch_whitened = math.sqrt(
            max(float(mismatch @ np.linalg.solve(frozen_active, mismatch)), 0.0)
        )
        psi_float64_audit = (
            optimizer_residual_float64_audit / math.sqrt(ridge)
            + exact_mismatch_whitened
        )
        linearization = (
            true_means
            - action_centers
            - action_gradients @ (theta_star - theta)
        )
        epsilon_true = float(np.max(np.abs(linearization)))
        collection_remainder = float(linearization[action])
        true_f += collection_remainder**2
        true_e += epsilon_true
        update = certificate_state.update_after_reward(
            theta,
            float(action_centers[action] - reward),
            snapshot.epsilon_lin_bar_t,
        )
        played_width_squared = float(widths_squared[action])
        exact_played_width_squared = float(exact_widths_chosen[action])
        dynamic_increment = math.log1p(exact_played_width_squared / variance)
        dynamic_lambda += dynamic_increment
        endpoint_logdet_before = _operator_logdet(
            representation, chosen_operator, ridge
        )

        played_feature = action_features[action].copy()
        played_frozen_gradient = action_gradients[action].copy()
        history_features = np.vstack([history_features, played_feature])
        history_rewards = np.append(history_rewards, reward)
        history_thetas = np.vstack([history_thetas, theta.copy()])
        history_collection_means = np.append(
            history_collection_means, action_centers[action]
        )
        frozen_gradients = np.vstack([frozen_gradients, played_frozen_gradient])
        theta_before_update = theta.copy()
        theta, zeta_next, strong_convexity_next, optimizer_iterations_used = (
            optimize_separable_cumulative_loss(
                theta,
                history_features,
                history_rewards,
                network_width=network_width,
                ridge=ridge,
                noise_variance=variance,
                trust_radius=trust_radius,
                maximum_iterations=optimizer_iterations,
                gradient_tolerance=optimizer_tolerance,
            )
        )
        optimizer_increment = float(np.linalg.norm(theta - theta_before_update))
        next_current_gradients = scaled_tanh_gradients(
            theta, history_features, network_width
        )
        next_current_active = _operator_matrix(
            next_current_gradients, ridge=ridge, noise_variance=variance
        )
        next_frozen_active = _operator_matrix(
            frozen_gradients, ridge=ridge, noise_variance=variance
        )
        next_window_length = (
            _window_size(round_number + 1, window_exponent)
            if window_exponent is not None
            else history_features.shape[0]
        )
        next_window_gradients = (
            next_current_gradients[-next_window_length:]
            if next_window_length
            else next_current_gradients[:0]
        )
        next_window_active = _operator_matrix(
            next_window_gradients, ridge=ridge, noise_variance=variance
        )
        next_ambient_gradients = next_current_gradients @ environment.embedding.T
        next_representation, next_chosen_operator = _chosen_operator(
            method,
            current_active=next_current_active,
            frozen_active=next_frozen_active,
            window_active=next_window_active,
            current_ambient_gradients=next_ambient_gradients,
            embedding=environment.embedding,
            ridge=ridge,
            noise_variance=variance,
        )
        assert next_representation == representation
        if representation == "active_dense":
            played_active_gradient = action_gradients[action]
            current_plus = chosen_operator + np.outer(
                played_active_gradient, played_active_gradient
            ) / variance
            refresh_norm_audit = _relative_refresh_norm(
                current_plus, next_chosen_operator
            )
            refresh_logdet = _operator_logdet(
                next_representation, next_chosen_operator, ridge
            ) - _logdet_ratio(current_plus, ridge)
        else:
            played_ambient_gradient = action_gradients_ambient[action]
            logdet_current_plus = endpoint_logdet_before + math.log1p(
                float(np.sum(played_ambient_gradient**2 / chosen_operator)) / variance
            )
            refresh_logdet = _operator_logdet(
                next_representation, next_chosen_operator, ridge
            ) - logdet_current_plus
            refresh_norm_audit = None
        variation_charge += max(-refresh_logdet, 0.0)
        current_excitation_denominator = (
            ridge + excitation_per_sample * round_number
            if round_number >= active_rank
            else ridge
        )
        nu_bound = float(
            2.0
            * round_number
            * G
            * L_g
            * optimizer_increment
            / (variance * current_excitation_denominator)
        )
        if method not in {"exact_current", "full_cg", "greedy"}:
            nu_bound = 0.0
        if nu_bound < 1.0 and refresh_upper_valid:
            refresh_log_upper += active_rank * math.log(1.0 / (1.0 - nu_bound))
        elif nu_bound >= 1.0:
            refresh_upper_valid = False
        endpoint_logdet_after = _operator_logdet(
            next_representation, next_chosen_operator, ridge
        )
        dynamic_upper = endpoint_logdet_after + variation_charge
        theorem_event_checks = {
            "rank_information": gamma_exact <= gamma_rank_bound + 1.0e-10,
            "chi_lambda": exact_chi <= snapshot.chi_bar_t + 1.0e-10,
            "chi_excitation": exact_chi <= chi_excitation + 1.0e-10,
            "psi_lambda": psi_float64_audit <= snapshot.psi_bar_t + 1.0e-10,
            "psi_excitation": psi_float64_audit <= psi_excitation + 1.0e-10,
            "linearization": epsilon_true <= snapshot.epsilon_lin_bar_t + 1.0e-10,
            "optimizer_residual": optimizer_residual_float64_audit
            <= optimizer_residual_schedule + 1.0e-12,
            "F": true_f - collection_remainder**2 <= snapshot.f_bar_prior + 1.0e-10,
            "dynamic_width": dynamic_lambda <= dynamic_upper + 1.0e-9,
            "cg": cg_energy_error_audit <= (cg_error if method == "full_cg" else 0.0)
            + 1.0e-10,
        }
        record: dict[str, Any] = {
            "method": method,
            "round": round_number,
            "ambient_dimension": ambient_dimension,
            "active_rank": active_rank,
            "network_width": network_width,
            "action": action,
            "optimal_action_audit": optimal_action,
            "reward": reward,
            "realized_noise_audit": realized_noise,
            "instantaneous_regret_audit": instantaneous_regret,
            "cumulative_regret_audit": cumulative_regret,
            "scores_pre_action": scores.tolist(),
            "bonuses_pre_action": bonuses.tolist(),
            "selected_width_squared_pre_action": played_width_squared,
            "selected_exact_operator_width_squared_audit": exact_played_width_squared,
            "exact_current_widths_squared_audit": exact_widths_current.tolist(),
            "dynamic_width_increment": dynamic_increment,
            "Lambda_dynamic": dynamic_lambda,
            "endpoint_logdet": endpoint_logdet_after,
            "variation_charge": variation_charge,
            "dynamic_width_upper": dynamic_upper,
            "relative_refresh_norm_float64_audit": refresh_norm_audit,
            "nu_analytic_upper": nu_bound,
            "refresh_log_upper": refresh_log_upper if refresh_upper_valid else None,
            "refresh_log_upper_valid": refresh_upper_valid,
            "gamma_frozen_float64_audit": gamma_exact,
            "gamma_rank_upper": gamma_rank_bound,
            "lambda_min_current_active_float64_audit": float(
                np.min(np.linalg.eigvalsh(current_active))
            ),
            "lambda_min_frozen_active_float64_audit": float(
                np.min(np.linalg.eigvalsh(frozen_active))
            ),
            "lambda_min_window_active_float64_audit": float(
                np.min(np.linalg.eigvalsh(window_active))
            ),
            "window_length": window_length,
            "window_exponent": window_exponent,
            "excitation_floor_pre_action": excitation_denominator,
            "excitation_schedule_active": excitation_active,
            "optimizer_increment": optimizer_increment,
            "scaled_optimizer_increment": round_number * optimizer_increment,
            "optimizer_residual_pre_action_float64_audit": optimizer_residual_float64_audit,
            "optimizer_residual_schedule_pre_action": optimizer_residual_schedule,
            "optimizer_residual_next": zeta_next,
            "optimizer_iterations": optimizer_iterations_used,
            "strong_convexity_min_eigenvalue_float64_audit": strong_convexity_audit,
            "estimation_error_float64_audit": float(np.linalg.norm(theta_before_update - theta_star)),
            "Q_t": snapshot.q_t,
            "chi_exact_float64_audit": exact_chi,
            "chi_lambda_upper": snapshot.chi_bar_t,
            "chi_excitation_upper": chi_excitation,
            "psi_float64_audit": psi_float64_audit,
            "psi_lambda_upper": snapshot.psi_bar_t,
            "psi_excitation_upper": psi_excitation,
            "M_upper": snapshot.m_bar_t,
            "E_true_float64_audit": true_e,
            "F_true_float64_audit": true_f,
            "E_upper": update.e_bar_after_update,
            "F_upper": update.f_bar_after_update,
            "beta_rank_pre_action": beta_rank,
            "transfer_factor_pre_action": transfer_excitation,
            "optimism_violation_count_audit": optimism_violation_count,
            "cg_condition_upper": condition_bound,
            "cg_iterations": list(cg_iterations),
            "cg_relative_residual": cg_relative_residual,
            "cg_residual_certificate": cg_residual_certificate,
            "cg_energy_error_float64_audit": cg_energy_error_audit,
            "sample_cvp_count": round_sample_cvps,
            "cumulative_sample_cvp_count": cumulative_sample_cvps,
            "cg_seconds": cg_seconds,
            "round_seconds": time.perf_counter() - round_started,
            "theorem_event_checks_float64_audit": theorem_event_checks,
            "all_float64_audit_checks_hold": all(theorem_event_checks.values()),
            "audit_semantics": "post_action_float64_point_estimates_not_enclosures",
        }
        records.append(record)
        optimizer_residual_float64_audit = zeta_next
        strong_convexity_audit = strong_convexity_next

    summary = {
        "schema_version": 1,
        "experiment": "theory_scaling",
        "method": method,
        "seed": int(seed),
        "ambient_dimension": ambient_dimension,
        "active_rank": active_rank,
        "horizon": rounds,
        "network_width": network_width,
        "stream_sha256": environment.stream_sha256,
        "cumulative_regret": cumulative_regret,
        "Lambda_dynamic": dynamic_lambda,
        "endpoint_logdet": records[-1]["endpoint_logdet"],
        "variation_charge": variation_charge,
        "gamma_rank_upper": records[-1]["gamma_rank_upper"],
        "optimism_failures": optimism_failures,
        "all_float64_audit_checks_hold": all(
            bool(record["all_float64_audit_checks_hold"]) for record in records
        ),
        "sample_cvp_count": cumulative_sample_cvps,
        "runtime_seconds": time.perf_counter() - run_started,
        "certification_category": "posthoc_theorem_event_verified",
        "numerical_semantics": (
            "policy schedules are analytic and pre-action; dense spectral and teacher "
            "checks are post-action float64 audits, not verified enclosures"
        ),
    }
    return TheoryScalingRun(
        seed=int(seed),
        method=method,
        ambient_dimension=ambient_dimension,
        active_rank=active_rank,
        horizon=rounds,
        stream_sha256=environment.stream_sha256,
        records=tuple(records),
        summary=summary,
    )


def scaling_cells(config: Mapping[str, Any]) -> tuple[tuple[int, int, int], ...]:
    grid = _section(config, "grid")
    dimensions = tuple(int(value) for value in grid.get("ambient_dimensions", ()))
    ranks = tuple(int(value) for value in grid.get("active_ranks", ()))
    horizons = tuple(int(value) for value in grid.get("horizons", ()))
    if not dimensions or not ranks or not horizons:
        raise ValueError("grid dimensions, ranks, and horizons must be nonempty")
    return tuple(
        (dimension, rank, horizon)
        for dimension in dimensions
        for rank in ranks
        if rank <= dimension
        for horizon in horizons
    )


def save_theory_scaling_run(
    run: TheoryScalingRun,
    config: Mapping[str, Any],
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    output = Path(destination)
    summary_path = output / "summary.jsonl"
    if overwrite:
        for path in (output / "manifest.jsonl", output / "raw.jsonl", summary_path):
            if path.exists():
                path.unlink()
    elif summary_path.exists():
        raise FileExistsError(f"refusing to overwrite {summary_path}")
    with ExperimentLogger(
        output,
        config,
        run.seed,
        repository=Path(__file__).resolve().parents[1],
        overwrite=False,
    ) as logger:
        for round_index, record in enumerate(run.records):
            logger.log_round(round_index, record)
    append_jsonl(summary_path, run.summary)
    return output


def run_configured_experiment(
    config: Mapping[str, Any],
    *,
    seed_set: str,
    output_root: str | Path,
    methods: Sequence[str] | None = None,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    selected_methods = tuple(methods or _section(config, "policy").get("methods", METHODS))
    destinations: list[Path] = []
    for seed in get_seed_set(config, seed_set):
        for dimension, rank, horizon in scaling_cells(config):
            for method in selected_methods:
                run_config = json.loads(json.dumps(config))
                run_config["execution"] = {
                    "seed_set": seed_set,
                    "method": method,
                    "ambient_dimension": dimension,
                    "active_rank": rank,
                    "horizon": horizon,
                    "teacher_available_to_policy": False,
                    "float64_audits_are_enclosures": False,
                }
                run = run_theory_scaling_cell(
                    run_config,
                    seed,
                    method=method,
                    ambient_dimension=dimension,
                    active_rank=rank,
                    horizon=horizon,
                )
                destination = (
                    Path(output_root)
                    / str(config.get("profile", "unknown"))
                    / seed_set
                    / f"d-{dimension}_r-{rank}_T-{horizon}"
                    / method
                    / f"seed-{seed}"
                )
                save_theory_scaling_run(
                    run, run_config, destination, overwrite=overwrite
                )
                destinations.append(destination)
    return tuple(destinations)


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument(
        "--seed-set", choices=("development", "tuning", "evaluation"), default="development"
    )
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--method", action="append", choices=METHODS)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    config = load_config(args.config, profile=args.profile)
    output_root = args.output_root or Path(str(config["output_root"]))
    paths = run_configured_experiment(
        config,
        seed_set=args.seed_set,
        output_root=output_root,
        methods=args.method,
        overwrite=args.overwrite,
    )
    print(json.dumps({"runs": len(paths), "output_root": str(output_root)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = [
    "CyclicActiveTanhEnvironment",
    "DEFAULT_CONFIG_PATH",
    "METHODS",
    "TheoryScalingRun",
    "deterministic_embedding",
    "optimize_separable_cumulative_loss",
    "run_configured_experiment",
    "run_theory_scaling_cell",
    "save_theory_scaling_run",
    "scaled_tanh_constants",
    "scaled_tanh_gradients",
    "scaled_tanh_mean",
    "scaling_cells",
]
