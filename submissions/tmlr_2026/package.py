#!/usr/bin/env python3
"""Stage, compile and package the anonymous TMLR submission.

Everything this writes goes to an output directory outside the repository; no
protected path is touched.  The steps are deliberately separate so that each one
can fail loudly:

``stage``       copy the exact source set into ``<out>/src`` (flat, the way an
                unpacked ``source.zip`` looks to a reviewer);
``compile``     run ``latexmk`` there with a pinned ``SOURCE_DATE_EPOCH``;
``closure``     read ``main.fls`` and keep only the files pdfTeX actually opened;
``package``     write ``main.pdf``, ``source.zip``, ``supplement.zip``;
``scrub``       refuse to ship anything carrying an identifying string;
``manifest``    write ``release_manifest.json``.

``build.sh`` runs all of them in order.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
import anonymous_package_contract as contract  # noqa: E402
import tex_conditionals  # noqa: E402

SOURCE_DATE_EPOCH = "1609459200"  # 2021-01-01T00:00:00Z, fixed for reproducibility
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

# --------------------------------------------------------------------------
# what gets staged for the submission build
# --------------------------------------------------------------------------

ENTRY_POINT = Path("submissions/tmlr_2026/main.tex")

#: The compiled-source-closure manifest, shipped at the supplement root.
SOURCE_CLOSURE_NAME = "SOURCE_CLOSURE.json"

# Shared manuscript sources.  paper/main.tex is the historical AISTATS entry
# point and is deliberately absent; paper/legacy_experiments.tex is the cut
# legacy-benchmark appendix (see FINALIZATION_REPORT.md).
STAGE_TEX_EXCLUDE = {"main.tex", "legacy_experiments.tex"}
STAGE_STY_EXCLUDE = {"aistats2026.sty"}

STYLE_FILES = ("tmlr.sty", "tmlr.bst", "fancyhdr.sty")

# --------------------------------------------------------------------------
# what gets shipped as the reproducibility supplement
# --------------------------------------------------------------------------

SUPPLEMENT_EXPERIMENT_MODULES = (
    "__init__.py",
    "aggregate_transport_instantiation.py",
    "artifact_utils.py",
    "config.py",
    "curvature_operators.py",
    "logging_utils.py",
    "make_transport_instantiation_artifacts.py",
    "run_transport_instantiation.py",
    "run_transport_instantiation_study.py",
    "theory_metrics.py",
    "transport_instantiation.py",
)
SUPPLEMENT_EXPERIMENT_TESTS = (
    "test_transport_instantiation.py",
    "test_transport_instantiation_aggregate.py",
    "test_transport_instantiation_artifacts.py",
)
SUPPLEMENT_EVIDENCE = (
    "results/derived/transport_instantiation/full_aggregate.json",
    "results/derived/transport_instantiation/full_aggregate.json.provenance.json",
    "results/derived/transport_instantiation/full_aggregate.json.sha256",
    "results/derived/transport_instantiation/selection.json",
    "results/derived/transport_instantiation/selection.json.provenance.json",
    "results/derived/transport_instantiation/selection.json.sha256",
)
SUPPLEMENT_OTHER = (
    "experiments/TRANSPORT_INSTANTIATION_PROTOCOL.md",
    "experiments/requirements.txt",
    "experiments/configs/transport_instantiation.yaml",
    "tools/verify_tmlr_submission_numbers.py",
    "tools/transport_artifact_expectations.py",
    "tools/anonymous_package_contract.py",
    "tools/tex_conditionals.py",
    "tools/numeric_context_pins.py",
)

# The 21 artifacts tools/transport_artifact_expectations.py regenerates from the
# locked aggregate and requires to be byte-identical.  This list used to be an
# `iterdir()` over paper/tables and paper/figures, which also shipped six files
# belonging to two disconnected legacy benchmarks that FINALIZATION_REPORT.md
# excludes from the submission.  A supplement should carry the evidence behind
# the submitted claims and nothing else, so the inventory is explicit and is
# cross-checked against what is actually on disk below.
_PANELS = ("D-0p25", "D-0p5", "D-1", "D-2")
SUPPLEMENT_GENERATED_ARTIFACTS = (
    "paper/tables/transport_instantiation_performance.tex",
    "paper/tables/transport_instantiation_tightness.tex",
    "paper/tables/transport_instantiation_validity.tex",
    *(f"paper/figures/transport_instantiation_{series}.{suffix}"
      for series in ("bound", "regret", "tightness")
      for suffix in ("csv", "tex")),
    *(f"paper/figures/transport_instantiation_{series}_{panel}.csv"
      for series in ("bound", "regret", "tightness")
      for panel in _PANELS),
)

# Typeset by the submission but not generated from the study: every cell is an
# asymptotic rate, so it has no aggregate to regenerate from.  It ships because
# the manuscript sources ship, and its sidecar is verified like any other.
SUPPLEMENT_SYMBOLIC_ARTIFACTS = ("paper/tables/growing_window_pareto.tex",)

# Deliberately not shipped.  These are the legacy autodiff-GGN and linear-bound
# benchmarks: they were designed for the earlier one-sided dynamic theorem, do
# not execute the transported score, and are not evidence for any claim in this
# submission.  paper/availability.tex says so to the reviewer.
SUPPLEMENT_EXCLUDED_LEGACY = (
    "paper/tables/autodiff_ggn_summary.tex",
    "paper/tables/linear_bound_ratios.tex",
)

#: Companion records that travel with an artifact when they exist on disk.
ARTIFACT_COMPANION_SUFFIXES = (".sha256", ".provenance.json",
                               ".provenance.json.sha256")


def _with_companions(repo: Path, relatives: Sequence[str]) -> list[str]:
    """Each artifact followed by whichever sidecar and provenance records exist."""

    out: list[str] = []
    for relative in relatives:
        out.append(relative)
        out.extend(f"{relative}{suffix}"
                   for suffix in ARTIFACT_COMPANION_SUFFIXES
                   if (repo / f"{relative}{suffix}").is_file())
    return out


def supplement_artifact_inventory(repo: Path) -> list[str]:
    """The evidence files the supplement ships, with nothing left to chance.

    Raises if paper/tables or paper/figures holds a file that is neither on the
    shipped list nor on the excluded-legacy list, so a newly generated artifact
    cannot be dropped from the supplement by silence.
    """

    shipped = _with_companions(
        repo, list(SUPPLEMENT_GENERATED_ARTIFACTS)
        + list(SUPPLEMENT_SYMBOLIC_ARTIFACTS))
    excluded = _with_companions(repo, list(SUPPLEMENT_EXCLUDED_LEGACY))

    on_disk = {
        f"{directory}/{path.name}"
        for directory in ("paper/tables", "paper/figures")
        for path in sorted((repo / directory).iterdir())
        if path.is_file()
    }
    unaccounted = sorted(on_disk - set(shipped) - set(excluded))
    if unaccounted:
        raise RuntimeError(
            "paper/tables and paper/figures hold files that are neither "
            "shipped nor explicitly excluded; classify them before building: "
            f"{unaccounted}"
        )
    missing = sorted(name for name in shipped if not (repo / name).is_file())
    if missing:
        raise RuntimeError(f"supplement evidence is missing from disk: {missing}")
    return sorted(shipped)

# --------------------------------------------------------------------------
# anonymous packaging transform
# --------------------------------------------------------------------------

# Two committed evidence files carry a top-level ``git_revision`` string.  That
# value is a Git object id in the project's public repository and resolves there
# to a named author and email, so shipping it defeats double-blind review.
#
# The committed evidence is immutable and is NOT edited.  Instead the packaging
# step writes anonymous copies into the external staging tree, replacing exactly
# that one metadata string.  Nothing else changes: not a number, not a key, not
# an ordering, not a byte outside the replaced value.  ``ANONYMIZATION.json``
# ships alongside them so a reviewer is told plainly that these are modified
# copies rather than original evidence, and ``release_manifest.json`` (internal,
# not uploaded) carries the full source-path / original-hash / packaged-hash map.
# The acceptable packaged result is pinned in tools/anonymous_package_contract.py,
# which is also what the shipped verifiers measure against.  Packaging reads the
# same constants and refuses to emit anything that does not match them, so the
# contract cannot drift away from what is actually built.
ANONYMIZE_REVISION_IN = tuple(sorted(contract.CONTRACT))
ANONYMIZED_FIELD = contract.PACKAGED_FIELD
ANONYMIZED_TOKEN = contract.REPLACEMENT_TOKEN
ANONYMIZATION_MANIFEST = contract.DECLARATION_NAME

# Revisions of this project that must never appear in reviewer-visible bytes.
# These are named in committed records or are finalization candidates, and they
# are the floor for a build that runs outside a Git checkout; the rest is
# derived from the checkout by project_revisions() below.  Amending the
# candidate makes the old one unreachable from any ref, which is exactly the
# case a `rev-list --all` sweep misses, so superseded candidates are written
# down here as well.  package.py is internal and is never uploaded, which is why
# revisions may be written down here at all.
RECORDED_PROJECT_REVISIONS = (
    "0cd6264c1f8b8751728f3c4a198207e8289aed74",  # study execution revision
    "93eaa537d2702d5d18b05905913b0b879e3d608f",  # renderer / review revision
    "47037a2df6b81befd4a0cb3c5974e3565d8f61b6",  # review-bundle base
    "7a83c5f2c7f710be1e8178682cbfcd8566244a48",  # recorded source head
    "b99b682ecc8f69552a3f57b1b85333378ed12ac1",  # finalization baseline (START)
    "301f1d7c89b4a02e030c101bdb0b1f0bb5302a2b",  # superseded candidate, pass 2
    "c8f9e85519f6274808c5afe07e70aea774778f23",  # superseded candidate, pass 1
    "f94fa4ba7b76a38fcb86a7c8d95d0139af6fcaee",  # superseded candidate, pass 4
    "4fa7b8c959eaca43a8b8110a9d2aedf40d2280a9",  # superseded candidate, pass 5
    "b5055ccffc56882447a51fc9265063a2371f22fb",  # superseded candidate, pass 6a
    "dd8b5b9ecf8b87c6f9c4ccd6282a43f89832d2cf",  # superseded candidate, pass 6
    "8f74363694c41ba323233a324f1b570decdd39ab",  # superseded candidate, pass 7
    "e0f2b414cdb73c5fbcb2e87fd00b5bc09f234f71",  # superseded candidate, pass 8
    "eafcf90c4097f04fc32ef59046e0b2f7daec23ec",  # superseded candidate, pass 9
    "e32de5bd5b62fd9def863eb78be7475fd87fe7fc",  # superseded candidate, pass 9a
    "86b812523e692f3e944ba4862539d86f53c2e20d",  # superseded candidate, pass 10
)

#: Keys whose value is a version-control identifier.  A 40-hex string sitting in
#: one of these is a revision whether or not this project has ever seen it, and
#: shipping it would name a repository and therefore an author.
REVISION_FIELD_NAMES = ("git_revision", "revision", "commit", "commit_id",
                        "commit_hash", "git_commit", "git_sha", "sha1",
                        "head", "IMPLEMENTATION_COMMIT")


def project_revisions(repo: Path) -> tuple[str, ...]:
    """Every commit id of this project: reachable, recorded, and superseded.

    `rev-list --all` alone is not enough.  Amending the finalization candidate
    leaves the previous one reachable only from the reflog, and an independent
    reviewer demonstrated exactly that gap by pasting an abbreviated superseded
    candidate into a shipped file and watching the scan pass.
    """

    revisions = {r.lower() for r in RECORDED_PROJECT_REVISIONS}
    for argv in (["rev-list", "--all"],
                 ["reflog", "--format=%H", "--all"],
                 ["rev-parse", "HEAD"]):
        try:
            listing = subprocess.run(
                ["git", "-C", str(repo), *argv],
                capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            continue
        revisions.update(
            line.strip().lower() for line in listing.splitlines()
            if len(line.strip()) == 40 and _is_hex(line.strip())
        )
    return tuple(sorted(revisions))


def _is_hex(value: str) -> bool:
    return all(character in "0123456789abcdefABCDEF" for character in value)


def _is_sha256(value: object) -> bool:
    """A real digest, not the empty string `_is_hex` happily accepts."""

    return isinstance(value, str) and len(value) == 64 and _is_hex(value)

# --------------------------------------------------------------------------
# anonymity and internal-leak scrub
# --------------------------------------------------------------------------

# Anything matching these must not leave the repository inside an upload: author
# names, employer or institution names, internal hostnames and checkout paths,
# local filesystem paths, and the repository identity.
#
# Deliberately NOT on this list: the literal string "BUCK" and the tool name
# "buck2".  Both appear as ordinary build-file names inside the frozen
# selection record's study-source inventory, which is immutable evidence.  A
# build-file name identifies neither an author nor a host, and rewriting the
# locked evidence to satisfy a scrub pattern would be far worse than shipping
# the name.
#: Every established author surname on this project, plus employer, host,
#: checkout-path and repository identifiers.  Matched case-insensitively:
#: `GRANZIOL` in a section heading identifies an author exactly as well as
#: `Granziol` does, and an earlier version of this list matched neither
#: Granziol nor Juarev at all outside the bibliography.
AUTHOR_SURNAMES = (r"Behzadian", r"Nassif", r"Granziol", r"Juarev")

FORBIDDEN = (
    r"buiksat",
    *AUTHOR_SURNAMES,
    r"Purestrength",
    r"devvm",
    r"internalfb",
    r"fbsource",
    r"/data/repos",
    r"/home/[a-z]",
    r"github\.com/[A-Za-z0-9_.-]+/Curvature",
    r"Curvature-Calibrated-Exploration",
    r"@meta\.com",
    r"@fb\.com",
    r"\borcid\b",
)

# The bibliography legitimately carries third-party author names, including a
# cited preprint by two of this paper's authors.  Citing prior work in the third
# person is normal under double-blind review; the scrub therefore allows author
# names inside references.bib and nowhere else.  FINALIZATION_REPORT.md records
# this as an explicit author release decision rather than hiding it here.
#
# The exemption is scoped to the matched token, not to the line it sits on.  It
# used to clear a whole line as soon as one allowed name appeared anywhere on
# it, so a references.bib line carrying both an author name and, say, a local
# checkout path shipped the path as well.
SCRUB_ALLOWLIST = {"references.bib"}
SCRUB_ALLOWED_TOKENS = (r"Granziol", r"Juarev")

FORBIDDEN_RE = re.compile("|".join(FORBIDDEN), re.IGNORECASE)
SCRUB_ALLOWED_TOKEN_RE = re.compile("|".join(SCRUB_ALLOWED_TOKENS),
                                    re.IGNORECASE)

# A BibTeX key is mechanically derived from the first author's surname, so the
# same two names also occur in the manuscript as \citep{granziol2026hessian}.
# That is the identical release decision as the bibliography entry -- citing
# prior work in the third person -- and it is exempt on the identical terms:
# the matched token must itself be an allowed author name, and it must lie
# inside a citation command's key argument.  Prose naming an author is not.
CITATION_KEYS_RE = re.compile(
    r"\\[a-zA-Z]*cite[a-zA-Z]*\s*(?:\[[^\]]*\]\s*)*\{([^}]*)\}")


def _citation_key_spans(line: str) -> list[tuple[int, int]]:
    return [match.span(1) for match in CITATION_KEYS_RE.finditer(line)]


def citation_exempt(arcname: str, match: re.Match[str], line: str) -> bool:
    """True only for an allowed author token in a bibliography or citation key."""

    if SCRUB_ALLOWED_TOKEN_RE.fullmatch(match.group(0)) is None:
        return False
    if Path(arcname).name in SCRUB_ALLOWLIST:
        return True
    return any(start <= match.start() and match.end() <= end
               for start, end in _citation_key_spans(line))

# --------------------------------------------------------------------------
# the venue's layout rules, enforced on the sources the submission compiles
# --------------------------------------------------------------------------

# TMLR does not allow the font size, margins or spacing to be reduced in order
# to fit content.  An earlier candidate set the three generated evidence tables
# at \scriptsize, halved \tabcolsep and then scaled away whatever was still too
# wide; the rendered text came out near 6.2pt against 9.96pt body copy.  These
# are the mechanisms that did it, and none of them may survive into what the
# submission compiles.
#
# The historical two-column AISTATS entry point still scales those tables and
# has to, because it has half the measure.  That code sits in the true branch
# of \iflegacyextras, which the submission sets false, so the scan below
# evaluates the conditional the way the submission does and enforces the rule
# on exactly the text pdfTeX will see.
SHRINK_MECHANISMS = (
    (r"\\resizebox\b", "box scaling"),
    (r"\\scalebox\b", "box scaling"),
    (r"\\adjustbox\b", "box scaling"),
    (r"\\tiny\b", "font-size reduction"),
    (r"\\scriptsize\b", "font-size reduction"),
    (r"\\footnotesize\b", "font-size reduction"),
    (r"\\small\b", "font-size reduction"),
    # An explicit size selection is the same thing said the long way, and it
    # slipped past a list that only knew the named sizes.
    (r"\\fontsize\b", "explicit font size"),
    (r"\\selectfont\b", "explicit font size"),
    (r"\\usefont\b", "explicit font size"),
    (r"\\@setfontsize\b", "explicit font size"),
    (r"\\DeclareFontShape\b", "explicit font size"),
    (r"\\linespread\b", "line spacing"),
    (r"\\(?:set|addto)length\s*\{?\s*\\baselineskip", "line spacing"),
    (r"\\tabcolsep\s*=", "intercolumn spacing"),
    (r"\\(?:set|addto)length\s*\{?\s*\\tabcolsep", "intercolumn spacing"),
    (r"\\arraystretch\b", "row spacing"),
    (r"\\(?:set|addto)length\s*\{?\s*\\(?:text|column)(?:width|height)",
     "text block geometry"),
    (r"\\(?:set|addto)length\s*\{?\s*\\(?:odd|even)sidemargin", "margins"),
    (r"\\(?:set|addto)length\s*\{?\s*\\topmargin", "margins"),
    (r"\\usepackage\s*(?:\[[^]]*\])?\s*\{geometry\}", "margins"),
    # Constructs that let a control sequence be assembled at expansion time.
    # None of the submitted sources uses one, and a checker that reads tokens
    # cannot see through them, so their presence is itself the finding.
    (r"\\csname\b", "unreadable construct"),
    (r"\\expandafter\b", "unreadable construct"),
    (r"\\scantokens\b", "unreadable construct"),
    (r"\\catcode\b", "unreadable construct"),
)

#: Every generated evidence table, and the wrapper each one must be reached
#: through.  \evidencetabular substitutes a column preamble and nothing else;
#: it cannot change a font size or scale a box.
EVIDENCE_TABLE_INPUTS = (
    "tables/transport_instantiation_validity.tex",
    "tables/transport_instantiation_performance.tex",
    "tables/transport_instantiation_tightness.tex",
)
EVIDENCE_TABLE_WRAPPER = r"\evidencetabular"


def strip_tex_comments(text: str) -> str:
    """Drop everything after an unescaped ``%`` on each line."""

    out = []
    for line in text.splitlines():
        kept, escaped = [], False
        for char in line:
            if char == "%" and not escaped:
                break
            kept.append(char)
            escaped = char == "\\" and not escaped
        out.append("".join(kept))
    return "\n".join(out)


def resolve_legacy_conditionals(text: str) -> str:
    r"""The text the submission compiles: `\iflegacyextras` false, rest opaque.

    Shared with `paper/validate.py` through tools/tex_conditionals.py so the two
    internal checkers cannot disagree about which bytes are live.
    """

    return tex_conditionals.resolve(text, legacy=False)


def submitted_tex_sources(repo: Path) -> list[tuple[Path, str]]:
    """(path, arcname) for the .tex the repository preflight looks at.

    This is a *diagnostic*, not the authority.  It globs the repository and so
    it can only ever see what someone thought to glob -- it missed
    `paper/tables/` and `paper/figures/` entirely.  The authority is
    `check_compiled_layout_rules`, which reads the recorder output of the build
    that actually produced the submitted PDF.
    """

    sources = [(repo / ENTRY_POINT, str(ENTRY_POINT))]
    for path in sorted((repo / "paper").glob("*.tex")):
        if path.name in STAGE_TEX_EXCLUDE:
            continue
        sources.append((path, f"paper/{path.name}"))
    for directory in ("paper/tables", "paper/figures"):
        for path in sorted((repo / directory).glob("*.tex")):
            sources.append((path, f"{directory}/{path.name}"))
    return sources


#: The venue's mandatory template, which may not be edited and therefore may not
#: be held to our layout rule: `tmlr.sty` and `fancyhdr.sty` legitimately define
#: and use size commands.  The exemption is earned by bytes, not by filename --
#: a file is exempt only if its SHA-256 is the pinned upstream one, which is the
#: same digest paper/tmlr_style/PROVENANCE.md records.
VENUE_TEMPLATE_DIGESTS = {
    "tmlr.sty":
        "816214ff5919aa457b6b443bee52b15d9561421417b7f8a50cc84651519f0002",
    "tmlr.bst":
        "306fd454cf40771bee01293eeb98d2c1cd5f4e11ed0cd7296b335f354fc45206",
    "fancyhdr.sty":
        "3d2922548e0e5f1a6c5676eda6ebb6dc20d7d305b4d8c2be5f1c833fb1084e6d",
    "LICENSE-tmlr-style":
        "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4",
}

#: Third-party LaTeX packages the submission compiles against, vendored
#: into `paper/texmf_vendor/` and staged flat beside `main.tex`.  They are
#: here because the build refuses an external compiled input from any tree
#: the invoking user can write, and this host's TeX Live does not package
#: pgfplots, microtype, cleveref or mathtools -- so they were living in
#: `TEXMFHOME`, which is exactly what the rule rejects.
#:
#: The exemption from the layout rule and from the per-literal number audit
#: is earned by bytes, the same way the venue template's is: a file counts
#: as a vendored package only when its SHA-256 is the pinned one.  Edit a
#: byte and the build stops.  `paper/texmf_vendor/VENDORED-PACKAGES.md`
#: records what each package is and under which licence it travels.
VENDORED_PACKAGE_DIGESTS = {
    'LICENSE-gpl-3-0':
        '8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903',
    'LICENSE-lppl-1-2':
        'c5ccc6b3e36f75e1b44d8bfb178198a47692b6c86d936af804812c4866e0db58',
    'LICENSE-lppl-1-3c':
        '5f05fcf6ef25a6c31bccd2df7c0c46b23107bbeb2ce5cdba74efb5cc357f4dbb',
    'cleveref.sty':
        '58d7e2b67b8b165ec1c7e12dd2ea6edc807d5a61f68cb316267cea44fe128ef9',
    'mathtools.sty':
        '4c4bbd5e235f293dd773ad43b3aaebd3598a9d405b4ffe6326a9492157915085',
    'mhsetup.sty':
        'c3ae1e23f43029fbfc271e3b1440a692e1cd924d1810430b99e4f2aa5b9ccf09',
    'microtype-pdftex.def':
        'f196a58f713b3ec5e5a333645e031842859572c1b7e0d1a7d4e1dfc36896a5ea',
    'microtype.cfg':
        '48d49af4c08491d0bb1c8a4ba189e41d2a5bff4811a3af56540f7e9a88673eaf',
    'microtype.sty':
        '26604a3f185a5f389061b035f6d534b971a25b18ae3d41864e77870402cff56c',
    'mt-cmr.cfg':
        'ee8658bc3a8cec636afce4a7143811a4310f6c830b551dbed09a90836bb4cdf9',
    'mt-msa.cfg':
        '3c55f887c103890580e078c409bed845562b27f3b98697f93d08856f103c31ca',
    'mt-msb.cfg':
        'f3ea01b4420c406dbf1b68dd9efe3b33ef2b5b28ba0031140e0b6082bbdda018',
    'pgflibraryfillbetween.code.tex':
        '5f509db0338d04288db52164f3384e1dfa209e820b151d68568979385379baba',
    'pgflibrarypgfplots.surfshading.code.tex':
        'e90c556be8f468865ca2b656913ba8afc2220f2c163f02e0874731a6d34cdd64',
    'pgflibrarypgfplots.surfshading.pgfsys-pdftex.def':
        'c52c6c54e7ffd5e43094a13b33c6e93cbfa1f3fd6455cf2512102d19d3b7c49e',
    'pgfplots.code.tex':
        'b81c0ee2806033d4111b73f50400ff8865ae90accd3c6e7a6976e81c2a3aa52a',
    'pgfplots.errorbars.code.tex':
        '70c56e4ccf3448f53cfbb90046ada2683dbf2eec1cf586562fe78bcfe146b3de',
    'pgfplots.markers.code.tex':
        '59104418d1184b73a01e15b254ffb8c5d4320cf510673f095933d88e901617d6',
    'pgfplots.paths.code.tex':
        'd11c8b83414c052bb39c678e49d81c5f0235de4af1bdf5dd75270e4de82f94a5',
    'pgfplots.revision.tex':
        '208f32e66b042889cf8597135ebcf7ee1cea04c5f8bf9ee7a2b7ed383436944c',
    'pgfplots.scaling.code.tex':
        '3e8298cf4d0f913a2ca6c2bba59d9894a42f8e9572671e4dd2f83f6bceb95b80',
    'pgfplots.sty':
        'cb353b58769449f756c5c16f9d355c90c0714d1da1228bf912c3a5b208b4890b',
    'pgfplotsarray.code.tex':
        '38442c559fd7e7be2a812d4d809940795fc9535e6d571dbf52c5a0493b26f998',
    'pgfplotsbinary.code.tex':
        '71271312b0668f69e03014f6c90fcf37112de363643661a2cbb77e047e86d75e',
    'pgfplotsbinary.data.code.tex':
        'd48a5679ca97f921aa11c6ac0aea9773f8791ab8cf71399ed731f44236d04eed',
    'pgfplotscolor.code.tex':
        '521c3db6439ff99c2dbcba5384f8006824ab4a4af28f86785ec9930968272536',
    'pgfplotscolormap.code.tex':
        'b0671f2833e4eb6ee2bd932bbd93f01f92e841b4f6941294b95d5b8075d720e9',
    'pgfplotscoordprocessing.code.tex':
        '765209b4b8739df96bd13c01b5573c043a4b2a3490c7c741d5fa9c7e0743973d',
    'pgfplotscore.code.tex':
        '4c71ea64f5b3582f1d6346f9f9a782da20ed7a4c76e00ee1f73ee23186a1db9b',
    'pgfplotsdeque.code.tex':
        '86843251927c29a021eac1635ee8650cfc06265281b50441d8cb6f67bb8504ee',
    'pgfplotslibrary.code.tex':
        '12dfa15deed098538d51fb665a4f4ff759d8ef63d9216b38c19e87fbb0b476dc',
    'pgfplotsliststructure.code.tex':
        'ef606fdf2ffc6197b9e1037860e1fe788cfa1aa3bf271a986dd6662b2e6526ca',
    'pgfplotsliststructureext.code.tex':
        'a4cd7e5531850e0e874c1096838ec55d62bf413dd7488f5316f730ce833f42db',
    'pgfplotsmatrix.code.tex':
        'a22375071be85968f3b7489bd64c01f5317ca1ddadc0b7ab1f8257181d55a35b',
    'pgfplotsmeshplothandler.code.tex':
        '285da39b32bee58c3cad318670a986b3097efd4442d2452d48abbf3727a47157',
    'pgfplotsmeshplotimage.code.tex':
        '7da4d7c10e41e5fed5f54489deaf761a3d01e2353c47b345582666785805f18b',
    'pgfplotsoldpgfsupp_loader.code.tex':
        'a36a28ecd51df3dd0f63446f24a84290ec322095280578063ae9b94804014c37',
    'pgfplotsplothandlers.code.tex':
        '5810ee1120735670e9d7c3edd9c0f1e2e9e77284a76804cb413ecd314fe9f1f2',
    'pgfplotsstackedplots.code.tex':
        '77a129850572be38d1cb3540d5b6ac4a835f2335ba22a2f90cd4d05762b0bbf0',
    'pgfplotssysgeneric.code.tex':
        '7124db702274395928a825f687081477f0de5ee9007b9a4a9208f28f209f67fe',
    'pgfplotstableshared.code.tex':
        'ae3fd038684fb1192d7a9059d5c8b261cccbf647f0f3d9ac084be882b5ec9895',
    'pgfplotsticks.code.tex':
        '7005297bdcb9afb98162d9d2f4e0555285bb025c8359413f9785f2a57ffd228a',
    'pgfplotsutil.code.tex':
        'd385812ee2e3eebba3ae8356728e0e58697d9d508f4001ffad266de47f47886b',
    'pgfplotsutil.verb.code.tex':
        '878385031a1d3ea317938785f956d075fd419415bc00204b28f3f6792bb30d29',
    'tikzlibrarydecorations.softclip.code.tex':
        'dc56593a617f4a7512dce6c5ab16a80a5f53b164e93419937c9e249d61239739',
    'tikzlibraryfillbetween.code.tex':
        '14de4093b72cd84659cdd31b064827be0c88085428ead999080b43bcfc1e2d20',
    'tikzlibrarypgfplots.decorations.softclip.code.tex':
        '4d141d667fa77f766c592b62b6b8fddef8cf936be983b73c92340e94360c7a70',
    'tikzlibrarypgfplots.fillbetween.code.tex':
        '1f30469b33df72c0dc7fd2da567fd42fc08e679dfcbb0d5e3a82b710841d24ca',
    'tikzlibrarypgfplots.groupplots.code.tex':
        '27ad8052f7708da5f355f2754ceb274cc622da405aec7b93be7224d076bdfe42',
}

#: Where the vendored copies live in the repository.
VENDORED_DIRECTORY = "paper/texmf_vendor"

#: The licence texts that must travel with the vendored code.
VENDORED_LICENSE_FILES = (
    'LICENSE-gpl-3-0',
    'LICENSE-lppl-1-2',
    'LICENSE-lppl-1-3c',
)

#: The three generated pgfplots figure sources.  They carry
#: `legend style={font=\scriptsize}`, `tick label style={font=\scriptsize}` and
#: `label style={font=\small}` -- the size of a plot's own axis annotations,
#: which is a property of the figure and not of the body or table text the
#: venue's rule is about.  No journal sets tick labels at 10pt.
#:
#: The exemption is earned by bytes exactly as the venue template's is: these
#: digests are the locked artifacts that
#: `tools/transport_artifact_expectations.py` regenerates from the aggregate.
#: Edit one byte and the digest stops matching, the file is scanned like any
#: other compiled input, and the edit fails.
GENERATED_FIGURE_DIGESTS = {
    "figures/transport_instantiation_bound.tex":
        "9c6465521c216fa96fc6536044491684312108c510357f38cc92c0325319af3c",
    "figures/transport_instantiation_regret.tex":
        "239ae5e923801ed1a2f9eafa75ba6a642e8bd2bb14ec2875c8d080f22ea5ec98",
    "figures/transport_instantiation_tightness.tex":
        "828590d0cab45e2621677474acec4ae1216857191d54e816d4f4b24a2fd276c2",
}

#: `main.bbl` is written by the pinned `tmlr.bst`, and every natbib-family style
#: emits this preamble verbatim.  Exempting the exact block rather than the file
#: keeps the rest of the bibliography under the rule.
BBL_TEMPLATE_PREAMBLE = (
    "\\expandafter\\ifx\\csname urlstyle\\endcsname\\relax\n"
    "  \\providecommand{\\doi}[1]{doi: #1}\\else\n"
    "  \\providecommand{\\doi}{doi: \\begingroup \\urlstyle{rm}\\Url}\\fi"
)


def check_compiled_layout_rules(src: Path,
                                sources: dict[str, str] | None = None,
                                repo: Path | None = None) -> list[str]:
    """Run the venue's layout rule over the exact closure the compiler read.

    `src` is the staged tree of a build that has already succeeded, so
    `main.fls` lists every project-local file pdfTeX opened -- nested table and
    figure inputs included, and any directory added in future without anyone
    updating a glob.  `sources` maps staged names back to repository paths so a
    finding names the file a person has to edit.
    """

    sources = sources or {}
    findings: list[str] = []
    scanned = 0
    exempt: list[str] = []

    for relative in recorder_inputs(src, repo=repo):
        staged = str(relative)
        where = sources.get(staged, f"<staged only> {staged}")
        data = (src / relative).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if VENUE_TEMPLATE_DIGESTS.get(staged) == digest:
            exempt.append(staged)
            continue
        if staged in VENUE_TEMPLATE_DIGESTS:
            findings.append(
                f"{where}: the venue template was modified (sha256 {digest}, "
                f"pinned {VENUE_TEMPLATE_DIGESTS[staged]})")
            continue
        if GENERATED_FIGURE_DIGESTS.get(staged) == digest:
            exempt.append(staged)
            continue
        if VENDORED_PACKAGE_DIGESTS.get(staged) == digest:
            exempt.append(staged)
            continue
        if staged in VENDORED_PACKAGE_DIGESTS:
            findings.append(
                f"{where}: a vendored package was modified (sha256 {digest}, "
                f"pinned {VENDORED_PACKAGE_DIGESTS[staged]})")
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            findings.append(f"{where}: compiled input is not UTF-8 text")
            continue
        if staged == "main.bbl":
            text = text.replace(BBL_TEMPLATE_PREAMBLE, "", 1)
        scanned += 1
        try:
            compiled = resolve_legacy_conditionals(strip_tex_comments(text))
        except ValueError as error:
            findings.append(f"{where}: {error}")
            continue
        for number, line in enumerate(compiled.splitlines(), 1):
            for pattern, kind in SHRINK_MECHANISMS:
                for match in re.finditer(pattern, line):
                    findings.append(
                        f"{where}:{number}: {kind} via {match.group(0)!r} in "
                        f"{line.strip()[:100]!r}")

    if not scanned:
        findings.append("the compiled closure contained no reviewable source")
    if findings:
        return findings
    templates = sum(1 for name in exempt if name in VENUE_TEMPLATE_DIGESTS)
    figures = sum(1 for name in exempt if name in GENERATED_FIGURE_DIGESTS)
    vendored = sum(1 for name in exempt if name in VENDORED_PACKAGE_DIGESTS)
    print(f"compiled layout gate: {scanned} of {scanned + len(exempt)} recorded "
          f"inputs scanned; exempt by pinned digest: {templates} venue template, "
          f"{figures} generated figure source, {vendored} vendored package")
    return []


def check_layout_rules(repo: Path) -> list[str]:
    """Return every venue layout violation in the compiled submission sources."""

    findings: list[str] = []
    compiled_sources: list[tuple[str, str]] = []
    exempt_digests = (set(VENUE_TEMPLATE_DIGESTS.values())
                      | set(GENERATED_FIGURE_DIGESTS.values()))
    for path, arcname in submitted_tex_sources(repo):
        # Same earned-by-bytes exemptions the compiled gate uses, so the
        # diagnostic and the authority agree about what is in scope.
        if hashlib.sha256(path.read_bytes()).hexdigest() in exempt_digests:
            continue
        try:
            compiled = resolve_legacy_conditionals(
                strip_tex_comments(path.read_text(encoding="utf-8")))
        except ValueError as error:
            # An unbalanced branch would silently hide the rest of the file
            # from this scan, so it is a finding rather than a parse detail.
            findings.append(f"{arcname}: {error}")
            continue
        compiled_sources.append((arcname, compiled))
        for number, line in enumerate(compiled.splitlines(), 1):
            for pattern, kind in SHRINK_MECHANISMS:
                for match in re.finditer(pattern, line):
                    findings.append(
                        f"{arcname}:{number}: {kind} via {match.group(0)!r} in "
                        f"{line.strip()[:100]!r}")

    # Each generated evidence table must still be reached through the wrapper
    # that can only restate column widths, so the shrink path cannot come back
    # by routing the \input through something else.
    seen: dict[str, str] = {}
    for arcname, compiled in compiled_sources:
        for table in EVIDENCE_TABLE_INPUTS:
            marker = "\\input{" + table + "}"
            index = compiled.find(marker)
            if index < 0:
                continue
            seen[table] = arcname
            window = compiled[max(0, index - 1200):index]
            if EVIDENCE_TABLE_WRAPPER not in window:
                findings.append(
                    f"{arcname}: {table} is not typeset through "
                    f"{EVIDENCE_TABLE_WRAPPER}")
    for table in EVIDENCE_TABLE_INPUTS:
        if table not in seen:
            findings.append(f"{table} is no longer typeset by the submission")
    return findings


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def reset_build_directory(path: Path) -> None:
    """Make `path` a fresh, empty, real directory, following no symlink.

    `shutil.rmtree` refuses a symlink and would otherwise leave a link to a
    directory outside the output tree in place for the copy loop to write
    through.
    """

    if path.is_symlink() or (path.exists() and not path.is_dir()):
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def atomic_write_bytes(target: Path, data: bytes) -> None:
    """Write `data` to `target` without ever writing through a symlink.

    An independent reviewer pointed an external output directory at pre-placed
    `main.pdf` and `release_manifest.json` symlinks; the build "succeeded" and
    rewrote whatever those links pointed at, anywhere on the filesystem.
    Directory containment does not help: the escape is the link, not the path.

    A fresh temporary file in the destination directory is created with
    O_EXCL, so it cannot itself be a pre-existing link, and `os.replace` then
    swaps it into place. `os.replace` renames over the *link*, not through it,
    so a pre-existing symlink at `target` is destroyed rather than followed, and
    its former target is left byte-identical.
    """

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not target.is_symlink() and target.is_dir():
        raise RuntimeError(
            f"refusing to write a release output over a directory: {target}")
    handle, temporary = tempfile.mkstemp(
        dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def ensure_output_outside_repo(repo: Path, out: Path) -> Path:
    """Resolve the output directory and refuse anything inside the repository.

    Canonicalized containment, not a textual prefix.  build.sh used to run a
    `${out#"$repo"}` prefix test as well, which rejected a perfectly valid
    sibling such as <repo>-release because it shares the repository's path
    prefix without being inside it.  This is now the only containment rule.
    """

    repo = repo.resolve()
    out = out.resolve()
    if out.is_relative_to(repo):
        raise SystemExit(
            f"refusing to write build output inside the repository: {out}")
    return out


# --------------------------------------------------------------------------
# stage / compile / closure
# --------------------------------------------------------------------------


def stage(repo: Path, out: Path) -> tuple[Path, dict[str, str]]:
    """Copy the source set into `<out>/src` and report where each file came from.

    The returned map is `staged relative path -> repository relative path`.  It
    is recorded here, by the code that does the copying, rather than re-derived
    later from the staged names: re-deriving means guessing, and the layout gate
    and the number audit both need to name the repository file a finding belongs
    to.  `main.bbl` has no entry; bibtex writes it during the build.
    """

    src = out / "src"
    reset_build_directory(src)
    (src / "tables").mkdir(parents=True)
    (src / "figures").mkdir(parents=True)
    sources: dict[str, str] = {}

    def place(origin: Path, staged: str) -> None:
        shutil.copy2(origin, src / staged)
        sources[staged] = str(origin.relative_to(repo))

    place(repo / ENTRY_POINT, "main.tex")
    for path in sorted((repo / "paper").glob("*.tex")):
        if path.name in STAGE_TEX_EXCLUDE:
            continue
        place(path, path.name)
    for path in sorted((repo / "paper").glob("*.sty")):
        if path.name in STAGE_STY_EXCLUDE:
            continue
        place(path, path.name)
    place(repo / "paper/references.bib", "references.bib")
    for name in STYLE_FILES:
        place(repo / "paper/tmlr_style" / name, name)
    place(repo / "paper/tmlr_style/LICENSE", "LICENSE-tmlr-style")
    # Flat, beside main.tex, because kpathsea searches `.` first: that is what
    # makes the staged copies win over any tree on the machine, and what makes
    # a reviewer's clean `source.zip` unpack compile against these exact
    # versions rather than against whatever their TeX Live carries.
    for name in sorted(VENDORED_PACKAGE_DIGESTS):
        place(repo / VENDORED_DIRECTORY / name, name)
    for path in sorted((repo / "paper/tables").glob("*.tex")):
        place(path, f"tables/{path.name}")
    for pattern in ("*.tex", "*.csv"):
        for path in sorted((repo / "paper/figures").glob(pattern)):
            place(path, f"figures/{path.name}")
    return src, sources


def compile_environment(src: Path) -> dict[str, str]:
    """The environment the authoritative compile runs in.

    Every TeX search variable is stripped first, then four are set back:

    * `TEXMFHOME` and `TEXMFCONFIG` point at directories under the staged tree
      that are never created, so a user tree cannot shadow the distribution --
      which is how 46 of this submission's inputs were coming from
      `/home/<user>/texmf` in the first place;
    * `TEXMFVAR` points at the system variable tree, so the format dump pdfTeX
      loads is the root-owned one rather than the user's cache;
    * `TEXMFCNF` points at the directory holding the installation's real
      `texmf.cnf`, so the recorder writes that canonical path rather than the
      distribution's symlink to it.

    The vendored packages are staged flat beside `main.tex`, and `.` comes
    first in kpathsea's search, so those are what the compiler reads.
    """

    env = {key: value for key, value in os.environ.items()
           if not key.startswith(TEX_SEARCH_ENV_PREFIXES)}
    env["SOURCE_DATE_EPOCH"] = SOURCE_DATE_EPOCH
    env["FORCE_SOURCE_DATE"] = "1"
    env["TEXMFHOME"] = str(src / ".no-user-texmf")
    env["TEXMFCONFIG"] = str(src / ".no-user-texmf-config")
    sysvar = kpsewhich_value("TEXMFSYSVAR")
    if sysvar:
        resolved = Path(os.path.realpath(
            sysvar.split(os.pathsep)[0].strip().lstrip("!").rstrip("/")))
        if resolved.is_dir() and not write_protection_problems(resolved):
            env["TEXMFVAR"] = str(resolved)
    config = texmf_config_root()
    if config is not None:
        env["TEXMFCNF"] = str(config)
    return env


def compile_pdf(src: Path) -> Path:
    subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error",
         "-recorder", "main.tex"],
        cwd=src, env=compile_environment(src), check=True,
    )
    pdf = src / "main.pdf"
    if not pdf.is_file():
        raise RuntimeError("latexmk reported success but produced no main.pdf")
    return pdf


# --------------------------------------------------------------------------
# the compiled document must resolve every reference it makes
# --------------------------------------------------------------------------

#: What pdfTeX and natbib say in the log when a cross-reference does not
#: resolve.  The log is the authority: it names the key, and it is emitted on
#: the final converged run, which is the only run whose `.aux` is stable.
UNRESOLVED_LOG_PATTERNS = (
    (r"LaTeX Warning: Reference `([^']*)' on page [^ ]+ undefined",
     "undefined reference"),
    (r"LaTeX Warning: Citation `([^']*)'[^\n]*undefined", "undefined citation"),
    # natbib does not use the LaTeX prefix.  `tmlr.sty` loads natbib, so this is
    # the form the submission's own builds actually emit, and a checker that
    # only knew the LaTeX spelling would have seen nothing at all.
    (r"Package natbib Warning: Citation `([^']*)'[^\n]*undefined",
     "undefined citation (natbib)"),
    (r"Package natbib Warning: Citation[^\n]*undefined on input line",
     "undefined citation (natbib)"),
    (r"Package natbib Warning: There were undefined citations",
     "undefined citations (natbib summary)"),
    (r"Package natbib Warning: Citation\(s\) may have changed",
     "bibliography not converged (natbib)"),
    (r"LaTeX Warning: Label `([^']*)' multiply defined", "duplicate label"),
    (r"LaTeX Warning: There were undefined references",
     "undefined references (summary)"),
    (r"LaTeX Warning: Citation\(s\) may have changed",
     "bibliography not converged"),
    (r"LaTeX Warning: There were multiply-defined labels",
     "multiply-defined labels (summary)"),
    # The catch-all, for a cross-reference diagnostic from some package these
    # patterns do not name.  Restricted to messages about references,
    # citations and labels: `LaTeX Warning: Font shape ... undefined` is a
    # routine message in almost every build, and a gate that fails on it would
    # be a gate someone turns off.
    (r"^(?:Package \w+|LaTeX) Warning:(?![^\n]*Font shape)[^\n]*"
     r"\b(?:[Cc]itations?|[Rr]eferences?|[Ll]abels?)\b[^\n]*\bundefined\b",
     "undefined cross-reference"),
)

#: What an unresolved reference looks like in the rendered text.  A bare `?` is
#: NOT on this list: the manuscript asks real questions in prose, cites a URL
#: containing `forum?id=`, and uses superscript stars that `pdftotext` maps to
#: `?`.  Only the placeholder shapes are a finding.
UNRESOLVED_RENDERED = ("??", "[?]", "(?)")


def check_compiled_references(src: Path) -> list[str]:
    r"""Reject a build whose cross-references did not resolve.

    `paper/validate.py` checks the sources statically, but it was pointed at the
    historical entry point only, so a `\ref` that the TMLR entry point cannot
    resolve compiled to `??` and shipped.  This reads the final log of the build
    that actually produced the submitted PDF, and then corroborates it against
    the rendered text when a text extractor is available.
    """

    findings: list[str] = []
    log_path = src / "main.log"
    if not log_path.is_file():
        return ["main.log is missing; the reference check cannot run"]
    log = log_path.read_text(encoding="utf-8", errors="replace")
    # pdfTeX wraps log lines at 79 columns, so a warning can be split across
    # two physical lines; unwrap before matching or the pattern never fires.
    unwrapped = re.sub(r"\n(?=[^\n])", lambda m: "\n", log)
    seen: set[str] = set()
    for pattern, kind in UNRESOLVED_LOG_PATTERNS:
        for match in re.finditer(pattern, unwrapped, re.M):
            detail = match.group(1) if match.groups() else ""
            finding = f"main.log: {kind} {detail!r}".rstrip(" ''")
            if finding not in seen:
                seen.add(finding)
                findings.append(finding)

    # The log check above is complete on its own.  The rendered-text pass below
    # is corroboration: it runs when a text extractor is available and is
    # reported as NOT EXECUTED when one is not, rather than being the thing the
    # gate silently depends on.
    pdf = src / "main.pdf"
    if not pdf.is_file():
        return findings + ["main.pdf is missing; nothing to inspect"]
    try:
        rendered = subprocess.run(
            ["pdftotext", "-layout", str(pdf), "-"],
            capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        print("reference check: log check complete; pdftotext unavailable, so "
              "the rendered-output corroboration is NOT EXECUTED")
        return findings
    for placeholder in UNRESOLVED_RENDERED:
        count = rendered.count(placeholder)
        if count:
            findings.append(
                f"main.pdf: {count} rendered {placeholder!r} placeholder(s)")
    return findings


#: The manifest schema.  Version 2 replaced the boolean `in_supplement` with
#: `ships_in`, because a boolean cannot distinguish "source.zip carries it" from
#: "no archive carries it at all".
CLOSURE_SCHEMA_VERSION = 2

#: Where a compiled input's bytes actually are.
CLOSURE_ARCHIVES = ("supplement", "source", "neither")


def closure_archive(staged: str, repository: str | None,
                    shipped: set[str], source_members: set[str]) -> str:
    """Which archive carries this compiled input, from the archives themselves.

    Derived from the member lists the build is about to write, not from a rule
    about roles: the answer is a fact about the two ZIPs, and a reviewer holding
    one of them can check it.
    """

    if repository is not None and repository in shipped:
        return "supplement"
    if staged in source_members:
        return "source"
    return "neither"


def write_source_closure_manifest(src: Path, sources: dict[str, str],
                                  out: Path,
                                  shipped: set[str] | None = None,
                                  repo: Path | None = None,
                                  source_members: set[str] | None = None) -> Path:
    r"""Record the compiled source closure so a reviewer can audit it offline.

    `verify.sh` runs where there is no TeX installation and no `.fls` file, so
    without this the packaged audit would have to re-derive the closure by
    parsing `\input` -- which is the guesswork the recorder exists to replace.
    The manifest binds every compiled input to its repository path, its
    SHA-256 and its byte count; the packaged checker then rejects a missing,
    extra, changed, unsafe or duplicated path.
    """

    shipped = shipped or set()
    source_members = source_members or set()
    entries = []
    for relative in recorder_inputs(src, repo=repo):
        staged = str(relative)
        data = (src / relative).read_bytes()
        repository = sources.get(staged)
        entries.append({
            "staged": staged,
            "repository": repository,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "role": closure_role(staged),
            # Which archive, if any, actually carries these bytes.  This
            # replaced a boolean `in_supplement`, which could not say the one
            # thing a reviewer most needs to know about `main.bbl`: bibtex
            # writes it during the build and it travels in *neither* archive,
            # so it exists to a reader only as a pinned digest and byte count.
            # Reading "not in the supplement" as "therefore in source.zip" was
            # wrong for exactly that entry.
            "ships_in": closure_archive(staged, repository, shipped,
                                        source_members),
        })
    drift = [
        f"{entry['staged']}: built {entry['sha256']} ({entry['bytes']} bytes, "
        f"{entry['role']}, {entry['ships_in']}), contract "
        f"{pinned['sha256']} ({pinned['bytes']} bytes, {pinned['role']}, "
        f"{pinned['ships_in']})"
        for entry in entries
        for pinned in [contract.COMPILED_CLOSURE.get(entry["staged"])]
        if pinned is not None
        and (entry["sha256"] != pinned["sha256"]
             or entry["bytes"] != pinned["bytes"]
             or entry["role"] != pinned["role"]
             or entry["ships_in"] != pinned["ships_in"]
             or entry["repository"] != pinned["repository"])
    ]
    built = {entry["staged"] for entry in entries}
    missing = sorted(set(contract.COMPILED_CLOSURE) - built)
    extra = sorted(built - set(contract.COMPILED_CLOSURE))
    if drift or missing or extra:
        raise RuntimeError(
            "the compiled closure disagrees with the pinned contract: "
            + "; ".join(drift + [f"{name}: absent" for name in missing]
                        + [f"{name}: not in the contract" for name in extra]))

    manifest = {
        "schema_version": CLOSURE_SCHEMA_VERSION,
        "what_this_is": CLOSURE_WHAT_THIS_IS,
        "entries": sorted(entries, key=lambda e: e["staged"]),
    }
    target = out / "supplement_stage" / SOURCE_CLOSURE_NAME
    atomic_write_bytes(target, canonical_json_bytes(manifest))
    return target


#: The prose the closure manifest carries.  A constant rather than a literal
#: inside the writer, because the release gate derives the document it expects
#: to find in `supplement.zip` from the pinned contract and compares bytes.
CLOSURE_WHAT_THIS_IS = (
    "Every project-local file pdfTeX opened while producing the submitted PDF, "
    "taken from the LaTeX recorder's .fls output of that exact build. This is "
    "the authoritative list of submitted inputs; it is not re-derived by "
    "parsing the sources. ships_in says where the bytes are: 'supplement' for "
    "a file supplement.zip carries, 'source' for one source.zip carries, and "
    "'neither' for a compiler input generated during the build that no archive "
    "ships -- main.bbl, which exists to a reader only as the digest and byte "
    "count recorded here and pinned in the package contract."
)


def canonical_json_bytes(document: object) -> bytes:
    """The one JSON serialisation this build writes, for every document."""

    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def derive_source_closure_document() -> dict:
    """The `SOURCE_CLOSURE.json` the pinned contract implies, byte for byte.

    `write_source_closure_manifest` refuses to write anything that disagrees
    with `contract.COMPILED_CLOSURE`, so an honest build's manifest is a pure
    function of that contract and this prose.  The release gate derives it here
    and requires the shipped member to match, which is what turns "the closure
    is pinned" into "the bytes in the archive are pinned".
    """

    return {
        "schema_version": CLOSURE_SCHEMA_VERSION,
        "what_this_is": CLOSURE_WHAT_THIS_IS,
        "entries": [
            {"staged": staged,
             **{field: pinned[field]
                for field in ("repository", "sha256", "bytes", "role",
                              "ships_in")}}
            for staged, pinned in sorted(contract.COMPILED_CLOSURE.items())
        ],
    }


def closure_role(staged: str) -> str:
    """What each compiled input is, for the reviewer reading the manifest."""

    if staged == "main.tex":
        return "entry-point"
    if staged in VENDORED_PACKAGE_DIGESTS:
        return "vendored-package"
    if staged in VENUE_TEMPLATE_DIGESTS:
        return "venue-template"
    if staged == "main.bbl":
        return "bibliography-output"
    if staged.endswith(".bib"):
        return "bibliography"
    if staged.endswith(".csv"):
        return "figure-data"
    if staged.startswith(("tables/", "figures/")):
        return "generated-artifact"
    return "manuscript-source"


def validate_staged_sources(repo: Path, src: Path) -> list[str]:
    """Run the static manuscript validator against the staged entry point."""

    done = subprocess.run(
        [sys.executable, str(repo / "paper/validate.py"), str(src / "main.tex")],
        capture_output=True, text=True)
    if done.returncode == 0:
        return []
    tail = (done.stdout + done.stderr).strip().splitlines()[-12:]
    return [f"paper/validate.py on the staged entry point: {line}"
            for line in tail]


#: Build by-products the recorder also lists.  Not inputs to anything.
RECORDER_IGNORED_SUFFIXES = frozenset({
    ".aux", ".out", ".log", ".fls", ".fdb_latexmk", ".pdf", ".blg", ".toc",
    ".lof", ".lot", ".nav", ".snm", ".synctex",
})

#: Every suffix a project-local compiled input is allowed to have.  An input
#: the checker does not know how to read is a finding, not something to skip:
#: the point of deriving the closure from the compiler is that nothing it reads
#: escapes review.
RECORDER_SUPPORTED_SUFFIXES = frozenset({
    # `.def` and `.cfg` arrived with the vendored microtype and pgfplots files;
    # they are ordinary LaTeX source and the layout gate reads them like any
    # other.
    ".tex", ".sty", ".bst", ".bbl", ".bib", ".csv", ".def", ".cfg", "",
})


#: kpathsea variables that name a *system* TeX distribution tree: the trees the
#: installed engine owns, which an ordinary user cannot write to.  Asking the
#: running installation is the only narrow way to learn where its own files
#: live; a hardcoded list would be wrong on the next distribution, and a
#: filesystem root such as /usr or /home would not be an allowlist at all.
SYSTEM_TEXMF_ROOT_VARIABLES = (
    "TEXMFDIST", "TEXMFMAIN", "TEXMFLOCAL", "TEXMFSYSVAR", "TEXMFSYSCONFIG",
)

#: kpathsea variables that name a *user* tree.  These are never trusted, even
#: though TeX reports them exactly like the system ones: `TEXMFHOME` and the
#: user caches live under the invoking user's home directory, so anything found
#: through them is bytes the person running the build can rewrite at will.  An
#: input from one of these is a finding unless it is separately pinned by
#: digest.  There is no such escape any more; see finding 1 of
#: section 9i in FINALIZATION_REPORT.md.
USER_TEXMF_ROOT_VARIABLES = ("TEXMFHOME", "TEXMFVAR", "TEXMFCONFIG")

#: Environment variables that redirect TeX's own search.  `kpsewhich
#: -var-value=TEXMFDIST` happily reports whatever `TEXMFDIST` in the
#: environment says, so asking the engine while these are set is asking the
#: attacker.  They are stripped before every kpsewhich call, which leaves the
#: values compiled into the installation.
TEX_SEARCH_ENV_PREFIXES = ("TEXMF", "TEXINPUTS", "BIBINPUTS", "BSTINPUTS",
                           "TEXFORMATS", "TEXPICTS", "TEXCONFIG", "TEXFONTS",
                           "TEXPSHEADERS", "TEXDOCS", "TEXSOURCES",
                           "KPATHSEA", "TEXMFCNF", "OPENTYPEFONTS",
                           "TTFONTS", "T1FONTS", "AFMFONTS", "ENCFONTS")

#: Directories that are never an acceptable allowlist entry, whatever kpsewhich
#: says.  A tree this shallow would readmit the whole filesystem.
FORBIDDEN_ROOT_PREFIXES = frozenset({
    "/", "/usr", "/usr/share", "/usr/local", "/home", "/root", "/tmp", "/var",
    "/etc", "/opt", "/srv", "/mnt", "/media", "/data",
})


def _scrubbed_tex_env() -> dict[str, str]:
    """`os.environ` with every TeX search-path override removed."""

    return {key: value for key, value in os.environ.items()
            if not key.startswith(TEX_SEARCH_ENV_PREFIXES)}


def kpsewhich_value(variable: str) -> str:
    """What the installed engine itself says `variable` is.

    Run with the TeX search environment stripped, so an exported `TEXMFDIST`
    cannot answer on the installation's behalf.
    """

    try:
        return subprocess.run(
            ["kpsewhich", f"-var-value={variable}"], capture_output=True,
            text=True, check=True, env=_scrubbed_tex_env()).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def write_protection_problems(path: Path) -> list[str]:
    """Why `path` is not write-protected, component by component from `/`.

    Every component has to be a real directory or file that the invoking user
    cannot replace: no symlink anywhere along the way, no write permission for
    this user, and no group or world write bit.  A single writable component is
    enough to swap the whole subtree, so the walk starts at the filesystem root
    and does not stop at the first interesting directory.
    """

    problems: list[str] = []
    current = Path(path.anchor or "/")
    for part in Path(path).parts[1:]:
        current = current / part
        try:
            info = current.lstat()
        except OSError as error:
            problems.append(f"{current}: {error.strerror}")
            return problems
        if stat.S_ISLNK(info.st_mode):
            problems.append(f"{current} is a symlink")
        if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            problems.append(f"{current} is group- or world-writable")
        if os.access(current, os.W_OK, follow_symlinks=False):
            problems.append(f"{current} is writable by the invoking user")
    return problems


def texmf_roots(repo: Path | None = None,
                staged: Path | None = None) -> tuple[Path, ...]:
    """The TeX trees an external compiled input may legitimately come from.

    Derived from the installed engine with `kpsewhich -var-value`, asked with
    the TeX search environment stripped, and then filtered hard.  A root is
    trusted only when all of this holds:

    * it came from a *system* distribution variable, never `TEXMFHOME` or a
      user cache;
    * it is an absolute, already-canonical, existing directory at least three
      components deep, and not one of the shallow filesystem roots above;
    * no component of its path, from `/` down, is a symlink;
    * no component is writable by the invoking user, by its group, or by the
      world;
    * it neither contains nor sits inside the repository or the staged tree.

    Anything else is simply not an allowlist: a user-writable tree lets the
    person running the build put arbitrary bytes into the submitted PDF without
    those bytes appearing anywhere in the audited source closure, which is the
    exact hole this closes.
    """

    roots: list[Path] = []
    guards = [p.resolve() for p in (repo, staged) if p is not None]

    def admit(candidate: Path) -> None:
        """Add `candidate` if it passes every rule; else try its real path.

        A distribution legitimately publishes a tree under a symlink -- here
        `TEXMFSYSVAR` is `/usr/share/texlive/texmf-var`, a root-owned link to
        `/var/lib/texmf`.  Rejecting the link outright would throw away a real
        system tree, and following it blindly would accept whatever it points
        at.  So the *resolved* path is validated in full, from `/` down, and the
        canonical form is what gets admitted: the link is never trusted, the
        target is, and only if the target earns it on its own.
        """

        for attempt in (candidate, Path(os.path.realpath(candidate))):
            if str(attempt) in FORBIDDEN_ROOT_PREFIXES:
                continue
            if len(attempt.parts) < 3:              # "/", "/usr", ...
                continue
            if not attempt.is_dir():
                continue
            if write_protection_problems(attempt):
                continue
            if os.path.realpath(attempt) != str(attempt):
                continue                            # not already canonical
            if any(guard == attempt or guard.is_relative_to(attempt)
                   or attempt.is_relative_to(guard) for guard in guards):
                continue                            # our own tree, either way
            if attempt not in roots:
                roots.append(attempt)
            return

    for variable in SYSTEM_TEXMF_ROOT_VARIABLES:
        value = kpsewhich_value(variable)
        if not value:
            continue
        for piece in value.split(os.pathsep):
            # kpathsea marks a recursive tree with a trailing `//` and a
            # must-exist tree with a leading `!!`.
            cleaned = piece.strip().lstrip("!").rstrip("/")
            if not cleaned or not os.path.isabs(cleaned):
                continue
            admit(Path(os.path.normpath(cleaned)))

    config = texmf_config_root()
    if config is not None:
        admit(config)
    return tuple(sorted(roots, key=str))


def texmf_config_root() -> Path | None:
    """The directory holding the installation's real `texmf.cnf`.

    Derived from the installation, not from the environment: take the engine's
    own `TEXMFDIST`, look at `web2c/texmf.cnf` under it, and resolve.  On this
    host that file is a root-owned symlink into `/etc/texlive/web2c`, which is
    itself root-owned and unlinked -- a perfectly ordinary distribution layout
    that the "no symlink in any component" rule would otherwise reject.

    Naming the directory lets `compile_pdf` point `TEXMFCNF` straight at the
    canonical copy, so the recorder writes the real path and nothing has to be
    admitted through a link.  Returns None unless the resolved directory and
    file both pass the write-protection walk on their own.
    """

    dist = kpsewhich_value("TEXMFDIST")
    if not dist:
        return None
    candidate = Path(dist.split(os.pathsep)[0].strip().lstrip("!").rstrip("/"))
    real = Path(os.path.realpath(candidate / "web2c" / "texmf.cnf"))
    if not real.is_file():
        return None
    if write_protection_problems(real) or write_protection_problems(real.parent):
        return None
    if os.path.realpath(real.parent) != str(real.parent):
        return None
    return real.parent


def texmf_variable_roots() -> tuple[tuple[str, Path], ...]:
    """Every TeX tree the engine names, trusted or not, for naming a pinned file.

    A pinned external input is recorded as `VARIABLE:relative/path`, never as an
    absolute path: the absolute path of a user tree contains the operator's
    account name, and this record is compared inside a double-blind release.
    """

    named: list[tuple[str, Path]] = []
    for variable in (*SYSTEM_TEXMF_ROOT_VARIABLES, *USER_TEXMF_ROOT_VARIABLES):
        value = kpsewhich_value(variable)
        for piece in value.split(os.pathsep):
            cleaned = piece.strip().lstrip("!").rstrip("/")
            if not cleaned or not os.path.isabs(cleaned):
                continue
            lexical = Path(os.path.normpath(cleaned))
            named.append((variable, lexical))
            # The name has to reach the path the recorder actually wrote.  When
            # a distribution publishes a tree under a symlink -- `TEXMFSYSVAR`
            # is a link to `/var/lib/texmf` here -- the trusted root is the
            # resolved one, and so is every input under it.
            resolved = Path(os.path.realpath(lexical))
            if resolved != lexical:
                named.append((variable, resolved))
    config = texmf_config_root()
    if config is not None:
        named.append(("TEXMFCNF", config))
    # Longest path first, so a nested tree wins over the tree that contains it.
    return tuple(sorted(named, key=lambda pair: len(str(pair[1])), reverse=True))


def external_input_name(path: Path,
                        named: Sequence[tuple[str, Path]] | None = None
                        ) -> str | None:
    """`VARIABLE:relative/path` for an external input, or None if unplaceable."""

    named = texmf_variable_roots() if named is None else named
    for variable, root in named:
        try:
            relative = Path(path).relative_to(root)
        except ValueError:
            continue
        return f"{variable}:{relative.as_posix()}"
    return None


def external_input_problems(path: Path, *, roots: Sequence[Path],
                            repo: Path | None, staged: Path) -> list[str]:
    """Why an external compiled input may not be trusted; empty means it may.

    `path` is the lexically normalised absolute path the recorder wrote, not a
    resolved one: resolving first would follow a symlink out of the tree and the
    result would then look like an ordinary system file.
    """

    problems: list[str] = []
    if not any(path.is_relative_to(root) for root in roots):
        problems.append("not inside any trusted system TeX distribution tree")
        return problems
    problems.extend(write_protection_problems(path))
    if os.path.realpath(path) != str(path):
        problems.append(f"{path} is not canonical; it resolves to "
                        f"{os.path.realpath(path)}")
    try:
        info = path.lstat()
    except OSError as error:
        problems.append(f"{path}: {error.strerror}")
        return problems
    if not stat.S_ISREG(info.st_mode):
        problems.append(f"{path} is not a regular file")
    resolved = Path(os.path.realpath(path))
    if resolved.is_relative_to(staged) or (
            repo is not None and resolved.is_relative_to(repo.resolve())):
        problems.append(f"{path} leads back into the project: {resolved}")
    return problems


def recorder_inputs(src: Path, *,
                    allowed_roots: Sequence[Path] | None = None,
                    repo: Path | None = None,
                    external_record: list[dict] | None = None) -> list[Path]:
    """Every project-local file pdfTeX actually opened, from `main.fls`.

    This is the authoritative source closure: it comes from the compiler that
    produced the submitted PDF, so it cannot disagree with what was typeset the
    way a hand-written parser can.  An earlier version of the layout gate walked
    `paper/*.tex` instead and never looked at `paper/tables/` or
    `paper/figures/`, which is exactly the gap that closed.

    It fails closed in both directions:

    * a staged input must resolve to a canonical, regular, unlinked file inside
      the staged tree, with a suffix the checkers know how to read;
    * an input outside the staged tree must come from a *trusted* system TeX
      distribution tree -- write-protected, unlinked at every component,
      canonical -- or else be individually pinned by digest in
      the trusted rules.  Silently dropping everything outside the tree,
      which is what this did two revisions ago, let a manuscript file anywhere
      on the filesystem affect the submitted PDF without appearing in the source
      archive or in any audit closure; accepting anything kpsewhich named, which
      is what it did one revision ago, let a user-writable `TEXMFHOME` do the
      same thing.

    When `external_record` is given, every accepted external input is appended
    to it as `{"name", "sha256", "bytes", "trusted"}`, so the release manifest
    can record exactly which bytes outside the project the PDF depended on.
    """

    fls = src / "main.fls"
    if not fls.is_file():
        raise RuntimeError("main.fls is missing; latexmk must run with -recorder")
    root = src.resolve()
    if allowed_roots is None:
        allowed_roots = texmf_roots(repo=repo, staged=root)
    allowed = [Path(p).resolve() for p in allowed_roots]
    named_roots = texmf_variable_roots()
    external_seen: dict[str, dict] = {}

    opened: dict[Path, None] = {}
    canonical_of: dict[str, Path] = {}
    problems: list[str] = []
    external = 0
    for line in fls.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("INPUT "):
            continue
        raw = line[len("INPUT "):].strip()
        if not raw:
            problems.append("recorded input with an empty path")
            continue
        if not Path(raw).is_absolute() and ".." in Path(raw).parts:
            problems.append(f"recorded input escapes the staged tree: {raw!r}")
            continue
        # Normalise lexically, not through the filesystem.  Resolving first
        # would follow a symlink out of the staged tree and the result would
        # then look like an ordinary system file and be skipped in silence,
        # which is the opposite of what a safety check should do.
        joined = os.path.normpath(
            raw if Path(raw).is_absolute() else os.path.join(str(root), raw))
        candidate = Path(joined)
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            # Outside the staged tree.  One way through, and no other: the file
            # sits in a trusted system distribution tree and survives the
            # ownership, mode, symlink and canonicality walk in
            # external_input_problems.
            #
            # There used to be a second way -- a digest pinned in committed code
            # could admit a file from a user tree.  It is gone.  A pin proves
            # the bytes did not change between the build and the pin; it proves
            # nothing about who can change them next, and 46 of the submission's
            # inputs were sitting in `TEXMFHOME`.  Those four packages are now
            # vendored into the staged tree instead (see VENDORED_PACKAGE_DIGESTS
            # and paper/texmf_vendor/), and compile_pdf points TEXMFHOME,
            # TEXMFVAR and TEXMFCONFIG away from the user's trees so none of them
            # can shadow the distribution.
            trouble = external_input_problems(
                candidate, roots=allowed, repo=repo, staged=root)
            if trouble:
                problems.append(
                    f"external compiled input is not from a trusted system TeX "
                    f"distribution: {raw!r} ({'; '.join(trouble)})")
                continue
            name = external_input_name(candidate, named_roots)
            if name is None:
                problems.append(
                    f"external compiled input cannot be named by any TeX "
                    f"variable: {raw!r}")
                continue
            try:
                data = candidate.read_bytes()
            except OSError as error:
                problems.append(
                    f"external compiled input cannot be read: {name!r} "
                    f"({error.strerror})")
                continue
            external += 1
            if external_record is not None and name not in external_seen:
                external_seen[name] = {
                    "name": name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                    "trusted": True,
                }
            continue
        if relative.suffix in RECORDER_IGNORED_SUFFIXES:
            continue
        actual = src / relative
        if actual.is_symlink():
            problems.append(f"recorded input is a symlink: {relative}")
            continue
        if not actual.is_file():
            problems.append(f"recorded input is missing or not a file: {relative}")
            continue
        canonical = Path(os.path.realpath(actual))
        if canonical != (root / relative):
            problems.append(
                f"recorded input is not canonical: {relative} resolves to "
                f"{canonical}")
            continue
        seen_as = canonical_of.setdefault(str(canonical), relative)
        if seen_as != relative:
            problems.append(
                f"recorded input is aliased: {relative} and {seen_as} are the "
                "same file")
            continue
        if relative.suffix not in RECORDER_SUPPORTED_SUFFIXES:
            problems.append(
                f"recorded input has an unsupported suffix: {relative}")
            continue
        opened[relative] = None
    if problems:
        raise RuntimeError(
            "the compiler's recorded input list is not reviewable: "
            + "; ".join(sorted(set(problems))))
    if not allowed and external:
        raise RuntimeError(
            "external compiled inputs were recorded but no trusted system TeX "
            "distribution tree could be derived from the runtime")
    if external_record is not None:
        external_record.extend(
            sorted(external_seen.values(), key=lambda item: item["name"]))
    return sorted(opened)


def closure(src: Path, repo: Path | None = None) -> list[Path]:
    """The files that go into `source.zip`.

    The recorder's list, minus `main.bbl` -- a reviewer regenerates that by
    running bibtex -- plus the three files bibtex needs and the style LICENSE.
    """

    opened = set(recorder_inputs(src, repo=repo))
    for extra in ("references.bib", "tmlr.bst", "LICENSE-tmlr-style",
                  *VENDORED_LICENSE_FILES):
        if (src / extra).is_file():
            opened.add(Path(extra))
    opened.discard(Path("main.bbl"))
    return sorted(opened)


# --------------------------------------------------------------------------
# packaging
# --------------------------------------------------------------------------


def write_zip(target: Path, entries: Sequence[tuple[Path, str]]) -> None:
    """Deterministic zip: sorted names, fixed timestamps, fixed permissions.

    Members are STORED, not deflated, and that is deliberate.  A deflate stream
    is whatever the linked zlib chose to emit; two hosts with different zlib
    builds, or one host after a zlib upgrade, produce different archive bytes
    from byte-identical members, so the deliverable hash in
    `release_manifest.json` would drift for a reason that has nothing to do with
    the submission.  Nothing in the declared build closure pins zlib, so the
    honest options were to pin a compressor or to stop using one.  Storing the
    members makes the archive a pure function of (names, modes, timestamps,
    bytes), all of which this project does pin.

    The cost is size: the supplement is roughly 84 MB stored against roughly
    11 MB deflated.  That is checked against the venue limit in
    `check_archive_size`, and `submissions/tmlr_2026/README.md` records the
    tradeoff.

    Built in memory and then written through atomic_write_bytes, so a
    pre-existing symlink at `target` is replaced rather than written through.
    """

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for source, arcname in sorted(entries, key=lambda pair: pair[1]):
            info = zipfile.ZipInfo(arcname, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3            # Unix, so the mode below is read
            info.external_attr = 0o644 << 16
            archive.writestr(info, source.read_bytes())
    atomic_write_bytes(target, buffer.getvalue())


#: The venue's supplementary-material ceiling, in bytes.  TMLR states 100 MB;
#: the smaller of the two readings of "MB" is used, so the check cannot pass on
#: a generous interpretation.
SUPPLEMENT_SIZE_LIMIT = 100_000_000

#: How close to the ceiling a build may get before it says so out loud.
SUPPLEMENT_SIZE_WARN = int(SUPPLEMENT_SIZE_LIMIT * 0.9)


#: The four files a release consists of.  All of them, or none.
RELEASE_DELIVERABLES = ("main.pdf", "source.zip", "supplement.zip",
                        "release_manifest.json")

MANIFEST_SCHEMA_VERSION = 2

#: Every top-level record `release_manifest.json` carries, and nothing else.
#: Listing them is what makes "validate every authoritative field" checkable:
#: a new record has to be added here, which is the moment to decide whether it
#: is authoritative and to give it a check.  There is no non-authoritative
#: field -- anything that did not need validating was removed rather than
#: quietly skipped.
MANIFEST_RECORD_CLASSES = (
    "schema_version", "target_venue", "anonymous", "build", "deliverables",
    "source_zip_contents", "supplement_zip_contents", "external_tex_inputs",
    "shipped_tool_digests", "anonymization",
)

#: The three deliverables the manifest hashes.  It never hashes itself.
HASHED_DELIVERABLES = ("main.pdf", "source.zip", "supplement.zip")

#: The build record, pinned rather than reported, so a rewritten `note` or a
#: changed epoch is a difference against a constant instead of a free-text field
#: nobody compares.
MANIFEST_BUILD_RECORD = {
    "source_date_epoch": int(SOURCE_DATE_EPOCH),
    "zip_timestamp": "1980-01-01T00:00:00",
    "note": "deliverable hashes are recorded here; this manifest never "
            "hashes itself",
}


def archive_member_records(path: Path) -> list[dict]:
    """Every member of a built archive, read out of the archive itself.

    This describes an archive; it does not authorise one.  Everywhere the gate
    needs to know what an archive *should* contain it calls
    `expected_source_members` or `expected_supplement_members`, which derive the
    answer from the staged tree, the repository and the pinned contracts.  A
    reviewer renamed a member, changed a member's bytes, added one and removed a
    required one, regenerated the manifest from the mutated archive, and passed
    the gate -- because both sides of that comparison came out of the same zip.
    """

    with zipfile.ZipFile(path) as archive:
        return [
            {"path": info.filename,
             "sha256": hashlib.sha256(archive.read(info)).hexdigest(),
             "bytes": info.file_size}
            for info in sorted(archive.infolist(), key=lambda i: i.filename)
        ]


def derive_external_inputs(repo: Path, src: Path) -> list[dict]:
    """Every external TeX input, re-derived from the compiler's own `.fls`.

    There used to be a module-level `EXTERNAL_INPUT_CACHE` that the build filled
    in and the gate read back.  A reviewer deleted one of the 249 entries before
    derivation and got a 248-entry manifest that passed, because the cache was
    the only statement of what the complete set was.

    This re-runs `recorder_inputs` against the staged tree, so the authority is
    the recorder output pdfTeX wrote during the build.  Membership, name, digest,
    byte count and trust all come from that pass and from the files themselves;
    there is nothing in between for a caller to edit.
    """

    recorded: list[dict] = []
    recorder_inputs(src, repo=repo, external_record=recorded)
    return sorted(({"name": item["name"],
                    "sha256": item["sha256"],
                    "bytes": item["bytes"],
                    "trusted": item["trusted"]}
                   for item in recorded),
                  key=lambda item: item["name"])


def source_archive_extras(repo: Path) -> dict[str, Path]:
    """The `source.zip` members that are not compiled inputs, and their origins.

    Six files: `references.bib` and `tmlr.bst`, which bibtex reads and pdfTeX
    never opens, and the four licence texts.  The names are the ones `closure()`
    adds and the origins are the ones `stage()` copies from, both from committed
    constants -- so the expectation is a statement about the repository, not
    about the staged tree or the archive.
    """

    extras = {
        "references.bib": repo / "paper/references.bib",
        "tmlr.bst": repo / "paper/tmlr_style/tmlr.bst",
        "LICENSE-tmlr-style": repo / "paper/tmlr_style/LICENSE",
    }
    for name in VENDORED_LICENSE_FILES:
        extras[name] = repo / VENDORED_DIRECTORY / name
    return extras


def expected_staged_sources(repo: Path) -> dict[str, tuple[str, int]]:
    """Every compiled input and archive extra, bound outside the staged tree.

    The digests come from `contract.COMPILED_CLOSURE`, which is committed, and
    from the repository files the six extras are copied from.  Nothing here
    reads `src/`, `source.zip` or the release manifest.

    This replaces an expectation that hashed the staged files themselves.  A
    reviewer changed a staged manuscript source *and* the matching `source.zip`
    member, regenerated the manifest, and the gate returned nothing: every side
    of every comparison had moved together, because they all came from the
    mutation.  A clean rebuild of that archive produced a different PDF.
    """

    expected = {staged: (pinned["sha256"], pinned["bytes"])
                for staged, pinned in contract.COMPILED_CLOSURE.items()}
    for arcname, origin in source_archive_extras(repo).items():
        expected[arcname] = (sha256_file(origin), origin.stat().st_size)
    return expected


def expected_source_members(repo: Path) -> dict[str, tuple[str, int]]:
    """The subset of the staged sources that `source.zip` carries.

    Everything `expected_staged_sources` pins except the compiled inputs the
    contract marks `ships_in == "neither"` -- that is `main.bbl`, which bibtex
    writes during the build and no archive ships.
    """

    return {
        name: value for name, value in expected_staged_sources(repo).items()
        if contract.COMPILED_CLOSURE.get(name, {}).get("ships_in") != "neither"
    }


def check_staged_sources(repo: Path, src: Path) -> list[str]:
    """Hold the staged tree itself to the committed digest inventory.

    Checking only `source.zip` was not enough, because the archive is built from
    the staged tree: mutate both and they agree. This binds the staged bytes to
    `contract.COMPILED_CLOSURE`, which no build step can rewrite, and separately
    requires the compiler's own recorded input list to be exactly the pinned
    set -- which is what catches a source that was removed, added or renamed
    rather than edited in place.
    """

    findings: list[str] = []
    for arcname, (digest, size) in sorted(expected_staged_sources(repo).items()):
        staged = src / arcname
        if staged.is_symlink():
            findings.append(f"staged source {arcname} is a symlink; the "
                            "compiled inputs must be real files")
            continue
        if not staged.is_file():
            findings.append(f"staged source {arcname} is missing from {src}")
            continue
        actual, info = sha256_file(staged), staged.stat()
        if actual != digest or info.st_size != size:
            findings.append(
                f"staged source {arcname} is {actual} ({info.st_size} bytes), "
                f"the committed inventory pins {digest} ({size} bytes)")

    try:
        recorded = {str(relative) for relative in recorder_inputs(src, repo=repo)}
    except (OSError, RuntimeError) as error:
        findings.append(f"the compiler's recorded input list cannot be read: "
                        f"{error!r}")
        return findings
    pinned = set(contract.COMPILED_CLOSURE)
    if recorded != pinned:
        findings.append(
            f"the compiler's recorded inputs are not the pinned set: missing "
            f"{sorted(pinned - recorded)[:4]}, unpinned "
            f"{sorted(recorded - pinned)[:4]}")
    return findings


def expected_supplement_members(repo: Path,
                                records: Sequence[dict]
                                ) -> dict[str, tuple[str, int]]:
    """What `supplement.zip` must contain, from the repository and the contracts.

    Three kinds of member, and each is bound to something outside the archive:

    * an ordinary file, hashed from the repository path `supplement_entries`
      names;
    * a deliberately transformed file or its regenerated sidecar, bound to
      `contract.CONTRACT`'s packaged digest or to `contract.sidecar_text` --
      the anonymizing transform stays explicit and pinned rather than being
      waved through;
    * a document this build generates, `ANONYMIZATION.json` and
      `SOURCE_CLOSURE.json`, derived byte for byte from the transform records
      and from `contract.COMPILED_CLOSURE`.
    """

    packaged = {record["path"]: record for record in records}
    expected: dict[str, tuple[str, int]] = {}
    for source, arcname in supplement_entries(repo):
        pinned = packaged.get(arcname)
        if pinned is not None:
            expected[arcname] = (pinned["packaged_sha256"],
                                 pinned["packaged_bytes"])
            continue
        described = arcname[:-len(".sha256")] if arcname.endswith(".sha256") else None
        if described is not None and described in packaged:
            text = contract.sidecar_text(described).encode("ascii")
            expected[arcname] = (hashlib.sha256(text).hexdigest(), len(text))
            continue
        expected[arcname] = (sha256_file(source), source.stat().st_size)

    declaration = canonical_json_bytes(anonymization_declaration(records))
    expected[ANONYMIZATION_MANIFEST] = (
        hashlib.sha256(declaration).hexdigest(), len(declaration))
    closure_document = canonical_json_bytes(derive_source_closure_document())
    expected[SOURCE_CLOSURE_NAME] = (
        hashlib.sha256(closure_document).hexdigest(), len(closure_document))
    return expected


#: The ZIP `create_system` values whose external attributes carry a Unix mode.
#: 3 is Unix; 19 is Mac OS X, which writes the same layout.  Any other creator
#: -- MS-DOS, NTFS, and the several writers that leave the field at 0 -- puts
#: something else in those bits, so a type field read from them would be noise.
UNIX_ZIP_CREATORS = (3, 19)

#: Every file type a member may claim that is not an ordinary file.  A member
#: whose mode says FIFO, device, socket, symlink or directory has no business
#: in a source or supplement archive, and what an extractor does with one is its
#: own business rather than this project's.
IRREGULAR_FILE_TYPES = {
    stat.S_IFIFO: "FIFO",
    stat.S_IFCHR: "character device",
    stat.S_IFBLK: "block device",
    stat.S_IFSOCK: "socket",
    stat.S_IFLNK: "symlink",
    stat.S_IFDIR: "directory",
}


def member_file_type(info: zipfile.ZipInfo) -> str | None:
    """Name the member's file type when it is explicitly not a regular file.

    Returns `None` for a member this build should accept: one written by a
    creator that does not record a Unix mode, one whose type field is absent,
    and one whose type field says `S_IFREG`.

    The previous version tested only `S_ISLNK` and `S_ISDIR`, so a member whose
    mode said FIFO, character device, block device or socket went through the
    whole publication gate while its name and payload matched.  Listing the
    rejected types rather than the accepted one would have had the same hole;
    this checks the type field against the full set and treats anything it does
    not recognise as irregular too.
    """

    if info.create_system not in UNIX_ZIP_CREATORS:
        return None
    mode = (info.external_attr >> 16) & 0xFFFF
    file_type = mode & 0o170000
    if file_type in (0, stat.S_IFREG):
        return None
    return IRREGULAR_FILE_TYPES.get(file_type, f"unknown type {file_type:o}")


def check_archive_inventory(name: str, path: Path,
                            expected: dict[str, tuple[str, int]]) -> list[str]:
    """Hold one built archive to an inventory derived from outside it."""

    records = archive_member_records(path)
    findings: list[str] = []
    names = [record["path"] for record in records]
    duplicated = sorted({member for member in names if names.count(member) > 1})
    if duplicated:
        findings.append(f"{name} lists {len(duplicated)} member(s) more than "
                        f"once: {duplicated[:4]}")
    with zipfile.ZipFile(path) as archive:
        irregular = sorted(
            f"{info.filename} ({described})"
            for info in archive.infolist()
            for described in [member_file_type(info)]
            if described is not None)
    if irregular:
        findings.append(f"{name} carries {len(irregular)} member(s) that are "
                        f"not regular files: {irregular[:4]}")

    actual = {record["path"]: (record["sha256"], record["bytes"])
              for record in records}
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    if missing:
        findings.append(f"{name} is missing {len(missing)} required member(s): "
                        f"{missing[:4]}")
    if extra:
        findings.append(f"{name} carries {len(extra)} member(s) nothing "
                        f"authorises: {extra[:4]}")
    drifted = sorted(
        f"{member}: archive has {actual[member][0]} ({actual[member][1]} "
        f"bytes), the staged sources imply {expected[member][0]} "
        f"({expected[member][1]} bytes)"
        for member in set(actual) & set(expected)
        if actual[member] != expected[member])
    if drifted:
        findings.append(f"{name}: {len(drifted)} member(s) are not the bytes "
                        f"they should be: {'; '.join(drifted[:3])}")
    return findings


def derive_release_manifest(repo: Path, src: Path, pending: Path) -> dict:
    """Build the manifest from the pending bytes and the pinned contracts.

    This is the only place a release manifest is constructed, and the gate below
    calls it again rather than re-serialising whatever object the build happened
    to have in hand.  That distinction is the fix for a reviewer who edited the
    build metadata, the external-input records, the anonymization digests, and
    removed a deliverable record, and got no findings at all: the old gate
    compared the manifest to itself.

    It takes no caller-supplied records at all.  Every argument is a directory;
    everything else comes from the repository, the staged tree the compiler read
    or a pinned contract.
    """

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "target_venue": "TMLR",
        "anonymous": True,
        "build": dict(MANIFEST_BUILD_RECORD),
        "deliverables": {
            name: {"sha256": sha256_file(pending / name),
                   "bytes": (pending / name).stat().st_size}
            for name in HASHED_DELIVERABLES
        },
        "source_zip_contents": archive_member_records(pending / "source.zip"),
        "supplement_zip_contents":
            archive_member_records(pending / "supplement.zip"),
        # Every compiled input that came from outside the project, named by the
        # TeX variable whose tree holds it and bound to its exact bytes.  Each
        # one came from a write-protected system distribution tree that is
        # unlinked and canonical at every path component; the build has no other
        # way to admit one, so `trusted` is true for all of them.
        "external_tex_inputs": derive_external_inputs(repo, src),
        # The digests of the shipped tools a reviewer's verification depends on.
        "shipped_tool_digests": dict(sorted(contract.SHIPPED_TOOL_DIGESTS.items())),
        # Internal provenance for the anonymizing transform.  This file is
        # release metadata and is not uploaded, so it carries the removed value
        # as well as both digests.
        "anonymization": {
            "token": ANONYMIZED_TOKEN,
            "declaration_shipped_as": ANONYMIZATION_MANIFEST,
            "transformed": derive_anonymization_records(repo),
        },
    }


def canonical_manifest_bytes(manifest: dict) -> bytes:
    """The one serialisation of a release manifest, used to write and compare."""

    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def manifest_difference(recorded: dict, rebuilt: dict) -> list[str]:
    """Which record classes differ, and how, for a readable failure."""

    lines: list[str] = []
    for key in sorted(set(recorded) | set(rebuilt)):
        if key not in recorded:
            lines.append(f"{key}: only in the rebuild")
        elif key not in rebuilt:
            lines.append(f"{key}: only in the recorded manifest")
        elif recorded[key] != rebuilt[key]:
            if isinstance(recorded[key], list) and isinstance(rebuilt[key], list):
                a = {json.dumps(x, sort_keys=True) for x in recorded[key]}
                b = {json.dumps(x, sort_keys=True) for x in rebuilt[key]}
                lines.append(f"{key}: {len(a - b)} recorded-only and "
                             f"{len(b - a)} rebuilt-only records")
            else:
                lines.append(f"{key}: differs")
    return lines


def check_anonymization_record(transforms: Sequence[dict]) -> list[str]:
    """Hold a set of anonymization records to the pinned contract.

    Applied to the *derived* records, so it is a check on the derivation rather
    than on a caller's claim: exactly one record for each contract path, no
    extras and no duplicates, exactly `TRANSFORM_RECORD_KEYS` on each, and every
    pinned field equal to what the contract pins.
    """

    findings: list[str] = []
    paths = [record["path"] for record in transforms]
    duplicated = sorted({path for path in paths if paths.count(path) > 1})
    if duplicated:
        findings.append(f"anonymization lists {duplicated} more than once")
    if set(paths) != set(contract.CONTRACT):
        findings.append(
            f"anonymization covers {sorted(set(paths))}, the contract pins "
            f"{sorted(contract.CONTRACT)}")
        return findings
    if duplicated:
        return findings
    for record in sorted(transforms, key=lambda r: r["path"]):
        if set(record) != set(TRANSFORM_RECORD_KEYS):
            findings.append(
                f"anonymization {record['path']}: keys are {sorted(record)}, "
                f"expected {sorted(TRANSFORM_RECORD_KEYS)}")
            continue
        pinned = contract.CONTRACT[record["path"]]
        for field in ("original_sha256", "original_bytes", "packaged_sha256",
                      "packaged_bytes"):
            if record.get(field) != pinned[field]:
                findings.append(
                    f"anonymization {record['path']}: {field} is "
                    f"{record.get(field)!r}, the contract pins {pinned[field]!r}")
        if record.get("field") != contract.PACKAGED_FIELD:
            findings.append(f"anonymization {record['path']}: wrong field")
        if record.get("replacement") != contract.REPLACEMENT_TOKEN:
            findings.append(f"anonymization {record['path']}: wrong replacement")
        if record.get("removed_value_class") != TRANSFORM_REMOVED_VALUE_CLASS:
            findings.append(
                f"anonymization {record['path']}: wrong removed_value_class")
        if record.get("reason") != TRANSFORM_REASON:
            findings.append(f"anonymization {record['path']}: wrong reason")
        removed = record.get("removed_value_internal_only")
        if not isinstance(removed, str) or not re.fullmatch(r"[0-9a-f]{40}",
                                                            removed):
            findings.append(
                f"anonymization {record['path']}: removed_value_internal_only "
                f"is {removed!r}, expected the 40-hex value that was replaced")
        if record.get("source_path") != record["path"]:
            findings.append(
                f"anonymization {record['path']}: source_path is "
                f"{record.get('source_path')!r}, expected the repository path "
                "the packaged copy was made from")
    return findings


def check_reported_transforms(reported: Sequence[dict],
                              derived: Sequence[dict]) -> list[str]:
    """The build's own record of what it anonymized, against the derived set.

    `reported` is never an authority here.  It is what `anonymize()` says it
    did, and this is the one place that claim is compared with what the contract
    and the repository bytes say it must have been.
    """

    if list(sorted(reported, key=lambda r: r["path"])) == list(derived):
        return []
    return ["the transform records the build reported are not the records the "
            "contract and the repository bytes imply"]


def check_shipped_closure(supplement: Path) -> list[str]:
    """The compiled closure the supplement carries must be the pinned set.

    This stays a check of its own rather than folding into the manifest
    comparison below, because the manifest records the archive's member digests:
    a build that shipped a drifted closure and then hashed it would agree with
    itself perfectly.  `contract.COMPILED_CLOSURE` lives outside both, which is
    the only reason this catches anything.
    """

    try:
        with zipfile.ZipFile(supplement) as archive:
            if SOURCE_CLOSURE_NAME not in archive.namelist():
                return [f"{SOURCE_CLOSURE_NAME} is not in supplement.zip"]
            declared = {entry["staged"]: entry
                        for entry in json.loads(
                            archive.read(SOURCE_CLOSURE_NAME))["entries"]}
    except (OSError, ValueError, KeyError, TypeError,
            zipfile.BadZipFile) as error:
        return [f"{SOURCE_CLOSURE_NAME} cannot be read from supplement.zip: "
                f"{error!r}"]

    if set(declared) != set(contract.COMPILED_CLOSURE):
        return ["the shipped source closure is not the pinned set: missing "
                f"{sorted(set(contract.COMPILED_CLOSURE) - set(declared))[:4]}, "
                f"extra {sorted(set(declared) - set(contract.COMPILED_CLOSURE))[:4]}"]
    off = sorted(
        staged for staged, entry in declared.items()
        if any(entry.get(field) != contract.COMPILED_CLOSURE[staged][field]
               for field in ("repository", "sha256", "bytes", "role",
                             "ships_in")))
    if off:
        return [f"the shipped source closure disagrees with the pinned "
                f"contract: {off[:4]}"]
    return []


def check_derived_manifest(manifest: dict) -> list[str]:
    """Reject an expected manifest that is itself degenerate.

    Byte equality is only worth as much as the expectation it compares against.
    A build that recorded no external inputs, or one it could not resolve back
    to a file, would write a staged manifest that matches the derivation exactly
    and publish anyway.  These are the conditions the old field-by-field gate
    rejected, kept here and applied to the derived document.
    """

    findings: list[str] = []
    if set(manifest) != set(MANIFEST_RECORD_CLASSES):
        findings.append(
            f"derived manifest top-level keys: missing "
            f"{sorted(set(MANIFEST_RECORD_CLASSES) - set(manifest))}, unexpected "
            f"{sorted(set(manifest) - set(MANIFEST_RECORD_CLASSES))}")
        return findings

    if manifest["schema_version"] != MANIFEST_SCHEMA_VERSION:
        findings.append(f"derived manifest schema_version is "
                        f"{manifest['schema_version']!r}")
    if manifest["target_venue"] != "TMLR" or manifest["anonymous"] is not True:
        findings.append("derived manifest target_venue/anonymous are not the "
                        "pinned values")
    if manifest["build"] != MANIFEST_BUILD_RECORD:
        findings.append("derived manifest build record is not the pinned record")

    if set(manifest["deliverables"]) != set(HASHED_DELIVERABLES):
        findings.append(
            f"derived manifest deliverables are "
            f"{sorted(manifest['deliverables'])}, expected "
            f"{sorted(HASHED_DELIVERABLES)}")
    for name, record in sorted(manifest["deliverables"].items()):
        if not _is_sha256(record.get("sha256")) or record.get("bytes", 0) <= 0:
            findings.append(f"derived manifest {name} record is malformed: "
                            f"{record!r}")

    for key in ("source_zip_contents", "supplement_zip_contents"):
        members = manifest[key]
        if not members:
            findings.append(f"derived manifest {key} is empty")
        if len({member["path"] for member in members}) != len(members):
            findings.append(f"derived manifest {key} lists a member twice")
        if any(not _is_sha256(member.get("sha256"))
               or int(member.get("bytes", -1)) < 0 for member in members):
            findings.append(f"derived manifest {key} has a malformed record")

    external = manifest["external_tex_inputs"]
    if not external or any(item.get("trusted") is not True for item in external):
        findings.append(
            "derived manifest external_tex_inputs is empty or records an input "
            "that did not come from a trusted system TeX distribution tree")
    if any(not _is_sha256(item.get("sha256")) or item.get("bytes", 0) <= 0
           or ":" not in str(item.get("name"))
           or str(item.get("name")).startswith("/") for item in external):
        findings.append("derived manifest external_tex_inputs has a malformed "
                        "record, which is how an input that no longer resolves "
                        "on disk shows up")

    if manifest["shipped_tool_digests"] != dict(
            sorted(contract.SHIPPED_TOOL_DIGESTS.items())):
        findings.append("derived manifest shipped_tool_digests disagree with "
                        "the pinned contract")
    return findings


def describe_manifest_mismatch(staged: dict, expected: dict) -> list[str]:
    """Say which records of the staged manifest differ from the derived one.

    The verdict is the byte comparison in `check_pending_release`; this exists
    so the failure names the record class instead of printing two 95 kB
    documents.  It parses attacker-controlled JSON, so every lookup is defensive
    and a record of the wrong shape is reported as such rather than raising.
    """

    findings: list[str] = []
    got, want = set(staged), set(expected)
    if got != want:
        findings.append(f"top-level keys: missing {sorted(want - got)}, "
                        f"unexpected {sorted(got - want)}")

    recorded_deliverables = staged.get("deliverables")
    if not isinstance(recorded_deliverables, dict):
        findings.append(f"deliverables is {type(recorded_deliverables).__name__}, "
                        "expected an object")
    else:
        if set(recorded_deliverables) != set(expected["deliverables"]):
            findings.append(
                f"deliverables: {sorted(recorded_deliverables)}, expected "
                f"{sorted(expected['deliverables'])}")
        for name, want_record in sorted(expected["deliverables"].items()):
            got_record = recorded_deliverables.get(name)
            if not isinstance(got_record, dict):
                findings.append(
                    f"{name}: the manifest record is a "
                    f"{type(got_record).__name__}, expected an object")
                continue
            if (got_record.get("sha256") != want_record["sha256"]
                    or got_record.get("bytes") != want_record["bytes"]):
                findings.append(
                    f"{name}: staged bytes are {want_record['sha256']} "
                    f"({want_record['bytes']} bytes), the manifest says "
                    f"{got_record.get('sha256')} ({got_record.get('bytes')} "
                    f"bytes)")

    for name, key in (("source.zip", "source_zip_contents"),
                      ("supplement.zip", "supplement_zip_contents")):
        members = staged.get(key)
        if not isinstance(members, list) or any(
                not isinstance(member, dict) for member in members):
            findings.append(f"{name}: {key} is not a list of records")
            continue
        recorded = {member.get("path"): (member.get("sha256"),
                                         member.get("bytes"))
                    for member in members}
        actual = {member["path"]: (member["sha256"], member["bytes"])
                  for member in expected[key]}
        if len(recorded) != len(members):
            findings.append(f"{name}: the manifest lists a member twice")
        if set(actual) != set(recorded):
            missing = sorted(str(path) for path in set(recorded) - set(actual))
            extra = sorted(str(path) for path in set(actual) - set(recorded))
            findings.append(
                f"{name}: member list disagrees with the manifest "
                f"(missing {missing[:4]}, unrecorded {extra[:4]})")
        drifted = sorted(
            f"{member}: archive has {actual[member][0]} ({actual[member][1]} "
            f"bytes), manifest says {recorded[member][0]} "
            f"({recorded[member][1]} bytes)"
            for member in set(actual) & set(recorded)
            if actual[member] != recorded[member])
        if drifted:
            findings.append(f"{name}: {len(drifted)} member(s) disagree with "
                            f"the manifest: {'; '.join(drifted[:3])}")

    if staged.get("schema_version") != expected["schema_version"]:
        findings.append(f"manifest schema_version is "
                        f"{staged.get('schema_version')!r}")
    if (staged.get("target_venue") != expected["target_venue"]
            or staged.get("anonymous") is not expected["anonymous"]):
        findings.append("manifest target_venue/anonymous are not the pinned "
                        "values")
    build = staged.get("build")
    if not isinstance(build, dict):
        findings.append(f"manifest build is {type(build).__name__}, expected an "
                        "object")
    elif build != expected["build"]:
        if build.get("source_date_epoch") != expected["build"]["source_date_epoch"]:
            findings.append("manifest build.source_date_epoch is not the pinned "
                            "value")
        else:
            findings.append(f"manifest build record differs: {build!r}")

    external = staged.get("external_tex_inputs")
    if not isinstance(external, list) or any(
            not isinstance(item, dict) for item in external):
        findings.append("manifest external_tex_inputs is not a list of records")
    else:
        if not external or any(item.get("trusted") is not True
                               for item in external):
            findings.append(
                "manifest external_tex_inputs is empty or records an input that "
                "did not come from a trusted system TeX distribution tree")
        if any(not _is_sha256(item.get("sha256")) or item.get("bytes", 0) <= 0
               or str(item.get("name")).startswith("/") for item in external):
            findings.append("manifest external_tex_inputs has a malformed record")
        if external != expected["external_tex_inputs"]:
            findings.append(
                "manifest external_tex_inputs disagree with the files those "
                "names resolve to on disk")

    if staged.get("shipped_tool_digests") != expected["shipped_tool_digests"]:
        findings.append("manifest shipped_tool_digests disagree with the pinned "
                        "contract")
    if staged.get("anonymization") != expected["anonymization"]:
        findings.append("manifest anonymization metadata disagrees with the "
                        "pinned contract")
    return findings


def check_pending_release(repo: Path, src: Path, pending: Path,
                          reported: Sequence[dict] = ()) -> list[str]:
    """The last gate before anything is published, and it is authoritative.

    It derives a complete canonical manifest from the pending bytes, the pending
    archives, the pinned dependency/closure/tool contracts, the build metadata
    and the anonymization contract -- then requires the
    `release_manifest.json` **read back from disk** to equal it byte for byte.

    The previous version took the build's in-memory manifest object and
    compared parts of it to the archives.  A reviewer changed the build
    metadata, the external-input names, hashes and sizes, and the anonymization
    digests; removed a deliverable record; and replaced the staged manifest file
    while keeping the original object -- and got no findings.  Every one of
    those is now a byte difference against an independently derived expectation,
    and no field escapes because the comparison is over the whole document.

    Four things are checked outside that byte comparison, because a manifest
    derived from the archives cannot catch them:

    * the staged tree itself, against `expected_staged_sources`
      (`check_staged_sources`).  Checking only the archive was not enough: the
      archive is built from the staged tree, so a reviewer who changed both --
      and then regenerated the manifest -- moved every side of every comparison
      at once.  The digests come from `contract.COMPILED_CLOSURE`, which is
      committed, and the compiler's own recorded input list must be exactly the
      pinned set;
    * the two archive inventories, against `expected_source_members` and
      `expected_supplement_members` -- derived from the committed closure, the
      repository and the pinned contracts, never from the archive.  Re-hashing
      an archive and comparing it to itself proved nothing: a renamed, added,
      removed, duplicated or rewritten member survived it;
    * the closure the supplement ships (`check_shipped_closure`);
    * the derived document's own validity (`check_derived_manifest`);
    * the transform records the build reported (`check_reported_transforms`),
      which are compared against the derived set and never used as authority.

    `reported` is the only caller-supplied argument and it is never trusted --
    it exists so that a build whose own account of the anonymizing transform
    disagrees with the contract is a finding rather than a silent difference.
    """

    findings: list[str] = []
    for name in RELEASE_DELIVERABLES:
        path = pending / name
        if not path.is_file() or path.is_symlink():
            findings.append(f"{name} is missing from the staged release")
    if findings:
        return findings

    try:
        records = derive_anonymization_records(repo)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        return findings + [f"the anonymization records cannot be derived: "
                           f"{error!r}"]
    findings.extend(check_anonymization_record(records))
    findings.extend(check_reported_transforms(reported, records))
    findings.extend(check_shipped_closure(pending / "supplement.zip"))
    try:
        findings.extend(check_staged_sources(repo, src))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        findings.append(f"the staged sources cannot be checked against the "
                        f"committed inventory: {error!r}")

    try:
        findings.extend(check_archive_inventory(
            "source.zip", pending / "source.zip",
            expected_source_members(repo)))
        findings.extend(check_archive_inventory(
            "supplement.zip", pending / "supplement.zip",
            expected_supplement_members(repo, records)))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        findings.append(f"the expected archive inventories cannot be derived: "
                        f"{error!r}")

    try:
        expected = derive_release_manifest(repo, src, pending)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        return findings + [f"the expected manifest cannot be derived: {error!r}"]
    findings.extend(check_derived_manifest(expected))

    staged_bytes = (pending / "release_manifest.json").read_bytes()
    if staged_bytes == canonical_manifest_bytes(expected):
        return findings

    findings.append("the staged release_manifest.json is not the manifest these "
                    "bytes imply")
    try:
        staged = json.loads(staged_bytes)
    except ValueError as error:
        findings.append(f"  and it does not parse: {error!r}")
        return findings
    if not isinstance(staged, dict):
        findings.append(f"  and it is a {type(staged).__name__}, not an object")
        return findings
    findings.extend("  " + line
                    for line in describe_manifest_mismatch(staged, expected))
    return findings


class ReleaseRecoveryError(RuntimeError):
    """Publication failed *and* the previous generation could not be restored.

    Carries the exact durable backup path and every individual restoration
    failure, because at that point the only honest thing to report is where the
    old bytes are and what stopped them going back.
    """

    def __init__(self, backup: Path, failures: Sequence[str],
                 cause: BaseException) -> None:
        super().__init__(
            "the release could not be published AND the previous generation "
            "could not be fully restored.\n"
            f"  original failure: {cause!r}\n"
            f"  recovery copy retained at: {backup}\n"
            + "".join(f"  unrestored: {failure}\n" for failure in failures))
        self.backup = backup
        self.failures = list(failures)
        self.cause = cause


def remove_if_present(path: Path) -> None:
    """Remove a path if it is there, following nothing."""

    try:
        path.unlink()
    except FileNotFoundError:
        pass


def snapshot_deliverables(out: Path, backup: Path) -> dict[str, dict]:
    """Record what every deliverable path is, before anything is replaced.

    All four, unconditionally -- not only the ones that exist, and not only the
    ones a later loop happens to reach.  A path is one of three things: a
    symlink (recorded by target, never read through), a regular file (copied
    into `backup` with its mode), or absent.
    """

    snapshot: dict[str, dict] = {}
    for name in RELEASE_DELIVERABLES:
        target = out / name
        if target.is_symlink():
            snapshot[name] = {"kind": "symlink", "target": os.readlink(target)}
        elif target.exists():
            info = target.stat()
            shutil.copy2(target, backup / name)
            snapshot[name] = {"kind": "file",
                              "sha256": sha256_file(target),
                              "bytes": info.st_size,
                              "mode": stat.S_IMODE(info.st_mode)}
        else:
            snapshot[name] = {"kind": "absent"}
    return snapshot


#: How many random names to try before giving up on finding a free one.
UNIQUE_NAME_ATTEMPTS = 64


def unique_scratch_symlink(directory: Path, prefix: str, target: str) -> Path:
    """Create a symlink at a fresh name this call owns, and return that name.

    `os.symlink` is the test and the creation in one step: it raises
    `FileExistsError` rather than replacing anything, so no path that already
    existed is ever touched, and the caller may safely remove exactly the path
    it gets back.
    """

    for _ in range(UNIQUE_NAME_ATTEMPTS):
        candidate = directory / f"{prefix}.{secrets.token_hex(8)}"
        try:
            os.symlink(target, candidate)
        except FileExistsError:
            continue
        return candidate
    raise RuntimeError(
        f"could not find an unused scratch name under {directory} after "
        f"{UNIQUE_NAME_ATTEMPTS} attempts")


def fsync_directory(path: Path) -> None:
    """Flush a directory entry, so a rename into it is on the medium."""

    handle = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def restore_deliverable(name: str, record: dict, out: Path, backup: Path) -> None:
    """Put one path back exactly as `snapshot_deliverables` found it."""

    target = out / name
    if record["kind"] == "file":
        handle, temporary = tempfile.mkstemp(dir=str(out),
                                             prefix=f".{name}.restore.")
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write((backup / name).read_bytes())
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, record["mode"])
            os.replace(temporary, target)
        except BaseException:
            remove_if_present(Path(temporary))
            raise
    elif record["kind"] == "symlink":
        # Recreate the link.  Never write through it: those bytes are not ours.
        #
        # The scratch name is unique and owned by this call.  It used to be the
        # fixed `.<name>.restore-link`, which the rollback deleted before using
        # -- so an unrelated file that happened to have that name was destroyed
        # by a rollback that was otherwise correct.  `os.symlink` fails with
        # EEXIST rather than overwriting, which makes creation the test, and
        # only the path this call created is ever removed.
        temporary = unique_scratch_symlink(out, f".{name}.restore-link",
                                           record["target"])
        try:
            os.replace(temporary, target)
        except BaseException:
            remove_if_present(temporary)
            raise
    elif target.is_symlink() or target.exists():
        target.unlink()


def verify_restored(name: str, record: dict, out: Path) -> str | None:
    """Confirm one path really is what the snapshot said; describe it if not."""

    target = out / name
    if record["kind"] == "file":
        if target.is_symlink():
            return f"{name}: expected a regular file, found a symlink"
        if not target.is_file():
            return f"{name}: expected a regular file, it is missing"
        actual, info = sha256_file(target), target.stat()
        if actual != record["sha256"] or info.st_size != record["bytes"]:
            return (f"{name}: restored bytes are {actual} ({info.st_size} "
                    f"bytes), snapshot was {record['sha256']} "
                    f"({record['bytes']} bytes)")
        if stat.S_IMODE(info.st_mode) != record["mode"]:
            return (f"{name}: restored mode is {stat.S_IMODE(info.st_mode):o}, "
                    f"snapshot was {record['mode']:o}")
        return None
    if record["kind"] == "symlink":
        if not target.is_symlink():
            return f"{name}: expected a symlink, it is not one"
        if os.readlink(target) != record["target"]:
            return (f"{name}: symlink points at {os.readlink(target)!r}, "
                    f"snapshot was {record['target']!r}")
        return None
    if target.is_symlink() or target.exists():
        return f"{name}: expected to be absent, it exists"
    return None


#: The prefix of a retained recovery directory.  A prefix, not a fixed name:
#: `mkdtemp` appends a unique suffix, so nothing existing is ever reused.
RECOVERY_PREFIX = ".release-recovery-"

#: What the retained recovery directory says about itself.
RECOVERY_SNAPSHOT_NAME = "RECOVERY.json"


def recovery_metadata(snapshot: dict, problems: Sequence[str],
                      failure: BaseException | None,
                      stage_name: str = "retained") -> bytes:
    """What a recovery directory says about itself.

    `stage_name` is `"prepublication"` for the copy written before the first
    public replacement and `"retained"` for the rewrite after a rollback.  The
    first one is what makes an abandoned backup interpretable at all: it names
    every deliverable, says whether it was a regular file, a symlink or absent,
    and gives the link target for a symlink -- none of which can be recovered
    from the directory contents, because a symlink and an absent entry leave no
    file behind.
    """

    explanation = {
        "prepublication":
            "The release generation that was public when this publication "
            "started, copied here before anything was replaced. Each entry in "
            "`snapshot` with kind 'file' is here under its own name; an entry "
            "with kind 'symlink' or 'absent' has no file here, and `snapshot` "
            "is the only record of what it was. If this directory still exists "
            "the publication did not finish cleanly.",
        "retained":
            "The previous release generation, retained because publication "
            "failed and the rollback did not fully verify. Each file named in "
            "`snapshot` with kind 'file' is here under its own name; an entry "
            "with kind 'symlink' or 'absent' has no file here because there "
            "were no bytes of ours to keep.",
    }[stage_name]
    return canonical_json_bytes({
        "what_this_is": explanation,
        "stage": stage_name,
        "original_failure": repr(failure) if failure is not None else None,
        "unrestored": list(problems),
        "snapshot": {name: dict(record) for name, record in snapshot.items()},
    })


def write_recovery_metadata(backup: Path, snapshot: dict,
                            problems: Sequence[str] = (),
                            failure: BaseException | None = None,
                            stage_name: str = "retained") -> None:
    """Put `RECOVERY.json` **inside the backup**, durably.

    Called twice.  Once before the first public replacement, so that any backup
    left behind by any later fault is independently interpretable; once again
    after a rollback, to add what could not be restored.  Writing it only at
    retention time was the mistake: a metadata failure then left a directory of
    regular files with no record that `main.pdf` had been a symlink or that
    `supplement.zip` had been absent.

    The bytes and the directory entry are both fsynced before this returns.
    """

    handle, temporary = tempfile.mkstemp(dir=str(backup),
                                         prefix=f".{RECOVERY_SNAPSHOT_NAME}.")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(recovery_metadata(snapshot, problems, failure,
                                           stage_name))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, backup / RECOVERY_SNAPSHOT_NAME)
    except BaseException:
        remove_if_present(Path(temporary))
        raise
    fsync_directory(backup)


def retain_recovery(out: Path, backup: Path, snapshot: dict,
                    problems: list[str], failure: BaseException,
                    relocated: list[Path] | None = None) -> Path:
    """Move the prepublication backup somewhere durable, in one step.

    Three ways earlier versions lost or split data, all reproduced:

    * a fixed `.release-recovery` name plus `rmtree` destroyed an earlier failed
      generation's only copy, and `shutil.move` onto a pre-existing **symlink**
      of that name followed the link out of the output tree;
    * moving the backup **entry by entry** into a new directory meant a failure
      on the second move left three files in `.previous` and one in a directory
      nobody was told about, with no metadata anywhere;
    * writing the metadata **after** those moves meant a failure there left the
      reported backup empty and all four files unreported.

    So the directory is now moved whole.  The metadata is written and fsynced
    inside `.previous` first, and then exactly one `os.rename` relocates the
    complete directory to a name that did not exist.  A rename of a directory
    within one filesystem is atomic, so there is no state in which part of the
    backup is here and part of it is there: either the whole thing moved, or
    none of it did and `.previous` is still complete and self-describing.

    The metadata update here only *adds* what the rollback could not restore.
    A durable copy already went in before the first public replacement, so a
    failure updating it is recorded as one more problem rather than aborting
    retention -- the directory is interpretable either way.

    `relocated` is an out-parameter: the destination is appended to it the
    instant the rename succeeds, so a caller handling a later failure knows
    exactly where the bytes went instead of having to guess from a directory
    listing.

    This is caught-failure integrity, not crash atomicity: see `publish_release`.
    """

    relocated = [] if relocated is None else relocated

    # `problems` is the caller's list and is appended to in place: a note about
    # a failed metadata update has to reach the error the caller raises, not a
    # local copy that dies here.
    try:
        write_recovery_metadata(backup, snapshot, problems, failure,
                                stage_name="retained")
    except BaseException as error:
        problems.append(
            f"the recovery metadata could not be updated with the rollback "
            f"result ({error!r}); the copy written before publication began is "
            f"still in place")
    for _ in range(UNIQUE_NAME_ATTEMPTS):
        durable = out / f"{RECOVERY_PREFIX}{secrets.token_hex(8)}"
        if os.path.lexists(durable):
            continue
        # One move, whole directory.  If this raises, `backup` is untouched and
        # still complete, and `publish_release` reports that path instead.
        os.rename(backup, durable)
        # The rename has happened: from here on the bytes are at `durable` and
        # nowhere else, so record that before anything else can fail.  The
        # parent fsync used to come first, and when it raised, the caller fell
        # back to scanning the output directory -- which could name an older
        # recovery generation as the primary backup, or, if the scan failed
        # too, omit the new destination entirely.
        relocated.append(durable)
        fsync_directory(out)
        return durable
    raise RuntimeError(
        f"could not find an unused recovery name under {out} after "
        f"{UNIQUE_NAME_ATTEMPTS} attempts")


def residual_recovery_problem(backup: Path) -> str | None:
    """Describe an unrecovered backup left where this run wants to work.

    `publish_release` starts by resetting `.previous`, which empties it.  That
    is right when it holds nothing but a previous run's already-relocated
    scratch, and catastrophic when a retention failure left it holding the only
    copy of the previous generation -- which is exactly what `RECOVERY.json`
    inside it means.  So the presence of that file stops the run.
    """

    try:
        if not backup.is_dir() or backup.is_symlink():
            return None
    except OSError as error:
        return (f"{backup} cannot be inspected ({error!r}); it may hold an "
                "unrecovered previous generation. Resolve it by hand before "
                "publishing again.")
    kept, trouble = directory_contents(backup)
    if trouble is not None:
        return (f"{trouble}; it may hold an unrecovered previous generation. "
                "Resolve it by hand before publishing again.")
    interesting = [name for name in kept
                   if name == RECOVERY_SNAPSHOT_NAME
                   or name in RELEASE_DELIVERABLES]
    if not interesting:
        return None
    return (f"{backup} still holds an unrecovered previous generation "
            f"({kept}); publishing would erase it. Move or remove that "
            f"directory deliberately, then publish again.")


def directory_contents(path: Path) -> tuple[list[str], str | None]:
    """The entry names, or an explanation of why they could not be read.

    Every recovery path is inspected through this.  A directory that cannot be
    enumerated used to raise straight out of the failure handler, so a
    `PermissionError` on one unrelated candidate replaced the structured
    `ReleaseRecoveryError` and took the known backup path down with it.  An
    unreadable directory is a recovery location that has to be reported, not a
    reason to stop reporting.
    """

    try:
        return sorted(entry.name for entry in path.iterdir()), None
    except OSError as error:
        return [], f"{path} could not be enumerated: {error!r}"


def recovery_locations(out: Path, backup: Path,
                       troubles: list[str] | None = None) -> list[Path]:
    """Every directory under `out` that may hold recovery material.

    Used when retention itself failed, so the error can name all of them
    instead of guessing one.  The backup comes first when it still exists,
    because that is where the files were last known to be.  Best-effort
    throughout: a candidate that cannot be read is included rather than
    skipped, and never cleaned up.

    `troubles` is an out-parameter for inspection failures.  Returning a short
    list and swallowing the reason was not good enough: when the output
    directory itself could not be enumerated, the caller had no way to say so,
    and an operator reading the error could not tell "there is nothing else"
    from "nothing else could be looked at".
    """

    troubles = [] if troubles is None else troubles
    found: list[Path] = []
    try:
        usable = backup.is_dir() and not backup.is_symlink()
    except OSError:
        usable = True                       # unreadable, so assume it matters
    if usable:
        names, trouble = directory_contents(backup)
        if names or trouble is not None:
            found.append(backup)
    try:
        entries = sorted(out.iterdir())
    except OSError as error:
        troubles.append(f"{out} could not be enumerated: {error!r}; other "
                        "recovery directories may exist there")
        return found
    for entry in entries:
        if not entry.name.startswith(RECOVERY_PREFIX):
            continue
        try:
            if entry.is_symlink() or not entry.is_dir():
                continue
        except OSError:
            found.append(entry)             # cannot tell; report it anyway
            continue
        found.append(entry)
    return found


def publish_release(pending: Path, out: Path) -> None:
    """Replace the four deliverables as a set, or leave every one of them alone.

    Two reviewer attacks got through the previous version, and both came from
    the same mistake: the rollback trusted a list of names the *successful*
    writes had appended to.

    * An exception raised after the second replacement had already completed
      left `source.zip` new beside three old files, because that name had not
      yet been appended.
    * An exception during a rollback write aborted the rollback, left the
      already-replaced files in place, and then deleted the backup directory in
      a `finally`, destroying the only copy of the old bytes.

    So the rollback no longer consults what succeeded.  It restores **all four
    paths from the complete prepublication snapshot**, unconditionally: a path
    that was a regular file goes back with its bytes and mode, one that was a
    symlink is recreated as a symlink, and one that was absent is removed.  Each
    is attempted independently, so one failure does not skip the other three,
    and each is then *verified* against the snapshot.

    Verification is attempted independently too, for the same reason.  A third
    attack raised inside the first verification call: the loop stopped, the
    other three paths were never checked, the exception escaped as a plain
    `OSError`, and the mixed public set that was left had its only backup inside
    the staging directory -- which this function then deleted.

    The backup is deleted only when all four verify.  If any does not, it is
    moved whole into a fresh uniquely named recovery directory
    (`retain_recovery`, which never deletes, reuses or follows an existing path,
    writes the metadata inside the backup first and then relocates it with one
    atomic rename), and this raises `ReleaseRecoveryError` naming that exact
    path and every failed restoration.  It does not claim the old generation is
    back.  If even that move fails, the staging directory is kept, the error
    names the backup inside it, and that backup already carries its own
    `RECOVERY.json`.

    A residual backup from such a failure is never destroyed by a retry.  This
    refuses to start while one is present, because `reset_build_directory` would
    otherwise empty the only remaining copy of a previous generation.  Clearing
    it is a deliberate human act.

    Nothing reads or writes through an output symlink in either direction:
    `atomic_write_bytes` replaces the name via `os.replace`, and the restore
    recreates the link rather than writing to its target.

    Scope, stated honestly: this covers **caught application failures** -- an
    exception from any replacement, restoration or verification step.  It is
    **not** crash or power-loss consistency.  A machine that dies between two
    `os.replace` calls leaves a mixed set, and only a single atomic generation
    switch -- a versioned directory and one pointer rename -- would fix that.
    That would change the documented output paths, so it is not implemented, and
    this docstring does not pretend otherwise.
    """

    backup = pending / ".previous"
    residual = residual_recovery_problem(backup)
    if residual is not None:
        raise ReleaseRecoveryError(
            backup, [residual],
            RuntimeError("a previous publication left an unrecovered backup"))
    reset_build_directory(backup)
    snapshot = snapshot_deliverables(out, backup)

    # Durable before the first public byte moves.  A symlink entry and an absent
    # entry leave no file in the backup, so without this the only record of what
    # they were lives in a Python dict that dies with the process -- and a
    # reviewer produced exactly that: a retained directory of regular files with
    # no `RECOVERY.json`, no link target for the `main.pdf` that had been a
    # symlink, and no sign that `supplement.zip` had been absent.
    #
    # If this write or its fsync fails, nothing public has been touched, so the
    # honest thing is to stop here and say so.
    try:
        write_recovery_metadata(backup, snapshot,
                                stage_name="prepublication")
    except BaseException as error:
        raise ReleaseRecoveryError(backup, [
            "the prepublication recovery record could not be written, so no "
            "deliverable was replaced and the public release is unchanged: "
            f"{error!r}",
            f"the copied backup is at {backup}",
        ], error) from error

    try:
        for name in RELEASE_DELIVERABLES:
            atomic_write_bytes(out / name, (pending / name).read_bytes())
    except BaseException as failure:
        problems: list[str] = []
        for name in RELEASE_DELIVERABLES:
            try:
                restore_deliverable(name, snapshot[name], out, backup)
            except BaseException as error:      # keep going; report them all
                problems.append(f"{name}: restore raised {error!r}")
        for name in RELEASE_DELIVERABLES:
            # Verification is as fallible as restoration -- it stats, reads and
            # hashes.  A raise here used to abort the loop, escape as a plain
            # OSError and leave a mixed public set whose only backup was inside
            # the staging directory this function then deleted.
            try:
                mismatch = verify_restored(name, snapshot[name], out)
            except BaseException as error:
                problems.append(f"{name}: verification raised {error!r}")
                continue
            if mismatch is not None:
                problems.append(mismatch)
        if not problems:
            shutil.rmtree(pending, ignore_errors=True)
            raise
        relocated: list[Path] = []
        try:
            durable = retain_recovery(out, backup, snapshot, problems, failure,
                                      relocated)
        except BaseException as error:
            # Last resort: the staging directory stays, because the backup
            # inside it may be the only copy of the previous generation.  Name
            # every place that holds recovery material rather than assuming one.
            #
            # `relocated` is authoritative and comes first.  If the rename
            # succeeded and only the parent fsync failed, the bytes are at that
            # path and at no other, and a directory scan must not be allowed to
            # put an older generation in front of it -- or, when the scan itself
            # fails, to leave it out of the report altogether.
            problems.append(
                f"the recovery copy could not be moved to a durable directory: "
                f"{error!r}")
            places = list(relocated)
            if relocated:
                problems.append(
                    f"the backup directory was moved to {relocated[-1]} before "
                    f"the failure; that is the current generation")
            troubles: list[str] = []
            try:
                for place in recovery_locations(out, backup, troubles):
                    if place not in places:
                        places.append(place)
            except BaseException as scan:   # discovery must never take over
                troubles.append(f"the other recovery locations could not be "
                                f"enumerated: {scan!r}")
                if backup not in places:
                    places.append(backup)
            problems.extend(troubles)
            for place in places:
                names, trouble = directory_contents(place)
                problems.append(
                    f"recovery material is at {place}: {names}"
                    if trouble is None
                    else f"recovery material may be at {place}, but {trouble}")
            if not places:
                problems.append(
                    "no recovery material could be located, which should not "
                    "happen; inspect the output directory by hand")
            raise ReleaseRecoveryError(places[0] if places else backup,
                                       problems, failure) from failure
        shutil.rmtree(pending, ignore_errors=True)
        raise ReleaseRecoveryError(durable, problems, failure) from failure
    shutil.rmtree(pending, ignore_errors=True)


def check_archive_size(path: Path, limit: int = SUPPLEMENT_SIZE_LIMIT
                       ) -> list[str]:
    """Refuse to publish a supplement the venue would reject.

    Storing rather than deflating trades roughly 73 MB of compression for an
    archive whose bytes do not depend on an unpinned zlib.  That trade is only
    available while the result stays under the limit, so the limit is enforced
    here rather than assumed.
    """

    size = path.stat().st_size
    if size >= limit:
        return [f"{path.name} is {size} bytes, at or over the venue's "
                f"{limit}-byte supplementary-material limit"]
    if size >= SUPPLEMENT_SIZE_WARN:
        print(f"WARNING: {path.name} is {size} bytes, within 10% of the "
              f"{limit}-byte venue limit")
    return []


def scrub(entries: Iterable[tuple[Path, str]]) -> list[str]:
    """Return every forbidden-string hit; an empty list means the bundle is clean."""

    findings: list[str] = []
    for source, arcname in entries:
        if source.suffix in {".pdf", ".whl", ".png", ".jpg", ".zip"}:
            continue
        try:
            text = source.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for match in FORBIDDEN_RE.finditer(line):
                if citation_exempt(arcname, match, line):
                    continue
                findings.append(f"{arcname}:{number}: {match.group(0)!r} in {line.strip()[:120]!r}")
    return findings


def _replace_revision_field(data: bytes, arcname: str) -> tuple[bytes, str]:
    """Replace exactly one ``"git_revision": "<40 hex>"`` value, byte-targeted.

    Everything outside the replaced value is preserved byte for byte, so the
    packaged file differs from the original evidence in that string and nowhere
    else.  Refuses to guess: the field must occur exactly once.
    """

    pattern = re.compile(
        rb'("' + ANONYMIZED_FIELD.encode("ascii") + rb'"\s*:\s*")([0-9a-f]{40})(")'
    )
    matches = pattern.findall(data)
    if len(matches) != 1:
        raise RuntimeError(
            f"{arcname}: expected exactly one {ANONYMIZED_FIELD} field with a "
            f"40-hex value, found {len(matches)}"
        )
    original_value = matches[0][1].decode("ascii")
    replaced = pattern.sub(
        rb"\g<1>" + ANONYMIZED_TOKEN.encode("ascii") + rb"\g<3>", data, count=1
    )
    return replaced, original_value


#: Every key an anonymization transform record carries, and nothing else.
#: Enforced on the derived set, so a record that grew a field or lost one is a
#: finding rather than a difference nobody looks at.
TRANSFORM_RECORD_KEYS = (
    "path", "source_path", "field", "removed_value_class",
    "removed_value_internal_only", "replacement", "original_sha256",
    "packaged_sha256", "original_bytes", "packaged_bytes", "reason",
)

TRANSFORM_REMOVED_VALUE_CLASS = (
    "version-control revision identifier (40-hex Git object id); "
    "resolves in the project's public repository to a named author"
)

TRANSFORM_REASON = (
    "double-blind anonymity: the value identifies the authors "
    "through the public repository"
)

#: The prose of the shipped declaration, hoisted for the same reason as
#: `CLOSURE_WHAT_THIS_IS`: the gate derives the document and compares bytes.
DECLARATION_PROSE = {
    "what_this_is": (
        "This supplement is anonymized for double-blind review. The files "
        "listed below are MODIFIED COPIES of the study's evidence, not the "
        "original evidence bytes. In each one, exactly one metadata string "
        "was replaced; no numerical value, key, ordering or any other byte "
        "was changed."
    ),
    "how_to_tell_it_did_not_change_the_numbers": (
        "Regenerate the published tables, figures and CSVs from the "
        "packaged aggregate with tools/transport_artifact_expectations.py. "
        "They reproduce byte-identically, which they could not do if the "
        "redaction had perturbed anything the artifacts depend on."
    ),
    "sidecars": (
        "The .sha256 sidecars next to the transformed files were "
        "regenerated over the packaged bytes. The .provenance.json records "
        "next to them were NOT regenerated: they truthfully describe the "
        "original evidence, whose digest is given below as original_sha256."
    ),
}


def anonymization_declaration(records: Sequence[dict]) -> dict:
    """The reviewer-facing `ANONYMIZATION.json`, from the transform records."""

    return {
        "schema_version": 1,
        **DECLARATION_PROSE,
        "replacement_token_is_not_a_revision": (
            f"{ANONYMIZED_TOKEN!r} is a placeholder string. It is not a commit, "
            "not a hash, and not a substitute provenance identifier."
        ),
        "transformed": [
            {k: v for k, v in record.items()
             if k not in {"removed_value_internal_only", "source_path"}}
            for record in sorted(records, key=lambda r: r["path"])
        ],
    }


def derive_anonymization_records(repo: Path) -> list[dict]:
    """The transform records the contract and the repository bytes imply.

    Built here rather than taken from the caller.  A reviewer changed
    descriptive fields, dropped `source_path`, added a key and duplicated a
    record, regenerated the staged manifest from the same mutated list, and the
    gate had nothing to disagree with -- both sides came from one object.

    The digests are **computed from the bytes in the repository right now**,
    not copied from the contract.  Copying them was the next hole: a reviewer
    edited the evidence while leaving the `git_revision` field alone, and every
    derived record came back identical to the contract because the contract was
    the only thing anyone read.  `check_anonymization_record` then compares
    these computed values with `contract.CONTRACT`, so the comparison has two
    independent sides -- the current bytes and the immutable pin -- and evidence
    that drifted from the pin is a finding.

    Exactly one record per contract path, in path order, with exactly
    `TRANSFORM_RECORD_KEYS`.
    """

    by_arcname = {arc: source for source, arc in supplement_entries(repo)}
    records: list[dict] = []
    for arcname in sorted(contract.CONTRACT):
        source = by_arcname.get(arcname)
        if source is None:
            raise RuntimeError(
                f"{arcname} is pinned in the anonymization contract but is not "
                "in the supplement inventory")
        original = source.read_bytes()
        packaged, removed = _replace_revision_field(original, arcname)
        records.append({
            "path": arcname,
            "source_path": str(source.relative_to(repo)),
            "field": ANONYMIZED_FIELD,
            "removed_value_class": TRANSFORM_REMOVED_VALUE_CLASS,
            "removed_value_internal_only": removed,
            "replacement": ANONYMIZED_TOKEN,
            "original_sha256": hashlib.sha256(original).hexdigest(),
            "packaged_sha256": hashlib.sha256(packaged).hexdigest(),
            "original_bytes": len(original),
            "packaged_bytes": len(packaged),
            "reason": TRANSFORM_REASON,
        })
    return records


def anonymize(repo: Path, out: Path,
              entries: Sequence[tuple[Path, str]]
              ) -> tuple[list[tuple[Path, str]], list[dict[str, object]]]:
    """Rewrite reviewer-facing evidence copies in the external staging tree.

    Returns the new entry list and the transform records.  Nothing under the
    repository is written.
    """

    stage_dir = out / "supplement_stage"
    reset_build_directory(stage_dir)

    by_arcname = {arc: source for source, arc in entries}
    transforms: list[dict[str, object]] = []
    replacements: dict[str, Path] = {}

    for arcname in ANONYMIZE_REVISION_IN:
        source = by_arcname.get(arcname)
        if source is None:
            raise RuntimeError(f"{arcname} is not in the supplement inventory")
        original = source.read_bytes()
        packaged, original_value = _replace_revision_field(original, arcname)
        pinned = contract.CONTRACT[arcname]
        packaged_sha = hashlib.sha256(packaged).hexdigest()
        if (packaged_sha != pinned["packaged_sha256"]
                or len(packaged) != pinned["packaged_bytes"]
                or hashlib.sha256(original).hexdigest() != pinned["original_sha256"]
                or len(original) != pinned["original_bytes"]):
            raise RuntimeError(
                f"{arcname}: packaging result does not match the pinned contract "
                f"in tools/anonymous_package_contract.py. produced "
                f"{packaged_sha} ({len(packaged)} bytes) from original "
                f"{hashlib.sha256(original).hexdigest()} ({len(original)} bytes); "
                f"pinned {pinned['packaged_sha256']} "
                f"({pinned['packaged_bytes']} bytes) from original "
                f"{pinned['original_sha256']} ({pinned['original_bytes']} bytes). "
                "Regenerate the contract constants deliberately; do not relax "
                "this check."
            )
        target = stage_dir / arcname
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(target, packaged)
        replacements[arcname] = target
        transforms.append({
            "path": arcname,
            "source_path": str(source.relative_to(repo)),
            "field": ANONYMIZED_FIELD,
            "removed_value_class": TRANSFORM_REMOVED_VALUE_CLASS,
            "removed_value_internal_only": original_value,
            "replacement": ANONYMIZED_TOKEN,
            "original_sha256": hashlib.sha256(original).hexdigest(),
            "packaged_sha256": hashlib.sha256(packaged).hexdigest(),
            "original_bytes": len(original),
            "packaged_bytes": len(packaged),
            "reason": TRANSFORM_REASON,
        })

        # The sidecar next to a file must describe that file.  Regenerate it over
        # the packaged bytes rather than shipping a digest of bytes the reviewer
        # does not have; ANONYMIZATION.json says which is which.
        sidecar_arc = f"{arcname}.sha256"
        if sidecar_arc in by_arcname:
            sidecar_target = stage_dir / sidecar_arc
            sidecar_target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(
                sidecar_target, contract.sidecar_text(arcname).encode("ascii"))
            replacements[sidecar_arc] = sidecar_target

    # The reviewer-facing declaration.  It carries both digests so the reviewer
    # can see that the packaged file is a modified copy of a different artifact,
    # and it never calls the replacement token a revision.
    declaration_path = stage_dir / ANONYMIZATION_MANIFEST
    atomic_write_bytes(
        declaration_path,
        canonical_json_bytes(anonymization_declaration(transforms)))

    rewritten = [
        (replacements.get(arc, source), arc) for source, arc in entries
    ]
    rewritten.append((declaration_path, ANONYMIZATION_MANIFEST))
    return rewritten, transforms


def scan_for_identifiers(entries: Iterable[tuple[Path, str]],
                         revisions: Sequence[str]) -> list[str]:
    """Fail on anything in reviewer-visible bytes that identifies the project.

    Catches every project revision at any abbreviation of seven characters or
    more, in either letter case, and any 40-hex value sitting in a field whose
    name says it is a version-control identifier.

    A bare 40-hex string is deliberately NOT a finding on its own.  The SHA-1 of
    "abc" is `a9993e364706816aba3e25717850c26c9cd0d89d`, and a content digest is
    not a leak; rejecting the shape rather than the identity would force real
    evidence to be rewritten to satisfy a scan.  A 64-hex SHA-256 is likewise
    fine: the hex boundaries stop a 40-hex or 7-hex window from matching inside
    a longer run.

    `revisions` comes from project_revisions(), so the current candidate, its
    ancestors and every superseded candidate are covered, not just a list
    someone maintained.
    """

    prefixes = sorted({revision[:7].lower() for revision in revisions})
    abbreviated = re.compile(
        "(?<![0-9a-fA-F])(?:"
        + "|".join(prefix + "[0-9a-fA-F]*" for prefix in prefixes)
        + ")(?![0-9a-fA-F])",
        re.IGNORECASE,
    )
    # A revision-shaped value in a revision-named field, in JSON, YAML or prose.
    revision_field = re.compile(
        r"(?:" + "|".join(re.escape(name) for name in REVISION_FIELD_NAMES)
        + r")\b[\"']?\s*[:=]\s*[\"']?"
        r"(?<![0-9a-fA-F])([0-9a-fA-F]{7,40})(?![0-9a-fA-F])",
        re.IGNORECASE,
    )
    identity = re.compile("|".join(FORBIDDEN), re.IGNORECASE)
    # A repository URL of any shape is a finding, because this project's own
    # slug is one.  The exception is a vendored third-party package, which
    # carries its *upstream* project's URL -- `github.com/latex3/mathtools` in
    # mhsetup.sty -- and says nothing about who wrote this paper.  The exception
    # is scoped to this one rule and to files whose bytes are pinned in
    # VENDORED_PACKAGE_DIGESTS: author names, `/home/` paths, the employer and
    # every project revision still apply to them in full.
    repository_url = re.compile(
        r"github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", re.IGNORECASE)

    findings: list[str] = []
    for source, arcname in entries:
        if source.suffix in {".pdf", ".whl", ".png", ".jpg", ".zip"}:
            continue
        try:
            text = source.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for match in revision_field.finditer(line):
                findings.append(
                    f"{arcname}:{number}: version-control identifier in a "
                    f"revision field: {match.group(1)!r}")
            for match in abbreviated.finditer(line):
                findings.append(
                    f"{arcname}:{number}: known project revision "
                    f"{match.group(0)!r}")
            for match in identity.finditer(line):
                if citation_exempt(arcname, match, line):
                    continue
                findings.append(
                    f"{arcname}:{number}: project or author identifier "
                    f"{match.group(0)!r}")
            if vendored_package_member(source, arcname):
                continue
            for match in repository_url.finditer(line):
                findings.append(
                    f"{arcname}:{number}: repository URL {match.group(0)!r}")
    return findings


def vendored_package_member(source: Path, arcname: str) -> bool:
    """True when these exact bytes are a pinned vendored third-party package."""

    pinned = VENDORED_PACKAGE_DIGESTS.get(Path(arcname).name)
    if pinned is None:
        return False
    try:
        return hashlib.sha256(source.read_bytes()).hexdigest() == pinned
    except OSError:
        return False


def supplement_entries(repo: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []

    def add(source: Path, arcname: str) -> None:
        if not source.is_file():
            raise FileNotFoundError(source)
        entries.append((source, arcname))

    for name in SUPPLEMENT_EXPERIMENT_MODULES:
        add(repo / "experiments" / name, f"experiments/{name}")
    for name in SUPPLEMENT_EXPERIMENT_TESTS:
        add(repo / "experiments/tests" / name, f"experiments/tests/{name}")
    for relative in SUPPLEMENT_EVIDENCE + SUPPLEMENT_OTHER:
        add(repo / relative, relative)

    # generated evidence artifacts with their sidecars and provenance records
    for relative in supplement_artifact_inventory(repo):
        add(repo / relative, relative)

    # the manuscript sources, so the ledger's literal checks run in the supplement
    for path in sorted((repo / "paper").glob("*.tex")):
        if path.name in STAGE_TEX_EXCLUDE:
            continue
        add(path, f"paper/{path.name}")
    add(repo / "paper/references.bib", "paper/references.bib")
    add(repo / ENTRY_POINT, str(ENTRY_POINT))

    # reviewer-facing entry points, written for the supplement
    add(repo / "submissions/tmlr_2026/supplement_README.md", "README.md")
    add(repo / "submissions/tmlr_2026/supplement_verify.sh", "verify.sh")
    return entries


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        help="output directory, outside the repository")
    parser.add_argument("--repo", type=Path, default=repo_root())
    parser.add_argument("--skip-compile", action="store_true")
    parser.add_argument("--compare-manifest", type=Path, default=None,
                        help="compare a freshly built release_manifest.json "
                             "against the one recorded in this directory and "
                             "exit nonzero if the deliverables differ")
    args = parser.parse_args(argv)

    if args.compare_manifest is not None:
        # Exact bytes after the same deterministic serialisation the build
        # uses.  Comparing only `deliverables` meant the committed manifest
        # could disagree with a rebuild about every archive member, every
        # external TeX input, the anonymization metadata and the shipped-tool
        # pins, and this would still print "matches".
        recorded_path = Path(__file__).resolve().parent / "release_manifest.json"
        rebuilt = json.loads(args.compare_manifest.read_text(encoding="utf-8"))
        recorded = json.loads(recorded_path.read_text(encoding="utf-8"))
        for key in MANIFEST_RECORD_CLASSES:
            if key not in rebuilt or key not in recorded:
                print(f"a manifest is missing the {key!r} record class",
                      file=sys.stderr)
                return 4
        if canonical_manifest_bytes(rebuilt) != canonical_manifest_bytes(recorded):
            print("the recorded release manifest no longer matches a rebuild",
                  file=sys.stderr)
            for line in manifest_difference(recorded, rebuilt):
                print("  " + line, file=sys.stderr)
            return 4
        print("release manifest matches the rebuilt manifest, byte for byte "
              f"over all {len(MANIFEST_RECORD_CLASSES)} record classes")
        return 0

    if args.out is None:
        parser.error("--out is required unless --compare-manifest is given")

    repo = args.repo.resolve()
    out = args.out.resolve()
    out = ensure_output_outside_repo(repo, out)
    out.mkdir(parents=True, exist_ok=True)

    # The very first thing, before anything in this process can create, reset or
    # remove a directory under `out`.  `publish_release` has the same guard, but
    # by the time it runs this CLI has already called `reset_build_directory` on
    # `.pending` -- which deletes `.previous` with it.  A reviewer put a
    # retention failure's only surviving backup there, ran the real CLI, and
    # watched it return 0 with the backup gone and the release replaced.  That
    # is data loss, not a rejected publication, so the check belongs here.
    residual = residual_recovery_problem(out / ".pending" / ".previous")
    if residual is not None:
        print("\nREFUSING TO BUILD: AN UNRECOVERED RELEASE BACKUP IS PRESENT",
              file=sys.stderr)
        print("  " + residual, file=sys.stderr)
        print("  Nothing has been read, written or removed under the output "
              "directory.", file=sys.stderr)
        return 13
    print("residual-recovery check: no unrecovered backup in the way")

    # Early diagnostic only.  It globs the repository, so it can catch a
    # mistake before a five-minute build, but it is NOT the authority: the
    # authority is check_compiled_layout_rules below, over the recorder output
    # of the build that actually produced the PDF.
    layout = check_layout_rules(repo)
    if layout:
        print("\nLAYOUT RULES VIOLATED (repository preflight diagnostic) - "
              "the venue forbids shrinking content:", file=sys.stderr)
        for finding in layout:
            print("  " + finding, file=sys.stderr)
        return 6
    print("layout preflight (diagnostic, not the authority): clean")

    src, staged_sources = stage(repo, out)
    print(f"staged {len(list(src.rglob('*')))} paths into {src}")

    static = validate_staged_sources(repo, src)
    if static:
        print("\nSTAGED SOURCES FAILED STATIC VALIDATION:", file=sys.stderr)
        for finding in static:
            print("  " + finding, file=sys.stderr)
        return 7
    print("staged entry point: static validation clean")

    if not args.skip_compile:
        compile_pdf(src)
        unresolved = check_compiled_references(src)
        if unresolved:
            print("\nUNRESOLVED CROSS-REFERENCES IN THE COMPILED DOCUMENT:",
                  file=sys.stderr)
            for finding in unresolved:
                print("  " + finding, file=sys.stderr)
            return 8
        print("compiled document: every reference and citation resolved")

        # The authoritative layout gate: the exact closure the compiler read,
        # nested table and figure inputs included, run after a successful
        # compile and before any deliverable is written.
        compiled_layout = check_compiled_layout_rules(src, staged_sources, repo)
        if compiled_layout:
            print("\nLAYOUT RULES VIOLATED IN THE COMPILED SOURCE CLOSURE:",
                  file=sys.stderr)
            for finding in compiled_layout:
                print("  " + finding, file=sys.stderr)
            return 9
    pdf = src / "main.pdf"

    # Every byte outside the project that the compiler read, named and hashed.
    # Recording this is the other half of the trusted-root rule: the rule keeps
    # untrusted bytes out, and this says exactly what the trusted ones were.
    external_inputs: list[dict] = []
    if not args.skip_compile:
        recorder_inputs(src, repo=repo, external_record=external_inputs)
        untrusted = [item["name"] for item in external_inputs
                     if not item["trusted"]]
        print(f"external compiled inputs: {len(external_inputs)} "
              f"({len(untrusted)} accepted only by pinned digest)")
    # Reported, not remembered.  The manifest derivation re-runs the recorder
    # for itself; nothing here is carried forward for it to trust.

    source_files = closure(src, repo)
    source_entries = [(src / p, str(p)) for p in source_files]
    print(f"dependency closure from main.fls: {len(source_entries)} files")

    supplement = supplement_entries(repo)
    print(f"supplement inventory: {len(supplement)} files")

    # Internal documents must never reach an upload, whatever else changes.
    never_upload = {"FINALIZATION_REPORT.md", "PORTAL.md", "README.md",
                    "package.py", "build.sh"}
    leaked = sorted(
        arc for _, arc in source_entries
        if Path(arc).name in never_upload
    ) + sorted(
        arc for _, arc in supplement
        if Path(arc).name in never_upload and arc != "README.md"
    )
    if leaked:
        print(f"\ninternal files would have shipped: {leaked}", file=sys.stderr)
        return 3

    findings = scrub(source_entries) + scrub(supplement)
    if findings:
        print("\nSCRUB FAILED - these would have shipped:", file=sys.stderr)
        for finding in findings:
            print("  " + finding, file=sys.stderr)
        return 2
    print("scrub: clean")

    # The shipped tools that decide a reviewer's verification result are pinned
    # in the contract module.  Packaging refuses to emit bytes the contract does
    # not already describe, in the same direction as the anonymization pins: the
    # contract cannot drift away from what is actually shipped.
    tool_drift = [f"{name}: built {sha256_file(repo / name)}, contract {pinned}"
                  for name, pinned in sorted(contract.SHIPPED_TOOL_DIGESTS.items())
                  if (repo / name).is_file()
                  and sha256_file(repo / name) != pinned]
    if tool_drift:
        print("\nSHIPPED TOOL DIGESTS DO NOT MATCH THE PINNED CONTRACT:",
              file=sys.stderr)
        for finding in tool_drift:
            print("  " + finding, file=sys.stderr)
        return 11
    print(f"shipped tool digests: "
          f"{len(contract.SHIPPED_TOOL_DIGESTS)} match the pinned contract")

    # Anonymous packaging transform, applied only to the external staging tree.
    supplement, transforms = anonymize(repo, out, supplement)
    for record in transforms:
        print(f"anonymized {record['path']}: {record['field']} -> "
              f"{record['replacement']!r}")

    # The compiled closure, recorded for the reviewer.  Written after
    # anonymize() because that call resets the staging directory.
    if not args.skip_compile:
        closure_manifest = write_source_closure_manifest(
            src, staged_sources, out, {arc for _, arc in supplement}, repo,
            {arc for _, arc in source_entries})
        supplement.append((closure_manifest, SOURCE_CLOSURE_NAME))
        print(f"source-closure manifest: {len(recorder_inputs(src, repo=repo))} compiled "
              f"inputs recorded in {SOURCE_CLOSURE_NAME}")
    print(f"supplement inventory after transform: {len(supplement)} files")

    # Nothing that identifies the project or its authors may reach either
    # archive.  This runs after the transform, so it is the gate the transform
    # has to satisfy rather than a description of it.
    revisions = project_revisions(repo)
    print(f"revision scan covers {len(revisions)} project revisions")
    leaks = (scan_for_identifiers(source_entries, revisions)
             + scan_for_identifiers(supplement, revisions))
    if leaks:
        print("\nREVISION/IDENTITY SCAN FAILED - these would have shipped:",
              file=sys.stderr)
        for leak in leaks[:40]:
            print("  " + leak, file=sys.stderr)
        if len(leaks) > 40:
            print(f"  ... and {len(leaks) - 40} more", file=sys.stderr)
        return 5
    print("revision/identity scan: clean")

    # Everything below is built in a staging area and published in one step.
    #
    # It used to be built straight into `out`, with the size gate after the
    # writes: an oversized supplement left `main.pdf`, `source.zip` and
    # `supplement.zip` replaced and `release_manifest.json` describing the
    # previous build.  That is the worst possible failure -- a mixed generation
    # that looks like a release.  Now every gate runs against the staged bytes,
    # and a failure returns with every prior deliverable byte-identical.
    pending = out / ".pending"
    reset_build_directory(pending)

    atomic_write_bytes(pending / "main.pdf", pdf.read_bytes())
    write_zip(pending / "source.zip", source_entries)
    write_zip(pending / "supplement.zip", supplement)

    oversize = (check_archive_size(pending / "supplement.zip")
                + check_archive_size(pending / "source.zip"))
    if oversize:
        print("\nARCHIVE TOO LARGE FOR THE VENUE:", file=sys.stderr)
        for finding in oversize:
            print("  " + finding, file=sys.stderr)
        shutil.rmtree(pending, ignore_errors=True)
        return 10

    manifest = derive_release_manifest(repo, src, pending)
    deliverables = manifest["deliverables"]
    atomic_write_bytes(pending / "release_manifest.json",
                       canonical_manifest_bytes(manifest))

    consistency = check_pending_release(repo, src, pending, transforms)
    if consistency:
        print("\nSTAGED RELEASE FAILED ITS CONSISTENCY CHECKS:", file=sys.stderr)
        for finding in consistency:
            print("  " + finding, file=sys.stderr)
        shutil.rmtree(pending, ignore_errors=True)
        return 12

    publish_release(pending, out)

    print()
    for name, record in deliverables.items():
        print(f"{record['sha256']}  {record['bytes']:>9}  {name}")
    print(f"{'':<64}  {'':>9}  release_manifest.json (not self-hashed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
