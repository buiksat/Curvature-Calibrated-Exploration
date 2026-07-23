"""Run the rotated, analytically excited, nontrivial-CG scaling study."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import math
import shutil
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .artifact_utils import sha256_file, write_deterministic_npz, write_json_artifact
from .config import config_digest, get_seed_set, load_config
from .curvature_operators import conjugate_gradient
from .logging_utils import canonical_json, collect_run_metadata, derive_seed, seed_everything


FloatArray = NDArray[np.float64]

WINDOW_METHODS = {
    "window_q_1_2": 0.5,
    "window_q_2_3": 2.0 / 3.0,
    "window_q_1": 1.0,
}
BASE_METHODS = {"exact_current", "full_cg", "frozen", "diagonal", "greedy"}


@dataclass(frozen=True)
class Cell:
    dimension: int
    rank: int
    condition_number: int

    @property
    def token(self) -> str:
        return f"d-{self.dimension}_r-{self.rank}_kappa-{self.condition_number}"


@dataclass(frozen=True)
class ScalingStream:
    active_basis: FloatArray
    cycle_vectors: FloatArray
    parameter: FloatArray
    noises: FloatArray
    minimum_cycle_eigenvalue: float
    stream_sha256: str


@dataclass(frozen=True)
class ScalingTrajectory:
    arrays: dict[str, NDArray[np.generic]]
    summary: dict[str, Any]


def _positive_integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _cells(config: dict[str, Any]) -> tuple[Cell, ...]:
    return tuple(
        Cell(int(dimension), int(rank), int(condition))
        for dimension in config["dimensions"]
        for rank in config["effective_ranks"]
        for condition in config["condition_numbers"]
    )


def validate_scaling_config(config: dict[str, Any]) -> None:
    rounds = _positive_integer(config["rounds"], "rounds")
    horizons = tuple(int(value) for value in config["horizons"])
    if not horizons or sorted(set(horizons)) != list(horizons) or horizons[-1] != rounds:
        raise ValueError("horizons must be strictly increasing and end at rounds")
    dimensions = tuple(int(value) for value in config["dimensions"])
    ranks = tuple(int(value) for value in config["effective_ranks"])
    if any(value <= 0 for value in dimensions + ranks):
        raise ValueError("dimensions and effective ranks must be positive")
    if any(rank > dimension for dimension in dimensions for rank in ranks):
        raise ValueError("every effective rank must fit every dimension")
    conditions = tuple(int(value) for value in config["condition_numbers"])
    if not conditions or any(value <= 1 for value in conditions):
        raise ValueError("condition numbers must exceed one")
    exponents = tuple(float(value) for value in config["window_exponents"])
    if not exponents or any(value <= 0.0 or value > 1.0 for value in exponents):
        raise ValueError("window exponents must lie in (0, 1]")
    methods = tuple(str(value) for value in config["methods"])
    allowed = BASE_METHODS | set(WINDOW_METHODS)
    if not methods or len(set(methods)) != len(methods) or not set(methods) <= allowed:
        raise ValueError("methods contain duplicates or unknown entries")
    expected_windows = {
        method
        for method, exponent in WINDOW_METHODS.items()
        if any(abs(exponent - configured) < 1e-12 for configured in exponents)
    }
    if {method for method in methods if method in WINDOW_METHODS} != expected_windows:
        raise ValueError("window methods and window_exponents disagree")
    if int(config["action_count"]) != 2:
        raise ValueError("the analytic sign-symmetric construction requires two actions")
    for name in (
        "damping",
        "noise_std",
        "parameter_norm",
        "confidence_delta",
        "cg_target_energy_error",
        "optimizer_residual_tolerance",
    ):
        value = float(config[name])
        if not np.isfinite(value) or value <= 0.0:
            raise ValueError(f"{name} must be finite and positive")
    if float(config["confidence_delta"]) >= 1.0:
        raise ValueError("confidence_delta must be below one")
    if float(config["cg_target_energy_error"]) >= 1.0:
        raise ValueError("cg_target_energy_error must be below one")
    if int(config["figure_dimension"]) not in dimensions:
        raise ValueError("figure_dimension must be in dimensions")
    if int(config["figure_condition_number"]) not in conditions:
        raise ValueError("figure_condition_number must be in condition_numbers")


def _digest_arrays(*arrays: NDArray[np.generic]) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(str(tuple(contiguous.shape)).encode("ascii"))
        digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def _orthonormal_columns(rows: int, columns: int, seed: int) -> FloatArray:
    rng = np.random.Generator(np.random.PCG64(seed))
    raw = rng.normal(size=(rows, columns))
    basis, triangular = np.linalg.qr(raw, mode="reduced")
    signs = np.where(np.diag(triangular) < 0.0, -1.0, 1.0)
    return np.asarray(basis * signs, dtype=np.float64)


def generate_scaling_stream(
    config: dict[str, Any], cell: Cell, seed: int
) -> ScalingStream:
    basis = _orthonormal_columns(
        cell.dimension,
        cell.rank,
        derive_seed(seed, "certified-scaling", cell.token, "ambient-basis"),
    )
    mixing = _orthonormal_columns(
        cell.rank,
        cell.rank,
        derive_seed(seed, "certified-scaling", cell.token, "cycle-mixing"),
    )
    eigenvalues = np.geomspace(
        1.0 / float(cell.condition_number), 1.0, cell.rank, dtype=np.float64
    )
    cycle = np.asarray(mixing @ np.diag(np.sqrt(eigenvalues)), dtype=np.float64)
    maximum_norm = float(np.max(np.linalg.norm(cycle, axis=1)))
    cycle /= max(1.0, maximum_norm)
    cycle_gram = cycle.T @ cycle
    minimum = float(np.linalg.eigvalsh(cycle_gram)[0])

    rng = np.random.Generator(
        np.random.PCG64(derive_seed(seed, "certified-scaling", cell.token, "teacher"))
    )
    parameter = np.asarray(rng.normal(size=cell.rank), dtype=np.float64)
    parameter *= float(config["parameter_norm"]) / np.linalg.norm(parameter)
    noises = np.asarray(
        rng.normal(
            scale=float(config["noise_std"]),
            size=(int(config["rounds"]), 2),
        ),
        dtype=np.float64,
    )
    stream_sha = _digest_arrays(basis, cycle, parameter, noises)
    for array in (basis, cycle, parameter, noises):
        array.setflags(write=False)
    return ScalingStream(
        active_basis=basis,
        cycle_vectors=cycle,
        parameter=parameter,
        noises=noises,
        minimum_cycle_eigenvalue=minimum,
        stream_sha256=stream_sha,
    )


def _window_length(round_index: int, exponent: float) -> int:
    history = round_index
    return min(history, int(math.ceil((round_index + 1) ** exponent)))


def _relative_energy_error(
    matrix: FloatArray, exact: FloatArray, approximate: FloatArray
) -> float:
    difference = exact - approximate
    denominator = float(exact @ matrix @ exact)
    numerator = float(difference @ matrix @ difference)
    if denominator <= 0.0:
        return 0.0
    return math.sqrt(max(0.0, numerator) / denominator)


def _cg_widths(
    matrix: FloatArray,
    feature: FloatArray,
    *,
    condition_upper: float,
    energy_target: float,
) -> tuple[FloatArray, NDArray[np.int64], FloatArray, FloatArray, NDArray[np.bool_]]:
    residual_target = energy_target / math.sqrt(condition_upper)

    def matrix_free_matvec(vector: FloatArray) -> FloatArray:
        return matrix @ vector

    widths = np.empty(2, dtype=np.float64)
    iterations = np.empty(2, dtype=np.int64)
    residuals = np.empty(2, dtype=np.float64)
    energy_errors = np.empty(2, dtype=np.float64)
    converged = np.empty(2, dtype=np.bool_)
    for action, sign in enumerate((1.0, -1.0)):
        right_hand_side = sign * feature
        exact = np.linalg.solve(matrix, right_hand_side)
        result = conjugate_gradient(
            matrix_free_matvec,
            right_hand_side,
            tolerance=residual_target,
            max_iterations=8 * matrix.shape[0],
            initial_solution=None,
            raise_on_nonconvergence=False,
        )
        widths[action] = math.sqrt(max(0.0, float(right_hand_side @ result.solution)))
        iterations[action] = result.iterations
        residuals[action] = result.relative_residual_norm
        energy_errors[action] = _relative_energy_error(matrix, exact, result.solution)
        converged[action] = result.converged
    return widths, iterations, residuals, energy_errors, converged


def _rank_information_bound(
    history: int, rank: int, damping: float, variance: float
) -> float:
    if history == 0:
        return 0.0
    effective_rank = min(history, rank)
    return effective_rank * math.log1p(
        history / (effective_rank * damping * variance)
    )


def run_scaling_trajectory(
    config: dict[str, Any],
    cell: Cell,
    stream: ScalingStream,
    *,
    method: str,
) -> ScalingTrajectory:
    rounds = int(config["rounds"])
    damping = float(config["damping"])
    variance = float(config["noise_std"]) ** 2
    parameter_norm = float(config["parameter_norm"])
    delta = float(config["confidence_delta"])
    energy_target = float(config["cg_target_energy_error"])
    optimizer_tolerance = float(config["optimizer_residual_tolerance"])
    exponent = WINDOW_METHODS.get(method)
    if method not in BASE_METHODS and exponent is None:
        raise ValueError(f"unknown method {method!r}")

    active_gram = np.eye(cell.rank, dtype=np.float64) * damping
    response = np.zeros(cell.rank, dtype=np.float64)
    ambient_diagonal = np.full(cell.dimension, damping, dtype=np.float64)
    prefix_grams = np.empty((rounds + 1, cell.rank, cell.rank), dtype=np.float64)
    prefix_grams[0] = 0.0

    cumulative_regret = np.empty(rounds, dtype=np.float64)
    lambda_complexity = np.empty(rounds, dtype=np.float64)
    gamma = np.empty(rounds, dtype=np.float64)
    information_bound = np.empty(rounds, dtype=np.float64)
    confidence_radius = np.empty(rounds, dtype=np.float64)
    h_t = np.empty(rounds, dtype=np.float64)
    selected_width_squared = np.empty(rounds, dtype=np.float64)
    exact_operator_width_squared = np.empty(rounds, dtype=np.float64)
    optimizer_residual = np.empty(rounds, dtype=np.float64)
    excitation_floor = np.full(rounds, np.nan, dtype=np.float64)
    observed_window_minimum = np.full(rounds, np.nan, dtype=np.float64)
    window_length = np.zeros(rounds, dtype=np.int64)
    excitation_required = np.zeros(rounds, dtype=np.bool_)
    excitation_pass = np.ones(rounds, dtype=np.bool_)
    cg_iterations = np.zeros((rounds, 2), dtype=np.int64)
    cg_relative_residual = np.zeros((rounds, 2), dtype=np.float64)
    cg_energy_error = np.zeros((rounds, 2), dtype=np.float64)
    cg_converged = np.ones((rounds, 2), dtype=np.bool_)
    cumulative_sample_cvps = np.zeros(rounds, dtype=np.int64)
    premise_pass = np.ones(rounds, dtype=np.bool_)
    selected_actions = np.empty(rounds, dtype=np.int64)

    regret_total = 0.0
    dynamic_total = 0.0
    work_total = 0
    maximum_h = 0.0
    for round_index in range(rounds):
        history = round_index
        base_feature = stream.cycle_vectors[round_index % cell.rank]
        active_features = np.stack((base_feature, -base_feature))
        true_means = active_features @ stream.parameter
        theta_hat = np.linalg.solve(active_gram, response)
        optimizer_residual[round_index] = float(
            np.linalg.norm(active_gram @ theta_hat - response)
        )
        full_logdet = float(
            np.linalg.slogdet(active_gram)[1] - cell.rank * math.log(damping)
        )
        gamma[round_index] = full_logdet
        information_bound[round_index] = _rank_information_bound(
            history, cell.rank, damping, variance
        )
        beta = math.sqrt(damping) * parameter_norm + math.sqrt(
            2.0 * math.log(1.0 / delta) + full_logdet
        )
        confidence_radius[round_index] = beta

        operator_matrix = active_gram
        operator_history = history
        alpha = 1.0
        if exponent is not None:
            length = _window_length(round_index, exponent)
            window_length[round_index] = length
            operator_matrix = np.eye(cell.rank, dtype=np.float64) * damping
            if length:
                operator_matrix += (
                    prefix_grams[history] - prefix_grams[history - length]
                ) / variance
            operator_history = length
            if length >= 2 * cell.rank:
                excitation_required[round_index] = True
                kappa_w = stream.minimum_cycle_eigenvalue / (
                    2.0 * cell.rank * variance
                )
                lower = damping + kappa_w * length
                observed = float(np.linalg.eigvalsh(operator_matrix)[0])
                excitation_floor[round_index] = lower
                observed_window_minimum[round_index] = observed
                excitation_pass[round_index] = observed + 1e-12 >= lower
        elif method == "diagonal":
            ambient = stream.active_basis @ base_feature
            widths = np.sqrt(
                np.sum(
                    np.stack((ambient, -ambient)) ** 2 / ambient_diagonal,
                    axis=1,
                )
            )
        elif method == "greedy":
            widths = np.zeros(2, dtype=np.float64)

        if method in {"full_cg", *WINDOW_METHODS}:
            condition_upper = 1.0 + operator_history / (damping * variance)
            widths, iterations, residuals, energy_errors, converged = _cg_widths(
                operator_matrix,
                base_feature,
                condition_upper=condition_upper,
                energy_target=energy_target,
            )
            cg_iterations[round_index] = iterations
            cg_relative_residual[round_index] = residuals
            cg_energy_error[round_index] = energy_errors
            cg_converged[round_index] = converged
            alpha = 1.0 / (1.0 - energy_target)
            work_total += int(np.sum(iterations)) * operator_history
        elif method not in {"diagonal", "greedy"}:
            solved = np.linalg.solve(operator_matrix, active_features.T).T
            widths = np.sqrt(
                np.maximum(0.0, np.einsum("ij,ij->i", active_features, solved))
            )

        if method == "diagonal":
            exact_width_squared = float(widths[0] ** 2)
        elif method == "greedy":
            exact_width_squared = 0.0
        else:
            exact_solution = np.linalg.solve(operator_matrix, base_feature)
            exact_width_squared = float(base_feature @ exact_solution)
        scores = active_features @ theta_hat + alpha * beta * widths
        selected = int(np.argmax(scores))
        optimal = int(np.argmax(true_means))
        instantaneous_regret = float(true_means[optimal] - true_means[selected])
        regret_total += instantaneous_regret
        cumulative_regret[round_index] = regret_total
        selected_actions[round_index] = selected
        selected_width_squared[round_index] = float(widths[selected] ** 2)
        exact_operator_width_squared[round_index] = exact_width_squared
        increment = math.log1p(exact_width_squared / variance)
        dynamic_total += increment
        lambda_complexity[round_index] = dynamic_total
        maximum_h = max(maximum_h, alpha * beta)
        h_t[round_index] = maximum_h
        cumulative_sample_cvps[round_index] = work_total

        round_checks = (
            optimizer_residual[round_index] <= optimizer_tolerance
            and gamma[round_index] <= information_bound[round_index] + 1e-10
            and excitation_pass[round_index]
            and (
                method not in {"full_cg", *WINDOW_METHODS}
                or (
                    bool(np.all(cg_converged[round_index]))
                    and float(np.max(cg_energy_error[round_index]))
                    <= energy_target + 1e-10
                )
            )
        )
        premise_pass[round_index] = round_checks

        chosen_feature = active_features[selected]
        reward = float(true_means[selected] + stream.noises[round_index, selected])
        active_gram += np.outer(chosen_feature, chosen_feature) / variance
        response += chosen_feature * reward / variance
        prefix_grams[round_index + 1] = (
            prefix_grams[round_index] + np.outer(chosen_feature, chosen_feature)
        )
        if method == "diagonal":
            ambient_chosen = stream.active_basis @ chosen_feature
            ambient_diagonal += ambient_chosen * ambient_chosen / variance

    multi_iteration_fraction = float(np.mean(np.max(cg_iterations, axis=1) > 1))
    arrays: dict[str, NDArray[np.generic]] = {
        "cumulative_pseudo_regret": cumulative_regret,
        "Lambda_C": lambda_complexity,
        "gamma": gamma,
        "rank_information_bound": information_bound,
        "H_T": h_t,
        "E_T": np.zeros(rounds, dtype=np.float64),
        "bar_chi_t": np.zeros(rounds, dtype=np.float64),
        "confidence_radius": confidence_radius,
        "selected_width_squared": selected_width_squared,
        "exact_operator_width_squared": exact_operator_width_squared,
        "optimizer_residual": optimizer_residual,
        "excitation_floor": excitation_floor,
        "observed_window_minimum": observed_window_minimum,
        "window_length": window_length,
        "excitation_required": excitation_required,
        "excitation_pass": excitation_pass,
        "cg_iterations": cg_iterations,
        "cg_relative_residual": cg_relative_residual,
        "cg_energy_error": cg_energy_error,
        "cg_converged": cg_converged,
        "cumulative_sample_cvps": cumulative_sample_cvps,
        "premise_pass": premise_pass,
        "selected_actions": selected_actions,
    }
    summary = {
        "schema_version": 1,
        "experiment": "certified_scaling",
        "method": method,
        "cell": {
            "dimension": cell.dimension,
            "effective_rank": cell.rank,
            "condition_number": cell.condition_number,
        },
        "rounds": rounds,
        "terminal_pseudo_regret": float(cumulative_regret[-1]),
        "terminal_Lambda_C": float(lambda_complexity[-1]),
        "terminal_gamma": float(gamma[-1]),
        "terminal_H_T": float(h_t[-1]),
        "terminal_E_T": 0.0,
        "maximum_bar_chi_t": 0.0,
        "maximum_optimizer_residual": float(np.max(optimizer_residual)),
        "maximum_cg_energy_error": float(np.max(cg_energy_error)),
        "maximum_cg_relative_residual": float(np.max(cg_relative_residual)),
        "all_cg_solves_converged": bool(np.all(cg_converged)),
        "mean_cg_iterations": float(np.mean(cg_iterations)),
        "multi_iteration_round_fraction": multi_iteration_fraction,
        "sample_cvps": int(cumulative_sample_cvps[-1]),
        "all_required_premises_pass": bool(np.all(premise_pass)),
        "post_burnin_excitation_pass": bool(
            np.all(excitation_pass[excitation_required])
        ),
        "excitation_checked_rounds": int(np.sum(excitation_required)),
        "optimizer": "closed-form ridge solve",
        "feature_drift": "identically zero fixed linear representation",
        "linearization_error": "identically zero",
        "cg_start": "zero",
        "numerical_semantics": "post-hoc float64 audit; analytic excitation floor",
    }
    return ScalingTrajectory(arrays=arrays, summary=summary)


def _run_directory(
    root: Path, profile: str, cell: Cell, method: str, seed: int
) -> Path:
    return root / profile / "evaluation" / cell.token / method / f"seed-{seed}"


def _save_run(
    destination: Path,
    run: ScalingTrajectory,
    *,
    config: dict[str, Any],
    profile: str,
    seed: int,
    stream: ScalingStream,
    metadata: dict[str, Any],
    overwrite: bool,
) -> None:
    if destination.exists():
        if not overwrite:
            raise FileExistsError(f"refusing to overwrite {destination}")
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    rounds_path, _ = write_deterministic_npz(destination / "rounds.npz", run.arrays)
    summary_path, _ = write_json_artifact(destination / "summary.json", run.summary)
    write_json_artifact(
        destination / "manifest.json",
        {
            "schema_version": 1,
            "experiment": "certified_scaling",
            "profile": profile,
            "phase": "evaluation",
            "seed": seed,
            "method": run.summary["method"],
            "config": config,
            "config_digest": config_digest(config),
            "stream_sha256": stream.stream_sha256,
            "rounds_sha256": sha256_file(rounds_path),
            "summary_sha256": sha256_file(summary_path),
            "rng": "numpy.random.Generator(numpy.random.PCG64)",
            "timestamp_utc": dt.datetime.now(dt.timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "selection_protocol": config["selection_protocol"],
            "evaluation_data_used_for_selection": False,
            "provenance": metadata,
        },
    )


def _execute_scaling_task(
    task: tuple[
        dict[str, Any],
        str,
        str,
        int,
        Cell,
        tuple[str, ...],
        dict[str, Any],
        bool,
    ],
) -> tuple[int, int]:
    (
        config,
        profile,
        output_root_text,
        seed,
        cell,
        methods,
        metadata,
        overwrite,
    ) = task
    seed_everything(seed)
    stream = generate_scaling_stream(config, cell, seed)
    clean_count = 0
    for method in methods:
        run = run_scaling_trajectory(config, cell, stream, method=method)
        _save_run(
            _run_directory(Path(output_root_text), profile, cell, method, seed),
            run,
            config=config,
            profile=profile,
            seed=seed,
            stream=stream,
            metadata=metadata,
            overwrite=overwrite,
        )
        clean_count += int(run.summary["all_required_premises_pass"])
    return len(methods), clean_count


def run_evaluation(
    config: dict[str, Any],
    *,
    profile: str,
    output_root: Path,
    overwrite: bool,
    workers: int = 1,
) -> dict[str, Any]:
    validate_scaling_config(config)
    if workers <= 0:
        raise ValueError("workers must be positive")
    seeds = get_seed_set(config, "evaluation")
    metadata = collect_run_metadata(
        repository=Path(__file__).resolve().parents[1],
        packages=tuple(config.get("provenance", {}).get("packages", ())),
    )
    methods = tuple(str(value) for value in config["methods"])
    tasks = [
        (
            config,
            profile,
            output_root.as_posix(),
            seed,
            cell,
            methods,
            metadata,
            overwrite,
        )
        for seed in seeds
        for cell in _cells(config)
    ]
    executor: ProcessPoolExecutor | None = None
    if workers == 1:
        task_results = map(_execute_scaling_task, tasks)
    else:
        executor = ProcessPoolExecutor(max_workers=workers)
        task_results = executor.map(_execute_scaling_task, tasks, chunksize=1)
    count = 0
    clean_count = 0
    try:
        for task_count, task_clean_count in task_results:
            count += task_count
            clean_count += task_clean_count
    finally:
        if executor is not None:
            executor.shutdown()
    return {
        "profile": profile,
        "phase": "evaluation",
        "seeds": list(seeds),
        "run_count": count,
        "premise_clean_run_count": clean_count,
        "workers": workers,
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    config = load_config(args.config, profile=args.profile)
    result = run_evaluation(
        config,
        profile=args.profile,
        output_root=args.output_root,
        overwrite=args.overwrite,
        workers=args.workers,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = [
    "Cell",
    "ScalingStream",
    "ScalingTrajectory",
    "generate_scaling_stream",
    "run_evaluation",
    "run_scaling_trajectory",
    "validate_scaling_config",
]
