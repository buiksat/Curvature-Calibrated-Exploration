from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.aggregate_results import aggregate_results
from experiments.config import load_config
from experiments.logging_utils import canonical_json
from experiments.run_covertype import (
    NONCONTEXTUAL_METHODS,
    SUPPORTED_METHODS,
    PreparedCovertypeData,
    build_test_class_diagnostics,
    method_protocol,
    prepare_covertype_data,
    run_experiment,
    run_policy,
    verify_selection_authorization,
    write_test_class_diagnostics,
    write_tuning_selection,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "experiments" / "configs" / "covertype_rerun.yaml"


def _config(*, rounds: int = 3, all_methods: bool = False) -> dict[str, object]:
    config = load_config(CONFIG, profile="smoke")
    config["rounds"] = rounds
    if all_methods:
        config["methods"] = list(SUPPORTED_METHODS)
    return config


def _arrays(sample_count: int = 70) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(9182)
    continuous = rng.normal(
        loc=np.linspace(-3.0, 4.0, 10),
        scale=np.linspace(0.4, 2.2, 10),
        size=(sample_count, 10),
    )
    binary = rng.integers(0, 2, size=(sample_count, 44)).astype(np.float64)
    features = np.concatenate((continuous, binary), axis=1).astype(np.float64)
    labels = np.resize(np.arange(1, 8, dtype=np.int64), sample_count)
    return features, labels


def _prepared(config: dict[str, object]) -> tuple[PreparedCovertypeData, np.ndarray]:
    features, labels = _arrays()
    original = features.copy()
    return prepare_covertype_data(config, dataset=(features, labels)), original


def test_train_only_standardization_and_exact_deterministic_splits() -> None:
    config = _config()
    first, original = _prepared(config)
    second = prepare_covertype_data(config, dataset=_arrays())

    np.testing.assert_array_equal(first.features[:, 10:], original[:, 10:])
    train = first.indices("train")
    np.testing.assert_allclose(
        np.mean(first.features[train, :10], axis=0), 0.0, atol=2e-15
    )
    np.testing.assert_allclose(
        np.std(first.features[train, :10], axis=0), 1.0, atol=2e-15
    )
    assert first.features.dtype == np.float64
    assert first.labels.dtype == np.int64
    assert first.labels.min() == 0
    assert first.labels.max() == 6
    assert first.provenance["injected"] is True
    assert first.provenance["dataset_file"] == []
    assert sum(len(first.indices(name)) for name in ("train", "validation", "test")) == 70
    for name in ("train", "validation", "test"):
        np.testing.assert_array_equal(first.indices(name), second.indices(name))
        assert first.split_protocol["partitions"][name]["indices_sha256"]

    full_config = load_config(CONFIG, profile="full")
    assert tuple(full_config["methods"]) == SUPPORTED_METHODS
    assert full_config["tuning_rounds"] == 200
    assert full_config["rounds"] == 1500
    assert full_config["horizons"] == [200, 500, 1000, 1500]


def test_custom_fetcher_is_offline_nonmutating_and_records_its_identity(
    tmp_path: Path,
) -> None:
    config = _config()
    features, labels = _arrays()
    original = features.copy()
    calls: dict[str, object] = {}

    def local_fetcher(**kwargs: object) -> tuple[np.ndarray, np.ndarray]:
        calls.update(kwargs)
        return features, labels

    data = prepare_covertype_data(
        config,
        fetcher=local_fetcher,
        data_home=tmp_path,
        download=False,
    )
    np.testing.assert_array_equal(features, original)
    assert calls["data_home"] == str(tmp_path)
    assert calls["download_if_missing"] is False
    assert calls["return_X_y"] is True
    assert calls["shuffle"] is False
    assert data.provenance["loader"].endswith("local_fetcher")
    assert data.provenance["upstream_archive_sha256"] is None

    subset_labels = np.resize(np.arange(1, 4, dtype=np.int64), len(labels))
    subset = prepare_covertype_data(config, dataset=(features, subset_labels))
    assert set(subset.labels) == {0, 1, 2}


def test_all_methods_execute_binary_bandit_policies_with_common_random_numbers() -> None:
    config = _config(rounds=4, all_methods=True)
    data, _ = _prepared(config)
    runs = [
        run_policy(
            config,
            data,
            method,
            150,
            phase="evaluation",
            damping=0.0 if method in NONCONTEXTUAL_METHODS else 1.0,
            bonus_scale=(
                0.0
                if method in (*NONCONTEXTUAL_METHODS, "greedy_full_network")
                else 2.0
            ),
        )
        for method in SUPPORTED_METHODS
    ]

    assert len({run.dataset_indices for run in runs}) == 1
    contextual = [run for run in runs if run.method not in NONCONTEXTUAL_METHODS]
    assert len({run.summary["initialization_seed"] for run in contextual}) == 1
    assert all(run.summary["executed_policy"] for run in runs)
    assert all(run.summary["gaussian_regret_theorem_certified"] is False for run in runs)
    assert all(
        run.summary["curvature_likelihood"]
        == "unit_variance_gaussian_squared_loss"
        for run in contextual
    )
    assert all(
        run.summary["curvature_likelihood"] == "not_applicable"
        for run in runs
        if run.method in NONCONTEXTUAL_METHODS
    )
    for run in runs:
        assert len(run.records) == 4
        for record in run.records:
            assert record["enumerated_actions"] == list(range(7))
            assert record["reward"] in {0.0, 1.0}
            assert record["pseudo_regret"] == 1.0 - record["reward"]
            assert record["policy_feedback"] == "selected_arm_reward_only"
            assert record["test_label_used_for_hyperparameter_selection"] is False
            assert record["round_runtime_seconds"] >= 0.0
            assert record["peak_host_memory_bytes"] > 0
            assert (
                record["peak_host_memory_scope"]
                == "process_lifetime_high_water_mark"
            )

    last_layer = next(run for run in runs if run.method == "last_layer_full")
    backbone_count = 4 * 54 + 4
    np.testing.assert_array_equal(last_layer.final_displacement[:backbone_count], 0.0)
    full = next(run for run in runs if run.method == "full_network_ggn_cg")
    assert np.linalg.norm(full.final_displacement[:backbone_count]) > 0.0
    frozen = next(run for run in runs if run.method == "frozen_full_gram")
    diagonal = next(run for run in runs if run.method == "diagonal_full_network")
    np.testing.assert_allclose(
        full.records[0]["predictive_variances"],
        frozen.records[0]["predictive_variances"],
        rtol=2e-13,
        atol=2e-13,
    )
    np.testing.assert_allclose(
        full.records[0]["predictive_variances"],
        diagonal.records[0]["predictive_variances"],
        rtol=2e-13,
        atol=2e-13,
    )
    assert not np.allclose(
        full.records[1]["predictive_variances"],
        frozen.records[1]["predictive_variances"],
    )
    for record in full.records:
        expected_cvps = [iterations + 1 for iterations in record["cg_iterations"]]
        assert record["curvature_vector_products_per_action"] == expected_cvps
        assert record["curvature_vector_products"] == sum(expected_cvps)
    assert (
        full.summary["curvature_vector_products"]
        == full.records[-1]["cumulative_curvature_vector_products"]
    )
    last_full = next(run for run in runs if run.method == "last_layer_full")
    last_diagonal = next(run for run in runs if run.method == "last_layer_diagonal")
    np.testing.assert_allclose(
        last_full.records[0]["predictive_variances"],
        last_diagonal.records[0]["predictive_variances"],
        rtol=2e-15,
        atol=2e-15,
    )
    greedy = next(run for run in runs if run.method == "greedy_full_network")
    assert all(max(record["exploration_widths"]) == 0.0 for record in greedy.records)
    assert greedy.summary["curvature_vector_products"] == 0
    assert method_protocol("frozen_full_gram").historical_linearization.startswith(
        "each_observation_frozen"
    )


def test_ucb1_and_independent_beta_thompson_state_transitions() -> None:
    config = _config(rounds=10, all_methods=True)
    data, _ = _prepared(config)
    ucb = run_policy(
        config,
        data,
        "ucb1",
        150,
        phase="evaluation",
        damping=0.0,
        bonus_scale=0.0,
    )
    assert ucb.actions[:7] == tuple(range(7))
    eighth = ucb.records[7]
    np.testing.assert_array_equal(eighth["pull_counts_before"], np.ones(7))
    expected_ucb = np.asarray(eighth["empirical_means_before"]) + np.sqrt(
        2.0 * np.log(8.0)
    )
    np.testing.assert_allclose(eighth["ucb_scores"], expected_ucb)
    assert eighth["action"] == int(np.argmax(expected_ucb))
    assert sum(ucb.summary["pull_counts"]) == 10
    assert sum(ucb.summary["reward_sums"]) == ucb.summary["cumulative_reward"]

    first = run_policy(
        config,
        data,
        "thompson_sampling",
        150,
        phase="evaluation",
        damping=0.0,
        bonus_scale=0.0,
    )
    second = run_policy(
        config,
        data,
        "thompson_sampling",
        150,
        phase="evaluation",
        damping=0.0,
        bonus_scale=0.0,
    )
    assert first.actions == second.actions
    assert first.summary["policy_random_seed"] == second.summary["policy_random_seed"]
    pulls = np.asarray(first.summary["pull_counts"], dtype=np.float64)
    rewards = np.asarray(first.summary["reward_sums"], dtype=np.float64)
    np.testing.assert_allclose(first.summary["posterior_alpha"], 1.0 + rewards)
    np.testing.assert_allclose(first.summary["posterior_beta"], 1.0 + pulls - rewards)
    assert all(record["posterior_independent_across_arms"] for record in first.records)


def test_test_class_diagnostics_are_explicitly_nonpolicy_and_hash_bound(
    tmp_path: Path,
) -> None:
    config = _config(rounds=10, all_methods=True)
    config["horizons"] = [4, 10]
    data, _ = _prepared(config)
    artifact = build_test_class_diagnostics(
        config,
        data,
        clock=lambda: "2026-07-20T00:00:00Z",
    )
    counts = np.bincount(data.labels[data.indices("test")], minlength=7)
    assert artifact["class_counts_by_arm"] == {
        str(arm): int(count) for arm, count in enumerate(counts)
    }
    assert artifact["executed_policy"] is False
    uniform = artifact["diagnostics"]["uniform_random"]
    assert uniform["expected_accuracy"] == pytest.approx(1.0 / 7.0)
    oracle = artifact["diagnostics"]["fixed_test_split_majority_arm_oracle"]
    assert oracle["fixed_arm"] == int(np.argmax(counts))
    assert oracle["deployable"] is False
    assert oracle["uses_test_labels_to_choose_actions"] is True

    output, sidecar = write_test_class_diagnostics(
        artifact, tmp_path / "covertype_test_class_counts.json"
    )
    provenance = json.loads(sidecar.read_text(encoding="utf-8"))
    assert provenance["artifact_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()


def test_phase_specific_tuning_and_evaluation_horizons() -> None:
    config = _config(rounds=5, all_methods=True)
    config["tuning_rounds"] = 2
    config["methods"] = ["ucb1", "thompson_sampling"]
    config["seed_sets"] = {"tuning": [50], "evaluation": [150]}
    data, _ = _prepared(config)
    tuning = run_experiment(config, seed_set="tuning", data=data)
    assert {len(run.records) for run in tuning.runs} == {2}
    assert tuning.tuning_selection is not None
    assert tuning.tuning_selection["tuning_rounds"] == 2
    assert tuning.tuning_selection["evaluation_rounds"] == 5
    evaluation = run_experiment(
        config,
        seed_set="evaluation",
        data=data,
        tuning_selection=tuning.tuning_selection,
    )
    assert {len(run.records) for run in evaluation.runs} == {5}


def test_tuning_artifact_gates_from_scratch_evaluation_and_outputs(tmp_path: Path) -> None:
    config = _config(rounds=3, all_methods=True)
    data, _ = _prepared(config)
    output = tmp_path / "covertype"

    tuning = run_experiment(
        config,
        seed_set="tuning",
        data=data,
        output_root=output,
    )
    assert len(tuning.runs) == len(SUPPORTED_METHODS)
    assert tuning.tuning_selection_path is not None
    artifact = json.loads(tuning.tuning_selection_path.read_text(encoding="utf-8"))
    assert artifact["selected_on_seed_set"] == "tuning"
    assert artifact["selected_on_environment_split"] == "validation"
    assert artifact["evaluation_labels_used"] is False
    assert artifact["test_label_used_for_hyperparameter_selection"] is False
    assert {item["method"] for item in artifact["selected"]} == set(SUPPORTED_METHODS)

    evaluation = run_experiment(
        config,
        seed_set="evaluation",
        data=data,
        output_root=output,
    )
    assert len(evaluation.runs) == len(SUPPORTED_METHODS)
    assert {run.split for run in evaluation.runs} == {"test"}
    assert len({run.dataset_indices for run in evaluation.runs}) == 1
    assert all(run.seed == 150 for run in evaluation.runs)
    aggregate = aggregate_results(output)
    assert {group["method"] for group in aggregate["groups"]} == set(
        SUPPORTED_METHODS
    )
    assert all(
        [item["horizon"] for item in group["horizons"]] == [3]
        for group in aggregate["groups"]
    )

    destination = next(
        path.parent
        for path in output.rglob("manifest.jsonl")
        if "/evaluation/full_network_ggn_cg/" in str(path)
    )
    manifest = json.loads((destination / "manifest.jsonl").read_text(encoding="utf-8"))
    raw = [
        json.loads(line)
        for line in (destination / "raw.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    summary = json.loads((destination / "summary.jsonl").read_text(encoding="utf-8"))
    execution = manifest["config"]["execution"]
    assert execution["executed_policy"] is True
    assert execution["dataset"]["provenance"]["checksum_sha256"]
    assert execution["dataset"]["provenance"]["dataset_version"]
    assert execution["dataset"]["provenance"]["dataset_access_timestamp_utc"]
    for split in ("train", "validation", "test"):
        split_record = execution["dataset"]["split_protocol"]["partitions"][split]
        assert Path(split_record["indices_artifact"]).exists()
        assert split_record["indices_artifact_sha256"]
    assert execution["architecture"]["hidden_width"] == 4
    assert execution["layers_trained"]
    assert execution["curvature"]["likelihood_for_curvature"] == "gaussian_squared_loss"
    assert execution["curvature"]["gaussian_regret_theorem_certified"] is False
    assert execution["optimizer"]["uses_unselected_labels"] is False
    assert execution["solver"]["operator_fixed_within_solve"] is True
    authorization = execution["selection"]["authorization"]
    assert authorization["canonical_json_sha256"]
    assert authorization["artifact_file_sha256"]
    assert authorization["validation_evidence_sha256"]
    assert authorization["validation"]["status"] == "passed"
    assert authorization["validation"]["complete_grid_recomputed"] is True
    assert authorization["validation"]["per_seed_means_recomputed"] is True
    assert authorization["validation"]["tie_break_recomputed"] is True
    assert authorization["artifact"]["selected"] == artifact["selected"]
    assert authorization["canonical_json_sha256"] == hashlib.sha256(
        canonical_json(artifact).encode("ascii")
    ).hexdigest()
    assert authorization["artifact_file_sha256"] == hashlib.sha256(
        tuning.tuning_selection_path.read_bytes()
    ).hexdigest()
    verified = verify_selection_authorization(
        config,
        data,
        authorization,
        require_current_file=True,
    )
    assert set(verified) == set(SUPPORTED_METHODS)
    altered_embedded_artifact = copy.deepcopy(authorization)
    altered_embedded_artifact["artifact"]["created_at_utc"] = "changed"
    with pytest.raises(ValueError, match="embedded tuning-selection artifact hash"):
        verify_selection_authorization(
            config,
            data,
            altered_embedded_artifact,
        )
    altered_embedded_evidence = copy.deepcopy(authorization)
    altered_embedded_evidence["validation_evidence"]["tuning_seeds"] = []
    with pytest.raises(ValueError, match="validation evidence does not match"):
        verify_selection_authorization(
            config,
            data,
            altered_embedded_evidence,
        )
    assert manifest["hardware"]
    assert manifest["package_versions"]["numpy"]
    assert len(raw) == 3
    assert summary["environment_split"] == "test"
    assert (
        summary["tuning_selection_canonical_json_sha256"]
        == authorization["canonical_json_sha256"]
    )
    assert (
        summary["tuning_selection_validation_evidence_sha256"]
        == authorization["validation_evidence_sha256"]
    )
    assert summary["tuning_selection_validation_status"] == "passed"

    ucb_destination = next(
        path.parent
        for path in output.rglob("manifest.jsonl")
        if "/evaluation/ucb1/" in str(path)
    )
    ucb_manifest = json.loads(
        (ucb_destination / "manifest.jsonl").read_text(encoding="utf-8")
    )["config"]["execution"]
    assert ucb_manifest["mode"] == "online_adaptive_noncontextual"
    assert ucb_manifest["architecture"]["kind"] == "none_noncontextual_bandit"
    assert ucb_manifest["curvature"]["applies"] is False
    assert ucb_manifest["optimizer"]["uses_unselected_labels"] is False
    assert ucb_manifest["selection"]["parameter_free_policy"] is True


def test_pooled_grid_selection_is_recomputed_and_bound_before_evaluation(
    tmp_path: Path,
) -> None:
    config = _config(rounds=2)
    config["methods"] = ["full_network_ggn_cg", "diagonal_full_network"]
    config["damping_grid"] = [1.0, 10.0]
    config["bonus_grid"] = [1.0, 2.0]
    config["seed_sets"] = {"tuning": [50, 51], "evaluation": [150]}
    data, _ = _prepared(config)

    tuning = run_experiment(config, seed_set="tuning", data=data)
    assert len(tuning.runs) == 2 * 2 * 2 * 2
    assert tuning.tuning_selection is not None
    artifact = tuning.tuning_selection
    assert len(artifact["candidates"]) == 2 * 2 * 2
    for candidate in artifact["candidates"]:
        assert set(candidate["per_seed_cumulative_pseudo_regret"]) == {"50", "51"}
    for selected in artifact["selected"]:
        candidates = [
            item for item in artifact["candidates"] if item["method"] == selected["method"]
        ]
        winner = min(
            candidates,
            key=lambda item: (
                item["mean_cumulative_pseudo_regret"],
                item["grid_order"],
            ),
        )
        assert selected["damping"] == winner["damping"]
        assert selected["bonus_scale"] == winner["bonus_scale"]

    artifact_path = write_tuning_selection(
        artifact, tmp_path / "selection.json"
    )
    evaluation_root = tmp_path / "evaluation"
    evaluation = run_experiment(
        config,
        seed_set="evaluation",
        data=data,
        tuning_selection=artifact_path,
        output_root=evaluation_root,
    )
    assert len(evaluation.runs) == 2
    manifest_path = next(evaluation_root.rglob("manifest.jsonl"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    original_authorization = manifest["config"]["execution"]["selection"][
        "authorization"
    ]
    verify_selection_authorization(
        config,
        data,
        original_authorization,
        require_current_file=True,
    )

    tampered = copy.deepcopy(artifact)
    first = tampered["selected"][0]
    alternative = next(
        item
        for item in tampered["candidates"]
        if item["method"] == first["method"]
        and (item["damping"], item["bonus_scale"])
        != (first["damping"], first["bonus_scale"])
    )
    first["damping"] = alternative["damping"]
    first["bonus_scale"] = alternative["bonus_scale"]
    with pytest.raises(ValueError, match="not the tuning argmin"):
        run_experiment(
            config,
            seed_set="evaluation",
            data=data,
            tuning_selection=tampered,
        )

    # Change the evidence as well as the selected row so the altered artifact
    # remains internally valid.  It must still fail the original evaluation
    # manifest's cryptographic commitment.
    coherently_altered = copy.deepcopy(artifact)
    selected = coherently_altered["selected"][0]
    alternative = next(
        item
        for item in coherently_altered["candidates"]
        if item["method"] == selected["method"]
        and (item["damping"], item["bonus_scale"])
        != (selected["damping"], selected["bonus_scale"])
    )
    for candidate in coherently_altered["candidates"]:
        if candidate["method"] != selected["method"]:
            continue
        regret = 0.0 if candidate is alternative else float(config["rounds"])
        candidate["per_seed_cumulative_pseudo_regret"] = {
            seed: regret
            for seed in candidate["per_seed_cumulative_pseudo_regret"]
        }
        candidate["mean_cumulative_pseudo_regret"] = regret
    selected["damping"] = alternative["damping"]
    selected["bonus_scale"] = alternative["bonus_scale"]
    selected["mean_tuning_cumulative_pseudo_regret"] = 0.0
    selected["tie_break_grid_order"] = alternative["grid_order"]
    artifact_path.write_text(
        canonical_json(coherently_altered) + "\n", encoding="utf-8"
    )
    altered_digest = hashlib.sha256(
        canonical_json(coherently_altered).encode("ascii")
    ).hexdigest()
    assert altered_digest != original_authorization["canonical_json_sha256"]
    altered_evaluation = run_experiment(
        config,
        seed_set="evaluation",
        data=data,
        methods=[selected["method"]],
        tuning_selection=artifact_path,
    )
    assert len(altered_evaluation.runs) == 1
    with pytest.raises(ValueError, match="current tuning-selection artifact"):
        verify_selection_authorization(
            config,
            data,
            original_authorization,
            require_current_file=True,
        )


def test_evaluation_rejects_missing_or_test_selected_artifact() -> None:
    config = _config(rounds=1)
    data, _ = _prepared(config)
    with pytest.raises(ValueError, match="requires a tuning-selection artifact"):
        run_experiment(config, seed_set="evaluation", data=data)

    tuning = run_experiment(config, seed_set="tuning", data=data)
    assert tuning.tuning_selection is not None
    invalid = dict(tuning.tuning_selection)
    invalid["selected_on_environment_split"] = "test"
    with pytest.raises(ValueError, match="test labels"):
        run_experiment(
            config,
            seed_set="evaluation",
            data=data,
            tuning_selection=invalid,
        )
