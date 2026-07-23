"""Run the finite-support scaled-tanh theorem-instantiation study."""

from __future__ import annotations

import argparse
import copy
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
    sha256_file,
    validate_sha256_sidecar,
    write_deterministic_npz,
    write_json_artifact,
)
from .config import config_digest, get_seed_set, load_config
from .curvature_operators import conjugate_gradient
from .logging_utils import canonical_json, collect_run_metadata, derive_seed, seed_everything


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
BoolArray = NDArray[np.bool_]

METHODS = {
    "exact_current_relative",
    "full_cg_relative",
    "current_welford",
    "corrected_current",
    "frozen_neuralucb",
    "diagonal_current",
    "frozen_linear_ucb",
    "greedy",
}
THEOREM_METHODS = {
    "exact_current_relative",
    "full_cg_relative",
    "current_welford",
    "corrected_current",
}


@dataclass(frozen=True)
class Cell:
    horizon: int
    width_ratio: float
    width: float
    residual_factor: float

    @property
    def token(self) -> str:
        ratio = format(self.width_ratio, ".12g").replace(".", "p")
        return f"T-{self.horizon}_ratio-{ratio}"


@dataclass(frozen=True)
class ScaledTanhEnvironment:
    features: FloatArray
    active_features: FloatArray
    teacher: FloatArray
    optimal_actions: IntArray
    minimum_gap: float
    digest: str


@dataclass(frozen=True)
class ScaledTanhStream:
    contexts: IntArray
    noises: FloatArray
    digest: str


@dataclass(frozen=True)
class ScaledTanhTrajectory:
    arrays: dict[str, NDArray[np.generic]]
    summary: dict[str, Any]


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _positive_float(value: Any, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _digest_arrays(*arrays: NDArray[np.generic]) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(str(tuple(contiguous.shape)).encode("ascii"))
        digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def residual_factor(config: dict[str, Any], horizon: int) -> float:
    bound = float(config["feature_bound"]) * float(config["trust_region_radius"])
    sigma = float(config["noise_std"])
    delta = float(config["residual_failure_delta"])
    return max(1.0, 8.0 * bound * bound + 4.0 * sigma * sigma * math.log(2.0 * horizon / delta))


def cells(config: dict[str, Any]) -> tuple[Cell, ...]:
    result = []
    for horizon in config["horizons"]:
        factor = residual_factor(config, int(horizon))
        for ratio in config["width_ratios"]:
            result.append(
                Cell(
                    horizon=int(horizon),
                    width_ratio=float(ratio),
                    width=float(ratio) * int(horizon) * factor,
                    residual_factor=factor,
                )
            )
    return tuple(result)


def optimizer_selection_cells(config: dict[str, Any]) -> tuple[Cell, ...]:
    selection = config["optimizer_selection"]
    result = []
    for horizon in selection["horizons"]:
        factor = residual_factor(config, int(horizon))
        for ratio in selection["width_ratios"]:
            result.append(
                Cell(
                    horizon=int(horizon),
                    width_ratio=float(ratio),
                    width=float(ratio) * int(horizon) * factor,
                    residual_factor=factor,
                )
            )
    return tuple(result)


def validate_config(config: dict[str, Any]) -> None:
    dimension = _positive_int(config["dimension"], name="dimension")
    rank = _positive_int(config["effective_rank"], name="effective_rank")
    actions = _positive_int(config["action_count"], name="action_count")
    contexts = _positive_int(config["context_count"], name="context_count")
    if rank > dimension:
        raise ValueError("effective_rank must not exceed dimension")
    if actions < 2 or contexts < actions:
        raise ValueError("the construction requires at least two actions and one context per action")
    horizons = tuple(int(value) for value in config["horizons"])
    if not horizons or sorted(set(horizons)) != list(horizons):
        raise ValueError("horizons must be nonempty and strictly increasing")
    ratios = tuple(float(value) for value in config["width_ratios"])
    if not ratios or any(not np.isfinite(value) or value <= 0.0 for value in ratios):
        raise ValueError("width_ratios must be finite and positive")
    methods = tuple(str(value) for value in config["methods"])
    if not methods or len(methods) != len(set(methods)) or not set(methods) <= METHODS:
        raise ValueError("methods contain duplicates or unknown entries")
    for name in (
        "damping",
        "noise_std",
        "teacher_norm",
        "trust_region_radius",
        "feature_bound",
        "confidence_delta",
        "residual_failure_delta",
        "optimizer_zeta0",
        "optimizer_armijo",
        "optimizer_backtracking",
        "cg_target_energy_error",
        "score_tie_tolerance",
    ):
        _positive_float(config[name], name=name)
    if float(config["teacher_norm"]) > float(config["trust_region_radius"]):
        raise ValueError("teacher must lie in the trust region")
    if float(config["feature_bound"]) < 1.0:
        raise ValueError("the fixed construction has unit-norm active features")
    for name in ("confidence_delta", "residual_failure_delta", "cg_target_energy_error"):
        if float(config[name]) >= 1.0:
            raise ValueError(f"{name} must be smaller than one")
    if not 0.0 < float(config["optimizer_backtracking"]) < 1.0:
        raise ValueError("optimizer_backtracking must lie in (0, 1)")
    _positive_int(config["optimizer_max_iterations"], name="optimizer_max_iterations")
    selection = config.get("optimizer_selection")
    if not isinstance(selection, dict):
        raise ValueError("optimizer_selection must be an object")
    candidates = tuple(float(value) for value in selection.get("damping_candidates", ()))
    if not candidates or any(not np.isfinite(value) or value <= 0.0 for value in candidates):
        raise ValueError("optimizer damping candidates must be finite and positive")
    if len(set(candidates)) != len(candidates) or list(candidates) != sorted(candidates):
        raise ValueError("optimizer damping candidates must be unique and increasing")
    if float(config["damping"]) not in candidates:
        raise ValueError("configured damping must be one optimizer-selection candidate")
    if selection.get("method") != "exact_current_relative":
        raise ValueError("optimizer selection must use exact_current_relative")
    if selection.get("evaluation_metrics_read") is not False:
        raise ValueError("optimizer selection must forbid evaluation metrics")
    for name in ("horizons", "width_ratios"):
        if not selection.get(name):
            raise ValueError(f"optimizer_selection.{name} must not be empty")


def _scaled_tanh(q: FloatArray, width: float) -> FloatArray:
    return np.asarray(math.sqrt(width) * np.tanh(q / math.sqrt(width)), dtype=np.float64)


def _scaled_tanh_prime(q: FloatArray, width: float) -> FloatArray:
    value = np.tanh(q / math.sqrt(width))
    return np.asarray(1.0 - value * value, dtype=np.float64)


def _scaled_tanh_second(q: FloatArray, width: float) -> FloatArray:
    root = math.sqrt(width)
    value = np.tanh(q / root)
    return np.asarray(-2.0 * value * (1.0 - value * value) / root, dtype=np.float64)


def _stable_argmax(values: FloatArray, *, tolerance: float) -> int:
    maximum = float(np.max(values))
    threshold = tolerance * max(1.0, abs(maximum))
    candidates = np.flatnonzero(maximum - values <= threshold)
    if candidates.size == 0:
        raise FloatingPointError("argmax candidate set is empty")
    return int(candidates[0])


def make_environment(config: dict[str, Any]) -> ScaledTanhEnvironment:
    validate_config(config)
    dimension = int(config["dimension"])
    rank = int(config["effective_rank"])
    actions = int(config["action_count"])
    contexts = int(config["context_count"])
    rng = np.random.Generator(np.random.PCG64(int(config["environment_seed"])))
    active = np.empty((contexts, actions, rank), dtype=np.float64)
    optimal = np.arange(contexts, dtype=np.int64) % actions
    for context in range(contexts):
        for action in range(actions):
            score = 0.8 if action == int(optimal[context]) else 0.18 - 0.01 * ((action - context) % actions)
            nuisance = rng.normal(size=rank - 1)
            nuisance /= np.linalg.norm(nuisance)
            active[context, action, 0] = score
            active[context, action, 1:] = math.sqrt(max(0.0, 1.0 - score * score)) * nuisance
    features = np.zeros((contexts, actions, dimension), dtype=np.float64)
    features[:, :, :rank] = active
    teacher = np.zeros(rank, dtype=np.float64)
    teacher[0] = float(config["teacher_norm"])
    reference_width = max(cell.width for cell in cells(config))
    means = _scaled_tanh(active @ teacher, reference_width)
    inferred = np.argmax(means, axis=1).astype(np.int64)
    if not np.array_equal(inferred, optimal):
        raise AssertionError("the fixed environment does not have the designated optimal actions")
    sorted_means = np.sort(means, axis=1)
    minimum_gap = float(np.min(sorted_means[:, -1] - sorted_means[:, -2]))
    if minimum_gap <= 0.0 or len(set(optimal.tolist())) != actions:
        raise AssertionError("the support must have positive gaps and multiple optimal actions")
    if np.linalg.matrix_rank(active.reshape(-1, rank), tol=1e-12) != rank:
        raise AssertionError("the active feature support does not span the supplied rank")
    digest = _digest_arrays(features, teacher, optimal)
    for array in (features, active, teacher, optimal):
        array.setflags(write=False)
    return ScaledTanhEnvironment(
        features=features,
        active_features=active,
        teacher=teacher,
        optimal_actions=optimal,
        minimum_gap=minimum_gap,
        digest=digest,
    )


def make_stream(config: dict[str, Any], cell: Cell, seed: int) -> ScaledTanhStream:
    context_rng = np.random.Generator(
        np.random.PCG64(derive_seed(seed, "scaled-tanh-instantiation", "contexts"))
    )
    noise_rng = np.random.Generator(
        np.random.PCG64(derive_seed(seed, "scaled-tanh-instantiation", "noise"))
    )
    contexts = np.asarray(
        context_rng.integers(0, int(config["context_count"]), size=cell.horizon),
        dtype=np.int64,
    )
    noises = np.asarray(
        noise_rng.normal(
            scale=float(config["noise_std"]),
            size=(cell.horizon, int(config["action_count"])),
        ),
        dtype=np.float64,
    )
    digest = _digest_arrays(contexts, noises)
    contexts.setflags(write=False)
    noises.setflags(write=False)
    return ScaledTanhStream(contexts=contexts, noises=noises, digest=digest)


def _objective_terms(
    theta: FloatArray,
    features: FloatArray,
    counts: FloatArray,
    reward_sums: FloatArray,
    reward_square_sums: FloatArray,
    *,
    width: float,
    damping: float,
    variance: float,
) -> tuple[float, FloatArray, FloatArray]:
    q = features @ theta
    means = _scaled_tanh(q, width)
    derivatives = _scaled_tanh_prime(q, width)
    second = _scaled_tanh_second(q, width)
    residual_sums = counts * means - reward_sums
    objective = float(
        (
            np.sum(counts * means * means - 2.0 * reward_sums * means + reward_square_sums)
            / (2.0 * variance)
        )
        + 0.5 * damping * float(theta @ theta)
    )
    gradient = np.asarray(
        features.T @ (residual_sums * derivatives) / variance + damping * theta,
        dtype=np.float64,
    )
    weights = (counts * derivatives * derivatives + residual_sums * second) / variance
    hessian = np.asarray(
        features.T @ (weights[:, None] * features)
        + damping * np.eye(theta.size, dtype=np.float64),
        dtype=np.float64,
    )
    return objective, gradient, hessian


def optimize_full_history(
    initial: FloatArray,
    features: FloatArray,
    counts: FloatArray,
    reward_sums: FloatArray,
    reward_square_sums: FloatArray,
    *,
    width: float,
    damping: float,
    variance: float,
    radius: float,
    target_residual: float,
    maximum_iterations: int,
    armijo: float,
    backtracking: float,
) -> tuple[FloatArray, float, int, bool]:
    theta = np.asarray(initial, dtype=np.float64).copy()
    norm = float(np.linalg.norm(theta))
    if norm > radius:
        theta *= radius / norm
    completed = 0
    for completed in range(maximum_iterations + 1):
        objective, gradient, hessian = _objective_terms(
            theta,
            features,
            counts,
            reward_sums,
            reward_square_sums,
            width=width,
            damping=damping,
            variance=variance,
        )
        residual = float(np.linalg.norm(gradient))
        if residual <= target_residual:
            return theta, residual, completed, True
        if completed == maximum_iterations:
            break
        hessian = 0.5 * (hessian + hessian.T)
        minimum = float(np.linalg.eigvalsh(hessian)[0])
        if minimum <= 1e-10:
            hessian = hessian + (1e-8 - minimum) * np.eye(theta.size)
        try:
            direction = np.linalg.solve(hessian, -gradient)
        except np.linalg.LinAlgError:
            direction = -gradient
        directional = float(gradient @ direction)
        if not np.isfinite(directional) or directional >= 0.0:
            direction = -gradient
        step = 1.0
        accepted = False
        for _ in range(50):
            candidate = theta + step * direction
            candidate_norm = float(np.linalg.norm(candidate))
            if candidate_norm > radius:
                candidate *= radius / candidate_norm
            projected_step = candidate - theta
            projected_directional = float(gradient @ projected_step)
            if projected_directional >= 0.0:
                step *= backtracking
                continue
            candidate_objective, _, _ = _objective_terms(
                candidate,
                features,
                counts,
                reward_sums,
                reward_square_sums,
                width=width,
                damping=damping,
                variance=variance,
            )
            if candidate_objective <= objective + armijo * projected_directional:
                theta = candidate
                accepted = True
                break
            step *= backtracking
        if not accepted:
            break
    _, final_gradient, _ = _objective_terms(
        theta,
        features,
        counts,
        reward_sums,
        reward_square_sums,
        width=width,
        damping=damping,
        variance=variance,
    )
    residual = float(np.linalg.norm(final_gradient))
    return theta, residual, completed, residual <= target_residual


def _inverse_root(matrix: FloatArray) -> FloatArray:
    values, vectors = np.linalg.eigh(matrix)
    if values[0] <= 0.0:
        raise FloatingPointError("curvature is not positive definite")
    return np.asarray((vectors * (1.0 / np.sqrt(values))) @ vectors.T, dtype=np.float64)


def _rank_information_bound(history: int, rank: int, damping: float, variance: float) -> float:
    if history == 0:
        return 0.0
    effective = min(history, rank)
    return float(effective * math.log1p(history / (effective * damping * variance)))


def _cg_widths(
    matrix: FloatArray,
    queries: FloatArray,
    *,
    history: int,
    variance: float,
    damping: float,
    energy_target: float,
) -> tuple[FloatArray, IntArray, FloatArray, FloatArray, BoolArray]:
    condition_upper = 1.0 + history / (damping * variance)
    residual_target = energy_target / math.sqrt(condition_upper)
    widths = np.empty(queries.shape[0], dtype=np.float64)
    iterations = np.empty(queries.shape[0], dtype=np.int64)
    residuals = np.empty(queries.shape[0], dtype=np.float64)
    errors = np.empty(queries.shape[0], dtype=np.float64)
    converged = np.empty(queries.shape[0], dtype=np.bool_)
    for action, query in enumerate(queries):
        exact = np.linalg.solve(matrix, query)
        solved = conjugate_gradient(
            lambda vector: matrix @ vector,
            query,
            tolerance=residual_target,
            max_iterations=4 * matrix.shape[0],
            initial_solution=None,
            raise_on_nonconvergence=False,
        )
        value = float(query @ solved.solution)
        widths[action] = max(0.0, value)
        iterations[action] = solved.iterations
        original_residual = query - matrix @ solved.solution
        query_norm = float(np.linalg.norm(query))
        residuals[action] = (
            float(np.linalg.norm(original_residual)) / query_norm
            if query_norm > 0.0
            else 0.0
        )
        difference = exact - solved.solution
        denominator = float(exact @ matrix @ exact)
        errors[action] = math.sqrt(max(0.0, float(difference @ matrix @ difference)) / denominator) if denominator > 0.0 else 0.0
        converged[action] = solved.converged and residuals[action] <= residual_target
    return widths, iterations, residuals, errors, converged


def run_trajectory(
    config: dict[str, Any],
    cell: Cell,
    environment: ScaledTanhEnvironment,
    stream: ScaledTanhStream,
    *,
    method: str,
) -> ScaledTanhTrajectory:
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    horizon = cell.horizon
    dimension = int(config["dimension"])
    rank = int(config["effective_rank"])
    actions = int(config["action_count"])
    damping = float(config["damping"])
    sigma = float(config["noise_std"])
    variance = sigma * sigma
    radius = float(config["trust_region_radius"])
    teacher_norm = float(config["teacher_norm"])
    delta = float(config["confidence_delta"])
    zeta0 = float(config["optimizer_zeta0"])
    cg_target = float(config["cg_target_energy_error"])
    c_h = 4.0 / (3.0 * math.sqrt(3.0))
    lipschitz = c_h / math.sqrt(cell.width)
    rho_w = math.exp(4.0 * radius / math.sqrt(cell.width)) - 1.0
    epsilon_bound = 2.0 * c_h * radius * radius / math.sqrt(cell.width)
    category_features = environment.active_features.reshape(-1, rank)
    category_count = category_features.shape[0]

    counts = np.zeros(category_count, dtype=np.float64)
    reward_sums = np.zeros(category_count, dtype=np.float64)
    reward_square_sums = np.zeros(category_count, dtype=np.float64)
    sum_hprime = np.zeros(category_count, dtype=np.float64)
    sum_hprime_squared = np.zeros(category_count, dtype=np.float64)
    sum_hprime_residual = np.zeros(category_count, dtype=np.float64)
    sum_hprime_squared_q = np.zeros(category_count, dtype=np.float64)
    minimum_hprime = np.full(category_count, np.inf, dtype=np.float64)
    maximum_hprime = np.zeros(category_count, dtype=np.float64)
    frozen_active = damping * np.eye(rank, dtype=np.float64)
    frozen_response = np.zeros(rank, dtype=np.float64)
    linear_active = damping * np.eye(rank, dtype=np.float64)
    linear_response = np.zeros(rank, dtype=np.float64)
    theta = np.zeros(rank, dtype=np.float64)
    path_count = 0
    path_mean = np.zeros(rank, dtype=np.float64)
    path_scatter = 0.0
    collection_residual_energy = 0.0
    f_bar = 0.0
    e_bar = 0.0
    f_exact = 0.0
    e_exact = 0.0

    cumulative_regret = np.empty(horizon, dtype=np.float64)
    theorem_rhs = np.full(horizon, np.nan, dtype=np.float64)
    rhs_per_round = np.full(horizon, np.nan, dtype=np.float64)
    rhs_regret_ratio = np.full(horizon, np.nan, dtype=np.float64)
    exact_chi = np.empty(horizon, dtype=np.float64)
    old_chi = np.empty(horizon, dtype=np.float64)
    exact_rho = np.empty(horizon, dtype=np.float64)
    analytic_rho = np.full(horizon, rho_w, dtype=np.float64)
    exact_psi = np.empty(horizon, dtype=np.float64)
    relative_psi = np.empty(horizon, dtype=np.float64)
    old_psi = np.empty(horizon, dtype=np.float64)
    exact_linearization = np.empty(horizon, dtype=np.float64)
    linearization_bound = np.full(horizon, epsilon_bound, dtype=np.float64)
    gamma = np.empty(horizon, dtype=np.float64)
    gamma_tail = np.empty(horizon, dtype=np.float64)
    gamma_split = np.empty(horizon, dtype=np.float64)
    optimizer_residual = np.empty(horizon, dtype=np.float64)
    optimizer_iterations = np.empty(horizon, dtype=np.int64)
    optimizer_pass = np.empty(horizon, dtype=np.bool_)
    confidence_event = np.empty(horizon, dtype=np.bool_)
    optimism_event = np.empty(horizon, dtype=np.bool_)
    premise_pass = np.empty(horizon, dtype=np.bool_)
    selected_actions = np.empty(horizon, dtype=np.int64)
    cg_iterations = np.zeros((horizon, actions), dtype=np.int64)
    cg_residual = np.zeros((horizon, actions), dtype=np.float64)
    cg_energy_error = np.zeros((horizon, actions), dtype=np.float64)
    cg_converged = np.ones((horizon, actions), dtype=np.bool_)
    cumulative_cvps = np.zeros(horizon, dtype=np.int64)
    dense_width_squared = np.empty((horizon, actions), dtype=np.float64)
    computed_width_squared = np.empty((horizon, actions), dtype=np.float64)
    transfer_pass = np.empty(horizon, dtype=np.bool_)
    centering_pass = np.empty(horizon, dtype=np.bool_)
    linearization_pass = np.empty(horizon, dtype=np.bool_)
    information_pass = np.empty(horizon, dtype=np.bool_)
    endpoint_information_pass = np.empty(horizon, dtype=np.bool_)
    old_transfer_pass = np.empty(horizon, dtype=np.bool_)
    old_centering_pass = np.empty(horizon, dtype=np.bool_)
    regret_bound_pass = np.empty(horizon, dtype=np.bool_)
    path_q = np.empty(horizon, dtype=np.float64)
    residual_energy_prefix = np.empty(horizon, dtype=np.float64)
    residual_energy_envelope = np.empty(horizon, dtype=np.float64)
    residual_envelope_pass = np.empty(horizon, dtype=np.bool_)
    residual_energy_through_round = np.empty(horizon, dtype=np.float64)
    residual_envelope_through_round = np.empty(horizon, dtype=np.float64)
    residual_endpoint_pass = np.empty(horizon, dtype=np.bool_)
    exact_e_prefix = np.empty(horizon, dtype=np.float64)
    predictable_e_prefix = np.empty(horizon, dtype=np.float64)
    exact_e_through_round = np.empty(horizon, dtype=np.float64)
    predictable_e_through_round = np.empty(horizon, dtype=np.float64)
    exact_f_prefix = np.empty(horizon, dtype=np.float64)
    predictable_f_prefix = np.empty(horizon, dtype=np.float64)
    exact_f_next = np.empty(horizon, dtype=np.float64)
    predictable_f_next = np.empty(horizon, dtype=np.float64)
    gamma_endpoint = np.empty(horizon, dtype=np.float64)
    gamma_tail_endpoint = np.empty(horizon, dtype=np.float64)
    gamma_split_endpoint = np.empty(horizon, dtype=np.float64)
    rhs_information_term = np.full(horizon, np.nan, dtype=np.float64)
    rhs_factor_sum = np.full(horizon, np.nan, dtype=np.float64)
    rhs_width_potential = np.full(horizon, np.nan, dtype=np.float64)
    rhs_statistical_component = np.full(horizon, np.nan, dtype=np.float64)
    rhs_linearization_component = np.full(horizon, np.nan, dtype=np.float64)

    regret_total = 0.0
    factor_sum = 0.0
    dynamic_sum = 0.0
    work_total = 0
    cell_minimum_gap = math.nan
    for round_index in range(horizon):
        history = round_index
        target_residual = zeta0 / math.sqrt(cell.width)
        theta, residual, iterations, converged_optimizer = optimize_full_history(
            theta,
            category_features,
            counts,
            reward_sums,
            reward_square_sums,
            width=cell.width,
            damping=damping,
            variance=variance,
            radius=radius,
            target_residual=target_residual,
            maximum_iterations=int(config["optimizer_max_iterations"]),
            armijo=float(config["optimizer_armijo"]),
            backtracking=float(config["optimizer_backtracking"]),
        )
        optimizer_residual[round_index] = residual
        optimizer_iterations[round_index] = iterations
        optimizer_pass[round_index] = converged_optimizer and residual <= target_residual * (1.0 + 1e-8)

        all_q = category_features @ theta
        all_means = _scaled_tanh(all_q, cell.width)
        all_hprime = _scaled_tanh_prime(all_q, cell.width)
        current_weights = counts * all_hprime * all_hprime
        current_active = np.asarray(
            damping * np.eye(rank) + category_features.T @ (current_weights[:, None] * category_features) / variance,
            dtype=np.float64,
        )
        drift_weights = counts * all_hprime * all_hprime - 2.0 * all_hprime * sum_hprime + sum_hprime_squared
        drift_weights = np.maximum(drift_weights, 0.0)
        drift_gram = category_features.T @ (drift_weights[:, None] * category_features) / variance
        inverse_root = _inverse_root(frozen_active)
        whitened_drift_gram = inverse_root @ drift_gram @ inverse_root
        chi = math.sqrt(max(0.0, float(np.linalg.eigvalsh(whitened_drift_gram)[-1])))
        exact_chi[round_index] = chi

        observed = counts > 0.0
        if np.any(observed):
            ratios_min = all_hprime[observed] / minimum_hprime[observed]
            ratios_max = all_hprime[observed] / maximum_hprime[observed]
            rho = float(max(np.max(np.abs(ratios_min - 1.0)), np.max(np.abs(ratios_max - 1.0))))
        else:
            rho = 0.0
        exact_rho[round_index] = rho
        q_path = path_scatter + path_count * float((theta - path_mean) @ (theta - path_mean))
        q_path = max(0.0, q_path)
        path_q[round_index] = q_path
        residual_energy_prefix[round_index] = collection_residual_energy
        residual_energy_envelope[round_index] = history * cell.residual_factor
        residual_envelope_pass[round_index] = (
            collection_residual_energy
            <= residual_energy_envelope[round_index] + 2e-10
        )
        exact_e_prefix[round_index] = e_exact
        predictable_e_prefix[round_index] = e_bar
        exact_f_prefix[round_index] = f_exact
        predictable_f_prefix[round_index] = f_bar
        old_chi_value = lipschitz * math.sqrt(q_path) / (sigma * math.sqrt(damping))
        old_chi[round_index] = old_chi_value

        mismatch_coefficients = (
            all_hprime * (counts * all_means - reward_sums)
            - sum_hprime_residual
            - (all_q * sum_hprime_squared - sum_hprime_squared_q)
        )
        mismatch_active = category_features.T @ mismatch_coefficients / variance
        mismatch_metric = math.sqrt(max(0.0, float(mismatch_active @ np.linalg.solve(frozen_active, mismatch_active))))
        exact_psi_value = residual / math.sqrt(damping) + mismatch_metric
        relative_psi_value = residual / math.sqrt(damping) + (
            rho_w * (math.sqrt(collection_residual_energy) + math.sqrt(q_path))
            + (1.0 + rho_w) * lipschitz * radius * math.sqrt(q_path)
        ) / sigma
        old_m = (
            lipschitz * math.sqrt(collection_residual_energy * q_path)
            + 1.5 * lipschitz * q_path
            + lipschitz * lipschitz * radius * q_path
        ) / variance
        old_psi_value = (residual + old_m) / math.sqrt(damping)
        exact_psi[round_index] = exact_psi_value
        relative_psi[round_index] = relative_psi_value
        old_psi[round_index] = old_psi_value

        sign, logdet = np.linalg.slogdet(frozen_active)
        if sign <= 0.0:
            raise FloatingPointError("frozen curvature lost positive definiteness")
        gamma_value = float(logdet - rank * math.log(damping))
        rank_bound = _rank_information_bound(history, rank, damping, variance)
        trace = float(np.trace(frozen_active) - rank * damping)
        effective = min(history, rank)
        split_bound = 0.0 if effective == 0 else effective * math.log1p(trace / (effective * damping))
        gamma[round_index] = gamma_value
        gamma_tail[round_index] = rank_bound
        gamma_split[round_index] = split_bound
        beta = math.sqrt(rank_bound + 2.0 * math.log(1.0 / delta)) + math.sqrt(damping) * teacher_norm + math.sqrt(f_bar) / sigma

        context = int(stream.contexts[round_index])
        active_candidates = environment.active_features[context]
        q_candidates = active_candidates @ theta
        means = _scaled_tanh(q_candidates, cell.width)
        hprime_candidates = _scaled_tanh_prime(q_candidates, cell.width)
        active_queries = hprime_candidates[:, None] * active_candidates
        queries = np.zeros((actions, dimension), dtype=np.float64)
        queries[:, :rank] = active_queries
        current_matrix = damping * np.eye(dimension, dtype=np.float64)
        current_matrix[:rank, :rank] = current_active
        frozen_matrix = damping * np.eye(dimension, dtype=np.float64)
        frozen_matrix[:rank, :rank] = frozen_active
        dense_solutions = np.linalg.solve(current_matrix, queries.T).T
        dense_values = np.maximum(0.0, np.einsum("ij,ij->i", queries, dense_solutions))
        dense_width_squared[round_index] = dense_values

        cg_values = dense_values.copy()
        alpha = 1.0
        if method == "full_cg_relative":
            cg_values, its, residuals, errors, converged = _cg_widths(
                current_matrix,
                queries,
                history=history,
                variance=variance,
                damping=damping,
                energy_target=cg_target,
            )
            cg_iterations[round_index] = its
            cg_residual[round_index] = residuals
            cg_energy_error[round_index] = errors
            cg_converged[round_index] = converged
            # The extra application recomputes r=g-Cu in the original system.
            work_total += int(np.sum(its + 1)) * history
            alpha = math.sqrt((1.0 + cg_target) / (1.0 - cg_target))
        computed_width_squared[round_index] = cg_values if method == "full_cg_relative" else dense_values

        theta_hat_linearized = np.linalg.solve(frozen_active, frozen_response)
        corrected_center = means + active_queries @ (theta_hat_linearized - theta)
        frozen_solved = np.linalg.solve(frozen_active, active_queries.T).T
        frozen_widths = np.sqrt(np.maximum(0.0, np.einsum("ij,ij->i", active_queries, frozen_solved)))
        diagonal = np.diag(current_active)
        diagonal_widths = np.sqrt(np.sum(active_queries * active_queries / diagonal[None, :], axis=1))
        linear_theta = np.linalg.solve(linear_active, linear_response)
        linear_center = active_candidates @ linear_theta
        linear_solved = np.linalg.solve(linear_active, active_candidates.T).T
        linear_widths = np.sqrt(np.maximum(0.0, np.einsum("ij,ij->i", active_candidates, linear_solved)))
        linear_beta = math.sqrt(rank_bound + 2.0 * math.log(1.0 / delta)) + math.sqrt(damping) * teacher_norm
        omega_relative = beta + relative_psi_value
        omega_old = beta + old_psi_value
        if method == "exact_current_relative":
            scores = means + omega_relative * (1.0 + rho_w) * np.sqrt(dense_values)
            omega_for_bound = omega_relative
        elif method == "full_cg_relative":
            scores = means + omega_relative * (1.0 + rho_w) * np.sqrt(cg_values / (1.0 - cg_target))
            omega_for_bound = omega_relative
        elif method == "current_welford":
            scores = means + omega_old * (1.0 + old_chi_value) * np.sqrt(dense_values)
            omega_for_bound = omega_old
        elif method == "corrected_current":
            scores = corrected_center + beta * (1.0 + rho_w) * np.sqrt(dense_values)
            omega_for_bound = beta
        elif method == "frozen_neuralucb":
            scale = float(config["baseline_bonus_scales"][method])
            scores = means + scale * beta * frozen_widths
            omega_for_bound = beta
        elif method == "diagonal_current":
            scale = float(config["baseline_bonus_scales"][method])
            scores = means + scale * beta * diagonal_widths
            omega_for_bound = beta
        elif method == "frozen_linear_ucb":
            scale = float(config["baseline_bonus_scales"][method])
            scores = linear_center + scale * linear_beta * linear_widths
            omega_for_bound = linear_beta
        else:
            scores = means
            omega_for_bound = 0.0

        selected = _stable_argmax(
            scores, tolerance=float(config["score_tie_tolerance"])
        )
        # Teacher quantities are evaluated only after the policy has committed.
        flat_teacher_q_audit = category_features @ environment.teacher
        flat_teacher_means_audit = _scaled_tanh(flat_teacher_q_audit, cell.width)
        cell_means_audit = flat_teacher_means_audit.reshape(
            int(config["context_count"]), actions
        )
        true_means = cell_means_audit[context]
        optimal = int(environment.optimal_actions[context])
        regret_total += float(true_means[optimal] - true_means[selected])
        cumulative_regret[round_index] = regret_total
        selected_actions[round_index] = selected
        cumulative_cvps[round_index] = work_total

        teacher_difference = environment.teacher - theta
        exact_remainders = (
            flat_teacher_means_audit
            - all_means
            - all_hprime * (category_features @ teacher_difference)
        )
        exact_linearization_value = float(np.max(np.abs(exact_remainders)))
        exact_linearization[round_index] = exact_linearization_value
        transfer_pass[round_index] = chi <= rho + 2e-11 and rho <= rho_w + 2e-11 and rho_w < 1.0
        centering_pass[round_index] = exact_psi_value <= relative_psi_value + 2e-10
        old_transfer_pass[round_index] = chi <= old_chi_value + 2e-10
        old_centering_pass[round_index] = exact_psi_value <= old_psi_value + 2e-10
        linearization_pass[round_index] = exact_linearization_value <= epsilon_bound + 2e-11
        information_pass[round_index] = gamma_value <= split_bound + 2e-10 and split_bound <= rank_bound + 2e-10
        if method == "corrected_current":
            prediction_errors = np.abs(true_means - corrected_center)
            confidence_radius = beta * frozen_widths + epsilon_bound
        elif method == "current_welford":
            prediction_errors = np.abs(true_means - means)
            confidence_radius = omega_old * frozen_widths + epsilon_bound
        else:
            prediction_errors = np.abs(true_means - means)
            confidence_radius = omega_relative * frozen_widths + epsilon_bound
        confidence_event[round_index] = bool(
            np.all(prediction_errors <= confidence_radius + 2e-10)
        )
        optimism_event[round_index] = bool(np.all(scores + epsilon_bound + 2e-10 >= true_means)) if method in THEOREM_METHODS else True
        cg_pass = method != "full_cg_relative" or (
            bool(np.all(cg_converged[round_index]))
            and float(np.max(cg_energy_error[round_index])) <= cg_target + 2e-10
        )
        selected_dense_width = float(dense_values[selected])
        dynamic_sum += math.log1p(selected_dense_width / variance)
        if method in {"exact_current_relative", "full_cg_relative", "corrected_current"}:
            factor_sum += alpha * alpha * omega_for_bound * omega_for_bound * ((1.0 + rho_w) / (1.0 - rho_w)) ** 2
        elif method == "current_welford":
            factor_sum += omega_old * omega_old * (1.0 + old_chi_value) ** 2

        category = context * actions + selected
        reward = float(true_means[selected] + stream.noises[round_index, selected])
        q_selected = float(q_candidates[selected])
        mean_selected = float(means[selected])
        hp_selected = float(hprime_candidates[selected])
        feature_selected = active_candidates[selected]
        gradient_selected = hp_selected * feature_selected
        collection_residual = mean_selected - reward
        pseudo_response = reward - mean_selected + hp_selected * q_selected
        counts[category] += 1.0
        reward_sums[category] += reward
        reward_square_sums[category] += reward * reward
        sum_hprime[category] += hp_selected
        sum_hprime_squared[category] += hp_selected * hp_selected
        sum_hprime_residual[category] += hp_selected * collection_residual
        sum_hprime_squared_q[category] += hp_selected * hp_selected * q_selected
        minimum_hprime[category] = min(minimum_hprime[category], hp_selected)
        maximum_hprime[category] = max(maximum_hprime[category], hp_selected)
        frozen_active += np.outer(gradient_selected, gradient_selected) / variance
        frozen_response += gradient_selected * pseudo_response / variance
        linear_active += np.outer(feature_selected, feature_selected) / variance
        linear_response += feature_selected * reward / variance
        collection_residual_energy += collection_residual * collection_residual
        residual_energy_through_round[round_index] = collection_residual_energy
        residual_envelope_through_round[round_index] = (
            (round_index + 1) * cell.residual_factor
        )
        residual_endpoint_pass[round_index] = (
            collection_residual_energy
            <= residual_envelope_through_round[round_index] + 2e-10
        )
        f_bar += epsilon_bound * epsilon_bound
        e_bar += epsilon_bound
        f_exact += exact_linearization_value * exact_linearization_value
        e_exact += exact_linearization_value
        exact_e_through_round[round_index] = e_exact
        predictable_e_through_round[round_index] = e_bar
        exact_f_next[round_index] = f_exact
        predictable_f_next[round_index] = f_bar
        path_count += 1
        displacement = theta - path_mean
        path_mean = path_mean + displacement / path_count
        path_scatter += float(displacement @ (theta - path_mean))

        sign_next, logdet_next = np.linalg.slogdet(frozen_active)
        if sign_next <= 0.0:
            raise FloatingPointError("updated frozen curvature lost positive definiteness")
        gamma_next = float(logdet_next - rank * math.log(damping))
        endpoint_rank_bound = _rank_information_bound(
            round_index + 1, rank, damping, variance
        )
        endpoint_trace = float(np.trace(frozen_active) - rank * damping)
        endpoint_effective = min(round_index + 1, rank)
        endpoint_split = endpoint_effective * math.log1p(
            endpoint_trace / (endpoint_effective * damping)
        )
        gamma_endpoint[round_index] = gamma_next
        gamma_tail_endpoint[round_index] = endpoint_rank_bound
        gamma_split_endpoint[round_index] = endpoint_split
        endpoint_information_pass[round_index] = (
            gamma_next <= endpoint_split + 2e-10
            and endpoint_split <= endpoint_rank_bound + 2e-10
        )

        if method in {"exact_current_relative", "full_cg_relative", "corrected_current"}:
            width_potential = endpoint_rank_bound
        elif method == "current_welford":
            width_potential = dynamic_sum
        else:
            width_potential = math.nan
        rhs_information_term[round_index] = endpoint_rank_bound
        rhs_factor_sum[round_index] = factor_sum if method in THEOREM_METHODS else math.nan
        rhs_width_potential[round_index] = width_potential
        if np.isfinite(width_potential):
            statistical_component = 2.0 * math.sqrt(
                (variance + 1.0 / damping) * width_potential * factor_sum
            )
            linearization_component = 2.0 * e_bar
            rhs_value = statistical_component + linearization_component
            rhs_statistical_component[round_index] = statistical_component
            rhs_linearization_component[round_index] = linearization_component
            theorem_rhs[round_index] = rhs_value
            rhs_per_round[round_index] = rhs_value / (round_index + 1)
            if regret_total > 0.0:
                rhs_regret_ratio[round_index] = rhs_value / regret_total
            regret_bound_pass[round_index] = regret_total <= rhs_value + 2e-10
        else:
            regret_bound_pass[round_index] = True

        common_premises = bool(
            np.linalg.norm(theta) <= radius + 1e-12
            and linearization_pass[round_index]
            and information_pass[round_index]
            and endpoint_information_pass[round_index]
            and confidence_event[round_index]
            and optimism_event[round_index]
            and cg_pass
            and regret_bound_pass[round_index]
        )
        if method in {"exact_current_relative", "full_cg_relative"}:
            premise_pass[round_index] = bool(
                common_premises
                and optimizer_pass[round_index]
                and transfer_pass[round_index]
                and centering_pass[round_index]
                and residual_envelope_pass[round_index]
            )
        elif method == "current_welford":
            premise_pass[round_index] = bool(
                common_premises
                and optimizer_pass[round_index]
                and old_transfer_pass[round_index]
                and old_centering_pass[round_index]
                and residual_envelope_pass[round_index]
            )
        elif method == "corrected_current":
            premise_pass[round_index] = bool(
                common_premises and transfer_pass[round_index]
            )
        else:
            premise_pass[round_index] = True

    sorted_cell_means = np.sort(cell_means_audit, axis=1)
    cell_minimum_gap = float(
        np.min(sorted_cell_means[:, -1] - sorted_cell_means[:, -2])
    )
    finite_rhs = np.isfinite(theorem_rhs[-1])
    summary: dict[str, Any] = {
        "schema_version": 1,
        "experiment": "scaled_tanh_instantiation",
        "method": method,
        "cell": {
            "horizon": cell.horizon,
            "width_ratio": cell.width_ratio,
            "width": cell.width,
            "residual_factor": cell.residual_factor,
        },
        "dimension": dimension,
        "effective_rank": rank,
        "action_count": actions,
        "terminal_pseudo_regret": float(cumulative_regret[-1]),
        "terminal_theorem_rhs": float(theorem_rhs[-1]) if finite_rhs else None,
        "terminal_rhs_per_round": float(rhs_per_round[-1]) if finite_rhs else None,
        "terminal_rhs_regret_ratio": float(rhs_regret_ratio[-1]) if np.isfinite(rhs_regret_ratio[-1]) else None,
        "terminal_rhs_statistical_component": float(rhs_statistical_component[-1]) if finite_rhs else None,
        "terminal_rhs_linearization_component": float(rhs_linearization_component[-1]) if finite_rhs else None,
        "terminal_rhs_information_term": float(rhs_information_term[-1]) if finite_rhs else None,
        "terminal_rhs_factor_sum": float(rhs_factor_sum[-1]) if finite_rhs else None,
        "terminal_gamma_prefix": float(gamma[-1]),
        "terminal_gamma_endpoint": float(gamma_endpoint[-1]),
        "terminal_Gamma_tail_endpoint": float(gamma_tail_endpoint[-1]),
        "terminal_Gamma_split_endpoint": float(gamma_split_endpoint[-1]),
        "terminal_exact_E": float(exact_e_through_round[-1]),
        "terminal_predictable_E": float(predictable_e_through_round[-1]),
        "terminal_exact_F": float(exact_f_next[-1]),
        "terminal_predictable_F": float(predictable_f_next[-1]),
        "terminal_residual_energy": float(residual_energy_through_round[-1]),
        "terminal_residual_envelope": float(residual_envelope_through_round[-1]),
        "maximum_exact_chi": float(np.max(exact_chi)),
        "maximum_old_chi": float(np.max(old_chi)),
        "maximum_exact_rho": float(np.max(exact_rho)),
        "analytic_rho_W": rho_w,
        "maximum_exact_psi": float(np.max(exact_psi)),
        "maximum_relative_psi_certificate": float(np.max(relative_psi)),
        "maximum_old_psi_certificate": float(np.max(old_psi)),
        "maximum_optimizer_residual": float(np.max(optimizer_residual)),
        "optimizer_failure_count": int(np.sum(~optimizer_pass)),
        "premise_failure_count": int(np.sum(~premise_pass)) if method in THEOREM_METHODS else 0,
        "all_required_premises_pass": bool(np.all(premise_pass)) if method in THEOREM_METHODS else None,
        "confidence_failure_count": int(np.sum(~confidence_event)) if method in THEOREM_METHODS else 0,
        "optimism_failure_count": int(np.sum(~optimism_event)) if method in THEOREM_METHODS else 0,
        "residual_envelope_failure_count": int(np.sum(~residual_endpoint_pass)),
        "endpoint_information_failure_count": int(np.sum(~endpoint_information_pass)),
        "regret_bound_failure_count": int(np.sum(~regret_bound_pass)) if method in THEOREM_METHODS else 0,
        "old_transfer_failure_count": int(np.sum(~old_transfer_pass)),
        "old_centering_failure_count": int(np.sum(~old_centering_pass)),
        "maximum_cg_energy_error": float(np.max(cg_energy_error)) if method == "full_cg_relative" else None,
        "maximum_cg_relative_residual": float(np.max(cg_residual)) if method == "full_cg_relative" else None,
        "all_cg_solves_converged": bool(np.all(cg_converged)) if method == "full_cg_relative" else None,
        "mean_cg_iterations": float(np.mean(cg_iterations)) if method == "full_cg_relative" else None,
        "sample_cvps": int(cumulative_cvps[-1]) if method == "full_cg_relative" else None,
        "environment_reference_minimum_gap": environment.minimum_gap,
        "cell_minimum_gap": cell_minimum_gap,
        "optimizer": "deterministic projected damped Newton with exact finite-support full-history sufficient statistics",
        "policy_uses_teacher": False,
        "evaluation_data_used_for_selection": False,
        "stream_pairing": "same PCG64 context/noise prefixes across width ratios and horizons for a fixed seed",
        "numerical_semantics": "post-hoc float64 audits; analytic action-time relative and residual envelopes",
    }
    arrays: dict[str, NDArray[np.generic]] = {
        "cumulative_pseudo_regret": cumulative_regret,
        "theorem_rhs": theorem_rhs,
        "rhs_per_round": rhs_per_round,
        "rhs_regret_ratio": rhs_regret_ratio,
        "exact_chi_t": exact_chi,
        "old_chi_bar_t": old_chi,
        "exact_rho_t": exact_rho,
        "analytic_rho_W": analytic_rho,
        "exact_psi_t": exact_psi,
        "relative_psi_bar_t": relative_psi,
        "old_psi_bar_t": old_psi,
        "exact_linearization_error": exact_linearization,
        "linearization_bound": linearization_bound,
        "gamma": gamma,
        "Gamma_tail": gamma_tail,
        "Gamma_split": gamma_split,
        "optimizer_residual": optimizer_residual,
        "optimizer_iterations": optimizer_iterations,
        "optimizer_pass": optimizer_pass,
        "confidence_event": confidence_event,
        "optimism_event": optimism_event,
        "transfer_pass": transfer_pass,
        "centering_pass": centering_pass,
        "linearization_pass": linearization_pass,
        "information_pass": information_pass,
        "endpoint_information_pass": endpoint_information_pass,
        "old_transfer_pass": old_transfer_pass,
        "old_centering_pass": old_centering_pass,
        "regret_bound_pass": regret_bound_pass,
        "path_Q_t": path_q,
        "residual_energy_prefix": residual_energy_prefix,
        "residual_energy_envelope": residual_energy_envelope,
        "residual_envelope_pass": residual_envelope_pass,
        "residual_energy_through_round": residual_energy_through_round,
        "residual_envelope_through_round": residual_envelope_through_round,
        "residual_endpoint_pass": residual_endpoint_pass,
        "exact_E_prefix": exact_e_prefix,
        "predictable_E_prefix": predictable_e_prefix,
        "exact_E_through_round": exact_e_through_round,
        "predictable_E_through_round": predictable_e_through_round,
        "exact_F_prefix": exact_f_prefix,
        "predictable_F_prefix": predictable_f_prefix,
        "exact_F_next": exact_f_next,
        "predictable_F_next": predictable_f_next,
        "gamma_endpoint": gamma_endpoint,
        "Gamma_tail_endpoint": gamma_tail_endpoint,
        "Gamma_split_endpoint": gamma_split_endpoint,
        "rhs_information_term": rhs_information_term,
        "rhs_factor_sum": rhs_factor_sum,
        "rhs_width_potential": rhs_width_potential,
        "rhs_statistical_component": rhs_statistical_component,
        "rhs_linearization_component": rhs_linearization_component,
        "premise_pass": premise_pass,
        "selected_actions": selected_actions,
        "dense_width_squared": dense_width_squared,
        "computed_width_squared": computed_width_squared,
        "cg_iterations": cg_iterations,
        "cg_relative_residual": cg_residual,
        "cg_energy_error": cg_energy_error,
        "cg_converged": cg_converged,
        "cumulative_sample_cvps": cumulative_cvps,
    }
    return ScaledTanhTrajectory(arrays=arrays, summary=summary)


def _run_directory(root: Path, profile: str, cell: Cell, method: str, seed: int) -> Path:
    return root / profile / "evaluation" / cell.token / method / f"seed-{seed}"


def _selection_winner(candidate_records: list[dict[str, Any]]) -> dict[str, Any]:
    if not candidate_records:
        raise ValueError("optimizer selection has no candidate records")
    zero_failure = [
        record for record in candidate_records if record["optimizer_failure_count"] == 0
    ]
    pool = zero_failure if zero_failure else candidate_records
    return min(
        pool,
        key=lambda record: (
            int(record["optimizer_failure_count"]),
            float(record["damping"]),
        ),
    )


def build_optimizer_selection(
    config: dict[str, Any],
    *,
    profile: str,
    selection_path: Path,
    overwrite: bool,
) -> dict[str, Any]:
    validate_config(config)
    if selection_path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite {selection_path}")
    tuning_seeds = get_seed_set(config, "tuning")
    selection_cells = optimizer_selection_cells(config)
    records: list[dict[str, Any]] = []
    for damping_candidate in config["optimizer_selection"]["damping_candidates"]:
        candidate_config = copy.deepcopy(config)
        candidate_config["damping"] = float(damping_candidate)
        environment = make_environment(candidate_config)
        failures = 0
        maximum_residual = 0.0
        run_records = []
        for seed in tuning_seeds:
            for cell in selection_cells:
                trajectory = run_trajectory(
                    candidate_config,
                    cell,
                    environment,
                    make_stream(candidate_config, cell, seed),
                    method="exact_current_relative",
                )
                failure_count = int(trajectory.summary["optimizer_failure_count"])
                failures += failure_count
                maximum_residual = max(
                    maximum_residual,
                    float(trajectory.summary["maximum_optimizer_residual"]),
                )
                run_records.append(
                    {
                        "seed": seed,
                        "cell": trajectory.summary["cell"],
                        "optimizer_failure_count": failure_count,
                        "maximum_optimizer_residual": trajectory.summary[
                            "maximum_optimizer_residual"
                        ],
                    }
                )
        records.append(
            {
                "damping": float(damping_candidate),
                "optimizer_failure_count": failures,
                "maximum_optimizer_residual": maximum_residual,
                "run_count": len(run_records),
                "runs": run_records,
            }
        )
    winner = _selection_winner(records)
    metadata = collect_run_metadata(
        repository=Path(__file__).resolve().parents[1],
        packages=tuple(config.get("provenance", {}).get("packages", ())),
    )
    metadata["source_artifact_hashes"] = {
        "experiments/run_scaled_tanh_instantiation.py": sha256_file(__file__),
    }
    artifact = {
        "schema_version": 1,
        "event": "scaled_tanh_optimizer_selection",
        "profile": profile,
        "config_digest": config_digest(config),
        "tuning_seeds": list(tuning_seeds),
        "evaluation_seeds": list(get_seed_set(config, "evaluation")),
        "selection_cells": [cell.__dict__ for cell in selection_cells],
        "criterion": config["optimizer_selection"]["criterion"],
        "selected_damping": float(winner["damping"]),
        "selected_optimizer_zeta0": float(config["optimizer_zeta0"]),
        "candidate_results": records,
        "evaluation_metrics_read": False,
        "protocol_amendment": config["protocol_amendment"],
        "timestamp_utc": dt.datetime.now(dt.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "provenance": metadata,
    }
    write_json_artifact(selection_path, artifact)
    return artifact


def load_optimizer_selection(
    config: dict[str, Any], selection_path: Path, *, profile: str
) -> dict[str, Any]:
    validate_sha256_sidecar(selection_path)
    artifact = json.loads(selection_path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": 1,
        "event": "scaled_tanh_optimizer_selection",
        "profile": profile,
        "config_digest": config_digest(config),
        "tuning_seeds": list(get_seed_set(config, "tuning")),
        "evaluation_seeds": list(get_seed_set(config, "evaluation")),
        "evaluation_metrics_read": False,
        "selected_damping": float(config["damping"]),
        "selected_optimizer_zeta0": float(config["optimizer_zeta0"]),
    }
    for key, value in expected.items():
        if artifact.get(key) != value:
            raise ValueError(f"optimizer selection mismatch for {key}")
    records = artifact.get("candidate_results")
    if not isinstance(records, list) or not records:
        raise ValueError("optimizer selection lacks candidate results")
    winner = _selection_winner(records)
    if float(winner["damping"]) != float(config["damping"]):
        raise ValueError("optimizer selection winner does not match resolved config")
    return artifact


def _save_run(
    destination: Path,
    run: ScaledTanhTrajectory,
    *,
    config: dict[str, Any],
    profile: str,
    seed: int,
    environment: ScaledTanhEnvironment,
    stream: ScaledTanhStream,
    metadata: dict[str, Any],
    selection_sha256: str,
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
            "experiment": "scaled_tanh_instantiation",
            "profile": profile,
            "phase": "evaluation",
            "seed": seed,
            "method": run.summary["method"],
            "cell": run.summary["cell"],
            "config": config,
            "config_digest": config_digest(config),
            "environment_sha256": environment.digest,
            "stream_sha256": stream.digest,
            "rounds_sha256": sha256_file(rounds_path),
            "summary_sha256": sha256_file(summary_path),
            "rng": config["rng"],
            "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            "selection_protocol": config["selection_protocol"],
            "optimizer_selection_sha256": selection_sha256,
            "evaluation_data_used_for_selection": False,
            "provenance": metadata,
        },
    )


def _execute_task(
    task: tuple[
        dict[str, Any],
        str,
        str,
        int,
        Cell,
        tuple[str, ...],
        dict[str, Any],
        str,
        bool,
    ]
) -> tuple[int, int]:
    (
        config,
        profile,
        root_text,
        seed,
        cell,
        methods,
        metadata,
        selection_sha256,
        overwrite,
    ) = task
    seed_everything(seed)
    environment = make_environment(config)
    stream = make_stream(config, cell, seed)
    clean = 0
    for method in methods:
        run = run_trajectory(config, cell, environment, stream, method=method)
        _save_run(
            _run_directory(Path(root_text), profile, cell, method, seed),
            run,
            config=config,
            profile=profile,
            seed=seed,
            environment=environment,
            stream=stream,
            metadata=metadata,
            selection_sha256=selection_sha256,
            overwrite=overwrite,
        )
        clean += int(run.summary["all_required_premises_pass"] is True)
    return len(methods), clean


def run_evaluation(
    config: dict[str, Any],
    *,
    profile: str,
    output_root: Path,
    selection_path: Path,
    overwrite: bool,
    workers: int = 1,
) -> dict[str, Any]:
    validate_config(config)
    if workers <= 0:
        raise ValueError("workers must be positive")
    seeds = get_seed_set(config, "evaluation")
    load_optimizer_selection(config, selection_path, profile=profile)
    selection_sha256 = sha256_file(selection_path)
    methods = tuple(str(value) for value in config["methods"])
    metadata = collect_run_metadata(
        repository=Path(__file__).resolve().parents[1],
        packages=tuple(config.get("provenance", {}).get("packages", ())),
    )
    metadata["source_artifact_hashes"] = {
        "experiments/run_scaled_tanh_instantiation.py": sha256_file(__file__),
    }
    tasks = [
        (
            config,
            profile,
            output_root.as_posix(),
            seed,
            cell,
            methods,
            metadata,
            selection_sha256,
            overwrite,
        )
        for seed in seeds
        for cell in cells(config)
    ]
    executor: ProcessPoolExecutor | None = None
    task_results = map(_execute_task, tasks)
    if workers > 1:
        executor = ProcessPoolExecutor(max_workers=workers)
        task_results = executor.map(_execute_task, tasks, chunksize=1)
    run_count = 0
    clean_count = 0
    try:
        for count, clean in task_results:
            run_count += count
            clean_count += clean
    finally:
        if executor is not None:
            executor.shutdown()
    return {
        "profile": profile,
        "phase": "evaluation",
        "seeds": list(seeds),
        "cell_count": len(cells(config)),
        "run_count": run_count,
        "premise_clean_theorem_run_count": clean_count,
        "workers": workers,
        "optimizer_selection_sha256": selection_sha256,
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument("--phase", choices=("tuning", "evaluation"), required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config, profile=args.profile)
    if args.phase == "tuning":
        artifact = build_optimizer_selection(
            config,
            profile=args.profile,
            selection_path=args.selection,
            overwrite=args.overwrite,
        )
        result = {
            "profile": args.profile,
            "phase": "tuning",
            "selection": args.selection.as_posix(),
            "selection_sha256": sha256_file(args.selection),
            "selected_damping": artifact["selected_damping"],
        }
    else:
        result = run_evaluation(
            config,
            profile=args.profile,
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
    "Cell",
    "ScaledTanhEnvironment",
    "ScaledTanhStream",
    "ScaledTanhTrajectory",
    "cells",
    "build_optimizer_selection",
    "load_optimizer_selection",
    "make_environment",
    "make_stream",
    "optimize_full_history",
    "optimizer_selection_cells",
    "residual_factor",
    "run_evaluation",
    "run_trajectory",
    "validate_config",
]
