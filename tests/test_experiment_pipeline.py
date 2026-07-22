from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

import pytest

from experiments.config import ConfigError, config_digest, get_seed_set, load_config
from experiments.logging_utils import ExperimentLogger, derive_seed, seed_everything


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "experiments" / "configs"
CONFIG_NAMES = {
    "balanced_benchmark",
    "certified_tanh",
    "linear_audit",
    "nonlinear_drift",
    "operator_ablation",
    "cg_accuracy",
    "systems_scaling",
    "covertype_rerun",
    "curvature_phase_diagram",
    "offdiagonal_witness",
    "spectral_tail_study",
    "autodiff_systems",
}


def _metadata() -> dict[str, object]:
    return {
        "git_revision": "0123456789abcdef",
        "git_dirty": False,
        "git_root": "/repo",
        "package_versions": {"numpy": "1.0"},
        "hardware": {"machine": "test-machine", "logical_cpu_count": 1},
        "python": {"version": "3.test", "implementation": "CPython", "executable": "python"},
    }


def _fixed_clock() -> dt.datetime:
    return dt.datetime(2026, 7, 17, 12, 0, tzinfo=dt.timezone.utc)


def test_all_configs_resolve_with_disjoint_seed_sets() -> None:
    paths = sorted(CONFIG_DIR.glob("*.yaml"))
    assert {path.stem for path in paths} == CONFIG_NAMES

    for path in paths:
        raw_text = path.read_text(encoding="utf-8")
        assert isinstance(json.loads(raw_text), dict), f"{path} must remain JSON-compatible YAML"
        for profile in ("smoke", "full"):
            resolved = load_config(path, profile=profile)
            tuning = get_seed_set(resolved, "tuning")
            evaluation = get_seed_set(resolved, "evaluation")
            assert set(tuning).isdisjoint(evaluation)
            assert resolved["profile"] == profile
            assert resolved["rounds"] > 0


def test_config_resolution_and_digest_are_deterministic() -> None:
    path = CONFIG_DIR / "linear_audit.yaml"
    first = load_config(path, profile="smoke")
    first["environment"]["feature_dimension"] = -1
    second = load_config(path, profile="smoke")

    assert second["environment"]["feature_dimension"] == 53
    assert config_digest(second) == config_digest(load_config(path, profile="smoke"))


def test_invalid_overlapping_seed_sets_are_rejected(tmp_path: Path) -> None:
    document = {
        "schema_version": 1,
        "name": "bad",
        "description": "bad seed split",
        "base": {"rounds": 1},
        "profiles": {
            "smoke": {"seed_sets": {"tuning": [1], "evaluation": [1]}},
            "full": {"seed_sets": {"tuning": [2], "evaluation": [3]}},
        },
    }
    path = tmp_path / "bad.yaml"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ConfigError, match="overlap"):
        load_config(path)


def test_optional_development_seed_set_is_disjoint_and_accessible(tmp_path: Path) -> None:
    document = {
        "schema_version": 1,
        "name": "three-way-split",
        "description": "three-way seed split",
        "base": {"rounds": 1},
        "profiles": {
            "smoke": {
                "seed_sets": {
                    "development": [1],
                    "tuning": [2],
                    "evaluation": [3],
                }
            },
            "full": {
                "seed_sets": {
                    "development": [4],
                    "tuning": [5],
                    "evaluation": [6],
                }
            },
        },
    }
    path = tmp_path / "three-way.yaml"
    path.write_text(json.dumps(document), encoding="utf-8")
    resolved = load_config(path, profile="smoke")
    assert get_seed_set(resolved, "development") == (1,)
    assert get_seed_set(resolved, "tuning") == (2,)
    assert get_seed_set(resolved, "evaluation") == (3,)


def test_seed_derivation_and_stdlib_seeding_are_reproducible() -> None:
    assert derive_seed(7, "operator", 2) == derive_seed(7, "operator", 2)
    assert derive_seed(7, "operator", 2) != derive_seed(7, "operator", 3)

    seed_everything(314159, include_optional=False)
    first = [random.random() for _ in range(5)]
    seed_everything(314159, include_optional=False)
    assert [random.random() for _ in range(5)] == first


def test_logger_writes_deterministic_manifest_and_round_jsonl(tmp_path: Path) -> None:
    config = load_config(CONFIG_DIR / "cg_accuracy.yaml", profile="smoke")
    run_bytes: list[tuple[bytes, bytes]] = []

    for name in ("first", "second"):
        output = tmp_path / name
        with ExperimentLogger(
            output,
            config,
            seed=30,
            metadata=_metadata(),
            clock=_fixed_clock,
        ) as logger:
            logger.log_round(0, {"regret": 0.0, "cg_iterations": 3})
            logger.log_round(1, regret=0.25, cg_iterations=4)
        run_bytes.append(
            ((output / "manifest.jsonl").read_bytes(), (output / "raw.jsonl").read_bytes())
        )

    assert run_bytes[0] == run_bytes[1]
    manifest = json.loads(run_bytes[0][0])
    rounds = [json.loads(line) for line in run_bytes[0][1].splitlines()]
    assert manifest["config"] == config
    assert manifest["seed"] == 30
    assert manifest["git_revision"] == "0123456789abcdef"
    assert manifest["package_versions"] == {"numpy": "1.0"}
    assert manifest["hardware"]["machine"] == "test-machine"
    assert [record["round"] for record in rounds] == [0, 1]
    assert rounds[1]["metrics"]["regret"] == 0.25


def test_logger_rejects_duplicate_round_and_nonfinite_metric(tmp_path: Path) -> None:
    config = load_config(CONFIG_DIR / "linear_audit.yaml", profile="smoke")
    with ExperimentLogger(
        tmp_path / "run",
        config,
        seed=0,
        metadata=_metadata(),
        clock=_fixed_clock,
    ) as logger:
        logger.log_round(0, regret=0.0)
        with pytest.raises(ValueError, match="strictly"):
            logger.log_round(0, regret=0.1)
        with pytest.raises(ValueError, match="non-finite"):
            logger.log_round(1, regret=float("nan"))
