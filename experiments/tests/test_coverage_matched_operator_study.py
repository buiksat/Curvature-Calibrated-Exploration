from __future__ import annotations

import json
from pathlib import Path

from experiments.config import load_config
from experiments.make_coverage_matched_operator_artifacts import build_artifacts
from experiments.run_coverage_matched_operator_study import (
    PROTOCOLS,
    run_study,
    validate_study_config,
)


CONFIG = Path("experiments/configs/coverage_matched_operator.yaml")


def test_coverage_matched_seed_manifest_is_disjoint() -> None:
    config = load_config(CONFIG, "full")
    validate_study_config(config, full=True)
    assert set(config["seed_sets"]["tuning"]).isdisjoint(
        config["seed_sets"]["evaluation"]
    )
    assert tuple(config["calibration"]["protocols"]) == PROTOCOLS


def test_coverage_matched_smoke_pipeline(tmp_path: Path) -> None:
    config = load_config(CONFIG, "smoke")
    raw = tmp_path / "raw"
    manifest = run_study(config, raw)
    assert manifest["evaluation_seeds_inspected_during_selection"] is False
    assert manifest["evaluation_run_count"] == 48

    selection = json.loads((raw / "selection.json").read_text(encoding="ascii"))
    assert selection["evaluation_seeds_inspected"] is False
    assert set(selection["tuning_seeds"]).isdisjoint(manifest["evaluation_seeds"])
    assert selection["multipliers"]["identical_theoretical"] == {
        method: 1.0 for method in config["semantic_methods"]
    }

    artifacts = build_artifacts(
        raw,
        tmp_path / "derived.json",
        tmp_path / "mechanism.pdf",
        tmp_path / "heatmaps.pdf",
        tmp_path / "calibration.tex",
        tmp_path / "comparisons.tex",
    )
    assert artifacts["evaluation_run_count"] == 48
    for path in (
        tmp_path / "derived.json",
        tmp_path / "mechanism.pdf",
        tmp_path / "heatmaps.pdf",
        tmp_path / "calibration.tex",
        tmp_path / "comparisons.tex",
    ):
        assert path.is_file()
        assert path.with_name(path.name + ".sha256").is_file()
        if path.name != "derived.json":
            provenance = json.loads(
                path.with_name(path.name + ".provenance.json").read_text(
                    encoding="ascii"
                )
            )
            assert provenance["artifact"] == path.as_posix()
            assert provenance["inputs"][0]["path"] == (
                tmp_path / "derived.json"
            ).as_posix()
    comparison_text = (tmp_path / "comparisons.tex").read_text(encoding="ascii")
    assert "Holm adjustment uses the complete 168-test family" in comparison_text
    derived = json.loads((tmp_path / "derived.json").read_text(encoding="ascii"))
    assert derived["inference"]["familywise_alpha"] == 0.05
    assert derived["inference"]["test"].startswith("two_sided_paired_student_t")
