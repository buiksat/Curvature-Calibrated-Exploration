"""Constructive two-action witness for off-diagonal uncertainty geometry.

The deterministic proposition is analytic.  Floating-point simulations in this
module are execution checks and noisy extensions; they are not numerical
certificates for the proposition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


PolicyName = Literal[
    "exact_full",
    "full_cg",
    "diagonal_raw",
    "diagonal_uniform_transfer",
    "diagonal_actionwise_reference",
    "greedy",
]

POLICIES: tuple[PolicyName, ...] = (
    "exact_full",
    "full_cg",
    "diagonal_raw",
    "diagonal_uniform_transfer",
    "diagonal_actionwise_reference",
    "greedy",
)


@dataclass(frozen=True)
class WitnessProblem:
    damping: float = 1.0
    epsilon: float = 0.1
    delta: float = 1.0
    bonus: float = 1.1
    angle_degrees: float = 45.0

    def __post_init__(self) -> None:
        values = (self.damping, self.epsilon, self.delta, self.bonus)
        if not all(np.isfinite(value) for value in values):
            raise ValueError("witness parameters must be finite")
        if self.damping <= 0.0:
            raise ValueError("damping must be positive")
        if not 0.0 < self.epsilon < self.delta:
            raise ValueError("require 0 < epsilon < delta")
        if self.bonus < 0.0:
            raise ValueError("bonus must be nonnegative")
        if not np.isfinite(self.angle_degrees):
            raise ValueError("angle_degrees must be finite")

    @property
    def actions(self) -> np.ndarray:
        angle = np.deg2rad(self.angle_degrees)
        u = np.asarray([np.cos(angle), np.sin(angle)], dtype=np.float64)
        v = np.asarray([np.sin(angle), -np.cos(angle)], dtype=np.float64)
        return np.vstack((u, v))

    @property
    def theta_star(self) -> np.ndarray:
        actions = self.actions
        return self.epsilon * actions[0] + self.delta * actions[1]

    @property
    def means(self) -> np.ndarray:
        return self.actions @ self.theta_star

    @property
    def gap(self) -> float:
        return self.delta - self.epsilon


@dataclass(frozen=True)
class WitnessInterval:
    confidence_lower: float
    immediate_switch_lower: float
    no_return_upper: float
    nonempty: bool


def one_pull_witness_interval(problem: WitnessProblem) -> WitnessInterval:
    """Return the analytic interval giving the path ``u,v,v,...``.

    The lower endpoint enforces both noiseless ridge confidence and a strict
    switch after the first pull.  The upper endpoint prevents a return to u.
    """

    ridge = problem.damping
    epsilon = problem.epsilon
    delta = problem.delta
    confidence = float(np.sqrt(ridge * (epsilon * epsilon + delta * delta)))
    switch = float(
        epsilon * np.sqrt(ridge) * (1.0 + np.sqrt(ridge / (ridge + 1.0)))
    )
    upper = float((delta - epsilon / (ridge + 1.0)) * np.sqrt(ridge + 1.0))
    lower = max(confidence, switch)
    return WitnessInterval(
        confidence_lower=confidence,
        immediate_switch_lower=switch,
        no_return_upper=upper,
        nonempty=lower < upper,
    )


def full_first_hit_count(problem: WitnessProblem) -> int | None:
    """Number of initial u pulls before full Gram strictly selects v."""

    ridge = problem.damping
    epsilon = problem.epsilon
    bonus = problem.bonus
    if bonus <= epsilon * np.sqrt(ridge):
        return None
    c = bonus / (epsilon * np.sqrt(ridge)) - 1.0
    count = int(np.floor(ridge * (c ** -2 - 1.0)) + 1)
    return max(1, count)


def uniform_diagonal_transfer_factor(
    full_gram: np.ndarray, diagonal_gram: np.ndarray, *, damping: float
) -> float:
    """Analytic factor from ``D <= max_i D_ii I <= kappa C``.

    This bound does not call a generalized eigensolver.  It is valid whenever
    ``C >= damping I`` and ``D`` is diagonal PSD.
    """

    full = np.asarray(full_gram, dtype=np.float64)
    diagonal = np.asarray(diagonal_gram, dtype=np.float64)
    if full.shape != (2, 2) or diagonal.shape != (2, 2):
        raise ValueError("witness Gram matrices must be 2 by 2")
    if damping <= 0.0:
        raise ValueError("damping must be positive")
    if not np.allclose(diagonal, np.diag(np.diag(diagonal)), atol=1e-14):
        raise ValueError("diagonal_gram must be diagonal")
    return float(np.max(np.diag(diagonal)) / damping)


@dataclass(frozen=True)
class WitnessRun:
    policy: PolicyName
    actions: np.ndarray
    pseudo_regret: np.ndarray
    cumulative_regret: np.ndarray
    records: tuple[dict[str, object], ...]


def _full_widths(full_gram: np.ndarray, actions: np.ndarray) -> np.ndarray:
    a = float(full_gram[0, 0])
    b = float(full_gram[0, 1])
    c = float(full_gram[1, 1])
    determinant = a * c - b * b
    if determinant <= 0.0 or not np.isfinite(determinant):
        raise FloatingPointError("full Gram is not positive definite")
    values = (
        c * actions[:, 0] ** 2
        - 2.0 * b * actions[:, 0] * actions[:, 1]
        + a * actions[:, 1] ** 2
    ) / determinant
    if np.any(values < -1e-13):
        raise FloatingPointError("a full width squared is negative")
    return np.sqrt(np.maximum(values, 0.0))


def _cg_widths(full_gram: np.ndarray, actions: np.ndarray) -> tuple[np.ndarray, int, float]:
    """Zero-start scalar CG with an original-system residual check."""

    widths: list[float] = []
    total_iterations = 0
    largest_relative_residual = 0.0
    for action in actions:
        solution = np.zeros(2, dtype=np.float64)
        residual = action.copy()
        direction = residual.copy()
        residual_squared = float(residual @ residual)
        denominator = max(float(np.linalg.norm(action)), np.finfo(np.float64).tiny)
        converged = False
        iterations = 0
        for iterations in (1, 2):
            operator_direction = full_gram @ direction
            curvature = float(direction @ operator_direction)
            if curvature <= 0.0:
                raise FloatingPointError("CG encountered nonpositive curvature")
            step = residual_squared / curvature
            solution += step * direction
            residual -= step * operator_direction
            new_residual_squared = float(residual @ residual)
            if np.sqrt(new_residual_squared) <= 1e-13 * denominator:
                converged = True
                break
            direction = residual + (new_residual_squared / residual_squared) * direction
            residual_squared = new_residual_squared
        if not converged:
            raise FloatingPointError("two-dimensional CG failed its residual tolerance")
        width_squared = float(action @ solution)
        if width_squared < 0.0:
            raise FloatingPointError("CG returned a negative width squared")
        widths.append(float(np.sqrt(width_squared)))
        total_iterations += iterations
        largest_relative_residual = max(
            largest_relative_residual,
            float(np.linalg.norm(full_gram @ solution - action) / denominator),
        )
    return np.asarray(widths), total_iterations, largest_relative_residual


def run_witness_policy(
    problem: WitnessProblem,
    *,
    policy: PolicyName,
    rounds: int,
    seed: int,
    noise_std: float = 0.0,
    record_every_round: bool = False,
    checkpoints: tuple[int, ...] = (),
) -> WitnessRun:
    """Execute one online policy with paired potential-outcome noise."""

    if policy not in POLICIES:
        raise ValueError(f"unknown witness policy {policy!r}")
    if rounds <= 0:
        raise ValueError("rounds must be positive")
    if noise_std < 0.0 or not np.isfinite(noise_std):
        raise ValueError("noise_std must be finite and nonnegative")
    if any(checkpoint <= 0 or checkpoint > rounds for checkpoint in checkpoints):
        raise ValueError("checkpoints must lie in [1, rounds]")
    rng = np.random.default_rng(seed)
    potential_noise = rng.normal(scale=noise_std, size=(rounds, 2))
    actions = problem.actions
    theta_star = problem.theta_star
    means = problem.means
    ridge = problem.damping
    full_gram = ridge * np.eye(2, dtype=np.float64)
    response_sum = np.zeros(2, dtype=np.float64)
    selected = np.empty(rounds, dtype=np.int64)
    regrets = np.empty(rounds, dtype=np.float64)
    cumulative = 0.0
    records: list[dict[str, object]] = []
    checkpoint_set = set(checkpoints)

    for index in range(rounds):
        a = float(full_gram[0, 0])
        b = float(full_gram[0, 1])
        c = float(full_gram[1, 1])
        determinant = a * c - b * b
        theta_hat = np.asarray(
            [
                (c * response_sum[0] - b * response_sum[1]) / determinant,
                (a * response_sum[1] - b * response_sum[0]) / determinant,
            ],
            dtype=np.float64,
        )
        full_widths = _full_widths(full_gram, actions)
        diagonal_gram = np.diag(np.diag(full_gram))
        diagonal_widths = np.sqrt(
            np.einsum("ij,ij->i", actions, actions / np.diag(diagonal_gram))
        )
        transfer_factor = uniform_diagonal_transfer_factor(
            full_gram, diagonal_gram, damping=ridge
        )
        cg_iterations = 0
        cg_relative_residual = 0.0
        if policy == "exact_full":
            policy_widths = full_widths
        elif policy == "full_cg":
            policy_widths, cg_iterations, cg_relative_residual = _cg_widths(
                full_gram, actions
            )
        elif policy == "diagonal_raw":
            policy_widths = diagonal_widths
        elif policy == "diagonal_uniform_transfer":
            policy_widths = np.sqrt(transfer_factor) * diagonal_widths
        elif policy == "diagonal_actionwise_reference":
            # Dense pre-action reference factors reproduce the full widths.
            action_factors = full_widths**2 / diagonal_widths**2
            policy_widths = np.sqrt(action_factors) * diagonal_widths
        else:
            policy_widths = np.zeros(2, dtype=np.float64)

        centers = actions @ theta_hat
        scores = centers + problem.bonus * policy_widths
        chosen = int(np.argmax(scores))
        reward = float(means[chosen] + potential_noise[index, chosen])
        gap = float(problem.delta - means[chosen])
        cumulative += gap
        selected[index] = chosen
        regrets[index] = gap
        action = actions[chosen]
        full_gram = full_gram + np.outer(action, action)
        response_sum = response_sum + action * reward

        round_number = index + 1
        if record_every_round or round_number in checkpoint_set:
            transfer_slack = float(
                np.min(np.linalg.eigvalsh(transfer_factor * (full_gram - np.outer(action, action)) - diagonal_gram))
            )
            confidence_slack = problem.bonus * policy_widths - np.abs(
                actions @ (theta_star - theta_hat)
            )
            records.append(
                {
                    "round": round_number,
                    "policy": policy,
                    "selected_action": chosen,
                    "instantaneous_pseudo_regret": gap,
                    "cumulative_pseudo_regret": cumulative,
                    "centers": centers.tolist(),
                    "scores": scores.tolist(),
                    "policy_widths": policy_widths.tolist(),
                    "full_widths": full_widths.tolist(),
                    "diagonal_widths": diagonal_widths.tolist(),
                    "uniform_transfer_factor": transfer_factor,
                    "uniform_transfer_min_eigenvalue_audit": transfer_slack,
                    "confidence_slacks": confidence_slack.tolist(),
                    "cg_iterations_total": cg_iterations,
                    "cg_max_relative_residual": cg_relative_residual,
                }
            )

    return WitnessRun(
        policy=policy,
        actions=selected,
        pseudo_regret=regrets,
        cumulative_regret=np.cumsum(regrets),
        records=tuple(records),
    )


__all__ = [
    "POLICIES",
    "PolicyName",
    "WitnessInterval",
    "WitnessProblem",
    "WitnessRun",
    "full_first_hit_count",
    "one_pull_witness_interval",
    "run_witness_policy",
    "uniform_diagonal_transfer_factor",
]
