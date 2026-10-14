# Review-revision validation

This record concerns the manuscript revision synchronized on 2026-10-13
(America/Los_Angeles). `FINALIZATION_REPORT.md` remains the historical release
record. A collected test has not necessarily run or passed.

**Current result (2026-10-14):** the final strict release, extracted supplement
verification and byte-identical clean source rebuild all pass. The final full
repository run reports **694 passed, 3 skipped, zero failed**. The final sections
record the commands, artifacts, diagnostics and remaining raw-data limitations.
These results supersede the historical system-TeX and missing-inventory blockers
below. Compact evidence verification remains separate from raw-trajectory replay.

| Collection scope | Current collected cases |
| --- | --- |
| Release-package test collection | 545 collected |
| Repository suite collection | 697 collected |

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
