from __future__ import annotations

import gzip
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

import tools.build_anonymous_supplement as anonymous_supplement

from tools.build_anonymous_supplement import (
    BuildError,
    FileRecord,
    IdentityScanner,
    RELEASE_TOOLING_EXCLUSIONS,
    REVIEW_AUXILIARY_MAX_BYTES,
    REVIEW_OUTPUT,
    REVIEW_RAW_INDEX_PATH,
    REVIEW_SELECTION_ALGORITHM,
    ReferenceTarget,
    ReleaseBuilder,
    StructuredSanitizer,
    UNAVAILABLE_RAW_STATUS,
    canonical_json,
    discover_identity_terms,
    is_optional_paper_reference,
    parse_args,
    project_raw_record,
    sanitize_source_text,
    select_review_run_directories,
)


def test_structured_sanitizer_relativizes_paths_and_replaces_revision(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    source_hash = "a" * 64
    sanitizer = StructuredSanitizer(repository, source_hash)
    record = {
        "config": {"output_root": str(repository / "results/raw/study")},
        "config_digest": "old",
        "git_revision": "old-revision",
        "git_root": str(repository),
        "python": {"executable": str(repository / ".venv/bin/python")},
        "test_indices_artifact": "/" + "Users" + "/example/cache/test_indices.npy",
    }

    sanitized = sanitizer.sanitize(record)

    assert sanitized["git_revision"] == source_hash
    assert sanitized["git_root"] == "."
    assert sanitized["python"]["executable"] == ".venv/bin/python"
    assert sanitized["test_indices_artifact"] == "external-data/test_indices.npy"
    assert sanitized["config"]["output_root"] == "results/raw/study"
    expected = hashlib.sha256(canonical_json(sanitized["config"]).encode("ascii"))
    assert sanitized["config_digest"] == expected.hexdigest()


def test_reference_rewriter_accepts_already_rewritten_nested_inputs() -> None:
    builder = object.__new__(ReleaseBuilder)
    builder.tier = "full"
    builder.references = {
        "results/raw/run/raw.jsonl": ReferenceTarget(
            "results/raw/run/raw.jsonl.zst", "b" * 64
        )
    }
    builder.records = {
        "results/raw/run/raw.jsonl.zst": FileRecord(
            path="results/raw/run/raw.jsonl.zst",
            sha256="b" * 64,
            size_bytes=10,
            role="compact-raw",
        )
    }
    builder.sanitizer = StructuredSanitizer(Path.cwd(), "a" * 64)
    value = {
        "inputs": [
            {"path": "results/raw/run/raw.jsonl", "sha256": "stale"}
        ],
        "input_set_sha256": "stale",
    }

    rewritten = builder._rewrite_known_paths(value)

    expected_inputs = [
        {"path": "results/raw/run/raw.jsonl.zst", "sha256": "b" * 64}
    ]
    assert rewritten["inputs"] == expected_inputs
    assert rewritten["input_set_sha256"] == hashlib.sha256(
        canonical_json(expected_inputs).encode("ascii")
    ).hexdigest()


def test_identity_scanner_rejects_local_paths_emails_and_discovered_names() -> None:
    scanner = IdentityScanner(["Example Person"])
    text = "\n".join(
        (
            "/" + "Users" + "/account/project",
            "person" + "@" + "example.org",
            "Example Person",
        )
    )

    scanner.scan_text("artifact.json", text)

    with pytest.raises(BuildError, match="identity scan failed"):
        scanner.raise_for_issues()
    assert {issue["rule"] for issue in scanner.issues} >= {
        "local-user-path",
        "email-address",
        "local-identity-1",
    }


def test_identity_scanner_rejects_reconstructed_python_identity() -> None:
    identity = "ReleaseIdentity"
    split = len(identity) // 2
    source = f"private_parts = ({identity[:split]!r}, {identity[split:]!r})\n"
    scanner = IdentityScanner([identity])

    scanner.scan_text("mapping.py", source)

    with pytest.raises(BuildError, match="identity scan failed"):
        scanner.raise_for_issues()
    assert {issue["rule"] for issue in scanner.issues} == {
        "local-identity-1-reconstructed"
    }


def test_binary_email_scan_does_not_join_across_invalid_bytes() -> None:
    scanner = IdentityScanner([])
    scanner.scan_bytes("numeric.bin", b"person@\xffexample.org")
    scanner.raise_for_issues()

    scanner.scan_bytes("metadata.bin", b"person" + b"@" + b"example.org")
    with pytest.raises(BuildError, match="email-address"):
        scanner.raise_for_issues()


def test_binary_identity_scan_is_case_insensitive_after_invalid_bytes() -> None:
    scanner = IdentityScanner(["ReleaseIdentity"])

    scanner.scan_bytes("metadata.bin", b"\xffreleaseidentity\x00")

    with pytest.raises(BuildError, match="local-identity-1"):
        scanner.raise_for_issues()


def _npy_v1_payload(
    descriptor: str,
    payload: bytes,
    *,
    shape: tuple[int, ...] = (1,),
) -> bytes:
    header = (
        "{'descr': "
        + repr(descriptor)
        + f", 'fortran_order': False, 'shape': {shape!r}, }}"
    )
    padding = (-(10 + len(header) + 1)) % 16
    header_bytes = (header + " " * padding + "\n").encode("latin1")
    return (
        b"\x93NUMPY\x01\x00"
        + len(header_bytes).to_bytes(2, "little")
        + header_bytes
        + payload
    )


def _npz_payload(
    member: bytes,
    *,
    compression: int = zipfile.ZIP_DEFLATED,
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        archive.writestr("values.npy", member)
    return output.getvalue()


def test_npz_identity_scan_inspects_deflated_members() -> None:
    identity = b"ReleaseIdentity"
    scanner = IdentityScanner([identity.decode("ascii")])

    scanner.scan_bytes("rounds.npz", _npz_payload(_npy_v1_payload("|S15", identity)))

    with pytest.raises(BuildError, match="local-identity-1"):
        scanner.raise_for_issues()


def test_npz_identity_scan_accepts_numeric_and_rejects_unauditable_dtype() -> None:
    scanner = IdentityScanner([])
    scanner.scan_bytes(
        "numeric.npz",
        _npz_payload(_npy_v1_payload("<f8", b"\x00" * 8)),
    )
    scanner.raise_for_issues()

    with pytest.raises(BuildError, match="unauditable dtype"):
        scanner.scan_bytes(
            "unicode.npz",
            _npz_payload(_npy_v1_payload("<U1", b"x\x00\x00\x00")),
        )


def test_npz_email_scan_applies_only_to_string_arrays() -> None:
    email = b"git" + bytes([64]) + b"example.test"
    scanner = IdentityScanner([])
    scanner.scan_bytes(
        "numeric.npz",
        _npz_payload(_npy_v1_payload("|u1", email, shape=(len(email),))),
    )
    scanner.raise_for_issues()

    scanner = IdentityScanner([])
    scanner.scan_bytes(
        "strings.npz",
        _npz_payload(_npy_v1_payload(f"|S{len(email)}", email)),
    )
    with pytest.raises(BuildError, match="email-address"):
        scanner.raise_for_issues()


def test_npz_identity_scan_rejects_excessive_compression_ratio() -> None:
    payload = b"\x00" * (1024 * 1024)
    scanner = IdentityScanner([])

    with pytest.raises(BuildError, match="compression ratio is too high"):
        scanner.scan_bytes(
            "compressed.npz",
            _npz_payload(
                _npy_v1_payload("|u1", payload, shape=(len(payload),))
            ),
        )


@pytest.mark.parametrize("relative", sorted(RELEASE_TOOLING_EXCLUSIONS))
def test_private_release_tooling_does_not_embed_forbidden_literals(
    relative: str,
) -> None:
    source = Path(relative).read_text(encoding="utf-8")
    scanner = IdentityScanner(discover_identity_terms(Path.cwd()))

    scanner.scan_text(relative, source)

    scanner.raise_for_issues()


def test_raw_projection_keeps_scalars_and_aggregator_arrays() -> None:
    record = {
        "round": 0,
        "metrics": {
            "cumulative_pseudo_regret": 1.25,
            "executed_policy": True,
            "cg_iterations": [3, 4],
            "policy_scores_all_actions": [1.0, 2.0],
            "context": [0.1, 0.2, 0.3],
            "operator_metadata": {"rank": 2},
        },
    }

    compact, removed = project_raw_record(record)

    assert compact["round"] == 0
    assert compact["metrics"] == {
        "cumulative_pseudo_regret": 1.25,
        "executed_policy": True,
        "cg_iterations": [3, 4],
        "policy_scores_all_actions": [1.0, 2.0],
    }
    assert removed == {"context", "operator_metadata"}


def _auxiliary_builder(repository: Path, staging: Path, *, tier: str) -> ReleaseBuilder:
    builder = object.__new__(ReleaseBuilder)
    builder.repository = repository
    builder.staging = staging
    staging.mkdir()
    builder.tier = tier
    builder.hydrate_raw = False
    builder.records = {}
    builder.references = {}
    builder.raw_inventory = []
    builder.raw_source_index = {}
    builder.raw_index_record = None
    builder.removed_raw_fields = set()
    builder.run_id_maps = {}
    builder.compression = "gzip"
    builder.compression_extension = ".gz"
    builder.identity_scanner = IdentityScanner([])
    builder.sanitizer = StructuredSanitizer(repository, "a" * 64)
    return builder


def test_auxiliary_jsonl_is_sanitized_and_compressed_losslessly(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    source = repository / "results" / "raw" / "phase" / "online_rounds.jsonl"
    source.parent.mkdir(parents=True)
    source.write_text('{"round":1,"metrics":{"vector":[1,2]}}\n', encoding="utf-8")
    builder = _auxiliary_builder(repository, tmp_path / "staging", tier="full")

    builder._process_auxiliary_raw_files([source])

    relative = source.relative_to(repository).as_posix()
    released = relative + ".gz"
    assert builder.references[relative].path == released
    assert gzip.decompress((builder.staging / released).read_bytes()) == (
        b'{"metrics":{"vector":[1,2]},"round":1}\n'
    )
    assert builder.raw_inventory[0]["removed_composite_metric_fields"] == []


def test_review_omits_large_auxiliary_raw_file_for_source_index(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    raw = repository / "results" / "raw" / "phase"
    raw.mkdir(parents=True)
    small = raw / "grid.json"
    large = raw / "online_rounds.jsonl"
    small.write_text('{"cells":8}\n', encoding="utf-8")
    large.write_bytes(b" " * (REVIEW_AUXILIARY_MAX_BYTES + 1))
    builder = _auxiliary_builder(repository, tmp_path / "staging", tier="review")

    builder._process_auxiliary_raw_files([small, large])

    assert small.relative_to(repository).as_posix() in builder.references
    assert large.relative_to(repository).as_posix() not in builder.references


def test_hydrated_review_includes_large_auxiliary_raw_file(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    raw = repository / "results" / "raw" / "phase"
    raw.mkdir(parents=True)
    large = raw / "rounds.npz"
    values = b"\x00" * (REVIEW_AUXILIARY_MAX_BYTES + 1)
    large.write_bytes(
        _npz_payload(
            _npy_v1_payload("|u1", values, shape=(len(values),)),
            compression=zipfile.ZIP_STORED,
        )
    )
    builder = _auxiliary_builder(repository, tmp_path / "staging", tier="review")
    builder.hydrate_raw = True

    builder._process_auxiliary_raw_files([large])

    relative = large.relative_to(repository).as_posix()
    assert builder.references[relative].path == relative
    assert (builder.staging / relative).read_bytes() == large.read_bytes()


def test_parallel_npz_staging_preserves_scanned_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    raw = repository / "results" / "raw" / "phase"
    raw.mkdir(parents=True)
    payloads = []
    for index in range(2):
        path = raw / f"rounds-{index}.npz"
        path.write_bytes(_npz_payload(_npy_v1_payload("<f8", b"\x00" * 8)))
        payloads.append(path)
    builder = _auxiliary_builder(repository, tmp_path / "staging", tier="review")
    builder.hydrate_raw = True
    monkeypatch.setattr(anonymous_supplement, "NPZ_PROCESS_POOL_MIN_FILES", 1)
    monkeypatch.setattr(anonymous_supplement, "NPZ_PROCESS_POOL_WORKERS", 2)

    builder._process_auxiliary_raw_files(payloads)

    for path in payloads:
        relative = path.relative_to(repository).as_posix()
        assert builder.records[relative].sha256 == hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        assert builder.references[relative].path == relative
        assert relative in builder.identity_scanner.scanned_paths
        assert (builder.staging / relative).read_bytes() == path.read_bytes()


def test_release_raw_files_excludes_source_bundle_workspace(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    raw = repository / "results" / "raw"
    evidence = raw / "study" / "manifest.json"
    source_bundle = raw / "bundles" / "private-source.tar.gz"
    legacy_smoke = raw / "smoke" / "manifest.json"
    evidence.parent.mkdir(parents=True)
    source_bundle.parent.mkdir(parents=True)
    legacy_smoke.parent.mkdir(parents=True)
    evidence.write_text('{"schema_version":1}\n', encoding="utf-8")
    source_bundle.write_bytes(b"private source archive")
    legacy_smoke.write_text('{"smoke":true}\n', encoding="utf-8")
    builder = _auxiliary_builder(repository, tmp_path / "staging", tier="review")

    released = builder._release_raw_files()

    assert released == [evidence]
    builder.hydrate_raw = True
    assert builder._release_raw_files() == [legacy_smoke, evidence]


def test_release_raw_files_rejects_symlinks(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    raw = repository / "results" / "raw" / "study"
    raw.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text('{"private":true}\n', encoding="utf-8")
    (raw / "linked.json").symlink_to(outside)
    builder = _auxiliary_builder(repository, tmp_path / "staging", tier="review")

    with pytest.raises(BuildError, match="raw release input cannot be a symlink"):
        builder._release_raw_files()


def test_auxiliary_manifest_resolves_parent_relative_inputs_after_payloads(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    raw = repository / "results" / "raw" / "study"
    deepest = raw / "data" / "payload.bin"
    deepest.parent.mkdir(parents=True)
    deepest.write_bytes(b"payload")
    payload = raw / "payloads" / "payload.json"
    payload.parent.mkdir(parents=True)
    payload_inputs = [
        {
            "path": "../data/payload.bin",
            "sha256": hashlib.sha256(deepest.read_bytes()).hexdigest(),
        }
    ]
    payload.write_text(
        json.dumps(
            {
                "git_root": str(repository),
                "input_set_sha256": hashlib.sha256(
                    canonical_json(payload_inputs).encode("ascii")
                ).hexdigest(),
                "inputs": payload_inputs,
                "schema_version": 1,
            }
        ),
        encoding="utf-8",
    )
    owner = raw / "aggregate" / "manifest.json"
    owner.parent.mkdir()
    source_inputs = [
        {
            "path": "../payloads/payload.json",
            "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
        }
    ]
    owner.write_text(
        json.dumps(
            {
                "input_set_sha256": hashlib.sha256(
                    canonical_json(source_inputs).encode("ascii")
                ).hexdigest(),
                "inputs": source_inputs,
                "schema_version": 1,
            }
        ),
        encoding="utf-8",
    )
    sidecar = owner.with_name("manifest.json.sha256")
    sidecar.write_text(
        f"{hashlib.sha256(owner.read_bytes()).hexdigest()}  manifest.json\n",
        encoding="ascii",
    )
    builder = _auxiliary_builder(repository, tmp_path / "staging", tier="full")

    builder._process_auxiliary_raw_files(
        sorted(path for path in raw.rglob("*") if path.is_file())
    )

    owner_relative = owner.relative_to(repository).as_posix()
    payload_relative = payload.relative_to(repository).as_posix()
    released = json.loads((builder.staging / owner_relative).read_text())
    released_inputs = [
        {
            "path": payload_relative,
            "sha256": builder.records[payload_relative].sha256,
        }
    ]
    assert released["inputs"] == released_inputs
    assert released["input_set_sha256"] == hashlib.sha256(
        canonical_json(released_inputs).encode("ascii")
    ).hexdigest()
    assert (
        builder._rewrite_known_paths(released, source_relative=owner_relative)
        == released
    )
    released_payload = json.loads((builder.staging / payload_relative).read_text())
    deepest_relative = deepest.relative_to(repository).as_posix()
    assert released_payload["inputs"] == [
        {
            "path": deepest_relative,
            "sha256": builder.records[deepest_relative].sha256,
        }
    ]
    assert str(repository) not in canonical_json(released_payload)
    released_sidecar = builder.staging / sidecar.relative_to(repository)
    sidecar_digest, sidecar_name = released_sidecar.read_text(encoding="ascii").split()
    assert sidecar_name == "manifest.json"
    assert sidecar_digest == builder.records[owner_relative].sha256


def test_auxiliary_manifest_validates_digest_before_sanitizing_absolute_input(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    raw = repository / "results" / "raw" / "study"
    raw.mkdir(parents=True)
    payload = raw / "payload.json"
    payload.write_text('{"schema_version":1}\n', encoding="utf-8")
    inputs = [
        {
            "path": str(payload),
            "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
        }
    ]
    manifest = raw / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "input_set_sha256": hashlib.sha256(
                    canonical_json(inputs).encode("ascii")
                ).hexdigest(),
                "inputs": inputs,
            }
        ),
        encoding="utf-8",
    )
    builder = _auxiliary_builder(repository, tmp_path / "staging", tier="full")

    builder._process_auxiliary_raw_files([manifest, payload])

    released = json.loads(
        (builder.staging / manifest.relative_to(repository)).read_text()
    )
    assert released["inputs"] == [
        {
            "path": payload.relative_to(repository).as_posix(),
            "sha256": builder.records[
                payload.relative_to(repository).as_posix()
            ].sha256,
        }
    ]


def test_contextual_input_resolver_rejects_ambiguity_escape_and_stale_hash(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    owner = repository / "results" / "raw" / "study" / "manifest.json"
    owner.parent.mkdir(parents=True)
    direct = repository / "payload.json"
    contextual = owner.parent / "payload.json"
    direct.write_text("direct", encoding="utf-8")
    contextual.write_text("contextual", encoding="utf-8")
    builder = _auxiliary_builder(repository, tmp_path / "staging", tier="full")
    builder.planned_auxiliary_paths = {
        direct.relative_to(repository).as_posix(),
        contextual.relative_to(repository).as_posix(),
    }

    with pytest.raises(BuildError, match="ambiguous provenance input path"):
        builder._rewrite_known_paths(
            {"inputs": [{"path": "payload.json", "sha256": "a" * 64}]},
            source_relative=owner.relative_to(repository).as_posix(),
        )

    with pytest.raises(BuildError, match="escapes repository"):
        builder._rewrite_known_paths(
            {"inputs": [{"path": "../../../../outside", "sha256": "a" * 64}]},
            source_relative=owner.relative_to(repository).as_posix(),
        )

    direct.unlink()
    builder.planned_auxiliary_paths.remove("payload.json")
    with pytest.raises(BuildError, match="input hash is stale"):
        builder._rewrite_known_paths(
            {"inputs": [{"path": "payload.json", "sha256": "a" * 64}]},
            source_relative=owner.relative_to(repository).as_posix(),
        )


def test_review_cascade_omits_manifest_with_large_auxiliary_dependency(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    raw = repository / "results" / "raw" / "study"
    raw.mkdir(parents=True)
    large = raw / "payload.bin"
    large.write_bytes(b"x" * (REVIEW_AUXILIARY_MAX_BYTES + 1))
    source_inputs = [
        {
            "path": "payload.bin",
            "sha256": hashlib.sha256(large.read_bytes()).hexdigest(),
        }
    ]
    manifest = raw / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "input_set_sha256": hashlib.sha256(
                    canonical_json(source_inputs).encode("ascii")
                ).hexdigest(),
                "inputs": source_inputs,
            }
        ),
        encoding="utf-8",
    )
    builder = _auxiliary_builder(repository, tmp_path / "staging", tier="review")

    builder._process_auxiliary_raw_files(sorted(raw.iterdir()))

    assert large.relative_to(repository).as_posix() not in builder.references
    assert manifest.relative_to(repository).as_posix() not in builder.references


def test_copy_derived_recurses_into_study_directories(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    aggregate = (
        repository
        / "results"
        / "derived"
        / "spectral_tail_study"
        / "full"
        / "aggregate.json"
    )
    aggregate.parent.mkdir(parents=True)
    aggregate.write_text('{"schema_version":1}\n', encoding="utf-8")
    builder = _auxiliary_builder(repository, tmp_path / "staging", tier="review")

    builder._copy_derived()

    relative = aggregate.relative_to(repository).as_posix()
    assert relative in builder.records
    assert json.loads((builder.staging / relative).read_text()) == {
        "schema_version": 1
    }


def test_copy_derived_validates_absolute_input_before_sanitizing(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    derived = repository / "results" / "derived"
    derived.mkdir(parents=True)
    payload = derived / "payload.bin"
    payload.write_bytes(b"payload")
    aggregate = derived / "aggregate.json"
    aggregate.write_text(
        json.dumps(
            {
                "inputs": [{"path": str(payload), "sha256": "a" * 64}],
                "schema_version": 1,
            }
        ),
        encoding="utf-8",
    )
    builder = _auxiliary_builder(repository, tmp_path / "staging", tier="full")

    with pytest.raises(BuildError, match="provenance input hash is stale"):
        builder._copy_derived()


def test_grouped_sidecar_inputs_are_standardized_to_released_files() -> None:
    builder = object.__new__(ReleaseBuilder)
    builder.tier = "full"
    builder.records = {
        "experiments/generator.py": FileRecord(
            "experiments/generator.py", "a" * 64, 1, "source"
        ),
        "results/derived/aggregate.json": FileRecord(
            "results/derived/aggregate.json", "b" * 64, 1, "derived"
        ),
        "results/raw/linear_audit/full/evaluation/run/manifest.jsonl": FileRecord(
            "results/raw/linear_audit/full/evaluation/run/manifest.jsonl",
            "c" * 64,
            1,
            "run-manifest",
        ),
        "results/raw/linear_audit/full/evaluation/run/summary.jsonl": FileRecord(
            "results/raw/linear_audit/full/evaluation/run/summary.jsonl",
            "d" * 64,
            1,
            "run-summary",
        ),
    }
    sidecar = {
        "generator": {"path": "experiments/generator.py", "sha256": "a" * 64},
        "inputs": {
            "aggregate": {
                "path": "results/derived/aggregate.json",
                "sha256": "b" * 64,
            },
            "evaluation_manifests": {"file_count": 1, "sha256": "c" * 64},
            "evaluation_summaries": {"file_count": 1, "sha256": "d" * 64},
        },
    }

    standardized = builder._standardize_grouped_sidecar_inputs(sidecar)

    assert standardized["input_groups"] == sidecar["inputs"]
    assert [item["path"] for item in standardized["inputs"]] == sorted(
        builder.records
    )
    assert len(standardized["input_set_sha256"]) == 64


def test_paper_sidecar_can_bind_a_derived_provenance_sidecar(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    staging = tmp_path / "staging"
    derived_artifact = repository / "results" / "derived" / "aggregate.json"
    paper_artifact = repository / "paper" / "figures" / "figure.pdf"
    derived_artifact.parent.mkdir(parents=True)
    paper_artifact.parent.mkdir(parents=True)
    derived_artifact.write_text('{"schema_version":1}\n', encoding="utf-8")
    paper_artifact.write_bytes(b"%PDF-1.4\n")
    derived_sidecar = derived_artifact.with_suffix(".json.provenance.json")
    derived_sidecar.write_text(
        json.dumps(
            {
                "artifact": "results/derived/aggregate.json",
                "artifact_sha256": hashlib.sha256(derived_artifact.read_bytes()).hexdigest(),
                "inputs": [],
                "schema_version": 1,
            }
        ),
        encoding="utf-8",
    )
    paper_sidecar = paper_artifact.with_suffix(".pdf.provenance.json")
    paper_sidecar.write_text(
        json.dumps(
            {
                "artifact": "paper/figures/figure.pdf",
                "artifact_sha256": hashlib.sha256(paper_artifact.read_bytes()).hexdigest(),
                "inputs": [
                    {
                        "path": "results/derived/aggregate.json.provenance.json",
                        "sha256": hashlib.sha256(derived_sidecar.read_bytes()).hexdigest(),
                    }
                ],
                "schema_version": 1,
            }
        ),
        encoding="utf-8",
    )

    builder = object.__new__(ReleaseBuilder)
    builder.repository = repository
    builder.staging = staging
    staging.mkdir()
    builder.tier = "full"
    builder.records = {}
    builder.references = {}
    builder.raw_source_index = {}
    builder.identity_scanner = IdentityScanner([])
    builder.sanitizer = StructuredSanitizer(repository, "a" * 64)
    for source, role in ((derived_artifact, "derived"), (paper_artifact, "paper")):
        relative = source.relative_to(repository).as_posix()
        builder._write_bytes(
            relative,
            source.read_bytes(),
            role=role,
            source_relative=relative,
        )

    builder._write_provenance_sidecars()

    released_derived_sidecar = "results/derived/aggregate.json.provenance.json"
    released_paper_sidecar = "paper/figures/figure.pdf.provenance.json"
    assert released_derived_sidecar in builder.records
    assert released_paper_sidecar in builder.records
    paper_value = json.loads((staging / released_paper_sidecar).read_text())
    assert paper_value["inputs"] == [
        {
            "path": released_derived_sidecar,
            "sha256": builder.records[released_derived_sidecar].sha256,
        }
    ]


def test_provenance_sidecar_validates_absolute_input_before_sanitizing(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    artifact = repository / "paper" / "figure.pdf"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"%PDF-1.4\n")
    payload = repository / "results" / "derived" / "payload.bin"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"payload")
    sidecar = artifact.with_suffix(".pdf.provenance.json")
    sidecar.write_text(
        json.dumps(
            {
                "artifact": artifact.relative_to(repository).as_posix(),
                "inputs": [{"path": str(payload), "sha256": "a" * 64}],
                "schema_version": 1,
            }
        ),
        encoding="utf-8",
    )
    builder = _auxiliary_builder(repository, tmp_path / "staging", tier="full")
    artifact_relative = artifact.relative_to(repository).as_posix()
    builder._write_bytes(
        artifact_relative,
        artifact.read_bytes(),
        role="paper",
        source_relative=artifact_relative,
    )

    with pytest.raises(BuildError, match="provenance input hash is stale"):
        builder._write_provenance_sidecars()


def _write_complete_run(directory: Path, marker: str) -> None:
    directory.mkdir(parents=True)
    for name in ("manifest.jsonl", "raw.jsonl", "summary.jsonl"):
        (directory / name).write_text(f'{{"marker":"{marker}"}}\n', encoding="utf-8")


def test_review_selector_uses_first_complete_run_per_study(tmp_path: Path) -> None:
    raw_root = tmp_path / "results" / "raw"
    incomplete = raw_root / "alpha" / "a-incomplete"
    incomplete.mkdir(parents=True)
    (incomplete / "raw.jsonl").write_text("{}\n", encoding="utf-8")
    alpha = raw_root / "alpha" / "b-complete"
    beta_first = raw_root / "beta" / "a-run"
    beta_second = raw_root / "beta" / "b-run"
    _write_complete_run(alpha, "alpha")
    _write_complete_run(beta_second, "second")
    _write_complete_run(beta_first, "first")
    _write_complete_run(raw_root / "smoke" / "ignored", "smoke")

    selected = select_review_run_directories(raw_root)

    assert selected == (alpha, beta_first)


def test_missing_raw_root_is_an_empty_release_input(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    builder = ReleaseBuilder(repository, tmp_path / "release", tier="review")

    assert builder._release_raw_files() == []


def test_hydrated_review_rejects_empty_raw_tree(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    (repository / "results" / "raw").mkdir(parents=True)
    builder = _auxiliary_builder(repository, tmp_path / "staging", tier="review")
    builder.hydrate_raw = True

    with pytest.raises(
        BuildError, match="raw hydration requires a non-empty results/raw tree"
    ):
        builder._copy_raw()


def test_review_tier_has_separate_default_output() -> None:
    assert parse_args([]).output == Path("release")
    review = parse_args(["--tier", "review"])
    assert review.output == Path(REVIEW_OUTPUT)
    assert review.tier == "review"
    explicit = parse_args(["--tier", "review", "--output", "custom"])
    assert explicit.output == Path("custom")


def test_review_tier_cannot_overwrite_full_release(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    builder = ReleaseBuilder(
        repository,
        Path("release") / "nested",
        overwrite=True,
        tier="review",
    )

    with pytest.raises(BuildError, match="cannot target the full release"):
        builder._validate_destination()


def test_review_rewriter_binds_omitted_raw_input_to_index(tmp_path: Path) -> None:
    source_path = "results/raw/study/full/evaluation/seed-1/raw.jsonl"
    source_digest = "c" * 64
    index_record = FileRecord(REVIEW_RAW_INDEX_PATH, "d" * 64, 100, "raw-source-index")
    builder = object.__new__(ReleaseBuilder)
    builder.tier = "review"
    builder.raw_index_record = index_record
    builder.raw_source_index = {
        source_path: {
            "path": source_path,
            "release_status": "indexed_not_released",
            "sha256": source_digest,
            "size_bytes": 10,
        }
    }
    builder.records = {index_record.path: index_record}
    builder.references = {}
    builder.sanitizer = StructuredSanitizer(tmp_path, "a" * 64)

    rewritten = builder._rewrite_known_paths(
        {"input_set_sha256": "stale", "inputs": [{"path": source_path, "sha256": source_digest}]}
    )

    item = rewritten["inputs"][0]
    assert item["availability"] == "indexed_not_released"
    assert item["index"] == {"path": index_record.path, "sha256": index_record.sha256}
    assert builder._is_valid_indexed_raw_reference(item)
    assert rewritten["input_set_sha256"] == hashlib.sha256(
        canonical_json(rewritten["inputs"]).encode("ascii")
    ).hexdigest()

    with pytest.raises(BuildError, match="indexed raw input hash is stale"):
        builder._rewrite_known_paths(
            {"inputs": [{"path": source_path, "sha256": "e" * 64}]}
        )


def test_compact_checkout_retains_unavailable_raw_binding(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    source_path = "results/raw/study/full/evaluation/seed-1/raw.jsonl"
    source_digest = "c" * 64
    builder = object.__new__(ReleaseBuilder)
    builder.repository = repository
    builder.tier = "review"
    builder.raw_index_record = None
    builder.raw_source_index = {}
    builder.records = {}
    builder.references = {}
    builder.sanitizer = StructuredSanitizer(repository, "a" * 64)

    rewritten = builder._rewrite_known_paths(
        {
            "input_set_sha256": "stale",
            "inputs": [{"path": source_path, "sha256": source_digest}],
        }
    )

    item = rewritten["inputs"][0]
    assert item == {
        "availability": UNAVAILABLE_RAW_STATUS,
        "path": source_path,
        "sha256": source_digest,
    }
    assert builder._is_valid_unavailable_raw_reference(item)
    with pytest.raises(BuildError, match="unavailable raw input hash is invalid"):
        builder._rewrite_known_paths(
            {"inputs": [{"path": source_path, "sha256": "invalid"}]}
        )


def test_partial_raw_tree_retains_missing_legacy_binding(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    present = repository / "results" / "raw" / "current" / "raw.jsonl"
    present.parent.mkdir(parents=True)
    present.write_text("{}\n", encoding="utf-8")
    source_path = "results/raw/legacy/full/seed-1/raw.jsonl"
    builder = object.__new__(ReleaseBuilder)
    builder.repository = repository
    builder.tier = "review"
    builder.raw_index_record = None
    builder.raw_source_index = {}
    builder.records = {}
    builder.references = {}
    builder.sanitizer = StructuredSanitizer(repository, "a" * 64)

    rewritten = builder._rewrite_known_paths(
        {"inputs": [{"path": source_path, "sha256": "c" * 64}]}
    )

    item = rewritten["inputs"][0]
    assert item["availability"] == UNAVAILABLE_RAW_STATUS
    assert builder._is_valid_unavailable_raw_reference(item)

    direct = builder._rewrite_known_paths(
        {"selection": {"path": source_path, "sha256": "c" * 64}}
    )
    assert direct["selection"]["availability"] == UNAVAILABLE_RAW_STATUS


def test_compact_checkout_retains_public_dataset_cache_binding(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    builder = object.__new__(ReleaseBuilder)
    builder.repository = repository
    builder.tier = "review"
    builder.raw_index_record = None
    builder.raw_source_index = {}
    builder.records = {}
    builder.references = {}
    builder.sanitizer = StructuredSanitizer(repository, "a" * 64)

    rewritten = builder._rewrite_known_paths(
        {
            "inputs": [
                {"path": "external-data/samples_py3", "sha256": "d" * 64}
            ]
        }
    )

    item = rewritten["inputs"][0]
    assert item == {
        "availability": "public_dataset_cache_not_in_checkout",
        "path": "external-data/samples_py3",
        "sha256": "d" * 64,
    }
    assert builder._is_valid_unavailable_external_data_reference(item)


def test_review_rewriter_rejects_stale_hash_for_selected_raw_input(
    tmp_path: Path,
) -> None:
    source_path = "results/raw/study/full/evaluation/seed-1/raw.jsonl"
    released_path = source_path + ".zst"
    released = FileRecord(released_path, "b" * 64, 10, "compact-raw")
    builder = object.__new__(ReleaseBuilder)
    builder.tier = "review"
    builder.raw_source_index = {
        source_path: {
            "path": source_path,
            "release_status": "representative_transformed_copy_released",
            "sha256": "a" * 64,
            "size_bytes": 10,
        }
    }
    builder.records = {released.path: released}
    builder.references = {
        source_path: ReferenceTarget(released.path, released.sha256)
    }
    builder.sanitizer = StructuredSanitizer(tmp_path, "c" * 64)

    with pytest.raises(BuildError, match="indexed raw input hash is stale"):
        builder._rewrite_known_paths(
            {"inputs": [{"path": source_path, "sha256": "d" * 64}]}
        )


def test_review_raw_index_binds_source_and_released_hashes(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    raw_root = repository / "results" / "raw"
    selected = raw_root / "study" / "full" / "evaluation" / "seed-1"
    omitted = raw_root / "study" / "full" / "evaluation" / "seed-2"
    _write_complete_run(selected, "selected")
    _write_complete_run(omitted, "omitted")
    auxiliary = raw_root / "study" / "full" / "selection.json"
    auxiliary.write_text('{"selected":1}\n', encoding="utf-8")

    builder = object.__new__(ReleaseBuilder)
    builder.repository = repository
    builder.staging = tmp_path / "staging"
    builder.staging.mkdir()
    builder.tier = "review"
    builder.hydrate_raw = False
    builder.records = {}
    builder.references = {}
    builder.raw_source_index = {}
    builder.raw_index_record = None
    builder.review_run_directories = ()
    builder.identity_scanner = IdentityScanner([])
    for source in (*sorted(selected.iterdir()), auxiliary):
        relative = source.relative_to(repository).as_posix()
        released = relative + (".gz" if source.name == "raw.jsonl" else "")
        record = builder._write_bytes(released, source.read_bytes(), role="test")
        builder.references[relative] = ReferenceTarget(record.path, record.sha256)

    raw_files = sorted(path for path in raw_root.rglob("*") if path.is_file())
    builder._write_review_raw_index(raw_files, [selected])
    validation = builder._validate_review_raw_index()

    assert validation == {
        "indexed_raw_files_checked": 7,
        "representative_raw_runs_checked": 1,
    }
    index = json.loads((builder.staging / REVIEW_RAW_INDEX_PATH).read_text(encoding="utf-8"))
    assert index["selection"]["algorithm"] == REVIEW_SELECTION_ALGORITHM
    by_path = {item["path"]: item for item in index["files"]}
    omitted_raw = (omitted / "raw.jsonl").relative_to(repository).as_posix()
    assert by_path[omitted_raw]["release_status"] == "indexed_not_released"
    assert "released_copy" not in by_path[omitted_raw]
    selected_raw = (selected / "raw.jsonl").relative_to(repository).as_posix()
    assert by_path[selected_raw]["release_status"] == (
        "representative_transformed_copy_released"
    )

    omitted_raw_path = omitted / "raw.jsonl"
    original_omitted_raw = omitted_raw_path.read_bytes()
    omitted_raw_path.write_text('{"marker":"mutated"}\n', encoding="utf-8")
    with pytest.raises(BuildError, match="indexed source hash is stale"):
        builder._validate_review_raw_index()
    omitted_raw_path.write_bytes(original_omitted_raw)
    (raw_root / "study" / "full" / "new-unindexed.json").write_text(
        "{}\n", encoding="utf-8"
    )
    with pytest.raises(BuildError, match="does not match source tree"):
        builder._validate_review_raw_index()


def test_review_grouped_provenance_keeps_full_indexed_counts() -> None:
    prefix = "results/raw/linear_audit/full/evaluation/"
    index_record = FileRecord(REVIEW_RAW_INDEX_PATH, "f" * 64, 100, "raw-source-index")
    builder = object.__new__(ReleaseBuilder)
    builder.tier = "review"
    builder.raw_index_record = index_record
    builder.raw_source_index = {
        f"{prefix}method/seed-{seed}/{name}": {
            "path": f"{prefix}method/seed-{seed}/{name}",
            "sha256": digest * 64,
        }
        for seed, digest in ((1, "a"), (2, "b"))
        for name in ("manifest.jsonl", "summary.jsonl")
    }

    refreshed = builder._refresh_grouped_provenance(
        {
            "evaluation_manifests": {"file_count": 0, "sha256": "stale"},
            "evaluation_summaries": {"file_count": 0, "sha256": "stale"},
        }
    )

    for key in ("evaluation_manifests", "evaluation_summaries"):
        descriptor = refreshed[key]
        assert descriptor["file_count"] == 2
        assert descriptor["availability"] == "indexed_source_inputs"
        assert descriptor["index"] == {
            "path": index_record.path,
            "sha256": index_record.sha256,
        }


def test_review_tier_build_is_hash_valid_with_indexed_omissions(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    paper = repository / "paper"
    paper.mkdir(parents=True)
    (paper / "main.tex").write_text(
        "\\documentclass{article}\n\\author{Anonymous}\n\\begin{document}x\\end{document}\n",
        encoding="utf-8",
    )
    raw_root = repository / "results" / "raw"
    first = raw_root / "study" / "full" / "evaluation" / "seed-1"
    second = raw_root / "study" / "full" / "evaluation" / "seed-2"
    _write_complete_run(first, "first")
    _write_complete_run(second, "second")
    source_inputs = [
        {
            "path": path.relative_to(repository).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted((*first.iterdir(), *second.iterdir()))
    ]
    source_inputs.append(
        {
            "path": "results/raw/legacy/full/evaluation/seed-1/raw.jsonl",
            "sha256": "c" * 64,
        }
    )
    derived = repository / "results" / "derived"
    derived.mkdir(parents=True)
    aggregate = derived / "aggregate.json"
    aggregate_value = {
        "input_set_sha256": hashlib.sha256(
            canonical_json(source_inputs).encode("ascii")
        ).hexdigest(),
        "inputs": source_inputs,
        "schema_version": 1,
    }
    aggregate.write_text(json.dumps(aggregate_value), encoding="utf-8")
    sidecar = {
        "artifact": aggregate.relative_to(repository).as_posix(),
        "artifact_sha256": hashlib.sha256(aggregate.read_bytes()).hexdigest(),
        "inputs": source_inputs,
        "schema_version": 1,
    }
    (derived / "aggregate.json.provenance.json").write_text(
        json.dumps(sidecar), encoding="utf-8"
    )

    output = tmp_path / "release_review"
    report = ReleaseBuilder(repository, output, tier="review").build()

    assert report["representative_raw_runs"] == 1
    assert report["indexed_raw_files"] == 6
    assert report["indexed_provenance_input_references_checked"] == 3
    assert report["unavailable_raw_unique_files"] == 1
    raw_manifest = json.loads((output / "manifests/compact-raw.json").read_text())
    assert raw_manifest["lossless_for_reported_artifacts"] is False
    assert raw_manifest["coverage"]["scope"] == "representative_trajectories_only"
    top_manifest = json.loads((output / "MANIFEST.json").read_text())
    assert top_manifest["release_kind"] == "anonymous_review_supplement"
    assert top_manifest["raw_hydration"]["status"] == "compact"
    for item in top_manifest["files"]:
        assert hashlib.sha256((output / item["path"]).read_bytes()).hexdigest() == item[
            "sha256"
        ]

    hydrated_output = tmp_path / "release_review_hydrated"
    hydrated_report = ReleaseBuilder(
        repository,
        hydrated_output,
        hydrate_raw=True,
        tier="review",
    ).build()
    assert hydrated_report["raw_hydrated"] is True
    assert hydrated_report["representative_raw_runs"] == 2
    hydrated_manifest = json.loads(
        (hydrated_output / "MANIFEST.json").read_text()
    )
    assert (
        hydrated_manifest["raw_hydration"]["status"]
        == "complete_available_source_payloads_with_declared_legacy_gaps"
    )
    assert hydrated_manifest["raw_hydration"]["unavailable_source_inputs"] == {
        "occurrence_count": 2,
        "path": "manifests/unavailable-source-inputs.json",
        "sha256": hashlib.sha256(
            (
                hydrated_output
                / "manifests"
                / "unavailable-source-inputs.json"
            ).read_bytes()
        ).hexdigest(),
        "unique_file_count": 1,
    }
    assert hydrated_manifest["release_kind"] == "anonymous_review_supplement"
    assert (
        hydrated_manifest["raw_hydration"]["legacy_smoke_workspace_excluded"]
        is False
    )
    hydrated_raw_manifest = json.loads(
        (hydrated_output / "manifests" / "compact-raw.json").read_text()
    )
    assert hydrated_raw_manifest["lossless_for_reported_artifacts"] is True
    assert (
        hydrated_raw_manifest["coverage"]["scope"]
        == "complete_available_source_payloads_with_declared_legacy_gaps"
    )
    assert (
        hydrated_raw_manifest["coverage"]["selection_algorithm"]
        == "all-complete-runs-v1"
    )
    hydrated_index = json.loads(
        (hydrated_output / REVIEW_RAW_INDEX_PATH).read_text()
    )
    assert hydrated_index["indexed_not_released_count"] == 0
    assert hydrated_index["selection"]["algorithm"] == "all-complete-runs-v1"
    assert (
        hydrated_index["selection"]["grouping_key"]
        == "none; all complete runs selected"
    )


def test_only_conditional_checklist_paper_inputs_are_optional() -> None:
    assert is_optional_paper_reference("aistats2027_checklist.tex")
    assert is_optional_paper_reference("paper/aistats_checklist.tex")
    assert not is_optional_paper_reference("tables/executed_policy_results.tex")
    assert not is_optional_paper_reference("missing_checklist_notes.tex")


def test_released_validator_removes_leading_private_editor_macro_class(
    tmp_path: Path,
) -> None:
    sanitizer = StructuredSanitizer(tmp_path, "a" * 64)
    source = r"""
deleted = [r'\\firsteditor', r'\\secondeditor',
           r'\\resultCheck', r'\\technical\b']
public_text = "Public citation text remains unchanged"
"""

    released = sanitize_source_text("paper/validate.py", source, sanitizer)

    assert "firsteditor" not in released
    assert "secondeditor" not in released
    assert "resultCheck" in released
    assert "technical" in released
    assert "Public citation text remains unchanged" in released
    compile(released, "paper/validate.py", "exec")


@pytest.mark.parametrize("tier", ["full", "review"])
def test_final_release_tree_excludes_private_tooling_and_scans_every_file(
    tmp_path: Path,
    tier: str,
) -> None:
    repository = tmp_path / "repository"
    identity = "ReleaseIdentity"
    paper = repository / "paper"
    paper.mkdir(parents=True)
    (paper / "main.tex").write_text(
        "\\documentclass{article}\n"
        "\\author{Anonymous}\n"
        "\\begin{document}x\\end{document}\n",
        encoding="utf-8",
    )
    (paper / "validate.py").write_text(
        "import re\n"
        f"deleted = [r'\\\\{identity.casefold()}', r'\\\\resultCheck']\n"
        "for pattern in deleted:\n"
        "    re.findall(pattern, '')\n",
        encoding="utf-8",
    )
    tools = repository / "tools"
    tools.mkdir()
    split = len(identity) // 2
    (tools / "build_anonymous_supplement.py").write_text(
        f"private_parts = ({identity[:split]!r}, {identity[split:]!r})\n",
        encoding="utf-8",
    )
    tests = repository / "tests"
    tests.mkdir()
    (tests / "test_anonymous_supplement.py").write_text(
        f"private_identity = {identity!r}\n",
        encoding="utf-8",
    )
    (repository / "results" / "derived").mkdir(parents=True)

    output = tmp_path / f"release-{tier}"
    builder = ReleaseBuilder(repository, output, tier=tier)
    identity_terms = (*discover_identity_terms(Path.cwd()), identity)
    builder.identity_scanner = IdentityScanner(identity_terms)
    builder.build()

    released_paths = tuple(
        sorted(
            path.relative_to(output).as_posix()
            for path in output.rglob("*")
            if path.is_file()
        )
    )
    assert "paper/validate.py" in released_paths
    assert RELEASE_TOOLING_EXCLUSIONS.isdisjoint(released_paths)
    manifest = json.loads((output / "MANIFEST.json").read_text(encoding="utf-8"))
    assert RELEASE_TOOLING_EXCLUSIONS.isdisjoint(
        item["path"] for item in manifest["files"]
    )
    source_manifest = json.loads(
        (output / "manifests" / "source-tree.json").read_text(encoding="utf-8")
    )
    assert RELEASE_TOOLING_EXCLUSIONS.isdisjoint(
        item["path"] for item in source_manifest["files"]
    )
    released_validator = (output / "paper" / "validate.py").read_text(
        encoding="utf-8"
    )
    assert identity.casefold() not in released_validator.casefold()
    assert "resultCheck" in released_validator

    scanner = IdentityScanner(identity_terms)
    for relative in released_paths:
        scanner.scan_bytes(relative, (output / relative).read_bytes())
    scanner.raise_for_issues()


def test_anonymized_auxiliary_raw_sidecar_binds_released_payload(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    paper = repository / "paper"
    paper.mkdir(parents=True)
    (paper / "main.tex").write_text(
        "\\documentclass{article}\n"
        "\\author{Anonymous}\n"
        "\\begin{document}x\\end{document}\n",
        encoding="utf-8",
    )
    (repository / "results" / "derived").mkdir(parents=True)
    raw_directory = repository / "results" / "raw" / "study" / "run"
    raw_directory.mkdir(parents=True)
    manifest = raw_directory / "manifest.json"
    manifest.write_text(
        json.dumps({"git_root": str(repository), "schema_version": 1}),
        encoding="utf-8",
    )
    (raw_directory / "manifest.json.sha256").write_text(
        f"{hashlib.sha256(manifest.read_bytes()).hexdigest()}  manifest.json\n",
        encoding="ascii",
    )

    output = tmp_path / "release"
    ReleaseBuilder(repository, output, tier="full").build()

    released_manifest = output / manifest.relative_to(repository)
    released_sidecar = released_manifest.with_name("manifest.json.sha256")
    released_digest, released_name = released_sidecar.read_text(
        encoding="ascii"
    ).split()
    assert released_name == "manifest.json"
    assert released_digest == hashlib.sha256(released_manifest.read_bytes()).hexdigest()
    assert str(repository) not in released_manifest.read_text(encoding="utf-8")
