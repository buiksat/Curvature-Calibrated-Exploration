#!/usr/bin/env python3
"""Analyze existing full-study logs without executing a policy or optimizer.

All diagnostic recommendations condition on each behavior policy's own saved
state. Summed alternative one-step regrets are NOT alternative adaptive-policy
regrets. The Decimal calculation uses stored doubles, including a FLOAT-rounded
B=beta*inflation; it is not an exact-arithmetic rerun of the experiment.
"""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal, Inexact, Rounded, localcontext
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import sys
import time

FIELDS = {
    "transport_hessian": "hessian_transport_scores",
    "transport_endpoint": "endpoint_transport_scores",
    "frozen_reference": "frozen_reference_scores",
    "naive_current": "naive_current_scores",
}
REQUIRED = {"manifest.jsonl", "raw.jsonl", "summary.json", "summary.json.sha256"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def first_argmax(values):
    return max(range(len(values)), key=values.__getitem__)


def run(args):
    started = time.monotonic()
    root, output = args.raw_root.resolve(), args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = [output / name for name in ("analysis.json", "input_inventory.jsonl")]
    require(not any(p.exists() for p in targets), "Refusing to replace an existing analysis; use a new output directory")
    inventory = []

    def bound_read(path, kind, original_bytes=None):
        data = path.read_bytes() if original_bytes is None else original_bytes
        inventory.append({"path": str(path), "kind": kind, "bytes": len(data), "sha256": sha(data)})
        return data

    manifest = json.loads(bound_read(root / "run.json", "run_manifest"))
    config = json.loads(bound_read(root / "execution_config.json", "execution_config"))
    bound_read(root / "source_config.json", "source_config")
    require(manifest["status"] == "complete" and manifest["evaluation_complete"] is True, "Run is not currently complete")
    require(config["profile"] == "full" and config["horizons"] == [1000], "Unexpected profile/horizon")
    require(list(FIELDS) == config["methods"] and len(config["seed_sets"]["evaluation"]) == 50, "Unexpected method/seed grid")
    require(not list((root / "raw/evaluation").rglob(".review-failed.json")), "Failed evaluation task marker exists")
    code_path = args.repository.resolve() / "experiments/transport_instantiation.py"
    code_bytes = bound_read(code_path, "scientific_source")
    recorded_code = next(v["sha256"] for v in manifest["source_inputs"] if v["path"] == "experiments/transport_instantiation.py")
    require(sha(code_bytes) == recorded_code, "Scientific source differs from recorded run source")
    script_path = Path(__file__).resolve()
    script_hash = sha(script_path.read_bytes())
    paths = sorted((root / "raw/evaluation").rglob("summary.json"))
    expected = set(itertools.product(config["target_D"], config["methods"], config["seed_sets"]["evaluation"]))
    require(len(paths) == len(expected) == 600, "Unexpected summary count")
    by_group = defaultdict(list)
    seen = set()
    for path in paths:
        summary = read(path)
        key = (summary["target_D"], summary["method"], summary["seed"])
        require(key in expected and key not in seen, "Duplicate/unexpected cell")
        seen.add(key)
        by_group[(summary["target_D"], summary["method"])].append(path)
    require(seen == expected, "Incomplete grid")
    groups = []
    with localcontext() as ctx:
        ctx.prec = 250
        for target in config["target_D"]:
            for behavior in config["methods"]:
                counts, maxima = Counter(), defaultdict(float)
                minima = {"width": float("inf"), "top_score_gap_ulps": float("inf"), "top_width_gap": float("inf")}
                sums, disagreements = defaultdict(float), Counter()
                ratios, terminal_regrets, rank_mismatches = [], [], []
                seeds, raw_paths = [], []
                W = None
                for summary_path in by_group[(target, behavior)]:
                    leaf = summary_path.parent
                    receipt_bytes = bound_read(leaf / ".review-complete.json", "completion_receipt")
                    receipt = json.loads(receipt_bytes)
                    require(receipt["signature"] == manifest["signature"] and set(receipt["files"]) == REQUIRED, "Completion receipt mismatch")
                    data = {}
                    for name in sorted(REQUIRED):
                        data[name] = bound_read(leaf / name, name)
                        require(sha(data[name]) == receipt["files"][name], "Receipt hash mismatch: " + str(leaf / name))
                    summary, run_meta = json.loads(data["summary.json"]), json.loads(data["manifest.jsonl"])
                    require(summary["config_digest"] == run_meta["config_digest"] == manifest["config_digest"], "Config digest mismatch")
                    require(run_meta["config"] == config and run_meta["git_revision"] == manifest["git_revision"], "Per-run provenance mismatch")
                    require(summary["phase"] == "evaluation" and summary["horizon"] == 1000 and summary["deterministic_audit_pass"] is True, "Unexpected summary state")
                    require(summary["selection_sha256"] == manifest["selection_sha256"], "Selection mismatch")
                    seeds.append(summary["seed"])
                    W = summary["W"] if W is None else W
                    require(W == summary["W"], "Mixed W values")
                    raw_paths.append(str(leaf / "raw.jsonl"))
                    counts["seeds"] += 1
                    terminal_regrets.append(summary["cumulative_pseudo_regret"])
                    lines = data["raw.jsonl"].splitlines()
                    require(len(lines) == 1000, "Wrong raw round count")
                    for index, line in enumerate(lines):
                        r = json.loads(line)
                        m = r["metrics"]
                        require(r["round"] == index and m["round"] == index + 1 and r["seed"] == summary["seed"], "Raw round identity mismatch")
                        require(m["deterministic_audit_passed"] is True, "Raw audit failure")
                        counts["rounds"] += 1
                        c, w = m["corrected_centers"], m["current_widths"]
                        s = m["hessian_transport_scores"]
                        beta, infl, bias = m["beta_t_corr"], m["exp_bar_D_over_2"], m["current_bias"]
                        B = beta * infl  # preserve the implementation's rounded scalar multiplication
                        actual = m["selected_action"]
                        recommendations = {name: first_argmax(m[field]) for name, field in FIELDS.items()}
                        require(m["scores"] == m[FIELDS[behavior]] and actual == recommendations[behavior], "Actual behavior score/action mismatch")
                        a = recommendations["transport_hessian"]
                        aw, wm = first_argmax(w), max(w)
                        wt, sm = sum(x == wm for x in w), max(s)
                        st = sum(x == sm for x in s)
                        counts["width_argmax_first_matches"] += a == aw
                        counts["width_argmax_set_matches"] += w[a] == wm
                        counts["width_top_tie"] += wt > 1
                        counts["score_top_tie"] += st > 1
                        counts["width_top_tie_after_round1"] += wt > 1 and m["round"] > 1
                        counts["score_top_tie_after_round1"] += st > 1 and m["round"] > 1
                        wsort = sorted(w, reverse=True)
                        wg, cr = wsort[0] - wsort[1], max(c) - min(c)
                        counts["strict_width_dominance_sufficient"] += B * wg > cr
                        dn, dw = [Decimal.from_float(x) for x in c], [Decimal.from_float(x) for x in w]
                        db, dk = Decimal.from_float(B), Decimal.from_float(bias)
                        ctx.clear_flags()
                        high_precision = [dn[j] + db * dw[j] + dk for j in range(5)]
                        counts["decimal_score_arithmetic_inexact"] += ctx.flags[Inexact]
                        counts["decimal_score_arithmetic_rounded"] += ctx.flags[Rounded]
                        ae, em = first_argmax(high_precision), max(high_precision)
                        exact_ties = sum(x == em for x in high_precision)
                        counts["exact_rank_first_mismatch"] += a != ae
                        counts["selected_not_exact_argmax_set"] += high_precision[a] != em
                        counts["exact_top_tie"] += exact_ties > 1
                        counts["rounded_score_tie_exact_unique"] += st > 1 and exact_ties == 1
                        counts["strict_width_dominance_sufficient_decimal"] += db * (dw[aw] - max(dw[j] for j in range(5) if j != aw)) > max(dn) - min(dn)
                        counts["width_argmax_is_exact_unique_max"] += high_precision[aw] == em and exact_ties == 1
                        normalized = [w[j] + c[j] / B for j in range(5)]
                        counts["normalized_rank_first_mismatch"] += a != first_argmax(normalized)
                        no_center = [B * x + bias for x in w]
                        absorbed = all(s[j] == no_center[j] for j in range(5))
                        counts["all_centers_numerically_absorbed"] += absorbed
                        counts["all_centers_absorbed_after_round1"] += absorbed and m["round"] > 1
                        counts["some_centers_numerically_absorbed"] += any(c[j] != 0 and s[j] == no_center[j] for j in range(5))
                        counts["score_reconstruction_mismatch"] += any(s[j] != (c[j] + B * w[j]) + bias for j in range(5))
                        counts["nonfinite_score_or_coefficient"] += not all(math.isfinite(x) for x in s + [B])
                        counts["zero_width"] += any(x == 0 for x in w)
                        maxima["B"] = max(maxima["B"], B)
                        maxima["D_Q"] = max(maxima["D_Q"], m["D_Q"])
                        maxima["score"] = max(maxima["score"], sm)
                        maxima["center_range"] = max(maxima["center_range"], cr)
                        maxima["theta_t_norm"] = max(maxima["theta_t_norm"], m["theta_t_norm"])
                        maxima["current_metric_condition_number"] = max(maxima["current_metric_condition_number"], m["current_metric_condition_number"])
                        minima["width"] = min(minima["width"], min(w))
                        if wg > 0:
                            minima["top_width_gap"] = min(minima["top_width_gap"], wg)
                        ss = sorted(s, reverse=True)
                        if ss[0] > ss[1]:
                            minima["top_score_gap_ulps"] = min(minima["top_score_gap_ulps"], (ss[0] - ss[1]) / math.ulp(sm))
                        if a != ae:
                            gap = em - high_precision[a]
                            rank_mismatches.append({"seed": r["seed"], "round": m["round"], "hessian_logged_argmax": a, "high_precision_argmax": ae, "rounded_top_tie": st > 1, "high_precision_top_tie": exact_ties > 1, "lost_high_precision_score_gap": float(gap), "gap_in_score_ulps": float(gap / Decimal.from_float(math.ulp(sm))), "B": B})
                        ratios.append(m["beta_hist"] / m["beta_stat"])
                        mu = m["true_means"]
                        best = max(mu)
                        for name, choice in recommendations.items():
                            sums[name] += best - mu[choice]
                        for left, right in itertools.combinations(FIELDS, 2):
                            disagreements[left + "__vs__" + right] += recommendations[left] != recommendations[right]
                require(seeds == sorted(config["seed_sets"]["evaluation"]), "Unexpected seed ordering")
                groups.append({"behavior_method": behavior, "W": W, "target_D": target, "horizon": 1000, "seeds": seeds, "hessian_recommendation_diagnostics": {"counts": dict(sorted(counts.items())), "maximum": dict(maxima), "minimum": minima, "stored_input_rank_mismatches": rank_mismatches}, "same_history_recommendations": {"pairwise_disagreement_counts": dict(disagreements), "mean_one_step_pseudo_regret": {k: v / counts["rounds"] for k,v in sums.items()}, "scope": "conditional on this behavior policy's logged states; not alternative adaptive-policy regret"}, "beta_hist_over_beta_stat": {"minimum": min(ratios), "median": statistics.median(ratios), "maximum": max(ratios)}, "actual_behavior_mean_terminal_regret": statistics.mean(terminal_regrets), "input_raw_trajectories": raw_paths})
                print(json.dumps({"W": W, "behavior": behavior, "rounds": counts["rounds"], "width_argmax_matches": counts["width_argmax_first_matches"], "decimal_rank_mismatches": counts["exact_rank_first_mismatch"]}), flush=True)
    originals = {16.0: (49691, 48552, 5, 50), 1.0: (49981, 49686, 5, 18552), 0.25: (49991, 49754, 6, 46876)}
    reproduced = []
    keys = ("width_argmax_first_matches", "strict_width_dominance_sufficient", "exact_rank_first_mismatch", "all_centers_numerically_absorbed")
    for group in groups:
        if group["behavior_method"] != "transport_hessian":
            continue
        c = group["hessian_recommendation_diagnostics"]["counts"]
        actual = tuple(c[k] for k in keys)
        require(actual == originals[group["W"]], "Original primary count changed: " + str(group["W"]))
        reproduced.append({"W": group["W"], "counts": {k:c[k] for k in keys}, "matches_original_report": True})
    inventory.sort(key=lambda r: r["path"])
    inventory_bytes = ''.join(json.dumps(v, sort_keys=True, separators=(',', ':')) + '\n' for v in inventory).encode()
    result = {"schema_version": 1, "analysis_kind": "exploratory post-outcome stored-log diagnostics", "experiments_rerun": False, "raw_root": str(root), "run_source_revision": manifest["git_revision"], "run_status": manifest["status"], "run_signature": manifest["signature"], "run_manifest_historical_error_text": manifest.get("error"), "config_digest": manifest["config_digest"], "scientific_source_sha256": recorded_code, "analysis_script_sha256": script_hash, "python": sys.version, "raw_trajectories": 600, "raw_rounds": sum(g["hessian_recommendation_diagnostics"]["counts"]["rounds"] for g in groups), "raw_trajectory_bytes": sum(v["bytes"] for v in inventory if v["kind"] == "raw.jsonl"), "hashed_input_count": len(inventory), "input_inventory_sha256": sha(inventory_bytes), "decimal_precision": 250, "decimal_definition": "Decimal.from_float of each logged c,w,bias; B is first evaluated beta*logged_inflation as float, then Decimal.from_float(B). No policy/state/exp/linear-algebra rerun. Per-round Decimal arithmetic flags reported.", "tie_rule": "first maximum action index, for stored float scores, widths, normalized float scores, and high-precision scores; argmax-set mismatches also counted", "same_history_scope": "Each row uses its behavior policy's actual logged state and true means. Alternative recommendations do not change future states or data. Their average one-step regrets are not cumulative regret estimates for alternate adaptive policies.", "original_primary_counts_reproduced": reproduced, "elapsed_analysis_seconds": time.monotonic() - started, "groups": groups}
    (output / "input_inventory.jsonl").write_bytes(inventory_bytes)
    (output / "analysis.json").write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n')
    print(json.dumps({"complete": True, "analysis": str(output/'analysis.json'), "input_inventory": str(output/'input_inventory.jsonl'), "raw_rounds": result["raw_rounds"], "elapsed_seconds": result["elapsed_analysis_seconds"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=Path('/workspace/cce-full-local'))
    parser.add_argument("--repository", type=Path, default=Path('/workspace/cce-research'))
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    run(parser.parse_args())
