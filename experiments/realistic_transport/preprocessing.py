"""Deterministic split, standardization, and PCA for real-context tasks."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .data import canonical_array_digest, canonical_json


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
BoolArray = NDArray[np.bool_]

SPLIT_NAMESPACE = "realistic-transport-covtype-v1"


class PreprocessingError(RuntimeError):
    """Raised when a split or fitted transform violates the protocol."""


def _readonly(array: np.ndarray) -> np.ndarray:
    array.setflags(write=False)
    return array


def _validate_digest(value: str) -> str:
    normalized = str(value).lower()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError(
            "prepared_data_digest must be a 64-character SHA-256 hex value"
        )
    return normalized


def index_digest(indices: ArrayLike) -> str:
    values = np.asarray(indices, dtype=np.int64)
    if values.ndim != 1 or np.any(values < 0):
        raise ValueError("indices must be a one-dimensional nonnegative array")
    return canonical_array_digest({"indices": values})


@dataclass(frozen=True)
class DatasetSplit:
    development: IntArray
    tuning: IntArray
    evaluation: IntArray
    row_count: int
    prepared_data_digest: str
    namespace: str = SPLIT_NAMESPACE

    def __post_init__(self) -> None:
        if self.row_count < 3:
            raise ValueError("row_count must be at least three")
        _validate_digest(self.prepared_data_digest)
        arrays: list[IntArray] = []
        for name in ("development", "tuning", "evaluation"):
            values = np.asarray(getattr(self, name), dtype=np.int64)
            if values.ndim != 1 or values.size == 0:
                raise ValueError(f"{name} indices must be a nonempty vector")
            if np.any(values < 0) or np.any(values >= self.row_count):
                raise ValueError(f"{name} contains an out-of-range row index")
            if np.unique(values).size != values.size:
                raise ValueError(f"{name} contains duplicate row indices")
            values = np.sort(values)
            object.__setattr__(self, name, _readonly(values))
            arrays.append(values)
        combined = np.concatenate(arrays)
        if (
            combined.size != self.row_count
            or np.unique(combined).size != self.row_count
        ):
            raise ValueError("split indices are not disjoint and complete")
        if not np.array_equal(np.sort(combined), np.arange(self.row_count)):
            raise ValueError("split indices do not cover every row exactly once")

    def phase_indices(self, phase: str) -> IntArray:
        if phase not in {"development", "tuning", "evaluation"}:
            raise ValueError(f"unknown phase {phase!r}")
        return getattr(self, phase)

    @property
    def digest(self) -> str:
        arrays = {
            "development": self.development,
            "evaluation": self.evaluation,
            "tuning": self.tuning,
        }
        metadata = canonical_json(
            {
                "array_digest": canonical_array_digest(arrays),
                "namespace": self.namespace,
                "prepared_data_digest": self.prepared_data_digest,
                "row_count": self.row_count,
            }
        ).encode("ascii")
        return hashlib.sha256(metadata).hexdigest()


def deterministic_split(
    row_count: int,
    prepared_data_digest: str,
    *,
    development_fraction: float = 0.2,
    tuning_fraction: float = 0.2,
    namespace: str = SPLIT_NAMESPACE,
) -> DatasetSplit:
    """Assign each row from the first eight SHA-256 bytes modulo 100."""

    if isinstance(row_count, bool) or not isinstance(row_count, (int, np.integer)):
        raise TypeError("row_count must be an integer")
    count = int(row_count)
    if count < 3:
        raise ValueError("row_count must be at least three")
    digest = _validate_digest(prepared_data_digest)
    development_fraction = float(development_fraction)
    tuning_fraction = float(tuning_fraction)
    if (
        not math.isfinite(development_fraction)
        or not math.isfinite(tuning_fraction)
        or development_fraction <= 0.0
        or tuning_fraction <= 0.0
        or development_fraction + tuning_fraction >= 1.0
    ):
        raise ValueError("split fractions must be positive and sum to less than one")

    development_bucket_count = int(round(100.0 * development_fraction))
    tuning_bucket_count = int(round(100.0 * tuning_fraction))
    if development_bucket_count <= 0 or tuning_bucket_count <= 0:
        raise ValueError("split fractions are too small for 100 hash buckets")
    tuning_cutoff = development_bucket_count + tuning_bucket_count
    partitions: list[list[int]] = [[], [], []]
    prefix = f"{namespace}\0{digest}\0".encode("ascii")
    for row_index in range(count):
        value = int.from_bytes(
            hashlib.sha256(prefix + str(row_index).encode("ascii")).digest()[:8],
            "big",
        )
        bucket = value % 100
        partition = (
            0
            if bucket < development_bucket_count
            else 1 if bucket < tuning_cutoff else 2
        )
        partitions[partition].append(row_index)
    if any(not partition for partition in partitions):
        raise PreprocessingError(
            "hash split produced an empty partition; the dataset is too small"
        )
    return DatasetSplit(
        development=np.asarray(partitions[0], dtype=np.int64),
        tuning=np.asarray(partitions[1], dtype=np.int64),
        evaluation=np.asarray(partitions[2], dtype=np.int64),
        row_count=count,
        prepared_data_digest=digest,
        namespace=namespace,
    )


@dataclass(frozen=True)
class PreprocessingTransform:
    """Development-only standardization and fixed-rank PCA transform."""

    mean: FloatArray
    scale: FloatArray
    zero_variance: BoolArray
    projection: FloatArray
    eigenvalues: FloatArray
    sign_anchors: IntArray
    development_index_digest: str
    prepared_data_digest: str
    covariance_divisor: int

    def __post_init__(self) -> None:
        mean = np.asarray(self.mean, dtype=np.float64)
        scale = np.asarray(self.scale, dtype=np.float64)
        zero = np.asarray(self.zero_variance, dtype=np.bool_)
        projection = np.asarray(self.projection, dtype=np.float64)
        eigenvalues = np.asarray(self.eigenvalues, dtype=np.float64)
        sign_anchors = np.asarray(self.sign_anchors, dtype=np.int64)
        dimension = mean.size
        if mean.shape != (dimension,) or scale.shape != (dimension,):
            raise ValueError("mean and scale must be vectors of equal size")
        if zero.shape != (dimension,):
            raise ValueError("zero_variance must match the source dimension")
        if projection.ndim != 2 or projection.shape[0] != dimension:
            raise ValueError("projection has the wrong source dimension")
        if eigenvalues.shape != (dimension,):
            raise ValueError("eigenvalues must contain the full source spectrum")
        if sign_anchors.shape != (projection.shape[1],):
            raise ValueError("sign_anchors must contain one index per component")
        if np.any(sign_anchors < 0) or np.any(sign_anchors >= dimension):
            raise ValueError("sign_anchors contain an out-of-range coordinate")
        if not all(
            np.all(np.isfinite(value))
            for value in (mean, scale, projection, eigenvalues)
        ):
            raise ValueError("preprocessing transform contains nonfinite values")
        if np.any(scale <= 0.0):
            raise ValueError("preprocessing scales must be positive")
        if np.any(eigenvalues < -1e-12 * max(1.0, float(eigenvalues[0]))):
            raise ValueError(
                "preprocessing covariance has a material negative eigenvalue"
            )
        if self.covariance_divisor <= 0:
            raise ValueError("covariance_divisor must be positive")
        _validate_digest(self.prepared_data_digest)
        _validate_digest(self.development_index_digest)
        gram = projection.T @ projection
        np.testing.assert_allclose(
            gram,
            np.eye(projection.shape[1]),
            rtol=2e-12,
            atol=2e-12,
        )
        object.__setattr__(self, "mean", _readonly(mean.copy()))
        object.__setattr__(self, "scale", _readonly(scale.copy()))
        object.__setattr__(self, "zero_variance", _readonly(zero.copy()))
        object.__setattr__(self, "projection", _readonly(projection.copy()))
        object.__setattr__(self, "eigenvalues", _readonly(eigenvalues.copy()))
        object.__setattr__(self, "sign_anchors", _readonly(sign_anchors.copy()))

    @property
    def source_dimension(self) -> int:
        return int(self.mean.size)

    @property
    def output_dimension(self) -> int:
        return int(self.projection.shape[1])

    @property
    def digest(self) -> str:
        arrays = {
            "eigenvalues": self.eigenvalues,
            "mean": self.mean,
            "projection": self.projection,
            "scale": self.scale,
            "sign_anchors": self.sign_anchors,
            "zero_variance": self.zero_variance,
        }
        payload = canonical_json(
            {
                "array_digest": canonical_array_digest(arrays),
                "covariance_divisor": self.covariance_divisor,
                "development_index_digest": self.development_index_digest,
                "prepared_data_digest": self.prepared_data_digest,
                "schema": "realistic-transport-preprocessing-v1",
            }
        ).encode("ascii")
        return hashlib.sha256(payload).hexdigest()

    def transform(self, features: ArrayLike) -> FloatArray:
        matrix = np.asarray(features, dtype=np.float64)
        single = matrix.ndim == 1
        if single:
            matrix = matrix[np.newaxis, :]
        if matrix.ndim != 2 or matrix.shape[1] != self.source_dimension:
            raise ValueError(
                f"features must end in dimension {self.source_dimension}, got {matrix.shape}"
            )
        if not np.all(np.isfinite(matrix)):
            raise ValueError("features contain a nonfinite value")
        projected = ((matrix - self.mean) / self.scale) @ self.projection
        norms = np.linalg.norm(projected, axis=1)
        denominators = np.maximum(1.0, norms)
        normalized = projected / denominators[:, np.newaxis]
        if np.any(
            np.linalg.norm(normalized, axis=1) > 1.0 + 32.0 * np.finfo(np.float64).eps
        ):
            raise FloatingPointError("context normalization failed")
        result = np.asarray(normalized, dtype=np.float64)
        return result[0] if single else result

    def summary(self, transformed_features: ArrayLike) -> dict[str, Any]:
        values = np.asarray(transformed_features, dtype=np.float64)
        if values.ndim != 2 or values.shape[1] != self.output_dimension:
            raise ValueError("transformed features have the wrong shape")
        norms = np.linalg.norm(values, axis=1)
        return {
            "row_count": int(values.shape[0]),
            "dimension": int(values.shape[1]),
            "coordinate_mean": np.mean(values, axis=0).tolist(),
            "coordinate_std": np.std(values, axis=0).tolist(),
            "norm_min": float(np.min(norms)),
            "norm_mean": float(np.mean(norms)),
            "norm_max": float(np.max(norms)),
            "array_content_sha256": canonical_array_digest({"contexts": values}),
        }


def fit_preprocessing(
    features: ArrayLike,
    development_indices: ArrayLike,
    *,
    prepared_data_digest: str,
    rank: int = 16,
    zero_variance_tolerance: float | None = None,
    degeneracy_tolerance: float | None = None,
) -> PreprocessingTransform:
    """Fit all statistics using only explicitly supplied development rows."""

    matrix = np.asarray(features, dtype=np.float64)
    indices = np.asarray(development_indices, dtype=np.int64)
    if matrix.ndim != 2 or matrix.shape[0] < 3 or matrix.shape[1] < 1:
        raise ValueError("features must be a nonempty two-dimensional matrix")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("features contain a nonfinite value")
    if indices.ndim != 1 or indices.size < 2:
        raise ValueError("development_indices must contain at least two rows")
    if np.any(indices < 0) or np.any(indices >= matrix.shape[0]):
        raise ValueError("development_indices contain an out-of-range row")
    if np.unique(indices).size != indices.size:
        raise ValueError("development_indices contain duplicates")
    if isinstance(rank, bool) or not isinstance(rank, (int, np.integer)):
        raise TypeError("rank must be an integer")
    rank = int(rank)
    if rank <= 0 or rank > matrix.shape[1]:
        raise ValueError("rank must lie between one and the source dimension")

    development = matrix[indices]
    mean = np.mean(development, axis=0, dtype=np.float64)
    centered = development - mean
    variances = np.mean(centered * centered, axis=0, dtype=np.float64)
    if zero_variance_tolerance is None:
        zero_variance_tolerance = 0.0
    tolerance = float(zero_variance_tolerance)
    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("zero_variance_tolerance must be finite and nonnegative")
    zero_variance = variances <= tolerance
    scale = np.sqrt(np.maximum(variances, 0.0))
    scale[zero_variance] = 1.0
    standardized = centered / scale
    standardized[:, zero_variance] = 0.0
    covariance = (standardized.T @ standardized) / float(development.shape[0])
    covariance = 0.5 * (covariance + covariance.T)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues, kind="stable")[::-1]
    eigenvalues = np.asarray(eigenvalues[order], dtype=np.float64)
    eigenvectors = np.asarray(eigenvectors[:, order], dtype=np.float64)
    spectral_scale = max(1.0, float(eigenvalues[0]))
    negative_tolerance = 4096.0 * np.finfo(np.float64).eps * spectral_scale
    if float(eigenvalues[-1]) < -negative_tolerance:
        raise PreprocessingError("development covariance is materially indefinite")
    eigenvalues[eigenvalues < 0.0] = 0.0
    rank_tolerance = (
        np.finfo(np.float64).eps * max(development.shape) * spectral_scale * 32.0
    )
    if float(eigenvalues[rank - 1]) <= rank_tolerance:
        raise PreprocessingError(
            f"development covariance has numerical rank below requested rank {rank}"
        )
    if degeneracy_tolerance is None:
        degeneracy_tolerance = 4096.0 * np.finfo(np.float64).eps * spectral_scale
    gap_tolerance = float(degeneracy_tolerance)
    if not math.isfinite(gap_tolerance) or gap_tolerance < 0.0:
        raise ValueError("degeneracy_tolerance must be finite and nonnegative")
    if rank < matrix.shape[1]:
        cutoff_gap = float(eigenvalues[rank - 1] - eigenvalues[rank])
        if cutoff_gap <= gap_tolerance:
            raise PreprocessingError(
                "PCA cutoff lies in a numerically degenerate eigenspace"
            )

    projection = eigenvectors[:, :rank].copy()
    sign_anchors = np.empty(rank, dtype=np.int64)
    for component_index in range(rank):
        component = projection[:, component_index]
        pivot = int(np.argmax(np.abs(component)))
        if abs(float(component[pivot])) <= rank_tolerance:
            raise PreprocessingError("PCA component has no stable sign pivot")
        if component[pivot] < 0.0:
            projection[:, component_index] *= -1.0
        sign_anchors[component_index] = pivot

    return PreprocessingTransform(
        mean=mean,
        scale=scale,
        zero_variance=zero_variance,
        projection=projection,
        eigenvalues=eigenvalues,
        sign_anchors=sign_anchors,
        development_index_digest=index_digest(indices),
        prepared_data_digest=_validate_digest(prepared_data_digest),
        covariance_divisor=int(development.shape[0]),
    )


PreprocessingArtifact = PreprocessingTransform


__all__ = [
    "DatasetSplit",
    "PreprocessingArtifact",
    "PreprocessingError",
    "PreprocessingTransform",
    "SPLIT_NAMESPACE",
    "deterministic_split",
    "fit_preprocessing",
    "index_digest",
]
