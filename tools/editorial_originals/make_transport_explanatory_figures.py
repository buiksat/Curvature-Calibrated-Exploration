#!/usr/bin/env python3
"""Generate explanatory follow-up figures from retained evidence; no experiments."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path

import anonymous_package_contract as package_contract

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = Path("paper/figures")
FULL = Path("review/transport_review_followup/full-cce-full-local")
INPUT_HASHES = {
    FULL / "aggregate_compact.json": "f28acc2d601d7524f5b30a55f396c5408a7f37a26fd36bde49a3477024bc6658",
    FULL / "drift_and_reference_diagnostics.json": "fb3293daacba3511ca5f3269d67e9aa0f0aca2708ad9876661ca062e197a59a4",
    FULL / "terminal_bound_decomposition.json": "b1a6e9c5d8cfe70d3c3e3bb7cbd818502c21bb3b2f276426702cb016db323ecc",
}
CONDITIONS = ((16.0, 97.32420048477151), (1.0, 389.29680193908604),
              (0.25, 778.5936038781721))
METHODS = ("transport_hessian", "transport_endpoint", "frozen_reference", "naive_current")
NAMES = ("Hessian", "Endpoint", "Frozen reference", "Naive current")
COLORS = ("exHessian", "exEndpoint", "exFrozen", "exNaive")
MARKS = ("*", "triangle*", "square*", "diamond*")
PALETTE = r"""\definecolor{exHessian}{HTML}{D55E00}
\definecolor{exEndpoint}{HTML}{0072B2}
\definecolor{exFrozen}{HTML}{009E73}
\definecolor{exNaive}{HTML}{CC79A7}
"""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def original_digest(path: Path, root: Path) -> str:
    """Require the independently authenticated metadata contract in packages."""
    require(not package_contract.package_required(None) or package_contract.is_packaged_tree(root),
            "Required anonymous package declaration is missing")
    if package_contract.is_packaged_tree(root):
        helper = package_contract.load_followup_contract(root)
        return helper.original_digest(root, str(path.relative_to(root)))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_row(rows, **selectors):
    matches = [row for row in rows if all(row[key] == value for key, value in selectors.items())]
    require(len(matches) == 1, f"Expected one evidence row for {selectors}; found {len(matches)}")
    return matches[0]


def csv_text(fields, rows):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def number(value):
    """Round-trip representation of the stored float; no plotting-value rounding."""
    return format(float(value), ".17g")


def outcomes_tex(rows, paired):
    """Three categorical conditions; common scales within both plot columns."""
    text = PALETTE + r"""\begin{tikzpicture}
\begin{groupplot}[
  group style={group size=2 by 3,horizontal sep=0.42in,vertical sep=0.60in},
  scale only axis,width=2.30in,height=1.17in,
  /tikz/font=\normalsize,tick label style={font=\normalsize},
  label style={font=\normalsize},title style={font=\normalsize,align=center},
  axis lines=left,tick align=outside,clip=false,
  ymin=-0.5,ymax=3.5,ytick={0,1,2,3},
  yticklabels={Naive current,Frozen reference,Endpoint,Hessian},
  xmajorgrids,grid style={black!12},
]
"""
    for index, (width, _) in enumerate(CONDITIONS):
        title = r"title={(a) Mean cumulative\\pseudo-regret}," if index == 0 else ""
        xlabel = r"xlabel={Mean regret; no uncertainty bars}," if index == 2 else ""
        text += (r"\nextgroupplot[" + title + xlabel
                 + "xmin=145,xmax=190,xtick={150,170,190}]\n")
        text += r"\node[anchor=south east] at (rel axis cs:1,1.04) {$W=" + f"{width:g}" + "$};\n"
        for method_index, method in enumerate(METHODS):
            row = exact_row(rows, W=width, method=method)
            text += (r"\addplot[only marks,mark=" + MARKS[method_index]
                     + ",mark size=2.8pt,color=" + COLORS[method_index]
                     + "] coordinates {(" + number(row["mean_regret"]) + ","
                     + str(3 - method_index) + ")};\n")
        title = r"title={(b) Comparator minus Hessian\\Pointwise 95\% paired CI}," if index == 0 else ""
        xlabel = r"xlabel={Difference in mean regret}," if index == 2 else ""
        text += (r"\nextgroupplot[" + title + xlabel
                 + "xmin=-36,xmax=2,xtick={-30,-20,-10,0},yticklabels={,,,}]\n")
        text += r"\draw[densely dashed,black!65] (axis cs:0,-0.5) -- (axis cs:0,3.5);" + "\n"
        text += r"\node[anchor=east] at (rel axis cs:0.90,0.88) {Hessian $=0$};" + "\n"
        for method_index, method in enumerate(METHODS[1:], 1):
            row = exact_row(paired, W=width, method=method)
            y = str(3 - method_index)
            lo, mean, hi = (number(row[key]) for key in ("ci_low", "mean_difference", "ci_high"))
            text += (r"\addplot[no marks,line width=1pt,color=" + COLORS[method_index]
                     + "] coordinates {(" + lo + "," + y + ") (" + hi + "," + y + ")};\n")
            for end in (lo, hi):
                text += (r"\addplot[no marks,color=" + COLORS[method_index] + ",line width=1pt] "
                         + "coordinates {(" + end + "," + number(int(y) - 0.09) + ") ("
                         + end + "," + number(int(y) + 0.09) + ")};\n")
            text += (r"\addplot[only marks,mark=" + MARKS[method_index]
                     + ",mark size=1.5pt,color=" + COLORS[method_index]
                     + "] coordinates {(" + mean + "," + y + ")};\n")
    text += r"""\end{groupplot}
\end{tikzpicture}
\par\medskip
\noindent\begin{minipage}{\linewidth}
\raggedright
$T=1000$; 50 paired seeds per condition; separate adaptive histories.
All nine intervals: 10,000 paired bootstrap resamples, pointwise 95\%,
without multiplicity adjustment. Negative differences favor the comparator.
The $W$ conditions change the reward task as well as curvature.
\end{minipage}
"""
    return text


def bounds_tex(rows):
    text = PALETTE + r"""\begin{tikzpicture}
\begin{axis}[
  scale only axis,width=5.55in,height=2.40in,
  /tikz/font=\normalsize,tick label style={font=\normalsize},
  label style={font=\normalsize},
  axis lines=left,tick align=outside,clip=false,
  xmin=-2,xmax=85,xtick={0,20,40,60,80},
  ymin=-0.4,ymax=2.6,ytick={0,1,2},yticklabels={$W=0.25$,$W=1$,$W=16$},
  xlabel={$\log_{10}(\text{arithmetic mean terminal RHS}/\text{cap})$},
  xmajorgrids,grid style={black!12},
  legend style={draw=none,at={(0.5,1.17)},anchor=south,legend columns=2,
    font=\normalsize,/tikz/every even column/.append style={column sep=12pt}},
]
\draw[densely dashed,black!65] (axis cs:0,-0.4) -- (axis cs:0,2.5);
\node[anchor=south west] at (axis cs:0,2.5) {cap};
"""
    for method, color, mark, label, offset in (
            ("transport_hessian", COLORS[0], MARKS[0], "Hessian", 0.11),
            ("frozen_reference", COLORS[2], MARKS[2], "Frozen reference", -0.11)):
        coordinates = []
        for index, (width, _) in enumerate(CONDITIONS):
            row = exact_row(rows, W=width, method=method)
            coordinates.append("(" + number(row["log10_mean_rhs_over_cap"]) + ","
                               + number(2 - index + offset) + ")")
        text += (r"\addplot[only marks,mark=" + mark + ",mark size=3.2pt,color=" + color
                 + "] coordinates {" + " ".join(coordinates) + "};\n"
                 + r"\addlegendentry{" + label + "}\n")
    text += r"""\end{axis}
\end{tikzpicture}
\par\medskip
\noindent\begin{minipage}{\linewidth}
\raggedright
$T=1000$; arithmetic means over each policy's own 50 histories.
The axis shows the logarithm of a mean ratio, not the mean of logarithms.
Positive values exceed the deterministic cap. Caps are 2000, 2000 and 1000
at $W=16,1,0.25$, respectively. No uncertainty intervals are plotted.
\end{minipage}
"""
    return text


def build(root: Path | None = None) -> dict[Path, str]:
    root = ROOT if root is None else Path(root).resolve()
    inputs = []
    for relative, expected in sorted(INPUT_HASHES.items()):
        require(original_digest(root / relative, root) == expected,
                f"Unreviewed figure input: {relative}")
        inputs.append({"path": relative.as_posix(), "original_sha256": expected})
    aggregate, diagnostics, decomposition = (
        json.loads((root / FULL / name).read_text()) for name in (
            "aggregate_compact.json", "drift_and_reference_diagnostics.json",
            "terminal_bound_decomposition.json"))
    require(aggregate["full_grid_complete"] and aggregate["completed_run_count"] == 600,
            "Incomplete follow-up evaluation")
    require(len(aggregate["policy_outcomes"]) == 12, "Unexpected outcome grid")
    outcomes, paired, bounds = [], [], []
    for width, target in CONDITIONS:
        for method in METHODS:
            row = exact_row(aggregate["policy_outcomes"], horizon=1000, target_D=target, method=method)
            require(row["run_count"] == row["cumulative_pseudo_regret"]["n"] == 50,
                    "Unexpected outcome replication count")
            outcomes.append({"W": width, "target_D": target, "horizon": 1000,
                             "method": method, "n": 50,
                             "mean_regret": row["cumulative_pseudo_regret"]["mean"]})
            if method != METHODS[0]:
                interval = row["paired_difference_from_transport_hessian"]["bootstrap_mean_interval"]
                require(row["paired_difference_from_transport_hessian"]["n"] == 50
                        and interval["level"] == 0.95 and interval["resamples"] == 10000,
                        "Unexpected paired interval definition")
                require(interval["ci_low"] <= interval["mean"] <= interval["ci_high"],
                        "Malformed paired interval")
                paired.append({"W": width, "target_D": target, "horizon": 1000,
                               "method": method, "n": 50, "mean_difference": interval["mean"],
                               "ci_low": interval["ci_low"], "ci_high": interval["ci_high"],
                               "level": interval["level"], "resamples": interval["resamples"]})
        primary = exact_row(decomposition, horizon=1000, round=1000, target_D=target)
        for method in (METHODS[0], METHODS[2]):
            diagnostic = exact_row(diagnostics, horizon=1000, W=width, method=method)
            require(diagnostic["target_D"] == target and diagnostic["seeds"] == 50,
                    "Unexpected bound condition or replication count")
            cap = diagnostic["deterministic_regret_cap"]
            require(cap == 2000 * min(1, math.sqrt(width)), "Unexpected regret cap")
            rhs = (primary["sharp_theorem_rhs"] if method == METHODS[0] else
                   diagnostic["reference_geometry_rhs_mean_on_own_trajectory"])
            require(math.isfinite(rhs) and rhs > 0, "Invalid bound mean")
            ratio = rhs / cap
            bounds.append({"W": width, "target_D": target, "horizon": 1000,
                           "method": method, "n": 50, "mean_terminal_rhs": rhs,
                           "deterministic_cap": cap, "mean_rhs_over_cap": ratio,
                           "log10_mean_rhs_over_cap": math.log10(ratio)})
    require(len(outcomes) == 12 and len(paired) == 9 and len(bounds) == 6,
            "Unexpected explanatory figure population")
    header = "% Generated by tools/make_transport_explanatory_figures.py; no experiments rerun.\n"
    header += "".join(f"% Original input SHA-256 {row['original_sha256']}  {row['path']}\n" for row in inputs)
    outputs = {
        "transport_explanatory_outcomes.csv": csv_text(tuple(outcomes[0]), outcomes),
        "transport_explanatory_paired.csv": csv_text(tuple(paired[0]), paired),
        "transport_explanatory_bounds.csv": csv_text(tuple(bounds[0]), bounds),
        "transport_explanatory_outcomes.tex": header + outcomes_tex(outcomes, paired),
        "transport_explanatory_bounds.tex": header + bounds_tex(bounds),
    }
    provenance = {
        "schema_version": 1,
        "scope": "Prespecified T=1000 follow-up only; all three W conditions; no new experiments.",
        "inputs": inputs,
        "generator": {"path": "tools/make_transport_explanatory_figures.py",
                      "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "outcomes": {
            "population": "Four policies, three W conditions, 50 paired evaluation seeds per cell.",
            "mean_selector": "policy_outcomes[horizon=1000,target_D,method].cumulative_pseudo_regret.mean",
            "interval_selector": "policy_outcomes[horizon=1000,target_D,method].paired_difference_from_transport_hessian.bootstrap_mean_interval",
            "interval_definition": "Pointwise 95% paired bootstrap, 10000 resamples, no multiplicity adjustment.",
            "limits": "Distinct adaptive histories; no fixed-history intervention or universal policy ordering. Descriptive mean panel has no uncertainty bars. W also changes the reward task.",
        },
        "bounds": {
            "hessian_selector": "terminal_bound_decomposition[horizon=1000,round=1000,target_D].sharp_theorem_rhs",
            "frozen_selector": "drift_and_reference_diagnostics[horizon=1000,W,method=frozen_reference].reference_geometry_rhs_mean_on_own_trajectory",
            "transformation": "log10(arithmetic mean terminal RHS / deterministic_regret_cap)",
            "limits": "Each policy's own 50 histories. Not mean(log10 ratio), not a path-removal counterfactual, and no uncertainty intervals.",
        },
        "display": "Native 10pt body-size PGFPlots; condition categories unconnected; colors and distinct markers; no bars or resizing.",
        "outputs": [{"path": str(DESTINATION / name), "sha256": hashlib.sha256(content.encode()).hexdigest()}
                    for name, content in sorted(outputs.items())],
    }
    outputs["transport_explanatory_provenance.json"] = json.dumps(provenance, indent=2, sort_keys=True) + "\n"
    return {DESTINATION / name: content for name, content in outputs.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true", help="Compare regenerated bytes without writing.")
    args = parser.parse_args()
    outputs = build(args.root)
    for relative, content in outputs.items():
        path = args.root / relative
        if args.check:
            require(path.is_file() and path.read_bytes() == content.encode(), f"Generated figure differs: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode())
    print(f"{'Verified' if args.check else 'Generated'} {len(outputs)} explanatory figure artifacts; no experiments rerun.")


if __name__ == "__main__":
    main()
