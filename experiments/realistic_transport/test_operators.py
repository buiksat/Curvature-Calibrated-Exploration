from __future__ import annotations

import numpy as np
import pytest
from experiments.realistic_transport.operators import (
    build_nystrom,
    build_nystrom_approximation,
    build_operational_nystrom,
    certified_cg_widths,
    certify_cg_width,
    certify_cg_width_map,
    conjugate_gradient_fixed,
    ConjugateGradientError,
    DenseSPDOperator,
    diagnose_operational_nystrom,
    diagnose_exact_width,
    exact_inverse_width,
    exact_widths,
    FLOAT64_CERTIFICATE_DIAGNOSTIC,
    LowRankRidgeOperator,
    NumericalAuditError,
    thompson_distance,
)


def _spd_with_condition(seed: int, dimension: int, condition: float) -> np.ndarray:
    generator = np.random.default_rng(seed)
    orthogonal, _ = np.linalg.qr(generator.normal(size=(dimension, dimension)))
    eigenvalues = np.geomspace(1.0, condition, dimension)
    return np.asarray((orthogonal * eigenvalues) @ orthogonal.T, dtype=np.float64)


def test_nystrom_is_deterministic_psd_and_satisfies_operator_sandwich() -> None:
    gradients = np.random.default_rng(101).normal(size=(48, 17)) / 3.0
    first = build_nystrom_approximation(
        gradients, target_rank=6, sketch_seed=90210, ridge=1.3
    )
    second = build_nystrom_approximation(
        gradients, target_rank=6, sketch_seed=90210, ridge=1.3
    )

    np.testing.assert_array_equal(first.sketch, second.sketch)
    np.testing.assert_allclose(
        first.approximate_hessian, second.approximate_hessian, rtol=0.0, atol=0.0
    )
    assert first.sketch_digest == second.sketch_digest
    assert np.linalg.eigvalsh(first.approximate_hessian)[0] >= -1e-11
    assert np.linalg.eigvalsh(first.residual_hessian)[0] >= -1e-11
    np.testing.assert_allclose(
        first.exact_hessian,
        first.approximate_hessian + first.residual_hessian,
        rtol=2e-12,
        atol=2e-12,
    )
    assert first.factors.trace_tail >= first.factors.operator_tail >= 0.0
    assert 0.0 < first.factors.operational_kappa_minus_trace <= 1.0
    assert (
        first.factors.operational_kappa_minus_trace
        <= first.factors.diagnostic_kappa_minus_operator_tail
        <= 1.0
    )
    lower = (
        first.algorithm_operator
        - first.factors.operational_kappa_minus_trace * first.exact_current_operator
    )
    upper = first.exact_current_operator - first.algorithm_operator
    assert np.linalg.eigvalsh(lower)[0] >= -1e-10
    assert np.linalg.eigvalsh(upper)[0] >= -1e-10
    assert first.certificate_class == FLOAT64_CERTIFICATE_DIAGNOSTIC


def test_nystrom_exact_rank_rank_zero_and_empty_history() -> None:
    generator = np.random.default_rng(102)
    left = generator.normal(size=(25, 3))
    right = generator.normal(size=(3, 11))
    gradients = left @ right
    exact_rank = build_nystrom_approximation(
        gradients, target_rank=3, sketch_seed=7, ridge=0.75
    )
    np.testing.assert_allclose(
        exact_rank.approximate_hessian,
        exact_rank.exact_hessian,
        rtol=2e-10,
        atol=2e-10,
    )
    assert exact_rank.factors.trace_tail == pytest.approx(0.0, abs=2e-10)

    rank_zero = build_nystrom_approximation(
        gradients, target_rank=0, sketch_seed=7, ridge=0.75
    )
    np.testing.assert_array_equal(rank_zero.approximate_hessian, np.zeros((11, 11)))
    np.testing.assert_allclose(rank_zero.residual_hessian, rank_zero.exact_hessian)
    assert rank_zero.factors.operational_kappa_minus_trace == pytest.approx(
        0.75 / (0.75 + np.trace(rank_zero.exact_hessian))
    )

    empty = build_nystrom_approximation(
        np.empty((0, 11)), target_rank=3, sketch_seed=7, ridge=0.75
    )
    np.testing.assert_array_equal(empty.exact_hessian, np.zeros((11, 11)))
    np.testing.assert_array_equal(empty.approximate_hessian, np.zeros((11, 11)))
    np.testing.assert_array_equal(empty.residual_hessian, np.zeros((11, 11)))
    assert empty.factors.operational_kappa_minus_trace == 1.0
    assert empty.factors.diagnostic_generalized_kappa_minus == pytest.approx(1.0)
    assert empty.retained_trace_fraction is None
    assert empty.spectral_tail_fraction is None


def test_nystrom_accepts_a_frozen_caller_supplied_sketch() -> None:
    gradients = np.random.default_rng(151).normal(size=(20, 9))
    sketch = np.random.default_rng(152).normal(size=(9, 6))
    direct = build_nystrom(gradients, 4, sketch, ridge=1.0, oversampling=2)
    repeated = build_nystrom(gradients, 4, sketch.copy(), ridge=1.0, oversampling=2)
    assert direct.sketch_seed is None
    assert direct.sketch_size == 6
    assert direct.sketch_digest == repeated.sketch_digest
    np.testing.assert_array_equal(
        direct.approximate_hessian, repeated.approximate_hessian
    )
    hessian = gradients.T @ gradients
    gram = sketch.T @ hessian @ sketch
    eigenvalues, eigenvectors = np.linalg.eigh(0.5 * (gram + gram.T))
    inverse_values = np.where(
        eigenvalues > direct.pseudoinverse_cutoff, 1.0 / eigenvalues, 0.0
    )
    pseudoinverse = (eigenvectors * inverse_values) @ eigenvectors.T
    formula = hessian @ sketch @ pseudoinverse @ sketch.T @ hessian
    np.testing.assert_allclose(
        direct.untruncated_hessian, formula, rtol=2e-11, atol=2e-11
    )


def test_operational_nystrom_uses_low_rank_matvec_and_matches_dense_audit() -> None:
    gradients = np.random.default_rng(160).normal(size=(31, 19))
    approximation = build_operational_nystrom(
        gradients, target_rank=5, sketch_seed=161, ridge=0.8
    )
    assert isinstance(approximation.operator, LowRankRidgeOperator)
    assert approximation.factor.shape == (19, 5)
    assert approximation.operator_storage_bytes < 19 * 19 * 8
    assert approximation.trace_tail >= 0.0
    assert 0.0 < approximation.operational_kappa_minus <= 1.0
    dense_reference = build_nystrom(gradients, 5, 161, ridge=0.8)
    np.testing.assert_allclose(
        approximation.factor @ approximation.factor.T,
        dense_reference.approximate_hessian,
        rtol=2e-11,
        atol=2e-11,
    )

    diagnostic = diagnose_operational_nystrom(approximation, gradients)
    assert diagnostic.operator_tail <= approximation.trace_tail + 1e-9
    assert diagnostic.oracle_generalized_kappa_minus + 1e-10 >= (
        approximation.operational_kappa_minus
    )
    dense = approximation.operator.to_dense()
    query = np.random.default_rng(162).normal(size=19)
    np.testing.assert_allclose(
        approximation.operator.matvec(query), dense @ query, rtol=1e-13, atol=1e-13
    )
    np.testing.assert_allclose(
        approximation.operator.solve_cholesky(query),
        np.linalg.solve(dense, query),
        rtol=2e-12,
        atol=2e-12,
    )


@pytest.mark.parametrize("condition", [1.0, 1e4, 1e8])
def test_cg_width_certificates_hold_across_condition_numbers(condition: float) -> None:
    matrix = _spd_with_condition(201, 12, condition)
    operator = DenseSPDOperator(matrix)
    query = np.random.default_rng(202).normal(size=12)
    certificate = certify_cg_width(
        operator,
        query,
        lower_eigenvalue_bound=1.0,
        upper_eigenvalue_bound=condition,
        relative_tolerance=1e-12,
        max_iterations=48,
    )
    diagnostic = diagnose_exact_width(operator, certificate)
    recomputed = query - operator.to_dense() @ certificate.cg.solution

    assert certificate.upper_width >= diagnostic.exact_width * (1.0 - 2e-10)
    assert certificate.lower_width <= diagnostic.exact_width * (1.0 + 2e-10)
    assert certificate.sharpness_factor >= diagnostic.upper_over_exact - 2e-10
    assert certificate.cg.total_matvec_count == (
        certificate.cg.algorithm_matvec_count + certificate.cg.audit_matvec_count
    )
    assert certificate.cg.algorithm_matvec_count == certificate.cg.iterations + 1
    assert certificate.cg.audit_matvec_count == 1
    np.testing.assert_allclose(certificate.cg.true_residual, recomputed)
    assert certificate.cg.true_residual_norm == pytest.approx(
        np.linalg.norm(recomputed)
    )
    assert certificate.cg.certificate_class == FLOAT64_CERTIFICATE_DIAGNOSTIC


def test_cg_zero_rhs_exact_initial_solution_one_dimension_and_nonconvergence() -> None:
    matrix = np.asarray([[4.0]])
    zero = certify_cg_width(
        matrix,
        np.zeros(1),
        lower_eigenvalue_bound=4.0,
        upper_eigenvalue_bound=4.0,
        relative_tolerance=1e-4,
        max_iterations=1,
    )
    assert zero.upper_width == 0.0
    assert zero.lower_width == 0.0
    assert zero.sharpness_factor == 1.0
    assert zero.cg.iterations == 0
    assert zero.cg.converged
    assert diagnose_exact_width(matrix, zero).upper_over_exact is None

    exact_initial = conjugate_gradient_fixed(
        matrix,
        np.asarray([2.0]),
        relative_tolerance=1e-14,
        initial_solution=np.asarray([0.5]),
        max_iterations=1,
    )
    assert exact_initial.converged
    assert exact_initial.iterations == 0
    np.testing.assert_array_equal(exact_initial.solution, np.asarray([0.5]))

    one_dimensional = conjugate_gradient_fixed(
        matrix, np.asarray([2.0]), relative_tolerance=0.0, max_iterations=1
    )
    np.testing.assert_allclose(one_dimensional.solution, np.asarray([0.5]))

    with pytest.raises(ConjugateGradientError) as raised:
        conjugate_gradient_fixed(
            np.diag([1.0, 2.0]),
            np.ones(2),
            relative_tolerance=0.0,
            max_iterations=0,
        )
    assert raised.value.result.termination_reason == "iteration_limit"
    preserved = conjugate_gradient_fixed(
        np.diag([1.0, 2.0]),
        np.ones(2),
        relative_tolerance=0.0,
        max_iterations=0,
        raise_on_nonconvergence=False,
    )
    assert not preserved.converged
    assert preserved.iterations == 0


def test_operator_snapshot_is_defensive_and_rejects_changing_callable() -> None:
    matrix = _spd_with_condition(301, 5, 30.0)
    original = matrix.copy()
    operator = DenseSPDOperator(matrix)
    matrix[0, 0] = -1e9
    np.testing.assert_allclose(operator.to_dense(), original)

    with pytest.raises(TypeError, match="fixed-operator"):
        conjugate_gradient_fixed(lambda value: value, np.ones(5))


def test_all_action_width_map_reuses_one_snapshot_without_refinement() -> None:
    matrix = _spd_with_condition(401, 7, 50.0)
    queries = np.random.default_rng(402).normal(size=(5, 7))
    width_map = certify_cg_width_map(
        matrix,
        queries,
        lower_eigenvalue_bound=1.0,
        upper_eigenvalue_bound=50.0,
        relative_tolerance=1e-4,
        max_iterations=7,
    )
    assert len(width_map.certificates) == 5
    assert width_map.total_iterations == sum(
        item.cg.iterations for item in width_map.certificates
    )
    assert {item.cg.operator_fingerprint for item in width_map.certificates} == {
        width_map.operator_fingerprint
    }
    for action, query in enumerate(queries):
        selected = width_map.selected(action)
        assert selected is width_map.certificates[action]
        assert selected.upper_width == width_map.upper_widths[action]
        assert selected.sharpness_factor == width_map.sharpness_factors[action]
        diagnostic = diagnose_exact_width(matrix, selected)
        assert selected.upper_width >= diagnostic.exact_width - 1e-10
        assert exact_inverse_width(matrix, query) == pytest.approx(
            diagnostic.exact_width
        )

    compatibility_map = certified_cg_widths(
        matrix,
        queries,
        lower_eigenvalue_bound=1.0,
        upper_eigenvalue_bound=50.0,
        rel_tol=1e-4,
        max_iterations=7,
    )
    np.testing.assert_allclose(compatibility_map.upper_widths, width_map.upper_widths)
    np.testing.assert_allclose(
        exact_widths(matrix, queries),
        [exact_inverse_width(matrix, query) for query in queries],
    )


def test_thompson_distance_uses_generalized_spd_eigenvalues() -> None:
    reference = np.diag([1.0, 2.0, 4.0])
    current = np.diag([2.0, 1.0, 8.0])
    expected = np.log(2.0)
    assert thompson_distance(reference, current) == pytest.approx(expected)
    assert thompson_distance(current, reference) == pytest.approx(expected)


def test_bad_spectral_bounds_and_material_asymmetry_fail_closed() -> None:
    matrix = np.diag([1.0, 3.0])
    with pytest.raises(NumericalAuditError, match="lower_eigenvalue_bound"):
        certify_cg_width(
            matrix,
            np.ones(2),
            lower_eigenvalue_bound=1.1,
            upper_eigenvalue_bound=3.0,
            relative_tolerance=1e-4,
        )
    with pytest.raises(NumericalAuditError, match="upper_eigenvalue_bound"):
        certify_cg_width(
            matrix,
            np.ones(2),
            lower_eigenvalue_bound=1.0,
            upper_eigenvalue_bound=2.9,
            relative_tolerance=1e-4,
        )
    with pytest.raises(NumericalAuditError, match="symmetry"):
        DenseSPDOperator(np.asarray([[2.0, 0.1], [0.0, 2.0]]))


@pytest.mark.parametrize("scale", [1e-100, 1e100])
def test_width_certificate_is_scale_aware(scale: float) -> None:
    matrix = scale * np.diag([1.0, 2.0, 4.0])
    query = scale * np.asarray([1.0, -0.5, 0.25])
    certificate = certify_cg_width(
        matrix,
        query,
        lower_eigenvalue_bound=scale,
        upper_eigenvalue_bound=4.0 * scale,
        relative_tolerance=1e-12,
        max_iterations=3,
    )
    diagnostic = diagnose_exact_width(matrix, certificate)
    assert np.isfinite(certificate.upper_width)
    assert certificate.upper_width >= diagnostic.exact_width * (1.0 - 1e-10)
    assert certificate.lower_width <= diagnostic.exact_width * (1.0 + 1e-10)
