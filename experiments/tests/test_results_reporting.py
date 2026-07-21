from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.aggregate_results import (
    AggregationError,
    _nonlinear_hypothesis_audits,
    aggregate_results,
    prefix_metrics,
    validate_aggregate_provenance_sidecar,
    write_aggregate_with_provenance,
)
from experiments.make_paper_artifacts import (
    ArtifactError,
    make_paper_artifacts,
    validate_primary_aggregate,
)
from experiments.run_linear_study import run_linear_study, tuning_run_is_valid


def _study_config() -> dict[str, object]:
    return {
        "schema_version": 1,
        "name": "linear_audit",
        "description": "fixture",
        "profile": "full",
        "rounds": 4,
        "tuning_rounds": 2,
        "methods": ["dense_full", "cg_full"],
        "ridge": 1.0,
        "confidence": {"bonus_scale": 1.0},
        "tuning_grid": {"ridge": [1.0, 2.0], "bonus_scale": [1.0]},
        "seed_sets": {"tuning": [1, 2], "evaluation": [101, 102]},
    }


def test_linear_study_selects_only_valid_tuning_and_restarts_evaluation(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, int, int, float, int]] = []
    saved: list[tuple[Path, dict[str, object]]] = []

    def runner(config, method, seed, *, retain_matrices):
        del retain_matrices
        phase = config["study"]["phase"]
        ridge = float(config["ridge"])
        calls.append((phase, int(config["rounds"]), seed, ridge, id(config)))
        # Ridge 1 has lower regret but fails its certificate on one tuning seed.
        valid = not (phase == "tuning" and ridge == 1.0 and seed == 2)
        regret = ridge + seed / 1000.0
        return SimpleNamespace(
            method=method,
            seed=seed,
            summary={
                "executed_policy": True,
                "confidence_event_realized": True,
                "policy_used_predictable_valid_certificates": True,
                "certified_execution": valid,
                "cumulative_pseudo_regret": regret,
            },
        )

    def saver(run, destination, config, *, overwrite):
        del run, overwrite
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        saved.append((destination, copy.deepcopy(config)))
        return destination

    result = run_linear_study(
        _study_config(), tmp_path / "raw", runner=runner, saver=saver
    )

    assert result["selected"]["dense_full"]["hyperparameters"]["ridge"] == 2.0
    assert result["selected"]["cg_full"]["hyperparameters"]["ridge"] == 2.0
    assert result["tuning_run_count"] == 8
    assert result["evaluation_run_count"] == 8
    assert all(rounds == 2 for phase, rounds, *_ in calls if phase == "tuning")
    assert all(rounds == 4 for phase, rounds, *_ in calls if phase == "evaluation")
    assert {seed for phase, _, seed, *_ in calls if phase == "tuning"} == {1, 2}
    assert {seed for phase, _, seed, *_ in calls if phase == "evaluation"} == {
        101,
        102,
    }
    evaluation_configs = [identity for phase, *_, identity in calls if phase == "evaluation"]
    # Each method/comparison gets its own immutable runtime config; the runner
    # constructs a new policy for each seed.
    assert len(set(evaluation_configs)) == 4
    assert any("fixed_reference" in str(path) for path, _ in saved)
    assert any("validation_tuned" in str(path) for path, _ in saved)
    selection_path = Path(result["selection_path"])
    assert selection_path.is_file()
    assert hashlib.sha256(selection_path.read_bytes()).hexdigest() == result[
        "selection_sha256"
    ]


def test_tuning_validity_requires_all_three_claims() -> None:
    valid = {
        "executed_policy": True,
        "confidence_event_realized": True,
        "policy_used_predictable_valid_certificates": True,
        "certified_execution": True,
    }
    assert tuning_run_is_valid(valid)
    for key in valid:
        invalid = dict(valid)
        invalid[key] = False
        assert not tuning_run_is_valid(invalid)


def test_nonlinear_prefix_standardizes_policy_rhs_and_all_action_violations() -> None:
    raw = [
        {
            "round": 0,
            "metrics": {
                "executed_policy": True,
                "policy_optimism_violation_count": 1,
                "policy_scores_all_actions": [0.0] * 5,
                "posthoc_theorem_rhs_using_policy_schedule": 10.0,
                "posthoc_theorem_rhs_using_exact_diagnostics": 20.0,
            },
        },
        {
            "round": 1,
            "metrics": {
                "executed_policy": True,
                "policy_optimism_violation_count": 2,
                "policy_scores_all_actions": [0.0] * 5,
                "posthoc_theorem_rhs_using_policy_schedule": 12.0,
                "posthoc_theorem_rhs_using_exact_diagnostics": 24.0,
            },
        },
    ]

    metrics = prefix_metrics(raw, 2)
    assert metrics["theorem_rhs"] == 12.0
    assert metrics["diagnostic_theorem_rhs"] == 24.0
    assert metrics["optimism_violation_rate"] == pytest.approx(0.3)


def test_prefix_reports_regret_normalization_and_binary_accuracy() -> None:
    raw = [
        {
            "round": 0,
            "metrics": {"cumulative_pseudo_regret": 0.5, "true_label_arm": 1},
        },
        {
            "round": 1,
            "metrics": {"cumulative_pseudo_regret": 1.0, "true_label_arm": 0},
        },
    ]
    metrics = prefix_metrics(raw, 2)
    assert metrics["mean_pseudo_regret"] == 0.5
    assert metrics["accuracy"] == 0.5


def test_nonlinear_hypothesis_audit_is_descriptive_and_flags_nonmonotone_optimism() -> None:
    values = [
        ("frozen_head", "original", 11.123638, 1001.386071, 0.0, 0.0088),
        ("frozen_head", "corrected", 11.123638, 1001.386071, 0.0, 0.0088),
        ("mild", "original", 20.255891, 1376.721351, 6.799617, 0.1700),
        ("mild", "corrected", 11.927316, 1175.897981, 6.603154, 0.0027),
        ("medium", "original", 18.339042, 2344.538479, 19.274041, 0.0011),
        ("medium", "corrected", 15.173542, 1751.464177, 19.377907, 0.0083),
        ("aggressive", "original", 20.719025, 4442.658897, 6.832380, 0.0),
        ("aggressive", "corrected", 17.718915, 2643.241943, 7.205551, 0.0016),
    ]

    def stats(mean: float) -> dict[str, float]:
        return {"mean": mean}

    groups = [
        {
            "experiment": "nonlinear_audit",
            "profile": "full",
            "seed_set": "evaluation",
            "method": regime,
            "variant": {"center": center},
            "summary_metrics": {
                "cumulative_pseudo_regret": stats(regret),
                "theorem_rhs_policy_schedule": stats(rhs),
                "policy_optimism_violation_rate": stats(optimism),
            },
            "horizons": [
                {
                    "horizon": 100,
                    "metrics": {
                        "posthoc_whitened_curvature_difference_operator_norm": stats(
                            relative
                        )
                    },
                }
            ],
            "run_directories": [f"run/{regime}/{center}"],
        }
        for regime, center, regret, rhs, relative, optimism in values
    ]

    audit = _nonlinear_hypothesis_audits(groups)[0]
    correlations = {
        item["predictor"]: item["spearman_rho"] for item in audit["correlations"]
    }
    assert correlations["mean_policy_schedule_theorem_rhs"] == pytest.approx(
        0.8313253012
    )
    assert correlations[
        "mean_posthoc_relative_curvature_change_operator_norm"
    ] == pytest.approx(0.5662650602)
    assert audit["n_cells"] == 8
    assert audit["causal"] is False
    assert audit["independent_cells"] is False
    optimism_hypothesis = audit["hypotheses"][1]
    assert optimism_hypothesis["status"] == "failed_or_mixed"
    assert optimism_hypothesis["monotone_non_decreasing_by_center"] == {
        "corrected": False,
        "original": False,
    }


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _write_policy_run(
    root: Path,
    *,
    seed: int,
    profile: str = "full",
    executed: bool = True,
    overlap: bool = False,
    method: str = "dense_full",
    regret_scale: float = 1.0,
) -> Path:
    directory = root / "linear_audit" / profile / "evaluation" / method / f"seed-{seed}"
    tuning = [seed] if overlap else [0]
    config = {
        "name": "linear_audit",
        "profile": profile,
        "rounds": 3,
        "horizons": [1, 2, 3],
        "seed_sets": {"tuning": tuning, "evaluation": [100, 101]},
        "execution": {"method": method, "executed_policy": executed},
    }
    _write_jsonl(
        directory / "manifest.jsonl",
        [{"schema_version": 1, "seed": seed, "config": config}],
    )
    raw = []
    cumulative = 0.0
    for round_index in range(3):
        regret = float(regret_scale * (seed - 99) * (round_index + 1))
        cumulative += regret
        raw.append(
            {
                "round": round_index,
                "metrics": {
                    "executed_policy": executed,
                    "pseudo_regret": regret,
                    "cumulative_pseudo_regret": cumulative,
                    "theorem_rhs": cumulative + 10.0,
                    "Lambda_alg_cumulative": round_index + 0.5,
                    "S_t_cumulative": round_index + 2.0,
                    "round_runtime_seconds": 0.1,
                    "runtime_seconds": 0.1 * (round_index + 1),
                },
            }
        )
    _write_jsonl(directory / "raw.jsonl", raw)
    _write_jsonl(
        directory / "summary.jsonl",
        [
            {
                "seed": seed,
                "method": method,
                "executed_policy": executed,
                "rounds": 3,
                "cumulative_pseudo_regret": cumulative,
                "theorem_rhs": cumulative + 10.0,
                "runtime_seconds": 0.3,
            }
        ],
    )
    return directory


def _write_offline_operator_run(
    root: Path, *, seed: int, operator: str, trajectory_digest: str
) -> Path:
    directory = (
        root
        / "operator_ablation"
        / "full"
        / "evaluation"
        / "offline_common_trajectory"
        / operator
        / f"seed-{seed}"
    )
    config = {
        "name": "operator_ablation",
        "profile": "full",
        "rounds": 2,
        "seed_sets": {"tuning": [0], "evaluation": [100, 101]},
        "execution": {
            "mode": "offline_common_trajectory_diagnostic",
            "operator": operator,
        },
    }
    _write_jsonl(
        directory / "manifest.jsonl",
        [{"schema_version": 1, "seed": seed, "config": config}],
    )
    raw = [
        {
            "round": round_index,
            "metrics": {
                "executed_policy": False,
                "offline_diagnostic": True,
                "causal_regret_claim": False,
                "regret_reported": False,
                "execution_mode": "offline_common_trajectory_diagnostic",
                "trajectory_digest": trajectory_digest,
                "operator": operator,
                "width_distortion": float(round_index + 1),
            },
        }
        for round_index in range(2)
    ]
    _write_jsonl(directory / "raw.jsonl", raw)
    _write_jsonl(
        directory / "summary.jsonl",
        [
            {
                "seed": seed,
                "operator": operator,
                "executed_policy": False,
                "offline_diagnostic": True,
                "causal_regret_claim": False,
                "regret_reported": False,
                "execution_mode": "offline_common_trajectory_diagnostic",
                "trajectory_digest": trajectory_digest,
                "rounds": 2,
                "width_distortion_max": 2.0,
            }
        ],
    )
    return directory


def _write_cg_benchmark_run(root: Path, *, seed: int) -> None:
    directory = root / "cg_accuracy" / "full" / "evaluation" / f"seed-{seed}"
    config = {
        "name": "cg_accuracy",
        "profile": "full",
        "rounds": 99,
        "seed_sets": {"tuning": [0], "evaluation": [100, 101]},
        "execution": {"driver": "run_cg_accuracy"},
    }
    _write_jsonl(
        directory / "manifest.jsonl",
        [{"schema_version": 1, "seed": seed, "config": config}],
    )
    raw = []
    for round_index, (initialization, iterations, initial_error) in enumerate(
        (("zero", 3, 1.0), ("warm", 2, 0.5))
    ):
        raw.append(
            {
                "round": round_index,
                "metrics": {
                    "condition_number_requested": 10.0,
                    "target_energy_error": 0.1,
                    "epsilon_bar": 0.1,
                    "initialization": initialization,
                    "preconditioner": "none",
                    "cg_iterations": iterations,
                    "initial_relative_energy_error": initial_error,
                    "exact_relative_energy_error": 0.05,
                    "wall_time_seconds": 0.01,
                    "sample_cvp_count": 100,
                    "predictive_width_relative_error": 0.001,
                    "peak_host_memory_bytes": 1000,
                },
            }
        )
    _write_jsonl(directory / "raw.jsonl", raw)
    _write_jsonl(
        directory / "summary.jsonl",
        [
            {
                "experiment": "cg_accuracy",
                "seed": seed,
                "record_count": 2,
                "target_failure_count": 0,
                "certificate_target_failure_count": 0,
                "residual_certificate_violation_count": 0,
                "sandwich_violation_count": 0,
                "optimism_violation_count": 0,
                "warm_start_advantage_assumed": False,
            }
        ],
    )


def _write_systems_benchmark_run(root: Path, *, seed: int) -> None:
    directory = root / "systems_scaling" / "full" / "evaluation" / f"seed-{seed}"
    config = {
        "name": "systems_scaling",
        "profile": "full",
        "rounds": 1,
        "seed_sets": {"tuning": [0], "evaluation": [100, 101]},
        "execution": {"driver": "run_systems_scaling"},
    }
    _write_jsonl(
        directory / "manifest.jsonl",
        [{"schema_version": 1, "seed": seed, "config": config}],
    )
    _write_jsonl(
        directory / "raw.jsonl",
        [
            {
                "round": 0,
                "metrics": {
                    "d": 32,
                    "n": 64,
                    "K": 5,
                    "I": 10,
                    "method": "batched_jacobi_cg",
                    "benchmark_grid": "advanced_cpu_grid",
                    "wall_time_seconds": 0.1,
                    "peak_host_memory_bytes": 2000,
                    "estimated_working_memory_bytes": 512,
                    "estimated_total_host_memory_bytes": 1024,
                    "curvature_vector_products": 1280,
                    "batch_operator_call_count": 4,
                    "equivalent_sample_cvp_count": 1280,
                    "sample_cvp_count": 1280,
                    "cg_iterations": 0,
                    "mean_explicit_relative_residual": 1e-10,
                    "max_explicit_relative_residual": 2e-10,
                    "predictive_width_relative_error": 0.0,
                },
            }
        ],
    )
    _write_jsonl(
        directory / "summary.jsonl",
        [
            {
                "experiment": "systems_scaling",
                "seed": seed,
                "record_count": 1,
                "synthetic_feasibility_benchmark": True,
                "synthetic_cpu_parameter_vector_benchmark": True,
                "benchmark_kind": "synthetic_cpu_parameter_vector_operator_benchmark",
                "accelerator_benchmark": False,
                "foundation_model_benchmark": False,
                "foundation_model_wall_clock_claim": False,
                "width_sandwich_violation_count": 0,
            }
        ],
    )


@pytest.fixture
def full_aggregate(tmp_path: Path) -> dict[str, object]:
    raw = tmp_path / "raw"
    _write_policy_run(raw, seed=100)
    _write_policy_run(raw, seed=101)
    return aggregate_results(raw)


def test_aggregate_computes_prefixes_and_student_t_intervals(
    full_aggregate: dict[str, object],
) -> None:
    assert full_aggregate["run_count"] == 2
    assert full_aggregate["all_groups_complete"] is True
    group = full_aggregate["groups"][0]
    by_horizon = {item["horizon"]: item for item in group["horizons"]}
    # Seed 100 has prefix regret 3; seed 101 has prefix regret 6.
    stats = by_horizon[2]["metrics"]["cumulative_pseudo_regret"]
    assert stats["n"] == 2
    assert stats["mean"] == pytest.approx(4.5)
    assert stats["ci95_half_width"] == pytest.approx(19.059, rel=1e-3)
    assert "Lambda_alg_T" in by_horizon[3]["theorem_components"]
    assert "runtime_seconds" in by_horizon[3]["runtime_components"]


def test_aggregate_emits_hash_bound_paired_method_differences(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    for seed in (100, 101):
        _write_policy_run(raw, seed=seed, method="dense_full", regret_scale=1.0)
        _write_policy_run(raw, seed=seed, method="diagonal", regret_scale=2.0)

    aggregate = aggregate_results(raw)
    assert aggregate["paired_comparison_count"] == 1
    paired = aggregate["paired_comparisons"][0]
    assert paired["method"] == "diagonal"
    assert paired["reference_method"] == "dense_full"
    assert paired["difference_direction"] == "method_minus_reference"
    assert paired["seeds"] == [100, 101]
    by_horizon = {item["horizon"]: item for item in paired["horizons"]}
    difference = by_horizon[2]["metrics"]["cumulative_pseudo_regret"]
    assert difference["mean"] == pytest.approx(4.5)
    assert difference["n"] == 2
    assert len(paired["inputs"]) == 12
    from experiments.logging_utils import canonical_json

    assert paired["input_set_sha256"] == hashlib.sha256(
        canonical_json(paired["inputs"]).encode("ascii")
    ).hexdigest()

    result = make_paper_artifacts(
        aggregate,
        derived_dir=tmp_path / "derived",
        table_path=tmp_path / "table.tex",
        figure_dir=tmp_path / "figures",
    )
    csv_text = (tmp_path / "derived" / "paper_results.csv").read_text(
        encoding="utf-8"
    )
    assert "paired_horizon" in csv_text
    assert "dense_full" in csv_text
    assert result["primary"] is True


def test_aggregate_provenance_sidecar_detects_raw_and_artifact_tampering(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    _write_policy_run(raw, seed=100)
    _write_policy_run(raw, seed=101)
    aggregate = aggregate_results(raw)
    artifact, sidecar = write_aggregate_with_provenance(
        aggregate, tmp_path / "derived" / "aggregate.json"
    )
    provenance = validate_aggregate_provenance_sidecar(artifact, sidecar)
    assert provenance["artifact_sha256"] == hashlib.sha256(
        artifact.read_bytes()
    ).hexdigest()
    assert provenance["input_set_sha256"] == aggregate["input_set_sha256"]
    assert provenance["inputs"] == aggregate["inputs"]

    raw_path = next(Path(item["path"]) for item in aggregate["inputs"] if item["path"].endswith("raw.jsonl"))
    raw_bytes = raw_path.read_bytes()
    raw_path.write_bytes(raw_bytes + b"\n")
    with pytest.raises(AggregationError, match="input digest"):
        validate_aggregate_provenance_sidecar(artifact, sidecar)
    raw_path.write_bytes(raw_bytes)

    artifact.write_text(artifact.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(AggregationError, match="artifact digest"):
        validate_aggregate_provenance_sidecar(artifact, sidecar)


def test_aggregate_rejects_nonexecuted_and_overlapping_provenance(tmp_path: Path) -> None:
    nonexecuted = tmp_path / "nonexecuted"
    _write_policy_run(nonexecuted, seed=100, executed=False)
    with pytest.raises(AggregationError, match="executed|non-executed"):
        aggregate_results(nonexecuted)

    overlapping = tmp_path / "overlap"
    _write_policy_run(overlapping, seed=100, overlap=True)
    with pytest.raises(AggregationError, match="overlap"):
        aggregate_results(overlapping)


def test_offline_common_trajectory_is_aggregated_separately_and_never_as_policy(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    for seed in (100, 101):
        _write_policy_run(raw, seed=seed)
        digest = f"trajectory-{seed}"
        _write_offline_operator_run(
            raw, seed=seed, operator="full", trajectory_digest=digest
        )
        _write_offline_operator_run(
            raw, seed=seed, operator="diagonal", trajectory_digest=digest
        )

    aggregate = aggregate_results(raw)
    assert aggregate["run_count"] == 2
    assert aggregate["artifact_run_count"] == 6
    assert aggregate["offline_diagnostic_run_count"] == 4
    assert aggregate["offline_diagnostic_group_count"] == 2
    assert aggregate["offline_common_trajectory_validated"] is True
    assert all(
        group["executed_policy"] is False
        and group["causal_regret_claim"] is False
        and group["regret_reported"] is False
        and group["inputs"]
        for group in aggregate["offline_diagnostic_groups"]
    )
    assert all(
        group["experiment"] != "operator_ablation" for group in aggregate["groups"]
    )

    make_paper_artifacts(
        aggregate,
        derived_dir=tmp_path / "derived",
        table_path=tmp_path / "table.tex",
        figure_dir=tmp_path / "figures",
    )
    csv_text = (tmp_path / "derived" / "paper_results.csv").read_text(
        encoding="utf-8"
    )
    assert "offline_summary" in csv_text
    assert "offline_noncausal_not_executed_policy" in csv_text


def test_benchmark_diagnostics_stream_to_compact_seed_level_summaries(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    for seed in (100, 101):
        _write_cg_benchmark_run(raw, seed=seed)
        _write_systems_benchmark_run(raw, seed=seed)

    aggregate = aggregate_results(raw)
    assert aggregate["event"] == "diagnostic_aggregate"
    assert aggregate["run_count"] == 0
    assert aggregate["benchmark_diagnostic_run_count"] == 4
    assert aggregate["benchmark_diagnostic_group_count"] == 3
    cg_audit = next(
        audit
        for audit in aggregate["benchmark_diagnostic_audits"]
        if audit["experiment"] == "cg_accuracy"
    )
    assert cg_audit["all_target_residual_sandwich_optimism_violations_zero"] is True
    assert cg_audit["warm_start_cells"] == 1
    comparison = cg_audit["warm_start_comparisons"][0]
    assert comparison["mean_cg_iterations_difference"]["mean"] == -1.0
    assert comparison["warm_start_lowered_mean_iterations"] is True
    assert comparison["warm_start_iteration_reduction_ci_excludes_zero"] is True
    systems_audit = next(
        audit
        for audit in aggregate["benchmark_diagnostic_audits"]
        if audit["experiment"] == "systems_scaling"
    )
    assert systems_audit["all_width_sandwich_checks_hold"] is True
    systems_group = next(
        group
        for group in aggregate["benchmark_diagnostic_groups"]
        if group["experiment"] == "systems_scaling"
    )
    assert systems_group["benchmark_kind"] == (
        "synthetic_cpu_parameter_vector_operator_benchmark"
    )
    assert systems_group["benchmark_grid"] == "advanced_cpu_grid"
    assert systems_group["summary_metrics"]["batch_operator_call_count"]["mean"] == 4.0
    assert systems_group["summary_metrics"]["max_explicit_relative_residual"][
        "mean"
    ] == 2e-10
    assert all(group["inputs"] for group in aggregate["benchmark_diagnostic_groups"])

    make_paper_artifacts(
        aggregate,
        derived_dir=tmp_path / "derived",
        output_stem="diagnostics",
        table_path=tmp_path / "table.tex",
        figure_dir=tmp_path / "figures",
        primary=False,
    )
    csv_text = (tmp_path / "derived" / "diagnostics.csv").read_text(
        encoding="utf-8"
    )
    assert "benchmark_paired" in csv_text
    assert "warm_minus_zero" in csv_text
    assert "width_sandwich_violation_count" in csv_text
    table_text = (tmp_path / "table.tex").read_text(encoding="ascii")
    assert "CG accuracy diagnostic" in table_text
    assert "10 & 0.1 & none" in table_text
    assert "All target, residual-certificate" in table_text
    assert "Systems scaling diagnostic" in table_text
    assert r"32 & batched\_jacobi\_cg & 64 & 5 & 10" in table_text
    assert "Working memory (KiB)" in table_text
    assert "All logged width-sandwich checks hold" in table_text
    assert "Regret & Reported RHS" not in table_text


def test_artifact_generation_and_primary_gate(
    tmp_path: Path, full_aggregate: dict[str, object]
) -> None:
    derived = tmp_path / "derived"
    table = tmp_path / "tables" / "results.tex"
    result = make_paper_artifacts(
        full_aggregate,
        derived_dir=derived,
        table_path=table,
        figure_dir=tmp_path / "figures",
    )
    artifacts = [Path(path) for path in result["artifacts"]]
    assert derived / "paper_results.json" in artifacts
    assert derived / "paper_results.csv" in artifacts
    assert table in artifacts
    assert "Student-t" in (derived / "paper_results.json").read_text(encoding="utf-8")
    assert "Regret" in table.read_text(encoding="ascii")
    for artifact, sidecar_name in zip(artifacts, result["provenance_sidecars"], strict=True):
        sidecar = json.loads(Path(sidecar_name).read_text(encoding="utf-8"))
        assert sidecar["artifact_sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
        assert sidecar["inputs"]

    smoke = copy.deepcopy(full_aggregate)
    smoke["profiles"] = ["smoke"]
    for group in smoke["groups"]:
        group["profile"] = "smoke"
    with pytest.raises(ArtifactError, match="smoke"):
        validate_primary_aggregate(smoke)

    incomplete = copy.deepcopy(full_aggregate)
    incomplete["groups"][0]["complete_declared_seed_set"] = False
    with pytest.raises(ArtifactError, match="missing"):
        validate_primary_aggregate(incomplete)

    legacy = copy.deepcopy(full_aggregate)
    legacy["schema_version"] = 0
    with pytest.raises(ArtifactError, match="legacy"):
        validate_primary_aggregate(legacy)


def test_nonlinear_aggregate_emits_pdf_and_png(
    tmp_path: Path, full_aggregate: dict[str, object]
) -> None:
    nonlinear = copy.deepcopy(full_aggregate)
    nonlinear["experiments"] = ["nonlinear_audit"]
    group = nonlinear["groups"][0]
    group["experiment"] = "nonlinear_audit"
    group["method"] = "aggressive"
    group["variant"] = {"drift_name": "aggressive", "center": "original"}
    final = group["horizons"][-1]
    final["metrics"]["max_diagnostic_u_t"] = {
        "n": 2,
        "mean": 2.0,
        "standard_deviation": 0.1,
        "standard_error": 0.07,
        "t_critical": 12.706,
        "ci95_half_width": 0.2,
        "ci95_low": 1.8,
        "ci95_high": 2.2,
        "ci95": [1.8, 2.2],
    }
    for metric in ("optimism_violation_rate", "E_T", "psi_t", "V_alg_T"):
        final["metrics"][metric] = copy.deepcopy(
            final["metrics"]["max_diagnostic_u_t"]
        )
    result = make_paper_artifacts(
        nonlinear,
        derived_dir=tmp_path / "derived",
        table_path=tmp_path / "table.tex",
        figure_dir=tmp_path / "figures",
    )
    assert str(tmp_path / "figures" / "theory_factor_drift.pdf") in result["artifacts"]
    png = tmp_path / "figures" / "theory_factor_drift.png"
    assert str(png) in result["artifacts"]
    from matplotlib.image import imread

    pixels = imread(png)
    assert pixels.shape[1] > 1.5 * pixels.shape[0]
    assert float(pixels[..., :3].std()) > 0.05
