from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from experiments.realistic_transport.aggregate import AggregateError, aggregate_profile
from experiments.realistic_transport.artifacts import generate_artifacts
from experiments.realistic_transport.configuration import (
    EXPECTED_METHODS,
    EXPECTED_TASKS,
    load_config,
    seed_set,
)
from experiments.realistic_transport.data import prepare_loaded_dataset
from experiments.realistic_transport.io import validate_run_directory
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
    for task in EXPECTED_TASKS:
        validated = validate_run_directory(
            raw_root / "smoke" / task / "greedy_corrected" / "seed-0"
        )
        assert validated["round_count"] == 32
        assert validated["manifest"]["prepared_data"]["smoke_only"]
        assert not validated["summary"][
            "floating_point_checks_are_verified_certificates"
        ]


def test_strict_aggregate_rejects_an_incomplete_cartesian_product(tmp_path) -> None:
    with pytest.raises(AggregateError, match="raw grid mismatch"):
        aggregate_profile(
            config_path=CONFIG,
            profile="smoke",
            raw_root=tmp_path / "empty",
            output_path=tmp_path / "aggregate.json",
        )


def test_artifact_generation_is_byte_deterministic(tmp_path) -> None:
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
    aggregate_path = tmp_path / "aggregate.json"
    aggregate_path.write_text(json.dumps(aggregate), encoding="utf-8")
    review = tmp_path / "review"
    first = generate_artifacts(aggregate_path=aggregate_path, review_root=review)
    first_bytes = {
        path.relative_to(review): path.read_bytes()
        for path in review.rglob("*")
        if path.is_file()
    }
    second = generate_artifacts(aggregate_path=aggregate_path, review_root=review)
    second_bytes = {
        path.relative_to(review): path.read_bytes()
        for path in review.rglob("*")
        if path.is_file()
    }
    assert first == second
    assert first_bytes == second_bytes
