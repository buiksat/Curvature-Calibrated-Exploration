from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import matplotlib
import numpy as np

from experiments.artifact_utils import validate_sha256_sidecar
from experiments.config import get_seed_set, load_config
from experiments.make_end_to_end_systems_artifacts import build_artifacts
from experiments.run_autodiff_systems import mlp_parameter_count, torch_capability
from experiments.run_end_to_end_systems_benchmark import (
    COMPONENTS,
    METHODS,
    benchmark_grid,
    run_grid,
    summarize_timings,
    validate_benchmark_config,
)


CONFIG = Path("experiments/configs/end_to_end_systems_benchmark.yaml")


def test_full_protocol_has_preregistered_scale_and_disjoint_seeds() -> None:
    config = load_config(CONFIG, profile="full")
    validate_benchmark_config(config)
    models = {str(model["name"]): model for model in config["models"]}

    assert int(config["rounds"]) == 1_000
    assert int(config["warmup_rounds"]) == 10
    assert tuple(config["action_counts"]) == (5, 10)
    assert tuple(config["replay_sizes"]) == (128, 512)
    assert tuple(config["methods"]) == METHODS
    assert mlp_parameter_count(models["mlp_100k"]["architecture"]) == 131_841
    assert mlp_parameter_count(models["mlp_1m"]["architecture"]) == 1_051_393
    assert len(get_seed_set(config, "evaluation")) == 10
    assert set(get_seed_set(config, "tuning")).isdisjoint(
        get_seed_set(config, "evaluation")
    )
    assert len(benchmark_grid(config, "evaluation")) == 480


def test_methods_are_labeled_by_implemented_algebra() -> None:
    config = load_config(CONFIG, profile="smoke")
    validate_benchmark_config(config)

    assert "lofi" not in METHODS
    assert "kfac" not in METHODS
    assert set(config["unavailable_baselines"]) == {"lofi", "kfac"}
    assert "not KFAC" in config["method_semantics"]["local_tensor_block_isotropic"]
    assert "collection-time" in config["method_semantics"]["exact_last_layer"]
    assert len(benchmark_grid(config, "evaluation")) == len(METHODS)


def test_timing_summary_reports_total_and_quantiles() -> None:
    summary = summarize_timings([0.1, 0.2, 0.3, 0.4])

    assert summary["count"] == 4
    assert np.isclose(summary["total_seconds"], 1.0)
    assert np.isclose(summary["p50_seconds"], 0.25)
    assert np.isclose(summary["p95_seconds"], 0.385)


def test_tiny_real_loop_and_artifact_validation(tmp_path: Path) -> None:
    config = copy.deepcopy(load_config(CONFIG, profile="smoke"))
    config["rounds"] = 2
    config["warmup_rounds"] = 1
    config["replay_sizes"] = [1]
    validate_benchmark_config(config)

    raw_root = tmp_path / "raw"
    result = run_grid(
        config,
        profile="smoke",
        seed_set="evaluation",
        output_root=raw_root,
    )
    capability = torch_capability()
    phase_root = raw_root / "smoke" / "evaluation"
    validate_sha256_sidecar(phase_root / "manifest.json")
    if not capability.available:
        assert result["status"] == "not_run"
        manifest = json.loads(
            (phase_root / "manifest.json").read_text(encoding="ascii")
        )
        assert manifest["reportable_complete"] is False
        assert manifest["completed_run_count"] == 0
        return

    assert result["status"] == "completed"
    assert result["completed_run_count"] == len(METHODS)
    assert result["reportable_complete"] is True
    for method in METHODS:
        directory = phase_root / "model-mlp_smoke_K-2_replay-1" / method / "seed-8000"
        for filename in ("manifest.json", "summary.json", "timings.npz"):
            validate_sha256_sidecar(directory / filename)
        summary = json.loads((directory / "summary.json").read_text(encoding="ascii"))
        manifest = json.loads(
            (directory / "manifest.json").read_text(encoding="ascii")
        )
        assert summary["evidence_scope"] == "SMOKE ONLY - not main-paper evidence"
        assert manifest["evidence_scope"] == "SMOKE ONLY - not main-paper evidence"
        assert set(summary["latency_components"]) == set(COMPONENTS)
        assert all(
            summary["latency_components"][component]["count"] == 1
            for component in COMPONENTS
        )
        with np.load(directory / "timings.npz", allow_pickle=False) as archive:
            assert archive["host_rss_bytes"].shape == (1,)
            assert archive["device_allocated_bytes"].shape == (1,)
            assert archive["device_reserved_bytes"].shape == (1,)

    derived = tmp_path / "derived"
    artifacts = build_artifacts(
        config,
        profile="smoke",
        raw_root=raw_root,
        aggregate_path=derived / "aggregate.json",
        figure_path=derived / "systems.pdf",
        table_path=derived / "systems.tex",
    )
    assert artifacts["validated_run_count"] == len(METHODS)
    assert artifacts["evidence_scope"] == "SMOKE ONLY - not main-paper evidence"
    aggregate = json.loads(
        (derived / "aggregate.json").read_text(encoding="ascii")
    )
    assert aggregate["evidence_scope"] == "SMOKE ONLY - not main-paper evidence"
    assert "SMOKE ONLY --- not main-paper evidence" in (
        derived / "systems.tex"
    ).read_text(encoding="ascii")
    assert matplotlib.rcParams["pdf.fonttype"] == 42
    for path in (
        derived / "aggregate.json",
        derived / "systems.pdf",
        derived / "systems.tex",
    ):
        validate_sha256_sidecar(path)
    if shutil.which("pdffonts"):
        fonts = subprocess.run(
            ["pdffonts", (derived / "systems.pdf").as_posix()],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert "Type 3" not in fonts
    if shutil.which("pdftotext"):
        extracted = subprocess.run(
            ["pdftotext", (derived / "systems.pdf").as_posix(), "-"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert "SMOKE ONLY - not main-paper evidence" in extracted
