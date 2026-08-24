"""Portable provenance helpers for the realistic transport benchmark."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def canonical_json(value: Any) -> str:
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


def atomic_write_text(path: str | Path, value: str) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def write_json(path: str | Path, value: Mapping[str, Any]) -> tuple[Path, Path]:
    destination = atomic_write_text(
        path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    sidecar = destination.with_name(destination.name + ".sha256")
    atomic_write_text(sidecar, f"{sha256_file(destination)}  {destination.name}\n")
    return destination, sidecar


def input_set_sha256(inputs: Sequence[Mapping[str, str]]) -> str:
    normalized = sorted(
        ({"path": str(item["path"]), "sha256": str(item["sha256"])} for item in inputs),
        key=lambda item: (item["path"], item["sha256"]),
    )
    return sha256_bytes(canonical_json(normalized).encode("ascii"))


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()


def git_state() -> dict[str, Any]:
    try:
        return {
            "branch": _git("branch", "--show-current"),
            "revision": _git("rev-parse", "HEAD"),
            "dirty": bool(_git("status", "--porcelain", "--untracked-files=normal")),
        }
    except (OSError, subprocess.SubprocessError):
        return {"branch": "unknown", "revision": "unknown", "dirty": None}


def package_versions(names: Sequence[str]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in sorted(set(names), key=str.casefold):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            module_name = (
                "sklearn" if name == "scikit-learn" else name.replace("-", "_")
            )
            try:
                module = __import__(module_name)
            except ImportError:
                result[name] = None
            else:
                version = getattr(module, "__version__", None)
                result[name] = str(version) if version is not None else None
    return result


def runtime_metadata(*, workers: int, blas_threads: int) -> dict[str, Any]:
    return {
        "git": git_state(),
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "packages": package_versions(
            ("numpy", "scipy", "scikit-learn", "pytest", "psutil")
        ),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "logical_cpu_count": os.cpu_count(),
        },
        "execution": {
            "workers": int(workers),
            "blas_threads_per_worker": int(blas_threads),
        },
    }


def source_inventory() -> list[dict[str, str]]:
    candidates: list[Path] = [
        REPOSITORY_ROOT / "experiments/REALISTIC_TRANSPORT_PROTOCOL.md",
        REPOSITORY_ROOT / "experiments/configs/realistic_transport_covtype.yaml",
        REPOSITORY_ROOT / "experiments/artifact_utils.py",
        REPOSITORY_ROOT / "experiments/logging_utils.py",
        REPOSITORY_ROOT / "experiments/tests/BUCK",
        REPOSITORY_ROOT / "tests/BUCK",
        REPOSITORY_ROOT / "tests/test_experiment_pipeline.py",
        REPOSITORY_ROOT / "tools/BUCK",
    ]
    package_root = REPOSITORY_ROOT / "experiments/realistic_transport"
    if package_root.exists():
        candidates.extend(
            path
            for path in package_root.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix in {".py", ".md", ".json", ".yaml", ".sh"}
        )
        buck_file = package_root / "BUCK"
        if buck_file.is_file():
            candidates.append(buck_file)
    tool = REPOSITORY_ROOT / "tools/prepare_covtype_benchmark.py"
    if tool.is_file():
        candidates.append(tool)
    unique = sorted({path.resolve() for path in candidates if path.is_file()})
    return [
        {
            "path": str(path.relative_to(REPOSITORY_ROOT)),
            "sha256": sha256_file(path),
        }
        for path in unique
    ]


def assert_source_inventory(expected: Sequence[Mapping[str, str]]) -> None:
    actual = source_inventory()
    normalized = [
        {"path": str(item["path"]), "sha256": str(item["sha256"])} for item in expected
    ]
    if actual != normalized:
        raise ValueError("frozen realistic-transport source inventory changed")


def reject_absolute_paths(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            reject_absolute_paths(child, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            reject_absolute_paths(child, path=f"{path}[{index}]")
    elif isinstance(value, str) and value.startswith("/"):
        raise ValueError(f"absolute path is forbidden at {path}")


__all__ = [
    "REPOSITORY_ROOT",
    "assert_source_inventory",
    "atomic_write_text",
    "canonical_json",
    "git_state",
    "input_set_sha256",
    "package_versions",
    "reject_absolute_paths",
    "runtime_metadata",
    "sha256_bytes",
    "sha256_file",
    "source_inventory",
    "write_json",
]
