"""Fixed, float64 curvature operators and a small conjugate-gradient solver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]
Matvec = Callable[[FloatArray], FloatArray]


def _as_float64_array(
    value: ArrayLike,
    *,
    name: str,
    ndim: int,
    copy: bool = False,
) -> FloatArray:
    raw = np.asarray(value)
    if np.iscomplexobj(raw):
        raise TypeError(f"{name} must be real-valued")
    try:
        if copy:
            array = np.array(value, dtype=np.float64, copy=True)
        else:
            array = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise TypeError(f"{name} must be convertible to float64") from error
    if array.ndim != ndim:
        raise ValueError(f"{name} must be {ndim}-dimensional, got shape {array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def _positive_float(value: float, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and strictly positive")
    return result


def _nonnegative_float(value: float, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


def _readonly(array: FloatArray) -> FloatArray:
    array.setflags(write=False)
    return array


def _validate_vector(value: ArrayLike, dimension: int, *, name: str) -> FloatArray:
    vector = _as_float64_array(value, name=name, ndim=1)
    if vector.shape != (dimension,):
        raise ValueError(f"{name} must have shape ({dimension},), got {vector.shape}")
    return vector


@runtime_checkable
class SPDOperator(Protocol):
    """Structural interface used by the solver and metric routines."""

    shape: tuple[int, int]
    dtype: np.dtype[np.float64]

    def matvec(self, vector: ArrayLike) -> FloatArray:
        """Apply the fixed operator to one vector."""

    def to_dense(self) -> FloatArray:
        """Materialize the operator for diagnostics only."""


class DenseSPDLinearOperator:
    """Immutable wrapper that validates a dense matrix as symmetric SPD."""

    def __init__(
        self,
        matrix: ArrayLike,
        *,
        symmetry_rtol: float = 1e-12,
        symmetry_atol: float = 1e-14,
    ) -> None:
        dense = _as_float64_array(matrix, name="matrix", ndim=2, copy=True)
        if dense.shape[0] != dense.shape[1]:
            raise ValueError(f"matrix must be square, got shape {dense.shape}")
        if dense.shape[0] == 0:
            raise ValueError("matrix dimension must be positive")
        if not np.allclose(dense, dense.T, rtol=symmetry_rtol, atol=symmetry_atol):
            asymmetry = float(np.max(np.abs(dense - dense.T)))
            raise ValueError(f"matrix must be symmetric; max asymmetry is {asymmetry}")
        try:
            np.linalg.cholesky(dense)
        except np.linalg.LinAlgError as error:
            raise ValueError("matrix must be positive definite") from error
        self._matrix = _readonly(dense)
        self.shape = dense.shape
        self.dtype = np.dtype(np.float64)

    @property
    def matrix(self) -> FloatArray:
        return self._matrix

    def matvec(self, vector: ArrayLike) -> FloatArray:
        checked = _validate_vector(vector, self.shape[0], name="vector")
        result = np.asarray(self._matrix @ checked, dtype=np.float64)
        if not np.all(np.isfinite(result)):
            raise FloatingPointError(
                "dense operator matvec produced a non-finite value"
            )
        return result

    def __call__(self, vector: ArrayLike) -> FloatArray:
        return self.matvec(vector)

    def to_dense(self) -> FloatArray:
        return self._matrix.copy()


class CurvatureOperator:
    r"""Damped nonnegative weighted outer-product curvature.

    The represented matrix is

    ``damping * I + features.T @ diag(weights) @ features / noise_variance``.

    All state is copied into read-only float64 arrays. Consequently a matvec, and
    every CG solve using it, sees one fixed operator.
    """

    def __init__(
        self,
        features: ArrayLike,
        *,
        damping: float,
        noise_variance: float = 1.0,
        weights: ArrayLike | None = None,
    ) -> None:
        feature_matrix = _as_float64_array(
            features, name="features", ndim=2, copy=True
        )
        sample_count, dimension = feature_matrix.shape
        if dimension == 0:
            raise ValueError("features must have a positive parameter dimension")

        if weights is None:
            weight_vector = np.ones(sample_count, dtype=np.float64)
        else:
            weight_vector = _as_float64_array(
                weights, name="weights", ndim=1, copy=True
            )
            if weight_vector.shape != (sample_count,):
                raise ValueError(
                    f"weights must have shape ({sample_count},), got "
                    f"{weight_vector.shape}"
                )
            if np.any(weight_vector < 0.0):
                raise ValueError("weights must be nonnegative")

        self._features = _readonly(feature_matrix)
        self._weights = _readonly(weight_vector)
        self.damping = _positive_float(damping, name="damping")
        self.noise_variance = _positive_float(
            noise_variance, name="noise_variance"
        )
        self.shape = (dimension, dimension)
        self.dtype = np.dtype(np.float64)

    @property
    def dimension(self) -> int:
        return self.shape[0]

    @property
    def sample_count(self) -> int:
        return self._features.shape[0]

    @property
    def features(self) -> FloatArray:
        return self._features

    @property
    def weights(self) -> FloatArray:
        return self._weights

    def matvec(self, vector: ArrayLike) -> FloatArray:
        checked = _validate_vector(vector, self.dimension, name="vector")
        projections = self._features @ checked
        result = self.damping * checked + (
            self._features.T @ (self._weights * projections)
        ) / self.noise_variance
        result = np.asarray(result, dtype=np.float64)
        if not np.all(np.isfinite(result)):
            raise FloatingPointError("curvature matvec produced a non-finite value")
        return result

    def __call__(self, vector: ArrayLike) -> FloatArray:
        return self.matvec(vector)

    def to_dense(self) -> FloatArray:
        dense = self.damping * np.eye(self.dimension, dtype=np.float64)
        dense += (
            self._features.T @ (self._weights[:, None] * self._features)
        ) / self.noise_variance
        if not np.all(np.isfinite(dense)):
            raise FloatingPointError("dense curvature materialization is non-finite")
        return np.asarray(dense, dtype=np.float64)


class FixedSubsampleCurvatureOperator(CurvatureOperator):
    """A uniformly subsampled curvature whose indices are drawn exactly once."""

    def __init__(
        self,
        features: ArrayLike,
        *,
        damping: float,
        sample_size: int,
        rng: np.random.Generator | int,
        noise_variance: float = 1.0,
        weights: ArrayLike | None = None,
        replace: bool = False,
        rescale: bool = True,
    ) -> None:
        full_features = _as_float64_array(
            features, name="features", ndim=2, copy=True
        )
        full_count = full_features.shape[0]
        if isinstance(sample_size, (bool, np.bool_)) or not isinstance(
            sample_size, (int, np.integer)
        ):
            raise TypeError("sample_size must be an integer")
        sample_size = int(sample_size)
        if sample_size <= 0:
            raise ValueError("sample_size must be positive")
        if full_count == 0:
            raise ValueError("cannot subsample an empty feature matrix")
        if not replace and sample_size > full_count:
            raise ValueError(
                "sample_size cannot exceed the sample count without replacement"
            )

        generator = _coerce_rng(rng)
        indices = np.asarray(
            generator.choice(full_count, size=sample_size, replace=replace),
            dtype=np.int64,
        )

        if weights is None:
            full_weights = np.ones(full_count, dtype=np.float64)
        else:
            full_weights = _as_float64_array(
                weights, name="weights", ndim=1, copy=True
            )
            if full_weights.shape != (full_count,):
                raise ValueError(
                    f"weights must have shape ({full_count},), got {full_weights.shape}"
                )
            if np.any(full_weights < 0.0):
                raise ValueError("weights must be nonnegative")

        scale = float(full_count / sample_size) if rescale else 1.0
        selected_weights = full_weights[indices] * scale
        super().__init__(
            full_features[indices],
            damping=damping,
            noise_variance=noise_variance,
            weights=selected_weights,
        )
        self._sample_indices = indices.copy()
        self._sample_indices.setflags(write=False)
        self.full_sample_count = full_count
        self.rescale_factor = scale
        self.replace = bool(replace)

    @property
    def sample_indices(self) -> NDArray[np.int64]:
        return self._sample_indices


class FixedGaussianSketchCurvatureOperator(CurvatureOperator):
    """A Gaussian feature sketch drawn once and then held fixed for all matvecs."""

    def __init__(
        self,
        features: ArrayLike,
        *,
        damping: float,
        sketch_size: int,
        rng: np.random.Generator | int,
        noise_variance: float = 1.0,
        weights: ArrayLike | None = None,
    ) -> None:
        full_features = _as_float64_array(
            features, name="features", ndim=2, copy=True
        )
        sample_count = full_features.shape[0]
        if isinstance(sketch_size, (bool, np.bool_)) or not isinstance(
            sketch_size, (int, np.integer)
        ):
            raise TypeError("sketch_size must be an integer")
        sketch_size = int(sketch_size)
        if sketch_size <= 0:
            raise ValueError("sketch_size must be positive")
        if sample_count == 0:
            raise ValueError("cannot sketch an empty feature matrix")

        if weights is None:
            weight_vector = np.ones(sample_count, dtype=np.float64)
        else:
            weight_vector = _as_float64_array(
                weights, name="weights", ndim=1, copy=True
            )
            if weight_vector.shape != (sample_count,):
                raise ValueError(
                    f"weights must have shape ({sample_count},), got "
                    f"{weight_vector.shape}"
                )
            if np.any(weight_vector < 0.0):
                raise ValueError("weights must be nonnegative")

        generator = _coerce_rng(rng)
        projection = generator.normal(
            loc=0.0,
            scale=1.0 / np.sqrt(float(sketch_size)),
            size=(sketch_size, sample_count),
        ).astype(np.float64, copy=False)
        weighted_features = np.sqrt(weight_vector)[:, None] * full_features
        sketched_features = projection @ weighted_features
        super().__init__(
            sketched_features,
            damping=damping,
            noise_variance=noise_variance,
        )
        self._projection = _readonly(projection.copy())
        self.source_sample_count = sample_count

    @property
    def projection(self) -> FloatArray:
        return self._projection


def _coerce_rng(rng: np.random.Generator | int) -> np.random.Generator:
    if isinstance(rng, np.random.Generator):
        return rng
    if isinstance(rng, (bool, np.bool_)):
        raise TypeError("rng must be a numpy Generator or an integer seed")
    if isinstance(rng, (int, np.integer)):
        return np.random.default_rng(int(rng))
    raise TypeError("rng must be a numpy Generator or an integer seed")


@dataclass(frozen=True)
class ConjugateGradientResult:
    solution: FloatArray
    converged: bool
    iterations: int
    residual_norm: float
    relative_residual_norm: float
    residual_history: FloatArray


class ConjugateGradientError(RuntimeError):
    """Raised when CG exhausts its iteration budget before meeting tolerance."""

    def __init__(self, message: str, result: ConjugateGradientResult) -> None:
        super().__init__(message)
        self.result = result


OperatorLike = SPDOperator | ArrayLike | Matvec


def _matvec(operator: OperatorLike, vector: FloatArray) -> FloatArray:
    if hasattr(operator, "matvec"):
        result = operator.matvec(vector)  # type: ignore[union-attr]
    elif callable(operator):
        result = operator(vector)
    else:
        dense = _as_float64_array(operator, name="operator", ndim=2)
        result = dense @ vector
    checked = _as_float64_array(result, name="operator result", ndim=1)
    if checked.shape != vector.shape:
        raise ValueError(
            f"operator result must have shape {vector.shape}, got {checked.shape}"
        )
    return checked


def conjugate_gradient(
    operator: OperatorLike,
    right_hand_side: ArrayLike,
    *,
    tolerance: float = 1e-10,
    absolute_tolerance: float = 0.0,
    max_iterations: int | None = None,
    initial_solution: ArrayLike | None = None,
    raise_on_nonconvergence: bool = True,
) -> ConjugateGradientResult:
    """Solve an SPD system using standard CG and one fixed matvec oracle."""

    rhs = _as_float64_array(
        right_hand_side, name="right_hand_side", ndim=1, copy=True
    )
    dimension = rhs.size
    if dimension == 0:
        raise ValueError("right_hand_side must have positive dimension")

    if not hasattr(operator, "matvec") and not callable(operator):
        prepared_operator: OperatorLike = DenseSPDLinearOperator(operator)
    else:
        prepared_operator = operator
        shape = getattr(operator, "shape", None)
        if shape is not None and tuple(shape) != (dimension, dimension):
            raise ValueError(
                f"operator shape must be ({dimension}, {dimension}), got {shape}"
            )

    relative_tolerance = _nonnegative_float(tolerance, name="tolerance")
    absolute_tolerance = _nonnegative_float(
        absolute_tolerance, name="absolute_tolerance"
    )
    if max_iterations is None:
        iteration_limit = dimension
    else:
        if isinstance(max_iterations, (bool, np.bool_)) or not isinstance(
            max_iterations, (int, np.integer)
        ):
            raise TypeError("max_iterations must be an integer")
        iteration_limit = int(max_iterations)
        if iteration_limit < 0:
            raise ValueError("max_iterations must be nonnegative")

    if initial_solution is None:
        solution = np.zeros(dimension, dtype=np.float64)
    else:
        solution = _validate_vector(
            initial_solution, dimension, name="initial_solution"
        ).copy()

    residual = rhs - _matvec(prepared_operator, solution)
    rhs_norm = float(np.linalg.norm(rhs))
    residual_norm = float(np.linalg.norm(residual))
    threshold = max(absolute_tolerance, relative_tolerance * rhs_norm)
    history = [residual_norm]

    if residual_norm <= threshold:
        return _cg_result(solution, True, 0, residual_norm, rhs_norm, history)

    direction = residual.copy()
    residual_squared = float(residual @ residual)
    iterations = 0
    converged = False

    for iterations in range(1, iteration_limit + 1):
        applied_direction = _matvec(prepared_operator, direction)
        direction_curvature = float(direction @ applied_direction)
        if not np.isfinite(direction_curvature) or direction_curvature <= 0.0:
            raise ArithmeticError(
                "CG encountered nonpositive search-direction curvature; "
                "the operator is not a fixed SPD oracle"
            )
        step_size = residual_squared / direction_curvature
        solution = solution + step_size * direction
        residual = residual - step_size * applied_direction
        next_residual_squared = float(residual @ residual)
        if not np.isfinite(next_residual_squared):
            raise FloatingPointError("CG residual became non-finite")
        residual_norm = float(np.sqrt(next_residual_squared))
        history.append(residual_norm)
        if residual_norm <= threshold:
            converged = True
            break
        if residual_squared == 0.0:
            raise ArithmeticError("CG reached a zero denominator before convergence")
        direction = residual + (next_residual_squared / residual_squared) * direction
        residual_squared = next_residual_squared

    result = _cg_result(
        solution, converged, iterations, residual_norm, rhs_norm, history
    )
    if not converged and raise_on_nonconvergence:
        raise ConjugateGradientError(
            f"CG did not converge in {iteration_limit} iterations; "
            f"relative residual is {result.relative_residual_norm}",
            result,
        )
    return result


def _cg_result(
    solution: FloatArray,
    converged: bool,
    iterations: int,
    residual_norm: float,
    rhs_norm: float,
    residual_history: list[float],
) -> ConjugateGradientResult:
    frozen_solution = _readonly(np.asarray(solution, dtype=np.float64).copy())
    frozen_history = _readonly(np.asarray(residual_history, dtype=np.float64))
    relative = residual_norm / rhs_norm if rhs_norm > 0.0 else 0.0
    return ConjugateGradientResult(
        solution=frozen_solution,
        converged=converged,
        iterations=iterations,
        residual_norm=float(residual_norm),
        relative_residual_norm=float(relative),
        residual_history=frozen_history,
    )


# More explicit name for callers that want to emphasize the construction.
WeightedOuterProductCurvature = CurvatureOperator
