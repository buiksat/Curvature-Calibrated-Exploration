from __future__ import annotations

import copy
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from experiments.config import load_config
from experiments.logging_utils import canonical_json
from experiments.make_wheel_benchmark_artifacts import build_artifact
from experiments.raw_artifact_bundle import (
    RawArtifactBundleError,
    create_wheel_bundle,
    extract_bundle,
    verify_bundle,
)
from experiments.run_wheel_benchmark import METHODS, run_experiment


SOURCE_CONFIG = Path("experiments/configs/wheel_benchmark.yaml")


@dataclass(frozen=True)
class TinyWheelChain:
    config: dict[str, Any]
    config_path: Path
    raw_root: Path


def _write_resolved_config(config: dict[str, Any], path: Path) -> None:
    header_names = {"schema_version", "name", "description"}
    document = {name: copy.deepcopy(config[name]) for name in header_names}
    document["base"] = {
        name: copy.deepcopy(value)
        for name, value in config.items()
        if name not in header_names | {"profile"}
    }
    document["profiles"] = {"smoke": {}, "full": {}}
    path.write_text(canonical_json(document) + "\n", encoding="ascii")


@pytest.fixture(scope="module")
def tiny_wheel_chain(tmp_path_factory: pytest.TempPathFactory) -> TinyWheelChain:
    root = tmp_path_factory.mktemp("wheel-raw-bundle")
    config = copy.deepcopy(load_config(SOURCE_CONFIG, profile="smoke"))
    config.update(
        {
            "rounds": 4,
            "tuning_rounds": 4,
            "horizons": [2, 4],
            "ridge_grid": [1.0],
            "bonus_grid": [0.5],
            "seed_sets": {"tuning": [2000], "evaluation": [3000]},
        }
    )
    config_path = root / "tiny_wheel.yaml"
    _write_resolved_config(config, config_path)
    resolved = load_config(config_path, profile="smoke")
    assert resolved == config

    raw_root = root / "raw"
    selection = raw_root / "smoke" / "tuning_selection.json"
    tuning = run_experiment(
        config,
        seed_set="tuning",
        output_root=raw_root,
        tuning_selection=selection,
        workers=1,
    )
    evaluation = run_experiment(
        config,
        seed_set="evaluation",
        output_root=raw_root,
        tuning_selection=selection,
        workers=1,
    )
    assert len(tuning) == len(evaluation) == 4 * len(METHODS)
    return TinyWheelChain(config=config, config_path=config_path, raw_root=raw_root)


def test_wheel_bundle_is_deterministic_extractable_and_rebuildable(
    tiny_wheel_chain: TinyWheelChain,
    tmp_path: Path,
) -> None:
    bundles = (tmp_path / "first.tar.gz", tmp_path / "second.tar.gz")
    results = [
        create_wheel_bundle(
            tiny_wheel_chain.config,
            config_path=tiny_wheel_chain.config_path,
            profile="smoke",
            raw_root=tiny_wheel_chain.raw_root,
            bundle_path=bundle,
        )
        for bundle in bundles
    ]
    assert bundles[0].read_bytes() == bundles[1].read_bytes()
    assert results[0]["bundle_sha256"] == results[1]["bundle_sha256"]
    expected_run_count = 4 * len(METHODS)
    expected_file_count = 2 * expected_run_count * 3 + 1
    assert results[0]["validated_tuning_run_count"] == expected_run_count
    assert results[0]["validated_evaluation_run_count"] == expected_run_count
    assert results[0]["file_count"] == expected_file_count

    verified = verify_bundle(bundles[0])
    assert verified["status"] == "verified"
    extraction_root = tmp_path / "extracted"
    extracted = extract_bundle(bundles[0], destination=extraction_root)
    assert extracted["extracted_file_count"] == expected_file_count

    restored_profile = extraction_root / "wheel_benchmark" / "smoke"
    report = build_artifact(
        config_path=tiny_wheel_chain.config_path,
        raw_root=restored_profile / "evaluation",
        selection_path=restored_profile / "tuning_selection.json",
        profile="smoke",
    )
    assert report["profile"] == "smoke"
    assert report["evaluation_outcomes_used_for_tuning"] is False
    assert len(report["seed_level_results"]) == expected_run_count


def test_wheel_bundle_rejects_extra_files_and_selection_hash_drift(
    tiny_wheel_chain: TinyWheelChain,
    tmp_path: Path,
) -> None:
    copied = tmp_path / "extra"
    shutil.copytree(tiny_wheel_chain.raw_root, copied)
    (copied / "smoke" / "unexpected.txt").write_text("extra\n", encoding="ascii")
    with pytest.raises(RawArtifactBundleError, match="inventory mismatch"):
        create_wheel_bundle(
            tiny_wheel_chain.config,
            config_path=tiny_wheel_chain.config_path,
            profile="smoke",
            raw_root=copied,
            bundle_path=tmp_path / "extra.tar.gz",
        )

    copied = tmp_path / "selection-drift"
    shutil.copytree(tiny_wheel_chain.raw_root, copied)
    manifest_path = (
        copied
        / "smoke"
        / "evaluation"
        / "delta-0p5"
        / "linucb"
        / "seed-3000"
        / "manifest.jsonl"
    )
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    manifest["config"]["execution"]["tuning_selection_sha256"] = "0" * 64
    manifest_path.write_text(canonical_json(manifest) + "\n", encoding="ascii")
    with pytest.raises(RawArtifactBundleError, match="manifest mismatch"):
        create_wheel_bundle(
            tiny_wheel_chain.config,
            config_path=tiny_wheel_chain.config_path,
            profile="smoke",
            raw_root=copied,
            bundle_path=tmp_path / "selection-drift.tar.gz",
        )


def test_wheel_inventory_records_tuning_only_selection_and_source_hashes(
    tiny_wheel_chain: TinyWheelChain,
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "scope.tar.gz"
    result = create_wheel_bundle(
        tiny_wheel_chain.config,
        config_path=tiny_wheel_chain.config_path,
        profile="smoke",
        raw_root=tiny_wheel_chain.raw_root,
        bundle_path=bundle,
    )
    inventory = json.loads(Path(result["inventory"]).read_text(encoding="ascii"))
    assert inventory["tuning_evaluation_seeds_disjoint"] is True
    assert inventory["validation"]["evaluation_outcomes_used_for_selection"] is False
    assert inventory["validation"]["tuning_selection_recomputed_from_tuning_only"]
    assert set(inventory["source_artifact_hashes"]) == {
        "experiments/logging_utils.py",
        "experiments/make_wheel_benchmark_artifacts.py",
        "experiments/run_wheel_benchmark.py",
        "experiments/wheel_environment.py",
    }
