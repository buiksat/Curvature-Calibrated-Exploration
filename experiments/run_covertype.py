"""Run the documented Covertype classes-as-arms experiment.

The driver deliberately separates validation-seed hyperparameter selection from
test-seed evaluation.  Every saved trajectory is an actually executed policy;
evaluation accepts only a selection artifact produced on the validation split.

The binary reward is modelled with squared loss and unit-weight Gaussian GGN
curvature.  This is an experimental curvature choice, not a certification by
the Gaussian regret theorem.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import hmac
import json
import math
import os
import resource
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

try:  # Package execution: python -m experiments.run_covertype
    from .config import config_digest, get_seed_set, load_config
    from .curvature_operators import conjugate_gradient
    from .logging_utils import (
        ExperimentLogger,
        append_jsonl,
        canonical_json,
        derive_seed,
    )
    from .nonlinear_environment import MLPLayout, SmallTanhMLP
except ImportError:  # Direct execution from the repository root.
    from experiments.config import config_digest, get_seed_set, load_config
    from experiments.curvature_operators import conjugate_gradient
    from experiments.logging_utils import (
        ExperimentLogger,
        append_jsonl,
        canonical_json,
        derive_seed,
    )
    from experiments.nonlinear_environment import MLPLayout, SmallTanhMLP


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
Phase = Literal["tuning", "evaluation"]

SUPPORTED_METHODS = (
    "full_network_ggn_cg",
    "frozen_full_gram",
    "diagonal_full_network",
    "last_layer_full",
    "last_layer_diagonal",
    "greedy_full_network",
    "ucb1",
    "thompson_sampling",
)

NONCONTEXTUAL_METHODS = ("ucb1", "thompson_sampling")

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = Path(__file__).with_name("configs") / "covertype_rerun.yaml"


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _timestamp(value: dt.datetime | str) -> str:
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _peak_host_memory_bytes() -> int:
    maximum = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return maximum if sys.platform == "darwin" else maximum * 1024


def _positive_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _nonnegative_int(value: Any, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def _positive_float(value: Any, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _nonnegative_float(value: Any, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


def _readonly(array: ArrayLike, *, dtype: np.dtype[Any] | type = np.float64) -> NDArray[Any]:
    result = np.asarray(array, dtype=dtype).copy()
    result.setflags(write=False)
    return result


def _array_sha256(array: ArrayLike) -> str:
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(tuple(contiguous.shape)).encode("ascii"))
    digest.update(contiguous.dtype.str.encode("ascii"))
    digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _dataset_section(config: Mapping[str, Any]) -> Mapping[str, Any]:
    section = config.get("dataset")
    if not isinstance(section, Mapping):
        raise ValueError("config.dataset must be an object")
    return section


def _model_section(config: Mapping[str, Any]) -> Mapping[str, Any]:
    section = config.get("model")
    if not isinstance(section, Mapping):
        raise ValueError("config.model must be an object")
    return section


@dataclass(frozen=True)
class PreparedCovertypeData:
    """One standardized dataset plus immutable exact split indices."""

    features: FloatArray
    labels: IntArray
    split_indices: Mapping[str, IntArray]
    provenance: Mapping[str, Any]
    preprocessing: Mapping[str, Any]
    split_protocol: Mapping[str, Any]

    @property
    def feature_count(self) -> int:
        return int(self.features.shape[1])

    @property
    def class_count(self) -> int:
        return int(self.preprocessing["class_count"])

    def indices(self, split: str) -> IntArray:
        if split not in self.split_indices:
            raise ValueError(f"unknown split {split!r}")
        return self.split_indices[split]

    def split(self, split: str) -> tuple[FloatArray, IntArray]:
        indices = self.indices(split)
        return self.features[indices], self.labels[indices]

    @property
    def dataset_sha256(self) -> str:
        return str(self.provenance["checksum_sha256"])


DatasetInput = tuple[ArrayLike, ArrayLike]
DatasetFetcher = Callable[..., Any]


def _coerce_fetched_dataset(value: Any) -> tuple[ArrayLike, ArrayLike]:
    if isinstance(value, tuple) and len(value) == 2:
        return value[0], value[1]
    data = getattr(value, "data", None)
    target = getattr(value, "target", None)
    if data is None or target is None:
        raise TypeError("dataset loader must return (features, labels) or a Bunch")
    return data, target


def _cache_file_records(data_home: Path) -> list[dict[str, Any]]:
    directory = data_home / "covertype"
    if not directory.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        records.append(
            {
                "path": str(path.resolve()),
                "size_bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    return records


def _raw_dataset_checksum(
    features: ArrayLike, labels: ArrayLike, files: Sequence[Mapping[str, Any]]
) -> str:
    if files:
        identity = [
            {
                "name": Path(str(item["path"])).name,
                "size_bytes": int(item["size_bytes"]),
                "sha256": str(item["sha256"]),
            }
            for item in files
        ]
        return hashlib.sha256(canonical_json(identity).encode("ascii")).hexdigest()
    digest = hashlib.sha256()
    digest.update(_array_sha256(features).encode("ascii"))
    digest.update(_array_sha256(labels).encode("ascii"))
    return digest.hexdigest()


def _normalize_labels(labels: ArrayLike, class_count: int) -> IntArray:
    raw = np.asarray(labels)
    if raw.ndim != 1:
        raise ValueError(f"labels must be one-dimensional, got shape {raw.shape}")
    if raw.size == 0 or not np.all(np.isfinite(raw)):
        raise ValueError("labels must be nonempty and finite")
    integral = raw.astype(np.int64)
    if not np.array_equal(raw, integral):
        raise ValueError("labels must be integer-valued")
    # Covertype's native labels are one-based.  A zero anywhere is an explicit
    # signal that an injected test fixture already uses arm indices.
    if np.all((1 <= integral) & (integral <= class_count)):
        normalized = integral - 1
    elif np.all((0 <= integral) & (integral < class_count)):
        normalized = integral
    else:
        raise ValueError(
            f"labels must use either 0..{class_count - 1} or 1..{class_count}"
        )
    result = np.asarray(normalized, dtype=np.int64).copy()
    result.setflags(write=False)
    return result


def prepare_covertype_data(
    config: Mapping[str, Any],
    *,
    download: bool = False,
    dataset: DatasetInput | None = None,
    fetcher: DatasetFetcher | None = None,
    data_home: str | Path | None = None,
    clock: Callable[[], dt.datetime | str] = _utc_now,
) -> PreparedCovertypeData:
    """Load, split, and train-standardize Covertype.

    ``dataset`` is the offline injection point used by tests.  Supplying it
    bypasses scikit-learn and all network/cache access.
    """

    dataset_config = _dataset_section(config)
    feature_count = _positive_int(dataset_config.get("feature_count"), name="feature_count")
    class_count = _positive_int(dataset_config.get("class_count"), name="class_count")
    split_seed = _nonnegative_int(dataset_config.get("split_seed"), name="split_seed")
    raw_fractions = dataset_config.get("split_fractions")
    if (
        not isinstance(raw_fractions, Sequence)
        or isinstance(raw_fractions, (str, bytes))
        or len(raw_fractions) != 3
    ):
        raise ValueError("dataset.split_fractions must contain train/validation/test")
    fractions = tuple(float(value) for value in raw_fractions)
    if any(not np.isfinite(value) or value <= 0.0 for value in fractions):
        raise ValueError("split fractions must be finite and positive")
    if not math.isclose(sum(fractions), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("split fractions must sum to one")

    configured_columns = dataset_config.get("continuous_columns")
    if not isinstance(configured_columns, Sequence) or isinstance(
        configured_columns, (str, bytes)
    ):
        raise ValueError("dataset.continuous_columns must be a sequence")
    continuous = tuple(int(column) for column in configured_columns)
    if len(set(continuous)) != len(continuous) or any(
        column < 0 or column >= feature_count for column in continuous
    ):
        raise ValueError("continuous columns must be unique valid feature indices")

    injected = dataset is not None
    custom_fetcher = fetcher is not None
    official_sklearn_fetcher = False
    resolved_home = (
        Path(data_home)
        if data_home is not None
        else REPOSITORY_ROOT / str(dataset_config.get("data_home", "experiments/data/sklearn"))
    )
    if injected:
        raw_features, raw_labels = dataset
        files: list[dict[str, Any]] = []
        loader_name = "injected_array_dataset"
        version = "synthetic/injected"
    else:
        if fetcher is None:
            from sklearn import __version__ as sklearn_version
            from sklearn.datasets import fetch_covtype

            fetcher = fetch_covtype
            official_sklearn_fetcher = True
            version = f"UCI Covertype DOI 10.24432/C50K5N via scikit-learn {sklearn_version}"
        else:
            try:
                from sklearn import __version__ as sklearn_version
            except ImportError:  # pragma: no cover - runner depends on sklearn in production.
                sklearn_version = "unavailable"
            version = f"custom fetcher; scikit-learn {sklearn_version}"
        fetched = fetcher(
            data_home=str(resolved_home),
            download_if_missing=bool(download),
            return_X_y=True,
            shuffle=False,
        )
        raw_features, raw_labels = _coerce_fetched_dataset(fetched)
        files = _cache_file_records(resolved_home)
        if official_sklearn_fetcher:
            loader_name = str(
                dataset_config.get("loader", "sklearn.datasets.fetch_covtype")
            )
        else:
            module = getattr(fetcher, "__module__", "unknown")
            qualified_name = getattr(
                fetcher, "__qualname__", getattr(fetcher, "__name__", "callable")
            )
            loader_name = f"{module}.{qualified_name}"

    raw_array = np.asarray(raw_features)
    if raw_array.ndim != 2 or raw_array.shape[1] != feature_count:
        raise ValueError(
            f"features must have shape (n, {feature_count}), got {raw_array.shape}"
        )
    if raw_array.shape[0] < 3 or not np.all(np.isfinite(raw_array)):
        raise ValueError("features must contain at least three finite rows")
    raw_label_array = np.asarray(raw_labels)
    if raw_label_array.shape != (raw_array.shape[0],):
        raise ValueError("features and labels must have the same sample count")
    checksum = _raw_dataset_checksum(raw_array, raw_label_array, files)

    labels = _normalize_labels(raw_label_array, class_count)
    label_base = 1 if np.all((1 <= raw_label_array) & (raw_label_array <= class_count)) else 0
    # Preserve injected caller arrays and permit in-place standardization of a
    # freshly loaded sklearn cache array to avoid a second 250 MB full copy.
    features = np.array(
        raw_array,
        dtype=np.float64,
        copy=injected or custom_fetcher or raw_array.dtype != np.float64,
    )
    if not features.flags.writeable:
        features = features.copy()

    sample_count = int(features.shape[0])
    permutation = np.random.default_rng(split_seed).permutation(sample_count).astype(
        np.int64, copy=False
    )
    train_count = int(math.floor(fractions[0] * sample_count))
    validation_count = int(math.floor(fractions[1] * sample_count))
    test_count = sample_count - train_count - validation_count
    if min(train_count, validation_count, test_count) <= 0:
        raise ValueError("configured split leaves an empty partition")
    train_indices = permutation[:train_count]
    validation_indices = permutation[train_count : train_count + validation_count]
    test_indices = permutation[train_count + validation_count :]

    continuous_array = np.asarray(continuous, dtype=np.int64)
    train_continuous = features[np.ix_(train_indices, continuous_array)]
    means = np.mean(train_continuous, axis=0, dtype=np.float64)
    scales = np.std(train_continuous, axis=0, dtype=np.float64)
    constant = scales == 0.0
    scales[constant] = 1.0
    features[:, continuous_array] = (features[:, continuous_array] - means) / scales
    if not np.all(np.isfinite(features)):
        raise FloatingPointError("standardization produced non-finite features")

    immutable_features = np.asarray(features, dtype=np.float64)
    immutable_features.setflags(write=False)
    split_indices: dict[str, IntArray] = {
        "train": _readonly(train_indices, dtype=np.int64),
        "validation": _readonly(validation_indices, dtype=np.int64),
        "test": _readonly(test_indices, dtype=np.int64),
    }
    split_records = {
        name: {
            "count": int(indices.size),
            "indices_sha256": _array_sha256(indices),
            "indices_artifact": None,
            "indices_artifact_sha256": None,
        }
        for name, indices in split_indices.items()
    }
    accessed_at = _timestamp(clock())
    provenance = {
        "loader": loader_name,
        "source": str(dataset_config.get("source", "UCI Covertype")),
        "version": version,
        "dataset_version": version,
        "access_timestamp_utc": accessed_at,
        "dataset_access_timestamp_utc": accessed_at,
        "data_home": None if injected else str(resolved_home.resolve()),
        "download_allowed": bool(download),
        "injected": injected,
        "dataset_file": [record["path"] for record in files],
        "dataset_files": files,
        "checksum_algorithm": "sha256",
        "checksum_sha256": checksum,
        "dataset_checksum_sha256": checksum,
        "upstream_archive_sha256": (
            None
            if injected or not official_sklearn_fetcher
            else "614360d0257557dd1792834a85a1cdebfadc3c4f30b011d56afee7ffb5b15771"
        ),
        "sample_count": sample_count,
        "feature_count": feature_count,
        "class_count": class_count,
    }
    preprocessing = {
        "dtype": "float64",
        "fit_split": "train",
        "continuous_columns": list(continuous),
        "continuous_mean": means.tolist(),
        "continuous_scale": scales.tolist(),
        "constant_continuous_columns": [
            continuous[index] for index in np.flatnonzero(constant)
        ],
        "binary_columns": [column for column in range(feature_count) if column not in continuous],
        "binary_columns_unchanged": bool(dataset_config.get("binary_columns_unchanged", True)),
        "label_source_base": label_base,
        "label_arm_base": 0,
        "class_count": class_count,
    }
    split_protocol = {
        "algorithm": "numpy.random.Generator(PCG64).permutation_then_contiguous_slices",
        "stratified": False,
        "seed": split_seed,
        "fractions": list(fractions),
        "rounding": "floor_train_floor_validation_test_remainder",
        "partitions": split_records,
    }
    return PreparedCovertypeData(
        features=immutable_features,
        labels=labels,
        split_indices=split_indices,
        provenance=provenance,
        preprocessing=preprocessing,
        split_protocol=split_protocol,
    )


# Short aliases for callers and tests.
prepare_dataset = prepare_covertype_data
load_covertype_data = prepare_covertype_data


@dataclass(frozen=True)
class MethodProtocol:
    name: str
    trained_parameter_set: str
    curvature_parameter_set: str
    curvature_representation: str
    historical_linearization: str
    inverse_solver: str


def method_protocol(method: str) -> MethodProtocol:
    if method not in SUPPORTED_METHODS:
        raise ValueError(f"unknown method {method!r}; choose from {SUPPORTED_METHODS}")
    values = {
        "full_network_ggn_cg": MethodProtocol(
            method,
            "all_parameters",
            "all_parameters",
            "full_matrix_free_ggn",
            "all_history_relinearized_at_current_parameters",
            "conjugate_gradient_from_zero",
        ),
        "frozen_full_gram": MethodProtocol(
            method,
            "all_parameters",
            "all_parameters",
            "full_acquisition_time_gradient_gram",
            "each_observation_frozen_at_its_pre_update_acquisition_parameters",
            "exact_rank_one_sherman_morrison",
        ),
        "diagonal_full_network": MethodProtocol(
            method,
            "all_parameters",
            "all_parameters",
            "diagonal_ggn",
            "all_history_relinearized_at_current_parameters",
            "elementwise_diagonal_inverse",
        ),
        "last_layer_full": MethodProtocol(
            method,
            "output_weight_and_bias",
            "output_weight_and_bias",
            "full_last_layer_gram",
            "fixed_backbone_features",
            "exact_rank_one_sherman_morrison",
        ),
        "last_layer_diagonal": MethodProtocol(
            method,
            "output_weight_and_bias",
            "output_weight_and_bias",
            "diagonal_last_layer_gram",
            "fixed_backbone_features",
            "elementwise_diagonal_inverse",
        ),
        "greedy_full_network": MethodProtocol(
            method,
            "all_parameters",
            "none",
            "none",
            "none",
            "none",
        ),
        "ucb1": MethodProtocol(
            method,
            "per_arm_reward_counts",
            "none",
            "none",
            "none",
            "closed_form_ucb1_index",
        ),
        "thompson_sampling": MethodProtocol(
            method,
            "independent_per_arm_beta_posterior",
            "none",
            "none",
            "none",
            "independent_beta_sampling",
        ),
    }
    return values[method]


def _initial_model(
    feature_count: int, class_count: int, hidden_width: int, seed: int
) -> tuple[SmallTanhMLP, FloatArray]:
    layout = MLPLayout(
        context_dimension=feature_count,
        hidden_width=hidden_width,
        action_count=class_count,
    )
    rng = np.random.default_rng(seed)
    input_weights = rng.normal(
        0.0,
        1.0 / math.sqrt(float(feature_count)),
        size=(hidden_width, feature_count),
    )
    hidden_bias = np.zeros(hidden_width, dtype=np.float64)
    output_weights = rng.normal(
        0.0,
        1.0 / math.sqrt(float(hidden_width)),
        size=(class_count, hidden_width),
    )
    output_bias = np.zeros(class_count, dtype=np.float64)
    base = layout.pack(input_weights, hidden_bias, output_weights, output_bias)
    model = SmallTanhMLP(layout, base_parameters=base)
    displacement = np.zeros(layout.parameter_dimension, dtype=np.float64)
    return model, displacement


def _batch_selected_jacobians(
    model: SmallTanhMLP,
    displacement: FloatArray,
    contexts: Sequence[FloatArray],
    actions: Sequence[int],
) -> FloatArray:
    count = len(contexts)
    if count != len(actions):
        raise ValueError("context and action histories disagree")
    if count == 0:
        return np.empty((0, model.parameter_dimension), dtype=np.float64)
    x = np.asarray(contexts, dtype=np.float64)
    chosen = np.asarray(actions, dtype=np.int64)
    layout = model.layout
    w, b, v, _ = layout.unpack(model.base_parameters + displacement)
    hidden = np.tanh(x @ w.T + b)
    sensitivity = v[chosen] * (1.0 - hidden * hidden)
    result = np.zeros((count, layout.parameter_dimension), dtype=np.float64)
    result[:, : layout.weight_count] = (sensitivity[:, :, None] * x[:, None, :]).reshape(
        count, -1
    )
    result[:, layout.weight_count : layout.backbone_dimension] = sensitivity
    rows = np.arange(count, dtype=np.int64)
    output_start = layout.backbone_dimension
    for hidden_index in range(layout.hidden_width):
        columns = output_start + chosen * layout.hidden_width + hidden_index
        result[rows, columns] = hidden[:, hidden_index]
    bias_start = output_start + layout.action_count * layout.hidden_width
    result[rows, bias_start + chosen] = 1.0
    return result


def _stream_positions(size: int, rounds: int, seed: int) -> IntArray:
    if size <= 0:
        raise ValueError("environment split must be nonempty")
    rng = np.random.default_rng(seed)
    pieces: list[IntArray] = []
    remaining = rounds
    while remaining:
        permutation = rng.permutation(size).astype(np.int64, copy=False)
        take = min(remaining, size)
        pieces.append(permutation[:take])
        remaining -= take
    return np.concatenate(pieces).astype(np.int64, copy=False)


def _method_indices(model: SmallTanhMLP, protocol: MethodProtocol) -> IntArray:
    if protocol.trained_parameter_set == "output_weight_and_bias":
        return np.asarray(model.head_indices, dtype=np.int64)
    return np.arange(model.parameter_dimension, dtype=np.int64)


def _rank_one_inverse_update(inverse: FloatArray, feature: FloatArray) -> FloatArray:
    projected = inverse @ feature
    denominator = 1.0 + float(feature @ projected)
    if not np.isfinite(denominator) or denominator <= 0.0:
        raise ArithmeticError("rank-one Gram update lost positive definiteness")
    updated = inverse - np.outer(projected, projected) / denominator
    return np.asarray(0.5 * (updated + updated.T), dtype=np.float64)


@dataclass(frozen=True)
class WidthResult:
    widths_squared: FloatArray
    cg_iterations: IntArray
    cg_relative_residuals: FloatArray
    cg_converged: tuple[bool, ...]
    curvature_vector_products: IntArray
    curvature_trace: float


def _policy_widths(
    method: str,
    damping: float,
    model: SmallTanhMLP,
    displacement: FloatArray,
    query_jacobians: FloatArray,
    trainable_indices: IntArray,
    contexts: Sequence[FloatArray],
    actions: Sequence[int],
    gram_inverse: FloatArray | None,
    gram_diagonal: FloatArray | None,
    *,
    cg_tolerance: float,
    cg_max_iterations: int,
) -> WidthResult:
    action_count = query_jacobians.shape[0]
    zero_iterations = np.zeros(action_count, dtype=np.int64)
    zero_residuals = np.zeros(action_count, dtype=np.float64)
    if method == "greedy_full_network":
        return WidthResult(
            np.zeros(action_count, dtype=np.float64),
            zero_iterations,
            zero_residuals,
            tuple(True for _ in range(action_count)),
            zero_iterations.copy(),
            0.0,
        )

    query = np.asarray(query_jacobians[:, trainable_indices], dtype=np.float64)
    dimension = query.shape[1]
    if method in {"frozen_full_gram", "last_layer_full"}:
        if gram_inverse is None:
            raise AssertionError("full stored Gram requires its maintained inverse")
        if gram_diagonal is None:
            raise AssertionError("full stored Gram requires its maintained diagonal")
        solved = query @ gram_inverse
        widths = np.einsum("ij,ij->i", solved, query, dtype=np.float64)
        return WidthResult(
            np.maximum(widths, 0.0),
            zero_iterations,
            zero_residuals,
            tuple(True for _ in range(action_count)),
            zero_iterations.copy(),
            float(np.sum(gram_diagonal)),
        )

    if method == "last_layer_diagonal":
        if gram_diagonal is None:
            raise AssertionError("last-layer diagonal requires maintained diagonal")
        widths = np.sum(query * query / gram_diagonal[None, :], axis=1)
        return WidthResult(
            np.maximum(widths, 0.0),
            zero_iterations,
            zero_residuals,
            tuple(True for _ in range(action_count)),
            zero_iterations.copy(),
            float(np.sum(gram_diagonal)),
        )

    history = _batch_selected_jacobians(model, displacement, contexts, actions)
    history = np.asarray(history[:, trainable_indices], dtype=np.float64)
    if method == "diagonal_full_network":
        diagonal = damping + np.sum(history * history, axis=0, dtype=np.float64)
        widths = np.sum(query * query / diagonal[None, :], axis=1)
        return WidthResult(
            np.maximum(widths, 0.0),
            zero_iterations,
            zero_residuals,
            tuple(True for _ in range(action_count)),
            zero_iterations.copy(),
            float(np.sum(diagonal)),
        )

    if method != "full_network_ggn_cg":
        raise AssertionError(f"unhandled method {method}")

    # Capture one immutable Jacobian batch.  Every action solve in this round
    # sees the same fixed SPD operator.
    fixed_history = history.copy()
    operator_calls = 0

    def matvec(vector: FloatArray) -> FloatArray:
        nonlocal operator_calls
        operator_calls += 1
        return damping * vector + fixed_history.T @ (fixed_history @ vector)

    widths = np.empty(action_count, dtype=np.float64)
    iterations = np.empty(action_count, dtype=np.int64)
    residuals = np.empty(action_count, dtype=np.float64)
    operator_matvecs = np.empty(action_count, dtype=np.int64)
    converged: list[bool] = []
    for action in range(action_count):
        calls_before_solve = operator_calls
        result = conjugate_gradient(
            matvec,
            query[action],
            tolerance=cg_tolerance,
            absolute_tolerance=0.0,
            max_iterations=cg_max_iterations,
            initial_solution=None,
            raise_on_nonconvergence=False,
        )
        width = float(query[action] @ result.solution)
        if width < -1e-10 or not np.isfinite(width):
            raise ArithmeticError("CG produced an invalid predictive variance")
        widths[action] = max(width, 0.0)
        iterations[action] = result.iterations
        residuals[action] = result.relative_residual_norm
        operator_matvecs[action] = operator_calls - calls_before_solve
        converged.append(bool(result.converged))
    trace = damping * dimension + float(np.sum(fixed_history * fixed_history))
    return WidthResult(
        widths,
        iterations,
        residuals,
        tuple(converged),
        operator_matvecs,
        trace,
    )


@dataclass(frozen=True)
class CovertypeRun:
    method: str
    seed: int
    phase: Phase
    split: str
    damping: float
    bonus_scale: float
    records: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    final_displacement: FloatArray

    @property
    def actions(self) -> tuple[int, ...]:
        return tuple(int(record["action"]) for record in self.records)

    @property
    def dataset_indices(self) -> tuple[int, ...]:
        return tuple(int(record["dataset_index"]) for record in self.records)


def configured_methods(config: Mapping[str, Any]) -> tuple[str, ...]:
    raw = config.get("methods")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        raise ValueError("config.methods must be a nonempty sequence")
    methods = tuple(str(value) for value in raw)
    for method in methods:
        method_protocol(method)
    if len(set(methods)) != len(methods):
        raise ValueError("config.methods contains duplicates")
    return methods


def _grid(config: Mapping[str, Any], name: str) -> tuple[float, ...]:
    raw = config.get(name)
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        raise ValueError(f"config.{name} must be a nonempty sequence")
    values = tuple(_positive_float(value, name=name) for value in raw)
    if len(set(values)) != len(values):
        raise ValueError(f"config.{name} contains duplicates")
    return values


def hyperparameter_grid(
    config: Mapping[str, Any], method: str
) -> tuple[tuple[float, float], ...]:
    method_protocol(method)
    model = _model_section(config)
    if method in NONCONTEXTUAL_METHODS:
        return ((0.0, 0.0),)
    if method == "greedy_full_network":
        return ((_positive_float(model.get("ridge"), name="model.ridge"), 0.0),)
    damping = _grid(config, "damping_grid")
    bonuses = _grid(config, "bonus_grid")
    return tuple((ridge, bonus) for ridge in damping for bonus in bonuses)


def _rounds_for_phase(config: Mapping[str, Any], phase: Phase) -> int:
    if phase == "tuning" and "tuning_rounds" in config:
        return _positive_int(config.get("tuning_rounds"), name="tuning_rounds")
    return _positive_int(config.get("rounds"), name="rounds")


def _selection_damping(method: str, value: Any, *, name: str) -> float:
    if method in NONCONTEXTUAL_METHODS:
        result = _nonnegative_float(value, name=name)
        if result != 0.0:
            raise ValueError(f"{method} is parameter-free and requires {name}=0")
        return result
    return _positive_float(value, name=name)


def _run_noncontextual_policy(
    config: Mapping[str, Any],
    data: PreparedCovertypeData,
    method: str,
    seed: int,
    phase: Phase,
    expected_split: str,
    split_indices: IntArray,
    rounds: int,
) -> CovertypeRun:
    """Run a deployable context-free Bernoulli bandit policy."""

    action_count = data.class_count
    environment_seed = derive_seed(
        seed, "covertype", expected_split, "environment_order"
    )
    policy_seed = (
        derive_seed(
            seed,
            "covertype",
            expected_split,
            "thompson_sampling",
            "posterior_samples",
        )
        if method == "thompson_sampling"
        else None
    )
    policy_rng = None if policy_seed is None else np.random.default_rng(policy_seed)
    stream_positions = _stream_positions(len(split_indices), rounds, environment_seed)
    stream_indices = np.asarray(split_indices[stream_positions], dtype=np.int64)

    pull_counts = np.zeros(action_count, dtype=np.int64)
    reward_sums = np.zeros(action_count, dtype=np.float64)
    posterior_alpha = np.ones(action_count, dtype=np.float64)
    posterior_beta = np.ones(action_count, dtype=np.float64)
    records: list[dict[str, Any]] = []
    cumulative_regret = 0.0
    cumulative_reward = 0.0
    cumulative_runtime = 0.0
    peak_host_memory = _peak_host_memory_bytes()

    for zero_round, dataset_index in enumerate(stream_indices):
        round_started = time.perf_counter()
        round_number = zero_round + 1
        context = np.asarray(data.features[int(dataset_index)], dtype=np.float64)
        label = int(data.labels[int(dataset_index)])
        counts_before = pull_counts.copy()
        rewards_before = reward_sums.copy()

        if method == "ucb1":
            empirical_means = np.divide(
                reward_sums,
                pull_counts,
                out=np.zeros(action_count, dtype=np.float64),
                where=pull_counts > 0,
            )
            forced_initialization = zero_round < action_count
            if forced_initialization:
                action = zero_round
                widths = np.zeros(action_count, dtype=np.float64)
                score_values: list[float | None] = [None] * action_count
            else:
                widths = np.sqrt(
                    2.0 * math.log(float(round_number)) / pull_counts.astype(np.float64)
                )
                ucb_scores = empirical_means + widths
                action = int(np.argmax(ucb_scores))
                score_values = ucb_scores.tolist()
            predictions = empirical_means
            predictive_variances = widths * widths
            method_state: dict[str, Any] = {
                "forced_initialization": forced_initialization,
                "ucb1_index_definition": "empirical_mean_plus_sqrt_2_log_t_over_pulls",
                "ucb_scores": score_values,
                "pull_counts_before": counts_before.tolist(),
                "reward_sums_before": rewards_before.tolist(),
                "empirical_means_before": empirical_means.tolist(),
            }
        elif method == "thompson_sampling":
            if policy_rng is None:  # pragma: no cover - guarded by construction.
                raise AssertionError("Thompson sampling requires its private RNG")
            alpha_before = posterior_alpha.copy()
            beta_before = posterior_beta.copy()
            predictions = alpha_before / (alpha_before + beta_before)
            predictive_variances = (
                alpha_before
                * beta_before
                / (
                    (alpha_before + beta_before) ** 2
                    * (alpha_before + beta_before + 1.0)
                )
            )
            widths = np.sqrt(predictive_variances)
            posterior_samples = policy_rng.beta(alpha_before, beta_before)
            action = int(np.argmax(posterior_samples))
            score_values = posterior_samples.tolist()
            method_state = {
                "beta_prior_alpha": 1.0,
                "beta_prior_beta": 1.0,
                "posterior_independent_across_arms": True,
                "posterior_alpha_before": alpha_before.tolist(),
                "posterior_beta_before": beta_before.tolist(),
                "posterior_samples": posterior_samples.tolist(),
                "pull_counts_before": counts_before.tolist(),
                "reward_sums_before": rewards_before.tolist(),
            }
        else:  # pragma: no cover - caller validates the method.
            raise AssertionError(f"unhandled noncontextual method {method}")

        reward = float(action == label)
        pseudo_regret = 1.0 - reward
        pull_counts[action] += 1
        reward_sums[action] += reward
        if method == "thompson_sampling":
            posterior_alpha[action] += reward
            posterior_beta[action] += 1.0 - reward
        cumulative_regret += pseudo_regret
        cumulative_reward += reward
        round_runtime = time.perf_counter() - round_started
        cumulative_runtime += round_runtime
        peak_host_memory = max(peak_host_memory, _peak_host_memory_bytes())

        records.append(
            {
                "round": round_number,
                "method": method,
                "phase": phase,
                "environment_split": expected_split,
                "executed_policy": True,
                "execution_mode": "online_adaptive_noncontextual",
                "noncontextual_policy": True,
                "context_used_by_policy": False,
                "full_action_enumeration": True,
                "enumerated_actions": list(range(action_count)),
                "dataset_index": int(dataset_index),
                "context": context.tolist(),
                "true_label_arm": label,
                "policy_feedback": "selected_arm_reward_only",
                "action": action,
                "reward": reward,
                "pseudo_regret": pseudo_regret,
                "cumulative_pseudo_regret": cumulative_regret,
                "predicted_rewards": predictions.tolist(),
                "predictive_variances": predictive_variances.tolist(),
                "exploration_widths": widths.tolist(),
                "scores": score_values,
                "pull_counts_after": pull_counts.tolist(),
                "reward_sums_after": reward_sums.tolist(),
                "damping": 0.0,
                "bonus_scale": 0.0,
                "curvature_dimension": 0,
                "curvature_likelihood": "not_applicable",
                "observed_reward_kind": "binary_zero_one",
                "binary_reward_with_gaussian_curvature": False,
                "gaussian_theorem_certified": False,
                "gaussian_regret_theorem_certified": False,
                "cg_applies": False,
                "cg_iterations": [],
                "cg_relative_residuals": [],
                "cg_converged": [],
                "curvature_vector_products_per_action": [],
                "curvature_vector_products": 0,
                "cumulative_curvature_vector_products": 0,
                "updates_completed": 1,
                "round_runtime_seconds": round_runtime,
                "cumulative_runtime_seconds": cumulative_runtime,
                "peak_host_memory_bytes": peak_host_memory,
                "peak_host_memory_scope": "process_lifetime_high_water_mark",
                "runtime_clock": "time.perf_counter_wall_seconds",
                "test_label_used_for_hyperparameter_selection": False,
                **method_state,
            }
        )

    sequence_digest = _array_sha256(stream_indices)
    summary: dict[str, Any] = {
        "schema_version": 1,
        "event": "covertype_run_summary",
        "method": method,
        "seed": seed,
        "phase": phase,
        "environment_split": expected_split,
        "executed_policy": True,
        "execution_mode": "online_adaptive_noncontextual",
        "noncontextual_policy": True,
        "context_used_by_policy": False,
        "rounds": rounds,
        "damping": 0.0,
        "bonus_scale": 0.0,
        "cumulative_pseudo_regret": cumulative_regret,
        "mean_pseudo_regret": cumulative_regret / rounds,
        "cumulative_reward": cumulative_reward,
        "accuracy": cumulative_reward / rounds,
        "environment_seed": environment_seed,
        "policy_random_seed": policy_seed,
        "dataset_index_sequence_sha256": sequence_digest,
        "final_displacement_norm": 0.0,
        "runtime_seconds": cumulative_runtime,
        "peak_host_memory_bytes": peak_host_memory,
        "peak_host_memory_scope": "process_lifetime_high_water_mark",
        "runtime_clock": "time.perf_counter_wall_seconds",
        "curvature_vector_products": 0,
        "curvature_likelihood": "not_applicable",
        "observed_reward_kind": "binary_zero_one",
        "binary_reward_with_gaussian_curvature": False,
        "gaussian_theorem_certified": False,
        "gaussian_regret_theorem_certified": False,
        "cg_applies": False,
        "all_cg_solves_converged": True,
        "pull_counts": pull_counts.tolist(),
        "reward_sums": reward_sums.tolist(),
        "test_label_used_for_hyperparameter_selection": False,
    }
    if method == "ucb1":
        summary["hyperparameters"] = {
            "ucb_log_multiplier": 2.0,
            "forced_initial_pulls_per_arm": 1,
        }
        summary["tie_break"] = "lowest_zero_based_arm_via_numpy_argmax"
    else:
        summary["hyperparameters"] = {
            "beta_prior_alpha": 1.0,
            "beta_prior_beta": 1.0,
        }
        summary["posterior_alpha"] = posterior_alpha.tolist()
        summary["posterior_beta"] = posterior_beta.tolist()
        summary["posterior_independent_across_arms"] = True
        summary["tie_break"] = "lowest_zero_based_arm_via_numpy_argmax"

    final = np.empty(0, dtype=np.float64)
    final.setflags(write=False)
    return CovertypeRun(
        method=method,
        seed=seed,
        phase=phase,
        split=expected_split,
        damping=0.0,
        bonus_scale=0.0,
        records=tuple(records),
        summary=summary,
        final_displacement=final,
    )


def run_policy(
    config: Mapping[str, Any],
    data: PreparedCovertypeData,
    method: str,
    seed: int,
    *,
    phase: Phase = "evaluation",
    damping: float | None = None,
    bonus_scale: float | None = None,
) -> CovertypeRun:
    """Execute one online policy from a fresh seeded initialization."""

    seed = _nonnegative_int(seed, name="seed")
    if phase not in {"tuning", "evaluation"}:
        raise ValueError("phase must be 'tuning' or 'evaluation'")
    protocol = method_protocol(method)
    dataset_config = _dataset_section(config)
    expected_split = str(
        dataset_config[
            "tuning_environment_split" if phase == "tuning" else "evaluation_environment_split"
        ]
    )
    if phase == "evaluation" and expected_split != "test":
        raise ValueError("evaluation_environment_split must be 'test'")
    if phase == "tuning" and expected_split != "validation":
        raise ValueError("tuning_environment_split must be 'validation'")
    split_indices = data.indices(expected_split)
    rounds = _rounds_for_phase(config, phase)

    if method in NONCONTEXTUAL_METHODS:
        damping_value = (
            0.0
            if damping is None
            else _selection_damping(method, damping, name="damping")
        )
        bonus_value = (
            0.0
            if bonus_scale is None
            else _nonnegative_float(bonus_scale, name="bonus_scale")
        )
        if damping_value != 0.0 or bonus_value != 0.0:
            raise ValueError(f"{method} is parameter-free and requires zero sentinels")
        return _run_noncontextual_policy(
            config,
            data,
            method,
            seed,
            phase,
            expected_split,
            split_indices,
            rounds,
        )

    model_config = _model_section(config)
    hidden_width = _positive_int(model_config.get("hidden_width"), name="hidden_width")
    learning_rate = _positive_float(model_config.get("learning_rate"), name="learning_rate")
    model_ridge = _nonnegative_float(model_config.get("ridge"), name="model.ridge")
    updates = _positive_int(model_config.get("updates_per_round"), name="updates_per_round")
    if updates != 1:
        raise ValueError("this protocol implements exactly one online update per round")
    if str(model_config.get("dtype")) != "float64":
        raise ValueError("Covertype runner requires model.dtype='float64'")
    damping_value = (
        model_ridge if damping is None else _positive_float(damping, name="damping")
    )
    bonus_value = (
        (0.0 if method == "greedy_full_network" else _grid(config, "bonus_grid")[0])
        if bonus_scale is None
        else _nonnegative_float(bonus_scale, name="bonus_scale")
    )
    if method != "greedy_full_network" and bonus_value <= 0.0:
        raise ValueError("exploratory methods require a positive bonus scale")
    if method == "greedy_full_network" and bonus_value != 0.0:
        raise ValueError("greedy_full_network requires bonus_scale=0")

    cg_config = config.get("cg")
    if not isinstance(cg_config, Mapping):
        raise ValueError("config.cg must be an object")
    cg_tolerance = _positive_float(
        cg_config.get("relative_residual_tolerance"), name="cg tolerance"
    )
    cg_max_iterations = _positive_int(
        cg_config.get("max_iterations"), name="cg max_iterations"
    )
    if not bool(cg_config.get("operator_fixed_within_solve")):
        raise ValueError("CG operator must be fixed within each solve")

    initialization_seed = derive_seed(seed, "covertype", "model_initialization")
    environment_seed = derive_seed(seed, "covertype", expected_split, "environment_order")
    model, displacement = _initial_model(
        data.feature_count, data.class_count, hidden_width, initialization_seed
    )
    trained_indices = _method_indices(model, protocol)
    stream_positions = _stream_positions(len(split_indices), rounds, environment_seed)
    stream_indices = np.asarray(split_indices[stream_positions], dtype=np.int64)

    dimension = len(trained_indices)
    gram_inverse: FloatArray | None = None
    gram_diagonal: FloatArray | None = None
    if method in {"frozen_full_gram", "last_layer_full"}:
        gram_inverse = np.eye(dimension, dtype=np.float64) / damping_value
        gram_diagonal = np.full(dimension, damping_value, dtype=np.float64)
    elif method == "last_layer_diagonal":
        gram_diagonal = np.full(dimension, damping_value, dtype=np.float64)

    history_contexts: list[FloatArray] = []
    history_actions: list[int] = []
    records: list[dict[str, Any]] = []
    cumulative_regret = 0.0
    cumulative_reward = 0.0
    cumulative_runtime = 0.0
    cumulative_cvps = 0
    peak_host_memory = _peak_host_memory_bytes()

    for zero_round, dataset_index in enumerate(stream_indices):
        round_started = time.perf_counter()
        round_number = zero_round + 1
        context = np.asarray(data.features[int(dataset_index)], dtype=np.float64)
        label = int(data.labels[int(dataset_index)])
        predictions = model.means(displacement, context)
        current_jacobians = model.jacobians(displacement, context)
        width_result = _policy_widths(
            method,
            damping_value,
            model,
            displacement,
            current_jacobians,
            trained_indices,
            history_contexts,
            history_actions,
            gram_inverse,
            gram_diagonal,
            cg_tolerance=cg_tolerance,
            cg_max_iterations=cg_max_iterations,
        )
        widths = np.sqrt(np.maximum(width_result.widths_squared, 0.0))
        scores = predictions + bonus_value * widths
        action = int(np.argmax(scores))
        reward = float(action == label)
        pseudo_regret = 1.0 - reward
        cumulative_regret += pseudo_regret
        cumulative_reward += reward

        selected_full_jacobian = np.asarray(current_jacobians[action], dtype=np.float64)
        selected_trainable_jacobian = selected_full_jacobian[trained_indices]
        prediction_error = float(predictions[action] - reward)
        pre_update_regularizer = 0.5 * model_ridge * float(
            displacement[trained_indices] @ displacement[trained_indices]
        )
        gradient = prediction_error * selected_trainable_jacobian
        gradient = gradient + model_ridge * displacement[trained_indices]
        gradient_norm = float(np.linalg.norm(gradient))
        update = -learning_rate * gradient
        displacement[trained_indices] += update

        if gram_inverse is not None:
            gram_inverse = _rank_one_inverse_update(
                gram_inverse, selected_trainable_jacobian
            )
        if gram_diagonal is not None:
            gram_diagonal = gram_diagonal + selected_trainable_jacobian**2
        history_contexts.append(context.copy())
        history_actions.append(action)
        round_runtime = time.perf_counter() - round_started
        cumulative_runtime += round_runtime
        round_cvps = int(np.sum(width_result.curvature_vector_products))
        cumulative_cvps += round_cvps
        peak_host_memory = max(peak_host_memory, _peak_host_memory_bytes())

        records.append(
            {
                "round": round_number,
                "method": method,
                "phase": phase,
                "environment_split": expected_split,
                "executed_policy": True,
                "full_action_enumeration": True,
                "enumerated_actions": list(range(data.class_count)),
                "dataset_index": int(dataset_index),
                "context": context.tolist(),
                "true_label_arm": label,
                "policy_feedback": "selected_arm_reward_only",
                "action": action,
                "reward": reward,
                "pseudo_regret": pseudo_regret,
                "cumulative_pseudo_regret": cumulative_regret,
                "predicted_rewards": predictions.tolist(),
                "predictive_variances": width_result.widths_squared.tolist(),
                "exploration_widths": widths.tolist(),
                "scores": scores.tolist(),
                "damping": damping_value,
                "bonus_scale": bonus_value,
                "model_ridge": model_ridge,
                "curvature_dimension": dimension,
                "curvature_trace_diagnostic": width_result.curvature_trace,
                "curvature_likelihood": "unit_variance_gaussian_squared_loss",
                "observed_reward_kind": "binary_zero_one",
                "binary_reward_with_gaussian_curvature": True,
                "gaussian_theorem_certified": False,
                "gaussian_regret_theorem_certified": False,
                "cg_iterations": width_result.cg_iterations.tolist(),
                "cg_relative_residuals": width_result.cg_relative_residuals.tolist(),
                "cg_converged": list(width_result.cg_converged),
                "curvature_vector_products_per_action": (
                    width_result.curvature_vector_products.tolist()
                ),
                "cg_operator_fixed_within_solve": True,
                "pre_update_selected_prediction": float(predictions[action]),
                "squared_loss": 0.5 * prediction_error * prediction_error,
                "regularizer": pre_update_regularizer,
                "update_gradient_norm": gradient_norm,
                "update_norm": float(np.linalg.norm(update)),
                "updates_completed": 1,
                "round_runtime_seconds": round_runtime,
                "cumulative_runtime_seconds": cumulative_runtime,
                "peak_host_memory_bytes": peak_host_memory,
                "peak_host_memory_scope": "process_lifetime_high_water_mark",
                "runtime_clock": "time.perf_counter_wall_seconds",
                "curvature_vector_products": round_cvps,
                "cumulative_curvature_vector_products": cumulative_cvps,
                "test_label_used_for_hyperparameter_selection": False,
            }
        )

    sequence_digest = _array_sha256(stream_indices)
    summary = {
        "schema_version": 1,
        "event": "covertype_run_summary",
        "method": method,
        "seed": seed,
        "phase": phase,
        "environment_split": expected_split,
        "executed_policy": True,
        "rounds": rounds,
        "damping": damping_value,
        "bonus_scale": bonus_value,
        "model_ridge": model_ridge,
        "cumulative_pseudo_regret": cumulative_regret,
        "mean_pseudo_regret": cumulative_regret / rounds,
        "cumulative_reward": cumulative_reward,
        "accuracy": cumulative_reward / rounds,
        "initialization_seed": initialization_seed,
        "environment_seed": environment_seed,
        "dataset_index_sequence_sha256": sequence_digest,
        "final_displacement_norm": float(np.linalg.norm(displacement)),
        "runtime_seconds": cumulative_runtime,
        "peak_host_memory_bytes": peak_host_memory,
        "peak_host_memory_scope": "process_lifetime_high_water_mark",
        "runtime_clock": "time.perf_counter_wall_seconds",
        "curvature_vector_products": cumulative_cvps,
        "curvature_likelihood": "unit_variance_gaussian_squared_loss",
        "observed_reward_kind": "binary_zero_one",
        "binary_reward_with_gaussian_curvature": True,
        "gaussian_theorem_certified": False,
        "gaussian_regret_theorem_certified": False,
        "test_label_used_for_hyperparameter_selection": False,
        "all_cg_solves_converged": all(
            all(bool(value) for value in record["cg_converged"]) for record in records
        ),
    }
    final = np.asarray(displacement, dtype=np.float64).copy()
    final.setflags(write=False)
    return CovertypeRun(
        method=method,
        seed=seed,
        phase=phase,
        split=expected_split,
        damping=damping_value,
        bonus_scale=bonus_value,
        records=tuple(records),
        summary=summary,
        final_displacement=final,
    )


run_method = run_policy


def _method_manifest(
    config: Mapping[str, Any],
    data: PreparedCovertypeData,
    run: CovertypeRun,
    split_protocol: Mapping[str, Any],
    selection_authorization: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    protocol = method_protocol(run.method)
    manifest = copy.deepcopy(dict(config))
    manifest["configured_phase_rounds"] = {
        "tuning": _rounds_for_phase(config, "tuning"),
        "evaluation": _rounds_for_phase(config, "evaluation"),
    }
    # Aggregation validates this field against the actual raw trajectory.
    manifest["rounds"] = int(run.summary["rounds"])
    if run.method in NONCONTEXTUAL_METHODS:
        policy_parameters = copy.deepcopy(dict(run.summary["hyperparameters"]))
        manifest["execution"] = {
            "driver": "experiments.run_covertype",
            "phase": run.phase,
            "seed_set": run.phase,
            "seed": run.seed,
            "method": run.method,
            "mode": "online_adaptive_noncontextual",
            "executed_policy": True,
            "full_action_enumeration": True,
            "environment_split": run.split,
            "dataset": {
                "provenance": copy.deepcopy(data.provenance),
                "split_protocol": copy.deepcopy(split_protocol),
                "preprocessing": copy.deepcopy(data.preprocessing),
            },
            "policy": {
                "task": "classes_as_arms",
                "family": run.method,
                "actions": list(range(data.class_count)),
                "reward": "one_if_selected_arm_matches_label_else_zero",
                "feedback_to_optimizer": "selected_arm_reward_only",
                "context_used": False,
                "tie_break": "lowest_zero_based_arm_via_numpy_argmax",
                "parameters": policy_parameters,
                "posterior_independent_across_arms": (
                    True if run.method == "thompson_sampling" else None
                ),
            },
            "architecture": {
                "kind": "none_noncontextual_bandit",
                "input_features_observed_but_ignored": data.feature_count,
                "output_arms": data.class_count,
                "parameter_count": 0,
                "dtype": "float64",
            },
            "layers_trained": [],
            "trained_parameter_set": protocol.trained_parameter_set,
            "initialization": {
                "kind": (
                    "one_forced_pull_per_arm"
                    if run.method == "ucb1"
                    else "independent_beta_1_1_prior_per_arm"
                ),
                "policy_random_seed": run.summary["policy_random_seed"],
            },
            "optimizer": {
                "name": "per_arm_bernoulli_sufficient_statistic_update",
                "updates_per_round": 1,
                "uses_unselected_labels": False,
                "uses_context": False,
            },
            "curvature": {
                "applies": False,
                "parameter_set": "none",
                "representation": "none",
                "likelihood_for_curvature": "not_applicable",
                "observed_reward_distribution": "binary_zero_one",
                "binary_reward_with_gaussian_curvature": False,
                "gaussian_theorem_certified": False,
                "gaussian_regret_theorem_certified": False,
            },
            "hyperparameter_grids": {
                "parameter_free": True,
                "selected_damping_sentinel": 0.0,
                "selected_bonus_sentinel": 0.0,
            },
            "hyperparameters": policy_parameters,
            "solver": {"name": protocol.inverse_solver, "cg_applies": False},
            "randomness": {
                "master_seed": run.seed,
                "environment_seed": int(run.summary["environment_seed"]),
                "environment_sequence_sha256": run.summary[
                    "dataset_index_sequence_sha256"
                ],
                "policy_random_seed": run.summary["policy_random_seed"],
                "environment_common_random_numbers_within_seed": True,
            },
            "selection": {
                "criterion": "mean_cumulative_pseudo_regret",
                "hyperparameters_selected_on": "tuning_seeds_only",
                "parameter_free_policy": True,
                "selection_environment_split": "validation",
                "evaluation_rerun_from_scratch": True,
                "test_label_used_for_hyperparameter_selection": False,
                "authorization": (
                    None
                    if selection_authorization is None
                    else copy.deepcopy(dict(selection_authorization))
                ),
            },
        }
        return manifest

    model_config = _model_section(config)
    hidden_width = int(model_config["hidden_width"])
    layout = MLPLayout(data.feature_count, hidden_width, data.class_count)
    layers_trained = (
        ["output_weights", "output_bias"]
        if protocol.trained_parameter_set == "output_weight_and_bias"
        else ["input_weights", "hidden_bias", "output_weights", "output_bias"]
    )
    manifest["execution"] = {
        "driver": "experiments.run_covertype",
        "phase": run.phase,
        "seed_set": run.phase,
        "seed": run.seed,
        "method": run.method,
        "executed_policy": True,
        "full_action_enumeration": True,
        "environment_split": run.split,
        "dataset": {
            "provenance": copy.deepcopy(data.provenance),
            "split_protocol": copy.deepcopy(split_protocol),
            "preprocessing": copy.deepcopy(data.preprocessing),
        },
        "policy": {
            "task": "classes_as_arms",
            "actions": list(range(data.class_count)),
            "reward": "one_if_selected_arm_matches_label_else_zero",
            "feedback_to_optimizer": "selected_arm_reward_only",
            "tie_break": "lowest_zero_based_arm_via_numpy_argmax",
        },
        "architecture": {
            "kind": "one_hidden_layer_tanh",
            "input_features": data.feature_count,
            "hidden_width": hidden_width,
            "output_arms": data.class_count,
            "parameter_count": layout.parameter_dimension,
            "backbone_parameter_count": layout.backbone_dimension,
            "head_parameter_count": layout.head_dimension,
            "parameter_order": [
                "input_weights_row_major",
                "hidden_bias",
                "output_weights_row_major",
                "output_bias",
            ],
            "dtype": "float64",
        },
        "layers_trained": layers_trained,
        "trained_parameter_set": protocol.trained_parameter_set,
        "initialization": {
            "seed": int(run.summary["initialization_seed"]),
            "input_weights": "normal_mean_0_std_1_over_sqrt_input_fan_in",
            "hidden_bias": "zeros",
            "output_weights": "normal_mean_0_std_1_over_sqrt_hidden_fan_in",
            "output_bias": "zeros",
            "regularization_center": "initial_parameters",
        },
        "optimizer": {
            "name": "online_sgd",
            "learning_rate": float(model_config["learning_rate"]),
            "updates_per_round": int(model_config["updates_per_round"]),
            "update_schedule": "select_then_reveal_selected_reward_then_one_current_sample_update",
            "loss": (
                "half_squared_selected_arm_error_plus_half_model_ridge_"
                "displacement_norm_squared"
            ),
            "model_ridge": float(model_config["ridge"]),
            "uses_unselected_labels": False,
        },
        "curvature": {
            "parameter_set": protocol.curvature_parameter_set,
            "representation": protocol.curvature_representation,
            "historical_linearization": protocol.historical_linearization,
            "query_linearization": "current_pre_update_parameters",
            "damping": run.damping,
            "ggn_output_hessian_weight": 1.0,
            "likelihood_for_curvature": "gaussian_squared_loss",
            "observed_reward_distribution": "binary_zero_one",
            "binary_reward_with_gaussian_curvature": True,
            "gaussian_theorem_certified": False,
            "gaussian_regret_theorem_certified": False,
            "certification_note": (
                "binary reward with Gaussian curvature; "
                "no Gaussian theorem certification"
            ),
        },
        "hyperparameter_grids": {
            "damping": list(_grid(config, "damping_grid")),
            "bonus": list(_grid(config, "bonus_grid")),
            "selected_damping": run.damping,
            "selected_bonus": run.bonus_scale,
        },
        "solver": {
            "name": protocol.inverse_solver,
            "relative_residual_tolerance": float(config["cg"]["relative_residual_tolerance"]),
            "max_iterations": int(config["cg"]["max_iterations"]),
            "operator_fixed_within_solve": bool(config["cg"]["operator_fixed_within_solve"]),
            "initial_solution": "zero",
            "preconditioner": "none",
            "cg_settings_apply_to": "full_network_ggn_cg_only",
            "on_nonconvergence": (
                "use_logged_final_iterate_without_theorem_certification"
            ),
        },
        "randomness": {
            "master_seed": run.seed,
            "initialization_seed": int(run.summary["initialization_seed"]),
            "environment_seed": int(run.summary["environment_seed"]),
            "environment_sequence_sha256": run.summary["dataset_index_sequence_sha256"],
            "common_random_numbers_within_seed": True,
        },
        "selection": {
            "criterion": "mean_cumulative_pseudo_regret",
            "hyperparameters_selected_on": "tuning_seeds_only",
            "selection_environment_split": "validation",
            "evaluation_rerun_from_scratch": True,
            "test_label_used_for_hyperparameter_selection": False,
            "authorization": (
                None
                if selection_authorization is None
                else copy.deepcopy(dict(selection_authorization))
            ),
        },
    }
    return manifest


def _split_artifacts(data: PreparedCovertypeData, directory: Path) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    result = copy.deepcopy(dict(data.split_protocol))
    partitions = result["partitions"]
    for name, indices in data.split_indices.items():
        destination = directory / f"{name}_indices.npy"
        if destination.exists():
            existing = np.load(destination, allow_pickle=False)
            if not np.array_equal(existing, indices):
                raise FileExistsError(f"existing split artifact disagrees: {destination}")
        else:
            with destination.open("wb") as stream:
                np.save(stream, np.asarray(indices, dtype=np.int64), allow_pickle=False)
        partitions[name]["indices_artifact"] = str(destination.resolve())
        partitions[name]["indices_artifact_sha256"] = _file_sha256(destination)
    return result


def build_test_class_diagnostics(
    config: Mapping[str, Any],
    data: PreparedCovertypeData,
    *,
    split_protocol: Mapping[str, Any] | None = None,
    clock: Callable[[], dt.datetime | str] = _utc_now,
) -> dict[str, Any]:
    """Build label-count baselines that are never represented as policy runs."""

    protocol = copy.deepcopy(
        dict(data.split_protocol if split_protocol is None else split_protocol)
    )
    test_indices = data.indices("test")
    test_labels = np.asarray(data.labels[test_indices], dtype=np.int64)
    counts = np.bincount(test_labels, minlength=data.class_count).astype(np.int64)
    if counts.shape != (data.class_count,) or int(np.sum(counts)) != len(test_indices):
        raise AssertionError("test class counts do not cover the exact test split")
    total = int(len(test_indices))
    fractions = counts.astype(np.float64) / float(total)
    majority_arm = int(np.argmax(counts))
    majority_accuracy = float(fractions[majority_arm])
    uniform_accuracy = 1.0 / float(data.class_count)
    raw_horizons = config.get("horizons", ())
    evaluation_rounds = _rounds_for_phase(config, "evaluation")
    horizons = {evaluation_rounds}
    if isinstance(raw_horizons, Sequence) and not isinstance(
        raw_horizons, (str, bytes)
    ):
        horizons.update(
            int(value)
            for value in raw_horizons
            if isinstance(value, int)
            and not isinstance(value, bool)
            and 0 < value <= evaluation_rounds
        )

    input_records: list[dict[str, str]] = []
    for item in data.provenance.get("dataset_files", []):
        if isinstance(item, Mapping) and isinstance(item.get("path"), str):
            input_records.append(
                {"path": str(item["path"]), "sha256": str(item["sha256"])}
            )
    test_partition = protocol["partitions"]["test"]
    indices_artifact = test_partition.get("indices_artifact")
    indices_artifact_sha256 = test_partition.get("indices_artifact_sha256")
    if isinstance(indices_artifact, str) and isinstance(indices_artifact_sha256, str):
        input_records.append(
            {"path": indices_artifact, "sha256": indices_artifact_sha256}
        )
    inputs = sorted(input_records, key=lambda item: item["path"])
    input_set_sha256 = hashlib.sha256(
        canonical_json(inputs).encode("ascii")
    ).hexdigest()
    label_base = int(data.preprocessing["label_source_base"])

    return {
        "schema_version": 1,
        "event": "covertype_test_class_count_diagnostics",
        "created_at_utc": _timestamp(clock()),
        "experiment": str(config.get("name", "covertype_rerun")),
        "profile": str(config.get("profile", "default")),
        "resolved_config_digest": config_digest(config),
        "executed_policy": False,
        "included_in_executed_policy_aggregate": False,
        "environment_split": "test",
        "uses_whole_test_split_labels": True,
        "dataset_checksum_sha256": data.dataset_sha256,
        "dataset_provenance": copy.deepcopy(data.provenance),
        "split_seed": int(protocol["seed"]),
        "test_indices_sha256": str(test_partition["indices_sha256"]),
        "test_indices_artifact": indices_artifact,
        "test_indices_artifact_sha256": indices_artifact_sha256,
        "test_sample_count": total,
        "class_count": data.class_count,
        "class_counts_by_arm": {str(arm): int(counts[arm]) for arm in range(data.class_count)},
        "classes": [
            {
                "arm": arm,
                "source_label": arm + label_base,
                "count": int(counts[arm]),
                "fraction": float(fractions[arm]),
            }
            for arm in range(data.class_count)
        ],
        "diagnostics": {
            "uniform_random": {
                "kind": "analytic_expectation",
                "executed_policy": False,
                "deployable": True,
                "uses_test_labels_to_choose_actions": False,
                "expected_accuracy": uniform_accuracy,
                "expected_mean_pseudo_regret": 1.0 - uniform_accuracy,
                "horizons": [
                    {
                        "horizon": horizon,
                        "expected_cumulative_reward": horizon * uniform_accuracy,
                        "expected_cumulative_pseudo_regret": horizon
                        * (1.0 - uniform_accuracy),
                    }
                    for horizon in sorted(horizons)
                ],
            },
            "fixed_test_split_majority_arm_oracle": {
                "kind": "whole_test_split_label_oracle_diagnostic",
                "executed_policy": False,
                "deployable": False,
                "oracle_diagnostic_only": True,
                "causal_regret_claim": False,
                "uses_test_labels_to_choose_actions": True,
                "fixed_arm": majority_arm,
                "fixed_source_label": majority_arm + label_base,
                "accuracy": majority_accuracy,
                "mean_pseudo_regret": 1.0 - majority_accuracy,
                "horizons": [
                    {
                        "horizon": horizon,
                        "expected_cumulative_reward_at_full_split_rate": horizon
                        * majority_accuracy,
                        "expected_cumulative_pseudo_regret_at_full_split_rate": horizon
                        * (1.0 - majority_accuracy),
                    }
                    for horizon in sorted(horizons)
                ],
            },
        },
        "inputs": inputs,
        "input_set_sha256": input_set_sha256,
    }


def write_test_class_diagnostics(
    artifact: Mapping[str, Any],
    path: str | Path,
    *,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    """Write the diagnostic and a digest sidecar over its exact raw inputs."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    inputs = artifact.get("inputs")
    if not isinstance(inputs, Sequence) or isinstance(inputs, (str, bytes)):
        raise ValueError("diagnostic inputs must be a sequence")
    normalized_inputs = [
        {"path": str(item["path"]), "sha256": str(item["sha256"])}
        for item in inputs
        if isinstance(item, Mapping)
    ]
    if len(normalized_inputs) != len(inputs):
        raise ValueError("diagnostic input records are malformed")
    normalized_inputs.sort(key=lambda item: item["path"])
    expected_input_digest = hashlib.sha256(
        canonical_json(normalized_inputs).encode("ascii")
    ).hexdigest()
    if artifact.get("input_set_sha256") != expected_input_digest:
        raise ValueError("diagnostic input inventory digest mismatch")
    for item in normalized_inputs:
        input_path = Path(item["path"])
        if not input_path.is_file() or _file_sha256(input_path) != item["sha256"]:
            raise ValueError(f"diagnostic input is unavailable or changed: {input_path}")

    payload = json.dumps(
        artifact, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False
    ) + "\n"
    flags = os.O_CREAT | os.O_WRONLY | (os.O_TRUNC if overwrite else os.O_EXCL)
    descriptor = os.open(destination, flags, 0o644)
    try:
        view = memoryview(payload.encode("utf-8"))
        while view:
            written = os.write(descriptor, view)
            if written == 0:
                raise OSError(f"zero-byte write while writing {destination}")
            view = view[written:]
    finally:
        os.close(descriptor)
    sidecar = destination.with_suffix(destination.suffix + ".provenance.json")
    sidecar_record = {
        "schema_version": 1,
        "artifact": str(destination),
        "artifact_sha256": _file_sha256(destination),
        "input_set_sha256": expected_input_digest,
        "inputs": normalized_inputs,
    }
    sidecar_payload = json.dumps(
        sidecar_record, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False
    ) + "\n"
    sidecar_flags = os.O_CREAT | os.O_WRONLY | (
        os.O_TRUNC if overwrite else os.O_EXCL
    )
    descriptor = os.open(sidecar, sidecar_flags, 0o644)
    try:
        view = memoryview(sidecar_payload.encode("utf-8"))
        while view:
            written = os.write(descriptor, view)
            if written == 0:
                raise OSError(f"zero-byte write while writing {sidecar}")
            view = view[written:]
    finally:
        os.close(descriptor)
    return destination, sidecar


def _format_grid_value(value: float) -> str:
    return format(value, ".12g").replace("-", "m").replace("+", "p").replace(".", "d")


def save_run(
    run: CovertypeRun,
    output_root: str | Path,
    config: Mapping[str, Any],
    data: PreparedCovertypeData,
    *,
    split_protocol: Mapping[str, Any] | None = None,
    selection_authorization: Mapping[str, Any] | None = None,
    overwrite: bool = False,
) -> Path:
    root = Path(output_root)
    profile = str(config.get("profile", "default"))
    destination = (
        root
        / profile
        / run.phase
        / run.method
        / f"damping-{_format_grid_value(run.damping)}_bonus-{_format_grid_value(run.bonus_scale)}"
        / f"seed-{run.seed}"
    )
    protocol = (
        _split_artifacts(data, root / profile / "dataset_splits")
        if split_protocol is None
        else split_protocol
    )
    manifest = _method_manifest(
        config,
        data,
        run,
        protocol,
        selection_authorization=selection_authorization,
    )
    with ExperimentLogger(
        destination,
        manifest,
        run.seed,
        repository=REPOSITORY_ROOT,
        overwrite=overwrite,
    ) as logger:
        for zero_round, record in enumerate(run.records):
            logger.log_round(zero_round, record)
    summary_path = destination / "summary.jsonl"
    if overwrite and summary_path.exists():
        summary_path.unlink()
    saved_summary = dict(run.summary)
    if selection_authorization is not None:
        saved_summary["tuning_selection_canonical_json_sha256"] = str(
            selection_authorization["canonical_json_sha256"]
        )
        saved_summary["tuning_selection_artifact_path"] = selection_authorization[
            "artifact_path"
        ]
        saved_summary["tuning_selection_artifact_file_sha256"] = (
            selection_authorization["artifact_file_sha256"]
        )
        saved_summary["tuning_selection_validation_evidence_sha256"] = str(
            selection_authorization["validation_evidence_sha256"]
        )
        saved_summary["tuning_selection_validation_status"] = (
            selection_authorization["validation"]["status"]
        )
    append_jsonl(summary_path, saved_summary)
    return destination


def _selection_key(run: CovertypeRun) -> tuple[str, float, float]:
    return run.method, run.damping, run.bonus_scale


def build_tuning_selection(
    config: Mapping[str, Any],
    data: PreparedCovertypeData,
    runs: Sequence[CovertypeRun],
    *,
    clock: Callable[[], dt.datetime | str] = _utc_now,
) -> dict[str, Any]:
    if not runs or any(
        run.phase != "tuning" or run.split != "validation" for run in runs
    ):
        raise ValueError("selection requires nonempty validation tuning runs only")
    if str(_dataset_section(config).get("tuning_environment_split")) != "validation":
        raise ValueError("selection protocol requires the validation split")
    tuning_seeds = tuple(int(seed) for seed in get_seed_set(config, "tuning"))
    expected_methods = configured_methods(config)
    grouped: dict[tuple[str, float, float], list[CovertypeRun]] = {}
    for run in runs:
        grouped.setdefault(_selection_key(run), []).append(run)

    selected: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for method in expected_methods:
        method_candidates: list[tuple[float, int, CovertypeRun, list[CovertypeRun]]] = []
        for grid_order, (damping, bonus) in enumerate(hyperparameter_grid(config, method)):
            matching = grouped.get((method, damping, bonus), [])
            seeds = tuple(sorted(run.seed for run in matching))
            if seeds != tuple(sorted(tuning_seeds)):
                raise ValueError(
                    f"incomplete tuning grid for {method}, damping={damping}, bonus={bonus}"
                )
            mean_regret = float(
                np.mean([run.summary["cumulative_pseudo_regret"] for run in matching])
            )
            candidate = {
                "method": method,
                "damping": damping,
                "bonus_scale": bonus,
                "mean_cumulative_pseudo_regret": mean_regret,
                "per_seed_cumulative_pseudo_regret": {
                    str(run.seed): float(run.summary["cumulative_pseudo_regret"])
                    for run in sorted(matching, key=lambda item: item.seed)
                },
                "grid_order": grid_order,
            }
            candidates.append(candidate)
            method_candidates.append((mean_regret, grid_order, matching[0], matching))
        mean_regret, grid_order, representative, matching = min(
            method_candidates, key=lambda value: (value[0], value[1])
        )
        selected.append(
            {
                "method": method,
                "damping": representative.damping,
                "bonus_scale": representative.bonus_scale,
                "mean_tuning_cumulative_pseudo_regret": mean_regret,
                "tie_break_grid_order": grid_order,
            }
        )

    return {
        "schema_version": 1,
        "event": "covertype_tuning_selection",
        "created_at_utc": _timestamp(clock()),
        "experiment": str(config.get("name", "covertype_rerun")),
        "profile": str(config.get("profile", "default")),
        "resolved_config_digest": config_digest(config),
        "criterion": "mean_cumulative_pseudo_regret",
        "selected_on_seed_set": "tuning",
        "selected_on_environment_split": "validation",
        "tuning_rounds": _rounds_for_phase(config, "tuning"),
        "evaluation_rounds": _rounds_for_phase(config, "evaluation"),
        "tuning_seeds": list(tuning_seeds),
        "evaluation_seeds": list(get_seed_set(config, "evaluation")),
        "dataset_checksum_sha256": data.dataset_sha256,
        "split_seed": int(data.split_protocol["seed"]),
        "validation_indices_sha256": data.split_protocol["partitions"]["validation"][
            "indices_sha256"
        ],
        "evaluation_labels_used": False,
        "test_label_used_for_hyperparameter_selection": False,
        "evaluation_policies_must_rerun_from_scratch": True,
        "tie_break": "lowest_configured_grid_order",
        "candidates": candidates,
        "selected": selected,
    }


def write_tuning_selection(
    artifact: Mapping[str, Any], path: str | Path, *, overwrite: bool = False
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_WRONLY | (os.O_TRUNC if overwrite else os.O_EXCL)
    descriptor = os.open(destination, flags, 0o644)
    try:
        payload = (canonical_json(artifact) + "\n").encode("utf-8")
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written == 0:
                raise OSError(f"zero-byte write while writing {destination}")
            view = view[written:]
    finally:
        os.close(descriptor)
    return destination


def load_tuning_selection(path: str | Path) -> dict[str, Any]:
    destination = Path(path)
    try:
        artifact = json.loads(destination.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load tuning selection {destination}: {exc}") from exc
    if not isinstance(artifact, dict):
        raise ValueError("tuning selection artifact must contain one JSON object")
    return artifact


def _validate_selection(
    config: Mapping[str, Any],
    data: PreparedCovertypeData,
    artifact: Mapping[str, Any],
) -> dict[str, tuple[float, float]]:
    if artifact.get("event") != "covertype_tuning_selection":
        raise ValueError("not a Covertype tuning-selection artifact")
    if artifact.get("schema_version") != 1:
        raise ValueError("unsupported tuning-selection schema")
    if artifact.get("criterion") != "mean_cumulative_pseudo_regret":
        raise ValueError("selection artifact criterion mismatch")
    if artifact.get("tie_break") != "lowest_configured_grid_order":
        raise ValueError("selection artifact tie-break mismatch")
    if artifact.get("experiment") != str(config.get("name", "covertype_rerun")):
        raise ValueError("selection artifact experiment mismatch")
    if artifact.get("selected_on_seed_set") != "tuning":
        raise ValueError("evaluation selection was not produced on tuning seeds")
    if artifact.get("selected_on_environment_split") != "validation":
        raise ValueError("evaluation selection must use validation, never test labels")
    if artifact.get("tuning_rounds") != _rounds_for_phase(config, "tuning"):
        raise ValueError("selection artifact tuning horizon mismatch")
    if artifact.get("evaluation_rounds") != _rounds_for_phase(config, "evaluation"):
        raise ValueError("selection artifact evaluation horizon mismatch")
    if artifact.get("evaluation_labels_used") is not False:
        raise ValueError("selection artifact must assert evaluation_labels_used=false")
    if artifact.get("test_label_used_for_hyperparameter_selection") is not False:
        raise ValueError("selection artifact used test labels")
    if artifact.get("evaluation_policies_must_rerun_from_scratch") is not True:
        raise ValueError("selection artifact does not require fresh evaluation runs")
    if artifact.get("resolved_config_digest") != config_digest(config):
        raise ValueError("selection artifact was produced from a different resolved config")
    if artifact.get("profile") != str(config.get("profile", "default")):
        raise ValueError("selection artifact profile mismatch")
    if artifact.get("tuning_seeds") != list(get_seed_set(config, "tuning")):
        raise ValueError("selection artifact tuning seed mismatch")
    if artifact.get("evaluation_seeds") != list(get_seed_set(config, "evaluation")):
        raise ValueError("selection artifact evaluation seed mismatch")
    if artifact.get("dataset_checksum_sha256") != data.dataset_sha256:
        raise ValueError("selection artifact dataset checksum mismatch")
    if artifact.get("split_seed") != int(data.split_protocol["seed"]):
        raise ValueError("selection artifact split seed mismatch")
    if artifact.get("validation_indices_sha256") != data.split_protocol["partitions"][
        "validation"
    ]["indices_sha256"]:
        raise ValueError("selection artifact split mismatch")

    methods = configured_methods(config)
    tuning_seeds = tuple(int(seed) for seed in get_seed_set(config, "tuning"))
    expected_seed_keys = {str(seed) for seed in tuning_seeds}
    raw_candidates = artifact.get("candidates")
    if not isinstance(raw_candidates, Sequence) or isinstance(
        raw_candidates, (str, bytes)
    ):
        raise ValueError("selection artifact candidates must be a sequence")
    candidates: dict[tuple[str, float, float], tuple[float, int]] = {}
    for item in raw_candidates:
        if not isinstance(item, Mapping):
            raise ValueError("selection candidates must be objects")
        method = str(item.get("method"))
        grid = hyperparameter_grid(config, method)
        damping = _selection_damping(
            method, item.get("damping"), name="candidate damping"
        )
        bonus = _nonnegative_float(item.get("bonus_scale"), name="candidate bonus")
        try:
            expected_order = grid.index((damping, bonus))
        except ValueError as exc:
            raise ValueError(f"candidate setting for {method} is outside the grid") from exc
        grid_order = _nonnegative_int(item.get("grid_order"), name="candidate grid_order")
        if grid_order != expected_order:
            raise ValueError(f"candidate grid order mismatch for {method}")
        key = (method, damping, bonus)
        if key in candidates:
            raise ValueError(f"duplicate tuning candidate for {method}")
        per_seed = item.get("per_seed_cumulative_pseudo_regret")
        if not isinstance(per_seed, Mapping) or set(per_seed) != expected_seed_keys:
            raise ValueError(f"candidate seed coverage mismatch for {method}")
        regrets = [
            _nonnegative_float(per_seed[str(seed)], name="candidate seed regret")
            for seed in tuning_seeds
        ]
        if any(value > _rounds_for_phase(config, "tuning") for value in regrets):
            raise ValueError("candidate pseudo-regret exceeds the configured horizon")
        recomputed_mean = float(np.mean(regrets, dtype=np.float64))
        stated_mean = _nonnegative_float(
            item.get("mean_cumulative_pseudo_regret"), name="candidate mean regret"
        )
        if not math.isclose(
            stated_mean, recomputed_mean, rel_tol=0.0, abs_tol=1e-12
        ):
            raise ValueError(f"candidate mean does not match per-seed regrets for {method}")
        candidates[key] = (recomputed_mean, grid_order)

    expected_keys = {
        (method, damping, bonus)
        for method in methods
        for damping, bonus in hyperparameter_grid(config, method)
    }
    if set(candidates) != expected_keys:
        raise ValueError("selection artifact does not contain the complete tuning grid")

    winners: dict[str, tuple[float, float, float, int]] = {}
    for method in methods:
        method_rows = [
            (mean, order, damping, bonus)
            for (candidate_method, damping, bonus), (mean, order) in candidates.items()
            if candidate_method == method
        ]
        mean, order, damping, bonus = min(method_rows, key=lambda row: (row[0], row[1]))
        winners[method] = (damping, bonus, mean, order)

    raw_selected = artifact.get("selected")
    if not isinstance(raw_selected, Sequence) or isinstance(raw_selected, (str, bytes)):
        raise ValueError("selection artifact selected field must be a sequence")
    selected_rows: dict[str, tuple[float, float, float, int]] = {}
    for item in raw_selected:
        if not isinstance(item, Mapping):
            raise ValueError("selected settings must be objects")
        method = str(item.get("method"))
        if method in selected_rows:
            raise ValueError(f"duplicate selection for {method}")
        damping = _selection_damping(
            method, item.get("damping"), name="selected damping"
        )
        bonus = _nonnegative_float(item.get("bonus_scale"), name="selected bonus")
        mean = _nonnegative_float(
            item.get("mean_tuning_cumulative_pseudo_regret"),
            name="selected mean regret",
        )
        order = _nonnegative_int(
            item.get("tie_break_grid_order"), name="selected grid order"
        )
        selected_rows[method] = (damping, bonus, mean, order)
    if set(selected_rows) != set(methods):
        raise ValueError("selection artifact does not select every configured method")
    for method in methods:
        selected = selected_rows[method]
        winner = winners[method]
        if selected[:2] != winner[:2] or selected[3] != winner[3] or not math.isclose(
            selected[2], winner[2], rel_tol=0.0, abs_tol=1e-12
        ):
            raise ValueError(f"selected setting for {method} is not the tuning argmin")
    return {method: selected_rows[method][:2] for method in methods}


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def _selection_validation_evidence(artifact: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "schema_version",
        "event",
        "experiment",
        "profile",
        "resolved_config_digest",
        "criterion",
        "selected_on_seed_set",
        "selected_on_environment_split",
        "tuning_rounds",
        "evaluation_rounds",
        "tuning_seeds",
        "dataset_checksum_sha256",
        "split_seed",
        "validation_indices_sha256",
        "evaluation_labels_used",
        "test_label_used_for_hyperparameter_selection",
        "tie_break",
        "candidates",
        "selected",
    )
    missing = [key for key in keys if key not in artifact]
    if missing:
        raise ValueError(f"selection artifact lacks validation evidence: {missing}")
    return {key: copy.deepcopy(artifact[key]) for key in keys}


def _selection_authorization(
    artifact: Mapping[str, Any],
    path: Path | None,
    validated_selected: Mapping[str, tuple[float, float]],
) -> dict[str, Any]:
    evidence = _selection_validation_evidence(artifact)
    selected_record = [
        {
            "method": method,
            "damping": setting[0],
            "bonus_scale": setting[1],
        }
        for method, setting in validated_selected.items()
    ]
    return {
        "hash_algorithm": "sha256",
        "canonicalization": "sorted_strict_canonical_json_without_trailing_newline",
        "canonical_json_sha256": _canonical_sha256(artifact),
        "validation_evidence_sha256": _canonical_sha256(evidence),
        "artifact_path": None if path is None else str(path.resolve()),
        "artifact_file_sha256": (
            None if path is None or not path.exists() else _file_sha256(path)
        ),
        "validation": {
            "status": "passed",
            "validator": "complete_grid_per_seed_mean_and_argmin_v1",
            "complete_grid_recomputed": True,
            "per_seed_means_recomputed": True,
            "tie_break_recomputed": True,
            "test_labels_used": False,
            "candidate_count": len(artifact["candidates"]),
            "validated_selected": selected_record,
        },
        "validation_evidence": evidence,
        "artifact": copy.deepcopy(dict(artifact)),
    }


def verify_selection_authorization(
    config: Mapping[str, Any],
    data: PreparedCovertypeData,
    authorization: Mapping[str, Any],
    *,
    require_current_file: bool = False,
) -> dict[str, tuple[float, float]]:
    """Verify an evaluation manifest's exact tuning-artifact commitment."""

    if authorization.get("hash_algorithm") != "sha256":
        raise ValueError("selection authorization hash algorithm mismatch")
    artifact = authorization.get("artifact")
    evidence = authorization.get("validation_evidence")
    validation = authorization.get("validation")
    if not isinstance(artifact, Mapping) or not isinstance(evidence, Mapping):
        raise ValueError("selection authorization lacks embedded evidence")
    if not isinstance(validation, Mapping) or validation.get("status") != "passed":
        raise ValueError("selection authorization lacks a passing validation record")

    artifact_digest = _canonical_sha256(artifact)
    expected_artifact_digest = authorization.get("canonical_json_sha256")
    if not isinstance(expected_artifact_digest, str) or not hmac.compare_digest(
        artifact_digest, expected_artifact_digest
    ):
        raise ValueError("embedded tuning-selection artifact hash mismatch")
    recomputed_evidence = _selection_validation_evidence(artifact)
    if canonical_json(evidence) != canonical_json(recomputed_evidence):
        raise ValueError("embedded validation evidence does not match the artifact")
    evidence_digest = _canonical_sha256(recomputed_evidence)
    expected_evidence_digest = authorization.get("validation_evidence_sha256")
    if not isinstance(expected_evidence_digest, str) or not hmac.compare_digest(
        evidence_digest, expected_evidence_digest
    ):
        raise ValueError("selection validation-evidence hash mismatch")

    selected = _validate_selection(config, data, artifact)
    expected_selected = [
        {
            "method": method,
            "damping": setting[0],
            "bonus_scale": setting[1],
        }
        for method, setting in selected.items()
    ]
    if validation.get("validated_selected") != expected_selected:
        raise ValueError("authorized selected settings do not match validation evidence")
    if validation.get("validator") != "complete_grid_per_seed_mean_and_argmin_v1":
        raise ValueError("selection authorization validator mismatch")
    if validation.get("candidate_count") != len(artifact["candidates"]):
        raise ValueError("selection authorization candidate count mismatch")
    required_flags = (
        "complete_grid_recomputed",
        "per_seed_means_recomputed",
        "tie_break_recomputed",
    )
    if any(validation.get(flag) is not True for flag in required_flags):
        raise ValueError("selection authorization omits required validation checks")
    if validation.get("test_labels_used") is not False:
        raise ValueError("selection authorization used test labels")

    artifact_path = authorization.get("artifact_path")
    expected_file_digest = authorization.get("artifact_file_sha256")
    if artifact_path is None:
        if require_current_file:
            raise ValueError("selection authorization has no artifact file")
    elif require_current_file:
        path = Path(str(artifact_path))
        if not path.is_file() or not isinstance(expected_file_digest, str):
            raise ValueError("authorized tuning-selection artifact file is unavailable")
        current_file_digest = _file_sha256(path)
        if not hmac.compare_digest(current_file_digest, expected_file_digest):
            raise ValueError("current tuning-selection artifact file hash mismatch")
        current_artifact = load_tuning_selection(path)
        if not hmac.compare_digest(
            _canonical_sha256(current_artifact), expected_artifact_digest
        ):
            raise ValueError("current tuning-selection artifact content mismatch")
    return selected


@dataclass(frozen=True)
class CovertypeExperimentResult:
    phase: Phase
    runs: tuple[CovertypeRun, ...]
    tuning_selection: Mapping[str, Any] | None
    tuning_selection_path: Path | None
    test_diagnostics_paths: tuple[Path, Path] | None


def run_experiment(
    config: Mapping[str, Any],
    *,
    seed_set: Phase = "tuning",
    data: PreparedCovertypeData | None = None,
    dataset: DatasetInput | None = None,
    fetcher: DatasetFetcher | None = None,
    download: bool = False,
    methods: Sequence[str] | None = None,
    output_root: str | Path | None = None,
    tuning_selection: Mapping[str, Any] | str | Path | None = None,
    test_diagnostics_output: str | Path | None = None,
    overwrite: bool = False,
    clock: Callable[[], dt.datetime | str] = _utc_now,
) -> CovertypeExperimentResult:
    if seed_set not in {"tuning", "evaluation"}:
        raise ValueError("seed_set must be 'tuning' or 'evaluation'")
    prepared = (
        prepare_covertype_data(
            config,
            download=download,
            dataset=dataset,
            fetcher=fetcher,
            clock=clock,
        )
        if data is None
        else data
    )
    chosen_methods = configured_methods(config) if methods is None else tuple(methods)
    if not chosen_methods or len(set(chosen_methods)) != len(chosen_methods):
        raise ValueError("requested methods must be nonempty and unique")
    for method in chosen_methods:
        method_protocol(method)
    configured = set(configured_methods(config))
    if not set(chosen_methods) <= configured:
        raise ValueError("requested methods must be present in the resolved config")

    root = None if output_root is None else Path(output_root)
    split_protocol = (
        None
        if root is None
        else _split_artifacts(
            prepared,
            root / str(config.get("profile", "default")) / "dataset_splits",
        )
    )
    runs: list[CovertypeRun] = []
    artifact: Mapping[str, Any] | None = None
    artifact_path: Path | None = None
    diagnostic_paths: tuple[Path, Path] | None = None

    if seed_set == "tuning":
        if tuning_selection is not None and isinstance(tuning_selection, Mapping):
            raise ValueError("tuning_selection mapping is an input only for evaluation")
        for seed in get_seed_set(config, "tuning"):
            for method in chosen_methods:
                for damping, bonus in hyperparameter_grid(config, method):
                    run = run_policy(
                        config,
                        prepared,
                        method,
                        int(seed),
                        phase="tuning",
                        damping=damping,
                        bonus_scale=bonus,
                    )
                    runs.append(run)
                    if root is not None:
                        save_run(
                            run,
                            root,
                            config,
                            prepared,
                            split_protocol=split_protocol,
                            overwrite=overwrite,
                        )
        # A subset run is useful for debugging but cannot create a legal
        # all-method evaluation artifact.
        if len(chosen_methods) == len(configured) and set(chosen_methods) == configured:
            artifact = build_tuning_selection(config, prepared, runs, clock=clock)
            if isinstance(tuning_selection, (str, Path)):
                artifact_path = Path(tuning_selection)
            elif root is not None:
                artifact_path = (
                    root / str(config.get("profile", "default")) / "tuning_selection.json"
                )
            if artifact_path is not None:
                write_tuning_selection(artifact, artifact_path, overwrite=overwrite)
    else:
        if tuning_selection is None:
            if root is None:
                raise ValueError("evaluation requires a tuning-selection artifact")
            artifact_path = (
                root / str(config.get("profile", "default")) / "tuning_selection.json"
            )
            artifact = load_tuning_selection(artifact_path)
        elif isinstance(tuning_selection, Mapping):
            artifact = tuning_selection
        else:
            artifact_path = Path(tuning_selection)
            artifact = load_tuning_selection(artifact_path)
        selected = _validate_selection(config, prepared, artifact)
        authorization = _selection_authorization(artifact, artifact_path, selected)
        selected = verify_selection_authorization(
            config,
            prepared,
            authorization,
            require_current_file=artifact_path is not None,
        )
        for seed in get_seed_set(config, "evaluation"):
            for method in chosen_methods:
                damping, bonus = selected[method]
                run = run_policy(
                    config,
                    prepared,
                    method,
                    int(seed),
                    phase="evaluation",
                    damping=damping,
                    bonus_scale=bonus,
                )
                runs.append(run)
                if root is not None:
                    save_run(
                        run,
                        root,
                        config,
                        prepared,
                        split_protocol=split_protocol,
                        selection_authorization=authorization,
                        overwrite=overwrite,
                    )
        if test_diagnostics_output is not None:
            diagnostic = build_test_class_diagnostics(
                config,
                prepared,
                split_protocol=split_protocol,
                clock=clock,
            )
            diagnostic_paths = write_test_class_diagnostics(
                diagnostic,
                test_diagnostics_output,
                overwrite=overwrite,
            )

    return CovertypeExperimentResult(
        phase=seed_set,
        runs=tuple(runs),
        tuning_selection=artifact,
        tuning_selection_path=artifact_path,
        test_diagnostics_paths=diagnostic_paths,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument(
        "--seed-set", choices=("tuning", "evaluation"), default="tuning"
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="allow sklearn to download Covertype when the local cache is missing",
    )
    parser.add_argument("--method", action="append", choices=SUPPORTED_METHODS)
    parser.add_argument("--rounds", type=int, help="override the configured horizon")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument(
        "--test-diagnostics-output",
        type=Path,
        help="write test class-count/random/oracle diagnostics during evaluation",
    )
    parser.add_argument(
        "--tuning-selection",
        "--selection-artifact",
        dest="tuning_selection",
        type=Path,
        help="write this artifact for tuning or require it for evaluation",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config, profile=args.profile)
    if args.rounds is not None:
        if args.rounds <= 0:
            parser.error("--rounds must be positive")
        if args.seed_set == "tuning":
            config["tuning_rounds"] = args.rounds
        else:
            config["rounds"] = args.rounds
    output_root = args.output_root or Path(str(config["output_root"]))
    try:
        result = run_experiment(
            config,
            seed_set=args.seed_set,
            download=args.download,
            methods=args.method,
            output_root=output_root,
            tuning_selection=args.tuning_selection,
            test_diagnostics_output=args.test_diagnostics_output,
            overwrite=args.overwrite,
        )
    except (FileExistsError, OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {
                "profile": args.profile,
                "seed_set": args.seed_set,
                "run_count": len(result.runs),
                "output_root": str(output_root),
                "tuning_selection": (
                    None
                    if result.tuning_selection_path is None
                    else str(result.tuning_selection_path)
                ),
                "test_diagnostics": (
                    None
                    if result.test_diagnostics_paths is None
                    else [str(path) for path in result.test_diagnostics_paths]
                ),
                "summaries": [run.summary for run in result.runs],
            },
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CovertypeExperimentResult",
    "CovertypeRun",
    "MethodProtocol",
    "NONCONTEXTUAL_METHODS",
    "PreparedCovertypeData",
    "SUPPORTED_METHODS",
    "build_test_class_diagnostics",
    "build_tuning_selection",
    "configured_methods",
    "hyperparameter_grid",
    "load_covertype_data",
    "load_tuning_selection",
    "main",
    "method_protocol",
    "prepare_covertype_data",
    "prepare_dataset",
    "run_experiment",
    "run_method",
    "run_policy",
    "save_run",
    "verify_selection_authorization",
    "write_test_class_diagnostics",
    "write_tuning_selection",
]
