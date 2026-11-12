"""Smooth nonlinear operator ablations with exact small-scale diagnostics.

Every online run executes its own adaptive policy.  The separate common-
trajectory diagnostic evaluates all operators on checkpoints logged by the
full relinearized policy and deliberately reports no causal regret quantity.
All matrices are materialized in float64 so the global generalized-eigenvalue
factor is exact up to the dense eigensolver's numerical precision.
"""

from __future__ import annotations

import copy
import hashlib
import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import psutil
from numpy.typing import ArrayLike, NDArray

from .logging_utils import ExperimentLogger, append_jsonl, canonical_json, derive_seed
from .nonlinear_environment import (
    ACTION_COUNT,
    CONTEXT_DIMENSION,
    HIDDEN_WIDTH,
    PARAMETER_DIMENSION,
    NonlinearBanditEnvironment,
)
from .run_nonlinear_audit import (
    CENTER_VARIANTS,
    PredeterminedPolicySchedule,
    active_parameter_indices,
    corrected_centers,
    deterministic_online_update,
    frozen_linearized_ridge,
    get_drift_regime,
)
from .run_operator_ablation import (
    OperatorSpec,
    _select_specs,
    action_set_width_ratios,
    exact_global_kappa_plus,
)


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


def _readonly(value: ArrayLike, *, dtype: np.dtype[Any] = np.dtype(np.float64)) -> NDArray[Any]:
    result = np.asarray(value, dtype=dtype).copy()
    result.setflags(write=False)
    return result


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _positive_float(value: Any, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _logdet(matrix: FloatArray) -> float:
    values = np.linalg.eigvalsh(0.5 * (matrix + matrix.T))
    if np.any(values <= 0.0) or not np.all(np.isfinite(values)):
        raise ArithmeticError("curvature must have a finite positive determinant")
    return float(np.sum(np.log(values)))


def _gram(
    features: FloatArray, *, dimension: int, damping: float, noise_variance: float
) -> FloatArray:
    result = damping * np.eye(dimension, dtype=np.float64)
    if features.shape[0]:
        result += features.T @ features / noise_variance
    return np.asarray(0.5 * (result + result.T), dtype=np.float64)


def _lanczos_surrogate(
    matrix: FloatArray, *, damping: float, rank: int, seed: int
) -> tuple[FloatArray, dict[str, Any]]:
    """Return the deterministic rank-k-plus-damping Ritz surrogate."""

    dimension = matrix.shape[0]
    generator = np.random.default_rng(seed)
    q = generator.normal(size=dimension).astype(np.float64)
    q /= np.linalg.norm(q)
    basis: list[FloatArray] = []
    previous = np.zeros(dimension, dtype=np.float64)
    previous_beta = 0.0
    tolerance = 100.0 * np.finfo(np.float64).eps * max(
        1.0, float(np.linalg.norm(matrix, 2))
    )
    for _ in range(min(rank, dimension)):
        basis.append(q.copy())
        z = matrix @ q - previous_beta * previous
        alpha = float(q @ z)
        z -= alpha * q
        for _pass in range(2):
            for vector in basis:
                z -= float(vector @ z) * vector
        beta = float(np.linalg.norm(z))
        if beta <= tolerance:
            break
        previous, q, previous_beta = q, z / beta, beta

    krylov, _ = np.linalg.qr(np.column_stack(basis), mode="reduced")
    compression = krylov.T @ matrix @ krylov
    compression = 0.5 * (compression + compression.T)
    values, vectors = np.linalg.eigh(compression)
    order = np.argsort(values)[::-1]
    values = np.asarray(values[order], dtype=np.float64)
    ritz_vectors = np.asarray(krylov @ vectors[:, order], dtype=np.float64)
    increments = np.maximum(values - damping, 0.0)
    surrogate = damping * np.eye(dimension, dtype=np.float64)
    surrogate += (ritz_vectors * increments) @ ritz_vectors.T
    surrogate = np.asarray(0.5 * (surrogate + surrogate.T), dtype=np.float64)
    residuals = np.linalg.norm(matrix @ ritz_vectors - ritz_vectors * values, axis=0)
    return surrogate, {
        "lanczos_steps": int(krylov.shape[1]),
        "ritz_values": values.tolist(),
        "ritz_residual_max": float(np.max(residuals, initial=0.0)),
    }


@dataclass(frozen=True)
class NonlinearOperatorConfig:
    rounds: int
    damping: float
    noise_std: float
    confidence_delta: float
    regime: str
    center: str
    schedule: PredeterminedPolicySchedule
    specs: tuple[OperatorSpec, ...]
    common_trajectory_enabled: bool

    @classmethod
    def from_mapping(cls, source: Mapping[str, Any]) -> "NonlinearOperatorConfig":
        options = source.get("nonlinear_audit", {})
        if not isinstance(options, Mapping):
            raise TypeError("nonlinear_audit must be a mapping")
        rounds = _positive_int(options.get("rounds", source.get("rounds", 20)), name="rounds")
        damping = _positive_float(
            options.get("damping", source.get("ridge", source.get("damping", 1.0))),
            name="damping",
        )
        environment = source.get("environment", {})
        if not isinstance(environment, Mapping):
            environment = {}
        noise_std = _positive_float(
            options.get("noise_std", environment.get("noise_std", source.get("noise_std", 0.1))),
            name="noise_std",
        )
        confidence = source.get("confidence", {})
        if not isinstance(confidence, Mapping):
            confidence = {}
        probability = float(options.get("confidence_delta", confidence.get("delta", 0.05)))
        if not np.isfinite(probability) or not 0.0 < probability < 1.0:
            raise ValueError("confidence_delta must lie in (0, 1)")
        regime = get_drift_regime(str(options.get("regime", "medium"))).name
        center = str(options.get("center", "corrected"))
        center = "corrected" if center == "corrected_exact_frozen_feature" else center
        if center not in CENTER_VARIANTS:
            raise ValueError(f"center must be one of {CENTER_VARIANTS}")
        schedule_options = options.get("bonus_schedule", {})
        if not isinstance(schedule_options, Mapping):
            raise TypeError("nonlinear_audit.bonus_schedule must be a mapping")
        schedule = PredeterminedPolicySchedule(
            beta_base=float(schedule_options.get("beta_base", 2.25)),
            beta_log_rate=float(schedule_options.get("beta_log_rate", 0.10)),
            cg_energy_tolerance=float(
                schedule_options.get("cg_energy_tolerance", 0.05)
            ),
            condition_number_bound=float(
                schedule_options.get("condition_number_bound", 1.0e8)
            ),
        )
        common = source.get("common_trajectory", True)
        common_enabled = bool(
            common.get("enabled", True) if isinstance(common, Mapping) else common
        )
        # Import lazily to avoid duplicating the config parser's canonicalization.
        from .run_operator_ablation import configured_operator_specs

        return cls(
            rounds=rounds,
            damping=damping,
            noise_std=noise_std,
            confidence_delta=probability,
            regime=regime,
            center=center,
            schedule=schedule,
            specs=configured_operator_specs(source),
            common_trajectory_enabled=common_enabled,
        )


class _NonlinearOperatorBuilder:
    """Build one deterministic operator per checkpoint and retain stale state."""

    def __init__(
        self,
        spec: OperatorSpec,
        *,
        dimension: int,
        damping: float,
        noise_variance: float,
        seed: int,
    ) -> None:
        self.spec = spec
        self.dimension = dimension
        self.damping = damping
        self.noise_variance = noise_variance
        self.seed = int(seed)
        self._stale_matrix: FloatArray | None = None

    def build(
        self,
        round_number: int,
        current_features: FloatArray,
        frozen_features: FloatArray,
    ) -> tuple[FloatArray, dict[str, Any]]:
        count = current_features.shape[0]
        if current_features.shape != frozen_features.shape:
            raise ValueError("current and frozen histories must have the same shape")
        if current_features.shape[1] != self.dimension:
            raise ValueError("history has the wrong parameter dimension")
        full = _gram(
            current_features,
            dimension=self.dimension,
            damping=self.damping,
            noise_variance=self.noise_variance,
        )
        spec = self.spec
        metadata: dict[str, Any] = {"history_count": count}
        if spec.kind == "full":
            result = full
        elif spec.kind == "frozen":
            result = _gram(
                frozen_features,
                dimension=self.dimension,
                damping=self.damping,
                noise_variance=self.noise_variance,
            )
        elif spec.kind == "diagonal":
            result = np.diag(np.diag(full)).astype(np.float64)
        elif spec.kind == "unrescaled_window":
            size = int(spec.parameter)
            start = max(0, count - size)
            result = _gram(
                current_features[start:],
                dimension=self.dimension,
                damping=self.damping,
                noise_variance=self.noise_variance,
            )
            metadata.update({"selected_indices": list(range(start, count)), "rescale": 1.0})
        elif spec.kind == "rescaled_subsample":
            size = min(count, int(spec.parameter))
            if size == 0:
                indices = np.empty(0, dtype=np.int64)
                scale = 1.0
            elif size == count:
                indices = np.arange(count, dtype=np.int64)
                scale = 1.0
            else:
                rng = np.random.default_rng(
                    derive_seed(self.seed, "nonlinear_operator", spec.name, round_number)
                )
                indices = np.sort(rng.choice(count, size=size, replace=False))
                scale = float(count / size)
            result = self.damping * np.eye(self.dimension, dtype=np.float64)
            if size:
                selected = current_features[indices]
                result += scale * selected.T @ selected / self.noise_variance
            result = np.asarray(0.5 * (result + result.T), dtype=np.float64)
            metadata.update({"selected_indices": indices.tolist(), "rescale": scale})
        elif spec.kind == "lanczos":
            result, lanczos = _lanczos_surrogate(
                full,
                damping=self.damping,
                rank=min(int(spec.parameter), self.dimension),
                seed=derive_seed(
                    self.seed, "nonlinear_operator", spec.name, round_number
                ),
            )
            metadata.update(lanczos)
        elif spec.kind == "stale_refresh":
            period = int(spec.parameter)
            refreshed = self._stale_matrix is None or (round_number - 1) % period == 0
            if refreshed:
                self._stale_matrix = full.copy()
            if self._stale_matrix is None:
                raise AssertionError("stale operator was not initialized")
            result = self._stale_matrix.copy()
            metadata.update({"refreshed": refreshed, "refresh_period": period})
        else:
            raise AssertionError(f"unhandled operator kind {spec.kind}")
        np.linalg.cholesky(result)
        metadata["fixed_within_all_action_solves"] = True
        return np.asarray(result, dtype=np.float64), metadata


@dataclass(frozen=True)
class NonlinearLoggedTrajectory:
    seed: int
    regime: str
    center: str
    damping: float
    noise_std: float
    contexts: FloatArray
    actions: IntArray
    rewards: FloatArray
    parameters: FloatArray
    frozen_jacobians: FloatArray
    collection_parameters: FloatArray
    collection_means: FloatArray
    action_jacobians: FloatArray
    current_histories: tuple[FloatArray, ...]
    centers: FloatArray
    teacher_means: FloatArray
    bonus_coefficients: FloatArray
    digest: str
    source_operator: str

    @property
    def rounds(self) -> int:
        return int(self.actions.size)


@dataclass(frozen=True)
class NonlinearOnlineOperatorRun:
    spec: OperatorSpec
    seed: int
    config: NonlinearOperatorConfig
    records: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    trajectory: NonlinearLoggedTrajectory

    @property
    def actions(self) -> tuple[int, ...]:
        return tuple(int(value) for value in self.trajectory.actions)


@dataclass(frozen=True)
class NonlinearOfflineDiagnostic:
    spec: OperatorSpec
    records: tuple[dict[str, Any], ...]
    summary: dict[str, Any]


@dataclass(frozen=True)
class NonlinearCommonTrajectoryResult:
    trajectory: NonlinearLoggedTrajectory
    diagnostics: tuple[NonlinearOfflineDiagnostic, ...]
    summary: dict[str, Any]


@dataclass(frozen=True)
class NonlinearOperatorAblationResult:
    seed: int
    config: NonlinearOperatorConfig
    online_runs: tuple[NonlinearOnlineOperatorRun, ...]
    common_trajectory: NonlinearCommonTrajectoryResult | None
    summary: dict[str, Any]


def _history_matrix(values: Sequence[FloatArray], dimension: int) -> FloatArray:
    if not values:
        return np.empty((0, dimension), dtype=np.float64)
    return np.asarray(np.stack(values, axis=0), dtype=np.float64)


def _trajectory_digest(arrays: Sequence[ArrayLike], metadata: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(metadata).encode("ascii"))
    for value in arrays:
        array = np.ascontiguousarray(value)
        digest.update(str(array.shape).encode("ascii"))
        digest.update(array.dtype.str.encode("ascii"))
        digest.update(array.tobytes())
    return digest.hexdigest()


def _dynamic_update(
    *,
    information: float,
    transition_sum: float,
    variation: float,
    initial_logdet: float,
    current: FloatArray,
    following: FloatArray,
    played_feature: FloatArray,
    noise_variance: float,
) -> tuple[float, float, float, float, float, float, float]:
    width_squared = float(played_feature @ np.linalg.solve(current, played_feature))
    increment = float(np.log1p(width_squared / noise_variance))
    updated = current + np.outer(played_feature, played_feature) / noise_variance
    transition = _logdet(following) - _logdet(updated)
    next_information = information + increment
    next_transition_sum = transition_sum + transition
    next_variation = variation + max(-transition, 0.0)
    endpoint = _logdet(following) - initial_logdet
    gamma = endpoint + next_variation
    residual = next_information - (endpoint - next_transition_sum)
    return (
        next_information,
        next_transition_sum,
        next_variation,
        endpoint,
        gamma,
        residual,
        width_squared,
    )


def _make_trajectory(
    *,
    seed: int,
    config: NonlinearOperatorConfig,
    spec: OperatorSpec,
    contexts: list[FloatArray],
    actions: list[int],
    rewards: list[float],
    parameters: list[FloatArray],
    frozen_jacobians: list[FloatArray],
    collection_parameters: list[FloatArray],
    collection_means: list[float],
    action_jacobians: list[FloatArray],
    current_histories: list[FloatArray],
    centers: list[FloatArray],
    teacher_means: list[FloatArray],
    bonuses: list[float],
) -> NonlinearLoggedTrajectory:
    arrays = (
        np.stack(contexts),
        np.asarray(actions, dtype=np.int64),
        np.asarray(rewards, dtype=np.float64),
        np.stack(parameters),
        np.stack(frozen_jacobians),
        np.stack(collection_parameters),
        np.asarray(collection_means, dtype=np.float64),
        np.stack(action_jacobians),
        np.stack(centers),
        np.stack(teacher_means),
        np.asarray(bonuses, dtype=np.float64),
    )
    digest = _trajectory_digest(
        arrays,
        {
            "seed": seed,
            "regime": config.regime,
            "center": config.center,
            "damping": config.damping,
            "noise_std": config.noise_std,
            "source_operator": spec.name,
        },
    )
    return NonlinearLoggedTrajectory(
        seed=seed,
        regime=config.regime,
        center=config.center,
        damping=config.damping,
        noise_std=config.noise_std,
        contexts=_readonly(arrays[0]),
        actions=_readonly(arrays[1], dtype=np.dtype(np.int64)),
        rewards=_readonly(arrays[2]),
        parameters=_readonly(arrays[3]),
        frozen_jacobians=_readonly(arrays[4]),
        collection_parameters=_readonly(arrays[5]),
        collection_means=_readonly(arrays[6]),
        action_jacobians=_readonly(arrays[7]),
        current_histories=tuple(_readonly(value) for value in current_histories),
        centers=_readonly(arrays[8]),
        teacher_means=_readonly(arrays[9]),
        bonus_coefficients=_readonly(arrays[10]),
        digest=digest,
        source_operator=spec.name,
    )


def run_nonlinear_operator(
    config: Mapping[str, Any] | NonlinearOperatorConfig,
    spec: OperatorSpec,
    seed: int,
    *,
    measure_resources: bool = False,
) -> NonlinearOnlineOperatorRun:
    """Execute one nonlinear policy using one fixed-reference bonus schedule."""

    resolved = (
        config if isinstance(config, NonlinearOperatorConfig) else NonlinearOperatorConfig.from_mapping(config)
    )
    regime = get_drift_regime(resolved.regime)
    environment = NonlinearBanditEnvironment(seed, noise_std=resolved.noise_std)
    model = environment.model
    active = active_parameter_indices(model, regime)
    dimension = int(active.size)
    variance = resolved.noise_std**2
    builder = _NonlinearOperatorBuilder(
        spec,
        dimension=dimension,
        damping=resolved.damping,
        noise_variance=variance,
        seed=seed,
    )

    theta = np.zeros(model.parameter_dimension, dtype=np.float64)
    history_contexts: list[FloatArray] = []
    history_actions: list[int] = []
    history_rewards: list[float] = []
    frozen_jacobians: list[FloatArray] = []
    collection_parameters: list[FloatArray] = []
    collection_means: list[float] = []
    trajectory_parameters = [theta.copy()]
    trajectory_action_jacobians: list[FloatArray] = []
    trajectory_current_histories: list[FloatArray] = []
    trajectory_centers: list[FloatArray] = []
    trajectory_teacher_means: list[FloatArray] = []
    trajectory_bonuses: list[float] = []
    records: list[dict[str, Any]] = []
    played_jacobians: list[FloatArray] = []
    cumulative_regret = 0.0
    information = 0.0
    transition_sum = 0.0
    variation = 0.0
    epsilon_sum = 0.0
    epsilon_square_sum = 0.0
    run_started = time.perf_counter()
    process = psutil.Process() if measure_resources else None
    peak_memory = process.memory_info().rss if process is not None else 0
    initial_logdet = dimension * math.log(resolved.damping)

    current_history = np.empty((0, dimension), dtype=np.float64)
    frozen_history = np.empty((0, dimension), dtype=np.float64)
    current_operator, operator_metadata = builder.build(1, current_history, frozen_history)

    for index in range(resolved.rounds):
        round_started = time.perf_counter()
        round_number = index + 1
        context = environment.draw_context()
        action_jacobians = model.jacobians(theta, context)[:, active]
        original_centers = model.means(theta, context)
        if history_actions:
            ridge_fit = frozen_linearized_ridge(
                frozen_history,
                np.stack(collection_parameters),
                np.asarray(collection_means),
                np.asarray(history_rewards),
                damping=resolved.damping,
                noise_variance=variance,
            )
            corrected = corrected_centers(
                original_centers,
                action_jacobians,
                theta[active],
                ridge_fit.parameters,
            )
            theta_hat = np.asarray(ridge_fit.parameters, dtype=np.float64)
        else:
            corrected = original_centers.copy()
            theta_hat = np.zeros(dimension, dtype=np.float64)
        centers = original_centers if resolved.center == "original" else corrected
        teacher_means = environment.mean_rewards(context)

        full_operator = _gram(
            current_history,
            dimension=dimension,
            damping=resolved.damping,
            noise_variance=variance,
        )
        frozen_operator = _gram(
            frozen_history,
            dimension=dimension,
            damping=resolved.damping,
            noise_variance=variance,
        )
        approximate_widths = np.asarray(
            np.einsum(
                "ij,ji->i",
                action_jacobians,
                np.linalg.solve(current_operator, action_jacobians.T),
            ),
            dtype=np.float64,
        )
        full_widths = np.asarray(
            np.einsum(
                "ij,ji->i",
                action_jacobians,
                np.linalg.solve(full_operator, action_jacobians.T),
            ),
            dtype=np.float64,
        )
        if np.any(approximate_widths <= 0.0) or np.any(full_widths <= 0.0):
            raise ArithmeticError("SPD curvature produced a nonpositive action width")
        omega = resolved.schedule.beta(round_number)
        if resolved.center == "original":
            omega += resolved.schedule.centering(resolved.regime, "original", round_number)
        scores = centers + omega * np.sqrt(approximate_widths)
        full_scores = centers + omega * np.sqrt(full_widths)
        action = int(np.argmax(scores))
        same_checkpoint_full_action = int(np.argmax(full_scores))
        optimal_action = int(np.argmax(teacher_means))
        regret = float(teacher_means[optimal_action] - teacher_means[action])
        cumulative_regret += regret
        reward, realized_noise = environment.reward(context, action)

        global_factor = exact_global_kappa_plus(current_operator, full_operator)
        cbar_ratios = action_set_width_ratios(
            current_operator, frozen_operator, action_jacobians
        )
        current_ratios = action_set_width_ratios(
            current_operator, full_operator, action_jacobians
        )
        relative_width_distortion = np.abs(
            np.sqrt(approximate_widths / full_widths) - 1.0
        )
        approximation_error = float(
            np.linalg.norm(current_operator - full_operator, ord="fro")
            / max(np.linalg.norm(full_operator, ord="fro"), np.finfo(np.float64).tiny)
        )
        if current_history.shape[0]:
            cbar_values, cbar_vectors = np.linalg.eigh(frozen_operator)
            cbar_inverse_root = (
                cbar_vectors * (1.0 / np.sqrt(cbar_values))
            ) @ cbar_vectors.T
            whitened_drift = (
                cbar_inverse_root
                @ (current_history - frozen_history).T
                / resolved.noise_std
            )
            chi = float(np.linalg.norm(whitened_drift, ord=2))
        else:
            chi = 0.0
        cbar_widths = np.sqrt(cbar_ratios.cbar_widths_squared)
        centering_ratio = float(
            np.max(
                np.abs(action_jacobians @ (theta[active] - theta_hat))
                / cbar_widths
            )
        )
        theta_star = environment.teacher_displacement[active]
        linearization_remainder = (
            teacher_means
            - original_centers
            - action_jacobians @ (theta_star - theta[active])
        )
        epsilon_lin = float(np.max(np.abs(linearization_remainder)))
        epsilon_sum += epsilon_lin
        epsilon_square_sum += epsilon_lin**2
        algorithmic_eigenvalues = np.linalg.eigvalsh(current_operator)
        condition_number = float(
            algorithmic_eigenvalues[-1] / algorithmic_eigenvalues[0]
        )
        condition_bound = float(algorithmic_eigenvalues[-1] / resolved.damping)

        frozen_selected = action_jacobians[action].copy()
        selected_mean = float(original_centers[action])
        history_contexts.append(context.copy())
        history_actions.append(action)
        history_rewards.append(reward)
        frozen_jacobians.append(frozen_selected)
        collection_parameters.append(theta[active].copy())
        collection_means.append(selected_mean)
        played_jacobians.append(frozen_selected)
        trajectory_action_jacobians.append(action_jacobians.copy())
        trajectory_current_histories.append(current_history.copy())
        trajectory_centers.append(np.asarray(centers, dtype=np.float64).copy())
        trajectory_teacher_means.append(teacher_means.copy())
        trajectory_bonuses.append(omega)

        update = deterministic_online_update(
            model,
            theta,
            np.stack(history_contexts),
            np.asarray(history_actions, dtype=np.int64),
            np.asarray(history_rewards, dtype=np.float64),
            regime=regime,
            damping=resolved.damping,
            noise_variance=variance,
        )
        next_theta = np.asarray(update.parameters, dtype=np.float64).copy()
        trajectory_parameters.append(next_theta.copy())
        frozen_history = _history_matrix(frozen_jacobians, dimension)
        current_history = np.stack(
            [
                model.jacobian(next_theta, old_context, old_action)[active]
                for old_context, old_action in zip(
                    history_contexts, history_actions, strict=True
                )
            ]
        )
        following_operator, following_metadata = builder.build(
            round_number + 1, current_history, frozen_history
        )
        (
            information,
            transition_sum,
            variation,
            endpoint,
            gamma,
            identity_residual,
            played_width_squared,
        ) = _dynamic_update(
            information=information,
            transition_sum=transition_sum,
            variation=variation,
            initial_logdet=initial_logdet,
            current=current_operator,
            following=following_operator,
            played_feature=frozen_selected,
            noise_variance=variance,
        )

        tolerance = 1.0e-12 * max(1.0, float(np.max(np.abs(teacher_means))))
        violations = scores + tolerance < teacher_means
        global_tolerance = 2.0e-10 * max(1.0, abs(global_factor))
        record: dict[str, Any] = {
            "seed": int(seed),
            "round": round_number,
            "environment": "smooth_nonlinear_tanh",
            "regime": resolved.regime,
            "center": resolved.center,
            "operator": spec.name,
            "method": spec.name,
            "operator_kind": spec.kind,
            "operator_parameter": spec.parameter,
            "execution_mode": "online_adaptive",
            "executed_policy": True,
            "offline_diagnostic": False,
            "comparison": "fixed_reference_bonus_and_damping",
            "certified_run_claim": False,
            "posthoc_diagnostics_are_policy_inputs": False,
            "context": context.tolist(),
            "selected_action": action,
            "action": action,
            "optimal_action": optimal_action,
            "instantaneous_pseudo_regret": regret,
            "cumulative_pseudo_regret": cumulative_regret,
            "observed_reward": reward,
            "realized_noise": realized_noise,
            "predicted_centers": centers.tolist(),
            "mean_predictions": centers.tolist(),
            "teacher_means": teacher_means.tolist(),
            "policy_scores": scores.tolist(),
            "fixed_bonus_coefficient": omega,
            "damping": resolved.damping,
            "exact_algorithmic_widths_squared": approximate_widths.tolist(),
            "exact_full_widths_squared": full_widths.tolist(),
            "exact_global_kappa_plus": global_factor,
            "kappa_plus": global_factor,
            "action_set_transfer_Cbar_over_Chat": cbar_ratios.maximum_squared_ratio,
            "action_set_transfer": cbar_ratios.maximum_squared_ratio,
            "action_set_transfer_C_over_Chat": current_ratios.maximum_squared_ratio,
            "action_set_current_ratio_bounded_by_global_kappa": bool(
                current_ratios.maximum_squared_ratio <= global_factor + global_tolerance
            ),
            "max_relative_width_distortion_from_full": float(
                np.max(relative_width_distortion)
            ),
            "mean_relative_width_distortion_from_full": float(
                np.mean(relative_width_distortion)
            ),
            "relative_frobenius_operator_error": approximation_error,
            "same_checkpoint_full_action": same_checkpoint_full_action,
            "action_disagrees_with_full": bool(action != same_checkpoint_full_action),
            "optimism_violation_count": int(np.count_nonzero(violations)),
            "optimism_violation_rate": float(
                np.count_nonzero(violations) / environment.action_count
            ),
            "optimism_violation": bool(np.any(violations)),
            "Lambda_alg_cumulative": information,
            "Lambda_t_C": information,
            "V_alg_cumulative": variation,
            "V_t_C": variation,
            "Gamma_dynamic_cumulative": gamma,
            "Gamma_t_dynamic": gamma,
            "endpoint_logdet": endpoint,
            "dynamic_transition_logdet_sum": transition_sum,
            "dynamic_identity_residual": identity_residual,
            "played_width_squared": played_width_squared,
            "condition_number_algorithmic": condition_number,
            "condition_number_full": float(np.linalg.cond(full_operator)),
            "kappa_t": condition_number,
            "kappa_bar_t": condition_bound,
            "chi_t": chi,
            "psi_t_action_set_centering_ratio": centering_ratio,
            "epsilon_lin_t": epsilon_lin,
            "E_t": epsilon_sum,
            "F_t": epsilon_square_sum,
            "alpha_t": 1.0,
            "u_t": cbar_ratios.maximum_squared_ratio,
            "omega_t": omega,
            "window_global_kappa_le_one": (
                bool(global_factor <= 1.0 + global_tolerance)
                if spec.kind == "unrescaled_window"
                else None
            ),
            "operator_metadata": operator_metadata,
            "model_step_norm": update.step_norm,
            "backbone_step_norm": update.backbone_step_norm,
            "fixed_operator_across_all_action_width_solves": True,
            "cg_iterations": 0,
            "cg_residual": 0.0,
            "cg_energy_error": 0.0,
            "float_dtype": "float64",
        }
        if process is not None:
            peak_memory = max(peak_memory, process.memory_info().rss)
            record.update(
                {
                    "round_runtime_seconds": time.perf_counter() - round_started,
                    "runtime_seconds": time.perf_counter() - run_started,
                    "peak_host_memory_bytes": peak_memory,
                }
            )
        records.append(record)
        theta = next_theta
        current_operator = following_operator
        operator_metadata = following_metadata

    trajectory_current_histories.append(current_history.copy())
    trajectory = _make_trajectory(
        seed=seed,
        config=resolved,
        spec=spec,
        contexts=history_contexts,
        actions=history_actions,
        rewards=history_rewards,
        parameters=trajectory_parameters,
        frozen_jacobians=frozen_jacobians,
        collection_parameters=collection_parameters,
        collection_means=collection_means,
        action_jacobians=trajectory_action_jacobians,
        current_histories=trajectory_current_histories,
        centers=trajectory_centers,
        teacher_means=trajectory_teacher_means,
        bonuses=trajectory_bonuses,
    )
    last = records[-1]
    summary: dict[str, Any] = {
        "event": "nonlinear_operator_online_summary",
        "seed": int(seed),
        "rounds": resolved.rounds,
        "environment": "smooth_nonlinear_tanh",
        "regime": resolved.regime,
        "center": resolved.center,
        "operator": spec.name,
        "operator_kind": spec.kind,
        "operator_parameter": spec.parameter,
        "execution_mode": "online_adaptive",
        "executed_policy": True,
        "offline_diagnostic": False,
        "comparison": "fixed_reference_bonus_and_damping",
        "certified_run_claim": False,
        "trajectory_digest": trajectory.digest,
        "cumulative_pseudo_regret": float(last["cumulative_pseudo_regret"]),
        "optimism_violation_rate": float(
            sum(int(record["optimism_violation_count"]) for record in records)
            / (resolved.rounds * environment.action_count)
        ),
        "Lambda_alg_T": float(last["Lambda_alg_cumulative"]),
        "V_alg_T": float(last["V_alg_cumulative"]),
        "Gamma_dynamic_T": float(last["Gamma_dynamic_cumulative"]),
        "endpoint_logdet_T": float(last["endpoint_logdet"]),
        "dynamic_identity_residual": float(last["dynamic_identity_residual"]),
        "kappa_plus_max": max(float(record["kappa_plus"]) for record in records),
        "action_set_transfer_Cbar_over_Chat_max": max(
            float(record["action_set_transfer_Cbar_over_Chat"]) for record in records
        ),
        "action_set_transfer_max": max(
            float(record["action_set_transfer"]) for record in records
        ),
        "action_set_transfer_C_over_Chat_max": max(
            float(record["action_set_transfer_C_over_Chat"]) for record in records
        ),
        "max_relative_width_distortion_from_full": max(
            float(record["max_relative_width_distortion_from_full"])
            for record in records
        ),
        "relative_frobenius_operator_error_max": max(
            float(record["relative_frobenius_operator_error"]) for record in records
        ),
        "action_disagreement_rate": float(
            sum(bool(record["action_disagrees_with_full"]) for record in records)
            / resolved.rounds
        ),
        "window_global_kappa_le_one_all_rounds": (
            all(bool(record["window_global_kappa_le_one"]) for record in records)
            if spec.kind == "unrescaled_window"
            else None
        ),
        "all_current_action_ratios_bounded_by_global_kappa": all(
            bool(record["action_set_current_ratio_bounded_by_global_kappa"])
            for record in records
        ),
        "runtime_seconds": time.perf_counter() - run_started,
        "peak_host_memory_bytes": peak_memory if process is not None else None,
        "float_dtype": "float64",
    }
    return NonlinearOnlineOperatorRun(
        spec=spec,
        seed=int(seed),
        config=resolved,
        records=tuple(records),
        summary=summary,
        trajectory=trajectory,
    )


def _offline_nonlinear_diagnostic(
    config: NonlinearOperatorConfig,
    spec: OperatorSpec,
    trajectory: NonlinearLoggedTrajectory,
) -> NonlinearOfflineDiagnostic:
    dimension = trajectory.frozen_jacobians.shape[1]
    variance = config.noise_std**2
    builder = _NonlinearOperatorBuilder(
        spec,
        dimension=dimension,
        damping=config.damping,
        noise_variance=variance,
        seed=trajectory.seed,
    )
    operators: list[FloatArray] = []
    metadata: list[dict[str, Any]] = []
    for index, current in enumerate(trajectory.current_histories):
        matrix, details = builder.build(
            index + 1,
            np.asarray(current, dtype=np.float64),
            np.asarray(trajectory.frozen_jacobians[:index], dtype=np.float64),
        )
        operators.append(matrix)
        metadata.append(details)

    records: list[dict[str, Any]] = []
    information = 0.0
    transition_sum = 0.0
    variation = 0.0
    initial_logdet = dimension * math.log(config.damping)
    for index in range(trajectory.rounds):
        current = operators[index]
        following = operators[index + 1]
        current_reference = _gram(
            np.asarray(trajectory.current_histories[index]),
            dimension=dimension,
            damping=config.damping,
            noise_variance=variance,
        )
        frozen_reference = _gram(
            np.asarray(trajectory.frozen_jacobians[:index]),
            dimension=dimension,
            damping=config.damping,
            noise_variance=variance,
        )
        candidates = np.asarray(trajectory.action_jacobians[index])
        approximate_widths = np.einsum(
            "ij,ji->i", candidates, np.linalg.solve(current, candidates.T)
        )
        full_widths = np.einsum(
            "ij,ji->i", candidates, np.linalg.solve(current_reference, candidates.T)
        )
        scores = trajectory.centers[index] + trajectory.bonus_coefficients[index] * np.sqrt(
            approximate_widths
        )
        full_scores = trajectory.centers[index] + trajectory.bonus_coefficients[index] * np.sqrt(
            full_widths
        )
        diagnostic_action = int(np.argmax(scores))
        full_action = int(np.argmax(full_scores))
        logged_action = int(trajectory.actions[index])
        global_factor = exact_global_kappa_plus(current, current_reference)
        cbar_ratios = action_set_width_ratios(current, frozen_reference, candidates)
        current_ratios = action_set_width_ratios(current, current_reference, candidates)
        played = candidates[logged_action]
        (
            information,
            transition_sum,
            variation,
            endpoint,
            gamma,
            identity_residual,
            played_width,
        ) = _dynamic_update(
            information=information,
            transition_sum=transition_sum,
            variation=variation,
            initial_logdet=initial_logdet,
            current=current,
            following=following,
            played_feature=played,
            noise_variance=variance,
        )
        relative_distortion = np.abs(np.sqrt(approximate_widths / full_widths) - 1.0)
        tolerance = 2.0e-10 * max(1.0, abs(global_factor))
        records.append(
            {
                "seed": trajectory.seed,
                "round": index + 1,
                "environment": "smooth_nonlinear_tanh",
                "regime": trajectory.regime,
                "center": trajectory.center,
                "operator": spec.name,
                "operator_kind": spec.kind,
                "operator_parameter": spec.parameter,
                "execution_mode": "offline_common_trajectory_diagnostic",
                "executed_policy": False,
                "offline_diagnostic": True,
                "causal_regret_claim": False,
                "regret_reported": False,
                "trajectory_digest": trajectory.digest,
                "source_operator": trajectory.source_operator,
                "same_history_parameters_actions_damping_bonus": True,
                "logged_action": logged_action,
                "diagnostic_action": diagnostic_action,
                "full_diagnostic_action": full_action,
                "diagnostic_action_matches_logged_action": bool(
                    diagnostic_action == logged_action
                ),
                "action_disagrees_with_full": bool(diagnostic_action != full_action),
                "fixed_damping": config.damping,
                "fixed_bonus_coefficient": float(trajectory.bonus_coefficients[index]),
                "kappa_plus": global_factor,
                "exact_global_kappa_plus": global_factor,
                "action_set_transfer_Cbar_over_Chat": cbar_ratios.maximum_squared_ratio,
                "action_set_transfer_C_over_Chat": current_ratios.maximum_squared_ratio,
                "action_set_current_ratio_bounded_by_global_kappa": bool(
                    current_ratios.maximum_squared_ratio <= global_factor + tolerance
                ),
                "exact_algorithmic_widths_squared": approximate_widths.tolist(),
                "exact_full_widths_squared": full_widths.tolist(),
                "max_relative_width_distortion_from_full": float(
                    np.max(relative_distortion)
                ),
                "Lambda_alg_cumulative": information,
                "V_alg_cumulative": variation,
                "Gamma_dynamic_cumulative": gamma,
                "endpoint_logdet": endpoint,
                "dynamic_identity_residual": identity_residual,
                "played_width_squared": played_width,
                "window_global_kappa_le_one": (
                    bool(global_factor <= 1.0 + tolerance)
                    if spec.kind == "unrescaled_window"
                    else None
                ),
                "operator_metadata": metadata[index],
                "float_dtype": "float64",
            }
        )
    last = records[-1]
    summary = {
        "event": "nonlinear_operator_offline_summary",
        "seed": trajectory.seed,
        "rounds": trajectory.rounds,
        "environment": "smooth_nonlinear_tanh",
        "regime": trajectory.regime,
        "center": trajectory.center,
        "operator": spec.name,
        "operator_kind": spec.kind,
        "operator_parameter": spec.parameter,
        "execution_mode": "offline_common_trajectory_diagnostic",
        "executed_policy": False,
        "offline_diagnostic": True,
        "causal_regret_claim": False,
        "regret_reported": False,
        "trajectory_digest": trajectory.digest,
        "source_operator": trajectory.source_operator,
        "same_history_parameters_actions_damping_bonus": True,
        "Lambda_alg_T": float(last["Lambda_alg_cumulative"]),
        "V_alg_T": float(last["V_alg_cumulative"]),
        "Gamma_dynamic_T": float(last["Gamma_dynamic_cumulative"]),
        "endpoint_logdet_T": float(last["endpoint_logdet"]),
        "dynamic_identity_residual": float(last["dynamic_identity_residual"]),
        "kappa_plus_max": max(float(record["kappa_plus"]) for record in records),
        "action_set_transfer_Cbar_over_Chat_max": max(
            float(record["action_set_transfer_Cbar_over_Chat"]) for record in records
        ),
        "max_relative_width_distortion_from_full": max(
            float(record["max_relative_width_distortion_from_full"])
            for record in records
        ),
        "action_disagreement_rate": float(
            sum(bool(record["action_disagrees_with_full"]) for record in records)
            / trajectory.rounds
        ),
        "window_global_kappa_le_one_all_rounds": (
            all(bool(record["window_global_kappa_le_one"]) for record in records)
            if spec.kind == "unrescaled_window"
            else None
        ),
        "float_dtype": "float64",
    }
    return NonlinearOfflineDiagnostic(spec=spec, records=tuple(records), summary=summary)


def evaluate_nonlinear_common_trajectory(
    config: Mapping[str, Any] | NonlinearOperatorConfig,
    trajectory: NonlinearLoggedTrajectory,
    *,
    operators: Sequence[OperatorSpec] | None = None,
) -> NonlinearCommonTrajectoryResult:
    resolved = (
        config if isinstance(config, NonlinearOperatorConfig) else NonlinearOperatorConfig.from_mapping(config)
    )
    specs = resolved.specs if operators is None else tuple(operators)
    diagnostics = tuple(
        _offline_nonlinear_diagnostic(resolved, spec, trajectory) for spec in specs
    )
    return NonlinearCommonTrajectoryResult(
        trajectory=trajectory,
        diagnostics=diagnostics,
        summary={
            "event": "nonlinear_common_trajectory_summary",
            "seed": trajectory.seed,
            "rounds": trajectory.rounds,
            "execution_mode": "offline_common_trajectory_diagnostic",
            "executed_policy": False,
            "offline_diagnostic": True,
            "causal_regret_claim": False,
            "regret_reported": False,
            "trajectory_digest": trajectory.digest,
            "source_operator": trajectory.source_operator,
            "operators": [spec.name for spec in specs],
            "same_history_parameters_actions_damping_bonus": True,
        },
    )


def run_nonlinear_operator_ablation(
    config: Mapping[str, Any] | NonlinearOperatorConfig,
    seed: int,
    *,
    operators: Sequence[str | OperatorSpec] | None = None,
    include_common_trajectory: bool | None = None,
    measure_resources: bool = False,
) -> NonlinearOperatorAblationResult:
    resolved = (
        config if isinstance(config, NonlinearOperatorConfig) else NonlinearOperatorConfig.from_mapping(config)
    )
    specs = _select_specs(resolved.specs, operators)
    runs = tuple(
        run_nonlinear_operator(
            resolved, spec, seed, measure_resources=measure_resources
        )
        for spec in specs
    )
    include_offline = (
        resolved.common_trajectory_enabled
        if include_common_trajectory is None
        else bool(include_common_trajectory)
    )
    source = next((run for run in runs if run.spec.kind == "full"), None)
    if include_offline and source is None:
        source = run_nonlinear_operator(
            resolved, OperatorSpec("full"), seed, measure_resources=measure_resources
        )
    common = (
        evaluate_nonlinear_common_trajectory(
            resolved, source.trajectory, operators=specs
        )
        if include_offline and source is not None
        else None
    )
    contexts_equal = all(
        np.array_equal(run.trajectory.contexts, runs[0].trajectory.contexts)
        for run in runs[1:]
    )
    noises_equal = all(
        np.allclose(
            [record["realized_noise"] for record in run.records],
            [record["realized_noise"] for record in runs[0].records],
            rtol=0.0,
            atol=0.0,
        )
        for run in runs[1:]
    )
    summary = {
        "event": "nonlinear_operator_ablation_seed_summary",
        "seed": int(seed),
        "rounds": resolved.rounds,
        "environment": "smooth_nonlinear_tanh",
        "regime": resolved.regime,
        "center": resolved.center,
        "operators": [spec.name for spec in specs],
        "online_executed_policies": True,
        "comparison": "fixed_reference_bonus_and_damping",
        "common_random_contexts_across_methods": contexts_equal,
        "common_random_noise_across_methods": noises_equal,
        "common_trajectory_included": common is not None,
        "common_trajectory_offline": common is not None,
        "common_trajectory_causal_regret_claim": False,
        "online_summaries": [run.summary for run in runs],
        "common_trajectory_summary": None if common is None else common.summary,
    }
    return NonlinearOperatorAblationResult(
        seed=int(seed),
        config=resolved,
        online_runs=runs,
        common_trajectory=common,
        summary=summary,
    )


def _manifest_config(
    source: Mapping[str, Any],
    *,
    result: NonlinearOperatorAblationResult,
    spec: OperatorSpec,
    mode: str,
) -> dict[str, Any]:
    runtime = copy.deepcopy(dict(source))
    runtime["rounds"] = result.config.rounds
    runtime["environment_family"] = "smooth_nonlinear_tanh"
    runtime["environment"] = {
        "family": "smooth_nonlinear_tanh",
        "context_distribution": "normalized_rademacher",
        "context_dimension": CONTEXT_DIMENSION,
        "action_count": ACTION_COUNT,
        "noise_std": result.config.noise_std,
        "teacher_known_to_evaluator_only": True,
        "context_dependent_ranking": True,
    }
    runtime["model"] = {
        "architecture": "one_hidden_layer_tanh",
        "hidden_width": HIDDEN_WIDTH,
        "parameter_dimension": PARAMETER_DIMENSION,
        "dtype": "float64",
    }
    runtime["ridge"] = result.config.damping
    runtime["execution"] = {
        "environment": "smooth_nonlinear_tanh",
        "mode": mode,
        "seed": result.seed,
        "regime": result.config.regime,
        "center": result.config.center,
        "rounds": result.config.rounds,
        "operator": spec.name,
        "operator_kind": spec.kind,
        "operator_parameter": spec.parameter,
        "comparison": "fixed_reference_bonus_and_damping",
        "posthoc_diagnostics_are_certificates": False,
        "dtype": "float64",
    }
    return runtime


def _save(
    records: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    destination: Path,
    runtime_config: Mapping[str, Any],
    seed: int,
    *,
    overwrite: bool,
) -> None:
    with ExperimentLogger(
        destination,
        runtime_config,
        seed,
        repository=Path(__file__).resolve().parents[1],
        packages=("numpy", "scipy", "psutil"),
        overwrite=overwrite,
    ) as logger:
        for index, record in enumerate(records):
            logger.log_round(index, record)
    summary_path = destination / "summary.jsonl"
    if overwrite and summary_path.exists():
        summary_path.unlink()
    append_jsonl(summary_path, summary)


def save_nonlinear_operator_ablation(
    result: NonlinearOperatorAblationResult,
    output_root: str | Path,
    source_config: Mapping[str, Any],
    *,
    seed_set: str,
    overwrite: bool = False,
) -> Path:
    profile = str(source_config.get("profile", "default"))
    base = (
        Path(output_root)
        / profile
        / seed_set
        / "nonlinear"
        / result.config.regime
        / result.config.center
    )
    for run in result.online_runs:
        destination = base / run.spec.name / f"seed-{result.seed}"
        _save(
            run.records,
            run.summary,
            destination,
            _manifest_config(
                source_config, result=result, spec=run.spec, mode="online_adaptive"
            ),
            result.seed,
            overwrite=overwrite,
        )
    if result.common_trajectory is not None:
        for diagnostic in result.common_trajectory.diagnostics:
            destination = (
                base
                / "offline_common_trajectory"
                / diagnostic.spec.name
                / f"seed-{result.seed}"
            )
            _save(
                diagnostic.records,
                diagnostic.summary,
                destination,
                _manifest_config(
                    source_config,
                    result=result,
                    spec=diagnostic.spec,
                    mode="offline_common_trajectory_diagnostic",
                ),
                result.seed,
                overwrite=overwrite,
            )
    return base


__all__ = [
    "NonlinearCommonTrajectoryResult",
    "NonlinearLoggedTrajectory",
    "NonlinearOfflineDiagnostic",
    "NonlinearOnlineOperatorRun",
    "NonlinearOperatorAblationResult",
    "NonlinearOperatorConfig",
    "evaluate_nonlinear_common_trajectory",
    "run_nonlinear_operator",
    "run_nonlinear_operator_ablation",
    "save_nonlinear_operator_ablation",
]
