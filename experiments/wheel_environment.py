"""Canonical five-action Wheel contextual-bandit environment.

The protocol follows the Wheel benchmark introduced by Riquelme et al. (2018):
contexts are uniform by area on the two-dimensional unit disk, action zero is a
safe arm, and exactly one of four risky arms has a large mean outside a radius
``delta``.  The quadrant map is fixed and explicit so independent
implementations can reproduce the same oracle labels.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Any, Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .logging_utils import canonical_json, derive_seed


FloatArray = NDArray[np.float64]
ACTION_COUNT = 5
SAFE_ACTION = 0
RISKY_ACTIONS = (1, 2, 3, 4)
QUADRANT_TO_ACTION = {
    "northeast": 1,
    "northwest": 2,
    "southwest": 3,
    "southeast": 4,
}


def _finite_float(value: Any, *, name: str, positive: bool = False) -> float:
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        qualifier = "positive " if positive else ""
        raise ValueError(f"{name} must be a finite {qualifier}number")
    return result


def _context(value: ArrayLike) -> FloatArray:
    context = np.asarray(value, dtype=np.float64)
    if context.shape != (2,) or not np.all(np.isfinite(context)):
        raise ValueError("context must be a finite two-dimensional vector")
    if float(context @ context) > 1.0 + 64.0 * np.finfo(np.float64).eps:
        raise ValueError("context must lie in the closed unit disk")
    return context


@dataclass(frozen=True)
class WheelSpecification:
    """Numerical definition of one Wheel benchmark instance."""

    delta: float = 0.95
    safe_mean: float = 1.2
    safe_std: float = 0.05
    risky_mean: float = 1.0
    risky_std: float = 0.05
    high_mean: float = 50.0
    high_std: float = 0.01

    def __post_init__(self) -> None:
        delta = _finite_float(self.delta, name="delta", positive=True)
        if delta >= 1.0:
            raise ValueError("delta must lie strictly between zero and one")
        for name in ("safe_mean", "risky_mean", "high_mean"):
            _finite_float(getattr(self, name), name=name)
        for name in ("safe_std", "risky_std", "high_std"):
            _finite_float(getattr(self, name), name=name, positive=True)
        if not self.high_mean > self.safe_mean > self.risky_mean:
            raise ValueError("means must satisfy high_mean > safe_mean > risky_mean")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "WheelSpecification":
        return cls(
            delta=float(value["delta"]),
            safe_mean=float(value["safe_mean"]),
            safe_std=float(value["safe_std"]),
            risky_mean=float(value["risky_mean"]),
            risky_std=float(value["risky_std"]),
            high_mean=float(value["high_mean"]),
            high_std=float(value["high_std"]),
        )

    @property
    def inner_disk_probability(self) -> float:
        return self.delta * self.delta

    def quadrant_action(self, context: ArrayLike) -> int:
        """Return the risky action assigned to a context's closed-open quadrant.

        The axes have probability zero under the benchmark distribution.  For
        deterministic tests, nonnegative coordinates are assigned north/east:
        NE -> 1, NW -> 2, SW -> 3, and SE -> 4.
        """

        x, y = _context(context)
        if x >= 0.0 and y >= 0.0:
            return QUADRANT_TO_ACTION["northeast"]
        if x < 0.0 <= y:
            return QUADRANT_TO_ACTION["northwest"]
        if x < 0.0 and y < 0.0:
            return QUADRANT_TO_ACTION["southwest"]
        return QUADRANT_TO_ACTION["southeast"]

    def is_outer(self, context: ArrayLike) -> bool:
        x = _context(context)
        return float(x @ x) > self.delta * self.delta

    def mean_rewards(self, context: ArrayLike) -> FloatArray:
        x = _context(context)
        means = np.full(ACTION_COUNT, self.risky_mean, dtype=np.float64)
        means[SAFE_ACTION] = self.safe_mean
        if float(x @ x) > self.delta * self.delta:
            means[self.quadrant_action(x)] = self.high_mean
        means.setflags(write=False)
        return means

    def reward_stds(self, context: ArrayLike) -> FloatArray:
        x = _context(context)
        stds = np.full(ACTION_COUNT, self.risky_std, dtype=np.float64)
        stds[SAFE_ACTION] = self.safe_std
        if float(x @ x) > self.delta * self.delta:
            stds[self.quadrant_action(x)] = self.high_std
        stds.setflags(write=False)
        return stds

    def optimal_action(self, context: ArrayLike) -> int:
        x = _context(context)
        return self.quadrant_action(x) if self.is_outer(x) else SAFE_ACTION

    def pseudo_regret(self, context: ArrayLike, action: int) -> float:
        if isinstance(action, (bool, np.bool_)) or not isinstance(
            action, (int, np.integer)
        ):
            raise TypeError("action must be an integer")
        action_index = int(action)
        if not 0 <= action_index < ACTION_COUNT:
            raise ValueError("action lies outside the five-action set")
        means = self.mean_rewards(context)
        return float(means[self.optimal_action(context)] - means[action_index])

    def expected_control_regret(self, method: str) -> float:
        """Return analytic one-round pseudo-regret for benchmark controls."""

        outer_probability = 1.0 - self.inner_disk_probability
        if method == "oracle":
            return 0.0
        if method == "safe":
            return outer_probability * (self.high_mean - self.safe_mean)
        if method == "random":
            inner = (
                (ACTION_COUNT - 1)
                * (self.safe_mean - self.risky_mean)
                / ACTION_COUNT
            )
            outer = (
                (self.high_mean - self.safe_mean)
                + (ACTION_COUNT - 2) * (self.high_mean - self.risky_mean)
            ) / ACTION_COUNT
            return self.inner_disk_probability * inner + outer_probability * outer
        raise ValueError("method must be one of random, safe, or oracle")


@dataclass(frozen=True)
class WheelStream:
    contexts: FloatArray
    standard_normals: FloatArray
    stream_sha256: str


@dataclass(frozen=True)
class WheelOutcome:
    reward: float
    pseudo_regret: float
    optimal_action: int
    chosen_mean: float
    chosen_std: float


class PostActionWheelOracle:
    """Reveal reward and oracle diagnostics only after an action is committed."""

    def __init__(self, specification: WheelSpecification) -> None:
        self.__specification = specification

    def observe_after_action(
        self, context: ArrayLike, action: int, standard_normal: float
    ) -> WheelOutcome:
        if isinstance(action, (bool, np.bool_)) or not isinstance(
            action, (int, np.integer)
        ):
            raise TypeError("a committed integer action is required")
        action_index = int(action)
        if not 0 <= action_index < ACTION_COUNT:
            raise ValueError("committed action lies outside the action set")
        noise = _finite_float(standard_normal, name="standard_normal")
        means = self.__specification.mean_rewards(context)
        stds = self.__specification.reward_stds(context)
        optimum = self.__specification.optimal_action(context)
        return WheelOutcome(
            reward=float(means[action_index] + stds[action_index] * noise),
            pseudo_regret=float(means[optimum] - means[action_index]),
            optimal_action=optimum,
            chosen_mean=float(means[action_index]),
            chosen_std=float(stds[action_index]),
        )


def _array_digest(*arrays: NDArray[np.generic]) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(canonical_json(list(contiguous.shape)).encode("ascii"))
        digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def generate_wheel_stream(seed: int, rounds: int) -> WheelStream:
    """Generate common contexts/noise with NumPy PCG64 and stable seed derivation."""

    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, (int, np.integer)):
        raise TypeError("seed must be an integer")
    if int(seed) < 0:
        raise ValueError("seed must be nonnegative")
    if isinstance(rounds, (bool, np.bool_)) or not isinstance(
        rounds, (int, np.integer)
    ) or int(rounds) <= 0:
        raise ValueError("rounds must be a positive integer")
    rounds = int(rounds)
    rng = np.random.Generator(
        np.random.PCG64(derive_seed(int(seed), "wheel_benchmark", "stream"))
    )
    radii = np.sqrt(rng.random(rounds))
    angles = 2.0 * np.pi * rng.random(rounds)
    contexts = np.column_stack((radii * np.cos(angles), radii * np.sin(angles)))
    contexts = np.asarray(contexts, dtype=np.float64)
    standard_normals = np.asarray(
        rng.standard_normal((rounds, ACTION_COUNT)), dtype=np.float64
    )
    digest = _array_digest(contexts, standard_normals)
    contexts.setflags(write=False)
    standard_normals.setflags(write=False)
    return WheelStream(contexts, standard_normals, digest)


__all__ = [
    "ACTION_COUNT",
    "PostActionWheelOracle",
    "QUADRANT_TO_ACTION",
    "RISKY_ACTIONS",
    "SAFE_ACTION",
    "WheelOutcome",
    "WheelSpecification",
    "WheelStream",
    "generate_wheel_stream",
]
