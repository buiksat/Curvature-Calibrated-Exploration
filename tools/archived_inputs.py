"""Read retired inputs from the pinned pre-cleanup Git commit.

Current scientific inputs never use this fallback. Historical checks opt in
explicitly, and existing files are checked as supplied rather than replaced.
Extracted originals live only in a temporary directory outside the checkout.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tempfile

ARCHIVE_COMMIT = "ea33d2fc4f93ac831dfe7ae31fa3cfdc114cba42"
ARCHIVE_TAG = "archive/research-before-tmlr-cleanup-2026-11-12"
_EXTRACTIONS: dict[Path, tempfile.TemporaryDirectory] = {}
_VALIDATED: dict[tuple[Path, str], int] = {}


def archive_records(root: Path) -> dict[str, dict]:
    manifest = json.loads((root / "ARCHIVED_FILES.json").read_text())
    if manifest.get("archive_commit") != ARCHIVE_COMMIT:
        raise ValueError("archive manifest does not name the pinned commit")
    records = {entry["path"]: entry for entry in manifest["files"]}
    if len(records) != len(manifest["files"]):
        raise ValueError("duplicate archived path")
    for name in records:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or str(path) != name:
            raise ValueError(f"invalid archived path: {name}")
    return records


def validate_archive(root: Path) -> int:
    """Check the entire retirement inventory against the immutable Git tree."""
    identity = (root.resolve(), hashlib.sha256(
        (root / "ARCHIVED_FILES.json").read_bytes()).hexdigest())
    if identity in _VALIDATED:
        return _VALIDATED[identity]
    records = archive_records(root)
    result = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-rl", ARCHIVE_COMMIT],
        check=True, capture_output=True, text=True,
    )
    original = {}
    for row in result.stdout.splitlines():
        metadata, name = row.split("\t", 1)
        mode, kind, blob, size = metadata.split()
        if kind == "blob":
            original[name] = (mode, blob, int(size))
    for name, entry in records.items():
        if original.get(name) != (entry["mode"], entry["git_blob"], entry["bytes"]):
            raise ValueError(f"archive inventory differs from pinned tree: {name}")
    objects = subprocess.run(
        ["git", "-C", str(root), "cat-file", "--batch"],
        input="".join(row["git_blob"] + "\n" for row in records.values()).encode(),
        check=True, capture_output=True,
    ).stdout
    offset = 0
    for name, entry in records.items():
        end = objects.index(b"\n", offset)
        blob, kind, size = objects[offset:end].decode().split()
        size = int(size)
        data = objects[end + 1:end + 1 + size]
        offset = end + size + 2
        if (blob != entry["git_blob"] or kind != "blob"
                or len(data) != entry["bytes"]
                or hashlib.sha256(data).hexdigest() != entry["sha256"]):
            raise ValueError(f"archive SHA-256 inventory mismatch: {name}")
    _VALIDATED[identity] = len(records)
    return len(records)


def archived_input(root: Path, relative: str | Path) -> Path:
    """Return an existing input or authenticate and extract a retired original."""
    root = root.resolve()
    name = str(relative)
    current = root / name
    if current.exists() or current.is_symlink():
        return current
    records = archive_records(root)
    if name not in records:
        raise FileNotFoundError(f"not a retired input: {name}")
    validate_archive(root)
    if root not in _EXTRACTIONS:
        _EXTRACTIONS[root] = tempfile.TemporaryDirectory(prefix="cce-archived-inputs-")
    temporary = _EXTRACTIONS[root]
    # PDF manifests refer to sibling audit artifacts. Restore that complete
    # closure together, retaining every original byte and manifest check.
    names = ([p for p in records if p.startswith("review/transport_instantiation/pdf/")]
             if name.startswith("review/transport_instantiation/pdf/") else [name])
    for item in names:
        record = records[item]
        if record["mode"] not in ("100644", "100755"):
            raise ValueError(f"archived input is not a regular file: {item}")
        destination = Path(temporary.name) / item
        if not destination.exists():
            data = subprocess.run(
                ["git", "-C", str(root), "show", f"{ARCHIVE_COMMIT}:{item}"],
                check=True, capture_output=True,
            ).stdout
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        data = destination.read_bytes()
        if (len(data) != record["bytes"]
                or hashlib.sha256(data).hexdigest() != record["sha256"]):
            raise ValueError(f"archived bytes fail integrity checks: {item}")
    return Path(temporary.name) / name


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    print(f"Verified {validate_archive(root)} retired paths at {ARCHIVE_COMMIT}")
