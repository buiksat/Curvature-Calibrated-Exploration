"""Run the preregistered rotated linear spectral-tail bandit study."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import shutil
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .artifact_utils import (
    input_set_sha256,
    sha256_file,
    validate_sha256_sidecar,
    write_deterministic_npz,
    write_json_artifact,
)
from .config import config_digest, get_seed_set, load_config
from .logging_utils import (
    canonical_json,
    collect_run_metadata,
    derive_seed,
    seed_everything,
)


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True)
class Cell:
    rank: int
    spectral_power: int
    alignment: str

    @property
    def token(self) -> str:
        return f"p-{self.spectral_power}_r-{self.rank}_align-{self.alignment}"


@dataclass(frozen=True)
class BanditStream:
    rotation: FloatArray
    coordinates: IntArray
    signs: FloatArray
    noises: FloatArray
    theta: FloatArray
    probabilities: FloatArray
    stream_sha256: str


@dataclass(frozen=True)
class Trajectory:
    arrays: dict[str, NDArray[np.generic]]
    summary: dict[str, Any]


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _float(value: Any, *, name: str, positive: bool = False) -> float:
    result = float(value)
    if not np.isfinite(result) or (positive and result <= 0.0):
        qualifier = "positive " if positive else ""
        raise ValueError(f"{name} must be a finite {qualifier}number")
    return result


def _cells(config: dict[str, Any]) -> tuple[Cell, ...]:
    cells = tuple(
        Cell(int(rank), int(power), str(alignment))
        for rank in config["target_ranks"]
        for power in config["spectral_powers"]
        for alignment in config["gap_alignments"]
    )
    if any(cell.alignment not in {"head", "tail"} for cell in cells):
        raise ValueError("gap_alignments must contain only 'head' or 'tail'")
    if len({cell.token for cell in cells}) != len(cells):
        raise ValueError("spectral-tail cell grid contains duplicates")
    return cells


def validate_study_config(config: dict[str, Any]) -> None:
    dimension = _positive_int(config["dimension"], name="dimension")
    action_count = _positive_int(config["action_count"], name="action_count")
    rounds = _positive_int(config["rounds"], name="rounds")
    if action_count < 2 or action_count > dimension:
        raise ValueError("action_count must lie in [2, dimension]")
    horizons = tuple(int(value) for value in config["horizons"])
    if not horizons or sorted(set(horizons)) != list(horizons):
        raise ValueError("horizons must be a strictly increasing unique list")
    if horizons[-1] != rounds or horizons[0] <= 0:
        raise ValueError("horizons must be positive and end at rounds")
    ranks = tuple(int(value) for value in config["target_ranks"])
    if not ranks or any(rank <= 0 or 2 * rank > dimension for rank in ranks):
        raise ValueError("target ranks must be positive and satisfy 2r <= dimension")
    _float(config["damping"], name="damping", positive=True)
    _float(config["noise_std"], name="noise_std", positive=True)
    _float(config["feature_bound"], name="feature_bound", positive=True)
    _float(config["parameter_norm"], name="parameter_norm", positive=True)
    target = _float(
        config["cg_target_energy_error"],
        name="cg_target_energy_error",
        positive=True,
    )
    if target >= 1.0:
        raise ValueError("cg_target_energy_error must be below one")
    methods = tuple(str(value) for value in config["methods"])
    expected = {
        "exact_dense_full",
        "full_cg",
        "rank_truncation",
        "diagonal",
        "block_diagonal",
        "frequent_directions",
        "greedy",
    }
    if set(methods) != expected or len(methods) != len(expected):
        raise ValueError("methods must contain the complete preregistered method set")
    block_size = _positive_int(config["block_size"], name="block_size")
    if dimension % block_size != 0:
        raise ValueError("block_size must divide dimension")
    bonus_grid = tuple(float(value) for value in config["bonus_grid"])
    if not bonus_grid or any(value < 0.0 or not np.isfinite(value) for value in bonus_grid):
        raise ValueError("bonus_grid must contain finite nonnegative values")
    figure_rank = _positive_int(config["figure_rank"], name="figure_rank")
    if figure_rank not in ranks:
        raise ValueError("figure_rank must be one of target_ranks")
    figure_methods = tuple(str(value) for value in config["figure_methods"])
    if not figure_methods or len(set(figure_methods)) != len(figure_methods):
        raise ValueError("figure_methods must be a nonempty unique list")
    if not set(figure_methods) <= expected:
        raise ValueError("figure_methods must be drawn from methods")
    _cells(config)


def _orthogonal_rotation(dimension: int, seed: int) -> FloatArray:
    rng = np.random.Generator(np.random.PCG64(seed))
    raw = rng.normal(size=(dimension, dimension))
    rotation, triangular = np.linalg.qr(raw)
    signs = np.where(np.diag(triangular) < 0.0, -1.0, 1.0)
    rotation = np.asarray(rotation * signs, dtype=np.float64)
    rotation.setflags(write=False)
    return rotation


def _array_digest(*arrays: NDArray[np.generic]) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(canonical_json(list(contiguous.shape)).encode("ascii"))
        digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def generate_stream(config: dict[str, Any], cell: Cell, seed: int) -> BanditStream:
    dimension = int(config["dimension"])
    action_count = int(config["action_count"])
    rounds = int(config["rounds"])
    rotation = _orthogonal_rotation(
        dimension, derive_seed(seed, "spectral-tail", cell.token, "rotation")
    )
    rng = np.random.Generator(
        np.random.PCG64(derive_seed(seed, "spectral-tail", cell.token, "stream"))
    )
    indices = np.arange(1, dimension + 1, dtype=np.float64)
    weights = np.power(indices, -float(cell.spectral_power))
    probabilities = np.asarray(weights / np.sum(weights), dtype=np.float64)

    support_start = 0 if cell.alignment == "head" else cell.rank
    support = np.arange(support_start, support_start + cell.rank, dtype=np.int64)
    theta = np.zeros(dimension, dtype=np.float64)
    theta[support] = float(config["parameter_norm"]) / np.sqrt(float(cell.rank))

    coordinates = np.empty((rounds, action_count), dtype=np.int64)
    signs = np.empty((rounds, action_count), dtype=np.float64)
    for round_index in range(rounds):
        optimal_coordinate = int(rng.choice(support))
        coordinates[round_index, 0] = optimal_coordinate
        coordinates[round_index, 1] = optimal_coordinate
        signs[round_index, 0] = 1.0
        signs[round_index, 1] = -1.0
        residual_probabilities = probabilities.copy()
        residual_probabilities[optimal_coordinate] = 0.0
        residual_probabilities /= np.sum(residual_probabilities)
        coordinates[round_index, 2:] = rng.choice(
            dimension,
            size=action_count - 2,
            replace=True,
            p=residual_probabilities,
        )
        signs[round_index, 2:] = np.where(
            rng.integers(0, 2, size=action_count - 2, dtype=np.int64) == 0,
            -1.0,
            1.0,
        )
    noises = np.asarray(
        rng.normal(
            loc=0.0,
            scale=float(config["noise_std"]),
            size=(rounds, action_count),
        ),
        dtype=np.float64,
    )
    stream_sha = _array_digest(rotation, coordinates, signs, noises, theta, probabilities)
    for array in (coordinates, signs, noises, theta, probabilities):
        array.setflags(write=False)
    return BanditStream(
        rotation=rotation,
        coordinates=coordinates,
        signs=signs,
        noises=noises,
        theta=theta,
        probabilities=probabilities,
        stream_sha256=stream_sha,
    )


def _cg_budget(condition_number: float, target: float) -> int:
    if condition_number <= 1.0:
        return 1
    root = math.sqrt(condition_number)
    denominator = math.log((root + 1.0) / (root - 1.0))
    return max(1, math.ceil(math.log(2.0 / target) / denominator))


def _tail_alignment(
    coordinates: IntArray,
    signs: FloatArray,
    means: FloatArray,
    rank: int,
) -> float:
    order = np.argsort(-means, kind="stable")
    best, runner = int(order[0]), int(order[1])
    difference: dict[int, float] = {}
    difference[int(coordinates[best])] = float(signs[best])
    difference[int(coordinates[runner])] = difference.get(
        int(coordinates[runner]), 0.0
    ) - float(signs[runner])
    total = sum(value * value for value in difference.values())
    if total == 0.0:
        return 0.0
    tail = sum(
        value * value
        for coordinate, value in difference.items()
        if rank <= coordinate < 2 * rank
    )
    return float(tail / total)


def run_trajectory(
    config: dict[str, Any],
    cell: Cell,
    stream: BanditStream,
    *,
    method: str,
    bonus: float,
) -> Trajectory:
    dimension = int(config["dimension"])
    action_count = int(config["action_count"])
    rounds = int(config["rounds"])
    damping = float(config["damping"])
    variance = float(config["noise_std"]) ** 2
    block_size = int(config["block_size"])
    sketch_rank = min(
        dimension,
        max(1, int(config["sketch_rank_multiplier"]) * cell.rank),
    )
    cg_target = float(config["cg_target_energy_error"])

    counts = np.zeros(dimension, dtype=np.float64)
    response_sum = np.zeros(dimension, dtype=np.float64)
    ambient_diagonal = np.full(dimension, damping, dtype=np.float64)
    block_inverses = (
        [
            np.eye(block_size, dtype=np.float64) / damping
            for _ in range(dimension // block_size)
        ]
        if method == "block_diagonal"
        else []
    )
    fd_weights = np.zeros(dimension, dtype=np.float64)

    cumulative_regret = np.empty(rounds, dtype=np.float64)
    gamma = np.empty(rounds, dtype=np.float64)
    spectral_tail = np.empty(rounds, dtype=np.float64)
    gamma_tail = np.empty(rounds, dtype=np.float64)
    relative_width_error = np.empty(rounds, dtype=np.float64)
    action_disagreement = np.empty(rounds, dtype=np.bool_)
    tail_alignment = np.empty(rounds, dtype=np.float64)
    cg_iterations = np.zeros(rounds, dtype=np.int64)
    cg_relative_residual = np.zeros(rounds, dtype=np.float64)
    cumulative_sample_cvps = np.zeros(rounds, dtype=np.int64)
    selected_actions = np.empty(rounds, dtype=np.int64)
    selected_coordinates = np.empty(rounds, dtype=np.int64)

    regret_total = 0.0
    cvp_total = 0
    for round_index in range(rounds):
        coordinates = stream.coordinates[round_index]
        signs = stream.signs[round_index]
        true_means = signs * stream.theta[coordinates]
        denominators = damping + counts[coordinates] / variance
        estimates = signs * response_sum[coordinates] / denominators
        full_widths = np.sqrt(1.0 / denominators)

        if method in {"exact_dense_full", "full_cg"}:
            widths = full_widths.copy()
        elif method == "rank_truncation":
            widths = np.where(coordinates < cell.rank, full_widths, 0.0)
        elif method == "diagonal":
            columns = stream.rotation[:, coordinates]
            widths = np.sqrt(
                np.sum(columns * columns / ambient_diagonal[:, None], axis=0)
            )
        elif method == "block_diagonal":
            widths_squared = np.zeros(action_count, dtype=np.float64)
            for block_index, inverse in enumerate(block_inverses):
                start = block_index * block_size
                stop = start + block_size
                block = stream.rotation[start:stop, coordinates]
                widths_squared += np.sum(block * (inverse @ block), axis=0)
            widths = np.sqrt(widths_squared)
        elif method == "frequent_directions":
            widths = np.sqrt(1.0 / (damping + fd_weights[coordinates]))
        elif method == "greedy":
            widths = np.zeros(action_count, dtype=np.float64)
        else:
            raise ValueError(f"unknown method {method!r}")

        scores = estimates + bonus * widths
        reference_scores = estimates + bonus * full_widths
        selected = int(np.argmax(scores))
        reference_selected = int(np.argmax(reference_scores))
        optimal = int(np.argmax(true_means))
        order = np.argsort(-true_means, kind="stable")
        regret_total += float(true_means[optimal] - true_means[selected])
        cumulative_regret[round_index] = regret_total
        selected_actions[round_index] = selected
        selected_coordinates[round_index] = int(coordinates[selected])
        action_disagreement[round_index] = selected != reference_selected
        relative_width_error[round_index] = float(
            np.mean(np.abs(widths - full_widths) / np.maximum(full_widths, 1e-15))
        )
        tail_alignment[round_index] = _tail_alignment(
            coordinates, signs, true_means, cell.rank
        )

        if method == "full_cg":
            history = round_index
            condition_upper = 1.0 + history / (damping * variance)
            budget = _cg_budget(condition_upper, cg_target)
            # Every right-hand side is an eigenvector in this spectral study.
            # Zero-start CG is therefore exact in one iteration; the separate
            # certified-scaling study deliberately removes this degeneracy.
            actual_iterations = 1
            cg_iterations[round_index] = actual_iterations
            cg_relative_residual[round_index] = 0.0
            if actual_iterations > budget:
                raise AssertionError("analytic CG budget was violated")
            cvp_total += action_count * history * actual_iterations
        cumulative_sample_cvps[round_index] = cvp_total

        coordinate = int(coordinates[selected])
        sign = float(signs[selected])
        reward = float(true_means[selected] + stream.noises[round_index, selected])
        counts[coordinate] += 1.0
        response_sum[coordinate] += sign * reward / variance

        ambient_feature = sign * stream.rotation[:, coordinate]
        if method == "diagonal":
            ambient_diagonal += ambient_feature * ambient_feature / variance
        elif method == "block_diagonal":
            for block_index, inverse in enumerate(block_inverses):
                start = block_index * block_size
                stop = start + block_size
                vector = ambient_feature[start:stop] / math.sqrt(variance)
                transformed = inverse @ vector
                inverse -= np.outer(transformed, transformed) / (
                    1.0 + vector @ transformed
                )
        elif method == "frequent_directions":
            fd_weights[coordinate] += 1.0 / variance
            positive = fd_weights[fd_weights > 0.0]
            if positive.size > sketch_rank:
                position = positive.size - sketch_rank - 1
                delta = float(np.partition(positive, position)[position])
                fd_weights = np.maximum(fd_weights - delta, 0.0)

        eigenvalues = np.sort(counts / variance)[::-1]
        gamma[round_index] = float(np.sum(np.log1p(eigenvalues / damping)))
        spectral_tail[round_index] = float(np.sum(eigenvalues[cell.rank :]))
        effective_rank = min(cell.rank, round_index + 1)
        head = effective_rank * math.log1p(
            (round_index + 1)
            * float(config["feature_bound"]) ** 2
            / (effective_rank * damping * variance)
        )
        gamma_tail[round_index] = head + spectral_tail[round_index] / damping

    arrays: dict[str, NDArray[np.generic]] = {
        "cumulative_pseudo_regret": cumulative_regret,
        "gamma": gamma,
        "spectral_tail": spectral_tail,
        "gamma_tail": gamma_tail,
        "relative_width_error": relative_width_error,
        "action_disagreement": action_disagreement,
        "tail_alignment": tail_alignment,
        "cg_iterations": cg_iterations,
        "cg_relative_residual": cg_relative_residual,
        "cumulative_sample_cvps": cumulative_sample_cvps,
        "selected_actions": selected_actions,
        "selected_coordinates": selected_coordinates,
    }
    summary = {
        "schema_version": 1,
        "method": method,
        "bonus": bonus,
        "cell": {
            "rank": cell.rank,
            "spectral_power": cell.spectral_power,
            "alignment": cell.alignment,
        },
        "rounds": rounds,
        "terminal_pseudo_regret": float(cumulative_regret[-1]),
        "terminal_gamma": float(gamma[-1]),
        "terminal_spectral_tail": float(spectral_tail[-1]),
        "terminal_gamma_tail": float(gamma_tail[-1]),
        "terminal_gamma_tail_ratio": float(gamma_tail[-1] / max(gamma[-1], 1e-15)),
        "mean_relative_width_error": float(np.mean(relative_width_error)),
        "top_action_disagreement_rate": float(np.mean(action_disagreement)),
        "mean_tail_alignment": float(np.mean(tail_alignment)),
        "maximum_cg_relative_residual": float(np.max(cg_relative_residual)),
        "mean_cg_iterations": float(np.mean(cg_iterations)),
        "sample_cvps": int(cumulative_sample_cvps[-1]),
        "selected_action_sha256": _array_digest(selected_actions),
        "optimal_action_index_is_preregistered_zero": bool(
            np.all(np.argmax(stream.signs * stream.theta[stream.coordinates], axis=1) == 0)
        ),
        "runner_up_index_terminal": int(order[1]),
        "numerical_semantics": "post-hoc float64 audit; no verified enclosure",
    }
    return Trajectory(arrays=arrays, summary=summary)


def _run_directory(
    root: Path,
    profile: str,
    phase: str,
    seed: int,
    cell: Cell,
    method: str,
    bonus: float,
) -> Path:
    bonus_token = f"{bonus:.8g}".replace(".", "p")
    return (
        root
        / profile
        / phase
        / f"seed-{seed}"
        / cell.token
        / method
        / f"bonus-{bonus_token}"
    )


def _save_trajectory(
    destination: Path,
    trajectory: Trajectory,
    *,
    config: dict[str, Any],
    profile: str,
    phase: str,
    seed: int,
    stream: BanditStream,
    metadata: dict[str, Any],
    overwrite: bool,
) -> tuple[Path, Path, Path]:
    if destination.exists():
        if not overwrite:
            raise FileExistsError(f"refusing to overwrite {destination}")
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    rounds_path, _ = write_deterministic_npz(
        destination / "rounds.npz", trajectory.arrays
    )
    summary_path, _ = write_json_artifact(
        destination / "summary.json", trajectory.summary
    )
    manifest = {
        "schema_version": 1,
        "experiment": "spectral_tail_study",
        "profile": profile,
        "phase": phase,
        "seed": seed,
        "config_digest": config_digest(config),
        "config": config,
        "stream_sha256": stream.stream_sha256,
        "rounds_sha256": sha256_file(rounds_path),
        "summary_sha256": sha256_file(summary_path),
        "rng": "numpy.random.Generator(numpy.random.PCG64)",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "provenance": metadata,
    }
    manifest_path, _ = write_json_artifact(destination / "manifest.json", manifest)
    return rounds_path, summary_path, manifest_path


def _load_selection(path: Path, config: dict[str, Any], profile: str) -> dict[str, float]:
    validate_sha256_sidecar(path)
    selection = json.loads(path.read_text(encoding="ascii"))
    if selection.get("experiment") != "spectral_tail_study":
        raise ValueError("selection artifact belongs to a different experiment")
    if selection.get("profile") != profile:
        raise ValueError("selection profile does not match the requested profile")
    if selection.get("config_digest") != config_digest(config):
        raise ValueError("selection config digest does not match")
    expected_tuning = list(get_seed_set(config, "tuning"))
    expected_evaluation = list(get_seed_set(config, "evaluation"))
    if selection.get("tuning_seeds") != expected_tuning:
        raise ValueError("selection does not contain the complete tuning seed set")
    if set(expected_tuning) & set(expected_evaluation):
        raise ValueError("tuning and evaluation seeds overlap")
    selected = selection.get("selected_bonus")
    if not isinstance(selected, dict):
        raise ValueError("selection artifact has no selected_bonus mapping")
    methods = tuple(str(value) for value in config["methods"])
    if set(selected) != set(methods):
        raise ValueError("selection does not cover every method")
    return {method: float(selected[method]) for method in methods}


def _execute_phase_task(
    task: tuple[
        dict[str, Any],
        str,
        str,
        str,
        int,
        Cell,
        tuple[str, ...],
        tuple[float, ...],
        dict[str, float],
        dict[str, Any],
        bool,
    ],
) -> tuple[list[dict[str, str]], list[tuple[str, float, float]]]:
    (
        config,
        profile,
        phase,
        output_root_text,
        seed,
        cell,
        methods,
        bonus_grid,
        selected_bonus,
        metadata,
        overwrite,
    ) = task
    seed_everything(seed)
    stream = generate_stream(config, cell, seed)
    source_inputs: list[dict[str, str]] = []
    objective_records: list[tuple[str, float, float]] = []
    output_root = Path(output_root_text)
    for method in methods:
        bonuses = (
            (selected_bonus[method],)
            if phase == "evaluation"
            else ((0.0,) if method == "greedy" else bonus_grid)
        )
        for bonus in bonuses:
            trajectory = run_trajectory(
                config, cell, stream, method=method, bonus=bonus
            )
            destination = _run_directory(
                output_root, profile, phase, seed, cell, method, bonus
            )
            paths = _save_trajectory(
                destination,
                trajectory,
                config=config,
                profile=profile,
                phase=phase,
                seed=seed,
                stream=stream,
                metadata=metadata,
                overwrite=overwrite,
            )
            for path in paths:
                source_inputs.append(
                    {"path": path.as_posix(), "sha256": sha256_file(path)}
                )
            if phase == "tuning":
                objective_records.append(
                    (
                        method,
                        bonus,
                        float(trajectory.summary["terminal_pseudo_regret"]),
                    )
                )
    return source_inputs, objective_records


def run_phase(
    config: dict[str, Any],
    *,
    profile: str,
    phase: str,
    output_root: Path,
    selection_path: Path,
    overwrite: bool,
    workers: int = 1,
) -> dict[str, Any]:
    validate_study_config(config)
    if phase not in {"tuning", "evaluation"}:
        raise ValueError("phase must be tuning or evaluation")
    if workers <= 0:
        raise ValueError("workers must be positive")
    seeds = get_seed_set(config, phase)
    methods = tuple(str(value) for value in config["methods"])
    bonus_grid = tuple(float(value) for value in config["bonus_grid"])
    if phase == "evaluation":
        selected_bonus = _load_selection(selection_path, config, profile)
    else:
        selected_bonus = {}

    metadata = collect_run_metadata(
        repository=Path(__file__).resolve().parents[1],
        packages=tuple(config.get("provenance", {}).get("packages", ())),
    )
    source_inputs: list[dict[str, str]] = []
    objective: dict[str, dict[float, list[float]]] = {
        method: {} for method in methods
    }
    tasks = [
        (
            config,
            profile,
            phase,
            output_root.as_posix(),
            seed,
            cell,
            methods,
            bonus_grid,
            selected_bonus,
            metadata,
            overwrite,
        )
        for seed in seeds
        for cell in _cells(config)
    ]
    executor: ProcessPoolExecutor | None = None
    if workers == 1:
        task_results = map(_execute_phase_task, tasks)
    else:
        executor = ProcessPoolExecutor(max_workers=workers)
        task_results = executor.map(_execute_phase_task, tasks, chunksize=1)
    try:
        for task_inputs, task_objectives in task_results:
            source_inputs.extend(task_inputs)
            for method, bonus, regret in task_objectives:
                objective[method].setdefault(bonus, []).append(regret)
    finally:
        if executor is not None:
            executor.shutdown()

    result = {
        "phase": phase,
        "profile": profile,
        "seeds": list(seeds),
        "run_count": sum(
            1
            for item in source_inputs
            if item["path"].endswith("manifest.json")
        ),
        "input_set_sha256": input_set_sha256(source_inputs),
        "workers": workers,
    }
    if phase == "tuning":
        choices: dict[str, float] = {}
        diagnostics: dict[str, Any] = {}
        for method in methods:
            means = {
                bonus: float(np.mean(values))
                for bonus, values in sorted(objective[method].items())
            }
            best = min(means, key=lambda bonus: (means[bonus], bonus))
            choices[method] = float(best)
            diagnostics[method] = {
                "mean_terminal_pseudo_regret_by_bonus": {
                    f"{bonus:.8g}": value for bonus, value in means.items()
                },
                "selected_bonus": float(best),
            }
        selection = {
            "schema_version": 1,
            "experiment": "spectral_tail_study",
            "profile": profile,
            "config_digest": config_digest(config),
            "tuning_seeds": list(get_seed_set(config, "tuning")),
            "evaluation_seeds": list(get_seed_set(config, "evaluation")),
            "selection_rule": config["selection_rule"],
            "selected_bonus": choices,
            "diagnostics": diagnostics,
            "raw_inputs": sorted(source_inputs, key=lambda item: item["path"]),
            "input_set_sha256": input_set_sha256(source_inputs),
            "evaluation_data_accessed": False,
            "workers": workers,
        }
        if selection_path.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite {selection_path}")
        write_json_artifact(selection_path, selection)
        result["selection"] = selection_path.as_posix()
    return result


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument("--phase", choices=("tuning", "evaluation"), required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    config = load_config(args.config, profile=args.profile)
    result = run_phase(
        config,
        profile=args.profile,
        phase=args.phase,
        output_root=args.output_root,
        selection_path=args.selection,
        overwrite=args.overwrite,
        workers=args.workers,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = [
    "BanditStream",
    "Cell",
    "Trajectory",
    "generate_stream",
    "run_phase",
    "run_trajectory",
    "validate_study_config",
]
