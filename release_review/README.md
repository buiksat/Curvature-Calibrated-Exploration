# Anonymous supplementary material

This review-tier release contains the anonymous paper,
experiment implementation and configuration, tests, every derived artifact,
and the table and figure regeneration inputs.  It intentionally includes only
one deterministic representative raw trajectory per top-level study.
`MANIFEST.json` binds every released file.  The anonymous source-tree digest is
`df93d7794dc36706bccf861a1ade9f9ae172e2423eccaece031c727424e6adc3`.

## Environment

```sh
python -m venv .venv
.venv/bin/pip install -r experiments/requirements.txt
.venv/bin/python -m pytest -q tests experiments/tests
```

## Raw records

Run the following from the release root before invoking an aggregator.  It
restores each `raw.jsonl` beside its compressed archive without deleting the
archive.

```sh
find results/raw -name '*.zst' -exec sh -c 'for p do; zstd -q -d -f "$p" -o "${p%.zst}"; done' sh {} +
```

The command above restores only the representative trajectories.
It does not reconstruct the full experiment corpus, so the published full
aggregates cannot be regenerated from this smaller tier alone.

`manifests/full-raw-index.json` binds every non-smoke source raw file by its original
path and SHA-256 and records whether an anonymized copy is released.  Provenance
entries marked `indexed_not_released` are deliberately absent and are validated
against that index; they are not claimed as locally available inputs.

## Paper

```sh
make pdf
```

Generated table and figure inputs are under `results/derived`.  Run and source
inventories are under `manifests`.
