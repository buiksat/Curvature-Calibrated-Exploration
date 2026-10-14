# Retained raw archive status

Audit date: 2026-10-14. The complete follow-up run is retained locally at
`/workspace/cce-full-local`. These are the original execution artifacts. This
audit read and hashed them; it did not rerun experiments or modify original
data, configurations, source files, or receipts.

| Scope | Trajectories | Files | Bytes |
|---|---:|---:|---:|
| Evaluation raw tree | 600 | 3,000 | 3,723,674,108 |
| Tuning raw tree | 270 | 1,350 | 271,805,985 |
| Development raw tree | 24 | 120 | 148,899,054 |
| Complete raw tree | 894 | 4,470 | 4,144,379,147 |
| Complete retained run, including aggregate and supporting files | 894 | 4,485 | 4,182,046,431 |

Each trajectory has a raw log, manifest, summary, summary hash sidecar, and
completion receipt. Evaluation `raw.jsonl` files alone total 3,715,685,774
bytes. Counts above describe the uncompressed directory tree, not a compressed
archive. The separate compact follow-up export contains 14 files totaling
3,009,864 original bytes.

## Checks completed

- Every input hash matched local bytes in the compact export's 3,483-row raw
  input inventory, the independent analysis's 3,004-row inventory, and the
  relative diagnostic analysis's 3,005-row inventory. Declared byte counts
  matched wherever recorded. The export inventory covers 2,400 evaluation
  inputs, 1,080 tuning inputs, and three supporting files; it is not an
  inventory of the development tree.
- All 894 completion receipts matched the hashes of their four referenced
  files and the original run signature. The run signature independently
  recomputed from its recorded identity fields.
- All 32 original source-input hashes recorded in `run.json` matched the
  current repository files. They were checked again when this report was
  written. Original source/configuration bytes remain unchanged; anonymous
  transformations apply only to separate staged copies.
- Both analysis script hashes matched their recorded values. All eight
  checksummed independent-analysis artifacts and all three checksummed
  relative-analysis artifacts matched. These integrity checks do not repeat
  either analysis's scientific calculations.
- The compact export verifier independently recomputed all 24 terminal
  intervals from 600 evaluation summaries. The environment checker matched
  all 13 exact dependency pins. Raw-dependent scans and optimizer replay were
  not rerun during this audit.
- The retained quadrature-refinement ZIP and all its declared members matched
  their recorded hashes. It contains original runtime metadata and is not an
  anonymous raw-data release.

## Anonymous release and remaining gaps

The implemented anonymous evidence contract covers the compact export and
authoritative exploratory outputs: 20 evidence files plus six generated
artifacts. Its staged copies preserve scientific JSON values, redact specified
metadata, and update dependent hashes. Original external-input hashes remain
explicitly distinguished from packaged-file hashes. The anonymous compact
export still recomputes all 24 terminal intervals, and its identity scan
passes.

**No sanitized raw archive has been built. No durable anonymous hosting
location has been supplied or verified.** The retained original raw tree
contains identifying Git revisions and machine-specific paths in provenance;
it must not be presented as the anonymous supplement. A separate reviewed
transformation, complete hash-chain validation, archive integrity check, and
durable anonymous delivery location remain necessary before distributing raw
data anonymously. Preserve the originals throughout that process.

The relative-analysis replay also requires the exact recorded Python build,
in addition to NumPy/SciPy versions and thread settings. The current local
environment meets that requirement; the dependency lock alone does not
guarantee replay on an arbitrary Python build.

The original near-linear study is separate. Its raw trajectories are absent
from this checkout, and the new follow-up archive does not recover them.
Historical raw-byte validation and raw-dependent statistical reconstruction
therefore remain unavailable. Compact evidence integrity, retained follow-up
raw data, and complete anonymous raw reproducibility are distinct statuses.
