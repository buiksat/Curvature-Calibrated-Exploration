#!/usr/bin/env python3
"""Build a compact, self-contained, anonymous paper supplement.

The builder deliberately does not use Git's archive machinery: experiment
artifacts in this repository are generated files, and Git metadata is itself
an anonymity risk.  Instead it selects the release surface explicitly,
sanitizes structured records, rewrites provenance to released files, and
installs a fully validated staging tree atomically.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import dataclasses
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Iterable, Iterator, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO


SCHEMA_VERSION = 1
DEFAULT_OUTPUT = "release"
REVIEW_OUTPUT = "release_review"
RELEASE_TIERS = ("full", "review")
RAW_ROOT = PurePosixPath("results/raw")
REVIEW_RAW_INDEX_PATH = "manifests/full-raw-index.json"
UNAVAILABLE_SOURCE_INDEX_PATH = "manifests/unavailable-source-inputs.json"
UNAVAILABLE_RAW_STATUS = "not_in_source_tree"
HYDRATED_COMPLETE_STATUS = "complete_payloads"
HYDRATED_LEGACY_GAPS_STATUS = (
    "complete_available_source_payloads_with_declared_legacy_gaps"
)
REVIEW_SELECTION_ALGORITHM = (
    "lexicographically-first-complete-run-per-top-level-study-v1"
)
REVIEW_AUXILIARY_MAX_BYTES = 1024 * 1024
MAX_NPZ_MEMBERS = 1024
MAX_NPZ_MEMBER_BYTES = 16 * 1024 * 1024
MAX_NPZ_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_NPZ_COMPRESSION_RATIO = 100
NPZ_PROCESS_POOL_MIN_FILES = 64
NPZ_PROCESS_POOL_WORKERS = min(8, os.cpu_count() or 1)

# Build these strings in pieces so the scanner implementation can itself be
# shipped in the supplement without tripping its literal-token checks.
LOCAL_PATH_PREFIXES = (
    "/" + "Users" + "/",
    "/" + "home" + "/",
    "/" + "mnt" + "/",
)
FIXED_FORBIDDEN = {
    "local-user-path": LOCAL_PATH_PREFIXES[0],
    "local-home-path": LOCAL_PATH_PREFIXES[1],
    "mounted-path": LOCAL_PATH_PREFIXES[2],
    "local-file-uri": "file" + "://",
    "loopback-host": "local" + "host",
    "code-forge-host": "github" + ".com",
    "ssh-repository-uri": "git" + "@",
}
EMAIL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._%+-])"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    r"(?![A-Za-z0-9.-])"
)
EMAIL_BYTES_PATTERN = re.compile(
    rb"(?<![A-Za-z0-9._%+-])"
    rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    rb"(?![A-Za-z0-9.-])"
)
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PATHISH_KEYS = {
    "artifact",
    "data_home",
    "dataset_file",
    "dataset_files",
    "executable",
    "git_root",
    "input_root",
    "indices_artifact",
    "output_root",
    "path",
    "run_directories",
}
IDENTITY_KEYS = {
    "affiliation",
    "affiliations",
    "author",
    "authors",
    "email",
    "emails",
    "host",
    "host_name",
    "hostname",
    "institution",
    "institutions",
    "login",
    "node",
    "user",
    "username",
}
GIT_REVISION_KEYS = {
    "commit",
    "commit_hash",
    "git_commit",
    "git_revision",
    "git_revisions",
    "revision",
}
TEXT_SUFFIXES = {
    ".bib",
    ".cfg",
    ".csv",
    ".md",
    ".py",
    ".sty",
    ".tex",
    ".txt",
    ".yaml",
    ".yml",
}
PAPER_TOP_LEVEL = {
    "aistats2026.sty",
    "aistats2027.sty",
    "macros.tex",
    "main.pdf",
    "main.tex",
    "references.bib",
    "validate.py",
}
OPTIONAL_PAPER_INPUTS = {
    "aistats2027_checklist.tex",
    "aistats_checklist.tex",
}
RELEASE_TOOLING_EXCLUSIONS = frozenset(
    {
        "tests/test_anonymous_supplement.py",
        "tools/build_anonymous_supplement.py",
    }
)
PRIVATE_EDITOR_MACRO_PATTERN = re.compile(r"^\\\\[a-z]+$")
DATA_FIXTURE_PATHS = (
    "experiments/data/sklearn/covertype/samples_py3",
    "experiments/data/sklearn/covertype/targets_py3",
)
# Aggregators consume every scalar metric.  These are the only composite
# metrics they inspect directly or use to reconstruct action counts and solver
# iteration summaries.  The remaining vectors are redundant with released
# summaries/derived artifacts and dominate the archive size.
RETAINED_COMPOSITE_METRICS = {
    "cg_converged",
    "cg_iterations",
    "exact_error_sandwich_holds",
    "optimism_violation_indicators",
    "optimism_violations",
    "per_action_iterations",
    "policy_optimism_violation_actions",
    "policy_scores_all_actions",
    "posthoc_cg_converged_all_actions",
    "posthoc_cg_iterations_all_actions",
    "target_sandwich_holds",
}
SOURCE_HASH_EXCLUDED_SUFFIXES = {
    ".pdf",
    ".png",
}
OPAQUE_GENERATED_SUFFIXES = {
    ".pdf",
    ".png",
}


class BuildError(RuntimeError):
    """Raised when the release cannot be made complete and anonymous."""


class _UnresolvedReference(BuildError):
    """Raised when a release input must be processed in a later pass."""


class _IntentionallyOmittedReference(BuildError):
    """Raised when a review-tier dependency was deliberately excluded."""


@dataclasses.dataclass(frozen=True)
class FileRecord:
    path: str
    sha256: str
    size_bytes: int
    role: str


@dataclasses.dataclass(frozen=True)
class ReferenceTarget:
    path: str
    sha256: str


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_posix(path: Path, root: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise BuildError(f"path escapes repository root: {path}") from error
    return relative.as_posix()


def _git_output(repository: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=repository,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def discover_identity_terms(repository: Path) -> tuple[str, ...]:
    """Collect local identity tokens without writing them to the release."""

    candidates: set[str] = set()
    names: set[str] = set()
    emails: set[str] = set()

    configured_name = _git_output(repository, "config", "--get", "user.name")
    configured_email = _git_output(repository, "config", "--get", "user.email")
    if configured_name:
        names.add(configured_name)
    if configured_email:
        emails.add(configured_email)

    history = _git_output(repository, "log", "--all", "--format=%an%x00%ae")
    for line in history.splitlines():
        if "\x00" not in line:
            continue
        name, email = line.split("\x00", 1)
        if name.strip():
            names.add(name.strip())
        if email.strip():
            emails.add(email.strip())

    for name in names:
        candidates.add(name)
        for component in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", name):
            candidates.add(component)
    for email in emails:
        candidates.add(email)
        local, separator, domain = email.partition("@")
        if separator:
            if len(local) >= 5:
                candidates.add(local)
            candidates.add(domain)
            organization = domain.split(".", 1)[0]
            if len(organization) >= 5:
                candidates.add(organization)

    for variable in ("USER", "LOGNAME"):
        value = os.environ.get(variable, "").strip()
        if len(value) >= 5 and value.lower() not in {"runner", "nobody"}:
            candidates.add(value)
    hostname = socket.gethostname().strip()
    if hostname and hostname.lower() != FIXED_FORBIDDEN["loopback-host"]:
        candidates.add(hostname)

    return tuple(sorted(candidates, key=lambda item: (item.casefold(), item)))


class IdentityScanner:
    def __init__(self, identity_terms: Sequence[str]) -> None:
        self.identity_terms = tuple(identity_terms)
        self._fixed = tuple(
            (name, re.compile(re.escape(value), re.IGNORECASE))
            for name, value in FIXED_FORBIDDEN.items()
        )
        self._identity = tuple(
            (
                f"local-identity-{index + 1}",
                re.compile(
                    rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])",
                    re.IGNORECASE,
                ),
            )
            for index, term in enumerate(self.identity_terms)
        )
        byte_marker_text = (
            *FIXED_FORBIDDEN.values(),
            *self.identity_terms,
        )
        self._byte_markers = tuple(
            marker.casefold().encode("utf-8") for marker in byte_marker_text
        )
        self._requires_unicode_prefilter = any(
            not marker.isascii() for marker in byte_marker_text
        )
        self.issues: list[dict[str, Any]] = []
        self.scanned_paths: set[str] = set()

    def scan_text(
        self,
        path: str,
        text: str,
        *,
        count: bool = True,
        scan_email: bool = True,
    ) -> None:
        if count:
            self.scanned_paths.add(path)
        folded = text.casefold()
        fixed_markers = tuple(value.casefold() for value in FIXED_FORBIDDEN.values())
        identity_markers = tuple(term.casefold() for term in self.identity_terms)
        may_reconstruct_identity = bool(
            self.identity_terms and PurePosixPath(path).suffix.lower() == ".py"
        )
        if (
            "@" not in text
            and not any(marker in folded for marker in fixed_markers)
            and not any(marker in folded for marker in identity_markers)
            and not may_reconstruct_identity
        ):
            return

        patterns = (*self._fixed, *self._identity)
        if scan_email:
            patterns = (*patterns, ("email-address", EMAIL_PATTERN))
        for rule, pattern in patterns:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                self.issues.append({"path": path, "line": line, "rule": rule})

        if may_reconstruct_identity:
            for line, value in _python_reconstructed_strings(text):
                for rule, pattern in self._identity:
                    if pattern.search(value):
                        self.issues.append(
                            {
                                "path": path,
                                "line": line,
                                "rule": f"{rule}-reconstructed",
                            }
                        )

    def scan_bytes(self, path: str, data: bytes, *, count: bool = True) -> None:
        if PurePosixPath(path).suffix.lower() == ".npz":
            self._scan_npz(path, data, count=count)
            return
        self._scan_plain_bytes(path, data, count=count)

    def _scan_plain_bytes(
        self,
        path: str,
        data: bytes,
        *,
        count: bool,
        scan_email: bool = True,
    ) -> None:
        if count:
            self.scanned_paths.add(path)
        may_reconstruct_identity = bool(
            self.identity_terms and PurePosixPath(path).suffix.lower() == ".py"
        )
        has_email_marker = scan_email and b"@" in data
        requires_text_scan = (
            self._requires_unicode_prefilter or may_reconstruct_identity
        )
        if not requires_text_scan:
            folded = data.lower()
            requires_text_scan = any(
                marker in folded for marker in self._byte_markers
            )
        if requires_text_scan:
            self.scan_text(
                path,
                data.decode("utf-8", errors="replace"),
                count=False,
                scan_email=False,
            )
        if has_email_marker:
            for match in EMAIL_BYTES_PATTERN.finditer(data):
                line = data.count(b"\n", 0, match.start()) + 1
                self.issues.append(
                    {"path": path, "line": line, "rule": "email-address"}
                )

    def _scan_npz(self, path: str, data: bytes, *, count: bool) -> None:
        if count:
            self.scanned_paths.add(path)
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as error:
            raise BuildError(f"invalid NPZ container: {path}") from error
        with archive:
            infos = archive.infolist()
            if not infos:
                raise BuildError(f"empty NPZ container: {path}")
            if len(infos) > MAX_NPZ_MEMBERS:
                raise BuildError(f"NPZ container has too many members: {path}")
            total_size = sum(info.file_size for info in infos)
            if total_size > MAX_NPZ_UNCOMPRESSED_BYTES:
                raise BuildError(f"NPZ container is too large to inspect: {path}")
            compressed_size = sum(info.compress_size for info in infos)
            if total_size > MAX_NPZ_COMPRESSION_RATIO * max(compressed_size, 1):
                raise BuildError(
                    f"NPZ compression ratio is too high to inspect: {path}"
                )
            seen: set[str] = set()
            self._scan_plain_bytes(
                f"{path}!archive-comment",
                archive.comment,
                count=False,
            )
            for info in infos:
                member = PurePosixPath(info.filename)
                if (
                    info.is_dir()
                    or member.is_absolute()
                    or ".." in member.parts
                    or member.suffix.lower() != ".npy"
                    or info.filename in seen
                    or info.flag_bits & 0x1
                ):
                    raise BuildError(
                        f"unsafe or unsupported NPZ member {info.filename!r} in {path}"
                    )
                if info.file_size > MAX_NPZ_MEMBER_BYTES:
                    raise BuildError(
                        f"NPZ member is too large to inspect: {path}!{info.filename}"
                    )
                seen.add(info.filename)
                member_path = f"{path}!{info.filename}"
                self.scan_text(member_path, info.filename, count=False)
                self._scan_plain_bytes(
                    f"{member_path}!metadata",
                    info.extra + info.comment,
                    count=False,
                )
                payload = archive.read(info)
                kinds = self._validate_npy_payload(member_path, payload)
                if kinds == {"S"}:
                    self._scan_plain_bytes(member_path, payload, count=False)
                elif "S" in kinds:
                    raise BuildError(
                        f"NPY member has mixed string/numeric fields: {member_path}"
                    )

    def _validate_npy_payload(self, path: str, payload: bytes) -> set[str]:
        if len(payload) < 10 or payload[:6] != b"\x93NUMPY":
            raise BuildError(f"invalid NPY member: {path}")
        version = (payload[6], payload[7])
        if version == (1, 0):
            length_bytes = 2
            encoding = "latin1"
        elif version in {(2, 0), (3, 0)}:
            length_bytes = 4
            encoding = "utf-8" if version == (3, 0) else "latin1"
        else:
            raise BuildError(f"unsupported NPY version {version} in {path}")
        header_start = 8 + length_bytes
        header_length = int.from_bytes(payload[8:header_start], "little")
        header_end = header_start + header_length
        if header_end > len(payload):
            raise BuildError(f"truncated NPY header: {path}")
        try:
            header_text = payload[header_start:header_end].decode(encoding)
            header = ast.literal_eval(header_text.strip())
        except (SyntaxError, ValueError, UnicodeDecodeError) as error:
            raise BuildError(f"invalid NPY header: {path}") from error
        if not isinstance(header, dict) or "descr" not in header:
            raise BuildError(f"invalid NPY header fields: {path}")
        self.scan_text(f"{path}!header", header_text, count=False)
        kinds = _npy_dtype_kinds(header["descr"])
        unsupported = kinds & {"O", "U", "V"}
        if unsupported:
            raise BuildError(
                f"NPY member has unauditable dtype kinds {sorted(unsupported)}: {path}"
            )
        return kinds

    def raise_for_issues(self) -> None:
        if not self.issues:
            return
        sample = ", ".join(
            f"{item['path']}:{item['line']} ({item['rule']})"
            for item in self.issues[:12]
        )
        remainder = len(self.issues) - min(len(self.issues), 12)
        suffix = f"; {remainder} more" if remainder else ""
        raise BuildError(f"identity scan failed: {sample}{suffix}")


def _scan_and_stage_npz(
    task: tuple[str, str, str, tuple[str, ...]],
) -> tuple[str, str, int]:
    source_text, destination_text, relative, identity_terms = task
    source = Path(source_text)
    destination = Path(destination_text)
    before = source.stat()
    data = source.read_bytes()
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (
        after.st_size,
        after.st_mtime_ns,
    ):
        raise BuildError(f"source changed while copying: {relative}")
    scanner = IdentityScanner(identity_terms)
    scanner.scan_bytes(relative, data)
    scanner.raise_for_issues()
    destination.write_bytes(data)
    os.chmod(destination, 0o644)
    return relative, sha256_bytes(data), len(data)


class StructuredSanitizer:
    def __init__(self, repository: Path, anonymous_source_hash: str) -> None:
        self.repository = repository.resolve()
        self.repository_text = self.repository.as_posix()
        self.anonymous_source_hash = anonymous_source_hash

    def normalize_string(self, value: str, *, path_context: bool = False) -> str:
        file_scheme = FIXED_FORBIDDEN["local-file-uri"]
        normalized = value
        if normalized.startswith(file_scheme):
            normalized = normalized[len(file_scheme) :]

        if normalized == self.repository_text:
            return "."
        prefix = self.repository_text.rstrip("/") + "/"
        if normalized.startswith(prefix):
            return normalized[len(prefix) :]
        if prefix in normalized:
            normalized = normalized.replace(prefix, "")

        if path_context and normalized.startswith(LOCAL_PATH_PREFIXES):
            basename = PurePosixPath(normalized).name or "path"
            return f"external-data/{basename}"
        return normalized

    def sanitize(self, value: Any, *, key: str | None = None) -> Any:
        normalized_key = key.casefold() if isinstance(key, str) else None
        if normalized_key in GIT_REVISION_KEYS:
            if isinstance(value, list):
                return [self.anonymous_source_hash]
            return self.anonymous_source_hash
        if normalized_key in IDENTITY_KEYS:
            if isinstance(value, list):
                return ["anonymous"]
            if isinstance(value, dict):
                return {"value": "anonymous"}
            return "anonymous"

        if isinstance(value, dict):
            result = {
                str(item_key): self.sanitize(item_value, key=str(item_key))
                for item_key, item_value in value.items()
            }
            if isinstance(result.get("config"), dict) and "config_digest" in result:
                result["config_digest"] = sha256_bytes(
                    canonical_json(result["config"]).encode("ascii")
                )
            return result
        if isinstance(value, list):
            return [self.sanitize(item, key=key) for item in value]
        if isinstance(value, str):
            path_context = bool(
                normalized_key in PATHISH_KEYS
                or (
                    normalized_key
                    and normalized_key.endswith(
                        ("_path", "_root", "_file", "_artifact")
                    )
                )
            )
            return self.normalize_string(value, path_context=path_context)
        return value


def _python_reconstructed_strings(text: str) -> tuple[tuple[int, str], ...]:
    """Return strings assembled by Python syntax from multiple literals."""

    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return ()

    reconstructed: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            parts = _literal_addition_parts(node)
            if parts is not None and len(parts) > 1:
                reconstructed.add((node.lineno, "".join(parts)))
        elif isinstance(node, (ast.List, ast.Set, ast.Tuple)):
            run: list[str] = []
            for element in node.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    run.append(element.value)
                    continue
                if len(run) > 1:
                    reconstructed.add((node.lineno, "".join(run)))
                run = []
            if len(run) > 1:
                reconstructed.add((node.lineno, "".join(run)))
    return tuple(sorted(reconstructed))


def _literal_addition_parts(node: ast.expr) -> list[str] | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Add):
        return None
    left = _literal_addition_parts(node.left)
    right = _literal_addition_parts(node.right)
    if left is None or right is None:
        return None
    return [*left, *right]


def _npy_dtype_kinds(descriptor: Any) -> set[str]:
    if isinstance(descriptor, str):
        normalized = descriptor.lstrip("<>=|")
        if not normalized:
            raise BuildError(f"invalid NPY dtype descriptor: {descriptor!r}")
        return {normalized[0]}
    if isinstance(descriptor, tuple):
        if not descriptor:
            raise BuildError("empty NPY dtype tuple")
        return _npy_dtype_kinds(descriptor[0])
    if isinstance(descriptor, list):
        kinds: set[str] = set()
        for field in descriptor:
            if not isinstance(field, tuple) or len(field) < 2:
                raise BuildError(f"invalid structured NPY dtype field: {field!r}")
            kinds.update(_npy_dtype_kinds(field[1]))
        return kinds
    raise BuildError(f"invalid NPY dtype descriptor: {descriptor!r}")


def _source_candidates(repository: Path) -> tuple[Path, ...]:
    candidates: set[Path] = set()
    for root_name in ("Makefile", "pytest.ini"):
        root_file = repository / root_name
        if root_file.is_file():
            candidates.add(root_file)

    experiments = repository / "experiments"
    if experiments.is_dir():
        for path in experiments.rglob("*"):
            if not path.is_file():
                continue
            relative_parts = path.relative_to(experiments).parts
            if not relative_parts:
                continue
            if relative_parts[0] in {"data", "results", "__pycache__"}:
                continue
            if path.name == ".DS_Store" or "__pycache__" in relative_parts:
                continue
            candidates.add(path)

    for subtree in (repository / "tests", repository / "tools", repository / "scripts"):
        if not subtree.is_dir():
            continue
        for path in subtree.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                candidates.add(path)

    generated_tables = repository / "tables" / "generated"
    if generated_tables.is_dir():
        for path in generated_tables.rglob("*"):
            if (
                path.is_file()
                and path.name != ".gitkeep"
                and not path.name.endswith(".provenance.json")
            ):
                candidates.add(path)

    paper = repository / "paper"
    if paper.is_dir():
        for name in PAPER_TOP_LEVEL:
            path = paper / name
            if path.is_file():
                candidates.add(path)
        for subtree_name in ("figures", "tables"):
            subtree = paper / subtree_name
            if not subtree.is_dir():
                continue
            for path in subtree.rglob("*"):
                if not path.is_file() or path.name == ".gitkeep":
                    continue
                if path.name.endswith(".provenance.json"):
                    continue
                candidates.add(path)
    return tuple(
        sorted(
            (
                path
                for path in candidates
                if relative_posix(path, repository) not in RELEASE_TOOLING_EXCLUSIONS
            ),
            key=lambda path: relative_posix(path, repository),
        )
    )


def _is_source_hash_file(path: Path, repository: Path) -> bool:
    relative = PurePosixPath(relative_posix(path, repository))
    if path.suffix.lower() in SOURCE_HASH_EXCLUDED_SUFFIXES:
        return False
    if relative.parts[:2] in {
        ("paper", "figures"),
        ("paper", "tables"),
        ("tables", "generated"),
    }:
        return False
    return True


def _sanitized_source_bytes(path: Path, sanitizer: StructuredSanitizer) -> bytes:
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name != "Makefile":
        return path.read_bytes()
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        try:
            return _json_bytes(sanitizer.sanitize(json.loads(text)))
        except json.JSONDecodeError as error:
            raise BuildError(f"cannot parse structured source {path}: {error}") from error
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            pass
        else:
            return _json_bytes(sanitizer.sanitize(value))
    relative = relative_posix(path, sanitizer.repository)
    return sanitize_source_text(relative, text, sanitizer).encode("utf-8")


def sanitize_source_text(
    relative: str, text: str, sanitizer: StructuredSanitizer
) -> str:
    result = sanitizer.normalize_string(text)
    if relative == "paper/validate.py":
        result = _remove_private_validator_macros(result)
    return result


def _remove_private_validator_macros(text: str) -> str:
    """Remove the leading class of bare editor aliases from ``deleted``."""

    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        raise BuildError(f"cannot parse paper validator: {error}") from error

    deleted_value: ast.List | ast.Tuple | None = None
    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "deleted"
            for target in statement.targets
        ):
            continue
        if isinstance(statement.value, (ast.List, ast.Tuple)):
            deleted_value = statement.value
        break
    if deleted_value is None:
        return text

    values: list[str] = []
    for element in deleted_value.elts:
        if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
            raise BuildError("paper validator deleted-macro list is not literal")
        values.append(element.value)

    private_prefix_length = 0
    for value in values:
        if not PRIVATE_EDITOR_MACRO_PATTERN.fullmatch(value):
            break
        private_prefix_length += 1
    if not private_prefix_length:
        return text

    retained = values[private_prefix_length:]
    replacement = "[\n" + "".join(f"    {value!r},\n" for value in retained) + "]"
    lines = text.splitlines(keepends=True)
    if deleted_value.end_lineno is None or deleted_value.end_col_offset is None:
        raise BuildError("paper validator deleted-macro location is unavailable")
    start = _ast_text_offset(lines, deleted_value.lineno, deleted_value.col_offset)
    end = _ast_text_offset(
        lines,
        deleted_value.end_lineno,
        deleted_value.end_col_offset,
    )
    return text[:start] + replacement + text[end:]


def _ast_text_offset(lines: Sequence[str], line_number: int, byte_offset: int) -> int:
    prefix = "".join(lines[: line_number - 1])
    line = lines[line_number - 1]
    column = len(line.encode("utf-8")[:byte_offset].decode("utf-8"))
    return len(prefix) + column


def anonymous_source_inventory(
    repository: Path, candidates: Sequence[Path]
) -> tuple[str, list[dict[str, Any]]]:
    # Source files do not carry revision fields, so a fixed bootstrap value is
    # sufficient while computing their content-addressed identity.
    bootstrap = StructuredSanitizer(repository, "0" * 64)
    inventory: list[dict[str, Any]] = []
    for path in candidates:
        if not _is_source_hash_file(path, repository):
            continue
        data = _sanitized_source_bytes(path, bootstrap)
        inventory.append(
            {
                "path": relative_posix(path, repository),
                "sha256": sha256_bytes(data),
                "size_bytes": len(data),
            }
        )
    digest = sha256_bytes(canonical_json(inventory).encode("ascii"))
    return digest, inventory


def _json_bytes(value: Any, *, pretty: bool = True) -> bytes:
    if pretty:
        return (
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    return (canonical_json(value) + "\n").encode("ascii")


def project_raw_record(record: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    """Remove only composite metrics unused by released artifact generators."""

    metrics = record.get("metrics")
    if not isinstance(metrics, dict):
        return record, set()
    compact_metrics: dict[str, Any] = {}
    removed: set[str] = set()
    for metric_name, metric_value in metrics.items():
        if metric_value is None or isinstance(metric_value, (str, bool, int, float)):
            compact_metrics[metric_name] = metric_value
        elif metric_name in RETAINED_COMPOSITE_METRICS:
            compact_metrics[metric_name] = metric_value
        else:
            removed.add(metric_name)
    result = dict(record)
    result["metrics"] = compact_metrics
    return result, removed


def is_optional_paper_reference(reference: str) -> bool:
    return PurePosixPath(reference).name in OPTIONAL_PAPER_INPUTS


def select_review_run_directories(raw_root: Path) -> tuple[Path, ...]:
    """Select one stable representative trajectory per top-level study.

    Candidates are ordered by their POSIX path below ``results/raw``.  The
    first complete run for each first path component is retained.  The legacy
    top-level smoke workspace is excluded in the same way as the full release.
    """

    candidates: list[tuple[str, Path]] = []
    for raw_path in raw_root.rglob("raw.jsonl"):
        relative = raw_path.relative_to(raw_root)
        if not relative.parts or relative.parts[0] == "smoke":
            continue
        if not all(
            (raw_path.parent / name).is_file()
            for name in ("manifest.jsonl", "summary.jsonl")
        ):
            continue
        candidates.append((relative.as_posix(), raw_path.parent))

    selected: dict[str, Path] = {}
    for _, directory in sorted(candidates):
        study = directory.relative_to(raw_root).parts[0]
        selected.setdefault(study, directory)
    return tuple(selected[study] for study in sorted(selected))


class ReleaseBuilder:
    def __init__(
        self,
        repository: Path,
        output: Path,
        *,
        hydrate_raw: bool = False,
        overwrite: bool = False,
        tier: str = "full",
    ) -> None:
        if tier not in RELEASE_TIERS:
            raise BuildError(f"unknown release tier: {tier}")
        if hydrate_raw and tier != "review":
            raise BuildError("raw hydration is available only for the review tier")
        self.repository = repository.resolve()
        self.output = output if output.is_absolute() else self.repository / output
        self.output = self.output.absolute()
        self.overwrite = overwrite
        self.tier = tier
        self.hydrate_raw = hydrate_raw
        self.identity_scanner = IdentityScanner(discover_identity_terms(self.repository))
        self.source_candidates = _source_candidates(self.repository)
        self.source_hash, self.source_inventory = anonymous_source_inventory(
            self.repository, self.source_candidates
        )
        self.sanitizer = StructuredSanitizer(self.repository, self.source_hash)
        self.records: dict[str, FileRecord] = {}
        self.references: dict[str, ReferenceTarget] = {}
        self.raw_inventory: list[dict[str, Any]] = []
        self.raw_source_index: dict[str, dict[str, Any]] = {}
        self.raw_index_record: FileRecord | None = None
        self.unavailable_source_index_record: FileRecord | None = None
        self.unavailable_raw_occurrence_count = 0
        self.unavailable_raw_unique_count = 0
        self.review_run_directories: tuple[str, ...] = ()
        self.removed_raw_fields: set[str] = set()
        self.run_id_maps: dict[str, dict[str, str]] = {}
        self.source_digest_cache: dict[str, tuple[int, int, str]] = {}
        self.compression, self.compression_extension = self._select_compression()
        self.staging: Path | None = None

    @staticmethod
    def _select_compression() -> tuple[str, str]:
        if shutil.which("zstd"):
            return "zstd", ".zst"
        return "gzip", ".gz"

    def _validate_destination(self) -> None:
        repository = self.repository.resolve()
        output = self.output.resolve(strict=False)
        full_release = repository / DEFAULT_OUTPUT
        if output == repository or output == Path(output.anchor):
            raise BuildError("output must be a dedicated release directory")
        if repository.is_relative_to(output):
            raise BuildError("output cannot be an ancestor of the repository")
        if self.tier == "review" and (
            output == full_release or output.is_relative_to(full_release)
        ):
            raise BuildError("review tier cannot target the full release directory")
        if output.exists() and not self.overwrite:
            raise BuildError(f"output already exists: {output}; pass --overwrite to replace it")

    def _stage_path(self, relative: str) -> Path:
        if self.staging is None:
            raise AssertionError("staging directory is not initialized")
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts:
            raise BuildError(f"invalid release path: {relative}")
        destination = self.staging.joinpath(*pure.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        return destination

    def _record_file(
        self,
        relative: str,
        *,
        role: str,
        source_relative: str | None = None,
    ) -> FileRecord:
        path = self._stage_path(relative)
        record = FileRecord(
            path=relative,
            sha256=sha256_file(path),
            size_bytes=path.stat().st_size,
            role=role,
        )
        self.records[relative] = record
        if source_relative is not None:
            self.references[source_relative] = ReferenceTarget(relative, record.sha256)
        return record

    def _write_bytes(
        self,
        relative: str,
        data: bytes,
        *,
        role: str,
        source_relative: str | None = None,
        scan: bool = True,
    ) -> FileRecord:
        destination = self._stage_path(relative)
        destination.write_bytes(data)
        os.chmod(destination, 0o755 if relative.endswith(".py") else 0o644)
        if scan:
            if PurePosixPath(relative).suffix.lower() not in OPAQUE_GENERATED_SUFFIXES:
                self.identity_scanner.scan_bytes(relative, data)
        return self._record_file(
            relative, role=role, source_relative=source_relative
        )

    def _copy_sources(self) -> None:
        for source in self.source_candidates:
            relative = relative_posix(source, self.repository)
            suffix = source.suffix.lower()
            if suffix in {".json"}:
                try:
                    value = json.loads(source.read_text(encoding="utf-8"))
                except json.JSONDecodeError as error:
                    raise BuildError(f"cannot parse structured source {relative}: {error}") from error
                value = self.sanitizer.sanitize(value)
                data = _json_bytes(value)
            elif suffix in {".yaml", ".yml"}:
                text = source.read_text(encoding="utf-8")
                try:
                    value = json.loads(text)
                except json.JSONDecodeError:
                    data = self.sanitizer.normalize_string(text).encode("utf-8")
                else:
                    data = _json_bytes(self.sanitizer.sanitize(value))
            elif suffix in TEXT_SUFFIXES or source.name == "Makefile":
                text = source.read_text(encoding="utf-8")
                data = sanitize_source_text(relative, text, self.sanitizer).encode("utf-8")
            else:
                data = source.read_bytes()
            role = "paper" if relative.startswith("paper/") else "source"
            self._write_bytes(
                relative,
                data,
                role=role,
                source_relative=relative,
            )

    def _copy_dataset_fixtures(self) -> None:
        for relative in DATA_FIXTURE_PATHS:
            source = self.repository.joinpath(*PurePosixPath(relative).parts)
            if not source.is_file():
                # Public dataset caches are machine-local accelerators.  The
                # release keeps the loader/configuration but must not depend on
                # a particular scikit-learn cache serialization.
                continue
            self._write_bytes(
                relative,
                source.read_bytes(),
                role="dataset-fixture",
                source_relative=relative,
            )

    def _rewrite_run_id(self, record: dict[str, Any], source_relative: str) -> None:
        old = record.get("run_id")
        config = record.get("config")
        digest = record.get("config_digest")
        if not isinstance(old, str) or not isinstance(config, dict) or not isinstance(digest, str):
            return
        name = str(config.get("name", "run"))
        seed = record.get("seed", "unknown")
        new = f"{name}-s{seed}-{digest[:16]}"
        record["run_id"] = new
        self.run_id_maps.setdefault(str(PurePosixPath(source_relative).parent), {})[old] = new

    def _rewrite_known_paths(
        self,
        value: Any,
        *,
        contextual_inputs_validated: bool = False,
        source_relative: str | None = None,
    ) -> Any:
        if isinstance(value, list):
            return [
                self._rewrite_known_paths(
                    item,
                    contextual_inputs_validated=contextual_inputs_validated,
                    source_relative=source_relative,
                )
                for item in value
            ]
        if not isinstance(value, dict):
            return value

        if not contextual_inputs_validated:
            value = self._resolve_contextual_inputs(value, source_relative)

        source_path = value.get("path")
        if self.tier == "review" and isinstance(source_path, str) and "sha256" in value:
            normalized_source = self.sanitizer.normalize_string(
                source_path, path_context=True
            )
            source_entry = getattr(self, "raw_source_index", {}).get(normalized_source)
            if source_entry is not None and value.get("sha256") != source_entry["sha256"]:
                raise BuildError(f"indexed raw input hash is stale: {normalized_source}")

        result = {
            key: self._rewrite_known_paths(
                item,
                contextual_inputs_validated=contextual_inputs_validated,
                source_relative=source_relative,
            )
            for key, item in value.items()
        }
        path_value = result.get("path")
        target = self._resolve_reference(path_value) if isinstance(path_value, str) else None
        if target is not None:
            result["path"] = target.path
            if "sha256" in result:
                result["sha256"] = target.sha256
        elif isinstance(path_value, str) and "sha256" in result:
            unavailable = self._unavailable_raw_reference(
                path_value, result.get("sha256")
            )
            if unavailable is not None:
                result.update(unavailable)

        for key, item in list(result.items()):
            if not isinstance(item, str):
                continue
            normalized = self.sanitizer.normalize_string(
                item,
                path_context=(
                    key in PATHISH_KEYS
                    or key.endswith(("_path", "_root", "_file", "_artifact"))
                ),
            )
            target = self._resolve_reference(normalized)
            if target is not None:
                result[key] = target.path
                stem = key[:-5] if key.endswith("_path") else key
                for digest_key in (f"{stem}_sha256", f"{stem}_file_sha256"):
                    if digest_key in result:
                        result[digest_key] = target.sha256
            else:
                result[key] = normalized

        inputs = result.get("inputs")
        if isinstance(inputs, list):
            rewritten: list[dict[str, str]] = []
            for index, item in enumerate(inputs):
                if not isinstance(item, dict):
                    raise BuildError(f"invalid provenance input at index {index}")
                path_value = item.get("path")
                if not isinstance(path_value, str):
                    raise BuildError(f"provenance input {index} has no path")
                normalized = self.sanitizer.normalize_string(path_value, path_context=True)
                target = self._resolve_reference(normalized)
                if target is None:
                    indexed = self._indexed_raw_reference(normalized, item.get("sha256"))
                    if indexed is not None:
                        rewritten.append(indexed)
                    else:
                        unavailable = self._unavailable_raw_reference(
                            normalized, item.get("sha256")
                        )
                        if unavailable is not None:
                            rewritten.append(unavailable)
                        else:
                            external = self._unavailable_external_data_reference(
                                normalized, item.get("sha256")
                            )
                            if external is not None:
                                rewritten.append(external)
                            else:
                                self._raise_for_missing_input(
                                    normalized,
                                    source_relative=source_relative,
                                )
                else:
                    rewritten.append({"path": target.path, "sha256": target.sha256})
            rewritten.sort(key=lambda item: (item["path"], item["sha256"]))
            result["inputs"] = rewritten
            digest = sha256_bytes(canonical_json(rewritten).encode("ascii"))
            if "input_set_sha256" in result:
                result["input_set_sha256"] = digest
            if "input_manifest_sha256" in result:
                result["input_manifest_sha256"] = digest
        return result

    def _raise_for_missing_input(
        self,
        relative: str,
        *,
        source_relative: str | None,
    ) -> None:
        if source_relative is None:
            raise _UnresolvedReference(
                f"provenance references an omitted file: {relative}"
            )
        if relative in getattr(self, "omitted_auxiliary_paths", set()):
            raise _IntentionallyOmittedReference(
                f"review dependency was intentionally omitted: {relative}"
            )
        if relative in getattr(self, "planned_auxiliary_paths", set()):
            raise _UnresolvedReference(
                f"provenance dependency is not released yet: {relative}"
            )
        if self._source_path(relative).is_file():
            raise BuildError(f"provenance input is not scheduled for release: {relative}")
        raise BuildError(f"provenance input does not exist: {relative}")

    def _resolve_contextual_inputs(
        self,
        value: dict[str, Any],
        source_relative: str | None,
    ) -> dict[str, Any]:
        inputs = value.get("inputs")
        if source_relative is None or not isinstance(inputs, list):
            return value

        source_input_digest = sha256_bytes(canonical_json(inputs).encode("ascii"))
        for digest_key in ("input_set_sha256", "input_manifest_sha256"):
            if digest_key in value and value[digest_key] != source_input_digest:
                raise BuildError(
                    f"provenance {digest_key} is stale in {source_relative}"
                )

        resolved_inputs: list[Any] = []
        for index, item in enumerate(inputs):
            if not isinstance(item, dict):
                raise BuildError(f"invalid provenance input at index {index}")
            path = item.get("path")
            if not isinstance(path, str):
                raise BuildError(f"provenance input {index} has no path")
            resolved_path = self._resolve_contextual_input_path(
                path,
                source_relative=source_relative,
            )
            digest = item.get("sha256")
            self._validate_source_input_digest(resolved_path, digest)
            resolved_item = dict(item)
            resolved_item["path"] = resolved_path
            resolved_inputs.append(resolved_item)

        resolved = dict(value)
        resolved["inputs"] = resolved_inputs
        return resolved

    def _resolve_contextual_input_tree(
        self,
        value: Any,
        source_relative: str,
    ) -> Any:
        if isinstance(value, list):
            return [
                self._resolve_contextual_input_tree(item, source_relative)
                for item in value
            ]
        if not isinstance(value, dict):
            return value
        resolved = self._resolve_contextual_inputs(value, source_relative)
        return {
            key: self._resolve_contextual_input_tree(item, source_relative)
            for key, item in resolved.items()
        }

    def _resolve_contextual_input_path(
        self,
        path: str,
        *,
        source_relative: str,
    ) -> str:
        normalized = self.sanitizer.normalize_string(path, path_context=True)
        source = self._canonical_repository_path(source_relative)
        contextual = self._canonical_repository_path(
            str(PurePosixPath(source).parent / normalized)
        )
        try:
            direct = self._canonical_repository_path(normalized)
        except BuildError:
            direct = None

        candidates = {
            candidate
            for candidate in (direct, contextual)
            if candidate is not None and self._source_reference_exists(candidate)
        }
        if len(candidates) > 1:
            raise BuildError(
                f"ambiguous provenance input path from {source}: {path}"
            )
        if candidates:
            return candidates.pop()

        actual_candidates = {
            candidate
            for candidate in (direct, contextual)
            if candidate is not None and self._source_path(candidate).is_file()
        }
        if len(actual_candidates) > 1:
            raise BuildError(
                f"ambiguous provenance input path from {source}: {path}"
            )
        if actual_candidates:
            return actual_candidates.pop()
        if direct is not None and PurePosixPath(direct).parts[0] in {
            "experiments",
            "external-data",
            "manifests",
            "paper",
            "results",
            "tables",
        }:
            return direct
        return contextual

    @staticmethod
    def _canonical_repository_path(path: str) -> str:
        if not path or "\\" in path or "\x00" in path:
            raise BuildError(f"invalid provenance input path: {path!r}")
        pure = PurePosixPath(path)
        if pure.is_absolute():
            raise BuildError(f"absolute provenance input path: {path}")

        parts: list[str] = []
        for part in pure.parts:
            if part in {"", "."}:
                continue
            if part == "..":
                if not parts:
                    raise BuildError(f"provenance input escapes repository: {path}")
                parts.pop()
                continue
            parts.append(part)
        if not parts:
            raise BuildError(f"invalid provenance input path: {path!r}")
        return PurePosixPath(*parts).as_posix()

    def _source_reference_exists(self, relative: str) -> bool:
        if (
            relative in self.references
            or relative in self.records
            or relative in getattr(self, "raw_source_index", {})
            or relative in getattr(self, "planned_auxiliary_paths", set())
        ):
            return True
        return False

    def _source_path(self, relative: str) -> Path:
        repository = self.repository.resolve()
        path = repository.joinpath(*PurePosixPath(relative).parts)
        try:
            path.resolve(strict=False).relative_to(repository)
        except ValueError as error:
            raise BuildError(
                f"provenance input escapes repository: {relative}"
            ) from error
        return path

    def _source_digest(self, relative: str) -> str:
        cache = getattr(self, "source_digest_cache", None)
        if cache is None:
            cache = {}
            self.source_digest_cache = cache
        source = self._source_path(relative)
        stat = source.stat()
        cached = cache.get(relative)
        if cached is not None and cached[:2] == (stat.st_size, stat.st_mtime_ns):
            return cached[2]
        digest = sha256_file(source)
        final_stat = source.stat()
        if (stat.st_size, stat.st_mtime_ns) != (
            final_stat.st_size,
            final_stat.st_mtime_ns,
        ):
            raise BuildError(f"source changed while hashing: {relative}")
        cache[relative] = (final_stat.st_size, final_stat.st_mtime_ns, digest)
        return digest

    def _validate_source_input_digest(self, relative: str, digest: Any) -> None:
        target = self._resolve_reference(relative)
        if target is not None and digest == target.sha256:
            return
        source = self._source_path(relative)
        if not source.is_file():
            return
        if not isinstance(digest, str) or not HASH_PATTERN.fullmatch(digest):
            raise BuildError(f"provenance input hash is invalid: {relative}")
        if self._source_digest(relative) != digest:
            raise BuildError(f"provenance input hash is stale: {relative}")

    def _resolve_reference(self, path: str) -> ReferenceTarget | None:
        target = self.references.get(path)
        if target is not None:
            return target
        record = self.records.get(path)
        if record is not None:
            return ReferenceTarget(record.path, record.sha256)
        return None

    def _indexed_raw_reference(self, path: str, digest: Any) -> dict[str, Any] | None:
        if self.tier != "review" or self.raw_index_record is None:
            return None
        entry = self.raw_source_index.get(path)
        if entry is None:
            return None
        if not isinstance(digest, str) or digest != entry["sha256"]:
            raise BuildError(f"indexed raw input hash is stale: {path}")
        if entry["release_status"] != "indexed_not_released":
            return None
        return {
            "availability": "indexed_not_released",
            "index": {
                "path": self.raw_index_record.path,
                "sha256": self.raw_index_record.sha256,
            },
            "path": path,
            "sha256": digest,
        }

    def _unavailable_raw_reference(
        self, path: str, digest: Any
    ) -> dict[str, Any] | None:
        if not path.startswith(f"{RAW_ROOT.as_posix()}/"):
            return None
        if path in getattr(self, "raw_source_index", {}):
            return None
        if self._source_path(path).is_file():
            return None
        if not isinstance(digest, str) or not HASH_PATTERN.fullmatch(digest):
            raise BuildError(f"unavailable raw input hash is invalid: {path}")
        return {
            "availability": UNAVAILABLE_RAW_STATUS,
            "path": path,
            "sha256": digest,
        }

    def _is_valid_indexed_raw_reference(self, item: Mapping[str, Any]) -> bool:
        if self.tier != "review" or self.raw_index_record is None:
            return False
        path = item.get("path")
        digest = item.get("sha256")
        index = item.get("index")
        if (
            not isinstance(path, str)
            or not isinstance(digest, str)
            or item.get("availability") != "indexed_not_released"
            or not isinstance(index, dict)
            or index.get("path") != self.raw_index_record.path
            or index.get("sha256") != self.raw_index_record.sha256
        ):
            return False
        entry = self.raw_source_index.get(path)
        return bool(
            entry
            and entry.get("sha256") == digest
            and entry.get("release_status") == "indexed_not_released"
        )

    def _is_valid_unavailable_raw_reference(self, item: Mapping[str, Any]) -> bool:
        path = item.get("path")
        digest = item.get("sha256")
        return bool(
            isinstance(path, str)
            and path.startswith(f"{RAW_ROOT.as_posix()}/")
            and path not in getattr(self, "raw_source_index", {})
            and not self._source_path(path).is_file()
            and isinstance(digest, str)
            and HASH_PATTERN.fullmatch(digest)
            and item.get("availability") == UNAVAILABLE_RAW_STATUS
        )

    @staticmethod
    def _unavailable_external_data_reference(
        path: str, digest: Any
    ) -> dict[str, Any] | None:
        if not path.startswith("external-data/"):
            return None
        if not isinstance(digest, str) or not HASH_PATTERN.fullmatch(digest):
            raise BuildError(f"external data input hash is invalid: {path}")
        return {
            "availability": "public_dataset_cache_not_in_checkout",
            "path": path,
            "sha256": digest,
        }

    @staticmethod
    def _is_valid_unavailable_external_data_reference(
        item: Mapping[str, Any],
    ) -> bool:
        path = item.get("path")
        digest = item.get("sha256")
        return bool(
            isinstance(path, str)
            and path.startswith("external-data/")
            and isinstance(digest, str)
            and HASH_PATTERN.fullmatch(digest)
            and item.get("availability")
            == "public_dataset_cache_not_in_checkout"
        )

    def _record_inventory(
        self, *, role: str, path_prefix: str
    ) -> list[dict[str, str]]:
        return [
            {"path": path, "sha256": record.sha256}
            for path, record in sorted(self.records.items())
            if record.role == role and path.startswith(path_prefix)
        ]

    def _indexed_raw_inventory(
        self, *, role: str, path_prefix: str
    ) -> list[dict[str, str]]:
        filenames = {
            "run-manifest": "manifest.jsonl",
            "run-summary": "summary.jsonl",
        }
        filename = filenames[role]
        return [
            {"path": path, "sha256": entry["sha256"]}
            for path, entry in sorted(self.raw_source_index.items())
            if path.startswith(path_prefix) and PurePosixPath(path).name == filename
        ]

    def _refresh_grouped_provenance(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._refresh_grouped_provenance(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {
            key: self._refresh_grouped_provenance(item)
            for key, item in value.items()
        }

        grouped_sources = {
            "evaluation_manifests": "run-manifest",
            "evaluation_summaries": "run-summary",
        }
        for key, role in grouped_sources.items():
            descriptor = result.get(key)
            if not isinstance(descriptor, dict):
                continue
            prefix = "results/raw/linear_audit/full/evaluation/"
            if self.tier == "review":
                if self.raw_index_record is None:
                    raise BuildError("review raw index is not initialized")
                inventory = self._indexed_raw_inventory(role=role, path_prefix=prefix)
                descriptor["availability"] = "indexed_source_inputs"
                descriptor["index"] = {
                    "path": self.raw_index_record.path,
                    "sha256": self.raw_index_record.sha256,
                }
            else:
                inventory = self._record_inventory(role=role, path_prefix=prefix)
            descriptor["file_count"] = len(inventory)
            descriptor["sha256"] = sha256_bytes(
                canonical_json(inventory).encode("ascii")
            )

        path = result.get("path")
        if isinstance(path, str) and "raw_input_set_sha256" in result:
            target_path = self._stage_path(path)
            if target_path.is_file() and path.endswith(".json"):
                target_value = json.loads(target_path.read_text(encoding="utf-8"))
                digest = target_value.get("input_set_sha256")
                if isinstance(digest, str):
                    result["raw_input_set_sha256"] = digest

        if "raw_input_set_sha256" in result and isinstance(result.get("inputs"), list):
            for item in result["inputs"]:
                if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                    continue
                target_path = self._stage_path(item["path"])
                if not target_path.is_file() or target_path.suffix != ".json":
                    continue
                target_value = json.loads(target_path.read_text(encoding="utf-8"))
                digest = target_value.get("input_set_sha256")
                if isinstance(digest, str):
                    result["raw_input_set_sha256"] = digest
                    break
        return result

    def _standardize_grouped_sidecar_inputs(self, value: dict[str, Any]) -> dict[str, Any]:
        grouped = value.get("inputs")
        if not isinstance(grouped, dict):
            return value
        explicit: dict[str, str] = {}

        def collect(item: Any) -> None:
            if isinstance(item, list):
                for child in item:
                    collect(child)
                return
            if not isinstance(item, dict):
                return
            path = item.get("path")
            digest = item.get("sha256")
            if isinstance(path, str) and isinstance(digest, str) and path in self.records:
                explicit[path] = self.records[path].sha256
            for child in item.values():
                collect(child)

        collect(grouped)
        collect(value.get("generator"))
        if self.tier == "review":
            if self.raw_index_record is None:
                raise BuildError("review raw index is not initialized")
            explicit[self.raw_index_record.path] = self.raw_index_record.sha256
        for role in ("run-manifest", "run-summary"):
            for item in self._record_inventory(
                role=role,
                path_prefix="results/raw/linear_audit/full/evaluation/",
            ):
                explicit[item["path"]] = item["sha256"]
        standardized = dict(value)
        standardized["input_groups"] = grouped
        standardized["inputs"] = [
            {"path": path, "sha256": digest}
            for path, digest in sorted(explicit.items())
        ]
        standardized["input_set_sha256"] = sha256_bytes(
            canonical_json(standardized["inputs"]).encode("ascii")
        )
        return standardized

    def _process_auxiliary_raw_files(self, raw_files: Sequence[Path]) -> None:
        auxiliary = [
            (path, self._raw_relative(path))
            for path in raw_files
            if path.name not in {"manifest.jsonl", "raw.jsonl", "summary.jsonl"}
        ]
        skipped = {
            relative
            for source, relative in auxiliary
            if self.tier == "review"
            and not self.hydrate_raw
            and source.stat().st_size > REVIEW_AUXILIARY_MAX_BYTES
        }
        self.omitted_auxiliary_paths = set(skipped)
        pending = [
            (source, relative)
            for source, relative in auxiliary
            if relative not in skipped
            and not (
                source.name.endswith(".sha256")
                and relative.removesuffix(".sha256") in skipped
            )
        ]
        self.planned_auxiliary_paths = {relative for _, relative in pending}
        parallel_npz = [
            (source, relative)
            for source, relative in pending
            if source.suffix.lower() == ".npz"
        ]
        if len(parallel_npz) >= NPZ_PROCESS_POOL_MIN_FILES:
            self._process_npz_payloads_parallel(parallel_npz)
            released_npz = {relative for _, relative in parallel_npz}
            pending = [
                (source, relative)
                for source, relative in pending
                if relative not in released_npz
            ]
        while pending:
            deferred: list[tuple[Path, str]] = []
            last_error: _UnresolvedReference | None = None
            progress = False
            for source, relative in pending:
                try:
                    self._process_auxiliary_raw_file(source, relative)
                except _IntentionallyOmittedReference:
                    self.planned_auxiliary_paths.discard(relative)
                    self.omitted_auxiliary_paths.add(relative)
                    progress = True
                except _UnresolvedReference as error:
                    deferred.append((source, relative))
                    last_error = error
                else:
                    progress = True
            if not progress:
                raise last_error or BuildError("raw auxiliary dependency cycle")
            pending = deferred

    def _process_npz_payloads_parallel(
        self,
        payloads: Sequence[tuple[Path, str]],
    ) -> None:
        tasks: list[tuple[str, str, str, tuple[str, ...]]] = []
        for source, relative in payloads:
            destination = self._stage_path(relative)
            tasks.append(
                (
                    str(source),
                    str(destination),
                    relative,
                    self.identity_scanner.identity_terms,
                )
            )
        with ProcessPoolExecutor(max_workers=NPZ_PROCESS_POOL_WORKERS) as executor:
            results = executor.map(_scan_and_stage_npz, tasks, chunksize=8)
            for relative, digest, size in results:
                record = FileRecord(
                    path=relative,
                    sha256=digest,
                    size_bytes=size,
                    role="raw-fixture",
                )
                self.records[relative] = record
                self.references[relative] = ReferenceTarget(relative, digest)
                self.identity_scanner.scanned_paths.add(relative)

    def _process_auxiliary_raw_file(self, source: Path, relative: str) -> None:
        if source.name.endswith(".sha256"):
            payload_relative = relative.removesuffix(".sha256")
            if payload_relative in getattr(self, "omitted_auxiliary_paths", set()):
                raise _IntentionallyOmittedReference(
                    f"checksum payload was intentionally omitted: {payload_relative}"
                )
            released_payload = self.references.get(payload_relative)
            if released_payload is None:
                raise _UnresolvedReference(
                    f"checksum payload was not released: {payload_relative}"
                )
            self._validate_checksum_sidecar(source, payload_relative)
            data = (
                f"{released_payload.sha256}  "
                f"{PurePosixPath(released_payload.path).name}\n"
            ).encode("ascii")
            self._write_bytes(
                relative,
                data,
                role="raw-checksum",
                source_relative=relative,
            )
            return
        if source.suffix == ".jsonl":
            self._process_raw_jsonl(source, project_metrics=False)
            return
        if source.suffix == ".json":
            try:
                value = json.loads(source.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise BuildError(f"cannot parse {relative}: {error}") from error
            value = self._resolve_contextual_input_tree(value, relative)
            value = self._rewrite_known_paths(
                self.sanitizer.sanitize(value),
                contextual_inputs_validated=True,
                source_relative=relative,
            )
            data = _json_bytes(value)
        else:
            data = source.read_bytes()
        self._write_bytes(
            relative,
            data,
            role="raw-fixture",
            source_relative=relative,
        )

    def _validate_checksum_sidecar(
        self,
        source: Path,
        payload_relative: str,
    ) -> None:
        try:
            fields = source.read_text(encoding="ascii").split()
        except UnicodeDecodeError as error:
            raise BuildError(f"checksum sidecar is not ASCII: {source}") from error
        expected_name = PurePosixPath(payload_relative).name
        if (
            len(fields) != 2
            or not HASH_PATTERN.fullmatch(fields[0])
            or fields[1].removeprefix("*") != expected_name
        ):
            raise BuildError(f"checksum sidecar is invalid: {source}")
        if fields[0] != self._source_digest(payload_relative):
            raise BuildError(f"checksum sidecar is stale: {source}")

    def _process_small_jsonl(self, source: Path, role: str) -> FileRecord:
        relative = relative_posix(source, self.repository)
        records: list[dict[str, Any]] = []
        with source.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as error:
                    raise BuildError(f"cannot parse {relative}:{line_number}: {error}") from error
                if not isinstance(value, dict):
                    raise BuildError(f"JSONL record is not an object: {relative}:{line_number}")
                value = self._resolve_contextual_input_tree(value, relative)
                value = self.sanitizer.sanitize(value)
                value = self._rewrite_known_paths(
                    value,
                    contextual_inputs_validated=True,
                    source_relative=relative,
                )
                if source.name == "manifest.jsonl":
                    self._rewrite_run_id(value, relative)
                records.append(value)
        data = b"".join(_json_bytes(record, pretty=False) for record in records)
        return self._write_bytes(
            relative,
            data,
            role=role,
            source_relative=relative,
        )

    @contextlib.contextmanager
    def _compressed_writer(self, destination: Path) -> Iterator[BinaryIO]:
        if self.compression == "gzip":
            with destination.open("wb") as raw_handle:
                with gzip.GzipFile(
                    filename="",
                    mode="wb",
                    compresslevel=9,
                    fileobj=raw_handle,
                    mtime=0,
                ) as compressed:
                    yield compressed
            return

        with destination.open("wb") as output_handle, subprocess.Popen(
            ["zstd", "-q", "-10", "-T1", "-c"],
            stdin=subprocess.PIPE,
            stdout=output_handle,
            stderr=subprocess.PIPE,
        ) as process:
            if process.stdin is None:
                raise BuildError("failed to open zstd input stream")
            try:
                yield process.stdin
            except BaseException:
                process.stdin.close()
                process.kill()
                process.wait()
                raise
            else:
                process.stdin.close()
                stderr = (
                    process.stderr.read().decode("utf-8", errors="replace")
                    if process.stderr
                    else ""
                )
                return_code = process.wait()
                if return_code:
                    raise BuildError(
                        f"zstd failed with status {return_code}: {stderr.strip()}"
                    )

    def _process_raw_jsonl(self, source: Path, *, project_metrics: bool = True) -> None:
        source_relative = relative_posix(source, self.repository)
        destination_relative = source_relative + self.compression_extension
        destination = self._stage_path(destination_relative)
        run_directory = str(PurePosixPath(source_relative).parent)
        run_map = self.run_id_maps.get(run_directory, {})
        logical_digest = hashlib.sha256()
        logical_size = 0
        record_count = 0
        file_removed_fields: set[str] = set()
        with self._compressed_writer(destination) as compressed:
            with source.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, 1):
                    if not line.strip():
                        continue
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError as error:
                        raise BuildError(
                            f"cannot parse {source_relative}:{line_number}: {error}"
                        ) from error
                    if not isinstance(value, dict):
                        raise BuildError(
                            f"JSONL record is not an object: {source_relative}:{line_number}"
                        )
                    value = self.sanitizer.sanitize(value)
                    if project_metrics:
                        value, removed_fields = project_raw_record(value)
                        file_removed_fields.update(removed_fields)
                        self.removed_raw_fields.update(removed_fields)
                    old_run_id = value.get("run_id")
                    if isinstance(old_run_id, str) and old_run_id in run_map:
                        value["run_id"] = run_map[old_run_id]
                    data = _json_bytes(value, pretty=False)
                    self.identity_scanner.scan_bytes(source_relative, data, count=False)
                    logical_digest.update(data)
                    logical_size += len(data)
                    compressed.write(data)
                    record_count += 1
        self.identity_scanner.scanned_paths.add(source_relative)
        record = self._record_file(destination_relative, role="compact-raw")
        self.references[source_relative] = ReferenceTarget(record.path, record.sha256)
        self.raw_inventory.append(
            {
                "archive_path": record.path,
                "archive_sha256": record.sha256,
                "archive_size_bytes": record.size_bytes,
                "compression": self.compression,
                "record_count": record_count,
                "removed_composite_metric_fields": sorted(file_removed_fields),
                "source_path": source_relative,
                "uncompressed_sha256": logical_digest.hexdigest(),
                "uncompressed_size_bytes": logical_size,
            }
        )

    def _write_review_raw_index(
        self, raw_files: Sequence[Path], selected_directories: Sequence[Path]
    ) -> None:
        selected = set(selected_directories)
        entries: list[dict[str, Any]] = []
        source_bindings: list[dict[str, str]] = []
        omitted_count = 0
        for source in raw_files:
            relative = self._raw_relative(source)
            digest = self._source_digest(relative)
            target = self.references.get(relative)
            if source.parent in selected and source.name in {
                "manifest.jsonl",
                "raw.jsonl",
                "summary.jsonl",
            }:
                status = (
                    "complete_transformed_copy_released"
                    if self.hydrate_raw
                    else "representative_transformed_copy_released"
                )
            elif target is not None:
                status = "supporting_anonymized_copy_released"
            else:
                status = "indexed_not_released"
                omitted_count += 1
            entry: dict[str, Any] = {
                "path": relative,
                "release_status": status,
                "sha256": digest,
                "size_bytes": source.stat().st_size,
            }
            if target is not None:
                entry["released_copy"] = {
                    "path": target.path,
                    "sha256": target.sha256,
                }
            entries.append(entry)
            source_bindings.append({"path": relative, "sha256": digest})
            self.raw_source_index[relative] = entry

        if self.hydrate_raw and omitted_count:
            omitted = [
                item["path"]
                for item in entries
                if item["release_status"] == "indexed_not_released"
            ]
            raise BuildError(
                "hydrated review omitted raw files: " + ", ".join(omitted[:3])
            )

        selected_paths = tuple(
            relative_posix(directory, self.repository)
            for directory in selected_directories
        )
        self.review_run_directories = selected_paths
        index = {
            "file_count": len(entries),
            "files": entries,
            "hash_semantics": (
                "source sha256 values bind original experiment outputs before "
                "anonymity-preserving release transformation"
            ),
            "indexed_not_released_count": omitted_count,
            "schema_version": SCHEMA_VERSION,
            "selection": {
                "algorithm": (
                    "all-complete-runs-v1"
                    if self.hydrate_raw
                    else REVIEW_SELECTION_ALGORITHM
                ),
                "candidate_filter": (
                    "all complete runs excluding source bundle archives"
                    if self.hydrate_raw
                    else "all complete runs excluding source bundles and results/raw/smoke"
                ),
                "grouping_key": (
                    "none; all complete runs selected"
                    if self.hydrate_raw
                    else "first path component below results/raw"
                ),
                "selected_run_count": len(selected_paths),
                "selected_run_directories": list(selected_paths),
            },
            "source_input_set_sha256": sha256_bytes(
                canonical_json(source_bindings).encode("ascii")
            ),
        }
        self.raw_index_record = self._write_bytes(
            REVIEW_RAW_INDEX_PATH,
            _json_bytes(index),
            role="raw-source-index",
        )

    def _release_raw_files(self) -> list[Path]:
        raw_root = self.repository / "results" / "raw"
        if not raw_root.exists():
            return []
        if raw_root.is_symlink() or not raw_root.is_dir():
            raise BuildError("results/raw is missing")
        raw_files: list[tuple[str, Path]] = []
        for path in raw_root.rglob("*"):
            if path.is_symlink():
                raise BuildError(f"raw release input cannot be a symlink: {path}")
            if (
                not path.is_file()
                or path.name in {".DS_Store", ".gitkeep"}
                or path.relative_to(raw_root).parts[0] == "bundles"
                or (
                    path.relative_to(raw_root).parts[0] == "smoke"
                    and not self.hydrate_raw
                )
            ):
                continue
            raw_files.append((self._raw_relative(path), path))
        raw_files.sort(key=lambda item: item[0])
        return [path for _, path in raw_files]

    def _raw_relative(self, path: Path) -> str:
        if path.is_symlink():
            raise BuildError(f"raw release input cannot be a symlink: {path}")
        root_parts = self.repository.parts
        path_parts = path.parts
        relative_parts = path_parts[len(root_parts) :]
        if path_parts[: len(root_parts)] != root_parts or not relative_parts:
            raise BuildError(f"raw release input escapes repository: {path}")
        return PurePosixPath(*relative_parts).as_posix()

    def _copy_raw(self) -> None:
        raw_root = self.repository / "results" / "raw"
        raw_files = self._release_raw_files()
        if self.hydrate_raw and not raw_files:
            raise BuildError("raw hydration requires a non-empty results/raw tree")
        self._process_auxiliary_raw_files(raw_files)

        run_directories = sorted(
            {path.parent for path in raw_files if path.name == "raw.jsonl"},
            key=lambda path: relative_posix(path, self.repository),
        )
        selected_directories: Sequence[Path] = run_directories
        if self.tier == "review" and not self.hydrate_raw:
            selected_directories = select_review_run_directories(raw_root)
            studies = {
                path.relative_to(raw_root).parts[0]
                for path in raw_files
                if path.name == "raw.jsonl"
            }
            selected_studies = {
                path.relative_to(raw_root).parts[0]
                for path in selected_directories
            }
            missing_studies = sorted(studies - selected_studies)
            if missing_studies:
                raise BuildError(
                    "no complete review trajectory for studies: "
                    + ", ".join(missing_studies)
                )

        for directory in selected_directories:
            for filename, role in (
                ("manifest.jsonl", "run-manifest"),
                ("summary.jsonl", "run-summary"),
            ):
                source = directory / filename
                if not source.is_file():
                    raise BuildError(f"incomplete raw run: {relative_posix(directory, self.repository)}")
                self._process_small_jsonl(source, role)
            self._process_raw_jsonl(directory / "raw.jsonl")
        if self.tier == "review":
            self._write_review_raw_index(raw_files, selected_directories)

    def _copy_derived(self) -> None:
        derived_root = self.repository / "results" / "derived"
        if not derived_root.is_dir():
            raise BuildError("results/derived is missing")
        sources = sorted(
            (
                path
                for path in derived_root.rglob("*")
                if path.is_file()
                and path.name != ".gitkeep"
                and not path.name.endswith(".provenance.json")
            ),
            key=lambda path: relative_posix(path, self.repository),
        )
        pending_json: dict[str, tuple[Path, Any]] = {}
        for source in sources:
            relative = relative_posix(source, self.repository)
            if source.suffix == ".json":
                try:
                    value = json.loads(source.read_text(encoding="utf-8"))
                except json.JSONDecodeError as error:
                    raise BuildError(f"cannot parse {relative}: {error}") from error
                value = self._resolve_contextual_input_tree(value, relative)
                pending_json[relative] = (source, self.sanitizer.sanitize(value))
                continue
            elif source.suffix.lower() in TEXT_SUFFIXES:
                data = self.sanitizer.normalize_string(
                    source.read_text(encoding="utf-8")
                ).encode("utf-8")
            else:
                data = source.read_bytes()
            self._write_bytes(
                relative,
                data,
                role="derived",
                source_relative=relative,
            )

        while pending_json:
            deferred: dict[str, tuple[Path, Any]] = {}
            progress = False
            last_error: BuildError | None = None
            for relative, (source, value) in pending_json.items():
                try:
                    rewritten = self._rewrite_known_paths(
                        value,
                        contextual_inputs_validated=True,
                    )
                    rewritten = self._refresh_grouped_provenance(rewritten)
                except BuildError as error:
                    if "provenance references an omitted file" not in str(error):
                        raise BuildError(
                            f"{error} while rewriting {relative}"
                        ) from error
                    deferred[relative] = (source, value)
                    last_error = error
                    continue
                self._write_bytes(
                    relative,
                    _json_bytes(rewritten),
                    role="derived",
                    source_relative=relative,
                )
                progress = True
            if not progress:
                raise last_error or BuildError("derived artifact dependency cycle")
            pending_json = deferred

    def _provenance_sources(self) -> tuple[Path, ...]:
        roots = (
            self.repository / "results" / "derived",
            self.repository / "paper",
            self.repository / "tables" / "generated",
        )
        sources: list[Path] = []
        for root in roots:
            if root.is_dir():
                sources.extend(root.rglob("*.provenance.json"))
        return tuple(sorted(sources, key=lambda path: relative_posix(path, self.repository)))

    def _write_provenance_sidecars(self) -> None:
        written_artifacts: set[str] = set()
        pending: dict[str, tuple[Path, dict[str, Any]]] = {}
        for source in self._provenance_sources():
            relative = relative_posix(source, self.repository)
            try:
                value = json.loads(source.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise BuildError(f"cannot parse {relative}: {error}") from error
            if not isinstance(value, dict):
                raise BuildError(f"provenance sidecar is not an object: {relative}")
            pending[relative] = (source, value)

        # Paper artifacts may bind both a derived result and that result's
        # provenance sidecar.  Resolve such dependencies in topological passes
        # instead of relying on lexicographic paper/results ordering.
        while pending:
            deferred: dict[str, tuple[Path, dict[str, Any]]] = {}
            progress = False
            last_error: BuildError | None = None
            for relative, (source, source_value) in pending.items():
                resolved_source = self._resolve_contextual_input_tree(
                    source_value, relative
                )
                value = self.sanitizer.sanitize(resolved_source)
                artifact = value.get("artifact")
                if not isinstance(artifact, str):
                    artifact = relative.removesuffix(".provenance.json")
                artifact = self.sanitizer.normalize_string(artifact, path_context=True)
                artifact_target = self.references.get(artifact)
                if artifact_target is None:
                    raise BuildError(f"provenance artifact is omitted: {artifact}")
                value["artifact"] = artifact_target.path
                value["artifact_sha256"] = artifact_target.sha256
                try:
                    value = self._rewrite_known_paths(
                        value,
                        contextual_inputs_validated=True,
                    )
                    value = self._refresh_grouped_provenance(value)
                    value = self._standardize_grouped_sidecar_inputs(value)
                except BuildError as error:
                    if "provenance references an omitted file" not in str(error):
                        raise BuildError(
                            f"{error} while rewriting {relative}"
                        ) from error
                    deferred[relative] = (source, source_value)
                    last_error = error
                    continue
                self._write_bytes(
                    relative,
                    _json_bytes(value),
                    role="provenance",
                    source_relative=relative,
                )
                written_artifacts.add(artifact_target.path)
                progress = True
            if not progress:
                raise last_error or BuildError("provenance sidecar dependency cycle")
            pending = deferred

        # Full aggregates embed their complete input inventory but historically
        # did not all receive sidecars.  Give every released aggregate the same
        # independently verifiable binding.
        for relative, record in sorted(self.records.items()):
            if record.role != "derived" or not relative.endswith(".json"):
                continue
            if relative in written_artifacts:
                continue
            value = json.loads(self._stage_path(relative).read_text(encoding="utf-8"))
            inputs = value.get("inputs") if isinstance(value, dict) else None
            if not isinstance(inputs, list) or not inputs:
                continue
            sidecar_relative = relative + ".provenance.json"
            sidecar = {
                "artifact": relative,
                "artifact_sha256": record.sha256,
                "inputs": inputs,
                "schema_version": SCHEMA_VERSION,
            }
            self._write_bytes(
                sidecar_relative,
                _json_bytes(sidecar),
                role="provenance",
            )

    def _collect_unavailable_raw_references(
        self,
    ) -> tuple[int, dict[str, str]]:
        occurrence_count = 0
        unique: dict[str, str] = {}

        def collect(value: Any) -> None:
            nonlocal occurrence_count
            if isinstance(value, list):
                for item in value:
                    collect(item)
                return
            if not isinstance(value, dict):
                return
            if value.get("availability") == UNAVAILABLE_RAW_STATUS:
                path = value.get("path")
                digest = value.get("sha256")
                if (
                    not isinstance(path, str)
                    or not path.startswith(f"{RAW_ROOT.as_posix()}/")
                    or not isinstance(digest, str)
                    or not HASH_PATTERN.fullmatch(digest)
                ):
                    raise BuildError("invalid unavailable raw reference")
                previous = unique.setdefault(path, digest)
                if previous != digest:
                    raise BuildError(
                        f"conflicting unavailable raw input hashes: {path}"
                    )
                occurrence_count += 1
            for item in value.values():
                collect(item)

        for relative, record in sorted(self.records.items()):
            if (
                record.path == UNAVAILABLE_SOURCE_INDEX_PATH
                or PurePosixPath(relative).suffix.lower() != ".json"
            ):
                continue
            value = json.loads(
                self._stage_path(relative).read_text(encoding="utf-8")
            )
            collect(value)
        return occurrence_count, unique

    def _write_unavailable_source_index(self) -> None:
        occurrence_count, unique = self._collect_unavailable_raw_references()
        value = {
            "files": [
                {"path": path, "sha256": digest}
                for path, digest in sorted(unique.items())
            ],
            "occurrence_count": occurrence_count,
            "schema_version": SCHEMA_VERSION,
            "semantics": (
                "recorded source bindings absent from the local source raw tree; "
                "digests are retained but not independently reverified"
            ),
            "unique_file_count": len(unique),
        }
        self.unavailable_raw_occurrence_count = occurrence_count
        self.unavailable_raw_unique_count = len(unique)
        self.unavailable_source_index_record = self._write_bytes(
            UNAVAILABLE_SOURCE_INDEX_PATH,
            _json_bytes(value),
            role="manifest",
        )

    def _write_release_metadata(self) -> None:
        self._write_unavailable_source_index()
        raw_sources_available = (self.repository / "results" / "raw").is_dir()
        source_manifest = {
            "anonymous_source_tree_sha256": self.source_hash,
            "files": self.source_inventory,
            "schema_version": SCHEMA_VERSION,
        }
        self._write_bytes(
            "manifests/source-tree.json",
            _json_bytes(source_manifest),
            role="manifest",
        )
        raw_manifest = {
            "archives": sorted(self.raw_inventory, key=lambda item: item["source_path"]),
            "compression": self.compression,
            "lossless": False,
            "lossless_for_reported_artifacts": (
                (self.tier == "full" or self.hydrate_raw) and raw_sources_available
            ),
            "projection": {
                "record_envelope": "all fields retained",
                "metric_scalars": "all string, boolean, integer, float, and null values retained",
                "retained_composite_metric_fields": sorted(RETAINED_COMPOSITE_METRICS),
                "removed_composite_metric_fields": sorted(self.removed_raw_fields),
                "schema": "artifact-preserving-jsonl-projection-v1",
            },
            "release_tier": self.tier,
            "schema_version": SCHEMA_VERSION,
        }
        if self.tier == "review":
            if self.raw_index_record is None:
                raise BuildError("review raw index is not initialized")
            raw_manifest["coverage"] = {
                "full_raw_index": {
                    "path": self.raw_index_record.path,
                    "sha256": self.raw_index_record.sha256,
                },
                "scope": (
                    (
                        (
                            HYDRATED_LEGACY_GAPS_STATUS
                            if self.unavailable_raw_unique_count
                            else HYDRATED_COMPLETE_STATUS
                        )
                        if self.hydrate_raw
                        else "representative_trajectories_only"
                    )
                    if raw_sources_available
                    else "derived_artifacts_only"
                ),
                "selected_run_count": len(self.review_run_directories),
                "selection_algorithm": (
                    "all-complete-runs-v1"
                    if self.hydrate_raw
                    else REVIEW_SELECTION_ALGORITHM
                ),
                "unavailable_source_inputs": {
                    "occurrence_count": self.unavailable_raw_occurrence_count,
                    "path": self.unavailable_source_index_record.path,
                    "sha256": self.unavailable_source_index_record.sha256,
                    "unique_file_count": self.unavailable_raw_unique_count,
                },
            }
        self._write_bytes(
            "manifests/compact-raw.json",
            _json_bytes(raw_manifest),
            role="manifest",
        )

        suffix = self.compression_extension
        if self.compression == "zstd":
            unpack = (
                "find results/raw -name '*" + suffix + "' -exec sh -c "
                "'for p do; zstd -q -d -f \"$p\" -o \"${p%" + suffix + "}\"; done' sh {} +"
            )
        else:
            unpack = (
                "find results/raw -name '*" + suffix + "' -exec sh -c "
                "'for p do; gzip -dc \"$p\" > \"${p%" + suffix + "}\"; done' sh {} +"
            )
        if not raw_sources_available:
            introduction = f"""This compact-checkout release contains the anonymous paper,
experiment implementation and configuration, tests, every committed derived
artifact, and the table and figure regeneration inputs.  Seed-level raw outputs
are intentionally stored outside Git and are not included.  `MANIFEST.json`
binds every released file.  The anonymous source-tree digest is
`{self.source_hash}`."""
            raw_notes = f"""No raw trajectory is present in this compact-checkout build.
Provenance entries marked `{UNAVAILABLE_RAW_STATUS}` retain the recorded source
path and SHA-256, but the release does not claim to have independently verified
or locally supplied those inputs.  Re-run the deterministic experiment entry
points to reconstruct them.  Entries marked
`public_dataset_cache_not_in_checkout` likewise identify optional public-data
cache inputs that are fetched by the released loaders rather than shipped in
the bundle."""
        elif self.tier == "review" and self.hydrate_raw:
            introduction = f"""This hydrated review-tier release contains the anonymous
paper, implementation, tests, derived artifacts, and anonymized copies of every
source raw payload.  Original source bundle archives are excluded because they
duplicate these payloads and may contain private local metadata.  `MANIFEST.json`
binds every released file.  The anonymous source-tree digest is
`{self.source_hash}`."""
            raw_notes = f"""The command above restores every compressed raw trajectory.
The released payloads are sufficient to rerun raw-to-figure checks whose
tracked provenance has no declared source-tree gap, without the excluded source
bundle archives.

`{REVIEW_RAW_INDEX_PATH}` binds every source raw payload by its original path and
SHA-256 and binds its anonymized released copy.  Hydrated validation rejects any
`indexed_not_released` entry.  A derived legacy artifact can still declare a
`{UNAVAILABLE_RAW_STATUS}` input when that path is absent from the source raw
tree; such a declaration is counted in `MANIFEST.json` and is not a claim of
independent reproducibility for that legacy artifact."""
        elif self.tier == "review":
            introduction = f"""This review-tier release contains the anonymous paper,
experiment implementation and configuration, tests, every derived artifact,
and the table and figure regeneration inputs.  It intentionally includes only
one deterministic representative raw trajectory per top-level study.
`MANIFEST.json` binds every released file.  The anonymous source-tree digest is
`{self.source_hash}`."""
            raw_notes = f"""The command above restores only the representative trajectories.
It does not reconstruct the full experiment corpus, so the published full
aggregates cannot be regenerated from this smaller tier alone.

`{REVIEW_RAW_INDEX_PATH}` binds every indexed source raw file by its original
path and SHA-256 and records whether an anonymized copy is released.  Provenance
entries marked `indexed_not_released` are deliberately absent and are validated
against that index; they are not claimed as locally available inputs."""
        else:
            introduction = f"""This release contains the anonymous paper, experiment
implementation and configuration, tests, derived tables and figure data, and
artifact-preserving compressed per-round records.  `MANIFEST.json` binds every
released file.  The anonymous source-tree digest is `{self.source_hash}`."""
            raw_notes = """The experiment commands and aggregation entry points are documented in
`experiments/README.md`.  Released provenance binds the compressed records;
newly generated aggregates bind the restored records."""
        readme = f"""# Anonymous supplementary material

{introduction}

## Environment

```sh
python -m venv .venv
.venv/bin/pip install -r experiments/requirements.txt
.venv/bin/python -m pytest -q tests experiments/tests
```

## Raw records

Run the following from the release root before invoking an aggregator.  It
restores each `raw.jsonl` beside its compressed archive without deleting the
archive.

```sh
{unpack}
```

{raw_notes}

## Paper

```sh
make pdf
```

Generated table and figure inputs are under `results/derived`.  Run and source
inventories are under `manifests`.
"""
        self._write_bytes("README.md", readme.encode("utf-8"), role="documentation")

    def _validate_review_raw_index(self) -> dict[str, int]:
        if self.tier != "review":
            return {
                "indexed_raw_files_checked": 0,
                "representative_raw_runs_checked": 0,
            }
        if self.raw_index_record is None:
            raise BuildError("review raw index was not released")
        index_path = self._stage_path(self.raw_index_record.path)
        if sha256_file(index_path) != self.raw_index_record.sha256:
            raise BuildError("review raw index hash is stale")
        value = json.loads(index_path.read_text(encoding="utf-8"))
        files = value.get("files")
        if not isinstance(files, list) or value.get("file_count") != len(files):
            raise BuildError("review raw index file inventory is invalid")
        if self.hydrate_raw and value.get("indexed_not_released_count") != 0:
            raise BuildError("hydrated review raw index contains omitted files")
        source_bindings: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in files:
            if not isinstance(item, dict):
                raise BuildError("review raw index entry is invalid")
            path = item.get("path")
            digest = item.get("sha256")
            size = item.get("size_bytes")
            if (
                not isinstance(path, str)
                or not isinstance(digest, str)
                or not HASH_PATTERN.fullmatch(digest)
                or not isinstance(size, int)
                or size < 0
                or path in seen
            ):
                raise BuildError("review raw index binding is invalid")
            seen.add(path)
            source_bindings.append({"path": path, "sha256": digest})
            if self.raw_source_index.get(path) != item:
                raise BuildError(f"review raw index entry is stale: {path}")
            source_path = self.repository.joinpath(*PurePosixPath(path).parts)
            if not source_path.is_file() or source_path.stat().st_size != size:
                raise BuildError(f"review raw indexed source size is stale: {path}")
            if self._source_digest(path) != digest:
                raise BuildError(f"review raw indexed source hash is stale: {path}")
            released_copy = item.get("released_copy")
            if released_copy is None:
                if self.hydrate_raw:
                    raise BuildError(f"hydrated review raw file is omitted: {path}")
                if item.get("release_status") != "indexed_not_released":
                    raise BuildError(f"review raw index status is invalid: {path}")
                continue
            if not isinstance(released_copy, dict):
                raise BuildError(f"review raw released-copy binding is invalid: {path}")
            released_path = released_copy.get("path")
            released_digest = released_copy.get("sha256")
            record = self.records.get(released_path) if isinstance(released_path, str) else None
            if record is None or record.sha256 != released_digest:
                raise BuildError(f"review raw released-copy hash is stale: {path}")

        expected_digest = sha256_bytes(canonical_json(source_bindings).encode("ascii"))
        if value.get("source_input_set_sha256") != expected_digest:
            raise BuildError("review raw source input-set hash is stale")
        current_paths = {
            self._raw_relative(path)
            for path in self._release_raw_files()
        }
        if current_paths != seen:
            added = sorted(current_paths - seen)
            removed = sorted(seen - current_paths)
            details: list[str] = []
            if added:
                details.append("added=" + ",".join(added[:3]))
            if removed:
                details.append("removed=" + ",".join(removed[:3]))
            raise BuildError(
                "review raw index does not match source tree: " + "; ".join(details)
            )
        selection = value.get("selection")
        expected_algorithm = (
            "all-complete-runs-v1"
            if self.hydrate_raw
            else REVIEW_SELECTION_ALGORITHM
        )
        if (
            not isinstance(selection, dict)
            or selection.get("algorithm") != expected_algorithm
            or selection.get("selected_run_directories")
            != list(self.review_run_directories)
        ):
            raise BuildError("review raw selection metadata is invalid")
        for directory in self.review_run_directories:
            for name in ("manifest.jsonl", "raw.jsonl", "summary.jsonl"):
                if f"{directory}/{name}" not in self.references:
                    raise BuildError(f"review trajectory is incomplete: {directory}")
        return {
            "indexed_raw_files_checked": len(files),
            "representative_raw_runs_checked": len(self.review_run_directories),
        }

    def _validate_unavailable_source_index(self) -> dict[str, int]:
        if self.unavailable_source_index_record is None:
            raise BuildError("unavailable-source index was not released")
        record = self.unavailable_source_index_record
        if sha256_file(self._stage_path(record.path)) != record.sha256:
            raise BuildError("unavailable-source index hash is stale")
        value = json.loads(
            self._stage_path(record.path).read_text(encoding="utf-8")
        )
        occurrence_count, unique = self._collect_unavailable_raw_references()
        expected_files = [
            {"path": path, "sha256": digest}
            for path, digest in sorted(unique.items())
        ]
        if (
            value.get("occurrence_count") != occurrence_count
            or value.get("unique_file_count") != len(unique)
            or value.get("files") != expected_files
        ):
            raise BuildError("unavailable-source index is stale")
        if occurrence_count != self.unavailable_raw_occurrence_count or len(
            unique
        ) != self.unavailable_raw_unique_count:
            raise BuildError("unavailable-source counters are stale")
        return {
            "unavailable_raw_reference_occurrences": occurrence_count,
            "unavailable_raw_unique_files": len(unique),
        }

    def _validate_provenance(self) -> dict[str, int]:
        sidecars = 0
        input_references = 0
        indexed_input_references = 0
        unavailable_input_references = 0
        unavailable_raw_paths: set[str] = set()
        unavailable_external_data_references = 0
        for relative, record in sorted(self.records.items()):
            if record.role != "provenance":
                continue
            sidecars += 1
            value = json.loads(self._stage_path(relative).read_text(encoding="utf-8"))
            artifact = value.get("artifact")
            artifact_digest = value.get("artifact_sha256")
            if not isinstance(artifact, str) or artifact not in self.records:
                raise BuildError(f"sidecar artifact is missing: {relative}")
            if artifact_digest != self.records[artifact].sha256:
                raise BuildError(f"sidecar artifact hash is stale: {relative}")
            inputs = value.get("inputs")
            if not isinstance(inputs, list):
                raise BuildError(f"sidecar inputs are invalid: {relative}")
            for item in inputs:
                if not isinstance(item, dict):
                    raise BuildError(f"sidecar input is invalid: {relative}")
                path = item.get("path")
                digest = item.get("sha256")
                if isinstance(path, str) and path in self.records:
                    if digest != self.records[path].sha256:
                        raise BuildError(f"sidecar input hash is stale: {relative}")
                elif self._is_valid_indexed_raw_reference(item):
                    indexed_input_references += 1
                elif self._is_valid_unavailable_raw_reference(item):
                    unavailable_input_references += 1
                    if isinstance(path, str):
                        unavailable_raw_paths.add(path)
                elif self._is_valid_unavailable_external_data_reference(item):
                    unavailable_external_data_references += 1
                else:
                    raise BuildError(f"sidecar input is missing: {relative}")
                input_references += 1

        paper = self._stage_path("paper/main.tex")
        if not paper.is_file():
            raise BuildError("paper/main.tex was not released")
        paper_text = paper.read_text(encoding="utf-8")
        references_checked = 0
        for match in re.finditer(
            r"\\(?:input|includegraphics)\s*(?:\[[^]]*\])?\s*\{([^}]+)\}",
            paper_text,
        ):
            reference = match.group(1)
            if is_optional_paper_reference(reference):
                continue
            candidate = paper.parent / reference
            if not candidate.suffix:
                choices = (candidate, candidate.with_suffix(".tex"), candidate.with_suffix(".pdf"))
            else:
                choices = (candidate,)
            if not any(path.is_file() for path in choices):
                raise BuildError(f"paper source reference is missing: {reference}")
            references_checked += 1
        return {
            **self._validate_review_raw_index(),
            **self._validate_unavailable_source_index(),
            "indexed_provenance_input_references_checked": indexed_input_references,
            "paper_references_checked": references_checked,
            "provenance_input_references_checked": input_references,
            "provenance_sidecars_checked": sidecars,
            "unavailable_raw_provenance_input_references": (
                unavailable_input_references
            ),
            "unavailable_raw_provenance_unique_files": len(
                unavailable_raw_paths
            ),
            "unavailable_external_data_provenance_input_references": (
                unavailable_external_data_references
            ),
        }

    def _validate_anonymous_author_declarations(self) -> None:
        main = self._stage_path("paper/main.tex")
        text = main.read_text(encoding="utf-8")
        author_declarations = re.findall(r"\\author\s*\{([^}]*)\}", text, flags=re.DOTALL)
        if not author_declarations:
            raise BuildError("paper has no explicit anonymous author declaration")
        for declaration in author_declarations:
            if "anonymous" not in declaration.casefold():
                raise BuildError("paper author declaration is not anonymous")
        for command in ("address", "affiliation", "institution"):
            for declaration in re.findall(
                rf"\\{command}\s*\{{([^}}]*)\}}", text, flags=re.DOTALL
            ):
                if declaration.strip() and "anonymous" not in declaration.casefold():
                    raise BuildError(f"paper {command} declaration is not anonymous")

    def _scan_staging(self) -> None:
        # Raw logical streams were scanned before compression.  Scan all other
        # released bytes after provenance and metadata generation.
        for relative in sorted(self.records):
            if relative in self.identity_scanner.scanned_paths:
                continue
            if relative.endswith((".jsonl.zst", ".jsonl.gz")) or (
                PurePosixPath(relative).suffix.lower() in OPAQUE_GENERATED_SUFFIXES
            ):
                continue
            self.identity_scanner.scan_bytes(relative, self._stage_path(relative).read_bytes())
        self._validate_anonymous_author_declarations()
        self.identity_scanner.raise_for_issues()

    def _write_top_manifest(self, validation: Mapping[str, int]) -> FileRecord:
        total_bytes = sum(record.size_bytes for record in self.records.values())
        if self.unavailable_source_index_record is None:
            raise BuildError("unavailable-source index was not released")
        release_kind = (
            "anonymous_review_supplement"
            if self.tier == "review"
            else "anonymous_compact_supplement"
        )
        validation_status = (
            "passed_with_declared_unavailable_inputs"
            if (
                validation.get("unavailable_raw_reference_occurrences", 0)
                or validation.get(
                    "unavailable_external_data_provenance_input_references", 0
                )
            )
            else "passed"
        )
        manifest = {
            "anonymous_source_tree_sha256": self.source_hash,
            "compression": self.compression,
            "created_utc": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            "files": [dataclasses.asdict(record) for _, record in sorted(self.records.items())],
            "identity_scan": {
                "files_scanned": len(self.identity_scanner.scanned_paths),
                "status": "passed",
            },
            "raw_hydration": {
                "legacy_smoke_workspace_excluded": not self.hydrate_raw,
                "source_bundle_workspace_excluded": True,
                "status": (
                    (
                        HYDRATED_LEGACY_GAPS_STATUS
                        if validation.get("unavailable_raw_unique_files", 0)
                        else HYDRATED_COMPLETE_STATUS
                    )
                    if self.hydrate_raw
                    else "compact"
                ),
                "unavailable_source_inputs": {
                    "occurrence_count": validation.get(
                        "unavailable_raw_reference_occurrences", 0
                    ),
                    "path": self.unavailable_source_index_record.path,
                    "sha256": self.unavailable_source_index_record.sha256,
                    "unique_file_count": validation.get(
                        "unavailable_raw_unique_files", 0
                    ),
                },
            },
            "release_kind": release_kind,
            "release_tier": self.tier,
            "schema_version": SCHEMA_VERSION,
            "source_reference_validation": {
                "status": validation_status,
                **validation,
            },
            "total_bytes_excluding_this_manifest": total_bytes,
        }
        return self._write_bytes(
            "MANIFEST.json",
            _json_bytes(manifest),
            role="top-manifest",
        )

    def _install(self) -> None:
        if self.staging is None:
            raise AssertionError("staging directory is not initialized")
        if self.output.exists() or self.output.is_symlink():
            if not self.overwrite:
                raise BuildError(f"output already exists: {self.output}")
            if self.output.is_symlink() or self.output.is_file():
                self.output.unlink()
            else:
                shutil.rmtree(self.output)
        self.staging.replace(self.output)
        self.staging = None

    def build(self) -> dict[str, Any]:
        self._validate_destination()
        self.output.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(prefix=f".{self.output.name}.tmp-", dir=self.output.parent)
        )
        self.staging = staging
        try:
            self._copy_sources()
            self._copy_dataset_fixtures()
            self._copy_raw()
            self._copy_derived()
            self._write_provenance_sidecars()
            self._write_release_metadata()
            validation = self._validate_provenance()
            self._scan_staging()
            top_manifest = self._write_top_manifest(validation)
            self.identity_scanner.scan_bytes(
                top_manifest.path, self._stage_path(top_manifest.path).read_bytes()
            )
            self.identity_scanner.raise_for_issues()
            file_count = len(self.records)
            total_bytes = sum(record.size_bytes for record in self.records.values())
            raw_archive_bytes = sum(item["archive_size_bytes"] for item in self.raw_inventory)
            raw_logical_bytes = sum(item["uncompressed_size_bytes"] for item in self.raw_inventory)
            self._install()
            return {
                "anonymous_source_tree_sha256": self.source_hash,
                "compression": self.compression,
                "file_count": file_count,
                "identity_scan_files": len(self.identity_scanner.scanned_paths),
                "indexed_raw_files": len(self.raw_source_index),
                "output": str(self.output),
                "raw_archive_bytes": raw_archive_bytes,
                "raw_logical_bytes": raw_logical_bytes,
                "raw_hydrated": self.hydrate_raw,
                "release_tier": self.tier,
                "representative_raw_runs": len(self.review_run_directories),
                "total_bytes": total_bytes,
                **validation,
            }
        except BaseException:
            if self.staging is not None:
                shutil.rmtree(self.staging, ignore_errors=True)
                self.staging = None
            raise


def _format_bytes(value: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    amount = float(value)
    for unit in units:
        if amount < 1024.0 or unit == units[-1]:
            return f"{amount:.1f} {unit}"
        amount /= 1024.0
    raise AssertionError("unreachable")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tier",
        choices=RELEASE_TIERS,
        default="full",
        help="release surface: full corpus or smaller review bundle (default: full)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="fresh release directory (defaults to release or release_review by tier)",
    )
    parser.add_argument(
        "--hydrate-raw",
        action="store_true",
        help=(
            "include all raw payload sizes in the review tier; original source "
            "bundle archives remain excluded"
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace only the selected output after a new staging tree validates",
    )
    args = parser.parse_args(argv)
    if args.output is None:
        args.output = Path(REVIEW_OUTPUT if args.tier == "review" else DEFAULT_OUTPUT)
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repository = Path(__file__).resolve().parents[1]
    try:
        report = ReleaseBuilder(
            repository,
            args.output,
            hydrate_raw=args.hydrate_raw,
            overwrite=args.overwrite,
            tier=args.tier,
        ).build()
    except BuildError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    ratio = (
        report["raw_archive_bytes"] / report["raw_logical_bytes"]
        if report["raw_logical_bytes"]
        else 0.0
    )
    print(f"release: {report['output']}")
    print(f"tier: {report['release_tier']}")
    print(f"files: {report['file_count']}")
    print(f"size: {_format_bytes(report['total_bytes'])}")
    print(
        "compact raw: "
        f"{_format_bytes(report['raw_archive_bytes'])} / "
        f"{_format_bytes(report['raw_logical_bytes'])} ({ratio:.1%})"
    )
    print(f"compression: {report['compression']}")
    if report["release_tier"] == "review":
        print(
            "review raw coverage: "
            f"{report['representative_raw_runs']} representative runs; "
            f"{report['indexed_raw_files']} source files indexed"
        )
        print(f"review raw hydration: {report['raw_hydrated']}")
    print(f"identity scan: passed ({report['identity_scan_files']} files)")
    print(
        "source references: passed "
        f"({report['provenance_input_references_checked']} provenance inputs)"
    )
    print(f"anonymous source tree: {report['anonymous_source_tree_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
