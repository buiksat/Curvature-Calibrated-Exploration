"""Run the canonical Wheel benchmark with leakage-free model selection."""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

import numpy as np
import psutil
from numpy.typing import ArrayLike, NDArray

from .config import config_digest, get_seed_set, load_config
from .curvature_operators import conjugate_gradient
from .logging_utils import ExperimentLogger, append_jsonl, canonical_json, derive_seed
from .nonlinear_environment import MLPLayout, SmallTanhMLP
from .wheel_environment import (
    ACTION_COUNT,
    PostActionWheelOracle,
    QUADRANT_TO_ACTION,
    SAFE_ACTION,
    WheelSpecification,
    generate_wheel_stream,
)


FloatArray = NDArray[np.float64]
DEFAULT_CONFIG = Path(__file__).with_name("configs") / "wheel_benchmark.yaml"
METHODS = (
    "cc_ucb_full_ggn_cg",
    "linucb",
    "linear_ts",
    "local_neural_ucb",
    "local_neural_ts",
    "random",
    "safe",
    "oracle",
)
CONTROL_METHODS = {"random", "safe", "oracle"}
NEURAL_METHODS = {
    "cc_ucb_full_ggn_cg",
    "local_neural_ucb",
    "local_neural_ts",
}
METHOD_IMPLEMENTATIONS = {
    "cc_ucb_full_ggn_cg": "local_current_parameter_full_ggn_residual_checked_cg_ucb",
    "linucb": "local_disjoint_affine_feature_linucb",
    "linear_ts": "local_disjoint_affine_feature_gaussian_linear_ts",
    "local_neural_ucb": "local_full_network_linearized_ucb_not_published_code",
    "local_neural_ts": "local_full_network_linearized_gaussian_ts_not_published_code",
    "random": "uniform_random_context_and_oracle_independent_control",
    "safe": "fixed_canonical_safe_action_control",
    "oracle": "privileged_true_mean_oracle_nonlearner_control",
}


@dataclass(frozen=True)
class Cell:
    delta: float

    @property
    def token(self) -> str:
        return f"delta-{format(self.delta, '.12g').replace('.', 'p')}"


def cells(config: Mapping[str, Any]) -> tuple[Cell, ...]:
    values = config.get("deltas")
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValueError("deltas must be a sequence")
    result = tuple(Cell(float(value)) for value in values)
    if tuple(cell.delta for cell in result) != (0.5, 0.7, 0.9, 0.95):
        raise ValueError("Wheel deltas must be exactly 0.5, 0.7, 0.9, and 0.95")
    return result


def _positive(value: Any, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _nonnegative(value: Any, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _section(config: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = config.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"config.{name} must be a mapping")
    return value


def configured_methods(config: Mapping[str, Any]) -> tuple[str, ...]:
    value = config.get("methods")
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("methods must be a sequence")
    methods = tuple(str(item) for item in value)
    if methods != METHODS:
        raise ValueError("methods must contain the preregistered Wheel inventory in order")
    return methods


def validate_wheel_config(config: Mapping[str, Any]) -> None:
    configured_methods(config)
    configured_cells = cells(config)
    environment = _section(config, "environment")
    if int(environment.get("context_dimension", -1)) != 2:
        raise ValueError("Wheel context_dimension must be two")
    if int(environment.get("action_count", -1)) != ACTION_COUNT:
        raise ValueError("Wheel action_count must be five")
    if environment.get("context_distribution") != "uniform_by_area_on_unit_disk":
        raise ValueError("Wheel contexts must be uniform by area on the unit disk")
    if environment.get("quadrant_actions") != QUADRANT_TO_ACTION:
        raise ValueError("Wheel quadrant map differs from the canonical protocol")
    for cell in configured_cells:
        WheelSpecification.from_mapping({**environment, "delta": cell.delta})
    rounds = _positive_int(config.get("rounds"), name="rounds")
    _positive_int(config.get("tuning_rounds"), name="tuning_rounds")
    horizons = tuple(int(value) for value in config.get("horizons", ()))
    if not horizons or tuple(sorted(set(horizons))) != horizons:
        raise ValueError("horizons must be a strictly increasing unique list")
    if horizons[-1] != rounds or horizons[0] <= 0:
        raise ValueError("horizons must be positive and end at rounds")
    controls = _section(config, "controls")
    if tuple(controls.get("required", ())) != ("random", "safe", "oracle"):
        raise ValueError("random, safe, and oracle controls are required")
    if controls.get("oracle_is_privileged_nonlearner") is not True:
        raise ValueError("the oracle must be labeled as a privileged non-learner")
    omissions = _section(config, "omitted_methods")
    if "lofi" not in omissions or "faithful pinned" not in str(omissions["lofi"]):
        raise ValueError("LO-FI must be explicitly excluded without a faithful pin")
    model = _section(config, "model")
    _positive_int(model.get("hidden_width"), name="model.hidden_width")
    _positive(model.get("learning_rate"), name="model.learning_rate")
    _nonnegative(model.get("model_ridge"), name="model.model_ridge")
    _positive(model.get("maximum_step_norm"), name="model.maximum_step_norm")
    _positive(model.get("posterior_noise_std"), name="model.posterior_noise_std")
    if _positive_int(model.get("updates_per_round"), name="model.updates_per_round") != 1:
        raise ValueError("the matched protocol requires one update per round")
    cg = _section(config, "cg")
    _positive(cg.get("relative_residual_tolerance"), name="cg tolerance")
    _positive_int(cg.get("max_iterations"), name="cg.max_iterations")


def linear_action_features(context: ArrayLike) -> FloatArray:
    x = np.asarray(context, dtype=np.float64)
    if x.shape != (2,) or not np.all(np.isfinite(x)):
        raise ValueError("context must be a finite two-vector")
    base = np.asarray([1.0, x[0], x[1]], dtype=np.float64)
    features = np.zeros((ACTION_COUNT, ACTION_COUNT * base.size), dtype=np.float64)
    for action in range(ACTION_COUNT):
        start = action * base.size
        features[action, start : start + base.size] = base
    return features


def hyperparameter_grid(
    config: Mapping[str, Any], method: str
) -> tuple[tuple[float, float], ...]:
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    if method in CONTROL_METHODS:
        return ((0.0, 0.0),)
    ridges = tuple(_positive(value, name="ridge") for value in config["ridge_grid"])
    bonuses = tuple(_positive(value, name="bonus") for value in config["bonus_grid"])
    if not ridges or not bonuses:
        raise ValueError("ridge_grid and bonus_grid must be nonempty")
    return tuple((ridge, bonus) for ridge in ridges for bonus in bonuses)


def _posterior_sample(
    rng: np.random.Generator, matrix: FloatArray, mean: FloatArray, scale: float
) -> FloatArray:
    factor = np.linalg.cholesky(matrix)
    perturbation = np.linalg.solve(factor.T, rng.normal(size=mean.size))
    return np.asarray(mean + scale * perturbation, dtype=np.float64)


def _model_update(
    model: SmallTanhMLP,
    theta: FloatArray,
    context: FloatArray,
    action: int,
    normalized_reward: float,
    *,
    learning_rate: float,
    model_ridge: float,
    maximum_step_norm: float,
) -> tuple[FloatArray, float]:
    prediction, jacobian = model.mean_and_jacobian(theta, context, action)
    gradient = (prediction - normalized_reward) * jacobian + model_ridge * theta
    step = learning_rate * gradient
    norm = float(np.linalg.norm(step))
    if norm > maximum_step_norm:
        step *= maximum_step_norm / norm
    updated = np.asarray(theta - step, dtype=np.float64)
    return updated, float(np.linalg.norm(step))


def _control_action(
    method: str,
    context: FloatArray,
    rng: np.random.Generator,
    specification: WheelSpecification,
) -> int:
    if method == "random":
        return int(rng.integers(0, ACTION_COUNT))
    if method == "safe":
        return SAFE_ACTION
    if method == "oracle":
        return specification.optimal_action(context)
    raise ValueError("control action requested for a learner")


@dataclass(frozen=True)
class WheelRun:
    method: str
    cell: Cell
    seed: int
    phase: str
    ridge: float
    bonus_scale: float
    records: tuple[dict[str, Any], ...]
    summary: dict[str, Any]

    def deterministic_signature(self) -> str:
        stripped = [
            {
                key: value
                for key, value in row.items()
                if not key.endswith(("_seconds", "_bytes"))
            }
            for row in self.records
        ]
        return hashlib.sha256(canonical_json(stripped).encode("ascii")).hexdigest()


def run_policy(
    config: Mapping[str, Any],
    method: str,
    seed: int,
    *,
    cell: Cell,
    phase: str,
    ridge: float,
    bonus_scale: float,
) -> WheelRun:
    validate_wheel_config(config)
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    if cell not in cells(config):
        raise ValueError("cell is not declared by the Wheel config")
    if phase not in {"tuning", "evaluation"}:
        raise ValueError("phase must be tuning or evaluation")
    ridge_value = _nonnegative(ridge, name="ridge")
    bonus = _nonnegative(bonus_scale, name="bonus_scale")
    if (ridge_value, bonus) not in hyperparameter_grid(config, method):
        raise ValueError("hyperparameters lie outside the configured grid")

    rounds = _positive_int(
        config["tuning_rounds"] if phase == "tuning" else config["rounds"],
        name="rounds",
    )
    specification = WheelSpecification.from_mapping(
        {**_section(config, "environment"), "delta": cell.delta}
    )
    stream = generate_wheel_stream(int(seed), rounds)
    outcome_oracle = PostActionWheelOracle(specification)
    model_config = _section(config, "model")
    posterior_std = _positive(
        model_config["posterior_noise_std"], name="model.posterior_noise_std"
    )
    posterior_variance = posterior_std * posterior_std
    reward_scale = specification.high_mean
    layout = MLPLayout(
        context_dimension=2,
        hidden_width=_positive_int(model_config["hidden_width"], name="hidden_width"),
        action_count=ACTION_COUNT,
    )
    model = SmallTanhMLP(layout)
    theta = np.zeros(layout.parameter_dimension, dtype=np.float64)
    learning_rate = _positive(model_config["learning_rate"], name="learning_rate")
    model_ridge = _nonnegative(model_config["model_ridge"], name="model_ridge")
    maximum_step = _positive(
        model_config["maximum_step_norm"], name="maximum_step_norm"
    )
    cg_config = _section(config, "cg")
    cg_tolerance = _positive(
        cg_config["relative_residual_tolerance"], name="cg tolerance"
    )
    cg_limit = _positive_int(cg_config["max_iterations"], name="cg.max_iterations")

    linear_dimension = ACTION_COUNT * 3
    linear_matrix = max(ridge_value, 1.0e-12) * np.eye(linear_dimension)
    linear_rhs = np.zeros(linear_dimension, dtype=np.float64)
    frozen_gradients: list[FloatArray] = []
    history_contexts: list[FloatArray] = []
    history_actions: list[int] = []
    rng = np.random.Generator(
        np.random.PCG64(derive_seed(int(seed), "wheel_benchmark", method, "policy"))
    )
    records: list[dict[str, Any]] = []
    cumulative_regret = 0.0
    cumulative_reward = 0.0
    cumulative_runtime = 0.0
    cumulative_update = 0.0
    cumulative_uncertainty = 0.0
    outer_rounds = 0
    optimal_action_count = 0
    total_cg_iterations = 0
    total_cg_operator_calls = 0
    maximum_cg_residual = 0.0
    process = psutil.Process()
    start_rss = process.memory_info().rss
    peak_rss = start_rss
    maximum_state_bytes = 0

    for round_index in range(rounds):
        started = time.perf_counter()
        context = np.asarray(stream.contexts[round_index], dtype=np.float64)
        outer = specification.is_outer(context)
        outer_rounds += int(outer)
        uncertainty_started = time.perf_counter()
        predicted = np.zeros(ACTION_COUNT, dtype=np.float64)
        widths = np.zeros(ACTION_COUNT, dtype=np.float64)
        scores = np.zeros(ACTION_COUNT, dtype=np.float64)
        queries: FloatArray | None = None
        candidates: FloatArray | None = None
        cg_iterations: list[int] = []
        cg_residuals: list[float] = []
        cg_calls: list[int] = []

        if method in CONTROL_METHODS:
            action = _control_action(method, context, rng, specification)
            scores[action] = 1.0
        elif method in {"linucb", "linear_ts"}:
            candidates = linear_action_features(context)
            estimate = np.linalg.solve(linear_matrix, linear_rhs)
            predicted_normalized = candidates @ estimate
            solved = np.linalg.solve(linear_matrix, candidates.T).T
            widths = np.sqrt(
                np.maximum(np.einsum("ij,ij->i", candidates, solved), 0.0)
            )
            if method == "linucb":
                scores = predicted_normalized + bonus * widths
            else:
                sampled = _posterior_sample(rng, linear_matrix, estimate, bonus)
                scores = candidates @ sampled
            predicted = reward_scale * predicted_normalized
            action = int(np.argmax(scores))
        else:
            predicted_normalized = model.means(theta, context)
            predicted = reward_scale * predicted_normalized
            queries = model.jacobians(theta, context)
            if method == "cc_ucb_full_ggn_cg":
                historical = (
                    np.stack(
                        [
                            model.jacobian(theta, old_context, old_action)
                            for old_context, old_action in zip(
                                history_contexts, history_actions, strict=True
                            )
                        ]
                    )
                    if history_contexts
                    else np.empty((0, layout.parameter_dimension), dtype=np.float64)
                )
                fixed_history = historical.copy()
                operator_calls = 0

                def matvec(vector: FloatArray) -> FloatArray:
                    nonlocal operator_calls
                    operator_calls += 1
                    return (
                        ridge_value * vector
                        + fixed_history.T @ (fixed_history @ vector)
                        / posterior_variance
                    )

                width_squared = np.empty(ACTION_COUNT, dtype=np.float64)
                for action_index, query in enumerate(queries):
                    calls_before = operator_calls
                    solution = conjugate_gradient(
                        matvec,
                        query,
                        tolerance=cg_tolerance,
                        max_iterations=cg_limit,
                        raise_on_nonconvergence=False,
                    )
                    residual = query - matvec(solution.solution)
                    denominator = float(np.linalg.norm(query))
                    relative = (
                        float(np.linalg.norm(residual) / denominator)
                        if denominator > 0.0
                        else 0.0
                    )
                    if not solution.converged or relative > cg_tolerance + 1.0e-12:
                        raise RuntimeError("Wheel current-GGN solve failed residual check")
                    width_squared[action_index] = max(
                        float(query @ solution.solution), 0.0
                    )
                    cg_iterations.append(int(solution.iterations))
                    cg_residuals.append(relative)
                    cg_calls.append(operator_calls - calls_before)
                widths = np.sqrt(width_squared)
                scores = predicted_normalized + bonus * widths
            else:
                historical = (
                    np.stack(frozen_gradients)
                    if frozen_gradients
                    else np.empty((0, layout.parameter_dimension), dtype=np.float64)
                )
                matrix = ridge_value * np.eye(layout.parameter_dimension)
                if historical.size:
                    matrix += historical.T @ historical / posterior_variance
                solved = np.linalg.solve(matrix, queries.T).T
                widths = np.sqrt(
                    np.maximum(np.einsum("ij,ij->i", queries, solved), 0.0)
                )
                if method == "local_neural_ucb":
                    scores = predicted_normalized + bonus * widths
                else:
                    perturbation = _posterior_sample(
                        rng, matrix, np.zeros(layout.parameter_dimension), bonus
                    )
                    scores = predicted_normalized + queries @ perturbation
            action = int(np.argmax(scores))

        uncertainty_seconds = time.perf_counter() - uncertainty_started
        outcome = outcome_oracle.observe_after_action(
            context,
            action,
            float(stream.standard_normals[round_index, action]),
        )
        cumulative_regret += outcome.pseudo_regret
        cumulative_reward += outcome.reward
        optimal_action_count += int(action == outcome.optimal_action)

        update_started = time.perf_counter()
        update_norm = 0.0
        normalized_reward = outcome.reward / reward_scale
        if method in {"linucb", "linear_ts"}:
            assert candidates is not None
            selected = candidates[action]
            linear_matrix += np.outer(selected, selected) / posterior_variance
            linear_rhs += selected * normalized_reward / posterior_variance
        elif method in NEURAL_METHODS:
            assert queries is not None
            selected_query = queries[action].copy()
            if method == "cc_ucb_full_ggn_cg":
                history_contexts.append(context.copy())
                history_actions.append(action)
            else:
                frozen_gradients.append(selected_query)
            theta, update_norm = _model_update(
                model,
                theta,
                context,
                action,
                normalized_reward,
                learning_rate=learning_rate,
                model_ridge=model_ridge,
                maximum_step_norm=maximum_step,
            )
        update_seconds = time.perf_counter() - update_started

        if method == "cc_ucb_full_ggn_cg":
            total_cg_iterations += sum(cg_iterations)
            total_cg_operator_calls += sum(cg_calls)
            maximum_cg_residual = max(
                maximum_cg_residual, max(cg_residuals, default=0.0)
            )
        if method in {"linucb", "linear_ts"}:
            state_bytes = linear_matrix.nbytes + linear_rhs.nbytes
        elif method == "cc_ucb_full_ggn_cg":
            state_bytes = theta.nbytes + sum(item.nbytes for item in history_contexts)
            state_bytes += 8 * len(history_actions)
        elif method in {"local_neural_ucb", "local_neural_ts"}:
            state_bytes = theta.nbytes + sum(item.nbytes for item in frozen_gradients)
        else:
            state_bytes = 0
        maximum_state_bytes = max(maximum_state_bytes, state_bytes)
        elapsed = time.perf_counter() - started
        cumulative_runtime += elapsed
        cumulative_update += update_seconds
        cumulative_uncertainty += uncertainty_seconds
        peak_rss = max(peak_rss, process.memory_info().rss)

        record: dict[str, Any] = {
            "round_number": round_index + 1,
            "method": method,
            "method_implementation": METHOD_IMPLEMENTATIONS[method],
            "published_implementation_claim": False,
            "phase": phase,
            "delta": cell.delta,
            "cell": {"delta": cell.delta, "token": cell.token},
            "executed_policy": True,
            "execution_mode": "online_adaptive" if method not in CONTROL_METHODS else "online_control",
            "context": context.tolist(),
            "context_radius": float(np.linalg.norm(context)),
            "outer_region": outer,
            "environment_stream_sha256": stream.stream_sha256,
            "selected_action": action,
            "optimal_action_posthoc": outcome.optimal_action,
            "selected_optimal_action": bool(action == outcome.optimal_action),
            "oracle_information_used_for_selection": method == "oracle",
            "uses_privileged_pre_action_oracle": method == "oracle",
            "observed_reward": outcome.reward,
            "chosen_mean_posthoc": outcome.chosen_mean,
            "chosen_std_posthoc": outcome.chosen_std,
            "standard_normal_for_selected_action": float(
                stream.standard_normals[round_index, action]
            ),
            "instantaneous_pseudo_regret": outcome.pseudo_regret,
            "cumulative_pseudo_regret": cumulative_regret,
            "cumulative_reward": cumulative_reward,
            "mean_reward": cumulative_reward / float(round_index + 1),
            "cumulative_optimal_action_rate": optimal_action_count
            / float(round_index + 1),
            "cumulative_outer_rounds": outer_rounds,
            "predicted_means_all_actions": predicted.tolist(),
            "predictive_widths_all_actions": widths.tolist(),
            "policy_scores_all_actions": scores.tolist(),
            "ridge": ridge_value,
            "bonus_scale": bonus,
            "model_update_norm": update_norm,
            "round_runtime_seconds": elapsed,
            "cumulative_runtime_seconds": cumulative_runtime,
            "state_update_seconds": update_seconds,
            "cumulative_state_update_seconds": cumulative_update,
            "uncertainty_seconds": uncertainty_seconds,
            "cumulative_uncertainty_seconds": cumulative_uncertainty,
            "persistent_numeric_policy_state_bytes": state_bytes,
            "peak_host_memory_bytes": peak_rss,
            "host_rss_at_start_bytes": start_rss,
            "peak_host_rss_delta_bytes": max(0, peak_rss - start_rss),
        }
        if method == "cc_ucb_full_ggn_cg":
            record.update(
                {
                    "cg_iterations_all_actions": cg_iterations,
                    "cg_iterations": cg_iterations,
                    "cg_relative_residuals_all_actions": cg_residuals,
                    "cg_operator_calls_all_actions": cg_calls,
                    "operator_matvecs": sum(cg_calls),
                    "cumulative_operator_matvecs": total_cg_operator_calls,
                    "cg_all_actions_converged": True,
                    "current_parameter_history_relinearized": True,
                    "matrix_free_dense_gram_materialized": False,
                }
            )
        records.append(record)

    summary: dict[str, Any] = {
        "schema_version": 1,
        "event": "wheel_benchmark_run_summary",
        "experiment": str(config.get("name")),
        "profile": str(config.get("profile")),
        "method": method,
        "method_implementation": METHOD_IMPLEMENTATIONS[method],
        "published_implementation_claim": False,
        "seed": int(seed),
        "phase": phase,
        "delta": cell.delta,
        "cell": {"delta": cell.delta, "token": cell.token},
        "comparison": "pooled_validation_tuned",
        "executed_policy": True,
        "execution_mode": "online_adaptive" if method not in CONTROL_METHODS else "online_control",
        "rounds": rounds,
        "cumulative_pseudo_regret": cumulative_regret,
        "cumulative_reward": cumulative_reward,
        "mean_reward": cumulative_reward / float(rounds),
        "optimal_action_rate": optimal_action_count / float(rounds),
        "outer_round_count": outer_rounds,
        "runtime_seconds": cumulative_runtime,
        "state_update_seconds": cumulative_update,
        "uncertainty_seconds": cumulative_uncertainty,
        "peak_host_memory_bytes": peak_rss,
        "host_rss_at_start_bytes": start_rss,
        "peak_host_rss_delta_bytes": max(0, peak_rss - start_rss),
        "maximum_persistent_numeric_policy_state_bytes": maximum_state_bytes,
        "ridge": ridge_value,
        "bonus_scale": bonus,
        "hyperparameters": {"ridge": ridge_value, "bonus_scale": bonus},
        "environment_stream_sha256": stream.stream_sha256,
        "common_random_numbers": True,
        "common_stream_within_seed_across_deltas": True,
        "eligible_for_pooled_tuning": phase == "tuning",
        "pooled_tuning_setting": phase == "evaluation",
        "uses_privileged_pre_action_oracle": method == "oracle",
        "oracle_information_used_for_selection": method == "oracle",
        "control_expected_one_round_pseudo_regret": (
            specification.expected_control_regret(method)
            if method in CONTROL_METHODS
            else None
        ),
        "lofi_included": False,
        "kfac_included": False,
        "local_neural_method": method in {"local_neural_ucb", "local_neural_ts"},
        "evaluation_outcomes_used_for_tuning": False,
    }
    if method == "cc_ucb_full_ggn_cg":
        summary.update(
            {
                "cg_total_iterations": total_cg_iterations,
                "cg_iterations_per_action": total_cg_iterations
                / float(rounds * ACTION_COUNT),
                "cg_total_operator_calls": total_cg_operator_calls,
                "cg_maximum_relative_residual": maximum_cg_residual,
                "cg_relative_residual_tolerance": cg_tolerance,
                "all_cg_solves_converged": True,
                "current_parameter_history_relinearized": True,
                "matrix_free_dense_gram_materialized": False,
            }
        )
    return WheelRun(
        method=method,
        cell=cell,
        seed=int(seed),
        phase=phase,
        ridge=ridge_value,
        bonus_scale=bonus,
        records=tuple(records),
        summary=summary,
    )


def build_tuning_selection(
    config: Mapping[str, Any], runs: Sequence[WheelRun]
) -> dict[str, Any]:
    if not runs or any(run.phase != "tuning" for run in runs):
        raise ValueError("selection requires tuning runs only")
    tuning_seeds = tuple(sorted(get_seed_set(config, "tuning")))
    configured_cells = cells(config)
    expected_coverage = {
        (cell.delta, seed) for cell in configured_cells for seed in tuning_seeds
    }
    grouped: dict[tuple[str, float, float], list[WheelRun]] = {}
    for run in runs:
        grouped.setdefault((run.method, run.ridge, run.bonus_scale), []).append(run)
    candidates: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    for method in configured_methods(config):
        choices: list[tuple[float, int, float, float]] = []
        for order, (ridge, bonus) in enumerate(hyperparameter_grid(config, method)):
            matching = sorted(
                grouped.get((method, ridge, bonus), []),
                key=lambda run: (run.cell.delta, run.seed),
            )
            coverage = {(run.cell.delta, run.seed) for run in matching}
            if coverage != expected_coverage or len(matching) != len(expected_coverage):
                raise ValueError(
                    f"incomplete pooled tuning grid for {method}/{ridge}/{bonus}"
                )
            per_cell = [
                {
                    "delta": run.cell.delta,
                    "seed": run.seed,
                    "cumulative_pseudo_regret": float(
                        run.summary["cumulative_pseudo_regret"]
                    ),
                }
                for run in matching
            ]
            per_delta = [
                {
                    "delta": cell.delta,
                    "mean_cumulative_pseudo_regret": float(
                        np.mean(
                            [
                                row["cumulative_pseudo_regret"]
                                for row in per_cell
                                if row["delta"] == cell.delta
                            ],
                            dtype=np.float64,
                        )
                    ),
                }
                for cell in configured_cells
            ]
            mean = float(
                np.mean(
                    [row["cumulative_pseudo_regret"] for row in per_cell],
                    dtype=np.float64,
                )
            )
            candidates.append(
                {
                    "method": method,
                    "ridge": ridge,
                    "bonus_scale": bonus,
                    "grid_order": order,
                    "pooled_mean_cumulative_pseudo_regret": mean,
                    "per_delta_means": per_delta,
                    "per_cell_cumulative_pseudo_regret": per_cell,
                    "fixed_control": method in CONTROL_METHODS,
                }
            )
            choices.append((mean, order, ridge, bonus))
        winner = min(choices, key=lambda item: (item[0], item[1]))
        selected.append(
            {
                "method": method,
                "ridge": winner[2],
                "bonus_scale": winner[3],
                "pooled_mean_tuning_cumulative_pseudo_regret": winner[0],
                "tie_break_grid_order": winner[1],
                "fixed_control": method in CONTROL_METHODS,
            }
        )
    return {
        "schema_version": 1,
        "event": "wheel_benchmark_tuning_selection",
        "experiment": str(config.get("name")),
        "profile": str(config.get("profile")),
        "resolved_config_digest": config_digest(config),
        "criterion": "pooled_mean_cumulative_pseudo_regret",
        "pooling_axis": "cartesian_product_of_all_deltas_and_tuning_seeds",
        "deltas": [cell.delta for cell in configured_cells],
        "selected_on_seed_set": "tuning",
        "tuning_seeds": list(get_seed_set(config, "tuning")),
        "evaluation_seeds": list(get_seed_set(config, "evaluation")),
        "evaluation_outcomes_used": False,
        "evaluation_policies_rerun_from_scratch": True,
        "controls_have_single_fixed_setting": True,
        "common_stream_within_seed_across_deltas": True,
        "tie_break": "lowest_configured_grid_order",
        "candidates": candidates,
        "selected": selected,
    }


def validate_tuning_selection(
    config: Mapping[str, Any], artifact: Mapping[str, Any]
) -> dict[str, tuple[float, float]]:
    required = {
        "schema_version": 1,
        "event": "wheel_benchmark_tuning_selection",
        "experiment": str(config.get("name")),
        "profile": str(config.get("profile")),
        "resolved_config_digest": config_digest(config),
        "criterion": "pooled_mean_cumulative_pseudo_regret",
        "pooling_axis": "cartesian_product_of_all_deltas_and_tuning_seeds",
        "deltas": [cell.delta for cell in cells(config)],
        "selected_on_seed_set": "tuning",
        "tuning_seeds": list(get_seed_set(config, "tuning")),
        "evaluation_seeds": list(get_seed_set(config, "evaluation")),
        "evaluation_outcomes_used": False,
        "evaluation_policies_rerun_from_scratch": True,
        "controls_have_single_fixed_setting": True,
        "common_stream_within_seed_across_deltas": True,
        "tie_break": "lowest_configured_grid_order",
    }
    for key, expected in required.items():
        if artifact.get(key) != expected:
            raise ValueError(f"selection artifact {key} mismatch")
    raw_candidates = artifact.get("candidates")
    raw_selected = artifact.get("selected")
    if not isinstance(raw_candidates, list) or not isinstance(raw_selected, list):
        raise ValueError("selection artifact lacks candidates or selected rows")
    tuning_seeds = tuple(sorted(get_seed_set(config, "tuning")))
    configured_cells = cells(config)
    expected_coverage = {
        (cell.delta, seed) for cell in configured_cells for seed in tuning_seeds
    }
    candidates: dict[tuple[str, float, float], tuple[float, int]] = {}
    for item in raw_candidates:
        if not isinstance(item, Mapping):
            raise ValueError("selection candidate must be a mapping")
        method = str(item.get("method"))
        ridge = float(item.get("ridge"))
        bonus = float(item.get("bonus_scale"))
        grid = hyperparameter_grid(config, method)
        if (ridge, bonus) not in grid:
            raise ValueError("selection candidate lies outside the grid")
        order = int(item.get("grid_order"))
        if not 0 <= order < len(grid) or grid[order] != (ridge, bonus):
            raise ValueError("selection candidate grid order mismatch")
        if item.get("fixed_control") is not (method in CONTROL_METHODS):
            raise ValueError("selection candidate control label mismatch")
        per_cell = item.get("per_cell_cumulative_pseudo_regret")
        if not isinstance(per_cell, list) or any(
            not isinstance(row, Mapping) for row in per_cell
        ):
            raise ValueError("selection candidate lacks pooled cell rows")
        coverage = {
            (float(row.get("delta")), int(row.get("seed"))) for row in per_cell
        }
        if coverage != expected_coverage or len(per_cell) != len(expected_coverage):
            raise ValueError("selection candidate pooled cell coverage mismatch")
        ordered = sorted(
            per_cell, key=lambda row: (float(row["delta"]), int(row["seed"]))
        )
        mean = float(
            np.mean(
                [float(row["cumulative_pseudo_regret"]) for row in ordered],
                dtype=np.float64,
            )
        )
        if not math.isclose(
            mean,
            float(item.get("pooled_mean_cumulative_pseudo_regret")),
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError("selection candidate pooled mean mismatch")
        raw_per_delta = item.get("per_delta_means")
        if not isinstance(raw_per_delta, list) or len(raw_per_delta) != len(
            configured_cells
        ):
            raise ValueError("selection candidate per-delta means are incomplete")
        for cell in configured_cells:
            rows = [
                row for row in raw_per_delta if float(row.get("delta")) == cell.delta
            ]
            if len(rows) != 1:
                raise ValueError("selection candidate has duplicate per-delta means")
            expected_delta_mean = float(
                np.mean(
                    [
                        float(row["cumulative_pseudo_regret"])
                        for row in ordered
                        if float(row["delta"]) == cell.delta
                    ],
                    dtype=np.float64,
                )
            )
            if not math.isclose(
                float(rows[0].get("mean_cumulative_pseudo_regret")),
                expected_delta_mean,
                rel_tol=0.0,
                abs_tol=1.0e-12,
            ):
                raise ValueError("selection candidate per-delta mean mismatch")
        key = (method, ridge, bonus)
        if key in candidates:
            raise ValueError("selection artifact contains a duplicate candidate")
        candidates[key] = (mean, order)
    expected = {
        (method, ridge, bonus)
        for method in METHODS
        for ridge, bonus in hyperparameter_grid(config, method)
    }
    if set(candidates) != expected:
        raise ValueError("selection artifact has an incomplete grid")
    if len(raw_selected) != len(METHODS):
        raise ValueError("selection artifact has the wrong selected-row count")
    chosen: dict[str, tuple[float, float]] = {}
    for method in METHODS:
        rows = [
            (mean, order, ridge, bonus)
            for (candidate_method, ridge, bonus), (mean, order) in candidates.items()
            if candidate_method == method
        ]
        expected_winner = min(rows, key=lambda item: (item[0], item[1]))
        selected_rows = [item for item in raw_selected if item.get("method") == method]
        if len(selected_rows) != 1:
            raise ValueError(f"selection must contain one row for {method}")
        item = selected_rows[0]
        stated = (
            float(item.get("pooled_mean_tuning_cumulative_pseudo_regret")),
            int(item.get("tie_break_grid_order")),
            float(item.get("ridge")),
            float(item.get("bonus_scale")),
        )
        if stated != expected_winner:
            raise ValueError(f"selected setting for {method} is not the tuning argmin")
        if item.get("fixed_control") is not (method in CONTROL_METHODS):
            raise ValueError("selected control label mismatch")
        chosen[method] = (stated[2], stated[3])
    return chosen


def write_tuning_selection(
    artifact: Mapping[str, Any], path: str | Path, *, overwrite: bool = False
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.write_text(canonical_json(artifact) + "\n", encoding="ascii")
    return destination


def load_tuning_selection(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise ValueError("selection artifact must be an object")
    return value


def save_run(
    run: WheelRun,
    config: Mapping[str, Any],
    output: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    destination = Path(output)
    summary_path = destination / "summary.jsonl"
    if overwrite:
        summary_path.unlink(missing_ok=True)
    with ExperimentLogger(
        destination,
        config,
        run.seed,
        repository=Path(__file__).resolve().parents[1],
        overwrite=overwrite,
    ) as logger:
        for index, record in enumerate(run.records):
            logger.log_round(index, record)
    append_jsonl(summary_path, run.summary)
    return destination


def run_experiment(
    config: Mapping[str, Any],
    *,
    seed_set: str,
    output_root: str | Path,
    tuning_selection: str | Path | Mapping[str, Any] | None = None,
    overwrite: bool = False,
) -> tuple[WheelRun, ...]:
    validate_wheel_config(config)
    if seed_set not in {"tuning", "evaluation"}:
        raise ValueError("seed_set must be tuning or evaluation")
    root = Path(output_root)
    runs: list[WheelRun] = []
    if seed_set == "tuning":
        for cell in cells(config):
            for method in METHODS:
                for ridge, bonus in hyperparameter_grid(config, method):
                    for seed in get_seed_set(config, "tuning"):
                        run = run_policy(
                            config,
                            method,
                            seed,
                            cell=cell,
                            phase="tuning",
                            ridge=ridge,
                            bonus_scale=bonus,
                        )
                        run_config = copy.deepcopy(dict(config))
                        run_config["execution"] = {
                            "seed_set": "tuning",
                            "method": method,
                            "cell": {"delta": cell.delta, "token": cell.token},
                            "comparison": "pooled_validation_tuned",
                            "executed_policy": True,
                            "mode": "online_adaptive",
                            "hyperparameters": {
                                "ridge": ridge,
                                "bonus_scale": bonus,
                            },
                        }
                        setting = f"ridge-{ridge:g}_bonus-{bonus:g}"
                        save_run(
                            run,
                            run_config,
                            root
                            / str(config["profile"])
                            / "tuning"
                            / cell.token
                            / method
                            / setting
                            / f"seed-{seed}",
                            overwrite=overwrite,
                        )
                        runs.append(run)
        artifact = build_tuning_selection(config, runs)
        selection_path = (
            Path(tuning_selection)
            if isinstance(tuning_selection, (str, Path))
            else root / str(config["profile"]) / "tuning_selection.json"
        )
        write_tuning_selection(artifact, selection_path, overwrite=overwrite)
        return tuple(runs)

    if tuning_selection is None:
        raise ValueError("evaluation requires a tuning-selection artifact")
    artifact = (
        dict(tuning_selection)
        if isinstance(tuning_selection, Mapping)
        else load_tuning_selection(tuning_selection)
    )
    selected = validate_tuning_selection(config, artifact)
    selection_sha = hashlib.sha256(canonical_json(artifact).encode("ascii")).hexdigest()
    for cell in cells(config):
        for method in METHODS:
            ridge, bonus = selected[method]
            for seed in get_seed_set(config, "evaluation"):
                run = run_policy(
                    config,
                    method,
                    seed,
                    cell=cell,
                    phase="evaluation",
                    ridge=ridge,
                    bonus_scale=bonus,
                )
                run_config = copy.deepcopy(dict(config))
                run_config["execution"] = {
                    "seed_set": "evaluation",
                    "method": method,
                    "cell": {"delta": cell.delta, "token": cell.token},
                    "comparison": "pooled_validation_tuned",
                    "executed_policy": True,
                    "mode": "online_adaptive",
                    "hyperparameters": {"ridge": ridge, "bonus_scale": bonus},
                    "tuning_selection_sha256": selection_sha,
                    "pooled_over_all_declared_deltas": True,
                    "evaluation_rerun_from_scratch": True,
                    "evaluation_outcomes_used_for_tuning": False,
                }
                save_run(
                    run,
                    run_config,
                    root
                    / str(config["profile"])
                    / "evaluation"
                    / cell.token
                    / method
                    / f"seed-{seed}",
                    overwrite=overwrite,
                )
                runs.append(run)
    return tuple(runs)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--seed-set", choices=("tuning", "evaluation"), required=True)
    parser.add_argument("--output-root")
    parser.add_argument("--tuning-selection")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    config = load_config(args.config, profile=args.profile)
    runs = run_experiment(
        config,
        seed_set=args.seed_set,
        output_root=args.output_root or str(config["output_root"]),
        tuning_selection=args.tuning_selection,
        overwrite=args.overwrite,
    )
    print(canonical_json({"run_count": len(runs)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CONTROL_METHODS",
    "Cell",
    "METHODS",
    "METHOD_IMPLEMENTATIONS",
    "NEURAL_METHODS",
    "WheelRun",
    "build_tuning_selection",
    "configured_methods",
    "cells",
    "hyperparameter_grid",
    "linear_action_features",
    "load_tuning_selection",
    "run_experiment",
    "run_policy",
    "save_run",
    "validate_tuning_selection",
    "validate_wheel_config",
    "write_tuning_selection",
]
