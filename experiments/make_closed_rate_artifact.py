"""Generate the analytic growing-window Pareto artifact and LaTeX table."""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from .aggregate_results import write_aggregate_with_provenance
from .logging_utils import canonical_json


DEFAULT_CONFIG = Path("experiments/configs/closed_rate_predictions.json")
DEFAULT_OUTPUT = Path("results/derived/closed_rate_predictions.json")
DEFAULT_TABLE = Path("paper/tables/growing_window_pareto.tex")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_artifact(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise ValueError("closed-rate config schema_version must be 1")
    rows = []
    for item in config.get("window_exponents", []):
        q = Fraction(int(item["numerator"]), int(item["denominator"]))
        if not Fraction(0, 1) < q <= Fraction(1, 1):
            raise ValueError("window exponents must lie in (0,1]")
        regret = Fraction(1, 1) - q / 2
        cost = Fraction(1, 1) + 3 * q / 2
        rows.append(
            {
                "q": {"numerator": q.numerator, "denominator": q.denominator},
                "regret_exponent": {
                    "numerator": regret.numerator,
                    "denominator": regret.denominator,
                },
                "sample_cvp_exponent": {
                    "numerator": cost.numerator,
                    "denominator": cost.denominator,
                },
            }
        )
    if not rows:
        raise ValueError("closed-rate config has no window exponents")
    inputs = [{"path": str(config_path), "sha256": _sha256(config_path)}]
    return {
        "schema_version": 1,
        "artifact": "closed_rate_predictions",
        "regret_formula": "1-q/2",
        "sample_cvp_formula": "1+3q/2",
        "rows": rows,
        "inputs": inputs,
        "input_set_sha256": hashlib.sha256(
            canonical_json(inputs).encode("ascii")
        ).hexdigest(),
    }


def _tex_fraction(value: dict[str, int]) -> str:
    numerator = int(value["numerator"])
    denominator = int(value["denominator"])
    return str(numerator) if denominator == 1 else rf"\frac{{{numerator}}}{{{denominator}}}"


def render_table(artifact: dict[str, Any]) -> str:
    lines = [
        r"\begin{center}",
        r"\begin{tabular}{@{}ccc@{}}",
        r"\toprule",
        r"$q$ & regret exponent & cumulative sample-CVP exponent\\",
        r"\midrule",
    ]
    for row in artifact["rows"]:
        q = _tex_fraction(row["q"])
        regret = _tex_fraction(row["regret_exponent"])
        cost = _tex_fraction(row["sample_cvp_exponent"])
        lines.append(rf"${q}$ & $T^{{{regret}}}$ & $KT^{{{cost}}}$\\")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{center}", ""])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    args = parser.parse_args(argv)
    artifact = build_artifact(args.config)
    output, sidecar = write_aggregate_with_provenance(artifact, args.output)
    args.table.parent.mkdir(parents=True, exist_ok=True)
    args.table.write_text(render_table(artifact), encoding="ascii")
    table_sidecar = args.table.with_suffix(args.table.suffix + ".sha256")
    table_sidecar.write_text(f"{_sha256(args.table)}  {args.table.name}\n", encoding="ascii")
    print(f"wrote {output}, {sidecar}, {args.table}, and {table_sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
