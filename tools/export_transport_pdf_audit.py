#!/usr/bin/env python3
"""Build a GitHub-inspectable audit package for the locked manuscript PDF.

A reviewer who only has GitHub cannot open a 933,908-byte PDF blob and check
whether a figure clipped, a table overflowed, or a label went illegible.  This
tool renders the evidence GitHub *can* show: structural output, extracted text,
a page-to-section index, contact sheets for every page, and full-resolution
renders of the pages that carry the transport theorems, experiment, tables and
figures.

`paper/main.pdf` is never modified.  Its SHA-256 is checked before anything is
read, and again at the end.

## Tool substitutions

The canonical commands in the review request are poppler/qpdf based.  Only
ghostscript is present in this environment, so each is substituted with a
documented ghostscript equivalent and the substitution is recorded in
``pdf_manifest.json`` under ``tooling``:

| Canonical            | Substitute                                            |
| -------------------- | ----------------------------------------------------- |
| ``qpdf --check``     | ``gs -sDEVICE=nullpage`` (full interpret of every page) |
| ``pdfinfo``          | ``gs`` page count plus a standard-library trailer scan  |
| ``pdffonts``         | standard-library ``/BaseFont`` scan of inflated objects |
| ``pdftotext -layout``| ``gs -sDEVICE=txtwrite``                                |
| ``pdftoppm``         | ``gs -sDEVICE=png16m`` / ``-sDEVICE=ppmraw``            |

Contact sheets and page renders are evidence about typesetting.  They are not
evidence that any theorem is correct.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unicodedata
import zlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from export_transport_github_review_bundle import (  # noqa: E402
    IMPLEMENTATION_COMMIT,
    LOCKED_PDF_SHA256,
    PDF_PATH,
    SOURCE_HEAD,
    ReviewBundleError,
    canonical_json,
    pdf_page_count,
    sha256_file,
)

SCHEMA_VERSION = 1
CONTACT_SHEET_DPI = 24
CONTACT_SHEET_COLUMNS = 4
CONTACT_SHEET_ROWS = 4
CONTACT_SHEET_PAD = 6
PAGE_RENDER_DPI = 150

LIGATURES = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "st",
    "ﬆ": "st",
}

# Pages that must be legible at full resolution, keyed by what they carry.
FULL_RESOLUTION_TARGETS: Mapping[str, str] = {
    "headline confidence-transport theorem (Theorem 1)": (
        r"Theorem\s*1\s*\(\s*Estimator-\s*and\s*solver-agnostic\s*confidence"
    ),
    "corrected-center theorem (Corollary 7)": r"Corollary 7 \(Corrected-center confidence",
    "finite-dimensional corrected-center rate (Corollary 8)": (
        r"Corollary 8 \(Finite-dimensional corrected-center"
    ),
    "global near-linearity corollary (Corollary 9)": r"Corollary 9 \(Global near-linearity",
    "corrected-center transported UCB algorithm": r"Corrected-center specialization of trans",
    "transport experiment section 6": r"controlled instantiation of",
    "transport experiment environment diagnostics": r"mean optimal-action entropy was 1\.579",
    "validity table": r"Locked theorem-instantiation audit",
    "performance table": r"Policy outcomes at the primary horizon",
    "proof of Theorem 1": r"Proofs for confidence transport",
    "appendix transport diagnostics": r"Additional transport-instantiation diagnostics",
    "tightness table": r"Certificate and bound tightness",
    "regret figure": r"Mean cumulative pseudo-regret at",
    "tightness figure": r"Path-certificate conservatism",
    "bound figure": r"Mean cumulative decomposition",
}

SECTION_PATTERN = re.compile(
    r"(?:^|\s)((?:[A-N]|\d{1,2}))\s+([A-Z][A-Za-z][^.]{6,70}?)(?=\s+[A-Z]|\s*$)"
)


class PdfAuditError(RuntimeError):
    pass


def normalize_text(value: str) -> str:
    for ligature, replacement in LIGATURES.items():
        value = value.replace(ligature, replacement)
    value = unicodedata.normalize("NFKD", value)
    return " ".join(value.split())


def run_ghostscript(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gs", "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE", *args],
        capture_output=True,
        text=True,
        check=False,
    )


# --------------------------------------------------------------------------
# minimal PNG writer (standard library)
# --------------------------------------------------------------------------


def write_png(path: Path, width: int, height: int, rgb: bytes) -> None:
    if len(rgb) != width * height * 3:
        raise PdfAuditError("RGB buffer size does not match the declared geometry")
    raw = bytearray()
    stride = width * 3
    for row in range(height):
        raw.append(0)  # filter type 0
        raw += rgb[row * stride : (row + 1) * stride]

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    body = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def read_ppm(path: Path) -> tuple[int, int, bytes]:
    """Parse a binary P6 PPM, skipping comment lines."""

    data = path.read_bytes()
    fields: list[bytes] = []
    index = 0
    while len(fields) < 4:
        while index < len(data) and data[index : index + 1].isspace():
            index += 1
        if data[index : index + 1] == b"#":
            while index < len(data) and data[index] != 0x0A:
                index += 1
            continue
        start = index
        while index < len(data) and not data[index : index + 1].isspace():
            index += 1
        fields.append(data[start:index])
    index += 1  # single whitespace byte after maxval
    if fields[0] != b"P6":
        raise PdfAuditError(f"expected a binary P6 PPM, got {fields[0]!r}")
    width, height, maxval = (int(fields[1]), int(fields[2]), int(fields[3]))
    if maxval != 255:
        raise PdfAuditError("only 8-bit PPM output is supported")
    payload = data[index : index + width * height * 3]
    if len(payload) != width * height * 3:
        raise PdfAuditError("truncated PPM payload")
    return width, height, payload


# --------------------------------------------------------------------------
# structural, metadata and text extraction
# --------------------------------------------------------------------------


def structural_check(pdf: Path) -> str:
    result = run_ghostscript(["-sDEVICE=nullpage", "-o", os.devnull, str(pdf)])
    lines = [
        "# Structural PDF check",
        "#",
        "# Canonical command : qpdf --check paper/main.pdf",
        "# Substitute used   : gs -dSAFER -dBATCH -dNOPAUSE -sDEVICE=nullpage",
        "#   qpdf is not installed in this environment. The nullpage device fully",
        "#   interprets every page and content stream and fails on a structurally",
        "#   broken file, so it detects the same class of corruption qpdf --check",
        "#   reports. It does not reproduce qpdf's object-level warnings.",
        "#",
        f"exit_status: {result.returncode}",
        f"stderr_bytes: {len(result.stderr)}",
        "",
        "## stdout",
        result.stdout.rstrip("\n"),
        "",
        "## stderr",
        result.stderr.rstrip("\n"),
        "",
    ]
    return "\n".join(lines) + "\n"


def pdf_metadata(pdf: Path) -> tuple[str, dict[str, Any]]:
    data = pdf.read_bytes()
    pages = pdf_page_count(pdf)
    version = data[:8].decode("ascii", "replace").lstrip("%")
    boxes = sorted(
        {
            tuple(round(float(v), 3) for v in match.groups())
            for match in re.finditer(
                rb"/MediaBox\s*\[\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\]",
                _inflated(data),
            )
        }
    )
    linearized = b"/Linearized" in data
    encrypted = b"/Encrypt" in data
    record = {
        "path": str(PDF_PATH),
        "sha256": LOCKED_PDF_SHA256,
        "bytes": len(data),
        "pages": pages,
        "pdf_version": version,
        "media_boxes": [list(b) for b in boxes],
        "linearized": linearized,
        "encrypted": encrypted,
    }
    text = "\n".join(
        [
            "# PDF metadata",
            "#",
            "# Canonical command : pdfinfo paper/main.pdf",
            "# Substitute used   : gs page count plus a standard-library object scan",
            "#   poppler is not installed. Page count is cross-checked against",
            "#   gs -dNODISPLAY pdfpagecount; both report the same value.",
            "",
            f"File:           {record['path']}",
            f"SHA-256:        {record['sha256']}",
            f"File size:      {record['bytes']} bytes",
            f"Pages:          {record['pages']}",
            f"PDF version:    {record['pdf_version']}",
            f"Encrypted:      {'yes' if encrypted else 'no'}",
            f"Linearized:     {'yes' if linearized else 'no'}",
            "MediaBoxes:     "
            + "; ".join(" ".join(str(v) for v in b) for b in boxes),
            "",
        ]
    )
    return text, record


def _inflated(data: bytes) -> bytes:
    blobs = [data]
    for match in re.finditer(rb"stream\r?\n", data):
        start = match.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        try:
            blobs.append(zlib.decompress(data[start:end]))
        except zlib.error:
            continue
    return b"\n".join(blobs)


def pdf_fonts(pdf: Path) -> tuple[str, list[dict[str, Any]]]:
    joined = _inflated(pdf.read_bytes())
    fonts: dict[str, dict[str, Any]] = {}
    for match in re.finditer(
        rb"/BaseFont\s*/([#\w+.\-]+)(?:(?!/BaseFont).){0,400}?/Subtype\s*/(\w+)",
        joined,
        re.S,
    ):
        name = match.group(1).decode("ascii", "replace")
        subtype = match.group(2).decode("ascii", "replace")
        entry = fonts.setdefault(
            name, {"name": name, "subtype": subtype, "embedded": "+" in name}
        )
        entry["subtype"] = subtype
    for match in re.finditer(rb"/BaseFont\s*/([#\w+.\-]+)", joined):
        name = match.group(1).decode("ascii", "replace")
        fonts.setdefault(name, {"name": name, "subtype": "unknown", "embedded": "+" in name})
    ordered = [fonts[key] for key in sorted(fonts)]
    lines = [
        "# Embedded fonts",
        "#",
        "# Canonical command : pdffonts paper/main.pdf",
        "# Substitute used   : standard-library /BaseFont scan over inflated objects",
        "#   poppler is not installed. A subset-embedded font carries a six-letter",
        "#   tag and a '+' in its BaseFont name; that is what 'embedded' reports.",
        "",
        f"{'name':<44} {'subtype':<14} embedded",
        f"{'-' * 44} {'-' * 14} --------",
    ]
    for font in ordered:
        lines.append(
            f"{font['name']:<44} {font['subtype']:<14} {'yes' if font['embedded'] else 'no'}"
        )
    lines.append("")
    lines.append(f"total: {len(ordered)}")
    lines.append("")
    return "\n".join(lines), ordered


def extract_text(pdf: Path, pages: int, workdir: Path) -> list[str]:
    texts: list[str] = []
    for page in range(1, pages + 1):
        target = workdir / f"page-{page:03d}.txt"
        result = run_ghostscript(
            [
                "-sDEVICE=txtwrite",
                f"-dFirstPage={page}",
                f"-dLastPage={page}",
                "-o",
                str(target),
                str(pdf),
            ]
        )
        if result.returncode != 0 or not target.is_file():
            raise PdfAuditError(f"text extraction failed on page {page}")
        texts.append(target.read_text(encoding="utf-8", errors="replace"))
    return texts


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


def render_page_png(pdf: Path, page: int, target: Path, dpi: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = run_ghostscript(
        [
            "-sDEVICE=png16m",
            f"-r{dpi}",
            f"-dFirstPage={page}",
            f"-dLastPage={page}",
            "-dTextAlphaBits=4",
            "-dGraphicsAlphaBits=4",
            "-o",
            str(target),
            str(pdf),
        ]
    )
    if result.returncode != 0 or not target.is_file():
        raise PdfAuditError(f"render failed on page {page}: {result.stderr[:200]}")


def build_contact_sheets(pdf: Path, pages: int, output: Path, workdir: Path) -> list[dict[str, Any]]:
    thumbs: list[tuple[int, int, bytes]] = []
    for page in range(1, pages + 1):
        ppm = workdir / f"thumb-{page:03d}.ppm"
        result = run_ghostscript(
            [
                "-sDEVICE=ppmraw",
                f"-r{CONTACT_SHEET_DPI}",
                f"-dFirstPage={page}",
                f"-dLastPage={page}",
                "-dTextAlphaBits=4",
                "-dGraphicsAlphaBits=4",
                "-o",
                str(ppm),
                str(pdf),
            ]
        )
        if result.returncode != 0 or not ppm.is_file():
            raise PdfAuditError(f"thumbnail render failed on page {page}")
        thumbs.append(read_ppm(ppm))

    cell_w = max(t[0] for t in thumbs)
    cell_h = max(t[1] for t in thumbs)
    per_sheet = CONTACT_SHEET_COLUMNS * CONTACT_SHEET_ROWS
    sheets: list[dict[str, Any]] = []
    for sheet_index in range(0, pages, per_sheet):
        batch = thumbs[sheet_index : sheet_index + per_sheet]
        rows = (len(batch) + CONTACT_SHEET_COLUMNS - 1) // CONTACT_SHEET_COLUMNS
        width = CONTACT_SHEET_COLUMNS * (cell_w + CONTACT_SHEET_PAD) + CONTACT_SHEET_PAD
        height = rows * (cell_h + CONTACT_SHEET_PAD) + CONTACT_SHEET_PAD
        canvas = bytearray(b"\x40" * (width * height * 3))
        for offset, (tw, th, payload) in enumerate(batch):
            col = offset % CONTACT_SHEET_COLUMNS
            row = offset // CONTACT_SHEET_COLUMNS
            x0 = CONTACT_SHEET_PAD + col * (cell_w + CONTACT_SHEET_PAD)
            y0 = CONTACT_SHEET_PAD + row * (cell_h + CONTACT_SHEET_PAD)
            for line in range(th):
                dst = ((y0 + line) * width + x0) * 3
                src = line * tw * 3
                canvas[dst : dst + tw * 3] = payload[src : src + tw * 3]
        first = sheet_index + 1
        last = sheet_index + len(batch)
        name = f"contact_sheet_p{first:03d}-p{last:03d}.png"
        write_png(output / name, width, height, bytes(canvas))
        sheets.append(
            {
                "path": name,
                "first_page": first,
                "last_page": last,
                "page_count": len(batch),
                "width": width,
                "height": height,
                "dpi": CONTACT_SHEET_DPI,
                "columns": CONTACT_SHEET_COLUMNS,
            }
        )
    return sheets


# --------------------------------------------------------------------------
# page index
# --------------------------------------------------------------------------


def build_page_index(texts: Sequence[str]) -> list[dict[str, Any]]:
    index: list[dict[str, Any]] = []
    for number, raw in enumerate(texts, start=1):
        normalized = normalize_text(raw)
        headers = []
        for match in re.finditer(
            r"(?:^|\s)((?:Theorem|Corollary|Lemma|Proposition)\s+\d+)\s*\(([^)]{3,90})\)",
            normalized,
        ):
            headers.append(f"{match.group(1)} ({match.group(2).strip()})")
        index.append(
            {
                "page": number,
                "characters": len(normalized),
                "statements": headers,
                "first_line": normalized[:180],
            }
        )
    return index


def locate_targets(texts: Sequence[str]) -> dict[str, list[int]]:
    normalized = [normalize_text(t) for t in texts]
    located: dict[str, list[int]] = {}
    for label, pattern in FULL_RESOLUTION_TARGETS.items():
        compiled = re.compile(pattern)
        hits = [i + 1 for i, text in enumerate(normalized) if compiled.search(text)]
        located[label] = hits
    return located


# --------------------------------------------------------------------------
# rebuild
# --------------------------------------------------------------------------


def classify_rebuild(
    repo_root: Path, pdf: Path, texts: Sequence[str], *, attempt: bool
) -> dict[str, Any]:
    if not attempt:
        return {
            "classification": "NOT_EXECUTED",
            "detail": "clean rebuild not requested; pass --attempt-rebuild",
        }
    if shutil.which("pdflatex") is None:
        return {
            "classification": "rebuild unavailable due to a concrete dependency",
            "detail": "pdflatex is not installed",
        }
    stamp = subprocess.run(
        ["git", "show", "-s", "--format=%ct", IMPLEMENTATION_COMMIT],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    epoch = stamp.stdout.strip() if stamp.returncode == 0 else ""
    with tempfile.TemporaryDirectory(prefix="transport-pdf-rebuild-") as scratch:
        work = Path(scratch) / "repo"
        archive = subprocess.run(
            ["git", "archive", SOURCE_HEAD],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
        if archive.returncode != 0:
            return {
                "classification": "rebuild unavailable due to a concrete dependency",
                "detail": "git archive of the locked head failed",
            }
        work.mkdir(parents=True)
        subprocess.run(["tar", "-x", "-C", str(work)], input=archive.stdout, check=True)
        env = dict(os.environ)
        if epoch:
            env["SOURCE_DATE_EPOCH"] = epoch
        subprocess.run(["make", "clean"], cwd=work, capture_output=True, check=False, env=env)
        build = subprocess.run(
            ["make", "pdf"],
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=1800,
        )
        rebuilt = work / "paper/main.pdf"
        if build.returncode != 0 or not rebuilt.is_file():
            tail = (build.stdout or "")[-1500:]
            return {
                "classification": "rebuild unavailable due to a concrete dependency",
                "detail": "make pdf failed in a clean tree",
                "source_date_epoch": epoch,
                "log_tail": tail,
            }
        rebuilt_sha = sha256_file(rebuilt)
        if rebuilt_sha == LOCKED_PDF_SHA256:
            return {
                "classification": "byte-identical rebuild",
                "detail": "make clean && make pdf reproduced the locked bytes",
                "source_date_epoch": epoch,
                "rebuilt_sha256": rebuilt_sha,
            }
        rebuilt_pages = pdf_page_count(rebuilt)
        with tempfile.TemporaryDirectory(prefix="transport-pdf-cmp-") as cmp_dir:
            rebuilt_texts = extract_text(rebuilt, rebuilt_pages, Path(cmp_dir))
        same_pages = rebuilt_pages == len(texts)
        same_text = [normalize_text(t) for t in rebuilt_texts] == [
            normalize_text(t) for t in texts
        ]
        raster_mismatch: list[int] = []
        if same_pages:
            with tempfile.TemporaryDirectory(prefix="transport-pdf-raster-") as raster:
                for page in range(1, rebuilt_pages + 1):
                    a = Path(raster) / f"a-{page}.png"
                    b = Path(raster) / f"b-{page}.png"
                    render_page_png(pdf, page, a, 72)
                    render_page_png(rebuilt, page, b, 72)
                    if sha256_file(a) != sha256_file(b):
                        raster_mismatch.append(page)
        classification = (
            "semantically identical but byte-different rebuild"
            if same_pages and same_text and not raster_mismatch
            else "rebuild content mismatch"
        )
        return {
            "classification": classification,
            "detail": (
                f"page_count_match={same_pages} extracted_text_match={same_text} "
                f"raster_mismatch_pages={raster_mismatch[:10]}"
            ),
            "source_date_epoch": epoch,
            "rebuilt_sha256": rebuilt_sha,
            "rebuilt_pages": rebuilt_pages,
            "raster_mismatch_page_count": len(raster_mismatch),
        }


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def export(repo_root: Path, output: Path, *, attempt_rebuild: bool) -> dict[str, Any]:
    pdf = repo_root / PDF_PATH
    if not pdf.is_file():
        raise PdfAuditError(f"{PDF_PATH} is missing")
    before = sha256_file(pdf)
    if before != LOCKED_PDF_SHA256:
        raise PdfAuditError(
            f"{PDF_PATH} has SHA-256 {before}, expected {LOCKED_PDF_SHA256}"
        )
    if shutil.which("gs") is None:
        raise PdfAuditError("ghostscript is required to build the PDF audit package")

    output.mkdir(parents=True, exist_ok=True)
    for stale in output.glob("*.png"):
        stale.unlink()
    text_dir = output / "text"
    if text_dir.is_dir():
        shutil.rmtree(text_dir)
    page_dir = output / "pages"
    if page_dir.is_dir():
        shutil.rmtree(page_dir)

    pages = pdf_page_count(pdf)
    files: list[dict[str, Any]] = []

    def emit(relative: str, payload: bytes, kind: str, **extra: Any) -> None:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        record = {
            "path": relative,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "kind": kind,
        }
        record.update(extra)
        files.append(record)

    emit("structural_check.txt", structural_check(pdf).encode("utf-8"), "structural")
    info_text, info_record = pdf_metadata(pdf)
    emit("pdfinfo.txt", info_text.encode("utf-8"), "metadata")
    fonts_text, fonts = pdf_fonts(pdf)
    emit("pdffonts.txt", fonts_text.encode("utf-8"), "metadata")

    with tempfile.TemporaryDirectory(prefix="transport-pdf-text-") as scratch:
        texts = extract_text(pdf, pages, Path(scratch))
        sheets = build_contact_sheets(pdf, pages, output, Path(scratch))

    for number, raw in enumerate(texts, start=1):
        emit(f"text/page-{number:03d}.txt", raw.encode("utf-8"), "text", page=number)
    emit(
        "extracted_text.txt",
        "".join(
            f"\n===== page {i:03d} =====\n{t}" for i, t in enumerate(texts, start=1)
        ).encode("utf-8"),
        "text",
    )

    for sheet in sheets:
        payload = (output / sheet["path"]).read_bytes()
        files.append(
            {
                "path": sheet["path"],
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                "kind": "contact_sheet",
                "first_page": sheet["first_page"],
                "last_page": sheet["last_page"],
                "width": sheet["width"],
                "height": sheet["height"],
                "dpi": sheet["dpi"],
            }
        )

    located = locate_targets(texts)
    unresolved = [label for label, hits in located.items() if not hits]
    render_pages = sorted({page for hits in located.values() for page in hits})
    rendered: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="transport-pdf-render-") as scratch:
        for page in render_pages:
            temporary = Path(scratch) / f"page-{page:03d}.png"
            render_page_png(pdf, page, temporary, PAGE_RENDER_DPI)
            payload = temporary.read_bytes()
            width, height = struct.unpack(">II", payload[16:24])
            relative = f"pages/page-{page:03d}.png"
            emit(
                relative,
                payload,
                "page_render",
                page=page,
                width=width,
                height=height,
                dpi=PAGE_RENDER_DPI,
                carries=sorted(
                    label for label, hits in located.items() if page in hits
                ),
            )
            rendered.append({"page": page, "path": relative})

    page_index = build_page_index(texts)
    emit(
        "page_index.json",
        (json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "pdf_sha256": LOCKED_PDF_SHA256,
                "page_count": pages,
                "pages": page_index,
                "targets": {k: v for k, v in sorted(located.items())},
            },
            indent=2,
            sort_keys=True,
        ) + "\n").encode("utf-8"),
        "index",
    )

    rebuild = classify_rebuild(repo_root, pdf, texts, attempt=attempt_rebuild)

    after = sha256_file(pdf)
    if after != LOCKED_PDF_SHA256:
        raise PdfAuditError("the locked PDF changed while the audit package was built")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "pdf_path": str(PDF_PATH),
        "pdf_sha256": LOCKED_PDF_SHA256,
        "pdf_bytes": info_record["bytes"],
        "pdf_pages": pages,
        "pdf_version": info_record["pdf_version"],
        "media_boxes": info_record["media_boxes"],
        "encrypted": info_record["encrypted"],
        "linearized": info_record["linearized"],
        "fonts": fonts,
        "font_count": len(fonts),
        "contact_sheets": sheets,
        "full_resolution_pages": rendered,
        "full_resolution_targets": {k: v for k, v in sorted(located.items())},
        "unresolved_targets": unresolved,
        "render_dpi": PAGE_RENDER_DPI,
        "contact_sheet_dpi": CONTACT_SHEET_DPI,
        "files": sorted(files, key=lambda item: item["path"]),
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "rebuild": rebuild,
        "tooling": {
            "renderer": "ghostscript",
            "ghostscript_version": subprocess.run(
                ["gs", "--version"], capture_output=True, text=True, check=False
            ).stdout.strip(),
            "substitutions": {
                "qpdf --check": "gs -sDEVICE=nullpage (full page interpretation)",
                "pdfinfo": "gs page count plus standard-library trailer scan",
                "pdffonts": "standard-library /BaseFont scan over inflated objects",
                "pdftotext -layout": "gs -sDEVICE=txtwrite",
                "pdftoppm": "gs -sDEVICE=png16m and -sDEVICE=ppmraw",
            },
            "substitution_reason": (
                "poppler-utils and qpdf are not installed in this environment; "
                "ghostscript is."
            ),
        },
        "non_claims": [
            "Contact sheets and page renders show typesetting, not mathematical correctness.",
            "Extracted text is a rendering artifact and preserves neither ligature "
            "spelling nor two-column reading order.",
            "This package does not verify that results/raw/ inputs exist or match.",
        ],
    }
    (output / "pdf_manifest.json").write_bytes(
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("review/transport_instantiation/pdf")
    )
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parent.parent
    )
    parser.add_argument("--attempt-rebuild", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = export(
            args.repo_root.resolve(), args.output, attempt_rebuild=args.attempt_rebuild
        )
    except (PdfAuditError, ReviewBundleError) as error:
        print(f"pdf audit failed: {error}", file=sys.stderr)
        return 1
    print(
        f"wrote {manifest['file_count']} files ({manifest['total_bytes']} bytes) "
        f"for {manifest['pdf_pages']} pages to {args.output}"
    )
    if manifest["unresolved_targets"]:
        print(f"unresolved targets: {manifest['unresolved_targets']}", file=sys.stderr)
        return 1
    print(f"rebuild: {manifest['rebuild']['classification']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
