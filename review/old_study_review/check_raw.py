"""Recompute per-round quantities of the 600 replayed evaluation runs from their raw logs.

Independent of experiments/transport_instantiation.py: uses only the logged per-round
fields and the paper's formulas (sigma = 0.25, lambda = 1, R = B_phi = 1, delta = 0.05,
c_h = 4/(3 sqrt 3), L = c_h / sqrt(W)). Also computes the Phase 1 checks that needed raw
logs: A4 (zero-width optimism) and A2 (radius terms at t = 10, 100, 500, 1000).

Usage: python3 check_raw.py REPLAY_OUT_DIR COMMITTED_SEED_SUMMARIES OUT_JSON
"""
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

SIGMA, LAM, R, DELTA = 0.25, 1.0, 1.0, 0.05
C_H = 4.0 / (3.0 * math.sqrt(3.0))
RTOL = 1e-10
POLICIES = ("transport_hessian", "transport_endpoint", "frozen_reference", "naive_current")
SCORE_FIELD = {"transport_hessian": "hessian_transport_scores", "transport_endpoint": "endpoint_transport_scores",
               "frozen_reference": "frozen_reference_scores", "naive_current": "naive_current_scores"}
# every logged numeric field the checks read; each must be finite in every round
USED = ("corrected_centers", "true_means", "frozen_widths", "current_widths", "current_bias", "beta_t_corr",
        "beta_stat", "beta_hist", "gamma_t", "gamma_t_minus_1", "historical_certified_error_energy", "theta_t_norm",
        "D_Q", "Q_t", "endpoint_thompson_distance", "scores", *SCORE_FIELD.values(), "instantaneous_pseudo_regret",
        "cumulative_pseudo_regret", "played_frozen_width")


def close(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if not (np.all(np.isfinite(a)) and np.all(np.isfinite(b))):
        return False
    return bool(np.all(np.abs(a - b) <= RTOL * np.maximum(1.0, np.maximum(np.abs(a), np.abs(b)))))


def check_run(job):
    path, committed = job
    summary = json.loads((path.parent / "summary.json").read_text())
    w, method = summary["W"], summary["method"]
    lip = C_H / math.sqrt(w)
    bad = {}
    note = lambda k: bad.__setitem__(k, bad.get(k, 0) + 1)
    cum_regret = bias_sum = hist_energy = frozen_sum = width_sum = 0.0
    prev_gamma = None
    zero_width_ok = zero_width_pairs = 0
    min_slack = math.inf
    own_optimism_rounds = 0
    a2 = {}
    rounds = 0
    for line in path.open():
        record = json.loads(line)
        m = record["metrics"]
        rounds += 1
        t = m["round"]
        # labels must match position (outer round is zero-based, metrics round one-based) and the run's seed
        if t != rounds or record["round"] != rounds - 1 or record["seed"] != summary["seed"]: note("round_or_seed_label")
        if not all(np.all(np.isfinite(np.asarray(m[k], float))) for k in USED): note("nonfinite_input")
        centers = np.asarray(m["corrected_centers"]); true = np.asarray(m["true_means"])
        sbar = np.asarray(m["frozen_widths"]); s = np.asarray(m["current_widths"])
        bias, beta = m["current_bias"], m["beta_t_corr"]
        # radius: beta = sqrt(gamma_{t-1} + 2 log(1/delta)) + sqrt(lambda) R + sqrt(sum_{s<t} eps(s)^2) / sigma
        stat = math.sqrt(m["gamma_t_minus_1"] + 2 * math.log(1 / DELTA)) + math.sqrt(LAM) * R
        if not close(m["beta_stat"], stat): note("beta_stat")
        if not close(hist_energy, m["historical_certified_error_energy"]): note("historical_energy_running_sum")
        if not close(m["beta_hist"], math.sqrt(hist_energy) / SIGMA): note("beta_hist")
        if not close(beta, stat + math.sqrt(hist_energy) / SIGMA): note("beta_total")
        if prev_gamma is not None and not close(m["gamma_t_minus_1"], prev_gamma): note("gamma_index")
        prev_gamma = m["gamma_t"]
        # envelope and certificates
        if not close(bias, 0.5 * lip * (R + m["theta_t_norm"]) ** 2): note("envelope")
        if not close(m["D_Q"], 2 * lip * math.sqrt(max(m["Q_t"], 0.0)) / (SIGMA * math.sqrt(LAM))): note("D_Q")
        if m["Q_t"] < 0: note("Q_negative")
        # scores of all four policies, in the paper's form m + beta * factor * width + b, evaluated with the
        # simulator's association (coefficient beta * factor first) so the binary64 scores must match exactly
        coef = {"transport_hessian": beta * math.exp(m["D_Q"] / 2),
                "transport_endpoint": beta * math.exp(m["endpoint_thompson_distance"] / 2),
                "frozen_reference": beta, "naive_current": beta}
        width = {"transport_hessian": s, "transport_endpoint": s, "frozen_reference": sbar, "naive_current": s}
        recon = {p: centers + coef[p] * width[p] + bias for p in POLICIES}
        for p in POLICIES:
            if not np.array_equal(np.asarray(m[SCORE_FIELD[p]]), recon[p]): note(f"score_{p}")
        own = recon[method]
        if not np.array_equal(np.asarray(m["scores"]), own): note("scores_field_is_own_policy")
        if m["selected_action"] != int(np.argmax(own)): note("argmax")  # first maximum, as np.argmax in the simulator
        if m["optimal_action"] != int(np.argmax(true)): note("optimal_action")
        inst = float(true.max() - true[m["selected_action"]])
        if not close(m["instantaneous_pseudo_regret"], inst): note("instantaneous_regret")
        cum_regret += inst
        if not close(m["cumulative_pseudo_regret"], cum_regret): note("cumulative_regret")
        if not close(m["played_frozen_width"], sbar[m["selected_action"]]): note("played_frozen_width")
        own_optimism_rounds += bool(np.all(own >= true))
        if bool(m["method_optimism_all_actions"]) != bool(np.all(own >= true)): note("method_optimism_flag")
        # A4: zero-width optimism m_t(a) + b_t >= mu*_t(a) for every action
        slack = centers + bias - true
        zero_width_pairs += len(slack); zero_width_ok += int(np.sum(slack >= 0)); min_slack = min(min_slack, float(slack.min()))
        if t in (10, 100, 500, 1000):
            a2[t] = {"beta": beta, "stat": stat - math.sqrt(LAM) * R, "ridge": math.sqrt(LAM) * R,
                     "hist": math.sqrt(hist_energy) / SIGMA, "bias": bias, "theta_norm": m["theta_t_norm"]}
        bias_sum += bias; hist_energy += bias ** 2; frozen_sum += sbar[m["selected_action"]] ** 2
    # per-run summary fields: current_bias_cumulative = 2 sum b_t (the bound's bias term);
    # frozen_width_sum = sum sbar_t(a_t)^2 (the potential-lemma quantity, despite its name)
    for key, value in (("cumulative_pseudo_regret", cum_regret), ("current_bias_cumulative", 2 * bias_sum),
                       ("frozen_width_sum", frozen_sum), ("rounds", rounds)):
        if not close(summary[key], value): note(f"summary_{key}")
        if committed is None or not close(committed[key], value): note(f"committed_summary_{key}")
    return {"W": w, "method": method, "seed": summary["seed"], "bad": bad, "zero_width_ok": zero_width_ok,
            "zero_width_pairs": zero_width_pairs, "min_zero_width_slack": min_slack,
            "own_optimism_rounds": own_optimism_rounds, "a2": a2}


if __name__ == "__main__":
    out, committed_path, out_json = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    paths = sorted(p for p in out.glob("raw/evaluation/T-1000/*/*/seed-*/raw.jsonl") if (p.parent / "summary.json").exists())
    rows = [json.loads(line) for line in committed_path.open()]
    committed = {(r["W"], r["method"], r["seed"]): r for r in rows}
    jobs, identities = [], []
    for p in paths:
        s = json.loads((p.parent / "summary.json").read_text())
        identities.append((s["W"], s["method"], s["seed"]))
        jobs.append((p, committed.get(identities[-1])))
    # both sides must hold each (W, method, seed) exactly once, and the same set of them
    if len(set(identities)) != len(identities) or len(committed) != len(rows) or set(identities) != set(committed):
        print(f"IDENTITY MISMATCH: replay {len(identities)} runs, {len(set(identities))} distinct; committed "
              f"{len(rows)} rows, {len(committed)} distinct; missing {sorted(set(committed) - set(identities))[:5]}")
        raise SystemExit(1)
    with ProcessPoolExecutor(32) as pool:
        results = list(pool.map(check_run, jobs, chunksize=4))
    total_bad = {}
    for r in results:
        for k, v in r["bad"].items():
            total_bad[k] = total_bad.get(k, 0) + v
    cells = {}
    for r in results:
        c = cells.setdefault(f"W={r['W']} {r['method']}", {"runs": 0, "zw_ok": 0, "zw_pairs": 0, "min_slack": math.inf,
                                                         "own_optimism_rounds": 0, "a2": {}})
        c["runs"] += 1; c["zw_ok"] += r["zero_width_ok"]; c["zw_pairs"] += r["zero_width_pairs"]
        c["min_slack"] = min(c["min_slack"], r["min_zero_width_slack"]); c["own_optimism_rounds"] += r["own_optimism_rounds"]
        for t, v in r["a2"].items():
            for k, x in v.items():
                c["a2"].setdefault(str(t), {}).setdefault(k, []).append(x)
    for c in cells.values():
        c["a2"] = {t: {k: float(np.median(v)) for k, v in d.items()} for t, d in c["a2"].items()}
    report = {"runs_checked": len(results), "rtol": RTOL, "mismatch_counts": total_bad, "cells": cells}
    out_json.write_text(json.dumps(report, indent=1, sort_keys=True))
    print(f"runs {len(results)}; mismatches {total_bad or 'none'}")
    for name, c in sorted(cells.items()):
        print(f"{name:32s} A4 {c['zw_ok']}/{c['zw_pairs']} min slack {c['min_slack']:.4f}  own-optimism rounds {c['own_optimism_rounds']}/{c['runs'] * 1000}")
    raise SystemExit(1 if total_bad else 0)
