from __future__ import annotations

import numpy as np
import pytest

from experiments.theory_metrics import (
    dynamic_logdet_metrics,
    generalized_eigenvalues,
    width_sum_inequality,
)


def _frozen_operator_path(
    features: np.ndarray,
    *,
    damping: float,
    noise_variance: float,
) -> tuple[np.ndarray, ...]:
    operators = [damping * np.eye(features.shape[1])]
    for feature in features:
        operators.append(
            operators[-1] + np.outer(feature, feature) / noise_variance
        )
    return tuple(operators)


def test_dynamic_logdet_identity_for_frozen_sequential_updates() -> None:
    rng = np.random.default_rng(21)
    features = rng.normal(size=(7, 4))
    operators = _frozen_operator_path(
        features,
        damping=0.8,
        noise_variance=0.5,
    )

    result = dynamic_logdet_metrics(
        operators,
        features,
        noise_variance=0.5,
    )

    assert result.identity_residual == pytest.approx(0.0, abs=2e-12)
    assert result.variation_charge == pytest.approx(0.0, abs=2e-12)
    assert result.information_complexity == pytest.approx(
        result.endpoint_logdeterminant,
        abs=2e-12,
    )
    for perturbation in result.normalized_perturbations:
        np.testing.assert_allclose(perturbation, 0.0, atol=2e-12)


def test_dynamic_logdet_identity_includes_relinearization_variation() -> None:
    features = np.asarray([[0.4, -0.2], [0.1, 0.3]], dtype=np.float64)
    initial = np.diag([1.0, 1.4])
    first_update = initial + np.outer(features[0], features[0])
    current = first_update + np.diag([0.2, -0.1])
    terminal = current + np.outer(features[1], features[1]) + np.diag([0.1, 0.05])

    result = dynamic_logdet_metrics(
        (initial, current, terminal),
        features,
    )

    assert result.identity_residual == pytest.approx(0.0, abs=2e-12)
    assert result.dynamic_potential + 2e-12 >= result.information_complexity
    assert len(result.transition_logdeterminants) == 2


def test_width_sum_bounds_actual_widths_and_checks_declared_constants() -> None:
    rng = np.random.default_rng(22)
    features = rng.normal(size=(6, 3))
    features /= np.maximum(1.0, np.linalg.norm(features, axis=1, keepdims=True))
    operators = _frozen_operator_path(
        features,
        damping=1.2,
        noise_variance=0.7,
    )

    result = width_sum_inequality(
        operators,
        features,
        damping=1.2,
        noise_variance=0.7,
        feature_bound=1.0,
    )

    assert result.width_sum <= result.information_bound + 2e-12
    assert result.width_sum <= result.dynamic_bound + 2e-12
    assert result.coefficient == pytest.approx(0.7 + 1.0 / 1.2)

    with pytest.raises(ValueError, match="feature norm"):
        width_sum_inequality(
            operators,
            features,
            damping=1.2,
            noise_variance=0.7,
            feature_bound=0.1,
        )


def test_generalized_eigenvalues_certify_the_two_sided_dense_comparison() -> None:
    reference = np.asarray([[2.0, 0.3], [0.3, 1.4]])
    approximate = np.asarray([[3.0, -0.1], [-0.1, 0.9]])

    result = generalized_eigenvalues(approximate, reference)
    whitened = np.linalg.solve(np.linalg.cholesky(reference), approximate)
    whitened = np.linalg.solve(np.linalg.cholesky(reference), whitened.T).T
    expected = np.linalg.eigvalsh(0.5 * (whitened + whitened.T))

    np.testing.assert_allclose(result.eigenvalues, expected, rtol=2e-14, atol=2e-14)
    assert result.maximum == pytest.approx(expected[-1])
    assert result.residual_norm <= 2e-14
    lower = approximate - result.eigenvalues[0] * reference
    upper = result.maximum * reference - approximate
    assert np.linalg.eigvalsh(0.5 * (lower + lower.T))[0] >= -2e-14
    assert np.linalg.eigvalsh(0.5 * (upper + upper.T))[0] >= -2e-14


def test_metric_helpers_reject_invalid_operator_paths() -> None:
    features = np.zeros((1, 2))
    with pytest.raises(ValueError, match="one round operator"):
        dynamic_logdet_metrics((np.eye(2),), features)
    with pytest.raises(ValueError, match="positive definite"):
        generalized_eigenvalues(np.diag([1.0, 0.0]), np.eye(2))
