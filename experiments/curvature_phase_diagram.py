"""Preregistered bounded-linear curvature-mechanism phase diagram.

Every online method executes its own adaptive policy.  Common-trajectory
diagnostics replay the exact-full trajectory and never report causal regret.
The configured evaluation cells and seeds are used verbatim: this module has no
tuning phase and no code path that selects cells where any method wins.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .aggregate_results import student_t_interval
from .config import load_config as load_repository_config
from .logging_utils import canonical_json, collect_run_metadata, derive_seed


FloatArray = NDArray[np.float64]
SCHEMA_VERSION = 1
METHODS = (
    "exact_full",
    "full_cg",
    "diagonal",
    "block_diagonal",
    "low_rank_lanczos",
    "unrescaled_window",
    "stale_refresh",
)
OPTIONAL_METHODS = ("low_rank_plus_diagonal",)
SUPPORTED_METHODS = METHODS + OPTIONAL_METHODS
REQUIRED_KNOBS = (
    "active_spectrum_condition_number",
    "rotation_degrees",
    "action_gap",
    "nuisance_strength",
    "effective_rank",
    "damping",
    "representation_drift",
)
ROUND_MEAN_METRICS = (
    "width_ratio_cv",
    "width_spearman",
    "width_kendall",
    "normalized_margin_distortion_abs",
    "ucb_score_disagreement",
    "reference_leading_alignment",
    "reference_discarded_alignment",
    "operator_leading_alignment",
    "operator_discarded_alignment",
    "candidate_full_leading_projection_mean",
    "candidate_full_discarded_projection_mean",
    "candidate_full_leading_projection_reference_top",
    "candidate_full_discarded_projection_reference_top",
    "candidate_operator_retained_projection_mean",
    "candidate_operator_discarded_projection_mean",
    "candidate_operator_retained_projection_reference_top",
    "candidate_operator_discarded_projection_reference_top",
    "global_transfer_alg_over_full",
    "global_transfer_full_over_alg",
    "action_transfer_full_width_over_alg",
    "action_transfer_alg_width_over_full",
    "full_effective_rank",
    "full_condition",
    "algorithmic_condition",
    "cg_iterations_mean",
)


@dataclass(frozen=True)
class Cell:
    cell_id: str
    active_spectrum_condition_number: float
    rotation_degrees: float
    action_gap: float
    nuisance_strength: float
    effective_rank: int
    damping: float
    representation_drift: float
    representation_drift_status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "active_spectrum_condition_number": self.active_spectrum_condition_number,
            "rotation_degrees": self.rotation_degrees,
            "action_gap": self.action_gap,
            "nuisance_strength": self.nuisance_strength,
            "effective_rank": self.effective_rank,
            "damping": self.damping,
            "representation_drift": self.representation_drift,
            "representation_drift_status": self.representation_drift_status,
        }


@dataclass(frozen=True)
class Environment:
    features: FloatArray
    means: FloatArray
    rewards: FloatArray
    theta_star: FloatArray
    decision_direction: FloatArray
    covariance: FloatArray
    covariance_eigenvalues: FloatArray
    feature_bound: float
    realized_feature_max: float


@dataclass
class PolicyResult:
    method: str
    actions: list[int]
    selected_features: list[FloatArray]
    selected_rewards: list[float]
    rounds: list[dict[str, Any]]
    summary: dict[str, Any]


class ConfigError(ValueError):
    """Invalid phase-diagram configuration."""


def _strict_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"cannot load strict-JSON config {source}: {error}") from error
    if not isinstance(value, dict):
        raise ConfigError("config must be an object")
    return value


def _finite_float(value: Any, *, name: str, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise ConfigError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        qualifier = "positive " if positive else ""
        raise ConfigError(f"{name} must be a finite {qualifier}number")
    return result


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{name} must be a positive integer")
    return int(value)


def validate_config(config: Mapping[str, Any], *, require_30_seeds: bool = True) -> None:
    if config.get("schema_version") != SCHEMA_VERSION:
        raise ConfigError(f"schema_version must be {SCHEMA_VERSION}")
    study = config.get("study")
    if not isinstance(study, Mapping):
        raise ConfigError("study must be an object")
    if study.get("phase") != "evaluation" or study.get("tuning_enabled") is not False:
        raise ConfigError("study must be evaluation-only with tuning_enabled=false")
    if study.get("cell_selection") != "none_preregistered_all_cells":
        raise ConfigError("cell_selection must forbid evaluation-cell selection")
    seeds = study.get("evaluation_seeds")
    if not isinstance(seeds, Sequence) or isinstance(seeds, (str, bytes)):
        raise ConfigError("evaluation_seeds must be a list")
    if any(isinstance(seed, bool) or not isinstance(seed, int) or seed < 0 for seed in seeds):
        raise ConfigError("evaluation_seeds must contain nonnegative integers")
    if len(set(seeds)) != len(seeds):
        raise ConfigError("evaluation_seeds contain duplicates")
    if require_30_seeds and len(seeds) < 30:
        raise ConfigError("at least 30 evaluation seeds are required")

    environment = config.get("environment")
    if not isinstance(environment, Mapping):
        raise ConfigError("environment must be an object")
    dimension = _positive_int(environment.get("dimension"), name="environment.dimension")
    _positive_int(environment.get("action_count"), name="environment.action_count")
    _positive_int(environment.get("rounds"), name="environment.rounds")
    _finite_float(environment.get("noise_std"), name="environment.noise_std", positive=True)

    methods = config.get("methods")
    if not isinstance(methods, Sequence) or isinstance(methods, (str, bytes)):
        raise ConfigError("methods must be a list")
    if tuple(methods) not in {METHODS, SUPPORTED_METHODS}:
        raise ConfigError(f"methods must be exactly {METHODS} or {SUPPORTED_METHODS}")

    cells = config.get("preregistered_cells")
    if not isinstance(cells, Sequence) or isinstance(cells, (str, bytes)) or not cells:
        raise ConfigError("preregistered_cells must be a nonempty list")
    ids: set[str] = set()
    for index, raw in enumerate(cells):
        if not isinstance(raw, Mapping):
            raise ConfigError(f"cell {index} must be an object")
        if set(REQUIRED_KNOBS) - set(raw):
            raise ConfigError(f"cell {index} is missing required knobs")
        cell_id = raw.get("cell_id")
        if not isinstance(cell_id, str) or not cell_id:
            raise ConfigError(f"cell {index} has invalid cell_id")
        if cell_id in ids:
            raise ConfigError(f"duplicate cell_id {cell_id}")
        ids.add(cell_id)
        condition = _finite_float(
            raw["active_spectrum_condition_number"],
            name=f"{cell_id}.active_spectrum_condition_number",
            positive=True,
        )
        if condition < 1.0:
            raise ConfigError("covariance condition must be at least one")
        rank = _positive_int(raw["effective_rank"], name=f"{cell_id}.effective_rank")
        if rank > dimension:
            raise ConfigError(f"{cell_id}.effective_rank exceeds dimension")
        _finite_float(raw["rotation_degrees"], name=f"{cell_id}.rotation_degrees")
        _finite_float(raw["action_gap"], name=f"{cell_id}.action_gap", positive=True)
        nuisance = _finite_float(
            raw["nuisance_strength"], name=f"{cell_id}.nuisance_strength"
        )
        if nuisance < 0.0:
            raise ConfigError("nuisance strength must be nonnegative")
        _finite_float(raw["damping"], name=f"{cell_id}.damping", positive=True)
        drift = _finite_float(
            raw["representation_drift"], name=f"{cell_id}.representation_drift"
        )
        if drift != 0.0 or raw.get("representation_drift_status") != "not_run_fixed_zero":
            raise ConfigError("bounded-linear representation drift must be zero and marked not run")


def load_config(path: str | Path, profile: str = "full") -> dict[str, Any]:
    config = load_repository_config(path, profile)
    validate_config(config)
    if list(config["study"]["evaluation_seeds"]) != list(
        config["seed_sets"]["evaluation"]
    ):
        raise ConfigError("study evaluation seeds must equal seed_sets.evaluation")
    return config


def cells_from_config(config: Mapping[str, Any]) -> tuple[Cell, ...]:
    validate_config(config, require_30_seeds=False)
    result: list[Cell] = []
    for raw in config["preregistered_cells"]:
        result.append(
            Cell(
                cell_id=str(raw["cell_id"]),
                active_spectrum_condition_number=float(
                    raw["active_spectrum_condition_number"]
                ),
                rotation_degrees=float(raw["rotation_degrees"]),
                action_gap=float(raw["action_gap"]),
                nuisance_strength=float(raw["nuisance_strength"]),
                effective_rank=int(raw["effective_rank"]),
                damping=float(raw["damping"]),
                representation_drift=float(raw["representation_drift"]),
                representation_drift_status=str(raw["representation_drift_status"]),
            )
        )
    return tuple(result)


def _rotation(dimension: int, degrees: float) -> FloatArray:
    matrix = np.eye(dimension, dtype=np.float64)
    angle = math.radians(degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    matrix[:2, :2] = np.array([[cosine, -sine], [sine, cosine]])
    return matrix


def generate_environment(
    config: Mapping[str, Any], cell: Cell, seed: int
) -> Environment:
    env_config = config["environment"]
    rounds = int(env_config["rounds"])
    action_count = int(env_config["action_count"])
    dimension = int(env_config["dimension"])
    noise_std = float(env_config["noise_std"])
    rng = np.random.default_rng(derive_seed(seed, "phase_diagram_environment", cell.cell_id))

    spectrum = np.zeros(dimension, dtype=np.float64)
    if cell.effective_rank == 1:
        spectrum[0] = 1.0
    else:
        spectrum[: cell.effective_rank] = np.geomspace(
            1.0,
            1.0 / cell.active_spectrum_condition_number,
            cell.effective_rank,
        )
    spectrum /= float(np.sum(spectrum))
    rotation = _rotation(dimension, cell.rotation_degrees)
    covariance = rotation @ np.diag(spectrum) @ rotation.T
    square_root = rotation @ np.diag(np.sqrt(spectrum)) @ rotation.T
    signs = rng.choice(np.array([-1.0, 1.0]), size=(rounds, dimension))
    contexts = cell.nuisance_strength * (signs @ square_root.T)

    decision = np.zeros(dimension, dtype=np.float64)
    decision[0] = 1.0
    offsets = np.stack(
        [-float(action) * cell.action_gap * decision for action in range(action_count)]
    )
    features = contexts[:, None, :] + offsets[None, :, :]
    theta_star = decision.copy()
    means = np.einsum("tad,d->ta", features, theta_star)
    rewards = means + rng.normal(0.0, noise_std, size=means.shape)
    maximum_covariance_eigenvalue = float(np.max(spectrum))
    feature_bound = (
        cell.nuisance_strength
        * math.sqrt(dimension)
        * math.sqrt(maximum_covariance_eigenvalue)
        + (action_count - 1) * cell.action_gap
    )
    realized_feature_max = float(np.max(np.linalg.norm(features, axis=2)))
    if realized_feature_max > feature_bound + 1e-12:
        raise AssertionError("analytic feature bound failed")
    for array in (features, means, rewards, theta_star, decision, covariance, spectrum):
        array.setflags(write=False)
    return Environment(
        features=features,
        means=means,
        rewards=rewards,
        theta_star=theta_star,
        decision_direction=decision,
        covariance=covariance,
        covariance_eigenvalues=spectrum,
        feature_bound=feature_bound,
        realized_feature_max=realized_feature_max,
    )


def _gram(
    history: Sequence[FloatArray],
    *,
    dimension: int,
    damping: float,
    noise_variance: float,
) -> FloatArray:
    matrix = damping * np.eye(dimension, dtype=np.float64)
    if history:
        features = np.stack(history)
        matrix += features.T @ features / noise_variance
    return np.asarray(0.5 * (matrix + matrix.T), dtype=np.float64)


def _ridge_estimate(
    history: Sequence[FloatArray],
    rewards: Sequence[float],
    *,
    dimension: int,
    damping: float,
    noise_variance: float,
) -> tuple[FloatArray, FloatArray]:
    matrix = _gram(
        history, dimension=dimension, damping=damping, noise_variance=noise_variance
    )
    if not history:
        return np.zeros(dimension, dtype=np.float64), matrix
    features = np.stack(history)
    rhs = features.T @ np.asarray(rewards, dtype=np.float64) / noise_variance
    return np.linalg.solve(matrix, rhs), matrix


def _stable_child_seed(seed: int, *namespace: object) -> int:
    return derive_seed(seed, "curvature_phase_diagram", *namespace)


def _lanczos_surrogate(
    matrix: FloatArray, *, damping: float, rank: int, seed: int
) -> tuple[FloatArray, FloatArray]:
    dimension = matrix.shape[0]
    rng = np.random.default_rng(seed)
    current = rng.normal(size=dimension)
    current /= np.linalg.norm(current)
    previous = np.zeros(dimension, dtype=np.float64)
    previous_beta = 0.0
    basis: list[FloatArray] = []
    tolerance = 128.0 * np.finfo(np.float64).eps * max(1.0, np.linalg.norm(matrix, 2))
    for _ in range(min(rank, dimension)):
        basis.append(current.copy())
        residual = matrix @ current - previous_beta * previous
        alpha = float(current @ residual)
        residual -= alpha * current
        for _pass in range(2):
            for vector in basis:
                residual -= float(vector @ residual) * vector
        beta = float(np.linalg.norm(residual))
        if beta <= tolerance:
            break
        previous, current, previous_beta = current, residual / beta, beta
    krylov, _ = np.linalg.qr(np.column_stack(basis), mode="reduced")
    compressed = 0.5 * (krylov.T @ matrix @ krylov + krylov.T @ matrix.T @ krylov)
    values, vectors = np.linalg.eigh(compressed)
    order = np.argsort(values)[::-1]
    values = values[order]
    ritz = krylov @ vectors[:, order]
    increments = np.maximum(values - damping, 0.0)
    surrogate = damping * np.eye(dimension) + (ritz * increments) @ ritz.T
    retained = ritz[:, increments > tolerance]
    return np.asarray(0.5 * (surrogate + surrogate.T), dtype=np.float64), retained


class OperatorBuilder:
    def __init__(
        self, method: str, config: Mapping[str, Any], cell: Cell, seed: int
    ) -> None:
        if method not in SUPPORTED_METHODS:
            raise ValueError(f"unknown method {method}")
        self.method = method
        self.config = config
        self.cell = cell
        self.seed = seed
        self._stale: FloatArray | None = None

    def build(
        self,
        round_index: int,
        history: Sequence[FloatArray],
        reference: FloatArray,
    ) -> tuple[FloatArray, dict[str, Any]]:
        options = self.config["method_options"]
        dimension = reference.shape[0]
        variance = float(self.config["environment"]["noise_std"]) ** 2
        if self.method in {"exact_full", "full_cg"}:
            return reference.copy(), {"retained_basis": None}
        if self.method == "diagonal":
            return np.diag(np.diag(reference)), {"retained_basis": None}
        if self.method == "block_diagonal":
            split = min(int(options["block_size"]), dimension - 1)
            result = np.zeros_like(reference)
            result[:split, :split] = reference[:split, :split]
            result[split:, split:] = reference[split:, split:]
            return result, {"retained_basis": None}
        if self.method == "low_rank_lanczos":
            rank = min(int(options["lanczos_rank"]), dimension)
            return_value, basis = _lanczos_surrogate(
                reference,
                damping=self.cell.damping,
                rank=rank,
                seed=_stable_child_seed(
                    self.seed, self.cell.cell_id, self.method, round_index
                ),
            )
            return return_value, {"retained_basis": basis}
        if self.method == "low_rank_plus_diagonal":
            rank = min(int(options["lofi_rank"]), dimension)
            increment = 0.5 * (
                reference + reference.T
            ) - self.cell.damping * np.eye(dimension)
            values, vectors = np.linalg.eigh(increment)
            order = np.argsort(values)[::-1]
            values = np.maximum(values[order][:rank], 0.0)
            basis = vectors[:, order[:rank]]
            low_rank = (basis * values) @ basis.T
            residual_diagonal = np.maximum(
                np.diag(increment - low_rank), 0.0
            )
            surrogate = (
                self.cell.damping * np.eye(dimension)
                + low_rank
                + np.diag(residual_diagonal)
            )
            return surrogate, {"retained_basis": basis}
        if self.method == "unrescaled_window":
            size = int(options["window_size"])
            return (
                _gram(
                    history[-size:],
                    dimension=dimension,
                    damping=self.cell.damping,
                    noise_variance=variance,
                ),
                {"retained_basis": None},
            )
        if self.method == "stale_refresh":
            period = int(options["stale_period"])
            if self._stale is None or round_index % period == 0:
                self._stale = reference.copy()
            return self._stale.copy(), {"retained_basis": None}
        raise AssertionError("unreachable operator method")


def _dense_widths(matrix: FloatArray, features: FloatArray) -> FloatArray:
    solutions = np.linalg.solve(matrix, features.T)
    widths = np.einsum("ad,da->a", features, solutions)
    return np.maximum(np.asarray(widths, dtype=np.float64), 0.0)


def _cg_solve(
    matrix: FloatArray, rhs: FloatArray, *, tolerance: float, max_iterations: int
) -> tuple[FloatArray, int, float]:
    solution = np.zeros_like(rhs)
    residual = rhs.copy()
    direction = residual.copy()
    rhs_norm = float(np.linalg.norm(rhs))
    if rhs_norm == 0.0:
        return solution, 0, 0.0
    residual_squared = float(residual @ residual)
    completed = 0
    for completed in range(1, max_iterations + 1):
        applied = matrix @ direction
        denominator = float(direction @ applied)
        if denominator <= 0.0:
            raise ArithmeticError("CG encountered a nonpositive denominator")
        step = residual_squared / denominator
        solution += step * direction
        residual -= step * applied
        next_squared = float(residual @ residual)
        relative = math.sqrt(max(next_squared, 0.0)) / rhs_norm
        if relative <= tolerance:
            residual_squared = next_squared
            break
        direction = residual + (next_squared / residual_squared) * direction
        residual_squared = next_squared
    explicit_residual = float(np.linalg.norm(rhs - matrix @ solution) / rhs_norm)
    if explicit_residual > tolerance * (1.0 + 1e-6) + 1e-14:
        raise ArithmeticError(
            "CG did not meet the explicit original-system residual tolerance: "
            f"{explicit_residual} > {tolerance}"
        )
    return solution, completed, explicit_residual


def _cg_widths(
    matrix: FloatArray,
    features: FloatArray,
    *,
    tolerance: float,
    max_iterations: int,
) -> tuple[FloatArray, list[int], list[float]]:
    widths: list[float] = []
    iterations: list[int] = []
    residuals: list[float] = []
    for feature in features:
        solution, count, residual = _cg_solve(
            matrix, feature, tolerance=tolerance, max_iterations=max_iterations
        )
        widths.append(max(float(feature @ solution), 0.0))
        iterations.append(count)
        residuals.append(residual)
    return np.asarray(widths), iterations, residuals


def _invsqrt(matrix: FloatArray) -> FloatArray:
    values, vectors = np.linalg.eigh(0.5 * (matrix + matrix.T))
    if np.any(values <= 0.0):
        raise ArithmeticError("matrix must be SPD")
    return (vectors * (1.0 / np.sqrt(values))) @ vectors.T


def _generalized_max(left: FloatArray, right: FloatArray) -> float:
    root = _invsqrt(right)
    transformed = root @ left @ root
    return float(np.max(np.linalg.eigvalsh(0.5 * (transformed + transformed.T))))


def _average_ranks(values: FloatArray) -> FloatArray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.size, dtype=np.float64)
    start = 0
    while start < values.size:
        stop = start + 1
        while stop < values.size and values[order[stop]] == values[order[start]]:
            stop += 1
        rank = 0.5 * (start + stop - 1)
        ranks[order[start:stop]] = rank
        start = stop
    return ranks


def _spearman(first: FloatArray, second: FloatArray) -> float:
    first_rank, second_rank = _average_ranks(first), _average_ranks(second)
    first_centered = first_rank - np.mean(first_rank)
    second_centered = second_rank - np.mean(second_rank)
    denominator = float(np.linalg.norm(first_centered) * np.linalg.norm(second_centered))
    if denominator == 0.0:
        return 1.0 if np.allclose(first, second, rtol=1e-12, atol=1e-14) else 0.0
    return float((first_centered @ second_centered) / denominator)


def _kendall(first: FloatArray, second: FloatArray) -> float:
    concordant = discordant = 0
    for left in range(first.size):
        for right in range(left + 1, first.size):
            product = (first[left] - first[right]) * (second[left] - second[right])
            if product > 0.0:
                concordant += 1
            elif product < 0.0:
                discordant += 1
    compared = concordant + discordant
    if compared == 0:
        return 1.0 if np.allclose(first, second, rtol=1e-12, atol=1e-14) else 0.0
    return float((concordant - discordant) / compared)


def _safe_ratios(numerator: FloatArray, denominator: FloatArray) -> FloatArray:
    ratios = np.ones_like(numerator)
    positive = denominator > 1e-15
    ratios[positive] = numerator[positive] / denominator[positive]
    only_numerator = (~positive) & (numerator > 1e-15)
    ratios[only_numerator] = np.inf
    return ratios


def _effective_rank(data_matrix: FloatArray) -> float:
    values = np.maximum(np.linalg.eigvalsh(0.5 * (data_matrix + data_matrix.T)), 0.0)
    maximum = float(np.max(values, initial=0.0))
    return 0.0 if maximum <= 1e-15 else float(np.sum(values) / maximum)


def _subspace_alignment(
    matrix: FloatArray, direction: FloatArray, rank: int
) -> tuple[float, float, bool]:
    values, vectors = np.linalg.eigh(0.5 * (matrix + matrix.T))
    positive = values > 1e-12
    if not np.any(positive):
        return 0.0, 1.0, False
    order = np.argsort(values)[::-1]
    retained = vectors[:, order[: min(rank, matrix.shape[0])]]
    leading = float(np.sum((retained.T @ direction) ** 2))
    leading = min(max(leading, 0.0), 1.0)
    return leading, 1.0 - leading, True


def _candidate_projections(
    data_matrix: FloatArray,
    features: FloatArray,
    rank: int,
    *,
    basis: FloatArray | None = None,
) -> tuple[FloatArray, FloatArray, bool]:
    if basis is None:
        values, vectors = np.linalg.eigh(0.5 * (data_matrix + data_matrix.T))
        if float(np.max(values, initial=0.0)) <= 1e-12:
            zeros = np.zeros(features.shape[0], dtype=np.float64)
            return zeros, np.ones_like(zeros), False
        order = np.argsort(values)[::-1]
        retained = vectors[:, order[: min(rank, data_matrix.shape[0])]]
    else:
        retained = basis
        if retained.shape[1] == 0:
            zeros = np.zeros(features.shape[0], dtype=np.float64)
            return zeros, np.ones_like(zeros), False
    norms_squared = np.sum(features * features, axis=1)
    projected_squared = np.sum((features @ retained) ** 2, axis=1)
    leading = np.zeros(features.shape[0], dtype=np.float64)
    nonzero = norms_squared > 1e-15
    leading[nonzero] = projected_squared[nonzero] / norms_squared[nonzero]
    leading = np.clip(leading, 0.0, 1.0)
    return leading, 1.0 - leading, True


def _round_metrics(
    *,
    full_matrix: FloatArray,
    algorithmic_matrix: FloatArray,
    full_widths: FloatArray,
    algorithmic_widths: FloatArray,
    means: FloatArray,
    candidate_features: FloatArray,
    beta: float,
    damping: float,
    direction: FloatArray,
    alignment_rank: int,
    operator_basis: FloatArray | None,
    cg_iterations: Sequence[int],
    cg_residuals: Sequence[float],
    cg_tolerance: float,
) -> dict[str, Any]:
    full_scales = np.sqrt(np.maximum(full_widths, 0.0))
    algorithmic_scales = np.sqrt(np.maximum(algorithmic_widths, 0.0))
    width_ratios = _safe_ratios(algorithmic_scales, full_scales)
    finite_ratios = width_ratios[np.isfinite(width_ratios)]
    ratio_mean = float(np.mean(finite_ratios)) if finite_ratios.size else 0.0
    ratio_cv = (
        float(np.std(finite_ratios, ddof=0) / abs(ratio_mean))
        if finite_ratios.size and ratio_mean != 0.0
        else 0.0
    )

    full_scores = means + beta * full_scales
    algorithmic_scores = means + beta * algorithmic_scales
    full_order = np.argsort(-full_scores, kind="mergesort")
    reference_top = int(full_order[0])
    reference_runner_up = int(full_order[1])
    algorithmic_top = int(np.argmax(algorithmic_scores))
    reference_margin = float(
        full_scores[reference_top] - full_scores[reference_runner_up]
    )
    algorithmic_pair_margin = float(
        algorithmic_scores[reference_top] - algorithmic_scores[reference_runner_up]
    )
    normalized_distortion = (algorithmic_pair_margin - reference_margin) / (
        abs(reference_margin) + 1e-12
    )
    score_disagreement = float(
        np.linalg.norm(algorithmic_scores - full_scores)
        / (np.linalg.norm(full_scores) + 1e-12)
    )
    scalar_factor = ratio_mean if ratio_mean > 1e-15 else 1.0
    scalar_rescaled_scores = means + beta * algorithmic_scales / scalar_factor
    scalar_rescaled_top = int(np.argmax(scalar_rescaled_scores))

    full_data = full_matrix - damping * np.eye(full_matrix.shape[0])
    algorithmic_data = algorithmic_matrix - damping * np.eye(full_matrix.shape[0])
    ref_leading, ref_discarded, ref_defined = _subspace_alignment(
        full_data, direction, alignment_rank
    )
    if operator_basis is None:
        alg_leading, alg_discarded, alg_defined = _subspace_alignment(
            algorithmic_data, direction, alignment_rank
        )
    else:
        alg_leading = float(np.sum((operator_basis.T @ direction) ** 2))
        alg_leading = min(max(alg_leading, 0.0), 1.0)
        alg_discarded, alg_defined = 1.0 - alg_leading, True
    full_candidate_leading, full_candidate_discarded, full_candidate_defined = (
        _candidate_projections(
            full_data, candidate_features, alignment_rank
        )
    )
    operator_candidate_leading, operator_candidate_discarded, operator_candidate_defined = (
        _candidate_projections(
            algorithmic_data,
            candidate_features,
            alignment_rank,
            basis=operator_basis,
        )
    )

    full_over_alg = _safe_ratios(full_widths, algorithmic_widths)
    alg_over_full = _safe_ratios(algorithmic_widths, full_widths)
    return {
        "width_ratio_mean": ratio_mean,
        "width_ratio_cv": ratio_cv,
        "width_spearman": _spearman(full_scales, algorithmic_scales),
        "width_kendall": _kendall(full_scales, algorithmic_scales),
        "reference_top_action": reference_top,
        "diagnostic_top_action": algorithmic_top,
        "top_action_disagreement": algorithmic_top != reference_top,
        "reference_decision_margin": reference_margin,
        "algorithmic_reference_pair_margin": algorithmic_pair_margin,
        "normalized_margin_distortion_signed": float(normalized_distortion),
        "normalized_margin_distortion_abs": float(abs(normalized_distortion)),
        "ucb_score_disagreement": score_disagreement,
        "scalar_calibration_factor": scalar_factor,
        "scalar_rescaled_top_action": scalar_rescaled_top,
        "scalar_rescaled_score_disagreement": scalar_rescaled_top != reference_top,
        "reference_leading_alignment": ref_leading,
        "reference_discarded_alignment": ref_discarded,
        "reference_alignment_defined": ref_defined,
        "operator_leading_alignment": alg_leading,
        "operator_discarded_alignment": alg_discarded,
        "operator_alignment_defined": alg_defined,
        "candidate_full_leading_projection_mean": float(
            np.mean(full_candidate_leading)
        ),
        "candidate_full_discarded_projection_mean": float(
            np.mean(full_candidate_discarded)
        ),
        "candidate_full_leading_projection_reference_top": float(
            full_candidate_leading[reference_top]
        ),
        "candidate_full_discarded_projection_reference_top": float(
            full_candidate_discarded[reference_top]
        ),
        "candidate_full_projection_defined": full_candidate_defined,
        "candidate_operator_retained_projection_mean": float(
            np.mean(operator_candidate_leading)
        ),
        "candidate_operator_discarded_projection_mean": float(
            np.mean(operator_candidate_discarded)
        ),
        "candidate_operator_retained_projection_reference_top": float(
            operator_candidate_leading[reference_top]
        ),
        "candidate_operator_discarded_projection_reference_top": float(
            operator_candidate_discarded[reference_top]
        ),
        "candidate_operator_projection_defined": operator_candidate_defined,
        "global_transfer_alg_over_full": _generalized_max(
            algorithmic_matrix, full_matrix
        ),
        "global_transfer_full_over_alg": _generalized_max(
            full_matrix, algorithmic_matrix
        ),
        "action_transfer_full_width_over_alg": float(
            np.max(full_over_alg, initial=1.0)
        ),
        "action_transfer_alg_width_over_full": float(
            np.max(alg_over_full, initial=1.0)
        ),
        "full_effective_rank": _effective_rank(full_data),
        "full_condition": float(np.linalg.cond(full_matrix)),
        "algorithmic_condition": float(np.linalg.cond(algorithmic_matrix)),
        "cg_iterations_mean": float(np.mean(cg_iterations)) if cg_iterations else 0.0,
        "cg_iterations_max": int(max(cg_iterations, default=0)),
        "cg_relative_residual_max": float(max(cg_residuals, default=0.0)),
        "cg_all_converged": (
            max(cg_residuals, default=0.0)
            <= cg_tolerance * (1.0 + 1e-6) + 1e-14
        ),
    }


def _beta(
    config: Mapping[str, Any],
    cell: Cell,
    *,
    history_count: int,
    feature_bound: float,
) -> float:
    environment = config["environment"]
    dimension = int(environment["dimension"])
    variance = float(environment["noise_std"]) ** 2
    delta = float(config["policy"]["delta"])
    scale = float(config["policy"]["bonus_scale"])
    information = dimension * math.log1p(
        history_count
        * feature_bound
        * feature_bound
        / (dimension * cell.damping * variance)
    )
    return scale * (
        math.sqrt(information + 2.0 * math.log(1.0 / delta))
        + math.sqrt(cell.damping)
    )


def _base_record(
    cell: Cell, *, seed: int, method: str, round_index: int, mode: str
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "study": "curvature_mechanism_phase_diagram",
        "phase": "evaluation",
        "cell_id": cell.cell_id,
        "cell": cell.as_dict(),
        "seed": seed,
        "method": method,
        "round": round_index + 1,
        "execution_mode": mode,
        "representation_drift_status": cell.representation_drift_status,
        "representation_drift": cell.representation_drift,
    }


def _summarize_rounds(
    rounds: Sequence[Mapping[str, Any]],
    *,
    cell: Cell,
    seed: int,
    method: str,
    mode: str,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "study": "curvature_mechanism_phase_diagram",
        "phase": "evaluation",
        "cell_id": cell.cell_id,
        "cell": cell.as_dict(),
        "seed": seed,
        "method": method,
        "execution_mode": mode,
        "round_count": len(rounds),
        "representation_drift_status": cell.representation_drift_status,
        "evaluation_cell_selected_posthoc": False,
    }
    for key in ROUND_MEAN_METRICS:
        summary[f"{key}_mean"] = float(np.mean([float(row[key]) for row in rounds]))
    summary["top_action_disagreement_rate"] = float(
        np.mean([bool(row["top_action_disagreement"]) for row in rounds])
    )
    summary["global_transfer_alg_over_full_max"] = max(
        float(row["global_transfer_alg_over_full"]) for row in rounds
    )
    summary["action_transfer_full_width_over_alg_max"] = max(
        float(row["action_transfer_full_width_over_alg"]) for row in rounds
    )
    summary["full_condition_max"] = max(float(row["full_condition"]) for row in rounds)
    summary["algorithmic_condition_max"] = max(
        float(row["algorithmic_condition"]) for row in rounds
    )
    if rounds and "coverage_hits_all_actions" in rounds[0]:
        coverage_hits = sum(int(row["coverage_hits_all_actions"]) for row in rounds)
        coverage_total = sum(int(row["coverage_total_actions"]) for row in rounds)
        summary["empirical_coverage_all_actions"] = (
            float(coverage_hits / coverage_total) if coverage_total else 1.0
        )
        summary["average_bonus_magnitude"] = float(
            np.mean([float(row["average_bonus_magnitude"]) for row in rounds])
        )
    return summary


def run_online_policy(
    config: Mapping[str, Any],
    cell: Cell,
    seed: int,
    method: str,
    *,
    environment: Environment | None = None,
    bonus_multiplier: float = 1.0,
    calibration_protocol: str = "identical_theoretical_coefficient",
) -> PolicyResult:
    validate_config(config, require_30_seeds=False)
    if method not in SUPPORTED_METHODS:
        raise ValueError(f"unknown method {method}")
    if not math.isfinite(bonus_multiplier) or bonus_multiplier <= 0.0:
        raise ValueError("bonus_multiplier must be finite and positive")
    if not calibration_protocol:
        raise ValueError("calibration_protocol must be nonempty")
    env = environment or generate_environment(config, cell, seed)
    dimension = env.features.shape[2]
    variance = float(config["environment"]["noise_std"]) ** 2
    cg_options = config["method_options"]["cg"]
    builder = OperatorBuilder(method, config, cell, seed)
    history: list[FloatArray] = []
    observed_rewards: list[float] = []
    actions: list[int] = []
    records: list[dict[str, Any]] = []

    for round_index in range(env.features.shape[0]):
        estimate, full_matrix = _ridge_estimate(
            history,
            observed_rewards,
            dimension=dimension,
            damping=cell.damping,
            noise_variance=variance,
        )
        algorithmic_matrix, metadata = builder.build(
            round_index, history, full_matrix
        )
        candidate_features = env.features[round_index]
        means = candidate_features @ estimate
        full_widths = _dense_widths(full_matrix, candidate_features)
        if method == "full_cg":
            algorithmic_widths, iterations, residuals = _cg_widths(
                algorithmic_matrix,
                candidate_features,
                tolerance=float(cg_options["relative_residual"]),
                max_iterations=int(cg_options["max_iterations"]),
            )
        else:
            algorithmic_widths = _dense_widths(
                algorithmic_matrix, candidate_features
            )
            iterations, residuals = [], []
        base_beta = _beta(
            config,
            cell,
            history_count=len(history),
            feature_bound=env.feature_bound,
        )
        beta = bonus_multiplier * base_beta
        scores = means + beta * np.sqrt(np.maximum(algorithmic_widths, 0.0))
        action = int(np.argmax(scores))
        true_means = env.means[round_index]
        regret = float(np.max(true_means) - true_means[action])
        algorithmic_scales = np.sqrt(np.maximum(algorithmic_widths, 0.0))
        base_denominators = base_beta * algorithmic_scales
        prediction_errors = np.abs(true_means - means)
        required_multipliers = np.divide(
            prediction_errors,
            base_denominators,
            out=np.where(prediction_errors == 0.0, 0.0, np.inf),
            where=base_denominators > 0.0,
        )
        record = _base_record(
            cell,
            seed=seed,
            method=method,
            round_index=round_index,
            mode="online_adaptive_policy",
        )
        record.update(
            _round_metrics(
                full_matrix=full_matrix,
                algorithmic_matrix=algorithmic_matrix,
                full_widths=full_widths,
                algorithmic_widths=algorithmic_widths,
                means=means,
                candidate_features=candidate_features,
                beta=beta,
                damping=cell.damping,
                direction=env.decision_direction,
                alignment_rank=int(config["method_options"]["lanczos_rank"]),
                operator_basis=metadata["retained_basis"],
                cg_iterations=iterations,
                cg_residuals=residuals,
                cg_tolerance=float(cg_options["relative_residual"]),
            )
        )
        for diagnostic_only in (
            "scalar_calibration_factor",
            "scalar_rescaled_top_action",
            "scalar_rescaled_score_disagreement",
        ):
            record.pop(diagnostic_only)
        record.update(
            {
                "executed_policy": True,
                "causal_regret_claim": True,
                "selected_action": action,
                "optimal_action": int(np.argmax(true_means)),
                "pseudo_regret": regret,
                "beta": beta,
                "base_beta": base_beta,
                "calibration_multiplier": bonus_multiplier,
                "calibration_protocol": calibration_protocol,
                "coverage_hits_all_actions": int(
                    np.count_nonzero(required_multipliers <= bonus_multiplier)
                ),
                "coverage_total_actions": int(required_multipliers.size),
                "coverage_required_multipliers": required_multipliers.tolist(),
                "average_bonus_magnitude": float(np.mean(beta * algorithmic_scales)),
                "feature_bound": env.feature_bound,
                "realized_feature_max_posthoc": env.realized_feature_max,
                "feature_bound_source": "analytic_preexecution_cell_bound",
                "bonus_calibration": calibration_protocol,
                "population_effective_rank": float(
                    np.sum(env.covariance_eigenvalues)
                    / np.max(env.covariance_eigenvalues)
                ),
                "population_active_spectrum_condition_number": (
                    cell.active_spectrum_condition_number
                ),
                "population_full_covariance_condition_number": (
                    "infinite_rank_deficient"
                ),
                "optimal_action_structure": "arm_0_fixed_by_design",
                "benchmark_scope": (
                    "fixed_gap_curvature_mechanism_not_general_contextual"
                ),
            }
        )
        records.append(record)
        actions.append(action)
        selected = candidate_features[action].copy()
        history.append(selected)
        observed_rewards.append(float(env.rewards[round_index, action]))

    summary = _summarize_rounds(
        records,
        cell=cell,
        seed=seed,
        method=method,
        mode="online_adaptive_policy",
    )
    regrets = [float(record["pseudo_regret"]) for record in records]
    summary.update(
        {
            "executed_policy": True,
            "offline_diagnostic": False,
            "causal_regret_claim": True,
            "cumulative_pseudo_regret": float(sum(regrets)),
            "mean_pseudo_regret": float(np.mean(regrets)),
            "optimal_action_rate": float(
                np.mean(
                    [
                        int(record["selected_action"]) == int(record["optimal_action"])
                        for record in records
                    ]
                )
            ),
            "action_digest": hashlib.sha256(
                canonical_json(actions).encode("ascii")
            ).hexdigest(),
        }
    )
    return PolicyResult(
        method=method,
        actions=actions,
        selected_features=history,
        selected_rewards=observed_rewards,
        rounds=records,
        summary=summary,
    )


def run_common_trajectory_diagnostic(
    config: Mapping[str, Any],
    cell: Cell,
    seed: int,
    method: str,
    baseline: PolicyResult,
    *,
    environment: Environment | None = None,
) -> PolicyResult:
    if baseline.method != "exact_full":
        raise ValueError("common trajectory baseline must be exact_full")
    env = environment or generate_environment(config, cell, seed)
    dimension = env.features.shape[2]
    variance = float(config["environment"]["noise_std"]) ** 2
    cg_options = config["method_options"]["cg"]
    builder = OperatorBuilder(method, config, cell, seed)
    history: list[FloatArray] = []
    observed_rewards: list[float] = []
    records: list[dict[str, Any]] = []

    for round_index, logged_action in enumerate(baseline.actions):
        estimate, full_matrix = _ridge_estimate(
            history,
            observed_rewards,
            dimension=dimension,
            damping=cell.damping,
            noise_variance=variance,
        )
        algorithmic_matrix, metadata = builder.build(
            round_index, history, full_matrix
        )
        candidate_features = env.features[round_index]
        means = candidate_features @ estimate
        full_widths = _dense_widths(full_matrix, candidate_features)
        if method == "full_cg":
            algorithmic_widths, iterations, residuals = _cg_widths(
                algorithmic_matrix,
                candidate_features,
                tolerance=float(cg_options["relative_residual"]),
                max_iterations=int(cg_options["max_iterations"]),
            )
        else:
            algorithmic_widths = _dense_widths(
                algorithmic_matrix, candidate_features
            )
            iterations, residuals = [], []
        beta = _beta(
            config,
            cell,
            history_count=len(history),
            feature_bound=env.feature_bound,
        )
        diagnostic_action = int(
            np.argmax(means + beta * np.sqrt(np.maximum(algorithmic_widths, 0.0)))
        )
        algorithmic_scales = np.sqrt(np.maximum(algorithmic_widths, 0.0))
        full_scales = np.sqrt(np.maximum(full_widths, 0.0))
        true_means = env.means[round_index]
        prediction_errors = np.abs(true_means - means)
        base_denominators = beta * algorithmic_scales
        required_multipliers = np.divide(
            prediction_errors,
            base_denominators,
            out=np.where(prediction_errors == 0.0, 0.0, np.inf),
            where=base_denominators > 0.0,
        )
        record = _base_record(
            cell,
            seed=seed,
            method=method,
            round_index=round_index,
            mode="offline_common_trajectory_diagnostic",
        )
        record.update(
            _round_metrics(
                full_matrix=full_matrix,
                algorithmic_matrix=algorithmic_matrix,
                full_widths=full_widths,
                algorithmic_widths=algorithmic_widths,
                means=means,
                candidate_features=candidate_features,
                beta=beta,
                damping=cell.damping,
                direction=env.decision_direction,
                alignment_rank=int(config["method_options"]["lanczos_rank"]),
                operator_basis=metadata["retained_basis"],
                cg_iterations=iterations,
                cg_residuals=residuals,
                cg_tolerance=float(cg_options["relative_residual"]),
            )
        )
        record.update(
            {
                "executed_policy": False,
                "offline_diagnostic": True,
                "causal_regret_claim": False,
                "regret_reported": False,
                "logged_action": logged_action,
                "diagnostic_action": diagnostic_action,
                "diagnostic_action_matches_logged_action": diagnostic_action
                == logged_action,
                "coverage_hits_all_actions": int(
                    np.count_nonzero(required_multipliers <= 1.0)
                ),
                "coverage_total_actions": int(required_multipliers.size),
                "coverage_required_multipliers": required_multipliers.tolist(),
                "average_bonus_magnitude": float(np.mean(beta * algorithmic_scales)),
                "reference_average_bonus_magnitude": float(
                    np.mean(beta * full_scales)
                ),
                "baseline_action_digest": baseline.summary["action_digest"],
                "scalar_rescaling_status": (
                    "posthoc_common_trajectory_diagnostic_only"
                ),
            }
        )
        records.append(record)
        history.append(env.features[round_index, logged_action].copy())
        observed_rewards.append(float(env.rewards[round_index, logged_action]))

    summary = _summarize_rounds(
        records,
        cell=cell,
        seed=seed,
        method=method,
        mode="offline_common_trajectory_diagnostic",
    )
    summary.update(
        {
            "executed_policy": False,
            "offline_diagnostic": True,
            "causal_regret_claim": False,
            "regret_reported": False,
            "same_fixed_trajectory": True,
            "baseline_action_digest": baseline.summary["action_digest"],
            "diagnostic_action_matches_logged_rate": float(
                np.mean(
                    [
                        bool(record["diagnostic_action_matches_logged_action"])
                        for record in records
                    ]
                )
            ),
            "scalar_rescaled_score_disagreement_rate": float(
                np.mean(
                    [
                        bool(record["scalar_rescaled_score_disagreement"])
                        for record in records
                    ]
                )
            ),
            "scalar_rescaling_interpretation": (
                "divide algorithmic width by mean finite alg/full width ratio "
                "within round; diagnostic only"
            ),
        }
    )
    return PolicyResult(
        method=method,
        actions=list(baseline.actions),
        selected_features=history,
        selected_rewards=observed_rewards,
        rounds=records,
        summary=summary,
    )


def _numeric_summary_keys(records: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    ignored = {
        "schema_version",
        "seed",
        "round_count",
        "representation_drift",
    }
    keys: list[str] = []
    for key, value in records[0].items():
        if key in ignored or isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            keys.append(key)
    return tuple(sorted(keys))


def aggregate_summaries(
    online: Sequence[Mapping[str, Any]],
    common: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    aggregates: list[dict[str, Any]] = []
    for mode_records in (online, common):
        grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
        for record in mode_records:
            grouped.setdefault(
                (str(record["cell_id"]), str(record["method"])), []
            ).append(record)
        for (cell_id, method), records in sorted(grouped.items()):
            aggregate: dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "cell_id": cell_id,
                "cell": records[0]["cell"],
                "method": method,
                "execution_mode": records[0]["execution_mode"],
                "seed_count": len(records),
                "seeds": sorted(int(record["seed"]) for record in records),
                "evaluation_cell_selected_posthoc": False,
            }
            for key in _numeric_summary_keys(records):
                aggregate[key] = student_t_interval(
                    float(record[key]) for record in records
                )
            aggregates.append(aggregate)

    baseline = {
        (str(record["cell_id"]), int(record["seed"])): record
        for record in online
        if record["method"] == "exact_full"
    }
    paired: list[dict[str, Any]] = []
    grouped_methods: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for record in online:
        if record["method"] != "exact_full":
            grouped_methods.setdefault(
                (str(record["cell_id"]), str(record["method"])), []
            ).append(record)
    for (cell_id, method), records in sorted(grouped_methods.items()):
        differences: list[float] = []
        seeds: list[int] = []
        for record in sorted(records, key=lambda value: int(value["seed"])):
            seed = int(record["seed"])
            reference = baseline[(cell_id, seed)]
            differences.append(
                float(record["cumulative_pseudo_regret"])
                - float(reference["cumulative_pseudo_regret"])
            )
            seeds.append(seed)
        interval = student_t_interval(differences)
        if float(interval["ci95_low"]) > 0.0:
            classification = "full_lower_regret"
        elif float(interval["ci95_high"]) < 0.0:
            classification = "method_lower_regret"
        else:
            classification = "unresolved"
        paired.append(
            {
                "schema_version": SCHEMA_VERSION,
                "cell_id": cell_id,
                "cell": records[0]["cell"],
                "method": method,
                "reference_method": "exact_full",
                "difference": "method_minus_full_cumulative_pseudo_regret",
                "paired_interval": interval,
                "classification": classification,
                "classification_rule": (
                    "full_lower_regret iff CI low > 0; method_lower_regret iff "
                    "CI high < 0; otherwise unresolved"
                ),
                "seeds": seeds,
                "posthoc_cell_or_method_selection": False,
                "multiplicity_adjustment": "none_descriptive_preregistered_cells",
            }
        )
    return aggregates, paired


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(canonical_json(record) + "\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_study(
    config: Mapping[str, Any],
    output_dir: str | Path,
    *,
    write_round_records: bool | None = None,
) -> dict[str, Any]:
    validate_config(config, require_30_seeds=True)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty output directory {destination}")
    cells = cells_from_config(config)
    seeds = tuple(int(seed) for seed in config["study"]["evaluation_seeds"])
    write_rounds = (
        bool(config["output"]["write_round_records"])
        if write_round_records is None
        else bool(write_round_records)
    )
    preregistration = {
        "schema_version": SCHEMA_VERSION,
        "design": config["design"],
        "cells": [cell.as_dict() for cell in cells],
        "cell_count": len(cells),
        "evaluation_seeds": list(seeds),
        "evaluation_seed_count": len(seeds),
        "methods": list(METHODS),
        "phase": "evaluation",
        "tuning_enabled": False,
        "cell_selection": "none_preregistered_all_cells",
        "representation_drift": "not_run_fixed_zero",
    }
    preregistration["sha256"] = hashlib.sha256(
        canonical_json(preregistration).encode("ascii")
    ).hexdigest()
    _write_json(destination / "preregistered_grid.json", preregistration)

    online_summaries: list[dict[str, Any]] = []
    common_summaries: list[dict[str, Any]] = []
    online_rounds: list[dict[str, Any]] = []
    common_rounds: list[dict[str, Any]] = []
    started = time.perf_counter()
    for cell in cells:
        for seed in seeds:
            environment = generate_environment(config, cell, seed)
            baseline = run_online_policy(
                config, cell, seed, "exact_full", environment=environment
            )
            online_by_method: dict[str, PolicyResult] = {"exact_full": baseline}
            for method in METHODS[1:]:
                online_by_method[method] = run_online_policy(
                    config, cell, seed, method, environment=environment
                )
            for method in METHODS:
                result = online_by_method[method]
                online_summaries.append(result.summary)
                if write_rounds:
                    online_rounds.extend(result.rounds)
                diagnostic = run_common_trajectory_diagnostic(
                    config,
                    cell,
                    seed,
                    method,
                    baseline,
                    environment=environment,
                )
                common_summaries.append(diagnostic.summary)
                if write_rounds:
                    common_rounds.extend(diagnostic.rounds)
    elapsed = time.perf_counter() - started

    aggregates, paired = aggregate_summaries(online_summaries, common_summaries)
    _write_jsonl(destination / "online_summaries.jsonl", online_summaries)
    _write_jsonl(destination / "common_trajectory_summaries.jsonl", common_summaries)
    _write_jsonl(destination / "aggregates.jsonl", aggregates)
    _write_jsonl(destination / "paired_full_comparisons.jsonl", paired)
    if write_rounds:
        _write_jsonl(destination / "online_rounds.jsonl", online_rounds)
        _write_jsonl(destination / "common_trajectory_rounds.jsonl", common_rounds)

    output_files = sorted(
        path for path in destination.iterdir() if path.is_file()
    )
    file_hashes = {
        path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
        for path in output_files
    }
    source_path = Path(__file__).resolve()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "study": "curvature_mechanism_phase_diagram",
        "execution_phase": "evaluation",
        "tuning_enabled": False,
        "evaluation_cell_selection": "none",
        "full_win_search": False,
        "cell_count": len(cells),
        "evaluation_seed_count": len(seeds),
        "online_run_count": len(online_summaries),
        "common_trajectory_run_count": len(common_summaries),
        "paired_comparison_count": len(paired),
        "round_records_written": write_rounds,
        "elapsed_seconds": elapsed,
        "expected_full_runtime_seconds": config["output"][
            "expected_full_runtime_seconds"
        ],
        "config_sha256": hashlib.sha256(
            canonical_json(config).encode("ascii")
        ).hexdigest(),
        "preregistered_grid_sha256": preregistration["sha256"],
        "driver_sha256": _sha256(source_path),
        "provenance": collect_run_metadata(
            repository=source_path.parents[1], packages=("numpy", "scipy")
        ),
        "platform": platform.platform(),
        "outputs": file_hashes,
        "interpretation": {
            "online": "independently executed adaptive policies",
            "common_trajectory": "offline diagnostic; no causal regret claim",
            "paired_intervals": "descriptive 95% Student-t on preregistered cells",
            "representation_drift": "not run; fixed zero in bounded linear model",
        },
    }
    _write_json(destination / "manifest.json", manifest)
    return manifest


def build_artifact(
    config_path: str | Path,
    output_dir: str | Path,
    *,
    write_round_records: bool | None = None,
) -> dict[str, Any]:
    return run_study(
        load_config(config_path),
        output_dir,
        write_round_records=write_round_records,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("configs")
        / "curvature_phase_diagram.yaml",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--write-round-records", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    manifest = build_artifact(
        args.config,
        args.output,
        write_round_records=True if args.write_round_records else None,
    )
    print(canonical_json(manifest))


if __name__ == "__main__":
    main()


__all__ = [
    "Cell",
    "ConfigError",
    "Environment",
    "METHODS",
    "PolicyResult",
    "aggregate_summaries",
    "build_artifact",
    "cells_from_config",
    "generate_environment",
    "load_config",
    "run_common_trajectory_diagnostic",
    "run_online_policy",
    "run_study",
    "validate_config",
]
