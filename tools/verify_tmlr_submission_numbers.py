#!/usr/bin/env python3
"""Executable numerical-provenance ledger for the TMLR submission candidate.

Every number the submission states about the controlled transport-instantiation
study is listed here once, together with

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

It does not recompute anything that needs the raw per-run trajectories.  Those
files were never committed; checks that would need them are reported as
NOT EXECUTED with the reason, never as passes.

Runs from the repository root or from an unpacked supplement root with the same
layout.  Exit status is nonzero if any check fails.
"""

from __future__ import annotations

import argparse
import hashlib
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
COST_APPENDIX_TEX = Path("paper/appendix_deferred.tex")

AGGREGATE_SHA256 = "0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02"
CONFIG_SHA256 = "d6f6c0de47651a7e6a291f63ba609654afd5cff6cc13d11722d9fae587e7abdd"

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
    add(EXPERIMENT_TEX, "there are five\nactions", "5", C,
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
    add(ABSTRACT_TEX, "all\n600 transport-Hessian runs", "600", A,
        "len(horizons) * len(target_D) * len(evaluation_seeds)", "runs", "count",
        "transport-Hessian arm of the grid",
        lambda a, c: float(len(a["horizons"]) * len(a["target_D"])
                           * len(a["evaluation_seeds"])))
    add(ABSTRACT_TEX, "locked 29-parameter scaled-tanh audit", "29", C,
        "base.environment.feature_dimension", "parameters", "declared constant",
        "configuration",
        lambda a, c: float(c["base"]["environment"]["feature_dimension"]))
    add(CONCLUSION_TEX, "All 600 transport-Hessian trajectories", "600", A,
        "len(horizons) * len(target_D) * len(evaluation_seeds)", "runs", "count",
        "transport-Hessian arm of the grid",
        lambda a, c: float(len(a["horizons"]) * len(a["target_D"])
                           * len(a["evaluation_seeds"])))
    add(INTRO_TEX, "29-parameter", "29", C,
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


_classify("paper/appendix_cg.tex", "math-constant",
          {"0": 3, "1": 24, "2": 12})
_classify("paper/appendix_cg.tex", "interval-endpoint", {"0,1": 1})
_classify("paper/appendix_deferred.tex", "math-constant",
          {"0": 48, "1": 520, "2": 476, "3": 25, "4": 34, "5": 1, "6": 3,
           "8": 8})
_classify("paper/appendix_deferred.tex", "interval-endpoint", {"0,1": 13})
_classify("paper/appendix_deferred.tex", "citation-locator", {"6.1.1": 2})
_classify("paper/appendix_deferred.tex", "cited-scale", {"10^8": 1})
_classify("paper/appendix_deferred.tex", "illustration-input",
          {"10": 1, "25": 1, "256": 1})
_classify("paper/appendix_deferred.tex", "derived-arithmetic",
          {"64{,}000": 1, "66{,}560": 1})
_classify("paper/appendix_expfam.tex", "math-constant", {"1": 6, "2": 7})
_classify("paper/appendix_ggn.tex", "math-constant", {"1": 5, "2": 5})
_classify("paper/appendix_onesided_proof.tex", "math-constant",
          {"1": 16, "2": 24, "3": 1, "4": 1, "5": 1, "6": 1})
_classify("paper/appendix_protocol.tex", "math-constant",
          {"0": 17, "1": 83, "2": 81, "3": 2, "4": 1})
_classify("paper/appendix_protocol.tex", "interval-endpoint", {"0,1": 1})
_classify("paper/appendix_rates.tex", "math-constant",
          {"0": 4, "1": 59, "2": 52, "3": 5, "4": 2})
_classify("paper/appendix_rates.tex", "interval-endpoint", {"0,1": 2})
_classify("paper/appendix_twosided.tex", "math-constant",
          {"0": 2, "1": 20, "2": 31, "3": 1, "4": 1})
_classify("paper/body_related.tex", "math-constant", {"1": 3, "2": 2})
_classify("paper/body_related.tex", "cited-scale", {"10^8": 1})
_classify("paper/legacy_dynamic.tex", "math-constant",
          {"0": 12, "1": 97, "2": 79, "4": 1, "16": 2})
_classify("paper/legacy_dynamic.tex", "interval-endpoint", {"0,1": 1})
_classify("paper/notation.tex", "math-constant", {"1": 2, "2": 3})
_classify("paper/transport_proofs.tex", "math-constant",
          {"0": 8, "1": 63, "2": 73, "4": 2})
_classify("paper/transport_theory.tex", "math-constant",
          {"0": 19, "1": 79, "2": 80, "3": 2, "4": 4})
_classify("paper/transport_theory.tex", "interval-endpoint", {"0,1": 5})
for _readme in (str(SUPPLEMENT_README_REPO), str(SUPPLEMENT_README_PACKAGED)):
    _classify(_readme, "document-structure",
              {"0": 1, "1": 2, "2": 2, "3": 2, "4": 1})
    _classify(_readme, "environment-version",
              {"3.12": 1, "2.2.3": 1, "1.15.2": 1})

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
    ("paper/body_conclusion.tex", "$D_t<1$"): 1,
    ("paper/body_conclusion.tex", "All 600 transport-Hessian trajectories"): 1,
    ("paper/body_intro.tex", "29-parameter"): 1,
    ("paper/transport_experiment.tex",
     "$1.20$--$1.22$ times the endpoint distance"): 1,
    ("paper/transport_experiment.tex", "$1.88\\times10^6$"): 1,
    ("paper/transport_experiment.tex", "$126.7$--$135.0$ at $T=1000$"): 1,
    ("paper/transport_experiment.tex", "$2.24\\times10^6$"): 1,
    ("paper/transport_experiment.tex", "$2.51\\times10^5$"): 1,
    ("paper/transport_experiment.tex", "$3{,}989$--$12{,}607$"): 1,
    ("paper/transport_experiment.tex", "$8.74\\times10^{-6}$"): 1,
    ("paper/transport_experiment.tex", "$T=1000$"): 7,
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
    ("paper/transport_experiment.tex", "there are five\nactions"): 1,
    ("paper/transport_experiment.tex", "to $0.384$"): 1,
    ("paper/transport_experiment.tex", "to $1.18$"): 1,
    ("paper/transport_experiment.tex", "to $94.0$"): 1,
    ("paper/transport_experiment.tex", "versus caps of $500$--$2{,}000$"): 1,
    ("paper/transport_experiment_appendix.tex", "$T=1000$"): 2,
    ("paper/transport_experiment_appendix.tex", "$e^{\\bar D_t^Q/2}$"): 1,
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
    ("submissions/tmlr_2026/main.tex", "all\n600 transport-Hessian runs"): 1,
    ("submissions/tmlr_2026/main.tex",
     "locked 29-parameter scaled-tanh audit"): 1,
    ("submissions/tmlr_2026/supplement_README.md", "2,400 trajectories"): 1,
    ("submissions/tmlr_2026/supplement_README.md", "21 artifacts"): 1,
    ("submissions/tmlr_2026/supplement_README.md",
     "all 21 published tables, figures and CSVs"): 1,
}


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
    'LICENSE-lppl-1-2',
    'LICENSE-lppl-1-3c',
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
    | (VENDORED_PACKAGE_NAMES - VENDORED_LICENSE_NAMES)))


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
    extra = sorted(compiled_shipped - recorded)
    expect("every shipped manuscript source is a recorded compiled input",
           not extra, f"shipped but not recorded as compiled: {extra}")

    loose = sorted(
        name for name in data_shipped - recorded
        if name not in CLOSURE_UNSIDECARRED_SOURCES
        and not (root / f"{name}.sha256").is_file())
    expect("every shipped figure-data file is recorded or sidecarred",
           not loose, f"bound to nothing: {loose}")

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
    regenerated = set(GENERATED_ARTIFACT_SOURCES)

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
    for relative in sorted(regenerated):
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

    checks.extend(macro_file_checks(root))
    checks.extend(symbolic_table_checks(root))

    # Typeset generated artifacts are bound by byte-identical regeneration, not
    # by per-literal entries.  Anything else \input from tables/ or figures/
    # must be declared symbolic.
    known = {Path(name).name for name in GENERATED_ARTIFACT_SOURCES}
    known |= {Path(name).name for name in SYMBOLIC_TABLE_INPUTS}
    undeclared: list[str] = []
    for relative in sources:
        path = root / relative
        if not path.is_file() or path.suffix != ".tex":
            continue
        body = visible_tex(path.read_text(encoding="utf-8"))
        for match in _INPUT.finditer(body):
            target = match.group(1) or match.group(2)
            if target.startswith(("tables/", "figures/")) \
                    and Path(target).name not in known:
                undeclared.append(f"{relative}: {target}")
    expect("every typeset table and figure is generated evidence or declared "
           "symbolic", not undeclared, f"undeclared: {sorted(undeclared)}")

    # The classification table must not rot: an entry naming a file that is no
    # longer in the closure is a stale exemption waiting to be reused.
    # Both README aliases are legitimate: the repository carries one name and a
    # packaged tree the other, so neither is stale just because this tree has
    # only one of them.
    in_closure = ({str(p) for p in sources}
                  | set(GENERATED_ARTIFACT_SOURCES)
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

    sources = {AGGREGATE: AGGREGATE_SHA256, CONFIG: CONFIG_SHA256}
    for relative, expected in sources.items():
        path = root / relative
        if not path.is_file():
            checks.append(Check(f"source present: {relative}", STATUS_FAIL, "missing"))
            continue
        actual = sha256_file(path)
        pinned = contract.CONTRACT.get(str(relative)) if packaged else None
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
                ok = recorded == contract.sidecar_text(str(relative))
                detail = (f"sidecar {recorded!r}, pinned "
                          f"{contract.sidecar_text(str(relative))!r}")
            checks.append(Check(
                f"sidecar agrees: {relative}.sha256"
                + (" (pinned packaged text)" if pinned else ""),
                STATUS_PASS if ok else STATUS_FAIL,
                detail,
            ))

    aggregate = json.loads((root / AGGREGATE).read_text(encoding="utf-8"))
    config = json.loads((root / CONFIG).read_text(encoding="utf-8"))

    manuscript_cache: dict[Path, str] = {}

    for entry in ledger:
        label = f"{entry.manuscript.name}: {entry.literal.splitlines()[0][:52]}"
        try:
            entry.unrounded = float(entry.compute(aggregate, config))
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
                and str(p) not in GENERATED_ARTIFACT_SOURCES}

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
