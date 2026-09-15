"""Git-backed trust boundaries for realistic-transport evidence.

Prepared-data manifests describe candidate bytes.  They never authorize a
Covertype run.  Authorization comes from a data-lock file committed in the
explicit freeze revision, and evaluation additionally requires a selection
artifact committed unchanged in a later selection-only revision.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .configuration import APPROXIMATE_METHODS, canonical_json, EXPECTED_TASKS
from .data import load_prepared_dataset, PreparedDataset
from .provenance import (
    ALLOWED_SCIENTIFIC_SYMLINKS,
    input_set_sha256,
    is_scientific_path,
    NONSCIENTIFIC_OUTPUT_PREFIXES,
    REPOSITORY_ROOT,
    scientific_files,
    sha256_bytes,
    sha256_file,
    sha256_source_path,
    source_path_mode,
)


DATA_LOCK_SCHEMA = "realistic-transport-approved-data-lock-v1"
SELECTION_SCHEMA = "realistic-transport-selection-v2"
_FULL_SHA256 = re.compile(r"[0-9a-f]{64}")
_FULL_GIT_SHA = re.compile(r"[0-9a-f]{40}")


class IntegrityError(RuntimeError):
    """Raised when an evidence trust boundary cannot be established."""


def _git(repo_root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repo_root,
            input=input_bytes,
            check=True,
            capture_output=True,
            timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError) as error:
        detail = getattr(error, "stderr", b"")
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="replace").strip()
        raise IntegrityError(
            f"git {' '.join(args)} failed: {detail or error}"
        ) from error


def _full_commit(repo_root: Path, revision: str, *, name: str) -> str:
    if not isinstance(revision, str) or _FULL_GIT_SHA.fullmatch(revision) is None:
        raise IntegrityError(f"{name} must be a full 40-character Git commit SHA")
    resolved = _git(repo_root, "rev-parse", "--verify", f"{revision}^{{commit}}")
    result = resolved.decode("ascii").strip()
    if result != revision:
        raise IntegrityError(f"{name} does not resolve to the exact supplied commit")
    return result


def _repo_relative(path: str | Path, repo_root: Path, *, name: str) -> str:
    candidate = Path(path).resolve()
    try:
        relative = candidate.relative_to(repo_root.resolve())
    except ValueError as error:
        raise IntegrityError(f"{name} must be inside the repository") from error
    return relative.as_posix()


def _scientific_pathspecs() -> tuple[str, ...]:
    """Scan all worktree entries; the central predicate decides membership."""

    root_entries = (":(top,glob)*",)
    recursive_entries = (":(top,glob)**/*",)
    output_exclusions = tuple(
        f":(top,exclude,glob){prefix}**" for prefix in NONSCIENTIFIC_OUTPUT_PREFIXES
    )
    return tuple(
        sorted(
            (
                *root_entries,
                *recursive_entries,
                *output_exclusions,
            )
        )
    )


def _is_relevant_worktree_path(repo_root: Path, path: str) -> bool:
    candidate = repo_root / path
    path_is_symlink = candidate.is_symlink()
    if not path_is_symlink:
        staged = _git(repo_root, "ls-files", "--stage", "--", path)
        path_is_symlink = staged.startswith(b"120000 ")
    return is_scientific_path(path, is_symlink=path_is_symlink)


def _git_tree_paths(repo_root: Path, revision: str) -> tuple[tuple[str, str], ...]:
    raw = _git(repo_root, "ls-tree", "-r", "-z", revision)
    paths: list[tuple[str, str]] = []
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, path_bytes = entry.split(b"\t", 1)
        mode = metadata.split(b" ", 1)[0].decode("ascii")
        path = path_bytes.decode("utf-8")
        if is_scientific_path(path, is_symlink=mode == "120000"):
            paths.append((path, mode))
    return tuple(paths)


def _untracked_scientific_paths(repo_root: Path) -> set[str]:
    paths: set[str] = set()
    for ignored in (False, True):
        arguments = ["ls-files", "--others", "-z"]
        if ignored:
            arguments.extend(("--ignored", "--exclude-standard"))
        else:
            arguments.append("--exclude-standard")
        raw = _git(repo_root, *arguments)
        for path in raw.decode("utf-8", errors="replace").split("\0"):
            if path and _is_relevant_worktree_path(repo_root, path):
                paths.add(path)
    return paths


def source_inventory_at_revision(
    revision: str, *, repo_root: str | Path = REPOSITORY_ROOT
) -> list[dict[str, str]]:
    """Hash the authoritative scientific files directly from Git objects."""

    root = Path(repo_root).resolve()
    commit = _full_commit(root, revision, name="freeze_revision")
    inventory: list[dict[str, str]] = []
    for path, mode in sorted(_git_tree_paths(root, commit)):
        if mode not in {"100644", "100755", "120000"}:
            raise IntegrityError(
                f"scientific source has unsupported Git mode {mode}: {path}"
            )
        if mode == "120000" and path not in ALLOWED_SCIENTIFIC_SYMLINKS:
            raise IntegrityError(
                f"unsafe scientific symlink is not allowlisted: {path}"
            )
        payload = _git(root, "show", f"{commit}:{path}")
        inventory.append({"path": path, "sha256": sha256_bytes(payload), "mode": mode})
    if not inventory:
        raise IntegrityError("freeze revision has no realistic scientific sources")
    return inventory


def current_source_inventory(
    *, repo_root: str | Path = REPOSITORY_ROOT
) -> list[dict[str, str]]:
    """Hash the current scientific bytes without deriving authority from them."""

    root = Path(repo_root).resolve()
    inventory: list[dict[str, str]] = []
    for path in scientific_files(root):
        relative = path.relative_to(root).as_posix()
        try:
            mode = source_path_mode(path)
        except (OSError, ValueError) as error:
            raise IntegrityError(str(error)) from error
        if mode == "120000" and relative not in ALLOWED_SCIENTIFIC_SYMLINKS:
            raise IntegrityError(
                f"unsafe scientific symlink is not allowlisted: {relative}"
            )
        inventory.append(
            {
                "path": relative,
                "sha256": sha256_source_path(path),
                "mode": mode,
            }
        )
    return inventory


def verify_clean_freeze(
    freeze_revision: str,
    *,
    repo_root: str | Path = REPOSITORY_ROOT,
    require_head: bool,
) -> list[dict[str, str]]:
    """Verify current scientific bytes against an immutable Git revision."""

    root = Path(repo_root).resolve()
    commit = _full_commit(root, freeze_revision, name="freeze_revision")
    head = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    if require_head and head != commit:
        raise IntegrityError(f"HEAD {head} differs from freeze revision {commit}")
    expected = source_inventory_at_revision(commit, repo_root=root)
    expected_by_path = {
        item["path"]: (item["sha256"], item["mode"]) for item in expected
    }
    actual = current_source_inventory(repo_root=root)
    actual_by_path = {item["path"]: (item["sha256"], item["mode"]) for item in actual}
    if actual_by_path != expected_by_path:
        missing = sorted(set(expected_by_path) - set(actual_by_path))
        added = sorted(set(actual_by_path) - set(expected_by_path))
        changed = sorted(
            path
            for path in set(expected_by_path) & set(actual_by_path)
            if expected_by_path[path] != actual_by_path[path]
        )
        raise IntegrityError(
            "scientific sources differ from freeze: "
            f"missing={missing}, added={added}, changed={changed}"
        )

    status = _git(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignored=matching",
        "--",
        *_scientific_pathspecs(),
    ).decode("utf-8", errors="replace")
    dirty: list[str] = []
    fields = [field for field in status.split("\0") if field]
    index = 0
    while index < len(fields):
        entry = fields[index]
        code = entry[:2]
        path = entry[3:]
        if code[0] in {"R", "C"} and index + 1 < len(fields):
            index += 1
        if _is_relevant_worktree_path(root, path):
            dirty.append(f"{code} {path}")
        index += 1
    if dirty:
        raise IntegrityError(f"scientific working tree is dirty: {dirty}")
    untracked_scientific = sorted(_untracked_scientific_paths(root))
    if untracked_scientific:
        raise IntegrityError(
            "untracked scientific source exists outside explicit output paths: "
            f"{untracked_scientific}"
        )
    return expected


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IntegrityError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _strict_json(path: Path, *, description: str) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                IntegrityError(f"non-finite JSON value {value}")
            ),
        )
    except (OSError, json.JSONDecodeError, IntegrityError) as error:
        raise IntegrityError(f"cannot read {description}: {error}") from error
    if not isinstance(value, dict):
        raise IntegrityError(f"{description} must be a JSON object")
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def authenticate_prepared_data(
    *,
    config: Mapping[str, Any],
    config_path: str | Path,
    prepared_artifact: str | Path,
    data_lock_path: str | Path | None,
    freeze_revision: str | None,
    repo_root: str | Path = REPOSITORY_ROOT,
) -> tuple[PreparedDataset, dict[str, Any]]:
    """Load Covertype only after validating a lock committed at the freeze."""

    dataset = config.get("dataset")
    if not isinstance(dataset, Mapping):
        raise IntegrityError("configuration lacks dataset policy")
    approved = dataset.get("approved_data_lock")
    required_digest = dataset.get("required_semantic_digest")
    if not isinstance(approved, Mapping) or not approved:
        raise IntegrityError("Covertype execution requires an approved data lock")
    if (
        not isinstance(required_digest, str)
        or _FULL_SHA256.fullmatch(required_digest) is None
    ):
        raise IntegrityError("approved Covertype semantic digest is null or invalid")
    if data_lock_path is None:
        raise IntegrityError("Covertype execution requires --data-lock")
    if freeze_revision is None:
        raise IntegrityError("Covertype execution requires --freeze-revision")

    root = Path(repo_root).resolve()
    commit = _full_commit(root, freeze_revision, name="freeze_revision")
    configured_path = approved.get("path")
    configured_sha = approved.get("sha256")
    if not isinstance(configured_path, str) or configured_path.startswith("/"):
        raise IntegrityError("approved data-lock path must be repository-relative")
    if (
        not isinstance(configured_sha, str)
        or _FULL_SHA256.fullmatch(configured_sha) is None
    ):
        raise IntegrityError("approved data-lock SHA-256 is invalid")
    actual_relative = _repo_relative(data_lock_path, root, name="data lock")
    if actual_relative != configured_path:
        raise IntegrityError("supplied data lock is not the configured approved lock")
    lock_path = root / configured_path
    lock_bytes = lock_path.read_bytes()
    if sha256_bytes(lock_bytes) != configured_sha:
        raise IntegrityError("approved data-lock bytes do not match the config")
    committed_lock = _git(root, "show", f"{commit}:{configured_path}")
    if committed_lock != lock_bytes:
        raise IntegrityError("data lock does not match the blob committed at F")
    config_relative = _repo_relative(config_path, root, name="configuration")
    if (
        _git(root, "show", f"{commit}:{config_relative}")
        != Path(config_path).read_bytes()
    ):
        raise IntegrityError("configuration does not match the blob committed at F")

    lock = _strict_json(lock_path, description="approved data lock")
    if lock.get("schema") != DATA_LOCK_SCHEMA or lock.get("status") != "approved":
        raise IntegrityError("data lock is not an approved lock")
    if lock.get("fixture_only") is not False:
        raise IntegrityError("fixture data can never authorize a Covertype run")
    if lock.get("dataset_name") != "sklearn_covtype":
        raise IntegrityError("approved lock is not for sklearn_covtype")
    if lock.get("semantic_digest") != required_digest:
        raise IntegrityError("config and data lock semantic digests differ")

    artifact = Path(prepared_artifact)
    manifest_path = artifact.with_suffix(artifact.suffix + ".manifest.json")
    if lock.get("artifact_sha256") != sha256_file(artifact):
        raise IntegrityError("prepared artifact differs from the approved data lock")
    if lock.get("manifest_sha256") != sha256_file(manifest_path):
        raise IntegrityError("prepared manifest differs from the approved data lock")
    prepared = load_prepared_dataset(
        artifact,
        required_digest=required_digest,
        expected_artifact_sha256=str(lock["artifact_sha256"]),
        expected_content_sha256=str(lock["semantic_digest"]),
    )
    if prepared.dataset_name != "sklearn_covtype" or prepared.manifest.get(
        "smoke_only"
    ):
        raise IntegrityError("approved Covertype input has the wrong dataset identity")
    if prepared.manifest.get("fixture_only") is not False:
        raise IntegrityError("fixture data can never authorize a Covertype run")
    if (
        prepared.row_count != 581_012
        or prepared.source_feature_dimension != 54
        or prepared.action_count != 7
        or list(prepared.manifest.get("original_classes", [])) != list(range(1, 8))
    ):
        raise IntegrityError(
            "prepared input does not have canonical Covertype dimensions"
        )
    loader = prepared.manifest.get("loader")
    if not isinstance(loader, Mapping) or loader.get("callable") != (
        "sklearn.datasets.fetch_covtype"
    ):
        raise IntegrityError("prepared input was not produced by fetch_covtype")
    parameters = loader.get("parameters")
    required_parameters = {
        "as_frame": False,
        "return_X_y": True,
        "shuffle": False,
    }
    if not isinstance(parameters, Mapping) or any(
        parameters.get(key) != value for key, value in required_parameters.items()
    ):
        raise IntegrityError("prepared input has unexpected fetch_covtype parameters")
    if lock.get("loader_provenance") != loader:
        raise IntegrityError("loader provenance differs from the approved data lock")
    if lock.get("runtime_provenance") != prepared.manifest.get("runtime_provenance"):
        raise IntegrityError("runtime provenance differs from the approved data lock")
    if lock.get("source_cache_files") != prepared.manifest.get("source_cache_files"):
        raise IntegrityError(
            "source-cache provenance differs from the approved data lock"
        )

    expected_split = {
        "namespace": dataset.get("split_namespace"),
        "buckets": dataset.get("split_buckets"),
    }
    if lock.get("split_identity") != expected_split:
        raise IntegrityError("split policy differs from the approved data lock")
    preprocessing_identity = config.get("preprocessing")
    if lock.get("preprocessing_policy_sha256") != _digest(preprocessing_identity):
        raise IntegrityError("preprocessing policy differs from the approved data lock")
    return prepared, lock


def verify_derived_data_identities(
    lock: Mapping[str, Any], *, split_digest: str, preprocessing_digest: str
) -> None:
    if lock.get("split_digest") != split_digest:
        raise IntegrityError("actual split differs from the approved data lock")
    if lock.get("preprocessing_digest") != preprocessing_digest:
        raise IntegrityError("actual preprocessing differs from the approved data lock")


def verify_recorded_data_authorization(
    *,
    config: Mapping[str, Any],
    config_path: str | Path,
    data_lock_path: str | Path,
    freeze_revision: str,
    prepared_metadata: Mapping[str, Any],
    authentication: Mapping[str, Any],
    repo_root: str | Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    """Recheck a run's data authorization without trusting manifest booleans."""

    dataset = config.get("dataset")
    if not isinstance(dataset, Mapping):
        raise IntegrityError("configuration lacks dataset policy")
    approved = dataset.get("approved_data_lock")
    if not isinstance(approved, Mapping):
        raise IntegrityError("configuration has no approved data lock")
    root = Path(repo_root).resolve()
    freeze = _full_commit(root, freeze_revision, name="freeze_revision")
    configured_path = approved.get("path")
    configured_sha = approved.get("sha256")
    if not isinstance(configured_path, str) or not isinstance(configured_sha, str):
        raise IntegrityError("configured approved data lock is incomplete")
    if _repo_relative(data_lock_path, root, name="data lock") != configured_path:
        raise IntegrityError("supplied data lock is not the configured approved lock")
    lock_path = root / configured_path
    lock_bytes = lock_path.read_bytes()
    lock_sha = sha256_bytes(lock_bytes)
    if lock_sha != configured_sha:
        raise IntegrityError("approved data-lock hash differs from config")
    if _git(root, "show", f"{freeze}:{configured_path}") != lock_bytes:
        raise IntegrityError("approved data lock is not the blob committed at F")
    config_relative = _repo_relative(config_path, root, name="configuration")
    if (
        _git(root, "show", f"{freeze}:{config_relative}")
        != Path(config_path).read_bytes()
    ):
        raise IntegrityError("configuration is not the blob committed at F")
    lock = _strict_json(lock_path, description="approved data lock")
    if (
        lock.get("schema") != DATA_LOCK_SCHEMA
        or lock.get("status") != "approved"
        or lock.get("fixture_only") is not False
    ):
        raise IntegrityError("recorded evidence lacks an authentic approved data lock")
    if lock.get("dataset_name") != "sklearn_covtype":
        raise IntegrityError("recorded data lock is not for sklearn_covtype")
    required_digest = dataset.get("required_semantic_digest")
    if (
        not isinstance(required_digest, str)
        or _FULL_SHA256.fullmatch(required_digest) is None
        or lock.get("semantic_digest") != required_digest
    ):
        raise IntegrityError("recorded semantic digest is not approved by config")
    if lock.get("split_identity") != {
        "namespace": dataset.get("split_namespace"),
        "buckets": dataset.get("split_buckets"),
    }:
        raise IntegrityError("recorded split policy differs from the approved lock")
    if lock.get("preprocessing_policy_sha256") != _digest(config.get("preprocessing")):
        raise IntegrityError(
            "recorded preprocessing policy differs from the approved lock"
        )
    comparisons = {
        "semantic_digest": prepared_metadata.get("semantic_digest"),
        "artifact_sha256": prepared_metadata.get("artifact_sha256"),
        "manifest_sha256": prepared_metadata.get("manifest_sha256"),
        "loader_provenance": prepared_metadata.get("loader"),
        "runtime_provenance": prepared_metadata.get("runtime_provenance"),
        "source_cache_files": prepared_metadata.get("source_cache_files"),
    }
    for field, value in comparisons.items():
        if lock.get(field) != value:
            raise IntegrityError(f"recorded {field} differs from approved data lock")
    if (
        prepared_metadata.get("dataset_name") != "sklearn_covtype"
        or prepared_metadata.get("smoke_only") is not False
        or prepared_metadata.get("fixture_only") is not False
        or int(prepared_metadata.get("row_count", -1)) != 581_012
        or int(prepared_metadata.get("source_feature_dimension", -1)) != 54
        or int(prepared_metadata.get("class_count", -1)) != 7
        or list(prepared_metadata.get("original_classes", [])) != list(range(1, 8))
    ):
        raise IntegrityError(
            "recorded prepared-data identity is not canonical Covertype"
        )
    loader = prepared_metadata.get("loader")
    if not isinstance(loader, Mapping) or loader.get("callable") != (
        "sklearn.datasets.fetch_covtype"
    ):
        raise IntegrityError("recorded loader is not fetch_covtype")
    parameters = loader.get("parameters")
    if not isinstance(parameters, Mapping) or any(
        parameters.get(key) != value
        for key, value in {
            "as_frame": False,
            "return_X_y": True,
            "shuffle": False,
        }.items()
    ):
        raise IntegrityError("recorded fetch_covtype parameters are invalid")
    expected_authentication = {
        "status": "verified_against_committed_freeze_lock",
        "freeze_revision": freeze,
        "data_lock_path": configured_path,
        "data_lock_sha256": lock_sha,
        "manifest_sha256": lock.get("manifest_sha256"),
    }
    if dict(authentication) != expected_authentication:
        raise IntegrityError("recorded data-authentication result is invalid")
    verify_clean_freeze(freeze, repo_root=root, require_head=False)
    return lock


def verify_evaluation_lineage(
    *,
    freeze_revision: str,
    selection_lock_revision: str,
    evaluation_state_revision: str,
    repo_root: str | Path = REPOSITORY_ROOT,
) -> None:
    """Require the recorded evaluation state E to descend from selection lock L."""

    root = Path(repo_root).resolve()
    freeze = _full_commit(root, freeze_revision, name="freeze_revision")
    lock_revision = _full_commit(
        root, selection_lock_revision, name="selection_lock_revision"
    )
    evaluation = _full_commit(
        root, evaluation_state_revision, name="evaluation_state_revision"
    )
    try:
        _git(root, "merge-base", "--is-ancestor", lock_revision, evaluation)
    except IntegrityError as error:
        raise IntegrityError(
            "recorded evaluation state E does not descend from L"
        ) from error
    if source_inventory_at_revision(
        evaluation, repo_root=root
    ) != source_inventory_at_revision(freeze, repo_root=root):
        raise IntegrityError("scientific source objects at E differ from F")


def selection_payload_sha256(selection: Mapping[str, Any]) -> str:
    payload = {
        "optimizer": selection.get("optimizer"),
        "linucb_alpha": selection.get("linucb_alpha"),
        "practical_nystrom": selection.get("practical_nystrom"),
    }
    return _digest(payload)


def validate_selection_policy(
    selection: Mapping[str, Any], config: Mapping[str, Any]
) -> None:
    """Validate every locked choice against the preregistered candidate grids."""

    optimizers = selection.get("optimizer")
    if not isinstance(optimizers, Mapping) or set(optimizers) != {
        "label",
        "controlled_shared",
    }:
        raise IntegrityError("selection has an invalid optimizer mapping")
    rates = {
        float(value) for value in config["representation_update"]["learning_rate_grid"]
    }
    steps = {
        int(value) for value in config["representation_update"]["steps_per_round_grid"]
    }
    for name, raw in optimizers.items():
        if not isinstance(raw, Mapping):
            raise IntegrityError(f"selection optimizer {name} is invalid")
        try:
            raw_rate = raw["learning_rate"]
            raw_count = raw["steps_per_round"]
        except (KeyError, TypeError, ValueError) as error:
            raise IntegrityError(f"selection optimizer {name} is invalid") from error
        if (
            isinstance(raw_rate, bool)
            or not isinstance(raw_rate, (int, float))
            or not math.isfinite(float(raw_rate))
            or isinstance(raw_count, bool)
            or not isinstance(raw_count, int)
            or set(raw) != {"learning_rate", "steps_per_round"}
            or float(raw_rate) not in rates
            or raw_count not in steps
        ):
            raise IntegrityError(
                f"selection optimizer {name} is outside the frozen grid"
            )

    alphas = selection.get("linucb_alpha")
    if not isinstance(alphas, Mapping) or set(alphas) != set(EXPECTED_TASKS):
        raise IntegrityError("selection has an invalid LinUCB mapping")
    allowed_alphas = {float(value) for value in config["linucb"]["alpha_grid"]}
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) not in allowed_alphas
        for value in alphas.values()
    ):
        raise IntegrityError("selection LinUCB alpha is outside the frozen grid")

    practical = selection.get("practical_nystrom")
    if not isinstance(practical, Mapping) or set(practical) != set(EXPECTED_TASKS):
        raise IntegrityError("selection has an invalid practical-Nyström mapping")
    if any(str(value) not in APPROXIMATE_METHODS for value in practical.values()):
        raise IntegrityError("selection practical Nyström method is outside the grid")


def verify_selection_lock(
    *,
    selection_path: str | Path,
    freeze_revision: str,
    selection_lock_revision: str,
    repo_root: str | Path = REPOSITORY_ROOT,
    require_current_lineage: bool = True,
) -> tuple[dict[str, Any], str]:
    """Verify F -> selection-only L and the exact selection blob at L."""

    root = Path(repo_root).resolve()
    freeze = _full_commit(root, freeze_revision, name="freeze_revision")
    lock_revision = _full_commit(
        root, selection_lock_revision, name="selection_lock_revision"
    )
    path = Path(selection_path)
    relative = _repo_relative(path, root, name="selection artifact")
    document = _strict_json(path, description="selection artifact")
    if (
        document.get("schema") != SELECTION_SCHEMA
        or document.get("status") != "selected"
    ):
        raise IntegrityError("selection artifact is not a locked v2 selection")
    if document.get("freeze_revision") != freeze:
        raise IntegrityError("selection artifact is bound to the wrong F")
    if document.get("selection_payload_sha256") != selection_payload_sha256(document):
        raise IntegrityError("selection payload hash is invalid")
    committed = _git(root, "show", f"{lock_revision}:{relative}")
    current = path.read_bytes()
    if committed != current:
        raise IntegrityError("selection bytes are not committed unchanged at L")
    artifact_sha256 = sha256_bytes(current)
    sidecar_relative = relative + ".sha256"
    sidecar = _git(root, "show", f"{lock_revision}:{sidecar_relative}").decode("ascii")
    if sidecar.split() != [artifact_sha256, Path(relative).name]:
        raise IntegrityError("selection SHA-256 sidecar committed at L is invalid")

    parents = (
        _git(root, "rev-list", "--parents", "-n", "1", lock_revision)
        .decode("ascii")
        .split()
    )
    if len(parents) != 2 or parents[1] != freeze:
        raise IntegrityError("L must be a single-parent selection-only child of F")
    changed = set(
        item
        for item in _git(root, "diff", "--name-only", "-z", freeze, lock_revision)
        .decode("utf-8")
        .split("\0")
        if item
    )
    if changed != {relative, sidecar_relative}:
        raise IntegrityError(
            f"L is not selection-only: changed paths are {sorted(changed)}"
        )
    expected_inventory = source_inventory_at_revision(freeze, repo_root=root)
    if document.get("source_inventory") != expected_inventory:
        raise IntegrityError("selection source inventory does not match F")
    if document.get("source_inventory_sha256") != input_set_sha256(expected_inventory):
        raise IntegrityError("selection source-inventory hash is invalid")
    verify_clean_freeze(freeze, repo_root=root, require_head=False)
    if require_current_lineage:
        try:
            _git(root, "merge-base", "--is-ancestor", lock_revision, "HEAD")
        except IntegrityError as error:
            raise IntegrityError(
                "current evaluation state E does not descend from L"
            ) from error
    return document, artifact_sha256


__all__ = [
    "DATA_LOCK_SCHEMA",
    "IntegrityError",
    "SELECTION_SCHEMA",
    "authenticate_prepared_data",
    "current_source_inventory",
    "selection_payload_sha256",
    "source_inventory_at_revision",
    "validate_selection_policy",
    "verify_clean_freeze",
    "verify_derived_data_identities",
    "verify_evaluation_lineage",
    "verify_recorded_data_authorization",
    "verify_selection_lock",
]
