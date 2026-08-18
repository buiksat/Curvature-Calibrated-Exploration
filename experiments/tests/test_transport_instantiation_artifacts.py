from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from experiments.aggregate_transport_instantiation import METHODS
from experiments.artifact_utils import (
    input_set_sha256,
    sha256_file,
    validate_sha256_sidecar,
    write_aggregate_with_provenance,
)
from experiments.make_transport_instantiation_artifacts import (
    DEFAULT_CONFIG,
    TransportArtifactError,
    _curve_plot_rounds,
    escape_tex,
    make_artifacts,
    make_performance_table,
)
from experiments.config import config_digest, load_config


def _stat(value: float) -> dict[str, Any]:
    return {
        "n": 50,
        "mean": value,
        "standard_error": 0.1,
        "median": value,
        "iqr": 0.2,
        "p10": value - 0.2,
        "p25": value - 0.1,
        "p75": value + 0.1,
        "p90": value + 0.2,
        "min": value - 0.3,
        "max": value + 0.3,
    }


def _coverage(successes: int = 49) -> dict[str, Any]:
    return {
        "successes": successes,
        "n": 50,
        "estimate": successes / 50.0,
        "level": 0.95,
        "method": "exact_clopper_pearson",
        "ci_low": 0.89,
        "ci_high": 0.999,
        "ci": [0.89, 0.999],
    }


def _aggregate(tmp_path: Path) -> tuple[dict[str, Any], Path]:
    targets = [2.0, 1.0, 0.5, 0.25]
    validity = []
    tightness = []
    outcomes = []
    curves = []
    path_points = []
    decomposition = []
    for target in targets:
        validity.append(
            {
                "horizon": 1000,
                "target_D": target,
                "run_count": 50,
                "reference_confidence_coverage": _coverage(),
                "transport_optimism_coverage": _coverage(48),
                "deterministic_audit_failures": 0,
                "bound_violations_on_joint_event": 0,
                "max_realized_D_Q": _stat(target / 2.0),
                "max_endpoint_Thompson_distance": _stat(target / 4.0),
                "sharp_theorem_rhs": _stat(20.0 + target),
                "cumulative_pseudo_regret": _stat(4.0 + target),
            }
        )
        tightness.append(
            {
                "horizon": 1000,
                "target_D": target,
                "D_Q_over_d_Th": _stat(2.0),
                "d_Th_at_or_below_ratio_tolerance_count": 0,
                "D_Q_over_D_path_quad": _stat(1.2),
                "D_path_quad_at_or_below_ratio_tolerance_count": 0,
                "D_path_quad_over_d_Th": _stat(1.6),
                "d_Th_at_or_below_tolerance_with_path_count": 0,
                "exp_D_Q_over_2": _stat(1.1),
                "historical_confidence_radius_contribution": _stat(0.3),
                "current_additive_bias": _stat(0.4),
                "frozen_width_sum_over_potential_upper": _stat(0.7),
                "sharp_rhs_over_simple_rhs": _stat(0.85),
            }
        )
        for method_index, method in reversed(list(enumerate(METHODS))):
            regret = _stat(3.0 + method_index + target)
            regret["bootstrap_mean_interval"] = {
                "level": 0.95,
                "ci_low": regret["mean"] - 0.25,
                "ci_high": regret["mean"] + 0.25,
                "ci": [regret["mean"] - 0.25, regret["mean"] + 0.25],
            }
            difference = _stat(float(method_index))
            difference["bootstrap_mean_interval"] = {
                "level": 0.95,
                "ci_low": float(method_index) - 0.2,
                "ci_high": float(method_index) + 0.2,
                "ci": [float(method_index) - 0.2, float(method_index) + 0.2],
            }
            outcomes.append(
                {
                    "horizon": 1000,
                    "target_D": target,
                    "method": method,
                    "method_role": "fixture",
                    "run_count": 50,
                    "cumulative_pseudo_regret": regret,
                    "paired_difference_from_transport_hessian": difference,
                    "simultaneous_optimism_coverage": _coverage(47),
                }
            )
            curves.append(
                {
                    "horizon": 1000,
                    "target_D": target,
                    "method": method,
                    "round": 1,
                    "mean": regret["mean"],
                    "ci_low": regret["mean"] - 0.25,
                    "ci_high": regret["mean"] + 0.25,
                }
            )
        path_points.append(
            {
                "horizon": 1000,
                "target_D": target,
                "seed": 100,
                "round": 10,
                "D_Q": target / 2.0,
                "d_Th": target / 4.0,
                "D_path_quad": target / 3.0,
            }
        )
        decomposition.append(
            {
                "horizon": 1000,
                "target_D": target,
                "round": 1,
                "statistical_bound_component": 1.0,
                "historical_bound_component": 0.2,
                "path_inflation_component": 0.3,
                "current_bias_cumulative": 0.4,
                "cumulative_pseudo_regret": 0.5,
                "sharp_theorem_rhs": 1.9,
            }
        )

    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "raw-input.txt"
    source.write_text("fixture raw inventory\n", encoding="ascii")
    inputs = [{"path": str(source), "sha256": sha256_file(source)}]
    aggregate = {
        "schema_version": 1,
        "event": "transport_instantiation_aggregate",
        "experiment": "transport_instantiation",
        "profile": "full",
        "publication_ready": True,
        "full_grid_complete": True,
        "all_deterministic_audits_pass": True,
        "stochastic_confidence_failures_retained": True,
        "completed_run_count": 2400,
        "expected_run_count": 2400,
        "config_digest": config_digest(load_config(DEFAULT_CONFIG, profile="full")),
        "evaluation_seeds": list(range(100, 150)),
        "methods": list(METHODS),
        "target_D": [0.25, 0.5, 1.0, 2.0],
        "horizons": [250, 500, 1000],
        "selected_optimizer": {
            "candidate_id": "candidate-000",
            "learning_rate": 0.01,
            "steps_per_round": 1,
        },
        "validity": validity,
        "policy_outcomes": outcomes,
        "certificate_tightness": tightness,
        "regret_curves": curves,
        "path_points": path_points,
        "bound_decomposition": decomposition,
        "inputs": inputs,
        "input_set_sha256": input_set_sha256(inputs),
    }
    aggregate_path, _ = write_aggregate_with_provenance(
        aggregate, tmp_path / "full_aggregate.json"
    )
    return aggregate, aggregate_path


def test_tex_escaping_and_stable_table_ordering(tmp_path: Path) -> None:
    aggregate, _ = _aggregate(tmp_path)
    escaped = escape_tex("a_b&c%$#{}~^" + "\\")
    assert escaped == (
        r"a\_b\&c\%\$\#\{\}\textasciitilde{}"
        r"\textasciicircum{}\textbackslash{}"
    )

    first = make_performance_table(aggregate)
    second = make_performance_table(copy.deepcopy(aggregate))
    assert first == second
    assert first.index("0.25 & transport Hessian") < first.index(
        "0.25 & transport endpoint"
    )
    assert first.index("0.25 & transport endpoint") < first.index(
        "0.25 & frozen reference"
    )
    assert first.index("0.25 & frozen reference") < first.index(
        "0.25 & naive current"
    )
    assert first.index("0.25 &") < first.index("2 &")
    assert "dense oracle" in first
    assert "uncertified" in first


def test_curve_plot_rounds_are_deterministic_and_preserve_endpoints() -> None:
    assert _curve_plot_rounds(32) == tuple(range(1, 33))
    rounds = _curve_plot_rounds(1000)
    assert len(rounds) == 101
    assert rounds[0] == 1
    assert rounds[-1] == 1000
    assert rounds == tuple(sorted(set(rounds)))


def test_artifact_generation_is_deterministic_and_bound_to_exact_aggregate(
    tmp_path: Path,
) -> None:
    _, aggregate_path = _aggregate(tmp_path)
    tables = tmp_path / "tables"
    figures = tmp_path / "figures"
    kwargs = {
        "validity_table": tables / "validity.tex",
        "performance_table": tables / "performance.tex",
        "tightness_table": tables / "tightness.tex",
        "figure_directory": figures,
    }
    first = make_artifacts(aggregate_path, **kwargs)
    first_payloads = {
        item["path"]: Path(item["path"]).read_bytes() for item in first["artifacts"]
    }
    second = make_artifacts(aggregate_path, **kwargs)
    second_payloads = {
        item["path"]: Path(item["path"]).read_bytes() for item in second["artifacts"]
    }
    assert first == second
    assert first_payloads == second_payloads

    aggregate_sha256 = sha256_file(aggregate_path)
    assert first["aggregate_sha256"] == aggregate_sha256
    for item in first["artifacts"]:
        path = Path(item["path"])
        assert item["sha256"] == sha256_file(path)
        validate_sha256_sidecar(path)
        assert aggregate_sha256.encode("ascii") in path.read_bytes()
        provenance = Path(item["provenance"]).read_text(encoding="ascii")
        assert aggregate_sha256 in provenance

    regret_tex = (figures / "transport_instantiation_regret.tex").read_text(
        encoding="ascii"
    )
    path_tex = (figures / "transport_instantiation_tightness.tex").read_text(
        encoding="ascii"
    )
    bound_tex = (figures / "transport_instantiation_bound.tex").read_text(
        encoding="ascii"
    )
    assert regret_tex.count(r"xlabel={Round}") == 2
    assert bound_tex.count(r"xlabel={Round}") == 2
    assert path_tex.count(r"xlabel={$d_{\rm Th}$}") == 2
    assert (
        "scatter/use mapped color={draw=blue!75!black,fill=blue!75!black}"
        in path_tex
    )
    assert (
        "scatter/use mapped color={draw=orange!90!black,fill=orange!90!black}"
        in path_tex
    )


def test_smoke_aggregate_is_never_accepted_as_publication_evidence(
    tmp_path: Path,
) -> None:
    aggregate, _ = _aggregate(tmp_path / "full")
    smoke = copy.deepcopy(aggregate)
    smoke["profile"] = "smoke"
    smoke["publication_ready"] = False
    source = tmp_path / "smoke-source.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("smoke\n", encoding="ascii")
    smoke["inputs"] = [{"path": str(source), "sha256": sha256_file(source)}]
    smoke["input_set_sha256"] = input_set_sha256(smoke["inputs"])
    smoke_path, _ = write_aggregate_with_provenance(
        smoke, tmp_path / "smoke_aggregate.json"
    )

    with pytest.raises(TransportArtifactError, match="publication-ready: profile"):
        make_artifacts(
            smoke_path,
            validity_table=tmp_path / "validity.tex",
            performance_table=tmp_path / "performance.tex",
            tightness_table=tmp_path / "tightness.tex",
            figure_directory=tmp_path / "figures",
        )
