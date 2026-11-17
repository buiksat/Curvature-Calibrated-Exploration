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


def test_crash_is_recorded_not_raised():
    result = v.run(("not_a_method", 41000, v.Spec(horizon=5)))
    assert result["crashed"] and result["failures"] == ["crash"]


def test_holm_is_step_down():
    from experiments.analyze_transport_v3 import holm
    assert holm({"a": 0.001, "b": 0.03, "c": 0.04}) == {"a": True, "b": False, "c": False}
    assert holm({"a": 0.01, "b": 0.02, "c": 0.03}) == {"a": True, "b": True, "c": True}


def test_new_arms_run_without_failures_at_small_width():
    spec = v.Spec(horizon=120, c=1.0 / 120)  # W = 1
    for method in v.ENVELOPE_FREE_METHODS + ("linucb",):
        result = v.run((method, 41000, spec))
        assert result["failures"] == [], (method, result.get("traceback"))


def test_nonfinite_iterate_is_a_crash_not_a_success():
    result = v.run(("frozen_reference", 41000, v.Spec(horizon=1, learning_rate=1e308)))
    assert result["crashed"] and "FloatingPointError" in result["traceback"]


def test_glm_objective_gradient_is_the_estimating_equation():
    rng = np.random.default_rng(0)
    theta, counts, sums, width = rng.normal(size=v.D), rng.integers(1, 5, 12).astype(float), rng.normal(size=12), 1.0
    grad = (counts * v.mean(theta, v.CATEGORY_FEATURES, width) - sums) @ v.CATEGORY_FEATURES
    eye = np.eye(v.D) * 1e-6
    numeric = [(v.glm_objective(theta + e, counts, sums, width) - v.glm_objective(theta - e, counts, sums, width)) / 2e-6 for e in eye]
    assert np.allclose(grad, numeric, atol=1e-6)


def test_analysis_refuses_bad_inputs_and_survives_a_missing_primary_arm():
    from experiments import analyze_transport_v3 as an

    def row(method, seed, lr=1e-5, phase="development", **extra):
        spec = {"horizon": 20000, "c": 1.0, "learning_rate": lr, "steps_per_round": 20}
        return {"method": method, "seed": seed, "phase": phase, "spec": spec, "regret": 1.0 + seed % 7,
                "context_free_regret": 100.0, "failures": [], "A5": 1.0, "frozen_form_bound": 1.0, "cap": 40000.0, **extra}

    runs = [row(m, s) for m in an.H1_POLICIES if m != "ucb_glm" for s in (41000, 41001, 41002)]
    primary = an.evaluate(runs)["W=20000"]["primary"]["ucb_glm-frozen_reference"]
    assert primary["available"] is False and primary["holm_reject"] is False
    for bad in (runs + [row("frozen_reference", 41003, lr=3e-5)], runs + [runs[0]],  # distinct keys except the duplicate
                runs + [row("frozen_reference", 41003, phase="tuning")]):
        with pytest.raises(SystemExit):
            an.evaluate(bad)
    tuning = [row("tuning_uniform", s, phase="tuning", mse=0.1) for s in range(41100, 41110)]
    assert an.select_optimizer(tuning)["learning_rate"] == 1e-5
    for bad in ([tuning[0]] * 10, tuning[:9] + [dict(tuning[9], mse=float("nan"))],
                [dict(r, spec=dict(r["spec"], c=0.00005)) for r in tuning]):
        with pytest.raises(SystemExit):
            an.select_optimizer(bad)


def test_glm_solve_finds_the_finite_root_and_never_applies_a_rejected_step():
    f, width = v.CATEGORY_FEATURES, 1.0
    counts, sums = np.r_[2.0, np.ones(5), np.zeros(6)], np.r_[0.09, np.zeros(11)]
    for old_mean in (0.99, np.nextafter(1.0, 0.0)):  # warm starts from a saturated earlier fit
        start = np.linalg.solve(f[:6], np.r_[np.arctanh(old_mean), np.zeros(5)])
        theta, converged = v.glm_solve(start, counts, sums, width)
        assert np.all(np.isfinite(theta))
        assert v.glm_objective(theta, counts, sums, width) <= v.glm_objective(start, counts, sums, width) + 1e-9
        if old_mean == 0.99:
            assert converged and np.isclose(f[0] @ theta, np.arctanh(0.045))
