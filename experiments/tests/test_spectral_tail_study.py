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
from experiments.make_spectral_tail_artifacts import (
    SpectralTailArtifactError,
    _reanalyze_trajectory_bounds,
)
from experiments.run_spectral_tail_study import (
    Cell,
    generate_stream,
    run_phase,
    run_trajectory,
    validate_study_config,
)
from experiments.theory_metrics import spectral_tail_information_bound


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


def test_retained_trajectory_reanalysis_orders_refined_and_ambient_bounds() -> None:
    config = _smoke_config()
    cell = Cell(rank=2, spectral_power=2, alignment="tail")
    trajectory = run_trajectory(
        config,
        cell,
        generate_stream(config, cell, seed=1000),
        method="exact_dense_full",
        bonus=0.4,
    )
    bounds, diagnostics = _reanalyze_trajectory_bounds(
        trajectory.arrays, config, tail_rank=cell.rank
    )

    tolerance = 1e-10
    assert np.all(bounds["gamma_exact"] <= bounds["gamma_split"] + tolerance)
    assert np.all(bounds["gamma_split"] <= bounds["gamma_tail_old"] + tolerance)
    assert np.all(
        bounds["gamma_split"]
        <= bounds["gamma_ambient_realized_trace"] + tolerance
    )
    assert np.all(
        bounds["gamma_ambient_realized_trace"]
        <= bounds["gamma_ambient_worst_case"] + tolerance
    )
    assert set(diagnostics["comparisons"]) == {
        "gamma_exact_le_gamma_split",
        "gamma_split_le_gamma_tail_old",
        "gamma_split_le_gamma_ambient_realized_trace",
        "gamma_ambient_realized_trace_le_gamma_ambient_worst_case",
    }

    selected = np.asarray(
        trajectory.arrays["selected_coordinates"], dtype=np.int64
    )
    counts = np.bincount(selected, minlength=int(config["dimension"])).astype(
        np.float64
    )
    increment = np.diag(counts / float(config["noise_std"]) ** 2)
    reference = spectral_tail_information_bound(
        increment,
        damping=float(config["damping"]),
        horizon=int(config["rounds"]),
        feature_bound=float(config["feature_bound"]),
        noise_variance=float(config["noise_std"]) ** 2,
        tail_rank=cell.rank,
    )
    assert bounds["gamma_exact"][-1] == pytest.approx(reference.exact_logdet)
    assert bounds["gamma_split"][-1] == pytest.approx(reference.split_upper_bound)
    assert bounds["gamma_tail_old"][-1] == pytest.approx(reference.upper_bound)


def test_retained_trajectory_reanalysis_rejects_ordering_violation() -> None:
    config = _smoke_config()
    cell = Cell(rank=2, spectral_power=1, alignment="head")
    trajectory = run_trajectory(
        config,
        cell,
        generate_stream(config, cell, seed=1001),
        method="exact_dense_full",
        bonus=0.1,
    )
    bounds, _ = _reanalyze_trajectory_bounds(
        trajectory.arrays, config, tail_rank=cell.rank
    )
    corrupted = dict(trajectory.arrays)
    corrupted["gamma"] = bounds["gamma_split"] + 1.0
    with pytest.raises(
        SpectralTailArtifactError, match="gamma_exact <= gamma_split"
    ):
        _reanalyze_trajectory_bounds(corrupted, config, tail_rank=cell.rank)


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


def test_parallel_phase_matches_declared_run_count(tmp_path: Path) -> None:
    config = _smoke_config()
    selection = tmp_path / "selection.json"
    result = run_phase(
        config,
        profile="smoke",
        phase="tuning",
        output_root=tmp_path / "raw",
        selection_path=selection,
        overwrite=False,
        workers=2,
    )
    assert result["workers"] == 2
    assert result["run_count"] == 312
    assert selection.is_file()
