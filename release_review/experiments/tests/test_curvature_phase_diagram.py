from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.curvature_phase_diagram import (
    METHODS,
    ConfigError,
    aggregate_summaries,
    cells_from_config,
    generate_environment,
    load_config,
    run_common_trajectory_diagnostic,
    run_online_policy,
    run_study,
    validate_config,
)


CONFIG_PATH = (
    Path(__file__).resolve().parents[1]
    / "configs"
    / "curvature_phase_diagram.yaml"
)


def _config() -> dict[str, object]:
    return load_config(CONFIG_PATH)


def test_grid_is_exact_preregistered_evaluation_only_and_balanced() -> None:
    config = _config()
    validate_config(config)
    cells = cells_from_config(config)

    assert len(cells) == 8
    assert len(config["study"]["evaluation_seeds"]) == 30
    assert config["study"]["tuning_enabled"] is False
    assert config["study"]["cell_selection"] == "none_preregistered_all_cells"
    assert tuple(config["methods"]) == METHODS
    assert all(cell.representation_drift == 0.0 for cell in cells)
    assert all(
        cell.representation_drift_status == "not_run_fixed_zero" for cell in cells
    )

    for name in (
        "active_spectrum_condition_number",
        "rotation_degrees",
        "action_gap",
        "nuisance_strength",
        "effective_rank",
        "damping",
    ):
        values = [getattr(cell, name) for cell in cells]
        unique = sorted(set(values))
        assert len(unique) == 2
        assert values.count(unique[0]) == values.count(unique[1]) == 4


def test_validation_rejects_seed_shortfall_and_posthoc_selection() -> None:
    config = _config()
    config["study"]["evaluation_seeds"] = list(range(29))
    with pytest.raises(ConfigError, match="at least 30"):
        validate_config(config)

    config = _config()
    config["study"]["cell_selection"] = "search_for_full_wins"
    with pytest.raises(ConfigError, match="forbid"):
        validate_config(config)


def test_environment_has_requested_rank_condition_gap_and_bound() -> None:
    config = _config()
    cell = cells_from_config(config)[-1]
    environment = generate_environment(config, cell, 201)
    positive = environment.covariance_eigenvalues[
        environment.covariance_eigenvalues > 0.0
    ]

    assert positive.size == cell.effective_rank
    np.testing.assert_allclose(
        positive[0] / positive[-1],
        cell.active_spectrum_condition_number,
        rtol=1e-13,
    )
    differences = environment.means[:, :-1] - environment.means[:, 1:]
    np.testing.assert_allclose(differences, cell.action_gap, rtol=0.0, atol=2e-15)
    assert np.max(np.linalg.norm(environment.features, axis=2)) <= (
        environment.feature_bound + 1e-14
    )
    different_future = generate_environment(config, cell, 999)
    assert different_future.feature_bound == environment.feature_bound
    assert environment.feature_bound >= environment.realized_feature_max
    assert different_future.feature_bound >= different_future.realized_feature_max


def test_exact_online_and_common_reference_identities() -> None:
    config = _config()
    config["environment"]["rounds"] = 6
    cell = cells_from_config(config)[0]
    environment = generate_environment(config, cell, 204)
    online = run_online_policy(
        config, cell, 204, "exact_full", environment=environment
    )
    common = run_common_trajectory_diagnostic(
        config, cell, 204, "exact_full", online, environment=environment
    )

    assert online.summary["executed_policy"] is True
    assert common.summary["executed_policy"] is False
    assert common.summary["causal_regret_claim"] is False
    assert common.summary["regret_reported"] is False
    assert "cumulative_pseudo_regret" not in common.summary
    assert all(record["width_ratio_cv"] == pytest.approx(0.0) for record in online.rounds)
    assert all(record["width_spearman"] == pytest.approx(1.0) for record in online.rounds)
    assert all(record["width_kendall"] == pytest.approx(1.0) for record in online.rounds)
    assert all(record["ucb_score_disagreement"] == pytest.approx(0.0) for record in online.rounds)
    assert all(
        0.0 <= record["candidate_full_leading_projection_mean"] <= 1.0
        for record in online.rounds
    )
    assert all(not record["top_action_disagreement"] for record in online.rounds)
    assert all(record["diagnostic_action_matches_logged_action"] for record in common.rounds)
    assert all(
        not record["scalar_rescaled_score_disagreement"] for record in common.rounds
    )


def test_all_methods_execute_independent_policies_and_common_replay() -> None:
    config = _config()
    config["environment"]["rounds"] = 5
    cell = cells_from_config(config)[3]
    environment = generate_environment(config, cell, 207)
    baseline = run_online_policy(
        config, cell, 207, "exact_full", environment=environment
    )
    for method in METHODS:
        online = (
            baseline
            if method == "exact_full"
            else run_online_policy(config, cell, 207, method, environment=environment)
        )
        diagnostic = run_common_trajectory_diagnostic(
            config, cell, 207, method, baseline, environment=environment
        )
        assert online.summary["execution_mode"] == "online_adaptive_policy"
        assert diagnostic.summary["execution_mode"] == (
            "offline_common_trajectory_diagnostic"
        )
        assert diagnostic.actions == baseline.actions
        assert all(np.isfinite(float(row["width_ratio_cv"])) for row in online.rounds)
        assert all(
            np.isfinite(float(row["global_transfer_alg_over_full"]))
            for row in diagnostic.rounds
        )


def test_paired_classification_uses_method_minus_full_ci_without_selection() -> None:
    base = {
        "schema_version": 1,
        "cell_id": "cell",
        "cell": {"cell_id": "cell"},
        "execution_mode": "online_adaptive_policy",
        "round_count": 2,
        "width_ratio_cv_mean": 0.0,
        "top_action_disagreement_rate": 0.0,
        "evaluation_cell_selected_posthoc": False,
    }
    online: list[dict[str, object]] = []
    for seed in range(30):
        online.append(
            {
                **base,
                "seed": seed,
                "method": "exact_full",
                "cumulative_pseudo_regret": 1.0,
            }
        )
        online.append(
            {
                **base,
                "seed": seed,
                "method": "diagonal",
                "cumulative_pseudo_regret": 2.0 + 0.01 * (seed % 2),
            }
        )
    _, paired = aggregate_summaries(online, [])
    comparison = paired[0]
    assert comparison["classification"] == "full_lower_regret"
    assert comparison["paired_interval"]["n"] == 30
    assert comparison["paired_interval"]["ci95_low"] > 0.0
    assert comparison["posthoc_cell_or_method_selection"] is False


def test_artifact_contract_writes_30_seed_aggregation_and_provenance(
    tmp_path: Path,
) -> None:
    config = copy.deepcopy(_config())
    config["environment"]["rounds"] = 2
    config["environment"]["dimension"] = 4
    config["method_options"]["lanczos_rank"] = 2
    config["method_options"]["block_size"] = 2
    config["preregistered_cells"] = [copy.deepcopy(config["preregistered_cells"][0])]
    config["preregistered_cells"][0]["effective_rank"] = 3
    config["output"]["write_round_records"] = False
    output = tmp_path / "artifact"

    manifest = run_study(config, output)

    assert manifest["evaluation_seed_count"] == 30
    assert manifest["cell_count"] == 1
    assert manifest["online_run_count"] == 30 * len(METHODS)
    assert manifest["common_trajectory_run_count"] == 30 * len(METHODS)
    assert manifest["paired_comparison_count"] == 30 * 0 + len(METHODS) - 1
    assert manifest["evaluation_cell_selection"] == "none"
    assert manifest["full_win_search"] is False
    for name in (
        "preregistered_grid.json",
        "online_summaries.jsonl",
        "common_trajectory_summaries.jsonl",
        "aggregates.jsonl",
        "paired_full_comparisons.jsonl",
        "manifest.json",
    ):
        assert (output / name).is_file()
    preregistered = json.loads((output / "preregistered_grid.json").read_text())
    assert preregistered["evaluation_seed_count"] == 30
    assert preregistered["cell_selection"] == "none_preregistered_all_cells"
