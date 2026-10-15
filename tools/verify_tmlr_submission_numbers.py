#!/usr/bin/env python3
"""Executable numerical-provenance ledger for the TMLR submission candidate.

Every numerical claim in the two controlled studies and the separately labeled
exploratory diagnostics is derived here or regenerated as a table, together with

* the manuscript file and the exact literal as it is displayed there,
* the committed source file and the SHA-256 that source must have,
* the selector that pulls the value out of that source,
* the unit, the aggregation rule, and the population the value summarizes,
* the unrounded recomputed value and the display rounding.

The script then checks three separate things and refuses to conflate them:

1. every declared source file hashes to its declared value and, where a
   ``.sha256`` sidecar exists, agrees with it;
2. the recomputed value agrees with the displayed literal to within half a unit
   in the last displayed place -- not "is close", but "rounds to what is
   printed";
3. the literal really occurs in the manuscript file it is attributed to, so
   that a later edit which silently changes a number is caught.

It does not recompute anything that needs raw per-run trajectories. The original
study's per-seed inputs are unavailable; the follow-up's compact per-seed export
does permit independent terminal-bootstrap reconstruction. Checks requiring the
external raw archives are NOT EXECUTED, never passes.

Runs from the repository root or from an unpacked supplement root with the same
layout.  Exit status is nonzero if any check fails.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

AGGREGATE = Path("results/derived/transport_instantiation/full_aggregate.json")
CONFIG = Path("experiments/configs/transport_instantiation.yaml")
EXPERIMENT_TEX = Path("paper/transport_experiment.tex")
APPENDIX_TEX = Path("paper/transport_experiment_appendix.tex")
ABSTRACT_TEX = Path("submissions/tmlr_2026/main.tex")
INTRO_TEX = Path("paper/body_intro.tex")
CONCLUSION_TEX = Path("paper/body_conclusion.tex")
AVAILABILITY_TEX = Path("paper/availability.tex")
LEGACY_SCOPE_TEX = Path("paper/legacy_scope.tex")
COST_APPENDIX_TEX = Path("paper/appendix_deferred.tex")

AGGREGATE_SHA256 = "0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02"
CONFIG_SHA256 = "d6f6c0de47651a7e6a291f63ba609654afd5cff6cc13d11722d9fae587e7abdd"

# The completed follow-up is a distinct population. Its exported seed summaries
# permit terminal bootstrap reconstruction; they do not replace absent raw logs.
FOLLOWUP_ROOT = Path("review/transport_review_followup/full-cce-full-local")
FOLLOWUP_CONFIG = FOLLOWUP_ROOT / "execution_config.json"
FOLLOWUP_AGGREGATE = FOLLOWUP_ROOT / "aggregate_compact.json"
FOLLOWUP_SEEDS = FOLLOWUP_ROOT / "seed_summaries.jsonl"
FOLLOWUP_ROUNDS = FOLLOWUP_ROOT / "round_drift_summaries.jsonl"
FOLLOWUP_DIAGNOSTICS = FOLLOWUP_ROOT / "drift_and_reference_diagnostics.json"
FOLLOWUP_DECOMPOSITION = FOLLOWUP_ROOT / "terminal_bound_decomposition.json"
FOLLOWUP_ANALYSIS = Path("review/post_full_fable/independent/analysis.json")
FOLLOWUP_TEX = Path("paper/transport_followup.tex")
FOLLOWUP_APPENDIX_TEX = Path("paper/transport_followup_appendix.tex")
FOLLOWUP_GENERATOR = Path("tools/make_transport_followup_paper.py")
TABLE_CHART_GENERATOR = Path("tools/make_transport_table_charts.py")
EXPLANATORY_GENERATOR = Path("tools/make_transport_explanatory_figures.py")
FOLLOWUP_EXPORT_VERIFIER = Path("tools/verify_review_experiment_export.py")
FOLLOWUP_PACKAGE_CONTRACT = Path("tools/followup_anonymous_contract.py")
RELATIVE_ROOT = Path("review/transport_relative_diagnostics/full")
RELATIVE_ANALYSIS = RELATIVE_ROOT / "analysis.json"
RELATIVE_SEEDS = RELATIVE_ROOT / "per_seed.jsonl"
FOLLOWUP_SOURCE_HASHES = {
    TABLE_CHART_GENERATOR: 'ed0e3fb6b1e5449009fa4a9f0a2850e32c205ce2bbd47923958039512ce6e479',
    EXPLANATORY_GENERATOR: '464083a92053499c9dacba950707a3cbd4749fe0e908531c06b27da5e5b43150',
    FOLLOWUP_CONFIG: "be6e253b68970de29d2b18ca27413d3551f00d0dbca75eb168379ab3d9b0cae3",
    FOLLOWUP_AGGREGATE: "f28acc2d601d7524f5b30a55f396c5408a7f37a26fd36bde49a3477024bc6658",
    FOLLOWUP_SEEDS: "e1c4935f879df7418a2a115692113d90e50d6e50e3819cbe3ad29ce40a9afc60",
    FOLLOWUP_ROUNDS: "9b6bda78c88074e46e1ff3c4253b9623bb95f467f068b6339bee9d83e4e4fce1",
    FOLLOWUP_DIAGNOSTICS: "fb3293daacba3511ca5f3269d67e9aa0f0aca2708ad9876661ca062e197a59a4",
    FOLLOWUP_DECOMPOSITION: "b1a6e9c5d8cfe70d3c3e3bb7cbd818502c21bb3b2f276426702cb016db323ecc",
    FOLLOWUP_ANALYSIS: "914013bf6436e82a50865d5ce3570b4195e7cdc2e4f25b436eb5b28a9b99ece3",
    FOLLOWUP_ROOT / "export_manifest.json": "adbf7ab8d401fa057999d4f98582a52f8ca5af71362efd05632345be4984eaca",
    FOLLOWUP_EXPORT_VERIFIER: "d9d3f6d0994ddceba279563f92dda946ba99f0c27c8aa5a6a83d1b267aa9fad0",
    FOLLOWUP_GENERATOR: "153da33c998c3074e6fdabb9dc241157da5ff2bf0e9f401350699fa87a540496",
    RELATIVE_ANALYSIS: "fd67cdc031c02876ed1e18ea0444a35348b4cb80bdd261b3fd3d75e6e920b29e",
    RELATIVE_SEEDS: "9d7939364bfd7737df5daaf80d43c0673828505466ede181fe31f42fe2f98bea",
    RELATIVE_ROOT / "input_inventory.jsonl": "c905bdcd58aa9c827a141ac024c49cccdba1d97bf5ad8908889b15d3f471190a",
}

# An anonymous supplement ships modified copies of some evidence files with one
# metadata string replaced.  The shipped ANONYMIZATION.json is a reviewer-visible
# claim about that, not an authority: tools/anonymous_package_contract.py pins
# the acceptable packaged digests, byte counts, token and sidecar text in code,
# and this tool measures the tree against those constants.  Where a file is
# covered by the contract it is reported as PASS_ANON rather than a plain PASS,
# so nothing here implies the reviewer holds original bytes.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import anonymous_package_contract as contract  # noqa: E402
import numeric_context_pins as pins  # noqa: E402
import tex_conditionals  # noqa: E402

STATUS_ANONYMIZED = "PASS_ANON"

PRIMARY_HORIZON = 1000

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_NOT_EXECUTED = "NOT_EXECUTED"


class LedgerError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_prose(text: str) -> str:
    """Collapse whitespace runs only, so TeX line wrapping cannot break a match."""

    return " ".join(text.split())


def tolerance_of(display: str) -> float:
    """Half a unit in the last displayed place of a decimal or mantissa literal."""

    # `{,}` first: stripping bare commas would leave `2{}000` behind.
    cleaned = display.replace("{,}", "").replace(",", "").strip()
    mantissa = cleaned
    exponent = 0
    match = re.fullmatch(r"([0-9.]+)(?:e|E|\\times10\^\{?)(-?[0-9]+)\}?", cleaned)
    if match:
        mantissa, exponent = match.group(1), int(match.group(2))
    if "." in mantissa:
        places = len(mantissa.split(".", 1)[1])
    else:
        places = 0
    return 0.5 * (10.0 ** (-places)) * (10.0**exponent)


def parse_display(display: str) -> float:
    # `{,}` first: stripping bare commas would leave `2{}000` behind.
    cleaned = display.replace("{,}", "").replace(",", "").strip()
    match = re.fullmatch(r"([0-9.]+)(?:e|E|\\times10\^\{?)(-?[0-9]+)\}?", cleaned)
    if match:
        return float(match.group(1)) * (10.0 ** int(match.group(2)))
    return float(cleaned)


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""


@dataclass
class Entry:
    """One manuscript number and everything needed to re-derive it."""

    manuscript: Path
    literal: str            # the exact string as displayed in the manuscript
    display: str            # the numeric part of that string
    source: Path
    selector: str           # human-readable description of the selector
    units: str
    aggregation: str
    population: str
    compute: Callable[[dict[str, Any], dict[str, Any]], float]
    unrounded: float | None = field(default=None, init=False)


# --------------------------------------------------------------------------
# selectors over the locked aggregate
# --------------------------------------------------------------------------


def _cells(aggregate: dict[str, Any], section: str, horizon: int | None = None):
    rows = aggregate[section]
    if horizon is not None:
        rows = [r for r in rows if int(r["horizon"]) == horizon]
    return sorted(rows, key=lambda r: (float(r["target_D"]), int(r["horizon"])))


def _medians(aggregate, section, field_name, horizon=None):
    return [
        float(row[field_name]["median"])
        for row in _cells(aggregate, section, horizon)
        if row[field_name] is not None
    ]


def _env_means(aggregate, field_name, horizon):
    values = [
        float(row[field_name]["mean"])
        for row in _cells(aggregate, "environment_diagnostics", horizon)
    ]
    if not values:
        raise LedgerError(f"no environment diagnostics at horizon {horizon}")
    # Every target cell shares the same environment stream, so the four cell
    # means agree to display precision; take the arithmetic mean over cells.
    return math.fsum(values) / len(values)


def _unique_ci_low(aggregate) -> float:
    """The Clopper-Pearson lower limit, required to be identical in every cell."""

    values = {r["reference_confidence_coverage"]["ci_low"] for r in aggregate["validity"]}
    values |= {r["transport_optimism_coverage"]["ci_low"] for r in aggregate["validity"]}
    if len(values) != 1:
        raise LedgerError(f"coverage lower limits differ across cells: {sorted(values)}")
    return float(values.pop())


def _policy(aggregate, method, horizon, target):
    for row in aggregate["policy_outcomes"]:
        if (
            row["method"] == method
            and int(row["horizon"]) == horizon
            and abs(float(row["target_D"]) - target) < 1e-12
        ):
            return row
    raise LedgerError(f"no policy outcome for {method} at T={horizon}, D={target}")


def _terminal_decomposition(aggregate):
    """One terminal mean over 50 primary-policy runs for each target cell."""

    rows = [r for r in aggregate["bound_decomposition"]
            if int(r["horizon"]) == PRIMARY_HORIZON
            and int(r["round"]) == PRIMARY_HORIZON]
    targets = [float(r["target_D"]) for r in rows]
    if sorted(targets) != sorted(float(d) for d in aggregate["target_D"]):
        raise LedgerError("terminal decomposition does not cover each target once")
    return sorted(rows, key=lambda r: float(r["target_D"]))


def _decomposition_shares(aggregate, field_name):
    """Ratios of component means to sharp-RHS means, not means of ratios."""

    shares = []
    for row in _terminal_decomposition(aggregate):
        denominator = float(row["sharp_theorem_rhs"])
        if not math.isfinite(denominator) or denominator <= 0:
            raise LedgerError("nonpositive or nonfinite mean sharp RHS")
        shares.append(100.0 * float(row[field_name]) / denominator)
    return shares


def readme_sources(root: Path | None) -> tuple[Path, ...]:
    """Whichever supplement README this tree carries, repository or packaged.

    A repository also has a top-level `README.md`, and that one is not the
    supplement's reviewer-facing text, so the packaged name counts only in a
    packaged tree.
    """

    if root is None:
        return (SUPPLEMENT_README_REPO,)
    present = []
    if (root / SUPPLEMENT_README_REPO).is_file():
        present.append(SUPPLEMENT_README_REPO)
    if contract.is_packaged_tree(root) \
            and (root / SUPPLEMENT_README_PACKAGED).is_file():
        present.append(SUPPLEMENT_README_PACKAGED)
    return tuple(present) or (SUPPLEMENT_README_REPO,)


def _followup_group(analysis, width, method="transport_hessian"):
    return next(g for g in analysis["groups"]
                if g["W"] == width and g["behavior_method"] == method)


def _followup_tuning_count(config):
    tuning = config["representation_update"]["tuning"]
    return len(tuning["learning_rate_grid"]) * len(tuning["steps_per_round_grid"])


def _followup_pre_evaluation_count(config):
    return len(config["target_D"]) * (
        len(config["methods"]) * len(config["seed_sets"]["development"])
        + _followup_tuning_count(config) * len(config["seed_sets"]["tuning"]))


def _followup_environment_mean(aggregate, target, field_name):
    rows = [row for row in aggregate["environment_diagnostics"]
            if row["horizon"] == PRIMARY_HORIZON and row["target_D"] == target]
    if len(rows) != 1:
        raise LedgerError(f"expected one follow-up environment cell at T={PRIMARY_HORIZON}, target_D={target}")
    return float(rows[0][field_name]["mean"])


def _followup_mean_bound_ratio(seeds, width, method):
    """Arithmetic mean on the named policy's own histories, then divide by cap."""
    if method not in {"transport_hessian", "frozen_reference"}:
        raise LedgerError(f"unsupported bound policy: {method}")
    rows = [row for row in seeds if row["W"] == width
            and row["method"] == method and row["horizon"] == PRIMARY_HORIZON]
    if len(rows) != 50 or len({row["seed"] for row in rows}) != 50:
        raise LedgerError(f"expected 50 distinct terminal histories for {method}, W={width}")
    bounds = [float(row["sharp_theorem_rhs"]) if method == "transport_hessian"
              else math.fsum(float(row[key]) for key in (
                  "statistical_bound_component", "historical_bound_component",
                  "current_bias_cumulative")) for row in rows]
    if any(not math.isfinite(value) or value <= 0 for value in bounds):
        raise LedgerError("terminal bounds must be positive and finite")
    cap = 2 * PRIMARY_HORIZON * min(1.0, math.sqrt(width))
    return (math.fsum(bounds) / len(bounds)) / cap


def followup_ledger() -> list[Entry]:
    """Explicit selectors for new prose; table cells are regenerated separately."""
    entries = []
    main, appendix = FOLLOWUP_TEX, FOLLOWUP_APPENDIX_TEX
    C, A, S, D, X = (FOLLOWUP_CONFIG, FOLLOWUP_AGGREGATE, FOLLOWUP_SEEDS,
                     FOLLOWUP_DIAGNOSTICS, FOLLOWUP_ANALYSIS)

    def add(file, phrase, display, source, selector, compute, units="count"):
        entries.append(Entry(file, phrase, display, source, selector, units,
                             "explicit selector over the retained follow-up export",
                             "completed follow-up; exploratory results identified separately",
                             lambda data, _old_config: compute(data)))

    # Compute from retained per-seed evidence, independently of chart CSVs.
    # The logarithm follows the arithmetic mean; these are not mean log bounds
    # or bounds evaluated on another policy's adaptive histories.
    for width, hessian_log, frozen_ratio in (
            (16., "9.51", "19"), (1., "37.19", "60"), (.25, "80.91", "231")):
        for method, display, phrase, logarithmic in (
                ("transport_hessian", hessian_log,
                 "approximately 9.51, 37.19, and 80.91", True),
                ("frozen_reference", frozen_ratio,
                 "approximately 19, 60, and 231", False)):
            fields = ("sharp_theorem_rhs" if logarithmic else
                      "statistical_bound_component + historical_bound_component "
                      "+ current_bias_cumulative")
            entries.append(Entry(
                main, phrase, display, S,
                f"seed_summaries[method={method}, W={width}, horizon={PRIMARY_HORIZON}].{fields}",
                "base-ten log of mean bound/cap" if logarithmic else "mean bound/cap",
                "arithmetic mean of 50 terminal bounds / (2*T*min(1,sqrt(W)))"
                + (", then log10" if logarithmic else ""),
                f"50 distinct evaluation seeds on {method}'s own histories at W={width}",
                lambda data, _config, w=width, m=method, log=logarithmic:
                    math.log10(_followup_mean_bound_ratio(data, w, m)) if log
                    else _followup_mean_bound_ratio(data, w, m)))

    for file, phrase in ((main, "600 policy trajectories"),
                         (main, "All 600 evaluation trajectories"),
                         (main, "all 600 preserved trajectories"),
                         (appendix, "the 600\ntrajectories"),
                         (AVAILABILITY_TEX, "600 evaluation seed summaries")):
        add(file, phrase, "600", A, "completed_run_count", lambda a: a["completed_run_count"])
    for file, phrase in ((main, "294 development and tuning trajectories"),
                         (appendix, "294 development and tuning trajectories")):
        add(file, phrase, "294", C, "conditions * (policies * development seeds + candidates * tuning seeds)",
            _followup_pre_evaluation_count)
    for phrase in ("dimension 29", "29-parameter"):
        add(main, phrase, "29", C, "environment.feature_dimension", lambda c: c["environment"]["feature_dimension"])
    add(main, "$T=1000$", "1000", C, "reporting.primary_horizon", lambda c: c["reporting"]["primary_horizon"], "rounds")
    add(appendix, "$T=1000$", "1000", C, "reporting.primary_horizon", lambda c: c["reporting"]["primary_horizon"], "rounds")
    for phrase in (r"$W\in\{16,1,0.25\}$", "$W=16,1,0.25$"):
        for i, value in enumerate(("16", "1", "0.25")):
            add(main, phrase, value, C, f"followup.prespecified_width_W[{i}]",
                lambda c, i=i: c["followup"]["prespecified_width_W"][i], "model smoothness parameter")
    add(main, "$W=0.25$", "0.25", C, "min(followup.prespecified_width_W)",
        lambda c: min(c["followup"]["prespecified_width_W"]))
    # The prescribed W values map to these target labels in the pinned config;
    # target_D is an encoding, not an observed metric distance. Select each
    # environment cell explicitly rather than pooling different reward tasks.
    for width, target, context_free, best_fixed in (
            (16., 97.32420048477151, "185.26", "180.01"),
            (1., 389.29680193908604, "183.06", "177.97"),
            (.25, 778.5936038781721, "176.67", "171.84")):
        for field_name, phrase, display in (
                ("context_free_mean_only_regret", "regrets 185.26, 183.06, and 176.67", context_free),
                ("best_fixed_action_regret", "regrets 180.01, 177.97, and 171.84", best_fixed)):
            add(main, phrase, display, A,
                f"environment_diagnostics[horizon={PRIMARY_HORIZON}, target_D={target} (W={width})].{field_name}.mean; 50 evaluation streams",
                lambda a, t=target, k=field_name: _followup_environment_mean(a, t, k),
                "mean cumulative pseudo-regret within one condition")
    for file, phrases in ((main, ("50 common evaluation seeds", "50 seeds per condition", "50 successes out of 50", "50 histories")),
                          (appendix, ("50 evaluation seeds", "50 paired evaluation seeds"))):
        for phrase in phrases:
            add(file, phrase, "50", C, "len(seed_sets.evaluation)", lambda c: len(c["seed_sets"]["evaluation"]))
    for file in (main, appendix):
        add(file, r"learning rate $3\times10^{-4}$", "3e-4", A, "selected_optimizer.learning_rate",
            lambda a: a["selected_optimizer"]["learning_rate"], "optimizer learning rate")
        add(file, "20 " + ("full-batch steps" if file == main else "steps"), "20", A,
            "selected_optimizer.steps_per_round", lambda a: a["selected_optimizer"]["steps_per_round"])
        add(file, "10,000", "10,000", C, "statistics.paired_bootstrap_resamples",
            lambda c: c["statistics"]["paired_bootstrap_resamples"])
    for phrase in (r"paired 95\% intervals", r"pointwise 95\% paired", r"exact 95\% Clopper--Pearson interval"):
        add(main, phrase, "95", C, "100 * statistics.paired_bootstrap_level (also coverage_level)",
            lambda c: 100 * c["statistics"]["paired_bootstrap_level"], "percent")
    add(appendix, r"pointwise 95\% paired", "95", C,
        "100 * statistics.paired_bootstrap_level",
        lambda c: 100 * c["statistics"]["paired_bootstrap_level"], "percent")
    for value, key in (("92.9", "ci_low"), ("100", "ci_high")):
        add(main, r"$[92.9\%,100\%]$", value, A, f"policy_outcomes[0].simultaneous_optimism_coverage.{key} * 100",
            lambda a, k=key: 100 * a["policy_outcomes"][0]["simultaneous_optimism_coverage"][k], "percent")
    for value, fn in (("16", lambda rows: sum(r["max_endpoint_thompson_distance"] > 1 for r in rows if r["W"] == .25 and r["method"] == "transport_hessian")),
                      ("50", lambda rows: sum(r["W"] == .25 and r["method"] == "transport_hessian" for r in rows))):
        add(main, "16 of 50 seeds", value, S, "primary W=0.25 seed maxima strictly above one; count and denominator", fn)
    add(main, "286 of 50,000", "286", FOLLOWUP_ROUNDS,
        "sum primary W=.25 endpoint_at_least_threshold_counts['1.0']",
        lambda rows: sum(r["endpoint_at_least_threshold_counts"]["1.0"] for r in rows
                         if r["W"] == .25 and r["method"] == "transport_hessian"))
    for file, phrases in ((main, ("of 50,000 seed--round observations", "50,000 seed--round observations per condition")),
                          (appendix, ("50,000 dependent states",))):
        for phrase in phrases:
            add(file, phrase, "50,000", C, "primary_horizon * number evaluation seeds",
                lambda c: c["reporting"]["primary_horizon"] * len(c["seed_sets"]["evaluation"]), "dependent seed-round observations")
    for i, value in enumerate(("2000", "2000", "1000")):
        add(main, "2000, 2000, and 1000", value, C, f"2*T*min(1,sqrt(prespecified_width_W[{i}]))",
            lambda c, i=i: 2*c["reporting"]["primary_horizon"]*min(1, math.sqrt(c["followup"]["prespecified_width_W"][i])), "cumulative regret upper cap")
    add(main, "all 150 of its trajectories", "150", S, "count(method=frozen_reference)",
        lambda rows: sum(r["method"] == "frozen_reference" for r in rows))
    for i, width in enumerate((16., 1., .25)):
        for display, key in ((("99.382", "99.962", "99.982")[i], "width_argmax_first_matches"),
                             (("97.104", "99.372", "99.508")[i], "strict_width_dominance_sufficient")):
            add(main, display + r"\%", display, X, f"100 * primary W={width} {key} / rounds",
                lambda a, w=width, k=key: 100*_followup_group(a,w)["hessian_recommendation_diagnostics"]["counts"][k]
                / _followup_group(a,w)["hessian_recommendation_diagnostics"]["counts"]["rounds"], "percent of dependent rounds")
    add(appendix, "teacher seed 1729", "1729", C, "teacher.seed", lambda c: c["teacher"]["seed"], "seed identifier")
    for kind, first, last in (("development", "30000", "30001"), ("tuning", "30100", "30109"), ("evaluation", "30200", "30249")):
        for value, fn in ((first, min), (last, max)):
            add(appendix, first+"--"+last, value, C, f"{fn.__name__}(seed_sets.{kind})",
                lambda c, kind=kind, fn=fn: fn(c["seed_sets"][kind]), "seed identifier")
    for phrase in ("24 development trajectories", "24 declared trajectories"):
        add(appendix, phrase, "24", C, "conditions * policies * development seeds",
            lambda c: len(c["target_D"])*len(c["methods"])*len(c["seed_sets"]["development"]))
    add(appendix, "270 tuning trajectories", "270", C, "conditions * optimizer candidates * tuning seeds",
        lambda c: len(c["target_D"])*_followup_tuning_count(c)*len(c["seed_sets"]["tuning"]))
    for i,value in enumerate(("3e-5", "1e-4", "3e-4")):
        add(appendix, r"$\{3\times10^{-5},10^{-4},3\times10^{-4}\}$", value, C,
            f"representation_update.tuning.learning_rate_grid[{i}]", lambda c,i=i: c["representation_update"]["tuning"]["learning_rate_grid"][i])
    for i,value in enumerate(("1","5","20")):
        add(appendix, r"$\{1,5,20\}$", value, C, f"representation_update.tuning.steps_per_round_grid[{i}]",
            lambda c,i=i: c["representation_update"]["tuning"]["steps_per_round_grid"][i])
    add(appendix, "Candidate 008", "008", A, "selected_optimizer.candidate_id numeric suffix",
        lambda a: int(a["selected_optimizer"]["candidate_id"].split("-")[-1]), "candidate identifier")
    add(appendix, "30 tuning", "30", C, "conditions * tuning seeds", lambda c: len(c["target_D"])*len(c["seed_sets"]["tuning"]))
    add(appendix, "$0.00392155$", "0.00392155", A, "selected_optimizer.aggregate_mean_all_action_prediction_mse",
        lambda a: a["selected_optimizer"]["aggregate_mean_all_action_prediction_mse"], "mean squared prediction error")
    for value, fn in (("3",lambda c:len(c["target_D"])), ("4",lambda c:len(c["methods"])),
                      ("50",lambda c:len(c["seed_sets"]["evaluation"])),
                      ("600",lambda c:len(c["target_D"])*len(c["methods"])*len(c["seed_sets"]["evaluation"]))):
        add(appendix, r"$3\times4\times50=600$", value, C, "condition, policy, seed counts and their product", fn)
    for value in ("1024","2048","4096"):
        add(appendix, value, value, C, "transport.quadrature declared orders contains this exact value",
            lambda c,v=int(value): next(x for x in set(c["transport"]["quadrature"]["development_orders"]
                +c["transport"]["quadrature"]["independent_validation_orders"]) if x==v), "quadrature order")
    add(appendix, "12 combinations", "12", X, "len(groups)", lambda a: len(a["groups"]))
    add(appendix, "divided by 1000", "1000", C, "reporting.primary_horizon",lambda c:c["reporting"]["primary_horizon"])
    add(appendix,"250-digit", "250", X,"decimal_precision",lambda a:a["decimal_precision"],"decimal digits for stored-input score arithmetic")
    add(appendix,"at 16 states", "16", X,"sum primary exact_rank_first_mismatch",
        lambda a:sum(_followup_group(a,w)["hessian_recommendation_diagnostics"]["counts"]["exact_rank_first_mismatch"] for w in (16.,1.,.25)))
    add(appendix,"65 changes", "65", X,"sum all behavior exact_rank_first_mismatch",
        lambda a:sum(g["hessian_recommendation_diagnostics"]["counts"]["exact_rank_first_mismatch"] for g in a["groups"]))
    add(appendix,"600,000 states", "600,000", X,"raw_rounds",lambda a:a["raw_rounds"])
    for value,fn in (("2",min),("10",max)):
        add(appendix,"2--10",value,X,f"{fn.__name__} mismatch round over all behavior histories",
            lambda a,fn=fn:fn(r["round"] for g in a["groups"] for r in g["hessian_recommendation_diagnostics"]["stored_input_rank_mismatches"]))
    add(appendix,"below 0.629", "0.629", X,"ceil(1000 * maximum gap_in_score_ulps over all behavior histories) / 1000",
        lambda a:math.ceil(1000*max(r["gap_in_score_ulps"] for g in a["groups"]
            for r in g["hessian_recommendation_diagnostics"]["stored_input_rank_mismatches"]))/1000,"score ULP upper bound")
    add(main, "there are five actions", "5", C, "environment.action_count", lambda c:c["environment"]["action_count"])
    add(main, "standard deviation $0.25$", "0.25", C,
        "environment.noise_std", lambda c: c["environment"]["noise_std"])
    add(main, r"$\delta=0.05$", "0.05", C,
        "confidence.delta", lambda c: c["confidence"]["delta"])
    add(main, "same 600 recorded histories", "600", RELATIVE_ANALYSIS,
        "trajectories", lambda a: a["trajectories"])
    for value, fn in (("4", lambda c:c["environment"]["context_dimension"]),
                      ("5", lambda c:c["environment"]["action_count"]),
                      ("20", lambda c:c["environment"]["context_dimension"]*c["environment"]["action_count"]),
                      ("29", lambda c:c["environment"]["feature_dimension"])):
        add(appendix, "$4+5+20=29$", value, C, "context, action and tensor-product feature dimensions", fn)
    for phrase in ("1000 rounds in its denominator", "and 1000 rounds"):
        add(appendix, phrase, "1000", C, "reporting.primary_horizon", lambda c:c["reporting"]["primary_horizon"])
    for phrase in ("summarize 50 seeds", "across 50 seeds", "50 seeds per condition"):
        add(appendix, phrase, "50", C, "len(seed_sets.evaluation)", lambda c:len(c["seed_sets"]["evaluation"]))
    for width, value in ((16.,"0.124"), (1.,"1.735"), (.25,"5.300")):
        add(appendix, "$"+value+"$", value, C, f"4 log cosh(feature_bound * theta_radius / sqrt(W={width}))",
            lambda c,w=width:4*math.log(math.cosh(c["environment"]["feature_bound"]*c["teacher"]["theta_radius"]/math.sqrt(w))), "uniform endpoint bound")
    add(appendix, "all 600 trajectories", "600", RELATIVE_ANALYSIS, "trajectories", lambda a:a["trajectories"])
    for i,value in enumerate(("1","2","10","100","500","1000")):
        add(appendix, "rounds 1, 2, 10, 100, 500, and 1000", value, RELATIVE_ANALYSIS,
            f"checkpoint_rounds[{i}]", lambda a,i=i:a["checkpoint_rounds"][i], "reconstruction checkpoint")
    for method, bounds in (("category_asymmetric", ("0.28", "12.68")),
                           ("transport_endpoint", ("0.16", "12.13"))):
        for fn, value in zip((min, max), bounds):
            add(main, "$"+value+r"\%$", value, RELATIVE_ANALYSIS,
                f"{fn.__name__} over primary-history conditions of 100*(mean actionwise width ratio for {method} - 1)",
                lambda a,fn=fn,m=method:fn(100*(g["width_overhead_seed_mean_variation"][m]["mean"]-1)
                    for g in a["groups"] if g["behavior_method"]=="transport_hessian"),
                "percent overhead; mean of actionwise ratios with equal-size seed cells")
    add(appendix, "$0.005$", "0.005", RELATIVE_ANALYSIS,
        "ceil(1000 * maximum residual/original_tolerance) / 1000",
        lambda a:math.ceil(1000*max(a["maximum_residual_or_excess_over_original_tolerance"].values()))/1000,
        "upper bound on normalized floating-point diagnostic residual")
    return entries


def build_ledger(root: Path | None = None) -> list[Entry]:
    A, C = AGGREGATE, CONFIG
    e: list[Entry] = []

    def add(manuscript, literal, display, source, selector, units,
            aggregation, population, compute):
        e.append(Entry(manuscript, literal, display, source, selector, units,
                       aggregation, population, compute))

    # ---- the design grid itself, literal by literal -------------------------
    # The grids used to be summarized only through derived counts, so editing
    # a horizon or a target label in the manuscript changed no checked value.
    # Each element is now pinned to its own configuration slot, and the printed
    # set is pinned as a literal.
    for index, horizon in enumerate((250, 500, 1000)):
        add(EXPERIMENT_TEX, r"horizons $T\in\{250,500,1000\}$", str(horizon), C,
            f"base.horizons[{index}]", "rounds", "declared grid element",
            "configuration",
            lambda a, c, i=index: float(c["base"]["horizons"][i]))
    for index, target in enumerate(("0.25", "0.5", "1", "2")):
        add(EXPERIMENT_TEX,
            r"target labels $D_{\rm target}\in\{0.25,0.5,1,2\}$", target, C,
            f"base.target_D[{index}]", "dimensionless", "declared grid element",
            "configuration",
            lambda a, c, i=index: float(c["base"]["target_D"][i]))
    add(EXPERIMENT_TEX, "$T=1000$", "1000", C,
        "base.reporting.primary_horizon", "rounds", "declared constant",
        "configuration",
        lambda a, c: float(c["base"]["reporting"]["primary_horizon"]))
    add(EXPERIMENT_TEX, r"exact 95\% Clopper--Pearson interval", "95", C,
        "100 * base.statistics.coverage_level", "percent", "declared level",
        "configuration",
        lambda a, c: 100.0 * float(c["base"]["statistics"]["coverage_level"]))
    add(EXPERIMENT_TEX, r"paired-bootstrap 95\%", "95", C,
        "100 * base.statistics.paired_bootstrap_level", "percent",
        "declared level", "configuration",
        lambda a, c: 100.0
        * float(c["base"]["statistics"]["paired_bootstrap_level"]))
    add(APPENDIX_TEX, r"preregistered $10^{-12}$ ratio tolerance", "1e-12", C,
        "base.numerics.ratio_denominator_tolerance", "dimensionless",
        "declared constant", "configuration",
        lambda a, c: float(c["base"]["numerics"]["ratio_denominator_tolerance"]))

    # ---- the deterministic cap, stated as a range over the horizon grid -----
    add(EXPERIMENT_TEX, r"versus caps of $500$--$2{,}000$", "500", C,
        "2 * min(base.horizons)", "cumulative reward units",
        "deterministic cap 2T at the shortest horizon", "design grid",
        lambda a, c: 2.0 * min(float(h) for h in c["base"]["horizons"]))
    add(EXPERIMENT_TEX, r"versus caps of $500$--$2{,}000$", "2{,}000", C,
        "2 * max(base.horizons)", "cumulative reward units",
        "deterministic cap 2T at the longest horizon", "design grid",
        lambda a, c: 2.0 * max(float(h) for h in c["base"]["horizons"]))

    # ---- protocol constants, from the frozen configuration -----------------
    add(EXPERIMENT_TEX, "Contexts have dimension $4$", "4", C,
        "base.environment.context_dimension", "dimensionless", "declared constant",
        "configuration", lambda a, c: float(c["base"]["environment"]["context_dimension"]))
    add(EXPERIMENT_TEX, "there are five actions", "5", C,
        "base.environment.action_count", "dimensionless", "declared constant",
        "configuration", lambda a, c: float(c["base"]["environment"]["action_count"]))
    add(EXPERIMENT_TEX, "feature map has dimension $29$", "29", C,
        "base.environment.feature_dimension", "parameters", "declared constant",
        "configuration", lambda a, c: float(c["base"]["environment"]["feature_dimension"]))
    add(EXPERIMENT_TEX, "50 evaluation seeds", "50", A,
        "len(evaluation_seeds)", "seeds", "count",
        "evaluation seed set", lambda a, c: float(len(a["evaluation_seeds"])))
    # Every other place the manuscript restates the seed count or a population
    # size.  These used to be unchecked prose: only the first "50 evaluation
    # seeds" was in the ledger, so the rest could drift away from it silently.
    for literal in ("the 50-seed means",
                    "the same 50 base seeds",
                    "50 runs per cell",
                    "50 trajectory-level observations per cell"):
        add(EXPERIMENT_TEX, literal, "50", A,
            "len(evaluation_seeds)", "seeds", "count",
            "evaluation seed set",
            lambda a, c: float(len(a["evaluation_seeds"])))
    add(APPENDIX_TEX, "50 transport-Hessian trajectories", "50", A,
        "len(evaluation_seeds)", "trajectories", "count",
        "one transport-Hessian cell",
        lambda a, c: float(len(a["evaluation_seeds"])))
    add(EXPERIMENT_TEX, "600 independent runs", "600", A,
        "len(horizons) * len(target_D) * len(evaluation_seeds)", "runs", "count",
        "transport-Hessian arm of the grid",
        lambda a, c: float(len(a["horizons"]) * len(a["target_D"])
                           * len(a["evaluation_seeds"])))
    add(EXPERIMENT_TEX, "Ten disjoint tuning seeds", "10", C,
        "len(profiles.full.seed_sets.tuning)", "seeds", "count",
        "tuning seed set",
        lambda a, c: float(len(c["profiles"]["full"]["seed_sets"]["tuning"])))
    add(EXPERIMENT_TEX, "learning rate $3\\times10^{-4}$", "3e-4", A,
        "selected_optimizer.learning_rate", "dimensionless", "selected value",
        "optimizer selection over 10 tuning seeds",
        lambda a, c: float(a["selected_optimizer"]["learning_rate"]))
    add(EXPERIMENT_TEX, "20 full-batch steps", "20", A,
        "selected_optimizer.steps_per_round", "steps per round", "selected value",
        "optimizer selection over 10 tuning seeds",
        lambda a, c: float(a["selected_optimizer"]["steps_per_round"]))
    add(EXPERIMENT_TEX, "100 declared checkpoints per trajectory", "100", C,
        "primary horizon / transport.quadrature.full_checkpoint_period",
        "checkpoints", "derived count", "one T=1000 trajectory",
        lambda a, c: PRIMARY_HORIZON
        / float(c["base"]["transport"]["quadrature"]["full_checkpoint_period"]))

    # ---- grid completeness --------------------------------------------------
    add(EXPERIMENT_TEX, "all 2400 policy\ntrajectories", "2400", A,
        "completed_run_count", "trajectories", "count",
        "4 methods x 12 cells x 50 seeds",
        lambda a, c: float(a["completed_run_count"]))
    add(EXPERIMENT_TEX, "each of the 12\nhorizon--target cells", "12", A,
        "len(horizons) * len(target_D)", "cells", "count",
        "design grid",
        lambda a, c: float(len(a["horizons"]) * len(a["target_D"])))

    # ---- validity audit -----------------------------------------------------
    add(EXPERIMENT_TEX, "no deterministic algebra or certificate-check failure", "0", A,
        "sum(validity[*].deterministic_audit_failures)", "failures", "sum over cells",
        "all 12 transport-Hessian cells",
        lambda a, c: float(sum(int(r["deterministic_audit_failures"])
                               for r in a["validity"])))
    add(EXPERIMENT_TEX, "no bound violation on the joint confidence event", "0", A,
        "sum(validity[*].bound_violations_on_joint_event)", "violations",
        "sum over cells", "all 12 transport-Hessian cells",
        lambda a, c: float(sum(int(r["bound_violations_on_joint_event"])
                               for r in a["validity"])))
    add(EXPERIMENT_TEX, "$[92.9\\%,100\\%]$", "92.9", A,
        "100 * validity[*].reference_confidence_coverage.ci_low "
        "(bitwise identical in all 12 cells)",
        "percent", "exact Clopper-Pearson lower limit, 50 successes of 50 at level 0.95",
        "one cell of 50 runs",
        lambda a, c: 100.0 * _unique_ci_low(a))
    add(EXPERIMENT_TEX, "$[92.9\\%,100\\%]$", "100", A,
        "100 * validity[*].reference_confidence_coverage.ci_high "
        "(bitwise identical in all 12 cells)",
        "percent", "exact Clopper-Pearson upper limit, 50 successes of 50 at level 0.95",
        "one cell of 50 runs",
        lambda a, c: 100.0 * float({r["reference_confidence_coverage"]["ci_high"]
                                    for r in a["validity"]}.pop()))

    # ---- environment diagnostics at the primary horizon --------------------
    add(EXPERIMENT_TEX, "optimal-action\nentropy $1.579$", "1.579", A,
        "mean over T=1000 cells of environment_diagnostics.optimal_action_entropy.mean",
        "nats", "trajectory mean, then mean over the four target cells",
        "50 evaluation streams at T=1000",
        lambda a, c: _env_means(a, "optimal_action_entropy", PRIMARY_HORIZON))
    add(EXPERIMENT_TEX, "optimality\ngap $0.123$", "0.123", A,
        "mean over T=1000 cells of environment_diagnostics.average_optimality_gap.mean",
        "reward units", "trajectory mean, then mean over the four target cells",
        "50 evaluation streams at T=1000",
        lambda a, c: _env_means(a, "average_optimality_gap", PRIMARY_HORIZON))
    add(EXPERIMENT_TEX, "best-fixed-action regret $180.4$", "180.4", A,
        "mean over T=1000 cells of environment_diagnostics.best_fixed_action_regret.mean",
        "cumulative reward units", "trajectory total, then mean over seeds and cells",
        "50 evaluation streams at T=1000",
        lambda a, c: _env_means(a, "best_fixed_action_regret", PRIMARY_HORIZON))
    add(EXPERIMENT_TEX, "mean-only regret $185.4$", "185.4", A,
        "mean over T=1000 cells of environment_diagnostics.context_free_mean_only_regret.mean",
        "cumulative reward units", "trajectory total, then mean over seeds and cells",
        "50 evaluation streams at T=1000",
        lambda a, c: _env_means(a, "context_free_mean_only_regret", PRIMARY_HORIZON))
    add(EXPERIMENT_TEX, "All five actions are optimal somewhere in every", "5", A,
        "min over cells of environment_diagnostics.distinct_optimal_actions.minimum",
        "actions", "per-stream count, then minimum over cells and seeds",
        "all 12 cells",
        lambda a, c: float(min(r["distinct_optimal_actions"]["minimum"]
                               for r in a["environment_diagnostics"])))
    add(EXPERIMENT_TEX, r"$\log 5\approx1.609$", "5", C,
        "base.environment.action_count", "actions", "declared constant",
        "uniform distribution on the configured action set",
        lambda a, c: float(c["base"]["environment"]["action_count"]))
    add(EXPERIMENT_TEX, r"$\log 5\approx1.609$", "1.609", C,
        "log(base.environment.action_count)", "nats", "maximum discrete entropy",
        "uniform distribution on the configured action set",
        lambda a, c: math.log(float(c["base"]["environment"]["action_count"])))

    # ---- certificate tightness at the primary horizon ----------------------
    add(EXPERIMENT_TEX, "ranges from $0.0486$", "0.0486", A,
        "min over T=1000 cells of validity.max_realized_D_Q.median", "dimensionless",
        "within-trajectory maximum, then median over 50 runs, then min over cells",
        "50 transport-Hessian trajectories per cell",
        lambda a, c: min(_medians(a, "validity", "max_realized_D_Q", PRIMARY_HORIZON)))
    add(EXPERIMENT_TEX, "to $0.384$", "0.384", A,
        "max over T=1000 cells of validity.max_realized_D_Q.median", "dimensionless",
        "within-trajectory maximum, then median over 50 runs, then max over cells",
        "50 transport-Hessian trajectories per cell",
        lambda a, c: max(_medians(a, "validity", "max_realized_D_Q", PRIMARY_HORIZON)))
    add(EXPERIMENT_TEX, "ranges from $1.31\\times10^{-7}$", "1.31e-7", A,
        "min over T=1000 cells of validity.max_endpoint_Thompson_distance.median",
        "dimensionless",
        "within-trajectory maximum, then median over 50 runs, then min over cells",
        "50 transport-Hessian trajectories per cell",
        lambda a, c: min(_medians(a, "validity",
                                  "max_endpoint_Thompson_distance", PRIMARY_HORIZON)))
    add(EXPERIMENT_TEX, "$8.74\\times10^{-6}$", "8.74e-6", A,
        "max over T=1000 cells of validity.max_endpoint_Thompson_distance.median",
        "dimensionless",
        "within-trajectory maximum, then median over 50 runs, then max over cells",
        "50 transport-Hessian trajectories per cell",
        lambda a, c: max(_medians(a, "validity",
                                  "max_endpoint_Thompson_distance", PRIMARY_HORIZON)))
    add(EXPERIMENT_TEX, "5,000\neligible seed--checkpoint ratios", "5000", A,
        "certificate_tightness[T=1000].D_path_quad_over_d_Th.n (identical in all cells)",
        "ratios", "pooled eligible seed-checkpoint observations",
        "50 seeds x 100 checkpoints in one T=1000 cell",
        lambda a, c: float({int(r["D_path_quad_over_d_Th"]["n"])
                            for r in _cells(a, "certificate_tightness",
                                            PRIMARY_HORIZON)}.pop()))
    add(EXPERIMENT_TEX, "$1.20$--$1.22$ times the endpoint distance", "1.20", A,
        "min over T=1000 cells of certificate_tightness.D_path_quad_over_d_Th.median",
        "dimensionless", "pooled seed-checkpoint ratio median, then min over cells",
        "5,000 seed-checkpoint ratios per cell",
        lambda a, c: min(_medians(a, "certificate_tightness",
                                  "D_path_quad_over_d_Th", PRIMARY_HORIZON)))
    add(EXPERIMENT_TEX, "$1.20$--$1.22$ times the endpoint distance", "1.22", A,
        "max over T=1000 cells of certificate_tightness.D_path_quad_over_d_Th.median",
        "dimensionless", "pooled seed-checkpoint ratio median, then max over cells",
        "5,000 seed-checkpoint ratios per cell",
        lambda a, c: max(_medians(a, "certificate_tightness",
                                  "D_path_quad_over_d_Th", PRIMARY_HORIZON)))
    add(EXPERIMENT_TEX, "$2.51\\times10^5$", "2.51e5", A,
        "min over T=1000 cells of certificate_tightness.D_Q_over_D_path_quad.median",
        "dimensionless", "pooled seed-checkpoint ratio median, then min over cells",
        "5,000 seed-checkpoint ratios per cell",
        lambda a, c: min(_medians(a, "certificate_tightness",
                                  "D_Q_over_D_path_quad", PRIMARY_HORIZON)))
    add(EXPERIMENT_TEX, "$1.88\\times10^6$", "1.88e6", A,
        "max over T=1000 cells of certificate_tightness.D_Q_over_D_path_quad.median",
        "dimensionless", "pooled seed-checkpoint ratio median, then max over cells",
        "5,000 seed-checkpoint ratios per cell",
        lambda a, c: max(_medians(a, "certificate_tightness",
                                  "D_Q_over_D_path_quad", PRIMARY_HORIZON)))
    add(EXPERIMENT_TEX, "is $3.07\\times10^5$", "3.07e5", A,
        "min over T=1000 cells of certificate_tightness.D_Q_over_d_Th.median",
        "dimensionless", "pooled seed-round ratio median, then min over cells",
        "eligible seed-round ratios per cell",
        lambda a, c: min(_medians(a, "certificate_tightness",
                                  "D_Q_over_d_Th", PRIMARY_HORIZON)))
    add(EXPERIMENT_TEX, "$2.24\\times10^6$", "2.24e6", A,
        "max over T=1000 cells of certificate_tightness.D_Q_over_d_Th.median",
        "dimensionless", "pooled seed-round ratio median, then max over cells",
        "eligible seed-round ratios per cell",
        lambda a, c: max(_medians(a, "certificate_tightness",
                                  "D_Q_over_d_Th", PRIMARY_HORIZON)))
    add(EXPERIMENT_TEX, "pools all 50,000 seed--round values", "50000", A,
        "certificate_tightness[T=1000].exp_D_Q_over_2.n (identical in all cells)",
        "values", "pooled seed-round observations",
        "50 seeds x 1000 rounds in one T=1000 cell",
        lambda a, c: float({int(r["exp_D_Q_over_2"]["n"])
                            for r in _cells(a, "certificate_tightness",
                                            PRIMARY_HORIZON)}.pop()))
    add(EXPERIMENT_TEX, "ranges from\n$1.02$", "1.02", A,
        "min over T=1000 cells of certificate_tightness.exp_D_Q_over_2.median",
        "dimensionless", "pooled seed-round median, then min over cells",
        "50,000 seed-round values per cell",
        lambda a, c: min(_medians(a, "certificate_tightness",
                                  "exp_D_Q_over_2", PRIMARY_HORIZON)))
    add(EXPERIMENT_TEX, "to $1.18$", "1.18", A,
        "max over T=1000 cells of certificate_tightness.exp_D_Q_over_2.median",
        "dimensionless", "pooled seed-round median, then max over cells",
        "50,000 seed-round values per cell",
        lambda a, c: max(_medians(a, "certificate_tightness",
                                  "exp_D_Q_over_2", PRIMARY_HORIZON)))

    # ---- bound nonvacuity ---------------------------------------------------
    add(EXPERIMENT_TEX, "is $126.7$--$155.7$ over the", "126.7", A,
        "min over all 12 cells of bound_nonvacuity.sharp_rhs_over_positive_regret.median",
        "dimensionless", "per-trajectory terminal ratio, median over 50 runs, min over cells",
        "50 transport-Hessian trajectories per cell, full grid",
        lambda a, c: min(_medians(a, "bound_nonvacuity",
                                  "sharp_rhs_over_positive_regret")))
    add(EXPERIMENT_TEX, "is $126.7$--$155.7$ over the", "155.7", A,
        "max over all 12 cells of bound_nonvacuity.sharp_rhs_over_positive_regret.median",
        "dimensionless", "per-trajectory terminal ratio, median over 50 runs, max over cells",
        "50 transport-Hessian trajectories per cell, full grid",
        lambda a, c: max(_medians(a, "bound_nonvacuity",
                                  "sharp_rhs_over_positive_regret")))
    add(EXPERIMENT_TEX, "$126.7$--$135.0$ at $T=1000$", "135.0", A,
        "max over T=1000 cells of bound_nonvacuity.sharp_rhs_over_positive_regret.median",
        "dimensionless", "per-trajectory terminal ratio, median over 50 runs, max over cells",
        "50 transport-Hessian trajectories per cell at T=1000",
        lambda a, c: max(_medians(a, "bound_nonvacuity",
                                  "sharp_rhs_over_positive_regret", PRIMARY_HORIZON)))
    add(EXPERIMENT_TEX, "No run has zero regret", "0", A,
        "sum(bound_nonvacuity[*].zero_regret_run_count)", "runs", "sum over cells",
        "all 600 transport-Hessian runs",
        lambda a, c: float(sum(int(r["zero_regret_run_count"])
                               for r in a["bound_nonvacuity"])))
    add(EXPERIMENT_TEX, "$3{,}989$--$12{,}607$", "3989", A,
        "min over all 12 cells of bound_nonvacuity.sharp_theorem_rhs.median",
        "cumulative reward units", "per-trajectory terminal value, median over 50 runs, min over cells",
        "50 transport-Hessian trajectories per cell, full grid",
        lambda a, c: min(_medians(a, "bound_nonvacuity", "sharp_theorem_rhs")))
    add(EXPERIMENT_TEX, "$3{,}989$--$12{,}607$", "12607", A,
        "max over all 12 cells of bound_nonvacuity.sharp_theorem_rhs.median",
        "cumulative reward units", "per-trajectory terminal value, median over 50 runs, max over cells",
        "50 transport-Hessian trajectories per cell, full grid",
        lambda a, c: max(_medians(a, "bound_nonvacuity", "sharp_theorem_rhs")))

    # ---- the existing cumulative decomposition, along primary-policy paths --
    # The aggregate stores per-round component means.  Taking their ratio is
    # intentional: it is neither a median share nor a frozen-policy replay.
    for field_name, literal, displays in (
        ("statistical_bound_component", r"$79.4\%$--$97.3\%$", ("79.4", "97.3")),
        ("path_inflation_component", r"$2.0\%$--$16.3\%$", ("2.0", "16.3")),
    ):
        for reducer, display in zip((min, max), displays):
            add(EXPERIMENT_TEX, literal, display, A,
                f"{reducer.__name__} over terminal primary-horizon cells of "
                f"100 * bound_decomposition.{field_name} / sharp_theorem_rhs",
                "percent", "ratio of component mean to sharp-RHS mean, then cell extremum",
                "50 transport-Hessian trajectories per T=1000 target cell",
                lambda a, c, field=field_name, reduce=reducer:
                reduce(_decomposition_shares(a, field)))
    for reducer, display in ((min, "9{,}948"), (max, "10{,}010")):
        add(EXPERIMENT_TEX, r"$9{,}948$--$10{,}010$", display, A,
            f"{reducer.__name__} over terminal primary-horizon cells of "
            "bound_decomposition.statistical_bound_component",
            "cumulative reward units", "mean over 50 runs, then cell extremum",
            "50 transport-Hessian trajectories per T=1000 target cell",
            lambda a, c, reduce=reducer: reduce(
                float(r["statistical_bound_component"])
                for r in _terminal_decomposition(a)))
    add(EXPERIMENT_TEX, r"cap $2{,}000$", "2{,}000", C,
        "2 * base.reporting.primary_horizon", "cumulative reward units",
        "deterministic cap 2T", "primary horizon",
        lambda a, c: 2.0 * float(c["base"]["reporting"]["primary_horizon"]))
    for manuscript, literal in (
        (EXPERIMENT_TEX, "50 transport-Hessian trajectories"),
        (APPENDIX_TEX, "50 primary-policy trajectories"),
    ):
        add(manuscript, literal, "50", A, "len(evaluation_seeds)", "trajectories",
            "count", "one transport-Hessian target cell",
            lambda a, c: float(len(a["evaluation_seeds"])))
    for field_name, literal, displays in (
        ("statistical_bound_component", r"$97.33\%,94.66\%,89.39\%,79.39\%$",
         ("97.33", "94.66", "89.39", "79.39")),
        ("path_inflation_component", r"$2.01\%,4.04\%,8.16\%,16.27\%$",
         ("2.01", "4.04", "8.16", "16.27")),
    ):
        for index, display in enumerate(displays):
            add(APPENDIX_TEX, literal, display, A,
                "terminal primary-horizon target cells in ascending target order, "
                f"index {index}: 100 * {field_name} / sharp_theorem_rhs",
                "percent", "ratio of component mean to sharp-RHS mean",
                "50 transport-Hessian trajectories in one T=1000 target cell",
                lambda a, c, field=field_name, i=index: _decomposition_shares(a, field)[i])
    for index, target in enumerate((0.25, 0.5, 1, 2)):
        add(APPENDIX_TEX, r"$D_{\rm target}=0.25,0.5,1,2$", str(target), C,
            f"base.target_D[{index}]", "dimensionless", "design label",
            "configuration", lambda a, c, i=index:
            float(c["base"]["target_D"][i]))

    # ---- policy outcomes at the primary horizon ----------------------------
    add(EXPERIMENT_TEX, "rises\nfrom $81.0$", "81.0", A,
        "policy_outcomes[transport_hessian, T=1000, D=0.25].cumulative_pseudo_regret.mean",
        "cumulative reward units", "trajectory total, then mean over 50 seeds",
        "50 transport-Hessian trajectories",
        lambda a, c: float(_policy(a, "transport_hessian", PRIMARY_HORIZON, 0.25)
                           ["cumulative_pseudo_regret"]["mean"]))
    add(EXPERIMENT_TEX, "to $94.0$", "94.0", A,
        "policy_outcomes[transport_hessian, T=1000, D=2.0].cumulative_pseudo_regret.mean",
        "cumulative reward units", "trajectory total, then mean over 50 seeds",
        "50 transport-Hessian trajectories",
        lambda a, c: float(_policy(a, "transport_hessian", PRIMARY_HORIZON, 2.0)
                           ["cumulative_pseudo_regret"]["mean"]))

    # ---- claims repeated in the abstract, introduction and conclusion ------
    # Abstract and introduction now describe the distinct completed follow-up.
    for manuscript in (ABSTRACT_TEX, INTRO_TEX):
        add(manuscript, "29-parameter", "29", FOLLOWUP_CONFIG,
            "environment.feature_dimension", "parameters", "declared constant",
            "completed follow-up configuration",
            lambda a, c: float(a["environment"]["feature_dimension"]))
        add(manuscript, "50 paired seeds", "50", FOLLOWUP_CONFIG,
            "len(seed_sets.evaluation)", "seeds", "count",
            "completed follow-up evaluation seeds within each condition",
            lambda a, c: float(len(a["seed_sets"]["evaluation"])))
    add(LEGACY_SCOPE_TEX, "29-parameter", "29", C,
        "base.environment.feature_dimension", "parameters", "declared constant",
        "configuration",
        lambda a, c: float(c["base"]["environment"]["feature_dimension"]))

    # ---- counts the supplement's own README states to a reviewer ------------
    # These used to be prose nobody checked: changing "2,400 trajectories" to
    # "2,401" in a clean unpack left every verifier stage green.  The repository
    # keeps this file under its build name and the archive ships it as
    # README.md, so the entries follow whichever one this tree actually has.
    for readme in readme_sources(root):
        add(readme, "2,400 trajectories", "2,400", A,
            "completed_run_count", "trajectories", "count",
            "4 methods x 12 cells x 50 seeds",
            lambda a, c: float(a["completed_run_count"]))
        add(readme, "21 artifacts", "21", A,
            "3 series x (1 pooled CSV + len(target_D) panel CSVs) "
            "+ 3 tables + 3 figure sources", "files", "derived count",
            "generated artifact set",
            lambda a, c: float(3 * (3 + len(a["target_D"]))))
        add(readme, "all 21 published tables, figures and CSVs", "21", A,
            "3 series x (1 pooled CSV + len(target_D) panel CSVs) "
            "+ 3 tables + 3 figure sources", "files", "derived count",
            "generated artifact set",
            lambda a, c: float(3 * (3 + len(a["target_D"]))))
    e.extend(followup_ledger())
    return e


# --------------------------------------------------------------------------
# the literal-coverage audit
# --------------------------------------------------------------------------
#
# The ledger above says that each number it lists is right.  It said nothing
# about numbers it does not list, and that was the real gap: the horizon grid
# `{250,500,1000}` and the deterministic-cap range `500--2,000` were printed in
# the manuscript and checked by nothing, so `{251,500,1000}` passed.
#
# The audit below closes the class rather than the two instances.  It reads the
# submitted sources, removes the spans that ledger entries already account for
# and the spans explicitly declared non-empirical, and fails on whatever
# numeric literal is left.  Adding an unchecked number to a results section is
# therefore a failure, not an omission.

#: The submission entry point.  The audited set is its transitive \input
#: closure, computed from the files themselves, so a source added to the
#: manuscript is audited without anyone updating a list.
ENTRY_POINT = ABSTRACT_TEX

#: Reviewer-facing supplement text.  It states counts about the study, and an
#: independent reviewer changed one of them in a clean unpack and watched every
#: verifier stage stay green, so it is audited under the same rule as the
#: manuscript.  The repository keeps it under its build name; the archive ships
#: it as README.md at the root.
SUPPLEMENT_README_REPO = Path("submissions/tmlr_2026/supplement_README.md")
SUPPLEMENT_README_PACKAGED = Path("README.md")

#: Sources the submission entry point does not compile.
UNSUBMITTED_TEX = ("main.tex", "legacy_experiments.tex")

#: Sources regenerated byte-for-byte from the locked aggregate by
#: tools/transport_artifact_expectations.py.  Byte identity against a committed
#: source is a stronger statement about every cell than a list of per-cell
#: entries would be, and the audit rejects the label unless a matching sidecar
#: backs it, so this is a verified property and not an exemption.
GENERATED_ARTIFACT_SOURCES = (
    "paper/tables/transport_instantiation_validity.tex",
    "paper/tables/transport_instantiation_performance.tex",
    "paper/tables/transport_instantiation_tightness.tex",
    "paper/figures/transport_instantiation_regret.tex",
    "paper/figures/transport_instantiation_tightness.tex",
    "paper/figures/transport_instantiation_bound.tex",
)
FOLLOWUP_GENERATED_SOURCES = (
    "paper/tables/transport_followup_outcomes.tex",
    "paper/tables/transport_followup_drift_bounds.tex",
    "paper/tables/transport_followup_same_history.tex",
    "paper/tables/transport_followup_mechanism_variation.tex",
    "paper/tables/transport_followup_relative_audit.tex",
)
EXPLANATORY_GENERATED_SOURCES = (
    "paper/figures/transport_explanatory_outcomes.tex",
    "paper/figures/transport_explanatory_outcomes.csv",
    "paper/figures/transport_explanatory_paired.csv",
    "paper/figures/transport_explanatory_bounds.tex",
    "paper/figures/transport_explanatory_bounds.csv",
)
TABLE_CHART_GENERATED_SOURCES = ('paper/figures/transport_table_drift.tex', 'paper/figures/transport_table_mechanism.tex', 'paper/figures/transport_table_original_bound_ratios.tex', 'paper/figures/transport_table_original_components.tex', 'paper/figures/transport_table_original_distribution.tex', 'paper/figures/transport_table_original_path_ratios.tex', 'paper/figures/transport_table_original_performance.tex', 'paper/figures/transport_table_original_validity.tex', 'paper/figures/transport_table_relative.tex', 'paper/figures/transport_table_same_history.tex')
TABLE_CHART_PROVENANCE = 'paper/figures/transport_table_provenance.json'
EXPLANATORY_PROVENANCE = "paper/figures/transport_explanatory_provenance.json"
ANALYTICAL_SCHEMATIC_SOURCES = (
    "paper/figures/transport_conceptual_interfaces.tex",
    "paper/figures/transport_conceptual_geometry.tex",
)
ALL_GENERATED_SOURCES = (GENERATED_ARTIFACT_SOURCES + FOLLOWUP_GENERATED_SOURCES
                         + EXPLANATORY_GENERATED_SOURCES + TABLE_CHART_GENERATED_SOURCES)

#: Two sources that are neither ledger-covered nor per-literal classified.  They
#: used to be whole-file exemptions, which meant an empirical value dropped into
#: either one was waved through.  Each now has a structural check that says what
#: the file is allowed to contain; see macro_file_checks and
#: symbolic_table_checks.
MACRO_SOURCE = "paper/macros.tex"
SYMBOLIC_TABLE_SOURCE = "paper/tables/growing_window_pareto.tex"

#: Typeset input that is not generated from the study.
SYMBOLIC_TABLE_INPUTS = ("tables/growing_window_pareto.tex",)

#: Declarations a macro file may contain, and nothing else.
MACRO_DECLARATIONS = (
    r"\newcommand", r"\renewcommand", r"\providecommand",
    r"\DeclareMathOperator", r"\newif", r"\let", r"\def", r"\newenvironment",
    r"\newsavebox", r"\usepackage", r"\makeatletter", r"\makeatother",
    r"\newtheorem", r"\newaliascnt", r"\aliascntresetthe",
    r"\crefname", r"\Crefname",
)

#: The grammar of a cell in the symbolic rate table.  An alphabet-membership
#: test used to stand in for this, and it accepted any rearrangement of the same
#: characters -- `T^{2}` and `T^{3}` are equally "in the alphabet", so a changed
#: rate passed.  Each cell is parsed instead, and the parsed result is compared
#: against the pinned list below, so a semantic change fails even though it is
#: still a well-formed rate.
_SYMBOLIC_INT = re.compile(r"\A(\d+)\Z")
_SYMBOLIC_FRAC = re.compile(r"\A\\frac\{(\d+)\}\{(\d+)\}\Z")
_SYMBOLIC_POWER = re.compile(r"\A(K?T)\^\{(.+)\}\Z")


def parse_symbolic_cell(cell: str) -> str | None:
    r"""Canonical form of one asymptotic-rate cell, or None if it is not one."""

    inner = cell.strip()
    if not (inner.startswith("$") and inner.endswith("$") and len(inner) > 2):
        return None
    inner = inner[1:-1].strip()

    def exponent(text: str) -> str | None:
        match = _SYMBOLIC_INT.match(text)
        if match:
            return f"int {match.group(1)}"
        match = _SYMBOLIC_FRAC.match(text)
        if match:
            return f"frac {match.group(1)}/{match.group(2)}"
        return None

    match = _SYMBOLIC_POWER.match(inner)
    if match:
        exponent_form = exponent(match.group(2).strip())
        return None if exponent_form is None else \
            f"{match.group(1)}^{exponent_form}"
    return exponent(inner)


#: The exact ordered cells of the symbolic rate table's body.  Pinned, so that a
#: rate changing from one valid rate to another is a failure.
SYMBOLIC_TABLE_CELLS = (
    "frac 1/2", "T^frac 3/4", "KT^frac 7/4", "T^int 2",
    "frac 2/3", "T^frac 2/3", "KT^int 2", "T^int 2",
    "int 1", "T^frac 1/2", "KT^frac 5/2", "T^frac 5/2",
)

# --------------------------------------------------------------------------
# the explicit non-empirical classification
# --------------------------------------------------------------------------
#
# Every numeric literal in every other submitted source is listed here, keyed by
# the file it appears in, with a category.  Keying by file is deliberate: `42.7`
# being a legitimate constant in one proof says nothing about `42.7` appearing
# in a results paragraph, and an independent reviewer planted exactly that
# number in a theory source and watched a value-set rule wave it through.
#
# Nothing here is a regex. Adding a number to the manuscript that is not already
# on this list, and not covered by a ledger entry, fails the audit.

_CATEGORY_REASON = {
    "math-constant":
        "a constant, exponent, index or coefficient inside a formula or a "
        "theorem statement; not a measurement",
    "interval-endpoint":
        "an endpoint of the unit interval or of the set {0,1}",
    "citation-locator":
        "a theorem number inside a citation, naming someone else's result",
    "cited-scale":
        "an order-of-magnitude parameter count attributed to cited work, not "
        "measured here",
    "illustration-input":
        "an input the manuscript declares in the same sentence for an "
        "arithmetic illustration of an operation count",
    "derived-arithmetic":
        "the product of the declared illustration inputs; the structural check "
        "'the per-round cost illustration is arithmetically consistent' "
        "recomputes it",
    "document-structure":
        "a step number or list marker in the supplement's own instructions",
    "environment-version":
        "a declared software version, checked against "
        "experiments/requirements.txt by a structural check",
    "historical-dependency-version":
        "dependency metadata from the retained implementation snapshot, not "
        "an experimental measurement; the exact provenance statement is pinned",
    "analytic-schematic":
        "a formula in a declared analytical illustration or its drawing "
        "coordinates and layout; not measured evidence; the entire source "
        "and each occurrence's semantic unit are independently pinned",
}

# Each entry is bound to one file AND to an exact number of occurrences in it.
# A per-file classification without a count authorises every occurrence, which
# is how a newly written empirical sentence could reuse a theorem constant that
# was already classified. A count makes the extra occurrence the failure.
#
# The counts are large in the proof appendices because `1` and `2` really do
# appear hundreds of times in the mathematics. That brittleness is the point:
# the manuscript is frozen, and any change in how a number is used has to be
# re-declared rather than absorbed.

#: (path, literal) -> (category, exact occurrence count)
CLASSIFIED_LITERALS: dict[tuple[str, str], tuple[str, int]] = {}


def _classify(path: str, category: str, counts: dict[str, int]) -> None:
    for literal, count in counts.items():
        CLASSIFIED_LITERALS[(path, literal)] = (category, count)


_classify("paper/availability.tex", "historical-dependency-version",
          {"1.13.1": 1, "1.15.2": 1})
_classify("paper/body_related.tex", "math-constant", {"1": 3, "2": 2})
_classify("paper/notation.tex", "math-constant", {"1": 2, "2": 3})
_classify("paper/transport_experiment_appendix.tex", "math-constant",
          {"1": 7, "2": 10})
_classify("paper/transport_proofs.tex", "math-constant",
          {"0": 16, "1": 80, "2": 110, "4": 4})
_classify("paper/transport_proofs.tex", "interval-endpoint", {"0,1": 1})
_classify("paper/transport_theory.tex", "math-constant",
          {"0": 33, "1": 100, "1,0": 1, "2": 113, "3": 2, "4": 6})
_classify("paper/transport_theory.tex", "interval-endpoint", {"0,1": 5})
_classify("paper/transport_followup.tex", "math-constant", {"1": 2, "2": 2})
_classify("paper/transport_followup_appendix.tex", "math-constant",
          {"1": 4, "2": 5, "4": 1})
for _readme in (str(SUPPLEMENT_README_REPO), str(SUPPLEMENT_README_PACKAGED)):
    _classify(_readme, "environment-version",
              {"3.12": 1, "2.2.3": 1, "1.15.2": 1})

_classify('paper/figures/transport_conceptual_interfaces.tex', "analytic-schematic",
          {'.3': 1,
           '0': 7,
           '0,0': 1,
           '1.15': 4,
           '1.8': 1,
           '10.2': 1,
           '11': 1,
           '14.4': 1,
           '16.2': 2,
           '2': 2,
           '2.2': 3,
           '28': 2,
           '4.6': 2,
           '4.95': 1,
           '5.5': 1,
           '5.57': 1,
           '55': 1,
           '6': 1,
           '6.11': 1,
           '6.65': 1,
           '6.8': 1})
_classify('paper/figures/transport_conceptual_geometry.tex', "analytic-schematic",
          {'.25': 1,
           '.55': 2,
           '.65': 1,
           '.82': 1,
           '0': 8,
           '0,0': 1,
           '0,13': 1,
           '1': 6,
           '1,0': 1,
           '1,10': 1,
           '1.05': 1,
           '1.25': 2,
           '1.8': 2,
           '1.95': 1,
           '10': 3,
           '11.5': 4,
           '13': 3,
           '14.5': 13,
           '14.72': 1,
           '14.85': 1,
           '16.2': 1,
           '2': 4,
           '2.1': 1,
           '2.25': 1,
           '2.35': 1,
           '2.73': 2,
           '2.85': 3,
           '2.97': 2,
           '3': 5,
           '3.02': 3,
           '3.525': 3,
           '3.55': 1,
           '3.6': 4,
           '3.75': 1,
           '30': 1,
           '4': 2,
           '4.05': 3,
           '4.2': 1,
           '4.23': 2,
           '4.32': 2,
           '4.35': 12,
           '4.37': 1,
           '4.4': 2,
           '4.47': 4,
           '4.53': 1,
           '4.6': 2,
           '40': 2,
           '5.2': 1,
           '5.25': 1,
           '5.73': 2,
           '5.85': 3,
           '5.97': 2,
           '50': 2,
           '55': 1,
           '6': 1,
           '6.35': 2,
           '6.64': 1,
           '6.7': 3,
           '6.76': 1,
           '6.86': 1,
           '65': 3,
           '7': 4,
           '7.15': 6,
           '7.4': 1,
           '7.85': 1,
           '70': 1,
           '8.15': 1,
           '8.32': 1,
           '8.35': 1,
           '8.5': 7,
           '80': 3})

#: Literals that are definitions or mathematics rather than measurements, and
#: that are easier to read as a phrase than as a bare token.  Each is masked
#: wherever it occurs, with the reason recorded so the classification is
#: reviewable rather than implicit.
NON_EMPIRICAL_LITERALS = (
    (r"\alpha_t=1",
     "declared exact-instantiation interface: the dense exact operator makes "
     "the theorem's approximation factor identically one by definition"),
    (r"\kappa_{-,t}=\kappa_{+,t}=1",
     "declared exact-instantiation interface: exact current curvature, so the "
     "two-sided comparison factors are one by definition"),
    (r"\xi_t=0",
     "declared exact-instantiation interface: finite enumeration with a fixed "
     "tie rule, so the selector slack is zero by definition"),
    (r"deterministic cap $2T$",
     "mathematical consequence of |mu*| <= 1, which the structural check "
     "'the deterministic pseudo-regret cap 2T is implied by the configuration' "
     "verifies against the configuration"),
    (r"$e^{\bar D_t^Q/2}$",
     "mathematical expression; the 2 is the exponent in the transport factor, "
     "not a measured quantity"),
    (r"$D_t<1$",
     "mathematical condition from the prior one-sided theorem, not a "
     "measurement"),
)

# Where each ledger literal and each non-empirical phrase is allowed to occur,
# and how many times.  Masking used to be global: a phrase declared for one file
# was blanked wherever it appeared, so copying `best-fixed-action regret $180.4$`
# into a theory source made the copy invisible to the audit.  Now a phrase is
# masked only in the files listed here, an occurrence anywhere else is an
# unclassified literal, and a count that does not match is a failure -- which is
# what catches a missing, duplicated or moved occurrence.
#
# `$T=1000$` and `\xi_t=0` legitimately recur; the count records how often.
PHRASE_OCCURRENCES: dict[tuple[str, str], int] = {
    ("paper/body_intro.tex", "29-parameter"): 1,
    ("paper/body_intro.tex", "50 paired seeds"): 1,
    ("paper/legacy_scope.tex", "29-parameter"): 1,
    ("paper/transport_experiment.tex",
     "$1.20$--$1.22$ times the endpoint distance"): 1,
    ("paper/transport_experiment.tex", "$1.88\\times10^6$"): 1,
    ("paper/transport_experiment.tex", "$126.7$--$135.0$ at $T=1000$"): 1,
    ("paper/transport_experiment.tex", "$2.24\\times10^6$"): 1,
    ("paper/transport_experiment.tex", "$2.51\\times10^5$"): 1,
    ("paper/transport_experiment.tex", "$3{,}989$--$12{,}607$"): 1,
    ("paper/transport_experiment.tex", "$8.74\\times10^{-6}$"): 1,
    ("paper/transport_experiment.tex", "$T=1000$"): 8,
    ("paper/transport_experiment.tex", r"$\log 5\approx1.609$"): 1,
    ("paper/transport_experiment.tex", r"$79.4\%$--$97.3\%$"): 1,
    ("paper/transport_experiment.tex", r"$2.0\%$--$16.3\%$"): 1,
    ("paper/transport_experiment.tex", r"$9{,}948$--$10{,}010$"): 1,
    ("paper/transport_experiment.tex", r"cap $2{,}000$"): 1,
    ("paper/transport_experiment.tex", "50 transport-Hessian trajectories"): 1,
    ("paper/transport_experiment.tex", "$[92.9\\%,100\\%]$"): 1,
    ("paper/transport_experiment.tex", "$e^{\\bar D_t^Q/2}$"): 1,
    ("paper/transport_experiment.tex",
     "100 declared checkpoints per trajectory"): 1,
    ("paper/transport_experiment.tex", "20 full-batch steps"): 1,
    ("paper/transport_experiment.tex",
     "5,000\neligible seed--checkpoint ratios"): 1,
    ("paper/transport_experiment.tex", "50 evaluation seeds"): 2,
    ("paper/transport_experiment.tex", "50 runs per cell"): 1,
    ("paper/transport_experiment.tex",
     "50 trajectory-level observations per cell"): 1,
    ("paper/transport_experiment.tex", "600 independent runs"): 1,
    ("paper/transport_experiment.tex",
     "All five actions are optimal somewhere in every"): 1,
    ("paper/transport_experiment.tex", "Contexts have dimension $4$"): 1,
    ("paper/transport_experiment.tex", "No run has zero regret"): 1,
    ("paper/transport_experiment.tex", "Ten disjoint tuning seeds"): 1,
    ("paper/transport_experiment.tex", "\\alpha_t=1"): 1,
    ("paper/transport_experiment.tex", "\\kappa_{-,t}=\\kappa_{+,t}=1"): 1,
    ("paper/transport_experiment.tex", "\\xi_t=0"): 1,
    ("paper/transport_experiment.tex", "all 2400 policy\ntrajectories"): 1,
    ("paper/transport_experiment.tex",
     "best-fixed-action regret $180.4$"): 1,
    ("paper/transport_experiment.tex", "deterministic cap $2T$"): 1,
    ("paper/transport_experiment.tex",
     "each of the 12\nhorizon--target cells"): 1,
    ("paper/transport_experiment.tex",
     "exact 95\\% Clopper--Pearson interval"): 1,
    ("paper/transport_experiment.tex", "feature map has dimension $29$"): 1,
    ("paper/transport_experiment.tex",
     "horizons $T\\in\\{250,500,1000\\}$"): 1,
    ("paper/transport_experiment.tex", "is $126.7$--$155.7$ over the"): 1,
    ("paper/transport_experiment.tex", "is $3.07\\times10^5$"): 1,
    ("paper/transport_experiment.tex", "learning rate $3\\times10^{-4}$"): 1,
    ("paper/transport_experiment.tex", "mean-only regret $185.4$"): 1,
    ("paper/transport_experiment.tex",
     "no bound violation on the joint confidence event"): 1,
    ("paper/transport_experiment.tex",
     "no deterministic algebra or certificate-check failure"): 1,
    ("paper/transport_experiment.tex", "optimal-action\nentropy $1.579$"): 1,
    ("paper/transport_experiment.tex", "optimality\ngap $0.123$"): 1,
    ("paper/transport_experiment.tex", "paired-bootstrap 95\\%"): 1,
    ("paper/transport_experiment.tex",
     "pools all 50,000 seed--round values"): 1,
    ("paper/transport_experiment.tex", "ranges from\n$1.02$"): 1,
    ("paper/transport_experiment.tex", "ranges from $0.0486$"): 1,
    ("paper/transport_experiment.tex",
     "ranges from $1.31\\times10^{-7}$"): 1,
    ("paper/transport_experiment.tex", "rises\nfrom $81.0$"): 1,
    ("paper/transport_experiment.tex",
     "target labels $D_{\\rm target}\\in\\{0.25,0.5,1,2\\}$"): 1,
    ("paper/transport_experiment.tex", "the 50-seed means"): 1,
    ("paper/transport_experiment.tex", "the same 50 base seeds"): 1,
    ("paper/transport_experiment.tex", "there are five actions"): 1,
    ("paper/transport_experiment.tex", "to $0.384$"): 1,
    ("paper/transport_experiment.tex", "to $1.18$"): 1,
    ("paper/transport_experiment.tex", "to $94.0$"): 1,
    ("paper/transport_experiment.tex", "versus caps of $500$--$2{,}000$"): 1,
    ("paper/transport_experiment_appendix.tex", "$T=1000$"): 3,
    ("paper/transport_experiment_appendix.tex", "$e^{\\bar D_t^Q/2}$"): 2,
    ("paper/transport_experiment_appendix.tex", "50 primary-policy trajectories"): 1,
    ("paper/transport_experiment_appendix.tex", r"$97.33\%,94.66\%,89.39\%,79.39\%$"): 1,
    ("paper/transport_experiment_appendix.tex", r"$2.01\%,4.04\%,8.16\%,16.27\%$"): 1,
    ("paper/transport_experiment_appendix.tex", r"$D_{\rm target}=0.25,0.5,1,2$"): 1,
    ("paper/transport_experiment_appendix.tex", r"\kappa_{-,t}=\kappa_{+,t}=1"): 1,
    ("paper/transport_experiment_appendix.tex", r"\xi_t=0"): 1,
    ("paper/transport_experiment_appendix.tex", "50 evaluation seeds"): 2,
    ("paper/transport_experiment_appendix.tex", "50 runs per cell"): 1,
    ("paper/transport_experiment_appendix.tex",
     "50 transport-Hessian trajectories"): 1,
    ("paper/transport_experiment_appendix.tex", "paired-bootstrap 95\\%"): 1,
    ("paper/transport_experiment_appendix.tex",
     "preregistered $10^{-12}$ ratio tolerance"): 1,
    ("paper/transport_proofs.tex", "\\xi_t=0"): 2,
    ("paper/transport_theory.tex", "$D_t<1$"): 1,
    ("paper/transport_theory.tex", "\\alpha_t=1"): 1,
    ("paper/transport_theory.tex", "\\kappa_{-,t}=\\kappa_{+,t}=1"): 2,
    ("paper/transport_theory.tex", "\\xi_t=0"): 3,
    ("submissions/tmlr_2026/main.tex", "29-parameter"): 1,
    ("submissions/tmlr_2026/main.tex", "50 paired seeds"): 1,
    ("submissions/tmlr_2026/supplement_README.md", "2,400 trajectories"): 1,
    ("submissions/tmlr_2026/supplement_README.md", "21 artifacts"): 1,
    ("submissions/tmlr_2026/supplement_README.md",
     "all 21 published tables, figures and CSVs"): 1,
}


# Reviewed follow-up prose: exact file, phrase and occurrence count.
PHRASE_OCCURRENCES.update({
    ('paper/availability.tex', '600 evaluation seed summaries'): 1,
    ('paper/transport_followup.tex', '$0.16\\%$'): 1,
    ('paper/transport_followup.tex', '$0.28\\%$'): 1,
    ('paper/transport_followup.tex', '$12.13\\%$'): 1,
    ('paper/transport_followup.tex', '$12.68\\%$'): 1,
    ('paper/transport_followup.tex', '$T=1000$'): 2,
    ('paper/transport_followup.tex', '$W=0.25$'): 1,
    ('paper/transport_followup.tex', '$W=16,1,0.25$'): 3,
    ('paper/transport_followup.tex', '$W\\in\\{16,1,0.25\\}$'): 1,
    ('paper/transport_followup.tex', '$[92.9\\%,100\\%]$'): 1,
    ('paper/transport_followup.tex', '$\\delta=0.05$'): 1,
    ('paper/transport_followup.tex', '10,000'): 2,
    ('paper/transport_followup.tex', '16 of 50 seeds'): 1,
    ('paper/transport_followup.tex', '20 full-batch steps'): 1,
    ('paper/transport_followup.tex', '2000, 2000, and 1000'): 1,
    ('paper/transport_followup.tex', '286 of 50,000'): 1,
    ('paper/transport_followup.tex', '29-parameter'): 1,
    ('paper/transport_followup.tex', '294 development and tuning trajectories'): 1,
    ('paper/transport_followup.tex', '50 common evaluation seeds'): 1,
    ('paper/transport_followup.tex', '50 histories'): 3,
    ('paper/transport_followup.tex', '50 seeds per condition'): 1,
    ('paper/transport_followup.tex', '50 successes out of 50'): 1,
    ('paper/transport_followup.tex', '50,000 seed--round observations per condition'): 1,
    ('paper/transport_followup.tex', '600 policy trajectories'): 1,
    ('paper/transport_followup.tex', '97.104\\%'): 1,
    ('paper/transport_followup.tex', '99.372\\%'): 1,
    ('paper/transport_followup.tex', '99.382\\%'): 1,
    ('paper/transport_followup.tex', '99.508\\%'): 1,
    ('paper/transport_followup.tex', '99.962\\%'): 1,
    ('paper/transport_followup.tex', '99.982\\%'): 1,
    ('paper/transport_followup.tex', 'All 600 evaluation trajectories'): 1,
    ('paper/transport_followup.tex', 'all 150 of its trajectories'): 1,
    ('paper/transport_followup.tex', 'all 600 preserved trajectories'): 1,
    ('paper/transport_followup.tex', 'approximately 9.51, 37.19, and 80.91'): 1,
    ('paper/transport_followup.tex', 'approximately 19, 60, and 231'): 1,
    ('paper/transport_followup.tex', 'dimension 29'): 1,
    ('paper/transport_followup.tex', 'exact 95\\% Clopper--Pearson interval'): 1,
    ('paper/transport_followup.tex', 'learning rate $3\\times10^{-4}$'): 1,
    ('paper/transport_followup.tex', 'of 50,000 seed--round observations'): 1,
    ('paper/transport_followup.tex', 'paired 95\\% intervals'): 1,
    ('paper/transport_followup.tex', 'pointwise 95\\% paired'): 1,
    ('paper/transport_followup.tex', 'regrets 180.01, 177.97, and 171.84'): 1,
    ('paper/transport_followup.tex', 'regrets 185.26, 183.06, and 176.67'): 1,
    ('paper/transport_followup.tex', 'same 600 recorded histories'): 1,
    ('paper/transport_followup.tex', 'standard deviation $0.25$'): 1,
    ('paper/transport_followup.tex', 'there are five actions'): 1,
    ('paper/transport_followup_appendix.tex', '$0.00392155$'): 1,
    ('paper/transport_followup_appendix.tex', '$T=1000$'): 1,
    ('paper/transport_followup_appendix.tex', '50 paired evaluation seeds'): 1,
    ('paper/transport_followup_appendix.tex', 'pointwise 95\\% paired'): 1,
    ('paper/transport_followup_appendix.tex', '$0.005$'): 1,
    ('paper/transport_followup_appendix.tex', '$0.124$'): 1,
    ('paper/transport_followup_appendix.tex', '$1.735$'): 1,
    ('paper/transport_followup_appendix.tex', '$3\\times4\\times50=600$'): 1,
    ('paper/transport_followup_appendix.tex', '$4+5+20=29$'): 1,
    ('paper/transport_followup_appendix.tex', '$5.300$'): 1,
    ('paper/transport_followup_appendix.tex', '$\\{1,5,20\\}$'): 1,
    ('paper/transport_followup_appendix.tex', '$\\{3\\times10^{-5},10^{-4},3\\times10^{-4}\\}$'): 1,
    ('paper/transport_followup_appendix.tex', '10,000'): 1,
    ('paper/transport_followup_appendix.tex', '1000 rounds in its denominator'): 1,
    ('paper/transport_followup_appendix.tex', '1024'): 1,
    ('paper/transport_followup_appendix.tex', '12 combinations'): 1,
    ('paper/transport_followup_appendix.tex', '2--10'): 1,
    ('paper/transport_followup_appendix.tex', '20 steps'): 1,
    ('paper/transport_followup_appendix.tex', '2048'): 3,
    ('paper/transport_followup_appendix.tex', '24 declared trajectories'): 1,
    ('paper/transport_followup_appendix.tex', '24 development trajectories'): 1,
    ('paper/transport_followup_appendix.tex', '250-digit'): 1,
    ('paper/transport_followup_appendix.tex', '270 tuning trajectories'): 1,
    ('paper/transport_followup_appendix.tex', '294 development and tuning trajectories'): 1,
    ('paper/transport_followup_appendix.tex', '30 tuning'): 1,
    ('paper/transport_followup_appendix.tex', '30000--30001'): 1,
    ('paper/transport_followup_appendix.tex', '30100--30109'): 1,
    ('paper/transport_followup_appendix.tex', '30200--30249'): 1,
    ('paper/transport_followup_appendix.tex', '4096'): 1,
    ('paper/transport_followup_appendix.tex', '50 evaluation seeds'): 1,
    ('paper/transport_followup_appendix.tex', '50 seeds per condition'): 1,
    ('paper/transport_followup_appendix.tex', '50,000 dependent states'): 1,
    ('paper/transport_followup_appendix.tex', '600,000 states'): 1,
    ('paper/transport_followup_appendix.tex', '65 changes'): 1,
    ('paper/transport_followup_appendix.tex', 'Candidate 008'): 1,
    ('paper/transport_followup_appendix.tex', 'across 50 seeds'): 1,
    ('paper/transport_followup_appendix.tex', 'all 600 trajectories'): 1,
    ('paper/transport_followup_appendix.tex', 'and 1000 rounds'): 1,
    ('paper/transport_followup_appendix.tex', 'at 16 states'): 1,
    ('paper/transport_followup_appendix.tex', 'below 0.629'): 1,
    ('paper/transport_followup_appendix.tex', 'divided by 1000'): 1,
    ('paper/transport_followup_appendix.tex', 'learning rate $3\\times10^{-4}$'): 1,
    ('paper/transport_followup_appendix.tex', 'rounds 1, 2, 10, 100, 500, and 1000'): 1,
    ('paper/transport_followup_appendix.tex', 'summarize 50 seeds'): 1,
    ('paper/transport_followup_appendix.tex', 'teacher seed 1729'): 1,
    ('paper/transport_followup_appendix.tex', 'the 600\ntrajectories'): 1,
})


def _mirror_readme(table: dict) -> dict:
    """Copy the repository README's rows onto the packaged README name."""

    mirrored = dict(table)
    repo_readme = str(SUPPLEMENT_README_REPO)
    for (path, key), value in list(table.items()):
        if path == repo_readme:
            mirrored[(str(SUPPLEMENT_README_PACKAGED), key)] = value
    return mirrored


def phrase_occurrences(root: Path) -> dict[tuple[str, str], int]:
    """(file, phrase) -> allowed occurrence count, from the pinned record."""

    return {key: value[0] for key, value in _mirror_readme(pins.PHRASE_PINS).items()}


def phrase_pins(root: Path
                ) -> dict[tuple[str, str], tuple[int, tuple[tuple[str, int], ...]]]:
    """(file, phrase) -> (count, the complete semantic unit of each occurrence)."""

    return _mirror_readme(pins.PHRASE_PINS)


def classified_pins(
        root: Path
) -> dict[tuple[str, str], tuple[str, int, tuple[tuple[str, int], ...]]]:
    """(file, literal) -> (category, count, the unit of each occurrence)."""

    return _mirror_readme(pins.CLASSIFIED_PINS)


def file_pins(root: Path) -> dict[str, str]:
    """file -> digest of its whole normalized auditable text."""

    mirrored = dict(pins.FILE_PINS)
    repo_readme = str(SUPPLEMENT_README_REPO)
    if repo_readme in mirrored:
        mirrored[str(SUPPLEMENT_README_PACKAGED)] = mirrored[repo_readme]
    return mirrored


def first_unit_difference(want: Sequence[tuple[str, int]],
                          got: Sequence[tuple[str, int]]) -> str:
    """A reviewable description of how two unit lists differ."""

    if len(want) != len(got):
        return f"{len(got)} occurrence(s) in units, pinned {len(want)}"
    for index, (expected, actual) in enumerate(zip(want, got)):
        if expected == actual:
            continue
        if expected[1] != actual[1] and expected[0] == actual[0]:
            return (f"occurrence {index + 1} moved inside its unit: "
                    f"offset {actual[1]}, pinned {expected[1]}")
        return (f"occurrence {index + 1} is in a different unit\n"
                f"          pinned: {expected[0][:220]!r}\n"
                f"          found : {actual[0][:220]!r}")
    return ""

#: The one arithmetic illustration in the theory appendices.  It is not a
#: measurement: the three inputs are stated in the same sentence and the two
#: products follow from them, so the check is that the arithmetic is right.
COST_ILLUSTRATION = {
    "candidates": (r"$K=10$", 10),
    "iterations": (r"$I=25$", 25),
    "buffer": (r"$m_t=256$", 256),
    "recurrence_cvps": (r"$64{,}000$", 64_000),
    "with_residual_cvps": (r"$66{,}560$", 66_560),
}

# A TeX length, written the way every length in these sources is written: the
# unit immediately follows the number.  Allowing whitespace here would blank
# "126.7 in the study" as if it were 126.7 inches, and a study value smuggled
# into a theory source would then pass the audit unseen.
_TEX_DIMENSION = re.compile(
    r"(?<![0-9A-Za-z_.\\])\d*\.?\d+(?:pt|bp|cm|mm|in|em|ex|pc|sp|dd|cc)\b"
    r"|(?<![0-9A-Za-z_.\\])\d*\.?\d+\\(?:text|column|line|page)(?:width|height)"
)
_SHA_LABEL = re.compile(r"SHA-256")
_NUMBER = re.compile(
    # scientific notation written as a TeX product or a bare power of ten
    r"(?<![0-9A-Za-z_.\\])\d[\d]*(?:[.,]\d+|\{,\}\d+)*\\times10\^\{?-?\d+\}?"
    r"|(?<![0-9A-Za-z_.\\])\d[\d]*\^\{?-?\d+\}?"
    # plain decimals, thousands separators and printed sets
    r"|(?<![0-9A-Za-z_.\\])\d[\d]*(?:[.,]\d+|\{,\}\d+)*"
    # a leading-dot decimal is still a number.  `.1` used to be invisible to
    # the recognizer, which is how a reviewer replaced a reported 180.4 with
    # `.1` and left the audit reporting nothing at all.
    r"|(?<![0-9A-Za-z_.\\])\.\d+"
)

# TeX accepts both `\input{file}` and the plain-TeX `\input file`, and LaTeX
# adds `\include{file}`.  The recogniser knew only the braced form, so an
# unbraced `\input` was a source the audit never opened.  The compiled closure
# manifest is the release authority; this parser is the repository preflight.
_INPUT = re.compile(
    r"\\(?:input|include)\s*\{([^}]+)\}"
    r"|\\input\s+([^\s{}\\%]+)"
)

#: The compiled-source-closure manifest, written by packaging from the LaTeX
#: recorder's own output.  When it is present it is the authority; the `\input`
#: walk below is only used in a repository tree, where no build has run.
SOURCE_CLOSURE_NAME = "SOURCE_CLOSURE.json"


def document_body(text: str) -> str:
    r"""The part of a source that is content, not preamble.

    Only the submission entry point has a preamble; the \input sources are all
    body.  Class options, package options and PDF-metadata assignments are
    typesetting configuration, so auditing them for empirical claims would be
    noise, not rigour.
    """

    start = text.find(r"\begin{document}")
    if start < 0:
        return text
    end = text.find(r"\end{document}", start)
    return text[start:end if end >= 0 else len(text)]


strip_tex_comments = tex_conditionals.strip_comments


def visible_tex(text: str) -> str:
    r"""The bytes a reader sees: comments gone, the venue switch resolved.

    Both steps are load-bearing.  Matching against a file that still carried its
    comments let a visible `180.4` be replaced by `.1` while the old value
    stayed behind in a `%` comment to satisfy the literal check, and leaving the
    switch unresolved would audit text no reader of this submission sees.
    """

    return tex_conditionals.resolve(strip_tex_comments(text), legacy=False)


#: The character inserted where one semantic unit ends and the next begins.  NUL
#: cannot appear in a TeX source or a Markdown file, the numeric recogniser does
#: not match it, and -- unlike the ASCII separator characters, which Python
#: counts as whitespace -- it survives `normalize_prose`.  That last point is not
#: a detail: an earlier draft used `\x1d`, `str.split()` ate every marker, and
#: each file came out as a single unit, which is the failure mode this pin
#: exists to prevent.
UNIT_BREAK = "\x00"

#: Where a semantic unit ends.  These are the boundaries a reader sees: a blank
#: line ends a paragraph, `\\` ends a table row, `&` ends a cell, `\item` starts
#: a list entry, a sectioning command starts a section, and an environment or a
#: caption is a block of its own.  Splitting on them turns a TeX source into the
#: units a number can sensibly be said to live in.
_UNIT_BOUNDARY = re.compile(
    r"\n[ \t]*\n\s*"                                  # paragraph break
    r"|\\par\b"
    r"|\\\\(?:\s*\[[^\]]*\])?"                        # row break, optional skip
    r"|(?<!\\)&"                                      # cell separator
    r"|\\item\b"
    r"|\\(?:sub)*(?:section|paragraph)\*?\b"
    r"|\\(?:begin|end)\s*\{[^}]*\}"
    r"|\\caption\b"
    r"|\\(?:midrule|toprule|bottomrule|hline)\b"
)


def split_into_units(text: str) -> str:
    """`text` with a unit break at every semantic boundary."""

    return _UNIT_BOUNDARY.sub(f" {UNIT_BREAK} ", text)


def drop_empty_units(text: str) -> str:
    """Collapse runs of unit breaks and trim the ends.

    Two adjacent boundaries -- `\\end{x}` immediately followed by a blank line,
    or a trailing conditional that resolved to nothing -- would otherwise leave
    an empty unit, and the whole-file digest would change for an edit that
    altered no text a reader sees.
    """

    units = [unit.strip() for unit in text.split(UNIT_BREAK)]
    return f" {UNIT_BREAK} ".join(unit for unit in units if unit)


def enclosing_unit(text: str, start: int, end: int) -> tuple[str, int]:
    """The complete unit an occurrence sits in, and its offset inside it.

    A fixed radius was the previous pin, and it could not see a meaning-changing
    edit past its own edge: "the median is 126.7" and "the median is 126.7, for
    the discarded pilot run" differ only 41 characters away from the number.  A
    unit has no edge to hide behind -- the whole sentence, cell, item, caption or
    paragraph is the pin, so any edit inside it is a mismatch.
    """

    left = text.rfind(UNIT_BREAK, 0, start)
    left = 0 if left < 0 else left + 1
    right = text.find(UNIT_BREAK, end)
    right = len(text) if right < 0 else right
    raw = text[left:right]
    # `text` is already whitespace-collapsed, so the only thing `strip` removes
    # is the single space each inserted break carries; subtracting exactly that
    # keeps the offset exact rather than approximately right.
    lead = len(raw) - len(raw.lstrip())
    unit = raw.strip()
    return unit, max(0, min(start - left - lead, len(unit)))


def occurrence_units(text: str, spans: Sequence[tuple[int, int]]
                     ) -> tuple[tuple[str, int], ...]:
    """The complete semantic unit of each occurrence, in document order.

    Returned as `(unit, offset)` pairs so that two occurrences of the same
    number in one unit stay distinguishable, and so a number that moves within
    its own sentence is still a mismatch.
    """

    return tuple(enclosing_unit(text, start, end) for start, end in sorted(spans))


def units_digest(units: Sequence[tuple[str, int]]) -> str:
    """A compact identity for an ordered unit list, for printing and logs."""

    joined = "\x1f".join(f"{offset}:{unit}" for unit, offset in units)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def file_digest(text: str) -> str:
    """A digest over the whole normalized auditable text of one source.

    An additional fail-closed binding, not a substitute for the per-occurrence
    units: it catches a meaning-changing edit in a part of the file that holds
    no pinned number -- a redefined symbol, a reversed caveat, a deleted
    qualification -- which no per-occurrence pin can see.  The units stay because
    a whole-file digest says only "something changed", and a reviewer needs to
    know what.
    """

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def mask_typesetting(text: str) -> str:
    """Blank the spans that are typesetting or naming, not claims.

    Column widths and the "SHA-256" label carry digits that say nothing about
    the study.  Blanking rather than deleting keeps every other offset intact.
    """

    text = _TEX_DIMENSION.sub(lambda m: " " * len(m.group(0)), text)
    return _SHA_LABEL.sub(lambda m: " " * len(m.group(0)), text)


def auditable_text(path: Path) -> str:
    """One source, reduced to the prose and mathematics an audit should read.

    Unit breaks go in before whitespace is collapsed, because the most important
    boundary -- the blank line that ends a paragraph -- is whitespace and would
    otherwise be gone by the time anything could see it.
    """

    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".tex":
        raw = document_body(visible_tex(raw))
    return mask_typesetting(
        drop_empty_units(normalize_prose(split_into_units(raw))))


def manuscript_closure(root: Path) -> list[Path]:
    r"""Every source the entry point transitively \inputs, relative to `root`.

    Derived from the files rather than from a maintained list, so a source added
    to the manuscript is audited the moment it is typeset.
    """

    order: list[Path] = []
    seen: set[Path] = set()
    base = root.resolve()

    def walk(path: Path) -> None:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file():
            return
        seen.add(resolved)
        try:
            order.append(resolved.relative_to(base))
        except ValueError:                       # outside the tree; ignore
            return
        # Only the branch this submission compiles: a source reachable solely
        # from the legacy branch is not submitted evidence and must not be
        # audited as though it were.
        for match in _INPUT.finditer(visible_tex(
                resolved.read_text(encoding="utf-8"))):
            target = Path(match.group(1) or match.group(2))
            if not target.suffix:
                target = target.with_suffix(".tex")
            walk(root / "paper" / target)

    walk(root / ENTRY_POINT)
    return sorted(order, key=str)


#: Closure roles whose text the number audit reads.  The rest of the compiled
#: closure -- the venue template, the bibliography and its bibtex output, the
#: figure data CSVs -- is covered by the pinned template digests, by the
#: bibliography's own content, and by byte-identical artifact regeneration.
AUDITED_CLOSURE_ROLES = ("entry-point", "manuscript-source",
                         "generated-artifact")


def closure_manifest(root: Path) -> dict | None:
    """The compiled-source-closure manifest, if this tree carries one."""

    path = root / SOURCE_CLOSURE_NAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


#: Exactly the top-level keys the manifest may carry.
CLOSURE_MANIFEST_KEYS = frozenset({"schema_version", "what_this_is", "entries"})

#: Exactly the per-entry keys, with the exact type each must have.  These are
#: compared with `type(value) is ...`, not `isinstance`: in Python `bool` is a
#: subclass of `int`, so `isinstance(True, int)` is true and a manifest could
#: write `"bytes": true` and satisfy an isinstance check.  `True` then compares
#: equal to `1`, so a one-byte file would pass the byte binding.  Exact types
#: close that and every other subclass substitution.  `repository` may be null
#: only for the bibtex output, which has no repository source; that exception is
#: derived from the staged path below, not taken from the entry.
CLOSURE_ENTRY_TYPES: dict[str, tuple[type, ...]] = {
    "staged": (str,),
    "repository": (str, type(None)),
    "sha256": (str,),
    "bytes": (int,),
    "role": (str,),
    "ships_in": (str,),
}

#: The three places a compiled input's bytes can be.  `in_supplement` used to be
#: a boolean here, and a boolean cannot say that `main.bbl` is in *neither*
#: archive: reading "not in the supplement" as "therefore in source.zip" was
#: wrong for the one entry where it mattered.
CLOSURE_ARCHIVES = ("supplement", "source", "neither")

CLOSURE_SCHEMA_VERSION = 2

#: Where the vendored third-party packages live in the repository, and the
#: staged names they compile under.  They are exempt from the per-literal
#: number audit for the same reason the venue template is -- the numbers in
#: them are code, not claims about this study -- and packaging holds them to
#: pinned digests instead; see `package.VENDORED_PACKAGE_DIGESTS` and
#: `paper/texmf_vendor/VENDORED-PACKAGES.md`.
VENDORED_DIRECTORY = "paper/texmf_vendor"
VENDORED_PACKAGE_NAMES = frozenset({
    'LICENSE-gpl-3-0',
    'LICENSE-lgpl-2-1',
    'LICENSE-lppl-1-2',
    'LICENSE-lppl-1-3c',
    'algorithm.sty',
    'algorithmic.sty',
    'algorithms.dtx',
    'algorithms.ins',
    'cleveref.sty',
    'mathtools.sty',
    'mhsetup.sty',
    'microtype-pdftex.def',
    'microtype.cfg',
    'microtype.sty',
    'mt-cmr.cfg',
    'mt-msa.cfg',
    'mt-msb.cfg',
    'pgflibraryfillbetween.code.tex',
    'pgflibrarypgfplots.surfshading.code.tex',
    'pgflibrarypgfplots.surfshading.pgfsys-pdftex.def',
    'pgfplots.code.tex',
    'pgfplots.errorbars.code.tex',
    'pgfplots.markers.code.tex',
    'pgfplots.paths.code.tex',
    'pgfplots.revision.tex',
    'pgfplots.scaling.code.tex',
    'pgfplots.sty',
    'pgfplotsarray.code.tex',
    'pgfplotsbinary.code.tex',
    'pgfplotsbinary.data.code.tex',
    'pgfplotscolor.code.tex',
    'pgfplotscolormap.code.tex',
    'pgfplotscoordprocessing.code.tex',
    'pgfplotscore.code.tex',
    'pgfplotsdeque.code.tex',
    'pgfplotslibrary.code.tex',
    'pgfplotsliststructure.code.tex',
    'pgfplotsliststructureext.code.tex',
    'pgfplotsmatrix.code.tex',
    'pgfplotsmeshplothandler.code.tex',
    'pgfplotsmeshplotimage.code.tex',
    'pgfplotsoldpgfsupp_loader.code.tex',
    'pgfplotsplothandlers.code.tex',
    'pgfplotsstackedplots.code.tex',
    'pgfplotssysgeneric.code.tex',
    'pgfplotstableshared.code.tex',
    'pgfplotsticks.code.tex',
    'pgfplotsutil.code.tex',
    'pgfplotsutil.verb.code.tex',
    'tikzlibrarydecorations.softclip.code.tex',
    'tikzlibraryfillbetween.code.tex',
    'tikzlibrarypgfplots.decorations.softclip.code.tex',
    'tikzlibrarypgfplots.fillbetween.code.tex',
    'tikzlibrarypgfplots.groupplots.code.tex',
})

#: The staged names whose repository source is a style file rather than a
#: manuscript source, and the directory they come from.
CLOSURE_STYLE_DIRECTORY = "paper/tmlr_style"
CLOSURE_STYLE_FILES = {"tmlr.sty", "tmlr.bst", "fancyhdr.sty"}
CLOSURE_ENTRY_POINT_REPOSITORY = "submissions/tmlr_2026/main.tex"

#: Roles whose entry legitimately has no repository path.
CLOSURE_ROLES_WITHOUT_SOURCE = frozenset({"bibliography-output"})

#: Suffixes under `paper/` that a package may only carry if the manifest
#: records them as compiled inputs.  These are the typeset sources: if one is in
#: the archive and not in the closure, either the closure is short or the
#: archive is carrying manuscript text nobody audited.
COMPILED_SHIPPED_SUFFIXES = frozenset({".tex", ".sty", ".bst"})

#: Data suffixes under `paper/`.  These need not be compiled inputs -- the full
#: per-figure CSVs ship as evidence while only the per-panel slices are read by
#: pgfplots -- but every one of them must be bound to bytes somehow: either the
#: closure records it, or a `.sha256` sidecar in the same archive does.
DATA_SHIPPED_SUFFIXES = frozenset({".csv", ".bib"})

#: The one shipped source that is neither compiled by pdfTeX nor sidecarred:
#: bibtex reads it, and its content is bound by `main.bbl`, which *is* a
#: recorded compiled input carrying the rendered entries.
CLOSURE_UNSIDECARRED_SOURCES = frozenset({"paper/references.bib"})

#: Every directory a shipped manuscript source may live in.  The sweep below
#: walks all of them recursively: `paper/` holds the manuscript, and
#: `submissions/tmlr_2026/` holds the entry point, which a `paper/`-only sweep
#: could not see.
SHIPPED_SOURCE_ROOTS = ("paper", "submissions/tmlr_2026")

#: Directories whose contents are not compiled inputs under their repository
#: names.  `tmlr_style/` and `texmf_vendor/` both travel in `source.zip` under
#: flat staged names, and the manifest records them that way, so the recursive
#: sweep would otherwise report the venue template and the vendored packages as
#: undeclared shipped sources.
CLOSURE_IGNORED_DIRECTORIES = frozenset({"tmlr_style", "texmf_vendor"})

#: Licence texts that travel with the vendored code.  They are shipped, not
#: compiled: pdfTeX never opens them, so they are not in the closure and must
#: not be required to be.
VENDORED_LICENSE_NAMES = frozenset(
    name for name in VENDORED_PACKAGE_NAMES if name.startswith("LICENSE-"))

#: Exact package sources shipped for the algorithms bundle's licence terms.
#: They generate the two style files but are not themselves pdfTeX inputs.
VENDORED_SOURCE_EXTRA_NAMES = frozenset({"algorithms.dtx", "algorithms.ins"})

#: Compiler inputs that must be recorded exactly once and byte-bound even
#: though the supplement does not carry them.  `main.bbl` is the case that
#: mattered: bibtex writes it during the build, it travels in neither archive,
#: and every other check here is driven by bytes an archive holds -- so its
#: entry could have been deleted and nothing would have said a word.  The venue
#: template and the vendored packages are in the same position, and are listed
#: by derivation rather than by hand so the list cannot fall behind.
#:
#: `tmlr.bst` and `references.bib` are deliberately absent: bibtex reads them,
#: pdfTeX does not, so they appear in `source.zip` but never in `main.fls`.
MANDATORY_NON_SUPPLEMENT_STAGED = tuple(sorted(
    {"main.bbl", "tmlr.sty", "fancyhdr.sty"}
    | (VENDORED_PACKAGE_NAMES - VENDORED_LICENSE_NAMES - VENDORED_SOURCE_EXTRA_NAMES)))


def derive_repository_path(staged: str) -> str | None:
    r"""The exact repository path a staged name must have come from.

    The staged tree is flat, and packaging builds it by copying from four
    places.  Recomputing the whole path rather than comparing basenames is what
    stops `figures/x.csv` from claiming it came from `experiments/x.csv`: a
    basename check passes that, and the audit would then read a different file
    from the one the compiler opened.

    Returns None for the one staged input that has no repository source --
    `main.bbl`, which bibtex writes during the build.
    """

    if staged == "main.bbl":
        return None
    if staged == "main.tex":
        return CLOSURE_ENTRY_POINT_REPOSITORY
    if staged == "LICENSE-tmlr-style":
        return f"{CLOSURE_STYLE_DIRECTORY}/LICENSE"
    if staged in CLOSURE_STYLE_FILES:
        return f"{CLOSURE_STYLE_DIRECTORY}/{staged}"
    if staged in VENDORED_PACKAGE_NAMES:
        return f"{VENDORED_DIRECTORY}/{staged}"
    if staged.startswith(("tables/", "figures/")):
        return f"paper/{staged}"
    if "/" in staged:
        return None                       # no other nesting is staged at all
    return f"paper/{staged}"

#: Which roles the supplement is expected to carry.  The venue template and the
#: bibtex output ship in source.zip instead, and the audit derives membership
#: from this rather than believing the manifest's own claim.
SUPPLEMENT_ROLES = frozenset({
    "entry-point", "manuscript-source", "generated-artifact", "figure-data",
    "bibliography",
})

#: How a role is *derived* from a validated path.  The manifest states a role,
#: but the audit recomputes it and requires agreement: a role read out of the
#: input would let a manuscript source relabel itself as figure data and drop
#: out of the number audit.
def derive_closure_role(staged: str) -> str:
    if staged == "main.tex":
        return "entry-point"
    if staged in VENDORED_PACKAGE_NAMES:
        return "vendored-package"
    if staged in ("tmlr.sty", "tmlr.bst", "fancyhdr.sty", "LICENSE-tmlr-style"):
        return "venue-template"
    if staged == "main.bbl":
        return "bibliography-output"
    if staged.endswith(".bib"):
        return "bibliography"
    if staged.endswith(".csv"):
        return "figure-data"
    if f"paper/{staged}" in ANALYTICAL_SCHEMATIC_SOURCES:
        return "manuscript-source"
    if staged.startswith(("tables/", "figures/")):
        return "generated-artifact"
    return "manuscript-source"


def closure_manifest_checks(root: Path, *,
                            require_manifest: bool = False) -> list[Check]:
    r"""Validate the compiled-source-closure manifest as a strict contract.

    The manifest says what the compiler read while producing the submitted PDF,
    and everything downstream is read through it, so nothing in it may be taken
    on trust.  Every invariant below has to hold before a single entry is used:
    shape, schema, key sets, types, canonical and unique paths, containment,
    file type, the staged-to-repository mapping, the role (recomputed, not
    read), supplement membership (recomputed, not read), and the byte binding.

    In package mode a missing manifest is itself a failure.  In repository mode
    there is no manifest and none is required -- the `\input` preflight stands
    in -- but repository mode cannot certify a packaged release either way.
    """

    checks: list[Check] = []

    def expect(name, ok, detail=""):
        checks.append(Check(name, STATUS_PASS if ok else STATUS_FAIL, detail))

    path = root / SOURCE_CLOSURE_NAME
    if not path.is_file():
        if require_manifest:
            expect(f"{SOURCE_CLOSURE_NAME} is present (required in a package)",
                   False, f"no {SOURCE_CLOSURE_NAME} at {root}")
        return checks

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        expect(f"{SOURCE_CLOSURE_NAME} parses", False, repr(error))
        return checks
    if not isinstance(manifest, dict):
        expect(f"{SOURCE_CLOSURE_NAME} is an object", False,
               type(manifest).__name__)
        return checks

    keys = set(manifest)
    expect(f"{SOURCE_CLOSURE_NAME} has exactly the pinned top-level keys",
           keys == CLOSURE_MANIFEST_KEYS,
           f"missing {sorted(CLOSURE_MANIFEST_KEYS - keys)}; "
           f"unexpected {sorted(keys - CLOSURE_MANIFEST_KEYS)}")
    # Exact type, then value.  `True == 1`, so a manifest could declare
    # `"schema_version": true` and satisfy an equality test against 1; the same
    # trap the per-entry scalar check closes.
    expect(f"{SOURCE_CLOSURE_NAME} declares a supported schema version",
           type(manifest.get("schema_version")) is int
           and manifest.get("schema_version") == CLOSURE_SCHEMA_VERSION,
           f"got {manifest.get('schema_version')!r} of type "
           f"{type(manifest.get('schema_version')).__name__}")
    expect(f"{SOURCE_CLOSURE_NAME} describes itself in text",
           type(manifest.get("what_this_is")) is str
           and manifest.get("what_this_is", "").strip(),
           f"got {type(manifest.get('what_this_is')).__name__}")

    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        expect(f"{SOURCE_CLOSURE_NAME} lists compiled inputs", False,
               f"got {type(entries).__name__}")
        return checks

    shape = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            shape.append(f"entry {index} is {type(entry).__name__}")
            continue
        got = set(entry)
        if got != set(CLOSURE_ENTRY_TYPES):
            shape.append(
                f"entry {index} keys: missing "
                f"{sorted(set(CLOSURE_ENTRY_TYPES) - got)}, unexpected "
                f"{sorted(got - set(CLOSURE_ENTRY_TYPES))}")
            continue
        for key, types in CLOSURE_ENTRY_TYPES.items():
            # `type(...) is`, not isinstance: bool subclasses int, so
            # `"bytes": true` would pass an isinstance check and then compare
            # equal to a one-byte file.
            if type(entry[key]) not in types:
                shape.append(f"entry {index} {key} is exactly "
                             f"{type(entry[key]).__name__}, not one of "
                             f"{[t.__name__ for t in types]}")
    expect("every manifest entry has exactly the pinned keys and scalar types",
           not shape, "; ".join(shape[:6]))
    if shape:
        return checks

    staged_names = [e["staged"] for e in entries]
    expect("no compiled input is listed twice",
           len(staged_names) == len(set(staged_names)),
           f"{len(staged_names)} entries, {len(set(staged_names))} distinct")

    repositories = [e["repository"] for e in entries if e["repository"]]
    expect("no repository path is listed twice",
           len(repositories) == len(set(repositories)),
           f"{len(repositories)} paths, {len(set(repositories))} distinct")

    def unsafe(name: str) -> bool:
        parts = Path(name).parts
        return (name.startswith("/") or ".." in parts or "." in parts
                or name != os.path.normpath(name) or not name.strip())

    bad_paths = sorted({n for n in staged_names if unsafe(n)}
                       | {n for n in repositories if unsafe(n)})
    expect("no compiled input has an unsafe or noncanonical path",
           not bad_paths, f"unsafe: {bad_paths}")

    # A null repository path is allowed for exactly one derived role -- the
    # bibtex output, which no repository file backs.  Anything else claiming
    # `"repository": null` would drop straight out of the byte binding below,
    # so the exception is derived from the staged path, never granted by the
    # entry.
    wrong_null = sorted(
        f"{e['staged']}: repository is "
        f"{'null' if e['repository'] is None else 'set'}, derived role "
        f"{derive_closure_role(e['staged'])!r}"
        for e in entries
        if (e["repository"] is None)
        != (derive_closure_role(e["staged"]) in CLOSURE_ROLES_WITHOUT_SOURCE))
    expect("only the generated bibliography output has no repository path",
           not wrong_null, "; ".join(wrong_null[:6]))

    # The staged name determines the repository path exactly.  Comparing only
    # basenames, which is what this did before, accepts `figures/x.csv <-
    # experiments/x.csv`: the audit would then read a different file from the
    # one the compiler opened, under a name that looks right.
    mismatched = sorted(
        f"{e['staged']} <- {e['repository']} (derived "
        f"{derive_repository_path(e['staged'])})"
        for e in entries
        if e["repository"] != derive_repository_path(e["staged"]))
    expect("every staged name maps to exactly its derived repository path",
           not mismatched, "; ".join(mismatched[:6]))

    contained = sorted(
        e["repository"] for e in entries if e["repository"]
        and not (Path(e["repository"]).parts
                 and Path(e["repository"]).parts[0] in
                 ("paper", "submissions", "tools", "experiments", "results")))
    expect("every repository path is inside a known project directory",
           not contained, f"outside: {contained[:6]}")

    wrong_role = sorted(
        f"{e['staged']}: says {e['role']!r}, derived "
        f"{derive_closure_role(e['staged'])!r}"
        for e in entries if e["role"] != derive_closure_role(e["staged"]))
    expect("every role is the one derived from the validated path",
           not wrong_role, "; ".join(wrong_role[:6]))

    # THE set check, before anything about individual bytes.  The manifest
    # cannot be its own authority: a reviewer deleted one recorded figure CSV
    # from it and full verification stayed green, because the file's `.sha256`
    # sidecar still verified its bytes and nothing required the file to be in
    # the closure at all.  A sidecar says "these are the bytes I expect"; only
    # the closure says "and the compiler read this file".
    #
    # So the expected set comes from `contract.COMPILED_CLOSURE`, which lives in
    # the package-contract module rather than in the manifest it judges.  Exact
    # in every direction: missing, extra, duplicated, or remapped all fail here,
    # before a single sidecar is consulted.
    declared = [e["staged"] for e in entries]
    pinned_closure = contract.COMPILED_CLOSURE
    absent = sorted(set(pinned_closure) - set(declared))
    unexpected = sorted(set(declared) - set(pinned_closure))
    bad_archive = sorted(
        f"{e['staged']}: ships_in {e['ships_in']!r}"
        for e in entries if e["ships_in"] not in CLOSURE_ARCHIVES)
    expect("every entry names one of the three archives it can be in",
           not bad_archive, "; ".join(bad_archive[:6]))

    expect("the closure declares exactly the pinned set of compiled inputs",
           not absent and not unexpected,
           f"missing from the manifest: {absent[:6]}; not in the contract: "
           f"{unexpected[:6]}")
    remapped = sorted(
        f"{e['staged']}: {field} is {e[field]!r}, the contract says "
        f"{pinned_closure[e['staged']][field]!r}"
        for e in entries if e["staged"] in pinned_closure
        for field in ("repository", "sha256", "bytes", "role", "ships_in")
        if e[field] != pinned_closure[e["staged"]][field])
    expect("every closure entry matches the pinned contract exactly",
           not remapped, "; ".join(remapped[:6]))

    # `ships_in` has to agree with the archive the checker is standing in.  In
    # a supplement, an entry that says `supplement` must be present and one that
    # says `source` or `neither` must not be: that is what stops a false
    # membership claim from excusing a file from the byte binding below.
    packaged = contract.is_packaged_tree(root)
    links, kinds, missing, changed, wrong_membership = [], [], [], [], []
    for entry in entries:
        relative = entry["repository"]
        if relative is None:
            continue
        target = root / relative
        here = target.is_file() and not target.is_symlink()
        expected = entry["ships_in"] == "supplement"
        if expected != (derive_closure_role(entry["staged"]) in SUPPLEMENT_ROLES):
            wrong_membership.append(
                f"{relative}: ships_in {entry['ships_in']!r} disagrees with the "
                f"policy for role {derive_closure_role(entry['staged'])!r}")
        elif packaged and expected != here:
            wrong_membership.append(
                f"{relative}: ships_in says {entry['ships_in']!r}, archive "
                f"has {here}")
        # Every component, not only the leaf.  A symlinked `paper/` directory
        # redirects every entry under it while each leaf still reports as a
        # plain file, which is the whole point of checking the chain.
        linked_component = None
        walk = root
        for part in Path(relative).parts:
            walk = walk / part
            if walk.is_symlink():
                linked_component = str(walk.relative_to(root))
                break
        if linked_component is not None:
            links.append(f"{relative} (via {linked_component})")
            continue
        if not target.exists():
            if entry["ships_in"] == "supplement":
                missing.append(relative)
            continue
        if not target.is_file():
            kinds.append(relative)
            continue
        if sha256_file(target) != entry["sha256"] \
                or target.stat().st_size != entry["bytes"]:
            changed.append(relative)
    expect("no recorded compiled input has a symlink in any path component",
           not links, f"symlinks: {sorted(links)}")
    expect("every recorded compiled input present is a regular file",
           not kinds, f"not regular files: {sorted(kinds)}")
    expect("every recorded compiled input this archive carries is present",
           not missing, f"missing: {sorted(missing)}")
    expect("every recorded compiled input still has its recorded bytes",
           not changed, f"changed: {sorted(changed)}")
    expect("ships_in follows the role policy and the archive in hand",
           not wrong_membership, "; ".join(sorted(wrong_membership)[:6]))

    # The inputs no archive carries still have to be in the closure, exactly
    # once, with a real digest and byte count.  `main.bbl` is the case that
    # mattered: bibtex writes it during the build, it travels in neither
    # archive, and nothing above would have noticed its entry disappearing.
    staged_index: dict[str, list[dict]] = {}
    for entry in entries:
        staged_index.setdefault(entry["staged"], []).append(entry)
    # Only a manifest that claims to describe the whole submission is held to
    # the full list; the entry point is what makes that claim.  A partial
    # manifest fails the completeness checks above instead, which is where a
    # partial manifest belongs.
    if "main.tex" in staged_index:
        mandatory = []
        for name in MANDATORY_NON_SUPPLEMENT_STAGED:
            found = staged_index.get(name, [])
            if len(found) != 1:
                mandatory.append(
                    f"{name}: {len(found)} entries, expected exactly 1")
                continue
            entry = found[0]
            if len(entry["sha256"]) != 64 or not all(
                    c in "0123456789abcdef" for c in entry["sha256"].lower()):
                mandatory.append(f"{name}: sha256 is not a 64-hex digest")
            if entry["bytes"] <= 0:
                mandatory.append(f"{name}: byte count is {entry['bytes']}")
            # The supplement does not carry these files, so the digest cannot
            # be recomputed from bytes beside it.  It can still be compared to
            # the pinned value in the contract module, which is what stops the
            # recorded digest from being quietly rewritten.
            pinned = contract.COMPILED_CLOSURE.get(name)
            if pinned is not None and (entry["sha256"] != pinned["sha256"]
                                       or entry["bytes"] != pinned["bytes"]):
                mandatory.append(
                    f"{name}: records {entry['sha256']} ({entry['bytes']} "
                    f"bytes), the pinned contract says {pinned['sha256']} "
                    f"({pinned['bytes']} bytes)")
        expect("every mandatory compiler input is recorded once and byte-bound",
               not mandatory, "; ".join(mandatory[:6]))

    # And nothing typeset escapes the manifest.  The sweep is recursive and
    # covers every suffix the audit or the compiler would read, not just
    # `paper/*.tex` at one level: a nested `paper/parts/extra.tex` or a figure
    # CSV dropped into the archive was previously invisible here, so deleting
    # its manifest entry removed it from the audit without removing it from the
    # package.
    recorded = {e["repository"] for e in entries}
    compiled_shipped: set[str] = set()
    data_shipped: set[str] = set()
    # Every shipped source root, not only `paper/`.  The submission entry point
    # lives under `submissions/tmlr_2026/`, and a `.tex` dropped in beside it
    # would have been invisible to a sweep that looked at `paper/` alone.
    for directory in SHIPPED_SOURCE_ROOTS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if any(part in CLOSURE_IGNORED_DIRECTORIES for part in relative.parts):
                continue
            if path.suffix in COMPILED_SHIPPED_SUFFIXES:
                compiled_shipped.add(relative.as_posix())
            elif path.suffix in DATA_SHIPPED_SUFFIXES:
                data_shipped.add(relative.as_posix())
    # The former numeric tables are supplementary lookup data, not compiled
    # prose. Admit only the eight reviewed tables after authenticating the
    # chart generator and anonymous contract and matching immutable byte pins.
    # A new TeX file or a self-rehashed table never earns this exception.
    lookup_tables: set[str] = set()
    lookup_problem = ""
    retained_tables = set(FOLLOWUP_GENERATED_SOURCES) | {
        name for name in GENERATED_ARTIFACT_SOURCES if name.startswith("paper/tables/")}
    if (compiled_shipped - recorded) & retained_tables:
        try:
            _validated_followup_packaged_sources(root, require_package=require_manifest)
            helper = contract.load_followup_contract(root)
            generator = _load_reviewed_tool(root, TABLE_CHART_GENERATOR)
            expected = {"paper/tables/" + name + ".tex": digest
                        for name, digest in generator.INPUT_HASHES.items()}
            outcomes = "paper/tables/transport_followup_outcomes.tex"
            expected[outcomes] = helper.ARTIFACT_PINS[outcomes]["sha256"]
            if set(expected) != retained_tables or len(expected) != 8:
                raise LedgerError("numeric lookup-table inventory differs")
            for name, digest in expected.items():
                path = root / name
                if (path.is_file() and not path.is_symlink()
                        and sha256_file(path) == digest):
                    lookup_tables.add(name)
        except Exception as error:
            lookup_problem = f"; numeric lookup verification failed: {error}"
    extra = sorted(compiled_shipped - recorded - lookup_tables)
    expect("every shipped manuscript source is a recorded compiled input or a pinned numerical lookup table",
           not extra, f"shipped but neither compiled nor pinned lookup data: {extra}{lookup_problem}")

    # The explanatory TeX embeds its coordinates, so its reviewer-facing CSV
    # exports are not compiler inputs. Admit only the exact reviewed CSV paths
    # after authenticating both implementations, checking the independent
    # artifact pins, and reconstructing their bytes from immutable evidence.
    # A new CSV, editable provenance record, or rewritten sidecar cannot grant
    # this status. Required package mode also requires the full declaration.
    reconstructed: set[str] = set()
    reconstruction_problem = ""
    explanatory_csvs = {name for name in EXPLANATORY_GENERATED_SOURCES
                        if name.endswith(".csv")}
    if (data_shipped - recorded) & explanatory_csvs:
        try:
            _validated_followup_packaged_sources(root, require_package=require_manifest)
            helper = contract.load_followup_contract(root)
            generator = _load_reviewed_tool(root, EXPLANATORY_GENERATOR)
            outputs = generator.build(root)
            expected = {Path(name) for name in EXPLANATORY_GENERATED_SOURCES}
            expected.add(Path(EXPLANATORY_PROVENANCE))
            if set(outputs) != expected:
                raise LedgerError("explanatory output inventory differs")
            for name in explanatory_csvs:
                path = root / name
                pin = helper.ARTIFACT_PINS[name]
                if (path.is_file() and not path.is_symlink()
                        and path.stat().st_size == pin["bytes"]
                        and sha256_file(path) == pin["sha256"]
                        and path.read_bytes() == outputs[Path(name)].encode("utf-8")):
                    reconstructed.add(name)
        except Exception as error:
            reconstruction_problem = f"; explanatory reconstruction failed: {error}"
    loose = sorted(
        name for name in data_shipped - recorded
        if name not in CLOSURE_UNSIDECARRED_SOURCES
        and name not in reconstructed
        and not (root / f"{name}.sha256").is_file())
    expect("every shipped figure-data file is recorded, sidecarred, or independently reconstructed",
           not loose, f"bound to nothing: {loose}{reconstruction_problem}")

    # And the audit actually reads every audited-role source the archive
    # carries: a role whose text the number audit reads, whose bytes are here,
    # must appear in the audited set.  Recursive completeness in the other
    # direction.
    audited_here = sorted(
        e["repository"] for e in entries
        if e["repository"]
        and derive_closure_role(e["staged"]) in AUDITED_CLOSURE_ROLES
        and (root / e["repository"]).is_file())
    expect("every audited source the archive ships is in the audited set",
           set(audited_here) <= {str(p) for p in audited_sources(root)},
           f"shipped but not audited: "
           f"{sorted(set(audited_here) - {str(p) for p in audited_sources(root)})[:6]}")
    return checks


def audited_sources(root: Path) -> list[Path]:
    """The sources the number audit reads, from the compiler where possible.

    In a packaged tree the compiled-source-closure manifest is the authority:
    it was written from the LaTeX recorder's own record of the build that
    produced the submitted PDF. In a repository tree no build has run, so the
    ``\\input`` walk stands in as a preflight.
    """

    manifest = closure_manifest(root)
    if manifest is None:
        sources = manuscript_closure(root)
    else:
        sources = [Path(entry["repository"])
                   for entry in manifest.get("entries", [])
                   if entry.get("repository")
                   and entry.get("role") in AUDITED_CLOSURE_ROLES]
        sources.sort(key=str)
    return sources + list(readme_sources(root))


def masked_text(text: str, covered: Sequence[str]) -> str:
    """`text` with every occurrence of every covered phrase blanked."""

    masked = list(text)
    for needle in covered:
        start = 0
        while True:
            index = text.find(needle, start)
            if index < 0:
                break
            for position in range(index, index + len(needle)):
                masked[position] = " "
            start = index + 1
    return "".join(masked)


def literal_spans(text: str, covered: Sequence[str]
                  ) -> dict[str, list[tuple[int, int]]]:
    """Every remaining numeric literal, with the span of each occurrence."""

    spans: dict[str, list[tuple[int, int]]] = {}
    for match in _NUMBER.finditer(masked_text(text, covered)):
        spans.setdefault(match.group(0), []).append(match.span())
    return spans


def phrase_spans(text: str, phrase: str) -> list[tuple[int, int]]:
    needle = normalize_prose(phrase)
    spans, start = [], 0
    while True:
        index = text.find(needle, start)
        if index < 0:
            return spans
        spans.append((index, index + len(needle)))
        start = index + 1


def uncovered_literals(text: str, covered: Sequence[str]) -> list[str]:
    """Numeric literals left after masking every accounted-for span."""

    masked = list(text)
    for needle in covered:
        start = 0
        while True:
            index = text.find(needle, start)
            if index < 0:
                break
            for position in range(index, index + len(needle)):
                masked[position] = " "
            start = index + 1
    return [m.group(0) for m in _NUMBER.finditer("".join(masked))]


def macro_file_checks(root: Path) -> list[Check]:
    r"""`paper/macros.tex` is declarations, and the check says exactly that.

    It used to be a whole-file exemption, which meant an empirical value written
    into it was waved through.  The file is now required to consist only of
    macro declarations and comments, and to contain no numeric literal at all:
    every macro here is notation, and a number in a notation file has no reason
    to exist.
    """

    checks: list[Check] = []
    path = root / MACRO_SOURCE
    if not path.is_file():
        return [Check(f"macro source present: {MACRO_SOURCE}", STATUS_FAIL,
                      "missing")]
    text = visible_tex(path.read_text(encoding="utf-8"))
    offending = [line.strip() for line in text.splitlines()
                 if line.strip()
                 and not line.lstrip().startswith(MACRO_DECLARATIONS)]
    checks.append(Check(
        f"{MACRO_SOURCE} contains only macro declarations",
        STATUS_PASS if not offending else STATUS_FAIL,
        f"{len(offending)} non-declaration line(s): {offending[:4]}"))
    literals = sorted({m.group(0) for m in _NUMBER.finditer(
        mask_typesetting(normalize_prose(text)))})
    checks.append(Check(
        f"{MACRO_SOURCE} states no numeric value",
        STATUS_PASS if not literals else STATUS_FAIL,
        f"numeric literals found: {literals}"))
    return checks


def symbolic_table_checks(root: Path) -> list[Check]:
    r"""Every cell of the symbolic rate table is a rate, not a measurement.

    Also previously a whole-file exemption.  The table states asymptotic rates
    in `T`, `K` and `q`, so each cell is checked against the alphabet those
    rates use: a decimal point, a comma or any other character is enough to say
    the cell is no longer symbolic.
    """

    checks: list[Check] = []
    path = root / SYMBOLIC_TABLE_SOURCE
    if not path.is_file():
        return [Check(f"symbolic table present: {SYMBOLIC_TABLE_SOURCE}",
                      STATUS_FAIL, "missing")]
    text = visible_tex(path.read_text(encoding="utf-8"))
    # Body rows only.  The header row names the columns in words; it states no
    # value, and the rule is about the cells that do.
    body = text.split("\\midrule", 1)[-1].split("\\bottomrule", 1)[0]
    parsed, offending = [], []
    for line in body.splitlines():
        stripped = line.strip()
        if "&" not in stripped or not stripped.endswith("\\\\"):
            continue
        for cell in stripped[:-2].split("&"):
            cell = cell.strip()
            if not cell:
                continue
            form = parse_symbolic_cell(cell)
            if form is None:
                offending.append(f"{cell!r} is not an asymptotic rate")
            else:
                parsed.append(form)
    checks.append(Check(
        f"every cell of {SYMBOLIC_TABLE_SOURCE} parses as an asymptotic rate",
        STATUS_PASS if not offending and parsed else STATUS_FAIL,
        "; ".join(offending[:4]) or f"{len(parsed)} cells"))
    checks.append(Check(
        f"the cells of {SYMBOLIC_TABLE_SOURCE} are exactly the pinned rates",
        STATUS_PASS if tuple(parsed) == SYMBOLIC_TABLE_CELLS else STATUS_FAIL,
        f"parsed {tuple(parsed)}; pinned {SYMBOLIC_TABLE_CELLS}"))
    return checks


def literal_coverage_checks(root: Path, ledger: Sequence[Entry],
                            *, require_package: bool = False) -> list[Check]:
    """Audit every numeric literal in the submitted manuscript sources."""

    checks: list[Check] = []

    def expect(name, ok, detail=""):
        checks.append(Check(name, STATUS_PASS if ok else STATUS_FAIL, detail))

    sources = audited_sources(root)
    expect("the manuscript closure was resolved",
           len(sources) > 10, f"{len(sources)} sources")
    # In a package the manifest is mandatory and is the release authority; in a
    # repository there is none and the `\input` preflight stands in, which is
    # explicitly not certification of a release.
    checks.extend(closure_manifest_checks(root, require_manifest=require_package))
    if not require_package and closure_manifest(root) is None:
        checks.append(Check(
            "source closure: repository preflight only",
            STATUS_NOT_EXECUTED,
            "no SOURCE_CLOSURE.json in this tree, so the audited set came from "
            "an \\input walk rather than from the compiler. That is a "
            "preflight; it does not certify a packaged release."))

    # The pin module is generated data that ships with the supplement, and the
    # ledger reads it.  Editing a source and regenerating its pin inside an
    # unpacked package would otherwise be self-consistent and pass, so the pin
    # module's own bytes are checked against the contract module first -- before
    # a single pin is consulted.
    for name, ok, detail in contract.check_shipped_tools(root):
        checks.append(Check(name, STATUS_PASS if ok else STATUS_FAIL, detail))
    pin_module = Path(pins.__file__)
    expect("the pin module the ledger loaded is the pinned one",
           sha256_file(pin_module)
           == contract.SHIPPED_TOOL_DIGESTS.get(
               "tools/numeric_context_pins.py"),
           f"loaded {pin_module} at {sha256_file(pin_module)}")

    phrases = phrase_occurrences(root)
    phrase_pinned = phrase_pins(root)
    classified_pinned = classified_pins(root)
    file_pinned = file_pins(root)
    structural = {MACRO_SOURCE, SYMBOLIC_TABLE_SOURCE}
    regenerated = set(ALL_GENERATED_SOURCES)

    # The pinned record and the reviewable category table have to describe the
    # same set: a pin without a category is unexplained, and a category without
    # a pin is unenforced.
    declared = set(CLASSIFIED_LITERALS)
    pinned = set(classified_pinned)
    expect("every pinned classification has a declared category and rationale",
           pinned <= declared, f"unexplained: {sorted(pinned - declared)[:6]}")
    expect("every declared category is pinned to contexts",
           declared <= pinned, f"unpinned: {sorted(declared - pinned)[:6]}")
    expect("every pinned category is one of the declared kinds",
           all(category in _CATEGORY_REASON
               for category, _, _ in classified_pinned.values()),
           f"unknown categories: "
           f"{sorted({c for c, _, _ in classified_pinned.values()} - set(_CATEGORY_REASON))}")
    disagreeing = sorted(
        f"{key}: category {classified_pinned[key][0]!r} vs "
        f"{CLASSIFIED_LITERALS[key][0]!r}"
        for key in pinned & declared
        if classified_pinned[key][0] != CLASSIFIED_LITERALS[key][0])
    expect("the pinned record and the category table agree",
           not disagreeing, "; ".join(disagreeing[:6]))

    # Every literal in every compiled source, bound to the file it is in and to
    # the number of times it may appear there.
    for relative in sources:
        key = str(relative)
        path = root / relative
        if not path.is_file():
            expect(f"audit source present: {relative}", False, "missing")
            continue

        # The whole-file pin runs for every audited source that is not
        # regenerated evidence, and it runs *first*.  It used to sit after the
        # `continue` below, so `paper/macros.tex` and the symbolic rate table
        # were never held to it: a reviewer redefined `\argmin` to render
        # "arg max", updated the closure entry to match, and the complete
        # shipped verifier still passed. Both files have specialized structural
        # checks -- macro declarations only, cells that parse as asymptotic
        # rates -- and neither of those notices a changed operator name.
        #
        # The pin is not self-authorizing: FILE_PINS lives in
        # tools/numeric_context_pins.py, whose digest is pinned in the contract
        # module and checked before any pin here is read.
        if key not in regenerated:
            text = auditable_text(path)
            want_file = file_pinned.get(key)
            expect(
                f"the audited text of this source is the pinned text: "
                f"{relative}",
                want_file is not None and file_digest(text) == want_file,
                f"digest {file_digest(text)}, pinned {want_file}. The "
                "per-occurrence units say which numbers moved; this says the "
                "file changed at all.")

        if key in regenerated or key in structural:
            continue                       # additionally checked below

        # Phrases: the count AND the ordered contexts of every occurrence.  A
        # count alone let a declared sentence move anywhere inside its file and
        # let the prose around a number be rewritten under it.
        mine = sorted((phrase for (f, phrase) in phrase_pinned if f == key),
                      key=len, reverse=True)
        phrase_problems = []
        for phrase in mine:
            want, want_units = phrase_pinned[(key, phrase)]
            spans = phrase_spans(text, phrase)
            if len(spans) != want:
                phrase_problems.append(
                    f"{phrase.splitlines()[0][:40]!r}: {len(spans)} "
                    f"occurrence(s), pinned {want}")
                continue
            got_units = occurrence_units(text, spans)
            if tuple(got_units) != tuple(tuple(u) for u in want_units):
                phrase_problems.append(
                    f"{phrase.splitlines()[0][:40]!r}: "
                    + first_unit_difference([tuple(u) for u in want_units],
                                            got_units))
        expect(
            f"every declared phrase occurs in its pinned semantic unit: "
            f"{relative}",
            not phrase_problems, "; ".join(phrase_problems[:6]))

        spans_by_literal = literal_spans(
            text, [normalize_prose(phrase) for phrase in mine])
        unclassified = sorted(
            literal for literal in spans_by_literal
            if (key, literal) not in classified_pinned)
        expect(
            f"every numeric literal is accounted for: {relative}",
            not unclassified,
            f"{len(unclassified)} unclassified literal(s) with no ledger entry "
            f"and no declared classification: {unclassified}",
        )
        wrong = []
        for (f, literal), (_, want, want_units) in classified_pinned.items():
            if f != key:
                continue
            spans = spans_by_literal.get(literal, [])
            if len(spans) != want:
                wrong.append(f"{literal!r}: {len(spans)} occurrence(s), "
                             f"pinned {want}")
                continue
            got_units = occurrence_units(text, spans)
            if tuple(got_units) != tuple(tuple(u) for u in want_units):
                wrong.append(f"{literal!r}: " + first_unit_difference(
                    [tuple(u) for u in want_units], got_units))
        expect(
            f"every classified literal occurs in its pinned semantic unit: "
            f"{relative}",
            not wrong, "; ".join(sorted(wrong)[:6]))

    # A phrase may only appear where it is declared.  Copying a ledger sentence
    # into another file is otherwise invisible: the old audit masked declared
    # phrases everywhere at once.
    strays: list[str] = []
    every_phrase = {phrase for _, phrase in phrases}
    for relative in sources:
        key = str(relative)
        path = root / relative
        if not path.is_file() or key in regenerated:
            continue
        text = auditable_text(path)
        for phrase in every_phrase:
            if (key, phrase) in phrases:
                continue                   # declared here, counted above
            if normalize_prose(phrase) in text:
                strays.append(
                    f"{key}: {phrase.splitlines()[0][:48]!r} occurs but is "
                    "declared only for other files")
    expect("no declared phrase appears in a file it is not declared for",
           not strays, "; ".join(sorted(set(strays))))

    # "Regenerated evidence" has to be earned: the artifact checker rebuilds
    # that exact file from the locked aggregate and requires byte identity, and
    # the sidecar has to describe the bytes on disk.
    for relative in sorted(GENERATED_ARTIFACT_SOURCES):
        path = root / relative
        if not path.is_file():
            expect(f"regenerated source present: {relative}", False, "missing")
            continue
        sidecar = Path(f"{path}.sha256")
        expect(
            f"regenerated-evidence status is backed by a digest: {relative}",
            sidecar.is_file()
            and sidecar.read_text(encoding="ascii").split()[0]
            == sha256_file(path),
            "the file claims to be regenerated evidence but its sidecar is "
            "missing or does not describe it",
        )

    # New cells have no self-authorizing sidecar exemption: exact regeneration
    # requires the reviewed generator and every pinned input, then byte identity
    # for all tables and their provenance record. Missing inputs fail closed.
    # Repository mode accepts only original retained bytes. Required package
    # mode additionally permits the exact anonymous copies fixed in reviewed
    # code, after validating the complete declaration and evidence set.
    try:
        followup_packaged = _validated_followup_packaged_sources(
            root, require_package=require_package)
        for source, expected_digest in FOLLOWUP_SOURCE_HASHES.items():
            path = root / source
            record = followup_packaged.get(str(source))
            matches = path.is_file() and (
                sha256_file(path) == expected_digest if record is None else
                record["original_sha256"] == expected_digest
                and sha256_file(path) == record["packaged_sha256"]
                and path.stat().st_size == record["packaged_bytes"])
            if not matches:
                raise LedgerError(f"missing or unreviewed generated-table input: {source}")
        generator = _load_reviewed_tool(root, FOLLOWUP_GENERATOR)
        expected_outputs = generator.build(root)
        expected_names = {Path(p).name for p in FOLLOWUP_GENERATED_SOURCES}
        expected_names.add("transport_followup_provenance.json")
        expect("follow-up generator produces exactly the reviewed artifact set",
               set(expected_outputs) == expected_names,
               f"got {sorted(expected_outputs)}")
        for name in sorted(expected_names):
            path = root / "paper/tables" / name
            expected = expected_outputs.get(name)
            expect(f"follow-up generated bytes agree: {name}",
                   isinstance(expected, str) and path.is_file()
                   and path.read_bytes() == expected.encode("utf-8"),
                   "compared with deterministic rendering from fixed source inputs")
    except Exception as exc:
        expect("follow-up tables can be regenerated from reviewed sources", False, repr(exc))

    # Charts have their own exact output inventory and reviewed generator. They
    # share only fixed evidence inputs with the tables; a new drawing does not
    # earn a blanket numerical exemption merely by living in figures/.
    try:
        generator = _load_reviewed_tool(root, EXPLANATORY_GENERATOR)
        expected_outputs = generator.build(root)
        expected_paths = {Path(p) for p in EXPLANATORY_GENERATED_SOURCES}
        expected_paths.add(Path(EXPLANATORY_PROVENANCE))
        expect("explanatory generator produces exactly the reviewed artifact set",
               set(expected_outputs) == expected_paths,
               f"got {sorted(str(p) for p in expected_outputs)}")
        for relative in sorted(expected_paths):
            path = root / relative
            expected = expected_outputs.get(relative)
            expect(f"explanatory generated bytes agree: {relative}",
                   isinstance(expected, str) and path.is_file()
                   and path.read_bytes() == expected.encode("utf-8"),
                   "compared with deterministic plotting data and rendering "
                   "from fixed source inputs")
    except Exception as exc:
        expect("explanatory charts can be regenerated from reviewed sources", False, repr(exc))

    # Charts have their own exact output inventory and reviewed generator. They
    # share only fixed evidence inputs with the tables; a new drawing does not
    # earn a blanket numerical exemption merely by living in figures/.
    try:
        generator = _load_reviewed_tool(root, TABLE_CHART_GENERATOR)
        expected_outputs = generator.build(root)
        expected_paths = {Path(p) for p in TABLE_CHART_GENERATED_SOURCES}
        expected_paths.add(Path(TABLE_CHART_PROVENANCE))
        expect("table-conversion generator produces exactly the reviewed artifact set",
               set(expected_outputs) == expected_paths,
               f"got {sorted(str(p) for p in expected_outputs)}")
        for relative in sorted(expected_paths):
            path = root / relative
            expected = expected_outputs.get(relative)
            expect(f"table-conversion generated bytes agree: {relative}",
                   isinstance(expected, str) and path.is_file()
                   and path.read_bytes() == expected.encode("utf-8"),
                   "compared with deterministic plotting data and rendering "
                   "from fixed source inputs")
    except Exception as exc:
        expect("table-conversion charts can be regenerated from reviewed sources", False, repr(exc))

    checks.extend(macro_file_checks(root))

    # Typeset generated artifacts are bound by byte-identical regeneration, not
    # by per-literal entries.  Anything else \input from tables/ or figures/
    # must be declared symbolic.
    known = {Path(name).name for name in ALL_GENERATED_SOURCES}
    known |= {Path(name).name for name in SYMBOLIC_TABLE_INPUTS}
    known |= {Path(name).name for name in ANALYTICAL_SCHEMATIC_SOURCES}
    undeclared: list[str] = []
    # Retained legacy files are not automatically submitted claims. Require
    # their specialized check only when the compiled closure includes them or
    # an active source references them. The reference check also catches a
    # missing table that the repository input walk could not open.
    symbolic_active = Path(SYMBOLIC_TABLE_SOURCE) in sources
    for relative in sources:
        path = root / relative
        if not path.is_file() or path.suffix != ".tex":
            continue
        body = visible_tex(path.read_text(encoding="utf-8"))
        for match in _INPUT.finditer(body):
            target = match.group(1) or match.group(2)
            target_path = Path(target)
            if not target_path.suffix:
                target_path = target_path.with_suffix(".tex")
            if (root / "paper" / target_path).resolve() == (root / SYMBOLIC_TABLE_SOURCE).resolve():
                symbolic_active = True
            if target.startswith(("tables/", "figures/")) \
                    and Path(target).name not in known:
                undeclared.append(f"{relative}: {target}")
    expect("every typeset table and figure is generated evidence or declared "
           "symbolic", not undeclared, f"undeclared: {sorted(undeclared)}")
    if symbolic_active:
        checks.extend(symbolic_table_checks(root))

    # The classification table must not rot: an entry naming a file that is no
    # longer in the closure is a stale exemption waiting to be reused.
    # Both README aliases are legitimate: the repository carries one name and a
    # packaged tree the other, so neither is stale just because this tree has
    # only one of them.
    in_closure = ({str(p) for p in sources}
                  | set(ALL_GENERATED_SOURCES)
                  | {MACRO_SOURCE, SYMBOLIC_TABLE_SOURCE}
                  | {str(SUPPLEMENT_README_REPO),
                     str(SUPPLEMENT_README_PACKAGED)})
    stale = sorted({path for path, _ in CLASSIFIED_LITERALS
                    if path not in in_closure}
                   | {path for path, _ in phrases if path not in in_closure})
    expect("no classification names a source outside the submitted closure",
           not stale, f"stale: {stale}")

    # The single arithmetic illustration in the theory appendices.
    path = root / COST_APPENDIX_TEX
    if path.is_file():
        text = auditable_text(path)
        missing = [literal for literal, _ in COST_ILLUSTRATION.values()
                   if normalize_prose(literal) not in text]
        candidates = COST_ILLUSTRATION["candidates"][1]
        iterations = COST_ILLUSTRATION["iterations"][1]
        buffer_size = COST_ILLUSTRATION["buffer"][1]
        expect(
            "the per-round cost illustration is arithmetically consistent",
            not missing
            and candidates * iterations * buffer_size
            == COST_ILLUSTRATION["recurrence_cvps"][1]
            and candidates * (iterations + 1) * buffer_size
            == COST_ILLUSTRATION["with_residual_cvps"][1],
            f"missing literals {missing}; "
            f"{candidates}*{iterations}*{buffer_size}="
            f"{candidates * iterations * buffer_size}, "
            f"{candidates}*{iterations + 1}*{buffer_size}="
            f"{candidates * (iterations + 1) * buffer_size}",
        )
    return checks


# --------------------------------------------------------------------------
# non-numeric invariants that the ledger still has to police
# --------------------------------------------------------------------------


def structural_checks(root: Path, aggregate, config) -> list[Check]:
    checks: list[Check] = []

    def expect(name, ok, detail=""):
        checks.append(Check(name, STATUS_PASS if ok else STATUS_FAIL, detail))

    expect("grid is complete", aggregate["full_grid_complete"] is True
           and aggregate["completed_run_count"] == aggregate["expected_run_count"],
           f"{aggregate['completed_run_count']}/{aggregate['expected_run_count']}")
    expect("all deterministic audits pass",
           aggregate["all_deterministic_audits_pass"] is True)
    expect("stochastic confidence failures were retained, not dropped",
           aggregate["stochastic_confidence_failures_retained"] is True)
    expect("profile is the full evaluation profile", aggregate["profile"] == "full")
    expect("smoke and tuning runs are excluded from the published profile",
           config["base"]["reporting"]["allow_smoke_or_tuning_in_paper"] is False)

    tuning = set(config["profiles"]["full"]["seed_sets"]["tuning"])
    evaluation = set(config["profiles"]["full"]["seed_sets"]["evaluation"])
    expect("tuning and evaluation seeds are disjoint", tuning.isdisjoint(evaluation),
           f"{len(tuning)} tuning, {len(evaluation)} evaluation")
    expect("the aggregate reports exactly the configured evaluation seeds",
           set(aggregate["evaluation_seeds"]) == evaluation)

    expect("horizons are executed as independent runs",
           config["base"]["execution"]["horizon_execution"] == "independent_runs")
    expect("contexts and potential noise are shared across methods",
           config["base"]["seed_derivation"]
           ["common_context_and_potential_noise_across_methods"] is True)

    # The deterministic cap 2T follows from |mu*| <= ||phi|| ||theta|| <= 1.
    expect("the deterministic pseudo-regret cap 2T is implied by the configuration",
           float(config["base"]["environment"]["feature_bound"]) == 1.0
           and float(config["base"]["teacher"]["theta_radius"]) == 1.0,
           "feature_bound = theta_radius = 1")

    components = ("statistical_bound_component", "historical_bound_component",
                  "path_inflation_component", "current_bias_cumulative")
    decomposition = aggregate["bound_decomposition"]
    bad_decomposition = [
        (r["target_D"], r["round"])
        for r in decomposition
        if not math.isclose(math.fsum(float(r[k]) for k in components),
                            float(r["sharp_theorem_rhs"]), rel_tol=1e-12, abs_tol=1e-10)
        or min(float(r[k]) for k in components) < -1e-10
    ]
    expect("recorded bound components are nonnegative and sum to the sharp RHS",
           bool(decomposition) and not bad_decomposition,
           f"inconsistent rows: {bad_decomposition[:5]}")
    expect("base component dominates the recorded mean bound decomposition",
           bool(decomposition) and all(
               float(r["statistical_bound_component"])
               >= max(float(r[k]) for k in components[1:])
               for r in decomposition))
    expect("each terminal mean base component exceeds the primary-horizon cap",
           all(float(r["statistical_bound_component"]) > 2 * PRIMARY_HORIZON
               for r in _terminal_decomposition(aggregate)))

    # Every comparison policy beats transport Hessian at the primary horizon.
    worse = []
    for target in aggregate["target_D"]:
        base = _policy(aggregate, "transport_hessian", PRIMARY_HORIZON, float(target))
        for method in ("transport_endpoint", "frozen_reference", "naive_current"):
            row = _policy(aggregate, method, PRIMARY_HORIZON, float(target))
            if not (row["cumulative_pseudo_regret"]["mean"]
                    < base["cumulative_pseudo_regret"]["mean"]):
                worse.append((method, target))
    expect("all three comparison policies have lower T=1000 sample-mean regret",
           not worse, f"exceptions: {worse}")

    # The supplement README names the declared package versions.  They are
    # classified as environment metadata rather than measurements, which is only
    # honest if they actually match the declared dependency set.
    # Only the two the README names: it discusses the scientific stack a
    # reviewer has to install, not the whole test-time dependency set.
    README_NAMED_PACKAGES = ("numpy", "scipy")
    requirements = root / "experiments/requirements.txt"
    readme = root / readme_sources(root)[0]
    if requirements.is_file() and readme.is_file():
        declared = dict(
            re.findall(r"^([A-Za-z0-9_.-]+)==([0-9][0-9A-Za-z.]*)\s*$",
                       requirements.read_text(encoding="utf-8"), re.M))
        prose = readme.read_text(encoding="utf-8")
        wanted = {name: declared[name] for name in README_NAMED_PACKAGES
                  if name in declared}
        wrong = [f"{name} {version} not stated"
                 for name, version in sorted(wanted.items())
                 if version not in prose]
        expect("the supplement README states the declared package versions",
               not wrong and len(wanted) == len(README_NAMED_PACKAGES),
               f"declared {wanted}; {wrong}")
        availability = root / AVAILABILITY_TEX
        if availability.is_file():
            expect("availability names the declared SciPy requirement",
                   declared.get("scipy") == "1.15.2"
                   and "SciPy 1.15.2" in availability.read_text(encoding="utf-8"))
    # The historical wheel inventory is retained in the repository, but is not
    # a required supplement input.  Its version is dependency provenance, not
    # an inferred runtime for the study; the availability statement remains
    # bound by exact semantic-unit and whole-file pins in both layouts.
    wheel_manifest = root / "third_party/wheels/SHA256SUMS"
    if wheel_manifest.is_file():
        expect("historical wheel inventory records the stated SciPy version",
               "35043677e4c5d0c556fbd355380bee8e1d349905243b011c9714c5dde7d00628  "
               "scipy-1.13.1-cp312-cp312-manylinux_x86_64.whl"
               in wheel_manifest.read_text(encoding="ascii").splitlines())

    # The conservatism statement in the abstract, as an order-of-magnitude claim.
    ratios = _medians(aggregate, "certificate_tightness", "D_Q_over_d_Th",
                      PRIMARY_HORIZON)
    lo, hi = math.floor(math.log10(min(ratios))), math.floor(math.log10(max(ratios)))
    expect("analytic-vs-endpoint conservatism spans five to six orders of magnitude",
           (lo, hi) == (5, 6), f"log10 range floor: {lo} to {hi}")

    return checks


def not_executed_checks() -> list[Check]:
    return [
        Check(
            "paired bootstrap intervals recomputed from per-seed values",
            STATUS_NOT_EXECUTED,
            "the bootstrap resamples per-seed totals, which live in the raw run "
            "tree; that tree was never committed, so the intervals are reported "
            "from the locked aggregate and are not recomputed here",
        ),
        Check(
            "raw per-run trajectory bytes verified against the aggregate inventory",
            STATUS_NOT_EXECUTED,
            "results/raw/ is not distributed; the aggregate's SHA-256 input "
            "inventory is structurally verified elsewhere but its bytes are absent",
        ),
    ]


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def _load_reviewed_tool(root: Path, relative: Path):
    """Load only the exact reviewed implementation; an input cannot pick code."""
    expected = FOLLOWUP_SOURCE_HASHES[relative]
    path = root / relative
    if not path.is_file() or sha256_file(path) != expected:
        raise LedgerError(f"unreviewed or missing tool: {relative}")
    spec = importlib.util.spec_from_file_location(f"_numeric_{relative.stem}", path)
    if spec is None or spec.loader is None:
        raise LedgerError(f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validated_followup_packaged_sources(
        root: Path, *, require_package: bool) -> dict[str, dict[str, Any]]:
    """Return anonymous source pins only in explicitly required package mode.

    A declaration cannot choose its own digests. The helper's code is bound by
    the separate shipped-tool contract, and it must validate every packaged
    evidence file and the exact declaration before its fixed mapping is used.
    """
    if not require_package:
        return {}
    if not contract.is_packaged_tree(root):
        raise LedgerError("anonymous follow-up sources require the package declaration")
    path = root / FOLLOWUP_PACKAGE_CONTRACT
    expected = contract.SHIPPED_TOOL_DIGESTS.get(str(FOLLOWUP_PACKAGE_CONTRACT))
    if not expected or not path.is_file() or path.is_symlink() or sha256_file(path) != expected:
        raise LedgerError(f"unreviewed or missing follow-up package contract: {FOLLOWUP_PACKAGE_CONTRACT}")
    spec = importlib.util.spec_from_file_location("_numeric_followup_package_contract", path)
    if spec is None or spec.loader is None:
        raise LedgerError(f"cannot load {FOLLOWUP_PACKAGE_CONTRACT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    failures = module.validate_packaged(root)
    if failures:
        raise LedgerError("invalid anonymous follow-up evidence: " + "; ".join(failures))
    return module.FOLLOWUP_CONTRACT


def followup_checks(root: Path, data: dict[Path, Any]) -> list[Check]:
    """Check new claims from the distinct retained follow-up population."""
    checks: list[Check] = []

    def verify(name: str, test: Callable[[], Any]) -> None:
        try:
            result = test()
            if not result:
                raise LedgerError("condition is false")
            checks.append(Check("follow-up: " + name, STATUS_PASS, str(result)))
        except Exception as exc:
            checks.append(Check("follow-up: " + name, STATUS_FAIL, repr(exc)))

    verify("terminal bootstrap reconstruction from preserved seed summaries",
           lambda: _load_reviewed_tool(root, FOLLOWUP_EXPORT_VERIFIER)
           .verify_export(root / FOLLOWUP_ROOT))

    required = {FOLLOWUP_CONFIG, FOLLOWUP_AGGREGATE, FOLLOWUP_SEEDS,
                FOLLOWUP_ROUNDS, FOLLOWUP_DIAGNOSTICS, FOLLOWUP_DECOMPOSITION,
                FOLLOWUP_ANALYSIS}
    if not required <= data.keys():
        checks.append(Check("follow-up: source set available", STATUS_FAIL,
                            str(sorted(str(p) for p in required - data.keys()))))
        return checks
    config, aggregate, seeds, rounds, diagnostics, components, analysis = (
        data[p] for p in (FOLLOWUP_CONFIG, FOLLOWUP_AGGREGATE, FOLLOWUP_SEEDS,
                         FOLLOWUP_ROUNDS, FOLLOWUP_DIAGNOSTICS,
                         FOLLOWUP_DECOMPOSITION, FOLLOWUP_ANALYSIS))
    methods = set(config["methods"])
    widths = set(config["followup"]["prespecified_width_W"])
    verify("four policies, three conditions, fifty evaluation seeds",
           lambda: len(methods) == 4 and len(widths) == 3
           and len(config["seed_sets"]["evaluation"]) == 50
           and aggregate["completed_run_count"] == len(seeds) == 600)
    verify("development, tuning and evaluation seed sets are disjoint",
           lambda: all(not (set(config["seed_sets"][a]) & set(config["seed_sets"][b]))
                       for a, b in (("development", "tuning"),
                                    ("development", "evaluation"),
                                    ("tuning", "evaluation"))))
    verify("all recorded confidence, optimism and deterministic diagnostics pass",
           lambda: all(row["simultaneous_reference_confidence"] is True
                       and row["simultaneous_method_optimism"] is True
                       and row["deterministic_audit_passed"] is True for row in seeds))
    comparisons = [row for row in aggregate["policy_outcomes"]
                   if row["method"] != "transport_hessian"]
    verify("all nine pointwise comparator-minus-Hessian intervals exclude zero below",
           lambda: len(comparisons) == 9 and all(
               row["paired_difference_from_transport_hessian"]["bootstrap_mean_interval"]["ci_high"] < 0
               for row in comparisons))
    verify("primary terminal decomposition adds to its sharp RHS and is path dominated",
           lambda: len(components) == 3 and all(
               math.isclose(sum(row[k] for k in ("statistical_bound_component",
                            "historical_bound_component", "path_inflation_component",
                            "current_bias_cumulative")), row["sharp_theorem_rhs"], rel_tol=1e-12)
               and row["path_inflation_component"] > row["sharp_theorem_rhs"] / 2
               for row in components))
    def own_bound_nonvacuity():
        counts = Counter()
        for row in seeds:
            method = row["method"]
            if method not in {"transport_hessian", "frozen_reference"}:
                continue
            cap = 2 * row["horizon"] * min(1.0, math.sqrt(row["W"]))
            rhs = row["sharp_theorem_rhs"] if method == "transport_hessian" else sum(
                row[key] for key in ("statistical_bound_component",
                                     "historical_bound_component", "current_bias_cumulative"))
            if not math.isfinite(rhs) or rhs <= cap:
                return False
            counts[method] += 1
        return counts == {"transport_hessian": 150, "frozen_reference": 150}
    verify("all primary and frozen-policy bounds exceed each own-trajectory cap",
           own_bound_nonvacuity)
    verify("round-threshold denominators and summaries agree in all policy cells",
           lambda: len(rounds) == 600 and all(
               len(members := [r for r in rounds if r["W"] == d["W"]
                               and r["method"] == d["method"]]) == 50
               and sum(r["round_count"] for r in members) == d["total_rounds"] == 50000
               and all(math.isclose(sum(r["endpoint_at_least_threshold_counts"][threshold]
                                        for r in members) / d["total_rounds"], fraction,
                                    rel_tol=1e-12, abs_tol=1e-12)
                       for threshold, fraction in d["endpoint_round_at_least_threshold_fraction"].items())
               for d in diagnostics))
    verify("exploratory same-history grid is complete and diagonals reproduce actual behavior",
           lambda: analysis["experiments_rerun"] is False
           and analysis["raw_rounds"] == 600000
           and len(analysis["groups"]) == 12
           and {(g["W"], g["behavior_method"]) for g in analysis["groups"]}
           == {(w, m) for w in widths for m in methods}
           and all(math.isclose(g["same_history_recommendations"]["mean_one_step_pseudo_regret"][g["behavior_method"]]
                                * config["reporting"]["primary_horizon"],
                                g["actual_behavior_mean_terminal_regret"], rel_tol=1e-12)
                   for g in analysis["groups"]))
    def relative_consistency():
        relative = data[RELATIVE_ANALYSIS]
        members = data[RELATIVE_SEEDS]
        if not (relative["complete_600_trajectory_audit"] is True
                and relative["new_adaptive_experiments"] is False
                and relative["optimizer_replayed_on_logged_actions_rewards"] is True
                and relative["floating_point_checks_are_verified_certificates"] is False
                and relative["trajectories"] == len(members) == 600
                and relative["rounds"] == sum(row["rounds"] for row in members) == 600000
                and relative["source_config_digest"] == aggregate["config_digest"]):
            return False
        expected = {(w, m, seed) for w in widths for m in methods
                    for seed in config["seed_sets"]["evaluation"]}
        if {(r["W"], r["behavior_method"], r["seed"]) for r in members} != expected:
            return False
        for key, maximum in relative["maximum_residual_or_excess_over_original_tolerance"].items():
            measured = max(r["maximum_residual_or_excess_over_original_tolerance"][key] for r in members)
            if not (math.isfinite(maximum) and maximum == measured and maximum < .005):
                return False
        for group in relative["groups"]:
            w, behavior = group["W"], group["behavior_method"]
            old = _followup_group(analysis, w, behavior)
            counts = group["diagnostic_counts"]["transport_hessian"]
            for name in ("width_argmax_first_matches", "strict_width_dominance_sufficient"):
                if counts[name] != old["hessian_recommendation_diagnostics"]["counts"][name]:
                    return False
            for method in methods:
                if not math.isclose(group["same_history_mean_one_step_regret"][method]["mean"],
                                    old["same_history_recommendations"]["mean_one_step_pseudo_regret"][method],
                                    rel_tol=1e-12, abs_tol=1e-12):
                    return False
        timing_rows = [t for row in members for t in row["fixed_state_kernel_timings"]]
        return len(timing_rows) == 36 and all(
            kernel["count"] == 5 for row in timing_rows
            for kernel in row["kernels_seconds_per_call"].values())
    verify("relative replay identities, old-score agreement, residual bounds and timing denominators",
           relative_consistency)
    checks.append(Check("follow-up: raw trajectories and upstream floating-point operations",
                        STATUS_NOT_EXECUTED,
                        "compact summaries and exploratory outputs are bound to retained bytes; "
                        "this ledger does not read the external raw archive or rerun policy "
                        "trajectories, matrix solves, exponentials or decimal score calculations"))
    return checks


def run(root: Path, *, check_manuscript: bool = True,
        require_package: bool | None = None) -> tuple[list[Check], list[Entry]]:
    checks: list[Check] = []
    ledger = build_ledger(root)

    required = contract.package_required(require_package)
    packaged = contract.is_packaged_tree(root)
    if required and not packaged:
        # A supplement whose declaration has been removed must not be graded
        # with repository semantics: that is exactly how restored original,
        # author-linked evidence would verify clean.
        name, ok, detail = contract.missing_declaration_result(root)
        checks.append(Check(f"anonymous package: {name}", STATUS_FAIL, detail))
        return checks, ledger
    if packaged:
        # Validate the whole anonymous-package contract from pinned constants
        # before trusting any packaged byte.  The shipped declaration has to
        # agree with the code; it never gets to define what is acceptable.
        for name, ok, detail in contract.check(root, require_package=required):
            checks.append(Check(
                f"anonymous package: {name}",
                STATUS_ANONYMIZED if ok else STATUS_FAIL,
                detail,
            ))

    try:
        followup_packaged = _validated_followup_packaged_sources(
            root, require_package=required)
    except Exception as exc:
        checks.append(Check("follow-up anonymous source contract", STATUS_FAIL, repr(exc)))
        return checks, ledger
    if required:
        checks.append(Check("follow-up anonymous source contract", STATUS_ANONYMIZED,
                            "complete evidence set and declaration match fixed reviewed code"))

    sources = {AGGREGATE: AGGREGATE_SHA256, CONFIG: CONFIG_SHA256,
               **FOLLOWUP_SOURCE_HASHES}
    for relative, expected in sources.items():
        path = root / relative
        if not path.is_file():
            checks.append(Check(f"source present: {relative}", STATUS_FAIL, "missing"))
            continue
        actual = sha256_file(path)
        pinned = contract.CONTRACT.get(str(relative)) if packaged else None
        if relative in FOLLOWUP_SOURCE_HASHES:
            pinned = followup_packaged.get(str(relative), pinned)
        if pinned is None:
            # Original repository evidence: the digest must be exactly the one
            # this tool was written against.  Strict, and unchanged.
            checks.append(Check(
                f"source hash: {relative}",
                STATUS_PASS if actual == expected else STATUS_FAIL,
                f"expected {expected}, got {actual}",
            ))
        else:
            # Packaged copy.  Accept only the one deterministic sanitized digest
            # pinned in code, and only when the contract also ties it back to
            # exactly the original evidence this tool expects.
            ok = (
                actual == pinned["packaged_sha256"]
                and path.stat().st_size == pinned["packaged_bytes"]
                and pinned["original_sha256"] == expected
            )
            checks.append(Check(
                f"source hash: {relative} (anonymized packaging copy, "
                f"NOT original evidence bytes)",
                STATUS_ANONYMIZED if ok else STATUS_FAIL,
                f"packaged {actual} ({path.stat().st_size} bytes); pinned "
                f"{pinned['packaged_sha256']} ({pinned['packaged_bytes']} bytes); "
                f"pinned original {pinned['original_sha256']}; this tool expects "
                f"original {expected}",
            ))
        sidecar = Path(str(path) + ".sha256")
        if sidecar.is_file():
            recorded = sidecar.read_text(encoding="ascii")
            if pinned is None:
                ok = recorded.split()[0] == actual
                detail = f"sidecar {recorded.split()[0]}"
            else:
                # Pinned text, so a recomputed-but-consistent sidecar over
                # mutated bytes is rejected rather than accepted.
                expected_sidecar = f"{pinned['packaged_sha256']}  {path.name}\n"
                ok = recorded == expected_sidecar
                detail = f"sidecar {recorded!r}, pinned {expected_sidecar!r}"
            checks.append(Check(
                f"sidecar agrees: {relative}.sha256"
                + (" (pinned packaged text)" if pinned else ""),
                STATUS_PASS if ok else STATUS_FAIL,
                detail,
            ))

    aggregate = json.loads((root / AGGREGATE).read_text(encoding="utf-8"))
    config = json.loads((root / CONFIG).read_text(encoding="utf-8"))

    followup_data: dict[Path, Any] = {}
    for relative in FOLLOWUP_SOURCE_HASHES:
        if relative.suffix not in {".json", ".jsonl"}:
            continue
        try:
            raw = (root / relative).read_text(encoding="utf-8")
            followup_data[relative] = ([json.loads(line) for line in raw.splitlines()]
                                      if relative.suffix == ".jsonl" else json.loads(raw))
        except (OSError, ValueError) as exc:
            checks.append(Check(f"follow-up source parses: {relative}", STATUS_FAIL, repr(exc)))

    manuscript_cache: dict[Path, str] = {}

    for entry in ledger:
        label = f"{entry.manuscript.name}: {entry.literal.splitlines()[0][:52]}"
        try:
            entry.unrounded = float(entry.compute(followup_data[entry.source] if entry.source in FOLLOWUP_SOURCE_HASHES else aggregate, config))
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            checks.append(Check(f"recompute {label}", STATUS_FAIL, repr(exc)))
            continue
        want = parse_display(entry.display)
        tol = tolerance_of(entry.display)
        ok = abs(entry.unrounded - want) <= tol
        checks.append(Check(
            f"value {label}",
            STATUS_PASS if ok else STATUS_FAIL,
            f"recomputed {entry.unrounded!r} vs displayed {entry.display} "
            f"(tolerance {tol!r})",
        ))

        if not check_manuscript:
            continue
        path = root / entry.manuscript
        if path not in manuscript_cache:
            if not path.is_file():
                checks.append(Check(f"manuscript present: {entry.manuscript}",
                                    STATUS_FAIL, "missing"))
                manuscript_cache[path] = ""
            else:
                # Visible bytes only.  Searching the raw file let a commented-out
                # copy of the old value satisfy this check while the rendered
                # number said something else.
                raw = path.read_text(encoding="utf-8")
                if path.suffix == ".tex":
                    raw = visible_tex(raw)
                manuscript_cache[path] = normalize_prose(raw)
        text = manuscript_cache[path]
        needle = normalize_prose(entry.literal)
        checks.append(Check(
            f"literal {label}",
            STATUS_PASS if needle and needle in text else STATUS_FAIL,
            f"expected literal {needle!r} in {entry.manuscript}",
        ))

    checks.extend(structural_checks(root, aggregate, config))
    checks.extend(followup_checks(root, followup_data))
    if check_manuscript:
        checks.extend(literal_coverage_checks(root, ledger,
                                              require_package=required))
    checks.extend(not_executed_checks())
    return checks, ledger


PIN_MODULE_HEADER = '''#!/usr/bin/env python3
r"""Pinned semantic units for every declared numeric occurrence in the submission.

GENERATED DATA.  Produced by `tools/verify_tmlr_submission_numbers.py
--regenerate-pins` from the frozen manuscript sources, and committed so that the
audit compares against a fixed, reviewed record rather than against whatever the
sources currently say.  Do not hand-edit: regenerate, and read the diff.

What a pin binds
----------------
Each key is `(repository path, literal-or-phrase)`.  Each value carries the
exact number of occurrences allowed in that file and, for each occurrence in
document order, the **complete normalized semantic unit** it sits in together
with its offset inside that unit.

A unit is the whole thing a reader would call one statement: a paragraph, a
table row or cell, a list item, a caption, a heading, or an equation
environment.  Boundaries come from the source itself -- a blank line, `\\\\`, an
unescaped `&`, `\\item`, a sectioning command, `\\begin`/`\\end`, `\\caption`, a
booktabs rule -- not from a character count.

Why not a fixed radius
----------------------
The previous record pinned forty characters on each side of the number.  That
cannot see a meaning-changing edit past its own edge: "the median is 126.7" and
"the median is 126.7, for the discarded pilot run" are identical inside the
window and say different things.  A unit has no edge to hide behind.  Every way
of getting it wrong -- moved, reworded, duplicated, missing, one more, or a
qualification added anywhere in the same sentence -- is a mismatch.

`FILE_PINS` adds a whole-file binding on top: a digest over the entire
normalized auditable text of each audited source, which catches a
meaning-changing edit in a part of the file that holds no pinned number.  It is
an addition, not a replacement -- a file digest says only "something changed",
and the units say what.

This record is not self-authorizing.  The module ships with the supplement
because the shipped ledger reads it, so its own SHA-256 is pinned in
`tools/anonymous_package_contract.py` and recorded again in the internal
`release_manifest.json`; the ledger checks that binding before it consults a
single pin.  Editing a manuscript source and regenerating its pin inside an
unpacked supplement therefore does not authorize itself.

`tools/verify_tmlr_submission_numbers.py --print-contexts` prints every unit in
full, with each category's rationale.

This module carries no repository, host or author information.

Layout
------
`UNITS` holds every distinct unit once; the pin tables cite them by index
through `_u`.  The same paragraph is the unit of a dozen different numbers, so
writing each one out per pin cost 1.6 MB of duplicated prose and made the
record harder to read, not easier.
"""

from __future__ import annotations

#: Every distinct semantic unit, once, sorted.
'''


def _format_pin_table(name: str, annotation: str,
                      rows: Sequence[tuple[tuple[str, str], object]],
                      index_of: dict[str, int]) -> str:
    """One generated table, grouped by file, citing units by index.

    The same paragraph is the unit of a dozen different numbers, so writing it
    out once and citing it by index turns 1.6 MB of duplicated prose into 187 kB
    -- and makes the record easier to read, because each unit appears once
    instead of a dozen times.
    """

    out = [f"{name}: {annotation} = {{"]
    last_file = None
    for (relative, key), value in rows:
        if relative != last_file:
            out.append(f"    # {relative}")
            last_file = relative
        if len(value) == 2:
            count, units = value
            head = f"{count!r}, "
        else:
            category, count, units = value
            head = f"{category!r}, {count!r}, "
        cited = ", ".join(f"({index_of[unit]}, {offset})" for unit, offset in units)
        out.append(f"    ({relative!r}, {key!r}):")
        out.append(f"        ({head}_u({cited})),")
    out.append("}")
    return "\n".join(out) + "\n"


def regenerated_pin_module(root: Path) -> str:
    """The exact text of `tools/numeric_context_pins.py` for these sources.

    Authoring aid only.  Running this against the same sources the audit reads
    always agrees with itself, which is precisely why its output is not an
    approval: what makes a pin authority is that a human read the diff and
    committed it.
    """

    phrase_rows: list[tuple[tuple[str, str], object]] = []
    literal_rows: list[tuple[tuple[str, str], object]] = []
    file_rows: list[tuple[str, str]] = []

    declared_phrases: dict[str, list[str]] = {}
    for relative, phrase in pins.PHRASE_PINS:
        declared_phrases.setdefault(relative, []).append(phrase)
    declared_literals: dict[str, list[tuple[str, str]]] = {}
    for (relative, literal), value in pins.CLASSIFIED_PINS.items():
        declared_literals.setdefault(relative, []).append((literal, value[0]))

    # Every audited source gets a whole-file pin, including the ones that state
    # no number at all: `paper/availability.tex` has nothing to classify and can
    # still be rewritten to say something false.
    covered = set(declared_phrases) | set(declared_literals)
    covered |= {str(p) for p in audited_sources(root)
                if (root / p).is_file()
                and str(p) not in ALL_GENERATED_SOURCES}

    for relative in sorted(covered):
        path = root / relative
        if not path.is_file():
            raise LedgerError(f"cannot regenerate pins: {relative} is missing")
        text = auditable_text(path)
        mine = sorted(declared_phrases.get(relative, []), key=len, reverse=True)
        for phrase in sorted(declared_phrases.get(relative, [])):
            spans = phrase_spans(text, phrase)
            phrase_rows.append(((relative, phrase),
                                (len(spans), occurrence_units(text, spans))))
        spans_by_literal = literal_spans(
            text, [normalize_prose(phrase) for phrase in mine])
        for literal, category in sorted(declared_literals.get(relative, [])):
            spans = spans_by_literal.get(literal, [])
            literal_rows.append(((relative, literal),
                                 (category, len(spans),
                                  occurrence_units(text, spans))))
        file_rows.append((relative, file_digest(text)))

    every_unit: list[str] = []
    seen: set[str] = set()
    for _key, value in phrase_rows + literal_rows:
        for unit, _offset in value[-1]:
            if unit not in seen:
                seen.add(unit)
                every_unit.append(unit)
    every_unit.sort()
    index_of = {unit: index for index, unit in enumerate(every_unit)}

    body = [PIN_MODULE_HEADER]
    body.append("UNITS: tuple[str, ...] = (\n")
    for unit in every_unit:
        body.append(f"    {unit!r},\n")
    body.append(")\n\n\n")
    body.append("def _u(*cited: tuple[int, int]) -> tuple[tuple[str, int], ...]:\n"
                '    """Resolve `(unit index, offset)` pairs against UNITS."""\n\n'
                "    return tuple((UNITS[index], offset) for index, offset in cited)\n"
                "\n\n")
    body.append("#: (path, phrase) -> (occurrences, ((unit, offset-in-unit), ...))\n")
    body.append(_format_pin_table(
        "PHRASE_PINS",
        "dict[tuple[str, str], tuple[int, tuple[tuple[str, int], ...]]]",
        phrase_rows, index_of))
    body.append("\n#: (path, literal) -> (category, occurrences, "
                "((unit, offset-in-unit), ...))\n")
    body.append(_format_pin_table(
        "CLASSIFIED_PINS",
        "dict[tuple[str, str], tuple[str, int, tuple[tuple[str, int], ...]]]",
        literal_rows, index_of))
    body.append("\n#: path -> SHA-256 of the whole normalized auditable text\n")
    body.append("FILE_PINS: dict[str, str] = {\n")
    for relative, digest in file_rows:
        body.append(f"    {relative!r}:\n        {digest!r},\n")
    body.append("}\n")
    return "".join(body)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--no-manuscript", action="store_true",
                        help="skip the literal-occurrence checks (for an "
                             "evidence-only supplement without the .tex sources)")
    parser.add_argument("--ledger", type=Path, default=None,
                        help="write the full ledger as JSON")
    parser.add_argument(
        "--require-package", action="store_true", default=None,
        help="fail if the tree is not an anonymous package; also implied by "
             f"{contract.ENV_REQUIRE_PACKAGE}=1")
    parser.add_argument(
        "--print-contexts", action="store_true",
        help="print the complete semantic unit behind every pinned occurrence, "
             "so the pinned record can be read and not just trusted")
    parser.add_argument(
        "--regenerate-pins", action="store_true",
        help="print tools/numeric_context_pins.py for the sources in --root. "
             "An authoring aid: verification never calls this, and the pins it "
             "prints are not authority until they are committed and reviewed.")
    args = parser.parse_args(argv)

    root = args.root.resolve()

    if args.print_contexts:
        for (relative, phrase), (count, units) in sorted(
                phrase_pins(root).items()):
            path = root / relative
            if not path.is_file():
                continue
            text = auditable_text(path)
            print(f"\n=== phrase {relative} :: {phrase!r}  "
                  f"({count} occurrence(s), {units_digest(units)[:16]})")
            for unit, offset in occurrence_units(text,
                                                 phrase_spans(text, phrase)):
                print(f"    @{offset} {unit}")
        for relative in sorted({p for p, _ in classified_pins(root)}):
            path = root / relative
            if not path.is_file():
                continue
            text = auditable_text(path)
            mine = [normalize_prose(p) for (f, p) in phrase_pins(root)
                    if f == relative]
            spans = literal_spans(text, sorted(mine, key=len, reverse=True))
            for (f, literal), (category, count, units) in sorted(
                    classified_pins(root).items()):
                if f != relative or literal not in spans:
                    continue
                print(f"\n=== {category} {relative} :: {literal!r}  "
                      f"({count} occurrence(s), {units_digest(units)[:16]})")
                print(f"    rationale: {_CATEGORY_REASON[category]}")
                for unit, offset in occurrence_units(text, spans[literal]):
                    print(f"    @{offset} {unit}")
        for relative, digest in sorted(file_pins(root).items()):
            print(f"\n=== whole-file binding {relative}  {digest}")
        return 0

    if args.regenerate_pins:
        print(regenerated_pin_module(root), end="")
        return 0
    checks, ledger = run(root, check_manuscript=not args.no_manuscript,
                         require_package=args.require_package)

    for check in checks:
        print(f"{check.status:<13} {check.name}")
        if check.status in (STATUS_FAIL, STATUS_NOT_EXECUTED, STATUS_ANONYMIZED) \
                and check.detail:
            print(f"{'':<13}   -> {check.detail}")

    failures = [c for c in checks if c.status == STATUS_FAIL]
    counts: dict[str, int] = {}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1
    print()
    print("summary: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))

    if args.ledger:
        args.ledger.write_text(json.dumps({
            "schema_version": 1,
            "aggregate_sha256": AGGREGATE_SHA256,
            "config_sha256": CONFIG_SHA256,
            "additional_source_sha256": {str(path): digest for path, digest in FOLLOWUP_SOURCE_HASHES.items()},
            "entries": [
                {
                    "manuscript": str(x.manuscript),
                    "literal": x.literal,
                    "display": x.display,
                    "source": str(x.source),
                    "selector": x.selector,
                    "units": x.units,
                    "aggregation": x.aggregation,
                    "population": x.population,
                    "unrounded": x.unrounded,
                }
                for x in ledger
            ],
            "checks": [
                {"name": c.name, "status": c.status, "detail": c.detail}
                for c in checks
            ],
            "ok": not failures,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
