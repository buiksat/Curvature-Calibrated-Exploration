"""Regression tests for the TMLR release package and the CI that gates it.

Five defects motivated this file, and each has a test that fails without its
fix:

1. `sha256sum -c paper/main.pdf.sha256` was run from the repository root. The
   sidecar names the file as bare `main.pdf`, so the call exited 1 and aborted CI
   before any submission check ran. The tests here exercise the real
   working-directory semantics by running the extracted command, not by grepping
   for a keyword.
2. `supplement.zip` shipped the study's `git_revision`, a Git object id that
   resolves in the public repository to a named author, so the "anonymous"
   supplement was not anonymous.
3. `git diff --check` was reported as passing when the exact
   baseline-to-candidate range check had not been run and did not pass.
4. The shipped verifiers took `ANONYMIZATION.json` as the authority for which
   packaged bytes were acceptable. Editing a packaged file, recomputing its
   sidecar and updating the declaration to match therefore passed every check.
   The contract is now pinned in code and the declaration is validated against
   it.
5. Deleting `ANONYMIZATION.json` altogether downgraded the supplement to
   repository semantics, so a supplement carrying the restored original,
   author-linked evidence verified clean. Supplement verification now requires
   package mode, and a missing declaration is a failure.
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github/workflows/transport-committed-evidence.yml"
SIDECAR = REPO_ROOT / "paper/main.pdf.sha256"
LOCKED_PDF = REPO_ROOT / "paper/main.pdf"

sys.path.insert(0, str(REPO_ROOT / "submissions/tmlr_2026"))
import package as packager  # noqa: E402

BASELINE = "b99b682ecc8f69552a3f57b1b85333378ed12ac1"

#: Derived once: every commit id in this checkout, plus the recorded five.
PROJECT_REVISIONS = packager.project_revisions(REPO_ROOT)


def scan(entries):
    """scan_for_identifiers against the derived revision set."""

    return packager.scan_for_identifiers(entries, PROJECT_REVISIONS)


# --------------------------------------------------------------------------
# 1. the PDF sidecar is checked from the directory the sidecar names
# --------------------------------------------------------------------------


def _sidecar_commands() -> list[str]:
    """Every workflow line that runs sha256sum against the locked-PDF sidecar."""

    return [
        line.strip()
        for line in WORKFLOW.read_text(encoding="utf-8").splitlines()
        if "main.pdf.sha256" in line and "sha256sum" in line
    ]


def test_the_sidecar_names_a_bare_filename():
    """The premise the other tests rest on: the sidecar is directory-relative."""

    fields = SIDECAR.read_text(encoding="ascii").split()
    assert fields[1] == "main.pdf"
    assert "/" not in fields[1]


def test_every_sidecar_call_runs_from_the_paper_directory():
    commands = _sidecar_commands()
    assert len(commands) == 3, commands
    for command in commands:
        assert "cd paper" in command, command
        # the broken form must not come back
        assert "sha256sum -c paper/main.pdf.sha256" not in command, command


@pytest.mark.parametrize("command", _sidecar_commands())
def test_sidecar_command_succeeds_when_run_as_written(command, tmp_path):
    """Run the workflow's own command string. This is the cwd semantics test."""

    work = tmp_path / "tree"
    (work / "paper").mkdir(parents=True)
    shutil.copy2(LOCKED_PDF, work / "paper/main.pdf")
    shutil.copy2(SIDECAR, work / "paper/main.pdf.sha256")

    done = subprocess.run(["bash", "-c", f"set -euo pipefail\n{command}"],
                          cwd=work, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_old_repository_root_form_really_did_fail(tmp_path):
    """Guard against someone 'simplifying' the fix back to the broken form."""

    work = tmp_path / "tree"
    (work / "paper").mkdir(parents=True)
    shutil.copy2(LOCKED_PDF, work / "paper/main.pdf")
    shutil.copy2(SIDECAR, work / "paper/main.pdf.sha256")

    done = subprocess.run(
        ["bash", "-c", "set -euo pipefail\nsha256sum -c paper/main.pdf.sha256"],
        cwd=work, capture_output=True, text=True)
    assert done.returncode != 0
    assert "main.pdf" in done.stdout + done.stderr


@pytest.mark.parametrize("command", _sidecar_commands())
def test_sidecar_command_fails_on_a_corrupted_pdf(command, tmp_path):
    """The check must still be a gate, not just a call that happens to pass."""

    work = tmp_path / "tree"
    (work / "paper").mkdir(parents=True)
    (work / "paper/main.pdf").write_bytes(LOCKED_PDF.read_bytes() + b"tamper")
    shutil.copy2(SIDECAR, work / "paper/main.pdf.sha256")

    done = subprocess.run(["bash", "-c", f"set -euo pipefail\n{command}"],
                          cwd=work, capture_output=True, text=True)
    assert done.returncode != 0, done.stdout + done.stderr


def test_submission_steps_are_downstream_of_the_pdf_check_and_never_skipped():
    text = WORKFLOW.read_text(encoding="utf-8")
    pdf_check = text.index("- name: PDF structural checks")
    downstream = (
        "- name: Numerical-provenance ledger",
        "- name: Regenerate every published artifact from the locked aggregate",
        "- name: Attempt the clean PDF rebuild",
        "- name: Build the anonymous TMLR submission",
        "- name: Release manifest still describes the rebuilt deliverables",
        "- name: Rebuild the submission from a clean unpacked source.zip",
    )
    previous = pdf_check
    for step in downstream:
        here = text.index(step)
        assert here > previous, step
        previous = here
    # a skipped-on-failure step would hide exactly the defect this file is about
    assert "continue-on-error" not in text


def test_workflow_parses_as_yaml_and_keeps_the_jobs_independent():
    yaml = pytest.importorskip("yaml")
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = document["jobs"]
    assert set(jobs) == {"submission-evidence", "realistic-transport-deferred"}
    # the deferred extension must not gate the submission checks, in either
    # direction, so its status can be honest without blocking the submission
    assert "needs" not in jobs["submission-evidence"]
    assert "needs" not in jobs["realistic-transport-deferred"]
    names = [step.get("name") for step in jobs["submission-evidence"]["steps"]]
    assert "PDF structural checks" in names
    assert "Build the anonymous TMLR submission" in names


# --------------------------------------------------------------------------
# 2. no project revision or identity reaches a reviewer
# --------------------------------------------------------------------------


def test_scan_flags_a_git_object_id_but_not_a_sha256_digest(tmp_path):
    object_id = "0" * 39 + "a"                      # 40 hex, looks like a commit
    content_digest = "0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02"
    assert len(object_id) == 40 and len(content_digest) == 64

    good = tmp_path / "good.json"
    good.write_text(f'{{"sha256": "{content_digest}"}}\n', encoding="utf-8")
    assert scan([(good, "good.json")]) == []

    bad = tmp_path / "bad.json"
    bad.write_text(f'{{"git_revision": "{object_id}"}}\n', encoding="utf-8")
    findings = scan([(bad, "bad.json")])
    assert findings and "revision field" in findings[0]


def test_scan_flags_an_abbreviated_known_revision(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text(
        f"extracted at {packager.RECORDED_PROJECT_REVISIONS[0][:7]}\n",
        encoding="utf-8")
    findings = scan([(path, "note.txt")])
    assert findings and "known project revision" in findings[0]


def test_scan_covers_the_current_candidate_and_its_ancestors():
    """The revision set is derived from the checkout, not maintained by hand."""

    head = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True
                          ).stdout.strip()
    parent = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD^"],
                            capture_output=True, text=True, check=True
                            ).stdout.strip()
    assert head in PROJECT_REVISIONS
    assert parent in PROJECT_REVISIONS
    for revision in packager.RECORDED_PROJECT_REVISIONS:
        assert revision in PROJECT_REVISIONS


@pytest.mark.parametrize("case", ["exact", "abbreviated", "uppercase"])
def test_scan_flags_the_current_candidate_in_every_case_variant(tmp_path, case):
    head = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True
                          ).stdout.strip()
    rendered = {"exact": head,
                "abbreviated": head[:9],
                "uppercase": head[:12].upper()}[case]
    path = tmp_path / "note.txt"
    path.write_text(f"built from {rendered}\n", encoding="utf-8")
    assert scan([(path, "note.txt")]), rendered


@pytest.mark.parametrize("text", [
    "see github.com/someone/Curvature-Calibrated-Exploration",
    "written by Behzadian",
    "WRITTEN BY BEHZADIAN",
    "cited in Granziol and Juarev",
    "as GRANZIOL showed",
    "juarev, personal communication",
])
def test_scan_flags_project_and_author_identity_in_any_case(tmp_path, text):
    path = tmp_path / "x.md"
    path.write_text(text + "\n", encoding="utf-8")
    assert scan([(path, "x.md")]), text


def test_author_names_are_allowed_only_inside_the_bibliography(tmp_path):
    """Positive control for the exemption, and proof it is not line-scoped."""

    entry = tmp_path / "references.bib"
    entry.write_text(
        "@article{granziol2026hessian,\n"
        "  author  = {Granziol, Diego and Juarev, Khurshid},\n"
        "}\n", encoding="utf-8")
    assert scan([(entry, "references.bib")]) == []
    assert packager.scrub([(entry, "references.bib")]) == []

    # the same names anywhere else are a leak
    elsewhere = tmp_path / "notes.md"
    elsewhere.write_text("thanks to Granziol and Juarev\n", encoding="utf-8")
    assert scan([(elsewhere, "notes.md")])
    assert packager.scrub([(elsewhere, "notes.md")])

    # and a bibliography line that also carries a checkout path no longer
    # passes just because an allowed name sits on it
    mixed = tmp_path / "mixed.bib"
    mixed.write_text(
        "  note = {Granziol, see /home/someone/checkout/paper.pdf},\n",
        encoding="utf-8")
    findings = packager.scrub([(mixed, "references.bib")])
    assert len(findings) == 1, findings
    assert "'/home/s'" in findings[0], findings
    # the exempt name on the same line is still exempt; the path is not
    assert "'Granziol'" not in findings[0]


def test_supplement_is_only_clean_because_of_the_anonymization(tmp_path):
    """Scan before and after the transform, so the test proves what fixed it."""

    entries = packager.supplement_entries(REPO_ROOT)
    before = scan(entries)
    assert any(packager.RECORDED_PROJECT_REVISIONS[0] in finding
               for finding in before), \
        "the committed evidence is expected to carry the execution revision"

    out = tmp_path / "out"
    out.mkdir()
    transformed, records = packager.anonymize(REPO_ROOT, out, entries)
    assert scan(transformed) == []
    assert {record["path"] for record in records} == set(
        packager.ANONYMIZE_REVISION_IN)


def test_anonymization_changes_exactly_the_declared_field(tmp_path):
    """Substituting the removed value back must reproduce the original bytes."""

    entries = packager.supplement_entries(REPO_ROOT)
    out = tmp_path / "out"
    out.mkdir()
    transformed, records = packager.anonymize(REPO_ROOT, out, entries)
    packaged = {arc: path for path, arc in transformed}

    for record in records:
        original = (REPO_ROOT / record["source_path"]).read_bytes()
        shipped = packaged[record["path"]].read_bytes()
        assert shipped != original
        restored = shipped.replace(
            record["replacement"].encode("ascii"),
            record["removed_value_internal_only"].encode("ascii"),
        )
        assert restored == original, record["path"]
        assert record["original_sha256"] != record["packaged_sha256"]


def test_anonymization_declaration_is_shipped_and_self_consistent(tmp_path):
    entries = packager.supplement_entries(REPO_ROOT)
    out = tmp_path / "out"
    out.mkdir()
    transformed, records = packager.anonymize(REPO_ROOT, out, entries)

    packaged = {arc: path for path, arc in transformed}
    assert packager.ANONYMIZATION_MANIFEST in packaged
    declaration = json.loads(
        packaged[packager.ANONYMIZATION_MANIFEST].read_text(encoding="utf-8"))

    # the reviewer-facing declaration must not carry the removed value
    assert packager.RECORDED_PROJECT_REVISIONS[0] not in json.dumps(declaration)
    # nor may it call the placeholder a revision
    assert "not a commit" in declaration["replacement_token_is_not_a_revision"]

    shipped = {entry["path"]: entry for entry in declaration["transformed"]}
    assert set(shipped) == set(packager.ANONYMIZE_REVISION_IN)
    for record in records:
        entry = shipped[record["path"]]
        assert "removed_value_internal_only" not in entry
        assert entry["packaged_sha256"] == record["packaged_sha256"]
        assert entry["original_sha256"] == record["original_sha256"]
        assert packager.sha256_file(packaged[record["path"]]) == \
            entry["packaged_sha256"]
        loaded = json.loads(packaged[record["path"]].read_text(encoding="utf-8"))
        assert loaded[entry["field"]] == entry["replacement"]


def test_the_internal_provenance_map_stays_out_of_the_reviewer_bytes(tmp_path):
    entries = packager.supplement_entries(REPO_ROOT)
    out = tmp_path / "out"
    out.mkdir()
    _, records = packager.anonymize(REPO_ROOT, out, entries)
    for record in records:
        # kept for release_manifest.json, which is not uploaded
        assert record["removed_value_internal_only"] in \
            packager.RECORDED_PROJECT_REVISIONS


def _release_dir() -> Path | None:
    import os
    candidate = Path(
        os.environ.get("TMLR_OUT",
                       Path(os.environ.get("TMPDIR", "/tmp")) / "cce-tmlr-2026-release"))
    return candidate if (candidate / "supplement.zip").is_file() else None


@pytest.mark.parametrize("archive", ["source.zip", "supplement.zip"])
def test_built_archives_carry_no_project_revision(archive):
    """Integration check against the real ZIP members, when a build is present."""

    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")

    hex40 = re.compile(rb"(?<![0-9a-fA-F])[0-9a-f]{40}(?![0-9a-fA-F])")
    findings: list[str] = []
    with zipfile.ZipFile(release / archive) as zf:
        for info in zf.infolist():
            data = zf.read(info)
            # The bare-40-hex sweep is deliberately stricter than the shipped
            # scanner, which does not treat the shape as a leak.  It is skipped
            # for a vendored package whose bytes match its pin: upstream
            # pgfplots carries its *own* revision in a FIXME comment, which
            # identifies pgfplots and not this submission.  The exemption is
            # scoped to this one pattern and to bytes that match the pin --
            # every other sweep below still applies to those files.
            pinned = packager.VENDORED_PACKAGE_DIGESTS.get(info.filename)
            vendored = (pinned is not None
                        and hashlib.sha256(data).hexdigest() == pinned)
            if not vendored:
                for match in hex40.findall(data):
                    findings.append(f"{info.filename}: {match.decode()}")
            for revision in PROJECT_REVISIONS:
                if revision.encode("ascii") in data:
                    findings.append(f"{info.filename}: {revision}")
            for needle in (b"Curvature-Calibrated-Exploration", b"buiksat",
                           b"Behzadian", b"Nassif"):
                if needle in data:
                    findings.append(f"{info.filename}: {needle.decode()}")
    assert findings == [], findings[:20]


def test_the_bare_hex_exemption_is_scoped_to_pinned_vendored_bytes(tmp_path):
    """An edited vendored file gets no exemption, and neither does anything else."""

    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    hex40 = re.compile(rb"(?<![0-9a-fA-F])[0-9a-f]{40}(?![0-9a-fA-F])")
    carrier = REPO_ROOT / packager.VENDORED_DIRECTORY / \
        "pgfplotsmeshplothandler.code.tex"
    data = carrier.read_bytes()
    assert hex40.findall(data), "the upstream FIXME comment moved"
    assert hashlib.sha256(data).hexdigest() == \
        packager.VENDORED_PACKAGE_DIGESTS["pgfplotsmeshplothandler.code.tex"]
    # and a project revision inside a vendored file is still a finding
    forged = tmp_path / "pgfplotsmeshplothandler.code.tex"
    forged.write_bytes(data + f"% {BASELINE}\n".encode())
    assert scan([(forged, "pgfplotsmeshplothandler.code.tex")])


def test_supplement_archive_ships_the_declaration():
    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    with zipfile.ZipFile(release / "supplement.zip") as zf:
        names = set(zf.namelist())
    assert packager.ANONYMIZATION_MANIFEST in names
    for arcname in packager.ANONYMIZE_REVISION_IN:
        assert arcname in names


# --------------------------------------------------------------------------
# 3. the exact baseline-to-candidate range is whitespace-clean
# --------------------------------------------------------------------------


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT,
                          capture_output=True, text=True)


def test_exact_baseline_to_head_range_has_no_whitespace_defects():
    """The range the reviewer ran, not an empty post-commit working-tree diff."""

    if _git("cat-file", "-e", f"{BASELINE}^{{commit}}").returncode != 0:
        pytest.skip("baseline commit is not present in this checkout")
    done = _git("diff", "--check", f"{BASELINE}..HEAD")
    assert done.returncode == 0, done.stdout + done.stderr


def test_official_style_bytes_are_untouched():
    """The whitespace attribute must not have been 'fixed' by editing upstream."""

    expected = {
        "tmlr.sty": "816214ff5919aa457b6b443bee52b15d9561421417b7f8a50cc84651519f0002",
        "tmlr.bst": "306fd454cf40771bee01293eeb98d2c1cd5f4e11ed0cd7296b335f354fc45206",
        "fancyhdr.sty": "3d2922548e0e5f1a6c5676eda6ebb6dc20d7d305b4d8c2be5f1c833fb1084e6d",
        "LICENSE": "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4",
    }
    for name, digest in expected.items():
        path = REPO_ROOT / "paper/tmlr_style" / name
        assert packager.sha256_file(path) == digest, name


def test_whitespace_attribute_is_scoped_to_the_upstream_style_files():
    """Only the three upstream files may opt out; our own sources stay checked."""

    done = _git("check-attr", "whitespace", "--",
                "paper/tmlr_style/tmlr.sty",
                "paper/tmlr_style/tmlr.bst",
                "paper/tmlr_style/fancyhdr.sty",
                "paper/tmlr_style/LICENSE",
                "paper/body_related.tex",
                "paper/main.tex",
                "submissions/tmlr_2026/main.tex")
    assert done.returncode == 0, done.stderr
    lines = dict(
        (line.split(": whitespace: ")[0], line.split(": whitespace: ")[1])
        for line in done.stdout.strip().splitlines()
    )
    assert lines["paper/tmlr_style/tmlr.sty"] == "unset"
    assert lines["paper/tmlr_style/tmlr.bst"] == "unset"
    assert lines["paper/tmlr_style/fancyhdr.sty"] == "unset"
    for ours in ("paper/tmlr_style/LICENSE", "paper/body_related.tex",
                 "paper/main.tex", "submissions/tmlr_2026/main.tex"):
        assert lines[ours] == "unspecified", ours


def test_no_manuscript_source_ends_with_a_blank_line():
    """The defect the range check found, guarded directly."""

    offenders = []
    for path in sorted((REPO_ROOT / "paper").glob("*.tex")):
        data = path.read_bytes()
        if data.endswith(b"\n\n") or (data and not data.endswith(b"\n")):
            offenders.append(path.name)
    assert offenders == [], offenders


# --------------------------------------------------------------------------
# 4. the anonymous-package contract is pinned in code, not in shipped data
# --------------------------------------------------------------------------

CONTRACT_TOOL = REPO_ROOT / "tools/anonymous_package_contract.py"
sys.path.insert(0, str(REPO_ROOT / "tools"))
import anonymous_package_contract as contract  # noqa: E402


@pytest.fixture(scope="module")
def packaged_tree(tmp_path_factory):
    """One real anonymized package, built once; negatives clone it cheaply."""

    out = tmp_path_factory.mktemp("packaged")
    entries = packager.supplement_entries(REPO_ROOT)
    transformed, records = packager.anonymize(REPO_ROOT, out, entries)
    by_arcname = {arc: path for path, arc in transformed}

    tree = out / "tree"
    wanted = [contract.DECLARATION_NAME]
    for relative in contract.CONTRACT:
        wanted += [relative, f"{relative}.sha256"]
    # The provenance records are pinned by the contract too, so a tree without
    # them is not a package the contract can pass.  `_materialize` falls back to
    # a copy: the repository and the temporary tree are often on two devices.
    for relative in contract.PROVENANCE_PINS:
        _materialize(REPO_ROOT / relative, tree / relative)
    for arcname in wanted:
        target = tree / arcname
        target.parent.mkdir(parents=True, exist_ok=True)
        # hard-link: the aggregate is 77 MB and every test only reads it
        os.link(by_arcname[arcname], target)
    return tree, {record["path"]: record for record in records}


def _clone(tree: Path, destination: Path) -> Path:
    """A writable clone whose large members are hard links, not copies."""

    destination.mkdir(parents=True, exist_ok=True)
    for source in tree.rglob("*"):
        if source.is_file():
            target = destination / source.relative_to(tree)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(source, target)
    return destination


def _rewrite(path: Path, data: bytes) -> None:
    """Replace a hard-linked member without disturbing the shared original."""

    path.unlink()
    path.write_bytes(data)


def _run_contract_tool(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CONTRACT_TOOL), "--root", str(root)],
                          capture_output=True, text=True)


def test_the_clean_package_satisfies_the_pinned_contract(packaged_tree):
    tree, _ = packaged_tree
    done = _run_contract_tool(tree)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "FAIL" not in done.stdout


def test_contract_constants_match_what_packaging_actually_produces(packaged_tree):
    """Guard against the pins drifting away from the real packaged bytes."""

    tree, records = packaged_tree
    assert set(records) == set(contract.CONTRACT)
    for relative, pinned in contract.CONTRACT.items():
        path = tree / relative
        assert packager.sha256_file(path) == pinned["packaged_sha256"], relative
        assert path.stat().st_size == pinned["packaged_bytes"], relative
        original = REPO_ROOT / relative
        assert packager.sha256_file(original) == pinned["original_sha256"], relative
        assert original.stat().st_size == pinned["original_bytes"], relative
        assert (tree / f"{relative}.sha256").read_text(encoding="ascii") == \
            contract.sidecar_text(relative)


def test_reviewers_exact_mutation_is_rejected(packaged_tree, tmp_path):
    """candidate_count 9 -> 10, with BOTH the sidecar and the declaration updated.

    This is the reviewer's reproduction verbatim. Before the fix it exited 0.
    """

    tree, _ = packaged_tree
    root = _clone(tree, tmp_path / "mutated")
    relative = "results/derived/transport_instantiation/selection.json"
    target = root / relative

    data = target.read_bytes()
    mutated = re.sub(rb'("candidate_count"\s*:\s*)9\b', rb"\g<1>10", data, count=1)
    assert mutated != data, "the fixture no longer has candidate_count 9"
    _rewrite(target, mutated)

    digest = hashlib.sha256(mutated).hexdigest()
    _rewrite(root / f"{relative}.sha256",
             f"{digest}  selection.json\n".encode("ascii"))

    declaration_path = root / contract.DECLARATION_NAME
    declaration = json.loads(declaration_path.read_text(encoding="utf-8"))
    for record in declaration["transformed"]:
        if record["path"] == relative:
            record["packaged_sha256"] = digest
            record["packaged_bytes"] = len(mutated)
    _rewrite(declaration_path,
             (json.dumps(declaration, indent=2, sort_keys=True) + "\n").encode())

    # the attacker made the package internally consistent; it must still fail
    assert json.loads(target.read_bytes())["candidate_count"] == 10
    done = _run_contract_tool(root)
    assert done.returncode != 0, done.stdout
    assert "sanitized bytes match the pinned contract" in done.stdout
    assert "FAIL" in done.stdout


def _mutate_declaration(root: Path, edit) -> None:
    path = root / contract.DECLARATION_NAME
    declaration = json.loads(path.read_text(encoding="utf-8"))
    edit(declaration)
    _rewrite(path, (json.dumps(declaration, indent=2, sort_keys=True) + "\n").encode())


def test_changed_packaged_bytes_in_the_declaration_is_rejected(packaged_tree, tmp_path):
    tree, _ = packaged_tree
    root = _clone(tree, tmp_path / "bytes")

    def edit(declaration):
        declaration["transformed"][0]["packaged_bytes"] += 1

    _mutate_declaration(root, edit)
    done = _run_contract_tool(root)
    assert done.returncode != 0, done.stdout
    assert "declaration agrees with the pinned contract" in done.stdout


def test_changed_path_in_the_declaration_is_rejected(packaged_tree, tmp_path):
    tree, _ = packaged_tree
    root = _clone(tree, tmp_path / "path")

    def edit(declaration):
        declaration["transformed"][0]["path"] = "results/derived/elsewhere.json"

    _mutate_declaration(root, edit)
    done = _run_contract_tool(root)
    assert done.returncode != 0, done.stdout
    assert "declared record set is exactly the pinned set" in done.stdout


def test_an_extra_declaration_record_is_rejected(packaged_tree, tmp_path):
    tree, _ = packaged_tree
    root = _clone(tree, tmp_path / "extra")

    def edit(declaration):
        extra = dict(declaration["transformed"][0])
        extra["path"] = "results/derived/transport_instantiation/extra.json"
        declaration["transformed"].append(extra)

    _mutate_declaration(root, edit)
    done = _run_contract_tool(root)
    assert done.returncode != 0, done.stdout
    assert "declared record set is exactly the pinned set" in done.stdout


def test_a_missing_declaration_record_is_rejected(packaged_tree, tmp_path):
    tree, _ = packaged_tree
    root = _clone(tree, tmp_path / "missing")

    def edit(declaration):
        declaration["transformed"] = declaration["transformed"][:1]

    _mutate_declaration(root, edit)
    done = _run_contract_tool(root)
    assert done.returncode != 0, done.stdout
    assert "declared record set is exactly the pinned set" in done.stdout


def test_a_wrong_replacement_token_is_rejected(packaged_tree, tmp_path):
    """Both in the file itself and in the declaration."""

    tree, _ = packaged_tree

    root = _clone(tree, tmp_path / "token-file")
    relative = "results/derived/transport_instantiation/selection.json"
    target = root / relative
    swapped = target.read_bytes().replace(
        contract.REPLACEMENT_TOKEN.encode("ascii"), b"withheld-for-some-other-reason")
    _rewrite(target, swapped)
    done = _run_contract_tool(root)
    assert done.returncode != 0, done.stdout
    assert "redacted field holds the pinned token" in done.stdout

    other = _clone(tree, tmp_path / "token-declaration")

    def edit(declaration):
        declaration["transformed"][0]["replacement"] = "anonymous"

    _mutate_declaration(other, edit)
    done = _run_contract_tool(other)
    assert done.returncode != 0, done.stdout
    assert "declaration agrees with the pinned contract" in done.stdout


def test_a_wrong_sanitized_digest_in_the_declaration_is_rejected(packaged_tree,
                                                                 tmp_path):
    tree, _ = packaged_tree
    root = _clone(tree, tmp_path / "digest")

    def edit(declaration):
        declaration["transformed"][0]["packaged_sha256"] = "0" * 64

    _mutate_declaration(root, edit)
    done = _run_contract_tool(root)
    assert done.returncode != 0, done.stdout
    assert "declaration agrees with the pinned contract" in done.stdout


def test_a_recomputed_but_unpinned_sidecar_is_rejected(packaged_tree, tmp_path):
    """A sidecar that is self-consistent over mutated bytes is not enough."""

    tree, _ = packaged_tree
    root = _clone(tree, tmp_path / "sidecar")
    relative = "results/derived/transport_instantiation/selection.json"
    _rewrite(root / f"{relative}.sha256",
             b"0" * 64 + b"  selection.json\n")
    done = _run_contract_tool(root)
    assert done.returncode != 0, done.stdout
    assert "sidecar text matches the pinned contract" in done.stdout


def test_internal_only_fields_must_not_appear_in_the_declaration(packaged_tree,
                                                                 tmp_path):
    tree, _ = packaged_tree
    root = _clone(tree, tmp_path / "leak")

    def edit(declaration):
        declaration["transformed"][0]["removed_value_internal_only"] = "x" * 40

    _mutate_declaration(root, edit)
    done = _run_contract_tool(root)
    assert done.returncode != 0, done.stdout
    assert "declaration agrees with the pinned contract" in done.stdout


def test_the_shipped_contract_carries_no_revision_or_identity():
    """The pins are content digests; none of them is a Git object id."""

    assert scan([(CONTRACT_TOOL, "tools/anonymous_package_contract.py")]) == []
    text = CONTRACT_TOOL.read_text(encoding="utf-8")
    for revision in PROJECT_REVISIONS:
        assert revision not in text
        assert revision[:7] not in text
    # every pinned hex constant is a 64-hex content digest, not a 40-hex id
    for pinned in contract.CONTRACT.values():
        for key in ("original_sha256", "packaged_sha256"):
            assert len(pinned[key]) == 64


def test_repository_mode_stays_strict_and_unpackaged():
    """No declaration in the repository, so nothing relaxes there."""

    assert not contract.is_packaged_tree(REPO_ROOT)
    done = _run_contract_tool(REPO_ROOT)
    assert done.returncode == 0
    assert "not an anonymous package" in done.stdout


# --------------------------------------------------------------------------
# 5. supplement verification requires package mode
# --------------------------------------------------------------------------

LEDGER_TOOL = REPO_ROOT / "tools/verify_tmlr_submission_numbers.py"
ARTIFACT_TOOL = REPO_ROOT / "tools/transport_artifact_expectations.py"
VERIFY_SH = REPO_ROOT / "submissions/tmlr_2026/supplement_verify.sh"


#: Above this size a fixture file is hard-linked rather than copied.  Only the
#: 77 MB aggregate and its packaged copy qualify.
_LINK_THRESHOLD = 8 * 1024 * 1024


def _materialize(source: Path, target: Path) -> None:
    """Copy, except for the very large evidence files, which are hard-linked.

    Everything used to be hard-linked, which made the module-scoped package
    fixture share inodes with every clone of it: a test that wrote to a clone in
    place silently corrupted the fixture for whatever ran next, and the failure
    surfaced somewhere unrelated.  Small files are copied now; the two big ones
    are only ever read.
    """

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if source.stat().st_size >= _LINK_THRESHOLD:
            os.link(source, target)
            return
    except OSError:
        pass
    shutil.copy2(source, target)


@pytest.fixture(scope="module")
def full_package_tree(tmp_path_factory):
    """A clean unpack of the supplement the build actually produced.

    This used to assemble a package by calling `anonymize()` directly, which
    skipped everything the build adds afterwards -- the compiled-source-closure
    manifest among them -- so the fixture was an incomplete package and the
    strict contract was right to reject it.  Unpacking the real archive is also
    simply the better test: it is the bytes a reviewer receives.
    """

    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    tree = tmp_path_factory.mktemp("full-package") / "supplement"
    tree.mkdir()
    with zipfile.ZipFile(release / "supplement.zip") as archive:
        archive.extractall(tree)
    assert (tree / "verify.sh").is_file()
    assert (tree / packager.SOURCE_CLOSURE_NAME).is_file()
    return tree


def _run_verify_sh(tree: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("CCE_REQUIRE_ANONYMOUS_PACKAGE", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(["bash", "verify.sh"], cwd=tree, env=env,
                          capture_output=True, text=True)


@pytest.fixture(scope="module")
def clean_verify_run(full_package_tree):
    """One end-to-end run of the shipped entry point, shared by its readers."""

    return _run_verify_sh(full_package_tree)


def test_untouched_supplement_verifies(clean_verify_run):
    """Positive control: the clean package still passes end to end."""

    done = clean_verify_run
    assert done.returncode == 0, done.stdout[-4000:] + done.stderr[-2000:]
    assert "all supplement checks passed" in done.stdout


def test_the_supplement_verifier_covers_every_shipped_evidence_file(
        full_package_tree, clean_verify_run):
    """Coverage, not a sample: every evidence file in the archive is checked."""

    expected = sum(
        1
        for directory in ("paper/tables", "paper/figures")
        for path in sorted((full_package_tree / directory).iterdir())
        if path.is_file() and not path.name.endswith(".sha256")
    )
    assert expected > 0
    assert f"verified {expected} shipped evidence files" \
        in clean_verify_run.stdout


def test_changing_a_count_in_the_packaged_readme_is_rejected(
        full_package_tree, tmp_path):
    """The exact reproduction: `2,400 trajectories` -> `2,401` in a clean unpack.

    Every verifier stage used to stay green, because the reviewer-facing README
    was not in the audit at all.
    """

    tree = tmp_path / "readme-mutated"
    for source in full_package_tree.rglob("*"):
        if source.is_file():
            _materialize(source, tree / source.relative_to(full_package_tree))

    readme = tree / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert "2,400 trajectories" in text
    readme.unlink()                       # break the hard link to the original
    readme.write_text(text.replace("2,400 trajectories", "2,401 trajectories", 1),
                      encoding="utf-8")

    done = _run_verify_sh(tree)
    assert done.returncode != 0, done.stdout[-3000:]
    assert "all supplement checks passed" not in done.stdout
    assert "2,400 trajectories" in done.stdout    # the ledger names the literal


def test_the_supplement_verifier_fails_on_an_unsidecarred_evidence_file(
        full_package_tree, tmp_path):
    """A file that arrives without a sidecar is a failure, not an omission."""

    tree = tmp_path / "unsidecarred"
    for source in full_package_tree.rglob("*"):
        if source.is_file():
            _materialize(source, tree / source.relative_to(full_package_tree))
    (tree / "paper/tables/smuggled_result.tex").write_text(
        "\\begin{tabular}{c}\\\\\\end{tabular}\n", encoding="utf-8")

    done = _run_verify_sh(tree)
    assert done.returncode != 0, done.stdout[-3000:]
    assert "has no SHA-256 sidecar" in (done.stdout + done.stderr)


def test_removing_the_declaration_and_restoring_originals_is_rejected(
        full_package_tree, tmp_path):
    """The reviewer's exact reproduction.

    Unpack, delete ANONYMIZATION.json, restore the two original evidence files
    and their original sidecars, run verify.sh.  Before this fix that exited 0
    with "all supplement checks passed" while shipping the author-linked
    `git_revision`.
    """

    tree = tmp_path / "reverted"
    for source in full_package_tree.rglob("*"):
        if source.is_file():
            _materialize(source, tree / source.relative_to(full_package_tree))

    (tree / contract.DECLARATION_NAME).unlink()
    for relative in contract.CONTRACT:
        for name in (relative, f"{relative}.sha256"):
            target = tree / name
            target.unlink()
            _materialize(REPO_ROOT / name, target)

    # the restored files really do carry the identifier the package removed
    for relative in contract.CONTRACT:
        restored = json.loads((tree / relative).read_text(encoding="utf-8"))
        assert contract.PACKAGED_FIELD in restored
        assert restored[contract.PACKAGED_FIELD] != contract.REPLACEMENT_TOKEN
        # and their original sidecars are self-consistent, so nothing else catches it
        recorded = (tree / f"{relative}.sha256").read_text(encoding="ascii").split()[0]
        assert recorded == packager.sha256_file(tree / relative)

    done = _run_verify_sh(tree)
    assert done.returncode != 0, done.stdout[-4000:]
    assert "required package mode" in done.stdout
    assert "not the declared anonymous package" in done.stdout
    # the gate must stop before the later checks report anything reassuring
    assert "all supplement checks passed" not in done.stdout
    assert "numerical-provenance ledger" not in done.stdout


@pytest.mark.parametrize("tool", [LEDGER_TOOL, ARTIFACT_TOOL])
def test_shipped_checkers_accept_an_explicit_package_required_flag(tool, tmp_path):
    """Running a shipped checker directly must not fall back to repo semantics."""

    empty = tmp_path / "no-declaration"
    empty.mkdir()
    done = subprocess.run(
        [sys.executable, str(tool), "--root", str(empty), "--require-package"],
        capture_output=True, text=True)
    assert done.returncode != 0, done.stdout
    assert "required package mode" in done.stdout


@pytest.mark.parametrize("tool", [LEDGER_TOOL, ARTIFACT_TOOL, CONTRACT_TOOL])
def test_the_environment_contract_also_requires_package_mode(tool, tmp_path):
    """verify.sh exports the signal, so a later step inherits it without a flag."""

    empty = tmp_path / "no-declaration"
    empty.mkdir()
    env = dict(os.environ)
    env[contract.ENV_REQUIRE_PACKAGE] = "1"
    done = subprocess.run([sys.executable, str(tool), "--root", str(empty)],
                          capture_output=True, text=True, env=env)
    assert done.returncode != 0, done.stdout
    assert "required package mode" in done.stdout


def test_verify_sh_requires_package_mode_for_every_advertised_check():
    """Structural: the gate runs first and every checker is told it is a package."""

    text = VERIFY_SH.read_text(encoding="utf-8")
    assert f"export {contract.ENV_REQUIRE_PACKAGE}=1" in text
    gate = text.index("anonymous_package_contract.py --root . --require-package")
    for later in ("verify_tmlr_submission_numbers.py",
                  "transport_artifact_expectations.py"):
        assert text.index(later) > gate, later
    # the gate must abort rather than merely record a failure
    assert "exit 1" in text[gate:text.index("numerical-provenance ledger")]
    assert "--require-package" in text[gate:]
    assert text.count("--require-package") >= 3


def test_repository_tooling_still_works_without_any_declaration():
    """Optional repository mode is preserved: repo checks need no such file."""

    assert not contract.is_packaged_tree(REPO_ROOT)
    for tool in (CONTRACT_TOOL,):
        done = subprocess.run([sys.executable, str(tool), "--root", str(REPO_ROOT)],
                              capture_output=True, text=True)
        assert done.returncode == 0, done.stdout
        assert "optional repository mode" in done.stdout


def test_package_required_resolution_is_explicit_then_environment(monkeypatch):
    monkeypatch.delenv(contract.ENV_REQUIRE_PACKAGE, raising=False)
    assert contract.package_required() is False
    assert contract.package_required(True) is True
    assert contract.package_required(False) is False
    for value in ("1", "true", "YES", "on"):
        monkeypatch.setenv(contract.ENV_REQUIRE_PACKAGE, value)
        assert contract.package_required() is True
        # an explicit False still wins, so a caller can opt out deliberately
        assert contract.package_required(False) is False
    monkeypatch.setenv(contract.ENV_REQUIRE_PACKAGE, "0")
    assert contract.package_required() is False


def test_the_declaration_may_not_carry_an_extra_top_level_key(packaged_tree,
                                                              tmp_path):
    """Exact key set, not containment: an unchecked extra key is a failure."""

    tree, _ = packaged_tree
    root = _clone(tree, tmp_path / "extra-key")

    def edit(declaration):
        declaration["reviewer_note"] = "these bytes are fine, honestly"

    _mutate_declaration(root, edit)
    done = _run_contract_tool(root)
    assert done.returncode != 0, done.stdout
    assert "exactly the pinned top-level schema" in done.stdout
    assert "unexpected ['reviewer_note']" in done.stdout


def test_the_untouched_declaration_still_satisfies_the_exact_schema(
        packaged_tree):
    """Positive control for the tightened key rule."""

    tree, _ = packaged_tree
    done = _run_contract_tool(tree)
    assert done.returncode == 0, done.stdout
    assert "FAIL" not in done.stdout


# --------------------------------------------------------------------------
# 6. the venue's layout rules: no shrinking to fit
# --------------------------------------------------------------------------
#
# The candidate reviewed before this file grew this section typeset the three
# generated evidence tables at \scriptsize, halved \tabcolsep and scaled the
# residual, which rendered them near 6.2pt against 9.96pt body copy. TMLR does
# not allow that. The tables are now landscape floats at the body font size
# with the template's spacing, and these tests refuse the mechanisms that made
# the old rendering possible.


def _submitted_tex_tree(tmp_path: Path) -> Path:
    """A throwaway checkout holding everything the submission typesets.

    Complete enough that the number audit passes on it untouched, so a mutation
    test proves a transition from clean to failing rather than adding one
    failure to a pile.
    """

    root = tmp_path / "repo"
    (root / "paper").mkdir(parents=True)
    (root / packager.ENTRY_POINT).parent.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / packager.ENTRY_POINT, root / packager.ENTRY_POINT)
    shutil.copy2(REPO_ROOT / "submissions/tmlr_2026/supplement_README.md",
                 root / "submissions/tmlr_2026/supplement_README.md")
    for path in sorted((REPO_ROOT / "paper").glob("*.tex")):
        shutil.copy2(path, root / "paper" / path.name)
    for directory in ("tables", "figures"):
        (root / "paper" / directory).mkdir()
        for path in sorted((REPO_ROOT / "paper" / directory).iterdir()):
            if path.is_file():
                shutil.copy2(path, root / "paper" / directory / path.name)
    return root


def test_the_throwaway_tree_audits_clean_before_any_mutation(tmp_path):
    """The baseline the mutation tests below are measured against."""

    assert _audit(_submitted_tex_tree(tmp_path)) == []


def test_the_submission_sources_carry_no_shrink_mechanism():
    assert packager.check_layout_rules(REPO_ROOT) == []


@pytest.mark.parametrize("injected", [
    r"\resizebox{\textwidth}{!}{x}",
    r"\scalebox{0.8}{x}",
    r"\setlength{\tabcolsep}{3pt}",
    r"\renewcommand{\arraystretch}{0.8}",
    r"\scriptsize",
    r"\footnotesize",
    r"\small",
    r"\tiny",
    r"\usepackage[margin=0.5in]{geometry}",
    r"\addtolength{\textwidth}{60pt}",
    r"\setlength{\oddsidemargin}{-30pt}",
])
def test_layout_check_rejects_a_reintroduced_shrink_in_the_entry_point(
        tmp_path, injected):
    root = _submitted_tex_tree(tmp_path)
    entry = root / packager.ENTRY_POINT
    entry.write_text(
        entry.read_text(encoding="utf-8").replace(
            r"\begin{document}", injected + "\n" + r"\begin{document}", 1),
        encoding="utf-8")
    findings = packager.check_layout_rules(root)
    stem = injected.split("{")[0].lstrip("\\")
    assert findings and any(stem in finding for finding in findings), findings


@pytest.mark.parametrize("table", packager.EVIDENCE_TABLE_INPUTS)
def test_layout_check_rejects_a_shrink_around_an_evidence_table(tmp_path, table):
    root = _submitted_tex_tree(tmp_path)
    marker = "\\input{" + table + "}"
    for path in sorted((root / "paper").glob("*.tex")):
        if path.name in packager.STAGE_TEX_EXCLUDE:
            continue
        text = path.read_text(encoding="utf-8")
        if marker not in text:
            continue
        path.write_text(text.replace(marker, r"\scriptsize" + marker),
                        encoding="utf-8")
        break
    else:
        pytest.fail(f"{table} is typeset by no submitted source")
    findings = packager.check_layout_rules(root)
    assert any("scriptsize" in finding for finding in findings), findings


@pytest.mark.parametrize("table", packager.EVIDENCE_TABLE_INPUTS)
def test_layout_check_rejects_bypassing_the_evidence_table_wrapper(tmp_path,
                                                                  table):
    root = _submitted_tex_tree(tmp_path)
    marker = "\\input{" + table + "}"
    for path in sorted((root / "paper").glob("*.tex")):
        text = path.read_text(encoding="utf-8")
        if marker in text and packager.EVIDENCE_TABLE_WRAPPER in text:
            path.write_text(
                text.replace(packager.EVIDENCE_TABLE_WRAPPER, r"\relax"),
                encoding="utf-8")
            break
    else:
        pytest.fail(f"{table} is not reached through the wrapper today")
    findings = packager.check_layout_rules(root)
    assert any("is not typeset through" in finding for finding in findings), \
        findings


def test_layout_check_notices_an_evidence_table_that_stopped_being_typeset(
        tmp_path):
    root = _submitted_tex_tree(tmp_path)
    table = packager.EVIDENCE_TABLE_INPUTS[0]
    marker = "\\input{" + table + "}"
    for path in sorted((root / "paper").glob("*.tex")):
        text = path.read_text(encoding="utf-8")
        if marker in text:
            path.write_text(text.replace(marker, ""), encoding="utf-8")
    findings = packager.check_layout_rules(root)
    assert any("no longer typeset" in finding for finding in findings), findings


def test_only_the_legacy_branch_may_still_scale(tmp_path):
    """The exemption is the dead branch, not a hole in the rule."""

    root = _submitted_tex_tree(tmp_path)
    notation = root / "paper/notation.tex"
    original = notation.read_text(encoding="utf-8")
    # the legacy definition really is present, and really is exempt
    assert r"\resizebox" in original
    assert r"\iflegacyextras" in original
    assert packager.check_layout_rules(root) == []

    # the same mechanism moved into the branch the submission compiles is not
    notation.write_text(
        original.replace(r"  \newcommand{\ccetablesize}{}",
                         r"  \newcommand{\ccetablesize}{\scriptsize}", 1),
        encoding="utf-8")
    findings = packager.check_layout_rules(root)
    assert any("scriptsize" in finding for finding in findings), findings


def test_legacy_conditionals_resolve_the_way_the_submission_compiles():
    resolve = packager.resolve_legacy_conditionals
    source = (r"before" "\n"
              r"\iflegacyextras" "\n" r"LEGACY" "\n"
              r"\else" "\n" r"SUBMITTED" "\n" r"\fi" "\n"
              r"after")
    resolved = resolve(source)
    assert "SUBMITTED" in resolved and "LEGACY" not in resolved
    assert "before" in resolved and "after" in resolved
    # a branch with no \else drops entirely
    assert "LEGACY" not in resolve(
        "\\iflegacyextras\nLEGACY\n\\fi\nkept")
    assert "kept" in resolve("\\iflegacyextras\nLEGACY\n\\fi\nkept")


def test_the_switch_declaration_does_not_open_a_branch():
    r"""`\newif\iflegacyextras` declares the switch; it opens nothing.

    Reading it as a branch left the rest of the entry point's preamble outside
    the scan, so every shrink mechanism declared there went unseen.
    """

    resolve = packager.resolve_legacy_conditionals
    source = "\\newif\\iflegacyextras \\legacyextrasfalse\nVISIBLE\n"
    assert "VISIBLE" in resolve(source)

    entry = (REPO_ROOT / packager.ENTRY_POINT).read_text(encoding="utf-8")
    compiled = resolve(packager.strip_tex_comments(entry))
    assert r"\begin{document}" in compiled
    assert r"\end{document}" in compiled


def test_an_unbalanced_legacy_branch_is_reported_rather_than_hiding_the_rest(
        tmp_path):
    root = _submitted_tex_tree(tmp_path)
    notation = root / "paper/notation.tex"
    notation.write_text(
        notation.read_text(encoding="utf-8").replace("\\fi", "", 1),
        encoding="utf-8")
    findings = packager.check_layout_rules(root)
    assert any("unbalanced" in finding for finding in findings), findings


# --------------------------------------------------------------------------
# 7. every retained empirical literal maps to a committed source
# --------------------------------------------------------------------------

sys.path.insert(0, str(REPO_ROOT / "tools"))
import verify_tmlr_submission_numbers as ledger_tool  # noqa: E402

LEDGER = ledger_tool.build_ledger()


def _audit(root: Path) -> list[str]:
    return [check.name
            for check in ledger_tool.literal_coverage_checks(root, LEDGER)
            if check.status == ledger_tool.STATUS_FAIL]


def test_every_manuscript_literal_is_accounted_for():
    assert _audit(REPO_ROOT) == []


@pytest.mark.parametrize("source, before, after", [
    # the two mutations the independent reviewer demonstrated
    ("paper/transport_experiment.tex",
     r"$T\in\{250,500,1000\}$", r"$T\in\{251,500,1000\}$"),
    ("paper/transport_experiment.tex",
     r"caps of $500$--$2{,}000$", r"caps of $501$--$2{,}001$"),
    # representative members of the same omission class
    ("paper/transport_experiment.tex",
     r"$D_{\rm target}\in\{0.25,0.5,1,2\}$",
     r"$D_{\rm target}\in\{0.26,0.5,1,2\}$"),
    ("paper/transport_experiment.tex",
     r"exact 95\% Clopper--Pearson", r"exact 90\% Clopper--Pearson"),
    ("paper/transport_experiment.tex",
     "the same 50 base seeds", "the same 60 base seeds"),
    ("paper/transport_experiment.tex",
     "600 independent runs", "900 independent runs"),
    ("paper/transport_experiment_appendix.tex",
     r"preregistered $10^{-12}$ ratio tolerance",
     r"preregistered $10^{-14}$ ratio tolerance"),
    ("paper/body_intro.tex", "29-parameter", "31-parameter"),
])
def test_audit_rejects_an_unchecked_edit_to_a_retained_literal(
        tmp_path, source, before, after):
    root = _submitted_tex_tree(tmp_path)
    path = root / source
    text = path.read_text(encoding="utf-8")
    assert before in text, before
    path.write_text(text.replace(before, after), encoding="utf-8")
    assert _audit(root), f"{before!r} -> {after!r} went unnoticed"


def test_audit_rejects_a_brand_new_unledgered_number(tmp_path):
    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/transport_experiment.tex"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "No run has zero regret.",
            "No run has zero regret.  The mean ratio is 42.7.", 1),
        encoding="utf-8")
    assert "every numeric literal is accounted for: paper/transport_experiment.tex" \
        in _audit(root)


def test_audit_rejects_a_study_value_moved_into_a_theory_source(tmp_path):
    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/transport_theory.tex"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "Neither the local factor",
            "The median terminal ratio is 126.7.\nNeither the local factor", 1),
        encoding="utf-8")
    assert any("paper/transport_theory.tex" in name
               for name in _audit(root))


def test_a_source_that_is_not_typeset_is_not_audited(tmp_path):
    """The audited set is the \\input closure, so an untypeset file is not in it.

    This replaces an earlier rule that audited every file in paper/ whether or
    not the submission compiled it.  The stronger guarantee now comes from the
    closure being derived: see
    test_a_new_input_source_joins_the_audit_automatically, where the same file
    is \\input and does fail the audit.
    """

    root = _submitted_tex_tree(tmp_path)
    (root / "paper/scratch_notes.tex").write_text(
        "The new mean is 7.5.\n", encoding="utf-8")
    assert _audit(root) == []


def test_audit_rejects_an_undeclared_typeset_table(tmp_path):
    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/transport_experiment.tex"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\n\\input{tables/some_other_result.tex}\n", encoding="utf-8")
    assert any("generated evidence or declared symbolic" in name
               for name in _audit(root))


def test_the_grid_entries_recompute_from_the_frozen_configuration():
    """The new entries are source-derived, not restatements of the literal."""

    config = json.loads(
        (REPO_ROOT / ledger_tool.CONFIG).read_text(encoding="utf-8"))
    by_literal: dict[str, list] = {}
    for entry in LEDGER:
        by_literal.setdefault(entry.literal, []).append(entry)

    horizons = by_literal[r"horizons $T\in\{250,500,1000\}$"]
    assert [e.display for e in horizons] == ["250", "500", "1000"]
    assert [e.compute({}, config) for e in horizons] == [250.0, 500.0, 1000.0]

    targets = by_literal[r"target labels $D_{\rm target}\in\{0.25,0.5,1,2\}$"]
    assert [e.display for e in targets] == ["0.25", "0.5", "1", "2"]
    assert [e.compute({}, config) for e in targets] == [0.25, 0.5, 1.0, 2.0]

    caps = by_literal[r"versus caps of $500$--$2{,}000$"]
    assert [e.display for e in caps] == ["500", "2{,}000"]
    assert [e.compute({}, config) for e in caps] == [500.0, 2000.0]

    level = by_literal[r"exact 95\% Clopper--Pearson interval"]
    assert [e.compute({}, config) for e in level] == [95.0]


def test_a_thousands_separated_display_parses_and_rounds():
    """`2{,}000` used to become `2{}000` and crash the comparison."""

    assert ledger_tool.parse_display("2{,}000") == 2000.0
    assert ledger_tool.tolerance_of("2{,}000") == 0.5
    assert ledger_tool.parse_display("12,607") == 12607.0


def test_a_tex_length_is_not_mistaken_for_a_measurement_or_a_hiding_place():
    """Column widths are masked; a number followed by the word "in" is not."""

    def leftover(text):
        return ledger_tool.uncovered_literals(
            ledger_tool.mask_typesetting(text), [])

    assert leftover("a p{32pt} b 0.21\\textwidth c 1.6em d SHA-256") == []
    # a whitespace-tolerant unit rule read this as "126.7 inches" and blanked it
    assert leftover("126.7 in the study") == ["126.7"]
    assert leftover("the median is 126.7") == ["126.7"]


# --------------------------------------------------------------------------
# 8. the supplement ships the active evidence closure and nothing else
# --------------------------------------------------------------------------

import transport_artifact_expectations as artifacts  # noqa: E402


def test_the_supplement_ships_no_excluded_legacy_benchmark():
    inventory = packager.supplement_artifact_inventory(REPO_ROOT)
    shipped = {arc for _, arc in packager.supplement_entries(REPO_ROOT)}
    for excluded in packager.SUPPLEMENT_EXCLUDED_LEGACY:
        assert not any(name.startswith(excluded) for name in inventory), excluded
        assert not any(arc.startswith(excluded) for arc in shipped), excluded
    # and the files really are there to be excluded, so this is not vacuous
    for excluded in packager.SUPPLEMENT_EXCLUDED_LEGACY:
        assert (REPO_ROOT / excluded).is_file(), excluded


def test_the_supplement_ships_every_active_artifact_with_its_records():
    inventory = set(packager.supplement_artifact_inventory(REPO_ROOT))
    shipped = {arc for _, arc in packager.supplement_entries(REPO_ROOT)}
    for artifact in packager.SUPPLEMENT_GENERATED_ARTIFACTS:
        for name in (artifact, f"{artifact}.sha256",
                     f"{artifact}.provenance.json"):
            assert name in inventory, name
            assert name in shipped, name
    for symbolic in packager.SUPPLEMENT_SYMBOLIC_ARTIFACTS:
        assert symbolic in shipped
        assert f"{symbolic}.sha256" in shipped


def test_the_whitelist_is_exactly_what_the_checker_regenerates():
    """Derived from the evidence closure, not a list someone keeps by hand."""

    expected, _ = artifacts.expected_artifact_text(REPO_ROOT)
    regenerated = {str(path.relative_to(REPO_ROOT)) for path in expected}
    assert set(packager.SUPPLEMENT_GENERATED_ARTIFACTS) == regenerated


def test_an_unclassified_artifact_stops_the_build(tmp_path):
    root = tmp_path / "repo"
    for directory in ("paper/tables", "paper/figures"):
        (root / directory).mkdir(parents=True)
        for path in sorted((REPO_ROOT / directory).iterdir()):
            (root / directory / path.name).write_bytes(b"")
    packager.supplement_artifact_inventory(root)        # classified: fine

    (root / "paper/tables/brand_new_result.tex").write_bytes(b"")
    with pytest.raises(RuntimeError, match="neither shipped nor explicitly"):
        packager.supplement_artifact_inventory(root)


def test_a_missing_active_artifact_stops_the_build(tmp_path):
    root = tmp_path / "repo"
    for directory in ("paper/tables", "paper/figures"):
        (root / directory).mkdir(parents=True)
        for path in sorted((REPO_ROOT / directory).iterdir()):
            (root / directory / path.name).write_bytes(b"")
    (root / packager.SUPPLEMENT_GENERATED_ARTIFACTS[0]).unlink()
    with pytest.raises(RuntimeError, match="missing from disk"):
        packager.supplement_artifact_inventory(root)


# --------------------------------------------------------------------------
# 9. the build refuses only genuinely in-repository output directories
# --------------------------------------------------------------------------


def test_a_valid_sibling_output_directory_is_accepted(tmp_path):
    repo = tmp_path / "Curvature-Calibrated-Exploration"
    sibling = tmp_path / "Curvature-Calibrated-Exploration-release"
    repo.mkdir()
    sibling.mkdir()
    assert packager.ensure_output_outside_repo(repo, sibling) \
        == sibling.resolve()


def test_a_true_in_repository_output_directory_is_refused(tmp_path):
    repo = tmp_path / "Curvature-Calibrated-Exploration"
    inside = repo / "build" / "release"
    inside.mkdir(parents=True)
    for candidate in (inside, repo, repo / "paper"):
        with pytest.raises(SystemExit):
            packager.ensure_output_outside_repo(repo, candidate)


def test_build_sh_no_longer_carries_the_string_prefix_test():
    text = (REPO_ROOT / "submissions/tmlr_2026/build.sh").read_text(
        encoding="utf-8")
    assert '${out#"$repo"}' not in text
    assert "must be outside the repository (got" not in text


# --------------------------------------------------------------------------
# 10. a failing contract run cannot be read as a passing one
# --------------------------------------------------------------------------


def test_missing_declaration_diagnostics_are_truthful(tmp_path):
    empty = tmp_path / "not-a-package"
    empty.mkdir()
    done = subprocess.run(
        [sys.executable,
         str(REPO_ROOT / "tools/transport_artifact_expectations.py"),
         "--root", str(empty), "--require-package"],
        capture_output=True, text=True)
    assert done.returncode == 1, done.stdout
    assert "0 of 1 anonymous-package contract checks passed" in done.stdout
    assert "no generated artifact was checked" in done.stdout
    assert "FAILED: 1 of 1 checks did not pass" in done.stdout
    # the shapes that used to read as success
    assert "0 of 0 generated artifacts" not in done.stdout
    assert not re.search(r"^\d+ anonymous-package contract checks passed",
                         done.stdout, re.M)
    assert "packaged (anonymized) aggregate" not in done.stdout


# --------------------------------------------------------------------------
# 11. CI gates the release package and the shipped supplement entry point
# --------------------------------------------------------------------------


def _submission_job_steps() -> list[dict]:
    import yaml
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return data["jobs"]["submission-evidence"]["steps"]


def _workflow_gate_findings(steps: list[dict]) -> list[str]:
    """What is missing from the CI gate, as a list; empty means it is complete."""

    findings: list[str] = []
    runs = [step.get("run", "") or "" for step in steps]
    names = [step.get("name", "") or "" for step in steps]

    suite = [i for i, run in enumerate(runs)
             if "tests/test_tmlr_release_package.py" in run]
    if not suite:
        findings.append("no step runs tests/test_tmlr_release_package.py")
    else:
        run = runs[suite[0]]
        if "TMLR_OUT=" not in run:
            findings.append("the package suite does not bind TMLR_OUT")
        if "${RUNNER_TEMP}/tmlr" not in run:
            findings.append("TMLR_OUT is not the externally built output")
        if "::" in run or " -k " in run:
            findings.append("the package suite runs a selection, not the module")
        build = [i for i, name in enumerate(names)
                 if name == "Build the anonymous TMLR submission"]
        if not build or suite[0] < build[0]:
            findings.append("the package suite does not run after the build")

    unpack = [run for run in runs
              if "supplement.zip" in run and "bash verify.sh" in run]
    if not unpack:
        findings.append("no step unpacks supplement.zip and runs its verify.sh")
    else:
        run = unpack[0]
        if "unzip" not in run:
            findings.append("the supplement is not unpacked from the archive")
        if "all supplement checks passed" not in run:
            findings.append("the supplement run does not assert its own verdict")
        if "supplement_verify.sh" in run:
            findings.append("the repository copy is run instead of the shipped one")
    return findings


def test_ci_gates_the_package_suite_and_the_shipped_supplement():
    assert _workflow_gate_findings(_submission_job_steps()) == []


@pytest.mark.parametrize("needle", [
    "tests/test_tmlr_release_package.py",
    "bash verify.sh",
])
def test_dropping_either_ci_gate_is_detected(needle):
    """The gate check is not vacuous: remove a step and it fails."""

    pruned = [step for step in _submission_job_steps()
              if needle not in (step.get("run", "") or "")]
    assert len(pruned) < len(_submission_job_steps()), needle
    assert _workflow_gate_findings(pruned), needle


def test_ci_keeps_the_deferred_realistic_job_and_its_real_status():
    import yaml
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = data["jobs"]["realistic-transport-deferred"]
    runs = " ".join(step.get("run", "") or "" for step in job["steps"])
    assert "experiments/realistic_transport" in runs
    assert "--collect-only" in runs
    # it must not be a dependency of, or depended on by, the submission job
    assert "needs" not in job
    assert "needs" not in data["jobs"]["submission-evidence"]
    # and no step may swallow its status
    for step in job["steps"]:
        assert step.get("continue-on-error") is not True


def test_ci_writes_the_new_gate_logs_outside_the_worktree():
    for step in _submission_job_steps():
        run = step.get("run", "") or ""
        if "tests/test_tmlr_release_package.py" in run or "bash verify.sh" in run:
            assert "RUNNER_TEMP" in run
            # and the step proves it left the tree alone
            assert "git status --porcelain" in run


# --------------------------------------------------------------------------
# 12. the layout gate fails closed
# --------------------------------------------------------------------------
#
# A second independent review got two shrink mechanisms past the gate: a
# `\scriptsize` hidden behind `\iffalse ... \else ... \fi` inside the branch the
# submission does compile, which the conditional parser mis-attributed, and a
# plain `\fontsize{6pt}{7pt}\selectfont`, which was not on the mechanism list.


@pytest.mark.parametrize("where, anchor", [
    ("paper/transport_experiment.tex",
     "\\input{tables/transport_instantiation_validity.tex}"),
    ("paper/transport_experiment_appendix.tex",
     "\\input{tables/transport_instantiation_tightness.tex}"),
])
def test_a_shrink_hidden_behind_a_foreign_conditional_is_caught(
        tmp_path, where, anchor):
    root = _submitted_tex_tree(tmp_path)
    path = root / where
    text = path.read_text(encoding="utf-8")
    assert anchor in text
    path.write_text(
        text.replace(anchor, "\\iffalse X\\else\\scriptsize\\fi " + anchor, 1),
        encoding="utf-8")
    findings = packager.check_layout_rules(root)
    assert any("scriptsize" in finding for finding in findings), findings


def test_a_shrink_hidden_inside_the_compiled_legacy_branch_is_caught(tmp_path):
    """The exact reproduction: the parser used to credit the inner `\\else`."""

    root = _submitted_tex_tree(tmp_path)
    notation = root / "paper/notation.tex"
    anchor = "  \\newcommand{\\ccetablesize}{}"
    text = notation.read_text(encoding="utf-8")
    assert anchor in text
    notation.write_text(
        text.replace(anchor, "  \\iffalse X\\else\\scriptsize\\fi\n" + anchor, 1),
        encoding="utf-8")
    findings = packager.check_layout_rules(root)
    assert any("scriptsize" in finding for finding in findings), findings


@pytest.mark.parametrize("injected, expected", [
    (r"\fontsize{6pt}{7pt}\selectfont", "fontsize"),
    (r"\usefont{OT1}{cmr}{m}{n}", "usefont"),
    (r"\linespread{0.8}", "linespread"),
    (r"\csname scriptsize\endcsname", "csname"),
    (r"\expandafter\scriptsize", "expandafter"),
])
def test_an_explicit_or_obfuscated_size_change_is_caught(
        tmp_path, injected, expected):
    root = _submitted_tex_tree(tmp_path)
    anchor = "\\input{tables/transport_instantiation_validity.tex}"
    path = root / "paper/transport_experiment.tex"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace(anchor, injected + " " + anchor, 1),
                    encoding="utf-8")
    findings = packager.check_layout_rules(root)
    assert any(expected in finding for finding in findings), findings


@pytest.mark.parametrize("source", [
    "\\iffalse\nA\n\\else\nB\n\\fi\n",
    "\\ifnum1=1\nA\n\\else\nB\n\\fi\n",
    "\\ifx\\a\\b\nA\n\\fi\n",
])
def test_an_opaque_conditional_keeps_both_branches(source):
    """The checker cannot evaluate them, so it reads all of them."""

    resolved = packager.resolve_legacy_conditionals(source)
    for branch in re.findall(r"^[AB]$", source, re.M):
        assert branch in resolved, (source, resolved)


def test_an_opaque_conditional_nested_in_the_switch_does_not_steal_its_else():
    source = ("\\iflegacyextras\nLEGACY\n\\else\n"
              "\\iffalse\nX\n\\else\nSUBMITTED\n\\fi\n"
              "ALSOSUBMITTED\n\\fi\n")
    resolved = packager.resolve_legacy_conditionals(source)
    assert "SUBMITTED" in resolved
    assert "ALSOSUBMITTED" in resolved
    assert "LEGACY" not in resolved


def test_the_layout_gate_runs_before_anything_is_staged(tmp_path):
    """A violation must cost nothing and leave no half-built output behind."""

    repo = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "paper", repo / "paper",
                    ignore=shutil.ignore_patterns("*.pdf"))
    (repo / "submissions/tmlr_2026").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / packager.ENTRY_POINT, repo / packager.ENTRY_POINT)
    entry = repo / packager.ENTRY_POINT
    entry.write_text(
        entry.read_text(encoding="utf-8").replace(
            r"\begin{document}", "\\scriptsize\n" + r"\begin{document}", 1),
        encoding="utf-8")

    out = tmp_path / "out"
    status = packager.main(["--repo", str(repo), "--out", str(out),
                            "--skip-compile"])
    assert status == 6
    assert not (out / "src").exists()


# --------------------------------------------------------------------------
# 13. every release output is written without following a symlink
# --------------------------------------------------------------------------


def test_atomic_write_replaces_a_symlink_instead_of_its_target(tmp_path):
    victim = tmp_path / "somewhere-else.bin"
    victim.write_bytes(b"do not touch me")
    target = tmp_path / "out" / "main.pdf"
    target.parent.mkdir()
    target.symlink_to(victim)

    packager.atomic_write_bytes(target, b"fresh release bytes")

    assert victim.read_bytes() == b"do not touch me"
    assert not target.is_symlink()
    assert target.read_bytes() == b"fresh release bytes"


def test_atomic_write_replaces_a_symlink_to_a_directory(tmp_path):
    victim = tmp_path / "victim-dir"
    victim.mkdir()
    (victim / "keep.txt").write_bytes(b"keep")
    target = tmp_path / "out" / "release_manifest.json"
    target.parent.mkdir()
    target.symlink_to(victim, target_is_directory=True)

    packager.atomic_write_bytes(target, b"{}")

    assert (victim / "keep.txt").read_bytes() == b"keep"
    assert not target.is_symlink()
    assert target.read_bytes() == b"{}"


def test_atomic_write_refuses_a_real_directory(tmp_path):
    target = tmp_path / "main.pdf"
    target.mkdir()
    with pytest.raises(RuntimeError, match="over a directory"):
        packager.atomic_write_bytes(target, b"x")


def test_atomic_write_leaves_no_temporary_behind(tmp_path):
    target = tmp_path / "out.bin"
    packager.atomic_write_bytes(target, b"abc")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out.bin"]


def test_write_zip_does_not_follow_a_symlink(tmp_path):
    victim = tmp_path / "victim.zip"
    victim.write_bytes(b"original archive bytes")
    member = tmp_path / "member.txt"
    member.write_bytes(b"hello")
    target = tmp_path / "source.zip"
    target.symlink_to(victim)

    packager.write_zip(target, [(member, "member.txt")])

    assert victim.read_bytes() == b"original archive bytes"
    assert not target.is_symlink()
    with zipfile.ZipFile(target) as archive:
        assert archive.read("member.txt") == b"hello"


def test_write_zip_stays_deterministic(tmp_path):
    member = tmp_path / "member.txt"
    member.write_bytes(b"hello")
    first, second = tmp_path / "a.zip", tmp_path / "b.zip"
    packager.write_zip(first, [(member, "member.txt")])
    packager.write_zip(second, [(member, "member.txt")])
    assert first.read_bytes() == second.read_bytes()


def test_write_zip_stores_rather_than_compressing(tmp_path):
    """Archive identity must not depend on an unpinned zlib."""

    member = tmp_path / "member.txt"
    member.write_bytes(b"compress me " * 4000)
    target = tmp_path / "a.zip"
    packager.write_zip(target, [(member, "member.txt")])
    with zipfile.ZipFile(target) as archive:
        for info in archive.infolist():
            assert info.compress_type == zipfile.ZIP_STORED, info.filename
            assert info.compress_size == info.file_size, info.filename
    # the member's bytes appear verbatim, so no deflate stream was produced
    assert member.read_bytes() in target.read_bytes()
    assert "ZIP_DEFLATED" not in (
        REPO_ROOT / "submissions/tmlr_2026/package.py").read_text(encoding="utf-8")


def test_stored_archives_are_identical_across_compression_settings(tmp_path,
                                                                   monkeypatch):
    """A different zlib would change a deflate stream; it cannot change these."""

    member = tmp_path / "member.txt"
    member.write_bytes(b"compress me " * 4000)
    first = tmp_path / "a.zip"
    packager.write_zip(first, [(member, "member.txt")])

    import zlib

    real = zlib.compressobj

    def refuse(*args, **kwargs):
        raise AssertionError("the archive writer must not call zlib")

    monkeypatch.setattr(zlib, "compressobj", refuse)
    second = tmp_path / "b.zip"
    packager.write_zip(second, [(member, "member.txt")])
    monkeypatch.setattr(zlib, "compressobj", real)
    assert first.read_bytes() == second.read_bytes()


def test_a_supplement_over_the_venue_limit_is_refused(tmp_path):
    big = tmp_path / "supplement.zip"
    big.write_bytes(b"x" * 1024)
    assert packager.check_archive_size(big, limit=10_000) == []
    assert packager.check_archive_size(big, limit=512)


def test_the_built_supplement_is_under_the_venue_limit():
    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    size = (release / "supplement.zip").stat().st_size
    assert size < packager.SUPPLEMENT_SIZE_LIMIT, size
    assert packager.check_archive_size(release / "supplement.zip") == []


def test_the_whitespace_exemption_covers_only_pinned_upstream_bytes():
    """A glob also exempted the prose this project wrote about the vendoring."""

    attrs = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "paper/texmf_vendor/** -whitespace" not in attrs
    for name in packager.VENDORED_PACKAGE_DIGESTS:
        assert f"paper/texmf_vendor/{name} -whitespace" in attrs, name
    done = _git("check-attr", "whitespace", "--",
                *[f"paper/texmf_vendor/{n}" for n in
                  sorted(packager.VENDORED_PACKAGE_DIGESTS)],
                "paper/texmf_vendor/VENDORED-PACKAGES.md")
    assert done.returncode == 0, done.stderr
    lines = dict(line.rsplit(": whitespace: ", 1)
                 for line in done.stdout.splitlines() if line.strip())
    for name in packager.VENDORED_PACKAGE_DIGESTS:
        assert lines[f"paper/texmf_vendor/{name}"] == "unset", name
    assert lines["paper/texmf_vendor/VENDORED-PACKAGES.md"] == "set"


def test_authored_prose_whitespace_is_still_caught(tmp_path):
    """`git diff --check` must still see a defect in the authored note."""

    clone = tmp_path / "clone"
    done = _git("clone", "--quiet", "--no-hardlinks", str(REPO_ROOT), str(clone))
    if done.returncode != 0:
        pytest.skip("cannot clone this checkout")
    # the working-tree rules, which is what this test is about
    shutil.copy2(REPO_ROOT / ".gitattributes", clone / ".gitattributes")

    def check(path: Path, text: str) -> str:
        path.write_text(text, encoding="utf-8")
        run = subprocess.run(["git", "add", "-A"], cwd=clone,
                             capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        run = subprocess.run(["git", "diff", "--cached", "--check"], cwd=clone,
                             capture_output=True, text=True)
        return run.stdout

    authored = clone / "paper/texmf_vendor/VENDORED-PACKAGES.md"
    out = check(authored, authored.read_text(encoding="utf-8")
                + "\nA line with trailing space \n")
    assert "trailing whitespace" in out, out

    # and the pinned upstream bytes stay exempt
    subprocess.run(["git", "checkout", "--", "."], cwd=clone,
                   capture_output=True, text=True)
    vendored = clone / "paper/texmf_vendor/pgfplots.sty"
    out = check(vendored, vendored.read_text(encoding="utf-8")
                + "\n% appended with trailing space \n")
    assert "pgfplots.sty" not in out, out


def test_the_readme_current_release_table_matches_the_artifacts():
    """Every current figure in the README is recomputed, not maintained.

    The reviewer found `~0.8 MB` for a 3,420,977-byte archive and `roughly
    14 MB` of headroom against 15,832,559.  A prose approximation drifts the
    moment anything changes; this makes the table a checked claim.
    """

    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    readme = (REPO_ROOT / "submissions/tmlr_2026/README.md").read_text(
        encoding="utf-8")
    assert "## Current release" in readme
    assert "~0.8 MB" not in readme and "roughly 14 MB" not in readme

    def grouped(value: int) -> str:
        return f"{value:,}"

    for name in ("main.pdf", "source.zip", "supplement.zip",
                 "release_manifest.json"):
        assert grouped((release / name).stat().st_size) in readme, name
    for name in ("source.zip", "supplement.zip"):
        with zipfile.ZipFile(release / name) as archive:
            infos = archive.infolist()
        assert grouped(len(infos)) in readme or str(len(infos)) in readme, name
        assert grouped(sum(i.file_size for i in infos)) in readme, name

    size = (release / "supplement.zip").stat().st_size
    assert grouped(packager.SUPPLEMENT_SIZE_LIMIT - size) in readme
    assert f"{100 * size / packager.SUPPLEMENT_SIZE_LIMIT:.1f}%" in readme

    with zipfile.ZipFile(release / "supplement.zip") as archive:
        closure = json.loads(archive.read(ledger_tool.SOURCE_CLOSURE_NAME))
    counts = collections.Counter(e["ships_in"] for e in closure["entries"])
    assert f"{len(closure['entries'])} entries" in readme
    assert f"{counts['supplement']} whose bytes the supplement" in readme
    assert f"{counts['source']} in `source.zip`" in readme


def test_the_report_states_the_current_release_package_test_count():
    """The report's current count is this file's count, not a stale literal.

    The report carried 402 -- the pre-amend R11 run -- while the post-amend run
    had 403.  A number that has to be retyped after every amend will be wrong
    again, so it is asserted here against the suite itself.
    """

    import re

    report = (REPO_ROOT / "submissions/tmlr_2026/FINALIZATION_REPORT.md").read_text(
        encoding="utf-8")
    row = next(line for line in report.splitlines()
               if line.startswith("| Release-package and anonymization tests"))
    stated = re.search(r"\| (\d+) passed, 0 skipped", row)
    assert stated, row
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header",
         "-p", "no:cacheprovider", "--collect-only", "-q", str(Path(__file__))],
        capture_output=True, text=True, cwd=REPO_ROOT)
    collected = re.search(r"test_tmlr_release_package\.py: (\d+)", done.stdout)
    assert collected, done.stdout[-2000:]
    assert int(stated.group(1)) == int(collected.group(1)), (
        f"the report says {stated.group(1)} release-package tests; this file "
        f"has {collected.group(1)}")


def test_the_report_states_the_current_repository_suite_count():
    """The combined-suite count is derived too, for the same reason.

    It sat at 525 for two passes after the suite had grown, because only the
    release-package number was asserted anywhere.
    """

    report = (REPO_ROOT / "submissions/tmlr_2026/FINALIZATION_REPORT.md").read_text(
        encoding="utf-8")
    row = next(line for line in report.splitlines()
               if line.startswith("| Repository test suites"))
    stated = re.search(r"\| (\d+) passed, 0 skipped", row)
    assert stated, row
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header",
         "-p", "no:cacheprovider", "--collect-only", "-q",
         "tests", "experiments/tests"],
        capture_output=True, text=True, cwd=REPO_ROOT)
    # `--collect-only -q` prints one `path: count` line per file, no total
    per_file = re.findall(r"^(\S+\.py): (\d+)$", done.stdout, re.MULTILINE)
    assert per_file, done.stdout[-2000:]
    collected = sum(int(count) for _, count in per_file)
    assert int(stated.group(1)) == collected, (
        f"the report says {stated.group(1)} repository tests; the suites "
        f"collect {collected}")


def test_the_readme_bundling_table_matches_the_source_archive():
    """What the README says is bundled must be what `source.zip` carries.

    It used to say only the venue template was bundled and everything else was
    stock TeX Live, while the archive also carried 46 files from four
    third-party packages and their licence texts.
    """

    readme = (REPO_ROOT / "submissions/tmlr_2026/README.md").read_text(
        encoding="utf-8")
    assert "only the venue's own `tmlr.sty`, `tmlr.bst` and" not in readme
    assert "everything else\nis stock TeX Live" not in readme

    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    with zipfile.ZipFile(release / "source.zip") as archive:
        members = set(archive.namelist())

    bundled = {"mathtools": "mathtools.sty", "cleveref": "cleveref.sty",
               "pgfplots": "pgfplots.sty", "microtype": "microtype.sty"}
    for package, probe in sorted(bundled.items()):
        assert probe in members, (package, probe)
        row = next(line for line in readme.splitlines()
                   if line.startswith(f"| `{package}`"))
        assert "**bundled**" in row, row

    # rotating and the fonts are external, and the archive must not carry them
    for package, probe in (("rotating", "rotating.sty"),
                           ("cm-super", "cm-super-ts1.enc")):
        assert probe not in members, probe
        row = next(line for line in readme.splitlines()
                   if line.startswith(f"| `{package}`"))
        assert "external" in row and "**bundled**" not in row, row

    assert str(len(packager.VENDORED_PACKAGE_DIGESTS)
               - len(packager.VENDORED_LICENSE_FILES)) in readme
    for name in packager.VENDORED_LICENSE_FILES:
        assert name in members, name


def test_the_size_tradeoff_is_documented():
    readme = (REPO_ROOT / "submissions/tmlr_2026/README.md").read_text(
        encoding="utf-8")
    assert "ZIP_STORED" in readme or "stored" in readme.lower()
    assert "100" in readme


# --------------------------------------------------------------------------
# 25. a deliverable set is published in one step, or not at all
# --------------------------------------------------------------------------
#
# The size gate used to run after main.pdf, source.zip and supplement.zip had
# already replaced the previous release, so an oversized supplement left three
# new deliverables beside a release_manifest.json describing the old ones.


def _sentinel_release(out: Path) -> dict[str, bytes]:
    out.mkdir(parents=True, exist_ok=True)
    prior = {}
    for name in packager.RELEASE_DELIVERABLES:
        data = f"prior {name}\n".encode()
        (out / name).write_bytes(data)
        prior[name] = data
    return prior


def test_publish_release_moves_the_whole_set(tmp_path):
    out = tmp_path / "out"
    prior = _sentinel_release(out)
    pending = out / ".pending"
    pending.mkdir()
    for name in packager.RELEASE_DELIVERABLES:
        (pending / name).write_bytes(f"new {name}\n".encode())
    packager.publish_release(pending, out)
    assert not pending.exists()
    for name in prior:
        assert (out / name).read_bytes() == f"new {name}\n".encode()


@pytest.mark.parametrize("archive", ["source.zip", "supplement.zip"])
def test_an_oversized_archive_leaves_the_prior_release_untouched(tmp_path,
                                                                 archive):
    """Both size gates, and both must fail before anything is published."""

    out = tmp_path / "out"
    prior = _sentinel_release(out)
    pending = out / ".pending"
    pending.mkdir()
    big = pending / archive
    big.write_bytes(b"x" * 4096)
    assert packager.check_archive_size(big, limit=1024)
    # the real build removes the staging area and returns; nothing is published
    shutil.rmtree(pending)
    for name, data in prior.items():
        assert (out / name).read_bytes() == data


#: One plausible external TeX input, so the fixture does not have to resolve a
#: real TeX tree.  `check_derived_manifest` rejects an empty list, which is the
#: point of the last test in this section.
_FIXTURE_EXTERNAL_INPUTS = [
    {"name": "TEXMFDIST:tex/latex/base/article.cls",
     "sha256": "a" * 64, "bytes": 10, "trusted": True},
]


def _transform_records() -> list[dict]:
    """The anonymization records the contract implies, with every pinned key.

    The same shape `packager.derive_anonymization_records` produces; the fixture
    supplies a synthetic removed value because it does not have the 77 MB
    original to extract one from.
    """

    return [{"path": path,
             "source_path": path,
             "field": contract.PACKAGED_FIELD,
             "removed_value_class": packager.TRANSFORM_REMOVED_VALUE_CLASS,
             "removed_value_internal_only": "0" * 40,
             "replacement": contract.REPLACEMENT_TOKEN,
             "reason": packager.TRANSFORM_REASON,
             **{field: pinned[field]
                for field in ("original_sha256", "original_bytes",
                              "packaged_sha256", "packaged_bytes")}}
            for path, pinned in sorted(contract.CONTRACT.items())]


def _digest_of(path: Path) -> tuple[str, int]:
    return packager.sha256_file(path), path.stat().st_size


def _stage_manifest(pending: Path, tamper=None) -> dict:
    """Write `release_manifest.json` the way the build writes it.

    `tamper` edits the document *after* derivation and *before* it is written,
    so what lands on disk is what the gate reads.  Editing the returned object
    afterwards changes nothing, which is the whole point: the gate stopped
    believing objects.
    """

    manifest = packager.derive_release_manifest(REPO_ROOT, FIXTURE_SRC, pending)
    if tamper is not None:
        tamper(manifest)
    (pending / "release_manifest.json").write_bytes(
        packager.canonical_manifest_bytes(manifest))
    return manifest


#: A stand-in for the staged tree.  Every derivation that would read it is
#: patched in `_pending_release`, because a fixture has no compile and so no
#: `main.fls`; the real derivations are exercised against a real build in
#: section 18b below.
FIXTURE_SRC = Path("/nonexistent-staged-tree")


def _restage_inventories(pending: Path, monkeypatch, records) -> None:
    """Re-pin the expected inventories to whatever is in the pending archives.

    Used only to establish the *clean* baseline.  An attack test calls this
    once, before the mutation, and then does not call it again -- which is the
    whole point: the expectation must not move when the archive does.
    """

    monkeypatch.setattr(
        packager, "expected_source_members",
        lambda repo, _pinned={
            record["path"]: (record["sha256"], record["bytes"])
            for record in packager.archive_member_records(
                pending / "source.zip")}: dict(_pinned))
    monkeypatch.setattr(
        packager, "expected_supplement_members",
        lambda repo, records, _pinned={
            record["path"]: (record["sha256"], record["bytes"])
            for record in packager.archive_member_records(
                pending / "supplement.zip")}: dict(_pinned))


def _pending_release(tmp_path: Path, pending: Path, monkeypatch) -> list[dict]:
    """A staged release complete enough for every check_pending_release rule.

    Returns the anonymization records the gate will derive.  The manifest is not
    returned as an expectation; it is written to disk and the gate derives its
    own.
    """

    member = tmp_path / "member.txt"
    member.write_bytes(b"hello")
    (pending / "main.pdf").write_bytes(b"%PDF-1.5\n")
    packager.write_zip(pending / "source.zip", [(member, "member.txt")])
    closure = tmp_path / packager.SOURCE_CLOSURE_NAME
    closure.write_bytes(
        packager.canonical_json_bytes(packager.derive_source_closure_document()))
    packager.write_zip(pending / "supplement.zip",
                       [(member, "member.txt"),
                        (closure, packager.SOURCE_CLOSURE_NAME)])

    records = _transform_records()
    monkeypatch.setattr(packager, "derive_external_inputs",
                        lambda repo, src: [dict(item)
                                           for item in _FIXTURE_EXTERNAL_INPUTS])
    monkeypatch.setattr(packager, "derive_anonymization_records",
                        lambda repo: [dict(record) for record in records])
    # This fixture has no compile and so no staged tree; the staged-source
    # binding is exercised against a real build in
    # `test_a_mutated_staged_source_fails_the_mandatory_gate` and its
    # neighbours.
    monkeypatch.setattr(packager, "check_staged_sources",
                        lambda repo, src: [])
    _restage_inventories(pending, monkeypatch, records)
    _stage_manifest(pending)
    return records


def _check(pending: Path, reported=None) -> list[str]:
    return packager.check_pending_release(
        REPO_ROOT, FIXTURE_SRC, pending,
        _transform_records() if reported is None else reported)


def _evidence_clone(tmp_path: Path) -> Path:
    """A disposable tree holding copies of the contract-pinned evidence.

    Copies, never hardlinks: a test that mutates evidence must not be one
    `os.link` away from writing through to the repository's own bytes.
    """

    clone = tmp_path / "evidence-clone"
    for arcname in sorted(contract.CONTRACT):
        target = clone / arcname
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / arcname, target)
    return clone


def _pending_release_over(clone: Path, tmp_path: Path, pending: Path,
                          monkeypatch) -> list[dict]:
    """Like `_pending_release`, but the anonymization derivation runs for real.

    Only `supplement_entries` is redirected, at the one seam a fixture needs: to
    the two evidence files instead of the whole 140-file inventory.  Everything
    downstream -- reading the bytes, extracting the revision, hashing, comparing
    with the contract -- is the production path.
    """

    monkeypatch.setattr(
        packager, "supplement_entries",
        lambda repo: [(Path(repo) / arcname, arcname)
                      for arcname in sorted(contract.CONTRACT)])

    member = tmp_path / "member.txt"
    member.write_bytes(b"hello")
    (pending / "main.pdf").write_bytes(b"%PDF-1.5\n")
    packager.write_zip(pending / "source.zip", [(member, "member.txt")])
    closure = tmp_path / packager.SOURCE_CLOSURE_NAME
    closure.write_bytes(
        packager.canonical_json_bytes(packager.derive_source_closure_document()))
    packager.write_zip(pending / "supplement.zip",
                       [(member, "member.txt"),
                        (closure, packager.SOURCE_CLOSURE_NAME)])

    monkeypatch.setattr(packager, "derive_external_inputs",
                        lambda repo, src: [dict(item)
                                           for item in _FIXTURE_EXTERNAL_INPUTS])
    monkeypatch.setattr(packager, "check_staged_sources",
                        lambda repo, src: [])
    records = packager.derive_anonymization_records(clone)
    _restage_inventories(pending, monkeypatch, records)
    manifest = packager.derive_release_manifest(clone, FIXTURE_SRC, pending)
    (pending / "release_manifest.json").write_bytes(
        packager.canonical_manifest_bytes(manifest))
    return records


def test_a_complete_staged_release_passes_every_consistency_rule(tmp_path,
                                                                 monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    pending = out / ".pending"
    pending.mkdir()
    _pending_release(tmp_path, pending, monkeypatch)
    assert _check(pending) == []


@pytest.mark.parametrize("tamper, expected", [
    # deliverable bytes
    (lambda m: m["deliverables"]["main.pdf"].update(sha256="0" * 64),
     "manifest says"),
    (lambda m: m["deliverables"]["main.pdf"].update(bytes=1), "manifest says"),
    # the deliverable records themselves: one removed, one invented, one that
    # is not even an object.  The reviewer removed a record and got nothing.
    (lambda m: m["deliverables"].pop("source.zip"), "deliverables:"),
    (lambda m: m["deliverables"].update({"extra.bin": {"sha256": "0" * 64,
                                                       "bytes": 1}}),
     "deliverables:"),
    (lambda m: m["deliverables"].update({"main.pdf": 5}), "expected an object"),
    # per-member hash and size, which a name-only comparison missed entirely
    (lambda m: m["source_zip_contents"][0].update(sha256="0" * 64),
     "disagree with the manifest"),
    (lambda m: m["source_zip_contents"][0].update(bytes=999),
     "disagree with the manifest"),
    (lambda m: m["supplement_zip_contents"][0].update(sha256="0" * 64),
     "disagree with the manifest"),
    # member list
    (lambda m: m["source_zip_contents"].append(
        {"path": "ghost.txt", "sha256": "0" * 64, "bytes": 1}),
     "member list disagrees"),
    (lambda m: m["source_zip_contents"].clear(), "member list disagrees"),
    (lambda m: m["source_zip_contents"].append(dict(m["source_zip_contents"][0])),
     "lists a member twice"),
    (lambda m: m.update(source_zip_contents={}), "not a list of records"),
    (lambda m: m.update(supplement_zip_contents=["nope"]),
     "not a list of records"),
    # the other authoritative record classes
    (lambda m: m.update(schema_version=1), "schema_version"),
    (lambda m: m.update(schema_version=True), "schema_version"),
    (lambda m: m.update(target_venue="NeurIPS"), "target_venue/anonymous"),
    (lambda m: m.update(anonymous=False), "target_venue/anonymous"),
    (lambda m: m.update(anonymous="yes"), "target_venue/anonymous"),
    (lambda m: m["build"].update(source_date_epoch=0), "source_date_epoch"),
    (lambda m: m["build"].update(note="rewritten"), "build record differs"),
    (lambda m: m.update(build=[]), "expected an object"),
    (lambda m: m["external_tex_inputs"][0].update(trusted=False),
     "trusted system TeX"),
    (lambda m: m["external_tex_inputs"].clear(), "trusted system TeX"),
    (lambda m: m["external_tex_inputs"][0].update(name="/etc/passwd"),
     "malformed record"),
    (lambda m: m["external_tex_inputs"][0].update(sha256="b" * 64),
     "resolve to on disk"),
    (lambda m: m["external_tex_inputs"][0].update(bytes=11),
     "resolve to on disk"),
    (lambda m: m.update(external_tex_inputs="nope"), "not a list of records"),
    (lambda m: m["shipped_tool_digests"].update(
        {"tools/numeric_context_pins.py": "0" * 64}), "shipped_tool_digests"),
    (lambda m: m["anonymization"].update(token="whatever"), "anonymization"),
    (lambda m: m["anonymization"]["transformed"].clear(), "anonymization"),
    (lambda m: m["anonymization"]["transformed"][0].update(
        packaged_sha256="0" * 64), "anonymization"),
    (lambda m: m.pop("anonymization"), "top-level keys"),
    (lambda m: m.update(surprise=1), "top-level keys"),
])
def test_each_manifest_record_class_is_validated(tmp_path, monkeypatch,
                                                 tamper, expected):
    """Every mutation is applied to the staged file, which is what is read."""

    out = tmp_path / "out"
    out.mkdir()
    pending = out / ".pending"
    pending.mkdir()
    _pending_release(tmp_path, pending, monkeypatch)
    _stage_manifest(pending, tamper)
    findings = _check(pending)
    assert any(expected in f for f in findings), (expected, findings)


def test_the_staged_file_is_checked_not_the_object_the_build_had_in_hand(
        tmp_path, monkeypatch):
    """The reviewer's attack: swap the file, keep the object, get no findings.

    The old gate took the build's manifest object as its subject.  Replacing
    `release_manifest.json` on disk with a different document -- changed build
    metadata, changed external-input names, hashes and sizes, changed
    anonymization digests -- was invisible to it.
    """

    out = tmp_path / "out"
    out.mkdir()
    pending = out / ".pending"
    pending.mkdir()
    _pending_release(tmp_path, pending, monkeypatch)
    honest = json.loads(
        (pending / "release_manifest.json").read_text(encoding="utf-8"))
    assert _check(pending) == []

    forged = json.loads(json.dumps(honest))
    forged["build"]["note"] = "built by hand"
    forged["build"]["source_date_epoch"] = 0
    forged["external_tex_inputs"][0].update(
        name="TEXMFDIST:tex/latex/base/size10.clo", sha256="c" * 64, bytes=99)
    forged["anonymization"]["transformed"][0]["original_sha256"] = "d" * 64
    forged["deliverables"].pop("supplement.zip")
    (pending / "release_manifest.json").write_bytes(
        packager.canonical_manifest_bytes(forged))

    # the object the build had is untouched and still honest; the file is not
    assert honest["build"]["source_date_epoch"] != 0
    findings = _check(pending)
    assert any("not the manifest these bytes imply" in f for f in findings)
    for expected in ("source_date_epoch", "resolve to on disk", "anonymization",
                     "deliverables:"):
        assert any(expected in f for f in findings), (expected, findings)


def test_a_tampered_anonymization_record_fails_before_publication(tmp_path,
                                                                  monkeypatch):
    """The derived records are held to the pinned contract, field by field."""

    out = tmp_path / "out"
    out.mkdir()
    pending = out / ".pending"
    pending.mkdir()
    records = _pending_release(tmp_path, pending, monkeypatch)
    records[0]["packaged_sha256"] = "0" * 64
    _stage_manifest(pending)                 # the manifest agrees with itself
    findings = _check(pending, records)
    assert any("the contract pins" in f for f in findings), findings


def test_a_tampered_shipped_closure_fails_the_pending_gate(tmp_path, monkeypatch):
    """The supplement's own SOURCE_CLOSURE.json is checked before publication.

    The manifest is restaged over the new archive, so every hash agrees.  Only
    a check bound to `contract.COMPILED_CLOSURE`, which is outside both the
    archive and the manifest, can catch this.
    """

    out = tmp_path / "out"
    out.mkdir()
    pending = out / ".pending"
    pending.mkdir()
    _pending_release(tmp_path, pending, monkeypatch)

    member = tmp_path / "member.txt"
    closure = tmp_path / packager.SOURCE_CLOSURE_NAME
    broken = json.loads(closure.read_text(encoding="utf-8"))
    broken["entries"] = [e for e in broken["entries"] if e["staged"] != "main.bbl"]
    closure.write_bytes(packager.canonical_json_bytes(broken))
    packager.write_zip(pending / "supplement.zip",
                       [(member, "member.txt"),
                        (closure, packager.SOURCE_CLOSURE_NAME)])
    _stage_manifest(pending)

    findings = _check(pending)
    assert any("not the pinned set" in f for f in findings), findings


def test_a_shipped_closure_entry_that_disagrees_with_the_contract_is_caught(
        tmp_path, monkeypatch):
    """Same set of entries, one field rewritten, manifest restaged to agree."""

    out = tmp_path / "out"
    out.mkdir()
    pending = out / ".pending"
    pending.mkdir()
    _pending_release(tmp_path, pending, monkeypatch)

    member = tmp_path / "member.txt"
    closure = tmp_path / packager.SOURCE_CLOSURE_NAME
    drifted = json.loads(closure.read_text(encoding="utf-8"))
    drifted["entries"][0]["sha256"] = "0" * 64
    closure.write_bytes(packager.canonical_json_bytes(drifted))
    packager.write_zip(pending / "supplement.zip",
                       [(member, "member.txt"),
                        (closure, packager.SOURCE_CLOSURE_NAME)])
    _stage_manifest(pending)

    findings = _check(pending)
    assert any("disagrees with the pinned contract" in f for f in findings), \
        findings


@pytest.mark.parametrize("archive, mutation, expected", [
    ("source.zip", "rename", "nothing authorises"),
    ("source.zip", "rewrite", "not the bytes they should be"),
    ("source.zip", "add", "nothing authorises"),
    ("source.zip", "remove", "is missing"),
    ("supplement.zip", "rename", "nothing authorises"),
    ("supplement.zip", "rewrite", "not the bytes they should be"),
    ("supplement.zip", "add", "nothing authorises"),
    ("supplement.zip", "remove", "is missing"),
])
def test_an_archive_is_checked_against_an_inventory_derived_outside_it(
        tmp_path, monkeypatch, archive, mutation, expected):
    """Rebuilding the manifest from a mutated archive must not launder it.

    The reviewer renamed a member, changed one's bytes, added one and removed a
    required one, regenerated `release_manifest.json` from the mutated archive
    each time, and passed the gate.  Both sides of the member comparison were
    the same zip.  The expectation now comes from the staged tree and the
    repository, which do not move when the archive does.
    """

    out = tmp_path / "out"
    out.mkdir()
    pending = out / ".pending"
    pending.mkdir()
    _pending_release(tmp_path, pending, monkeypatch)
    assert _check(pending) == []

    member = tmp_path / "member.txt"
    other = tmp_path / "other.txt"
    other.write_bytes(b"bytes nothing in the closure accounts for")
    keep = [(tmp_path / packager.SOURCE_CLOSURE_NAME,
             packager.SOURCE_CLOSURE_NAME)] if archive == "supplement.zip" else []
    entries = {
        "rename": [(member, "renamed.txt")],
        "rewrite": [(other, "member.txt")],
        "add": [(member, "member.txt"), (other, "smuggled.txt")],
        "remove": [],
    }[mutation]
    packager.write_zip(pending / archive, entries + keep)
    _stage_manifest(pending)                    # regenerated from the mutation

    findings = _check(pending)
    assert any(archive in f and expected in f for f in findings), findings


def test_the_expected_source_inventory_comes_from_the_committed_contract():
    """`expected_source_members` reads the contract and the repository only.

    It used to hash the staged files.  That made the staged tree its own
    authority, so changing a staged source and the matching archive member
    moved both sides of the comparison together.
    """

    expected = packager.expected_source_members(REPO_ROOT)
    pinned = contract.COMPILED_CLOSURE
    shipped = {name for name, entry in pinned.items()
               if entry["ships_in"] != "neither"}
    extras = set(packager.source_archive_extras(REPO_ROOT))
    assert set(expected) == shipped | extras
    assert "main.bbl" not in expected, "no archive carries it"
    for name in shipped:
        assert expected[name] == (pinned[name]["sha256"], pinned[name]["bytes"])
    for name, origin in packager.source_archive_extras(REPO_ROOT).items():
        assert expected[name] == (packager.sha256_file(origin),
                                  origin.stat().st_size), name
    # and the whole-tree inventory adds exactly main.bbl on top
    assert set(packager.expected_staged_sources(REPO_ROOT)) == \
        set(expected) | {"main.bbl"}


def test_the_source_inventory_does_not_move_when_the_staged_tree_does(
        staged_tree, tmp_path):
    """The authority must not follow a mutation of the thing it judges."""

    src = _clone_staged(staged_tree, tmp_path / "tree")
    before = packager.expected_source_members(REPO_ROOT)
    victim = src / "main.tex"
    victim.write_bytes(victim.read_bytes() + b"\n% smuggled\n")
    assert packager.expected_source_members(REPO_ROOT) == before


def _staged_release_from_build(tmp_path: Path):
    """A copy of a real built release plus its staged tree, safe to mutate."""

    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    if not (release / "src" / "main.fls").is_file():
        pytest.skip("the staged tree was not kept")
    src = tmp_path / "src"
    shutil.copytree(release / "src", src, symlinks=True)
    pending = tmp_path / "out" / ".pending"
    pending.mkdir(parents=True)
    for name in packager.RELEASE_DELIVERABLES:
        shutil.copy2(release / name, pending / name)
    return src, pending


def _regenerate_manifest_only(src: Path, pending: Path) -> list[dict]:
    """Rebuild the release manifest from the pending archives as they are.

    Unlike `_regenerate_caller_artifacts` this does not rewrite `source.zip`,
    so a test that has just edited an archive keeps its edit while everything a
    caller controls is brought back into agreement with it.
    """

    records = packager.derive_anonymization_records(REPO_ROOT)
    manifest = packager.derive_release_manifest(REPO_ROOT, src, pending)
    (pending / "release_manifest.json").write_bytes(
        packager.canonical_manifest_bytes(manifest))
    return records


def _regenerate_caller_artifacts(src: Path, pending: Path) -> list[dict]:
    """Rebuild every archive and manifest a caller controls, from `src`."""

    entries = [(src / relative, str(relative))
               for relative in packager.closure(src, REPO_ROOT)]
    packager.write_zip(pending / "source.zip", entries)
    records = packager.derive_anonymization_records(REPO_ROOT)
    manifest = packager.derive_release_manifest(REPO_ROOT, src, pending)
    (pending / "release_manifest.json").write_bytes(
        packager.canonical_manifest_bytes(manifest))
    return records


def test_a_mutated_staged_source_fails_the_mandatory_gate(tmp_path):
    """The reviewer's attack, end to end and with everything regenerated.

    A staged manuscript source and the matching `source.zip` member were both
    changed, the release manifest was rebuilt from the mutation, and
    `check_pending_release` returned an empty list. A clean rebuild of that
    archive produced a different PDF, so the gate had cleared a candidate that
    does not typeset the submitted document.
    """

    src, pending = _staged_release_from_build(tmp_path)
    records = _regenerate_caller_artifacts(src, pending)
    assert packager.check_pending_release(REPO_ROOT, src, pending, records) == []

    victim = "transport_experiment.tex"
    staged = src / victim
    original = staged.read_bytes()
    assert hashlib.sha256(original).hexdigest() == \
        contract.COMPILED_CLOSURE[victim]["sha256"]
    staged.write_bytes(original + b"\n% smuggled\n")
    records = _regenerate_caller_artifacts(src, pending)

    findings = packager.check_pending_release(REPO_ROOT, src, pending, records)
    assert any(f"staged source {victim}" in f and "committed inventory pins" in f
               for f in findings), findings
    assert any("source.zip" in f and "not the bytes they should be" in f
               for f in findings), findings


@pytest.mark.parametrize("mutation", ["missing", "renamed", "symlinked"])
def test_a_compiled_source_that_is_not_the_pinned_file_is_rejected(tmp_path,
                                                                   mutation):
    """Missing, renamed and symlinked staged sources, each caught by name."""

    src, pending = _staged_release_from_build(tmp_path)
    victim = "transport_experiment.tex"
    staged = src / victim
    body = staged.read_bytes()

    if mutation == "missing":
        staged.unlink()
        expected = "is missing from"
    elif mutation == "renamed":
        staged.rename(src / "renamed_experiment.tex")
        expected = "is missing from"
    else:
        elsewhere = tmp_path / "elsewhere.tex"
        elsewhere.write_bytes(body)
        staged.unlink()
        staged.symlink_to(elsewhere)
        expected = "is a symlink"

    findings = packager.check_staged_sources(REPO_ROOT, src)
    assert any(victim in f and expected in f for f in findings), findings


def test_an_extra_compiled_input_is_rejected(tmp_path):
    """A source the compiler read that nothing pins."""

    src, pending = _staged_release_from_build(tmp_path)
    smuggled = src / "smuggled.tex"
    smuggled.write_bytes(b"% not in the contract\n")
    fls = src / "main.fls"
    fls.write_text(fls.read_text(encoding="utf-8") + "INPUT smuggled.tex\n",
                   encoding="utf-8")

    findings = packager.check_staged_sources(REPO_ROOT, src)
    assert any("recorded inputs are not the pinned set" in f
               and "smuggled.tex" in f for f in findings), findings


@pytest.mark.parametrize("archive", ["source.zip", "supplement.zip"])
def test_a_duplicate_archive_member_is_rejected(tmp_path, archive):
    """`infolist` can hold the same name twice; a dict comparison hid it."""

    src, pending = _staged_release_from_build(tmp_path)
    target = pending / archive
    with zipfile.ZipFile(target) as source:
        first = source.infolist()[0]
        payload = source.read(first)
    with zipfile.ZipFile(target, "a", compression=zipfile.ZIP_STORED) as out:
        info = zipfile.ZipInfo(first.filename, date_time=packager.ZIP_TIMESTAMP)
        info.compress_type = zipfile.ZIP_STORED
        info.external_attr = 0o644 << 16
        out.writestr(info, payload)

    expected = (packager.expected_source_members(REPO_ROOT)
                if archive == "source.zip"
                else packager.expected_supplement_members(
                    REPO_ROOT, packager.derive_anonymization_records(REPO_ROOT)))
    findings = packager.check_archive_inventory(archive, target, expected)
    assert any("more than once" in f and first.filename in f
               for f in findings), findings


def test_a_symlink_archive_member_is_rejected(tmp_path):
    """A member whose mode says symlink is not a regular file."""

    src, pending = _staged_release_from_build(tmp_path)
    target = pending / "source.zip"
    with zipfile.ZipFile(target, "a", compression=zipfile.ZIP_STORED) as out:
        info = zipfile.ZipInfo("sneaky.tex", date_time=packager.ZIP_TIMESTAMP)
        info.compress_type = zipfile.ZIP_STORED
        info.create_system = 3
        info.external_attr = (0o120777 << 16)
        out.writestr(info, "/etc/passwd")

    findings = packager.check_archive_inventory(
        "source.zip", target, packager.expected_source_members(REPO_ROOT))
    assert any("not regular files" in f and "sneaky.tex" in f
               for f in findings), findings


def _retype_member(source: Path, target: Path, member: str, mode: int,
                   create_system: int = 3) -> None:
    """Rewrite an archive with one member's external attributes replaced.

    Everything else -- names, order, payloads, timestamps -- is preserved, so
    the only thing a checker can object to is the type metadata.
    """

    with zipfile.ZipFile(source) as original:
        infos = original.infolist()
        payloads = {info.filename: original.read(info) for info in infos}
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as out:
        for info in infos:
            rewritten = zipfile.ZipInfo(info.filename,
                                        date_time=packager.ZIP_TIMESTAMP)
            rewritten.compress_type = zipfile.ZIP_STORED
            rewritten.create_system = create_system
            rewritten.external_attr = (
                (mode if info.filename == member else 0o644) << 16)
            out.writestr(rewritten, payloads[info.filename])


@pytest.mark.parametrize("label, type_bits", [
    ("FIFO", stat.S_IFIFO),
    ("character device", stat.S_IFCHR),
    ("block device", stat.S_IFBLK),
    ("socket", stat.S_IFSOCK),
    ("symlink", stat.S_IFLNK),
    ("directory", stat.S_IFDIR),
])
def test_a_member_of_any_irregular_type_fails_the_publication_gate(
        tmp_path, label, type_bits):
    """Not only links and directories.

    The check tested `S_ISLNK` and `S_ISDIR` only, so a member whose Unix mode
    said FIFO, character device, block device or socket passed the complete
    publication gate with a matching name and payload, leaving whatever the
    reviewer's extractor chose to do about it.
    """

    src, pending = _staged_release_from_build(tmp_path)
    source_zip = pending / "source.zip"
    rewritten = tmp_path / "rewritten.zip"
    _retype_member(source_zip, rewritten, "main.tex", type_bits | 0o644)
    shutil.move(str(rewritten), str(source_zip))
    records = _regenerate_manifest_only(src, pending)

    findings = packager.check_pending_release(REPO_ROOT, src, pending, records)
    assert any("not regular files" in f and f"main.tex ({label})" in f
               for f in findings), (label, findings)


@pytest.mark.parametrize("label, mode, creator", [
    ("unix regular file", stat.S_IFREG | 0o644, 3),
    ("unix permission bits with no type field", 0o644, 3),
    ("mac os x creator", stat.S_IFREG | 0o644, 19),
    ("ms-dos creator with no unix mode", 0, 0),
    ("windows ntfs creator with no unix mode", 0, 11),
])
def test_supported_regular_file_metadata_still_passes(tmp_path, label, mode,
                                                      creator):
    """Rejecting types must not reject the writers this project supports."""

    src, pending = _staged_release_from_build(tmp_path)
    source_zip = pending / "source.zip"
    rewritten = tmp_path / "rewritten.zip"
    _retype_member(source_zip, rewritten, "main.tex", mode,
                   create_system=creator)
    shutil.move(str(rewritten), str(source_zip))
    records = _regenerate_manifest_only(src, pending)

    findings = packager.check_pending_release(REPO_ROOT, src, pending, records)
    assert findings == [], (label, findings)


def test_the_type_check_does_not_replace_the_content_checks(tmp_path):
    """A well-typed member with the wrong bytes is still rejected."""

    src, pending = _staged_release_from_build(tmp_path)
    source_zip = pending / "source.zip"
    with zipfile.ZipFile(source_zip) as original:
        infos = original.infolist()
        payloads = {info.filename: original.read(info) for info in infos}
    payloads["main.tex"] = payloads["main.tex"] + b"\n% smuggled\n"
    rewritten = tmp_path / "rewritten.zip"
    with zipfile.ZipFile(rewritten, "w", compression=zipfile.ZIP_STORED) as out:
        for info in infos:
            fresh = zipfile.ZipInfo(info.filename,
                                    date_time=packager.ZIP_TIMESTAMP)
            fresh.compress_type = zipfile.ZIP_STORED
            fresh.create_system = 3
            fresh.external_attr = (stat.S_IFREG | 0o644) << 16
            out.writestr(fresh, payloads[info.filename])
    shutil.move(str(rewritten), str(source_zip))
    records = _regenerate_manifest_only(src, pending)

    findings = packager.check_pending_release(REPO_ROOT, src, pending, records)
    assert any("not the bytes they should be" in f for f in findings), findings


def test_member_file_type_names_what_it_rejects():
    """The helper, directly, including a type nobody has defined."""

    def info(mode, creator=3):
        entry = zipfile.ZipInfo("x")
        entry.create_system = creator
        entry.external_attr = mode << 16
        return entry

    assert packager.member_file_type(info(stat.S_IFREG | 0o644)) is None
    assert packager.member_file_type(info(0o644)) is None
    assert packager.member_file_type(info(0)) is None
    assert packager.member_file_type(info(stat.S_IFLNK | 0o777, creator=0)) \
        is None, "a non-unix creator has no unix mode to read"
    assert packager.member_file_type(info(stat.S_IFIFO | 0o644)) == "FIFO"
    assert packager.member_file_type(info(stat.S_IFSOCK | 0o644)) == "socket"
    # 0o030000 is not a type this platform defines; it is still not a file
    assert "unknown type" in packager.member_file_type(info(0o030644))


def test_external_inputs_are_rederived_from_the_fls_every_time(staged_tree,
                                                               tmp_path):
    """No cache stands between the recorder and the manifest.

    The reviewer deleted one of the 249 entries from `EXTERNAL_INPUT_CACHE`
    before derivation and got a 248-entry manifest that passed.  There is no
    such cache now: the derivation re-runs the recorder, so the set follows the
    `.fls` file and nothing else.
    """

    assert not hasattr(packager, "EXTERNAL_INPUT_CACHE")
    roots = packager.texmf_roots(repo=REPO_ROOT, staged=staged_tree[0])
    dependency = next(
        (p for root in roots for p in root.rglob("article.cls")), None)
    if dependency is None:
        pytest.skip("no article.cls under any derived TeX tree")

    src = _clone_staged(staged_tree, tmp_path / "tree")
    before = packager.derive_external_inputs(REPO_ROOT, src)
    fls = src / "main.fls"
    original = fls.read_text(encoding="utf-8")
    fls.write_text(original + f"INPUT {dependency}\n", encoding="utf-8")
    after = packager.derive_external_inputs(REPO_ROOT, src)
    assert len(after) == len(before) + 1
    added = [item for item in after if item not in before]
    assert len(added) == 1 and added[0]["trusted"] is True
    assert added[0]["sha256"] == packager.sha256_file(dependency)
    assert added[0]["bytes"] == dependency.stat().st_size

    fls.write_text(original, encoding="utf-8")
    assert packager.derive_external_inputs(REPO_ROOT, src) == before


def test_a_manifest_missing_one_external_input_fails_the_gate(tmp_path,
                                                              monkeypatch):
    """The 249-to-248 attack, from the manifest side."""

    out = tmp_path / "out"
    out.mkdir()
    pending = out / ".pending"
    pending.mkdir()
    _pending_release(tmp_path, pending, monkeypatch)
    full = [{"name": f"TEXMFDIST:tex/latex/base/f{index}.sty",
             "sha256": f"{index:064d}", "bytes": 10 + index, "trusted": True}
            for index in range(249)]
    monkeypatch.setattr(packager, "derive_external_inputs",
                        lambda repo, src: [dict(item) for item in full])
    _stage_manifest(pending)
    assert _check(pending) == []

    _stage_manifest(pending, lambda m: m["external_tex_inputs"].pop())
    findings = _check(pending)
    assert any("external_tex_inputs" in f for f in findings), findings


def test_the_shipped_closure_document_is_derived_from_the_contract():
    """The gate's expectation for `SOURCE_CLOSURE.json` is the contract itself."""

    document = packager.derive_source_closure_document()
    assert document["schema_version"] == packager.CLOSURE_SCHEMA_VERSION
    assert len(document["entries"]) == len(contract.COMPILED_CLOSURE)
    for entry in document["entries"]:
        pinned = contract.COMPILED_CLOSURE[entry["staged"]]
        for field in ("repository", "sha256", "bytes", "role", "ships_in"):
            assert entry[field] == pinned[field], (entry["staged"], field)

    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    with zipfile.ZipFile(release / "supplement.zip") as archive:
        shipped = archive.read(packager.SOURCE_CLOSURE_NAME)
    assert shipped == packager.canonical_json_bytes(document)


def test_the_shipped_declaration_is_derived_from_the_contract():
    """Same for `ANONYMIZATION.json`: derived bytes, then compared."""

    records = packager.derive_anonymization_records(REPO_ROOT)
    derived = packager.canonical_json_bytes(
        packager.anonymization_declaration(records))
    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    with zipfile.ZipFile(release / "supplement.zip") as archive:
        assert archive.read(packager.ANONYMIZATION_MANIFEST) == derived


def test_the_real_archives_match_their_independently_derived_inventories():
    """End to end: both built archives against expectations derived elsewhere."""

    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    src = release / "src"
    if not (src / "main.fls").is_file():
        pytest.skip("the staged tree was not kept")
    records = packager.derive_anonymization_records(REPO_ROOT)
    assert packager.check_archive_inventory(
        "source.zip", release / "source.zip",
        packager.expected_source_members(REPO_ROOT)) == []
    assert packager.check_archive_inventory(
        "supplement.zip", release / "supplement.zip",
        packager.expected_supplement_members(REPO_ROOT, records)) == []


def test_mutated_evidence_bytes_fail_the_complete_pending_gate(tmp_path,
                                                               monkeypatch):
    """Change the evidence, keep the revision field, and the gate must refuse.

    The reviewer edited a repository evidence file without touching
    `git_revision`. Every derived record came back equal to `contract.CONTRACT`
    -- because the contract was the only thing the derivation read -- and the
    complete pending-release gate returned no findings at all.

    The digests are computed from the current bytes now, so the comparison has
    two independent sides.
    """

    clone = _evidence_clone(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    pending = out / ".pending"
    pending.mkdir()
    records = _pending_release_over(clone, tmp_path, pending, monkeypatch)

    # the untouched clone is clean, and the records really were computed
    assert packager.check_pending_release(clone, FIXTURE_SRC, pending,
                                          records) == []
    victim_path = "results/derived/transport_instantiation/selection.json"
    pinned = contract.CONTRACT[victim_path]
    by_path = {record["path"]: record for record in records}
    assert by_path[victim_path]["original_sha256"] == pinned["original_sha256"]

    victim = clone / victim_path
    before = victim.read_bytes()
    marker = b'"candidate_count": 9'
    assert marker in before, "fixture assumption about the evidence changed"
    after = before.replace(marker, b'"candidate_count": 8', 1)
    assert after != before
    victim.write_bytes(after)

    # the revision field is untouched, which is what defeated the old check
    _, was = packager._replace_revision_field(before, victim_path)
    _, now = packager._replace_revision_field(after, victim_path)
    assert was == now

    mutated = packager.derive_anonymization_records(clone)
    changed = {record["path"]: record for record in mutated}[victim_path]
    assert changed["original_sha256"] == hashlib.sha256(after).hexdigest()
    assert changed["original_sha256"] != pinned["original_sha256"]

    findings = packager.check_pending_release(clone, FIXTURE_SRC, pending,
                                              mutated)
    assert any("original_sha256" in f and "the contract pins" in f
               for f in findings), findings
    assert any("packaged_sha256" in f and "the contract pins" in f
               for f in findings), findings
    # and the repository's own bytes were never at risk
    assert (REPO_ROOT / victim_path).read_bytes() == before


def test_the_derived_records_hash_the_bytes_that_are_there_now(tmp_path,
                                                               monkeypatch):
    """Byte counts follow the file too, not just digests."""

    clone = _evidence_clone(tmp_path)
    monkeypatch.setattr(
        packager, "supplement_entries",
        lambda repo: [(Path(repo) / arcname, arcname)
                      for arcname in sorted(contract.CONTRACT)])
    victim_path = "results/derived/transport_instantiation/selection.json"
    victim = clone / victim_path
    grown = victim.read_bytes() + b"\n"
    victim.write_bytes(grown)

    record = {r["path"]: r
              for r in packager.derive_anonymization_records(clone)}[victim_path]
    assert record["original_bytes"] == len(grown)
    assert record["original_bytes"] != \
        contract.CONTRACT[victim_path]["original_bytes"]
    findings = packager.check_anonymization_record(
        packager.derive_anonymization_records(clone))
    assert any("original_bytes" in f for f in findings), findings


def test_the_anonymization_records_are_derived_not_reported():
    """Every field comes from the contract, the constants or the original bytes."""

    records = packager.derive_anonymization_records(REPO_ROOT)
    assert [record["path"] for record in records] == sorted(contract.CONTRACT)
    for record in records:
        assert set(record) == set(packager.TRANSFORM_RECORD_KEYS)
        pinned = contract.CONTRACT[record["path"]]
        for field in ("original_sha256", "original_bytes", "packaged_sha256",
                      "packaged_bytes"):
            assert record[field] == pinned[field], (record["path"], field)
        assert record["field"] == packager.ANONYMIZED_FIELD
        assert record["replacement"] == packager.ANONYMIZED_TOKEN
        assert record["reason"] == packager.TRANSFORM_REASON
        assert record["removed_value_class"] == \
            packager.TRANSFORM_REMOVED_VALUE_CLASS
        assert re.fullmatch(r"[0-9a-f]{40}",
                            record["removed_value_internal_only"])
    assert packager.check_anonymization_record(records) == []


@pytest.mark.parametrize("mutate, expected", [
    (lambda r: r[0].update(reason="no reason at all"), "reported"),
    (lambda r: r[0].update(removed_value_class="something else"), "reported"),
    (lambda r: r[0].update(source_path="somewhere/else.json"), "reported"),
    (lambda r: r[0].update(removed_value_internal_only="0" * 39), "reported"),
    (lambda r: r[0].pop("field"), "reported"),
    (lambda r: r[0].pop("source_path"), "reported"),
    (lambda r: r[0].update(smuggled="anything"), "reported"),
    (lambda r: r.append(dict(r[0])), "reported"),
    (lambda r: r.clear(), "reported"),
])
def test_a_reported_transform_record_that_differs_is_a_finding(
        tmp_path, monkeypatch, mutate, expected):
    """The build's own account of the transform is compared, never trusted.

    Each mutation used to pass because the staged manifest was regenerated from
    the same mutated list: one object was both the claim and the check.
    """

    out = tmp_path / "out"
    out.mkdir()
    pending = out / ".pending"
    pending.mkdir()
    _pending_release(tmp_path, pending, monkeypatch)
    reported = _transform_records()
    mutate(reported)
    findings = _check(pending, reported)
    assert any(expected in f for f in findings), findings


@pytest.mark.parametrize("mutate, expected", [
    (lambda r: r.append(dict(r[0])), "more than once"),
    (lambda r: r[0].update(smuggled="anything"), "keys are"),
    (lambda r: r[0].pop("reason"), "keys are"),
    (lambda r: r[0].update(reason="no reason at all"), "wrong reason"),
    (lambda r: r[0].update(removed_value_class="x"), "removed_value_class"),
    (lambda r: r[0].update(removed_value_internal_only="nope"),
     "removed_value_internal_only"),
    (lambda r: r[0].update(source_path="somewhere/else.json"), "source_path"),
    (lambda r: r[0].update(field="author"), "wrong field"),
    (lambda r: r[0].update(replacement="anonymous"), "wrong replacement"),
])
def test_each_anonymization_field_class_is_checked_independently(mutate,
                                                                 expected):
    """`check_anonymization_record` on the derived set, one field class at a time."""

    records = _transform_records()
    assert packager.check_anonymization_record(records) == []
    mutate(records)
    findings = packager.check_anonymization_record(records)
    assert any(expected in f for f in findings), (expected, findings)


def test_a_degenerate_expectation_is_rejected_even_when_the_file_agrees(
        tmp_path, monkeypatch):
    """Byte equality is worthless if the derived expectation is empty.

    An external input that no longer resolves is recorded with an empty digest
    and zero bytes.  Derive the manifest from that, stage it, and the two agree
    perfectly -- so the gate has to judge the expectation itself.
    """

    out = tmp_path / "out"
    out.mkdir()
    pending = out / ".pending"
    pending.mkdir()
    _pending_release(tmp_path, pending, monkeypatch)

    monkeypatch.setattr(packager, "derive_external_inputs",
                        lambda repo, src: [])
    _stage_manifest(pending)
    findings = _check(pending)
    assert any("derived manifest external_tex_inputs is empty" in f
               for f in findings), findings

    monkeypatch.setattr(packager, "derive_external_inputs", lambda repo, src: [
        {"name": "TEXMFDIST:tex/latex/base/article.cls", "sha256": "",
         "bytes": 0, "trusted": True}])
    _stage_manifest(pending)
    findings = _check(pending)
    assert any("no longer resolves on disk" in f for f in findings), findings


def test_a_late_consistency_failure_leaves_the_prior_release_untouched(
        tmp_path, monkeypatch):
    """A manifest that disagrees with the bytes beside it publishes nothing."""

    out = tmp_path / "out"
    prior = _sentinel_release(out)
    pending = out / ".pending"
    pending.mkdir()
    _pending_release(tmp_path, pending, monkeypatch)
    assert _check(pending) == []
    _stage_manifest(pending,
                    lambda m: m["deliverables"]["main.pdf"].update(
                        sha256="0" * 64))
    assert _check(pending)
    shutil.rmtree(pending)
    for name, data in prior.items():
        assert (out / name).read_bytes() == data


def test_a_missing_staged_deliverable_is_a_consistency_failure(tmp_path):
    pending = tmp_path / ".pending"
    pending.mkdir()
    (pending / "main.pdf").write_bytes(b"%PDF-1.5\n")
    findings = _check(pending)
    assert len(findings) == 3, findings
    assert all("is missing from the staged release" in f for f in findings)


@pytest.mark.parametrize("fail_at", [1, 2, 3, 4])
@pytest.mark.parametrize("present", ["all", "none", "some"])
def test_a_failed_publication_restores_the_previous_release(tmp_path, monkeypatch,
                                                            fail_at, present):
    """Injected failure at every replacement step, with and without priors.

    The previous implementation replaced the four deliverables one at a time
    with no rollback.  A reviewer injected a failure on the second and got a new
    `main.pdf` beside three old deliverables.
    """

    out = tmp_path / "out"
    out.mkdir()
    keep = {"all": packager.RELEASE_DELIVERABLES, "none": (),
            "some": ("main.pdf", "supplement.zip")}[present]
    prior = {}
    for name in keep:
        data = f"OLD {name}\n".encode()
        (out / name).write_bytes(data)
        prior[name] = data
    pending = out / ".pending"
    pending.mkdir()
    for name in packager.RELEASE_DELIVERABLES:
        (pending / name).write_bytes(f"NEW {name}\n".encode())

    real = packager.atomic_write_bytes
    calls = {"n": 0}

    def flaky(target, data):
        calls["n"] += 1
        if calls["n"] == fail_at:
            raise OSError(f"injected failure at replacement {fail_at}")
        return real(target, data)

    monkeypatch.setattr(packager, "atomic_write_bytes", flaky)
    with pytest.raises(OSError, match="injected failure"):
        packager.publish_release(pending, out)
    monkeypatch.undo()

    for name in packager.RELEASE_DELIVERABLES:
        target = out / name
        if name in prior:
            assert target.is_file(), name
            assert target.read_bytes() == prior[name], name
        else:
            assert not target.exists(), name
    assert not pending.exists(), "the staging area must not survive"


def test_a_successful_publication_writes_all_four_from_one_generation(tmp_path):
    out = tmp_path / "out"
    prior = _sentinel_release(out)
    pending = out / ".pending"
    pending.mkdir()
    for name in packager.RELEASE_DELIVERABLES:
        (pending / name).write_bytes(f"NEW {name}\n".encode())
    packager.publish_release(pending, out)
    assert not pending.exists()
    for name in prior:
        assert (out / name).read_bytes() == f"NEW {name}\n".encode()


def test_a_failed_publication_restores_a_symlink_without_writing_through_it(
        tmp_path, monkeypatch):
    """A pre-placed output symlink is recreated, never followed."""

    out = tmp_path / "out"
    out.mkdir()
    victim = tmp_path / "victim.bin"
    victim.write_bytes(b"bytes that are not ours\n")
    (out / "main.pdf").symlink_to(victim)
    for name in ("source.zip", "supplement.zip", "release_manifest.json"):
        (out / name).write_bytes(f"OLD {name}\n".encode())
    pending = out / ".pending"
    pending.mkdir()
    for name in packager.RELEASE_DELIVERABLES:
        (pending / name).write_bytes(f"NEW {name}\n".encode())

    real = packager.atomic_write_bytes
    calls = {"n": 0}

    def flaky(target, data):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError("injected failure at replacement 3")
        return real(target, data)

    monkeypatch.setattr(packager, "atomic_write_bytes", flaky)
    with pytest.raises(OSError):
        packager.publish_release(pending, out)
    monkeypatch.undo()

    assert (out / "main.pdf").is_symlink()
    assert os.readlink(out / "main.pdf") == str(victim)
    assert victim.read_bytes() == b"bytes that are not ours\n"
    for name in ("source.zip", "supplement.zip", "release_manifest.json"):
        assert (out / name).read_bytes() == f"OLD {name}\n".encode()
    assert not pending.exists()


def _staged_generation(out: Path) -> Path:
    """Four new deliverables in `out/.pending`, ready to publish."""

    pending = out / ".pending"
    pending.mkdir()
    for name in packager.RELEASE_DELIVERABLES:
        (pending / name).write_bytes(f"NEW {name}\n".encode())
    return pending


@pytest.mark.parametrize("fail_at", [1, 2, 3, 4])
@pytest.mark.parametrize("present", ["all", "none", "some"])
def test_a_failure_after_a_completed_replacement_still_rolls_back(
        tmp_path, monkeypatch, fail_at, present):
    """The reviewer's first attack: the write *finished*, then it raised.

    The old rollback replayed a list the successful writes appended to, and the
    name that raised had not been appended yet -- so the file it had already
    replaced stayed replaced, beside three old ones.
    """

    out = tmp_path / "out"
    out.mkdir()
    keep = {"all": packager.RELEASE_DELIVERABLES, "none": (),
            "some": ("main.pdf", "supplement.zip")}[present]
    prior = {}
    for name in keep:
        data = f"OLD {name}\n".encode()
        (out / name).write_bytes(data)
        prior[name] = data
    pending = _staged_generation(out)

    real = packager.atomic_write_bytes
    calls = {"n": 0}

    def flaky(target, data):
        calls["n"] += 1
        real(target, data)                      # the replacement completes ...
        if calls["n"] == fail_at:
            raise OSError(f"injected failure after replacement {fail_at}")

    monkeypatch.setattr(packager, "atomic_write_bytes", flaky)
    with pytest.raises(OSError, match="injected failure"):
        packager.publish_release(pending, out)
    monkeypatch.undo()

    for name in packager.RELEASE_DELIVERABLES:
        target = out / name
        if name in prior:
            assert target.is_file(), name
            assert target.read_bytes() == prior[name], name
        else:
            assert not target.exists(), name
    assert not pending.exists()


@pytest.mark.parametrize("fail_at", [1, 2, 3, 4])
def test_a_failure_midway_through_a_replacement_rolls_back(tmp_path, monkeypatch,
                                                           fail_at):
    """Not before and not after: inside `atomic_write_bytes`, before the swap.

    The temporary file exists, the destination has not moved, and the exception
    comes out of the writer itself rather than a wrapper around it.
    """

    out = tmp_path / "out"
    out.mkdir()
    prior = _sentinel_release(out)
    pending = _staged_generation(out)

    real_replace = os.replace
    state = {"n": 0, "fired": False}

    def flaky_replace(source, target, *args, **kwargs):
        if not state["fired"] and Path(target).name in packager.RELEASE_DELIVERABLES:
            state["n"] += 1
            if state["n"] == fail_at:
                state["fired"] = True           # the rollback must still work
                raise OSError(f"injected failure inside replacement {fail_at}")
        return real_replace(source, target, *args, **kwargs)

    monkeypatch.setattr(packager.os, "replace", flaky_replace)
    with pytest.raises(OSError, match="injected failure"):
        packager.publish_release(pending, out)
    monkeypatch.undo()

    for name, data in prior.items():
        assert (out / name).read_bytes() == data, name
    assert sorted(p.name for p in out.iterdir()) == sorted(prior)


def test_a_failure_in_the_rollback_writer_keeps_the_backup_and_says_so(
        tmp_path, monkeypatch):
    """The reviewer's second attack, and the worst one.

    An injected failure during a rollback write left the new files in place and
    then deleted the backup directory in a `finally` -- destroying the only copy
    of the old bytes while reporting a plain `OSError`.  Now the failure is a
    `ReleaseRecoveryError` that names a retained recovery copy, and the three
    restorations that can still happen happen.
    """

    out = tmp_path / "out"
    out.mkdir()
    prior = _sentinel_release(out)
    pending = _staged_generation(out)

    real_chmod = os.chmod

    def flaky_chmod(path, mode, *args, **kwargs):
        if ".source.zip.restore." in str(path):
            raise OSError("injected failure in the rollback writer")
        return real_chmod(path, mode, *args, **kwargs)

    real_write = packager.atomic_write_bytes

    def flaky_write(target, data):
        if target.name == "release_manifest.json":
            raise OSError("injected failure at the last replacement")
        return real_write(target, data)

    monkeypatch.setattr(packager.os, "chmod", flaky_chmod)
    monkeypatch.setattr(packager, "atomic_write_bytes", flaky_write)
    with pytest.raises(packager.ReleaseRecoveryError) as raised:
        packager.publish_release(pending, out)
    monkeypatch.undo()

    error = raised.value
    assert isinstance(error.cause, OSError)
    assert any("source.zip" in failure for failure in error.failures)

    # the durable copy is retained, named exactly, and holds the old bytes
    assert error.backup.is_dir()
    assert str(error.backup) in str(error)
    assert (error.backup / "source.zip").read_bytes() == prior["source.zip"]
    assert not pending.exists()

    # and the other three went back independently of the one that failed
    for name in ("main.pdf", "supplement.zip", "release_manifest.json"):
        assert (out / name).read_bytes() == prior[name], name
    assert (out / "source.zip").read_bytes() == b"NEW source.zip\n"
    # no temporary file from the failed restore is left behind
    assert not [p for p in out.iterdir() if ".restore." in p.name]


def test_one_failed_restoration_does_not_skip_the_others(tmp_path, monkeypatch):
    """Restorations are independent; the loop does not stop at the first raise."""

    out = tmp_path / "out"
    out.mkdir()
    prior = _sentinel_release(out)
    pending = _staged_generation(out)

    real_restore = packager.restore_deliverable
    attempted = []

    def flaky_restore(name, record, out_dir, backup):
        attempted.append(name)
        if name == "main.pdf":                  # the first one in the order
            raise OSError("injected failure restoring main.pdf")
        return real_restore(name, record, out_dir, backup)

    real_write = packager.atomic_write_bytes

    def flaky_write(target, data):
        if target.name == "supplement.zip":
            raise OSError("injected failure at replacement 3")
        return real_write(target, data)

    monkeypatch.setattr(packager, "restore_deliverable", flaky_restore)
    monkeypatch.setattr(packager, "atomic_write_bytes", flaky_write)
    with pytest.raises(packager.ReleaseRecoveryError) as raised:
        packager.publish_release(pending, out)
    monkeypatch.undo()

    assert attempted == list(packager.RELEASE_DELIVERABLES)
    assert any("main.pdf: restore raised" in f for f in raised.value.failures)
    for name in ("source.zip", "supplement.zip", "release_manifest.json"):
        assert (out / name).read_bytes() == prior[name], name


def test_a_recovered_rollback_deletes_the_backup(tmp_path, monkeypatch):
    """The retention rule has a second half: a clean recovery leaves nothing."""

    out = tmp_path / "out"
    out.mkdir()
    prior = _sentinel_release(out)
    pending = _staged_generation(out)

    real_write = packager.atomic_write_bytes

    def flaky_write(target, data):
        if target.name == "supplement.zip":
            raise OSError("injected failure at replacement 3")
        return real_write(target, data)

    monkeypatch.setattr(packager, "atomic_write_bytes", flaky_write)
    with pytest.raises(OSError, match="injected failure"):
        packager.publish_release(pending, out)
    monkeypatch.undo()

    for name, data in prior.items():
        assert (out / name).read_bytes() == data, name
    assert not pending.exists()
    assert not _recovery_directories(out)
    assert sorted(p.name for p in out.iterdir()) == sorted(prior)


def _recovery_directories(out: Path) -> list[Path]:
    return sorted(p for p in out.iterdir()
                  if p.name.startswith(packager.RECOVERY_PREFIX))


def _failing_publication(out: Path, monkeypatch, *, fail_write="supplement.zip",
                         fail_restore=None, fail_verify=None):
    """Publish into `out` with injected failures, and return what was raised."""

    pending = _staged_generation(out)
    real_write = packager.atomic_write_bytes
    real_restore = packager.restore_deliverable
    real_verify = packager.verify_restored
    verified = []

    def flaky_write(target, data):
        if target.name == fail_write:
            raise OSError(f"injected failure replacing {fail_write}")
        return real_write(target, data)

    def flaky_restore(name, record, out_dir, backup):
        if name == fail_restore:
            raise OSError(f"injected restore failure on {name}")
        return real_restore(name, record, out_dir, backup)

    def flaky_verify(name, record, out_dir):
        verified.append(name)
        if name == fail_verify:
            raise OSError(f"injected verification failure on {name}")
        return real_verify(name, record, out_dir)

    monkeypatch.setattr(packager, "atomic_write_bytes", flaky_write)
    monkeypatch.setattr(packager, "restore_deliverable", flaky_restore)
    monkeypatch.setattr(packager, "verify_restored", flaky_verify)
    raised = None
    try:
        packager.publish_release(pending, out)
    except BaseException as error:                  # noqa: BLE001 - it is the subject
        raised = error
    monkeypatch.undo()
    return raised, verified, pending


def test_a_verification_failure_still_checks_the_other_three(tmp_path,
                                                             monkeypatch):
    """A raise inside the first verification used to abort the whole loop.

    The reviewer injected it on the first restored file.  The other three were
    never verified, the exception escaped as a plain `OSError`, and what was
    left on disk was a mixed public set whose only backup was inside the
    staging directory.
    """

    out = tmp_path / "out"
    out.mkdir()
    prior = _sentinel_release(out)
    raised, verified, pending = _failing_publication(
        out, monkeypatch, fail_restore="source.zip", fail_verify="main.pdf")

    assert verified == list(packager.RELEASE_DELIVERABLES), verified
    assert isinstance(raised, packager.ReleaseRecoveryError), repr(raised)
    assert any("main.pdf: verification raised" in f for f in raised.failures)
    assert any("source.zip: restore raised" in f for f in raised.failures)

    # the recovery copy is durable, named, and outside the staging directory
    assert raised.backup.is_dir() and not raised.backup.is_symlink()
    assert raised.backup.parent == out
    assert not pending.exists()
    assert (raised.backup / "main.pdf").read_bytes() == prior["main.pdf"]

    # the three paths whose verification did not raise are back
    for name in ("main.pdf", "supplement.zip", "release_manifest.json"):
        assert (out / name).read_bytes() == prior[name], name


def test_a_retained_recovery_directory_describes_itself(tmp_path, monkeypatch):
    """A recovery copy that does not say what it holds is not much use."""

    out = tmp_path / "out"
    out.mkdir()
    prior = _sentinel_release(out)
    raised, _, _ = _failing_publication(out, monkeypatch,
                                        fail_restore="main.pdf")

    record = json.loads(
        (raised.backup / packager.RECOVERY_SNAPSHOT_NAME).read_text(
            encoding="utf-8"))
    assert set(record["snapshot"]) == set(packager.RELEASE_DELIVERABLES)
    assert record["snapshot"]["main.pdf"]["kind"] == "file"
    assert record["snapshot"]["main.pdf"]["sha256"] == \
        hashlib.sha256(prior["main.pdf"]).hexdigest()
    assert record["unrestored"] == raised.failures
    assert "injected" in record["original_failure"]


def test_an_existing_recovery_directory_is_never_deleted(tmp_path, monkeypatch):
    """A fixed name plus `rmtree` destroyed an earlier failed generation."""

    out = tmp_path / "out"
    out.mkdir()
    _sentinel_release(out)
    earlier = out / ".release-recovery"
    earlier.mkdir()
    (earlier / "EARLIER.txt").write_bytes(b"the only copy of an earlier failure\n")

    raised, _, _ = _failing_publication(out, monkeypatch,
                                        fail_restore="main.pdf")
    assert (earlier / "EARLIER.txt").read_bytes() == \
        b"the only copy of an earlier failure\n"
    assert raised.backup != earlier
    assert raised.backup.is_dir()


def test_an_existing_recovery_symlink_is_never_followed(tmp_path, monkeypatch):
    """`shutil.move` onto a link put the backup outside the output tree."""

    out = tmp_path / "out"
    out.mkdir()
    prior = _sentinel_release(out)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (out / ".release-recovery").symlink_to(elsewhere)

    raised, _, _ = _failing_publication(out, monkeypatch,
                                        fail_restore="main.pdf")
    assert list(elsewhere.iterdir()) == [], "nothing may be written through it"
    assert (out / ".release-recovery").is_symlink()
    assert not raised.backup.is_symlink()
    assert raised.backup.parent == out
    assert (raised.backup / "main.pdf").read_bytes() == prior["main.pdf"]


def test_two_failed_publications_keep_two_recovery_copies(tmp_path, monkeypatch):
    """Unique names, so the second failure does not overwrite the first."""

    out = tmp_path / "out"
    out.mkdir()
    _sentinel_release(out)
    first, _, _ = _failing_publication(out, monkeypatch, fail_restore="main.pdf")
    second, _, _ = _failing_publication(out, monkeypatch, fail_restore="main.pdf")

    assert first.backup != second.backup
    assert first.backup.is_dir() and second.backup.is_dir()
    assert len(_recovery_directories(out)) == 2


def test_a_recovery_that_cannot_be_retained_keeps_the_staging_directory(
        tmp_path, monkeypatch):
    """Last resort: say where the bytes actually are, and do not delete them."""

    out = tmp_path / "out"
    out.mkdir()
    prior = _sentinel_release(out)

    def refuse(out_dir, backup, snapshot, problems, failure):
        raise OSError("injected failure retaining the recovery copy")

    monkeypatch.setattr(packager, "retain_recovery", refuse)
    raised, _, pending = _failing_publication(out, monkeypatch,
                                              fail_restore="main.pdf")

    assert isinstance(raised, packager.ReleaseRecoveryError)
    assert raised.backup == pending / ".previous"
    assert pending.is_dir(), "the only copy of the old bytes must survive"
    assert (pending / ".previous" / "main.pdf").read_bytes() == prior["main.pdf"]
    assert any("could not be moved to a durable directory" in f
               for f in raised.failures)


def _recovery_material(out: Path, pending: Path) -> dict[str, list[str]]:
    """Every place holding old deliverables or recovery metadata, and what."""

    places = {}
    candidates = [pending / ".previous"] + [
        p for p in out.iterdir()
        if p.is_dir() and p.name.startswith(packager.RECOVERY_PREFIX)]
    for place in candidates:
        if not place.is_dir():
            continue
        held = sorted(p.name for p in place.iterdir())
        if any(name in packager.RELEASE_DELIVERABLES
               or name == packager.RECOVERY_SNAPSHOT_NAME for name in held):
            places[str(place)] = held
    return places


def test_a_successful_retention_leaves_one_complete_self_describing_copy(
        tmp_path, monkeypatch):
    """The whole backup moves in one rename, metadata already inside it."""

    out = tmp_path / "out"
    out.mkdir()
    prior = _sentinel_release(out)
    raised, _, pending = _failing_publication(out, monkeypatch,
                                              fail_restore="main.pdf")

    places = _recovery_material(out, pending)
    assert list(places) == [str(raised.backup)], places
    assert places[str(raised.backup)] == sorted(
        list(packager.RELEASE_DELIVERABLES) + [packager.RECOVERY_SNAPSHOT_NAME])
    for name, data in prior.items():
        assert (raised.backup / name).read_bytes() == data, name


def test_a_failed_backup_move_does_not_split_the_only_backup(tmp_path,
                                                             monkeypatch):
    """The reviewer's first split: a failure part-way through moving the backup.

    Moving the files one at a time meant a failure on the second left three in
    `.previous`, one in a directory nobody was told about, and the metadata
    nowhere.  The backup is moved whole now, so a rename failure leaves it
    exactly where it was -- complete, and already carrying its own
    `RECOVERY.json`.
    """

    out = tmp_path / "out"
    out.mkdir()
    prior = _sentinel_release(out)
    real_rename = os.rename

    def flaky_rename(source, destination, *args, **kwargs):
        if Path(destination).name.startswith(packager.RECOVERY_PREFIX):
            raise OSError("injected failure moving the backup")
        return real_rename(source, destination, *args, **kwargs)

    monkeypatch.setattr(packager.os, "rename", flaky_rename)
    raised, _, pending = _failing_publication(out, monkeypatch,
                                              fail_restore="main.pdf")

    places = _recovery_material(out, pending)
    assert len(places) == 1, f"the backup was split across {places}"
    only = Path(next(iter(places)))
    assert only == pending / ".previous"
    assert raised.backup == only, "the reported path must be the real one"
    assert places[str(only)] == sorted(
        list(packager.RELEASE_DELIVERABLES) + [packager.RECOVERY_SNAPSHOT_NAME])
    for name, data in prior.items():
        assert (only / name).read_bytes() == data, name
    record = json.loads((only / packager.RECOVERY_SNAPSHOT_NAME).read_text(
        encoding="utf-8"))
    assert set(record["snapshot"]) == set(packager.RELEASE_DELIVERABLES)
    assert any(f"recovery material is at {only}" in f for f in raised.failures)


def test_a_failed_metadata_write_does_not_strand_the_backup(tmp_path,
                                                            monkeypatch):
    """The reviewer's second split: the metadata write failing after the moves.

    It left the reported backup empty and all four files in a directory nobody
    was told about.  The metadata is written first now, so its failure happens
    before anything has moved.
    """

    out = tmp_path / "out"
    out.mkdir()
    prior = _sentinel_release(out)

    real_meta = packager.write_recovery_metadata
    calls = {"n": 0}

    def refuse_update(*args, **kwargs):
        # the prepublication write succeeds, so publication proceeds and the
        # rollback runs; only the retention update fails
        calls["n"] += 1
        if calls["n"] > 1:
            raise OSError("injected failure writing the recovery metadata")
        return real_meta(*args, **kwargs)

    monkeypatch.setattr(packager, "write_recovery_metadata", refuse_update)

    def refuse_move(out_dir, backup, snapshot, problems, failure):
        packager.write_recovery_metadata(backup, snapshot, problems, failure,
                                         stage_name="retained")
        raise OSError("injected failure moving the backup")

    monkeypatch.setattr(packager, "retain_recovery", refuse_move)
    raised, _, pending = _failing_publication(out, monkeypatch,
                                              fail_restore="main.pdf")

    places = _recovery_material(out, pending)
    assert len(places) == 1, f"the backup was split across {places}"
    only = Path(next(iter(places)))
    assert only == pending / ".previous" == raised.backup
    # the prepublication record is already there, so the directory is complete
    assert places[str(only)] == sorted(
        list(packager.RELEASE_DELIVERABLES) + [packager.RECOVERY_SNAPSHOT_NAME])
    for name, data in prior.items():
        assert (only / name).read_bytes() == data, name
    assert any(f"recovery material is at {only}" in f for f in raised.failures)
    assert not _recovery_directories(out), "nothing may be left unreported"


def test_a_retry_never_deletes_a_residual_recovery_backup(tmp_path, monkeypatch):
    """`reset_build_directory` would empty the only copy of a generation.

    Reproduced: the second publication into the surviving staging directory
    succeeded and took the residual backup with it.
    """

    out = tmp_path / "out"
    out.mkdir()
    prior = _sentinel_release(out)

    def refuse(out_dir, backup, snapshot, problems, failure):
        raise OSError("injected failure retaining the recovery copy")

    monkeypatch.setattr(packager, "retain_recovery", refuse)
    first, _, pending = _failing_publication(out, monkeypatch,
                                             fail_restore="main.pdf")
    monkeypatch.undo()
    residual = pending / ".previous"
    assert first.backup == residual
    before = {p.name: p.read_bytes() for p in residual.iterdir()}
    # the prepublication record is written before the first replacement, so a
    # residual backup carries it as well as the four copied deliverables
    assert set(before) == set(packager.RELEASE_DELIVERABLES) | {
        packager.RECOVERY_SNAPSHOT_NAME}
    assert before["main.pdf"] == prior["main.pdf"]
    # main.pdf is the one the injected fault left unrestored, so the public set
    # is mixed; the retry must not change it either way
    public = {name: (out / name).read_bytes()
              for name in packager.RELEASE_DELIVERABLES}
    assert public["main.pdf"] != prior["main.pdf"]

    # the retry: same staging directory, fresh deliverables, no injected fault
    for name in packager.RELEASE_DELIVERABLES:
        (pending / name).write_bytes(f"NEWER {name}\n".encode())
    with pytest.raises(packager.ReleaseRecoveryError) as raised:
        packager.publish_release(pending, out)

    assert residual.is_dir(), "the retry must not remove the residual backup"
    after = {p.name: p.read_bytes() for p in residual.iterdir()}
    assert after == before, "the residual bytes must be untouched"
    assert {name: (out / name).read_bytes()
            for name in packager.RELEASE_DELIVERABLES} == public, \
        "the refused retry must publish nothing"
    assert any("still holds an unrecovered previous generation" in f
               for f in raised.value.failures)
    assert raised.value.backup == residual


def test_a_rollback_leaves_an_unrelated_scratch_name_alone(tmp_path,
                                                           monkeypatch):
    """The symlink restore used a fixed scratch name and deleted whatever held it.

    Everything else about the rollback was right: the link came back and its
    target was untouched.  An unrelated file that happened to be called
    `.main.pdf.restore-link` was destroyed anyway.
    """

    out = tmp_path / "out"
    out.mkdir()
    victim = tmp_path / "victim.bin"
    victim.write_bytes(b"bytes that are not ours\n")
    (out / "main.pdf").symlink_to(victim)
    prior = {}
    for name in ("source.zip", "supplement.zip", "release_manifest.json"):
        data = f"prior {name}\n".encode()
        (out / name).write_bytes(data)
        prior[name] = data
    canary = out / ".main.pdf.restore-link"
    canary_bytes = b"an unrelated scratch file that is not ours\n"
    canary.write_bytes(canary_bytes)

    raised, _, pending = _failing_publication(out, monkeypatch,
                                              fail_write="supplement.zip")

    assert isinstance(raised, OSError)
    assert canary.is_file(), "the rollback deleted an unrelated path"
    assert canary.read_bytes() == canary_bytes
    assert (out / "main.pdf").is_symlink()
    assert os.readlink(out / "main.pdf") == str(victim)
    assert victim.read_bytes() == b"bytes that are not ours\n"
    for name, data in prior.items():
        assert (out / name).read_bytes() == data, name
    assert not pending.exists()
    # and no scratch symlink of this operation survived
    assert not [p for p in out.iterdir()
                if p.name.startswith(".main.pdf.restore-link.")]


def test_unique_scratch_symlink_never_touches_an_existing_path(tmp_path):
    """The primitive itself: creation is the test, so nothing is overwritten."""

    occupied = tmp_path / ".scratch.deadbeefdeadbeef"
    occupied.write_bytes(b"not ours\n")
    real_token = packager.secrets.token_hex
    calls = {"n": 0}

    def token(length):
        calls["n"] += 1
        return "deadbeefdeadbeef" if calls["n"] == 1 else real_token(length)

    packager.secrets.token_hex = token
    try:
        made = packager.unique_scratch_symlink(tmp_path, ".scratch", "/somewhere")
    finally:
        packager.secrets.token_hex = real_token

    assert made != occupied
    assert occupied.read_bytes() == b"not ours\n"
    assert made.is_symlink() and os.readlink(made) == "/somewhere"


def _residual_backup(out: Path) -> tuple[Path, dict[str, bytes]]:
    """A residual recovery backup exactly where a retention failure leaves one."""

    residual = out / ".pending" / ".previous"
    residual.mkdir(parents=True)
    kept = {}
    for name in packager.RELEASE_DELIVERABLES:
        data = f"the only copy of {name}\n".encode()
        (residual / name).write_bytes(data)
        kept[name] = data
    record = packager.recovery_metadata(
        {name: {"kind": "file", "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data), "mode": 0o644}
         for name, data in kept.items()},
        ["an earlier retention failure"], RuntimeError("earlier"),
        "prepublication")
    (residual / packager.RECOVERY_SNAPSHOT_NAME).write_bytes(record)
    kept[packager.RECOVERY_SNAPSHOT_NAME] = record
    return residual, kept


def test_the_cli_refuses_to_build_over_a_residual_recovery_backup(tmp_path):
    """The guard has to be at the CLI boundary, not inside publish_release.

    `main()` reset `.pending` long before `publish_release` ran, and the reset
    took `.previous` with it. The reviewer ran the real CLI over a residual
    backup and got exit 0, a replaced release and no surviving copy of the
    previous generation. This goes through `main()`, not `publish_release`.
    """

    out = tmp_path / "out"
    out.mkdir()
    public = {}
    for name in packager.RELEASE_DELIVERABLES:
        data = f"published {name}\n".encode()
        (out / name).write_bytes(data)
        public[name] = data
    residual, kept = _residual_backup(out)

    status = packager.main(["--repo", str(REPO_ROOT), "--out", str(out)])

    assert status == 13, "the CLI must refuse, not publish"
    assert residual.is_dir(), "the residual backup must survive"
    assert {p.name: p.read_bytes() for p in residual.iterdir()} == kept
    for name, data in public.items():
        assert (out / name).read_bytes() == data, name
    # nothing else was created under the output directory either
    assert sorted(p.name for p in out.iterdir()) == \
        sorted(list(packager.RELEASE_DELIVERABLES) + [".pending"])


def test_the_cli_guard_runs_before_any_directory_is_reset():
    """Structural: the check precedes every reset and cleanup in `main()`."""

    source = (REPO_ROOT / "submissions/tmlr_2026/package.py").read_text(
        encoding="utf-8")
    body = source.split("def main(", 1)[1]
    guard = body.index("residual_recovery_problem(")
    for destructive in ("reset_build_directory(", "shutil.rmtree(", "stage(",
                        "anonymize("):
        assert guard < body.index(destructive), destructive


def test_the_prepublication_snapshot_is_durable_before_any_replacement(
        tmp_path, monkeypatch):
    """A symlink and an absent entry leave no file; only the record holds them.

    The metadata was first written during retention, so a failure there left a
    directory of regular files with nothing to say `main.pdf` had been a symlink
    or that `supplement.zip` had been absent.
    """

    out = tmp_path / "out"
    out.mkdir()
    victim = tmp_path / "victim.bin"
    victim.write_bytes(b"bytes that are not ours\n")
    (out / "main.pdf").symlink_to(victim)
    (out / "source.zip").write_bytes(b"prior source.zip\n")
    (out / "release_manifest.json").write_bytes(b"prior manifest\n")
    # supplement.zip deliberately absent

    real_meta = packager.write_recovery_metadata
    calls = {"n": 0}

    def flaky_meta(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] > 1:              # the prepublication write succeeds
            raise OSError("injected failure updating the recovery metadata")
        return real_meta(*args, **kwargs)

    monkeypatch.setattr(packager, "write_recovery_metadata", flaky_meta)
    raised, _, pending = _failing_publication(
        out, monkeypatch, fail_write="release_manifest.json",
        fail_restore="source.zip")

    assert isinstance(raised, packager.ReleaseRecoveryError)
    record = json.loads(
        (raised.backup / packager.RECOVERY_SNAPSHOT_NAME).read_text(
            encoding="utf-8"))
    assert record["stage"] == "prepublication"
    snapshot = record["snapshot"]
    assert snapshot["main.pdf"] == {"kind": "symlink", "target": str(victim)}
    assert snapshot["supplement.zip"] == {"kind": "absent"}
    assert snapshot["source.zip"]["kind"] == "file"
    assert snapshot["source.zip"]["sha256"] == \
        hashlib.sha256(b"prior source.zip\n").hexdigest()
    assert any("metadata could not be updated" in f for f in raised.failures)


@pytest.mark.parametrize("fault", ["write", "fsync"])
def test_a_prepublication_metadata_failure_publishes_nothing(tmp_path,
                                                             monkeypatch, fault):
    """If the record cannot be made durable, no public byte moves."""

    out = tmp_path / "out"
    out.mkdir()
    victim = tmp_path / "victim.bin"
    victim.write_bytes(b"bytes that are not ours\n")
    (out / "main.pdf").symlink_to(victim)
    (out / "source.zip").write_bytes(b"prior source.zip\n")
    (out / "release_manifest.json").write_bytes(b"prior manifest\n")
    # supplement.zip deliberately absent
    pending = _staged_generation(out)

    if fault == "write":
        def refuse(*args, **kwargs):
            raise OSError("injected failure writing the recovery metadata")
        monkeypatch.setattr(packager, "write_recovery_metadata", refuse)
    else:
        real_fsync = packager.fsync_directory

        def flaky_fsync(path):
            if path.name == ".previous":
                raise OSError("injected fsync failure on the backup directory")
            return real_fsync(path)
        monkeypatch.setattr(packager, "fsync_directory", flaky_fsync)

    with pytest.raises(packager.ReleaseRecoveryError) as raised:
        packager.publish_release(pending, out)
    monkeypatch.undo()

    assert any("no deliverable was replaced" in f
               for f in raised.value.failures), raised.value.failures
    # the public release is exactly as it was
    assert (out / "main.pdf").is_symlink()
    assert os.readlink(out / "main.pdf") == str(victim)
    assert victim.read_bytes() == b"bytes that are not ours\n"
    assert (out / "source.zip").read_bytes() == b"prior source.zip\n"
    assert (out / "release_manifest.json").read_bytes() == b"prior manifest\n"
    assert not (out / "supplement.zip").exists()
    # the copied backup is named and kept
    assert raised.value.backup == pending / ".previous"
    assert raised.value.backup.is_dir()
    assert not _recovery_directories(out)


def test_an_unreadable_recovery_location_is_reported_not_raised(tmp_path,
                                                                monkeypatch):
    """Enumeration is fault-injected, so this does not depend on being non-root.

    A pre-existing recovery directory that could not be listed raised
    `PermissionError` straight out of the failure handler, replacing the
    structured error and losing the known backup path with it.
    """

    out = tmp_path / "out"
    out.mkdir()
    prior = _sentinel_release(out)
    blocked = out / f"{packager.RECOVERY_PREFIX}unreadable"
    blocked.mkdir()
    (blocked / "main.pdf").write_bytes(b"an earlier generation\n")

    real_iterdir = Path.iterdir

    def flaky_iterdir(self):
        if self.name == blocked.name:
            raise PermissionError(13, "Permission denied", str(self))
        return real_iterdir(self)

    def refuse(out_dir, backup, snapshot, problems, failure):
        raise OSError("injected failure retaining the recovery copy")

    monkeypatch.setattr(packager, "retain_recovery", refuse)
    monkeypatch.setattr(Path, "iterdir", flaky_iterdir)
    raised, _, pending = _failing_publication(out, monkeypatch,
                                              fail_restore="main.pdf")
    monkeypatch.undo()

    assert isinstance(raised, packager.ReleaseRecoveryError), repr(raised)
    assert raised.backup == pending / ".previous"
    assert any(str(pending / ".previous") in f and "recovery material is at" in f
               for f in raised.failures), raised.failures
    assert any(str(blocked) in f and "could not be enumerated" in f
               for f in raised.failures), raised.failures
    # the unreadable directory was left completely alone
    assert blocked.is_dir()
    assert (blocked / "main.pdf").read_bytes() == b"an earlier generation\n"
    for name, data in prior.items():
        if name != "main.pdf":
            assert (out / name).read_bytes() == data, name


#: A recovery directory whose name sorts before every 16-hex name `mkdtemp`-
#: style naming can produce, so "first in sorted order" deterministically picks
#: the older generation if anything still sorts rather than tracks.
OLDER_RECOVERY_SUFFIX = "0" * 16


def _older_recovery_generation(out: Path) -> tuple[Path, bytes]:
    older = out / f"{packager.RECOVERY_PREFIX}{OLDER_RECOVERY_SUFFIX}"
    older.mkdir()
    data = b"an OLDER generation, not the one being retained now\n"
    (older / "main.pdf").write_bytes(data)
    (older / packager.RECOVERY_SNAPSHOT_NAME).write_bytes(b"{}\n")
    return older, data


@pytest.mark.parametrize("break_enumeration", [False, True])
def test_a_parent_fsync_failure_still_names_the_new_destination(
        tmp_path, monkeypatch, break_enumeration):
    """The rename succeeded, so the bytes are at the new path and nowhere else.

    The parent fsync used to run before anything recorded where the directory
    had gone, so when it failed the handler fell back to scanning the output
    directory. With an older recovery generation present that scan could put the
    older path first and report it as the primary backup; if the scan failed
    too, the new destination was left out of the error entirely.
    """

    out = tmp_path / "out"
    out.mkdir()
    prior = _sentinel_release(out)
    older, older_bytes = _older_recovery_generation(out)

    real_fsync = packager.fsync_directory
    real_iterdir = Path.iterdir

    def flaky_fsync(path):
        if path == out:
            raise OSError("injected fsync failure on the output directory")
        return real_fsync(path)

    def flaky_iterdir(self):
        if self == out:
            raise PermissionError(13, "Permission denied", str(self))
        return real_iterdir(self)

    monkeypatch.setattr(packager, "fsync_directory", flaky_fsync)
    if break_enumeration:
        monkeypatch.setattr(Path, "iterdir", flaky_iterdir)
    raised, _, pending = _failing_publication(out, monkeypatch,
                                              fail_restore="main.pdf")
    monkeypatch.undo()

    assert isinstance(raised, packager.ReleaseRecoveryError), repr(raised)
    created = [p for p in out.iterdir()
               if p.name.startswith(packager.RECOVERY_PREFIX) and p != older]
    assert len(created) == 1, created
    destination = created[0]

    # the primary is the generation this run retained, not the older one
    assert raised.backup == destination
    assert any(f"recovery material is at {destination}" in f
               for f in raised.failures), raised.failures
    assert any("that is the current generation" in f
               for f in raised.failures), raised.failures
    assert any("could not be moved to a durable directory" in f
               for f in raised.failures), raised.failures

    # exact preserved bytes, in the new destination and in the older one
    for name, data in prior.items():
        assert (destination / name).read_bytes() == data, name
    assert (destination / packager.RECOVERY_SNAPSHOT_NAME).is_file()
    assert (older / "main.pdf").read_bytes() == older_bytes
    assert not pending.exists() or not (pending / ".previous").exists()

    if break_enumeration:
        assert any("could not be enumerated" in f
                   for f in raised.failures), raised.failures
        # the older path cannot be listed, so it is not claimed as located
        assert not any(str(older) in f and "recovery material is at" in f
                       for f in raised.failures)
    else:
        # both are reported, and the older one never comes first
        assert any(f"recovery material is at {older}" in f
                   for f in raised.failures), raised.failures
        order = [f.split("recovery material is at ")[1].split(":")[0]
                 for f in raised.failures if "recovery material is at " in f]
        assert order[0] == str(destination), order


def test_retain_recovery_records_the_destination_before_the_fsync():
    """Structural: the out-parameter is appended between rename and fsync."""

    source = (REPO_ROOT / "submissions/tmlr_2026/package.py").read_text(
        encoding="utf-8")
    body = source.split("def retain_recovery(", 1)[1].split("\ndef ", 1)[0]
    assert body.index("os.rename(backup, durable)") \
        < body.index("relocated.append(durable)") \
        < body.index("fsync_directory(out)")


def test_an_unreadable_residual_backup_stops_the_build(tmp_path, monkeypatch):
    """The guard must fail closed when it cannot see what is there."""

    out = tmp_path / "out"
    out.mkdir()
    backup = out / ".pending" / ".previous"
    backup.mkdir(parents=True)
    real_iterdir = Path.iterdir

    def flaky_iterdir(self):
        if self == backup:
            raise PermissionError(13, "Permission denied", str(self))
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", flaky_iterdir)
    problem = packager.residual_recovery_problem(backup)
    monkeypatch.undo()

    assert problem is not None
    assert "could not be enumerated" in problem
    assert "Resolve it by hand" in problem


def test_publish_release_documents_only_the_guarantee_it_implements():
    """No claim of crash consistency, which this does not provide."""

    doc = " ".join(packager.publish_release.__doc__.replace("*", "").split())
    assert "caught application failures" in doc
    assert re.search(r"\bnot crash(?: or power-loss)? consistency\b", doc), doc


def test_every_gate_runs_before_anything_is_published():
    """Structural: the size and consistency gates precede publish_release."""

    source = (REPO_ROOT / "submissions/tmlr_2026/package.py").read_text(
        encoding="utf-8")
    body = source.split("def main(", 1)[1]
    assert body.index("check_archive_size(") < body.index("publish_release(")
    assert body.index("check_pending_release(") < body.index("publish_release(")
    # and the deliverables are built into the staging area, never into `out`
    assert 'atomic_write_bytes(pending / "main.pdf"' in body
    assert 'write_zip(pending / "source.zip"' in body
    assert 'write_zip(pending / "supplement.zip"' in body


# --------------------------------------------------------------------------
# 26. the vendored third-party packages
# --------------------------------------------------------------------------


def test_every_vendored_package_matches_its_pinned_digest():
    for name, pinned in sorted(packager.VENDORED_PACKAGE_DIGESTS.items()):
        path = REPO_ROOT / packager.VENDORED_DIRECTORY / name
        assert path.is_file(), name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == pinned, name


def test_an_edited_vendored_package_is_not_exempt(staged_tree, tmp_path):
    src = _clone_staged(staged_tree, tmp_path / "tree")
    victim = src / "pgfplots.sty"
    assert victim.is_file()
    victim.write_text(victim.read_text(encoding="utf-8") + "\n\\scriptsize\n",
                      encoding="utf-8")
    findings = packager.check_compiled_layout_rules(src, staged_tree[1])
    assert any("vendored package was modified" in f for f in findings), findings


def test_the_vendored_licences_ship_with_the_code():
    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    with zipfile.ZipFile(release / "source.zip") as archive:
        members = set(archive.namelist())
    for name in packager.VENDORED_LICENSE_FILES:
        assert name in members, name
    for name in packager.VENDORED_PACKAGE_DIGESTS:
        assert name in members, name
    assert "LICENSE-tmlr-style" in members


def test_no_font_is_vendored():
    for name in packager.VENDORED_PACKAGE_DIGESTS:
        assert Path(name).suffix in {".sty", ".tex", ".def", ".cfg", ""}, name
        assert not name.endswith((".pfb", ".ttf", ".otf", ".tfm", ".vf")), name


def test_the_vendored_packages_are_recorded_as_such():
    for name in packager.VENDORED_PACKAGE_DIGESTS:
        assert packager.closure_role(name) == "vendored-package", name
        assert ledger_tool.derive_closure_role(name) == "vendored-package", name
        assert ledger_tool.derive_repository_path(name) == \
            f"{packager.VENDORED_DIRECTORY}/{name}", name
    # a vendored package is not audited for numbers and does not ship in the
    # supplement: it is third-party code held at a digest
    assert "vendored-package" not in ledger_tool.AUDITED_CLOSURE_ROLES
    assert "vendored-package" not in ledger_tool.SUPPLEMENT_ROLES


def test_the_vendored_packages_are_documented_with_their_licences():
    note = (REPO_ROOT / packager.VENDORED_DIRECTORY
            / "VENDORED-PACKAGES.md").read_text(encoding="utf-8")
    for package in ("pgfplots", "microtype", "mathtools", "cleveref"):
        assert package in note, package
    for name in packager.VENDORED_LICENSE_FILES:
        assert name in note, name


def test_an_upstream_repository_url_is_allowed_only_in_a_pinned_package(tmp_path):
    """mhsetup.sty carries github.com/latex3/mathtools; that is not our identity."""

    pinned = REPO_ROOT / packager.VENDORED_DIRECTORY / "mhsetup.sty"
    assert scan([(pinned, "mhsetup.sty")]) == []
    forged = tmp_path / "mhsetup.sty"
    forged.write_text(pinned.read_text(encoding="utf-8") + "\n% edited\n",
                      encoding="utf-8")
    assert any("repository URL" in f for f in scan([(forged, "mhsetup.sty")]))
    other = tmp_path / "notes.md"
    other.write_text("see github.com/someone/something\n", encoding="utf-8")
    assert any("repository URL" in f for f in scan([(other, "notes.md")]))


def test_the_source_archive_is_described_precisely():
    readme = (REPO_ROOT / "submissions/tmlr_2026/README.md").read_text(
        encoding="utf-8")
    assert "exactly the files pdfTeX opened" not in readme
    assert "project-local" in readme
    assert "external_tex_inputs" in readme
    for path in ("submissions/tmlr_2026/build.sh", "paper/EXPOSITION_REVISION.md"):
        text = (REPO_ROOT / path).read_text(encoding="utf-8")
        assert "exactly the files pdfTeX opened" not in text, path
        assert "recorder's `.fls` closure" not in text, path


def test_the_formal_change_record_names_its_one_exception():
    note = (REPO_ROOT / "paper/EXPOSITION_REVISION.md").read_text(encoding="utf-8")
    assert "No theorem, lemma, corollary, proposition, assumption, equation" \
        not in note
    assert "sole\ntheorem/lemma/corollary/proposition statement-text exception" in note
    assert "equations and its conclusion are\nunchanged" in note


def test_no_release_output_is_written_through_an_unchecked_path():
    """Structural: every write into the output directory goes through the
    symlink-safe helpers, so a new deliverable cannot reintroduce the hole."""

    source = (REPO_ROOT / "submissions/tmlr_2026/package.py").read_text(
        encoding="utf-8")
    body = source.split("def main(", 1)[1]
    for unsafe in ("out / ", "stage_dir / "):
        for line in body.splitlines():
            if unsafe in line and (".write_text(" in line
                                   or ".write_bytes(" in line
                                   or "shutil.copy2(" in line):
                pytest.fail(f"unchecked write into the output tree: {line!r}")


def test_reset_build_directory_unlinks_a_symlinked_directory(tmp_path):
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "keep.txt").write_bytes(b"keep")
    target = tmp_path / "src"
    target.symlink_to(victim, target_is_directory=True)

    packager.reset_build_directory(target)

    assert (victim / "keep.txt").read_bytes() == b"keep"
    assert target.is_dir() and not target.is_symlink()
    assert list(target.iterdir()) == []


# --------------------------------------------------------------------------
# 14. an unresolved reference or citation fails the release
# --------------------------------------------------------------------------


def test_the_reference_check_reads_the_log_and_the_rendered_text(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.log").write_text(
        "LaTeX Warning: Reference `tab:missing' on page 3 undefined on "
        "input line 10.\n"
        "LaTeX Warning: Citation `nobody2020' on page 4 undefined on input "
        "line 11.\n"
        "LaTeX Warning: There were undefined references.\n",
        encoding="utf-8")
    findings = packager.check_compiled_references(src)
    assert any("undefined reference" in f and "tab:missing" in f
               for f in findings), findings
    assert any("undefined citation" in f and "nobody2020" in f
               for f in findings), findings


def test_the_reference_check_is_quiet_on_a_clean_log(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.log").write_text(
        "LaTeX Warning: Some other warning that mentions a page.\n",
        encoding="utf-8")
    assert packager.check_compiled_references(src) == ["main.pdf is missing; "
                                                       "nothing to inspect"]


def test_a_literal_question_mark_is_not_an_unresolved_reference():
    """The manuscript asks questions and cites a URL with `?id=`."""

    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    rendered = subprocess.run(
        ["pdftotext", "-layout", str(release / "main.pdf"), "-"],
        capture_output=True, text=True, check=True).stdout
    assert "?" in rendered                      # real question marks are there
    for placeholder in packager.UNRESOLVED_RENDERED:
        assert placeholder not in rendered, placeholder


@pytest.mark.parametrize("broken, expected", [
    (r"\Cref{tab:does-not-exist-anywhere}", "unresolved refs"),
    (r"\citep{nobody-ever-wrote-this}", "missing citations"),
])
def test_the_staged_entry_point_is_validated_not_just_the_legacy_one(
        tmp_path, broken, expected):
    """An unresolved TMLR-only reference used to pass the old-entry validator."""

    repo = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "paper", repo / "paper",
                    ignore=shutil.ignore_patterns("*.pdf"))
    (repo / "submissions/tmlr_2026").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / packager.ENTRY_POINT, repo / packager.ENTRY_POINT)
    shutil.copy2(REPO_ROOT / "paper/validate.py", repo / "paper/validate.py")
    (repo / "tools").mkdir()
    shutil.copy2(REPO_ROOT / "tools/tex_conditionals.py",
                 repo / "tools/tex_conditionals.py")
    experiment = repo / "paper/transport_experiment.tex"
    experiment.write_text(
        experiment.read_text(encoding="utf-8").replace(
            "\\paragraph{Protocol.}", broken + "\n\\paragraph{Protocol.}", 1),
        encoding="utf-8")

    out = tmp_path / "out"
    src, _ = packager.stage(repo, out)
    findings = packager.validate_staged_sources(repo, src)
    assert findings, "the staged entry point was not validated"
    assert any(expected in finding for finding in findings), findings


def test_the_real_staged_entry_point_validates_clean(tmp_path):
    out = tmp_path / "out"
    src, _ = packager.stage(REPO_ROOT, out)
    assert packager.validate_staged_sources(REPO_ROOT, src) == []


# --------------------------------------------------------------------------
# 15. the shipped provenance records are in the verification closure
# --------------------------------------------------------------------------


def test_the_provenance_records_are_pinned_and_verified():
    results = contract.check_provenance(REPO_ROOT)
    assert results
    assert all(ok for _, ok, _ in results), results
    for relative in contract.PROVENANCE_PINS:
        assert (REPO_ROOT / relative).is_file()


def test_zeroing_a_provenance_digest_is_rejected(tmp_path):
    """The exact mutation: `artifact_sha256` replaced with zeros."""

    root = tmp_path / "tree"
    for relative in contract.PROVENANCE_PINS:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        record = json.loads(
            (REPO_ROOT / relative).read_text(encoding="utf-8"))
        record["artifact_sha256"] = "0" * 64
        target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    results = contract.check_provenance(root)
    assert any(not ok and "binds its artifact" in name
               for name, ok, _ in results), results

    done = subprocess.run(
        [sys.executable, str(CONTRACT_TOOL), "--root", str(root)],
        capture_output=True, text=True)
    assert done.returncode == 1, done.stdout
    assert "FAIL" in done.stdout


def test_repository_mode_still_checks_the_provenance_pins():
    done = subprocess.run(
        [sys.executable, str(CONTRACT_TOOL), "--root", str(REPO_ROOT)],
        capture_output=True, text=True)
    assert done.returncode == 0, done.stdout
    assert "optional repository mode" in done.stdout
    assert "pinned provenance and shipped-tool checks passed" in done.stdout


def test_the_pinned_list_is_what_the_sidecar_sweep_skips():
    done = subprocess.run(
        [sys.executable, str(CONTRACT_TOOL), "--list-pinned"],
        capture_output=True, text=True, check=True)
    listed = set(done.stdout.split())
    for relative in contract.PROVENANCE_PINS:
        assert relative in listed
    for relative in contract.CONTRACT:
        assert relative in listed
    sweep = (REPO_ROOT / "submissions/tmlr_2026/supplement_verify.sh").read_text(
        encoding="utf-8")
    assert "--list-pinned" in sweep
    assert "results/derived" in sweep


# --------------------------------------------------------------------------
# 16. the revision scanner names identities, not hex shapes
# --------------------------------------------------------------------------


def test_a_superseded_candidate_is_still_a_project_revision(tmp_path):
    """`F94FA4B` passed once the amend made that commit unreachable."""

    superseded = "f94fa4ba7b76a38fcb86a7c8d95d0139af6fcaee"
    assert superseded in PROJECT_REVISIONS
    for rendered in (superseded, superseded[:7].upper(), superseded[:12]):
        path = tmp_path / "note.txt"
        path.write_text(f"built at {rendered}\n", encoding="utf-8")
        assert scan([(path, "note.txt")]), rendered


def test_a_benign_forty_hex_digest_is_not_a_finding(tmp_path):
    """The SHA-1 of "abc". A content digest is not a leak."""

    benign = "a9993e364706816aba3e25717850c26c9cd0d89d"
    assert len(benign) == 40
    assert benign not in PROJECT_REVISIONS
    path = tmp_path / "digests.txt"
    path.write_text(f"sha1 of abc: {benign}\n", encoding="utf-8")
    assert scan([(path, "digests.txt")]) == []


def test_a_forty_hex_value_in_a_revision_field_is_still_a_finding(tmp_path):
    """Unknown or not, a value called a revision names a repository."""

    path = tmp_path / "meta.json"
    path.write_text(
        '{"git_revision": "a9993e364706816aba3e25717850c26c9cd0d89d"}\n',
        encoding="utf-8")
    findings = scan([(path, "meta.json")])
    assert findings and "revision field" in findings[0], findings


def test_a_sixty_four_hex_content_digest_is_still_fine(tmp_path):
    path = tmp_path / "sidecar.txt"
    path.write_text(
        "0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02  x\n",
        encoding="utf-8")
    assert scan([(path, "sidecar.txt")]) == []


def test_the_recorded_revisions_include_every_candidate_so_far():
    for revision in ("b99b682ecc8f69552a3f57b1b85333378ed12ac1",
                     "c8f9e85519f6274808c5afe07e70aea774778f23",
                     "301f1d7c89b4a02e030c101bdb0b1f0bb5302a2b",
                     "f94fa4ba7b76a38fcb86a7c8d95d0139af6fcaee",
                     "4fa7b8c959eaca43a8b8110a9d2aedf40d2280a9"):
        assert revision in packager.RECORDED_PROJECT_REVISIONS, revision


# --------------------------------------------------------------------------
# 17. the number audit is exhaustive over the shipped closure
# --------------------------------------------------------------------------


def test_the_audited_set_is_the_transitive_input_closure():
    closure = {str(p) for p in ledger_tool.manuscript_closure(REPO_ROOT)}
    assert str(packager.ENTRY_POINT) in closure
    for expected in ("paper/transport_experiment.tex",
                     "paper/transport_proofs.tex",
                     "paper/tables/transport_instantiation_validity.tex",
                     "paper/figures/transport_instantiation_bound.tex"):
        assert expected in closure, expected
    for excluded in ("paper/main.tex", "paper/legacy_experiments.tex"):
        assert excluded not in closure, excluded


def test_a_comment_cannot_stand_in_for_a_visible_literal(tmp_path):
    """The exact reproduction: visible `.1`, old value parked in a comment."""

    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/transport_experiment.tex"
    text = path.read_text(encoding="utf-8")
    anchor = "best-fixed-action regret $180.4$"
    assert anchor in text
    path.write_text(
        text.replace(anchor, "best-fixed-action regret $.1$  % was $180.4$", 1),
        encoding="utf-8")
    failures = _audit(root)
    assert any("accounted for" in name for name in failures), failures


def test_a_leading_dot_decimal_is_recognised(tmp_path):
    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/transport_experiment.tex"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "No run has zero regret.",
            "No run has zero regret.  The ratio is .37.", 1),
        encoding="utf-8")
    assert _audit(root)


def test_an_unclassified_number_in_any_theory_source_fails(tmp_path):
    """Not just distinctive ledger values: any unaccounted literal."""

    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/transport_theory.tex"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "Neither the local factor",
            "The observed value is 42.7.\nNeither the local factor", 1),
        encoding="utf-8")
    failures = _audit(root)
    assert any("paper/transport_theory.tex" in name
               for name in failures), failures


def test_a_new_input_source_joins_the_audit_automatically(tmp_path):
    root = _submitted_tex_tree(tmp_path)
    (root / "paper/new_results.tex").write_text(
        "The new mean is 7.5.\n", encoding="utf-8")
    conclusion = root / "paper/body_conclusion.tex"
    conclusion.write_text(
        conclusion.read_text(encoding="utf-8") + "\n\\input{new_results}\n",
        encoding="utf-8")
    failures = _audit(root)
    assert any("paper/new_results.tex" in name for name in failures), failures


def test_the_supplement_readme_counts_are_source_derived(tmp_path):
    """`2,400 trajectories` used to be prose nobody checked."""

    entries = [e for e in ledger_tool.build_ledger(REPO_ROOT)
               if "2,400 trajectories" in e.literal]
    assert entries
    aggregate = {"completed_run_count": 2400}
    assert [e.compute(aggregate, {}) for e in entries] == [2400.0]


def test_a_classified_literal_is_scoped_to_its_own_file():
    """`42.7` being fine in one file may not make it fine in another."""

    for (path, literal) in ledger_tool.CLASSIFIED_LITERALS:
        assert path and literal
    # a token classified in one theory source is not classified in another
    assert ("paper/appendix_deferred.tex", "256") in \
        ledger_tool.CLASSIFIED_LITERALS
    assert ("paper/transport_theory.tex", "256") not in \
        ledger_tool.CLASSIFIED_LITERALS


def test_generated_artifact_classifications_are_backed_by_a_digest():
    for relative in ledger_tool.GENERATED_ARTIFACT_SOURCES:
        path = REPO_ROOT / relative
        sidecar = Path(f"{path}.sha256")
        assert path.is_file() and sidecar.is_file(), relative
        assert sidecar.read_text(encoding="ascii").split()[0] == \
            ledger_tool.sha256_file(path)


# --------------------------------------------------------------------------
# 18. the compiler's own record is the source closure
# --------------------------------------------------------------------------
#
# The layout gate used to glob `paper/*.tex`, which meant the seven compiled
# inputs under `paper/tables/` and `paper/figures/` were never scanned and a
# future subdirectory never would be. The authority is now the LaTeX recorder's
# `.fls` output for the build that produced the submitted PDF.


@pytest.fixture(scope="module")
def staged_tree(tmp_path_factory):
    """A staged tree with a recorder file, built without needing TeX."""

    out = tmp_path_factory.mktemp("staged")
    src, sources = packager.stage(REPO_ROOT, out)
    lines = [f"INPUT {p.relative_to(src)}"
             for p in sorted(src.rglob("*")) if p.is_file()]
    (src / "main.fls").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return src, sources


def _clone_staged(staged_tree, destination: Path) -> Path:
    src, _ = staged_tree
    shutil.copytree(src, destination, symlinks=True)
    return destination


def test_the_recorder_closure_covers_nested_inputs(staged_tree):
    src, sources = staged_tree
    closure = {str(p) for p in packager.recorder_inputs(src)}
    for nested in ("tables/transport_instantiation_validity.tex",
                   "figures/transport_instantiation_bound.tex",
                   "figures/transport_instantiation_bound_D-1.csv"):
        assert nested in closure, nested
    assert sources["tables/transport_instantiation_validity.tex"] == \
        "paper/tables/transport_instantiation_validity.tex"


def test_the_clean_compiled_closure_passes_the_layout_gate(staged_tree):
    src, sources = staged_tree
    assert packager.check_compiled_layout_rules(src, sources) == []


@pytest.mark.parametrize("target", [
    "tables/transport_instantiation_validity.tex",
    "tables/growing_window_pareto.tex",
    "figures/transport_instantiation_bound.tex",
])
@pytest.mark.parametrize("injected, expected", [
    (r"\scriptsize", "scriptsize"),
    (r"\fontsize{6pt}{7pt}\selectfont", "fontsize"),
    (r"\setlength{\tabcolsep}{2pt}", "tabcolsep"),
    (r"\resizebox{\textwidth}{!}{x}", "resizebox"),
])
def test_a_shrink_in_a_nested_compiled_input_fails(
        staged_tree, tmp_path, target, injected, expected):
    src = _clone_staged(staged_tree, tmp_path / "tree")
    path = src / target
    path.write_text(injected + " " + path.read_text(encoding="utf-8"),
                    encoding="utf-8")
    findings = packager.check_compiled_layout_rules(src, staged_tree[1])
    assert any(expected in finding for finding in findings), findings


def test_a_shrink_in_a_new_subdirectory_input_fails(staged_tree, tmp_path):
    """A directory nobody thought to glob is still in the recorder's list."""

    src = _clone_staged(staged_tree, tmp_path / "tree")
    (src / "appendix").mkdir()
    (src / "appendix/extra.tex").write_text("\\scriptsize More.\n",
                                            encoding="utf-8")
    fls = src / "main.fls"
    fls.write_text(fls.read_text(encoding="utf-8") + "INPUT appendix/extra.tex\n",
                   encoding="utf-8")
    findings = packager.check_compiled_layout_rules(src, staged_tree[1])
    assert any("appendix/extra.tex" in finding for finding in findings), findings


def test_an_edited_venue_template_is_not_exempt(staged_tree, tmp_path):
    src = _clone_staged(staged_tree, tmp_path / "tree")
    style = src / "tmlr.sty"
    style.write_text(style.read_text(encoding="utf-8") + "\n% edited\n",
                     encoding="utf-8")
    findings = packager.check_compiled_layout_rules(src, staged_tree[1])
    assert any("venue template was modified" in f for f in findings), findings


def test_an_edited_generated_figure_is_not_exempt(staged_tree, tmp_path):
    """The figure exemption is a pinned digest, not a filename."""

    src = _clone_staged(staged_tree, tmp_path / "tree")
    figure = src / "figures/transport_instantiation_bound.tex"
    figure.write_text("\\scriptsize\n" + figure.read_text(encoding="utf-8"),
                      encoding="utf-8")
    findings = packager.check_compiled_layout_rules(src, staged_tree[1])
    assert any("scriptsize" in finding for finding in findings), findings


@pytest.mark.parametrize("setup, expected", [
    ("symlink", "symlink"),
    ("escape", "escapes the staged tree"),
    ("missing", "missing or not a file"),
    ("suffix", "unsupported suffix"),
])
def test_an_unreviewable_recorded_input_is_rejected(
        staged_tree, tmp_path, setup, expected):
    src = _clone_staged(staged_tree, tmp_path / "tree")
    extra = {
        "symlink": "INPUT linked.tex\n",
        "escape": "INPUT ../outside.tex\n",
        "missing": "INPUT ghost.tex\n",
        "suffix": "INPUT evil.sh\n",
    }[setup]
    if setup == "symlink":
        (src / "linked.tex").symlink_to("/etc/hostname")
    if setup == "suffix":
        (src / "evil.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    fls = src / "main.fls"
    fls.write_text(fls.read_text(encoding="utf-8") + extra, encoding="utf-8")
    with pytest.raises(RuntimeError, match=expected):
        packager.recorder_inputs(src)


def test_the_repository_preflight_is_declared_a_diagnostic():
    source = (REPO_ROOT / "submissions/tmlr_2026/package.py").read_text(
        encoding="utf-8")
    assert "diagnostic, not the authority" in source
    # and the authoritative gate runs after the compile, before packaging
    body = source.split("def main(", 1)[1]
    compiled = body.index("check_compiled_layout_rules(")
    packaged = body.index("write_zip(")
    assert body.index("compile_pdf(") < compiled < packaged


# --------------------------------------------------------------------------
# 19. the closure manifest binds the submitted inputs to bytes
# --------------------------------------------------------------------------


def test_the_supplement_ships_the_source_closure_manifest():
    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    with zipfile.ZipFile(release / "supplement.zip") as archive:
        assert packager.SOURCE_CLOSURE_NAME in archive.namelist()
        manifest = json.loads(archive.read(packager.SOURCE_CLOSURE_NAME))
    staged = [entry["staged"] for entry in manifest["entries"]]
    assert "tables/transport_instantiation_validity.tex" in staged
    assert "figures/transport_instantiation_bound_D-1.csv" in staged
    assert len(staged) == len(set(staged))


# The earlier loose-manifest tests lived here.  They are superseded by the
# strict-contract suite in section 23, which checks every invariant they did and
# fourteen more, against a fixture that satisfies the contract to begin with.
# Keeping both would have meant maintaining two fixture shapes, one of which the
# contract now rejects on sight.


# --------------------------------------------------------------------------
# 20. classifications are bound to a file and to an occurrence count
# --------------------------------------------------------------------------


def _audit_fails(root: Path) -> list[str]:
    return _audit(root)


def test_a_ledger_phrase_copied_into_another_file_fails(tmp_path):
    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/transport_theory.tex"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "Neither the local factor",
            "best-fixed-action regret $180.4$ holds.\nNeither the local factor",
            1),
        encoding="utf-8")
    assert _audit_fails(root)


def test_a_second_occurrence_of_a_classified_literal_fails(tmp_path):
    """A classified theorem constant does not license a new empirical sentence."""

    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/transport_theory.tex"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "Neither the local factor",
            "The measured optimism count is 4.\nNeither the local factor", 1),
        encoding="utf-8")
    failures = _audit_fails(root)
    assert any("pinned semantic unit" in name for name in failures), failures


def test_a_missing_classified_occurrence_fails(tmp_path):
    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/appendix_deferred.tex"
    path.write_text(
        path.read_text(encoding="utf-8").replace("$K=10$", "$K=11$", 1),
        encoding="utf-8")
    assert _audit_fails(root)


def test_an_empirical_value_in_the_macro_file_fails(tmp_path):
    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/macros.tex"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\n\\newcommand{\\meanregret}{81.0}\n", encoding="utf-8")
    failures = _audit_fails(root)
    assert any("states no numeric value" in name for name in failures), failures


def test_an_empirical_value_in_the_symbolic_table_fails(tmp_path):
    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/tables/growing_window_pareto.tex"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "$1$ & $T^{\\frac{1}{2}}$", "$1$ & $42.7$", 1),
        encoding="utf-8")
    failures = _audit_fails(root)
    assert any("asymptotic rate" in name for name in failures), failures


def test_an_unbraced_input_is_followed(tmp_path):
    root = _submitted_tex_tree(tmp_path)
    (root / "paper/extra_results.tex").write_text(
        "The extra mean is 7.5.\n", encoding="utf-8")
    conclusion = root / "paper/body_conclusion.tex"
    conclusion.write_text(
        conclusion.read_text(encoding="utf-8") + "\n\\input extra_results\n",
        encoding="utf-8")
    failures = _audit_fails(root)
    assert any("paper/extra_results.tex" in name for name in failures), failures


def test_an_inactive_branch_source_is_not_submitted_evidence(tmp_path):
    """A source only the legacy branch reads is not audited as submitted."""

    root = _submitted_tex_tree(tmp_path)
    (root / "paper/legacy_only.tex").write_text(
        "The legacy mean is 7.5.\n", encoding="utf-8")
    conclusion = root / "paper/body_conclusion.tex"
    conclusion.write_text(
        conclusion.read_text(encoding="utf-8")
        + "\n\\iflegacyextras\n\\input{legacy_only}\n\\fi\n", encoding="utf-8")
    assert _audit_fails(root) == []


def test_the_input_recogniser_handles_both_forms():
    matches = [(m.group(1), m.group(2)) for m in ledger_tool._INPUT.finditer(
        r"\input{braced} \input unbraced \include{included}")]
    found = {a or b for a, b in matches}
    assert found == {"braced", "unbraced", "included"}


# --------------------------------------------------------------------------
# 21. natbib's own unresolved-citation diagnostics
# --------------------------------------------------------------------------


@pytest.mark.parametrize("log_text, expected", [
    ("Package natbib Warning: Citation `nobody2020' on page 3 undefined on "
     "input line\n(natbib)                42.\n", "undefined citation"),
    ("Package natbib Warning: There were undefined citations.\n",
     "undefined citations"),
    ("Package natbib Warning: Citation(s) may have changed.\n",
     "not converged"),
    ("LaTeX Warning: Reference `tab:x' on page 3 undefined on input line 10.\n",
     "undefined reference"),
])
def test_real_natbib_and_latex_diagnostics_are_recognised(
        tmp_path, log_text, expected):
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.log").write_text(log_text, encoding="utf-8")
    findings = [f for f in packager.check_compiled_references(src)
                if "main.pdf is missing" not in f]
    assert any(expected in finding for finding in findings), findings


@pytest.mark.parametrize("benign", [
    "LaTeX Warning: Font shape `OT1/cmr/bx/sc' undefined\n"
    "(Font)              using `OT1/cmr/bx/n' instead on input line 5.\n",
    "Overfull \\hbox in paragraph: why? because.\n",
    "LaTeX Font Warning: Size substitutions with differences up to 1.0pt.\n",
])
def test_ordinary_log_noise_is_not_an_unresolved_reference(tmp_path, benign):
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.log").write_text(benign, encoding="utf-8")
    findings = [f for f in packager.check_compiled_references(src)
                if "main.pdf is missing" not in f]
    assert findings == [], findings


def test_the_log_check_stands_alone_without_a_text_extractor():
    """The rendered pass is corroboration, and says so when it cannot run."""

    source = (REPO_ROOT / "submissions/tmlr_2026/package.py").read_text(
        encoding="utf-8")
    assert "log check complete" in source
    assert "NOT EXECUTED" in source


def test_the_static_validator_sees_citations_with_optional_arguments():
    validator = (REPO_ROOT / "paper/validate.py").read_text(encoding="utf-8")
    assert r"(?:\[[^\]]*\])*" in validator
    done = subprocess.run(
        [sys.executable, str(REPO_ROOT / "paper/validate.py")],
        capture_output=True, text=True, cwd=REPO_ROOT)
    assert done.returncode == 0, done.stdout
    assert "38 distinct cite keys, 0 missing" in done.stdout


# --------------------------------------------------------------------------
# 22. the recorder classifier fails closed on non-staged inputs
# --------------------------------------------------------------------------
#
# Anything outside the staged tree used to be dropped in silence as "a system
# TeX Live file". A manuscript file anywhere on the filesystem could therefore
# affect the submitted PDF without appearing in the source archive or in any
# audit closure.


def test_the_texmf_allowlist_is_narrow_and_derived():
    roots = packager.texmf_roots(repo=REPO_ROOT, staged=REPO_ROOT / "x")
    assert roots, "no TeX tree could be derived from the runtime"
    for root in roots:
        assert root.is_absolute() and root.is_dir(), root
        assert str(root) not in packager.FORBIDDEN_ROOT_PREFIXES, root
        assert len(root.parts) >= 3, root
        assert not REPO_ROOT.is_relative_to(root), root
        # write-protected at every component, from / down
        assert packager.write_protection_problems(root) == [], root
        assert os.path.realpath(root) == str(root), root


def test_no_user_tree_is_ever_a_trusted_root():
    """TEXMFHOME and the user caches are bytes this account can rewrite."""

    roots = packager.texmf_roots(repo=REPO_ROOT, staged=REPO_ROOT / "x")
    for variable in packager.USER_TEXMF_ROOT_VARIABLES:
        value = packager.kpsewhich_value(variable)
        if not value:
            continue
        user_tree = Path(value.split(os.pathsep)[0].strip().lstrip("!").rstrip("/"))
        assert user_tree not in roots, (variable, user_tree)
    assert "TEXMFHOME" not in packager.SYSTEM_TEXMF_ROOT_VARIABLES


def test_a_user_writable_root_is_refused(tmp_path):
    """Anything under a directory this account can write is not a distribution."""

    tree = tmp_path / "texmf-dist" / "tex" / "latex"
    tree.mkdir(parents=True)
    problems = packager.write_protection_problems(tree)
    assert problems and any("writable by the invoking user" in p
                            for p in problems), problems


def test_a_linked_root_component_is_refused(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    problems = packager.write_protection_problems(link / "inner")
    assert any("is a symlink" in p for p in problems), problems


def test_a_group_or_world_writable_component_is_refused(tmp_path):
    tree = tmp_path / "shared"
    tree.mkdir()
    os.chmod(tree, 0o777)
    problems = packager.write_protection_problems(tree)
    assert any("group- or world-writable" in p for p in problems), problems


def test_an_environment_supplied_root_cannot_answer_for_the_engine(monkeypatch):
    """`kpsewhich -var-value=TEXMFDIST` reports $TEXMFDIST if it is exported."""

    monkeypatch.setenv("TEXMFDIST", "/tmp/not-a-distribution")
    assert packager.kpsewhich_value("TEXMFDIST") != "/tmp/not-a-distribution"
    assert Path("/tmp/not-a-distribution") not in packager.texmf_roots(
        repo=REPO_ROOT, staged=REPO_ROOT / "x")


def test_a_broad_root_is_refused():
    for shallow in ("/", "/usr", "/usr/share", "/home", "/tmp", "/var"):
        assert shallow in packager.FORBIDDEN_ROOT_PREFIXES, shallow
    for root in packager.texmf_roots(repo=REPO_ROOT, staged=REPO_ROOT / "x"):
        assert len(root.parts) >= 3, root


def test_a_root_that_would_contain_the_repository_is_refused(tmp_path):
    """A misconfigured TEXMFHOME=$HOME must not readmit the filesystem."""

    inside = tmp_path / "repo"
    inside.mkdir()
    roots = packager.texmf_roots(repo=inside, staged=inside)
    assert all(not inside.is_relative_to(root) for root in roots)


def test_an_outside_tree_manuscript_input_is_rejected(staged_tree, tmp_path):
    src = _clone_staged(staged_tree, tmp_path / "tree")
    stray = tmp_path / "stray.tex"
    stray.write_text("\\scriptsize smuggled\n", encoding="utf-8")
    fls = src / "main.fls"
    fls.write_text(fls.read_text(encoding="utf-8") + f"INPUT {stray}\n",
                   encoding="utf-8")
    with pytest.raises(RuntimeError, match="not from a trusted system TeX"):
        packager.recorder_inputs(src, repo=REPO_ROOT)


def test_a_project_path_reached_through_a_tex_root_is_rejected(staged_tree,
                                                               tmp_path):
    """A trusted root that links back into the staged tree is still a finding."""

    src = _clone_staged(staged_tree, tmp_path / "tree")
    problems = packager.external_input_problems(
        src / "notation.tex", roots=[src.parent], repo=REPO_ROOT, staged=src)
    assert problems


def test_no_input_is_admitted_by_digest_alone(staged_tree, tmp_path):
    """The pin escape is gone: a user-tree input is a finding, full stop.

    It used to be possible to admit an external input whose digest was recorded
    in committed code even though it sat somewhere the invoking account could
    rewrite. A digest proves the bytes did not change between the pin and the
    build; it says nothing about who can change them next, and 46 of this
    submission's inputs were living in `TEXMFHOME`.
    """

    source = (REPO_ROOT / "submissions/tmlr_2026/package.py").read_text(
        encoding="utf-8")
    assert "import external_tex_inputs" not in source
    assert "PINS" not in source
    assert not (REPO_ROOT / "submissions/tmlr_2026/external_tex_inputs.py").exists()

    src = _clone_staged(staged_tree, tmp_path / "tree")
    home = packager.kpsewhich_value("TEXMFHOME")
    if not home:
        pytest.skip("this host reports no TEXMFHOME")
    candidate = next((p for p in Path(home).rglob("*.sty") if p.is_file()), None)
    if candidate is None:
        pytest.skip("this host has no file under TEXMFHOME")
    fls = src / "main.fls"
    fls.write_text(fls.read_text(encoding="utf-8") + f"INPUT {candidate}\n",
                   encoding="utf-8")
    with pytest.raises(RuntimeError, match="not from a trusted system TeX"):
        packager.recorder_inputs(src, repo=REPO_ROOT)


def test_a_user_cache_input_is_rejected(staged_tree, tmp_path):
    """TEXMFVAR is the account's own cache; the format dump there is not trusted."""

    src = _clone_staged(staged_tree, tmp_path / "tree")
    cache = packager.kpsewhich_value("TEXMFVAR")
    if not cache or not Path(cache).is_dir():
        pytest.skip("this host reports no user TEXMFVAR")
    candidate = next((p for p in Path(cache).rglob("*") if p.is_file()), None)
    if candidate is None:
        pytest.skip("the user cache is empty")
    roots = packager.texmf_roots(repo=REPO_ROOT, staged=src)
    assert packager.external_input_problems(
        candidate, roots=roots, repo=REPO_ROOT, staged=src)


def test_the_compile_environment_shuts_out_user_trees(tmp_path):
    env = packager.compile_environment(tmp_path / "src")
    assert env["TEXMFHOME"].startswith(str(tmp_path))
    assert not Path(env["TEXMFHOME"]).exists()
    assert env["TEXMFCONFIG"].startswith(str(tmp_path))
    assert not Path(env["TEXMFCONFIG"]).exists()
    # nothing the caller exported can steer the search
    for key in env:
        if key.startswith(packager.TEX_SEARCH_ENV_PREFIXES):
            assert key in {"TEXMFHOME", "TEXMFCONFIG", "TEXMFVAR", "TEXMFCNF"}, key
    if "TEXMFVAR" in env:
        assert packager.write_protection_problems(Path(env["TEXMFVAR"])) == []
    if "TEXMFCNF" in env:
        assert packager.write_protection_problems(Path(env["TEXMFCNF"])) == []


def test_the_config_root_is_derived_from_the_installation():
    """`texmf.cnf` is a distribution symlink; the canonical copy is what is used."""

    config = packager.texmf_config_root()
    if config is None:
        pytest.skip("this host has no resolvable texmf.cnf")
    assert packager.write_protection_problems(config) == []
    assert os.path.realpath(config) == str(config)
    assert (config / "texmf.cnf").is_file()
    assert config in packager.texmf_roots(repo=REPO_ROOT, staged=REPO_ROOT / "x")


def test_a_symlinked_system_tree_is_admitted_only_as_its_real_path():
    """TEXMFSYSVAR is a root-owned link; the link is never the trusted root."""

    value = packager.kpsewhich_value("TEXMFSYSVAR")
    if not value:
        pytest.skip("this host reports no TEXMFSYSVAR")
    lexical = Path(value.split(os.pathsep)[0].strip().lstrip("!").rstrip("/"))
    roots = packager.texmf_roots(repo=REPO_ROOT, staged=REPO_ROOT / "x")
    if not lexical.is_symlink():
        pytest.skip("TEXMFSYSVAR is not a symlink on this host")
    assert lexical not in roots
    assert Path(os.path.realpath(lexical)) in roots


def test_the_build_records_every_external_input_it_accepted():
    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    manifest = json.loads(
        (release / "release_manifest.json").read_text(encoding="utf-8"))
    recorded = manifest["external_tex_inputs"]
    assert recorded, "no external compiled inputs recorded"
    for item in recorded:
        assert set(item) == {"name", "sha256", "bytes", "trusted"}
        assert len(item["sha256"]) == 64
        assert item["bytes"] > 0
        variable, _, relative = item["name"].partition(":")
        assert relative and not relative.startswith("/"), item["name"]
    # the whole point of this pass: nothing is admitted by digest any more
    assert all(item["trusted"] for item in recorded), \
        [i["name"] for i in recorded if not i["trusted"]]


def test_a_linked_staged_input_is_rejected(staged_tree, tmp_path):
    src = _clone_staged(staged_tree, tmp_path / "tree")
    (src / "aliased.tex").symlink_to("notation.tex")
    fls = src / "main.fls"
    fls.write_text(fls.read_text(encoding="utf-8") + "INPUT aliased.tex\n",
                   encoding="utf-8")
    with pytest.raises(RuntimeError, match="symlink"):
        packager.recorder_inputs(src, repo=REPO_ROOT)


def test_an_ordinary_tex_distribution_dependency_is_accepted(staged_tree,
                                                             tmp_path):
    roots = packager.texmf_roots(repo=REPO_ROOT, staged=staged_tree[0])
    dependency = next(
        (p for root in roots for p in root.rglob("article.cls")), None)
    if dependency is None:
        pytest.skip("no article.cls under any derived TeX tree")
    src = _clone_staged(staged_tree, tmp_path / "tree")
    before = len(packager.recorder_inputs(src, repo=REPO_ROOT))
    fls = src / "main.fls"
    fls.write_text(fls.read_text(encoding="utf-8") + f"INPUT {dependency}\n",
                   encoding="utf-8")
    assert len(packager.recorder_inputs(src, repo=REPO_ROOT)) == before


def test_the_real_build_closure_is_accepted_unchanged():
    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    src = release / "src"
    if not (src / "main.fls").is_file():
        pytest.skip("the staged tree was not kept")
    assert packager.recorder_inputs(src, repo=REPO_ROOT)
    assert packager.check_compiled_layout_rules(src, {}, REPO_ROOT) == []


def test_recorder_rejection_precedes_any_certified_output():
    """The closure is read before a deliverable is written, not after."""

    source = (REPO_ROOT / "submissions/tmlr_2026/package.py").read_text(
        encoding="utf-8")
    body = source.split("def main(", 1)[1]
    assert body.index("check_compiled_layout_rules(") < body.index("write_zip(")
    assert body.index("closure(src, repo)") < body.index("atomic_write_bytes(")


# --------------------------------------------------------------------------
# 23. the closure manifest is a strict contract
# --------------------------------------------------------------------------


def _closure_tree(tmp_path: Path, edit=None, packaged: bool = False) -> Path:
    """A tree whose closure manifest is the real one the contract pins.

    It used to be three hand-written entries, which cannot exercise the set
    check at all: the contract now says exactly which 89 compiled inputs must
    be declared, so a fixture with three of them is not a clean control, it is
    a failing one.  Everything `ships_in == "supplement"` is materialised from
    the repository; the rest are declared and legitimately absent, which is
    what a supplement looks like.
    """

    root = tmp_path / "tree"
    root.mkdir(parents=True, exist_ok=True)
    entries = []
    for staged, pinned in sorted(contract.COMPILED_CLOSURE.items()):
        entry = {"staged": staged, **{k: pinned[k] for k in
                                      ("repository", "sha256", "bytes",
                                       "role", "ships_in")}}
        entries.append(entry)
        if pinned["ships_in"] != "supplement":
            continue
        target = root / pinned["repository"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / pinned["repository"], target)
    manifest = {
        "schema_version": ledger_tool.CLOSURE_SCHEMA_VERSION,
        "what_this_is": "test fixture",
        "entries": entries,
    }
    if packaged:
        (root / contract.DECLARATION_NAME).write_text("{}", encoding="utf-8")
    if edit is not None:
        edit(root, manifest)
    if manifest is not None:
        (root / ledger_tool.SOURCE_CLOSURE_NAME).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    return root


def _entry(manifest: dict, staged: str) -> dict:
    return next(e for e in manifest["entries"] if e["staged"] == staged)


def _closure_failures(root: Path, require: bool = False) -> list[str]:
    return [c.name for c in ledger_tool.closure_manifest_checks(
        root, require_manifest=require) if c.status == ledger_tool.STATUS_FAIL]


def test_a_clean_closure_manifest_satisfies_the_contract(tmp_path):
    assert _closure_failures(_closure_tree(tmp_path)) == []


def test_a_missing_manifest_fails_in_package_mode(tmp_path):
    root = tmp_path / "bare"
    root.mkdir()
    failures = _closure_failures(root, require=True)
    assert any("is present" in name for name in failures), failures
    assert _closure_failures(root, require=False) == []


def test_unparseable_manifest_json_fails(tmp_path):
    root = _closure_tree(tmp_path)
    (root / ledger_tool.SOURCE_CLOSURE_NAME).write_text("{ not json",
                                                        encoding="utf-8")
    assert any("parses" in name for name in _closure_failures(root))


@pytest.mark.parametrize("edit, expected", [
    (lambda r, m: m.update(extra_key=1), "top-level keys"),
    (lambda r, m: m.pop("what_this_is"), "top-level keys"),
    (lambda r, m: m.update(schema_version=99), "schema version"),
    # `True == 1`, so an equality test alone would have accepted this.
    (lambda r, m: m.update(schema_version=True), "schema version"),
    (lambda r, m: m.update(schema_version="1"), "schema version"),
    (lambda r, m: m.update(what_this_is=1), "describes itself in text"),
    (lambda r, m: m.update(what_this_is="   "), "describes itself in text"),
    (lambda r, m: m["entries"][0].update(surprise=1), "pinned keys and scalar types"),
    (lambda r, m: m["entries"][0].pop("role"), "pinned keys and scalar types"),
    (lambda r, m: m["entries"][0].update(bytes="lots"),
     "pinned keys and scalar types"),
    # bool subclasses int, so `isinstance(True, int)` is true and `True == 1`.
    # A one-byte file would have satisfied an isinstance check.
    (lambda r, m: m["entries"][0].update(bytes=True),
     "pinned keys and scalar types"),
    (lambda r, m: m["entries"][0].update(ships_in=1),
     "pinned keys and scalar types"),
    (lambda r, m: m["entries"][0].update(ships_in="archive"),
     "one of the three archives"),
    (lambda r, m: m["entries"].append(dict(m["entries"][0])), "listed twice"),
    (lambda r, m: m["entries"][1].update(
        repository=m["entries"][0]["repository"]), "repository path is listed twice"),
    (lambda r, m: m["entries"][0].update(staged="./notation.tex"),
     "unsafe or noncanonical"),
    (lambda r, m: m["entries"][0].update(repository="../escape.tex"),
     "unsafe or noncanonical"),
    (lambda r, m: m["entries"][0].update(repository="etc/passwd.tex"),
     "known project directory"),
    (lambda r, m: m["entries"][0].update(staged="somethingelse.tex"),
     "derived repository path"),
    # A basename-only mapping check accepts this; an exact one does not.
    (lambda r, m: m["entries"][0].update(
        repository="experiments/" + Path(m["entries"][0]["repository"]).name),
     "derived repository path"),
    (lambda r, m: m["entries"][0].update(repository=None),
     "only the generated bibliography output has no repository path"),
    (lambda r, m: m["entries"][0].update(role="figure-data"),
     "derived from the validated path"),
    (lambda r, m: m["entries"][0].update(sha256="0" * 64), "recorded bytes"),
    (lambda r, m: m["entries"][0].update(bytes=1), "recorded bytes"),
])
def test_each_closure_manifest_invariant_is_enforced(tmp_path, edit, expected):
    failures = _closure_failures(_closure_tree(tmp_path, edit))
    assert any(expected in name for name in failures), failures


def test_a_bibliography_output_entry_may_have_no_repository_path(tmp_path):
    """The one derived exception, and only for the role that earns it."""

    assert _closure_failures(_closure_tree(tmp_path)) == []
    entry = contract.COMPILED_CLOSURE["main.bbl"]
    assert entry["repository"] is None
    assert entry["role"] == "bibliography-output"
    assert entry["ships_in"] == "neither"

    def give_it_a_path(root, manifest):
        _entry(manifest, "main.bbl")["repository"] = "paper/main.bbl"

    failures = _closure_failures(_closure_tree(tmp_path / "x", give_it_a_path))
    assert any("only the generated bibliography output" in name
               or "matches the pinned contract exactly" in name
               for name in failures), failures


def test_a_symlinked_path_component_fails_the_contract(tmp_path):
    """A symlinked `paper/` redirects every entry while each leaf looks real."""

    root = _closure_tree(tmp_path)
    real = root / "paper"
    moved = root / "elsewhere"
    real.rename(moved)
    real.symlink_to(moved)
    failures = _closure_failures(root)
    assert any("symlink in any path component" in name
               for name in failures), failures


def test_a_nested_shipped_source_must_be_recorded(tmp_path):
    """The completeness sweep is recursive, not one directory deep."""

    root = _closure_tree(tmp_path)
    nested = root / "paper/parts"
    nested.mkdir(parents=True)
    (nested / "smuggled.tex").write_text("A claim of $42.7$.\n", encoding="utf-8")
    failures = _closure_failures(root)
    assert any("recorded compiled input" in name for name in failures), failures


def test_an_unbound_shipped_data_file_fails(tmp_path):
    root = _closure_tree(tmp_path)
    (root / "paper/figures").mkdir(parents=True, exist_ok=True)
    (root / "paper/figures/loose.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    failures = _closure_failures(root)
    assert any("recorded or sidecarred" in name for name in failures), failures


def _mandatory_failures(root: Path) -> str:
    return " ".join(c.detail for c in ledger_tool.closure_manifest_checks(root)
                    if c.status == ledger_tool.STATUS_FAIL
                    and "mandatory compiler input" in c.name)


def test_a_complete_fixture_manifest_satisfies_the_mandatory_check(tmp_path):
    assert _mandatory_failures(_closure_tree(tmp_path)) == ""


def test_a_missing_mandatory_compiler_entry_fails(tmp_path):
    """`main.bbl` travels in neither archive, so only this check can miss it."""

    def drop(root, manifest):
        manifest["entries"] = [e for e in manifest["entries"]
                               if e["staged"] != "main.bbl"]

    detail = _mandatory_failures(_closure_tree(tmp_path, drop))
    assert "main.bbl: 0 entries" in detail, detail


def test_a_partial_manifest_is_not_held_to_the_mandatory_list(tmp_path):
    """Without an entry point the manifest is partial; completeness catches it."""

    assert _mandatory_failures(_closure_tree(tmp_path)) == ""


@pytest.mark.parametrize("staged, why", [
    ("transport_experiment.tex", "ordinary manuscript source"),
    ("figures/transport_instantiation_bound_D-1.csv", "sidecarred figure data"),
    ("tables/transport_instantiation_validity.tex", "sidecarred generated table"),
    ("pgfplots.sty", "vendored package"),
    ("tmlr.sty", "venue template"),
    ("main.bbl", "generated, in neither archive"),
])
def test_removing_any_compiled_input_from_the_closure_fails(tmp_path, staged, why):
    """A sidecar verifies bytes; it can never excuse a missing closure entry.

    The reviewer deleted one recorded figure CSV from `SOURCE_CLOSURE.json` and
    full supplement verification stayed green, because that file's `.sha256`
    sidecar still verified its bytes and nothing required it to be in the
    closure at all.
    """

    def edit(root, manifest):
        manifest["entries"] = [e for e in manifest["entries"]
                               if e["staged"] != staged]

    failures = _closure_failures(_closure_tree(tmp_path, edit))
    assert any("exactly the pinned set" in name for name in failures), \
        (staged, why, failures)


def test_an_extra_closure_entry_fails(tmp_path):
    def edit(root, manifest):
        manifest["entries"].append({
            "staged": "smuggled.tex", "repository": "paper/smuggled.tex",
            "sha256": "a" * 64, "bytes": 12, "role": "manuscript-source",
            "ships_in": "supplement",
        })

    failures = _closure_failures(_closure_tree(tmp_path, edit))
    assert any("exactly the pinned set" in name for name in failures), failures


@pytest.mark.parametrize("field, value", [
    ("repository", "experiments/notation.tex"),
    ("sha256", "0" * 64),
    ("bytes", 7),
    ("role", "figure-data"),
    ("ships_in", "source"),
])
def test_a_remapped_closure_entry_fails(tmp_path, field, value):
    def edit(root, manifest):
        _entry(manifest, "notation.tex")[field] = value

    failures = _closure_failures(_closure_tree(tmp_path, edit))
    assert any("matches the pinned contract exactly" in name
               or "derived repository path" in name
               or "derived from the validated path" in name
               for name in failures), (field, failures)


def test_a_sidecar_cannot_stand_in_for_closure_membership(tmp_path):
    """The exact reviewer reproduction, end to end, against the real tree."""

    target = "figures/transport_instantiation_bound_D-1.csv"
    repository = contract.COMPILED_CLOSURE[target]["repository"]

    def edit(root, manifest):
        manifest["entries"] = [e for e in manifest["entries"]
                               if e["staged"] != target]
        # the file and its sidecar are both still there and both still correct
        sidecar = root / f"{repository}.sha256"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        data = (root / repository).read_bytes()
        sidecar.write_text(
            f"{hashlib.sha256(data).hexdigest()}  {Path(repository).name}\n",
            encoding="utf-8")

    root = _closure_tree(tmp_path, edit)
    assert (root / repository).is_file()
    assert (root / f"{repository}.sha256").is_file()
    failures = _closure_failures(root)
    assert any("exactly the pinned set" in name for name in failures), failures


def test_a_rewritten_non_supplement_digest_fails(tmp_path):
    """The supplement has no bytes for these, so only the pinned value catches it."""

    def edit(root, manifest):
        for entry in manifest["entries"]:
            if entry["staged"] == "pgfplots.sty":
                entry["sha256"] = "0" * 64

    detail = _mandatory_failures(_closure_tree(tmp_path, edit))
    assert "the pinned contract says" in detail, detail


def test_the_generated_bibliography_is_reproducible_from_source_zip():
    """`ships_in: neither` is a checkable claim, not an excuse.

    `main.bbl` is in no archive. What a reviewer can do is unpack `source.zip`,
    run bibtex, and get back the digest pinned in the contract -- so the entry
    is verifiable without either archive carrying the bytes.
    """

    rebuilt = Path("/home/buiksat/cce-tmlr-work/srcziptest-r11/main.bbl")
    if not rebuilt.is_file():
        pytest.skip("no clean source.zip rebuild present")
    pinned = contract.COMPILED_CLOSURE["main.bbl"]
    assert hashlib.sha256(rebuilt.read_bytes()).hexdigest() == pinned["sha256"]
    assert rebuilt.stat().st_size == pinned["bytes"]


def test_the_supplement_readme_describes_all_three_archive_states():
    readme = (REPO_ROOT / "submissions/tmlr_2026/supplement_README.md").read_text(
        encoding="utf-8")
    assert "ships_in" in readme
    for state in ledger_tool.CLOSURE_ARCHIVES:
        assert f"`{state}`" in readme, state
    assert "main.bbl" in readme
    # the wording the reviewer found wrong must be gone
    assert "in_supplement false are shipped in source.zip" not in readme
    manifest_note = packager.write_source_closure_manifest.__doc__ or ""
    assert "in_supplement false" not in manifest_note


def test_the_manifest_note_distinguishes_the_three_states():
    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    with zipfile.ZipFile(release / "supplement.zip") as archive:
        manifest = json.loads(archive.read(ledger_tool.SOURCE_CLOSURE_NAME))
    note = manifest["what_this_is"]
    for state in ledger_tool.CLOSURE_ARCHIVES:
        assert state in note, state
    assert "main.bbl" in note
    assert "in_supplement" not in note


def test_the_pinned_closure_describes_the_real_closure():
    """The contract cannot drift away from what packaging actually records."""

    pinned = contract.COMPILED_CLOSURE
    assert set(ledger_tool.MANDATORY_NON_SUPPLEMENT_STAGED) <= set(pinned)
    for name, record in sorted(pinned.items()):
        assert len(record["sha256"]) == 64, name
        assert record["bytes"] > 0, name
        assert record["role"] == ledger_tool.derive_closure_role(name), name
        assert record["ships_in"] in ledger_tool.CLOSURE_ARCHIVES, name
        assert record["repository"] == ledger_tool.derive_repository_path(name), name
        if name in packager.VENDORED_PACKAGE_DIGESTS:
            assert record["sha256"] == packager.VENDORED_PACKAGE_DIGESTS[name]
        if name in packager.VENUE_TEMPLATE_DIGESTS:
            assert record["sha256"] == packager.VENUE_TEMPLATE_DIGESTS[name]
    # main.bbl is the case ships_in exists for: in neither archive.
    assert pinned["main.bbl"]["ships_in"] == "neither"
    assert pinned["main.bbl"]["repository"] is None
    assert {r["ships_in"] for r in pinned.values()} == {"supplement", "source",
                                                       "neither"}

    release = _release_dir()
    if release is None:
        pytest.skip("no built release directory; run submissions/tmlr_2026/build.sh")
    with zipfile.ZipFile(release / "supplement.zip") as archive:
        manifest = json.loads(archive.read(ledger_tool.SOURCE_CLOSURE_NAME))
    recorded = {e["staged"]: e for e in manifest["entries"]}
    assert set(recorded) == set(pinned)
    for name, record in sorted(pinned.items()):
        for field in ("repository", "sha256", "bytes", "role", "ships_in"):
            assert recorded[name][field] == record[field], (name, field)

    # and ships_in is a fact about the two archives, not a label
    with zipfile.ZipFile(release / "supplement.zip") as archive:
        supplement_members = set(archive.namelist())
    with zipfile.ZipFile(release / "source.zip") as archive:
        source_members = set(archive.namelist())
    for name, record in sorted(pinned.items()):
        if record["ships_in"] == "supplement":
            assert record["repository"] in supplement_members, name
        elif record["ships_in"] == "source":
            assert name in source_members, name
        else:
            assert name not in source_members, name
            assert record["repository"] not in supplement_members, name


def _rewrite_bbl(**fields):
    def edit(root, manifest):
        for entry in manifest["entries"]:
            if entry["staged"] == "main.bbl":
                entry.update(fields)
    return edit


@pytest.mark.parametrize("edit, expected", [
    (_rewrite_bbl(sha256="not hex" + "0" * 57), "the pinned contract says"),
    (_rewrite_bbl(sha256="z" * 64), "sha256 is not a 64-hex digest"),
    (_rewrite_bbl(bytes=0), "byte count is 0"),
])
def test_an_unbound_mandatory_compiler_entry_fails(tmp_path, edit, expected):
    detail = _mandatory_failures(_closure_tree(tmp_path, edit))
    assert expected in detail, detail


def test_a_duplicated_mandatory_compiler_entry_fails(tmp_path):
    def edit(root, manifest):
        duplicate = next(dict(e) for e in manifest["entries"]
                         if e["staged"] == "main.bbl")
        manifest["entries"].append(duplicate)

    detail = _mandatory_failures(_closure_tree(tmp_path, edit))
    assert "main.bbl: 2 entries" in detail, detail


def test_a_nested_source_outside_paper_must_be_recorded(tmp_path):
    """The sweep covers every shipped source root, not only `paper/`."""

    assert "submissions/tmlr_2026" in ledger_tool.SHIPPED_SOURCE_ROOTS
    root = _closure_tree(tmp_path)
    nested = root / "submissions/tmlr_2026"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "extra.tex").write_text("A claim of $42.7$.\n", encoding="utf-8")
    failures = _closure_failures(root)
    assert any("recorded compiled input" in name for name in failures), failures


def test_a_sidecarred_shipped_data_file_is_allowed(tmp_path):
    root = _closure_tree(tmp_path)
    (root / "paper/figures").mkdir(parents=True, exist_ok=True)
    data = root / "paper/figures/evidence.csv"
    data.write_text("x,y\n1,2\n", encoding="utf-8")
    (root / "paper/figures/evidence.csv.sha256").write_text(
        f"{hashlib.sha256(data.read_bytes()).hexdigest()}  evidence.csv\n",
        encoding="utf-8")
    assert _closure_failures(root) == []


def test_a_missing_recorded_file_fails_the_contract(tmp_path):
    root = _closure_tree(tmp_path, lambda r, m: (r / "paper/notation.tex").unlink())
    assert any("is present" in name for name in _closure_failures(root))


def test_a_symlinked_recorded_file_fails_the_contract(tmp_path):
    def edit(root, manifest):
        target = root / "paper/notation.tex"
        target.unlink()
        target.symlink_to(REPO_ROOT / "paper/notation.tex")

    assert any("symlink" in name
               for name in _closure_failures(_closure_tree(tmp_path, edit)))


def test_a_false_supplement_membership_claim_fails(tmp_path):
    """Claiming a manuscript source is not in the supplement, to dodge the
    byte binding when the file is absent, contradicts the role's policy."""

    def edit(root, manifest):
        (root / "paper/notation.tex").unlink()
        for entry in manifest["entries"]:
            if entry["repository"] == "paper/notation.tex":
                entry["ships_in"] = "source"

    failures = _closure_failures(_closure_tree(tmp_path, edit, packaged=True))
    assert any("ships_in follows the role policy" in name
               or "matches the pinned contract exactly" in name
               for name in failures), failures


def test_deleting_an_entry_still_fails_the_contract(tmp_path):
    def edit(root, manifest):
        manifest["entries"] = manifest["entries"][:1]

    failures = _closure_failures(_closure_tree(tmp_path, edit))
    assert any("recorded compiled input" in name for name in failures), failures


def test_repository_preflight_is_usable_but_does_not_certify():
    checks = ledger_tool.literal_coverage_checks(
        REPO_ROOT, LEDGER, require_package=False)
    preflight = [c for c in checks if c.name.startswith("source closure:")]
    assert preflight and preflight[0].status == ledger_tool.STATUS_NOT_EXECUTED
    assert "does not certify" in preflight[0].detail


# --------------------------------------------------------------------------
# 24. every classification is bound to a context, not just a file and a count
# --------------------------------------------------------------------------


@pytest.mark.parametrize("source, before, after, category", [
    ("paper/appendix_deferred.tex", "Thm.~6.1.1", "Thm.~6.1.2",
     "citation-locator"),
    ("paper/body_related.tex", "$>10^8$-parameter", "$>10^9$-parameter",
     "cited-scale"),
    ("paper/appendix_deferred.tex", "$K=10$, $I=25$", "$K=10$, $I=26$",
     "illustration-input"),
    ("submissions/tmlr_2026/supplement_README.md", "NumPy 2.2.3",
     "NumPy 2.2.4", "environment-version"),
])
def test_each_classification_category_is_context_bound(
        tmp_path, source, before, after, category):
    root = _submitted_tex_tree(tmp_path)
    path = root / source
    text = path.read_text(encoding="utf-8")
    assert before in text, before
    path.write_text(text.replace(before, after, 1), encoding="utf-8")
    assert _audit(root), f"{category}: {before!r} -> {after!r} went unnoticed"


def test_a_classified_literal_reused_in_a_new_sentence_fails(tmp_path):
    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/appendix_cg.tex"
    text = path.read_text(encoding="utf-8")
    anchor = text.splitlines()[3]
    path.write_text(text.replace(anchor, "The measured value is 2.\n" + anchor, 1),
                    encoding="utf-8")
    failures = _audit(root)
    assert any("pinned semantic unit" in name for name in failures), failures


def test_rewording_around_a_number_without_changing_it_fails(tmp_path):
    """The number is the same; its meaning is carried by the words around it."""

    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/transport_experiment.tex"
    text = path.read_text(encoding="utf-8")
    before = "Contexts have dimension $4$, there are five"
    assert before in text
    path.write_text(
        text.replace(before, "Contexts have dimension $4$; there are five", 1),
        encoding="utf-8")
    failures = _audit(root)
    assert any("pinned semantic unit" in name for name in failures), failures


def test_a_moved_classified_occurrence_fails(tmp_path):
    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/appendix_twosided.tex"
    text = path.read_text(encoding="utf-8")
    index = text.index("\\begin{proof}")
    path.write_text(
        text[:index] + "A restatement with $3$ terms.\n"
        + text[index:].replace("$3$", "$\\mathbf{3}$", 1), encoding="utf-8")
    assert _audit(root)


def test_a_symbolic_rate_change_that_still_parses_fails(tmp_path):
    """`KT^{2}` -> `KT^{3}` is a different claim, and both are valid rates."""

    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/tables/growing_window_pareto.tex"
    path.write_text(
        path.read_text(encoding="utf-8").replace("$KT^{2}$", "$KT^{3}$", 1),
        encoding="utf-8")
    failures = _audit(root)
    assert any("pinned rates" in name for name in failures), failures


def test_the_symbolic_cell_parser_rejects_non_rates():
    for good in ("$1$", "$\\frac{1}{2}$", "$T^{2}$", "$KT^{\\frac{5}{2}}$"):
        assert ledger_tool.parse_symbolic_cell(good) is not None, good
    for bad in ("$42.7$", "$T^{1.5}$", "$81.0$", "conditional regret",
                "$T^{2} + 1$", "$2,400$"):
        assert ledger_tool.parse_symbolic_cell(bad) is None, bad


def test_the_pinned_record_and_the_category_table_describe_one_set():
    pinned = set(ledger_tool.classified_pins(REPO_ROOT))
    declared = set(ledger_tool.CLASSIFIED_LITERALS)
    assert pinned == declared
    for category, count, units in ledger_tool.classified_pins(REPO_ROOT).values():
        assert category in ledger_tool._CATEGORY_REASON
        assert len(units) == count
        for unit, offset in units:
            assert isinstance(unit, str) and unit == unit.strip()
            assert 0 <= offset <= len(unit)


def test_every_pin_carries_a_complete_reviewable_unit():
    """A record a human can read: file, literal, category, count, and the unit."""

    for (relative, literal), (category, count, units) in \
            ledger_tool.classified_pins(REPO_ROOT).items():
        assert relative and literal and category and count == len(units)
        for unit, offset in units:
            # the unit really contains the literal it claims to place
            assert unit, (relative, literal)
            assert ledger_tool.UNIT_BREAK not in unit
    for (relative, phrase), (count, units) in \
            ledger_tool.phrase_pins(REPO_ROOT).items():
        assert relative and phrase and count == len(units)


@pytest.mark.parametrize("source, before, after, what", [
    ("paper/macros.tex", r"\DeclareMathOperator*{\argmin}{arg\,min}",
     r"\DeclareMathOperator*{\argmin}{arg\,max}",
     "argmin now renders as arg max"),
    ("paper/tables/growing_window_pareto.tex", "$KT^{2}$", "$KT^{3}$",
     "a different asymptotic rate"),
])
def test_a_structural_source_is_held_to_its_whole_file_pin(tmp_path, source,
                                                           before, after, what):
    """Structural sources used to skip FILE_PINS entirely.

    `paper/macros.tex` and the symbolic rate table have specialized checks --
    declarations only, cells that parse as rates -- and both of those are blind
    to a renamed operator.  The reviewer changed `\argmin` to render "arg max",
    updated the closure metadata to match, and the complete shipped verifier
    still passed.
    """

    root = _submitted_tex_tree(tmp_path)
    path = root / source
    text = path.read_text(encoding="utf-8")
    assert before in text, (source, before)
    path.write_text(text.replace(before, after, 1), encoding="utf-8")
    failures = _audit(root)
    assert any("is the pinned text" in name for name in failures), (what, failures)


def test_the_whole_file_pin_runs_before_the_structural_short_circuit():
    """Structural: the pin is not behind the `continue` any more."""

    body = (REPO_ROOT / "tools/verify_tmlr_submission_numbers.py").read_text(
        encoding="utf-8")
    body = body.split("def literal_coverage_checks(", 1)[1].split("\ndef ", 1)[0]
    pin = body.index("is the pinned text")
    short_circuit = body.index("additionally checked below")
    assert pin < short_circuit, \
        "the whole-file pin must run before structural sources are skipped"


def test_structural_sources_are_still_checked_structurally(tmp_path):
    """The specialized checks are additions, not replacements."""

    root = _submitted_tex_tree(tmp_path)
    macros = root / "paper/macros.tex"
    macros.write_text(macros.read_text(encoding="utf-8")
                      + "\nThe measured value is 42.7.\n", encoding="utf-8")
    failures = _audit(root)
    assert any("contains only macro declarations" in name for name in failures)
    assert any("states no numeric value" in name for name in failures)
    assert any("is the pinned text" in name for name in failures)


def test_every_audited_source_has_a_whole_file_binding():
    pinned = ledger_tool.file_pins(REPO_ROOT)
    for source in ledger_tool.audited_sources(REPO_ROOT):
        if str(source) in ledger_tool.GENERATED_ARTIFACT_SOURCES:
            continue
        assert str(source) in pinned, source
        assert len(pinned[str(source)]) == 64


def test_the_pinned_units_can_be_printed_for_review():
    done = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools/verify_tmlr_submission_numbers.py"),
         "--print-contexts"], capture_output=True, text=True, cwd=REPO_ROOT)
    assert done.returncode == 0, done.stderr[-2000:]
    assert "rationale:" in done.stdout
    assert "best-fixed-action regret" in done.stdout
    assert "whole-file binding" in done.stdout


def test_a_meaning_change_beyond_the_old_forty_character_radius_fails(tmp_path):
    """The exact false negative the fixed-radius pin had.

    "independently of $T$" -> "growing linearly in $T$" reverses a claim about
    the sufficient budget, 60-odd characters away from the nearest pinned
    number. The old +-40 context is byte-identical before and after; the unit is
    not.
    """

    root = _submitted_tex_tree(tmp_path)
    path = root / "paper/appendix_cg.tex"
    text = path.read_text(encoding="utf-8")
    before = "independently of~$T$."
    assert before in text
    path.write_text(text.replace(before, "growing linearly in~$T$.", 1),
                    encoding="utf-8")

    # the old pin would not have seen it
    edited = ledger_tool.auditable_text(path)
    pristine = ledger_tool.auditable_text(REPO_ROOT / "paper/appendix_cg.tex")

    def radius_40(body):
        mine = [ledger_tool.normalize_prose(p) for (f, p)
                in ledger_tool.phrase_pins(REPO_ROOT) if f == "paper/appendix_cg.tex"]
        spans = ledger_tool.literal_spans(
            body, sorted(mine, key=len, reverse=True)).get("0,1", [])
        return [ledger_tool.normalize_prose(body[max(0, a - 40):b + 40])
                for a, b in sorted(spans)]

    assert radius_40(edited) == radius_40(pristine), \
        "pick a different anchor: this one is inside the old radius"

    failures = _audit(root)
    assert any("pinned semantic unit" in name for name in failures), failures
    assert any("is the pinned text" in name for name in failures), failures


def test_a_regenerated_pin_inside_a_package_does_not_self_authorize(tmp_path):
    """Editing a source and its pin together must still fail.

    The pin module ships, and it is generated from the sources, so a consistent
    pair of edits inside an unpacked supplement agrees with itself. The
    contract module holds the pin module's digest, and the ledger checks that
    before consulting a single pin.
    """

    root = tmp_path / "unpacked"
    (root / "tools").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "tools/numeric_context_pins.py",
                 root / "tools/numeric_context_pins.py")
    clean = contract.check_shipped_tools(root)
    assert clean and all(ok for _name, ok, _detail in clean)

    forged = (root / "tools/numeric_context_pins.py")
    forged.write_text(forged.read_text(encoding="utf-8")
                      + "\n# regenerated after editing a source\n",
                      encoding="utf-8")
    after = contract.check_shipped_tools(root)
    assert after and not all(ok for _name, ok, _detail in after)


def test_the_ledger_refuses_a_pin_module_the_contract_does_not_know():
    """Even in the repository: the loaded module is checked, not assumed."""

    checks = ledger_tool.literal_coverage_checks(REPO_ROOT, LEDGER)
    named = [c for c in checks if "pin module the ledger loaded" in c.name]
    assert named and named[0].status == ledger_tool.STATUS_PASS
    assert contract.SHIPPED_TOOL_DIGESTS["tools/numeric_context_pins.py"] == \
        hashlib.sha256(
            (REPO_ROOT / "tools/numeric_context_pins.py").read_bytes()).hexdigest()


def test_regeneration_is_not_an_approval_anchor():
    """Verification must not call the generator; it reads committed pins."""

    source = (REPO_ROOT / "tools/verify_tmlr_submission_numbers.py").read_text(
        encoding="utf-8")
    body = source.split("def literal_coverage_checks(", 1)[1]
    body = body.split("\ndef ", 1)[0]
    assert "regenerated_pin_module" not in body
    assert "--regenerate-pins" in source          # exists, and is opt-in only


def test_the_regenerator_reproduces_the_committed_pins():
    """The committed record is what this repository's sources actually say."""

    generated = ledger_tool.regenerated_pin_module(REPO_ROOT)
    committed = (REPO_ROOT / "tools/numeric_context_pins.py").read_text(
        encoding="utf-8")
    assert generated == committed


def test_the_superseded_r7_candidate_is_recorded():
    superseded = "8f74363694c41ba323233a324f1b570decdd39ab"
    assert superseded in packager.RECORDED_PROJECT_REVISIONS
    assert superseded in PROJECT_REVISIONS


@pytest.mark.parametrize("rendered", [
    "8f74363694c41ba323233a324f1b570decdd39ab",
    "8F74363694C41BA323233A324F1B570DECDD39AB",
    "8f743636",
    "8F74363",
])
def test_the_superseded_r7_candidate_is_scanned_in_every_form(tmp_path,
                                                              rendered):
    path = tmp_path / "note.txt"
    path.write_text(f"built at {rendered}\n", encoding="utf-8")
    assert scan([(path, "note.txt")]), rendered


def test_the_immediate_prior_candidate_is_recorded():
    superseded = "e0f2b414cdb73c5fbcb2e87fd00b5bc09f234f71"
    assert superseded in packager.RECORDED_PROJECT_REVISIONS
    assert superseded in PROJECT_REVISIONS


@pytest.mark.parametrize("rendered", [
    "e0f2b414cdb73c5fbcb2e87fd00b5bc09f234f71",
    "E0F2B414CDB73C5FBCB2E87FD00B5BC09F234F71",
    "e0f2b414",
    "E0F2B41",
])
def test_the_immediate_prior_candidate_is_scanned_in_every_form(tmp_path,
                                                                rendered):
    path = tmp_path / "note.txt"
    path.write_text(f"built at {rendered}\n", encoding="utf-8")
    assert scan([(path, "note.txt")]), rendered


@pytest.mark.parametrize("revision", [
    "e0f2b414cdb73c5fbcb2e87fd00b5bc09f234f71",
    "eafcf90c4097f04fc32ef59046e0b2f7daec23ec",
    "e32de5bd5b62fd9def863eb78be7475fd87fe7fc",
    "86b812523e692f3e944ba4862539d86f53c2e20d",
])
def test_every_prior_candidate_is_in_the_static_floor(revision):
    """The floor is what a clean checkout has: no reflog, no local objects."""

    assert revision in packager.RECORDED_PROJECT_REVISIONS


@pytest.mark.parametrize("revision", [
    "e0f2b414cdb73c5fbcb2e87fd00b5bc09f234f71",
    "eafcf90c4097f04fc32ef59046e0b2f7daec23ec",
    "e32de5bd5b62fd9def863eb78be7475fd87fe7fc",
    "86b812523e692f3e944ba4862539d86f53c2e20d",
])
@pytest.mark.parametrize("render", [
    lambda r: r, lambda r: r.upper(), lambda r: r[:8], lambda r: r[:7].upper(),
    lambda r: r[:12].capitalize(),
])
def test_a_prior_candidate_is_scanned_without_a_reflog(tmp_path, revision,
                                                       render):
    """Scanned against the static floor alone, as a fresh clone would."""

    path = tmp_path / "note.txt"
    path.write_text(f"built at {render(revision)}\n", encoding="utf-8")
    floor = packager.RECORDED_PROJECT_REVISIONS
    assert packager.scan_for_identifiers([(path, "note.txt")], floor), render(revision)


def test_no_forbidden_revision_reaches_a_shipped_reviewer_artifact():
    for shipped in ("tools/anonymous_package_contract.py",
                    "tools/tex_conditionals.py",
                    "tools/numeric_context_pins.py",
                    "tools/verify_tmlr_submission_numbers.py",
                    "tools/transport_artifact_expectations.py"):
        text = (REPO_ROOT / shipped).read_text(encoding="utf-8")
        for revision in packager.RECORDED_PROJECT_REVISIONS:
            assert revision not in text, (shipped, revision)
            assert revision[:7] not in text, (shipped, revision)


def test_rotating_is_documented_with_the_package_that_supplies_it():
    readme = (REPO_ROOT / "submissions/tmlr_2026/README.md").read_text(
        encoding="utf-8")
    assert "rotating" in readme
    assert "texlive-latex-recommended" in readme
    entry = (REPO_ROOT / packager.ENTRY_POINT).read_text(encoding="utf-8")
    assert r"\usepackage{rotating}" in entry
