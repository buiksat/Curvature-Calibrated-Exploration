"""Audit residual-certified CG accuracy against dense float64 inverses.

The audit deliberately keeps the solver local to this driver.  It compares
zero and previous-round warm starts, with and without Jacobi preconditioning,
at the fixed relative energy targets in :data:`ENERGY_TARGETS`.  Warm starts
are observations, not assumptions: every record contains their measured
initial energy error, which may be larger than the zero-start value of one.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import resource
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import scipy.linalg as la
from numpy.typing import ArrayLike, NDArray

from .config import get_seed_set, load_config
from .linear_environment import (
    ACTION_COUNT,
    FEATURE_DIMENSION,
    LinearBanditEnvironment,
    default_theta_star,
    enumerate_rademacher_contexts,
)
from .logging_utils import ExperimentLogger, append_jsonl, derive_seed, seed_everything
from .run_linear_audit import confidence_radius


FloatArray = NDArray[np.float64]

ENERGY_TARGETS = (0.5, 0.25, 0.1, 0.05, 0.01)
INITIALIZATIONS = ("zero", "warm")
PRECONDITIONERS = ("none", "jacobi")
POLICY_EXPERIMENT_NAME = "cg_policy_accuracy"

DEFAULT_CONFIG: dict[str, Any] = {
    "name": "cg_accuracy",
    "profile": "smoke",
    "rounds": 2,
    "dimension": 16,
    "action_count": 2,
    "condition_numbers": [30.0],
    "damping": [1.0],
    "cg": {"record_residual_history": True},
    "provenance": {"packages": ["numpy", "scipy"]},
}


def _float64_vector(value: ArrayLike, dimension: int, *, name: str) -> FloatArray:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (dimension,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite float64 vector of length {dimension}")
    return array


def _float64_spd(value: ArrayLike) -> FloatArray:
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("matrix must be a nonempty square float64 array")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("matrix must be finite")
    if not np.allclose(matrix, matrix.T, rtol=1e-12, atol=1e-14):
        raise ValueError("matrix must be symmetric")
    matrix = np.asarray(0.5 * (matrix + matrix.T), dtype=np.float64)
    try:
        la.cholesky(matrix, lower=True, check_finite=False)
    except la.LinAlgError as error:
        raise ValueError("matrix must be symmetric positive definite") from error
    return matrix


def _positive_float(value: Any, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _rss_bytes() -> int:
    """Return current process RSS without making psutil a dependency."""

    try:
        with open("/proc/self/statm", encoding="ascii") as stream:
            resident_pages = int(stream.read().split()[1])
        return resident_pages * int(os.sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError, IndexError, AttributeError):
        try:
            import psutil  # type: ignore[import-not-found]

            return int(psutil.Process().memory_info().rss)
        except (ImportError, OSError):
            return 0


def _peak_host_memory_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # macOS reports bytes; Linux and the BSDs report KiB.
    return value if sys.platform == "darwin" else value * 1024


def _energy_norm_squared(matrix: FloatArray, vector: FloatArray) -> float:
    value = float(vector @ (matrix @ vector))
    if not np.isfinite(value) or value < -256.0 * np.finfo(np.float64).eps:
        raise ArithmeticError("invalid squared energy norm")
    return max(0.0, value)


def relative_energy_error(
    matrix: ArrayLike,
    exact_solution: ArrayLike,
    approximate_solution: ArrayLike,
) -> float:
    """Return the exact relative error in the matrix energy norm."""

    spd = _float64_spd(matrix)
    exact = _float64_vector(exact_solution, spd.shape[0], name="exact_solution")
    approximate = _float64_vector(
        approximate_solution, spd.shape[0], name="approximate_solution"
    )
    denominator = _energy_norm_squared(spd, exact)
    numerator = _energy_norm_squared(spd, exact - approximate)
    if denominator == 0.0:
        return 0.0 if numerator == 0.0 else math.inf
    return float(np.sqrt(numerator / denominator))


def _scaled_condition_number(matrix: FloatArray, diagonal: FloatArray) -> float:
    inverse_root = 1.0 / np.sqrt(diagonal)
    scaled = (inverse_root[:, None] * matrix) * inverse_root[None, :]
    eigenvalues = la.eigvalsh(scaled, check_finite=False)
    condition = float(eigenvalues[-1] / eigenvalues[0])
    # Round upward so the value is used as a numerical upper bound.
    return condition * (1.0 + 64.0 * np.finfo(np.float64).eps)


def residual_energy_certificate(
    matrix: ArrayLike,
    right_hand_side: ArrayLike,
    residual: ArrayLike,
    *,
    preconditioner: str = "none",
    condition_upper_bound: float | None = None,
) -> float:
    """Certify energy error from a Euclidean or Jacobi-scaled residual.

    For ``none`` this is ``sqrt(kappa(A))*||r||/||b||``.  For ``jacobi``
    the same inequality is applied to the symmetrically scaled system
    ``D^-1/2 A D^-1/2``.
    """

    spd = _float64_spd(matrix)
    dimension = spd.shape[0]
    rhs = _float64_vector(right_hand_side, dimension, name="right_hand_side")
    checked_residual = _float64_vector(residual, dimension, name="residual")
    if preconditioner not in PRECONDITIONERS:
        raise ValueError(f"unknown preconditioner {preconditioner!r}")
    diagonal = (
        np.ones(dimension, dtype=np.float64)
        if preconditioner == "none"
        else np.diag(spd).copy()
    )
    if np.any(diagonal <= 0.0):
        raise ArithmeticError("Jacobi diagonal must be positive")
    scaled_rhs_norm = float(np.linalg.norm(rhs / np.sqrt(diagonal)))
    scaled_residual_norm = float(
        np.linalg.norm(checked_residual / np.sqrt(diagonal))
    )
    if scaled_rhs_norm == 0.0:
        return 0.0 if scaled_residual_norm == 0.0 else math.inf
    condition = (
        _scaled_condition_number(spd, diagonal)
        if condition_upper_bound is None
        else _positive_float(condition_upper_bound, name="condition_upper_bound")
    )
    return float(np.sqrt(condition) * scaled_residual_norm / scaled_rhs_norm)


@dataclass(frozen=True)
class CertifiedCGResult:
    solution: FloatArray
    converged: bool
    iterations: int
    operator_matvecs: int
    residual_norm: float
    relative_residual: float
    residual_certificate: float
    initial_residual_certificate: float
    condition_upper_bound: float
    residual_history: FloatArray
    certificate_history: FloatArray


def solve_certified_cg(
    matrix: ArrayLike,
    right_hand_side: ArrayLike,
    *,
    target: float,
    preconditioner: str = "none",
    initial_solution: ArrayLike | None = None,
    max_iterations: int | None = None,
    condition_upper_bound: float | None = None,
    operator_matvec: Callable[[FloatArray], FloatArray] | None = None,
) -> CertifiedCGResult:
    """Run float64 (P)CG until the residual certificate reaches ``target``."""

    spd = _float64_spd(matrix)
    dimension = spd.shape[0]
    rhs = _float64_vector(right_hand_side, dimension, name="right_hand_side").copy()
    target_value = _positive_float(target, name="target")
    if target_value >= 1.0:
        raise ValueError("target must be smaller than one")
    if preconditioner not in PRECONDITIONERS:
        raise ValueError(f"unknown preconditioner {preconditioner!r}")
    iteration_limit = (
        4 * dimension
        if max_iterations is None
        else _positive_int(max_iterations, name="max_iterations")
    )
    diagonal = (
        np.ones(dimension, dtype=np.float64)
        if preconditioner == "none"
        else np.diag(spd).copy()
    )
    condition = (
        _scaled_condition_number(spd, diagonal)
        if condition_upper_bound is None
        else _positive_float(condition_upper_bound, name="condition_upper_bound")
    )

    def apply(vector: FloatArray) -> FloatArray:
        raw = spd @ vector if operator_matvec is None else operator_matvec(vector)
        checked = np.asarray(raw, dtype=np.float64)
        if checked.shape != (dimension,) or not np.all(np.isfinite(checked)):
            raise ValueError("operator_matvec must return a finite vector of the RHS shape")
        return checked

    matvecs = 0
    if initial_solution is None:
        solution = np.zeros(dimension, dtype=np.float64)
        residual = rhs.copy()
    else:
        solution = _float64_vector(
            initial_solution, dimension, name="initial_solution"
        ).copy()
        residual = rhs - apply(solution)
        matvecs += 1

    rhs_norm = float(np.linalg.norm(rhs))

    def certificate(current: FloatArray) -> float:
        scaled_rhs = rhs / np.sqrt(diagonal)
        denominator = float(np.linalg.norm(scaled_rhs))
        numerator = float(np.linalg.norm(current / np.sqrt(diagonal)))
        if denominator == 0.0:
            return 0.0 if numerator == 0.0 else math.inf
        return float(np.sqrt(condition) * numerator / denominator)

    residual_history = [float(np.linalg.norm(residual))]
    certificate_history = [certificate(residual)]
    if certificate_history[-1] <= target_value:
        frozen_solution = np.asarray(solution, dtype=np.float64).copy()
        frozen_solution.setflags(write=False)
        frozen_residual_history = np.asarray(residual_history, dtype=np.float64)
        frozen_certificate_history = np.asarray(
            certificate_history, dtype=np.float64
        )
        frozen_residual_history.setflags(write=False)
        frozen_certificate_history.setflags(write=False)
        return CertifiedCGResult(
            solution=frozen_solution,
            converged=True,
            iterations=0,
            operator_matvecs=matvecs,
            residual_norm=residual_history[-1],
            relative_residual=(residual_history[-1] / rhs_norm if rhs_norm else 0.0),
            residual_certificate=certificate_history[-1],
            initial_residual_certificate=certificate_history[0],
            condition_upper_bound=condition,
            residual_history=frozen_residual_history,
            certificate_history=frozen_certificate_history,
        )

    inverse_diagonal = 1.0 / diagonal
    preconditioned_residual = inverse_diagonal * residual
    direction = preconditioned_residual.copy()
    residual_product = float(residual @ preconditioned_residual)
    converged = False
    iterations = 0
    for iterations in range(1, iteration_limit + 1):
        applied = apply(direction)
        matvecs += 1
        curvature = float(direction @ applied)
        if not np.isfinite(curvature) or curvature <= 0.0:
            raise ArithmeticError("CG encountered nonpositive direction curvature")
        step = residual_product / curvature
        solution += step * direction
        residual -= step * applied
        residual_norm = float(np.linalg.norm(residual))
        current_certificate = certificate(residual)
        residual_history.append(residual_norm)
        certificate_history.append(current_certificate)
        if current_certificate <= target_value:
            converged = True
            break
        next_preconditioned = inverse_diagonal * residual
        next_product = float(residual @ next_preconditioned)
        if not np.isfinite(next_product) or next_product < 0.0:
            raise ArithmeticError("CG encountered an invalid residual product")
        if residual_product == 0.0:
            break
        direction = next_preconditioned + (next_product / residual_product) * direction
        preconditioned_residual = next_preconditioned
        residual_product = next_product

    frozen_solution = np.asarray(solution, dtype=np.float64).copy()
    frozen_solution.setflags(write=False)
    residual_array = np.asarray(residual_history, dtype=np.float64)
    certificate_array = np.asarray(certificate_history, dtype=np.float64)
    residual_array.setflags(write=False)
    certificate_array.setflags(write=False)
    return CertifiedCGResult(
        solution=frozen_solution,
        converged=converged,
        iterations=iterations,
        operator_matvecs=matvecs,
        residual_norm=float(residual_array[-1]),
        relative_residual=(float(residual_array[-1]) / rhs_norm if rhs_norm else 0.0),
        residual_certificate=float(certificate_array[-1]),
        initial_residual_certificate=float(certificate_array[0]),
        condition_upper_bound=condition,
        residual_history=residual_array,
        certificate_history=certificate_array,
    )


def make_spd_problem(
    dimension: int,
    action_count: int,
    condition_number: float,
    damping: float,
    seed: int,
    *,
    sample_count: int | None = None,
    noise_std: float = 1.0,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Construct a deterministic rotated SPD matrix, features, and RHS batch."""

    dimension = _positive_int(dimension, name="dimension")
    action_count = _positive_int(action_count, name="action_count")
    samples = (
        dimension
        if sample_count is None
        else _positive_int(sample_count, name="sample_count")
    )
    condition = _positive_float(condition_number, name="condition_number")
    ridge = _positive_float(damping, name="damping")
    standard_deviation = _positive_float(noise_std, name="noise_std")
    if condition < 1.0:
        raise ValueError("condition_number must be at least one")
    rng = np.random.default_rng(seed)
    basis, raw_r = la.qr(
        rng.normal(size=(dimension, dimension)).astype(np.float64),
        mode="economic",
        check_finite=False,
    )
    signs = np.where(np.diag(raw_r) < 0.0, -1.0, 1.0)
    basis = np.asarray(basis * signs, dtype=np.float64)
    active_rank = min(samples, dimension)
    eigenvalues = np.full(dimension, ridge, dtype=np.float64)
    if active_rank == dimension:
        active_eigenvalues = ridge * np.geomspace(
            1.0, condition, active_rank, dtype=np.float64
        )
    else:
        # The inactive complement supplies the exact ridge eigenvalue.
        active_eigenvalues = ridge * np.geomspace(
            condition ** (1.0 / active_rank),
            condition,
            active_rank,
            dtype=np.float64,
        )
    eigenvalues[-active_rank:] = active_eigenvalues
    matrix = np.asarray((basis * eigenvalues) @ basis.T, dtype=np.float64)
    matrix = np.asarray(0.5 * (matrix + matrix.T), dtype=np.float64)
    active_basis = basis[:, -active_rank:]
    feature_scales = standard_deviation * np.sqrt(active_eigenvalues - ridge)
    compact_factor = feature_scales[:, None] * active_basis.T
    row_basis, _ = la.qr(
        rng.normal(size=(samples, active_rank)).astype(np.float64),
        mode="economic",
        check_finite=False,
    )
    features = np.asarray(row_basis @ compact_factor, dtype=np.float64)
    right_hand_sides = rng.normal(size=(action_count, dimension)).astype(np.float64)
    norms = np.linalg.norm(right_hand_sides, axis=1)
    right_hand_sides /= norms[:, None]
    return matrix, features, right_hand_sides


@dataclass(frozen=True)
class CGAccuracyRun:
    seed: int
    records: tuple[dict[str, Any], ...]
    summary: dict[str, Any]

    @property
    def rounds(self) -> tuple[dict[str, Any], ...]:
        return self.records


def _sequence(value: Any, *, name: str) -> tuple[Any, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise ValueError(f"{name} must be a nonempty sequence")
    return tuple(value)


def run_cg_accuracy(config: Mapping[str, Any], seed: int) -> CGAccuracyRun:
    """Run every target/start/preconditioner combination for one seed."""

    seed_everything(seed)
    dimension = _positive_int(config.get("dimension", 30), name="dimension")
    rounds = _positive_int(config.get("rounds", 1), name="rounds")
    action_count = _positive_int(config.get("action_count", 1), name="action_count")
    sample_count = _positive_int(
        config.get("sample_count", dimension), name="sample_count"
    )
    noise_std = _positive_float(config.get("noise_std", 1.0), name="noise_std")
    conditions = tuple(
        _positive_float(value, name="condition_number")
        for value in _sequence(config.get("condition_numbers", [30.0]), name="condition_numbers")
    )
    raw_damping = config.get("damping", config.get("ridge", [1.0]))
    if isinstance(raw_damping, (int, float, np.integer, np.floating)):
        raw_damping = [raw_damping]
    dampings = tuple(
        _positive_float(value, name="damping")
        for value in _sequence(raw_damping, name="damping")
    )
    cg_config = config.get("cg", {})
    if not isinstance(cg_config, Mapping):
        raise ValueError("cg must be a mapping")
    requested_limit = cg_config.get("max_iterations")
    if requested_limit is None:
        budgets = cg_config.get("iteration_budgets", [])
        budget_max = max((int(value) for value in budgets), default=0)
        max_iterations = max(4 * dimension, budget_max)
    else:
        max_iterations = _positive_int(requested_limit, name="cg.max_iterations")
    include_histories = bool(
        cg_config.get(
            "record_residual_history", config.get("record_residual_history", False)
        )
    )

    records: list[dict[str, Any]] = []
    warm_solutions: dict[tuple[float, float, float, str, int], FloatArray] = {}
    for condition_index, condition in enumerate(conditions):
        for damping_index, damping in enumerate(dampings):
            for round_index in range(rounds):
                problem_seed = derive_seed(
                    seed, "cg_accuracy", condition_index, damping_index, round_index
                )
                matrix, features, right_hand_sides = make_spd_problem(
                    dimension,
                    action_count,
                    condition,
                    damping,
                    problem_seed,
                    sample_count=sample_count,
                    noise_std=noise_std,
                )
                reference_start = time.perf_counter()
                dense_inverse = la.inv(matrix, check_finite=False)
                reference_seconds = time.perf_counter() - reference_start
                actual_eigenvalues = la.eigvalsh(matrix, check_finite=False)
                actual_condition = float(actual_eigenvalues[-1] / actual_eigenvalues[0])
                sample_count = int(features.shape[0])

                def curvature_matvec(vector: FloatArray) -> FloatArray:
                    return np.asarray(
                        damping * vector
                        + features.T @ (features @ vector) / (noise_std**2),
                        dtype=np.float64,
                    )

                for action_index, rhs in enumerate(right_hand_sides):
                    exact_solution = np.asarray(dense_inverse @ rhs, dtype=np.float64)
                    exact_width_squared = float(rhs @ exact_solution)
                    exact_width = float(np.sqrt(exact_width_squared))
                    for target in ENERGY_TARGETS:
                        for preconditioner in PRECONDITIONERS:
                            diagonal = (
                                np.ones(dimension, dtype=np.float64)
                                if preconditioner == "none"
                                else np.diag(matrix).copy()
                            )
                            certificate_condition = _scaled_condition_number(
                                matrix, diagonal
                            )
                            state_key = (
                                condition,
                                damping,
                                target,
                                preconditioner,
                                action_index,
                            )
                            for initialization in INITIALIZATIONS:
                                if initialization == "zero":
                                    initial = np.zeros(dimension, dtype=np.float64)
                                    solver_initial: FloatArray | None = None
                                else:
                                    initial = warm_solutions.get(
                                        state_key, np.zeros(dimension, dtype=np.float64)
                                    ).copy()
                                    solver_initial = initial
                                initial_error = (
                                    1.0
                                    if initialization == "zero"
                                    else relative_energy_error(
                                        matrix, exact_solution, initial
                                    )
                                )
                                rss_before = _rss_bytes()
                                start = time.perf_counter()
                                result = solve_certified_cg(
                                    matrix,
                                    rhs,
                                    target=target,
                                    preconditioner=preconditioner,
                                    initial_solution=solver_initial,
                                    max_iterations=max_iterations,
                                    condition_upper_bound=certificate_condition,
                                    operator_matvec=curvature_matvec,
                                )
                                wall_seconds = time.perf_counter() - start
                                rss_after = _rss_bytes()
                                if initialization == "warm":
                                    warm_solutions[state_key] = result.solution.copy()

                                exact_error = relative_energy_error(
                                    matrix, exact_solution, result.solution
                                )
                                recomputed_residual = rhs - matrix @ result.solution
                                recomputed_certificate = residual_energy_certificate(
                                    matrix,
                                    rhs,
                                    recomputed_residual,
                                    preconditioner=preconditioner,
                                    condition_upper_bound=certificate_condition,
                                )
                                approximate_width_squared = float(rhs @ result.solution)
                                if approximate_width_squared < 0.0:
                                    raise FloatingPointError(
                                        "certified CG produced a negative width squared"
                                    )
                                approximate_width = float(
                                    np.sqrt(approximate_width_squared)
                                )
                                lower_bound = (1.0 - exact_error) * exact_width_squared
                                upper_bound = (1.0 + exact_error) * exact_width_squared
                                tolerance = 256.0 * np.finfo(np.float64).eps * max(
                                    1.0, exact_width_squared
                                )
                                record: dict[str, Any] = {
                                    "seed": seed,
                                    "round": round_index,
                                    "condition_number_requested": condition,
                                    "condition_number": actual_condition,
                                    "damping": damping,
                                    "dimension": dimension,
                                    "sample_count": sample_count,
                                    "action": action_index,
                                    "target_energy_error": target,
                                    "epsilon_bar": target,
                                    "initialization": initialization,
                                    "preconditioner": preconditioner,
                                    "initial_relative_energy_error": initial_error,
                                    "relative_energy_error": exact_error,
                                    "exact_relative_energy_error": exact_error,
                                    "residual_certificate": recomputed_certificate,
                                    "certificate_slack": recomputed_certificate - exact_error,
                                    "target_satisfied": bool(exact_error <= target + tolerance),
                                    "certificate_target_satisfied": bool(
                                        recomputed_certificate <= target + tolerance
                                    ),
                                    "converged": result.converged,
                                    "cg_iterations": result.iterations,
                                    "iterations": result.iterations,
                                    "operator_matvec_count": result.operator_matvecs,
                                    "cg_matvec_count": result.operator_matvecs,
                                    "sample_cvp_count": result.operator_matvecs * sample_count,
                                    "cvp_count": result.operator_matvecs * sample_count,
                                    "curvature_vector_products": result.operator_matvecs
                                    * sample_count,
                                    "relative_residual": result.relative_residual,
                                    "residual_norm": result.residual_norm,
                                    "condition_upper_bound": result.condition_upper_bound,
                                    "exact_width_squared": exact_width_squared,
                                    "approximate_width_squared": approximate_width_squared,
                                    "exact_width": exact_width,
                                    "approximate_width": approximate_width,
                                    "width_squared_relative_error": abs(
                                        approximate_width_squared - exact_width_squared
                                    )
                                    / exact_width_squared,
                                    "width_relative_error": abs(
                                        approximate_width - exact_width
                                    )
                                    / exact_width,
                                    "predictive_width_relative_error": abs(
                                        approximate_width - exact_width
                                    )
                                    / exact_width,
                                    "sandwich_lower_bound": lower_bound,
                                    "sandwich_upper_bound": upper_bound,
                                    "sandwich_lower_slack": approximate_width_squared
                                    - lower_bound,
                                    "sandwich_upper_slack": upper_bound
                                    - approximate_width_squared,
                                    "sandwich_holds": bool(
                                        lower_bound - tolerance
                                        <= approximate_width_squared
                                        <= upper_bound + tolerance
                                    ),
                                    "cg_width_sandwich": bool(
                                        lower_bound - tolerance
                                        <= approximate_width_squared
                                        <= upper_bound + tolerance
                                    ),
                                    "inflated_approximate_width": float(
                                        approximate_width / np.sqrt(1.0 - target)
                                    ),
                                    "optimism_violation": bool(
                                        approximate_width
                                        / np.sqrt(1.0 - target)
                                        + tolerance
                                        < exact_width
                                    ),
                                    "inflation_alpha": float(
                                        np.sqrt((1.0 + target) / (1.0 - target))
                                    ),
                                    "dense_inverse_reference_seconds": reference_seconds,
                                    "wall_time_seconds": wall_seconds,
                                    "rss_before_bytes": rss_before,
                                    "rss_after_bytes": rss_after,
                                    "rss_bytes": rss_after,
                                    "rss_delta_bytes": rss_after - rss_before,
                                    "peak_host_memory_bytes": _peak_host_memory_bytes(),
                                    "operator_storage_bytes": int(features.nbytes),
                                    "dense_reference_storage_bytes": int(
                                        matrix.nbytes + dense_inverse.nbytes
                                    ),
                                }
                                if include_histories:
                                    record["residual_history"] = result.residual_history.tolist()
                                    record["residual_certificate_history"] = (
                                        result.certificate_history.tolist()
                                    )
                                records.append(record)

    failures = [record for record in records if not record["target_satisfied"]]
    certificate_target_failures = [
        record for record in records if not record["certificate_target_satisfied"]
    ]
    certificate_violations = [
        record for record in records if record["certificate_slack"] < -2e-12
    ]
    sandwich_violations = [record for record in records if not record["sandwich_holds"]]
    summary: dict[str, Any] = {
        "experiment": "cg_accuracy",
        "seed": seed,
        "record_count": len(records),
        "energy_targets": list(ENERGY_TARGETS),
        "initializations": list(INITIALIZATIONS),
        "preconditioners": list(PRECONDITIONERS),
        "target_failure_count": len(failures),
        "certificate_target_failure_count": len(certificate_target_failures),
        "residual_certificate_violation_count": len(certificate_violations),
        "sandwich_violation_count": len(sandwich_violations),
        "optimism_violation_count": sum(
            bool(record["optimism_violation"]) for record in records
        ),
        "max_relative_energy_error": max(
            (float(record["relative_energy_error"]) for record in records), default=0.0
        ),
        "total_iterations": sum(int(record["cg_iterations"]) for record in records),
        "total_sample_cvps": sum(int(record["sample_cvp_count"]) for record in records),
        "warm_start_advantage_assumed": False,
        "exact_reference": "scipy.linalg.inv float64 dense inverse",
    }
    return CGAccuracyRun(seed=seed, records=tuple(records), summary=summary)


@dataclass(frozen=True)
class CGPolicyCellRun:
    """One executed LinUCB policy for a fixed CG configuration."""

    seed: int
    epsilon_bar: float
    initialization: str
    preconditioner: str
    records: tuple[dict[str, Any], ...]
    summary: dict[str, Any]


@dataclass(frozen=True)
class CGPolicyStudyRun:
    """All CG policy cells executed with common random numbers for one seed."""

    seed: int
    cells: tuple[CGPolicyCellRun, ...]

    @property
    def records(self) -> tuple[dict[str, Any], ...]:
        return tuple(record for cell in self.cells for record in cell.records)

    @property
    def summaries(self) -> tuple[dict[str, Any], ...]:
        return tuple(cell.summary for cell in self.cells)


def _policy_settings(config: Mapping[str, Any]) -> dict[str, Any]:
    raw_policy = config.get("policy_audit", {})
    if not isinstance(raw_policy, Mapping):
        raise ValueError("policy_audit must be a mapping")
    ridge = _positive_float(config.get("ridge", 1.0), name="ridge")
    noise_std = _positive_float(config.get("noise_std", 0.25), name="noise_std")
    rounds = _positive_int(config.get("rounds", 200), name="rounds")
    configured_actions = _positive_int(
        config.get("action_count", ACTION_COUNT), name="action_count"
    )
    if configured_actions != ACTION_COUNT:
        raise ValueError(
            f"the CG policy audit reuses the fixed K={ACTION_COUNT} linear environment"
        )
    delta = float(raw_policy.get("delta", 0.05))
    if not np.isfinite(delta) or not 0.0 < delta < 1.0:
        raise ValueError("policy_audit.delta must lie strictly between zero and one")
    bonus_scale = float(raw_policy.get("bonus_scale", 1.0))
    if not np.isfinite(bonus_scale) or bonus_scale < 1.0:
        raise ValueError("policy_audit.bonus_scale must be finite and at least one")
    max_iterations = _positive_int(
        raw_policy.get("max_iterations", 4 * FEATURE_DIMENSION),
        name="policy_audit.max_iterations",
    )
    theta_star = np.asarray(
        raw_policy.get("theta_star", default_theta_star()), dtype=np.float64
    )
    if theta_star.shape != (FEATURE_DIMENSION,) or not np.all(np.isfinite(theta_star)):
        raise ValueError(
            f"policy_audit.theta_star must have shape ({FEATURE_DIMENSION},)"
        )
    theta_norm = float(np.linalg.norm(theta_star))
    theta_bound = _positive_float(
        raw_policy.get("theta_bound", theta_norm), name="policy_audit.theta_bound"
    )
    if theta_bound + 1e-14 < theta_norm:
        raise ValueError("policy_audit.theta_bound must be at least ||theta_star||")
    return {
        "ridge": ridge,
        "noise_std": noise_std,
        "rounds": rounds,
        "delta": delta,
        "bonus_scale": bonus_scale,
        "max_iterations": max_iterations,
        "theta_star": theta_star,
        "theta_bound": theta_bound,
    }


def run_cg_policy_cell(
    config: Mapping[str, Any],
    seed: int,
    *,
    epsilon_bar: float,
    initialization: str,
    preconditioner: str,
) -> CGPolicyCellRun:
    """Execute one residual-certified full-Gram LinUCB policy from scratch.

    The curvature is constructed once before action enumeration and is then
    captured by a deterministic matrix-vector oracle.  Each action receives a
    separate CG solve against that same fixed operator.
    """

    seed_everything(seed)
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    target = _positive_float(epsilon_bar, name="epsilon_bar")
    if target >= 1.0 or target not in ENERGY_TARGETS:
        raise ValueError(f"epsilon_bar must be one of {list(ENERGY_TARGETS)}")
    if initialization not in INITIALIZATIONS:
        raise ValueError(f"initialization must be one of {list(INITIALIZATIONS)}")
    if preconditioner not in PRECONDITIONERS:
        raise ValueError(f"preconditioner must be one of {list(PRECONDITIONERS)}")

    settings = _policy_settings(config)
    ridge = float(settings["ridge"])
    noise_std = float(settings["noise_std"])
    variance = noise_std * noise_std
    rounds = int(settings["rounds"])
    theta_star = np.asarray(settings["theta_star"], dtype=np.float64)
    environment_seed = derive_seed(seed, POLICY_EXPERIMENT_NAME, "environment")
    environment = LinearBanditEnvironment(
        environment_seed, noise_std=noise_std, theta_star=theta_star
    )

    dimension = FEATURE_DIMENSION
    feature_bound = environment.feature_norm
    curvature = ridge * np.eye(dimension, dtype=np.float64)
    response_vector = np.zeros(dimension, dtype=np.float64)
    theta_hat = np.zeros(dimension, dtype=np.float64)
    history: list[FloatArray] = []
    warm_solutions: dict[int, FloatArray] = {}
    records: list[dict[str, Any]] = []

    alpha = float(np.sqrt((1.0 + target) / (1.0 - target)))
    cumulative_regret = 0.0
    cumulative_lambda = 0.0
    cumulative_width = 0.0
    cumulative_S = 0.0
    cumulative_all_action_violations = 0
    cumulative_selected_violations = 0
    cumulative_operator_matvecs = 0
    cumulative_sample_cvps = 0
    cumulative_iterations = 0
    total_runtime_seconds = 0.0
    total_cg_seconds = 0.0
    peak_host_memory_bytes = _rss_bytes()
    initial_logdet = dimension * math.log(ridge)

    for round_index in range(1, rounds + 1):
        round_started = time.perf_counter()
        fixed_curvature = np.asarray(curvature, dtype=np.float64).copy()
        fixed_curvature.setflags(write=False)
        history_matrix = (
            np.asarray(np.stack(history), dtype=np.float64)
            if history
            else np.empty((0, dimension), dtype=np.float64)
        )
        history_matrix.setflags(write=False)

        context = environment.draw_context()
        candidates = environment.features(context)
        true_means = np.asarray(candidates @ environment.theta_star, dtype=np.float64)
        predicted_means = np.asarray(candidates @ theta_hat, dtype=np.float64)
        optimal_action = int(np.argmax(true_means))

        beta, gamma_upper = confidence_radius(
            round_index,
            dimension=dimension,
            feature_bound=feature_bound,
            ridge=ridge,
            noise_std=noise_std,
            delta=float(settings["delta"]),
            theta_bound=float(settings["theta_bound"]),
        )
        beta *= float(settings["bonus_scale"])

        reference_started = time.perf_counter()
        factor = la.cho_factor(fixed_curvature, lower=True, check_finite=False)
        exact_solutions = np.asarray(
            la.cho_solve(factor, candidates.T, check_finite=False).T,
            dtype=np.float64,
        )
        exact_widths_squared = np.einsum(
            "ij,ij->i", candidates, exact_solutions, dtype=np.float64
        )
        dense_reference_seconds = time.perf_counter() - reference_started
        if np.any(exact_widths_squared <= 0.0):
            raise FloatingPointError("dense reference produced a nonpositive width")

        eigenvalues = la.eigvalsh(fixed_curvature, check_finite=False)
        condition_number = float(eigenvalues[-1] / eigenvalues[0])
        kappa_bar = float(eigenvalues[-1] / ridge)
        diagonal = (
            np.ones(dimension, dtype=np.float64)
            if preconditioner == "none"
            else np.diag(fixed_curvature).copy()
        )
        residual_condition_bound = _scaled_condition_number(
            fixed_curvature, diagonal
        )

        def curvature_matvec(vector: FloatArray) -> FloatArray:
            # history_matrix is immutable for all action solves in this round.
            return np.asarray(
                ridge * vector
                + history_matrix.T @ (history_matrix @ vector) / variance,
                dtype=np.float64,
            )

        probe = np.linspace(-1.0, 1.0, dimension, dtype=np.float64)
        operator_dense_max_abs = float(
            np.max(np.abs(curvature_matvec(probe) - fixed_curvature @ probe))
        )
        operator_tolerance = 512.0 * np.finfo(np.float64).eps * max(
            1.0,
            float(np.linalg.norm(fixed_curvature, ord=2))
            * float(np.linalg.norm(probe)),
        )
        if operator_dense_max_abs > operator_tolerance:
            raise AssertionError("fixed matrix-free operator disagrees with dense curvature")

        approximate_widths_squared = np.empty(ACTION_COUNT, dtype=np.float64)
        exact_energy_errors = np.empty(ACTION_COUNT, dtype=np.float64)
        initial_energy_errors = np.empty(ACTION_COUNT, dtype=np.float64)
        residual_certificates = np.empty(ACTION_COUNT, dtype=np.float64)
        relative_residuals = np.empty(ACTION_COUNT, dtype=np.float64)
        iterations = np.empty(ACTION_COUNT, dtype=np.int64)
        matvecs = np.empty(ACTION_COUNT, dtype=np.int64)
        solver_seconds = np.empty(ACTION_COUNT, dtype=np.float64)
        target_sandwich_holds: list[bool] = []
        exact_error_sandwich_holds: list[bool] = []
        target_sandwich_lower_slacks: list[float] = []
        target_sandwich_upper_slacks: list[float] = []

        for action in range(ACTION_COUNT):
            rhs = np.asarray(candidates[action], dtype=np.float64)
            exact_solution = exact_solutions[action]
            if initialization == "zero":
                initial_solution: FloatArray | None = None
                initial_vector = np.zeros(dimension, dtype=np.float64)
            else:
                initial_vector = warm_solutions.get(
                    action, np.zeros(dimension, dtype=np.float64)
                ).copy()
                initial_solution = initial_vector
            initial_energy_errors[action] = relative_energy_error(
                fixed_curvature, exact_solution, initial_vector
            )

            solve_started = time.perf_counter()
            result = solve_certified_cg(
                fixed_curvature,
                rhs,
                target=target,
                preconditioner=preconditioner,
                initial_solution=initial_solution,
                max_iterations=int(settings["max_iterations"]),
                condition_upper_bound=residual_condition_bound,
                operator_matvec=curvature_matvec,
            )
            solver_seconds[action] = time.perf_counter() - solve_started
            if not result.converged:
                raise RuntimeError(
                    "CG did not meet its predictable residual certificate; "
                    "the policy refuses an uncertified fallback"
                )
            if initialization == "warm":
                warm_solutions[action] = result.solution.copy()

            exact_error = relative_energy_error(
                fixed_curvature, exact_solution, result.solution
            )
            residual = rhs - fixed_curvature @ result.solution
            residual_certificate = residual_energy_certificate(
                fixed_curvature,
                rhs,
                residual,
                preconditioner=preconditioner,
                condition_upper_bound=residual_condition_bound,
            )
            approximate_width_squared = float(rhs @ result.solution)
            exact_width_squared = float(exact_widths_squared[action])
            tolerance = 1024.0 * np.finfo(np.float64).eps * max(
                1.0, exact_width_squared
            )
            target_lower = (1.0 - target) * exact_width_squared
            target_upper = (1.0 + target) * exact_width_squared
            actual_lower = (1.0 - exact_error) * exact_width_squared
            actual_upper = (1.0 + exact_error) * exact_width_squared
            target_holds = bool(
                target_lower - tolerance
                <= approximate_width_squared
                <= target_upper + tolerance
            )
            actual_holds = bool(
                actual_lower - tolerance
                <= approximate_width_squared
                <= actual_upper + tolerance
            )
            if residual_certificate > target + tolerance:
                raise AssertionError("CG stopped without satisfying its residual certificate")
            if exact_error > residual_certificate + tolerance:
                raise AssertionError("residual certificate did not upper-bound energy error")
            if not target_holds or not actual_holds:
                raise AssertionError("CG predictive width violated its multiplicative sandwich")
            if approximate_width_squared <= 0.0:
                raise FloatingPointError("CG produced a nonpositive predictive width")

            approximate_widths_squared[action] = approximate_width_squared
            exact_energy_errors[action] = exact_error
            residual_certificates[action] = residual_certificate
            relative_residuals[action] = result.relative_residual
            iterations[action] = result.iterations
            matvecs[action] = result.operator_matvecs
            target_sandwich_holds.append(target_holds)
            exact_error_sandwich_holds.append(actual_holds)
            target_sandwich_lower_slacks.append(
                approximate_width_squared - target_lower
            )
            target_sandwich_upper_slacks.append(
                target_upper - approximate_width_squared
            )

        inflated_widths = np.sqrt(
            approximate_widths_squared / (1.0 - target)
        )
        bonuses = beta * inflated_widths
        ucb_scores = predicted_means + bonuses
        optimism_violations = true_means > ucb_scores + 1e-12
        action = int(np.argmax(ucb_scores))
        reward, noise = environment.reward(context, action)
        played = np.asarray(candidates[action], dtype=np.float64).copy()
        pseudo_regret = float(true_means[optimal_action] - true_means[action])
        cumulative_regret += pseudo_regret
        cumulative_all_action_violations += int(np.count_nonzero(optimism_violations))
        cumulative_selected_violations += int(optimism_violations[action])

        played_exact_width_squared = float(exact_widths_squared[action])
        information_increment = float(
            np.log1p(played_exact_width_squared / variance)
        )
        cumulative_lambda += information_increment
        cumulative_width += played_exact_width_squared
        cumulative_S += alpha * alpha * beta * beta
        cumulative_operator_matvecs += int(np.sum(matvecs))
        cumulative_sample_cvps += int(np.sum(matvecs)) * len(history)
        cumulative_iterations += int(np.sum(iterations))
        total_cg_seconds += float(np.sum(solver_seconds))

        curvature_next = fixed_curvature + np.outer(played, played) / variance
        response_next = response_vector + played * reward / variance
        theta_next = np.asarray(
            la.solve(
                curvature_next,
                response_next,
                assume_a="pos",
                check_finite=False,
            ),
            dtype=np.float64,
        )
        endpoint_cholesky = la.cholesky(
            curvature_next, lower=True, check_finite=False
        )
        endpoint_logdet = float(
            2.0 * np.sum(np.log(np.diag(endpoint_cholesky))) - initial_logdet
        )
        dynamic_identity_residual = cumulative_lambda - endpoint_logdet
        width_coefficient = variance + feature_bound * feature_bound / ridge
        width_information_bound = width_coefficient * cumulative_lambda
        theorem_rhs = float(
            2.0
            * np.sqrt(width_coefficient * cumulative_lambda * cumulative_S)
        )
        confidence_ratios = np.abs(
            candidates @ (theta_hat - environment.theta_star)
        ) / np.sqrt(exact_widths_squared)

        round_runtime_seconds = time.perf_counter() - round_started
        total_runtime_seconds += round_runtime_seconds
        peak_host_memory_bytes = max(peak_host_memory_bytes, _rss_bytes())
        record = {
            "seed": int(seed),
            "policy_round": round_index,
            "experiment": POLICY_EXPERIMENT_NAME,
            "method": "full_ggn_cg",
            "executed_policy": True,
            "full_action_enumeration": True,
            "epsilon_bar": target,
            "initialization": initialization,
            "preconditioner": preconditioner,
            "certificate_mode": "predictable_exact_small_scale_condition_bound",
            "policy_used_predictable_valid_certificates": True,
            "context": context.tolist(),
            "action": action,
            "selected_action": action,
            "optimal_action": optimal_action,
            "reward": float(reward),
            "noise": float(noise),
            "pseudo_regret": pseudo_regret,
            "instantaneous_pseudo_regret": pseudo_regret,
            "cumulative_pseudo_regret": cumulative_regret,
            "predicted_means": predicted_means.tolist(),
            "true_means": true_means.tolist(),
            "ucb_scores": ucb_scores.tolist(),
            "bonuses": bonuses.tolist(),
            "exact_widths_squared": exact_widths_squared.tolist(),
            "approximate_widths_squared": approximate_widths_squared.tolist(),
            "predictive_width_relative_errors": (
                np.abs(
                    np.sqrt(approximate_widths_squared)
                    - np.sqrt(exact_widths_squared)
                )
                / np.sqrt(exact_widths_squared)
            ).tolist(),
            "initial_relative_energy_errors": initial_energy_errors.tolist(),
            "exact_relative_energy_errors": exact_energy_errors.tolist(),
            "residual_certificates": residual_certificates.tolist(),
            "relative_residuals": relative_residuals.tolist(),
            "target_sandwich_holds": target_sandwich_holds,
            "exact_error_sandwich_holds": exact_error_sandwich_holds,
            "target_sandwich_lower_slack_min": float(
                min(target_sandwich_lower_slacks)
            ),
            "target_sandwich_upper_slack_min": float(
                min(target_sandwich_upper_slacks)
            ),
            "cg_iterations": iterations.tolist(),
            "cg_iterations_total": int(np.sum(iterations)),
            "operator_matvec_counts": matvecs.tolist(),
            "operator_matvec_count": int(np.sum(matvecs)),
            "curvature_vector_products": int(np.sum(matvecs)),
            "sample_cvp_count": int(np.sum(matvecs)) * len(history),
            "cumulative_operator_matvec_count": cumulative_operator_matvecs,
            "cumulative_sample_cvp_count": cumulative_sample_cvps,
            "solver_wall_time_seconds": float(np.sum(solver_seconds)),
            "dense_reference_wall_time_seconds": dense_reference_seconds,
            "round_runtime_seconds": round_runtime_seconds,
            "runtime_seconds": total_runtime_seconds,
            "rss_bytes": _rss_bytes(),
            "peak_host_memory_bytes": peak_host_memory_bytes,
            "process_peak_host_memory_bytes": _peak_host_memory_bytes(),
            "accelerator_used": False,
            "peak_accelerator_memory_bytes": 0,
            "curvature_operator_build_count": 1,
            "separate_per_action_cg_solves": ACTION_COUNT,
            "same_fixed_operator_reused_across_action_solves": True,
            "operator_dense_probe_max_abs": operator_dense_max_abs,
            "operator_dense_probe_tolerance": operator_tolerance,
            "beta_t": beta,
            "omega_t": beta,
            "alpha_t": alpha,
            "u_t": 1.0,
            "gamma_upper_t": gamma_upper,
            "confidence_ratio_max": float(np.max(confidence_ratios)),
            "confidence_radius_valid_on_path": bool(
                np.max(confidence_ratios) <= beta + 1e-10
            ),
            "optimism_violation_indicators": optimism_violations.tolist(),
            "all_action_optimism_violation_rate": (
                cumulative_all_action_violations / (round_index * ACTION_COUNT)
            ),
            "selected_action_optimism_violation": bool(
                optimism_violations[action]
            ),
            "selected_action_optimism_violation_rate": (
                cumulative_selected_violations / round_index
            ),
            "kappa_t": condition_number,
            "kappa_bar_t": kappa_bar,
            "residual_certificate_condition_bound": residual_condition_bound,
            "kappa_plus_t": 1.0,
            "chi_t": 0.0,
            "psi_t": 0.0,
            "epsilon_lin_t": 0.0,
            "E_t": 0.0,
            "F_t": 0.0,
            "Lambda_t_C": cumulative_lambda,
            "information_increment": information_increment,
            "V_t_C": 0.0,
            "Gamma_t_dynamic": endpoint_logdet,
            "dynamic_identity_residual": dynamic_identity_residual,
            "width_squared_cumulative": cumulative_width,
            "width_information_bound": width_information_bound,
            "width_information_slack": width_information_bound - cumulative_width,
            "S_t": cumulative_S,
            "theorem_rhs": theorem_rhs,
            "theorem_bound_slack": theorem_rhs - cumulative_regret,
        }
        records.append(record)
        history.append(played)
        curvature = np.asarray(curvature_next, dtype=np.float64)
        response_vector = response_next
        theta_hat = theta_next

    all_optimal_actions = {
        environment.optimal_action(context)
        for context in enumerate_rademacher_contexts()
    }
    last = records[-1]
    summary = {
        "experiment": POLICY_EXPERIMENT_NAME,
        "seed": int(seed),
        "epsilon_bar": target,
        "initialization": initialization,
        "preconditioner": preconditioner,
        "rounds": rounds,
        "executed_policy": True,
        "full_action_enumeration": True,
        "policy_used_predictable_valid_certificates": True,
        "certified_execution": all(
            bool(record["confidence_radius_valid_on_path"]) for record in records
        ),
        "confidence_event_realized": all(
            bool(record["confidence_radius_valid_on_path"]) for record in records
        ),
        "context_dependent_optimal_arm": len(all_optimal_actions) > 1,
        "common_random_number_environment_seed": environment_seed,
        "cumulative_pseudo_regret": cumulative_regret,
        "all_action_optimism_violation_rate": float(
            last["all_action_optimism_violation_rate"]
        ),
        "selected_action_optimism_violation_rate": float(
            last["selected_action_optimism_violation_rate"]
        ),
        "Lambda_T_C": cumulative_lambda,
        "S_T": cumulative_S,
        "theorem_rhs": float(last["theorem_rhs"]),
        "theorem_bound_slack": float(last["theorem_bound_slack"]),
        "mean_initial_relative_energy_error": float(
            np.mean(
                [
                    value
                    for record in records
                    for value in record["initial_relative_energy_errors"]
                ]
            )
        ),
        "mean_exact_relative_energy_error": float(
            np.mean(
                [
                    value
                    for record in records
                    for value in record["exact_relative_energy_errors"]
                ]
            )
        ),
        "max_exact_relative_energy_error": float(
            max(
                value
                for record in records
                for value in record["exact_relative_energy_errors"]
            )
        ),
        "max_residual_certificate": float(
            max(
                value
                for record in records
                for value in record["residual_certificates"]
            )
        ),
        "residual_certificate_violation_count": sum(
            value
            > certificate + 1e-12
            for record in records
            for value, certificate in zip(
                record["exact_relative_energy_errors"],
                record["residual_certificates"],
                strict=True,
            )
        ),
        "target_failure_count": sum(
            certificate > target + 1e-12
            for record in records
            for certificate in record["residual_certificates"]
        ),
        "sandwich_violation_count": sum(
            not bool(value)
            for record in records
            for value in record["target_sandwich_holds"]
        ),
        "mean_cg_iterations_per_action": cumulative_iterations
        / (rounds * ACTION_COUNT),
        "total_cg_iterations": cumulative_iterations,
        "total_operator_matvecs": cumulative_operator_matvecs,
        "total_sample_cvps": cumulative_sample_cvps,
        "runtime_seconds": total_runtime_seconds,
        "solver_wall_time_seconds": total_cg_seconds,
        "peak_host_memory_bytes": peak_host_memory_bytes,
        "accelerator_used": False,
        "peak_accelerator_memory_bytes": 0,
        "warm_start_advantage_assumed": False,
        "same_fixed_operator_reused_across_action_solves": True,
        "max_dynamic_identity_abs_residual": max(
            abs(float(record["dynamic_identity_residual"])) for record in records
        ),
        "min_width_information_slack": min(
            float(record["width_information_slack"]) for record in records
        ),
    }
    return CGPolicyCellRun(
        seed=int(seed),
        epsilon_bar=target,
        initialization=initialization,
        preconditioner=preconditioner,
        records=tuple(records),
        summary=summary,
    )


def run_cg_policy_accuracy(
    config: Mapping[str, Any], seed: int
) -> CGPolicyStudyRun:
    """Execute the complete 5 x 2 x 2 policy grid for one evaluation seed."""

    cells = tuple(
        run_cg_policy_cell(
            config,
            seed,
            epsilon_bar=epsilon_bar,
            initialization=initialization,
            preconditioner=preconditioner,
        )
        for epsilon_bar in ENERGY_TARGETS
        for initialization in INITIALIZATIONS
        for preconditioner in PRECONDITIONERS
    )
    return CGPolicyStudyRun(seed=int(seed), cells=cells)


def save_policy_run(
    run: CGPolicyStudyRun,
    output_dir: str | Path,
    config: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    """Save policy rounds separately from the pre-existing static solver audit."""

    destination = Path(output_dir)
    manifest_config = dict(config)
    manifest_config["execution"] = {
        "driver": "run_cg_accuracy",
        "audit": "executed_policy",
        "seed": run.seed,
        "energy_targets": list(ENERGY_TARGETS),
        "initializations": list(INITIALIZATIONS),
        "preconditioners": list(PRECONDITIONERS),
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
    for summary in run.summaries:
        append_jsonl(summary_path, summary)
    return destination


def run_policy_experiment(
    config: Mapping[str, Any],
    *,
    seed_set: str,
    output_root: str | Path,
    overwrite: bool = False,
) -> tuple[CGPolicyStudyRun, ...]:
    results: list[CGPolicyStudyRun] = []
    for seed in get_seed_set(config, seed_set):
        run = run_cg_policy_accuracy(config, seed)
        destination = (
            Path(output_root)
            / POLICY_EXPERIMENT_NAME
            / str(config.get("profile", "default"))
            / seed_set
            / f"seed-{seed}"
        )
        save_policy_run(run, destination, config, overwrite=overwrite)
        results.append(run)
    return tuple(results)


def save_run(
    run: CGAccuracyRun,
    output_dir: str | Path,
    config: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    destination = Path(output_dir)
    manifest_config = dict(config)
    manifest_config["execution"] = {
        "driver": "run_cg_accuracy",
        "seed": run.seed,
        "energy_targets": list(ENERGY_TARGETS),
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
) -> tuple[CGAccuracyRun, ...]:
    results: list[CGAccuracyRun] = []
    for seed in get_seed_set(config, seed_set):
        run = run_cg_accuracy(config, seed)
        destination = (
            Path(output_root)
            / str(config.get("name", "cg_accuracy"))
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
        "--audit",
        choices=("solver", "policy"),
        default="solver",
        help="run the static dense-reference solve audit or executed-policy audit",
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
    if args.audit == "policy":
        results = run_policy_experiment(
            config,
            seed_set=args.seed_set,
            output_root=args.output_root,
            overwrite=args.overwrite,
        )
        record_count = sum(len(run.records) for run in results)
        cell_count = sum(len(run.cells) for run in results)
    else:
        results = run_experiment(
            config,
            seed_set=args.seed_set,
            output_root=args.output_root,
            overwrite=args.overwrite,
        )
        record_count = sum(len(run.records) for run in results)
        cell_count = None
    print(
        json.dumps(
            {
                "experiment": config["name"],
                "audit": args.audit,
                "profile": args.profile,
                "seed_set": args.seed_set,
                "seeds": [run.seed for run in results],
                "policy_cells": cell_count,
                "records": record_count,
                "output_root": str(args.output_root),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CGAccuracyRun",
    "CGPolicyCellRun",
    "CGPolicyStudyRun",
    "CertifiedCGResult",
    "DEFAULT_CONFIG",
    "ENERGY_TARGETS",
    "INITIALIZATIONS",
    "PRECONDITIONERS",
    "make_spd_problem",
    "relative_energy_error",
    "residual_energy_certificate",
    "run_cg_accuracy",
    "run_cg_policy_accuracy",
    "run_cg_policy_cell",
    "run_experiment",
    "run_policy_experiment",
    "save_policy_run",
    "save_run",
    "solve_certified_cg",
]
