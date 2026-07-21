"""Load and resolve versioned experiment configurations.

The checked-in ``.yaml`` files deliberately use JSON syntax. JSON is a strict
subset of YAML, so the standard library is sufficient in a clean environment.
If a user supplies non-JSON YAML, PyYAML is used when it is installed.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when a configuration cannot be parsed or validated."""


def _load_document(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc

    try:
        document = json.loads(text)
    except json.JSONDecodeError as json_exc:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ConfigError(
                f"{path} is not JSON-compatible YAML; install PyYAML to parse "
                "general YAML"
            ) from json_exc
        try:
            document = yaml.safe_load(text)
        except yaml.YAMLError as exc:  # type: ignore[attr-defined]
            raise ConfigError(f"cannot parse config {path}: {exc}") from exc

    if not isinstance(document, dict):
        raise ConfigError(f"config {path} must contain a top-level object")
    return document


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_seed_sets(config: Mapping[str, Any], context: str) -> None:
    seed_sets = config.get("seed_sets")
    if not isinstance(seed_sets, Mapping):
        raise ConfigError(f"{context}.seed_sets must be an object")

    parsed: dict[str, set[int]] = {}
    required_names = ("tuning", "evaluation")
    optional_names = ("development",)
    for name in (*optional_names, *required_names):
        seeds = seed_sets.get(name)
        if name in optional_names and seeds is None:
            continue
        if not isinstance(seeds, Sequence) or isinstance(seeds, (str, bytes)):
            raise ConfigError(f"{context}.seed_sets.{name} must be a list")
        if not seeds:
            raise ConfigError(f"{context}.seed_sets.{name} must not be empty")
        if any(not _is_int(seed) or seed < 0 for seed in seeds):
            raise ConfigError(
                f"{context}.seed_sets.{name} must contain non-negative integers"
            )
        if len(set(seeds)) != len(seeds):
            raise ConfigError(f"{context}.seed_sets.{name} contains duplicates")
        parsed[name] = set(seeds)

    names = tuple(parsed)
    for left_index, left_name in enumerate(names):
        for right_name in names[left_index + 1 :]:
            overlap = parsed[left_name] & parsed[right_name]
            if overlap:
                raise ConfigError(
                    f"{context} {left_name}/{right_name} seeds overlap: "
                    f"{sorted(overlap)}"
                )


def validate_config(config: Mapping[str, Any]) -> None:
    """Validate the unresolved, versioned configuration document."""

    if config.get("schema_version") != 1:
        raise ConfigError("schema_version must be 1")
    if not isinstance(config.get("name"), str) or not config["name"].strip():
        raise ConfigError("name must be a non-empty string")
    if not isinstance(config.get("description"), str):
        raise ConfigError("description must be a string")
    if not isinstance(config.get("base"), Mapping):
        raise ConfigError("base must be an object")

    profiles = config.get("profiles")
    if not isinstance(profiles, Mapping):
        raise ConfigError("profiles must be an object")
    missing = {"smoke", "full"} - set(profiles)
    if missing:
        raise ConfigError(f"missing required profiles: {sorted(missing)}")
    for name, profile in profiles.items():
        if not isinstance(profile, Mapping):
            raise ConfigError(f"profiles.{name} must be an object")

    # Validate seeds after inheritance, because profiles intentionally own them.
    for profile_name in profiles:
        resolved = resolve_config(config, profile_name, validate=False)
        _validate_seed_sets(resolved, f"profiles.{profile_name}")
        horizon = resolved.get("rounds")
        if not _is_int(horizon) or horizon <= 0:
            raise ConfigError(
                f"profiles.{profile_name}.rounds must resolve to a positive integer"
            )


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def resolve_config(
    config: Mapping[str, Any], profile: str, *, validate: bool = True
) -> dict[str, Any]:
    """Resolve ``base`` plus a named profile without mutating the input."""

    if validate:
        validate_config(config)
    profiles = config.get("profiles")
    if not isinstance(profiles, Mapping) or profile not in profiles:
        available = sorted(profiles) if isinstance(profiles, Mapping) else []
        raise ConfigError(f"unknown profile {profile!r}; choose from {available}")

    header = {
        key: copy.deepcopy(value)
        for key, value in config.items()
        if key not in {"base", "profiles"}
    }
    resolved = _deep_merge(header, config["base"])
    resolved = _deep_merge(resolved, profiles[profile])
    resolved["profile"] = profile
    return resolved


def load_config(path: str | Path, profile: str | None = None) -> dict[str, Any]:
    """Load a config, optionally resolving a ``smoke`` or ``full`` profile."""

    document = _load_document(Path(path))
    validate_config(document)
    if profile is None:
        return copy.deepcopy(document)
    return resolve_config(document, profile)


def get_seed_set(config: Mapping[str, Any], name: str) -> tuple[int, ...]:
    """Return one validated seed split from a resolved configuration."""

    _validate_seed_sets(config, "config")
    if name not in {"development", "tuning", "evaluation"}:
        raise ConfigError("seed set must be 'development', 'tuning', or 'evaluation'")
    if name not in config["seed_sets"]:
        raise ConfigError(f"seed set {name!r} is not declared by this configuration")
    return tuple(config["seed_sets"][name])


def config_digest(config: Mapping[str, Any], length: int | None = None) -> str:
    """Return a stable SHA-256 digest of a JSON-compatible config."""

    try:
        payload = json.dumps(
            config,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"config is not strict JSON: {exc}") from exc
    digest = hashlib.sha256(payload).hexdigest()
    return digest if length is None else digest[:length]


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and resolve an experiment config")
    parser.add_argument("config", type=Path)
    parser.add_argument("--profile", choices=("smoke", "full"), required=True)
    parser.add_argument(
        "--seed-set", choices=("development", "tuning", "evaluation"), required=True
    )
    parser.add_argument(
        "--print", dest="print_config", action="store_true", help="print resolved JSON"
    )
    args = parser.parse_args(argv)

    resolved = load_config(args.config, profile=args.profile)
    seeds = get_seed_set(resolved, args.seed_set)
    if args.print_config:
        print(json.dumps(resolved, indent=2, sort_keys=True, allow_nan=False))
    print(
        f"valid name={resolved['name']} profile={args.profile} "
        f"seed_set={args.seed_set} seeds={list(seeds)} "
        f"digest={config_digest(resolved, 12)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
