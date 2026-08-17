from __future__ import annotations

import numpy as np
import pytest

from experiments.curvature_operators import (
    ConjugateGradientError,
    DenseSPDLinearOperator,
    conjugate_gradient,
)


def _spd_matrix(seed: int, dimension: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    factor = rng.normal(size=(dimension, dimension))
    return factor.T @ factor + 0.5 * np.eye(dimension)


def test_dense_operator_validates_spd_and_returns_defensive_copies() -> None:
    matrix = _spd_matrix(11, 5)
    operator = DenseSPDLinearOperator(matrix)
    vector = np.arange(5, dtype=np.float64)

    np.testing.assert_allclose(operator.matvec(vector), matrix @ vector)
    exported = operator.to_dense()
    exported[0, 0] = -1.0
    np.testing.assert_allclose(operator.to_dense(), matrix)

    with pytest.raises(ValueError, match="symmetric"):
        DenseSPDLinearOperator(np.asarray([[1.0, 0.2], [0.0, 1.0]]))
    with pytest.raises(ValueError, match="positive definite"):
        DenseSPDLinearOperator(np.diag([1.0, 0.0]))
    with pytest.raises(ValueError, match="finite"):
        DenseSPDLinearOperator(np.asarray([[np.nan]]))


def test_conjugate_gradient_matches_dense_solution_and_supports_warm_starts() -> None:
    matrix = _spd_matrix(12, 8)
    rhs = np.random.default_rng(13).normal(size=8)
    exact = np.linalg.solve(matrix, rhs)

    cold = conjugate_gradient(matrix, rhs, tolerance=1e-12, max_iterations=8)
    warm = conjugate_gradient(
        DenseSPDLinearOperator(matrix),
        rhs,
        tolerance=1e-12,
        max_iterations=8,
        initial_solution=0.8 * exact,
    )

    assert cold.converged and warm.converged
    np.testing.assert_allclose(cold.solution, exact, rtol=2e-11, atol=2e-11)
    np.testing.assert_allclose(warm.solution, exact, rtol=2e-11, atol=2e-11)
    assert cold.relative_residual_norm <= 1e-12
    assert warm.relative_residual_norm <= 1e-12


def test_conjugate_gradient_handles_zero_rhs_and_reports_budget_exhaustion() -> None:
    matrix = _spd_matrix(14, 4)
    zero = conjugate_gradient(matrix, np.zeros(4), max_iterations=0)
    assert zero.converged
    assert zero.iterations == 0
    np.testing.assert_array_equal(zero.solution, np.zeros(4))

    with pytest.raises(ConjugateGradientError) as raised:
        conjugate_gradient(matrix, np.ones(4), tolerance=0.0, max_iterations=0)
    assert not raised.value.result.converged
    assert raised.value.result.iterations == 0

    exhausted = conjugate_gradient(
        matrix,
        np.ones(4),
        tolerance=0.0,
        max_iterations=0,
        raise_on_nonconvergence=False,
    )
    assert not exhausted.converged


def test_conjugate_gradient_fails_closed_on_non_spd_callable() -> None:
    with pytest.raises(ArithmeticError, match="nonpositive"):
        conjugate_gradient(
            lambda vector: -vector,
            np.ones(3),
            max_iterations=3,
        )
