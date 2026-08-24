"""Dynamic feature map for real-context finite-action benchmarks."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


def _positive_int(value: int, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


@dataclass(frozen=True)
class FeatureMapSpec:
    context_dimension: int
    action_count: int
    feature_bound: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "context_dimension",
            _positive_int(self.context_dimension, name="context_dimension"),
        )
        object.__setattr__(
            self,
            "action_count",
            _positive_int(self.action_count, name="action_count"),
        )
        bound = float(self.feature_bound)
        if not np.isfinite(bound) or bound <= 0.0:
            raise ValueError("feature_bound must be finite and positive")
        object.__setattr__(self, "feature_bound", bound)

    @property
    def feature_dimension(self) -> int:
        p = self.context_dimension
        k = self.action_count
        return p + k + p * k

    def feature(self, context: ArrayLike, action: int) -> FloatArray:
        return normalized_feature(
            context,
            action,
            action_count=self.action_count,
            feature_bound=self.feature_bound,
        )

    def all_action_features(self, context: ArrayLike) -> FloatArray:
        return action_features(
            context,
            action_count=self.action_count,
            feature_bound=self.feature_bound,
        )


def _context_vector(context: ArrayLike) -> FloatArray:
    vector = np.asarray(context, dtype=np.float64)
    if vector.ndim != 1 or vector.size == 0:
        raise ValueError("context must be a nonempty vector")
    if not np.all(np.isfinite(vector)):
        raise ValueError("context contains a nonfinite value")
    norm = float(np.linalg.norm(vector))
    if norm > 1.0 + 64.0 * np.finfo(np.float64).eps:
        raise ValueError(f"context norm exceeds one: {norm}")
    return vector


def normalized_feature(
    context: ArrayLike,
    action: int,
    *,
    action_count: int,
    feature_bound: float = 1.0,
) -> FloatArray:
    """Return normalized ``[x, e_a, np.kron(x, e_a)]`` in that order."""

    x = _context_vector(context)
    actions = _positive_int(action_count, name="action_count")
    if isinstance(action, (bool, np.bool_)) or not isinstance(
        action, (int, np.integer)
    ):
        raise TypeError("action must be an integer")
    action = int(action)
    if not 0 <= action < actions:
        raise ValueError(f"action must lie in [0, {actions})")
    bound = float(feature_bound)
    if not np.isfinite(bound) or bound <= 0.0:
        raise ValueError("feature_bound must be finite and positive")
    one_hot = np.zeros(actions, dtype=np.float64)
    one_hot[action] = 1.0
    raw = np.concatenate((x, one_hot, np.kron(x, one_hot)))
    raw_norm = float(np.linalg.norm(raw))
    if not np.isfinite(raw_norm):
        raise FloatingPointError("raw feature norm is nonfinite")
    # This is raw / max(1, ||raw||) for the protocol's feature_bound=1.
    denominator = max(bound, raw_norm)
    feature = np.asarray(bound * raw / denominator, dtype=np.float64)
    if float(np.linalg.norm(feature)) > bound + 64.0 * np.finfo(np.float64).eps:
        raise FloatingPointError("feature normalization failed")
    return feature


def action_features(
    context: ArrayLike,
    *,
    action_count: int,
    feature_bound: float = 1.0,
) -> FloatArray:
    """Enumerate all actions in increasing order with a stable tie convention."""

    x = _context_vector(context)
    actions = _positive_int(action_count, name="action_count")
    return np.stack(
        [
            normalized_feature(
                x, action, action_count=actions, feature_bound=feature_bound
            )
            for action in range(actions)
        ],
        axis=0,
    )


__all__ = ["FeatureMapSpec", "action_features", "normalized_feature"]
