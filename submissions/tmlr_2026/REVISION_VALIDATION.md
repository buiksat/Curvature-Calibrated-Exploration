# Review-revision validation

This record covers the research revisions through 2026-10-14
(America/Los_Angeles). `FINALIZATION_REPORT.md` remains the historical release
record. A collected test has not necessarily run or passed.

**Current targeted-readability status (2026-10-14):** the checked Fable advice
has been applied and the main manuscript builds to 47 pages. Preservation and
focused numerical, chart and detached-evidence checks pass. Both final source
archives reproduce their PDFs byte for byte, and the extracted supplement passes
its verification. The final regression reports **716 passed, three skipped,
zero failed and two warnings** in **384.00 seconds**. The preceding readability
run of 713 passed and three skipped remains a historical result.
Compact evidence verification remains separate from raw replay.

| Collection scope | Current collected cases |
| --- | --- |
| Release-package test collection | 555 collected |
| Repository suite collection | 719 collected |

The counts come from `python -m pytest -q --no-header -p no:cacheprovider
--collect-only -q tests experiments/tests`; the package count is the
`tests/test_tmlr_release_package.py` row. Two regression tests compare these
recorded counts with live collection. Refresh them after adding or removing
cases. They deliberately do not compare collection to the historical report's
`643 passed, 0 skipped` claim.

The initial repository run in this cloud session reported **589 passed,
47 skipped, 7 failed** before the parallel revision work was finalized. Its
failures included missing PyYAML, a new configuration inventory entry, and the
historical-test-count guard. This is a diagnostic baseline, not the final
revised test outcome. Final execution results must retain their actual skip
and failure counts; collection counts cannot substitute for them.

The next full repository regression run, after manuscript synchronization,
reported **606 passed, 46 skipped, 4 failed**. Three failures were stale
abstract/conclusion phrase expectations in the detached evidence verifier;
the fourth mutated a CG appendix that the revised manuscript no longer includes.
The repairs retain the negative-finding requirements and move the numeric
mutation to an active source. Four additional mutation cases check that the
revised abstract and conclusion still reject removal of their qualifications.
This run predates those repairs; targeted repair checks are recorded separately.

The detached-evidence review-bundle module passes after its phrase-contract
repair: **67 passed**, including the four new negative-finding mutation cases.
The repair changes the expected scientifically equivalent wording; it does not
remove the conservative-certificate, vacuous-bound, validity-versus-usefulness,
or no-uniform-regret-ordering requirements.

The inactive-CG test now mutates an active experiment explanation outside every
numeric context window and requires both semantic-unit and whole-file checks
to reject it. That repaired test and its clean baseline pass: **2 passed**.
Both collection-count guards also pass: **2 passed, 520 deselected**.

The final full repository rerun after those repairs completed with **614 passed,
46 skipped, 0 failed** in 173.24 seconds, using the locked Python environment
and single-threaded BLAS. Skips remain environment-dependent release-build and
optional capability checks; this result does not certify the blocked strict
release build described below. The separate launcher safety/cache module also
passes **7 tests**.

The actual local follow-up pilot completed all **24 development, 54 tuning,
and 24 held-out evaluation trajectories**. Its strict aggregate and independent
replay of all 24 terminal paired intervals pass. An identical invocation reuses
the completed trajectories, tuning selection, and aggregate successfully.
See `review/transport_review_followup/PILOT_VALIDATION.md` for the measured
outcomes and limitations; this pilot does not substitute for the full study.

The full-profile development gate also completed successfully from clean
research revision `dc2e2dc9e3f9f7ace8d5335fdf634cd31159c41a`: **24 trajectories
at horizon 1000**, on four CPU workers, with development-phase elapsed time
358.367673 seconds. Tuning and held-out evaluation were not run for this profile.
The separately retained development evidence is under
`review/transport_review_followup/full-development-check/`.

The subsequent complete local follow-up started from clean research revision
`707c8243ea6d5395369ed812a68cf7e27d700596` and completed **24 development,
270 tuning, and 600 evaluation trajectories**, with no failed trajectory records
and all deterministic audits passing. It resumed 16 verified development
trajectories after a user-requested pause. The strict raw-data aggregation passed;
the portable verifier independently replayed all 24 reported terminal intervals
from 600 exact evaluation summaries. Export commit
`65dd4e76efd376c830e2ea7e9dfe23eddd4bf01e` is confirmed on GitHub. These checks do
not imply favorable regret comparisons or manuscript readiness; see
`review/transport_review_followup/FULL_RESULTS.md`. The prior source-test and
ledger counts above have not been represented as new executions.

Focused package-contract validation passes: **10 passed, 511 deselected**.
These checks exercise the evidence anonymization contract and a mutated
declaration, original repository evidence handling, excluded/active artifact
inventory, and both current collection-count records. They are not a full
release-build result.

The revised numerical ledger reports **277 PASS, 3 NOT_EXECUTED, 0 FAIL**,
covering 91 source-derived entries. The three nonexecuted checks remain explicit
limitations; they are not counted as passes. Focused numeric mutation tests
report **32 passed, 1 skipped, 489 deselected**. The skipped test requires a
compiled release. The numeric context digest is pinned by the anonymous-package
contract, whose optional-repository provenance/tool checks pass **5 of 5**.

The synchronized TMLR entry point passes staged static validation and the
repository layout preflight. A diagnostic compile using the cloud's local TeX
packages succeeds; it supplies the exact project-local recorder closure used
to update `COMPILED_CLOSURE`: 80 inputs, including the new `legacy_scope.tex`,
with the nine legacy appendix sources and `tables/growing_window_pareto.tex`
removed. The entry-point/source digests and generated bibliography digest were
updated; venue and vendored-package digests were preserved. The independent
contract still binds exact paths, roles, digests, sizes, and archive membership.

**Strict release build remains blocked.** `package.compile_environment`
intentionally removes writable user TeX trees from the search path. Its compile
fails because this machine lacks the system-installed `algorithm.sty`; the
cloud onboarding installation supplies it only in a writable local tree.
The diagnostic compile does not satisfy the release packager's system-input
trust rule. That rule, its recorder checks, and its mutation tests remain
enforced. No revised strict release or anonymous supplement has been claimed
as verified. Install the required LaTeX packages in system-owned distribution
trees and run the full packager to validate external-input trust and release
checks before publishing a new supplement.

The historical AISTATS PDF and its checksum, frozen experiment sources and
configuration, original aggregate and selection bytes, provenance pins, and
the evidence anonymization transform were not changed by this synchronization.

## Full-manuscript revision: build preflight

The preceding results concern the earlier synchronized manuscript. They do not
validate the subsequent full-manuscript revision or its additional empirical
inputs. Final-source compilation and the new evidence scope must be checked
separately before reporting a new release.

The working main-branch build uses the rootless cloud TeX installation:

```bash
cd /workspace/Curvature-Calibrated-Exploration
source /workspace/cce-env/activate.sh
TMLR_OUT=/workspace/cce-build/tmlr-full-revision \
  bash submissions/tmlr_2026/build.sh
```

This command produces a manuscript PDF and a recorder-derived LaTeX source
archive. It does not produce or certify a research supplement. Reproduction
requires extracting `source.zip` into a fresh directory outside both checkouts,
running `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex` there
under the same TeX activation, comparing PDF hashes, and checking that the
extracted build's recorder references no files in either original checkout.
The final-source result of those steps is pending.

The system-dependency blocker has been independently rechecked. In the strict
packager's scrubbed compile environment, `kpsewhich algorithm.sty` and
`kpsewhich algorithmic.sty` both exit 1. The engine's existing protected system
trees are recognized correctly. The local copies under `/workspace/cce-env`
fail the packager's component-by-component write-protection check because the
invoking user can modify their containing directories. The packager's rejection
is therefore expected and its trust rule has not been changed.

The retained Debian science package has SHA-256
`452596eb7ab5ee08ff1664a8586e243e561ff675abb88d2f764b38113c688adc`,
matching the authenticated onboarding package record. An APT simulation using
the signed Debian metadata resolved `texlive-science=2024.20250309-2` and its
three required dependencies without removals. The actual installation attempt,
including execution outside the filesystem sandbox, was:

```bash
APT_CONFIG=/workspace/cce-env/apt/apt.conf /usr/bin/apt-get \
  --yes --no-install-recommends install texlive-science=2024.20250309-2
```

It exited 100 before installation: `/var/lib/dpkg/lock-frontend` could not be
opened (`Permission denied`; root required). The session runs as UID 1000,
has no effective capabilities, and has no `sudo` command. This was an operating
system privilege failure, not an automatic approval rejection. No system
package was installed and no verification check was bypassed. A privileged
environment administrator must install the dependency into a protected TeX
distribution tree before the strict release build can progress past this step.

After that prerequisite is supplied, the strict command is:

```bash
cd /workspace/cce-research
PYTHON=/workspace/cce-research-env/bin/python \
  TMLR_OUT=/workspace/cce-build/tmlr-full-strict-release \
  bash submissions/tmlr_2026/build.sh
```

The research packager must separately account for every newly cited follow-up
dataset and numerical source. Its existing historical aggregate supplement
cannot establish completeness for the expanded manuscript. A successful main
PDF/source build will not be reported as a successful strict package or a
complete anonymous evidence supplement.

## Full-manuscript revision: final numerical and build checks

The previous validation records above describe earlier manuscript snapshots.
For the expanded manuscript, the numerical ledger now derives **216 prose
entries**, binds the original study and the separate follow-up/relative-audit
inputs to fixed SHA-256 digests, independently reconstructs the follow-up's
terminal bootstrap intervals, and regenerates the five new tables plus their
provenance record byte for byte. The original study's numerical checks remain.
The source-only input sets are kept distinct; no original per-seed values were
invented to fill its historical gap.

Executed from the research checkout:

```sh
/workspace/cce-research-env/bin/python tools/verify_tmlr_submission_numbers.py \
  --ledger /workspace/cce-build/tmlr-full-revision-number-ledger.json
```

Result: **565 PASS, 4 NOT_EXECUTED, zero FAIL**. The four unexecuted checks
are: external raw/upstream recomputation for the follow-up and exploratory
analyses; certification of a packaged compiled source closure (this is a
repository input-walk preflight); the original study's paired bootstrap from
missing per-seed values; and verification of the original raw trajectory bytes.
The follow-up's terminal bootstrap reconstruction does execute and pass.

The reviewed context module is
`9b14bb6b1397039572c37924828b49f17efed8693a76c8a38be7a4c08644e9b1`.
Only its existing shipped-tool digest pin was refreshed in the anonymous
contract. That is **not** an expanded anonymous evidence contract: missing new
inputs fail the complete-paper audit, and a newly sanitized follow-up copy
also fails until a separate export/provenance contract is reviewed. No complete
strict supplement is certified by this result.

Collection checks find **669 repository tests** and **531 package-module
tests**. Five new mutation cases cover a changed follow-up value, changed ratio
meaning, either missing new evidence source, and coordinated changes to an
input plus its regenerated tables/provenance. Their clean fixtures carry the
required fixed evidence. Full-suite execution is tracked separately; collection
counts do not claim those tests have all passed.

The final main-checkout build produced a **38-page** Letter PDF, with no
undefined reference/citation, no overfull box, and four underfull boxes
(three horizontal and one vertical) in its final log:

- `main.pdf`: `8cc566123e1fe13bdb23b5f7929f1d3bb22df9d8f847007b350b61840ddac5d7`
- `source.zip`: `4872f6e2da31318ec7263573ec6737f49aa0d8ff6c9bb25ac453f840b8cc47a5`

Both are in `/workspace/cce-build/tmlr-full-revision`. An independent clean
extraction of the 45-member source ZIP rebuilt a byte-identical 38-page,
642,844-byte PDF. The recorder showed zero original-checkout dependencies; all
four official style hashes passed, and BibTeX resolved 29 bibliography entries.
References begin on physical page 18. The
clean build had zero warnings, overfull boxes, or unresolved references, and
four underfull boxes (three horizontal, one vertical). The independent report
is `/workspace/cce-build/tmlr-full-revision-clean-verification.md`. These checks
identify the reproducible PDF/source snapshot, not an anonymous supplement.

Before the explicit follow-up inventory gate was added, the research strict
build was attempted with the command in the preceding preflight section. It staged 100 paths and passed static layout/entry checks,
then stopped in the protected TeX environment with
`LaTeX Error: File algorithm.sty not found` (`latexmk` exit 12). The complete log
is `/workspace/cce-build/tmlr-full-strict-release.log`. It produced no strict
release PDF or supplement. The workspace-local TeX package works for the main
source build but cannot satisfy this protected-system-input trust policy, and
the attempted system package installation failed for lack of dpkg privileges.
The separate expanded-supplement inventory gap also remains unresolved.

The first full-suite run against this expanded snapshot completed with **581
passed, 45 skipped, 26 failed, and 13 errors** in 59.29 seconds (log:
`/workspace/cce-build/tmlr-full-revision-tests.log`). It exposed stale source,
artifact-inventory, closure, and manuscript-qualifier fixtures; it is not a
passing release result. The numeric/static fixtures have since been corrected
without changing scientific text. A focused selection then reported **27
passed, 1 failed, 499 deselected**; the remaining selected failure was the
package inventory case `test_an_unclassified_artifact_stops_the_build`, being
handled with the package classification updates. All five new numerical
mutation cases passed. The separately revised optional-citation parser test
also passed. Final full-suite results must be recorded after the remaining
package/verifier changes, rather than inferred from these focused results.

After the artifact classification and context updates, the focused numerical,
context, and collection checks passed: **29 passed, 502 deselected**. The
follow-up artifact/provenance/preflight selection passed: **6 passed, 525
deselected**. Its four new tests check the exact five-table-plus-provenance
classification, source/output digest bindings, an explicit incomplete-evidence
finding, and the real CLI's refusal before staging while preserving prior
deliverables. Together with the five numerical mutations, these additions
bring current collection to 531 package tests and 669 repository tests.

The current strict research CLI now fails earlier and more clearly: exit
**14**, `FOLLOW-UP ANONYMOUS SUPPLEMENT IS INCOMPLETE`. It identifies 13 missing
fixed evidence/tool inputs and six follow-up artifacts without reviewed
anonymous provenance/sidecar support, before staging or running TeX. This was
executed with output `/workspace/cce-build/tmlr-full-strict-preflight`; the log
is `/workspace/cce-build/tmlr-full-strict-preflight.log`. The earlier actual
TeX failure and system-install permission failure remain recorded above as
additional environment limitations, not the current first failing gate.

The next full-suite run reported **623 passed, 45 skipped, 1 failed** in 202.02
seconds (`/workspace/cce-build/tmlr-full-revision-tests-final.log`). Its only
failure was an overbroad test asserting that the token `PINS` could occur
nowhere in the package module; the new supplement-evidence provenance gate
legitimately uses `contract.PROVENANCE_PINS`. The test now checks the actual
external-TeX admission functions' parsed identifiers and still forbids the
removed external-input pin module. It also always injects a user-writable TeX
file and proves rejection, instead of skipping when the host's TEXMFHOME is
empty. No production trust gate was changed. Focused external-input checks
then passed: **5 passed, 1 skipped, 525 deselected**. The final full-suite rerun
is recorded below when complete.

Final full-suite rerun: **624 passed, 45 skipped, zero failed, zero errors**, in
**151.62 seconds (2:31)**, exit status 0. The command used the pinned Python
environment, single-thread BLAS variables, and both `tests` and
`experiments/tests`; the complete log is
`/workspace/cce-build/tmlr-full-revision-tests-clean.log`. All 669 collected
cases are accounted for. This passing test result, the 565-pass numerical
ledger, and the byte-identical standalone PDF/source rebuild do not override
the strict supplement's explicit incomplete-evidence preflight (exit 14).

## Anonymous compact supplement completion (2026-10-14)

The compact supplement now includes the complete follow-up export and the
independent and relative fixed-history evidence. Its separate typed contract
pins 20 evidence files and six generated artifacts. The transformation changes
only enumerated metadata fields and their dependent digests; it checks that
all scientific JSON values and types remain unchanged. The original raw-input
hashes and historical run signatures explicitly describe unshipped original
bytes. They are not relabeled as signatures of an anonymous raw archive.

Both anonymous declarations are required. The parent contract, numerical ledger,
table generator and standalone pinned-path listing authenticate the helper's
exact bytes before importing it. The new helper is independently pinned at
`8c0410993e78112101b07b66b01df469f7d822b7de201ea6c55178933b0b21b9`.
The generator's final digest is
`153da33c998c3074e6fdabb9dc241157da5ff2bf0e9f401350699fa87a540496`.
Its source-attribution comments changed; the generated numerical table bodies
did not. Missing evidence, changed scientific values, coordinated evidence and
declaration edits, and replacement helper code are rejected.

The first integrated strict candidate build completed successfully with
`PYTHON=/workspace/cce-research-env/bin/python` and
`TMLR_OUT=/workspace/cce-build/tmlr-anonymous-followup-candidate` running
`bash submissions/tmlr_2026/build.sh`. It used 89 project-local recorded inputs
and 240 protected distribution inputs, with no acceptance of mutable external
TeX trees. Exact-byte vendoring supplies the algorithms styles and their source
and license; runtime-derived `TEXMFDEBIAN` uses the existing canonicality,
ownership and write-protection checks. The candidate supplement was 93,691,848
bytes, below the enforced 100,000,000-byte ceiling. Its identity scan was clean.
This candidate is an intermediate artifact, superseded by the final rebuild
that includes the corrected availability text and final checker pins.

The first extracted candidate verification exposed one stale ledger requirement:
it demanded the excluded symbolic growing-window table. Every other advertised
check passed, including all 24 terminal interval reconstructions, all six
follow-up artifact checks, evidence coverage, and 23 shipped study tests. The
ledger correctly reported one failure rather than declaring the archive valid.
The repair restricts the specialized symbolic-table check to active source
references and preserves failure for a missing referenced table. It does not
add excluded legacy material to the supplement.

Focused validation records are: 14 typed-transform tests passed; 26 initial
package/contract cases passed; and 66 final numerical/context/module-authentication
cases passed with 6 environment-dependent skips. The broader package-focused
run reported 67 passed, 11 skipped and one closure failure because it imported
the ledger before the concurrent vendor-name update; both affected clean-closure
checks pass in a fresh process. The standalone helper-listing tests pass all
three pinned/missing/replaced cases without executing replacement code. Current
repository ledger result before final archive verification: 556 PASS,
4 NOT_EXECUTED, zero FAIL. Nonexecuted checks remain limitations, not passes.

The full follow-up raw run is locally intact but is not shipped in the compact
supplement. Exact phase sizes and the verified receipt, inventory and source
checks are recorded in `review/post_fable_revision/RAW_ARCHIVE_STATUS.md`.
No sanitized raw archive or durable anonymous download endpoint has been
claimed. The earlier near-linear study's raw and per-seed bootstrap inputs
remain absent. Those gaps do not prevent the compact follow-up's terminal
interval and generated-table reconstruction.

The final strict release at `/workspace/cce-build/tmlr-fable-final-release`
completed with exit status zero. A fresh extraction into
`/workspace/cce-build/tmlr-fable-final-reviewer-check` ran `bash verify.sh`
with the locked interpreter and no checkout imports. It passed in **15.73
seconds**: the anonymous contract passed **23/23** checks; the numerical ledger
reported **565 PASS, 36 PASS_ANON, 3 NOT_EXECUTED, zero FAIL**; all **24** follow-up
terminal intervals reconstructed; all **six** follow-up artifacts matched;
**42** evidence files passed sidecar checks and **29** further evidence files
were covered by code pins; all **23** shipped study tests passed. Every
advertised check returned zero. The three nonexecuted checks retain the raw
follow-up replay, historical bootstrap-input and historical raw-byte limitations.
The complete log is `/workspace/cce-build/tmlr-fable-final-reviewer-verify.log`.

Final strict artifacts:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `main.pdf` | 644,571 | `158c98e99f2665d0c804a7f13a8c8d76fe0c6ae1d18f3c45bfae21caf3e64822` |
| `source.zip` | 3,364,042 | `da0e004d58b3198da3e3526c4c9a36921f665d60e0e4dac93d25d889ad0e5fa3` |
| `supplement.zip` | 93,693,136 | `8be0424f9fdc98387dde264d8e2dc8fe7bb3ea3eb3438c9fdf86aa3180fff81a` |

The source archive has **97** members and **3,351,306** unpacked bytes. The
supplement has **169** members and **93,661,942** unpacked bytes. Its stored size
leaves **6,306,864** bytes below the venue ceiling. The internal release manifest
is **110,726** bytes and is not part of either anonymous upload archive. The
reviewer verification wrote only to its extracted scratch directory; original
experiment sources, configurations, aggregate evidence and raw logs were not
modified. The independent clean source rebuild and final repository test run
are recorded below when complete.

An independent clean extraction of the final source ZIP rebuilt the **38-page**
PDF in **32.647914308 seconds**, byte-identical to the final release digest
above. The recorder found **89** local inputs and **240** protected system
inputs. Every external input record matched the release manifest, and no input
came from either original checkout. All included vendor digests and the official
TMLR style, bibliography style, header package and license digests matched their
pinned provenance. There were no unresolved references/citations or overfull
boxes; the final strict toolchain reported **eight underfull boxes and one
LaTeX hook deprecation warning**. These diagnostics are reported rather than
represented as a warning-free build. The machine-readable record is
`/workspace/cce-build/tmlr-fable-final-clean-source/clean-build-verification.json`.

The first complete repository run against those final archives reported
**665 passed, 3 skipped, 29 failed, 2 warnings** in **338.22 seconds**. Its log is
`/workspace/cce-build/tmlr-fable-final-tests.log`. The failures exposed outdated
test fixtures and incomplete internal README details: the verifier subprocess
used an unrelated Python without pytest; coverage assumed only sidecars and
the older evidence inventory; the synthetic recorder incorrectly included the
new upstream `.dtx`/`.ins` redistribution sources; two mutation checks selected
an archive-only file by list position; and a layout mutation targeted an inactive
table. The corrected fixtures use the test interpreter, complete evidence
inventory and actual active inputs while retaining positive controls and
tamper rejection. No production verification rule or release bytes changed.

The internal README now identifies the actual bundled/external packages,
`ZIP_STORED` format and external-input manifest field. Debian ownership checks
identify `texlive-latex-base` as this build's provider of `rotating.sty`; the
stale provider assertion was corrected accordingly. Focused fixture and
mutation checks pass **47 cases**; the four README checks also pass. Each
focused invocation reported 9,993 dependency deprecation warnings from the
locked pytest version on Python 3.12, not additional test failures. The full
rerun result is recorded below when complete.

The final full rerun completed with **694 passed, 3 skipped, zero failed,
9,995 warnings** in **331.78 seconds**, exit status zero:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
TMLR_OUT=/workspace/cce-build/tmlr-fable-final-release \
  /workspace/cce-research-env/bin/python -m pytest -q -ra tests experiments/tests
```

All **697** collected cases are accounted for. The complete log is
`/workspace/cce-build/tmlr-fable-final-tests-clean.log`. Two skips concern host
TeX properties absent here (a user `TEXMFVAR` and a symlinked `TEXMFSYSVAR`).
The third is a historical bibliography test looking in an old hard-coded
workstation directory; the independent clean rebuild above verifies the
current archive separately. The warning count comprises 9,993 locked-pytest
AST deprecations on Python 3.12 and two intentional duplicate-ZIP-member
warnings from rejection tests. No warning was represented as a passed check.

An independent review of the final fixture changes found no weakened evidence,
tamper, layout or compiled-closure protection. Scientific manuscript sources,
the bibliography and abstract match the main-branch mirror. Final artifact
hashes remain exactly those recorded above; the frozen experiment and historical
PDF digests are unchanged. No new experimental run or TMLR submission occurred.

## Explanatory visual revision (2026-10-14)

The requested precise technical communication skill guided four new native
LaTeX figures. They explain the conditional certificate interfaces, an abstract
confidence-geometry example, all policy outcomes and paired intervals, and
the mean bound scale relative to the deterministic regret cap. The detailed
outcomes table moves to the appendix; the theorem statements, proofs, original
experiment sources, locked configurations and retained evidence are unchanged.
No new experiment or model review was run. Figure-level claims and sources are
recorded in `review/visual_revision/IMPLEMENTATION_REPORT.md`.

Independent numerical review matched all 12 policy means, nine paired means,
18 interval endpoints and six transformed bound values to retained evidence.
The charts retain pointwise paired uncertainty, all evaluated conditions and
the own-history interpretation. The geometric diagram is an abstract example,
not an observed study failure. The first outcome render exposed incorrectly
positioned interval caps; explicit data coordinates repaired the rendering
without changing the numerical endpoints. All four standalone figures and all
four integrated pages were visually inspected.

### Build and source reproduction

Both the main mirror and strict research release now have **40 pages**. The
new figures appear on pages **2, 7, 15 and 16**; references begin on page **20**.
They use native body-size text without shrinking or page-limit compression.
Both builds have empty identifying PDF metadata and no unresolved references,
citations, missing characters or overfull boxes. Each retains four underfull
horizontal-box and five underfull vertical-box diagnostics. The main build has
no LaTeX warnings; the strict build retains one existing generic package-hook
deprecation warning.

The main build is `/workspace/cce-build/tmlr-visual-main`. Its 660,363-byte PDF
has SHA-256 `0e910f8fc70aa07238a10937b2028a4b1e426a6d81054430fef470fa68d5eedb`.
The 181,445-byte source ZIP has 49 members, 646,190 unpacked bytes and SHA-256
`cf1e8731e1d4e9763134974d1c55384d4efa9b9089dfa424c9fe3f9612d435c4`.
An independent clean extraction rebuilt the PDF byte for byte. The actual
recorder has 338 unique canonical inputs: 44 archived project inputs, three
regenerated inputs and 291 environment inputs. No original-checkout or
prior-build input was used. All four official style/licence pins pass.
The report's broad `inputs_sha256` inventory also includes inactive source
files and must not be described as the actual compiler closure.

The strict release is `/workspace/cce-build/tmlr-visual-release`. Its matched
PDF/source/supplement hashes and sizes are in `README.md` and the tracked
internal `release_manifest.json`. An independent clean extraction of its
101-member source ZIP rebuilt the 660,312-byte PDF exactly. The recorder has
93 project inputs, of which 92 are archived and `main.bbl` is regenerated;
all 240 protected external input records match the release manifest. No
original-checkout, release-staging or writable user-environment input was used.
All four official and 54 vendored file pins pass. The strict clean-rebuild
report is `/workspace/cce-build/tmlr-visual-strict-clean/verification.json`.
The final tool-only supplement repair leaves the PDF and source ZIP byte
identical to this independently rebuilt candidate; the final external records
are also exactly equal. The report records that final release binding.

The final supplement is 93,770,633 bytes with 178 members and 93,737,907 unpacked
bytes. It remains below the 100,000,000-byte limit by 6,229,367 bytes. Both ZIPs
use deterministic uncompressed entries. The build passes layout, identity,
archive-member, byte-size and exact-digest gates. The internal manifest is not
anonymous submission material.

### Integration failures and repairs

An initial focused package/numeric run reported 69 passed, six skipped and one
failed: its miniature ledger fixture omitted the newly required generator.
The fixture now supplies that generator and checks gate order. The rerun
reported **71 passed, six skipped, 470 deselected**. The figure/follow-up
contract checks report **26 passed**.

The first strict candidate compiled successfully, but verification from its
extracted supplement found a real closure gap: the three new CSV data exports
are shipped for inspection, while PGFPlots reads their generated TeX coordinates
instead of the CSVs. The generic closure check therefore found neither recorder
entries nor standalone sidecars for those files. Its other checks passed.
The repair admits only those three exact paths after complete anonymous-package
validation, authenticated generator/helper loading, exact six-output inventory,
fixed byte-size/digest checks and exact regeneration. It does not exempt other
CSV files or rely on a mutable provenance record. Independent review found no
weakening of the integrity gates.

The added mutation tests initially reported five failures and two passes
because their fixture omitted the six historical figure sidecars before even
reaching the new CSV checks. Supplying the actual sidecars repaired the fixture;
no production gate was relaxed. The final targeted run reports **seven passed,
545 deselected**. It covers changed CSV/provenance, unknown CSVs and missing or
replaced generators, as well as a valid packaged baseline. Collection is now
552 package cases and 716 repository cases.

The first failed extracted verification and the subsequent successful one are
retained separately. Fresh extraction of the final supplement passes its
advertised `verify.sh`, using the supported locked Python explicitly and no
repository `PYTHONPATH`: **24/24 required contract checks**, a ledger of
**588 PASS, 37 PASS_ANON, three NOT_EXECUTED, zero FAIL**, reconstruction of all
24 terminal intervals from 600 summaries, exact regeneration of both sets of
six artifacts, coverage of 42 sidecarred and 37 code-pinned files, and
**23 shipped study tests passed**. Exit status was zero in 10.183 seconds.
The log is `/workspace/cce-build/tmlr-visual-reviewer-verify-final.log`.
The remaining nonexecuted checks concern raw/upstream replay and historical
missing raw/per-seed bootstrap inputs; they remain limitations, not passes.

### Final repository regression

The final complete run, after the source, generator and verification code were
frozen, used:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  TMLR_OUT=/workspace/cce-build/tmlr-visual-release \
  /workspace/cce-research-env/bin/python -m pytest -q -ra tests experiments/tests
```

Result: **713 passed, three skipped, zero failed, two warnings**, in
**336.30 seconds**. The log is
`/workspace/cce-build/tmlr-visual-final-tests.log`. The three skips are the host
reporting no user `TEXMFVAR`, its `TEXMFSYSVAR` not being a symlink, and a legacy
clean-bibliography test looking for a rebuild at an old workstation path.
The actual current clean source rebuild and bibliography were checked separately
as recorded above. Both warnings come from deliberate duplicate-ZIP-member
mutation tests; those tests passed.

A final independent scope audit confirmed all 172 protected experiment,
configuration, evidence and historical-PDF files unchanged, all 46 active shared
scientific/figure files synchronized with main, and final release sizes,
hashes and contents equal to the records. The source PDF builds precede only
internal documentation updates; those files are outside the compiler closure.

## Readability rewrite (2026-10-14)

The author's request and Fable's preceding advice prompted a substantial prose
rewrite. The abstract and introduction start with the decision problem and a
concrete illustrative example. The theory explains the exact-matrix case before
the general protocol and adds interpretation around its formal results. The
empirical section answers questions about policies, regret, useful bounds and
recorded checks. Related work is organized by uncertainty construction. The
precise technical communication skill guided the rewrite; the original
conditions, uncertainty statements and evidence limitations remain.

### Preservation and focused checks

An independent comparison against research commit
`650c072548f950c5b13bf58146c983a8ef88eadd` confirms that all 240 protected evidence,
configuration, experiment, generator, figure, table and historical-PDF files
retain their original bytes. All 21 formal theory statements, 59 existing
theory displays, 18 proof blocks and 44 proof displays are retained. The sole
added display introduces an exact-matrix/exact-width specialization of the
existing score. Empirical numeric and mathematical-expression inventories,
labels, citations and input paths remain unchanged. The final comparison-table
caption clarifies the separate metric-transport factor; its wording is therefore
deliberately not claimed byte-identical. The independent preservation report
and scientific-source hashes are tracked in `review/readability_revision/`.

All 212 numerical-ledger entries retain their scientific literals, source
selectors, units, aggregations and populations. Its 175 phrase/count contracts
and 123 classified literal keys are unchanged. Reviewed source-context pins
were refreshed for the rewritten prose. The introductory theory explanation
adds one occurrence of mathematical constant one and four of two. No evidence
hash, numerical computation, closure admission or unledgered-number guard was
weakened. The repository ledger reports **579 PASS, four NOT_EXECUTED, zero
FAIL**; focused numerical mutation tests report **47 passed, 505 deselected**
in 16.70 seconds.

The detached verifier's wording guards were translated to the rewritten prose
while preserving the scientific requirements. Its first test run reported
**66 passed and one failed**: the rewritten abstract's line wrapping split an
existing mutation anchor. Updating the anchor to the same explicit vacuity
predicate repaired that test; the complete reference-policy context remains
required. The final module reports **67 passed** in 34.18 seconds. No test cases
were added or removed. The complete detached evidence verifier reports
**123 direct PASS, 39 recomputed PASS, two STRUCTURAL_PASS, two KNOWN_DIVERGENCE,
four NOT_EXECUTED and zero FAIL**, plus one semantically identical but
byte-different rebuild classification. Focused logs are under
`/workspace/cce-build/readability-*`; the ledger and detached reports are under
`/workspace/cce-reviews/`.

### Rendered paper and clean builds

Both final builds have **46 pages** in the unmodified official TMLR style at
10pt. The figures appear on pages **3, 9, 19 and 20**, and references start on
page **25**. The additional space is used for explanations. The abstract,
introduction, interface diagram and exact-case guide on pages 1–4 were checked
in rendered form. An independent reader also checked the main prose for
comprehension and scientific scope. Its final clarifications corrected an
experiment pointer, made the operator-comparison caption self-contained and
removed a vague reference to a previous result before the source freeze.
Final independent visual inspection covered pages **1–4, 7–9 and 17–20**.
The theorem interpretation, operator-only table qualification and all four
figures are legible, with no clipping or overlap.

The main mirror build is `/workspace/cce-build/tmlr-readable-main`. Its PDF is
685,705 bytes with SHA-256
`a4f982c9569cf7f453b5346715f407149e1308b6f27830100abc6b38931cac2c`.
Its 188,508-byte source ZIP has 49 members and 667,276 unpacked bytes, with SHA-256
`aa649bde2c604a27230d73e117e4f99973a928ee3ea68b93548dc6097681b959`.
An independent extraction rebuilt the PDF byte for byte. The recorder contains
44 archived project inputs, three regenerated inputs and 291 environment inputs;
there are no original-checkout or prior-build dependencies. All four official
style/licence pins pass. The report is
`/workspace/cce-build/tmlr-readable-main-clean/verification.json`.

The strict research release is `/workspace/cce-build/tmlr-readable-release`.
Its matched PDF, source and supplement sizes and hashes are in `README.md`
and the internal tracked `release_manifest.json`. An independent fresh
extraction of the 101-member source ZIP rebuilt the 685,695-byte PDF exactly.
All 93 project records match the compiled closure: 92 archived inputs and
regenerated `main.bbl`. All 240 protected external records match the release
manifest. All four official and 54 vendored file pins pass, with no original
checkout, release-staging, prior-build or user-environment inputs. The report is
`/workspace/cce-build/tmlr-readable-strict-clean/verification.json`.

Both PDFs have empty identifying metadata and no unresolved references or
citations, missing characters or overfull boxes. Both logs retain four underfull
horizontal-box and three underfull vertical-box notices. The main build has no
compiler warnings; the strict build retains its existing generic package-hook
deprecation warning. The final supplement is 93,803,092 bytes with 178 members
and 93,770,366 unpacked bytes, below the decimal 100 MB limit by 6,196,908 bytes.
Layout, identity, archive-member, size and exact-digest gates pass.

### Fresh extracted supplement

The final supplement's advertised `verify.sh` passed from a fresh extraction in
**14.63 seconds** using locked Python 3.12.14, NumPy 2.2.3 and SciPy 1.15.2 with
the inherited repository import path removed. All eight steps exited zero:
**24/24 required contract checks**, **588 PASS, 37 PASS_ANON, three NOT_EXECUTED,
zero FAIL** in the authoritative ledger, exact regeneration of all 21 original
artifacts and both sets of six follow-up/chart artifacts, 24 terminal intervals
recomputed from 600 summaries, coverage of 42 sidecarred and 37 code-pinned
evidence files, and **23 shipped tests passed**. The locked pytest emits its
existing Python AST deprecation warnings on this interpreter. The log is
`/workspace/cce-build/tmlr-readable-reviewer-verify.log`.

The nonexecuted checks still concern raw/upstream replay and historical missing
raw/per-seed inputs. Compact terminal-interval checks do not certify roundwise
raw replay. No new experiment, Fable API review or TMLR submission occurred.

### Final repository regression

The final complete run on the frozen scientific sources and verification code
used:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  TMLR_OUT=/workspace/cce-build/tmlr-readable-release \
  /workspace/cce-research-env/bin/python -m pytest -q -ra tests experiments/tests
```

Result: **713 passed, three skipped, zero failed, two warnings**, in
**368.95 seconds**. The log is
`/workspace/cce-build/tmlr-readable-final-tests.log`. The skips concern the host
reporting no user `TEXMFVAR`, its `TEXMFSYSVAR` not being a symlink, and a legacy
clean-bibliography test looking for a rebuild at an old workstation path.
The actual final clean source rebuilds and bibliography were verified separately
as recorded above. Both warnings arise from deliberate duplicate-ZIP-member
mutation tests; those tests passed. Only internal documentation was edited
after this run; the frozen scientific sources, verification code and final
release artifacts remain unchanged.

A final independent scope audit compared all 240 protected files, totaling
103,540,985 bytes, against the baseline commit and found no changes. All 46
active shared scientific files match the main branch; all three abstracts and
the frozen scientific-source hashes agree. Actual PDF/ZIP bytes match the
documentation, tracked manifest and clean-rebuild reports. The audit is
`/workspace/cce-build/readability-independent-scope.json`.

## Checked Fable readability follow-up (2026-10-14)

This revision applies the checked recommendations from the fresh Fable
readability review. The abstract separates the confidence-center construction
from its conditions. A native-size notation table and chronological protocol
guide precede the general assumptions; finite-action readers are told which
selection details they may skim and which obligations remain. The empirical
section gives the mean bound magnitudes with their own-history populations,
clarifies the policy names and feature categories, and distinguishes an
asymptotic scaling family from the fixed-horizon study. The chart label now
reads “Hessian = 0.” The implementation record is
`review/readability_followup/IMPLEMENTATION_REPORT.md`.

### Preservation and numerical meaning

The immutable baseline is research `a9315960dbbf6e7c81d519872805041f9d8114dc`
and main `890943f9a031ab9d719827ea9446707e609fc450`. All 21 existing formal theory
blocks, all 60 theory displays, all 18 proof blocks and all 44 proof displays
remain unchanged. Every data CSV and plotted data coordinate is preserved.
Experiments, configurations, original evidence and historical PDFs are unchanged.
The notation table adds one label. All 46 active shared scientific sources and
all three abstracts agree across the research entry points and main mirror.

All 212 prior numerical-ledger entries retain their scientific literals,
selectors, units, aggregations and populations. Six entries are added for the
mean-bound explanation, independently recomputed from pinned per-seed summaries:
Hessian uses the terminal sharp RHS, while frozen reference uses the sum of
statistical, historical and current-bias components. Each cell selects 50
distinct own-policy histories at the recorded horizon. The arithmetic mean is
divided by the common within-cell cap; only then do the Hessian entries take a
base-ten logarithm. The resulting displayed values round to 9.51, 37.19 and
80.91 for Hessian log ratios, and 19, 60 and 231 for frozen mean ratios.
The calculations agree with the original summary-derived chart quantities up
to ordinary summation roundoff. They do not attach those means to each trajectory
or decompose the difference between policies.

Three existing parameterized mutation cases were added to reject a changed
Hessian magnitude, changed frozen magnitude and substituted history population.
The existing chart-statistics test adds an independent per-seed-to-chart
comparison. No previous case, assertion or threshold was removed or weakened.
Live collection reports **555 package cases and 719 repository cases**.

### Candidate checks and rendered-label repair

The first revised source passes **50 numerical tests, 505 deselected**, in
34.51 seconds, and **79 chart/detached tests** in 52.39 seconds. The repository
ledger reports **591 PASS, four NOT_EXECUTED, zero FAIL**, with 218 entries.
The main build and a separate strict candidate build both succeed at 47 pages.
The candidate main source archive rebuilds its PDF byte for byte.

Rendered inspection then exposed a small overlap: the chart's dashed zero guide
crossed the zero glyph in the new label. One independent initial page review
missed it; the clean-rebuild visual review and root inspection identified it.
The generator now moves that annotation's relative horizontal anchor from one
to 0.90. Its three generated node commands and the associated provenance/contract
pins change; data coordinates, axis bounds, intervals and CSVs do not. Candidate
builds and reports are preserved under `tmlr-clarity-*`; the final artifacts use
the distinct `tmlr-clarity-final-*` directories.

After that placement repair, **12 chart/regeneration/mutation tests pass** in
4.17 seconds, **13/13 repository contract checks pass**, and the ledger again
reports **591 PASS, four NOT_EXECUTED, zero FAIL**. These affected checks use the
final placement bytes; the earlier 50/79 results remain bound to the candidate.
The final archive checks and complete regression are recorded below. No
experiment or new Fable API review was run for this implementation.

### Final artifacts and verification

The final main build has **47 pages**, with the notation table on page 5,
figures on pages 3, 10, 20 and 21, and references beginning on page 26. The final
labels clear the zero guides without overlapping data. The remaining figure
pages render identically to the inspected candidate. Independent extraction of
`/workspace/cce-build/tmlr-clarity-final-main/source.zip` reproduces its PDF byte
for byte. All four official style/licence pins pass; the recorder accounts for
44 archived project inputs, three regenerated inputs and 291 environment inputs.
There are no original-checkout or prior-build dependencies, identifying metadata,
unresolved references/citations, missing characters, overfull boxes or compiler
warnings. Four underfull horizontal and two underfull vertical boxes remain.
The report is
`/workspace/cce-build/tmlr-clarity-final-main-clean/verification.json`.

The final strict release at `/workspace/cce-build/tmlr-clarity-final-release`
passes its layout, identity, archive-member, size and digest checks. Its PDF
also has **47 pages**. The exact artifact sizes and SHA-256 digests are recorded
in `README.md` and the tracked `release_manifest.json`. The 93,812,058-byte
supplement leaves 6,187,942 bytes below the decimal 100 MB limit. An independent
clean extraction of the strict source archive also reproduces its matched PDF
byte for byte. All four official and 54 vendor pins pass. Its actual recorder
contains 93 project inputs, 240 protected external inputs and two generated
auxiliary inputs; the project closure and external records match the release
manifest exactly. No original checkout, release directory, prior build or user
environment supplies an input. Identifying metadata is empty; no unresolved
references, missing characters or overfull boxes remain. There are four
underfull horizontal and two underfull vertical boxes, plus the known deprecated
`package/after/fontspec` hook warning. The report is
`/workspace/cce-build/tmlr-clarity-final-strict-clean/verification.json`.

A fresh extraction of the final supplement passes its verification in
**20.022 seconds** with the locked Python 3.12.14, NumPy 2.2.3 and SciPy 1.15.2
environment and inherited `PYTHONPATH` removed. All eight verification steps
exit successfully. The ledger reports **600 PASS, 37 PASS_ANON, three
NOT_EXECUTED, zero FAIL**, with 218 entries, and all **24/24** required contract
checks pass. It reproduces 21 original artifacts byte for byte, six follow-up
table artifacts and six explanatory-chart artifacts exactly, and recomputes all
24 terminal intervals from 600 summaries. It verifies 42 sidecarred and 37
independently pinned evidence files. The **23 shipped tests pass** in 0.83 seconds
with 1,202 existing pytest assertion-rewrite AST deprecation warnings. The three
unexecuted checks concern follow-up raw/upstream operations, the original study's
bootstrap inputs and original raw trajectory bytes. Compact terminal-interval
verification does not establish raw-dependent roundwise replay. The log and
machine-readable report are
`/workspace/cce-build/clarity-final-reviewer-verify.{log,json}`.

### Final repository regression for the follow-up

The complete run on the frozen final sources and verification code used:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  TMLR_OUT=/workspace/cce-build/tmlr-clarity-final-release \
  /workspace/cce-research-env/bin/python -m pytest -q -ra tests experiments/tests
```

Result: **716 passed, three skipped, zero failed, two warnings**, in
**384.00 seconds**. The log is
`/workspace/cce-build/tmlr-clarity-final-tests.log`. The skips concern the host
reporting no user `TEXMFVAR`, its `TEXMFSYSVAR` not being a symlink, and the legacy
clean-bibliography test looking for a rebuild at an old workstation path. Both
final source archives and their bibliographies were independently rebuilt as
recorded above. Both warnings come from deliberate duplicate-ZIP-member mutation
tests; those tests pass. Only internal documentation changed after this run.

The final independent commit-scope audit confirms the frozen source hashes,
all 46 active scientific mirrors, all 358 preceding review files and the
historical PDFs. The four allowed protected-file changes are the chart generator,
its generated annotation and provenance, and the child contract's corresponding
pins; the other 236 protected files remain byte-identical. Every source and
supplement member matches its manifest record. No internal review or manifest
record is included in the upload archives. The report is
`/workspace/cce-build/clarity-final-commit-scope.json`.
