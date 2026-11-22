from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.optimize import minimize_scalar

from experiments import relin_coverage as rc
from experiments import relin_policy as rp
from experiments import transport_instantiation as ti
from experiments import transport_v3 as v3

SMALL = rc.ModelClass(block=256)
LEARNER_KEYS = ("theta", "center", "sbar", "s", "d_th", "beta_sharp", "beta_original", "b_sharp", "b_original", "action")


def _numerical_sup(x: float, a: float, model: rc.ModelClass) -> float:
    """Independent sup of |remainder| over [-a, a]: dense grid plus bounded refinement in each cell."""
    grid = np.linspace(-a, a, 200_001)
    values = np.abs(rc.remainder(grid, x, model))
    best = float(values.max())
    k = int(values.argmax())
    lo, hi = grid[max(k - 1, 0)], grid[min(k + 1, grid.size - 1)]
    if hi > lo:
        res = minimize_scalar(lambda v: -abs(float(rc.remainder(v, x, model))), bounds=(lo, hi), method="bounded",
                              options={"xatol": 1e-13})
        best = max(best, -float(res.fun))
    return best


@pytest.mark.parametrize("width", [0.25, 1.0, 6.25, 100.0])
def test_sharp_envelope_matches_independent_numerical_sup(width):
    model = rc.ModelClass(width=width)
    rng = np.random.default_rng(7)
    for _ in range(40):
        a = float(rng.uniform(0.05, 3.0))
        x = float(rng.uniform(-a, a))
        formula = float(rc.sharp_envelope(x, a, model))
        numeric = _numerical_sup(x, a, model)
        assert formula >= numeric - 1e-12  # never below the numerical supremum
        assert formula <= numeric + 1e-9  # and attained (grid refinement), so not loose


def test_sharp_envelope_edge_cases_and_ordering():
    model = rc.ModelClass()
    assert float(rc.sharp_envelope(0.0, 0.0, model)) == 0.0  # phi = 0
    with pytest.raises(ValueError):
        rc.sharp_envelope(1.5, 1.0, model)  # parameter outside the certified region
    x = np.linspace(-1.0, 1.0, 101)
    sharp = rc.sharp_envelope(x, 1.0, model)
    original = rc.original_envelope(np.abs(x), 1.0, model)  # scalar: ||theta|| = |x| for phi = +-1
    assert np.all(sharp <= original + 1e-15)
    assert np.all(rc.sharp_envelope(x, 1.0, rc.ModelClass(link="linear")) == 0.0)


def test_scalar_block_envelope_equals_realized_teacher_remainder():
    # theta_s = R and teacher = -R: the envelope's endpoint v = -x is the realized index, so it is tight.
    model = rc.ModelClass()
    for phi in rc.ACTIONS:
        realized = abs(float(rc.remainder(phi * -1.0, phi * 1.0, model)))
        assert math.isclose(float(rc.sharp_envelope(phi, 1.0, model)), realized, rel_tol=1e-14)


def test_delayed_update_is_the_gradient_step_of_the_stated_loss():
    model, result = SMALL, rc.run_seed(50999, SMALL, -1.0)
    learner = rc.Learner(model)
    rec = result["records"]
    for t in range(model.block):
        learner.evaluate()
        learner.observe(int(rec["action"][t]), float(rec["reward"][t]))
    phis, rewards = learner.phis, learner.rewards
    loss = lambda th: 0.5 * float(np.mean((rc.h(phis * th, model) - rewards) ** 2))
    eps = 1e-6
    numeric = (loss(1.0 + eps) - loss(1.0 - eps)) / (2 * eps)
    learner.delayed_update()
    upd = learner.update_record
    assert math.isclose(upd["gradient"], numeric, rel_tol=1e-7, abs_tol=1e-9)
    assert math.isclose(upd["gradient"], upd["closed_form_gradient"], rel_tol=1e-12, abs_tol=1e-15)
    assert math.isclose(upd["eta"], 1.0 / (2 * float(rc.h(1.0, model)) * float(rc.dh(1.0, model))))
    assert upd == result["meta"]["update"]


def test_linear_model_limit_metrics_widths_and_scores_agree():
    rec = rc.run_seed(50998, rc.ModelClass(block=128, link="linear"), -1.0)["records"]
    assert np.array_equal(rec["vbar"], rec["vcur"])
    assert np.array_equal(rec["sbar"], rec["s"])
    assert np.all(rec["d_th"] == 0.0)
    assert np.all(rec["b_sharp"] == 0.0) and np.all(rec["b_original"] == 0.0)
    assert rec["argmax_agree"].all()


def test_collection_time_queries_and_pseudo_responses():
    model, result = SMALL, rc.run_seed(50997, SMALL, -1.0)
    rec = result["records"]
    learner = rc.Learner(model)
    for t in range(model.block):
        learner.evaluate()
        learner.observe(int(rec["action"][t]), float(rec["reward"][t]))
    phis, thetas = learner.phis, learner.thetas
    assert np.array_equal(thetas, rec["theta"][: model.block])
    assert np.allclose(learner.queries, rc.dh(phis * thetas, model) * phis, rtol=0, atol=0)
    expected_y = learner.rewards - rc.h(phis * thetas, model) + learner.queries * thetas
    assert np.allclose(learner.pseudo, expected_y, rtol=0, atol=1e-15)
    assert result["meta"]["max_stored_query_recompute_error"] == 0.0


def test_future_rewards_cannot_change_pre_reward_scores():
    noise = rc.noise_table(50996, SMALL)
    base = rc.run_seed(50996, SMALL, -1.0, noise=noise)["records"]
    k = 100
    changed = noise.copy()
    changed[k:] += np.random.default_rng(1).normal(0, 5.0, size=changed[k:].shape)
    other = rc.run_seed(50996, SMALL, -1.0, noise=changed)["records"]
    for key in LEARNER_KEYS:  # round index k is evaluated before reward index k is revealed
        assert np.array_equal(base[key][: k + 1], other[key][: k + 1]), key
    assert not np.array_equal(base["center"][k + 1:], other["center"][k + 1:])


def test_teacher_and_unobserved_rewards_cannot_enter_the_learner():
    noise = rc.noise_table(50995, SMALL)
    base = rc.run_seed(50995, SMALL, -1.0, noise=noise)
    rec = base["records"]
    # Unselected potential outcomes changed: learner records identical.
    changed = noise.copy()
    sel = rec["action"][: SMALL.block]
    changed[np.arange(SMALL.block), 1 - sel] += 3.0
    other = rc.run_seed(50995, SMALL, -1.0, noise=changed)["records"]
    for key in LEARNER_KEYS:
        assert np.array_equal(rec[key], other[key]), key
    # A different teacher with noise adjusted so that every potential outcome is unchanged.
    mu_a, mu_b = rc.h(rc.ACTIONS * -1.0, SMALL), rc.h(rc.ACTIONS * 0.3, SMALL)
    swapped = rc.run_seed(50995, SMALL, 0.3, noise=noise + (mu_a - mu_b))["records"]
    for key in LEARNER_KEYS:
        assert np.allclose(rec[key], swapped[key], rtol=0, atol=1e-12), key
    assert not np.allclose(rec["mu_star"], swapped["mu_star"])
    assert not hasattr(rc.Learner(SMALL), "teacher") and "teacher" not in rc.ModelClass.__dataclass_fields__


def test_dense_replay_matches_sufficient_statistics_and_region():
    result = rc.run_seed(50994, SMALL, -1.0)
    rec = result["records"]
    assert rec["vcur_suff_rel"].max() < 1e-12
    assert rec["vbar_dense_rel"].max() < 1e-12
    assert np.all(np.abs(rec["theta"]) <= SMALL.radius)
    for _, ours, scipy_value in result["meta"]["thompson_scipy_checks"]:
        assert math.isclose(ours, scipy_value, rel_tol=1e-9, abs_tol=1e-12)
    assert np.all(rec["b_sharp"] + 1e-15 >= rec["remainder_current"])  # allowance valid for the teacher


def test_endpoint_transport_spectral_orientation():
    D = math.log(4.0)
    ref, cur = np.eye(2), np.diag([math.exp(D), math.exp(-D)])
    dist, eig = ti.thompson_distance(ref, cur)  # eigenvalues of the pencil (current, reference)
    assert math.isclose(dist, D) and np.allclose(np.sort(eig), [math.exp(-D), math.exp(D)])
    queries = np.random.default_rng(3).normal(size=(500, 2))
    sbar = ti.inverse_quadratic_widths(ref, queries)
    s = ti.inverse_quadratic_widths(cur, queries)
    assert np.all(math.exp(dist / 2) * s >= sbar * (1 - 1e-12))
    assert np.all(math.sqrt(eig.max()) * s >= sbar * (1 - 1e-12))  # correct one-sided factor
    assert np.any(math.sqrt(eig.min()) * s < sbar)  # the reversed orientation fails
    rec = rc.run_seed(50993, SMALL, -1.0)["records"]
    assert np.all(np.exp(rec["d_th"] / 2)[:, None] * rec["s"] >= rec["sbar"] * (1 - 1e-12))


def test_deterministic_sanity_values():
    rec = rc.run_seed(0, rc.ModelClass(), -1.0, noise=np.zeros((8192, 2)))["records"]
    T = 8192
    beta, b = rec["beta_sharp"][T], rec["b_sharp"][T]
    assert np.allclose(rec["s"][T] / rec["sbar"][T], 0.856, atol=5e-4)
    assert np.allclose(np.abs(rec["mu_star"][T] - rec["center"][T]), 0.270, atol=5e-4)
    assert np.allclose(beta * rec["sbar"][T] + b, 0.287, atol=5e-4)
    assert np.allclose(beta * rec["s"][T] + b, 0.253, atol=5e-4)


def test_policy_port_reproduces_transport_v3_with_original_envelope():
    for method in rp.METHODS:
        ours = rp.run_policy(method, 51998, rp.PolicySpec(width=150.0, horizon=150), envelope="original")
        ref = v3.run_corrected(method, 51998, v3.Spec(horizon=150, c=1.0, learning_rate=3e-6,
                                                      steps_per_round=5))
        assert math.isclose(ours["meta"]["regret"], ref["regret"], rel_tol=0, abs_tol=1e-12)


def test_policy_runner_records_and_replay_checks():
    out = rp.run_policy("transport_endpoint", 51997, rp.PolicySpec(width=10.0, horizon=120))
    rec, meta = out["records"], out["meta"]
    assert meta["failures"] == [] and len(meta["replay_checks"]) == 3  # rounds 1, 10, 100
    assert np.all(rec["theta_norm"] <= 1.0 + 1e-12)
    assert np.all(np.exp(rec["d_th"] / 2)[:, None] * rec["s"] >= rec["sbar"] * (1 - 1e-12))
    feats = v3.FEATURES[rec["context"].astype(int)]
    assert np.all(rec["b"] >= 0.0) and feats.shape == (120, 3, 6)
