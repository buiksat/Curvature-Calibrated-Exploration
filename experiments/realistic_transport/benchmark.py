"""Dimension-general trajectory engine for the realistic transport benchmark.

Policies receive only :class:`PolicyRound` and the selected reward.  Truth and
potential-outcome arrays are read after action selection for evaluation only.
All numerical certificates in this module are float64 diagnostics of the
corresponding exact-arithmetic statements.
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .configuration import EXPECTED_METHODS, method_spec, MethodSpec
from .environment import (
    CONTROLLED_MISSPECIFIED_TASK,
    derive_seed,
    LABEL_TASK,
    PotentialOutcomeStream,
    smoothness_constant,
    TaskEnvironment,
)
from .model import scaled_tanh_gradient, scaled_tanh_mean
from .operators import (
    build_operational_nystrom,
    certified_cg_widths,
    CertifiedWidthMap,
    DenseSPDOperator,
    diagnose_operational_nystrom,
    diagnose_exact_width,
    exact_widths,
    FLOAT64_CERTIFICATE_DIAGNOSTIC,
    FixedSPDOperator,
    LowRankRidgeOperator,
    OperationalNystromApproximation,
    thompson_distance,
)


FloatArray = NDArray[np.float64]

THEOREM_METHODS: Final = frozenset(
    {
        "transport_exact_corrected_cholesky",
        "transport_exact_corrected_cg_1e-4",
        "transport_endpoint_corrected_cholesky",
        "frozen_reference_corrected_cholesky",
        *(
            method
            for method in EXPECTED_METHODS
            if method.startswith("transport_nystrom_")
        ),
    }
)


class BenchmarkError(RuntimeError):
    """Raised when a trajectory violates a deterministic benchmark invariant."""


def _finite(value: Any, *, name: str) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be numeric, not boolean")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _positive(value: Any, *, name: str) -> float:
    result = _finite(value, name=name)
    if result <= 0.0:
        raise ValueError(f"{name} must be positive")
    return result


def _positive_integer(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _nonnegative_integer(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def _vector(value: ArrayLike, *, name: str, dimension: int) -> FloatArray:
    result = np.asarray(value, dtype=np.float64)
    if result.shape != (dimension,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite vector of length {dimension}")
    return result


def _matrix(
    value: ArrayLike,
    *,
    name: str,
    columns: int,
    rows: int | None = None,
) -> FloatArray:
    result = np.asarray(value, dtype=np.float64)
    expected = (rows, columns) if rows is not None else None
    if result.ndim != 2 or result.shape[1] != columns:
        raise ValueError(f"{name} must have {columns} columns, got {result.shape}")
    if expected is not None and result.shape != expected:
        raise ValueError(f"{name} must have shape {expected}, got {result.shape}")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} contains a nonfinite value")
    return result


def _nested(source: Mapping[str, Any], path: str, default: Any) -> Any:
    value: Any = source
    for component in path.split("."):
        if not isinstance(value, Mapping) or component not in value:
            return default
        value = value[component]
    return value


@dataclass(frozen=True)
class OptimizerSpec:
    learning_rate: float
    steps_per_round: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "learning_rate",
            _positive(self.learning_rate, name="learning_rate"),
        )
        object.__setattr__(
            self,
            "steps_per_round",
            _positive_integer(self.steps_per_round, name="steps_per_round"),
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "OptimizerSpec":
        return cls(
            learning_rate=float(value["learning_rate"]),
            steps_per_round=int(value["steps_per_round"]),
        )


@dataclass(frozen=True)
class BenchmarkSettings:
    optimizer: OptimizerSpec
    ridge: float = 1.0
    training_ridge: float = 1.0
    theta_radius: float = 1.0
    reference_norm_bound: float = 1.0
    confidence_delta: float = 0.05
    linucb_alpha: float = 1.0
    prefixes: tuple[int, ...] = ()
    nystrom_oversampling: int = 8
    nystrom_pseudoinverse_multiplier: float = 64.0
    cg_absolute_tolerance: float = 0.0
    cg_max_iterations: int | None = None
    require_cg_convergence: bool = False
    diagnostic_checkpoints: tuple[int, ...] = (1, 100, 250, 500)

    def __post_init__(self) -> None:
        if not isinstance(self.optimizer, OptimizerSpec):
            raise TypeError("optimizer must be an OptimizerSpec")
        for name in (
            "ridge",
            "training_ridge",
            "theta_radius",
            "reference_norm_bound",
        ):
            object.__setattr__(self, name, _positive(getattr(self, name), name=name))
        delta = _finite(self.confidence_delta, name="confidence_delta")
        if not 0.0 < delta < 1.0:
            raise ValueError("confidence_delta must lie strictly between zero and one")
        object.__setattr__(self, "confidence_delta", delta)
        object.__setattr__(
            self, "linucb_alpha", _positive(self.linucb_alpha, name="linucb_alpha")
        )
        prefixes = tuple(
            sorted({_positive_integer(value, name="prefix") for value in self.prefixes})
        )
        object.__setattr__(self, "prefixes", prefixes)
        object.__setattr__(
            self,
            "nystrom_oversampling",
            _nonnegative_integer(
                self.nystrom_oversampling, name="nystrom_oversampling"
            ),
        )
        object.__setattr__(
            self,
            "nystrom_pseudoinverse_multiplier",
            _positive(
                self.nystrom_pseudoinverse_multiplier,
                name="nystrom_pseudoinverse_multiplier",
            ),
        )
        absolute = _finite(self.cg_absolute_tolerance, name="cg_absolute_tolerance")
        if absolute < 0.0:
            raise ValueError("cg_absolute_tolerance must be nonnegative")
        object.__setattr__(self, "cg_absolute_tolerance", absolute)
        if self.cg_max_iterations is not None:
            object.__setattr__(
                self,
                "cg_max_iterations",
                _positive_integer(self.cg_max_iterations, name="cg_max_iterations"),
            )
        checkpoints = tuple(
            sorted(
                {
                    _positive_integer(value, name="diagnostic checkpoint")
                    for value in self.diagnostic_checkpoints
                }
            )
        )
        object.__setattr__(self, "diagnostic_checkpoints", checkpoints)

    @classmethod
    def from_config(
        cls,
        config: Mapping[str, Any],
        *,
        optimizer: OptimizerSpec | Mapping[str, Any] | None = None,
        linucb_alpha: float | None = None,
    ) -> "BenchmarkSettings":
        if optimizer is None:
            raw_optimizer = _nested(
                config,
                "representation_update.development_optimizer",
                {"learning_rate": 1e-4, "steps_per_round": 5},
            )
            if not isinstance(raw_optimizer, Mapping):
                raise ValueError("optimizer configuration must be an object")
            optimizer_spec = OptimizerSpec.from_mapping(raw_optimizer)
        elif isinstance(optimizer, OptimizerSpec):
            optimizer_spec = optimizer
        else:
            optimizer_spec = OptimizerSpec.from_mapping(optimizer)
        configured_prefixes = _nested(config, "horizons.prefixes", ())
        max_iterations = _nested(config, "cg.maximum_iterations", None)
        if max_iterations == "feature_dimension":
            max_iterations = None
        return cls(
            optimizer=optimizer_spec,
            ridge=float(_nested(config, "model.ridge", 1.0)),
            training_ridge=float(_nested(config, "model.training_ridge", 1.0)),
            theta_radius=float(_nested(config, "model.theta_radius", 1.0)),
            reference_norm_bound=float(
                _nested(config, "model.reference_norm_bound", 1.0)
            ),
            confidence_delta=float(_nested(config, "model.confidence_delta", 0.05)),
            linucb_alpha=float(
                linucb_alpha
                if linucb_alpha is not None
                else _nested(config, "linucb.alpha", 1.0)
            ),
            prefixes=tuple(int(value) for value in configured_prefixes),
            nystrom_oversampling=int(_nested(config, "nystrom.oversampling", 8)),
            nystrom_pseudoinverse_multiplier=float(
                _nested(config, "nystrom.pseudoinverse_multiplier", 64.0)
            ),
            cg_absolute_tolerance=float(_nested(config, "cg.absolute_tolerance", 0.0)),
            cg_max_iterations=max_iterations,
            require_cg_convergence=bool(
                _nested(config, "cg.require_convergence", False)
            ),
            diagnostic_checkpoints=tuple(
                int(value)
                for value in _nested(
                    config, "diagnostics.checkpoints", (1, 100, 250, 500)
                )
            ),
        )


@dataclass(frozen=True)
class OptimizerDiagnostics:
    objective: float
    gradient_norm: float
    projection_occurred: bool
    displacement_norm: float


@dataclass
class SelectedHistory:
    """One policy's selected observations and predictable frozen state."""

    dimension: int
    ridge: float
    noise_proxy: float
    frozen_metric: FloatArray = field(init=False)
    frozen_rhs: FloatArray = field(init=False)
    selected_features: list[FloatArray] = field(default_factory=list)
    collection_thetas: list[FloatArray] = field(default_factory=list)
    collection_queries: list[FloatArray] = field(default_factory=list)
    pseudo_responses: list[float] = field(default_factory=list)
    rewards: list[float] = field(default_factory=list)
    linearization_envelopes: list[float] = field(default_factory=list)
    misspecification_envelopes: list[float] = field(default_factory=list)
    theta_mean: FloatArray = field(init=False)
    theta_scatter: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self.dimension = _positive_integer(self.dimension, name="dimension")
        self.ridge = _positive(self.ridge, name="ridge")
        self.noise_proxy = _positive(self.noise_proxy, name="noise_proxy")
        self.frozen_metric = self.ridge * np.eye(self.dimension, dtype=np.float64)
        self.frozen_rhs = np.zeros(self.dimension, dtype=np.float64)
        self.theta_mean = np.zeros(self.dimension, dtype=np.float64)

    @property
    def length(self) -> int:
        return len(self.rewards)

    @property
    def feature_array(self) -> FloatArray:
        if not self.selected_features:
            return np.empty((0, self.dimension), dtype=np.float64)
        return np.stack(self.selected_features, axis=0)

    @property
    def reward_array(self) -> FloatArray:
        return np.asarray(self.rewards, dtype=np.float64)

    @property
    def historical_error_energy(self) -> float:
        linearization = np.asarray(self.linearization_envelopes, dtype=np.float64)
        misspecification = np.asarray(self.misspecification_envelopes, dtype=np.float64)
        return float(np.sum((linearization + misspecification) ** 2))

    @property
    def historical_linearization_radius(self) -> float:
        values = np.asarray(self.linearization_envelopes, dtype=np.float64)
        return float(np.linalg.norm(values) / self.noise_proxy)

    @property
    def historical_misspecification_radius_increment(self) -> float:
        total = math.sqrt(self.historical_error_energy) / self.noise_proxy
        return float(total - self.historical_linearization_radius)

    def theta_hat_linear(self) -> FloatArray:
        return np.asarray(
            np.linalg.solve(self.frozen_metric, self.frozen_rhs), dtype=np.float64
        )

    def information_gain(self) -> float:
        sign, logdet = np.linalg.slogdet(self.frozen_metric / self.ridge)
        if sign <= 0.0 or not math.isfinite(float(logdet)):
            raise BenchmarkError("frozen metric does not have a finite positive logdet")
        tolerance = (
            4096.0
            * np.finfo(np.float64).eps
            * self.dimension
            * max(1.0, abs(float(logdet)))
        )
        if logdet < -tolerance:
            raise BenchmarkError("frozen information gain is materially negative")
        return float(max(0.0, logdet))

    def path_q(self, theta: ArrayLike) -> float:
        current = _vector(theta, name="theta", dimension=self.dimension)
        if self.length == 0:
            return 0.0
        displacement = current - self.theta_mean
        result = self.theta_scatter + self.length * float(displacement @ displacement)
        tolerance = 256.0 * np.finfo(np.float64).eps * max(1.0, abs(result))
        if result < -tolerance:
            raise BenchmarkError("Welford path statistic is materially negative")
        return float(max(0.0, result))

    def current_replay_gradients(self, theta: ArrayLike, width: float) -> FloatArray:
        if self.length == 0:
            return np.empty((0, self.dimension), dtype=np.float64)
        return np.asarray(
            scaled_tanh_gradient(theta, self.feature_array, width) / self.noise_proxy,
            dtype=np.float64,
        )

    def current_metric(self, theta: ArrayLike, width: float) -> FloatArray:
        replay = self.current_replay_gradients(theta, width)
        return np.asarray(
            self.ridge * np.eye(self.dimension, dtype=np.float64) + replay.T @ replay,
            dtype=np.float64,
        )

    def append(
        self,
        *,
        feature: ArrayLike,
        collection_theta: ArrayLike,
        collection_query: ArrayLike,
        pseudo_response: float,
        reward: float,
        linearization_envelope: float,
        misspecification_envelope: float,
    ) -> None:
        selected_feature = _vector(
            feature, name="selected feature", dimension=self.dimension
        ).copy()
        theta = _vector(
            collection_theta, name="collection theta", dimension=self.dimension
        ).copy()
        query = _vector(
            collection_query, name="collection query", dimension=self.dimension
        ).copy()
        pseudo_response = _finite(pseudo_response, name="pseudo_response")
        reward = _finite(reward, name="reward")
        linearization = _finite(linearization_envelope, name="linearization_envelope")
        misspecification = _finite(
            misspecification_envelope, name="misspecification_envelope"
        )
        if linearization < 0.0 or misspecification < 0.0:
            raise ValueError("historical envelopes must be nonnegative")

        variance = self.noise_proxy * self.noise_proxy
        self.frozen_metric += np.outer(query, query) / variance
        self.frozen_rhs += query * pseudo_response / variance
        previous_count = self.length
        if previous_count == 0:
            self.theta_mean = theta.copy()
        else:
            difference = theta - self.theta_mean
            next_count = previous_count + 1
            next_mean = self.theta_mean + difference / float(next_count)
            self.theta_scatter += float(difference @ (theta - next_mean))
            self.theta_mean = next_mean
        self.selected_features.append(selected_feature)
        self.collection_thetas.append(theta)
        self.collection_queries.append(query)
        self.pseudo_responses.append(pseudo_response)
        self.rewards.append(reward)
        self.linearization_envelopes.append(linearization)
        self.misspecification_envelopes.append(misspecification)


@dataclass
class LinearBanditState:
    dimension: int
    ridge: float
    metric: FloatArray = field(init=False)
    rhs: FloatArray = field(init=False)

    def __post_init__(self) -> None:
        self.dimension = _positive_integer(self.dimension, name="dimension")
        self.ridge = _positive(self.ridge, name="linucb ridge")
        self.metric = self.ridge * np.eye(self.dimension, dtype=np.float64)
        self.rhs = np.zeros(self.dimension, dtype=np.float64)

    def score(
        self, features: FloatArray, alpha: float
    ) -> tuple[FloatArray, FloatArray, FloatArray]:
        estimate = np.linalg.solve(self.metric, self.rhs)
        operator = DenseSPDOperator(self.metric)
        widths = exact_widths(operator, features)
        centers = np.asarray(features @ estimate, dtype=np.float64)
        scores = np.asarray(centers + alpha * widths, dtype=np.float64)
        return centers, widths, scores

    def append(self, feature: FloatArray, reward: float) -> None:
        self.metric += np.outer(feature, feature)
        self.rhs += feature * reward


@dataclass(frozen=True)
class TrajectoryResult:
    task: str
    method: str
    seed: int
    rounds: tuple[dict[str, Any], ...]
    prefix_summaries: dict[int, dict[str, Any]]
    summary: dict[str, Any]


@dataclass(frozen=True)
class TuningResult:
    task: str
    seed: int
    optimizer: OptimizerSpec
    rounds: tuple[dict[str, Any], ...]
    summary: dict[str, Any]


def linearization_envelope(
    theta: ArrayLike,
    *,
    reference_norm_bound: float,
    lipschitz_mean: float,
) -> float:
    parameters = np.asarray(theta, dtype=np.float64)
    if parameters.ndim != 1 or not np.all(np.isfinite(parameters)):
        raise ValueError("theta must be a finite vector")
    bound = _positive(reference_norm_bound, name="reference_norm_bound")
    lipschitz = _finite(lipschitz_mean, name="lipschitz_mean")
    if lipschitz < 0.0:
        raise ValueError("lipschitz_mean must be nonnegative")
    return float(0.5 * lipschitz * (bound + np.linalg.norm(parameters)) ** 2)


def corrected_center(
    theta: ArrayLike,
    theta_hat_linear: ArrayLike,
    action_features: ArrayLike,
    *,
    width: float,
) -> FloatArray:
    parameters = np.asarray(theta, dtype=np.float64)
    estimate = np.asarray(theta_hat_linear, dtype=np.float64)
    features = np.asarray(action_features, dtype=np.float64)
    if parameters.ndim != 1 or estimate.shape != parameters.shape:
        raise ValueError("theta and theta_hat_linear must be equal-length vectors")
    features = _matrix(
        features,
        name="action_features",
        columns=parameters.size,
    )
    means = np.asarray(scaled_tanh_mean(parameters, features, width), dtype=np.float64)
    queries = scaled_tanh_gradient(parameters, features, width)
    return np.asarray(means + queries @ (estimate - parameters), dtype=np.float64)


def tangent_center(
    theta: ArrayLike,
    theta_hat_linear: ArrayLike,
    action_features: ArrayLike,
    *,
    width: float,
) -> FloatArray:
    parameters = np.asarray(theta, dtype=np.float64)
    estimate = np.asarray(theta_hat_linear, dtype=np.float64)
    features = np.asarray(action_features, dtype=np.float64)
    if parameters.ndim != 1 or estimate.shape != parameters.shape:
        raise ValueError("theta and theta_hat_linear must be equal-length vectors")
    features = _matrix(
        features,
        name="action_features",
        columns=parameters.size,
    )
    queries = scaled_tanh_gradient(parameters, features, width)
    return np.asarray(queries @ estimate, dtype=np.float64)


def corrected_confidence_radius(
    information_gain: float,
    *,
    delta: float,
    ridge: float,
    reference_norm_bound: float,
    historical_error_energy: float,
    noise_proxy: float,
) -> tuple[float, float, float]:
    gamma = _finite(information_gain, name="information_gain")
    energy = _finite(historical_error_energy, name="historical_error_energy")
    if gamma < 0.0 or energy < 0.0:
        raise ValueError(
            "information gain and historical error energy must be nonnegative"
        )
    probability = _finite(delta, name="delta")
    if not 0.0 < probability < 1.0:
        raise ValueError("delta must lie strictly between zero and one")
    statistical = math.sqrt(gamma + 2.0 * math.log(1.0 / probability))
    statistical += math.sqrt(_positive(ridge, name="ridge")) * _positive(
        reference_norm_bound, name="reference_norm_bound"
    )
    historical = math.sqrt(energy) / _positive(noise_proxy, name="noise_proxy")
    return float(statistical + historical), float(statistical), float(historical)


def projected_full_batch_update(
    history: SelectedHistory,
    theta: ArrayLike,
    *,
    width: float,
    optimizer: OptimizerSpec,
    training_ridge: float,
    theta_radius: float,
) -> tuple[FloatArray, OptimizerDiagnostics]:
    current = _vector(theta, name="theta", dimension=history.dimension).copy()
    initial = current.copy()
    variance = history.noise_proxy * history.noise_proxy
    damping = _positive(training_ridge, name="training_ridge")
    radius = _positive(theta_radius, name="theta_radius")
    features = history.feature_array
    rewards = history.reward_array
    if history.length == 0:
        raise ValueError("projected update requires at least one observation")
    for _ in range(optimizer.steps_per_round):
        means = np.asarray(scaled_tanh_mean(current, features, width), dtype=np.float64)
        queries = scaled_tanh_gradient(current, features, width)
        gradient = queries.T @ (means - rewards) / variance + damping * current
        current = np.asarray(current - optimizer.learning_rate * gradient)
        if not np.all(np.isfinite(current)):
            raise BenchmarkError("optimizer produced a nonfinite iterate")
    norm = float(np.linalg.norm(current))
    projected = norm > radius
    if projected:
        current *= radius / norm
    means = np.asarray(scaled_tanh_mean(current, features, width), dtype=np.float64)
    queries = scaled_tanh_gradient(current, features, width)
    residuals = means - rewards
    objective = 0.5 * float(residuals @ residuals) / variance
    objective += 0.5 * damping * float(current @ current)
    gradient = queries.T @ residuals / variance + damping * current
    if not math.isfinite(objective) or not np.all(np.isfinite(gradient)):
        raise BenchmarkError("optimizer diagnostics are nonfinite")
    return current, OptimizerDiagnostics(
        objective=float(objective),
        gradient_norm=float(np.linalg.norm(gradient)),
        projection_occurred=projected,
        displacement_norm=float(np.linalg.norm(current - initial)),
    )


def _path_bound(
    history: SelectedHistory,
    theta: FloatArray,
    *,
    lipschitz_gradient: float,
) -> tuple[float, float]:
    q_value = history.path_q(theta)
    d_q = 2.0 * lipschitz_gradient * math.sqrt(q_value)
    d_q /= history.noise_proxy * math.sqrt(history.ridge)
    if not math.isfinite(d_q):
        raise BenchmarkError("path certificate is nonfinite")
    return q_value, float(d_q)


def _safe_exp(value: float) -> float:
    if value > math.log(np.finfo(np.float64).max):
        raise BenchmarkError("transport exponential overflowed")
    return float(math.exp(value))


def _smallest_maximizer(scores: FloatArray) -> tuple[int, int, float]:
    if scores.ndim != 1 or scores.size < 2 or not np.all(np.isfinite(scores)):
        raise BenchmarkError("scores must be a finite vector with at least two actions")
    maximum = float(np.max(scores))
    tied = np.flatnonzero(scores == maximum)
    action = int(tied[0])
    competitors = np.delete(scores, action)
    margin = maximum - float(np.max(competitors))
    return action, int(tied.size), float(margin)


def _nystrom_diagnostics(
    approximation: OperationalNystromApproximation,
) -> dict[str, Any]:
    return {
        "nystrom_target_rank": approximation.target_rank,
        "nystrom_numerical_rank": approximation.numerical_rank,
        "nystrom_sketch_size": approximation.sketch_size,
        "nystrom_sketch_seed": approximation.sketch_seed,
        "nystrom_sketch_digest": approximation.sketch_digest,
        "nystrom_pseudoinverse_cutoff": approximation.pseudoinverse_cutoff,
        "nystrom_pseudoinverse_rank": approximation.pseudoinverse_rank,
        "nystrom_trace_tail": approximation.trace_tail,
        "nystrom_operator_tail": None,
        "nystrom_trace_tail_over_operator_tail": None,
        "nystrom_operational_kappa_minus": approximation.operational_kappa_minus,
        "nystrom_operational_kappa_plus": approximation.operational_kappa_plus,
        "nystrom_oracle_kappa_minus_operator_tail": None,
        "nystrom_oracle_generalized_kappa_minus": None,
        "nystrom_oracle_generalized_kappa_plus": None,
        "nystrom_effective_rank": None,
        "nystrom_retained_trace_fraction": approximation.retained_trace_fraction,
        "nystrom_spectral_tail_fraction": None,
        "nystrom_decomposition_error_norm": None,
        "nystrom_construction_seconds": approximation.construction_seconds,
        "nystrom_diagnostic_seconds": 0.0,
        "nystrom_operator_storage_bytes": approximation.operator_storage_bytes,
        "nystrom_working_storage_bytes": approximation.working_storage_bytes,
        "nystrom_roundoff_correction_count": len(approximation.roundoff_corrections),
    }


def _empty_nystrom_diagnostics() -> dict[str, Any]:
    return {
        "nystrom_target_rank": None,
        "nystrom_numerical_rank": None,
        "nystrom_sketch_size": None,
        "nystrom_sketch_seed": None,
        "nystrom_sketch_digest": None,
        "nystrom_pseudoinverse_cutoff": None,
        "nystrom_pseudoinverse_rank": None,
        "nystrom_trace_tail": None,
        "nystrom_operator_tail": None,
        "nystrom_trace_tail_over_operator_tail": None,
        "nystrom_operational_kappa_minus": None,
        "nystrom_operational_kappa_plus": None,
        "nystrom_oracle_kappa_minus_operator_tail": None,
        "nystrom_oracle_generalized_kappa_minus": None,
        "nystrom_oracle_generalized_kappa_plus": None,
        "nystrom_effective_rank": None,
        "nystrom_retained_trace_fraction": None,
        "nystrom_spectral_tail_fraction": None,
        "nystrom_decomposition_error_norm": None,
        "nystrom_construction_seconds": 0.0,
        "nystrom_diagnostic_seconds": 0.0,
        "nystrom_operator_storage_bytes": 0,
        "nystrom_working_storage_bytes": 0,
        "nystrom_roundoff_correction_count": 0,
    }


def _add_nystrom_checkpoint_diagnostics(
    metrics: dict[str, Any],
    approximation: OperationalNystromApproximation,
    replay_gradients: FloatArray,
) -> float:
    diagnostic = diagnose_operational_nystrom(approximation, replay_gradients)
    metrics.update(
        {
            "nystrom_operator_tail": diagnostic.operator_tail,
            "nystrom_trace_tail_over_operator_tail": (
                diagnostic.trace_tail_over_operator_tail
            ),
            "nystrom_oracle_kappa_minus_operator_tail": (
                diagnostic.oracle_kappa_minus_operator_tail
            ),
            "nystrom_oracle_generalized_kappa_minus": (
                diagnostic.oracle_generalized_kappa_minus
            ),
            "nystrom_oracle_generalized_kappa_plus": (
                diagnostic.oracle_generalized_kappa_plus
            ),
            "nystrom_effective_rank": diagnostic.effective_rank,
            "nystrom_spectral_tail_fraction": diagnostic.spectral_tail_fraction,
            "nystrom_decomposition_error_norm": (diagnostic.decomposition_error_norm),
            "nystrom_diagnostic_seconds": diagnostic.elapsed_seconds,
        }
    )
    return diagnostic.elapsed_seconds


def _cg_metrics(
    operator: FixedSPDOperator,
    width_map: CertifiedWidthMap,
    selected_action: int,
    *,
    exact_diagnostic: bool,
) -> dict[str, Any]:
    selected = width_map.selected(selected_action)
    exact_diagnostics = (
        tuple(
            diagnose_exact_width(operator, certificate)
            for certificate in width_map.certificates
        )
        if exact_diagnostic
        else None
    )
    exact = (
        exact_diagnostics[selected_action] if exact_diagnostics is not None else None
    )
    return {
        "solver_width_upper": selected.upper_width,
        "solver_width_lower": selected.lower_width,
        "solver_alpha": selected.sharpness_factor,
        "solver_exact_width": exact.exact_width if exact is not None else None,
        "solver_upper_over_exact": (
            exact.upper_over_exact if exact is not None else None
        ),
        "solver_exact_over_lower": (
            exact.exact_over_lower if exact is not None else None
        ),
        "solver_true_residual_norm": selected.cg.true_residual_norm,
        "solver_recursive_residual_norm": selected.cg.recursive_residual_norm,
        "solver_residual_discrepancy_norm": selected.cg.residual_discrepancy_norm,
        "solver_relative_true_residual_norm": selected.cg.relative_true_residual_norm,
        "solver_iterations_selected": selected.cg.iterations,
        "solver_iterations_all_actions": width_map.total_iterations,
        "solver_algorithm_matvecs_all_actions": (
            width_map.total_algorithm_matvec_count
        ),
        "solver_audit_matvecs_all_actions": width_map.total_audit_matvec_count,
        "solver_converged_selected": selected.cg.converged,
        "solver_all_actions_converged": all(
            certificate.cg.converged for certificate in width_map.certificates
        ),
        "solver_termination_reason": selected.cg.termination_reason,
        "solver_upper_widths_all_actions": width_map.upper_widths.tolist(),
        "solver_lower_widths_all_actions": width_map.lower_widths.tolist(),
        "solver_alphas_all_actions": width_map.sharpness_factors.tolist(),
        "solver_iterations_by_action": [
            certificate.cg.iterations for certificate in width_map.certificates
        ],
        "solver_true_residuals_by_action": [
            certificate.cg.true_residual_norm for certificate in width_map.certificates
        ],
        "solver_recursive_residuals_by_action": [
            certificate.cg.recursive_residual_norm
            for certificate in width_map.certificates
        ],
        "solver_exact_widths_all_actions": (
            [item.exact_width for item in exact_diagnostics]
            if exact_diagnostics is not None
            else None
        ),
        "solver_upper_over_exact_all_actions": (
            [item.upper_over_exact for item in exact_diagnostics]
            if exact_diagnostics is not None
            else None
        ),
        "solver_seconds_all_actions": float(
            sum(
                certificate.cg.elapsed_seconds for certificate in width_map.certificates
            )
        ),
        "solver_post_selection_refinement": False,
    }


def _exact_solver_metrics(
    width: float, *, elapsed_seconds: float = 0.0
) -> dict[str, Any]:
    positive_ratio = 1.0 if width > 0.0 else None
    return {
        "solver_width_upper": width,
        "solver_width_lower": width,
        "solver_alpha": 1.0,
        "solver_exact_width": width,
        "solver_upper_over_exact": positive_ratio,
        "solver_exact_over_lower": positive_ratio,
        "solver_true_residual_norm": 0.0,
        "solver_recursive_residual_norm": 0.0,
        "solver_residual_discrepancy_norm": 0.0,
        "solver_relative_true_residual_norm": 0.0,
        "solver_iterations_selected": 0,
        "solver_iterations_all_actions": 0,
        "solver_algorithm_matvecs_all_actions": 0,
        "solver_audit_matvecs_all_actions": 0,
        "solver_converged_selected": True,
        "solver_all_actions_converged": True,
        "solver_termination_reason": "exact_cholesky",
        "solver_upper_widths_all_actions": None,
        "solver_lower_widths_all_actions": None,
        "solver_alphas_all_actions": None,
        "solver_iterations_by_action": None,
        "solver_true_residuals_by_action": None,
        "solver_recursive_residuals_by_action": None,
        "solver_exact_widths_all_actions": None,
        "solver_upper_over_exact_all_actions": None,
        "solver_seconds_all_actions": float(elapsed_seconds),
        "solver_post_selection_refinement": False,
    }


def _no_solver_metrics() -> dict[str, Any]:
    return {
        "solver_width_upper": None,
        "solver_width_lower": None,
        "solver_alpha": None,
        "solver_exact_width": None,
        "solver_upper_over_exact": None,
        "solver_exact_over_lower": None,
        "solver_true_residual_norm": None,
        "solver_recursive_residual_norm": None,
        "solver_residual_discrepancy_norm": None,
        "solver_relative_true_residual_norm": None,
        "solver_iterations_selected": 0,
        "solver_iterations_all_actions": 0,
        "solver_algorithm_matvecs_all_actions": 0,
        "solver_audit_matvecs_all_actions": 0,
        "solver_converged_selected": None,
        "solver_all_actions_converged": None,
        "solver_termination_reason": "not_applicable",
        "solver_upper_widths_all_actions": None,
        "solver_lower_widths_all_actions": None,
        "solver_alphas_all_actions": None,
        "solver_iterations_by_action": None,
        "solver_true_residuals_by_action": None,
        "solver_recursive_residuals_by_action": None,
        "solver_exact_widths_all_actions": None,
        "solver_upper_over_exact_all_actions": None,
        "solver_seconds_all_actions": 0.0,
        "solver_post_selection_refinement": False,
    }


def _current_truth_diagnostics(
    environment: TaskEnvironment,
    context: FloatArray,
    true_means: FloatArray,
    model_means: FloatArray,
    queries: FloatArray,
    theta: FloatArray,
) -> tuple[FloatArray | None, FloatArray | None]:
    theta_star = environment.theta_star
    if theta_star is None:
        return None, None
    reference = _vector(theta_star, name="theta_star", dimension=theta.size)
    base_means = np.asarray(
        scaled_tanh_mean(
            reference, environment.feature_matrix(context), environment.width
        ),
        dtype=np.float64,
    )
    taylor = np.asarray(
        base_means - model_means - queries @ (reference - theta),
        dtype=np.float64,
    )
    misspecification = np.asarray(true_means - base_means, dtype=np.float64)
    return taylor, misspecification


def _prefix_summary(
    *,
    environment: TaskEnvironment,
    method: str,
    records: Sequence[Mapping[str, Any]],
    cumulative_regret: float,
    cumulative_trivial_bound: float,
    prefix_reference_coverage: bool,
    prefix_method_optimism: bool,
    cumulative_accuracy: int,
    sharp_rhs: float | None,
    simple_rhs: float | None,
) -> dict[str, Any]:
    count = len(records)
    return {
        "task": environment.task_name,
        "method": method,
        "rounds": count,
        "seed": int(records[-1]["seed"]),
        "cumulative_pseudo_regret": float(cumulative_regret),
        "action_accuracy": (
            cumulative_accuracy / count if environment.task_name == LABEL_TASK else None
        ),
        "simultaneous_reference_confidence": prefix_reference_coverage,
        "simultaneous_method_optimism": prefix_method_optimism,
        "simultaneous_transport_optimism": (
            prefix_method_optimism if method in THEOREM_METHODS else None
        ),
        "confidence_role": str(records[-1]["confidence_role"]),
        "theorem_applicable": bool(records[-1]["theorem_applicable"]),
        "sharp_theorem_rhs": sharp_rhs,
        "simple_theorem_rhs": simple_rhs,
        "cumulative_trivial_regret_bound": float(cumulative_trivial_bound),
        "theorem_bound_nonvacuous": (
            sharp_rhs < cumulative_trivial_bound if sharp_rhs is not None else None
        ),
        "fraction_bonus_below_true_action_gap": float(
            np.mean([bool(record["bonus_below_true_action_gap"]) for record in records])
        ),
        "fraction_bonus_exceeds_reward_range": float(
            np.mean(
                [
                    float(record["selected_confidence_bonus"])
                    > float(record["reward_range"])
                    for record in records
                ]
            )
        ),
        "zero_regret": cumulative_regret == 0.0,
        "sharp_rhs_over_regret": (
            sharp_rhs / cumulative_regret
            if sharp_rhs is not None and cumulative_regret > 0.0
            else None
        ),
        "total_algorithm_seconds": float(
            sum(float(record["algorithm_seconds"]) for record in records)
        ),
        "total_operator_construction_seconds": float(
            sum(float(record["operator_construction_seconds"]) for record in records)
        ),
        "total_transport_certificate_seconds": float(
            sum(float(record["transport_certificate_seconds"]) for record in records)
        ),
        "total_action_scoring_seconds": float(
            sum(float(record["action_scoring_seconds"]) for record in records)
        ),
        "total_representation_update_seconds": float(
            sum(float(record["representation_update_seconds"]) for record in records)
        ),
        "total_diagnostic_seconds": float(
            sum(float(record["diagnostic_seconds"]) for record in records)
        ),
        "total_end_to_end_round_seconds": float(
            sum(float(record["end_to_end_round_seconds"]) for record in records)
        ),
        "total_cg_iterations": int(
            sum(int(record["solver_iterations_all_actions"]) for record in records)
        ),
        "total_cg_matvecs": int(
            sum(
                int(record["solver_algorithm_matvecs_all_actions"])
                + int(record["solver_audit_matvecs_all_actions"])
                for record in records
            )
        ),
        "total_solver_seconds": float(
            sum(float(record["solver_seconds_all_actions"]) for record in records)
        ),
        "maximum_logical_operator_bytes": int(
            max(int(record["operator_storage_bytes"]) for record in records)
        ),
        "floating_point_checks_are_verified_certificates": False,
        "analytic_certificate_valid_in_exact_arithmetic": bool(
            records[-1]["analytic_certificate_valid_in_exact_arithmetic"]
        ),
        "float64_diagnostic_pass": True,
        "verified_numerical_certificate": False,
        "certificate_class": FLOAT64_CERTIFICATE_DIAGNOSTIC,
    }


def run_policy_trajectory(
    environment: TaskEnvironment,
    stream: PotentialOutcomeStream,
    method: str,
    settings: BenchmarkSettings,
) -> TrajectoryResult:
    """Run one policy with its own selected history and representation path."""

    spec = method_spec(method)
    if not isinstance(settings, BenchmarkSettings):
        raise TypeError("settings must be a BenchmarkSettings instance")
    if stream.task_name != environment.task_name:
        raise ValueError("stream and environment tasks differ")
    rounds = int(stream.rounds)
    if rounds <= 0:
        raise ValueError("stream must contain at least one round")
    dimension = int(environment.feature_dimension)
    action_count = int(environment.action_count)
    if dimension <= 0 or action_count < 2:
        raise ValueError("environment dimensions are invalid")
    if spec.rank is not None and spec.rank > dimension:
        raise ValueError(
            f"method rank {spec.rank} exceeds feature dimension {dimension}"
        )
    prefixes = tuple(value for value in settings.prefixes if value <= rounds)
    report_prefixes = set(prefixes) | {rounds}

    history = SelectedHistory(dimension, settings.ridge, environment.noise_proxy)
    linear_state = LinearBanditState(dimension, settings.ridge)
    theta = np.zeros(dimension, dtype=np.float64)
    lipschitz = smoothness_constant(environment.feature_map.feature_bound) / math.sqrt(
        environment.width
    )
    historical_misspecification = (
        0.0
        if environment.historical_misspecification_envelope is None
        else float(environment.historical_misspecification_envelope)
    )
    current_misspecification = (
        0.0
        if environment.current_misspecification_envelope is None
        else float(environment.current_misspecification_envelope)
    )
    theorem_applicable = bool(
        environment.theorem_applicable and method in THEOREM_METHODS
    )
    sketch_seed = (
        derive_seed(
            int(stream.seed),
            "realistic_transport/nystrom/v1",
            environment.task_name,
            int(spec.rank),
        )
        if spec.rank is not None
        else None
    )

    records: list[dict[str, Any]] = []
    prefix_summaries: dict[int, dict[str, Any]] = {}
    cumulative_regret = 0.0
    cumulative_trivial_bound = 0.0
    cumulative_accuracy = 0
    cumulative_width_square = 0.0
    cumulative_sharp_coefficient_square = 0.0
    cumulative_simple_coefficient_square = 0.0
    cumulative_current_bias = 0.0
    prefix_reference_coverage = True
    prefix_method_optimism = True
    sharp_rhs: float | None = None
    simple_rhs: float | None = None

    for round_index in range(rounds):
        round_started = time.perf_counter()
        diagnostic_checkpoint = (
            round_index + 1 in set(settings.diagnostic_checkpoints) | report_prefixes
        )
        diagnostic_seconds = 0.0
        update_seconds = 0.0
        policy_round = stream.policy_round(round_index)
        context = _vector(
            policy_round.context,
            name="policy context",
            dimension=environment.context_dimension,
        )
        features = _matrix(
            policy_round.action_features,
            name="action features",
            rows=action_count,
            columns=dimension,
        )
        nystrom: OperationalNystromApproximation | None = None
        width_map: CertifiedWidthMap | None = None
        algorithm_operator: FixedSPDOperator | None = None
        current_operator: DenseSPDOperator | None = None
        operator_metrics = _empty_nystrom_diagnostics()

        if method == "linucb_fixed_features":
            operator_started = time.perf_counter()
            centers, linucb_widths, scores = linear_state.score(
                features, settings.linucb_alpha
            )
            width_solve_seconds = time.perf_counter() - operator_started
            operator_construction_seconds = 0.0
            transport_certificate_seconds = 0.0
            operator_seconds = width_solve_seconds
            scoring_started = time.perf_counter()
            common_seconds = 0.0
            corrected_centers = None
            tangent_centers = None
            model_means = None
            queries = None
            beta = None
            beta_statistical = None
            beta_historical = None
            current_linearization = None
            current_bias = 0.0
            gamma_before = None
            q_value = None
            d_q = None
            endpoint = None
            kappa_minus = None
            kappa_plus = None
            transport_distance = None
            score_widths = None
            frozen_widths = None
            current_widths = None
            selected_alpha = None
        else:
            frozen_metric_before = history.frozen_metric.copy()
            frozen_operator = DenseSPDOperator(history.frozen_metric)
            theta_hat = history.theta_hat_linear()
            ridge_normal_equation_residual = float(
                np.linalg.norm(frozen_metric_before @ theta_hat - history.frozen_rhs)
            )
            model_means = np.asarray(
                scaled_tanh_mean(theta, features, environment.width), dtype=np.float64
            )
            queries = scaled_tanh_gradient(theta, features, environment.width)
            corrected_centers = corrected_center(
                theta, theta_hat, features, width=environment.width
            )
            tangent_centers = tangent_center(
                theta, theta_hat, features, width=environment.width
            )
            centers = tangent_centers if spec.center == "tangent" else corrected_centers
            gamma_before = history.information_gain()
            historical_error_energy_before = history.historical_error_energy
            historical_linearization_radius = history.historical_linearization_radius
            historical_misspecification_radius_increment = (
                history.historical_misspecification_radius_increment
            )
            beta, beta_statistical, beta_historical = corrected_confidence_radius(
                gamma_before,
                delta=settings.confidence_delta,
                ridge=settings.ridge,
                reference_norm_bound=settings.reference_norm_bound,
                historical_error_energy=historical_error_energy_before,
                noise_proxy=environment.noise_proxy,
            )
            current_linearization = linearization_envelope(
                theta,
                reference_norm_bound=settings.reference_norm_bound,
                lipschitz_mean=lipschitz,
            )
            current_bias = current_linearization + current_misspecification
            q_value, d_q = _path_bound(history, theta, lipschitz_gradient=lipschitz)
            common_seconds = time.perf_counter() - round_started
            direct_q_value = None
            welford_q_residual = None
            replay_gradients: FloatArray | None = None
            frozen_widths: FloatArray | None = None
            current_widths: FloatArray | None = None
            endpoint: float | None = None
            kappa_minus = 1.0
            kappa_plus = 1.0
            transport_distance = 0.0
            score_widths: FloatArray | None = None

            operator_started = time.perf_counter()
            operator_construction_seconds = 0.0
            width_solve_seconds = 0.0
            transport_certificate_seconds = 0.0
            if spec.metric == "frozen":
                algorithm_operator = frozen_operator
                width_started = time.perf_counter()
                frozen_widths = exact_widths(frozen_operator, queries)
                width_solve_seconds += time.perf_counter() - width_started
                score_widths = frozen_widths
            elif spec.metric == "nystrom":
                assert spec.rank is not None and sketch_seed is not None
                replay_gradients = history.current_replay_gradients(
                    theta, environment.width
                )
                nystrom = build_operational_nystrom(
                    replay_gradients,
                    target_rank=spec.rank,
                    sketch_seed=sketch_seed,
                    ridge=settings.ridge,
                    oversampling=settings.nystrom_oversampling,
                    pseudoinverse_multiplier=(
                        settings.nystrom_pseudoinverse_multiplier
                    ),
                )
                algorithm_operator = nystrom.operator
                operator_construction_seconds = nystrom.construction_seconds
                kappa_minus = nystrom.operational_kappa_minus
                kappa_plus = nystrom.operational_kappa_plus
                operator_metrics.update(_nystrom_diagnostics(nystrom))
            elif spec.metric == "current_exact":
                construction_started = time.perf_counter()
                replay_gradients = history.current_replay_gradients(
                    theta, environment.width
                )
                current_matrix = np.asarray(
                    settings.ridge * np.eye(dimension)
                    + replay_gradients.T @ replay_gradients,
                    dtype=np.float64,
                )
                current_operator = DenseSPDOperator(current_matrix)
                algorithm_operator = current_operator
                operator_construction_seconds = (
                    time.perf_counter() - construction_started
                )
                if spec.solver == "cholesky":
                    width_started = time.perf_counter()
                    current_widths = exact_widths(current_operator, queries)
                    width_solve_seconds += time.perf_counter() - width_started
                    score_widths = current_widths

            if spec.transport == "operational":
                transport_distance = d_q
            elif spec.transport == "endpoint_oracle":
                assert current_operator is not None
                transport_started = time.perf_counter()
                endpoint = thompson_distance(frozen_operator, current_operator)
                transport_certificate_seconds = time.perf_counter() - transport_started
                transport_distance = endpoint
            elif spec.transport in {"reference", "none"}:
                transport_distance = 0.0
            else:
                raise BenchmarkError(f"unsupported transport mode {spec.transport!r}")

            if spec.solver == "cg":
                if algorithm_operator is None or spec.cg_tolerance is None:
                    raise BenchmarkError(
                        "CG method is missing its fixed operator or tolerance"
                    )
                upper_eigenvalue_bound = (
                    settings.ridge + algorithm_operator.trace_hessian
                    if isinstance(algorithm_operator, LowRankRidgeOperator)
                    else settings.ridge
                    + float(
                        np.trace(algorithm_operator.to_dense())
                        - settings.ridge * dimension
                    )
                )
                width_started = time.perf_counter()
                width_map = certified_cg_widths(
                    algorithm_operator,
                    queries,
                    lower_eigenvalue_bound=settings.ridge,
                    upper_eigenvalue_bound=upper_eigenvalue_bound,
                    rel_tol=spec.cg_tolerance,
                    max_iterations=settings.cg_max_iterations or dimension,
                    absolute_tolerance=settings.cg_absolute_tolerance,
                    require_convergence=settings.require_cg_convergence,
                )
                width_solve_seconds += time.perf_counter() - width_started
                score_widths = width_map.upper_widths
            elif spec.solver == "cholesky":
                if algorithm_operator is None:
                    raise BenchmarkError("Cholesky method is missing its operator")
                if score_widths is None:
                    width_started = time.perf_counter()
                    score_widths = exact_widths(algorithm_operator, queries)
                    width_solve_seconds += time.perf_counter() - width_started
            elif spec.solver != "none":
                raise BenchmarkError(f"unsupported solver {spec.solver!r}")

            operator_seconds = (
                operator_construction_seconds
                + width_solve_seconds
                + transport_certificate_seconds
            )
            scoring_started = time.perf_counter()
            if method == "greedy_corrected":
                scores = corrected_centers.copy()
                score_widths = np.zeros(action_count, dtype=np.float64)
            else:
                assert score_widths is not None
                inflation = _safe_exp(0.5 * float(transport_distance))
                bonus = beta * inflation * math.sqrt(float(kappa_plus)) * score_widths
                scores = np.asarray(centers + bonus + current_bias, dtype=np.float64)

        action, tie_count, score_margin = _smallest_maximizer(scores)
        scoring_seconds = time.perf_counter() - scoring_started
        selected_score = float(scores[action])

        if method != "linucb_fixed_features":
            diagnostics_started = time.perf_counter()
            assert queries is not None
            if frozen_widths is None:
                frozen_widths = exact_widths(frozen_operator, queries)
            direct_q_value = float(
                sum(
                    np.linalg.norm(theta - collection_theta) ** 2
                    for collection_theta in history.collection_thetas
                )
            )
            welford_q_residual = abs(float(q_value) - direct_q_value)
            if diagnostic_checkpoint and endpoint is None:
                if replay_gradients is None:
                    replay_gradients = history.current_replay_gradients(
                        theta, environment.width
                    )
                current_matrix = np.asarray(
                    settings.ridge * np.eye(dimension)
                    + replay_gradients.T @ replay_gradients,
                    dtype=np.float64,
                )
                current_operator = DenseSPDOperator(current_matrix)
                endpoint = thompson_distance(frozen_operator, current_operator)
            if diagnostic_checkpoint and nystrom is not None:
                assert replay_gradients is not None
                _add_nystrom_checkpoint_diagnostics(
                    operator_metrics, nystrom, replay_gradients
                )
            diagnostic_seconds += time.perf_counter() - diagnostics_started

        # The reward and truth table are touched only after the action is fixed.
        reward = float(stream.observe(round_index, action))
        true_means = _vector(
            stream.means[round_index],
            name="evaluation true means",
            dimension=action_count,
        )
        optimal_action = int(np.argmax(true_means))
        optimal_mean = float(true_means[optimal_action])
        selected_mean = float(true_means[action])
        instantaneous_regret = optimal_mean - selected_mean
        cumulative_regret += instantaneous_regret
        reward_range = float(np.max(true_means) - np.min(true_means))
        cumulative_trivial_bound += reward_range
        sorted_means = np.sort(true_means)
        true_action_gap = float(sorted_means[-1] - sorted_means[-2])
        numerical_tolerance = (
            4096.0
            * np.finfo(np.float64).eps
            * dimension
            * max(1.0, float(np.max(np.abs(true_means))))
        )
        if environment.task_name == LABEL_TASK:
            cumulative_accuracy += int(action == stream.evaluation_label(round_index))

        if method == "linucb_fixed_features":
            empirical_radii = settings.linucb_alpha * linucb_widths
            coverage = bool(np.all(np.abs(true_means - centers) <= empirical_radii))
            optimism = bool(np.all(scores >= true_means))
            update_started = time.perf_counter()
            linear_state.append(features[action], reward)
            update_seconds = time.perf_counter() - update_started
            optimizer_diagnostics = None
            selected_bonus = float(empirical_radii[action])
            selected_width = float(linucb_widths[action])
            gamma_after = None
            instantaneous_rhs = None
            operator_storage_bytes = int(linear_state.metric.nbytes)
            cg_metrics = _exact_solver_metrics(
                selected_width, elapsed_seconds=width_solve_seconds
            )
            actual_taylor = None
            actual_misspecification = None
            pseudo_response = None
            historical_error_energy_before = None
            historical_linearization_radius = None
            historical_misspecification_radius_increment = None
            ridge_normal_equation_residual = None
            corrected_center_identity_residual = None
            pseudo_response_identity_residual = None
            current_taylor_envelope_valid = None
            current_misspecification_envelope_valid = None
            frozen_metric_recursion_residual = None
            information_gain_recursion_residual = None
            direct_q_value = None
            welford_q_residual = None
        else:
            assert corrected_centers is not None
            assert model_means is not None and queries is not None
            assert beta is not None and frozen_widths is not None
            assert score_widths is not None and d_q is not None
            assert kappa_minus is not None and kappa_plus is not None
            actual_taylor, actual_misspecification = _current_truth_diagnostics(
                environment,
                context,
                true_means,
                model_means,
                queries,
                theta,
            )
            numerical_tolerance = max(
                numerical_tolerance,
                4096.0
                * np.finfo(np.float64).eps
                * dimension
                * max(1.0, float(np.max(np.abs(corrected_centers)))),
            )
            if actual_taylor is None or actual_misspecification is None:
                corrected_center_identity_residual = None
                current_taylor_envelope_valid = None
                current_misspecification_envelope_valid = None
            else:
                theta_star = _vector(
                    environment.theta_star,
                    name="theta_star",
                    dimension=dimension,
                )
                identity_rhs = (
                    queries @ (theta_star - theta_hat)
                    + actual_taylor
                    + actual_misspecification
                )
                corrected_center_identity_residual = float(
                    np.max(np.abs(true_means - corrected_centers - identity_rhs))
                )
                if corrected_center_identity_residual > numerical_tolerance:
                    raise BenchmarkError("corrected-center identity failed")
                current_taylor_envelope_valid = bool(
                    np.max(np.abs(actual_taylor))
                    <= float(current_linearization) + numerical_tolerance
                )
                current_misspecification_envelope_valid = bool(
                    np.max(np.abs(actual_misspecification))
                    <= current_misspecification + numerical_tolerance
                )
                if not current_taylor_envelope_valid:
                    raise BenchmarkError("current Taylor envelope was violated")
                if not current_misspecification_envelope_valid:
                    raise BenchmarkError(
                        "current misspecification envelope was violated"
                    )
            reference_radii = beta * frozen_widths + current_bias
            coverage = bool(
                np.all(np.abs(true_means - corrected_centers) <= reference_radii)
            )
            optimism = bool(np.all(scores >= true_means))
            selected_query = queries[action]
            pseudo_response = (
                reward - float(model_means[action]) + float(selected_query @ theta)
            )
            if actual_taylor is None or actual_misspecification is None:
                pseudo_response_identity_residual = None
            else:
                selected_noise = float(stream.noises[round_index, action])
                pseudo_identity_rhs = (
                    float(selected_query @ theta_star)
                    + float(actual_taylor[action])
                    + float(actual_misspecification[action])
                    + selected_noise
                )
                pseudo_response_identity_residual = abs(
                    pseudo_response - pseudo_identity_rhs
                )
                if pseudo_response_identity_residual > numerical_tolerance:
                    raise BenchmarkError("pseudo-response identity failed")
            update_started = time.perf_counter()
            history.append(
                feature=features[action],
                collection_theta=theta,
                collection_query=selected_query,
                pseudo_response=pseudo_response,
                reward=reward,
                linearization_envelope=float(current_linearization),
                misspecification_envelope=historical_misspecification,
            )
            gamma_after = history.information_gain()
            expected_frozen_metric = frozen_metric_before + np.outer(
                selected_query, selected_query
            ) / (environment.noise_proxy**2)
            frozen_metric_recursion_residual = float(
                np.linalg.norm(history.frozen_metric - expected_frozen_metric, ord=2)
            )
            information_gain_recursion_residual = abs(
                (gamma_after - gamma_before)
                - math.log1p(
                    float(frozen_widths[action] ** 2) / (environment.noise_proxy**2)
                )
            )
            if frozen_metric_recursion_residual > numerical_tolerance:
                raise BenchmarkError("frozen metric recursion failed")
            if information_gain_recursion_residual > numerical_tolerance:
                raise BenchmarkError("information-gain recursion failed")
            if welford_q_residual > numerical_tolerance:
                raise BenchmarkError("Welford path statistic disagrees with direct sum")
            if endpoint is not None and endpoint > d_q + numerical_tolerance:
                raise BenchmarkError("endpoint distance exceeds the path certificate")
            cumulative_width_square += float(frozen_widths[action] ** 2)
            selected_alpha = (
                width_map.selected(action).sharpness_factor
                if width_map is not None
                else 1.0
            )
            selected_width = float(score_widths[action])
            selected_bonus = (
                float(
                    beta
                    * _safe_exp(0.5 * float(transport_distance))
                    * math.sqrt(float(kappa_plus))
                    * selected_width
                )
                if method != "greedy_corrected"
                else 0.0
            )
            if theorem_applicable:
                sharp_coefficient = beta * (
                    1.0
                    + selected_alpha
                    * _safe_exp(float(transport_distance))
                    * math.sqrt(float(kappa_plus) / float(kappa_minus))
                )
                simple_coefficient_square = (
                    selected_alpha**2
                    * beta**2
                    * _safe_exp(2.0 * float(transport_distance))
                    * float(kappa_plus)
                    / float(kappa_minus)
                )
                cumulative_sharp_coefficient_square += sharp_coefficient**2
                cumulative_simple_coefficient_square += simple_coefficient_square
                cumulative_current_bias += current_bias
                potential = (
                    environment.noise_proxy**2
                    + environment.feature_map.feature_bound**2 / settings.ridge
                ) * gamma_after
                instantaneous_rhs = (
                    sharp_coefficient * float(frozen_widths[action])
                    + 2.0 * current_bias
                )
                sharp_rhs = (
                    math.sqrt(potential * cumulative_sharp_coefficient_square)
                    + 2.0 * cumulative_current_bias
                )
                simple_rhs = (
                    2.0 * math.sqrt(potential * cumulative_simple_coefficient_square)
                    + 2.0 * cumulative_current_bias
                )
            else:
                instantaneous_rhs = None
            theta, optimizer_diagnostics = projected_full_batch_update(
                history,
                theta,
                width=environment.width,
                optimizer=settings.optimizer,
                training_ridge=settings.training_ridge,
                theta_radius=settings.theta_radius,
            )
            if nystrom is not None:
                operator_storage_bytes = nystrom.operator_storage_bytes
            elif algorithm_operator is not None:
                operator_storage_bytes = int(algorithm_operator.to_dense().nbytes)
            else:
                operator_storage_bytes = 0
            update_seconds = time.perf_counter() - update_started
            if width_map is not None and algorithm_operator is not None:
                diagnostic_started = time.perf_counter()
                cg_metrics = _cg_metrics(
                    algorithm_operator,
                    width_map,
                    action,
                    exact_diagnostic=diagnostic_checkpoint,
                )
                diagnostic_seconds += time.perf_counter() - diagnostic_started
            elif spec.solver == "cholesky":
                cg_metrics = _exact_solver_metrics(
                    selected_width, elapsed_seconds=width_solve_seconds
                )
            else:
                cg_metrics = _no_solver_metrics()

        prefix_reference_coverage = prefix_reference_coverage and coverage
        prefix_method_optimism = prefix_method_optimism and optimism
        if not theorem_applicable:
            instantaneous_bound_status = "not_applicable"
            cumulative_bound_status = "not_applicable"
        else:
            instantaneous_bound_status = "premise_false"
            if coverage:
                instantaneous_bound_status = (
                    "satisfied"
                    if instantaneous_rhs is not None
                    and instantaneous_regret <= instantaneous_rhs + numerical_tolerance
                    else "bound_violation_on_event"
                )
            cumulative_bound_status = "premise_false"
            if prefix_reference_coverage:
                cumulative_bound_status = (
                    "satisfied"
                    if sharp_rhs is not None
                    and cumulative_regret <= sharp_rhs + numerical_tolerance
                    else "bound_violation_on_event"
                )
        algorithm_seconds = (
            common_seconds + operator_seconds + scoring_seconds + update_seconds
        )
        end_to_end_round_seconds = time.perf_counter() - round_started
        record: dict[str, Any] = {
            "round": round_index + 1,
            "seed": int(stream.seed),
            "task": environment.task_name,
            "method": method,
            "selected_action": action,
            "optimal_action": optimal_action,
            "selected_reward": reward,
            "selected_mean": selected_mean,
            "optimal_mean": optimal_mean,
            "instantaneous_pseudo_regret": instantaneous_regret,
            "cumulative_pseudo_regret": cumulative_regret,
            "action_correct": (
                action == stream.evaluation_label(round_index)
                if environment.task_name == LABEL_TASK
                else None
            ),
            "scores": scores.tolist(),
            "score_widths": (
                linucb_widths.tolist()
                if method == "linucb_fixed_features"
                else score_widths.tolist()
            ),
            "frozen_widths": (
                frozen_widths.tolist() if frozen_widths is not None else None
            ),
            "current_exact_widths": (
                current_widths.tolist() if current_widths is not None else None
            ),
            "selected_score": selected_score,
            "score_tie_count": tie_count,
            "score_margin": score_margin,
            "action_oracle_error": 0.0,
            "reward_range": reward_range,
            "true_action_gap": true_action_gap,
            "selected_confidence_bonus": selected_bonus,
            "bonus_below_true_action_gap": selected_bonus < true_action_gap,
            "reference_confidence_all_actions": coverage,
            "method_optimism_all_actions": optimism,
            "transport_optimism_all_actions": (
                optimism if method in THEOREM_METHODS else None
            ),
            "prefix_simultaneous_reference_confidence": (prefix_reference_coverage),
            "prefix_simultaneous_method_optimism": prefix_method_optimism,
            "confidence_role": (
                "uncertified_linucb_diagnostic"
                if method == "linucb_fixed_features"
                else (
                    "theorem_reference_event"
                    if environment.theorem_applicable
                    else "uncertified_stress_diagnostic"
                )
            ),
            "theorem_applicable": theorem_applicable,
            "method_certified_under_exact_arithmetic": theorem_applicable,
            "analytic_certificate_valid_in_exact_arithmetic": theorem_applicable,
            "float64_diagnostic_pass": True,
            "verified_numerical_certificate": False,
            "floating_point_checks_are_verified_certificates": False,
            "certificate_class": FLOAT64_CERTIFICATE_DIAGNOSTIC,
            "theta_norm_after_update": float(np.linalg.norm(theta)),
            "optimizer_objective": (
                optimizer_diagnostics.objective
                if optimizer_diagnostics is not None
                else None
            ),
            "optimizer_gradient_norm": (
                optimizer_diagnostics.gradient_norm
                if optimizer_diagnostics is not None
                else None
            ),
            "optimizer_projection_occurred": (
                optimizer_diagnostics.projection_occurred
                if optimizer_diagnostics is not None
                else None
            ),
            "pseudo_response": pseudo_response,
            "ridge_normal_equation_residual": ridge_normal_equation_residual,
            "corrected_center_identity_max_residual": (
                corrected_center_identity_residual
            ),
            "pseudo_response_identity_residual": pseudo_response_identity_residual,
            "current_taylor_envelope_valid": current_taylor_envelope_valid,
            "current_misspecification_envelope_valid": (
                current_misspecification_envelope_valid
            ),
            "frozen_metric_recursion_residual": frozen_metric_recursion_residual,
            "information_gain_recursion_residual": (
                information_gain_recursion_residual
            ),
            "gamma_t_minus_1": gamma_before,
            "gamma_t": gamma_after,
            "beta_t_corr": beta,
            "beta_statistical": beta_statistical,
            "beta_historical": beta_historical,
            "beta_historical_linearization_only": (historical_linearization_radius),
            "beta_historical_misspecification_increment": (
                historical_misspecification_radius_increment
            ),
            "historical_error_energy_before": historical_error_energy_before,
            "historical_error_energy_after": (
                history.historical_error_energy
                if method != "linucb_fixed_features"
                else None
            ),
            "historical_misspecification_envelope": (
                historical_misspecification
                if method != "linucb_fixed_features"
                else None
            ),
            "current_linearization_envelope": current_linearization,
            "current_misspecification_envelope": (
                current_misspecification if method != "linucb_fixed_features" else None
            ),
            "current_bias": current_bias,
            "actual_current_taylor_remainders": (
                actual_taylor.tolist() if actual_taylor is not None else None
            ),
            "actual_current_misspecification": (
                actual_misspecification.tolist()
                if actual_misspecification is not None
                else None
            ),
            "corrected_centers": (
                corrected_centers.tolist() if corrected_centers is not None else None
            ),
            "tangent_centers": (
                tangent_centers.tolist() if tangent_centers is not None else None
            ),
            "frozen_widths": (
                frozen_widths.tolist() if frozen_widths is not None else None
            ),
            "current_widths": (
                current_widths.tolist() if current_widths is not None else None
            ),
            "Q_t": q_value,
            "Q_t_direct": direct_q_value,
            "Q_t_welford_residual": welford_q_residual,
            "D_Q": d_q,
            "d_Th": endpoint,
            "D_Q_minus_d_Th": (
                float(d_q - endpoint)
                if d_q is not None and endpoint is not None
                else None
            ),
            "transport_distance_used": transport_distance,
            "kappa_minus": kappa_minus,
            "kappa_plus": kappa_plus,
            "selected_width": selected_width,
            "instantaneous_theorem_rhs": instantaneous_rhs,
            "instantaneous_theorem_bound_status": instantaneous_bound_status,
            "sharp_theorem_rhs": sharp_rhs,
            "simple_theorem_rhs": simple_rhs,
            "cumulative_theorem_bound_status": cumulative_bound_status,
            "cumulative_trivial_regret_bound": cumulative_trivial_bound,
            "frozen_width_square_sum": cumulative_width_square,
            "operator_construction_seconds": float(operator_construction_seconds),
            "transport_certificate_seconds": float(transport_certificate_seconds),
            "action_scoring_seconds": float(scoring_seconds),
            "representation_update_seconds": float(update_seconds),
            "algorithm_seconds": float(algorithm_seconds),
            "diagnostic_seconds": float(diagnostic_seconds),
            "end_to_end_round_seconds": float(end_to_end_round_seconds),
            "diagnostic_checkpoint": diagnostic_checkpoint,
            "operator_storage_bytes": operator_storage_bytes,
            **operator_metrics,
            **cg_metrics,
        }
        if method == "linucb_fixed_features":
            record["linucb_alpha"] = settings.linucb_alpha
        records.append(record)

        if round_index + 1 in report_prefixes:
            prefix_summaries[round_index + 1] = _prefix_summary(
                environment=environment,
                method=method,
                records=records,
                cumulative_regret=cumulative_regret,
                cumulative_trivial_bound=cumulative_trivial_bound,
                prefix_reference_coverage=prefix_reference_coverage,
                prefix_method_optimism=prefix_method_optimism,
                cumulative_accuracy=cumulative_accuracy,
                sharp_rhs=sharp_rhs,
                simple_rhs=simple_rhs,
            )

    summary = dict(prefix_summaries[rounds])
    summary.update(
        {
            "completed": True,
            "feature_dimension": dimension,
            "action_count": action_count,
            "width": float(environment.width),
            "noise_proxy": float(environment.noise_proxy),
            "optimizer": {
                "learning_rate": settings.optimizer.learning_rate,
                "steps_per_round": settings.optimizer.steps_per_round,
            },
            "linucb_alpha": (
                settings.linucb_alpha if method == "linucb_fixed_features" else None
            ),
            "nystrom_rank": spec.rank,
            "cg_tolerance": spec.cg_tolerance,
            "post_selection_refinement": False,
        }
    )
    return TrajectoryResult(
        task=environment.task_name,
        method=method,
        seed=int(stream.seed),
        rounds=tuple(records),
        prefix_summaries=prefix_summaries,
        summary=summary,
    )


def run_method_grid(
    environment: TaskEnvironment,
    stream: PotentialOutcomeStream,
    settings: BenchmarkSettings,
    *,
    methods: Sequence[str] = EXPECTED_METHODS,
) -> tuple[TrajectoryResult, ...]:
    """Run the fixed method grid against one immutable paired outcome stream."""

    names = tuple(methods)
    if len(names) != len(set(names)):
        raise ValueError("method grid contains duplicates")
    if any(name not in EXPECTED_METHODS for name in names):
        raise ValueError("method grid contains an unknown method")
    return tuple(
        run_policy_trajectory(environment, stream, name, settings) for name in names
    )


def run_tuning_trajectory(
    environment: TaskEnvironment,
    stream: PotentialOutcomeStream,
    optimizer: OptimizerSpec,
    *,
    ridge: float = 1.0,
    training_ridge: float = 1.0,
    theta_radius: float = 1.0,
    burn_in: int = 100,
    behavior_seed: int | None = None,
) -> TuningResult:
    """Run one optimizer on a shared, uniformly random selected-reward stream."""

    if stream.task_name != environment.task_name:
        raise ValueError("stream and environment tasks differ")
    if stream.phase == "evaluation":
        raise ValueError("tuning trajectories must not consume evaluation rows")
    if not isinstance(optimizer, OptimizerSpec):
        raise TypeError("optimizer must be an OptimizerSpec")
    rounds = int(stream.rounds)
    if isinstance(burn_in, (bool, np.bool_)) or not isinstance(
        burn_in, (int, np.integer)
    ):
        raise TypeError("burn_in must be an integer")
    burn_in = int(burn_in)
    if burn_in < 0 or burn_in >= rounds:
        raise ValueError("burn_in must be nonnegative and smaller than the horizon")
    seed = (
        derive_seed(
            int(stream.seed),
            "realistic_transport/tuning_behavior/v1",
            environment.task_name,
        )
        if behavior_seed is None
        else _nonnegative_integer(behavior_seed, name="behavior_seed")
    )
    if seed < 0:
        raise ValueError("behavior_seed must be nonnegative")
    generator = np.random.default_rng(seed)
    behavior_actions = generator.integers(
        0, environment.action_count, size=rounds, dtype=np.int64
    )
    history = SelectedHistory(
        environment.feature_dimension, ridge, environment.noise_proxy
    )
    theta = np.zeros(environment.feature_dimension, dtype=np.float64)
    records: list[dict[str, Any]] = []
    post_burn_in_errors: list[float] = []
    for round_index in range(rounds):
        policy_round = stream.policy_round(round_index)
        features = _matrix(
            policy_round.action_features,
            name="action features",
            rows=environment.action_count,
            columns=environment.feature_dimension,
        )
        predictions = np.asarray(
            scaled_tanh_mean(theta, features, environment.width), dtype=np.float64
        )
        queries = scaled_tanh_gradient(theta, features, environment.width)
        action = int(behavior_actions[round_index])
        reward = float(stream.observe(round_index, action))
        true_means = _vector(
            stream.means[round_index],
            name="evaluation true means",
            dimension=environment.action_count,
        )
        mse = float(np.mean((predictions - true_means) ** 2))
        included = round_index + 1 > burn_in
        if included:
            post_burn_in_errors.append(mse)
        selected_query = queries[action]
        pseudo_response = (
            reward - float(predictions[action]) + float(selected_query @ theta)
        )
        history.append(
            feature=features[action],
            collection_theta=theta,
            collection_query=selected_query,
            pseudo_response=pseudo_response,
            reward=reward,
            linearization_envelope=0.0,
            misspecification_envelope=0.0,
        )
        theta, diagnostics = projected_full_batch_update(
            history,
            theta,
            width=environment.width,
            optimizer=optimizer,
            training_ridge=training_ridge,
            theta_radius=theta_radius,
        )
        records.append(
            {
                "round": round_index + 1,
                "seed": int(stream.seed),
                "task": environment.task_name,
                "behavior_action": action,
                "prediction_mse_all_actions": mse,
                "included_after_burn_in": included,
                "selected_reward": reward,
                "theta_norm_after_update": float(np.linalg.norm(theta)),
                "optimizer_objective": diagnostics.objective,
                "optimizer_gradient_norm": diagnostics.gradient_norm,
                "optimizer_projection_occurred": diagnostics.projection_occurred,
            }
        )
    summary = {
        "task": environment.task_name,
        "seed": int(stream.seed),
        "rounds": rounds,
        "burn_in": burn_in,
        "post_burn_in_round_count": len(post_burn_in_errors),
        "mean_all_action_prediction_mse": float(np.mean(post_burn_in_errors)),
        "median_all_action_prediction_mse": float(np.median(post_burn_in_errors)),
        "learning_rate": optimizer.learning_rate,
        "steps_per_round": optimizer.steps_per_round,
        "behavior_seed": seed,
        "behavior_stream_is_uniform_random": True,
        "behavior_stream_independent_of_optimizer": True,
        "completed": True,
    }
    return TuningResult(
        task=environment.task_name,
        seed=int(stream.seed),
        optimizer=optimizer,
        rounds=tuple(records),
        summary=summary,
    )


__all__ = [
    "BenchmarkError",
    "BenchmarkSettings",
    "LinearBanditState",
    "OptimizerDiagnostics",
    "OptimizerSpec",
    "SelectedHistory",
    "THEOREM_METHODS",
    "TrajectoryResult",
    "TuningResult",
    "corrected_center",
    "corrected_confidence_radius",
    "linearization_envelope",
    "projected_full_batch_update",
    "run_method_grid",
    "run_policy_trajectory",
    "run_tuning_trajectory",
    "tangent_center",
]
