"""Deterministic standalone artifacts for realistic transport evidence."""

from __future__ import annotations

import argparse
import csv
import ctypes
import errno
import io
import json
import os
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .aggregate import publication_eligibility, validate_and_aggregate_profile
from .configuration import load_config, profile_policy
from .provenance import (
    atomic_write_text,
    canonical_json,
    REPOSITORY_ROOT,
    sha256_file,
    write_json,
)


def _refuse_existing_artifacts(root: Path) -> None:
    if root.exists() or root.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing evidence root: {root}")


def _publish_directory_no_replace(source: Path, destination: Path) -> None:
    """Atomically publish a same-filesystem directory without replacement."""

    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise OSError(errno.ENOSYS, "renameat2 is unavailable")
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    result = renameat2(
        -100,
        os.fsencode(source),
        -100,
        os.fsencode(destination),
        1,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise FileExistsError(
            error_number,
            f"refusing to overwrite existing evidence root: {destination}",
            str(destination),
        )
    raise OSError(
        error_number,
        f"renameat2(RENAME_NOREPLACE) failed for {destination}",
        str(destination),
    )


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise ValueError(f"aggregate has duplicate JSON key {key!r}")
        value[key] = child
    return value


def _load(path: str | Path) -> tuple[dict[str, Any], str]:
    aggregate_path = Path(path)
    digest = sha256_file(aggregate_path)
    sidecar_path = aggregate_path.with_name(aggregate_path.name + ".sha256")
    try:
        sidecar = sidecar_path.read_text(encoding="ascii").split()
    except OSError as error:
        raise ValueError(f"cannot read aggregate sidecar: {error}") from error
    if sidecar != [digest, aggregate_path.name]:
        raise ValueError("aggregate SHA-256 sidecar is invalid")
    try:
        value = json.loads(
            aggregate_path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ValueError(f"aggregate contains non-finite JSON value {constant}")
            ),
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read aggregate: {error}") from error
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("aggregate has an unsupported schema")
    return value, digest


def _validate_accepted_aggregate(
    *,
    aggregate_path: str | Path,
    config_path: str | Path,
    profile: str,
    raw_root: str | Path,
    selection_path: str | Path | None,
    data_lock_path: str | Path | None,
    freeze_revision: str | None,
    selection_lock_revision: str | None,
    repository_root: str | Path,
) -> tuple[dict[str, Any], str]:
    supplied, aggregate_sha256 = _load(aggregate_path)
    if supplied.get("profile") != profile:
        raise ValueError("aggregate profile does not match the requested profile")
    expected = validate_and_aggregate_profile(
        config_path=config_path,
        profile=profile,
        raw_root=raw_root,
        selection_path=selection_path,
        data_lock_path=data_lock_path,
        freeze_revision=freeze_revision,
        selection_lock_revision=selection_lock_revision,
        repository_root=repository_root,
    )
    serialized_expected = json.loads(canonical_json(expected))
    if supplied != serialized_expected:
        raise ValueError(
            "aggregate does not match the independently validated raw grid"
        )
    expected = serialized_expected

    config = load_config(config_path, profile)
    policy = profile_policy(config, profile)
    common = expected.get("common_provenance")
    semantic = expected.get("semantic_status")
    if not isinstance(common, Mapping) or not isinstance(semantic, Mapping):
        raise ValueError("accepted aggregate lacks validated provenance or status")
    prepared = common.get("prepared_data")
    if not isinstance(prepared, Mapping):
        raise ValueError("accepted aggregate lacks prepared-data identity")
    authentication = common.get("data_authentication")
    data_authorized = bool(
        policy.requires_data_lock
        and isinstance(authentication, Mapping)
        and authentication.get("status") == "verified_against_committed_freeze_lock"
    )
    selection_authorized = bool(
        policy.requires_selection_lock
        and isinstance(common.get("selection_artifact_sha256"), str)
        and common.get("selection_lock_revision") == selection_lock_revision
    )
    deterministic_failures = semantic.get("deterministic_failure_count")
    if isinstance(deterministic_failures, bool) or not isinstance(
        deterministic_failures, int
    ):
        raise ValueError("accepted aggregate has invalid deterministic failure count")
    eligible = publication_eligibility(
        profile=profile,
        phase=policy.phase,
        evidence_role=policy.evidence_role,
        prepared_data=prepared,
        data_authorized=data_authorized,
        selection_authorized=selection_authorized,
        deterministic_failure_count=deterministic_failures,
    )
    if expected.get("publication_evidence") is not eligible:
        raise ValueError("aggregate publication eligibility does not recompute")

    tasks = expected.get("tasks")
    methods = expected.get("methods")
    seeds = expected.get("seeds")
    prefixes = expected.get("prefixes")
    if not all(
        isinstance(value, list) and value for value in (tasks, methods, seeds, prefixes)
    ):
        raise ValueError("accepted aggregate has an incomplete declared grid")
    expected_cells = len(tasks) * len(methods) * len(seeds)
    if (
        expected.get("expected_cell_count") != expected_cells
        or expected.get("accepted_cell_count") != expected_cells
        or len(expected.get("run_level_metrics", ())) != expected_cells * len(prefixes)
        or len(expected.get("method_statistics", ()))
        != len(tasks) * len(methods) * len(prefixes)
    ):
        raise ValueError("accepted aggregate grid is incomplete")
    return expected, aggregate_sha256


def _write_csv(
    path: Path,
    fields: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field) for field in fields})
    destination = atomic_write_text(path, output.getvalue())
    atomic_write_text(
        destination.with_name(destination.name + ".sha256"),
        f"{sha256_file(destination)}  {destination.name}\n",
    )


def _metric(cell: Mapping[str, Any], name: str, statistic: str = "mean") -> Any:
    value = cell["metrics"].get(name)
    return None if value is None else value.get(statistic)


def _method_rows(aggregate: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell in aggregate["method_statistics"]:
        rows.append(
            {
                "task": cell["task"],
                "method": cell["method"],
                "prefix": cell["prefix"],
                "seed_count": cell["seed_count"],
                "regret_mean": _metric(cell, "cumulative_regret"),
                "regret_se": _metric(cell, "cumulative_regret", "standard_error"),
                "regret_median": _metric(cell, "cumulative_regret", "median"),
                "runtime_mean_seconds": _metric(cell, "algorithm_seconds"),
                "memory_mean_bytes": _metric(cell, "peak_rss_bytes"),
                "reference_coverage": cell["reference_confidence"]["proportion"],
                "reference_coverage_low": cell["reference_confidence"][
                    "clopper_pearson_95"
                ]["ci_low"],
                "reference_coverage_high": cell["reference_confidence"][
                    "clopper_pearson_95"
                ]["ci_high"],
                "optimism": cell["method_optimism"]["proportion"],
                "optimism_low": cell["method_optimism"]["clopper_pearson_95"]["ci_low"],
                "optimism_high": cell["method_optimism"]["clopper_pearson_95"][
                    "ci_high"
                ],
            }
        )
    return rows


def _selected_run_rows(
    aggregate: Mapping[str, Any], predicate: Callable[[Mapping[str, Any]], bool]
) -> list[dict[str, Any]]:
    return [dict(row) for row in aggregate["run_level_metrics"] if predicate(row)]


def _write_publication_data(aggregate: Mapping[str, Any], root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    method_rows = _method_rows(aggregate)
    common = ("task", "method", "prefix", "seed_count")
    _write_csv(
        root / "cumulative_regret_curves.csv",
        (*common, "regret_mean", "regret_se", "regret_median"),
        method_rows,
    )
    maximum = int(max(aggregate["prefixes"]))
    final_rows = [row for row in method_rows if int(row["prefix"]) == maximum]
    _write_csv(
        root / "runtime_regret_pareto.csv",
        ("task", "method", "seed_count", "regret_mean", "runtime_mean_seconds"),
        final_rows,
    )
    _write_csv(
        root / "memory_regret_pareto.csv",
        ("task", "method", "seed_count", "regret_mean", "memory_mean_bytes"),
        final_rows,
    )
    _write_csv(
        root / "confidence_optimism.csv",
        (
            "task",
            "method",
            "seed_count",
            "reference_coverage",
            "reference_coverage_low",
            "reference_coverage_high",
            "optimism",
            "optimism_low",
            "optimism_high",
        ),
        final_rows,
    )

    run_rows = aggregate["run_level_metrics"]
    diagnostic_specs = {
        "path_vs_endpoint.csv": (
            (
                "task",
                "method",
                "seed",
                "prefix",
                "D_Q_minus_d_Th",
                "D_Q_over_d_Th",
                "D_Q_over_d_Th_zero_denominators",
            ),
            lambda row: row.get("D_Q_minus_d_Th") is not None,
        ),
        "operator_tail_kappa.csv": (
            (
                "task",
                "method",
                "seed",
                "prefix",
                "trace_tail_over_operator_tail",
                "kappa_minus",
                "oracle_kappa_minus",
            ),
            lambda row: row.get("trace_tail_over_operator_tail") is not None,
        ),
        "certified_width_inflation.csv": (
            (
                "task",
                "method",
                "seed",
                "prefix",
                "width_upper_over_exact",
                "solver_upper_over_exact_A",
                "exact_A_width_over_exact_V_width",
                "operational_upper_width_over_exact_V_width",
                "solver_upper_over_exact_A_zero_denominators",
                "exact_A_width_over_exact_V_width_zero_denominators",
                "operational_upper_width_over_exact_V_width_zero_denominators",
                "solver_alpha",
                "cg_iterations",
                "cg_matvecs",
            ),
            lambda row: row.get("width_upper_over_exact") is not None,
        ),
        "theorem_bound_nonvacuity.csv": (
            (
                "task",
                "method",
                "seed",
                "prefix",
                "cumulative_regret",
                "sharp_theorem_rhs",
                "trivial_regret_bound",
                "theorem_bound_nonvacuous",
                "zero_regret",
            ),
            lambda row: row.get("theorem_bound_nonvacuous") is not None,
        ),
        "controlled_misspecification_decomposition.csv": (
            (
                "task",
                "method",
                "seed",
                "prefix",
                "historical_misspecification_envelope",
                "current_misspecification_envelope",
            ),
            lambda row: row["task"] == "covtype_semisynthetic_misspecified",
        ),
        "real_label_baseline_comparison.csv": (
            (
                "task",
                "method",
                "seed",
                "prefix",
                "cumulative_regret",
                "action_accuracy",
                "algorithm_seconds",
                "peak_rss_bytes",
            ),
            lambda row: row["task"] == "covtype_label_bandit",
        ),
    }
    for name, (fields, predicate) in diagnostic_specs.items():
        _write_csv(root / name, fields, _selected_run_rows(aggregate, predicate))

    source_hash = aggregate["raw_input_inventory_sha256"]
    latex = """% Deterministic standalone PGFPlots input.
% Raw aggregate inventory SHA-256: {source_hash}
\\begin{{tikzpicture}}
\\begin{{axis}}[
  xlabel={{Round}}, ylabel={{Mean cumulative pseudo-regret}},
  legend style={{font=\\scriptsize}},
]
% Choose a task/method by filtering cumulative_regret_curves.csv before inclusion.
\\addplot table [x=prefix,y=regret_mean,col sep=comma] {{cumulative_regret_curves.csv}};
\\end{{axis}}
\\end{{tikzpicture}}
""".format(
        source_hash=source_hash
    )
    destination = atomic_write_text(root / "cumulative_regret_plot.tex", latex)
    atomic_write_text(
        destination.with_name(destination.name + ".sha256"),
        f"{sha256_file(destination)}  {destination.name}\n",
    )
    readme = """# Realistic transport publication-artifact data

These deterministic CSV files derive from one accepted aggregate. The
aggregate input inventory SHA-256 is `{source_hash}`. A file from a smoke or
pilot profile is engineering evidence only and must not be cited as Covertype
publication evidence.
""".format(
        source_hash=source_hash
    )
    destination = atomic_write_text(root / "README.md", readme)
    atomic_write_text(
        destination.with_name(destination.name + ".sha256"),
        f"{sha256_file(destination)}  {destination.name}\n",
    )


def _results_markdown(aggregate: Mapping[str, Any]) -> str:
    maximum = int(max(aggregate["prefixes"]))
    final = [
        cell
        for cell in aggregate["method_statistics"]
        if int(cell["prefix"]) == maximum
    ]
    lines = [
        "# Realistic confidence-transport benchmark results",
        "",
        f"Profile: `{aggregate['profile']}`",
        "",
        f"Accepted cells: {aggregate['accepted_cell_count']} / {aggregate['expected_cell_count']}",
        "",
        f"Raw-input inventory SHA-256: `{aggregate['raw_input_inventory_sha256']}`",
        "",
    ]
    semantic = aggregate.get("semantic_status", {})
    lines.extend(
        [
            f"Deterministic failures: {int(semantic.get('deterministic_failure_count', 0))}",
            "",
            f"Float64 diagnostic failures: {int(semantic.get('float64_diagnostic_failure_count', 0))}",
            "",
            "Theorem-event bound violations: "
            f"{int(semantic.get('instantaneous_theorem_event_violation_count', 0))} instantaneous, "
            f"{int(semantic.get('cumulative_theorem_event_violation_count', 0))} cumulative",
            "",
        ]
    )
    if not aggregate["publication_evidence"]:
        reason = (
            "The full grid contains a deterministic execution failure."
            if aggregate.get("profile") == "full"
            and int(semantic.get("deterministic_failure_count", 0)) > 0
            else "This profile is smoke, tuning, pilot, fallback, or fixture evidence."
        )
        lines.extend([f"This result is not publication evidence. {reason}", ""])
    lines.extend(
        [
            "| Task | Method | n | Mean regret | SE | Coverage | Optimism | Algorithm s | Peak MiB |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for cell in final:
        regret = cell["metrics"]["cumulative_regret"]
        runtime = cell["metrics"]["algorithm_seconds"]
        memory = cell["metrics"]["peak_rss_bytes"]
        lines.append(
            "| {task} | {method} | {n} | {regret:.6g} | {se:.3g} | {coverage:.3f} | {optimism:.3f} | {runtime:.4g} | {memory:.2f} |".format(
                task=cell["task"],
                method=cell["method"],
                n=cell["seed_count"],
                regret=float(regret["mean"]),
                se=float(regret["standard_error"]),
                coverage=float(cell["reference_confidence"]["proportion"]),
                optimism=float(cell["method_optimism"]["proportion"]),
                runtime=float(runtime["mean"]),
                memory=float(memory["mean"]) / (1024.0 * 1024.0),
            )
        )
    lines.extend(
        [
            "",
            "Float64 residual and Loewner checks are exact-arithmetic certificate "
            "diagnostics, not verified numerical certificates.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_validated_artifacts(
    aggregate: Mapping[str, Any],
    root: Path,
    *,
    accepted_aggregate_sha256: str,
) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    results = atomic_write_text(root / "RESULTS.md", _results_markdown(aggregate))
    atomic_write_text(
        results.with_name(results.name + ".sha256"),
        f"{sha256_file(results)}  {results.name}\n",
    )
    statistical = {
        "schema_version": 1,
        "profile": aggregate["profile"],
        "publication_evidence": aggregate["publication_evidence"],
        "accepted_aggregate_sha256": accepted_aggregate_sha256,
        "raw_input_inventory_sha256": aggregate["raw_input_inventory_sha256"],
        "method_statistics": aggregate["method_statistics"],
        "paired_primary_comparisons": aggregate["paired_primary_comparisons"],
        "controlled_task_secondary_comparisons": aggregate.get(
            "controlled_task_secondary_comparisons", []
        ),
        "rank_tolerance_effects": aggregate["rank_tolerance_effects"],
        "semantic_status": aggregate.get("semantic_status", {}),
    }
    write_json(root / "STATISTICAL_RESULTS.json", statistical)
    provenance = {
        "schema_version": 1,
        "profile": aggregate["profile"],
        "publication_evidence": aggregate["publication_evidence"],
        "accepted_aggregate_sha256": accepted_aggregate_sha256,
        "config_digest": aggregate["config_digest"],
        "common_provenance": aggregate["common_provenance"],
        "raw_input_inventory_sha256": aggregate["raw_input_inventory_sha256"],
        "raw_input_count": len(aggregate["raw_input_inventory"]),
    }
    write_json(root / "DATA_PROVENANCE.json", provenance)
    _write_publication_data(aggregate, root / "publication_artifacts")
    return {
        "results_sha256": sha256_file(root / "RESULTS.md"),
        "statistics_sha256": sha256_file(root / "STATISTICAL_RESULTS.json"),
        "data_provenance_sha256": sha256_file(root / "DATA_PROVENANCE.json"),
    }


def generate_artifacts(
    *,
    aggregate_path: str | Path,
    review_root: str | Path,
    config_path: str | Path,
    profile: str,
    raw_root: str | Path,
    selection_path: str | Path | None = None,
    data_lock_path: str | Path | None = None,
    freeze_revision: str | None = None,
    selection_lock_revision: str | None = None,
    repository_root: str | Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    """Render only an aggregate reproduced from authenticated raw inputs."""

    root = Path(review_root)
    _refuse_existing_artifacts(root)
    aggregate, aggregate_sha256 = _validate_accepted_aggregate(
        aggregate_path=aggregate_path,
        config_path=config_path,
        profile=profile,
        raw_root=raw_root,
        selection_path=selection_path,
        data_lock_path=data_lock_path,
        freeze_revision=freeze_revision,
        selection_lock_revision=selection_lock_revision,
        repository_root=repository_root,
    )

    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{root.name}.staging-", dir=root.parent))
    try:
        result = _render_validated_artifacts(
            aggregate,
            staging,
            accepted_aggregate_sha256=aggregate_sha256,
        )
        _publish_directory_no_replace(staging, root)
        return result
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--aggregate",
        type=Path,
        default=Path("review/realistic_transport/AGGREGATE.json"),
    )
    parser.add_argument(
        "--review-root",
        type=Path,
        default=Path("review/realistic_transport"),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("experiments/configs/realistic_transport_covtype.yaml"),
    )
    parser.add_argument(
        "--profile",
        choices=("smoke", "covtype_pilot", "tuning", "resource_fallback", "full"),
        required=True,
    )
    parser.add_argument(
        "--raw-root", type=Path, default=Path("results/raw/realistic_transport")
    )
    parser.add_argument("--selection", type=Path, default=None)
    parser.add_argument("--data-lock", type=Path, default=None)
    parser.add_argument("--freeze-revision", default=None)
    parser.add_argument("--selection-lock-revision", default=None)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            generate_artifacts(
                aggregate_path=args.aggregate,
                review_root=args.review_root,
                config_path=args.config,
                profile=args.profile,
                raw_root=args.raw_root,
                selection_path=args.selection,
                data_lock_path=args.data_lock,
                freeze_revision=args.freeze_revision,
                selection_lock_revision=args.selection_lock_revision,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
