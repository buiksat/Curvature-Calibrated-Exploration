"""Deterministic raw-run and derived-artifact I/O."""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
import traceback
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .provenance import (
    atomic_write_text,
    canonical_json,
    reject_absolute_paths,
    REPOSITORY_ROOT,
    sha256_file,
    write_json,
)


RUN_FILES = ("manifest.json", "rounds.jsonl", "summary.json")
EVIDENCE_FILES = (*RUN_FILES, "failure.json")


def utc_timestamp() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def run_directory(
    root: str | Path,
    *,
    phase: str,
    task: str,
    method: str,
    seed: int,
) -> Path:
    return Path(root) / str(phase) / str(task) / str(method) / f"seed-{int(seed)}"


def existing_run_outputs(directory: str | Path) -> tuple[Path, ...]:
    root = Path(directory)
    candidates = tuple(
        path
        for name in EVIDENCE_FILES
        for path in (root / name, root / f"{name}.sha256")
    )
    return tuple(path for path in candidates if path.exists() or path.is_symlink())


def refuse_existing_run_outputs(directory: str | Path) -> None:
    present = existing_run_outputs(directory)
    if present:
        raise FileExistsError(
            f"refusing to overwrite run files: {[str(path) for path in present]}"
        )


def _prepare(directory: Path, *, overwrite: bool) -> None:
    present = existing_run_outputs(directory)
    if present and not overwrite:
        raise FileExistsError(
            f"refusing to overwrite run files: {[str(path) for path in present]}"
        )
    if overwrite:
        for name in EVIDENCE_FILES:
            path = directory / name
            path.unlink(missing_ok=True)
            path.with_name(path.name + ".sha256").unlink(missing_ok=True)
    directory.mkdir(parents=True, exist_ok=True)


def _write_run(
    directory: str | Path,
    *,
    manifest: Mapping[str, Any],
    rounds: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    overwrite: bool,
) -> dict[str, str]:
    destination = Path(directory)
    _prepare(destination, overwrite=overwrite)
    for value in (manifest, rounds, summary):
        reject_absolute_paths(value)
    manifest_path, manifest_sha = write_json(destination / "manifest.json", manifest)
    rounds_path = atomic_write_text(
        destination / "rounds.jsonl",
        "".join(canonical_json(record) + "\n" for record in rounds),
    )
    rounds_sha = rounds_path.with_name(rounds_path.name + ".sha256")
    atomic_write_text(rounds_sha, f"{sha256_file(rounds_path)}  {rounds_path.name}\n")
    summary_path, summary_sha = write_json(destination / "summary.json", summary)
    return {
        "manifest": str(manifest_path),
        "manifest_sha256": str(manifest_sha),
        "rounds": str(rounds_path),
        "rounds_sha256": str(rounds_sha),
        "summary": str(summary_path),
        "summary_sha256": str(summary_sha),
    }


def write_run(
    directory: str | Path,
    *,
    manifest: Mapping[str, Any],
    rounds: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> dict[str, str]:
    """Write a new production cell, refusing every existing evidence file."""

    return _write_run(
        directory,
        manifest=manifest,
        rounds=rounds,
        summary=summary,
        overwrite=False,
    )


def _rewrite_run_fixture(
    directory: str | Path,
    *,
    manifest: Mapping[str, Any],
    rounds: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> dict[str, str]:
    """Rewrite a disposable test fixture located under the host temp root."""

    destination = Path(directory).resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    try:
        destination.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("fixture rewrites cannot target the repository")
    try:
        destination.relative_to(temporary_root)
    except ValueError as error:
        raise ValueError(
            "fixture rewrites are restricted to the host temp root"
        ) from error
    return _write_run(
        destination,
        manifest=manifest,
        rounds=rounds,
        summary=summary,
        overwrite=True,
    )


def write_failure(
    directory: str | Path,
    *,
    context: Mapping[str, Any],
    error: BaseException,
) -> Path:
    destination = Path(directory)
    _prepare(destination, overwrite=False)
    record = {
        "schema_version": 1,
        "event": "realistic_transport_failure",
        "recorded_at": utc_timestamp(),
        "status": "failed",
        "context": dict(context),
        "error_type": type(error).__name__,
        "error": str(error),
        "traceback": traceback.format_exception(
            type(error), error, error.__traceback__
        ),
    }
    reject_absolute_paths(record["context"])
    path, _ = write_json(destination / "failure.json", record)
    return path


def read_json(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object at {path}")
    return value


def validate_run_directory(directory: str | Path) -> dict[str, Any]:
    root = Path(directory)
    for name in RUN_FILES:
        path = root / name
        if not path.is_file():
            raise ValueError(f"missing run file {path}")
        fields = (
            path.with_name(path.name + ".sha256").read_text(encoding="ascii").split()
        )
        if len(fields) != 2 or fields[1] != path.name:
            raise ValueError(f"malformed SHA-256 sidecar for {path}")
        if fields[0] != sha256_file(path):
            raise ValueError(f"SHA-256 mismatch for {path}")
    manifest = read_json(root / "manifest.json")
    summary = read_json(root / "summary.json")
    round_count = 0
    with (root / "rounds.jsonl").open(encoding="ascii") as handle:
        for expected_round, line in enumerate(handle, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSONL in {root}: {error}") from error
            if not isinstance(record, dict) or record.get("round") != expected_round:
                raise ValueError(f"invalid round sequence in {root}")
            round_count = expected_round
    if summary.get("rounds") != round_count:
        raise ValueError(f"summary round count mismatch in {root}")
    return {"manifest": manifest, "summary": summary, "round_count": round_count}


__all__ = [
    "EVIDENCE_FILES",
    "RUN_FILES",
    "existing_run_outputs",
    "read_json",
    "refuse_existing_run_outputs",
    "run_directory",
    "utc_timestamp",
    "validate_run_directory",
    "write_failure",
    "write_run",
]
