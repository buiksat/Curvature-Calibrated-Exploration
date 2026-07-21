from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from experiments.aggregate_results import write_aggregate_with_provenance
from experiments.logging_utils import canonical_json
from experiments.make_offdiagonal_witness_paper_artifacts import (
    WitnessPaperArtifactError,
    generate_offdiagonal_witness_paper_artifacts,
)


CHECKPOINTS = [10, 100, 1000, 10000]
METHODS = (
    "exact_full",
    "full_cg",
    "diagonal_raw",
    "diagonal_uniform_transfer",
    "diagonal_actionwise_reference",
    "greedy",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stats(mean: float, n: int, spread: float = 0.0) -> dict[str, Any]:
    return {
        "mean": mean,
        "ci95_low": mean - spread,
        "ci95_high": mean + spread,
        "n": n,
    }


def _group(
    *,
    cell: str,
    method: str,
    curve: list[float],
    noise: float,
    run_count: int,
    slope: float,
) -> dict[str, Any]:
    return {
        "cell": cell,
        "method": method,
        "noise_std": noise,
        "run_count": run_count,
        "classification": (
            "analytic_constructive_witness"
            if noise == 0.0
            else "uncertified_noisy_extension"
        ),
        "horizons": [
            {
                "horizon": horizon,
                "cumulative_pseudo_regret": _stats(
                    mean, run_count, 0.0 if run_count == 1 else min(0.1, mean / 2.0)
                ),
            }
            for horizon, mean in zip(CHECKPOINTS, curve)
        ],
        "log_log_slope": {
            "estimate": slope,
            "bootstrap_ci95": [slope - 0.01, slope + 0.01],
        },
    }


def _source(tmp_path: Path) -> tuple[Path, Path]:
    raw = tmp_path / "raw.jsonl"
    raw.write_text('{"event":"fixture"}\n', encoding="ascii")
    inputs = [{"path": str(raw), "sha256": _sha256(raw)}]
    groups: list[dict[str, Any]] = []
    flat = [1.0, 1.0, 1.0, 1.0]
    linear = [9.0, 90.0, 900.0, 9000.0]
    for method in METHODS:
        curve = (
            flat
            if method
            in {"exact_full", "full_cg", "diagonal_actionwise_reference"}
            else linear
        )
        groups.append(
            _group(
                cell="analytic",
                method=method,
                curve=curve,
                noise=0.0,
                run_count=1,
                slope=0.0 if curve is flat else 1.0,
            )
        )
    noisy_curves = {
        "exact_full": [1.0, 2.0, 3.0, 4.0],
        "full_cg": [1.0, 2.0, 3.0, 4.0],
        "diagonal_raw": linear,
        "diagonal_uniform_transfer": [2.0, 4.0, 6.0, 8.0],
        "diagonal_actionwise_reference": [1.0, 2.0, 3.0, 4.0],
        "greedy": linear,
    }
    for method in METHODS:
        groups.append(
            _group(
                cell="noisy_cell",
                method=method,
                curve=noisy_curves[method],
                noise=0.02,
                run_count=4,
                slope=0.2 if method in {"exact_full", "full_cg"} else 1.0,
            )
        )
    paired = [
        {
            "cell": "noisy_cell",
            "comparison": "diagonal_raw_minus_exact_full",
            "horizon": 10000,
            "paired_cumulative_pseudo_regret": _stats(8996.0, 4, 1.0),
        },
        {
            "cell": "noisy_cell",
            "comparison": "diagonal_uniform_transfer_minus_exact_full",
            "horizon": 10000,
            "paired_cumulative_pseudo_regret": _stats(4.0, 4, 1.0),
        },
    ]
    input_digest = hashlib.sha256(canonical_json(inputs).encode("ascii")).hexdigest()
    report = {
        "schema_version": 1,
        "experiment": "offdiagonal_witness",
        "profile": "full",
        "seed_set": "evaluation",
        "scope": "existence witness only; it does not claim uniform full-curvature dominance",
        "deterministic_cell_seed_count": 1,
        "noisy_cell_seed_count": 4,
        "checkpoints": CHECKPOINTS,
        "groups": groups,
        "paired_final_horizon": paired,
        "inputs": inputs,
        "input_set_sha256": input_digest,
    }
    return write_aggregate_with_provenance(report, tmp_path / "offdiagonal.json")


def test_generator_uses_only_validated_derived_values(tmp_path: Path) -> None:
    source, source_sidecar = _source(tmp_path)
    figure = tmp_path / "paper" / "figures" / "witness.pdf"
    table = tmp_path / "paper" / "tables" / "witness.tex"
    result = generate_offdiagonal_witness_paper_artifacts(
        source=source, figure=figure, table=table
    )

    assert result["artifacts"] == [str(figure), str(table)]
    assert figure.read_bytes().startswith(b"%PDF")
    assert b"/Subtype /Type3" not in figure.read_bytes()
    table_text = table.read_text(encoding="ascii")
    assert "Exact full & 1.00 & 1.00 & 1.00 & 1.00 & 0.000" in table_text
    assert "Diagonal (raw) & 9.00 & 90.00 & 900.00 & 9000.00 & 1.000" in table_text

    figure_provenance = json.loads(
        figure.with_suffix(".pdf.provenance.json").read_text(encoding="utf-8")
    )
    assert figure_provenance["artifact_sha256"] == _sha256(figure)
    assert figure_provenance["generation_parameters"]["log_axis_numerical_floor"] is None
    assert [item["path"] for item in figure_provenance["inputs"]] == sorted(
        (str(source), str(source_sidecar))
    )
    for item in figure_provenance["inputs"]:
        assert item["sha256"] == _sha256(Path(item["path"]))

    table_provenance = json.loads(
        table.with_suffix(".tex.provenance.json").read_text(encoding="utf-8")
    )
    assert table_provenance["artifact_sha256"] == _sha256(table)
    assert table_provenance["generation_parameters"]["checkpoints"] == CHECKPOINTS


def test_generator_rejects_stale_source_before_writing(tmp_path: Path) -> None:
    source, _ = _source(tmp_path)
    report = json.loads(source.read_text(encoding="utf-8"))
    report["groups"][0]["horizons"][0]["cumulative_pseudo_regret"]["mean"] = 7.0
    source.write_text(json.dumps(report), encoding="utf-8")
    figure = tmp_path / "stale" / "witness.pdf"
    table = tmp_path / "stale" / "witness.tex"

    with pytest.raises(WitnessPaperArtifactError, match="provenance validation failed"):
        generate_offdiagonal_witness_paper_artifacts(
            source=source, figure=figure, table=table
        )

    assert not figure.exists()
    assert not table.exists()


def test_generator_rejects_zero_log_axis_value(tmp_path: Path) -> None:
    source, _ = _source(tmp_path)
    report = json.loads(source.read_text(encoding="utf-8"))
    report["groups"][0]["horizons"][0]["cumulative_pseudo_regret"].update(
        {"mean": 0.0, "ci95_low": 0.0, "ci95_high": 0.0}
    )
    inputs = report["inputs"]
    report["input_set_sha256"] = hashlib.sha256(
        canonical_json(inputs).encode("ascii")
    ).hexdigest()
    source, _ = write_aggregate_with_provenance(report, source)

    with pytest.raises(WitnessPaperArtifactError, match="positive on a log axis"):
        generate_offdiagonal_witness_paper_artifacts(
            source=source,
            figure=tmp_path / "zero.pdf",
            table=tmp_path / "zero.tex",
        )
