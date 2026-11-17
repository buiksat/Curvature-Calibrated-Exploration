"""Recompute every number added to the manuscript in Phase 4 and check that the paper source states it.

Run from the repository root:  python -B review/v3_results/check_paper_numbers.py
Sources: review/v3_results/{eval_runs.jsonl,eval_analysis.json,tuning_selection.json},
review/v3_audit/phase1_audit.json, the first study's committed per-seed summaries, and closed forms.
"""
import json
import math
import re
import statistics as st
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
C_H, SIGMA, LAM, DELTA = 4 / (3 * math.sqrt(3)), 0.25, 1.0, 0.05
paper = {f: re.sub(r"\s+", " ", (ROOT / "paper" / f).read_text()) for f in
         ("transport_followup.tex", "transport_followup_appendix.tex", "transport_proofs.tex", "transport_theory.tex")}
failures = []


def expect(file, text):
    if re.sub(r"\s+", " ", text) not in paper[file]:
        failures.append(f"{file}: {text!r}")


def comma(x, p):
    return f"{x:,.{p}f}"


def tex(x, p):  # table style: {,} thousands separator and $-$ minus
    return ("$-$" if x < 0 else "") + f"{abs(x):,.{p}f}".replace(",", "{,}")


F = "transport_followup.tex"
# First study (Section 6): envelopes and frozen-bound terms.
expect(F, ", ".join(f"{2 * C_H / math.sqrt(w):.3f}" for w in (16, 1)) + f" and {2 * C_H / math.sqrt(0.25):.3f}")
audit = json.loads((ROOT / "review/v3_audit/phase1_audit.json").read_text())["compact"]
ratios = [v["A1_mean_current_envelope_over_H_a"]["median"] for v in audit.values()]
expect(F, f"{100 * min(ratios):.1f}\\%--{100 * max(ratios):.1f}\\%")
summaries = [json.loads(l) for l in (ROOT / "review/transport_review_followup/full-cce-full-local/seed_summaries.jsonl").open()]
gammas = []
for w in (16.0, 1.0, 0.25):
    rs = [r for r in summaries if r["W"] == w and r["method"] == "frozen_reference"]
    assert len(rs) == 50
    terms = [round(st.median(r[k] for r in rs)) for k in
             ("statistical_bound_component", "historical_bound_component", "current_bias_cumulative")]
    expect(F, f"{terms[0]:,}, {terms[1]:,} and {terms[2]:,}")
    gammas.append(st.median(r["gamma_T"] for r in rs))
expect(F, f"about {math.floor(min(gammas))}--{math.floor(max(gammas))}")

# Second study (Section 6.1).
a = json.loads((ROOT / "review/v3_results/eval_analysis.json").read_text())
runs = [json.loads(l) for l in (ROOT / "review/v3_results/eval_runs.jsonl").open()]
assert len(runs) == 1500 and not any(r["failures"] for r in runs)
d = a["W=20000"]
pr = d["primary"]
expect(F, f"costs {pr['transport_hessian-frozen_reference']['mean']:.1f} regret units")
expect(F, f"has {-pr['ucb_glm-frozen_reference']['mean']:.1f} units less regret")
expect(F, f"UCB-GLM minus frozen is ${pr['ucb_glm-frozen_reference']['mean']:.1f}$".replace("$-", "$-"))
for key in pr:
    m, e = f"{pr[key]['p_two_sided']:.1e}".split("e")
    expect(F, f"$p={m}\\times10^{{{int(e)}}}$")
h1 = max(v["p_one_sided"] for v in d["design_checks"]["H1"].values())
m, e = f"{h1:.1e}".split("e")
expect(F, f"$p\\le{m}\\times10^{{{int(e)}}}$")
ci = [x for v in d["design_checks"]["H2"].values() for x in v["ci90"]]
assert -1.0 < min(ci) and max(ci) < 1.0 and d["design_checks"]["H2_delta"] == 3.0
expect(F, "inside $(-1.0,1.0)$")
expect(F, "$\\Delta=3.0$")
fz = [r for r in runs if r["W"] == 20000 and r["method"] == "frozen_reference"]
expect(F, f"at most {max(r['frozen_form_bound'] / r['cap'] for r in fz):.3f} of it")
gam = 6 * math.log(1 + 20000 / (6 * LAM * SIGMA ** 2))
beta = math.sqrt(gam + 2 * math.log(1 / DELTA)) + 1 + 2 * C_H * math.sqrt(20000) / (SIGMA * math.sqrt(20000))
apriori = 2 * beta * math.sqrt((SIGMA ** 2 + 1) * gam * 20000) + 4 * C_H * 20000 / math.sqrt(20000)
expect(F, f"at most {comma(apriori, 0)}, which is {apriori / 40000:.2f} of the cap")
expect(F, f"\\approx{4 * math.log(math.cosh(1 / math.sqrt(20000))) / 1e-4:.1f}\\times10^{{-4}}")
rows = {"transport_hessian": "Hessian", "transport_endpoint": "Endpoint", "frozen_reference": "Frozen reference",
        "naive_current": "Naive current", "frozen_reference_no_envelope": "Envelope-free frozen",
        "naive_current_no_envelope": "Envelope-free naive", "linucb": "Linear UCB", "ucb_glm": "UCB-GLM"}
for k, name in rows.items():  # design-cell table
    if k not in d["mean_regret"]:
        continue
    sd = st.stdev(r["regret"] for r in runs if r["W"] == 20000 and r["method"] == k)
    tail = "--- & ---" if k == "frozen_reference" else (
        lambda p: f"{tex(p['mean'], 2)} & [{tex(p['bootstrap_ci95'][0], 2)}, {tex(p['bootstrap_ci95'][1], 2)}]")(
        d["descriptive_pairs"][f"{k}-frozen_reference"])
    expect(F, f"{name} & {tex(d['mean_regret'][k], 2)} & {tex(sd, 2)} & {tail} \\\\")
expect(F, f"Context-free & {tex(d['mean_context_free'], 2)} & & & \\\\")
cells = [a[f"W={w}"] for w in (100, 10, 1)]
for k, name in rows.items():  # descriptive table
    expect(F, f"{name} & " + " & ".join(tex(c["mean_regret"][k], 1) for c in cells) + " \\\\")
expect(F, "Context-free & " + " & ".join(tex(c["mean_context_free"], 1) for c in cells) + " \\\\")
hes = [c["descriptive_pairs"]["transport_hessian-frozen_reference"]["mean"] for c in cells]
expect(F, "Hessian minus frozen & " + " & ".join(tex(x, 1) for x in hes) + " \\\\")
expect(F, f"{comma(hes[0], 1)}, {comma(hes[1], 1)} and {comma(hes[2], 1)}")
big = [max(r["frozen_form_bound"] / r["cap"] for r in runs if r["W"] == w and r["method"] == "frozen_reference")
       for w in (100.0, 10.0, 1.0)]
expect(F, "Largest frozen bound/cap & " + " & ".join(f"{x:.2f}" for x in big) + " \\\\")
fr = [c["mean_regret"]["frozen_reference"] for c in cells]
expect(F, f"(frozen: {comma(fr[0], 1)}, {comma(fr[1], 1)} and {comma(fr[2], 1)})")
expect(F, f"from {comma(min(fr), 1)}--{comma(max(fr), 1)} to")
nf = [c["mean_regret"]["frozen_reference_no_envelope"] for c in cells]
expect(F, f"to {min(nf):.1f}--{max(nf):.1f}")
low = [c["mean_regret"][k] for c in cells for k in ("frozen_reference_no_envelope", "naive_current_no_envelope", "linucb")]
expect(F, f"between {min(low):.1f} and {max(low):.1f}")
for k in ("transport_endpoint", "naive_current"):
    p = a["W=1"]["descriptive_pairs"][f"{k}-frozen_reference"]
    lo, hi = p["bootstrap_ci95"]
    expect(F, f"${p['mean']:.1f}$ ($[{lo:.1f},{hi:.1f}]$)")
for c in cells[:2]:
    for k in ("transport_endpoint", "naive_current"):
        lo, hi = c["descriptive_pairs"][f"{k}-frozen_reference"]["bootstrap_ci95"]
        assert lo < 0 < hi
gap = max(abs(c["mean_regret"][x] - c["mean_regret"][y]) for c in cells
          for x in ("frozen_reference", "transport_endpoint", "naive_current")
          for y in ("frozen_reference", "transport_endpoint", "naive_current"))
expect(F, f"at most {gap:.1f} units")
glm = [c["mean_regret"]["ucb_glm"] for c in cells]
expect(F, f"{glm[0]:.1f}, {glm[1]:.1f} and {glm[2]:.1f}")
lin1 = a["W=1"]["mean_regret"]["linucb"]
expect(F, f"about {glm[2] / lin1:.1f} times the regret of linear UCB ({lin1:.1f})")
ug = {r["W"]: r for r in runs if r["method"] == "ucb_glm"}
expect(F, f"$\\kappa={ug[1.0]['kappa']:.4f}$ makes its radius $\\alpha={ug[1.0]['alpha']:.2f}$ (against ${ug[20000.0]['alpha']:.2f}$")
taus = [r["tau"] for r in runs if r["method"] == "ucb_glm"]
expect(F, f"lasted {min(taus)} to {max(taus)} rounds")
assert sum(r["newton_failures"] for r in runs if r["method"] == "ucb_glm") == 0
checked = [r for r in runs if r.get("replay_checks")]
n = sum(1 for r in checked for c in r["replay_checks"] for k in c if k != "round")
worst = max(v[0] / v[1] for r in checked for c in r["replay_checks"] for k, v in c.items() if k != "round")
expect(F, f"In the {len(checked):,} corrected-center runs")
expect(F, f"{n:,} checks in all; the largest discrepancy was {worst:.3f} of its tolerance")
assert all(r["optimism_failure_pairs"] == 0 for r in runs if "optimism_failure_pairs" in r)

A = "transport_followup_appendix.tex"
t = json.loads((ROOT / "review/v3_results/tuning_selection.json").read_text())
mse = t["mean_mse"]
assert (t["learning_rate"], t["steps_per_round"]) == (3e-06, 5) and not t["disqualified"]
m, e = f"{min(mse.values()):.3e}".split("e")
expect(A, f"${m}\\times10^{{{int(e)}}}$")
assert max(mse.values()) / min(mse.values()) - 1 < 0.002
expect(A, "within 0.2\\% of each other")
expect(A, "difference, 12.0,")

# Phase 2 closed forms (Section 5 and Appendix A).
P = "transport_proofs.tex"
x = lambda w: 1 / math.sqrt(w)
expect(P, ", ".join(f"${math.sqrt(w) * math.log(math.cosh(x(w))) / math.tanh(x(w)):.3f}$" for w in (16, 1))
       + f" and ${math.sqrt(0.25) * math.log(math.cosh(x(0.25))) / math.tanh(x(0.25)):.3f}$")
expect(P, f"the factor is ${3 * math.sqrt(3) * SIGMA / 2:.3f}$")
expect(P, f"about ${4 * C_H / SIGMA:.1f}/\\sqrt c$")
D = [4 * C_H * math.sqrt(999) / (SIGMA * math.sqrt(w)) for w in (16, 1, 0.25)]
expect(P, f"$10^{{{math.log10(2) + D[0] / math.log(10):.1f}}}$, $10^{{{math.log10(2) + D[1] / math.log(10):.1f}}}$ and "
          f"$10^{{{math.log10(2) + D[2] / math.log(10):.1f}}}$ ($D_{{T,W}}={D[0]:.1f}$, ${D[1]:.1f}$ and ${D[2]:.1f}$)")
uni = [1 + math.cosh(x(w)) ** 4 for w in (16, 1, 0.25)]
expect(P, f"$1+\\cosh^4(1/\\sqrt W)={uni[0]:.2f}$, ${uni[1]:.2f}$ and ${uni[2]:.1f}$")
hb = [1 + math.exp(2 / w) for w in (16, 1, 0.25)]  # c = W/T, so 2/(cT) = 2/W
expect(P, f"$\\bar h$ is ${hb[0]:.2f}$, ${hb[1]:.2f}$ and ${hb[2]:.0f}$")

print("\n".join(failures) or "all manuscript numbers match their sources")
raise SystemExit(1 if failures else 0)
