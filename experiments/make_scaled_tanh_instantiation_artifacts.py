"""Build provenance-bound artifacts for the scaled-tanh instantiation study."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import NDArray

from .artifact_utils import (
    input_set_sha256,
    sha256_file,
    validate_sha256_sidecar,
    write_json_artifact,
    write_sha256_sidecar,
)
from .config import config_digest, get_seed_set, load_config
from .logging_utils import canonical_json, derive_seed
from .run_scaled_tanh_instantiation import (
    THEOREM_METHODS,
    Cell,
    cells,
    load_optimizer_selection,
    make_environment,
    make_stream,
    optimizer_selection_cells,
    validate_config,
)


FloatArray = NDArray[np.float64]

METHOD_LABELS = {
    "exact_current_relative": "Exact relative",
    "full_cg_relative": "Full CG relative",
    "current_welford": "Current Welford",
    "corrected_current": "Corrected current",
    "frozen_neuralucb": "Frozen NeuralUCB",
    "diagonal_current": "Diagonal current",
    "frozen_linear_ucb": "Frozen linear UCB",
    "greedy": "Greedy",
}
METHOD_COLORS = {
    "exact_current_relative": "#111111",
    "full_cg_relative": "#2474B5",
    "current_welford": "#D9822B",
    "corrected_current": "#2E8B57",
    "frozen_neuralucb": "#6B4C9A",
    "diagonal_current": "#C44E52",
    "frozen_linear_ucb": "#00A6A6",
    "greedy": "#777777",
}

ONE_DIMENSIONAL_ARRAYS = {
    "cumulative_pseudo_regret",
    "theorem_rhs",
    "rhs_per_round",
    "rhs_regret_ratio",
    "exact_chi_t",
    "old_chi_bar_t",
    "exact_rho_t",
    "analytic_rho_W",
    "exact_psi_t",
    "relative_psi_bar_t",
    "old_psi_bar_t",
    "exact_linearization_error",
    "linearization_bound",
    "gamma",
    "Gamma_tail",
    "Gamma_split",
    "optimizer_residual",
    "optimizer_iterations",
    "optimizer_pass",
    "confidence_event",
    "optimism_event",
    "transfer_pass",
    "centering_pass",
    "linearization_pass",
    "information_pass",
    "endpoint_information_pass",
    "old_transfer_pass",
    "old_centering_pass",
    "regret_bound_pass",
    "path_Q_t",
    "residual_energy_prefix",
    "residual_energy_envelope",
    "residual_envelope_pass",
    "residual_energy_through_round",
    "residual_envelope_through_round",
    "residual_endpoint_pass",
    "exact_E_prefix",
    "predictable_E_prefix",
    "exact_E_through_round",
    "predictable_E_through_round",
    "exact_F_prefix",
    "predictable_F_prefix",
    "exact_F_next",
    "predictable_F_next",
    "gamma_endpoint",
    "Gamma_tail_endpoint",
    "Gamma_split_endpoint",
    "rhs_information_term",
    "rhs_factor_sum",
    "rhs_width_potential",
    "rhs_statistical_component",
    "rhs_linearization_component",
    "premise_pass",
    "selected_actions",
    "cumulative_sample_cvps",
}
ACTION_ARRAYS = {
    "dense_width_squared",
    "computed_width_squared",
    "cg_iterations",
    "cg_relative_residual",
    "cg_energy_error",
    "cg_converged",
}
BOOLEAN_ARRAYS = {
    "optimizer_pass",
    "confidence_event",
    "optimism_event",
    "transfer_pass",
    "centering_pass",
    "linearization_pass",
    "information_pass",
    "endpoint_information_pass",
    "old_transfer_pass",
    "old_centering_pass",
    "regret_bound_pass",
    "residual_envelope_pass",
    "residual_endpoint_pass",
    "premise_pass",
    "cg_converged",
}
INTEGER_ARRAYS = {
    "optimizer_iterations",
    "selected_actions",
    "cumulative_sample_cvps",
    "cg_iterations",
}
BOUND_ARRAYS = {
    "theorem_rhs",
    "rhs_per_round",
    "rhs_regret_ratio",
    "rhs_factor_sum",
    "rhs_width_potential",
    "rhs_statistical_component",
    "rhs_linearization_component",
}


class ScaledTanhArtifactError(ValueError):
    """Raised when a raw record is incomplete or inconsistent."""


def _runner_source_sha256() -> str:
    source = Path(__file__).with_name("run_scaled_tanh_instantiation.py")
    if not source.is_file():
        raise ScaledTanhArtifactError(f"missing packaged runner source {source}")
    return sha256_file(source)


def _run_directory(
    root: Path, profile: str, cell: Cell, method: str, seed: int
) -> Path:
    return root / profile / "evaluation" / cell.token / method / f"seed-{seed}"


def _expected_cell(cell: Cell) -> dict[str, float | int]:
    return {
        "horizon": cell.horizon,
        "width_ratio": cell.width_ratio,
        "width": cell.width,
        "residual_factor": cell.residual_factor,
    }


def _validate_record(path: Path) -> None:
    if not path.is_file():
        raise ScaledTanhArtifactError(f"missing raw record {path}")
    try:
        validate_sha256_sidecar(path)
    except (OSError, ValueError) as error:
        raise ScaledTanhArtifactError(
            f"invalid SHA-256 sidecar for {path}: {error}"
        ) from error


def _load_json(path: Path) -> dict[str, Any]:
    _validate_record(path)
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (OSError, json.JSONDecodeError) as error:
        raise ScaledTanhArtifactError(f"cannot parse {path}: {error}") from error
    if not isinstance(value, dict):
        raise ScaledTanhArtifactError(f"{path} is not a JSON object")
    return value


def _record_inputs(paths: Sequence[Path]) -> list[dict[str, str]]:
    result = []
    for path in paths:
        sidecar = path.with_name(path.name + ".sha256")
        result.extend(
            (
                {"path": path.as_posix(), "sha256": sha256_file(path)},
                {"path": sidecar.as_posix(), "sha256": sha256_file(sidecar)},
            )
        )
    return result


def _close(left: Any, right: float, *, tolerance: float = 1e-11) -> bool:
    return isinstance(left, (int, float)) and bool(
        np.isclose(float(left), right, rtol=tolerance, atol=tolerance)
    )


def _validate_arrays(
    arrays: Mapping[str, NDArray[np.generic]],
    *,
    directory: Path,
    cell: Cell,
    action_count: int,
    method: str,
) -> None:
    expected = ONE_DIMENSIONAL_ARRAYS | ACTION_ARRAYS
    if set(arrays) != expected:
        missing = sorted(expected - set(arrays))
        extra = sorted(set(arrays) - expected)
        raise ScaledTanhArtifactError(
            f"array schema mismatch in {directory}: missing={missing}, extra={extra}"
        )
    if any(arrays[name].shape != (cell.horizon,) for name in ONE_DIMENSIONAL_ARRAYS):
        raise ScaledTanhArtifactError(f"round coverage is invalid in {directory}")
    if any(
        arrays[name].shape != (cell.horizon, action_count) for name in ACTION_ARRAYS
    ):
        raise ScaledTanhArtifactError(f"action coverage is invalid in {directory}")
    if any(arrays[name].dtype != np.dtype(np.bool_) for name in BOOLEAN_ARRAYS):
        raise ScaledTanhArtifactError(f"boolean array dtype is invalid in {directory}")
    if any(
        not np.issubdtype(arrays[name].dtype, np.integer) for name in INTEGER_ARRAYS
    ):
        raise ScaledTanhArtifactError(f"integer array dtype is invalid in {directory}")

    for name, values in arrays.items():
        if name in BOOLEAN_ARRAYS:
            continue
        if name in BOUND_ARRAYS:
            if np.any(np.isinf(values)):
                raise ScaledTanhArtifactError(f"infinite {name} values in {directory}")
            continue
        if not np.all(np.isfinite(values)):
            raise ScaledTanhArtifactError(f"nonfinite {name} values in {directory}")

    if method in THEOREM_METHODS:
        finite_bound_arrays = BOUND_ARRAYS - {"rhs_regret_ratio"}
        if any(not np.all(np.isfinite(arrays[name])) for name in finite_bound_arrays):
            raise ScaledTanhArtifactError(
                f"theorem method has undefined bound values in {directory}"
            )
    elif any(not np.all(np.isnan(arrays[name])) for name in BOUND_ARRAYS):
        raise ScaledTanhArtifactError(
            f"control method unexpectedly records theorem bounds in {directory}"
        )
    if np.any(np.diff(arrays["cumulative_pseudo_regret"]) < -1e-11):
        raise ScaledTanhArtifactError(f"regret is not cumulative in {directory}")
    selected = arrays["selected_actions"]
    if np.any(selected < 0) or np.any(selected >= action_count):
        raise ScaledTanhArtifactError(f"selected action is out of range in {directory}")

    tolerance = 2e-9
    if not (
        np.all(arrays["gamma"] <= arrays["Gamma_split"] + tolerance)
        and np.all(arrays["Gamma_split"] <= arrays["Gamma_tail"] + tolerance)
        and np.all(
            arrays["gamma_endpoint"] <= arrays["Gamma_split_endpoint"] + tolerance
        )
        and np.all(
            arrays["Gamma_split_endpoint"] <= arrays["Gamma_tail_endpoint"] + tolerance
        )
    ):
        raise ScaledTanhArtifactError(
            f"information certificate is invalid in {directory}"
        )
    if not (
        np.all(arrays["exact_E_prefix"] <= arrays["predictable_E_prefix"] + tolerance)
        and np.all(
            arrays["exact_E_through_round"]
            <= arrays["predictable_E_through_round"] + tolerance
        )
        and np.all(
            arrays["exact_F_prefix"] <= arrays["predictable_F_prefix"] + tolerance
        )
        and np.all(arrays["exact_F_next"] <= arrays["predictable_F_next"] + tolerance)
        and np.all(
            arrays["residual_energy_prefix"]
            <= arrays["residual_energy_envelope"] + tolerance
        )
        and np.all(
            arrays["residual_energy_through_round"]
            <= arrays["residual_envelope_through_round"] + tolerance
        )
    ):
        raise ScaledTanhArtifactError(f"predictable envelope is invalid in {directory}")
    prefix_endpoint_pairs = (
        ("gamma", "gamma_endpoint"),
        ("Gamma_tail", "Gamma_tail_endpoint"),
        ("Gamma_split", "Gamma_split_endpoint"),
        ("exact_E_prefix", "exact_E_through_round"),
        ("predictable_E_prefix", "predictable_E_through_round"),
        ("exact_F_prefix", "exact_F_next"),
        ("predictable_F_prefix", "predictable_F_next"),
    )
    if cell.horizon > 1 and any(
        not np.allclose(
            arrays[prefix][1:], arrays[endpoint][:-1], rtol=0.0, atol=tolerance
        )
        for prefix, endpoint in prefix_endpoint_pairs
    ):
        raise ScaledTanhArtifactError(
            f"prefix/endpoint indexing is invalid in {directory}"
        )
    if method in THEOREM_METHODS and not np.allclose(
        arrays["theorem_rhs"],
        arrays["rhs_statistical_component"] + arrays["rhs_linearization_component"],
        rtol=1e-11,
        atol=1e-11,
    ):
        raise ScaledTanhArtifactError(f"RHS decomposition is invalid in {directory}")


def _load_run(
    directory: Path,
    *,
    config: Mapping[str, Any],
    profile: str,
    seed: int,
    cell: Cell,
    method: str,
    environment_sha256: str,
    environment_minimum_gap: float,
    stream_sha256: str,
    optimizer_selection_sha256: str,
    runner_source_sha256: str,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, NDArray[np.generic]],
    list[dict[str, str]],
]:
    manifest_path = directory / "manifest.json"
    summary_path = directory / "summary.json"
    rounds_path = directory / "rounds.npz"
    manifest = _load_json(manifest_path)
    summary = _load_json(summary_path)
    _validate_record(rounds_path)
    expected_cell = _expected_cell(cell)
    expected_manifest = {
        "schema_version": 1,
        "experiment": "scaled_tanh_instantiation",
        "profile": profile,
        "phase": "evaluation",
        "seed": seed,
        "method": method,
        "cell": expected_cell,
        "config": dict(config),
        "config_digest": config_digest(config),
        "environment_sha256": environment_sha256,
        "stream_sha256": stream_sha256,
        "rng": config["rng"],
        "selection_protocol": config["selection_protocol"],
        "optimizer_selection_sha256": optimizer_selection_sha256,
        "evaluation_data_used_for_selection": False,
    }
    for key, expected in expected_manifest.items():
        if manifest.get(key) != expected:
            raise ScaledTanhArtifactError(
                f"manifest identity mismatch for {directory}: {key}"
            )
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        raise ScaledTanhArtifactError(f"manifest provenance is invalid in {directory}")
    if provenance.get("source_artifact_hashes") != {
        "experiments/run_scaled_tanh_instantiation.py": runner_source_sha256
    }:
        raise ScaledTanhArtifactError(
            f"manifest runner source hash is invalid in {directory}"
        )
    if manifest.get("rounds_sha256") != sha256_file(rounds_path):
        raise ScaledTanhArtifactError(f"round archive hash mismatch in {directory}")
    if manifest.get("summary_sha256") != sha256_file(summary_path):
        raise ScaledTanhArtifactError(f"summary hash mismatch in {directory}")

    expected_summary = {
        "schema_version": 1,
        "experiment": "scaled_tanh_instantiation",
        "method": method,
        "cell": expected_cell,
        "dimension": int(config["dimension"]),
        "effective_rank": int(config["effective_rank"]),
        "action_count": int(config["action_count"]),
        "policy_uses_teacher": False,
        "evaluation_data_used_for_selection": False,
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            raise ScaledTanhArtifactError(
                f"summary identity mismatch for {directory}: {key}"
            )
    if not _close(
        summary.get("environment_reference_minimum_gap"), environment_minimum_gap
    ):
        raise ScaledTanhArtifactError(
            f"environment gap does not match reconstructed environment in {directory}"
        )

    try:
        with np.load(rounds_path, allow_pickle=False) as archive:
            arrays = {name: np.asarray(archive[name]) for name in archive.files}
    except (OSError, ValueError) as error:
        raise ScaledTanhArtifactError(
            f"cannot load round archive {rounds_path}: {error}"
        ) from error
    _validate_arrays(
        arrays,
        directory=directory,
        cell=cell,
        action_count=int(config["action_count"]),
        method=method,
    )
    if not _close(
        summary.get("terminal_pseudo_regret"),
        float(arrays["cumulative_pseudo_regret"][-1]),
    ):
        raise ScaledTanhArtifactError(f"terminal summary mismatch in {directory}")
    if method == "full_cg_relative":
        if summary.get("sample_cvps") != int(arrays["cumulative_sample_cvps"][-1]):
            raise ScaledTanhArtifactError(f"CG work summary mismatch in {directory}")
    elif summary.get("sample_cvps") is not None:
        raise ScaledTanhArtifactError(
            f"non-CG method reports sample-CVPs in {directory}"
        )
    expected_premise = (
        bool(np.all(arrays["premise_pass"])) if method in THEOREM_METHODS else None
    )
    expected_failures = (
        int(np.sum(~arrays["premise_pass"])) if method in THEOREM_METHODS else 0
    )
    if (
        summary.get("all_required_premises_pass") is not expected_premise
        or summary.get("premise_failure_count") != expected_failures
    ):
        raise ScaledTanhArtifactError(f"premise summary mismatch in {directory}")
    if method in THEOREM_METHODS:
        if not _close(
            summary.get("terminal_theorem_rhs"), float(arrays["theorem_rhs"][-1])
        ):
            raise ScaledTanhArtifactError(f"theorem summary mismatch in {directory}")
    elif any(
        summary.get(name) is not None
        for name in (
            "terminal_theorem_rhs",
            "terminal_rhs_per_round",
            "terminal_rhs_regret_ratio",
        )
    ):
        raise ScaledTanhArtifactError(
            f"control summary has theorem values in {directory}"
        )
    terminal_checks = {
        "terminal_gamma_prefix": "gamma",
        "terminal_gamma_endpoint": "gamma_endpoint",
        "terminal_Gamma_tail_endpoint": "Gamma_tail_endpoint",
        "terminal_Gamma_split_endpoint": "Gamma_split_endpoint",
        "terminal_exact_E": "exact_E_through_round",
        "terminal_predictable_E": "predictable_E_through_round",
        "terminal_exact_F": "exact_F_next",
        "terminal_predictable_F": "predictable_F_next",
        "terminal_residual_energy": "residual_energy_through_round",
        "terminal_residual_envelope": "residual_envelope_through_round",
    }
    if any(
        not _close(summary.get(summary_name), float(arrays[array_name][-1]))
        for summary_name, array_name in terminal_checks.items()
    ):
        raise ScaledTanhArtifactError(f"endpoint summary mismatch in {directory}")
    return (
        manifest,
        summary,
        arrays,
        _record_inputs((manifest_path, summary_path, rounds_path)),
    )


def _bootstrap_interval(
    values: FloatArray, *, resamples: int, seed_parts: Sequence[object]
) -> dict[str, float | int]:
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ScaledTanhArtifactError("bootstrap input is not a finite vector")
    if resamples <= 0:
        raise ScaledTanhArtifactError("bootstrap_resamples must be positive")
    rng = np.random.Generator(
        np.random.PCG64(derive_seed(0, "scaled-tanh-artifacts", *seed_parts))
    )
    indices = rng.integers(0, values.size, size=(resamples, values.size))
    bootstrap = np.mean(values[indices], axis=1)
    low, high = np.quantile(bootstrap, (0.025, 0.975))
    return {
        "mean": float(np.mean(values)),
        "ci95_low": float(low),
        "ci95_high": float(high),
        "n": int(values.size),
    }


def _optional_bootstrap_interval(
    values: FloatArray, *, resamples: int, seed_parts: Sequence[object]
) -> dict[str, float | int | None]:
    if values.ndim != 1 or values.size == 0 or np.any(np.isinf(values)):
        raise ScaledTanhArtifactError("optional bootstrap input is invalid")
    defined = np.isfinite(values)
    if not bool(np.all(defined)):
        return {
            "mean": None,
            "ci95_low": None,
            "ci95_high": None,
            "n": int(values.size),
            "defined_n": int(np.sum(defined)),
        }
    return _bootstrap_interval(values, resamples=resamples, seed_parts=seed_parts)


def _trajectory_interval(
    values: FloatArray, *, resamples: int, seed_parts: Sequence[object]
) -> dict[str, Any]:
    """Bootstrap complete seed trajectories, never individual time points."""

    if values.ndim != 2 or values.shape[0] == 0 or not np.all(np.isfinite(values)):
        raise ScaledTanhArtifactError("trajectory bootstrap input is not finite")
    if resamples <= 0:
        raise ScaledTanhArtifactError("bootstrap_resamples must be positive")
    rng = np.random.Generator(
        np.random.PCG64(derive_seed(0, "scaled-tanh-trajectories", *seed_parts))
    )
    indices = rng.integers(0, values.shape[0], size=(resamples, values.shape[0]))
    weights = np.zeros((resamples, values.shape[0]), dtype=np.float64)
    for row, sampled in enumerate(indices):
        weights[row] = np.bincount(sampled, minlength=values.shape[0])
    weights /= values.shape[0]
    bootstrap = weights @ values
    low, high = np.quantile(bootstrap, (0.025, 0.975), axis=0)
    return {
        "mean": np.mean(values, axis=0).tolist(),
        "ci95_low": low.tolist(),
        "ci95_high": high.tolist(),
        "n": int(values.shape[0]),
    }


def _cell_key(cell: Cell) -> tuple[int, float]:
    return cell.horizon, cell.width_ratio


def _build_group(
    *,
    profile: str,
    cell: Cell,
    method: str,
    summaries: Sequence[Mapping[str, Any]],
    runs: Sequence[Mapping[str, NDArray[np.generic]]],
    resamples: int,
) -> dict[str, Any]:
    def terminal(name: str) -> FloatArray:
        return np.asarray([float(run[name][-1]) for run in runs], dtype=np.float64)

    def maximum(name: str) -> FloatArray:
        return np.asarray([float(np.max(run[name])) for run in runs], dtype=np.float64)

    prefix = (profile, cell.token, method)
    theorem = method in THEOREM_METHODS
    group: dict[str, Any] = {
        "cell": _expected_cell(cell),
        "method": method,
        "run_count": len(runs),
        "all_required_premises_pass": (
            bool(all(item["all_required_premises_pass"] is True for item in summaries))
            if theorem
            else None
        ),
        "premise_failure_count": (
            int(sum(int(item["premise_failure_count"]) for item in summaries))
            if theorem
            else 0
        ),
        "terminal_pseudo_regret": _bootstrap_interval(
            terminal("cumulative_pseudo_regret"),
            resamples=resamples,
            seed_parts=(*prefix, "regret"),
        ),
        "terminal_sample_cvps": _bootstrap_interval(
            terminal("cumulative_sample_cvps"),
            resamples=resamples,
            seed_parts=(*prefix, "sample-cvps"),
        ),
        "maximum_exact_chi": _bootstrap_interval(
            maximum("exact_chi_t"),
            resamples=resamples,
            seed_parts=(*prefix, "exact-chi"),
        ),
        "maximum_old_chi_bar": _bootstrap_interval(
            maximum("old_chi_bar_t"),
            resamples=resamples,
            seed_parts=(*prefix, "old-chi"),
        ),
        "maximum_exact_rho": _bootstrap_interval(
            maximum("exact_rho_t"),
            resamples=resamples,
            seed_parts=(*prefix, "exact-rho"),
        ),
        "analytic_rho_W": float(runs[0]["analytic_rho_W"][0]),
        "maximum_exact_psi": _bootstrap_interval(
            maximum("exact_psi_t"),
            resamples=resamples,
            seed_parts=(*prefix, "exact-psi"),
        ),
        "maximum_relative_psi_certificate": _bootstrap_interval(
            maximum("relative_psi_bar_t"),
            resamples=resamples,
            seed_parts=(*prefix, "relative-psi"),
        ),
        "maximum_old_psi_certificate": _bootstrap_interval(
            maximum("old_psi_bar_t"),
            resamples=resamples,
            seed_parts=(*prefix, "old-psi"),
        ),
    }
    if theorem:
        group["terminal_theorem_rhs"] = _bootstrap_interval(
            terminal("theorem_rhs"),
            resamples=resamples,
            seed_parts=(*prefix, "rhs"),
        )
        group["terminal_rhs_per_round"] = _bootstrap_interval(
            terminal("rhs_per_round"),
            resamples=resamples,
            seed_parts=(*prefix, "rhs-per-round"),
        )
        group["terminal_rhs_regret_ratio"] = _optional_bootstrap_interval(
            terminal("rhs_regret_ratio"),
            resamples=resamples,
            seed_parts=(*prefix, "rhs-regret-ratio"),
        )
    else:
        group["terminal_theorem_rhs"] = None
        group["terminal_rhs_per_round"] = None
        group["terminal_rhs_regret_ratio"] = None
    return group


def _load_selection(
    config: dict[str, Any],
    *,
    profile: str,
    selection_path: Path,
    runner_source_sha256: str,
) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    _validate_record(selection_path)
    try:
        selection = load_optimizer_selection(config, selection_path, profile=profile)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ScaledTanhArtifactError(
            f"invalid optimizer selection {selection_path}: {error}"
        ) from error
    expected = {
        "selection_cells": [
            cell.__dict__ for cell in optimizer_selection_cells(config)
        ],
        "criterion": config["optimizer_selection"]["criterion"],
        "protocol_amendment": config["protocol_amendment"],
        "evaluation_metrics_read": False,
    }
    for key, value in expected.items():
        if selection.get(key) != value:
            raise ScaledTanhArtifactError(f"optimizer selection mismatch for {key}")
    provenance = selection.get("provenance")
    if not isinstance(provenance, dict):
        raise ScaledTanhArtifactError("optimizer selection provenance is invalid")
    if provenance.get("source_artifact_hashes") != {
        "experiments/run_scaled_tanh_instantiation.py": runner_source_sha256
    }:
        raise ScaledTanhArtifactError(
            "optimizer selection runner source hash is invalid"
        )
    digest = sha256_file(selection_path)
    return selection, digest, _record_inputs((selection_path,))


def build_aggregate(
    config: dict[str, Any],
    *,
    profile: str,
    raw_root: Path,
    selection_path: Path,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    validate_config(config)
    if config.get("profile") != profile:
        raise ScaledTanhArtifactError(
            "resolved config profile does not match --profile"
        )
    methods = tuple(str(value) for value in config["methods"])
    required_methods = {"exact_current_relative", "full_cg_relative"}
    if not required_methods <= set(methods):
        raise ScaledTanhArtifactError(
            "artifact generation requires exact_current_relative and full_cg_relative"
        )
    if 1.0 not in {float(value) for value in config["width_ratios"]}:
        raise ScaledTanhArtifactError("artifact generation requires width ratio 1")
    seeds = get_seed_set(config, "evaluation")
    resamples = int(config["bootstrap_resamples"])
    if set(seeds) & set(get_seed_set(config, "tuning")):
        raise ScaledTanhArtifactError("tuning and evaluation seeds overlap")

    runner_source_sha256 = _runner_source_sha256()
    selection, selection_sha256, selection_inputs = _load_selection(
        config,
        profile=profile,
        selection_path=selection_path,
        runner_source_sha256=runner_source_sha256,
    )
    environment = make_environment(config)
    inputs: list[dict[str, str]] = [
        *selection_inputs,
        {
            "path": "experiments/run_scaled_tanh_instantiation.py",
            "sha256": runner_source_sha256,
        },
    ]
    manifests: list[str] = []
    study_cells = cells(config)
    reference_cell = next(
        cell
        for cell in study_cells
        if cell.horizon == max(int(value) for value in config["horizons"])
        and cell.width_ratio == 1.0
    )
    reference_method = "exact_current_relative"
    trace_names = (
        "exact_chi_t",
        "old_chi_bar_t",
        "exact_rho_t",
        "analytic_rho_W",
        "exact_psi_t",
        "relative_psi_bar_t",
        "old_psi_bar_t",
    )
    reference_runs: list[dict[str, FloatArray]] = []
    group_records: dict[tuple[int, float, str], dict[str, Any]] = {}
    comparisons: list[dict[str, Any]] = []
    load_methods = (
        "exact_current_relative",
        "full_cg_relative",
        *(method for method in methods if method not in required_methods),
    )

    for cell in study_cells:
        expected_streams = {seed: make_stream(config, cell, seed) for seed in seeds}
        exact_actions: list[NDArray[np.int64]] = []
        exact_regrets: list[float] = []
        comparison_values: dict[str, list[float]] = {
            "agreements": [],
            "width_errors": [],
            "energy_errors": [],
            "regret_differences": [],
            "sample_cvps": [],
        }
        for method in load_methods:
            summaries: list[dict[str, Any]] = []
            runs: list[dict[str, NDArray[np.generic]]] = []
            for seed in seeds:
                expected_stream = expected_streams[seed]
                directory = _run_directory(raw_root, profile, cell, method, seed)
                manifest, summary, arrays, run_inputs = _load_run(
                    directory,
                    config=config,
                    profile=profile,
                    seed=seed,
                    cell=cell,
                    method=method,
                    environment_sha256=environment.digest,
                    environment_minimum_gap=environment.minimum_gap,
                    stream_sha256=expected_stream.digest,
                    optimizer_selection_sha256=selection_sha256,
                    runner_source_sha256=runner_source_sha256,
                )
                if manifest["stream_sha256"] != expected_stream.digest:
                    raise ScaledTanhArtifactError(
                        f"stream mismatch for {cell.token}/{method}/seed-{seed}"
                    )
                summaries.append(summary)
                runs.append(arrays)
                inputs.extend(run_inputs)
                manifests.append((directory / "manifest.json").as_posix())
            group_records[(*_cell_key(cell), method)] = _build_group(
                profile=profile,
                cell=cell,
                method=method,
                summaries=summaries,
                runs=runs,
                resamples=resamples,
            )
            if method == "exact_current_relative":
                exact_actions = [
                    np.asarray(run["selected_actions"], dtype=np.int64).copy()
                    for run in runs
                ]
                exact_regrets = [
                    float(run["cumulative_pseudo_regret"][-1]) for run in runs
                ]
                if cell == reference_cell:
                    reference_runs = [
                        {
                            name: np.asarray(run[name], dtype=np.float64).copy()
                            for name in trace_names
                        }
                        for run in runs
                    ]
            elif method == "full_cg_relative":
                if len(exact_actions) != len(runs):
                    raise ScaledTanhArtifactError(
                        f"exact/CG pairing is incomplete for {cell.token}"
                    )
                for index, run in enumerate(runs):
                    comparison_values["agreements"].append(
                        float(np.mean(exact_actions[index] == run["selected_actions"]))
                    )
                    dense = np.asarray(run["dense_width_squared"], dtype=np.float64)
                    computed = np.asarray(
                        run["computed_width_squared"], dtype=np.float64
                    )
                    relative = np.abs(computed - dense) / np.maximum(
                        np.abs(dense), 1e-15
                    )
                    comparison_values["width_errors"].append(float(np.max(relative)))
                    comparison_values["energy_errors"].append(
                        float(np.max(run["cg_energy_error"]))
                    )
                    comparison_values["regret_differences"].append(
                        float(run["cumulative_pseudo_regret"][-1])
                        - exact_regrets[index]
                    )
                    comparison_values["sample_cvps"].append(
                        float(run["cumulative_sample_cvps"][-1])
                    )

        prefix = (profile, cell.token, "exact-cg")
        theorem_groups = [
            group_records[(*_cell_key(cell), method)]
            for method in methods
            if method in THEOREM_METHODS
        ]
        exact_group = group_records[(*_cell_key(cell), "exact_current_relative")]
        comparisons.append(
            {
                "cell": _expected_cell(cell),
                "all_theorem_premises_pass": bool(
                    all(group["all_required_premises_pass"] for group in theorem_groups)
                ),
                "analytic_rho_W": exact_group["analytic_rho_W"],
                "exact_terminal_pseudo_regret": exact_group["terminal_pseudo_regret"],
                "exact_terminal_rhs_per_round": exact_group["terminal_rhs_per_round"],
                "action_agreement": _bootstrap_interval(
                    np.asarray(comparison_values["agreements"]),
                    resamples=resamples,
                    seed_parts=(*prefix, "action-agreement"),
                ),
                "maximum_relative_width_squared_error": _bootstrap_interval(
                    np.asarray(comparison_values["width_errors"]),
                    resamples=resamples,
                    seed_parts=(*prefix, "width-error"),
                ),
                "maximum_cg_energy_error": _bootstrap_interval(
                    np.asarray(comparison_values["energy_errors"]),
                    resamples=resamples,
                    seed_parts=(*prefix, "energy-error"),
                ),
                "terminal_regret_difference": _bootstrap_interval(
                    np.asarray(comparison_values["regret_differences"]),
                    resamples=resamples,
                    seed_parts=(*prefix, "regret-difference"),
                ),
                "terminal_cg_sample_cvps": _bootstrap_interval(
                    np.asarray(comparison_values["sample_cvps"]),
                    resamples=resamples,
                    seed_parts=(*prefix, "sample-cvps"),
                ),
            }
        )

    groups = [
        group_records[(*_cell_key(cell), method)]
        for cell in study_cells
        for method in methods
    ]
    if len(reference_runs) != len(seeds):
        raise ScaledTanhArtifactError("canonical certificate trace is incomplete")
    certificate_trace = {
        "cell": _expected_cell(reference_cell),
        "method": reference_method,
        "rounds": list(range(1, reference_cell.horizon + 1)),
        "metrics": {
            name: _trajectory_interval(
                np.stack(
                    [np.asarray(run[name], dtype=np.float64) for run in reference_runs]
                ),
                resamples=resamples,
                seed_parts=(profile, reference_cell.token, reference_method, name),
            )
            for name in trace_names
        },
    }

    normalized_inputs = sorted(inputs, key=lambda item: item["path"])
    expected_run_count = len(study_cells) * len(methods) * len(seeds)
    evidence_scope = (
        "smoke-only engineering verification; not main-paper evidence"
        if profile == "smoke"
        else "prespecified full-profile evaluation"
    )
    report = {
        "schema_version": 1,
        "experiment": "scaled_tanh_instantiation_aggregate",
        "profile": profile,
        "evidence_scope": evidence_scope,
        "config": config,
        "config_digest": config_digest(config),
        "environment_sha256": environment.digest,
        "environment_reference_minimum_gap": environment.minimum_gap,
        "evaluation_seeds": list(seeds),
        "evaluation_seed_count": len(seeds),
        "tuning_seeds": list(get_seed_set(config, "tuning")),
        "tuning_evaluation_seeds_disjoint": True,
        "selection_protocol": config["selection_protocol"],
        "optimizer_selection": selection,
        "optimizer_selection_path": selection_path.as_posix(),
        "optimizer_selection_sha256": selection_sha256,
        "runner_source_sha256": runner_source_sha256,
        "evaluation_data_used_for_selection": False,
        "manifest_policy": (
            "only the expected evaluation manifests enumerated from the resolved "
            "profile seed set, cells, and methods are consumed"
        ),
        "expected_run_count": expected_run_count,
        "validated_run_count": len(manifests),
        "validated_manifests": sorted(manifests),
        "interval": {
            "method": "whole-trajectory percentile bootstrap over evaluation seeds",
            "confidence": 0.95,
            "resamples": resamples,
            "unit": "one complete evaluation-seed trajectory",
        },
        "width_error_definition": (
            "maximum over rounds and actions of abs(CG width squared - exact width "
            "squared) / max(abs(exact width squared), 1e-15)"
        ),
        "groups": groups,
        "exact_cg_comparisons": comparisons,
        "certificate_trace": certificate_trace,
        "raw_inputs": normalized_inputs,
        "input_set_sha256": input_set_sha256(normalized_inputs),
    }
    return report, normalized_inputs


def _group_index(
    report: Mapping[str, Any],
) -> dict[tuple[int, float, str], Mapping[str, Any]]:
    return {
        (
            int(group["cell"]["horizon"]),
            float(group["cell"]["width_ratio"]),
            str(group["method"]),
        ): group
        for group in report["groups"]
    }


def _comparison_index(
    report: Mapping[str, Any],
) -> dict[tuple[int, float], Mapping[str, Any]]:
    return {
        (
            int(item["cell"]["horizon"]),
            float(item["cell"]["width_ratio"]),
        ): item
        for item in report["exact_cg_comparisons"]
    }


def _interval_vectors(
    records: Sequence[Mapping[str, Any]], key: str
) -> tuple[FloatArray, FloatArray, FloatArray]:
    intervals = [record[key] for record in records]
    if any(interval is None or interval["mean"] is None for interval in intervals):
        raise ScaledTanhArtifactError(f"cannot plot undefined interval {key}")
    return (
        np.asarray([interval["mean"] for interval in intervals], dtype=np.float64),
        np.asarray([interval["ci95_low"] for interval in intervals], dtype=np.float64),
        np.asarray([interval["ci95_high"] for interval in intervals], dtype=np.float64),
    )


def _optional_interval_vectors(
    records: Sequence[Mapping[str, Any]], key: str
) -> tuple[NDArray[np.bool_], FloatArray, FloatArray, FloatArray]:
    intervals = [record[key] for record in records]
    defined = np.asarray(
        [
            interval is not None and interval["mean"] is not None
            for interval in intervals
        ],
        dtype=np.bool_,
    )
    selected = [interval for interval, keep in zip(intervals, defined) if keep]
    return (
        defined,
        np.asarray([interval["mean"] for interval in selected], dtype=np.float64),
        np.asarray([interval["ci95_low"] for interval in selected], dtype=np.float64),
        np.asarray([interval["ci95_high"] for interval in selected], dtype=np.float64),
    )


def _configure_pdf_fonts() -> None:
    matplotlib.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})


def _save_figure(figure: plt.Figure, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        output,
        bbox_inches="tight",
        metadata={
            "Creator": "scaled_tanh_instantiation",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    plt.close(figure)
    write_sha256_sidecar(output)


def _add_scope_banner(figure: plt.Figure, report: Mapping[str, Any]) -> float:
    if report["profile"] == "smoke":
        figure.suptitle(
            "Smoke verification only; not main-paper evidence",
            fontsize=9,
            color="#A12A2A",
        )
        return 0.88
    return 0.95


def make_certificates_figure(report: Mapping[str, Any], output: Path) -> None:
    _configure_pdf_fonts()
    trace = report["certificate_trace"]
    rounds = np.asarray(trace["rounds"], dtype=np.float64)
    metrics = trace["metrics"]
    figure, axes = plt.subplots(1, 2, figsize=(9.0, 3.45))
    left_specs = (
        ("exact_chi_t", r"Exact $\chi_t$", "#111111", "-"),
        ("old_chi_bar_t", r"Old $\bar\chi_t$", "#D9822B", "-"),
        ("exact_rho_t", r"Exact $\rho_t$", "#2474B5", "-"),
        ("analytic_rho_W", r"Analytic $\rho_W$", "#777777", "--"),
    )
    right_specs = (
        ("exact_psi_t", r"Exact $\psi_t$", "#111111", "-"),
        ("relative_psi_bar_t", r"Relative $\bar\psi_t$", "#2E8B57", "-"),
        ("old_psi_bar_t", r"Old $\bar\psi_t$", "#D9822B", "--"),
    )
    for axis, specifications in zip(axes, (left_specs, right_specs)):
        for name, label, color, linestyle in specifications:
            interval = metrics[name]
            mean = np.asarray(interval["mean"], dtype=np.float64)
            low = np.asarray(interval["ci95_low"], dtype=np.float64)
            high = np.asarray(interval["ci95_high"], dtype=np.float64)
            plotting_floor = 1e-8
            axis.plot(
                rounds,
                np.maximum(mean, plotting_floor),
                color=color,
                linestyle=linestyle,
                linewidth=1.5,
                label=label,
            )
            if name != "analytic_rho_W":
                axis.fill_between(
                    rounds,
                    np.maximum(low, plotting_floor),
                    np.maximum(high, plotting_floor),
                    color=color,
                    alpha=0.12,
                    linewidth=0,
                )
        axis.set_xscale("log", base=2)
        axis.set_yscale("log")
        axis.set_ylim(bottom=plotting_floor)
        axis.set_xlabel("Round")
        axis.grid(alpha=0.2, linewidth=0.5)
        axis.legend(frameon=False, fontsize=8)
    axes[0].set_title("Curvature-transfer certificates", fontsize=9)
    axes[0].set_ylabel("Certificate value")
    axes[1].set_title("Predictable-centering certificates", fontsize=9)
    axes[1].set_ylabel("Centering value")
    cell = trace["cell"]
    figure.text(
        0.5,
        0.01,
        f"T={cell['horizon']}, W/(T R_T)={float(cell['width_ratio']):g}, exact relative policy",
        ha="center",
        fontsize=7,
    )
    top = _add_scope_banner(figure, report)
    figure.tight_layout(rect=(0, 0.04, 1, top))
    _save_figure(figure, output)


def make_regret_bounds_figure(report: Mapping[str, Any], output: Path) -> None:
    _configure_pdf_fonts()
    config = report["config"]
    horizons = np.asarray(config["horizons"], dtype=np.float64)
    methods = [method for method in config["methods"] if method in THEOREM_METHODS]
    groups = _group_index(report)
    figure, axes = plt.subplots(1, 3, figsize=(12.0, 3.5))
    for method in methods:
        records = [groups[(int(horizon), 1.0, method)] for horizon in horizons]
        color = METHOD_COLORS[method]
        regret, regret_low, regret_high = _interval_vectors(
            records, "terminal_pseudo_regret"
        )
        rhs, rhs_low, rhs_high = _interval_vectors(records, "terminal_theorem_rhs")
        per_round, per_low, per_high = _interval_vectors(
            records, "terminal_rhs_per_round"
        )
        ratio_defined, ratio, ratio_low, ratio_high = _optional_interval_vectors(
            records, "terminal_rhs_regret_ratio"
        )
        axes[0].plot(
            horizons,
            regret,
            color=color,
            marker="o",
            linewidth=1.4,
            label=f"{METHOD_LABELS[method]} regret",
        )
        axes[0].plot(
            horizons,
            rhs,
            color=color,
            marker="s",
            linestyle="--",
            linewidth=1.1,
            label=f"{METHOD_LABELS[method]} RHS",
        )
        axes[0].fill_between(
            horizons, regret_low, regret_high, color=color, alpha=0.10, linewidth=0
        )
        axes[0].fill_between(
            horizons, rhs_low, rhs_high, color=color, alpha=0.06, linewidth=0
        )
        axes[1].plot(
            horizons,
            per_round,
            color=color,
            marker="o",
            linewidth=1.4,
            label=METHOD_LABELS[method],
        )
        axes[1].fill_between(
            horizons, per_low, per_high, color=color, alpha=0.10, linewidth=0
        )
        if np.any(ratio_defined):
            axes[2].plot(
                horizons[ratio_defined],
                ratio,
                color=color,
                marker="o",
                linewidth=1.4,
                label=METHOD_LABELS[method],
            )
            axes[2].fill_between(
                horizons[ratio_defined],
                ratio_low,
                ratio_high,
                color=color,
                alpha=0.10,
                linewidth=0,
            )
    titles = ("Cumulative regret and theorem RHS", "RHS / T", "RHS / regret")
    ylabels = ("Terminal value", "Per-round bound", "Bound ratio")
    for axis, title, ylabel in zip(axes, titles, ylabels):
        axis.set_xscale("log", base=2)
        axis.set_yscale("log")
        axis.set_xlabel("Horizon")
        axis.set_ylabel(ylabel)
        axis.set_title(title, fontsize=9)
        axis.grid(alpha=0.2, linewidth=0.5)
    axes[0].legend(frameon=False, fontsize=6, ncol=2)
    axes[1].legend(frameon=False, fontsize=7)
    top = _add_scope_banner(figure, report)
    figure.tight_layout(rect=(0, 0, 1, top))
    _save_figure(figure, output)


def make_compute_figure(report: Mapping[str, Any], output: Path) -> None:
    _configure_pdf_fonts()
    config = report["config"]
    horizons = np.asarray(config["horizons"], dtype=np.float64)
    ratios = tuple(float(value) for value in config["width_ratios"])
    groups = _group_index(report)
    comparisons = _comparison_index(report)
    figure, axes = plt.subplots(1, 3, figsize=(12.0, 3.5))
    for method in config["methods"]:
        records = [groups[(int(horizon), 1.0, method)] for horizon in horizons]
        work, work_low, work_high = _interval_vectors(records, "terminal_sample_cvps")
        regret, regret_low, regret_high = _interval_vectors(
            records, "terminal_pseudo_regret"
        )
        axes[0].errorbar(
            work,
            regret,
            xerr=np.vstack((work - work_low, work_high - work)),
            yerr=np.vstack((regret - regret_low, regret_high - regret)),
            color=METHOD_COLORS[method],
            marker="o",
            linewidth=1.1,
            capsize=2,
            label=METHOD_LABELS[method],
        )
    ratio_colors = plt.get_cmap("tab10")
    for index, ratio in enumerate(ratios):
        records = [comparisons[(int(horizon), ratio)] for horizon in horizons]
        agreement, agreement_low, agreement_high = _interval_vectors(
            records, "action_agreement"
        )
        error, error_low, error_high = _interval_vectors(
            records, "maximum_relative_width_squared_error"
        )
        error = np.maximum(error, 1e-18)
        error_low = np.maximum(error_low, 1e-18)
        error_high = np.maximum(error_high, 1e-18)
        color = ratio_colors(index % 10)
        label = rf"$W/(T R_T)={ratio:g}$"
        axes[1].plot(
            horizons, agreement, marker="o", color=color, linewidth=1.4, label=label
        )
        axes[1].fill_between(
            horizons,
            agreement_low,
            agreement_high,
            color=color,
            alpha=0.12,
            linewidth=0,
        )
        axes[2].plot(
            horizons, error, marker="o", color=color, linewidth=1.4, label=label
        )
        axes[2].fill_between(
            horizons, error_low, error_high, color=color, alpha=0.12, linewidth=0
        )
    axes[0].set_xscale("symlog", linthresh=1.0)
    axes[0].set_yscale("log")
    axes[0].set(
        xlabel="Width-solve sample-CVPs",
        ylabel="Terminal pseudo-regret",
        title="Regret versus solve work",
    )
    axes[1].set_xscale("log", base=2)
    axes[1].set_ylim(-0.02, 1.02)
    axes[1].set(
        xlabel="Horizon",
        ylabel="Agreement fraction",
        title="Exact / CG action agreement",
    )
    axes[2].set_xscale("log", base=2)
    axes[2].set_yscale("log")
    axes[2].set(
        xlabel="Horizon",
        ylabel="Maximum relative error",
        title="CG width-squared error",
    )
    axes[0].legend(frameon=False, fontsize=6, ncol=2)
    axes[1].legend(frameon=False, fontsize=7)
    for axis in axes:
        axis.title.set_fontsize(9)
        axis.grid(alpha=0.2, linewidth=0.5)
    top = _add_scope_banner(figure, report)
    figure.tight_layout(rect=(0, 0, 1, top))
    _save_figure(figure, output)


def _format_mean(interval: Mapping[str, Any], *, digits: int = 3) -> str:
    value = interval.get("mean")
    return "--" if value is None else f"{float(value):.{digits}g}"


def make_table(report: Mapping[str, Any], output: Path) -> None:
    lines = [
        r"\begin{tabular}{rrrcrrrrr}",
        r"\toprule",
    ]
    if report["profile"] == "smoke":
        lines.extend(
            (
                r"\multicolumn{9}{c}{\emph{Smoke verification only; not main-paper evidence.}} \\",
                r"\midrule",
            )
        )
    lines.extend(
        (
            r"$T$ & $W/(T R_T)$ & $\rho_W$ & Premises & Regret & RHS/$T$ & CG agree. & Max width err. & Sample-CVPs \\",
            r"\midrule",
        )
    )
    for item in report["exact_cg_comparisons"]:
        cell = item["cell"]
        status = "PASS" if item["all_theorem_premises_pass"] else "FAIL"
        lines.append(
            f"{int(cell['horizon'])} & {float(cell['width_ratio']):g} & "
            f"{float(item['analytic_rho_W']):.3g} & {status} & "
            f"{_format_mean(item['exact_terminal_pseudo_regret'])} & "
            f"{_format_mean(item['exact_terminal_rhs_per_round'])} & "
            f"{_format_mean(item['action_agreement'])} & "
            f"{_format_mean(item['maximum_relative_width_squared_error'])} & "
            f"{_format_mean(item['terminal_cg_sample_cvps'])} \\\\"
        )
    lines.extend((r"\bottomrule", r"\end{tabular}"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="ascii")
    write_sha256_sidecar(output)


def _write_provenance(
    artifact: Path,
    *,
    aggregate_path: Path,
    report: Mapping[str, Any],
) -> Path:
    aggregate_sidecar = aggregate_path.with_name(aggregate_path.name + ".sha256")
    inputs = [
        {"path": aggregate_path.as_posix(), "sha256": sha256_file(aggregate_path)},
        {
            "path": aggregate_sidecar.as_posix(),
            "sha256": sha256_file(aggregate_sidecar),
        },
    ]
    provenance = artifact.with_name(artifact.name + ".provenance.json")
    write_json_artifact(
        provenance,
        {
            "schema_version": 1,
            "experiment": "scaled_tanh_instantiation",
            "artifact": artifact.as_posix(),
            "artifact_sha256": sha256_file(artifact),
            "profile": report["profile"],
            "evidence_scope": report["evidence_scope"],
            "inputs": inputs,
            "input_set_sha256": input_set_sha256(inputs),
            "generation_parameters": {
                "config_digest": report["config_digest"],
                "optimizer_selection_sha256": report["optimizer_selection_sha256"],
                "runner_source_sha256": report["runner_source_sha256"],
                "interval": report["interval"],
                "pdf_fonttype": 42 if artifact.suffix == ".pdf" else None,
            },
        },
    )
    return provenance


def make_artifacts(
    config: dict[str, Any],
    *,
    profile: str,
    raw_root: Path,
    selection_path: Path,
    aggregate_path: Path,
    certificates_figure_path: Path,
    regret_bounds_figure_path: Path,
    compute_figure_path: Path,
    table_path: Path,
) -> dict[str, Any]:
    report, inputs = build_aggregate(
        config,
        profile=profile,
        raw_root=raw_root,
        selection_path=selection_path,
    )
    write_json_artifact(aggregate_path, report)
    make_certificates_figure(report, certificates_figure_path)
    make_regret_bounds_figure(report, regret_bounds_figure_path)
    make_compute_figure(report, compute_figure_path)
    make_table(report, table_path)
    artifacts = (
        certificates_figure_path,
        regret_bounds_figure_path,
        compute_figure_path,
        table_path,
    )
    provenance = [
        _write_provenance(
            artifact,
            aggregate_path=aggregate_path,
            report=report,
        )
        for artifact in artifacts
    ]
    return {
        "profile": profile,
        "evidence_scope": report["evidence_scope"],
        "aggregate": aggregate_path.as_posix(),
        "validated_run_count": report["validated_run_count"],
        "raw_input_count": len(inputs),
        "input_set_sha256": report["input_set_sha256"],
        "artifacts": [path.as_posix() for path in artifacts],
        "provenance": [path.as_posix() for path in provenance],
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--certificates-figure", type=Path, required=True)
    parser.add_argument("--regret-bounds-figure", type=Path, required=True)
    parser.add_argument("--compute-figure", type=Path, required=True)
    parser.add_argument("--table", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config, profile=args.profile)
    result = make_artifacts(
        config,
        profile=args.profile,
        raw_root=args.raw_root,
        selection_path=args.selection,
        aggregate_path=args.aggregate,
        certificates_figure_path=args.certificates_figure,
        regret_bounds_figure_path=args.regret_bounds_figure,
        compute_figure_path=args.compute_figure,
        table_path=args.table,
    )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = [
    "ScaledTanhArtifactError",
    "build_aggregate",
    "make_artifacts",
]
