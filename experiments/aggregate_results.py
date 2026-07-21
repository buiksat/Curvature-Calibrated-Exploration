"""Validate and aggregate executed-policy experiment artifacts.

An input run is a directory containing ``manifest.jsonl``, ``raw.jsonl``, and
``summary.jsonl``.  Aggregation is intentionally strict: replay diagnostics,
legacy records, incomplete trajectories, and tuning/evaluation leakage are
errors rather than rows that are silently mixed into a paper result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from scipy.stats import t as _student_t
except ImportError:  # pragma: no cover - the pinned experiment environment has SciPy.
    _student_t = None

from .logging_utils import canonical_json


REQUIRED_FILENAMES = ("manifest.jsonl", "raw.jsonl", "summary.jsonl")


class AggregationError(ValueError):
    """Raised when raw artifacts cannot support a valid aggregate."""


@dataclass(frozen=True)
class LoadedRun:
    directory: Path
    manifest: dict[str, Any]
    raw: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    config: dict[str, Any]
    seed: int
    seed_set: str
    experiment: str
    profile: str
    comparison: str
    method: str
    variant: dict[str, Any]
    hyperparameters: dict[str, Any]
    declared_seeds: tuple[int, ...]
    executed_policy: bool
    execution_mode: str


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AggregationError(f"cannot read {path}: {exc}") from exc
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AggregationError(f"invalid JSON in {path}:{line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise AggregationError(f"{path}:{line_number} must contain a JSON object")
        records.append(record)
    if not records:
        raise AggregationError(f"{path} contains no records")
    return records


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    """Stream strict JSONL records without retaining large diagnostic grids."""

    seen = False
    try:
        stream = path.open(encoding="utf-8")
    except OSError as exc:
        raise AggregationError(f"cannot read {path}: {exc}") from exc
    with stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            seen = True
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AggregationError(
                    f"invalid JSON in {path}:{line_number}: {exc}"
                ) from exc
            if not isinstance(record, dict):
                raise AggregationError(
                    f"{path}:{line_number} must contain a JSON object"
                )
            yield record
    if not seen:
        raise AggregationError(f"{path} contains no records")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def discover_run_directories(root: str | Path) -> tuple[Path, ...]:
    source = Path(root)
    if not source.exists():
        raise AggregationError(f"input root does not exist: {source}")
    if source.is_file():
        raise AggregationError("input root must be a directory")
    directories = sorted({path.parent for path in source.rglob("manifest.jsonl")})
    if not directories:
        raise AggregationError(f"no manifest.jsonl files found below {source}")
    for directory in directories:
        missing = [name for name in REQUIRED_FILENAMES if not (directory / name).is_file()]
        if missing:
            raise AggregationError(
                f"incomplete run directory {directory}: missing {', '.join(missing)}"
            )
    return tuple(directories)


def _integer_seed_list(value: Any, *, context: str) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise AggregationError(f"{context} must be a nonempty seed list")
    result: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise AggregationError(f"{context} contains an invalid seed")
        result.append(item)
    if len(result) != len(set(result)):
        raise AggregationError(f"{context} contains duplicate seeds")
    return tuple(result)


def _declared_seed_sets(config: Mapping[str, Any]) -> dict[str, tuple[int, ...]]:
    value = config.get("seed_sets")
    if not isinstance(value, Mapping):
        raise AggregationError("manifest config is missing seed_sets provenance")
    result = {
        name: _integer_seed_list(value.get(name), context=f"seed_sets.{name}")
        for name in ("tuning", "evaluation")
    }
    overlap = set(result["tuning"]) & set(result["evaluation"])
    if overlap:
        raise AggregationError(
            f"tuning/evaluation provenance overlaps at seeds {sorted(overlap)}"
        )
    study = config.get("study")
    if isinstance(study, Mapping):
        tuning = study.get("tuning_seeds")
        evaluation = study.get("evaluation_seeds")
        if tuning is not None or evaluation is not None:
            study_tuning = _integer_seed_list(tuning, context="study.tuning_seeds")
            study_evaluation = _integer_seed_list(
                evaluation, context="study.evaluation_seeds"
            )
            if set(study_tuning) & set(study_evaluation):
                raise AggregationError("study tuning/evaluation provenance overlaps")
            if study_tuning != result["tuning"] or study_evaluation != result["evaluation"]:
                raise AggregationError("study seed provenance disagrees with config.seed_sets")
    return result


def _compact_header(directory: Path) -> dict[str, Any]:
    manifests = _read_jsonl(directory / "manifest.jsonl")
    summaries = _read_jsonl(directory / "summary.jsonl")
    if len(manifests) != 1 or len(summaries) != 1:
        raise AggregationError(
            f"{directory} must contain exactly one manifest and one summary"
        )
    manifest = manifests[0]
    summary = summaries[0]
    if manifest.get("schema_version") != 1 or not isinstance(
        manifest.get("config"), dict
    ):
        raise AggregationError(f"legacy or malformed manifest in {directory}")
    config = manifest["config"]
    seed = manifest.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise AggregationError(f"invalid manifest seed in {directory}")
    if summary.get("seed", seed) != seed:
        raise AggregationError(f"summary seed disagrees with manifest in {directory}")
    declared = _declared_seed_sets(config)
    memberships = [name for name, seeds in declared.items() if seed in seeds]
    if len(memberships) != 1:
        raise AggregationError(
            f"seed {seed} must belong to exactly one declared seed set in {directory}"
        )
    explicit = _explicit_seed_set(config, directory)
    if explicit is not None and explicit != memberships[0]:
        raise AggregationError(f"seed-set path/provenance mismatch in {directory}")
    return {
        "directory": directory,
        "manifest": manifest,
        "summary": summary,
        "config": config,
        "seed": seed,
        "seed_set": memberships[0],
        "declared_seeds": declared[memberships[0]],
        "experiment": str(config.get("name", "")),
        "profile": str(config.get("profile", "")),
    }


def _explicit_seed_set(config: Mapping[str, Any], directory: Path) -> str | None:
    candidates: list[str] = []
    study = config.get("study")
    if isinstance(study, Mapping):
        for key in ("phase", "seed_set"):
            value = study.get(key)
            if value in {"tuning", "evaluation"}:
                candidates.append(str(value))
    execution = config.get("execution")
    if isinstance(execution, Mapping) and execution.get("seed_set") in {
        "tuning",
        "evaluation",
    }:
        candidates.append(str(execution["seed_set"]))
    if config.get("seed_set") in {"tuning", "evaluation"}:
        candidates.append(str(config["seed_set"]))
    path_candidates = [part for part in directory.parts if part in {"tuning", "evaluation"}]
    if path_candidates:
        candidates.append(path_candidates[-1])
    if len(set(candidates)) > 1:
        raise AggregationError(
            f"conflicting seed-set provenance for {directory}: {sorted(set(candidates))}"
        )
    return candidates[0] if candidates else None


def _record_metrics(record: Mapping[str, Any]) -> Mapping[str, Any]:
    metrics = record.get("metrics")
    return metrics if isinstance(metrics, Mapping) else record


def _validate_executed_policy(
    directory: Path,
    config: Mapping[str, Any],
    summary: Mapping[str, Any],
    raw: Sequence[Mapping[str, Any]],
) -> None:
    execution = config.get("execution")
    if isinstance(execution, Mapping):
        if execution.get("executed_policy") is False:
            raise AggregationError(f"manifest marks {directory} as a non-executed policy")
        mode = str(execution.get("mode", "")).lower()
        if "offline" in mode or "diagnostic" in mode or "legacy" in mode:
            raise AggregationError(f"manifest execution mode is not an online policy: {mode}")
    if summary.get("executed_policy") is not True:
        raise AggregationError(f"summary does not explicitly certify executed_policy: {directory}")
    if summary.get("offline_diagnostic") is True or summary.get("legacy") is True:
        raise AggregationError(f"summary is diagnostic or legacy: {directory}")
    for index, record in enumerate(raw):
        if _record_metrics(record).get("executed_policy") is not True:
            raise AggregationError(
                f"raw record {index} does not explicitly certify executed_policy: {directory}"
            )


def _validate_offline_diagnostic(
    directory: Path,
    config: Mapping[str, Any],
    summary: Mapping[str, Any],
    raw: Sequence[Mapping[str, Any]],
) -> None:
    execution = config.get("execution")
    mode = (
        str(execution.get("mode", "")).lower()
        if isinstance(execution, Mapping)
        else ""
    )
    if "offline_common_trajectory" not in mode:
        raise AggregationError(
            f"non-executed artifact lacks offline common-trajectory provenance: {directory}"
        )
    if (
        summary.get("executed_policy") is not False
        or summary.get("offline_diagnostic") is not True
        or summary.get("causal_regret_claim") is not False
        or summary.get("regret_reported") is not False
    ):
        raise AggregationError(f"invalid offline diagnostic summary claims: {directory}")
    trajectory_digest = summary.get("trajectory_digest")
    if not isinstance(trajectory_digest, str) or not trajectory_digest:
        raise AggregationError(f"offline diagnostic lacks a trajectory digest: {directory}")
    for index, record in enumerate(raw):
        metrics = _record_metrics(record)
        if (
            metrics.get("executed_policy") is not False
            or metrics.get("offline_diagnostic") is not True
            or metrics.get("causal_regret_claim") is not False
            or metrics.get("regret_reported") is not False
            or metrics.get("trajectory_digest") != trajectory_digest
        ):
            raise AggregationError(
                f"raw record {index} violates offline diagnostic labeling: {directory}"
            )


def _scalar_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(key, str) and (
            item is None or isinstance(item, (str, bool, int, float))
        ):
            result[key] = item
    return result


def _comparison(config: Mapping[str, Any], summary: Mapping[str, Any]) -> str:
    study = config.get("study")
    execution = config.get("execution")
    for value in (
        study.get("comparison") if isinstance(study, Mapping) else None,
        execution.get("comparison") if isinstance(execution, Mapping) else None,
        config.get("comparison"),
        summary.get("comparison"),
    ):
        if isinstance(value, str) and value:
            return value
    return "default"


def _method(
    directory: Path, config: Mapping[str, Any], summary: Mapping[str, Any]
) -> str:
    execution = config.get("execution")
    audit_execution = config.get("audit_execution")
    values = (
        summary.get("method"),
        summary.get("policy"),
        summary.get("operator"),
        summary.get("drift_name"),
        summary.get("drift_level"),
        execution.get("method") if isinstance(execution, Mapping) else None,
        execution.get("policy") if isinstance(execution, Mapping) else None,
        execution.get("operator") if isinstance(execution, Mapping) else None,
        execution.get("drift_name") if isinstance(execution, Mapping) else None,
        audit_execution.get("regime")
        if isinstance(audit_execution, Mapping)
        else None,
    )
    for value in values:
        if isinstance(value, str) and value:
            return value
    parent = directory.parent.name
    return parent if not parent.startswith("seed-") else "default"


def _variant(config: Mapping[str, Any], summary: Mapping[str, Any]) -> dict[str, Any]:
    execution = config.get("execution")
    audit_execution = config.get("audit_execution")
    result: dict[str, Any] = {}
    keys = (
        "center",
        "drift_name",
        "drift_level",
        "operator",
        "operator_kind",
        "policy",
        "model",
        "trainable",
    )
    for key in keys:
        for source in (
            summary,
            execution if isinstance(execution, Mapping) else {},
            audit_execution if isinstance(audit_execution, Mapping) else {},
        ):
            value = source.get(key)
            if value is None or isinstance(value, (str, bool, int, float)):
                if value is not None:
                    result[key] = value
                    break
    return result


def _hyperparameters(config: Mapping[str, Any], summary: Mapping[str, Any]) -> dict[str, Any]:
    study = config.get("study")
    execution = config.get("execution")
    for value in (
        study.get("hyperparameters") if isinstance(study, Mapping) else None,
        execution.get("hyperparameters") if isinstance(execution, Mapping) else None,
        config.get("hyperparameters"),
        summary.get("hyperparameters"),
    ):
        checked = _scalar_mapping(value)
        if checked:
            return checked
    # Several runners persist selected scalar settings directly in the run
    # summary rather than under a nested hyperparameters object.
    fallback: dict[str, Any] = {}
    for key in (
        "ridge",
        "damping",
        "bonus_scale",
        "model_ridge",
        "learning_rate",
        "step_cap",
    ):
        value = summary.get(key, config.get(key))
        if value is not None and not isinstance(value, (Mapping, Sequence)):
            fallback[key] = value
    return fallback


def load_run(directory: str | Path) -> LoadedRun:
    run_dir = Path(directory)
    manifest_records = _read_jsonl(run_dir / "manifest.jsonl")
    summary_records = _read_jsonl(run_dir / "summary.jsonl")
    raw_records = _read_jsonl(run_dir / "raw.jsonl")
    if len(manifest_records) != 1:
        raise AggregationError(f"{run_dir}/manifest.jsonl must contain exactly one record")
    if len(summary_records) != 1:
        raise AggregationError(f"{run_dir}/summary.jsonl must contain exactly one record")
    manifest = manifest_records[0]
    summary = summary_records[0]
    if manifest.get("schema_version") != 1:
        raise AggregationError(f"legacy or unknown manifest schema in {run_dir}")
    config_value = manifest.get("config")
    if not isinstance(config_value, dict):
        raise AggregationError(f"manifest config is missing in {run_dir}")
    config = config_value
    seed = manifest.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise AggregationError(f"manifest seed is invalid in {run_dir}")
    if summary.get("seed", seed) != seed:
        raise AggregationError(f"summary seed disagrees with manifest in {run_dir}")
    declared = _declared_seed_sets(config)
    memberships = [name for name, seeds in declared.items() if seed in seeds]
    if len(memberships) != 1:
        raise AggregationError(
            f"seed {seed} must belong to exactly one declared seed set in {run_dir}"
        )
    explicit = _explicit_seed_set(config, run_dir)
    seed_set = memberships[0]
    if explicit is not None and explicit != seed_set:
        raise AggregationError(
            f"run path/metadata says {explicit}, but seed {seed} belongs to {seed_set}"
        )
    rounds = [record.get("round") for record in raw_records]
    if rounds != list(range(len(raw_records))):
        raise AggregationError(f"raw rounds are not the contiguous prefix 0..T-1 in {run_dir}")
    configured_rounds = config.get("rounds")
    if isinstance(configured_rounds, int) and not isinstance(configured_rounds, bool):
        if configured_rounds != len(raw_records):
            raise AggregationError(
                f"raw trajectory length {len(raw_records)} != configured rounds "
                f"{configured_rounds} in {run_dir}"
            )
    is_offline = (
        summary.get("executed_policy") is False
        and summary.get("offline_diagnostic") is True
    )
    if is_offline:
        _validate_offline_diagnostic(run_dir, config, summary, raw_records)
        executed_policy = False
        execution_mode = "offline_common_trajectory_diagnostic"
    else:
        _validate_executed_policy(run_dir, config, summary, raw_records)
        executed_policy = True
        execution_mode = str(summary.get("execution_mode", "online_adaptive"))
    experiment = config.get("name")
    profile = config.get("profile")
    if not isinstance(experiment, str) or not experiment:
        raise AggregationError(f"manifest has no experiment name in {run_dir}")
    if not isinstance(profile, str) or not profile:
        raise AggregationError(f"manifest has no profile in {run_dir}")
    return LoadedRun(
        directory=run_dir,
        manifest=manifest,
        raw=tuple(raw_records),
        summary=summary,
        config=config,
        seed=seed,
        seed_set=seed_set,
        experiment=experiment,
        profile=profile,
        comparison=_comparison(config, summary),
        method=_method(run_dir, config, summary),
        variant=_variant(config, summary),
        hyperparameters=_hyperparameters(config, summary),
        declared_seeds=declared[seed_set],
        executed_policy=executed_policy,
        execution_mode=execution_mode,
    )


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    if not math.isfinite(result):
        raise AggregationError("non-finite numeric metric")
    return result


def _t_critical_95(degrees_of_freedom: int) -> float:
    if degrees_of_freedom <= 0:
        return 0.0
    if _student_t is not None:
        return float(_student_t.ppf(0.975, degrees_of_freedom))
    # Conservative table for minimal installations; interpolate by rounding
    # down in degrees of freedom, then use the normal limit above 30.
    table = {
        1: 12.706,
        2: 4.303,
        3: 3.182,
        4: 2.776,
        5: 2.571,
        6: 2.447,
        7: 2.365,
        8: 2.306,
        9: 2.262,
        10: 2.228,
        12: 2.179,
        15: 2.131,
        20: 2.086,
        25: 2.060,
        30: 2.042,
    }
    eligible = [key for key in table if key <= degrees_of_freedom]
    return table[max(eligible)] if degrees_of_freedom <= 30 else 1.96


def student_t_interval(values: Iterable[float]) -> dict[str, Any]:
    """Return a mean and two-sided 95% Student-t interval."""

    checked = [float(value) for value in values]
    if not checked or any(not math.isfinite(value) for value in checked):
        raise AggregationError("t interval requires nonempty finite values")
    count = len(checked)
    mean = float(statistics.fmean(checked))
    if count == 1:
        standard_deviation = 0.0
        standard_error = 0.0
        critical = 0.0
    else:
        standard_deviation = float(statistics.stdev(checked))
        standard_error = standard_deviation / math.sqrt(count)
        critical = _t_critical_95(count - 1)
    half_width = critical * standard_error
    low = mean - half_width
    high = mean + half_width
    return {
        "n": count,
        "mean": mean,
        "standard_deviation": standard_deviation,
        "standard_error": standard_error,
        "t_critical": critical,
        "ci95_half_width": half_width,
        "ci95_low": low,
        "ci95_high": high,
        "ci95": [low, high],
    }


def _last_numeric(metrics: Mapping[str, Any], names: Sequence[str]) -> float | None:
    for name in names:
        value = _numeric(metrics.get(name))
        if value is not None:
            return value
    return None


def prefix_metrics(raw: Sequence[Mapping[str, Any]], horizon: int) -> dict[str, float]:
    """Extract standardized metrics from the first ``horizon`` online rounds."""

    if horizon <= 0 or horizon > len(raw):
        raise AggregationError(f"invalid horizon {horizon} for {len(raw)} records")
    prefix = [_record_metrics(record) for record in raw[:horizon]]
    last = prefix[-1]
    result: dict[str, float] = {}
    for key, value in last.items():
        numeric = _numeric(value)
        if numeric is not None:
            result[key] = numeric

    aliases: dict[str, tuple[str, ...]] = {
        "cumulative_pseudo_regret": (
            "cumulative_pseudo_regret",
            "pseudo_regret_cumulative",
        ),
        "theorem_rhs": (
            "theorem_rhs",
            "theorem_rhs_posthoc",
            "posthoc_theorem_rhs_using_policy_schedule",
            "theorem_rhs_policy_schedule",
        ),
        "diagnostic_theorem_rhs": (
            "posthoc_theorem_rhs_using_exact_diagnostics",
        ),
        "Lambda_alg_T": (
            "Lambda_alg_cumulative",
            "Lambda_alg_T",
            "posthoc_Lambda_algorithmic",
        ),
        "S_T": ("S_t_cumulative", "S_T", "posthoc_policy_S_sum"),
        "diagnostic_S_T": ("posthoc_exact_diagnostic_S_sum",),
        "E_T": ("E_T", "E_t_cumulative", "posthoc_E_including_round"),
        "F_T": ("F_T", "F_t_cumulative", "posthoc_F_including_round"),
        "V_alg_T": (
            "V_alg_cumulative",
            "V_alg_T",
            "posthoc_V_variation_charge",
        ),
        "Gamma_dynamic_T": (
            "Gamma_dynamic_cumulative",
            "Gamma_dynamic_T",
            "posthoc_Gamma_dynamic",
        ),
        "runtime_seconds": ("runtime_seconds", "cumulative_runtime_seconds"),
        "optimism_violation_rate": (
            "selected_action_optimism_violation_rate",
            "optimism_violation_rate",
            "all_action_optimism_violation_rate",
            "policy_optimism_violation_rate",
        ),
    }
    for target, names in aliases.items():
        value = _last_numeric(last, names)
        if value is not None:
            result[target] = value

    if "cumulative_pseudo_regret" not in result:
        increments = [_numeric(metrics.get("pseudo_regret")) for metrics in prefix]
        if all(value is not None for value in increments):
            result["cumulative_pseudo_regret"] = float(
                sum(value for value in increments if value is not None)
            )
    if "runtime_seconds" not in result:
        runtimes = [_numeric(metrics.get("round_runtime_seconds")) for metrics in prefix]
        if all(value is not None for value in runtimes):
            result["runtime_seconds"] = float(
                sum(value for value in runtimes if value is not None)
            )
    if "cumulative_pseudo_regret" in result:
        mean_pseudo_regret = result["cumulative_pseudo_regret"] / float(horizon)
        result["mean_pseudo_regret"] = mean_pseudo_regret
        # Covertype records the true class arm on every binary-feedback round;
        # there pseudo-regret is exactly one minus accuracy.
        if all("true_label_arm" in metrics for metrics in prefix):
            result["accuracy"] = 1.0 - mean_pseudo_regret

    # The nonlinear audit records per-round all-action violation counts.  Turn
    # those into the same arm-round rate used in its final summary, including
    # at intermediate prefix horizons.
    if "optimism_violation_rate" not in result:
        violation_counts = [
            _numeric(metrics.get("policy_optimism_violation_count"))
            for metrics in prefix
        ]
        action_counts: list[int] = []
        for metrics in prefix:
            scores = metrics.get("policy_scores_all_actions")
            if isinstance(scores, Sequence) and not isinstance(scores, (str, bytes)):
                action_counts.append(len(scores))
        if (
            all(value is not None for value in violation_counts)
            and len(action_counts) == len(prefix)
            and sum(action_counts) > 0
        ):
            result["optimism_violation_rate"] = float(
                sum(value for value in violation_counts if value is not None)
                / sum(action_counts)
            )

    round_runtimes = [_numeric(metrics.get("round_runtime_seconds")) for metrics in prefix]
    if all(value is not None for value in round_runtimes):
        result["mean_round_runtime_seconds"] = statistics.fmean(
            value for value in round_runtimes if value is not None
        )
    cg_values: list[float] = []
    for metrics in prefix:
        value = metrics.get(
            "cg_iterations", metrics.get("posthoc_cg_iterations_all_actions")
        )
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for item in value:
                numeric = _numeric(item)
                if numeric is not None:
                    cg_values.append(numeric)
        else:
            numeric = _numeric(value)
            if numeric is not None:
                cg_values.append(numeric)
    if cg_values:
        result["mean_cg_iterations"] = statistics.fmean(cg_values)

    for metric, names in {
        "u_t": ("u_t", "policy_transfer_factor"),
        "diagnostic_u_t": ("posthoc_transfer_factor_one_plus_chi_squared",),
        "psi_t": ("bar_psi_t", "psi_t", "posthoc_primitive_psi"),
        "chi_t": ("bar_chi_t", "chi_t", "posthoc_chi_operator_norm"),
    }.items():
        values = [
            value
            for metrics in prefix
            if (value := _last_numeric(metrics, names)) is not None
        ]
        if values:
            result[f"mean_{metric}"] = statistics.fmean(values)
            result[f"max_{metric}"] = max(values)
            result[metric] = values[-1]

    theory_factors: list[float] = []
    for metrics in prefix:
        alpha = _last_numeric(metrics, ("alpha_t",))
        transfer = _last_numeric(metrics, ("u_t", "policy_transfer_factor"))
        omega = _last_numeric(metrics, ("omega_t", "policy_omega"))
        if alpha is None:
            epsilon = _last_numeric(metrics, ("policy_cg_energy_tolerance",))
            if epsilon is not None and 0.0 <= epsilon < 1.0:
                alpha = math.sqrt((1.0 + epsilon) / (1.0 - epsilon))
        if alpha is not None and transfer is not None and omega is not None:
            theory_factors.append(alpha * alpha * transfer * omega * omega)
    if theory_factors:
        result["mean_theory_factor"] = statistics.fmean(theory_factors)
        result["max_theory_factor"] = max(theory_factors)
        result["theory_factor"] = theory_factors[-1]
        result.setdefault("S_T", float(sum(theory_factors)))
    return result


def _summary_metrics(summary: Mapping[str, Any]) -> dict[str, float]:
    result = {
        key: numeric
        for key, value in summary.items()
        if (numeric := _numeric(value)) is not None
    }
    aliases = {
        "theorem_rhs": (
            "theorem_rhs",
            "theorem_rhs_posthoc",
            "theorem_rhs_policy_schedule",
        ),
        "Lambda_alg_T": ("Lambda_alg_T", "Lambda_alg_cumulative"),
        "S_T": ("S_T", "S_t_cumulative"),
        "optimism_violation_rate": (
            "selected_action_optimism_violation_rate",
            "optimism_violation_rate",
            "all_action_optimism_violation_rate",
            "policy_optimism_violation_rate",
        ),
    }
    for target, names in aliases.items():
        value = _last_numeric(summary, names)
        if value is not None:
            result[target] = value
    return result


def _aggregate_metric_maps(values: Sequence[Mapping[str, float]]) -> dict[str, Any]:
    names = sorted({name for value in values for name in value})
    return {
        name: student_t_interval(value[name] for value in values if name in value)
        for name in names
    }


def _requested_horizons(run: LoadedRun) -> tuple[int, ...]:
    raw_horizons = run.config.get("horizons", ())
    horizons: set[int] = {len(run.raw)}
    if isinstance(raw_horizons, Sequence) and not isinstance(raw_horizons, (str, bytes)):
        for value in raw_horizons:
            if isinstance(value, int) and not isinstance(value, bool) and 0 < value <= len(run.raw):
                horizons.add(value)
    return tuple(sorted(horizons))


def _group_key(run: LoadedRun) -> str:
    return canonical_json(
        {
            "experiment": run.experiment,
            "profile": run.profile,
            "seed_set": run.seed_set,
            "comparison": run.comparison,
            "method": run.method,
            "variant": run.variant,
            "hyperparameters": run.hyperparameters,
        }
    )


def _paired_reference(experiment: str) -> str | None:
    if experiment == "balanced_benchmark":
        return "cc_ucb_full_ggn_cg"
    if experiment == "linear_audit" or experiment.startswith("linear_"):
        return "dense_full"
    if "covertype" in experiment.lower():
        return "full_network_ggn_cg"
    return None


def _subtract_metric_maps(
    candidate: Mapping[str, float], reference: Mapping[str, float]
) -> dict[str, float]:
    return {
        name: float(candidate[name] - reference[name])
        for name in sorted(set(candidate) & set(reference))
    }


def _paired_comparisons(
    grouped: Mapping[str, Sequence[LoadedRun]],
) -> list[dict[str, Any]]:
    families: dict[tuple[str, str, str, str], list[tuple[str, Sequence[LoadedRun]]]] = (
        defaultdict(list)
    )
    for key, members in grouped.items():
        first = members[0]
        families[
            (first.experiment, first.profile, first.seed_set, first.comparison)
        ].append((key, members))

    results: list[dict[str, Any]] = []
    for family, group_entries in sorted(families.items()):
        experiment, profile, seed_set, comparison = family
        reference_method = _paired_reference(experiment)
        if reference_method is None:
            continue
        references = [
            (key, members)
            for key, members in group_entries
            if members[0].method == reference_method
        ]
        if not references:
            if len(group_entries) > 1:
                raise AggregationError(
                    f"{experiment}/{comparison} has multiple methods but no paired "
                    f"reference {reference_method}"
                )
            continue
        if len(references) != 1:
            raise AggregationError(
                f"{experiment}/{comparison} has ambiguous {reference_method} references"
            )
        _, reference_members = references[0]
        reference_by_seed = {run.seed: run for run in reference_members}
        for _, candidate_members in sorted(
            group_entries, key=lambda entry: _group_key(entry[1][0])
        ):
            candidate_first = candidate_members[0]
            if candidate_first.method == reference_method:
                continue
            candidate_by_seed = {run.seed: run for run in candidate_members}
            if set(candidate_by_seed) != set(reference_by_seed):
                raise AggregationError(
                    f"paired comparison {candidate_first.method} - {reference_method} "
                    "does not use identical evaluation seeds"
                )
            seeds = sorted(candidate_by_seed)
            if candidate_first.declared_seeds != reference_members[0].declared_seeds:
                raise AggregationError("paired comparison has inconsistent declared seeds")

            summary_differences = [
                _subtract_metric_maps(
                    _summary_metrics(candidate_by_seed[seed].summary),
                    _summary_metrics(reference_by_seed[seed].summary),
                )
                for seed in seeds
            ]
            candidate_horizons = [
                set(_requested_horizons(candidate_by_seed[seed])) for seed in seeds
            ]
            reference_horizons = [
                set(_requested_horizons(reference_by_seed[seed])) for seed in seeds
            ]
            shared_horizons = set.intersection(
                *candidate_horizons, *reference_horizons
            )
            horizon_records: list[dict[str, Any]] = []
            for horizon in sorted(shared_horizons):
                differences = [
                    _subtract_metric_maps(
                        prefix_metrics(candidate_by_seed[seed].raw, horizon),
                        prefix_metrics(reference_by_seed[seed].raw, horizon),
                    )
                    for seed in seeds
                ]
                metrics = _aggregate_metric_maps(differences)
                horizon_records.append(
                    {
                        "horizon": horizon,
                        "metrics": metrics,
                        "theorem_components": _theorem_components(metrics),
                        "runtime_components": _runtime_components(metrics),
                    }
                )
            summary_metrics = _aggregate_metric_maps(summary_differences)
            directories = sorted(
                {
                    str(run.directory)
                    for run in (*candidate_members, *reference_members)
                }
            )
            results.append(
                {
                    "experiment": experiment,
                    "profile": profile,
                    "seed_set": seed_set,
                    "comparison": comparison,
                    "method": candidate_first.method,
                    "reference_method": reference_method,
                    "difference_direction": "method_minus_reference",
                    "variant": candidate_first.variant,
                    "hyperparameters": candidate_first.hyperparameters,
                    "reference_hyperparameters": reference_members[0].hyperparameters,
                    "seeds": seeds,
                    "declared_seeds": list(candidate_first.declared_seeds),
                    "pair_count": len(seeds),
                    "complete_common_seed_set": set(seeds)
                    == set(candidate_first.declared_seeds),
                    "summary_metrics": summary_metrics,
                    "theorem_components": _theorem_components(summary_metrics),
                    "runtime_components": _runtime_components(summary_metrics),
                    "horizons": horizon_records,
                    "run_directories": directories,
                }
            )
    return results


THEOREM_COMPONENT_NAMES = (
    "cumulative_pseudo_regret",
    "theorem_rhs",
    "diagnostic_theorem_rhs",
    "Lambda_alg_T",
    "S_T",
    "diagnostic_S_T",
    "E_T",
    "F_T",
    "V_alg_T",
    "Gamma_dynamic_T",
    "u_t",
    "max_u_t",
    "diagnostic_u_t",
    "max_diagnostic_u_t",
    "psi_t",
    "max_psi_t",
    "chi_t",
    "max_chi_t",
    "theory_factor",
    "max_theory_factor",
    "optimism_violation_rate",
)

RUNTIME_COMPONENT_NAMES = (
    "runtime_seconds",
    "mean_round_runtime_seconds",
    "mean_cg_iterations",
    "operator_matvecs",
    "sample_cvps",
    "peak_memory_bytes",
)


def _theorem_components(metrics: Mapping[str, Any]) -> dict[str, Any]:
    keywords = (
        "theorem",
        "lambda_alg",
        "gamma_dynamic",
        "variation",
        "optimism",
        "transfer",
        "theory_factor",
    )
    return {
        name: value
        for name, value in metrics.items()
        if name in THEOREM_COMPONENT_NAMES
        or any(keyword in name.lower() for keyword in keywords)
    }


def _runtime_components(metrics: Mapping[str, Any]) -> dict[str, Any]:
    keywords = ("runtime", "seconds", "iteration", "matvec", "memory", "cvp")
    return {
        name: value
        for name, value in metrics.items()
        if name in RUNTIME_COMPONENT_NAMES
        or any(keyword in name.lower() for keyword in keywords)
    }


def _average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average = ((start + 1) + end) / 2.0
        for position in range(start, end):
            ranks[order[position]] = average
        start = end
    return ranks


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        raise AggregationError("correlation requires equal vectors of length at least two")
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right, strict=True)
    )
    left_sum = sum((value - left_mean) ** 2 for value in left)
    right_sum = sum((value - right_mean) ** 2 for value in right)
    denominator = math.sqrt(left_sum * right_sum)
    if denominator == 0.0:
        raise AggregationError("correlation is undefined for a constant vector")
    return float(numerator / denominator)


def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    return _pearson(_average_ranks(left), _average_ranks(right))


def _nonlinear_hypothesis_audits(
    groups: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    nonlinear = [
        group
        for group in groups
        if "nonlinear" in str(group.get("experiment", "")).lower()
    ]
    if not nonlinear:
        return []
    drift_order = {"frozen_head": 0, "mild": 1, "medium": 2, "aggressive": 3}
    cells: list[dict[str, Any]] = []
    for group in nonlinear:
        final = group.get("horizons", [])
        if not isinstance(final, Sequence) or not final:
            continue
        final_record = max(
            (item for item in final if isinstance(item, Mapping)),
            key=lambda item: int(item.get("horizon", 0)),
        )
        final_metrics = final_record.get("metrics", {})
        summary = group.get("summary_metrics", {})
        if not isinstance(final_metrics, Mapping) or not isinstance(summary, Mapping):
            continue

        def mean_from(*candidates: tuple[Mapping[str, Any], str]) -> float | None:
            for source, name in candidates:
                stats = source.get(name)
                if isinstance(stats, Mapping) and isinstance(stats.get("mean"), (int, float)):
                    value = float(stats["mean"])
                    if math.isfinite(value):
                        return value
            return None

        regret = mean_from((summary, "cumulative_pseudo_regret"), (final_metrics, "cumulative_pseudo_regret"))
        schedule_rhs = mean_from((summary, "theorem_rhs_policy_schedule"), (summary, "theorem_rhs"), (final_metrics, "theorem_rhs"))
        relative_change = mean_from(
            (final_metrics, "posthoc_whitened_curvature_difference_operator_norm"),
        )
        optimism = mean_from(
            (summary, "policy_optimism_violation_rate"),
            (summary, "optimism_violation_rate"),
            (final_metrics, "optimism_violation_rate"),
        )
        if None in (regret, schedule_rhs, relative_change, optimism):
            continue
        variant = group.get("variant", {})
        center = (
            str(variant.get("center", "default"))
            if isinstance(variant, Mapping)
            else "default"
        )
        cells.append(
            {
                "regime": str(group.get("method", "unknown")),
                "center": center,
                "mean_cumulative_pseudo_regret": regret,
                "mean_policy_schedule_theorem_rhs": schedule_rhs,
                "mean_posthoc_relative_curvature_change_operator_norm": relative_change,
                "mean_policy_optimism_violation_rate": optimism,
                "run_directories": list(group.get("run_directories", [])),
            }
        )
    cells.sort(
        key=lambda cell: (
            drift_order.get(cell["regime"], 99),
            0 if cell["center"] == "original" else 1,
            cell["center"],
        )
    )
    if len(cells) < 2:
        return []
    regret_values = [cell["mean_cumulative_pseudo_regret"] for cell in cells]
    schedule_values = [cell["mean_policy_schedule_theorem_rhs"] for cell in cells]
    relative_values = [
        cell["mean_posthoc_relative_curvature_change_operator_norm"] for cell in cells
    ]
    optimism_monotonic: dict[str, bool] = {}
    for center in sorted({cell["center"] for cell in cells}):
        ordered = [
            cell["mean_policy_optimism_violation_rate"]
            for cell in cells
            if cell["center"] == center and cell["regime"] in drift_order
        ]
        optimism_monotonic[center] = len(ordered) == len(drift_order) and all(
            left <= right for left, right in zip(ordered, ordered[1:])
        )
    directories = sorted(
        {
            directory
            for cell in cells
            for directory in cell.pop("run_directories", [])
        }
    )
    schedule_rho = _spearman(regret_values, schedule_values)
    relative_rho = _spearman(regret_values, relative_values)
    return [
        {
            "name": "nonlinear_regime_center_rank_audit",
            "experiment": str(nonlinear[0].get("experiment", "nonlinear")),
            "profile": str(nonlinear[0].get("profile", "")),
            "seed_set": str(nonlinear[0].get("seed_set", "")),
            "analysis": "descriptive_tie_aware_spearman_rank_correlation",
            "analysis_unit": "regime_center_cell_mean",
            "n_cells": len(cells),
            "causal": False,
            "independent_cells": False,
            "inferential_p_value_reported": False,
            "warnings": [
                "descriptive only",
                "non-causal",
                "regime/center cells reuse common evaluation seeds and are not independent",
            ],
            "outcome": "mean_cumulative_pseudo_regret",
            "correlations": [
                {
                    "predictor": "mean_policy_schedule_theorem_rhs",
                    "spearman_rho": schedule_rho,
                    "n": len(cells),
                },
                {
                    "predictor": "mean_posthoc_relative_curvature_change_operator_norm",
                    "spearman_rho": relative_rho,
                    "n": len(cells),
                },
            ],
            "hypotheses": [
                {
                    "name": "policy_schedule_rhs_has_stronger_rank_alignment_with_regret_than_relative_curvature_change",
                    "status": "descriptively_supported_not_inferential",
                    "evidence": {
                        "schedule_rhs_spearman_rho": schedule_rho,
                        "relative_curvature_change_spearman_rho": relative_rho,
                    },
                },
                {
                    "name": "optimism_violation_rate_increases_monotonically_with_drift",
                    "status": (
                        "supported"
                        if all(optimism_monotonic.values())
                        else "failed_or_mixed"
                    ),
                    "monotone_non_decreasing_by_center": optimism_monotonic,
                },
            ],
            "cells": cells,
            "run_directories": directories,
        }
    ]


def _aggregate_operator_directories(
    directories: Sequence[Path], seed_set: str | None
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for directory in directories:
        header = _compact_header(directory)
        if seed_set is not None and header["seed_set"] != seed_set:
            continue
        summary = header["summary"]
        offline = summary.get("offline_diagnostic") is True
        if offline:
            if (
                summary.get("executed_policy") is not False
                or summary.get("causal_regret_claim") is not False
                or summary.get("regret_reported") is not False
            ):
                raise AggregationError(f"unsafe offline claims in {directory}")
        elif summary.get("executed_policy") is not True:
            raise AggregationError(f"operator policy lacks executed-policy claim: {directory}")
        trajectory_digest = summary.get("trajectory_digest") if offline else None
        final_record: dict[str, Any] | None = None
        count = 0
        for record in _iter_jsonl(directory / "raw.jsonl"):
            if record.get("round") != count:
                raise AggregationError(f"noncontiguous operator rounds in {directory}")
            metrics = _record_metrics(record)
            if offline:
                if (
                    metrics.get("executed_policy") is not False
                    or metrics.get("offline_diagnostic") is not True
                    or metrics.get("causal_regret_claim") is not False
                    or metrics.get("regret_reported") is not False
                    or metrics.get("trajectory_digest") != trajectory_digest
                ):
                    raise AggregationError(f"unsafe offline raw record in {directory}")
            elif metrics.get("executed_policy") is not True:
                raise AggregationError(f"operator raw record is not an executed policy: {directory}")
            final_record = record
            count += 1
        if count != int(header["config"].get("rounds", -1)) or final_record is None:
            raise AggregationError(f"incomplete operator trajectory in {directory}")
        operator = summary.get("operator")
        if not isinstance(operator, str) or not operator:
            raise AggregationError(f"operator summary has no operator name: {directory}")
        environment = summary.get(
            "environment", header["config"].get("environment_family", "bounded_linear")
        )
        if not isinstance(environment, str) or not environment:
            raise AggregationError(f"operator summary has no environment family: {directory}")
        records.append(
            {
                **header,
                "offline": offline,
                "operator": operator,
                "environment": environment,
                "regime": summary.get("regime"),
                "center": summary.get("center"),
                "variant": {
                    key: summary[key]
                    for key in (
                        "operator_kind",
                        "operator_parameter",
                        "regime",
                        "center",
                    )
                    if summary.get(key) is not None
                },
                "summary_metrics": _summary_metrics(summary),
                "final_metrics": prefix_metrics((final_record,), 1),
                "rounds": count,
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = canonical_json(
            {
                "offline": record["offline"],
                "environment": record["environment"],
                "regime": record["regime"],
                "center": record["center"],
                "operator": record["operator"],
                "variant": record["variant"],
            }
        )
        grouped[key].append(record)
    online_groups: list[dict[str, Any]] = []
    offline_groups: list[dict[str, Any]] = []
    for key in sorted(grouped):
        members = sorted(grouped[key], key=lambda record: record["seed"])
        first = members[0]
        seeds = [record["seed"] for record in members]
        declared = first["declared_seeds"]
        if len(seeds) != len(set(seeds)):
            raise AggregationError("duplicate operator seed")
        metrics = _aggregate_metric_maps(
            [record["final_metrics"] for record in members]
        )
        summary_metrics = _aggregate_metric_maps(
            [record["summary_metrics"] for record in members]
        )
        group = {
            "experiment": first["experiment"],
            "profile": first["profile"],
            "seed_set": first["seed_set"],
            "comparison": "default",
            "environment": first["environment"],
            "method": first["operator"],
            "variant": first["variant"],
            "hyperparameters": {},
            "seeds": seeds,
            "declared_seeds": list(declared),
            "run_count": len(members),
            "complete_declared_seed_set": set(seeds) == set(declared),
            "summary_metrics": summary_metrics,
            "theorem_components": _theorem_components(summary_metrics),
            "runtime_components": _runtime_components(summary_metrics),
            "horizons": [
                {
                    "horizon": first["rounds"],
                    "metrics": metrics,
                    "theorem_components": _theorem_components(metrics),
                    "runtime_components": _runtime_components(metrics),
                }
            ],
            "run_directories": [str(record["directory"]) for record in members],
        }
        if first["offline"]:
            group.update(
                {
                    "executed_policy": False,
                    "offline_diagnostic": True,
                    "causal_regret_claim": False,
                    "regret_reported": False,
                    "aggregation_role": "offline_common_trajectory_diagnostic_only",
                }
            )
            offline_groups.append(group)
        else:
            group["executed_policy"] = True
            online_groups.append(group)

    paired_comparisons: list[dict[str, Any]] = []
    online_records = [record for record in records if not record["offline"]]
    families: dict[tuple[str, Any, Any], list[dict[str, Any]]] = defaultdict(list)
    for record in online_records:
        families[
            (record["environment"], record["regime"], record["center"])
        ].append(record)
    for (environment, regime, center), members in sorted(
        families.items(), key=lambda item: tuple(str(value) for value in item[0])
    ):
        references = [
            record
            for record in members
            if record["summary"].get("operator_kind") == "full"
        ]
        reference_operators = {record["operator"] for record in references}
        if len(reference_operators) != 1:
            raise AggregationError(
                f"operator family {environment}/{regime}/{center} must have one "
                "full-reference operator"
            )
        reference_method = next(iter(reference_operators))
        reference_by_seed = {record["seed"]: record for record in references}
        operators = sorted({record["operator"] for record in members})
        for operator in operators:
            if operator == reference_method:
                continue
            candidates = [record for record in members if record["operator"] == operator]
            candidate_by_seed = {record["seed"]: record for record in candidates}
            if set(candidate_by_seed) != set(reference_by_seed):
                raise AggregationError(
                    f"paired operator comparison {operator} - {reference_method} "
                    f"lacks identical seeds in {environment}"
                )
            seeds = sorted(reference_by_seed)
            summary_differences = [
                _subtract_metric_maps(
                    candidate_by_seed[seed]["summary_metrics"],
                    reference_by_seed[seed]["summary_metrics"],
                )
                for seed in seeds
            ]
            final_differences = [
                _subtract_metric_maps(
                    candidate_by_seed[seed]["final_metrics"],
                    reference_by_seed[seed]["final_metrics"],
                )
                for seed in seeds
            ]
            paired_comparisons.append(
                {
                    "experiment": "operator_ablation",
                    "profile": candidates[0]["profile"],
                    "seed_set": candidates[0]["seed_set"],
                    "comparison": "fixed_reference_bonus_and_damping",
                    "environment": environment,
                    "regime": regime,
                    "center": center,
                    "method": operator,
                    "reference_method": reference_method,
                    "difference_direction": "method_minus_reference",
                    "seeds": seeds,
                    "declared_seeds": list(candidates[0]["declared_seeds"]),
                    "pair_count": len(seeds),
                    "complete_common_seed_set": set(seeds)
                    == set(candidates[0]["declared_seeds"]),
                    "summary_metrics": _aggregate_metric_maps(summary_differences),
                    "horizons": [
                        {
                            "horizon": candidates[0]["rounds"],
                            "metrics": _aggregate_metric_maps(final_differences),
                        }
                    ],
                    "run_directories": sorted(
                        {
                            str(record["directory"])
                            for record in (*candidates, *references)
                        }
                    ),
                }
            )

    offline_records = [record for record in records if record["offline"]]
    digests_by_seed: dict[tuple[str, Any, Any, int], set[str]] = defaultdict(set)
    for record in offline_records:
        key = (
            record["environment"],
            record["regime"],
            record["center"],
            record["seed"],
        )
        digests_by_seed[key].add(str(record["summary"]["trajectory_digest"]))
    if any(len(digests) != 1 for digests in digests_by_seed.values()):
        raise AggregationError("offline operator diagnostics do not share one trajectory per seed")
    return {
        "online_groups": online_groups,
        "offline_groups": offline_groups,
        "online_run_count": sum(len(group["seeds"]) for group in online_groups),
        "offline_run_count": len(offline_records),
        "paired_comparisons": paired_comparisons,
        "directories": [record["directory"] for record in records],
        "profiles": sorted({record["profile"] for record in records}),
        "seed_sets": sorted({record["seed_set"] for record in records}),
        "experiments": sorted({record["experiment"] for record in records}),
    }


def _aggregate_cg_directories(
    directories: Sequence[Path], seed_set: str | None
) -> dict[str, Any]:
    metric_sources = {
        "mean_cg_iterations": "cg_iterations",
        "mean_initial_relative_energy_error": "initial_relative_energy_error",
        "mean_exact_relative_energy_error": "exact_relative_energy_error",
        "mean_wall_time_seconds": "wall_time_seconds",
        "mean_sample_cvp_count": "sample_cvp_count",
        "mean_predictive_width_relative_error": "predictive_width_relative_error",
    }
    cells: dict[tuple[float, float, str, str], dict[int, dict[str, float]]] = defaultdict(dict)
    run_directories: list[Path] = []
    declared_seeds: tuple[int, ...] | None = None
    profiles: set[str] = set()
    seed_sets: set[str] = set()
    validation_totals = {
        "target_failure_count": 0,
        "certificate_target_failure_count": 0,
        "residual_certificate_violation_count": 0,
        "sandwich_violation_count": 0,
        "optimism_violation_count": 0,
    }
    for directory in directories:
        header = _compact_header(directory)
        if seed_set is not None and header["seed_set"] != seed_set:
            continue
        if header["experiment"] != "cg_accuracy":
            raise AggregationError(f"unexpected CG experiment in {directory}")
        summary = header["summary"]
        if "executed_policy" in summary:
            raise AggregationError("CG accuracy artifacts must remain diagnostics")
        accumulators: dict[tuple[float, float, str, str], dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "sums": defaultdict(float), "peak_memory": 0.0}
        )
        count = 0
        for record in _iter_jsonl(directory / "raw.jsonl"):
            if record.get("round") != count:
                raise AggregationError(f"noncontiguous CG rows in {directory}")
            metrics = _record_metrics(record)
            if "executed_policy" in metrics:
                raise AggregationError("CG diagnostic row contains a policy-execution claim")
            key = (
                float(metrics["condition_number_requested"]),
                float(metrics.get("target_energy_error", metrics["epsilon_bar"])),
                str(metrics["initialization"]),
                str(metrics["preconditioner"]),
            )
            accumulator = accumulators[key]
            accumulator["count"] += 1
            for output_name, source_name in metric_sources.items():
                accumulator["sums"][output_name] += float(metrics[source_name])
            accumulator["peak_memory"] = max(
                accumulator["peak_memory"],
                float(metrics.get("peak_host_memory_bytes", 0.0)),
            )
            count += 1
        if count != int(summary.get("record_count", -1)):
            raise AggregationError(f"CG raw/summary record count mismatch in {directory}")
        for key, accumulator in accumulators.items():
            cell_count = accumulator["count"]
            values = {
                name: total / cell_count
                for name, total in accumulator["sums"].items()
            }
            values["peak_host_memory_bytes"] = accumulator["peak_memory"]
            values["records_per_seed"] = float(cell_count)
            cells[key][header["seed"]] = values
        for name in validation_totals:
            validation_totals[name] += int(summary.get(name, 0))
        if summary.get("warm_start_advantage_assumed") is not False:
            raise AggregationError("CG summary improperly assumes a warm-start advantage")
        run_directories.append(directory)
        profiles.add(header["profile"])
        seed_sets.add(header["seed_set"])
        if declared_seeds is None:
            declared_seeds = header["declared_seeds"]
        elif declared_seeds != header["declared_seeds"]:
            raise AggregationError("inconsistent CG seed provenance")

    if not cells or declared_seeds is None:
        return {"groups": [], "audits": [], "run_count": 0, "directories": []}
    groups: list[dict[str, Any]] = []
    for key in sorted(cells, key=lambda item: (item[0], -item[1], item[2], item[3])):
        condition, target, initialization, preconditioner = key
        seed_values = cells[key]
        seeds = sorted(seed_values)
        metrics = _aggregate_metric_maps([seed_values[seed] for seed in seeds])
        groups.append(
            {
                "experiment": "cg_accuracy",
                "profile": next(iter(profiles)),
                "seed_set": next(iter(seed_sets)),
                "benchmark_kind": "fixed_spd_cg_diagnostic",
                "method": "conjugate_gradient",
                "variant": {
                    "condition_number": condition,
                    "target_relative_energy_error": target,
                    "initialization": initialization,
                    "preconditioner": preconditioner,
                },
                "seeds": seeds,
                "declared_seeds": list(declared_seeds),
                "run_count": len(seeds),
                "complete_declared_seed_set": set(seeds) == set(declared_seeds),
                "summary_metrics": metrics,
                "runtime_components": _runtime_components(metrics),
                "run_directories": [str(path) for path in run_directories],
                "executed_policy": False,
                "aggregation_role": "benchmark_diagnostic_only",
            }
        )

    warm_comparisons: list[dict[str, Any]] = []
    base_keys = sorted({(key[0], key[1], key[3]) for key in cells})
    for condition, target, preconditioner in base_keys:
        zero = cells.get((condition, target, "zero", preconditioner))
        warm = cells.get((condition, target, "warm", preconditioner))
        if zero is None or warm is None or set(zero) != set(warm):
            raise AggregationError("CG warm/zero comparison lacks common seeds")
        seeds = sorted(zero)
        iteration_difference = student_t_interval(
            warm[seed]["mean_cg_iterations"] - zero[seed]["mean_cg_iterations"]
            for seed in seeds
        )
        error_difference = student_t_interval(
            warm[seed]["mean_initial_relative_energy_error"]
            - zero[seed]["mean_initial_relative_energy_error"]
            for seed in seeds
        )
        warm_comparisons.append(
            {
                "condition_number": condition,
                "target_relative_energy_error": target,
                "preconditioner": preconditioner,
                "seeds": seeds,
                "difference_direction": "warm_minus_zero",
                "mean_cg_iterations_difference": iteration_difference,
                "mean_initial_relative_energy_error_difference": error_difference,
                "warm_start_lowered_mean_iterations": iteration_difference["mean"] < 0.0,
                "warm_start_iteration_reduction_ci_excludes_zero": iteration_difference[
                    "ci95_high"
                ]
                < 0.0,
                "warm_start_lowered_initial_relative_energy_error": error_difference[
                    "mean"
                ]
                < 0.0,
            }
        )
    audit = {
        "name": "cg_accuracy_validity_and_warm_start_audit",
        "experiment": "cg_accuracy",
        "profile": next(iter(profiles)),
        "seed_set": next(iter(seed_sets)),
        "executed_policy": False,
        "analysis_unit": "evaluation_seed",
        "validation_totals": validation_totals,
        "all_target_residual_sandwich_optimism_violations_zero": all(
            value == 0 for value in validation_totals.values()
        ),
        "warm_start_advantage_assumed": False,
        "warm_start_comparisons": warm_comparisons,
        "warm_start_cells": len(warm_comparisons),
        "cells_with_lower_mean_iterations": sum(
            item["warm_start_lowered_mean_iterations"] for item in warm_comparisons
        ),
        "cells_with_iteration_reduction_ci_excluding_zero": sum(
            item["warm_start_iteration_reduction_ci_excludes_zero"]
            for item in warm_comparisons
        ),
        "run_directories": [str(path) for path in run_directories],
    }
    return {
        "groups": groups,
        "audits": [audit],
        "run_count": len(run_directories),
        "directories": run_directories,
        "profiles": sorted(profiles),
        "seed_sets": sorted(seed_sets),
        "experiments": ["cg_accuracy"],
    }


def _aggregate_systems_directories(
    directories: Sequence[Path], seed_set: str | None
) -> dict[str, Any]:
    metric_names = (
        "wall_time_seconds",
        "wall_time_min_seconds",
        "peak_host_memory_bytes",
        "peak_accelerator_memory_bytes",
        "curvature_vector_products",
        "batch_operator_call_count",
        "equivalent_sample_cvp_count",
        "sample_cvp_count",
        "cg_iterations",
        "mean_explicit_relative_residual",
        "max_explicit_relative_residual",
        "predictive_width_relative_error",
        "mean_relative_energy_error",
        "max_relative_energy_error",
        "estimated_working_memory_bytes",
        "estimated_total_host_memory_bytes",
    )
    cells: dict[
        tuple[str, int, int, int, int, str], dict[int, dict[str, float]]
    ] = defaultdict(dict)
    run_directories: list[Path] = []
    declared_seeds: tuple[int, ...] | None = None
    profiles: set[str] = set()
    seed_sets: set[str] = set()
    sandwich_violations = 0
    for directory in directories:
        header = _compact_header(directory)
        if seed_set is not None and header["seed_set"] != seed_set:
            continue
        if header["experiment"] != "systems_scaling":
            raise AggregationError(f"unexpected systems experiment in {directory}")
        summary = header["summary"]
        if summary.get("synthetic_feasibility_benchmark") is not True or summary.get(
            "foundation_model_wall_clock_claim"
        ) is not False:
            raise AggregationError("systems benchmark has unsafe scope claims")
        if "benchmark_kind" in summary and (
            summary.get("benchmark_kind")
            != "synthetic_cpu_parameter_vector_operator_benchmark"
            or summary.get("synthetic_cpu_parameter_vector_benchmark") is not True
            or summary.get("accelerator_benchmark") is not False
            or summary.get("foundation_model_benchmark") is not False
        ):
            raise AggregationError("systems benchmark has inconsistent CPU-vector scope")
        count = 0
        for record in _iter_jsonl(directory / "raw.jsonl"):
            if record.get("round") != count:
                raise AggregationError(f"noncontiguous systems rows in {directory}")
            metrics = _record_metrics(record)
            if "executed_policy" in metrics:
                raise AggregationError("systems benchmark row contains a policy claim")
            key = (
                str(metrics.get("benchmark_grid", "standard_cpu_grid")),
                int(metrics["d"]),
                int(metrics["n"]),
                int(metrics["K"]),
                int(metrics["I"]),
                str(metrics["method"]),
            )
            values = {
                name: float(metrics[name])
                for name in metric_names
                if isinstance(metrics.get(name), (int, float))
                and not isinstance(metrics.get(name), bool)
            }
            cells[key][header["seed"]] = values
            count += 1
        if count != int(summary.get("record_count", -1)):
            raise AggregationError(f"systems raw/summary count mismatch in {directory}")
        sandwich_violations += int(summary.get("width_sandwich_violation_count", 0))
        run_directories.append(directory)
        profiles.add(header["profile"])
        seed_sets.add(header["seed_set"])
        if declared_seeds is None:
            declared_seeds = header["declared_seeds"]
        elif declared_seeds != header["declared_seeds"]:
            raise AggregationError("inconsistent systems seed provenance")
    if not cells or declared_seeds is None:
        return {"groups": [], "audits": [], "run_count": 0, "directories": []}
    groups: list[dict[str, Any]] = []
    for key in sorted(cells):
        benchmark_grid, dimension, samples, actions, iterations, method = key
        seed_values = cells[key]
        seeds = sorted(seed_values)
        metrics = _aggregate_metric_maps([seed_values[seed] for seed in seeds])
        groups.append(
            {
                "experiment": "systems_scaling",
                "profile": next(iter(profiles)),
                "seed_set": next(iter(seed_sets)),
                "benchmark_kind": "synthetic_cpu_parameter_vector_operator_benchmark",
                "benchmark_grid": benchmark_grid,
                "method": method,
                "variant": {
                    "dimension": dimension,
                    "sample_count": samples,
                    "action_count": actions,
                    "iteration_budget": iterations,
                },
                "seeds": seeds,
                "declared_seeds": list(declared_seeds),
                "run_count": len(seeds),
                "complete_declared_seed_set": set(seeds) == set(declared_seeds),
                "summary_metrics": metrics,
                "runtime_components": _runtime_components(metrics),
                "run_directories": [str(path) for path in run_directories],
                "executed_policy": False,
                "aggregation_role": "benchmark_diagnostic_only",
            }
        )
    audit = {
        "name": "systems_scaling_scope_and_sandwich_audit",
        "experiment": "systems_scaling",
        "profile": next(iter(profiles)),
        "seed_set": next(iter(seed_sets)),
        "executed_policy": False,
        "synthetic_feasibility_benchmark": True,
        "foundation_model_wall_clock_claim": False,
        "width_sandwich_violation_count": sandwich_violations,
        "all_width_sandwich_checks_hold": sandwich_violations == 0,
        "run_directories": [str(path) for path in run_directories],
    }
    return {
        "groups": groups,
        "audits": [audit],
        "run_count": len(run_directories),
        "directories": run_directories,
        "profiles": sorted(profiles),
        "seed_sets": sorted(seed_sets),
        "experiments": ["systems_scaling"],
    }


def aggregate_loaded_runs(runs: Sequence[LoadedRun]) -> dict[str, Any]:
    if not runs:
        raise AggregationError("no runs selected for aggregation")
    grouped: dict[str, list[LoadedRun]] = defaultdict(list)
    for run in runs:
        grouped[_group_key(run)].append(run)
    groups: list[dict[str, Any]] = []
    for key in sorted(grouped):
        members = sorted(grouped[key], key=lambda run: run.seed)
        seeds = [run.seed for run in members]
        if len(seeds) != len(set(seeds)):
            raise AggregationError(f"duplicate seed in aggregate group: {seeds}")
        first = members[0]
        declared = first.declared_seeds
        if any(run.declared_seeds != declared for run in members):
            raise AggregationError("inconsistent declared seed provenance within a group")
        horizon_sets = [_requested_horizons(run) for run in members]
        shared_horizons = set(horizon_sets[0]).intersection(*map(set, horizon_sets[1:]))
        if not shared_horizons:
            raise AggregationError("group has no shared horizon prefix")
        horizon_records: list[dict[str, Any]] = []
        for horizon in sorted(shared_horizons):
            metrics = _aggregate_metric_maps(
                [prefix_metrics(run.raw, horizon) for run in members]
            )
            horizon_records.append(
                {
                    "horizon": horizon,
                    "metrics": metrics,
                    "theorem_components": _theorem_components(metrics),
                    "runtime_components": _runtime_components(metrics),
                }
            )
        summary_metrics = _aggregate_metric_maps(
            [_summary_metrics(run.summary) for run in members]
        )
        groups.append(
            {
                "experiment": first.experiment,
                "profile": first.profile,
                "seed_set": first.seed_set,
                "comparison": first.comparison,
                "method": first.method,
                "variant": first.variant,
                "hyperparameters": first.hyperparameters,
                "seeds": seeds,
                "declared_seeds": list(declared),
                "run_count": len(members),
                "complete_declared_seed_set": set(seeds) == set(declared),
                "summary_metrics": summary_metrics,
                "theorem_components": _theorem_components(summary_metrics),
                "runtime_components": _runtime_components(summary_metrics),
                "horizons": horizon_records,
                "run_directories": [str(run.directory) for run in members],
            }
        )
    paired_comparisons = _paired_comparisons(grouped)
    hypothesis_audits = _nonlinear_hypothesis_audits(groups)
    return {
        "schema_version": 1,
        "event": "executed_policy_aggregate",
        "confidence_interval": "two-sided 95% Student-t",
        "run_count": len(runs),
        "group_count": len(groups),
        "profiles": sorted({run.profile for run in runs}),
        "seed_sets": sorted({run.seed_set for run in runs}),
        "experiments": sorted({run.experiment for run in runs}),
        "all_runs_executed_policy": True,
        "all_seed_provenance_disjoint": True,
        "all_groups_complete": all(group["complete_declared_seed_set"] for group in groups),
        "paired_comparison_count": len(paired_comparisons),
        "all_paired_comparisons_complete": all(
            comparison["complete_common_seed_set"]
            for comparison in paired_comparisons
        ),
        "groups": groups,
        "paired_comparisons": paired_comparisons,
        "hypothesis_audits": hypothesis_audits,
    }


def aggregate_results(
    input_root: str | Path,
    *,
    seed_set: str | None = "evaluation",
) -> dict[str, Any]:
    """Load, validate, and aggregate all selected runs below ``input_root``."""

    if seed_set not in {None, "tuning", "evaluation"}:
        raise AggregationError("seed_set must be tuning, evaluation, or None")
    directories = discover_run_directories(input_root)
    categorized: dict[str, list[Path]] = defaultdict(list)
    for directory in directories:
        manifests = _read_jsonl(directory / "manifest.jsonl")
        if len(manifests) != 1 or not isinstance(manifests[0].get("config"), Mapping):
            raise AggregationError(f"malformed manifest in {directory}")
        experiment = str(manifests[0]["config"].get("name", ""))
        category = (
            experiment
            if experiment in {"operator_ablation", "cg_accuracy", "systems_scaling"}
            else "regular"
        )
        categorized[category].append(directory)

    loaded = [load_run(directory) for directory in categorized.get("regular", [])]
    selected_all = [run for run in loaded if seed_set is None or run.seed_set == seed_set]
    selected = [run for run in selected_all if run.executed_policy]
    offline = [run for run in selected_all if not run.executed_policy]
    if selected:
        aggregate = aggregate_loaded_runs(selected)
    else:
        aggregate = {
            "schema_version": 1,
            "event": "diagnostic_aggregate",
            "confidence_interval": "two-sided 95% Student-t",
            "run_count": 0,
            "group_count": 0,
            "profiles": [],
            "seed_sets": [],
            "experiments": [],
            "all_runs_executed_policy": False,
            "all_seed_provenance_disjoint": True,
            "all_groups_complete": True,
            "paired_comparison_count": 0,
            "all_paired_comparisons_complete": True,
            "groups": [],
            "paired_comparisons": [],
            "hypothesis_audits": [],
        }
    selected_directories: set[Path] = {run.directory for run in selected_all}
    if offline:
        digests_by_seed: dict[int, set[str]] = defaultdict(set)
        for run in offline:
            digest = run.summary.get("trajectory_digest")
            if isinstance(digest, str):
                digests_by_seed[run.seed].add(digest)
        inconsistent = {
            seed: sorted(digests)
            for seed, digests in digests_by_seed.items()
            if len(digests) != 1
        }
        if inconsistent:
            raise AggregationError(
                f"offline operators do not share one trajectory per seed: {inconsistent}"
            )
        offline_aggregate = aggregate_loaded_runs(offline)
        offline_groups = offline_aggregate["groups"]
        for group in offline_groups:
            group["executed_policy"] = False
            group["offline_diagnostic"] = True
            group["causal_regret_claim"] = False
            group["regret_reported"] = False
            group["aggregation_role"] = "offline_common_trajectory_diagnostic_only"
        aggregate["offline_diagnostic_run_count"] = len(offline)
        aggregate["offline_diagnostic_group_count"] = len(offline_groups)
        aggregate["offline_common_trajectory_validated"] = True
        aggregate["offline_diagnostic_groups"] = offline_groups
    else:
        aggregate["offline_diagnostic_run_count"] = 0
        aggregate["offline_diagnostic_group_count"] = 0
        aggregate["offline_common_trajectory_validated"] = True
        aggregate["offline_diagnostic_groups"] = []

    operator_result = _aggregate_operator_directories(
        categorized.get("operator_ablation", []), seed_set
    )
    aggregate["groups"].extend(operator_result.get("online_groups", []))
    aggregate["offline_diagnostic_groups"].extend(
        operator_result.get("offline_groups", [])
    )
    aggregate["run_count"] += int(operator_result.get("online_run_count", 0))
    aggregate["offline_diagnostic_run_count"] += int(
        operator_result.get("offline_run_count", 0)
    )
    aggregate["offline_diagnostic_group_count"] = len(
        aggregate["offline_diagnostic_groups"]
    )
    aggregate["paired_comparisons"].extend(
        operator_result.get("paired_comparisons", [])
    )
    aggregate["paired_comparison_count"] = len(aggregate["paired_comparisons"])
    aggregate["all_paired_comparisons_complete"] = all(
        comparison["complete_common_seed_set"]
        for comparison in aggregate["paired_comparisons"]
    )
    selected_directories.update(operator_result.get("directories", []))

    cg_result = _aggregate_cg_directories(categorized.get("cg_accuracy", []), seed_set)
    systems_result = _aggregate_systems_directories(
        categorized.get("systems_scaling", []), seed_set
    )
    benchmark_groups = [
        *cg_result.get("groups", []),
        *systems_result.get("groups", []),
    ]
    benchmark_audits = [
        *cg_result.get("audits", []),
        *systems_result.get("audits", []),
    ]
    aggregate["benchmark_diagnostic_groups"] = benchmark_groups
    aggregate["benchmark_diagnostic_audits"] = benchmark_audits
    aggregate["benchmark_diagnostic_run_count"] = int(
        cg_result.get("run_count", 0)
    ) + int(systems_result.get("run_count", 0))
    aggregate["benchmark_diagnostic_group_count"] = len(benchmark_groups)
    selected_directories.update(cg_result.get("directories", []))
    selected_directories.update(systems_result.get("directories", []))

    if not selected_directories:
        raise AggregationError(f"no {seed_set or 'selected'} runs found below {input_root}")
    aggregate["group_count"] = len(aggregate["groups"])
    aggregate["all_groups_complete"] = all(
        group["complete_declared_seed_set"] for group in aggregate["groups"]
    )
    aggregate["all_runs_executed_policy"] = aggregate["run_count"] > 0
    aggregate["event"] = (
        "executed_policy_aggregate"
        if aggregate["run_count"] > 0
        else "diagnostic_aggregate"
    )
    aggregate["artifact_run_count"] = len(selected_directories)
    aggregate["profiles"] = sorted(
        set(aggregate.get("profiles", []))
        | set(operator_result.get("profiles", []))
        | set(cg_result.get("profiles", []))
        | set(systems_result.get("profiles", []))
    )
    aggregate["seed_sets"] = sorted(
        set(aggregate.get("seed_sets", []))
        | set(operator_result.get("seed_sets", []))
        | set(cg_result.get("seed_sets", []))
        | set(systems_result.get("seed_sets", []))
    )
    aggregate["experiments"] = sorted(
        set(aggregate.get("experiments", []))
        | set(operator_result.get("experiments", []))
        | set(cg_result.get("experiments", []))
        | set(systems_result.get("experiments", []))
    )
    inputs = []
    for directory in sorted(selected_directories):
        for filename in REQUIRED_FILENAMES:
            path = directory / filename
            inputs.append({"path": str(path), "sha256": _sha256(path)})
    aggregate["input_root"] = str(Path(input_root))
    aggregate["inputs"] = sorted(inputs, key=lambda item: item["path"])
    aggregate["input_set_sha256"] = hashlib.sha256(
        canonical_json(aggregate["inputs"]).encode("ascii")
    ).hexdigest()
    for group in [
        *aggregate.get("groups", []),
        *aggregate.get("offline_diagnostic_groups", []),
        *aggregate.get("benchmark_diagnostic_groups", []),
    ]:
        directories = set(group.get("run_directories", []))
        group_inputs = [
            item
            for item in aggregate["inputs"]
            if str(Path(item["path"]).parent) in directories
        ]
        group["inputs"] = group_inputs
        group["input_set_sha256"] = hashlib.sha256(
            canonical_json(group_inputs).encode("ascii")
        ).hexdigest()
    for comparison in aggregate.get("paired_comparisons", []):
        directories = set(comparison.get("run_directories", []))
        paired_inputs = [
            item
            for item in aggregate["inputs"]
            if str(Path(item["path"]).parent) in directories
        ]
        comparison["inputs"] = paired_inputs
        comparison["input_set_sha256"] = hashlib.sha256(
            canonical_json(paired_inputs).encode("ascii")
        ).hexdigest()
    for audit in aggregate.get("hypothesis_audits", []):
        directories = set(audit.get("run_directories", []))
        audit_inputs = [
            item
            for item in aggregate["inputs"]
            if str(Path(item["path"]).parent) in directories
        ]
        audit["inputs"] = audit_inputs
        audit["input_set_sha256"] = hashlib.sha256(
            canonical_json(audit_inputs).encode("ascii")
        ).hexdigest()
    for audit in aggregate.get("benchmark_diagnostic_audits", []):
        directories = set(audit.get("run_directories", []))
        audit_inputs = [
            item
            for item in aggregate["inputs"]
            if str(Path(item["path"]).parent) in directories
        ]
        audit["inputs"] = audit_inputs
        audit["input_set_sha256"] = hashlib.sha256(
            canonical_json(audit_inputs).encode("ascii")
        ).hexdigest()
    return aggregate


def write_aggregate(aggregate: Mapping[str, Any], destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return path


def validate_aggregate_provenance_sidecar(
    artifact: str | Path, sidecar: str | Path | None = None
) -> dict[str, Any]:
    """Validate an aggregate digest and its complete raw-artifact inventory."""

    artifact_path = Path(artifact)
    sidecar_path = (
        artifact_path.with_suffix(artifact_path.suffix + ".provenance.json")
        if sidecar is None
        else Path(sidecar)
    )
    try:
        record = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AggregationError(f"cannot parse sidecar {sidecar_path}: {error}") from error
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        raise AggregationError("unsupported aggregate provenance sidecar")
    if record.get("artifact") != str(artifact_path):
        raise AggregationError("sidecar artifact path does not match")
    if record.get("artifact_sha256") != _sha256(artifact_path):
        raise AggregationError("sidecar artifact digest does not match")
    inputs = record.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise AggregationError("sidecar must bind at least one raw input")
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(inputs):
        if not isinstance(item, Mapping):
            raise AggregationError(f"invalid sidecar input {index}")
        path_value = item.get("path")
        digest_value = item.get("sha256")
        if not isinstance(path_value, str) or not isinstance(digest_value, str):
            raise AggregationError(f"invalid sidecar input {index}")
        input_path = Path(path_value)
        if not input_path.is_file():
            raise AggregationError(f"sidecar input is missing: {input_path}")
        if _sha256(input_path) != digest_value:
            raise AggregationError(f"sidecar input digest does not match: {input_path}")
        normalized.append({"path": path_value, "sha256": digest_value})
    if normalized != sorted(normalized, key=lambda item: item["path"]):
        raise AggregationError("sidecar inputs are not in canonical path order")
    try:
        aggregate_record = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AggregationError(f"cannot parse aggregate artifact: {error}") from error
    if not isinstance(aggregate_record, Mapping):
        raise AggregationError("aggregate artifact is not an object")
    if aggregate_record.get("inputs") != normalized:
        raise AggregationError(
            "sidecar inputs do not match the aggregate's complete raw-input inventory"
        )
    expected_input_digest = hashlib.sha256(
        canonical_json(normalized).encode("ascii")
    ).hexdigest()
    if aggregate_record.get("input_set_sha256") != expected_input_digest:
        raise AggregationError("aggregate raw-input inventory digest does not match")
    if record.get("input_set_sha256") != expected_input_digest:
        raise AggregationError("sidecar raw-input inventory digest does not match")
    return record


def write_aggregate_with_provenance(
    aggregate: Mapping[str, Any], destination: str | Path
) -> tuple[Path, Path]:
    """Write an aggregate and a SHA-256 sidecar over every raw input file."""

    inputs = aggregate.get("inputs")
    if not isinstance(inputs, Sequence) or isinstance(inputs, (str, bytes)) or not inputs:
        raise AggregationError("aggregate has no raw-input provenance")
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(inputs):
        if not isinstance(item, Mapping):
            raise AggregationError(f"invalid aggregate input {index}")
        path_value = item.get("path")
        digest_value = item.get("sha256")
        if not isinstance(path_value, str) or not isinstance(digest_value, str):
            raise AggregationError(f"invalid aggregate input {index}")
        normalized.append({"path": path_value, "sha256": digest_value})
    normalized.sort(key=lambda item: item["path"])
    expected_input_digest = hashlib.sha256(
        canonical_json(normalized).encode("ascii")
    ).hexdigest()
    if aggregate.get("input_set_sha256") != expected_input_digest:
        raise AggregationError("aggregate raw-input inventory digest does not match")
    path = write_aggregate(aggregate, destination)
    sidecar = path.with_suffix(path.suffix + ".provenance.json")
    sidecar_record = {
        "schema_version": 1,
        "artifact": str(path),
        "artifact_sha256": _sha256(path),
        "input_set_sha256": expected_input_digest,
        "inputs": normalized,
    }
    sidecar.write_text(
        json.dumps(sidecar_record, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    validate_aggregate_provenance_sidecar(path, sidecar)
    return path, sidecar


# Convenient short alias for programmatic callers.
aggregate = aggregate_results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_root", type=Path)
    parser.add_argument(
        "--seed-set", choices=("tuning", "evaluation", "all"), default="evaluation"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("results/derived/aggregate_results.json")
    )
    args = parser.parse_args(argv)
    seed_set = None if args.seed_set == "all" else args.seed_set
    result = aggregate_results(args.input_root, seed_set=seed_set)
    output, sidecar = write_aggregate_with_provenance(result, args.output)
    print(
        canonical_json(
            {
                "output": str(output),
                "provenance_sidecar": str(sidecar),
                "provenance_sidecar_sha256": _sha256(sidecar),
                "groups": result["group_count"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AggregationError",
    "LoadedRun",
    "aggregate",
    "aggregate_loaded_runs",
    "aggregate_results",
    "discover_run_directories",
    "load_run",
    "prefix_metrics",
    "student_t_interval",
    "validate_aggregate_provenance_sidecar",
    "write_aggregate",
    "write_aggregate_with_provenance",
]
