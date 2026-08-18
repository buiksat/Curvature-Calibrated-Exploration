"""Run and persist one exact nonlinear confidence-transport trajectory."""

from __future__ import annotations

import argparse
import copy
import json
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .artifact_utils import write_json_artifact
from .config import config_digest, load_config
from .logging_utils import (
    ExperimentLogger,
    canonical_json,
    collect_run_metadata,
    derive_seed,
)
from .transport_instantiation import (
    OptimizerSpec,
    PolicyTrajectory,
    TransportInstantiationError,
    TuningTrajectory,
    canonical_method,
    condition_token,
    run_policy_trajectory,
    run_tuning_trajectory,
)


DEFAULT_CONFIG_PATH = (
    Path(__file__).with_name("configs") / "transport_instantiation.yaml"
)
REQUIRED_RUN_FILES = (
    "manifest.jsonl",
    "raw.jsonl",
    "summary.json",
    "summary.json.sha256",
)


def bootstrap_child_seed(
    config: Mapping[str, Any], horizon: int, target_d: float
) -> int:
    """Return the paired-bootstrap seed used for this reported condition."""

    master = int(config_digest(config)[:16], 16)
    return derive_seed(
        master,
        "transport_instantiation",
        "bootstrap",
        int(horizon),
        float(target_d),
    )


def run_directory(
    output_root: str | Path,
    *,
    phase: str,
    horizon: int,
    target_d: float,
    run_key: str,
    seed: int,
) -> Path:
    """Return the canonical leaf directory for one independent trajectory."""

    if phase not in {"development", "tuning", "evaluation"}:
        raise ValueError("phase must be development, tuning, or evaluation")
    if not run_key or "/" in run_key:
        raise ValueError("run_key must be a nonempty path component")
    return (
        Path(output_root)
        / phase
        / f"T-{int(horizon)}"
        / f"D-{condition_token(target_d)}"
        / run_key
        / f"seed-{int(seed)}"
    )


def _metadata(
    config: Mapping[str, Any],
    *,
    phase: str,
    method: str | None,
    candidate_id: str | None,
    horizon: int,
    target_d: float,
    width: float,
    child_seeds: Mapping[str, int],
    selection_sha256: str | None,
    runtime_seconds: float,
) -> dict[str, Any]:
    execution = config.get("execution")
    packages = (
        tuple(execution.get("packages", ()))
        if isinstance(execution, Mapping)
        else None
    )
    metadata = collect_run_metadata(
        repository=Path(__file__).resolve().parents[1], packages=packages
    )
    recorded_child_seeds = dict(child_seeds)
    recorded_child_seeds["bootstrap_aggregation"] = bootstrap_child_seed(
        config, horizon, target_d
    )
    metadata.update(
        {
            "phase": phase,
            "profile": str(config.get("profile", "unspecified")),
            "method": method,
            "candidate_id": candidate_id,
            "horizon": int(horizon),
            "target_D": float(target_d),
            "W": float(width),
            "selection_sha256": selection_sha256,
            "child_seeds": recorded_child_seeds,
            "config_digest": config_digest(config),
            "runtime_seconds": float(runtime_seconds),
        }
    )
    return metadata


def _prepare_destination(destination: Path, *, overwrite: bool) -> None:
    existing = [destination / name for name in REQUIRED_RUN_FILES if (destination / name).exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "refusing to overwrite an existing run: "
            + ", ".join(str(path) for path in existing)
        )


def save_policy_trajectory(
    trajectory: PolicyTrajectory,
    destination: str | Path,
    config: Mapping[str, Any],
    *,
    phase: str,
    selection_sha256: str | None,
    runtime_seconds: float,
    overwrite: bool,
) -> Path:
    destination_path = Path(destination)
    _prepare_destination(destination_path, overwrite=overwrite)
    metadata = _metadata(
        config,
        phase=phase,
        method=trajectory.method,
        candidate_id=None,
        horizon=trajectory.horizon,
        target_d=trajectory.target_d,
        width=trajectory.width,
        child_seeds=trajectory.child_seeds,
        selection_sha256=selection_sha256,
        runtime_seconds=runtime_seconds,
    )
    logger = ExperimentLogger(
        destination_path,
        config,
        trajectory.seed,
        repository=Path(__file__).resolve().parents[1],
        metadata=metadata,
        overwrite=overwrite,
    )
    try:
        for index, record in enumerate(trajectory.rounds):
            logger.log_round(index, record)
    finally:
        logger.close()

    summary = copy.deepcopy(trajectory.summary)
    summary.update(
        {
            "schema_version": 1,
            "event": "transport_instantiation_summary",
            "phase": phase,
            "profile": str(config.get("profile", "unspecified")),
            "config_digest": config_digest(config),
            "selection_sha256": selection_sha256,
            "optimizer": {
                "learning_rate": trajectory.optimizer.learning_rate,
                "steps_per_round": trajectory.optimizer.steps_per_round,
            },
            "deterministic_audit_pass": bool(
                trajectory.summary.get("deterministic_audit_passed", False)
            ),
            "zero_regret": float(
                trajectory.summary.get("cumulative_pseudo_regret", 0.0)
            )
            == 0.0,
            "runtime_seconds": float(runtime_seconds),
        }
    )
    write_json_artifact(destination_path / "summary.json", summary)
    return destination_path


def save_tuning_trajectory(
    trajectory: TuningTrajectory,
    destination: str | Path,
    config: Mapping[str, Any],
    *,
    candidate_id: str,
    runtime_seconds: float,
    overwrite: bool,
) -> Path:
    destination_path = Path(destination)
    _prepare_destination(destination_path, overwrite=overwrite)
    metadata = _metadata(
        config,
        phase="tuning",
        method=None,
        candidate_id=candidate_id,
        horizon=trajectory.horizon,
        target_d=trajectory.target_d,
        width=trajectory.width,
        child_seeds=trajectory.child_seeds,
        selection_sha256=None,
        runtime_seconds=runtime_seconds,
    )
    logger = ExperimentLogger(
        destination_path,
        config,
        trajectory.seed,
        repository=Path(__file__).resolve().parents[1],
        metadata=metadata,
        overwrite=overwrite,
    )
    try:
        for index, record in enumerate(trajectory.rounds):
            logger.log_round(index, record)
    finally:
        logger.close()

    summary = copy.deepcopy(trajectory.summary)
    summary.update(
        {
            "schema_version": 1,
            "event": "transport_instantiation_tuning_summary",
            "phase": "tuning",
            "profile": str(config.get("profile", "unspecified")),
            "candidate_id": candidate_id,
            "config_digest": config_digest(config),
            "selection_sha256": None,
            "W": trajectory.width,
            "rounds": trajectory.horizon,
            "deterministic_audit_pass": bool(summary.get("valid", False)),
            "deterministic_audit_failure_count": len(
                summary.get("rejection_reasons", ())
            ),
            "runtime_seconds": float(runtime_seconds),
        }
    )
    write_json_artifact(destination_path / "summary.json", summary)
    return destination_path


def run_and_save_policy(
    config: Mapping[str, Any],
    *,
    method: str,
    seed: int,
    horizon: int,
    target_d: float,
    optimizer: OptimizerSpec,
    phase: str,
    diagnostic_mode: str,
    output_root: str | Path,
    selection_sha256: str | None,
    overwrite: bool,
) -> dict[str, Any]:
    canonical = canonical_method(method)
    started = time.perf_counter()
    trajectory = run_policy_trajectory(
        config,
        canonical,
        seed,
        horizon,
        target_d,
        optimizer,
        diagnostic_mode,
    )
    runtime_seconds = time.perf_counter() - started
    destination = run_directory(
        output_root,
        phase=phase,
        horizon=horizon,
        target_d=target_d,
        run_key=canonical,
        seed=seed,
    )
    save_policy_trajectory(
        trajectory,
        destination,
        config,
        phase=phase,
        selection_sha256=selection_sha256,
        runtime_seconds=runtime_seconds,
        overwrite=overwrite,
    )
    if trajectory.summary.get("deterministic_audit_passed") is not True:
        raise TransportInstantiationError(
            f"deterministic audit failed; raw run preserved at {destination}"
        )
    return {"destination": str(destination), **trajectory.summary}


def run_and_save_tuning(
    config: Mapping[str, Any],
    *,
    candidate_id: str,
    seed: int,
    horizon: int,
    target_d: float,
    optimizer: OptimizerSpec,
    output_root: str | Path,
    overwrite: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    trajectory = run_tuning_trajectory(
        config, seed, horizon, target_d, optimizer
    )
    runtime_seconds = time.perf_counter() - started
    destination = run_directory(
        output_root,
        phase="tuning",
        horizon=horizon,
        target_d=target_d,
        run_key=candidate_id,
        seed=seed,
    )
    save_tuning_trajectory(
        trajectory,
        destination,
        config,
        candidate_id=candidate_id,
        runtime_seconds=runtime_seconds,
        overwrite=overwrite,
    )
    return {"destination": str(destination), **trajectory.summary}


def _load_selection_optimizer(path: Path) -> tuple[OptimizerSpec, str]:
    from .artifact_utils import sha256_file, validate_aggregate_provenance_sidecar

    validate_aggregate_provenance_sidecar(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    selected = value.get("selected")
    if not isinstance(selected, Mapping):
        raise ValueError("selection artifact has no selected optimizer")
    return OptimizerSpec.from_mapping(selected), sha256_file(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument(
        "--phase", choices=("development", "evaluation"), default="development"
    )
    parser.add_argument("--method", choices=tuple(canonical_method(name) for name in ("transport_hessian", "transport_endpoint", "frozen_reference", "naive_current")), required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--horizon", type=int, required=True)
    parser.add_argument("--target-D", dest="target_d", type=float, required=True)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--steps-per-round", type=int)
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--diagnostic-mode", default="development")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config, profile=args.profile)
    selection_sha256: str | None = None
    if args.selection is not None:
        optimizer, selection_sha256 = _load_selection_optimizer(args.selection)
    else:
        development = config.get("representation_update", {}).get(
            "development_optimizer", {}
        )
        optimizer = OptimizerSpec(
            learning_rate=(
                args.learning_rate
                if args.learning_rate is not None
                else float(development.get("learning_rate", 0.0001))
            ),
            steps_per_round=(
                args.steps_per_round
                if args.steps_per_round is not None
                else int(development.get("steps_per_round", 5))
            ),
        )
    result = run_and_save_policy(
        config,
        method=args.method,
        seed=args.seed,
        horizon=args.horizon,
        target_d=args.target_d,
        optimizer=optimizer,
        phase=args.phase,
        diagnostic_mode=args.diagnostic_mode,
        output_root=args.output_root,
        selection_sha256=selection_sha256,
        overwrite=args.overwrite,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_CONFIG_PATH",
    "REQUIRED_RUN_FILES",
    "bootstrap_child_seed",
    "run_and_save_policy",
    "run_and_save_tuning",
    "run_directory",
    "save_policy_trajectory",
    "save_tuning_trajectory",
]
