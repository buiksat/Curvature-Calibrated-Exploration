"""Regression tests for the four fixes from the 2026-11-17 review of the 600-run study code.

Run from the repository root (kept outside tests/ and experiments/tests/, whose collected count is pinned):
    python -B -m pytest -q -p no:cacheprovider review/old_study_review/test_old_study_fixes.py
"""
import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

from experiments.config import load_config
from experiments.run_transport_instantiation_study import study_source_inventory
from experiments.transport_instantiation import OptimizerSpec, policy_scores, run_policy_trajectory

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("review_launcher", ROOT / "tools/run_review_experiments.py")
launcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(launcher)


def test_study_inventory_builds_without_the_archived_buck_file():
    paths = [item["path"] for item in study_source_inventory()]
    assert "experiments/BUCK" not in paths
    assert "experiments/transport_instantiation.py" in paths


def test_unused_transport_factor_cannot_overflow():
    args = dict(beta=2.0, current_bias=0.3, frozen_widths=np.ones(5), current_widths=np.ones(5),
                hessian_path_bound=1500.0, endpoint_distance=0.1)
    for method in ("frozen_reference", "naive_current"):
        assert np.array_equal(policy_scores(method, np.zeros(5), **args), np.full(5, 2.3))
    with pytest.raises(OverflowError):
        policy_scores("transport_hessian", np.zeros(5), **args)


def test_logged_ratios_use_the_configured_denominator_tolerance():
    config = load_config(ROOT / "experiments/configs/transport_review_followup.yaml", "full")
    # "full" diagnostics compute the quadrature path length, so both ratio fields are exercised
    row = run_policy_trajectory(config, "frozen_reference", 50004, 2, 0.001, OptimizerSpec(0.0003, 20), "full").rounds[1]
    tolerance = config["numerics"]["ratio_denominator_tolerance"]
    for ratio, denominator in (("D_Q_over_d_Th", "d_Th"), ("D_Q_over_path_quad", "D_path_quad")):
        assert tolerance < row[denominator] <= row["algebra_tolerance"]  # the case the old rule dropped
        assert math.isclose(row[ratio], row["D_Q"] / row[denominator], rel_tol=1e-15)


def test_success_moves_earlier_interruptions_out_of_the_active_error():
    manifest = {"status": "incomplete", "error": "KeyboardInterrupt: "}
    launcher.mark_succeeded(manifest, status="development_complete", evaluation_complete=False)
    manifest.update(status="incomplete", error="OSError: disk full")  # a later attempt fails, then resumes
    launcher.mark_succeeded(manifest, status="complete", evaluation_complete=True)
    assert "error" not in manifest
    assert manifest["resumed_after_errors"] == ["KeyboardInterrupt: ", "OSError: disk full"]
    assert manifest["status"] == "complete" and manifest["evaluation_complete"] is True
    clean = {"status": "evaluation"}
    launcher.mark_succeeded(clean, status="complete")
    assert clean == {"status": "complete"}
