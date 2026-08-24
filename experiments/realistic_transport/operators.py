"""Exact and low-rank operators with float64 certificate diagnostics.

The inequalities implemented here are exact-arithmetic statements.  Every
reported certificate is therefore labelled as a float64 exact-arithmetic
certificate diagnostic.  Scale-aware audits fail closed when floating-point
departures are too large to attribute to roundoff.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]
FLOAT64_CERTIFICATE_DIAGNOSTIC: Final = (
    "float64 exact-arithmetic certificate diagnostic"
)


class NumericalAuditError(ArithmeticError):
    """A deterministic numerical invariant failed beyond roundoff tolerance."""

    def __init__(
        self,
        check: str,
        *,
        observed: float,
        tolerance: float,
        detail: str,
    ) -> None:
        self.check = check
        self.observed = float(observed)
        self.tolerance = float(tolerance)
        self.detail = detail
        super().__init__(
            f"{check} failed: {detail}; observed={observed:.17g}, "
            f"scale-aware tolerance={tolerance:.17g}"
        )


@dataclass(frozen=True)
class RoundoffCorrection:
    check: str
    observed: float
    corrected: float
    tolerance: float


@dataclass(frozen=True)
class AuditTolerance:
    """Dimension- and scale-aware float64 audit tolerance."""

    multiplier: float = 4096.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.multiplier) or self.multiplier <= 0.0:
            raise ValueError("multiplier must be finite and strictly positive")

    def bound(self, scale: float, *, dimension: int = 1) -> float:
        checked_scale = abs(float(scale))
        if not math.isfinite(checked_scale):
            raise ValueError("audit scale must be finite")
        if dimension <= 0:
            raise ValueError("audit dimension must be positive")
        effective_scale = max(checked_scale, np.finfo(np.float64).tiny)
        return float(
            self.multiplier
            * np.finfo(np.float64).eps
            * max(1, int(dimension))
            * effective_scale
        )


def _as_float64(
    value: ArrayLike,
    *,
    name: str,
    ndim: int,
    copy: bool = False,
) -> FloatArray:
    if np.iscomplexobj(np.asarray(value)):
        raise TypeError(f"{name} must be real-valued")
    try:
        result = (
            np.array(value, dtype=np.float64, copy=True)
            if copy
            else np.asarray(value, dtype=np.float64)
        )
    except (TypeError, ValueError) as error:
        raise TypeError(f"{name} must be convertible to float64") from error
    if result.ndim != ndim:
        raise ValueError(f"{name} must be {ndim}-dimensional, got {result.shape}")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _readonly(value: FloatArray) -> FloatArray:
    value.setflags(write=False)
    return value


def _positive(value: float, *, name: str) -> float:
    checked = float(value)
    if not math.isfinite(checked) or checked <= 0.0:
        raise ValueError(f"{name} must be finite and strictly positive")
    return checked


def _nonnegative(value: float, *, name: str) -> float:
    checked = float(value)
    if not math.isfinite(checked) or checked < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return checked


def _nonnegative_integer(value: int, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    checked = int(value)
    if checked < 0:
        raise ValueError(f"{name} must be nonnegative")
    return checked


def _matrix_scale(matrix: FloatArray) -> float:
    if matrix.size == 0:
        return 0.0
    return float(np.linalg.norm(matrix, ord=2))


def _euclidean_norm(vector: FloatArray) -> float:
    """Compute a float64 Euclidean norm without avoidable square overflow."""

    if vector.size == 0:
        return 0.0
    maximum = float(np.max(np.abs(vector)))
    if maximum == 0.0:
        return 0.0
    scaled = np.asarray(vector / maximum, dtype=np.float64)
    return float(maximum * math.sqrt(float(scaled @ scaled)))


def _checked_symmetric(
    matrix: ArrayLike,
    *,
    name: str,
    audit: AuditTolerance,
    corrections: list[RoundoffCorrection] | None = None,
) -> FloatArray:
    dense = _as_float64(matrix, name=name, ndim=2, copy=True)
    if dense.shape[0] != dense.shape[1]:
        raise ValueError(f"{name} must be square, got {dense.shape}")
    if dense.shape[0] == 0:
        raise ValueError(f"{name} must have positive dimension")
    asymmetry = float(np.linalg.norm(dense - dense.T, ord=2))
    tolerance = audit.bound(_matrix_scale(dense), dimension=dense.shape[0])
    if asymmetry > tolerance:
        raise NumericalAuditError(
            f"{name}.symmetry",
            observed=asymmetry,
            tolerance=tolerance,
            detail="spectral norm of A - A.T is too large",
        )
    if asymmetry > 0.0 and corrections is not None:
        corrections.append(
            RoundoffCorrection(
                check=f"{name}.symmetry",
                observed=asymmetry,
                corrected=0.0,
                tolerance=tolerance,
            )
        )
    return np.asarray(0.5 * (dense + dense.T), dtype=np.float64)


def _audit_psd(
    matrix: FloatArray,
    *,
    name: str,
    audit: AuditTolerance,
    reference_scale: float | None = None,
) -> tuple[FloatArray, float, float]:
    eigenvalues = np.linalg.eigvalsh(matrix)
    minimum = float(eigenvalues[0])
    scale = _matrix_scale(matrix) if reference_scale is None else reference_scale
    tolerance = audit.bound(scale, dimension=matrix.shape[0])
    if minimum < -tolerance:
        raise NumericalAuditError(
            f"{name}.psd",
            observed=minimum,
            tolerance=tolerance,
            detail="minimum eigenvalue is materially negative",
        )
    return eigenvalues, minimum, tolerance


class DenseSPDOperator:
    """Immutable dense SPD snapshot with explicit matvec accounting."""

    def __init__(
        self,
        matrix: ArrayLike,
        *,
        audit_tolerance: AuditTolerance = AuditTolerance(),
    ) -> None:
        corrections: list[RoundoffCorrection] = []
        dense = _checked_symmetric(
            matrix,
            name="operator",
            audit=audit_tolerance,
            corrections=corrections,
        )
        eigenvalues = np.linalg.eigvalsh(dense)
        minimum = float(eigenvalues[0])
        tolerance = audit_tolerance.bound(
            _matrix_scale(dense), dimension=dense.shape[0]
        )
        if minimum <= 0.0:
            raise NumericalAuditError(
                "operator.positive_definite",
                observed=minimum,
                tolerance=tolerance,
                detail="minimum eigenvalue must be strictly positive",
            )
        try:
            cholesky = np.linalg.cholesky(dense)
        except np.linalg.LinAlgError as error:
            raise NumericalAuditError(
                "operator.cholesky",
                observed=minimum,
                tolerance=tolerance,
                detail="Cholesky factorization rejected the matrix",
            ) from error
        self._matrix = _readonly(dense)
        self._cholesky = _readonly(np.asarray(cholesky, dtype=np.float64))
        self._eigenvalues = _readonly(np.asarray(eigenvalues, dtype=np.float64))
        self._audit_tolerance = audit_tolerance
        self._roundoff_corrections = tuple(corrections)
        self._matvec_count = 0
        self.shape = dense.shape
        self.dtype = np.dtype(np.float64)
        self.fingerprint = hashlib.sha256(dense.tobytes(order="C")).hexdigest()

    @property
    def dimension(self) -> int:
        return self.shape[0]

    @property
    def matvec_count(self) -> int:
        return self._matvec_count

    @property
    def minimum_eigenvalue(self) -> float:
        return float(self._eigenvalues[0])

    @property
    def maximum_eigenvalue(self) -> float:
        return float(self._eigenvalues[-1])

    @property
    def roundoff_corrections(self) -> tuple[RoundoffCorrection, ...]:
        return self._roundoff_corrections

    def matvec(self, vector: ArrayLike) -> FloatArray:
        checked = _as_float64(vector, name="vector", ndim=1)
        if checked.shape != (self.dimension,):
            raise ValueError(
                f"vector must have shape ({self.dimension},), got {checked.shape}"
            )
        self._matvec_count += 1
        result = np.asarray(self._matrix @ checked, dtype=np.float64)
        if not np.all(np.isfinite(result)):
            raise FloatingPointError("operator matvec produced a non-finite value")
        return result

    def solve_cholesky(self, right_hand_side: ArrayLike) -> FloatArray:
        rhs = _as_float64(right_hand_side, name="right_hand_side", ndim=1)
        if rhs.shape != (self.dimension,):
            raise ValueError(
                f"right_hand_side must have shape ({self.dimension},), got {rhs.shape}"
            )
        intermediate = np.linalg.solve(self._cholesky, rhs)
        solution = np.linalg.solve(self._cholesky.T, intermediate)
        if not np.all(np.isfinite(solution)):
            raise FloatingPointError("Cholesky solve produced a non-finite value")
        return np.asarray(solution, dtype=np.float64)

    def to_dense(self) -> FloatArray:
        return self._matrix.copy()


class LowRankRidgeOperator:
    """Immutable ``ridge * I + factor @ factor.T`` operator snapshot."""

    def __init__(self, ridge: float, factor: ArrayLike) -> None:
        self.ridge = _positive(ridge, name="ridge")
        checked = _as_float64(factor, name="factor", ndim=2, copy=True)
        if checked.shape[0] == 0:
            raise ValueError("factor must have positive row dimension")
        self._factor = _readonly(checked)
        self.shape = (checked.shape[0], checked.shape[0])
        self.dtype = np.dtype(np.float64)
        self._matvec_count = 0
        gram = checked.T @ checked
        eigenvalues = np.linalg.eigvalsh(gram) if gram.size else np.empty(0)
        self._maximum_eigenvalue = self.ridge + (
            float(eigenvalues[-1]) if eigenvalues.size else 0.0
        )
        digest = hashlib.sha256()
        digest.update(b"realistic-transport-low-rank-ridge-v1\0")
        digest.update(np.float64(self.ridge).tobytes())
        digest.update(np.asarray(checked.shape, dtype="<i8").tobytes())
        digest.update(checked.tobytes(order="C"))
        self.fingerprint = digest.hexdigest()

    @property
    def dimension(self) -> int:
        return self.shape[0]

    @property
    def rank(self) -> int:
        return int(self._factor.shape[1])

    @property
    def factor(self) -> FloatArray:
        return self._factor

    @property
    def matvec_count(self) -> int:
        return self._matvec_count

    @property
    def minimum_eigenvalue(self) -> float:
        return self.ridge

    @property
    def maximum_eigenvalue(self) -> float:
        return self._maximum_eigenvalue

    @property
    def trace_hessian(self) -> float:
        return float(np.sum(self._factor * self._factor))

    @property
    def storage_bytes(self) -> int:
        return int(self._factor.nbytes + np.dtype(np.float64).itemsize)

    def matvec(self, vector: ArrayLike) -> FloatArray:
        checked = _as_float64(vector, name="vector", ndim=1)
        if checked.shape != (self.dimension,):
            raise ValueError(
                f"vector must have shape ({self.dimension},), got {checked.shape}"
            )
        self._matvec_count += 1
        result = self.ridge * checked
        if self.rank:
            result = result + self._factor @ (self._factor.T @ checked)
        if not np.all(np.isfinite(result)):
            raise FloatingPointError("operator matvec produced a non-finite value")
        return np.asarray(result, dtype=np.float64)

    def solve_cholesky(self, right_hand_side: ArrayLike) -> FloatArray:
        """Solve exactly up to float64 roundoff using the Woodbury identity."""

        rhs = _as_float64(right_hand_side, name="right_hand_side", ndim=1)
        if rhs.shape != (self.dimension,):
            raise ValueError(
                f"right_hand_side must have shape ({self.dimension},), got {rhs.shape}"
            )
        solution = rhs / self.ridge
        if self.rank:
            small = np.eye(self.rank, dtype=np.float64)
            small += (self._factor.T @ self._factor) / self.ridge
            correction = np.linalg.solve(small, self._factor.T @ rhs)
            solution = solution - self._factor @ correction / (self.ridge**2)
        if not np.all(np.isfinite(solution)):
            raise FloatingPointError("Woodbury solve produced a non-finite value")
        return np.asarray(solution, dtype=np.float64)

    def to_dense(self) -> FloatArray:
        return np.asarray(
            self.ridge * np.eye(self.dimension, dtype=np.float64)
            + self._factor @ self._factor.T,
            dtype=np.float64,
        )


FixedSPDOperator = DenseSPDOperator | LowRankRidgeOperator
DenseOperatorLike = FixedSPDOperator | ArrayLike


def _coerce_operator(
    operator: DenseOperatorLike,
    *,
    audit_tolerance: AuditTolerance,
) -> FixedSPDOperator:
    if isinstance(operator, (DenseSPDOperator, LowRankRidgeOperator)):
        return operator
    if callable(operator) or hasattr(operator, "matvec"):
        raise TypeError(
            "fixed-operator CG accepts a dense matrix or DenseSPDOperator snapshot, "
            "not a mutable/callable operator"
        )
    return DenseSPDOperator(operator, audit_tolerance=audit_tolerance)


def _generalized_eigenvalues(
    numerator: FloatArray,
    denominator: FloatArray,
) -> FloatArray:
    cholesky = np.linalg.cholesky(denominator)
    left = np.linalg.solve(cholesky, numerator)
    normalized = np.linalg.solve(cholesky, left.T).T
    normalized = np.asarray(0.5 * (normalized + normalized.T), dtype=np.float64)
    return np.asarray(np.linalg.eigvalsh(normalized), dtype=np.float64)


@dataclass(frozen=True)
class OperatorFactorDiagnostics:
    operational_kappa_minus_trace: float
    operational_kappa_plus: float
    diagnostic_kappa_minus_operator_tail: float
    diagnostic_generalized_kappa_minus: float
    diagnostic_generalized_kappa_plus: float
    trace_tail: float
    operator_tail: float
    trace_tail_over_operator_tail: float | None
    certificate_class: str = FLOAT64_CERTIFICATE_DIAGNOSTIC


@dataclass(frozen=True)
class OperationalNystromApproximation:
    """Low-rank Nyström state used by the policy before action selection."""

    operator: LowRankRidgeOperator
    factor: FloatArray
    sketch: FloatArray
    sketch_digest: str
    sketch_seed: int | None
    target_rank: int
    numerical_rank: int
    sketch_size: int
    pseudoinverse_cutoff: float
    pseudoinverse_rank: int
    ridge: float
    exact_trace: float
    retained_trace: float
    trace_tail: float
    operational_kappa_minus: float
    operational_kappa_plus: float
    retained_trace_fraction: float | None
    construction_seconds: float
    operator_storage_bytes: int
    working_storage_bytes: int
    roundoff_corrections: tuple[RoundoffCorrection, ...]
    certificate_class: str = FLOAT64_CERTIFICATE_DIAGNOSTIC


@dataclass(frozen=True)
class NystromCheckpointDiagnostics:
    operator_tail: float
    trace_tail_over_operator_tail: float | None
    oracle_kappa_minus_operator_tail: float
    oracle_generalized_kappa_minus: float
    oracle_generalized_kappa_plus: float
    effective_rank: float
    spectral_tail_fraction: float | None
    decomposition_error_norm: float
    elapsed_seconds: float
    certificate_class: str = FLOAT64_CERTIFICATE_DIAGNOSTIC


def build_operational_nystrom(
    replay_gradients: ArrayLike,
    *,
    target_rank: int,
    ridge: float,
    sketch_seed: int | None = None,
    sketch: ArrayLike | None = None,
    oversampling: int = 8,
    pseudoinverse_multiplier: float = 64.0,
    audit_tolerance: AuditTolerance = AuditTolerance(),
) -> OperationalNystromApproximation:
    """Build a low-rank Nyström operator without materializing ``J.T @ J``."""

    started = time.perf_counter()
    gradients = _as_float64(
        replay_gradients, name="replay_gradients", ndim=2, copy=True
    )
    sample_count, dimension = gradients.shape
    if dimension == 0:
        raise ValueError("replay_gradients must have positive column dimension")
    rank = _nonnegative_integer(target_rank, name="target_rank")
    if rank > dimension:
        raise ValueError(f"target_rank must not exceed parameter dimension {dimension}")
    oversample = _nonnegative_integer(oversampling, name="oversampling")
    if (sketch_seed is None) == (sketch is None):
        raise ValueError("supply exactly one of sketch_seed or sketch")
    checked_ridge = _positive(ridge, name="ridge")
    pinv_multiplier = _positive(
        pseudoinverse_multiplier, name="pseudoinverse_multiplier"
    )
    corrections: list[RoundoffCorrection] = []
    supplied_sketch: FloatArray | None = None
    checked_seed: int | None = None
    if sketch_seed is not None:
        if isinstance(sketch_seed, (bool, np.bool_)) or not isinstance(
            sketch_seed, (int, np.integer)
        ):
            raise TypeError("sketch_seed must be an integer")
        checked_seed = int(sketch_seed)
        if checked_seed < 0:
            raise ValueError("sketch_seed must be nonnegative")
    else:
        supplied_sketch = _as_float64(sketch, name="sketch", ndim=2, copy=True)
        if supplied_sketch.shape[0] != dimension:
            raise ValueError(
                f"sketch must have {dimension} rows, got {supplied_sketch.shape}"
            )
        if supplied_sketch.shape[1] < rank:
            raise ValueError("sketch must have at least target_rank columns")

    sketch_size = (
        supplied_sketch.shape[1]
        if supplied_sketch is not None
        else min(dimension, rank + oversample)
    )
    if supplied_sketch is None:
        assert checked_seed is not None
        generator = np.random.Generator(np.random.PCG64(checked_seed))
        frozen_sketch = np.asarray(
            generator.standard_normal((dimension, sketch_size)), dtype=np.float64
        )
    else:
        frozen_sketch = supplied_sketch

    if sketch_size == 0 or sample_count == 0:
        basis = np.empty((sample_count, 0), dtype=np.float64)
        pinv_cutoff = 0.0
        pinv_rank = 0
    else:
        sampled_range = np.asarray(gradients @ frozen_sketch, dtype=np.float64)
        left_vectors, singular_values, _ = np.linalg.svd(
            sampled_range, full_matrices=False
        )
        largest_gram_eigenvalue = (
            float(singular_values[0] ** 2) if singular_values.size else 0.0
        )
        pinv_cutoff = float(
            pinv_multiplier
            * np.finfo(np.float64).eps
            * max(sampled_range.shape)
            * largest_gram_eigenvalue
        )
        retained = singular_values * singular_values > pinv_cutoff
        pinv_rank = int(np.count_nonzero(retained))
        basis = np.asarray(left_vectors[:, retained], dtype=np.float64)

    compressed = np.asarray(basis.T @ gradients, dtype=np.float64)
    if compressed.size:
        _, singular_values, right_vectors_t = np.linalg.svd(
            compressed, full_matrices=False
        )
    else:
        singular_values = np.empty(0, dtype=np.float64)
        right_vectors_t = np.empty((0, dimension), dtype=np.float64)
    keep = min(rank, singular_values.size)
    kept_values = np.asarray(singular_values[:keep], dtype=np.float64)
    factor = np.asarray(
        right_vectors_t[:keep].T * kept_values[np.newaxis, :], dtype=np.float64
    )
    exact_trace = float(np.sum(gradients * gradients))
    retained_trace = float(kept_values @ kept_values)
    trace_tail = exact_trace - retained_trace
    tolerance = audit_tolerance.bound(exact_trace, dimension=dimension)
    if trace_tail < -tolerance:
        raise NumericalAuditError(
            "nystrom.trace_tail",
            observed=trace_tail,
            tolerance=tolerance,
            detail="retained trace materially exceeds exact trace",
        )
    if trace_tail < 0.0:
        corrections.append(
            RoundoffCorrection(
                check="nystrom.trace_tail",
                observed=trace_tail,
                corrected=0.0,
                tolerance=tolerance,
            )
        )
        trace_tail = 0.0
    operator = LowRankRidgeOperator(checked_ridge, factor)
    frozen_sketch = _readonly(frozen_sketch.copy())
    factor = operator.factor
    sketch_digest = hashlib.sha256(frozen_sketch.tobytes(order="C")).hexdigest()
    return OperationalNystromApproximation(
        operator=operator,
        factor=factor,
        sketch=frozen_sketch,
        sketch_digest=sketch_digest,
        sketch_seed=checked_seed,
        target_rank=rank,
        numerical_rank=int(np.count_nonzero(kept_values > math.sqrt(tolerance))),
        sketch_size=sketch_size,
        pseudoinverse_cutoff=pinv_cutoff,
        pseudoinverse_rank=pinv_rank,
        ridge=checked_ridge,
        exact_trace=exact_trace,
        retained_trace=retained_trace,
        trace_tail=trace_tail,
        operational_kappa_minus=checked_ridge / (checked_ridge + trace_tail),
        operational_kappa_plus=1.0,
        retained_trace_fraction=(
            retained_trace / exact_trace if exact_trace > 0.0 else None
        ),
        construction_seconds=float(time.perf_counter() - started),
        operator_storage_bytes=operator.storage_bytes,
        working_storage_bytes=int(
            operator.storage_bytes + frozen_sketch.nbytes + basis.nbytes
        ),
        roundoff_corrections=tuple(corrections),
    )


def diagnose_operational_nystrom(
    approximation: OperationalNystromApproximation,
    replay_gradients: ArrayLike,
    *,
    audit_tolerance: AuditTolerance = AuditTolerance(),
) -> NystromCheckpointDiagnostics:
    """Run dense oracle audits for a frozen operational approximation."""

    started = time.perf_counter()
    gradients = _as_float64(replay_gradients, name="replay_gradients", ndim=2)
    if gradients.shape[1] != approximation.operator.dimension:
        raise ValueError("replay gradients do not match the approximation dimension")
    exact_hessian = np.asarray(gradients.T @ gradients, dtype=np.float64)
    approximate_hessian = np.asarray(
        approximation.factor @ approximation.factor.T, dtype=np.float64
    )
    residual = np.asarray(exact_hessian - approximate_hessian, dtype=np.float64)
    residual = np.asarray(0.5 * (residual + residual.T), dtype=np.float64)
    residual_eigenvalues, _, _ = _audit_psd(
        residual,
        name="operational_nystrom.residual",
        audit=audit_tolerance,
        reference_scale=_matrix_scale(exact_hessian),
    )
    operator_tail = float(max(0.0, residual_eigenvalues[-1]))
    trace_tail = approximation.trace_tail
    trace_tolerance = audit_tolerance.bound(
        max(1.0, trace_tail), dimension=approximation.operator.dimension
    )
    trace_residual = abs(float(np.trace(residual)) - trace_tail)
    if trace_residual > trace_tolerance:
        raise NumericalAuditError(
            "operational_nystrom.trace_identity",
            observed=trace_residual,
            tolerance=trace_tolerance,
            detail="dense residual trace disagrees with the operational trace tail",
        )
    exact_operator = np.asarray(
        approximation.ridge * np.eye(approximation.operator.dimension) + exact_hessian,
        dtype=np.float64,
    )
    generalized = _generalized_eigenvalues(
        approximation.operator.to_dense(), exact_operator
    )
    sandwich_tolerance = audit_tolerance.bound(
        1.0, dimension=approximation.operator.dimension
    )
    if generalized[0] < approximation.operational_kappa_minus - sandwich_tolerance:
        raise NumericalAuditError(
            "operational_nystrom.lower_sandwich",
            observed=float(approximation.operational_kappa_minus - generalized[0]),
            tolerance=sandwich_tolerance,
            detail="operational kappa_minus exceeds the exact generalized factor",
        )
    if generalized[-1] > 1.0 + sandwich_tolerance:
        raise NumericalAuditError(
            "operational_nystrom.upper_sandwich",
            observed=float(generalized[-1] - 1.0),
            tolerance=sandwich_tolerance,
            detail="low-rank operator is not below the exact current metric",
        )
    exact_eigenvalues = np.linalg.eigvalsh(exact_hessian)
    exact_norm = float(max(0.0, exact_eigenvalues[-1]))
    effective_rank = approximation.exact_trace / exact_norm if exact_norm > 0.0 else 0.0
    return NystromCheckpointDiagnostics(
        operator_tail=operator_tail,
        trace_tail_over_operator_tail=(
            trace_tail / operator_tail if operator_tail > 0.0 else None
        ),
        oracle_kappa_minus_operator_tail=(
            approximation.ridge / (approximation.ridge + operator_tail)
        ),
        oracle_generalized_kappa_minus=float(generalized[0]),
        oracle_generalized_kappa_plus=float(generalized[-1]),
        effective_rank=float(effective_rank),
        spectral_tail_fraction=(
            operator_tail / exact_norm if exact_norm > 0.0 else None
        ),
        decomposition_error_norm=float(
            np.linalg.norm(exact_hessian - (approximate_hessian + residual), ord=2)
        ),
        elapsed_seconds=float(time.perf_counter() - started),
    )


@dataclass(frozen=True)
class NystromApproximation:
    exact_hessian: FloatArray
    untruncated_hessian: FloatArray
    approximate_hessian: FloatArray
    residual_hessian: FloatArray
    algorithm_operator: FloatArray
    exact_current_operator: FloatArray
    sketch: FloatArray
    sketch_digest: str
    sketch_seed: int | None
    target_rank: int
    numerical_rank: int
    sketch_size: int
    pseudoinverse_cutoff: float
    pseudoinverse_rank: int
    ridge: float
    effective_rank: float
    retained_trace_fraction: float | None
    spectral_tail_fraction: float | None
    decomposition_error_norm: float
    operator_storage_bytes: int
    construction_seconds: float
    factors: OperatorFactorDiagnostics
    roundoff_corrections: tuple[RoundoffCorrection, ...]
    certificate_class: str = FLOAT64_CERTIFICATE_DIAGNOSTIC


def build_nystrom_approximation(
    replay_gradients: ArrayLike,
    *,
    target_rank: int,
    ridge: float,
    sketch_seed: int | None = None,
    sketch: ArrayLike | None = None,
    oversampling: int = 8,
    pseudoinverse_multiplier: float = 64.0,
    audit_tolerance: AuditTolerance = AuditTolerance(),
) -> NystromApproximation:
    """Build a PSD Nyström replay-curvature approximation.

    ``replay_gradients`` is the matrix J whose rows already include the noise
    scaling.  The implementation uses the projector identity

        H Omega (Omega.T H Omega)^dagger Omega.T H = J.T P_(J Omega) J,

    which is algebraically identical to the requested Nyström formula and is
    more stable than multiplying an explicit pseudoinverse.
    """

    started = time.perf_counter()
    gradients = _as_float64(
        replay_gradients, name="replay_gradients", ndim=2, copy=True
    )
    sample_count, dimension = gradients.shape
    if dimension == 0:
        raise ValueError("replay_gradients must have positive column dimension")
    rank = _nonnegative_integer(target_rank, name="target_rank")
    if rank > dimension:
        raise ValueError(f"target_rank must not exceed parameter dimension {dimension}")
    oversample = _nonnegative_integer(oversampling, name="oversampling")
    if (sketch_seed is None) == (sketch is None):
        raise ValueError("supply exactly one of sketch_seed or sketch")
    checked_seed: int | None
    supplied_sketch: FloatArray | None
    if sketch_seed is not None:
        if isinstance(sketch_seed, (bool, np.bool_)) or not isinstance(
            sketch_seed, (int, np.integer)
        ):
            raise TypeError("sketch_seed must be an integer")
        checked_seed = int(sketch_seed)
        if checked_seed < 0:
            raise ValueError("sketch_seed must be nonnegative")
        supplied_sketch = None
    else:
        checked_seed = None
        supplied_sketch = _as_float64(sketch, name="sketch", ndim=2, copy=True)
        if supplied_sketch.shape[0] != dimension:
            raise ValueError(
                f"sketch must have {dimension} rows, got {supplied_sketch.shape}"
            )
        if supplied_sketch.shape[1] < rank:
            raise ValueError(
                "sketch must have at least target_rank columns when supplied"
            )
    checked_ridge = _positive(ridge, name="ridge")
    pinv_multiplier = _positive(
        pseudoinverse_multiplier, name="pseudoinverse_multiplier"
    )
    corrections: list[RoundoffCorrection] = []

    exact_hessian = np.asarray(gradients.T @ gradients, dtype=np.float64)
    exact_hessian = _checked_symmetric(
        exact_hessian,
        name="exact_hessian",
        audit=audit_tolerance,
        corrections=corrections,
    )
    _audit_psd(
        exact_hessian,
        name="exact_hessian",
        audit=audit_tolerance,
    )

    sketch_size = (
        supplied_sketch.shape[1]
        if supplied_sketch is not None
        else min(dimension, rank + oversample)
    )
    if sketch_size == 0:
        sketch = np.empty((dimension, 0), dtype=np.float64)
        basis = np.empty((sample_count, 0), dtype=np.float64)
        pinv_cutoff = 0.0
        pinv_rank = 0
    else:
        if supplied_sketch is None:
            assert checked_seed is not None
            generator = np.random.Generator(np.random.PCG64(checked_seed))
            sketch = np.asarray(
                generator.standard_normal((dimension, sketch_size)), dtype=np.float64
            )
        else:
            sketch = supplied_sketch
        sampled_range = np.asarray(gradients @ sketch, dtype=np.float64)
        if sample_count == 0:
            basis = np.empty((0, 0), dtype=np.float64)
            pinv_cutoff = 0.0
            pinv_rank = 0
        else:
            left_vectors, singular_values, _ = np.linalg.svd(
                sampled_range, full_matrices=False
            )
            largest_gram_eigenvalue = (
                float(singular_values[0] ** 2) if singular_values.size else 0.0
            )
            pinv_cutoff = float(
                pinv_multiplier
                * np.finfo(np.float64).eps
                * max(sampled_range.shape)
                * largest_gram_eigenvalue
            )
            retained = singular_values * singular_values > pinv_cutoff
            pinv_rank = int(np.count_nonzero(retained))
            basis = np.asarray(left_vectors[:, retained], dtype=np.float64)

    projected_gradients = np.asarray(basis.T @ gradients, dtype=np.float64)
    raw_untruncated = np.asarray(
        projected_gradients.T @ projected_gradients, dtype=np.float64
    )
    raw_untruncated = _checked_symmetric(
        raw_untruncated,
        name="untruncated_hessian",
        audit=audit_tolerance,
        corrections=corrections,
    )
    eigenvalues, eigenvectors = np.linalg.eigh(raw_untruncated)
    psd_tolerance = audit_tolerance.bound(
        _matrix_scale(raw_untruncated), dimension=dimension
    )
    minimum_untruncated = float(eigenvalues[0])
    if minimum_untruncated < -psd_tolerance:
        raise NumericalAuditError(
            "untruncated_hessian.psd",
            observed=minimum_untruncated,
            tolerance=psd_tolerance,
            detail="Nyström projector produced material negative curvature",
        )
    negative = eigenvalues < 0.0
    if np.any(negative):
        corrections.append(
            RoundoffCorrection(
                check="untruncated_hessian.negative_eigenvalues",
                observed=minimum_untruncated,
                corrected=0.0,
                tolerance=psd_tolerance,
            )
        )
        eigenvalues = np.maximum(eigenvalues, 0.0)

    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]
    keep_count = min(rank, dimension)
    kept_values = eigenvalues[:keep_count]
    kept_vectors = eigenvectors[:, :keep_count]
    discarded_values = eigenvalues[keep_count:]
    discarded_vectors = eigenvectors[:, keep_count:]
    approximate = np.asarray(
        (kept_vectors * kept_values) @ kept_vectors.T, dtype=np.float64
    )
    discarded = np.asarray(
        (discarded_vectors * discarded_values) @ discarded_vectors.T,
        dtype=np.float64,
    )
    untruncated = np.asarray(approximate + discarded, dtype=np.float64)

    projection_residual = np.asarray(
        gradients - basis @ projected_gradients, dtype=np.float64
    )
    residual = np.asarray(
        projection_residual.T @ projection_residual + discarded,
        dtype=np.float64,
    )
    approximate = _checked_symmetric(
        approximate,
        name="approximate_hessian",
        audit=audit_tolerance,
        corrections=corrections,
    )
    residual = _checked_symmetric(
        residual,
        name="residual_hessian",
        audit=audit_tolerance,
        corrections=corrections,
    )
    approximate_eigenvalues, _, _ = _audit_psd(
        approximate,
        name="approximate_hessian",
        audit=audit_tolerance,
    )
    residual_eigenvalues, _, _ = _audit_psd(
        residual,
        name="residual_hessian",
        audit=audit_tolerance,
    )

    reconstructed = np.asarray(approximate + residual, dtype=np.float64)
    decomposition_error = float(np.linalg.norm(exact_hessian - reconstructed, ord=2))
    decomposition_tolerance = audit_tolerance.bound(
        _matrix_scale(exact_hessian), dimension=dimension
    )
    if decomposition_error > decomposition_tolerance:
        raise NumericalAuditError(
            "nystrom.decomposition",
            observed=decomposition_error,
            tolerance=decomposition_tolerance,
            detail="H differs materially from H_r + E_r",
        )

    raw_loewner_residual = np.asarray(exact_hessian - approximate, dtype=np.float64)
    raw_loewner_residual = np.asarray(
        0.5 * (raw_loewner_residual + raw_loewner_residual.T), dtype=np.float64
    )
    _, loewner_minimum, loewner_tolerance = _audit_psd(
        raw_loewner_residual,
        name="exact_minus_approximate_hessian",
        audit=audit_tolerance,
        reference_scale=_matrix_scale(exact_hessian),
    )
    if loewner_minimum < 0.0:
        corrections.append(
            RoundoffCorrection(
                check="exact_minus_approximate_hessian.minimum_eigenvalue",
                observed=loewner_minimum,
                corrected=0.0,
                tolerance=loewner_tolerance,
            )
        )

    trace_tail = float(np.sum(residual_eigenvalues))
    operator_tail = float(max(0.0, residual_eigenvalues[-1]))
    trace_tolerance = audit_tolerance.bound(
        _matrix_scale(residual), dimension=dimension
    )
    if trace_tail < 0.0:
        if trace_tail < -trace_tolerance:
            raise NumericalAuditError(
                "residual_hessian.trace",
                observed=trace_tail,
                tolerance=trace_tolerance,
                detail="trace tail is materially negative",
            )
        corrections.append(
            RoundoffCorrection(
                check="residual_hessian.trace",
                observed=trace_tail,
                corrected=0.0,
                tolerance=trace_tolerance,
            )
        )
        trace_tail = 0.0

    trace_tail_slack = np.asarray(
        trace_tail * np.eye(dimension, dtype=np.float64) - residual,
        dtype=np.float64,
    )
    _audit_psd(
        trace_tail_slack,
        name="trace_tail_upper_bound",
        audit=audit_tolerance,
    )

    identity = np.eye(dimension, dtype=np.float64)
    algorithm_operator = np.asarray(
        checked_ridge * identity + approximate, dtype=np.float64
    )
    exact_operator = np.asarray(
        checked_ridge * identity + exact_hessian, dtype=np.float64
    )
    generalized = _generalized_eigenvalues(algorithm_operator, exact_operator)
    generalized_minimum = float(generalized[0])
    generalized_maximum = float(generalized[-1])
    trace_kappa = checked_ridge / (checked_ridge + trace_tail)
    operator_kappa = checked_ridge / (checked_ridge + operator_tail)

    lower_slack = np.asarray(
        algorithm_operator - trace_kappa * exact_operator, dtype=np.float64
    )
    upper_slack = np.asarray(exact_operator - algorithm_operator, dtype=np.float64)
    _audit_psd(
        np.asarray(0.5 * (lower_slack + lower_slack.T)),
        name="operational_lower_sandwich",
        audit=audit_tolerance,
        reference_scale=_matrix_scale(exact_operator),
    )
    _, upper_minimum, upper_tolerance = _audit_psd(
        np.asarray(0.5 * (upper_slack + upper_slack.T)),
        name="operational_upper_sandwich",
        audit=audit_tolerance,
        reference_scale=_matrix_scale(exact_operator),
    )
    if upper_minimum < 0.0:
        corrections.append(
            RoundoffCorrection(
                check="operational_upper_sandwich.minimum_eigenvalue",
                observed=upper_minimum,
                corrected=0.0,
                tolerance=upper_tolerance,
            )
        )

    exact_trace = float(np.trace(exact_hessian))
    approximate_trace = float(np.sum(approximate_eigenvalues))
    exact_operator_norm = float(max(0.0, np.linalg.eigvalsh(exact_hessian)[-1]))
    effective_rank = (
        exact_trace / exact_operator_norm if exact_operator_norm > 0.0 else 0.0
    )
    retained_trace_fraction = (
        approximate_trace / exact_trace if exact_trace > 0.0 else None
    )
    spectral_tail_fraction = (
        operator_tail / exact_operator_norm if exact_operator_norm > 0.0 else None
    )
    trace_over_operator = trace_tail / operator_tail if operator_tail > 0.0 else None
    numerical_rank = int(np.count_nonzero(kept_values > psd_tolerance))
    sketch = _readonly(np.asarray(sketch, dtype=np.float64).copy())
    sketch_digest = hashlib.sha256(sketch.tobytes(order="C")).hexdigest()

    return NystromApproximation(
        exact_hessian=_readonly(exact_hessian.copy()),
        untruncated_hessian=_readonly(untruncated.copy()),
        approximate_hessian=_readonly(approximate.copy()),
        residual_hessian=_readonly(residual.copy()),
        algorithm_operator=_readonly(algorithm_operator.copy()),
        exact_current_operator=_readonly(exact_operator.copy()),
        sketch=sketch,
        sketch_digest=sketch_digest,
        sketch_seed=checked_seed,
        target_rank=rank,
        numerical_rank=numerical_rank,
        sketch_size=sketch_size,
        pseudoinverse_cutoff=pinv_cutoff,
        pseudoinverse_rank=pinv_rank,
        ridge=checked_ridge,
        effective_rank=float(effective_rank),
        retained_trace_fraction=(
            float(retained_trace_fraction)
            if retained_trace_fraction is not None
            else None
        ),
        spectral_tail_fraction=(
            float(spectral_tail_fraction)
            if spectral_tail_fraction is not None
            else None
        ),
        decomposition_error_norm=decomposition_error,
        operator_storage_bytes=int(algorithm_operator.nbytes),
        construction_seconds=float(time.perf_counter() - started),
        factors=OperatorFactorDiagnostics(
            operational_kappa_minus_trace=float(trace_kappa),
            operational_kappa_plus=1.0,
            diagnostic_kappa_minus_operator_tail=float(operator_kappa),
            diagnostic_generalized_kappa_minus=generalized_minimum,
            diagnostic_generalized_kappa_plus=generalized_maximum,
            trace_tail=trace_tail,
            operator_tail=operator_tail,
            trace_tail_over_operator_tail=(
                float(trace_over_operator) if trace_over_operator is not None else None
            ),
        ),
        roundoff_corrections=tuple(corrections),
    )


@dataclass(frozen=True)
class ConjugateGradientResult:
    solution: FloatArray
    true_residual: FloatArray
    recursive_residual: FloatArray
    residual_history: FloatArray
    converged: bool
    termination_reason: str
    iterations: int
    algorithm_matvec_count: int
    audit_matvec_count: int
    total_matvec_count: int
    right_hand_side_norm: float
    threshold: float
    true_residual_norm: float
    recursive_residual_norm: float
    relative_true_residual_norm: float
    residual_discrepancy_norm: float
    operator_fingerprint: str
    elapsed_seconds: float
    certificate_class: str = FLOAT64_CERTIFICATE_DIAGNOSTIC


class ConjugateGradientError(RuntimeError):
    def __init__(self, message: str, result: ConjugateGradientResult) -> None:
        self.result = result
        super().__init__(message)


def conjugate_gradient_fixed(
    operator: DenseOperatorLike,
    right_hand_side: ArrayLike,
    *,
    relative_tolerance: float = 1e-10,
    absolute_tolerance: float = 0.0,
    max_iterations: int | None = None,
    initial_solution: ArrayLike | None = None,
    raise_on_nonconvergence: bool = True,
    audit_tolerance: AuditTolerance = AuditTolerance(),
) -> ConjugateGradientResult:
    """Solve one immutable dense SPD snapshot with standard CG."""

    started = time.perf_counter()
    prepared = _coerce_operator(operator, audit_tolerance=audit_tolerance)
    fingerprint = prepared.fingerprint
    rhs = _as_float64(right_hand_side, name="right_hand_side", ndim=1, copy=True)
    if rhs.shape != (prepared.dimension,):
        raise ValueError(
            f"right_hand_side must have shape ({prepared.dimension},), got {rhs.shape}"
        )
    rel_tol = _nonnegative(relative_tolerance, name="relative_tolerance")
    abs_tol = _nonnegative(absolute_tolerance, name="absolute_tolerance")
    if max_iterations is None:
        iteration_limit = prepared.dimension
    else:
        iteration_limit = _nonnegative_integer(max_iterations, name="max_iterations")
    if initial_solution is None:
        solution = np.zeros(prepared.dimension, dtype=np.float64)
    else:
        solution = _as_float64(
            initial_solution, name="initial_solution", ndim=1, copy=True
        )
        if solution.shape != (prepared.dimension,):
            raise ValueError(
                f"initial_solution must have shape ({prepared.dimension},), "
                f"got {solution.shape}"
            )

    initial_matvec_count = prepared.matvec_count
    recursive_residual = np.asarray(rhs - prepared.matvec(solution), dtype=np.float64)
    rhs_norm = _euclidean_norm(rhs)
    threshold = max(abs_tol, rel_tol * rhs_norm)
    recursive_norm = _euclidean_norm(recursive_residual)
    residual_history = [recursive_norm]
    iterations = 0
    recurrence_converged = recursive_norm <= threshold
    termination_reason = (
        "initial_residual" if recurrence_converged else "iteration_limit"
    )

    if not recurrence_converged and iteration_limit > 0:
        direction = recursive_residual.copy()
        residual_squared = float(recursive_residual @ recursive_residual)
        for iterations in range(1, iteration_limit + 1):
            applied_direction = prepared.matvec(direction)
            curvature = float(direction @ applied_direction)
            curvature_scale = _euclidean_norm(direction) * _euclidean_norm(
                applied_direction
            )
            curvature_tolerance = audit_tolerance.bound(
                curvature_scale, dimension=prepared.dimension
            )
            if not math.isfinite(curvature) or curvature <= 0.0:
                raise NumericalAuditError(
                    "cg.search_direction_curvature",
                    observed=curvature,
                    tolerance=curvature_tolerance,
                    detail="fixed SPD operator produced nonpositive curvature",
                )
            step = residual_squared / curvature
            solution = np.asarray(solution + step * direction, dtype=np.float64)
            recursive_residual = np.asarray(
                recursive_residual - step * applied_direction, dtype=np.float64
            )
            next_residual_squared = float(recursive_residual @ recursive_residual)
            if not math.isfinite(next_residual_squared) or next_residual_squared < 0.0:
                raise FloatingPointError("CG recursive residual became invalid")
            recursive_norm = float(math.sqrt(next_residual_squared))
            residual_history.append(recursive_norm)
            if recursive_norm <= threshold:
                recurrence_converged = True
                termination_reason = "recursive_residual"
                break
            direction = np.asarray(
                recursive_residual
                + (next_residual_squared / residual_squared) * direction,
                dtype=np.float64,
            )
            residual_squared = next_residual_squared

    algorithm_matvec_count = prepared.matvec_count - initial_matvec_count
    applied_solution = prepared.matvec(solution)
    true_residual = np.asarray(rhs - applied_solution, dtype=np.float64)
    audit_matvec_count = 1
    true_norm = _euclidean_norm(true_residual)
    recursive_norm = _euclidean_norm(recursive_residual)
    discrepancy = _euclidean_norm(true_residual - recursive_residual)
    converged = true_norm <= threshold
    if recurrence_converged and not converged:
        termination_reason = "recomputed_residual_above_tolerance"
    elif converged and termination_reason == "iteration_limit":
        termination_reason = "recomputed_residual"
    if prepared.fingerprint != fingerprint:
        raise RuntimeError("operator snapshot changed during CG")

    result = ConjugateGradientResult(
        solution=_readonly(solution.copy()),
        true_residual=_readonly(true_residual.copy()),
        recursive_residual=_readonly(recursive_residual.copy()),
        residual_history=_readonly(np.asarray(residual_history, dtype=np.float64)),
        converged=converged,
        termination_reason=termination_reason,
        iterations=iterations,
        algorithm_matvec_count=algorithm_matvec_count,
        audit_matvec_count=audit_matvec_count,
        total_matvec_count=algorithm_matvec_count + audit_matvec_count,
        right_hand_side_norm=rhs_norm,
        threshold=threshold,
        true_residual_norm=true_norm,
        recursive_residual_norm=recursive_norm,
        relative_true_residual_norm=(true_norm / rhs_norm if rhs_norm > 0.0 else 0.0),
        residual_discrepancy_norm=discrepancy,
        operator_fingerprint=fingerprint,
        elapsed_seconds=float(time.perf_counter() - started),
    )
    if not converged and raise_on_nonconvergence:
        raise ConjugateGradientError(
            f"CG did not meet the recomputed-residual target in "
            f"{iteration_limit} iterations",
            result,
        )
    return result


@dataclass(frozen=True)
class CertifiedWidth:
    query: FloatArray
    solution: FloatArray
    upper_width: float
    lower_width: float
    sharpness_factor: float
    energy_norm: float
    residual_error_bound: float
    lower_eigenvalue_bound: float
    upper_eigenvalue_bound: float
    cg: ConjugateGradientResult
    roundoff_corrections: tuple[RoundoffCorrection, ...]
    certificate_class: str = FLOAT64_CERTIFICATE_DIAGNOSTIC


def _audit_spectral_bounds(
    operator: FixedSPDOperator,
    *,
    lower_bound: float,
    upper_bound: float,
    audit: AuditTolerance,
) -> None:
    scale = max(abs(lower_bound), abs(upper_bound), operator.maximum_eigenvalue)
    tolerance = audit.bound(scale, dimension=operator.dimension)
    lower_shortfall = lower_bound - operator.minimum_eigenvalue
    if lower_shortfall > tolerance:
        raise NumericalAuditError(
            "operator.lower_eigenvalue_bound",
            observed=lower_shortfall,
            tolerance=tolerance,
            detail="declared lower bound exceeds the diagnostic minimum eigenvalue",
        )
    upper_shortfall = operator.maximum_eigenvalue - upper_bound
    if upper_shortfall > tolerance:
        raise NumericalAuditError(
            "operator.upper_eigenvalue_bound",
            observed=upper_shortfall,
            tolerance=tolerance,
            detail="declared upper bound is below the diagnostic maximum eigenvalue",
        )


def certify_cg_width(
    operator: DenseOperatorLike,
    query: ArrayLike,
    *,
    lower_eigenvalue_bound: float,
    upper_eigenvalue_bound: float,
    relative_tolerance: float,
    absolute_tolerance: float = 0.0,
    max_iterations: int | None = None,
    initial_solution: ArrayLike | None = None,
    require_convergence: bool = False,
    audit_tolerance: AuditTolerance = AuditTolerance(),
) -> CertifiedWidth:
    """Return the n+e upper width and pre-reward lower width for one query."""

    prepared = _coerce_operator(operator, audit_tolerance=audit_tolerance)
    lower_bound = _positive(lower_eigenvalue_bound, name="lower_eigenvalue_bound")
    upper_bound = _positive(upper_eigenvalue_bound, name="upper_eigenvalue_bound")
    if upper_bound < lower_bound:
        raise ValueError("upper_eigenvalue_bound must be at least the lower bound")
    _audit_spectral_bounds(
        prepared,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        audit=audit_tolerance,
    )
    checked_query = _as_float64(query, name="query", ndim=1, copy=True)
    if checked_query.shape != (prepared.dimension,):
        raise ValueError(
            f"query must have shape ({prepared.dimension},), got {checked_query.shape}"
        )
    cg = conjugate_gradient_fixed(
        prepared,
        checked_query,
        relative_tolerance=relative_tolerance,
        absolute_tolerance=absolute_tolerance,
        max_iterations=max_iterations,
        initial_solution=initial_solution,
        raise_on_nonconvergence=require_convergence,
        audit_tolerance=audit_tolerance,
    )
    corrections: list[RoundoffCorrection] = []
    applied_solution = np.asarray(checked_query - cg.true_residual, dtype=np.float64)
    energy_squared = float(cg.solution @ applied_solution)
    energy_scale = _euclidean_norm(cg.solution) * _euclidean_norm(applied_solution)
    energy_tolerance = audit_tolerance.bound(energy_scale, dimension=prepared.dimension)
    if energy_squared < -energy_tolerance:
        raise NumericalAuditError(
            "width.iterate_energy",
            observed=energy_squared,
            tolerance=energy_tolerance,
            detail="x.T A x is materially negative",
        )
    if energy_squared < 0.0:
        corrections.append(
            RoundoffCorrection(
                check="width.iterate_energy",
                observed=energy_squared,
                corrected=0.0,
                tolerance=energy_tolerance,
            )
        )
        energy_squared = 0.0
    energy_norm = float(math.sqrt(energy_squared))
    error_bound = float(cg.true_residual_norm / math.sqrt(lower_bound))
    upper_width = float(energy_norm + error_bound)
    query_norm = _euclidean_norm(checked_query)
    if query_norm == 0.0:
        lower_width = 0.0
        sharpness = 1.0
        upper_width = 0.0
    else:
        lower_width = float(
            max(
                0.0,
                energy_norm - error_bound,
                query_norm / math.sqrt(upper_bound),
            )
        )
        if lower_width <= 0.0:
            raise NumericalAuditError(
                "width.positive_lower_bound",
                observed=lower_width,
                tolerance=0.0,
                detail="nonzero query must have a positive spectral lower width",
            )
        sharpness = float(upper_width / lower_width)
    return CertifiedWidth(
        query=_readonly(checked_query.copy()),
        solution=cg.solution,
        upper_width=upper_width,
        lower_width=lower_width,
        sharpness_factor=sharpness,
        energy_norm=energy_norm,
        residual_error_bound=error_bound,
        lower_eigenvalue_bound=lower_bound,
        upper_eigenvalue_bound=upper_bound,
        cg=cg,
        roundoff_corrections=tuple(corrections),
    )


@dataclass(frozen=True)
class CertifiedWidthMap:
    certificates: tuple[CertifiedWidth, ...]
    upper_widths: FloatArray
    lower_widths: FloatArray
    sharpness_factors: FloatArray
    total_iterations: int
    total_algorithm_matvec_count: int
    total_audit_matvec_count: int
    operator_fingerprint: str
    certificate_class: str = FLOAT64_CERTIFICATE_DIAGNOSTIC

    def selected(self, action: int) -> CertifiedWidth:
        if isinstance(action, (bool, np.bool_)) or not isinstance(
            action, (int, np.integer)
        ):
            raise TypeError("action must be an integer")
        checked = int(action)
        if not 0 <= checked < len(self.certificates):
            raise IndexError("action is outside the width map")
        return self.certificates[checked]


def certify_cg_width_map(
    operator: DenseOperatorLike,
    queries: ArrayLike,
    *,
    lower_eigenvalue_bound: float,
    upper_eigenvalue_bound: float,
    relative_tolerance: float,
    absolute_tolerance: float = 0.0,
    max_iterations: int | None = None,
    require_convergence: bool = False,
    audit_tolerance: AuditTolerance = AuditTolerance(),
) -> CertifiedWidthMap:
    """Compute one immutable all-action width map with no refinement path."""

    prepared = _coerce_operator(operator, audit_tolerance=audit_tolerance)
    checked_queries = _as_float64(queries, name="queries", ndim=2, copy=True)
    if checked_queries.shape[1:] != (prepared.dimension,):
        raise ValueError(
            f"queries must have shape (action_count, {prepared.dimension}), "
            f"got {checked_queries.shape}"
        )
    certificates = tuple(
        certify_cg_width(
            prepared,
            query,
            lower_eigenvalue_bound=lower_eigenvalue_bound,
            upper_eigenvalue_bound=upper_eigenvalue_bound,
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
            max_iterations=max_iterations,
            require_convergence=require_convergence,
            audit_tolerance=audit_tolerance,
        )
        for query in checked_queries
    )
    fingerprints = {item.cg.operator_fingerprint for item in certificates}
    if fingerprints != {prepared.fingerprint}:
        raise RuntimeError("all-action solves did not use one fixed operator snapshot")
    return CertifiedWidthMap(
        certificates=certificates,
        upper_widths=_readonly(
            np.asarray([item.upper_width for item in certificates], dtype=np.float64)
        ),
        lower_widths=_readonly(
            np.asarray([item.lower_width for item in certificates], dtype=np.float64)
        ),
        sharpness_factors=_readonly(
            np.asarray(
                [item.sharpness_factor for item in certificates], dtype=np.float64
            )
        ),
        total_iterations=sum(item.cg.iterations for item in certificates),
        total_algorithm_matvec_count=sum(
            item.cg.algorithm_matvec_count for item in certificates
        ),
        total_audit_matvec_count=sum(
            item.cg.audit_matvec_count for item in certificates
        ),
        operator_fingerprint=prepared.fingerprint,
    )


def exact_inverse_width(
    operator: DenseOperatorLike,
    query: ArrayLike,
    *,
    audit_tolerance: AuditTolerance = AuditTolerance(),
) -> float:
    prepared = _coerce_operator(operator, audit_tolerance=audit_tolerance)
    checked_query = _as_float64(query, name="query", ndim=1)
    if checked_query.shape != (prepared.dimension,):
        raise ValueError(
            f"query must have shape ({prepared.dimension},), got {checked_query.shape}"
        )
    solution = prepared.solve_cholesky(checked_query)
    squared_width = float(checked_query @ solution)
    scale = _euclidean_norm(checked_query) * _euclidean_norm(solution)
    tolerance = audit_tolerance.bound(scale, dimension=prepared.dimension)
    if squared_width < -tolerance:
        raise NumericalAuditError(
            "exact_width.nonnegative",
            observed=squared_width,
            tolerance=tolerance,
            detail="q.T A^-1 q is materially negative",
        )
    return float(math.sqrt(max(0.0, squared_width)))


def exact_widths(
    operator: DenseOperatorLike,
    queries: ArrayLike,
    *,
    audit_tolerance: AuditTolerance = AuditTolerance(),
) -> FloatArray:
    """Return dense Cholesky widths for a fixed all-action query matrix."""

    prepared = _coerce_operator(operator, audit_tolerance=audit_tolerance)
    checked_queries = _as_float64(queries, name="queries", ndim=2, copy=True)
    if checked_queries.shape[1:] != (prepared.dimension,):
        raise ValueError(
            f"queries must have shape (action_count, {prepared.dimension}), "
            f"got {checked_queries.shape}"
        )
    squared = np.asarray(
        [float(query @ prepared.solve_cholesky(query)) for query in checked_queries],
        dtype=np.float64,
    )
    if squared.size == 0:
        return _readonly(squared)
    scale = float(np.max(np.abs(squared)))
    tolerance = audit_tolerance.bound(scale, dimension=prepared.dimension)
    minimum = float(np.min(squared))
    if minimum < -tolerance:
        raise NumericalAuditError(
            "exact_widths.nonnegative",
            observed=minimum,
            tolerance=tolerance,
            detail="an all-action q.T A^-1 q value is materially negative",
        )
    return _readonly(np.sqrt(np.maximum(squared, 0.0)))


def thompson_distance(
    reference_operator: DenseOperatorLike,
    current_operator: DenseOperatorLike,
    *,
    audit_tolerance: AuditTolerance = AuditTolerance(),
) -> float:
    """Return max_i |log lambda_i(current, reference)| for dense SPD inputs."""

    reference = _coerce_operator(reference_operator, audit_tolerance=audit_tolerance)
    current = _coerce_operator(current_operator, audit_tolerance=audit_tolerance)
    if current.shape != reference.shape:
        raise ValueError(
            f"operator shapes must match, got {reference.shape} and {current.shape}"
        )
    eigenvalues = _generalized_eigenvalues(current.to_dense(), reference.to_dense())
    if np.any(eigenvalues <= 0.0) or not np.all(np.isfinite(eigenvalues)):
        raise NumericalAuditError(
            "thompson_distance.generalized_eigenvalues",
            observed=float(np.min(eigenvalues)),
            tolerance=0.0,
            detail="SPD generalized eigenvalues must be finite and positive",
        )
    return float(np.max(np.abs(np.log(eigenvalues))))


def build_nystrom(
    replay_gradients: ArrayLike,
    rank: int,
    sketch: int | ArrayLike,
    *,
    ridge: float,
    oversampling: int = 8,
    pseudoinverse_multiplier: float = 64.0,
    audit_tolerance: AuditTolerance = AuditTolerance(),
) -> NystromApproximation:
    """Compact benchmark-facing Nyström API accepting a seed or fixed sketch."""

    if isinstance(sketch, (int, np.integer)) and not isinstance(
        sketch, (bool, np.bool_)
    ):
        return build_nystrom_approximation(
            replay_gradients,
            target_rank=rank,
            sketch_seed=int(sketch),
            ridge=ridge,
            oversampling=oversampling,
            pseudoinverse_multiplier=pseudoinverse_multiplier,
            audit_tolerance=audit_tolerance,
        )
    return build_nystrom_approximation(
        replay_gradients,
        target_rank=rank,
        sketch=sketch,
        ridge=ridge,
        oversampling=oversampling,
        pseudoinverse_multiplier=pseudoinverse_multiplier,
        audit_tolerance=audit_tolerance,
    )


def certified_cg_widths(
    operator: DenseOperatorLike,
    queries: ArrayLike,
    *,
    lower_eigenvalue_bound: float,
    upper_eigenvalue_bound: float,
    rel_tol: float,
    max_iterations: int | None,
    absolute_tolerance: float = 0.0,
    require_convergence: bool = False,
    audit_tolerance: AuditTolerance = AuditTolerance(),
) -> CertifiedWidthMap:
    """Benchmark-facing alias for the fixed all-action certified width map."""

    return certify_cg_width_map(
        operator,
        queries,
        lower_eigenvalue_bound=lower_eigenvalue_bound,
        upper_eigenvalue_bound=upper_eigenvalue_bound,
        relative_tolerance=rel_tol,
        absolute_tolerance=absolute_tolerance,
        max_iterations=max_iterations,
        require_convergence=require_convergence,
        audit_tolerance=audit_tolerance,
    )


@dataclass(frozen=True)
class ExactWidthDiagnostic:
    exact_width: float
    certified_upper_width: float
    certified_lower_width: float
    certified_sharpness_factor: float
    upper_over_exact: float | None
    exact_over_lower: float | None
    sharpness_slack: float | None
    elapsed_seconds: float
    certificate_class: str = FLOAT64_CERTIFICATE_DIAGNOSTIC


def diagnose_exact_width(
    operator: DenseOperatorLike,
    certificate: CertifiedWidth,
    *,
    audit_tolerance: AuditTolerance = AuditTolerance(),
) -> ExactWidthDiagnostic:
    """Compare an operational certificate with an oracle Cholesky width."""

    started = time.perf_counter()
    prepared = _coerce_operator(operator, audit_tolerance=audit_tolerance)
    if prepared.fingerprint != certificate.cg.operator_fingerprint:
        raise ValueError("certificate belongs to a different operator snapshot")
    exact = exact_inverse_width(
        prepared, certificate.query, audit_tolerance=audit_tolerance
    )
    scale = max(exact, certificate.upper_width, certificate.lower_width)
    tolerance = audit_tolerance.bound(scale, dimension=prepared.dimension)
    upper_shortfall = exact - certificate.upper_width
    if upper_shortfall > tolerance:
        raise NumericalAuditError(
            "width.upper_certificate",
            observed=upper_shortfall,
            tolerance=tolerance,
            detail="certified upper width is below the exact width",
        )
    lower_excess = certificate.lower_width - exact
    if lower_excess > tolerance:
        raise NumericalAuditError(
            "width.lower_certificate",
            observed=lower_excess,
            tolerance=tolerance,
            detail="certified lower width is above the exact width",
        )
    if exact == 0.0:
        upper_over_exact = None
        exact_over_lower = None
        sharpness_slack = None
    else:
        upper_over_exact = certificate.upper_width / exact
        exact_over_lower = (
            exact / certificate.lower_width if certificate.lower_width > 0.0 else None
        )
        realized_inflation = certificate.upper_width / exact
        sharpness_slack = certificate.sharpness_factor - realized_inflation
        sharpness_tolerance = audit_tolerance.bound(
            max(
                1.0,
                abs(certificate.sharpness_factor),
                abs(realized_inflation),
            ),
            dimension=prepared.dimension,
        )
        if sharpness_slack < -sharpness_tolerance:
            raise NumericalAuditError(
                "width.sharpness_factor",
                observed=sharpness_slack,
                tolerance=sharpness_tolerance,
                detail="alpha does not upper-bound realized width inflation",
            )
    return ExactWidthDiagnostic(
        exact_width=exact,
        certified_upper_width=certificate.upper_width,
        certified_lower_width=certificate.lower_width,
        certified_sharpness_factor=certificate.sharpness_factor,
        upper_over_exact=(
            float(upper_over_exact) if upper_over_exact is not None else None
        ),
        exact_over_lower=(
            float(exact_over_lower) if exact_over_lower is not None else None
        ),
        sharpness_slack=(
            float(sharpness_slack) if sharpness_slack is not None else None
        ),
        elapsed_seconds=float(time.perf_counter() - started),
    )


__all__ = [
    "FLOAT64_CERTIFICATE_DIAGNOSTIC",
    "AuditTolerance",
    "CertifiedWidth",
    "CertifiedWidthMap",
    "ConjugateGradientError",
    "ConjugateGradientResult",
    "DenseSPDOperator",
    "ExactWidthDiagnostic",
    "FixedSPDOperator",
    "FloatArray",
    "LowRankRidgeOperator",
    "NumericalAuditError",
    "NystromCheckpointDiagnostics",
    "NystromApproximation",
    "OperationalNystromApproximation",
    "OperatorFactorDiagnostics",
    "RoundoffCorrection",
    "build_nystrom",
    "build_nystrom_approximation",
    "build_operational_nystrom",
    "certified_cg_widths",
    "certify_cg_width",
    "certify_cg_width_map",
    "conjugate_gradient_fixed",
    "diagnose_exact_width",
    "diagnose_operational_nystrom",
    "exact_inverse_width",
    "exact_widths",
    "thompson_distance",
]
