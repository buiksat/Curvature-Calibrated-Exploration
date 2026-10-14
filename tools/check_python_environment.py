#!/usr/bin/env python3
"""Check the supported review-run interpreter and exact package versions offline."""
from __future__ import annotations

import argparse
from importlib import metadata
from pathlib import Path
import platform
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = ROOT / "experiments/requirements-python312.lock"


def read_pins(path: Path) -> dict[str, str]:
    """Read exact pins, rejecting ranges or malformed/duplicate dependency rows."""
    pins: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(
            r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)(?:\s+--hash=sha256:[0-9a-f]{64})?",
            line,
        )
        if not match:
            raise ValueError(f"{path.name}:{number}: expected one exact package pin")
        name = re.sub(r"[-_.]+", "-", match[1]).lower()
        if name in pins:
            raise ValueError(f"{path.name}:{number}: duplicate package {name}")
        pins[name] = match[2]
    if not pins:
        raise ValueError(f"{path.name}: dependency list is empty")
    return pins


def check_environment(lock_path: Path | None = None) -> list[str]:
    """Return actionable errors; an empty list means all declared versions match.

    This checks installed metadata, not the integrity of installed files. The
    installation step separately verifies wheel hashes with pip --require-hashes.
    """
    errors: list[str] = []
    if sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 12):
        errors.append("Use CPython 3.12 for the locked review environment.")
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        errors.append("The wheel lock supports Linux x86_64 only.")
    path = Path(lock_path) if lock_path is not None else DEFAULT_LOCK
    try:
        pins = read_pins(path)
        declared = read_pins(ROOT / "experiments/requirements.txt")
    except (OSError, ValueError) as exc:
        return errors + [f"Cannot validate dependency declarations: {exc}"]
    for name, version in declared.items():
        if pins.get(name) != version:
            errors.append(f"Lock must retain declared dependency {name}=={version}.")
    for name, version in pins.items():
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            errors.append(f"Missing {name}=={version}.")
            continue
        if installed != version:
            errors.append(f"Expected {name}=={version}; installed {installed}.")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    args = parser.parse_args(argv)
    errors = check_environment(args.lock)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: CPython 3.12 Linux x86_64; {len(read_pins(args.lock))} exact package pins match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
