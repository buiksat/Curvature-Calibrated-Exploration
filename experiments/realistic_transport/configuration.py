"""Configuration parsing and frozen-grid validation for the realistic benchmark."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RealisticConfigError(ValueError):
    """Raised when the preregistered benchmark configuration is invalid."""


EXPECTED_METHODS = (
    "transport_exact_corrected_cholesky",
    "transport_exact_corrected_cg_1e-4",
    "transport_endpoint_corrected_cholesky",
    "frozen_reference_corrected_cholesky",
    "naive_current_corrected_cholesky",
    "transport_exact_uncorrected_tangent_cholesky",
    "greedy_corrected",
    "linucb_fixed_features",
    "transport_nystrom_r16_cg_1e-2",
    "transport_nystrom_r16_cg_1e-6",
    "transport_nystrom_r64_cg_1e-2",
    "transport_nystrom_r64_cg_1e-6",
    "transport_nystrom_r32_cg_1e-4",
)

EXPECTED_TASKS = (
    "covtype_label_bandit",
    "covtype_semisynthetic_realizable",
    "covtype_semisynthetic_misspecified",
)

APPROXIMATE_METHODS = tuple(
    method for method in EXPECTED_METHODS if method.startswith("transport_nystrom_")
)


@dataclass(frozen=True)
class MethodSpec:
    name: str
    center: str
    metric: str
    solver: str
    transport: str
    rank: int | None = None
    cg_tolerance: float | None = None
    certified_method: bool = True


def method_spec(name: str) -> MethodSpec:
    if name not in EXPECTED_METHODS:
        raise RealisticConfigError(f"unknown method {name!r}")
    fixed = {
        "transport_exact_corrected_cholesky": MethodSpec(
            name, "corrected", "current_exact", "cholesky", "operational"
        ),
        "transport_exact_corrected_cg_1e-4": MethodSpec(
            name, "corrected", "current_exact", "cg", "operational", cg_tolerance=1e-4
        ),
        "transport_endpoint_corrected_cholesky": MethodSpec(
            name, "corrected", "current_exact", "cholesky", "endpoint_oracle"
        ),
        "frozen_reference_corrected_cholesky": MethodSpec(
            name, "corrected", "frozen", "cholesky", "reference"
        ),
        "naive_current_corrected_cholesky": MethodSpec(
            name,
            "corrected",
            "current_exact",
            "cholesky",
            "none",
            certified_method=False,
        ),
        "transport_exact_uncorrected_tangent_cholesky": MethodSpec(
            name,
            "tangent",
            "current_exact",
            "cholesky",
            "operational",
            certified_method=False,
        ),
        "greedy_corrected": MethodSpec(
            name, "corrected", "none", "none", "none", certified_method=False
        ),
        "linucb_fixed_features": MethodSpec(
            name, "linear", "frozen_static", "cholesky", "none"
        ),
    }
    if name in fixed:
        return fixed[name]
    match = re.fullmatch(r"transport_nystrom_r(\d+)_cg_(1e-\d+)", name)
    if match is None:
        raise RealisticConfigError(f"cannot parse method {name!r}")
    return MethodSpec(
        name=name,
        center="corrected",
        metric="nystrom",
        solver="cg",
        transport="operational",
        rank=int(match.group(1)),
        cg_tolerance=float(match.group(2)),
    )


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RealisticConfigError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                RealisticConfigError(f"non-finite JSON value {value}")
            ),
        )
    except (OSError, json.JSONDecodeError) as error:
        raise RealisticConfigError(
            f"cannot read configuration {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise RealisticConfigError("configuration must be a JSON object")
    return value


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def config_digest(config: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(config).encode("ascii")).hexdigest()


def _integer_sequence(value: Any, *, name: str) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise RealisticConfigError(f"{name} must be a list")
    result: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise RealisticConfigError(f"{name} must contain nonnegative integers")
        result.append(int(item))
    if not result or len(result) != len(set(result)):
        raise RealisticConfigError(f"{name} must be nonempty and unique")
    return tuple(result)


def validate_config(document: Mapping[str, Any]) -> None:
    if document.get("schema_version") != 1:
        raise RealisticConfigError("schema_version must be 1")
    if document.get("protocol_version") != "realistic-transport-covtype-v1":
        raise RealisticConfigError("unexpected protocol_version")
    base = document.get("base")
    profiles = document.get("profiles")
    if not isinstance(base, Mapping) or not isinstance(profiles, Mapping):
        raise RealisticConfigError("base and profiles must be objects")
    if tuple(base.get("methods", ())) != EXPECTED_METHODS:
        raise RealisticConfigError("method grid differs from the preregistered order")
    for method in EXPECTED_METHODS:
        method_spec(method)
    tasks = base.get("tasks")
    if not isinstance(tasks, Mapping) or tuple(tasks) != EXPECTED_TASKS:
        raise RealisticConfigError("task grid differs from the preregistered order")
    seed_sets = base.get("seed_sets")
    if not isinstance(seed_sets, Mapping):
        raise RealisticConfigError("seed_sets must be an object")
    parsed = {
        name: set(_integer_sequence(seed_sets.get(name), name=f"seed_sets.{name}"))
        for name in ("development", "tuning", "evaluation", "pilot")
    }
    names = tuple(parsed)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            overlap = parsed[left] & parsed[right]
            if overlap:
                raise RealisticConfigError(
                    f"seed sets {left}/{right} overlap: {sorted(overlap)}"
                )
    if parsed["development"] != {0, 1, 2}:
        raise RealisticConfigError("development seeds are not frozen")
    if parsed["tuning"] != set(range(10, 20)):
        raise RealisticConfigError("tuning seeds are not frozen")
    if parsed["evaluation"] != set(range(100, 130)):
        raise RealisticConfigError("evaluation seeds are not frozen")
    if parsed["pilot"] != set(range(200, 210)):
        raise RealisticConfigError("pilot seeds are not frozen")
    required_profiles = {"smoke", "covtype_pilot", "resource_fallback", "full"}
    if set(profiles) != required_profiles:
        raise RealisticConfigError("profile set differs from the preregistration")
    for name, profile in profiles.items():
        if not isinstance(profile, Mapping):
            raise RealisticConfigError(f"profiles.{name} must be an object")
        rounds = profile.get("rounds", base.get("horizons", {}).get("maximum"))
        if isinstance(rounds, bool) or not isinstance(rounds, int) or rounds <= 0:
            raise RealisticConfigError(f"profiles.{name}.rounds must be positive")
    model = base.get("model")
    if not isinstance(model, Mapping):
        raise RealisticConfigError("model must be an object")
    for field in ("theta_radius", "reference_norm_bound", "ridge", "training_ridge"):
        value = float(model.get(field, math.nan))
        if not math.isfinite(value) or value <= 0.0:
            raise RealisticConfigError(f"model.{field} must be positive")
    prefixes = base.get("horizons", {}).get("prefixes")
    if tuple(prefixes or ()) != (100, 250, 500):
        raise RealisticConfigError("reported prefixes must be [100, 250, 500]")


def load_config(path: str | Path, profile: str) -> dict[str, Any]:
    document = _load_json(Path(path))
    validate_config(document)
    profiles = document["profiles"]
    if profile not in profiles:
        raise RealisticConfigError(
            f"unknown profile {profile!r}; choose from {sorted(profiles)}"
        )
    header = {
        key: copy.deepcopy(value)
        for key, value in document.items()
        if key not in {"base", "profiles"}
    }
    resolved = _deep_merge(header, document["base"])
    resolved = _deep_merge(resolved, profiles[profile])
    resolved["profile"] = profile
    return resolved


def seed_set(config: Mapping[str, Any], name: str) -> tuple[int, ...]:
    sets = config.get("seed_sets")
    if not isinstance(sets, Mapping) or name not in sets:
        raise RealisticConfigError(f"unknown seed set {name!r}")
    return _integer_sequence(sets[name], name=f"seed_sets.{name}")


__all__ = [
    "APPROXIMATE_METHODS",
    "EXPECTED_METHODS",
    "EXPECTED_TASKS",
    "MethodSpec",
    "RealisticConfigError",
    "canonical_json",
    "config_digest",
    "load_config",
    "method_spec",
    "seed_set",
    "validate_config",
]
