# Supplement: controlled transport-instantiation study

This is the reproducibility material for the controlled scaled-tanh audit
reported in the paper. It is anonymous: it carries no author, institution,
repository or host information.

## What is here

```
experiments/                         study implementation, aggregation, renderer
  TRANSPORT_INSTANTIATION_PROTOCOL.md  the frozen protocol
  configs/transport_instantiation.yaml the frozen configuration
  requirements.txt                     declared package versions
  tests/                               the three study test modules
paper/                               manuscript sources, generated tables and
                                     figures, with SHA-256 sidecars and
                                     per-artifact provenance records
results/derived/transport_instantiation/
  full_aggregate.json                  the aggregate (the evidence; see below)
  selection.json                       the optimizer-selection record
  *.provenance.json, *.sha256          provenance and digests
tools/
  anonymous_package_contract.py        the redaction contract, pinned in code
  verify_tmlr_submission_numbers.py    executable numerical-provenance ledger
  transport_artifact_expectations.py   in-memory artifact regeneration check
  tex_conditionals.py                  resolves the manuscript's venue switch
ANONYMIZATION.json                   what was redacted for double-blind review
SOURCE_CLOSURE.json                  every file the compiler read, with digests
verify.sh                            runs every check below
```

`SOURCE_CLOSURE.json` is the authoritative list of submitted inputs. It is not a
list of files someone wrote down: it comes from the LaTeX recorder's own `.fls`
output for the build that produced the submitted PDF, so it cannot disagree with
what was typeset. Each entry gives the staged name, the repository path, the
SHA-256, the byte count, the role, and `ships_in`.

`ships_in` says where the bytes are, and it has exactly three values:

- `supplement` — this archive carries the file, and the ledger recomputes its
  digest from the bytes beside you.
- `source` — `source.zip` carries it. That is the venue template and the four
  vendored LaTeX packages, which a paper supplement has no reason to duplicate.
- `neither` — no archive carries it.

The only `neither` entry is `main.bbl`. Bibtex writes it during the build from
`references.bib` and `tmlr.bst`, both of which are in `source.zip`, and the
result is not shipped anywhere. It exists to you as the digest and byte count
recorded here, pinned independently in `tools/anonymous_package_contract.py`, and
reproducible by running bibtex on a clean `source.zip` unpack. Earlier wording
said every entry outside the supplement was in `source.zip`; that was wrong for
this one entry and is why the field is no longer a boolean.

The expected set of entries is pinned in
`tools/anonymous_package_contract.py`, not in this file, so the manifest cannot
vouch for itself: a missing, extra, duplicated or remapped entry fails whatever
the sidecars say. A `.sha256` sidecar tells you the bytes are the expected ones;
only the closure tells you the compiler read the file at all.

`paper/tables/` and `paper/figures/` carry the 21 artifacts this study
generates, each with its sidecar and provenance record, plus one symbolic table
of asymptotic rates. They do **not** carry the project's older autodiff-GGN and
linear-bound benchmark outputs: those were designed for an earlier one-sided
theorem, do not execute the transported score, and are not evidence for any
claim in this paper, so shipping them here would only invite them to be read as
if they were. Check 3 below verifies every evidence file that is here.

## What was redacted, and what that does and does not mean

Two files here are **modified copies**, not the original evidence bytes:
`full_aggregate.json` and `selection.json`. Each carried a top-level
`git_revision` string — a version-control revision identifier that resolves in
the authors' repository to a named person. Exactly that one string was replaced
with the placeholder `withheld-for-double-blind-review`. Nothing else changed:
no numerical value, no key, no ordering, no other byte.

`ANONYMIZATION.json` records, for each file, the field, the placeholder, the
SHA-256 of the packaged bytes you have, and the SHA-256 of the original evidence
you do not. The placeholder is a string, not a commit and not a substitute
provenance identifier.

**That file is a claim, not an authority, and the tooling treats it that way.**
`tools/anonymous_package_contract.py` pins the whole contract in code: the exact
two paths, the field name, the placeholder, the original and sanitized SHA-256
digests, the exact byte counts, the exact sidecar text, and the exact schema and
record set of the declaration. Every check measures this supplement against
those constants, and `ANONYMIZATION.json` is then validated against them too. So
editing a packaged file, recomputing its sidecar and updating the declaration to
match does not produce a passing supplement -- it produces three failures. Nor
does deleting the declaration: every shipped checker takes a `--require-package`
flag, `verify.sh` passes it and also exports
`CCE_REQUIRE_ANONYMOUS_PACKAGE=1`, and in that mode a missing declaration is a
failure rather than a fallback to repository semantics.

Two consequences worth stating plainly:

- The `.sha256` sidecars next to those two files were regenerated over the
  **packaged** bytes, so `sha256sum -c` still works on what you were given.
  The `.provenance.json` records next to them were **not** regenerated: they
  truthfully describe the original evidence, and their `artifact_sha256`
  therefore differs from the packaged digest. That is expected, and
  `ANONYMIZATION.json` gives you both numbers.
- Content verification is unaffected; original Git provenance is not verifiable
  from this supplement, by design. The two are different questions and the
  tooling keeps them apart: the ledger reports the transformed files with a
  distinct `PASS_ANON` status and the words "NOT original evidence bytes"
  rather than a plain pass.

The check that the redaction did not touch the numbers is step 2 below. The
published tables, figures and CSVs are regenerated **from the packaged
aggregate** and must come out byte-identical to the committed copies. They
could not, if the redaction had perturbed anything they depend on.

## Requirements

Python 3.12 with `numpy` and `scipy` (`experiments/requirements.txt` records the
versions the study declared: NumPy 2.2.3, SciPy 1.15.2). `pytest` is needed only
for the test suite. Nothing else is required, and nothing downloads anything.

## Verify

```bash
bash verify.sh
```

`verify.sh` runs in **required package mode**: it asserts that this really is
the declared anonymous package before it checks anything else, and it stops
there if that fails. Deleting `ANONYMIZATION.json` does not turn the supplement
into an ordinary directory to be graded leniently -- it is a failure, because a
supplement without its declaration is either incomplete or has been reverted to
the original, author-linked evidence.

It runs one gate and four checks, and prints the exit status of each:

0. **Anonymous-package contract, required (a gate, not a result).**
   `python3 tools/anonymous_package_contract.py --root . --require-package`
   Checks this supplement against the constants pinned in shipped code: the
   sanitized digests and byte counts, the redacted field's placeholder, the
   sidecar text, and the declaration's schema and record set. Nothing here reads
   an expectation out of `ANONYMIZATION.json`. If it fails, `verify.sh` exits
   nonzero immediately and the remaining checks are not run, because they would
   otherwise report on bytes this supplement does not vouch for.

1. **Numerical-provenance ledger.**
   `python3 tools/verify_tmlr_submission_numbers.py --require-package`
   Every number the paper states about this study is listed once with its
   source file and SHA-256, its selector, unit, aggregation rule, population,
   unrounded value and display rounding. The tool re-derives each value from the
   locked aggregate, checks it rounds to the printed literal, and checks the
   literal really occurs in the manuscript file it is attributed to.

   It also audits every *other* numeric literal in every compiled input listed
   in `SOURCE_CLOSURE.json`. Each one must be either a ledger entry or an
   explicit classification bound to that file and to an exact number of
   occurrences; `paper/macros.tex` and the symbolic rate table are checked
   structurally instead. Anything left over is a failure, so a number added to
   the manuscript without being declared cannot pass.

2. **Artifact regeneration.**
   `python3 tools/transport_artifact_expectations.py --root . --require-package`
   Regenerates all 21 published tables, figures and CSVs from the packaged
   aggregate and requires byte equality with the committed copies. It first
   checks `ANONYMIZATION.json` against the files it describes, and it stamps the
   artifacts with the declared original-evidence digest, which is the digest the
   published artifacts and their provenance records actually carry.

3. **SHA-256 sidecars for every shipped evidence file.**
   Walks `paper/tables/`, `paper/figures/` and `results/derived/` as they
   actually arrive in this archive and checks each file against its sidecar. A
   file that ships without a sidecar is a failure, so the coverage is of the
   archive rather than of a list written in advance. This is what covers the one
   typeset table that is not generated from the aggregate
   (`tables/growing_window_pareto.tex`, whose cells are asymptotic rates, not
   measurements). The files the pinned contract already verifies from constants
   in shipped code are counted separately and skipped here; that is where the
   two `.provenance.json` records are checked, byte for byte and for whether
   they still name the digest of the artifact they describe.

4. **Study tests.**
   `python3 -m pytest -q experiments/tests`
   The three transport-instantiation modules: the study's own algebra and
   seed-derivation tests, the aggregation tests, and the artifact tests.

## What this supplement does not let you check

Stated plainly rather than worked around:

- **Raw per-run trajectories are not included.** They were never part of the
  distributed material: the full grid is 2,400 trajectories and the raw tree is
  far larger than the supplement limit. The aggregate carries a complete
  SHA-256 inventory of every raw input it consumed, so the inventory's structure
  and digests are checkable, but the bytes those digests name are absent. The
  ledger reports that as NOT EXECUTED, not as a pass.
- **The deterministic paired bootstrap is therefore not recomputable here.** It
  resamples per-seed totals. Its algorithm, level, resample count and derived
  child seeds are all recorded in the aggregate; no per-seed values are
  synthesized to fake the recomputation.
- **Re-running the study from scratch is not a one-command operation.** The full
  grid is a multi-hour, multi-process job. `experiments/run_transport_instantiation_study.py`
  is included so the protocol can be read and executed, not because a reviewer is
  expected to run it.

## Reading the evidence directly

`results/derived/transport_instantiation/full_aggregate.json` is the single
source for every reported number (as the redacted copy described above; the
redacted field is metadata and is read by nothing that computes a number). Its top-level keys are `validity` (per-cell
coverage and audit failures), `certificate_tightness` (path-certificate ratios),
`bound_nonvacuity` (theorem right-hand side against realized regret),
`policy_outcomes` (per-method regret), `environment_diagnostics`,
`regret_curves`, `bound_decomposition` and `path_points`, plus the SHA-256 input
inventory under `inputs`.

The float64 checks recorded throughout are tolerance-based diagnostics computed
in ordinary floating point. They are not verified numerical enclosures, and the
paper does not describe them as certificates.
