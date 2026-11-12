"""Balanced contextual benchmark with leakage-free tuning and matched updates."""

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
from .nonlinear_environment import (
    ACTION_COUNT,
    CONTEXT_DIMENSION,
    PARAMETER_DIMENSION,
    NonlinearBanditEnvironment,
    SmallTanhMLP,
    enumerate_rademacher_contexts,
)


FloatArray = NDArray[np.float64]
DEFAULT_CONFIG = Path(__file__).with_name("configs") / "balanced_benchmark.yaml"
METHODS = (
    "linucb",
    "linear_ts",
    "cc_ucb_full_ggn_cg",
    "neural_linear",
    "neural_ucb",
    "neural_ts",
    "diagonal_full_network_ucb",
    "frozen_last_layer_ucb",
    "greedy_full_network",
    "gaussian_ucb1",
    "gaussian_context_free_ts",
)
FULL_NETWORK_METHODS = {
    "cc_ucb_full_ggn_cg",
    "neural_ucb",
    "neural_ts",
    "diagonal_full_network_ucb",
    "greedy_full_network",
}
CONTEXT_FREE_METHODS = {"gaussian_ucb1", "gaussian_context_free_ts"}
CONTEXTUAL_METHODS = set(METHODS) - CONTEXT_FREE_METHODS
METHOD_IMPLEMENTATIONS = {
    "linucb": "local_fixed_feature_linear_ucb",
    "linear_ts": "local_fixed_feature_gaussian_linear_thompson_sampling",
    "cc_ucb_full_ggn_cg": "current_parameter_relinearized_full_ggn_residual_checked_cg_ucb",
    "neural_linear": "frozen_initialized_representation_bayesian_linear_head_ts",
    "neural_ucb": "local_full_network_linearized_ucb",
    "neural_ts": "local_full_network_linearized_gaussian_thompson_sampling",
    "diagonal_full_network_ucb": "local_diagonal_full_network_linearized_ucb",
    "frozen_last_layer_ucb": "frozen_initialized_representation_bayesian_linear_head_ucb",
    "greedy_full_network": "local_full_network_mean_greedy",
    "gaussian_ucb1": "context_free_gaussian_ucb1",
    "gaussian_context_free_ts": "context_free_independent_gaussian_thompson_sampling",
}


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
    value = config.get(name, {})
    if not isinstance(value, Mapping):
        raise ValueError(f"config.{name} must be a mapping")
    return value


def configured_methods(config: Mapping[str, Any]) -> tuple[str, ...]:
    values = config.get("methods", METHODS)
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValueError("methods must be a sequence")
    result = tuple(str(value) for value in values)
    if len(set(result)) != len(result) or not result:
        raise ValueError("methods must be nonempty and unique")
    unknown = set(result) - set(METHODS)
    if unknown:
        raise ValueError(f"unknown methods: {sorted(unknown)}")
    return result


def linear_action_features(context: ArrayLike) -> FloatArray:
    x = np.asarray(context, dtype=np.float64)
    if x.shape != (CONTEXT_DIMENSION,):
        raise ValueError("context has the wrong shape")
    rows: list[FloatArray] = []
    for action in range(ACTION_COUNT):
        indicator = np.zeros(ACTION_COUNT, dtype=np.float64)
        indicator[action] = 1.0
        rows.append(np.concatenate((x, indicator, np.kron(x, indicator))))
    return np.asarray(rows, dtype=np.float64)


@dataclass(frozen=True)
class BalancedStream:
    contexts: FloatArray
    noises: FloatArray
    digest: str


@dataclass(frozen=True)
class PostActionOutcome:
    reward: float
    pseudo_regret: float
    optimal_action: int


class PostActionTeacherOracle:
    """Expose teacher information only after a policy has committed an action."""

    def __init__(self, noise_std: float) -> None:
        self.__environment = NonlinearBanditEnvironment(0, noise_std=noise_std)

    def observe_after_action(
        self, context: ArrayLike, action: int, realized_noise: float
    ) -> PostActionOutcome:
        if isinstance(action, (bool, np.bool_)) or not isinstance(
            action, (int, np.integer)
        ):
            raise TypeError("a committed integer action is required")
        action_index = int(action)
        if not 0 <= action_index < ACTION_COUNT:
            raise ValueError("committed action is outside the action set")
        means = self.__environment.mean_rewards(context)
        optimal_action = int(np.argmax(means))
        return PostActionOutcome(
            reward=float(means[action_index] + realized_noise),
            pseudo_regret=float(means[optimal_action] - means[action_index]),
            optimal_action=optimal_action,
        )


def make_stream(seed: int, rounds: int, noise_std: float) -> BalancedStream:
    environment = NonlinearBanditEnvironment(
        derive_seed(int(seed), "balanced_benchmark", "environment"),
        noise_std=noise_std,
    )
    contexts = np.stack([environment.draw_context() for _ in range(rounds)])
    noises = np.asarray([environment.draw_noise() for _ in range(rounds)], dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(np.ascontiguousarray(contexts, dtype="<f8").tobytes())
    digest.update(np.ascontiguousarray(noises, dtype="<f8").tobytes())
    contexts.setflags(write=False)
    noises.setflags(write=False)
    return BalancedStream(contexts, noises, digest.hexdigest())


def winner_counts() -> tuple[int, ...]:
    environment = NonlinearBanditEnvironment(0)
    winners = [environment.optimal_action(x) for x in enumerate_rademacher_contexts()]
    return tuple(int(value) for value in np.bincount(winners, minlength=ACTION_COUNT))


def hyperparameter_grid(
    config: Mapping[str, Any], method: str
) -> tuple[tuple[float, float], ...]:
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    ridges = tuple(_positive(value, name="ridge") for value in config.get("ridge_grid", ()))
    bonuses = tuple(_positive(value, name="bonus") for value in config.get("bonus_grid", ()))
    if not ridges or not bonuses:
        raise ValueError("ridge_grid and bonus_grid must be nonempty")
    if method == "greedy_full_network":
        return ((ridges[0], 0.0),)
    if method == "gaussian_ucb1":
        return tuple((0.0, bonus) for bonus in bonuses)
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
    reward: float,
    *,
    trainable: FloatArray | NDArray[np.int64],
    learning_rate: float,
    model_ridge: float,
    noise_variance: float,
    maximum_step_norm: float,
) -> tuple[FloatArray, float]:
    indices = np.asarray(trainable, dtype=np.int64)
    prediction, jacobian = model.mean_and_jacobian(theta, context, action)
    gradient = (prediction - reward) * jacobian[indices] / noise_variance
    gradient += model_ridge * theta[indices]
    step = learning_rate * gradient
    norm = float(np.linalg.norm(step))
    if norm > maximum_step_norm:
        step *= maximum_step_norm / norm
    result = theta.copy()
    result[indices] -= step
    return result, float(np.linalg.norm(step))


@dataclass(frozen=True)
class BalancedRun:
    method: str
    seed: int
    phase: str
    ridge: float
    bonus_scale: float
    records: tuple[dict[str, Any], ...]
    summary: dict[str, Any]

    def deterministic_signature(self) -> str:
        records = [
            {key: value for key, value in record.items() if not key.endswith("_seconds")}
            for record in self.records
        ]
        return hashlib.sha256(canonical_json(records).encode("ascii")).hexdigest()


def run_policy(
    config: Mapping[str, Any],
    method: str,
    seed: int,
    *,
    phase: str,
    ridge: float,
    bonus_scale: float,
) -> BalancedRun:
    if method not in configured_methods(config):
        raise ValueError(f"method {method!r} is not enabled")
    if phase not in {"tuning", "evaluation"}:
        raise ValueError("phase must be tuning or evaluation")
    ridge_value = _nonnegative(ridge, name="ridge")
    bonus = _nonnegative(bonus_scale, name="bonus_scale")
    if method != "gaussian_ucb1" and ridge_value <= 0.0:
        raise ValueError("this method requires positive ridge")
    if method == "greedy_full_network" and bonus != 0.0:
        raise ValueError("greedy requires zero bonus")

    environment_config = _section(config, "environment")
    model_config = _section(config, "model")
    rounds = int(config["tuning_rounds"] if phase == "tuning" else config["rounds"])
    rounds = _positive_int(rounds, name="rounds")
    noise_std = _positive(environment_config.get("noise_std"), name="noise_std")
    variance = noise_std * noise_std
    learning_rate = _positive(model_config.get("learning_rate"), name="learning_rate")
    model_ridge = _nonnegative(model_config.get("model_ridge"), name="model_ridge")
    updates = _positive_int(model_config.get("updates_per_round"), name="updates_per_round")
    if updates != 1:
        raise ValueError("the matched protocol requires one update per round")
    maximum_step = _positive(model_config.get("maximum_step_norm"), name="maximum_step_norm")
    cg_config = _section(config, "cg")
    cg_tolerance = _positive(
        cg_config.get("relative_residual_tolerance"),
        name="cg.relative_residual_tolerance",
    )
    cg_max_iterations = _positive_int(
        cg_config.get("max_iterations"), name="cg.max_iterations"
    )

    stream = make_stream(seed, rounds, noise_std)
    teacher_oracle = PostActionTeacherOracle(noise_std)
    model = SmallTanhMLP()
    theta = np.zeros(PARAMETER_DIMENSION, dtype=np.float64)
    frozen_full_gradients: list[FloatArray] = []
    history_contexts: list[FloatArray] = []
    history_actions: list[int] = []
    linear_dimension = linear_action_features(stream.contexts[0]).shape[1]
    linear_matrix = max(ridge_value, 1.0e-12) * np.eye(linear_dimension)
    linear_rhs = np.zeros(linear_dimension, dtype=np.float64)
    head_indices = model.head_indices
    head_matrix = ridge_value * np.eye(head_indices.size, dtype=np.float64)
    head_rhs = np.zeros(head_indices.size, dtype=np.float64)
    arm_counts = np.zeros(ACTION_COUNT, dtype=np.int64)
    arm_reward_sums = np.zeros(ACTION_COUNT, dtype=np.float64)
    rng = np.random.default_rng(derive_seed(int(seed), "balanced_benchmark", method, "policy"))
    records: list[dict[str, Any]] = []
    cumulative_regret = 0.0
    cumulative_reward = 0.0
    cumulative_runtime = 0.0
    cumulative_state_update = 0.0
    cumulative_model_update = 0.0
    cumulative_posterior_update = 0.0
    cumulative_uncertainty = 0.0
    disagreements = 0
    process = psutil.Process()
    host_rss_at_start = process.memory_info().rss
    peak_memory = host_rss_at_start
    maximum_persistent_numeric_state = 0
    total_cg_iterations = 0
    total_cg_operator_calls = 0
    maximum_cg_relative_residual = 0.0
    all_cg_solves_converged = True

    for round_index in range(rounds):
        started = time.perf_counter()
        context = np.asarray(stream.contexts[round_index], dtype=np.float64)
        uncertainty_started = time.perf_counter()
        curvature_dimension = 0
        cg_iterations: list[int] = []
        cg_relative_residuals: list[float] = []
        cg_operator_calls: list[int] = []
        cg_converged: list[bool] = []
        predicted: FloatArray

        if method in {"linucb", "linear_ts"}:
            candidates = linear_action_features(context)
            estimate = np.linalg.solve(linear_matrix, linear_rhs)
            predicted = candidates @ estimate
            if method == "linucb":
                solved = np.linalg.solve(linear_matrix, candidates.T).T
                widths = np.sqrt(np.maximum(np.einsum("ij,ij->i", candidates, solved), 0.0))
                scores = predicted + bonus * widths
            else:
                sampled = _posterior_sample(rng, linear_matrix, estimate, bonus)
                scores = candidates @ sampled
                widths = np.sqrt(
                    np.maximum(
                        np.einsum(
                            "ij,ij->i", candidates, np.linalg.solve(linear_matrix, candidates.T).T
                        ),
                        0.0,
                    )
                )
            curvature_dimension = linear_dimension
        elif method in {"gaussian_ucb1", "gaussian_context_free_ts"}:
            precision = max(ridge_value, 1.0e-12) + arm_counts / variance
            predicted = (arm_reward_sums / variance) / precision
            widths = 1.0 / np.sqrt(precision)
            if method == "gaussian_ucb1":
                if round_index < ACTION_COUNT:
                    scores = np.full(ACTION_COUNT, -1.0e300)
                    scores[round_index] = 1.0e300
                else:
                    scores = predicted + bonus * np.sqrt(
                        2.0 * math.log(float(round_index + 1)) / arm_counts
                    )
            else:
                scores = rng.normal(predicted, bonus * widths)
            curvature_dimension = ACTION_COUNT
        elif method in {"neural_linear", "frozen_last_layer_ucb"}:
            frozen_theta = np.zeros(PARAMETER_DIMENSION, dtype=np.float64)
            base_predictions = model.means(frozen_theta, context)
            queries = model.jacobians(frozen_theta, context)[:, head_indices]
            head_estimate = np.linalg.solve(head_matrix, head_rhs)
            predicted = base_predictions + queries @ head_estimate
            solved = np.linalg.solve(head_matrix, queries.T).T
            width_sq = np.einsum("ij,ij->i", queries, solved)
            widths = np.sqrt(np.maximum(width_sq, 0.0))
            if method == "neural_linear":
                sampled_head = _posterior_sample(
                    rng, head_matrix, head_estimate, bonus
                )
                scores = base_predictions + queries @ sampled_head
            else:
                scores = predicted + bonus * widths
            curvature_dimension = int(head_indices.size)
        else:
            predicted = model.means(theta, context)
            full_jacobians = model.jacobians(theta, context)
            if method == "greedy_full_network":
                widths = np.zeros(ACTION_COUNT, dtype=np.float64)
                scores = predicted.copy()
            elif method == "cc_ucb_full_ggn_cg":
                current_history = (
                    np.stack(
                        [
                            model.jacobian(theta, old_context, old_action)
                            for old_context, old_action in zip(
                                history_contexts, history_actions, strict=True
                            )
                        ]
                    )
                    if history_contexts
                    else np.empty((0, PARAMETER_DIMENSION), dtype=np.float64)
                )
                fixed_history = current_history.copy()
                operator_call_count = 0

                def current_ggn_matvec(vector: FloatArray) -> FloatArray:
                    nonlocal operator_call_count
                    operator_call_count += 1
                    return (
                        ridge_value * vector
                        + fixed_history.T @ (fixed_history @ vector) / variance
                    )

                width_sq = np.empty(ACTION_COUNT, dtype=np.float64)
                for query in full_jacobians:
                    calls_before = operator_call_count
                    result = conjugate_gradient(
                        current_ggn_matvec,
                        query,
                        tolerance=cg_tolerance,
                        absolute_tolerance=0.0,
                        max_iterations=cg_max_iterations,
                        raise_on_nonconvergence=False,
                    )
                    explicit_residual = query - current_ggn_matvec(result.solution)
                    query_norm = float(np.linalg.norm(query))
                    relative_residual = (
                        float(np.linalg.norm(explicit_residual) / query_norm)
                        if query_norm > 0.0
                        else 0.0
                    )
                    tolerance_slack = 1024.0 * np.finfo(np.float64).eps
                    converged = bool(
                        result.converged
                        and relative_residual <= cg_tolerance + tolerance_slack
                    )
                    if not converged:
                        raise RuntimeError(
                            "current-GGN CG failed its original-system residual check"
                        )
                    value = float(query @ result.solution)
                    if not np.isfinite(value) or value < -1e-10:
                        raise FloatingPointError("current-GGN CG produced an invalid width")
                    width_sq[len(cg_iterations)] = max(value, 0.0)
                    cg_iterations.append(int(result.iterations))
                    cg_relative_residuals.append(relative_residual)
                    cg_operator_calls.append(operator_call_count - calls_before)
                    cg_converged.append(converged)
                widths = np.sqrt(width_sq)
                scores = predicted + bonus * widths
                curvature_dimension = PARAMETER_DIMENSION
            else:
                historical = (
                    np.stack(frozen_full_gradients)
                    if frozen_full_gradients
                    else np.empty((0, PARAMETER_DIMENSION), dtype=np.float64)
                )
                queries = full_jacobians
                matrix = ridge_value * np.eye(queries.shape[1])
                if historical.shape[0]:
                    matrix += historical.T @ historical / variance
                if method == "diagonal_full_network_ucb":
                    diagonal = np.diag(matrix)
                    width_sq = np.sum(queries * queries / diagonal[None, :], axis=1)
                else:
                    solved = np.linalg.solve(matrix, queries.T).T
                    width_sq = np.einsum("ij,ij->i", queries, solved)
                widths = np.sqrt(np.maximum(width_sq, 0.0))
                if method in {"neural_ts"}:
                    sampled_delta = _posterior_sample(
                        rng, matrix, np.zeros(queries.shape[1]), bonus
                    )
                    scores = predicted + queries @ sampled_delta
                else:
                    scores = predicted + bonus * widths
                curvature_dimension = int(queries.shape[1])

        uncertainty_seconds = time.perf_counter() - uncertainty_started
        if method == "cc_ucb_full_ggn_cg":
            total_cg_iterations += sum(cg_iterations)
            total_cg_operator_calls += sum(cg_operator_calls)
            maximum_cg_relative_residual = max(
                maximum_cg_relative_residual,
                max(cg_relative_residuals, default=0.0),
            )
            all_cg_solves_converged = all_cg_solves_converged and all(cg_converged)
        action = int(np.argmax(scores))
        greedy_action = int(np.argmax(predicted))
        disagreements += int(action != greedy_action)
        outcome = teacher_oracle.observe_after_action(
            context, action, float(stream.noises[round_index])
        )
        optimal_action = outcome.optimal_action
        reward = outcome.reward
        regret = outcome.pseudo_regret
        cumulative_regret += regret
        cumulative_reward += reward

        update_started = time.perf_counter()
        update_norm = 0.0
        if method in {"linucb", "linear_ts"}:
            selected = candidates[action]
            linear_matrix += np.outer(selected, selected) / variance
            linear_rhs += selected * reward / variance
        elif method in CONTEXT_FREE_METHODS:
            arm_counts[action] += 1
            arm_reward_sums[action] += reward
        elif method in {"neural_linear", "frozen_last_layer_ucb"}:
            selected_head = queries[action]
            centered_reward = reward - float(base_predictions[action])
            head_matrix += np.outer(selected_head, selected_head) / variance
            head_rhs += selected_head * centered_reward / variance
        else:
            selected_full = model.jacobian(theta, context, action)
            if method == "cc_ucb_full_ggn_cg":
                history_contexts.append(context.copy())
                history_actions.append(action)
            else:
                frozen_full_gradients.append(selected_full.copy())
            theta, update_norm = _model_update(
                model,
                theta,
                context,
                action,
                reward,
                trainable=np.arange(PARAMETER_DIMENSION, dtype=np.int64),
                learning_rate=learning_rate,
                model_ridge=model_ridge,
                noise_variance=variance,
                maximum_step_norm=maximum_step,
            )
        update_seconds = time.perf_counter() - update_started
        model_update_seconds = update_seconds if method in FULL_NETWORK_METHODS else 0.0
        posterior_update_seconds = (
            update_seconds if method not in FULL_NETWORK_METHODS else 0.0
        )
        elapsed = time.perf_counter() - started
        cumulative_runtime += elapsed
        cumulative_state_update += update_seconds
        cumulative_model_update += model_update_seconds
        cumulative_posterior_update += posterior_update_seconds
        cumulative_uncertainty += uncertainty_seconds
        peak_memory = max(peak_memory, process.memory_info().rss)
        if method in {"linucb", "linear_ts"}:
            persistent_numeric_state = linear_matrix.nbytes + linear_rhs.nbytes
        elif method in CONTEXT_FREE_METHODS:
            persistent_numeric_state = arm_counts.nbytes + arm_reward_sums.nbytes
        elif method in {"neural_linear", "frozen_last_layer_ucb"}:
            persistent_numeric_state = head_matrix.nbytes + head_rhs.nbytes
        elif method == "cc_ucb_full_ggn_cg":
            persistent_numeric_state = theta.nbytes + sum(
                item.nbytes for item in history_contexts
            ) + 8 * len(history_actions)
        else:
            persistent_numeric_state = theta.nbytes + sum(
                item.nbytes for item in frozen_full_gradients
            )
        maximum_persistent_numeric_state = max(
            maximum_persistent_numeric_state, persistent_numeric_state
        )

        record = {
                "round_number": round_index + 1,
                "method": method,
                "method_implementation": METHOD_IMPLEMENTATIONS[method],
                "policy_type": (
                    "context_free" if method in CONTEXT_FREE_METHODS else "contextual"
                ),
                "phase": phase,
                "executed_policy": True,
                "execution_mode": "online_adaptive",
                "certification_category": "uncertified_diagnostic",
                "context": context.tolist(),
                "environment_stream_sha256": stream.digest,
                "selected_action": action,
                "optimal_action_posthoc": optimal_action,
                "observed_reward": reward,
                "cumulative_reward": cumulative_reward,
                "mean_reward": cumulative_reward / float(round_index + 1),
                "realized_noise": float(stream.noises[round_index]),
                "instantaneous_pseudo_regret": regret,
                "cumulative_pseudo_regret": cumulative_regret,
                "predicted_means_all_actions": predicted.tolist(),
                "policy_scores_all_actions": np.asarray(scores).tolist(),
                "predictive_widths_all_actions": np.asarray(widths).tolist(),
                "action_disagrees_with_mean_greedy": bool(action != greedy_action),
                "cumulative_action_disagreement_rate": disagreements / float(round_index + 1),
                "ridge": ridge_value,
                "bonus_scale": bonus,
                "curvature_dimension": curvature_dimension,
                "model_update_norm": update_norm,
                "model_update_count": int(method in FULL_NETWORK_METHODS),
                "posterior_update_count": int(method not in FULL_NETWORK_METHODS),
                "uncertainty_seconds": uncertainty_seconds,
                "state_update_seconds": update_seconds,
                "model_update_seconds": model_update_seconds,
                "posterior_update_seconds": posterior_update_seconds,
                "round_runtime_seconds": elapsed,
                "cumulative_runtime_seconds": cumulative_runtime,
                "cumulative_uncertainty_seconds": cumulative_uncertainty,
                "cumulative_state_update_seconds": cumulative_state_update,
                "cumulative_model_update_seconds": cumulative_model_update,
                "cumulative_posterior_update_seconds": cumulative_posterior_update,
                "peak_host_memory_bytes": peak_memory,
                "host_rss_at_start_bytes": host_rss_at_start,
                "peak_host_rss_delta_bytes": max(
                    0, peak_memory - host_rss_at_start
                ),
                "persistent_numeric_policy_state_bytes": persistent_numeric_state,
            }
        if method == "cc_ucb_full_ggn_cg":
            record.update(
                {
                    "cg_iterations_all_actions": cg_iterations,
                    "cg_iterations": cg_iterations,
                    "cg_relative_residuals_all_actions": cg_relative_residuals,
                    "cg_operator_calls_all_actions": cg_operator_calls,
                    "operator_matvecs": sum(cg_operator_calls),
                    "cumulative_operator_matvecs": total_cg_operator_calls,
                    "cg_all_actions_converged": all(cg_converged),
                    "cg_relative_residual_tolerance": cg_tolerance,
                    "current_parameter_history_relinearized": True,
                    "matrix_free_dense_gram_materialized": False,
                }
            )
        records.append(record)

    summary = {
        "schema_version": 1,
        "event": "balanced_benchmark_run_summary",
        "experiment": str(config.get("name", "balanced_benchmark")),
        "profile": str(config.get("profile", "unknown")),
        "method": method,
        "method_implementation": METHOD_IMPLEMENTATIONS[method],
        "published_implementation_claim": False,
        "policy_type": (
            "context_free" if method in CONTEXT_FREE_METHODS else "contextual"
        ),
        "seed": int(seed),
        "phase": phase,
        "comparison": "validation_tuned",
        "executed_policy": True,
        "execution_mode": "online_adaptive",
        "rounds": rounds,
        "cumulative_pseudo_regret": cumulative_regret,
        "cumulative_reward": cumulative_reward,
        "mean_reward": cumulative_reward / float(rounds),
        "runtime_seconds": cumulative_runtime,
        "state_update_seconds": cumulative_state_update,
        "model_update_seconds": cumulative_model_update,
        "posterior_update_seconds": cumulative_posterior_update,
        "uncertainty_seconds": cumulative_uncertainty,
        "peak_host_memory_bytes": peak_memory,
        "host_rss_at_start_bytes": host_rss_at_start,
        "peak_host_rss_delta_bytes": max(0, peak_memory - host_rss_at_start),
        "maximum_persistent_numeric_policy_state_bytes": (
            maximum_persistent_numeric_state
        ),
        "action_disagreement_rate": disagreements / float(rounds),
        "ridge": ridge_value,
        "bonus_scale": bonus,
        "hyperparameters": {"ridge": ridge_value, "bonus_scale": bonus},
        "environment_stream_sha256": stream.digest,
        "winner_counts_on_exact_context_support": list(winner_counts()),
        "common_random_numbers": True,
        "matched_full_network_update_rule": method in FULL_NETWORK_METHODS,
        "representation_update_protocol": (
            "frozen_initialized_backbone"
            if method in {"neural_linear", "frozen_last_layer_ucb"}
            else "one_matched_full_network_sgd_step_per_round"
            if method in FULL_NETWORK_METHODS
            else "not_applicable"
        ),
        "certification_category": "uncertified_diagnostic",
    }
    if method == "cc_ucb_full_ggn_cg":
        summary.update(
            {
                "cg_total_iterations": total_cg_iterations,
                "cg_iterations_per_action": total_cg_iterations
                / float(rounds * ACTION_COUNT),
                "cg_total_operator_calls": total_cg_operator_calls,
                "cg_maximum_relative_residual": maximum_cg_relative_residual,
                "cg_relative_residual_tolerance": cg_tolerance,
                "all_cg_solves_converged": all_cg_solves_converged,
                "cg_solver_status": (
                    "original_system_residual_checked_not_energy_error_certified"
                ),
                "current_parameter_history_relinearized": True,
                "matrix_free_dense_gram_materialized": False,
            }
        )
    return BalancedRun(
        method, int(seed), phase, ridge_value, bonus, tuple(records), summary
    )


def _candidate_key(run: BalancedRun) -> tuple[str, float, float]:
    return run.method, run.ridge, run.bonus_scale


def build_tuning_selection(
    config: Mapping[str, Any], runs: Sequence[BalancedRun]
) -> dict[str, Any]:
    if not runs or any(run.phase != "tuning" for run in runs):
        raise ValueError("selection requires tuning runs only")
    tuning_seeds = tuple(sorted(int(seed) for seed in get_seed_set(config, "tuning")))
    grouped: dict[tuple[str, float, float], list[BalancedRun]] = {}
    for run in runs:
        grouped.setdefault(_candidate_key(run), []).append(run)
    candidates: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    for method in configured_methods(config):
        choices: list[tuple[float, int, float, float]] = []
        for order, (ridge, bonus) in enumerate(hyperparameter_grid(config, method)):
            matching = sorted(grouped.get((method, ridge, bonus), []), key=lambda item: item.seed)
            if tuple(run.seed for run in matching) != tuning_seeds:
                raise ValueError(f"incomplete tuning grid for {method}/{ridge}/{bonus}")
            per_seed = {
                str(run.seed): float(run.summary["cumulative_pseudo_regret"])
                for run in matching
            }
            mean = float(np.mean(list(per_seed.values()), dtype=np.float64))
            candidates.append(
                {
                    "method": method,
                    "ridge": ridge,
                    "bonus_scale": bonus,
                    "grid_order": order,
                    "mean_cumulative_pseudo_regret": mean,
                    "per_seed_cumulative_pseudo_regret": per_seed,
                }
            )
            choices.append((mean, order, ridge, bonus))
        mean, order, ridge, bonus = min(choices, key=lambda item: (item[0], item[1]))
        selected.append(
            {
                "method": method,
                "ridge": ridge,
                "bonus_scale": bonus,
                "mean_tuning_cumulative_pseudo_regret": mean,
                "tie_break_grid_order": order,
            }
        )
    return {
        "schema_version": 1,
        "event": "balanced_benchmark_tuning_selection",
        "experiment": str(config.get("name")),
        "profile": str(config.get("profile")),
        "resolved_config_digest": config_digest(config),
        "criterion": "mean_cumulative_pseudo_regret",
        "selected_on_seed_set": "tuning",
        "tuning_seeds": list(get_seed_set(config, "tuning")),
        "evaluation_seeds": list(get_seed_set(config, "evaluation")),
        "evaluation_outcomes_used": False,
        "evaluation_policies_rerun_from_scratch": True,
        "tie_break": "lowest_configured_grid_order",
        "candidates": candidates,
        "selected": selected,
    }


def validate_tuning_selection(
    config: Mapping[str, Any], artifact: Mapping[str, Any]
) -> dict[str, tuple[float, float]]:
    required = {
        "schema_version": 1,
        "event": "balanced_benchmark_tuning_selection",
        "experiment": str(config.get("name")),
        "profile": str(config.get("profile")),
        "resolved_config_digest": config_digest(config),
        "criterion": "mean_cumulative_pseudo_regret",
        "selected_on_seed_set": "tuning",
        "tuning_seeds": list(get_seed_set(config, "tuning")),
        "evaluation_seeds": list(get_seed_set(config, "evaluation")),
        "evaluation_outcomes_used": False,
        "evaluation_policies_rerun_from_scratch": True,
        "tie_break": "lowest_configured_grid_order",
    }
    for key, expected in required.items():
        if artifact.get(key) != expected:
            raise ValueError(f"selection artifact {key} mismatch")
    raw_candidates = artifact.get("candidates")
    raw_selected = artifact.get("selected")
    if not isinstance(raw_candidates, list) or not isinstance(raw_selected, list):
        raise ValueError("selection artifact lacks candidates or selected rows")
    tuning_keys = {str(seed) for seed in get_seed_set(config, "tuning")}
    candidates: dict[tuple[str, float, float], tuple[float, int]] = {}
    for item in raw_candidates:
        method = str(item.get("method"))
        ridge = float(item.get("ridge"))
        bonus = float(item.get("bonus_scale"))
        grid = hyperparameter_grid(config, method)
        if (ridge, bonus) not in grid:
            raise ValueError("selection candidate lies outside the grid")
        order = int(item.get("grid_order"))
        if not 0 <= order < len(grid) or grid[order] != (ridge, bonus):
            raise ValueError("selection candidate grid order mismatch")
        per_seed = item.get("per_seed_cumulative_pseudo_regret")
        if not isinstance(per_seed, Mapping) or set(per_seed) != tuning_keys:
            raise ValueError("selection candidate seed coverage mismatch")
        mean = float(np.mean([float(per_seed[key]) for key in sorted(per_seed)], dtype=np.float64))
        if not math.isclose(
            mean,
            float(item.get("mean_cumulative_pseudo_regret")),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("selection candidate mean mismatch")
        candidate_key = (method, ridge, bonus)
        if candidate_key in candidates:
            raise ValueError("selection artifact contains a duplicate candidate")
        candidates[candidate_key] = (mean, order)
    expected = {
        (method, ridge, bonus)
        for method in configured_methods(config)
        for ridge, bonus in hyperparameter_grid(config, method)
    }
    if set(candidates) != expected:
        raise ValueError("selection artifact has an incomplete grid")
    chosen: dict[str, tuple[float, float]] = {}
    if len(raw_selected) != len(configured_methods(config)) or {
        str(item.get("method")) for item in raw_selected
    } != set(configured_methods(config)):
        raise ValueError("selection artifact has unexpected selected rows")
    for method in configured_methods(config):
        rows = [
            (mean, order, ridge, bonus)
            for (candidate_method, ridge, bonus), (mean, order) in candidates.items()
            if candidate_method == method
        ]
        expected_winner = min(rows, key=lambda item: (item[0], item[1]))
        selected_rows = [item for item in raw_selected if item.get("method") == method]
        if len(selected_rows) != 1:
            raise ValueError(f"selection must contain exactly one row for {method}")
        row = selected_rows[0]
        stated = (
            float(row.get("mean_tuning_cumulative_pseudo_regret")),
            int(row.get("tie_break_grid_order")),
            float(row.get("ridge")),
            float(row.get("bonus_scale")),
        )
        if stated != expected_winner:
            raise ValueError(f"selected setting for {method} is not the tuning argmin")
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
    run: BalancedRun,
    config: Mapping[str, Any],
    output: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    destination = Path(output)
    summary_path = destination / "summary.jsonl"
    if overwrite:
        for name in ("manifest.jsonl", "raw.jsonl", "summary.jsonl"):
            (destination / name).unlink(missing_ok=True)
    with ExperimentLogger(
        destination,
        config,
        run.seed,
        repository=Path(__file__).resolve().parents[1],
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
) -> tuple[BalancedRun, ...]:
    if seed_set not in {"tuning", "evaluation"}:
        raise ValueError("seed_set must be tuning or evaluation")
    root = Path(output_root)
    runs: list[BalancedRun] = []
    if seed_set == "tuning":
        for method in configured_methods(config):
            for ridge, bonus in hyperparameter_grid(config, method):
                for seed in get_seed_set(config, "tuning"):
                    run = run_policy(
                        config, method, seed, phase="tuning", ridge=ridge, bonus_scale=bonus
                    )
                    run_config = copy.deepcopy(dict(config))
                    run_config["execution"] = {
                        "seed_set": "tuning",
                        "method": method,
                        "comparison": "validation_tuned",
                        "hyperparameters": {"ridge": ridge, "bonus_scale": bonus},
                    }
                    cell = f"ridge-{ridge:g}_bonus-{bonus:g}"
                    save_run(
                        run,
                        run_config,
                        root / str(config["profile"]) / "tuning" / method / cell / f"seed-{seed}",
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
    for method in configured_methods(config):
        ridge, bonus = selected[method]
        for seed in get_seed_set(config, "evaluation"):
            run = run_policy(
                config, method, seed, phase="evaluation", ridge=ridge, bonus_scale=bonus
            )
            run_config = copy.deepcopy(dict(config))
            run_config["execution"] = {
                "seed_set": "evaluation",
                "method": method,
                "comparison": "validation_tuned",
                "hyperparameters": {"ridge": ridge, "bonus_scale": bonus},
                "tuning_selection_sha256": selection_sha,
                "evaluation_rerun_from_scratch": True,
            }
            save_run(
                run,
                run_config,
                root / str(config["profile"]) / "evaluation" / method / f"seed-{seed}",
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
    print(json.dumps({"run_count": len(runs)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BalancedRun",
    "BalancedStream",
    "CONTEXTUAL_METHODS",
    "CONTEXT_FREE_METHODS",
    "FULL_NETWORK_METHODS",
    "METHOD_IMPLEMENTATIONS",
    "METHODS",
    "PostActionOutcome",
    "PostActionTeacherOracle",
    "build_tuning_selection",
    "configured_methods",
    "hyperparameter_grid",
    "linear_action_features",
    "load_tuning_selection",
    "make_stream",
    "run_experiment",
    "run_policy",
    "save_run",
    "validate_tuning_selection",
    "winner_counts",
    "write_tuning_selection",
]
