"""Retirement must preserve originals and keep current-input checks strict."""

import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from archived_inputs import archived_input, validate_archive


def test_every_retired_path_is_bound_to_the_original_git_tree():
    records = json.loads((ROOT / "ARCHIVED_FILES.json").read_text())
    assert validate_archive(ROOT) == len(records["files"])
    assert all(not (ROOT / row["path"]).exists() for row in records["files"])


def test_archived_pdf_and_selection_retain_their_locked_hashes():
    for name, expected in (
        ("paper/main.pdf", "2545c368d6b97393f5c1e5bb61d4696f7fed6b8ae988ce42c9d7bc7ccab717e1"),
        ("results/derived/transport_instantiation_selection.json",
         "8c16bec7cc220109df3fd7173c3d06ae6c6e1b95e9db5bc5b8c3377b3564f6f4"),
    ):
        recovered = archived_input(ROOT, name)
        assert not recovered.is_relative_to(ROOT)
        assert hashlib.sha256(recovered.read_bytes()).hexdigest() == expected


def test_missing_current_scientific_inputs_cannot_use_the_archive():
    with pytest.raises(FileNotFoundError, match="not a retired input"):
        archived_input(ROOT, "results/derived/transport_instantiation/missing.json")


def test_existing_tampered_input_is_not_silently_replaced(tmp_path):
    victim = tmp_path / "paper/main.pdf"
    victim.parent.mkdir()
    victim.write_bytes(b"changed")
    assert archived_input(tmp_path, "paper/main.pdf") == victim
    assert victim.read_bytes() == b"changed"
