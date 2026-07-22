"""Compact raw runner for the primary theorem-scaling slice.

Every method/seed pair is executed once at the maximum horizon. Checkpoint
statistics are extracted later by :mod:`experiments.aggregate_theory_scaling`.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import sys
import zipfile
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .config import config_digest, get_seed_set, load_config
from .logging_utils import collect_run_metadata
from .theory_scaling import (
    DEFAULT_CONFIG_PATH,
    METHODS,
    TheoryScalingRun,
    run_theory_scaling_cell,
)


PRIMARY_DIMENSION = 128
PRIMARY_RANK = 4
PRIMARY_HORIZON = 2048
PRIMARY_CHECKPOINTS = (128, 256, 512, 1024, 2048)
SCHEMA_VERSION = 1

SCALAR_FIELDS = (
    "round", "action", "optimal_action_audit", "reward",
    "realized_noise_audit", "instantaneous_regret_audit",
    "cumulative_regret_audit", "selected_width_squared_pre_action",
    "selected_exact_operator_width_squared_audit",
    "dynamic_width_increment", "Lambda_dynamic", "endpoint_logdet",
    "variation_charge", "dynamic_width_upper",
    "relative_refresh_norm_float64_audit", "nu_analytic_upper",
    "refresh_log_upper", "refresh_log_upper_valid",
    "gamma_frozen_float64_audit", "gamma_rank_upper",
    "lambda_min_current_active_float64_audit",
    "lambda_min_frozen_active_float64_audit",
    "lambda_min_window_active_float64_audit", "window_length",
    "window_exponent", "excitation_floor_pre_action",
    "excitation_schedule_active", "optimizer_increment",
    "scaled_optimizer_increment",
    "optimizer_residual_pre_action_float64_audit",
    "optimizer_residual_schedule_pre_action", "optimizer_residual_next",
    "optimizer_iterations", "strong_convexity_min_eigenvalue_float64_audit",
    "estimation_error_float64_audit", "Q_t", "chi_exact_float64_audit",
    "chi_lambda_upper", "chi_excitation_upper", "psi_float64_audit",
    "psi_lambda_upper", "psi_excitation_upper", "M_upper",
    "E_true_float64_audit", "F_true_float64_audit", "E_upper", "F_upper",
    "beta_rank_pre_action", "transfer_factor_pre_action",
    "optimism_violation_count_audit", "cg_condition_upper",
    "cg_relative_residual", "cg_residual_certificate",
    "cg_energy_error_float64_audit", "sample_cvp_count",
    "cumulative_sample_cvp_count", "cg_seconds", "round_seconds",
    "all_float64_audit_checks_hold",
)
VECTOR_FIELDS = (
    "scores_pre_action", "bonuses_pre_action",
    "exact_current_widths_squared_audit", "cg_iterations",
)
CHECK_FIELDS = (
    "rank_information", "chi_lambda", "chi_excitation", "psi_lambda",
    "psi_excitation", "linearization", "optimizer_residual", "F",
    "dynamic_width", "cg",
)


def _peak_host_memory_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _strict_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False
        )
        + "\n"
    ).encode("ascii")


def _write_bytes_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)


def _write_hash_sidecar(path: Path) -> Path:
    sidecar = path.with_name(path.name + ".sha256")
    _write_bytes_exclusive(
        sidecar, f"{sha256_file(path)}  {path.name}\n".encode("ascii")
    )
    return sidecar


def write_deterministic_npz(
    path: str | Path, arrays: Mapping[str, NDArray[np.generic]]
) -> Path:
    """Write an ``np.load``-compatible compressed archive with fixed metadata."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite {destination}")
    with destination.open("xb") as raw_handle:
        with zipfile.ZipFile(
            raw_handle,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            strict_timestamps=True,
        ) as archive:
            for name in sorted(arrays):
                array = np.asarray(arrays[name])
                if array.dtype.hasobject:
                    raise TypeError(f"array {name!r} has object dtype")
                buffer = io.BytesIO()
                np.lib.format.write_array(buffer, array, allow_pickle=False)
                info = zipfile.ZipInfo(
                    f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0)
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(
                    info,
                    buffer.getvalue(),
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )
    return destination


def records_to_numeric_arrays(
    run: TheoryScalingRun,
) -> dict[str, NDArray[np.generic]]:
    if not run.records:
        raise ValueError("run has no round records")
    arrays: dict[str, NDArray[np.generic]] = {}
    for field in SCALAR_FIELDS:
        values = [record[field] for record in run.records]
        if any(value is None for value in values):
            arrays[field] = np.asarray(
                [np.nan if value is None else value for value in values],
                dtype=np.float64,
            )
        elif all(isinstance(value, (bool, np.bool_)) for value in values):
            arrays[field] = np.asarray(values, dtype=np.bool_)
        elif all(isinstance(value, (int, np.integer)) for value in values):
            arrays[field] = np.asarray(values, dtype=np.int64)
        else:
            arrays[field] = np.asarray(values, dtype=np.float64)
    for field in VECTOR_FIELDS:
        arrays[field] = np.asarray(
            [record[field] for record in run.records], dtype=np.float64
        )
    for field in CHECK_FIELDS:
        arrays[f"check__{field}"] = np.asarray(
            [
                record["theorem_event_checks_float64_audit"][field]
                for record in run.records
            ],
            dtype=np.bool_,
        )
    if not np.array_equal(
        arrays["round"], np.arange(1, run.horizon + 1, dtype=np.int64)
    ):
        raise ValueError("round records are incomplete or out of order")
    return arrays


def compact_run_directory(
    root: str | Path,
    *,
    profile: str,
    seed_set: str,
    dimension: int,
    rank: int,
    horizon: int,
    method: str,
    seed: int,
) -> Path:
    return (
        Path(root)
        / profile
        / seed_set
        / f"d-{dimension}_r-{rank}_T-{horizon}"
        / method
        / f"seed-{seed}"
    )


def save_compact_run(
    run: TheoryScalingRun,
    config: Mapping[str, Any],
    destination: str | Path,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> Path:
    output = Path(destination)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty directory {output}")
    output.mkdir(parents=True, exist_ok=True)
    arrays = records_to_numeric_arrays(run)
    rounds_path = write_deterministic_npz(output / "rounds.npz", arrays)
    summary_path = output / "summary.json"
    _write_bytes_exclusive(summary_path, _strict_json_bytes(run.summary))
    provenance = dict(
        metadata
        if metadata is not None
        else collect_run_metadata(
            repository=Path(__file__).resolve().parents[1],
            packages=("numpy", "scipy", "psutil"),
        )
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "theory_scaling_compact",
        "seed": run.seed,
        "method": run.method,
        "ambient_dimension": run.ambient_dimension,
        "active_rank": run.active_rank,
        "horizon": run.horizon,
        "stream_sha256": run.stream_sha256,
        "config_digest": config_digest(config),
        "config": config,
        "numeric_arrays": {
            name: {"dtype": str(array.dtype), "shape": list(array.shape)}
            for name, array in sorted(arrays.items())
        },
        "rounds_sha256": sha256_file(rounds_path),
        "summary_sha256": sha256_file(summary_path),
        "checkpoint_semantics": (
            "all checkpoints are prefixes of this one maximum-horizon online trajectory"
        ),
        "numerical_semantics": (
            "float64 audit arrays are point diagnostics, not verified enclosures"
        ),
        "provenance": provenance,
    }
    manifest_path = output / "manifest.json"
    _write_bytes_exclusive(manifest_path, _strict_json_bytes(manifest))
    for path in (rounds_path, summary_path, manifest_path):
        _write_hash_sidecar(path)
    return output


def run_primary_compact_protocol(
    config: Mapping[str, Any],
    *,
    output_root: str | Path,
    seeds: Sequence[int] | None = None,
    methods: Sequence[str] = METHODS,
    dimension: int = PRIMARY_DIMENSION,
    rank: int = PRIMARY_RANK,
    horizon: int = PRIMARY_HORIZON,
    seed_set: str = "evaluation",
) -> tuple[Path, ...]:
    selected_seeds = tuple(seeds or get_seed_set(config, seed_set))
    selected_methods = tuple(methods)
    if len(set(selected_seeds)) != len(selected_seeds):
        raise ValueError("seeds contain duplicates")
    if len(set(selected_methods)) != len(selected_methods):
        raise ValueError("methods contain duplicates")
    unknown = set(selected_methods) - set(METHODS)
    if unknown:
        raise ValueError(f"unknown methods: {sorted(unknown)}")
    destinations: list[Path] = []
    protocol_metadata = collect_run_metadata(
        repository=Path(__file__).resolve().parents[1],
        packages=("numpy", "scipy", "psutil"),
    )
    protocol_metadata["execution_environment"] = {
        name: os.environ.get(name)
        for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
    }
    for seed in selected_seeds:
        for method in selected_methods:
            run_config = json.loads(json.dumps(config))
            run_config["execution"] = {
                "seed_set": seed_set,
                "method": method,
                "ambient_dimension": dimension,
                "active_rank": rank,
                "maximum_horizon": horizon,
                "checkpoint_horizons": [
                    checkpoint
                    for checkpoint in PRIMARY_CHECKPOINTS
                    if checkpoint <= horizon
                ],
                "single_trajectory": True,
            }
            run = run_theory_scaling_cell(
                run_config,
                int(seed),
                method=method,
                ambient_dimension=dimension,
                active_rank=rank,
                horizon=horizon,
            )
            run.summary["peak_host_memory_bytes"] = _peak_host_memory_bytes()
            run.summary["peak_host_memory_scope"] = (
                "process_lifetime_high_water_mark"
            )
            destination = compact_run_directory(
                output_root,
                profile=str(config.get("profile", "unknown")),
                seed_set=seed_set,
                dimension=dimension,
                rank=rank,
                horizon=horizon,
                method=method,
                seed=int(seed),
            )
            save_compact_run(
                run, run_config, destination, metadata=protocol_metadata
            )
            destinations.append(destination)
    return tuple(destinations)


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--profile", choices=("smoke", "full"), default="full")
    parser.add_argument(
        "--seed-set",
        choices=("development", "tuning", "evaluation"),
        default="evaluation",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("results/raw/theory_scaling_compact"),
    )
    parser.add_argument("--method", action="append", choices=METHODS)
    parser.add_argument("--seed", action="append", type=int)
    parser.add_argument("--seed-offset", type=int, default=0)
    parser.add_argument("--max-seeds", type=int)
    parser.add_argument("--dimension", type=int, default=PRIMARY_DIMENSION)
    parser.add_argument("--rank", type=int, default=PRIMARY_RANK)
    parser.add_argument("--horizon", type=int, default=PRIMARY_HORIZON)
    args = parser.parse_args(argv)
    config = load_config(args.config, profile=args.profile)
    if args.seed_offset < 0:
        parser.error("--seed-offset must be nonnegative")
    if args.max_seeds is not None and args.max_seeds <= 0:
        parser.error("--max-seeds must be positive")
    if args.seed is not None and (args.seed_offset or args.max_seeds is not None):
        parser.error("explicit --seed cannot be combined with seed slicing")
    selected_seeds = args.seed
    if selected_seeds is None and (args.seed_offset or args.max_seeds is not None):
        declared = get_seed_set(config, args.seed_set)
        stop = (
            None
            if args.max_seeds is None
            else args.seed_offset + args.max_seeds
        )
        selected_seeds = list(declared[args.seed_offset:stop])
        if not selected_seeds:
            parser.error("seed slice is empty")
    paths = run_primary_compact_protocol(
        config,
        output_root=args.output_root,
        seeds=selected_seeds,
        methods=tuple(args.method or METHODS),
        dimension=args.dimension,
        rank=args.rank,
        horizon=args.horizon,
        seed_set=args.seed_set,
    )
    print(
        json.dumps(
            {"runs": len(paths), "output_root": str(args.output_root)},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = [
    "CHECK_FIELDS", "PRIMARY_CHECKPOINTS", "PRIMARY_DIMENSION",
    "PRIMARY_HORIZON", "PRIMARY_RANK", "SCALAR_FIELDS", "VECTOR_FIELDS",
    "compact_run_directory", "records_to_numeric_arrays",
    "run_primary_compact_protocol", "save_compact_run", "sha256_file",
    "write_deterministic_npz",
]
