"""Chart conversions preserve numerical cells and their statistical interpretation."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import make_transport_table_charts as charts
import verify_tmlr_submission_numbers as ledger


def plotted(text):
    # Read only the actual data marks, excluding interval lines and black rings.
    return Counter(float(x) for x in re.findall(
        r'\\addplot\[only marks,mark=(?!o,)[^\]]+\] coordinates \{\(([^,]+),',text))


def test_all_plotted_values_match_reviewed_table_cells():
    output = charts.build(ROOT)
    def marks(name):
        return plotted(output[Path('paper/figures/transport_table_'+name+'.tex')])
    def rows(name):
        return [[c.strip() for c in s.split('&')] for s in
                (ROOT/'paper/tables'/('transport_'+name+'.tex')).read_text().splitlines()
                if re.match(r'^\d',s)]
    def first(cell):
        # Independent numeric extraction for the ordinary decimal/e-notation cells.
        return float(re.search(r'-?\d+(?:\.\d+)?(?:e[+-]?\d+)?',cell)[0])
    for table,figure,columns in (
        ('followup_same_history','same_history',range(2,6)),
        ('followup_mechanism_variation','mechanism',range(2,4)),
        ('followup_relative_audit','relative',range(1,5)),
        ('instantiation_validity','original_validity',range(7,11)),
        ('instantiation_performance','original_performance',(2,5)),
        ('instantiation_performance','original_distribution',(3,4)),
        ('instantiation_tightness','original_components',range(5,8)),
        ('instantiation_tightness','original_bound_ratios',(8,9)),
    ):
        assert marks(figure)==Counter(first(row[c]) for row in rows(table) for c in columns)
    tightness=rows('instantiation_tightness')
    expected=Counter(first(row[c]) for row in tightness for c in (2,3,4))
    expected.update(int(re.search(r'n_0=(\d+)',row[2])[1]) for row in tightness)
    assert marks('original_path_ratios')==expected
    drift=rows('followup_drift_bounds')
    expected=Counter(first(row[1]) for row in drift)
    expected.update(int(n)/500 for row in drift for n in row[2].split('/'))
    assert marks('drift')==expected
    assert len(output)==11
    for path,text in output.items(): assert (ROOT/path).read_text()==text


def test_intervals_and_condition_labels_preserve_their_meaning():
    output=charts.build(ROOT)
    mechanism=output[Path('paper/figures/transport_table_mechanism.tex')]
    assert 'minimum--maximum seed range, not confidence intervals' in mechanism
    assert 'Every row diagnoses the Hessian score' in mechanism
    for cell in ('99.4 [98.8, 99.9]','97.3 [92.9, 98.6]'):
        mean,low,high=map(float,re.findall(r'\d+\.\d+',cell))
        assert '('+str(low)+',3) ('+str(high)+',3)' in mechanism
    performance=output[Path('paper/figures/transport_table_original_performance.tex')]
    assert 'pointwise 95\\% bootstrap confidence intervals' in performance
    assert performance.count('xmin=75,xmax=98')==4
    assert performance.count('xmin=-15,xmax=1')==4
    same=output[Path('paper/figures/transport_table_same_history.tex')]
    assert same.count('mark=o,mark size=4.6pt')==12
    assert 'not alternative adaptive trajectories' in same


@pytest.fixture
def chart_tree(tmp_path):
    for name in charts.INPUT_HASHES:
        path=Path('paper/tables')/(name+'.tex')
        (tmp_path/path).parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/path,tmp_path/path)
    for path,text in charts.build(ROOT).items():
        (tmp_path/path).parent.mkdir(parents=True,exist_ok=True)
        (tmp_path/path).write_text(text)
    return tmp_path


def test_changed_point_fails_even_after_rewriting_provenance(chart_tree):
    relative=Path('paper/figures/transport_table_original_performance.tex')
    path=chart_tree/relative
    path.write_text(path.read_text().replace('(81,3)','(999,3)',1))
    p=chart_tree/'paper/figures/transport_table_provenance.json'
    record=json.loads(p.read_text());record['outputs'][str(relative)]=hashlib.sha256(path.read_bytes()).hexdigest()
    p.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    result=subprocess.run([sys.executable,str(ROOT/'tools/make_transport_table_charts.py'),
                           '--root',str(chart_tree),'--check'],text=True,capture_output=True)
    assert result.returncode and 'Chart differs' in result.stderr


def test_changed_table_is_rejected(chart_tree):
    path=chart_tree/'paper/tables/transport_instantiation_performance.tex'
    path.write_text(path.read_text().replace('81 [79.5, 82.6]','90 [89.5, 92.6]'))
    with pytest.raises(ValueError,match='Unreviewed chart input'): charts.build(chart_tree)


def test_package_requirement_and_generator_authentication(chart_tree,monkeypatch):
    monkeypatch.setenv(charts.contract.ENV_REQUIRE_PACKAGE,'1')
    with pytest.raises(ValueError,match='declaration'): charts.build(chart_tree)
    path=chart_tree/ledger.TABLE_CHART_GENERATOR
    path.parent.mkdir();path.write_text('raise RuntimeError("must not execute")\n')
    with pytest.raises(ledger.LedgerError,match='unreviewed or missing tool'):
        ledger._load_reviewed_tool(chart_tree,ledger.TABLE_CHART_GENERATOR)
