#!/usr/bin/env bash
# Run every check the supplement advertises, from the supplement root.
#
# Each step prints its own exit status and the script keeps going, so a reviewer
# sees the whole picture rather than stopping at the first problem.  The overall
# exit status is nonzero if any step failed.
set -uo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"
export PYTHONPATH="$here${PYTHONPATH:+:$PYTHONPATH}"

python="${PYTHON:-python3}"
overall=0

# This is a supplement, so every checker below must use package semantics.  A
# supplement that has lost its ANONYMIZATION.json is either incomplete or has
# been reverted to the original, author-linked evidence; treating it as if it
# were the repository would let both verify clean.  Exported so that a checker
# invoked without its own flag still inherits the requirement.
export CCE_REQUIRE_ANONYMOUS_PACKAGE=1

run() {
  local label="$1"; shift
  echo
  echo "=============================================================="
  echo "== $label"
  echo "=============================================================="
  "$@"
  local status=$?
  echo "-- $label exit status: $status"
  [ "$status" -ne 0 ] && overall=1
  return 0
}

# Every scientific evidence file the supplement ships must be covered by a
# check, not only the ones the artifact regenerator rebuilds.  This walks what
# is actually in the archive, so a file that arrives without a sidecar is a
# failure rather than something nobody looked at.
#
# `results/derived/` is in the sweep too.  It was not, and that is how a
# provenance record could have its `artifact_sha256` replaced with zeros while
# every stage stayed green.  Files the pinned contract verifies from constants
# in shipped code do not need a sidecar; everything else does.
check_evidence_sidecars() {
  local status=0 checked=0 pinned_count=0 unsidecarred=0 file
  local pinned
  pinned="$("$python" tools/anonymous_package_contract.py --list-pinned)" || {
    echo "could not list the contract-pinned paths" >&2
    return 1
  }
  while IFS= read -r file; do
    case "$file" in *.sha256) continue ;; esac
    if printf '%s\n' "$pinned" | grep -qxF "$file"; then
      pinned_count=$((pinned_count + 1))
      continue
    fi
    if [ ! -f "$file.sha256" ]; then
      echo "shipped evidence file has no SHA-256 sidecar: $file" >&2
      unsidecarred=$((unsidecarred + 1)); status=1; continue
    fi
    if ! ( cd "$(dirname "$file")" \
             && sha256sum -c "$(basename "$file").sha256" >/dev/null ); then
      echo "sidecar mismatch: $file" >&2
      status=1
    fi
    checked=$((checked + 1))
  done < <(find paper/tables paper/figures results/derived -type f 2>/dev/null | sort)
  if [ "$checked" -eq 0 ]; then
    echo "no shipped evidence files were found to check" >&2
    status=1
  fi
  echo "verified $checked shipped evidence files against their sidecars"
  echo "$pinned_count further shipped evidence files are verified against the"
  echo "constants pinned in tools/anonymous_package_contract.py instead"
  [ "$unsidecarred" -eq 0 ] \
    || echo "$unsidecarred shipped evidence file(s) carry no sidecar" >&2
  return $status
}

echo "python: $("$python" --version 2>&1)"
"$python" - <<'PY' || true
for name in ("numpy", "scipy"):
    try:
        module = __import__(name)
        print(f"{name}: {module.__version__}")
    except Exception as error:
        print(f"{name}: UNAVAILABLE ({error})")
PY

# Step 0 is a gate, not one result among several: if this supplement is not the
# anonymous package it claims to be, nothing below is worth reading.
echo
echo "=============================================================="
echo "== anonymous-package contract, required (pinned in shipped code)"
echo "=============================================================="
if ! "$python" tools/anonymous_package_contract.py --root . --require-package; then
  echo "-- anonymous-package contract exit status: 1"
  echo
  echo "=============================================================="
  echo "== FAILED: this tree is not the declared anonymous package."
  echo "== Refusing to run the remaining checks, because they would"
  echo "== otherwise report on bytes this supplement does not vouch for."
  echo "=============================================================="
  exit 1
fi
echo "-- anonymous-package contract exit status: 0"

run "numerical-provenance ledger" \
  "$python" tools/verify_tmlr_submission_numbers.py \
  --root . --require-package --ledger ledger.json

run "artifact regeneration from the packaged aggregate (writes nothing)" \
  "$python" tools/transport_artifact_expectations.py --root . --require-package

run "SHA-256 sidecars for every shipped evidence file" check_evidence_sidecars

run "study tests" \
  "$python" -c 'import sys, pytest; sys.exit(pytest.main(["-q", "experiments/tests"]))'

echo
echo "=============================================================="
if [ "$overall" -eq 0 ]; then
  echo "== all supplement checks passed"
else
  echo "== at least one supplement check FAILED"
fi
echo "=============================================================="
exit "$overall"
