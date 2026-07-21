"""Bounded, context-dependent linear bandit used by the linear audit.

The benchmark deliberately keeps the statistical model small enough that every
matrix appearing in the audit can also be materialized exactly.  Contexts have
unit Euclidean norm and the feature ordering is exactly

``[x, one_hot(action), kron(x, one_hot(action))]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Final

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]

CONTEXT_DIMENSION: Final = 8
ACTION_COUNT: Final = 5
FEATURE_DIMENSION: Final = (
    CONTEXT_DIMENSION + ACTION_COUNT + CONTEXT_DIMENSION * ACTION_COUNT
)


def _as_vector(value: ArrayLike, length: int, *, name: str) -> FloatArray:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (length,):
        raise ValueError(f"{name} must have shape ({length},), got {array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def linear_feature(context: ArrayLike, action: int) -> FloatArray:
    """Return ``[x, e_a, x kron e_a]`` as a float64 vector."""

    x = _as_vector(context, CONTEXT_DIMENSION, name="context")
    if isinstance(action, (bool, np.bool_)) or not isinstance(
        action, (int, np.integer)
    ):
        raise TypeError("action must be an integer")
    action = int(action)
    if not 0 <= action < ACTION_COUNT:
        raise ValueError(f"action must be in [0, {ACTION_COUNT})")
    one_hot = np.zeros(ACTION_COUNT, dtype=np.float64)
    one_hot[action] = 1.0
    return np.concatenate((x, one_hot, np.kron(x, one_hot))).astype(
        np.float64, copy=False
    )


def action_features(context: ArrayLike) -> FloatArray:
    """Enumerate the feature of every action in fixed increasing order."""

    x = _as_vector(context, CONTEXT_DIMENSION, name="context")
    return np.stack(
        [linear_feature(x, action) for action in range(ACTION_COUNT)], axis=0
    ).astype(np.float64, copy=False)


def default_theta_star() -> FloatArray:
    """Return a fixed parameter whose optimal arm genuinely depends on context."""

    shared = np.array(
        [0.15, -0.10, 0.08, -0.05, 0.03, -0.02, 0.01, 0.00],
        dtype=np.float64,
    )
    intercepts = np.array([0.025, 0.0125, 0.0, -0.0125, -0.025], dtype=np.float64)
    interactions = np.array(
        [
            [0.90, -0.90, 0.00, 0.00, 0.10],
            [0.10, 0.10, 0.90, -0.90, 0.00],
            [0.05, -0.05, 0.05, -0.05, 0.90],
            [0.03, 0.03, -0.03, -0.03, 0.05],
            [0.02, -0.02, 0.02, -0.02, -0.05],
            [0.01, 0.01, -0.01, -0.01, 0.03],
            [0.00, 0.02, 0.00, -0.02, -0.03],
            [-0.01, 0.00, 0.01, 0.00, 0.02],
        ],
        dtype=np.float64,
    )
    # np.kron(x, e_a) contracts with a row-major p-by-K interaction matrix.
    return np.concatenate((shared, intercepts, interactions.reshape(-1))).astype(
        np.float64, copy=False
    )


@dataclass(frozen=True)
class LinearEnvironmentSpec:
    """Validated environment parameters for the fixed benchmark dimensions."""

    noise_std: float = 0.25
    theta_star: ArrayLike | None = None

    def resolved_theta(self) -> FloatArray:
        theta = default_theta_star() if self.theta_star is None else self.theta_star
        return _as_vector(theta, FEATURE_DIMENSION, name="theta_star").copy()


class LinearBanditEnvironment:
    """Normalized-Rademacher contextual linear bandit with Gaussian noise."""

    context_dimension = CONTEXT_DIMENSION
    action_count = ACTION_COUNT
    feature_dimension = FEATURE_DIMENSION

    def __init__(
        self,
        seed: int,
        *,
        noise_std: float = 0.25,
        theta_star: ArrayLike | None = None,
    ) -> None:
        if isinstance(seed, (bool, np.bool_)) or not isinstance(
            seed, (int, np.integer)
        ):
            raise TypeError("seed must be an integer")
        if int(seed) < 0:
            raise ValueError("seed must be nonnegative")
        noise_std = float(noise_std)
        if not np.isfinite(noise_std) or noise_std <= 0.0:
            raise ValueError("noise_std must be finite and positive")

        streams = np.random.SeedSequence(int(seed)).spawn(2)
        self._context_rng = np.random.default_rng(streams[0])
        self._noise_rng = np.random.default_rng(streams[1])
        self.noise_std = noise_std
        self._theta_star = (
            default_theta_star()
            if theta_star is None
            else _as_vector(theta_star, FEATURE_DIMENSION, name="theta_star").copy()
        )
        self._theta_star.setflags(write=False)

    @property
    def theta_star(self) -> FloatArray:
        return self._theta_star

    @property
    def theta_norm(self) -> float:
        return float(np.linalg.norm(self._theta_star))

    @property
    def feature_norm(self) -> float:
        # ||x|| = ||e_a|| = ||x kron e_a|| = 1.
        return float(np.sqrt(3.0))

    def draw_context(self) -> FloatArray:
        signs = self._context_rng.integers(
            0, 2, size=CONTEXT_DIMENSION, dtype=np.int64
        )
        context = (2.0 * signs.astype(np.float64) - 1.0) / np.sqrt(
            float(CONTEXT_DIMENSION)
        )
        return np.asarray(context, dtype=np.float64)

    def draw_noise(self) -> float:
        return float(self._noise_rng.normal(loc=0.0, scale=self.noise_std))

    def features(self, context: ArrayLike) -> FloatArray:
        return action_features(context)

    def mean_rewards(self, context: ArrayLike) -> FloatArray:
        return np.asarray(self.features(context) @ self._theta_star, dtype=np.float64)

    def optimal_action(self, context: ArrayLike) -> int:
        # np.argmax provides the fixed lowest-index tie break used by the policy.
        return int(np.argmax(self.mean_rewards(context)))

    def reward(
        self, context: ArrayLike, action: int, *, noise: float | None = None
    ) -> tuple[float, float]:
        feature = linear_feature(context, action)
        realized_noise = self.draw_noise() if noise is None else float(noise)
        if not np.isfinite(realized_noise):
            raise ValueError("noise must be finite")
        mean = float(feature @ self._theta_star)
        return mean + realized_noise, realized_noise


def enumerate_rademacher_contexts() -> FloatArray:
    """Return all 2**8 normalized contexts, useful for exact audit tests."""

    scale = 1.0 / np.sqrt(float(CONTEXT_DIMENSION))
    return np.asarray(list(product((-scale, scale), repeat=CONTEXT_DIMENSION)), dtype=np.float64)


# Concise aliases for callers and older local notebooks.
build_feature = linear_feature
build_action_features = action_features
ContextualLinearBandit = LinearBanditEnvironment


__all__ = [
    "ACTION_COUNT",
    "CONTEXT_DIMENSION",
    "FEATURE_DIMENSION",
    "ContextualLinearBandit",
    "LinearBanditEnvironment",
    "LinearEnvironmentSpec",
    "action_features",
    "build_action_features",
    "build_feature",
    "default_theta_star",
    "enumerate_rademacher_contexts",
    "linear_feature",
]
