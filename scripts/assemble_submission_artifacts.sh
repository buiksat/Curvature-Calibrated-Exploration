#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

assembly_started_epoch="$(date +%s)"
assembly_started_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ALLOW_DIRTY_SOURCE="${ALLOW_DIRTY_SOURCE:-0}"
if [[ "$ALLOW_DIRTY_SOURCE" != 0 && "$ALLOW_DIRTY_SOURCE" != 1 ]]; then
  printf 'ALLOW_DIRTY_SOURCE must be 0 or 1\n' >&2
  exit 2
fi
if [[ -z "$(git status --porcelain --untracked-files=normal)" ]]; then
  source_worktree_clean=true
else
  source_worktree_clean=false
fi
if [[ "$source_worktree_clean" != true && "$ALLOW_DIRTY_SOURCE" != 1 ]]; then
  printf 'refusing to assemble upload artifacts from a dirty worktree\n' >&2
  exit 2
fi

DESTINATION="${1:-release_review/submission_bundle}"
EXPECTED_SCALED_FILES=48002
SOURCE_BUNDLE_SHA256_FILE="results/derived/raw_bundles/scaled_tanh_instantiation/scaled_tanh_instantiation-full.tar.gz.sha256"

if [[ -e "$DESTINATION" ]]; then
  printf 'destination already exists: %s\n' "$DESTINATION" >&2
  exit 2
fi

PROFILE=full scripts/bundle_scaled_tanh_raw.sh verify
PROFILE=smoke scripts/bundle_wheel_raw.sh verify

parent="$(dirname "$DESTINATION")"
mkdir -p "$parent"
staging="$(mktemp -d "$parent/.submission_bundle.XXXXXX")"
trap 'rm -rf "$staging"' EXIT

buck2 run //tools:build_anonymous_supplement -- \
  --tier review \
  --hydrate-raw \
  --output "$staging/anonymous_review_supplement"

scaled_release_root="$staging/anonymous_review_supplement/results/raw/scaled_tanh_instantiation/full"
scaled_file_count="$(find "$scaled_release_root" -type f | wc -l)"
if [[ "$scaled_file_count" -ne "$EXPECTED_SCALED_FILES" ]]; then
  printf 'anonymous release has %s scaled-tanh files; expected %s\n' \
    "$scaled_file_count" "$EXPECTED_SCALED_FILES" >&2
  exit 1
fi

release_manifest="$staging/anonymous_review_supplement/MANIFEST.json"
jq -e '
  .release_kind == "anonymous_review_supplement"
  and .release_tier == "review"
  and .raw_hydration.legacy_smoke_workspace_excluded == false
  and .raw_hydration.source_bundle_workspace_excluded == true
' "$release_manifest" >/dev/null
jq -e '.identity_scan.status == "passed"' "$release_manifest" >/dev/null
jq -e '.raw_hydration.status == "complete_available_source_payloads_with_declared_legacy_gaps"' \
  "$release_manifest" >/dev/null
source_reference_validation_status="$(
  jq -r '.source_reference_validation.status' "$release_manifest"
)"
case "$source_reference_validation_status" in
  passed|passed_with_declared_unavailable_inputs) ;;
  *)
    printf 'release source-reference validation failed: %s\n' \
      "$source_reference_validation_status" >&2
    exit 1
    ;;
esac
release_manifest_sha256="$(sha256sum "$release_manifest" | cut -d' ' -f1)"
release_file_count="$(find "$staging/anonymous_review_supplement" -type f | wc -l)"
identity_scan_files="$(jq -r '.identity_scan.files_scanned' "$release_manifest")"
unavailable_raw_occurrences="$(
  jq -r '.raw_hydration.unavailable_source_inputs.occurrence_count' \
    "$release_manifest"
)"
unavailable_raw_unique_files="$(
  jq -r '.raw_hydration.unavailable_source_inputs.unique_file_count' \
    "$release_manifest"
)"
anonymous_source_tree_sha256="$(jq -r '.anonymous_source_tree_sha256' "$release_manifest")"
source_bundle_sha256="$(cut -d' ' -f1 "$SOURCE_BUNDLE_SHA256_FILE")"

tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner \
  --use-compress-program='gzip -n -1' \
  -cf "$staging/anonymous_review_supplement.tar.gz" \
  -C "$staging" anonymous_review_supplement
tar -tzf "$staging/anonymous_review_supplement.tar.gz" \
  > "$staging/ARCHIVE_MEMBERS.txt"
if rg -q '/(tools/build_anonymous_supplement.py|tests/test_anonymous_supplement.py)$' \
  "$staging/ARCHIVE_MEMBERS.txt"; then
  printf 'private release tooling is present in the final archive\n' >&2
  exit 1
fi
archived_manifest_sha256="$(
  tar -xOzf "$staging/anonymous_review_supplement.tar.gz" \
    anonymous_review_supplement/MANIFEST.json \
    | sha256sum \
    | cut -d' ' -f1
)"
if [[ "$archived_manifest_sha256" != "$release_manifest_sha256" ]]; then
  printf 'archived release manifest does not match the scanned tree\n' >&2
  exit 1
fi
archive_sha256="$(
  sha256sum "$staging/anonymous_review_supplement.tar.gz" | cut -d' ' -f1
)"
rm -rf "$staging/anonymous_review_supplement"

jq -n \
  --arg archive "anonymous_review_supplement.tar.gz" \
  --arg archive_sha256 "$archive_sha256" \
  --arg assembly_started_utc "$assembly_started_utc" \
  --arg anonymous_source_tree_sha256 "$anonymous_source_tree_sha256" \
  --arg release_manifest_sha256 "$release_manifest_sha256" \
  --arg source_bundle_sha256 "$source_bundle_sha256" \
  --arg source_reference_validation_status "$source_reference_validation_status" \
  --argjson archive_size_bytes "$(stat -c %s "$staging/anonymous_review_supplement.tar.gz")" \
  --argjson assembly_elapsed_seconds "$(( $(date +%s) - assembly_started_epoch ))" \
  --argjson identity_scan_files "$identity_scan_files" \
  --argjson release_file_count "$release_file_count" \
  --argjson scaled_tanh_file_count "$scaled_file_count" \
  --argjson source_worktree_clean "$source_worktree_clean" \
  --argjson unavailable_raw_occurrences "$unavailable_raw_occurrences" \
  --argjson unavailable_raw_unique_files "$unavailable_raw_unique_files" \
  '{
    archive: $archive,
    archive_sha256: $archive_sha256,
    archive_size_bytes: $archive_size_bytes,
    anonymous_source_tree_sha256: $anonymous_source_tree_sha256,
    assembly_elapsed_seconds: $assembly_elapsed_seconds,
    assembly_started_utc: $assembly_started_utc,
    identity_scan: {
      files_scanned: $identity_scan_files,
      status: "passed"
    },
    release_file_count: $release_file_count,
    release_manifest_sha256: $release_manifest_sha256,
    raw_copy_semantics: "identity-scanned transformed copies bound to original source hashes by the release manifest",
    scaled_tanh_file_count: $scaled_tanh_file_count,
    schema_version: 1,
    source_scaled_tanh_bundle_sha256: $source_bundle_sha256,
    source_reference_validation_status: $source_reference_validation_status,
    source_worktree_clean: $source_worktree_clean,
    unavailable_raw_reference_occurrences: $unavailable_raw_occurrences,
    unavailable_raw_unique_files: $unavailable_raw_unique_files,
    upload_status: "not_uploaded"
  }' > "$staging/ASSEMBLY_REPORT.json"

(
  cd "$staging"
  {
    printf '%s  %s\n' "$archive_sha256" ./anonymous_review_supplement.tar.gz
    sha256sum ./ARCHIVE_MEMBERS.txt ./ASSEMBLY_REPORT.json
  } | sort -k2 > SHA256SUMS
)

mv "$staging" "$DESTINATION"
trap - EXIT
printf 'submission artifacts: %s\n' "$DESTINATION"
printf 'upload the complete directory through an approved anonymous reviewer channel\n'
