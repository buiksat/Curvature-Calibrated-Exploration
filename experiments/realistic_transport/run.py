"""Run one realistic-transport task/method/seed cell."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .study import run_profile


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("experiments/configs/realistic_transport_covtype.yaml"),
    )
    parser.add_argument(
        "--profile",
        choices=("smoke", "covtype_pilot", "resource_fallback", "full"),
        required=True,
    )
    parser.add_argument("--prepared-artifact", type=Path, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--phase", default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--selection", type=Path, default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    result = run_profile(
        config_path=args.config,
        profile=args.profile,
        prepared_artifact=args.prepared_artifact,
        output_root=args.output_root,
        selection_path=args.selection,
        phase=args.phase,
        methods=(args.method,),
        tasks=(args.task,),
        seeds=(args.seed,),
        overwrite=args.overwrite,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
