from __future__ import annotations

import copy
import inspect
from pathlib import Path

import numpy as np
import pytest

from experiments.aggregate_results import (
    aggregate_results,
    validate_aggregate_provenance_sidecar,
    write_aggregate_with_provenance,
)
from experiments.config import get_seed_set, load_config
from experiments.make_balanced_benchmark_artifact import build_artifact
from experiments.run_balanced_benchmark import (
    CONTEXTUAL_METHODS,
    CONTEXT_FREE_METHODS,
    FULL_NETWORK_METHODS,
    METHODS,
    PostActionTeacherOracle,
    build_tuning_selection,
    configured_methods,
    hyperparameter_grid,
    make_stream,
    run_experiment,
    run_policy,
    validate_tuning_selection,
    winner_counts,
)


CONFIG = Path("experiments/configs/balanced_benchmark.yaml")


def _smoke_config() -> dict[str, object]:
    return load_config(CONFIG, profile="smoke")


def test_balanced_benchmark_protocol_and_exact_teacher_balance() -> None:
    smoke = _smoke_config()
    full = load_config(CONFIG, profile="full")
    assert configured_methods(smoke) == METHODS
    assert CONTEXTUAL_METHODS | CONTEXT_FREE_METHODS == set(METHODS)
    assert CONTEXTUAL_METHODS & CONTEXT_FREE_METHODS == set()
    assert "cc_ucb_full_ggn_cg" in FULL_NETWORK_METHODS
    assert winner_counts() == (4, 3, 3, 2, 4)
    assert max(winner_counts()) - min(winner_counts()) <= 2
    assert len(get_seed_set(full, "evaluation")) == 30
    assert set(get_seed_set(full, "tuning")).isdisjoint(
        get_seed_set(full, "evaluation")
    )
    assert full["sanity_check"]["predefined_contextual_method"] == "linucb"


def test_stream_is_deterministic_and_teacher_is_post_action_only() -> None:
    first = make_stream(260, 24, 0.1)
    second = make_stream(260, 24, 0.1)
    other = make_stream(261, 24, 0.1)
    np.testing.assert_array_equal(first.contexts, second.contexts)
    np.testing.assert_array_equal(first.noises, second.noises)
    assert first.digest == second.digest
    assert first.digest != other.digest

    policy_source = inspect.getsource(run_policy)
    assert ".mean_rewards" not in policy_source
    assert policy_source.index("action = int(np.argmax(scores))") < policy_source.index(
        "teacher_oracle.observe_after_action"
    )
    public_oracle_names = {
        name for name in dir(PostActionTeacherOracle) if not name.startswith("_")
    }
    assert public_oracle_names == {"observe_after_action"}


def test_neural_linear_is_a_bayesian_head_and_not_neural_ucb() -> None:
    config = _smoke_config()
    neural_linear = run_policy(
        config,
        "neural_linear",
        260,
        phase="evaluation",
        ridge=1.0,
        bonus_scale=1.0,
    )
    last_layer_ucb = run_policy(
        config,
        "frozen_last_layer_ucb",
        260,
        phase="evaluation",
        ridge=1.0,
        bonus_scale=1.0,
    )
    neural_ucb = run_policy(
        config,
        "neural_ucb",
        260,
        phase="evaluation",
        ridge=1.0,
        bonus_scale=1.0,
    )

    assert neural_linear.summary["representation_update_protocol"] == (
        "frozen_initialized_backbone"
    )
    assert neural_linear.summary["model_update_seconds"] == 0.0
    assert all(record["model_update_count"] == 0 for record in neural_linear.records)
    assert all(record["curvature_dimension"] == 25 for record in neural_linear.records)
    np.testing.assert_allclose(
        neural_linear.records[0]["predicted_means_all_actions"],
        last_layer_ucb.records[0]["predicted_means_all_actions"],
    )
    np.testing.assert_allclose(
        neural_linear.records[0]["predictive_widths_all_actions"],
        last_layer_ucb.records[0]["predictive_widths_all_actions"],
    )
    assert neural_linear.records[0]["policy_scores_all_actions"] != (
        last_layer_ucb.records[0]["policy_scores_all_actions"]
    )
    assert neural_ucb.summary["method_implementation"] == (
        "local_full_network_linearized_ucb"
    )
    assert neural_ucb.summary["published_implementation_claim"] is False
    assert all(record["model_update_count"] == 1 for record in neural_ucb.records)
    assert all(record["curvature_dimension"] == 45 for record in neural_ucb.records)


def test_cc_ucb_relinearizes_and_checks_each_cg_solve() -> None:
    config = _smoke_config()
    cc_ucb = run_policy(
        config,
        "cc_ucb_full_ggn_cg",
        260,
        phase="evaluation",
        ridge=1.0,
        bonus_scale=1.0,
    )
    neural_ucb = run_policy(
        config,
        "neural_ucb",
        260,
        phase="evaluation",
        ridge=1.0,
        bonus_scale=1.0,
    )
    assert cc_ucb.summary["current_parameter_history_relinearized"] is True
    assert cc_ucb.summary["matrix_free_dense_gram_materialized"] is False
    assert cc_ucb.summary["all_cg_solves_converged"] is True
    assert cc_ucb.summary["cg_total_iterations"] > 0
    assert cc_ucb.summary["cg_total_operator_calls"] > (
        cc_ucb.summary["cg_total_iterations"]
    )
    tolerance = float(cc_ucb.summary["cg_relative_residual_tolerance"])
    assert cc_ucb.summary["cg_maximum_relative_residual"] <= tolerance + 1e-12
    for record in cc_ucb.records:
        assert len(record["cg_iterations_all_actions"]) == 5
        assert len(record["cg_relative_residuals_all_actions"]) == 5
        assert len(record["cg_operator_calls_all_actions"]) == 5
        assert record["cg_all_actions_converged"] is True
    assert "current_parameter_history_relinearized" not in neural_ucb.summary
    assert "cg_iterations_all_actions" not in neural_ucb.records[0]


def test_selection_artifact_rejects_tampering_and_evaluation_requires_it(
    tmp_path: Path,
) -> None:
    config = _smoke_config()
    tuning_runs = [
        run_policy(
            config,
            method,
            seed,
            phase="tuning",
            ridge=ridge,
            bonus_scale=bonus,
        )
        for method in configured_methods(config)
        for ridge, bonus in hyperparameter_grid(config, method)
        for seed in get_seed_set(config, "tuning")
    ]
    artifact = build_tuning_selection(config, tuning_runs)
    assert set(validate_tuning_selection(config, artifact)) == set(METHODS)

    leaked = copy.deepcopy(artifact)
    leaked["evaluation_outcomes_used"] = True
    with pytest.raises(ValueError, match="evaluation_outcomes_used"):
        validate_tuning_selection(config, leaked)
    duplicated = copy.deepcopy(artifact)
    duplicated["candidates"].append(copy.deepcopy(duplicated["candidates"][0]))
    with pytest.raises(ValueError, match="duplicate candidate"):
        validate_tuning_selection(config, duplicated)
    with pytest.raises(ValueError, match="requires a tuning-selection artifact"):
        run_experiment(
            config,
            seed_set="evaluation",
            output_root=tmp_path,
            tuning_selection=None,
        )


def test_smoke_pipeline_aggregates_horizons_pairs_seed_rows_and_provenance(
    tmp_path: Path,
) -> None:
    config = _smoke_config()
    selection_path = tmp_path / "smoke" / "tuning_selection.json"
    tuning = run_experiment(
        config,
        seed_set="tuning",
        output_root=tmp_path,
        tuning_selection=selection_path,
    )
    assert len(tuning) == len(METHODS) * len(get_seed_set(config, "tuning"))
    evaluation = run_experiment(
        config,
        seed_set="evaluation",
        output_root=tmp_path,
        tuning_selection=selection_path,
    )
    assert len(evaluation) == len(METHODS) * len(get_seed_set(config, "evaluation"))

    raw_root = tmp_path / "smoke" / "evaluation"
    aggregate = aggregate_results(raw_root, seed_set="evaluation")
    assert aggregate["group_count"] == len(METHODS)
    assert aggregate["paired_comparison_count"] == len(METHODS) - 1
    assert aggregate["all_groups_complete"] is True
    assert aggregate["all_paired_comparisons_complete"] is True
    for comparison in aggregate["paired_comparisons"]:
        assert comparison["reference_method"] == "cc_ucb_full_ggn_cg"
        assert comparison["pair_count"] == 2
    for group in aggregate["groups"]:
        assert [row["horizon"] for row in group["horizons"]] == [12, 24]
        final_metrics = group["horizons"][-1]["metrics"]
        for name in (
            "cumulative_pseudo_regret",
            "cumulative_reward",
            "mean_reward",
            "cumulative_model_update_seconds",
            "cumulative_uncertainty_seconds",
            "peak_host_memory_bytes",
            "cumulative_action_disagreement_rate",
        ):
            assert final_metrics[name]["n"] == 2

    artifact = build_artifact(
        config_path=CONFIG,
        raw_root=raw_root,
        selection_path=selection_path,
        profile="smoke",
    )
    assert len(artifact["seed_level_results"]) == len(METHODS) * 2
    assert artifact["contextual_sanity_check"][
        "passes_mean_regret_prerequisite"
    ] is True
    assert set(artifact["method_results"]) == set(METHODS)
    assert artifact["method_results"]["cc_ucb_full_ggn_cg"][
        "all_cg_solves_converged"
    ] is True
    assert isinstance(
        artifact["empirical_finding"][
            "cc_ucb_worse_than_each_listed_comparator"
        ],
        bool,
    )
    references = {
        row["reference_method"] for row in artifact["paired_horizon_comparisons"]
    }
    assert references == {
        "cc_ucb_full_ggn_cg",
        "gaussian_ucb1",
        "gaussian_context_free_ts",
    }
    assert all(
        [horizon["horizon"] for horizon in row["horizons"]] == [12, 24]
        for row in artifact["paired_horizon_comparisons"]
    )
    output, sidecar = write_aggregate_with_provenance(
        artifact, tmp_path / "derived" / "balanced.json"
    )
    provenance = validate_aggregate_provenance_sidecar(output, sidecar)
    assert provenance["input_set_sha256"] == artifact["input_set_sha256"]


def test_predefined_contextual_sanity_method_beats_context_free_controls() -> None:
    config = load_config(CONFIG, profile="full")
    seeds = get_seed_set(config, "evaluation")[:10]
    settings = {
        "linucb": (0.5, 0.5),
        "gaussian_ucb1": (0.0, 0.5),
        "gaussian_context_free_ts": (0.5, 2.0),
    }
    means: dict[str, float] = {}
    for method, (ridge, bonus) in settings.items():
        regrets = [
            run_policy(
                config,
                method,
                seed,
                phase="evaluation",
                ridge=ridge,
                bonus_scale=bonus,
            ).summary["cumulative_pseudo_regret"]
            for seed in seeds
        ]
        means[method] = float(np.mean(regrets, dtype=np.float64))
    assert means["linucb"] < means["gaussian_ucb1"]
    assert means["linucb"] < means["gaussian_context_free_ts"]
