"""Strict aggregation for the nonlinear confidence-transport instantiation.

The aggregator accepts only a complete declared smoke or locked full Cartesian
product.  It revalidates each raw run, the optimizer-selection binding, every
file hash, and every deterministic audit before computing summary statistics.
Statistical confidence failures remain data; they are not run failures.
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import beta as beta_distribution

from .artifact_utils import (
    input_set_sha256,
    sha256_file,
    validate_aggregate_provenance_sidecar,
    validate_sha256_sidecar,
    write_aggregate_with_provenance,
)
from .config import config_digest, get_seed_set, load_config
from .logging_utils import canonical_json, derive_seed
from .transport_instantiation import derive_child_seed


METHODS = (
    "transport_hessian",
    "transport_endpoint",
    "frozen_reference",
    "naive_current",
)
PRIMARY_METHOD = "transport_hessian"
REQUIRED_RUN_FILES = (
    "manifest.jsonl",
    "raw.jsonl",
    "summary.json",
    "summary.json.sha256",
)
SUMMARY_EVENT = "transport_instantiation_summary"
SELECTION_EVENT = "transport_instantiation_selection"
AGGREGATE_EVENT = "transport_instantiation_aggregate"


class TransportAggregationError(ValueError):
    """Raised when the locked evaluation grid is incomplete or inconsistent."""


@dataclass(frozen=True)
class TransportRun:
    directory: Path
    manifest: dict[str, Any]
    raw: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    method: str
    seed: int
    horizon: int
    target_d: float
    width_scale: float


def _number_token(value: float) -> str:
    return format(float(value), ".12g").replace("-", "m").replace(".", "p")


def condition_directory(root: Path, horizon: int, target_d: float) -> Path:
    return root / f"T-{horizon}" / f"D-{_number_token(target_d)}"


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TransportAggregationError(f"cannot read JSON object {path}: {error}") from error
    if not isinstance(value, dict):
        raise TransportAggregationError(f"expected a JSON object in {path}")
    return value


def _load_jsonl(path: Path, *, exactly_one: bool) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise TransportAggregationError(f"cannot read {path}: {error}") from error
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise TransportAggregationError(
                f"invalid JSON in {path}:{line_number}: {error}"
            ) from error
        if not isinstance(record, dict):
            raise TransportAggregationError(f"{path}:{line_number} is not an object")
        records.append(record)
    if not records or (exactly_one and len(records) != 1):
        expected = "exactly one record" if exactly_one else "at least one record"
        raise TransportAggregationError(f"{path} must contain {expected}")
    return records


def _finite_number(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise TransportAggregationError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise TransportAggregationError(f"{name} must be finite")
    return result


def _integer(value: Any, *, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise TransportAggregationError(f"{name} must be an integer")
    result = int(value)
    if result < minimum:
        raise TransportAggregationError(f"{name} must be at least {minimum}")
    return result


def _boolean(value: Any, *, name: str) -> bool:
    if not isinstance(value, (bool, np.bool_)):
        raise TransportAggregationError(f"{name} must be boolean")
    return bool(value)


def _validate_finite_tree(value: Any, *, name: str, allow_none: bool = True) -> None:
    if value is None:
        if allow_none:
            return
        raise TransportAggregationError(f"{name} must not be null")
    if isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TransportAggregationError(f"{name} contains a non-finite value")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _validate_finite_tree(item, name=f"{name}.{key}", allow_none=allow_none)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _validate_finite_tree(item, name=f"{name}[{index}]", allow_none=allow_none)
        return
    raise TransportAggregationError(f"{name} contains unsupported type {type(value).__name__}")


def _metrics(record: Mapping[str, Any], *, path: Path, round_index: int) -> Mapping[str, Any]:
    value = record.get("metrics")
    if not isinstance(value, Mapping):
        raise TransportAggregationError(f"raw round {round_index} has no metrics in {path}")
    return value


def _lookup(source: Mapping[str, Any], *names: str, required: bool = True) -> Any:
    for name in names:
        value: Any = source
        found = True
        for component in name.split("."):
            if not isinstance(value, Mapping) or component not in value:
                found = False
                break
            value = value[component]
        if found:
            return value
    if required:
        raise TransportAggregationError(f"missing required field; tried {list(names)}")
    return None


def _expected_width(config: Mapping[str, Any], horizon: int, target_d: float) -> float:
    environment = config.get("environment")
    teacher = config.get("teacher")
    if not isinstance(environment, Mapping) or not isinstance(teacher, Mapping):
        raise TransportAggregationError("config is missing environment or teacher")
    feature_bound = _finite_number(environment.get("feature_bound"), name="feature_bound")
    radius = _finite_number(teacher.get("theta_radius"), name="theta_radius")
    sigma = _finite_number(environment.get("noise_std"), name="noise_std")
    ridge = _finite_number(config.get("ridge"), name="ridge")
    if min(feature_bound, radius, sigma, ridge, target_d) <= 0.0 or horizon <= 1:
        raise TransportAggregationError("invalid W-rule inputs")
    c_h = 4.0 * feature_bound * feature_bound / (3.0 * math.sqrt(3.0))
    numerator = 4.0 * c_h * radius * math.sqrt(horizon - 1)
    return float((numerator / (sigma * math.sqrt(ridge) * target_d)) ** 2)


def _close(left: Any, right: float, *, name: str, tolerance: float = 2e-11) -> None:
    value = _finite_number(left, name=name)
    if not math.isclose(value, right, rel_tol=tolerance, abs_tol=tolerance):
        raise TransportAggregationError(f"{name} mismatch: {value} != {right}")


def _validate_selection_candidates(
    selection: Mapping[str, Any], config: Mapping[str, Any]
) -> None:
    representation = config.get("representation_update")
    tuning = representation.get("tuning") if isinstance(representation, Mapping) else None
    if not isinstance(tuning, Mapping):
        raise TransportAggregationError("config is missing the optimizer tuning grid")
    rates = tuple(float(value) for value in tuning.get("learning_rate_grid", ()))
    steps = tuple(int(value) for value in tuning.get("steps_per_round_grid", ()))
    expected_candidates = [
        (f"candidate-{index:03d}", rate, step_count)
        for index, (rate, step_count) in enumerate(
            (pair for rate in rates for pair in ((rate, step) for step in steps))
        )
    ]
    records = selection.get("candidates")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise TransportAggregationError("selection candidates must be a list")
    if len(records) != len(expected_candidates) or selection.get("candidate_count") != len(
        expected_candidates
    ):
        raise TransportAggregationError("selection candidate grid is incomplete")
    tuning_seeds = get_seed_set(config, "tuning")
    cells = tuple(
        (int(horizon), float(target_d))
        for horizon in config.get("horizons", ())
        for target_d in config.get("target_D", ())
    )
    computed: list[dict[str, Any]] = []
    for record, (candidate_id, rate, step_count) in zip(
        records, expected_candidates, strict=True
    ):
        if not isinstance(record, Mapping):
            raise TransportAggregationError("selection candidate is malformed")
        if record.get("candidate_id") != candidate_id:
            raise TransportAggregationError(f"candidate id mismatch for {candidate_id}")
        _close(record.get("learning_rate"), rate, name=f"{candidate_id} learning rate")
        if record.get("steps_per_round") != step_count:
            raise TransportAggregationError(f"{candidate_id} step count mismatch")
        run_records = record.get("runs")
        if not isinstance(run_records, Sequence) or isinstance(run_records, (str, bytes)):
            raise TransportAggregationError(f"{candidate_id} has no run inventory")
        expected_runs = [(seed, *cell) for seed in tuning_seeds for cell in cells]
        if len(run_records) != len(expected_runs):
            raise TransportAggregationError(f"{candidate_id} tuning grid is incomplete")
        values: list[float] = []
        rejection_reasons: list[str] = []
        for run_record, (seed, horizon, target_d) in zip(
            run_records, expected_runs, strict=True
        ):
            if not isinstance(run_record, Mapping):
                raise TransportAggregationError(f"{candidate_id} run record is malformed")
            if (
                run_record.get("seed") != seed
                or run_record.get("horizon") != horizon
            ):
                raise TransportAggregationError(f"{candidate_id} run grid mismatch")
            _close(
                run_record.get("target_D"),
                target_d,
                name=f"{candidate_id} run target_D",
            )
            summary_path_value = run_record.get("summary_path")
            if not isinstance(summary_path_value, str):
                raise TransportAggregationError(f"{candidate_id} run has no summary path")
            summary_path = Path(summary_path_value)
            try:
                validate_sha256_sidecar(summary_path)
            except (OSError, ValueError) as error:
                raise TransportAggregationError(
                    f"invalid tuning summary hash {summary_path}: {error}"
                ) from error
            summary = _load_object(summary_path)
            if (
                summary.get("event") != "transport_instantiation_tuning_summary"
                or summary.get("phase") != "tuning"
                or summary.get("profile") != config.get("profile")
                or summary.get("config_digest") != config_digest(config)
                or summary.get("candidate_id") != candidate_id
                or summary.get("seed") != seed
                or summary.get("horizon") != horizon
            ):
                raise TransportAggregationError(f"tuning summary mismatch: {summary_path}")
            _close(summary.get("target_D"), target_d, name=f"{summary_path} target_D")
            valid = summary.get("valid") is True
            if run_record.get("valid") is not valid:
                raise TransportAggregationError(f"tuning validity mismatch: {summary_path}")
            criterion = summary.get("mean_all_action_prediction_mse")
            record_criterion = run_record.get("mean_all_action_prediction_mse")
            reasons = list(summary.get("rejection_reasons", ()))
            if canonical_json(run_record.get("rejection_reasons", ())) != canonical_json(reasons):
                raise TransportAggregationError(f"tuning rejection mismatch: {summary_path}")
            if valid:
                criterion_value = _finite_number(
                    criterion, name=f"{summary_path} prediction MSE"
                )
                _close(
                    record_criterion,
                    criterion_value,
                    name=f"{summary_path} recorded prediction MSE",
                )
                values.append(criterion_value)
            else:
                if criterion is None:
                    if record_criterion is not None:
                        raise TransportAggregationError(
                            f"invalid tuning criterion mismatch: {summary_path}"
                        )
                else:
                    criterion_value = _finite_number(
                        criterion, name=f"{summary_path} diagnostic prediction MSE"
                    )
                    _close(
                        record_criterion,
                        criterion_value,
                        name=f"{summary_path} diagnostic recorded prediction MSE",
                    )
                rejection_reasons.append(
                    f"seed={seed},T={horizon},D={target_d}: {reasons}"
                )
        eligible = not rejection_reasons and len(values) == len(expected_runs)
        mean_value = float(sum(values) / len(values)) if eligible else None
        if record.get("eligible") is not eligible:
            raise TransportAggregationError(f"{candidate_id} eligibility mismatch")
        if canonical_json(record.get("rejection_reasons", ())) != canonical_json(
            rejection_reasons
        ):
            raise TransportAggregationError(f"{candidate_id} rejection summary mismatch")
        if mean_value is None:
            if record.get("aggregate_mean_all_action_prediction_mse") is not None:
                raise TransportAggregationError(f"{candidate_id} has an invalid mean criterion")
        else:
            _close(
                record.get("aggregate_mean_all_action_prediction_mse"),
                mean_value,
                name=f"{candidate_id} aggregate prediction MSE",
            )
        computed.append(
            {
                "candidate_id": candidate_id,
                "learning_rate": rate,
                "steps_per_round": step_count,
                "eligible": eligible,
                "mean": mean_value,
            }
        )
    eligible_records = [record for record in computed if record["eligible"]]
    if not eligible_records:
        raise TransportAggregationError("selection has no eligible optimizer candidate")
    winner = min(
        eligible_records,
        key=lambda record: (
            float(record["mean"]),
            int(record["steps_per_round"]),
            float(record["learning_rate"]),
            str(record["candidate_id"]),
        ),
    )
    selected = selection.get("selected")
    if not isinstance(selected, Mapping):
        raise TransportAggregationError("selection has no winner")
    if (
        selected.get("candidate_id") != winner["candidate_id"]
        or selected.get("steps_per_round") != winner["steps_per_round"]
    ):
        raise TransportAggregationError("selection winner or tie-break is inconsistent")
    _close(
        selected.get("learning_rate"),
        float(winner["learning_rate"]),
        name="selected learning rate",
    )
    _close(
        selected.get("aggregate_mean_all_action_prediction_mse"),
        float(winner["mean"]),
        name="selected aggregate prediction MSE",
    )
    if selected.get("tie_break") != ["fewer_steps_per_round", "smaller_learning_rate"]:
        raise TransportAggregationError("selection tie-break is inconsistent")


def _load_selection(
    selection_path: Path,
    config: Mapping[str, Any],
    *,
    profile: str,
) -> tuple[dict[str, Any], str]:
    try:
        validate_aggregate_provenance_sidecar(selection_path)
    except (OSError, ValueError) as error:
        raise TransportAggregationError(f"invalid selection provenance: {error}") from error
    selection = _load_object(selection_path)
    tuning_seeds = get_seed_set(config, "tuning")
    evaluation_seeds = get_seed_set(config, "evaluation")
    expected = {
        "schema_version": 1,
        "event": SELECTION_EVENT,
        "profile": profile,
        "config_digest": config_digest(config),
        "tuning_seeds": list(tuning_seeds),
        "evaluation_seeds": list(evaluation_seeds),
        "seed_sets_disjoint": True,
    }
    for key, value in expected.items():
        if selection.get(key) != value:
            raise TransportAggregationError(f"selection mismatch for {key}")
    if set(tuning_seeds) & set(evaluation_seeds):
        raise TransportAggregationError("tuning and evaluation seeds overlap")
    if selection.get("selection_metric") != "mean_all_action_prediction_mse_after_burn_in":
        raise TransportAggregationError("selection metric is not the preregistered MSE")
    candidates = selection.get("candidates")
    selected = selection.get("selected")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise TransportAggregationError("selection candidates must be a list")
    if not isinstance(selected, Mapping):
        raise TransportAggregationError("selection has no selected optimizer")
    for name in ("candidate_id", "learning_rate", "steps_per_round"):
        if name not in selected:
            raise TransportAggregationError(f"selected optimizer is missing {name}")
    _finite_number(selected["learning_rate"], name="selected learning_rate")
    _integer(selected["steps_per_round"], name="selected steps_per_round", minimum=1)
    if not any(
        isinstance(candidate, Mapping)
        and candidate.get("candidate_id") == selected.get("candidate_id")
        for candidate in candidates
    ):
        raise TransportAggregationError("selected optimizer is absent from candidates")
    if selection.get("complete_tuning_input_inventory") is not True:
        raise TransportAggregationError("selection does not certify a complete tuning inventory")
    inputs = selection.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise TransportAggregationError("selection has no complete tuning input inventory")
    evaluation_seed_tokens = {f"seed-{seed}" for seed in evaluation_seeds}
    for item in inputs:
        if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
            raise TransportAggregationError("selection input inventory is malformed")
        path_text = str(item["path"])
        parts = set(Path(path_text).parts)
        if "evaluation" in parts or parts & evaluation_seed_tokens:
            raise TransportAggregationError(
                f"evaluation data appears in tuning selection inputs: {path_text}"
            )
    revision = selection.get("git_revision")
    if not isinstance(revision, str) or not revision:
        raise TransportAggregationError("selection is missing its Git revision")
    tuning_seed_set = set(tuning_seeds)
    for item in inputs:
        input_path = Path(str(item["path"]))
        if input_path.name != "manifest.jsonl":
            continue
        manifest = _load_jsonl(input_path, exactly_one=True)[0]
        if manifest.get("phase") != "tuning" or manifest.get("profile") != profile:
            raise TransportAggregationError(
                f"selection manifest is not a full tuning run: {input_path}"
            )
        if manifest.get("git_revision") != revision:
            raise TransportAggregationError(
                f"mixed Git revisions in selection inputs: {input_path}"
            )
        if manifest.get("config_digest") != config_digest(config):
            raise TransportAggregationError(
                f"mixed config digests in selection inputs: {input_path}"
            )
        if manifest.get("seed") not in tuning_seed_set:
            raise TransportAggregationError(
                f"non-tuning seed in selection input: {input_path}"
            )
    _validate_selection_candidates(selection, config)
    return selection, sha256_file(selection_path)


def _load_run(
    directory: Path,
    *,
    config: Mapping[str, Any],
    profile: str,
    method: str,
    seed: int,
    horizon: int,
    target_d: float,
    selection_sha256: str,
    selection_revision: str,
    selected_optimizer: Mapping[str, Any],
) -> TransportRun:
    missing = [name for name in REQUIRED_RUN_FILES if not (directory / name).is_file()]
    if missing:
        raise TransportAggregationError(
            f"incomplete run directory {directory}: missing {', '.join(missing)}"
        )
    try:
        validate_sha256_sidecar(directory / "summary.json")
    except (OSError, ValueError) as error:
        raise TransportAggregationError(f"invalid summary hash in {directory}: {error}") from error

    manifest = _load_jsonl(directory / "manifest.jsonl", exactly_one=True)[0]
    raw = tuple(_load_jsonl(directory / "raw.jsonl", exactly_one=False))
    summary = _load_object(directory / "summary.json")
    _validate_finite_tree(manifest, name=f"{directory}.manifest")
    _validate_finite_tree(raw, name=f"{directory}.raw")
    _validate_finite_tree(summary, name=f"{directory}.summary")

    digest = config_digest(config)
    if manifest.get("schema_version") != 1:
        raise TransportAggregationError(f"unsupported manifest schema in {directory}")
    if manifest.get("config_digest") != digest or summary.get("config_digest") != digest:
        raise TransportAggregationError(f"config digest mismatch in {directory}")
    manifest_config = manifest.get("config")
    if not isinstance(manifest_config, Mapping) or canonical_json(manifest_config) != canonical_json(config):
        raise TransportAggregationError(f"resolved config mismatch in {directory}")
    expected_manifest = {
        "phase": "evaluation",
        "profile": profile,
        "method": method,
        "seed": seed,
        "horizon": horizon,
        "selection_sha256": selection_sha256,
    }
    for key, value in expected_manifest.items():
        if manifest.get(key) != value:
            raise TransportAggregationError(f"manifest {key} mismatch in {directory}")
    _close(manifest.get("target_D"), target_d, name=f"{directory} target_D")
    expected_w = _expected_width(config, horizon, target_d)
    _close(manifest.get("W"), expected_w, name=f"{directory} W", tolerance=5e-11)
    if manifest.get("git_revision") != selection_revision:
        raise TransportAggregationError(f"Git revision mismatch in {directory}")
    child_seeds = manifest.get("child_seeds")
    required_child_seeds = {
        "context_stream",
        "potential_noise_table",
        "teacher_construction",
        "behavior_policy_tuning_stream",
        "bootstrap_aggregation",
    }
    if not isinstance(child_seeds, Mapping) or not required_child_seeds <= set(child_seeds):
        raise TransportAggregationError(f"child-seed provenance is incomplete in {directory}")
    expected_run_child_seeds = {
        "context_stream": derive_child_seed(
            seed, "transport_instantiation/context/v1"
        ),
        "potential_noise_table": derive_child_seed(
            seed, "transport_instantiation/potential_noise/v1"
        ),
        "behavior_policy_tuning_stream": derive_child_seed(
            seed, "transport_instantiation/behavior_policy/v1"
        ),
        "teacher_construction": int(_lookup(config, "teacher.seed")),
    }
    for name, expected_seed in expected_run_child_seeds.items():
        if child_seeds.get(name) != expected_seed:
            raise TransportAggregationError(
                f"{name} child seed mismatch in {directory}"
            )
    expected_bootstrap_seed = derive_seed(
        int(digest[:16], 16),
        "transport_instantiation",
        "bootstrap",
        horizon,
        target_d,
    )
    if child_seeds.get("bootstrap_aggregation") != expected_bootstrap_seed:
        raise TransportAggregationError(
            f"bootstrap child seed mismatch in {directory}"
        )

    expected_summary = {
        "schema_version": 1,
        "event": SUMMARY_EVENT,
        "phase": "evaluation",
        "profile": profile,
        "method": method,
        "seed": seed,
        "horizon": horizon,
        "selection_sha256": selection_sha256,
        "rounds": horizon,
    }
    for key, value in expected_summary.items():
        if summary.get(key) != value:
            raise TransportAggregationError(f"summary {key} mismatch in {directory}")
    _close(summary.get("target_D"), target_d, name=f"{directory} summary target_D")
    _close(summary.get("W"), expected_w, name=f"{directory} summary W", tolerance=5e-11)
    optimizer = summary.get("optimizer")
    if not isinstance(optimizer, Mapping):
        raise TransportAggregationError(f"summary optimizer is missing in {directory}")
    _close(
        optimizer.get("learning_rate"),
        _finite_number(
            selected_optimizer.get("learning_rate"),
            name="selected optimizer learning rate",
        ),
        name=f"{directory} optimizer learning rate",
    )
    if optimizer.get("steps_per_round") != selected_optimizer.get("steps_per_round"):
        raise TransportAggregationError(f"optimizer step count mismatch in {directory}")
    failure_count = _integer(
        summary.get("deterministic_audit_failure_count"),
        name=f"{directory} deterministic failures",
    )
    deterministic_pass = summary.get(
        "deterministic_audit_pass", summary.get("deterministic_audit_passed")
    )
    if failure_count != 0 or deterministic_pass is not True:
        raise TransportAggregationError(f"deterministic audit failed in {directory}")
    _boolean(
        summary.get("simultaneous_reference_confidence"),
        name=f"{directory} simultaneous reference confidence",
    )
    _boolean(
        summary.get("simultaneous_transport_optimism"),
        name=f"{directory} simultaneous transport optimism",
    )
    _boolean(
        summary.get("simultaneous_method_optimism"),
        name=f"{directory} simultaneous method optimism",
    )

    rounds = [record.get("round") for record in raw]
    if rounds != list(range(horizon)):
        raise TransportAggregationError(f"raw rounds are incomplete or noncontiguous in {directory}")
    for round_index, record in enumerate(raw):
        metrics = _metrics(record, path=directory / "raw.jsonl", round_index=round_index)
        raw_failures = _integer(
            _lookup(metrics, "deterministic_audit_failure_count"),
            name=f"{directory} round {round_index} deterministic failures",
        )
        if raw_failures != 0:
            raise TransportAggregationError(
                f"deterministic audit failed at round {round_index} in {directory}"
            )
        for field in (
            "cumulative_pseudo_regret",
            "D_Q",
            "d_Th",
            "sharp_theorem_rhs",
            "simple_theorem_rhs",
            "beta_t_corr",
            "historical_radius_contribution",
            "current_bias",
        ):
            _finite_number(_lookup(metrics, field), name=f"{directory} round {round_index} {field}")
        path_value = _lookup(metrics, "D_path_quad", required=False)
        if path_value is not None:
            _finite_number(path_value, name=f"{directory} round {round_index} D_path_quad")
        _boolean(
            _lookup(metrics, "reference_confidence_all_actions"),
            name=f"{directory} round {round_index} reference confidence",
        )
        _boolean(
            _lookup(metrics, "transport_optimism_all_actions"),
            name=f"{directory} round {round_index} transport optimism",
        )

    final_metrics = _metrics(raw[-1], path=directory / "raw.jsonl", round_index=horizon - 1)
    prefix_flag_pairs = (
        (
            "simultaneous_reference_confidence",
            "prefix_simultaneous_reference_confidence",
        ),
        (
            "simultaneous_transport_optimism",
            "prefix_simultaneous_transport_optimism",
        ),
        ("simultaneous_method_optimism", "prefix_simultaneous_method_optimism"),
    )
    for summary_name, raw_name in prefix_flag_pairs:
        raw_flag = _boolean(
            _lookup(final_metrics, raw_name),
            name=f"{directory} final {raw_name}",
        )
        if summary.get(summary_name) is not raw_flag:
            raise TransportAggregationError(
                f"summary {summary_name} disagrees with final raw round in {directory}"
            )
    aliases = {
        "cumulative_pseudo_regret": ("cumulative_pseudo_regret",),
        "sharp_theorem_rhs": ("sharp_theorem_rhs",),
        "simple_theorem_rhs": ("simple_theorem_rhs",),
        "width_sum": ("width_sum", "frozen_width_sum"),
        "potential_upper": ("potential_upper", "frozen_potential_upper"),
    }
    for summary_name, raw_names in aliases.items():
        summary_value = _finite_number(summary.get(summary_name), name=f"summary {summary_name}")
        raw_value = _finite_number(
            _lookup(final_metrics, *raw_names), name=f"final raw {summary_name}"
        )
        if not math.isclose(summary_value, raw_value, rel_tol=2e-10, abs_tol=2e-10):
            raise TransportAggregationError(
                f"summary {summary_name} disagrees with final raw round in {directory}"
            )
    regret = _finite_number(summary["cumulative_pseudo_regret"], name="regret")
    if summary.get("zero_regret") is not (regret == 0.0):
        raise TransportAggregationError(f"zero-regret classification mismatch in {directory}")
    if _finite_number(summary["width_sum"], name="width sum") > _finite_number(
        summary["potential_upper"], name="potential upper"
    ) + 2e-9:
        raise TransportAggregationError(f"frozen potential closure failed in {directory}")
    return TransportRun(
        directory=directory,
        manifest=manifest,
        raw=raw,
        summary=summary,
        method=method,
        seed=seed,
        horizon=horizon,
        target_d=target_d,
        width_scale=expected_w,
    )


def _clopper_pearson(successes: int, total: int, level: float) -> dict[str, Any]:
    if total <= 0 or not 0 <= successes <= total or not 0.0 < level < 1.0:
        raise TransportAggregationError("invalid Clopper-Pearson inputs")
    alpha = 1.0 - level
    low = 0.0 if successes == 0 else float(
        beta_distribution.ppf(alpha / 2.0, successes, total - successes + 1)
    )
    high = 1.0 if successes == total else float(
        beta_distribution.ppf(1.0 - alpha / 2.0, successes + 1, total - successes)
    )
    return {
        "successes": successes,
        "n": total,
        "estimate": successes / total,
        "level": level,
        "method": "exact_clopper_pearson",
        "ci_low": low,
        "ci_high": high,
        "ci": [low, high],
    }


def _describe(values: Iterable[float]) -> dict[str, Any]:
    array = np.asarray(tuple(float(value) for value in values), dtype=np.float64)
    if array.size == 0 or not np.all(np.isfinite(array)):
        raise TransportAggregationError("descriptive input must be nonempty and finite")
    standard_deviation = float(np.std(array, ddof=1)) if array.size > 1 else 0.0
    return {
        "n": int(array.size),
        "mean": float(np.mean(array)),
        "standard_deviation": standard_deviation,
        "standard_error": standard_deviation / math.sqrt(array.size),
        "median": float(np.median(array)),
        "q10": float(np.quantile(array, 0.10)),
        "q25": float(np.quantile(array, 0.25)),
        "q75": float(np.quantile(array, 0.75)),
        "q90": float(np.quantile(array, 0.90)),
        "iqr": float(np.quantile(array, 0.75) - np.quantile(array, 0.25)),
        "minimum": float(np.min(array)),
        "maximum": float(np.max(array)),
    }


def _bootstrap_counts(seed: int, count: int, resamples: int) -> np.ndarray:
    if count <= 0 or resamples <= 0:
        raise TransportAggregationError("bootstrap dimensions must be positive")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, count, size=(resamples, count), dtype=np.int64)
    counts = np.zeros((resamples, count), dtype=np.float64)
    rows = np.repeat(np.arange(resamples, dtype=np.int64), count)
    np.add.at(counts, (rows, indices.reshape(-1)), 1.0)
    return counts


def _bootstrap_interval(
    values: Sequence[float], counts: np.ndarray, level: float
) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.float64)
    if array.shape != (counts.shape[1],) or not np.all(np.isfinite(array)):
        raise TransportAggregationError("bootstrap values do not match resample counts")
    means = counts @ array / array.size
    alpha = 1.0 - level
    low, high = np.quantile(means, (alpha / 2.0, 1.0 - alpha / 2.0))
    return {
        "resamples": int(counts.shape[0]),
        "level": level,
        "method": "deterministic_seed_paired_bootstrap",
        "mean": float(np.mean(array)),
        "ci_low": float(low),
        "ci_high": float(high),
        "ci": [float(low), float(high)],
    }


def _curve_interval(matrix: np.ndarray, counts: np.ndarray, level: float) -> tuple[np.ndarray, ...]:
    if matrix.ndim != 2 or matrix.shape[0] != counts.shape[1]:
        raise TransportAggregationError("curve matrix does not match bootstrap counts")
    draws = counts @ matrix / matrix.shape[0]
    alpha = 1.0 - level
    low, high = np.quantile(draws, (alpha / 2.0, 1.0 - alpha / 2.0), axis=0)
    return np.mean(matrix, axis=0), low, high


def _raw_series(run: TransportRun, name: str, *aliases: str) -> np.ndarray:
    values = [
        _finite_number(
            _lookup(_metrics(record, path=run.directory / "raw.jsonl", round_index=index), name, *aliases),
            name=f"{run.directory} {name} round {index}",
        )
        for index, record in enumerate(run.raw)
    ]
    return np.asarray(values, dtype=np.float64)


def _directory_inputs(directories: Iterable[Path]) -> list[dict[str, str]]:
    return [
        {"path": str(directory / filename), "sha256": sha256_file(directory / filename)}
        for directory in sorted(directories, key=str)
        for filename in REQUIRED_RUN_FILES
    ]


def aggregate_transport_instantiation(
    config: Mapping[str, Any],
    selection_path: str | Path,
    raw_root: str | Path,
    *,
    profile: str,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate and aggregate the complete locked evaluation grid."""

    if config.get("name") != "transport_instantiation" or config.get("profile") != profile:
        raise TransportAggregationError("config must be the resolved transport profile")
    if profile not in {"smoke", "full"}:
        raise TransportAggregationError("profile must be 'smoke' or 'full'")
    methods = tuple(str(value) for value in config.get("methods", ()))
    if methods != METHODS:
        raise TransportAggregationError(f"method order must be exactly {METHODS}")
    horizons = tuple(_integer(value, name="horizon", minimum=2) for value in config.get("horizons", ()))
    targets = tuple(_finite_number(value, name="target_D") for value in config.get("target_D", ()))
    if not horizons or not targets or len(set(horizons)) != len(horizons) or len(set(targets)) != len(targets):
        raise TransportAggregationError("horizons and target_D must be nonempty and unique")
    evaluation_seeds = get_seed_set(config, "evaluation")
    if profile == "full" and len(evaluation_seeds) != 50:
        raise TransportAggregationError("full publication aggregate requires 50 evaluation seeds")
    selection_file = Path(selection_path)
    selection, selection_sha256 = _load_selection(selection_file, config, profile=profile)
    selection_revision = str(selection["git_revision"])

    evaluation_root = Path(raw_root) / "evaluation"
    expected_directories = {
        condition_directory(evaluation_root, horizon, target_d) / method / f"seed-{seed}"
        for horizon in horizons
        for target_d in targets
        for method in methods
        for seed in evaluation_seeds
    }
    discovered_directories = {
        path.parent for path in evaluation_root.rglob("manifest.jsonl")
    }
    if discovered_directories != expected_directories:
        missing = sorted(str(path) for path in expected_directories - discovered_directories)
        extra = sorted(str(path) for path in discovered_directories - expected_directories)
        raise TransportAggregationError(
            f"evaluation Cartesian product mismatch; missing={missing[:5]} "
            f"({len(missing)} total), extra={extra[:5]} ({len(extra)} total)"
        )

    def load_group(horizon: int, target_d: float, method: str) -> list[TransportRun]:
        cell_root = condition_directory(evaluation_root, horizon, target_d)
        members = [
            _load_run(
                cell_root / method / f"seed-{seed}",
                config=config,
                profile=profile,
                method=method,
                seed=seed,
                horizon=horizon,
                target_d=target_d,
                selection_sha256=selection_sha256,
                selection_revision=selection_revision,
                selected_optimizer=selection["selected"],
            )
            for seed in evaluation_seeds
        ]
        if [run.seed for run in members] != list(evaluation_seeds):
            raise TransportAggregationError("evaluation seed ordering mismatch")
        return members

    validated_run_count = 0
    for horizon in horizons:
        for target_d in targets:
            for method in methods:
                members = load_group(horizon, target_d, method)
                validated_run_count += len(members)
                del members

    statistics_config = config.get("statistics")
    if not isinstance(statistics_config, Mapping):
        raise TransportAggregationError("statistics config is missing")
    coverage_level = _finite_number(
        statistics_config.get("coverage_level"), name="coverage level"
    )
    bootstrap_level = _finite_number(
        statistics_config.get("paired_bootstrap_level"), name="bootstrap level"
    )
    bootstrap_resamples = _integer(
        statistics_config.get("paired_bootstrap_resamples"),
        name="bootstrap resamples",
        minimum=1,
    )
    digest = config_digest(config)
    bootstrap_master = int(digest[:16], 16)
    ratio_tolerance = _finite_number(
        _lookup(config, "numerics.ratio_denominator_tolerance"),
        name="ratio denominator tolerance",
    )

    validity: list[dict[str, Any]] = []
    tightness: list[dict[str, Any]] = []
    bound_nonvacuity: list[dict[str, Any]] = []
    path_points: list[dict[str, Any]] = []
    for horizon in horizons:
        for target_d in targets:
            members = load_group(horizon, target_d, PRIMARY_METHOD)
            confidence_successes = sum(
                bool(run.summary["simultaneous_reference_confidence"]) for run in members
            )
            optimism_successes = sum(
                bool(run.summary["simultaneous_transport_optimism"])
                for run in members
            )
            bound_violations = sum(
                bool(run.summary["simultaneous_reference_confidence"])
                and _finite_number(run.summary["sharp_theorem_rhs"], name="sharp RHS")
                + 2e-9
                < _finite_number(run.summary["cumulative_pseudo_regret"], name="regret")
                for run in members
            )
            max_d_q = [float(np.max(_raw_series(run, "D_Q"))) for run in members]
            max_d_th = [float(np.max(_raw_series(run, "d_Th"))) for run in members]
            sharp_values = [float(run.summary["sharp_theorem_rhs"]) for run in members]
            regrets = [float(run.summary["cumulative_pseudo_regret"]) for run in members]
            validity.append(
                {
                    "horizon": horizon,
                    "target_D": target_d,
                    "run_count": len(members),
                    "reference_confidence_coverage": _clopper_pearson(
                        confidence_successes, len(members), coverage_level
                    ),
                    "transport_optimism_coverage": _clopper_pearson(
                        optimism_successes, len(members), coverage_level
                    ),
                    "deterministic_audit_failures": 0,
                    "bound_violations_on_joint_event": bound_violations,
                    "max_realized_D_Q": _describe(max_d_q),
                    "max_endpoint_Thompson_distance": _describe(max_d_th),
                    "sharp_theorem_rhs": _describe(sharp_values),
                    "cumulative_pseudo_regret": _describe(regrets),
                }
            )

            d_q_over_d_th: list[float] = []
            d_q_over_path: list[float] = []
            path_over_d_th: list[float] = []
            d_th_zero_count = 0
            path_zero_count = 0
            d_q_when_d_th_small: list[float] = []
            d_q_when_path_small: list[float] = []
            path_when_d_th_small: list[float] = []
            exp_half: list[float] = []
            historical: list[float] = []
            current_bias: list[float] = []
            for run in members:
                for round_index, record in enumerate(run.raw, start=1):
                    metrics = _metrics(
                        record, path=run.directory / "raw.jsonl", round_index=round_index - 1
                    )
                    d_q = _finite_number(_lookup(metrics, "D_Q"), name="D_Q")
                    d_th = _finite_number(_lookup(metrics, "d_Th"), name="d_Th")
                    path_value = _lookup(metrics, "D_path_quad", required=False)
                    d_path = None if path_value is None else _finite_number(path_value, name="D_path")
                    if d_th > ratio_tolerance:
                        d_q_over_d_th.append(d_q / d_th)
                    else:
                        d_th_zero_count += 1
                        d_q_when_d_th_small.append(d_q)
                    if d_path is not None and d_path > ratio_tolerance:
                        d_q_over_path.append(d_q / d_path)
                    elif d_path is not None:
                        path_zero_count += 1
                        d_q_when_path_small.append(d_q)
                    if d_path is not None and d_th > ratio_tolerance:
                        path_over_d_th.append(d_path / d_th)
                    elif d_path is not None:
                        path_when_d_th_small.append(d_path)
                    exp_half.append(math.exp(d_q / 2.0))
                    path_points.append(
                        {
                            "horizon": horizon,
                            "target_D": target_d,
                            "seed": run.seed,
                            "round": round_index,
                            "D_Q": d_q,
                            "d_Th": d_th,
                            "D_path_quad": d_path,
                        }
                    )
                final_metrics = _metrics(
                    run.raw[-1], path=run.directory / "raw.jsonl", round_index=horizon - 1
                )
                historical.append(
                    _finite_number(
                        _lookup(final_metrics, "historical_radius_contribution"),
                        name="terminal historical radius",
                    )
                )
                current_bias.append(
                    _finite_number(
                        _lookup(final_metrics, "current_bias_cumulative"),
                        name="cumulative current bias",
                    )
                )
            width_ratios = [
                float(run.summary["width_sum"]) / float(run.summary["potential_upper"])
                if float(run.summary["potential_upper"]) > ratio_tolerance
                else 0.0
                for run in members
            ]
            sharp_simple = [
                float(run.summary["sharp_theorem_rhs"])
                / float(run.summary["simple_theorem_rhs"])
                for run in members
                if float(run.summary["simple_theorem_rhs"]) > ratio_tolerance
            ]
            tightness.append(
                {
                    "horizon": horizon,
                    "target_D": target_d,
                    "D_Q_over_d_Th": None if not d_q_over_d_th else _describe(d_q_over_d_th),
                    "d_Th_at_or_below_ratio_tolerance_count": d_th_zero_count,
                    "D_Q_when_d_Th_at_or_below_tolerance": (
                        None if not d_q_when_d_th_small else _describe(d_q_when_d_th_small)
                    ),
                    "D_Q_over_D_path_quad": None if not d_q_over_path else _describe(d_q_over_path),
                    "D_path_quad_at_or_below_ratio_tolerance_count": path_zero_count,
                    "D_Q_when_D_path_quad_at_or_below_tolerance": (
                        None if not d_q_when_path_small else _describe(d_q_when_path_small)
                    ),
                    "D_path_quad_over_d_Th": None if not path_over_d_th else _describe(path_over_d_th),
                    "d_Th_at_or_below_tolerance_with_path_count": len(
                        path_when_d_th_small
                    ),
                    "D_path_quad_when_d_Th_at_or_below_tolerance": (
                        None if not path_when_d_th_small else _describe(path_when_d_th_small)
                    ),
                    "exp_D_Q_over_2": _describe(exp_half),
                    "historical_confidence_radius_contribution": _describe(historical),
                    "current_additive_bias": _describe(current_bias),
                    "frozen_width_sum_over_potential_upper": _describe(width_ratios),
                    "sharp_rhs_over_simple_rhs": _describe(sharp_simple),
                }
            )

            positive = [
                (float(run.summary["sharp_theorem_rhs"]), float(run.summary["cumulative_pseudo_regret"]))
                for run in members
                if float(run.summary["cumulative_pseudo_regret"]) > 0.0
            ]
            zero_count = len(members) - len(positive)
            on_event_members = [
                run for run in members if bool(run.summary["simultaneous_reference_confidence"])
            ]
            positive_on_event = [
                (
                    float(run.summary["sharp_theorem_rhs"]),
                    float(run.summary["cumulative_pseudo_regret"]),
                )
                for run in on_event_members
                if float(run.summary["cumulative_pseudo_regret"]) > 0.0
            ]
            bound_nonvacuity.append(
                {
                    "horizon": horizon,
                    "target_D": target_d,
                    "run_count": len(members),
                    "zero_regret_run_count": zero_count,
                    "positive_regret_run_count": len(positive),
                    "joint_confidence_event_run_count": len(on_event_members),
                    "premise_false_run_count": len(members) - len(on_event_members),
                    "sharp_theorem_rhs": _describe(sharp_values),
                    "cumulative_pseudo_regret": _describe(regrets),
                    "sharp_rhs_over_positive_regret": (
                        None
                        if not positive
                        else _describe(rhs / regret for rhs, regret in positive)
                    ),
                    "sharp_rhs_over_positive_regret_on_joint_event": (
                        None
                        if not positive_on_event
                        else _describe(
                            rhs / regret for rhs, regret in positive_on_event
                        )
                    ),
                }
            )

    reporting = config.get("reporting")
    if not isinstance(reporting, Mapping):
        raise TransportAggregationError("reporting config is missing")
    primary_horizon = _integer(
        reporting.get("primary_horizon"), name="primary horizon", minimum=2
    )
    if primary_horizon not in horizons:
        raise TransportAggregationError("primary horizon is absent from the evaluation grid")

    policy_outcomes: list[dict[str, Any]] = []
    regret_curves: list[dict[str, Any]] = []
    bound_decomposition: list[dict[str, Any]] = []
    environment_diagnostics: list[dict[str, Any]] = []
    bootstrap_child_seeds: list[dict[str, Any]] = []
    for horizon in horizons:
        for target_d in targets:
            members = load_group(horizon, target_d, PRIMARY_METHOD)
            environment_diagnostics.append(
                {
                    "horizon": horizon,
                    "target_D": target_d,
                    "optimal_action_entropy": _describe(
                        float(run.summary["optimal_action_entropy"]) for run in members
                    ),
                    "distinct_optimal_actions": _describe(
                        float(run.summary["distinct_optimal_actions"]) for run in members
                    ),
                    "average_optimality_gap": _describe(
                        float(run.summary["average_optimality_gap"]) for run in members
                    ),
                    "best_fixed_action_regret": _describe(
                        float(run.summary["best_fixed_action_regret"]) for run in members
                    ),
                    "context_free_mean_only_regret": _describe(
                        float(run.summary["context_free_mean_only_regret"])
                        for run in members
                    ),
                }
            )
            del members
    for target_d in targets:
        reference_members = load_group(primary_horizon, target_d, PRIMARY_METHOD)
        bootstrap_seed = derive_seed(
            bootstrap_master,
            "transport_instantiation",
            "bootstrap",
            primary_horizon,
            target_d,
        )
        bootstrap_child_seeds.append(
            {
                "horizon": primary_horizon,
                "target_D": target_d,
                "seed": bootstrap_seed,
            }
        )
        counts = _bootstrap_counts(
            bootstrap_seed,
            len(evaluation_seeds),
            bootstrap_resamples,
        )
        reference_by_seed = {run.seed: run for run in reference_members}
        for method in methods:
            members = (
                reference_members
                if method == PRIMARY_METHOD
                else load_group(primary_horizon, target_d, method)
            )
            regrets = [float(run.summary["cumulative_pseudo_regret"]) for run in members]
            differences = [
                float(run.summary["cumulative_pseudo_regret"])
                - float(reference_by_seed[run.seed].summary["cumulative_pseudo_regret"])
                for run in members
            ]
            optimism_successes = sum(
                bool(run.summary["simultaneous_method_optimism"])
                for run in members
            )
            policy_outcomes.append(
                {
                    "horizon": primary_horizon,
                    "target_D": target_d,
                    "method": method,
                    "method_role": str(_lookup(config, f"method_roles.{method}")),
                    "run_count": len(members),
                    "cumulative_pseudo_regret": {
                        **_describe(regrets),
                        "bootstrap_mean_interval": _bootstrap_interval(
                            regrets, counts, bootstrap_level
                        ),
                    },
                    "paired_difference_from_transport_hessian": {
                        **_describe(differences),
                        "bootstrap_mean_interval": _bootstrap_interval(
                            differences, counts, bootstrap_level
                        ),
                    },
                    "simultaneous_optimism_coverage": _clopper_pearson(
                        optimism_successes, len(members), coverage_level
                    ),
                }
            )

            matrix = np.stack(
                [_raw_series(run, "cumulative_pseudo_regret") for run in members], axis=0
            )
            mean_curve, low_curve, high_curve = _curve_interval(
                matrix, counts, bootstrap_level
            )
            regret_curves.extend(
                {
                    "horizon": primary_horizon,
                    "target_D": target_d,
                    "method": method,
                    "round": round_index + 1,
                    "mean": float(mean_curve[round_index]),
                    "ci_low": float(low_curve[round_index]),
                    "ci_high": float(high_curve[round_index]),
                }
                for round_index in range(primary_horizon)
            )
            if method != PRIMARY_METHOD:
                del members

        decomposition_names = (
            "statistical_bound_component",
            "historical_bound_component",
            "path_inflation_component",
            "current_bias_cumulative",
            "cumulative_pseudo_regret",
            "sharp_theorem_rhs",
        )
        decomposition_matrices = {
            name: np.stack([_raw_series(run, name) for run in reference_members], axis=0)
            for name in decomposition_names
        }
        decomposition_means = {
            name: np.mean(matrix, axis=0) for name, matrix in decomposition_matrices.items()
        }
        for round_index in range(primary_horizon):
            record: dict[str, Any] = {
                "horizon": primary_horizon,
                "target_D": target_d,
                "round": round_index + 1,
            }
            record.update(
                {
                    name: float(values[round_index])
                    for name, values in decomposition_means.items()
                }
            )
            bound_decomposition.append(record)
        del reference_members

    inputs = _directory_inputs(expected_directories)
    inputs.extend(
        {
            "path": str(item["path"]),
            "sha256": str(item["sha256"]),
        }
        for item in selection["inputs"]
    )
    selection_sidecar = selection_file.with_suffix(selection_file.suffix + ".provenance.json")
    inputs.extend(
        [
            {"path": str(selection_file), "sha256": selection_sha256},
            {"path": str(selection_sidecar), "sha256": sha256_file(selection_sidecar)},
        ]
    )
    if config_path is not None:
        source = Path(config_path)
        inputs.append({"path": str(source), "sha256": sha256_file(source)})
    deduplicated: dict[str, str] = {}
    for item in inputs:
        previous = deduplicated.get(item["path"])
        if previous is not None and previous != item["sha256"]:
            raise TransportAggregationError(
                f"conflicting input hashes for {item['path']}"
            )
        deduplicated[item["path"]] = item["sha256"]
    inputs = [
        {"path": path, "sha256": digest_value}
        for path, digest_value in sorted(deduplicated.items())
    ]
    expected_run_count = len(horizons) * len(targets) * len(methods) * len(evaluation_seeds)
    aggregate = {
        "schema_version": 1,
        "event": AGGREGATE_EVENT,
        "experiment": "transport_instantiation",
        "profile": profile,
        "config_digest": digest,
        "git_revision": selection_revision,
        "selection_path": str(selection_file),
        "selection_sha256": selection_sha256,
        "selected_optimizer": dict(selection["selected"]),
        "methods": list(methods),
        "horizons": list(horizons),
        "target_D": list(targets),
        "evaluation_seeds": list(evaluation_seeds),
        "expected_run_count": expected_run_count,
        "completed_run_count": validated_run_count,
        "full_grid_complete": validated_run_count == expected_run_count,
        "publication_ready": profile == "full" and len(evaluation_seeds) == 50,
        "all_deterministic_audits_pass": True,
        "stochastic_confidence_failures_retained": True,
        "coverage_interval": "exact Clopper-Pearson",
        "paired_bootstrap": {
            "resamples": bootstrap_resamples,
            "level": bootstrap_level,
            "seed_source": "resolved config digest and fixed namespace",
            "paired_by": ["evaluation seed", "horizon", "target_D"],
            "child_seeds": bootstrap_child_seeds,
        },
        "validity": validity,
        "policy_outcomes": policy_outcomes,
        "certificate_tightness": tightness,
        "bound_nonvacuity": bound_nonvacuity,
        "environment_diagnostics": environment_diagnostics,
        "regret_curves": regret_curves,
        "path_points": path_points,
        "bound_decomposition": bound_decomposition,
        "inputs": inputs,
        "input_set_sha256": input_set_sha256(inputs),
    }
    _validate_finite_tree(aggregate, name="aggregate")
    return aggregate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("experiments/configs/transport_instantiation.yaml"),
    )
    parser.add_argument("--profile", choices=("smoke", "full"), default="full")
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    config = load_config(args.config, profile=args.profile)
    aggregate = aggregate_transport_instantiation(
        config,
        args.selection,
        args.raw_root,
        profile=args.profile,
        config_path=args.config,
    )
    output, provenance = write_aggregate_with_provenance(aggregate, args.output)
    print(
        canonical_json(
            {
                "output": str(output),
                "provenance": str(provenance),
                "expected_run_count": aggregate["expected_run_count"],
                "completed_run_count": aggregate["completed_run_count"],
                "selection_sha256": aggregate["selection_sha256"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AGGREGATE_EVENT",
    "METHODS",
    "PRIMARY_METHOD",
    "TransportAggregationError",
    "TransportRun",
    "aggregate_transport_instantiation",
    "condition_directory",
    "main",
]
