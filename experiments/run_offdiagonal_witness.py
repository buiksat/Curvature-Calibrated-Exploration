"""Execute the preregistered off-diagonal linear-Gram witness."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

from .config import get_seed_set, load_config
from .logging_utils import ExperimentLogger, append_jsonl, collect_run_metadata
from .offdiagonal_witness import POLICIES, WitnessProblem, run_witness_policy


DEFAULT_CONFIG = Path(__file__).with_name("configs") / "offdiagonal_witness.yaml"
DEFAULT_OUTPUT = Path("results/raw/offdiagonal_witness")


def _cells(config: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    value = config.get("cells")
    if not isinstance(value, list) or not value:
        raise ValueError("config.cells must be a nonempty list")
    cells: list[dict[str, Any]] = []
    names: set[str] = set()
    for raw in value:
        if not isinstance(raw, Mapping):
            raise ValueError("every witness cell must be an object")
        cell = dict(raw)
        name = str(cell.get("cell", ""))
        if not name or name in names:
            raise ValueError("witness cell names must be nonempty and unique")
        names.add(name)
        cells.append(cell)
    return tuple(cells)


def _methods(config: Mapping[str, Any]) -> tuple[str, ...]:
    value = config.get("methods")
    if not isinstance(value, list) or not value:
        raise ValueError("config.methods must be a nonempty list")
    methods = tuple(str(item) for item in value)
    if len(set(methods)) != len(methods) or any(method not in POLICIES for method in methods):
        raise ValueError("config.methods contains a duplicate or unknown method")
    return methods


def execute(
    config: Mapping[str, Any],
    *,
    seed_set: str,
    output_root: str | Path,
    overwrite: bool = False,
    max_seeds: int | None = None,
    seed_offset: int = 0,
    include_deterministic: bool = True,
) -> tuple[Path, ...]:
    seeds = get_seed_set(config, seed_set)
    if seed_offset < 0 or seed_offset >= len(seeds):
        raise ValueError("seed_offset must index the selected seed set")
    seeds = seeds[seed_offset:]
    if max_seeds is not None:
        if max_seeds <= 0:
            raise ValueError("max_seeds must be positive")
        seeds = seeds[:max_seeds]
    rounds = int(config["rounds"])
    checkpoints = tuple(int(value) for value in config["checkpoints"])
    representative = int(config["representative_seed"])
    output = Path(output_root) / str(config["profile"]) / seed_set
    written: list[Path] = []
    metadata = collect_run_metadata(
        repository=Path(__file__).resolve().parents[1], packages=("numpy", "scipy")
    )

    for cell in _cells(config):
        noise_std = float(cell["noise_std"])
        if noise_std == 0.0 and not include_deterministic:
            continue
        cell_seeds = seeds[:1] if noise_std == 0.0 else seeds
        problem = WitnessProblem(
            damping=float(config["damping"]),
            epsilon=float(config["epsilon"]),
            delta=float(cell["delta"]),
            bonus=float(config["bonus"]),
            angle_degrees=float(cell["angle_degrees"]),
        )
        for method in _methods(config):
            for seed in cell_seeds:
                record_every_round = (
                    str(cell["cell"]) == "analytic" and seed == representative
                )
                started = time.perf_counter()
                run = run_witness_policy(
                    problem,
                    policy=method,  # type: ignore[arg-type]
                    rounds=rounds,
                    seed=seed,
                    noise_std=noise_std,
                    record_every_round=record_every_round,
                    checkpoints=checkpoints,
                )
                elapsed = time.perf_counter() - started
                run_config = copy.deepcopy(dict(config))
                run_config["execution"] = {
                    "seed_set": seed_set,
                    "seed": seed,
                    "cell": cell,
                    "method": method,
                    "record_every_round": record_every_round,
                    "deterministic_cell_executes_once": noise_std == 0.0,
                    "hyperparameter_selection": "none_preregistered_coefficient",
                }
                destination = (
                    output / str(cell["cell"]) / method / f"seed-{seed}"
                )
                if overwrite:
                    for name in ("manifest.jsonl", "raw.jsonl", "summary.jsonl"):
                        (destination / name).unlink(missing_ok=True)
                with ExperimentLogger(
                    destination,
                    run_config,
                    seed,
                    metadata=metadata,
                ) as logger:
                    for record in run.records:
                        round_number = int(record["round"])
                        logger.log_round(round_number, record)
                summary = {
                    "schema_version": 1,
                    "experiment": "offdiagonal_witness",
                    "profile": str(config["profile"]),
                    "seed_set": seed_set,
                    "seed": seed,
                    "cell": str(cell["cell"]),
                    "method": method,
                    "rounds": rounds,
                    "noise_std": noise_std,
                    "delta": problem.delta,
                    "epsilon": problem.epsilon,
                    "angle_degrees": problem.angle_degrees,
                    "bonus": problem.bonus,
                    "final_cumulative_pseudo_regret": float(
                        run.cumulative_regret[-1]
                    ),
                    "suboptimal_pull_count": int((run.actions == 0).sum()),
                    "optimal_pull_count": int((run.actions == 1).sum()),
                    "runtime_seconds": elapsed,
                    "policy_type": "online_executed_policy",
                    "classification": (
                        "analytic_constructive_witness"
                        if noise_std == 0.0
                        else "uncertified_noisy_extension"
                    ),
                    "uniform_transfer_semantics": (
                        "analytic_one_sided_factor"
                        if method == "diagonal_uniform_transfer"
                        else "not_used"
                    ),
                    "dense_reference_semantics": (
                        "pre_action_dense_oracle_not_scalable"
                        if method == "diagonal_actionwise_reference"
                        else "not_used"
                    ),
                }
                append_jsonl(destination / "summary.jsonl", summary)
                written.append(destination)
    return tuple(written)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument(
        "--seed-set",
        choices=("development", "tuning", "evaluation"),
        default="evaluation",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-seeds", type=int)
    parser.add_argument("--seed-offset", type=int, default=0)
    parser.add_argument("--skip-deterministic", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    config = load_config(args.config, profile=args.profile)
    outputs = execute(
        config,
        seed_set=args.seed_set,
        output_root=args.output,
        overwrite=args.overwrite,
        max_seeds=args.max_seeds,
        seed_offset=args.seed_offset,
        include_deterministic=not args.skip_deterministic,
    )
    print(f"wrote {len(outputs)} runs under {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
