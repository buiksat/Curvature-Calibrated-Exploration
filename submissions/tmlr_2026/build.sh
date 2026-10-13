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
with zipfile.ZipFile(output / 'source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(source.rglob('*')):
        if path.is_file() and (path.suffix in extensions or path.name in
                               {'LICENSE', 'STYLE_SHA256SUMS', 'BUILD.md'}):
            archive.write(path, path.relative_to(source))
print(f'PDF: {output / "main.pdf"}')
print(f'LaTeX source: {output / "source.zip"}')
print('Manuscript build only; no experiment supplement is generated or submitted.')
PY
