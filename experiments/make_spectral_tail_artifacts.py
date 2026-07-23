"""Build validated spectral-tail aggregates, figures, and LaTeX tables."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

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
from .run_spectral_tail_study import Cell, validate_study_config


FloatArray = NDArray[np.float64]

BOUND_FIELDS = (
    "gamma_exact",
    "gamma_split",
    "gamma_tail_old",
    "gamma_ambient_realized_trace",
    "gamma_ambient_worst_case",
)
BOUND_LABELS = {
    "gamma_exact": r"Realized $\gamma_t$",
    "gamma_split": r"Refined $\Gamma_{\rm split}$",
    "gamma_tail_old": r"Old $\Gamma_{\rm tail}$",
    "gamma_ambient_realized_trace": r"Ambient, realized trace",
    "gamma_ambient_worst_case": r"Ambient, $tG^2/\sigma^2$",
}
BOUND_COLORS = {
    "gamma_exact": "#111111",
    "gamma_split": "#2474B5",
    "gamma_tail_old": "#C43C39",
    "gamma_ambient_realized_trace": "#2E8B57",
    "gamma_ambient_worst_case": "#D9822B",
}
BOUND_LINESTYLES = {
    "gamma_exact": "-",
    "gamma_split": "-",
    "gamma_tail_old": "--",
    "gamma_ambient_realized_trace": ":",
    "gamma_ambient_worst_case": "--",
}
BOUND_MARKERS = {
    "gamma_exact": None,
    "gamma_split": None,
    "gamma_tail_old": None,
    "gamma_ambient_realized_trace": "o",
    "gamma_ambient_worst_case": None,
}
BOUND_PLOT_ORDER = (
    "gamma_exact",
    "gamma_split",
    "gamma_tail_old",
    "gamma_ambient_worst_case",
    "gamma_ambient_realized_trace",
)
BOUND_TOLERANCE_MULTIPLIER = 4096.0

METHOD_LABELS = {
    "exact_dense_full": "Exact dense full",
    "full_cg": "Residual-checked full CG",
    "rank_truncation": "Rank truncation",
    "diagonal": "Diagonal",
    "block_diagonal": "Block diagonal",
    "frequent_directions": "Frequent Directions",
    "greedy": "Greedy",
}
METHOD_COLORS = {
    "exact_dense_full": "#111111",
    "full_cg": "#2474B5",
    "rank_truncation": "#C43C39",
    "diagonal": "#D9822B",
    "block_diagonal": "#6B4C9A",
    "frequent_directions": "#2E8B57",
    "greedy": "#777777",
}


class SpectralTailArtifactError(ValueError):
    """Raised when raw records cannot support the requested artifacts."""


def _rank_mass_log_bound(
    mass: FloatArray, rank: FloatArray, damping: float
) -> FloatArray:
    result = np.zeros_like(mass, dtype=np.float64)
    positive = rank > 0.0
    if np.any(mass[~positive] > 0.0):
        raise SpectralTailArtifactError("positive spectral mass has zero rank")
    result[positive] = rank[positive] * np.log1p(
        mass[positive] / (rank[positive] * damping)
    )
    return result


def _bound_tolerance(dimension: int, *values: FloatArray) -> FloatArray:
    scale = np.ones_like(values[0], dtype=np.float64)
    for value in values:
        scale = np.maximum(scale, np.abs(value))
    return (
        BOUND_TOLERANCE_MULTIPLIER
        * np.finfo(np.float64).eps
        * max(1, dimension)
        * scale
    )


def _verify_upper_bound(
    lower: FloatArray,
    upper: FloatArray,
    tolerance: FloatArray,
    *,
    relation: str,
) -> dict[str, float]:
    excess = lower - upper
    adjusted = excess - tolerance
    if np.any(adjusted > 0.0):
        index = int(np.argmax(adjusted))
        raise SpectralTailArtifactError(
            f"bound ordering {relation} failed at round {index + 1}: "
            f"lower={lower[index]:.17g}, upper={upper[index]:.17g}, "
            f"tolerance={tolerance[index]:.17g}"
        )
    return {
        "minimum_slack": float(np.min(upper - lower)),
        "maximum_excess": float(np.max(excess)),
        "maximum_tolerance_adjusted_excess": float(np.max(adjusted)),
    }


def _reanalyze_trajectory_bounds(
    arrays: Mapping[str, NDArray[np.generic]],
    config: Mapping[str, Any],
    *,
    tail_rank: int,
) -> tuple[dict[str, FloatArray], dict[str, Any]]:
    """Recompute spectral bounds from one retained action trajectory."""

    rounds = int(config["rounds"])
    dimension = int(config["dimension"])
    damping = float(config["damping"])
    variance = float(config["noise_std"]) ** 2
    feature_bound = float(config["feature_bound"])
    required = ("gamma", "spectral_tail", "gamma_tail", "selected_coordinates")
    if any(name not in arrays for name in required):
        raise SpectralTailArtifactError(
            "retained trajectory lacks arrays required for bound reanalysis"
        )
    gamma_exact = np.asarray(arrays["gamma"], dtype=np.float64)
    spectral_tail = np.asarray(arrays["spectral_tail"], dtype=np.float64)
    gamma_tail_raw = np.asarray(arrays["gamma_tail"], dtype=np.float64)
    selected_coordinates = np.asarray(
        arrays["selected_coordinates"], dtype=np.int64
    )
    if any(
        value.shape != (rounds,)
        for value in (
            gamma_exact,
            spectral_tail,
            gamma_tail_raw,
            selected_coordinates,
        )
    ):
        raise SpectralTailArtifactError("retained bound arrays have invalid coverage")
    if (
        not np.all(np.isfinite(gamma_exact))
        or not np.all(np.isfinite(spectral_tail))
        or not np.all(np.isfinite(gamma_tail_raw))
        or np.any(selected_coordinates < 0)
        or np.any(selected_coordinates >= dimension)
    ):
        raise SpectralTailArtifactError("retained bound arrays contain invalid values")

    steps = np.arange(1, rounds + 1, dtype=np.float64)
    # The study plays signed columns of an orthogonal rotation. Every selected
    # feature therefore has squared norm one, so this is the realized trace.
    trace = steps / variance
    effective_top_rank = np.minimum(float(tail_rank), steps)
    effective_tail_rank = np.minimum(
        float(dimension - tail_rank), np.maximum(steps - float(tail_rank), 0.0)
    )
    effective_ambient_rank = np.minimum(float(dimension), steps)

    preliminary_tolerance = _bound_tolerance(
        dimension, gamma_exact, spectral_tail, gamma_tail_raw, trace
    )
    spectral_head = trace - spectral_tail
    if np.any(spectral_head < -preliminary_tolerance):
        index = int(np.argmin(spectral_head))
        raise SpectralTailArtifactError(
            f"spectral tail exceeds the realized trace at round {index + 1}"
        )
    spectral_head = np.maximum(spectral_head, 0.0)

    gamma_split = _rank_mass_log_bound(
        spectral_head, effective_top_rank, damping
    ) + _rank_mass_log_bound(spectral_tail, effective_tail_rank, damping)
    worst_trace = steps * feature_bound * feature_bound / variance
    gamma_tail_old = _rank_mass_log_bound(
        np.where(effective_top_rank > 0.0, worst_trace, 0.0),
        effective_top_rank,
        damping,
    ) + spectral_tail / damping
    gamma_ambient_realized = _rank_mass_log_bound(
        trace, effective_ambient_rank, damping
    )
    gamma_ambient_worst = _rank_mass_log_bound(
        worst_trace, effective_ambient_rank, damping
    )
    tolerance = _bound_tolerance(
        dimension,
        gamma_exact,
        gamma_split,
        gamma_tail_old,
        gamma_ambient_realized,
        gamma_ambient_worst,
    )

    raw_old_error = np.abs(gamma_tail_raw - gamma_tail_old)
    if np.any(raw_old_error > tolerance):
        index = int(np.argmax(raw_old_error - tolerance))
        raise SpectralTailArtifactError(
            f"retained old tail bound disagrees with its formula at round {index + 1}"
        )

    comparisons = {
        "gamma_exact_le_gamma_split": _verify_upper_bound(
            gamma_exact,
            gamma_split,
            tolerance,
            relation="gamma_exact <= gamma_split",
        ),
        "gamma_split_le_gamma_tail_old": _verify_upper_bound(
            gamma_split,
            gamma_tail_old,
            tolerance,
            relation="gamma_split <= gamma_tail_old",
        ),
        "gamma_split_le_gamma_ambient_realized_trace": _verify_upper_bound(
            gamma_split,
            gamma_ambient_realized,
            tolerance,
            relation="gamma_split <= gamma_ambient_realized_trace",
        ),
        "gamma_ambient_realized_trace_le_gamma_ambient_worst_case": (
            _verify_upper_bound(
                gamma_ambient_realized,
                gamma_ambient_worst,
                tolerance,
                relation=(
                    "gamma_ambient_realized_trace <= gamma_ambient_worst_case"
                ),
            )
        ),
    }

    counts = np.zeros(dimension, dtype=np.float64)
    horizon_errors = {
        "gamma_exact": 0.0,
        "spectral_tail": 0.0,
    }
    configured_horizons = set(int(value) for value in config["horizons"])
    for index, coordinate in enumerate(selected_coordinates, start=1):
        counts[int(coordinate)] += 1.0
        if index not in configured_horizons:
            continue
        eigenvalues = np.sort(counts / variance)[::-1]
        recomputed_gamma = float(np.sum(np.log1p(eigenvalues / damping)))
        recomputed_tail = float(np.sum(eigenvalues[tail_rank:]))
        horizon_errors["gamma_exact"] = max(
            horizon_errors["gamma_exact"],
            abs(recomputed_gamma - float(gamma_exact[index - 1])),
        )
        horizon_errors["spectral_tail"] = max(
            horizon_errors["spectral_tail"],
            abs(recomputed_tail - float(spectral_tail[index - 1])),
        )
        if (
            abs(recomputed_gamma - float(gamma_exact[index - 1]))
            > float(tolerance[index - 1])
            or abs(recomputed_tail - float(spectral_tail[index - 1]))
            > float(tolerance[index - 1])
        ):
            raise SpectralTailArtifactError(
                f"retained spectrum cannot be reconstructed at horizon {index}"
            )

    return (
        {
            "gamma_exact": gamma_exact,
            "gamma_split": gamma_split,
            "gamma_tail_old": gamma_tail_old,
            "gamma_ambient_realized_trace": gamma_ambient_realized,
            "gamma_ambient_worst_case": gamma_ambient_worst,
            "spectral_tail": spectral_tail,
        },
        {
            "comparisons": comparisons,
            "maximum_tolerance": float(np.max(tolerance)),
            "maximum_raw_old_formula_error": float(np.max(raw_old_error)),
            "maximum_horizon_recomputation_error": horizon_errors,
            "checkpoint_count": rounds,
            "recomputed_horizon_count": len(configured_horizons),
        },
    )


def _cells(config: Mapping[str, Any]) -> tuple[Cell, ...]:
    return tuple(
        Cell(int(rank), int(power), str(alignment))
        for rank in config["target_ranks"]
        for power in config["spectral_powers"]
        for alignment in config["gap_alignments"]
    )


def _bonus_token(bonus: float) -> str:
    return f"{bonus:.8g}".replace(".", "p")


def _run_directory(
    root: Path,
    profile: str,
    seed: int,
    cell: Cell,
    method: str,
    bonus: float,
) -> Path:
    return (
        root
        / profile
        / "evaluation"
        / f"seed-{seed}"
        / cell.token
        / method
        / f"bonus-{_bonus_token(bonus)}"
    )


def _load_json(path: Path) -> dict[str, Any]:
    validate_sha256_sidecar(path)
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (OSError, json.JSONDecodeError) as error:
        raise SpectralTailArtifactError(f"cannot parse {path}: {error}") from error
    if not isinstance(value, dict):
        raise SpectralTailArtifactError(f"{path} is not a JSON object")
    return value


def _load_selection(
    path: Path, config: Mapping[str, Any], profile: str
) -> tuple[dict[str, float], list[dict[str, str]]]:
    value = _load_json(path)
    if (
        value.get("experiment") != "spectral_tail_study"
        or value.get("profile") != profile
        or value.get("config_digest") != config_digest(config)
        or value.get("evaluation_data_accessed") is not False
        or value.get("tuning_seeds") != list(get_seed_set(config, "tuning"))
        or value.get("evaluation_seeds") != list(get_seed_set(config, "evaluation"))
    ):
        raise SpectralTailArtifactError("selection artifact does not match the protocol")
    selected = value.get("selected_bonus")
    methods = tuple(str(method) for method in config["methods"])
    if not isinstance(selected, Mapping) or set(selected) != set(methods):
        raise SpectralTailArtifactError("selection does not cover every method")
    sidecar = path.with_name(path.name + ".sha256")
    inputs = [
        {"path": path.as_posix(), "sha256": sha256_file(path)},
        {"path": sidecar.as_posix(), "sha256": sha256_file(sidecar)},
    ]
    return {method: float(selected[method]) for method in methods}, inputs


def _load_run(
    directory: Path,
    *,
    config: Mapping[str, Any],
    profile: str,
    seed: int,
    cell: Cell,
    method: str,
    bonus: float,
) -> tuple[dict[str, Any], dict[str, FloatArray], list[dict[str, str]]]:
    manifest_path = directory / "manifest.json"
    summary_path = directory / "summary.json"
    rounds_path = directory / "rounds.npz"
    for path in (manifest_path, summary_path, rounds_path):
        if not path.is_file():
            raise SpectralTailArtifactError(f"missing raw artifact {path}")
        validate_sha256_sidecar(path)
    manifest = _load_json(manifest_path)
    summary = _load_json(summary_path)
    if (
        manifest.get("experiment") != "spectral_tail_study"
        or manifest.get("profile") != profile
        or manifest.get("phase") != "evaluation"
        or manifest.get("seed") != seed
        or manifest.get("config_digest") != config_digest(config)
        or manifest.get("rounds_sha256") != sha256_file(rounds_path)
        or manifest.get("summary_sha256") != sha256_file(summary_path)
        or summary.get("method") != method
        or summary.get("bonus") != bonus
        or summary.get("cell")
        != {
            "rank": cell.rank,
            "spectral_power": cell.spectral_power,
            "alignment": cell.alignment,
        }
    ):
        raise SpectralTailArtifactError(f"raw identity mismatch in {directory}")
    with np.load(rounds_path, allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    rounds = int(config["rounds"])
    required = {
        "cumulative_pseudo_regret",
        "gamma",
        "spectral_tail",
        "gamma_tail",
        "relative_width_error",
        "action_disagreement",
        "tail_alignment",
        "cg_iterations",
        "cg_relative_residual",
        "cumulative_sample_cvps",
    }
    if set(arrays) < required or any(
        arrays[name].shape != (rounds,) for name in required
    ):
        raise SpectralTailArtifactError(f"round array coverage is invalid in {directory}")
    inputs = []
    for path in (manifest_path, summary_path, rounds_path):
        sidecar = path.with_name(path.name + ".sha256")
        inputs.extend(
            (
                {"path": path.as_posix(), "sha256": sha256_file(path)},
                {"path": sidecar.as_posix(), "sha256": sha256_file(sidecar)},
            )
        )
    return summary, arrays, inputs


def _percentile_interval(
    values: FloatArray, *, resamples: int, seed_parts: Sequence[object]
) -> dict[str, float | int]:
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise SpectralTailArtifactError("interval input must be a finite nonempty vector")
    rng = np.random.Generator(np.random.PCG64(derive_seed(0, *seed_parts)))
    indices = rng.integers(0, values.size, size=(resamples, values.size))
    means = np.mean(values[indices], axis=1)
    low, high = np.quantile(means, (0.025, 0.975))
    return {
        "mean": float(np.mean(values)),
        "ci95_low": float(low),
        "ci95_high": float(high),
        "n": int(values.size),
    }


def _stats_by_horizon(
    matrix: FloatArray,
    horizons: Sequence[int],
    *,
    resamples: int,
    seed_parts: Sequence[object],
) -> list[dict[str, Any]]:
    return [
        {
            "horizon": int(horizon),
            "interval": _percentile_interval(
                matrix[:, horizon - 1],
                resamples=resamples,
                seed_parts=(*seed_parts, horizon),
            ),
        }
        for horizon in horizons
    ]


def build_aggregate(
    config: dict[str, Any],
    *,
    profile: str,
    raw_root: Path,
    selection_path: Path,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    validate_study_config(config)
    selected, inputs = _load_selection(selection_path, config, profile)
    seeds = get_seed_set(config, "evaluation")
    horizons = tuple(int(horizon) for horizon in config["horizons"])
    resamples = int(config["bootstrap_resamples"])
    methods = tuple(str(method) for method in config["methods"])
    groups: list[dict[str, Any]] = []
    raw: dict[
        tuple[Cell, str], list[tuple[dict[str, Any], dict[str, FloatArray]]]
    ] = {}

    for cell in _cells(config):
        for method in methods:
            runs = []
            bonus = selected[method]
            for seed in seeds:
                directory = _run_directory(
                    raw_root, profile, seed, cell, method, bonus
                )
                summary, arrays, run_inputs = _load_run(
                    directory,
                    config=config,
                    profile=profile,
                    seed=seed,
                    cell=cell,
                    method=method,
                    bonus=bonus,
                )
                runs.append((summary, arrays))
                inputs.extend(run_inputs)
            raw[(cell, method)] = runs
            record: dict[str, Any] = {
                "cell": {
                    "rank": cell.rank,
                    "spectral_power": cell.spectral_power,
                    "alignment": cell.alignment,
                },
                "method": method,
                "selected_bonus": bonus,
                "run_count": len(runs),
                "regret": _stats_by_horizon(
                    np.stack(
                        [arrays["cumulative_pseudo_regret"] for _, arrays in runs]
                    ),
                    horizons,
                    resamples=resamples,
                    seed_parts=(profile, cell.token, method, "regret"),
                ),
            }
            for field, array_name in (
                ("gamma", "gamma"),
                ("spectral_tail", "spectral_tail"),
                ("gamma_tail", "gamma_tail"),
                ("width_error", "relative_width_error"),
                ("action_disagreement", "action_disagreement"),
                ("tail_alignment", "tail_alignment"),
                ("cg_iterations", "cg_iterations"),
                ("sample_cvps", "cumulative_sample_cvps"),
            ):
                values = np.asarray(
                    [float(arrays[array_name][-1]) for _, arrays in runs],
                    dtype=np.float64,
                )
                record[field] = _percentile_interval(
                    values,
                    resamples=resamples,
                    seed_parts=(profile, cell.token, method, field),
                )
            ratios = np.asarray(
                [
                    float(arrays["gamma_tail"][-1])
                    / max(float(arrays["gamma"][-1]), 1e-15)
                    for _, arrays in runs
                ],
                dtype=np.float64,
            )
            record["gamma_tail_ratio"] = _percentile_interval(
                ratios,
                resamples=resamples,
                seed_parts=(profile, cell.token, method, "gamma_tail_ratio"),
            )
            groups.append(record)

    paired: list[dict[str, Any]] = []
    for cell in _cells(config):
        exact = raw[(cell, "exact_dense_full")]
        for method in methods:
            if method == "exact_dense_full":
                continue
            candidate = raw[(cell, method)]
            regret_difference = np.asarray(
                [
                    float(candidate[index][1]["cumulative_pseudo_regret"][-1])
                    - float(exact[index][1]["cumulative_pseudo_regret"][-1])
                    for index in range(len(seeds))
                ],
                dtype=np.float64,
            )
            paired.append(
                {
                    "cell": {
                        "rank": cell.rank,
                        "spectral_power": cell.spectral_power,
                        "alignment": cell.alignment,
                    },
                    "method": method,
                    "terminal_regret_minus_exact": _percentile_interval(
                        regret_difference,
                        resamples=resamples,
                        seed_parts=(profile, cell.token, method, "paired_regret"),
                    ),
                }
            )

    normalized_inputs = sorted(inputs, key=lambda item: item["path"])
    aggregate = {
        "schema_version": 1,
        "experiment": "spectral_tail_study_aggregate",
        "profile": profile,
        "config_digest": config_digest(config),
        "config": config,
        "selection": selected,
        "evaluation_seeds": list(seeds),
        "evaluation_seed_count": len(seeds),
        "interval": (
            "trajectory-level percentile bootstrap over evaluation seeds; "
            "evaluation data were not used for configuration selection"
        ),
        "groups": groups,
        "paired_terminal": paired,
        "raw_inputs": normalized_inputs,
        "input_set_sha256": input_set_sha256(normalized_inputs),
    }
    return aggregate, normalized_inputs


def _update_reanalysis_verification(
    combined: dict[str, Any], diagnostic: Mapping[str, Any]
) -> None:
    combined["trajectory_count"] += 1
    combined["verified_checkpoint_count"] += int(diagnostic["checkpoint_count"])
    combined["recomputed_horizon_count"] += int(
        diagnostic["recomputed_horizon_count"]
    )
    combined["maximum_tolerance"] = max(
        float(combined["maximum_tolerance"]),
        float(diagnostic["maximum_tolerance"]),
    )
    combined["maximum_raw_old_formula_error"] = max(
        float(combined["maximum_raw_old_formula_error"]),
        float(diagnostic["maximum_raw_old_formula_error"]),
    )
    for field, value in diagnostic["maximum_horizon_recomputation_error"].items():
        combined["maximum_horizon_recomputation_error"][field] = max(
            float(combined["maximum_horizon_recomputation_error"][field]),
            float(value),
        )
    for relation, values in diagnostic["comparisons"].items():
        destination = combined["comparisons"][relation]
        destination["minimum_slack"] = min(
            float(destination["minimum_slack"]), float(values["minimum_slack"])
        )
        destination["maximum_excess"] = max(
            float(destination["maximum_excess"]), float(values["maximum_excess"])
        )
        destination["maximum_tolerance_adjusted_excess"] = max(
            float(destination["maximum_tolerance_adjusted_excess"]),
            float(values["maximum_tolerance_adjusted_excess"]),
        )


def build_bound_reanalysis(
    config: dict[str, Any],
    *,
    profile: str,
    raw_root: Path,
    selection_path: Path,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Reanalyze retained evaluation trajectories without rerunning policies."""

    validate_study_config(config)
    selected, inputs = _load_selection(selection_path, config, profile)
    seeds = get_seed_set(config, "evaluation")
    horizons = tuple(int(horizon) for horizon in config["horizons"])
    resamples = int(config["bootstrap_resamples"])
    methods = tuple(str(method) for method in config["methods"])
    comparison_names = (
        "gamma_exact_le_gamma_split",
        "gamma_split_le_gamma_tail_old",
        "gamma_split_le_gamma_ambient_realized_trace",
        "gamma_ambient_realized_trace_le_gamma_ambient_worst_case",
    )
    verification: dict[str, Any] = {
        "status": "passed",
        "tolerance": {
            "formula": (
                "4096 * float64_epsilon * ambient_dimension * "
                "max(1, absolute compared values)"
            ),
            "multiplier": BOUND_TOLERANCE_MULTIPLIER,
            "float64_epsilon": float(np.finfo(np.float64).eps),
            "maximum_tolerance": 0.0,
        },
        "guaranteed_orderings_checked": [
            "gamma_exact <= gamma_split <= gamma_tail_old",
            "gamma_exact <= gamma_split <= gamma_ambient_realized_trace "
            "<= gamma_ambient_worst_case",
        ],
        "pairs_deliberately_not_ordered": [
            "gamma_tail_old versus gamma_ambient_realized_trace",
            "gamma_tail_old versus gamma_ambient_worst_case",
        ],
        "trajectory_count": 0,
        "verified_checkpoint_count": 0,
        "recomputed_horizon_count": 0,
        "maximum_tolerance": 0.0,
        "maximum_raw_old_formula_error": 0.0,
        "maximum_horizon_recomputation_error": {
            "gamma_exact": 0.0,
            "spectral_tail": 0.0,
        },
        "comparisons": {
            relation: {
                "minimum_slack": float("inf"),
                "maximum_excess": -float("inf"),
                "maximum_tolerance_adjusted_excess": -float("inf"),
            }
            for relation in comparison_names
        },
    }
    groups: list[dict[str, Any]] = []

    for cell in _cells(config):
        for method in methods:
            bound_runs: dict[str, list[FloatArray]] = {
                field: [] for field in (*BOUND_FIELDS, "spectral_tail")
            }
            bonus = selected[method]
            for seed in seeds:
                directory = _run_directory(
                    raw_root, profile, seed, cell, method, bonus
                )
                _, arrays, run_inputs = _load_run(
                    directory,
                    config=config,
                    profile=profile,
                    seed=seed,
                    cell=cell,
                    method=method,
                    bonus=bonus,
                )
                bounds, diagnostic = _reanalyze_trajectory_bounds(
                    arrays, config, tail_rank=cell.rank
                )
                for field in bound_runs:
                    bound_runs[field].append(bounds[field])
                _update_reanalysis_verification(verification, diagnostic)
                inputs.extend(run_inputs)

            record: dict[str, Any] = {
                "cell": {
                    "rank": cell.rank,
                    "spectral_power": cell.spectral_power,
                    "alignment": cell.alignment,
                },
                "method": method,
                "selected_bonus_from_frozen_tuning": bonus,
                "run_count": len(seeds),
            }
            for field, runs in bound_runs.items():
                record[field] = _stats_by_horizon(
                    np.stack(runs),
                    horizons,
                    resamples=resamples,
                    seed_parts=(
                        profile,
                        cell.token,
                        method,
                        "bound_reanalysis",
                        field,
                    ),
                )
            groups.append(record)

    verification["tolerance"]["maximum_tolerance"] = verification.pop(
        "maximum_tolerance"
    )
    normalized_inputs = sorted(inputs, key=lambda item: item["path"])
    aggregate = {
        "schema_version": 1,
        "experiment": "spectral_tail_bound_reanalysis",
        "source_experiment": "spectral_tail_study",
        "analysis_only": True,
        "policies_rerun": False,
        "hyperparameters_reselected": False,
        "profile": profile,
        "config_digest": config_digest(config),
        "config": config,
        "selection": selected,
        "evaluation_seeds": list(seeds),
        "evaluation_seed_count": len(seeds),
        "interval": (
            "trajectory-level percentile bootstrap over the retained evaluation "
            "seeds; the frozen tuning selection is read but not recomputed"
        ),
        "bound_definitions": {
            "gamma_exact": "sum_i log(1 + nu_i/lambda)",
            "gamma_split": (
                "r_t log(1 + head_mass/(r_t lambda)) + "
                "q_t,r log(1 + tail_mass/(q_t,r lambda))"
            ),
            "gamma_tail_old": (
                "r_t log(1 + t G^2/(r_t lambda sigma^2)) + "
                "tail_mass/lambda"
            ),
            "gamma_ambient_realized_trace": (
                "d_t log(1 + realized_trace/(d_t lambda))"
            ),
            "gamma_ambient_worst_case": (
                "d_t log(1 + t G^2/(d_t lambda sigma^2))"
            ),
        },
        "verification": verification,
        "groups": groups,
        "raw_inputs": normalized_inputs,
        "input_set_sha256": input_set_sha256(normalized_inputs),
    }
    return aggregate, normalized_inputs


def _group_index(
    report: Mapping[str, Any],
) -> dict[tuple[int, int, str, str], Mapping[str, Any]]:
    result = {}
    for group in report["groups"]:
        cell = group["cell"]
        key = (
            int(cell["rank"]),
            int(cell["spectral_power"]),
            str(cell["alignment"]),
            str(group["method"]),
        )
        if key in result:
            raise SpectralTailArtifactError(f"duplicate aggregate group {key}")
        result[key] = group
    return result


def _interval_arrays(
    records: Sequence[Mapping[str, Any]],
) -> tuple[FloatArray, FloatArray, FloatArray]:
    means = np.asarray([record["interval"]["mean"] for record in records])
    lows = np.asarray([record["interval"]["ci95_low"] for record in records])
    highs = np.asarray([record["interval"]["ci95_high"] for record in records])
    return means, lows, highs


def make_regret_figure(report: Mapping[str, Any], output: Path) -> None:
    import matplotlib
    import matplotlib.pyplot as plt

    matplotlib.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})

    config = report["config"]
    rank = int(config["figure_rank"])
    methods = tuple(str(method) for method in config["figure_methods"])
    powers = tuple(int(power) for power in config["spectral_powers"])
    alignments = tuple(str(alignment) for alignment in config["gap_alignments"])
    horizons = np.asarray(config["horizons"], dtype=np.float64)
    groups = _group_index(report)
    figure, axes = plt.subplots(
        len(alignments),
        len(powers),
        figsize=(10.2, 5.4),
        sharex=True,
        sharey=True,
    )
    axes_array = np.atleast_2d(axes)
    for row, alignment in enumerate(alignments):
        for column, power in enumerate(powers):
            axis = axes_array[row, column]
            for method in methods:
                group = groups[(rank, power, alignment, method)]
                means, lows, highs = _interval_arrays(group["regret"])
                axis.plot(
                    horizons,
                    means,
                    color=METHOD_COLORS[method],
                    linewidth=1.6,
                    label=METHOD_LABELS[method],
                )
                axis.fill_between(
                    horizons,
                    lows,
                    highs,
                    color=METHOD_COLORS[method],
                    alpha=0.12,
                    linewidth=0,
                )
            axis.set_xscale("log", base=2)
            axis.set_yscale("symlog", linthresh=0.05)
            axis.grid(alpha=0.2, linewidth=0.5)
            axis.set_title(f"$p={power}$, {alignment}-aligned", fontsize=9)
            if column == 0:
                axis.set_ylabel("Cumulative pseudo-regret")
            if row == len(alignments) - 1:
                axis.set_xlabel("Horizon")
    handles, labels = axes_array[0, 0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.91),
        ncol=4,
        frameon=False,
        fontsize=8,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.86))
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(figure)
    write_sha256_sidecar(output)


def make_complexity_figure(report: Mapping[str, Any], output: Path) -> None:
    import matplotlib
    import matplotlib.pyplot as plt

    matplotlib.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})

    config = report["config"]
    rank = int(config["figure_rank"])
    groups = _group_index(report)
    figure, axes = plt.subplots(1, 2, figsize=(7.0, 3.0))
    markers = {"head": "o", "tail": "s"}
    colors = {0: "#777777", 1: "#2474B5", 2: "#C43C39"}
    for power in config["spectral_powers"]:
        for alignment in config["gap_alignments"]:
            group = groups[(rank, int(power), str(alignment), "exact_dense_full")]
            gamma = float(group["gamma"]["mean"])
            gamma_tail = float(group["gamma_tail"]["mean"])
            tail = float(group["spectral_tail"]["mean"])
            axes[0].scatter(
                gamma,
                gamma_tail,
                marker=markers[str(alignment)],
                color=colors[int(power)],
                s=38,
                label=f"p={power}, {alignment}",
            )
            axes[1].scatter(
                tail,
                gamma_tail / max(gamma, 1e-15),
                marker=markers[str(alignment)],
                color=colors[int(power)],
                s=38,
            )
    maximum = max(axes[0].get_xlim()[1], axes[0].get_ylim()[1])
    axes[0].plot(
        [0, maximum],
        [0, maximum],
        color="#222222",
        linestyle="--",
        linewidth=0.8,
    )
    axes[0].set_xlabel(r"Realized $\gamma_T$")
    axes[0].set_ylabel(r"Tail bound $\Gamma_{\rm tail}$")
    axes[1].set_xlabel(r"Tail mass $\Delta_{T,r}$")
    axes[1].set_ylabel(r"$\Gamma_{\rm tail}/\gamma_T$")
    for axis in axes:
        axis.grid(alpha=0.2, linewidth=0.5)
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper center",
        ncol=3,
        frameon=False,
        fontsize=8,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.86))
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(figure)
    write_sha256_sidecar(output)


def make_decision_figure(report: Mapping[str, Any], output: Path) -> None:
    import matplotlib
    import matplotlib.pyplot as plt

    matplotlib.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})

    groups = _group_index(report)
    paired = {
        (
            int(item["cell"]["rank"]),
            int(item["cell"]["spectral_power"]),
            str(item["cell"]["alignment"]),
            str(item["method"]),
        ): item
        for item in report["paired_terminal"]
    }
    figure, axes = plt.subplots(1, 2, figsize=(7.0, 3.0))
    for rank in report["config"]["target_ranks"]:
        for power in report["config"]["spectral_powers"]:
            for alignment in report["config"]["gap_alignments"]:
                key = (int(rank), int(power), str(alignment), "rank_truncation")
                group = groups[key]
                difference = paired[key]
                x = float(group["tail_alignment"]["mean"])
                axes[0].scatter(
                    x,
                    float(group["action_disagreement"]["mean"]),
                    color=METHOD_COLORS["rank_truncation"],
                    alpha=0.75,
                    s=24,
                )
                axes[1].scatter(
                    x,
                    float(difference["terminal_regret_minus_exact"]["mean"]),
                    color=METHOD_COLORS["rank_truncation"],
                    alpha=0.75,
                    s=24,
                )
    axes[0].set_xlabel("Decision-margin tail alignment")
    axes[0].set_ylabel("Top-action disagreement")
    axes[1].set_xlabel("Decision-margin tail alignment")
    axes[1].set_ylabel("Rank truncation regret minus full")
    axes[1].axhline(0.0, color="#222222", linewidth=0.8, linestyle="--")
    for axis in axes:
        axis.grid(alpha=0.2, linewidth=0.5)
    figure.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(figure)
    write_sha256_sidecar(output)


def make_table(report: Mapping[str, Any], output: Path) -> None:
    groups = _group_index(report)
    rank = int(report["config"]["figure_rank"])
    methods = tuple(str(method) for method in report["config"]["figure_methods"])
    lines = [
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Regime & Method & Regret & $\gamma_T$ & $\Gamma_{\rm tail}$ & Disagree \\",
        r"\midrule",
    ]
    for power in report["config"]["spectral_powers"]:
        for alignment in report["config"]["gap_alignments"]:
            for method in methods:
                group = groups[(rank, int(power), str(alignment), method)]
                regret = group["regret"][-1]["interval"]
                lines.append(
                    f"$p={power}$, {alignment} & {METHOD_LABELS[method]} & "
                    f"{regret['mean']:.3f} & {group['gamma']['mean']:.2f} & "
                    f"{group['gamma_tail']['mean']:.2f} & "
                    f"{group['action_disagreement']['mean']:.3f} \\\\"
                )
            lines.append(r"\addlinespace")
    lines.extend((r"\bottomrule", r"\end{tabular}"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="ascii")
    write_sha256_sidecar(output)


def make_bound_reanalysis_figure(report: Mapping[str, Any], output: Path) -> None:
    import matplotlib
    import matplotlib.pyplot as plt

    matplotlib.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})

    config = report["config"]
    rank = int(config["figure_rank"])
    powers = tuple(int(power) for power in config["spectral_powers"])
    alignments = tuple(str(alignment) for alignment in config["gap_alignments"])
    horizons = np.asarray(config["horizons"], dtype=np.float64)
    groups = _group_index(report)
    figure, axes = plt.subplots(
        len(alignments),
        len(powers),
        figsize=(10.2, 5.4),
        sharex=True,
        sharey=True,
    )
    axes_array = np.atleast_2d(axes)
    for row, alignment in enumerate(alignments):
        for column, power in enumerate(powers):
            axis = axes_array[row, column]
            group = groups[(rank, power, alignment, "exact_dense_full")]
            for field in BOUND_PLOT_ORDER:
                means, _, _ = _interval_arrays(group[field])
                axis.plot(
                    horizons,
                    means,
                    color=BOUND_COLORS[field],
                    linestyle=BOUND_LINESTYLES[field],
                    linewidth=1.45,
                    marker=BOUND_MARKERS[field],
                    markersize=3.0,
                    label=BOUND_LABELS[field],
                )
            axis.set_xscale("log", base=2)
            axis.set_yscale("log")
            axis.grid(alpha=0.2, linewidth=0.5)
            axis.set_title(f"$p={power}$, {alignment}-aligned", fontsize=9)
            if column == 0:
                axis.set_ylabel("Information complexity")
            if row == len(alignments) - 1:
                axis.set_xlabel("Horizon")
    handles, labels = axes_array[0, 0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.91),
        ncol=3,
        frameon=False,
        fontsize=7.5,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.85))
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(figure)
    write_sha256_sidecar(output)


def _terminal_mean(group: Mapping[str, Any], field: str) -> float:
    return float(group[field][-1]["interval"]["mean"])


def make_bound_reanalysis_table(report: Mapping[str, Any], output: Path) -> None:
    groups = _group_index(report)
    rank = int(report["config"]["figure_rank"])
    lines = [
        r"\begin{tabular}{llrrrrr}",
        r"\toprule",
        (
            r"Regime & Alignment & $\gamma_T$ & $\Gamma_{\rm split}$ & "
            r"$\Gamma_{\rm tail}$ & $\Gamma_{\rm amb,real}$ & "
            r"$\Gamma_{\rm amb,wc}$ \\"
        ),
        r"\midrule",
    ]
    for power in report["config"]["spectral_powers"]:
        for alignment in report["config"]["gap_alignments"]:
            group = groups[
                (rank, int(power), str(alignment), "exact_dense_full")
            ]
            lines.append(
                f"$p={power}$ & {alignment} & "
                f"{_terminal_mean(group, 'gamma_exact'):.2f} & "
                f"{_terminal_mean(group, 'gamma_split'):.2f} & "
                f"{_terminal_mean(group, 'gamma_tail_old'):.2f} & "
                f"{_terminal_mean(group, 'gamma_ambient_realized_trace'):.2f} & "
                f"{_terminal_mean(group, 'gamma_ambient_worst_case'):.2f} \\\\"
            )
        lines.append(r"\addlinespace")
    lines.extend((r"\bottomrule", r"\end{tabular}"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="ascii")
    write_sha256_sidecar(output)


def _write_provenance(
    artifact: Path,
    *,
    inputs: Sequence[Mapping[str, str]],
    config: Mapping[str, Any],
    artifact_kind: str | None = None,
) -> None:
    sidecar = artifact.with_name(artifact.name + ".provenance.json")
    generation_parameters = {
        "experiment": "spectral_tail_study",
        "config_digest": config_digest(config),
    }
    if artifact_kind is not None:
        generation_parameters["artifact_kind"] = artifact_kind
    write_json_artifact(
        sidecar,
        {
            "schema_version": 1,
            "artifact": artifact.as_posix(),
            "artifact_sha256": sha256_file(artifact),
            "input_set_sha256": input_set_sha256(inputs),
            "inputs": list(inputs),
            "generation_parameters": generation_parameters,
        },
    )


def make_artifacts(
    config: dict[str, Any],
    *,
    profile: str,
    raw_root: Path,
    selection_path: Path,
    aggregate_path: Path,
    regret_figure: Path,
    complexity_figure: Path,
    decision_figure: Path,
    table_path: Path,
) -> dict[str, Any]:
    aggregate, inputs = build_aggregate(
        config,
        profile=profile,
        raw_root=raw_root,
        selection_path=selection_path,
    )
    write_json_artifact(aggregate_path, aggregate)
    aggregate_sidecar = aggregate_path.with_name(aggregate_path.name + ".sha256")
    aggregate_inputs = [
        {"path": aggregate_path.as_posix(), "sha256": sha256_file(aggregate_path)},
        {
            "path": aggregate_sidecar.as_posix(),
            "sha256": sha256_file(aggregate_sidecar),
        },
    ]
    make_regret_figure(aggregate, regret_figure)
    make_complexity_figure(aggregate, complexity_figure)
    make_decision_figure(aggregate, decision_figure)
    make_table(aggregate, table_path)
    for artifact in (regret_figure, complexity_figure, decision_figure, table_path):
        _write_provenance(artifact, inputs=aggregate_inputs, config=config)
    return {
        "profile": profile,
        "aggregate": aggregate_path.as_posix(),
        "input_set_sha256": aggregate["input_set_sha256"],
        "artifacts": [
            regret_figure.as_posix(),
            complexity_figure.as_posix(),
            decision_figure.as_posix(),
            table_path.as_posix(),
        ],
        "raw_input_count": len(inputs),
    }


def make_bound_reanalysis_artifacts(
    config: dict[str, Any],
    *,
    profile: str,
    raw_root: Path,
    selection_path: Path,
    aggregate_path: Path,
    figure_path: Path,
    table_path: Path,
) -> dict[str, Any]:
    aggregate, inputs = build_bound_reanalysis(
        config,
        profile=profile,
        raw_root=raw_root,
        selection_path=selection_path,
    )
    write_json_artifact(aggregate_path, aggregate)
    aggregate_sidecar = aggregate_path.with_name(aggregate_path.name + ".sha256")
    aggregate_inputs = [
        {"path": aggregate_path.as_posix(), "sha256": sha256_file(aggregate_path)},
        {"path": aggregate_sidecar.as_posix(), "sha256": sha256_file(aggregate_sidecar)},
    ]
    make_bound_reanalysis_figure(aggregate, figure_path)
    make_bound_reanalysis_table(aggregate, table_path)
    for artifact in (figure_path, table_path):
        _write_provenance(
            artifact,
            inputs=aggregate_inputs,
            config=config,
            artifact_kind="bound_reanalysis",
        )
    return {
        "profile": profile,
        "analysis_only": True,
        "policies_rerun": False,
        "hyperparameters_reselected": False,
        "aggregate": aggregate_path.as_posix(),
        "input_set_sha256": aggregate["input_set_sha256"],
        "artifacts": [figure_path.as_posix(), table_path.as_posix()],
        "raw_input_count": len(inputs),
        "verification": aggregate["verification"],
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--aggregate", type=Path)
    parser.add_argument("--regret-figure", type=Path)
    parser.add_argument("--complexity-figure", type=Path)
    parser.add_argument("--decision-figure", type=Path)
    parser.add_argument("--table", type=Path)
    parser.add_argument("--bound-reanalysis", action="store_true")
    parser.add_argument("--bound-aggregate", type=Path)
    parser.add_argument("--bound-figure", type=Path)
    parser.add_argument("--bound-table", type=Path)
    args = parser.parse_args()
    config = load_config(args.config, profile=args.profile)
    if args.bound_reanalysis:
        required = {
            "--bound-aggregate": args.bound_aggregate,
            "--bound-figure": args.bound_figure,
            "--bound-table": args.bound_table,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            parser.error(
                "bound reanalysis requires " + ", ".join(sorted(missing))
            )
        result = make_bound_reanalysis_artifacts(
            config,
            profile=args.profile,
            raw_root=args.raw_root,
            selection_path=args.selection,
            aggregate_path=args.bound_aggregate,
            figure_path=args.bound_figure,
            table_path=args.bound_table,
        )
    else:
        required = {
            "--aggregate": args.aggregate,
            "--regret-figure": args.regret_figure,
            "--complexity-figure": args.complexity_figure,
            "--decision-figure": args.decision_figure,
            "--table": args.table,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            parser.error(
                "legacy artifact generation requires "
                + ", ".join(sorted(missing))
            )
        result = make_artifacts(
            config,
            profile=args.profile,
            raw_root=args.raw_root,
            selection_path=args.selection,
            aggregate_path=args.aggregate,
            regret_figure=args.regret_figure,
            complexity_figure=args.complexity_figure,
            decision_figure=args.decision_figure,
            table_path=args.table,
        )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = ["build_aggregate", "make_artifacts"]
