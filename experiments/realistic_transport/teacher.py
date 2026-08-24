"""Development-only realizable teacher and controlled misspecification."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .data import canonical_array_digest, canonical_json
from .features import FeatureMapSpec
from .model import scaled_tanh_mean
from .preprocessing import index_digest


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


class TeacherConstructionError(RuntimeError):
    """Raised when the development-only teacher construction is degenerate."""


def _readonly(array: np.ndarray) -> np.ndarray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class RidgeTeacher:
    """A multiclass ridge teacher embedded in the benchmark feature map."""

    theta: FloatArray
    coefficients: FloatArray
    intercepts: FloatArray
    ridge: float
    theta_radius: float
    scale_factor: float
    unscaled_theta_norm: float
    development_index_digest: str
    feature_map: FeatureMapSpec

    def __post_init__(self) -> None:
        theta = np.asarray(self.theta, dtype=np.float64)
        coefficients = np.asarray(self.coefficients, dtype=np.float64)
        intercepts = np.asarray(self.intercepts, dtype=np.float64)
        p = self.feature_map.context_dimension
        k = self.feature_map.action_count
        if theta.shape != (self.feature_map.feature_dimension,):
            raise ValueError("teacher theta has the wrong feature dimension")
        if coefficients.shape != (p, k) or intercepts.shape != (k,):
            raise ValueError("teacher ridge coefficients have the wrong shape")
        if not all(
            np.all(np.isfinite(value)) for value in (theta, coefficients, intercepts)
        ):
            raise ValueError("teacher contains a nonfinite value")
        if not np.isfinite(self.ridge) or self.ridge <= 0.0:
            raise ValueError("teacher ridge must be finite and positive")
        if not np.isfinite(self.theta_radius) or self.theta_radius <= 0.0:
            raise ValueError("theta_radius must be finite and positive")
        if not np.isfinite(self.scale_factor) or self.scale_factor <= 0.0:
            raise ValueError("teacher scale_factor must be finite and positive")
        if not np.isfinite(self.unscaled_theta_norm) or self.unscaled_theta_norm <= 0.0:
            raise ValueError("unscaled_theta_norm must be finite and positive")
        if not np.isclose(
            np.linalg.norm(theta), self.theta_radius, rtol=2e-13, atol=2e-14
        ):
            raise ValueError("teacher theta does not have the declared radius")
        object.__setattr__(self, "theta", _readonly(theta.copy()))
        object.__setattr__(self, "coefficients", _readonly(coefficients.copy()))
        object.__setattr__(self, "intercepts", _readonly(intercepts.copy()))

    @property
    def digest(self) -> str:
        array_digest = canonical_array_digest(
            {
                "coefficients": self.coefficients,
                "intercepts": self.intercepts,
                "theta": self.theta,
            }
        )
        payload = canonical_json(
            {
                "array_digest": array_digest,
                "development_index_digest": self.development_index_digest,
                "feature_dimension": self.feature_map.feature_dimension,
                "ridge": self.ridge,
                "scale_factor": self.scale_factor,
                "schema": "realistic-transport-ridge-teacher-v1",
                "theta_radius": self.theta_radius,
                "unscaled_theta_norm": self.unscaled_theta_norm,
            }
        ).encode("ascii")
        return hashlib.sha256(payload).hexdigest()

    @property
    def theta_star(self) -> FloatArray:
        return self.theta

    def action_means(self, context: ArrayLike, *, width: float) -> FloatArray:
        features = self.feature_map.all_action_features(context)
        return np.asarray(
            scaled_tanh_mean(self.theta, features, width), dtype=np.float64
        )


def fit_ridge_teacher(
    contexts: ArrayLike,
    labels: ArrayLike,
    development_indices: ArrayLike,
    *,
    action_count: int,
    ridge: float = 1.0,
    theta_radius: float = 1.0,
    feature_bound: float = 1.0,
) -> RidgeTeacher:
    """Fit multiclass ridge on development rows and scale the mapped parameter."""

    matrix = np.asarray(contexts, dtype=np.float64)
    target = np.asarray(labels, dtype=np.int64)
    indices = np.asarray(development_indices, dtype=np.int64)
    if matrix.ndim != 2 or matrix.shape[0] < 2 or matrix.shape[1] < 1:
        raise ValueError("contexts must be a nonempty matrix")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("contexts contain a nonfinite value")
    if target.shape != (matrix.shape[0],):
        raise ValueError("labels must match the context rows")
    if indices.ndim != 1 or indices.size < 2:
        raise ValueError("development_indices must contain at least two rows")
    if np.any(indices < 0) or np.any(indices >= matrix.shape[0]):
        raise ValueError("development_indices contain an out-of-range row")
    if np.unique(indices).size != indices.size:
        raise ValueError("development_indices contain duplicates")
    if isinstance(action_count, bool) or not isinstance(
        action_count, (int, np.integer)
    ):
        raise TypeError("action_count must be an integer")
    actions = int(action_count)
    if actions < 2:
        raise ValueError("action_count must be at least two")
    if np.any(target < 0) or np.any(target >= actions):
        raise ValueError("labels contain an action outside the declared range")
    ridge = float(ridge)
    radius = float(theta_radius)
    if not np.isfinite(ridge) or ridge <= 0.0:
        raise ValueError("ridge must be finite and positive")
    if not np.isfinite(radius) or radius <= 0.0:
        raise ValueError("theta_radius must be finite and positive")

    development = matrix[indices]
    labels_development = target[indices]
    responses = np.eye(actions, dtype=np.float64)[labels_development]
    context_mean = np.mean(development, axis=0)
    response_mean = np.mean(responses, axis=0)
    centered_contexts = development - context_mean
    centered_responses = responses - response_mean
    normal_matrix = centered_contexts.T @ centered_contexts
    normal_matrix += ridge * np.eye(matrix.shape[1], dtype=np.float64)
    rhs = centered_contexts.T @ centered_responses
    coefficients_unscaled = np.linalg.solve(normal_matrix, rhs)
    intercepts_unscaled = response_mean - context_mean @ coefficients_unscaled

    feature_map = FeatureMapSpec(
        context_dimension=matrix.shape[1],
        action_count=actions,
        feature_bound=feature_bound,
    )
    theta_unscaled = np.zeros(feature_map.feature_dimension, dtype=np.float64)
    offset = matrix.shape[1]
    theta_unscaled[offset : offset + actions] = intercepts_unscaled
    # np.kron(x, e_a) contracts with a row-major p-by-K matrix.
    theta_unscaled[offset + actions :] = coefficients_unscaled.reshape(-1)
    norm = float(np.linalg.norm(theta_unscaled))
    if not np.isfinite(norm) or norm <= 64.0 * np.finfo(np.float64).tiny:
        raise TeacherConstructionError("ridge teacher parameter is degenerate")
    scale_factor = radius / norm
    theta = theta_unscaled * scale_factor
    coefficients = coefficients_unscaled * scale_factor
    intercepts = intercepts_unscaled * scale_factor
    return RidgeTeacher(
        theta=theta,
        coefficients=coefficients,
        intercepts=intercepts,
        ridge=ridge,
        theta_radius=radius,
        scale_factor=scale_factor,
        unscaled_theta_norm=norm,
        development_index_digest=index_digest(indices),
        feature_map=feature_map,
    )


@dataclass(frozen=True)
class MisspecificationSpec:
    frequencies: FloatArray
    phases: FloatArray
    rho: float
    range_quantile: float
    seed: int

    def __post_init__(self) -> None:
        frequencies = np.asarray(self.frequencies, dtype=np.float64)
        phases = np.asarray(self.phases, dtype=np.float64)
        if frequencies.ndim != 2 or phases.shape != (frequencies.shape[0],):
            raise ValueError("misspecification arrays have incompatible shapes")
        if not np.all(np.isfinite(frequencies)) or not np.all(np.isfinite(phases)):
            raise ValueError("misspecification arrays contain nonfinite values")
        norms = np.linalg.norm(frequencies, axis=1)
        if not np.allclose(norms, 1.0, rtol=2e-13, atol=2e-14):
            raise ValueError("misspecification frequencies must have unit norm")
        if not np.isfinite(self.rho) or self.rho <= 0.0:
            raise ValueError("rho must be finite and positive")
        if not np.isfinite(self.range_quantile) or self.range_quantile <= 0.0:
            raise ValueError("range_quantile must be finite and positive")
        if isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        object.__setattr__(self, "frequencies", _readonly(frequencies.copy()))
        object.__setattr__(self, "phases", _readonly(phases.copy()))

    @property
    def action_count(self) -> int:
        return int(self.frequencies.shape[0])

    @property
    def context_dimension(self) -> int:
        return int(self.frequencies.shape[1])

    @property
    def digest(self) -> str:
        arrays = canonical_array_digest(
            {"frequencies": self.frequencies, "phases": self.phases}
        )
        payload = canonical_json(
            {
                "array_digest": arrays,
                "range_quantile": self.range_quantile,
                "rho": self.rho,
                "schema": "realistic-transport-misspecification-v1",
                "seed": self.seed,
            }
        ).encode("ascii")
        return hashlib.sha256(payload).hexdigest()

    def values(self, context: ArrayLike) -> FloatArray:
        vector = np.asarray(context, dtype=np.float64)
        if vector.shape != (self.context_dimension,):
            raise ValueError("context has the wrong dimension")
        if not np.all(np.isfinite(vector)):
            raise ValueError("context contains a nonfinite value")
        values = np.sin(self.frequencies @ vector + self.phases)
        if np.any(np.abs(values) > 1.0 + 8.0 * np.finfo(np.float64).eps):
            raise FloatingPointError("misspecification function exceeded its bound")
        return np.asarray(values, dtype=np.float64)

    def perturbation(self, context: ArrayLike) -> FloatArray:
        return np.asarray(self.rho * self.values(context), dtype=np.float64)

    def uniform_envelope(self) -> float:
        return self.rho


def build_misspecification(
    development_contexts: ArrayLike,
    teacher: RidgeTeacher,
    *,
    width: float,
    seed: int = 271828,
    quantile: float = 0.9,
    fraction: float = 0.25,
) -> MisspecificationSpec:
    """Freeze sinusoidal misspecification using development contexts only."""

    contexts = np.asarray(development_contexts, dtype=np.float64)
    if contexts.ndim != 2 or contexts.shape[1] != teacher.feature_map.context_dimension:
        raise ValueError("development_contexts have the wrong shape")
    if not np.all(np.isfinite(contexts)):
        raise ValueError("development_contexts contain a nonfinite value")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    quantile = float(quantile)
    fraction = float(fraction)
    if not 0.0 < quantile < 1.0:
        raise ValueError("quantile must lie strictly between zero and one")
    if not np.isfinite(fraction) or fraction <= 0.0:
        raise ValueError("fraction must be finite and positive")
    all_means = np.stack(
        [teacher.action_means(context, width=width) for context in contexts], axis=0
    )
    ranges = np.max(all_means, axis=1) - np.min(all_means, axis=1)
    range_quantile = float(np.quantile(ranges, quantile, method="linear"))
    if not np.isfinite(range_quantile) or range_quantile <= 0.0:
        raise TeacherConstructionError(
            "development teacher has a degenerate action-reward range"
        )
    rho = fraction * range_quantile

    rng = np.random.default_rng(int(seed))
    frequencies = rng.normal(
        size=(teacher.feature_map.action_count, teacher.feature_map.context_dimension)
    )
    norms = np.linalg.norm(frequencies, axis=1)
    if np.any(~np.isfinite(norms)) or np.any(norms <= 0.0):
        raise TeacherConstructionError("misspecification frequency draw is degenerate")
    frequencies /= norms[:, np.newaxis]
    phases = rng.uniform(-math.pi, math.pi, size=teacher.feature_map.action_count)
    return MisspecificationSpec(
        frequencies=frequencies,
        phases=phases,
        rho=rho,
        range_quantile=range_quantile,
        seed=int(seed),
    )


__all__ = [
    "MisspecificationSpec",
    "RidgeTeacher",
    "TeacherConstructionError",
    "build_misspecification",
    "fit_ridge_teacher",
]
