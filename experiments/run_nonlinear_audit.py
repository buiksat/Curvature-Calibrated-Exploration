"""Execute the small exact nonlinear curvature audit.

This driver intentionally materializes every Jacobian and curvature matrix in
float64.  Policy inputs come only from a fixed, time-indexed schedule.  Quantities
that use the known teacher, replayed frozen features, dense solves, or realized
CG errors are named ``posthoc_*`` and are audit diagnostics, not certification
claims.
"""

from __future__ import annotations

import argparse
import copy
import time
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np
import psutil
from numpy.typing import ArrayLike, NDArray

from .config import get_seed_set, load_config
from .curvature_operators import CurvatureOperator
from .logging_utils import ExperimentLogger, append_jsonl, canonical_json, seed_everything
from .nonlinear_environment import (
    ACTION_COUNT,
    CONTEXT_DIMENSION,
    HIDDEN_WIDTH,
    NonlinearBanditEnvironment,
    SmallTanhMLP,
)
from .theory_metrics import (
    cg_sandwich,
    cg_width,
    dynamic_logdet_metrics,
    generalized_eigenvalues,
)


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]

CENTER_VARIANTS = ("original", "corrected")


def _readonly(value: ArrayLike, *, dtype: np.dtype[Any] = np.dtype(np.float64)) -> NDArray[Any]:
    array = np.asarray(value, dtype=dtype).copy()
    array.setflags(write=False)
    return array


def _finite_positive(value: float, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _positive_integer(value: int, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


@dataclass(frozen=True)
class DriftRegime:
    """Deterministic optimization rule for one rung of the drift ladder."""

    name: str
    exact_head_ridge: bool
    learning_rate: float
    updates_per_round: int
    trust_region_cap: float


_REGIMES = {
    "frozen_head": DriftRegime("frozen_head", True, 0.0, 1, 0.0),
    "mild": DriftRegime("mild", False, 0.002, 2, 0.005),
    "medium": DriftRegime("medium", False, 0.004, 3, 0.020),
    "aggressive": DriftRegime("aggressive", False, 0.008, 4, 0.080),
}
DRIFT_REGIMES: Mapping[str, DriftRegime] = MappingProxyType(_REGIMES)


def get_drift_regime(name: str) -> DriftRegime:
    """Resolve one regime, accepting ``head_only`` as a compatibility alias."""

    canonical = "frozen_head" if name == "head_only" else name
    try:
        return DRIFT_REGIMES[canonical]
    except KeyError as error:
        raise ValueError(
            f"unknown drift regime {name!r}; choose from {list(DRIFT_REGIMES)}"
        ) from error


def active_parameter_indices(model: SmallTanhMLP, regime: str | DriftRegime) -> IntArray:
    resolved = get_drift_regime(regime) if isinstance(regime, str) else regime
    if resolved.exact_head_ridge:
        return np.asarray(model.head_indices, dtype=np.int64)
    return np.arange(model.parameter_dimension, dtype=np.int64)


@dataclass(frozen=True)
class TrainingUpdate:
    parameters: FloatArray
    objective: float
    gradient_norm: float
    step_norm: float
    backbone_step_norm: float
    trust_region_active: bool


def squared_loss_and_gradient(
    model: SmallTanhMLP,
    parameters: ArrayLike,
    contexts: ArrayLike,
    actions: ArrayLike,
    rewards: ArrayLike,
    *,
    damping: float,
    noise_variance: float,
) -> tuple[float, FloatArray]:
    """Return the paper's full-history squared-loss objective and gradient."""

    theta = np.asarray(parameters, dtype=np.float64)
    if theta.shape != (model.parameter_dimension,) or not np.all(np.isfinite(theta)):
        raise ValueError("parameters have an invalid shape or non-finite value")
    x = np.asarray(contexts, dtype=np.float64)
    a = np.asarray(actions, dtype=np.int64)
    r = np.asarray(rewards, dtype=np.float64)
    sample_count = x.shape[0] if x.ndim == 2 else -1
    if x.shape != (sample_count, model.layout.context_dimension):
        raise ValueError("contexts have an invalid shape")
    if a.shape != (sample_count,) or r.shape != (sample_count,):
        raise ValueError("actions and rewards must match the context count")
    if np.any(a < 0) or np.any(a >= model.layout.action_count):
        raise ValueError("actions contain an out-of-range value")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(r)):
        raise ValueError("training data must be finite")
    ridge = _finite_positive(damping, name="damping")
    variance = _finite_positive(noise_variance, name="noise_variance")

    objective = 0.5 * ridge * float(theta @ theta)
    gradient = ridge * theta.copy()
    for context, action, reward in zip(x, a, r, strict=True):
        prediction = model.mean(theta, context, int(action))
        residual = prediction - float(reward)
        jacobian = model.jacobian(theta, context, int(action))
        objective += 0.5 * residual * residual / variance
        gradient += (residual / variance) * jacobian
    return float(objective), np.asarray(gradient, dtype=np.float64)


def exact_ridge_head_update(
    model: SmallTanhMLP,
    contexts: ArrayLike,
    actions: ArrayLike,
    rewards: ArrayLike,
    *,
    damping: float,
    noise_variance: float,
) -> FloatArray:
    """Solve the frozen-backbone action-head ridge problem exactly."""

    ridge = _finite_positive(damping, name="damping")
    variance = _finite_positive(noise_variance, name="noise_variance")
    x = np.asarray(contexts, dtype=np.float64)
    a = np.asarray(actions, dtype=np.int64)
    r = np.asarray(rewards, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != model.layout.context_dimension:
        raise ValueError("contexts have an invalid shape")
    count = x.shape[0]
    if a.shape != (count,) or r.shape != (count,):
        raise ValueError("actions and rewards must match the context count")
    if np.any(a < 0) or np.any(a >= model.layout.action_count):
        raise ValueError("actions contain an out-of-range value")

    head = model.head_indices
    head_dimension = head.size
    if count == 0:
        return np.zeros(model.parameter_dimension, dtype=np.float64)
    features = np.stack(
        [
            model.jacobian(np.zeros(model.parameter_dimension), context, int(action))[head]
            for context, action in zip(x, a, strict=True)
        ],
        axis=0,
    )
    base_means = np.asarray(
        [
            model.mean(np.zeros(model.parameter_dimension), context, int(action))
            for context, action in zip(x, a, strict=True)
        ],
        dtype=np.float64,
    )
    gram = ridge * np.eye(head_dimension, dtype=np.float64)
    gram += features.T @ features / variance
    right_hand_side = features.T @ (r - base_means) / variance
    head_solution = np.linalg.solve(gram, right_hand_side)
    result = np.zeros(model.parameter_dimension, dtype=np.float64)
    result[head] = head_solution
    return result


def deterministic_online_update(
    model: SmallTanhMLP,
    parameters: ArrayLike,
    contexts: ArrayLike,
    actions: ArrayLike,
    rewards: ArrayLike,
    *,
    regime: str | DriftRegime,
    damping: float,
    noise_variance: float,
) -> TrainingUpdate:
    """Apply an exact head solve or deterministic capped full-batch steps."""

    resolved = get_drift_regime(regime) if isinstance(regime, str) else regime
    start = np.asarray(parameters, dtype=np.float64)
    if start.shape != (model.parameter_dimension,):
        raise ValueError("parameters have an invalid shape")
    if resolved.exact_head_ridge:
        updated = exact_ridge_head_update(
            model,
            contexts,
            actions,
            rewards,
            damping=damping,
            noise_variance=noise_variance,
        )
        objective, gradient = squared_loss_and_gradient(
            model,
            updated,
            contexts,
            actions,
            rewards,
            damping=damping,
            noise_variance=noise_variance,
        )
        active_gradient = gradient[model.head_indices]
        step = updated - start
        return TrainingUpdate(
            parameters=_readonly(updated),
            objective=objective,
            gradient_norm=float(np.linalg.norm(active_gradient)),
            step_norm=float(np.linalg.norm(step)),
            backbone_step_norm=float(np.linalg.norm(step[model.backbone_indices])),
            trust_region_active=False,
        )

    current = start.copy()
    trust_region_active = False
    for _ in range(resolved.updates_per_round):
        _, gradient = squared_loss_and_gradient(
            model,
            current,
            contexts,
            actions,
            rewards,
            damping=damping,
            noise_variance=noise_variance,
        )
        proposal = current - resolved.learning_rate * gradient
        displacement = proposal - start
        norm = float(np.linalg.norm(displacement))
        if norm > resolved.trust_region_cap:
            proposal = start + (resolved.trust_region_cap / norm) * displacement
            trust_region_active = True
        current = np.asarray(proposal, dtype=np.float64)
    objective, final_gradient = squared_loss_and_gradient(
        model,
        current,
        contexts,
        actions,
        rewards,
        damping=damping,
        noise_variance=noise_variance,
    )
    step = current - start
    return TrainingUpdate(
        parameters=_readonly(current),
        objective=objective,
        gradient_norm=float(np.linalg.norm(final_gradient)),
        step_norm=float(np.linalg.norm(step)),
        backbone_step_norm=float(np.linalg.norm(step[model.backbone_indices])),
        trust_region_active=trust_region_active,
    )


@dataclass(frozen=True)
class PredeterminedPolicySchedule:
    """Time-only quantities fixed before any trajectory is observed."""

    beta_base: float = 2.25
    beta_log_rate: float = 0.10
    cg_energy_tolerance: float = 0.05
    condition_number_bound: float = 1.0e8

    def __post_init__(self) -> None:
        _finite_positive(self.beta_base, name="beta_base")
        if not np.isfinite(self.beta_log_rate) or self.beta_log_rate < 0.0:
            raise ValueError("beta_log_rate must be finite and nonnegative")
        tolerance = _finite_positive(
            self.cg_energy_tolerance, name="cg_energy_tolerance"
        )
        if tolerance >= 1.0:
            raise ValueError("cg_energy_tolerance must be below one")
        _finite_positive(self.condition_number_bound, name="condition_number_bound")

    def beta(self, round_number: int) -> float:
        index = _positive_integer(round_number, name="round_number")
        return float(self.beta_base + self.beta_log_rate * np.sqrt(np.log1p(index)))

    def centering(self, regime: str, center: str, round_number: int) -> float:
        _positive_integer(round_number, name="round_number")
        if center == "corrected":
            return 0.0
        if center != "original":
            raise ValueError(f"unknown center {center!r}")
        canonical = get_drift_regime(regime).name
        return {
            "frozen_head": 0.0,
            "mild": 0.35,
            "medium": 0.80,
            "aggressive": 1.60,
        }[canonical]

    def transfer_factor(self, regime: str, round_number: int) -> float:
        _positive_integer(round_number, name="round_number")
        canonical = get_drift_regime(regime).name
        return {
            "frozen_head": 1.0,
            "mild": 1.25,
            "medium": 2.00,
            "aggressive": 4.00,
        }[canonical]

    def values(self, regime: str, center: str, round_number: int) -> dict[str, float]:
        beta = self.beta(round_number)
        psi = self.centering(regime, center, round_number)
        return {
            "beta": beta,
            "centering": psi,
            "omega": beta + psi,
            "transfer_factor": self.transfer_factor(regime, round_number),
            "cg_energy_tolerance": self.cg_energy_tolerance,
            "condition_number_bound": self.condition_number_bound,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": "predetermined_time_only",
            "beta_base": self.beta_base,
            "beta_log_rate": self.beta_log_rate,
            "cg_energy_tolerance": self.cg_energy_tolerance,
            "condition_number_bound": self.condition_number_bound,
            "centering_by_regime": {
                name: self.centering(name, "original", 1) for name in DRIFT_REGIMES
            },
            "transfer_factor_by_regime": {
                name: self.transfer_factor(name, 1) for name in DRIFT_REGIMES
            },
        }


@dataclass(frozen=True)
class LinearizedRidgeFit:
    parameters: FloatArray
    intercepts: FloatArray
    pseudo_responses: FloatArray
    right_hand_side: FloatArray


def frozen_linearized_ridge(
    frozen_jacobians: ArrayLike,
    collection_parameters: ArrayLike,
    collection_means: ArrayLike,
    rewards: ArrayLike,
    *,
    damping: float,
    noise_variance: float,
) -> LinearizedRidgeFit:
    """Construct and solve the exact frozen-feature pseudo-response ridge fit."""

    gradients = np.asarray(frozen_jacobians, dtype=np.float64)
    checkpoints = np.asarray(collection_parameters, dtype=np.float64)
    means = np.asarray(collection_means, dtype=np.float64)
    observed = np.asarray(rewards, dtype=np.float64)
    if gradients.ndim != 2:
        raise ValueError("frozen_jacobians must be a matrix")
    count, dimension = gradients.shape
    if dimension == 0:
        raise ValueError("frozen_jacobians must have positive width")
    if checkpoints.shape != (count, dimension):
        raise ValueError("collection_parameters have an invalid shape")
    if means.shape != (count,) or observed.shape != (count,):
        raise ValueError("means and rewards must match frozen_jacobians")
    ridge = _finite_positive(damping, name="damping")
    variance = _finite_positive(noise_variance, name="noise_variance")
    intercepts = means - np.einsum("ij,ij->i", gradients, checkpoints)
    pseudo_responses = observed - intercepts
    gram = ridge * np.eye(dimension, dtype=np.float64)
    gram += gradients.T @ gradients / variance
    rhs = gradients.T @ pseudo_responses / variance
    solution = np.linalg.solve(gram, rhs)
    return LinearizedRidgeFit(
        parameters=_readonly(solution),
        intercepts=_readonly(intercepts),
        pseudo_responses=_readonly(pseudo_responses),
        right_hand_side=_readonly(rhs),
    )


def corrected_centers(
    means: ArrayLike,
    jacobians: ArrayLike,
    current_parameters: ArrayLike,
    linearized_parameters: ArrayLike,
) -> FloatArray:
    """Return the exact frozen-ridge corrected center for every action."""

    values = np.asarray(means, dtype=np.float64)
    gradients = np.asarray(jacobians, dtype=np.float64)
    current = np.asarray(current_parameters, dtype=np.float64)
    linearized = np.asarray(linearized_parameters, dtype=np.float64)
    if gradients.ndim != 2 or values.shape != (gradients.shape[0],):
        raise ValueError("means and jacobians have incompatible shapes")
    if current.shape != (gradients.shape[1],) or linearized.shape != current.shape:
        raise ValueError("parameter vectors have an incompatible shape")
    return np.asarray(values + gradients @ (linearized - current), dtype=np.float64)


@dataclass(frozen=True)
class AuditSnapshot:
    round_index: int
    active_indices: IntArray
    parameters: FloatArray
    theta_hat_lin: FloatArray
    frozen_intercepts: FloatArray
    pseudo_responses: FloatArray
    frozen_jacobians: FloatArray
    replayed_current_jacobians: FloatArray
    frozen_curvature: FloatArray
    current_curvature: FloatArray
    action_jacobians: FloatArray
    original_centers: FloatArray
    corrected_centers: FloatArray
    teacher_means: FloatArray


@dataclass(frozen=True)
class AuditRun:
    seed: int
    regime: str
    center: str
    records: tuple[dict[str, Any], ...]
    snapshots: tuple[AuditSnapshot, ...]
    parameter_path: FloatArray
    contexts: FloatArray
    actions: IntArray
    rewards: FloatArray

    def deterministic_signature(self) -> str:
        """Canonical trajectory signature excluding logger timestamps."""

        return canonical_json(
            {
                "seed": self.seed,
                "regime": self.regime,
                "center": self.center,
                "records": self.records,
                "parameter_path": self.parameter_path.tolist(),
                "contexts": self.contexts.tolist(),
                "actions": self.actions.tolist(),
                "rewards": self.rewards.tolist(),
            }
        )


@dataclass
class _History:
    contexts: list[FloatArray]
    actions: list[int]
    rewards: list[float]
    frozen_jacobians: list[FloatArray]
    parameters: list[FloatArray]
    means: list[float]

    @classmethod
    def empty(cls) -> _History:
        return cls([], [], [], [], [], [])


def _history_arrays(
    history: _History,
    *,
    context_dimension: int,
    active_dimension: int,
) -> tuple[FloatArray, IntArray, FloatArray, FloatArray, FloatArray, FloatArray]:
    count = len(history.actions)
    contexts = (
        np.stack(history.contexts, axis=0)
        if count
        else np.empty((0, context_dimension), dtype=np.float64)
    )
    actions = np.asarray(history.actions, dtype=np.int64)
    rewards = np.asarray(history.rewards, dtype=np.float64)
    frozen = (
        np.stack(history.frozen_jacobians, axis=0)
        if count
        else np.empty((0, active_dimension), dtype=np.float64)
    )
    checkpoints = (
        np.stack(history.parameters, axis=0)
        if count
        else np.empty((0, active_dimension), dtype=np.float64)
    )
    means = np.asarray(history.means, dtype=np.float64)
    return contexts, actions, rewards, frozen, checkpoints, means


def _principal_inverse_root(matrix: FloatArray) -> FloatArray:
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    if np.any(eigenvalues <= 0.0):
        raise ArithmeticError("matrix is not SPD")
    return np.asarray(
        (eigenvectors * (1.0 / np.sqrt(eigenvalues))) @ eigenvectors.T,
        dtype=np.float64,
    )


def _condition_number(matrix: FloatArray) -> float:
    eigenvalues = np.linalg.eigvalsh(matrix)
    return float(eigenvalues[-1] / eigenvalues[0])


def _logdet_ratio(matrix: FloatArray, damping: float) -> float:
    eigenvalues = np.linalg.eigvalsh(matrix)
    if np.any(eigenvalues <= 0.0) or not np.all(np.isfinite(eigenvalues)):
        raise ArithmeticError("matrix determinant is not positive")
    return float(np.sum(np.log(eigenvalues)) - matrix.shape[0] * np.log(damping))


def _optimizer_and_mismatch(
    model: SmallTanhMLP,
    theta: FloatArray,
    active: IntArray,
    contexts: FloatArray,
    actions: IntArray,
    rewards: FloatArray,
    frozen: FloatArray,
    checkpoints: FloatArray,
    collection_means: FloatArray,
    theta_hat: FloatArray,
    cbar: FloatArray,
    *,
    damping: float,
    noise_variance: float,
) -> tuple[float, FloatArray, float, float, float]:
    count = actions.size
    theta_active = theta[active]
    if count == 0:
        mismatch = np.zeros(active.size, dtype=np.float64)
        gradient = damping * theta_active
    else:
        current_means = np.asarray(
            [
                model.mean(theta, context, int(action))
                for context, action in zip(contexts, actions, strict=True)
            ],
            dtype=np.float64,
        )
        current_jacobians = np.stack(
            [
                model.jacobian(theta, context, int(action))[active]
                for context, action in zip(contexts, actions, strict=True)
            ],
            axis=0,
        )
        delta = current_jacobians - frozen
        bar_mu = collection_means + np.einsum(
            "ij,ij->i", frozen, theta_active[None, :] - checkpoints
        )
        nonlinear_remainder = current_means - bar_mu
        bar_residual = bar_mu - rewards
        mismatch = np.sum(
            bar_residual[:, None] * delta
            + nonlinear_remainder[:, None] * frozen
            + nonlinear_remainder[:, None] * delta,
            axis=0,
        ) / noise_variance
        residual = current_means - rewards
        gradient = damping * theta_active + current_jacobians.T @ residual / noise_variance
    zeta = float(np.linalg.norm(gradient))
    mismatch_metric_norm = float(np.sqrt(mismatch @ np.linalg.solve(cbar, mismatch)))
    primitive_psi = zeta / np.sqrt(damping) + mismatch_metric_norm
    coarse_psi = (zeta + float(np.linalg.norm(mismatch))) / np.sqrt(damping)
    linearized_gradient = cbar @ (theta_active - theta_hat)
    identity_residual = float(np.linalg.norm(gradient - linearized_gradient - mismatch))
    return zeta, mismatch, primitive_psi, max(coarse_psi, primitive_psi), identity_residual


def _all_replayed_gradient_bound(
    model: SmallTanhMLP,
    theta: FloatArray,
    active: IntArray,
    prior_contexts: FloatArray,
    current_context: FloatArray,
) -> float:
    contexts = np.concatenate((prior_contexts, current_context[None, :]), axis=0)
    maximum = 0.0
    for context in contexts:
        norms = np.linalg.norm(model.jacobians(theta, context)[:, active], axis=1)
        maximum = max(maximum, float(np.max(norms)))
    return maximum


def _snapshot_pre_action(
    environment: NonlinearBanditEnvironment,
    theta: FloatArray,
    active: IntArray,
    history: _History,
    context: FloatArray,
    *,
    damping: float,
    cg_budget: int,
    schedule: PredeterminedPolicySchedule,
    regime: str,
    center: str,
    round_number: int,
    epsilon_sum_prior: float,
    epsilon_square_sum_prior: float,
    delta_probability: float,
) -> tuple[dict[str, Any], AuditSnapshot, dict[str, Any]]:
    model = environment.model
    variance = environment.noise_std**2
    theta_active = theta[active]
    theta_star = environment.teacher_displacement[active]
    (
        contexts,
        actions,
        rewards,
        frozen,
        checkpoints,
        collection_means,
    ) = _history_arrays(
        history,
        context_dimension=model.layout.context_dimension,
        active_dimension=active.size,
    )
    replayed = (
        np.stack(
            [
                model.jacobian(theta, old_context, int(action))[active]
                for old_context, action in zip(contexts, actions, strict=True)
            ],
            axis=0,
        )
        if actions.size
        else np.empty((0, active.size), dtype=np.float64)
    )
    frozen_operator = CurvatureOperator(
        frozen, damping=damping, noise_variance=variance
    )
    current_operator = CurvatureOperator(
        replayed, damping=damping, noise_variance=variance
    )
    cbar = frozen_operator.to_dense()
    current_curvature = current_operator.to_dense()
    ridge_fit = frozen_linearized_ridge(
        frozen,
        checkpoints,
        collection_means,
        rewards,
        damping=damping,
        noise_variance=variance,
    )
    theta_hat = ridge_fit.parameters

    action_means = model.means(theta, context)
    action_jacobians = model.jacobians(theta, context)[:, active]
    teacher_means = environment.mean_rewards(context)
    corrected = corrected_centers(
        action_means, action_jacobians, theta_active, theta_hat
    )
    remainder = teacher_means - action_means - action_jacobians @ (
        theta_star - theta_active
    )
    epsilon_lin = float(np.max(np.abs(remainder)))
    corrected_identity = teacher_means - corrected - (
        action_jacobians @ (theta_star - theta_hat) + remainder
    )

    frozen_solutions = np.linalg.solve(cbar, action_jacobians.T).T
    current_solutions = np.linalg.solve(current_curvature, action_jacobians.T).T
    frozen_width_squared = np.einsum(
        "ij,ij->i", action_jacobians, frozen_solutions
    )
    current_width_squared = np.einsum(
        "ij,ij->i", action_jacobians, current_solutions
    )
    centering_discrepancy = np.abs(
        action_jacobians @ (theta_active - theta_hat)
    )
    frozen_widths = np.sqrt(frozen_width_squared)
    centering_ratios = centering_discrepancy / frozen_widths
    centering_ratio = float(np.max(centering_ratios))

    zeta, mismatch, primitive_psi, coarse_psi, mismatch_identity_residual = (
        _optimizer_and_mismatch(
            model,
            theta,
            active,
            contexts,
            actions,
            rewards,
            frozen,
            checkpoints,
            collection_means,
            theta_hat,
            cbar,
            damping=damping,
            noise_variance=variance,
        )
    )

    delta_jacobians = replayed - frozen
    inverse_root = _principal_inverse_root(cbar)
    whitened_delta = inverse_root @ delta_jacobians.T / environment.noise_std
    if actions.size:
        chi = float(np.linalg.norm(whitened_delta, ord=2))
        chi_frobenius = float(np.linalg.norm(whitened_delta, ord="fro"))
    else:
        chi = 0.0
        chi_frobenius = 0.0
    whitened_curvature_difference = (
        inverse_root @ (current_curvature - cbar) @ inverse_root
    )
    curvature_difference_norm = float(
        np.linalg.norm(whitened_curvature_difference, ord=2)
    )
    transfer_factor = (1.0 + chi) ** 2
    generalized = generalized_eigenvalues(current_curvature, cbar)
    action_transfer = float(np.max(frozen_width_squared / current_width_squared))

    schedule_values = schedule.values(regime, center, round_number)
    residual_tolerance = schedule.cg_energy_tolerance / np.sqrt(
        schedule.condition_number_bound
    )
    cg_squared: list[float] = []
    cg_energy_errors: list[float] = []
    cg_relative_residuals: list[float] = []
    cg_iterations: list[int] = []
    cg_converged: list[bool] = []
    cg_lower_bounds: list[float] = []
    cg_upper_bounds: list[float] = []
    for jacobian in action_jacobians:
        approximate = cg_width(
            current_operator,
            jacobian,
            tolerance=residual_tolerance,
            max_iterations=cg_budget,
            raise_on_nonconvergence=False,
        )
        sandwich = cg_sandwich(
            current_operator,
            jacobian,
            approximate.solution,
            require_error_below_one=False,
        )
        cg_squared.append(approximate.width_squared)
        cg_energy_errors.append(sandwich.relative_energy_error)
        cg_relative_residuals.append(approximate.cg.relative_residual_norm)
        cg_iterations.append(approximate.cg.iterations)
        cg_converged.append(approximate.cg.converged)
        cg_lower_bounds.append(sandwich.lower_bound)
        cg_upper_bounds.append(sandwich.upper_bound)
    cg_squared_array = np.asarray(cg_squared, dtype=np.float64)
    cg_error_array = np.asarray(cg_energy_errors, dtype=np.float64)
    cg_residual_array = np.asarray(cg_relative_residuals, dtype=np.float64)
    cg_max_error = float(np.max(cg_error_array))

    gamma_prior = _logdet_ratio(cbar, damping)
    beta_exact = float(
        np.sqrt(gamma_prior + 2.0 * np.log(1.0 / delta_probability))
        + np.sqrt(damping) * np.linalg.norm(theta_star)
        + np.sqrt(epsilon_square_sum_prior) / environment.noise_std
    )

    policy_omega_original = schedule.beta(round_number) + schedule.centering(
        regime, "original", round_number
    )
    policy_omega_corrected = schedule.beta(round_number)
    policy_transfer = schedule.transfer_factor(regime, round_number)
    policy_width_scale = np.sqrt(
        policy_transfer / (1.0 - schedule.cg_energy_tolerance)
    ) * np.sqrt(cg_squared_array)
    policy_original_score = action_means + policy_omega_original * policy_width_scale
    policy_corrected_score = corrected + policy_omega_corrected * policy_width_scale
    chosen_policy_score = (
        policy_original_score if center == "original" else policy_corrected_score
    )

    diagnostic_error = min(cg_max_error, 1.0 - 1.0e-12)
    diagnostic_width_scale = np.sqrt(
        transfer_factor / (1.0 - diagnostic_error)
    ) * np.sqrt(cg_squared_array)
    diagnostic_original_score = action_means + (
        beta_exact + primitive_psi
    ) * diagnostic_width_scale
    diagnostic_corrected_score = corrected + beta_exact * diagnostic_width_scale

    condition_cbar = _condition_number(cbar)
    condition_current = _condition_number(current_curvature)
    scheduled_residual_certificate = (
        np.sqrt(schedule.condition_number_bound) * cg_residual_array
    )
    exact_condition_residual_bound = np.sqrt(condition_current) * cg_residual_array
    condition_bound_holds = condition_current <= schedule.condition_number_bound
    cg_energy_schedule_holds = bool(
        np.all(cg_error_array <= schedule.cg_energy_tolerance)
    )
    cg_residual_rule_holds = bool(np.all(cg_residual_array <= residual_tolerance))
    transfer_schedule_holds = policy_transfer + 1.0e-12 >= transfer_factor
    centering_schedule_holds = (
        center == "corrected"
        or schedule.centering(regime, center, round_number) + 1.0e-12
        >= centering_ratio
    )
    beta_schedule_holds = schedule.beta(round_number) + 1.0e-12 >= beta_exact

    metrics: dict[str, Any] = {
        "round_number": round_number,
        "executed_policy": True,
        "execution_mode": "online_adaptive",
        "policy_regime": regime,
        "policy_center": center,
        "policy_schedule_source": "predetermined_time_only",
        "posthoc_diagnostic_status": "audit_only_not_a_certification_claim",
        "certified_run_claim": False,
        "policy_beta": schedule_values["beta"],
        "policy_centering": schedule_values["centering"],
        "policy_omega": schedule_values["omega"],
        "policy_transfer_factor": schedule_values["transfer_factor"],
        "policy_cg_energy_tolerance": schedule_values["cg_energy_tolerance"],
        "policy_condition_number_bound": schedule_values["condition_number_bound"],
        "policy_scores_all_actions": chosen_policy_score.tolist(),
        "policy_original_scores_all_actions": policy_original_score.tolist(),
        "policy_corrected_scores_all_actions": policy_corrected_score.tolist(),
        "policy_optimism_margin_all_actions": (
            chosen_policy_score - teacher_means
        ).tolist(),
        "policy_optimism_violation_actions": np.flatnonzero(
            chosen_policy_score < teacher_means
        ).astype(int).tolist(),
        "policy_optimism_violation_count": int(
            np.count_nonzero(chosen_policy_score < teacher_means)
        ),
        "policy_original_optimism_violation_count": int(
            np.count_nonzero(policy_original_score < teacher_means)
        ),
        "policy_corrected_optimism_violation_count": int(
            np.count_nonzero(policy_corrected_score < teacher_means)
        ),
        "posthoc_epsilon_lin": epsilon_lin,
        "posthoc_E_prior": epsilon_sum_prior,
        "posthoc_E_including_round": epsilon_sum_prior + epsilon_lin,
        "posthoc_F_prior": epsilon_square_sum_prior,
        "posthoc_F_including_round": epsilon_square_sum_prior + epsilon_lin**2,
        "posthoc_theta_hat_lin_norm": float(np.linalg.norm(theta_hat)),
        "posthoc_theta_hat_normal_equation_residual": float(
            np.linalg.norm(cbar @ theta_hat - ridge_fit.right_hand_side)
        ),
        "posthoc_corrected_center_identity_error": float(
            np.max(np.abs(corrected_identity))
        ),
        "posthoc_centering_discrepancy_all_actions": centering_discrepancy.tolist(),
        "posthoc_centering_ratio_all_actions": centering_ratios.tolist(),
        "posthoc_centering_ratio": centering_ratio,
        "posthoc_optimizer_residual_zeta": zeta,
        "posthoc_mismatch_norm": float(np.linalg.norm(mismatch)),
        "posthoc_primitive_psi": primitive_psi,
        "posthoc_coarse_psi": coarse_psi,
        "posthoc_mismatch_gradient_identity_residual": mismatch_identity_residual,
        "posthoc_chi_operator_norm": chi,
        "posthoc_chi_frobenius_primitive": chi_frobenius,
        "posthoc_transfer_factor_one_plus_chi_squared": transfer_factor,
        "posthoc_whitened_curvature_difference_operator_norm": curvature_difference_norm,
        "posthoc_generalized_eigenvalue_C_over_Cbar": generalized.maximum,
        "posthoc_generalized_eigen_residual": generalized.residual_norm,
        "posthoc_actionwise_required_transfer": action_transfer,
        "posthoc_condition_number_Cbar": condition_cbar,
        "posthoc_condition_number_C": condition_current,
        "posthoc_frozen_width_squared_all_actions": frozen_width_squared.tolist(),
        "posthoc_current_width_squared_all_actions": current_width_squared.tolist(),
        "posthoc_cg_width_squared_all_actions": cg_squared_array.tolist(),
        "posthoc_cg_energy_error_all_actions": cg_error_array.tolist(),
        "posthoc_cg_relative_residual_all_actions": cg_residual_array.tolist(),
        "posthoc_cg_scheduled_residual_certificate_all_actions": scheduled_residual_certificate.tolist(),
        "posthoc_cg_exact_condition_residual_bound_all_actions": exact_condition_residual_bound.tolist(),
        "posthoc_cg_iterations_all_actions": cg_iterations,
        "posthoc_cg_converged_all_actions": cg_converged,
        "posthoc_cg_sandwich_lower_all_actions": cg_lower_bounds,
        "posthoc_cg_sandwich_upper_all_actions": cg_upper_bounds,
        "posthoc_cg_max_energy_error": cg_max_error,
        "posthoc_gamma_frozen_prior": gamma_prior,
        "posthoc_beta_exact_teacher_diagnostic": beta_exact,
        "posthoc_original_optimism_violation_count": int(
            np.count_nonzero(diagnostic_original_score < teacher_means)
        ),
        "posthoc_corrected_optimism_violation_count": int(
            np.count_nonzero(diagnostic_corrected_score < teacher_means)
        ),
        "posthoc_original_optimism_margin_all_actions": (
            diagnostic_original_score - teacher_means
        ).tolist(),
        "posthoc_corrected_optimism_margin_all_actions": (
            diagnostic_corrected_score - teacher_means
        ).tolist(),
        "posthoc_schedule_check_beta_holds": beta_schedule_holds,
        "posthoc_schedule_check_centering_holds": centering_schedule_holds,
        "posthoc_schedule_check_transfer_holds": transfer_schedule_holds,
        "posthoc_schedule_check_condition_bound_holds": condition_bound_holds,
        "posthoc_schedule_check_cg_energy_holds": cg_energy_schedule_holds,
        "posthoc_schedule_check_cg_residual_rule_holds": cg_residual_rule_holds,
        "posthoc_schedule_check_cg_residual_certificate_holds": bool(
            np.all(
                scheduled_residual_certificate
                <= schedule.cg_energy_tolerance
            )
        ),
    }
    snapshot = AuditSnapshot(
        round_index=round_number - 1,
        active_indices=_readonly(active, dtype=np.dtype(np.int64)),
        parameters=_readonly(theta_active),
        theta_hat_lin=_readonly(theta_hat),
        frozen_intercepts=_readonly(ridge_fit.intercepts),
        pseudo_responses=_readonly(ridge_fit.pseudo_responses),
        frozen_jacobians=_readonly(frozen),
        replayed_current_jacobians=_readonly(replayed),
        frozen_curvature=_readonly(cbar),
        current_curvature=_readonly(current_curvature),
        action_jacobians=_readonly(action_jacobians),
        original_centers=_readonly(action_means),
        corrected_centers=_readonly(corrected),
        teacher_means=_readonly(teacher_means),
    )
    internal = {
        "current_operator": current_operator,
        "current_curvature": current_curvature,
        "frozen_curvature": cbar,
        "action_jacobians": action_jacobians,
        "action_means": action_means,
        "teacher_means": teacher_means,
        "theta_hat": theta_hat,
        "epsilon_lin": epsilon_lin,
        "primitive_psi": primitive_psi,
        "beta_exact": beta_exact,
        "transfer_factor": transfer_factor,
        "cg_max_error": cg_max_error,
        "cg_width_squared": cg_squared_array,
        "policy_scores": chosen_policy_score,
        "schedule_checks": (
            beta_schedule_holds
            and centering_schedule_holds
            and transfer_schedule_holds
            and condition_bound_holds
            and cg_energy_schedule_holds
        ),
        "gradient_bound": _all_replayed_gradient_bound(
            model, theta, active, contexts, context
        ),
    }
    return metrics, snapshot, internal


def run_single_audit(
    *,
    seed: int,
    regime: str = "frozen_head",
    center: str = "original",
    rounds: int = 20,
    damping: float = 1.0,
    noise_std: float = 0.1,
    cg_max_iterations: int | None = None,
    confidence_delta: float = 0.1,
    schedule: PredeterminedPolicySchedule | None = None,
    snapshot_rounds: Sequence[int] | None = None,
    environment: NonlinearBanditEnvironment | None = None,
    measure_resources: bool = False,
) -> AuditRun:
    """Execute one predetermined policy and return exact audit diagnostics."""

    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, (int, np.integer)):
        raise TypeError("seed must be an integer")
    if int(seed) < 0:
        raise ValueError("seed must be nonnegative")
    horizon = _positive_integer(rounds, name="rounds")
    ridge = _finite_positive(damping, name="damping")
    standard_deviation = _finite_positive(noise_std, name="noise_std")
    probability = float(confidence_delta)
    if not np.isfinite(probability) or not 0.0 < probability < 1.0:
        raise ValueError("confidence_delta must lie in (0, 1)")
    resolved_regime = get_drift_regime(regime)
    if center not in CENTER_VARIANTS:
        raise ValueError(f"center must be one of {CENTER_VARIANTS}")
    policy_schedule = PredeterminedPolicySchedule() if schedule is None else schedule
    env = (
        NonlinearBanditEnvironment(int(seed), noise_std=standard_deviation)
        if environment is None
        else environment
    )
    if env.action_count != ACTION_COUNT:
        raise ValueError(f"the nonlinear audit requires exactly K={ACTION_COUNT} actions")
    if not np.isclose(env.noise_std, standard_deviation):
        raise ValueError("environment noise_std does not match the audit noise_std")
    model = env.model
    active = active_parameter_indices(model, resolved_regime)
    dimension = active.size
    cg_budget = dimension if cg_max_iterations is None else _positive_integer(
        cg_max_iterations, name="cg_max_iterations"
    )
    if snapshot_rounds is None:
        snapshot_set = set(range(1, horizon + 1))
    else:
        snapshot_set = {int(value) for value in snapshot_rounds}
        if any(value < 1 or value > horizon for value in snapshot_set):
            raise ValueError("snapshot_rounds must lie within [1, rounds]")
        snapshot_set.add(horizon)

    theta = np.zeros(model.parameter_dimension, dtype=np.float64)
    history = _History.empty()
    parameter_path = [theta.copy()]
    records: list[dict[str, Any]] = []
    snapshots: list[AuditSnapshot] = []
    curvature_sequence: list[FloatArray] = []
    played_jacobians: list[FloatArray] = []
    played_cg_width_squared: list[float] = []
    policy_s_sum = 0.0
    diagnostic_s_sum = 0.0
    epsilon_sum = 0.0
    epsilon_square_sum = 0.0
    cumulative_regret = 0.0
    cumulative_path_length = 0.0
    cumulative_backbone_path_length = 0.0
    gradient_bound_seen = 0.0
    all_schedule_checks = True
    variance = standard_deviation**2
    run_started = time.perf_counter()
    process = psutil.Process() if measure_resources else None
    peak_host_memory_bytes = process.memory_info().rss if process is not None else 0

    for round_index in range(horizon):
        round_started = time.perf_counter()
        round_number = round_index + 1
        context = env.draw_context()
        metrics, snapshot, internal = _snapshot_pre_action(
            env,
            theta,
            active,
            history,
            context,
            damping=ridge,
            cg_budget=cg_budget,
            schedule=policy_schedule,
            regime=resolved_regime.name,
            center=center,
            round_number=round_number,
            epsilon_sum_prior=epsilon_sum,
            epsilon_square_sum_prior=epsilon_square_sum,
            delta_probability=probability,
        )
        current_curvature = np.asarray(internal["current_curvature"], dtype=np.float64)
        if curvature_sequence:
            if not np.allclose(
                current_curvature, curvature_sequence[-1], rtol=2.0e-12, atol=2.0e-13
            ):
                raise FloatingPointError("terminal and next-round curvatures disagree")
        else:
            curvature_sequence.append(current_curvature.copy())

        scores = np.asarray(internal["policy_scores"], dtype=np.float64)
        action = int(np.argmax(scores))
        teacher_means = np.asarray(internal["teacher_means"], dtype=np.float64)
        optimal_action = int(np.argmax(teacher_means))
        instantaneous_regret = float(teacher_means[optimal_action] - teacher_means[action])
        cumulative_regret += instantaneous_regret
        reward, realized_noise = env.reward(context, action)

        theta_active = theta[active].copy()
        frozen_jacobian = np.asarray(internal["action_jacobians"], dtype=np.float64)[
            action
        ].copy()
        selected_mean = float(
            np.asarray(internal["action_means"], dtype=np.float64)[action]
        )
        history.contexts.append(context.copy())
        history.actions.append(action)
        history.rewards.append(reward)
        history.frozen_jacobians.append(frozen_jacobian)
        history.parameters.append(theta_active)
        history.means.append(selected_mean)
        played_jacobians.append(frozen_jacobian)
        played_cg_width_squared.append(
            float(np.asarray(internal["cg_width_squared"])[action])
        )

        contexts_array, actions_array, rewards_array, _, _, _ = _history_arrays(
            history,
            context_dimension=model.layout.context_dimension,
            active_dimension=dimension,
        )
        update = deterministic_online_update(
            model,
            theta,
            contexts_array,
            actions_array,
            rewards_array,
            regime=resolved_regime,
            damping=ridge,
            noise_variance=variance,
        )
        next_theta = np.asarray(update.parameters, dtype=np.float64).copy()
        cumulative_path_length += update.step_norm
        cumulative_backbone_path_length += update.backbone_step_norm
        parameter_path.append(next_theta.copy())

        epsilon = float(internal["epsilon_lin"])
        epsilon_sum += epsilon
        epsilon_square_sum += epsilon * epsilon
        schedule_values = policy_schedule.values(
            resolved_regime.name, center, round_number
        )
        alpha_squared = (1.0 + policy_schedule.cg_energy_tolerance) / (
            1.0 - policy_schedule.cg_energy_tolerance
        )
        policy_s_sum += (
            alpha_squared
            * schedule_values["transfer_factor"]
            * schedule_values["omega"] ** 2
        )
        diagnostic_error = min(float(internal["cg_max_error"]), 1.0 - 1.0e-12)
        diagnostic_alpha_squared = (1.0 + diagnostic_error) / (
            1.0 - diagnostic_error
        )
        diagnostic_omega = float(internal["beta_exact"])
        if center == "original":
            diagnostic_omega += float(internal["primitive_psi"])
        diagnostic_s_sum += (
            diagnostic_alpha_squared
            * float(internal["transfer_factor"])
            * diagnostic_omega**2
        )
        gradient_bound_seen = max(
            gradient_bound_seen, float(internal["gradient_bound"])
        )
        all_schedule_checks = all_schedule_checks and bool(
            internal["schedule_checks"]
        )

        terminal_replayed = np.stack(
            [
                model.jacobian(next_theta, old_context, int(old_action))[active]
                for old_context, old_action in zip(
                    contexts_array, actions_array, strict=True
                )
            ],
            axis=0,
        )
        terminal_curvature = CurvatureOperator(
            terminal_replayed, damping=ridge, noise_variance=variance
        ).to_dense()
        curvature_sequence.append(terminal_curvature)
        # NumPy 2.4 on Python 3.14 can emit spurious floating-point warnings
        # inside slogdet's LAPACK gufunc even when the returned SPD logdet is
        # finite.  The shared helper validates the sign and finiteness itself.
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            dynamic = dynamic_logdet_metrics(
                curvature_sequence,
                np.stack(played_jacobians, axis=0),
                noise_variance=variance,
            )
        observable_lambda = float(
            np.sum(
                np.log1p(
                    np.asarray(played_cg_width_squared, dtype=np.float64)
                    / (variance * (1.0 - policy_schedule.cg_energy_tolerance))
                )
            )
        )
        theorem_coefficient = variance + gradient_bound_seen**2 / ridge
        policy_theorem_rhs = float(
            2.0
            * np.sqrt(theorem_coefficient * dynamic.information_complexity * policy_s_sum)
            + 2.0 * epsilon_sum
        )
        diagnostic_theorem_rhs = float(
            2.0
            * np.sqrt(
                theorem_coefficient
                * dynamic.information_complexity
                * diagnostic_s_sum
            )
            + 2.0 * epsilon_sum
        )

        metrics.update(
            {
                "selected_action": action,
                "optimal_action": optimal_action,
                "observed_reward": reward,
                "realized_noise": realized_noise,
                "instantaneous_pseudo_regret": instantaneous_regret,
                "cumulative_pseudo_regret": cumulative_regret,
                "training_objective_after_update": update.objective,
                "training_gradient_norm_after_update": update.gradient_norm,
                "parameter_step_norm": update.step_norm,
                "backbone_step_norm": update.backbone_step_norm,
                "cumulative_parameter_path_length": cumulative_path_length,
                "cumulative_backbone_path_length": cumulative_backbone_path_length,
                "parameter_distance_from_initial": float(np.linalg.norm(next_theta)),
                "backbone_distance_from_initial": float(
                    np.linalg.norm(next_theta[model.backbone_indices])
                ),
                "trust_region_active": update.trust_region_active,
                "posthoc_gradient_bound_seen": gradient_bound_seen,
                "posthoc_Lambda_algorithmic": dynamic.information_complexity,
                "posthoc_endpoint_logdet": dynamic.endpoint_logdeterminant,
                "posthoc_V_variation_charge": dynamic.variation_charge,
                "posthoc_Gamma_dynamic": dynamic.dynamic_potential,
                "posthoc_dynamic_identity_rhs": dynamic.identity_right_hand_side,
                "posthoc_dynamic_identity_residual": dynamic.identity_residual,
                "posthoc_Lambda_cg_observable_bound": observable_lambda,
                "posthoc_policy_S_sum": policy_s_sum,
                "posthoc_exact_diagnostic_S_sum": diagnostic_s_sum,
                "posthoc_theorem_rhs_using_policy_schedule": policy_theorem_rhs,
                "posthoc_theorem_rhs_using_exact_diagnostics": diagnostic_theorem_rhs,
                "posthoc_regret_minus_policy_theorem_rhs": cumulative_regret
                - policy_theorem_rhs,
                "posthoc_all_policy_schedule_checks_hold_through_round": all_schedule_checks,
                "is_exact_matrix_snapshot": round_number in snapshot_set,
            }
        )
        if process is not None:
            peak_host_memory_bytes = max(
                peak_host_memory_bytes, process.memory_info().rss
            )
            metrics.update(
                {
                    "round_runtime_seconds": time.perf_counter() - round_started,
                    "runtime_seconds": time.perf_counter() - run_started,
                    "peak_host_memory_bytes": peak_host_memory_bytes,
                }
            )
        records.append(metrics)
        if round_number in snapshot_set:
            snapshots.append(snapshot)
        theta = next_theta

    return AuditRun(
        seed=int(seed),
        regime=resolved_regime.name,
        center=center,
        records=tuple(records),
        snapshots=tuple(snapshots),
        parameter_path=_readonly(np.stack(parameter_path, axis=0)),
        contexts=_readonly(np.stack(history.contexts, axis=0)),
        actions=_readonly(history.actions, dtype=np.dtype(np.int64)),
        rewards=_readonly(history.rewards),
    )


def run_audit_suite(
    *,
    seed: int,
    rounds: int = 20,
    regimes: Sequence[str] = tuple(DRIFT_REGIMES),
    centers: Sequence[str] = CENTER_VARIANTS,
    **kwargs: Any,
) -> dict[tuple[str, str], AuditRun]:
    """Run every requested regime/center as its own executed policy."""

    results: dict[tuple[str, str], AuditRun] = {}
    for regime in regimes:
        canonical = get_drift_regime(regime).name
        for center in centers:
            results[(canonical, center)] = run_single_audit(
                seed=seed,
                regime=canonical,
                center=center,
                rounds=rounds,
                **kwargs,
            )
    return results


def _runtime_config(
    source: Mapping[str, Any],
    *,
    regime: str,
    center: str,
    rounds: int,
    damping: float,
    schedule: PredeterminedPolicySchedule,
) -> dict[str, Any]:
    config = copy.deepcopy(dict(source))
    resolved_regime = get_drift_regime(regime)
    config["name"] = "nonlinear_audit"
    config["task"] = "small_exact_smooth_nonlinear_bandit"
    config["rounds"] = rounds
    config["action_count"] = ACTION_COUNT
    config["context_dimension"] = CONTEXT_DIMENSION
    config["training_regimes"] = [regime]
    config["model"] = {
        "architecture": "single_hidden_layer_tanh_mlp",
        "hidden_width": HIDDEN_WIDTH,
        "optimizer": (
            "exact_ridge_head"
            if resolved_regime.exact_head_ridge
            else "deterministic_full_batch_gradient"
        ),
        "learning_rate": resolved_regime.learning_rate,
        "updates_per_round": resolved_regime.updates_per_round,
        "trust_region_step_cap": resolved_regime.trust_region_cap,
    }
    config["audit_execution"] = {
        "regime": regime,
        "center": center,
        "damping": damping,
        "numeric_dtype": "float64",
        "exact_dense_replay": True,
        "policy_schedule": schedule.as_dict(),
        "posthoc_diagnostics_are_certificates": False,
    }
    config["provenance"] = {"packages": ["numpy", "psutil"]}
    return config


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the exact small nonlinear audit")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("experiments/configs/nonlinear_drift.yaml"),
    )
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument(
        "--seed-set", choices=("tuning", "evaluation"), default="tuning"
    )
    parser.add_argument("--rounds", type=int)
    parser.add_argument(
        "--regime",
        action="append",
        choices=tuple(DRIFT_REGIMES),
        help="repeat to select regimes; default runs the full ladder",
    )
    parser.add_argument(
        "--center",
        action="append",
        choices=CENTER_VARIANTS,
        help="repeat to select centers; default executes both",
    )
    parser.add_argument("--damping", type=float)
    parser.add_argument("--cg-max-iterations", type=int)
    parser.add_argument("--snapshot-every", type=int, default=1)
    parser.add_argument(
        "--output-root", type=Path, default=Path("experiments/results")
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    resolved = load_config(args.config, profile=args.profile)
    horizon = int(resolved["rounds"] if args.rounds is None else args.rounds)
    _positive_integer(horizon, name="rounds")
    regimes = tuple(DRIFT_REGIMES) if args.regime is None else tuple(args.regime)
    centers = CENTER_VARIANTS if args.center is None else tuple(args.center)
    damping_values = resolved.get("curvature", {}).get("damping", [1.0])
    damping = float(damping_values[0] if args.damping is None else args.damping)
    noise_std = float(resolved.get("noise_std", 0.1))
    configured_budget = resolved.get("curvature", {}).get("cg_max_iterations")
    cg_budget = args.cg_max_iterations
    if cg_budget is None and configured_budget is not None:
        cg_budget = int(configured_budget)
    snapshot_every = _positive_integer(args.snapshot_every, name="snapshot_every")
    snapshot_rounds = list(range(snapshot_every, horizon + 1, snapshot_every))
    snapshot_rounds.append(horizon)
    schedule = PredeterminedPolicySchedule()

    for seed in get_seed_set(resolved, args.seed_set):
        seed_everything(seed, include_optional=False)
        for regime in regimes:
            for center in centers:
                run = run_single_audit(
                    seed=seed,
                    regime=regime,
                    center=center,
                    rounds=horizon,
                    damping=damping,
                    noise_std=noise_std,
                    cg_max_iterations=cg_budget,
                    schedule=schedule,
                    snapshot_rounds=snapshot_rounds,
                    measure_resources=True,
                )
                output = (
                    args.output_root
                    / "nonlinear_audit"
                    / args.profile
                    / args.seed_set
                    / f"seed-{seed}"
                    / run.regime
                    / run.center
                )
                runtime = _runtime_config(
                    resolved,
                    regime=run.regime,
                    center=run.center,
                    rounds=horizon,
                    damping=damping,
                    schedule=schedule,
                )
                with ExperimentLogger(
                    output,
                    runtime,
                    seed,
                    repository=Path(__file__).resolve().parents[1],
                    packages=("numpy", "psutil"),
                    overwrite=args.overwrite,
                ) as logger:
                    for round_index, metrics in enumerate(run.records):
                        logger.log_round(round_index, metrics)
                final = run.records[-1]
                summary_path = output / "summary.jsonl"
                if args.overwrite and summary_path.exists():
                    summary_path.unlink()
                append_jsonl(
                    summary_path,
                    {
                        "event": "nonlinear_audit_summary",
                        "executed_policy": True,
                        "execution_mode": "online_adaptive",
                        "certified_run_claim": False,
                        "posthoc_diagnostics_are_certificates": False,
                        "seed": seed,
                        "rounds": horizon,
                        "regime": run.regime,
                        "center": run.center,
                        "cumulative_pseudo_regret": final["cumulative_pseudo_regret"],
                        "policy_optimism_violation_rate": sum(
                            record["policy_optimism_violation_count"]
                            for record in run.records
                        ) / (horizon * ACTION_COUNT),
                        "E_T": final["posthoc_E_including_round"],
                        "F_T": final["posthoc_F_including_round"],
                        "psi_T": final["posthoc_primitive_psi"],
                        "chi_T": final["posthoc_chi_operator_norm"],
                        "u_T": final["posthoc_transfer_factor_one_plus_chi_squared"],
                        "Lambda_alg_T": final["posthoc_Lambda_algorithmic"],
                        "V_alg_T": final["posthoc_V_variation_charge"],
                        "Gamma_dynamic_T": final["posthoc_Gamma_dynamic"],
                        "theorem_rhs_policy_schedule": final[
                            "posthoc_theorem_rhs_using_policy_schedule"
                        ],
                        "runtime_seconds": final["runtime_seconds"],
                        "peak_host_memory_bytes": final[
                            "peak_host_memory_bytes"
                        ],
                        "all_policy_schedule_checks_hold": final[
                            "posthoc_all_policy_schedule_checks_hold_through_round"
                        ],
                    },
                )
                print(
                    f"seed={seed} regime={run.regime} center={run.center} "
                    f"regret={final['cumulative_pseudo_regret']:.6g} "
                    f"Lambda={final['posthoc_Lambda_algorithmic']:.6g} "
                    f"output={output}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = [
    "AuditRun",
    "AuditSnapshot",
    "CENTER_VARIANTS",
    "DRIFT_REGIMES",
    "DriftRegime",
    "LinearizedRidgeFit",
    "PredeterminedPolicySchedule",
    "TrainingUpdate",
    "active_parameter_indices",
    "corrected_centers",
    "deterministic_online_update",
    "exact_ridge_head_update",
    "frozen_linearized_ridge",
    "get_drift_regime",
    "run_audit_suite",
    "run_single_audit",
    "squared_loss_and_gradient",
]
