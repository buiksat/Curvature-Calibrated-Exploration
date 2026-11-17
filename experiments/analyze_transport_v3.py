"""Prespecified analysis for PROTOCOL_V3.md (tuning selection and evaluation summaries).

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

HORIZON = 20000
DESIGN_W = float(HORIZON)  # W = T cell
SMALL_W = (100.0, 10.0, 1.0)
DELTA_MARGIN = 3.0  # fixed in absolute regret units; never recomputed
H1_POLICIES = ("transport_hessian", "transport_endpoint", "frozen_reference", "naive_current", "linucb", "ucb_glm")
EQUIVALENCE_PAIRS = (("transport_endpoint", "frozen_reference"), ("naive_current", "frozen_reference"),
                     ("transport_endpoint", "naive_current"))
PRIMARY_PAIRS = (("ucb_glm", "frozen_reference"), ("transport_hessian", "frozen_reference"))
DESCRIPTIVE_PAIRS = (("naive_current", "frozen_reference"), ("transport_endpoint", "frozen_reference"),
                     ("naive_current_no_envelope", "frozen_reference_no_envelope"),
                     ("transport_hessian", "frozen_reference"), ("linucb", "frozen_reference"),
                     ("ucb_glm", "frozen_reference"))
CERTIFIED = ("transport_hessian", "transport_endpoint", "frozen_reference", "naive_current")
TUNING_SEEDS = 10


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def select_optimizer(runs: list[dict]) -> dict:
    by_config = defaultdict(list)
    for r in runs:
        by_config[(r["spec"]["learning_rate"], r["spec"]["steps_per_round"])].append(r)
    scores = {}
    for config, rs in by_config.items():
        valid = all(r["method"] == "tuning_uniform" and r.get("phase") == "tuning" and not r["failures"]
                    and r["spec"]["horizon"] == HORIZON and r["spec"]["c"] == 1.0  # design cell only
                    and r.get("mse") is not None and math.isfinite(r["mse"]) for r in rs)
        if valid and len(rs) == len({r["seed"] for r in rs}) == TUNING_SEEDS:
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


def t_pvalue(d: np.ndarray, alternative: str = "two-sided") -> float:
    """Paired t p-value; 1.0 (never rejects) when fewer than two pairs or the statistic is undefined."""
    p = float(stats.ttest_1samp(d, 0.0, alternative=alternative).pvalue) if len(d) >= 2 else 1.0
    return p if math.isfinite(p) else 1.0


def bootstrap_ci(d: np.ndarray, label: str) -> list[float]:
    """95% percentile interval over 10,000 resamples of seed-paired differences."""
    rng = np.random.default_rng(ti.derive_child_seed(41200, f"transport_v3/bootstrap/{label}"))
    boot = d[rng.integers(0, len(d), size=(10000, len(d)))].mean(axis=1)
    return [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]


def analyze_cell(runs: list[dict], width: float) -> dict:
    regret, cf, flagged = defaultdict(dict), {}, defaultdict(list)
    for r in runs:
        if r.get("crashed"):
            flagged[r["method"]].append([r["seed"], "crash"])
            continue
        regret[r["method"]][r["seed"]] = r["regret"]
        cf[r["seed"]] = r["context_free_regret"]
        if r["failures"]:
            flagged[r["method"]].append([r["seed"], r["failures"][:3]])  # flagged, still analyzed

    def paired(a, b):
        right = b if isinstance(b, dict) else regret[b]
        seeds = sorted(set(regret[a]) & set(right))
        return np.asarray([regret[a][s] - right[s] for s in seeds])

    def describe(a, b):
        d = paired(a, b)
        return {"n": len(d), "mean": float(d.mean()), "bootstrap_ci95": bootstrap_ci(d, f"{width:g}/{a}-{b}")} if len(d) else None

    ok = [r for r in runs if not r.get("crashed")]
    out = {
        "W": width, "flagged_or_crashed": dict(flagged),
        "mean_regret": {m: float(np.mean(list(v.values()))) for m, v in sorted(regret.items())},
        "mean_context_free": float(np.mean(list(cf.values()))) if cf else None,
        "optimism_failure_pairs": {m: [int(sum(r["optimism_failure_pairs"] for r in ok if r["method"] == m)),
                                       sum(r["optimism_failure_pairs"] > 0 for r in ok if r["method"] == m)]
                                   for m in sorted({r["method"] for r in ok if "optimism_failure_pairs" in r})},
        "s_over_sbar": {m: [min(r["s_over_sbar_quantiles"]["0.0"] for r in ok if r["method"] == m),
                            float(np.median([r["s_over_sbar_quantiles"]["0.5"] for r in ok if r["method"] == m])),
                            max(r["s_over_sbar_quantiles"]["1.0"] for r in ok if r["method"] == m)]
                        for m in sorted({r["method"] for r in ok if "s_over_sbar_quantiles" in r})},
        "descriptive_pairs": {f"{a}-{b}": describe(a, b) for a, b in DESCRIPTIVE_PAIRS},
    }
    if width != DESIGN_W:
        return out
    # Design checks (expected to pass by construction; not hypothesis tests).
    h1_p = {p: t_pvalue(paired(p, cf), "less") for p in H1_POLICIES}
    h1 = holm(h1_p)
    h2 = {}
    for a, b in EQUIVALENCE_PAIRS:
        d = paired(a, b)
        half = stats.t.ppf(0.95, len(d) - 1) * d.std(ddof=1) / math.sqrt(len(d))
        h2[f"{a}-{b}"] = {"n": len(d), "mean": float(d.mean()), "ci90": [float(d.mean() - half), float(d.mean() + half)],
                          "equivalent": bool(-DELTA_MARGIN < d.mean() - half and d.mean() + half < DELTA_MARGIN)}
    frozen = [r for r in runs if r["method"] == "frozen_reference"]
    certified = [r for r in runs if r["method"] in CERTIFIED]
    out["design_checks"] = {
        "H1": {p: {"p_one_sided": h1_p[p], "holm_reject": h1[p]} for p in H1_POLICIES}, "H1_holds": all(h1.values()),
        "H2_delta": DELTA_MARGIN, "H2": h2, "H2_holds": all(v["equivalent"] for v in h2.values()),
        "H3_frozen_runs_below_cap": sum(not r.get("crashed") and r["frozen_form_bound"] < r["cap"] for r in frozen),
        "H3_frozen_runs": len(frozen),
        "H3_holds": bool(frozen) and all(not r.get("crashed") and r["frozen_form_bound"] < r["cap"] for r in frozen),
        "A5_below_cap_runs": [sum(not r.get("crashed") and r["A5"] < r["cap"] for r in certified), len(certified)],
    }
    # Primary family: two-sided paired t, Holm over the two comparisons. A pair with fewer than two
    # seeds is reported unavailable and enters Holm with p = 1, so the family size stays 2.
    p = {f"{a}-{b}": t_pvalue(paired(a, b)) for a, b in PRIMARY_PAIRS}
    reject = holm(p)
    out["primary"] = {f"{a}-{b}": {**(describe(a, b) or {"n": 0}), "available": len(paired(a, b)) >= 2,
                                   "p_two_sided": p[f"{a}-{b}"], "holm_reject": reject[f"{a}-{b}"]}
                      for a, b in PRIMARY_PAIRS}
    return out


def evaluate(runs: list[dict]) -> dict:
    """Refuses inputs that would pair runs across optimizer settings or phases, or duplicate a run."""
    configs = {(r["spec"]["learning_rate"], r["spec"]["steps_per_round"]) for r in runs}
    phases = {r.get("phase") for r in runs}
    keys = [(round(r["spec"]["c"] * r["spec"]["horizon"], 9), r["method"], r["seed"]) for r in runs]
    if len(configs) > 1 or len(phases) > 1 or len(keys) != len(set(keys)):
        raise SystemExit(f"invalid input: optimizers {sorted(configs)}, phases {sorted(map(str, phases))}, "
                         f"{len(keys) - len(set(keys))} duplicate W/method/seed records")
    cells = defaultdict(list)
    for r in runs:
        cells[round(r["spec"]["c"] * r["spec"]["horizon"], 9)].append(r)
    return {f"W={w:g}": analyze_cell(rs, w) for w, rs in sorted(cells.items(), reverse=True)}


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
