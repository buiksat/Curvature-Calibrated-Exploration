"""Exact nonlinear instantiation of the confidence-transport theorem.

This module contains the numerical core for the controlled scaled-tanh study.
It deliberately uses dense float64 matrices and exact Cholesky solves.  The
floating-point checks are diagnostics, not verified numerical certificates.

The context space has only ``2**4 * 5 = 80`` context-action categories.  The
current replay metric and the nonlinear training objective therefore use exact
category sufficient statistics; no historical observation is discarded or
subsampled.  Per-observation collection parameters are retained only for the
frozen metric, the corrected-center audit, and the synthetic factor-path
diagnostic, where aggregation by category is not sufficient.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from itertools import product
from typing import Any, Final, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]

CONTEXT_DIMENSION: Final = 4
ACTION_COUNT: Final = 5
FEATURE_DIMENSION: Final = (
    CONTEXT_DIMENSION + ACTION_COUNT + CONTEXT_DIMENSION * ACTION_COUNT
)
CONTEXT_COUNT: Final = 2**CONTEXT_DIMENSION
CATEGORY_COUNT: Final = CONTEXT_COUNT * ACTION_COUNT

SUPPORTED_METHODS: Final = (
    "transport_hessian",
    "transport_endpoint",
    "frozen_reference",
    "naive_current",
)


class TransportInstantiationError(RuntimeError):
    """Raised when a deterministic prerequisite of the experiment fails."""


def _float_array(
    value: ArrayLike,
    *,
    name: str,
    ndim: int,
    shape: tuple[int, ...] | None = None,
    copy: bool = False,
) -> FloatArray:
    if np.iscomplexobj(np.asarray(value)):
        raise TypeError(f"{name} must be real-valued")
    array = (
        np.array(value, dtype=np.float64, copy=True)
        if copy
        else np.asarray(value, dtype=np.float64)
    )
    if array.ndim != ndim:
        raise ValueError(f"{name} must have {ndim} dimensions, got {array.shape}")
    if shape is not None and array.shape != shape:
        raise ValueError(f"{name} must have shape {shape}, got {array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def _positive_float(value: Any, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and strictly positive")
    return result


def _nonnegative_float(value: Any, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _readonly(value: FloatArray) -> FloatArray:
    value.setflags(write=False)
    return value


def _nested_value(source: Mapping[str, Any], paths: Sequence[str], default: Any) -> Any:
    for path in paths:
        current: Any = source
        found = True
        for component in path.split("."):
            if not isinstance(current, Mapping) or component not in current:
                found = False
                break
            current = current[component]
        if found:
            return current
    return default


def canonical_method(method: str) -> str:
    normalized = str(method).strip().lower().replace("-", "_").replace(" ", "_")
    if normalized not in SUPPORTED_METHODS:
        raise ValueError(
            f"unknown method {method!r}; choose from {list(SUPPORTED_METHODS)}"
        )
    return normalized


def condition_token(target_d: float) -> str:
    """Return the stable condition token used in raw artifact paths."""

    value = _positive_float(target_d, name="target_d")
    return format(value, ".12g").replace("-", "m").replace(".", "p")


def derive_child_seed(seed: int, label: str) -> int:
    """Derive a stable nonnegative seed without Python's randomized hash."""

    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, (int, np.integer)):
        raise TypeError("seed must be an integer")
    if int(seed) < 0:
        raise ValueError("seed must be nonnegative")
    payload = f"transport-instantiation-v1\0{int(seed)}\0{label}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & (
        (1 << 63) - 1
    )


def smoothness_constant(feature_bound: float) -> float:
    bound = _positive_float(feature_bound, name="feature_bound")
    return 4.0 * bound * bound / (3.0 * math.sqrt(3.0))


def target_width(
    horizon: int,
    target_d: float,
    *,
    feature_bound: float = 1.0,
    theta_radius: float = 1.0,
    noise_std: float = 0.25,
    ridge: float = 1.0,
) -> float:
    """Return the preregistered ``W(T, D_target)`` design value."""

    rounds = _positive_int(horizon, name="horizon")
    if rounds < 2:
        raise ValueError("target_width requires horizon at least two")
    target = _positive_float(target_d, name="target_d")
    radius = _positive_float(theta_radius, name="theta_radius")
    sigma = _positive_float(noise_std, name="noise_std")
    damping = _positive_float(ridge, name="ridge")
    constant = smoothness_constant(feature_bound)
    numerator = 4.0 * constant * radius * math.sqrt(float(rounds - 1))
    width = (numerator / (sigma * math.sqrt(damping) * target)) ** 2
    if not np.isfinite(width) or width <= 0.0:
        raise FloatingPointError("target-width calculation produced an invalid value")
    return float(width)


def hessian_q_path_certificate(
    q_value: float,
    *,
    lipschitz_gradient: float,
    noise_std: float,
    ridge: float,
) -> float:
    q_nonnegative = _nonnegative_float(q_value, name="q_value")
    lipschitz = _nonnegative_float(
        lipschitz_gradient, name="lipschitz_gradient"
    )
    sigma = _positive_float(noise_std, name="noise_std")
    damping = _positive_float(ridge, name="ridge")
    return float(2.0 * lipschitz * math.sqrt(q_nonnegative) / (sigma * math.sqrt(damping)))


def certified_linearization_envelope(
    theta: ArrayLike,
    *,
    theta_radius: float,
    lipschitz_mean: float,
) -> float:
    parameters = _float_array(
        theta, name="theta", ndim=1, shape=(FEATURE_DIMENSION,)
    )
    radius = _positive_float(theta_radius, name="theta_radius")
    lipschitz = _nonnegative_float(lipschitz_mean, name="lipschitz_mean")
    return float(0.5 * lipschitz * (radius + float(np.linalg.norm(parameters))) ** 2)


def corrected_center(
    theta: ArrayLike,
    theta_hat_linear: ArrayLike,
    features: ArrayLike,
    environment: "ScaledTanhEnvironment",
) -> FloatArray:
    parameters = _float_array(
        theta, name="theta", ndim=1, shape=(FEATURE_DIMENSION,)
    )
    estimate = _float_array(
        theta_hat_linear,
        name="theta_hat_linear",
        ndim=1,
        shape=(FEATURE_DIMENSION,),
    )
    design = np.asarray(features, dtype=np.float64)
    if design.ndim == 1:
        design = design[np.newaxis, :]
    if design.ndim != 2 or design.shape[1] != FEATURE_DIMENSION:
        raise ValueError(
            f"features must have second dimension {FEATURE_DIMENSION}, got {design.shape}"
        )
    means = np.asarray(environment.mean(parameters, design), dtype=np.float64)
    queries = environment.gradient(parameters, design)
    return np.asarray(means + queries @ (estimate - parameters), dtype=np.float64)


def confidence_radius(
    information_gain: float,
    *,
    delta: float,
    ridge: float,
    theta_radius: float,
    historical_error_energy: float,
    noise_std: float,
) -> tuple[float, float, float]:
    gamma = _nonnegative_float(information_gain, name="information_gain")
    probability = float(delta)
    if not np.isfinite(probability) or not 0.0 < probability < 1.0:
        raise ValueError("delta must lie strictly between zero and one")
    damping = _positive_float(ridge, name="ridge")
    radius = _positive_float(theta_radius, name="theta_radius")
    error_energy = _nonnegative_float(
        historical_error_energy, name="historical_error_energy"
    )
    sigma = _positive_float(noise_std, name="noise_std")
    statistical = math.sqrt(gamma + 2.0 * math.log(1.0 / probability))
    statistical += math.sqrt(damping) * radius
    historical = math.sqrt(error_energy) / sigma
    return statistical + historical, statistical, historical


def policy_scores(
    method: str,
    corrected_centers: ArrayLike,
    *,
    beta: float,
    current_bias: float | ArrayLike,
    frozen_widths: ArrayLike,
    current_widths: ArrayLike,
    hessian_path_bound: float,
    endpoint_distance: float,
) -> FloatArray:
    selected_method = canonical_method(method)
    centers = _float_array(corrected_centers, name="corrected_centers", ndim=1)
    frozen = _float_array(frozen_widths, name="frozen_widths", ndim=1)
    current = _float_array(current_widths, name="current_widths", ndim=1)
    if centers.shape != frozen.shape or centers.shape != current.shape:
        raise ValueError("centers and width arrays must have identical shapes")
    confidence = _nonnegative_float(beta, name="beta")
    d_q = _nonnegative_float(hessian_path_bound, name="hessian_path_bound")
    endpoint = _nonnegative_float(endpoint_distance, name="endpoint_distance")
    bias = np.asarray(current_bias, dtype=np.float64)
    if bias.ndim > 1 or (bias.ndim == 1 and bias.shape != centers.shape):
        raise ValueError("current_bias must be scalar or match the centers")
    if not np.all(np.isfinite(bias)) or np.any(bias < 0.0):
        raise ValueError("current_bias must be finite and nonnegative")
    widths = {
        "transport_hessian": math.exp(0.5 * d_q) * current,
        "transport_endpoint": math.exp(0.5 * endpoint) * current,
        "frozen_reference": frozen,
        "naive_current": current,
    }[selected_method]
    return np.asarray(centers + confidence * widths + bias, dtype=np.float64)


def enumerate_contexts() -> FloatArray:
    scale = 1.0 / math.sqrt(float(CONTEXT_DIMENSION))
    return np.asarray(
        list(product((-scale, scale), repeat=CONTEXT_DIMENSION)), dtype=np.float64
    )


def context_index(context: ArrayLike) -> int:
    vector = _float_array(
        context,
        name="context",
        ndim=1,
        shape=(CONTEXT_DIMENSION,),
    )
    scale = 1.0 / math.sqrt(float(CONTEXT_DIMENSION))
    if not np.all(np.isclose(np.abs(vector), scale, rtol=0.0, atol=1e-14)):
        raise ValueError("context must be a normalized Rademacher vector")
    index = 0
    for coordinate in vector:
        index = 2 * index + int(coordinate > 0.0)
    return index


def normalized_feature(
    context: ArrayLike, action: int, *, feature_bound: float = 1.0
) -> FloatArray:
    x = _float_array(
        context,
        name="context",
        ndim=1,
        shape=(CONTEXT_DIMENSION,),
    )
    if isinstance(action, (bool, np.bool_)) or not isinstance(
        action, (int, np.integer)
    ):
        raise TypeError("action must be an integer")
    action = int(action)
    if not 0 <= action < ACTION_COUNT:
        raise ValueError(f"action must lie in [0, {ACTION_COUNT})")
    bound = _positive_float(feature_bound, name="feature_bound")
    one_hot = np.zeros(ACTION_COUNT, dtype=np.float64)
    one_hot[action] = 1.0
    raw = np.concatenate((x, one_hot, np.kron(x, one_hot)))
    norm = float(np.linalg.norm(raw))
    if norm == 0.0 or not np.isfinite(norm):
        raise FloatingPointError("raw feature has an invalid norm")
    return np.asarray(bound * raw / norm, dtype=np.float64)


def feature_table(feature_bound: float = 1.0) -> FloatArray:
    contexts = enumerate_contexts()
    table = np.empty(
        (CONTEXT_COUNT, ACTION_COUNT, FEATURE_DIMENSION), dtype=np.float64
    )
    for context_id, context in enumerate(contexts):
        for action in range(ACTION_COUNT):
            table[context_id, action] = normalized_feature(
                context, action, feature_bound=feature_bound
            )
    return table


def _helmert_simplex() -> FloatArray:
    """Return five unit regular-simplex vertices as rows in R^4."""

    basis = np.zeros((ACTION_COUNT, ACTION_COUNT - 1), dtype=np.float64)
    for column in range(ACTION_COUNT - 1):
        denominator = math.sqrt(float((column + 1) * (column + 2)))
        basis[: column + 1, column] = 1.0 / denominator
        basis[column + 1, column] = -(column + 1) / denominator
    return np.asarray(math.sqrt(ACTION_COUNT / (ACTION_COUNT - 1)) * basis)


def regular_simplex_teacher(
    theta_radius: float = 1.0,
    *,
    teacher_seed: int = 202603,
) -> FloatArray:
    """Build the fixed interaction-only teacher used by every run.

    ``teacher_seed`` selects a deterministic orthogonal rotation.  It changes
    coordinates but preserves all regular-simplex inner products.
    """

    radius = _positive_float(theta_radius, name="theta_radius")
    if isinstance(teacher_seed, (bool, np.bool_)) or not isinstance(
        teacher_seed, (int, np.integer)
    ):
        raise TypeError("teacher_seed must be an integer")
    if int(teacher_seed) < 0:
        raise ValueError("teacher_seed must be nonnegative")
    rng = np.random.default_rng(int(teacher_seed))
    raw_rotation = rng.normal(size=(CONTEXT_DIMENSION, CONTEXT_DIMENSION))
    rotation, triangular = np.linalg.qr(raw_rotation)
    signs = np.where(np.diag(triangular) < 0.0, -1.0, 1.0)
    rotation = rotation * signs[np.newaxis, :]
    vertices = _helmert_simplex() @ rotation
    interactions = vertices.T
    theta = np.zeros(FEATURE_DIMENSION, dtype=np.float64)
    offset = CONTEXT_DIMENSION + ACTION_COUNT
    theta[offset:] = interactions.reshape(-1)
    theta *= radius / float(np.linalg.norm(theta))
    return theta


def scaled_tanh_mean(
    theta: ArrayLike, features: ArrayLike, width: float
) -> float | FloatArray:
    parameters = _float_array(
        theta, name="theta", ndim=1, shape=(FEATURE_DIMENSION,)
    )
    design = np.asarray(features, dtype=np.float64)
    if design.ndim not in (1, 2) or design.shape[-1] != FEATURE_DIMENSION:
        raise ValueError(
            f"features must end in dimension {FEATURE_DIMENSION}, got {design.shape}"
        )
    if not np.all(np.isfinite(design)):
        raise ValueError("features must contain only finite values")
    scale = math.sqrt(_positive_float(width, name="width"))
    values = scale * np.tanh((design @ parameters) / scale)
    if design.ndim == 1:
        return float(values)
    return np.asarray(values, dtype=np.float64)


def scaled_tanh_gradient(
    theta: ArrayLike, features: ArrayLike, width: float
) -> FloatArray:
    parameters = _float_array(
        theta, name="theta", ndim=1, shape=(FEATURE_DIMENSION,)
    )
    design = np.asarray(features, dtype=np.float64)
    if design.ndim not in (1, 2) or design.shape[-1] != FEATURE_DIMENSION:
        raise ValueError(
            f"features must end in dimension {FEATURE_DIMENSION}, got {design.shape}"
        )
    if not np.all(np.isfinite(design)):
        raise ValueError("features must contain only finite values")
    scale = math.sqrt(_positive_float(width, name="width"))
    tangent = np.tanh((design @ parameters) / scale)
    multipliers = 1.0 - tangent * tangent
    if design.ndim == 1:
        return np.asarray(multipliers * design, dtype=np.float64)
    return np.asarray(multipliers[:, np.newaxis] * design, dtype=np.float64)


def scaled_tanh_hessian_vector_product(
    theta: ArrayLike,
    features: ArrayLike,
    vector: ArrayLike,
    width: float,
) -> FloatArray:
    parameters = _float_array(
        theta, name="theta", ndim=1, shape=(FEATURE_DIMENSION,)
    )
    direction = _float_array(
        vector, name="vector", ndim=1, shape=(FEATURE_DIMENSION,)
    )
    design = np.asarray(features, dtype=np.float64)
    if design.ndim not in (1, 2) or design.shape[-1] != FEATURE_DIMENSION:
        raise ValueError(
            f"features must end in dimension {FEATURE_DIMENSION}, got {design.shape}"
        )
    if not np.all(np.isfinite(design)):
        raise ValueError("features must contain only finite values")
    scale = math.sqrt(_positive_float(width, name="width"))
    tangent = np.tanh((design @ parameters) / scale)
    sech_squared = 1.0 - tangent * tangent
    coefficient = -2.0 * tangent * sech_squared / scale
    directional_inner = design @ direction
    if design.ndim == 1:
        return np.asarray(coefficient * directional_inner * design, dtype=np.float64)
    return np.asarray(
        (coefficient * directional_inner)[:, np.newaxis] * design,
        dtype=np.float64,
    )


@dataclass(frozen=True)
class ScaledTanhEnvironment:
    """The fixed finite scaled-tanh contextual-bandit environment."""

    width: float
    feature_bound: float = 1.0
    theta_radius: float = 1.0
    noise_std: float = 0.25
    teacher_seed: int = 202603
    theta_star: FloatArray = field(init=False, repr=False)
    contexts: FloatArray = field(init=False, repr=False)
    features: FloatArray = field(init=False, repr=False)
    feature_outer_products: FloatArray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "width", _positive_float(self.width, name="width"))
        object.__setattr__(
            self,
            "feature_bound",
            _positive_float(self.feature_bound, name="feature_bound"),
        )
        object.__setattr__(
            self,
            "theta_radius",
            _positive_float(self.theta_radius, name="theta_radius"),
        )
        object.__setattr__(
            self, "noise_std", _positive_float(self.noise_std, name="noise_std")
        )
        contexts = enumerate_contexts()
        features = feature_table(self.feature_bound)
        teacher = regular_simplex_teacher(
            self.theta_radius, teacher_seed=self.teacher_seed
        )
        object.__setattr__(self, "contexts", _readonly(contexts))
        object.__setattr__(self, "features", _readonly(features))
        flattened = features.reshape(CATEGORY_COUNT, FEATURE_DIMENSION)
        outer_products = np.einsum("ci,cj->cij", flattened, flattened)
        object.__setattr__(
            self, "feature_outer_products", _readonly(outer_products)
        )
        object.__setattr__(self, "theta_star", _readonly(teacher))

    @property
    def category_features(self) -> FloatArray:
        return self.features.reshape(CATEGORY_COUNT, FEATURE_DIMENSION)

    @property
    def c_h(self) -> float:
        return smoothness_constant(self.feature_bound)

    @property
    def lipschitz_mean(self) -> float:
        return self.c_h / math.sqrt(self.width)

    @property
    def lipschitz_gradient(self) -> float:
        return self.c_h / math.sqrt(self.width)

    def mean(self, theta: ArrayLike, features: ArrayLike) -> float | FloatArray:
        return scaled_tanh_mean(theta, features, self.width)

    def gradient(self, theta: ArrayLike, features: ArrayLike) -> FloatArray:
        return scaled_tanh_gradient(theta, features, self.width)

    def hessian_vector_product(
        self, theta: ArrayLike, features: ArrayLike, vector: ArrayLike
    ) -> FloatArray:
        return scaled_tanh_hessian_vector_product(
            theta, features, vector, self.width
        )

    def true_means_for_context(self, context_id: int) -> FloatArray:
        if not 0 <= int(context_id) < CONTEXT_COUNT:
            raise ValueError("context_id is out of range")
        return np.asarray(
            self.mean(self.theta_star, self.features[int(context_id)]),
            dtype=np.float64,
        )


@dataclass(frozen=True)
class PotentialOutcomeStream:
    context_indices: NDArray[np.int64]
    contexts: FloatArray
    true_means: FloatArray
    noises: FloatArray
    rewards: FloatArray


def build_context_stream(rounds: int, seed: int) -> tuple[NDArray[np.int64], FloatArray]:
    count = _positive_int(rounds, name="rounds")
    rng = np.random.default_rng(int(seed))
    indices = rng.integers(0, CONTEXT_COUNT, size=count, dtype=np.int64)
    contexts = enumerate_contexts()[indices]
    return indices, np.asarray(contexts, dtype=np.float64)


def build_potential_noise_table(
    rounds: int, seed: int, noise_std: float
) -> FloatArray:
    count = _positive_int(rounds, name="rounds")
    sigma = _positive_float(noise_std, name="noise_std")
    rng = np.random.default_rng(int(seed))
    return np.asarray(
        rng.normal(0.0, sigma, size=(count, ACTION_COUNT)), dtype=np.float64
    )


def build_potential_outcome_stream(
    environment: ScaledTanhEnvironment,
    rounds: int,
    *,
    context_seed: int,
    noise_seed: int,
) -> PotentialOutcomeStream:
    indices, contexts = build_context_stream(rounds, context_seed)
    noises = build_potential_noise_table(rounds, noise_seed, environment.noise_std)
    true_means = np.empty((rounds, ACTION_COUNT), dtype=np.float64)
    for index, context_id in enumerate(indices):
        true_means[index] = environment.true_means_for_context(int(context_id))
    rewards = true_means + noises
    return PotentialOutcomeStream(
        context_indices=_readonly(indices.copy()),
        contexts=_readonly(contexts.copy()),
        true_means=_readonly(true_means),
        noises=_readonly(noises),
        rewards=_readonly(rewards),
    )


@dataclass(frozen=True)
class OptimizerSpec:
    learning_rate: float
    steps_per_round: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "learning_rate",
            _positive_float(self.learning_rate, name="optimizer.learning_rate"),
        )
        object.__setattr__(
            self,
            "steps_per_round",
            _positive_int(self.steps_per_round, name="optimizer.steps_per_round"),
        )

    @classmethod
    def from_mapping(cls, source: Mapping[str, Any]) -> "OptimizerSpec":
        return cls(
            learning_rate=float(
                _nested_value(source, ("learning_rate", "optimizer.learning_rate"), 0.01)
            ),
            steps_per_round=int(
                _nested_value(source, ("steps_per_round", "optimizer.steps_per_round"), 1)
            ),
        )


@dataclass(frozen=True)
class OptimizerDiagnostics:
    objective: float
    gradient_norm: float
    projection_occurred: bool
    projection_count: int
    displacement_norm: float


@dataclass
class CategorySufficientStatistics:
    """Exact sufficient statistics for the 80 possible selected categories."""

    counts: FloatArray = field(
        default_factory=lambda: np.zeros(CATEGORY_COUNT, dtype=np.float64)
    )
    reward_sums: FloatArray = field(
        default_factory=lambda: np.zeros(CATEGORY_COUNT, dtype=np.float64)
    )
    reward_square_sums: FloatArray = field(
        default_factory=lambda: np.zeros(CATEGORY_COUNT, dtype=np.float64)
    )

    def __post_init__(self) -> None:
        self.counts = _float_array(
            self.counts,
            name="counts",
            ndim=1,
            shape=(CATEGORY_COUNT,),
            copy=True,
        )
        self.reward_sums = _float_array(
            self.reward_sums,
            name="reward_sums",
            ndim=1,
            shape=(CATEGORY_COUNT,),
            copy=True,
        )
        self.reward_square_sums = _float_array(
            self.reward_square_sums,
            name="reward_square_sums",
            ndim=1,
            shape=(CATEGORY_COUNT,),
            copy=True,
        )
        if np.any(self.counts < 0.0):
            raise ValueError("category counts must be nonnegative")

    @property
    def observation_count(self) -> int:
        return int(round(float(np.sum(self.counts))))

    def add(self, category: int, reward: float) -> None:
        category = int(category)
        if not 0 <= category < CATEGORY_COUNT:
            raise ValueError("category is out of range")
        reward = float(reward)
        if not np.isfinite(reward):
            raise ValueError("reward must be finite")
        self.counts[category] += 1.0
        self.reward_sums[category] += reward
        self.reward_square_sums[category] += reward * reward

    def objective_and_gradient(
        self,
        theta: ArrayLike,
        environment: ScaledTanhEnvironment,
        *,
        training_ridge: float,
    ) -> tuple[float, FloatArray]:
        parameters = _float_array(
            theta, name="theta", ndim=1, shape=(FEATURE_DIMENSION,)
        )
        damping = _positive_float(training_ridge, name="training_ridge")
        means = np.asarray(
            environment.mean(parameters, environment.category_features),
            dtype=np.float64,
        )
        queries = environment.gradient(parameters, environment.category_features)
        residual_linear = self.counts * means - self.reward_sums
        squared_error_sum = float(
            np.sum(
                self.reward_square_sums
                - 2.0 * means * self.reward_sums
                + self.counts * means * means
            )
        )
        variance = environment.noise_std * environment.noise_std
        objective = (
            0.5 * squared_error_sum / variance
            + 0.5 * damping * float(parameters @ parameters)
        )
        gradient = queries.T @ residual_linear / variance + damping * parameters
        if not np.isfinite(objective) or not np.all(np.isfinite(gradient)):
            raise FloatingPointError("training objective or gradient is non-finite")
        return float(objective), np.asarray(gradient, dtype=np.float64)

    def current_metric(
        self,
        theta: ArrayLike,
        environment: ScaledTanhEnvironment,
        *,
        ridge: float,
    ) -> FloatArray:
        damping = _positive_float(ridge, name="ridge")
        parameters = _float_array(
            theta, name="theta", ndim=1, shape=(FEATURE_DIMENSION,)
        )
        scale = math.sqrt(environment.width)
        tangent = np.tanh(environment.category_features @ parameters / scale)
        query_scales = 1.0 - tangent * tangent
        weights = self.counts * query_scales * query_scales
        metric = damping * np.eye(FEATURE_DIMENSION, dtype=np.float64)
        metric += np.tensordot(
            weights,
            environment.feature_outer_products,
            axes=(0, 0),
        ) / (environment.noise_std**2)
        return np.asarray(0.5 * (metric + metric.T), dtype=np.float64)


def projected_gradient_update(
    statistics: CategorySufficientStatistics,
    theta: ArrayLike,
    environment: ScaledTanhEnvironment,
    *,
    optimizer: OptimizerSpec,
    training_ridge: float,
    theta_radius: float,
) -> tuple[FloatArray, OptimizerDiagnostics]:
    current = _float_array(
        theta,
        name="theta",
        ndim=1,
        shape=(FEATURE_DIMENSION,),
        copy=True,
    )
    initial = current.copy()
    radius = _positive_float(theta_radius, name="theta_radius")
    for _ in range(optimizer.steps_per_round):
        _, gradient = statistics.objective_and_gradient(
            current, environment, training_ridge=training_ridge
        )
        current = current - optimizer.learning_rate * gradient
        if not np.all(np.isfinite(current)):
            raise TransportInstantiationError("optimizer produced a non-finite iterate")
    projection_count = 0
    norm = float(np.linalg.norm(current))
    if norm > radius:
        current *= radius / norm
        projection_count = 1
    objective, final_gradient = statistics.objective_and_gradient(
        current, environment, training_ridge=training_ridge
    )
    return np.asarray(current, dtype=np.float64), OptimizerDiagnostics(
        objective=objective,
        gradient_norm=float(np.linalg.norm(final_gradient)),
        projection_occurred=projection_count > 0,
        projection_count=projection_count,
        displacement_norm=float(np.linalg.norm(current - initial)),
    )


def _cholesky(matrix: ArrayLike, *, name: str) -> FloatArray:
    dense = _float_array(matrix, name=name, ndim=2)
    if dense.shape[0] == 0 or dense.shape[0] != dense.shape[1]:
        raise ValueError(f"{name} must be a nonempty square matrix, got {dense.shape}")
    if not np.allclose(dense, dense.T, rtol=1e-12, atol=1e-14):
        raise TransportInstantiationError(f"{name} is not symmetric")
    try:
        return np.linalg.cholesky(dense)
    except np.linalg.LinAlgError as error:
        raise TransportInstantiationError(f"{name} is not positive definite") from error


def cholesky_solve(matrix: ArrayLike, right_hand_side: ArrayLike) -> FloatArray:
    factor = _cholesky(matrix, name="matrix")
    dimension = factor.shape[0]
    rhs = np.asarray(right_hand_side, dtype=np.float64)
    if rhs.ndim not in (1, 2) or rhs.shape[0] != dimension:
        raise ValueError(
            f"right_hand_side must start in dimension {dimension}, got {rhs.shape}"
        )
    if not np.all(np.isfinite(rhs)):
        raise ValueError("right_hand_side must contain only finite values")
    intermediate = np.linalg.solve(factor, rhs)
    return np.asarray(np.linalg.solve(factor.T, intermediate), dtype=np.float64)


def inverse_quadratic_widths(metric: ArrayLike, queries: ArrayLike) -> FloatArray:
    factor = _cholesky(metric, name="metric")
    dimension = factor.shape[0]
    query_matrix = _float_array(
        queries,
        name="queries",
        ndim=2,
    )
    if query_matrix.shape[1] != dimension:
        raise ValueError(f"queries must have second dimension {dimension}")
    whitened = np.linalg.solve(factor, query_matrix.T)
    return np.asarray(np.linalg.norm(whitened, axis=0), dtype=np.float64)


def logdet_spd(matrix: ArrayLike) -> float:
    factor = _cholesky(matrix, name="matrix")
    return float(2.0 * np.sum(np.log(np.diag(factor))))


def information_gain(metric: ArrayLike, ridge: float) -> float:
    """Compute ``log det(metric) - d log(ridge)`` without cancellation at t=1."""

    damping = _positive_float(ridge, name="ridge")
    dense = _float_array(metric, name="metric", ndim=2)
    return logdet_spd(dense / damping)


def thompson_distance(reference: ArrayLike, current: ArrayLike) -> tuple[float, FloatArray]:
    reference_matrix = _float_array(reference, name="reference", ndim=2)
    current_matrix = _float_array(current, name="current", ndim=2)
    if reference_matrix.shape != current_matrix.shape:
        raise ValueError(
            "reference and current matrices must have the same square shape"
        )
    _cholesky(reference_matrix, name="reference")
    _cholesky(current_matrix, name="current")
    try:
        from scipy.linalg import eigh
    except ImportError as error:  # pragma: no cover - SciPy is pinned for the study.
        raise RuntimeError("Thompson diagnostics require scipy") from error
    eigenvalues = np.asarray(
        eigh(
            current_matrix,
            reference_matrix,
            eigvals_only=True,
            check_finite=True,
            driver="gvd",
        ),
        dtype=np.float64,
    )
    if np.any(eigenvalues <= 0.0) or not np.all(np.isfinite(eigenvalues)):
        raise TransportInstantiationError(
            "generalized eigenvalues are not finite and positive"
        )
    distance = float(np.max(np.abs(np.log(eigenvalues))))
    return distance, eigenvalues


@dataclass
class TransportHistory:
    ridge: float
    noise_std: float
    statistics: CategorySufficientStatistics = field(
        default_factory=CategorySufficientStatistics
    )
    frozen_metric: FloatArray = field(init=False)
    frozen_rhs: FloatArray = field(init=False)
    categories: list[int] = field(default_factory=list)
    collection_thetas: list[FloatArray] = field(default_factory=list)
    collection_queries: list[FloatArray] = field(default_factory=list)
    pseudo_responses: list[float] = field(default_factory=list)
    rewards: list[float] = field(default_factory=list)
    noises: list[float] = field(default_factory=list)
    certified_envelopes: list[float] = field(default_factory=list)
    actual_remainders: list[float] = field(default_factory=list)
    theta_mean: FloatArray = field(init=False)
    theta_scatter: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self.ridge = _positive_float(self.ridge, name="ridge")
        self.noise_std = _positive_float(self.noise_std, name="noise_std")
        self.frozen_metric = self.ridge * np.eye(FEATURE_DIMENSION, dtype=np.float64)
        self.frozen_rhs = np.zeros(FEATURE_DIMENSION, dtype=np.float64)
        self.theta_mean = np.zeros(FEATURE_DIMENSION, dtype=np.float64)

    @property
    def length(self) -> int:
        return len(self.categories)

    @property
    def historical_error_energy(self) -> float:
        return float(np.dot(self.certified_envelopes, self.certified_envelopes))

    @property
    def collection_theta_array(self) -> FloatArray:
        if not self.collection_thetas:
            return np.empty((0, FEATURE_DIMENSION), dtype=np.float64)
        return np.stack(self.collection_thetas, axis=0)

    @property
    def collection_query_array(self) -> FloatArray:
        if not self.collection_queries:
            return np.empty((0, FEATURE_DIMENSION), dtype=np.float64)
        return np.stack(self.collection_queries, axis=0)

    def path_q(self, theta: ArrayLike) -> float:
        parameters = _float_array(
            theta, name="theta", ndim=1, shape=(FEATURE_DIMENSION,)
        )
        count = self.length
        if count == 0:
            return 0.0
        displacement = parameters - self.theta_mean
        return float(self.theta_scatter + count * float(displacement @ displacement))

    def append(
        self,
        *,
        category: int,
        collection_theta: ArrayLike,
        collection_query: ArrayLike,
        pseudo_response: float,
        reward: float,
        noise: float,
        certified_envelope: float,
        actual_remainder: float,
    ) -> None:
        category = int(category)
        theta = _float_array(
            collection_theta,
            name="collection_theta",
            ndim=1,
            shape=(FEATURE_DIMENSION,),
            copy=True,
        )
        query = _float_array(
            collection_query,
            name="collection_query",
            ndim=1,
            shape=(FEATURE_DIMENSION,),
            copy=True,
        )
        y = float(pseudo_response)
        reward = float(reward)
        noise = float(noise)
        envelope = _nonnegative_float(
            certified_envelope, name="certified_envelope"
        )
        remainder = float(actual_remainder)
        if not all(np.isfinite(value) for value in (y, reward, noise, remainder)):
            raise ValueError("historical scalar values must be finite")
        variance = self.noise_std * self.noise_std
        self.frozen_metric += np.outer(query, query) / variance
        self.frozen_rhs += query * y / variance
        self.statistics.add(category, reward)
        previous_count = self.length
        if previous_count == 0:
            self.theta_mean = theta.copy()
        else:
            difference = theta - self.theta_mean
            next_count = previous_count + 1
            next_mean = self.theta_mean + difference / float(next_count)
            self.theta_scatter += float(difference @ (theta - next_mean))
            self.theta_mean = next_mean
        self.categories.append(category)
        self.collection_thetas.append(theta)
        self.collection_queries.append(query)
        self.pseudo_responses.append(y)
        self.rewards.append(reward)
        self.noises.append(noise)
        self.certified_envelopes.append(envelope)
        self.actual_remainders.append(remainder)


@dataclass(frozen=True)
class NumericalTolerance:
    multiplier: float = 4096.0
    quadrature_tolerance: float = 1e-9
    quadrature_relative_tolerance: float = 1e-8

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "multiplier",
            _positive_float(self.multiplier, name="tolerance.multiplier"),
        )
        object.__setattr__(
            self,
            "quadrature_tolerance",
            _nonnegative_float(
                self.quadrature_tolerance, name="tolerance.quadrature_tolerance"
            ),
        )
        object.__setattr__(
            self,
            "quadrature_relative_tolerance",
            _nonnegative_float(
                self.quadrature_relative_tolerance,
                name="tolerance.quadrature_relative_tolerance",
            ),
        )

    def value(self, *objects: Any) -> float:
        scale = 1.0
        for item in objects:
            array = np.asarray(item)
            if array.size == 0:
                continue
            if array.ndim >= 2:
                candidate = float(np.linalg.norm(array, ord=2))
            else:
                candidate = float(np.max(np.abs(array)))
            if np.isfinite(candidate):
                scale = max(scale, candidate)
        return float(
            self.multiplier
            * np.finfo(np.float64).eps
            * max(1, FEATURE_DIMENSION)
            * scale
        )


def factor_path_length(
    history: TransportHistory,
    theta_t: ArrayLike,
    environment: ScaledTanhEnvironment,
    *,
    ridge: float,
    order: int = 32,
) -> float:
    """Numerically integrate the selected synthetic stacked-factor path."""

    quadrature_order = _positive_int(order, name="order")
    parameters = _float_array(
        theta_t, name="theta_t", ndim=1, shape=(FEATURE_DIMENSION,)
    )
    damping = _positive_float(ridge, name="ridge")
    if history.length == 0:
        return 0.0
    collection_thetas = history.collection_theta_array
    categories = np.asarray(history.categories, dtype=np.int64)
    features = environment.category_features[categories]
    collection_projections = np.einsum("ij,ij->i", features, collection_thetas)
    current_category_projections = environment.category_features @ parameters
    projection_displacements = (
        current_category_projections[categories] - collection_projections
    )
    nodes, weights = np.polynomial.legendre.leggauss(quadrature_order)
    try:
        from scipy.linalg import eigh
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("factor-path diagnostics require scipy") from error
    integral = 0.0
    variance = environment.noise_std * environment.noise_std
    scale = math.sqrt(environment.width)
    identity = np.eye(FEATURE_DIMENSION, dtype=np.float64)
    for node, weight in zip(nodes, weights, strict=True):
        tau = 0.5 * (float(node) + 1.0)
        linear = (
            collection_projections + tau * projection_displacements
        ) / scale
        tangent = np.tanh(linear)
        sech_squared = 1.0 - tangent * tangent
        hessian_coefficients = -2.0 * tangent * sech_squared / scale
        derivatives = hessian_coefficients * projection_displacements
        metric_weights = np.bincount(
            categories,
            weights=sech_squared * sech_squared,
            minlength=CATEGORY_COUNT,
        )
        derivative_weights = np.bincount(
            categories,
            weights=2.0 * sech_squared * derivatives,
            minlength=CATEGORY_COUNT,
        )
        path_metric = damping * identity + np.tensordot(
            metric_weights,
            environment.feature_outer_products,
            axes=(0, 0),
        ) / variance
        derivative = np.tensordot(
            derivative_weights,
            environment.feature_outer_products,
            axes=(0, 0),
        ) / variance
        derivative = 0.5 * (derivative + derivative.T)
        eigenvalues = eigh(
            derivative,
            path_metric,
            eigvals_only=True,
            check_finite=False,
            driver="gvd",
        )
        integrand = float(np.max(np.abs(eigenvalues)))
        if not np.isfinite(integrand):
            raise TransportInstantiationError("factor-path integrand is non-finite")
        integral += 0.5 * float(weight) * integrand
    return float(integral)


@dataclass(frozen=True)
class PolicyTrajectory:
    method: str
    seed: int
    horizon: int
    target_d: float
    width: float
    optimizer: OptimizerSpec
    rounds: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    child_seeds: dict[str, int]


@dataclass(frozen=True)
class TuningTrajectory:
    seed: int
    horizon: int
    target_d: float
    width: float
    optimizer: OptimizerSpec
    rounds: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    child_seeds: dict[str, int]


@dataclass(frozen=True)
class _ResolvedConfig:
    profile: str
    feature_bound: float
    theta_radius: float
    noise_std: float
    ridge: float
    training_ridge: float
    delta: float
    teacher_seed: int
    tolerance: NumericalTolerance
    quadrature_order: int
    quadrature_interval: int
    horizons: tuple[int, ...]
    tuning_burn_in: int
    raise_on_audit_failure: bool

    @classmethod
    def from_mapping(cls, source: Mapping[str, Any], horizon: int) -> "_ResolvedConfig":
        context_dimension = int(
            _nested_value(source, ("context_dimension", "environment.context_dimension"), 4)
        )
        action_count = int(
            _nested_value(source, ("action_count", "environment.action_count"), 5)
        )
        if context_dimension != CONTEXT_DIMENSION or action_count != ACTION_COUNT:
            raise ValueError(
                f"transport instantiation is fixed at p={CONTEXT_DIMENSION}, "
                f"K={ACTION_COUNT}"
            )
        delta = float(_nested_value(source, ("delta", "confidence.delta"), 0.05))
        if not np.isfinite(delta) or not 0.0 < delta < 1.0:
            raise ValueError("delta must lie strictly between zero and one")
        horizons_value = _nested_value(source, ("horizons",), [horizon])
        if isinstance(horizons_value, Mapping):
            horizons_value = list(horizons_value.values())
        horizons = tuple(sorted({int(value) for value in horizons_value}))
        return cls(
            profile=str(source.get("profile", "unspecified")),
            feature_bound=_positive_float(
                _nested_value(source, ("feature_bound", "environment.feature_bound"), 1.0),
                name="feature_bound",
            ),
            theta_radius=_positive_float(
                _nested_value(
                    source,
                    (
                        "theta_radius",
                        "teacher.theta_radius",
                        "representation_update.projection_radius",
                    ),
                    1.0,
                ),
                name="theta_radius",
            ),
            noise_std=_positive_float(
                _nested_value(source, ("noise_std", "environment.noise_std"), 0.25),
                name="noise_std",
            ),
            ridge=_positive_float(
                _nested_value(source, ("ridge", "algorithm.ridge"), 1.0),
                name="ridge",
            ),
            training_ridge=_positive_float(
                _nested_value(
                    source, ("training_ridge", "optimizer.training_ridge"), 1.0
                ),
                name="training_ridge",
            ),
            delta=delta,
            teacher_seed=int(
                _nested_value(source, ("teacher_seed", "teacher.seed"), 202603)
            ),
            tolerance=NumericalTolerance(
                multiplier=float(
                    _nested_value(
                        source,
                        (
                            "numerics.algebra_tolerance_constant",
                            "numerical.tolerance_multiplier",
                            "tolerance_multiplier",
                        ),
                        4096.0,
                    )
                ),
                quadrature_tolerance=float(
                    _nested_value(
                        source,
                        (
                            "transport.quadrature.inequality_absolute_tolerance",
                            "numerical.quadrature_tolerance",
                            "quadrature_tolerance",
                        ),
                        1e-9,
                    )
                ),
                quadrature_relative_tolerance=float(
                    _nested_value(
                        source,
                        (
                            "transport.quadrature.inequality_relative_tolerance",
                            "quadrature_relative_tolerance",
                        ),
                        1e-8,
                    )
                ),
            ),
            quadrature_order=_positive_int(
                int(
                    _nested_value(
                        source,
                        (
                            "transport.quadrature.frozen_order",
                            "path_quadrature.order",
                            "quadrature_order",
                        ),
                        32,
                    )
                ),
                name="quadrature_order",
            ),
            quadrature_interval=_positive_int(
                int(
                    _nested_value(
                        source,
                        (
                            "transport.quadrature.full_checkpoint_period",
                            "path_quadrature.full_interval",
                            "quadrature_interval",
                        ),
                        10,
                    )
                ),
                name="quadrature_interval",
            ),
            horizons=horizons,
            tuning_burn_in=max(
                0,
                int(
                    _nested_value(
                        source,
                        (
                            "representation_update.tuning.burn_in_rounds",
                            "tuning.burn_in",
                            "burn_in",
                        ),
                        max(1, horizon // 4),
                    )
                ),
            ),
            raise_on_audit_failure=bool(
                _nested_value(
                    source,
                    (
                        "numerics.fail_on_deterministic_violation",
                        "numerical.raise_on_audit_failure",
                    ),
                    False,
                )
            ),
        )


def _diagnostic_checkpoint(
    round_number: int,
    *,
    mode: str | bool,
    config: _ResolvedConfig,
    horizon: int,
) -> bool:
    if isinstance(mode, bool):
        return mode
    normalized = str(mode).strip().lower().replace("-", "_")
    if normalized in {"none", "off", "false"}:
        return False
    if normalized in {"all", "smoke"}:
        return True
    if normalized == "development":
        if config.profile == "smoke":
            return True
        return (
            round_number % config.quadrature_interval == 0
            or round_number in config.horizons
            or round_number == horizon
        )
    if normalized in {"full", "checkpoints", "evaluation"}:
        return (
            round_number % config.quadrature_interval == 0
            or round_number in config.horizons
            or round_number == horizon
        )
    raise ValueError(
        "diagnostic_mode must be one of none, all, smoke, development, full, "
        "checkpoints, or evaluation"
    )


def _record_failure(
    failures: list[str],
    name: str,
    residual: float,
    tolerance: float,
) -> None:
    if not np.isfinite(residual) or residual > tolerance:
        failures.append(
            f"{name}: residual={residual:.17g}, tolerance={tolerance:.17g}"
        )


def _minimum_symmetric_eigenvalue(matrix: FloatArray) -> float:
    symmetric = 0.5 * (matrix + matrix.T)
    return float(np.linalg.eigvalsh(symmetric)[0])


def _context_free_mean_only_regret(stream: PotentialOutcomeStream) -> float:
    """Run forced-one-pull-then-empirical-mean greedy without contexts."""

    reward_sums = np.zeros(ACTION_COUNT, dtype=np.float64)
    counts = np.zeros(ACTION_COUNT, dtype=np.int64)
    regret = 0.0
    for round_index in range(stream.true_means.shape[0]):
        if round_index < ACTION_COUNT:
            action = round_index
        else:
            empirical_means = reward_sums / counts
            action = int(np.argmax(empirical_means))
        regret += float(
            np.max(stream.true_means[round_index])
            - stream.true_means[round_index, action]
        )
        reward_sums[action] += stream.rewards[round_index, action]
        counts[action] += 1
    return regret


def _environment_summary(stream: PotentialOutcomeStream) -> dict[str, Any]:
    optimal_actions = np.argmax(stream.true_means, axis=1)
    counts = np.bincount(optimal_actions, minlength=ACTION_COUNT).astype(np.float64)
    probabilities = counts[counts > 0.0] / float(len(optimal_actions))
    entropy = float(-np.sum(probabilities * np.log(probabilities)))
    sorted_means = np.sort(stream.true_means, axis=1)
    gaps = sorted_means[:, -1] - sorted_means[:, -2]
    optimal = np.max(stream.true_means, axis=1)
    fixed_totals = np.sum(stream.true_means, axis=0)
    best_fixed_action = int(np.argmax(fixed_totals))
    best_fixed_regret = float(
        np.sum(optimal - stream.true_means[:, best_fixed_action])
    )
    return {
        "optimal_action_entropy": entropy,
        "distinct_optimal_actions": int(np.count_nonzero(counts)),
        "average_optimality_gap": float(np.mean(gaps)),
        "best_fixed_action": best_fixed_action,
        "best_fixed_action_regret": best_fixed_regret,
        "context_free_mean_only_rule": (
            "force actions 0,...,4 once, then choose the smallest-index largest "
            "empirical reward mean while ignoring context"
        ),
        "context_free_mean_only_regret": _context_free_mean_only_regret(stream),
    }


def _round_path_length(
    history: TransportHistory,
    theta: FloatArray,
    environment: ScaledTanhEnvironment,
    config: _ResolvedConfig,
    diagnostic_mode: str | bool,
    round_number: int,
    horizon: int,
) -> tuple[float | None, float | None]:
    if not _diagnostic_checkpoint(
        round_number, mode=diagnostic_mode, config=config, horizon=horizon
    ):
        return None, None
    full = factor_path_length(
        history,
        theta,
        environment,
        ridge=config.ridge,
        order=config.quadrature_order,
    )
    normalized = str(diagnostic_mode).lower() if not isinstance(diagnostic_mode, bool) else ""
    half: float | None = None
    if normalized == "development" and config.quadrature_order >= 4:
        half = factor_path_length(
            history,
            theta,
            environment,
            ridge=config.ridge,
            order=max(2, config.quadrature_order // 2),
        )
    return full, half


def run_policy_trajectory(
    config: Mapping[str, Any],
    method: str,
    seed: int,
    horizon: int,
    target_d: float,
    optimizer: OptimizerSpec | Mapping[str, Any],
    diagnostic_mode: str | bool = "full",
) -> PolicyTrajectory:
    """Execute one exact online policy trajectory.

    The generated potential-outcome table is shared across methods through
    method-independent child seeds.  Only the chosen reward is supplied to the
    history and representation update.
    """

    selected_method = canonical_method(method)
    rounds = _positive_int(horizon, name="horizon")
    target = _positive_float(target_d, name="target_d")
    optimizer_spec = (
        optimizer
        if isinstance(optimizer, OptimizerSpec)
        else OptimizerSpec.from_mapping(optimizer)
    )
    resolved = _ResolvedConfig.from_mapping(config, rounds)
    width = target_width(
        rounds,
        target,
        feature_bound=resolved.feature_bound,
        theta_radius=resolved.theta_radius,
        noise_std=resolved.noise_std,
        ridge=resolved.ridge,
    )
    environment = ScaledTanhEnvironment(
        width=width,
        feature_bound=resolved.feature_bound,
        theta_radius=resolved.theta_radius,
        noise_std=resolved.noise_std,
        teacher_seed=resolved.teacher_seed,
    )
    child_seeds = {
        "context_stream": derive_child_seed(
            seed, "transport_instantiation/context/v1"
        ),
        "potential_noise_table": derive_child_seed(
            seed, "transport_instantiation/potential_noise/v1"
        ),
        "teacher_construction": int(resolved.teacher_seed),
        "behavior_policy_tuning_stream": derive_child_seed(
            seed, "transport_instantiation/behavior_policy/v1"
        ),
        "bootstrap_aggregation": derive_child_seed(
            seed, "transport_instantiation/bootstrap/v1"
        ),
    }
    stream = build_potential_outcome_stream(
        environment,
        rounds,
        context_seed=child_seeds["context_stream"],
        noise_seed=child_seeds["potential_noise_table"],
    )
    history = TransportHistory(resolved.ridge, resolved.noise_std)
    theta = np.zeros(FEATURE_DIMENSION, dtype=np.float64)
    previous_theta = theta.copy()
    records: list[dict[str, Any]] = []
    all_failures: list[str] = []
    cumulative_regret = 0.0
    cumulative_width_square = 0.0
    cumulative_bias = 0.0
    cumulative_coefficient_square = 0.0
    cumulative_simple_square = 0.0
    cumulative_statistical_no_path_square = 0.0
    cumulative_full_no_path_square = 0.0
    cumulative_log_increments = 0.0
    prefix_reference_confidence = True
    prefix_hessian_optimism = True
    prefix_method_optimism = True
    path_lengths: list[float] = []
    path_half_differences: list[float] = []
    d_q_values: list[float] = []
    endpoint_values: list[float] = []
    last_sharp_bound = 0.0
    last_simple_bound = 0.0
    last_gamma = 0.0
    last_potential_bound = 0.0
    last_optimizer = OptimizerDiagnostics(0.0, 0.0, False, 0, 0.0)

    for round_index in range(rounds):
        round_number = round_index + 1
        context_id = int(stream.context_indices[round_index])
        action_features = environment.features[context_id]
        true_means = stream.true_means[round_index]
        queries = environment.gradient(theta, action_features)
        frozen_before = history.frozen_metric.copy()
        current_metric = history.statistics.current_metric(
            theta, environment, ridge=resolved.ridge
        )
        _cholesky(frozen_before, name="frozen_metric")
        _cholesky(current_metric, name="current_metric")
        theta_hat = cholesky_solve(frozen_before, history.frozen_rhs)
        ridge_normal_equation_residual = float(
            np.linalg.norm(frozen_before @ theta_hat - history.frozen_rhs)
        )
        means_at_theta = np.asarray(
            environment.mean(theta, action_features), dtype=np.float64
        )
        corrected_centers = corrected_center(
            theta, theta_hat, action_features, environment
        )
        frozen_widths = inverse_quadratic_widths(frozen_before, queries)
        current_widths = inverse_quadratic_widths(current_metric, queries)
        gamma_before = information_gain(frozen_before, resolved.ridge)
        historical_error_energy_before = history.historical_error_energy
        actual_historical_before = np.asarray(
            history.actual_remainders, dtype=np.float64
        )
        beta, beta_statistical, beta_historical = confidence_radius(
            gamma_before,
            delta=resolved.delta,
            ridge=resolved.ridge,
            theta_radius=resolved.theta_radius,
            historical_error_energy=historical_error_energy_before,
            noise_std=resolved.noise_std,
        )
        current_bias = certified_linearization_envelope(
            theta,
            theta_radius=resolved.theta_radius,
            lipschitz_mean=environment.lipschitz_mean,
        )
        q_value = history.path_q(theta)
        d_q = hessian_q_path_certificate(
            q_value,
            lipschitz_gradient=environment.lipschitz_gradient,
            noise_std=resolved.noise_std,
            ridge=resolved.ridge,
        )
        endpoint_distance, endpoint_eigenvalues = thompson_distance(
            frozen_before, current_metric
        )
        path_length, half_path_length = _round_path_length(
            history,
            theta,
            environment,
            resolved,
            diagnostic_mode,
            round_number,
            rounds,
        )
        hessian_inflation = math.exp(0.5 * d_q)
        endpoint_inflation = math.exp(0.5 * endpoint_distance)
        hessian_scores = (
            corrected_centers + beta * hessian_inflation * current_widths + current_bias
        )
        endpoint_scores = (
            corrected_centers + beta * endpoint_inflation * current_widths + current_bias
        )
        frozen_scores = corrected_centers + beta * frozen_widths + current_bias
        naive_scores = corrected_centers + beta * current_widths + current_bias
        score_by_method = {
            "transport_hessian": hessian_scores,
            "transport_endpoint": endpoint_scores,
            "frozen_reference": frozen_scores,
            "naive_current": naive_scores,
        }
        scores = score_by_method[selected_method]
        selected_action = int(np.argmax(scores))
        optimal_action = int(np.argmax(true_means))
        pseudo_regret = float(true_means[optimal_action] - true_means[selected_action])
        sorted_true_means = np.sort(true_means)
        optimality_gap = float(sorted_true_means[-1] - sorted_true_means[-2])
        cumulative_regret += pseudo_regret

        actual_current_remainders = np.asarray(
            true_means
            - means_at_theta
            - queries @ (environment.theta_star - theta),
            dtype=np.float64,
        )
        center_identity_rhs = (
            queries @ (environment.theta_star - theta_hat)
            + actual_current_remainders
        )
        center_identity_residuals = true_means - corrected_centers - center_identity_rhs
        scalar_tolerance = resolved.tolerance.value(
            true_means,
            corrected_centers,
            beta,
            d_q,
            endpoint_distance,
        )
        confidence_radii = beta * frozen_widths + current_bias
        confidence_margins = confidence_radii - np.abs(true_means - corrected_centers)
        reference_confidence = bool(np.all(confidence_margins >= -scalar_tolerance))
        hessian_optimism_margins = hessian_scores - true_means
        method_optimism_margins = scores - true_means
        hessian_optimism = bool(
            np.all(hessian_optimism_margins >= -scalar_tolerance)
        )
        method_optimism = bool(
            np.all(method_optimism_margins >= -scalar_tolerance)
        )
        prefix_reference_confidence = prefix_reference_confidence and reference_confidence
        prefix_hessian_optimism = prefix_hessian_optimism and hessian_optimism
        prefix_method_optimism = prefix_method_optimism and method_optimism

        failures: list[str] = []
        _record_failure(
            failures,
            "ridge_normal_equation",
            ridge_normal_equation_residual,
            resolved.tolerance.value(frozen_before, history.frozen_rhs),
        )
        _record_failure(
            failures,
            "corrected_center_identity",
            float(np.max(np.abs(center_identity_residuals))),
            scalar_tolerance,
        )
        lower_sandwich = current_metric - math.exp(-endpoint_distance) * frozen_before
        upper_sandwich = math.exp(endpoint_distance) * frozen_before - current_metric
        matrix_tolerance = resolved.tolerance.value(frozen_before, current_metric)
        endpoint_lower_min_eigenvalue = _minimum_symmetric_eigenvalue(lower_sandwich)
        endpoint_upper_min_eigenvalue = _minimum_symmetric_eigenvalue(upper_sandwich)
        endpoint_lower_shortfall = max(0.0, -endpoint_lower_min_eigenvalue)
        endpoint_upper_shortfall = max(0.0, -endpoint_upper_min_eigenvalue)
        d_th_minus_d_q = endpoint_distance - d_q
        frozen_to_current_shortfall = float(
            np.max(
                np.maximum(
                    0.0,
                    frozen_widths - hessian_inflation * current_widths,
                )
            )
        )
        current_to_frozen_shortfall = float(
            np.max(
                np.maximum(
                    0.0,
                    current_widths - hessian_inflation * frozen_widths,
                )
            )
        )
        _record_failure(
            failures,
            "endpoint_thompson_lower_sandwich",
            endpoint_lower_shortfall,
            matrix_tolerance,
        )
        _record_failure(
            failures,
            "endpoint_thompson_upper_sandwich",
            endpoint_upper_shortfall,
            matrix_tolerance,
        )
        _record_failure(
            failures,
            "endpoint_distance_below_hessian_certificate",
            max(0.0, d_th_minus_d_q),
            scalar_tolerance,
        )
        _record_failure(
            failures,
            "frozen_to_current_width_transport",
            frozen_to_current_shortfall,
            scalar_tolerance,
        )
        _record_failure(
            failures,
            "current_to_frozen_width_transport",
            current_to_frozen_shortfall,
            scalar_tolerance,
        )
        path_lower_shortfall: float | None = None
        path_upper_shortfall: float | None = None
        if path_length is not None:
            path_tolerance = max(
                resolved.tolerance.quadrature_tolerance
                + resolved.tolerance.quadrature_relative_tolerance
                * max(1.0, abs(endpoint_distance), abs(path_length), abs(d_q)),
                scalar_tolerance,
            )
            path_lower_shortfall = max(0.0, endpoint_distance - path_length)
            path_upper_shortfall = max(0.0, path_length - d_q)
            _record_failure(
                failures,
                "endpoint_distance_below_factor_path_length",
                path_lower_shortfall,
                path_tolerance,
            )
            _record_failure(
                failures,
                "factor_path_length_below_hessian_certificate",
                path_upper_shortfall,
                path_tolerance,
            )
            path_lengths.append(path_length)
            if half_path_length is not None:
                convergence_difference = abs(path_length - half_path_length)
                path_half_differences.append(convergence_difference)
                _record_failure(
                    failures,
                    "factor_path_quadrature_convergence",
                    convergence_difference,
                    path_tolerance,
                )

        selected_query = queries[selected_action]
        reward = float(stream.rewards[round_index, selected_action])
        noise = float(stream.noises[round_index, selected_action])
        mean_collection = float(means_at_theta[selected_action])
        pseudo_response = reward - mean_collection + float(selected_query @ theta)
        actual_remainder = float(actual_current_remainders[selected_action])
        pseudo_identity_rhs = (
            float(selected_query @ environment.theta_star) + actual_remainder + noise
        )
        _record_failure(
            failures,
            "pseudo_response_identity",
            abs(pseudo_response - pseudo_identity_rhs),
            scalar_tolerance,
        )
        certified_envelope = current_bias
        selected_category = context_id * ACTION_COUNT + selected_action
        history.append(
            category=selected_category,
            collection_theta=theta,
            collection_query=selected_query,
            pseudo_response=pseudo_response,
            reward=reward,
            noise=noise,
            certified_envelope=certified_envelope,
            actual_remainder=actual_remainder,
        )
        expected_frozen = frozen_before + np.outer(selected_query, selected_query) / (
            resolved.noise_std**2
        )
        frozen_gram_recursion_residual = float(
            np.linalg.norm(history.frozen_metric - expected_frozen, ord=2)
        )
        _record_failure(
            failures,
            "frozen_gram_recursion",
            frozen_gram_recursion_residual,
            resolved.tolerance.value(history.frozen_metric, expected_frozen),
        )
        gamma_after = information_gain(history.frozen_metric, resolved.ridge)
        selected_frozen_width = float(frozen_widths[selected_action])
        log_increment = math.log1p(
            selected_frozen_width * selected_frozen_width / (resolved.noise_std**2)
        )
        cumulative_log_increments += log_increment
        information_gain_recursion_residual = abs(
            (gamma_after - gamma_before) - log_increment
        )
        cumulative_information_gain_residual = abs(
            gamma_after - cumulative_log_increments
        )
        _record_failure(
            failures,
            "determinant_information_gain_recursion",
            information_gain_recursion_residual,
            resolved.tolerance.value(gamma_after, gamma_before, log_increment),
        )
        _record_failure(
            failures,
            "cumulative_information_gain_identity",
            cumulative_information_gain_residual,
            resolved.tolerance.value(gamma_after, cumulative_log_increments),
        )
        cumulative_width_square += selected_frozen_width**2
        potential_bound = (
            resolved.noise_std**2
            + resolved.feature_bound**2 / resolved.ridge
        ) * gamma_after
        potential_slack = potential_bound - cumulative_width_square
        _record_failure(
            failures,
            "frozen_width_sum_potential",
            max(0.0, -potential_slack),
            resolved.tolerance.value(cumulative_width_square, potential_bound),
        )

        coefficient = beta * (1.0 + math.exp(d_q))
        instantaneous_bound = coefficient * selected_frozen_width + 2.0 * current_bias
        instantaneous_status = "not_applicable"
        if selected_method == "transport_hessian":
            instantaneous_status = "premise_false"
            if reference_confidence:
                instantaneous_status = "satisfied"
                if pseudo_regret > instantaneous_bound + scalar_tolerance:
                    instantaneous_status = "bound_violation_on_event"
                    failures.append(
                        "instantaneous_regret_bound_on_event: "
                        f"regret={pseudo_regret:.17g}, rhs={instantaneous_bound:.17g}"
                    )
        cumulative_bias += current_bias
        cumulative_coefficient_square += coefficient**2
        cumulative_simple_square += beta * beta * math.exp(2.0 * d_q)
        cumulative_statistical_no_path_square += (2.0 * beta_statistical) ** 2
        cumulative_full_no_path_square += (2.0 * beta) ** 2
        potential_coefficient = (
            resolved.noise_std**2 + resolved.feature_bound**2 / resolved.ridge
        ) * gamma_after
        statistical_bound_component = math.sqrt(
            potential_coefficient * cumulative_statistical_no_path_square
        )
        full_no_path_exploration = math.sqrt(
            potential_coefficient * cumulative_full_no_path_square
        )
        actual_sharp_exploration = math.sqrt(
            potential_coefficient * cumulative_coefficient_square
        )
        historical_bound_component = (
            full_no_path_exploration - statistical_bound_component
        )
        path_inflation_component = (
            actual_sharp_exploration - full_no_path_exploration
        )
        current_bias_cumulative = 2.0 * cumulative_bias
        sharp_bound = math.sqrt(
            (
                resolved.noise_std**2
                + resolved.feature_bound**2 / resolved.ridge
            )
            * gamma_after
            * cumulative_coefficient_square
        ) + 2.0 * cumulative_bias
        simple_bound = 2.0 * math.sqrt(
            (
                resolved.noise_std**2
                + resolved.feature_bound**2 / resolved.ridge
            )
            * gamma_after
            * cumulative_simple_square
        ) + 2.0 * cumulative_bias
        _record_failure(
            failures,
            "sharp_bound_decomposition",
            abs(
                statistical_bound_component
                + historical_bound_component
                + path_inflation_component
                + current_bias_cumulative
                - sharp_bound
            ),
            resolved.tolerance.value(sharp_bound),
        )
        cumulative_status = "not_applicable"
        if selected_method == "transport_hessian":
            cumulative_status = "premise_false"
            if prefix_reference_confidence:
                cumulative_status = "satisfied"
                if cumulative_regret > sharp_bound + scalar_tolerance:
                    cumulative_status = "bound_violation_on_event"
                    failures.append(
                        "sharp_cumulative_regret_bound_on_event: "
                        f"regret={cumulative_regret:.17g}, rhs={sharp_bound:.17g}"
                    )
                if cumulative_regret > simple_bound + scalar_tolerance:
                    failures.append(
                        "simple_cumulative_regret_bound_on_event: "
                        f"regret={cumulative_regret:.17g}, rhs={simple_bound:.17g}"
                    )

        theta_next, optimizer_diagnostics = projected_gradient_update(
            history.statistics,
            theta,
            environment,
            optimizer=optimizer_spec,
            training_ridge=resolved.training_ridge,
            theta_radius=resolved.theta_radius,
        )
        radius_tolerance = resolved.tolerance.value(theta_next, resolved.theta_radius)
        _record_failure(
            failures,
            "parameter_radius",
            max(0.0, float(np.linalg.norm(theta_next)) - resolved.theta_radius),
            radius_tolerance,
        )
        if not np.all(np.isfinite(theta_next)):
            failures.append("optimizer_nonfinite")
        all_failures.extend(f"round {round_number}: {failure}" for failure in failures)

        frozen_eigenvalues = np.linalg.eigvalsh(frozen_before)
        current_eigenvalues = np.linalg.eigvalsh(current_metric)
        d_q_values.append(d_q)
        endpoint_values.append(endpoint_distance)
        record: dict[str, Any] = {
            "round": round_number,
            "context": stream.contexts[round_index].tolist(),
            "context_index": context_id,
            "true_means": true_means.tolist(),
            "optimal_action": optimal_action,
            "selected_action": selected_action,
            "selected_reward": reward,
            "selected_noise": noise,
            "instantaneous_pseudo_regret": pseudo_regret,
            "cumulative_pseudo_regret": cumulative_regret,
            "optimality_gap": optimality_gap,
            "theta_t_norm": float(np.linalg.norm(theta)),
            "theta_t_minus_theta_previous_norm": float(np.linalg.norm(theta - previous_theta)),
            "theta_next_norm": float(np.linalg.norm(theta_next)),
            "optimizer_objective": optimizer_diagnostics.objective,
            "optimizer_gradient_norm": optimizer_diagnostics.gradient_norm,
            "optimizer_projection_occurred": optimizer_diagnostics.projection_occurred,
            "optimizer_projection_count": optimizer_diagnostics.projection_count,
            "optimizer_parameter_displacement": optimizer_diagnostics.displacement_norm,
            "Q_t": q_value,
            "gamma_t_minus_1": gamma_before,
            "gamma_t": gamma_after,
            "beta_t_corr": beta,
            "beta_stat": beta_statistical,
            "beta_hist": beta_historical,
            "historical_radius_contribution": beta_historical,
            "historical_certified_error_energy": historical_error_energy_before,
            "current_certified_bias": current_bias,
            "current_bias": current_bias,
            "actual_historical_remainder_energy": float(
                actual_historical_before @ actual_historical_before
            ),
            "actual_historical_remainder_max_abs": (
                float(np.max(np.abs(actual_historical_before)))
                if actual_historical_before.size
                else 0.0
            ),
            "actual_current_remainders": actual_current_remainders.tolist(),
            "frozen_metric_min_eigenvalue": float(frozen_eigenvalues[0]),
            "frozen_metric_max_eigenvalue": float(frozen_eigenvalues[-1]),
            "frozen_metric_condition_number": float(frozen_eigenvalues[-1] / frozen_eigenvalues[0]),
            "current_metric_min_eigenvalue": float(current_eigenvalues[0]),
            "current_metric_max_eigenvalue": float(current_eigenvalues[-1]),
            "current_metric_condition_number": float(
                current_eigenvalues[-1] / current_eigenvalues[0]
            ),
            "frozen_widths": frozen_widths.tolist(),
            "current_widths": current_widths.tolist(),
            "bar_D_t_Q": d_q,
            "D_Q": d_q,
            "endpoint_thompson_distance": endpoint_distance,
            "d_Th": endpoint_distance,
            "endpoint_generalized_eigenvalues": endpoint_eigenvalues.tolist(),
            "factor_path_length_quad": path_length,
            "D_path_quad": path_length,
            "factor_path_length_half_order": half_path_length,
            "exp_bar_D_over_2": hessian_inflation,
            "exp_endpoint_distance_over_2": endpoint_inflation,
            "D_Q_minus_d_Th": d_q - endpoint_distance,
            "d_Th_minus_D_Q": d_th_minus_d_q,
            "D_Q_over_d_Th": (
                d_q / endpoint_distance
                if endpoint_distance > scalar_tolerance
                else None
            ),
            "D_Q_over_path_quad": (
                d_q / path_length
                if path_length is not None and path_length > scalar_tolerance
                else None
            ),
            "reference_confidence_all_actions": reference_confidence,
            "transport_optimism_all_actions": hessian_optimism,
            "method_optimism_all_actions": method_optimism,
            "reference_confidence_min_margin": float(np.min(confidence_margins)),
            "reference_confidence_max_margin": float(np.max(confidence_margins)),
            "reference_confidence_max_shortfall": float(max(0.0, -np.min(confidence_margins))),
            "transport_optimism_min_margin": float(np.min(hessian_optimism_margins)),
            "transport_optimism_max_margin": float(np.max(hessian_optimism_margins)),
            "transport_optimism_max_shortfall": float(max(0.0, -np.min(hessian_optimism_margins))),
            "prefix_simultaneous_reference_confidence": prefix_reference_confidence,
            "prefix_simultaneous_transport_optimism": prefix_hessian_optimism,
            "prefix_simultaneous_method_optimism": prefix_method_optimism,
            "scores": scores.tolist(),
            "corrected_centers": corrected_centers.tolist(),
            "hessian_transport_scores": hessian_scores.tolist(),
            "endpoint_transport_scores": endpoint_scores.tolist(),
            "frozen_reference_scores": frozen_scores.tolist(),
            "naive_current_scores": naive_scores.tolist(),
            "method_certified": selected_method != "naive_current",
            "pseudo_response": pseudo_response,
            "pseudo_response_identity_residual": pseudo_response - pseudo_identity_rhs,
            "ridge_normal_equation_residual": ridge_normal_equation_residual,
            "corrected_center_identity_max_residual": float(
                np.max(np.abs(center_identity_residuals))
            ),
            "frozen_gram_recursion_residual": frozen_gram_recursion_residual,
            "information_gain_recursion_residual": (
                information_gain_recursion_residual
            ),
            "cumulative_information_gain_residual": (
                cumulative_information_gain_residual
            ),
            "endpoint_lower_sandwich_min_eigenvalue": (
                endpoint_lower_min_eigenvalue
            ),
            "endpoint_upper_sandwich_min_eigenvalue": (
                endpoint_upper_min_eigenvalue
            ),
            "endpoint_lower_sandwich_shortfall": endpoint_lower_shortfall,
            "endpoint_upper_sandwich_shortfall": endpoint_upper_shortfall,
            "frozen_to_current_width_transport_max_shortfall": (
                frozen_to_current_shortfall
            ),
            "current_to_frozen_width_transport_max_shortfall": (
                current_to_frozen_shortfall
            ),
            "path_lower_shortfall": path_lower_shortfall,
            "path_upper_shortfall": path_upper_shortfall,
            "frozen_width_sum": cumulative_width_square,
            "width_sum": cumulative_width_square,
            "frozen_potential_upper_bound": potential_bound,
            "potential_upper": potential_bound,
            "potential_slack": potential_slack,
            "played_frozen_width": selected_frozen_width,
            "instantaneous_theorem_rhs": instantaneous_bound,
            "instantaneous_bound_status": instantaneous_status,
            "sharp_cumulative_theorem_rhs": sharp_bound,
            "sharp_theorem_rhs": sharp_bound,
            "simple_cumulative_theorem_rhs": simple_bound,
            "simple_theorem_rhs": simple_bound,
            "statistical_bound_component": statistical_bound_component,
            "historical_bound_component": historical_bound_component,
            "path_inflation_component": path_inflation_component,
            "current_bias_cumulative": current_bias_cumulative,
            "cumulative_bound_status": cumulative_status,
            "deterministic_audit_failures": tuple(failures),
            "deterministic_audit_failure_count": len(failures),
            "deterministic_audit_passed": not failures,
            "algebra_tolerance": scalar_tolerance,
            "numerical_check_class": "dense floating-point diagnostic",
            "quadrature_check_class": "quadrature diagnostic" if path_length is not None else None,
            "confidence_check_class": "statistical confidence event",
        }
        records.append(record)
        previous_theta = theta
        theta = theta_next
        last_optimizer = optimizer_diagnostics
        last_sharp_bound = sharp_bound
        last_simple_bound = simple_bound
        last_gamma = gamma_after
        last_potential_bound = potential_bound

    positive_regret = cumulative_regret > 0.0
    summary: dict[str, Any] = {
        "method": selected_method,
        "method_certified": selected_method != "naive_current",
        "seed": int(seed),
        "profile": resolved.profile,
        "horizon": rounds,
        "rounds": rounds,
        "target_D": target,
        "W": width,
        "width_W": width,
        "feature_dimension": FEATURE_DIMENSION,
        "category_count": CATEGORY_COUNT,
        "cumulative_pseudo_regret": cumulative_regret,
        "simultaneous_reference_confidence": prefix_reference_confidence,
        "simultaneous_transport_optimism": prefix_hessian_optimism,
        "simultaneous_method_optimism": prefix_method_optimism,
        "deterministic_audit_passed": not all_failures,
        "deterministic_audit_pass": not all_failures,
        "deterministic_audit_failure_count": len(all_failures),
        "deterministic_audit_failures": tuple(all_failures),
        "max_realized_D_Q": max(d_q_values, default=0.0),
        "max_endpoint_thompson_distance": max(endpoint_values, default=0.0),
        "max_factor_path_length_quad": max(path_lengths, default=None),
        "max_quadrature_order_difference": max(path_half_differences, default=None),
        "sharp_cumulative_theorem_rhs": last_sharp_bound,
        "sharp_theorem_rhs": last_sharp_bound,
        "simple_cumulative_theorem_rhs": last_simple_bound,
        "simple_theorem_rhs": last_simple_bound,
        "statistical_bound_component": statistical_bound_component,
        "historical_bound_component": historical_bound_component,
        "path_inflation_component": path_inflation_component,
        "current_bias_cumulative": current_bias_cumulative,
        "sharp_over_simple_rhs": (
            last_sharp_bound / last_simple_bound if last_simple_bound > 0.0 else None
        ),
        "positive_regret_for_ratio": positive_regret,
        "zero_regret": not positive_regret,
        "sharp_rhs_over_positive_regret": (
            last_sharp_bound / cumulative_regret if positive_regret else None
        ),
        "frozen_width_sum": cumulative_width_square,
        "width_sum": cumulative_width_square,
        "frozen_potential_upper_bound": last_potential_bound,
        "potential_upper": last_potential_bound,
        "frozen_width_sum_over_potential": (
            cumulative_width_square / last_potential_bound
            if last_potential_bound > 0.0
            else None
        ),
        "gamma_T": last_gamma,
        "final_theta_norm": float(np.linalg.norm(theta)),
        "final_optimizer_objective": last_optimizer.objective,
        "final_optimizer_gradient_norm": last_optimizer.gradient_norm,
        "floating_point_checks_are_verified_certificates": False,
        **_environment_summary(stream),
    }
    return PolicyTrajectory(
        method=selected_method,
        seed=int(seed),
        horizon=rounds,
        target_d=target,
        width=width,
        optimizer=optimizer_spec,
        rounds=tuple(records),
        summary=summary,
        child_seeds=child_seeds,
    )


def run_tuning_trajectory(
    config: Mapping[str, Any],
    seed: int,
    horizon: int,
    target_d: float,
    optimizer: OptimizerSpec | Mapping[str, Any],
) -> TuningTrajectory:
    """Evaluate one optimizer on a shared uniformly random behavior stream."""

    rounds = _positive_int(horizon, name="horizon")
    target = _positive_float(target_d, name="target_d")
    optimizer_spec = (
        optimizer
        if isinstance(optimizer, OptimizerSpec)
        else OptimizerSpec.from_mapping(optimizer)
    )
    resolved = _ResolvedConfig.from_mapping(config, rounds)
    width = target_width(
        rounds,
        target,
        feature_bound=resolved.feature_bound,
        theta_radius=resolved.theta_radius,
        noise_std=resolved.noise_std,
        ridge=resolved.ridge,
    )
    environment = ScaledTanhEnvironment(
        width=width,
        feature_bound=resolved.feature_bound,
        theta_radius=resolved.theta_radius,
        noise_std=resolved.noise_std,
        teacher_seed=resolved.teacher_seed,
    )
    child_seeds = {
        "context_stream": derive_child_seed(
            seed, "transport_instantiation/context/v1"
        ),
        "potential_noise_table": derive_child_seed(
            seed, "transport_instantiation/potential_noise/v1"
        ),
        "teacher_construction": int(resolved.teacher_seed),
        "behavior_policy_tuning_stream": derive_child_seed(
            seed, "transport_instantiation/behavior_policy/v1"
        ),
        "bootstrap_aggregation": derive_child_seed(
            seed, "transport_instantiation/bootstrap/v1"
        ),
    }
    stream = build_potential_outcome_stream(
        environment,
        rounds,
        context_seed=child_seeds["context_stream"],
        noise_seed=child_seeds["potential_noise_table"],
    )
    behavior_rng = np.random.default_rng(child_seeds["behavior_policy_tuning_stream"])
    behavior_actions = behavior_rng.integers(
        0, ACTION_COUNT, size=rounds, dtype=np.int64
    )
    history = TransportHistory(resolved.ridge, resolved.noise_std)
    theta = np.zeros(FEATURE_DIMENSION, dtype=np.float64)
    records: list[dict[str, Any]] = []
    mse_values: list[float] = []
    rejection_reasons: list[str] = []
    projection_count = 0
    cumulative_log_increments = 0.0
    for round_index in range(rounds):
        round_number = round_index + 1
        context_id = int(stream.context_indices[round_index])
        action_features = environment.features[context_id]
        predicted = np.asarray(
            environment.mean(theta, action_features),
            dtype=np.float64,
        )
        true = stream.true_means[round_index]
        mse = float(np.mean((predicted - true) ** 2))
        if round_number > resolved.tuning_burn_in:
            mse_values.append(mse)
        action = int(behavior_actions[round_index])
        reward = float(stream.rewards[round_index, action])
        noise = float(stream.noises[round_index, action])
        category = context_id * ACTION_COUNT + action
        failures: list[str] = []
        try:
            frozen_before = history.frozen_metric.copy()
            current_metric = history.statistics.current_metric(
                theta, environment, ridge=resolved.ridge
            )
            _cholesky(frozen_before, name="tuning_frozen_metric")
            _cholesky(current_metric, name="tuning_current_metric")
            theta_hat = cholesky_solve(frozen_before, history.frozen_rhs)
            normal_equation_residual = float(
                np.linalg.norm(frozen_before @ theta_hat - history.frozen_rhs)
            )
            queries = environment.gradient(theta, action_features)
            centers = corrected_center(theta, theta_hat, action_features, environment)
            current_remainders = np.asarray(
                true
                - predicted
                - queries @ (environment.theta_star - theta),
                dtype=np.float64,
            )
            center_rhs = (
                queries @ (environment.theta_star - theta_hat)
                + current_remainders
            )
            center_identity_residual = float(
                np.max(np.abs(true - centers - center_rhs))
            )
            gamma_before = information_gain(frozen_before, resolved.ridge)
            selected_query = queries[action]
            pseudo_response = (
                reward - float(predicted[action]) + float(selected_query @ theta)
            )
            actual_remainder = float(current_remainders[action])
            pseudo_identity_rhs = (
                float(selected_query @ environment.theta_star)
                + actual_remainder
                + noise
            )
            pseudo_identity_residual = abs(pseudo_response - pseudo_identity_rhs)
            envelope = certified_linearization_envelope(
                theta,
                theta_radius=resolved.theta_radius,
                lipschitz_mean=environment.lipschitz_mean,
            )
            scalar_tolerance = resolved.tolerance.value(
                reward,
                pseudo_response,
                centers,
                true,
                gamma_before,
            )
            _record_failure(
                failures,
                "ridge_normal_equation",
                normal_equation_residual,
                resolved.tolerance.value(frozen_before, history.frozen_rhs),
            )
            _record_failure(
                failures,
                "corrected_center_identity",
                center_identity_residual,
                scalar_tolerance,
            )
            _record_failure(
                failures,
                "pseudo_response_identity",
                pseudo_identity_residual,
                scalar_tolerance,
            )
            history.append(
                category=category,
                collection_theta=theta,
                collection_query=selected_query,
                pseudo_response=pseudo_response,
                reward=reward,
                noise=noise,
                certified_envelope=envelope,
                actual_remainder=actual_remainder,
            )
            expected_frozen = frozen_before + np.outer(
                selected_query, selected_query
            ) / (resolved.noise_std**2)
            gram_residual = float(
                np.linalg.norm(history.frozen_metric - expected_frozen, ord=2)
            )
            _record_failure(
                failures,
                "frozen_gram_recursion",
                gram_residual,
                resolved.tolerance.value(history.frozen_metric, expected_frozen),
            )
            gamma_after = information_gain(history.frozen_metric, resolved.ridge)
            selected_width = float(
                inverse_quadratic_widths(
                    frozen_before, selected_query[np.newaxis, :]
                )[0]
            )
            log_increment = math.log1p(
                selected_width**2 / (resolved.noise_std**2)
            )
            information_residual = abs(
                (gamma_after - gamma_before) - log_increment
            )
            cumulative_log_increments += log_increment
            cumulative_information_residual = abs(
                gamma_after - cumulative_log_increments
            )
            _record_failure(
                failures,
                "information_gain_recursion",
                information_residual,
                resolved.tolerance.value(gamma_after, gamma_before, log_increment),
            )
            _record_failure(
                failures,
                "cumulative_information_gain_identity",
                cumulative_information_residual,
                resolved.tolerance.value(gamma_after, cumulative_log_increments),
            )
            theta_next, diagnostics = projected_gradient_update(
                history.statistics,
                theta,
                environment,
                optimizer=optimizer_spec,
                training_ridge=resolved.training_ridge,
                theta_radius=resolved.theta_radius,
            )
        except (
            ArithmeticError,
            FloatingPointError,
            TransportInstantiationError,
            ValueError,
        ) as error:
            rejection_reasons.append(f"round {round_number}: {error}")
            break
        norm = float(np.linalg.norm(theta_next))
        tolerance = resolved.tolerance.value(theta_next, resolved.theta_radius)
        if norm > resolved.theta_radius + tolerance:
            rejection_reasons.append(
                f"round {round_number}: parameter radius exceeded ({norm})"
            )
            break
        if failures:
            rejection_reasons.extend(
                f"round {round_number}: {failure}" for failure in failures
            )
            break
        projection_count += diagnostics.projection_count
        records.append(
            {
                "round": round_number,
                "context_index": context_id,
                "behavior_action": action,
                "prediction_mse_all_actions": mse,
                "included_after_burn_in": round_number > resolved.tuning_burn_in,
                "theta_norm": float(np.linalg.norm(theta)),
                "theta_next_norm": norm,
                "optimizer_objective": diagnostics.objective,
                "optimizer_gradient_norm": diagnostics.gradient_norm,
                "optimizer_projection_occurred": diagnostics.projection_occurred,
                "optimizer_projection_count": diagnostics.projection_count,
                "ridge_normal_equation_residual": normal_equation_residual,
                "corrected_center_identity_residual": center_identity_residual,
                "pseudo_response_identity_residual": pseudo_identity_residual,
                "frozen_gram_recursion_residual": gram_residual,
                "information_gain_recursion_residual": information_residual,
                "cumulative_information_gain_residual": (
                    cumulative_information_residual
                ),
                "frozen_metric_min_eigenvalue": float(
                    np.linalg.eigvalsh(frozen_before)[0]
                ),
                "current_metric_min_eigenvalue": float(
                    np.linalg.eigvalsh(current_metric)[0]
                ),
                "deterministic_audit_passed": True,
            }
        )
        theta = theta_next
    valid = not rejection_reasons and len(records) == rounds and bool(mse_values)
    if not mse_values:
        rejection_reasons.append("no post-burn-in prediction errors were recorded")
    summary = {
        "seed": int(seed),
        "profile": resolved.profile,
        "horizon": rounds,
        "target_D": target,
        "W": width,
        "width_W": width,
        "learning_rate": optimizer_spec.learning_rate,
        "steps_per_round": optimizer_spec.steps_per_round,
        "burn_in": resolved.tuning_burn_in,
        "mean_all_action_prediction_mse": (
            float(np.mean(mse_values)) if valid else None
        ),
        "median_all_action_prediction_mse": (
            float(np.median(mse_values)) if valid else None
        ),
        "projection_count": projection_count,
        "valid": valid,
        "deterministic_audit_pass": valid,
        "deterministic_audit_failure_count": len(rejection_reasons),
        "rejection_reasons": tuple(rejection_reasons),
        "completed_rounds": len(records),
        "behavior_stream_is_uniform_random": True,
        "behavior_stream_independent_of_optimizer": True,
    }
    return TuningTrajectory(
        seed=int(seed),
        horizon=rounds,
        target_d=target,
        width=width,
        optimizer=optimizer_spec,
        rounds=tuple(records),
        summary=summary,
        child_seeds=child_seeds,
    )


__all__ = [
    "ACTION_COUNT",
    "CATEGORY_COUNT",
    "CONTEXT_COUNT",
    "CONTEXT_DIMENSION",
    "FEATURE_DIMENSION",
    "SUPPORTED_METHODS",
    "CategorySufficientStatistics",
    "NumericalTolerance",
    "OptimizerDiagnostics",
    "OptimizerSpec",
    "PolicyTrajectory",
    "PotentialOutcomeStream",
    "ScaledTanhEnvironment",
    "TransportHistory",
    "TransportInstantiationError",
    "TuningTrajectory",
    "build_context_stream",
    "build_potential_noise_table",
    "build_potential_outcome_stream",
    "canonical_method",
    "cholesky_solve",
    "certified_linearization_envelope",
    "condition_token",
    "confidence_radius",
    "context_index",
    "corrected_center",
    "derive_child_seed",
    "enumerate_contexts",
    "factor_path_length",
    "feature_table",
    "inverse_quadratic_widths",
    "information_gain",
    "logdet_spd",
    "normalized_feature",
    "policy_scores",
    "projected_gradient_update",
    "regular_simplex_teacher",
    "run_policy_trajectory",
    "run_tuning_trajectory",
    "scaled_tanh_gradient",
    "scaled_tanh_hessian_vector_product",
    "scaled_tanh_mean",
    "smoothness_constant",
    "target_width",
    "thompson_distance",
    "hessian_q_path_certificate",
]
