from __future__ import annotations

from pathlib import Path

import numpy as np

from experiments.config import load_config
from experiments.run_certified_scaling import (
    Cell,
    generate_scaling_stream,
    run_evaluation,
    run_scaling_trajectory,
    validate_scaling_config,
)


CONFIG = Path("experiments/configs/certified_scaling.yaml")


def _config() -> dict[str, object]:
    return load_config(CONFIG, profile="smoke")


def test_rotated_cycle_has_requested_condition_and_nondiagonal_ambient_gram() -> None:
    config = _config()
    validate_scaling_config(config)
    cell = Cell(dimension=32, rank=4, condition_number=100)
    stream = generate_scaling_stream(config, cell, seed=1000)
    active_gram = stream.cycle_vectors.T @ stream.cycle_vectors
    eigenvalues = np.linalg.eigvalsh(active_gram)
    assert np.isclose(eigenvalues[-1] / eigenvalues[0], 100.0)
    ambient_gram = stream.active_basis @ active_gram @ stream.active_basis.T
    off_diagonal = ambient_gram - np.diag(np.diag(ambient_gram))
    assert np.linalg.norm(off_diagonal) > 0.1 * np.linalg.norm(ambient_gram)


def test_every_long_cyclic_window_obeys_analytic_excitation_floor() -> None:
    config = _config()
    cell = Cell(dimension=32, rank=4, condition_number=100)
    stream = generate_scaling_stream(config, cell, seed=1000)
    variance = float(config["noise_std"]) ** 2
    damping = float(config["damping"])
    vectors = np.asarray(
        [stream.cycle_vectors[index % cell.rank] for index in range(40)]
    )
    for length in range(2 * cell.rank, 25):
        lower = damping + (
            stream.minimum_cycle_eigenvalue * length
            / (2.0 * cell.rank * variance)
        )
        for start in range(0, 40 - length + 1):
            matrix = np.eye(cell.rank) * damping
            matrix += vectors[start : start + length].T @ vectors[start : start + length] / variance
            assert np.linalg.eigvalsh(matrix)[0] + 1e-12 >= lower


def test_nontrivial_cg_matches_dense_and_all_required_premises_pass() -> None:
    config = _config()
    cell = Cell(dimension=32, rank=4, condition_number=100)
    stream = generate_scaling_stream(config, cell, seed=1000)
    dense = run_scaling_trajectory(
        config, cell, stream, method="exact_current"
    )
    cg = run_scaling_trajectory(config, cell, stream, method="full_cg")
    window = run_scaling_trajectory(config, cell, stream, method="window_q_1_2")
    assert cg.summary["multi_iteration_round_fraction"] > 0.9
    assert cg.summary["all_cg_solves_converged"] is True
    assert cg.summary["all_required_premises_pass"] is True
    assert window.summary["all_required_premises_pass"] is True
    assert window.summary["post_burnin_excitation_pass"] is True
    np.testing.assert_array_equal(
        dense.arrays["selected_actions"], cg.arrays["selected_actions"]
    )
    np.testing.assert_allclose(
        dense.arrays["cumulative_pseudo_regret"],
        cg.arrays["cumulative_pseudo_regret"],
        rtol=0.0,
        atol=0.0,
    )
    relative_width_error = np.abs(
        cg.arrays["selected_width_squared"]
        - cg.arrays["exact_operator_width_squared"]
    ) / np.maximum(cg.arrays["exact_operator_width_squared"], 1e-15)
    assert float(np.max(relative_width_error)) < 1e-9


def test_parallel_evaluation_preserves_complete_premise_clean_grid(
    tmp_path: Path,
) -> None:
    config = _config()
    result = run_evaluation(
        config,
        profile="smoke",
        output_root=tmp_path / "raw",
        overwrite=False,
        workers=2,
    )
    assert result["workers"] == 2
    assert result["run_count"] == 14
    assert result["premise_clean_run_count"] == 14
