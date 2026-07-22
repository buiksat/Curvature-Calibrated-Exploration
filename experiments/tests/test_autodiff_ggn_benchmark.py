from __future__ import annotations

from pathlib import Path

from experiments.config import get_seed_set, load_config
from experiments.run_autodiff_ggn_benchmark import (
    METHODS,
    validate_benchmark_config,
)
from experiments.run_autodiff_systems import mlp_parameter_count


CONFIG = Path("experiments/configs/autodiff_ggn_benchmark.yaml")


def test_autodiff_grid_is_preregistered_and_seed_disjoint() -> None:
    config = load_config(CONFIG, profile="full")
    validate_benchmark_config(config)
    assert tuple(config["methods"]) == METHODS
    assert len(get_seed_set(config, "evaluation")) == 10
    assert set(get_seed_set(config, "tuning")).isdisjoint(
        get_seed_set(config, "evaluation")
    )
    assert config["buffer_sizes"] == [32, 128, 512]
    assert config["action_counts"] == [5, 10]
    assert config["cg_targets"] == [0.1, 0.01, 0.001]


def test_model_sizes_and_dense_reference_scope() -> None:
    config = load_config(CONFIG, profile="full")
    models = {model["name"]: model for model in config["models"]}
    small_count = mlp_parameter_count(models["mlp_100k"]["architecture"])
    large_count = mlp_parameter_count(models["mlp_10m"]["architecture"])
    assert 100_000 <= small_count < 1_000_000
    assert 9_000_000 <= large_count <= 11_000_000
    assert models["mlp_100k"]["dense_reference"] is True
    assert models["mlp_10m"]["dense_reference"] is False
