"""Run exact small-scale curvature-operator ablations on the linear audit.

The online part of this driver executes every policy on its own adaptive data
path.  A separate common-trajectory diagnostic holds contexts, logged actions,
estimator checkpoints, damping, and bonus coefficients fixed.  That diagnostic
is offline and deliberately reports no causal regret comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

try:  # Package execution: python -m experiments.run_operator_ablation
    from .config import get_seed_set, load_config
    from .linear_environment import (
        ACTION_COUNT,
        CONTEXT_DIMENSION,
        FEATURE_DIMENSION,
        action_features,
        default_theta_star,
        linear_feature,
    )
    from .logging_utils import ExperimentLogger, append_jsonl, derive_seed
    from .run_linear_audit import (
        CurvatureStrategy,
        LinearAuditConfig,
        RoundMatrices,
        run_method,
    )
    from .theory_metrics import kappa_plus as _core_kappa_plus
except ImportError:  # Direct execution from the repository root.
    from experiments.config import get_seed_set, load_config  # type: ignore[no-redef]
    from experiments.linear_environment import (  # type: ignore[no-redef]
        ACTION_COUNT,
        CONTEXT_DIMENSION,
        FEATURE_DIMENSION,
        action_features,
        default_theta_star,
        linear_feature,
    )
    from experiments.logging_utils import (  # type: ignore[no-redef]
        ExperimentLogger,
        append_jsonl,
        derive_seed,
    )
    from experiments.run_linear_audit import (  # type: ignore[no-redef]
        CurvatureStrategy,
        LinearAuditConfig,
        RoundMatrices,
        run_method,
    )
    from experiments.theory_metrics import (  # type: ignore[no-redef]
        kappa_plus as _core_kappa_plus,
    )


FloatArray = NDArray[np.float64]

OPERATOR_KINDS = (
    "full",
    "frozen",
    "diagonal",
    "lanczos",
    "unrescaled_window",
    "rescaled_subsample",
    "stale_refresh",
)

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "name": "operator_ablation",
    "profile": "smoke",
    "rounds": 25,
    "noise_std": 0.1,
    "damping": 1.0,
    "confidence": {"delta": 0.05},
    "bonus_scale": 1.0,
    "operators": {
        "full": {"kind": "full"},
        "diagonal": {"kind": "diagonal"},
        "lanczos": {"kind": "lanczos", "ranks": [4]},
        "windowed": {"kind": "windowed", "buffer_sizes": [16]},
        "subsampled": {"kind": "subsampled", "buffer_sizes": [16]},
        "periodic_refresh": {"kind": "periodic_refresh", "periods": [5]},
    },
    "common_trajectory": {"enabled": True},
    "seed_sets": {"tuning": [20], "evaluation": [120]},
}


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


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _readonly(value: ArrayLike) -> FloatArray:
    result = np.asarray(value, dtype=np.float64).copy()
    result.setflags(write=False)
    return result


def _logdet(matrix: FloatArray) -> float:
    eigenvalues = np.linalg.eigvalsh(0.5 * (matrix + matrix.T))
    if np.any(eigenvalues <= 0.0) or not np.all(np.isfinite(eigenvalues)):
        raise ArithmeticError("operator must have a finite positive determinant")
    return float(np.sum(np.log(eigenvalues)))


def _inverse_sqrt(matrix: FloatArray) -> FloatArray:
    values, vectors = np.linalg.eigh(0.5 * (matrix + matrix.T))
    if np.any(values <= 0.0) or not np.all(np.isfinite(values)):
        raise ArithmeticError("operator must be finite and positive definite")
    return np.asarray((vectors * (1.0 / np.sqrt(values))) @ vectors.T, dtype=np.float64)


def _trajectory_hash(*values: object) -> str:
    digest = hashlib.sha256()
    for value in values:
        if isinstance(value, np.ndarray):
            array = np.ascontiguousarray(value)
            digest.update(str(array.shape).encode("ascii"))
            digest.update(array.dtype.str.encode("ascii"))
            digest.update(array.tobytes())
        else:
            digest.update(
                json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
                    "ascii"
                )
            )
    return digest.hexdigest()


@dataclass(frozen=True)
class OperatorSpec:
    """One concrete operator setting in the ablation grid."""

    kind: str
    parameter: int | None = None
    label: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in OPERATOR_KINDS:
            raise ValueError(f"unknown operator kind {self.kind!r}")
        parameterized = {
            "lanczos",
            "unrescaled_window",
            "rescaled_subsample",
            "stale_refresh",
        }
        if self.kind in parameterized:
            _positive_int(self.parameter, name=f"{self.kind} parameter")
        elif self.parameter is not None:
            raise ValueError(f"{self.kind} does not take an integer parameter")
        if self.label is not None:
            if not isinstance(self.label, str) or not self.label.strip():
                raise ValueError("operator label must be a nonempty string")
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", self.label):
                raise ValueError("operator label must be path-safe")

    @property
    def name(self) -> str:
        if self.label is not None:
            return self.label
        if self.kind == "lanczos":
            return f"lanczos_rank_{self.parameter}"
        if self.kind == "unrescaled_window":
            return f"unrescaled_window_{self.parameter}"
        if self.kind == "rescaled_subsample":
            return f"rescaled_subsample_{self.parameter}"
        if self.kind == "stale_refresh":
            return f"stale_refresh_{self.parameter}"
        return self.kind

    @property
    def linear_method(self) -> str:
        return {
            "full": "dense_full",
            "frozen": "dense_full",
            "diagonal": "diagonal",
            "lanczos": "lanczos_ritz",
            "unrescaled_window": "unrescaled_window",
            "rescaled_subsample": "rescaled_subsample",
            "stale_refresh": "stale_refresh",
        }[self.kind]

    def apply(self, config: LinearAuditConfig) -> LinearAuditConfig:
        if self.kind == "lanczos":
            return replace(config, lanczos_rank=min(int(self.parameter), FEATURE_DIMENSION))
        if self.kind == "unrescaled_window":
            return replace(config, window_size=int(self.parameter))
        if self.kind == "rescaled_subsample":
            return replace(config, subsample_size=int(self.parameter))
        if self.kind == "stale_refresh":
            return replace(config, refresh_period=int(self.parameter))
        return config


_SPEC_PATTERNS = (
    (re.compile(r"^(?:lanczos(?:_ritz)?(?:_rank)?)[_-]?(\d+)$"), "lanczos"),
    (re.compile(r"^(?:unrescaled_)?window(?:ed)?[_-]?(\d+)$"), "unrescaled_window"),
    (re.compile(r"^(?:rescaled_)?subsampled?[_-]?(\d+)$"), "rescaled_subsample"),
    (re.compile(r"^(?:stale_refresh|periodic_refresh)[_-]?(\d+)$"), "stale_refresh"),
)


def canonical_operator_spec(value: str | OperatorSpec) -> OperatorSpec:
    if isinstance(value, OperatorSpec):
        return value
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    normalized = {
        "dense": "full",
        "dense_full": "full",
        "full_dense": "full",
        "frozen_full": "frozen",
        "full_frozen": "frozen",
        "diag": "diagonal",
    }.get(normalized, normalized)
    if normalized in {"full", "frozen", "diagonal"}:
        return OperatorSpec(normalized)
    for pattern, kind in _SPEC_PATTERNS:
        match = pattern.match(normalized)
        if match:
            return OperatorSpec(kind, int(match.group(1)))
    raise ValueError(f"operator {value!r} is not a concrete operator setting")


def _operator_spec_from_mapping(value: Mapping[str, Any]) -> OperatorSpec | None:
    if not _enabled(value):
        return None
    raw_kind = str(value.get("kind", value.get("operator", ""))).strip().lower()
    kind = {
        "dense": "full",
        "dense_full": "full",
        "full_relinearized": "full",
        "frozen_gram": "frozen",
        "diag": "diagonal",
        "lanczos_ritz": "lanczos",
        "window": "unrescaled_window",
        "windowed": "unrescaled_window",
        "subsampled": "rescaled_subsample",
        "periodic_refresh": "stale_refresh",
    }.get(raw_kind, raw_kind)
    if kind not in OPERATOR_KINDS:
        raise ValueError(f"unknown configured operator kind {raw_kind!r}")
    parameter: int | None = None
    if kind == "lanczos":
        parameter = _positive_int(value.get("rank"), name="Lanczos rank")
        parameter = min(parameter, FEATURE_DIMENSION)
    elif kind in {"unrescaled_window", "rescaled_subsample"}:
        parameter = _positive_int(
            value.get("size", value.get("buffer_size", value.get("sample_size"))),
            name=f"{kind} size",
        )
    elif kind == "stale_refresh":
        parameter = _positive_int(
            value.get("period", value.get("refresh_period")),
            name="refresh period",
        )
    label_value = value.get("name")
    label = None if label_value is None else str(label_value)
    return OperatorSpec(kind, parameter, label)


def _enabled(value: Any) -> bool:
    if isinstance(value, Mapping):
        return bool(value.get("enabled", True))
    return bool(value)


def _grid_values(
    options: Mapping[str, Any],
    keys: Sequence[str],
    *,
    default: int,
    rounds: int,
    name: str,
) -> tuple[int, ...]:
    raw: Any = None
    for key in keys:
        if key in options:
            raw = options[key]
            break
    if raw is None:
        raw = [default]
    if isinstance(raw, (str, int, np.integer)):
        raw = [raw]
    if not isinstance(raw, Sequence) or isinstance(raw, (bytes, bytearray)):
        raise TypeError(f"{name} must be an integer or a sequence")
    parsed: list[int] = []
    for item in raw:
        value = rounds if isinstance(item, str) and item.lower() == "all" else item
        parsed.append(_positive_int(value, name=name))
    return tuple(dict.fromkeys(parsed))


def _linear_config(source: Mapping[str, Any]) -> LinearAuditConfig:
    """Resolve only fields meaningful to the fixed linear environment.

    The legacy operator protocol contains neural benchmark dimensions.  This
    exact audit intentionally ignores those fields and records its fixed
    p=8, K=5, d=53 environment explicitly.
    """

    rounds = _positive_int(source.get("rounds", 25), name="rounds")
    theta = _mapping_value(source, ("environment.theta_star", "theta_star"), default_theta_star())
    sanitized = {
        "rounds": rounds,
        "ridge": _mapping_value(source, ("damping", "ridge", "algorithm.damping"), 1.0),
        "environment": {
            "context_dimension": CONTEXT_DIMENSION,
            "action_count": ACTION_COUNT,
            "noise_std": _mapping_value(
                source, ("environment.noise_std", "noise_std"), 0.1
            ),
            "theta_star": theta,
        },
        "confidence": {
            "delta": _mapping_value(source, ("confidence.delta", "delta"), 0.05),
            "theta_bound": _mapping_value(
                source,
                ("confidence.theta_bound", "theta_bound"),
                float(np.linalg.norm(np.asarray(theta, dtype=np.float64))),
            ),
        },
        "bonus_scale": _mapping_value(
            source, ("bonus_scale", "confidence.bonus_scale"), 1.0
        ),
        "curvature": {
            "window_size": _mapping_value(source, ("curvature.window_size",), 8),
            "subsample_size": _mapping_value(source, ("curvature.subsample_size",), 8),
            "lanczos_rank": _mapping_value(source, ("curvature.lanczos_rank",), 8),
            "refresh_period": _mapping_value(source, ("curvature.refresh_period",), 4),
        },
        "cg": {
            "tolerance": _mapping_value(
                source, ("cg.tolerance", "solver.relative_energy_tolerance"), 0.05
            ),
            "max_iterations": _mapping_value(
                source, ("cg.max_iterations", "solver.max_iterations"), 2 * FEATURE_DIMENSION
            ),
        },
    }
    return LinearAuditConfig.from_mapping(sanitized)


def configured_operator_specs(
    source: Mapping[str, Any] | "OperatorAblationConfig",
) -> tuple[OperatorSpec, ...]:
    if isinstance(source, OperatorAblationConfig):
        return source.specs
    linear = _linear_config(source)
    rounds = linear.rounds
    operators = source.get("operators")
    if operators is None:
        return (
            OperatorSpec("full"),
            OperatorSpec("frozen"),
            OperatorSpec("diagonal"),
            OperatorSpec("lanczos", linear.lanczos_rank),
            OperatorSpec("unrescaled_window", linear.window_size),
            OperatorSpec("rescaled_subsample", linear.subsample_size),
            OperatorSpec("stale_refresh", linear.refresh_period),
        )
    if isinstance(operators, Sequence) and not isinstance(operators, (str, bytes)):
        parsed: list[OperatorSpec] = []
        for item in operators:
            spec = (
                _operator_spec_from_mapping(item)
                if isinstance(item, Mapping)
                else canonical_operator_spec(str(item))
            )
            if spec is not None:
                parsed.append(spec)
        if any(spec.kind == "full" for spec in parsed) and not any(
            spec.kind == "frozen" for spec in parsed
        ):
            full_index = next(
                index for index, spec in enumerate(parsed) if spec.kind == "full"
            )
            parsed.insert(full_index + 1, OperatorSpec("frozen"))
        if not parsed:
            raise ValueError("operator list resolved to no supported settings")
        return tuple(dict.fromkeys(parsed))
    if not isinstance(operators, Mapping):
        raise TypeError("operators must be a mapping or sequence")

    specs: list[OperatorSpec] = []
    full_options = operators.get("full", {"kind": "full"})
    if _enabled(full_options):
        specs.extend((OperatorSpec("full"), OperatorSpec("frozen")))
    elif _enabled(operators.get("frozen", False)):
        specs.append(OperatorSpec("frozen"))

    if _enabled(operators.get("diagonal", False)):
        specs.append(OperatorSpec("diagonal"))

    lanczos = operators.get("lanczos", operators.get("lanczos_ritz"))
    if lanczos is not None and _enabled(lanczos):
        options = lanczos if isinstance(lanczos, Mapping) else {}
        ranks = _grid_values(
            options,
            ("ranks", "rank"),
            default=linear.lanczos_rank,
            rounds=rounds,
            name="Lanczos rank",
        )
        specs.extend(OperatorSpec("lanczos", min(rank, FEATURE_DIMENSION)) for rank in ranks)

    windowed = operators.get("windowed", operators.get("unrescaled_window"))
    if windowed is not None and _enabled(windowed):
        options = windowed if isinstance(windowed, Mapping) else {}
        sizes = _grid_values(
            options,
            ("buffer_sizes", "window_sizes", "window_size", "size"),
            default=linear.window_size,
            rounds=rounds,
            name="window size",
        )
        specs.extend(OperatorSpec("unrescaled_window", size) for size in sizes)

    subsampled = operators.get("subsampled", operators.get("rescaled_subsample"))
    if subsampled is not None and _enabled(subsampled):
        options = subsampled if isinstance(subsampled, Mapping) else {}
        sizes = _grid_values(
            options,
            ("buffer_sizes", "sample_sizes", "sample_size", "size"),
            default=linear.subsample_size,
            rounds=rounds,
            name="subsample size",
        )
        specs.extend(OperatorSpec("rescaled_subsample", size) for size in sizes)

    stale = operators.get("periodic_refresh", operators.get("stale_refresh"))
    if stale is not None and _enabled(stale):
        options = stale if isinstance(stale, Mapping) else {}
        periods = _grid_values(
            options,
            ("periods", "refresh_periods", "period"),
            default=linear.refresh_period,
            rounds=rounds,
            name="refresh period",
        )
        specs.extend(OperatorSpec("stale_refresh", period) for period in periods)

    if not specs:
        raise ValueError("operator grid resolved to no supported settings")
    return tuple(dict.fromkeys(specs))


@dataclass(frozen=True)
class OperatorAblationConfig:
    linear: LinearAuditConfig
    specs: tuple[OperatorSpec, ...]
    common_trajectory_enabled: bool

    @classmethod
    def from_mapping(cls, source: Mapping[str, Any]) -> "OperatorAblationConfig":
        common = source.get("common_trajectory", True)
        enabled = _enabled(common)
        return cls(
            linear=_linear_config(source),
            specs=configured_operator_specs(source),
            common_trajectory_enabled=enabled,
        )


def exact_global_kappa_plus(c_hat: ArrayLike, c_full: ArrayLike) -> float:
    """Return exact global ``lambda_max(C_full^-1/2 C_hat C_full^-1/2)``."""

    approximate = np.asarray(c_hat, dtype=np.float64)
    reference = np.asarray(c_full, dtype=np.float64)
    return float(_core_kappa_plus(approximate, reference))


global_kappa_plus = exact_global_kappa_plus
exact_kappa_plus = exact_global_kappa_plus


def _widths_squared(operator: FloatArray, features: FloatArray) -> FloatArray:
    solved = np.linalg.solve(operator, features.T).T
    widths = np.einsum("ij,ij->i", features, solved, dtype=np.float64)
    tolerance = 256.0 * np.finfo(np.float64).eps * max(1.0, float(np.max(np.abs(widths))))
    if np.any(widths < -tolerance):
        raise ArithmeticError("positive-definite operator produced a negative width")
    return np.maximum(widths, 0.0).astype(np.float64, copy=False)


@dataclass(frozen=True)
class ActionSetWidthResult:
    cbar_widths_squared: FloatArray
    chat_widths_squared: FloatArray
    squared_ratios: FloatArray
    width_ratios: FloatArray
    maximum_squared_ratio: float
    maximum_width_ratio: float


def action_set_width_ratios(
    c_hat: ArrayLike, c_bar: ArrayLike, features: ArrayLike
) -> ActionSetWidthResult:
    approximate = np.asarray(c_hat, dtype=np.float64)
    frozen = np.asarray(c_bar, dtype=np.float64)
    candidates = np.asarray(features, dtype=np.float64)
    if candidates.ndim != 2 or candidates.shape[1] != approximate.shape[0]:
        raise ValueError("features must have shape (action_count, operator_dimension)")
    chat = _widths_squared(approximate, candidates)
    cbar = _widths_squared(frozen, candidates)
    if np.any(chat <= 0.0):
        raise ArithmeticError("action widths must be strictly positive")
    squared = np.asarray(cbar / chat, dtype=np.float64)
    widths = np.sqrt(squared)
    return ActionSetWidthResult(
        cbar_widths_squared=_readonly(cbar),
        chat_widths_squared=_readonly(chat),
        squared_ratios=_readonly(squared),
        width_ratios=_readonly(widths),
        maximum_squared_ratio=float(np.max(squared)),
        maximum_width_ratio=float(np.max(widths)),
    )


def action_set_max_width_ratio(
    c_hat: ArrayLike, c_bar: ArrayLike, features: ArrayLike, *, squared: bool = True
) -> float:
    result = action_set_width_ratios(c_hat, c_bar, features)
    return result.maximum_squared_ratio if squared else result.maximum_width_ratio


max_action_set_width_ratio = action_set_max_width_ratio


@dataclass(frozen=True)
class OnlineOperatorRun:
    spec: OperatorSpec
    seed: int
    config: LinearAuditConfig
    rounds: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    played_features: FloatArray
    matrices: tuple[RoundMatrices, ...] = ()

    @property
    def operator(self) -> str:
        return self.spec.name

    @property
    def method(self) -> str:
        return self.spec.name

    @property
    def actions(self) -> tuple[int, ...]:
        return tuple(int(record["action"]) for record in self.rounds)

    @property
    def contexts(self) -> FloatArray:
        return np.asarray([record["context"] for record in self.rounds], dtype=np.float64)


def _online_record(
    base: Mapping[str, Any], matrices: RoundMatrices, spec: OperatorSpec
) -> dict[str, Any]:
    c_hat = np.asarray(matrices.algorithmic, dtype=np.float64)
    c_full = np.asarray(matrices.reference, dtype=np.float64)
    c_bar = np.asarray(matrices.frozen, dtype=np.float64)
    candidates = np.asarray(matrices.action_features, dtype=np.float64)
    global_factor = exact_global_kappa_plus(c_hat, c_full)
    ratios = action_set_width_ratios(c_hat, c_bar, candidates)
    chat_width = np.sqrt(ratios.chat_widths_squared)
    cbar_width = np.sqrt(ratios.cbar_widths_squared)
    width_relative = np.abs(chat_width / cbar_width - 1.0)

    predicted = np.asarray(base["predicted_means"], dtype=np.float64)
    true_means = np.asarray(base["true_means"], dtype=np.float64)
    executed_scores = np.asarray(base["ucb_scores"], dtype=np.float64)
    beta = float(base["beta_t"])
    full_scores = predicted + beta * cbar_width
    same_history_full_action = int(np.argmax(full_scores))
    gaps = true_means - executed_scores
    tolerance = 1e-12 * max(1.0, float(np.max(np.abs(true_means))))
    violations = gaps > tolerance
    optimal_action = int(base["optimal_action"])
    global_tolerance = 2e-10 * max(1.0, abs(global_factor))

    record = dict(base)
    record.update(
        {
            "operator": spec.name,
            "operator_kind": spec.kind,
            "operator_parameter": spec.parameter,
            "linear_method": spec.linear_method,
            "execution_mode": "online_adaptive",
            "executed_policy": True,
            "offline_diagnostic": False,
            "policy_transfer_factor": float(base["kappa_plus"]),
            "kappa_plus": global_factor,
            "exact_global_kappa_plus": global_factor,
            "global_kappa_plus_C_hat_C_full": global_factor,
            "action_set_transfer": ratios.maximum_squared_ratio,
            "action_set_max_cbar_width_squared_over_chat_width_squared": ratios.maximum_squared_ratio,
            "action_set_max_cbar_width_over_chat_width": ratios.maximum_width_ratio,
            "action_set_ratio_bounded_by_global_kappa": bool(
                ratios.maximum_squared_ratio <= global_factor + global_tolerance
            ),
            "chat_widths_squared": ratios.chat_widths_squared.tolist(),
            "cbar_widths_squared": ratios.cbar_widths_squared.tolist(),
            "width_ratio_chat_over_cbar": (chat_width / cbar_width).tolist(),
            "max_relative_width_distortion": float(np.max(width_relative)),
            "mean_relative_width_distortion": float(np.mean(width_relative)),
            "width_distortion": float(np.max(width_relative)),
            "same_history_full_action": same_history_full_action,
            "action_disagrees_with_same_history_full": bool(
                int(base["action"]) != same_history_full_action
            ),
            "action_disagreement_with_full": bool(
                int(base["action"]) != same_history_full_action
            ),
            "optimism_violation_count": int(np.count_nonzero(violations)),
            "optimism_violation_rate": float(np.count_nonzero(violations) / ACTION_COUNT),
            "optimism_violation": bool(np.any(violations)),
            "optimism_violation_max": float(max(float(np.max(gaps)), 0.0)),
            "optimal_action_optimism_violation": bool(violations[optimal_action]),
            "C_full_equals_C_bar": bool(np.array_equal(c_full, c_bar)),
            "window_global_kappa_le_one": (
                bool(global_factor <= 1.0 + global_tolerance)
                if spec.kind == "unrescaled_window"
                else None
            ),
            "float_dtype": "float64",
        }
    )
    return record


def run_operator(
    config: Mapping[str, Any] | OperatorAblationConfig,
    operator: str | OperatorSpec,
    seed: int,
    *,
    retain_matrices: bool = False,
) -> OnlineOperatorRun:
    """Execute one online operator policy and add exact ablation diagnostics."""

    resolved = (
        config if isinstance(config, OperatorAblationConfig) else OperatorAblationConfig.from_mapping(config)
    )
    spec = canonical_operator_spec(operator)
    linear = spec.apply(resolved.linear)
    audit = run_method(linear, spec.linear_method, seed, retain_matrices=True)
    records = tuple(
        _online_record(record, matrices, spec)
        for record, matrices in zip(audit.rounds, audit.matrices, strict=True)
    )
    last = records[-1]
    violation_count = sum(int(record["optimism_violation_count"]) for record in records)
    disagreement_count = sum(
        bool(record["action_disagrees_with_same_history_full"]) for record in records
    )
    summary = {
        "operator": spec.name,
        "operator_kind": spec.kind,
        "operator_parameter": spec.parameter,
        "linear_method": spec.linear_method,
        "seed": int(seed),
        "rounds": linear.rounds,
        "execution_mode": "online_adaptive",
        "executed_policy": True,
        "offline_diagnostic": False,
        "cumulative_pseudo_regret": float(last["cumulative_pseudo_regret"]),
        "optimism_violation_count": violation_count,
        "optimism_violation_rate": float(violation_count / (linear.rounds * ACTION_COUNT)),
        "optimism_violation_rounds": sum(bool(record["optimism_violation"]) for record in records),
        "Lambda_alg_T": float(last["Lambda_alg_cumulative"]),
        "V_alg_T": float(last["V_alg_cumulative"]),
        "Gamma_dynamic_T": float(last["Gamma_dynamic_cumulative"]),
        "endpoint_logdet_T": float(last["endpoint_logdet"]),
        "dynamic_identity_residual": float(last["dynamic_identity_residual"]),
        "kappa_plus_max": max(float(record["kappa_plus"]) for record in records),
        "kappa_plus_min": min(float(record["kappa_plus"]) for record in records),
        "exact_global_kappa_plus_max": max(
            float(record["exact_global_kappa_plus"]) for record in records
        ),
        "exact_global_kappa_plus_min": min(
            float(record["exact_global_kappa_plus"]) for record in records
        ),
        "action_set_max_cbar_width_squared_over_chat_width_squared": max(
            float(record["action_set_max_cbar_width_squared_over_chat_width_squared"])
            for record in records
        ),
        "action_set_transfer_max": max(
            float(record["action_set_transfer"]) for record in records
        ),
        "max_relative_width_distortion": max(
            float(record["max_relative_width_distortion"]) for record in records
        ),
        "width_distortion_max": max(float(record["width_distortion"]) for record in records),
        "action_disagreement_count": disagreement_count,
        "action_disagreement_with_full_count": disagreement_count,
        "action_disagreement_rate": float(disagreement_count / linear.rounds),
        "runtime_seconds": float(last["runtime_seconds"]),
        "peak_host_memory_bytes": int(last["peak_host_memory_bytes"]),
        "mean_cg_iterations": float(
            np.mean([np.mean(record["cg_iterations"]) for record in records])
        ),
        "C_full_equals_C_bar_all_rounds": all(
            bool(record["C_full_equals_C_bar"]) for record in records
        ),
        "window_global_kappa_le_one_all_rounds": (
            all(bool(record["window_global_kappa_le_one"]) for record in records)
            if spec.kind == "unrescaled_window"
            else None
        ),
        "action_set_ratio_bounded_by_global_kappa_all_rounds": all(
            bool(record["action_set_ratio_bounded_by_global_kappa"]) for record in records
        ),
        "float_dtype": "float64",
    }
    return OnlineOperatorRun(
        spec=spec,
        seed=int(seed),
        config=linear,
        rounds=records,
        summary=summary,
        played_features=_readonly(audit.played_features),
        matrices=audit.matrices if retain_matrices else (),
    )


run_operator_policy = run_operator


@dataclass(frozen=True)
class FixedLoggedTrajectory:
    """Immutable inputs shared by every offline operator diagnostic."""

    contexts: FloatArray
    actions: tuple[int, ...]
    rewards: FloatArray
    checkpoints: FloatArray
    bonus_coefficients: FloatArray
    damping: float
    noise_std: float
    digest: str
    source_operator: str

    @property
    def rounds(self) -> int:
        return len(self.actions)


def fixed_trajectory_from_run(run: OnlineOperatorRun) -> FixedLoggedTrajectory:
    contexts = np.asarray(run.contexts, dtype=np.float64)
    actions = run.actions
    rewards = np.asarray([record["reward"] for record in run.rounds], dtype=np.float64)
    bonuses = np.asarray([record["beta_t"] for record in run.rounds], dtype=np.float64)
    checkpoints = np.empty((len(actions), FEATURE_DIMENSION), dtype=np.float64)
    curvature = run.config.ridge * np.eye(FEATURE_DIMENSION, dtype=np.float64)
    response = np.zeros(FEATURE_DIMENSION, dtype=np.float64)
    variance = run.config.noise_std * run.config.noise_std
    for index, (context, action, reward) in enumerate(
        zip(contexts, actions, rewards, strict=True)
    ):
        checkpoint = np.linalg.solve(curvature, response)
        checkpoints[index] = checkpoint
        candidates = action_features(context)
        predicted = candidates @ checkpoint
        if not np.allclose(
            predicted,
            np.asarray(run.rounds[index]["predicted_means"], dtype=np.float64),
            rtol=2e-11,
            atol=2e-11,
        ):
            raise AssertionError("reconstructed checkpoint disagrees with the online log")
        played = linear_feature(context, action)
        curvature += np.outer(played, played) / variance
        response += played * reward / variance
    digest = _trajectory_hash(
        contexts,
        actions,
        rewards,
        checkpoints,
        bonuses,
        run.config.ridge,
        run.config.noise_std,
    )
    return FixedLoggedTrajectory(
        contexts=_readonly(contexts),
        actions=actions,
        rewards=_readonly(rewards),
        checkpoints=_readonly(checkpoints),
        bonus_coefficients=_readonly(bonuses),
        damping=float(run.config.ridge),
        noise_std=float(run.config.noise_std),
        digest=digest,
        source_operator=run.spec.name,
    )


@dataclass(frozen=True)
class OfflineOperatorDiagnostic:
    spec: OperatorSpec
    seed: int
    trajectory: FixedLoggedTrajectory
    rounds: tuple[dict[str, Any], ...]
    summary: dict[str, Any]

    @property
    def operator(self) -> str:
        return self.spec.name

    @property
    def actions(self) -> tuple[int, ...]:
        return self.trajectory.actions

    @property
    def contexts(self) -> FloatArray:
        return self.trajectory.contexts

    @property
    def checkpoints(self) -> FloatArray:
        return self.trajectory.checkpoints


@dataclass(frozen=True)
class CommonTrajectoryResult:
    seed: int
    trajectory: FixedLoggedTrajectory
    diagnostics: tuple[OfflineOperatorDiagnostic, ...]
    summary: dict[str, Any]

    @property
    def runs(self) -> tuple[OfflineOperatorDiagnostic, ...]:
        return self.diagnostics


def _offline_diagnostic(
    config: LinearAuditConfig,
    spec: OperatorSpec,
    seed: int,
    trajectory: FixedLoggedTrajectory,
) -> OfflineOperatorDiagnostic:
    linear = spec.apply(config)
    if not math.isclose(linear.ridge, trajectory.damping, rel_tol=0.0, abs_tol=0.0):
        raise ValueError("offline diagnostic damping must match the logged trajectory")
    if not math.isclose(linear.noise_std, trajectory.noise_std, rel_tol=0.0, abs_tol=0.0):
        raise ValueError("offline diagnostic noise_std must match the logged trajectory")
    strategy = CurvatureStrategy(
        spec.linear_method,
        linear,
        derive_seed(int(seed), "operator_ablation", "offline", spec.name),
    )
    variance = linear.noise_std * linear.noise_std
    reference = linear.ridge * np.eye(FEATURE_DIMENSION, dtype=np.float64)
    history: list[FloatArray] = []
    records: list[dict[str, Any]] = []
    cumulative_information = 0.0
    cumulative_variation = 0.0
    cumulative_transition = 0.0
    initial_logdet = FEATURE_DIMENSION * math.log(linear.ridge)

    for index in range(trajectory.rounds):
        round_index = index + 1
        context = np.asarray(trajectory.contexts[index], dtype=np.float64)
        logged_action = trajectory.actions[index]
        checkpoint = np.asarray(trajectory.checkpoints[index], dtype=np.float64)
        beta = float(trajectory.bonus_coefficients[index])
        candidates = action_features(context)
        predicted = np.asarray(candidates @ checkpoint, dtype=np.float64)
        true_means = np.asarray(candidates @ np.asarray(linear.theta_star), dtype=np.float64)
        c_full = reference.copy()
        c_bar = c_full.copy()
        current = strategy.build(round_index, history)
        c_hat = np.asarray(current.matrix, dtype=np.float64)
        global_factor = exact_global_kappa_plus(c_hat, c_full)
        ratios = action_set_width_ratios(c_hat, c_bar, candidates)
        chat_width = np.sqrt(ratios.chat_widths_squared)
        cbar_width = np.sqrt(ratios.cbar_widths_squared)
        scores = predicted + beta * chat_width
        full_scores = predicted + beta * cbar_width
        diagnostic_action = int(np.argmax(scores))
        full_action = int(np.argmax(full_scores))

        played = linear_feature(context, logged_action)
        next_history = [*history, played]
        next_operator = np.asarray(
            strategy.build(round_index + 1, next_history).matrix, dtype=np.float64
        )
        c_hat_plus = c_hat + np.outer(played, played) / variance
        inverse_root = _inverse_sqrt(c_hat_plus)
        xi = inverse_root @ (next_operator - c_hat_plus) @ inverse_root
        xi = np.asarray(0.5 * (xi + xi.T), dtype=np.float64)
        transition = _logdet(np.eye(FEATURE_DIMENSION, dtype=np.float64) + xi)
        variation = max(-transition, 0.0)
        played_width = float(ratios.chat_widths_squared[logged_action])
        information = float(np.log1p(played_width / variance))
        cumulative_information += information
        cumulative_transition += transition
        cumulative_variation += variation
        endpoint = _logdet(next_operator) - initial_logdet
        dynamic = endpoint + cumulative_variation
        identity_residual = cumulative_information - (endpoint - cumulative_transition)

        gaps = true_means - scores
        tolerance = 1e-12 * max(1.0, float(np.max(np.abs(true_means))))
        violations = gaps > tolerance
        global_tolerance = 2e-10 * max(1.0, abs(global_factor))
        record = {
            "round": round_index,
            "operator": spec.name,
            "operator_kind": spec.kind,
            "operator_parameter": spec.parameter,
            "linear_method": spec.linear_method,
            "execution_mode": "offline_common_trajectory_diagnostic",
            "executed_policy": False,
            "offline_diagnostic": True,
            "causal_regret_claim": False,
            "regret_reported": False,
            "trajectory_digest": trajectory.digest,
            "source_operator": trajectory.source_operator,
            "context": context.tolist(),
            "logged_action": logged_action,
            "checkpoint": checkpoint.tolist(),
            "fixed_damping": trajectory.damping,
            "fixed_bonus_coefficient": beta,
            "diagnostic_action": diagnostic_action,
            "full_diagnostic_action": full_action,
            "action_disagrees_with_full": bool(diagnostic_action != full_action),
            "action_disagreement_with_full": bool(diagnostic_action != full_action),
            "diagnostic_action_matches_logged_action": bool(
                diagnostic_action == logged_action
            ),
            "predicted_means": predicted.tolist(),
            "diagnostic_scores": scores.tolist(),
            "full_diagnostic_scores": full_scores.tolist(),
            "kappa_plus": global_factor,
            "exact_global_kappa_plus": global_factor,
            "global_kappa_plus_C_hat_C_full": global_factor,
            "action_set_transfer": ratios.maximum_squared_ratio,
            "action_set_max_cbar_width_squared_over_chat_width_squared": ratios.maximum_squared_ratio,
            "action_set_max_cbar_width_over_chat_width": ratios.maximum_width_ratio,
            "action_set_ratio_bounded_by_global_kappa": bool(
                ratios.maximum_squared_ratio <= global_factor + global_tolerance
            ),
            "chat_widths_squared": ratios.chat_widths_squared.tolist(),
            "cbar_widths_squared": ratios.cbar_widths_squared.tolist(),
            "width_ratio_chat_over_cbar": (chat_width / cbar_width).tolist(),
            "max_relative_width_distortion": float(
                np.max(np.abs(chat_width / cbar_width - 1.0))
            ),
            "width_distortion": float(
                np.max(np.abs(chat_width / cbar_width - 1.0))
            ),
            "optimism_violation_count": int(np.count_nonzero(violations)),
            "optimism_violation": bool(np.any(violations)),
            "information_increment": information,
            "Lambda_alg_cumulative": cumulative_information,
            "transition_logdet": transition,
            "variation_increment": variation,
            "V_alg_cumulative": cumulative_variation,
            "endpoint_logdet": endpoint,
            "Gamma_dynamic_cumulative": dynamic,
            "dynamic_identity_residual": identity_residual,
            "C_full_equals_C_bar": bool(np.array_equal(c_full, c_bar)),
            "window_global_kappa_le_one": (
                bool(global_factor <= 1.0 + global_tolerance)
                if spec.kind == "unrescaled_window"
                else None
            ),
            "operator_metadata": current.metadata,
            "float_dtype": "float64",
        }
        records.append(record)
        history = next_history
        reference += np.outer(played, played) / variance

    last = records[-1]
    disagreement_count = sum(bool(item["action_disagrees_with_full"]) for item in records)
    summary = {
        "operator": spec.name,
        "operator_kind": spec.kind,
        "operator_parameter": spec.parameter,
        "seed": int(seed),
        "rounds": trajectory.rounds,
        "execution_mode": "offline_common_trajectory_diagnostic",
        "executed_policy": False,
        "offline_diagnostic": True,
        "causal_regret_claim": False,
        "regret_reported": False,
        "trajectory_digest": trajectory.digest,
        "source_operator": trajectory.source_operator,
        "fixed_damping": trajectory.damping,
        "same_fixed_trajectory": True,
        "Lambda_alg_T": float(last["Lambda_alg_cumulative"]),
        "V_alg_T": float(last["V_alg_cumulative"]),
        "Gamma_dynamic_T": float(last["Gamma_dynamic_cumulative"]),
        "endpoint_logdet_T": float(last["endpoint_logdet"]),
        "dynamic_identity_residual": float(last["dynamic_identity_residual"]),
        "kappa_plus_max": max(float(item["kappa_plus"]) for item in records),
        "exact_global_kappa_plus_max": max(
            float(item["exact_global_kappa_plus"]) for item in records
        ),
        "action_set_max_cbar_width_squared_over_chat_width_squared": max(
            float(item["action_set_max_cbar_width_squared_over_chat_width_squared"])
            for item in records
        ),
        "action_set_transfer_max": max(
            float(item["action_set_transfer"]) for item in records
        ),
        "max_relative_width_distortion": max(
            float(item["max_relative_width_distortion"]) for item in records
        ),
        "width_distortion_max": max(float(item["width_distortion"]) for item in records),
        "action_disagreement_count": disagreement_count,
        "action_disagreement_with_full_count": disagreement_count,
        "action_disagreement_rate": float(disagreement_count / trajectory.rounds),
        "optimism_violation_count": sum(
            int(item["optimism_violation_count"]) for item in records
        ),
        "window_global_kappa_le_one_all_rounds": (
            all(bool(item["window_global_kappa_le_one"]) for item in records)
            if spec.kind == "unrescaled_window"
            else None
        ),
        "float_dtype": "float64",
    }
    return OfflineOperatorDiagnostic(
        spec=spec,
        seed=int(seed),
        trajectory=trajectory,
        rounds=tuple(records),
        summary=summary,
    )


def _select_specs(
    configured: Sequence[OperatorSpec], selected: Sequence[str | OperatorSpec] | None
) -> tuple[OperatorSpec, ...]:
    if selected is None:
        return tuple(configured)
    result: list[OperatorSpec] = []
    for item in selected:
        if isinstance(item, OperatorSpec):
            candidates = (item,)
        else:
            normalized = str(item).strip().lower().replace("-", "_")
            exact = tuple(
                spec
                for spec in configured
                if spec.name.lower().replace("-", "_") == normalized
            )
            if exact:
                result.extend(exact)
                continue
            kind_alias = {"windowed": "unrescaled_window", "subsampled": "rescaled_subsample", "periodic_refresh": "stale_refresh"}.get(normalized, normalized)
            if kind_alias in OPERATOR_KINDS:
                candidates = tuple(spec for spec in configured if spec.kind == kind_alias)
                if not candidates and kind_alias in {"full", "frozen", "diagonal"}:
                    candidates = (OperatorSpec(kind_alias),)
            else:
                candidates = (canonical_operator_spec(item),)
        result.extend(candidates)
    if not result:
        raise ValueError("operator selection resolved to no concrete settings")
    return tuple(dict.fromkeys(result))


def evaluate_common_trajectory(
    config: Mapping[str, Any] | OperatorAblationConfig,
    trajectory: FixedLoggedTrajectory,
    seed: int,
    *,
    operators: Sequence[str | OperatorSpec] | None = None,
) -> CommonTrajectoryResult:
    resolved = (
        config if isinstance(config, OperatorAblationConfig) else OperatorAblationConfig.from_mapping(config)
    )
    specs = _select_specs(resolved.specs, operators)
    diagnostics = tuple(
        _offline_diagnostic(resolved.linear, spec, seed, trajectory) for spec in specs
    )
    digests = {diagnostic.trajectory.digest for diagnostic in diagnostics}
    if digests != {trajectory.digest}:
        raise AssertionError("offline diagnostics did not use one fixed trajectory")
    summary = {
        "seed": int(seed),
        "execution_mode": "offline_common_trajectory_diagnostic",
        "executed_policy": False,
        "offline_diagnostic": True,
        "causal_regret_claim": False,
        "regret_reported": False,
        "same_fixed_trajectory": True,
        "trajectory_digest": trajectory.digest,
        "source_operator": trajectory.source_operator,
        "operators": [diagnostic.spec.name for diagnostic in diagnostics],
        "rounds": trajectory.rounds,
        "fixed_damping": trajectory.damping,
        "fixed_bonus_coefficients": trajectory.bonus_coefficients.tolist(),
    }
    return CommonTrajectoryResult(
        seed=int(seed),
        trajectory=trajectory,
        diagnostics=diagnostics,
        summary=summary,
    )


def run_common_trajectory(
    config: Mapping[str, Any] | OperatorAblationConfig,
    seed: int,
    *,
    operators: Sequence[str | OperatorSpec] | None = None,
    source_run: OnlineOperatorRun | None = None,
) -> CommonTrajectoryResult:
    """Evaluate operators on one fixed full-policy log; this is not a policy run."""

    resolved = (
        config if isinstance(config, OperatorAblationConfig) else OperatorAblationConfig.from_mapping(config)
    )
    source = source_run or run_operator(resolved, OperatorSpec("full"), seed)
    trajectory = fixed_trajectory_from_run(source)
    return evaluate_common_trajectory(
        resolved, trajectory, seed, operators=operators
    )


@dataclass(frozen=True)
class OperatorAblationResult:
    seed: int
    config: OperatorAblationConfig
    online_runs: tuple[OnlineOperatorRun, ...]
    common_trajectory: CommonTrajectoryResult | None
    summary: dict[str, Any]

    @property
    def runs(self) -> tuple[OnlineOperatorRun, ...]:
        return self.online_runs


def run_operator_ablation(
    config: Mapping[str, Any] | OperatorAblationConfig,
    seed: int,
    *,
    operators: Sequence[str | OperatorSpec] | None = None,
    include_common_trajectory: bool | None = None,
    retain_matrices: bool = False,
) -> OperatorAblationResult:
    """Run one seed of the complete operator ablation."""

    resolved = (
        config if isinstance(config, OperatorAblationConfig) else OperatorAblationConfig.from_mapping(config)
    )
    specs = _select_specs(resolved.specs, operators)
    runs = tuple(
        run_operator(resolved, spec, seed, retain_matrices=retain_matrices)
        for spec in specs
    )
    include_offline = (
        resolved.common_trajectory_enabled
        if include_common_trajectory is None
        else bool(include_common_trajectory)
    )
    source = next((run for run in runs if run.spec.kind == "full"), None)
    common = (
        run_common_trajectory(resolved, seed, operators=specs, source_run=source)
        if include_offline
        else None
    )

    full = next((run for run in runs if run.spec.kind == "full"), None)
    frozen = next((run for run in runs if run.spec.kind == "frozen"), None)
    full_frozen_equal = None
    if full is not None and frozen is not None:
        full_frozen_equal = bool(
            full.actions == frozen.actions
            and np.array_equal(full.contexts, frozen.contexts)
            and np.array_equal(full.played_features, frozen.played_features)
        )
    summary = {
        "seed": int(seed),
        "rounds": resolved.linear.rounds,
        "operators": [run.spec.name for run in runs],
        "online_executed_policies": True,
        "full_frozen_identical_in_linear_environment": full_frozen_equal,
        "C_full_equals_C_bar": all(
            bool(run.summary["C_full_equals_C_bar_all_rounds"]) for run in runs
        ),
        "window_global_kappa_le_one": all(
            bool(run.summary["window_global_kappa_le_one_all_rounds"])
            for run in runs
            if run.spec.kind == "unrescaled_window"
        ),
        "common_trajectory_included": common is not None,
        "common_trajectory_offline": common is not None,
        "common_trajectory_causal_regret_claim": False,
        "fixed_environment": {
            "context_dimension": CONTEXT_DIMENSION,
            "action_count": ACTION_COUNT,
            "feature_dimension": FEATURE_DIMENSION,
            "dtype": "float64",
        },
        "online_summaries": [run.summary for run in runs],
        "common_trajectory_summary": None if common is None else common.summary,
    }
    return OperatorAblationResult(
        seed=int(seed),
        config=resolved,
        online_runs=runs,
        common_trajectory=common,
        summary=summary,
    )


def _manifest_config(
    source: Mapping[str, Any], *, mode: str, operator: OperatorSpec, seed: int
) -> dict[str, Any]:
    config = dict(source)
    config["execution"] = {
        "mode": mode,
        "operator": operator.name,
        "operator_kind": operator.kind,
        "operator_parameter": operator.parameter,
        "seed": int(seed),
        "fixed_linear_environment": {
            "context_dimension": CONTEXT_DIMENSION,
            "action_count": ACTION_COUNT,
            "feature_dimension": FEATURE_DIMENSION,
            "dtype": "float64",
        },
    }
    return config


def _save_records(
    records: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    destination: Path,
    manifest_config: Mapping[str, Any],
    seed: int,
    *,
    overwrite: bool,
) -> None:
    with ExperimentLogger(
        destination,
        manifest_config,
        int(seed),
        repository=Path(__file__).resolve().parents[1],
        overwrite=overwrite,
    ) as logger:
        for index, record in enumerate(records):
            logger.log_round(index, record)
    summary_path = destination / "summary.jsonl"
    if overwrite and summary_path.exists():
        summary_path.unlink()
    append_jsonl(summary_path, summary)


def save_operator_ablation(
    result: OperatorAblationResult,
    output_root: str | Path,
    source_config: Mapping[str, Any],
    *,
    seed_set: str = "evaluation",
    overwrite: bool = False,
) -> Path:
    root = Path(output_root)
    profile = str(source_config.get("profile", "default"))
    base = root / profile / seed_set
    for run in result.online_runs:
        destination = base / run.spec.name / f"seed-{result.seed}"
        _save_records(
            run.rounds,
            run.summary,
            destination,
            _manifest_config(
                source_config,
                mode="online_adaptive",
                operator=run.spec,
                seed=result.seed,
            ),
            result.seed,
            overwrite=overwrite,
        )
    if result.common_trajectory is not None:
        for diagnostic in result.common_trajectory.diagnostics:
            destination = (
                base
                / "offline_common_trajectory"
                / diagnostic.spec.name
                / f"seed-{result.seed}"
            )
            _save_records(
                diagnostic.rounds,
                diagnostic.summary,
                destination,
                _manifest_config(
                    source_config,
                    mode="offline_common_trajectory_diagnostic",
                    operator=diagnostic.spec,
                    seed=result.seed,
                ),
                result.seed,
                overwrite=overwrite,
            )
    return base


def run_experiment(
    config: Mapping[str, Any],
    *,
    seed_set: str = "evaluation",
    operators: Sequence[str | OperatorSpec] | None = None,
    output_root: str | Path | None = None,
    include_common_trajectory: bool | None = None,
    overwrite: bool = False,
) -> tuple[OperatorAblationResult, ...]:
    seeds = get_seed_set(config, seed_set)
    results: list[OperatorAblationResult] = []
    for seed in seeds:
        result = run_operator_ablation(
            config,
            int(seed),
            operators=operators,
            include_common_trajectory=include_common_trajectory,
        )
        results.append(result)
        if output_root is not None:
            save_operator_ablation(
                result,
                output_root,
                config,
                seed_set=seed_set,
                overwrite=overwrite,
            )
    return tuple(results)


def run_nonlinear_experiment(
    config: Mapping[str, Any],
    *,
    seed_set: str = "evaluation",
    operators: Sequence[str | OperatorSpec] | None = None,
    output_root: str | Path | None = None,
    include_common_trajectory: bool | None = None,
    overwrite: bool = False,
) -> tuple[Any, ...]:
    """Execute the smooth nonlinear operator grid and optional offline audit."""

    from .nonlinear_operator_ablation import (
        run_nonlinear_operator_ablation,
        save_nonlinear_operator_ablation,
    )

    seeds = get_seed_set(config, seed_set)
    results: list[Any] = []
    for seed in seeds:
        result = run_nonlinear_operator_ablation(
            config,
            int(seed),
            operators=operators,
            include_common_trajectory=include_common_trajectory,
            measure_resources=True,
        )
        results.append(result)
        if output_root is not None:
            save_nonlinear_operator_ablation(
                result,
                output_root,
                config,
                seed_set=seed_set,
                overwrite=overwrite,
            )
    return tuple(results)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("configs") / "operator_ablation.yaml",
    )
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument(
        "--seed-set", choices=("tuning", "evaluation"), default="evaluation"
    )
    parser.add_argument(
        "--environment",
        choices=("linear", "nonlinear", "both"),
        default="linear",
        help="environment family to execute; use 'both' for the complete ablation",
    )
    parser.add_argument(
        "--operator",
        action="append",
        help="concrete setting or kind; repeat to select multiple settings",
    )
    parser.add_argument("--rounds", type=int, help="override the resolved horizon")
    parser.add_argument(
        "--output-root",
        "--output-dir",
        dest="output_root",
        type=Path,
        default=Path("experiments/results/operator_ablation"),
    )
    parser.add_argument("--no-common-trajectory", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config, profile=args.profile)
    if args.rounds is not None:
        if args.rounds <= 0:
            parser.error("--rounds must be positive")
        config["rounds"] = args.rounds
        nonlinear_options = config.get("nonlinear_audit")
        if isinstance(nonlinear_options, Mapping):
            nonlinear_options["rounds"] = args.rounds
    linear_results: tuple[Any, ...] = ()
    nonlinear_results: tuple[Any, ...] = ()
    if args.environment in {"linear", "both"}:
        linear_results = run_experiment(
            config,
            seed_set=args.seed_set,
            operators=args.operator,
            output_root=args.output_root,
            include_common_trajectory=not args.no_common_trajectory,
            overwrite=args.overwrite,
        )
    if args.environment in {"nonlinear", "both"}:
        nonlinear_results = run_nonlinear_experiment(
            config,
            seed_set=args.seed_set,
            operators=args.operator,
            output_root=args.output_root,
            include_common_trajectory=not args.no_common_trajectory,
            overwrite=args.overwrite,
        )
    print(
        json.dumps(
            {
                "profile": args.profile,
                "seed_set": args.seed_set,
                "environment": args.environment,
                "linear_seed_count": len(linear_results),
                "nonlinear_seed_count": len(nonlinear_results),
                "run_count": len(linear_results) + len(nonlinear_results),
                "output_root": str(args.output_root),
                "linear_summaries": [result.summary for result in linear_results],
                "nonlinear_summaries": [
                    result.summary for result in nonlinear_results
                ],
            },
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ActionSetWidthResult",
    "CommonTrajectoryResult",
    "DEFAULT_CONFIG",
    "FixedLoggedTrajectory",
    "OPERATOR_KINDS",
    "OfflineOperatorDiagnostic",
    "OnlineOperatorRun",
    "OperatorAblationConfig",
    "OperatorAblationResult",
    "OperatorSpec",
    "action_set_max_width_ratio",
    "action_set_width_ratios",
    "canonical_operator_spec",
    "configured_operator_specs",
    "evaluate_common_trajectory",
    "exact_global_kappa_plus",
    "exact_kappa_plus",
    "fixed_trajectory_from_run",
    "global_kappa_plus",
    "main",
    "max_action_set_width_ratio",
    "run_common_trajectory",
    "run_experiment",
    "run_nonlinear_experiment",
    "run_operator",
    "run_operator_ablation",
    "run_operator_policy",
    "save_operator_ablation",
]
