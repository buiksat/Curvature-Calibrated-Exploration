#!/usr/bin/env python3
"""Verify the committed transport-instantiation evidence from a bare checkout.

This is the *detached* verifier.  It is written for the situation a GitHub-only
reviewer is actually in: `results/raw/` is not committed, so the repository's
full provenance validator
(`experiments.artifact_utils.validate_aggregate_provenance_sidecar`) cannot run
at all -- it requires every declared input file to exist on disk.

The distinction this tool refuses to blur:

* verifying that a provenance inventory is internally consistent and its
  canonical digest reproduces  -- that is a STRUCTURAL PASS;
* verifying that the bytes the inventory points at are what it says  -- that is
  full provenance verification, and it is NOT possible here.

`STRUCTURAL PASS` is never reported as `PASS`.  Where a recomputation needs
per-seed values that the committed aggregate does not carry, the check is
reported `NOT EXECUTED` with the reason, and no synthetic data is invented.

The existing full validator is untouched.  Exit status is nonzero on any FAIL.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from export_transport_github_review_bundle import (  # noqa: E402
    AGGREGATE_PATH,
    AGGREGATE_PROVENANCE_PATH,
    EXPECTED_CANDIDATE_CELLS,
    EXPECTED_CANDIDATE_COUNT,
    EXPECTED_EVALUATION_SEEDS,
    EXPECTED_HORIZONS,
    EXPECTED_METHODS,
    EXPECTED_RUN_COUNT,
    EXPECTED_TARGETS,
    EXPECTED_TUNING_SEEDS,
    GENERATED_ARTIFACT_PATHS,
    KNOWN_STUDY_SOURCE_DIVERGENCES,
    LOCKED_AGGREGATE_INPUT_SET_SHA256,
    LOCKED_AGGREGATE_SHA256,
    LOCKED_COVERAGE_CI,
    LOCKED_PDF_SHA256,
    LOCKED_SELECTION_SHA256,
    PDF_PATH,
    RATIO_DENOMINATOR_TOLERANCE,
    SELECTION_FLAT_PATH,
    SELECTION_PATH,
    SELECTION_PROVENANCE_PATH,
    ReviewBundleError,
    canonical_json,
    clopper_pearson,
    describe,
    export_bundle,
    input_set_sha256,
    load_json_strict,
    pdf_page_count,
    sha256_file,
)

LOCKED_ARTIFACT_HASHES: Mapping[str, str] = {
    "results/derived/transport_instantiation/selection.json": LOCKED_SELECTION_SHA256,
    "results/derived/transport_instantiation_selection.json": LOCKED_SELECTION_SHA256,
    "results/derived/transport_instantiation/full_aggregate.json": LOCKED_AGGREGATE_SHA256,
    "paper/main.pdf": LOCKED_PDF_SHA256,
    "paper/tables/transport_instantiation_validity.tex": (
        "0ec0451563890ea9373a0710bbcbc33b2db28a14e405a798e6033062fab7634a"
    ),
    "paper/tables/transport_instantiation_performance.tex": (
        "5b2ea6000bfc123d9f52b38f37ddbb5aafb7eeb55139c8876a29d33879ee13ad"
    ),
    "paper/tables/transport_instantiation_tightness.tex": (
        "940106f9f33decab26a9033277c5bc354c6c2e8d09dc629b5b3b6954deb45311"
    ),
    "paper/figures/transport_instantiation_regret.tex": (
        "239ae5e923801ed1a2f9eafa75ba6a642e8bd2bb14ec2875c8d080f22ea5ec98"
    ),
    "paper/figures/transport_instantiation_tightness.tex": (
        "828590d0cab45e2621677474acec4ae1216857191d54e816d4f4b24a2fd276c2"
    ),
    "paper/figures/transport_instantiation_bound.tex": (
        "9c6465521c216fa96fc6536044491684312108c510357f38cc92c0325319af3c"
    ),
}

STATUS_PASS = "PASS"
STATUS_RECOMPUTED = "PASS_RECOMPUTED"
STATUS_STRUCTURAL = "STRUCTURAL_PASS"
STATUS_NOT_EXECUTED = "NOT_EXECUTED"
STATUS_KNOWN_DIVERGENCE = "KNOWN_DIVERGENCE"
STATUS_FAIL = "FAIL"

STATUS_LABELS = {
    STATUS_PASS: "PASS: directly verified committed evidence",
    STATUS_RECOMPUTED: "PASS: independently recomputed statistic",
    STATUS_STRUCTURAL: "STRUCTURAL PASS: provenance structure verified, raw bytes absent",
    STATUS_NOT_EXECUTED: "NOT EXECUTED: requires raw data or experiment execution",
    STATUS_KNOWN_DIVERGENCE: "KNOWN DIVERGENCE: pinned, explained, not silently accepted",
    STATUS_FAIL: "FAIL",
}


class Report:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def add(
        self,
        section: str,
        name: str,
        status: str,
        detail: str = "",
        **extra: Any,
    ) -> None:
        record = {"section": section, "check": name, "status": status, "detail": detail}
        record.update(extra)
        self.checks.append(record)

    def expect(
        self, section: str, name: str, condition: bool, detail: str = "", *, status: str
    ) -> bool:
        self.add(section, name, status if condition else STATUS_FAIL, detail)
        return condition

    @property
    def failures(self) -> list[dict[str, Any]]:
        return [c for c in self.checks if c["status"] == STATUS_FAIL]

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for check in self.checks:
            out[check["status"]] = out.get(check["status"], 0) + 1
        return out


# --------------------------------------------------------------------------
# 1. locked file hashes
# --------------------------------------------------------------------------


def check_locked_hashes(report: Report, root: Path) -> None:
    for relative, expected in sorted(LOCKED_ARTIFACT_HASHES.items()):
        path = root / relative
        if not path.is_file():
            report.add("locked", relative, STATUS_FAIL, "file is missing")
            continue
        actual = sha256_file(path)
        report.expect(
            "locked",
            relative,
            actual == expected,
            f"expected {expected}, got {actual}",
            status=STATUS_PASS,
        )

    sidecars = [
        "results/derived/transport_instantiation/selection.json.sha256",
        "results/derived/transport_instantiation/full_aggregate.json.sha256",
        "results/derived/transport_instantiation_selection.json.sha256",
        "paper/main.pdf.sha256",
    ]
    for relative in sidecars:
        path = root / relative
        artifact = path.with_name(path.name[: -len(".sha256")])
        if not path.is_file():
            report.add("locked", relative, STATUS_FAIL, "sidecar is missing")
            continue
        fields = path.read_text(encoding="ascii").strip().split()
        ok = (
            len(fields) == 2
            and fields[1] == artifact.name
            and fields[0] == sha256_file(artifact)
        )
        report.expect(
            "locked",
            relative,
            ok,
            "two-field sidecar must name and match its artifact",
            status=STATUS_PASS,
        )


# --------------------------------------------------------------------------
# 2. selection structural integrity
# --------------------------------------------------------------------------


def check_selection(report: Report, root: Path, selection: Mapping[str, Any]) -> None:
    section = "selection"

    report.expect(
        section,
        "selection parses with no duplicate keys or non-finite literals",
        True,
        status=STATUS_PASS,
    )

    sidecar = load_json_strict(root / SELECTION_PROVENANCE_PATH)
    report.expect(
        section,
        "sidecar artifact_sha256 matches the selection",
        sidecar.get("artifact_sha256") == LOCKED_SELECTION_SHA256,
        status=STATUS_PASS,
    )
    sidecar_inputs = [
        {"path": i["path"], "sha256": i["sha256"]} for i in sidecar.get("inputs", [])
    ]
    embedded = [
        {"path": i["path"], "sha256": i["sha256"]} for i in selection["inputs"]
    ]
    report.expect(
        section,
        "sidecar inventory equals the selection's embedded inventory",
        sidecar_inputs == embedded,
        f"{len(sidecar_inputs)} sidecar vs {len(embedded)} embedded records",
        status=STATUS_STRUCTURAL,
    )
    recomputed = input_set_sha256(embedded)
    report.expect(
        section,
        "canonical input inventory digest recomputes",
        recomputed == selection["input_set_sha256"] == sidecar.get("input_set_sha256"),
        f"recomputed {recomputed}",
        status=STATUS_RECOMPUTED,
    )

    missing = sum(1 for i in embedded if not (root / i["path"]).is_file())
    report.add(
        section,
        "tuning input file bytes",
        STATUS_NOT_EXECUTED,
        f"{missing} of {len(embedded)} declared inputs are absent from this checkout "
        "(results/raw/ is not committed); their content is not verified",
    )

    # study-source inventory against the current checkout
    diverged: list[str] = []
    for item in selection["study_source_inputs"]:
        path = root / item["path"]
        if not path.is_file():
            report.add(
                section, f"study source {item['path']}", STATUS_FAIL, "file is missing"
            )
            continue
        actual = sha256_file(path)
        if actual == item["sha256"]:
            report.add(
                section, f"study source {item['path']}", STATUS_PASS, "matches snapshot"
            )
            continue
        pinned = KNOWN_STUDY_SOURCE_DIVERGENCES.get(item["path"])
        if (
            pinned is not None
            and pinned["selection_inventory_sha256"] == item["sha256"]
            and pinned["expected_head_sha256"] == actual
        ):
            diverged.append(item["path"])
            report.add(
                section,
                f"study source {item['path']}",
                STATUS_KNOWN_DIVERGENCE,
                f"snapshot {item['sha256']} vs HEAD {actual}; "
                f"diverged in {pinned['diverged_in_commit']}: {pinned['reason']}",
            )
        else:
            report.add(
                section,
                f"study source {item['path']}",
                STATUS_FAIL,
                f"unpinned divergence: snapshot {item['sha256']} vs {actual}",
            )
    report.expect(
        section,
        "study-source divergences are exactly the pinned set",
        sorted(diverged) == sorted(KNOWN_STUDY_SOURCE_DIVERGENCES),
        f"observed {sorted(diverged)}",
        status=STATUS_PASS,
    )
    report.expect(
        section,
        "study-source inventory digest recomputes",
        input_set_sha256(selection["study_source_inputs"])
        == selection["study_source_input_set_sha256"],
        status=STATUS_RECOMPUTED,
    )

    tuning = tuple(selection["tuning_seeds"])
    evaluation = tuple(selection["evaluation_seeds"])
    report.expect(
        section,
        "tuning and evaluation seeds are disjoint",
        set(tuning).isdisjoint(evaluation) and selection["seed_sets_disjoint"] is True,
        status=STATUS_RECOMPUTED,
    )
    report.expect(
        section,
        "seed sets are the frozen split",
        tuning == EXPECTED_TUNING_SEEDS and evaluation == EXPECTED_EVALUATION_SEEDS,
        status=STATUS_PASS,
    )

    leaked = [
        item["path"]
        for item in selection["inputs"]
        if "/evaluation/" in item["path"]
        or any(f"seed-{s}/" in item["path"] for s in evaluation)
    ]
    report.expect(
        section,
        "no evaluation path or seed appears in tuning selection inputs",
        not leaked,
        f"{len(leaked)} leaked paths",
        status=STATUS_RECOMPUTED,
    )

    candidates = selection["candidates"]
    grid = sorted(
        (float(c["learning_rate"]), int(c["steps_per_round"])) for c in candidates
    )
    expected_grid = sorted(
        (lr, steps) for lr in (3e-05, 0.0001, 0.0003) for steps in (1, 5, 20)
    )
    report.expect(
        section,
        "candidate grid is exactly the 3x3 preregistered grid",
        len(candidates) == EXPECTED_CANDIDATE_COUNT
        and selection["candidate_count"] == EXPECTED_CANDIDATE_COUNT
        and grid == expected_grid,
        status=STATUS_PASS,
    )
    report.expect(
        section,
        "every candidate has exactly 120 unique cells",
        all(
            len(c["runs"]) == EXPECTED_CANDIDATE_CELLS
            and len(
                {(r["seed"], r["horizon"], r["target_D"]) for r in c["runs"]}
            )
            == EXPECTED_CANDIDATE_CELLS
            for c in candidates
        ),
        status=STATUS_RECOMPUTED,
    )

    means: dict[str, float] = {}
    exact = True
    for candidate in candidates:
        values = [float(r["mean_all_action_prediction_mse"]) for r in candidate["runs"]]
        mean = math.fsum(values) / len(values)
        means[candidate["candidate_id"]] = mean
        if mean != float(candidate["aggregate_mean_all_action_prediction_mse"]):
            exact = False
    report.expect(
        section,
        "candidate aggregate means recompute exactly",
        exact,
        status=STATUS_RECOMPUTED,
    )

    eligible = [c for c in candidates if c["eligible"]]
    winner = min(
        eligible,
        key=lambda c: (
            means[c["candidate_id"]],
            int(c["steps_per_round"]),
            float(c["learning_rate"]),
        ),
    )
    selected = selection["selected"]
    report.expect(
        section,
        "selection winner replays exactly",
        winner["candidate_id"] == selected["candidate_id"]
        and float(selected["learning_rate"]) == 0.0003
        and int(selected["steps_per_round"]) == 20
        and means[winner["candidate_id"]]
        == float(selected["aggregate_mean_all_action_prediction_mse"])
        == 0.00666914978044266,
        f"{winner['candidate_id']} lr={selected['learning_rate']} "
        f"steps={selected['steps_per_round']} "
        f"mse={selected['aggregate_mean_all_action_prediction_mse']!r}",
        status=STATUS_RECOMPUTED,
    )
    report.expect(
        section,
        "tie rule is the recorded deterministic rule",
        list(selected["tie_break"]) == ["fewer_steps_per_round", "smaller_learning_rate"],
        status=STATUS_PASS,
    )
    ordered = sorted(means.values())
    report.expect(
        section,
        "winner is strictly best so the tie rule is not load-bearing here",
        len(ordered) > 1 and ordered[0] < ordered[1],
        f"best {ordered[0]!r} runner-up {ordered[1]!r}",
        status=STATUS_RECOMPUTED,
    )


# --------------------------------------------------------------------------
# 3. aggregate structural integrity
# --------------------------------------------------------------------------


def check_aggregate(report: Report, root: Path, aggregate: Mapping[str, Any]) -> None:
    section = "aggregate"

    sidecar = load_json_strict(root / AGGREGATE_PROVENANCE_PATH)
    report.expect(
        section,
        "sidecar artifact_sha256 matches the aggregate",
        sidecar.get("artifact_sha256") == LOCKED_AGGREGATE_SHA256,
        status=STATUS_PASS,
    )
    sidecar_inputs = [
        {"path": i["path"], "sha256": i["sha256"]} for i in sidecar.get("inputs", [])
    ]
    embedded = [{"path": i["path"], "sha256": i["sha256"]} for i in aggregate["inputs"]]
    report.expect(
        section,
        "sidecar inventory equals the aggregate inventory",
        sidecar_inputs == embedded,
        f"{len(sidecar_inputs)} vs {len(embedded)} records",
        status=STATUS_STRUCTURAL,
    )
    recomputed = input_set_sha256(embedded)
    report.expect(
        section,
        "input-set digest recomputes to the locked value",
        recomputed
        == LOCKED_AGGREGATE_INPUT_SET_SHA256
        == aggregate["input_set_sha256"]
        == sidecar.get("input_set_sha256"),
        f"recomputed {recomputed}",
        status=STATUS_RECOMPUTED,
    )
    absent = sum(1 for i in embedded if not (root / i["path"]).is_file())
    report.add(
        section,
        "evaluation input file bytes",
        STATUS_NOT_EXECUTED,
        f"{absent} of {len(embedded)} declared inputs are absent; content not verified",
    )
    report.add(
        section,
        "full provenance validation",
        STATUS_NOT_EXECUTED,
        "experiments.artifact_utils.validate_aggregate_provenance_sidecar requires "
        "every declared input to exist on disk; results/raw/ is not committed",
    )

    report.expect(
        section,
        "config digest, revision, methods, seeds, horizons and targets are exact",
        aggregate["config_digest"]
        == "cf774ff572a356afb113e645b086ca4eb6912a99c069d313f6c02794c6ad6f9f"
        and aggregate["git_revision"] == "0cd6264c1f8b8751728f3c4a198207e8289aed74"
        and tuple(aggregate["methods"]) == EXPECTED_METHODS
        and tuple(aggregate["horizons"]) == EXPECTED_HORIZONS
        and tuple(aggregate["target_D"]) == EXPECTED_TARGETS
        and tuple(aggregate["evaluation_seeds"]) == EXPECTED_EVALUATION_SEEDS,
        status=STATUS_PASS,
    )
    report.expect(
        section,
        "expected and completed trajectory counts are 2400",
        aggregate["expected_run_count"]
        == aggregate["completed_run_count"]
        == EXPECTED_RUN_COUNT,
        status=STATUS_PASS,
    )
    report.expect(
        section,
        "publication flags are exact",
        aggregate["full_grid_complete"] is True
        and aggregate["publication_ready"] is True
        and aggregate["all_deterministic_audits_pass"] is True
        and aggregate["stochastic_confidence_failures_retained"] is True,
        status=STATUS_PASS,
    )
    report.expect(
        section,
        "aggregate is bound to the locked selection hash",
        aggregate["selection_sha256"] == LOCKED_SELECTION_SHA256,
        status=STATUS_PASS,
    )

    expected_sections = {
        "validity": (12, {"horizon", "target_D"}),
        "certificate_tightness": (12, {"horizon", "target_D"}),
        "bound_nonvacuity": (12, {"horizon", "target_D"}),
        "environment_diagnostics": (12, {"horizon", "target_D"}),
        "policy_outcomes": (16, {"horizon", "target_D", "method"}),
    }
    for name, (count, key_fields) in expected_sections.items():
        rows = aggregate[name]
        keys = [tuple(r[f] for f in sorted(key_fields)) for r in rows]
        report.expect(
            section,
            f"{name} has {count} cells with unique keys",
            len(rows) == count and len(set(keys)) == count,
            f"{len(rows)} rows, {len(set(keys))} unique keys",
            status=STATUS_PASS,
        )

    non_finite: list[str] = []

    def walk(node: Any, where: str) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                walk(value, f"{where}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{where}[{index}]")
        elif isinstance(node, float) and not math.isfinite(node):
            non_finite.append(where)

    walk(aggregate, "aggregate")
    report.expect(
        section,
        "every numeric value in the aggregate is finite",
        not non_finite,
        f"{len(non_finite)} non-finite values",
        status=STATUS_RECOMPUTED,
    )

    zero_regret = sum(int(r["zero_regret_run_count"]) for r in aggregate["bound_nonvacuity"])
    positive = sum(
        int(r["positive_regret_run_count"]) for r in aggregate["bound_nonvacuity"]
    )
    consistent = all(
        int(r["zero_regret_run_count"]) + int(r["positive_regret_run_count"])
        == int(r["run_count"])
        for r in aggregate["bound_nonvacuity"]
    )
    report.expect(
        section,
        "zero-regret handling is internally consistent",
        consistent and zero_regret == 0 and positive == 600,
        f"{zero_regret} zero-regret and {positive} positive-regret runs",
        status=STATUS_RECOMPUTED,
    )


# --------------------------------------------------------------------------
# 4. statistics
# --------------------------------------------------------------------------


def check_statistics(report: Report, aggregate: Mapping[str, Any]) -> None:
    section = "statistics"

    mismatched: list[str] = []
    cells = 0
    for record in aggregate["validity"]:
        for field in ("transport_optimism_coverage", "reference_confidence_coverage"):
            cell = record[field]
            cells += 1
            recomputed = clopper_pearson(cell["successes"], cell["n"], cell["level"])
            if (
                abs(recomputed["ci_low"] - float(cell["ci_low"])) > 1e-15
                or recomputed["ci_high"] != float(cell["ci_high"])
            ):
                mismatched.append(f"{field}@T{record['horizon']}D{record['target_D']}")
    report.expect(
        section,
        f"exact Clopper-Pearson recomputes in all {cells} validity cells",
        not mismatched,
        f"{len(mismatched)} mismatches; standard-library incomplete beta, not SciPy",
        status=STATUS_RECOMPUTED,
    )
    report.expect(
        section,
        "50/50 coverage yields the locked interval",
        [clopper_pearson(50, 50, 0.95)["ci_low"], clopper_pearson(50, 50, 0.95)["ci_high"]]
        == list(LOCKED_COVERAGE_CI),
        f"recomputed {clopper_pearson(50, 50, 0.95)['ci_low']!r}",
        status=STATUS_RECOMPUTED,
    )
    report.expect(
        section,
        "every primary coverage cell is 50 of 50",
        all(
            record[field]["successes"] == 50 and record[field]["n"] == 50
            for record in aggregate["validity"]
            for field in ("transport_optimism_coverage", "reference_confidence_coverage")
        )
        and all(
            r["simultaneous_optimism_coverage"]["successes"] == 50
            and r["simultaneous_optimism_coverage"]["n"] == 50
            for r in aggregate["policy_outcomes"]
        ),
        status=STATUS_RECOMPUTED,
    )

    # path statistics recomputed from path_points
    tolerance = RATIO_DENOMINATOR_TOLERANCE
    per_cell: dict[tuple[int, float], dict[str, Any]] = {}
    for point in aggregate["path_points"]:
        key = (int(point["horizon"]), float(point["target_D"]))
        cell = per_cell.setdefault(
            key,
            {
                "D_Q_over_d_Th": [],
                "D_Q_over_D_path_quad": [],
                "D_path_quad_over_d_Th": [],
                "d_Th_at_or_below_ratio_tolerance_count": 0,
                "D_path_quad_at_or_below_ratio_tolerance_count": 0,
                "d_Th_at_or_below_tolerance_with_path_count": 0,
            },
        )
        d_q = float(point["D_Q"])
        d_th = float(point["d_Th"])
        raw = point["D_path_quad"]
        d_path = None if raw is None else float(raw)
        if d_th > tolerance:
            cell["D_Q_over_d_Th"].append(d_q / d_th)
        else:
            cell["d_Th_at_or_below_ratio_tolerance_count"] += 1
        if d_path is not None:
            if d_path > tolerance:
                cell["D_Q_over_D_path_quad"].append(d_q / d_path)
            else:
                cell["D_path_quad_at_or_below_ratio_tolerance_count"] += 1
            if d_th > tolerance:
                cell["D_path_quad_over_d_Th"].append(d_path / d_th)
            else:
                cell["d_Th_at_or_below_tolerance_with_path_count"] += 1

    bad: list[str] = []
    for record in aggregate["certificate_tightness"]:
        key = (int(record["horizon"]), float(record["target_D"]))
        cell = per_cell[key]
        for field in ("D_Q_over_d_Th", "D_Q_over_D_path_quad", "D_path_quad_over_d_Th"):
            values = cell[field]
            published = record.get(field)
            if not values:
                if published is not None:
                    bad.append(f"{field}@{key} published but not recomputable")
                continue
            stats = describe(values)
            if published is None:
                bad.append(f"{field}@{key} recomputed but absent upstream")
                continue
            if stats["n"] != published["n"]:
                bad.append(f"{field}@{key} n {stats['n']} vs {published['n']}")
            if stats["median"] != float(published["median"]):
                bad.append(f"{field}@{key} median differs")
        for field in (
            "d_Th_at_or_below_ratio_tolerance_count",
            "D_path_quad_at_or_below_ratio_tolerance_count",
            "d_Th_at_or_below_tolerance_with_path_count",
        ):
            if cell[field] != record.get(field):
                bad.append(f"{field}@{key} {cell[field]} vs {record.get(field)}")
    report.expect(
        section,
        "certificate-tightness medians and zero-denominator counts recompute from path_points",
        not bad,
        "; ".join(bad[:6]) if bad else "12 cells, exact agreement",
        status=STATUS_RECOMPUTED,
    )

    ratios_ok = True
    for record in aggregate["bound_nonvacuity"]:
        summary = record["sharp_rhs_over_positive_regret"]
        if summary["n"] != record["positive_regret_run_count"]:
            ratios_ok = False
        if summary["minimum"] <= 0.0:
            ratios_ok = False
    report.expect(
        section,
        "bound-nonvacuity ratios use only positive denominators",
        ratios_ok,
        status=STATUS_RECOMPUTED,
    )

    report.add(
        section,
        "deterministic paired bootstrap intervals",
        STATUS_NOT_EXECUTED,
        "the committed aggregate stores per-cell descriptive summaries only; the "
        "per-seed values the bootstrap resamples live in results/raw/, which is not "
        "committed. The algorithm, level, resample count and child seeds are recorded, "
        "but no per-seed data is synthesized to fake the recomputation",
    )


# --------------------------------------------------------------------------
# 5. generated artifacts
# --------------------------------------------------------------------------


def check_generated_artifacts(report: Report, root: Path) -> None:
    section = "artifacts"
    try:
        sys.path.insert(0, str(root))
        import experiments.make_transport_instantiation_artifacts as maker
        from experiments.aggregate_transport_instantiation import METHODS
    except Exception as error:  # pragma: no cover - environment dependent
        report.add(
            section,
            "regenerate table and figure bytes from the committed aggregate",
            STATUS_NOT_EXECUTED,
            f"the repository rendering stack is unavailable here ({error.__class__.__name__}: {error})",
        )
        return

    aggregate_path = root / AGGREGATE_PATH
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    aggregate_sha = sha256_file(aggregate_path)
    source_comment = f"% Source aggregate SHA-256: {aggregate_sha}\n"
    figures = root / "paper/figures"
    tables = root / "paper/tables"
    targets = sorted(float(v) for v in aggregate["target_D"])
    token = maker._target_file_token

    regret_panel = {t: f"transport_instantiation_regret_D-{token(t)}.csv" for t in targets}
    path_panel = {t: f"transport_instantiation_tightness_D-{token(t)}.csv" for t in targets}
    bound_panel = {t: f"transport_instantiation_bound_D-{token(t)}.csv" for t in targets}

    regret_rows = sorted(
        maker._downsample_curve_records(aggregate["regret_curves"]),
        key=lambda i: (
            float(i["target_D"]),
            METHODS.index(str(i["method"])),
            int(i["round"]),
        ),
    )
    bound_rows = sorted(
        maker._downsample_curve_records(aggregate["bound_decomposition"]),
        key=lambda i: (float(i["target_D"]), int(i["round"])),
    )
    regret_csv_rows = [
        {**r, "method_index": METHODS.index(str(r["method"])), "aggregate_sha256": aggregate_sha}
        for r in regret_rows
    ]
    path_csv_rows = [
        {**r, "aggregate_sha256": aggregate_sha} for r in maker._path_plot_records(aggregate)
    ]
    bound_csv_rows = [{**r, "aggregate_sha256": aggregate_sha} for r in bound_rows]

    regret_fields = (
        "target_D", "horizon", "method", "method_index", "round", "mean",
        "ci_low", "ci_high", "aggregate_sha256",
    )
    path_fields = (
        "target_D", "series_code", "x", "y", "count", "marker_size", "aggregate_sha256",
    )
    bound_fields = (
        "target_D", "horizon", "round", "statistical_bound_component",
        "historical_bound_component", "path_inflation_component",
        "current_bias_cumulative", "cumulative_pseudo_regret", "sharp_theorem_rhs",
        "aggregate_sha256",
    )

    expected: dict[Path, str] = {
        tables / "transport_instantiation_validity.tex": source_comment
        + maker.make_validity_table(aggregate),
        tables / "transport_instantiation_performance.tex": source_comment
        + maker.make_performance_table(aggregate),
        tables / "transport_instantiation_tightness.tex": source_comment
        + maker.make_tightness_table(aggregate),
        figures / "transport_instantiation_regret.csv": maker._csv_text(
            regret_fields, regret_csv_rows
        ),
        figures / "transport_instantiation_tightness.csv": maker._csv_text(
            path_fields, path_csv_rows
        ),
        figures / "transport_instantiation_bound.csv": maker._csv_text(
            bound_fields, bound_csv_rows
        ),
        figures / "transport_instantiation_regret.tex": source_comment
        + maker.make_regret_figure_tex(aggregate, regret_panel),
        figures / "transport_instantiation_tightness.tex": source_comment
        + maker.make_path_figure_tex(aggregate, path_panel),
        figures / "transport_instantiation_bound.tex": source_comment
        + maker.make_bound_figure_tex(aggregate, bound_panel),
    }
    for target in targets:
        expected[figures / regret_panel[target]] = maker._csv_text(
            regret_fields,
            [r for r in regret_csv_rows if float(r["target_D"]) == target],
        )
        expected[figures / path_panel[target]] = maker._csv_text(
            path_fields, [r for r in path_csv_rows if float(r["target_D"]) == target]
        )
        expected[figures / bound_panel[target]] = maker._csv_text(
            bound_fields, [r for r in bound_csv_rows if float(r["target_D"]) == target]
        )

    import hashlib

    covered = {str(p.relative_to(root)) for p in expected}
    missing_from_check = set(GENERATED_ARTIFACT_PATHS) - covered
    report.expect(
        section,
        "every declared generated artifact is regenerated",
        not missing_from_check,
        f"unchecked: {sorted(missing_from_check)}",
        status=STATUS_PASS,
    )

    for path, text in sorted(expected.items()):
        relative = str(path.relative_to(root))
        want = hashlib.sha256(text.encode("ascii")).hexdigest()
        got = sha256_file(path)
        sidecar = Path(str(path) + ".sha256")
        provenance = Path(str(path) + ".provenance.json")
        sidecar_value = (
            sidecar.read_text(encoding="ascii").split()[0] if sidecar.is_file() else ""
        )
        bound_ok = False
        if provenance.is_file():
            record = json.loads(provenance.read_text(encoding="utf-8"))
            bound_ok = (
                record.get("artifact_sha256") == got
                and any(
                    i.get("sha256") == aggregate_sha
                    and i.get("path") == str(AGGREGATE_PATH)
                    for i in record.get("inputs", [])
                )
            )
        report.expect(
            section,
            relative,
            want == got == sidecar_value and bound_ok,
            f"regen={want[:16]} disk={got[:16]} sidecar={sidecar_value[:16]} "
            f"bound_to_aggregate={bound_ok}",
            status=STATUS_RECOMPUTED,
        )


# --------------------------------------------------------------------------
# 6. manuscript claims
# --------------------------------------------------------------------------

MANUSCRIPT_INVARIANTS: Mapping[str, Sequence[tuple[str, str]]] = {
    "paper/transport_experiment.tex": (
        ("2400 policy", "all 2400 policy trajectories accepted"),
        ("50 evaluation seeds", "50 evaluation seeds"),
        ("$[92.9\\%,100\\%]$", "displayed exact Clopper-Pearson interval"),
        ("$3\\times10^{-4}$", "selected learning rate"),
        ("20 full-batch steps", "selected steps per round"),
        (
            "no deterministic algebra or certificate-check failure",
            "zero deterministic failures",
        ),
        (
            "no bound violation on the joint confidence event",
            "zero on-event violations",
        ),
        ("No run has zero regret", "no zero-regret runs"),
        (
            "diagnostics, not verified numerical certificates",
            "float64 diagnostics are not verified certificates",
        ),
        (
            "does not provide a scalable policy certificate",
            "endpoint is not scalable",
        ),
        (
            "only a diagnostic oracle",
            "endpoint is a dense diagnostic oracle",
        ),
        ("intentionally uncertified", "naive current is uncertified"),
        (
            "naive score's observed optimism does not make it theoretically valid",
            "naive current remained optimistic but is not valid",
        ),
        (
            "do not show a causal or uniform advantage for full curvature",
            "no uniform curvature advantage",
        ),
        ("The cumulative guarantee is nevertheless vacuous here", "empirical vacuity"),
        ("is not network width", "no generic network-width claim"),
        (
            "lower descriptive regret in every condition",
            "endpoint, frozen and naive descriptive regret direction",
        ),
    ),
    "paper/transport_experiment_appendix.tex": (
        ("50 evaluation seeds", "figures use only evaluation seeds"),
        ("Smoke and tuning results are absent", "smoke and tuning excluded"),
        (
            "dense float64 diagnostics, not verified certificates",
            "float64 diagnostics are not verified certificates",
        ),
        ("$10^{-12}$ ratio tolerance", "preregistered ratio tolerance"),
    ),
    "TRANSPORT_INSTANTIATION_COMPLETION_REPORT.md": (
        ("2,400/2,400 trajectories", "full grid complete"),
        ("Deterministic audit failures: 0", "zero deterministic failures"),
        ("On-event theorem-bound violations: 0", "zero on-event violations"),
        (
            "2545c368d6b97393f5c1e5bb61d4696f7fed6b8ae988ce42c9d7bc7ccab717e1",
            "PDF hash",
        ),
        ("63 pages, 933,908 bytes", "PDF page count and size"),
    ),
}


def _normalize_prose(text: str) -> str:
    """Collapse whitespace runs so TeX line wrapping cannot break a match.

    Only whitespace is normalized.  Every other character, including every
    digit and every LaTeX control sequence, must still match exactly, so this
    is not a fuzzy matcher.
    """

    return " ".join(text.split())


def check_manuscript(report: Report, root: Path) -> None:
    section = "manuscript"
    for relative, invariants in sorted(MANUSCRIPT_INVARIANTS.items()):
        path = root / relative
        if not path.is_file():
            report.add(section, relative, STATUS_FAIL, "file is missing")
            continue
        text = _normalize_prose(path.read_text(encoding="utf-8"))
        for needle, description in invariants:
            report.expect(
                section,
                f"{relative}: {description}",
                _normalize_prose(needle) in text,
                f"expected literal {needle!r}",
                status=STATUS_PASS,
            )


# --------------------------------------------------------------------------
# 7. review bundle
# --------------------------------------------------------------------------


def check_review_bundle(report: Report, root: Path, bundle: Path) -> None:
    section = "review-bundle"
    if not bundle.is_dir():
        report.add(section, "committed bundle exists", STATUS_FAIL, f"{bundle} missing")
        return

    with tempfile.TemporaryDirectory(prefix="transport-review-") as scratch:
        rebuilt = Path(scratch) / "bundle"
        try:
            export_bundle(root, rebuilt)
        except ReviewBundleError as error:
            report.add(section, "regenerate bundle", STATUS_FAIL, str(error))
            return

        committed_files = {
            str(p.relative_to(bundle))
            for p in bundle.rglob("*")
            if p.is_file() and not str(p.relative_to(bundle)).startswith("pdf/")
        }
        rebuilt_files = {
            str(p.relative_to(rebuilt)) for p in rebuilt.rglob("*") if p.is_file()
        }
        report.expect(
            section,
            "regenerated file set matches the committed bundle",
            committed_files == rebuilt_files,
            f"only-committed={sorted(committed_files - rebuilt_files)[:5]} "
            f"only-rebuilt={sorted(rebuilt_files - committed_files)[:5]}",
            status=STATUS_PASS,
        )
        differing = [
            name
            for name in sorted(committed_files & rebuilt_files)
            if (bundle / name).read_bytes() != (rebuilt / name).read_bytes()
        ]
        report.expect(
            section,
            "every regenerated byte matches the committed bundle",
            not differing,
            f"{len(differing)} differing files: {differing[:5]}",
            status=STATUS_PASS,
        )

    manifest = load_json_strict(bundle / "manifest.json")
    inventory_ok = True
    for entry in manifest["outputs"]:
        path = bundle / entry["path"]
        if not path.is_file() or sha256_file(path) != entry["sha256"]:
            inventory_ok = False
            report.add(
                section, f"manifest entry {entry['path']}", STATUS_FAIL, "hash mismatch"
            )
        elif path.stat().st_size != entry["bytes"]:
            inventory_ok = False
            report.add(
                section, f"manifest entry {entry['path']}", STATUS_FAIL, "size mismatch"
            )
    report.expect(
        section,
        f"all {len(manifest['outputs'])} manifest entries match on disk",
        inventory_ok,
        status=STATUS_PASS,
    )
    digest = __import__("hashlib").sha256(
        canonical_json(
            [
                {
                    "path": i["path"],
                    "sha256": i["sha256"],
                    "bytes": i["bytes"],
                    "record_count": i["record_count"],
                }
                for i in sorted(manifest["outputs"], key=lambda x: x["path"])
            ]
        ).encode("ascii")
    ).hexdigest()
    report.expect(
        section,
        "bundle inventory digest recomputes",
        digest == manifest["bundle_inventory_digest"],
        f"recomputed {digest}",
        status=STATUS_RECOMPUTED,
    )
    oversize = [i["path"] for i in manifest["outputs"] if i["bytes"] > 750_000]
    report.expect(
        section,
        "every bundle file is within the 750,000-byte rendering ceiling",
        not oversize,
        f"oversize: {oversize}",
        status=STATUS_PASS,
    )
    report.expect(
        section,
        "manifest records that raw inputs were not content-verified",
        manifest["limitations"]["raw_input_bytes_verified"] is False
        and manifest["limitations"]["structural_pass_is_not_full_provenance"] is True
        and manifest["limitations"][
            "float64_diagnostics_are_verified_certificates"
        ]
        is False,
        status=STATUS_PASS,
    )


# --------------------------------------------------------------------------
# 8. PDF
# --------------------------------------------------------------------------


def check_pdf(report: Report, root: Path) -> None:
    section = "pdf"
    pdf = root / PDF_PATH
    report.expect(
        section,
        "PDF hash matches the locked value",
        sha256_file(pdf) == LOCKED_PDF_SHA256,
        status=STATUS_PASS,
    )
    pages = pdf_page_count(pdf)
    report.expect(
        section,
        "PDF page count is 63",
        pages == 63,
        f"counted {pages} via standard-library object-stream inflation",
        status=STATUS_RECOMPUTED,
    )
    report.expect(
        section,
        "PDF byte count is 933908",
        pdf.stat().st_size == 933908,
        status=STATUS_PASS,
    )
    audit = root / "review/transport_instantiation/pdf/pdf_manifest.json"
    if not audit.is_file():
        report.add(
            section,
            "PDF audit package",
            STATUS_NOT_EXECUTED,
            "review/transport_instantiation/pdf/pdf_manifest.json is absent; run "
            "tools/export_transport_pdf_audit.py",
        )
        return
    manifest = load_json_strict(audit)
    report.expect(
        section,
        "PDF audit package is bound to the locked PDF hash",
        manifest.get("pdf_sha256") == LOCKED_PDF_SHA256,
        status=STATUS_PASS,
    )
    bad = [
        entry["path"]
        for entry in manifest.get("files", [])
        if not (audit.parent / entry["path"]).is_file()
        or sha256_file(audit.parent / entry["path"]) != entry["sha256"]
    ]
    report.expect(
        section,
        f"all {len(manifest.get('files', []))} PDF audit files match their hashes",
        not bad,
        f"{len(bad)} mismatched: {bad[:5]}",
        status=STATUS_PASS,
    )
    report.add(
        section,
        "byte-identical PDF rebuild",
        manifest.get("rebuild", {}).get("classification", STATUS_NOT_EXECUTED),
        manifest.get("rebuild", {}).get("detail", "not attempted"),
    )


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def run(root: Path, bundle: Path, *, skip_bundle: bool) -> Report:
    report = Report()
    check_locked_hashes(report, root)
    selection = load_json_strict(root / SELECTION_PATH)
    flat = load_json_strict(root / SELECTION_FLAT_PATH)
    report.expect(
        "selection",
        "flat and nested selection copies are identical",
        selection == flat,
        status=STATUS_PASS,
    )
    aggregate = load_json_strict(root / AGGREGATE_PATH)
    check_selection(report, root, selection)
    check_aggregate(report, root, aggregate)
    check_statistics(report, aggregate)
    check_generated_artifacts(report, root)
    check_manuscript(report, root)
    check_pdf(report, root)
    if skip_bundle:
        report.add(
            "review-bundle",
            "regeneration",
            STATUS_NOT_EXECUTED,
            "--skip-bundle was requested",
        )
    else:
        check_review_bundle(report, root, bundle)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--bundle", type=Path, default=None)
    parser.add_argument("--skip-bundle", action="store_true")
    parser.add_argument("--json", type=Path, default=None, help="write the full report")
    args = parser.parse_args(argv)

    root = args.repo_root.resolve()
    bundle = args.bundle or (root / "review/transport_instantiation")

    report = run(root, bundle, skip_bundle=args.skip_bundle)
    counts = report.counts()

    for check in report.checks:
        print(f"{check['status']:<18} {check['section']:<14} {check['check']}")
        if check["status"] in (STATUS_FAIL, STATUS_NOT_EXECUTED, STATUS_KNOWN_DIVERGENCE) and check["detail"]:
            print(f"{'':<18} {'':<14}   -> {check['detail']}")

    print()
    print("summary")
    for status in (
        STATUS_PASS,
        STATUS_RECOMPUTED,
        STATUS_STRUCTURAL,
        STATUS_KNOWN_DIVERGENCE,
        STATUS_NOT_EXECUTED,
        STATUS_FAIL,
    ):
        print(f"  {counts.get(status, 0):4d}  {STATUS_LABELS[status]}")

    payload = {
        "schema_version": 1,
        "repo_root": str(root),
        "counts": counts,
        "ok": not report.failures,
        "checks": report.checks,
    }
    if args.json:
        args.json.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print()
    print(canonical_json({"ok": payload["ok"], "counts": counts}))
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
