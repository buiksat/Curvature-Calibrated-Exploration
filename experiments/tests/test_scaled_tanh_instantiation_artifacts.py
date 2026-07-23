from __future__ import annotations

import copy
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from matplotlib import pyplot as plt

from experiments.artifact_utils import (
    sha256_file,
    validate_sha256_sidecar,
    write_json_artifact,
)
from experiments.config import load_config
from experiments.make_scaled_tanh_instantiation_artifacts import (
    ScaledTanhArtifactError,
    _add_scope_banner,
    _trajectory_interval,
    build_aggregate,
    make_artifacts,
)
from experiments.run_scaled_tanh_instantiation import (
    build_optimizer_selection,
    cells,
    run_evaluation,
)


CONFIG = Path("experiments/configs/scaled_tanh_instantiation.yaml")


@dataclass(frozen=True)
class RawFixture:
    config: dict[str, Any]
    raw_root: Path
    selection: Path


@pytest.fixture(scope="module")
def raw_fixture(tmp_path_factory: pytest.TempPathFactory) -> RawFixture:
    root = tmp_path_factory.mktemp("scaled-tanh-artifacts")
    config = copy.deepcopy(load_config(CONFIG, profile="smoke"))
    config.update(
        {
            "rounds": 8,
            "context_count": 8,
            "horizons": [4, 8],
            "width_ratios": [1.0, 4.0],
            "methods": ["exact_current_relative", "full_cg_relative"],
            "bootstrap_resamples": 50,
            "seed_sets": {
                "development": [42],
                "tuning": [0],
                "evaluation": [200, 201],
            },
            "optimizer_selection": {
                "method": "exact_current_relative",
                "damping_candidates": [float(config["damping"])],
                "horizons": [4],
                "width_ratios": [1.0],
                "criterion": config["optimizer_selection"]["criterion"],
                "evaluation_metrics_read": False,
            },
        }
    )
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
    assert result["run_count"] == 16
    return RawFixture(config=config, raw_root=raw_root, selection=selection)


def test_trajectory_bootstrap_resamples_complete_seed_rows() -> None:
    values = np.asarray([[0.0, 0.0, 0.0], [10.0, 20.0, 30.0]])
    interval = _trajectory_interval(
        values,
        resamples=1000,
        seed_parts=("unit-test",),
    )
    np.testing.assert_allclose(interval["mean"], [5.0, 10.0, 15.0])
    np.testing.assert_allclose(
        np.asarray(interval["ci95_low"])[1:],
        np.asarray(interval["ci95_low"])[0] * np.asarray([2.0, 3.0]),
    )
    np.testing.assert_allclose(
        np.asarray(interval["ci95_high"])[1:],
        np.asarray(interval["ci95_high"])[0] * np.asarray([2.0, 3.0]),
    )
    assert interval["n"] == 2


def test_failed_full_profile_gets_visible_scope_banner() -> None:
    figure = plt.figure()
    top = _add_scope_banner(
        figure,
        {
            "profile": "full",
            "evaluation_seed_count": 2,
            "exact_cg_comparisons": [{}, {}],
            "support_criteria": {"supports_nonavacuous_instantiation_claim": False},
            "theorem_failure_audit": {
                "exact": {"failed_trajectory_count": 1},
                "cg": {"failed_trajectory_count": 2},
            },
        },
    )
    assert top == pytest.approx(0.88)
    assert figure._suptitle is not None
    assert "3/8 theorem trajectories" in figure._suptitle.get_text()
    plt.close(figure)


def test_manifest_grid_artifacts_and_smoke_scope(
    raw_fixture: RawFixture, tmp_path: Path
) -> None:
    # An unregistered seed must not be discovered or consumed.
    cell = cells(raw_fixture.config)[0]
    foreign = (
        raw_fixture.raw_root
        / "smoke"
        / "evaluation"
        / cell.token
        / "exact_current_relative"
        / "seed-999"
    )
    foreign.mkdir(parents=True)
    (foreign / "manifest.json").write_text("not json\n", encoding="ascii")

    aggregate = tmp_path / "aggregate.json"
    artifacts = (
        tmp_path / "scaled_tanh_certificates.pdf",
        tmp_path / "scaled_tanh_regret_bounds.pdf",
        tmp_path / "scaled_tanh_compute.pdf",
        tmp_path / "scaled_tanh_instantiation.tex",
    )
    result = make_artifacts(
        raw_fixture.config,
        profile="smoke",
        raw_root=raw_fixture.raw_root,
        selection_path=raw_fixture.selection,
        aggregate_path=aggregate,
        certificates_figure_path=artifacts[0],
        regret_bounds_figure_path=artifacts[1],
        compute_figure_path=artifacts[2],
        table_path=artifacts[3],
    )
    assert result["validated_run_count"] == 16
    assert result["evidence_scope"] == (
        "smoke-only engineering verification; not main-paper evidence"
    )
    report = json.loads(aggregate.read_text(encoding="ascii"))
    assert report["validated_run_count"] == report["expected_run_count"] == 16
    assert report["optimizer_selection_sha256"] == sha256_file(raw_fixture.selection)
    assert all("seed-999" not in item["path"] for item in report["raw_inputs"])
    assert report["interval"]["unit"] == "one complete evaluation-seed trajectory"
    assert report["tuning_evaluation_seeds_disjoint"] is True
    assert set(report["theorem_failure_audit"]) == {
        "exact_current_relative",
        "full_cg_relative",
    }
    for audit in report["theorem_failure_audit"].values():
        assert audit["failed_trajectory_count"] == 0
        assert audit["failed_round_count"] == 0
        assert all(
            count == 0
            for count in audit["required_event_failure_round_counts"].values()
        )
    assert report["support_criteria"][
        "primary_exact_and_cg_premises_pass_all_trajectories"
    ] is True
    assert report["support_criteria"]["dense_cg_declared_tolerances_pass"] is True
    assert isinstance(
        report["support_criteria"]["supports_nonavacuous_instantiation_claim"],
        bool,
    )
    for group in report["groups"]:
        assert group["premise_failure_count"] == group[
            "premise_failure_round_count"
        ]
        assert group["failed_trajectory_count"] == 0
    for path in (aggregate, *artifacts):
        validate_sha256_sidecar(path)
    for path in artifacts:
        provenance = path.with_name(path.name + ".provenance.json")
        validate_sha256_sidecar(provenance)
        assert json.loads(provenance.read_text(encoding="ascii"))["evidence_scope"] == (
            "smoke-only engineering verification; not main-paper evidence"
        )
    assert b"/FontFile2" in artifacts[0].read_bytes()
    assert "Smoke verification only; not main-paper evidence" in artifacts[3].read_text(
        encoding="ascii"
    )


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("environment_sha256", "0" * 64),
        ("stream_sha256", "1" * 64),
        ("optimizer_selection_sha256", "2" * 64),
    ),
)
def test_rehashed_manifest_identity_corruption_is_rejected(
    raw_fixture: RawFixture,
    tmp_path: Path,
    key: str,
    value: str,
) -> None:
    copied = tmp_path / "raw"
    shutil.copytree(raw_fixture.raw_root, copied)
    cell = cells(raw_fixture.config)[0]
    manifest_path = (
        copied
        / "smoke"
        / "evaluation"
        / cell.token
        / "exact_current_relative"
        / "seed-200"
        / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    manifest[key] = value
    write_json_artifact(manifest_path, manifest)
    with pytest.raises(ScaledTanhArtifactError, match="manifest identity mismatch"):
        build_aggregate(
            raw_fixture.config,
            profile="smoke",
            raw_root=copied,
            selection_path=raw_fixture.selection,
        )


def test_rehashed_config_snapshot_and_selection_corruption_are_rejected(
    raw_fixture: RawFixture, tmp_path: Path
) -> None:
    copied = tmp_path / "raw"
    shutil.copytree(raw_fixture.raw_root, copied)
    cell = cells(raw_fixture.config)[0]
    manifest_path = (
        copied
        / "smoke"
        / "evaluation"
        / cell.token
        / "exact_current_relative"
        / "seed-200"
        / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    manifest["config"]["damping"] = 999.0
    write_json_artifact(manifest_path, manifest)
    with pytest.raises(ScaledTanhArtifactError, match="manifest identity mismatch"):
        build_aggregate(
            raw_fixture.config,
            profile="smoke",
            raw_root=copied,
            selection_path=raw_fixture.selection,
        )

    selection = tmp_path / "optimizer_selection.json"
    shutil.copy2(raw_fixture.selection, selection)
    shutil.copy2(
        raw_fixture.selection.with_name(raw_fixture.selection.name + ".sha256"),
        selection.with_name(selection.name + ".sha256"),
    )
    payload = json.loads(selection.read_text(encoding="ascii"))
    payload["evaluation_metrics_read"] = True
    write_json_artifact(selection, payload)
    with pytest.raises(ScaledTanhArtifactError, match="invalid optimizer selection"):
        build_aggregate(
            raw_fixture.config,
            profile="smoke",
            raw_root=raw_fixture.raw_root,
            selection_path=selection,
        )

    payload = json.loads(raw_fixture.selection.read_text(encoding="ascii"))
    payload["provenance"]["source_artifact_hashes"][
        "experiments/run_scaled_tanh_instantiation.py"
    ] = ("3" * 64)
    write_json_artifact(selection, payload)
    with pytest.raises(ScaledTanhArtifactError, match="runner source hash"):
        build_aggregate(
            raw_fixture.config,
            profile="smoke",
            raw_root=raw_fixture.raw_root,
            selection_path=selection,
        )


def test_sidecar_corruption_is_rejected(
    raw_fixture: RawFixture, tmp_path: Path
) -> None:
    copied = tmp_path / "raw"
    shutil.copytree(raw_fixture.raw_root, copied)
    cell = cells(raw_fixture.config)[0]
    summary = (
        copied
        / "smoke"
        / "evaluation"
        / cell.token
        / "exact_current_relative"
        / "seed-200"
        / "summary.json"
    )
    summary.write_bytes(summary.read_bytes() + b" ")
    with pytest.raises(ScaledTanhArtifactError, match="invalid SHA-256 sidecar"):
        build_aggregate(
            raw_fixture.config,
            profile="smoke",
            raw_root=copied,
            selection_path=raw_fixture.selection,
        )
