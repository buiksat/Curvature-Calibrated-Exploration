"""Safety and interruption tests for the external-output research launcher."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("review_launcher", Path(__file__).with_name("run_review_experiments.py"))
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def task_payload(tmp_path):
    return ("_tuning_task", ({}, "candidate-000", 100, 4, 1.0, None, str(tmp_path / "raw"), False), "fixed-signature")


def write_fake_run(task):
    from experiments.run_transport_instantiation import REQUIRED_RUN_FILES
    directory = launcher._task_location("_tuning_task", task)
    directory.mkdir(parents=True)
    for filename in REQUIRED_RUN_FILES:
        (directory / filename).write_text(json.dumps({"valid": True}))
    return {"destination": str(directory), "valid": True}


def test_resume_reuses_only_unchanged_complete_outputs(tmp_path, monkeypatch):
    from experiments import run_transport_instantiation_study as study
    calls = []
    def execute(task):
        calls.append(task)
        return write_fake_run(task)
    monkeypatch.setattr(study, "_tuning_task", execute)
    payload = task_payload(tmp_path)
    assert launcher._resume_task(payload)["resumed"] is False
    assert launcher._resume_task(payload)["resumed"] is True
    assert len(calls) == 1
    directory = launcher._task_location(payload[0], payload[1])
    (directory / "raw.jsonl").write_text("corrupted\n")
    with pytest.raises(launcher.WorkflowError, match="evidence changed"):
        launcher._resume_task(payload)


def test_interrupted_partial_run_is_preserved_before_restart(tmp_path, monkeypatch):
    from experiments import run_transport_instantiation_study as study
    monkeypatch.setattr(study, "_tuning_task", write_fake_run)
    payload = task_payload(tmp_path)
    directory = launcher._task_location(payload[0], payload[1])
    directory.mkdir(parents=True)
    (directory / "raw.jsonl").write_text("unfinished evidence\n")
    assert launcher._resume_task(payload)["resumed"] is False
    retained = list((tmp_path / "interrupted").glob("*/raw.jsonl"))
    assert len(retained) == 1
    assert retained[0].read_text() == "unfinished evidence\n"


def test_scientific_failure_is_not_silently_rerun(tmp_path, monkeypatch):
    from experiments import run_transport_instantiation_study as study
    def failed(task):
        raise RuntimeError("deterministic audit failure")
    monkeypatch.setattr(study, "_tuning_task", failed)
    payload = task_payload(tmp_path)
    with pytest.raises(RuntimeError, match="deterministic audit"):
        launcher._resume_task(payload)
    monkeypatch.setattr(study, "_tuning_task", write_fake_run)
    with pytest.raises(launcher.WorkflowError, match="Previous task failure preserved"):
        launcher._resume_task(payload)


def test_different_task_signature_is_rejected(tmp_path, monkeypatch):
    from experiments import run_transport_instantiation_study as study
    monkeypatch.setattr(study, "_tuning_task", write_fake_run)
    payload = task_payload(tmp_path)
    launcher._resume_task(payload)
    with pytest.raises(launcher.WorkflowError, match="provenance changed"):
        launcher._resume_task((*payload[:2], "different-signature"))


def test_phase_partial_and_corrupted_outputs_are_distinguished(tmp_path):
    path = tmp_path / "selection.json"
    path.write_text("partially written")
    assert launcher.phase_ready(tmp_path, path.name) is False
    assert not path.exists()
    assert list((tmp_path / "interrupted").glob("*/selection.json"))
    for suffix in ("", ".provenance.json", ".sha256"):
        (tmp_path / (path.name + suffix)).write_text("completed")
    launcher.finish_phase(tmp_path, path.name)
    assert launcher.phase_ready(tmp_path, path.name) is True
    path.write_text("modified after completion")
    with pytest.raises(launcher.WorkflowError, match="Completed phase artifact changed"):
        launcher.phase_ready(tmp_path, path.name)


def test_external_output_rejects_checkout_and_symlink(tmp_path):
    with pytest.raises(launcher.WorkflowError, match="outside"):
        launcher.ensure_external(launcher.REPO / "results/raw/new-followup")
    shortcut = tmp_path / "checkout-link"
    shortcut.symlink_to(launcher.REPO, target_is_directory=True)
    with pytest.raises(launcher.WorkflowError, match="outside"):
        launcher.ensure_external(shortcut / "raw")
    assert launcher.ensure_external(tmp_path / "outside") == tmp_path / "outside"


def test_quadrature_cache_preserves_node_bytes_and_prevents_mutation(monkeypatch):
    import numpy as np
    installed = np.polynomial.legendre.leggauss
    original = getattr(installed, "_review_original", installed)
    monkeypatch.setattr(np.polynomial.legendre, "leggauss", original)
    cold = original(32)
    launcher.install_quadrature_cache()
    cached = np.polynomial.legendre.leggauss(32)
    again = np.polynomial.legendre.leggauss(32)
    for before, after, reused in zip(cold, cached, again):
        assert before.tobytes() == after.tobytes()
        assert after is reused
        assert not after.flags.writeable
        with pytest.raises(ValueError):
            after[0] = 0
