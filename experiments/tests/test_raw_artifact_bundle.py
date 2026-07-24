from __future__ import annotations

import copy
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from experiments.config import config_digest, load_config
from experiments.logging_utils import canonical_json
from experiments.make_scaled_tanh_instantiation_artifacts import build_aggregate
from experiments.raw_artifact_bundle import (
    RawArtifactBundleError,
    create_scaled_tanh_bundle,
    extract_bundle,
    verify_bundle,
)
from experiments.run_scaled_tanh_instantiation import (
    build_optimizer_selection,
    run_evaluation,
)
from experiments.scaled_tanh_config_compat import (
    CURRENT_DESCRIPTION,
    LEGACY_DESCRIPTION,
)


SOURCE_CONFIG = Path("experiments/configs/scaled_tanh_instantiation.yaml")


@dataclass(frozen=True)
class TinyRawChain:
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
def tiny_raw_chain(tmp_path_factory: pytest.TempPathFactory) -> TinyRawChain:
    root = tmp_path_factory.mktemp("raw-artifact-bundle")
    config = copy.deepcopy(load_config(SOURCE_CONFIG, profile="smoke"))
    config.update(
        {
            "rounds": 4,
            "context_count": 8,
            "horizons": [4],
            "width_ratios": [1.0],
            "methods": ["exact_current_relative", "full_cg_relative"],
            "bootstrap_resamples": 10,
            "seed_sets": {
                "development": [42],
                "tuning": [0],
                "evaluation": [200],
            },
            "optimizer_selection": {
                "method": "exact_current_relative",
                "damping_candidates": [float(config["damping"])],
                "horizons": [4],
                "width_ratios": [1.0],
                "criterion": "single-candidate bundle test selection",
                "evaluation_metrics_read": False,
            },
        }
    )
    config_path = root / "tiny_scaled_tanh.yaml"
    _write_resolved_config(config, config_path)
    resolved = load_config(config_path, profile="smoke")
    assert resolved == config

    raw_root = root / "raw"
    selection = raw_root / "smoke" / "optimizer_selection.json"
    build_optimizer_selection(
        config,
        profile="smoke",
        selection_path=selection,
        overwrite=False,
    )
    result = run_evaluation(
        config,
        profile="smoke",
        output_root=raw_root,
        selection_path=selection,
        overwrite=False,
        workers=1,
    )
    assert result["run_count"] == 2
    return TinyRawChain(config=config, config_path=config_path, raw_root=raw_root)


def test_bundle_is_deterministic_verifiable_extractable_and_rebuildable(
    tiny_raw_chain: TinyRawChain,
    tmp_path: Path,
) -> None:
    bundles = (tmp_path / "first.tar.gz", tmp_path / "second.tar.gz")
    results = [
        create_scaled_tanh_bundle(
            tiny_raw_chain.config,
            config_path=tiny_raw_chain.config_path,
            profile="smoke",
            raw_root=tiny_raw_chain.raw_root,
            bundle_path=bundle,
        )
        for bundle in bundles
    ]
    assert bundles[0].read_bytes() == bundles[1].read_bytes()
    assert results[0]["bundle_sha256"] == results[1]["bundle_sha256"]
    assert results[0]["validated_run_count"] == 2
    assert results[0]["file_count"] == 14

    verified = verify_bundle(bundles[0])
    assert verified["status"] == "verified"
    assert verified["file_count"] == 14
    extraction_root = tmp_path / "extracted"
    extracted = extract_bundle(bundles[0], destination=extraction_root)
    assert extracted["status"] == "extracted"
    assert extracted["extracted_file_count"] == 14

    restored_raw = extraction_root / "scaled_tanh_instantiation"
    restored_selection = restored_raw / "smoke" / "optimizer_selection.json"
    report, inputs = build_aggregate(
        tiny_raw_chain.config,
        profile="smoke",
        raw_root=restored_raw,
        selection_path=restored_selection,
    )
    assert report["validated_run_count"] == report["expected_run_count"] == 2
    # Selection/runs plus runner and two derived-artifact source hashes.
    assert len(inputs) == 17


def test_bundle_rejects_unexpected_raw_files_and_archive_corruption(
    tiny_raw_chain: TinyRawChain,
    tmp_path: Path,
) -> None:
    copied = tmp_path / "raw"
    shutil.copytree(tiny_raw_chain.raw_root, copied)
    unexpected = copied / "smoke" / "unexpected.txt"
    unexpected.write_text("not preregistered\n", encoding="ascii")
    with pytest.raises(RawArtifactBundleError, match="inventory mismatch"):
        create_scaled_tanh_bundle(
            tiny_raw_chain.config,
            config_path=tiny_raw_chain.config_path,
            profile="smoke",
            raw_root=copied,
            bundle_path=tmp_path / "unexpected.tar.gz",
        )

    bundle = tmp_path / "corrupt.tar.gz"
    create_scaled_tanh_bundle(
        tiny_raw_chain.config,
        config_path=tiny_raw_chain.config_path,
        profile="smoke",
        raw_root=tiny_raw_chain.raw_root,
        bundle_path=bundle,
    )
    bundle.write_bytes(bundle.read_bytes() + b"corruption")
    with pytest.raises(RawArtifactBundleError, match="SHA-256 sidecar"):
        verify_bundle(bundle)


def test_inventory_records_smoke_scope_and_complete_selection(
    tiny_raw_chain: TinyRawChain,
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "scope.tar.gz"
    result = create_scaled_tanh_bundle(
        tiny_raw_chain.config,
        config_path=tiny_raw_chain.config_path,
        profile="smoke",
        raw_root=tiny_raw_chain.raw_root,
        bundle_path=bundle,
    )
    inventory = json.loads(Path(result["inventory"]).read_text(encoding="ascii"))
    assert inventory["evidence_scope"] == (
        "smoke-only engineering verification; not main-paper evidence"
    )
    assert inventory["tuning_evaluation_seeds_disjoint"] is True
    assert inventory["execution_config_digest"] == inventory["config_digest"]
    assert inventory["config_wording_migration"]["applied"] is False
    assert inventory["expected_run_count"] == inventory["validated_run_count"] == 2
    assert inventory["validation"] == {
        "every_expected_manifest_sidecar_and_identity": True,
        "every_summary_and_round_archive_sidecar": True,
        "exact_profile_file_set": True,
        "manifest_summary_and_round_hash_bindings": True,
        "round_archives_readable_without_object_arrays": True,
        "tuning_selection_sidecar_and_semantics": True,
    }


def test_bundle_accepts_only_known_description_migration(
    tiny_raw_chain: TinyRawChain, tmp_path: Path
) -> None:
    legacy_config = copy.deepcopy(tiny_raw_chain.config)
    legacy_config["description"] = LEGACY_DESCRIPTION
    legacy_raw = tmp_path / "legacy-raw"
    legacy_selection = legacy_raw / "smoke" / "optimizer_selection.json"
    build_optimizer_selection(
        legacy_config,
        profile="smoke",
        selection_path=legacy_selection,
        overwrite=False,
    )
    run_evaluation(
        legacy_config,
        profile="smoke",
        output_root=legacy_raw,
        selection_path=legacy_selection,
        overwrite=False,
        workers=1,
    )

    current_config = copy.deepcopy(tiny_raw_chain.config)
    assert current_config["description"] == CURRENT_DESCRIPTION
    bundle = tmp_path / "legacy-description.tar.gz"
    result = create_scaled_tanh_bundle(
        current_config,
        config_path=tiny_raw_chain.config_path,
        profile="smoke",
        raw_root=legacy_raw,
        bundle_path=bundle,
    )
    inventory = json.loads(Path(result["inventory"]).read_text(encoding="ascii"))
    assert inventory["config_digest"] == config_digest(current_config)
    assert inventory["execution_config_digest"] == config_digest(legacy_config)
    assert inventory["config_wording_migration"]["applied"] is True
    assert inventory["execution_config"] == legacy_config
    assert verify_bundle(bundle)["status"] == "verified"
    report, _ = build_aggregate(
        current_config,
        profile="smoke",
        raw_root=legacy_raw,
        selection_path=legacy_selection,
    )
    assert report["config_digest"] == config_digest(current_config)
    assert report["execution_config_digest"] == config_digest(legacy_config)
    assert report["config_wording_migration"]["applied"] is True

    drifted = copy.deepcopy(current_config)
    drifted["feature_bound"] = float(drifted["feature_bound"]) + 0.1
    drifted_path = tmp_path / "drifted.yaml"
    _write_resolved_config(drifted, drifted_path)
    with pytest.raises(
        RawArtifactBundleError, match="differs by more than.*description"
    ):
        create_scaled_tanh_bundle(
            drifted,
            config_path=drifted_path,
            profile="smoke",
            raw_root=legacy_raw,
            bundle_path=tmp_path / "drifted.tar.gz",
        )
