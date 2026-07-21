"""Build the preregistered curvature-mechanism phase-diagram artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .aggregate_results import (
    validate_aggregate_provenance_sidecar,
    write_aggregate_with_provenance,
)
from .curvature_phase_diagram import build_artifact
from .logging_utils import canonical_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("configs")
        / "curvature_phase_diagram.yaml",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--derived-report", type=Path)
    parser.add_argument("--write-round-records", action="store_true")
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not an object")
            records.append(value)
    return records


def write_compact_report(
    raw_dir: str | Path,
    report_path: str | Path,
    *,
    config_path: str | Path,
) -> tuple[Path, Path]:
    raw = Path(raw_dir)
    report = Path(report_path)
    sidecar = report.with_suffix(report.suffix + ".provenance.json")
    if report.exists() or sidecar.exists():
        raise FileExistsError("refusing to overwrite derived report or provenance")
    manifest = json.loads((raw / "manifest.json").read_text(encoding="utf-8"))
    preregistration = json.loads(
        (raw / "preregistered_grid.json").read_text(encoding="utf-8")
    )
    aggregates = _read_jsonl(raw / "aggregates.jsonl")
    paired = _read_jsonl(raw / "paired_full_comparisons.jsonl")
    repository = Path(__file__).resolve().parents[1]

    def release_path(path: Path) -> str:
        resolved = path.resolve()
        if not resolved.is_relative_to(repository):
            raise ValueError(f"provenance input is outside the repository: {path}")
        return resolved.relative_to(repository).as_posix()

    input_paths = [path for path in raw.iterdir() if path.is_file()]
    input_paths.append(Path(config_path))
    inputs = sorted(
        (
            {"path": release_path(path), "sha256": _sha256(path)}
            for path in input_paths
        ),
        key=lambda item: item["path"],
    )
    input_set_sha256 = hashlib.sha256(
        canonical_json(inputs).encode("ascii")
    ).hexdigest()
    compact = {
        "schema_version": 1,
        "study": "curvature_mechanism_phase_diagram",
        "interpretation": (
            "Preregistered fixed-gap bounded-linear mechanism map. Online regret "
            "comes from independent policies; common-trajectory metrics are offline."
        ),
        "fixed_optimal_action": "arm_0_by_design",
        "general_contextual_benchmark": False,
        "evaluation_cell_selection": "none",
        "full_win_search": False,
        "preregistered_grid": preregistration,
        "run_manifest": manifest,
        "aggregates": aggregates,
        "paired_full_comparisons": paired,
        "inputs": inputs,
        "input_set_sha256": input_set_sha256,
    }
    report, sidecar = write_aggregate_with_provenance(compact, report)
    provenance = json.loads(sidecar.read_text(encoding="utf-8"))
    provenance.update(
        {
            "artifact_bytes": report.stat().st_size,
            "input_count": len(inputs),
            "round_files_included": all(
                (raw / name).is_file()
                for name in ("online_rounds.jsonl", "common_trajectory_rounds.jsonl")
            ),
            "binding": (
                "SHA-256 binds config, raw manifest, preregistered grid, summaries, "
                "aggregates, paired comparisons, and round records."
            ),
        }
    )
    sidecar.write_text(canonical_json(provenance) + "\n", encoding="utf-8")
    validate_aggregate_provenance_sidecar(report, sidecar)
    return report, sidecar


def main() -> None:
    args = _parser().parse_args()
    manifest = build_artifact(
        args.config,
        args.output,
        write_round_records=True if args.write_round_records else None,
    )
    if args.derived_report is not None:
        report, sidecar = write_compact_report(
            args.output,
            args.derived_report,
            config_path=args.config,
        )
        manifest = {
            **manifest,
            "derived_report": str(report),
            "derived_report_provenance": str(sidecar),
        }
    print(canonical_json(manifest))


if __name__ == "__main__":
    main()
