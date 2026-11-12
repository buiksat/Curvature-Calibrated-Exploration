from __future__ import annotations

from experiments.make_covertype_horizon_artifact import POLICY_TYPES


def test_covertype_release_policy_inventory_is_complete() -> None:
    assert set(POLICY_TYPES) == {
        "full_network_ggn_cg",
        "frozen_full_gram",
        "diagonal_full_network",
        "last_layer_full",
        "last_layer_diagonal",
        "greedy_full_network",
        "ucb1",
        "thompson_sampling",
    }
    assert "non-contextual" in POLICY_TYPES["ucb1"]
    assert "non-contextual" in POLICY_TYPES["thompson_sampling"]
