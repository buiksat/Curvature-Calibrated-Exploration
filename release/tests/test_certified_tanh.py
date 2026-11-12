from __future__ import annotations

import json
import inspect
import math
from pathlib import Path

import numpy as np
import pytest

from experiments.config import get_seed_set, load_config
from experiments.curvature_operators import CurvatureOperator
from experiments.run_certified_tanh import (
    TANH_SECOND_DERIVATIVE_MAX,
    TanhBanditEnvironment,
    analytic_tanh_constants,
    certified_cg_widths,
    certified_policy_scores,
    controlled_grid_cells,
    run_certified_policy,
    save_run,
    tanh_gradients,
    tanh_mean,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments" / "configs" / "certified_tanh.yaml"


def test_tanh_analytic_gradient_and_lipschitz_constant() -> None:
    rng = np.random.default_rng(720)
    dimension = 6
    bound = 0.75
    theta = rng.normal(0.0, 0.2, size=dimension)
    features = rng.normal(size=(5, dimension))
    features *= bound / np.linalg.norm(features, axis=1, keepdims=True)
    analytic = tanh_gradients(theta, features)
    numerical = np.empty_like(analytic)
    step = 1.0e-6
    for coordinate in range(dimension):
        offset = np.zeros(dimension)
        offset[coordinate] = step
        numerical[:, coordinate] = (
            tanh_mean(theta + offset, features)
            - tanh_mean(theta - offset, features)
        ) / (2.0 * step)
    np.testing.assert_allclose(analytic, numerical, rtol=2e-10, atol=2e-11)

    G, L_mu, L_g = analytic_tanh_constants(bound)
    assert G == bound
    assert L_mu == L_g
    assert L_mu == pytest.approx(TANH_SECOND_DERIVATIVE_MAX * bound**2)
    other = theta + rng.normal(0.0, 0.03, size=dimension)
    difference = np.linalg.norm(
        tanh_gradients(theta, features) - tanh_gradients(other, features), axis=1
    )
    assert np.all(difference <= L_g * np.linalg.norm(theta - other) + 2e-14)


def test_environment_is_bounded_and_reproducible() -> None:
    kwargs = dict(
        seed=721,
        rounds=7,
        action_count=4,
        dimension=6,
        feature_bound=0.7,
        noise_std=0.2,
        theta_star=np.asarray([0.1, -0.1, 0.05, 0.04, -0.03, 0.02]),
    )
    first = TanhBanditEnvironment(**kwargs)
    second = TanhBanditEnvironment(**kwargs)
    assert first.stream_sha256 == second.stream_sha256
    for round_index in range(7):
        np.testing.assert_array_equal(first.features(round_index), second.features(round_index))
        np.testing.assert_allclose(
            np.linalg.norm(first.features(round_index), axis=1), 0.7, rtol=2e-15
        )
        first_reward = first.reward_and_audit(round_index, 2)
        second_reward = second.reward_and_audit(round_index, 2)
        np.testing.assert_allclose(first_reward[:2], second_reward[:2])
        np.testing.assert_array_equal(first_reward[2], second_reward[2])
        assert first_reward[3] == second_reward[3]


def test_analytic_condition_bound_certifies_all_cg_widths() -> None:
    rng = np.random.default_rng(722)
    rows = rng.normal(size=(20, 6))
    rows /= np.maximum(np.linalg.norm(rows, axis=1, keepdims=True), 1.0)
    gradients = rng.normal(size=(4, 6))
    ridge = 0.9
    variance = 0.3**2
    operator = CurvatureOperator(rows, damping=ridge, noise_variance=variance)
    G = float(np.max(np.linalg.norm(rows, axis=1)))
    kappa_bar = 1.0 + rows.shape[0] * G**2 / (ridge * variance)
    result = certified_cg_widths(
        operator,
        gradients,
        condition_upper_bound=kappa_bar,
        energy_error_bound=0.05,
        max_iterations=48,
    )
    dense = operator.to_dense()
    exact = np.linalg.solve(dense, gradients.T).T
    for rhs, exact_solution, approximate, certificate in zip(
        gradients,
        exact,
        result.solutions,
        result.residual_certificates,
        strict=True,
    ):
        error = exact_solution - approximate
        relative_energy = math.sqrt(
            float(error @ dense @ error) / float(exact_solution @ dense @ exact_solution)
        )
        assert relative_energy <= certificate + 2e-13
        assert certificate <= 0.05 + 2e-13
        assert float(rhs @ approximate) > 0.0


def test_policy_score_function_has_no_teacher_or_posthoc_input() -> None:
    parameters = inspect.signature(certified_policy_scores).parameters
    assert "theta_star" not in parameters
    assert not any("posthoc" in name for name in parameters)
    scores, bonuses = certified_policy_scores(
        np.asarray([0.1, 0.2]),
        np.asarray([0.0, 0.3]),
        np.asarray([0.25, 1.0]),
        center="original",
        beta_bar=2.0,
        psi_bar=1.0,
        corrected_center_error_bar=0.0,
        transfer_factor=1.5,
        cg_error_bound=0.1,
    )
    np.testing.assert_allclose(scores, np.asarray([0.1, 0.2]) + bonuses)


def test_smoke_policies_execute_with_zero_certificate_failures() -> None:
    config = load_config(CONFIG, profile="smoke")
    runs = [
        run_certified_policy(config, 160, center=center)
        for center in ("original", "corrected")
    ]
    assert runs[0].summary["environment_stream_sha256"] == runs[1].summary[
        "environment_stream_sha256"
    ]
    for run in runs:
        assert run.summary["all_observed_theorem_event_checks_hold"] is True
        assert run.summary["certificate_failure_count"] == 0
        assert run.summary["policy_uses_teacher"] is False
        assert run.summary["policy_uses_posthoc_diagnostics"] is False
        assert run.summary["certification_category"] == "posthoc_theorem_event_verified"
        assert len(run.records) == 8
        assert run.records[-1]["Lambda_algorithmic_observable_upper"] + 1e-12 >= run.records[-1][
            "Lambda_algorithmic_exact"
        ]
        assert run.records[-1]["theorem_rhs_observable"] + 1e-12 >= run.records[-1][
            "cumulative_pseudo_regret"
        ]
        assert all(record["policy_certificate_gamma_hat_prior"] + 1e-11 >= record[
            "posthoc_exact_gamma_prior"
        ] for record in run.records)
        assert max(record["theta_norm_after_update"] for record in run.records) <= 0.5 + 1e-14

    repeated = run_certified_policy(config, 160, center="original")
    assert repeated.deterministic_signature() == runs[0].deterministic_signature()


def test_full_protocol_has_disjoint_50_seed_evaluation_set() -> None:
    config = load_config(CONFIG, profile="full")
    tuning = get_seed_set(config, "tuning")
    evaluation = get_seed_set(config, "evaluation")
    assert len(tuning) == 10
    assert len(evaluation) == 50
    assert set(tuning).isdisjoint(evaluation)
    assert config["controlled_grid"]["selection_rule"].startswith("pre-registered")
    cells = controlled_grid_cells(config)
    assert len(cells) == 8
    assert {cell["id"] for cell in cells} == {
        "reference",
        "trust035",
        "scale050",
        "horizon050",
        "horizon200",
        "cg010",
        "ridge050",
        "refresh005",
    }


def test_save_run_writes_manifest_raw_and_summary(tmp_path: Path) -> None:
    config = load_config(CONFIG, profile="smoke")
    config["execution"] = {"seed_set": "evaluation", "center": "original"}
    run = run_certified_policy(config, 160, center="original")
    destination = save_run(run, config, tmp_path / "run")
    assert {path.name for path in destination.iterdir()} == {
        "manifest.jsonl",
        "raw.jsonl",
        "summary.jsonl",
    }
    records = [json.loads(line) for line in (destination / "raw.jsonl").read_text().splitlines()]
    summary = json.loads((destination / "summary.jsonl").read_text())
    assert len(records) == 8
    assert summary["certificate_failure_count"] == 0
    assert records[0]["metrics"]["posthoc_fields_used_by_policy"] is False
