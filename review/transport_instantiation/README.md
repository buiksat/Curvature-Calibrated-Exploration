# GitHub-only review bundle: transport instantiation

Deterministic, small extracts of the locked transport-instantiation evidence, so
a reviewer with GitHub access but no local checkout and no raw experiment tree
can inspect and recompute as much as is logically possible.

Nothing in this directory is a new scientific result. Every file is derived from
two locked inputs whose SHA-256 values are checked before they are read.

## Provenance

| Field | Value |
| --- | --- |
| Repository | `https://github.com/buiksat/Curvature-Calibrated-Exploration` |
| Source branch | `codex/cc-ucb-theory-experiments` |
| Review base commit | `47037a2df6b81befd4a0cb3c5974e3565d8f61b6` |
| Implementation commit | `93eaa537d2702d5d18b05905913b0b879e3d608f` |
| Source HEAD | `7a83c5f2c7f710be1e8178682cbfcd8566244a48` |
| Generator | `tools/export_transport_github_review_bundle.py` |
| Generator SHA-256 | `702cae39adc9ec23adf9b0e7aed12d1b8e4cb085032012ad084bfeb54d1fa308` |
| Bundle format | `transport-github-review-bundle/1` |

## Locked files this bundle is derived from

These are never modified. The generator refuses to run if any hash moves.

| File | SHA-256 |
| --- | --- |
| `results/derived/transport_instantiation/selection.json` | `8c16bec7cc220109df3fd7173c3d06ae6c6e1b95e9db5bc5b8c3377b3564f6f4` |
| `results/derived/transport_instantiation/full_aggregate.json` | `0ddebd4915dd2e264e24b7b25047d24f86c3cdf63930a1e6df77585e0b97de02` |
| aggregate input inventory (canonical digest) | `4af9f51467981326c4f99ef171dc21e3fb27beb4d519b65d28d18f678e65ef66` |
| `paper/main.pdf` | `2545c368d6b97393f5c1e5bb61d4696f7fed6b8ae988ce42c9d7bc7ccab717e1` |

## Verified directly from committed files

Checked by recomputing a SHA-256 over bytes that are present in the repository.

- The selection, aggregate and PDF hashes in the table above.
- The 21 generated table, figure and CSV artifacts, each
  bound to the aggregate hash, together with their `.sha256` and
  `.provenance.json` sidecars.
- Every file in this bundle, against `manifest.json`.

## Recomputed from committed aggregate

Recomputed by `tools/verify_transport_committed_evidence.py` from the committed
JSON, not copied from documentation.

- Optimizer selection: 9 candidates over
  120 equally weighted (seed, horizon, target_D) cells,
  eligibility, the deterministic tie rule, and the winner
  (`candidate-008`, learning rate 0.0003,
  20 steps per round, aggregate tuning MSE
  0.00666914978044266).
- The canonical aggregate input-inventory digest over
  13923 input records.
- Exact Clopper-Pearson intervals for all 24 primary
  coverage cells, computed with a standard-library incomplete-beta
  implementation rather than the SciPy call that produced them.
- Certificate-tightness medians and zero-denominator counts, recomputed from
  `path_points` and compared against the published `certificate_tightness`
  section in `aggregate/path_recomputed_summaries.jsonl`.
- Table and figure bytes, regenerated in memory from the committed aggregate
  through the repository's pure rendering functions.

## Structurally verified but dependent on absent raw inputs

The structure of the provenance record is checked. The bytes it points at are
not present, so their content is *not* verified. This is reported as
`STRUCTURAL PASS` and is never collapsed into full provenance verification.

- The selection binds 4321 tuning input records and the
  aggregate binds 13923 input records under `results/raw/`,
  which is not committed.
- Sidecar inventories are checked for exact equality with the inventory
  embedded in the artifact, and the canonical digest over each inventory is
  recomputed. That proves the inventory was not edited; it does not prove any
  raw file has the recorded content.

## Requires raw experiment data

Not attempted from GitHub alone.

- Content hashing of the 4321 tuning summary files and the
  raw evaluation trees.
- `experiments.artifact_utils.validate_aggregate_provenance_sidecar`, which
  requires every declared input to exist on disk.
- The deterministic paired bootstrap. The aggregate stores per-cell descriptive
  summaries only; the per-seed values the bootstrap resamples live in
  `results/raw/`. The resampling algorithm, its level, its resample count and
  its child seeds are exported in `aggregate/bootstrap.json` so the interval can
  be reproduced once the raw tree is available. No synthetic per-seed data is
  manufactured.

## Requires executing the experiment

- Reproducing `results/raw/` and therefore the selection and aggregate from
  scratch.
- Any claim that the study would produce the same numbers on different
  hardware.

## PDF visual evidence

`pdf/` holds a rendered audit package for `paper/main.pdf` (63 pages,
933908 bytes). It contains structural output, extracted text, a
page-to-section index, contact sheets and full-resolution renders of the pages
carrying the transport theorems, the experiment, the tables and the three
figures.

Contact sheets and renders show what the typeset page looks like. They are
evidence about layout, clipping, overlap and legibility. They are not evidence
that a theorem is correct.

## Scope and non-claims

- No theorem, proof, experiment output, reported number, policy behavior or
  locked artifact was changed to produce this bundle.
- Float64 diagnostics recorded by the study are diagnostics. They are not
  verified numerical certificates, and nothing here upgrades them.
- `STRUCTURAL PASS` is not full provenance verification.
- This bundle does not make the study reproducible from GitHub. Levels 1 to 3 of
  the evidence hierarchy in `GITHUB_ONLY_TRANSPORT_REVIEW.md` are available
  here; levels 4 and 5 require the raw tree or a full rerun.
- One study-source file diverges from the selection-time snapshot by design; see
  `manifest.json` under `limitations.known_study_source_divergences`.

## Regenerating and verifying

```bash
python tools/export_transport_github_review_bundle.py --output review/transport_instantiation
python tools/verify_transport_committed_evidence.py

# byte-for-byte determinism
python tools/export_transport_github_review_bundle.py --output /tmp/transport-review-bundle
diff -ru review/transport_instantiation /tmp/transport-review-bundle
```

`pdf/` is produced separately, because it needs a PDF renderer rather than the
standard library:

```bash
python tools/export_transport_pdf_audit.py --output review/transport_instantiation/pdf
```
