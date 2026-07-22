"""Opaque pytest entry point used by Buck2 shell-test wrappers."""

from __future__ import annotations

import sys

import pytest


if __name__ == "__main__":
    raise SystemExit(pytest.main(sys.argv[1:]))
