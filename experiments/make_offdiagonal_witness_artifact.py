"""Aggregate the off-diagonal witness from immutable raw run directories."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .aggregate_results import student_t_interval, write_aggregate_with_provenance
from .config import get_seed_set, load_config
from .logging_utils import canonical_json


DEFAULT_CONFIG = Path("experiments/configs/offdiagonal_witness.yaml")
DEFAULT_RAW = Path("results/raw/offdiagonal_witness/full/evaluation")
DEFAULT_OUTPUT = Path("results/derived/offdiagonal_witness.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _single_json_line(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 1:
        raise ValueError(f"{path} must contain exactly one JSON line")
    value = json.loads(lines[0])
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _round_records(path: Path) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict) or value.get("event") != "round":
            raise ValueError(f"invalid round record in {path}")
        metrics = value.get("metrics")
        if not isinstance(metrics, dict):
            raise ValueError(f"round record lacks metrics in {path}")
        round_number = int(metrics.get("round", -1))
        if round_number <= 0 or round_number in result:
            raise ValueError(f"invalid or duplicate round in {path}")
        result[round_number] = metrics
    return result


def _slope(curves: np.ndarray, checkpoints: np.ndarray) -> tuple[float, list[float]]:
    mean_curve = np.mean(curves, axis=0)
    if np.any(mean_curve <= 0.0):
        raise ValueError("log-log slope requires positive cumulative regret")
    slope = float(np.polyfit(np.log(checkpoints), np.log(mean_curve), 1)[0])
    if curves.shape[0] == 1:
        return slope, [slope, slope]
    rng = np.random.default_rng(20260721)
    bootstrap = np.empty(2000, dtype=np.float64)
    for index in range(bootstrap.size):
        sample = rng.integers(0, curves.shape[0], size=curves.shape[0])
        curve = np.mean(curves[sample], axis=0)
        bootstrap[index] = np.polyfit(np.log(checkpoints), np.log(curve), 1)[0]
    interval = np.quantile(bootstrap, [0.025, 0.975]).tolist()
    return slope, [float(interval[0]), float(interval[1])]


def build_artifact(
    *,
    config_path: Path = DEFAULT_CONFIG,
    raw_root: Path = DEFAULT_RAW,
) -> dict[str, Any]:
    config = load_config(config_path, profile="full")
    evaluation_seeds = get_seed_set(config, "evaluation")
    methods = tuple(str(value) for value in config["methods"])
    checkpoints = np.asarray(config["checkpoints"], dtype=np.int64)
    cells = tuple(dict(value) for value in config["cells"])
    inputs: list[Path] = [config_path]
    groups: list[dict[str, Any]] = []
    curves_by_cell_method: dict[tuple[str, str], tuple[tuple[int, ...], np.ndarray]] = {}

    for cell in cells:
        cell_name = str(cell["cell"])
        noise_std = float(cell["noise_std"])
        expected_seeds = evaluation_seeds[:1] if noise_std == 0.0 else evaluation_seeds
        for method in methods:
            curves: list[list[float]] = []
            seed_level: list[dict[str, Any]] = []
            classifications: set[str] = set()
            for seed in expected_seeds:
                directory = raw_root / cell_name / method / f"seed-{seed}"
                manifest_path = directory / "manifest.jsonl"
                raw_path = directory / "raw.jsonl"
                summary_path = directory / "summary.jsonl"
                for path in (manifest_path, raw_path, summary_path):
                    if not path.is_file():
                        raise FileNotFoundError(path)
                    inputs.append(path)
                manifest = _single_json_line(manifest_path)
                summary = _single_json_line(summary_path)
                records = _round_records(raw_path)
                if int(manifest.get("seed", -1)) != seed:
                    raise ValueError(f"manifest seed mismatch in {directory}")
                if summary.get("cell") != cell_name or summary.get("method") != method:
                    raise ValueError(f"summary identity mismatch in {directory}")
                missing = set(int(value) for value in checkpoints) - set(records)
                if missing:
                    raise ValueError(f"missing checkpoints {sorted(missing)} in {directory}")
                curve = [
                    float(records[int(horizon)]["cumulative_pseudo_regret"])
                    for horizon in checkpoints
                ]
                if not np.isclose(
                    curve[-1],
                    float(summary["final_cumulative_pseudo_regret"]),
                    rtol=0.0,
                    atol=1e-10,
                ):
                    raise ValueError(f"raw/summary regret mismatch in {directory}")
                curves.append(curve)
                classifications.add(str(summary["classification"]))
                seed_level.append(
                    {
                        "seed": seed,
                        "cumulative_pseudo_regret": curve,
                        "suboptimal_pull_count": int(summary["suboptimal_pull_count"]),
                        "runtime_seconds": float(summary["runtime_seconds"]),
                    }
                )
            if len(classifications) != 1:
                raise ValueError("classification differs within a group")
            curve_array = np.asarray(curves, dtype=np.float64)
            slope, slope_interval = _slope(curve_array, checkpoints)
            horizon_metrics = []
            for column, horizon in enumerate(checkpoints):
                horizon_metrics.append(
                    {
                        "horizon": int(horizon),
                        "cumulative_pseudo_regret": student_t_interval(
                            curve_array[:, column]
                        ),
                    }
                )
            groups.append(
                {
                    "cell": cell_name,
                    "method": method,
                    "noise_std": noise_std,
                    "delta": float(cell["delta"]),
                    "epsilon": float(config["epsilon"]),
                    "angle_degrees": float(cell["angle_degrees"]),
                    "bonus": float(config["bonus"]),
                    "run_count": len(expected_seeds),
                    "seeds": list(expected_seeds),
                    "classification": next(iter(classifications)),
                    "horizons": horizon_metrics,
                    "log_log_slope": {
                        "estimate": slope,
                        "bootstrap_ci95": slope_interval,
                        "regression": "OLS log(mean cumulative pseudo-regret) on log(horizon)",
                        "horizon_range": [int(checkpoints[0]), int(checkpoints[-1])],
                        "bootstrap_resamples": 0 if len(expected_seeds) == 1 else 2000,
                    },
                    "seed_level": seed_level,
                }
            )
            curves_by_cell_method[(cell_name, method)] = (
                tuple(expected_seeds),
                curve_array,
            )

    paired: list[dict[str, Any]] = []
    for cell in cells:
        cell_name = str(cell["cell"])
        for comparator in ("full_cg", "diagonal_raw", "diagonal_uniform_transfer"):
            base_seeds, base = curves_by_cell_method[(cell_name, "exact_full")]
            other_seeds, other = curves_by_cell_method[(cell_name, comparator)]
            if base_seeds != other_seeds:
                raise ValueError("paired methods do not share seed coverage")
            differences = other[:, -1] - base[:, -1]
            paired.append(
                {
                    "cell": cell_name,
                    "comparison": f"{comparator}_minus_exact_full",
                    "horizon": int(checkpoints[-1]),
                    "paired_cumulative_pseudo_regret": student_t_interval(differences),
                }
            )

    normalized_inputs = [
        {"path": str(path), "sha256": _sha256(path)}
        for path in sorted(set(inputs), key=lambda value: str(value))
    ]
    input_digest = hashlib.sha256(
        canonical_json(normalized_inputs).encode("ascii")
    ).hexdigest()
    return {
        "schema_version": 1,
        "experiment": "offdiagonal_witness",
        "profile": "full",
        "seed_set": "evaluation",
        "preregistered_hypothesis": (
            "full covariance escapes the analytic 45-degree witness while raw and "
            "uniformly transferred diagonal geometry remain on the suboptimal action"
        ),
        "scope": (
            "existence witness only; it does not claim uniform full-curvature dominance"
        ),
        "deterministic_cell_seed_count": 1,
        "noisy_cell_seed_count": len(evaluation_seeds),
        "checkpoints": checkpoints.tolist(),
        "groups": groups,
        "paired_final_horizon": paired,
        "inputs": normalized_inputs,
        "input_set_sha256": input_digest,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    artifact = build_artifact(config_path=args.config, raw_root=args.raw)
    output, sidecar = write_aggregate_with_provenance(artifact, args.output)
    print(f"wrote {output} and {sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
