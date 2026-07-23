"""Small deterministic nonlinear contextual-bandit audit environment.

The student and teacher are single-hidden-layer tanh networks.  Parameters are
represented as displacements from a fixed, nonzero initialization.  This is the
same convention as the analysis: ridge regularization acts on the displacement,
and the deployed parameters are ``base_parameters + displacement``.

The default teacher shares the initialized backbone with the student and differs
only in its action-specific linear head.  Consequently the frozen-head regime is
an exactly realizable linear model, while the full-parameter regimes remain
smooth nonlinear models when their backbones move.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Final

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]

CONTEXT_DIMENSION: Final = 4
HIDDEN_WIDTH: Final = 4
ACTION_COUNT: Final = 5


def _finite_vector(value: ArrayLike, length: int, *, name: str) -> FloatArray:
    vector = np.asarray(value, dtype=np.float64)
    if vector.shape != (length,):
        raise ValueError(f"{name} must have shape ({length},), got {vector.shape}")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite values")
    return vector


def _nonnegative_integer(value: int, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


@dataclass(frozen=True)
class MLPLayout:
    """Flat-parameter layout for a tanh backbone and action-specific head."""

    context_dimension: int = CONTEXT_DIMENSION
    hidden_width: int = HIDDEN_WIDTH
    action_count: int = ACTION_COUNT

    def __post_init__(self) -> None:
        for field_name in ("context_dimension", "hidden_width", "action_count"):
            value = getattr(self, field_name)
            if isinstance(value, (bool, np.bool_)) or not isinstance(
                value, (int, np.integer)
            ):
                raise TypeError(f"{field_name} must be an integer")
            if int(value) <= 0:
                raise ValueError(f"{field_name} must be positive")

    @property
    def weight_count(self) -> int:
        return self.hidden_width * self.context_dimension

    @property
    def backbone_dimension(self) -> int:
        return self.weight_count + self.hidden_width

    @property
    def head_dimension(self) -> int:
        return self.action_count * self.hidden_width + self.action_count

    @property
    def parameter_dimension(self) -> int:
        return self.backbone_dimension + self.head_dimension

    @property
    def backbone_indices(self) -> NDArray[np.int64]:
        return np.arange(self.backbone_dimension, dtype=np.int64)

    @property
    def head_indices(self) -> NDArray[np.int64]:
        return np.arange(
            self.backbone_dimension, self.parameter_dimension, dtype=np.int64
        )

    def pack(
        self,
        input_weights: ArrayLike,
        hidden_bias: ArrayLike,
        output_weights: ArrayLike,
        output_bias: ArrayLike,
    ) -> FloatArray:
        w = np.asarray(input_weights, dtype=np.float64)
        b = np.asarray(hidden_bias, dtype=np.float64)
        v = np.asarray(output_weights, dtype=np.float64)
        c = np.asarray(output_bias, dtype=np.float64)
        expected = (
            (w, (self.hidden_width, self.context_dimension), "input_weights"),
            (b, (self.hidden_width,), "hidden_bias"),
            (v, (self.action_count, self.hidden_width), "output_weights"),
            (c, (self.action_count,), "output_bias"),
        )
        for array, shape, name in expected:
            if array.shape != shape:
                raise ValueError(f"{name} must have shape {shape}, got {array.shape}")
            if not np.all(np.isfinite(array)):
                raise ValueError(f"{name} must contain only finite values")
        return np.concatenate((w.reshape(-1), b, v.reshape(-1), c)).astype(
            np.float64, copy=False
        )

    def unpack(
        self, parameters: ArrayLike
    ) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
        flat = _finite_vector(
            parameters, self.parameter_dimension, name="parameters"
        )
        first = self.weight_count
        second = first + self.hidden_width
        third = second + self.action_count * self.hidden_width
        return (
            flat[:first].reshape(self.hidden_width, self.context_dimension),
            flat[first:second],
            flat[second:third].reshape(self.action_count, self.hidden_width),
            flat[third:],
        )


PARAMETER_DIMENSION: Final = MLPLayout().parameter_dimension


def default_base_parameters(layout: MLPLayout | None = None) -> FloatArray:
    """Return the fixed nonzero initialization used by the default audit."""

    resolved = MLPLayout() if layout is None else layout
    if resolved != MLPLayout():
        rng = np.random.default_rng(1729)
        w = rng.normal(
            0.0,
            0.55 / np.sqrt(float(resolved.context_dimension)),
            size=(resolved.hidden_width, resolved.context_dimension),
        )
        b = rng.normal(0.0, 0.06, size=resolved.hidden_width)
        v = rng.normal(
            0.0,
            0.18 / np.sqrt(float(resolved.hidden_width)),
            size=(resolved.action_count, resolved.hidden_width),
        )
        c = np.linspace(0.015, -0.015, resolved.action_count)
        return resolved.pack(w, b, v, c)

    w = np.array(
        [
            [1.20, 0.30, -0.20, 0.10],
            [-0.20, 1.10, 0.40, -0.30],
            [0.30, -0.40, 1.00, 0.50],
            [-0.50, 0.20, 0.30, 1.10],
        ],
        dtype=np.float64,
    )
    b = np.array([0.10, -0.05, 0.08, -0.02], dtype=np.float64)
    v = np.array(
        [
            [0.12, 0.02, -0.02, 0.00],
            [-0.10, 0.02, 0.02, 0.01],
            [0.01, 0.11, 0.01, -0.02],
            [0.01, -0.10, 0.01, 0.02],
            [-0.02, 0.00, 0.10, 0.03],
        ],
        dtype=np.float64,
    )
    c = np.zeros(ACTION_COUNT, dtype=np.float64)
    return resolved.pack(w, b, v, c)


def default_teacher_displacement(layout: MLPLayout | None = None) -> FloatArray:
    """Return a known teacher displacement with context-dependent rankings."""

    resolved = MLPLayout() if layout is None else layout
    base = default_base_parameters(resolved)
    w, b, base_v, base_c = resolved.unpack(base)
    if resolved == MLPLayout():
        teacher_v = np.array(
            [
                [0.80, 0.10, -0.10, 0.00],
                [-0.70, 0.10, 0.10, 0.05],
                [0.05, 0.75, 0.05, -0.10],
                [0.05, -0.70, 0.05, 0.10],
                [-0.10, 0.00, 0.65, 0.15],
            ],
            dtype=np.float64,
        )
        teacher_c = np.array([0.02, -0.01, 0.01, -0.02, 0.00], dtype=np.float64)
    else:
        rng = np.random.default_rng(2718)
        teacher_v = rng.normal(
            0.0,
            0.75 / np.sqrt(float(resolved.hidden_width)),
            size=(resolved.action_count, resolved.hidden_width),
        )
        teacher_c = np.linspace(0.02, -0.02, resolved.action_count)
    teacher_raw = resolved.pack(w, b, teacher_v, teacher_c)
    displacement = teacher_raw - base
    # Keep this invariant explicit: it is what makes frozen-head exactly linear.
    if np.any(displacement[resolved.backbone_indices] != 0.0):
        raise AssertionError("default teacher must share the initialized backbone")
    return np.asarray(displacement, dtype=np.float64)


class SmallTanhMLP:
    """Float64 tanh MLP with an analytic Jacobian of each action mean."""

    def __init__(
        self,
        layout: MLPLayout | None = None,
        *,
        base_parameters: ArrayLike | None = None,
    ) -> None:
        self.layout = MLPLayout() if layout is None else layout
        base = (
            default_base_parameters(self.layout)
            if base_parameters is None
            else _finite_vector(
                base_parameters,
                self.layout.parameter_dimension,
                name="base_parameters",
            ).copy()
        )
        base.setflags(write=False)
        self._base_parameters = base

    @property
    def base_parameters(self) -> FloatArray:
        return self._base_parameters

    @property
    def parameter_dimension(self) -> int:
        return self.layout.parameter_dimension

    @property
    def head_indices(self) -> NDArray[np.int64]:
        return self.layout.head_indices

    @property
    def backbone_indices(self) -> NDArray[np.int64]:
        return self.layout.backbone_indices

    def _raw_parts(
        self, displacement: ArrayLike
    ) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
        delta = _finite_vector(
            displacement, self.parameter_dimension, name="displacement"
        )
        return self.layout.unpack(self._base_parameters + delta)

    def hidden(self, displacement: ArrayLike, context: ArrayLike) -> FloatArray:
        x = _finite_vector(
            context, self.layout.context_dimension, name="context"
        )
        w, b, _, _ = self._raw_parts(displacement)
        return np.asarray(np.tanh(w @ x + b), dtype=np.float64)

    def means(self, displacement: ArrayLike, context: ArrayLike) -> FloatArray:
        h = self.hidden(displacement, context)
        _, _, v, c = self._raw_parts(displacement)
        return np.asarray(v @ h + c, dtype=np.float64)

    def mean(self, displacement: ArrayLike, context: ArrayLike, action: int) -> float:
        action_index = self._validate_action(action)
        return float(self.means(displacement, context)[action_index])

    def jacobians(self, displacement: ArrayLike, context: ArrayLike) -> FloatArray:
        """Return one exact mean Jacobian per action, shape ``(K, d)``."""

        delta = _finite_vector(
            displacement, self.parameter_dimension, name="displacement"
        )
        x = _finite_vector(
            context, self.layout.context_dimension, name="context"
        )
        w, b, v, _ = self.layout.unpack(self._base_parameters + delta)
        h = np.asarray(np.tanh(w @ x + b), dtype=np.float64)
        dh = 1.0 - h * h
        result = np.zeros(
            (self.layout.action_count, self.parameter_dimension), dtype=np.float64
        )
        w_end = self.layout.weight_count
        b_end = self.layout.backbone_dimension
        v_start = b_end
        c_start = v_start + self.layout.action_count * self.layout.hidden_width
        for action in range(self.layout.action_count):
            hidden_sensitivity = v[action] * dh
            result[action, :w_end] = np.outer(hidden_sensitivity, x).reshape(-1)
            result[action, w_end:b_end] = hidden_sensitivity
            block_start = v_start + action * self.layout.hidden_width
            result[action, block_start : block_start + self.layout.hidden_width] = h
            result[action, c_start + action] = 1.0
        return result

    def jacobian(
        self, displacement: ArrayLike, context: ArrayLike, action: int
    ) -> FloatArray:
        return self.jacobians(displacement, context)[self._validate_action(action)]

    def selected_jacobians(
        self,
        displacement: ArrayLike,
        contexts: ArrayLike,
        actions: ArrayLike,
    ) -> FloatArray:
        """Vectorize exact Jacobians for selected actions over replay samples."""

        delta = _finite_vector(
            displacement, self.parameter_dimension, name="displacement"
        )
        x = np.asarray(contexts, dtype=np.float64)
        selected_actions = np.asarray(actions)
        if (
            x.ndim != 2
            or x.shape[1] != self.layout.context_dimension
            or not np.all(np.isfinite(x))
        ):
            raise ValueError(
                "contexts must be a finite matrix with shape "
                f"(samples, {self.layout.context_dimension})"
            )
        if (
            selected_actions.ndim != 1
            or selected_actions.shape[0] != x.shape[0]
            or not np.issubdtype(selected_actions.dtype, np.integer)
        ):
            raise ValueError("actions must be an integer vector matching contexts")
        selected_actions = selected_actions.astype(np.int64, copy=False)
        if np.any(selected_actions < 0) or np.any(
            selected_actions >= self.layout.action_count
        ):
            raise ValueError("actions contain an out-of-range index")

        w, b, v, _ = self.layout.unpack(self._base_parameters + delta)
        hidden = np.tanh(x @ w.T + b[None, :])
        sensitivity = v[selected_actions] * (1.0 - hidden * hidden)
        result = np.zeros((x.shape[0], self.parameter_dimension), dtype=np.float64)
        w_end = self.layout.weight_count
        b_end = self.layout.backbone_dimension
        v_start = b_end
        c_start = v_start + self.layout.action_count * self.layout.hidden_width
        result[:, :w_end] = np.einsum("nh,ni->nhi", sensitivity, x).reshape(
            x.shape[0], w_end
        )
        result[:, w_end:b_end] = sensitivity
        rows = np.arange(x.shape[0], dtype=np.int64)[:, None]
        head_columns = (
            v_start
            + selected_actions[:, None] * self.layout.hidden_width
            + np.arange(self.layout.hidden_width, dtype=np.int64)[None, :]
        )
        result[rows, head_columns] = hidden
        result[np.arange(x.shape[0]), c_start + selected_actions] = 1.0
        return result

    def mean_and_jacobian(
        self, displacement: ArrayLike, context: ArrayLike, action: int
    ) -> tuple[float, FloatArray]:
        """Return one action mean and analytic Jacobian from a shared forward pass."""

        action_index = self._validate_action(action)
        return (
            float(self.means(displacement, context)[action_index]),
            self.jacobians(displacement, context)[action_index],
        )

    def action_means_and_jacobians(
        self, displacement: ArrayLike, context: ArrayLike
    ) -> tuple[FloatArray, FloatArray]:
        return self.means(displacement, context), self.jacobians(displacement, context)

    def _validate_action(self, action: int) -> int:
        if isinstance(action, (bool, np.bool_)) or not isinstance(
            action, (int, np.integer)
        ):
            raise TypeError("action must be an integer")
        result = int(action)
        if not 0 <= result < self.layout.action_count:
            raise ValueError(
                f"action must be in [0, {self.layout.action_count}), got {result}"
            )
        return result


def enumerate_rademacher_contexts(
    context_dimension: int = CONTEXT_DIMENSION,
) -> FloatArray:
    """Enumerate all normalized-Rademacher contexts in fixed order."""

    dimension = _nonnegative_integer(context_dimension, name="context_dimension")
    if dimension == 0:
        raise ValueError("context_dimension must be positive")
    scale = 1.0 / np.sqrt(float(dimension))
    return np.asarray(
        list(product((-scale, scale), repeat=dimension)), dtype=np.float64
    )


class NonlinearBanditEnvironment:
    """Normalized-Rademacher contextual bandit with a known tanh teacher."""

    def __init__(
        self,
        seed: int,
        *,
        noise_std: float = 0.1,
        model: SmallTanhMLP | None = None,
        teacher_displacement: ArrayLike | None = None,
    ) -> None:
        seed_value = _nonnegative_integer(seed, name="seed")
        standard_deviation = float(noise_std)
        if not np.isfinite(standard_deviation) or standard_deviation <= 0.0:
            raise ValueError("noise_std must be finite and positive")
        self.model = SmallTanhMLP() if model is None else model
        teacher = (
            default_teacher_displacement(self.model.layout)
            if teacher_displacement is None
            else _finite_vector(
                teacher_displacement,
                self.model.parameter_dimension,
                name="teacher_displacement",
            ).copy()
        )
        streams = np.random.SeedSequence(seed_value).spawn(2)
        self._context_rng = np.random.default_rng(streams[0])
        self._noise_rng = np.random.default_rng(streams[1])
        self.noise_std = standard_deviation
        teacher.setflags(write=False)
        self._teacher_displacement = teacher

    @property
    def context_dimension(self) -> int:
        return self.model.layout.context_dimension

    @property
    def action_count(self) -> int:
        return self.model.layout.action_count

    @property
    def parameter_dimension(self) -> int:
        return self.model.parameter_dimension

    @property
    def teacher_displacement(self) -> FloatArray:
        return self._teacher_displacement

    @property
    def theta_star(self) -> FloatArray:
        return self._teacher_displacement

    def draw_context(self) -> FloatArray:
        signs = self._context_rng.integers(
            0, 2, size=self.context_dimension, dtype=np.int64
        )
        return np.asarray(
            (2.0 * signs.astype(np.float64) - 1.0)
            / np.sqrt(float(self.context_dimension)),
            dtype=np.float64,
        )

    def draw_noise(self) -> float:
        return float(self._noise_rng.normal(0.0, self.noise_std))

    def mean_rewards(self, context: ArrayLike) -> FloatArray:
        return self.model.means(self._teacher_displacement, context)

    def optimal_action(self, context: ArrayLike) -> int:
        return int(np.argmax(self.mean_rewards(context)))

    def reward(
        self, context: ArrayLike, action: int, *, noise: float | None = None
    ) -> tuple[float, float]:
        mean = self.model.mean(self._teacher_displacement, context, action)
        realized_noise = self.draw_noise() if noise is None else float(noise)
        if not np.isfinite(realized_noise):
            raise ValueError("noise must be finite")
        return mean + realized_noise, realized_noise


# Concise aliases used by local notebooks and tests.
TanhMLP = SmallTanhMLP
SmoothNonlinearBandit = NonlinearBanditEnvironment
NonlinearEnvironment = NonlinearBanditEnvironment


__all__ = [
    "ACTION_COUNT",
    "CONTEXT_DIMENSION",
    "HIDDEN_WIDTH",
    "PARAMETER_DIMENSION",
    "MLPLayout",
    "NonlinearBanditEnvironment",
    "NonlinearEnvironment",
    "SmallTanhMLP",
    "SmoothNonlinearBandit",
    "TanhMLP",
    "default_base_parameters",
    "default_teacher_displacement",
    "enumerate_rademacher_contexts",
]
