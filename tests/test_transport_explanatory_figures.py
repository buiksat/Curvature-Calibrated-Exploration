"""Plotted quantities keep their population, units, and immutable evidence bindings."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import anonymous_package_contract as package_contract
import followup_anonymous_contract as followup_contract
import make_transport_explanatory_figures as figures


def rows(name):
    with (ROOT / "paper/figures" / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def test_plot_data_use_all_prespecified_cells_and_the_stated_statistics():
    aggregate = json.loads((ROOT / figures.FULL / "aggregate_compact.json").read_text())
    diagnostics = json.loads((ROOT / figures.FULL / "drift_and_reference_diagnostics.json").read_text())
    decomposition = json.loads((ROOT / figures.FULL / "terminal_bound_decomposition.json").read_text())
    outcomes = rows("transport_explanatory_outcomes.csv")
    paired = rows("transport_explanatory_paired.csv")
    bounds = rows("transport_explanatory_bounds.csv")
    assert len(outcomes) == 12 and len(paired) == 9 and len(bounds) == 6
    assert {(float(r["W"]), r["method"]) for r in outcomes} == {
        (width, method) for width in (16., 1., .25)
        for method in ("transport_hessian", "transport_endpoint", "frozen_reference", "naive_current")}
    assert {(float(r["W"]), r["method"]) for r in paired} == {
        (float(r["W"]), r["method"]) for r in outcomes if r["method"] != "transport_hessian"}
    assert {(float(r["W"]), r["method"]) for r in bounds} == {
        (width, method) for width in (16., 1., .25)
        for method in ("transport_hessian", "frozen_reference")}
    for row in outcomes + paired:
        source, = [r for r in aggregate["policy_outcomes"]
                   if r["horizon"] == int(row["horizon"]) == 1000
                   and r["target_D"] == float(row["target_D"])
                   and r["method"] == row["method"]]
        assert int(row["n"]) == source["run_count"] == 50
        if "mean_regret" in row:
            assert float(row["mean_regret"]) == source["cumulative_pseudo_regret"]["mean"]
        else:
            interval = source["paired_difference_from_transport_hessian"]["bootstrap_mean_interval"]
            for plotted, original in (("mean_difference", "mean"), ("ci_low", "ci_low"),
                                      ("ci_high", "ci_high"), ("level", "level")):
                assert float(row[plotted]) == interval[original]
            assert int(row["resamples"]) == interval["resamples"] == 10000
            assert float(row["level"]) == .95
    for row in bounds:
        width, target = float(row["W"]), float(row["target_D"])
        diagnostic, = [r for r in diagnostics if r["horizon"] == 1000
                       and r["W"] == width and r["method"] == row["method"]]
        if row["method"] == "transport_hessian":
            source, = [r for r in decomposition if r["horizon"] == r["round"] == 1000
                       and r["target_D"] == target]
            mean_rhs = source["sharp_theorem_rhs"]
        else:
            mean_rhs = diagnostic["reference_geometry_rhs_mean_on_own_trajectory"]
        cap = 2 * 1000 * min(1, math.sqrt(width))
        assert int(row["n"]) == diagnostic["seeds"] == 50
        assert float(row["mean_terminal_rhs"]) == mean_rhs
        assert float(row["deterministic_cap"]) == diagnostic["deterministic_regret_cap"] == cap
        assert float(row["mean_rhs_over_cap"]) == mean_rhs / cap
        assert float(row["log10_mean_rhs_over_cap"]) == math.log10(mean_rhs / cap)


@pytest.fixture
def original_figure_tree(tmp_path):
    for relative in (*figures.INPUT_HASHES, *figures.build(ROOT)):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, path)
    return tmp_path


def check(root):
    return subprocess.run([sys.executable, str(ROOT / "tools/make_transport_explanatory_figures.py"),
                           "--root", str(root), "--check"], capture_output=True, text=True)


@pytest.mark.parametrize("name,column", [
    ("transport_explanatory_outcomes.csv", "mean_regret"),
    ("transport_explanatory_paired.csv", "ci_low"),
    ("transport_explanatory_paired.csv", "ci_high"),
    ("transport_explanatory_bounds.csv", "log10_mean_rhs_over_cap"),
])
def test_changed_plotted_quantity_fails_even_with_rewritten_output_provenance(
        original_figure_tree, name, column):
    root = original_figure_tree
    assert check(root).returncode == 0
    path = root / "paper/figures" / name
    with path.open(newline="") as stream:
        data = list(csv.DictReader(stream))
    data[0][column] = str(float(data[0][column]) + .125)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(data[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(data)
    provenance = root / "paper/figures/transport_explanatory_provenance.json"
    record = json.loads(provenance.read_text())
    for output in record["outputs"]:
        if Path(output["path"]).name == name:
            output["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    provenance.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    done = check(root)
    assert done.returncode != 0 and "Generated figure differs" in done.stderr


def test_a_changed_typeset_point_is_rejected(original_figure_tree):
    root = original_figure_tree
    path = root / "paper/figures/transport_explanatory_outcomes.tex"
    value = format(float(rows("transport_explanatory_outcomes.csv")[0]["mean_regret"]), ".17g")
    assert value in path.read_text()
    path.write_text(path.read_text().replace(value, "999", 1))
    assert check(root).returncode != 0


@pytest.fixture
def anonymous_figures(tmp_path):
    followup_contract.stage_transform(tmp_path, ROOT)
    # This fixture exercises the follow-up contract and generator only. The
    # existing full-supplement fixture separately validates the older study.
    (tmp_path / package_contract.DECLARATION_NAME).write_text("{}\n")
    for relative in ("tools/anonymous_package_contract.py",
                     "tools/followup_anonymous_contract.py",
                     "tools/make_transport_explanatory_figures.py"):
        path = tmp_path / relative
        path.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / relative, path)
    return tmp_path


def test_anonymous_figures_reconstruct_exact_original_attribution(anonymous_figures):
    assert figures.build(anonymous_figures) == figures.build(ROOT)
    assert not followup_contract.validate_packaged(anonymous_figures)


@pytest.mark.parametrize("state", ["missing", "replaced"])
def test_chart_generator_authenticates_helper_before_import(anonymous_figures, state):
    path = anonymous_figures / "tools/followup_anonymous_contract.py"
    marker = anonymous_figures / "executed.txt"
    if state == "missing":
        path.unlink()
    else:
        path.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n")
    with pytest.raises(ImportError, match="independent pin"):
        figures.build(anonymous_figures)
    assert not marker.exists()


def test_required_package_cannot_fall_back_to_original_evidence(original_figure_tree, monkeypatch):
    monkeypatch.setenv(package_contract.ENV_REQUIRE_PACKAGE, "1")
    with pytest.raises(ValueError, match="declaration"):
        figures.build(original_figure_tree)


def test_schematic_mutation_fails_its_separate_reviewed_source_pin(anonymous_figures):
    path = anonymous_figures / "paper/figures/transport_conceptual_geometry.tex"
    before = path.read_text()
    assert "x radius=.525cm" in before
    path.write_text(before.replace("x radius=.525cm", "x radius=1.05cm"))
    assert any(str(path.relative_to(anonymous_figures)) in problem
               for problem in followup_contract.validate_packaged(anonymous_figures))


def test_ledger_rejects_a_replaced_chart_generator_before_execution(tmp_path):
    import verify_tmlr_submission_numbers as ledger
    path = tmp_path / ledger.EXPLANATORY_GENERATOR
    path.parent.mkdir()
    shutil.copyfile(ROOT / ledger.EXPLANATORY_GENERATOR, path)
    assert ledger._load_reviewed_tool(tmp_path, ledger.EXPLANATORY_GENERATOR)
    marker = tmp_path / "executed.txt"
    path.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n")
    with pytest.raises(ledger.LedgerError, match="unreviewed or missing tool"):
        ledger._load_reviewed_tool(tmp_path, ledger.EXPLANATORY_GENERATOR)
    assert not marker.exists()
