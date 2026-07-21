"""Generate the deterministic certification ledger for primary linear policies.

The ledger separates quantities available to action selection from checks that
use the synthetic teacher after execution.  Generation is deliberately strict:
all configured evaluation policies and seeds must be present, and every claimed
post-hoc theorem event must be supported by its run summary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .config import load_config
from .run_linear_audit import (
    ACTION_COUNT,
    FEATURE_DIMENSION,
    SUPPORTED_METHODS,
    LinearAuditConfig,
)


DEFAULT_CONFIG_PATH = Path("experiments/configs/linear_audit.yaml")
DEFAULT_SELECTION_PATH = Path("results/raw/linear_audit/full/selection.json")
DEFAULT_RAW_ROOT = Path("results/raw/linear_audit/full/evaluation")
DEFAULT_AGGREGATE_PATH = Path("results/derived/linear_audit_full.json")
DEFAULT_OUTPUT_PATH = Path("results/derived/certification_audit.json")

CATEGORIES = (
    "ex_ante_theorem_certified",
    "posthoc_theorem_event_verified",
    "cg_solver_certified",
    "uncertified_diagnostic",
)
COMPARISONS = ("fixed_reference", "validation_tuned")
NUMERICAL_TOLERANCE = 1e-8
ANALYTIC_TRANSFER_METHODS = frozenset(
    {"dense_full", "cg_full", "unrescaled_window", "stale_refresh"}
)
EX_ANTE_CERTIFIED_METHODS = frozenset(
    {"dense_full", "unrescaled_window", "stale_refresh"}
)


class CertificationAuditError(ValueError):
    """Raised when inputs do not support the requested certification claim."""


def _raw_claim_disposition(method: str) -> tuple[str, str]:
    if method in EX_ANTE_CERTIFIED_METHODS:
        return (
            "independently_supported_by_analytic_audit",
            "The current audit independently establishes every action-rule schedule; "
            "it does not rely on the raw self-classification fields.",
        )
    if method == "cg_full":
        return (
            "superseded_as_insufficient",
            "The analytic transfer factor remains valid, but the floating condition "
            "estimate and energy-error audit are not verified one-sided enclosures.",
        )
    return (
        "superseded_as_insufficient",
        "The floating generalized eigenvalue factor and heuristic padding are not a "
        "verified one-sided upper enclosure.",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CertificationAuditError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CertificationAuditError(f"expected a JSON object in {path}")
    return value


def _load_single_jsonl(path: Path) -> dict[str, Any]:
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    except OSError as exc:
        raise CertificationAuditError(f"cannot read {path}: {exc}") from exc
    if len(lines) != 1:
        raise CertificationAuditError(f"expected exactly one JSONL record in {path}")
    try:
        value = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise CertificationAuditError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CertificationAuditError(f"expected a JSON object in {path}")
    return value


def _input_set(paths: Sequence[Path]) -> dict[str, Any]:
    entries = [
        {"path": _display_path(path), "sha256": _sha256(path)}
        for path in sorted(paths, key=lambda item: _display_path(item))
    ]
    payload = json.dumps(
        entries,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return {
        "file_count": len(entries),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _number(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CertificationAuditError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise CertificationAuditError(f"{name} must be finite")
    return result


def _aggregate_groups(
    aggregate: Mapping[str, Any],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    required = {
        "schema_version": 1,
        "event": "executed_policy_aggregate",
        "all_groups_complete": True,
        "all_runs_executed_policy": True,
        "all_seed_provenance_disjoint": True,
        "profiles": ["full"],
        "seed_sets": ["evaluation"],
    }
    for key, expected in required.items():
        if aggregate.get(key) != expected:
            raise CertificationAuditError(
                f"aggregate is not a strict full evaluation aggregate: {key}"
            )
    raw_groups = aggregate.get("groups")
    if not isinstance(raw_groups, Sequence) or isinstance(raw_groups, (str, bytes)):
        raise CertificationAuditError("aggregate groups must be a list")
    groups: dict[tuple[str, str], Mapping[str, Any]] = {}
    for value in raw_groups:
        if not isinstance(value, Mapping):
            raise CertificationAuditError("aggregate contains a malformed group")
        key = (str(value.get("comparison")), str(value.get("method")))
        if key in groups:
            raise CertificationAuditError(f"duplicate aggregate group {key}")
        groups[key] = value
    expected = {
        (comparison, method)
        for comparison in COMPARISONS
        for method in SUPPORTED_METHODS
    }
    if set(groups) != expected:
        raise CertificationAuditError(
            f"aggregate policy groups differ from the configured primary set: "
            f"missing={sorted(expected - set(groups))}, extra={sorted(set(groups) - expected)}"
        )
    return groups


def _operator_formula(method: str) -> str:
    formulas = {
        "dense_full": ("C_alg_t = lambda I + sigma^-2 sum_{s<t} phi_s phi_s^T"),
        "cg_full": (
            "C_alg_t = lambda I + sigma^-2 sum_{s<t} phi_s phi_s^T; "
            "C_alg_t tilde_u_t(a) = phi(x_t,a) is solved by CG"
        ),
        "diagonal": "C_alg_t = diag(C_full_t)",
        "unrescaled_window": (
            "C_alg_t = lambda I + sigma^-2 sum over the last min(t-1,W) "
            "played features phi_s phi_s^T"
        ),
        "rescaled_subsample": (
            "C_alg_t = lambda I when m_t=0; otherwise C_alg_t = lambda I + "
            "sigma^-2 ((t-1)/m_t) sum_{s in S_t} phi_s phi_s^T, "
            "m_t=min(t-1,n)"
        ),
        "lanczos_ritz": (
            "C_alg_t = lambda I + Q_t diag(max(ritz_value-lambda,0)) Q_t^T"
        ),
        "stale_refresh": (
            "C_alg_t = lambda I + sigma^-2 sum_{s<=r_t} phi_s phi_s^T, "
            "r_t=P floor((t-1)/P)"
        ),
    }
    return formulas[method]


def _transfer_input(method: str) -> dict[str, Any]:
    if method in {"dense_full", "cg_full"}:
        return {
            "formula": "u_t(a) = 1 for every action",
            "source": "C_alg_t equals C_t equals C_bar_t",
            "source_file": "experiments/run_linear_audit.py",
            "config_key": "not_applicable",
            "timing": "pre_action",
            "predictable": True,
            "used_in_action_selection": True,
            "category": "ex_ante_theorem_certified",
            "one_sided_upper_enclosure_verified": True,
            "mathematical_justification": (
                "Equal SPD matrices have equal inverse quadratic forms, so "
                "s_bar_t^2(a) = s_alg_t^2(a)."
            ),
        }
    if method in {"unrescaled_window", "stale_refresh"}:
        qualifier = (
            "the unrescaled recent subset"
            if method == "unrescaled_window"
            else "the retained history prefix in this fixed-feature linear model"
        )
        return {
            "formula": "u_t(a) = 1 for every action",
            "source": f"analytic PSD subset relation for {qualifier}",
            "source_file": "experiments/run_linear_audit.py",
            "config_key": "not_applicable",
            "timing": "pre_action",
            "predictable": True,
            "used_in_action_selection": True,
            "category": "ex_ante_theorem_certified",
            "one_sided_upper_enclosure_verified": True,
            "mathematical_justification": (
                "C_alg_t <= C_bar_t in Loewner order because omitted history terms "
                "are PSD. Inversion reverses order, hence "
                "phi^T C_bar_t^-1 phi <= phi^T C_alg_t^-1 phi. The stale argument "
                "is specific to fixed linear features and is not a certificate for "
                "a stale nonlinear Jacobian operator."
            ),
        }
    return {
        "formula": (
            "rho_plus_t = lambda_max(C_bar_t^-1/2 C_alg_t C_bar_t^-1/2); "
            "u_t(a) = max(1, rho_plus_t (1 + 32 eps_machine))"
        ),
        "source": (
            "floating generalized eigenvalue estimate of the already constructed "
            "53 by 53 matrices, with heuristic machine-epsilon padding"
        ),
        "source_file": "experiments/run_linear_audit.py",
        "config_key": "not_applicable",
        "timing": "pre_action",
        "predictable": True,
        "used_in_action_selection": True,
        "category": "uncertified_diagnostic",
        "one_sided_upper_enclosure_verified": False,
        "mathematical_justification": (
            "The recorded floating eigenvalue and fixed machine-epsilon padding "
            "are not a verified one-sided upper enclosure. The raw factor remains "
            "part of the executed action rule, but it is not a theorem certificate."
        ),
    }


def _epsilon_input(method: str, config: LinearAuditConfig) -> dict[str, Any]:
    if method != "cg_full":
        return {
            "formula": "bar_epsilon_t = 0",
            "source": "exact dense action solve; no truncated CG solve",
            "source_file": "experiments/run_linear_audit.py",
            "config_key": "not_applicable",
            "timing": "pre_action",
            "predictable": True,
            "used_in_action_selection": True,
            "category": "ex_ante_theorem_certified",
            "uniform_upper_bound_verified": True,
            "mathematical_justification": (
                "The computed inverse quadratic form is exact up to floating-point "
                "arithmetic, so the modeled relative energy error is zero."
            ),
        }
    return {
        "formula": (
            "bar_epsilon_t = epsilon_cfg when max_a epsilon_ta <= epsilon_cfg; "
            "otherwise a floating pre-action energy-error audit raises it to a "
            "roundwise padded max below 1"
        ),
        "configured_value": config.cg_tolerance,
        "source": (
            "cg.tolerance plus all-action floating 53 dimensional energy-error audit "
            "in experiments.run_linear_audit.run_method"
        ),
        "source_file": "experiments/run_linear_audit.py",
        "config_key": "cg.tolerance",
        "timing": "pre_action",
        "predictable": True,
        "used_in_action_selection": True,
        "category": "uncertified_diagnostic",
        "uniform_upper_bound_verified": False,
        "mathematical_justification": (
            "Every action was solved and floating energy errors were audited before "
            "argmax, but neither that audit nor the condition estimate is a verified "
            "one-sided enclosure. The recorded inflation is therefore preserved "
            "without a CG solver-certification claim."
        ),
    }


def _kappa_input(method: str) -> dict[str, Any]:
    cg = method == "cg_full"
    return {
        "formula": "bar_kappa_t = cond_2(C_alg_t)",
        "source": "floating pre-action numpy.linalg.cond estimate of the SPD operator",
        "source_file": "experiments/run_linear_audit.py",
        "config_key": "not_applicable",
        "logged_source": "exact_dense_pre_action_small_scale_certificate",
        "timing": "pre_action",
        "predictable": True,
        "used_in_action_selection": cg,
        "category": "uncertified_diagnostic",
        "one_sided_upper_enclosure_verified": False,
        "mathematical_justification": (
            "For CG, the estimate sets the relative-residual target, but a floating "
            "condition estimate is not a verified upper enclosure and cannot certify "
            "the energy-error implication. The raw value and source label are "
            "preserved as executed-run diagnostics."
            if cg
            else "The policy does not use this logged condition estimate in its action rule."
        ),
    }


def _certificate_inputs(
    method: str,
    config: LinearAuditConfig,
    *,
    c_bonus: float,
    c_bonus_source: str,
    c_bonus_source_file: str,
) -> dict[str, Any]:
    beta_formula = (
        "gamma_upper_t = d log(1 + (t-1) G^2/(d lambda sigma^2)); "
        "beta_base_t = sqrt(gamma_upper_t + 2 log(1/delta)) + sqrt(lambda) S; "
        "bar_beta_t = c_bonus beta_base_t"
    )
    return {
        "beta_bar_t": {
            "formula": beta_formula,
            "constants": {
                "d": FEATURE_DIMENSION,
                "G_squared": 3.0,
                "sigma": config.noise_std,
                "delta": config.delta,
                "S": config.theta_bound,
                "lambda": config.ridge,
            },
            "source": (
                "experiments.run_linear_audit.confidence_radius followed by the "
                "configured bonus_scale multiplication"
            ),
            "source_file": "experiments/run_linear_audit.py",
            "config_key": "confidence.delta",
            "additional_config_keys": [
                "ridge",
                "environment.noise_std",
                "confidence.theta_bound",
            ],
            "logged_field": "beta_t",
            "timing": "pre_action",
            "predictable": True,
            "used_in_action_selection": True,
            "category": "ex_ante_theorem_certified",
            "mathematical_justification": (
                "The deterministic trace/log-determinant upper bound dominates the "
                "self-normalized information term. S is a declared parameter-norm "
                "bound, and c_bonus >= 1 preserves the upper-bound property."
            ),
        },
        "c_bonus": {
            "formula": "bar_beta_t = c_bonus beta_base_t",
            "value": c_bonus,
            "source": c_bonus_source,
            "source_file": c_bonus_source_file,
            "config_key": "bonus_scale",
            "timing": "fixed_before_evaluation",
            "predictable": True,
            "used_in_action_selection": True,
            "category": "ex_ante_theorem_certified",
            "mathematical_justification": (
                "The value is at least one. Fixed-reference uses the declared base "
                "value; validation-tuned uses only disjoint tuning seeds and is fixed "
                "before any evaluation trajectory."
            ),
        },
        "psi_bar_t": {
            "formula": "bar_psi_t = 0",
            "source": "analytic fixed-feature linear model with an exact ridge center",
            "source_file": "experiments/run_linear_audit.py",
            "config_key": "not_applicable",
            "timing": "pre_action",
            "predictable": True,
            "used_in_action_selection": True,
            "category": "ex_ante_theorem_certified",
            "mathematical_justification": (
                "There is no feature drift or nonlinear Taylor remainder and the "
                "ridge normal equation is solved exactly, so the centering discrepancy "
                "certificate vanishes."
            ),
        },
        "u_t(a)": _transfer_input(method),
        "epsilon_bar_t": _epsilon_input(method, config),
        "kappa_bar_t": _kappa_input(method),
    }


def _final_metrics(group: Mapping[str, Any]) -> Mapping[str, Any]:
    horizons = group.get("horizons")
    if (
        not isinstance(horizons, Sequence)
        or isinstance(horizons, (str, bytes))
        or not horizons
    ):
        raise CertificationAuditError("aggregate group has no horizon metrics")
    valid = [value for value in horizons if isinstance(value, Mapping)]
    if not valid:
        raise CertificationAuditError("aggregate group has malformed horizons")
    final = max(valid, key=lambda value: int(value.get("horizon", 0)))
    metrics = final.get("metrics")
    if not isinstance(metrics, Mapping):
        raise CertificationAuditError("aggregate final horizon has no metrics")
    return metrics


def _metric_mean(metrics: Mapping[str, Any], name: str) -> float:
    value = metrics.get(name)
    if not isinstance(value, Mapping):
        raise CertificationAuditError(f"aggregate is missing metric {name}")
    return _number(value.get("mean"), name=f"aggregate metric {name}.mean")


def _summary_evidence(
    summaries: Sequence[Mapping[str, Any]],
    *,
    expected_method: str,
    expected_seeds: Sequence[int],
) -> dict[str, Any]:
    if len(summaries) != len(expected_seeds):
        raise CertificationAuditError(
            f"{expected_method} has {len(summaries)} summaries, expected {len(expected_seeds)}"
        )
    seeds = tuple(int(value.get("seed", -1)) for value in summaries)
    if seeds != tuple(expected_seeds):
        raise CertificationAuditError(
            f"{expected_method} summary seeds differ from the declared evaluation seeds"
        )
    required_true = (
        "executed_policy",
        "policy_used_predictable_valid_certificates",
        "confidence_event_realized",
        "certified_execution",
        "C_equals_Cbar_all_rounds",
    )
    for summary in summaries:
        if summary.get("method") != expected_method:
            raise CertificationAuditError(
                "summary method disagrees with its policy directory"
            )
        for field in required_true:
            if summary.get(field) is not True:
                raise CertificationAuditError(
                    f"summary seed {summary.get('seed')} does not verify {field}"
                )
    minima = {
        field: min(_number(value.get(field), name=field) for value in summaries)
        for field in (
            "theorem_bound_slack",
            "dynamic_bound_slack",
            "width_information_slack",
            "width_dynamic_slack",
            "transfer_slack_min",
            "bonus_lower_slack_min",
            "bonus_upper_slack_min",
            "cg_sandwich_lower_slack_min",
            "cg_sandwich_upper_slack_min",
        )
    }
    for field, value in minima.items():
        if value < -NUMERICAL_TOLERANCE:
            raise CertificationAuditError(
                f"post-hoc inequality {field} failed: {value}"
            )
    max_identity_residual = max(
        abs(
            _number(
                value.get("dynamic_identity_residual"), name="dynamic_identity_residual"
            )
        )
        for value in summaries
    )
    if max_identity_residual > NUMERICAL_TOLERANCE:
        raise CertificationAuditError(
            f"dynamic identity residual exceeds tolerance: {max_identity_residual}"
        )
    raw_certificate_modes = [value.get("certificate_mode") for value in summaries]
    if not raw_certificate_modes or not all(
        isinstance(value, str) for value in raw_certificate_modes
    ):
        raise CertificationAuditError(
            f"{expected_method} summaries have malformed certificate_mode fields"
        )
    certificate_modes = sorted(set(raw_certificate_modes))
    raw_claim_disposition, raw_claim_reason = _raw_claim_disposition(expected_method)
    return {
        "run_count": len(summaries),
        "seeds": list(seeds),
        "all_executed_policy": True,
        "all_raw_summaries_report_predictable_certificate_flag": True,
        "all_confidence_events_realized": True,
        "all_raw_summaries_report_certified_execution": True,
        "all_C_equals_C_bar": True,
        "raw_summary_certification_claims": {
            "reported_values": {
                "policy_used_predictable_valid_certificates": True,
                "certified_execution": True,
                "certificate_mode": certificate_modes,
            },
            "audit_disposition": raw_claim_disposition,
            "audit_reason": raw_claim_reason,
            "raw_files_rewritten": False,
        },
        "minimum_slacks": minima,
        "maximum_absolute_dynamic_identity_residual": max_identity_residual,
        "numerical_tolerance": NUMERICAL_TOLERANCE,
        "interpretation": (
            "These are numerical checks and preserved raw summary flags. They do not "
            "supply a missing verified one-sided floating-point enclosure and do not "
            "override the policy-level certification categories."
        ),
    }


def _policy_record(
    *,
    comparison: str,
    method: str,
    base_config: Mapping[str, Any],
    selection: Mapping[str, Any],
    group: Mapping[str, Any],
    raw_root: Path,
    evaluation_seeds: Sequence[int],
    selection_sha256: str,
) -> tuple[dict[str, Any], list[Path], list[Path]]:
    hyperparameters = group.get("hyperparameters")
    if not isinstance(hyperparameters, Mapping):
        raise CertificationAuditError(
            f"aggregate group {comparison}/{method} has no hyperparameters"
        )
    ridge = _number(hyperparameters.get("ridge"), name="ridge")
    c_bonus = _number(hyperparameters.get("bonus_scale"), name="bonus_scale")
    if c_bonus < 1.0:
        raise CertificationAuditError("c_bonus must be at least one")

    selected = selection.get("selected")
    selected_method = selected.get(method) if isinstance(selected, Mapping) else None
    if comparison == "validation_tuned":
        if not isinstance(selected_method, Mapping):
            raise CertificationAuditError(f"selection has no winner for {method}")
        selected_hyperparameters = selected_method.get("hyperparameters")
        if not isinstance(selected_hyperparameters, Mapping) or dict(
            selected_hyperparameters
        ) != dict(hyperparameters):
            raise CertificationAuditError(
                f"aggregate hyperparameters disagree with selection for {method}"
            )
        c_bonus_source = (
            f"results/raw/linear_audit/full/selection.json winner "
            f"{selected_method.get('candidate_id')} selected on tuning seeds only"
        )
        c_bonus_source_file = "experiments/run_linear_study.py"
    else:
        base_confidence = base_config.get("confidence")
        base_scale = (
            base_confidence.get("bonus_scale", 1.0)
            if isinstance(base_confidence, Mapping)
            else 1.0
        )
        expected = _number(
            base_config.get("bonus_scale", base_scale), name="base bonus_scale"
        )
        expected_ridge = _number(base_config.get("ridge"), name="base ridge")
        if c_bonus != expected or ridge != expected_ridge:
            raise CertificationAuditError(
                f"fixed-reference hyperparameters changed for {method}"
            )
        c_bonus_source = "fixed full-profile base configuration"
        c_bonus_source_file = "experiments/configs/linear_audit.yaml"

    policy_config = dict(base_config)
    policy_config["ridge"] = ridge
    policy_config["bonus_scale"] = c_bonus
    parsed_config = LinearAuditConfig.from_mapping(policy_config)
    summaries: list[dict[str, Any]] = []
    manifest_paths: list[Path] = []
    summary_paths: list[Path] = []
    for seed in evaluation_seeds:
        directory = raw_root / comparison / method / f"seed-{seed}"
        manifest_path = directory / "manifest.jsonl"
        summary_path = directory / "summary.jsonl"
        manifest = _load_single_jsonl(manifest_path)
        summary = _load_single_jsonl(summary_path)
        manifest_config = manifest.get("config")
        if not isinstance(manifest_config, Mapping):
            raise CertificationAuditError(f"manifest has no config: {manifest_path}")
        study = manifest_config.get("study")
        execution = manifest_config.get("execution")
        if (
            manifest.get("seed") != seed
            or not isinstance(study, Mapping)
            or study.get("phase") != "evaluation"
            or study.get("comparison") != comparison
            or study.get("selection_sha256") != selection_sha256
            or not isinstance(execution, Mapping)
            or execution.get("method") != method
            or execution.get("executed_policy") is not True
        ):
            raise CertificationAuditError(
                f"manifest provenance mismatch: {manifest_path}"
            )
        manifest_hyperparameters = study.get("hyperparameters")
        if not isinstance(manifest_hyperparameters, Mapping) or dict(
            manifest_hyperparameters
        ) != dict(hyperparameters):
            raise CertificationAuditError(
                f"manifest hyperparameters mismatch: {manifest_path}"
            )
        confidence = manifest_config.get("confidence")
        confidence_scale = (
            confidence.get("bonus_scale") if isinstance(confidence, Mapping) else None
        )
        if (
            _number(manifest_config.get("ridge"), name="manifest ridge") != ridge
            or _number(manifest_config.get("bonus_scale"), name="manifest bonus_scale")
            != c_bonus
            or _number(confidence_scale, name="manifest confidence.bonus_scale")
            != c_bonus
        ):
            raise CertificationAuditError(
                f"manifest policy constants mismatch: {manifest_path}"
            )
        summaries.append(summary)
        manifest_paths.append(manifest_path)
        summary_paths.append(summary_path)

    evidence = _summary_evidence(
        summaries, expected_method=method, expected_seeds=evaluation_seeds
    )
    if int(group.get("run_count", -1)) != len(evaluation_seeds):
        raise CertificationAuditError(
            f"aggregate group run count mismatch for {comparison}/{method}"
        )
    if list(group.get("seeds", [])) != list(evaluation_seeds):
        raise CertificationAuditError(
            f"aggregate group seeds mismatch for {comparison}/{method}"
        )
    final_metrics = _final_metrics(group)
    evidence["aggregate_final_horizon_means"] = {
        "beta_t": _metric_mean(final_metrics, "beta_t"),
        "bar_psi_t": _metric_mean(final_metrics, "bar_psi_t"),
        "u_t": _metric_mean(final_metrics, "u_t"),
        "cg_certified_epsilon": _metric_mean(final_metrics, "cg_certified_epsilon"),
        "cg_energy_error_max": _metric_mean(final_metrics, "cg_energy_error_max"),
        "kappa_bar_t": _metric_mean(final_metrics, "kappa_bar_t"),
        "theorem_bound_slack": _metric_mean(final_metrics, "theorem_bound_slack"),
    }

    ex_ante_certified = method in EX_ANTE_CERTIFIED_METHODS
    certification_category = (
        "ex_ante_theorem_certified"
        if ex_ante_certified
        else "posthoc_theorem_event_verified"
    )
    categories = {
        "ex_ante_theorem_certified": ex_ante_certified,
        "posthoc_theorem_event_verified": True,
        "cg_solver_certified": False,
        "uncertified_diagnostic": not ex_ante_certified,
    }
    if tuple(categories) != CATEGORIES:
        raise AssertionError("category order/vocabulary drifted")
    schedules = _certificate_inputs(
        method,
        parsed_config,
        c_bonus=c_bonus,
        c_bonus_source=c_bonus_source,
        c_bonus_source_file=c_bonus_source_file,
    )
    exact_bonus_formula = (
        "w_t(a)=(bar_beta_t+bar_psi_t) "
        "sqrt(u_t(a)/(1-bar_epsilon_t)) sqrt(tilde_s_t^2(a))"
    )
    solve_definition = (
        "tilde_u_t(a) is the recorded truncated CG iterate for C_alg_t u=phi(x_t,a)"
        if method == "cg_full"
        else "tilde_u_t(a)=C_alg_t^-1 phi(x_t,a)"
    )
    record = {
        "policy_id": f"{comparison}/{method}",
        "policy_name": f"{comparison}/{method}",
        "comparison": comparison,
        "method": method,
        "hyperparameters": {"lambda": ridge, "c_bonus": c_bonus},
        "operator_formula": _operator_formula(method),
        "exact_bonus_formula": exact_bonus_formula,
        "action_selection": {
            "formula": (
                "tilde_s_t^2(a)=phi(x_t,a)^T tilde_u_t(a); "
                f"{solve_definition}; {exact_bonus_formula}; "
                "a_t=first argmax_a [phi(x_t,a)^T theta_hat_t+w_t(a)]"
            ),
            "solve_definition": solve_definition,
            "actions": list(range(ACTION_COUNT)),
            "tie_break": "numpy.argmax chooses the lowest action index among exact ties",
            "teacher_used": False,
            "all_actions_scored_before_selection": True,
        },
        "policy_available_schedules": schedules,
        "certification_category": certification_category,
        "categories": categories,
        "posthoc_theorem_event_evidence": evidence,
        "posthoc_fields": [
            {
                "fields": [
                    "confidence_ratio_max",
                    "confidence_radius_valid_on_path",
                    "optimism_violations",
                    "theorem_bound_slack",
                ],
                "timing": "post_action_or_end_of_run",
                "used_in_action_selection": False,
                "category": "posthoc_theorem_event_verified",
                "justification": (
                    "These fields numerically check that the recorded realized "
                    "confidence event and inequalities held. They neither make the "
                    "event predictable nor repair a missing one-sided enclosure."
                ),
            },
            {
                "fields": ["true_means", "optimal_action", "pseudo_regret"],
                "timing": "post_action",
                "used_in_action_selection": False,
                "category": "uncertified_diagnostic",
                "justification": (
                    "They use the synthetic teacher only to evaluate the executed "
                    "policy and carry no certification role in action selection."
                ),
            },
        ],
    }
    return record, manifest_paths, summary_paths


def generate(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    selection_path: str | Path = DEFAULT_SELECTION_PATH,
    raw_root: str | Path = DEFAULT_RAW_ROOT,
    aggregate_path: str | Path = DEFAULT_AGGREGATE_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
) -> dict[str, Any]:
    """Validate full linear artifacts and write a deterministic audit ledger."""

    config_path = Path(config_path)
    selection_path = Path(selection_path)
    raw_root = Path(raw_root)
    aggregate_path = Path(aggregate_path)
    output_path = Path(output_path)
    config = load_config(config_path, profile="full")
    methods = tuple(str(value) for value in config.get("methods", ()))
    comparisons = tuple(str(value) for value in config.get("comparisons", ()))
    if methods != SUPPORTED_METHODS:
        raise CertificationAuditError(
            "full config methods are not the primary method set"
        )
    if comparisons != COMPARISONS:
        raise CertificationAuditError(
            "full config comparisons are not the primary comparison set"
        )
    seed_sets = config.get("seed_sets")
    if not isinstance(seed_sets, Mapping):
        raise CertificationAuditError("full config has no seed sets")
    tuning_seeds = tuple(int(value) for value in seed_sets.get("tuning", ()))
    evaluation_seeds = tuple(int(value) for value in seed_sets.get("evaluation", ()))
    if (
        not tuning_seeds
        or not evaluation_seeds
        or set(tuning_seeds) & set(evaluation_seeds)
    ):
        raise CertificationAuditError(
            "tuning and evaluation seeds must be nonempty and disjoint"
        )

    selection = _load_object(selection_path)
    if (
        selection.get("event") != "linear_study_selection"
        or selection.get("profile") != "full"
        or selection.get("seed_sets_disjoint") is not True
        or tuple(selection.get("tuning_seed_set", ())) != tuning_seeds
        or tuple(selection.get("evaluation_seed_set", ())) != evaluation_seeds
    ):
        raise CertificationAuditError(
            "selection provenance disagrees with the full config"
        )
    selection_sha256 = _sha256(selection_path)
    aggregate = _load_object(aggregate_path)
    groups = _aggregate_groups(aggregate)
    expected_run_count = (
        len(COMPARISONS) * len(SUPPORTED_METHODS) * len(evaluation_seeds)
    )
    if int(aggregate.get("run_count", -1)) != expected_run_count:
        raise CertificationAuditError(
            "aggregate run count differs from the primary policy design"
        )

    policies: list[dict[str, Any]] = []
    manifest_paths: list[Path] = []
    summary_paths: list[Path] = []
    for comparison in COMPARISONS:
        for method in SUPPORTED_METHODS:
            record, manifests, summaries = _policy_record(
                comparison=comparison,
                method=method,
                base_config=config,
                selection=selection,
                group=groups[(comparison, method)],
                raw_root=raw_root,
                evaluation_seeds=evaluation_seeds,
                selection_sha256=selection_sha256,
            )
            policies.append(record)
            manifest_paths.extend(manifests)
            summary_paths.extend(summaries)

    source_root = Path(__file__).resolve().parent
    runner_path = source_root / "run_linear_audit.py"
    study_path = source_root / "run_linear_study.py"
    generator_path = Path(__file__).resolve()
    result = {
        "schema_version": 1,
        "event": "linear_policy_certification_audit",
        "scope": {
            "profile": "full",
            "phase": "evaluation",
            "methods": list(SUPPORTED_METHODS),
            "comparisons": list(COMPARISONS),
            "primary_policy_count": len(policies),
            "evaluation_run_count": expected_run_count,
            "tuning_seeds": list(tuning_seeds),
            "evaluation_seeds": list(evaluation_seeds),
            "seed_sets_disjoint": True,
        },
        "category_definitions": {
            "ex_ante_theorem_certified": (
                "The executed action rule used only predictable pre-action quantities "
                "that satisfy the conditional theorem assumptions."
            ),
            "posthoc_theorem_event_verified": (
                "Teacher-aware numerical checks made after execution verify the "
                "recorded realized confidence event and inequalities on every "
                "evaluation run; they do not create ex-ante certification."
            ),
            "cg_solver_certified": (
                "The approximate CG widths used a pre-action uniform energy-error "
                "certificate and the corresponding bonus inflation."
            ),
            "uncertified_diagnostic": (
                "A recorded quantity has no theorem-certification status; this includes "
                "evaluation-only fields and action-rule factors lacking a verified "
                "one-sided enclosure."
            ),
        },
        "c_bonus_beta_relationship": {
            "exact_formula": "bar_beta_t = c_bonus * beta_base_t",
            "beta_base_formula": (
                "sqrt(d log(1+(t-1)G^2/(d lambda sigma^2)) + "
                "2 log(1/delta)) + sqrt(lambda) S"
            ),
            "logged_beta_t_means": "bar_beta_t, after multiplication by c_bonus",
            "action_bonus_formula": (
                "w_t(a)=(bar_beta_t+bar_psi_t) sqrt(u_t(a)/(1-bar_epsilon_t)) "
                "sqrt(tilde_s_t^2(a))"
            ),
            "interpretation": (
                "c_bonus multiplies the entire base confidence radius, including the "
                "sqrt(lambda) S term. It does not separately multiply u_t, the CG "
                "inflation, or a nonzero centering certificate. In this linear audit "
                "bar_psi_t is exactly zero."
            ),
        },
        "policies": policies,
        "provenance": {
            "config": {
                "path": _display_path(config_path),
                "sha256": _sha256(config_path),
            },
            "selection": {
                "path": _display_path(selection_path),
                "sha256": selection_sha256,
            },
            "aggregate": {
                "path": _display_path(aggregate_path),
                "sha256": _sha256(aggregate_path),
                "raw_input_set_sha256": aggregate.get("input_set_sha256"),
            },
            "evaluation_manifests": _input_set(manifest_paths),
            "evaluation_summaries": _input_set(summary_paths),
            "implementation": [
                {"path": _display_path(path), "sha256": _sha256(path)}
                for path in (runner_path, study_path, generator_path)
            ],
        },
    }
    if tuple(result["category_definitions"]) != CATEGORIES:
        raise AssertionError("certification category vocabulary drifted")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        + "\n",
        encoding="ascii",
    )
    sidecar_path = output_path.with_suffix(output_path.suffix + ".provenance.json")
    sidecar = {
        "schema_version": 1,
        "event": "linear_policy_certification_audit_provenance",
        "artifact": _display_path(output_path),
        "artifact_sha256": _sha256(output_path),
        "generator": result["provenance"]["implementation"][-1],
        "inputs": {
            key: value
            for key, value in result["provenance"].items()
            if key != "implementation"
        },
        "primary_policy_count": len(policies),
        "evaluation_run_count": expected_run_count,
        "category_vocabulary": list(CATEGORIES),
    }
    sidecar_path.write_text(
        json.dumps(
            sidecar, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False
        )
        + "\n",
        encoding="ascii",
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION_PATH)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--aggregate", type=Path, default=DEFAULT_AGGREGATE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args(argv)
    result = generate(
        args.config,
        args.selection,
        args.raw_root,
        args.aggregate,
        args.output,
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "provenance": str(
                    args.output.with_suffix(args.output.suffix + ".provenance.json")
                ),
                "primary_policy_count": result["scope"]["primary_policy_count"],
                "evaluation_run_count": result["scope"]["evaluation_run_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ANALYTIC_TRANSFER_METHODS",
    "CATEGORIES",
    "CertificationAuditError",
    "EX_ANTE_CERTIFIED_METHODS",
    "generate",
]
