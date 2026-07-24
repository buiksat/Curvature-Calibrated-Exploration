"""Strict config-wording compatibility for immutable scaled-tanh evidence."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from .config import config_digest


LEGACY_DESCRIPTION = (
    "Predeclared finite-support scaled-tanh theorem-instantiation study with "
    "exact full-history sufficient statistics and relative-link certificates."
)
CURRENT_DESCRIPTION = (
    "Fresh final holdout after two disclosed diagnostic splits: finite-support "
    "scaled-tanh theorem-instantiation study with exact full-history sufficient "
    "statistics and relative-link certificates."
)


def resolve_execution_config(
    current_config: Mapping[str, Any], recorded_digest: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve the exact config used by raw data, allowing one known wording edit."""

    current = copy.deepcopy(dict(current_config))
    current_digest = config_digest(current)
    if recorded_digest == current_digest:
        return current, {
            "applied": False,
            "field": "description",
            "current_config_digest": current_digest,
            "execution_config_digest": current_digest,
        }

    if current.get("description") != CURRENT_DESCRIPTION:
        raise ValueError(
            "recorded config digest differs and the current scaled-tanh description "
            "is not the recognized final-holdout wording"
        )
    execution = copy.deepcopy(current)
    execution["description"] = LEGACY_DESCRIPTION
    execution_digest = config_digest(execution)
    if recorded_digest != execution_digest:
        raise ValueError(
            "recorded config differs by more than the recognized scaled-tanh "
            "description wording migration"
        )
    current_without_description = copy.deepcopy(current)
    execution_without_description = copy.deepcopy(execution)
    del current_without_description["description"]
    del execution_without_description["description"]
    if current_without_description != execution_without_description:
        raise ValueError("scaled-tanh execution config has non-description drift")
    return execution, {
        "applied": True,
        "field": "description",
        "current_value": CURRENT_DESCRIPTION,
        "execution_value": LEGACY_DESCRIPTION,
        "current_config_digest": current_digest,
        "execution_config_digest": execution_digest,
    }


__all__ = [
    "CURRENT_DESCRIPTION",
    "LEGACY_DESCRIPTION",
    "resolve_execution_config",
]
