from __future__ import annotations

import numpy as np
import pytest
from experiments.realistic_transport.data import (
    load_prepared_dataset,
    prepare_loaded_dataset,
)
from experiments.realistic_transport.environment import (
    build_stream,
    build_task_environment,
    CONTROLLED_MISSPECIFIED_TASK,
    LABEL_TASK,
    REALIZABLE_TASK,
)
from experiments.realistic_transport.model import scaled_tanh_mean
from experiments.realistic_transport.preprocessing import (
    deterministic_split,
    fit_preprocessing,
)


def _prepared_fixture(tmp_path):
    rng = np.random.default_rng(40301)
    features = rng.normal(size=(401, 20))
    latent = features[:, :3] @ np.asarray(
        [[1.0, -0.5, 0.2], [-0.4, 0.9, 0.1], [0.3, -0.2, 0.8]]
    )
    labels = np.argmax(latent, axis=1) + 1
    artifact = tmp_path / "fixture.npz"
    prepare_loaded_dataset(
        features,
        labels,
        dataset_name="fixture",
        destination=artifact,
    )
    return load_prepared_dataset(artifact)


def _environments(tmp_path):
    prepared = _prepared_fixture(tmp_path)
    split = deterministic_split(prepared.features.shape[0], prepared.content_digest)
    transform = fit_preprocessing(
        prepared.features,
        split.development,
        prepared_data_digest=prepared.content_digest,
        rank=4,
    )
    config = {
        "preprocessing": {"rank": 4},
        "teacher": {"ridge": 1.0, "theta_radius": 1.0},
        "feature_map": {"feature_bound": 1.0},
        "environment": {"gaussian_noise_std": 0.25},
        "maximum_horizon": 500,
        "target_D": 1.0,
        "ridge": 1.0,
        "model": {"width": 100.0},
        "misspecification": {"seed": 271828, "range_quantile": 0.9, "fraction": 0.25},
    }
    return tuple(
        build_task_environment(
            prepared,
            task,
            config,
            split=split,
            preprocessing=transform,
        )
        for task in (LABEL_TASK, REALIZABLE_TASK, CONTROLLED_MISSPECIFIED_TASK)
    )


def test_task_metadata_feature_dimensions_and_label_means(tmp_path) -> None:
    label, realizable, misspecified = _environments(tmp_path)
    assert label.context_dimension == 4
    assert label.action_count == 3
    assert label.feature_dimension == 4 + 3 + 4 * 3
    assert label.noise_proxy == 0.5
    assert label.theta_star is None
    assert not label.theorem_applicable
    assert realizable.noise_proxy == 0.25
    assert realizable.theorem_applicable
    assert misspecified.theorem_applicable
    assert misspecified.rho > 0.0

    for row_index in label.split.evaluation[:20]:
        means = label.true_means(int(row_index))
        assert means[int(label.labels[row_index])] == pytest.approx(0.9)
        assert np.count_nonzero(np.isclose(means, 0.1)) == label.action_count - 1


def test_realizable_means_recompute_exactly_through_learner(tmp_path) -> None:
    _, realizable, misspecified = _environments(tmp_path)
    assert realizable.theta_star is not None
    for row_index in realizable.split.evaluation[:40]:
        context = realizable.contexts[row_index]
        recomputed = scaled_tanh_mean(
            realizable.theta_star,
            realizable.feature_matrix(context),
            realizable.width,
        )
        np.testing.assert_array_equal(realizable.true_means(int(row_index)), recomputed)
        difference = misspecified.true_means(int(row_index)) - realizable.true_means(
            int(row_index)
        )
        assert np.max(np.abs(difference)) <= misspecified.rho + 2e-16
    assert realizable.historical_misspecification_envelope == 0.0
    assert realizable.current_misspecification_envelope == 0.0
    assert misspecified.historical_misspecification_envelope == misspecified.rho
    assert misspecified.current_misspecification_envelope == misspecified.rho


def test_streams_are_paired_deterministic_and_reveal_only_selected_reward(
    tmp_path,
) -> None:
    label, realizable, misspecified = _environments(tmp_path)
    first = build_stream(realizable, "evaluation", 100, 32)
    second = build_stream(realizable, "evaluation", 100, 32)
    misspecified_stream = build_stream(misspecified, "evaluation", 100, 32)
    np.testing.assert_array_equal(first.row_indices, second.row_indices)
    np.testing.assert_array_equal(first.rewards, second.rewards)
    np.testing.assert_array_equal(first.row_indices, misspecified_stream.row_indices)
    np.testing.assert_array_equal(first.noises, misspecified_stream.noises)
    assert first.digest == second.digest

    policy_input = first.policy_round(0)
    assert set(policy_input.__dataclass_fields__) == {"context", "action_features"}
    assert not hasattr(policy_input, "label")
    assert not hasattr(policy_input, "means")
    assert not hasattr(policy_input, "rewards")
    assert isinstance(first.observe(0, 1), float)
    assert first.observe(0, 1) == first.rewards[0, 1]

    label_stream = build_stream(label, "evaluation", 100, 32)
    assert set(np.unique(label_stream.rewards)).issubset({0.0, 1.0})
    expected = np.stack(
        [label.true_means(int(index)) for index in label_stream.row_indices]
    )
    np.testing.assert_array_equal(label_stream.means, expected)


def test_context_and_outcome_streams_change_under_separate_seed_namespaces(
    tmp_path,
) -> None:
    _, realizable, _ = _environments(tmp_path)
    first = build_stream(realizable, "evaluation", 100, 32)
    second = build_stream(realizable, "evaluation", 101, 32)
    assert not np.array_equal(first.row_indices, second.row_indices)
    assert not np.array_equal(first.noises, second.noises)


def test_context_stream_samples_without_replacement_and_rejects_oversubscription(
    tmp_path,
) -> None:
    _, realizable, _ = _environments(tmp_path)
    pool_size = realizable.split.development.size
    stream = build_stream(realizable, "development", 0, pool_size)

    assert np.unique(stream.row_indices).size == pool_size
    with pytest.raises(ValueError, match="requested .* rounds"):
        build_stream(realizable, "development", 0, pool_size + 1)
