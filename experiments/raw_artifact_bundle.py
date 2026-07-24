"""Create and verify portable bundles of seed-level figure evidence."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
import os
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Mapping, Sequence

from .artifact_utils import (
    input_set_sha256,
    sha256_file,
    validate_sha256_sidecar,
    write_json_artifact,
    write_sha256_sidecar,
)
from .config import config_digest, get_seed_set, load_config
from .logging_utils import canonical_json
from .scaled_tanh_config_compat import resolve_execution_config


SCHEMA_VERSION = 1
SCALED_TANH_EXPERIMENT = "scaled_tanh_instantiation"
WHEEL_EXPERIMENT = "wheel_benchmark"
EXPERIMENT = SCALED_TANH_EXPERIMENT
SUPPORTED_EXPERIMENTS = {SCALED_TANH_EXPERIMENT, WHEEL_EXPERIMENT}
COMPRESSION_LEVEL = 9
CHUNK_SIZE = 1024 * 1024


class RawArtifactBundleError(ValueError):
    """Raised when source evidence or an archive violates the bundle contract."""


@dataclass(frozen=True)
class SourceEntry:
    source: Path
    archive_path: str
    sha256: str
    size_bytes: int
    role: str

    def inventory_value(self) -> dict[str, Any]:
        return {
            "path": self.archive_path,
            "role": self.role,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


def default_inventory_path(bundle_path: Path) -> Path:
    return bundle_path.with_name(bundle_path.name + ".inventory.json")


def _sidecar(path: Path) -> Path:
    return path.with_name(path.name + ".sha256")


def _artifact_files(path: Path) -> tuple[Path, Path]:
    return path, _sidecar(path)


def _role(path: Path, *, experiment: str) -> str:
    if experiment == WHEEL_EXPERIMENT:
        if path.name == "tuning_selection.json":
            return "wheel_tuning_selection"
        phase = "tuning" if "tuning" in path.parts else "evaluation"
        return {
            "manifest.jsonl": f"wheel_{phase}_manifest",
            "raw.jsonl": f"wheel_{phase}_raw",
            "summary.jsonl": f"wheel_{phase}_summary",
        }.get(path.name) or _raise_unrecognized(path)
    if path.name.endswith(".sha256"):
        return "sha256_sidecar"
    if path.name == "optimizer_selection.json":
        return "optimizer_selection"
    if path.name == "manifest.json":
        return "run_manifest"
    if path.name == "summary.json":
        return "run_summary"
    if path.name == "rounds.npz":
        return "round_trajectory"
    return _raise_unrecognized(path)


def _raise_unrecognized(path: Path) -> str:
    raise RawArtifactBundleError(f"unrecognized raw evidence file {path}")


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _validate_exact_tree(profile_root: Path, expected: set[Path]) -> None:
    if not profile_root.is_dir():
        raise RawArtifactBundleError(f"missing raw profile directory {profile_root}")
    symlinks = sorted(path for path in profile_root.rglob("*") if path.is_symlink())
    if symlinks:
        relative = [path.relative_to(profile_root).as_posix() for path in symlinks]
        raise RawArtifactBundleError(f"raw profile contains symlinks: {relative[:5]}")
    actual = {path.resolve() for path in profile_root.rglob("*") if path.is_file()}
    normalized_expected = {path.resolve() for path in expected}
    missing = sorted(
        path.relative_to(profile_root.resolve()).as_posix()
        for path in normalized_expected - actual
    )
    unexpected = sorted(
        path.relative_to(profile_root.resolve()).as_posix()
        for path in actual - normalized_expected
    )
    if missing or unexpected:
        raise RawArtifactBundleError(
            "raw profile inventory mismatch: "
            f"missing={missing[:5]}, unexpected={unexpected[:5]}"
        )


def _source_json(path: Path) -> dict[str, Any]:
    try:
        validate_sha256_sidecar(path)
        value = json.loads(path.read_text(encoding="ascii"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise RawArtifactBundleError(
            f"invalid raw JSON record {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise RawArtifactBundleError(f"raw JSON record is not an object: {path}")
    return value


def _sha256_text(value: Any, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RawArtifactBundleError(f"invalid {name} SHA-256")
    return value


def _validate_source_run(
    directory: Path,
    *,
    config: Mapping[str, Any],
    profile: str,
    seed: int,
    cell: Any,
    method: str,
    selection_sha256: str,
    runner_source_sha256: str,
) -> tuple[str, str]:
    import numpy as np

    manifest_path = directory / "manifest.json"
    summary_path = directory / "summary.json"
    rounds_path = directory / "rounds.npz"
    manifest = _source_json(manifest_path)
    summary = _source_json(summary_path)
    try:
        validate_sha256_sidecar(rounds_path)
    except (OSError, ValueError) as error:
        raise RawArtifactBundleError(
            f"invalid round archive sidecar {rounds_path}: {error}"
        ) from error
    expected_cell = {
        "horizon": cell.horizon,
        "width_ratio": cell.width_ratio,
        "width": cell.width,
        "residual_factor": cell.residual_factor,
    }
    expected_manifest = {
        "schema_version": 1,
        "experiment": EXPERIMENT,
        "profile": profile,
        "phase": "evaluation",
        "seed": seed,
        "method": method,
        "cell": expected_cell,
        "config": dict(config),
        "config_digest": config_digest(config),
        "rng": config["rng"],
        "selection_protocol": config["selection_protocol"],
        "optimizer_selection_sha256": selection_sha256,
        "evaluation_data_used_for_selection": False,
    }
    for key, expected in expected_manifest.items():
        if manifest.get(key) != expected:
            raise RawArtifactBundleError(
                f"manifest identity mismatch for {directory}: {key}"
            )
    provenance = manifest.get("provenance")
    source_hashes = {
        "experiments/run_scaled_tanh_instantiation.py": runner_source_sha256
    }
    if (
        not isinstance(provenance, dict)
        or provenance.get("source_artifact_hashes") != source_hashes
    ):
        raise RawArtifactBundleError(
            f"manifest source provenance mismatch for {directory}"
        )
    if manifest.get("rounds_sha256") != sha256_file(rounds_path):
        raise RawArtifactBundleError(f"round archive hash mismatch for {directory}")
    if manifest.get("summary_sha256") != sha256_file(summary_path):
        raise RawArtifactBundleError(f"summary hash mismatch for {directory}")
    expected_summary = {
        "schema_version": 1,
        "experiment": EXPERIMENT,
        "method": method,
        "cell": expected_cell,
        "dimension": int(config["dimension"]),
        "effective_rank": int(config["effective_rank"]),
        "action_count": int(config["action_count"]),
        "policy_uses_teacher": False,
        "evaluation_data_used_for_selection": False,
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            raise RawArtifactBundleError(
                f"summary identity mismatch for {directory}: {key}"
            )
    try:
        with np.load(rounds_path, allow_pickle=False) as archive:
            if not archive.files:
                raise RawArtifactBundleError(f"empty round archive {rounds_path}")
            for name in archive.files:
                if archive[name].dtype.hasobject:
                    raise RawArtifactBundleError(
                        f"object array {name!r} in {rounds_path}"
                    )
    except (OSError, ValueError) as error:
        raise RawArtifactBundleError(
            f"cannot read round archive {rounds_path}: {error}"
        ) from error
    return (
        _sha256_text(manifest.get("environment_sha256"), name="environment"),
        _sha256_text(manifest.get("stream_sha256"), name="stream"),
    )


def _validated_scaled_tanh_sources(
    config: dict[str, Any],
    *,
    profile: str,
    raw_root: Path,
) -> tuple[list[Path], str, str, int, dict[str, Any], dict[str, Any]]:
    from .make_scaled_tanh_instantiation_artifacts import (
        ScaledTanhArtifactError,
        _load_selection,
        _run_directory,
        _runner_source_sha256,
    )
    from .run_scaled_tanh_instantiation import (
        cells,
        validate_config,
    )

    validate_config(config)
    if config.get("profile") != profile:
        raise RawArtifactBundleError("resolved config profile does not match profile")
    raw_root = raw_root.resolve()
    profile_root = raw_root / profile
    selection_path = profile_root / "optimizer_selection.json"
    runner_source_sha256 = _runner_source_sha256()
    selection_record = _source_json(selection_path)
    try:
        execution_config, config_wording_migration = resolve_execution_config(
            config, str(selection_record.get("config_digest", ""))
        )
        _, selection_sha256, _ = _load_selection(
            execution_config,
            profile=profile,
            selection_path=selection_path,
            runner_source_sha256=runner_source_sha256,
        )
    except (OSError, ValueError, ScaledTanhArtifactError) as error:
        raise RawArtifactBundleError(
            f"scaled-tanh tuning selection validation failed: {error}"
        ) from error

    expected_paths: set[Path] = set(_artifact_files(selection_path))
    methods = tuple(str(value) for value in config["methods"])
    seeds = get_seed_set(config, "evaluation")
    validated_runs = 0
    environment_sha256: str | None = None
    stream_sha256_by_horizon_seed: dict[tuple[int, int], str] = {}
    for cell in cells(execution_config):
        for seed in seeds:
            for method in methods:
                directory = _run_directory(raw_root, profile, cell, method, seed)
                try:
                    run_environment_sha256, run_stream_sha256 = _validate_source_run(
                        directory,
                        config=execution_config,
                        profile=profile,
                        seed=seed,
                        cell=cell,
                        method=method,
                        selection_sha256=selection_sha256,
                        runner_source_sha256=runner_source_sha256,
                    )
                except (OSError, ValueError) as error:
                    raise RawArtifactBundleError(
                        "scaled-tanh run validation failed for "
                        f"{cell.token}/{method}/seed-{seed}: {error}"
                    ) from error
                if environment_sha256 is None:
                    environment_sha256 = run_environment_sha256
                elif run_environment_sha256 != environment_sha256:
                    raise RawArtifactBundleError(
                        f"environment digest mismatch for {directory}"
                    )
                stream_key = (int(cell.horizon), int(seed))
                prior_stream_sha256 = stream_sha256_by_horizon_seed.setdefault(
                    stream_key, run_stream_sha256
                )
                if run_stream_sha256 != prior_stream_sha256:
                    raise RawArtifactBundleError(
                        f"common-stream digest mismatch for {directory}"
                    )
                for name in ("manifest.json", "summary.json", "rounds.npz"):
                    expected_paths.update(_artifact_files(directory / name))
                validated_runs += 1

    expected_run_count = len(cells(execution_config)) * len(methods) * len(seeds)
    if validated_runs != expected_run_count:
        raise RawArtifactBundleError(
            f"validated {validated_runs} runs, expected {expected_run_count}"
        )
    _validate_exact_tree(profile_root, expected_paths)
    return (
        sorted(expected_paths),
        selection_sha256,
        runner_source_sha256,
        validated_runs,
        execution_config,
        config_wording_migration,
    )


def _single_jsonl(path: Path) -> dict[str, Any]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except OSError as error:
        raise RawArtifactBundleError(
            f"cannot read JSONL record {path}: {error}"
        ) from error
    if len(lines) != 1:
        raise RawArtifactBundleError(f"expected one JSONL record in {path}")
    try:
        value = json.loads(lines[0])
    except json.JSONDecodeError as error:
        raise RawArtifactBundleError(f"invalid JSONL record {path}: {error}") from error
    if not isinstance(value, dict):
        raise RawArtifactBundleError(f"JSONL record is not an object: {path}")
    return value


def _validate_round_jsonl(path: Path, *, seed: int, rounds: int) -> None:
    completed = 0
    try:
        with path.open("r", encoding="ascii") as handle:
            for completed, line in enumerate(handle, start=1):
                value = json.loads(line)
                expected_round = completed - 1
                if (
                    not isinstance(value, dict)
                    or value.get("schema_version") != 1
                    or value.get("event") != "round"
                    or value.get("seed") != seed
                    or value.get("round") != expected_round
                    or not isinstance(value.get("metrics"), dict)
                ):
                    raise RawArtifactBundleError(
                        f"round identity mismatch at {path}:{completed}"
                    )
    except (OSError, json.JSONDecodeError) as error:
        raise RawArtifactBundleError(f"invalid round JSONL {path}: {error}") from error
    if completed != rounds:
        raise RawArtifactBundleError(
            f"round coverage mismatch for {path}: {completed} != {rounds}"
        )


def _wheel_execution_config(
    config: Mapping[str, Any],
    *,
    phase: str,
    method: str,
    cell: Any,
    ridge: float,
    bonus: float,
    selection_payload_sha256: str | None,
) -> dict[str, Any]:
    result = copy.deepcopy(dict(config))
    execution: dict[str, Any] = {
        "seed_set": phase,
        "method": method,
        "cell": {"delta": cell.delta, "token": cell.token},
        "comparison": "pooled_validation_tuned",
        "executed_policy": True,
        "mode": "online_adaptive",
        "hyperparameters": {"ridge": ridge, "bonus_scale": bonus},
    }
    if phase == "evaluation":
        if selection_payload_sha256 is None:
            raise RawArtifactBundleError("evaluation lacks a selection digest")
        execution.update(
            {
                "tuning_selection_sha256": selection_payload_sha256,
                "pooled_over_all_declared_deltas": True,
                "evaluation_rerun_from_scratch": True,
                "evaluation_outcomes_used_for_tuning": False,
            }
        )
    result["execution"] = execution
    return result


def _validate_wheel_run_source(
    directory: Path,
    *,
    config: Mapping[str, Any],
    profile: str,
    phase: str,
    method: str,
    cell: Any,
    seed: int,
    ridge: float,
    bonus: float,
    selection_payload_sha256: str | None,
) -> dict[str, Any]:
    manifest_path = directory / "manifest.jsonl"
    raw_path = directory / "raw.jsonl"
    summary_path = directory / "summary.jsonl"
    manifest = _single_jsonl(manifest_path)
    summary = _single_jsonl(summary_path)
    run_config = _wheel_execution_config(
        config,
        phase=phase,
        method=method,
        cell=cell,
        ridge=ridge,
        bonus=bonus,
        selection_payload_sha256=selection_payload_sha256,
    )
    expected_manifest = {
        "schema_version": 1,
        "event": "run_manifest",
        "seed": seed,
        "config": run_config,
        "config_digest": config_digest(run_config),
    }
    for key, expected in expected_manifest.items():
        if manifest.get(key) != expected:
            raise RawArtifactBundleError(
                f"Wheel manifest mismatch for {directory}: {key}"
            )
    rounds = int(config["tuning_rounds"] if phase == "tuning" else config["rounds"])
    expected_summary = {
        "schema_version": 1,
        "event": "wheel_benchmark_run_summary",
        "experiment": WHEEL_EXPERIMENT,
        "profile": profile,
        "phase": phase,
        "seed": seed,
        "method": method,
        "delta": cell.delta,
        "cell": {"delta": cell.delta, "token": cell.token},
        "hyperparameters": {"ridge": ridge, "bonus_scale": bonus},
        "rounds": rounds,
        "executed_policy": True,
        "eligible_for_pooled_tuning": phase == "tuning",
        "pooled_tuning_setting": phase == "evaluation",
        "evaluation_outcomes_used_for_tuning": False,
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            raise RawArtifactBundleError(
                f"Wheel summary provenance mismatch for {directory}: {key}"
            )
    _sha256_text(summary.get("environment_stream_sha256"), name="Wheel stream")
    _validate_round_jsonl(raw_path, seed=seed, rounds=rounds)
    return summary


def _wheel_source_hashes(repository: Path) -> dict[str, str]:
    paths = (
        "experiments/run_wheel_benchmark.py",
        "experiments/wheel_environment.py",
        "experiments/logging_utils.py",
        "experiments/make_wheel_benchmark_artifacts.py",
    )
    return {path: sha256_file(repository / path) for path in paths}


def _validated_wheel_sources(
    config: dict[str, Any],
    *,
    profile: str,
    raw_root: Path,
) -> tuple[
    list[Path],
    str,
    str,
    int,
    int,
    dict[str, str],
    dict[str, dict[str, float]],
]:
    from .run_wheel_benchmark import (
        METHODS,
        cells,
        hyperparameter_grid,
        load_tuning_selection,
        validate_tuning_selection,
        validate_wheel_config,
    )

    validate_wheel_config(config)
    if config.get("profile") != profile:
        raise RawArtifactBundleError("resolved Wheel config profile mismatch")
    tuning_seeds = get_seed_set(config, "tuning")
    evaluation_seeds = get_seed_set(config, "evaluation")
    if not set(tuning_seeds).isdisjoint(evaluation_seeds):
        raise RawArtifactBundleError("Wheel tuning/evaluation seeds overlap")
    raw_root = raw_root.resolve()
    profile_root = raw_root / profile
    selection_path = profile_root / "tuning_selection.json"
    try:
        selection = load_tuning_selection(selection_path)
        selected = validate_tuning_selection(config, selection)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise RawArtifactBundleError(
            f"Wheel tuning selection validation failed: {error}"
        ) from error
    if selection.get("evaluation_outcomes_used") is not False:
        raise RawArtifactBundleError("Wheel selection reads evaluation outcomes")
    selection_payload_sha256 = hashlib.sha256(
        canonical_json(selection).encode("ascii")
    ).hexdigest()
    selection_file_sha256 = sha256_file(selection_path)
    expected_paths: set[Path] = {selection_path}
    candidate_rows = {
        (
            str(candidate["method"]),
            float(candidate["ridge"]),
            float(candidate["bonus_scale"]),
        ): {
            (float(row["delta"]), int(row["seed"])): float(
                row["cumulative_pseudo_regret"]
            )
            for row in candidate["per_cell_cumulative_pseudo_regret"]
        }
        for candidate in selection["candidates"]
    }
    tuning_streams = {seed: set() for seed in tuning_seeds}
    tuning_run_count = 0
    for cell in cells(config):
        for method in METHODS:
            for ridge, bonus in hyperparameter_grid(config, method):
                candidate = candidate_rows[(method, ridge, bonus)]
                for seed in tuning_seeds:
                    setting = f"ridge-{ridge:g}_bonus-{bonus:g}"
                    directory = (
                        profile_root
                        / "tuning"
                        / cell.token
                        / method
                        / setting
                        / f"seed-{seed}"
                    )
                    summary = _validate_wheel_run_source(
                        directory,
                        config=config,
                        profile=profile,
                        phase="tuning",
                        method=method,
                        cell=cell,
                        seed=seed,
                        ridge=ridge,
                        bonus=bonus,
                        selection_payload_sha256=None,
                    )
                    if not math.isclose(
                        float(summary["cumulative_pseudo_regret"]),
                        candidate[(cell.delta, seed)],
                        rel_tol=0.0,
                        abs_tol=1.0e-12,
                    ):
                        raise RawArtifactBundleError(
                            f"Wheel tuning selection/raw mismatch for {directory}"
                        )
                    tuning_streams[seed].add(str(summary["environment_stream_sha256"]))
                    expected_paths.update(
                        directory / name
                        for name in ("manifest.jsonl", "raw.jsonl", "summary.jsonl")
                    )
                    tuning_run_count += 1
    if any(len(digests) != 1 for digests in tuning_streams.values()):
        raise RawArtifactBundleError("Wheel tuning runs do not share streams by seed")

    evaluation_streams = {seed: set() for seed in evaluation_seeds}
    evaluation_run_count = 0
    for cell in cells(config):
        for method in METHODS:
            ridge, bonus = selected[method]
            for seed in evaluation_seeds:
                directory = (
                    profile_root / "evaluation" / cell.token / method / f"seed-{seed}"
                )
                summary = _validate_wheel_run_source(
                    directory,
                    config=config,
                    profile=profile,
                    phase="evaluation",
                    method=method,
                    cell=cell,
                    seed=seed,
                    ridge=ridge,
                    bonus=bonus,
                    selection_payload_sha256=selection_payload_sha256,
                )
                evaluation_streams[seed].add(str(summary["environment_stream_sha256"]))
                expected_paths.update(
                    directory / name
                    for name in ("manifest.jsonl", "raw.jsonl", "summary.jsonl")
                )
                evaluation_run_count += 1
    if any(len(digests) != 1 for digests in evaluation_streams.values()):
        raise RawArtifactBundleError(
            "Wheel evaluation runs do not share streams by seed"
        )
    if set(tuning_streams) & set(evaluation_streams):
        raise RawArtifactBundleError("Wheel phase seed identities overlap")
    _validate_exact_tree(profile_root, expected_paths)
    source_hashes = _wheel_source_hashes(Path(__file__).resolve().parents[1])
    selected_settings = {
        method: {"ridge": ridge, "bonus_scale": bonus}
        for method, (ridge, bonus) in selected.items()
    }
    return (
        sorted(expected_paths),
        selection_file_sha256,
        selection_payload_sha256,
        tuning_run_count,
        evaluation_run_count,
        source_hashes,
        selected_settings,
    )


def _source_entries(
    paths: Sequence[Path], *, raw_root: Path, experiment: str
) -> list[SourceEntry]:
    result = []
    root = raw_root.resolve()
    for source in paths:
        resolved = source.resolve()
        try:
            relative = resolved.relative_to(root)
        except ValueError as error:
            raise RawArtifactBundleError(
                f"raw input is outside the declared root: {source}"
            ) from error
        archive_path = (PurePosixPath(experiment) / relative.as_posix()).as_posix()
        result.append(
            SourceEntry(
                source=resolved,
                archive_path=archive_path,
                sha256=sha256_file(resolved),
                size_bytes=resolved.stat().st_size,
                role=_role(resolved, experiment=experiment),
            )
        )
    result.sort(key=lambda item: item.archive_path)
    if len({item.archive_path for item in result}) != len(result):
        raise RawArtifactBundleError("archive paths are not unique")
    return result


def _write_deterministic_tar_gz(
    destination: Path, entries: Sequence[SourceEntry]
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as raw_handle:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                compresslevel=COMPRESSION_LEVEL,
                fileobj=raw_handle,
                mtime=0,
            ) as gzip_handle:
                with tarfile.open(
                    fileobj=gzip_handle,
                    mode="w",
                    format=tarfile.USTAR_FORMAT,
                ) as archive:
                    for entry in entries:
                        information = tarfile.TarInfo(entry.archive_path)
                        information.size = entry.size_bytes
                        information.mode = 0o644
                        information.mtime = 0
                        information.uid = 0
                        information.gid = 0
                        information.uname = ""
                        information.gname = ""
                        with entry.source.open("rb") as source_handle:
                            archive.addfile(information, source_handle)
            raw_handle.flush()
            os.fsync(raw_handle.fileno())
        temporary.chmod(0o644)
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def _outputs(bundle_path: Path, inventory_path: Path) -> tuple[Path, ...]:
    return (
        bundle_path,
        _sidecar(bundle_path),
        inventory_path,
        _sidecar(inventory_path),
    )


def create_scaled_tanh_bundle(
    config: dict[str, Any],
    *,
    config_path: Path,
    profile: str,
    raw_root: Path,
    bundle_path: Path,
    inventory_path: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Validate one scaled-tanh raw chain and write a deterministic bundle."""

    if not bundle_path.name.endswith(".tar.gz"):
        raise RawArtifactBundleError("bundle path must end in .tar.gz")
    inventory = inventory_path or default_inventory_path(bundle_path)
    if len(set(_outputs(bundle_path, inventory))) != 4:
        raise RawArtifactBundleError(
            "bundle and inventory output paths must be distinct"
        )
    profile_root = raw_root / profile
    if _inside(bundle_path, profile_root) or _inside(inventory, profile_root):
        raise RawArtifactBundleError("bundle outputs must be outside the raw profile")
    existing = [path for path in _outputs(bundle_path, inventory) if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "refusing to overwrite bundle outputs: "
            + ", ".join(path.as_posix() for path in existing)
        )
    if load_config(config_path, profile=profile) != config:
        raise RawArtifactBundleError(
            "resolved config does not match the declared config source"
        )

    (
        sources,
        selection_sha256,
        runner_source_sha256,
        validated_runs,
        execution_config,
        config_wording_migration,
    ) = _validated_scaled_tanh_sources(config, profile=profile, raw_root=raw_root)
    entries = _source_entries(
        sources, raw_root=raw_root, experiment=SCALED_TANH_EXPERIMENT
    )
    _write_deterministic_tar_gz(bundle_path, entries)
    archive_sha256 = sha256_file(bundle_path)
    write_sha256_sidecar(bundle_path)
    inventory_entries = [entry.inventory_value() for entry in entries]
    source_set_sha256 = input_set_sha256(inventory_entries)
    inventory_value = {
        "schema_version": SCHEMA_VERSION,
        "bundle_kind": "seed_level_figure_evidence",
        "experiment": EXPERIMENT,
        "profile": profile,
        "evidence_scope": (
            "smoke-only engineering verification; not main-paper evidence"
            if profile == "smoke"
            else "fresh final holdout after two disclosed diagnostic splits"
        ),
        "archive": {
            "filename": bundle_path.name,
            "format": "ustar+gzip",
            "sha256": archive_sha256,
            "size_bytes": bundle_path.stat().st_size,
            "compression_level": COMPRESSION_LEVEL,
            "fixed_member_mtime": 0,
            "fixed_member_mode": "0644",
            "fixed_member_owner": "0:0",
        },
        "raw_root_relative": EXPERIMENT,
        "selection_path_relative": (
            PurePosixPath(EXPERIMENT) / profile / "optimizer_selection.json"
        ).as_posix(),
        "optimizer_selection_sha256": selection_sha256,
        "config_digest": config_digest(config),
        "execution_config_digest": config_digest(execution_config),
        "config_wording_migration": config_wording_migration,
        "config_source": {
            "filename": config_path.name,
            "sha256": sha256_file(config_path),
        },
        "source_artifact_hashes": {
            "experiments/run_scaled_tanh_instantiation.py": runner_source_sha256,
        },
        "resolved_config": config,
        "execution_config": execution_config,
        "tuning_seeds": list(get_seed_set(config, "tuning")),
        "evaluation_seeds": list(get_seed_set(config, "evaluation")),
        "tuning_evaluation_seeds_disjoint": bool(
            set(get_seed_set(config, "tuning")).isdisjoint(
                get_seed_set(config, "evaluation")
            )
        ),
        "expected_run_count": validated_runs,
        "validated_run_count": validated_runs,
        "file_count": len(entries),
        "uncompressed_size_bytes": sum(entry.size_bytes for entry in entries),
        "input_set_sha256": source_set_sha256,
        "entries": inventory_entries,
        "validation": {
            "tuning_selection_sidecar_and_semantics": True,
            "every_expected_manifest_sidecar_and_identity": True,
            "every_summary_and_round_archive_sidecar": True,
            "manifest_summary_and_round_hash_bindings": True,
            "round_archives_readable_without_object_arrays": True,
            "exact_profile_file_set": True,
        },
    }
    write_json_artifact(inventory, inventory_value)
    verified = verify_bundle(bundle_path, inventory_path=inventory)
    return {
        "bundle": bundle_path.as_posix(),
        "bundle_sha256": archive_sha256,
        "inventory": inventory.as_posix(),
        "profile": profile,
        "validated_run_count": validated_runs,
        "file_count": len(entries),
        "uncompressed_size_bytes": inventory_value["uncompressed_size_bytes"],
        "archive_size_bytes": verified["archive_size_bytes"],
        "compression_ratio": verified["compression_ratio"],
    }


def create_wheel_bundle(
    config: dict[str, Any],
    *,
    config_path: Path,
    profile: str,
    raw_root: Path,
    bundle_path: Path,
    inventory_path: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Validate Wheel tuning/evaluation chains and write a deterministic bundle."""

    if not bundle_path.name.endswith(".tar.gz"):
        raise RawArtifactBundleError("bundle path must end in .tar.gz")
    inventory = inventory_path or default_inventory_path(bundle_path)
    if len(set(_outputs(bundle_path, inventory))) != 4:
        raise RawArtifactBundleError(
            "bundle and inventory output paths must be distinct"
        )
    profile_root = raw_root / profile
    if _inside(bundle_path, profile_root) or _inside(inventory, profile_root):
        raise RawArtifactBundleError("bundle outputs must be outside the raw profile")
    existing = [path for path in _outputs(bundle_path, inventory) if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "refusing to overwrite bundle outputs: "
            + ", ".join(path.as_posix() for path in existing)
        )
    if load_config(config_path, profile=profile) != config:
        raise RawArtifactBundleError(
            "resolved config does not match the declared config source"
        )

    (
        sources,
        selection_file_sha256,
        selection_payload_sha256,
        tuning_run_count,
        evaluation_run_count,
        source_hashes,
        selected_settings,
    ) = _validated_wheel_sources(config, profile=profile, raw_root=raw_root)
    entries = _source_entries(
        sources,
        raw_root=raw_root,
        experiment=WHEEL_EXPERIMENT,
    )
    _write_deterministic_tar_gz(bundle_path, entries)
    archive_sha256 = sha256_file(bundle_path)
    write_sha256_sidecar(bundle_path)
    inventory_entries = [entry.inventory_value() for entry in entries]
    total_runs = tuning_run_count + evaluation_run_count
    inventory_value = {
        "schema_version": SCHEMA_VERSION,
        "bundle_kind": "seed_level_figure_evidence",
        "experiment": WHEEL_EXPERIMENT,
        "profile": profile,
        "evidence_scope": (
            "smoke-only engineering verification; not main-paper evidence"
            if profile == "smoke"
            else "prespecified full-profile raw evidence"
        ),
        "archive": {
            "filename": bundle_path.name,
            "format": "ustar+gzip",
            "sha256": archive_sha256,
            "size_bytes": bundle_path.stat().st_size,
            "compression_level": COMPRESSION_LEVEL,
            "fixed_member_mtime": 0,
            "fixed_member_mode": "0644",
            "fixed_member_owner": "0:0",
        },
        "raw_root_relative": WHEEL_EXPERIMENT,
        "selection_path_relative": (
            PurePosixPath(WHEEL_EXPERIMENT) / profile / "tuning_selection.json"
        ).as_posix(),
        "selection_artifact_sha256": selection_file_sha256,
        "selection_payload_sha256": selection_payload_sha256,
        "selected_hyperparameters": selected_settings,
        "config_digest": config_digest(config),
        "config_source": {
            "filename": config_path.name,
            "sha256": sha256_file(config_path),
        },
        "resolved_config": config,
        "source_artifact_hashes": source_hashes,
        "source_binding_scope": (
            "source files are hashed at bundle creation; legacy Wheel JSONL "
            "manifests record git state but do not embed source-file hashes"
        ),
        "tuning_seeds": list(get_seed_set(config, "tuning")),
        "evaluation_seeds": list(get_seed_set(config, "evaluation")),
        "tuning_evaluation_seeds_disjoint": True,
        "expected_tuning_run_count": tuning_run_count,
        "validated_tuning_run_count": tuning_run_count,
        "expected_evaluation_run_count": evaluation_run_count,
        "validated_evaluation_run_count": evaluation_run_count,
        "expected_run_count": total_runs,
        "validated_run_count": total_runs,
        "file_count": len(entries),
        "uncompressed_size_bytes": sum(entry.size_bytes for entry in entries),
        "input_set_sha256": input_set_sha256(inventory_entries),
        "entries": inventory_entries,
        "validation": {
            "tuning_selection_recomputed_from_tuning_only": True,
            "tuning_selection_bound_to_every_tuning_summary": True,
            "evaluation_outcomes_used_for_selection": False,
            "evaluation_manifests_bound_to_selection_hash": True,
            "every_jsonl_manifest_and_trajectory_complete": True,
            "common_stream_per_seed_within_each_phase": True,
            "tuning_evaluation_seed_sets_disjoint": True,
            "exact_profile_file_set": True,
        },
    }
    write_json_artifact(inventory, inventory_value)
    verified = verify_bundle(bundle_path, inventory_path=inventory)
    return {
        "bundle": bundle_path.as_posix(),
        "bundle_sha256": archive_sha256,
        "inventory": inventory.as_posix(),
        "profile": profile,
        "validated_tuning_run_count": tuning_run_count,
        "validated_evaluation_run_count": evaluation_run_count,
        "validated_run_count": total_runs,
        "file_count": len(entries),
        "uncompressed_size_bytes": inventory_value["uncompressed_size_bytes"],
        "archive_size_bytes": verified["archive_size_bytes"],
        "compression_ratio": verified["compression_ratio"],
    }


def _load_inventory(path: Path) -> dict[str, Any]:
    try:
        validate_sha256_sidecar(path)
        value = json.loads(path.read_text(encoding="ascii"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise RawArtifactBundleError(
            f"invalid bundle inventory {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise RawArtifactBundleError("bundle inventory must be a JSON object")
    return value


def _safe_archive_path(value: Any, *, experiment: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise RawArtifactBundleError(f"unsafe archive path {value!r}")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.parts[0] != experiment
    ):
        raise RawArtifactBundleError(f"unsafe archive path {value!r}")
    return value


def _cell_token(horizon: int, width_ratio: float) -> str:
    ratio = format(width_ratio, ".12g").replace(".", "p")
    return f"T-{horizon}_ratio-{ratio}"


def _inventory_entries(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    experiment = value.get("experiment")
    if experiment not in SUPPORTED_EXPERIMENTS:
        raise RawArtifactBundleError("unsupported bundle experiment")
    raw_entries = value.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise RawArtifactBundleError("bundle inventory has no entries")
    entries: list[dict[str, Any]] = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise RawArtifactBundleError("bundle entry must be an object")
        path = _safe_archive_path(raw.get("path"), experiment=str(experiment))
        digest = raw.get("sha256")
        size = raw.get("size_bytes")
        role = raw.get("role")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise RawArtifactBundleError(f"invalid SHA-256 for {path}")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise RawArtifactBundleError(f"invalid size for {path}")
        if not isinstance(role, str) or not role:
            raise RawArtifactBundleError(f"invalid role for {path}")
        entries.append(
            {"path": path, "role": role, "sha256": digest, "size_bytes": size}
        )
    names = [entry["path"] for entry in entries]
    if names != sorted(names) or len(names) != len(set(names)):
        raise RawArtifactBundleError("bundle entries must be sorted and unique")
    if value.get("file_count") != len(entries):
        raise RawArtifactBundleError("bundle file count does not match inventory")
    if value.get("uncompressed_size_bytes") != sum(
        entry["size_bytes"] for entry in entries
    ):
        raise RawArtifactBundleError("bundle byte count does not match inventory")
    if value.get("input_set_sha256") != input_set_sha256(entries):
        raise RawArtifactBundleError("bundle input-set digest does not match inventory")
    return entries


def _validate_scaled_tanh_inventory_contract(
    value: Mapping[str, Any], entries: Sequence[Mapping[str, Any]]
) -> None:
    profile = value.get("profile")
    if profile not in {"smoke", "full"}:
        raise RawArtifactBundleError("bundle profile is invalid")
    resolved_config = value.get("resolved_config")
    if not isinstance(resolved_config, dict):
        raise RawArtifactBundleError("bundle lacks a resolved config")
    if resolved_config.get("profile") != profile:
        raise RawArtifactBundleError("resolved config profile mismatch")
    if value.get("config_digest") != config_digest(resolved_config):
        raise RawArtifactBundleError("resolved config digest mismatch")
    execution_digest = value.get("execution_config_digest")
    if not isinstance(execution_digest, str):
        raise RawArtifactBundleError("bundle lacks an execution config digest")
    try:
        expected_execution_config, expected_migration = resolve_execution_config(
            resolved_config, execution_digest
        )
    except ValueError as error:
        raise RawArtifactBundleError(
            f"bundle config wording migration is invalid: {error}"
        ) from error
    if value.get("execution_config") != expected_execution_config:
        raise RawArtifactBundleError("bundle execution config mismatch")
    if value.get("config_wording_migration") != expected_migration:
        raise RawArtifactBundleError("bundle config wording migration mismatch")
    expected_scope = (
        "smoke-only engineering verification; not main-paper evidence"
        if profile == "smoke"
        else "fresh final holdout after two disclosed diagnostic splits"
    )
    if value.get("evidence_scope") != expected_scope:
        raise RawArtifactBundleError("bundle evidence scope is invalid")
    source_hashes = value.get("source_artifact_hashes")
    if not isinstance(source_hashes, dict) or set(source_hashes) != {
        "experiments/run_scaled_tanh_instantiation.py"
    }:
        raise RawArtifactBundleError("bundle runner source provenance is invalid")
    runner_sha256 = source_hashes["experiments/run_scaled_tanh_instantiation.py"]
    if (
        not isinstance(runner_sha256, str)
        or len(runner_sha256) != 64
        or any(character not in "0123456789abcdef" for character in runner_sha256)
    ):
        raise RawArtifactBundleError("bundle runner source digest is invalid")
    tuning = value.get("tuning_seeds")
    evaluation = value.get("evaluation_seeds")
    if not isinstance(tuning, list) or not isinstance(evaluation, list):
        raise RawArtifactBundleError("bundle seed sets are invalid")
    disjoint = set(tuning).isdisjoint(evaluation)
    if not disjoint or value.get("tuning_evaluation_seeds_disjoint") is not True:
        raise RawArtifactBundleError("bundle tuning/evaluation seeds overlap")
    expected_runs = value.get("expected_run_count")
    validated_runs = value.get("validated_run_count")
    if (
        isinstance(expected_runs, bool)
        or not isinstance(expected_runs, int)
        or expected_runs <= 0
        or validated_runs != expected_runs
    ):
        raise RawArtifactBundleError("bundle run count is incomplete")
    selection_path = (
        PurePosixPath(EXPERIMENT) / str(profile) / "optimizer_selection.json"
    ).as_posix()
    if value.get("raw_root_relative") != EXPERIMENT:
        raise RawArtifactBundleError("bundle raw-root layout is invalid")
    if value.get("selection_path_relative") != selection_path:
        raise RawArtifactBundleError("bundle selection path is invalid")

    by_path = {str(entry["path"]): entry for entry in entries}
    if selection_path not in by_path:
        raise RawArtifactBundleError("bundle omits the optimizer selection")
    if by_path[selection_path]["role"] != "optimizer_selection":
        raise RawArtifactBundleError("optimizer selection role is invalid")
    if by_path[selection_path]["sha256"] != value.get("optimizer_selection_sha256"):
        raise RawArtifactBundleError("optimizer selection digest mismatch")

    try:
        methods = tuple(str(method) for method in resolved_config["methods"])
        horizons = tuple(int(horizon) for horizon in resolved_config["horizons"])
        ratios = tuple(float(ratio) for ratio in resolved_config["width_ratios"])
        seeds = tuple(int(seed) for seed in evaluation)
    except (KeyError, TypeError, ValueError) as error:
        raise RawArtifactBundleError("resolved config grid is invalid") from error
    expected_paths = {selection_path, selection_path + ".sha256"}
    expected_manifests: set[str] = set()
    for horizon in horizons:
        for ratio in ratios:
            token = _cell_token(horizon, ratio)
            for method in methods:
                for seed in seeds:
                    directory = (
                        PurePosixPath(EXPERIMENT)
                        / str(profile)
                        / "evaluation"
                        / token
                        / method
                        / f"seed-{seed}"
                    )
                    for filename in ("manifest.json", "summary.json", "rounds.npz"):
                        primary = (directory / filename).as_posix()
                        expected_paths.update((primary, primary + ".sha256"))
                    expected_manifests.add((directory / "manifest.json").as_posix())
    if set(by_path) != expected_paths:
        missing = sorted(expected_paths - set(by_path))
        extra = sorted(set(by_path) - expected_paths)
        raise RawArtifactBundleError(
            "bundle grid does not match resolved config: "
            f"missing={missing[:5]}, extra={extra[:5]}"
        )
    if expected_runs != len(expected_manifests):
        raise RawArtifactBundleError("resolved grid/run count mismatch")

    manifest_count = 0
    for entry in entries:
        path = str(entry["path"])
        parts = PurePosixPath(path).parts
        expected_role: str
        if path.endswith(".sha256"):
            expected_role = "sha256_sidecar"
            target = path[: -len(".sha256")]
            if target not in by_path:
                raise RawArtifactBundleError(f"orphaned SHA-256 sidecar {path}")
        elif path == selection_path:
            expected_role = "optimizer_selection"
        elif len(parts) == 7 and parts[:3] == (
            EXPERIMENT,
            str(profile),
            "evaluation",
        ):
            if not parts[5].startswith("seed-"):
                raise RawArtifactBundleError(f"invalid seed directory in {path}")
            filename = parts[6]
            expected_role = {
                "manifest.json": "run_manifest",
                "summary.json": "run_summary",
                "rounds.npz": "round_trajectory",
            }.get(filename, "")
            if not expected_role:
                raise RawArtifactBundleError(f"unexpected run artifact {path}")
            if expected_role == "run_manifest":
                manifest_count += 1
        else:
            raise RawArtifactBundleError(f"unexpected bundle layout for {path}")
        if entry["role"] != expected_role:
            raise RawArtifactBundleError(f"bundle role mismatch for {path}")
        if expected_role != "sha256_sidecar" and path + ".sha256" not in by_path:
            raise RawArtifactBundleError(f"bundle omits sidecar for {path}")
    if manifest_count != validated_runs:
        raise RawArtifactBundleError("manifest count does not match validated runs")


def _validate_wheel_inventory_contract(
    value: Mapping[str, Any], entries: Sequence[Mapping[str, Any]]
) -> None:
    from .run_wheel_benchmark import hyperparameter_grid

    profile = value.get("profile")
    if profile not in {"smoke", "full"}:
        raise RawArtifactBundleError("Wheel bundle profile is invalid")
    config = value.get("resolved_config")
    if not isinstance(config, dict) or config.get("profile") != profile:
        raise RawArtifactBundleError("Wheel resolved config is invalid")
    if value.get("config_digest") != config_digest(config):
        raise RawArtifactBundleError("Wheel config digest mismatch")
    source_hashes = value.get("source_artifact_hashes")
    expected_sources = {
        "experiments/run_wheel_benchmark.py",
        "experiments/wheel_environment.py",
        "experiments/logging_utils.py",
        "experiments/make_wheel_benchmark_artifacts.py",
    }
    if not isinstance(source_hashes, dict) or set(source_hashes) != expected_sources:
        raise RawArtifactBundleError("Wheel source provenance is incomplete")
    for name, digest in source_hashes.items():
        _sha256_text(digest, name=name)
    tuning_seeds = value.get("tuning_seeds")
    evaluation_seeds = value.get("evaluation_seeds")
    if not isinstance(tuning_seeds, list) or not isinstance(evaluation_seeds, list):
        raise RawArtifactBundleError("Wheel seed sets are invalid")
    if (
        not set(tuning_seeds).isdisjoint(evaluation_seeds)
        or value.get("tuning_evaluation_seeds_disjoint") is not True
    ):
        raise RawArtifactBundleError("Wheel tuning/evaluation seeds overlap")
    selection_path = (
        PurePosixPath(WHEEL_EXPERIMENT) / str(profile) / "tuning_selection.json"
    ).as_posix()
    if value.get("raw_root_relative") != WHEEL_EXPERIMENT:
        raise RawArtifactBundleError("Wheel raw-root layout is invalid")
    if value.get("selection_path_relative") != selection_path:
        raise RawArtifactBundleError("Wheel selection path is invalid")
    selection_sha256 = _sha256_text(
        value.get("selection_artifact_sha256"), name="Wheel selection artifact"
    )
    _sha256_text(value.get("selection_payload_sha256"), name="Wheel selection payload")

    try:
        methods = tuple(str(method) for method in config["methods"])
        deltas = tuple(float(delta) for delta in config["deltas"])
        tuning = tuple(int(seed) for seed in tuning_seeds)
        evaluation = tuple(int(seed) for seed in evaluation_seeds)
    except (KeyError, TypeError, ValueError) as error:
        raise RawArtifactBundleError("Wheel resolved grid is invalid") from error
    selected_settings = value.get("selected_hyperparameters")
    if not isinstance(selected_settings, dict) or set(selected_settings) != set(
        methods
    ):
        raise RawArtifactBundleError("Wheel selected settings are incomplete")
    for method in methods:
        setting = selected_settings[method]
        if not isinstance(setting, dict):
            raise RawArtifactBundleError("Wheel selected setting is invalid")
        try:
            pair = (float(setting["ridge"]), float(setting["bonus_scale"]))
        except (KeyError, TypeError, ValueError) as error:
            raise RawArtifactBundleError("Wheel selected setting is invalid") from error
        allowed = set(hyperparameter_grid(config, method))
        if pair not in allowed:
            raise RawArtifactBundleError("Wheel selected setting is outside its grid")
    expected_paths = {selection_path}
    tuning_manifests: set[str] = set()
    evaluation_manifests: set[str] = set()
    for delta in deltas:
        token = f"delta-{format(delta, '.12g').replace('.', 'p')}"
        for method in methods:
            settings = hyperparameter_grid(config, method)
            for ridge, bonus in settings:
                setting = f"ridge-{ridge:g}_bonus-{bonus:g}"
                for seed in tuning:
                    directory = (
                        PurePosixPath(WHEEL_EXPERIMENT)
                        / str(profile)
                        / "tuning"
                        / token
                        / method
                        / setting
                        / f"seed-{seed}"
                    )
                    for filename in ("manifest.jsonl", "raw.jsonl", "summary.jsonl"):
                        expected_paths.add((directory / filename).as_posix())
                    tuning_manifests.add((directory / "manifest.jsonl").as_posix())
            for seed in evaluation:
                directory = (
                    PurePosixPath(WHEEL_EXPERIMENT)
                    / str(profile)
                    / "evaluation"
                    / token
                    / method
                    / f"seed-{seed}"
                )
                for filename in ("manifest.jsonl", "raw.jsonl", "summary.jsonl"):
                    expected_paths.add((directory / filename).as_posix())
                evaluation_manifests.add((directory / "manifest.jsonl").as_posix())

    entries_by_path = {str(entry["path"]): entry for entry in entries}
    if set(entries_by_path) != expected_paths:
        missing = sorted(expected_paths - set(entries_by_path))
        extra = sorted(set(entries_by_path) - expected_paths)
        raise RawArtifactBundleError(
            "Wheel bundle grid mismatch: " f"missing={missing[:5]}, extra={extra[:5]}"
        )
    if entries_by_path[selection_path]["role"] != "wheel_tuning_selection":
        raise RawArtifactBundleError("Wheel selection role mismatch")
    if entries_by_path[selection_path]["sha256"] != selection_sha256:
        raise RawArtifactBundleError("Wheel selection file digest mismatch")
    expected_tuning = len(tuning_manifests)
    expected_evaluation = len(evaluation_manifests)
    count_fields = {
        "expected_tuning_run_count": expected_tuning,
        "validated_tuning_run_count": expected_tuning,
        "expected_evaluation_run_count": expected_evaluation,
        "validated_evaluation_run_count": expected_evaluation,
        "expected_run_count": expected_tuning + expected_evaluation,
        "validated_run_count": expected_tuning + expected_evaluation,
    }
    if any(value.get(key) != expected for key, expected in count_fields.items()):
        raise RawArtifactBundleError("Wheel bundle run counts are incomplete")
    for path, entry in entries_by_path.items():
        if path == selection_path:
            expected_role = "wheel_tuning_selection"
        elif "/tuning/" in path:
            expected_role = {
                "manifest.jsonl": "wheel_tuning_manifest",
                "raw.jsonl": "wheel_tuning_raw",
                "summary.jsonl": "wheel_tuning_summary",
            }[PurePosixPath(path).name]
        else:
            expected_role = {
                "manifest.jsonl": "wheel_evaluation_manifest",
                "raw.jsonl": "wheel_evaluation_raw",
                "summary.jsonl": "wheel_evaluation_summary",
            }[PurePosixPath(path).name]
        if entry["role"] != expected_role:
            raise RawArtifactBundleError(f"Wheel bundle role mismatch for {path}")


def _validate_inventory_contract(
    value: Mapping[str, Any], entries: Sequence[Mapping[str, Any]]
) -> None:
    experiment = value.get("experiment")
    if experiment == SCALED_TANH_EXPERIMENT:
        _validate_scaled_tanh_inventory_contract(value, entries)
        return
    if experiment == WHEEL_EXPERIMENT:
        _validate_wheel_inventory_contract(value, entries)
        return
    raise RawArtifactBundleError("unsupported bundle experiment")


def _stream_sha256(handle: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _validate_gzip_header(path: Path) -> None:
    with path.open("rb") as handle:
        header = handle.read(10)
    if len(header) != 10 or header[:3] != b"\x1f\x8b\x08":
        raise RawArtifactBundleError("bundle is not a gzip stream")
    if header[3] != 0 or header[4:8] != b"\x00\x00\x00\x00":
        raise RawArtifactBundleError("gzip header contains variable metadata")


def _validate_member(member: tarfile.TarInfo, expected: Mapping[str, Any]) -> None:
    if not member.isreg():
        raise RawArtifactBundleError(f"non-regular archive member {member.name}")
    if member.name != expected["path"] or member.size != expected["size_bytes"]:
        raise RawArtifactBundleError(f"archive member mismatch for {member.name}")
    if (
        member.mode != 0o644
        or member.mtime != 0
        or member.uid != 0
        or member.gid != 0
        or member.uname != ""
        or member.gname != ""
        or member.linkname != ""
        or member.pax_headers
    ):
        raise RawArtifactBundleError(f"non-deterministic metadata for {member.name}")


def _json_object(payload: bytes, *, path: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RawArtifactBundleError(f"invalid JSON payload {path}: {error}") from error
    if not isinstance(value, dict):
        raise RawArtifactBundleError(f"JSON payload is not an object: {path}")
    return value


def _validate_selection_payload(
    payload: bytes,
    *,
    entry: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> None:
    value = _json_object(payload, path=str(entry["path"]))
    config = inventory["execution_config"]
    expected = {
        "schema_version": 1,
        "event": "scaled_tanh_optimizer_selection",
        "profile": inventory["profile"],
        "config_digest": inventory["execution_config_digest"],
        "tuning_seeds": inventory["tuning_seeds"],
        "evaluation_seeds": inventory["evaluation_seeds"],
        "evaluation_metrics_read": False,
        "selected_damping": float(config["damping"]),
        "selected_optimizer_zeta0": float(config["optimizer_zeta0"]),
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise RawArtifactBundleError(f"optimizer selection mismatch for {key}")
    if (
        not isinstance(value.get("candidate_results"), list)
        or not value["candidate_results"]
    ):
        raise RawArtifactBundleError("optimizer selection has no candidate results")
    if not isinstance(value.get("provenance"), dict):
        raise RawArtifactBundleError("optimizer selection provenance is invalid")
    if (
        value["provenance"].get("source_artifact_hashes")
        != inventory["source_artifact_hashes"]
    ):
        raise RawArtifactBundleError("optimizer selection source provenance mismatch")
    if value.get("criterion") != config["optimizer_selection"]["criterion"]:
        raise RawArtifactBundleError("optimizer selection criterion mismatch")
    if value.get("protocol_amendment") != config["protocol_amendment"]:
        raise RawArtifactBundleError("optimizer selection amendment mismatch")
    expected_cells = [
        (int(horizon), float(ratio))
        for horizon in config["optimizer_selection"]["horizons"]
        for ratio in config["optimizer_selection"]["width_ratios"]
    ]
    raw_cells = value.get("selection_cells")
    if not isinstance(raw_cells, list):
        raise RawArtifactBundleError("optimizer selection cells are invalid")
    try:
        actual_cells = [
            (int(cell["horizon"]), float(cell["width_ratio"])) for cell in raw_cells
        ]
    except (KeyError, TypeError, ValueError) as error:
        raise RawArtifactBundleError("optimizer selection cells are invalid") from error
    if actual_cells != expected_cells:
        raise RawArtifactBundleError("optimizer selection cells mismatch")

    records = value["candidate_results"]
    expected_dampings = [
        float(candidate)
        for candidate in config["optimizer_selection"]["damping_candidates"]
    ]
    try:
        actual_dampings = [float(record["damping"]) for record in records]
        for record in records:
            failure_count = int(record["optimizer_failure_count"])
            runs = record["runs"]
            if failure_count < 0 or not isinstance(runs, list):
                raise ValueError
            if int(record["run_count"]) != len(runs):
                raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise RawArtifactBundleError(
            "optimizer candidate records are invalid"
        ) from error
    if actual_dampings != expected_dampings:
        raise RawArtifactBundleError("optimizer damping candidates mismatch")
    zero_failure = [
        record for record in records if int(record["optimizer_failure_count"]) == 0
    ]
    pool = zero_failure if zero_failure else records
    winner = min(
        pool,
        key=lambda record: (
            int(record["optimizer_failure_count"]),
            float(record["damping"]),
        ),
    )
    if float(winner["damping"]) != float(value["selected_damping"]):
        raise RawArtifactBundleError("optimizer selection winner mismatch")


def _validate_manifest_payload(
    payload: bytes,
    *,
    entry: Mapping[str, Any],
    inventory: Mapping[str, Any],
    entries_by_path: Mapping[str, Mapping[str, Any]],
) -> None:
    path = str(entry["path"])
    parts = PurePosixPath(path).parts
    value = _json_object(payload, path=path)
    seed_text = parts[5]
    try:
        seed = int(seed_text.removeprefix("seed-"))
    except ValueError as error:
        raise RawArtifactBundleError(f"invalid seed path {path}") from error
    cell = value.get("cell")
    if not isinstance(cell, dict):
        raise RawArtifactBundleError(f"manifest cell is invalid in {path}")
    try:
        cell_token = _cell_token(int(cell["horizon"]), float(cell["width_ratio"]))
    except (KeyError, TypeError, ValueError) as error:
        raise RawArtifactBundleError(f"manifest cell is invalid in {path}") from error
    config = inventory["execution_config"]
    expected = {
        "schema_version": 1,
        "experiment": EXPERIMENT,
        "profile": inventory["profile"],
        "phase": "evaluation",
        "seed": seed,
        "method": parts[4],
        "config": config,
        "config_digest": inventory["execution_config_digest"],
        "optimizer_selection_sha256": inventory["optimizer_selection_sha256"],
        "evaluation_data_used_for_selection": False,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise RawArtifactBundleError(f"manifest mismatch for {key} in {path}")
    if parts[3] != cell_token:
        raise RawArtifactBundleError(f"manifest cell/path mismatch in {path}")
    if not isinstance(value.get("provenance"), dict):
        raise RawArtifactBundleError(f"manifest provenance is invalid in {path}")
    if (
        value["provenance"].get("source_artifact_hashes")
        != inventory["source_artifact_hashes"]
    ):
        raise RawArtifactBundleError(f"manifest source provenance mismatch in {path}")
    directory = PurePosixPath(path).parent.as_posix()
    for key, filename in (
        ("rounds_sha256", "rounds.npz"),
        ("summary_sha256", "summary.json"),
    ):
        target = f"{directory}/{filename}"
        if (
            target not in entries_by_path
            or value.get(key) != entries_by_path[target]["sha256"]
        ):
            raise RawArtifactBundleError(f"manifest payload hash mismatch for {target}")


def _validate_sidecar_payload(
    payload: bytes,
    *,
    entry: Mapping[str, Any],
    entries_by_path: Mapping[str, Mapping[str, Any]],
) -> None:
    path = str(entry["path"])
    target = path[: -len(".sha256")]
    target_entry = entries_by_path[target]
    expected = f"{target_entry['sha256']}  {PurePosixPath(target).name}\n".encode(
        "ascii"
    )
    if payload != expected:
        raise RawArtifactBundleError(f"invalid embedded SHA-256 sidecar {path}")


def _validate_wheel_selection_payload(
    payload: bytes,
    *,
    entry: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> None:
    from .run_wheel_benchmark import validate_tuning_selection

    value = _json_object(payload, path=str(entry["path"]))
    if (
        hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()
        != inventory["selection_payload_sha256"]
    ):
        raise RawArtifactBundleError("Wheel selection canonical digest mismatch")
    try:
        selected = validate_tuning_selection(inventory["resolved_config"], value)
    except (TypeError, ValueError) as error:
        raise RawArtifactBundleError(
            f"Wheel tuning selection is invalid: {error}"
        ) from error
    if value.get("evaluation_outcomes_used") is not False:
        raise RawArtifactBundleError("Wheel selection used evaluation outcomes")
    expected_settings = inventory["selected_hyperparameters"]
    actual_settings = {
        method: {"ridge": ridge, "bonus_scale": bonus}
        for method, (ridge, bonus) in selected.items()
    }
    if actual_settings != expected_settings:
        raise RawArtifactBundleError("Wheel selected settings mismatch inventory")


def _validate_wheel_manifest_payload(
    payload: bytes,
    *,
    entry: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> None:
    path = str(entry["path"])
    parts = PurePosixPath(path).parts
    value = _json_object(payload, path=path)
    phase = "tuning" if entry["role"] == "wheel_tuning_manifest" else "evaluation"
    expected_parts = 8 if phase == "tuning" else 7
    if len(parts) != expected_parts or parts[:3] != (
        WHEEL_EXPERIMENT,
        str(inventory["profile"]),
        phase,
    ):
        raise RawArtifactBundleError(f"Wheel manifest path is invalid: {path}")
    token = parts[3]
    method = parts[4]
    seed_part = parts[6] if phase == "tuning" else parts[5]
    try:
        seed = int(seed_part.removeprefix("seed-"))
    except ValueError as error:
        raise RawArtifactBundleError(
            f"Wheel manifest seed path is invalid: {path}"
        ) from error
    run_config = value.get("config")
    if not isinstance(run_config, dict):
        raise RawArtifactBundleError(f"Wheel manifest config is invalid: {path}")
    execution = run_config.get("execution")
    base_config = {key: item for key, item in run_config.items() if key != "execution"}
    if base_config != inventory["resolved_config"] or not isinstance(execution, dict):
        raise RawArtifactBundleError(f"Wheel manifest base config mismatch: {path}")
    if (
        value.get("schema_version") != 1
        or value.get("event") != "run_manifest"
        or value.get("seed") != seed
        or value.get("config_digest") != config_digest(run_config)
        or execution.get("seed_set") != phase
        or execution.get("method") != method
        or execution.get("cell", {}).get("token") != token
        or execution.get("executed_policy") is not True
    ):
        raise RawArtifactBundleError(f"Wheel manifest identity mismatch: {path}")
    hyperparameters = execution.get("hyperparameters")
    if not isinstance(hyperparameters, dict):
        raise RawArtifactBundleError(f"Wheel manifest hyperparameters invalid: {path}")
    try:
        ridge = float(hyperparameters["ridge"])
        bonus = float(hyperparameters["bonus_scale"])
    except (KeyError, TypeError, ValueError) as error:
        raise RawArtifactBundleError(
            f"Wheel manifest hyperparameters invalid: {path}"
        ) from error
    if phase == "tuning":
        setting = parts[5]
        if setting != f"ridge-{ridge:g}_bonus-{bonus:g}":
            raise RawArtifactBundleError(f"Wheel tuning setting path mismatch: {path}")
    else:
        if hyperparameters != inventory["selected_hyperparameters"].get(method):
            raise RawArtifactBundleError(
                f"Wheel evaluation setting was not tuning-selected: {path}"
            )
        if (
            execution.get("tuning_selection_sha256")
            != inventory["selection_payload_sha256"]
            or execution.get("pooled_over_all_declared_deltas") is not True
            or execution.get("evaluation_rerun_from_scratch") is not True
            or execution.get("evaluation_outcomes_used_for_tuning") is not False
        ):
            raise RawArtifactBundleError(
                f"Wheel evaluation selection provenance mismatch: {path}"
            )


def verify_bundle(
    bundle_path: Path, *, inventory_path: Path | None = None
) -> dict[str, Any]:
    """Verify external hashes, inventory, tar metadata, and every member payload."""

    inventory = inventory_path or default_inventory_path(bundle_path)
    try:
        validate_sha256_sidecar(bundle_path)
    except (OSError, ValueError) as error:
        raise RawArtifactBundleError(
            f"invalid bundle SHA-256 sidecar for {bundle_path}: {error}"
        ) from error
    value = _load_inventory(inventory)
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("bundle_kind") != "seed_level_figure_evidence"
        or value.get("experiment") not in SUPPORTED_EXPERIMENTS
    ):
        raise RawArtifactBundleError("unsupported bundle inventory schema")
    experiment = str(value["experiment"])
    archive_record = value.get("archive")
    if not isinstance(archive_record, dict):
        raise RawArtifactBundleError("bundle inventory lacks archive metadata")
    if archive_record.get("filename") != bundle_path.name:
        raise RawArtifactBundleError("bundle filename does not match inventory")
    if archive_record.get("format") != "ustar+gzip":
        raise RawArtifactBundleError("unsupported bundle archive format")
    fixed_archive_fields = {
        "compression_level": COMPRESSION_LEVEL,
        "fixed_member_mtime": 0,
        "fixed_member_mode": "0644",
        "fixed_member_owner": "0:0",
    }
    if any(
        archive_record.get(key) != expected
        for key, expected in fixed_archive_fields.items()
    ):
        raise RawArtifactBundleError("bundle deterministic metadata contract mismatch")
    actual_sha256 = sha256_file(bundle_path)
    if archive_record.get("sha256") != actual_sha256:
        raise RawArtifactBundleError("bundle digest does not match inventory")
    if archive_record.get("size_bytes") != bundle_path.stat().st_size:
        raise RawArtifactBundleError("bundle size does not match inventory")
    entries = _inventory_entries(value)
    _validate_inventory_contract(value, entries)
    entries_by_path = {str(entry["path"]): entry for entry in entries}
    _validate_gzip_header(bundle_path)
    try:
        with tarfile.open(bundle_path, mode="r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            expected_names = [entry["path"] for entry in entries]
            if names != expected_names:
                raise RawArtifactBundleError(
                    "archive members do not match the ordered inventory"
                )
            for member, entry in zip(members, entries, strict=True):
                _safe_archive_path(member.name, experiment=experiment)
                _validate_member(member, entry)
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise RawArtifactBundleError(f"cannot read {member.name}")
                with extracted:
                    if entry["role"] in {
                        "sha256_sidecar",
                        "optimizer_selection",
                        "run_manifest",
                        "wheel_tuning_selection",
                        "wheel_tuning_manifest",
                        "wheel_evaluation_manifest",
                    }:
                        payload = extracted.read()
                        digest = hashlib.sha256(payload).hexdigest()
                    else:
                        payload = None
                        digest = _stream_sha256(extracted)
                if digest != entry["sha256"]:
                    raise RawArtifactBundleError(
                        f"archive payload digest mismatch for {member.name}"
                    )
                if entry["role"] == "sha256_sidecar":
                    assert payload is not None
                    _validate_sidecar_payload(
                        payload,
                        entry=entry,
                        entries_by_path=entries_by_path,
                    )
                elif entry["role"] == "optimizer_selection":
                    assert payload is not None
                    _validate_selection_payload(
                        payload,
                        entry=entry,
                        inventory=value,
                    )
                elif entry["role"] == "run_manifest":
                    assert payload is not None
                    _validate_manifest_payload(
                        payload,
                        entry=entry,
                        inventory=value,
                        entries_by_path=entries_by_path,
                    )
                elif entry["role"] == "wheel_tuning_selection":
                    assert payload is not None
                    _validate_wheel_selection_payload(
                        payload,
                        entry=entry,
                        inventory=value,
                    )
                elif entry["role"] in {
                    "wheel_tuning_manifest",
                    "wheel_evaluation_manifest",
                }:
                    assert payload is not None
                    _validate_wheel_manifest_payload(
                        payload,
                        entry=entry,
                        inventory=value,
                    )
    except (OSError, tarfile.TarError, EOFError) as error:
        raise RawArtifactBundleError(
            f"cannot read bundle {bundle_path}: {error}"
        ) from error
    uncompressed = int(value["uncompressed_size_bytes"])
    archive_size = bundle_path.stat().st_size
    return {
        "status": "verified",
        "bundle": bundle_path.as_posix(),
        "inventory": inventory.as_posix(),
        "archive_sha256": actual_sha256,
        "archive_size_bytes": archive_size,
        "uncompressed_size_bytes": uncompressed,
        "compression_ratio": archive_size / uncompressed if uncompressed else 0.0,
        "file_count": len(entries),
        "validated_run_count": value.get("validated_run_count"),
        "profile": value.get("profile"),
    }


def _copy_member(
    archive: tarfile.TarFile,
    member: tarfile.TarInfo,
    destination: Path,
    expected_sha256: str,
) -> None:
    source = archive.extractfile(member)
    if source is None:
        raise RawArtifactBundleError(f"cannot extract {member.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with source, destination.open("xb") as output:
        for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
            output.write(chunk)
            digest.update(chunk)
        output.flush()
        os.fsync(output.fileno())
    destination.chmod(0o644)
    os.utime(destination, (0, 0))
    if digest.hexdigest() != expected_sha256:
        raise RawArtifactBundleError(f"extracted digest mismatch for {member.name}")


def extract_bundle(
    bundle_path: Path,
    *,
    destination: Path,
    inventory_path: Path | None = None,
) -> dict[str, Any]:
    """Verify and atomically extract a bundle into a new destination directory."""

    inventory = inventory_path or default_inventory_path(bundle_path)
    verification = verify_bundle(bundle_path, inventory_path=inventory)
    value = _load_inventory(inventory)
    entries = _inventory_entries(value)
    experiment = str(value["experiment"])
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"refusing to overwrite extraction root {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
    )
    try:
        with tarfile.open(bundle_path, mode="r:gz") as archive:
            members = archive.getmembers()
            for member, entry in zip(members, entries, strict=True):
                _validate_member(member, entry)
                relative = PurePosixPath(
                    _safe_archive_path(member.name, experiment=experiment)
                )
                target = staging.joinpath(*relative.parts)
                _copy_member(archive, member, target, entry["sha256"])
        os.replace(staging, destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    raw_root = destination / str(value["raw_root_relative"])
    selection = destination.joinpath(
        *PurePosixPath(str(value["selection_path_relative"])).parts
    )
    return {
        **verification,
        "status": "extracted",
        "destination": destination.as_posix(),
        "raw_root": raw_root.as_posix(),
        "selection": selection.as_posix(),
        "extracted_file_count": len(entries),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser(
        "create", help="validate and bundle scaled-tanh raw data"
    )
    create.add_argument("--config", type=Path, required=True)
    create.add_argument("--profile", choices=("smoke", "full"), required=True)
    create.add_argument("--raw-root", type=Path, required=True)
    create.add_argument("--bundle", type=Path, required=True)
    create.add_argument("--inventory", type=Path)
    create.add_argument("--overwrite", action="store_true")

    wheel = subparsers.add_parser(
        "create-wheel", help="validate and bundle Wheel tuning/evaluation raw data"
    )
    wheel.add_argument("--config", type=Path, required=True)
    wheel.add_argument("--profile", choices=("smoke", "full"), required=True)
    wheel.add_argument("--raw-root", type=Path, required=True)
    wheel.add_argument("--bundle", type=Path, required=True)
    wheel.add_argument("--inventory", type=Path)
    wheel.add_argument("--overwrite", action="store_true")

    verify = subparsers.add_parser("verify", help="verify a bundle and inventory")
    verify.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--inventory", type=Path)

    extract = subparsers.add_parser(
        "extract", help="verify and safely extract a bundle"
    )
    extract.add_argument("--bundle", type=Path, required=True)
    extract.add_argument("--inventory", type=Path)
    extract.add_argument("--destination", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "create":
        config = load_config(args.config, profile=args.profile)
        result = create_scaled_tanh_bundle(
            config,
            config_path=args.config,
            profile=args.profile,
            raw_root=args.raw_root,
            bundle_path=args.bundle,
            inventory_path=args.inventory,
            overwrite=args.overwrite,
        )
    elif args.command == "create-wheel":
        config = load_config(args.config, profile=args.profile)
        result = create_wheel_bundle(
            config,
            config_path=args.config,
            profile=args.profile,
            raw_root=args.raw_root,
            bundle_path=args.bundle,
            inventory_path=args.inventory,
            overwrite=args.overwrite,
        )
    elif args.command == "verify":
        result = verify_bundle(args.bundle, inventory_path=args.inventory)
    else:
        result = extract_bundle(
            args.bundle,
            destination=args.destination,
            inventory_path=args.inventory,
        )
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "RawArtifactBundleError",
    "create_scaled_tanh_bundle",
    "create_wheel_bundle",
    "default_inventory_path",
    "extract_bundle",
    "verify_bundle",
]
