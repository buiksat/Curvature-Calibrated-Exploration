"""Hermetic pytest entry point for the realistic-transport package."""

from __future__ import annotations

import sys

import pytest


if __name__ == "__main__":
    raise SystemExit(pytest.main(sys.argv[1:]))
