#!/usr/bin/env python3
"""Render new follow-up tables from preserved machine artifacts; no experiments."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
METHODS = ("transport_hessian", "transport_endpoint", "frozen_reference", "naive_current")
NAMES = {"transport_hessian": "Hessian", "transport_endpoint": "Endpoint",
         "frozen_reference": "Frozen reference", "naive_current": "Naive current"}
WIDTHS = (16.0, 1.0, 0.25)


def load(path):
    return json.loads(path.read_text())


def digest(path, root):
    """Attribute historical inputs after independently validating anonymous bytes.

    The table comments describe the original evidence used to produce the
    reported results.  Anonymous metadata copies have separate packaged hashes
    in FOLLOWUP_ANONYMIZATION.json; they must never silently replace those
    original attributions.  The contract validates the complete packaged input
    set before it permits this original-digest lookup.
    """
    if (root / "ANONYMIZATION.json").is_file():
        import anonymous_package_contract as contract
        module_path = root / "tools/followup_anonymous_contract.py"
        expected = contract.SHIPPED_TOOL_DIGESTS.get("tools/followup_anonymous_contract.py")
        require(module_path.is_file() and not module_path.is_symlink()
                and hashlib.sha256(module_path.read_bytes()).hexdigest() == expected,
                "The packaged follow-up contract module is missing or differs from its independent pin.")
        spec = importlib.util.spec_from_file_location("followup_generator_contract", module_path)
        require(spec is not None and spec.loader is not None, "Cannot load the pinned follow-up contract.")
        followup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(followup)
        relative = str(path.relative_to(root))
        if relative in followup.FOLLOWUP_CONTRACT:
            return followup.original_digest(root, relative)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return f"{value:g}"


def scientific(value):
    coefficient, exponent = f"{value:.2e}".split("e")
    return "$" + coefficient + r"\times10^{" + str(int(exponent)) + "}$"


def tabular(columns, header, rows):
    return (r"\begin{tabular}{@{}" + columns + "@{}}\n" + r"\toprule" + "\n"
            + header + r" \\" + "\n" + r"\midrule" + "\n"
            + "\n".join(rows) + "\n" + r"\bottomrule" + "\n" + r"\end{tabular}" + "\n")


def build(root: Path | None = None):
    root = ROOT if root is None else Path(root).resolve()
    full = root / "review/transport_review_followup/full-cce-full-local"
    independent = root / "review/post_full_fable/independent"
    relative = root / "review/transport_relative_diagnostics/full"
    inputs = [full / name for name in ("aggregate_compact.json", "drift_and_reference_diagnostics.json",
              "terminal_bound_decomposition.json", "round_drift_summaries.jsonl", "seed_summaries.jsonl")]
    inputs += [independent / "analysis.json", relative / "analysis.json", relative / "per_seed.jsonl",
               root / "tools/make_transport_followup_paper.py"]
    aggregate = load(inputs[0])
    diagnostics = load(inputs[1])
    decomposition = load(inputs[2])
    rounds = [json.loads(line) for line in inputs[3].read_text().splitlines()]
    seeds = [json.loads(line) for line in inputs[4].read_text().splitlines()]
    analysis = load(independent / "analysis.json")
    require(aggregate["completed_run_count"] == 600 and aggregate["full_grid_complete"], "Full evaluation is incomplete.")
    require(len(seeds) == 600 and all(row["simultaneous_reference_confidence"]
            and row["simultaneous_method_optimism"] and row["deterministic_audit_passed"] for row in seeds),
            "The all-policy confidence/optimism statement changed.")
    by_target = {row["target_D"]: row["W"] for row in diagnostics}
    outcomes = {(by_target[row["target_D"]], row["method"]): row for row in aggregate["policy_outcomes"]}
    require(set(outcomes) == {(width, method) for width in WIDTHS for method in METHODS}, "Unexpected outcome grid.")
    rows = []
    for index, width in enumerate(WIDTHS):
        if index:
            rows.append(r"\addlinespace")
        for method in METHODS:
            row = outcomes[width, method]
            mean = row["cumulative_pseudo_regret"]["mean"]
            paired = row["paired_difference_from_transport_hessian"]["bootstrap_mean_interval"]
            if method == "transport_hessian":
                difference, interval = "---", "---"
            else:
                require(paired["ci_high"] < 0, "A comparison interval no longer excludes zero in the stated direction.")
                difference = f"{paired['mean']:.2f}"
                interval = f"[{paired['ci_low']:.2f}, {paired['ci_high']:.2f}]"
            rows.append(f"{number(width)} & {NAMES[method]} & {mean:.2f} & {difference} & {interval}" + r" \\")
    outputs = {"transport_followup_outcomes.tex": tabular("rlrrl",
        r"$W$ & Policy & Mean regret & Paired $\Delta$ & Pointwise 95\% CI", rows)}
    rows = []
    for width in WIDTHS:
        primary = next(row for row in diagnostics if row["W"] == width and row["method"] == "transport_hessian")
        frozen = next(row for row in diagnostics if row["W"] == width and row["method"] == "frozen_reference")
        components = next(row for row in decomposition if row["target_D"] == primary["target_D"])
        members = [row for row in rounds if row["W"] == width and row["method"] == "transport_hessian"]
        require(len(members) == 50 and sum(row["round_count"] for row in members) == 50000, "Unexpected drift denominator.")
        counts = [sum(row["endpoint_at_least_threshold_counts"][threshold] for row in members) for threshold in ("0.01", "0.1", "1.0")]
        frozen_mean = f"{frozen['reference_geometry_rhs_mean_on_own_trajectory']:,.0f}".replace(",", r"\,")
        rows.append(f"{number(width)} & {primary['endpoint_maximum_across_seeds']:.3f} & "
            + "/".join(map(str, counts)) + " & " + scientific(components["sharp_theorem_rhs"])
            + f" & ${frozen_mean}$ & {primary['deterministic_regret_cap']:.0f}" + r" \\")
    outputs["transport_followup_drift_bounds.tex"] = tabular("rrrrrr",
        r"$W$ & \shortstack{Max.\\$d_{\rm Th}$} & \shortstack{Rounds at least\\$0.01\,/\,0.1\,/\,1$} & \shortstack{Mean RHS\\Hessian} & \shortstack{Mean RHS\\frozen policy} & Cap", rows)
    groups = {(row["W"], row["behavior_method"]): row for row in analysis["groups"]}
    require(set(groups) == set(outcomes) and analysis["raw_rounds"] == 600000, "Unexpected exploratory state grid.")
    rows = []
    for index, width in enumerate(WIDTHS):
        if index:
            rows.append(r"\addlinespace")
        for behavior in METHODS:
            values = groups[width, behavior]["same_history_recommendations"]["mean_one_step_pseudo_regret"]
            formatted = []
            for method in METHODS:
                value = f"{values[method]:.6f}"
                formatted.append(r"\textbf{" + value + "}" if method == behavior else value)
            rows.append(f"{number(width)} & {NAMES[behavior]} & " + " & ".join(formatted) + r" \\")
    outputs["transport_followup_same_history.tex"] = tabular("rlrrrr",
        r"$W$ & Logged behavior & Hessian & Endpoint & Frozen & Naive", rows)
    audit = load(relative / "analysis.json")
    require(audit["complete_600_trajectory_audit"] and audit["rounds"] == 600000
            and not audit["new_adaptive_experiments"]
            and not audit["floating_point_checks_are_verified_certificates"], "Unexpected relative-audit scope.")
    relative_groups = {(row["W"], row["behavior_method"]): row for row in audit["groups"]}
    require(set(relative_groups) == set(groups), "Unexpected relative-audit grid.")
    relative_seeds = [json.loads(line) for line in (relative / "per_seed.jsonl").read_text().splitlines()]
    require(len(relative_seeds) == 600, "Incomplete relative-audit seed export.")
    require(max(audit["maximum_residual_or_excess_over_original_tolerance"].values()) <= 1.0,
            "A relative-audit check exceeds its original tolerance.")
    rows = []
    for index, width in enumerate(WIDTHS):
        if index:
            rows.append(r"\addlinespace")
        for behavior in METHODS:
            group = relative_groups[width, behavior]
            require(len(group["seeds"]) == 50 and group["rounds"] == 50000, "Unexpected per-seed denominator.")
            variation = group["seed_fraction_variation"]["transport_hessian"]
            seed_rows = [row for row in relative_seeds if row["W"] == width and row["behavior_method"] == behavior]
            require({row["seed"] for row in seed_rows} == set(group["seeds"]) and len(seed_rows) == 50,
                    "Relative-audit seed identities differ.")
            formatted = []
            for metric in ("width_argmax_first_matches", "strict_width_dominance_sufficient"):
                values = variation[metric]
                require(values["count"] == 50, "Unexpected seed variation count.")
                fractions = [row["diagnostic_counts"]["transport_hessian"][metric] / row["rounds"] for row in seed_rows]
                expected = {"min": min(fractions), "median": statistics.median(fractions), "max": max(fractions)}
                require(all(math.isclose(values[key], value, rel_tol=1e-12, abs_tol=1e-14)
                            for key, value in expected.items()), "Per-seed variation does not reproduce.")
                formatted.append(f"{100*values['median']:.1f} [{100*values['min']:.1f}, {100*values['max']:.1f}]")
            rows.append(f"{number(width)} & {NAMES[behavior]} & " + " & ".join(formatted) + r" \\")
    outputs["transport_followup_mechanism_variation.tex"] = tabular("rlrr",
        r"$W$ & Logged behavior & \shortstack{Width argmax (\%)\\Median [min, max]} & \shortstack{Strict condition (\%)\\Median [min, max]}", rows)
    relative_methods = ("transport_endpoint", "uniform_endpoint", "category_symmetric", "category_asymmetric")
    rows = [r"\multicolumn{5}{c}{Mean effective width / reference width} \\", r"\addlinespace"]
    for width in WIDTHS:
        group = relative_groups[width, "transport_hessian"]
        values = [group["width_overhead_seed_mean_variation"][name]["mean"] for name in relative_methods]
        rows.append(f"{number(width)} & " + " & ".join(f"{value:.4f}" for value in values) + r" \\")
    rows += [r"\addlinespace", r"\multicolumn{5}{c}{Mean one-step pseudo-regret on the same fixed states} \\", r"\addlinespace"]
    for width in WIDTHS:
        group = relative_groups[width, "transport_hessian"]
        values = [group["same_history_mean_one_step_regret"][name]["mean"] for name in relative_methods]
        rows.append(f"{number(width)} & " + " & ".join(f"{value:.6f}" for value in values) + r" \\")
    outputs["transport_followup_relative_audit.tex"] = tabular("rrrrr",
        r"$W$ & Dense endpoint & Uniform & Category symmetric & Category asymmetric", rows)
    inventory = [{"path": str(path.relative_to(root)), "sha256": digest(path, root)} for path in sorted(inputs)]
    header = "% Generated by tools/make_transport_followup_paper.py; no experiments rerun.\n"
    header += "".join(f"% Input SHA-256 {entry['sha256']}  {entry['path']}\n" for entry in inventory)
    outputs = {name: header + content for name, content in outputs.items()}
    provenance = {"schema_version": 1, "inputs": inventory, "outputs": [
        {"path": "paper/tables/" + name, "sha256": hashlib.sha256(content.encode()).hexdigest()}
        for name, content in sorted(outputs.items())], "scope": "Prespecified full-study tables and separately labeled exploratory same-history diagnostics."}
    outputs["transport_followup_provenance.json"] = json.dumps(provenance, sort_keys=True, indent=2) + "\n"
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify generated bytes without writing.")
    args = parser.parse_args()
    outputs = build()
    for name, content in outputs.items():
        destination = ROOT / "paper/tables" / name
        if args.check:
            require(destination.is_file() and destination.read_text() == content, f"Generated artifact differs: {destination}")
        else:
            destination.write_text(content)
    print(f"{'Verified' if args.check else 'Generated'} {len(outputs)} follow-up artifacts; historical artifacts unchanged.")


if __name__ == "__main__":
    main()
