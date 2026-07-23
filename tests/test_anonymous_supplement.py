from __future__ import annotations

import hashlib
import gzip
import json
from pathlib import Path

import pytest

from tools.build_anonymous_supplement import (
    BuildError,
    FileRecord,
    IdentityScanner,
    REVIEW_AUXILIARY_MAX_BYTES,
    REVIEW_OUTPUT,
    REVIEW_RAW_INDEX_PATH,
    REVIEW_SELECTION_ALGORITHM,
    ReferenceTarget,
    ReleaseBuilder,
    StructuredSanitizer,
    canonical_json,
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
        "test_indices_artifact": "/Users/example/cache/test_indices.npy",
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


def test_binary_email_scan_does_not_join_across_invalid_bytes() -> None:
    scanner = IdentityScanner([])
    scanner.scan_bytes("numeric.bin", b"person@\xffexample.org")
    scanner.raise_for_issues()

    scanner.scan_bytes("metadata.bin", b"person" + b"@" + b"example.org")
    with pytest.raises(BuildError, match="email-address"):
        scanner.raise_for_issues()


def test_builder_source_does_not_embed_forbidden_literals() -> None:
    source = Path("tools/build_anonymous_supplement.py").read_text(encoding="utf-8")
    scanner = IdentityScanner([])

    scanner.scan_text("tools/build_anonymous_supplement.py", source)

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
    builder.records = {}
    builder.references = {}
    builder.raw_inventory = []
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
        "availability": "not_in_compact_checkout",
        "path": source_path,
        "sha256": source_digest,
    }
    assert builder._is_valid_unavailable_raw_reference(item)
    with pytest.raises(BuildError, match="unavailable raw input hash is invalid"):
        builder._rewrite_known_paths(
            {"inputs": [{"path": source_path, "sha256": "invalid"}]}
        )


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
    raw_manifest = json.loads((output / "manifests/compact-raw.json").read_text())
    assert raw_manifest["lossless_for_reported_artifacts"] is False
    assert raw_manifest["coverage"]["scope"] == "representative_trajectories_only"
    top_manifest = json.loads((output / "MANIFEST.json").read_text())
    assert top_manifest["release_kind"] == "anonymous_review_supplement"
    for item in top_manifest["files"]:
        assert hashlib.sha256((output / item["path"]).read_bytes()).hexdigest() == item[
            "sha256"
        ]


def test_only_conditional_checklist_paper_inputs_are_optional() -> None:
    assert is_optional_paper_reference("aistats2027_checklist.tex")
    assert is_optional_paper_reference("paper/aistats_checklist.tex")
    assert not is_optional_paper_reference("tables/executed_policy_results.tex")
    assert not is_optional_paper_reference("missing_checklist_notes.tex")


def test_released_validator_removes_all_private_editor_macros(tmp_path: Path) -> None:
    sanitizer = StructuredSanitizer(tmp_path, "a" * 64)
    private_names = (("d", "iego"), ("b", "ahram"), ("h", "oussam"), ("b", "rett"))
    source = " ".join("\\" + first + rest for first, rest in private_names)
    source += " Public citation text remains unchanged"

    released = sanitize_source_text("paper/validate.py", source, sanitizer)

    for first, rest in private_names:
        assert "\\" + first + rest not in released
    assert "Public citation text remains unchanged" in released
