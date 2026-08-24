from __future__ import annotations

import numpy as np
import pytest
from experiments.realistic_transport.features import (
    action_features,
    FeatureMapSpec,
    normalized_feature,
)
from experiments.realistic_transport.teacher import (
    build_misspecification,
    fit_ridge_teacher,
)


def test_feature_map_preserves_kron_ordering_and_norm_bound() -> None:
    context = np.asarray([0.6, 0.8], dtype=np.float64)
    feature = normalized_feature(context, 1, action_count=3)
    raw = np.asarray(
        [
            0.6,
            0.8,
            0.0,
            1.0,
            0.0,
            0.0,
            0.6,
            0.0,
            0.0,
            0.8,
            0.0,
        ]
    )
    np.testing.assert_allclose(feature, raw / np.linalg.norm(raw), atol=2e-16)
    table = action_features(context, action_count=3)
    assert table.shape == (3, 2 + 3 + 2 * 3)
    np.testing.assert_allclose(np.linalg.norm(table, axis=1), 1.0, atol=2e-16)
    assert FeatureMapSpec(2, 3).feature_dimension == 11


def test_ridge_teacher_uses_only_development_rows_and_maps_coefficients() -> None:
    rng = np.random.default_rng(40201)
    contexts = rng.normal(size=(120, 4))
    contexts /= np.maximum(1.0, np.linalg.norm(contexts, axis=1))[:, None]
    labels = np.asarray([0, 1, 2] * 40, dtype=np.int64)
    development = np.arange(60, dtype=np.int64)
    first = fit_ridge_teacher(
        contexts,
        labels,
        development,
        action_count=3,
        ridge=1.0,
        theta_radius=1.0,
    )
    changed_contexts = contexts.copy()
    changed_contexts[60:] *= -7.0
    changed_labels = labels.copy()
    changed_labels[60:] = (changed_labels[60:] + 1) % 3
    second = fit_ridge_teacher(
        changed_contexts,
        changed_labels,
        development,
        action_count=3,
        ridge=1.0,
        theta_radius=1.0,
    )
    assert first.digest == second.digest
    assert np.linalg.norm(first.theta) == pytest.approx(1.0, abs=2e-15)
    assert np.count_nonzero(first.theta[:4]) == 0

    context = contexts[3]
    features = first.feature_map.all_action_features(context)
    raw_norm = np.linalg.norm(
        np.concatenate((context, np.eye(3)[0], np.kron(context, np.eye(3)[0])))
    )
    expected = (context @ first.coefficients + first.intercepts) / max(1.0, raw_norm)
    np.testing.assert_allclose(features @ first.theta, expected, atol=3e-16)


def test_controlled_misspecification_is_deterministic_and_uniformly_bounded() -> None:
    rng = np.random.default_rng(40202)
    contexts = rng.normal(size=(150, 5))
    contexts /= np.maximum(1.0, np.linalg.norm(contexts, axis=1))[:, None]
    labels = np.asarray([0, 1, 2] * 50, dtype=np.int64)
    teacher = fit_ridge_teacher(
        contexts,
        labels,
        np.arange(75),
        action_count=3,
        ridge=1.0,
    )
    first = build_misspecification(contexts[:75], teacher, width=100.0)
    second = build_misspecification(contexts[:75], teacher, width=100.0)
    assert first.digest == second.digest
    assert first.rho == pytest.approx(0.25 * first.range_quantile)
    for context in contexts:
        assert np.max(np.abs(first.values(context))) <= 1.0
        assert np.max(np.abs(first.perturbation(context))) <= first.rho
    assert first.uniform_envelope() == first.rho
