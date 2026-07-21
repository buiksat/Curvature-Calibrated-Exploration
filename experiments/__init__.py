"""Reproducible experiment configuration and logging helpers."""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "ConfigError",
    "ExperimentLogger",
    "config_digest",
    "derive_seed",
    "get_seed_set",
    "load_config",
    "resolve_config",
    "seed_everything",
]


def __getattr__(name: str):
    if name in {"ConfigError", "config_digest", "get_seed_set", "load_config", "resolve_config"}:
        return getattr(import_module(".config", __name__), name)
    if name in {"ExperimentLogger", "derive_seed", "seed_everything"}:
        return getattr(import_module(".logging_utils", __name__), name)
    raise AttributeError(name)
