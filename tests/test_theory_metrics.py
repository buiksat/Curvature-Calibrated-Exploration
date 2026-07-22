from __future__ import annotations

import numpy as np
import pytest

from experiments.curvature_operators import CurvatureOperator
from experiments.theory_metrics import (
    bounded_output_residual_factor,
    cg_sandwich,
    cg_width,
    dense_width,
    dynamic_rank_trace_upper_bound,
    dynamic_logdet_metrics,
    endpoint_rank_trace_logdet_bound,
    feature_drift_sandwich,
    frozen_rank_information_bound,
    generalized_eigenvalues,
    growing_window_complexity_bound,
    information_gain_closure,
    kappa_plus,
    outer_product_perturbation_bound,
    rank_sensitive_variation_bound,
    relative_refresh_audit,
    spectral_tail_information_bound,
    width_sum_inequality,
)


@pytest.mark.parametrize("seed", range(16))
def test_sharpened_feature_drift_sandwich_on_random_matrices(seed: int) -> None:
    rng = np.random.default_rng(seed)
    sample_count = 9
    dimension = 6
    frozen = rng.normal(size=(sample_count, dimension))
    raw_drift = rng.normal(size=(sample_count, dimension))

    pilot = feature_drift_sandwich(
        frozen,
        frozen + raw_drift,
        damping=0.8,
        noise_variance=1.3,
    )
    target_chi = 0.05 + 0.9 * seed / 15.0
    scale = target_chi / pilot.chi
    result = feature_drift_sandwich(
        frozen,
        frozen + scale * raw_drift,
        damping=0.8,
        noise_variance=1.3,
    )

    assert result.chi == pytest.approx(target_chi, rel=2e-12, abs=2e-13)
    assert result.lower_factor == pytest.approx((1.0 - target_chi) ** 2)
    assert result.upper_factor == pytest.approx((1.0 + target_chi) ** 2)
    assert result.minimum_squared_singular_value >= result.lower_factor - 1e-11
    assert result.maximum_squared_singular_value <= result.upper_factor + 1e-11
    np.testing.assert_allclose(
        result.stacked_frozen_design.T @ result.stacked_frozen_design,
        np.eye(dimension),
        rtol=2e-12,
        atol=2e-12,
    )


def test_sharpened_feature_drift_handles_empty_history_and_zero_gradient() -> None:
    empty = np.empty((0, 4), dtype=np.float64)
    result = feature_drift_sandwich(
        empty,
        empty,
        damping=1.7,
        noise_variance=0.4,
    )
    assert result.chi == 0.0
    assert result.lower_factor == 1.0
    assert result.upper_factor == 1.0
    np.testing.assert_allclose(result.frozen_curvature, 1.7 * np.eye(4))
    np.testing.assert_allclose(result.current_curvature, result.frozen_curvature)

    zeros = np.zeros((3, 4), dtype=np.float64)
    zero_gradient = feature_drift_sandwich(
        zeros,
        zeros,
        damping=1.7,
        noise_variance=0.4,
    )
    assert zero_gradient.chi == 0.0
    assert zero_gradient.lower_factor == 1.0
    assert zero_gradient.upper_factor == 1.0


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("tail_rank", [0, 1, 3, 8])
def test_spectral_tail_logdet_inequality(seed: int, tail_rank: int) -> None:
    rng = np.random.default_rng(seed)
    horizon = 8
    dimension = 10
    feature_bound = 1.5
    noise_variance = 0.7
    rows = rng.normal(size=(horizon, dimension))
    row_norms = np.linalg.norm(rows, axis=1)
    rows *= (feature_bound / np.maximum(feature_bound, row_norms))[:, None]
    increment = rows.T @ rows / noise_variance
    result = spectral_tail_information_bound(
        increment,
        damping=0.9,
        horizon=horizon,
        feature_bound=feature_bound,
        noise_variance=noise_variance,
        tail_rank=tail_rank,
    )

    assert result.effective_top_rank == min(tail_rank, horizon)
    assert result.exact_logdet <= result.upper_bound + 1e-11
    if tail_rank == 0:
        assert result.top_rank_bound == 0.0
        assert result.spectral_tail == pytest.approx(np.trace(increment))


def test_spectral_tail_exact_rank_and_zero_edge_cases() -> None:
    exact_rank = np.diag([4.0, 2.0, 0.0, 0.0])
    exact = spectral_tail_information_bound(
        exact_rank,
        damping=1.0,
        horizon=3,
        feature_bound=np.sqrt(2.0),
        noise_variance=1.0,
        tail_rank=2,
    )
    assert exact.spectral_tail == 0.0
    assert exact.tail_bound == 0.0

    zero = spectral_tail_information_bound(
        np.zeros((4, 4)),
        damping=1.0,
        horizon=0,
        feature_bound=0.0,
        noise_variance=1.0,
        tail_rank=0,
    )
    assert zero.exact_logdet == 0.0
    assert zero.upper_bound == 0.0


def test_bounded_output_residual_factor_has_declared_constants() -> None:
    bound = 1.3
    scale = 0.4
    horizon = 250
    failure_probability = 0.02
    factor = bounded_output_residual_factor(
        output_bound=bound,
        noise_scale=scale,
        horizon=horizon,
        failure_probability=failure_probability,
    )
    noise_threshold = scale * np.sqrt(
        2.0 * np.log(2.0 * horizon / failure_probability)
    )
    expected = 2.0 * (2.0 * bound) ** 2 + 2.0 * noise_threshold**2
    assert factor == pytest.approx(expected)
    assert 0.0 * factor == 0.0  # t=1 has no collected residuals.


@pytest.mark.parametrize("seed", range(12))
def test_rank_and_statistical_effective_dimension_close_logdet(seed: int) -> None:
    rng = np.random.default_rng(seed)
    dimension = 11
    rank = 4
    factors = rng.normal(size=(dimension, rank))
    increment = factors @ factors.T
    result = information_gain_closure(
        increment,
        damping=0.7,
        rank_bound=rank,
    )

    assert result.rank == rank
    assert result.statistical_effective_dimension <= rank
    assert result.exact_logdet <= result.rank_trace_bound + 1e-11
    assert result.exact_logdet <= result.effective_dimension_bound + 1e-11
    assert result.best_upper_bound >= result.exact_logdet - 1e-11


def test_trace_effective_rank_is_not_substituted_for_statistical_dimension() -> None:
    # tr(A)/||A|| is close to two, while log det(I+A) grows linearly with the
    # number of unit tail eigenvalues.  The implementation uses statistical
    # effective dimension and therefore does not make this invalid shortcut.
    dimension = 64
    increment = np.diag([dimension - 1.0, *([1.0] * (dimension - 1))])
    result = information_gain_closure(increment, damping=1.0)
    trace_effective_rank = np.trace(increment) / np.linalg.norm(increment, ord=2)

    assert trace_effective_rank == pytest.approx(2.0)
    assert result.statistical_effective_dimension > 30.0
    assert result.exact_logdet > 40.0


def test_frozen_rank_information_bound_has_declared_formula() -> None:
    value = frozen_rank_information_bound(
        horizon=250,
        feature_bound=1.5,
        rank_bound=5,
        damping=0.8,
        noise_variance=0.25,
    )
    expected = 5.0 * np.log1p(250.0 * 1.5**2 / (5.0 * 0.8 * 0.25))
    assert value == pytest.approx(expected)
    with pytest.raises(ValueError, match="rank_bound zero"):
        frozen_rank_information_bound(
            horizon=1,
            feature_bound=1.0,
            rank_bound=0,
            damping=1.0,
            noise_variance=1.0,
        )


@pytest.mark.parametrize("exponent", [0.5, 2.0 / 3.0, 1.0])
def test_growing_window_width_and_complexity_bounds(exponent: float) -> None:
    result = growing_window_complexity_bound(
        horizon=1000,
        exponent=exponent,
        feature_bound=1.2,
        damping=0.9,
        excitation=0.15,
        noise_variance=0.3,
    )

    expected = np.asarray(
        [
            1.2**2 / (0.9 if m == 0 else 0.9 + 0.15 * m)
            for m in result.window_sizes
        ]
    )
    np.testing.assert_allclose(result.width_squared_bounds, expected)
    assert result.exact_sum_bound <= result.asymptotic_sum_bound + 1e-11
    assert result.information_bound == pytest.approx(
        result.exact_sum_bound / 0.3
    )


@pytest.mark.parametrize("seed", range(12))
def test_window_excitation_loewner_floor_bounds_actual_width(seed: int) -> None:
    rng = np.random.default_rng(seed)
    dimension = 10
    rank = 4
    damping = 0.8
    excitation = 0.13
    window = 17
    basis, _ = np.linalg.qr(rng.normal(size=(dimension, rank)))
    projector = basis @ basis.T
    extra = rng.normal(size=(dimension, 3))
    operator = (
        damping * np.eye(dimension)
        + excitation * window * projector
        + extra @ extra.T
    )
    coordinates = rng.normal(size=rank)
    feature = basis @ coordinates
    feature *= 1.7 / max(1.7, np.linalg.norm(feature))
    actual = float(feature @ np.linalg.solve(operator, feature))
    upper = 1.7**2 / (damping + excitation * window)
    assert actual <= upper + 1e-11


@pytest.mark.parametrize("seed", range(20))
def test_outer_product_perturbation_inequality(seed: int) -> None:
    rng = np.random.default_rng(seed)
    a = rng.normal(size=7)
    b = rng.normal(size=7)
    observed, upper = outer_product_perturbation_bound(a, b)
    assert observed <= upper + 1e-12


@pytest.mark.parametrize("seed", range(12))
def test_relative_refresh_bound_on_random_active_subspaces(seed: int) -> None:
    rng = np.random.default_rng(seed)
    dimension = 9
    rank = 3
    sample_count = 7
    basis, _ = np.linalg.qr(rng.normal(size=(dimension, rank)))
    old_coordinates = rng.normal(size=(sample_count, rank))
    old_coordinates *= 0.4 / max(1.0, np.max(np.linalg.norm(old_coordinates, axis=1)))
    directions = rng.normal(size=(sample_count, rank))
    directions *= 0.03 / max(1.0, np.max(np.linalg.norm(directions, axis=1)))
    old = old_coordinates @ basis.T
    new = (old_coordinates + directions) @ basis.T
    feature_bound = float(
        max(np.max(np.linalg.norm(old, axis=1)), np.max(np.linalg.norm(new, axis=1)))
    )
    step = 0.2
    lipschitz = 0.03 / step
    variance = 0.7
    ridge = 0.8
    current_plus = ridge * np.eye(dimension) + old.T @ old / variance

    result = relative_refresh_audit(
        old,
        new,
        current_plus,
        active_basis=basis,
        feature_bound=feature_bound,
        jacobian_lipschitz=lipschitz,
        parameter_increment=step,
        noise_variance=variance,
        active_lower_bound=ridge,
    )

    assert result.sample_count == sample_count
    assert result.observed_perturbation_norm <= result.termwise_perturbation_bound + 1e-12
    assert result.observed_relative_norm <= result.analytic_relative_bound + 1e-12


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
