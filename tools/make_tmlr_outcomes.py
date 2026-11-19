#!/usr/bin/env python3
"""Render terminal outcomes from retained seeds; --check also replays bootstrap.

Equivalent outcome-table renderer to make_transport_followup_paper.py in the
locally inspected scientific source. Imports no experiment implementation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "review/transport_review_followup/full-cce-full-local"
OUTPUT = ROOT / "paper/figures"
METHODS = ("transport_hessian", "transport_endpoint", "frozen_reference", "naive_current")
NAMES = ("Hessian-path transport", "Endpoint transport", "Frozen reference", "Naive current")
WIDTHS = (16.0, 1.0, 0.25)
# Pins refer to bytes copied unchanged from the inspected local scientific ref.
INPUT_HASHES = {
    "seed_summaries.jsonl": "e1c4935f879df7418a2a115692113d90e50d6e50e3819cbe3ad29ce40a9afc60",
    "execution_config.json": "be6e253b68970de29d2b18ca27413d3551f00d0dbca75eb168379ab3d9b0cae3",
}
CSV_HASHES = {
    "transport_explanatory_outcomes.csv": "0779da05a7a0945531a1bff8c34bb4f88dcdf3829eebfffe79b3ae360307a7fe",
    "transport_explanatory_paired.csv": "c5e92e0c7158419edfacc2b4b51576aa9c7197ba87958261d37beec44a032266",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(actual, expected, label):
    require(math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10),
            f"{label}: artifact={actual!r}, recomputed={expected!r}")


def build(check_bootstrap=False, root=ROOT):
    import anonymous_package_contract as contract
    source = Path(root) / SOURCE.relative_to(ROOT)
    output = Path(root) / OUTPUT.relative_to(ROOT)
    for name, pin in INPUT_HASHES.items():
        require(not contract.package_required(None) or contract.is_packaged_tree(Path(root)),
                "Required anonymous package declaration is missing")
        actual = (contract.load_followup_contract(Path(root)).original_digest(Path(root), str(SOURCE.relative_to(ROOT) / name))
                  if contract.is_packaged_tree(Path(root)) else hashlib.sha256((source / name).read_bytes()).hexdigest())
        require(actual == pin,
                f"Input hash differs: {name}")
    for name, pin in CSV_HASHES.items():
        require(hashlib.sha256((output / name).read_bytes()).hexdigest() == pin,
                f"CSV input hash differs: {name}")
    config = json.loads((source / "execution_config.json").read_text())
    seeds = [json.loads(line) for line in (source / "seed_summaries.jsonl").read_text().splitlines()]
    expected_seeds = config["seed_sets"]["evaluation"]
    require(len(seeds) == 600 and len(expected_seeds) == 50, "Incomplete evaluation grid")
    require(all(row["horizon"] == 1000 and row["phase"] == "evaluation"
                and row["simultaneous_reference_confidence"]
                and row["simultaneous_method_optimism"] and row["deterministic_audit_passed"]
                for row in seeds), "Evaluation identity or all-policy checks changed")
    by_key = {(row["W"], row["method"], row["seed"]): row for row in seeds}
    require(len(by_key) == 600, "Duplicate seeds")
    targets = {row["W"]: row["target_D"] for row in seeds}
    outcomes = {(float(row["W"]), row["method"]): row for row in csv.DictReader((output / "transport_explanatory_outcomes.csv").read_text().splitlines())}
    paired_rows = {(float(row["W"]), row["method"]): row for row in csv.DictReader((output / "transport_explanatory_paired.csv").read_text().splitlines())}
    require(len(outcomes) == 12 and len(paired_rows) == 9, "Unexpected chart grid")
    require(config["statistics"]["paired_bootstrap_resamples"] == 10000
            and config["statistics"]["paired_bootstrap_level"] == 0.95, "Bootstrap settings changed")
    canonical_config = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    config_digest = hashlib.sha256(canonical_config).hexdigest()
    require(all(row["config_digest"] == config_digest for row in seeds), "Seed/config binding differs")
    if check_bootstrap:
        import numpy as np
    rows = []
    for i, width in enumerate(WIDTHS):
        if i:
            rows.append(r"\addlinespace")
        reference = [by_key[width, METHODS[0], seed]["cumulative_pseudo_regret"] for seed in expected_seeds]
        if check_bootstrap:
            payload = [int(config_digest[:16], 16), "transport_instantiation", "bootstrap", 1000, targets[width]]
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
            child = int.from_bytes(hashlib.sha256(canonical).digest()[:4], "big")
            indices = np.random.default_rng(child).integers(0, 50, size=(10000, 50), dtype=np.int64)
        for method, name in zip(METHODS, NAMES):
            values = [by_key[width, method, seed]["cumulative_pseudo_regret"] for seed in expected_seeds]
            differences = [a-b for a,b in zip(values, reference)]
            outcome = outcomes[width, method]
            mean = statistics.mean(values)
            close(float(outcome["mean_regret"]), mean, f"{width} {method} mean")
            if method == METHODS[0]:
                difference, interval_text = "---", "---"
            else:
                paired = paired_rows[width, method]
                require(float(paired["level"]) == 0.95 and int(paired["resamples"]) == 10000,
                        "Chart bootstrap protocol differs")
                close(float(paired["mean_difference"]), statistics.mean(differences), f"{width} {method} paired mean")
                if check_bootstrap:
                    samples = np.asarray(differences, dtype=np.float64)
                    alpha = (1.0 - 0.95) / 2.0
                    low, high = np.quantile(np.mean(samples[indices], axis=1), (alpha, 1-alpha))
                    close(float(paired["ci_low"]), float(low), f"{width} {method} CI low")
                    close(float(paired["ci_high"]), float(high), f"{width} {method} CI high")
                require(float(paired["ci_high"]) < 0, "A comparator interval no longer favors the comparator")
                difference = f"{statistics.mean(differences):.2f}"
                interval_text = f"[{float(paired['ci_low']):.2f}, {float(paired['ci_high']):.2f}]"
            rows.append(f"{width:g} & {name} & {mean:.2f} & {difference} & {interval_text}" + r" \\")
    table = ("% Terminal policy outcomes; regeneration is documented in BUILD.md.\n"
             + r"\begin{tabular}{@{}rlrrl@{}}" + "\n" + r"\toprule" + "\n"
             + r"$W$ & Policy & Mean regret & Paired $\Delta$ & Pointwise 95\% CI \\" + "\n"
             + r"\midrule" + "\n" + "\n".join(rows) + "\n" + r"\bottomrule" + "\n"
             + r"\end{tabular}" + "\n")
    provenance = {
        "inputs": [{"path": "review/transport_review_followup/full-cce-full-local/"+name, "sha256": pin}
                   for name,pin in sorted(INPUT_HASHES.items())] +
                  [{"path": "paper/figures/"+name,
                    "sha256": pin}
                   for name, pin in sorted(CSV_HASHES.items())],
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "output": "paper/figures/transport_followup_outcomes.tex",
        "output_sha256": hashlib.sha256(table.encode()).hexdigest(),
        "scope": "Terminal means from unchanged per-seed exports; stored paired intervals independently replayed by --check. No raw-trajectory reproduction.",
    }
    return {"transport_followup_outcomes.tex": table,
            "transport_outcomes_provenance.json": json.dumps(provenance, indent=2, sort_keys=True)+"\n"}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args=parser.parse_args()
    outputs=build(check_bootstrap=args.check, root=args.root)
    for name,content in outputs.items():
        path=args.root/OUTPUT.relative_to(ROOT)/name
        if args.check:
            require(path.read_text()==content, f"Generated artifact differs: {path}")
        else:
            path.write_text(content)
    print("PASS: 12 means, 9 paired differences, 2 generated artifacts" +
          ("; 9 paired intervals independently replayed" if args.check else "; bootstrap replay not executed"))


if __name__ == "__main__":
    main()
