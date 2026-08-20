# Reviewing the transport instantiation from GitHub alone

This is the entry point for a reviewer who has GitHub access, no local checkout,
and no copy of the raw experiment tree.

The evidence for the transport-instantiation study lives in two committed files
that GitHub cannot render: the optimizer selection (1.2 MB) and the full
aggregate (77 MB). Everything below exists so that you do not have to take those
files on trust, and so that nobody can quietly overstate what has been checked.

Nothing in this tooling changed a theorem, a proof, an experiment output, a
reported number, a policy behavior, or any locked artifact.

## Start here

| What you want | Where to look |
| --- | --- |
| The headline claims, recomputed | [`review/transport_instantiation/locked_claims.json`](review/transport_instantiation/locked_claims.json) |
| What is and is not verifiable | [`review/transport_instantiation/README.md`](review/transport_instantiation/README.md) |
| File inventory, hashes, limitations | [`review/transport_instantiation/manifest.json`](review/transport_instantiation/manifest.json) |
| The optimizer selection, in small pieces | [`review/transport_instantiation/selection/`](review/transport_instantiation/selection/) |
| The aggregate, in small pieces | [`review/transport_instantiation/aggregate/`](review/transport_instantiation/aggregate/) |
| What the typeset paper actually looks like | [`review/transport_instantiation/pdf/`](review/transport_instantiation/pdf/) |

Every file in the review bundle is at most 750,000 bytes, so GitHub and its
connectors can display all of them. Larger record collections are split at
record boundaries into `*.part-NNN.jsonl`, and the manifest records a SHA-256,
a byte count and a record count for every part. No record is dropped.

## The evidence hierarchy

The point of this document is that these five levels are **not**
interchangeable. Levels 1 to 3 are available from GitHub. Levels 4 and 5 are
not, and nothing here is a substitute for them.

### Level 1 — direct committed-file hash verification

Recompute a SHA-256 over bytes that are actually in the repository.

Covers the selection, the aggregate, the PDF, the three transport tables, the
three transport figure sources, the twelve panel CSVs, and every sidecar.

**Available from GitHub.**

### Level 2 — independent recomputation from the committed selection and aggregate

Rederive a published number from committed JSON, using an implementation that
is not the one that produced it.

Covers the optimizer selection replay (nine candidates, 120 equally weighted
cells each, eligibility, the deterministic tie rule, and the winner), the
canonical input-inventory digests, the exact Clopper-Pearson intervals, the
certificate-tightness medians and zero-denominator counts recomputed from
`path_points`, and byte-exact regeneration of all 21 generated artifacts from
the committed aggregate.

The Clopper-Pearson recomputation deliberately uses a standard-library
incomplete-beta implementation rather than the SciPy call that produced the
published values, so agreement is evidence rather than tautology.

**Available from GitHub.**

### Level 3 — structural verification of provenance inventories whose raw files are absent

Check that a provenance record is internally consistent: the sidecar names the
artifact, its digest matches, its inventory equals the inventory embedded in the
artifact, and the canonical digest over that inventory reproduces.

This proves the inventory was not edited after the fact. It does **not** prove
that any raw file has the content the inventory claims, because those files are
not in the repository. The verifier reports this as `STRUCTURAL PASS` and never
collapses it into full provenance verification.

**Available from GitHub.**

### Level 4 — full raw-input validation

Content-hash the 4,321 tuning summary files the selection binds and the raw
evaluation tree the aggregate binds, and run
`experiments.artifact_utils.validate_aggregate_provenance_sidecar`, which
requires every declared input to exist on disk.

Also at this level: the deterministic paired bootstrap. The committed aggregate
stores per-cell descriptive summaries only. The per-seed values the bootstrap
resamples are not in it, so the published intervals cannot be recomputed from
GitHub. The algorithm, level, resample count and child seeds are exported in
[`review/transport_instantiation/aggregate/bootstrap.json`](review/transport_instantiation/aggregate/bootstrap.json)
so the recomputation becomes possible the moment the raw tree is available. No
synthetic per-seed data is manufactured to fake it.

**Requires the original raw tree. Not available from GitHub.**

### Level 5 — complete experiment rerun

Regenerate `results/raw/` and therefore the selection and the aggregate from
scratch.

**Requires executing the experiment. Not available from GitHub.**

## What this is not

This repository is **not** fully reproducible from GitHub, and this document
does not claim otherwise. Levels 1 to 3 let you confirm that the committed
evidence is internally consistent, that the published statistics follow from the
committed aggregate, and that the manuscript reports what the aggregate says.
They cannot tell you that the aggregate is a faithful summary of runs you cannot
see.

Two further limits worth stating plainly:

- The float64 Cholesky, eigenvalue and quadrature checks recorded by the study
  are diagnostics. They are not verified numerical enclosures, and no tool here
  upgrades them.
- Contact sheets and page renders are evidence about typesetting: clipping,
  overlap, missing panels, illegible labels. They are not evidence that a
  theorem is correct.

## Running the checks yourself

```bash
# 1. detached verifier: works with results/raw/ absent
python tools/verify_transport_committed_evidence.py

# 2. regenerate the review bundle and require byte equality
python tools/export_transport_github_review_bundle.py --output /tmp/bundle
diff -ru --exclude=pdf review/transport_instantiation /tmp/bundle

# 3. rebuild the PDF audit package (needs a PDF renderer)
python tools/export_transport_pdf_audit.py --output review/transport_instantiation/pdf

# 4. tests
python -m pytest -q tests/test_transport_github_review_bundle.py \
  experiments/tests/test_transport_instantiation.py \
  experiments/tests/test_transport_instantiation_aggregate.py \
  experiments/tests/test_transport_instantiation_artifacts.py

# 5. sidecars
sha256sum -c results/derived/transport_instantiation/selection.json.sha256
sha256sum -c results/derived/transport_instantiation/full_aggregate.json.sha256
( cd paper && sha256sum -c main.pdf.sha256 )
```

The verifier prints one line per check, prefixed with its status, and exits
nonzero if anything fails. The statuses are deliberately distinct:

| Status | Meaning |
| --- | --- |
| `PASS` | directly verified committed evidence |
| `PASS_RECOMPUTED` | independently recomputed statistic |
| `STRUCTURAL_PASS` | provenance structure verified, raw bytes absent |
| `KNOWN_DIVERGENCE` | pinned and explained, not silently accepted |
| `NOT_EXECUTED` | requires raw data or experiment execution |
| `FAIL` | mismatch |

`.github/workflows/transport-committed-evidence.yml` runs all of the above on
every pull request and push that touches the paper, experiments, evidence,
review bundle or tooling.

## One known divergence

`experiments/make_transport_instantiation_artifacts.py` does not match the
study-source snapshot recorded inside `selection.json`.

- snapshot (at `0cd6264`, the revision `selection.json` records):
  `2c950ca777347a47e753f5bc6aa0c3e39bc8d17386de9f9e712b1f0a6733181b`
- HEAD: `5886932695fabfcc174798e94c93d372a09ffa9f51543ce3e1bcdc7c9297ba16`

The selection was frozen at `0cd6264`. Commit `93eaa537` then finished the
renderer, changing curve downsampling, histogram binning and per-target CSV
names. The file is not an input to tuning or aggregation: it appears in neither
`selection.inputs` nor `aggregate.inputs`, so the optimizer selection is
unaffected. All 21 generated artifacts regenerate byte-identically from the
committed aggregate using the HEAD renderer, which is what shows the locked
artifacts were produced by it.

The divergence is pinned by hash in the verifier rather than tolerated
generically. Any other study-source file that drifts, or this file changing away
from the recorded HEAD hash, is a hard failure.

## PDF rebuild status

`make clean && make pdf` in a clean tree at the locked head, with
`SOURCE_DATE_EPOCH` taken from the implementation commit, produces a **63-page,
semantically identical, byte-different** PDF.

The only differences are `/CreationDate`, `/ModDate` and `/ID`. Page count,
extracted text and all 63 page rasters are identical, as are every committed
table and figure source consumed by the build. The locked PDF was never
overwritten; the comparison is done against a copy.
