#!/usr/bin/env bash
# One command to build and package the anonymous TMLR submission.
#
#   bash submissions/tmlr_2026/build.sh                 # default output directory
#   TMLR_OUT=/some/where bash submissions/tmlr_2026/build.sh
#
# The output directory must be outside the repository; package.py refuses
# otherwise, so no protected path can be written by accident.  Produces
#
#   <out>/main.pdf               the anonymous submission PDF
#   <out>/source.zip             the staged project-local compile closure, flat
#   <out>/supplement.zip         anonymous reproducibility material
#   <out>/release_manifest.json  deliverable and input hashes
#   <out>/src/                   the staged flat build tree, kept for inspection
set -euo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd -- "$here/../.." && pwd)"
out="${TMLR_OUT:-${TMPDIR:-/tmp}/cce-tmlr-2026-release}"

# The containment rule is enforced once, in package.py, with resolved paths and
# Path.is_relative_to.  A string-prefix test used to run here as well and was
# simply wrong: a sibling directory such as
# <repo>-release shares the repository's path prefix without being inside it,
# so a perfectly valid output directory was rejected.

command -v latexmk >/dev/null || { echo "latexmk is required" >&2; exit 1; }
command -v pdflatex >/dev/null || { echo "pdflatex is required" >&2; exit 1; }
command -v bibtex >/dev/null || { echo "bibtex is required" >&2; exit 1; }

python="${PYTHON:-python3}"
"$python" - <<'PY' || { echo "numpy and scipy are required for the evidence checks" >&2; exit 1; }
import numpy, scipy  # noqa: F401
PY

echo "repository : $repo"
echo "output     : $out"
echo

"$python" "$here/package.py" --repo "$repo" --out "$out"

echo
echo "== PDF facts =="
pages=$("$python" - "$out/main.pdf" <<'PY'
import re, sys, zlib
data = open(sys.argv[1], "rb").read()
count = len(re.findall(rb"/Type\s*/Page[^s]", data))
if count == 0:  # object streams: inflate them first
    for match in re.finditer(rb"stream\r?\n", data):
        start = match.end()
        end = data.find(b"endstream", start)
        try:
            count += len(re.findall(rb"/Type\s*/Page[^s]",
                                    zlib.decompress(data[start:end])))
        except zlib.error:
            continue
print(count)
PY
)
echo "pages: $pages"
if command -v pdfinfo >/dev/null; then pdfinfo "$out/main.pdf" | sed -n '1,8p'; fi

echo
echo "Nothing has been uploaded or submitted.  See FINALIZATION_REPORT.md for the"
echo "release holds that still need a human decision."
