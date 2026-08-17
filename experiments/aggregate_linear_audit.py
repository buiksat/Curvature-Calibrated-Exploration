"""Strict, linear-only aggregation for the retained confidence audit."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scipy.stats import t as student_t

from .artifact_utils import (
    input_set_sha256,
    sha256_file,
    write_aggregate_with_provenance,
)
from .config import config_digest, get_seed_set, load_config
from .logging_utils import canonical_json
from .run_linear_audit import configured_methods
from .run_linear_study import (
    resolved_policy_config,
    study_metadata,
    tuning_grid,
    tuning_run_is_valid,
)


REQUIRED_RUN_FILES = ("manifest.jsonl", "raw.jsonl", "summary.jsonl")
COMPARISONS = ("fixed_reference", "validation_tuned")
REQUIRED_HORIZON_METRICS = (
    "cumulative_pseudo_regret",
    "theorem_rhs",
    "beta_t",
    "bar_psi_t",
    "u_t",
    "cg_certified_epsilon",
    "cg_energy_error_max",
    "kappa_bar_t",
    "theorem_bound_slack",
)


class LinearAggregationError(ValueError):
    """Raised when linear-study outputs are incomplete or inconsistent."""


@dataclass(frozen=True)
class LinearRun:
    directory: Path
    manifest: dict[str, Any]
    raw: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    config: dict[str, Any]
    method: str
    seed: int
    phase: str
    comparison: str
    hyperparameters: dict[str, float]


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LinearAggregationError(f"cannot read JSON object {path}: {error}") from error
    if not isinstance(value, dict):
        raise LinearAggregationError(f"expected a JSON object in {path}")
    return value


def _load_jsonl(path: Path, *, exactly_one: bool) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise LinearAggregationError(f"cannot read {path}: {error}") from error
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise LinearAggregationError(
                f"invalid JSON in {path}:{line_number}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise LinearAggregationError(f"{path}:{line_number} is not an object")
        records.append(value)
    if not records or (exactly_one and len(records) != 1):
        expected = "exactly one record" if exactly_one else "at least one record"
        raise LinearAggregationError(f"{path} must contain {expected}")
    return records


def _finite_number(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LinearAggregationError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise LinearAggregationError(f"{name} must be finite")
    return result


def _scalar_hyperparameters(value: Any, *, name: str) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise LinearAggregationError(f"{name} must be an object")
    result = {
        str(key): _finite_number(item, name=f"{name}.{key}")
        for key, item in value.items()
    }
    if set(result) != {"ridge", "bonus_scale"}:
        raise LinearAggregationError(
            f"{name} must contain exactly ridge and bonus_scale"
        )
    return result


def _same_hyperparameters(
    left: Mapping[str, float], right: Mapping[str, float]
) -> bool:
    return set(left) == set(right) and all(
        math.isclose(left[key], right[key], rel_tol=0.0, abs_tol=1e-14)
        for key in left
    )


def _load_run(
    directory: Path,
    *,
    expected_profile: str,
    expected_phase: str,
    expected_comparison: str,
    expected_method: str,
    expected_seed: int,
    expected_hyperparameters: Mapping[str, float],
    expected_config: Mapping[str, Any],
    tuning_seeds: Sequence[int],
    evaluation_seeds: Sequence[int],
    selection_sha256: str | None,
) -> LinearRun:
    missing = [name for name in REQUIRED_RUN_FILES if not (directory / name).is_file()]
    if missing:
        raise LinearAggregationError(
            f"incomplete run directory {directory}: missing {', '.join(missing)}"
        )
    manifest = _load_jsonl(directory / "manifest.jsonl", exactly_one=True)[0]
    raw = tuple(_load_jsonl(directory / "raw.jsonl", exactly_one=False))
    summary = _load_jsonl(directory / "summary.jsonl", exactly_one=True)[0]
    if manifest.get("schema_version") != 1:
        raise LinearAggregationError(f"unsupported manifest schema in {directory}")
    config = manifest.get("config")
    if not isinstance(config, dict):
        raise LinearAggregationError(f"manifest config is missing in {directory}")
    if manifest.get("config_digest") != config_digest(config):
        raise LinearAggregationError(f"manifest config digest mismatch in {directory}")
    if canonical_json(config) != canonical_json(expected_config):
        raise LinearAggregationError(f"manifest config mismatch in {directory}")
    if config.get("name") != "linear_audit" or config.get("profile") != expected_profile:
        raise LinearAggregationError(f"wrong experiment or profile in {directory}")
    if manifest.get("seed") != expected_seed or summary.get("seed") != expected_seed:
        raise LinearAggregationError(f"seed provenance mismatch in {directory}")
    if summary.get("method") != expected_method:
        raise LinearAggregationError(f"summary method mismatch in {directory}")
    if summary.get("executed_policy") is not True:
        raise LinearAggregationError(f"run is not an executed policy: {directory}")

    study = config.get("study")
    execution = config.get("execution")
    if not isinstance(study, Mapping) or not isinstance(execution, Mapping):
        raise LinearAggregationError(f"study/execution provenance is missing in {directory}")
    if study.get("phase") != expected_phase:
        raise LinearAggregationError(f"phase mismatch in {directory}")
    if study.get("comparison") != expected_comparison:
        raise LinearAggregationError(f"comparison mismatch in {directory}")
    if execution.get("method") != expected_method or execution.get("seed") != expected_seed:
        raise LinearAggregationError(f"execution provenance mismatch in {directory}")
    if execution.get("executed_policy") is not True:
        raise LinearAggregationError(f"manifest does not certify execution in {directory}")
    if tuple(study.get("tuning_seeds", ())) != tuple(tuning_seeds) or tuple(
        study.get("evaluation_seeds", ())
    ) != tuple(evaluation_seeds):
        raise LinearAggregationError(f"study seed provenance mismatch in {directory}")
    declared = config.get("seed_sets")
    if not isinstance(declared, Mapping) or tuple(declared.get("tuning", ())) != tuple(
        tuning_seeds
    ) or tuple(declared.get("evaluation", ())) != tuple(evaluation_seeds):
        raise LinearAggregationError(f"config seed provenance mismatch in {directory}")
    hyperparameters = _scalar_hyperparameters(
        study.get("hyperparameters"), name=f"{directory} hyperparameters"
    )
    if not _same_hyperparameters(hyperparameters, expected_hyperparameters):
        raise LinearAggregationError(f"hyperparameter mismatch in {directory}")
    if expected_phase == "evaluation":
        if not selection_sha256 or study.get("selection_sha256") != selection_sha256:
            raise LinearAggregationError(f"selection digest mismatch in {directory}")
    elif "selection_sha256" in study:
        raise LinearAggregationError(f"tuning run unexpectedly binds a selection in {directory}")

    rounds = [record.get("round") for record in raw]
    if rounds != list(range(len(raw))):
        raise LinearAggregationError(f"raw rounds are not contiguous in {directory}")
    configured_rounds = config.get("rounds")
    if (
        isinstance(configured_rounds, bool)
        or not isinstance(configured_rounds, int)
        or configured_rounds != len(raw)
    ):
        raise LinearAggregationError(f"raw trajectory length mismatch in {directory}")
    if summary.get("rounds") != len(raw):
        raise LinearAggregationError(f"summary trajectory length mismatch in {directory}")
    for index, record in enumerate(raw):
        metrics = record.get("metrics")
        if not isinstance(metrics, Mapping) or metrics.get("executed_policy") is not True:
            raise LinearAggregationError(
                f"raw round {index} is not an executed policy in {directory}"
            )
        if metrics.get("method") != expected_method:
            raise LinearAggregationError(f"raw method mismatch in {directory}")
    final_metrics = raw[-1]["metrics"]
    if not isinstance(final_metrics, Mapping):
        raise AssertionError("validated raw record lost its metric mapping")
    final_aliases = {
        "cumulative_pseudo_regret": "cumulative_pseudo_regret",
        "theorem_rhs": "theorem_rhs",
        "E_T": "E_T",
        "F_T": "F_T",
        "Lambda_alg_T": "Lambda_alg_cumulative",
        "S_T": "S_t_cumulative",
        "V_alg_T": "V_alg_cumulative",
        "Gamma_dynamic_T": "Gamma_dynamic_cumulative",
        "theorem_bound_slack": "theorem_bound_slack",
    }
    for summary_name, raw_name in final_aliases.items():
        if not math.isclose(
            _finite_number(summary.get(summary_name), name=f"summary {summary_name}"),
            _finite_number(final_metrics.get(raw_name), name=f"raw {raw_name}"),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise LinearAggregationError(
                f"summary {summary_name} disagrees with the final raw round in {directory}"
            )
    return LinearRun(
        directory=directory,
        manifest=manifest,
        raw=raw,
        summary=summary,
        config=config,
        method=expected_method,
        seed=expected_seed,
        phase=expected_phase,
        comparison=expected_comparison,
        hyperparameters=hyperparameters,
    )


def _prefix_metrics(run: LinearRun, horizon: int) -> dict[str, float]:
    if horizon <= 0 or horizon > len(run.raw):
        raise LinearAggregationError(f"invalid horizon {horizon} for {run.directory}")
    prefix = [record["metrics"] for record in run.raw[:horizon]]
    last = prefix[-1]
    if not isinstance(last, Mapping):
        raise AssertionError("validated raw record lost its metric mapping")
    return {
        name: _finite_number(last.get(name), name=f"raw {name}")
        for name in REQUIRED_HORIZON_METRICS
    }


def _student_t_interval(values: Iterable[float]) -> dict[str, Any]:
    checked = [float(value) for value in values]
    if not checked or any(not math.isfinite(value) for value in checked):
        raise LinearAggregationError("interval input must be nonempty and finite")
    count = len(checked)
    mean = statistics.fmean(checked)
    standard_deviation = statistics.stdev(checked) if count > 1 else 0.0
    standard_error = standard_deviation / math.sqrt(count) if count > 1 else 0.0
    critical = float(student_t.ppf(0.975, count - 1)) if count > 1 else 0.0
    half_width = critical * standard_error
    return {
        "n": count,
        "mean": float(mean),
        "standard_deviation": float(standard_deviation),
        "standard_error": float(standard_error),
        "t_critical": critical,
        "ci95_half_width": float(half_width),
        "ci95_low": float(mean - half_width),
        "ci95_high": float(mean + half_width),
        "ci95": [float(mean - half_width), float(mean + half_width)],
    }


def _aggregate_metrics(values: Sequence[Mapping[str, float]]) -> dict[str, Any]:
    names = sorted({name for value in values for name in value})
    return {
        name: _student_t_interval(value[name] for value in values if name in value)
        for name in names
    }


def _run_inputs(runs: Sequence[LinearRun]) -> list[dict[str, str]]:
    return [
        {"path": str(run.directory / filename), "sha256": sha256_file(run.directory / filename)}
        for run in sorted(runs, key=lambda item: str(item.directory))
        for filename in REQUIRED_RUN_FILES
    ]


def _group_record(
    runs: Sequence[LinearRun],
    *,
    horizons: Sequence[int],
    evaluation_seeds: Sequence[int],
) -> dict[str, Any]:
    members = sorted(runs, key=lambda run: run.seed)
    first = members[0]
    if [run.seed for run in members] != list(evaluation_seeds):
        raise LinearAggregationError(
            f"incomplete seed set for {first.comparison}/{first.method}"
        )
    horizon_records = []
    for horizon in horizons:
        metrics = _aggregate_metrics([_prefix_metrics(run, horizon) for run in members])
        horizon_records.append(
            {
                "horizon": horizon,
                "metrics": metrics,
            }
        )
    inputs = _run_inputs(members)
    return {
        "experiment": "linear_audit",
        "profile": str(first.config["profile"]),
        "seed_set": "evaluation",
        "comparison": first.comparison,
        "method": first.method,
        "variant": {},
        "hyperparameters": first.hyperparameters,
        "seeds": [run.seed for run in members],
        "declared_seeds": list(evaluation_seeds),
        "run_count": len(members),
        "complete_declared_seed_set": True,
        "horizons": horizon_records,
        "run_directories": [str(run.directory) for run in members],
        "inputs": inputs,
        "input_set_sha256": input_set_sha256(inputs),
    }


def aggregate_linear_audit(
    config: Mapping[str, Any],
    raw_root: str | Path,
    *,
    profile: str,
    selection_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate a complete study and return its strict evaluation aggregate."""

    if config.get("name") != "linear_audit" or config.get("profile") != profile:
        raise LinearAggregationError("config must be the resolved linear_audit profile")
    methods = configured_methods(config)
    if not methods or methods[0] != "dense_full":
        raise LinearAggregationError("linear methods must start with dense_full")
    tuning_seeds = get_seed_set(config, "tuning")
    evaluation_seeds = get_seed_set(config, "evaluation")
    if set(tuning_seeds) & set(evaluation_seeds):
        raise LinearAggregationError("tuning and evaluation seeds overlap")
    profile_root = Path(raw_root) / profile
    selection_file = (
        profile_root / "selection.json"
        if selection_path is None
        else Path(selection_path)
    )
    selection = _load_object(selection_file)
    if (
        selection.get("schema_version") != 1
        or selection.get("event") != "linear_study_selection"
        or selection.get("experiment") != "linear_audit"
        or selection.get("profile") != profile
        or selection.get("base_config_digest") != config_digest(config)
        or tuple(selection.get("tuning_seed_set", ())) != tuple(tuning_seeds)
        or tuple(selection.get("evaluation_seed_set", ())) != tuple(evaluation_seeds)
        or selection.get("seed_sets_disjoint") is not True
        or selection.get("tuning_rounds") != config.get("tuning_rounds")
        or selection.get("evaluation_rounds") != config.get("rounds")
    ):
        raise LinearAggregationError("selection provenance disagrees with the config")
    selection_sha256 = sha256_file(selection_file)

    candidates = selection.get("candidates")
    selected = selection.get("selected")
    if not isinstance(candidates, Mapping) or not isinstance(selected, Mapping):
        raise LinearAggregationError("selection is missing candidates or winners")
    if set(candidates) != set(methods) or set(selected) != set(methods):
        raise LinearAggregationError("selection method set disagrees with the config")

    tuning_runs: list[LinearRun] = []
    expected_tuning_directories: set[Path] = set()
    selected_hyperparameters: dict[str, dict[str, float]] = {}
    for method in methods:
        records = candidates[method]
        expected_grid = tuning_grid(config)
        if (
            not isinstance(records, Sequence)
            or isinstance(records, (str, bytes))
            or len(records) != len(expected_grid)
        ):
            raise LinearAggregationError(
                f"selection candidate grid is incomplete for {method}"
            )
        computed: list[dict[str, Any]] = []
        for candidate_index, (record, configured_hyperparameters) in enumerate(
            zip(records, expected_grid, strict=True)
        ):
            if not isinstance(record, Mapping):
                raise LinearAggregationError(f"malformed selection candidate for {method}")
            candidate_id = record.get("candidate_id")
            expected_candidate_id = f"candidate-{candidate_index:03d}"
            if candidate_id != expected_candidate_id:
                raise LinearAggregationError(
                    f"candidate id mismatch for {method}: expected {expected_candidate_id}"
                )
            hyperparameters = _scalar_hyperparameters(
                record.get("hyperparameters"), name=f"{method}/{candidate_id}"
            )
            if not _same_hyperparameters(hyperparameters, configured_hyperparameters):
                raise LinearAggregationError(
                    f"candidate grid mismatch for {method}/{candidate_id}"
                )
            regrets: list[float] = []
            valid_by_seed: dict[str, bool] = {}
            for seed in tuning_seeds:
                directory = (
                    profile_root / "tuning" / method / candidate_id / f"seed-{seed}"
                )
                expected_tuning_directories.add(directory)
                expected_run_config = resolved_policy_config(
                    config,
                    ridge=hyperparameters["ridge"],
                    bonus_scale=hyperparameters["bonus_scale"],
                    rounds=int(config["tuning_rounds"]),
                )
                expected_run_config["study"] = study_metadata(
                    config,
                    phase="tuning",
                    comparison="validation_tuning",
                    hyperparameters=hyperparameters,
                    tuning_seeds=tuning_seeds,
                    evaluation_seeds=evaluation_seeds,
                    tuning_rounds=int(config["tuning_rounds"]),
                    evaluation_rounds=int(config["rounds"]),
                )
                expected_run_config["execution"] = {
                    "method": method,
                    "seed": seed,
                    "executed_policy": True,
                }
                run = _load_run(
                    directory,
                    expected_profile=profile,
                    expected_phase="tuning",
                    expected_comparison="validation_tuning",
                    expected_method=method,
                    expected_seed=seed,
                    expected_hyperparameters=hyperparameters,
                    expected_config=expected_run_config,
                    tuning_seeds=tuning_seeds,
                    evaluation_seeds=evaluation_seeds,
                    selection_sha256=None,
                )
                tuning_runs.append(run)
                regrets.append(
                    _finite_number(
                        run.summary.get("cumulative_pseudo_regret"),
                        name="tuning cumulative regret",
                    )
                )
                valid_by_seed[str(seed)] = tuning_run_is_valid(run.summary)
            mean_regret = statistics.fmean(regrets)
            expected_regrets = record.get("regret_by_seed")
            if not isinstance(expected_regrets, Mapping) or any(
                not math.isclose(
                    _finite_number(expected_regrets.get(str(seed)), name="selection regret"),
                    regret,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
                for seed, regret in zip(tuning_seeds, regrets, strict=True)
            ):
                raise LinearAggregationError(f"selection regret mismatch for {method}/{candidate_id}")
            if record.get("valid_by_seed") != valid_by_seed:
                raise LinearAggregationError(f"selection validity mismatch for {method}/{candidate_id}")
            if record.get("eligible") is not all(valid_by_seed.values()):
                raise LinearAggregationError(f"selection eligibility mismatch for {method}/{candidate_id}")
            if not math.isclose(
                _finite_number(
                    record.get("mean_cumulative_pseudo_regret"),
                    name="selection mean regret",
                ),
                mean_regret,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise LinearAggregationError(f"selection mean mismatch for {method}/{candidate_id}")
            computed.append(
                {
                    "candidate_id": candidate_id,
                    "hyperparameters": hyperparameters,
                    "mean": mean_regret,
                    "eligible": all(valid_by_seed.values()),
                }
            )
        eligible = [record for record in computed if record["eligible"]]
        if not eligible:
            raise LinearAggregationError(f"no eligible tuning candidate for {method}")
        winner = min(
            eligible,
            key=lambda record: (
                record["mean"],
                record["hyperparameters"]["ridge"],
                record["hyperparameters"]["bonus_scale"],
                record["candidate_id"],
            ),
        )
        selected_record = selected[method]
        if not isinstance(selected_record, Mapping):
            raise LinearAggregationError(f"selected record is malformed for {method}")
        selected_values = _scalar_hyperparameters(
            selected_record.get("hyperparameters"), name=f"selected {method}"
        )
        if (
            selected_record.get("candidate_id") != winner["candidate_id"]
            or not _same_hyperparameters(selected_values, winner["hyperparameters"])
            or not math.isclose(
                _finite_number(
                    selected_record.get("mean_cumulative_pseudo_regret"),
                    name="selected mean regret",
                ),
                winner["mean"],
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ):
            raise LinearAggregationError(f"selected winner is inconsistent for {method}")
        selected_hyperparameters[method] = selected_values

    discovered_tuning = {
        path.parent for path in (profile_root / "tuning").rglob("manifest.jsonl")
    }
    if discovered_tuning != expected_tuning_directories:
        raise LinearAggregationError("tuning tree contains missing or unexpected runs")

    confidence = config.get("confidence")
    fixed_bonus = (
        confidence.get("bonus_scale", 1.0)
        if isinstance(confidence, Mapping)
        else 1.0
    )
    fixed_hyperparameters = {
        "ridge": _finite_number(config.get("ridge", 1.0), name="fixed ridge"),
        "bonus_scale": _finite_number(
            config.get("bonus_scale", fixed_bonus), name="fixed bonus scale"
        ),
    }
    evaluation_runs: list[LinearRun] = []
    grouped: dict[tuple[str, str], list[LinearRun]] = {}
    expected_evaluation_directories: set[Path] = set()
    for comparison in COMPARISONS:
        for method in methods:
            hyperparameters = (
                fixed_hyperparameters
                if comparison == "fixed_reference"
                else selected_hyperparameters[method]
            )
            members = []
            for seed in evaluation_seeds:
                directory = (
                    profile_root
                    / "evaluation"
                    / comparison
                    / method
                    / f"seed-{seed}"
                )
                expected_evaluation_directories.add(directory)
                expected_run_config = resolved_policy_config(
                    config,
                    ridge=hyperparameters["ridge"],
                    bonus_scale=hyperparameters["bonus_scale"],
                    rounds=int(config["rounds"]),
                )
                expected_run_config["study"] = study_metadata(
                    config,
                    phase="evaluation",
                    comparison=comparison,
                    hyperparameters=hyperparameters,
                    tuning_seeds=tuning_seeds,
                    evaluation_seeds=evaluation_seeds,
                    tuning_rounds=int(config["tuning_rounds"]),
                    evaluation_rounds=int(config["rounds"]),
                    selection_sha256=selection_sha256,
                )
                expected_run_config["execution"] = {
                    "method": method,
                    "seed": seed,
                    "executed_policy": True,
                }
                run = _load_run(
                    directory,
                    expected_profile=profile,
                    expected_phase="evaluation",
                    expected_comparison=comparison,
                    expected_method=method,
                    expected_seed=seed,
                    expected_hyperparameters=hyperparameters,
                    expected_config=expected_run_config,
                    tuning_seeds=tuning_seeds,
                    evaluation_seeds=evaluation_seeds,
                    selection_sha256=selection_sha256,
                )
                members.append(run)
                evaluation_runs.append(run)
            grouped[(comparison, method)] = members
    discovered_evaluation = {
        path.parent for path in (profile_root / "evaluation").rglob("manifest.jsonl")
    }
    if discovered_evaluation != expected_evaluation_directories:
        raise LinearAggregationError("evaluation tree contains missing or unexpected runs")

    trajectory_lengths = {len(run.raw) for run in evaluation_runs}
    if len(trajectory_lengths) != 1:
        raise LinearAggregationError("evaluation trajectories have inconsistent lengths")
    final_horizon = next(iter(trajectory_lengths))
    configured_horizons = config.get("horizons", ())
    horizons = {final_horizon}
    if isinstance(configured_horizons, Sequence) and not isinstance(
        configured_horizons, (str, bytes)
    ):
        horizons.update(
            int(value)
            for value in configured_horizons
            if isinstance(value, int)
            and not isinstance(value, bool)
            and 0 < value <= final_horizon
        )
    ordered_horizons = tuple(sorted(horizons))
    groups = [
        _group_record(
            grouped[(comparison, method)],
            horizons=ordered_horizons,
            evaluation_seeds=evaluation_seeds,
        )
        for comparison in COMPARISONS
        for method in methods
    ]
    inputs = _run_inputs([*tuning_runs, *evaluation_runs])
    inputs.append({"path": str(selection_file), "sha256": selection_sha256})
    if config_path is not None:
        source = Path(config_path)
        inputs.append({"path": str(source), "sha256": sha256_file(source)})
    inputs = sorted(inputs, key=lambda item: item["path"])
    aggregate = {
        "schema_version": 1,
        "event": "executed_policy_aggregate",
        "confidence_interval": "two-sided 95% Student-t",
        "run_count": len(evaluation_runs),
        "artifact_run_count": len(evaluation_runs),
        "tuning_run_count": len(tuning_runs),
        "group_count": len(groups),
        "profiles": [profile],
        "seed_sets": ["evaluation"],
        "experiments": ["linear_audit"],
        "all_runs_executed_policy": True,
        "all_seed_provenance_disjoint": True,
        "all_groups_complete": True,
        "paired_comparison_count": 0,
        "all_paired_comparisons_complete": True,
        "groups": groups,
        "paired_comparisons": [],
        "hypothesis_audits": [],
        "offline_diagnostic_run_count": 0,
        "offline_diagnostic_group_count": 0,
        "offline_common_trajectory_validated": True,
        "offline_diagnostic_groups": [],
        "benchmark_diagnostic_run_count": 0,
        "benchmark_diagnostic_group_count": 0,
        "benchmark_diagnostic_groups": [],
        "benchmark_diagnostic_audits": [],
        "input_root": str(profile_root / "evaluation"),
        "selection_path": str(selection_file),
        "selection_sha256": selection_sha256,
        "fresh_tuning_selection_validated": True,
        "inputs": inputs,
        "input_set_sha256": input_set_sha256(inputs),
    }
    return aggregate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("experiments/configs/linear_audit.yaml")
    )
    parser.add_argument("--profile", choices=("smoke", "full"), default="full")
    parser.add_argument(
        "--raw-root", type=Path, default=Path("results/raw/linear_audit")
    )
    parser.add_argument("--selection", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/derived/linear_audit_full.json"),
    )
    args = parser.parse_args(argv)
    config = load_config(args.config, profile=args.profile)
    aggregate = aggregate_linear_audit(
        config,
        args.raw_root,
        profile=args.profile,
        selection_path=args.selection,
        config_path=args.config,
    )
    output, sidecar = write_aggregate_with_provenance(aggregate, args.output)
    print(
        canonical_json(
            {
                "output": str(output),
                "provenance": str(sidecar),
                "run_count": aggregate["run_count"],
                "group_count": aggregate["group_count"],
                "selection_sha256": aggregate["selection_sha256"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "LinearAggregationError",
    "aggregate_linear_audit",
    "main",
]
