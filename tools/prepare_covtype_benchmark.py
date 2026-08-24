#!/usr/bin/env python3
"""Prepare a deterministic external dataset artifact for the benchmark."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.realistic_transport.prepare_dataset import main


if __name__ == "__main__":
    raise SystemExit(main())
