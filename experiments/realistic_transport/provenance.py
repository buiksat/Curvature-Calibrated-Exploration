"""Portable provenance helpers for the realistic transport benchmark."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import stat
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from threadpoolctl import threadpool_info, threadpool_limits


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCIENTIFIC_EXACT_PATHS = frozenset(
    {
        ".buck2",
        ".buckconfig",
        "BUCK",
        "BUCK2_SETUP.md",
        "PACKAGE",
        "experiments/BUCK",
        "experiments/REALISTIC_TRANSPORT_PROTOCOL.md",
        "experiments/__init__.py",
        "experiments/artifact_utils.py",
        "experiments/configs/realistic_transport_covtype.yaml",
        "experiments/logging_utils.py",
        "experiments/requirements.txt",
        "experiments/tests/BUCK",
        "pytest.ini",
        "tests/BUCK",
        "tests/test_experiment_pipeline.py",
        "third_party/BUCK",
        "third_party/wheels/SHA256SUMS",
        "tools/BUCK",
        "tools/prepare_covtype_benchmark.py",
    }
)
SCIENTIFIC_PREFIXES = ("experiments/realistic_transport/",)
SCIENTIFIC_IMPORTABLE_SUFFIXES = (
    ".bzl",
    ".py",
    ".pyc",
    ".pyi",
    ".pyo",
    ".so",
)
SCIENTIFIC_BUCK_BASENAMES = frozenset(
    {
        ".buckconfig",
        ".buckconfig.local",
        ".buckroot",
        "BUCK",
        "BUCK_TREE",
        "PACKAGE",
    }
)
SCIENTIFIC_BUCK_EXACT_PATHS = frozenset(
    {
        ".buck2",
        ".buck2-previous",
        "experiments/tests/run_buck_pytest.sh",
        "tests/run_buck_pytest.sh",
    }
)
SCIENTIFIC_BUCK_PREFIXES = (
    ".buck2-versions/",
    "third_party/wheels/",
    "tools/buck2-versions/",
)
NONSCIENTIFIC_OUTPUT_PREFIXES = (
    "buck-out/",
    "results/logs/",
    "results/raw/",
)
ALLOWED_SCIENTIFIC_SYMLINKS = frozenset(
    {
        ".buck/fbsource_cell/arvr",
        ".buck/fbsource_cell/fbandroid",
        ".buck/fbsource_cell/fbcode",
        ".buck/fbsource_cell/fbobjc",
        ".buck/fbsource_cell/genai",
        ".buck/fbsource_cell/nest",
        ".buck/fbsource_cell/opsfiles",
        ".buck/fbsource_cell/ovrsource-legacy",
        ".buck/fbsource_cell/third-party",
        ".buck/fbsource_cell/thrift_sync",
        ".buck/fbsource_cell/tools",
        ".buck/fbsource_cell/users",
        ".buck/fbsource_cell/whatsapp",
        ".buck/fbsource_cell/www",
        ".buck/fbsource_cell/xplat",
        "third_party/wheels/scipy-1.13.1-cp312-cp312-manylinux_x86_64.whl",
        "tools/build_defs",
    }
)


def _normalized_repository_path(path: str) -> str | None:
    """Normalize a repository-relative POSIX path without permitting escape."""

    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    return candidate.as_posix().removeprefix("./")


def _is_nonscientific_output(path: str) -> bool:
    normalized = _normalized_repository_path(path)
    if normalized is None:
        return False
    return any(
        normalized == prefix.removesuffix("/") or normalized.startswith(prefix)
        for prefix in NONSCIENTIFIC_OUTPUT_PREFIXES
    )


def is_scientific_path(path: str, *, is_symlink: bool = False) -> bool:
    """Return whether a repository-relative path can affect the study."""

    normalized = _normalized_repository_path(path)
    if normalized is None:
        return False
    if _is_nonscientific_output(normalized):
        return False
    parts = PurePosixPath(normalized).parts
    basename = parts[-1] if parts else ""
    is_buck_config_fragment = ".buckconfig.d" in parts[:-1]
    return (
        normalized in SCIENTIFIC_EXACT_PATHS
        or normalized in ALLOWED_SCIENTIFIC_SYMLINKS
        or normalized.startswith(SCIENTIFIC_PREFIXES)
        or normalized.endswith(SCIENTIFIC_IMPORTABLE_SUFFIXES)
        or basename in SCIENTIFIC_BUCK_BASENAMES
        or is_buck_config_fragment
        or normalized in SCIENTIFIC_BUCK_EXACT_PATHS
        or normalized.startswith(SCIENTIFIC_BUCK_PREFIXES)
        or is_symlink
    )


def scientific_files(root: str | Path) -> list[Path]:
    """Return every present file on the central scientific-source surface."""

    repository_root = Path(root).resolve()
    candidates: list[Path] = []
    for directory, directory_names, file_names in os.walk(repository_root):
        parent = Path(directory)
        relative_parent = parent.relative_to(repository_root)
        kept_directories: list[str] = []
        for name in directory_names:
            relative = (relative_parent / name).as_posix()
            if relative == ".git" or _is_nonscientific_output(relative):
                continue
            candidate = parent / name
            if candidate.is_symlink():
                if is_scientific_path(relative, is_symlink=True):
                    candidates.append(candidate)
                continue
            kept_directories.append(name)
        directory_names[:] = kept_directories
        for name in file_names:
            candidate = parent / name
            relative = candidate.relative_to(repository_root).as_posix()
            if is_scientific_path(
                relative,
                is_symlink=candidate.is_symlink(),
            ) and (candidate.is_file() or candidate.is_symlink()):
                candidates.append(candidate)
    return sorted(
        candidates, key=lambda path: path.relative_to(repository_root).as_posix()
    )


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


def sha256_source_path(path: str | Path) -> str:
    """Hash a source file or the stored text of a symbolic link."""

    candidate = Path(path)
    if candidate.is_symlink():
        return sha256_bytes(os.fsencode(os.readlink(candidate)))
    return sha256_file(candidate)


def source_path_mode(path: str | Path) -> str:
    """Return the Git-compatible mode for a worktree source entry."""

    candidate = Path(path)
    metadata = candidate.lstat()
    if stat.S_ISLNK(metadata.st_mode):
        return "120000"
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"unsupported scientific source entry type: {candidate}")
    return "100755" if metadata.st_mode & 0o111 else "100644"


def atomic_write_text(path: str | Path, value: str) -> Path:
    """Create one text file without replacing any final-path occupant."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.tmp-",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError as error:
            raise FileExistsError(
                f"refusing to overwrite evidence output: {destination}"
            ) from error
        return destination
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def write_json(path: str | Path, value: Mapping[str, Any]) -> tuple[Path, Path]:
    destination = atomic_write_text(
        path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    sidecar = destination.with_name(destination.name + ".sha256")
    atomic_write_text(sidecar, f"{sha256_file(destination)}  {destination.name}\n")
    return destination, sidecar


def input_set_sha256(inputs: Sequence[Mapping[str, str]]) -> str:
    normalized: list[dict[str, str]] = []
    for item in inputs:
        unexpected = set(item) - {"path", "sha256", "mode"}
        if unexpected:
            raise ValueError(f"input inventory has unsupported fields: {unexpected}")
        entry = {"path": str(item["path"]), "sha256": str(item["sha256"])}
        if "mode" in item:
            entry["mode"] = str(item["mode"])
        normalized.append(entry)
    normalized.sort(
        key=lambda item: (item["path"], item["sha256"], item.get("mode", ""))
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


def _module_origin(name: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(name)
    except ImportError:
        return {"available": False}
    raw = getattr(module, "__file__", None)
    result: dict[str, Any] = {"available": True}
    if not isinstance(raw, str):
        result["origin"] = "built_in_or_namespace"
        return result
    origin = Path(raw)
    for index, entry in enumerate(sys.path):
        if not entry:
            entry = os.getcwd()
        try:
            relative = origin.resolve().relative_to(Path(entry).resolve())
        except (OSError, ValueError):
            continue
        result.update(
            {
                "origin": relative.as_posix(),
                "sys_path_entry_index": index,
            }
        )
        break
    else:
        result["origin"] = origin.name
    if origin.is_file():
        result["origin_sha256"] = sha256_file(origin)
    return result


def _thread_pool_snapshot() -> list[dict[str, Any]]:
    pools: list[dict[str, Any]] = []
    for pool in threadpool_info():
        filepath = pool.get("filepath")
        pools.append(
            {
                "user_api": pool.get("user_api"),
                "internal_api": pool.get("internal_api"),
                "prefix": pool.get("prefix"),
                "version": pool.get("version"),
                "num_threads": pool.get("num_threads"),
                "library_filename": (
                    Path(str(filepath)).name if filepath is not None else None
                ),
            }
        )
    return sorted(
        pools,
        key=lambda item: (
            str(item["user_api"]),
            str(item["internal_api"]),
            str(item["prefix"]),
        ),
    )


@contextmanager
def enforced_numerical_threads(limit: int) -> Iterator[dict[str, Any]]:
    """Apply and verify the numerical thread limit for one execution scope."""

    if isinstance(limit, bool) or not isinstance(limit, int) or limit != 1:
        raise ValueError("numerical thread limit must be exactly one")
    evidence: dict[str, Any] = {"requested_limit": limit}
    with threadpool_limits(limits=limit):
        before = _thread_pool_snapshot()
        bad = [
            pool
            for pool in before
            if pool["user_api"] in {"blas", "openmp"} and pool["num_threads"] != limit
        ]
        if bad:
            raise RuntimeError(f"numerical thread limit was not enforced: {bad}")
        evidence["active_pools_before"] = before
        yield evidence
        after = _thread_pool_snapshot()
        bad = [
            pool
            for pool in after
            if pool["user_api"] in {"blas", "openmp"} and pool["num_threads"] != limit
        ]
        if bad:
            raise RuntimeError(f"numerical thread limit changed in scope: {bad}")
        evidence["active_pools_after"] = after
        evidence["verified"] = True


def runtime_metadata(
    *,
    workers: int,
    blas_threads: int,
    thread_control: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(blas_threads, bool) or not isinstance(blas_threads, int):
        raise ValueError("blas_threads must be exactly one")
    if blas_threads != 1:
        raise ValueError("blas_threads must be exactly one")
    return {
        "git": git_state(),
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable_name": Path(sys.executable).name,
            "executable_sha256": (
                sha256_file(sys.executable) if Path(sys.executable).is_file() else None
            ),
        },
        "packages": package_versions(
            (
                "numpy",
                "scipy",
                "scikit-learn",
                "pytest",
                "psutil",
                "threadpoolctl",
            )
        ),
        "module_origins": {
            name: _module_origin(name)
            for name in ("numpy", "scipy", "sklearn", "threadpoolctl")
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "logical_cpu_count": os.cpu_count(),
        },
        "execution": {
            "workers": int(workers),
            "blas_threads_per_worker": int(blas_threads),
            "thread_control": dict(thread_control or {}),
        },
    }


def source_inventory() -> list[dict[str, str]]:
    candidates = scientific_files(REPOSITORY_ROOT)
    inventory: list[dict[str, str]] = []
    for path in candidates:
        relative = path.relative_to(REPOSITORY_ROOT).as_posix()
        mode = source_path_mode(path)
        if mode == "120000" and relative not in ALLOWED_SCIENTIFIC_SYMLINKS:
            raise ValueError(
                f"unsafe scientific symlink is not allowlisted: {relative}"
            )
        inventory.append(
            {
                "path": relative,
                "sha256": sha256_source_path(path),
                "mode": mode,
            }
        )
    return inventory


def assert_source_inventory(expected: Sequence[Mapping[str, str]]) -> None:
    actual = source_inventory()
    normalized: list[dict[str, str]] = []
    for item in expected:
        if set(item) != {"path", "sha256", "mode"}:
            raise ValueError(
                "frozen source inventory must bind path, SHA-256, and mode"
            )
        normalized.append(
            {
                "path": str(item["path"]),
                "sha256": str(item["sha256"]),
                "mode": str(item["mode"]),
            }
        )
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
    "ALLOWED_SCIENTIFIC_SYMLINKS",
    "NONSCIENTIFIC_OUTPUT_PREFIXES",
    "SCIENTIFIC_BUCK_BASENAMES",
    "SCIENTIFIC_BUCK_EXACT_PATHS",
    "SCIENTIFIC_BUCK_PREFIXES",
    "SCIENTIFIC_EXACT_PATHS",
    "SCIENTIFIC_IMPORTABLE_SUFFIXES",
    "SCIENTIFIC_PREFIXES",
    "assert_source_inventory",
    "atomic_write_text",
    "canonical_json",
    "enforced_numerical_threads",
    "git_state",
    "input_set_sha256",
    "is_scientific_path",
    "package_versions",
    "reject_absolute_paths",
    "runtime_metadata",
    "sha256_bytes",
    "sha256_file",
    "sha256_source_path",
    "source_path_mode",
    "scientific_files",
    "source_inventory",
    "write_json",
]
