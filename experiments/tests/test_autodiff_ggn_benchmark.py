from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from experiments.artifact_utils import (
    ArtifactProvenanceError,
    input_set_sha256,
    validate_aggregate_provenance_sidecar,
    write_aggregate_with_provenance,
)
from experiments.autodiff_ggn import (
    AutodiffGGN,
    mlp_parameter_count,
    torch_capability,
)
from experiments.config import get_seed_set, load_config
from experiments.run_autodiff_ggn_benchmark import (
    METHODS,
    validate_benchmark_config,
)


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


def test_tiny_autodiff_operator_matches_dense_ggn() -> None:
    capability = torch_capability()
    if not capability.available:
        assert capability.reason_code in {
            "missing_optional_dependency",
            "torch_import_failed",
            "unsupported_torch_func_api",
        }
        return

    import torch

    torch.manual_seed(17)
    architecture = (3, 4, 1)
    parameters = torch.randn(
        mlp_parameter_count(architecture), dtype=torch.float64
    )
    inputs = torch.randn(5, architecture[0], dtype=torch.float64)
    operator = AutodiffGGN(
        torch,
        parameters,
        inputs,
        architecture,
        "tanh",
        damping=0.75,
        noise_variance=1.5,
    )
    jacobian = torch.func.jacrev(operator.outputs)(parameters).detach()
    dense = 0.75 * torch.eye(parameters.numel(), dtype=torch.float64)
    dense += jacobian.transpose(0, 1) @ jacobian / (5 * 1.5)
    vectors = torch.randn(3, parameters.numel(), dtype=torch.float64)

    torch.testing.assert_close(operator.matvec(vectors[0]), dense @ vectors[0])
    torch.testing.assert_close(operator.matmat(vectors), vectors @ dense)
    left = torch.dot(vectors[0], operator.matvec(vectors[1]))
    right = torch.dot(operator.matvec(vectors[0]), vectors[1])
    torch.testing.assert_close(left, right)


def test_aggregate_provenance_binds_every_input(tmp_path: Path) -> None:
    source = tmp_path / "input.json"
    source.write_text("{}\n", encoding="ascii")
    inputs = [
        {
            "path": str(source),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
    ]
    aggregate = {
        "schema_version": 1,
        "inputs": inputs,
        "input_set_sha256": input_set_sha256(inputs),
    }
    artifact, sidecar = write_aggregate_with_provenance(
        aggregate, tmp_path / "aggregate.json"
    )
    record = validate_aggregate_provenance_sidecar(artifact, sidecar)
    assert record["inputs"] == inputs

    source.write_text('{"changed": true}\n', encoding="ascii")
    with pytest.raises(ArtifactProvenanceError, match="digest does not match"):
        validate_aggregate_provenance_sidecar(artifact, sidecar)
