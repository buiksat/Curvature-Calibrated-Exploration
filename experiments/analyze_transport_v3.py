"""Prespecified analysis for PROTOCOL_V3.md (tuning selection and evaluation tests).

  python -m experiments.analyze_transport_v3 tuning TUNING/runs.jsonl
  python -m experiments.analyze_transport_v3 evaluation EVAL/runs.jsonl --output RESULT.json
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

from experiments import transport_instantiation as ti

DELTA_MARGIN = 6.65  # fixed from the development pilot; never recomputed
POLICIES = ("transport_hessian", "transport_endpoint", "frozen_reference", "naive_current", "ucb_glm")
EQUIVALENCE_PAIRS = (("transport_endpoint", "frozen_reference"), ("naive_current", "frozen_reference"),
                     ("transport_endpoint", "naive_current"))
SECONDARY_PAIRS = (("transport_hessian", "frozen_reference"), ("ucb_glm", "frozen_reference"))
BOOTSTRAP_SEED = ti.derive_child_seed(41200, "transport_v3/bootstrap")
TUNING_SEEDS = 10


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def select_optimizer(runs: list[dict]) -> dict:
    by_config = defaultdict(list)
    for r in runs:
        by_config[(r["spec"]["learning_rate"], r["spec"]["steps_per_round"])].append(r)
    scores = {}
    for config, rs in by_config.items():
        if len(rs) == TUNING_SEEDS and all(not r["failures"] and r.get("mse") is not None for r in rs):
            scores[config] = float(np.mean([r["mse"] for r in rs]))
    if not scores:
        raise SystemExit("no tuning configuration qualified")
    best = min(scores, key=lambda cfg: (scores[cfg], cfg[0], cfg[1]))  # ties: smaller rate, then fewer steps
    return {"learning_rate": best[0], "steps_per_round": best[1],
            "mean_mse": {f"{lr:g}|{k}": v for (lr, k), v in sorted(scores.items())},
            "disqualified": sorted(f"{lr:g}|{k}" for lr, k in by_config if (lr, k) not in scores)}


def holm(pvalues: dict, alpha: float = 0.05) -> dict:
    order = sorted(pvalues, key=pvalues.get)
    rejected, still = {}, True
    for rank, name in enumerate(order):
        still = still and pvalues[name] <= alpha / (len(order) - rank)
        rejected[name] = still
    return rejected


def evaluate(runs: list[dict]) -> dict:
    regret, failed, cf = defaultdict(dict), defaultdict(list), {}
    for r in runs:
        if r.get("crashed"):
            failed[r["method"]].append(r["seed"])
            continue
        regret[r["method"]][r["seed"]] = r["regret"]
        cf[r["seed"]] = r["context_free_regret"]
        if r["failures"]:
            failed[r["method"]].append(r["seed"])  # flagged, still analyzed

    def paired(a, b):
        seeds = sorted(set(regret[a]) & set(b if isinstance(b, dict) else regret[b]))
        right = b if isinstance(b, dict) else regret[b]
        return np.asarray([regret[a][s] - right[s] for s in seeds])

    h1_p = {p: float(stats.ttest_1samp(paired(p, cf), 0.0, alternative="less").pvalue) for p in POLICIES}
    h1_reject = holm(h1_p)
    h2 = {}
    for a, b in EQUIVALENCE_PAIRS:
        d = paired(a, b)
        half = stats.t.ppf(0.95, len(d) - 1) * d.std(ddof=1) / math.sqrt(len(d))
        lo, hi = d.mean() - half, d.mean() + half
        h2[f"{a}-{b}"] = {"n": len(d), "mean": float(d.mean()), "ci90": [float(lo), float(hi)],
                          "equivalent": bool(-DELTA_MARGIN < lo and hi < DELTA_MARGIN)}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    secondary = {}
    for a, b in SECONDARY_PAIRS:
        d = paired(a, b)
        boot = d[rng.integers(0, len(d), size=(10000, len(d)))].mean(axis=1)
        secondary[f"{a}-{b}"] = {"n": len(d), "mean": float(d.mean()),
                                 "percentile_ci95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]}
    frozen = [r for r in runs if r["method"] == "frozen_reference"]
    corrected = [r for r in runs if r["method"] in POLICIES[:4]]
    return {
        "delta_margin": DELTA_MARGIN, "failed_or_flagged_seeds": dict(failed),
        "H1": {p: {"n": len(paired(p, cf)), "mean_minus_context_free": float(paired(p, cf).mean()),
                   "p_one_sided": h1_p[p], "holm_reject": h1_reject[p]} for p in POLICIES},
        "H1_holds": all(h1_reject.values()),
        "H2": h2, "H2_holds": all(v["equivalent"] for v in h2.values()),
        "primary_endpoint_minus_frozen": h2["transport_endpoint-frozen_reference"],
        "H3_frozen_runs_below_cap": sum(not r.get("crashed") and r["frozen_form_bound"] < r["cap"] for r in frozen),
        "H3_frozen_runs": len(frozen),
        "H3_holds": len(frozen) > 0 and all(not r.get("crashed") and r["frozen_form_bound"] < r["cap"] for r in frozen),
        "A5_below_cap_runs": sum(not r.get("crashed") and r["A5"] < r["cap"] for r in corrected),
        "corrected_runs": len(corrected),
        "secondary_unadjusted": secondary,
        "mean_regret": {p: float(np.mean(list(regret[p].values()))) for p in POLICIES if regret[p]},
        "mean_context_free": float(np.mean(list(cf.values()))),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("tuning", "evaluation"))
    parser.add_argument("runs", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    runs = load(args.runs)
    result = select_optimizer(runs) if args.mode == "tuning" else evaluate(runs)
    text = json.dumps(result, indent=1, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
