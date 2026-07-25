"""Small deterministic helpers shared by new reproduction pipelines."""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .logging_utils import canonical_json


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_set_sha256(inputs: Sequence[Mapping[str, str]]) -> str:
    normalized = sorted(
        ({"path": str(item["path"]), "sha256": str(item["sha256"])} for item in inputs),
        key=lambda item: (item["path"], item["sha256"]),
    )
    return hashlib.sha256(canonical_json(normalized).encode("ascii")).hexdigest()


def atomic_write_bytes(path: str | Path, payload: bytes) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        os.chmod(destination, 0o644)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def atomic_write_text(path: str | Path, text: str, *, encoding: str = "utf-8") -> Path:
    return atomic_write_bytes(path, text.encode(encoding))


def write_sha256_sidecar(path: str | Path) -> Path:
    artifact = Path(path)
    sidecar = artifact.with_name(artifact.name + ".sha256")
    return atomic_write_text(
        sidecar,
        f"{sha256_file(artifact)}  {artifact.name}\n",
        encoding="ascii",
    )


def validate_sha256_sidecar(path: str | Path) -> None:
    artifact = Path(path)
    sidecar = artifact.with_name(artifact.name + ".sha256")
    fields = sidecar.read_text(encoding="ascii").strip().split()
    if len(fields) != 2 or fields[1] != artifact.name:
        raise ValueError(f"malformed SHA-256 sidecar for {artifact}")
    if fields[0] != sha256_file(artifact):
        raise ValueError(f"SHA-256 mismatch for {artifact}")


def write_json_artifact(path: str | Path, value: Any) -> tuple[Path, Path]:
    artifact = atomic_write_text(
        path, canonical_json(value) + "\n", encoding="ascii"
    )
    return artifact, write_sha256_sidecar(artifact)


def write_provenance_sidecar(
    artifact_path: str | Path,
    inputs: Sequence[Mapping[str, str]],
    *,
    generation_parameters: Mapping[str, Any] | None = None,
) -> Path:
    artifact = Path(artifact_path)
    normalized_inputs = sorted(
        (
            {"path": str(item["path"]), "sha256": str(item["sha256"])}
            for item in inputs
        ),
        key=lambda item: (item["path"], item["sha256"]),
    )
    for item in normalized_inputs:
        source = Path(item["path"])
        if not source.is_file() or sha256_file(source) != item["sha256"]:
            raise ValueError(f"provenance input is missing or stale: {source}")
    value: dict[str, Any] = {
        "artifact": artifact.as_posix(),
        "artifact_sha256": sha256_file(artifact),
        "input_set_sha256": input_set_sha256(normalized_inputs),
        "inputs": normalized_inputs,
        "schema_version": 1,
    }
    if generation_parameters is not None:
        value["generation_parameters"] = dict(generation_parameters)
    return atomic_write_text(
        artifact.with_name(artifact.name + ".provenance.json"),
        canonical_json(value) + "\n",
        encoding="ascii",
    )


def write_deterministic_npz(
    path: str | Path, arrays: Mapping[str, NDArray[np.generic]]
) -> tuple[Path, Path]:
    """Write an ``np.load`` archive with fixed entry order and timestamps."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as raw_handle:
            with zipfile.ZipFile(
                raw_handle,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
                strict_timestamps=True,
            ) as archive:
                for name in sorted(arrays):
                    array = np.asarray(arrays[name])
                    if array.dtype.hasobject:
                        raise TypeError(f"array {name!r} has object dtype")
                    buffer = io.BytesIO()
                    np.lib.format.write_array(buffer, array, allow_pickle=False)
                    info = zipfile.ZipInfo(
                        f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0)
                    )
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(
                        info,
                        buffer.getvalue(),
                        compress_type=zipfile.ZIP_DEFLATED,
                        compresslevel=9,
                    )
            raw_handle.flush()
            os.fsync(raw_handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination, write_sha256_sidecar(destination)


__all__ = [
    "atomic_write_bytes",
    "atomic_write_text",
    "input_set_sha256",
    "sha256_file",
    "validate_sha256_sidecar",
    "write_deterministic_npz",
    "write_json_artifact",
    "write_provenance_sidecar",
    "write_sha256_sidecar",
]
