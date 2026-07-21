"""Executed tanh-link Gaussian bandit with predictable path certificates."""

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
from .curvature_operators import CurvatureOperator, conjugate_gradient
from .logging_utils import (
    ExperimentLogger,
    append_jsonl,
    canonical_json,
    derive_seed,
    seed_everything,
)
from .path_certificates import PathCertificateState


FloatArray = NDArray[np.float64]
TANH_SECOND_DERIVATIVE_MAX = 4.0 / (3.0 * math.sqrt(3.0))
CENTERS = ("original", "corrected")
DEFAULT_CONFIG_PATH = Path(__file__).with_name("configs") / "certified_tanh.yaml"


def _positive(value: Any, *, name: str) -> float:
    checked = float(value)
    if not np.isfinite(checked) or checked <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return checked


def _nonnegative(value: Any, *, name: str) -> float:
    checked = float(value)
    if not np.isfinite(checked) or checked < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return checked


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    checked = int(value)
    if checked <= 0:
        raise ValueError(f"{name} must be positive")
    return checked


def _section(config: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = config.get(name, {})
    if not isinstance(value, Mapping):
        raise ValueError(f"config.{name} must be a mapping")
    return value


def tanh_mean(theta: ArrayLike, features: ArrayLike) -> FloatArray:
    parameters = np.asarray(theta, dtype=np.float64)
    design = np.asarray(features, dtype=np.float64)
    return np.asarray(np.tanh(design @ parameters), dtype=np.float64)


def tanh_gradients(theta: ArrayLike, features: ArrayLike) -> FloatArray:
    design = np.asarray(features, dtype=np.float64)
    means = tanh_mean(theta, design)
    return np.asarray((1.0 - means * means)[:, None] * design, dtype=np.float64)


def analytic_tanh_constants(feature_bound: float) -> tuple[float, float, float]:
    bound = _positive(feature_bound, name="feature_bound")
    lipschitz = TANH_SECOND_DERIVATIVE_MAX * bound * bound
    return bound, lipschitz, lipschitz


class TanhBanditEnvironment:
    """Seeded bounded features and hidden Gaussian reward noise."""

    def __init__(
        self,
        *,
        seed: int,
        rounds: int,
        action_count: int,
        dimension: int,
        feature_bound: float,
        noise_std: float,
        theta_star: ArrayLike,
    ) -> None:
        self.rounds = _positive_int(rounds, name="rounds")
        self.action_count = _positive_int(action_count, name="action_count")
        self.dimension = _positive_int(dimension, name="dimension")
        self.feature_bound = _positive(feature_bound, name="feature_bound")
        self.noise_std = _positive(noise_std, name="noise_std")
        teacher = np.asarray(theta_star, dtype=np.float64)
        if teacher.shape != (self.dimension,) or not np.all(np.isfinite(teacher)):
            raise ValueError("theta_star has the wrong shape or non-finite values")
        self._theta_star = teacher.copy()

        rng = np.random.default_rng(seed)
        raw = rng.normal(size=(self.rounds, self.action_count, self.dimension))
        norms = np.linalg.norm(raw, axis=2, keepdims=True)
        if np.any(norms == 0.0):  # probability zero, but deterministic failure is clearer.
            raise FloatingPointError("environment sampled a zero feature direction")
        self._features = np.asarray(self.feature_bound * raw / norms, dtype=np.float64)
        self._noise = np.asarray(
            rng.normal(0.0, self.noise_std, size=(self.rounds, self.action_count)),
            dtype=np.float64,
        )
        digest = hashlib.sha256()
        digest.update(np.ascontiguousarray(self._features, dtype="<f8").tobytes())
        digest.update(np.ascontiguousarray(self._noise, dtype="<f8").tobytes())
        self.stream_sha256 = digest.hexdigest()

    def features(self, round_index: int) -> FloatArray:
        return self._features[round_index].copy()

    def reward_and_audit(
        self, round_index: int, action: int
    ) -> tuple[float, float, FloatArray, int]:
        features = self._features[round_index]
        true_means = tanh_mean(self._theta_star, features)
        selected_noise = float(self._noise[round_index, action])
        reward = float(true_means[action] + selected_noise)
        return reward, selected_noise, true_means, int(np.argmax(true_means))

    def teacher_for_posthoc_audit(self) -> FloatArray:
        result = self._theta_star.copy()
        result.setflags(write=False)
        return result


@dataclass(frozen=True)
class CertifiedCGWidths:
    widths_squared: FloatArray
    solutions: FloatArray
    iterations: tuple[int, ...]
    relative_residuals: tuple[float, ...]
    residual_certificates: tuple[float, ...]
    condition_upper_bound: float


def certified_policy_scores(
    original_centers: ArrayLike,
    corrected_centers: ArrayLike,
    widths_squared: ArrayLike,
    *,
    center: str,
    beta_bar: float,
    psi_bar: float,
    corrected_center_error_bar: float = 0.0,
    transfer_factor: float,
    cg_error_bound: float,
) -> tuple[FloatArray, FloatArray]:
    """Compute scores from policy-available inputs only."""

    if center not in CENTERS:
        raise ValueError(f"center must be one of {CENTERS}")
    original = np.asarray(original_centers, dtype=np.float64)
    corrected = np.asarray(corrected_centers, dtype=np.float64)
    widths = np.asarray(widths_squared, dtype=np.float64)
    if original.ndim != 1 or corrected.shape != original.shape or widths.shape != original.shape:
        raise ValueError("center and width vectors must have the same one-dimensional shape")
    if not np.all(np.isfinite(original)) or not np.all(np.isfinite(corrected)):
        raise ValueError("centers must be finite")
    if not np.all(np.isfinite(widths)) or np.any(widths < 0.0):
        raise ValueError("widths_squared must be finite and nonnegative")
    beta = _nonnegative(beta_bar, name="beta_bar")
    psi = _nonnegative(psi_bar, name="psi_bar")
    corrected_error = _nonnegative(
        corrected_center_error_bar, name="corrected_center_error_bar"
    )
    transfer = _positive(transfer_factor, name="transfer_factor")
    cg_error = _nonnegative(cg_error_bound, name="cg_error_bound")
    if cg_error >= 1.0:
        raise ValueError("cg_error_bound must be smaller than one")
    omega = beta + psi if center == "original" else beta + corrected_error
    bonuses = np.asarray(
        omega * math.sqrt(transfer / (1.0 - cg_error)) * np.sqrt(widths),
        dtype=np.float64,
    )
    centers = original if center == "original" else corrected
    return np.asarray(centers + bonuses, dtype=np.float64), bonuses


def certified_cg_widths(
    operator: CurvatureOperator,
    action_gradients: ArrayLike,
    *,
    condition_upper_bound: float,
    energy_error_bound: float,
    max_iterations: int,
) -> CertifiedCGWidths:
    gradients = np.asarray(action_gradients, dtype=np.float64)
    if gradients.ndim != 2 or gradients.shape[1] != operator.dimension:
        raise ValueError("action_gradients has the wrong shape")
    kappa = _positive(condition_upper_bound, name="condition_upper_bound")
    epsilon = _positive(energy_error_bound, name="energy_error_bound")
    if epsilon >= 1.0:
        raise ValueError("energy_error_bound must be smaller than one")
    budget = _positive_int(max_iterations, name="max_iterations")
    residual_target = epsilon / (4.0 * math.sqrt(kappa))

    widths: list[float] = []
    solutions: list[FloatArray] = []
    iterations: list[int] = []
    relative_residuals: list[float] = []
    certificates: list[float] = []
    for gradient in gradients:
        rhs_norm = float(np.linalg.norm(gradient))
        if rhs_norm == 0.0:
            solution = np.zeros(operator.dimension, dtype=np.float64)
            widths.append(0.0)
            solutions.append(solution)
            iterations.append(0)
            relative_residuals.append(0.0)
            certificates.append(0.0)
            continue
        result = conjugate_gradient(
            operator,
            gradient,
            tolerance=residual_target,
            absolute_tolerance=0.0,
            max_iterations=budget,
            raise_on_nonconvergence=True,
        )
        solution = np.asarray(result.solution, dtype=np.float64)
        explicit_residual = gradient - operator.matvec(solution)
        relative_residual = float(np.linalg.norm(explicit_residual) / rhs_norm)
        certificate = float(math.sqrt(kappa) * relative_residual)
        tolerance = 1024.0 * np.finfo(np.float64).eps * max(1.0, epsilon)
        if certificate > epsilon + tolerance:
            raise RuntimeError(
                "CG failed the analytic original-system residual certificate; "
                "no uncertified fallback is permitted"
            )
        width_squared = float(gradient @ solution)
        if not np.isfinite(width_squared) or width_squared < 0.0:
            raise FloatingPointError("CG produced an invalid predictive width")
        widths.append(width_squared)
        solutions.append(solution.copy())
        iterations.append(int(result.iterations))
        relative_residuals.append(relative_residual)
        certificates.append(certificate)

    widths_array = np.asarray(widths, dtype=np.float64)
    solutions_array = np.stack(solutions, axis=0)
    widths_array.setflags(write=False)
    solutions_array.setflags(write=False)
    return CertifiedCGWidths(
        widths_squared=widths_array,
        solutions=solutions_array,
        iterations=tuple(iterations),
        relative_residuals=tuple(relative_residuals),
        residual_certificates=tuple(certificates),
        condition_upper_bound=kappa,
    )


def _objective_and_gradient(
    theta: FloatArray,
    history_features: FloatArray,
    rewards: FloatArray,
    *,
    ridge: float,
    noise_variance: float,
) -> tuple[float, FloatArray]:
    if history_features.shape[0] == 0:
        return 0.5 * ridge * float(theta @ theta), ridge * theta
    means = tanh_mean(theta, history_features)
    residuals = means - rewards
    gradients = tanh_gradients(theta, history_features)
    objective = float(
        0.5 * (residuals @ residuals) / noise_variance
        + 0.5 * ridge * (theta @ theta)
    )
    gradient = np.asarray(
        gradients.T @ residuals / noise_variance + ridge * theta,
        dtype=np.float64,
    )
    return objective, gradient


def _project_ball(theta: FloatArray, radius: float) -> FloatArray:
    norm = float(np.linalg.norm(theta))
    if norm <= radius:
        return theta.copy()
    return np.asarray(theta * (radius / norm), dtype=np.float64)


def optimize_projected(
    theta: FloatArray,
    history_features: FloatArray,
    rewards: FloatArray,
    *,
    ridge: float,
    noise_variance: float,
    radius: float,
    learning_rate: float,
    steps: int,
    maximum_step_norm: float,
) -> FloatArray:
    current = theta.copy()
    for _ in range(steps):
        objective, gradient = _objective_and_gradient(
            current,
            history_features,
            rewards,
            ridge=ridge,
            noise_variance=noise_variance,
        )
        gradient_norm = float(np.linalg.norm(gradient))
        if gradient_norm == 0.0:
            break
        step_size = learning_rate
        accepted = False
        for _ in range(30):
            step = step_size * gradient
            step_norm = float(np.linalg.norm(step))
            if step_norm > maximum_step_norm:
                step *= maximum_step_norm / step_norm
            candidate = _project_ball(current - step, radius)
            candidate_objective, _ = _objective_and_gradient(
                candidate,
                history_features,
                rewards,
                ridge=ridge,
                noise_variance=noise_variance,
            )
            if candidate_objective <= objective + 1.0e-14:
                current = candidate
                accepted = True
                break
            step_size *= 0.5
        if not accepted:
            break
    return np.asarray(current, dtype=np.float64)


def _inverse_root(matrix: FloatArray) -> FloatArray:
    values, vectors = np.linalg.eigh(0.5 * (matrix + matrix.T))
    if np.any(values <= 0.0):
        raise ArithmeticError("certificate audit matrix is not SPD")
    return np.asarray((vectors * (1.0 / np.sqrt(values))) @ vectors.T)


def _logdet_ratio(matrix: FloatArray, ridge: float) -> float:
    sign, value = np.linalg.slogdet(matrix)
    if sign <= 0.0 or not np.isfinite(value):
        raise ArithmeticError("certificate audit matrix has invalid determinant")
    return float(value - matrix.shape[0] * math.log(ridge))


@dataclass(frozen=True)
class CertifiedTanhRun:
    seed: int
    center: str
    records: tuple[dict[str, Any], ...]
    summary: dict[str, Any]

    def deterministic_signature(self) -> str:
        stable = [
            {
                key: value
                for key, value in record.items()
                if not key.endswith("_seconds")
            }
            for record in self.records
        ]
        return hashlib.sha256(canonical_json(stable).encode("ascii")).hexdigest()


def run_certified_policy(
    config: Mapping[str, Any],
    seed: int,
    *,
    center: str,
) -> CertifiedTanhRun:
    """Execute one policy; no teacher or post-hoc quantity enters its scores."""

    if center not in CENTERS:
        raise ValueError(f"center must be one of {CENTERS}")
    seed_everything(int(seed))
    environment_config = _section(config, "environment")
    policy_config = _section(config, "policy")
    cg_config = _section(config, "cg")
    optimizer_config = _section(config, "optimizer")

    rounds = _positive_int(config.get("rounds"), name="rounds")
    dimension = _positive_int(
        environment_config.get("feature_dimension"), name="feature_dimension"
    )
    action_count = _positive_int(
        environment_config.get("action_count"), name="action_count"
    )
    base_bound = _positive(
        environment_config.get("base_feature_bound"), name="base_feature_bound"
    )
    nonlinearity_scale = _positive(
        environment_config.get("nonlinearity_scale"), name="nonlinearity_scale"
    )
    feature_bound = base_bound * nonlinearity_scale
    noise_std = _positive(environment_config.get("noise_std"), name="noise_std")
    variance = noise_std * noise_std
    theta_star = np.asarray(environment_config.get("teacher_theta"), dtype=np.float64)
    if theta_star.shape != (dimension,):
        raise ValueError("teacher_theta dimension does not match feature_dimension")
    S = _positive(environment_config.get("theta_radius_S"), name="theta_radius_S")
    if float(np.linalg.norm(theta_star)) > S:
        raise ValueError("teacher_theta lies outside theta_radius_S")
    ridge = _positive(policy_config.get("ridge"), name="ridge")
    delta = _positive(policy_config.get("delta"), name="delta")
    if delta >= 1.0:
        raise ValueError("delta must be smaller than one")
    trust_radius = _positive(
        policy_config.get("trust_region_radius"), name="trust_region_radius"
    )
    epsilon_cg = _positive(
        cg_config.get("relative_energy_error"), name="relative_energy_error"
    )
    cg_max_iterations = _positive_int(
        cg_config.get("max_iterations"), name="max_iterations"
    )
    learning_rate = _positive(
        optimizer_config.get("learning_rate"), name="learning_rate"
    )
    optimizer_steps = _positive_int(
        optimizer_config.get("steps_per_update"), name="steps_per_update"
    )
    update_frequency = _positive_int(
        optimizer_config.get("update_frequency"), name="update_frequency"
    )
    maximum_step_norm = _positive(
        optimizer_config.get("maximum_step_norm"), name="maximum_step_norm"
    )
    G, L_mu, L_g = analytic_tanh_constants(feature_bound)

    environment = TanhBanditEnvironment(
        seed=derive_seed(int(seed), "certified_tanh", "environment"),
        rounds=rounds,
        action_count=action_count,
        dimension=dimension,
        feature_bound=feature_bound,
        noise_std=noise_std,
        theta_star=theta_star,
    )
    del theta_star  # The teacher remains encapsulated in the evaluator.
    certificate_state = PathCertificateState(dimension)
    theta = np.zeros(dimension, dtype=np.float64)
    history_features = np.empty((0, dimension), dtype=np.float64)
    history_rewards = np.empty(0, dtype=np.float64)
    history_parameters = np.empty((0, dimension), dtype=np.float64)
    history_collection_means = np.empty(0, dtype=np.float64)
    frozen_gradients = np.empty((0, dimension), dtype=np.float64)
    cbar = ridge * np.eye(dimension, dtype=np.float64)

    records: list[dict[str, Any]] = []
    true_F = 0.0
    exact_lambda = 0.0
    observable_lambda = 0.0
    cumulative_S = 0.0
    cumulative_regret = 0.0
    optimism_failures = 0
    confidence_failures = 0
    certificate_failures = 0
    cumulative_certificate_seconds = 0.0
    cumulative_cg_seconds = 0.0
    run_started = time.perf_counter()

    for round_index in range(rounds):
        round_started = time.perf_counter()
        round_number = round_index + 1
        features = environment.features(round_index)
        action_means = tanh_mean(theta, features)
        action_gradients = tanh_gradients(theta, features)
        certificate_started = time.perf_counter()
        replayed_gradients = (
            tanh_gradients(theta, history_features)
            if history_features.shape[0]
            else np.empty((0, dimension), dtype=np.float64)
        )
        current_operator = CurvatureOperator(
            replayed_gradients,
            damping=ridge,
            noise_variance=variance,
        )
        current_history_means = (
            tanh_mean(theta, history_features)
            if history_features.shape[0]
            else np.empty(0, dtype=np.float64)
        )
        _, objective_gradient = _objective_and_gradient(
            theta,
            history_features,
            history_rewards,
            ridge=ridge,
            noise_variance=variance,
        )
        zeta_t = float(np.linalg.norm(objective_gradient))

        if history_features.shape[0]:
            pseudo_offsets = (
                history_rewards
                - history_collection_means
                + np.einsum(
                    "ij,ij->i", frozen_gradients, history_parameters
                )
            )
            theta_hat_rhs = frozen_gradients.T @ pseudo_offsets / variance
            theta_hat = np.linalg.solve(cbar, theta_hat_rhs)
            theta_hat_normal_residual = theta_hat_rhs - cbar @ theta_hat
        else:
            theta_hat = np.zeros(dimension, dtype=np.float64)
            theta_hat_normal_residual = np.zeros(dimension, dtype=np.float64)
        corrected_center_error_bar = float(
            np.nextafter(
                np.linalg.norm(theta_hat_normal_residual)
                * (1.0 + 1024.0 * np.finfo(np.float64).eps * max(1, dimension)),
                math.inf,
            )
            / math.sqrt(ridge)
        )
        corrected_means = action_means + action_gradients @ (theta_hat - theta)

        condition_upper_bound = float(
            1.0
            + history_features.shape[0] * G * G / (ridge * variance)
        )
        snapshot = certificate_state.pre_action_schedule(
            theta,
            L_g=L_g,
            L_mu=L_mu,
            G=G,
            sigma=noise_std,
            lambda_=ridge,
            S=S,
            delta=delta,
            zeta_t=zeta_t,
            operator_mode="exact_full",
            optimizer_residual_source="exact_full_objective_gradient_norm",
            cg_certificate_source="analytic_outer_product_condition_bound_and_explicit_residual",
            smoothness_source="global_analytic_tanh_Hessian_bound",
            cg_error_bound=epsilon_cg,
            trust_region_radius=trust_radius,
            certificate_failure_probability=0.0,
        )
        cg_started = time.perf_counter()
        cg = certified_cg_widths(
            current_operator,
            action_gradients,
            condition_upper_bound=condition_upper_bound,
            energy_error_bound=epsilon_cg,
            max_iterations=cg_max_iterations,
        )
        cg_seconds = time.perf_counter() - cg_started
        cumulative_cg_seconds += cg_seconds
        omega = (
            snapshot.omega_original_t
            if center == "original"
            else snapshot.omega_corrected_t + corrected_center_error_bar
        )
        scores, bonuses = certified_policy_scores(
            action_means,
            corrected_means,
            cg.widths_squared,
            center=center,
            beta_bar=snapshot.beta_bar_t,
            psi_bar=snapshot.psi_bar_t,
            corrected_center_error_bar=corrected_center_error_bar,
            transfer_factor=snapshot.transfer_factor,
            cg_error_bound=epsilon_cg,
        )
        certificate_seconds = time.perf_counter() - certificate_started
        cumulative_certificate_seconds += certificate_seconds
        center_values = action_means if center == "original" else corrected_means
        action = int(np.argmax(scores))
        commitment = certificate_state.commit_action_selection(
            action, cg.widths_squared
        )

        # Everything below this line is post-selection.  Teacher-dependent
        # values are audit-only and never alter the score or selected action.
        reward, realized_noise, true_means, optimal_action = (
            environment.reward_and_audit(round_index, action)
        )
        theta_star_audit = environment.teacher_for_posthoc_audit()
        instantaneous_regret = float(true_means[optimal_action] - true_means[action])
        cumulative_regret += instantaneous_regret
        optimism_violation_count = int(np.count_nonzero(scores + 1.0e-12 < true_means))
        optimism_failures += optimism_violation_count

        current_curvature = current_operator.to_dense()
        exact_solutions = np.linalg.solve(current_curvature, action_gradients.T).T
        exact_widths_squared = np.einsum(
            "ij,ij->i", action_gradients, exact_solutions
        )
        frozen_solutions = np.linalg.solve(cbar, action_gradients.T).T
        frozen_widths_squared = np.einsum(
            "ij,ij->i", action_gradients, frozen_solutions
        )
        explicit_energy_errors: list[float] = []
        for exact_solution, approximate_solution in zip(
            exact_solutions, cg.solutions, strict=True
        ):
            difference = exact_solution - approximate_solution
            numerator = float(difference @ current_curvature @ difference)
            denominator = float(exact_solution @ current_curvature @ exact_solution)
            explicit_energy_errors.append(
                math.sqrt(max(numerator, 0.0) / denominator)
                if denominator > 0.0
                else 0.0
            )
        max_energy_error = max(explicit_energy_errors, default=0.0)

        if history_features.shape[0]:
            delta_gradients = replayed_gradients - frozen_gradients
            whitened_delta = _inverse_root(cbar) @ delta_gradients.T / noise_std
            exact_chi = float(np.linalg.norm(whitened_delta, ord=2))
            mismatch = np.zeros(dimension, dtype=np.float64)
            for old_theta, old_reward, old_mean, g_s, g_st, mu_current in zip(
                history_parameters,
                history_rewards,
                history_collection_means,
                frozen_gradients,
                replayed_gradients,
                current_history_means,
                strict=True,
            ):
                delta_s = g_st - g_s
                bar_mu = old_mean + float(g_s @ (theta - old_theta))
                e_st = float(mu_current - bar_mu)
                bar_r = float(bar_mu - old_reward)
                mismatch += bar_r * delta_s + e_st * g_s + e_st * delta_s
            mismatch /= variance
        else:
            exact_chi = 0.0
            mismatch = np.zeros(dimension, dtype=np.float64)
        exact_mismatch_norm = float(np.linalg.norm(mismatch))
        exact_psi = float(
            zeta_t / math.sqrt(ridge)
            + math.sqrt(max(float(mismatch @ np.linalg.solve(cbar, mismatch)), 0.0))
        )
        gamma_exact = _logdet_ratio(cbar, ridge)
        beta_exact = float(
            math.sqrt(gamma_exact + 2.0 * math.log(1.0 / delta))
            + math.sqrt(ridge) * S
            + math.sqrt(true_F) / noise_std
        )
        true_linearization = (
            true_means
            - action_means
            - action_gradients @ (theta_star_audit - theta)
        )
        confidence_errors = np.abs(action_gradients @ (theta_hat - theta_star_audit))
        confidence_violation_count = int(
            np.count_nonzero(
                confidence_errors
                > beta_exact * np.sqrt(frozen_widths_squared) + 1.0e-12
            )
        )
        confidence_failures += confidence_violation_count
        centering_discrepancies = np.abs(action_gradients @ (theta - theta_hat))

        checks = {
            "chi": exact_chi <= snapshot.chi_bar_t + 1.0e-11,
            "M": exact_mismatch_norm <= snapshot.m_bar_t + 1.0e-11,
            "psi": exact_psi <= snapshot.psi_bar_t + 1.0e-11,
            "linearization": float(np.max(np.abs(true_linearization)))
            <= snapshot.epsilon_lin_bar_t + 1.0e-11,
            "F": true_F <= snapshot.f_bar_prior + 1.0e-11,
            "gamma": gamma_exact <= snapshot.gamma_hat_prior + 1.0e-11,
            "beta": beta_exact <= snapshot.beta_bar_t + 1.0e-11,
            "transfer": bool(
                np.all(
                    frozen_widths_squared
                    <= snapshot.transfer_factor * exact_widths_squared + 1.0e-11
                )
            ),
            "centering": bool(
                np.all(
                    centering_discrepancies
                    <= snapshot.psi_bar_t * np.sqrt(frozen_widths_squared) + 1.0e-11
                )
            ),
            "corrected_center_solve": bool(
                np.all(
                    np.abs(
                        action_gradients
                        @ np.linalg.solve(cbar, theta_hat_normal_residual)
                    )
                    <= corrected_center_error_bar * np.sqrt(frozen_widths_squared)
                    + 1.0e-11
                )
            ),
            "cg": max_energy_error <= epsilon_cg + 1.0e-11
            and max(cg.residual_certificates, default=0.0) <= epsilon_cg + 1.0e-11,
            "condition": float(np.linalg.cond(current_curvature))
            <= condition_upper_bound + 1.0e-10,
        }
        round_certificate_failures = sum(not value for value in checks.values())
        certificate_failures += round_certificate_failures

        collection_residual = float(action_means[action] - reward)
        update = certificate_state.update_after_reward(
            theta,
            collection_residual,
            snapshot.epsilon_lin_bar_t,
        )
        true_collection_remainder = float(true_linearization[action])
        true_F += true_collection_remainder * true_collection_remainder
        exact_lambda += math.log1p(exact_widths_squared[action] / variance)
        observable_lambda += math.log1p(
            cg.widths_squared[action] / (variance * (1.0 - epsilon_cg))
        )
        cumulative_S += (
            snapshot.cg_inflation_alpha_t**2
            * snapshot.transfer_factor
            * omega**2
        )
        theorem_coefficient = variance + G * G / ridge
        theorem_rhs_exact = float(
            2.0 * math.sqrt(theorem_coefficient * exact_lambda * cumulative_S)
            + 2.0 * certificate_state.E_bar
        )
        theorem_rhs_observable = float(
            2.0
            * math.sqrt(theorem_coefficient * observable_lambda * cumulative_S)
            + 2.0 * certificate_state.E_bar
        )
        maximum_possible_regret = 2.0 * round_number

        played_feature = features[action].copy()
        played_frozen_gradient = action_gradients[action].copy()
        history_features = np.vstack([history_features, played_feature])
        history_rewards = np.append(history_rewards, reward)
        history_parameters = np.vstack([history_parameters, theta.copy()])
        history_collection_means = np.append(
            history_collection_means, action_means[action]
        )
        frozen_gradients = np.vstack([frozen_gradients, played_frozen_gradient])
        cbar = cbar + np.outer(played_frozen_gradient, played_frozen_gradient) / variance

        theta_before_update = theta.copy()
        if round_number % update_frequency == 0:
            theta = optimize_projected(
                theta,
                history_features,
                history_rewards,
                ridge=ridge,
                noise_variance=variance,
                radius=trust_radius,
                learning_rate=learning_rate,
                steps=optimizer_steps,
                maximum_step_norm=maximum_step_norm,
            )
        step_norm = float(np.linalg.norm(theta - theta_before_update))

        record: dict[str, Any] = {
            "round_number": round_number,
            "seed": int(seed),
            "center": center,
            "executed_policy": True,
            "execution_mode": "online_adaptive",
            "policy_type": "nonlinear_tanh_link_full_GGN_CG_UCB",
            "certification_category": "posthoc_theorem_event_verified",
            "mathematical_schedule_status": "all_theorem_schedules_predictable_pre_action",
            "numerical_enclosure_status": "float64_point_residuals_not_interval_verified",
            "posthoc_fields_used_by_policy": False,
            "environment_stream_sha256": environment.stream_sha256,
            "selected_action": action,
            "optimal_action_posthoc": optimal_action,
            "policy_scores_all_actions": scores.tolist(),
            "policy_centers_all_actions": center_values.tolist(),
            "policy_bonuses_all_actions": bonuses.tolist(),
            "policy_effective_omega": omega,
            "policy_cg_width_squared_all_actions": cg.widths_squared.tolist(),
            "policy_cg_iterations_all_actions": list(cg.iterations),
            "policy_cg_relative_residuals_all_actions": list(cg.relative_residuals),
            "policy_cg_residual_certificates_all_actions": list(cg.residual_certificates),
            "policy_condition_number_upper_bound": condition_upper_bound,
            "policy_corrected_center_solve_error_bar": corrected_center_error_bar,
            "policy_corrected_center_normal_residual_norm": float(
                np.linalg.norm(theta_hat_normal_residual)
            ),
            "observed_reward": reward,
            "realized_noise_posthoc": realized_noise,
            "instantaneous_pseudo_regret": instantaneous_regret,
            "cumulative_pseudo_regret": cumulative_regret,
            "normalized_cumulative_regret_by_reward_range": cumulative_regret
            / (2.0 * round_number),
            "optimism_violation_count": optimism_violation_count,
            "cumulative_optimism_violation_count": optimism_failures,
            "confidence_violation_count": confidence_violation_count,
            "cumulative_confidence_violation_count": confidence_failures,
            "posthoc_true_means_all_actions": true_means.tolist(),
            "posthoc_exact_current_width_squared_all_actions": exact_widths_squared.tolist(),
            "posthoc_frozen_width_squared_all_actions": frozen_widths_squared.tolist(),
            "posthoc_exact_cg_energy_errors_all_actions": explicit_energy_errors,
            "posthoc_exact_chi_t": exact_chi,
            "posthoc_exact_psi_t": exact_psi,
            "posthoc_exact_M_norm": exact_mismatch_norm,
            "posthoc_exact_F_prior": true_F - true_collection_remainder**2,
            "posthoc_exact_gamma_prior": gamma_exact,
            "posthoc_exact_beta_t": beta_exact,
            "posthoc_true_linearization_all_actions": true_linearization.tolist(),
            "posthoc_certificate_checks": checks,
            "round_certificate_failure_count": round_certificate_failures,
            "cumulative_certificate_failure_count": certificate_failures,
            "Lambda_algorithmic_exact": exact_lambda,
            "Lambda_algorithmic_observable_upper": observable_lambda,
            "operational_S_sum": cumulative_S,
            "theorem_rhs_exact_width_audit": theorem_rhs_exact,
            "theorem_rhs_observable": theorem_rhs_observable,
            "maximum_possible_regret": maximum_possible_regret,
            "observable_rhs_divided_by_regret": (
                theorem_rhs_observable / cumulative_regret
                if cumulative_regret > 0.0
                else None
            ),
            "theorem_bound_numerically_nonvacuous": theorem_rhs_observable
            < maximum_possible_regret,
            "theta_norm_before_update": float(np.linalg.norm(theta_before_update)),
            "theta_norm_after_update": float(np.linalg.norm(theta)),
            "optimizer_step_norm": step_norm,
            "certificate_seconds": certificate_seconds,
            "cg_seconds": cg_seconds,
            "cumulative_certificate_seconds": cumulative_certificate_seconds,
            "cumulative_cg_seconds": cumulative_cg_seconds,
            "round_runtime_seconds": time.perf_counter() - round_started,
            **snapshot.as_metrics(),
            **commitment.as_metrics(),
            **update.as_metrics(),
        }
        records.append(record)

    final = records[-1]
    summary = {
        "experiment": "certified_tanh",
        "seed": int(seed),
        "center": center,
        "profile": str(config.get("profile", "unknown")),
        "rounds": rounds,
        "executed_policy": True,
        "certification_category": "posthoc_theorem_event_verified",
        "mathematical_schedule_status": "all_theorem_schedules_predictable_pre_action",
        "all_observed_theorem_event_checks_hold": certificate_failures == 0,
        "numerical_enclosure_status": "float64_point_residuals_not_interval_verified",
        "certificate_failure_count": certificate_failures,
        "optimism_violation_count": optimism_failures,
        "confidence_violation_count": confidence_failures,
        "cumulative_pseudo_regret": final["cumulative_pseudo_regret"],
        "theorem_rhs_observable": final["theorem_rhs_observable"],
        "rhs_divided_by_regret": final["observable_rhs_divided_by_regret"],
        "theorem_bound_numerically_nonvacuous": final[
            "theorem_bound_numerically_nonvacuous"
        ],
        "runtime_seconds": time.perf_counter() - run_started,
        "certificate_seconds": final["cumulative_certificate_seconds"],
        "cg_seconds": final["cumulative_cg_seconds"],
        "Lambda_algorithmic_exact": final["Lambda_algorithmic_exact"],
        "Lambda_algorithmic_observable_upper": final[
            "Lambda_algorithmic_observable_upper"
        ],
        "final_chi_exact": final["posthoc_exact_chi_t"],
        "final_chi_bar": final["policy_certificate_chi_bar_t"],
        "final_psi_exact": final["posthoc_exact_psi_t"],
        "final_psi_bar": final["policy_certificate_psi_bar_t"],
        "final_F_exact_prior": final["posthoc_exact_F_prior"],
        "final_F_bar_prior": final["policy_certificate_f_bar_prior"],
        "final_gamma_exact": final["posthoc_exact_gamma_prior"],
        "final_gamma_hat": final["policy_certificate_gamma_hat_prior"],
        "environment_stream_sha256": environment.stream_sha256,
        "policy_uses_teacher": False,
        "policy_uses_posthoc_diagnostics": False,
        "smoothness_constants": {"G": G, "L_mu": L_mu, "L_g": L_g},
        "operator_certificate_failure_probability": 0.0,
    }
    return CertifiedTanhRun(
        seed=int(seed), center=center, records=tuple(records), summary=summary
    )


def save_run(
    run: CertifiedTanhRun,
    config: Mapping[str, Any],
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    destination = Path(output_dir)
    summary_path = destination / "summary.jsonl"
    if overwrite:
        for path in (destination / "manifest.jsonl", destination / "raw.jsonl", summary_path):
            if path.exists():
                path.unlink()
    elif summary_path.exists():
        raise FileExistsError(f"refusing to overwrite {summary_path}")
    with ExperimentLogger(
        destination,
        config,
        run.seed,
        repository=Path(__file__).resolve().parents[1],
        overwrite=False,
    ) as logger:
        for round_index, record in enumerate(run.records):
            logger.log_round(round_index, record)
    append_jsonl(summary_path, run.summary)
    return destination


def run_experiment(
    config: Mapping[str, Any],
    *,
    seed_set: str,
    output_root: str | Path,
    centers: Sequence[str] | None = None,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    selected_centers = tuple(centers or _section(config, "policy").get("centers", CENTERS))
    for center in selected_centers:
        if center not in CENTERS:
            raise ValueError(f"unknown center {center!r}")
    destinations: list[Path] = []
    for seed in get_seed_set(config, seed_set):
        for center in selected_centers:
            run_config = json.loads(json.dumps(config))
            run_config["execution"] = {
                "seed_set": seed_set,
                "center": center,
                "policy_uses_teacher": False,
            }
            run = run_certified_policy(run_config, seed, center=center)
            destination = (
                Path(output_root)
                / str(config.get("profile", "unknown"))
                / seed_set
                / center
                / f"seed-{seed}"
            )
            save_run(run, run_config, destination, overwrite=overwrite)
            destinations.append(destination)
    return tuple(destinations)


def controlled_grid_cells(config: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    grid = _section(config, "controlled_grid")
    raw = grid.get("cells")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        raise ValueError("controlled_grid.cells must be a nonempty sequence")
    cells: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    required = {
        "id",
        "trust_region_radius",
        "nonlinearity_scale",
        "horizon",
        "cg_relative_energy_error",
        "ridge",
        "update_frequency",
    }
    for value in raw:
        if not isinstance(value, Mapping) or set(value) != required:
            raise ValueError("each controlled grid cell must define the exact protocol keys")
        cell = dict(value)
        identifier = str(cell["id"])
        if not identifier or identifier in identifiers:
            raise ValueError("controlled grid cell ids must be unique and nonempty")
        identifiers.add(identifier)
        cells.append(cell)
    return tuple(cells)


def _config_for_grid_cell(
    config: Mapping[str, Any], cell: Mapping[str, Any]
) -> dict[str, Any]:
    resolved = json.loads(json.dumps(config))
    resolved["rounds"] = _positive_int(cell["horizon"], name="cell.horizon")
    resolved["horizons"] = [resolved["rounds"]]
    resolved["environment"]["nonlinearity_scale"] = _positive(
        cell["nonlinearity_scale"], name="cell.nonlinearity_scale"
    )
    resolved["policy"]["trust_region_radius"] = _positive(
        cell["trust_region_radius"], name="cell.trust_region_radius"
    )
    resolved["policy"]["ridge"] = _positive(cell["ridge"], name="cell.ridge")
    resolved["cg"]["relative_energy_error"] = _positive(
        cell["cg_relative_energy_error"], name="cell.cg_relative_energy_error"
    )
    resolved["optimizer"]["update_frequency"] = _positive_int(
        cell["update_frequency"], name="cell.update_frequency"
    )
    return resolved


def run_controlled_grid(
    config: Mapping[str, Any],
    *,
    seed_set: str,
    output_root: str | Path,
    centers: Sequence[str] | None = None,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    if seed_set != "tuning":
        raise ValueError("the controlled grid is restricted to tuning seeds")
    selected_centers = tuple(centers or _section(config, "policy").get("centers", CENTERS))
    destinations: list[Path] = []
    for cell in controlled_grid_cells(config):
        identifier = str(cell["id"])
        cell_config = _config_for_grid_cell(config, cell)
        for seed in get_seed_set(config, seed_set):
            for center in selected_centers:
                run_config = json.loads(json.dumps(cell_config))
                hyperparameters = {
                    key: value for key, value in cell.items() if key != "id"
                }
                method = f"{center}_{identifier}"
                run_config["execution"] = {
                    "seed_set": seed_set,
                    "center": center,
                    "method": method,
                    "grid_cell": identifier,
                    "hyperparameters": hyperparameters,
                    "selection_eligible": False,
                }
                run = run_certified_policy(run_config, seed, center=center)
                run.summary["method"] = method
                run.summary["grid_cell"] = identifier
                run.summary["hyperparameters"] = hyperparameters
                run.summary["evaluation_claim"] = False
                destination = (
                    Path(output_root)
                    / "controlled_grid"
                    / str(config.get("profile", "unknown"))
                    / seed_set
                    / identifier
                    / center
                    / f"seed-{seed}"
                )
                save_run(run, run_config, destination, overwrite=overwrite)
                destinations.append(destination)
    return tuple(destinations)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--seed-set", choices=("tuning", "evaluation"), default="evaluation")
    parser.add_argument("--center", action="append", choices=CENTERS)
    parser.add_argument("--output-root")
    parser.add_argument("--controlled-grid", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    config = load_config(args.config, profile=args.profile)
    output_root = args.output_root or str(config.get("output_root", "results/raw/certified_tanh"))
    runner = run_controlled_grid if args.controlled_grid else run_experiment
    destinations = runner(
        config,
        seed_set=args.seed_set,
        output_root=output_root,
        centers=args.center,
        overwrite=args.overwrite,
    )
    print(json.dumps({"run_count": len(destinations), "outputs": [str(path) for path in destinations]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CENTERS",
    "CertifiedCGWidths",
    "CertifiedTanhRun",
    "TANH_SECOND_DERIVATIVE_MAX",
    "TanhBanditEnvironment",
    "analytic_tanh_constants",
    "certified_cg_widths",
    "certified_policy_scores",
    "controlled_grid_cells",
    "optimize_projected",
    "run_certified_policy",
    "run_controlled_grid",
    "run_experiment",
    "save_run",
    "tanh_gradients",
    "tanh_mean",
]
