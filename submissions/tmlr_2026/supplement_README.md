# Supplement: transported-width experiments and fixed-history diagnostics

This anonymous compact supplement contains the evidence behind the manuscript's
full nonlinear follow-up, its exploratory fixed-history diagnostics, and the
historical earlier controlled audit. The current manuscript uses the nonlinear
follow-up. It supports numerical verification and table
and chart regeneration. It does not contain the raw trajectory archive.

## Contents

- `experiments/` contains the scientific implementation, aggregation and renderer,
  both protocols and configurations, the dependency declarations and wheel lock,
  and the study and follow-up configuration tests.
- `review/transport_review_followup/full-cce-full-local/` contains the complete
  compact follow-up export: execution and source configurations, optimizer
  selection, development/tuning/evaluation summaries, drift and bound summaries,
  and the export manifest. The directory name is a retained evidence identifier,
  not a raw-data location or a claim of durable external availability.
- `review/post_full_fable/independent/` contains the independent fixed-history
  analysis, its original-input inventory and its analysis script.
- `review/transport_relative_diagnostics/full/` contains the relative-width
  analysis, per-seed diagnostics, original-input inventory and checksums.
  `tools/analyze_relative_transport.py` contains the replay implementation.
- `review/v3_results/` and `review/v3_protocol/` contain the second study's
  per-run records, analysis, optimizer selection and development records;
  `experiments/transport_v3.py` and `experiments/analyze_transport_v3.py`
  contain its implementation and analysis. Their docstrings cite a protocol
  document that is not included; the manuscript appendix states the protocol.
  `review/v3_results/check_paper_numbers.py` recomputes the numbers these
  additions state. The second study ran with an earlier
  `experiments/transport_instantiation.py` whose `policy_scores` computed every
  policy's width factor; the included version computes only the selected
  policy's factor, with the same arithmetic, so its scores are unchanged for
  finite inputs.
- `review/relinearization_coverage/results/` contains the summaries of the
  realizable-trajectory example: `primary_summary.json` for the delayed-update
  coverage runs and `secondary_summary.json` for the policy runs.
  `experiments/relin_coverage.py`, `experiments/relin_policy.py` and
  `experiments/analyze_relin_coverage.py` contain its implementation and
  analysis. The example's protocol, run manifests, seed lists and per-seed
  records are not included, so these files support checking its stated values,
  not a canonical rerun; the runners' required `--protocol` argument names that
  missing document.
- `results/derived/transport_instantiation/` contains the earlier controlled
  audit's aggregate, optimizer selection, provenance records and checksums.
- `paper/` contains the active manuscript sources and generated artifacts.
  `tools/` contains the numerical ledger, the artifact checks and both pinned
  anonymous-evidence contracts.
- `ANONYMIZATION.json` describes the historical audit's metadata redaction.
  `FOLLOWUP_ANONYMIZATION.json` describes the follow-up's typed transformations
  and distinguishes original evidence from packaged copies.
- `SOURCE_CLOSURE.json` records the inputs read by the compiler. `verify.sh`
  runs the checks described below without executing new experiments.

The earlier audit contributes 21 artifacts. Its tables, CSVs and inactive figure sources retain their original bytes,
provenance records and checksum sidecars. The follow-up contributes separately generated
tables and explanatory charts with separate collective provenance records,
all independently pinned in code. The conceptual diagrams are reviewed
analytical schematics with separate source pins, not measured study outcomes.
The excluded legacy appendix, symbolic rate table, autodiff-GGN benchmark and
linear-bound benchmark are not evidence for the active manuscript and are not
included.

## Original evidence and anonymous copies

The historical `full_aggregate.json` and `selection.json` are **modified copies**:
exactly one top-level `git_revision` string in each is replaced by
`withheld-for-double-blind-review`. No numerical value, key, ordering or other
byte changes. Their checksum sidecars describe the packaged bytes; their
unchanged provenance records describe the original evidence.

The follow-up uses a separate, explicitly typed metadata transformation. It
redacts revision identifiers and normalizes local paths. References between
packaged compact files are rebound to their exact packaged hashes; scientific
values and settings are unchanged. The declaration specifies the transformations
and gives both original and packaged digests and sizes. Original raw-input
hashes retain their historical meaning under an explicitly external namespace:
they describe original, **unshipped** files. Historical run signatures, timing
records and runtime descriptions are not signatures of an anonymous raw archive.

Both declarations are claims, not authorities. The tools pin the exact evidence
paths, original and packaged bytes, declaration schemas and generated artifacts
in code. Editing evidence and then recomputing a sidecar, manifest or declaration
does not authorize the edit. Removing either required declaration fails package
verification rather than falling back to repository semantics.

Generated table and chart comments continue to attribute the original source
digests. A generator may use those attributions only after validating all packaged follow-up
bytes against the independent contract. This keeps original attribution distinct
from the hashes of anonymous copies. The ledger reports transformed evidence as
`PASS_ANON`, with an explicit statement that it is **NOT original evidence bytes**.
These content bindings do not independently authenticate a producer's identity.

## Compiled source closure

`SOURCE_CLOSURE.json` comes from the LaTeX recorder for the submitted PDF. Each
entry gives its staged name, source path, digest, byte count, role and `ships_in`:

- `supplement` — this archive carries the bytes, which the ledger checks.
- `source` — `source.zip` carries the venue template and vendored LaTeX packages.
- `neither` — no archive carries the bytes.

The only `neither` entry is `main.bbl`, generated by BibTeX from
`references.bib` and `tmlr.bst` in `source.zip`. Its digest and byte count are
pinned independently in `tools/anonymous_package_contract.py` and can be
reproduced by building a clean source archive. Missing, extra, duplicated or
remapped closure entries fail even when individual sidecars remain valid.

## Requirements and verification

Use Python 3.12 with NumPy 2.2.3 and SciPy 1.15.2. These are the declared versions
in `experiments/requirements.txt`. The supplied
`experiments/requirements-python312.lock` additionally pins the portable Linux
x86_64 wheel environment, including the test dependencies. A separate online
installation may use `pip install --require-hashes --only-binary=:all: -r
experiments/requirements-python312.lock`. The verification commands themselves
do not install or download anything.

```bash
python3 tools/check_python_environment.py
bash verify.sh
```

The environment checker checks installed package metadata, not installed-file
integrity. The wheel hashes apply at installation. The historical runtime
records remain distinct from this portable lock; the original replay analyzer
requires the recorded Python build as well as package versions for raw replay.

`verify.sh` first requires both anonymous-evidence contracts. If that gate fails,
it stops. Otherwise it prints each check's exit status and returns nonzero if any
check fails:

- **Numerical-provenance ledger:** derives every declared empirical literal from
  its pinned source, including the follow-up summaries, and checks its source
  context and display rounding. Every other numeric literal in the active
  compiled sources must have an explicit classification. Added or relocated
  numerical claims are rejected.
- **Historical artifact regeneration:** regenerates all 21 published tables,
  figures and CSVs from the packaged historical aggregate and requires byte
  equality with the pinned artifacts.
- **Follow-up terminal interval reconstruction:** independently resamples the
  complete per-seed evaluation summaries, verifies the configuration and
  selection bindings, and reconstructs all reported terminal intervals. The
  export manifest must describe exactly the files in its directory.
- **Follow-up table regeneration:** regenerates the manuscript tables from the
  packaged summaries and fixed-history outputs, verifies the original-source
  attribution, and requires exact artifact bytes.
- **Explanatory chart regeneration:** reconstructs every plotted mean, paired
  interval and bound-to-cap ratio from the fixed follow-up summaries, and
  requires exact TeX, CSV and provenance bytes. The outcome means are
  descriptive; the plotted intervals describe paired policy differences. The
  bound chart takes the logarithm after averaging the RHS, not before.
- **Evidence coverage:** scans the actual evidence directories. Each file must
  have a valid checksum sidecar or an exact, independently checked contract pin.
  An added file without coverage is a failure.
- **Study tests:** runs the shipped scientific algebra, seed, aggregation,
  artifact and follow-up configuration tests.

## What remains unavailable from this compact archive

- The historical controlled audit covers 2,400 trajectories, but its raw
  trajectories and original per-seed bootstrap inputs are absent. Its recorded
  bootstrap intervals therefore cannot be independently reconstructed here.
  The ledger reports that limitation as `NOT EXECUTED`.
- The nonlinear follow-up's per-seed summaries are included, so its terminal
  intervals **are** independently reconstructed. Its raw trajectories are not
  included. Their recorded hashes are checkable provenance metadata; the
  underlying raw bytes, roundwise fixed-history scans and optimizer replay are
  not verified by this archive. No synthetic raw inputs replace them.
- The raw follow-up archive is retained separately. This package does not assert
  a durable external download location or that a reviewer has received it.
  Analysis scripts are included for inspection and later replay with those
  original inputs and their recorded runtime. Running new adaptive experiments
  is a separate task and is not performed by `verify.sh`.

All floating-point audit results are tolerance-based diagnostics, not verified
numerical enclosures. Fixed-history alternative recommendations are not outcomes
of alternative adaptive policy trajectories.

## Editorial source checks

The exact original generator Python sources are included under
`tools/editorial_originals/`. Their independent digest pins are checked before
their bytes are loaded and executed. Original generation records keep their
original source hashes; the current editorial record separately identifies
original generator sources, current adapter hashes and the editorial tool hash.
Missing or changed original sources fail verification.

The original empirical generators reconstruct their original outputs before the
approved figure transforms. The transforms remove specified repeated annotations
and source comment payloads while preserving plotted values and coordinates.
Separate authenticated pins bind original and current figure bytes.
`tools/prepare_tmlr_figures.py --check` verifies those transforms and the separate
editorial provenance record. `tools/make_tmlr_outcomes.py --check` reconstructs the
current outcome table from the retained seed export and replays its paired
terminal intervals. Neither command runs a new adaptive study.

The historical manuscript prose is outside this archive's source closure. The
historical numerical evidence and its value/coordinate/hash checks remain here.
The ledger's current prose mappings retain selectors, units, populations and
rounding rules; semantic-unit pins bind the revised contexts.
