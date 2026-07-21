"""Run the leakage-free linear tuning and evaluation study.

The low-level policy implementation lives in :mod:`run_linear_audit`.  This
module only orchestrates the two-stage protocol: tune on the declared tuning
seeds at ``tuning_rounds``, then construct fresh policies on the disjoint
evaluation seeds at the configured full horizon.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .config import config_digest, get_seed_set, load_config
from .logging_utils import canonical_json
from .run_linear_audit import (
    AuditRun,
    configured_methods,
    run_method,
    save_run,
)


DEFAULT_CONFIG_PATH = Path(__file__).with_name("configs") / "linear_audit.yaml"


class LinearStudyError(RuntimeError):
    """Raised when the study protocol cannot be completed validly."""


def _finite_float(value: Any, *, name: str, minimum: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise LinearStudyError(f"{name} must be numeric") from exc
    if not (result >= minimum and result < float("inf")):
        raise LinearStudyError(f"{name} must be finite and at least {minimum}")
    return result


def tuning_grid(config: Mapping[str, Any]) -> tuple[dict[str, float], ...]:
    """Return the configured Cartesian grid in deterministic order."""

    grid = config.get("tuning_grid")
    if not isinstance(grid, Mapping):
        raise LinearStudyError("tuning_grid must be an object")
    ridges = grid.get("ridge")
    bonuses = grid.get("bonus_scale")
    if (
        not isinstance(ridges, Sequence)
        or isinstance(ridges, (str, bytes))
        or not ridges
        or not isinstance(bonuses, Sequence)
        or isinstance(bonuses, (str, bytes))
        or not bonuses
    ):
        raise LinearStudyError("tuning_grid.ridge and bonus_scale must be nonempty lists")
    checked_ridges = tuple(
        _finite_float(value, name="tuning ridge", minimum=1e-300) for value in ridges
    )
    checked_bonuses = tuple(
        _finite_float(value, name="tuning bonus_scale", minimum=1.0)
        for value in bonuses
    )
    if len(set(checked_ridges)) != len(checked_ridges):
        raise LinearStudyError("tuning_grid.ridge contains duplicates")
    if len(set(checked_bonuses)) != len(checked_bonuses):
        raise LinearStudyError("tuning_grid.bonus_scale contains duplicates")
    return tuple(
        {"ridge": ridge, "bonus_scale": bonus}
        for ridge, bonus in itertools.product(checked_ridges, checked_bonuses)
    )


def _with_hyperparameters(
    config: Mapping[str, Any], *, ridge: float, bonus_scale: float, rounds: int
) -> dict[str, Any]:
    resolved = copy.deepcopy(dict(config))
    resolved["rounds"] = int(rounds)
    resolved["ridge"] = float(ridge)
    # ``run_linear_audit`` accepts both locations.  Keeping them synchronized
    # makes the actual policy unambiguous in the persisted manifest.
    resolved["bonus_scale"] = float(bonus_scale)
    confidence = resolved.get("confidence")
    resolved["confidence"] = (
        copy.deepcopy(dict(confidence)) if isinstance(confidence, Mapping) else {}
    )
    resolved["confidence"]["bonus_scale"] = float(bonus_scale)
    return resolved


def _first_boolean(summary: Mapping[str, Any], names: Sequence[str]) -> bool | None:
    for name in names:
        if name in summary:
            return summary[name] is True
    return None


def tuning_run_is_valid(summary: Mapping[str, Any]) -> bool:
    """Require an executed policy and realized confidence/certificate validity."""

    confidence_valid = _first_boolean(
        summary,
        (
            "confidence_event_realized",
            "realized_confidence_valid",
            "confidence_valid",
        ),
    )
    certificate_valid = _first_boolean(
        summary,
        (
            "certified_execution",
            "certificate_valid",
            "policy_used_predictable_valid_certificates",
        ),
    )
    predictable_valid = summary.get(
        "policy_used_predictable_valid_certificates", certificate_valid
    )
    return (
        summary.get("executed_policy") is True
        and confidence_valid is True
        and certificate_valid is True
        and predictable_valid is True
    )


def _candidate_identifier(index: int) -> str:
    return f"candidate-{index:03d}"


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise LinearStudyError("cannot average an empty candidate")
    return float(sum(values) / len(values))


def _atomic_json(path: Path, value: Mapping[str, Any], *, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite {path}")
    payload = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
        "utf-8"
    )
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _study_metadata(
    config: Mapping[str, Any],
    *,
    phase: str,
    comparison: str,
    hyperparameters: Mapping[str, float],
    tuning_seeds: Sequence[int],
    evaluation_seeds: Sequence[int],
    tuning_rounds: int,
    evaluation_rounds: int,
    selection_sha256: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "schema_version": 1,
        "phase": phase,
        "seed_set": phase,
        "comparison": comparison,
        "hyperparameters": dict(hyperparameters),
        "tuning_seeds": list(tuning_seeds),
        "evaluation_seeds": list(evaluation_seeds),
        "tuning_rounds": tuning_rounds,
        "evaluation_rounds": evaluation_rounds,
        "base_config_digest": config_digest(config),
        "fresh_policy_initialization": True,
    }
    if selection_sha256 is not None:
        metadata["selection_sha256"] = selection_sha256
    return metadata


def _call_runner(
    runner: Callable[..., AuditRun],
    config: Mapping[str, Any],
    method: str,
    seed: int,
) -> AuditRun:
    return runner(config, method, seed, retain_matrices=False)


def _call_saver(
    saver: Callable[..., Path],
    run: AuditRun,
    destination: Path,
    config: Mapping[str, Any],
    *,
    overwrite: bool,
) -> Path:
    return saver(run, destination, config, overwrite=overwrite)


def run_linear_study(
    config: Mapping[str, Any],
    output_root: str | Path,
    *,
    overwrite: bool = False,
    runner: Callable[..., AuditRun] = run_method,
    saver: Callable[..., Path] = save_run,
) -> dict[str, Any]:
    """Execute tuning and fresh evaluation runs, returning the selection record."""

    resolved = copy.deepcopy(dict(config))
    profile = str(resolved.get("profile", "full"))
    tuning_seeds = get_seed_set(resolved, "tuning")
    evaluation_seeds = get_seed_set(resolved, "evaluation")
    if set(tuning_seeds) & set(evaluation_seeds):
        raise LinearStudyError("tuning and evaluation seeds must be disjoint")
    methods = configured_methods(resolved)
    if not methods:
        raise LinearStudyError("the study has no enabled methods")
    evaluation_rounds = int(resolved.get("rounds", 0))
    tuning_rounds = int(resolved.get("tuning_rounds", 0))
    if evaluation_rounds <= 0 or tuning_rounds <= 0:
        raise LinearStudyError("rounds and tuning_rounds must be positive")
    candidates = tuning_grid(resolved)
    root = Path(output_root) / profile

    candidate_scores: dict[str, list[dict[str, Any]]] = {method: [] for method in methods}
    selected: dict[str, dict[str, Any]] = {}
    tuning_run_count = 0
    for method in methods:
        for candidate_index, hyperparameters in enumerate(candidates):
            candidate_id = _candidate_identifier(candidate_index)
            tuning_config = _with_hyperparameters(
                resolved,
                ridge=hyperparameters["ridge"],
                bonus_scale=hyperparameters["bonus_scale"],
                rounds=tuning_rounds,
            )
            tuning_config["study"] = _study_metadata(
                resolved,
                phase="tuning",
                comparison="validation_tuning",
                hyperparameters=hyperparameters,
                tuning_seeds=tuning_seeds,
                evaluation_seeds=evaluation_seeds,
                tuning_rounds=tuning_rounds,
                evaluation_rounds=evaluation_rounds,
            )
            regrets: list[float] = []
            valid_by_seed: dict[str, bool] = {}
            for seed in tuning_seeds:
                run = _call_runner(runner, tuning_config, method, seed)
                _call_saver(
                    saver,
                    run,
                    root
                    / "tuning"
                    / method
                    / candidate_id
                    / f"seed-{seed}",
                    tuning_config,
                    overwrite=overwrite,
                )
                tuning_run_count += 1
                valid = tuning_run_is_valid(run.summary)
                valid_by_seed[str(seed)] = valid
                regret = run.summary.get("cumulative_pseudo_regret")
                if not isinstance(regret, (int, float)) or isinstance(regret, bool):
                    raise LinearStudyError(
                        f"{method} candidate {candidate_id} seed {seed} has no numeric regret"
                    )
                regrets.append(float(regret))
            candidate_record = {
                "candidate_id": candidate_id,
                "hyperparameters": dict(hyperparameters),
                "mean_cumulative_pseudo_regret": _mean(regrets),
                "regret_by_seed": {
                    str(seed): regret for seed, regret in zip(tuning_seeds, regrets, strict=True)
                },
                "valid_by_seed": valid_by_seed,
                "eligible": all(valid_by_seed.values()),
            }
            candidate_scores[method].append(candidate_record)

        eligible = [record for record in candidate_scores[method] if record["eligible"]]
        if not eligible:
            raise LinearStudyError(
                f"no valid tuning setting for {method}: all settings failed realized "
                "confidence or certificate validity"
            )
        winner = min(
            eligible,
            key=lambda record: (
                record["mean_cumulative_pseudo_regret"],
                record["hyperparameters"]["ridge"],
                record["hyperparameters"]["bonus_scale"],
                record["candidate_id"],
            ),
        )
        selected[method] = {
            "candidate_id": winner["candidate_id"],
            "hyperparameters": winner["hyperparameters"],
            "mean_cumulative_pseudo_regret": winner[
                "mean_cumulative_pseudo_regret"
            ],
        }

    selection: dict[str, Any] = {
        "schema_version": 1,
        "event": "linear_study_selection",
        "experiment": str(resolved.get("name", "linear_audit")),
        "profile": profile,
        "base_config_digest": config_digest(resolved),
        "tuning_seed_set": list(tuning_seeds),
        "evaluation_seed_set": list(evaluation_seeds),
        "seed_sets_disjoint": True,
        "tuning_rounds": tuning_rounds,
        "evaluation_rounds": evaluation_rounds,
        "selection_metric": "mean_cumulative_pseudo_regret",
        "eligibility": (
            "executed policy with realized confidence and valid predictable certificates"
        ),
        "candidates": candidate_scores,
        "selected": selected,
    }
    selection_path = root / "selection.json"
    _atomic_json(selection_path, selection, overwrite=overwrite)
    selection_bytes = selection_path.read_bytes()
    selection_sha256 = hashlib.sha256(selection_bytes).hexdigest()

    confidence = resolved.get("confidence")
    fixed_bonus = (
        confidence.get("bonus_scale", 1.0)
        if isinstance(confidence, Mapping)
        else 1.0
    )
    fixed_hyperparameters = {
        "ridge": float(resolved.get("ridge", 1.0)),
        "bonus_scale": float(resolved.get("bonus_scale", fixed_bonus)),
    }
    evaluation_run_count = 0
    for method in methods:
        comparisons = (
            ("fixed_reference", fixed_hyperparameters),
            ("validation_tuned", selected[method]["hyperparameters"]),
        )
        for comparison, hyperparameters in comparisons:
            evaluation_config = _with_hyperparameters(
                resolved,
                ridge=float(hyperparameters["ridge"]),
                bonus_scale=float(hyperparameters["bonus_scale"]),
                rounds=evaluation_rounds,
            )
            evaluation_config["study"] = _study_metadata(
                resolved,
                phase="evaluation",
                comparison=comparison,
                hyperparameters=hyperparameters,
                tuning_seeds=tuning_seeds,
                evaluation_seeds=evaluation_seeds,
                tuning_rounds=tuning_rounds,
                evaluation_rounds=evaluation_rounds,
                selection_sha256=selection_sha256,
            )
            for seed in evaluation_seeds:
                # This call is deliberately inside both loops: no fitted state,
                # history, or random generator is reused from tuning or another
                # comparison.
                run = _call_runner(runner, evaluation_config, method, seed)
                _call_saver(
                    saver,
                    run,
                    root / "evaluation" / comparison / method / f"seed-{seed}",
                    evaluation_config,
                    overwrite=overwrite,
                )
                evaluation_run_count += 1

    return {
        **selection,
        "selection_path": str(selection_path),
        "selection_sha256": selection_sha256,
        "tuning_run_count": tuning_run_count,
        "evaluation_run_count": evaluation_run_count,
    }


# Short alias for callers that already name the module in their imports.
run_study = run_linear_study


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--profile", choices=("smoke", "full"), default="full")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config, profile=args.profile)
    output_root = args.output_root or Path(
        str(config.get("output_root", "results/raw/linear_audit"))
    )
    result = run_linear_study(config, output_root, overwrite=args.overwrite)
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_CONFIG_PATH",
    "LinearStudyError",
    "run_linear_study",
    "run_study",
    "tuning_grid",
    "tuning_run_is_valid",
]
