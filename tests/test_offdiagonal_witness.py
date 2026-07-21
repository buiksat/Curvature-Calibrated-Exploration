from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from experiments.config import load_config
from experiments.make_offdiagonal_witness_artifact import build_artifact
from experiments.offdiagonal_witness import (
    WitnessProblem,
    full_first_hit_count,
    one_pull_witness_interval,
    run_witness_policy,
    uniform_diagonal_transfer_factor,
)
from experiments.run_offdiagonal_witness import execute


def test_default_witness_interval_and_first_hit() -> None:
    problem = WitnessProblem()
    interval = one_pull_witness_interval(problem)
    assert interval.nonempty
    assert problem.bonus >= interval.confidence_lower
    assert problem.bonus > interval.immediate_switch_lower
    assert problem.bonus <= interval.no_return_upper
    assert full_first_hit_count(problem) == 1


def test_deterministic_full_and_diagonal_trajectories() -> None:
    problem = WitnessProblem()
    full = run_witness_policy(problem, policy="exact_full", rounds=100, seed=0)
    cg = run_witness_policy(problem, policy="full_cg", rounds=100, seed=0)
    diagonal = run_witness_policy(problem, policy="diagonal_raw", rounds=100, seed=0)
    transferred = run_witness_policy(
        problem, policy="diagonal_uniform_transfer", rounds=100, seed=0
    )

    np.testing.assert_array_equal(full.actions[:5], [0, 1, 1, 1, 1])
    np.testing.assert_array_equal(cg.actions, full.actions)
    assert full.cumulative_regret[-1] == pytest.approx(problem.gap)
    assert cg.cumulative_regret[-1] == pytest.approx(problem.gap)
    np.testing.assert_array_equal(diagonal.actions, np.zeros(100, dtype=np.int64))
    np.testing.assert_array_equal(transferred.actions, diagonal.actions)
    assert diagonal.cumulative_regret[-1] == pytest.approx(100 * problem.gap)
    assert transferred.cumulative_regret[-1] == pytest.approx(100 * problem.gap)


def test_actionwise_dense_reference_recovers_full_path() -> None:
    problem = WitnessProblem()
    full = run_witness_policy(problem, policy="exact_full", rounds=30, seed=4)
    reference = run_witness_policy(
        problem,
        policy="diagonal_actionwise_reference",
        rounds=30,
        seed=4,
    )
    np.testing.assert_array_equal(reference.actions, full.actions)
    np.testing.assert_allclose(reference.cumulative_regret, full.cumulative_regret)


def test_uniform_transfer_is_analytic_and_positive_semidefinite() -> None:
    problem = WitnessProblem()
    u = problem.actions[0]
    for count in (0, 1, 2, 20, 100):
        full = problem.damping * np.eye(2) + count * np.outer(u, u)
        diagonal = np.diag(np.diag(full))
        factor = uniform_diagonal_transfer_factor(
            full, diagonal, damping=problem.damping
        )
        expected = (problem.damping + count / 2.0) / problem.damping
        assert factor == pytest.approx(expected)
        assert np.min(np.linalg.eigvalsh(factor * full - diagonal)) >= -1e-12


def test_first_hit_formula_matches_direct_strict_inequality() -> None:
    for bonus in (0.11, 0.15, 0.3, 1.1):
        problem = WitnessProblem(bonus=bonus)
        predicted = full_first_hit_count(problem)
        if predicted is None:
            pytest.fail("all selected bonuses exceed epsilon sqrt(lambda)")
        for count in range(1, predicted):
            left = count * problem.epsilon / (problem.damping + count)
            left += bonus / np.sqrt(problem.damping + count)
            right = bonus / np.sqrt(problem.damping)
            assert left >= right
        count = predicted
        left = count * problem.epsilon / (problem.damping + count)
        left += bonus / np.sqrt(problem.damping + count)
        right = bonus / np.sqrt(problem.damping)
        assert left < right


def test_smoke_execution_and_aggregation_are_raw_driven(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "experiments" / "configs" / "offdiagonal_witness.yaml"
    document = json.loads(source.read_text(encoding="utf-8"))
    document["base"]["rounds"] = 100
    document["base"]["checkpoints"] = [10, 100]
    document["base"]["cells"] = [document["base"]["cells"][0]]
    document["profiles"]["full"] = {
        "seed_sets": {
            "development": [0],
            "tuning": [100],
            "evaluation": [1000],
        }
    }
    config_path = tmp_path / "witness.yaml"
    config_path.write_text(json.dumps(document), encoding="utf-8")
    config = load_config(config_path, profile="full")
    raw_root = tmp_path / "raw"
    outputs = execute(
        config,
        seed_set="evaluation",
        output_root=raw_root,
    )
    assert len(outputs) == 6

    artifact = build_artifact(
        config_path=config_path,
        raw_root=raw_root / "full" / "evaluation",
    )
    assert len(artifact["groups"]) == 6
    groups = {
        row["method"]: row
        for row in artifact["groups"]
        if row["cell"] == "analytic"
    }
    assert groups["exact_full"]["horizons"][-1][
        "cumulative_pseudo_regret"
    ]["mean"] == pytest.approx(0.9)
    assert groups["diagonal_raw"]["horizons"][-1][
        "cumulative_pseudo_regret"
    ]["mean"] == pytest.approx(90.0)
