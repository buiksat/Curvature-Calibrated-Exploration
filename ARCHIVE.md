# TMLR cleanup archive

The active research branch is `cce-review-revisions`. Its pre-cleanup contents
are preserved at commit `ea33d2fc4f93ac831dfe7ae31fa3cfdc114cba42`, tagged
`archive/research-before-tmlr-cleanup-2026-11-12`. The manuscript mirror is
preserved at `archive/main-before-tmlr-cleanup-2026-11-12`.

## Retired material

[ARCHIVED_FILES.json](ARCHIVED_FILES.json) lists every removed research file,
its original Git blob, SHA-256 digest, byte count, and mode. The archive contains
historical AISTATS and CODE@MIT manuscripts, the frozen pre-rewrite PDF and its
rendered audit, the redundant flat selection export and its sidecars, the
separate deferred Covertype implementation and review records, and host-specific
Buck infrastructure. The deferred extension remains an unfinished historical
workstream; archiving it does not clear its recorded evidence blockers.

The archived files are outside the active TMLR source and experiment closures.
Current scientific sources, experiment code/configurations, the original
near-linear aggregate and provenance, follow-up evidence, numerical tables,
and vendored TeX packages remain active.

## Retrieve an original file

Fetch the archive tag if a shallow checkout lacks its commit:

```bash
git fetch origin tag archive/research-before-tmlr-cleanup-2026-11-12
```

Inspect a file without restoring it to the checkout:

```bash
git show ea33d2fc4f93ac831dfe7ae31fa3cfdc114cba42:paper/main.tex
```

Extract the complete snapshot into an unused directory outside the checkout:

```bash
mkdir /tmp/cce-historical-snapshot
git archive ea33d2fc4f93ac831dfe7ae31fa3cfdc114cba42 | tar -x -C /tmp/cce-historical-snapshot
```

## Integrity and verification

```bash
python tools/archived_inputs.py
python tools/verify_transport_committed_evidence.py
```

The first command checks the complete retirement inventory against the immutable
Git tree. Historical PDF, PDF-audit, flat-selection, and Buck-source checks
explicitly authenticate their archived originals and extract only the needed
files into temporary directories. They retain their original hashes and
scientific checks. Missing current scientific inputs cannot use that fallback.
The PDF checks concern the archived 63-page snapshot, not the current TMLR PDF.

The GitHub review bundle was regenerated for the current exporter; its scientific
JSON/JSONL extracts remain unchanged. `experiments/README.md` now documents direct
Python commands. The verifier records that exact documentation-only change as
a known divergence from the historical study-source snapshot; it still rejects
unrecognized changes to current implementation inputs.

The active validator and Makefile now target TMLR. CI retains the current
submission tests, strict packaging, numerical ledger, fresh source-archive
rebuild and extracted supplement checks. The deferred extension's old tests,
job definition and results remain in the archive, outside active CI. The root
configuration test still checks disjoint seeds for every retained configuration.

Cleanup removes files from active trees. Git history and archive tags preserve
their storage and provenance; this is not a history rewrite or experiment rerun.
