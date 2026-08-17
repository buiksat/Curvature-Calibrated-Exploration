"""Small deterministic helpers shared by new reproduction pipelines."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .logging_utils import canonical_json


class ArtifactProvenanceError(ValueError):
    """Raised when an artifact or its provenance record is invalid."""


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


def validate_aggregate_provenance_sidecar(
    artifact: str | Path, sidecar: str | Path | None = None
) -> dict[str, Any]:
    """Validate an aggregate digest and its complete input inventory."""

    artifact_path = Path(artifact)
    sidecar_path = (
        artifact_path.with_suffix(artifact_path.suffix + ".provenance.json")
        if sidecar is None
        else Path(sidecar)
    )
    try:
        record = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ArtifactProvenanceError(
            f"cannot parse sidecar {sidecar_path}: {error}"
        ) from error
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        raise ArtifactProvenanceError("unsupported aggregate provenance sidecar")
    if record.get("artifact") != str(artifact_path):
        raise ArtifactProvenanceError("sidecar artifact path does not match")
    if record.get("artifact_sha256") != sha256_file(artifact_path):
        raise ArtifactProvenanceError("sidecar artifact digest does not match")

    inputs = record.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise ArtifactProvenanceError("sidecar must bind at least one input")
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(inputs):
        if not isinstance(item, Mapping):
            raise ArtifactProvenanceError(f"invalid sidecar input {index}")
        path_value = item.get("path")
        digest_value = item.get("sha256")
        if not isinstance(path_value, str) or not isinstance(digest_value, str):
            raise ArtifactProvenanceError(f"invalid sidecar input {index}")
        input_path = Path(path_value)
        if not input_path.is_file():
            raise ArtifactProvenanceError(f"sidecar input is missing: {input_path}")
        if sha256_file(input_path) != digest_value:
            raise ArtifactProvenanceError(
                f"sidecar input digest does not match: {input_path}"
            )
        normalized.append({"path": path_value, "sha256": digest_value})
    if normalized != sorted(normalized, key=lambda item: item["path"]):
        raise ArtifactProvenanceError(
            "sidecar inputs are not in canonical path order"
        )

    try:
        aggregate_record = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ArtifactProvenanceError(
            f"cannot parse aggregate artifact: {error}"
        ) from error
    if not isinstance(aggregate_record, Mapping):
        raise ArtifactProvenanceError("aggregate artifact is not an object")
    if aggregate_record.get("inputs") != normalized:
        raise ArtifactProvenanceError(
            "sidecar inputs do not match the aggregate's complete input inventory"
        )
    expected_input_digest = input_set_sha256(normalized)
    if aggregate_record.get("input_set_sha256") != expected_input_digest:
        raise ArtifactProvenanceError("aggregate input inventory digest does not match")
    if record.get("input_set_sha256") != expected_input_digest:
        raise ArtifactProvenanceError("sidecar input inventory digest does not match")
    return record


def write_aggregate_with_provenance(
    aggregate: Mapping[str, Any], destination: str | Path
) -> tuple[Path, Path]:
    """Write a JSON aggregate and bind it to every declared input file."""

    inputs = aggregate.get("inputs")
    if not isinstance(inputs, Sequence) or isinstance(inputs, (str, bytes)) or not inputs:
        raise ArtifactProvenanceError("aggregate has no input provenance")
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(inputs):
        if not isinstance(item, Mapping):
            raise ArtifactProvenanceError(f"invalid aggregate input {index}")
        path_value = item.get("path")
        digest_value = item.get("sha256")
        if not isinstance(path_value, str) or not isinstance(digest_value, str):
            raise ArtifactProvenanceError(f"invalid aggregate input {index}")
        normalized.append({"path": path_value, "sha256": digest_value})
    normalized.sort(key=lambda item: item["path"])
    expected_input_digest = input_set_sha256(normalized)
    if aggregate.get("input_set_sha256") != expected_input_digest:
        raise ArtifactProvenanceError("aggregate input inventory digest does not match")

    path = atomic_write_text(
        destination,
        json.dumps(aggregate, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    sidecar = path.with_suffix(path.suffix + ".provenance.json")
    sidecar_record = {
        "schema_version": 1,
        "artifact": str(path),
        "artifact_sha256": sha256_file(path),
        "input_set_sha256": expected_input_digest,
        "inputs": normalized,
    }
    atomic_write_text(
        sidecar,
        json.dumps(sidecar_record, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    validate_aggregate_provenance_sidecar(path, sidecar)
    return path, sidecar


__all__ = [
    "ArtifactProvenanceError",
    "atomic_write_bytes",
    "atomic_write_text",
    "input_set_sha256",
    "sha256_file",
    "validate_aggregate_provenance_sidecar",
    "validate_sha256_sidecar",
    "write_aggregate_with_provenance",
    "write_json_artifact",
    "write_sha256_sidecar",
]
