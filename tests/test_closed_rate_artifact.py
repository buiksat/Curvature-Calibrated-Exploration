from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from experiments.make_closed_rate_artifact import build_artifact, render_table


def test_closed_rate_exponents_are_generated_from_formulas() -> None:
    root = Path(__file__).resolve().parents[1]
    artifact = build_artifact(
        root / "experiments" / "configs" / "closed_rate_predictions.json"
    )
    rows = artifact["rows"]
    assert rows[0]["regret_exponent"] == {"numerator": 3, "denominator": 4}
    assert rows[0]["sample_cvp_exponent"] == {"numerator": 7, "denominator": 4}
    assert rows[0]["bounded_full_history_exponent"] == {
        "numerator": 2,
        "denominator": 1,
    }
    assert rows[1]["regret_exponent"] == {"numerator": 2, "denominator": 3}
    assert rows[1]["sample_cvp_exponent"] == {"numerator": 2, "denominator": 1}
    assert rows[1]["bounded_full_history_exponent"] == {
        "numerator": 2,
        "denominator": 1,
    }
    assert rows[2]["regret_exponent"] == {"numerator": 1, "denominator": 2}
    assert rows[2]["sample_cvp_exponent"] == {"numerator": 5, "denominator": 2}
    assert rows[2]["bounded_full_history_exponent"] == {
        "numerator": 5,
        "denominator": 2,
    }
    table = render_table(artifact)
    assert "$T^{\\frac{3}{4}}$" in table
    assert "$KT^{2}$" in table
    assert "full-policy sample work" in table
    assert table.count("$T^{2}$") >= 2


def test_checked_in_closed_rate_artifacts_match_generator_and_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(root)
    artifact = build_artifact(
        Path("experiments/configs/closed_rate_predictions.json")
    )
    output = Path("results/derived/closed_rate_predictions.json")
    table = Path("paper/tables/growing_window_pareto.tex")

    assert json.loads(output.read_text(encoding="utf-8")) == artifact
    assert table.read_text(encoding="ascii") == render_table(artifact)

    output_digest = hashlib.sha256(output.read_bytes()).hexdigest()
    provenance = json.loads(
        output.with_suffix(".json.provenance.json").read_text(encoding="utf-8")
    )
    assert provenance["artifact_sha256"] == output_digest
    assert provenance["inputs"] == artifact["inputs"]

    table_digest = hashlib.sha256(table.read_bytes()).hexdigest()
    table_checksum = table.with_suffix(".tex.sha256").read_text(encoding="ascii")
    assert table_checksum == f"{table_digest}  {table.name}\n"
