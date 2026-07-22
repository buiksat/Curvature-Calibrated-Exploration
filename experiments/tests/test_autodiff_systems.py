from __future__ import annotations

import hashlib
import json
from pathlib import Path

from experiments.config import load_config
from experiments.run_autodiff_systems import (
    BENCHMARK_KIND,
    BUCK_TORCH_BLOCKER_REASON,
    METHODS,
    TorchCapability,
    mlp_parameter_count,
    run_autodiff_systems,
    run_experiment,
    save_run,
    torch_capability,
)


def test_full_protocol_uses_an_actual_large_mlp_and_two_history_operators() -> None:
    config = load_config(
        "experiments/configs/autodiff_systems.yaml", profile="full"
    )
    count = mlp_parameter_count(config["architecture"])

    assert count == 131_841
    assert count >= 100_000
    assert config["window_size"] < config["history_size"]
    assert config["device"] == "auto"
    assert set(config["seed_sets"]) == {"development", "tuning", "evaluation"}


def test_missing_torch_produces_deterministic_not_run_status(tmp_path: Path) -> None:
    config = load_config(
        "experiments/configs/autodiff_systems.yaml", profile="smoke"
    )
    unavailable = TorchCapability(
        available=False,
        version=None,
        reason_code="missing_optional_dependency",
        reason="PyTorch is not installed; no autodiff timing was executed.",
    )
    first = run_autodiff_systems(config, 7, capability=unavailable)
    second = run_autodiff_systems(config, 7, capability=unavailable)

    assert first == second
    assert first.status == "not_run"
    assert first.records[0]["timing_executed"] is False
    assert first.records[0]["numerical_result_reportable"] is False
    assert "wall_time_seconds" not in first.records[0]

    first_dir = save_run(first, tmp_path / "first", config)
    second_dir = save_run(second, tmp_path / "second", config)
    assert (first_dir / "status.json").read_bytes() == (
        second_dir / "status.json"
    ).read_bytes()
    payload = (first_dir / "status.json").read_bytes()
    sidecar = (first_dir / "status.json.sha256").read_text(encoding="ascii")
    assert sidecar == f"{hashlib.sha256(payload).hexdigest()}  status.json\n"

    raw = [json.loads(line) for line in (first_dir / "raw.jsonl").read_text().splitlines()]
    assert len(raw) == 1
    assert raw[0]["metrics"]["status"] == "not_run"


def test_verified_buck_dependency_blocker_is_recorded_without_timing(
    tmp_path: Path,
) -> None:
    config = load_config(
        "experiments/configs/autodiff_systems.yaml", profile="full"
    )
    blocker = TorchCapability(
        available=False,
        version=None,
        reason_code="missing_buck_dependency",
        reason=BUCK_TORCH_BLOCKER_REASON,
    )
    runs = run_experiment(
        config,
        seed_set="development",
        output_root=tmp_path,
        capability=blocker,
    )
    assert len(runs) == 1
    assert runs[0].status == "not_run"
    assert runs[0].summary["reason_code"] == "missing_buck_dependency"
    assert "Starlark call stack overflow" in runs[0].summary["reason"]
    assert runs[0].summary["timing_executed"] is False
    assert "wall_time_seconds" not in runs[0].records[0]


def test_runtime_is_explicitly_not_run_or_executes_tiny_actual_autodiff() -> None:
    config = load_config(
        "experiments/configs/autodiff_systems.yaml", profile="smoke"
    )
    run = run_autodiff_systems(config, 19)
    capability = torch_capability()

    if not capability.available:
        assert run.status == "not_run"
        assert run.summary["reason_code"] in {
            "missing_optional_dependency",
            "torch_import_failed",
            "unsupported_torch_func_api",
        }
        assert run.summary["timing_executed"] is False
        return

    assert run.status == "completed"
    assert run.summary["benchmark_kind"] == BENCHMARK_KIND
    assert run.summary["actual_autodiff"] is True
    assert run.summary["parameter_count"] == mlp_parameter_count(config["architecture"])
    assert len(run.records) == 2 * len(METHODS)
    assert {record["operator_kind"] for record in run.records} == {
        "full_history",
        "growing_window",
    }
    assert {record["method"] for record in run.records} == set(METHODS)
    for record in run.records:
        assert record["ggn_application"] == "torch_func_jvp_then_vjp"
        assert record["actual_autodiff"] is True
        assert record["wall_time_seconds"] >= 0.0
    for record in run.records:
        if record["method"] in {"scalar_cg", "batched_cg"}:
            assert len(record["per_action_explicit_relative_residual"]) == 2
            assert len(record["per_action_width_squared_relative_error"]) == 2
            assert record["sample_cvp_count"] > 0


def test_invalid_large_model_claim_is_rejected_before_runtime_probe() -> None:
    config = load_config(
        "experiments/configs/autodiff_systems.yaml", profile="smoke"
    )
    config["minimum_parameter_count"] = 100_000
    unavailable = TorchCapability(False, None, "missing", "missing")

    try:
        run_autodiff_systems(config, 3, capability=unavailable)
    except ValueError as exc:
        assert "below required minimum" in str(exc)
    else:
        raise AssertionError("an undersized architecture must not satisfy the full claim")
