#!/usr/bin/env python3
"""Independently replay terminal paired-bootstrap intervals from a compact export.

This verifies exported bytes and numerical summaries, not absent raw trajectories
or the truth of the server's provenance attestation. No experiment module imports.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

import numpy as np


class ExportError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ExportError(message)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def close(actual: object, expected: float, label: str) -> None:
    require(isinstance(actual, (int, float)) and not isinstance(actual, bool),
            f"{label}: expected a finite number")
    require(math.isfinite(float(actual)) and math.isclose(
        float(actual), expected, rel_tol=1e-12, abs_tol=1e-12),
        f"{label}: exported {actual}, recomputed {expected}")


def verify_export(directory: Path) -> dict[str, object]:
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "export_manifest.json").read_text())
    require(manifest.get("schema_version") == 1, "Unsupported export schema")
    entries = manifest["files"]
    names: set[str] = set()
    for item in entries:
        name = item["path"]
        require(isinstance(name, str) and Path(name).name == name
                and name not in {"", ".", "..", "export_manifest.json"},
                "Export manifest paths must be plain file names")
        require(name not in names, f"Duplicate manifest path: {name}")
        names.add(name)
        path = directory / name
        require(path.is_file() and not path.is_symlink(), f"Missing regular export file: {name}")
        raw = path.read_bytes()
        require(len(raw) == item["bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"],
                f"Export hash/size mismatch: {name}")
    needed = {"execution_config.json", "seed_summaries.jsonl", "aggregate_compact.json", "selection.json"}
    require(needed <= names, f"Required export files missing: {sorted(needed - names)}")
    actual_files = {path.name for path in directory.iterdir()}
    require(actual_files == names | {"export_manifest.json"}, "Export contains unlisted files")
    config_bytes = (directory / "execution_config.json").read_bytes()
    require(hashlib.sha256(config_bytes).hexdigest() == manifest["source"]["execution_sha256"],
            "Execution configuration differs from export source binding")
    config = json.loads(config_bytes)
    aggregate = json.loads((directory / "aggregate_compact.json").read_text())
    digest = hashlib.sha256(canonical(config)).hexdigest()
    require(aggregate["config_digest"] == digest, "Aggregate configuration digest mismatch")
    selection_sha = hashlib.sha256((directory / "selection.json").read_bytes()).hexdigest()
    require(aggregate["selection_sha256"] == selection_sha, "Aggregate selection digest mismatch")
    seeds = config["seed_sets"]["evaluation"]
    methods = config["methods"]
    horizons = config["horizons"]
    targets = [float(value) for value in config["target_D"]]
    for label, values in (("seeds", seeds), ("methods", methods), ("horizons", horizons), ("targets", targets)):
        require(bool(values) and len(values) == len(set(values)), f"Empty/duplicate {label}")
    require("transport_hessian" in methods, "Missing paired reference method")
    require(aggregate["evaluation_seeds"] == seeds and aggregate["methods"] == methods
            and aggregate["horizons"] == horizons and aggregate["target_D"] == targets,
            "Aggregate grid differs from execution configuration")
    expected = set(itertools.product(horizons, targets, methods, seeds))
    rows: dict[tuple, dict] = {}
    for line_number, line in enumerate((directory / "seed_summaries.jsonl").read_text().splitlines(), 1):
        row = json.loads(line)
        key = (row["horizon"], float(row["target_D"]), row["method"], row["seed"])
        require(key in expected and key not in rows, f"Unexpected/duplicate seed summary at line {line_number}")
        require(row["phase"] == "evaluation" and row["config_digest"] == digest
                and row["selection_sha256"] == selection_sha,
                f"Seed summary provenance mismatch at line {line_number}")
        require(math.isfinite(float(row["cumulative_pseudo_regret"])), f"Nonfinite regret at line {line_number}")
        rows[key] = row
    require(set(rows) == expected, f"Seed grid incomplete: missing {len(expected - set(rows))} rows")
    require(aggregate["expected_run_count"] == len(expected)
            and aggregate["completed_run_count"] == len(expected)
            and aggregate["full_grid_complete"] is True, "Aggregate completeness counts differ")

    primary = config["reporting"]["primary_horizon"]
    require(primary in horizons, "Primary horizon missing from grid")
    resamples = config["statistics"]["paired_bootstrap_resamples"]
    level = config["statistics"]["paired_bootstrap_level"]
    require(type(resamples) is int and 0 < resamples <= 1_000_000
            and 0.0 < level < 1.0, "Invalid bootstrap settings")
    bootstrap = aggregate["paired_bootstrap"]
    require(bootstrap["resamples"] == resamples and bootstrap["level"] == level,
            "Exported bootstrap settings differ from configuration")
    child_seeds = {(item["horizon"], float(item["target_D"])): item["seed"]
                   for item in bootstrap["child_seeds"]}
    require(len(child_seeds) == len(bootstrap["child_seeds"])
            and set(child_seeds) == {(primary, target) for target in targets},
            "Bootstrap child-seed grid differs")
    outcomes: dict[tuple, dict] = {}
    for item in aggregate["policy_outcomes"]:
        key = (item["horizon"], float(item["target_D"]), item["method"])
        require(key not in outcomes, "Duplicate policy outcome")
        outcomes[key] = item
    require(set(outcomes) == set(itertools.product([primary], targets, methods)),
            "Policy outcome grid differs")

    checked = 0
    for target in targets:
        seed_payload = [int(digest[:16], 16), "transport_instantiation", "bootstrap", primary, target]
        child = int.from_bytes(hashlib.sha256(canonical(seed_payload)).digest()[:4], "big")
        require(child_seeds[primary, target] == child, "Bootstrap child seed is not config-derived")
        # Reproduce the declared random draws directly, independently of the
        # aggregator's multiplicity matrix implementation.
        indices = np.random.default_rng(child).integers(
            0, len(seeds), size=(resamples, len(seeds)), dtype=np.int64)
        reference = np.array([rows[primary, target, "transport_hessian", seed]["cumulative_pseudo_regret"]
                              for seed in seeds], dtype=np.float64)
        for method in methods:
            values = np.array([rows[primary, target, method, seed]["cumulative_pseudo_regret"]
                               for seed in seeds], dtype=np.float64)
            outcome = outcomes[primary, target, method]
            require(outcome["run_count"] == len(seeds), "Policy run count differs")
            for name, series in (("cumulative_pseudo_regret", values),
                                 ("paired_difference_from_transport_hessian", values - reference)):
                record = outcome[name]
                interval = record["bootstrap_mean_interval"]
                require(interval["resamples"] == resamples and interval["level"] == level
                        and interval["method"] == "deterministic_seed_paired_bootstrap",
                        "Policy bootstrap protocol differs")
                mean = float(np.mean(series))
                draws = np.mean(series[indices], axis=1)
                alpha = (1.0 - level) / 2.0
                low, high = np.quantile(draws, (alpha, 1.0 - alpha))
                label = f"T={primary} D={target} {method} {name}"
                close(record["mean"], mean, label + " mean")
                close(interval["mean"], mean, label + " bootstrap mean")
                close(interval["ci_low"], float(low), label + " lower CI")
                close(interval["ci_high"], float(high), label + " upper CI")
                require(len(interval["ci"]) == 2, label + " CI must have two endpoints")
                close(interval["ci"][0], float(low), label + " CI[0]")
                close(interval["ci"][1], float(high), label + " CI[1]")
                checked += 1
    return {"status": "pass", "seed_summaries": len(rows), "terminal_intervals_recomputed": checked,
            "raw_trajectories": "not included; not independently verified",
            "per_round_intervals": "not included; not recomputed",
            "provenance_scope": "exported file hashes and config/selection bindings; no external authenticity attestation"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        report = verify_export(args.directory)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Export verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
