"""Real-label, realizable, and controlled-misspecification environments."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .data import canonical_array_digest, canonical_json, PreparedDataset
from .features import FeatureMapSpec
from .model import scaled_tanh_gradient, scaled_tanh_mean
from .preprocessing import (
    DatasetSplit,
    deterministic_split,
    fit_preprocessing,
    PreprocessingTransform,
)
from .teacher import (
    build_misspecification,
    fit_ridge_teacher,
    MisspecificationSpec,
    RidgeTeacher,
)


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]

LABEL_TASK = "covtype_label_bandit"
REALIZABLE_TASK = "covtype_semisynthetic_realizable"
CONTROLLED_MISSPECIFIED_TASK = "covtype_semisynthetic_misspecified"
SUPPORTED_TASKS = (LABEL_TASK, REALIZABLE_TASK, CONTROLLED_MISSPECIFIED_TASK)


class EnvironmentError(RuntimeError):
    """Raised when a task cannot satisfy its deterministic contract."""


def _readonly(array: np.ndarray) -> np.ndarray:
    array.setflags(write=False)
    return array


def _nested(config: Mapping[str, Any], paths: tuple[str, ...], default: Any) -> Any:
    for path in paths:
        value: Any = config
        found = True
        for component in path.split("."):
            if not isinstance(value, Mapping) or component not in value:
                found = False
                break
            value = value[component]
        if found:
            return value
    return default


def derive_seed(master_seed: int, *namespace: object) -> int:
    """Derive a stable 63-bit NumPy seed from explicit namespace components."""

    if isinstance(master_seed, bool) or not isinstance(master_seed, (int, np.integer)):
        raise TypeError("master_seed must be an integer")
    if int(master_seed) < 0:
        raise ValueError("master_seed must be nonnegative")
    payload = canonical_json([int(master_seed), *namespace]).encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & ((1 << 63) - 1)


def smoothness_constant(feature_bound: float) -> float:
    bound = float(feature_bound)
    if not np.isfinite(bound) or bound <= 0.0:
        raise ValueError("feature_bound must be finite and positive")
    return 4.0 * bound * bound / (3.0 * math.sqrt(3.0))


def target_width(
    horizon: int,
    target_d: float,
    *,
    feature_bound: float,
    theta_radius: float,
    noise_proxy: float,
    ridge: float,
) -> float:
    """Use the existing experiment's exact W(T, D_target) design rule."""

    if isinstance(horizon, bool) or not isinstance(horizon, (int, np.integer)):
        raise TypeError("horizon must be an integer")
    horizon = int(horizon)
    values = [target_d, feature_bound, theta_radius, noise_proxy, ridge]
    if horizon < 2 or any(not np.isfinite(value) or value <= 0.0 for value in values):
        raise ValueError("target-width inputs must be finite and positive")
    numerator = (
        4.0
        * smoothness_constant(feature_bound)
        * theta_radius
        * math.sqrt(float(horizon - 1))
    )
    width = (numerator / (noise_proxy * math.sqrt(ridge) * target_d)) ** 2
    if not np.isfinite(width) or width <= 0.0:
        raise FloatingPointError("target-width calculation produced an invalid value")
    return float(width)


@dataclass(frozen=True)
class PolicyRound:
    """The only pre-action information passed to a policy."""

    context: FloatArray
    action_features: FloatArray

    def __post_init__(self) -> None:
        context = np.asarray(self.context, dtype=np.float64)
        features = np.asarray(self.action_features, dtype=np.float64)
        if context.ndim != 1 or features.ndim != 2:
            raise ValueError("policy round arrays have the wrong rank")
        if features.shape[0] < 2:
            raise ValueError("policy round must contain at least two actions")
        if not np.all(np.isfinite(context)) or not np.all(np.isfinite(features)):
            raise ValueError("policy round contains nonfinite values")
        object.__setattr__(self, "context", _readonly(context.copy()))
        object.__setattr__(self, "action_features", _readonly(features.copy()))


@dataclass(frozen=True)
class PotentialOutcomeStream:
    """Paired environment stream with a selected-reward-only policy interface."""

    task_name: str
    seed: int
    phase: str
    row_indices: IntArray
    contexts: FloatArray
    _labels: IntArray = field(repr=False)
    means: FloatArray = field(repr=False)
    noises: FloatArray = field(repr=False)
    rewards: FloatArray = field(repr=False)
    _feature_map: FeatureMapSpec = field(repr=False)

    def __post_init__(self) -> None:
        row_indices = np.asarray(self.row_indices, dtype=np.int64)
        contexts = np.asarray(self.contexts, dtype=np.float64)
        labels = np.asarray(self._labels, dtype=np.int64)
        means = np.asarray(self.means, dtype=np.float64)
        noises = np.asarray(self.noises, dtype=np.float64)
        rewards = np.asarray(self.rewards, dtype=np.float64)
        rounds = row_indices.size
        actions = self._feature_map.action_count
        if contexts.shape != (rounds, self._feature_map.context_dimension):
            raise ValueError("stream contexts have the wrong shape")
        if labels.shape != (rounds,):
            raise ValueError("stream labels have the wrong shape")
        expected = (rounds, actions)
        if (
            means.shape != expected
            or noises.shape != expected
            or rewards.shape != expected
        ):
            raise ValueError("potential-outcome tables have the wrong shape")
        if not all(
            np.all(np.isfinite(value)) for value in (contexts, means, noises, rewards)
        ):
            raise ValueError("potential-outcome stream contains nonfinite values")
        if not np.array_equal(rewards, means + noises):
            raise ValueError("rewards are inconsistent with means and noises")
        for name, value in (
            ("row_indices", row_indices),
            ("contexts", contexts),
            ("_labels", labels),
            ("means", means),
            ("noises", noises),
            ("rewards", rewards),
        ):
            object.__setattr__(self, name, _readonly(value.copy()))

    @property
    def rounds(self) -> int:
        return int(self.row_indices.size)

    @property
    def action_count(self) -> int:
        return self._feature_map.action_count

    @property
    def digest(self) -> str:
        return canonical_array_digest(
            {
                "contexts": self.contexts,
                "labels": self._labels,
                "means": self.means,
                "noises": self.noises,
                "rewards": self.rewards,
                "row_indices": self.row_indices,
            }
        )

    def policy_round(self, round_index: int) -> PolicyRound:
        index = int(round_index)
        if not 0 <= index < self.rounds:
            raise IndexError("round index is out of range")
        context = self.contexts[index]
        return PolicyRound(
            context=context,
            action_features=self._feature_map.all_action_features(context),
        )

    def observe(self, round_index: int, action: int) -> float:
        """Reveal exactly one selected reward, never the potential-outcome row."""

        index = int(round_index)
        selected_action = int(action)
        if not 0 <= index < self.rounds:
            raise IndexError("round index is out of range")
        if not 0 <= selected_action < self.action_count:
            raise ValueError("action is out of range")
        return float(self.rewards[index, selected_action])

    def evaluation_label(self, round_index: int) -> int:
        """Return a label through an explicitly evaluator-only method."""

        index = int(round_index)
        if not 0 <= index < self.rounds:
            raise IndexError("round index is out of range")
        return int(self._labels[index])


@dataclass(frozen=True)
class TaskEnvironment:
    """One frozen truth model over a shared transformed context dataset."""

    task_name: str
    prepared: PreparedDataset
    split: DatasetSplit
    preprocessing: PreprocessingTransform
    contexts: FloatArray
    labels: IntArray = field(repr=False)
    feature_map: FeatureMapSpec
    width: float
    noise_proxy: float
    gaussian_noise_std: float
    teacher: RidgeTeacher
    misspecification: MisspecificationSpec | None
    theorem_applicable: bool

    def __post_init__(self) -> None:
        if self.task_name not in SUPPORTED_TASKS:
            raise ValueError(f"unknown task {self.task_name!r}")
        contexts = np.asarray(self.contexts, dtype=np.float64)
        labels = np.asarray(self.labels, dtype=np.int64)
        expected_context_shape = (
            self.prepared.features.shape[0],
            self.feature_map.context_dimension,
        )
        if contexts.shape != expected_context_shape:
            raise ValueError(
                f"transformed contexts have shape {contexts.shape}, expected {expected_context_shape}"
            )
        if labels.shape != (contexts.shape[0],):
            raise ValueError("labels do not match transformed contexts")
        if self.feature_map.action_count != self.prepared.action_count:
            raise ValueError("feature-map action count does not match prepared data")
        if np.any(
            np.linalg.norm(contexts, axis=1) > 1.0 + 64.0 * np.finfo(np.float64).eps
        ):
            raise ValueError("a transformed context exceeds the unit-norm bound")
        if not np.isfinite(self.width) or self.width <= 0.0:
            raise ValueError("width must be finite and positive")
        if not np.isfinite(self.noise_proxy) or self.noise_proxy <= 0.0:
            raise ValueError("noise_proxy must be finite and positive")
        if not np.isfinite(self.gaussian_noise_std) or self.gaussian_noise_std <= 0.0:
            raise ValueError("gaussian_noise_std must be finite and positive")
        if (
            self.task_name == CONTROLLED_MISSPECIFIED_TASK
            and self.misspecification is None
        ):
            raise ValueError(
                "controlled misspecification task requires a specification"
            )
        if (
            self.task_name != CONTROLLED_MISSPECIFIED_TASK
            and self.misspecification is not None
        ):
            raise ValueError("only the controlled task may carry misspecification")
        expected_applicability = self.task_name != LABEL_TASK
        if self.theorem_applicable != expected_applicability:
            raise ValueError("theorem_applicable is inconsistent with the task")
        object.__setattr__(self, "contexts", _readonly(contexts.copy()))
        object.__setattr__(self, "labels", _readonly(labels.copy()))

    @property
    def context_dimension(self) -> int:
        return self.feature_map.context_dimension

    @property
    def context_dim(self) -> int:
        return self.context_dimension

    @property
    def action_count(self) -> int:
        return self.feature_map.action_count

    @property
    def feature_dimension(self) -> int:
        return self.feature_map.feature_dimension

    @property
    def feature_dim(self) -> int:
        return self.feature_dimension

    @property
    def W(self) -> float:
        return self.width

    @property
    def theta_star(self) -> FloatArray | None:
        return None if self.task_name == LABEL_TASK else self.teacher.theta

    @property
    def rho(self) -> float:
        return 0.0 if self.misspecification is None else self.misspecification.rho

    @property
    def historical_misspecification_envelope(self) -> float | None:
        if self.task_name == LABEL_TASK:
            return None
        return self.rho

    @property
    def current_misspecification_envelope(self) -> float | None:
        return self.historical_misspecification_envelope

    def feature_matrix(self, context: ArrayLike) -> FloatArray:
        return self.feature_map.all_action_features(context)

    def learner_means(self, theta: ArrayLike, context: ArrayLike) -> FloatArray:
        return np.asarray(
            scaled_tanh_mean(theta, self.feature_matrix(context), self.width),
            dtype=np.float64,
        )

    def learner_gradients(self, theta: ArrayLike, context: ArrayLike) -> FloatArray:
        return scaled_tanh_gradient(theta, self.feature_matrix(context), self.width)

    def true_means(self, row_index: int) -> FloatArray:
        index = int(row_index)
        if not 0 <= index < self.contexts.shape[0]:
            raise IndexError("row index is out of range")
        if self.task_name == LABEL_TASK:
            means = np.full(self.action_count, 0.1, dtype=np.float64)
            means[int(self.labels[index])] = 0.9
            return means
        base = self.teacher.action_means(self.contexts[index], width=self.width)
        if self.misspecification is None:
            return base
        return np.asarray(
            base + self.misspecification.perturbation(self.contexts[index]),
            dtype=np.float64,
        )

    def build_stream(
        self, split: str | ArrayLike, seed: int, rounds: int
    ) -> PotentialOutcomeStream:
        return build_stream(self, split, seed, rounds)


def _context_order(pool: IntArray, *, seed: int, phase: str, rounds: int) -> IntArray:
    if isinstance(rounds, bool) or not isinstance(rounds, (int, np.integer)):
        raise TypeError("rounds must be an integer")
    count = int(rounds)
    if count <= 0:
        raise ValueError("rounds must be positive")
    if count > pool.size:
        raise ValueError(
            f"requested {count} rounds from a split containing only {pool.size} rows"
        )
    rng = np.random.default_rng(
        derive_seed(seed, "realistic-transport/context/v1", phase)
    )
    permutation = np.asarray(rng.permutation(pool), dtype=np.int64)
    return permutation[:count]


def build_stream(
    task: TaskEnvironment,
    split: str | ArrayLike,
    seed: int,
    rounds: int,
) -> PotentialOutcomeStream:
    """Build context and all-action potential outcomes before policy execution."""

    if isinstance(split, str):
        phase = split
        pool = task.split.phase_indices(split)
    else:
        phase = "custom"
        pool = np.asarray(split, dtype=np.int64)
        if pool.ndim != 1 or pool.size == 0:
            raise ValueError("custom split must be a nonempty index vector")
        if np.any(pool < 0) or np.any(pool >= task.contexts.shape[0]):
            raise ValueError("custom split contains an out-of-range row")
        phase = f"custom:{canonical_array_digest({'indices': pool})}"
    row_indices = _context_order(pool, seed=seed, phase=phase, rounds=rounds)
    contexts = task.contexts[row_indices]
    labels = task.labels[row_indices]
    means = np.stack([task.true_means(int(index)) for index in row_indices], axis=0)
    if task.task_name == LABEL_TASK:
        rng = np.random.default_rng(
            derive_seed(
                seed, "realistic-transport/potential-outcomes/bernoulli/v1", phase
            )
        )
        uniforms = rng.random(size=means.shape)
        rewards = (uniforms < means).astype(np.float64)
        noises = rewards - means
    else:
        # Tasks B and C deliberately share the same Gaussian noise table.
        rng = np.random.default_rng(
            derive_seed(
                seed, "realistic-transport/potential-outcomes/gaussian/v1", phase
            )
        )
        noises = rng.normal(0.0, task.gaussian_noise_std, size=means.shape)
        rewards = means + noises
    return PotentialOutcomeStream(
        task_name=task.task_name,
        seed=int(seed),
        phase=phase,
        row_indices=row_indices,
        contexts=contexts,
        _labels=labels,
        means=means,
        noises=noises,
        rewards=rewards,
        _feature_map=task.feature_map,
    )


def build_potential_outcome_stream(
    task: TaskEnvironment,
    split: str | ArrayLike,
    seed: int,
    rounds: int,
) -> PotentialOutcomeStream:
    return build_stream(task, split, seed, rounds)


def build_task_environment(
    prepared: PreparedDataset,
    task_name: str,
    config: Mapping[str, Any],
    *,
    split: DatasetSplit | None = None,
    preprocessing: PreprocessingTransform | None = None,
) -> TaskEnvironment:
    """Resolve one task without fitting anything on tuning or evaluation rows."""

    if task_name not in SUPPORTED_TASKS:
        raise ValueError(f"unknown task {task_name!r}; choose from {SUPPORTED_TASKS}")
    selected_split = split or deterministic_split(
        prepared.features.shape[0], prepared.content_digest
    )
    rank = int(
        _nested(
            config,
            (
                "preprocessing.projection_dimension",
                "preprocessing.rank",
                "context_dimension",
                "p",
            ),
            16,
        )
    )
    transform = preprocessing or fit_preprocessing(
        prepared.features,
        selected_split.development,
        prepared_data_digest=prepared.content_digest,
        rank=rank,
    )
    if transform.prepared_data_digest != prepared.content_digest:
        raise EnvironmentError("preprocessing artifact belongs to another dataset")
    if transform.development_index_digest != canonical_array_digest(
        {"indices": np.asarray(selected_split.development, dtype=np.int64)}
    ):
        raise EnvironmentError(
            "preprocessing artifact was not fit on this development split"
        )
    contexts = transform.transform(prepared.features)
    feature_bound = float(
        _nested(
            config,
            ("feature_map.bound", "feature_map.feature_bound", "feature_bound"),
            1.0,
        )
    )
    task_prefix = f"tasks.{task_name}"
    teacher_ridge = float(
        _nested(
            config,
            (
                f"{task_prefix}.teacher_ridge",
                "teacher.ridge",
                "teacher.lambda",
                "teacher_ridge",
            ),
            1.0,
        )
    )
    theta_radius = float(
        _nested(
            config,
            (
                f"{task_prefix}.teacher_norm",
                "model.theta_radius",
                "teacher.theta_radius",
                "theta_radius",
                "R",
            ),
            1.0,
        )
    )
    teacher = fit_ridge_teacher(
        contexts,
        prepared.labels,
        selected_split.development,
        action_count=prepared.action_count,
        ridge=teacher_ridge,
        theta_radius=theta_radius,
        feature_bound=feature_bound,
    )
    gaussian_noise_std = float(
        _nested(
            config,
            (
                f"{task_prefix}.noise_proxy",
                "environment.gaussian_noise_std",
                "environment.noise_std",
                "noise_std",
            ),
            0.25,
        )
    )
    noise_proxy = 0.5 if task_name == LABEL_TASK else gaussian_noise_std
    horizon = int(
        _nested(
            config,
            (
                "model.maximum_horizon",
                "horizons.maximum",
                "maximum_horizon",
                "horizon",
                "rounds",
            ),
            500,
        )
    )
    target_d = float(_nested(config, ("model.target_D", "target_D"), 1.0))
    ridge = float(_nested(config, ("ridge", "model.ridge"), 1.0))
    configured_width = _nested(config, ("model.width", "width"), None)
    width = (
        float(configured_width)
        if configured_width is not None
        else target_width(
            horizon,
            target_d,
            feature_bound=feature_bound,
            theta_radius=theta_radius,
            noise_proxy=noise_proxy,
            ridge=ridge,
        )
    )
    misspecification = None
    if task_name == CONTROLLED_MISSPECIFIED_TASK:
        misspecification = build_misspecification(
            contexts[selected_split.development],
            teacher,
            width=width,
            seed=int(
                _nested(
                    config,
                    (
                        f"{task_prefix}.misspecification_seed",
                        "misspecification.seed",
                        "misspecification_seed",
                    ),
                    271828,
                )
            ),
            quantile=float(
                _nested(
                    config,
                    (
                        f"{task_prefix}.range_quantile",
                        "misspecification.range_quantile",
                    ),
                    0.9,
                )
            ),
            fraction=float(
                _nested(
                    config,
                    (
                        f"{task_prefix}.range_scale",
                        "misspecification.fraction",
                    ),
                    0.25,
                )
            ),
        )
    return TaskEnvironment(
        task_name=task_name,
        prepared=prepared,
        split=selected_split,
        preprocessing=transform,
        contexts=contexts,
        labels=prepared.labels,
        feature_map=teacher.feature_map,
        width=width,
        noise_proxy=noise_proxy,
        gaussian_noise_std=gaussian_noise_std,
        teacher=teacher,
        misspecification=misspecification,
        theorem_applicable=task_name != LABEL_TASK,
    )


__all__ = [
    "CONTROLLED_MISSPECIFIED_TASK",
    "EnvironmentError",
    "LABEL_TASK",
    "PolicyRound",
    "PotentialOutcomeStream",
    "REALIZABLE_TASK",
    "SUPPORTED_TASKS",
    "TaskEnvironment",
    "build_potential_outcome_stream",
    "build_stream",
    "build_task_environment",
    "derive_seed",
    "smoothness_constant",
    "target_width",
]
