import numpy as np
import pytest

from experiments import transport_v3 as v


def test_environment_geometry():
    assert np.isclose(np.linalg.norm(v.teacher(1729, 1.0)), 1.0)
    assert np.allclose(np.linalg.norm(v.CATEGORY_FEATURES, axis=1), 1.0)
    assert np.linalg.matrix_rank(v.CATEGORY_FEATURES) == v.D


def test_reserved_seeds_rejected():
    with pytest.raises(SystemExit):
        v.parse_seeds("30249-30251")
    assert v.parse_seeds("41000-41002") == [41000, 41001, 41002]


def test_short_runs_pass_replay_checks_and_bound_algebra():
    spec = v.Spec(horizon=120, c=1.0)
    result = v.run(("frozen_reference", 41000, spec))
    assert result["failures"] == []
    assert [c["round"] for c in result["replay_checks"]] == [1, 10, 100]
    assert result["A5"] <= result["frozen_form_bound"]
    glm = v.run(("ucb_glm", 41000, spec))
    assert glm["tau"] is not None and glm["newton_failures"] == 0
