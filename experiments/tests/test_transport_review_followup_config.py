"""Scientific design invariants for the separate review follow-up."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from experiments.config import get_seed_set, load_config
from experiments.run_transport_instantiation_study import validate_transport_config
from experiments.transport_instantiation import target_width


ROOT = Path(__file__).resolve().parents[2]
FOLLOWUP = ROOT / "experiments/configs/transport_review_followup.yaml"
LOCKED = ROOT / "experiments/configs/transport_instantiation.yaml"


@pytest.mark.parametrize("profile", ("smoke", "full"))
def test_target_encoding_recovers_same_prespecified_nonlinearity_scales(profile: str) -> None:
    config = load_config(FOLLOWUP, profile=profile)
    validate_transport_config(config)
    assert config["horizons"] == [config["rounds"]]
    widths = config["followup"]["prespecified_width_W"]
    assert len(config["target_D"]) == len(widths)
    for target, width in zip(config["target_D"], widths):
        recovered = target_width(
            config["rounds"], target,
            feature_bound=config["environment"]["feature_bound"],
            theta_radius=config["teacher"]["theta_radius"],
            noise_std=config["environment"]["noise_std"],
            ridge=config["ridge"],
        )
        assert math.isclose(recovered, width, rel_tol=2e-15)


def test_no_followup_seed_reuses_locked_data_or_another_profile_partition() -> None:
    seen: set[int] = set()
    for profile in ("smoke", "full"):
        locked = load_config(LOCKED, profile=profile)
        for split in ("development", "tuning", "evaluation"):
            seen.update(get_seed_set(locked, split))
    for profile in ("smoke", "full"):
        config = load_config(FOLLOWUP, profile=profile)
        for split in ("development", "tuning", "evaluation"):
            seeds = set(get_seed_set(config, split))
            assert seen.isdisjoint(seeds), (profile, split)
            seen.update(seeds)


@pytest.mark.parametrize("profile", ("smoke", "full"))
def test_outputs_cannot_alias_locked_study_evidence(profile: str) -> None:
    config = load_config(FOLLOWUP, profile=profile)
    assert config["outputs"]["required_selection_export"] is None
    assert config["outputs"]["required_selection_export_provenance"] is None
    old_outputs = load_config(LOCKED, profile=profile)["outputs"]
    protected = {str(value) for value in old_outputs.values() if value is not None}
    for value in config["outputs"].values():
        if value is not None:
            assert str(value) not in protected
            assert "transport_review_followup" in str(value)


def test_full_precision_and_pilot_scope_are_separate() -> None:
    full = load_config(FOLLOWUP, profile="full")
    smoke = load_config(FOLLOWUP, profile="smoke")
    assert full["rounds"] == full["reporting"]["primary_horizon"] == 1000
    assert len(get_seed_set(full, "evaluation")) == 50
    assert len(get_seed_set(full, "tuning")) == 10
    assert smoke["followup"]["pilot_publication_evidence"] is False
    assert smoke["followup"]["drift_thresholds_select_cells_or_seeds"] is False
    assert full["methods"] == load_config(LOCKED, profile="full")["methods"]
