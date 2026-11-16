"""Phase 1 audit from committed derived artifacts (no trajectory is run).

Inputs (all committed):
  review/transport_review_followup/full-cce-full-local/seed_summaries.jsonl
  review/transport_relative_diagnostics/full/per_seed.jsonl
  review/transport_review_followup/development_refinement_raw.zip
The 600-run raw trajectories are not on this host; per-round checks that need
them are computed only on the single retained development trajectory (proxy).

Usage: python review/v3_audit/phase1_audit.py OUTPUT_JSON
"""

from __future__ import annotations

import json
import math
import statistics
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np

from experiments import transport_instantiation as ti

ROOT = Path(__file__).resolve().parents[2]
SUMMARIES = ROOT / "review/transport_review_followup/full-cce-full-local/seed_summaries.jsonl"
PER_SEED = ROOT / "review/transport_relative_diagnostics/full/per_seed.jsonl"
DEV_ZIP = ROOT / "review/transport_review_followup/development_refinement_raw.zip"
DEV_RUN = "full-order2048-cached/raw.jsonl"

T = 1000
SIGMA, LAMBDA, R, B, DELTA = 0.25, 1.0, 1.0, 1.0, 0.05
C_H = ti.smoothness_constant(B)  # 4 B^2 / (3 sqrt 3)
LOG_TERM = 2.0 * math.log(1.0 / DELTA)
METHODS = ("transport_hessian", "transport_endpoint", "frozen_reference", "naive_current")
WIDTHS = (16.0, 1.0, 0.25)


def med_range(values):
    values = list(values)
    return {"median": statistics.median(values), "min": min(values), "max": max(values), "n": len(values)}


def env_max(width):
    """Max |phi^T theta_o| and max |mu*| over the 80 categories for the configured teacher (seed 1729)."""
    env = ti.ScaledTanhEnvironment(width=width, feature_bound=B, theta_radius=R, noise_std=SIGMA, teacher_seed=1729)
    u = np.abs(env.features.reshape(-1, ti.FEATURE_DIMENSION) @ env.theta_star)
    mu = np.abs([env.true_means_for_context(c) for c in range(ti.CONTEXT_COUNT)])
    return {"max_abs_index": float(u.max()), "max_abs_mean": float(mu.max()),
            "analytic_index_bound_1_over_sqrt15": 1.0 / math.sqrt(15.0),
            "paper_mean_bound_sqrtW_tanh_BR_over_sqrtW": math.sqrt(width) * math.tanh(B * R / math.sqrt(width))}


def compact_audit():
    runs = [json.loads(line) for line in SUMMARIES.read_text().splitlines()]
    assert len(runs) == 600, len(runs)
    cells = defaultdict(list)
    for run in runs:
        assert run["horizon"] == T and run["phase"] == "evaluation"
        cells[(run["W"], run["method"])].append(run)
    out = {}
    for width in WIDTHS:
        e_max = 2.0 * C_H * R * R / math.sqrt(width)  # Corollary 12 envelope, H-a
        e_min = 0.5 * C_H * R * R / math.sqrt(width)  # code envelope at theta = 0
        cap = 2.0 * T * min(B * R, math.sqrt(width))
        for method in METHODS:
            rows = cells[(width, method)]
            assert len(rows) == 50
            a1, a2, a5 = [], defaultdict(list), defaultdict(list)
            for r in rows:
                s_eps = r["current_bias_cumulative"] / 2.0  # sum_{s<=T} eps(s); history envelope = current bias at collection
                a1.append(s_eps / T / e_max)
                gamma = r["gamma_T"]
                pot = r["potential_upper"]
                assert math.isclose(pot, (SIGMA**2 + B**2 / LAMBDA) * gamma, rel_tol=1e-12)
                # gamma_{T-1} lies in [gamma_T - log(1 + G^2/(lambda sigma^2)), gamma_T].
                g_lo = max(0.0, gamma - math.log1p(B * B / (LAMBDA * SIGMA**2)))
                a2["stochastic_T_low"].append(math.sqrt(g_lo + LOG_TERM))
                a2["stochastic_T_high"].append(math.sqrt(gamma + LOG_TERM))
                hist_sum_lo, hist_sum_hi = s_eps - e_max, s_eps - e_min  # sum_{s<T} eps(s)
                a2["historical_T_low"].append(math.sqrt(hist_sum_lo**2 / (T - 1)) / SIGMA)
                a2["historical_T_high"].append(math.sqrt(e_max * hist_sum_hi) / SIGMA)
                # statistical_bound_component = sqrt(pot * sum_t (2 (a_t + sqrt(lambda) R))^2), a_t = sqrt(gamma_{t-1} + LOG_TERM)
                k = r["statistical_bound_component"] ** 2 / (4.0 * pot)  # sum_t (a_t + 1)^2
                a_min = math.sqrt(LOG_TERM)
                a5["gamma_T"].append(gamma)
                a5["A5_low"].append(2.0 * math.sqrt(pot) * (math.sqrt(k) - math.sqrt(T)))
                a5["A5_high"].append(2.0 * math.sqrt(pot * (k - T * (2.0 * a_min + 1.0))))
                a5["frozen_form_full_rhs_no_path"].append(
                    r["statistical_bound_component"] + r["historical_bound_component"] + r["current_bias_cumulative"])
            out[f"W={width}|{method}"] = {
                "W": width, "method": method, "cap": cap,
                "H_a_envelope": e_max, "code_envelope_at_theta0": e_min,
                "A1_mean_current_envelope_over_H_a": med_range(a1),
                "A2_T_stochastic_bracket": [med_range(a2["stochastic_T_low"]), med_range(a2["stochastic_T_high"])],
                "A2_T_ridge": math.sqrt(LAMBDA) * R,
                "A2_T_historical_bracket": [med_range(a2["historical_T_low"]), med_range(a2["historical_T_high"])],
                "A5_gamma_T": med_range(a5["gamma_T"]),
                "A5_low": med_range(a5["A5_low"]), "A5_high": med_range(a5["A5_high"]),
                "A5_low_above_cap_runs": sum(v > cap for v in a5["A5_low"]),
                "frozen_form_full_rhs_no_path": med_range(a5["frozen_form_full_rhs_no_path"]),
                "regret": med_range(r["cumulative_pseudo_regret"] for r in rows),
                "regret_mean": statistics.fmean(r["cumulative_pseudo_regret"] for r in rows),
                "context_free_mean": statistics.fmean(r["context_free_mean_only_regret"] for r in rows),
                "regret_below_context_free_runs": sum(r["cumulative_pseudo_regret"] < r["context_free_mean_only_regret"] for r in rows),
            }
    return out


def per_seed_audit():
    rows = [json.loads(line) for line in PER_SEED.read_text().splitlines()]
    assert len(rows) == 600
    out = {}
    for width in WIDTHS:
        for method in METHODS:
            own = [r for r in rows if r["W"] == width and r["behavior_method"] == method]
            assert len(own) == 50
            counts = [r["diagnostic_counts"][method] for r in own]
            assert all(c["rounds"] == T for c in counts)
            ratio = [r["effective_width_over_frozen_width"]["naive_current"] for r in own]
            out[f"W={width}|{method}"] = {
                "A3_bonus_gap_exceeds_center_range": med_range(c["strict_width_dominance_sufficient"] / T for c in counts),
                "A3_action_equals_width_argmax": med_range(c["width_argmax_first_matches"] / T for c in counts),
                "A6_s_over_sbar_per_seed_median": med_range(x["median"] for x in ratio),
                "A6_s_over_sbar_per_seed_p10": med_range(x["p10"] for x in ratio),
                "A6_s_over_sbar_per_seed_p90": med_range(x["p90"] for x in ratio),
                "A6_s_over_sbar_min_over_seeds": min(x["min"] for x in ratio),
                "A6_s_over_sbar_max_over_seeds": max(x["max"] for x in ratio),
            }
    return out


def dev_proxy_audit():
    with zipfile.ZipFile(DEV_ZIP) as z:
        records = [json.loads(line) for line in z.read(DEV_RUN).decode().splitlines()]
    assert len(records) == T and all(r["seed"] == 30000 for r in records)
    a2, zero_ok, mult, ratios, a3 = {}, [], [], [], defaultdict(lambda: [0, 0])
    score_field = {"transport_hessian": "hessian_transport_scores", "transport_endpoint": "endpoint_transport_scores",
                   "frozen_reference": "frozen_reference_scores", "naive_current": "naive_current_scores"}
    factor = {"transport_hessian": "exp_bar_D_over_2", "transport_endpoint": "exp_endpoint_distance_over_2"}
    for rec in records:
        m = rec["metrics"]
        t = m["round"]
        c, mu = np.asarray(m["corrected_centers"]), np.asarray(m["true_means"])
        sbar, s = np.asarray(m["frozen_widths"]), np.asarray(m["current_widths"])
        beta, b = m["beta_t_corr"], m["current_bias"]
        if t in (10, 100, 500, 1000):
            a2[t] = {"beta": beta, "stochastic": m["beta_stat"] - math.sqrt(LAMBDA) * R,
                     "ridge": math.sqrt(LAMBDA) * R, "historical": m["beta_hist"], "current_bias": b,
                     "gamma_t_minus_1": m["gamma_t_minus_1"], "theta_t_norm": m["theta_t_norm"]}
        zero_ok.extend((c + b >= mu).tolist())
        mult.extend(np.maximum(0.0, (mu - c - b) / (beta * sbar)).tolist() if beta > 0 else [0.0] * len(c))
        ratios.extend((s / sbar).tolist())
        for name in METHODS:
            w = sbar if name == "frozen_reference" else s
            coef = beta if name in ("frozen_reference", "naive_current") else beta * m[factor[name]]
            sw = np.sort(w)
            a3[name][0] += int(coef * (sw[-1] - sw[-2]) > np.ptp(c))
            a3[name][1] += int(int(np.argmax(m[score_field[name]])) == int(np.argmax(w)))
    mult = np.asarray(mult)
    return {
        "scope": "one development trajectory: W=0.25, behavior transport_hessian, seed 30000, T=1000 (not the 600-run evaluation)",
        "W": records[0]["metrics"].get("W", 0.25),
        "A2": a2,
        "A3_on_hessian_history": {k: {"bonus_gap_exceeds_center_range": v[0] / T, "action_equals_width_argmax": v[1] / T} for k, v in a3.items()},
        "A4_zero_width_optimism_fraction": float(np.mean(zero_ok)), "A4_pairs": len(zero_ok),
        "A4_least_multiplier_quantiles": {q: float(np.quantile(mult, q)) for q in (0.5, 0.9, 0.99, 1.0)},
        "A4_pairs_needing_positive_multiplier": int(np.sum(mult > 0)),
        "A6_s_over_sbar_quantiles": {q: float(np.quantile(ratios, q)) for q in (0.0, 0.1, 0.5, 0.9, 1.0)},
        "max_abs_true_mean_observed": float(max(np.max(np.abs(r["metrics"]["true_means"])) for r in records)),
    }


def main():
    result = {"envelope_constants": {"c_h": C_H, "H_a": {w: 2 * C_H / math.sqrt(w) for w in WIDTHS},
                                     "H_b": {w: math.sqrt(w) * math.tanh(1 / math.sqrt(w)) for w in WIDTHS}},
              "teacher_extremes": {str(w): env_max(w) for w in WIDTHS},
              "compact": compact_audit(), "per_seed": per_seed_audit(), "dev_proxy": dev_proxy_audit()}
    Path(sys.argv[1]).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
