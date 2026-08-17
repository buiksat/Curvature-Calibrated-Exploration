from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from experiments.aggregate_linear_audit import (
    LinearAggregationError,
    _student_t_interval,
    aggregate_linear_audit,
)
from experiments.artifact_utils import (
    validate_aggregate_provenance_sidecar,
    write_aggregate_with_provenance,
)
from experiments.config import config_digest
from experiments.make_certification_audit import generate
from experiments.make_linear_bound_artifact import derive
from experiments.run_linear_audit import FEATURE_DIMENSION, SUPPORTED_METHODS
from experiments.run_linear_study import run_linear_study


def _config() -> dict[str, object]:
    return {
        "schema_version": 1,
        "name": "linear_audit",
        "profile": "full",
        "rounds": 4,
        "horizons": [2, 4, 8],
        "tuning_rounds": 2,
        "methods": list(SUPPORTED_METHODS),
        "comparisons": ["fixed_reference", "validation_tuned"],
        "ridge": 1.0,
        "bonus_scale": 1.0,
        "confidence": {"delta": 0.05, "bonus_scale": 1.0},
        "curvature": {
            "window_size": 2,
            "subsample_size": 2,
            "lanczos_rank": 2,
            "refresh_period": 2,
        },
        "cg": {"tolerance": 0.05, "max_iterations": 2 * FEATURE_DIMENSION},
        "tuning_grid": {"ridge": [1.0], "bonus_scale": [1.0]},
        "seed_sets": {"tuning": [0], "evaluation": [100]},
    }


def test_linear_study_aggregates_into_retained_consumers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config()
    raw_root = tmp_path / "raw"
    run_linear_study(config, raw_root, overwrite=False)
    config_path = tmp_path / "linear_audit.json"
    config_path.write_text(json.dumps(config, sort_keys=True) + "\n", encoding="ascii")

    aggregate = aggregate_linear_audit(
        config,
        raw_root,
        profile="full",
        config_path=config_path,
    )
    assert aggregate["event"] == "executed_policy_aggregate"
    assert aggregate["run_count"] == 2 * len(SUPPORTED_METHODS)
    assert aggregate["group_count"] == 2 * len(SUPPORTED_METHODS)
    assert aggregate["fresh_tuning_selection_validated"] is True
    assert {record["horizon"] for record in aggregate["groups"][0]["horizons"]} == {
        2,
        4,
    }

    aggregate_path, sidecar = write_aggregate_with_provenance(
        aggregate, tmp_path / "linear_audit_full.json"
    )
    validate_aggregate_provenance_sidecar(aggregate_path, sidecar)

    monkeypatch.setattr(
        "experiments.make_certification_audit.load_config",
        lambda path, profile: copy.deepcopy(config),
    )
    certification = generate(
        config_path,
        raw_root / "full" / "selection.json",
        raw_root / "full" / "evaluation",
        aggregate_path,
        tmp_path / "certification.json",
    )
    assert certification["scope"]["primary_policy_count"] == 14
    bound = derive(aggregate, certification)
    assert bound["rows"]
    assert {row["horizon"] for row in bound["rows"]} == {2, 4}

    manifest_path = (
        raw_root
        / "full"
        / "evaluation"
        / "fixed_reference"
        / "dense_full"
        / "seed-100"
        / "manifest.jsonl"
    )
    original_manifest = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(original_manifest)
    del manifest["config_digest"]
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="ascii")
    with pytest.raises(LinearAggregationError, match="config digest mismatch"):
        aggregate_linear_audit(config, raw_root, profile="full")
    manifest_path.write_text(original_manifest, encoding="utf-8")

    manifest = json.loads(original_manifest)
    manifest["config"]["curvature"]["refresh_period"] = 99
    manifest["config_digest"] = config_digest(manifest["config"])
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="ascii")
    with pytest.raises(LinearAggregationError, match="manifest config mismatch"):
        aggregate_linear_audit(config, raw_root, profile="full")
    manifest_path.write_text(original_manifest, encoding="utf-8")

    selection_path = raw_root / "full" / "selection.json"
    original_selection = selection_path.read_text(encoding="utf-8")
    selection = json.loads(original_selection)
    selection["candidates"]["dense_full"] = []
    selection_path.write_text(json.dumps(selection) + "\n", encoding="ascii")
    with pytest.raises(LinearAggregationError, match="candidate grid is incomplete"):
        aggregate_linear_audit(config, raw_root, profile="full")
    selection_path.write_text(original_selection, encoding="utf-8")

    raw_path = (
        raw_root
        / "full"
        / "evaluation"
        / "fixed_reference"
        / "dense_full"
        / "seed-100"
        / "raw.jsonl"
    )
    records = [json.loads(line) for line in raw_path.read_text().splitlines()]
    del records[-1]["metrics"]["theorem_rhs"]
    raw_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="ascii",
    )
    with pytest.raises(LinearAggregationError, match="raw theorem_rhs"):
        aggregate_linear_audit(config, raw_root, profile="full")


def test_student_t_interval_uses_seed_as_experimental_unit() -> None:
    interval = _student_t_interval([3.0, 6.0])
    assert interval["n"] == 2
    assert interval["mean"] == 4.5
    assert interval["ci95_half_width"] == pytest.approx(19.059, rel=1e-4)
