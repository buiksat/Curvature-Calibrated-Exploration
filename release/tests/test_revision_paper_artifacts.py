from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from experiments.aggregate_results import write_aggregate_with_provenance
from experiments.logging_utils import canonical_json
from experiments.make_revision_paper_artifacts import (
    BALANCED_METHODS,
    PHASE_METHODS,
    RevisionArtifactError,
    TANH_METRICS,
    _phase_matrix,
    generate_revision_artifacts,
)


def _stats(mean: float, *, positive: bool = False) -> dict[str, float]:
    width = 0.25 if positive else 0.5
    low = mean - width
    if positive:
        assert low > 0
    return {
        "mean": mean,
        "ci95_low": low,
        "ci95_high": mean + width,
        "ci95": [low, mean + width],
        "ci95_half_width": width,
        "n": 5,
        "standard_deviation": 0.1,
        "standard_error": 0.1 / 5**0.5,
        "t_critical": 2.7,
    }


def _bind_source(tmp_path: Path, name: str, value: dict[str, Any]) -> tuple[Path, Path]:
    raw = tmp_path / "raw" / f"{name}.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text('{"event":"fixture"}\n', encoding="utf-8")
    inputs = [{"path": str(raw), "sha256": hashlib.sha256(raw.read_bytes()).hexdigest()}]
    value["inputs"] = inputs
    value["input_set_sha256"] = hashlib.sha256(
        canonical_json(inputs).encode("ascii")
    ).hexdigest()
    return write_aggregate_with_provenance(value, tmp_path / f"{name}.json")


def _sources(tmp_path: Path) -> dict[str, tuple[Path, Path]]:
    policies: dict[str, Any] = {}
    for center_index, center in enumerate(("original", "corrected")):
        metrics: dict[str, Any] = {
            "cumulative_pseudo_regret": _stats(2.0 + center_index),
            "runtime_seconds": _stats(0.125 + 0.1 * center_index),
        }
        for metric_index, (exact, bound, _) in enumerate(TANH_METRICS):
            metrics[exact] = _stats(1.0 + metric_index + center_index, positive=True)
            metrics[bound] = _stats(10.0 + metric_index + center_index, positive=True)
        policies[center] = {
            "all_observed_theorem_event_checks_hold": True,
            "certificate_failure_count": 0,
            "certification_category": "posthoc_theorem_event_verified",
            "metrics": metrics,
            "run_count": 5,
        }
    tanh = {
        "schema_version": 1,
        "experiment": "certified_tanh",
        "profile": "full",
        "seed_set": "evaluation",
        "policies": policies,
    }

    method_results: dict[str, Any] = {}
    for index, (method, _) in enumerate(BALANCED_METHODS):
        method_results[method] = {
            "metrics": {
                "cumulative_pseudo_regret": _stats(10.0 + index),
                "runtime_seconds": _stats(0.01 + 0.001 * index),
            },
            "published_implementation_claim": False,
            "selected_hyperparameters": {"ridge": 1.0},
        }
    balanced = {
        "schema_version": 1,
        "event": "balanced_contextual_benchmark_report",
        "experiment": "balanced_benchmark",
        "profile": "full",
        "seed_set": "evaluation",
        "tuning_evaluation_seeds_disjoint": True,
        "selection_artifact_sha256": "a" * 64,
        "method_results": method_results,
    }

    cells = [{"cell_id": f"ffd_{index:03b}"} for index in range(8)]
    comparisons = []
    for method_index, (method, _) in enumerate(PHASE_METHODS):
        for cell_index, cell in enumerate(cells):
            comparisons.append(
                {
                    "cell_id": cell["cell_id"],
                    "method": method,
                    "reference_method": "exact_full",
                    "difference": "method_minus_full_cumulative_pseudo_regret",
                    "posthoc_cell_or_method_selection": False,
                    "paired_interval": _stats(float(10 * (method_index + 1) + cell_index)),
                }
            )
    for cell in cells:
        comparisons.append(
            {
                "cell_id": cell["cell_id"],
                "method": "full_cg",
                "reference_method": "exact_full",
                "difference": "method_minus_full_cumulative_pseudo_regret",
                "posthoc_cell_or_method_selection": False,
                "paired_interval": {
                    **_stats(0.0),
                    "ci95": [0.0, 0.0],
                    "ci95_low": 0.0,
                    "ci95_high": 0.0,
                },
            }
        )
    phase = {
        "schema_version": 1,
        "study": "curvature_mechanism_phase_diagram",
        "preregistered_grid": {
            "cell_count": 8,
            "phase": "evaluation",
            "cells": cells,
        },
        "paired_full_comparisons": comparisons,
    }
    systems = {
        "schema_version": 1,
        "event": "diagnostic_aggregate",
        "experiments": ["systems_scaling"],
        "profiles": ["full"],
        "seed_sets": ["evaluation"],
        "all_groups_complete": True,
        "benchmark_diagnostic_group_count": 1,
    }
    return {
        "tanh": _bind_source(tmp_path, "tanh", tanh),
        "balanced": _bind_source(tmp_path, "balanced", balanced),
        "phase": _bind_source(tmp_path, "phase", phase),
        "systems": _bind_source(tmp_path, "systems", systems),
    }


def _generate(tmp_path: Path, sources: dict[str, tuple[Path, Path]]) -> dict[str, Any]:
    return generate_revision_artifacts(
        tanh_path=sources["tanh"][0],
        balanced_path=sources["balanced"][0],
        phase_path=sources["phase"][0],
        systems_path=sources["systems"][0],
        figure_pdf=tmp_path / "paper" / "figures" / "theory_factor_drift.pdf",
        table_path=tmp_path / "paper" / "tables" / "executed_policy_results.tex",
    )


def test_generator_uses_exact_values_and_binds_direct_inputs(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    result = _generate(tmp_path, sources)

    pdf, png, table = (Path(path) for path in result["artifacts"])
    assert pdf.read_bytes().startswith(b"%PDF")
    assert b"/Subtype /Type3" not in pdf.read_bytes()
    assert png.read_bytes().startswith(b"\x89PNG")
    table_text = table.read_text(encoding="ascii")
    assert "Original center & 2.00 [1.50, 2.50] & 0.125 & 0/5 & Post-hoc verified" in table_text
    assert "CC-UCB (full GGN-CG) & 10.00 [9.50, 10.50] & 0.010 & -- & Uncertified" in table_text
    assert "Context-free TS & 20.00 [19.50, 20.50] & 0.020 & -- & Uncertified" in table_text

    figure_sidecar = json.loads(
        pdf.with_suffix(".pdf.provenance.json").read_text(encoding="utf-8")
    )
    expected_figure_paths = sorted(
        str(path) for name in ("tanh", "phase") for path in sources[name]
    )
    assert [item["path"] for item in figure_sidecar["inputs"]] == expected_figure_paths
    assert figure_sidecar["artifact_sha256"] == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert figure_sidecar["generation_parameters"]["log_axis_numerical_floor"] is None
    for item in figure_sidecar["inputs"]:
        assert item["sha256"] == hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest()

    table_sidecar = json.loads(
        table.with_suffix(".tex.provenance.json").read_text(encoding="utf-8")
    )
    expected_table_paths = sorted(
        str(path) for name in ("tanh", "balanced") for path in sources[name]
    )
    assert [item["path"] for item in table_sidecar["inputs"]] == expected_table_paths
    expected_input_hash = hashlib.sha256(
        canonical_json(table_sidecar["inputs"]).encode("ascii")
    ).hexdigest()
    assert table_sidecar["input_set_sha256"] == expected_input_hash
    assert {item["path"] for item in result["validated_sources"]} == {
        str(sources[name][0]) for name in sources
    }


def test_phase_matrix_is_paired_method_minus_full_without_reordering(tmp_path: Path) -> None:
    phase_path, _ = _sources(tmp_path)["phase"]
    phase = json.loads(phase_path.read_text(encoding="utf-8"))
    cells, matrix, identical = _phase_matrix(phase)
    assert cells == [f"ffd_{index:03b}" for index in range(8)]
    assert matrix[0] == [float(10 + index) for index in range(8)]
    assert matrix[-1] == [float(50 + index) for index in range(8)]
    assert identical is True


def test_generator_rejects_stale_source_before_writing(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    balanced = sources["balanced"][0]
    bound_raw = Path(json.loads(balanced.read_text(encoding="utf-8"))["inputs"][0]["path"])
    bound_raw.write_text('{"event":"mutated"}\n', encoding="utf-8")
    pdf = tmp_path / "out" / "figure.pdf"
    table = tmp_path / "out" / "table.tex"

    with pytest.raises(RevisionArtifactError, match="provenance validation failed"):
        generate_revision_artifacts(
            tanh_path=sources["tanh"][0],
            balanced_path=balanced,
            phase_path=sources["phase"][0],
            systems_path=sources["systems"][0],
            figure_pdf=pdf,
            table_path=table,
        )

    assert not pdf.exists()
    assert not table.exists()
