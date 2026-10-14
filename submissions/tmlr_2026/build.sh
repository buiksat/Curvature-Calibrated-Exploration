#!/usr/bin/env bash
# Build the anonymous manuscript and a self-contained project-source archive.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd -- "$here/../.." && pwd)"
out="${TMLR_OUT:-${TMPDIR:-/tmp}/cce-tmlr}"
out="$(python3 - "$repo" "$out" <<'PY'
from pathlib import Path
import sys
repo, out = map(lambda p: Path(p).resolve(), sys.argv[1:])
if out.is_relative_to(repo):
    raise SystemExit('TMLR_OUT must be outside the repository.')
print(out)
PY
)"
mkdir -p "$out"
cd "$here"
sha256sum -c STYLE_SHA256SUMS
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir="$out" main.tex
python3 - "$here" "$out" <<'PY'
from pathlib import Path
import re
import subprocess
import sys
import zipfile

source, output = map(Path, sys.argv[1:])
log = (output / 'main.log').read_text()
bad = re.findall(
    r'^!.*|^Missing character:.*|.*(?:Reference|Citation).*undefined.*|'
    r'.*(?:There were undefined|Rerun to get|Label\(s\) may have changed).*',
    log, re.MULTILINE,
)
if bad:
    raise SystemExit('\n'.join(bad))
subprocess.run(['pdfinfo', str(output / 'main.pdf')], check=True)
extensions = {'.tex', '.bib', '.csv', '.sty', '.bst'}
# Package only inputs used by this manuscript. Historical sources retained in
# Git are not part of the current submission's review surface. BibTeX inputs
# are added explicitly because they need not appear in pdfTeX's recorder.
inputs = {source / name for name in
          ('references.bib', 'tmlr.bst', 'LICENSE', 'STYLE_SHA256SUMS', 'BUILD.md')}
for record in (output / 'main.fls').read_text().splitlines():
    if not record.startswith('INPUT '):
        continue
    path = Path(record[6:])
    path = (source / path).resolve() if not path.is_absolute() else path.resolve()
    if path.is_relative_to(source) and path.suffix in extensions:
        inputs.add(path)
# Keep every official file listed by the style-integrity check in the archive.
for record in (source / 'STYLE_SHA256SUMS').read_text().splitlines():
    if record.strip():
        inputs.add(source / record.split(maxsplit=1)[1].lstrip('*'))
with zipfile.ZipFile(output / 'source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(inputs):
        if not path.is_file() or not path.resolve().is_relative_to(source):
            raise SystemExit(f'Missing or out-of-tree manuscript input: {path}')
        archive.write(path, path.relative_to(source))
print(f'PDF: {output / "main.pdf"}')
print(f'LaTeX source: {output / "source.zip"}')
print('Manuscript build only; no experiment supplement is generated or submitted.')
PY
