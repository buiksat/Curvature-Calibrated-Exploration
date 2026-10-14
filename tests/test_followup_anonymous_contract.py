"""The compact anonymous export must preserve observations and fail closed."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import followup_anonymous_contract as contract
import verify_review_experiment_export as export_verifier


@pytest.fixture
def staged(tmp_path):
    contract.stage_transform(tmp_path, ROOT)
    return tmp_path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def documents(path):
    raw = path.read_bytes()
    return [json.loads(line) for line in raw.splitlines()] if path.suffix == ".jsonl" else json.loads(raw)


def test_original_closure_transforms_without_changing_scientific_json(staged):
    assert len(contract.INPUT_PATHS) == len(contract.FOLLOWUP_CONTRACT) == 20
    assert len(contract.ARTIFACT_PINS) == 12
    assert len(contract.SCHEMATIC_PINS) == 2
    assert not contract.validate_original(ROOT)
    assert not contract.validate_packaged(staged)
    for relative in contract.INPUT_PATHS:
        source, target = ROOT / relative, staged / relative
        assert digest(source.read_bytes()) == contract.FOLLOWUP_CONTRACT[relative]["original_sha256"]
        if source.suffix in {".json", ".jsonl"}:
            contract.assert_scientific_values_unchanged(relative, documents(source), documents(target))


def test_compact_terminal_statistics_recompute_after_anonymization(staged):
    report = export_verifier.verify_export(staged / contract.FULL)
    assert report["status"] == "pass"
    assert report["seed_summaries"] == 600
    assert report["terminal_intervals_recomputed"] == 24
    assert "not included" in report["raw_trajectories"]


@pytest.mark.parametrize("relative", [contract.FULL + "raw_input_inventory.jsonl",
    contract.INDEPENDENT + "input_inventory.jsonl", contract.RELATIVE + "input_inventory.jsonl"])
def test_external_inventory_hashes_still_describe_original_unshipped_bytes(staged, relative):
    original, packaged = documents(ROOT / relative), documents(staged / relative)
    assert len(original) == len(packaged)
    for before, after in zip(original, packaged):
        assert after["path"].startswith("original-external/")
        assert {k: v for k, v in before.items() if k != "path"} == {
            k: v for k, v in after.items() if k != "path"}
    declaration = contract.declaration()
    assert declaration["external_inputs"]["included"] is False
    assert "NOT EXECUTED" in declaration["external_inputs"]["raw_replay"]


def test_historical_run_signature_is_preserved_and_explicitly_distinguished(staged):
    relative = contract.FULL + "run_manifest.json"
    before, after = documents(ROOT / relative), documents(staged / relative)
    assert before["signature"] == after["signature"]
    assert before["aggregate_sha256"] == after["aggregate_sha256"]
    assert before["source_inputs"] == after["source_inputs"]
    assert after["git_revision"] == contract.REPLACEMENT_TOKEN
    assert "not signatures" in contract.declaration()["original_provenance"]["run_signatures"]


def test_original_digest_requires_the_entire_package_and_exact_declaration(staged):
    relative = contract.FULL + "aggregate_compact.json"
    assert contract.original_digest(staged, relative) == digest((ROOT / relative).read_bytes())
    (staged / contract.DECLARATION_NAME).unlink()
    with pytest.raises(contract.ContractError, match="Invalid anonymous"):
        contract.original_digest(staged, relative)


def test_self_rehashed_scientific_mutation_and_declaration_are_rejected(staged):
    relative = contract.FULL + "aggregate_compact.json"
    path = staged / relative
    value = documents(path)
    value["policy_outcomes"][0]["cumulative_pseudo_regret"]["mean"] += 1
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    path.write_bytes(data)
    declaration_path = staged / contract.DECLARATION_NAME
    declaration = documents(declaration_path)
    record = next(row for row in declaration["files"] if row["path"] == relative)
    record["packaged_sha256"], record["packaged_bytes"] = digest(data), len(data)
    declaration_path.write_text(json.dumps(declaration))
    manifest_path = staged / (contract.FULL + "export_manifest.json")
    manifest = documents(manifest_path)
    row = next(row for row in manifest["files"] if row["path"] == "aggregate_compact.json")
    row["sha256"], row["bytes"] = digest(data), len(data)
    manifest_path.write_text(json.dumps(manifest))
    errors = contract.validate_packaged(staged)
    assert any("declaration differs" in error for error in errors)
    assert any(relative in error for error in errors)
    with pytest.raises(contract.ContractError):
        contract.original_digest(staged, relative)


def test_unrelated_missing_evidence_prevents_original_digest_authorization(staged):
    (staged / (contract.RELATIVE + "per_seed.jsonl")).unlink()
    with pytest.raises(contract.ContractError):
        contract.original_digest(staged, contract.FULL + "seed_summaries.jsonl")


def test_declaration_boolean_cannot_impersonate_integer_schema(staged):
    path = staged / contract.DECLARATION_NAME
    declaration = documents(path)
    declaration["schema_version"] = True
    path.write_text(json.dumps(declaration))
    assert any("declaration differs" in error for error in contract.validate_packaged(staged))


def test_generated_table_mutation_prevents_original_digest_authorization(staged):
    relative = next(iter(contract.ARTIFACT_PINS))
    with (staged / relative).open("ab") as stream:
        stream.write(b"% changed\n")
    with pytest.raises(contract.ContractError):
        contract.original_digest(staged, contract.FULL + "seed_summaries.jsonl")


def test_source_mutation_unknown_paths_and_numeric_type_changes_fail_closed():
    relative = contract.FULL + "aggregate_compact.json"
    with pytest.raises(contract.ContractError, match="Original evidence differs"):
        contract.transform_bytes(relative, (ROOT / relative).read_bytes() + b" ")
    with pytest.raises(contract.ContractError, match="Unknown"):
        contract.transform_bytes("unexpected.json", b"{}")
    before = documents(ROOT / relative)
    after = json.loads(json.dumps(before))
    after["completed_run_count"] = float(after["completed_run_count"])
    with pytest.raises(contract.ContractError, match="type changed"):
        contract.assert_scientific_values_unchanged(relative, before, after)
    after = json.loads(json.dumps(before))
    after["policy_outcomes"][0]["cumulative_pseudo_regret"]["mean"] += 1
    with pytest.raises(contract.ContractError, match="Scientific value changed"):
        contract.assert_scientific_values_unchanged(relative, before, after)


def test_staging_refuses_source_repository_and_escaping_symlinks(tmp_path):
    with pytest.raises(contract.ContractError, match="in place"):
        contract.stage_transform(ROOT, ROOT)
    (tmp_path / "review").symlink_to(ROOT / "review", target_is_directory=True)
    with pytest.raises(contract.ContractError, match="escapes"):
        contract.stage_transform(tmp_path, ROOT)


def test_all_packaged_revisions_are_tokens_and_paths_are_portable(staged):
    for relative in contract.INPUT_PATHS:
        if not relative.endswith((".json", ".jsonl")):
            continue
        def walk(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"git_revision", "run_source_revision", "source_run_revision"}:
                        assert item == contract.REPLACEMENT_TOKEN
                    yield from walk(item)
            elif isinstance(value, list):
                for item in value:
                    yield from walk(item)
            elif isinstance(value, str):
                yield value
        for value in walk(documents(staged / relative)):
            assert not value.startswith("/workspace/")
            assert not value.startswith("/home/")
