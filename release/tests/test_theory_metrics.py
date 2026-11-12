from __future__ import annotations

import numpy as np
import pytest

from experiments.curvature_operators import CurvatureOperator
from experiments.theory_metrics import (
    cg_sandwich,
    cg_width,
    dense_width,
    dynamic_rank_trace_upper_bound,
    dynamic_logdet_metrics,
    endpoint_rank_trace_logdet_bound,
    generalized_eigenvalues,
    kappa_plus,
    rank_sensitive_variation_bound,
    width_sum_inequality,
)


def test_dense_and_converged_cg_widths_agree() -> None:
    rng = np.random.default_rng(4)
    operator = CurvatureOperator(
        rng.normal(size=(20, 8)), damping=1.2, noise_variance=2.5
    )
    feature = rng.normal(size=8)

    dense = dense_width(operator, feature)
    approximate = cg_width(
        operator, feature, tolerance=1e-13, max_iterations=16
    )

    assert approximate.cg.converged
    np.testing.assert_allclose(approximate.width, dense, rtol=2e-12, atol=2e-13)


def test_truncated_cg_width_obeys_energy_error_sandwich() -> None:
    rng = np.random.default_rng(44)
    feature_rows = rng.normal(size=(16, 5)) * np.array([0.2, 0.5, 1.0, 2.0, 4.0])
    operator = CurvatureOperator(feature_rows, damping=0.7)
    feature = rng.normal(size=5)
    truncated = cg_width(
        operator,
        feature,
        tolerance=0.0,
        max_iterations=1,
        raise_on_nonconvergence=False,
    )
    sandwich = cg_sandwich(operator, feature, truncated.solution)

    assert 0.0 < sandwich.relative_energy_error < 1.0
    assert sandwich.lower_bound <= sandwich.approximate_width_squared
    assert sandwich.approximate_width_squared <= sandwich.upper_bound


def _nonmonotone_sequence() -> tuple[list[CurvatureOperator], np.ndarray, float, float]:
    damping = 0.6
    noise_variance = 1.4
    played = np.array(
        [
            [1.0, -0.2, 0.4],
            [0.1, 0.8, -0.5],
            [-0.6, 0.3, 0.9],
        ],
        dtype=np.float64,
    )
    empty = np.empty((0, 3), dtype=np.float64)
    operators = [
        CurvatureOperator(empty, damping=damping, noise_variance=noise_variance),
        CurvatureOperator(
            np.array([[0.2, 0.5, -0.1]]),
            damping=damping,
            noise_variance=noise_variance,
        ),
        CurvatureOperator(
            np.array([[0.7, -0.2, 0.4], [-0.3, 0.1, 0.5]]),
            damping=damping,
            noise_variance=noise_variance,
            weights=np.array([0.4, 1.1]),
        ),
        CurvatureOperator(
            np.array([[0.1, -0.4, 0.2]]),
            damping=damping,
            noise_variance=noise_variance,
            weights=np.array([0.3]),
        ),
    ]
    return operators, played, damping, noise_variance


def test_dynamic_logdet_identity_for_nonmonotone_curvature() -> None:
    operators, played, _, noise_variance = _nonmonotone_sequence()
    metrics = dynamic_logdet_metrics(
        operators, played, noise_variance=noise_variance
    )

    np.testing.assert_allclose(
        metrics.information_complexity,
        metrics.identity_right_hand_side,
        rtol=2e-12,
        atol=2e-13,
    )
    assert metrics.variation_charge > 0.0
    assert metrics.information_complexity <= metrics.dynamic_potential + 1e-13
    for perturbation in metrics.normalized_perturbations:
        assert np.linalg.eigvalsh(np.eye(3) + perturbation)[0] > 0.0


def test_dynamic_width_sum_inequality() -> None:
    operators, played, damping, noise_variance = _nonmonotone_sequence()
    feature_bound = float(np.max(np.linalg.norm(played, axis=1)))
    result = width_sum_inequality(
        operators,
        played,
        damping=damping,
        noise_variance=noise_variance,
        feature_bound=feature_bound,
    )

    assert result.width_sum <= result.information_bound + 1e-13
    assert result.information_bound <= result.dynamic_bound + 1e-13


def test_rank_sensitive_variation_keeps_positive_eigenvalue_contribution() -> None:
    perturbation = np.diag([-0.2, 0.0, 0.5]).astype(np.float64)
    result = rank_sensitive_variation_bound(
        perturbation, rank_bound=1, nu=0.2
    )

    np.testing.assert_array_equal(result.negative_eigenvalues, [-0.2])
    np.testing.assert_array_equal(result.positive_eigenvalues, [0.5])
    assert result.negative_rank == 1
    assert result.negative_log_contribution == pytest.approx(-np.log(0.8))
    assert result.positive_log_contribution == pytest.approx(np.log(1.5))
    assert result.transition_logdeterminant == pytest.approx(np.log(1.2))
    assert result.variation_charge == 0.0
    assert result.upper_bound == pytest.approx(-np.log(0.8))
    assert result.slack >= 0.0
    assert result.eigenvalues.dtype == np.float64
    assert result.eigenvalues.flags.writeable is False

    positive_only = rank_sensitive_variation_bound(
        np.diag([0.0, 0.25, 1.0]), rank_bound=0, nu=0.0
    )
    assert positive_only.negative_rank == 0
    assert positive_only.positive_log_contribution > 0.0
    assert positive_only.variation_charge == 0.0
    assert positive_only.upper_bound == 0.0


def test_rank_sensitive_variation_checks_rank_and_spectral_floor() -> None:
    perturbation = np.diag([-0.3, -0.1, 0.2]).astype(np.float64)

    with pytest.raises(ValueError, match="negative eigenvalue rank"):
        rank_sensitive_variation_bound(perturbation, rank_bound=1, nu=0.3)
    with pytest.raises(ValueError, match="spectral floor"):
        rank_sensitive_variation_bound(perturbation, rank_bound=2, nu=0.25)
    with pytest.raises(ValueError, match="strictly less than one"):
        rank_sensitive_variation_bound(perturbation, rank_bound=2, nu=1.0)


def test_endpoint_rank_trace_bound_and_rank_zero_case() -> None:
    increment = np.diag([2.0, 1.0, 0.0]).astype(np.float64)
    result = endpoint_rank_trace_logdet_bound(
        increment,
        damping=0.5,
        rank_bound=2,
        trace_bound=3.0,
    )

    assert result.positive_rank == 2
    assert result.trace == 3.0
    assert result.endpoint_logdeterminant == pytest.approx(np.log(15.0))
    assert result.upper_bound == pytest.approx(2.0 * np.log(4.0))
    assert result.slack >= 0.0

    zero = endpoint_rank_trace_logdet_bound(
        np.zeros((3, 3), dtype=np.float64),
        damping=0.5,
        rank_bound=0,
        trace_bound=5.0,
    )
    assert zero.positive_rank == 0
    assert zero.endpoint_logdeterminant == 0.0
    assert zero.upper_bound == 0.0


def test_endpoint_rank_trace_bound_accepts_rotated_low_rank_psd() -> None:
    rotation, _ = np.linalg.qr(
        np.array(
            [
                [1.0, 2.0, 3.0, 4.0, 5.0],
                [2.0, -1.0, 0.5, 3.0, -2.0],
                [0.5, 1.5, -2.0, 1.0, 4.0],
                [-1.0, 0.25, 2.0, -3.0, 1.0],
                [3.0, -2.0, 1.0, 0.5, -1.0],
            ],
            dtype=np.float64,
        )
    )
    increment = rotation @ np.diag([3.0, 1.0, 0.0, 0.0, 0.0]) @ rotation.T

    result = endpoint_rank_trace_logdet_bound(
        increment,
        damping=0.75,
        rank_bound=2,
        trace_bound=np.nextafter(4.0, np.inf),
    )

    assert result.positive_rank == 2
    assert result.numerical_zero_count == 3
    assert result.eigenvalue_sign_tolerance > 0.0
    assert result.endpoint_logdeterminant <= result.upper_bound + 1e-13


def test_endpoint_rank_trace_bound_rejects_invalid_premises() -> None:
    with pytest.raises(ValueError, match="positive semidefinite"):
        endpoint_rank_trace_logdet_bound(
            np.diag([1.0, -0.1]),
            damping=1.0,
            rank_bound=1,
            trace_bound=1.0,
        )
    with pytest.raises(ValueError, match="positive rank"):
        endpoint_rank_trace_logdet_bound(
            np.diag([1.0, 0.5]),
            damping=1.0,
            rank_bound=1,
            trace_bound=1.5,
        )
    with pytest.raises(ValueError, match="exceeds trace_bound"):
        endpoint_rank_trace_logdet_bound(
            np.diag([1.0, 0.5]),
            damping=1.0,
            rank_bound=2,
            trace_bound=1.4,
        )


def test_combined_dynamic_rank_trace_upper_bound() -> None:
    result = dynamic_rank_trace_upper_bound(
        np.diag([2.0, 1.0, 0.0]),
        (
            np.diag([-0.25, 0.05, 0.0]),
            np.diag([0.2, 0.0, 0.1]),
        ),
        damping=0.5,
        endpoint_rank_bound=2,
        endpoint_trace_bound=3.0,
        variation_rank_bounds=(1, 0),
        variation_nu_bounds=(0.25, 0.0),
    )

    assert len(result.transitions) == 2
    assert result.transitions[0].variation_charge > 0.0
    assert result.transitions[1].variation_charge == 0.0
    assert result.dynamic_potential == pytest.approx(
        result.endpoint.endpoint_logdeterminant + result.variation_charge
    )
    assert result.upper_bound == pytest.approx(
        result.endpoint.upper_bound + result.variation_upper_bound
    )
    assert result.dynamic_potential <= result.upper_bound + 1e-14

    with pytest.raises(ValueError, match="variation_rank_bounds"):
        dynamic_rank_trace_upper_bound(
            np.zeros((2, 2), dtype=np.float64),
            (np.zeros((2, 2), dtype=np.float64),),
            damping=1.0,
            endpoint_rank_bound=0,
            endpoint_trace_bound=0.0,
            variation_rank_bounds=(),
            variation_nu_bounds=(0.0,),
        )


def test_roundwise_scalar_width_rescaling_preserves_scores_and_action() -> None:
    means = np.array([0.75, -0.25, 0.5, 0.0], dtype=np.float64)
    widths = np.array([0.25, 0.5, 0.125, 0.75], dtype=np.float64)
    bonus_coefficient = np.float64(1.5)
    width_scale = np.float64(2.0)

    original_scores = means + bonus_coefficient * widths
    rescaled_scores = means + (bonus_coefficient / width_scale) * (
        width_scale * widths
    )

    np.testing.assert_array_equal(rescaled_scores, original_scores)
    assert np.flatnonzero(original_scores == np.max(original_scores)).tolist() == [0, 3]
    assert int(np.argmax(rescaled_scores)) == int(np.argmax(original_scores)) == 0


def test_width_sum_accepts_roundoff_at_damping_boundary() -> None:
    almost_damped = np.diag([1.0 - 2.0e-12, 25.0])
    features = np.asarray([[0.25, -0.5]], dtype=np.float64)
    result = width_sum_inequality(
        [almost_damped, almost_damped],
        features,
        damping=1.0,
        noise_variance=1.0,
    )
    assert result.width_sum <= result.information_bound + 1e-10


def test_width_sum_rejects_material_damping_violation() -> None:
    invalid = np.diag([0.99, 25.0])
    features = np.asarray([[0.25, -0.5]], dtype=np.float64)
    with pytest.raises(ValueError, match="below damping"):
        width_sum_inequality(
            [invalid, invalid],
            features,
            damping=1.0,
            noise_variance=1.0,
        )


def test_kappa_plus_is_exact_global_generalized_eigenvalue() -> None:
    reference = np.array(
        [[2.0, 0.3, -0.1], [0.3, 1.5, 0.2], [-0.1, 0.2, 1.1]],
        dtype=np.float64,
    )
    cholesky = np.linalg.cholesky(reference)
    rotation, _ = np.linalg.qr(
        np.array([[1.0, 2.0, -1.0], [2.0, -1.0, 0.5], [0.3, 0.7, 2.0]])
    )
    known = np.array([0.45, 1.7, 3.25])
    approximate = cholesky @ rotation @ np.diag(known) @ rotation.T @ cholesky.T

    result = generalized_eigenvalues(approximate, reference)

    np.testing.assert_allclose(result.eigenvalues, known, rtol=2e-13, atol=2e-13)
    np.testing.assert_allclose(kappa_plus(approximate, reference), known[-1])
    assert result.residual_norm < 1e-12
