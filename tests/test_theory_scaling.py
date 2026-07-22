from __future__ import annotations

import inspect
from pathlib import Path
import shutil

import numpy as np
import pytest

from experiments.config import get_seed_set, load_config
from experiments.aggregate_theory_scaling import (
    aggregate_full_grid,
    aggregate_primary_slice,
    load_compact_run,
)
from experiments.theory_scaling import (
    METHODS,
    CyclicActiveTanhEnvironment,
    deterministic_embedding,
    run_theory_scaling_cell,
    scaled_tanh_constants,
    scaled_tanh_gradients,
    scaled_tanh_mean,
    scaling_cells,
)
from experiments.theory_scaling_compact import (
    compact_run_directory,
    records_to_numeric_arrays,
    save_compact_run,
    sha256_file,
    write_deterministic_npz,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments" / "configs" / "theory_scaling.json"


def test_scaled_tanh_gradient_and_width_dependent_smoothness() -> None:
    rng = np.random.default_rng(901)
    theta = rng.normal(0.0, 0.1, size=4)
    features = rng.normal(size=(6, 4))
    features /= np.maximum(np.linalg.norm(features, axis=1, keepdims=True), 1.0)
    width = 64.0
    analytic = scaled_tanh_gradients(theta, features, width)
    numerical = np.empty_like(analytic)
    step = 1.0e-6
    for coordinate in range(theta.size):
        offset = np.zeros_like(theta)
        offset[coordinate] = step
        numerical[:, coordinate] = (
            scaled_tanh_mean(theta + offset, features, width)
            - scaled_tanh_mean(theta - offset, features, width)
        ) / (2.0 * step)
    np.testing.assert_allclose(analytic, numerical, rtol=3e-10, atol=3e-11)
    G, L_mu, L_g = scaled_tanh_constants(1.0, width)
    assert G == 1.0
    assert L_mu == L_g
    assert L_mu == pytest.approx(4.0 / (3.0 * np.sqrt(3.0 * width)))


def test_embedding_and_environment_are_reproducible_and_active() -> None:
    first = deterministic_embedding(16, 3, 902)
    second = deterministic_embedding(16, 3, 902)
    np.testing.assert_array_equal(first, second)
    np.testing.assert_allclose(first.T @ first, np.eye(3), atol=2e-15)
    kwargs = dict(
        seed=902,
        rounds=7,
        ambient_dimension=16,
        active_rank=3,
        action_magnitudes=(-0.5, 1.0),
        teacher_norm=0.2,
        network_width=256.0,
        noise_std=0.05,
    )
    environment = CyclicActiveTanhEnvironment(**kwargs)
    repeated = CyclicActiveTanhEnvironment(**kwargs)
    assert environment.stream_sha256 == repeated.stream_sha256
    for round_index in range(7):
        features = environment.active_features(round_index)
        assert np.count_nonzero(features) == 2
        assert np.flatnonzero(features[0])[0] == round_index % 3


def test_config_has_disjoint_protocol_splits_and_expected_grid() -> None:
    smoke = load_config(CONFIG, profile="smoke")
    splits = [set(get_seed_set(smoke, name)) for name in ("development", "tuning", "evaluation")]
    assert not (splits[0] & splits[1] or splits[0] & splits[2] or splits[1] & splits[2])
    assert scaling_cells(smoke) == ((16, 2, 8),)
    full = load_config(CONFIG, profile="full")
    assert len(get_seed_set(full, "tuning")) == 30
    assert len(get_seed_set(full, "evaluation")) == 50


@pytest.mark.parametrize("method", METHODS)
def test_all_smoke_methods_log_required_scaling_fields(method: str) -> None:
    config = load_config(CONFIG, profile="smoke")
    run = run_theory_scaling_cell(
        config,
        41,
        method=method,
        ambient_dimension=16,
        active_rank=2,
        horizon=8,
    )
    assert len(run.records) == 8
    assert run.summary["stream_sha256"] == run.stream_sha256
    required = {
        "Lambda_dynamic",
        "endpoint_logdet",
        "variation_charge",
        "gamma_frozen_float64_audit",
        "gamma_rank_upper",
        "lambda_min_current_active_float64_audit",
        "lambda_min_frozen_active_float64_audit",
        "lambda_min_window_active_float64_audit",
        "optimizer_increment",
        "scaled_optimizer_increment",
        "optimizer_residual_pre_action_float64_audit",
        "optimizer_residual_schedule_pre_action",
        "estimation_error_float64_audit",
        "Q_t",
        "chi_exact_float64_audit",
        "chi_lambda_upper",
        "chi_excitation_upper",
        "psi_float64_audit",
        "psi_lambda_upper",
        "psi_excitation_upper",
        "E_true_float64_audit",
        "F_true_float64_audit",
        "E_upper",
        "F_upper",
        "cg_relative_residual",
        "cg_energy_error_float64_audit",
        "sample_cvp_count",
        "selected_exact_operator_width_squared_audit",
    }
    assert required <= set(run.records[-1])
    assert all(record["audit_semantics"].endswith("not_enclosures") for record in run.records)
    assert all(record["gamma_frozen_float64_audit"] <= record["gamma_rank_upper"] + 1e-10 for record in run.records)
    assert all(record["Lambda_dynamic"] <= record["dynamic_width_upper"] + 1e-9 for record in run.records)
    if method == "full_cg":
        assert run.summary["sample_cvp_count"] > 0
        assert max(record["cg_energy_error_float64_audit"] for record in run.records) <= 0.05 + 1e-10


def test_policy_entry_point_has_no_teacher_argument() -> None:
    parameters = inspect.signature(run_theory_scaling_cell).parameters
    assert "theta_star" not in parameters
    assert "teacher" not in parameters
    source = inspect.getsource(run_theory_scaling_cell)
    assert source.index("commit_action_selection") < source.index("teacher_for_posthoc_audit")


def test_cyclic_excitation_is_not_claimed_before_rank_sized_burn_in() -> None:
    config = load_config(CONFIG, profile="smoke")
    run = run_theory_scaling_cell(
        config,
        41,
        method="exact_current",
        ambient_dimension=16,
        active_rank=2,
        horizon=4,
    )
    assert run.records[0]["excitation_schedule_active"] is False
    assert run.records[1]["excitation_schedule_active"] is False
    assert run.records[2]["excitation_schedule_active"] is True


def _test_metadata() -> dict[str, object]:
    return {
        "git_revision": "test-tree",
        "git_dirty": False,
        "package_versions": {"numpy": np.__version__},
        "hardware": {"machine": "test"},
        "python": {"version": "test", "implementation": "CPython"},
    }


def _write_smoke_grid(
    root: Path,
    *,
    dimensions: tuple[int, ...] = (16,),
    ranks: tuple[int, ...] = (2,),
    horizon: int = 4,
) -> None:
    config = load_config(CONFIG, profile="smoke")
    for dimension in dimensions:
        for rank in ranks:
            for method in METHODS:
                run = run_theory_scaling_cell(
                    config,
                    41,
                    method=method,
                    ambient_dimension=dimension,
                    active_rank=rank,
                    horizon=horizon,
                )
                destination = compact_run_directory(
                    root,
                    profile="smoke",
                    seed_set="development",
                    dimension=dimension,
                    rank=rank,
                    horizon=horizon,
                    method=method,
                    seed=41,
                )
                save_compact_run(
                    run, config, destination, metadata=_test_metadata()
                )


def test_compact_npz_is_deterministic_and_contains_only_numeric_arrays(
    tmp_path: Path,
) -> None:
    config = load_config(CONFIG, profile="smoke")
    run = run_theory_scaling_cell(
        config,
        41,
        method="exact_current",
        ambient_dimension=16,
        active_rank=2,
        horizon=8,
    )
    arrays = records_to_numeric_arrays(run)
    first = write_deterministic_npz(tmp_path / "first.npz", arrays)
    second = write_deterministic_npz(tmp_path / "second.npz", arrays)
    assert sha256_file(first) == sha256_file(second)
    with np.load(first, allow_pickle=False) as archive:
        assert set(archive.files) == set(arrays)
        assert archive["round"].tolist() == list(range(1, 9))
        assert archive["selected_exact_operator_width_squared_audit"].shape == (8,)
        assert all(not archive[name].dtype.hasobject for name in archive.files)


def test_compact_aggregate_validates_coverage_and_computes_paired_outputs(
    tmp_path: Path,
) -> None:
    config = load_config(CONFIG, profile="smoke")
    for method in METHODS:
        run = run_theory_scaling_cell(
            config,
            41,
            method=method,
            ambient_dimension=16,
            active_rank=2,
            horizon=8,
        )
        destination = compact_run_directory(
            tmp_path,
            profile="smoke",
            seed_set="development",
            dimension=16,
            rank=2,
            horizon=8,
            method=method,
            seed=41,
        )
        save_compact_run(run, config, destination, metadata=_test_metadata())
        manifest, arrays, summary = load_compact_run(
            destination,
            method=method,
            seed=41,
            dimension=16,
            rank=2,
            horizon=8,
        )
        assert manifest["rounds_sha256"] == manifest["verified_file_hashes"]["rounds"]
        assert arrays["Lambda_dynamic"].shape == (8,)
        assert summary["method"] == method

    aggregate = aggregate_primary_slice(
        tmp_path,
        seeds=(41,),
        methods=METHODS,
        checkpoints=(2, 4, 8),
        profile="smoke",
        seed_set="development",
        dimension=16,
        rank=2,
        horizon=8,
        bootstrap_replicates=31,
        bootstrap_seed=903,
    )
    assert aggregate["coverage"] == {
        "expected_runs": 8,
        "validated_runs": 8,
        "exact": True,
    }
    assert len(aggregate["seed_level"]) == 8 * 3
    assert aggregate["full_vs_cg"]["online_action_disagreement_rate"] == 0.0
    assert all(
        count == 0
        for method_counts in aggregate["theorem_event_failure_counts_float64_audit"].values()
        for count in method_counts.values()
    )
    assert aggregate["slopes"]["exact_current"]["Lambda"]["status"] == "ok"
    with pytest.raises(ValueError, match="coverage mismatch"):
        aggregate_primary_slice(
            tmp_path,
            seeds=(41,),
            methods=("exact_current", "full_cg"),
            checkpoints=(2, 4, 8),
            profile="smoke",
            seed_set="development",
            dimension=16,
            rank=2,
            horizon=8,
            bootstrap_replicates=5,
        )


def test_full_grid_aggregate_requires_and_validates_cartesian_coverage(
    tmp_path: Path,
) -> None:
    dimensions = (16, 24)
    ranks = (2, 3)
    _write_smoke_grid(tmp_path, dimensions=dimensions, ranks=ranks)
    aggregate = aggregate_full_grid(
        tmp_path,
        seeds=(41,),
        dimensions=dimensions,
        ranks=ranks,
        checkpoints=(2, 4),
        profile="smoke",
        seed_set="development",
        horizon=4,
        bootstrap_replicates=7,
    )
    assert aggregate["coverage"] == {
        "expected_cells": 4,
        "validated_cells": 4,
        "expected_runs": 32,
        "validated_runs": 32,
        "exact": True,
    }
    assert set(aggregate["cells"]) == {
        "d-16_r-2_T-4",
        "d-16_r-3_T-4",
        "d-24_r-2_T-4",
        "d-24_r-3_T-4",
    }


def test_full_grid_aggregate_rejects_missing_run(tmp_path: Path) -> None:
    _write_smoke_grid(tmp_path)
    missing = compact_run_directory(
        tmp_path,
        profile="smoke",
        seed_set="development",
        dimension=16,
        rank=2,
        horizon=4,
        method="greedy",
        seed=41,
    )
    shutil.rmtree(missing)
    with pytest.raises(ValueError, match="coverage mismatch"):
        aggregate_full_grid(
            tmp_path,
            seeds=(41,),
            dimensions=(16,),
            ranks=(2,),
            checkpoints=(2, 4),
            profile="smoke",
            seed_set="development",
            horizon=4,
            bootstrap_replicates=3,
        )


def test_full_grid_aggregate_rejects_duplicate_run(tmp_path: Path) -> None:
    _write_smoke_grid(tmp_path)
    original = compact_run_directory(
        tmp_path,
        profile="smoke",
        seed_set="development",
        dimension=16,
        rank=2,
        horizon=4,
        method="exact_current",
        seed=41,
    )
    original.with_name("seed-041").symlink_to(
        original.name, target_is_directory=True
    )
    with pytest.raises(ValueError, match="duplicate runs"):
        aggregate_full_grid(
            tmp_path,
            seeds=(41,),
            dimensions=(16,),
            ranks=(2,),
            checkpoints=(2, 4),
            profile="smoke",
            seed_set="development",
            horizon=4,
            bootstrap_replicates=3,
        )


def test_full_grid_aggregate_rejects_hash_failure(tmp_path: Path) -> None:
    _write_smoke_grid(tmp_path)
    directory = compact_run_directory(
        tmp_path,
        profile="smoke",
        seed_set="development",
        dimension=16,
        rank=2,
        horizon=4,
        method="exact_current",
        seed=41,
    )
    summary = directory / "summary.json"
    summary.write_text(summary.read_text(encoding="ascii") + "\n", encoding="ascii")
    with pytest.raises(ValueError, match="hash mismatch"):
        aggregate_full_grid(
            tmp_path,
            seeds=(41,),
            dimensions=(16,),
            ranks=(2,),
            checkpoints=(2, 4),
            profile="smoke",
            seed_set="development",
            horizon=4,
            bootstrap_replicates=3,
        )
