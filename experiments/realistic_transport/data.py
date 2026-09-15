"""Deterministic preparation and verification of benchmark datasets.

The runtime consumes a small, self-describing NumPy archive instead of invoking
scikit-learn.  Array content and archive bytes have separate SHA-256 digests:
the content digest is independent of paths and ZIP serialization, while the
artifact digest detects any byte-level change to the prepared file.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import io
import json
import os
import platform
import tempfile
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]

PREPARED_DATA_SCHEMA = "realistic-transport-prepared-data-v1"
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class DataPreparationError(RuntimeError):
    """Raised when source data or a prepared artifact is invalid."""


def canonical_json(value: Any) -> str:
    """Serialize strict JSON with a stable key and whitespace convention."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_array(value: ArrayLike, *, name: str) -> np.ndarray:
    array = np.asarray(value)
    if array.dtype.hasobject:
        raise TypeError(f"{name} must not have object dtype")
    if array.dtype.kind not in "biuf":
        raise TypeError(f"{name} must have a boolean, integer, or floating dtype")
    if array.dtype.kind == "f" and not np.all(np.isfinite(array)):
        raise ValueError(f"{name} contains a nonfinite value")
    little_endian = array.dtype.newbyteorder("<")
    return np.ascontiguousarray(array.astype(little_endian, copy=False))


def canonical_array_digest(arrays: Mapping[str, ArrayLike]) -> str:
    """Hash named arrays independent of host byte order and filesystem paths."""

    digest = hashlib.sha256()
    digest.update(b"realistic-transport-array-content-v1\0")
    for name in sorted(arrays):
        if not isinstance(name, str) or not name:
            raise ValueError("array names must be nonempty strings")
        array = _canonical_array(arrays[name], name=name)
        descriptor = canonical_json(
            {
                "dtype": array.dtype.str,
                "name": name,
                "shape": list(array.shape),
            }
        ).encode("ascii")
        digest.update(len(descriptor).to_bytes(8, "big"))
        digest.update(descriptor)
        digest.update(array.nbytes.to_bytes(8, "big"))
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def deterministic_npz_bytes(arrays: Mapping[str, ArrayLike]) -> bytes:
    """Encode named arrays as a byte-reproducible, uncompressed NPZ archive."""

    output = io.BytesIO()
    with zipfile.ZipFile(
        output, mode="w", compression=zipfile.ZIP_STORED, strict_timestamps=True
    ) as archive:
        for name in sorted(arrays):
            if not name or "/" in name or "\\" in name:
                raise ValueError(f"invalid archive array name: {name!r}")
            array = _canonical_array(arrays[name], name=name)
            payload = io.BytesIO()
            np.lib.format.write_array(payload, array, allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, payload.getvalue())
    return output.getvalue()


def _is_occupied(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _prepared_output_paths(artifact_path: Path) -> tuple[Path, Path, Path]:
    return (
        artifact_path,
        _manifest_path(artifact_path),
        _sidecar_path(artifact_path),
    )


def _refuse_existing_prepared_outputs(artifact_path: Path) -> None:
    existing = [
        str(path)
        for path in _prepared_output_paths(artifact_path)
        if _is_occupied(path)
    ]
    if existing:
        raise FileExistsError(f"refusing to overwrite existing files: {existing}")


def _reject_overwrite_request(overwrite: bool) -> None:
    if overwrite is not False:
        raise ValueError("prepared-data overwrite is not supported")


def _write_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if _is_occupied(path):
        raise FileExistsError(f"refusing to overwrite {path}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if _is_occupied(path):
            raise FileExistsError(f"refusing to overwrite {path}")
        try:
            # A hard link installs the completed temporary inode only when the
            # destination is still absent. Unlike os.replace, this cannot
            # overwrite a file or a dangling symlink created after preflight.
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as error:
            raise FileExistsError(f"refusing to overwrite {path}") from error
    finally:
        temporary.unlink(missing_ok=True)


def _manifest_path(artifact_path: Path) -> Path:
    return artifact_path.with_suffix(artifact_path.suffix + ".manifest.json")


def _sidecar_path(artifact_path: Path) -> Path:
    return artifact_path.with_suffix(artifact_path.suffix + ".sha256")


def _validate_loaded_arrays(
    features: ArrayLike, labels: ArrayLike
) -> tuple[FloatArray, IntArray, list[int]]:
    matrix = np.asarray(features, dtype=np.float64)
    target = np.asarray(labels)
    if matrix.ndim != 2 or matrix.shape[0] < 3 or matrix.shape[1] < 1:
        raise DataPreparationError(
            f"features must have shape (n >= 3, p >= 1), got {matrix.shape}"
        )
    if not np.all(np.isfinite(matrix)):
        raise DataPreparationError("features contain a nonfinite value")
    if target.ndim != 1 or target.shape[0] != matrix.shape[0]:
        raise DataPreparationError(
            f"labels must have shape ({matrix.shape[0]},), got {target.shape}"
        )
    if target.dtype.kind == "f" and not np.all(np.isfinite(target)):
        raise DataPreparationError("labels contain a nonfinite value")
    classes, encoded = np.unique(target, return_inverse=True)
    if classes.size < 2:
        raise DataPreparationError("dataset must contain at least two label classes")
    if classes.dtype.kind not in "biuf":
        raise DataPreparationError("labels must be numeric")
    class_values = [int(value) for value in classes.tolist()]
    if any(
        float(original) != float(integer)
        for original, integer in zip(classes, class_values, strict=True)
    ):
        raise DataPreparationError("labels must be integer-valued")
    matrix = np.ascontiguousarray(matrix, dtype=np.float64)
    encoded = np.ascontiguousarray(encoded, dtype=np.int64)
    return matrix, encoded, class_values


def cache_file_inventory(cache_root: str | Path) -> list[dict[str, Any]]:
    """Return hashes using paths relative to the declared external cache root."""

    root = Path(cache_root)
    if not root.exists():
        return []
    inventory: list[dict[str, Any]] = []
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        relative = path.relative_to(root).as_posix()
        inventory.append(
            {
                "relative_path": relative,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return inventory


@dataclass(frozen=True)
class PreparedDataset:
    """Verified, zero-indexed data loaded from a deterministic artifact."""

    features: FloatArray
    labels: IntArray
    manifest: Mapping[str, Any]
    artifact_path: Path

    @property
    def content_digest(self) -> str:
        return str(self.manifest["array_content_sha256"])

    @property
    def artifact_sha256(self) -> str:
        return str(self.manifest["artifact_sha256"])

    @property
    def dataset_name(self) -> str:
        return str(self.manifest["dataset_name"])

    @property
    def action_count(self) -> int:
        return int(self.manifest["class_count"])

    @property
    def row_count(self) -> int:
        return int(self.features.shape[0])

    @property
    def source_feature_dimension(self) -> int:
        return int(self.features.shape[1])


def prepare_loaded_dataset(
    features: ArrayLike,
    labels: ArrayLike,
    *,
    dataset_name: str,
    destination: str | Path,
    loader_metadata: Mapping[str, Any] | None = None,
    cache_inventory: list[dict[str, Any]] | None = None,
    smoke_only: bool = False,
    fixture_only: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Validate loaded arrays and write the locked runtime artifact."""

    _reject_overwrite_request(overwrite)
    artifact_path = Path(destination)
    _refuse_existing_prepared_outputs(artifact_path)
    if not dataset_name.strip():
        raise ValueError("dataset_name must be nonempty")
    if not isinstance(smoke_only, bool) or not isinstance(fixture_only, bool):
        raise TypeError("smoke_only and fixture_only must be booleans")
    loaded_features = np.asarray(features)
    loaded_labels = np.asarray(labels)
    loaded_digests = {
        "combined": canonical_array_digest(
            {"features": loaded_features, "labels": loaded_labels}
        ),
        "features": canonical_array_digest({"features": loaded_features}),
        "labels": canonical_array_digest({"labels": loaded_labels}),
    }
    matrix, encoded_labels, original_classes = _validate_loaded_arrays(features, labels)
    arrays = {"features": matrix, "labels": encoded_labels}
    content_digest = canonical_array_digest(arrays)
    artifact_bytes = deterministic_npz_bytes(arrays)
    artifact_digest = sha256_bytes(artifact_bytes)
    manifest = {
        "schema": PREPARED_DATA_SCHEMA,
        "dataset_name": dataset_name,
        "smoke_only": smoke_only,
        "fixture_only": fixture_only,
        "publication_evidence": False,
        "row_count": int(matrix.shape[0]),
        "source_feature_dimension": int(matrix.shape[1]),
        "class_count": len(original_classes),
        "original_classes": original_classes,
        "loaded_array_sha256": loaded_digests,
        "loaded_dtypes": {
            "features": loaded_features.dtype.str,
            "labels": loaded_labels.dtype.str,
        },
        "loaded_shapes": {
            "features": list(loaded_features.shape),
            "labels": list(loaded_labels.shape),
        },
        "prepared_dtypes": {"features": "<f8", "labels": "<i8"},
        "array_content_sha256": content_digest,
        "artifact_sha256": artifact_digest,
        "artifact_size_bytes": len(artifact_bytes),
        "loader": dict(loader_metadata or {}),
        "runtime_provenance": _preparation_runtime_provenance(),
        "source_cache_files": list(cache_inventory or []),
    }
    manifest_bytes = (canonical_json(manifest) + "\n").encode("ascii")
    sidecar_bytes = f"{artifact_digest}  {artifact_path.name}\n".encode("ascii")

    _refuse_existing_prepared_outputs(artifact_path)
    _write_once(artifact_path, artifact_bytes)
    _write_once(_manifest_path(artifact_path), manifest_bytes)
    _write_once(_sidecar_path(artifact_path), sidecar_bytes)
    return manifest


def _package_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        # Hermetic Python binaries may package a module without wheel metadata.
        module_name = distribution.replace("-", "_")
        if distribution == "scikit-learn":
            module_name = "sklearn"
        try:
            module = __import__(module_name)
        except ImportError as exc:
            raise DataPreparationError(
                f"{distribution} is required only by the one-time preparation command"
            ) from exc
        version = getattr(module, "__version__", None)
        if not isinstance(version, str) or not version:
            raise DataPreparationError(
                f"cannot determine the installed {distribution} version"
            )
        return version


def _preparation_runtime_provenance() -> dict[str, Any]:
    modules: dict[str, Any] = {}
    for distribution, module_name in (
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("scikit-learn", "sklearn"),
        ("threadpoolctl", "threadpoolctl"),
    ):
        try:
            module = __import__(module_name)
        except ImportError:
            modules[distribution] = {"version": None, "origin": None}
            continue
        raw_origin = getattr(module, "__file__", None)
        origin = Path(raw_origin) if isinstance(raw_origin, str) else None
        modules[distribution] = {
            "version": _package_version(distribution),
            "origin": origin.name if origin is not None else "built_in_or_namespace",
            "origin_sha256": (
                sha256_file(origin) if origin is not None and origin.is_file() else None
            ),
        }
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "modules": modules,
    }


def prepare_covtype_artifact(
    *,
    cache_root: str | Path,
    destination: str | Path,
    download_if_missing: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Fetch Covertype with the official loader and create a locked artifact."""

    _reject_overwrite_request(overwrite)
    artifact_path = Path(destination)
    _refuse_existing_prepared_outputs(artifact_path)
    try:
        from sklearn.datasets import fetch_covtype
    except ImportError as exc:
        raise DataPreparationError(
            "scikit-learn is required for Covertype preparation"
        ) from exc

    cache = Path(cache_root)
    cache.mkdir(parents=True, exist_ok=True)
    features, labels = fetch_covtype(
        data_home=str(cache),
        download_if_missing=download_if_missing,
        as_frame=False,
        shuffle=False,
        return_X_y=True,
    )
    loader_metadata = {
        "callable": "sklearn.datasets.fetch_covtype",
        "scikit_learn_version": _package_version("scikit-learn"),
        "parameters": {
            "as_frame": False,
            "download_if_missing": bool(download_if_missing),
            "return_X_y": True,
            "shuffle": False,
        },
        "returned_container": "tuple[data,target]",
    }
    return prepare_loaded_dataset(
        features,
        labels,
        dataset_name="sklearn_covtype",
        destination=destination,
        loader_metadata=loader_metadata,
        cache_inventory=cache_file_inventory(cache),
        smoke_only=False,
        fixture_only=False,
    )


def prepare_digits_artifact(
    *, destination: str | Path, overwrite: bool = False
) -> dict[str, Any]:
    """Create the deterministic Digits artifact used only for smoke tests."""

    _reject_overwrite_request(overwrite)
    artifact_path = Path(destination)
    _refuse_existing_prepared_outputs(artifact_path)
    try:
        from sklearn.datasets import load_digits
    except ImportError as exc:
        raise DataPreparationError(
            "scikit-learn is required for the Digits smoke artifact"
        ) from exc
    bunch = load_digits(n_class=10, return_X_y=False, as_frame=False)
    loader_metadata = {
        "callable": "sklearn.datasets.load_digits",
        "scikit_learn_version": _package_version("scikit-learn"),
        "parameters": {"as_frame": False, "n_class": 10, "return_X_y": False},
        "bunch_keys": sorted(str(key) for key in bunch.keys()),
        "description_sha256": sha256_bytes(str(bunch.DESCR).encode("utf-8")),
    }
    return prepare_loaded_dataset(
        bunch.data,
        bunch.target,
        dataset_name="sklearn_digits",
        destination=destination,
        loader_metadata=loader_metadata,
        smoke_only=True,
        fixture_only=False,
    )


def load_prepared_dataset(
    artifact_path: str | Path,
    manifest_path: str | Path | None = None,
    required_digest: str | None = None,
    *,
    expected_artifact_sha256: str | None = None,
    expected_content_sha256: str | None = None,
) -> PreparedDataset:
    """Load a prepared artifact after verifying all recorded digests."""

    path = Path(artifact_path)
    selected_manifest_path = (
        _manifest_path(path) if manifest_path is None else Path(manifest_path)
    )
    try:
        manifest = json.loads(selected_manifest_path.read_text(encoding="ascii"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataPreparationError(
            f"cannot read prepared-data manifest: {exc}"
        ) from exc
    if manifest.get("schema") != PREPARED_DATA_SCHEMA:
        raise DataPreparationError("prepared-data manifest has an unknown schema")
    if not isinstance(manifest.get("smoke_only"), bool):
        raise DataPreparationError("prepared-data smoke_only must be a boolean")
    if not isinstance(manifest.get("fixture_only"), bool):
        raise DataPreparationError("prepared-data fixture_only must be a boolean")
    if manifest.get("publication_evidence") is not False:
        raise DataPreparationError("prepared data cannot be publication evidence")
    actual_artifact_digest = sha256_file(path)
    recorded_artifact_digest = str(manifest.get("artifact_sha256", ""))
    if actual_artifact_digest != recorded_artifact_digest:
        raise DataPreparationError("prepared artifact SHA-256 does not match manifest")
    if (
        expected_artifact_sha256 is not None
        and actual_artifact_digest != expected_artifact_sha256
    ):
        raise DataPreparationError("prepared artifact SHA-256 does not match config")
    try:
        sidecar_fields = _sidecar_path(path).read_text(encoding="ascii").split()
    except OSError as exc:
        raise DataPreparationError(f"cannot read prepared-data sidecar: {exc}") from exc
    if not sidecar_fields or sidecar_fields[0] != actual_artifact_digest:
        raise DataPreparationError("prepared artifact SHA-256 sidecar is invalid")

    try:
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != {"features", "labels"}:
                raise DataPreparationError(
                    f"prepared artifact has unexpected arrays: {sorted(archive.files)}"
                )
            features = np.asarray(archive["features"], dtype=np.float64)
            labels = np.asarray(archive["labels"], dtype=np.int64)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise DataPreparationError(f"cannot load prepared artifact: {exc}") from exc
    features, labels, classes = _validate_loaded_arrays(features, labels)
    if classes != list(range(len(classes))):
        raise DataPreparationError(
            "prepared labels are not contiguous and zero-indexed"
        )
    actual_content_digest = canonical_array_digest(
        {"features": features, "labels": labels}
    )
    if actual_content_digest != manifest.get("array_content_sha256"):
        raise DataPreparationError(
            "prepared array-content digest does not match manifest"
        )
    if (
        expected_content_sha256 is not None
        and actual_content_digest != expected_content_sha256
    ):
        raise DataPreparationError(
            "prepared array-content digest does not match config"
        )
    if required_digest is not None and actual_content_digest != required_digest:
        raise DataPreparationError(
            "prepared array-content digest does not match required_digest"
        )
    expected_shape = (
        int(manifest.get("row_count", -1)),
        int(manifest.get("source_feature_dimension", -1)),
    )
    if features.shape != expected_shape:
        raise DataPreparationError(
            f"prepared feature shape {features.shape} does not match {expected_shape}"
        )
    if len(classes) != int(manifest.get("class_count", -1)):
        raise DataPreparationError("prepared class count does not match manifest")
    features.setflags(write=False)
    labels.setflags(write=False)
    return PreparedDataset(
        features=features,
        labels=labels,
        manifest=manifest,
        artifact_path=path,
    )


def prepare_dataset(
    dataset_name: str,
    data_root: str | Path | None,
    output_prefix: str | Path,
    *,
    download_if_missing: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Prepare the named official dataset through a compact caller API."""

    normalized = str(dataset_name).strip().lower()
    _reject_overwrite_request(overwrite)
    destination = Path(output_prefix)
    if destination.suffix != ".npz":
        destination = destination.with_suffix(".npz")
    _refuse_existing_prepared_outputs(destination)
    if normalized in {"covtype", "covertype", "sklearn_covtype"}:
        if data_root is None:
            raise DataPreparationError("Covertype preparation requires data_root")
        return prepare_covtype_artifact(
            cache_root=data_root,
            destination=destination,
            download_if_missing=download_if_missing,
        )
    if normalized in {"digits", "sklearn_digits"}:
        return prepare_digits_artifact(destination=destination)
    raise ValueError(f"unknown dataset_name {dataset_name!r}")


__all__ = [
    "DataPreparationError",
    "PreparedDataset",
    "cache_file_inventory",
    "canonical_array_digest",
    "canonical_json",
    "deterministic_npz_bytes",
    "load_prepared_dataset",
    "prepare_dataset",
    "prepare_covtype_artifact",
    "prepare_digits_artifact",
    "prepare_loaded_dataset",
    "sha256_file",
]
