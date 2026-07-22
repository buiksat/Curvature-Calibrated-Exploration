from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from experiments.artifact_utils import (
    sha256_file,
    validate_sha256_sidecar,
    write_deterministic_npz,
)
from experiments.config import get_seed_set, load_config
from experiments.run_spectral_tail_study import (
    Cell,
    generate_stream,
    run_trajectory,
    validate_study_config,
)


CONFIG = Path("experiments/configs/spectral_tail_study.yaml")


def _smoke_config() -> dict[str, object]:
    return load_config(CONFIG, profile="smoke")


def test_spectral_tail_config_has_disjoint_seed_manifests() -> None:
    config = _smoke_config()
    validate_study_config(config)
    tuning = set(get_seed_set(config, "tuning"))
    evaluation = set(get_seed_set(config, "evaluation"))
    development = set(get_seed_set(config, "development"))
    assert not tuning & evaluation
    assert not tuning & development
    assert not evaluation & development


def test_stream_generation_is_pcg64_deterministic() -> None:
    config = _smoke_config()
    cell = Cell(rank=2, spectral_power=1, alignment="tail")
    first = generate_stream(config, cell, seed=1000)
    second = generate_stream(config, cell, seed=1000)
    assert first.stream_sha256 == second.stream_sha256
    np.testing.assert_array_equal(first.coordinates, second.coordinates)
    np.testing.assert_array_equal(first.rotation, second.rotation)


def test_dense_and_cg_trajectories_match_and_tail_bound_holds() -> None:
    config = _smoke_config()
    cell = Cell(rank=2, spectral_power=2, alignment="tail")
    stream = generate_stream(config, cell, seed=1000)
    dense = run_trajectory(
        config, cell, stream, method="exact_dense_full", bonus=0.4
    )
    cg = run_trajectory(config, cell, stream, method="full_cg", bonus=0.4)
    np.testing.assert_array_equal(
        dense.arrays["selected_actions"], cg.arrays["selected_actions"]
    )
    np.testing.assert_allclose(
        dense.arrays["cumulative_pseudo_regret"],
        cg.arrays["cumulative_pseudo_regret"],
        rtol=0.0,
        atol=0.0,
    )
    assert np.all(cg.arrays["cg_iterations"] == 1)
    assert np.all(cg.arrays["cg_relative_residual"] == 0.0)
    assert np.all(dense.arrays["gamma"] <= dense.arrays["gamma_tail"] + 1e-12)


def test_deterministic_npz_and_hash_tamper_detection(tmp_path: Path) -> None:
    arrays = {
        "z": np.asarray([3.0, 4.0], dtype=np.float64),
        "a": np.asarray([1, 2], dtype=np.int64),
    }
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    write_deterministic_npz(first, arrays)
    write_deterministic_npz(second, arrays)
    assert sha256_file(first) == sha256_file(second)
    validate_sha256_sidecar(first)
    first.write_bytes(first.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        validate_sha256_sidecar(first)
