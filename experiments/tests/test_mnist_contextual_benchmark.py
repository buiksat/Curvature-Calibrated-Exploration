from __future__ import annotations

from pathlib import Path

import numpy as np

from experiments.config import load_config
from experiments.run_mnist_contextual_benchmark import (
    ACTION_COUNT,
    MNISTData,
    ManualNetwork,
    _balanced_indices,
    _cg_widths,
    _lofi_update,
    _lofi_widths,
    run_policy,
    validate_mnist_config,
)


CONFIG = Path("experiments/configs/mnist_contextual_benchmark.yaml")


def _synthetic_data(input_dimension: int) -> MNISTData:
    rng = np.random.Generator(np.random.PCG64(7))
    count = 40
    x = rng.normal(size=(count, input_dimension))
    y = np.arange(count, dtype=np.int64) % ACTION_COUNT
    return MNISTData(
        x[:10], y[:10], x[10:25], y[10:25], x[25:], y[25:],
        np.arange(input_dimension, dtype=np.int64), "synthetic-test-only"
    )


def test_manual_network_action_gradient_matches_finite_difference() -> None:
    network = ManualNetwork.initialize(5, 3, 11)
    x = np.linspace(-0.4, 0.6, 5)
    action = 2
    analytic = network.action_gradient(x, action)
    original = network.parameters()
    numeric = np.empty_like(original)
    epsilon = 1e-6
    for index in range(original.size):
        plus, minus = original.copy(), original.copy()
        plus[index] += epsilon
        minus[index] -= epsilon
        network.set_parameters(plus)
        upper = network.means(x[None, :])[0, action]
        network.set_parameters(minus)
        lower = network.means(x[None, :])[0, action]
        numeric[index] = (upper - lower) / (2.0 * epsilon)
    network.set_parameters(original)
    np.testing.assert_allclose(analytic, numeric, rtol=2e-5, atol=2e-7)


def test_batched_gradients_match_scalar_gradients() -> None:
    network = ManualNetwork.initialize(5, 3, 17)
    contexts = np.linspace(-0.7, 0.8, 20).reshape(4, 5)
    actions = np.asarray([0, 3, 3, 9], dtype=np.int64)
    expected = np.stack(
        [network.action_gradient(x, int(action)) for x, action in zip(contexts, actions)]
    )
    np.testing.assert_allclose(
        network.selected_action_gradients(contexts, actions), expected, atol=1e-14
    )


def test_batched_cg_widths_match_dense_solve() -> None:
    rng = np.random.Generator(np.random.PCG64(23))
    features = rng.normal(size=(13, 17))
    candidates = rng.normal(size=(10, 17))
    ridge = 0.7
    noise_variance = 0.2
    widths, iterations, residual = _cg_widths(
        features,
        candidates,
        ridge=ridge,
        noise_variance=noise_variance,
        tolerance=1e-12,
        maximum_iterations=40,
    )
    matrix = ridge * np.eye(features.shape[1]) + features.T @ features / noise_variance
    expected = np.sqrt(
        np.maximum(
            np.einsum("ij,ij->i", candidates, np.linalg.solve(matrix, candidates.T).T),
            0.0,
        )
    )
    np.testing.assert_allclose(widths, expected, rtol=1e-9, atol=1e-10)
    assert iterations > 0
    assert residual <= 1e-12

    pcg_widths, pcg_iterations, pcg_residual = _cg_widths(
        features,
        candidates,
        ridge=ridge,
        noise_variance=noise_variance,
        tolerance=1e-12,
        maximum_iterations=40,
        preconditioner="jacobi",
    )
    np.testing.assert_allclose(pcg_widths, expected, rtol=1e-9, atol=1e-10)
    assert pcg_iterations > 0
    assert pcg_residual <= 1e-12


def test_online_lofi_update_is_exact_before_rank_truncation() -> None:
    rng = np.random.Generator(np.random.PCG64(29))
    parameter_count = 11
    diagonal = np.full(parameter_count, 0.8)
    factor = np.empty((parameter_count, 0))
    gradients = rng.normal(size=(4, parameter_count))
    noise_variance = 0.3
    for gradient in gradients:
        diagonal, factor = _lofi_update(
            diagonal,
            factor,
            gradient,
            noise_variance=noise_variance,
            rank=4,
        )
    candidates = rng.normal(size=(6, parameter_count))
    widths = _lofi_widths(diagonal, factor, candidates)
    matrix = 0.8 * np.eye(parameter_count) + gradients.T @ gradients / noise_variance
    expected = np.sqrt(
        np.maximum(
            np.einsum("ij,ij->i", candidates, np.linalg.solve(matrix, candidates.T).T),
            0.0,
        )
    )
    np.testing.assert_allclose(widths, expected, rtol=1e-10, atol=1e-11)


def test_mnist_config_has_preregistered_disjoint_seeds() -> None:
    config = load_config(CONFIG, "full")
    validate_mnist_config(config, full=True)
    assert config["seed_sets"]["tuning"] == list(range(3000, 3010))
    assert config["seed_sets"]["evaluation"] == list(range(3100, 3120))
    assert config["evaluation_pool_count"] == 8000


def test_balanced_indices_are_disjoint_and_capacity_aware() -> None:
    labels = np.repeat(np.arange(ACTION_COUNT, dtype=np.int64), 12)
    labels = np.concatenate((labels, np.full(3, ACTION_COUNT - 1, dtype=np.int64)))
    rng = np.random.Generator(np.random.PCG64(19))
    first = _balanced_indices(labels, 100, rng)
    remaining = np.setdiff1d(np.arange(labels.size, dtype=np.int64), first)
    second = _balanced_indices(labels, 20, rng, candidates=remaining)

    assert np.intersect1d(first, second).size == 0
    assert np.max(np.bincount(labels[first], minlength=ACTION_COUNT)) == 10
    assert second.size == 20
    assert np.unique(second).size == second.size


def test_all_local_methods_execute_on_balanced_fixture() -> None:
    config = load_config(CONFIG, "smoke")
    config["rounds"] = 4
    data = _synthetic_data(int(config["input_dimension"]))
    network = ManualNetwork.initialize(
        int(config["input_dimension"]), int(config["hidden_width"]), 13
    )
    hyperparameters = dict(config["tuning_grid"][0])
    for method in config["methods"]:
        records, summary = run_policy(
            config, data, network, method, 3100, "evaluation", hyperparameters
        )
        assert len(records) == 4
        assert summary["method"] == method
        assert 0.0 <= summary["accuracy"] <= 1.0
