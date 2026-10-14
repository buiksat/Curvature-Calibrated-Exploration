# Legacy Buck2 host setup

Buck is not the supported reproducible execution path. Use the pinned,
hash-verified direct-Python environment in [PYTHON_SETUP.md](PYTHON_SETUP.md)
for new review runs and tests. The commands below document the historical Meta
host integration; they are not evidence that Buck currently builds or tests.
The repository's recorded validation reports an unresolved `root_values` block
during Prelude evaluation, and an ordinary checkout also lacks the host cell.

## Host prerequisites

This checkout uses the Meta host toolchain. A clean checkout requires:

- `buck2` on `PATH`; the checked-in `.buck2` DotSlash manifest pins the build;
- `/data/repos/fbsource` with the platform010 Python 3.12 toolchain, Prelude,
  and declared third-party targets;
- Linux x86-64 with glibc compatible with the historical CPython wheel targets.

The `.buck/fbsource_cell` links expose the required host cell. Buck actions are
local because remote execution cannot dereference those links. If
`/data/repos/fbsource` is absent, the configured build cannot run. The SciPy
target also names version 1.13.1 through an absolute host symlink, while the
declared direct-Python version is 1.15.2. The link is not a vendored wheel and
is dangling without that external file. These historical dependency files and
checksums remain unchanged; they are not inputs to the supported Python lock.

To diagnose the legacy host integration, inspect it from the repository root:

```bash
test -d /data/repos/fbsource
buck2 --version
buck2 root
buck2 audit cell
buck2 targets //...
(cd third_party/wheels && sha256sum -c SHA256SUMS)
```

Do not report these commands as successful until the host cell, Prelude issue,
and dependency mismatch are repaired and the commands actually pass. A direct
Python test pass does not establish a working Buck build.

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
