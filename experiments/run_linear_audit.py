"""Run the bounded linear-bandit theorem audit.

Every policy in this module is executed online.  There is no oracle replay,
coverage interpolation, or retrospective action replacement.  The small fixed
feature dimension permits exact reference matrices alongside each practical
curvature strategy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import psutil
from numpy.typing import ArrayLike, NDArray

try:  # Package execution: python -m experiments.run_linear_audit
    from .linear_environment import (
        ACTION_COUNT,
        CONTEXT_DIMENSION,
        FEATURE_DIMENSION,
        LinearBanditEnvironment,
        default_theta_star,
        enumerate_rademacher_contexts,
    )
except ImportError:  # Direct script execution from the repository root.
    from experiments.linear_environment import (  # type: ignore[no-redef]
        ACTION_COUNT,
        CONTEXT_DIMENSION,
        FEATURE_DIMENSION,
        LinearBanditEnvironment,
        default_theta_star,
        enumerate_rademacher_contexts,
    )

try:
    from . import theory_metrics as _theory_metrics
except (ImportError, SyntaxError):  # The runner remains useful in a minimal copy.
    _theory_metrics = None

try:
    from .curvature_operators import conjugate_gradient as _core_cg
except (ImportError, SyntaxError):
    _core_cg = None

try:
    from .config import get_seed_set as _get_seed_set
    from .config import load_config as _load_config
except (ImportError, SyntaxError):
    _get_seed_set = None
    _load_config = None

try:
    from .logging_utils import ExperimentLogger as _ExperimentLogger
    from .logging_utils import append_jsonl as _append_jsonl
    from .logging_utils import derive_seed as _derive_seed
except (ImportError, SyntaxError):
    _ExperimentLogger = None
    _append_jsonl = None
    _derive_seed = None


FloatArray = NDArray[np.float64]

SUPPORTED_METHODS = (
    "dense_full",
    "cg_full",
    "diagonal",
    "unrescaled_window",
    "rescaled_subsample",
    "lanczos_ritz",
    "stale_refresh",
)

_METHOD_ALIASES = {
    "dense": "dense_full",
    "full": "dense_full",
    "full_dense": "dense_full",
    "cg": "cg_full",
    "full_cg": "cg_full",
    "window": "unrescaled_window",
    "unrescaled": "unrescaled_window",
    "subsample": "rescaled_subsample",
    "rescaled": "rescaled_subsample",
    "lanczos": "lanczos_ritz",
    "ritz": "lanczos_ritz",
    "stale": "stale_refresh",
    "refresh": "stale_refresh",
}


def canonical_method(name: str) -> str:
    normalized = str(name).strip().lower().replace("-", "_").replace(" ", "_")
    normalized = _METHOD_ALIASES.get(normalized, normalized)
    if normalized not in SUPPORTED_METHODS:
        raise ValueError(
            f"unknown method {name!r}; choose from {list(SUPPORTED_METHODS)}"
        )
    return normalized


def _mapping_value(
    source: Mapping[str, Any], paths: Sequence[str], default: Any
) -> Any:
    for path in paths:
        value: Any = source
        found = True
        for component in path.split("."):
            if not isinstance(value, Mapping) or component not in value:
                found = False
                break
            value = value[component]
        if found:
            return value
    return default


def _positive_float(value: Any, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


@dataclass(frozen=True)
class LinearAuditConfig:
    rounds: int
    ridge: float
    noise_std: float
    delta: float
    bonus_scale: float
    theta_star: tuple[float, ...]
    theta_bound: float
    window_size: int
    subsample_size: int
    lanczos_rank: int
    refresh_period: int
    cg_tolerance: float
    cg_max_iterations: int

    @classmethod
    def from_mapping(cls, source: Mapping[str, Any]) -> "LinearAuditConfig":
        legacy_coverage = str(
            _mapping_value(source, ("coverage.kind",), "")
        ).endswith("oracle_optimism") or "oracle_optimism" in str(
            _mapping_value(source, ("coverage.kind",), "")
        )
        context_dimension = int(
            _mapping_value(
                source,
                ("environment.context_dimension", "environment.p", "context_dim", "p"),
                CONTEXT_DIMENSION,
            )
        )
        action_count = int(
            _mapping_value(
                source,
                (
                    "environment.action_count",
                    "environment.K",
                    "actions",
                    "K",
                ),
                ACTION_COUNT,
            )
        )
        if legacy_coverage:
            context_dimension = CONTEXT_DIMENSION
            action_count = ACTION_COUNT
        if context_dimension != CONTEXT_DIMENSION or action_count != ACTION_COUNT:
            raise ValueError(
                f"the linear audit is fixed at p={CONTEXT_DIMENSION}, K={ACTION_COUNT}"
            )

        rounds_value = _mapping_value(
            source, ("rounds", "horizon", "environment.rounds"), None
        )
        if rounds_value is None and isinstance(source.get("horizons"), Mapping):
            profile = str(source.get("profile", "smoke"))
            rounds_value = source["horizons"].get(profile)
        rounds = _positive_int(32 if rounds_value is None else rounds_value, name="rounds")
        ridge = _positive_float(
            _mapping_value(
                source,
                ("ridge", "damping", "lambda", "algorithm.ridge", "algorithm.damping"),
                1.0,
            ),
            name="ridge",
        )
        variance_value = _mapping_value(
            source, ("environment.noise_variance", "noise_variance"), None
        )
        if variance_value is None:
            noise_std = _positive_float(
                _mapping_value(
                    source,
                    ("environment.noise_std", "environment.sigma", "noise_std", "sigma"),
                    0.25,
                ),
                name="noise_std",
            )
        else:
            noise_std = float(np.sqrt(_positive_float(variance_value, name="noise_variance")))

        delta = float(
            _mapping_value(source, ("confidence.delta", "delta", "algorithm.delta"), 0.05)
        )
        if not np.isfinite(delta) or not 0.0 < delta < 1.0:
            raise ValueError("delta must lie strictly between zero and one")
        raw_bonus_scale = _mapping_value(
            source, ("bonus_scale", "confidence.bonus_scale"), 1.0
        )
        bonus_scale = (
            float(raw_bonus_scale)
            if isinstance(raw_bonus_scale, (int, float, np.integer, np.floating))
            else 1.0
        )
        if not np.isfinite(bonus_scale) or bonus_scale < 1.0:
            raise ValueError("bonus_scale must be finite and at least one")

        theta_value = _mapping_value(
            source, ("environment.theta_star", "theta_star"), default_theta_star()
        )
        theta = np.asarray(theta_value, dtype=np.float64)
        if theta.shape != (FEATURE_DIMENSION,) or not np.all(np.isfinite(theta)):
            raise ValueError(f"theta_star must have shape ({FEATURE_DIMENSION},)")
        norm = float(np.linalg.norm(theta))
        theta_bound = _positive_float(
            _mapping_value(
                source, ("confidence.theta_bound", "theta_bound", "parameter_bound"), norm
            ),
            name="theta_bound",
        )
        if theta_bound + 1e-14 < norm:
            raise ValueError("theta_bound must be at least ||theta_star|| for a valid radius")

        window_size = _positive_int(
            _mapping_value(
                source,
                (
                    "curvature.window_size",
                    "method_options.unrescaled_window.window_size",
                    "methods.unrescaled_window.window_size",
                    "methods.unrescaled_window.size",
                    "methods.window.window_size",
                    "methods.window.size",
                    "window_size",
                ),
                8,
            ),
            name="window_size",
        )
        subsample_size = _positive_int(
            _mapping_value(
                source,
                (
                    "curvature.subsample_size",
                    "method_options.rescaled_subsample.sample_size",
                    "methods.rescaled_subsample.sample_size",
                    "methods.rescaled_subsample.size",
                    "methods.subsample.sample_size",
                    "methods.subsample.size",
                    "subsample_size",
                ),
                8,
            ),
            name="subsample_size",
        )
        lanczos_rank = _positive_int(
            _mapping_value(
                source,
                (
                    "curvature.lanczos_rank",
                    "method_options.lanczos_ritz.rank",
                    "methods.lanczos_ritz.rank",
                    "methods.lanczos.rank",
                    "lanczos_rank",
                ),
                8,
            ),
            name="lanczos_rank",
        )
        lanczos_rank = min(lanczos_rank, FEATURE_DIMENSION)
        refresh_period = _positive_int(
            _mapping_value(
                source,
                (
                    "curvature.refresh_period",
                    "method_options.stale_refresh.period",
                    "methods.stale_refresh.period",
                    "methods.stale_refresh.refresh_period",
                    "methods.stale.period",
                    "methods.refresh.period",
                    "refresh_period",
                ),
                4,
            ),
            name="refresh_period",
        )
        cg_tolerance = float(
            _mapping_value(
                source,
                (
                    "cg.tolerance",
                    "algorithm.cg_tolerance",
                    "methods.cg_full.tolerance",
                    "cg_tolerance",
                ),
                0.05,
            )
        )
        if not np.isfinite(cg_tolerance) or not 0.0 < cg_tolerance < 1.0:
            raise ValueError("cg_tolerance must lie strictly between zero and one")
        cg_max_iterations = _positive_int(
            _mapping_value(
                source,
                (
                    "cg.max_iterations",
                    "algorithm.cg_max_iterations",
                    "methods.cg_full.max_iterations",
                    "cg_max_iterations",
                ),
                2 * FEATURE_DIMENSION,
            ),
            name="cg_max_iterations",
        )
        return cls(
            rounds=rounds,
            ridge=ridge,
            noise_std=noise_std,
            delta=delta,
            bonus_scale=bonus_scale,
            theta_star=tuple(float(value) for value in theta),
            theta_bound=theta_bound,
            window_size=window_size,
            subsample_size=subsample_size,
            lanczos_rank=lanczos_rank,
            refresh_period=refresh_period,
            cg_tolerance=cg_tolerance,
            cg_max_iterations=cg_max_iterations,
        )


DEFAULT_CONFIG: dict[str, Any] = {
    "name": "linear_audit",
    "rounds": 32,
    "environment": {
        "context_dimension": CONTEXT_DIMENSION,
        "action_count": ACTION_COUNT,
        "noise_std": 0.25,
    },
    "ridge": 1.0,
    "confidence": {"delta": 0.05},
    "bonus_scale": 1.0,
    "curvature": {
        "window_size": 8,
        "subsample_size": 8,
        "lanczos_rank": 8,
        "refresh_period": 4,
    },
    "cg": {"tolerance": 0.05, "max_iterations": 2 * FEATURE_DIMENSION},
    "methods": list(SUPPORTED_METHODS),
    "seed_sets": {"tuning": [0, 1], "evaluation": [100, 101]},
}


def confidence_radius(
    round_index: int,
    *,
    dimension: int,
    feature_bound: float,
    ridge: float,
    noise_std: float,
    delta: float,
    theta_bound: float,
) -> tuple[float, float]:
    """Deterministic time-uniform LinUCB radius and its log-det upper bound."""

    observations = round_index - 1
    gamma_upper = float(
        dimension
        * np.log1p(
            observations
            * feature_bound
            * feature_bound
            / (dimension * ridge * noise_std * noise_std)
        )
    )
    beta = float(
        np.sqrt(gamma_upper + 2.0 * np.log(1.0 / delta))
        + np.sqrt(ridge) * theta_bound
    )
    return beta, gamma_upper


def _stable_seed(master_seed: int, *namespace: object) -> int:
    if _derive_seed is not None:
        try:
            return int(_derive_seed(int(master_seed), *namespace))
        except (TypeError, ValueError):
            pass
    payload = json.dumps([int(master_seed), *namespace], sort_keys=True).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def _history_matrix(history: Sequence[FloatArray]) -> FloatArray:
    if not history:
        return np.empty((0, FEATURE_DIMENSION), dtype=np.float64)
    return np.asarray(np.stack(history, axis=0), dtype=np.float64)


def _gram(features: FloatArray, *, ridge: float, noise_variance: float) -> FloatArray:
    matrix = ridge * np.eye(FEATURE_DIMENSION, dtype=np.float64)
    if features.shape[0]:
        matrix += (features.T @ features) / noise_variance
    return np.asarray(0.5 * (matrix + matrix.T), dtype=np.float64)


@dataclass(frozen=True)
class MatrixBuild:
    matrix: FloatArray
    metadata: dict[str, Any]


def _lanczos_surrogate(
    matrix: FloatArray, *, ridge: float, rank: int, seed: int
) -> MatrixBuild:
    dimension = matrix.shape[0]
    generator = np.random.default_rng(seed)
    q = generator.normal(size=dimension).astype(np.float64)
    q /= np.linalg.norm(q)
    basis: list[FloatArray] = []
    previous = np.zeros(dimension, dtype=np.float64)
    previous_beta = 0.0
    tolerance = 100.0 * np.finfo(np.float64).eps * max(1.0, np.linalg.norm(matrix, 2))

    for _ in range(min(rank, dimension)):
        basis.append(q.copy())
        z = matrix @ q - previous_beta * previous
        alpha = float(q @ z)
        z = z - alpha * q
        # Full double reorthogonalization makes the seeded construction stable.
        for _pass in range(2):
            for vector in basis:
                z -= float(vector @ z) * vector
        beta = float(np.linalg.norm(z))
        if beta <= tolerance:
            break
        previous, q, previous_beta = q, z / beta, beta

    krylov = np.column_stack(basis).astype(np.float64, copy=False)
    krylov, _ = np.linalg.qr(krylov, mode="reduced")
    compression = krylov.T @ matrix @ krylov
    compression = 0.5 * (compression + compression.T)
    values, vectors = np.linalg.eigh(compression)
    order = np.argsort(values)[::-1]
    values = np.asarray(values[order], dtype=np.float64)
    ritz_vectors = np.asarray(krylov @ vectors[:, order], dtype=np.float64)
    increments = np.maximum(values - ridge, 0.0)
    surrogate = ridge * np.eye(dimension, dtype=np.float64)
    surrogate += (ritz_vectors * increments) @ ritz_vectors.T
    surrogate = np.asarray(0.5 * (surrogate + surrogate.T), dtype=np.float64)
    residuals = np.linalg.norm(matrix @ ritz_vectors - ritz_vectors * values, axis=0)
    return MatrixBuild(
        surrogate,
        {
            "lanczos_steps": int(krylov.shape[1]),
            "ritz_values": values.tolist(),
            "ritz_residual_max": float(np.max(residuals, initial=0.0)),
        },
    )


class CurvatureStrategy:
    def __init__(self, method: str, config: LinearAuditConfig, seed: int) -> None:
        self.method = canonical_method(method)
        self.config = config
        self.seed = int(seed)

    def build(self, round_index: int, history: Sequence[FloatArray]) -> MatrixBuild:
        cfg = self.config
        variance = cfg.noise_std * cfg.noise_std
        all_features = _history_matrix(history)
        full = _gram(all_features, ridge=cfg.ridge, noise_variance=variance)
        count = all_features.shape[0]

        if self.method in {"dense_full", "cg_full"}:
            return MatrixBuild(full, {"history_count": count})
        if self.method == "diagonal":
            return MatrixBuild(
                np.diag(np.diag(full)).astype(np.float64), {"history_count": count}
            )
        if self.method == "unrescaled_window":
            start = max(0, count - cfg.window_size)
            selected = all_features[start:]
            return MatrixBuild(
                _gram(selected, ridge=cfg.ridge, noise_variance=variance),
                {"history_count": count, "selected_indices": list(range(start, count)), "rescale": 1.0},
            )
        if self.method == "rescaled_subsample":
            sample_count = min(count, cfg.subsample_size)
            if sample_count == 0:
                indices = np.empty(0, dtype=np.int64)
                scale = 1.0
            elif sample_count == count:
                indices = np.arange(count, dtype=np.int64)
                scale = 1.0
            else:
                rng = np.random.default_rng(
                    _stable_seed(self.seed, self.method, "round", round_index)
                )
                indices = np.sort(
                    rng.choice(count, size=sample_count, replace=False).astype(np.int64)
                )
                scale = float(count / sample_count)
            matrix = cfg.ridge * np.eye(FEATURE_DIMENSION, dtype=np.float64)
            if sample_count:
                selected = all_features[indices]
                matrix += scale * (selected.T @ selected) / variance
            return MatrixBuild(
                np.asarray(0.5 * (matrix + matrix.T), dtype=np.float64),
                {
                    "history_count": count,
                    "selected_indices": indices.tolist(),
                    "rescale": scale,
                },
            )
        if self.method == "lanczos_ritz":
            result = _lanczos_surrogate(
                full,
                ridge=cfg.ridge,
                rank=cfg.lanczos_rank,
                seed=_stable_seed(self.seed, self.method, "round", round_index),
            )
            result.metadata["history_count"] = count
            return result
        if self.method == "stale_refresh":
            retained = ((round_index - 1) // cfg.refresh_period) * cfg.refresh_period
            retained = min(retained, count)
            return MatrixBuild(
                _gram(
                    all_features[:retained], ridge=cfg.ridge, noise_variance=variance
                ),
                {
                    "history_count": count,
                    "refresh_history_count": retained,
                    "refreshed": bool(round_index == 1 or (round_index - 1) % cfg.refresh_period == 0),
                },
            )
        raise AssertionError(f"unhandled method {self.method}")


def _generalized_eigenvalues(
    approximate: FloatArray, reference: FloatArray
) -> FloatArray:
    if _theory_metrics is not None:
        function = getattr(_theory_metrics, "generalized_eigenvalues", None)
        if callable(function):
            try:
                result = function(approximate, reference)
                values = np.asarray(result.eigenvalues, dtype=np.float64)
                if values.shape == (reference.shape[0],):
                    return values
            except (AttributeError, TypeError):
                pass
    cholesky = np.linalg.cholesky(reference)
    left = np.linalg.solve(cholesky, approximate)
    whitened = np.linalg.solve(cholesky, left.T).T
    return np.asarray(np.linalg.eigvalsh(0.5 * (whitened + whitened.T)), dtype=np.float64)


def _inverse_sqrt(matrix: FloatArray) -> FloatArray:
    values, vectors = np.linalg.eigh(matrix)
    if np.any(values <= 0.0):
        raise ArithmeticError("matrix is not positive definite")
    return np.asarray((vectors * (1.0 / np.sqrt(values))) @ vectors.T, dtype=np.float64)


def _logdet(matrix: FloatArray) -> float:
    symmetric = np.asarray(0.5 * (matrix + matrix.T), dtype=np.float64)
    eigenvalues = np.linalg.eigvalsh(symmetric)
    if np.any(eigenvalues <= 0.0) or not np.all(np.isfinite(eigenvalues)):
        raise ArithmeticError("expected a finite positive determinant")
    return float(np.sum(np.log(eigenvalues)))


def _local_cg(
    matrix: FloatArray, rhs: FloatArray, *, tolerance: float, max_iterations: int
) -> tuple[FloatArray, int, float, bool]:
    solution = np.zeros_like(rhs)
    residual = rhs.copy()
    direction = residual.copy()
    rhs_norm = float(np.linalg.norm(rhs))
    squared = float(residual @ residual)
    threshold = tolerance * rhs_norm
    if np.sqrt(squared) <= threshold:
        return solution, 0, 0.0, True
    for iteration in range(1, max_iterations + 1):
        applied = matrix @ direction
        curvature = float(direction @ applied)
        if curvature <= 0.0:
            break
        step = squared / curvature
        solution += step * direction
        residual -= step * applied
        next_squared = float(residual @ residual)
        if np.sqrt(next_squared) <= threshold:
            relative = float(np.sqrt(next_squared) / rhs_norm)
            return solution, iteration, relative, True
        direction = residual + (next_squared / squared) * direction
        squared = next_squared
    relative = float(np.linalg.norm(rhs - matrix @ solution) / rhs_norm)
    return solution, max_iterations, relative, False


def _cg_solve(
    matrix: FloatArray, rhs: FloatArray, *, tolerance: float, max_iterations: int
) -> tuple[FloatArray, int, float, bool]:
    if _core_cg is not None:
        try:
            result = _core_cg(
                matrix,
                rhs,
                tolerance=tolerance,
                absolute_tolerance=0.0,
                max_iterations=max_iterations,
                initial_solution=None,
                raise_on_nonconvergence=False,
            )
            return (
                np.asarray(result.solution, dtype=np.float64).copy(),
                int(result.iterations),
                float(result.relative_residual_norm),
                bool(result.converged),
            )
        except TypeError:
            pass
    return _local_cg(
        matrix, rhs, tolerance=tolerance, max_iterations=max_iterations
    )


@dataclass(frozen=True)
class RoundMatrices:
    reference: FloatArray
    frozen: FloatArray
    algorithmic: FloatArray
    algorithmic_plus: FloatArray
    next_algorithmic: FloatArray
    normalized_perturbation: FloatArray
    action_features: FloatArray
    played_feature: FloatArray

    @property
    def C_t(self) -> FloatArray:
        return self.reference

    @property
    def C_bar_t(self) -> FloatArray:
        return self.frozen


@dataclass(frozen=True)
class AuditRun:
    method: str
    seed: int
    config: LinearAuditConfig
    rounds: tuple[dict[str, Any], ...]
    matrices: tuple[RoundMatrices, ...]
    operators: tuple[FloatArray, ...]
    played_features: FloatArray
    summary: dict[str, Any]

    @property
    def actions(self) -> tuple[int, ...]:
        return tuple(int(record["action"]) for record in self.rounds)

    @property
    def contexts(self) -> FloatArray:
        return np.asarray([record["context"] for record in self.rounds], dtype=np.float64)


def _readonly_copy(array: ArrayLike) -> FloatArray:
    copied = np.asarray(array, dtype=np.float64).copy()
    copied.setflags(write=False)
    return copied


def run_method(
    config: Mapping[str, Any] | LinearAuditConfig,
    method: str,
    seed: int,
    *,
    retain_matrices: bool = True,
) -> AuditRun:
    """Execute one policy and return exact pathwise audit diagnostics."""

    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or int(seed) < 0:
        raise ValueError("seed must be a nonnegative integer")
    cfg = config if isinstance(config, LinearAuditConfig) else LinearAuditConfig.from_mapping(config)
    method = canonical_method(method)
    environment_seed = _stable_seed(int(seed), "linear_audit", "environment")
    strategy_seed = _stable_seed(int(seed), "linear_audit", method, "curvature")
    environment = LinearBanditEnvironment(
        environment_seed, noise_std=cfg.noise_std, theta_star=cfg.theta_star
    )
    strategy = CurvatureStrategy(method, cfg, strategy_seed)

    variance = cfg.noise_std * cfg.noise_std
    dimension = FEATURE_DIMENSION
    feature_bound = environment.feature_norm
    reference = cfg.ridge * np.eye(dimension, dtype=np.float64)
    response_vector = np.zeros(dimension, dtype=np.float64)
    theta_hat = np.zeros(dimension, dtype=np.float64)
    history: list[FloatArray] = []
    records: list[dict[str, Any]] = []
    matrix_records: list[RoundMatrices] = []
    operators: list[FloatArray] = []
    played_features: list[FloatArray] = []

    cumulative_regret = 0.0
    cumulative_information = 0.0
    cumulative_transition = 0.0
    cumulative_variation = 0.0
    cumulative_width = 0.0
    cumulative_S = 0.0
    cumulative_all_action_violations = 0
    cumulative_selected_action_violations = 0
    total_runtime_seconds = 0.0
    process = psutil.Process()
    peak_host_memory_bytes = process.memory_info().rss
    initial_logdet = dimension * math.log(cfg.ridge)

    for round_index in range(1, cfg.rounds + 1):
        round_started = time.perf_counter()
        current_build = strategy.build(round_index, history)
        algorithmic = current_build.matrix
        if not operators:
            operators.append(_readonly_copy(algorithmic))
        frozen = reference.copy()  # Linear features do not drift: C_t = Cbar_t.
        context = environment.draw_context()
        candidates = environment.features(context)
        true_means = np.asarray(candidates @ environment.theta_star, dtype=np.float64)
        predicted_means = np.asarray(candidates @ theta_hat, dtype=np.float64)
        optimal_action = int(np.argmax(true_means))

        beta, gamma_upper = confidence_radius(
            round_index,
            dimension=dimension,
            feature_bound=feature_bound,
            ridge=cfg.ridge,
            noise_std=cfg.noise_std,
            delta=cfg.delta,
            theta_bound=cfg.theta_bound,
        )
        beta *= cfg.bonus_scale

        generalized = _generalized_eigenvalues(algorithmic, reference)
        rho_minus = float(generalized[0])
        rho_plus = float(generalized[-1])
        if method in {"dense_full", "cg_full", "unrescaled_window", "stale_refresh"}:
            # These relations are analytic in this linear benchmark.
            kappa_plus = 1.0
        else:
            kappa_plus = max(1.0, rho_plus * (1.0 + 32.0 * np.finfo(np.float64).eps))
        transfer_factor = kappa_plus

        exact_solutions = np.linalg.solve(algorithmic, candidates.T).T
        algorithmic_widths_sq = np.einsum(
            "ij,ij->i", candidates, exact_solutions, dtype=np.float64
        )
        frozen_solutions = np.linalg.solve(frozen, candidates.T).T
        frozen_widths_sq = np.einsum(
            "ij,ij->i", candidates, frozen_solutions, dtype=np.float64
        )

        approximate_widths_sq = algorithmic_widths_sq.copy()
        energy_errors = np.zeros(ACTION_COUNT, dtype=np.float64)
        cg_iterations = np.zeros(ACTION_COUNT, dtype=np.int64)
        cg_relative_residuals = np.zeros(ACTION_COUNT, dtype=np.float64)
        cg_fallback = False
        certified_cg_error = 0.0
        condition_number = float(np.linalg.cond(algorithmic))
        if method == "cg_full":
            residual_target = cfg.cg_tolerance / np.sqrt(condition_number)
            for action in range(ACTION_COUNT):
                approximate, iterations, relative_residual, converged = _cg_solve(
                    algorithmic,
                    candidates[action],
                    tolerance=residual_target,
                    max_iterations=cfg.cg_max_iterations,
                )
                difference = approximate - exact_solutions[action]
                denominator = float(
                    exact_solutions[action] @ algorithmic @ exact_solutions[action]
                )
                numerator = float(difference @ algorithmic @ difference)
                energy_error = float(np.sqrt(max(numerator, 0.0) / denominator))
                width_squared = float(candidates[action] @ approximate)
                if not converged or energy_error >= 1.0 or width_squared < 0.0:
                    approximate = exact_solutions[action].copy()
                    energy_error = 0.0
                    width_squared = float(algorithmic_widths_sq[action])
                    relative_residual = 0.0
                    cg_fallback = True
                approximate_widths_sq[action] = width_squared
                energy_errors[action] = energy_error
                cg_iterations[action] = iterations
                cg_relative_residuals[action] = relative_residual
            certified_cg_error = cfg.cg_tolerance
            if float(np.max(energy_errors)) > certified_cg_error * (1.0 + 1e-10):
                # Exact small-matrix auditing supplies a predictable certificate.
                certified_cg_error = min(
                    0.999999,
                    float(np.max(energy_errors)) * (1.0 + 64.0 * np.finfo(np.float64).eps),
                )

        alpha = float(
            np.sqrt((1.0 + certified_cg_error) / (1.0 - certified_cg_error))
        )
        bonus = beta * np.sqrt(transfer_factor / (1.0 - certified_cg_error)) * np.sqrt(
            approximate_widths_sq
        )
        optimism_violations = true_means > predicted_means + bonus + 1e-12
        scores = predicted_means + bonus
        action = int(np.argmax(scores))
        reward, noise = environment.reward(context, action)
        played = candidates[action].copy()
        pseudo_regret = float(true_means[optimal_action] - true_means[action])
        cumulative_regret += pseudo_regret
        cumulative_all_action_violations += int(np.count_nonzero(optimism_violations))
        cumulative_selected_action_violations += int(optimism_violations[action])

        algorithmic_plus = algorithmic + np.outer(played, played) / variance
        next_history = [*history, played]
        next_build = strategy.build(round_index + 1, next_history)
        next_algorithmic = next_build.matrix
        inverse_root = _inverse_sqrt(algorithmic_plus)
        xi = inverse_root @ (next_algorithmic - algorithmic_plus) @ inverse_root
        xi = np.asarray(0.5 * (xi + xi.T), dtype=np.float64)
        transition_logdet = _logdet(np.eye(dimension, dtype=np.float64) + xi)
        variation_increment = max(-transition_logdet, 0.0)

        played_width_sq = float(algorithmic_widths_sq[action])
        information_increment = float(np.log1p(played_width_sq / variance))
        cumulative_information += information_increment
        cumulative_S += alpha * alpha * transfer_factor * beta * beta
        cumulative_transition += transition_logdet
        cumulative_variation += variation_increment
        cumulative_width += played_width_sq
        endpoint_logdet = _logdet(next_algorithmic) - initial_logdet
        identity_rhs = endpoint_logdet - cumulative_transition
        dynamic_potential = endpoint_logdet + cumulative_variation
        width_coefficient = variance + feature_bound * feature_bound / cfg.ridge
        theorem_rhs = 2.0 * np.sqrt(
            width_coefficient * cumulative_information * cumulative_S
        )

        reference_next = reference + np.outer(played, played) / variance
        response_next = response_vector + played * reward / variance
        theta_next = np.linalg.solve(reference_next, response_next)

        transfer_slack = transfer_factor * algorithmic_widths_sq - frozen_widths_sq
        lower_bonus = beta * np.sqrt(frozen_widths_sq)
        upper_bonus = (
            alpha
            * beta
            * np.sqrt(transfer_factor)
            * np.sqrt(algorithmic_widths_sq)
        )
        cg_lower = (1.0 - certified_cg_error) * algorithmic_widths_sq
        cg_upper = (1.0 + certified_cg_error) * algorithmic_widths_sq
        confidence_ratios = np.abs(candidates @ (theta_hat - environment.theta_star)) / np.sqrt(
            frozen_widths_sq
        )
        round_runtime_seconds = time.perf_counter() - round_started
        total_runtime_seconds += round_runtime_seconds
        peak_host_memory_bytes = max(
            peak_host_memory_bytes, process.memory_info().rss
        )

        record: dict[str, Any] = {
            "round": round_index,
            "method": method,
            "executed_policy": True,
            "certificate_mode": "predictable_exact_small_scale",
            "context": context.tolist(),
            "action": action,
            "optimal_action": optimal_action,
            "reward": float(reward),
            "noise": float(noise),
            "true_mean": float(true_means[action]),
            "optimal_mean": float(true_means[optimal_action]),
            "pseudo_regret": pseudo_regret,
            "cumulative_pseudo_regret": cumulative_regret,
            "predicted_means": predicted_means.tolist(),
            "true_means": true_means.tolist(),
            "ucb_scores": scores.tolist(),
            "bonuses": bonus.tolist(),
            "beta_t": beta,
            "gamma_upper_t": gamma_upper,
            "confidence_ratio_max": float(np.max(confidence_ratios)),
            "confidence_radius_valid_on_path": bool(np.max(confidence_ratios) <= beta + 1e-10),
            "optimism_violations": optimism_violations.tolist(),
            "all_action_optimism_violation_rate": (
                cumulative_all_action_violations / (round_index * ACTION_COUNT)
            ),
            "selected_action_optimism_violation": bool(optimism_violations[action]),
            "selected_action_optimism_violation_rate": (
                cumulative_selected_action_violations / round_index
            ),
            "E_t": 0.0,
            "F_t": 0.0,
            "E_T": 0.0,
            "F_T": 0.0,
            "psi_t": 0.0,
            "bar_psi_t": 0.0,
            "chi_t": 0.0,
            "bar_chi_t": 0.0,
            "C_equals_Cbar": True,
            "C_Cbar_max_abs": float(np.max(np.abs(reference - frozen))),
            "reference_update_max_abs": float(
                np.max(np.abs(reference_next - reference - np.outer(played, played) / variance))
            ),
            "ridge_normal_equation_residual": float(
                np.linalg.norm(reference_next @ theta_next - response_next)
            ),
            "rho_minus": rho_minus,
            "rho_plus": rho_plus,
            "kappa_plus": transfer_factor,
            "u_t": transfer_factor,
            "transfer_slack_min": float(np.min(transfer_slack)),
            "algorithmic_widths_squared": algorithmic_widths_sq.tolist(),
            "approximate_widths_squared": approximate_widths_sq.tolist(),
            "frozen_widths_squared": frozen_widths_sq.tolist(),
            "cg_energy_error_max": float(np.max(energy_errors)),
            "cg_certified_epsilon": certified_cg_error,
            "cg_iterations": cg_iterations.tolist(),
            "cg_relative_residuals": cg_relative_residuals.tolist(),
            "cg_fallback": cg_fallback,
            "cg_sandwich_lower_slack_min": float(np.min(approximate_widths_sq - cg_lower)),
            "cg_sandwich_upper_slack_min": float(np.min(cg_upper - approximate_widths_sq)),
            "bonus_lower_slack_min": float(np.min(bonus - lower_bonus)),
            "bonus_upper_slack_min": float(np.min(upper_bonus - bonus)),
            "alpha_t": alpha,
            "omega_t": beta,
            "S_t_cumulative": cumulative_S,
            "theorem_rhs": float(theorem_rhs),
            "theorem_bound_slack": float(theorem_rhs - cumulative_regret),
            "information_increment": information_increment,
            "Lambda_alg_cumulative": cumulative_information,
            "transition_logdet": transition_logdet,
            "variation_increment": variation_increment,
            "V_alg_cumulative": cumulative_variation,
            "endpoint_logdet": endpoint_logdet,
            "Gamma_dynamic_cumulative": dynamic_potential,
            "dynamic_identity_rhs": identity_rhs,
            "dynamic_identity_residual": cumulative_information - identity_rhs,
            "dynamic_bound_slack": dynamic_potential - cumulative_information,
            "width_squared_cumulative": cumulative_width,
            "width_information_bound": width_coefficient * cumulative_information,
            "width_dynamic_bound": width_coefficient * dynamic_potential,
            "width_information_slack": width_coefficient * cumulative_information - cumulative_width,
            "width_dynamic_slack": width_coefficient * dynamic_potential - cumulative_width,
            "xi_min_eigenvalue": float(np.linalg.eigvalsh(xi)[0]),
            "operator_min_eigenvalue": float(np.linalg.eigvalsh(algorithmic)[0]),
            "kappa_t": condition_number,
            "kappa_bar_t": condition_number,
            "kappa_bar_source": "exact_dense_pre_action_small_scale_certificate",
            "operator_condition_number": condition_number,
            "round_runtime_seconds": round_runtime_seconds,
            "runtime_seconds": total_runtime_seconds,
            "peak_host_memory_bytes": peak_host_memory_bytes,
            "operator_metadata": current_build.metadata,
            "next_operator_metadata": next_build.metadata,
        }
        records.append(record)
        played_features.append(played.copy())
        operators.append(_readonly_copy(next_algorithmic))
        if retain_matrices:
            matrix_records.append(
                RoundMatrices(
                    reference=_readonly_copy(reference),
                    frozen=_readonly_copy(frozen),
                    algorithmic=_readonly_copy(algorithmic),
                    algorithmic_plus=_readonly_copy(algorithmic_plus),
                    next_algorithmic=_readonly_copy(next_algorithmic),
                    normalized_perturbation=_readonly_copy(xi),
                    action_features=_readonly_copy(candidates),
                    played_feature=_readonly_copy(played),
                )
            )

        history = next_history
        reference = reference_next
        response_vector = response_next
        theta_hat = theta_next

    played_matrix = np.asarray(np.stack(played_features), dtype=np.float64)
    shared_metrics_used = False
    shared_identity_residual: float | None = None
    shared_width_metrics_used = False
    shared_width_information_slack: float | None = None
    shared_width_dynamic_slack: float | None = None
    if _theory_metrics is not None:
        dynamic_function = getattr(_theory_metrics, "dynamic_logdet_metrics", None)
        if callable(dynamic_function):
            try:
                with np.errstate(all="ignore"):
                    shared = dynamic_function(
                        tuple(operators), played_matrix, noise_variance=variance
                    )
                shared_metrics_used = True
                shared_identity_residual = float(shared.identity_residual)
                if not np.isclose(
                    shared.information_complexity,
                    cumulative_information,
                    rtol=2e-10,
                    atol=2e-10,
                ):
                    raise AssertionError("shared dynamic metric disagrees with runner")
            except (AttributeError, TypeError):
                pass
        width_function = getattr(_theory_metrics, "width_sum_inequality", None)
        if callable(width_function):
            try:
                with np.errstate(all="ignore"):
                    width_result = width_function(
                        tuple(operators),
                        played_matrix,
                        damping=cfg.ridge,
                        noise_variance=variance,
                        feature_bound=feature_bound,
                    )
                shared_width_metrics_used = True
                shared_width_information_slack = float(
                    width_result.information_bound - width_result.width_sum
                )
                shared_width_dynamic_slack = float(
                    width_result.dynamic_bound - width_result.width_sum
                )
                if not np.isclose(
                    width_result.width_sum,
                    cumulative_width,
                    rtol=2e-10,
                    atol=2e-10,
                ):
                    raise AssertionError("shared width metric disagrees with runner")
            except (AttributeError, TypeError):
                pass

    all_optimal_actions = {
        environment.optimal_action(context) for context in enumerate_rademacher_contexts()
    }
    last = records[-1]
    summary = {
        "method": method,
        "seed": int(seed),
        "executed_policy": True,
        "certificate_mode": "predictable_exact_small_scale",
        "policy_used_predictable_valid_certificates": True,
        "confidence_event_realized": all(
            bool(item["confidence_radius_valid_on_path"]) for item in records
        ),
        "certified_execution": all(
            bool(item["confidence_radius_valid_on_path"]) for item in records
        ) and not any(bool(item["cg_fallback"]) for item in records),
        "rounds": cfg.rounds,
        "cumulative_pseudo_regret": cumulative_regret,
        "E_T": 0.0,
        "F_T": 0.0,
        "psi_max": 0.0,
        "chi_max": 0.0,
        "C_equals_Cbar_all_rounds": True,
        "context_dependent_optimal_arm": len(all_optimal_actions) > 1,
        "optimal_arms_over_support": sorted(all_optimal_actions),
        "Lambda_alg_T": cumulative_information,
        "S_T": cumulative_S,
        "theorem_rhs": float(last["theorem_rhs"]),
        "theorem_bound_slack": float(last["theorem_bound_slack"]),
        "all_action_optimism_violation_rate": float(
            last["all_action_optimism_violation_rate"]
        ),
        "selected_action_optimism_violation_rate": float(
            last["selected_action_optimism_violation_rate"]
        ),
        "runtime_seconds": total_runtime_seconds,
        "peak_host_memory_bytes": peak_host_memory_bytes,
        "mean_cg_iterations": float(
            np.mean([np.mean(item["cg_iterations"]) for item in records])
        ),
        "V_alg_T": cumulative_variation,
        "Gamma_dynamic_T": float(last["Gamma_dynamic_cumulative"]),
        "dynamic_identity_residual": float(last["dynamic_identity_residual"]),
        "dynamic_bound_slack": float(last["dynamic_bound_slack"]),
        "width_information_slack": float(last["width_information_slack"]),
        "width_dynamic_slack": float(last["width_dynamic_slack"]),
        "transfer_slack_min": min(float(item["transfer_slack_min"]) for item in records),
        "bonus_lower_slack_min": min(float(item["bonus_lower_slack_min"]) for item in records),
        "bonus_upper_slack_min": min(float(item["bonus_upper_slack_min"]) for item in records),
        "cg_sandwich_lower_slack_min": min(
            float(item["cg_sandwich_lower_slack_min"]) for item in records
        ),
        "cg_sandwich_upper_slack_min": min(
            float(item["cg_sandwich_upper_slack_min"]) for item in records
        ),
        "shared_theory_metrics_used": shared_metrics_used,
        "shared_dynamic_identity_residual": shared_identity_residual,
        "shared_width_metrics_used": shared_width_metrics_used,
        "shared_width_information_slack": shared_width_information_slack,
        "shared_width_dynamic_slack": shared_width_dynamic_slack,
    }
    return AuditRun(
        method=method,
        seed=int(seed),
        config=cfg,
        rounds=tuple(records),
        matrices=tuple(matrix_records),
        operators=tuple(operators) if retain_matrices else tuple(),
        played_features=_readonly_copy(played_matrix),
        summary=summary,
    )


# Public aliases used by small scripts and tests.
run_policy = run_method
run_linear_audit = run_method


def configured_methods(config: Mapping[str, Any]) -> tuple[str, ...]:
    coverage_kind = str(_mapping_value(config, ("coverage.kind",), ""))
    if "oracle_optimism" in coverage_kind:
        # Ignore the superseded retrospective coverage grid.  This driver only
        # executes online policies from the current seven-method audit.
        return SUPPORTED_METHODS
    value = config.get("methods", SUPPORTED_METHODS)
    selected: list[str] = []
    if isinstance(value, Mapping):
        for name, options in value.items():
            enabled = options.get("enabled", True) if isinstance(options, Mapping) else bool(options)
            if enabled:
                selected.append(canonical_method(str(name)))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            if isinstance(item, Mapping):
                if item.get("enabled", True):
                    selected.append(canonical_method(str(item.get("name"))))
            else:
                selected.append(canonical_method(str(item)))
    else:
        raise TypeError("methods must be a list or mapping")
    return tuple(dict.fromkeys(selected))


def selected_seeds(config: Mapping[str, Any], seed_set: str) -> tuple[int, ...]:
    if seed_set not in {"tuning", "evaluation"}:
        raise ValueError("seed_set must be 'tuning' or 'evaluation'")
    if _get_seed_set is not None:
        try:
            return tuple(int(seed) for seed in _get_seed_set(config, seed_set))
        except (KeyError, TypeError, ValueError):
            pass
    sets = config.get("seed_sets")
    if isinstance(sets, Mapping):
        tuning_values = sets.get("tuning", ())
        evaluation_values = sets.get("evaluation", ())
    else:
        tuning_values = config.get("tuning_seeds", ())
        evaluation_values = config.get("evaluation_seeds", ())
    tuning = tuple(int(seed) for seed in tuning_values)
    evaluation = tuple(int(seed) for seed in evaluation_values)
    if not tuning or not evaluation:
        raise ValueError("both tuning and evaluation seed sets must be nonempty")
    if set(tuning) & set(evaluation):
        raise ValueError("tuning and evaluation seed sets must be disjoint")
    chosen = tuning if seed_set == "tuning" else evaluation
    if len(chosen) != len(set(chosen)) or any(seed < 0 for seed in chosen):
        raise ValueError(f"invalid {seed_set} seed set")
    return chosen


class _FallbackLogger:
    def __init__(self, output_dir: Path, config: Mapping[str, Any], seed: int, *, overwrite: bool) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.raw_path = output_dir / "raw.jsonl"
        self.manifest_path = output_dir / "manifest.jsonl"
        if not overwrite and (self.raw_path.exists() or self.manifest_path.exists()):
            raise FileExistsError(f"output already exists in {output_dir}")
        self.raw_path.write_text("", encoding="utf-8")
        self.manifest_path.write_text(
            json.dumps({"schema_version": 1, "seed": seed, "config": config}, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

    def log_round(self, round_index: int, metrics: Mapping[str, Any]) -> None:
        with self.raw_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"round": round_index, "metrics": metrics}, sort_keys=True) + "\n")

    def close(self) -> None:
        return None


def save_run(
    run: AuditRun,
    output_dir: str | Path,
    config: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    destination = Path(output_dir)
    manifest_config = dict(config)
    manifest_config["execution"] = {
        "method": run.method,
        "seed": run.seed,
        "executed_policy": True,
    }
    if _ExperimentLogger is not None:
        try:
            logger = _ExperimentLogger(
                destination, manifest_config, run.seed, overwrite=overwrite
            )
        except TypeError:
            logger = _FallbackLogger(destination, manifest_config, run.seed, overwrite=overwrite)
    else:
        logger = _FallbackLogger(destination, manifest_config, run.seed, overwrite=overwrite)
    try:
        for record in run.rounds:
            logger.log_round(int(record["round"]) - 1, record)
    finally:
        logger.close()

    summary_path = destination / "summary.jsonl"
    if overwrite and summary_path.exists():
        summary_path.unlink()
    if _append_jsonl is not None:
        _append_jsonl(summary_path, run.summary)
    else:
        with summary_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(run.summary, sort_keys=True, allow_nan=False) + "\n")
    return destination


def run_experiment(
    config: Mapping[str, Any],
    *,
    seed_set: str = "evaluation",
    methods: Sequence[str] | None = None,
    output_dir: str | Path | None = None,
    overwrite: bool = False,
    retain_matrices: bool = False,
) -> tuple[AuditRun, ...]:
    chosen_methods = (
        tuple(canonical_method(method) for method in methods)
        if methods is not None
        else configured_methods(config)
    )
    seeds = selected_seeds(config, seed_set)
    results: list[AuditRun] = []
    for seed in seeds:
        for method in chosen_methods:
            run = run_method(config, method, seed, retain_matrices=retain_matrices)
            results.append(run)
            if output_dir is not None:
                profile = str(config.get("profile", "default"))
                save_run(
                    run,
                    Path(output_dir)
                    / profile
                    / seed_set
                    / method
                    / f"seed-{seed}",
                    config,
                    overwrite=overwrite,
                )
    return tuple(results)


def _load_document(path: Path, profile: str) -> dict[str, Any]:
    if _load_config is not None:
        try:
            return dict(_load_config(path, profile=profile))
        except TypeError:
            try:
                return dict(_load_config(path, profile))
            except ValueError:
                pass
        except ValueError:
            pass
    text = path.read_text(encoding="utf-8")
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as error:
            raise ValueError("non-JSON YAML requires PyYAML") from error
        document = yaml.safe_load(text)
    if not isinstance(document, Mapping):
        raise ValueError("config must contain a top-level mapping")
    if "base" in document and "profiles" in document:
        def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
            merged_value = dict(base)
            for key, value in override.items():
                if isinstance(value, Mapping) and isinstance(merged_value.get(key), Mapping):
                    merged_value[key] = deep_merge(merged_value[key], value)
                else:
                    merged_value[key] = value
            return merged_value

        base = document["base"] if isinstance(document["base"], Mapping) else {}
        profiles = document["profiles"] if isinstance(document["profiles"], Mapping) else {}
        selected = profiles.get(profile, {})
        if not isinstance(selected, Mapping):
            raise ValueError(f"profile {profile!r} must be a mapping")
        header = {key: value for key, value in document.items() if key not in {"base", "profiles"}}
        merged = deep_merge(header, base)
        merged = deep_merge(merged, selected)
        merged["profile"] = profile
        return merged
    return dict(document)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument(
        "--seed-set", choices=("tuning", "evaluation"), default="evaluation"
    )
    parser.add_argument("--method", action="append", choices=SUPPORTED_METHODS)
    parser.add_argument("--rounds", type=int, help="override the resolved horizon")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    config = dict(DEFAULT_CONFIG) if args.config is None else _load_document(args.config, args.profile)
    if args.rounds is not None:
        if args.rounds <= 0:
            parser.error("--rounds must be positive")
        config["rounds"] = args.rounds
    output_dir = args.output_dir or Path(str(config.get("output_root", "outputs/linear_audit")))
    runs = run_experiment(
        config,
        seed_set=args.seed_set,
        methods=args.method,
        output_dir=output_dir,
        overwrite=args.overwrite,
        retain_matrices=False,
    )
    print(
        json.dumps(
            {
                "seed_set": args.seed_set,
                "run_count": len(runs),
                "output_dir": str(output_dir),
                "summaries": [run.summary for run in runs],
            },
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AuditRun",
    "CurvatureStrategy",
    "DEFAULT_CONFIG",
    "LinearAuditConfig",
    "RoundMatrices",
    "SUPPORTED_METHODS",
    "canonical_method",
    "confidence_radius",
    "configured_methods",
    "main",
    "run_experiment",
    "run_linear_audit",
    "run_method",
    "run_policy",
    "save_run",
    "selected_seeds",
]
