"""Run the controlled positive-gap validation study.

The environment is a fixed-feature Gaussian linear bandit.  Each round has one
unique optimal action and every suboptimal action is separated from it by the
configured gap.  The gap is used only to construct and audit the environment;
it is never supplied to a policy.
"""

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
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from .artifact_utils import (
    input_set_sha256,
    sha256_file,
    write_deterministic_npz,
    write_json_artifact,
)
from .config import config_digest, get_seed_set, load_config
from .curvature_operators import conjugate_gradient
from .logging_utils import (
    canonical_json,
    collect_run_metadata,
    derive_seed,
    seed_everything,
)


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
BoolArray = NDArray[np.bool_]

DEFAULT_CONFIG = Path(__file__).with_name("configs") / "gap_dependent_validation.yaml"
METHODS = (
    "exact_full",
    "full_cg",
    "rank_truncation",
    "diagonal",
    "greedy",
)
SMOKE_EVIDENCE_SCOPE = "SMOKE ONLY - not main-paper evidence"


@dataclass(frozen=True)
class BanditStream:
    features: FloatArray
    noises: FloatArray
    theta_star: FloatArray
    optimal_actions: IntArray
    true_means: FloatArray
    stream_sha256: str


@dataclass(frozen=True)
class Trajectory:
    arrays: dict[str, NDArray[np.generic]]
    summary: dict[str, Any]


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _positive_float(value: Any, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def validate_study_config(config: Mapping[str, Any]) -> None:
    rounds = _positive_int(config["rounds"], name="rounds")
    dimension = _positive_int(config["dimension"], name="dimension")
    action_count = _positive_int(config["action_count"], name="action_count")
    rank = _positive_int(config["target_rank"], name="target_rank")
    if action_count < 2:
        raise ValueError("action_count must be at least two")
    if rank >= dimension:
        raise ValueError("target_rank must be smaller than dimension")

    horizons = tuple(int(value) for value in config["horizons"])
    if not horizons or list(horizons) != sorted(set(horizons)):
        raise ValueError("horizons must be a strictly increasing unique list")
    if horizons[0] <= 0 or horizons[-1] != rounds:
        raise ValueError("horizons must be positive and end at rounds")

    gaps = tuple(float(value) for value in config["gaps"])
    if not gaps or list(gaps) != sorted(set(gaps)) or any(gap <= 0.0 for gap in gaps):
        raise ValueError("gaps must be a strictly increasing positive list")
    feature_bound = _positive_float(config["feature_bound"], name="feature_bound")
    parameter_norm = _positive_float(config["parameter_norm"], name="parameter_norm")
    if gaps[-1] >= 2.0 * feature_bound * parameter_norm:
        raise ValueError("every gap must be below 2 * feature_bound * parameter_norm")

    methods = tuple(str(value) for value in config["methods"])
    if methods != METHODS:
        raise ValueError(f"methods must equal the preregistered order {METHODS}")
    _positive_float(config["ridge"], name="ridge")
    _positive_float(config["noise_std"], name="noise_std")
    delta = _positive_float(config["confidence_delta"], name="confidence_delta")
    if delta >= 1.0:
        raise ValueError("confidence_delta must be below one")
    _positive_float(config["bonus_scale"], name="bonus_scale")
    cg_target = _positive_float(
        config["cg_target_energy_error"], name="cg_target_energy_error"
    )
    if cg_target >= 1.0:
        raise ValueError("cg_target_energy_error must be below one")
    if _positive_int(config["cg_max_iterations"], name="cg_max_iterations") < dimension:
        raise ValueError("cg_max_iterations must be at least dimension")
    if config.get("policy_uses_gap") is not False:
        raise ValueError("the validation policy must not receive the controlled gap")


def _array_digest(*arrays: NDArray[np.generic]) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(canonical_json(list(contiguous.shape)).encode("ascii"))
        digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def _unit_vector(rng: np.random.Generator, dimension: int) -> FloatArray:
    for _ in range(16):
        candidate = rng.normal(size=dimension)
        norm = float(np.linalg.norm(candidate))
        if norm > 1e-12:
            return np.asarray(candidate / norm, dtype=np.float64)
    raise RuntimeError("failed to draw a nonzero deterministic direction")


def generate_stream(config: Mapping[str, Any], gap: float, seed: int) -> BanditStream:
    """Generate common random numbers with one unique, exactly controlled gap."""

    validate_study_config(config)
    dimension = int(config["dimension"])
    action_count = int(config["action_count"])
    rounds = int(config["rounds"])
    feature_bound = float(config["feature_bound"])
    parameter_norm = float(config["parameter_norm"])
    if gap not in tuple(float(value) for value in config["gaps"]):
        raise ValueError("gap is not a preregistered cell")

    rng = np.random.Generator(
        np.random.PCG64(derive_seed(seed, "gap-dependent-validation", "stream"))
    )
    signal = _unit_vector(rng, dimension)
    theta_star = np.asarray(parameter_norm * signal, dtype=np.float64)
    optimal_actions = np.asarray(
        rng.integers(0, action_count, size=rounds, dtype=np.int64),
        dtype=np.int64,
    )
    features = np.empty((rounds, action_count, dimension), dtype=np.float64)
    coefficient = gap / (2.0 * parameter_norm)
    nuisance_norm = math.sqrt(feature_bound * feature_bound - coefficient * coefficient)
    for round_index in range(rounds):
        for action in range(action_count):
            nuisance = _unit_vector(rng, dimension)
            nuisance -= signal * float(signal @ nuisance)
            norm = float(np.linalg.norm(nuisance))
            if norm <= 1e-12:
                basis = np.zeros(dimension, dtype=np.float64)
                basis[(round_index + action + 1) % dimension] = 1.0
                nuisance = basis - signal * float(signal @ basis)
                norm = float(np.linalg.norm(nuisance))
            nuisance /= norm
            signed_coefficient = (
                coefficient if action == optimal_actions[round_index] else -coefficient
            )
            features[round_index, action] = (
                signed_coefficient * signal + nuisance_norm * nuisance
            )
    noises = np.asarray(
        rng.normal(
            loc=0.0,
            scale=float(config["noise_std"]),
            size=(rounds, action_count),
        ),
        dtype=np.float64,
    )
    true_means = np.asarray(features @ theta_star, dtype=np.float64)
    stream_sha = _array_digest(
        features, noises, theta_star, optimal_actions, true_means
    )
    for array in (features, noises, theta_star, optimal_actions, true_means):
        array.setflags(write=False)
    return BanditStream(
        features=features,
        noises=noises,
        theta_star=theta_star,
        optimal_actions=optimal_actions,
        true_means=true_means,
        stream_sha256=stream_sha,
    )


def confidence_radius(config: Mapping[str, Any], round_index: int) -> float:
    observations = round_index
    dimension = int(config["dimension"])
    gamma_upper = dimension * math.log1p(
        observations
        * float(config["feature_bound"]) ** 2
        / (
            dimension
            * float(config["ridge"])
            * float(config["noise_std"]) ** 2
        )
    )
    return float(config["bonus_scale"]) * (
        math.sqrt(gamma_upper + 2.0 * math.log(1.0 / float(config["confidence_delta"])))
        + math.sqrt(float(config["ridge"])) * float(config["parameter_norm"])
    )


def _rank_truncated_widths(
    precision: FloatArray,
    candidates: FloatArray,
    *,
    ridge: float,
    rank: int,
) -> FloatArray:
    information = np.asarray(
        0.5 * (precision + precision.T) - ridge * np.eye(precision.shape[0]),
        dtype=np.float64,
    )
    eigenvalues, eigenvectors = np.linalg.eigh(information)
    order = np.argsort(eigenvalues)[::-1][:rank]
    retained_values = np.maximum(eigenvalues[order], 0.0)
    retained_vectors = eigenvectors[:, order]
    projected = candidates @ retained_vectors
    quadratic = np.sum(candidates * candidates, axis=1) / ridge
    quadratic -= np.sum(
        projected
        * projected
        * (retained_values / (ridge * (ridge + retained_values)))[None, :],
        axis=1,
    )
    return np.sqrt(np.maximum(quadratic, 0.0))


def _cg_widths(
    precision: FloatArray,
    candidates: FloatArray,
    *,
    target: float,
    maximum_iterations: int,
) -> tuple[FloatArray, IntArray, FloatArray, FloatArray, BoolArray]:
    condition_number = float(np.linalg.cond(precision))
    residual_target = target / math.sqrt(condition_number)
    exact_solutions = np.linalg.solve(precision, candidates.T).T
    widths = np.empty(candidates.shape[0], dtype=np.float64)
    iterations = np.empty(candidates.shape[0], dtype=np.int64)
    relative_residuals = np.empty(candidates.shape[0], dtype=np.float64)
    energy_errors = np.empty(candidates.shape[0], dtype=np.float64)
    width_sandwich = np.empty(candidates.shape[0], dtype=np.bool_)
    for action, (candidate, exact) in enumerate(
        zip(candidates, exact_solutions, strict=True)
    ):
        result = conjugate_gradient(
            precision,
            candidate,
            tolerance=residual_target,
            absolute_tolerance=0.0,
            max_iterations=maximum_iterations,
            raise_on_nonconvergence=False,
        )
        explicit_residual = candidate - precision @ result.solution
        rhs_norm = float(np.linalg.norm(candidate))
        relative_residual = float(np.linalg.norm(explicit_residual) / rhs_norm)
        difference = result.solution - exact
        denominator = float(exact @ precision @ exact)
        numerator = float(difference @ precision @ difference)
        energy_error = math.sqrt(max(numerator, 0.0) / denominator)
        if not result.converged or energy_error > target * (1.0 + 1e-8):
            raise RuntimeError("full CG failed its preregistered energy-error target")
        approximate_width_squared = max(float(candidate @ result.solution), 0.0)
        exact_width_squared = float(candidate @ exact)
        widths[action] = math.sqrt(approximate_width_squared)
        iterations[action] = int(result.iterations)
        relative_residuals[action] = relative_residual
        energy_errors[action] = energy_error
        width_sandwich[action] = bool(
            (1.0 - target) * exact_width_squared - 1e-12
            <= approximate_width_squared
            <= (1.0 + target) * exact_width_squared + 1e-12
        )
    return widths, iterations, relative_residuals, energy_errors, width_sandwich


def run_trajectory(
    config: Mapping[str, Any],
    gap: float,
    stream: BanditStream,
    *,
    method: str,
) -> Trajectory:
    validate_study_config(config)
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    rounds = int(config["rounds"])
    dimension = int(config["dimension"])
    action_count = int(config["action_count"])
    ridge = float(config["ridge"])
    variance = float(config["noise_std"]) ** 2
    feature_bound = float(config["feature_bound"])
    cg_target = float(config["cg_target_energy_error"])
    exact_operator_method = method in {"exact_full", "full_cg"}
    alpha = (
        math.sqrt((1.0 + cg_target) / (1.0 - cg_target))
        if method == "full_cg"
        else 1.0
    )

    precision = ridge * np.eye(dimension, dtype=np.float64)
    response = np.zeros(dimension, dtype=np.float64)
    theta_hat = np.zeros(dimension, dtype=np.float64)
    initial_logdet = dimension * math.log(ridge)
    cumulative_regret_value = 0.0
    cumulative_linearization_error_value = 0.0
    cumulative_h_squared = 0.0
    maximum_h = 0.0
    width_coefficient = variance + feature_bound * feature_bound / ridge

    cumulative_regret = np.empty(rounds, dtype=np.float64)
    gap_free_rhs = np.empty(rounds, dtype=np.float64)
    gap_dependent_rhs = np.empty(rounds, dtype=np.float64)
    gamma = np.empty(rounds, dtype=np.float64)
    beta_values = np.empty(rounds, dtype=np.float64)
    h_gap_values = np.empty(rounds, dtype=np.float64)
    instantaneous_regret = np.empty(rounds, dtype=np.float64)
    realized_selected_gap = np.empty(rounds, dtype=np.float64)
    minimum_candidate_gap = np.empty(rounds, dtype=np.float64)
    maximum_linearization_error = np.empty(rounds, dtype=np.float64)
    cumulative_linearization_error = np.empty(rounds, dtype=np.float64)
    action_disagreement = np.empty(rounds, dtype=np.bool_)
    selected_actions = np.empty(rounds, dtype=np.int64)
    reference_actions = np.empty(rounds, dtype=np.int64)
    optimal_actions = np.empty(rounds, dtype=np.int64)
    confidence_event = np.empty(rounds, dtype=np.bool_)
    policy_optimism = np.empty(rounds, dtype=np.bool_)
    controlled_gap_premise = np.empty(rounds, dtype=np.bool_)
    linearization_premise = np.empty(rounds, dtype=np.bool_)
    cg_certificate = np.ones(rounds, dtype=np.bool_)
    cg_width_sandwich = np.ones(rounds, dtype=np.bool_)
    gap_corollary_applicable = np.empty(rounds, dtype=np.bool_)
    gap_free_bound_holds = np.empty(rounds, dtype=np.bool_)
    gap_dependent_bound_holds = np.empty(rounds, dtype=np.bool_)
    cg_iterations = np.zeros((rounds, action_count), dtype=np.int64)
    cg_relative_residual = np.zeros((rounds, action_count), dtype=np.float64)
    cg_energy_error = np.zeros((rounds, action_count), dtype=np.float64)

    for round_index in range(rounds):
        candidates = stream.features[round_index]
        true_means = stream.true_means[round_index]
        predicted_means = candidates @ theta_hat
        exact_solutions = np.linalg.solve(precision, candidates.T).T
        exact_widths = np.sqrt(
            np.maximum(np.einsum("ij,ij->i", candidates, exact_solutions), 0.0)
        )
        beta = confidence_radius(config, round_index)
        reference_scores = predicted_means + beta * exact_widths
        reference_action = int(np.argmax(reference_scores))

        if method == "exact_full":
            widths = exact_widths
        elif method == "full_cg":
            (
                widths,
                cg_iterations[round_index],
                cg_relative_residual[round_index],
                cg_energy_error[round_index],
                action_width_sandwich,
            ) = _cg_widths(
                precision,
                candidates,
                target=cg_target,
                maximum_iterations=int(config["cg_max_iterations"]),
            )
            widths = widths / math.sqrt(1.0 - cg_target)
            cg_certificate[round_index] = bool(
                np.max(cg_energy_error[round_index]) <= cg_target * (1.0 + 1e-8)
            )
            cg_width_sandwich[round_index] = bool(np.all(action_width_sandwich))
        elif method == "rank_truncation":
            widths = _rank_truncated_widths(
                precision,
                candidates,
                ridge=ridge,
                rank=int(config["target_rank"]),
            )
        elif method == "diagonal":
            widths = np.sqrt(
                np.sum(candidates * candidates / np.diag(precision)[None, :], axis=1)
            )
        else:
            widths = np.zeros(action_count, dtype=np.float64)

        scores = predicted_means if method == "greedy" else predicted_means + beta * widths
        selected_action = int(np.argmax(scores))
        optimal_action = int(np.argmax(true_means))
        sorted_means = np.sort(true_means)
        round_minimum_gap = float(sorted_means[-1] - sorted_means[-2])
        regret = float(true_means[optimal_action] - true_means[selected_action])
        cumulative_regret_value += regret

        linearized_means = predicted_means + candidates @ (
            stream.theta_star - theta_hat
        )
        linearization_error = float(np.max(np.abs(true_means - linearized_means)))
        cumulative_linearization_error_value += linearization_error
        round_confidence = bool(
            np.all(np.abs(true_means - predicted_means) <= beta * exact_widths + 1e-12)
        )
        round_policy_optimism = bool(np.all(true_means <= scores + 1e-12))
        unique_optimal = int(np.count_nonzero(np.isclose(true_means, true_means.max()))) == 1
        round_gap_premise = bool(
            unique_optimal and round_minimum_gap + 1e-12 >= gap and gap > 0.0
        )
        round_linearization_premise = bool(linearization_error <= gap / 4.0 + 1e-12)

        played = candidates[selected_action]
        reward = float(
            true_means[selected_action]
            + stream.noises[round_index, selected_action]
        )
        precision += np.outer(played, played) / variance
        response += played * reward / variance
        theta_hat = np.linalg.solve(precision, response)
        sign, logdet = np.linalg.slogdet(precision)
        if sign <= 0.0:
            raise ArithmeticError("precision matrix lost positive definiteness")
        gamma_value = float(logdet - initial_logdet)
        h_value = alpha * beta
        cumulative_h_squared += h_value * h_value
        maximum_h = max(maximum_h, h_value)
        free_rhs = 2.0 * math.sqrt(
            width_coefficient * gamma_value * cumulative_h_squared
        ) + 2.0 * cumulative_linearization_error_value
        dependent_rhs = (
            16.0 * maximum_h * maximum_h * width_coefficient * gamma_value / gap
        )
        round_applicable = bool(
            exact_operator_method
            and round_gap_premise
            and round_linearization_premise
            and round_confidence
            and round_policy_optimism
            and cg_certificate[round_index]
            and cg_width_sandwich[round_index]
        )

        cumulative_regret[round_index] = cumulative_regret_value
        gap_free_rhs[round_index] = free_rhs
        gap_dependent_rhs[round_index] = dependent_rhs
        gamma[round_index] = gamma_value
        beta_values[round_index] = beta
        h_gap_values[round_index] = h_value
        instantaneous_regret[round_index] = regret
        realized_selected_gap[round_index] = regret
        minimum_candidate_gap[round_index] = round_minimum_gap
        maximum_linearization_error[round_index] = linearization_error
        cumulative_linearization_error[round_index] = (
            cumulative_linearization_error_value
        )
        action_disagreement[round_index] = selected_action != reference_action
        selected_actions[round_index] = selected_action
        reference_actions[round_index] = reference_action
        optimal_actions[round_index] = optimal_action
        confidence_event[round_index] = round_confidence
        policy_optimism[round_index] = round_policy_optimism
        controlled_gap_premise[round_index] = round_gap_premise
        linearization_premise[round_index] = round_linearization_premise
        gap_corollary_applicable[round_index] = round_applicable
        gap_free_bound_holds[round_index] = cumulative_regret_value <= free_rhs + 1e-10
        gap_dependent_bound_holds[round_index] = (
            cumulative_regret_value <= dependent_rhs + 1e-10
        )

    arrays: dict[str, NDArray[np.generic]] = {
        "round": np.arange(1, rounds + 1, dtype=np.int64),
        "cumulative_pseudo_regret": cumulative_regret,
        "instantaneous_pseudo_regret": instantaneous_regret,
        "realized_selected_gap": realized_selected_gap,
        "minimum_candidate_gap": minimum_candidate_gap,
        "gap_free_rhs": gap_free_rhs,
        "gap_dependent_rhs": gap_dependent_rhs,
        "gamma": gamma,
        "beta": beta_values,
        "H_gap": h_gap_values,
        "maximum_linearization_error": maximum_linearization_error,
        "cumulative_linearization_error": cumulative_linearization_error,
        "selected_actions": selected_actions,
        "reference_exact_actions": reference_actions,
        "optimal_actions": optimal_actions,
        "action_disagreement": action_disagreement,
        "confidence_event": confidence_event,
        "policy_optimism": policy_optimism,
        "controlled_gap_premise": controlled_gap_premise,
        "linearization_error_premise": linearization_premise,
        "cg_certificate": cg_certificate,
        "cg_width_sandwich": cg_width_sandwich,
        "gap_corollary_applicable": gap_corollary_applicable,
        "gap_free_bound_holds": gap_free_bound_holds,
        "gap_dependent_bound_holds": gap_dependent_bound_holds,
        "cg_iterations": cg_iterations,
        "cg_relative_residual": cg_relative_residual,
        "cg_energy_error": cg_energy_error,
    }
    premise_checks = {
        "policy_gap_blind": config.get("policy_uses_gap") is False,
        "controlled_positive_gap": bool(np.all(controlled_gap_premise)),
        "linearization_error_le_gap_quarter": bool(np.all(linearization_premise)),
        "feature_bound": bool(
            np.max(np.linalg.norm(stream.features, axis=2)) <= feature_bound + 1e-12
        ),
        "parameter_bound": bool(
            np.linalg.norm(stream.theta_star)
            <= float(config["parameter_norm"]) + 1e-12
        ),
        "simultaneous_confidence_event_observed": bool(np.all(confidence_event)),
        "policy_optimism_observed": bool(np.all(policy_optimism)),
        "exact_current_operator": exact_operator_method,
        "cg_energy_error_certificate": bool(np.all(cg_certificate)),
        "cg_width_sandwich_certificate": bool(np.all(cg_width_sandwich)),
        "gap_corollary_applicable_all_rounds": bool(
            np.all(gap_corollary_applicable)
        ),
        "gap_free_rhs_dominates_regret": bool(np.all(gap_free_bound_holds)),
        "gap_dependent_rhs_dominates_regret": bool(
            np.all(gap_dependent_bound_holds)
        ),
    }
    horizon_metrics = [
        {
            "horizon": int(horizon),
            "cumulative_pseudo_regret": float(cumulative_regret[int(horizon) - 1]),
            "gap_free_rhs": float(gap_free_rhs[int(horizon) - 1]),
            "gap_dependent_rhs": float(gap_dependent_rhs[int(horizon) - 1]),
            "action_disagreement_rate": float(
                np.mean(action_disagreement[: int(horizon)])
            ),
            "maximum_linearization_error": float(
                np.max(maximum_linearization_error[: int(horizon)])
            ),
            "cumulative_linearization_error": float(
                cumulative_linearization_error[int(horizon) - 1]
            ),
        }
        for horizon in config["horizons"]
    ]
    summary = {
        "schema_version": 1,
        "experiment": "gap_dependent_validation",
        "method": method,
        "controlled_gap": gap,
        "rounds": rounds,
        "terminal_pseudo_regret": float(cumulative_regret[-1]),
        "terminal_gap_free_rhs": float(gap_free_rhs[-1]),
        "terminal_gap_dependent_rhs": float(gap_dependent_rhs[-1]),
        "terminal_gamma": float(gamma[-1]),
        "minimum_realized_candidate_gap": float(np.min(minimum_candidate_gap)),
        "maximum_linearization_error": float(
            np.max(maximum_linearization_error)
        ),
        "terminal_cumulative_linearization_error": float(
            cumulative_linearization_error[-1]
        ),
        "action_disagreement_rate": float(np.mean(action_disagreement)),
        "suboptimal_action_rate": float(np.mean(instantaneous_regret > 0.0)),
        "maximum_cg_energy_error": float(np.max(cg_energy_error)),
        "maximum_cg_relative_residual": float(np.max(cg_relative_residual)),
        "mean_cg_iterations": float(np.mean(cg_iterations)),
        "selected_action_sha256": _array_digest(selected_actions),
        "premise_checks": premise_checks,
        "horizon_metrics": horizon_metrics,
        "rhs_semantics": (
            "post-hoc evaluation of the exact-current gap-free and gap-dependent "
            "right-hand sides; theorem applicability requires the recorded premises"
        ),
        "numerical_semantics": "float64 audit; no verified interval enclosure",
    }
    return Trajectory(arrays=arrays, summary=summary)


def _gap_token(gap: float) -> str:
    return f"gap-{gap:.8g}".replace(".", "p")


def _run_directory(
    output_root: Path,
    profile: str,
    seed_set: str,
    gap: float,
    method: str,
    seed: int,
) -> Path:
    return (
        output_root
        / profile
        / seed_set
        / _gap_token(gap)
        / method
        / f"seed-{seed}"
    )


def _save_trajectory(
    destination: Path,
    trajectory: Trajectory,
    *,
    config: Mapping[str, Any],
    profile: str,
    seed_set: str,
    seed: int,
    gap: float,
    method: str,
    stream: BanditStream,
    timestamp_utc: str,
    provenance: Mapping[str, Any],
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
        "experiment": "gap_dependent_validation",
        "profile": profile,
        "seed_set": seed_set,
        "seed": seed,
        "controlled_gap": gap,
        "method": method,
        "config_digest": config_digest(config),
        "config": dict(config),
        "stream_sha256": stream.stream_sha256,
        "rounds_sha256": sha256_file(rounds_path),
        "summary_sha256": sha256_file(summary_path),
        "rng": "numpy.random.Generator(numpy.random.PCG64)",
        "timestamp_utc": timestamp_utc,
        "provenance": dict(provenance),
        "deterministic_scientific_payload": True,
        "evidence_scope": (
            SMOKE_EVIDENCE_SCOPE
            if profile == "smoke"
            else "full evaluation; eligible for paper reporting after artifact validation"
        ),
    }
    manifest_path, _ = write_json_artifact(destination / "manifest.json", manifest)
    return rounds_path, summary_path, manifest_path


def _execute_task(
    task: tuple[
        dict[str, Any],
        str,
        str,
        str,
        int,
        float,
        str,
        dict[str, Any],
        bool,
    ]
) -> list[str]:
    (
        config,
        profile,
        seed_set,
        output_root_text,
        seed,
        gap,
        timestamp_utc,
        provenance,
        overwrite,
    ) = task
    seed_everything(seed, include_optional=False)
    stream = generate_stream(config, gap, seed)
    paths: list[str] = []
    for method in METHODS:
        trajectory = run_trajectory(config, gap, stream, method=method)
        destination = _run_directory(
            Path(output_root_text), profile, seed_set, gap, method, seed
        )
        saved = _save_trajectory(
            destination,
            trajectory,
            config=config,
            profile=profile,
            seed_set=seed_set,
            seed=seed,
            gap=gap,
            method=method,
            stream=stream,
            timestamp_utc=timestamp_utc,
            provenance=provenance,
            overwrite=overwrite,
        )
        paths.extend(path.as_posix() for path in saved)
    return paths


def run_grid(
    config: dict[str, Any],
    *,
    profile: str,
    seed_set: str,
    output_root: Path,
    workers: int = 1,
    overwrite: bool = False,
) -> dict[str, Any]:
    validate_study_config(config)
    if seed_set not in {"tuning", "evaluation"}:
        raise ValueError("seed_set must be tuning or evaluation")
    if workers <= 0:
        raise ValueError("workers must be positive")
    seeds = get_seed_set(config, seed_set)
    gaps = tuple(float(value) for value in config["gaps"])
    repository = Path(__file__).resolve().parents[1]
    provenance = collect_run_metadata(
        repository=repository,
        packages=tuple(config.get("provenance", {}).get("packages", ())),
    )
    source_paths = (
        Path("experiments/run_gap_dependent_validation.py"),
        Path("experiments/artifact_utils.py"),
        Path("experiments/config.py"),
        Path("experiments/curvature_operators.py"),
        Path("experiments/logging_utils.py"),
        Path("experiments/configs/gap_dependent_validation.yaml"),
        Path("scripts/reproduce_fig_gap_dependent_validation.sh"),
    )
    provenance["source_artifact_hashes"] = {
        path.as_posix(): sha256_file(repository / path) for path in source_paths
    }
    timestamp_utc = (
        dt.datetime.now(dt.timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
    tasks = [
        (
            dict(config),
            profile,
            seed_set,
            output_root.as_posix(),
            seed,
            gap,
            timestamp_utc,
            provenance,
            overwrite,
        )
        for gap in gaps
        for seed in seeds
    ]
    if workers == 1:
        task_paths = [_execute_task(task) for task in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            task_paths = list(executor.map(_execute_task, tasks))

    phase_root = output_root / profile / seed_set
    files = sorted(Path(path) for paths in task_paths for path in paths)
    inputs = [
        {
            "path": path.relative_to(phase_root).as_posix(),
            "sha256": sha256_file(path),
        }
        for path in files
    ]
    manifest = {
        "schema_version": 1,
        "experiment": "gap_dependent_validation",
        "profile": profile,
        "seed_set": seed_set,
        "config_digest": config_digest(config),
        "seeds": list(seeds),
        "gaps": list(gaps),
        "methods": list(METHODS),
        "run_count": len(seeds) * len(gaps) * len(METHODS),
        "input_set_sha256": input_set_sha256(inputs),
        "inputs": inputs,
        "timestamp_utc": timestamp_utc,
        "provenance": provenance,
        "deterministic_scientific_payload": True,
        "evidence_scope": (
            SMOKE_EVIDENCE_SCOPE
            if profile == "smoke"
            else "full evaluation; eligible for paper reporting after artifact validation"
        ),
    }
    manifest_path, _ = write_json_artifact(phase_root / "manifest.json", manifest)
    return {
        "manifest": manifest_path.as_posix(),
        "profile": profile,
        "seed_set": seed_set,
        "run_count": manifest["run_count"],
        "workers": workers,
        "input_set_sha256": manifest["input_set_sha256"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument(
        "--seed-set", choices=("tuning", "evaluation"), default="evaluation"
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = load_config(args.config, profile=args.profile)
    result = run_grid(
        config,
        profile=args.profile,
        seed_set=args.seed_set,
        output_root=args.output_root,
        workers=args.workers,
        overwrite=args.overwrite,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BanditStream",
    "DEFAULT_CONFIG",
    "METHODS",
    "SMOKE_EVIDENCE_SCOPE",
    "Trajectory",
    "confidence_radius",
    "generate_stream",
    "run_grid",
    "run_trajectory",
    "validate_study_config",
]
