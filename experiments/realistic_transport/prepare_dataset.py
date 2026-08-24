"""Command-line entry point for one-time benchmark data preparation."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from .data import (
    canonical_json,
    DataPreparationError,
    prepare_covtype_artifact,
    prepare_digits_artifact,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare deterministic data for the realistic transport benchmark"
    )
    parser.add_argument("--dataset", choices=("covtype", "digits"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="external scikit-learn cache root; defaults to CCE_DATA_ROOT",
    )
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

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
                overwrite=args.overwrite,
            )
        else:
            manifest = prepare_digits_artifact(
                destination=args.output, overwrite=args.overwrite
            )
    except DataPreparationError as exc:
        parser.exit(2, f"data preparation failed: {exc}\n")
    print(canonical_json(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
