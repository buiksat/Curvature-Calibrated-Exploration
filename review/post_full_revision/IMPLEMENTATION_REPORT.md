# Implementation of the post-study revision plan

Completed scientific revision on 2026-10-14, following the user-approved
[plan](../post_full_fable/REVISION_PLAN.md), the exact Claude Fable 5
[review](../post_full_fable/review.md), and its source-checked
[qualifications](../post_full_fable/QUALIFICATIONS.md). The revision uses the
completed evaluation and separate exploratory diagnostics. It makes no new
adaptive-policy performance claim and does not indicate a venue submission.

## Manuscript and theory

The new title is **Confidence Transport under Relinearization: Guarantees,
Conservatism, and Policy Behavior**. The abstract, introduction, related work,
conclusion, and availability statement now distinguish conditional confidence
validity from certificate usefulness and realized policy behavior.

`paper/transport_theory.tex` and `paper/transport_proofs.tex` add:

1. A precise same-history width floor. Exact actionwise transport reproduces
   the direct reference width; a necessity statement explicitly fixes the
   center, bias, positive confidence radius and full confidence band. This
   elementary comparison neither orders adaptive regret nor excludes stronger
   confidence constructions.
2. A direct two-sided relative endpoint corollary with separate outward and
   return factors, retaining the theorem's operator, solver and confidence
   assumptions.
3. A scaled-tanh relative-weight certificate: the uniform endpoint distance
   is at most `4 log cosh(BR/sqrt(W))`, independent of horizon. Collection-time
   category weights give a sharper sandwich, including the unchanged ridge.
   The proofs distinguish endpoint comparisons from the original interpolated
   factor-path length.

The completed follow-up is the main empirical section. Its **600 evaluation
trajectories** are separate from **294 development/tuning trajectories**.
All nine comparator-minus-Hessian pointwise paired intervals are negative.
Primary path-inflated bounds and frozen policies' own bounds are all vacuous.
The original near-linear study remains in the appendix with its evidence
unchanged and its missing-raw-data limitation visible.

Five generated tables cover outcomes, drift/bounds, original fixed-history
recommendations, per-seed mechanism variation and new relative certificates.
[Their generator](../../tools/make_transport_followup_paper.py) binds input and
output SHA-256 values in `paper/tables/transport_followup_provenance.json`.
All four behavior-history groups are represented in the diagnostics. The text
retains numerical tie sensitivity, uncertainty conditional on a fixed teacher,
pointwise rather than simultaneous intervals, changing reward tasks across W,
and optimism success for the naive control.

The [literature audit](LITERATURE_CHECK.md) checks close publisher sources,
credits existing misspecified-linear and sketching ingredients, and removes two
unverified peripheral active claims. Their historical bibliography entries
remain; blocked retrievals are not evidence of fabrication. This bounded audit
does not establish novelty or submission readiness.

## Exploratory audit and decision about more experiments

The new [analyzer](../../tools/analyze_relative_transport.py) replays the
unchanged optimizer on every saved action/reward history; it generates no new
observations and substitutes no behavior actions. The [results](../transport_relative_diagnostics/RESULTS.md)
and [reproduction instructions](../transport_relative_diagnostics/README.md)
record all **600 histories / 600,000 rounds**, checked in **434.736 seconds**
on four CPU workers. This is post-outcome analysis, not a held-out test of a
new policy.

The 3,005-file input inventory binds 3,724,135,561 bytes. Independent review
matched all 2,400 consumed evaluation trajectory inputs against the previously
preserved hashes. All recorded parameter norms and optimizer displacements
reproduce exactly. Matrix/center/eigenvalue reconstruction uses 3,600 fixed
checkpoints and the original tolerances; the largest normalized residual is
0.00499440373754794. All checks pass, but ordinary float64 computations do not
constitute verified mathematical enclosures.

Category asymmetric effective widths average **1.002783, 1.042708 and 1.126764**
times direct frozen widths on primary histories. They remove much of the
Hessian/Q inflation without adding confidence information. Kernel medians are
27.7 microseconds for category ratios, 34.8 including current projections and
213.3 for dense endpoint evaluation over 36 fixed states under parallel load.
These measurements exclude matrix/estimator construction and the policy loop;
no end-to-end speedup has been established. Fixed-history recommendation regret
is not an alternative policy's adaptive regret.

**Decision: no new adaptive/GPU experiment yet.** Tightening this conversion
alone approaches the already available frozen score. Further work needs a
specific setting where its full computational cost is advantageous, or a new
statistical confidence construction. Any subsequent policy selected using these
outcomes requires a locked protocol and fresh evaluation seeds. The existing
29-dimensional NumPy/SciPy study runs appropriately on CPU; access to two A100s
would not resolve this scientific limitation.

## Build and scope

The main branch contains a self-contained manuscript mirror under
`submissions/tmlr_2026/`, pushed as
[`fb95a696863326345be0823de399937fcbdb8af8`](https://github.com/buiksat/Curvature-Calibrated-Exploration/commit/fb95a696863326345be0823de399937fcbdb8af8).
This research branch retains canonical sources and
analysis tools. The official TMLR style files and font sizes are unchanged.
The final main-branch build has **38 pages**, references beginning on page 18,
no unresolved references/citations, missing characters, overfull boxes or
LaTeX warnings. Four underfull-box diagnostics remain. Key pages and tables
were visually inspected. PDF identifying metadata is empty.

Workspace build outputs (not committed binaries):

- `/workspace/cce-build/tmlr-full-revision/main.pdf`, 642,844 bytes,
  SHA-256 `8cc566123e1fe13bdb23b5f7929f1d3bb22df9d8f847007b350b61840ddac5d7`.
- `/workspace/cce-build/tmlr-full-revision/source.zip`,
  SHA-256 `4872f6e2da31318ec7263573ec6737f49aa0d8ff6c9bb25ac453f840b8cc47a5`.

A fresh extraction of the 45-member source archive rebuilt the identical PDF.
The recorder contains no inputs from either original checkout. All four official
style/licence hashes match the pinned upstream files. This reproduction uses
the declared local TeX environment and does not establish strict system-tree
package certification.

The numerical ledger passes **565 checks**, with **4 NOT_EXECUTED** limitations
and **216 source-derived entries**. It independently reconstructs terminal
bootstrap intervals, validates five generated tables and their fixed input
hashes, and retains whole-file/context guards. The nonexecuted checks are not
counted as passes.

The historical `paper/main.pdf`, scientific implementation, locked study
configs/selections and all existing evaluation/review exports are unchanged.
The new analysis has its own directory and provenance. Neither the manuscript
build nor the numerical audit certifies an anonymous evidence supplement.

## Outstanding release and scientific limits

The strict research release requires protected system TeX inputs. This host
lacks `algorithm.sty` and `algorithmic.sty` there. Installation of the verified
Debian dependency was attempted and failed because UID 1000 cannot acquire the
system package-manager lock; no administrator capability or sudo is available.
This was an operating-system permission failure, not an approval rejection.
The trust check was preserved. The compiled-source contract was refreshed from a real diagnostic compiler
recorder ([diagnostic record](DIAGNOSTIC_CLOSURE_AUDIT.json)): 87 project-local
inputs, seven additions, ten changed byte records,
and no removed paths or weakened roles. This local-TeX build is not strict
release certification. The expanded anonymous evidence inventory still lacks
13 pinned source/tool inputs and supported provenance for six active outputs.
The release CLI now reports this gap and exits before staging or publishing,
preserving any previous deliverables. Its tests retain altered-evidence and
missing-source rejection; the old supplement does not cover the new paper.

The compact Git export permits independent terminal-bootstrap reconstruction.
Roundwise replay still requires the retained external raw archive; a durable
anonymous distribution path is open. Missing original-study raw logs and its
historical dependency discrepancy remain disclosed. The current paper is a
single synthetic model with one fixed teacher and no established practical
regret or full-computation advantage. Author assessment of scientific breadth,
anonymous distribution and OpenReview declarations remains necessary before
submission.

The current executable-check and archive-reproduction results are recorded in
[REVISION_VALIDATION.md](../../submissions/tmlr_2026/REVISION_VALIDATION.md).

The final full repository regression run completed with **624 passed, 45
skipped, zero failures** in 151.62 seconds using the pinned Python environment
and single-threaded BLAS. Skipped release/optional-capability checks are not
passes and do not certify the blocked anonymous supplement. The detached
original-study verifier and its 67-test regression module also pass. Earlier
failed integration runs and their specific repairs remain in the validation
record rather than being relabeled as successful executions.
