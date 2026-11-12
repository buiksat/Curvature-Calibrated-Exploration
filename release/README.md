# Anonymous supplementary material

This release contains the anonymous paper, experiment
implementation and configuration, tests, derived tables and figure data, and
artifact-preserving compressed per-round records.  `MANIFEST.json` binds every
released file.  The anonymous source-tree digest is `df93d7794dc36706bccf861a1ade9f9ae172e2423eccaece031c727424e6adc3`.

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

The experiment commands and aggregation entry points are documented in
`experiments/README.md`.  Released provenance binds the compressed records;
newly generated aggregates bind the restored records.

## Paper

```sh
make pdf
```

Generated table and figure inputs are under `results/derived`.  Run and source
inventories are under `manifests`.
