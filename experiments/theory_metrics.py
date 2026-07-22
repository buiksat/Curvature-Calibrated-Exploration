"""Numerical diagnostics corresponding to the paper's pathwise theory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike

from .curvature_operators import (
    ConjugateGradientResult,
    DenseSPDLinearOperator,
    FloatArray,
    OperatorLike,
    _as_float64_array,
    _matvec,
    _nonnegative_float,
    _positive_float,
    _readonly,
    _validate_vector,
    conjugate_gradient,
)


def _strict_sqrt(value: float, *, name: str) -> float:
    scalar = float(value)
    if not np.isfinite(scalar):
        raise FloatingPointError(f"{name} is non-finite")
    if scalar < 0.0:
        raise FloatingPointError(f"{name} is negative ({scalar}); refusing to clip it")
    return float(np.sqrt(scalar))


def _nonnegative_int(value: int, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def _symmetric_matrix(value: ArrayLike, *, name: str) -> FloatArray:
    matrix = _as_float64_array(value, name=name, ndim=2, copy=True)
    if matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"{name} must be square, got shape {matrix.shape}")
    if matrix.shape[0] == 0:
        raise ValueError(f"{name} must have positive dimension")
    if not np.allclose(matrix, matrix.T, rtol=1e-12, atol=1e-14):
        asymmetry = float(np.max(np.abs(matrix - matrix.T)))
        raise ValueError(f"{name} must be symmetric; max asymmetry is {asymmetry}")
    return np.asarray(0.5 * (matrix + matrix.T), dtype=np.float64)


def _log_one_plus_ratio(numerator: float, denominator: float) -> float:
    """Evaluate ``log(1 + numerator / denominator)`` without ratio overflow."""

    if numerator == 0.0:
        return 0.0
    log_denominator = float(np.log(denominator))
    value = float(
        np.logaddexp(log_denominator, float(np.log(numerator))) - log_denominator
    )
    if not np.isfinite(value) or value < 0.0:
        raise FloatingPointError("log-ratio evaluation produced an invalid value")
    return value


def _eigenvalue_sign_tolerance(eigenvalues: FloatArray) -> float:
    """Backward-error band used only to classify numerical zero eigenvalues."""

    if eigenvalues.ndim != 1 or not np.all(np.isfinite(eigenvalues)):
        raise ValueError("eigenvalues must be a finite one-dimensional array")
    spectral_scale = float(np.max(np.abs(eigenvalues), initial=0.0))
    return float(
        256.0
        * np.finfo(np.float64).eps
        * max(1, eigenvalues.size)
        * spectral_scale
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
                f"cannot materialize {name} without a shape or an explicit dimension"
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


def dense_width_squared(operator: OperatorLike, feature: ArrayLike) -> float:
    """Return ``feature.T @ operator^{-1} @ feature`` using a dense solve."""

    vector = _as_float64_array(feature, name="feature", ndim=1)
    if vector.size == 0:
        raise ValueError("feature must have positive dimension")
    dense = _materialize_spd(operator, dimension=vector.size)
    solution = np.linalg.solve(dense, vector)
    value = float(vector @ solution)
    if not np.isfinite(value):
        raise FloatingPointError("dense width squared is non-finite")
    if value < 0.0:
        raise FloatingPointError(
            f"dense width squared is negative ({value}); refusing to clip it"
        )
    return value


def dense_width(operator: OperatorLike, feature: ArrayLike) -> float:
    return _strict_sqrt(
        dense_width_squared(operator, feature), name="dense width squared"
    )


# The dense solve is the exact reference used by the small diagnostic experiments.
exact_width_squared = dense_width_squared
exact_width = dense_width


@dataclass(frozen=True)
class FeatureDriftSandwichResult:
    frozen_curvature: FloatArray
    current_curvature: FloatArray
    stacked_frozen_design: FloatArray
    stacked_current_design: FloatArray
    chi: float
    minimum_squared_singular_value: float
    maximum_squared_singular_value: float
    lower_factor: float | None
    upper_factor: float


def feature_drift_sandwich(
    frozen_features: ArrayLike,
    current_features: ArrayLike,
    *,
    damping: float,
    noise_variance: float,
) -> FeatureDriftSandwichResult:
    r"""Audit the sharpened stacked-design feature-drift sandwich.

    Rows of ``frozen_features`` are the predictable historical gradients
    ``g_s`` and rows of ``current_features`` are the same samples replayed at
    the current parameter.  If ``chi < 1``, the returned factors verify

    ``(1-chi)^2 Cbar <= C <= (1+chi)^2 Cbar``.

    The eigendecompositions are ordinary float64 diagnostics, not verified
    numerical enclosures and not policy inputs.
    """

    frozen = _as_float64_array(
        frozen_features, name="frozen_features", ndim=2, copy=True
    )
    current = _as_float64_array(
        current_features, name="current_features", ndim=2, copy=True
    )
    if frozen.shape != current.shape:
        raise ValueError("frozen_features and current_features must have equal shape")
    sample_count, dimension = frozen.shape
    if dimension == 0:
        raise ValueError("feature matrices must have positive parameter dimension")
    ridge = _positive_float(damping, name="damping")
    variance = _positive_float(noise_variance, name="noise_variance")

    identity = np.eye(dimension, dtype=np.float64)
    frozen_curvature = ridge * identity + frozen.T @ frozen / variance
    current_curvature = ridge * identity + current.T @ current / variance
    eigenvalues, eigenvectors = np.linalg.eigh(frozen_curvature)
    if np.any(eigenvalues <= 0.0) or not np.all(np.isfinite(eigenvalues)):
        raise FloatingPointError("frozen curvature is not positive definite")
    inverse_root = (
        eigenvectors * (1.0 / np.sqrt(eigenvalues))
    ) @ eigenvectors.T
    whitened_frozen = inverse_root @ frozen.T / np.sqrt(variance)
    whitened_drift = inverse_root @ (current - frozen).T / np.sqrt(variance)

    stacked_frozen = np.vstack((np.sqrt(ridge) * inverse_root, whitened_frozen.T))
    stacked_current = np.vstack(
        (np.sqrt(ridge) * inverse_root, (whitened_frozen + whitened_drift).T)
    )
    expected_shape = (dimension + sample_count, dimension)
    if (
        stacked_frozen.shape != expected_shape
        or stacked_current.shape != expected_shape
    ):
        raise AssertionError("stacked design has an unexpected shape")

    chi = (
        0.0
        if sample_count == 0
        else float(np.linalg.norm(whitened_drift, ord=2))
    )
    whitened_current = inverse_root @ current_curvature @ inverse_root
    frozen_identity_residual = float(
        np.linalg.norm(stacked_frozen.T @ stacked_frozen - identity, ord=2)
    )
    current_identity_residual = float(
        np.linalg.norm(stacked_current.T @ stacked_current - whitened_current, ord=2)
    )
    difference_residual = float(
        abs(np.linalg.norm(stacked_current - stacked_frozen, ord=2) - chi)
    )
    tolerance = (
        4096.0
        * np.finfo(np.float64).eps
        * max(1, dimension + sample_count)
        * max(1.0, chi, np.linalg.norm(whitened_current, ord=2))
    )
    if (
        frozen_identity_residual > tolerance
        or current_identity_residual > tolerance
        or difference_residual > tolerance
    ):
        raise FloatingPointError("a stacked-design identity failed in float64")

    singular_values = np.linalg.svd(stacked_current, compute_uv=False)
    minimum_squared = float(np.min(singular_values) ** 2)
    maximum_squared = float(np.max(singular_values) ** 2)
    lower = (1.0 - chi) ** 2 if chi < 1.0 else None
    upper = (1.0 + chi) ** 2
    if lower is not None and minimum_squared < lower - tolerance:
        raise FloatingPointError("the sharpened lower feature-drift bound failed")
    if maximum_squared > upper + tolerance:
        raise FloatingPointError("the sharpened upper feature-drift bound failed")
    return FeatureDriftSandwichResult(
        frozen_curvature=_readonly(frozen_curvature.copy()),
        current_curvature=_readonly(current_curvature.copy()),
        stacked_frozen_design=_readonly(stacked_frozen.copy()),
        stacked_current_design=_readonly(stacked_current.copy()),
        chi=chi,
        minimum_squared_singular_value=minimum_squared,
        maximum_squared_singular_value=maximum_squared,
        lower_factor=lower,
        upper_factor=upper,
    )


@dataclass(frozen=True)
class CGWidthResult:
    width_squared: float
    width: float
    cg: ConjugateGradientResult

    @property
    def solution(self) -> FloatArray:
        return self.cg.solution


def cg_width(
    operator: OperatorLike,
    feature: ArrayLike,
    *,
    tolerance: float = 1e-10,
    absolute_tolerance: float = 0.0,
    max_iterations: int | None = None,
    raise_on_nonconvergence: bool = True,
) -> CGWidthResult:
    """Estimate a predictive width with CG from the required zero start."""

    vector = _as_float64_array(feature, name="feature", ndim=1, copy=True)
    result = conjugate_gradient(
        operator,
        vector,
        tolerance=tolerance,
        absolute_tolerance=absolute_tolerance,
        max_iterations=max_iterations,
        initial_solution=None,
        raise_on_nonconvergence=raise_on_nonconvergence,
    )
    squared = float(vector @ result.solution)
    if not np.isfinite(squared):
        raise FloatingPointError("CG width squared is non-finite")
    if squared < 0.0:
        raise FloatingPointError(
            f"CG width squared is negative ({squared}); refusing to clip it"
        )
    return CGWidthResult(
        width_squared=squared,
        width=_strict_sqrt(squared, name="CG width squared"),
        cg=result,
    )


def relative_energy_error(
    operator: OperatorLike,
    exact_solution: ArrayLike,
    approximate_solution: ArrayLike,
) -> float:
    """Compute ``||u-u_tilde||_C / ||u||_C`` without regularization."""

    exact = _as_float64_array(exact_solution, name="exact_solution", ndim=1)
    if exact.size == 0:
        raise ValueError("exact_solution must have positive dimension")
    approximate = _validate_vector(
        approximate_solution, exact.size, name="approximate_solution"
    )
    difference = exact - approximate
    denominator_squared = float(exact @ _matvec(operator, exact))
    numerator_squared = float(difference @ _matvec(operator, difference))
    if not np.isfinite(denominator_squared) or not np.isfinite(numerator_squared):
        raise FloatingPointError("energy norm calculation produced a non-finite value")
    if denominator_squared < 0.0 or numerator_squared < 0.0:
        raise ArithmeticError("energy norm squared is negative; operator is not SPD")
    if denominator_squared == 0.0:
        if numerator_squared == 0.0:
            return 0.0
        raise ZeroDivisionError(
            "relative energy error is undefined for a zero exact solution"
        )
    return float(np.sqrt(numerator_squared / denominator_squared))


@dataclass(frozen=True)
class CGSandwichResult:
    exact_width_squared: float
    approximate_width_squared: float
    relative_energy_error: float
    lower_bound: float
    upper_bound: float


def cg_sandwich(
    operator: OperatorLike,
    feature: ArrayLike,
    approximate_solution: ArrayLike,
    *,
    require_error_below_one: bool = True,
) -> CGSandwichResult:
    """Evaluate the multiplicative CG quadratic-form sandwich exactly."""

    vector = _as_float64_array(feature, name="feature", ndim=1)
    if vector.size == 0:
        raise ValueError("feature must have positive dimension")
    approximate = _validate_vector(
        approximate_solution, vector.size, name="approximate_solution"
    )
    dense = _materialize_spd(operator, dimension=vector.size)
    exact_solution = np.linalg.solve(dense, vector)
    exact_squared = float(vector @ exact_solution)
    approximate_squared = float(vector @ approximate)
    if exact_squared < 0.0 or approximate_squared < 0.0:
        raise FloatingPointError("a width squared is negative; refusing to clip it")
    error = relative_energy_error(operator, exact_solution, approximate)
    if require_error_below_one and error >= 1.0:
        raise ValueError(
            f"CG sandwich requires relative energy error below one, got {error}"
        )
    return CGSandwichResult(
        exact_width_squared=exact_squared,
        approximate_width_squared=approximate_squared,
        relative_energy_error=error,
        lower_bound=(1.0 - error) * exact_squared,
        upper_bound=(1.0 + error) * exact_squared,
    )


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

    @property
    def lambda_alg(self) -> float:
        return self.information_complexity

    @property
    def v_alg(self) -> float:
        return self.variation_charge

    @property
    def gamma_dynamic(self) -> float:
        return self.dynamic_potential


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
        solution = np.linalg.solve(current, feature)
        width_squared = float(feature @ solution)
        if not np.isfinite(width_squared) or width_squared < 0.0:
            raise FloatingPointError(
                f"width squared at round {index} is invalid ({width_squared})"
            )
        widths.append(width_squared)

        updated = current + np.outer(feature, feature) / variance
        eigenvalues, eigenvectors = np.linalg.eigh(updated)
        if np.any(eigenvalues <= 0.0) or not np.all(np.isfinite(eigenvalues)):
            raise ArithmeticError(f"rank-one updated operator {index} is not SPD")
        inverse_root = (
            eigenvectors * (1.0 / np.sqrt(eigenvalues))
        ) @ eigenvectors.T
        perturbation = inverse_root @ (following - updated) @ inverse_root
        if not np.allclose(perturbation, perturbation.T, rtol=1e-11, atol=1e-13):
            raise FloatingPointError(
                f"normalized perturbation {index} lost numerical symmetry"
            )
        perturbation = 0.5 * (perturbation + perturbation.T)
        identity_plus = np.eye(dimension, dtype=np.float64) + perturbation
        DenseSPDLinearOperator(identity_plus)
        transition_logdet = _logdet_spd(
            identity_plus, name=f"normalized transition {index}"
        )
        transition_logdets.append(transition_logdet)
        perturbations.append(_readonly(np.asarray(perturbation).copy()))

    widths_array = _readonly(np.asarray(widths, dtype=np.float64))
    transitions_array = _readonly(
        np.asarray(transition_logdets, dtype=np.float64)
    )
    information = float(np.sum(np.log1p(widths_array / variance)))
    endpoint = terminal_logdet - initial_logdet
    identity_rhs = endpoint - float(np.sum(transitions_array))
    variation = float(
        sum(-value for value in transition_logdets if value < 0.0)
    )
    dynamic_potential = endpoint + variation
    return DynamicLogdetResult(
        widths_squared=widths_array,
        information_complexity=information,
        transition_logdeterminants=transitions_array,
        variation_charge=variation,
        endpoint_logdeterminant=endpoint,
        dynamic_potential=dynamic_potential,
        identity_right_hand_side=identity_rhs,
        normalized_perturbations=tuple(perturbations),
    )


dynamic_logdet_identity = dynamic_logdet_metrics


@dataclass(frozen=True)
class RankSensitiveVariationResult:
    eigenvalues: FloatArray
    negative_eigenvalues: FloatArray
    positive_eigenvalues: FloatArray
    negative_rank: int
    numerical_zero_count: int
    rank_bound: int
    nu: float
    eigenvalue_sign_tolerance: float
    minimum_identity_eigenvalue: float
    negative_log_contribution: float
    positive_log_contribution: float
    transition_logdeterminant: float
    variation_charge: float
    upper_bound: float

    @property
    def slack(self) -> float:
        return self.upper_bound - self.variation_charge


def rank_sensitive_variation_bound(
    normalized_perturbation: ArrayLike,
    *,
    rank_bound: int,
    nu: float,
) -> RankSensitiveVariationResult:
    r"""Check and evaluate ``[-log det(I + Xi)]_+ <= r log(1/(1-nu))``.

    ``rank_bound`` bounds the number of negative eigenvalues of ``Xi``.  The
    supplied ``nu`` must lie in ``[0, 1)`` and bound their magnitudes.  Values in
    a scale-aware symmetric-eigensolver backward-error band around zero are
    classified as numerical zeros; values outside that band retain their sign.
    Positive eigenvalues are kept explicitly because their log contributions
    reduce, rather than increase, the variation charge.
    """

    perturbation = _symmetric_matrix(
        normalized_perturbation, name="normalized_perturbation"
    )
    dimension = perturbation.shape[0]
    declared_rank = _nonnegative_int(rank_bound, name="rank_bound")
    if declared_rank > dimension:
        raise ValueError(
            f"rank_bound must not exceed dimension {dimension}, got {declared_rank}"
        )
    contraction = _nonnegative_float(nu, name="nu")
    if contraction >= 1.0:
        raise ValueError("nu must be strictly less than one")

    eigenvalues = np.asarray(np.linalg.eigvalsh(perturbation), dtype=np.float64)
    if not np.all(np.isfinite(eigenvalues)):
        raise FloatingPointError("perturbation eigenvalues are non-finite")
    identity_eigenvalues = 1.0 + eigenvalues
    if np.any(identity_eigenvalues <= 0.0):
        raise ValueError("I + normalized_perturbation must be positive definite")

    sign_tolerance = _eigenvalue_sign_tolerance(eigenvalues)
    negative = np.asarray(
        eigenvalues[eigenvalues < -sign_tolerance], dtype=np.float64
    )
    positive = np.asarray(
        eigenvalues[eigenvalues > sign_tolerance], dtype=np.float64
    )
    negative_rank = int(negative.size)
    numerical_zero_count = dimension - negative_rank - int(positive.size)
    if negative_rank > declared_rank:
        raise ValueError(
            f"negative eigenvalue rank {negative_rank} exceeds rank_bound "
            f"{declared_rank}"
        )
    if negative.size and float(negative[0]) < -contraction - sign_tolerance:
        raise ValueError(
            "minimum eigenvalue violates the declared spectral floor: "
            f"{negative[0]} < {-contraction}"
        )

    negative_contribution = float(np.sum(-np.log1p(negative)))
    positive_contribution = float(np.sum(np.log1p(positive)))
    if (
        not np.isfinite(negative_contribution)
        or negative_contribution < 0.0
        or not np.isfinite(positive_contribution)
        or positive_contribution < 0.0
    ):
        raise FloatingPointError("signed log-determinant contributions are invalid")
    transition_logdeterminant = positive_contribution - negative_contribution
    variation_charge = max(-transition_logdeterminant, 0.0)
    upper_bound = float(declared_rank * -np.log1p(-contraction))
    if not np.isfinite(upper_bound) or upper_bound < 0.0:
        raise FloatingPointError("variation upper bound is invalid")
    tolerance = (
        64.0
        * np.finfo(np.float64).eps
        * max(1, dimension)
        * max(1.0, negative_contribution, upper_bound)
    )
    if negative_contribution > upper_bound + tolerance:
        raise FloatingPointError(
            "computed negative-eigenvalue contribution exceeds its analytic bound"
        )

    return RankSensitiveVariationResult(
        eigenvalues=_readonly(eigenvalues.copy()),
        negative_eigenvalues=_readonly(negative.copy()),
        positive_eigenvalues=_readonly(positive.copy()),
        negative_rank=negative_rank,
        numerical_zero_count=numerical_zero_count,
        rank_bound=declared_rank,
        nu=contraction,
        eigenvalue_sign_tolerance=sign_tolerance,
        minimum_identity_eigenvalue=float(identity_eigenvalues[0]),
        negative_log_contribution=negative_contribution,
        positive_log_contribution=positive_contribution,
        transition_logdeterminant=transition_logdeterminant,
        variation_charge=variation_charge,
        upper_bound=upper_bound,
    )


@dataclass(frozen=True)
class EndpointRankTraceLogdetResult:
    eigenvalues: FloatArray
    positive_eigenvalues: FloatArray
    positive_rank: int
    numerical_zero_count: int
    rank_bound: int
    trace: float
    trace_bound: float
    damping: float
    eigenvalue_sign_tolerance: float
    endpoint_logdeterminant: float
    upper_bound: float

    @property
    def slack(self) -> float:
        return self.upper_bound - self.endpoint_logdeterminant


@dataclass(frozen=True)
class InformationGainClosureResult:
    eigenvalues: FloatArray
    damping: float
    trace: float
    rank: int
    rank_bound: int
    operator_ratio: float
    statistical_effective_dimension: float
    exact_logdet: float
    rank_trace_bound: float
    effective_dimension_multiplier: float
    effective_dimension_bound: float

    @property
    def best_upper_bound(self) -> float:
        return min(self.rank_trace_bound, self.effective_dimension_bound)


@dataclass(frozen=True)
class SpectralTailInformationResult:
    eigenvalues_descending: FloatArray
    damping: float
    horizon: int
    tail_rank: int
    effective_top_rank: int
    spectral_tail: float
    exact_logdet: float
    top_rank_bound: float
    tail_bound: float
    upper_bound: float


def spectral_tail_information_bound(
    increment: ArrayLike,
    *,
    damping: float,
    horizon: int,
    feature_bound: float,
    noise_variance: float,
    tail_rank: int,
) -> SpectralTailInformationResult:
    r"""Evaluate the approximate-rank spectral-tail log-det closure.

    For ``A >= 0`` generated by at most ``horizon`` rank-one terms, this checks

    ``log det(I+A/lambda) <= r_T log(1+T G^2/(r_T lambda sigma^2))
                              + sum_{i>r} nu_i/lambda``.

    The first term is defined as zero when ``r_T=min(r,T)`` is zero.
    """

    matrix = _symmetric_matrix(increment, name="increment")
    dimension = matrix.shape[0]
    ridge = _positive_float(damping, name="damping")
    rounds = _nonnegative_int(horizon, name="horizon")
    bound = _nonnegative_float(feature_bound, name="feature_bound")
    variance = _positive_float(noise_variance, name="noise_variance")
    rank = _nonnegative_int(tail_rank, name="tail_rank")
    if rank > dimension:
        raise ValueError("tail_rank must not exceed the matrix dimension")

    eigenvalues = np.asarray(np.linalg.eigvalsh(matrix), dtype=np.float64)
    sign_tolerance = _eigenvalue_sign_tolerance(eigenvalues)
    if np.any(eigenvalues < -sign_tolerance):
        raise ValueError("increment must be positive semidefinite")
    positive = np.asarray(
        np.where(eigenvalues > sign_tolerance, eigenvalues, 0.0),
        dtype=np.float64,
    )[::-1]
    observed_rank = int(np.count_nonzero(positive))
    if observed_rank > rounds:
        raise ValueError(
            "increment rank exceeds horizon; it cannot be a sum of the declared "
            "number of rank-one terms"
        )
    observed_trace = float(np.sum(positive))
    trace_bound = rounds * bound * bound / variance
    trace_tolerance = (
        512.0
        * np.finfo(np.float64).eps
        * max(1, dimension)
        * max(1.0, observed_trace, trace_bound)
    )
    if observed_trace > trace_bound + trace_tolerance:
        raise ValueError("increment trace exceeds T G^2 / sigma^2")

    effective_top_rank = min(rank, rounds)
    spectral_tail = float(np.sum(positive[rank:]))
    exact = float(np.sum(np.log1p(positive / ridge)))
    if effective_top_rank == 0:
        top_bound = 0.0
    else:
        top_bound = float(
            effective_top_rank
            * np.log1p(
                rounds
                * bound
                * bound
                / (effective_top_rank * ridge * variance)
            )
        )
    tail_bound = spectral_tail / ridge
    upper = top_bound + tail_bound
    tolerance = (
        1024.0
        * np.finfo(np.float64).eps
        * max(1, dimension)
        * max(1.0, exact, upper)
    )
    if exact > upper + tolerance:
        raise FloatingPointError("spectral-tail information bound was violated")
    return SpectralTailInformationResult(
        eigenvalues_descending=_readonly(positive.copy()),
        damping=ridge,
        horizon=rounds,
        tail_rank=rank,
        effective_top_rank=effective_top_rank,
        spectral_tail=spectral_tail,
        exact_logdet=exact,
        top_rank_bound=top_bound,
        tail_bound=tail_bound,
        upper_bound=upper,
    )


def bounded_output_residual_factor(
    *,
    output_bound: float,
    noise_scale: float,
    horizon: int,
    failure_probability: float,
) -> float:
    r"""Return ``8 B_mu^2 + 4 sigma^2 log(2T/delta_R)``."""

    bound = _nonnegative_float(output_bound, name="output_bound")
    scale = _nonnegative_float(noise_scale, name="noise_scale")
    rounds = _nonnegative_int(horizon, name="horizon")
    if rounds == 0:
        raise ValueError("horizon must be positive")
    probability = float(failure_probability)
    if not np.isfinite(probability) or not 0.0 < probability < 1.0:
        raise ValueError("failure_probability must lie strictly between zero and one")
    return float(
        8.0 * bound * bound
        + 4.0 * scale * scale * np.log(2.0 * rounds / probability)
    )


def information_gain_closure(
    increment: ArrayLike,
    *,
    damping: float,
    rank_bound: int | None = None,
) -> InformationGainClosureResult:
    r"""Close ``log det(I + A/lambda)`` by rank or effective dimension.

    ``A`` must be positive semidefinite.  The effective dimension is the
    statistical quantity ``tr(A(A+lambda I)^{-1})``; it is deliberately not
    the trace-based effective rank ``tr(A)/||A||``.
    """

    matrix = _symmetric_matrix(increment, name="increment")
    ridge = _positive_float(damping, name="damping")
    eigenvalues = np.asarray(np.linalg.eigvalsh(matrix), dtype=np.float64)
    sign_tolerance = _eigenvalue_sign_tolerance(eigenvalues)
    if np.any(eigenvalues < -sign_tolerance):
        raise ValueError("increment must be positive semidefinite")
    positive = np.asarray(
        np.where(eigenvalues > sign_tolerance, eigenvalues, 0.0),
        dtype=np.float64,
    )
    observed_rank = int(np.count_nonzero(positive))
    if rank_bound is None:
        declared_rank = observed_rank
    else:
        declared_rank = _nonnegative_int(rank_bound, name="rank_bound")
        if declared_rank > matrix.shape[0]:
            raise ValueError("rank_bound must not exceed the matrix dimension")
        if observed_rank > declared_rank:
            raise ValueError(
                f"positive rank {observed_rank} exceeds rank_bound {declared_rank}"
            )
    trace = float(np.sum(positive))
    exact = float(np.sum(np.log1p(positive / ridge)))
    if declared_rank == 0:
        rank_trace = 0.0
    else:
        rank_trace = float(
            declared_rank
            * np.log1p(trace / (float(declared_rank) * ridge))
        )
    operator_ratio = float(np.max(positive, initial=0.0) / ridge)
    effective_dimension = float(np.sum(positive / (positive + ridge)))
    if operator_ratio == 0.0:
        multiplier = 1.0
    else:
        multiplier = float(
            ((1.0 + operator_ratio) / operator_ratio)
            * np.log1p(operator_ratio)
        )
    effective_bound = multiplier * effective_dimension
    tolerance = (
        128.0
        * np.finfo(np.float64).eps
        * max(1, matrix.shape[0])
        * max(1.0, exact, rank_trace, effective_bound)
    )
    if exact > rank_trace + tolerance or exact > effective_bound + tolerance:
        raise FloatingPointError("an information-gain closure was violated")
    return InformationGainClosureResult(
        eigenvalues=_readonly(positive.copy()),
        damping=ridge,
        trace=trace,
        rank=observed_rank,
        rank_bound=declared_rank,
        operator_ratio=operator_ratio,
        statistical_effective_dimension=effective_dimension,
        exact_logdet=exact,
        rank_trace_bound=rank_trace,
        effective_dimension_multiplier=multiplier,
        effective_dimension_bound=effective_bound,
    )


def frozen_rank_information_bound(
    *,
    horizon: int,
    feature_bound: float,
    rank_bound: int,
    damping: float,
    noise_variance: float,
) -> float:
    r"""Return ``r log(1 + T G^2/(r lambda sigma^2))`` exactly."""

    rounds = _nonnegative_int(horizon, name="horizon")
    rank = _nonnegative_int(rank_bound, name="rank_bound")
    bound = _nonnegative_float(feature_bound, name="feature_bound")
    ridge = _positive_float(damping, name="damping")
    variance = _positive_float(noise_variance, name="noise_variance")
    if rank == 0:
        if rounds == 0 or bound == 0.0:
            return 0.0
        raise ValueError("positive feature trace cannot have rank_bound zero")
    return float(
        rank
        * np.log1p(rounds * bound * bound / (rank * ridge * variance))
    )


@dataclass(frozen=True)
class GrowingWindowComplexityBound:
    horizon: int
    exponent: float
    window_sizes: tuple[int, ...]
    width_squared_bounds: FloatArray
    exact_sum_bound: float
    asymptotic_sum_bound: float
    information_bound: float


def growing_window_complexity_bound(
    *,
    horizon: int,
    exponent: float,
    feature_bound: float,
    damping: float,
    excitation: float,
    noise_variance: float,
) -> GrowingWindowComplexityBound:
    r"""Bound widths and ``Lambda_T`` under certified window excitation.

    The number of available samples is
    ``m_t=min(t-1, ceil(t**q))``.  Round one has no history and is charged by
    ``G^2/lambda``.  For later rounds ``m_t >= (t-1)^q``.
    """

    rounds = _nonnegative_int(horizon, name="horizon")
    q = float(exponent)
    if not np.isfinite(q) or not 0.0 < q <= 1.0:
        raise ValueError("exponent must lie in (0, 1]")
    bound = _nonnegative_float(feature_bound, name="feature_bound")
    ridge = _positive_float(damping, name="damping")
    kappa = _positive_float(excitation, name="excitation")
    variance = _positive_float(noise_variance, name="noise_variance")
    windows: list[int] = []
    widths: list[float] = []
    for round_index in range(1, rounds + 1):
        available = round_index - 1
        window = min(available, int(np.ceil(round_index**q)))
        windows.append(window)
        denominator = ridge if window == 0 else ridge + kappa * window
        widths.append(bound * bound / denominator)
    exact_sum = float(np.sum(widths))
    if rounds == 0:
        asymptotic_sum = 0.0
    elif rounds == 1:
        asymptotic_sum = bound * bound / ridge
    elif q < 1.0:
        harmonic_bound = 1.0 + ((rounds - 1) ** (1.0 - q) - 1.0) / (
            1.0 - q
        )
        asymptotic_sum = bound * bound * (
            1.0 / ridge + harmonic_bound / kappa
        )
    else:
        harmonic_bound = 1.0 + float(np.log(rounds - 1))
        asymptotic_sum = bound * bound * (
            1.0 / ridge + harmonic_bound / kappa
        )
    tolerance = 128.0 * np.finfo(np.float64).eps * max(
        1.0, exact_sum, asymptotic_sum
    )
    if exact_sum > asymptotic_sum + tolerance:
        raise FloatingPointError("growing-window sum exceeded its integral bound")
    width_array = np.asarray(widths, dtype=np.float64)
    information = float(np.sum(np.log1p(width_array / variance)))
    linear_information_bound = exact_sum / variance
    if information > linear_information_bound + tolerance:
        raise FloatingPointError("logarithmic width sum exceeded log(1+x)<=x")
    return GrowingWindowComplexityBound(
        horizon=rounds,
        exponent=q,
        window_sizes=tuple(windows),
        width_squared_bounds=_readonly(width_array),
        exact_sum_bound=exact_sum,
        asymptotic_sum_bound=asymptotic_sum,
        information_bound=linear_information_bound,
    )


def outer_product_perturbation_bound(a: ArrayLike, b: ArrayLike) -> tuple[float, float]:
    r"""Return the two sides of ``||aa' - bb'|| <= (||a||+||b||)||a-b||``."""

    left_vector = _as_float64_array(a, name="a", ndim=1)
    right_vector = _validate_vector(b, left_vector.size, name="b")
    observed = float(
        np.linalg.norm(
            np.outer(left_vector, left_vector)
            - np.outer(right_vector, right_vector),
            ord=2,
        )
    )
    upper = float(
        (np.linalg.norm(left_vector) + np.linalg.norm(right_vector))
        * np.linalg.norm(left_vector - right_vector)
    )
    return observed, upper


@dataclass(frozen=True)
class RelativeRefreshAudit:
    sample_count: int
    observed_relative_norm: float
    observed_perturbation_norm: float
    termwise_perturbation_bound: float
    analytic_relative_bound: float
    active_minimum_eigenvalue: float


def relative_refresh_audit(
    old_features: ArrayLike,
    new_features: ArrayLike,
    current_plus: ArrayLike,
    *,
    active_basis: ArrayLike,
    feature_bound: float,
    jacobian_lipschitz: float,
    parameter_increment: float,
    noise_variance: float,
    active_lower_bound: float,
) -> RelativeRefreshAudit:
    r"""Audit the stable-excitation relative refresh inequality.

    The rows are the same samples evaluated before and after a parameter
    update.  They must lie in the columns of ``active_basis``.  This function
    checks the finite-dimensional premises and reports both the observed norm
    and the analytic upper bound

    ``2 n G L_g ||theta_new-theta_old|| / (sigma^2 active_lower_bound)``.

    The eigendecompositions here are post-hoc diagnostics, not verified
    numerical enclosures and therefore are never exposed to a policy.
    """

    old = _as_float64_array(old_features, name="old_features", ndim=2)
    new = _as_float64_array(new_features, name="new_features", ndim=2)
    if old.shape != new.shape:
        raise ValueError("old_features and new_features must have equal shape")
    if old.shape[0] == 0 or old.shape[1] == 0:
        raise ValueError("feature matrices must have positive shape")
    dimension = old.shape[1]
    operator = _symmetric_matrix(current_plus, name="current_plus")
    if operator.shape != (dimension, dimension):
        raise ValueError("current_plus dimension disagrees with the features")
    basis = _as_float64_array(active_basis, name="active_basis", ndim=2)
    if basis.shape[0] != dimension or basis.shape[1] == 0:
        raise ValueError("active_basis must have shape (dimension, positive rank)")
    gram = basis.T @ basis
    if not np.allclose(gram, np.eye(basis.shape[1]), rtol=1e-11, atol=1e-12):
        raise ValueError("active_basis columns must be orthonormal")

    bound = _nonnegative_float(feature_bound, name="feature_bound")
    lipschitz = _nonnegative_float(
        jacobian_lipschitz, name="jacobian_lipschitz"
    )
    increment = _nonnegative_float(
        parameter_increment, name="parameter_increment"
    )
    variance = _positive_float(noise_variance, name="noise_variance")
    lower = _positive_float(active_lower_bound, name="active_lower_bound")
    tolerance = 512.0 * np.finfo(np.float64).eps * max(1.0, bound)
    row_norms = np.concatenate(
        (np.linalg.norm(old, axis=1), np.linalg.norm(new, axis=1))
    )
    if float(np.max(row_norms)) > bound + tolerance:
        raise ValueError("a feature row exceeds feature_bound")
    differences = np.linalg.norm(new - old, axis=1)
    if float(np.max(differences)) > lipschitz * increment + tolerance:
        raise ValueError("a feature difference exceeds L_g times the increment")
    projector = basis @ basis.T
    support_residual = max(
        float(np.linalg.norm(old @ (np.eye(dimension) - projector), ord=2)),
        float(np.linalg.norm(new @ (np.eye(dimension) - projector), ord=2)),
    )
    if support_residual > tolerance * max(1.0, np.sqrt(old.shape[0])):
        raise ValueError("features are not supported on active_basis")

    active_operator = basis.T @ operator @ basis
    active_eigenvalues, active_eigenvectors = np.linalg.eigh(active_operator)
    observed_minimum = float(active_eigenvalues[0])
    if observed_minimum + tolerance < lower:
        raise ValueError("current_plus violates active_lower_bound")
    if observed_minimum <= 0.0:
        raise ValueError("current_plus is not positive definite on the active subspace")

    perturbation = (new.T @ new - old.T @ old) / variance
    active_perturbation = basis.T @ perturbation @ basis
    inverse_sqrt = (
        active_eigenvectors
        @ np.diag(1.0 / np.sqrt(active_eigenvalues))
        @ active_eigenvectors.T
    )
    relative = inverse_sqrt @ active_perturbation @ inverse_sqrt
    observed_perturbation = float(np.linalg.norm(active_perturbation, ord=2))
    observed_relative = float(np.linalg.norm(relative, ord=2))
    termwise = float(
        np.sum(
            (np.linalg.norm(old, axis=1) + np.linalg.norm(new, axis=1))
            * differences
        )
        / variance
    )
    analytic = float(
        2.0
        * old.shape[0]
        * bound
        * lipschitz
        * increment
        / (variance * lower)
    )
    check_tolerance = 1024.0 * np.finfo(np.float64).eps * max(
        1.0, observed_relative, analytic
    )
    if observed_perturbation > termwise + check_tolerance:
        raise FloatingPointError("outer-product refresh bound was violated")
    if observed_relative > analytic + check_tolerance:
        raise FloatingPointError("relative refresh bound was violated")
    return RelativeRefreshAudit(
        sample_count=old.shape[0],
        observed_relative_norm=observed_relative,
        observed_perturbation_norm=observed_perturbation,
        termwise_perturbation_bound=termwise,
        analytic_relative_bound=analytic,
        active_minimum_eigenvalue=observed_minimum,
    )


def endpoint_rank_trace_logdet_bound(
    endpoint_increment: ArrayLike,
    *,
    damping: float,
    rank_bound: int,
    trace_bound: float,
) -> EndpointRankTraceLogdetResult:
    r"""Bound ``log det(lambda I + A) - log det(lambda I)`` for PSD ``A``.

    The routine checks ``A >= 0``, its positive-eigenvalue rank, and the declared
    trace bound.  Eigenvalues in the same scale-aware backward-error band used
    by the variation helper are numerical zeros.  When ``rank_bound`` is zero,
    PSD plus the numerical-rank check makes both returned sides zero.
    """

    increment = _symmetric_matrix(endpoint_increment, name="endpoint_increment")
    dimension = increment.shape[0]
    ridge = _positive_float(damping, name="damping")
    declared_rank = _nonnegative_int(rank_bound, name="rank_bound")
    if declared_rank > dimension:
        raise ValueError(
            f"rank_bound must not exceed dimension {dimension}, got {declared_rank}"
        )
    declared_trace = _nonnegative_float(trace_bound, name="trace_bound")

    eigenvalues = np.asarray(np.linalg.eigvalsh(increment), dtype=np.float64)
    if not np.all(np.isfinite(eigenvalues)):
        raise FloatingPointError("endpoint increment eigenvalues are non-finite")
    sign_tolerance = _eigenvalue_sign_tolerance(eigenvalues)
    if np.any(eigenvalues < -sign_tolerance):
        raise ValueError("endpoint_increment must be positive semidefinite")
    positive = np.asarray(
        eigenvalues[eigenvalues > sign_tolerance], dtype=np.float64
    )
    positive_rank = int(positive.size)
    numerical_zero_count = dimension - positive_rank
    if positive_rank > declared_rank:
        raise ValueError(
            f"endpoint positive rank {positive_rank} exceeds rank_bound "
            f"{declared_rank}"
        )
    observed_trace = float(np.sum(positive))
    if not np.isfinite(observed_trace):
        raise FloatingPointError("endpoint increment trace is invalid")
    trace_tolerance = dimension * sign_tolerance
    if observed_trace > declared_trace + trace_tolerance:
        raise ValueError(
            f"endpoint trace {observed_trace} exceeds trace_bound {declared_trace}"
        )

    endpoint_logdeterminant = float(
        sum(_log_one_plus_ratio(float(value), ridge) for value in positive)
    )
    if declared_rank == 0 or declared_trace == 0.0:
        upper_bound = 0.0
    else:
        upper_bound = float(
            declared_rank
            * _log_one_plus_ratio(
                declared_trace, float(declared_rank) * ridge
            )
        )
    tolerance = (
        64.0
        * np.finfo(np.float64).eps
        * max(1, dimension)
        * max(1.0, endpoint_logdeterminant, upper_bound)
    )
    if endpoint_logdeterminant > upper_bound + tolerance:
        raise FloatingPointError(
            "computed endpoint log-determinant exceeds its analytic bound"
        )

    return EndpointRankTraceLogdetResult(
        eigenvalues=_readonly(eigenvalues.copy()),
        positive_eigenvalues=_readonly(positive.copy()),
        positive_rank=positive_rank,
        numerical_zero_count=numerical_zero_count,
        rank_bound=declared_rank,
        trace=observed_trace,
        trace_bound=declared_trace,
        damping=ridge,
        eigenvalue_sign_tolerance=sign_tolerance,
        endpoint_logdeterminant=endpoint_logdeterminant,
        upper_bound=upper_bound,
    )


@dataclass(frozen=True)
class DynamicRankTraceBoundResult:
    endpoint: EndpointRankTraceLogdetResult
    transitions: tuple[RankSensitiveVariationResult, ...]
    variation_charge: float
    variation_upper_bound: float
    dynamic_potential: float
    upper_bound: float

    @property
    def slack(self) -> float:
        return self.upper_bound - self.dynamic_potential


def dynamic_rank_trace_upper_bound(
    endpoint_increment: ArrayLike,
    normalized_perturbations: Sequence[ArrayLike],
    *,
    damping: float,
    endpoint_rank_bound: int,
    endpoint_trace_bound: float,
    variation_rank_bounds: Sequence[int],
    variation_nu_bounds: Sequence[float],
) -> DynamicRankTraceBoundResult:
    """Combine the endpoint rank/trace and roundwise variation upper bounds."""

    perturbations = tuple(normalized_perturbations)
    rank_bounds = tuple(variation_rank_bounds)
    nu_bounds = tuple(variation_nu_bounds)
    if len(rank_bounds) != len(perturbations):
        raise ValueError(
            "variation_rank_bounds must have one value per normalized perturbation"
        )
    if len(nu_bounds) != len(perturbations):
        raise ValueError(
            "variation_nu_bounds must have one value per normalized perturbation"
        )

    endpoint = endpoint_rank_trace_logdet_bound(
        endpoint_increment,
        damping=damping,
        rank_bound=endpoint_rank_bound,
        trace_bound=endpoint_trace_bound,
    )
    transitions = tuple(
        rank_sensitive_variation_bound(
            perturbation,
            rank_bound=rank_bound,
            nu=nu,
        )
        for perturbation, rank_bound, nu in zip(
            perturbations, rank_bounds, nu_bounds, strict=True
        )
    )
    variation_charge = float(
        sum(result.variation_charge for result in transitions)
    )
    variation_upper_bound = float(
        sum(result.upper_bound for result in transitions)
    )
    dynamic_potential = endpoint.endpoint_logdeterminant + variation_charge
    upper_bound = endpoint.upper_bound + variation_upper_bound
    tolerance = (
        64.0
        * np.finfo(np.float64).eps
        * max(1, len(transitions), endpoint.eigenvalues.size)
        * max(1.0, dynamic_potential, upper_bound)
    )
    if dynamic_potential > upper_bound + tolerance:
        raise FloatingPointError(
            "computed dynamic potential exceeds the combined analytic bound"
        )
    return DynamicRankTraceBoundResult(
        endpoint=endpoint,
        transitions=transitions,
        variation_charge=variation_charge,
        variation_upper_bound=variation_upper_bound,
        dynamic_potential=dynamic_potential,
        upper_bound=upper_bound,
    )


# Descriptive aliases matching the two constituent inequalities.
variation_rank_bound = rank_sensitive_variation_bound
endpoint_logdet_rank_trace_bound = endpoint_rank_trace_logdet_bound
combined_dynamic_upper_bound = dynamic_rank_trace_upper_bound


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
    """Evaluate both sides of the dynamic width-sum inequality."""

    features = _as_float64_array(
        played_features, name="played_features", ndim=2, copy=True
    )
    lower_eigenvalue_bound = _positive_float(damping, name="damping")
    variance = _positive_float(noise_variance, name="noise_variance")
    metrics = dynamic_logdet_metrics(
        operators, features, noise_variance=variance
    )

    dimension = features.shape[1]
    for index, operator in enumerate(operators[:-1]):
        dense = _materialize_spd(
            operator, dimension=dimension, name=f"operators[{index}]"
        )
        eigenvalues = np.linalg.eigvalsh(dense)
        minimum = float(eigenvalues[0])
        spectral_scale = max(
            1.0,
            abs(lower_eigenvalue_bound),
            abs(float(eigenvalues[-1])),
        )
        # The eigensolver's absolute error scales with the matrix norm and
        # dimension. Rank-one curvature accumulation can therefore place a
        # valid minimum eigenvalue a few ulps below the damping boundary.
        tolerance = (
            512.0
            * np.finfo(np.float64).eps
            * max(1, dimension)
            * spectral_scale
        )
        if minimum < lower_eigenvalue_bound - tolerance:
            raise ValueError(
                f"operators[{index}] has minimum eigenvalue {minimum}, below damping "
                f"{lower_eigenvalue_bound}"
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

    coefficient = variance + bound * bound / lower_eigenvalue_bound
    width_sum = float(np.sum(metrics.widths_squared))
    information_bound = coefficient * metrics.information_complexity
    dynamic_bound = coefficient * metrics.dynamic_potential
    return WidthSumResult(
        width_sum=width_sum,
        feature_bound=bound,
        coefficient=coefficient,
        information_complexity=metrics.information_complexity,
        information_bound=information_bound,
        dynamic_potential=metrics.dynamic_potential,
        dynamic_bound=dynamic_bound,
        dynamic_metrics=metrics,
    )


width_sum_bound = width_sum_inequality


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
    euclidean_norm = float(np.linalg.norm(maximizing_vector))
    if euclidean_norm == 0.0 or not np.isfinite(euclidean_norm):
        raise FloatingPointError("generalized eigenvector has invalid norm")
    maximizing_vector = maximizing_vector / euclidean_norm
    residual = approximate @ maximizing_vector - maximum * (
        reference @ maximizing_vector
    )
    return GeneralizedEigenvalueResult(
        eigenvalues=_readonly(np.asarray(eigenvalues, dtype=np.float64).copy()),
        maximum=maximum,
        maximizing_vector=_readonly(
            np.asarray(maximizing_vector, dtype=np.float64).copy()
        ),
        residual_norm=float(np.linalg.norm(residual)),
    )


def kappa_plus(
    approximate_operator: OperatorLike,
    reference_operator: OperatorLike,
) -> float:
    """Return the exact largest global generalized eigenvalue, without flooring."""

    return generalized_eigenvalues(
        approximate_operator, reference_operator
    ).maximum


exact_global_kappa_plus = kappa_plus
