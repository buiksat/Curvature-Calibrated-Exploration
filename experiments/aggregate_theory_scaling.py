"""Validate and aggregate compact theorem-scaling trajectories."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .config import get_seed_set, load_config
from .theory_scaling import DEFAULT_CONFIG_PATH, METHODS
from .theory_scaling_compact import (
    CHECK_FIELDS,
    PRIMARY_CHECKPOINTS,
    PRIMARY_DIMENSION,
    PRIMARY_HORIZON,
    PRIMARY_RANK,
    compact_run_directory,
    sha256_file,
)


FloatArray = NDArray[np.float64]
BOOTSTRAP_SEED = 20260721
BOOTSTRAP_REPLICATES = 2000


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read valid JSON from {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _validate_sidecar(path: Path) -> str:
    sidecar = path.with_name(path.name + ".sha256")
    try:
        tokens = sidecar.read_text(encoding="ascii").strip().split()
    except OSError as error:
        raise ValueError(f"missing hash sidecar for {path}") from error
    if len(tokens) != 2 or tokens[1] != path.name:
        raise ValueError(f"malformed hash sidecar {sidecar}")
    actual = sha256_file(path)
    if tokens[0] != actual:
        raise ValueError(f"hash mismatch for {path}")
    return actual


def load_compact_run(
    directory: str | Path,
    *,
    method: str,
    seed: int,
    dimension: int,
    rank: int,
    horizon: int,
) -> tuple[dict[str, Any], dict[str, NDArray[np.generic]], dict[str, Any]]:
    root = Path(directory)
    manifest_path = root / "manifest.json"
    summary_path = root / "summary.json"
    rounds_path = root / "rounds.npz"
    hashes = {
        "manifest": _validate_sidecar(manifest_path),
        "summary": _validate_sidecar(summary_path),
        "rounds": _validate_sidecar(rounds_path),
    }
    manifest = _read_json(manifest_path)
    summary = _read_json(summary_path)
    expected = {
        "method": method,
        "seed": seed,
        "ambient_dimension": dimension,
        "active_rank": rank,
        "horizon": horizon,
    }
    for field, value in expected.items():
        if manifest.get(field) != value:
            raise ValueError(
                f"manifest {root} has {field}={manifest.get(field)!r}, expected {value!r}"
            )
    if manifest.get("rounds_sha256") != hashes["rounds"]:
        raise ValueError(f"manifest rounds hash mismatch in {root}")
    if manifest.get("summary_sha256") != hashes["summary"]:
        raise ValueError(f"manifest summary hash mismatch in {root}")
    arrays: dict[str, NDArray[np.generic]] = {}
    try:
        with np.load(rounds_path, allow_pickle=False) as archive:
            for name in archive.files:
                arrays[name] = np.asarray(archive[name]).copy()
    except (OSError, ValueError) as error:
        raise ValueError(f"cannot load compact arrays from {rounds_path}: {error}") from error
    declared = manifest.get("numeric_arrays")
    if not isinstance(declared, Mapping) or set(declared) != set(arrays):
        raise ValueError(f"array schema mismatch in {root}")
    for name, array in arrays.items():
        specification = declared[name]
        if not isinstance(specification, Mapping):
            raise ValueError(f"invalid schema entry {name} in {root}")
        if list(array.shape) != specification.get("shape"):
            raise ValueError(f"array shape mismatch for {name} in {root}")
        if array.shape[0] != horizon:
            raise ValueError(f"array {name} does not contain {horizon} rounds")
    if not np.array_equal(arrays["round"], np.arange(1, horizon + 1)):
        raise ValueError(f"round sequence is incomplete in {root}")
    manifest["verified_file_hashes"] = hashes
    return manifest, arrays, summary


def _stable_rng(seed: int, token: str) -> np.random.Generator:
    digest = hashlib.sha256(f"{seed}:{token}".encode("ascii")).digest()
    derived = int.from_bytes(digest[:8], "little", signed=False)
    return np.random.default_rng(derived)


def _interval_from_samples(values: FloatArray) -> dict[str, float | int]:
    return {
        "mean": float(np.mean(values)),
        "lower_95": float(np.quantile(values, 0.025)),
        "upper_95": float(np.quantile(values, 0.975)),
        "bootstrap_replicates": int(values.size),
    }


def bootstrap_mean_interval(
    values: FloatArray,
    *,
    replicates: int,
    seed: int,
    token: str,
) -> dict[str, float | int]:
    vector = np.asarray(values, dtype=np.float64)
    if vector.ndim != 1 or vector.size == 0 or not np.all(np.isfinite(vector)):
        raise ValueError("bootstrap values must be a nonempty finite vector")
    if replicates <= 0:
        raise ValueError("bootstrap replicates must be positive")
    if vector.size == 1:
        samples = np.repeat(vector, replicates)
    else:
        rng = _stable_rng(seed, token)
        indices = rng.integers(0, vector.size, size=(replicates, vector.size))
        samples = np.mean(vector[indices], axis=1)
    result = _interval_from_samples(samples)
    result["sample_mean"] = float(np.mean(vector))
    result["seed_count"] = int(vector.size)
    return result


def bootstrap_loglog_slope(
    values: FloatArray,
    horizons: Sequence[int],
    *,
    replicates: int,
    seed: int,
    token: str,
) -> dict[str, Any]:
    matrix = np.asarray(values, dtype=np.float64)
    x = np.log(np.asarray(horizons, dtype=np.float64))
    if matrix.ndim != 2 or matrix.shape[1] != x.size:
        raise ValueError("slope values must have shape (seed, horizon)")
    mean_curve = np.mean(matrix, axis=0)
    specification = {
        "regression": "unweighted OLS of log(seed-mean metric) on log(horizon)",
        "horizons": [int(value) for value in horizons],
        "bootstrap": "paired seed resampling; curve is re-averaged before fitting",
    }
    if np.any(mean_curve <= 0.0) or not np.all(np.isfinite(mean_curve)):
        return {
            **specification,
            "status": "undefined_nonpositive_metric",
            "slope": None,
            "lower_95": None,
            "upper_95": None,
            "valid_bootstrap_replicates": 0,
        }
    point = float(np.polyfit(x, np.log(mean_curve), 1)[0])
    rng = _stable_rng(seed, token)
    indices = rng.integers(0, matrix.shape[0], size=(replicates, matrix.shape[0]))
    slopes: list[float] = []
    for sample_indices in indices:
        curve = np.mean(matrix[sample_indices], axis=0)
        if np.all(curve > 0.0) and np.all(np.isfinite(curve)):
            slopes.append(float(np.polyfit(x, np.log(curve), 1)[0]))
    return {
        **specification,
        "status": "ok" if slopes else "undefined_nonpositive_bootstrap_metrics",
        "slope": point,
        "lower_95": float(np.quantile(slopes, 0.025)) if slopes else None,
        "upper_95": float(np.quantile(slopes, 0.975)) if slopes else None,
        "valid_bootstrap_replicates": len(slopes),
    }


def _ratio_summary(numerator: FloatArray, denominator: FloatArray) -> dict[str, Any]:
    valid = np.isfinite(numerator) & np.isfinite(denominator) & (denominator > 0.0)
    ratios = numerator[valid] / denominator[valid]
    if ratios.size == 0:
        return {"count": 0, "mean": None, "median": None, "maximum": None}
    return {
        "count": int(ratios.size),
        "mean": float(np.mean(ratios)),
        "median": float(np.median(ratios)),
        "maximum": float(np.max(ratios)),
    }


def _actual_coverage(cell_root: Path) -> set[tuple[str, int]]:
    result: set[tuple[str, int]] = set()
    if not cell_root.exists():
        return result
    for method_dir in cell_root.iterdir():
        if not method_dir.is_dir():
            continue
        for seed_dir in method_dir.iterdir():
            if seed_dir.is_dir() and seed_dir.name.startswith("seed-"):
                try:
                    seed = int(seed_dir.name.removeprefix("seed-"))
                except ValueError:
                    continue
                result.add((method_dir.name, seed))
    return result


def aggregate_primary_slice(
    root: str | Path,
    *,
    seeds: Sequence[int],
    methods: Sequence[str] = METHODS,
    checkpoints: Sequence[int] = PRIMARY_CHECKPOINTS,
    profile: str = "full",
    seed_set: str = "evaluation",
    dimension: int = PRIMARY_DIMENSION,
    rank: int = PRIMARY_RANK,
    horizon: int = PRIMARY_HORIZON,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
    bootstrap_seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    ordered_seeds = tuple(sorted(int(value) for value in seeds))
    ordered_methods = tuple(methods)
    ordered_checkpoints = tuple(int(value) for value in checkpoints)
    if len(set(ordered_seeds)) != len(ordered_seeds) or not ordered_seeds:
        raise ValueError("expected seeds must be nonempty and unique")
    if len(set(ordered_methods)) != len(ordered_methods) or not ordered_methods:
        raise ValueError("expected methods must be nonempty and unique")
    if set(ordered_methods) - set(METHODS):
        raise ValueError("expected methods contain an unknown method")
    if any(value <= 0 or value > horizon for value in ordered_checkpoints):
        raise ValueError("checkpoints must lie within the maximum horizon")
    cell_root = (
        Path(root)
        / profile
        / seed_set
        / f"d-{dimension}_r-{rank}_T-{horizon}"
    )
    expected_coverage = {
        (method, seed) for method in ordered_methods for seed in ordered_seeds
    }
    actual_coverage = _actual_coverage(cell_root)
    if actual_coverage != expected_coverage:
        missing = sorted(expected_coverage - actual_coverage)
        extra = sorted(actual_coverage - expected_coverage)
        raise ValueError(f"coverage mismatch: missing={missing}, extra={extra}")

    loaded: dict[tuple[str, int], dict[str, NDArray[np.generic]]] = {}
    summaries: dict[tuple[str, int], dict[str, Any]] = {}
    source_hashes: list[dict[str, Any]] = []
    stream_by_seed: dict[int, str] = {}
    for method in ordered_methods:
        for seed in ordered_seeds:
            directory = compact_run_directory(
                root,
                profile=profile,
                seed_set=seed_set,
                dimension=dimension,
                rank=rank,
                horizon=horizon,
                method=method,
                seed=seed,
            )
            manifest, arrays, summary = load_compact_run(
                directory,
                method=method,
                seed=seed,
                dimension=dimension,
                rank=rank,
                horizon=horizon,
            )
            stream = str(manifest["stream_sha256"])
            if seed in stream_by_seed and stream_by_seed[seed] != stream:
                raise ValueError(f"method streams are not paired for seed {seed}")
            stream_by_seed[seed] = stream
            loaded[(method, seed)] = arrays
            summaries[(method, seed)] = summary
            source_hashes.append(
                {
                    "path": str(directory),
                    "method": method,
                    "seed": seed,
                    **manifest["verified_file_hashes"],
                }
            )

    indices = np.asarray(ordered_checkpoints, dtype=np.int64) - 1
    metric_fields = {
        "regret": "cumulative_regret_audit",
        "Lambda": "Lambda_dynamic",
    }
    metric_matrices: dict[str, dict[str, FloatArray]] = {}
    seed_level: list[dict[str, Any]] = []
    for method in ordered_methods:
        metric_matrices[method] = {}
        for metric, field in metric_fields.items():
            matrix = np.stack(
                [
                    np.asarray(loaded[(method, seed)][field], dtype=np.float64)[indices]
                    for seed in ordered_seeds
                ],
                axis=0,
            )
            metric_matrices[method][metric] = matrix
        for seed_index, seed in enumerate(ordered_seeds):
            for checkpoint_index, checkpoint in enumerate(ordered_checkpoints):
                seed_level.append(
                    {
                        "method": method,
                        "seed": seed,
                        "horizon": checkpoint,
                        "regret": float(
                            metric_matrices[method]["regret"][seed_index, checkpoint_index]
                        ),
                        "Lambda": float(
                            metric_matrices[method]["Lambda"][seed_index, checkpoint_index]
                        ),
                    }
                )

    estimates: dict[str, Any] = {}
    reference = "exact_current"
    if reference not in ordered_methods:
        raise ValueError("exact_current is required for paired intervals")
    for method in ordered_methods:
        estimates[method] = {}
        for checkpoint_index, checkpoint in enumerate(ordered_checkpoints):
            horizon_result: dict[str, Any] = {}
            for metric in metric_fields:
                values = metric_matrices[method][metric][:, checkpoint_index]
                paired = values - metric_matrices[reference][metric][:, checkpoint_index]
                horizon_result[metric] = {
                    "mean_interval": bootstrap_mean_interval(
                        values,
                        replicates=bootstrap_replicates,
                        seed=bootstrap_seed,
                        token=f"mean:{method}:{metric}:{checkpoint}",
                    ),
                    "paired_difference_vs_exact_current": bootstrap_mean_interval(
                        paired,
                        replicates=bootstrap_replicates,
                        seed=bootstrap_seed,
                        token=f"paired:{method}:{metric}:{checkpoint}",
                    ),
                }
            estimates[method][str(checkpoint)] = horizon_result

    slopes: dict[str, Any] = {}
    for method in ordered_methods:
        slopes[method] = {
            metric: bootstrap_loglog_slope(
                metric_matrices[method][metric],
                ordered_checkpoints,
                replicates=bootstrap_replicates,
                seed=bootstrap_seed,
                token=f"slope:{method}:{metric}",
            )
            for metric in metric_fields
        }

    tightness: dict[str, Any] = {}
    failures: dict[str, Any] = {}
    for method in ordered_methods:
        concatenated = {
            field: np.concatenate(
                [
                    np.asarray(loaded[(method, seed)][field], dtype=np.float64)
                    for seed in ordered_seeds
                ]
            )
            for field in (
                "chi_exact_float64_audit", "chi_lambda_upper",
                "chi_excitation_upper", "psi_float64_audit",
                "psi_lambda_upper", "psi_excitation_upper",
            )
        }
        tightness[method] = {
            "chi_over_lambda": _ratio_summary(
                concatenated["chi_exact_float64_audit"],
                concatenated["chi_lambda_upper"],
            ),
            "chi_over_excitation": _ratio_summary(
                concatenated["chi_exact_float64_audit"],
                concatenated["chi_excitation_upper"],
            ),
            "psi_over_lambda": _ratio_summary(
                concatenated["psi_float64_audit"],
                concatenated["psi_lambda_upper"],
            ),
            "psi_over_excitation": _ratio_summary(
                concatenated["psi_float64_audit"],
                concatenated["psi_excitation_upper"],
            ),
        }
        failures[method] = {
            field: int(
                sum(
                    np.count_nonzero(
                        ~np.asarray(
                            loaded[(method, seed)][f"check__{field}"], dtype=np.bool_
                        )
                    )
                    for seed in ordered_seeds
                )
            )
            for field in CHECK_FIELDS
        }

    exact_cg: dict[str, Any] | None = None
    if "full_cg" in ordered_methods:
        action_disagreements = 0
        action_total = 0
        width_relative_errors: list[float] = []
        final_regret_differences: list[float] = []
        for seed in ordered_seeds:
            exact_arrays = loaded[("exact_current", seed)]
            cg_arrays = loaded[("full_cg", seed)]
            exact_actions = np.asarray(exact_arrays["action"], dtype=np.int64)
            cg_actions = np.asarray(cg_arrays["action"], dtype=np.int64)
            action_disagreements += int(np.count_nonzero(exact_actions != cg_actions))
            action_total += horizon
            cg_widths = np.asarray(
                cg_arrays["selected_width_squared_pre_action"], dtype=np.float64
            )
            if "selected_exact_operator_width_squared_audit" in cg_arrays:
                cg_exact_selected = np.asarray(
                    cg_arrays["selected_exact_operator_width_squared_audit"],
                    dtype=np.float64,
                )
            else:
                # Backward-compatible recovery for compact schema v1 runs
                # created before the redundant selected-width array was added.
                exact_all = np.asarray(
                    cg_arrays["exact_current_widths_squared_audit"],
                    dtype=np.float64,
                )
                cg_exact_selected = exact_all[np.arange(horizon), cg_actions]
            relative = np.abs(cg_widths - cg_exact_selected) / np.maximum(
                np.abs(cg_exact_selected), np.finfo(np.float64).tiny
            )
            width_relative_errors.extend(relative.tolist())
            final_regret_differences.append(
                float(
                    cg_arrays["cumulative_regret_audit"][-1]
                    - exact_arrays["cumulative_regret_audit"][-1]
                )
            )
        exact_cg = {
            "online_action_disagreement_rate": action_disagreements / action_total,
            "action_count": action_total,
            "selected_width_relative_error_mean_float64_audit": float(
                np.mean(width_relative_errors)
            ),
            "selected_width_relative_error_max_float64_audit": float(
                np.max(width_relative_errors)
            ),
            "final_regret_paired_difference": bootstrap_mean_interval(
                np.asarray(final_regret_differences, dtype=np.float64),
                replicates=bootstrap_replicates,
                seed=bootstrap_seed,
                token="full-vs-cg-final-regret",
            ),
            "semantics": (
                "solver width errors use the CG trajectory's own dense active-coordinate "
                "reference; cross-policy action differences are online outcomes"
            ),
        }

    resources: dict[str, Any] = {}
    for method in ordered_methods:
        runtime = np.asarray(
            [float(summaries[(method, seed)]["runtime_seconds"]) for seed in ordered_seeds],
            dtype=np.float64,
        )
        cg_runtime = np.asarray(
            [
                float(
                    np.sum(
                        np.asarray(
                            loaded[(method, seed)]["cg_seconds"], dtype=np.float64
                        )
                    )
                )
                for seed in ordered_seeds
            ],
            dtype=np.float64,
        )
        sample_cvps = np.asarray(
            [
                float(
                    np.asarray(
                        loaded[(method, seed)]["cumulative_sample_cvp_count"]
                    )[-1]
                )
                for seed in ordered_seeds
            ],
            dtype=np.float64,
        )
        resources[method] = {
            "complete_run_seconds": bootstrap_mean_interval(
                runtime,
                replicates=bootstrap_replicates,
                seed=bootstrap_seed,
                token=f"runtime:{method}",
            ),
            "cg_seconds": bootstrap_mean_interval(
                cg_runtime,
                replicates=bootstrap_replicates,
                seed=bootstrap_seed,
                token=f"cg-runtime:{method}",
            ),
            "sample_cvp_count": bootstrap_mean_interval(
                sample_cvps,
                replicates=bootstrap_replicates,
                seed=bootstrap_seed,
                token=f"sample-cvp:{method}",
            ),
            "timing_semantics": (
                "wall clock from complete runs; concurrent shard contention is not removed"
            ),
        }

    horizon_values = np.asarray(ordered_checkpoints, dtype=np.float64)
    exact_lambda_mean = np.mean(metric_matrices[reference]["Lambda"], axis=0)
    exact_regret_mean = np.mean(metric_matrices[reference]["regret"], axis=0)
    normalizations = {
        "exact_Lambda_over_log_T": (
            exact_lambda_mean / np.log(horizon_values)
        ).tolist(),
        "exact_regret_over_sqrt_T_log_T": (
            exact_regret_mean
            / (np.sqrt(horizon_values) * np.log(horizon_values))
        ).tolist(),
    }
    window_targets = {
        "window_q_1_2": {"q": 0.5, "Lambda_upper_exponent": 0.5, "regret_upper_exponent": 0.75},
        "window_q_2_3": {
            "q": 2.0 / 3.0,
            "Lambda_upper_exponent": 1.0 / 3.0,
            "regret_upper_exponent": 2.0 / 3.0,
        },
        "window_q_1": {"q": 1.0, "Lambda_upper_exponent": 0.0, "regret_upper_exponent": 0.5},
    }
    scaling_hypotheses: dict[str, Any] = {
        "H1_exact_dynamic_width": {
            "prediction": "Lambda_T/log(T) remains bounded",
            "normalization": normalizations["exact_Lambda_over_log_T"],
            "slope": slopes[reference]["Lambda"],
            "interpretation": "finite-horizon scaling diagnostic, not a proof",
        },
        "H2_exact_regret": {
            "prediction": "R_T/(sqrt(T) log(T)) remains bounded",
            "normalization": normalizations["exact_regret_over_sqrt_T_log_T"],
            "slope": slopes[reference]["regret"],
            "interpretation": "finite-horizon scaling diagnostic, not a proof",
        },
        "H3_growing_windows": {},
    }
    for method, target in window_targets.items():
        if method not in slopes:
            continue
        scaling_hypotheses["H3_growing_windows"][method] = {
            **target,
            "observed_Lambda_slope": slopes[method]["Lambda"],
            "observed_regret_slope": slopes[method]["regret"],
            "interpretation": (
                "the theorem gives an asymptotic upper rate, not an equality; "
                "no inferential theorem claim is made from fitted slopes"
            ),
        }
    all_failure_count = sum(
        count for method_counts in failures.values() for count in method_counts.values()
    )
    scaling_hypotheses["H4_certificate_tightness"] = {
        "all_recorded_float64_event_failure_count": all_failure_count,
        "tightness": tightness,
        "interpretation": (
            "event checks are post-hoc float64 point audits; excitation-adapted "
            "schedules remain policy-available analytic quantities"
        ),
    }

    return {
        "schema_version": 1,
        "experiment": "theory_scaling_primary_aggregate",
        "protocol": {
            "profile": profile,
            "seed_set": seed_set,
            "ambient_dimension": dimension,
            "active_rank": rank,
            "maximum_horizon": horizon,
            "checkpoints": list(ordered_checkpoints),
            "methods": list(ordered_methods),
            "seeds": list(ordered_seeds),
            "seed_count": len(ordered_seeds),
            "bootstrap_seed": bootstrap_seed,
            "bootstrap_replicates": bootstrap_replicates,
            "checkpoint_semantics": "prefixes of one maximum-horizon trajectory per method and seed",
        },
        "coverage": {
            "expected_runs": len(expected_coverage),
            "validated_runs": len(actual_coverage),
            "exact": True,
        },
        "seed_level": seed_level,
        "estimates": estimates,
        "slopes": slopes,
        "certificate_tightness_float64_audit": tightness,
        "theorem_event_failure_counts_float64_audit": failures,
        "full_vs_cg": exact_cg,
        "resources": resources,
        "normalizations": normalizations,
        "preregistered_scaling_hypotheses": scaling_hypotheses,
        "source_hashes": source_hashes,
        "numerical_semantics": "float64 audit quantities are not verified enclosures",
    }


def write_aggregate(result: Mapping[str, Any], destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            result, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False
        )
        + "\n"
    )
    with path.open("x", encoding="ascii") as handle:
        handle.write(payload)
    sidecar = path.with_name(path.name + ".sha256")
    sidecar.write_text(f"{sha256_file(path)}  {path.name}\n", encoding="ascii")
    return path


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--profile", choices=("smoke", "full"), default="full")
    parser.add_argument("--seed-set", choices=("development", "tuning", "evaluation"), default="evaluation")
    parser.add_argument("--input-root", type=Path, default=Path("results/raw/theory_scaling_compact"))
    parser.add_argument("--output", type=Path, default=Path("results/derived/theory_scaling_primary.json"))
    parser.add_argument("--bootstrap-replicates", type=int, default=BOOTSTRAP_REPLICATES)
    args = parser.parse_args(argv)
    config = load_config(args.config, profile=args.profile)
    result = aggregate_primary_slice(
        args.input_root,
        seeds=get_seed_set(config, args.seed_set),
        profile=args.profile,
        seed_set=args.seed_set,
        bootstrap_replicates=args.bootstrap_replicates,
    )
    write_aggregate(result, args.output)
    print(json.dumps({"output": str(args.output), "runs": result["coverage"]["validated_runs"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = [
    "BOOTSTRAP_REPLICATES", "BOOTSTRAP_SEED", "aggregate_primary_slice",
    "bootstrap_loglog_slope", "bootstrap_mean_interval", "load_compact_run",
    "write_aggregate",
]
