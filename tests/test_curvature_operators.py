from __future__ import annotations

import copy

import numpy as np
import pytest

from experiments.curvature_operators import (
    CurvatureOperator,
    FixedGaussianSketchCurvatureOperator,
    conjugate_gradient,
)


def test_weighted_curvature_is_symmetric_spd_and_matches_dense_matvec() -> None:
    rng = np.random.default_rng(12)
    features = rng.normal(size=(17, 6))
    weights = rng.uniform(0.1, 2.0, size=17)
    operator = CurvatureOperator(
        features,
        damping=0.35,
        noise_variance=1.7,
        weights=weights,
    )

    dense = operator.to_dense()
    vector = rng.normal(size=6)
    vectors = rng.normal(size=(4, 6))

    assert dense.dtype == np.float64
    assert operator.matvec(vector).dtype == np.float64
    np.testing.assert_allclose(dense, dense.T, rtol=0.0, atol=1e-14)
    assert np.linalg.eigvalsh(dense)[0] >= operator.damping
    np.testing.assert_allclose(
        operator.matvec(vector), dense @ vector, rtol=2e-15, atol=2e-15
    )
    np.testing.assert_allclose(
        operator.matmat(vectors), vectors @ dense, rtol=2e-15, atol=2e-15
    )
    np.testing.assert_allclose(
        operator.diagonal(), np.diag(dense), rtol=2e-15, atol=2e-15
    )


def test_random_sketch_is_drawn_once_and_fixed_during_cg() -> None:
    rng = np.random.default_rng(91)
    features = rng.normal(size=(24, 7))
    operator = FixedGaussianSketchCurvatureOperator(
        features,
        damping=0.8,
        noise_variance=1.3,
        sketch_size=11,
        rng=rng,
    )
    state_after_construction = copy.deepcopy(rng.bit_generator.state)
    vector = rng.normal(size=7)
    # Account for the deliberate vector draw, then ensure operator calls use no RNG.
    state_before_calls = copy.deepcopy(rng.bit_generator.state)

    first = operator.matvec(vector)
    second = operator.matvec(vector)
    result = conjugate_gradient(
        operator, vector, tolerance=1e-12, max_iterations=14
    )

    assert state_after_construction != state_before_calls
    assert rng.bit_generator.state == state_before_calls
    np.testing.assert_array_equal(first, second)
    assert result.converged
    with pytest.raises(ValueError):
        operator.projection[0, 0] = 0.0


def test_invalid_curvature_fails_instead_of_repairing_inputs() -> None:
    with pytest.raises(ValueError, match="weights must be nonnegative"):
        CurvatureOperator(
            np.eye(2), damping=1.0, weights=np.array([1.0, -1.0])
        )
    with pytest.raises(ValueError, match="strictly positive"):
        CurvatureOperator(np.eye(2), damping=0.0)
