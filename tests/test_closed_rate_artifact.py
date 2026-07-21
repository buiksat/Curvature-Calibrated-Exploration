from __future__ import annotations

from pathlib import Path

from experiments.make_closed_rate_artifact import build_artifact, render_table


def test_closed_rate_exponents_are_generated_from_formulas() -> None:
    root = Path(__file__).resolve().parents[1]
    artifact = build_artifact(
        root / "experiments" / "configs" / "closed_rate_predictions.json"
    )
    rows = artifact["rows"]
    assert rows[0]["regret_exponent"] == {"numerator": 3, "denominator": 4}
    assert rows[0]["sample_cvp_exponent"] == {"numerator": 7, "denominator": 4}
    assert rows[1]["regret_exponent"] == {"numerator": 2, "denominator": 3}
    assert rows[1]["sample_cvp_exponent"] == {"numerator": 2, "denominator": 1}
    assert rows[2]["regret_exponent"] == {"numerator": 1, "denominator": 2}
    assert rows[2]["sample_cvp_exponent"] == {"numerator": 5, "denominator": 2}
    table = render_table(artifact)
    assert "$T^{\\frac{3}{4}}$" in table
    assert "$KT^{2}$" in table
