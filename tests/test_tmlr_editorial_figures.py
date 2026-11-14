"""Editorial transforms preserve table scope and reject altered plot sources."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import prepare_tmlr_figures as editorial


def test_equal_table_and_figure_basenames_do_not_share_a_transform():
    table = Path("paper/tables/transport_instantiation_tightness.tex")
    original = (ROOT / table).read_text()
    assert editorial.apply({table: original}) == {table: original}


def test_changed_original_coordinate_is_rejected():
    original = ROOT / "tools/editorial_originals/transport_conceptual_geometry.tex"
    source = original.read_text()
    assert "(0,-8.32)" in source
    with pytest.raises(ValueError, match="Original generator figure differs"):
        editorial.transform(original.name, source.replace("(0,-8.32)", "(0,-7.32)"))
