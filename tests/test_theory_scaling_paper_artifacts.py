from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from experiments.aggregate_theory_scaling import write_aggregate
from experiments.make_theory_scaling_paper_artifacts import (
    ScalingPaperArtifactError,
    generate_theory_scaling_paper_artifacts,
)


HORIZONS = (128, 256, 512, 1024, 2048)
METHODS = (
    "exact_current",
    "full_cg",
    "window_q_1_2",
    "window_q_2_3",
    "window_q_1",
    "frozen",
    "diagonal_current",
    "greedy",
)
def _failure_counts(dimension: int, rank: int, method: str) -> dict[str, int]:
    counts = {
        "optimizer_residual": 0,
        "psi_excitation": 0,
        "psi_lambda": 0,
    }
    if dimension == 2048 and rank == 4 and method == "full_cg":
        counts["optimizer_residual"] = 1
    if (
        dimension == 2048
        and rank == 8
        and method in {"window_q_1_2", "frozen", "diagonal_current"}
    ):
        counts["optimizer_residual"] = 1
    if dimension == 2048 and rank == 16 and method != "greedy":
        counts = {
            "optimizer_residual": 49,
            "psi_excitation": 46,
            "psi_lambda": 45,
        }
    if method == "greedy":
        counts = {
            "optimizer_residual": rank,
            "psi_excitation": rank,
            "psi_lambda": rank,
        }
    return counts


def _source(tmp_path: Path) -> Path:
    cells = {}
    for dimension in (128, 512, 2048):
        for rank in (4, 8, 16):
            estimates = {}
            slopes = {}
            for method_index, method in enumerate(METHODS, start=1):
                estimates[method] = {
                    str(horizon): {
                        "regret": {
                            "mean_interval": {
                                "sample_mean": method_index * rank * horizon / 128.0,
                                "lower_95": method_index * rank * horizon / 128.0 - 0.1,
                                "upper_95": method_index * rank * horizon / 128.0 + 0.1,
                            }
                        }
                    }
                    for horizon in HORIZONS
                }
                slopes[method] = {
                    "regret": {
                        "slope": 1.0,
                        "lower_95": 0.99,
                        "upper_95": 1.01,
                    },
                    "Lambda": {
                        "slope": 0.1 * method_index,
                        "lower_95": 0.1 * method_index - 0.01,
                        "upper_95": 0.1 * method_index + 0.01,
                    },
                }
            cells[f"d-{dimension}_r-{rank}_T-2048"] = {
                "estimates": estimates,
                "slopes": slopes,
                "theorem_event_failure_counts_float64_audit": {
                    method: _failure_counts(dimension, rank, method)
                    for method in METHODS
                },
            }
    report = {
        "schema_version": 1,
        "experiment": "theory_scaling_full_grid_aggregate",
        "coverage": {
            "exact": True,
            "validated_cells": 9,
            "validated_runs": 3600,
        },
        "protocol": {
            "checkpoints": list(HORIZONS),
            "methods": list(METHODS),
        },
        "cells": cells,
    }
    return write_aggregate(report, tmp_path / "scaling.json")


def test_generator_uses_only_hash_validated_full_grid(tmp_path: Path) -> None:
    source = _source(tmp_path)
    figure = tmp_path / "paper" / "figures" / "scaling.pdf"
    table = tmp_path / "paper" / "tables" / "scaling.tex"
    slopes_table = tmp_path / "paper" / "tables" / "scaling_slopes.tex"
    result = generate_theory_scaling_paper_artifacts(
        source=source,
        figure=figure,
        table=table,
        slopes_table=slopes_table,
    )

    assert result["artifacts"] == [
        str(figure),
        str(table),
        str(slopes_table),
    ]
    assert figure.read_bytes().startswith(b"%PDF")
    table_text = table.read_text(encoding="ascii")
    assert "$128/4$ & 64.00 & 128.00 & 192.00 & 256.00" in table_text
    assert "$2048/16$ & 256.00 & 512.00 & 768.00 & 1024.00" in table_text
    assert "Cell $(d/r)$ & Exact & CG" in table_text
    assert "Full CG & PASS & FAIL [$O$=1] & PASS & FAIL [$O$=49" in table_text
    assert (
        "Window $q=1/2$ & PASS & PASS & FAIL [$O$=1] "
        "& FAIL [$O$=49, $P_e$=46, $P_\\lambda$=45]"
        in table_text
    )
    assert table_text.count("Greedy") == 1
    assert "Greedy & PASS" not in table_text
    assert "Audit fail." not in table_text

    slopes_text = slopes_table.read_text(encoding="ascii")
    assert (
        "4 & Exact current & 1.000 [0.990, 1.010] & 1.0000 & "
        in slopes_text
    )
    assert "16 & Greedy & 1.000 [0.990, 1.010]" in slopes_text
    assert "$\\Lambda$ slope [95\\% interval]" in slopes_text

    for artifact in (figure, table, slopes_table):
        sidecar = artifact.with_suffix(artifact.suffix + ".provenance.json")
        provenance = json.loads(sidecar.read_text(encoding="ascii"))
        assert provenance["artifact_sha256"] == hashlib.sha256(
            artifact.read_bytes()
        ).hexdigest()
        assert [item["path"] for item in provenance["inputs"]] == sorted(
            (str(source), str(source.with_name(source.name + ".sha256")))
        )
    slopes_provenance = json.loads(
        slopes_table.with_suffix(".tex.provenance.json").read_text(encoding="ascii")
    )
    assert slopes_provenance["generation_parameters"]["diagnostics"] == [
        "R-squared",
        "maximum absolute log-space residual",
    ]


def test_generator_rejects_stale_aggregate(tmp_path: Path) -> None:
    source = _source(tmp_path)
    source.write_text(source.read_text(encoding="ascii") + "\n", encoding="ascii")

    with pytest.raises(ScalingPaperArtifactError, match="hash validation failed"):
        generate_theory_scaling_paper_artifacts(
            source=source,
            figure=tmp_path / "stale.pdf",
            table=tmp_path / "stale.tex",
            slopes_table=tmp_path / "stale_slopes.tex",
        )
