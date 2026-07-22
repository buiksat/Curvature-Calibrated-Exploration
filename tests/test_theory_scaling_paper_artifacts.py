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
    "diagonal_current",
    "greedy",
)


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
                    metric: {
                        "slope": 0.1 * method_index,
                        "lower_95": 0.1 * method_index - 0.01,
                        "upper_95": 0.1 * method_index + 0.01,
                    }
                    for metric in ("regret", "Lambda")
                }
            cells[f"d-{dimension}_r-{rank}_T-2048"] = {
                "estimates": estimates,
                "slopes": slopes,
                "theorem_event_failure_counts_float64_audit": {
                    method: {"optimizer_residual": 0} for method in METHODS
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
        "protocol": {"checkpoints": list(HORIZONS)},
        "cells": cells,
    }
    return write_aggregate(report, tmp_path / "scaling.json")


def test_generator_uses_only_hash_validated_full_grid(tmp_path: Path) -> None:
    source = _source(tmp_path)
    figure = tmp_path / "paper" / "figures" / "scaling.pdf"
    table = tmp_path / "paper" / "tables" / "scaling.tex"
    result = generate_theory_scaling_paper_artifacts(
        source=source, figure=figure, table=table
    )

    assert result["artifacts"] == [str(figure), str(table)]
    assert figure.read_bytes().startswith(b"%PDF")
    table_text = table.read_text(encoding="ascii")
    assert "4 & 64.00 [63.90,64.10]" in table_text
    assert "16 & 256.00 [255.90,256.10]" in table_text
    for artifact in (figure, table):
        sidecar = artifact.with_suffix(artifact.suffix + ".provenance.json")
        provenance = json.loads(sidecar.read_text(encoding="ascii"))
        assert provenance["artifact_sha256"] == hashlib.sha256(
            artifact.read_bytes()
        ).hexdigest()
        assert [item["path"] for item in provenance["inputs"]] == sorted(
            (str(source), str(source.with_name(source.name + ".sha256")))
        )


def test_generator_rejects_stale_aggregate(tmp_path: Path) -> None:
    source = _source(tmp_path)
    source.write_text(source.read_text(encoding="ascii") + "\n", encoding="ascii")

    with pytest.raises(ScalingPaperArtifactError, match="hash validation failed"):
        generate_theory_scaling_paper_artifacts(
            source=source,
            figure=tmp_path / "stale.pdf",
            table=tmp_path / "stale.tex",
        )
