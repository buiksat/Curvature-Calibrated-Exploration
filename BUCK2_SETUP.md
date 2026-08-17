# Buck2 setup

## Host prerequisites

This checkout uses the Meta host toolchain. A clean checkout requires:

- `buck2` on `PATH`; the checked-in `.buck2` DotSlash manifest pins the build;
- `/data/repos/fbsource` with the platform010 Python 3.12 toolchain, Prelude,
  and declared third-party targets;
- Linux x86-64 with glibc compatible with the checked-in CPython wheels.

The `.buck/fbsource_cell` links expose the required host cell. Buck actions are
local because remote execution cannot dereference those links. If
`/data/repos/fbsource` is absent, the configured build cannot run. Do not replace
declared dependencies with pip packages or a virtual environment.

Validate the checkout from the repository root:

```bash
test -d /data/repos/fbsource
buck2 --version
buck2 root
buck2 audit cell
buck2 targets //...
(cd third_party/wheels && sha256sum -c SHA256SUMS)
```

Run repository Python entry points through Buck rather than invoking Python,
pip, or pytest directly.

## Tests

Run the complete test targets:

```bash
buck2 test //tests:tests //experiments/tests:tests -- --timeout=1200
```

For a combined pytest report through the Buck-built runner:

```bash
buck2 run //tools:pytest_runner -- -q tests experiments/tests
```

Validate the manuscript sources with:

```bash
buck2 run //paper:validate
```

The retained experiment commands, seed partitions, artifact generators, and
raw-data requirements are documented in
[experiments/README.md](experiments/README.md).  These diagnostics predate the
current confidence-transport theorem and do not validate it.
