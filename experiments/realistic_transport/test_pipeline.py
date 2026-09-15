from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from experiments.realistic_transport.aggregate import (
    aggregate_profile,
    AggregateError,
    write_statistics_csv,
)
from experiments.realistic_transport.artifacts import _render_validated_artifacts
from experiments.realistic_transport.configuration import (
    config_digest,
    EXPECTED_METHODS,
    EXPECTED_TASKS,
    load_config,
    seed_set,
)
from experiments.realistic_transport.data import prepare_loaded_dataset
from experiments.realistic_transport.io import (
    _rewrite_run_fixture,
    validate_run_directory,
    write_failure,
    write_run,
)
from experiments.realistic_transport.study import run_profile


CONFIG = Path("experiments/configs/realistic_transport_covtype.yaml")


def _smoke_artifact(path: Path) -> Path:
    generator = np.random.default_rng(991)
    features = generator.normal(size=(401, 20))
    labels = np.arange(401, dtype=np.int64) % 7
    prepare_loaded_dataset(
        features,
        labels,
        dataset_name="test_smoke",
        destination=path,
        smoke_only=True,
        fixture_only=True,
    )
    return path


def test_realistic_configuration_freezes_all_grids() -> None:
    config = load_config(CONFIG, "smoke")
    assert tuple(config["methods"]) == EXPECTED_METHODS
    assert tuple(config["tasks"]) == EXPECTED_TASKS
    assert seed_set(config, "development") == (0, 1, 2)
    assert seed_set(config, "pilot") == tuple(range(200, 210))
    all_seeds = [
        set(seed_set(config, name))
        for name in ("development", "tuning", "evaluation", "pilot")
    ]
    assert sum(len(values) for values in all_seeds) == len(set().union(*all_seeds))
    assert config_digest(config) == (
        "4249a22156de864b7a15833f734a0cae6520ad95bacc8a4b4a30eca38118ed7d"
    )


def test_single_cell_study_writes_a_strict_self_describing_run(tmp_path) -> None:
    artifact = _smoke_artifact(tmp_path / "smoke.npz")
    raw_root = tmp_path / "raw"
    result = run_profile(
        config_path=CONFIG,
        profile="smoke",
        prepared_artifact=artifact,
        output_root=raw_root,
        methods=("greedy_corrected",),
        seeds=(0,),
    )
    assert result["completed_cells"] == 3
    assert result["failed_cells"] == 0
    worker_pids = set()
    for task in EXPECTED_TASKS:
        validated = validate_run_directory(
            raw_root / "smoke" / task / "greedy_corrected" / "seed-0"
        )
        assert validated["round_count"] == 32
        assert validated["manifest"]["prepared_data"]["smoke_only"]
        assert validated["manifest"]["prepared_data"]["fixture_only"]
        assert validated["manifest"]["evidence_role"] == "smoke_only"
        assert validated["manifest"]["data_authentication"]["status"] == (
            "smoke_only_not_approved"
        )
        execution = validated["manifest"]["runtime"]["execution"]
        worker_pids.add(execution["worker_pid"])
        assert execution["execution_model"] == (
            "sequential_parent_with_fresh_spawned_process_per_cell"
        )
        assert execution["thread_control"]["verified"]
        assert execution["thread_control"]["active_pools_before"]
        assert all(
            pool["num_threads"] == 1
            for pool in execution["thread_control"]["active_pools_before"]
            if pool["user_api"] in {"blas", "openmp"}
        )
        assert validated["summary"]["policy_memory_measurement"]["isolation"] == (
            "one_fresh_spawned_process_per_cell"
        )
        assert not validated["summary"][
            "floating_point_checks_are_verified_certificates"
        ]
    assert len(worker_pids) == len(EXPECTED_TASKS)


def test_strict_aggregate_rejects_an_incomplete_cartesian_product(tmp_path) -> None:
    with pytest.raises(AggregateError, match="raw grid mismatch"):
        aggregate_profile(
            config_path=CONFIG,
            profile="smoke",
            raw_root=tmp_path / "empty",
            output_path=tmp_path / "aggregate.json",
        )


def test_run_validation_rejects_failure_sidecar_and_round_count_corruption(
    tmp_path: Path,
) -> None:
    failure_directory = (
        tmp_path / "raw/smoke/covtype_label_bandit/greedy_corrected/seed-0"
    )
    write_failure(
        failure_directory,
        context={"profile": "smoke"},
        error=RuntimeError("fixture failure"),
    )
    with pytest.raises(AggregateError, match="failures=1"):
        aggregate_profile(
            config_path=CONFIG,
            profile="smoke",
            raw_root=tmp_path / "raw",
            output_path=tmp_path / "aggregate.json",
        )

    run = tmp_path / "run"
    write_run(
        run,
        manifest={"status": "completed"},
        rounds=({"round": 1},),
        summary={"status": "completed", "rounds": 1},
    )
    (run / "summary.json").write_text('{"rounds":1,"status":"changed"}\n')
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        validate_run_directory(run)

    _rewrite_run_fixture(
        run,
        manifest={"status": "completed"},
        rounds=({"round": 1},),
        summary={"status": "completed", "rounds": 2},
    )
    with pytest.raises(ValueError, match="summary round count mismatch"):
        validate_run_directory(run)


def test_validated_artifact_rendering_is_byte_deterministic(tmp_path) -> None:
    aggregate = {
        "schema_version": 1,
        "profile": "smoke",
        "publication_evidence": False,
        "config_digest": "0" * 64,
        "expected_cell_count": 1,
        "accepted_cell_count": 1,
        "prefixes": [1],
        "raw_input_inventory": [],
        "raw_input_inventory_sha256": "1" * 64,
        "common_provenance": {},
        "run_level_metrics": [],
        "paired_primary_comparisons": [],
        "rank_tolerance_effects": [],
        "method_statistics": [
            {
                "task": "covtype_label_bandit",
                "method": "greedy_corrected",
                "prefix": 1,
                "seed_count": 1,
                "metrics": {
                    "cumulative_regret": {
                        "mean": 0.8,
                        "standard_error": 0.0,
                        "median": 0.8,
                    },
                    "algorithm_seconds": {"mean": 0.1},
                    "peak_rss_bytes": {"mean": 1048576.0},
                },
                "reference_confidence": {
                    "proportion": 0.0,
                    "clopper_pearson_95": {"ci_low": 0.0, "ci_high": 0.975},
                },
                "method_optimism": {
                    "proportion": 0.0,
                    "clopper_pearson_95": {"ci_low": 0.0, "ci_high": 0.975},
                },
            }
        ],
    }
    first_root = tmp_path / "review-first"
    first = _render_validated_artifacts(
        aggregate,
        first_root,
        accepted_aggregate_sha256="2" * 64,
    )
    first_bytes = {
        path.relative_to(first_root): path.read_bytes()
        for path in first_root.rglob("*")
        if path.is_file()
    }
    second_root = tmp_path / "review-second"
    second = _render_validated_artifacts(
        aggregate,
        second_root,
        accepted_aggregate_sha256="2" * 64,
    )
    second_bytes = {
        path.relative_to(second_root): path.read_bytes()
        for path in second_root.rglob("*")
        if path.is_file()
    }
    assert first == second
    assert first_bytes == second_bytes


def test_statistics_writer_refuses_to_overwrite_existing_evidence(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "STATISTICAL_RESULTS.csv"
    sentinel = b"historical evidence\n"
    destination.write_bytes(sentinel)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_statistics_csv({"method_statistics": []}, destination)
    assert destination.read_bytes() == sentinel
    assert not destination.with_name(destination.name + ".sha256").exists()
