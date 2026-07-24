from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


REPOSITORY = Path(__file__).resolve().parents[1]
RAW_PREFIX = "results/raw/"


def _git(*args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_raw_results_are_absent_from_reachable_git_history() -> None:
    try:
        inside_work_tree = _git("rev-parse", "--is-inside-work-tree").strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("Git metadata is unavailable in this source archive")
    assert inside_work_tree == "true"

    reachable_raw_objects = [
        line
        for line in _git("rev-list", "--objects", "HEAD").splitlines()
        if " " in line and line.split(" ", 1)[1].startswith(RAW_PREFIX)
    ]
    raw_history = _git("log", "--format=%H", "HEAD", "--", RAW_PREFIX).splitlines()

    assert reachable_raw_objects == []
    assert raw_history == []
