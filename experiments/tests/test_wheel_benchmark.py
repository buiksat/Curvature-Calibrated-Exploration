from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.aggregate_results import validate_aggregate_provenance_sidecar
from experiments.artifact_utils import (
    sha256_file,
    validate_sha256_sidecar,
)
from experiments.config import get_seed_set, load_config
from experiments.make_wheel_benchmark_artifacts import build_artifact, write_artifacts
from experiments.run_wheel_benchmark import (
    CONTROL_METHODS,
    METHODS,
    WheelRun,
    _control_action,
    _execute_tasks,
    build_tuning_selection,
    cells,
    run_experiment,
    run_policy,
    validate_tuning_selection,
    validate_wheel_config,
)
from experiments.wheel_environment import (
    ACTION_COUNT,
    PostActionWheelOracle,
    QUADRANT_TO_ACTION,
    SAFE_ACTION,
    WheelSpecification,
    generate_wheel_stream,
)


CONFIG = Path("experiments/configs/wheel_benchmark.yaml")


def _smoke_config() -> dict[str, object]:
    return load_config(CONFIG, profile="smoke")


def test_wheel_config_is_canonical_disjoint_and_honest_about_implementations() -> None:
    smoke = _smoke_config()
    full = load_config(CONFIG, profile="full")
    validate_wheel_config(smoke)
    assert tuple(smoke["methods"]) == METHODS
    assert [cell.delta for cell in cells(smoke)] == [0.5, 0.7, 0.9, 0.95]
    assert CONTROL_METHODS == {"random", "safe", "oracle"}
    assert "lofi" not in smoke["methods"]
    assert "kfac" not in smoke["methods"]
    assert "faithful pinned" in smoke["omitted_methods"]["lofi"]
    assert "not a pinned or faithful" in smoke["method_semantics"]["local_neural_ucb"]
    assert set(get_seed_set(smoke, "tuning")).isdisjoint(
        get_seed_set(smoke, "evaluation")
    )
    assert full["rounds"] == 5000
    assert full["tuning_rounds"] == 5000
    assert get_seed_set(full, "tuning") == tuple(range(2000, 2010))
    assert get_seed_set(full, "evaluation") == tuple(range(3000, 3030))
    assert full["cg"]["relative_residual_tolerance"] == pytest.approx(1.0e-6)
    assert full["cg"]["solver"].startswith("batched_independent_cg")
    assert set(get_seed_set(full, "tuning")).isdisjoint(
        get_seed_set(full, "evaluation")
    )


def test_unit_disk_stream_is_pcg64_deterministic_and_uniform_by_area() -> None:
    first = generate_wheel_stream(1234, 200_000)
    second = generate_wheel_stream(1234, 200_000)
    other = generate_wheel_stream(1235, 200_000)
    np.testing.assert_array_equal(first.contexts, second.contexts)
    np.testing.assert_array_equal(first.standard_normals, second.standard_normals)
    assert first.stream_sha256 == second.stream_sha256
    assert first.stream_sha256 != other.stream_sha256

    squared_radii = np.einsum("ij,ij->i", first.contexts, first.contexts)
    assert np.max(squared_radii) <= 1.0 + 1.0e-14
    assert float(np.mean(squared_radii)) == pytest.approx(0.5, abs=0.003)
    for delta in (0.5, 0.7, 0.9, 0.95):
        assert float(np.mean(squared_radii <= delta * delta)) == pytest.approx(
            delta * delta, abs=0.003
        )
    x = first.contexts[:, 0]
    y = first.contexts[:, 1]
    quadrant_frequencies = np.asarray(
        [
            np.mean((x >= 0.0) & (y >= 0.0)),
            np.mean((x < 0.0) & (y >= 0.0)),
            np.mean((x < 0.0) & (y < 0.0)),
            np.mean((x >= 0.0) & (y < 0.0)),
        ]
    )
    np.testing.assert_allclose(quadrant_frequencies, 0.25, atol=0.004)


def test_quadrant_map_threshold_oracle_means_and_regret_are_exact() -> None:
    spec = WheelSpecification()
    assert spec.quadrant_action([0.5, 0.5]) == QUADRANT_TO_ACTION["northeast"]
    assert spec.quadrant_action([-0.5, 0.5]) == QUADRANT_TO_ACTION["northwest"]
    assert spec.quadrant_action([-0.5, -0.5]) == QUADRANT_TO_ACTION["southwest"]
    assert spec.quadrant_action([0.5, -0.5]) == QUADRANT_TO_ACTION["southeast"]
    assert spec.quadrant_action([0.0, 0.0]) == QUADRANT_TO_ACTION["northeast"]
    assert spec.quadrant_action([-0.5, 0.0]) == QUADRANT_TO_ACTION["northwest"]

    inner = np.asarray([spec.delta, 0.0])
    np.testing.assert_array_equal(
        spec.mean_rewards(inner), [1.2, 1.0, 1.0, 1.0, 1.0]
    )
    assert spec.optimal_action(inner) == SAFE_ACTION
    assert spec.pseudo_regret(inner, SAFE_ACTION) == 0.0
    assert spec.pseudo_regret(inner, 1) == pytest.approx(0.2)

    outer_contexts = (
        (np.asarray([0.8, 0.6]), 1),
        (np.asarray([-0.8, 0.6]), 2),
        (np.asarray([-0.8, -0.6]), 3),
        (np.asarray([0.8, -0.6]), 4),
    )
    for context, optimal in outer_contexts:
        means = spec.mean_rewards(context)
        assert means[optimal] == 50.0
        assert means[SAFE_ACTION] == 1.2
        assert spec.optimal_action(context) == optimal
        assert spec.pseudo_regret(context, optimal) == 0.0
        assert spec.pseudo_regret(context, SAFE_ACTION) == pytest.approx(48.8)
        wrong_risky = next(action for action in range(1, ACTION_COUNT) if action != optimal)
        assert spec.pseudo_regret(context, wrong_risky) == pytest.approx(49.0)
        assert spec.reward_stds(context)[optimal] == 0.01


def test_random_safe_oracle_control_regrets_and_access_labels() -> None:
    spec = WheelSpecification(delta=0.95)
    expected_safe = (1.0 - 0.95**2) * (50.0 - 1.2)
    expected_random = 0.95**2 * (4.0 * 0.2 / 5.0) + (1.0 - 0.95**2) * (
        (50.0 - 1.2 + 3.0 * (50.0 - 1.0)) / 5.0
    )
    assert spec.expected_control_regret("oracle") == 0.0
    assert spec.expected_control_regret("safe") == pytest.approx(expected_safe)
    assert spec.expected_control_regret("random") == pytest.approx(expected_random)
    assert {
        name for name in dir(PostActionWheelOracle) if not name.startswith("_")
    } == {"observe_after_action"}

    class NoOracleAccess:
        def optimal_action(self, context: np.ndarray) -> int:
            raise AssertionError("oracle access is forbidden for this control")

    rng = np.random.Generator(np.random.PCG64(7))
    random_actions = [
        _control_action("random", np.asarray([np.nan, np.nan]), rng, NoOracleAccess())
        for _ in range(50_000)
    ]
    frequencies = np.bincount(random_actions, minlength=ACTION_COUNT) / 50_000.0
    np.testing.assert_allclose(frequencies, 1.0 / ACTION_COUNT, atol=0.006)
    assert (
        _control_action(
            "safe", np.asarray([np.nan, np.nan]), rng, NoOracleAccess()
        )
        == SAFE_ACTION
    )

    config = _smoke_config()
    cell = cells(config)[-1]
    oracle = run_policy(
        config,
        "oracle",
        3000,
        cell=cell,
        phase="evaluation",
        ridge=0.0,
        bonus_scale=0.0,
    )
    safe = run_policy(
        config,
        "safe",
        3000,
        cell=cell,
        phase="evaluation",
        ridge=0.0,
        bonus_scale=0.0,
    )
    random_first = run_policy(
        config,
        "random",
        3000,
        cell=cell,
        phase="evaluation",
        ridge=0.0,
        bonus_scale=0.0,
    )
    random_second = run_policy(
        config,
        "random",
        3000,
        cell=cell,
        phase="evaluation",
        ridge=0.0,
        bonus_scale=0.0,
    )
    assert oracle.summary["cumulative_pseudo_regret"] == 0.0
    assert oracle.summary["uses_privileged_pre_action_oracle"] is True
    assert all(row["selected_action"] == row["optimal_action_posthoc"] for row in oracle.records)
    assert all(row["selected_action"] == SAFE_ACTION for row in safe.records)
    assert safe.summary["uses_privileged_pre_action_oracle"] is False
    assert random_first.deterministic_signature() == random_second.deterministic_signature()
    assert random_first.summary["uses_privileged_pre_action_oracle"] is False
    assert all(row["oracle_information_used_for_selection"] is False for row in random_first.records)
    source = inspect.getsource(PostActionWheelOracle)
    assert "observe_after_action" in source


def test_selection_rejects_evaluation_leakage_and_requires_tuning_artifact(
    tmp_path: Path,
) -> None:
    config = _smoke_config()
    config["tuning_rounds"] = 4
    tuning_runs = [
        run_policy(
            config,
            method,
            seed,
            cell=cell,
            phase="tuning",
            ridge=0.0 if method in CONTROL_METHODS else 1.0,
            bonus_scale=0.0 if method in CONTROL_METHODS else 0.5,
        )
        for method in METHODS
        for cell in cells(config)
        for seed in get_seed_set(config, "tuning")
    ]
    selection = build_tuning_selection(config, tuning_runs)
    assert set(validate_tuning_selection(config, selection)) == set(METHODS)
    leaked = copy.deepcopy(selection)
    leaked["evaluation_outcomes_used"] = True
    with pytest.raises(ValueError, match="evaluation_outcomes_used"):
        validate_tuning_selection(config, leaked)
    incomplete = copy.deepcopy(selection)
    incomplete["candidates"][0]["per_cell_cumulative_pseudo_regret"].pop()
    with pytest.raises(ValueError, match="pooled cell coverage"):
        validate_tuning_selection(config, incomplete)
    with pytest.raises(ValueError, match="requires a tuning-selection artifact"):
        run_experiment(
            config,
            seed_set="evaluation",
            output_root=tmp_path,
            tuning_selection=None,
        )


def test_tuning_selection_uses_one_pooled_argmin_across_all_deltas() -> None:
    config = _smoke_config()
    config["ridge_grid"] = [1.0, 2.0]
    runs: list[WheelRun] = []
    for method in METHODS:
        settings = ((0.0, 0.0),) if method in CONTROL_METHODS else (
            (1.0, 0.5),
            (2.0, 0.5),
        )
        for ridge, bonus in settings:
            for cell_index, cell in enumerate(cells(config)):
                if method in CONTROL_METHODS:
                    regret = 0.0
                elif ridge == 1.0:
                    regret = 0.0 if cell_index < 2 else 100.0
                else:
                    regret = 40.0
                for seed in get_seed_set(config, "tuning"):
                    runs.append(
                        WheelRun(
                            method=method,
                            cell=cell,
                            seed=seed,
                            phase="tuning",
                            ridge=ridge,
                            bonus_scale=bonus,
                            records=(),
                            summary={"cumulative_pseudo_regret": regret},
                        )
                    )
    artifact = build_tuning_selection(config, runs)
    selected = validate_tuning_selection(config, artifact)
    for method in set(METHODS) - CONTROL_METHODS:
        assert selected[method] == (2.0, 0.5)
    first = next(
        row
        for row in artifact["candidates"]
        if row["method"] == "linucb" and row["ridge"] == 1.0
    )
    assert [row["mean_cumulative_pseudo_regret"] for row in first["per_delta_means"]] == [
        0.0,
        0.0,
        100.0,
        100.0,
    ]
    assert first["pooled_mean_cumulative_pseudo_regret"] == 50.0


def test_workers_two_matches_serial_pooled_selection_and_surfaces_errors(
    tmp_path: Path,
) -> None:
    config = _smoke_config()
    config["tuning_rounds"] = 4
    serial_selection = tmp_path / "serial" / "smoke" / "selection.json"
    parallel_selection = tmp_path / "parallel" / "smoke" / "selection.json"
    serial = run_experiment(
        config,
        seed_set="tuning",
        output_root=tmp_path / "serial",
        tuning_selection=serial_selection,
        workers=1,
    )
    parallel = run_experiment(
        config,
        seed_set="tuning",
        output_root=tmp_path / "parallel",
        tuning_selection=parallel_selection,
        workers=2,
    )
    direct = run_policy(
        config,
        serial[0].method,
        serial[0].seed,
        cell=serial[0].cell,
        phase=serial[0].phase,
        ridge=serial[0].ridge,
        bonus_scale=serial[0].bonus_scale,
    )

    def deterministic_summary(run: WheelRun) -> dict[str, object]:
        return {
            key: value
            for key, value in run.summary.items()
            if not key.endswith(("_seconds", "_bytes"))
        }

    assert all(run.records == () for run in serial)
    assert all(run.records == () for run in parallel)
    assert deterministic_summary(direct) == deterministic_summary(serial[0])
    assert deterministic_summary(direct) == deterministic_summary(parallel[0])
    assert serial_selection.read_bytes() == parallel_selection.read_bytes()
    assert [
        (
            run.cell.delta,
            run.method,
            run.seed,
            run.ridge,
            run.bonus_scale,
            run.summary["cumulative_pseudo_regret"],
            run.summary["environment_stream_sha256"],
        )
        for run in serial
    ] == [
        (
            run.cell.delta,
            run.method,
            run.seed,
            run.ridge,
            run.bonus_scale,
            run.summary["cumulative_pseudo_regret"],
            run.summary["environment_stream_sha256"],
        )
        for run in parallel
    ]

    bad_task = (
        config,
        "not_a_wheel_method",
        2000,
        cells(config)[0],
        "tuning",
        1.0,
        0.5,
        (tmp_path / "bad-worker-run").as_posix(),
        False,
    )
    with pytest.raises(RuntimeError, match="method=not_a_wheel_method"):
        _execute_tasks([bad_task], workers=2)
    failure_path = tmp_path / "bad-worker-run" / "failure.json"
    validate_sha256_sidecar(failure_path)
    failure = json.loads(failure_path.read_text(encoding="ascii"))
    assert failure["event"] == "wheel_policy_run_failed"
    assert failure["seed"] == 2000
    assert failure["phase"] == "tuning"
    assert failure["method"] == "not_a_wheel_method"
    assert failure["cell"] == {"delta": 0.5, "token": "delta-0p5"}
    assert failure["hyperparameters"] == {"ridge": 1.0, "bonus_scale": 0.5}
    assert failure["error_type"] == "ValueError"
    assert failure["error_message"] == "unknown method 'not_a_wheel_method'"
    assert failure["provenance"]["git_revision"]


def test_complete_smoke_pipeline_builds_provenance_bound_artifact(
    tmp_path: Path,
) -> None:
    config = _smoke_config()
    selection_path = tmp_path / "smoke" / "tuning_selection.json"
    tuning = run_experiment(
        config,
        seed_set="tuning",
        output_root=tmp_path,
        tuning_selection=selection_path,
        workers=2,
    )
    expected_tuning = (
        len(cells(config)) * len(METHODS) * len(get_seed_set(config, "tuning"))
    )
    assert len(tuning) == expected_tuning
    selection = validate_tuning_selection(
        config,
        json.loads(selection_path.read_text(encoding="ascii")),
    )
    assert set(selection) == set(METHODS)
    evaluation = run_experiment(
        config,
        seed_set="evaluation",
        output_root=tmp_path,
        tuning_selection=selection_path,
        workers=2,
    )
    expected_evaluation = (
        len(cells(config))
        * len(METHODS)
        * len(get_seed_set(config, "evaluation"))
    )
    assert len(evaluation) == expected_evaluation
    for seed in get_seed_set(config, "evaluation"):
        assert len(
            {
                run.summary["environment_stream_sha256"]
                for run in evaluation
                if run.seed == seed
            }
        ) == 1

    artifact = build_artifact(
        config_path=CONFIG,
        raw_root=tmp_path / "smoke" / "evaluation",
        selection_path=selection_path,
        profile="smoke",
    )
    assert set(artifact["method_results"]) == set(METHODS)
    assert artifact["evaluation_outcomes_used_for_tuning"] is False
    assert artifact["control_invariants"] == {
        "oracle_zero_regret": True,
        "oracle_is_privileged_nonlearner": True,
        "safe_always_action_zero": True,
        "random_is_context_and_oracle_independent": True,
        "analytic_expected_one_round_pseudo_regret_by_delta": [
            {
                "delta": cell.delta,
                **{
                    method: WheelSpecification.from_mapping(
                        {**config["environment"], "delta": cell.delta}
                    ).expected_control_regret(method)
                    for method in ("random", "safe", "oracle")
                },
            }
            for cell in cells(config)
        ],
    }
    assert artifact["method_results"]["cc_ucb_full_ggn_cg"][
        "all_cg_solves_converged"
    ] is True
    assert "lofi" in artifact["omitted_methods"]
    assert artifact["pooled_tuning_over_all_deltas"] is True
    assert artifact["delta_count"] == 4
    assert len(artifact["method_results"]["linucb"]["by_delta"]) == 4
    assert len(artifact["seed_level_results"]) == expected_evaluation
    assert len(artifact["paired_comparisons_against_controls"]) == 4 * 3 * 7
    assert artifact["interval"]["unit"] == (
        "one complete evaluation-seed trajectory"
    )
    for method, result in artifact["method_results"].items():
        for row in result["by_delta"]:
            metrics = row["metrics"]
            assert "outside_optimal_risky_rate" in metrics
            assert metrics["inside_safe_action_rate"] is not None
            if method in CONTROL_METHODS:
                assert metrics["empirical_all_action_coverage"] is None
            else:
                assert metrics["empirical_all_action_coverage"]["n"] == len(
                    get_seed_set(config, "evaluation")
                )

    derived = tmp_path / "derived"
    output = derived / "wheel.json"
    quality = derived / "wheel_quality.pdf"
    compute = derived / "wheel_compute.pdf"
    table = derived / "wheel_summary.tex"
    result = write_artifacts(
        artifact,
        aggregate_path=output,
        regret_figure_path=quality,
        compute_figure_path=compute,
        table_path=table,
    )
    sidecar = Path(result["aggregate_provenance"])
    provenance = validate_aggregate_provenance_sidecar(output, sidecar)
    assert provenance["input_set_sha256"] == artifact["input_set_sha256"]
    for path in (output, sidecar, quality, compute, table):
        validate_sha256_sidecar(path)
    for path in (quality, compute, table):
        publication_provenance = path.with_name(path.name + ".provenance.json")
        validate_sha256_sidecar(publication_provenance)
        record = json.loads(publication_provenance.read_text(encoding="ascii"))
        assert record["artifact_sha256"] == sha256_file(path)
        assert record["profile"] == "smoke"
        assert record["generation_parameters"]["interval"] == artifact["interval"]
    assert b"/FontFile2" in quality.read_bytes()
    assert b"/FontFile2" in compute.read_bytes()
    table_text = table.read_text(encoding="ascii")
    assert "Smoke verification only; not main-paper evidence" in table_text
    assert "Outer opt." in table_text
    assert "All-act. cov." in table_text
