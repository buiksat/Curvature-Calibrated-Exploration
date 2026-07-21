"""Deterministic JSONL logging and reproducibility metadata collection."""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import random
import re
import subprocess
import sys
import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .config import config_digest


DEFAULT_PACKAGES = (
    "numpy",
    "scipy",
    "scikit-learn",
    "torch",
    "PyYAML",
)


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _timestamp(value: dt.datetime | str) -> str:
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    value = value.astimezone(dt.timezone.utc)
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json_value(value: Any, path: str = "$") -> Any:
    """Convert common scientific scalar/container values to strict JSON values."""

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _json_value(dataclasses.asdict(value), path)
    if isinstance(value, enum.Enum):
        return _json_value(value.value, path)
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite float at {path}")
        return value
    if isinstance(value, Mapping):
        converted: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"JSON object key at {path} is not a string: {key!r}")
            converted[key] = _json_value(item, f"{path}.{key}")
        return converted
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item, f"{path}[{index}]") for index, item in enumerate(value)]

    # NumPy scalars and arrays expose these without requiring NumPy here.
    item_method = getattr(value, "item", None)
    if callable(item_method):
        item = item_method()
        if item is not value:
            return _json_value(item, path)
    list_method = getattr(value, "tolist", None)
    if callable(list_method):
        return _json_value(list_method(), path)
    raise TypeError(f"unsupported JSON value at {path}: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Serialize a value deterministically, rejecting NaN and infinity."""

    return json.dumps(
        _json_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def append_jsonl(path: str | Path, record: Mapping[str, Any]) -> None:
    """Append one canonical record using an ``O_APPEND`` file descriptor."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = (canonical_json(record) + "\n").encode("utf-8")
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
    descriptor = os.open(destination, flags, 0o644)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written == 0:
                raise OSError(f"zero-byte write while appending {destination}")
            view = view[written:]
    finally:
        os.close(descriptor)


def _write_single_record(
    path: Path, record: Mapping[str, Any], *, overwrite: bool = False
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (canonical_json(record) + "\n").encode("utf-8")
    flags = os.O_CREAT | os.O_WRONLY | (os.O_TRUNC if overwrite else os.O_EXCL)
    descriptor = os.open(path, flags, 0o644)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written == 0:
                raise OSError(f"zero-byte write while writing {path}")
            view = view[written:]
    finally:
        os.close(descriptor)


def derive_seed(master_seed: int, *namespace: object) -> int:
    """Derive a stable 32-bit child seed without Python's randomized ``hash``."""

    if not isinstance(master_seed, int) or isinstance(master_seed, bool) or master_seed < 0:
        raise ValueError("master_seed must be a non-negative integer")
    payload = canonical_json([master_seed, *namespace]).encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def seed_everything(seed: int, *, include_optional: bool = True) -> dict[str, int]:
    """Seed stdlib and installed numerical backends, returning seeded backends."""

    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    seeded = {"python_random": seed}
    if not include_optional:
        return seeded

    if importlib.util.find_spec("numpy") is not None:
        import numpy as np

        numpy_seed = seed % (2**32)
        np.random.seed(numpy_seed)
        seeded["numpy"] = numpy_seed

    if importlib.util.find_spec("torch") is not None:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        if hasattr(torch, "use_deterministic_algorithms"):
            torch.use_deterministic_algorithms(True, warn_only=True)
        if hasattr(torch.backends, "cudnn"):
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True
        seeded["torch"] = seed
    return seeded


def collect_git_state(repository: str | Path | None = None) -> dict[str, Any]:
    """Collect the revision and dirty flag without modifying the repository."""

    cwd = Path(repository) if repository is not None else Path.cwd()

    def run(*arguments: str) -> str:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return completed.stdout.strip()

    try:
        revision = run("rev-parse", "HEAD")
        root = run("rev-parse", "--show-toplevel")
        dirty = bool(run("status", "--porcelain", "--untracked-files=normal"))
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return {"revision": "unknown", "dirty": None, "root": None}
    return {"revision": revision, "dirty": dirty, "root": root}


def collect_package_versions(
    packages: Sequence[str] | None = None,
) -> dict[str, str | None]:
    """Collect versions for an explicit, sorted dependency list."""

    names = DEFAULT_PACKAGES if packages is None else tuple(packages)
    versions: dict[str, str | None] = {}
    for name in sorted(set(names), key=str.casefold):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _physical_memory_bytes() -> int | None:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, OSError, ValueError):
        return None
    if not isinstance(page_size, int) or not isinstance(pages, int):
        return None
    return page_size * pages


def _nvidia_gpus() -> list[dict[str, str]]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return []
    gpus = []
    for line in result.stdout.splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) == 3:
            gpus.append(
                {"name": fields[0], "memory_mib": fields[1], "driver": fields[2]}
            )
    return gpus


def collect_hardware() -> dict[str, Any]:
    """Collect portable CPU, memory, OS, and visible accelerator metadata."""

    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "logical_cpu_count": os.cpu_count(),
        "physical_memory_bytes": _physical_memory_bytes(),
        "nvidia_gpus": _nvidia_gpus(),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }


def collect_run_metadata(
    *, repository: str | Path | None = None, packages: Sequence[str] | None = None
) -> dict[str, Any]:
    git = collect_git_state(repository)
    return {
        "git_revision": git["revision"],
        "git_dirty": git["dirty"],
        "git_root": git["root"],
        "package_versions": collect_package_versions(packages),
        "hardware": collect_hardware(),
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
    }


def _run_id(name: str, seed: int, timestamp: str, digest: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-") or "experiment"
    compact_time = re.sub(r"[^0-9]", "", timestamp)[:20]
    return f"{safe_name}-{compact_time}-s{seed}-{digest[:8]}"


class ExperimentLogger:
    """Write an immutable run manifest and ordered raw per-round metrics."""

    def __init__(
        self,
        output_dir: str | Path,
        config: Mapping[str, Any],
        seed: int,
        *,
        repository: str | Path | None = None,
        packages: Sequence[str] | None = None,
        metadata: Mapping[str, Any] | None = None,
        clock: Callable[[], dt.datetime | str] = _utc_now,
        run_id: str | None = None,
        overwrite: bool = False,
    ) -> None:
        if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
            raise ValueError("seed must be a non-negative integer")
        self.output_dir = Path(output_dir)
        self.manifest_path = self.output_dir / "manifest.jsonl"
        self.raw_path = self.output_dir / "raw.jsonl"
        self._clock = clock
        self._lock = threading.Lock()
        self._last_round = -1
        self._closed = False

        if not overwrite:
            existing = [
                str(path)
                for path in (self.manifest_path, self.raw_path)
                if path.exists()
            ]
            if existing:
                raise FileExistsError(
                    "refusing to append to an existing run: " + ", ".join(existing)
                )

        normalized_config = _json_value(config, "$.config")
        digest = config_digest(normalized_config)
        created_at = _timestamp(clock())
        name = str(normalized_config.get("name", "experiment"))
        self.run_id = run_id or _run_id(name, seed, created_at, digest)
        self.seed = seed

        if packages is None:
            provenance_config = normalized_config.get("provenance", {})
            declared_packages = (
                provenance_config.get("packages")
                if isinstance(provenance_config, Mapping)
                else None
            )
            if (
                isinstance(declared_packages, Sequence)
                and not isinstance(declared_packages, (str, bytes))
                and all(isinstance(package, str) for package in declared_packages)
            ):
                packages = tuple(declared_packages)

        provenance = (
            collect_run_metadata(repository=repository, packages=packages)
            if metadata is None
            else _json_value(metadata, "$.metadata")
        )
        required = {
            "git_revision",
            "git_dirty",
            "package_versions",
            "hardware",
            "python",
        }
        missing = required - set(provenance)
        if missing:
            raise ValueError(f"metadata is missing required keys: {sorted(missing)}")

        self.manifest = {
            "schema_version": 1,
            "event": "run_manifest",
            "run_id": self.run_id,
            "timestamp_utc": created_at,
            "seed": seed,
            "config_digest": digest,
            "config": normalized_config,
            **provenance,
        }
        self.output_dir.mkdir(parents=True, exist_ok=True)
        _write_single_record(self.manifest_path, self.manifest, overwrite=overwrite)
        if overwrite:
            self.raw_path.write_text("", encoding="utf-8")
        else:
            descriptor = os.open(self.raw_path, os.O_CREAT | os.O_EXCL, 0o644)
            os.close(descriptor)

    def log_round(
        self,
        round_index: int,
        metrics: Mapping[str, Any] | None = None,
        **metric_values: Any,
    ) -> dict[str, Any]:
        """Append one round after validating order and strict JSON values."""

        if not isinstance(round_index, int) or isinstance(round_index, bool):
            raise TypeError("round_index must be an integer")
        if round_index < 0:
            raise ValueError("round_index must be non-negative")
        values = {} if metrics is None else dict(metrics)
        duplicates = set(values) & set(metric_values)
        if duplicates:
            raise ValueError(f"duplicate metric names: {sorted(duplicates)}")
        values.update(metric_values)
        normalized_metrics = _json_value(values, "$.metrics")

        with self._lock:
            if self._closed:
                raise RuntimeError("logger is closed")
            if round_index <= self._last_round:
                raise ValueError(
                    f"rounds must increase strictly: {round_index} <= {self._last_round}"
                )
            record = {
                "schema_version": 1,
                "event": "round",
                "run_id": self.run_id,
                "seed": self.seed,
                "round": round_index,
                "timestamp_utc": _timestamp(self._clock()),
                "metrics": normalized_metrics,
            }
            append_jsonl(self.raw_path, record)
            self._last_round = round_index
        return record

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def __enter__(self) -> "ExperimentLogger":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


RunLogger = ExperimentLogger


__all__ = [
    "ExperimentLogger",
    "RunLogger",
    "append_jsonl",
    "canonical_json",
    "collect_git_state",
    "collect_hardware",
    "collect_package_versions",
    "collect_run_metadata",
    "derive_seed",
    "seed_everything",
]
