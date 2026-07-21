"""Synthetic systems scaling benchmark for curvature exploration methods.

The benchmark intentionally uses feasible CPU grids rather than pretending to
instantiate the foundation models listed in the protocol.  Its ``last_layer``
baseline is an explicit restriction: it solves the exact curvature system on
the final contiguous coordinate block and sets every preceding coordinate to
zero, thereby discarding backbone directions and cross-block curvature.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import scipy.linalg as la
from numpy.typing import ArrayLike, NDArray

from .config import get_seed_set, load_config
from .logging_utils import ExperimentLogger, append_jsonl, derive_seed, seed_everything
from .run_cg_accuracy import relative_energy_error


FloatArray = NDArray[np.float64]

METHODS = (
    "dense_exact",
    "full_cg",
    "diagonal",
    "lanczos",
    "last_layer_block",
    "batched_cg",
    "batched_jacobi_cg",
)
METHOD_ALIASES = {
    "dense_exact": "dense_exact",
    "full_cg": "full_cg",
    "full_ggn_cg": "full_cg",
    "diagonal": "diagonal",
    "lanczos": "lanczos",
    "lanczos_ritz": "lanczos",
    "last_layer": "last_layer_block",
    "last_layer_block": "last_layer_block",
    "batched_cg": "batched_cg",
    "batched_full_cg": "batched_cg",
    "batched_jacobi_cg": "batched_jacobi_cg",
}

SMOKE_GRID: dict[str, tuple[int, ...]] = {
    "d": (32, 64),
    "n": (16, 64),
    "K": (3, 5),
    "I": (5, 15),
}
FULL_GRID: dict[str, tuple[int, ...]] = {
    "d": (32, 64, 128),
    "n": (32, 128, 512),
    "K": (5, 10),
    "I": (5, 15, 30),
}
ADVANCED_CPU_GRID: dict[str, tuple[int, ...]] = {
    "d": (512, 2048, 8192),
    "n": (32,),
    "K": (4,),
    "I": (16,),
}

BENCHMARK_KIND = "synthetic_cpu_parameter_vector_operator_benchmark"

LAST_LAYER_RESTRICTION = (
    "Exact solve on the final contiguous coordinate block; coordinates before "
    "the block and all cross-block curvature are discarded."
)

DEFAULT_CONFIG: dict[str, Any] = {
    "name": "systems_scaling",
    "profile": "smoke",
    "benchmark_kind": BENCHMARK_KIND,
    "timing_repetitions": 1,
    "cg_relative_tolerance": 1e-10,
    "curvature": {"damping": 1.0},
    "advanced_cpu_grid": {"enabled": False},
    "last_layer_fraction": 0.25,
    "provenance": {"packages": ["numpy", "scipy"]},
}


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _nonnegative_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def _positive_float(value: Any, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _nonnegative_float(value: Any, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


def _rss_bytes() -> int:
    try:
        with open("/proc/self/statm", encoding="ascii") as stream:
            pages = int(stream.read().split()[1])
        return pages * int(os.sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError, IndexError, AttributeError):
        try:
            import psutil  # type: ignore[import-not-found]

            return int(psutil.Process().memory_info().rss)
        except (ImportError, OSError):
            return 0


def _peak_host_memory_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


class CurvatureOperator:
    """Float64 ``damping*I + features.T@features/n`` operator."""

    def __init__(self, features: ArrayLike, damping: float) -> None:
        checked = np.asarray(features, dtype=np.float64)
        if checked.ndim != 2 or checked.shape[0] == 0 or checked.shape[1] == 0:
            raise ValueError("features must be a nonempty matrix")
        if not np.all(np.isfinite(checked)):
            raise ValueError("features must be finite")
        self.features = checked.copy()
        self.damping = _positive_float(damping, name="damping")
        self.sample_count, self.dimension = self.features.shape
        self.shape = (self.dimension, self.dimension)
        self.dtype = np.dtype(np.float64)

    def matvec(self, vector: ArrayLike) -> FloatArray:
        checked = np.asarray(vector, dtype=np.float64)
        if checked.shape != (self.dimension,):
            raise ValueError(f"vector must have shape ({self.dimension},)")
        return np.asarray(
            self.damping * checked
            + self.features.T @ (self.features @ checked) / self.sample_count,
            dtype=np.float64,
        )

    def matmat(self, vectors: ArrayLike) -> FloatArray:
        """Apply the operator to row-oriented vectors in one shared batch."""

        checked = np.asarray(vectors, dtype=np.float64)
        if (
            checked.ndim != 2
            or checked.shape[1] != self.dimension
            or not np.all(np.isfinite(checked))
        ):
            raise ValueError(
                f"vectors must be a finite matrix with shape (batch, {self.dimension})"
            )
        return np.asarray(
            self.damping * checked
            + (checked @ self.features.T) @ self.features / self.sample_count,
            dtype=np.float64,
        )

    def diagonal(self) -> FloatArray:
        diagonal = self.damping + np.sum(self.features**2, axis=0) / self.sample_count
        if np.any(diagonal <= 0.0) or not np.all(np.isfinite(diagonal)):
            raise ArithmeticError("curvature diagonal must be finite and positive")
        return np.asarray(diagonal, dtype=np.float64)

    def to_dense(self) -> FloatArray:
        return np.asarray(
            self.damping * np.eye(self.dimension, dtype=np.float64)
            + self.features.T @ self.features / self.sample_count,
            dtype=np.float64,
        )


@dataclass(frozen=True)
class FixedCGResult:
    solution: FloatArray
    iterations: int
    operator_matvecs: int
    relative_residual: float


@dataclass(frozen=True)
class BatchedCGResult:
    solutions: FloatArray
    per_action_iterations: NDArray[np.int64]
    per_action_operator_matvecs: NDArray[np.int64]
    explicit_relative_residuals: FloatArray
    converged: NDArray[np.bool_]
    batch_operator_calls: int
    equivalent_operator_matvecs: int
    preconditioner: str


def batched_independent_cg(
    operator: CurvatureOperator,
    right_hand_sides: ArrayLike,
    iterations: int,
    *,
    relative_tolerance: float = 1e-10,
    absolute_tolerance: float = 0.0,
    preconditioner: str = "none",
) -> BatchedCGResult:
    """Run independent CG recurrences with shared row-batched operator calls.

    ``preconditioner="symmetric_jacobi"`` is standard PCG with the positive
    Jacobi diagonal, equivalently CG on ``D^-1/2 C D^-1/2``. Candidate stopping
    decisions and all returned residuals are checked explicitly in the original
    system ``B - X C``; recurrence residuals are never reported as final checks.
    """

    budget = _positive_int(iterations, name="iterations")
    relative = _nonnegative_float(relative_tolerance, name="relative_tolerance")
    absolute = _nonnegative_float(absolute_tolerance, name="absolute_tolerance")
    if preconditioner not in {"none", "symmetric_jacobi"}:
        raise ValueError(f"unknown preconditioner {preconditioner!r}")
    rhs = np.asarray(right_hand_sides, dtype=np.float64)
    if (
        rhs.ndim != 2
        or rhs.shape[0] == 0
        or rhs.shape[1] != operator.dimension
        or not np.all(np.isfinite(rhs))
    ):
        raise ValueError(
            "right_hand_sides must be a nonempty finite (actions, dimension) matrix"
        )

    action_count, dimension = rhs.shape
    diagonal = (
        operator.diagonal()
        if preconditioner == "symmetric_jacobi"
        else np.ones(dimension, dtype=np.float64)
    )
    solutions = np.zeros_like(rhs)
    residuals = rhs.copy()
    preconditioned = residuals / diagonal[None, :]
    directions = preconditioned.copy()
    rho = np.einsum("kd,kd->k", residuals, preconditioned)
    rhs_norms = np.linalg.norm(rhs, axis=1)
    thresholds = np.maximum(absolute, relative * rhs_norms)
    active = rhs_norms > thresholds
    per_action_iterations = np.zeros(action_count, dtype=np.int64)
    per_action_matvecs = np.zeros(action_count, dtype=np.int64)
    batch_calls = 0
    equivalent_matvecs = 0

    def apply(indices: NDArray[np.int64], vectors: FloatArray) -> FloatArray:
        nonlocal batch_calls, equivalent_matvecs
        if indices.size == 0:
            return np.empty((0, dimension), dtype=np.float64)
        result = operator.matmat(vectors)
        batch_calls += 1
        equivalent_matvecs += int(indices.size)
        per_action_matvecs[indices] += 1
        return result

    for _ in range(budget):
        indices = np.flatnonzero(active).astype(np.int64, copy=False)
        if not indices.size:
            break
        old_rho = rho[indices].copy()
        if np.any(old_rho <= 0.0) or not np.all(np.isfinite(old_rho)):
            raise ArithmeticError("CG encountered invalid preconditioned residual norm")
        applied = apply(indices, directions[indices])
        curvatures = np.einsum("kd,kd->k", directions[indices], applied)
        if np.any(curvatures <= 0.0) or not np.all(np.isfinite(curvatures)):
            raise ArithmeticError("CG encountered nonpositive direction curvature")
        steps = old_rho / curvatures
        solutions[indices] += steps[:, None] * directions[indices]
        residuals[indices] -= steps[:, None] * applied
        per_action_iterations[indices] += 1

        recurrence_norms = np.linalg.norm(residuals[indices], axis=1)
        candidate_indices = indices[
            recurrence_norms <= thresholds[indices]
        ]
        restart = np.zeros(action_count, dtype=bool)
        if candidate_indices.size:
            explicit = rhs[candidate_indices] - apply(
                candidate_indices, solutions[candidate_indices]
            )
            residuals[candidate_indices] = explicit
            explicit_norms = np.linalg.norm(explicit, axis=1)
            verified = candidate_indices[
                explicit_norms <= thresholds[candidate_indices]
            ]
            active[verified] = False
            failed = candidate_indices[
                explicit_norms > thresholds[candidate_indices]
            ]
            restart[failed] = True

        remaining = indices[active[indices]]
        if not remaining.size:
            continue
        next_preconditioned = residuals[remaining] / diagonal[None, :]
        next_rho = np.einsum(
            "kd,kd->k", residuals[remaining], next_preconditioned
        )
        if np.any(next_rho <= 0.0) or not np.all(np.isfinite(next_rho)):
            raise ArithmeticError("CG encountered invalid updated residual norm")
        previous_rho = rho[remaining]
        beta = next_rho / previous_rho
        directions[remaining] = (
            next_preconditioned + beta[:, None] * directions[remaining]
        )
        if np.any(restart[remaining]):
            restarted = remaining[restart[remaining]]
            directions[restarted] = residuals[restarted] / diagonal[None, :]
        rho[remaining] = next_rho

    all_indices = np.arange(action_count, dtype=np.int64)
    explicit_residuals = rhs - apply(all_indices, solutions)
    residual_norms = np.linalg.norm(explicit_residuals, axis=1)
    relative_residuals = np.zeros(action_count, dtype=np.float64)
    nonzero = rhs_norms > 0.0
    relative_residuals[nonzero] = residual_norms[nonzero] / rhs_norms[nonzero]
    if np.any(~nonzero & (residual_norms > 0.0)):
        raise FloatingPointError("zero right-hand side has a nonzero explicit residual")
    converged = residual_norms <= thresholds

    for array in (
        solutions,
        per_action_iterations,
        per_action_matvecs,
        relative_residuals,
        converged,
    ):
        array.setflags(write=False)
    return BatchedCGResult(
        solutions=solutions,
        per_action_iterations=per_action_iterations,
        per_action_operator_matvecs=per_action_matvecs,
        explicit_relative_residuals=relative_residuals,
        converged=converged,
        batch_operator_calls=batch_calls,
        equivalent_operator_matvecs=equivalent_matvecs,
        preconditioner=preconditioner,
    )


def fixed_iteration_cg(
    operator: CurvatureOperator,
    right_hand_side: ArrayLike,
    iterations: int,
) -> FixedCGResult:
    """Run zero-start CG for at most the requested fixed budget."""

    budget = _positive_int(iterations, name="iterations")
    rhs = np.asarray(right_hand_side, dtype=np.float64)
    if rhs.shape != (operator.dimension,) or not np.all(np.isfinite(rhs)):
        raise ValueError("right_hand_side has the wrong shape or non-finite values")
    solution = np.zeros(operator.dimension, dtype=np.float64)
    residual = rhs.copy()
    direction = residual.copy()
    residual_squared = float(residual @ residual)
    rhs_norm = float(np.sqrt(residual_squared))
    completed = 0
    matvecs = 0
    threshold = np.finfo(np.float64).eps * max(1.0, rhs_norm)
    for completed in range(1, budget + 1):
        applied = operator.matvec(direction)
        matvecs += 1
        curvature = float(direction @ applied)
        if not np.isfinite(curvature) or curvature <= 0.0:
            raise ArithmeticError("CG encountered nonpositive direction curvature")
        step = residual_squared / curvature
        solution += step * direction
        residual -= step * applied
        next_squared = float(residual @ residual)
        if np.sqrt(next_squared) <= threshold:
            residual_squared = next_squared
            break
        direction = residual + (next_squared / residual_squared) * direction
        residual_squared = next_squared
    solution.setflags(write=False)
    return FixedCGResult(
        solution=solution,
        iterations=completed,
        operator_matvecs=matvecs,
        relative_residual=(float(np.sqrt(residual_squared)) / rhs_norm if rhs_norm else 0.0),
    )


@dataclass(frozen=True)
class LanczosResult:
    basis: FloatArray
    ritz_values: FloatArray
    ritz_vectors: FloatArray
    operator_matvecs: int


def lanczos_ritz(
    operator: CurvatureOperator,
    rank: int,
    start_vector: ArrayLike,
) -> LanczosResult:
    """Build a fully reorthogonalized, single-start Lanczos surrogate."""

    requested_rank = min(_positive_int(rank, name="rank"), operator.dimension)
    start = np.asarray(start_vector, dtype=np.float64)
    if start.shape != (operator.dimension,) or not np.all(np.isfinite(start)):
        raise ValueError("start_vector has the wrong shape or non-finite values")
    norm = float(np.linalg.norm(start))
    if norm == 0.0:
        raise ValueError("start_vector must be nonzero")
    basis_columns: list[FloatArray] = []
    alphas: list[float] = []
    betas: list[float] = []
    previous = np.zeros(operator.dimension, dtype=np.float64)
    current = start / norm
    previous_beta = 0.0
    matvecs = 0
    for index in range(requested_rank):
        basis_columns.append(current.copy())
        applied = operator.matvec(current)
        matvecs += 1
        alpha = float(current @ applied)
        residual = applied - alpha * current - previous_beta * previous
        # Full reorthogonalization keeps the small benchmark deterministic.
        for column in basis_columns:
            residual -= float(column @ residual) * column
        alpha_correction = float(current @ residual)
        residual -= alpha_correction * current
        alpha += alpha_correction
        alphas.append(alpha)
        next_beta = float(np.linalg.norm(residual))
        if index + 1 == requested_rank or next_beta <= 64.0 * np.finfo(np.float64).eps:
            break
        betas.append(next_beta)
        previous, current = current, residual / next_beta
        previous_beta = next_beta

    basis = np.column_stack(basis_columns).astype(np.float64, copy=False)
    tridiagonal = np.diag(np.asarray(alphas, dtype=np.float64))
    if betas:
        off_diagonal = np.asarray(betas[: basis.shape[1] - 1], dtype=np.float64)
        tridiagonal += np.diag(off_diagonal, 1) + np.diag(off_diagonal, -1)
    values, vectors = la.eigh(tridiagonal, check_finite=False)
    if np.any(values <= 0.0):
        raise ArithmeticError("Lanczos projected curvature is not positive definite")
    ritz_vectors = np.asarray(basis @ vectors, dtype=np.float64)
    basis.setflags(write=False)
    values.setflags(write=False)
    ritz_vectors.setflags(write=False)
    return LanczosResult(
        basis=basis,
        ritz_values=np.asarray(values, dtype=np.float64),
        ritz_vectors=ritz_vectors,
        operator_matvecs=matvecs,
    )


def lanczos_inverse_apply(
    result: LanczosResult,
    right_hand_sides: ArrayLike,
    damping: float,
) -> FloatArray:
    """Apply a Ritz inverse with ``damping^-1 I`` off the Krylov subspace."""

    rhs = np.asarray(right_hand_sides, dtype=np.float64)
    if rhs.ndim != 2 or rhs.shape[1] != result.ritz_vectors.shape[0]:
        raise ValueError("right_hand_sides has the wrong shape")
    ridge = _positive_float(damping, name="damping")
    projected = rhs @ result.ritz_vectors
    correction = projected * (1.0 / result.ritz_values - 1.0 / ridge)
    return np.asarray(rhs / ridge + correction @ result.ritz_vectors.T, dtype=np.float64)


@dataclass(frozen=True)
class _MethodResult:
    solutions: FloatArray
    iterations: int
    operator_matvecs: int
    working_memory_bytes: int
    metadata: dict[str, Any]


def _run_method(
    method: str,
    operator: CurvatureOperator,
    right_hand_sides: FloatArray,
    iteration_budget: int,
    lanczos_start: FloatArray,
    last_layer_dimension: int,
    cg_relative_tolerance: float = 1e-10,
) -> _MethodResult:
    dimension = operator.dimension
    action_count = right_hand_sides.shape[0]
    if method == "dense_exact":
        dense = operator.to_dense()
        inverse = la.inv(dense, check_finite=False)
        solutions = np.asarray(right_hand_sides @ inverse.T, dtype=np.float64)
        return _MethodResult(
            solutions,
            0,
            0,
            int(2 * dense.nbytes),
            {"reference_solver": "scipy.linalg.inv"},
        )
    if method == "full_cg":
        solved = [
            fixed_iteration_cg(operator, rhs, iteration_budget)
            for rhs in right_hand_sides
        ]
        solutions = np.vstack([result.solution for result in solved])
        return _MethodResult(
            np.asarray(solutions, dtype=np.float64),
            sum(result.iterations for result in solved),
            sum(result.operator_matvecs for result in solved),
            int(5 * dimension * np.dtype(np.float64).itemsize),
            {
                "per_action_iterations": [result.iterations for result in solved],
                "per_action_relative_residual": [
                    result.relative_residual for result in solved
                ],
            },
        )
    if method in {"batched_cg", "batched_jacobi_cg"}:
        preconditioner = (
            "symmetric_jacobi" if method == "batched_jacobi_cg" else "none"
        )
        solved = batched_independent_cg(
            operator,
            right_hand_sides,
            iteration_budget,
            relative_tolerance=cg_relative_tolerance,
            preconditioner=preconditioner,
        )
        vector_copies = 6 if preconditioner == "symmetric_jacobi" else 5
        working = (
            vector_copies * action_count * dimension
            + action_count * operator.sample_count
            + (dimension if preconditioner == "symmetric_jacobi" else 0)
        ) * np.dtype(np.float64).itemsize
        return _MethodResult(
            solved.solutions,
            int(np.sum(solved.per_action_iterations)),
            solved.equivalent_operator_matvecs,
            int(working),
            {
                "solver": "independent_cg_shared_batched_outer_product_matvec",
                "preconditioner": solved.preconditioner,
                "batch_operator_call_count": solved.batch_operator_calls,
                "equivalent_operator_matvec_count": (
                    solved.equivalent_operator_matvecs
                ),
                "per_action_iterations": solved.per_action_iterations.tolist(),
                "per_action_operator_matvecs": (
                    solved.per_action_operator_matvecs.tolist()
                ),
                "per_action_explicit_relative_residual": (
                    solved.explicit_relative_residuals.tolist()
                ),
                "per_action_explicit_residual_converged": (
                    solved.converged.tolist()
                ),
                "mean_explicit_relative_residual": float(
                    np.mean(solved.explicit_relative_residuals)
                ),
                "max_explicit_relative_residual": float(
                    np.max(solved.explicit_relative_residuals)
                ),
                "explicit_residual_converged_count": int(
                    np.count_nonzero(solved.converged)
                ),
                "cg_relative_tolerance": cg_relative_tolerance,
            },
        )
    if method == "diagonal":
        diagonal = operator.diagonal()
        solutions = np.asarray(right_hand_sides / diagonal[None, :], dtype=np.float64)
        return _MethodResult(
            solutions,
            0,
            0,
            int(2 * diagonal.nbytes),
            {"surrogate": "coordinate_diagonal"},
        )
    if method == "lanczos":
        lanczos = lanczos_ritz(operator, iteration_budget, lanczos_start)
        solutions = lanczos_inverse_apply(
            lanczos, right_hand_sides, operator.damping
        )
        rank = int(lanczos.ritz_values.size)
        working = (
            2 * dimension * rank + rank * rank + action_count * rank
        ) * np.dtype(np.float64).itemsize
        return _MethodResult(
            solutions,
            rank,
            lanczos.operator_matvecs,
            int(working),
            {
                "lanczos_rank": rank,
                "lanczos_ritz_min": float(lanczos.ritz_values[0]),
                "lanczos_ritz_max": float(lanczos.ritz_values[-1]),
                "lanczos_start": "single_seeded_gaussian",
            },
        )
    if method == "last_layer_block":
        block = min(_positive_int(last_layer_dimension, name="last_layer_dimension"), dimension)
        start = dimension - block
        block_features = operator.features[:, start:]
        block_matrix = (
            operator.damping * np.eye(block, dtype=np.float64)
            + block_features.T @ block_features / operator.sample_count
        )
        block_inverse = la.inv(block_matrix, check_finite=False)
        solutions = np.zeros_like(right_hand_sides)
        solutions[:, start:] = right_hand_sides[:, start:] @ block_inverse.T
        return _MethodResult(
            solutions,
            0,
            0,
            int(2 * block_matrix.nbytes),
            {
                "last_layer_block_dimension": block,
                "last_layer_block_start": start,
                "last_layer_restriction": LAST_LAYER_RESTRICTION,
            },
        )
    raise ValueError(f"unknown method {method!r}; choose from {list(METHODS)}")


def _grid_values(config: Mapping[str, Any]) -> dict[str, tuple[int, ...]]:
    profile = str(config.get("profile", "smoke"))
    if profile not in {"smoke", "full"}:
        raise ValueError("profile must be 'smoke' or 'full'")
    source = SMOKE_GRID if profile == "smoke" else FULL_GRID
    override = config.get("scaling_grid", config.get("grid", {}))
    if not isinstance(override, Mapping):
        raise ValueError("scaling_grid must be a mapping")
    aliases = {
        "d": ("d", "dimensions"),
        "n": ("n", "sample_counts", "buffer_sizes"),
        "K": ("K", "action_counts"),
        "I": ("I", "iteration_budgets", "cg_iteration_budgets"),
    }
    result: dict[str, tuple[int, ...]] = {}
    for key, names in aliases.items():
        value: Any = source[key]
        for name in names:
            if name in override:
                value = override[name]
                break
            if name in config:
                value = config[name]
                break
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
            raise ValueError(f"grid {key} must be a nonempty sequence")
        result[key] = tuple(_positive_int(item, name=f"grid.{key}") for item in value)
    return result


def systems_grid(config: Mapping[str, Any]) -> tuple[tuple[int, int, int, int], ...]:
    """Return the deterministic Cartesian ``(d,n,K,I)`` grid."""

    grid = _grid_values(config)
    return tuple(
        (dimension, sample_count, action_count, iterations)
        for dimension in grid["d"]
        for sample_count in grid["n"]
        for action_count in grid["K"]
        for iterations in grid["I"]
    )


def advanced_systems_grid(
    config: Mapping[str, Any],
) -> tuple[tuple[int, int, int, int], ...]:
    """Return the optional large-dimension synthetic CPU vector/operator grid."""

    advanced = config.get("advanced_cpu_grid")
    if advanced is None:
        return ()
    if not isinstance(advanced, Mapping):
        raise ValueError("advanced_cpu_grid must be a mapping")
    enabled = advanced.get("enabled", False)
    if not isinstance(enabled, bool):
        raise TypeError("advanced_cpu_grid.enabled must be boolean")
    if not enabled:
        return ()
    aliases = {
        "d": ("d", "dimensions"),
        "n": ("n", "sample_counts", "buffer_sizes"),
        "K": ("K", "action_counts"),
        "I": ("I", "iteration_budgets", "cg_iteration_budgets"),
    }
    values: dict[str, tuple[int, ...]] = {}
    for key, names in aliases.items():
        raw: Any = ADVANCED_CPU_GRID[key]
        for name in names:
            if name in advanced:
                raw = advanced[name]
                break
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
            raise ValueError(f"advanced grid {key} must be a nonempty sequence")
        values[key] = tuple(
            _positive_int(item, name=f"advanced_cpu_grid.{key}") for item in raw
        )
    if max(values["d"]) <= 255:
        raise ValueError("advanced_cpu_grid must include a dimension greater than 255")
    return tuple(
        (dimension, sample_count, action_count, iterations)
        for dimension in values["d"]
        for sample_count in values["n"]
        for action_count in values["K"]
        for iterations in values["I"]
    )


@dataclass(frozen=True)
class _ReferenceResult:
    solutions: FloatArray
    widths_squared: FloatArray
    condition_number: float
    seconds: float
    storage_bytes: int
    implementation: str
    dense_matrix: FloatArray | None


def _exact_reference(
    operator: CurvatureOperator,
    right_hand_sides: FloatArray,
    *,
    sample_space: bool,
) -> _ReferenceResult:
    started = time.perf_counter()
    if not sample_space:
        dense = operator.to_dense()
        started = time.perf_counter()
        inverse = la.inv(dense, check_finite=False)
        solutions = np.asarray(right_hand_sides @ inverse.T, dtype=np.float64)
        elapsed = time.perf_counter() - started
        eigenvalues = la.eigvalsh(dense, check_finite=False)
        condition = float(eigenvalues[-1] / eigenvalues[0])
        widths = np.einsum("kd,kd->k", right_hand_sides, solutions)
        return _ReferenceResult(
            solutions=solutions,
            widths_squared=np.asarray(widths, dtype=np.float64),
            condition_number=condition,
            seconds=elapsed,
            storage_bytes=int(dense.nbytes + solutions.nbytes),
            implementation="scipy.linalg.inv_float64_parameter_space",
            dense_matrix=dense,
        )

    features = operator.features
    sample_count = operator.sample_count
    ridge = operator.damping
    sample_matrix = (
        sample_count * np.eye(sample_count, dtype=np.float64)
        + (features @ features.T) / ridge
    )
    factor = la.cho_factor(sample_matrix, lower=True, check_finite=False)
    projected_rhs = features @ right_hand_sides.T
    middle = la.cho_solve(factor, projected_rhs, check_finite=False)
    solutions = np.asarray(
        right_hand_sides / ridge - (middle.T @ features) / (ridge * ridge),
        dtype=np.float64,
    )
    singular_values = la.svdvals(features, check_finite=False)
    largest = float(singular_values[0]) if singular_values.size else 0.0
    smallest = (
        float(singular_values[-1])
        if operator.dimension <= singular_values.size and singular_values.size
        else 0.0
    )
    condition = float(
        (ridge + largest * largest / sample_count)
        / (ridge + smallest * smallest / sample_count)
    )
    elapsed = time.perf_counter() - started
    widths = np.einsum("kd,kd->k", right_hand_sides, solutions)
    storage = (
        sample_matrix.nbytes
        + projected_rhs.nbytes
        + middle.nbytes
        + solutions.nbytes
        + singular_values.nbytes
    )
    return _ReferenceResult(
        solutions=solutions,
        widths_squared=np.asarray(widths, dtype=np.float64),
        condition_number=condition,
        seconds=elapsed,
        storage_bytes=int(storage),
        implementation="woodbury_float64_sample_space_cholesky",
        dense_matrix=None,
    )


def _operator_relative_energy_errors(
    operator: CurvatureOperator,
    exact_solutions: FloatArray,
    approximate_solutions: FloatArray,
) -> FloatArray:
    errors = exact_solutions - approximate_solutions
    numerator = np.einsum("kd,kd->k", errors, operator.matmat(errors))
    denominator = np.einsum(
        "kd,kd->k", exact_solutions, operator.matmat(exact_solutions)
    )
    tolerance = 512.0 * np.finfo(np.float64).eps
    if np.any(numerator < -tolerance) or np.any(denominator <= 0.0):
        raise ArithmeticError("operator energy error diagnostic is invalid")
    return np.asarray(
        np.sqrt(np.maximum(numerator, 0.0) / denominator), dtype=np.float64
    )


@dataclass(frozen=True)
class SystemsScalingRun:
    seed: int
    records: tuple[dict[str, Any], ...]
    summary: dict[str, Any]

    @property
    def rounds(self) -> tuple[dict[str, Any], ...]:
        return self.records


def _method_selection(
    value: Any,
    *,
    name: str,
    allowed: set[str] | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    requested = tuple(str(method) for method in value)
    if not requested:
        raise ValueError(f"{name} must not be empty")
    unknown = set(requested) - set(METHOD_ALIASES)
    if unknown:
        raise ValueError(f"unknown methods in {name}: {sorted(unknown)}")
    canonical = tuple(METHOD_ALIASES[method] for method in requested)
    if len(set(canonical)) != len(canonical):
        raise ValueError(f"{name} resolves to duplicate canonical implementations")
    if allowed is not None and not set(canonical) <= allowed:
        raise ValueError(f"{name} may contain only {sorted(allowed)}")
    return requested, canonical


def run_systems_scaling(config: Mapping[str, Any], seed: int) -> SystemsScalingRun:
    """Benchmark all methods over the configured feasible systems grid."""

    seed_everything(seed)
    curvature_config = config.get("curvature", {})
    if not isinstance(curvature_config, Mapping):
        raise ValueError("curvature must be a mapping")
    damping = _positive_float(
        curvature_config.get("damping", config.get("ridge", 1.0)), name="damping"
    )
    noise_std = _positive_float(config.get("noise_std", 1.0), name="noise_std")
    repetitions = _positive_int(
        config.get("timing_repetitions", 1), name="timing_repetitions"
    )
    warmup_repetitions = _nonnegative_int(
        config.get("warmup_repetitions", 0), name="warmup_repetitions"
    )
    requested_methods, methods = _method_selection(
        config.get("methods", METHODS), name="methods"
    )
    cg_relative_tolerance = _nonnegative_float(
        config.get("cg_relative_tolerance", 1e-10),
        name="cg_relative_tolerance",
    )
    advanced_points = advanced_systems_grid(config)
    advanced_config = config.get("advanced_cpu_grid", {})
    if not isinstance(advanced_config, Mapping):
        raise ValueError("advanced_cpu_grid must be a mapping")
    advanced_requested: tuple[str, ...] = ()
    advanced_methods: tuple[str, ...] = ()
    if advanced_points:
        advanced_requested, advanced_methods = _method_selection(
            advanced_config.get(
                "methods", ("batched_cg", "batched_jacobi_cg")
            ),
            name="advanced_cpu_grid.methods",
            allowed={"batched_cg", "batched_jacobi_cg"},
        )
    fraction = float(config.get("last_layer_fraction", 0.25))
    if not np.isfinite(fraction) or not 0.0 < fraction <= 1.0:
        raise ValueError("last_layer_fraction must lie in (0, 1]")
    fixed_block = config.get("last_layer_block_dimension")

    standard_points = systems_grid(config)
    work_items = [
        (
            "standard_cpu_grid",
            index,
            point,
            requested_methods,
            methods,
            False,
        )
        for index, point in enumerate(standard_points)
    ]
    work_items.extend(
        (
            "advanced_cpu_grid",
            len(standard_points) + index,
            point,
            advanced_requested,
            advanced_methods,
            True,
        )
        for index, point in enumerate(advanced_points)
    )

    records: list[dict[str, Any]] = []
    for (
        grid_kind,
        grid_index,
        (dimension, sample_count, action_count, iterations),
        point_requested_methods,
        point_methods,
        sample_space_reference,
    ) in work_items:
        seed_namespace = "systems" if not sample_space_reference else "systems_advanced"
        seed_index = (
            grid_index
            if not sample_space_reference
            else grid_index - len(standard_points)
        )
        rng = np.random.default_rng(derive_seed(seed, seed_namespace, seed_index))
        features = rng.normal(size=(sample_count, dimension)).astype(np.float64)
        # Unit expected row norm keeps conditioning comparable across d and n.
        features /= noise_std * np.sqrt(float(dimension))
        right_hand_sides = rng.normal(size=(action_count, dimension)).astype(np.float64)
        right_hand_sides /= np.linalg.norm(right_hand_sides, axis=1)[:, None]
        lanczos_start = rng.normal(size=dimension).astype(np.float64)
        operator = CurvatureOperator(features, damping)
        reference = _exact_reference(
            operator,
            right_hand_sides,
            sample_space=sample_space_reference,
        )
        exact_solutions = reference.solutions
        exact_widths_squared = reference.widths_squared
        if np.any(exact_widths_squared <= 0.0):
            raise FloatingPointError("exact reference produced a nonpositive width")
        block_dimension = (
            min(dimension, _positive_int(fixed_block, name="last_layer_block_dimension"))
            if fixed_block is not None
            else max(1, int(np.ceil(fraction * dimension)))
        )

        probe = np.ones(dimension, dtype=np.float64) / np.sqrt(float(dimension))
        matvec_start = time.perf_counter()
        operator.matvec(probe)
        curvature_matvec_seconds = time.perf_counter() - matvec_start

        for configured_method, method in zip(
            point_requested_methods, point_methods, strict=True
        ):
            for _ in range(warmup_repetitions):
                _run_method(
                    method,
                    operator,
                    right_hand_sides,
                    iterations,
                    lanczos_start,
                    block_dimension,
                    cg_relative_tolerance,
                )
            timings: list[float] = []
            rss_before = _rss_bytes()
            method_result: _MethodResult | None = None
            for _ in range(repetitions):
                start = time.perf_counter()
                method_result = _run_method(
                    method,
                    operator,
                    right_hand_sides,
                    iterations,
                    lanczos_start,
                    block_dimension,
                    cg_relative_tolerance,
                )
                timings.append(time.perf_counter() - start)
            assert method_result is not None
            rss_after = _rss_bytes()
            approximate = method_result.solutions
            if reference.dense_matrix is not None:
                energy_errors = np.asarray(
                    [
                        relative_energy_error(
                            reference.dense_matrix, exact, candidate
                        )
                        for exact, candidate in zip(
                            exact_solutions, approximate, strict=True
                        )
                    ],
                    dtype=np.float64,
                )
            else:
                energy_errors = _operator_relative_energy_errors(
                    operator, exact_solutions, approximate
                )
            approximate_widths_squared = np.einsum(
                "kd,kd->k", right_hand_sides, approximate
            )
            if np.any(approximate_widths_squared < 0.0):
                raise FloatingPointError(f"{method} produced a negative width squared")
            width_relative_errors = np.abs(
                approximate_widths_squared - exact_widths_squared
            ) / exact_widths_squared
            sandwich_lower = (1.0 - energy_errors) * exact_widths_squared
            sandwich_upper = (1.0 + energy_errors) * exact_widths_squared
            sandwich_tolerance = 512.0 * np.finfo(np.float64).eps
            sandwich_holds = bool(
                np.all(approximate_widths_squared >= sandwich_lower - sandwich_tolerance)
                and np.all(approximate_widths_squared <= sandwich_upper + sandwich_tolerance)
            )
            operator_matvecs = int(method_result.operator_matvecs)
            sample_cvps = operator_matvecs * sample_count
            record: dict[str, Any] = {
                "seed": seed,
                "grid_index": grid_index,
                "method": configured_method,
                "method_implementation": method,
                "benchmark_kind": BENCHMARK_KIND,
                "benchmark_grid": grid_kind,
                "synthetic_cpu_parameter_vector_benchmark": True,
                "accelerator_benchmark": False,
                "foundation_model_benchmark": False,
                "dimension": dimension,
                "d": dimension,
                "sample_count": sample_count,
                "n": sample_count,
                "action_count": action_count,
                "K": action_count,
                "iteration_budget": iterations,
                "I": iterations,
                "damping": damping,
                "condition_number": reference.condition_number,
                "cg_iterations": int(method_result.iterations),
                "iterations_executed": int(method_result.iterations),
                "operator_matvec_count": operator_matvecs,
                "batch_operator_call_count": int(
                    method_result.metadata.get("batch_operator_call_count", 0)
                ),
                "sample_cvp_count": sample_cvps,
                "equivalent_sample_cvp_count": sample_cvps,
                "cvp_count": sample_cvps,
                "curvature_vector_products": sample_cvps,
                "mean_relative_energy_error": float(np.mean(energy_errors)),
                "max_relative_energy_error": float(np.max(energy_errors)),
                "mean_width_squared_relative_error": float(
                    np.mean(width_relative_errors)
                ),
                "max_width_squared_relative_error": float(
                    np.max(width_relative_errors)
                ),
                "predictive_width_relative_error": float(
                    np.max(width_relative_errors)
                ),
                "width_sandwich_holds": sandwich_holds,
                "wall_time_seconds": float(np.median(timings)),
                "wall_time_min_seconds": float(np.min(timings)),
                "wall_time_repetitions_seconds": timings,
                "timing_repetitions": repetitions,
                "warmup_repetitions": warmup_repetitions,
                "curvature_matvec_seconds": curvature_matvec_seconds,
                "exact_reference_seconds": reference.seconds,
                "exact_reference_implementation": reference.implementation,
                "dense_inverse_reference_seconds": (
                    reference.seconds if reference.dense_matrix is not None else 0.0
                ),
                "rss_before_bytes": rss_before,
                "rss_after_bytes": rss_after,
                "rss_bytes": rss_after,
                "rss_delta_bytes": rss_after - rss_before,
                "peak_host_memory_bytes": _peak_host_memory_bytes(),
                "peak_accelerator_memory_bytes": 0,
                "operator_storage_bytes": int(features.nbytes),
                "dense_diagnostic_reference_bytes": (
                    int(reference.dense_matrix.nbytes)
                    if reference.dense_matrix is not None
                    else 0
                ),
                "exact_reference_storage_bytes": reference.storage_bytes,
                "estimated_working_memory_bytes": method_result.working_memory_bytes,
                "estimated_total_host_memory_bytes": int(
                    features.nbytes
                    + method_result.working_memory_bytes
                    + reference.storage_bytes
                ),
                "last_layer_block_dimension": block_dimension,
                "last_layer_restriction": LAST_LAYER_RESTRICTION,
                **method_result.metadata,
            }
            records.append(record)

    summary: dict[str, Any] = {
        "experiment": "systems_scaling",
        "seed": seed,
        "profile": str(config.get("profile", "smoke")),
        "grid": {key: list(value) for key, value in _grid_values(config).items()},
        "grid_point_count": len(standard_points),
        "advanced_cpu_grid": [list(point) for point in advanced_points],
        "advanced_grid_point_count": len(advanced_points),
        "methods": list(requested_methods),
        "method_implementations": list(methods),
        "advanced_methods": list(advanced_requested),
        "advanced_method_implementations": list(advanced_methods),
        "record_count": len(records),
        "total_sample_cvps": sum(int(record["sample_cvp_count"]) for record in records),
        "width_sandwich_violation_count": sum(
            not bool(record["width_sandwich_holds"]) for record in records
        ),
        "last_layer_restriction": LAST_LAYER_RESTRICTION,
        "synthetic_feasibility_benchmark": True,
        "synthetic_cpu_parameter_vector_benchmark": True,
        "benchmark_kind": BENCHMARK_KIND,
        "accelerator_benchmark": False,
        "foundation_model_benchmark": False,
        "foundation_model_wall_clock_claim": False,
        "exact_reference": "scipy.linalg.inv float64 dense inverse",
        "exact_reference_implementations": sorted(
            {str(record["exact_reference_implementation"]) for record in records}
        ),
    }
    return SystemsScalingRun(seed=seed, records=tuple(records), summary=summary)


def save_run(
    run: SystemsScalingRun,
    output_dir: str | Path,
    config: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    destination = Path(output_dir)
    manifest_config = dict(config)
    manifest_config["execution"] = {
        "driver": "run_systems_scaling",
        "seed": run.seed,
        "benchmark_kind": BENCHMARK_KIND,
        "synthetic_cpu_parameter_vector_benchmark": True,
        "accelerator_benchmark": False,
        "foundation_model_benchmark": False,
        "methods": list(run.summary["methods"]),
        "grid": run.summary["grid"],
        "advanced_cpu_grid": run.summary["advanced_cpu_grid"],
        "advanced_methods": run.summary["advanced_methods"],
        "last_layer_restriction": LAST_LAYER_RESTRICTION,
    }
    with ExperimentLogger(
        destination,
        manifest_config,
        run.seed,
        repository=Path(__file__).resolve().parents[1],
        overwrite=overwrite,
    ) as logger:
        for index, record in enumerate(run.records):
            logger.log_round(index, record)
    summary_path = destination / "summary.jsonl"
    if overwrite and summary_path.exists():
        summary_path.unlink()
    append_jsonl(summary_path, run.summary)
    return destination


def run_experiment(
    config: Mapping[str, Any],
    *,
    seed_set: str,
    output_root: str | Path,
    overwrite: bool = False,
) -> tuple[SystemsScalingRun, ...]:
    results: list[SystemsScalingRun] = []
    for seed in get_seed_set(config, seed_set):
        run = run_systems_scaling(config, seed)
        destination = (
            Path(output_root)
            / str(config.get("name", "systems_scaling"))
            / str(config.get("profile", "default"))
            / seed_set
            / f"seed-{seed}"
        )
        save_run(run, destination, config, overwrite=overwrite)
        results.append(run)
    return tuple(results)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config_path", nargs="?", type=Path)
    parser.add_argument("--config", dest="config_option", type=Path)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument(
        "--seed-set", choices=("tuning", "evaluation"), required=True
    )
    parser.add_argument(
        "--output-root", type=Path, default=Path("experiments/results")
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.config_path is not None and args.config_option is not None:
        parser.error("provide the config either positionally or with --config, not both")
    config_path = args.config_option or args.config_path
    if config_path is None:
        parser.error("a config path is required")
    config = load_config(config_path, profile=args.profile)
    results = run_experiment(
        config,
        seed_set=args.seed_set,
        output_root=args.output_root,
        overwrite=args.overwrite,
    )
    print(
        json.dumps(
            {
                "experiment": config["name"],
                "profile": args.profile,
                "seed_set": args.seed_set,
                "seeds": [run.seed for run in results],
                "records": sum(len(run.records) for run in results),
                "output_root": str(args.output_root),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ADVANCED_CPU_GRID",
    "BENCHMARK_KIND",
    "BatchedCGResult",
    "CurvatureOperator",
    "DEFAULT_CONFIG",
    "FULL_GRID",
    "LAST_LAYER_RESTRICTION",
    "METHODS",
    "SMOKE_GRID",
    "SystemsScalingRun",
    "advanced_systems_grid",
    "batched_independent_cg",
    "fixed_iteration_cg",
    "lanczos_inverse_apply",
    "lanczos_ritz",
    "run_experiment",
    "run_systems_scaling",
    "save_run",
    "systems_grid",
]
