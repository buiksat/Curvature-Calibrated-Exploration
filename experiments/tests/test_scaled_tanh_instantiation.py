from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.artifact_utils import write_json_artifact
from experiments.config import load_config
from experiments.run_scaled_tanh_instantiation import (
    Cell,
    build_optimizer_selection,
    cells,
    load_optimizer_selection,
    make_environment,
    make_stream,
    residual_factor,
    run_evaluation,
    run_trajectory,
    validate_config,
)


CONFIG = Path("experiments/configs/scaled_tanh_instantiation.yaml")


def _smoke_config() -> dict[str, object]:
    return load_config(CONFIG, profile="smoke")


def _tiny_config() -> dict[str, object]:
    config = copy.deepcopy(_smoke_config())
    config["rounds"] = 6
    config["horizons"] = [6]
    config["width_ratios"] = [1.0]
    config["methods"] = ["exact_current_relative", "full_cg_relative"]
    config["seed_sets"] = {
        "development": [42],
        "tuning": [0],
        "evaluation": [200],
    }
    config["optimizer_selection"] = {
        "method": "exact_current_relative",
        "damping_candidates": [float(config["damping"])],
        "horizons": [6],
        "width_ratios": [1.0],
        "criterion": "single-candidate unit-test selection",
        "evaluation_metrics_read": False,
    }
    return config


def test_config_environment_and_stream_pairing_are_predeclared() -> None:
    smoke = _smoke_config()
    full = load_config(CONFIG, profile="full")
    validate_config(smoke)
    validate_config(full)
    assert set(full["seed_sets"]["tuning"]).isdisjoint(
        full["seed_sets"]["evaluation"]
    )
    assert set(full["excluded_diagnostic_seeds"]).isdisjoint(
        full["seed_sets"]["evaluation"]
    )
    assert set(full["abandoned_replacement_diagnostic_seeds"]).isdisjoint(
        full["seed_sets"]["evaluation"]
    )
    assert full["seed_sets"]["evaluation"] == list(range(1200, 1250))

    environment = make_environment(smoke)
    norms = np.linalg.norm(environment.active_features, axis=-1)
    np.testing.assert_allclose(norms, 1.0, atol=2e-15)
    assert np.linalg.matrix_rank(
        environment.active_features.reshape(-1, int(smoke["effective_rank"]))
    ) == int(smoke["effective_rank"])
    assert len(set(environment.optimal_actions.tolist())) == int(
        smoke["action_count"]
    )
    assert environment.minimum_gap > 0.0

    study_cells = cells(smoke)
    short_one = next(
        cell for cell in study_cells if cell.horizon == 32 and cell.width_ratio == 1.0
    )
    short_four = next(
        cell for cell in study_cells if cell.horizon == 32 and cell.width_ratio == 4.0
    )
    long_one = next(
        cell for cell in study_cells if cell.horizon == 64 and cell.width_ratio == 1.0
    )
    first = make_stream(smoke, short_one, 200)
    same_horizon = make_stream(smoke, short_four, 200)
    longer = make_stream(smoke, long_one, 200)
    np.testing.assert_array_equal(first.contexts, same_horizon.contexts)
    np.testing.assert_array_equal(first.noises, same_horizon.noises)
    np.testing.assert_array_equal(first.contexts, longer.contexts[:32])
    np.testing.assert_array_equal(first.noises, longer.noises[:32])


def test_dense_and_cg_paths_match_and_all_theorem_arrays_are_endpoint_correct() -> None:
    config = _smoke_config()
    environment = make_environment(config)
    factor = residual_factor(config, 16)
    cell = Cell(horizon=16, width_ratio=4.0, width=64.0 * factor, residual_factor=factor)
    stream = make_stream(config, cell, 200)
    dense = run_trajectory(
        config, cell, environment, stream, method="exact_current_relative"
    )
    cg = run_trajectory(
        config, cell, environment, stream, method="full_cg_relative"
    )

    np.testing.assert_array_equal(
        dense.arrays["selected_actions"], cg.arrays["selected_actions"]
    )
    np.testing.assert_allclose(
        cg.arrays["computed_width_squared"],
        cg.arrays["dense_width_squared"],
        rtol=1e-10,
        atol=1e-12,
    )
    assert cg.summary["all_cg_solves_converged"] is True
    assert cg.summary["maximum_cg_energy_error"] <= config["cg_target_energy_error"]
    assert cg.summary["sample_cvps"] > 0

    for run in (dense, cg):
        arrays = run.arrays
        assert arrays["gamma"][0] == pytest.approx(0.0)
        assert arrays["gamma_endpoint"][0] > 0.0
        assert arrays["Gamma_tail_endpoint"][0] > 0.0
        assert arrays["gamma_endpoint"][-1] >= arrays["gamma"][-1]
        assert np.all(arrays["endpoint_information_pass"])
        assert np.all(arrays["residual_envelope_pass"])
        assert np.all(arrays["residual_endpoint_pass"])
        assert np.all(arrays["old_transfer_pass"])
        assert np.all(arrays["old_centering_pass"])
        assert np.all(arrays["regret_bound_pass"])
        assert np.all(arrays["premise_pass"])
        assert np.all(
            arrays["exact_E_through_round"]
            <= arrays["predictable_E_through_round"] + 1e-12
        )
        assert np.all(
            arrays["exact_F_next"] <= arrays["predictable_F_next"] + 1e-12
        )
        np.testing.assert_allclose(
            arrays["theorem_rhs"],
            arrays["rhs_statistical_component"]
            + arrays["rhs_linearization_component"],
            rtol=2e-15,
            atol=2e-15,
        )
        np.testing.assert_allclose(
            arrays["rhs_information_term"], arrays["Gamma_tail_endpoint"]
        )


def test_optimizer_selection_is_hash_bound_and_evaluation_requires_it(
    tmp_path: Path,
) -> None:
    config = _tiny_config()
    validate_config(config)
    selection_path = tmp_path / "optimizer_selection.json"
    artifact = build_optimizer_selection(
        config,
        profile="smoke",
        selection_path=selection_path,
        overwrite=False,
    )
    assert artifact["evaluation_metrics_read"] is False
    assert artifact["selected_damping"] == config["damping"]
    loaded = load_optimizer_selection(config, selection_path, profile="smoke")
    assert loaded["config_digest"] == artifact["config_digest"]

    output_root = tmp_path / "raw"
    result = run_evaluation(
        config,
        profile="smoke",
        output_root=output_root,
        selection_path=selection_path,
        overwrite=False,
        workers=1,
    )
    assert result["run_count"] == 2
    manifest_paths = sorted(output_root.glob("smoke/evaluation/**/manifest.json"))
    assert len(manifest_paths) == 2
    for path in manifest_paths:
        manifest = json.loads(path.read_text(encoding="ascii"))
        assert (
            manifest["optimizer_selection_sha256"]
            == result["optimizer_selection_sha256"]
        )
        assert manifest["evaluation_data_used_for_selection"] is False

    tampered = copy.deepcopy(artifact)
    tampered["evaluation_metrics_read"] = True
    write_json_artifact(selection_path, tampered)
    with pytest.raises(ValueError, match="evaluation_metrics_read"):
        load_optimizer_selection(config, selection_path, profile="smoke")


def test_teacher_values_are_first_read_after_action_selection() -> None:
    source = inspect.getsource(run_trajectory)
    action_index = source.index("selected = _stable_argmax")
    teacher_index = source.index("flat_teacher_q_audit = category_features @ environment.teacher")
    assert action_index < teacher_index

