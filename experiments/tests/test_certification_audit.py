from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.make_certification_audit import (
    ANALYTIC_TRANSFER_METHODS,
    CATEGORIES,
    EX_ANTE_CERTIFIED_METHODS,
    generate,
)
from experiments.run_linear_audit import (
    DEFAULT_CONFIG,
    FEATURE_DIMENSION,
    SUPPORTED_METHODS,
    confidence_radius,
    run_method,
)


COMPARISONS = ("fixed_reference", "validation_tuned")
UNVERIFIED_TRANSFER_METHODS = frozenset(SUPPORTED_METHODS) - ANALYTIC_TRANSFER_METHODS


def _summary(method: str, seed: int) -> dict[str, object]:
    return {
        "method": method,
        "seed": seed,
        "executed_policy": True,
        "certificate_mode": "predictable_exact_small_scale",
        "policy_used_predictable_valid_certificates": True,
        "confidence_event_realized": True,
        "certified_execution": True,
        "C_equals_Cbar_all_rounds": True,
        "theorem_bound_slack": 10.0,
        "dynamic_bound_slack": 0.0,
        "width_information_slack": 1.0,
        "width_dynamic_slack": 1.0,
        "transfer_slack_min": 0.0,
        "bonus_lower_slack_min": 0.0,
        "bonus_upper_slack_min": 0.0,
        "cg_sandwich_lower_slack_min": 0.0,
        "cg_sandwich_upper_slack_min": 0.0,
        "dynamic_identity_residual": 0.0,
    }


def _stat(value: float) -> dict[str, float | int | list[float]]:
    return {
        "mean": value,
        "n": 1,
        "ci95": [value, value],
        "ci95_low": value,
        "ci95_high": value,
        "ci95_half_width": 0.0,
        "standard_deviation": 0.0,
        "standard_error": 0.0,
        "t_critical": 0.0,
    }


def _write_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, ...]:
    config = {
        "schema_version": 1,
        "name": "linear_audit",
        "profile": "full",
        "rounds": 2,
        "methods": list(SUPPORTED_METHODS),
        "comparisons": list(COMPARISONS),
        "seed_sets": {"tuning": [0], "evaluation": [100]},
        "ridge": 1.0,
        "bonus_scale": 1.0,
        "confidence": {"delta": 0.05, "bonus_scale": 1.0},
        "environment": {
            "context_dimension": 8,
            "action_count": 5,
            "noise_std": 0.25,
        },
        "curvature": {
            "window_size": 2,
            "subsample_size": 2,
            "lanczos_rank": 2,
            "refresh_period": 2,
        },
        "cg": {"tolerance": 0.05, "max_iterations": 2 * FEATURE_DIMENSION},
    }
    monkeypatch.setattr(
        "experiments.make_certification_audit.load_config",
        lambda path, profile: copy.deepcopy(config),
    )
    config_path = tmp_path / "linear_audit.yaml"
    config_path.write_text("{}\n", encoding="ascii")
    selection_path = tmp_path / "selection.json"
    selection = {
        "event": "linear_study_selection",
        "profile": "full",
        "seed_sets_disjoint": True,
        "tuning_seed_set": [0],
        "evaluation_seed_set": [100],
        "selected": {
            method: {
                "candidate_id": "candidate-000",
                "hyperparameters": {"ridge": 1.0, "bonus_scale": 1.0},
            }
            for method in SUPPORTED_METHODS
        },
    }
    selection_path.write_text(
        json.dumps(selection, sort_keys=True) + "\n", encoding="ascii"
    )
    selection_sha256 = hashlib.sha256(selection_path.read_bytes()).hexdigest()
    raw_root = tmp_path / "evaluation"
    groups = []
    for comparison in COMPARISONS:
        for method in SUPPORTED_METHODS:
            directory = raw_root / comparison / method / "seed-100"
            directory.mkdir(parents=True)
            manifest_config = copy.deepcopy(config)
            manifest_config["study"] = {
                "phase": "evaluation",
                "comparison": comparison,
                "selection_sha256": selection_sha256,
                "hyperparameters": {"ridge": 1.0, "bonus_scale": 1.0},
            }
            manifest_config["execution"] = {
                "method": method,
                "executed_policy": True,
            }
            manifest = {"seed": 100, "config": manifest_config}
            (directory / "manifest.jsonl").write_text(
                json.dumps(manifest, sort_keys=True) + "\n", encoding="ascii"
            )
            (directory / "summary.jsonl").write_text(
                json.dumps(_summary(method, 100), sort_keys=True) + "\n",
                encoding="ascii",
            )
            epsilon = 0.05 if method == "cg_full" else 0.0
            groups.append(
                {
                    "comparison": comparison,
                    "method": method,
                    "hyperparameters": {"ridge": 1.0, "bonus_scale": 1.0},
                    "run_count": 1,
                    "seeds": [100],
                    "horizons": [
                        {
                            "horizon": 2,
                            "metrics": {
                                "beta_t": _stat(5.0),
                                "bar_psi_t": _stat(0.0),
                                "u_t": _stat(1.0),
                                "cg_certified_epsilon": _stat(epsilon),
                                "cg_energy_error_max": _stat(0.0),
                                "kappa_bar_t": _stat(1.0),
                                "theorem_bound_slack": _stat(10.0),
                            },
                        }
                    ],
                }
            )
    aggregate_path = tmp_path / "linear_audit_full.json"
    aggregate = {
        "schema_version": 1,
        "event": "executed_policy_aggregate",
        "all_groups_complete": True,
        "all_runs_executed_policy": True,
        "all_seed_provenance_disjoint": True,
        "profiles": ["full"],
        "seed_sets": ["evaluation"],
        "run_count": len(groups),
        "input_set_sha256": "fixture-input-set",
        "groups": groups,
    }
    aggregate_path.write_text(
        json.dumps(aggregate, sort_keys=True) + "\n", encoding="ascii"
    )
    return config_path, selection_path, raw_root, aggregate_path


def test_generator_is_reproducible_and_category_vocabulary_is_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, selection, raw_root, aggregate = _write_fixture(tmp_path, monkeypatch)
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"

    first = generate(config, selection, raw_root, aggregate, first_path)
    first_bytes = first_path.read_bytes()
    first_sidecar = first_path.with_suffix(".json.provenance.json").read_bytes()
    second = generate(config, selection, raw_root, aggregate, second_path)
    generate(config, selection, raw_root, aggregate, first_path)

    assert first == second
    assert first_path.read_bytes() == second_path.read_bytes()
    assert first_path.read_bytes() == first_bytes
    assert first_path.with_suffix(".json.provenance.json").read_bytes() == first_sidecar
    assert tuple(first["category_definitions"]) == CATEGORIES
    assert len(first["policies"]) == 2 * len(SUPPORTED_METHODS)
    for policy in first["policies"]:
        assert set(policy["categories"]) == set(CATEGORIES)
        assert policy["policy_name"] == policy["policy_id"]
        assert policy["exact_bonus_formula"].startswith("w_t(a)=")
        assert set(policy["policy_available_schedules"]) == {
            "beta_bar_t",
            "c_bonus",
            "psi_bar_t",
            "u_t(a)",
            "epsilon_bar_t",
            "kappa_bar_t",
        }
        for schedule in policy["policy_available_schedules"].values():
            assert schedule["source_file"]
            assert schedule["config_key"]
            assert schedule["category"] in CATEGORIES
        assert all(field["category"] in CATEGORIES for field in policy["posthoc_fields"])
        method = policy["method"]
        ex_ante_certified = method in EX_ANTE_CERTIFIED_METHODS
        assert policy["certification_category"] == (
            "ex_ante_theorem_certified"
            if ex_ante_certified
            else "posthoc_theorem_event_verified"
        )
        assert policy["categories"] == {
            "ex_ante_theorem_certified": ex_ante_certified,
            "posthoc_theorem_event_verified": True,
            "cg_solver_certified": False,
            "uncertified_diagnostic": not ex_ante_certified,
        }
        transfer = policy["policy_available_schedules"]["u_t(a)"]
        assert transfer["one_sided_upper_enclosure_verified"] is (
            method in ANALYTIC_TRANSFER_METHODS
        )
        assert transfer["category"] == (
            "uncertified_diagnostic"
            if method in UNVERIFIED_TRANSFER_METHODS
            else "ex_ante_theorem_certified"
        )
        if method == "cg_full":
            schedules = policy["policy_available_schedules"]
            assert schedules["epsilon_bar_t"]["category"] == "uncertified_diagnostic"
            assert schedules["epsilon_bar_t"]["uniform_upper_bound_verified"] is False
            assert schedules["kappa_bar_t"]["category"] == "uncertified_diagnostic"
            assert (
                schedules["kappa_bar_t"]["one_sided_upper_enclosure_verified"]
                is False
            )
        raw_claims = policy["posthoc_theorem_event_evidence"][
            "raw_summary_certification_claims"
        ]
        assert raw_claims["reported_values"] == {
            "policy_used_predictable_valid_certificates": True,
            "certified_execution": True,
            "certificate_mode": ["predictable_exact_small_scale"],
        }
        assert raw_claims["audit_disposition"] == (
            "independently_supported_by_analytic_audit"
            if ex_ante_certified
            else "superseded_as_insufficient"
        )
        assert raw_claims["raw_files_rewritten"] is False


@pytest.mark.parametrize("method", ("dense_full", "cg_full"))
def test_logged_beta_and_bonus_match_c_bonus_semantics(method: str) -> None:
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rounds"] = 3
    config["bonus_scale"] = 1.25
    config["confidence"] = {"delta": 0.05, "bonus_scale": 1.25}
    run = run_method(config, method, 17, retain_matrices=False)

    for round_index, record in enumerate(run.rounds, start=1):
        beta_base, _ = confidence_radius(
            round_index,
            dimension=FEATURE_DIMENSION,
            feature_bound=np.sqrt(3.0),
            ridge=run.config.ridge,
            noise_std=run.config.noise_std,
            delta=run.config.delta,
            theta_bound=run.config.theta_bound,
        )
        assert record["beta_t"] == pytest.approx(1.25 * beta_base)
        expected_bonus = (
            record["beta_t"]
            * np.sqrt(record["u_t"] / (1.0 - record["cg_certified_epsilon"]))
            * np.sqrt(np.asarray(record["approximate_widths_squared"]))
        )
        np.testing.assert_allclose(record["bonuses"], expected_bonus, rtol=1e-13)


def test_checked_full_artifact_covers_every_primary_policy() -> None:
    path = Path("results/derived/certification_audit.json")
    value = json.loads(path.read_text(encoding="ascii"))
    sidecar = json.loads(
        path.with_suffix(".json.provenance.json").read_text(encoding="ascii")
    )

    assert value["scope"]["primary_policy_count"] == 14
    assert value["scope"]["evaluation_run_count"] == 280
    assert {policy["policy_id"] for policy in value["policies"]} == {
        f"{comparison}/{method}"
        for comparison in COMPARISONS
        for method in SUPPORTED_METHODS
    }
    assert value["c_bonus_beta_relationship"]["exact_formula"] == (
        "bar_beta_t = c_bonus * beta_base_t"
    )
    assert sidecar["artifact_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert sidecar["category_vocabulary"] == list(CATEGORIES)

    for policy in value["policies"]:
        method = policy["method"]
        ex_ante_certified = method in EX_ANTE_CERTIFIED_METHODS
        assert policy["certification_category"] == (
            "ex_ante_theorem_certified"
            if ex_ante_certified
            else "posthoc_theorem_event_verified"
        )
        assert policy["categories"] == {
            "cg_solver_certified": False,
            "ex_ante_theorem_certified": ex_ante_certified,
            "posthoc_theorem_event_verified": True,
            "uncertified_diagnostic": not ex_ante_certified,
        }
        transfer = policy["policy_available_schedules"]["u_t(a)"]
        assert transfer["one_sided_upper_enclosure_verified"] is (
            method in ANALYTIC_TRANSFER_METHODS
        )
        if method == "cg_full":
            assert policy["action_selection"]["solve_definition"].startswith(
                "tilde_u_t(a) is the recorded truncated CG iterate"
            )
        raw_claims = policy["posthoc_theorem_event_evidence"][
            "raw_summary_certification_claims"
        ]
        assert raw_claims["audit_disposition"] == (
            "independently_supported_by_analytic_audit"
            if ex_ante_certified
            else "superseded_as_insufficient"
        )
        assert raw_claims["reported_values"] == {
            "certificate_mode": ["predictable_exact_small_scale"],
            "certified_execution": True,
            "policy_used_predictable_valid_certificates": True,
        }
