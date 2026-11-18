"""Original-source attribution and ledger scope/identity guards fail closed."""
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import editorial_generator_sources as originals
import make_transport_explanatory_figures as explanatory
import make_transport_table_charts as charts
import verify_tmlr_submission_numbers as ledger


@pytest.mark.parametrize("name,adapter,record", [
    ("make_transport_explanatory_figures.py", explanatory, "transport_explanatory_provenance.json"),
    ("make_transport_table_charts.py", charts, "transport_table_provenance.json"),
])
def test_original_source_preimage_and_self_attribution_match(name, adapter, record):
    source, raw = originals.original_source(name, ROOT / "tools")
    assert raw == subprocess.check_output([
        "git", "-C", str(ROOT), "show",
        "a5fb603777b8187071ba1fc0a054ff84e473fd4b:tools/" + name,
    ])
    pin = hashlib.sha256(raw).hexdigest()
    outputs = adapter.build_original(ROOT)
    assert outputs[Path("paper/figures") / record].encode() == (ROOT / "paper/figures" / record).read_bytes()
    declaration = json.loads(outputs[Path("paper/figures") / record])
    recorded = declaration["generator"]["sha256"] if "generator" in declaration else declaration["generator_sha256"]
    assert recorded == pin
    current = adapter.generator_provenance()
    assert current["original_generator_sha256"] == pin
    assert (ROOT / current["original_source"]).read_bytes() == source.read_bytes()
    assert current["current_generator_sha256"] == hashlib.sha256((ROOT / current["current_generator"]).read_bytes()).hexdigest()
    assert current["current_generator_sha256"] != pin


@pytest.mark.parametrize("name", list(originals.ORIGINAL_GENERATOR_DIGESTS))
def test_original_source_tampering_is_rejected_before_execution_and_after_prior_load(tmp_path, name):
    directory = tmp_path / "editorial_originals"
    directory.mkdir()
    source = directory / name
    shutil.copyfile(ROOT / "tools/editorial_originals" / name, source)
    originals.load_original(name, tmp_path)
    marker = tmp_path / "must-not-execute"
    source.write_text(source.read_text() + "\nfrom pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n")
    with pytest.raises(ValueError, match="Original generator source digest differs"):
        originals.load_original(name, tmp_path)
    assert not marker.exists()


@pytest.fixture
def historical_tree(tmp_path):
    for relative in ledger.HISTORICAL_LEDGER_SOURCES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    return tmp_path


@pytest.mark.parametrize("relative", sorted(ledger.HISTORICAL_LEDGER_SOURCES))
def test_repository_historical_source_deletion_fails_instead_of_reducing_entries(historical_tree, relative):
    before = ledger.build_ledger(historical_tree)
    assert len(before) == 398
    (historical_tree / relative).unlink()
    with pytest.raises(ledger.LedgerError, match="Required historical manuscript sources missing"):
        ledger.build_ledger(historical_tree)
    checks, entries = ledger.run(historical_tree, check_manuscript=False)
    assert entries == []
    assert any(check.status == ledger.STATUS_FAIL and relative in check.detail for check in checks)


def test_unvalidated_package_marker_cannot_exclude_historical_sources(tmp_path):
    (tmp_path / "ANONYMIZATION.json").write_text("{}\n")
    with pytest.raises(ledger.LedgerError, match="Invalid anonymous package for ledger scope"):
        ledger.build_ledger(tmp_path)


def test_original_ledger_reordering_preserves_value_to_phrase_binding(historical_tree, monkeypatch):
    before = ledger.build_ledger(historical_tree)
    original = ledger.historical_and_prior_ledger(historical_tree)
    monkeypatch.setattr(ledger, "historical_and_prior_ledger", lambda root: list(reversed(original)))
    after = ledger.build_ledger(historical_tree)
    assert Counter(map(ledger.ledger_entry_identity, before)) == Counter(map(ledger.ledger_entry_identity, after))


@pytest.mark.parametrize("field,value", [
    ("selector", "different selector"),
    ("source", Path("different/source.json")),
    ("literal", "different original literal"),
    ("display", "31"),
    ("units", "different units"),
    ("population", "different population"),
    ("aggregation", "different aggregation"),
])
def test_changed_original_identity_cannot_be_rebound(historical_tree, monkeypatch, field, value):
    original = ledger.historical_and_prior_ledger(historical_tree)
    original[83] = replace(original[83], **{field: value})
    monkeypatch.setattr(ledger, "historical_and_prior_ledger", lambda root: original)
    with pytest.raises(ledger.LedgerError, match="Original ledger identities differ"):
        ledger.build_ledger(historical_tree)


@pytest.mark.parametrize("mutation", ["dropped", "duplicate"])
def test_original_declaration_set_cannot_silently_drop_or_duplicate_entries(historical_tree, monkeypatch, mutation):
    original = ledger.historical_and_prior_ledger(historical_tree)
    if mutation == "dropped":
        original.pop(85)
    else:
        original.append(original[0])
    monkeypatch.setattr(ledger, "historical_and_prior_ledger", lambda root: original)
    with pytest.raises(ledger.LedgerError, match="Original ledger identit|Duplicate original ledger identity"):
        ledger.build_ledger(historical_tree)
