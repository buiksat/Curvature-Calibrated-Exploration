from __future__ import annotations

import json

import numpy as np
import pytest

from experiments.linear_environment import (
    ACTION_COUNT,
    CONTEXT_DIMENSION,
    FEATURE_DIMENSION,
    LinearBanditEnvironment,
    enumerate_rademacher_contexts,
    linear_feature,
)
from experiments.run_linear_audit import (
    DEFAULT_CONFIG,
    SUPPORTED_METHODS,
    run_method,
    save_run,
    selected_seeds,
)


def _short_config(rounds: int = 8) -> dict[str, object]:
    return {
        **DEFAULT_CONFIG,
        "rounds": rounds,
        "curvature": {
            "window_size": 3,
            "subsample_size": 3,
            "lanczos_rank": 4,
            "refresh_period": 3,
        },
        "cg": {"tolerance": 0.05, "max_iterations": 2 * FEATURE_DIMENSION},
    }


def test_feature_map_is_float64_bounded_and_context_dependent() -> None:
    environment = LinearBanditEnvironment(11)
    context = environment.draw_context()
    feature = linear_feature(context, 3)

    assert context.dtype == np.float64
    assert feature.dtype == np.float64
    assert feature.shape == (FEATURE_DIMENSION,)
    assert np.linalg.norm(context) == pytest.approx(1.0)
    assert np.linalg.norm(feature) == pytest.approx(np.sqrt(3.0))
    np.testing.assert_array_equal(feature[:CONTEXT_DIMENSION], context)
    np.testing.assert_array_equal(
        feature[CONTEXT_DIMENSION : CONTEXT_DIMENSION + ACTION_COUNT],
        np.eye(ACTION_COUNT, dtype=np.float64)[3],
    )
    np.testing.assert_array_equal(
        feature[CONTEXT_DIMENSION + ACTION_COUNT :],
        np.kron(context, np.eye(ACTION_COUNT, dtype=np.float64)[3]),
    )

    optimal_actions = {
        environment.optimal_action(candidate)
        for candidate in enumerate_rademacher_contexts()
    }
    assert optimal_actions == set(range(ACTION_COUNT))


def test_linear_certificates_vanish_and_c_equals_cbar() -> None:
    run = run_method(_short_config(6), "dense_full", 23)

    assert run.summary["E_T"] == 0.0
    assert run.summary["F_T"] == 0.0
    assert run.summary["psi_max"] == 0.0
    assert run.summary["chi_max"] == 0.0
    assert run.summary["C_equals_Cbar_all_rounds"] is True
    assert run.summary["S_T"] > 0.0
    assert run.summary["theorem_bound_slack"] >= -1e-10
    assert run.summary["certified_execution"] is True
    for record, matrices in zip(run.rounds, run.matrices, strict=True):
        assert record["E_t"] == 0.0
        assert record["F_t"] == 0.0
        assert record["psi_t"] == 0.0
        assert record["bar_psi_t"] == 0.0
        assert record["chi_t"] == 0.0
        assert record["bar_chi_t"] == 0.0
        assert record["C_equals_Cbar"] is True
        np.testing.assert_array_equal(matrices.C_t, matrices.C_bar_t)


def test_seed_reproducibility_and_disjoint_seed_sets() -> None:
    config = _short_config(9)
    first = run_method(config, "rescaled_subsample", 31)
    second = run_method(config, "rescaled_subsample", 31)
    different = run_method(config, "rescaled_subsample", 32)

    nondeterministic = {
        "round_runtime_seconds",
        "runtime_seconds",
        "peak_host_memory_bytes",
    }
    first_deterministic = [
        {key: value for key, value in record.items() if key not in nondeterministic}
        for record in first.rounds
    ]
    second_deterministic = [
        {key: value for key, value in record.items() if key not in nondeterministic}
        for record in second.rounds
    ]
    assert first_deterministic == second_deterministic
    assert first.actions == second.actions
    np.testing.assert_array_equal(first.contexts, second.contexts)
    for left, right in zip(first.matrices, second.matrices, strict=True):
        np.testing.assert_array_equal(left.algorithmic, right.algorithmic)
    assert not np.array_equal(first.contexts, different.contexts)

    split_config = {"tuning_seeds": [1, 2], "evaluation_seeds": [101, 102]}
    assert selected_seeds(split_config, "tuning") == (1, 2)
    assert selected_seeds(split_config, "evaluation") == (101, 102)
    with pytest.raises(ValueError, match="disjoint"):
        selected_seeds(
            {"tuning_seeds": [1, 2], "evaluation_seeds": [2, 3]}, "evaluation"
        )


@pytest.mark.parametrize("method", SUPPORTED_METHODS)
def test_short_run_dynamic_identity_bounds_and_sandwiches(method: str) -> None:
    config = _short_config(8)
    run = run_method(config, method, 47)
    tolerance = 2e-8

    assert abs(run.summary["dynamic_identity_residual"]) <= tolerance
    assert run.summary["dynamic_bound_slack"] >= -tolerance
    assert run.summary["width_information_slack"] >= -tolerance
    assert run.summary["width_dynamic_slack"] >= -tolerance
    assert run.summary["transfer_slack_min"] >= -tolerance
    assert run.summary["bonus_lower_slack_min"] >= -tolerance
    assert run.summary["bonus_upper_slack_min"] >= -tolerance
    assert run.summary["cg_sandwich_lower_slack_min"] >= -tolerance
    assert run.summary["cg_sandwich_upper_slack_min"] >= -tolerance
    assert run.summary["shared_theory_metrics_used"] is True
    assert abs(run.summary["shared_dynamic_identity_residual"]) <= tolerance
    assert run.summary["theorem_rhs"] >= run.summary["cumulative_pseudo_regret"] - tolerance
    assert 0.0 <= run.summary["all_action_optimism_violation_rate"] <= 1.0
    assert 0.0 <= run.summary["selected_action_optimism_violation_rate"] <= 1.0
    assert run.summary["runtime_seconds"] >= 0.0

    for record, matrices in zip(run.rounds, run.matrices, strict=True):
        assert abs(record["dynamic_identity_residual"]) <= tolerance
        assert record["dynamic_bound_slack"] >= -tolerance
        assert record["width_information_slack"] >= -tolerance
        assert record["width_dynamic_slack"] >= -tolerance
        assert record["transfer_slack_min"] >= -tolerance
        assert record["bonus_lower_slack_min"] >= -tolerance
        assert record["bonus_upper_slack_min"] >= -tolerance
        assert record["cg_sandwich_lower_slack_min"] >= -tolerance
        assert record["cg_sandwich_upper_slack_min"] >= -tolerance
        assert record["u_t"] >= 1.0
        assert record["kappa_bar_t"] >= record["kappa_t"] * (1.0 - tolerance)
        assert record["theorem_rhs"] >= record["cumulative_pseudo_regret"] - tolerance
        assert record["xi_min_eigenvalue"] > -1.0
        assert np.linalg.eigvalsh(matrices.algorithmic)[0] > 0.0
        assert np.linalg.eigvalsh(
            np.eye(FEATURE_DIMENSION) + matrices.normalized_perturbation
        )[0] > 0.0

        rho_min = float(record["rho_minus"])
        rho_max = float(record["rho_plus"])
        lower = matrices.algorithmic - rho_min * matrices.reference
        upper = rho_max * matrices.reference - matrices.algorithmic
        assert np.linalg.eigvalsh(0.5 * (lower + lower.T))[0] >= -tolerance
        assert np.linalg.eigvalsh(0.5 * (upper + upper.T))[0] >= -tolerance

        if method == "unrescaled_window":
            difference = matrices.reference - matrices.algorithmic
            assert np.linalg.eigvalsh(0.5 * (difference + difference.T))[0] >= -tolerance
            assert record["kappa_plus"] == 1.0


def test_save_run_uses_jsonl_logging(tmp_path) -> None:
    config = _short_config(2)
    run = run_method(config, "dense_full", 5, retain_matrices=False)
    destination = save_run(run, tmp_path / "run", config, overwrite=True)

    assert (destination / "manifest.jsonl").is_file()
    raw_records = [
        json.loads(line)
        for line in (destination / "raw.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(raw_records) == 2
    assert [record["round"] for record in raw_records] == [0, 1]
    assert all(record["metrics"]["executed_policy"] for record in raw_records)
    summary = json.loads(
        (destination / "summary.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert summary["method"] == "dense_full"
    assert summary["executed_policy"] is True
