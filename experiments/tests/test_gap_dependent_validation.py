from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import matplotlib
import numpy as np

from experiments.artifact_utils import validate_sha256_sidecar
from experiments.config import get_seed_set, load_config
from experiments.make_gap_dependent_validation_artifacts import build_artifacts
from experiments.run_gap_dependent_validation import (
    METHODS,
    generate_stream,
    run_grid,
    run_trajectory,
    validate_study_config,
)


CONFIG = Path("experiments/configs/gap_dependent_validation.yaml")


def _smoke_config() -> dict[str, object]:
    return load_config(CONFIG, profile="smoke")


def test_gap_validation_config_is_preregistered_and_disjoint() -> None:
    config = _smoke_config()
    validate_study_config(config)
    assert tuple(config["gaps"]) == (0.05, 0.1, 0.2, 0.4)
    assert tuple(config["methods"]) == METHODS
    assert config["policy_uses_gap"] is False
    assert set(get_seed_set(config, "tuning")).isdisjoint(
        get_seed_set(config, "evaluation")
    )


def test_stream_has_one_unique_action_and_exact_controlled_gap() -> None:
    config = _smoke_config()
    first = generate_stream(config, 0.2, seed=1000)
    second = generate_stream(config, 0.2, seed=1000)
    assert first.stream_sha256 == second.stream_sha256
    np.testing.assert_array_equal(first.features, second.features)
    np.testing.assert_allclose(
        np.linalg.norm(first.features, axis=2),
        float(config["feature_bound"]),
        rtol=0.0,
        atol=1e-12,
    )
    ordered = np.sort(first.true_means, axis=1)
    np.testing.assert_allclose(ordered[:, -1] - ordered[:, -2], 0.2, atol=1e-12)
    np.testing.assert_array_equal(np.argmax(first.true_means, axis=1), first.optimal_actions)


def test_exact_and_full_cg_validate_gap_corollary_premises() -> None:
    config = _smoke_config()
    stream = generate_stream(config, 0.1, seed=1000)
    exact = run_trajectory(config, 0.1, stream, method="exact_full")
    cg = run_trajectory(config, 0.1, stream, method="full_cg")

    np.testing.assert_array_equal(
        exact.arrays["selected_actions"], exact.arrays["reference_exact_actions"]
    )
    np.testing.assert_array_equal(
        exact.arrays["selected_actions"], cg.arrays["selected_actions"]
    )
    assert float(np.max(exact.arrays["maximum_linearization_error"])) < 1e-12
    assert bool(np.all(exact.arrays["controlled_gap_premise"]))
    assert bool(np.all(exact.arrays["linearization_error_premise"]))
    assert exact.summary["premise_checks"]["gap_corollary_applicable_all_rounds"]
    assert cg.summary["premise_checks"]["gap_corollary_applicable_all_rounds"]
    assert cg.summary["maximum_cg_energy_error"] <= float(
        config["cg_target_energy_error"]
    ) * (1.0 + 1e-8)
    assert exact.summary["terminal_gap_free_rhs"] >= exact.summary[
        "terminal_pseudo_regret"
    ]
    assert exact.summary["terminal_gap_dependent_rhs"] >= exact.summary[
        "terminal_pseudo_regret"
    ]
    assert [item["horizon"] for item in exact.summary["horizon_metrics"]] == [16, 32]
    assert exact.summary["terminal_cumulative_linearization_error"] < 1e-12


def test_approximate_controls_are_not_mislabeled_exact_current() -> None:
    config = _smoke_config()
    stream = generate_stream(config, 0.4, seed=1000)
    for method in ("rank_truncation", "diagonal", "greedy"):
        trajectory = run_trajectory(config, 0.4, stream, method=method)
        assert trajectory.summary["premise_checks"]["exact_current_operator"] is False
        assert (
            trajectory.summary["premise_checks"][
                "gap_corollary_applicable_all_rounds"
            ]
            is False
        )


def test_raw_payload_is_deterministic_and_provenance_artifacts_validate(
    tmp_path: Path,
) -> None:
    config = copy.deepcopy(_smoke_config())
    config["rounds"] = 8
    config["horizons"] = [8]
    config["gaps"] = [0.1]
    config["seed_sets"] = {
        "development": [42],
        "tuning": [0],
        "evaluation": [1000],
    }
    validate_study_config(config)
    roots = (tmp_path / "first", tmp_path / "second")
    for root in roots:
        result = run_grid(
            config,
            profile="smoke",
            seed_set="evaluation",
            output_root=root,
            workers=1,
        )
        assert result["run_count"] == len(METHODS)

    first_phase = roots[0] / "smoke" / "evaluation"
    second_phase = roots[1] / "smoke" / "evaluation"
    for method in METHODS:
        relative = Path("gap-0p1") / method / "seed-1000"
        for filename in (
            "rounds.npz",
            "rounds.npz.sha256",
            "summary.json",
            "summary.json.sha256",
        ):
            assert (first_phase / relative / filename).read_bytes() == (
                second_phase / relative / filename
            ).read_bytes()

        manifest = json.loads(
            (first_phase / relative / "manifest.json").read_text(encoding="ascii")
        )
        assert manifest["timestamp_utc"].endswith("Z")
        assert manifest["deterministic_scientific_payload"] is True
        assert manifest["evidence_scope"] == (
            "SMOKE ONLY - not main-paper evidence"
        )
        provenance = manifest["provenance"]
        assert {
            "git_revision",
            "git_dirty",
            "package_versions",
            "hardware",
            "python",
            "source_artifact_hashes",
        } <= set(provenance)
        assert set(config["provenance"]["packages"]) <= set(
            provenance["package_versions"]
        )
        assert provenance["source_artifact_hashes"]

    aggregate = tmp_path / "derived" / "aggregate.json"
    figure = tmp_path / "derived" / "figure.pdf"
    table = tmp_path / "derived" / "table.tex"
    result = build_artifacts(
        config,
        profile="smoke",
        raw_root=roots[0],
        aggregate_path=aggregate,
        figure_path=figure,
        table_path=table,
    )
    assert result["validated_run_count"] == len(METHODS)
    assert result["evidence_scope"] == "SMOKE ONLY - not main-paper evidence"
    report = json.loads(aggregate.read_text(encoding="ascii"))
    assert report["evidence_scope"] == "SMOKE ONLY - not main-paper evidence"
    assert "SMOKE ONLY --- not main-paper evidence" in table.read_text(
        encoding="ascii"
    )
    assert matplotlib.rcParams["pdf.fonttype"] == 42
    for path in (aggregate, figure, table):
        validate_sha256_sidecar(path)
    validate_sha256_sidecar(figure.with_name("figure.pdf.provenance.json"))
    validate_sha256_sidecar(table.with_name("table.tex.provenance.json"))
    if shutil.which("pdffonts"):
        fonts = subprocess.run(
            ["pdffonts", figure.as_posix()],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert "Type 3" not in fonts
    if shutil.which("pdftotext"):
        extracted = subprocess.run(
            ["pdftotext", figure.as_posix(), "-"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert "SMOKE ONLY - not main-paper evidence" in extracted
