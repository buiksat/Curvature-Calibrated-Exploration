"""Command-line entry point for one-time benchmark data preparation."""

from __future__ import annotations

import argparse
import importlib
import os
import platform
from collections.abc import Sequence
from pathlib import Path

from .data import (
    canonical_json,
    DataPreparationError,
    prepare_covtype_artifact,
    prepare_digits_artifact,
)


def _runtime_info() -> dict[str, object]:
    modules: dict[str, object] = {}
    for name in ("numpy", "scipy", "sklearn", "threadpoolctl"):
        module = importlib.import_module(name)
        modules[name] = {
            "version": str(getattr(module, "__version__", "unknown")),
            "origin": str(getattr(module, "__file__", "unknown")),
        }
    return {
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "modules": modules,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare deterministic data for the realistic transport benchmark"
    )
    parser.add_argument("--runtime-info", action="store_true")
    parser.add_argument("--dataset", choices=("covtype", "digits"), default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="external scikit-learn cache root; defaults to CCE_DATA_ROOT",
    )
    parser.add_argument("--no-download", action="store_true")
    args = parser.parse_args(argv)

    if args.runtime_info:
        print(canonical_json(_runtime_info()))
        return 0
    if args.dataset is None or args.output is None:
        parser.error(
            "--dataset and --output are required unless --runtime-info is used"
        )

    try:
        if args.dataset == "covtype":
            data_root = args.data_root
            if data_root is None:
                value = os.environ.get("CCE_DATA_ROOT")
                if not value:
                    parser.error(
                        "Covertype preparation requires --data-root or CCE_DATA_ROOT"
                    )
                data_root = Path(value)
            manifest = prepare_covtype_artifact(
                cache_root=data_root,
                destination=args.output,
                download_if_missing=not args.no_download,
            )
        else:
            manifest = prepare_digits_artifact(destination=args.output)
    except DataPreparationError as exc:
        parser.exit(2, f"data preparation failed: {exc}\n")
    print(canonical_json(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
