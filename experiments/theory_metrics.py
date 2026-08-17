"""Dense diagnostics used by the retained linear confidence audit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike

from .curvature_operators import (
    DenseSPDLinearOperator,
    FloatArray,
    OperatorLike,
    _as_float64_array,
    _matvec,
    _nonnegative_float,
    _positive_float,
    _readonly,
)


def _materialize_spd(
    operator: OperatorLike,
    *,
    dimension: int | None = None,
    name: str = "operator",
) -> FloatArray:
    if hasattr(operator, "to_dense"):
        dense = operator.to_dense()  # type: ignore[union-attr]
    elif callable(operator) or hasattr(operator, "matvec"):
        shape = getattr(operator, "shape", None)
        if shape is not None:
            shape = tuple(shape)
            if len(shape) != 2 or shape[0] != shape[1]:
                raise ValueError(f"{name} shape must be square, got {shape}")
            inferred_dimension = int(shape[0])
            if dimension is not None and inferred_dimension != dimension:
                raise ValueError(
                    f"{name} dimension must be {dimension}, got {inferred_dimension}"
                )
            dimension = inferred_dimension
        if dimension is None:
            raise ValueError(
                f"cannot materialize {name} without a shape or explicit dimension"
            )
        basis = np.eye(dimension, dtype=np.float64)
        dense = np.column_stack(
            [_matvec(operator, basis[:, column]) for column in range(dimension)]
        )
    else:
        dense = _as_float64_array(operator, name=name, ndim=2)
    wrapped = DenseSPDLinearOperator(dense)
    if dimension is not None and wrapped.shape != (dimension, dimension):
        raise ValueError(
            f"{name} must have shape ({dimension}, {dimension}), got {wrapped.shape}"
        )
    return wrapped.to_dense()


def _logdet_spd(matrix: FloatArray, *, name: str) -> float:
    sign, log_abs_determinant = np.linalg.slogdet(matrix)
    if sign != 1.0 or not np.isfinite(log_abs_determinant):
        raise FloatingPointError(f"{name} does not have a finite positive determinant")
    return float(log_abs_determinant)


@dataclass(frozen=True)
class DynamicLogdetResult:
    widths_squared: FloatArray
    information_complexity: float
    transition_logdeterminants: FloatArray
    variation_charge: float
    endpoint_logdeterminant: float
    dynamic_potential: float
    identity_right_hand_side: float
    normalized_perturbations: tuple[FloatArray, ...]

    @property
    def identity_residual(self) -> float:
        return self.information_complexity - self.identity_right_hand_side


def dynamic_logdet_metrics(
    operators: Sequence[OperatorLike],
    played_features: ArrayLike,
    *,
    noise_variance: float = 1.0,
) -> DynamicLogdetResult:
    """Compute the exact pathwise dynamic log-determinant decomposition."""

    features = _as_float64_array(
        played_features, name="played_features", ndim=2, copy=True
    )
    round_count, dimension = features.shape
    if dimension == 0:
        raise ValueError("played_features must have a positive parameter dimension")
    operator_sequence = tuple(operators)
    if len(operator_sequence) != round_count + 1:
        raise ValueError(
            "operators must contain one round operator per played feature plus "
            "the terminal operator"
        )
    variance = _positive_float(noise_variance, name="noise_variance")
    dense_operators = tuple(
        _materialize_spd(operator, dimension=dimension, name=f"operators[{index}]")
        for index, operator in enumerate(operator_sequence)
    )

    initial_logdet = _logdet_spd(dense_operators[0], name="initial operator")
    terminal_logdet = _logdet_spd(dense_operators[-1], name="terminal operator")
    widths: list[float] = []
    transition_logdets: list[float] = []
    perturbations: list[FloatArray] = []
    for index, feature in enumerate(features):
        current = dense_operators[index]
        following = dense_operators[index + 1]
        width_squared = float(feature @ np.linalg.solve(current, feature))
        if not np.isfinite(width_squared) or width_squared < 0.0:
            raise FloatingPointError(
                f"width squared at round {index} is invalid ({width_squared})"
            )
        widths.append(width_squared)

        updated = current + np.outer(feature, feature) / variance
        eigenvalues, eigenvectors = np.linalg.eigh(updated)
        if np.any(eigenvalues <= 0.0) or not np.all(np.isfinite(eigenvalues)):
            raise ArithmeticError(f"rank-one updated operator {index} is not SPD")
        inverse_root = (eigenvectors * (1.0 / np.sqrt(eigenvalues))) @ eigenvectors.T
        perturbation = inverse_root @ (following - updated) @ inverse_root
        if not np.allclose(perturbation, perturbation.T, rtol=1e-11, atol=1e-13):
            raise FloatingPointError(
                f"normalized perturbation {index} lost numerical symmetry"
            )
        perturbation = np.asarray(0.5 * (perturbation + perturbation.T))
        identity_plus = np.eye(dimension, dtype=np.float64) + perturbation
        DenseSPDLinearOperator(identity_plus)
        transition_logdets.append(
            _logdet_spd(identity_plus, name=f"normalized transition {index}")
        )
        perturbations.append(_readonly(perturbation.copy()))

    widths_array = _readonly(np.asarray(widths, dtype=np.float64))
    transitions_array = _readonly(np.asarray(transition_logdets, dtype=np.float64))
    information = float(np.sum(np.log1p(widths_array / variance)))
    endpoint = terminal_logdet - initial_logdet
    identity_rhs = endpoint - float(np.sum(transitions_array))
    variation = float(sum(-value for value in transition_logdets if value < 0.0))
    return DynamicLogdetResult(
        widths_squared=widths_array,
        information_complexity=information,
        transition_logdeterminants=transitions_array,
        variation_charge=variation,
        endpoint_logdeterminant=endpoint,
        dynamic_potential=endpoint + variation,
        identity_right_hand_side=identity_rhs,
        normalized_perturbations=tuple(perturbations),
    )


@dataclass(frozen=True)
class WidthSumResult:
    width_sum: float
    feature_bound: float
    coefficient: float
    information_complexity: float
    information_bound: float
    dynamic_potential: float
    dynamic_bound: float
    dynamic_metrics: DynamicLogdetResult


def width_sum_inequality(
    operators: Sequence[OperatorLike],
    played_features: ArrayLike,
    *,
    damping: float,
    noise_variance: float = 1.0,
    feature_bound: float | None = None,
) -> WidthSumResult:
    """Evaluate the information and dynamic bounds on cumulative widths."""

    features = _as_float64_array(
        played_features, name="played_features", ndim=2, copy=True
    )
    lower_bound = _positive_float(damping, name="damping")
    variance = _positive_float(noise_variance, name="noise_variance")
    metrics = dynamic_logdet_metrics(operators, features, noise_variance=variance)

    dimension = features.shape[1]
    for index, operator in enumerate(operators[:-1]):
        dense = _materialize_spd(
            operator, dimension=dimension, name=f"operators[{index}]"
        )
        eigenvalues = np.linalg.eigvalsh(dense)
        minimum = float(eigenvalues[0])
        tolerance = (
            512.0
            * np.finfo(np.float64).eps
            * max(1, dimension)
            * max(1.0, lower_bound, abs(float(eigenvalues[-1])))
        )
        if minimum < lower_bound - tolerance:
            raise ValueError(
                f"operators[{index}] has minimum eigenvalue {minimum}, below "
                f"damping {lower_bound}"
            )

    feature_norms = np.linalg.norm(features, axis=1)
    if feature_bound is None:
        bound = float(np.max(feature_norms)) if feature_norms.size else 0.0
    else:
        bound = _nonnegative_float(feature_bound, name="feature_bound")
        violations = np.flatnonzero(feature_norms > bound)
        if violations.size:
            first = int(violations[0])
            raise ValueError(
                f"feature norm at round {first} is {feature_norms[first]}, above "
                f"feature_bound {bound}"
            )

    coefficient = variance + bound * bound / lower_bound
    width_sum = float(np.sum(metrics.widths_squared))
    return WidthSumResult(
        width_sum=width_sum,
        feature_bound=bound,
        coefficient=coefficient,
        information_complexity=metrics.information_complexity,
        information_bound=coefficient * metrics.information_complexity,
        dynamic_potential=metrics.dynamic_potential,
        dynamic_bound=coefficient * metrics.dynamic_potential,
        dynamic_metrics=metrics,
    )


@dataclass(frozen=True)
class GeneralizedEigenvalueResult:
    eigenvalues: FloatArray
    maximum: float
    maximizing_vector: FloatArray
    residual_norm: float


def generalized_eigenvalues(
    approximate_operator: OperatorLike,
    reference_operator: OperatorLike,
) -> GeneralizedEigenvalueResult:
    r"""Solve ``A v = kappa B v`` globally for dense SPD ``A`` and ``B``."""

    reference = _materialize_spd(reference_operator, name="reference_operator")
    dimension = reference.shape[0]
    approximate = _materialize_spd(
        approximate_operator,
        dimension=dimension,
        name="approximate_operator",
    )
    try:
        from scipy.linalg import eigh
    except ImportError as error:  # pragma: no cover - requirements pin SciPy.
        raise RuntimeError(
            "exact generalized eigenvalue diagnostics require scipy"
        ) from error
    eigenvalues, eigenvectors = eigh(
        approximate,
        reference,
        check_finite=True,
        driver="gvd",
    )
    if not np.all(np.isfinite(eigenvalues)) or np.any(eigenvalues <= 0.0):
        raise ArithmeticError("generalized eigenvalues must be finite and positive")
    maximum = float(eigenvalues[-1])
    maximizing_vector = np.asarray(eigenvectors[:, -1], dtype=np.float64)
    norm = float(np.linalg.norm(maximizing_vector))
    if norm == 0.0 or not np.isfinite(norm):
        raise FloatingPointError("generalized eigenvector has invalid norm")
    maximizing_vector = maximizing_vector / norm
    residual = approximate @ maximizing_vector - maximum * (
        reference @ maximizing_vector
    )
    return GeneralizedEigenvalueResult(
        eigenvalues=_readonly(np.asarray(eigenvalues, dtype=np.float64).copy()),
        maximum=maximum,
        maximizing_vector=_readonly(maximizing_vector.copy()),
        residual_norm=float(np.linalg.norm(residual)),
    )


__all__ = [
    "DynamicLogdetResult",
    "GeneralizedEigenvalueResult",
    "WidthSumResult",
    "dynamic_logdet_metrics",
    "generalized_eigenvalues",
    "width_sum_inequality",
]
