"""Strict seed-level aggregation for realistic transport runs."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .benchmark import (
    derive_float64_diagnostic_status,
    derive_theorem_bound_status,
    THEOREM_BOUND_COMPARISON_RULE,
    THEOREM_METHODS,
)
from .configuration import (
    APPROXIMATE_METHODS,
    config_digest,
    EXPECTED_METHODS,
    EXPECTED_TASKS,
    load_config,
    method_spec,
    profile_policy,
    scientific_config_digest,
)
from .environment import derive_seed, LABEL_TASK
from .integrity import (
    IntegrityError,
    source_inventory_at_revision,
    validate_selection_policy,
    verify_evaluation_lineage,
    verify_recorded_data_authorization,
    verify_selection_lock,
)
from .io import run_directory, validate_run_directory
from .operators import AuditTolerance
from .provenance import (
    atomic_write_text,
    input_set_sha256,
    REPOSITORY_ROOT,
    sha256_file,
    write_json,
)
from .statistics import (
    clopper_pearson_interval,
    clopper_pearson_upper_bound,
    controlled_task_average_bootstrap,
    describe,
    four_corner_rank_tolerance_contrasts,
    paired_seed_bootstrap,
)


class AggregateError(RuntimeError):
    """Raised when raw evidence is incomplete or internally inconsistent."""


_STREAM_IDENTITY_FIELDS = frozenset(
    {
        "context_order",
        "contexts",
        "labels",
        "potential_means",
        "noise",
        "potential_rewards",
        "prepared_data",
        "teacher",
        "misspecification",
        "preprocessing",
        "split",
        "stream",
    }
)
_FULL_SHA256 = re.compile(r"[0-9a-f]{64}")


def _require_sha256(value: Any, *, description: str) -> str:
    if not isinstance(value, str) or _FULL_SHA256.fullmatch(value) is None:
        raise AggregateError(f"{description} must be a lowercase SHA-256 digest")
    return value


def _sidecar(path: Path) -> Path:
    return path.with_name(path.name + ".sha256")


def _refuse_existing_outputs(*paths: str | Path) -> None:
    existing = sorted(
        str(candidate)
        for raw in paths
        for candidate in (Path(raw), _sidecar(Path(raw)))
        if candidate.exists() or candidate.is_symlink()
    )
    if existing:
        raise FileExistsError(f"refusing to overwrite evidence outputs: {existing}")


def _validate_paired_streams(
    manifests: Mapping[tuple[str, str, int], Mapping[str, Any]],
) -> None:
    by_task_seed: dict[tuple[str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for (task, _method, seed), manifest in manifests.items():
        identity = manifest.get("exogenous_stream_identity")
        if (
            not isinstance(identity, Mapping)
            or set(identity) != _STREAM_IDENTITY_FIELDS
        ):
            raise AggregateError(
                f"missing exogenous stream identities for {task}/seed-{seed}"
            )
        for field in _STREAM_IDENTITY_FIELDS - {"misspecification"}:
            _require_sha256(
                identity[field],
                description=f"exogenous {field} identity for {task}/seed-{seed}",
            )
        misspecification = identity["misspecification"]
        if task == EXPECTED_TASKS[2]:
            _require_sha256(
                misspecification,
                description=f"exogenous misspecification identity for {task}/seed-{seed}",
            )
        elif misspecification is not None:
            raise AggregateError(
                f"task {task}/seed-{seed} unexpectedly has a misspecification identity"
            )

        prepared = manifest.get("prepared_data")
        split = manifest.get("split")
        if not isinstance(prepared, Mapping) or not isinstance(split, Mapping):
            raise AggregateError(
                f"manifest identity bindings are incomplete for {task}/seed-{seed}"
            )
        bindings = {
            "prepared_data": prepared.get("semantic_digest"),
            "preprocessing": manifest.get("preprocessing_digest"),
            "split": split.get("digest"),
            "teacher": manifest.get("teacher_digest"),
            "misspecification": manifest.get("misspecification_function_digest"),
            "stream": manifest.get("stream_digest"),
        }
        for field, producer_value in bindings.items():
            if identity[field] != producer_value:
                raise AggregateError(
                    f"exogenous {field} identity does not match its manifest producer field "
                    f"for {task}/seed-{seed}"
                )
        by_task_seed[(task, seed)].append(identity)
    canonical_by_task_seed: dict[tuple[str, int], Mapping[str, Any]] = {}
    for key, identities in by_task_seed.items():
        first = identities[0]
        if any(identity != first for identity in identities[1:]):
            raise AggregateError(
                f"mixed exogenous streams before paired statistics for {key}"
            )
        canonical_by_task_seed[key] = first

    task_b, task_c = EXPECTED_TASKS[1:]
    common_seeds = sorted(
        {seed for task, seed in canonical_by_task_seed if task == task_b}
        & {seed for task, seed in canonical_by_task_seed if task == task_c}
    )
    for seed in common_seeds:
        left = canonical_by_task_seed[(task_b, seed)]
        right = canonical_by_task_seed[(task_c, seed)]
        for field in (
            "context_order",
            "contexts",
            "labels",
            "noise",
            "teacher",
            "prepared_data",
            "preprocessing",
            "split",
        ):
            if left[field] != right[field]:
                raise AggregateError(
                    f"controlled tasks do not share {field} for seed {seed}"
                )
        if left["misspecification"] is not None:
            raise AggregateError("realizable task unexpectedly has misspecification")
        if not isinstance(right["misspecification"], str):
            raise AggregateError("misspecified task lacks its fixed construction")
        if left["potential_means"] == right["potential_means"]:
            raise AggregateError(
                "controlled B/C potential means were not distinguished"
            )
        if left["potential_rewards"] == right["potential_rewards"]:
            raise AggregateError(
                "controlled B/C potential rewards were not distinguished"
            )


def publication_eligibility(
    *,
    profile: str,
    phase: str,
    evidence_role: str,
    prepared_data: Mapping[str, Any],
    data_authorized: bool,
    selection_authorized: bool,
    deterministic_failure_count: int,
) -> bool:
    """Derive eligibility from validated contents, never an asserted flag."""

    return bool(
        profile == "full"
        and phase == "evaluation"
        and evidence_role == "publication_candidate"
        and prepared_data.get("dataset_name") == "sklearn_covtype"
        and prepared_data.get("smoke_only") is False
        and prepared_data.get("fixture_only") is False
        and prepared_data.get("publication_evidence") is False
        and data_authorized
        and selection_authorized
        and deterministic_failure_count == 0
    )


def _validate_manifest_identity(
    manifest: Mapping[str, Any],
    summary: Mapping[str, Any],
    *,
    profile: str,
    phase: str,
    evidence_role: str,
    dataset_mode: str,
    seed_set_identity: str,
    task: str,
    method: str,
    seed: int,
    rounds: int,
    expected_config_digest: str,
    expected_resolved_config: Mapping[str, Any],
) -> None:
    expected_identity = {
        "profile": profile,
        "phase": phase,
        "evidence_role": evidence_role,
        "dataset_mode": dataset_mode,
        "seed_set_identity": seed_set_identity,
    }
    for field, expected_value in expected_identity.items():
        if manifest.get(field) != expected_value:
            raise AggregateError(
                f"wrong {field}: {manifest.get(field)!r} != {expected_value!r}"
            )
    if manifest.get("publication_evidence") is not False:
        raise AggregateError("raw run manifest cannot assert publication evidence")
    if summary.get("publication_evidence") is not False:
        raise AggregateError("raw run summary cannot assert publication evidence")
    if (
        manifest.get("task") != task
        or manifest.get("method") != method
        or int(manifest.get("base_seed", -1)) != seed
    ):
        raise AggregateError("manifest cell identity mismatch")
    if summary.get("status") != "completed":
        raise AggregateError("run summary is not completed")
    expected_summary_identity = {
        "profile": profile,
        "phase": phase,
        "task": task,
        "method": method,
        "seed": seed,
    }
    for field, expected_value in expected_summary_identity.items():
        if summary.get(field) != expected_value:
            raise AggregateError(
                f"summary {field} mismatch: "
                f"{summary.get(field)!r} != {expected_value!r}"
            )
    if manifest.get("status") != "completed":
        raise AggregateError("run manifest is not completed")
    if manifest.get("config_digest") != expected_config_digest:
        raise AggregateError("mixed config digest")
    if int(manifest.get("rounds", -1)) != rounds:
        raise AggregateError("wrong horizon")
    resolved_config = manifest.get("resolved_config")
    if not isinstance(resolved_config, Mapping):
        raise AggregateError("manifest resolved_config must be an object")
    if resolved_config != expected_resolved_config:
        raise AggregateError("manifest resolved_config differs from loaded config")
    if config_digest(resolved_config) != manifest.get("config_digest"):
        raise AggregateError("manifest resolved_config digest is inconsistent")


def _assert_finite_json(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _assert_finite_json(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_finite_json(child, path=f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise AggregateError(f"nonfinite value at {path}")


def _load_rounds(path: Path, expected: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="ascii") as handle:
        for line in handle:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise AggregateError(f"non-object round record in {path}")
            _assert_finite_json(value)
            records.append(value)
    if len(records) != expected:
        raise AggregateError(f"{path} has {len(records)} rounds, expected {expected}")
    return records


def _relative(path: Path, *, repository_root: str | Path, raw_root: str | Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path(repository_root).resolve()).as_posix()
    except ValueError:
        try:
            relative = resolved.relative_to(Path(raw_root).resolve()).as_posix()
        except ValueError as error:
            raise AggregateError(
                f"raw input is outside its declared root: {path}"
            ) from error
        return f"external_raw/{relative}"


def _mean_or_none(values: Iterable[Any]) -> float | None:
    selected = [float(value) for value in values if value is not None]
    return float(np.mean(selected)) if selected else None


def _ratio_mean(
    records: Sequence[Mapping[str, Any]],
    numerator: str,
    denominator: str,
    *,
    zero_tolerance: float = 0.0,
) -> tuple[float | None, int]:
    ratios: list[float] = []
    zeros = 0
    for record in records:
        left = record.get(numerator)
        right = record.get(denominator)
        if left is None or right is None:
            continue
        denominator_value = float(right)
        if abs(denominator_value) <= zero_tolerance:
            zeros += 1
        else:
            ratios.append(float(left) / denominator_value)
    return (float(np.mean(ratios)) if ratios else None), zeros


def _recorded_ratio_mean(
    records: Sequence[Mapping[str, Any]],
    field: str,
    omitted_field: str,
) -> tuple[float | None, int]:
    values: list[float] = []
    omitted = 0
    for record in records:
        if record.get(omitted_field) is True:
            omitted += 1
        value = record.get(field)
        if value is not None:
            values.append(float(value))
    return (float(np.mean(values)) if values else None), omitted


def _numeric_equal(left: float, right: float) -> bool:
    tolerance = AuditTolerance().bound(max(abs(left), abs(right)), dimension=1)
    return abs(left - right) <= tolerance


def _optional_float(value: Any, *, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise AggregateError(f"round record has nonnumeric {field}")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise AggregateError(f"round record has nonnumeric {field}") from error
    if not math.isfinite(result):
        raise AggregateError(f"round record has nonfinite {field}")
    return result


def _validate_ratio_pair(
    record: Mapping[str, Any], value_field: str, omitted_field: str
) -> tuple[float | None, bool | None]:
    value = _optional_float(record.get(value_field), field=value_field)
    omitted = record.get(omitted_field)
    if omitted is not None and not isinstance(omitted, bool):
        raise AggregateError(f"round record has invalid {omitted_field}")
    if value is not None and omitted is not False:
        raise AggregateError(
            f"round record has finite {value_field} with {omitted_field}={omitted!r}"
        )
    if value is None and omitted is False:
        raise AggregateError(
            f"round record has null {value_field} with {omitted_field}=false"
        )
    return value, omitted


def _validate_ratio_lists(
    record: Mapping[str, Any], value_field: str, omitted_field: str
) -> tuple[list[float | None] | None, list[bool] | None]:
    raw_values = record.get(value_field)
    raw_omitted = record.get(omitted_field)
    if raw_values is None and raw_omitted is None:
        return None, None
    if not isinstance(raw_values, list) or not isinstance(raw_omitted, list):
        raise AggregateError(
            f"round record must provide {value_field} and {omitted_field} together"
        )
    if len(raw_values) != len(raw_omitted):
        raise AggregateError(f"round record has mismatched {value_field} lengths")
    values: list[float | None] = []
    omitted: list[bool] = []
    for index, (raw_value, raw_flag) in enumerate(
        zip(raw_values, raw_omitted, strict=True)
    ):
        value = _optional_float(raw_value, field=f"{value_field}[{index}]")
        if not isinstance(raw_flag, bool):
            raise AggregateError(f"round record has invalid {omitted_field}[{index}]")
        if value is not None and raw_flag:
            raise AggregateError(
                f"round record has finite {value_field}[{index}] with omitted=true"
            )
        if value is None and not raw_flag:
            raise AggregateError(
                f"round record has null {value_field}[{index}] with omitted=false"
            )
        values.append(value)
        omitted.append(raw_flag)
    return values, omitted


def _assert_optional_equal(left: Any, right: Any, *, description: str) -> None:
    left_value = _optional_float(left, field=f"{description} left")
    right_value = _optional_float(right, field=f"{description} right")
    if left_value is None or right_value is None:
        if left_value is not right_value:
            raise AggregateError(f"round record has inconsistent {description}")
        return
    if not _numeric_equal(left_value, right_value):
        raise AggregateError(f"round record has inconsistent {description}")


def _validate_derived_ratio(
    record: Mapping[str, Any],
    *,
    value_field: str,
    omitted_field: str,
    numerator: Any,
    denominator: Any,
) -> None:
    value, omitted = _validate_ratio_pair(record, value_field, omitted_field)
    numerator_value = _optional_float(numerator, field=f"{value_field} numerator")
    denominator_value = _optional_float(denominator, field=f"{value_field} denominator")
    if numerator_value is None or denominator_value is None:
        if value is not None or omitted is not None:
            raise AggregateError(
                f"round record has {value_field} without both primitive widths"
            )
        return
    expected_omitted = denominator_value == 0.0
    if omitted is not expected_omitted:
        raise AggregateError(
            f"round record violates the exact-zero denominator rule for {value_field}"
        )
    if expected_omitted:
        if value is not None:
            raise AggregateError(f"round record must omit {value_field}")
        return
    expected = numerator_value / denominator_value
    if value is None or not _numeric_equal(value, expected):
        raise AggregateError(f"round record has inconsistent {value_field}")


def _validate_ratio_records(
    records: Sequence[Mapping[str, Any]],
    *,
    method: str,
    rounds: int,
    config: Mapping[str, Any],
    action_count: int,
) -> None:
    checkpoints = {int(value) for value in config["diagnostics"]["checkpoints"]} | {
        int(value) for value in config["horizons"]["prefixes"] if int(value) <= rounds
    }
    checkpoints.add(rounds)
    specification = method_spec(method)
    solver_kind = specification.solver
    for expected_round, record in enumerate(records, start=1):
        if record.get("round") != expected_round:
            raise AggregateError("round records are not sequential")
        checkpoint = expected_round in checkpoints
        if record.get("diagnostic_checkpoint") is not checkpoint:
            raise AggregateError(
                "round record has the wrong diagnostic checkpoint flag"
            )

        exact_a_fields = (
            "solver_exact_width",
            "solver_upper_over_exact",
            "solver_upper_over_exact_A",
            "solver_upper_over_exact_A_denominator_omitted",
            "solver_exact_over_lower",
            "solver_exact_widths_all_actions",
            "solver_upper_over_exact_all_actions",
            "solver_upper_over_exact_A_all_actions",
            "solver_upper_over_exact_A_denominator_omitted_all_actions",
        )
        if (
            solver_kind == "cg"
            and not checkpoint
            and any(record.get(field) is not None for field in exact_a_fields)
        ):
            raise AggregateError(
                "CG exact-A diagnostic appears outside a dense checkpoint"
            )
        if (
            solver_kind == "cg"
            and checkpoint
            and record.get("solver_exact_width") is None
        ):
            raise AggregateError("CG checkpoint lacks the selected exact-A width")

        solver_ratio, solver_omitted = _validate_ratio_pair(
            record,
            "solver_upper_over_exact_A",
            "solver_upper_over_exact_A_denominator_omitted",
        )
        legacy_ratio = _optional_float(
            record.get("solver_upper_over_exact"),
            field="solver_upper_over_exact",
        )
        _assert_optional_equal(
            legacy_ratio,
            solver_ratio,
            description="legacy solver ratio alias",
        )
        _validate_derived_ratio(
            record,
            value_field="solver_upper_over_exact_A",
            omitted_field="solver_upper_over_exact_A_denominator_omitted",
            numerator=record.get("solver_width_upper"),
            denominator=record.get("solver_exact_width"),
        )

        operator_ratio, operator_omitted = _validate_ratio_pair(
            record,
            "exact_A_width_over_exact_V_width",
            "exact_A_width_over_exact_V_width_denominator_omitted",
        )
        total_ratio, total_omitted = _validate_ratio_pair(
            record,
            "operational_upper_width_over_exact_V_width",
            "operational_upper_width_over_exact_V_width_denominator_omitted",
        )

        current_widths = record.get("current_exact_widths")
        current_widths_alias = record.get("current_widths")
        if current_widths != current_widths_alias:
            raise AggregateError("round record has inconsistent current-width aliases")
        if current_widths is not None and (
            not isinstance(current_widths, list) or len(current_widths) != action_count
        ):
            raise AggregateError("round record has invalid current_exact_widths")
        if current_widths is not None:
            for index, value in enumerate(current_widths):
                if (
                    _optional_float(value, field=f"current_exact_widths[{index}]")
                    is None
                ):
                    raise AggregateError(
                        "round record has null current_exact_widths entry"
                    )
        if solver_kind == "cg" and not checkpoint and current_widths is not None:
            raise AggregateError(
                "CG exact-V diagnostic appears outside a dense checkpoint"
            )
        if solver_kind == "cg" and checkpoint and current_widths is None:
            raise AggregateError("CG checkpoint lacks exact V widths")
        score_widths = record.get("score_widths")
        if not isinstance(score_widths, list) or len(score_widths) != action_count:
            raise AggregateError("round record has invalid score_widths")
        for index, value in enumerate(score_widths):
            if _optional_float(value, field=f"score_widths[{index}]") is None:
                raise AggregateError("round record has null score_widths entry")
        if solver_kind == "cholesky" and specification.metric == "current_exact":
            if current_widths is None:
                raise AggregateError(
                    "current-exact Cholesky record lacks operational exact V widths"
                )
            if any(
                not _numeric_equal(current_width, score_width)
                for current_width, score_width in zip(current_widths, score_widths)
            ):
                raise AggregateError(
                    "current-exact Cholesky widths differ from score_widths"
                )
        elif solver_kind != "cg" and current_widths is not None:
            raise AggregateError("exact-V widths appear on a non-current-exact record")
        selected_action = record.get("selected_action")
        if isinstance(selected_action, bool) or not isinstance(selected_action, int):
            raise AggregateError("round record has invalid selected_action")
        selected_current_width: Any = None
        if current_widths is not None:
            if not 0 <= selected_action < len(current_widths):
                raise AggregateError("round record selected_action is out of range")
            selected_current_width = current_widths[selected_action]

        dense_fields = (
            "exact_A_width_over_exact_V_width",
            "exact_A_width_over_exact_V_width_denominator_omitted",
            "operational_upper_width_over_exact_V_width",
            "operational_upper_width_over_exact_V_width_denominator_omitted",
            "exact_A_width_over_exact_V_width_all_actions",
            "exact_A_width_over_exact_V_width_denominator_omitted_all_actions",
            "operational_upper_width_over_exact_V_width_all_actions",
            "operational_upper_width_over_exact_V_width_denominator_omitted_all_actions",
        )
        if not checkpoint:
            if any(record.get(field) is not None for field in dense_fields):
                raise AggregateError(
                    "V-referenced width ratio appears outside a dense checkpoint"
                )
        elif solver_kind == "cg":
            _validate_derived_ratio(
                record,
                value_field="exact_A_width_over_exact_V_width",
                omitted_field=("exact_A_width_over_exact_V_width_denominator_omitted"),
                numerator=record.get("solver_exact_width"),
                denominator=selected_current_width,
            )
            _validate_derived_ratio(
                record,
                value_field="operational_upper_width_over_exact_V_width",
                omitted_field=(
                    "operational_upper_width_over_exact_V_width_denominator_omitted"
                ),
                numerator=record.get("solver_width_upper"),
                denominator=selected_current_width,
            )
        elif any(record.get(field) is not None for field in dense_fields):
            raise AggregateError("V-referenced width ratio appears on a non-CG record")

        if (
            solver_ratio is not None
            and operator_ratio is not None
            and total_ratio is not None
            and not _numeric_equal(total_ratio, solver_ratio * operator_ratio)
        ):
            raise AggregateError("round record has inconsistent operational ratio")
        if operator_omitted != total_omitted:
            raise AggregateError("round record has inconsistent V denominator flags")

        scalar_specs = (
            (
                "solver_upper_over_exact_A_all_actions",
                "solver_upper_over_exact_A_denominator_omitted_all_actions",
                "solver_upper_over_exact_A",
                "solver_upper_over_exact_A_denominator_omitted",
            ),
            (
                "exact_A_width_over_exact_V_width_all_actions",
                "exact_A_width_over_exact_V_width_denominator_omitted_all_actions",
                "exact_A_width_over_exact_V_width",
                "exact_A_width_over_exact_V_width_denominator_omitted",
            ),
            (
                "operational_upper_width_over_exact_V_width_all_actions",
                "operational_upper_width_over_exact_V_width_denominator_omitted_all_actions",
                "operational_upper_width_over_exact_V_width",
                "operational_upper_width_over_exact_V_width_denominator_omitted",
            ),
        )
        list_values: dict[str, list[float | None] | None] = {}
        list_flags: dict[str, list[bool] | None] = {}
        for values_field, flags_field, scalar_field, scalar_flag_field in scalar_specs:
            values, flags = _validate_ratio_lists(record, values_field, flags_field)
            list_values[values_field] = values
            list_flags[flags_field] = flags
            if values is not None and flags is not None:
                if len(values) != action_count:
                    raise AggregateError(
                        f"round record has the wrong action count for {values_field}"
                    )
                if not 0 <= selected_action < len(values):
                    raise AggregateError(
                        f"round record selected_action is out of range for {values_field}"
                    )
                _assert_optional_equal(
                    record.get(scalar_field),
                    values[selected_action],
                    description=f"selected {scalar_field}",
                )
                if record.get(scalar_flag_field) is not flags[selected_action]:
                    raise AggregateError(
                        f"round record has inconsistent selected {scalar_flag_field}"
                    )

        legacy_values = record.get("solver_upper_over_exact_all_actions")
        primary_values = list_values["solver_upper_over_exact_A_all_actions"]
        if legacy_values != primary_values:
            raise AggregateError("round record has inconsistent solver ratio aliases")

        upper_widths = record.get("solver_upper_widths_all_actions")
        exact_widths = record.get("solver_exact_widths_all_actions")
        if solver_kind == "cg" and checkpoint:
            if not isinstance(upper_widths, list) or not isinstance(exact_widths, list):
                raise AggregateError("CG checkpoint lacks all-action width primitives")
            if current_widths is None:
                raise AggregateError("CG checkpoint lacks exact V widths")
            if solver_omitted is None or legacy_ratio is None and not solver_omitted:
                raise AggregateError("CG checkpoint lacks the selected exact-A ratio")
            if (
                _optional_float(
                    record.get("solver_exact_width"), field="solver_exact_width"
                )
                is None
            ):
                raise AggregateError("CG checkpoint lacks the selected exact-A width")
            if any(value is None for value in list_values.values()) or any(
                value is None for value in list_flags.values()
            ):
                raise AggregateError("CG checkpoint lacks complete ratio vectors")
            lengths = {
                len(upper_widths),
                len(exact_widths),
                len(current_widths),
                *(len(value) for value in list_values.values() if value is not None),
            }
            if len(lengths) != 1:
                raise AggregateError("CG checkpoint ratio vectors have mixed lengths")
            _assert_optional_equal(
                record.get("solver_width_upper"),
                upper_widths[selected_action],
                description="selected solver_width_upper",
            )
            _assert_optional_equal(
                record.get("solver_exact_width"),
                exact_widths[selected_action],
                description="selected solver_exact_width",
            )
            for index in range(len(upper_widths)):
                for value_field, omitted_field, numerator, denominator in (
                    (
                        "solver_upper_over_exact_A_all_actions",
                        "solver_upper_over_exact_A_denominator_omitted_all_actions",
                        upper_widths[index],
                        exact_widths[index],
                    ),
                    (
                        "exact_A_width_over_exact_V_width_all_actions",
                        "exact_A_width_over_exact_V_width_denominator_omitted_all_actions",
                        exact_widths[index],
                        current_widths[index],
                    ),
                    (
                        "operational_upper_width_over_exact_V_width_all_actions",
                        "operational_upper_width_over_exact_V_width_denominator_omitted_all_actions",
                        upper_widths[index],
                        current_widths[index],
                    ),
                ):
                    values = list_values[value_field]
                    flags = list_flags[omitted_field]
                    if values is None or flags is None:
                        raise AggregateError(
                            f"CG checkpoint lacks complete {value_field} diagnostics"
                        )
                    denominator_value = _optional_float(
                        denominator, field=f"{value_field} denominator"
                    )
                    numerator_value = _optional_float(
                        numerator, field=f"{value_field} numerator"
                    )
                    if denominator_value is None or numerator_value is None:
                        raise AggregateError(
                            f"CG checkpoint has null width primitive for {value_field}"
                        )
                    expected_omitted = denominator_value == 0.0
                    if flags[index] is not expected_omitted:
                        raise AggregateError(
                            f"round record violates the exact-zero denominator rule for {value_field}"
                        )
                    expected_value = (
                        None
                        if expected_omitted
                        else numerator_value / denominator_value
                    )
                    _assert_optional_equal(
                        values[index],
                        expected_value,
                        description=f"{value_field}[{index}]",
                    )


def _validate_round_semantics(
    records: Sequence[Mapping[str, Any]],
    *,
    task: str,
    method: str,
    feature_dimension: int,
    action_count: int,
) -> None:
    if feature_dimension <= 0 or action_count <= 0:
        raise AggregateError("feature and action dimensions must be positive")
    expected_theorem_applicable = task != LABEL_TASK and method in THEOREM_METHODS
    prefix_confidence = True
    cumulative_regret = 0.0
    for record in records:
        coverage = record.get("reference_confidence_all_actions")
        if not isinstance(coverage, bool):
            raise AggregateError(
                "round record has invalid reference_confidence_all_actions"
            )
        prefix_confidence = prefix_confidence and coverage
        if record.get("prefix_simultaneous_reference_confidence") is not (
            prefix_confidence
        ):
            raise AggregateError("round record has inconsistent prefix confidence")
        if record.get("theorem_applicable") is not expected_theorem_applicable:
            raise AggregateError("round record has inconsistent theorem applicability")
        if record.get("analytic_certificate_valid_in_exact_arithmetic") is not (
            expected_theorem_applicable
        ):
            raise AggregateError("round record has inconsistent analytic status")

        true_means_raw = record.get("true_means")
        if not isinstance(true_means_raw, list) or not true_means_raw:
            raise AggregateError("round record lacks all-action true means")
        if len(true_means_raw) != action_count:
            raise AggregateError("round record has the wrong all-action mean count")
        true_means = [
            _optional_float(value, field="true_means") for value in true_means_raw
        ]
        if any(value is None for value in true_means):
            raise AggregateError("round record has a null all-action true mean")
        checked_true_means = [float(value) for value in true_means if value is not None]
        selected_action = record.get("selected_action")
        if (
            isinstance(selected_action, bool)
            or not isinstance(selected_action, int)
            or not 0 <= selected_action < len(checked_true_means)
        ):
            raise AggregateError("round record has invalid selected_action")

        solver_convergence = record.get("solver_all_actions_converged")
        if method_spec(method).solver == "none":
            if solver_convergence is not None:
                raise AggregateError(
                    "round record has solver convergence for a solver-free method"
                )
        elif not isinstance(solver_convergence, bool):
            raise AggregateError("round record lacks solver convergence diagnostics")
        envelope_values = (
            record.get("current_taylor_envelope_valid"),
            record.get("current_misspecification_envelope_valid"),
        )
        envelopes_apply = task != LABEL_TASK and method != "linucb_fixed_features"
        if envelopes_apply and any(
            not isinstance(value, bool) for value in envelope_values
        ):
            raise AggregateError("round record lacks envelope diagnostics")
        if not envelopes_apply and any(value is not None for value in envelope_values):
            raise AggregateError(
                "round record has envelope diagnostics where they do not apply"
            )

        instantaneous_regret = _optional_float(
            record.get("instantaneous_pseudo_regret"),
            field="instantaneous_pseudo_regret",
        )
        recorded_cumulative = _optional_float(
            record.get("cumulative_pseudo_regret"),
            field="cumulative_pseudo_regret",
        )
        if instantaneous_regret is None or recorded_cumulative is None:
            raise AggregateError("round record lacks regret primitives")
        expected_selected_mean = checked_true_means[selected_action]
        expected_optimal_mean = max(checked_true_means)
        _assert_optional_equal(
            record.get("selected_mean"),
            expected_selected_mean,
            description="selected mean",
        )
        _assert_optional_equal(
            record.get("optimal_mean"),
            expected_optimal_mean,
            description="optimal mean",
        )
        if not _numeric_equal(
            instantaneous_regret, expected_optimal_mean - expected_selected_mean
        ):
            raise AggregateError("round record has inconsistent instantaneous regret")
        cumulative_regret += instantaneous_regret
        if not _numeric_equal(cumulative_regret, recorded_cumulative):
            raise AggregateError("round record has inconsistent cumulative regret")

        try:
            expected_reasons, expected_float64_pass = derive_float64_diagnostic_status(
                solver_all_actions_converged=record.get("solver_all_actions_converged"),
                current_taylor_envelope_valid=record.get(
                    "current_taylor_envelope_valid"
                ),
                current_misspecification_envelope_valid=record.get(
                    "current_misspecification_envelope_valid"
                ),
            )
        except ValueError as error:
            raise AggregateError(
                f"invalid float64 diagnostic primitive: {error}"
            ) from error
        recorded_reasons = record.get("deterministic_failure_reasons")
        if not isinstance(recorded_reasons, list) or any(
            not isinstance(reason, str) for reason in recorded_reasons
        ):
            raise AggregateError(
                "round record has invalid deterministic failure reasons"
            )
        if recorded_reasons != expected_reasons:
            raise AggregateError(
                "round record deterministic failure reasons disagree with primitives"
            )
        if record.get("deterministic_failure") is not bool(expected_reasons):
            raise AggregateError(
                "round record deterministic failure status disagrees with primitives"
            )
        if record.get("float64_diagnostic_pass") is not expected_float64_pass:
            raise AggregateError(
                "round record float64 diagnostic status disagrees with primitives"
            )
        if record.get("verified_numerical_certificate") is not False:
            raise AggregateError(
                "realistic transport does not produce verified numerical certificates"
            )
        if record.get("theorem_bound_comparison_rule") != (
            THEOREM_BOUND_COMPARISON_RULE
        ):
            raise AggregateError("round record has an unknown theorem comparison rule")
        tolerance = _optional_float(
            record.get("theorem_bound_comparison_tolerance"),
            field="theorem_bound_comparison_tolerance",
        )
        if tolerance is None or tolerance < 0.0:
            raise AggregateError(
                "round record has invalid theorem comparison tolerance"
            )
        expected_tolerance = (
            4096.0
            * np.finfo(np.float64).eps
            * feature_dimension
            * max(1.0, max(abs(value) for value in checked_true_means))
        )
        corrected_centers_raw = record.get("corrected_centers")
        if method != "linucb_fixed_features":
            if not isinstance(corrected_centers_raw, list) or not corrected_centers_raw:
                raise AggregateError("round record lacks corrected-center diagnostics")
            corrected_centers = [
                _optional_float(value, field="corrected_centers")
                for value in corrected_centers_raw
            ]
            if any(value is None for value in corrected_centers):
                raise AggregateError("round record has a null corrected center")
            expected_tolerance = max(
                expected_tolerance,
                4096.0
                * np.finfo(np.float64).eps
                * feature_dimension
                * max(
                    1.0,
                    max(
                        abs(float(value))
                        for value in corrected_centers
                        if value is not None
                    ),
                ),
            )
        elif corrected_centers_raw is not None:
            raise AggregateError("LinUCB round unexpectedly records corrected centers")
        if not _numeric_equal(tolerance, expected_tolerance):
            raise AggregateError(
                "round record has the wrong theorem comparison tolerance"
            )
        instantaneous_rhs = _optional_float(
            record.get("instantaneous_theorem_rhs"),
            field="instantaneous_theorem_rhs",
        )
        cumulative_rhs = _optional_float(
            record.get("sharp_theorem_rhs"),
            field="sharp_theorem_rhs",
        )
        if expected_theorem_applicable:
            if instantaneous_rhs is None or cumulative_rhs is None:
                raise AggregateError(
                    "theorem-applicable round lacks finite theorem RHS primitives"
                )
        elif instantaneous_rhs is not None or cumulative_rhs is not None:
            raise AggregateError(
                "theorem-inapplicable round records theorem RHS primitives"
            )
        try:
            expected_instantaneous_status = derive_theorem_bound_status(
                theorem_applicable=expected_theorem_applicable,
                confidence_event=coverage,
                regret=instantaneous_regret,
                rhs=instantaneous_rhs,
                comparison_tolerance=tolerance,
            )
            expected_cumulative_status = derive_theorem_bound_status(
                theorem_applicable=expected_theorem_applicable,
                confidence_event=prefix_confidence,
                regret=recorded_cumulative,
                rhs=cumulative_rhs,
                comparison_tolerance=tolerance,
            )
        except ValueError as error:
            raise AggregateError(
                f"invalid theorem-status primitive: {error}"
            ) from error
        if record.get("instantaneous_theorem_bound_status") != (
            expected_instantaneous_status
        ):
            raise AggregateError(
                "round record instantaneous theorem status disagrees with primitives"
            )
        if record.get("cumulative_theorem_bound_status") != (
            expected_cumulative_status
        ):
            raise AggregateError(
                "round record cumulative theorem status disagrees with primitives"
            )


def _semantic_status(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    boolean_fields = (
        "analytic_certificate_valid_in_exact_arithmetic",
        "deterministic_failure",
        "float64_diagnostic_pass",
        "verified_numerical_certificate",
    )
    for record in records:
        for field in boolean_fields:
            if not isinstance(record.get(field), bool):
                raise AggregateError(f"round record has invalid {field}")
    return {
        "analytic_certificate_valid_in_exact_arithmetic": all(
            bool(record["analytic_certificate_valid_in_exact_arithmetic"])
            for record in records
        ),
        "deterministic_failure": any(
            bool(record.get("deterministic_failure")) for record in records
        ),
        "float64_diagnostic_pass": all(
            bool(record.get("float64_diagnostic_pass")) for record in records
        ),
        "verified_numerical_certificate": all(
            bool(record.get("verified_numerical_certificate")) for record in records
        ),
        "instantaneous_theorem_event_violation_count": sum(
            record.get("instantaneous_theorem_bound_status")
            == "bound_violation_on_event"
            for record in records
        ),
        "cumulative_theorem_event_violation_count": sum(
            record.get("cumulative_theorem_bound_status") == "bound_violation_on_event"
            for record in records
        ),
    }


def _validated_runtime_identity(
    manifest: Mapping[str, Any],
    summary: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate per-cell execution evidence and return its stable identity."""

    runtime = manifest.get("runtime")
    if not isinstance(runtime, Mapping):
        raise AggregateError("run manifest lacks runtime provenance")
    execution = runtime.get("execution")
    if not isinstance(execution, Mapping):
        raise AggregateError("run manifest lacks execution provenance")
    expected_limit = int(config["execution"]["blas_threads_per_worker"])
    if expected_limit != 1:
        raise AggregateError("configured BLAS thread limit must be exactly one")
    if (
        execution.get("workers") != 1
        or execution.get("actual_concurrent_workers") != 1
        or execution.get("requested_workers")
        != int(config.get("workers", config["execution"]["workers"]))
        or execution.get("blas_threads_per_worker") != expected_limit
        or execution.get("execution_model")
        != "sequential_parent_with_fresh_spawned_process_per_cell"
        or isinstance(execution.get("worker_pid"), bool)
        or not isinstance(execution.get("worker_pid"), int)
        or int(execution["worker_pid"]) <= 0
    ):
        raise AggregateError("run manifest has invalid worker execution provenance")
    thread_control = execution.get("thread_control")
    if (
        not isinstance(thread_control, Mapping)
        or thread_control.get("requested_limit") != expected_limit
        or thread_control.get("verified") is not True
    ):
        raise AggregateError("run manifest lacks verified numerical thread control")
    controlled_pools: list[Mapping[str, Any]] = []
    for edge in ("active_pools_before", "active_pools_after"):
        pools = thread_control.get(edge)
        if not isinstance(pools, list):
            raise AggregateError(f"run manifest lacks thread-pool snapshot {edge}")
        for pool in pools:
            if not isinstance(pool, Mapping):
                raise AggregateError("run manifest has malformed thread-pool evidence")
            if pool.get("user_api") in {"blas", "openmp"}:
                controlled_pools.append(pool)
                if pool.get("num_threads") != expected_limit:
                    raise AggregateError(
                        "run manifest records an unenforced numerical thread limit"
                    )
    if not controlled_pools:
        raise AggregateError("run manifest records no active numerical thread pool")

    memory = execution.get("memory_measurement")
    required_inclusions = {
        "interpreter_startup",
        "deserialized_dataset_and_environment",
        "model_optimizer_and_replay_state",
        "operational_computation",
        "checkpoint_diagnostics",
    }
    if (
        not isinstance(memory, Mapping)
        or memory.get("metric") != "fresh_process_peak_resident_set_size_bytes"
        or memory.get("isolation") != "one_fresh_spawned_process_per_cell"
        or memory.get("includes_startup_and_deserialization_peak") is not True
        or set(memory.get("includes", ())) != required_inclusions
        or isinstance(memory.get("peak_rss_bytes"), bool)
        or not isinstance(memory.get("peak_rss_bytes"), int)
        or int(memory["peak_rss_bytes"]) <= 0
        or summary.get("policy_memory_measurement") != memory
        or summary.get("policy_peak_rss_bytes") != memory.get("peak_rss_bytes")
    ):
        raise AggregateError("run manifest has invalid cell-attributable memory data")

    identity = {
        field: runtime.get(field)
        for field in ("python", "packages", "module_origins", "platform")
    }
    if any(not isinstance(value, Mapping) for value in identity.values()):
        raise AggregateError("run manifest has incomplete runtime identity")
    identity["execution"] = {
        "workers": execution["workers"],
        "requested_workers": execution["requested_workers"],
        "actual_concurrent_workers": execution["actual_concurrent_workers"],
        "execution_model": execution["execution_model"],
        "blas_threads_per_worker": execution["blas_threads_per_worker"],
        "thread_control": dict(thread_control),
        "memory_measurement": {
            field: memory[field]
            for field in (
                "metric",
                "backend",
                "includes",
                "includes_startup_and_deserialization_peak",
                "isolation",
            )
        },
    }
    return identity


def _run_metrics(
    records: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    prefix: int,
) -> dict[str, Any]:
    selected = records[:prefix]
    last = selected[-1]
    d_ratio, d_zeros = _ratio_mean(selected, "D_Q", "d_Th")
    tail_ratio, tail_zeros = _ratio_mean(
        selected, "nystrom_trace_tail", "nystrom_operator_tail"
    )
    operator_ratio, operator_zeros = _recorded_ratio_mean(
        selected,
        "exact_A_width_over_exact_V_width",
        "exact_A_width_over_exact_V_width_denominator_omitted",
    )
    total_ratio, total_zeros = _recorded_ratio_mean(
        selected,
        "operational_upper_width_over_exact_V_width",
        "operational_upper_width_over_exact_V_width_denominator_omitted",
    )
    solver_ratio, solver_zeros = _recorded_ratio_mean(
        selected,
        "solver_upper_over_exact_A",
        "solver_upper_over_exact_A_denominator_omitted",
    )
    return {
        "cumulative_regret": float(last["cumulative_pseudo_regret"]),
        "action_accuracy": (
            float(np.mean([bool(record["action_correct"]) for record in selected]))
            if last.get("action_correct") is not None
            else None
        ),
        "simultaneous_reference_confidence": bool(
            all(bool(record["reference_confidence_all_actions"]) for record in selected)
        ),
        "simultaneous_method_optimism": bool(
            all(bool(record["method_optimism_all_actions"]) for record in selected)
        ),
        "theorem_applicable": bool(last["theorem_applicable"]),
        "theorem_bound_nonvacuous": (
            bool(
                float(last["sharp_theorem_rhs"])
                < float(last["cumulative_trivial_regret_bound"])
            )
            if last.get("sharp_theorem_rhs") is not None
            else None
        ),
        "sharp_theorem_rhs": last.get("sharp_theorem_rhs"),
        "trivial_regret_bound": float(last["cumulative_trivial_regret_bound"]),
        "zero_regret": float(last["cumulative_pseudo_regret"]) == 0.0,
        "algorithm_seconds": float(
            sum(float(record["algorithm_seconds"]) for record in selected)
        ),
        "operator_construction_seconds": float(
            sum(float(record["operator_construction_seconds"]) for record in selected)
        ),
        "replay_gradient_construction_seconds": float(
            sum(
                float(record.get("replay_gradient_construction_seconds", 0.0))
                for record in selected
            )
        ),
        "transport_certificate_seconds": float(
            sum(float(record["transport_certificate_seconds"]) for record in selected)
        ),
        "action_scoring_seconds": float(
            sum(float(record["action_scoring_seconds"]) for record in selected)
        ),
        "representation_update_seconds": float(
            sum(float(record["representation_update_seconds"]) for record in selected)
        ),
        "diagnostic_seconds": float(
            sum(float(record["diagnostic_seconds"]) for record in selected)
        ),
        "end_to_end_round_seconds": float(
            sum(float(record["end_to_end_round_seconds"]) for record in selected)
        ),
        "data_loading_seconds": float(summary["data_loading_seconds"]),
        "preprocessing_seconds": float(summary["preprocessing_seconds"]),
        "teacher_environment_seconds": float(summary["teacher_environment_seconds"]),
        "peak_rss_bytes": int(summary["policy_peak_rss_bytes"]),
        "logical_operator_bytes": int(
            max(int(record["operator_storage_bytes"]) for record in selected)
        ),
        "cg_iterations": int(
            sum(int(record["solver_iterations_all_actions"]) for record in selected)
        ),
        "cg_matvecs": int(
            sum(
                int(record["solver_algorithm_matvecs_all_actions"])
                + int(record["solver_audit_matvecs_all_actions"])
                for record in selected
            )
        ),
        "solver_seconds": float(
            sum(float(record["solver_seconds_all_actions"]) for record in selected)
        ),
        "D_Q_minus_d_Th": _mean_or_none(
            record.get("D_Q_minus_d_Th") for record in selected
        ),
        "D_Q_over_d_Th": d_ratio,
        "D_Q_over_d_Th_zero_denominators": d_zeros,
        "trace_tail_over_operator_tail": tail_ratio,
        "trace_tail_over_operator_tail_zero_denominators": tail_zeros,
        "kappa_minus": _mean_or_none(record.get("kappa_minus") for record in selected),
        "oracle_kappa_minus": _mean_or_none(
            record.get("nystrom_oracle_generalized_kappa_minus") for record in selected
        ),
        "width_upper_over_exact": solver_ratio,
        "solver_upper_over_exact_A": solver_ratio,
        "exact_A_width_over_exact_V_width": operator_ratio,
        "operational_upper_width_over_exact_V_width": total_ratio,
        "exact_A_width_over_exact_V_width_zero_denominators": operator_zeros,
        "operational_upper_width_over_exact_V_width_zero_denominators": total_zeros,
        "solver_upper_over_exact_A_zero_denominators": solver_zeros,
        "solver_alpha": _mean_or_none(
            record.get("solver_alpha") for record in selected
        ),
        "fraction_bonus_below_gap": float(
            np.mean(
                [bool(record["bonus_below_true_action_gap"]) for record in selected]
            )
        ),
        "fraction_bonus_exceeds_range": float(
            np.mean(
                [
                    float(record["selected_confidence_bonus"])
                    > float(record["reward_range"])
                    for record in selected
                ]
            )
        ),
        "historical_misspecification_envelope": _mean_or_none(
            record.get("historical_misspecification_envelope") for record in selected
        ),
        "current_misspecification_envelope": _mean_or_none(
            record.get("current_misspecification_envelope") for record in selected
        ),
        **_semantic_status(selected),
    }


def _metric_summary(
    rows: Sequence[Mapping[str, Any]], field: str
) -> dict[str, Any] | None:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    return describe(values) if values else None


def _method_statistics(run_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for row in run_rows:
        grouped[(str(row["task"]), str(row["method"]), int(row["prefix"]))].append(row)
    output: list[dict[str, Any]] = []
    numeric_fields = (
        "cumulative_regret",
        "action_accuracy",
        "algorithm_seconds",
        "operator_construction_seconds",
        "replay_gradient_construction_seconds",
        "transport_certificate_seconds",
        "action_scoring_seconds",
        "representation_update_seconds",
        "diagnostic_seconds",
        "end_to_end_round_seconds",
        "data_loading_seconds",
        "preprocessing_seconds",
        "teacher_environment_seconds",
        "peak_rss_bytes",
        "logical_operator_bytes",
        "cg_iterations",
        "cg_matvecs",
        "solver_seconds",
        "D_Q_minus_d_Th",
        "D_Q_over_d_Th",
        "trace_tail_over_operator_tail",
        "kappa_minus",
        "oracle_kappa_minus",
        "width_upper_over_exact",
        "solver_upper_over_exact_A",
        "exact_A_width_over_exact_V_width",
        "operational_upper_width_over_exact_V_width",
        "solver_alpha",
        "fraction_bonus_below_gap",
        "fraction_bonus_exceeds_range",
        "historical_misspecification_envelope",
        "current_misspecification_envelope",
    )
    for key in sorted(grouped):
        task, method, prefix = key
        rows = sorted(grouped[key], key=lambda row: int(row["seed"]))
        reference_successes = sum(
            bool(row["simultaneous_reference_confidence"]) for row in rows
        )
        optimism_successes = sum(
            bool(row["simultaneous_method_optimism"]) for row in rows
        )
        total = len(rows)
        output.append(
            {
                "task": task,
                "method": method,
                "prefix": prefix,
                "seed_count": total,
                "metrics": {
                    field: _metric_summary(rows, field) for field in numeric_fields
                },
                "reference_confidence": {
                    "successes": reference_successes,
                    "total": total,
                    "proportion": reference_successes / total,
                    "clopper_pearson_95": clopper_pearson_interval(
                        reference_successes, total
                    ),
                    "one_sided_upper_95": clopper_pearson_upper_bound(
                        reference_successes, total
                    ),
                    "role": rows[0]["confidence_role"],
                },
                "method_optimism": {
                    "successes": optimism_successes,
                    "total": total,
                    "proportion": optimism_successes / total,
                    "clopper_pearson_95": clopper_pearson_interval(
                        optimism_successes, total
                    ),
                    "one_sided_upper_95": clopper_pearson_upper_bound(
                        optimism_successes, total
                    ),
                    "role": rows[0]["confidence_role"],
                },
                "theorem_bound_nonvacuous": {
                    "applicable_runs": sum(
                        row["theorem_bound_nonvacuous"] is not None for row in rows
                    ),
                    "successes": sum(
                        row["theorem_bound_nonvacuous"] is True for row in rows
                    ),
                },
                "semantic_status": {
                    "analytic_certificate_valid_runs": sum(
                        bool(row["analytic_certificate_valid_in_exact_arithmetic"])
                        for row in rows
                    ),
                    "deterministic_failure_runs": sum(
                        bool(row["deterministic_failure"]) for row in rows
                    ),
                    "float64_diagnostic_failure_runs": sum(
                        not bool(row["float64_diagnostic_pass"]) for row in rows
                    ),
                    "verified_numerical_certificate_runs": sum(
                        bool(row["verified_numerical_certificate"]) for row in rows
                    ),
                    "instantaneous_theorem_event_violations": sum(
                        int(row["instantaneous_theorem_event_violation_count"])
                        for row in rows
                    ),
                    "cumulative_theorem_event_violations": sum(
                        int(row["cumulative_theorem_event_violation_count"])
                        for row in rows
                    ),
                },
                "zero_regret_count": sum(bool(row["zero_regret"]) for row in rows),
                "D_Q_over_d_Th_zero_denominators": sum(
                    int(row["D_Q_over_d_Th_zero_denominators"]) for row in rows
                ),
                "trace_tail_over_operator_tail_zero_denominators": sum(
                    int(row["trace_tail_over_operator_tail_zero_denominators"])
                    for row in rows
                ),
                "solver_upper_over_exact_A_zero_denominators": sum(
                    int(row["solver_upper_over_exact_A_zero_denominators"])
                    for row in rows
                ),
                "exact_A_width_over_exact_V_width_zero_denominators": sum(
                    int(row["exact_A_width_over_exact_V_width_zero_denominators"])
                    for row in rows
                ),
                "operational_upper_width_over_exact_V_width_zero_denominators": sum(
                    int(
                        row[
                            "operational_upper_width_over_exact_V_width_zero_denominators"
                        ]
                    )
                    for row in rows
                ),
            }
        )
    return output


def _paired_comparisons(
    run_rows: Sequence[Mapping[str, Any]],
    *,
    maximum_prefix: int,
    selection: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    lookup = {
        (str(row["task"]), str(row["method"]), int(row["seed"])): row
        for row in run_rows
        if int(row["prefix"]) == maximum_prefix
    }
    controlled = EXPECTED_TASKS[1:]
    comparisons: list[tuple[str, str, str]] = []
    for task in controlled:
        comparisons.extend(
            (
                (
                    task,
                    "transport_exact_corrected_cholesky",
                    "frozen_reference_corrected_cholesky",
                ),
                (
                    task,
                    "transport_exact_corrected_cholesky",
                    "naive_current_corrected_cholesky",
                ),
                (
                    task,
                    "transport_exact_corrected_cholesky",
                    "transport_exact_uncorrected_tangent_cholesky",
                ),
                (
                    task,
                    "transport_exact_corrected_cg_1e-4",
                    "transport_exact_corrected_cholesky",
                ),
            )
        )
        if selection is not None:
            practical = selection.get("practical_nystrom", {})
            if not isinstance(practical, Mapping) or task not in practical:
                raise AggregateError(
                    f"selection lacks required practical Nyström choice for {task}"
                )
            comparisons.append(
                (
                    task,
                    str(practical[task]),
                    "transport_exact_corrected_cholesky",
                )
            )
    comparisons.append(
        (
            "covtype_label_bandit",
            "transport_exact_corrected_cholesky",
            "linucb_fixed_features",
        )
    )
    output: list[dict[str, Any]] = []
    for task, first, second in comparisons:
        first_values = {
            seed: float(row["cumulative_regret"])
            for (row_task, method, seed), row in lookup.items()
            if row_task == task and method == first
        }
        second_values = {
            seed: float(row["cumulative_regret"])
            for (row_task, method, seed), row in lookup.items()
            if row_task == task and method == second
        }
        result = paired_seed_bootstrap(
            first_values,
            second_values,
            bootstrap_seed=derive_seed(
                0, "realistic_transport/bootstrap/v1", task, first, second
            ),
        )
        output.append(
            {
                "task": task,
                "first": first,
                "second": second,
                "metric": "cumulative_regret",
                "prefix": maximum_prefix,
                "estimate": result,
            }
        )
    return output


def _controlled_task_secondary_comparisons(
    run_rows: Sequence[Mapping[str, Any]],
    *,
    maximum_prefix: int,
    selection: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Average B/C values within each seed before resampling seeds."""

    lookup = {
        (str(row["task"]), str(row["method"]), int(row["seed"])): float(
            row["cumulative_regret"]
        )
        for row in run_rows
        if int(row["prefix"]) == maximum_prefix
    }
    controlled = EXPECTED_TASKS[1:]
    specifications: list[tuple[str, Mapping[str, str], Mapping[str, str]]] = []
    for name, first, second in (
        (
            "exact_corrected_vs_frozen_reference",
            "transport_exact_corrected_cholesky",
            "frozen_reference_corrected_cholesky",
        ),
        (
            "exact_corrected_vs_naive_current",
            "transport_exact_corrected_cholesky",
            "naive_current_corrected_cholesky",
        ),
        (
            "exact_corrected_vs_uncorrected_tangent",
            "transport_exact_corrected_cholesky",
            "transport_exact_uncorrected_tangent_cholesky",
        ),
        (
            "exact_cg_vs_exact_cholesky",
            "transport_exact_corrected_cg_1e-4",
            "transport_exact_corrected_cholesky",
        ),
    ):
        specifications.append(
            (
                name,
                {task: first for task in controlled},
                {task: second for task in controlled},
            )
        )
    if selection is not None:
        practical = selection.get("practical_nystrom")
        if not isinstance(practical, Mapping) or any(
            task not in practical for task in controlled
        ):
            raise AggregateError(
                "selection lacks both controlled-task practical Nyström choices"
            )
        specifications.append(
            (
                "practical_nystrom_vs_exact_corrected",
                {task: str(practical[task]) for task in controlled},
                {task: "transport_exact_corrected_cholesky" for task in controlled},
            )
        )

    output: list[dict[str, Any]] = []
    for name, first_methods, second_methods in specifications:
        first_by_task: dict[str, dict[int, float]] = {}
        second_by_task: dict[str, dict[int, float]] = {}
        for task in controlled:
            first_by_task[task] = {
                seed: value
                for (row_task, method, seed), value in lookup.items()
                if row_task == task and method == first_methods[task]
            }
            second_by_task[task] = {
                seed: value
                for (row_task, method, seed), value in lookup.items()
                if row_task == task and method == second_methods[task]
            }
        estimate = controlled_task_average_bootstrap(
            first_by_task,
            second_by_task,
            tasks=controlled,
            bootstrap_seed=derive_seed(
                0, "realistic_transport/controlled_bootstrap/v1", name
            ),
        )
        output.append(
            {
                "name": name,
                "tasks": list(controlled),
                "first_methods": dict(first_methods),
                "second_methods": dict(second_methods),
                "metric": "cumulative_regret",
                "prefix": maximum_prefix,
                "estimate": estimate,
            }
        )
    return output


def _rank_tolerance_effects(
    run_rows: Sequence[Mapping[str, Any]], maximum_prefix: int
) -> list[dict[str, Any]]:
    corner_methods = tuple(
        method
        for method in APPROXIMATE_METHODS
        if method_spec(method).rank in {16, 64}
        and method_spec(method).cg_tolerance in {1e-2, 1e-6}
    )
    metrics = {
        "cumulative_regret": lambda row: float(row["cumulative_regret"]),
        "log_algorithm_seconds": lambda row: math.log(
            max(float(row["algorithm_seconds"]), np.finfo(float).tiny)
        ),
        "logical_operator_bytes": lambda row: float(row["logical_operator_bytes"]),
        "width_upper_over_exact": lambda row: row["width_upper_over_exact"],
        "theorem_bound_nonvacuous": lambda row: (
            float(row["theorem_bound_nonvacuous"])
            if row["theorem_bound_nonvacuous"] is not None
            else None
        ),
    }
    output: list[dict[str, Any]] = []
    for task in EXPECTED_TASKS:
        task_rows = [
            row
            for row in run_rows
            if row["task"] == task
            and row["method"] in corner_methods
            and int(row["prefix"]) == maximum_prefix
        ]
        for metric, transform in metrics.items():
            observations: list[tuple[int, int, float, float]] = []
            for row in task_rows:
                value = transform(row)
                if value is None:
                    continue
                spec = method_spec(str(row["method"]))
                assert spec.rank is not None and spec.cg_tolerance is not None
                observations.append(
                    (int(row["seed"]), spec.rank, spec.cg_tolerance, float(value))
                )
            if not observations:
                continue
            try:
                estimate = four_corner_rank_tolerance_contrasts(
                    observations,
                    low_rank=16,
                    high_rank=64,
                    loose_tolerance=1e-2,
                    tight_tolerance=1e-6,
                    bootstrap_seed=derive_seed(
                        0,
                        "realistic_transport/rank_tolerance_bootstrap/v1",
                        task,
                        metric,
                    ),
                )
            except ValueError as error:
                raise AggregateError(
                    f"incomplete rank/tolerance cells for {task}/{metric}: {error}"
                ) from error
            output.append({"task": task, "metric": metric, "estimate": estimate})
    return output


def validate_and_aggregate_profile(
    *,
    config_path: str | Path,
    profile: str,
    raw_root: str | Path,
    selection_path: str | Path | None = None,
    data_lock_path: str | Path | None = None,
    freeze_revision: str | None = None,
    selection_lock_revision: str | None = None,
    repository_root: str | Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    config = load_config(config_path, profile)
    policy = profile_policy(config, profile)
    seeds = policy.seeds
    rounds = policy.rounds
    if policy.requires_data_lock and (
        data_lock_path is None or freeze_revision is None
    ):
        raise AggregateError(
            f"profile {profile!r} requires a committed data lock and F"
        )
    if policy.requires_selection_lock and (
        selection_path is None or selection_lock_revision is None
    ):
        raise AggregateError(f"profile {profile!r} requires a selection artifact and L")
    prefixes = tuple(
        sorted(
            {
                rounds,
                *(
                    int(value)
                    for value in config["horizons"]["prefixes"]
                    if int(value) <= rounds
                ),
            }
        )
    )
    expected = {
        (task, method, seed)
        for task in EXPECTED_TASKS
        for method in EXPECTED_METHODS
        for seed in seeds
    }
    root = Path(raw_root)
    profile_root = root / profile
    actual: set[tuple[str, str, int]] = set()
    if profile_root.exists():
        for summary_path in profile_root.glob("*/*/seed-*/summary.json"):
            task = summary_path.parents[2].name
            method = summary_path.parents[1].name
            seed_text = summary_path.parent.name
            if not seed_text.startswith("seed-"):
                continue
            actual.add((task, method, int(seed_text.removeprefix("seed-"))))
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    failures = (
        sorted(profile_root.glob("*/*/seed-*/failure.json"))
        if profile_root.exists()
        else []
    )
    if missing or extra or failures:
        raise AggregateError(
            f"raw grid mismatch: missing={missing[:5]} ({len(missing)} total), "
            f"extra={extra[:5]} ({len(extra)} total), failures={len(failures)}"
        )

    expected_config_digest = config_digest(config)
    common_fields: dict[str, Any] = {}
    manifests: dict[tuple[str, str, int], Mapping[str, Any]] = {}
    raw_inventory: list[dict[str, str]] = []
    run_rows: list[dict[str, Any]] = []
    deterministic_failure_events: list[dict[str, Any]] = []
    for task, method, seed in sorted(expected):
        directory = run_directory(
            root, phase=profile, task=task, method=method, seed=seed
        )
        validated = validate_run_directory(directory)
        manifest = validated["manifest"]
        summary = validated["summary"]
        _assert_finite_json(manifest)
        _assert_finite_json(summary)
        try:
            _validate_manifest_identity(
                manifest,
                summary,
                profile=profile,
                phase=policy.phase,
                evidence_role=policy.evidence_role,
                dataset_mode=policy.dataset_mode,
                seed_set_identity=policy.seed_set_identity,
                task=task,
                method=method,
                seed=seed,
                rounds=rounds,
                expected_config_digest=expected_config_digest,
                expected_resolved_config=config,
            )
        except AggregateError as error:
            raise AggregateError(f"{error} in {directory}") from error
        try:
            _validate_paired_streams({(task, method, seed): manifest})
        except AggregateError as error:
            raise AggregateError(f"{error} in {directory}") from error
        for field in (
            "source_inventory_sha256",
            "source_inventory",
            "source_branch",
            "source_revision",
            "source_dirty",
            "scientific_config_digest",
            "resolved_config",
            "prepared_data",
            "data_authentication",
            "split",
            "preprocessing_digest",
            "preprocessing_artifact",
            "selection_artifact_sha256",
            "freeze_revision",
            "selection_lock_revision",
            "evaluation_state_revision",
            "evidence_role",
            "dataset_mode",
            "seed_set_identity",
        ):
            value = manifest.get(field)
            if field not in common_fields:
                common_fields[field] = value
            elif common_fields[field] != value:
                raise AggregateError(f"mixed {field} in {directory}")
        runtime_identity = _validated_runtime_identity(manifest, summary, config)
        if "runtime" not in common_fields:
            common_fields["runtime"] = runtime_identity
        elif common_fields["runtime"] != runtime_identity:
            raise AggregateError(f"mixed runtime environment in {directory}")
        if policy.requires_data_lock and manifest.get("source_dirty") is not False:
            raise AggregateError(
                f"Covertype run is not from a clean scientific tree: {directory}"
            )
        if manifest.get("evaluation_state_revision") != manifest.get("source_revision"):
            raise AggregateError(
                f"recorded evaluation state differs from source revision in {directory}"
            )
        manifests[(task, method, seed)] = manifest
        records = _load_rounds(directory / "rounds.jsonl", rounds)
        for record in records:
            if (
                record.get("task") != task
                or record.get("method") != method
                or int(record.get("seed", -1)) != seed
            ):
                raise AggregateError(f"run identity mismatch in {directory}")
        try:
            prepared_identity = manifest.get("prepared_data")
            if not isinstance(prepared_identity, Mapping):
                raise AggregateError("run manifest lacks prepared-data identity")
            try:
                action_count = int(prepared_identity.get("class_count", -1))
                context_dimension = int(config["preprocessing"]["projection_dimension"])
            except (TypeError, ValueError, KeyError) as error:
                raise AggregateError(
                    "run manifest has invalid feature dimensions"
                ) from error
            feature_dimension = (
                context_dimension + action_count + context_dimension * action_count
            )
            _validate_round_semantics(
                records,
                task=task,
                method=method,
                feature_dimension=feature_dimension,
                action_count=action_count,
            )
            _validate_ratio_records(
                records,
                method=method,
                rounds=rounds,
                config=config,
                action_count=action_count,
            )
        except AggregateError as error:
            raise AggregateError(f"{error} in {directory}") from error
        deterministic_failure_events.extend(
            {
                "task": task,
                "method": method,
                "seed": seed,
                "round": int(record["round"]),
                "reasons": list(record["deterministic_failure_reasons"]),
                "float64_diagnostic_pass": False,
            }
            for record in records
            if record["deterministic_failure"] is True
        )
        for name in (
            "manifest.json",
            "manifest.json.sha256",
            "rounds.jsonl",
            "rounds.jsonl.sha256",
            "summary.json",
            "summary.json.sha256",
        ):
            path = directory / name
            raw_inventory.append(
                {
                    "path": _relative(
                        path,
                        repository_root=repository_root,
                        raw_root=root,
                    ),
                    "sha256": sha256_file(path),
                }
            )
        for prefix in prefixes:
            metrics = _run_metrics(records, summary, prefix)
            run_rows.append(
                {
                    "task": task,
                    "method": method,
                    "seed": seed,
                    "prefix": prefix,
                    "confidence_role": records[prefix - 1]["confidence_role"],
                    **metrics,
                }
            )

    _validate_paired_streams(manifests)
    if common_fields.get("scientific_config_digest") != scientific_config_digest(
        config
    ):
        raise AggregateError("raw manifests use another scientific configuration")
    prepared_common = common_fields.get("prepared_data")
    if not isinstance(prepared_common, Mapping):
        raise AggregateError("raw manifests lack prepared-data metadata")
    if policy.dataset_mode == "digits_smoke":
        if prepared_common.get("smoke_only") is not True or not isinstance(
            prepared_common.get("fixture_only"), bool
        ):
            raise AggregateError("smoke evidence is not bound to a smoke-only dataset")
    elif policy.dataset_mode == "covtype":
        if (
            prepared_common.get("smoke_only") is not False
            or prepared_common.get("fixture_only") is not False
        ):
            raise AggregateError("Covertype profile contains smoke or fixture data")
    else:
        raise AggregateError(f"unknown aggregate dataset mode {policy.dataset_mode!r}")

    selection: dict[str, Any] | None = None
    data_authorized = False
    selection_authorized = False
    if policy.requires_data_lock:
        assert data_lock_path is not None and freeze_revision is not None
        if common_fields.get("freeze_revision") != freeze_revision:
            raise AggregateError("raw manifests do not bind the requested F")
        if (
            profile in {"covtype_pilot", "tuning"}
            and common_fields.get("evaluation_state_revision") != freeze_revision
        ):
            raise AggregateError(f"profile {profile!r} was not executed at F")
        authentication = common_fields.get("data_authentication")
        prepared_metadata = common_fields.get("prepared_data")
        if not isinstance(authentication, Mapping) or not isinstance(
            prepared_metadata, Mapping
        ):
            raise AggregateError("raw manifests lack data-lock authentication")
        try:
            data_lock = verify_recorded_data_authorization(
                config=config,
                config_path=config_path,
                data_lock_path=data_lock_path,
                freeze_revision=freeze_revision,
                prepared_metadata=prepared_metadata,
                authentication=authentication,
                repo_root=repository_root,
            )
        except IntegrityError as error:
            raise AggregateError(f"data-lock verification failed: {error}") from error
        expected_source_inventory = source_inventory_at_revision(
            freeze_revision, repo_root=repository_root
        )
        if common_fields.get("source_inventory") != expected_source_inventory:
            raise AggregateError("raw source inventory differs from F")
        if common_fields.get("source_inventory_sha256") != input_set_sha256(
            expected_source_inventory
        ):
            raise AggregateError("raw source-inventory hash differs from F")
        if (
            data_lock.get("split_digest") != common_fields["split"].get("digest")
            or data_lock.get("preprocessing_digest")
            != common_fields["preprocessing_digest"]
        ):
            raise AggregateError(
                "raw split/preprocessing identities differ from data lock"
            )
        data_authorized = True
    if selection_path is not None:
        if freeze_revision is None or selection_lock_revision is None:
            raise AggregateError("selection verification requires explicit F and L")
        try:
            selection, selection_digest = verify_selection_lock(
                selection_path=selection_path,
                freeze_revision=freeze_revision,
                selection_lock_revision=selection_lock_revision,
                repo_root=repository_root,
            )
        except IntegrityError as error:
            raise AggregateError(
                f"selection-lock verification failed: {error}"
            ) from error
        if common_fields.get("selection_lock_revision") != selection_lock_revision:
            raise AggregateError("raw manifests do not bind the requested L")
        try:
            validate_selection_policy(selection, config)
        except IntegrityError as error:
            raise AggregateError(f"selection policy is invalid: {error}") from error
        if selection_digest != common_fields["selection_artifact_sha256"]:
            raise AggregateError("selection artifact hash differs from raw manifests")
        if selection.get("prepared_data_digest") != common_fields["prepared_data"].get(
            "semantic_digest"
        ):
            raise AggregateError("selection and raw data identities differ")
        if (
            selection.get("preprocessing_digest")
            != common_fields["preprocessing_digest"]
        ):
            raise AggregateError("selection and raw preprocessing identities differ")
        if selection.get("scientific_config_digest") != scientific_config_digest(
            config
        ):
            raise AggregateError("selection and evaluation scientific configs differ")
        evaluation_state = common_fields.get("evaluation_state_revision")
        if not isinstance(evaluation_state, str):
            raise AggregateError("raw manifests lack evaluation state E")
        try:
            verify_evaluation_lineage(
                freeze_revision=freeze_revision,
                selection_lock_revision=selection_lock_revision,
                evaluation_state_revision=evaluation_state,
                repo_root=repository_root,
            )
        except IntegrityError as error:
            raise AggregateError(
                f"evaluation-lineage verification failed: {error}"
            ) from error
        selection_authorized = True
    deterministic_failure_count = sum(
        bool(row["deterministic_failure"])
        for row in run_rows
        if int(row["prefix"]) == rounds
    )
    prepared_metadata = common_fields.get("prepared_data")
    if not isinstance(prepared_metadata, Mapping):
        raise AggregateError("raw manifests lack prepared-data identity")
    aggregate = {
        "schema_version": 1,
        "protocol_version": config["protocol_version"],
        "profile": profile,
        "phase": policy.phase,
        "evidence_role": policy.evidence_role,
        "seed_set_identity": policy.seed_set_identity,
        "publication_evidence": publication_eligibility(
            profile=profile,
            phase=policy.phase,
            evidence_role=policy.evidence_role,
            prepared_data=prepared_metadata,
            data_authorized=data_authorized,
            selection_authorized=selection_authorized,
            deterministic_failure_count=deterministic_failure_count,
        ),
        "config_digest": expected_config_digest,
        "expected_cell_count": len(expected),
        "accepted_cell_count": len(expected),
        "rounds_per_cell": rounds,
        "prefixes": list(prefixes),
        "seeds": list(seeds),
        "tasks": list(EXPECTED_TASKS),
        "methods": list(EXPECTED_METHODS),
        "common_provenance": common_fields,
        "raw_input_inventory": sorted(raw_inventory, key=lambda item: item["path"]),
        "raw_input_inventory_sha256": input_set_sha256(raw_inventory),
        "run_level_metrics": run_rows,
        "method_statistics": _method_statistics(run_rows),
        "paired_primary_comparisons": _paired_comparisons(
            run_rows, maximum_prefix=rounds, selection=selection
        ),
        "controlled_task_secondary_comparisons": (
            _controlled_task_secondary_comparisons(
                run_rows, maximum_prefix=rounds, selection=selection
            )
        ),
        "rank_tolerance_effects": _rank_tolerance_effects(run_rows, rounds),
        "formal_p_values_reported": False,
        "verified_numerical_certificates": False,
        "semantic_status": {
            "deterministic_failure_count": deterministic_failure_count,
            "deterministic_failure_event_count": len(deterministic_failure_events),
            "deterministic_failure_events": deterministic_failure_events,
            "float64_diagnostic_failure_count": sum(
                not bool(row["float64_diagnostic_pass"])
                for row in run_rows
                if int(row["prefix"]) == rounds
            ),
            "instantaneous_theorem_event_violation_count": sum(
                int(row["instantaneous_theorem_event_violation_count"])
                for row in run_rows
                if int(row["prefix"]) == rounds
            ),
            "cumulative_theorem_event_violation_count": sum(
                int(row["cumulative_theorem_event_violation_count"])
                for row in run_rows
                if int(row["prefix"]) == rounds
            ),
        },
    }
    return aggregate


def aggregate_profile(
    *,
    config_path: str | Path,
    profile: str,
    raw_root: str | Path,
    output_path: str | Path,
    selection_path: str | Path | None = None,
    data_lock_path: str | Path | None = None,
    freeze_revision: str | None = None,
    selection_lock_revision: str | None = None,
    repository_root: str | Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    """Validate a complete raw grid and serialize its accepted aggregate."""

    _refuse_existing_outputs(output_path)
    aggregate = validate_and_aggregate_profile(
        config_path=config_path,
        profile=profile,
        raw_root=raw_root,
        selection_path=selection_path,
        data_lock_path=data_lock_path,
        freeze_revision=freeze_revision,
        selection_lock_revision=selection_lock_revision,
        repository_root=repository_root,
    )
    write_json(output_path, aggregate)
    return aggregate


def write_statistics_csv(aggregate: Mapping[str, Any], path: str | Path) -> Path:
    _refuse_existing_outputs(path)
    fields = (
        "task",
        "method",
        "prefix",
        "seed_count",
        "metric",
        "mean",
        "standard_error",
        "median",
        "q10",
        "q25",
        "q75",
        "q90",
        "iqr",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for cell in aggregate["method_statistics"]:
        for metric, values in sorted(cell["metrics"].items()):
            if values is None:
                continue
            writer.writerow(
                {
                    "task": cell["task"],
                    "method": cell["method"],
                    "prefix": cell["prefix"],
                    "seed_count": cell["seed_count"],
                    "metric": metric,
                    "mean": values["mean"],
                    "standard_error": values["standard_error"],
                    "median": values["median"],
                    "q10": values["q10"],
                    "q25": values["q25"],
                    "q75": values["q75"],
                    "q90": values["q90"],
                    "iqr": values["iqr"],
                }
            )
    destination = atomic_write_text(path, output.getvalue())
    atomic_write_text(
        destination.with_name(destination.name + ".sha256"),
        f"{sha256_file(destination)}  {destination.name}\n",
    )
    return destination


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("review/realistic_transport/AGGREGATE.json"),
    )
    parser.add_argument(
        "--statistics-csv",
        type=Path,
        default=None,
        help="defaults to STATISTICAL_RESULTS.csv beside --output",
    )
    parser.add_argument("--selection", type=Path, default=None)
    parser.add_argument("--data-lock", type=Path, default=None)
    parser.add_argument("--freeze-revision", default=None)
    parser.add_argument("--selection-lock-revision", default=None)
    args = parser.parse_args(argv)
    statistics_csv = args.statistics_csv or args.output.with_name(
        "STATISTICAL_RESULTS.csv"
    )
    _refuse_existing_outputs(args.output, statistics_csv)
    aggregate = aggregate_profile(
        config_path=args.config,
        profile=args.profile,
        raw_root=args.raw_root,
        output_path=args.output,
        selection_path=args.selection,
        data_lock_path=args.data_lock,
        freeze_revision=args.freeze_revision,
        selection_lock_revision=args.selection_lock_revision,
    )
    write_statistics_csv(aggregate, statistics_csv)
    print(
        json.dumps(
            {"aggregate": str(args.output), "cells": aggregate["accepted_cell_count"]},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
