"""Dimension-agnostic scaled-tanh learner family."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]


def _validated_model_inputs(
    theta: ArrayLike, features: ArrayLike, width: float
) -> tuple[FloatArray, FloatArray, float, bool]:
    parameters = np.asarray(theta, dtype=np.float64)
    design = np.asarray(features, dtype=np.float64)
    if parameters.ndim != 1 or parameters.size == 0:
        raise ValueError("theta must be a nonempty vector")
    if design.ndim not in (1, 2) or design.shape[-1] != parameters.size:
        raise ValueError(
            f"features must end in dimension {parameters.size}, got {design.shape}"
        )
    if not np.all(np.isfinite(parameters)) or not np.all(np.isfinite(design)):
        raise ValueError("theta and features must contain only finite values")
    width = float(width)
    if not np.isfinite(width) or width <= 0.0:
        raise ValueError("width must be finite and positive")
    return parameters, design, math.sqrt(width), design.ndim == 1


def scaled_tanh_mean(
    theta: ArrayLike, features: ArrayLike, width: float
) -> float | FloatArray:
    parameters, design, scale, single = _validated_model_inputs(theta, features, width)
    result = scale * np.tanh((design @ parameters) / scale)
    return float(result) if single else np.asarray(result, dtype=np.float64)


def scaled_tanh_gradient(
    theta: ArrayLike, features: ArrayLike, width: float
) -> FloatArray:
    parameters, design, scale, single = _validated_model_inputs(theta, features, width)
    tangent = np.tanh((design @ parameters) / scale)
    multiplier = 1.0 - tangent * tangent
    if single:
        return np.asarray(multiplier * design, dtype=np.float64)
    return np.asarray(multiplier[:, np.newaxis] * design, dtype=np.float64)


__all__ = ["scaled_tanh_gradient", "scaled_tanh_mean"]
