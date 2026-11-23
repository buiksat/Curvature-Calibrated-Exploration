"""Analysis for the relinearization coverage study; reads only saved run artifacts.

  python -m experiments.analyze_relin_coverage primary RUN_DIR --out OUT [--expected-protocol-sha256 HEX]
  python -m experiments.analyze_relin_coverage secondary RUN_DIR --out OUT [--expected-protocol-sha256 HEX]
  python -m experiments.analyze_relin_coverage select-width RUN_DIR

Every coverage and width number is recomputed here from the roundwise records:
r_frozen = beta sbar + b, r_naive = beta s + b, r_endpoint = beta exp(d_Th / 2) s + b.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import math
from dataclasses import asdict
from pathlib import Path

import numpy as np
from scipy.stats import beta as beta_dist

from experiments import relin_coverage as rc

DELTA, ALPHA = 0.05, 0.05
TAU, TAU_GRID = 1e-9, (0.0, 1e-9, 1e-6, 1e-3)
DOMINANCE_RTOL = 1e-12
BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED = 10_000, 20261121


def cp_lower(k: int, n: int, level: float) -> float:
    return 0.0 if k == 0 else float(beta_dist.ppf(level, k, n - k + 1))


def cp_upper(k: int, n: int, level: float) -> float:
    return 1.0 if k == n else float(beta_dist.ppf(1.0 - level, k + 1, n - k))


def radii(beta, sbar, s, d_th, b) -> dict:
    beta, d_th = np.asarray(beta)[:, None], np.asarray(d_th)[:, None]
    return {"frozen": beta * sbar + b, "naive": beta * s + b, "endpoint": beta * np.exp(0.5 * d_th) * s + b}


def _protocol_check(run_dir: Path, expected: str | None) -> dict:
    shas = sorted({json.loads(p.read_text()).get("protocol_sha256") for p in run_dir.glob("manifest_*.json")} - {None})
    if expected is not None and shas != [expected]:
        raise SystemExit(f"protocol hash mismatch: manifests record {shas}, expected {expected}")
    return {"manifest_protocol_sha256": shas}


def _run_plan(run_dir: Path, seeds: list[int] | None) -> dict:
    """The invocation recorded by the run directory's manifests; every record is checked against it."""
    manifests = [json.loads(p.read_text()) for p in sorted(run_dir.glob("manifest_*.json"))]
    if not manifests:
        raise SystemExit(f"{run_dir}: no manifest")
    if any(rc.manifest_key(m) != rc.manifest_key(manifests[0]) for m in manifests):
        raise SystemExit(f"{run_dir}: manifests disagree on configuration, source or protocol")
    planned = sorted({s for m in manifests for s in rc.parse_seeds(m["argv"]["seeds"])})
    if seeds is not None and planned != sorted(seeds):
        raise SystemExit(f"{run_dir}: manifests plan {len(planned)} seeds {planned[0]}-{planned[-1]}, not the expected seeds")
    return {"argv": manifests[0]["argv"], "model": manifests[0].get("model"), "seeds": planned}


def _check_record(path: Path, recorded: dict, expected: dict) -> None:
    diff = {k: (recorded.get(k), v) for k, v in expected.items() if recorded.get(k) != v}
    if diff:
        raise SystemExit(f"{path} does not match its run manifest (recorded, manifest): {diff}")


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def primary_seed(npz: Path, meta: dict) -> dict:
    z = np.load(npz)
    model = rc.ModelClass(**meta["model"])
    T, span = model.horizon, 2.0 * float(rc.h(model.radius, model))
    mu, center, action = z["mu_star"], z["center"], z["action"]
    err = np.abs(mu - center)
    # Every stored array except the reward, which is NaN by design at the unobserved scoring round.
    finite = (all(np.all(np.isfinite(z[k])) for k in z.files if k != "reward")
              and math.isfinite(meta["update"]["theta_new"]))
    row = {"seed": meta["seed"], "finite": finite, "theta_new": meta["update"]["theta_new"],
           "projected": meta["update"]["projected"]}
    opt = mu >= mu.max(axis=1, keepdims=True)
    for env in rc.ENVELOPES:
        r = radii(z[f"beta_{env}"], z["sbar"], z["s"], z["d_th"], z[f"b_{env}"])
        row[f"{env}_endpoint_dominance_violations"] = int(np.sum(r["endpoint"] < r["frozen"] * (1 - DOMINANCE_RTOL)))
        for c, rad in r.items():
            margin = err - rad
            upper = mu - center - rad
            k = f"{env}_{c}"
            row[f"{k}_max_margin"] = float(margin.max())
            for tau in TAU_GRID:
                row[f"{k}_fail_tau{tau:g}"] = bool(np.any(margin > tau))  # used for the naive arm
                row[f"{k}_fail_conservative_tau{tau:g}"] = bool(np.any(margin > -tau))  # used for controls
            row[f"{k}_ambiguous"] = int(np.sum(np.abs(margin) <= TAU))
            hit = np.argwhere(margin > TAU)
            row[f"{k}_first_failure_round"] = int(hit[0, 0]) + 1 if len(hit) else None
            row[f"{k}_upper_max_margin"] = float(upper.max())
            row[f"{k}_upper_fail"] = bool(np.any(upper > TAU))
            row[f"{k}_optimal_upper_fail"] = bool(np.any(upper[opt] > TAU))
            row[f"{k}_length_over_span_T"] = float(2.0 * rad[-1].max() / span)
        hit = np.argwhere(err - r["naive"] > TAU)
        for c in rc.CONSTRUCTIONS:
            row[f"{env}_{c}_length_over_span_at_first_naive_failure"] = (
                float(2.0 * r[c][tuple(hit[0])] / span) if len(hit) else None)
        # Regret bounds on the frozen behavior policy's own trajectory (Prop. frozen-width UCB).
        idx = np.arange(T)
        sbar_a, b_a, beta_e = z["sbar"][idx, action], z[f"b_{env}"][idx, action], z[f"beta_{env}"]
        gamma_T = float(z["gamma"][-1] + math.log1p(sbar_a[-1] ** 2 / model.sigma ** 2))
        G = 1.0
        row[f"{env}_frozen_bound_direct_sum"] = float(np.sum(2 * beta_e * sbar_a + 2 * b_a))
        row[f"{env}_frozen_bound_potential"] = float(
            2 * math.sqrt((model.sigma ** 2 + G ** 2 / model.ridge) * gamma_T * np.sum(beta_e ** 2)) + 2 * np.sum(b_a))
    row["regret"] = float(np.sum(mu.max(axis=1) - mu[np.arange(T), action]))
    row["cap_paper"] = 2.0 * T * min(1.0, math.sqrt(model.width))
    row["cap_feasible_range"] = T * span
    row["feasible_span"] = span
    row["width_ratio_T"] = float(z["s"][-1, 0] / z["sbar"][-1, 0])
    row["width_ratio_min"] = float(np.min(z["s"] / z["sbar"]))
    row["d_th_T"] = float(z["d_th"][-1])
    row["endpoint_factor_T"] = float(math.exp(0.5 * z["d_th"][-1]))
    row["center_error_T_max"] = float(err[-1].max())
    for env in rc.ENVELOPES:
        r = radii(z[f"beta_{env}"][-1:], z["sbar"][-1:], z["s"][-1:], z["d_th"][-1:], z[f"b_{env}"][-1:])
        for c in rc.CONSTRUCTIONS:
            row[f"{env}_{c}_halfwidth_T"] = float(r[c].max())
    row["argmax_agree_all"] = bool(z["argmax_agree"].all())
    row["envelope_valid_current"] = bool(np.all(z["b_sharp"] + 1e-15 >= z["remainder_current"]))
    row["replay_rel_max"] = float(max(z["vcur_suff_rel"].max(), z["vbar_dense_rel"].max()))
    # Same tolerance as the unit test: |ours - scipy| <= 1e-12 + 1e-9 |scipy| (d_Th is ~1e-14 during the block).
    row["thompson_check_excess"] = max(abs(a - b) - (1e-12 + 1e-9 * abs(b)) for _, a, b in meta["thompson_scipy_checks"])
    row["stored_query_error"] = meta["max_stored_query_recompute_error"]
    row["theta_in_region"] = bool(np.all(np.abs(z["theta"]) <= model.radius))
    row["runtime_seconds"] = meta["runtime_seconds"]
    return row


def _summary_stats(values) -> dict:
    v = np.asarray([x for x in values if x is not None], dtype=float)
    if v.size == 0:
        return {"n": 0}
    return {"n": int(v.size), "min": float(v.min()), "median": float(np.median(v)), "max": float(v.max()),
            "mean": float(v.mean())}


def primary(run_dir: Path, out: Path, expected: str | None, expected_seeds: int | None = None,
            seeds: list[int] | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    provenance = _protocol_check(run_dir, expected)
    plan = _run_plan(run_dir, seeds)
    want = {"model": plan["model"], "teacher": float(plan["argv"]["teacher"]), "phase": plan["argv"]["phase"]}
    rows, crashed, crashes = [], set(), sorted(p.name for p in run_dir.glob("seed_*.crash.json"))
    for meta_path in sorted(run_dir.glob("seed_*.json")):
        meta = json.loads(meta_path.read_text())
        if meta.get("seed") not in plan["seeds"]:
            raise SystemExit(f"{meta_path}: seed outside the manifest plan")
        _check_record(meta_path, meta, want)
        if meta_path.name.endswith(".crash.json"):
            crashed.add(meta["seed"])
        elif meta_path.with_suffix(".npz").exists():  # a record without its arrays counts as missing
            rows.append(primary_seed(meta_path.with_suffix(".npz"), meta))
    if rows:
        _write_csv(out / "primary_seed_level.csv", rows)
    crashed -= {r["seed"] for r in rows}
    missing = sorted(set(plan["seeds"]) - {r["seed"] for r in rows} - crashed)
    n_ok, n_crash, n = len(rows), len(crashed), len(plan["seeds"])
    level = ALPHA / 3.0
    summary = {"run_dir": str(run_dir), **provenance, "seeds_planned": n, "seeds_completed": n_ok,
               "seeds_crashed": n_crash, "missing_seeds": missing, "expected_seeds": expected_seeds,
               "crash_files": crashes, "delta": DELTA, "alpha": ALPHA, "bonferroni_level_each": level, "tau": TAU,
               "nonfinite_seeds": [r["seed"] for r in rows if not r["finite"]]}
    # Crashed, missing or nonfinite seeds: never a naive failure; always a control failure.
    good = [r for r in rows if r["finite"]]
    n_bad = n - len(good)
    for env in rc.ENVELOPES:
        block = {}
        for tau in TAU_GRID:
            k_naive = sum(r[f"{env}_naive_fail_tau{tau:g}"] for r in good)
            k_frozen = sum(r[f"{env}_frozen_fail_conservative_tau{tau:g}"] for r in good) + n_bad
            k_endpoint = sum(r[f"{env}_endpoint_fail_conservative_tau{tau:g}"] for r in good) + n_bad
            block[f"tau{tau:g}"] = {
                "n": n, "naive_failures": k_naive, "frozen_failures": k_frozen, "endpoint_failures": k_endpoint,
                "L_naive": cp_lower(k_naive, n, level) if n else None,
                "U_frozen": cp_upper(k_frozen, n, level) if n else None,
                "U_endpoint": cp_upper(k_endpoint, n, level) if n else None}
        for c in rc.CONSTRUCTIONS:
            block[c] = {
                "upper_failures": sum(r[f"{env}_{c}_upper_fail"] for r in good),
                "optimal_action_upper_failures": sum(r[f"{env}_{c}_optimal_upper_fail"] for r in good),
                "ambiguous_cases_total": sum(r[f"{env}_{c}_ambiguous"] for r in good),
                "max_margin": _summary_stats(r[f"{env}_{c}_max_margin"] for r in good),
                "first_failure_round": _summary_stats(r[f"{env}_{c}_first_failure_round"] for r in good),
                "halfwidth_T": _summary_stats(r[f"{env}_{c}_halfwidth_T"] for r in good),
                "length_over_span_T": _summary_stats(r[f"{env}_{c}_length_over_span_T"] for r in good),
                "length_over_span_at_first_naive_failure": _summary_stats(
                    r[f"{env}_{c}_length_over_span_at_first_naive_failure"] for r in good)}
        block["endpoint_dominance_violations"] = sum(r[f"{env}_endpoint_dominance_violations"] for r in good)
        block["frozen_bound_direct_sum"] = _summary_stats(r[f"{env}_frozen_bound_direct_sum"] for r in good)
        block["frozen_bound_potential"] = _summary_stats(r[f"{env}_frozen_bound_potential"] for r in good)
        summary[env] = block
    for key in ("regret", "cap_paper", "cap_feasible_range", "width_ratio_T", "width_ratio_min", "d_th_T",
                "endpoint_factor_T", "center_error_T_max", "theta_new", "runtime_seconds", "replay_rel_max",
                "thompson_check_excess", "stored_query_error"):
        summary[key] = _summary_stats(r[key] for r in good)
    summary["checks"] = {
        "argmax_agree_all_seeds": all(r["argmax_agree_all"] for r in good),
        "envelope_valid_current_all_seeds": all(r["envelope_valid_current"] for r in good),
        "theta_in_region_all_seeds": all(r["theta_in_region"] for r in good),
        "projection_occurred_seeds": sum(r["projected"] for r in good),
        "replay_rel_max_below_1e-10": all(r["replay_rel_max"] < 1e-10 for r in good),
        "thompson_check_within_tolerance": all(r["thompson_check_excess"] <= 0.0 for r in good),
        "stored_query_error_zero": all(r["stored_query_error"] == 0.0 for r in good)}
    summary["classification"] = classify(summary)
    (out / "primary_summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    (out / "primary_tables.md").write_text(primary_markdown(summary))
    return summary


def classify(s: dict) -> str:
    sharp, checks = s["sharp"], s["checks"]
    ok = (s["seeds_crashed"] == 0 and not s["nonfinite_seeds"] and not s["missing_seeds"]
          and (s["expected_seeds"] is None or s["seeds_completed"] == s["expected_seeds"]) and all(v for k, v in checks.items()
          if k != "projection_occurred_seeds") and sharp["endpoint_dominance_violations"] == 0)
    if not ok:
        return "invalid or incomplete experiment"
    b = sharp[f"tau{TAU:g}"]
    if not b["L_naive"] > DELTA:
        return "no demonstrated naive-confidence failure"
    if not (b["U_frozen"] <= DELTA and b["U_endpoint"] <= DELTA):
        return "naive failure demonstrated; control calibration inconclusive"
    worst = sharp["endpoint"]["length_over_span_at_first_naive_failure"].get("max", math.inf)
    return ("confidence repair with informative intervals" if worst < 1.0
            else "confidence repair achieved only through vacuous intervals")


def primary_markdown(s: dict) -> str:
    fmt = lambda d, key, spec=".4f": format(d[key], spec) if d.get("n") else "n/a"  # no valid seeds -> n/a
    lines = ["# Primary study: seed-level simultaneous coverage", "",
             f"Seeds completed {s['seeds_completed']}, crashed {s['seeds_crashed']}"
             + (f", missing {len(s['missing_seeds'])}, nonfinite {len(s['nonfinite_seeds'])}"
                if s["missing_seeds"] or s["nonfinite_seeds"] else "") + f". delta = {DELTA}; "
             f"alpha = {ALPHA}, each one-sided Clopper-Pearson bound at alpha/3 = {ALPHA / 3:.6f}; tau = {TAU:g}.", "",
             f"Classification: **{s['classification']}**", ""]
    for env in rc.ENVELOPES:
        label = "new certified-envelope variant (sharp)" if env == "sharp" else "manuscript's original envelope"
        lines += [f"## Envelope: {label}", "",
                  "| tau | naive fails | L_naive | frozen fails | U_frozen | endpoint fails | U_endpoint |",
                  "|---|---:|---:|---:|---:|---:|---:|"]
        for tau in TAU_GRID:
            b = s[env][f"tau{tau:g}"]
            lines.append(f"| {tau:g} | {b['naive_failures']}/{b['n']} | {b['L_naive']:.4f} | {b['frozen_failures']}/{b['n']}"
                         f" | {b['U_frozen']:.4f} | {b['endpoint_failures']}/{b['n']} | {b['U_endpoint']:.4f} |")
        lines += ["", "| construction | upper fails | optimal-action upper fails | max margin (median) | "
                      "half-width at T (median) | length/span at T (median) | length/span at first naive failure (max) |",
                  "|---|---:|---:|---:|---:|---:|---:|"]
        for c in rc.CONSTRUCTIONS:
            b = s[env][c]
            lines.append(f"| {c} | {b['upper_failures']} | {b['optimal_action_upper_failures']} | "
                         f"{fmt(b['max_margin'], 'median')} | {fmt(b['halfwidth_T'], 'median')} | "
                         f"{fmt(b['length_over_span_T'], 'median')} | "
                         f"{fmt(b['length_over_span_at_first_naive_failure'], 'max')} |")
        lines += ["", f"Frozen-policy regret bounds (own trajectory): direct sum of instantaneous bounds median "
                      f"{fmt(s[env]['frozen_bound_direct_sum'], 'median', '.1f')}; determinant-potential bound median "
                      f"{fmt(s[env]['frozen_bound_potential'], 'median', '.1f')}; caps: paper {fmt(s['cap_paper'], 'median', '.0f')}, "
                      f"feasible range {fmt(s['cap_feasible_range'], 'median', '.1f')}.", ""]
    lines += [f"Realized pseudo-regret of the behavior policy: median {fmt(s['regret'], 'median', '.3f')} "
              f"(min {fmt(s['regret'], 'min', '.3f')}, max {fmt(s['regret'], 'max', '.3f')}).",
              f"Width ratio s/sbar at T: median {fmt(s['width_ratio_T'], 'median', '.5f')}; "
              f"endpoint factor exp(d_Th/2) at T: median {fmt(s['endpoint_factor_T'], 'median', '.5f')}.", "",
              "Checks: " + ", ".join(f"{k}={v}" for k, v in s["checks"].items()), ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- secondary

SECONDARY_OWN = {"frozen_reference": "frozen", "naive_current": "naive", "transport_endpoint": "endpoint"}


def secondary_run(npz: Path, meta: dict) -> dict:
    from experiments import relin_policy as rp

    z = np.load(npz)
    spec = rp.PolicySpec(**meta["spec"])
    mu = rp.mean_table(spec)[z["context"].astype(int)]
    model = rc.ModelClass(width=spec.width, radius=spec.radius)
    span = 2.0 * float(rc.h(spec.radius, model))  # ||phi|| = 1 for every category
    T, action = spec.horizon, z["action"].astype(int)
    idx = np.arange(T)
    err = np.abs(mu - z["center"])
    r = radii(z["beta"], z["sbar"], z["s"], z["d_th"], z["b"])
    own = SECONDARY_OWN[meta["method"]]
    row = {"W": spec.width, "method": meta["method"], "seed": meta["seed"], "regret": meta["regret"],
           "context_free_regret": meta["context_free_regret"], "runtime_seconds": meta["runtime_seconds"],
           "replay_failures": len(meta["failures"]),
           "finite": bool(all(np.all(np.isfinite(z[k])) for k in z.files)
                          and all(math.isfinite(meta[k]) for k in ("regret", "gamma_T")))}
    for c, rad in r.items():
        margin = err - rad
        row[f"{c}_coverage_fail"] = bool(np.any(margin > (TAU if c == "naive" else -TAU)))
        row[f"{c}_max_margin"] = float(margin.max())
        row[f"{c}_upper_fail"] = bool(np.any(mu - z["center"] - rad > TAU))
    row["own_coverage_fail"] = row[f"{own}_coverage_fail"]
    ratio = z["s"] / z["sbar"]
    row |= {"width_ratio_min": float(ratio.min()), "width_ratio_max": float(ratio.max()),
            "width_ratio_median": float(np.median(ratio)), "d_th_max": float(z["d_th"].max()),
            "endpoint_factor_max": float(math.exp(0.5 * z["d_th"].max())),
            "own_length_over_span_median": float(np.median(2 * r[own] / span)),
            "own_length_over_span_final_played": float(2 * r[own][-1, action[-1]] / span),
            "endpoint_dominance_violations": int(np.sum(r["endpoint"] < r["frozen"] * (1 - DOMINANCE_RTOL)))}
    beta, sbar_a, b_a = z["beta"], z["sbar"][idx, action], z["b"][idx, action]
    pot = spec.sigma ** 2 + 1.0 / spec.ridge  # G = 1
    row["cap_paper"] = 2.0 * T * min(1.0, math.sqrt(spec.width))
    row["cap_feasible_range"] = T * span
    if own == "frozen":
        row["bound_direct_sum"] = float(np.sum(2 * beta * sbar_a + 2 * b_a))
        row["bound_potential"] = float(2 * math.sqrt(pot * meta["gamma_T"] * np.sum(beta ** 2)) + 2 * np.sum(b_a))
    elif own == "endpoint":
        h_t = 1.0 + np.exp(z["d_th"])  # Cor. direct endpoint sandwich with c_pm = exp(pm d_Th)
        row["bound_direct_sum"] = float(np.sum(beta * h_t * sbar_a + 2 * b_a))
        row["bound_potential"] = float(math.sqrt(pot * meta["gamma_T"] * np.sum((beta * h_t) ** 2)) + 2 * np.sum(b_a))
    else:
        row["bound_direct_sum"] = row["bound_potential"] = None  # naive current: uncertified, no bound
    return row


def _bootstrap(diffs: np.ndarray, label: str) -> list[float]:
    rng = np.random.default_rng([BOOTSTRAP_SEED, *label.encode()])
    means = diffs[rng.integers(0, diffs.size, size=(BOOTSTRAP_RESAMPLES, diffs.size))].mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def secondary(run_dir: Path, out: Path, expected: str | None, seeds: list[int] | None = None) -> dict:
    from experiments import relin_policy as rp

    out.mkdir(parents=True, exist_ok=True)
    provenance = _protocol_check(run_dir, expected)
    plan = _run_plan(run_dir, seeds)
    argv = plan["argv"]
    planned = {(float(W), m, s) for W in ast.literal_eval(argv["widths"])
               for m in ast.literal_eval(argv["methods"]) for s in plan["seeds"]}
    rows, present = [], set()
    for meta_path in sorted(run_dir.glob("W*.json")):
        meta = json.loads(meta_path.read_text())
        key = (meta["spec"]["width"], meta["method"], meta["seed"])
        if key not in planned:
            raise SystemExit(f"{meta_path}: run outside the manifest plan")
        _check_record(meta_path, meta, {"spec": asdict(rp.PolicySpec(width=key[0], horizon=int(argv["horizon"]))),
                                        "phase": argv["phase"]})
        if meta_path.name.endswith(".crash.json"):
            present.add(key)
        elif meta_path.with_suffix(".npz").exists():  # a record without its arrays counts as missing
            rows.append(secondary_run(meta_path.with_suffix(".npz"), meta))
            present.add(key)
    crashes = sorted(p.name for p in run_dir.glob("W*.crash.json"))
    if rows:
        _write_csv(out / "secondary_run_level.csv", rows)
    name = lambda W, m, s: f"W{W:g}_{m}_{s}"
    missing = sorted(name(*k) for k in planned - present)
    nonfinite = sorted(name(r["W"], r["method"], r["seed"]) for r in rows if not r["finite"])
    summary = {"run_dir": str(run_dir), **provenance, "runs_planned": len(planned), "runs": len(rows),
               "crashes": crashes, "missing_runs": missing, "nonfinite_runs": nonfinite,
               "complete": not (missing or nonfinite or crashes), "by_width": {}}
    for W in sorted({W for W, _, _ in planned}):
        cell = {"methods": {}, "paired_minus_frozen": {}}
        methods = [m for m in SECONDARY_OWN if any(k[:2] == (W, m) for k in planned)]
        by = {m: {r["seed"]: r for r in rows if r["W"] == W and r["method"] == m and r["finite"]} for m in methods}
        for m, runs in by.items():
            v = list(runs.values())
            n = sum(1 for k in planned if k[:2] == (W, m))
            # Crashed, missing or nonfinite runs count as coverage failures of their own policy.
            k = sum(r["own_coverage_fail"] for r in v) + n - len(v)
            cell["methods"][m] = {
                "n": n, "regret": _summary_stats(r["regret"] for r in v),
                "regret_sd": float(np.std([r["regret"] for r in v], ddof=1)) if len(v) > 1 else None,
                "own_coverage_failures": k,
                "own_coverage_cp95": [cp_lower(k, n, 0.025), cp_upper(k, n, 0.025)] if n else None,
                "all_constructions_coverage_failures": {c: sum(r[f"{c}_coverage_fail"] for r in v) for c in rc.CONSTRUCTIONS},
                "upper_failures_own": sum(r[f"{SECONDARY_OWN[m]}_upper_fail"] for r in v),
                "width_ratio_min": min((r["width_ratio_min"] for r in v), default=math.nan),
                "width_ratio_max": max((r["width_ratio_max"] for r in v), default=math.nan),
                "d_th_max": max((r["d_th_max"] for r in v), default=math.nan),
                "own_length_over_span_median": _summary_stats(r["own_length_over_span_median"] for r in v),
                "bound_potential": _summary_stats(r["bound_potential"] for r in v),
                "bound_direct_sum": _summary_stats(r["bound_direct_sum"] for r in v),
                "bound_potential_below_paper_cap": sum(1 for r in v if r["bound_potential"] is not None
                                                       and r["bound_potential"] < r["cap_paper"]),
                "cap_paper": v[0]["cap_paper"] if v else None,
                "replay_failures": sum(r["replay_failures"] for r in v),
                "endpoint_dominance_violations": sum(r["endpoint_dominance_violations"] for r in v),
                "runtime_seconds": _summary_stats(r["runtime_seconds"] for r in v),
                "context_free_regret": _summary_stats(r["context_free_regret"] for r in v)}
        for m in ("naive_current", "transport_endpoint"):
            common = sorted(set(by.get(m, ())) & set(by.get("frozen_reference", ())))
            if len(common) > 1:
                d = np.asarray([by[m][s]["regret"] - by["frozen_reference"][s]["regret"] for s in common])
                cell["paired_minus_frozen"][m] = {"n": len(common), "mean": float(d.mean()), "sd": float(d.std(ddof=1)),
                                                  "bootstrap95": _bootstrap(d, f"{W:g}/{m}")}
        summary["by_width"][f"{W:g}"] = cell
    (out / "secondary_summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    (out / "secondary_tables.md").write_text(secondary_markdown(summary))
    return summary


def secondary_markdown(s: dict) -> str:
    lines = ["# Secondary study: policies on their own adaptive histories", "",
             f"Runs {s['runs']}, crashes {len(s['crashes'])}"
             + ("" if s["complete"] else f", missing {len(s['missing_runs'])}, nonfinite {len(s['nonfinite_runs'])}; "
                "incomplete") + ".", ""]
    for W, cell in s["by_width"].items():
        lines += [f"## W = {W}", "", "| policy | n | mean regret | SD | minus frozen | 95% bootstrap | own-coverage fails "
                  "| s/sbar range | max d_Th | potential bound (median) | bound < cap |",
                  "|---|---:|---:|---:|---:|---|---:|---|---:|---:|---:|"]
        for m, b in cell["methods"].items():
            d = cell["paired_minus_frozen"].get(m)
            pb = b["bound_potential"]
            num = lambda x: "n/a" if x is None else f"{x:.2f}"
            row = f"| {m} | {b['n']} | {num(b['regret'].get('mean'))} | {num(b['regret_sd'])} | "
            row += f"{d['mean']:.2f} | [{d['bootstrap95'][0]:.2f}, {d['bootstrap95'][1]:.2f}] | " if d else "--- | --- | "
            row += (f"{b['own_coverage_failures']}/{b['n']} | {b['width_ratio_min']:.4f}--{b['width_ratio_max']:.4f} | "
                    f"{b['d_th_max']:.4g} | ")
            row += (f"{pb['median']:.0f} | {b['bound_potential_below_paper_cap']}/{b['n']} |" if pb.get("n")
                    else "uncertified | --- |" if m == "naive_current" else "n/a | --- |")
            lines.append(row)
        lines.append("")
    return "\n".join(lines)


def select_width(run_dir: Path) -> dict:
    """Development rule fixed before the development runs (see the protocol)."""
    rows = [secondary_run(p.with_suffix(".npz"), json.loads(p.read_text()))
            for p in sorted(run_dir.glob("W*.json")) if not p.name.endswith(".crash.json")]
    crashes = list(run_dir.glob("W*.crash.json"))
    result = {}
    for W in sorted({r["W"] for r in rows}):
        frozen = [r for r in rows if r["W"] == W and r["method"] == "frozen_reference"]
        all_w = [r for r in rows if r["W"] == W]
        result[f"{W:g}"] = {
            "frozen_runs": len(frozen), "runs": len(all_w),
            "frozen_bound_over_cap_max": max(r["bound_potential"] / r["cap_paper"] for r in frozen) if frozen else None,
            "replay_failures": sum(r["replay_failures"] for r in all_w),
            "qualifies": bool(frozen) and all(r["bound_potential"] < r["cap_paper"] for r in frozen)
                         and not any(r["replay_failures"] for r in all_w) and all(r["finite"] for r in all_w)
                         and not any(f"W{W:g}_" in c.name for c in crashes)}
    qualified = [float(W) for W, v in result.items() if v["qualifies"]]
    result["selected_width"] = min(qualified) if qualified else None
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("primary", "secondary", "select-width"))
    p.add_argument("run_dir", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--expected-protocol-sha256")
    p.add_argument("--expected-seeds", type=int)
    p.add_argument("--seeds", help="exact planned seed range, e.g. 50100-50355; must equal the manifests' plan")
    args = p.parse_args()
    if args.command == "select-width":
        print(json.dumps(select_width(args.run_dir), indent=1))
        return
    if args.out is None:
        p.error("--out is required")
    seeds = rc.parse_seeds(args.seeds) if args.seeds else None
    if args.command == "primary":
        result = primary(args.run_dir, args.out, args.expected_protocol_sha256, args.expected_seeds, seeds)
    else:
        result = secondary(args.run_dir, args.out, args.expected_protocol_sha256, seeds)
    print(json.dumps(result.get("classification", result.get("by_width")), indent=1, default=str)[:4000])


if __name__ == "__main__":
    main()
