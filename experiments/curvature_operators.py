"""Validated dense SPD operators and conjugate gradient for the linear audit."""

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
    if np.iscomplexobj(np.asarray(value)):
        raise TypeError(f"{name} must be real-valued")
    try:
        array = (
            np.array(value, dtype=np.float64, copy=True)
            if copy
            else np.asarray(value, dtype=np.float64)
        )
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
    shape: tuple[int, int]
    dtype: np.dtype[np.float64]

    def matvec(self, vector: ArrayLike) -> FloatArray: ...

    def to_dense(self) -> FloatArray: ...


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

    def matvec(self, vector: ArrayLike) -> FloatArray:
        checked = _validate_vector(vector, self.shape[0], name="vector")
        result = np.asarray(self._matrix @ checked, dtype=np.float64)
        if not np.all(np.isfinite(result)):
            raise FloatingPointError("dense operator matvec produced a non-finite value")
        return result

    def to_dense(self) -> FloatArray:
        return self._matrix.copy()


OperatorLike = SPDOperator | ArrayLike | Matvec


def _matvec(operator: OperatorLike, vector: FloatArray) -> FloatArray:
    if hasattr(operator, "matvec"):
        result = operator.matvec(vector)  # type: ignore[union-attr]
    elif callable(operator):
        result = operator(vector)
    else:
        result = _as_float64_array(operator, name="operator", ndim=2) @ vector
    checked = _as_float64_array(result, name="operator result", ndim=1)
    if checked.shape != vector.shape:
        raise ValueError(
            f"operator result must have shape {vector.shape}, got {checked.shape}"
        )
    return checked


@dataclass(frozen=True)
class ConjugateGradientResult:
    solution: FloatArray
    converged: bool
    iterations: int
    residual_norm: float
    relative_residual_norm: float
    residual_history: FloatArray


class ConjugateGradientError(RuntimeError):
    def __init__(self, message: str, result: ConjugateGradientResult) -> None:
        super().__init__(message)
        self.result = result


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
    """Solve a fixed SPD system with standard conjugate gradient."""

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
    elif isinstance(max_iterations, (bool, np.bool_)) or not isinstance(
        max_iterations, (int, np.integer)
    ):
        raise TypeError("max_iterations must be an integer")
    else:
        iteration_limit = int(max_iterations)
        if iteration_limit < 0:
            raise ValueError("max_iterations must be nonnegative")

    solution = (
        np.zeros(dimension, dtype=np.float64)
        if initial_solution is None
        else _validate_vector(initial_solution, dimension, name="initial_solution").copy()
    )
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
    relative = residual_norm / rhs_norm if rhs_norm > 0.0 else 0.0
    return ConjugateGradientResult(
        solution=_readonly(np.asarray(solution, dtype=np.float64).copy()),
        converged=converged,
        iterations=iterations,
        residual_norm=float(residual_norm),
        relative_residual_norm=float(relative),
        residual_history=_readonly(np.asarray(residual_history, dtype=np.float64)),
    )


__all__ = [
    "ConjugateGradientError",
    "ConjugateGradientResult",
    "DenseSPDLinearOperator",
    "FloatArray",
    "OperatorLike",
    "SPDOperator",
    "conjugate_gradient",
]
