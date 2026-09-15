# Exposition revision, 2026-09-11

This note records the prose-only AISTATS manuscript rewrite based on
`daec199c06c792a2eefee7b861d9e9c683c18cba`.

## What changed

- Rebuilt the introduction around the collection-time versus current-curvature mismatch,
  defined the four uncertainty objects before the formalism, and described one policy round.
- Added a layered reading of the headline theorem and a concrete explanation of matrix-free
  CG versus operator approximation.
- Reorganized the controlled experiment around validity, certificate tightness, bound
  nonvacuity, and matched-stream policy behavior. Pooling units and adaptive-history limits
  are stated next to the relevant numbers.
- Reworked related work around where each method fixes its uncertainty features and what
  statistical question it answers.
- Standardized the editable prose on "diagnostic comparator" for the dense endpoint policy
  and stated that its endpoint calculation uses learner-known matrices before reward
  observation. The protected generated tables and figures retain their historical "dense
  oracle" labels; this note records that legacy wording rather than rewriting those artifacts.
- Rewrote the abstract and conclusion to state the conditional guarantee and the negative
  empirical findings at their supported strength.
- Added proof and appendix roadmaps. Generated tables, figures, numerical entries, and
  evidence files were not edited.

## Formal-content preservation

The transitive manuscript at the baseline contains 17 TeX inputs, 71 theorem-like or
algorithm blocks, 261 labels, and 155 numbered display environments. A stricter final
comparison checked theorem, lemma, proposition, corollary, assumption, algorithm, proof,
numbered-display, and `\[...\]` blocks in every edited TeX source. All 391 extracted blocks
match the baseline byte-for-byte and all 261 labels are unchanged.

The title, anonymous author metadata, conference-style fallback, theorem statements,
assumptions, proofs, algorithms, equations, constants, labels, and bibliography entries are
unchanged.

The protected tracked `paper/main.pdf` remains the baseline snapshot with SHA-256
`2545c368d6b97393f5c1e5bb61d4696f7fed6b8ae988ce42c9d7bc7ccab717e1`.

## Build record

All builds used TeX Live 2020 and latexmk 4.70b in disposable copies under
`/tmp/cce-exposition.nqZOmI`.

| Stage | Pages | Overfull boxes | Result |
| --- | ---: | ---: | --- |
| Baseline | 63 | 5 | exit 0 |
| Batch A, introduction and method intuition | 63 | 5 | exit 0 |
| Batch B, theory and proof transitions | 63 | 5 | exit 0 |
| Batch C, experiments, related work, conclusion | 64 | 5 | exit 0 |
| Batch D, final abstract and continuous read | 64 | 5 | exit 0 |

The appendix begins on page 13 in the revised build versus page 12 in the baseline. The
total manuscript grows from 63 to 64 pages. Static validation passes with 261 labels, zero
duplicates, 184 reference targets, zero unresolved references, 37 cited keys, and zero
missing bibliography entries.

Every final page was rendered at 150 dpi with Ghostscript and inspected in 16 four-page
contact sheets. No clipped text, overlapping elements, broken equations, or problematic
float placement was found. The existing five overfull boxes remain; no new overfull box was
introduced.

## Literature read for exposition

The local corpus at `/tmp/cce-litcorpus` was used. The following primary-paper sections were
read; no wording was copied.

- Zhou, Li, and Gu (2020), `zhou2020neural`: introduction; problem setup; NeuralUCB
  algorithm; main theorem and proof roadmap; experiments; conclusion. The stated algorithm
  accumulates selected gradient features when observations arrive.
- Zhang et al. (2021), `zhang2021neural`: introduction; NeuralTS algorithm; effective-
  dimension theorem and remarks; proof roadmap; benchmark and delayed-feedback experiments;
  conclusion.
- Riquelme, Tucker, and Snoek (2018), `riquelme2018deep`: introduction; Thompson sampling;
  method families including NeuralLinear; adaptive-feedback example; experimental protocol;
  method-by-method discussion; conclusion.
- Kassraie and Krause (2022), `kassraie2022neural`: introduction; assumptions and NTK
  spectrum; NTK-UCB information-gain analysis; NN-UCB approximation; CNN extension;
  experiments; conclusion.
- Maddox et al. (2021), `maddox2021fast`: introduction; related work; trained-network
  linearization; function-space inference; implicit Fisher/Jacobian products and CG;
  inductive-bias and transfer experiments; conclusion.
- Daxberger et al. (2021), `daxberger2021laplace`: introduction; parameter-subset and
  curvature choices; hyperparameter and predictive approximations; software composition;
  experiments; related work; conclusion.
- Salgia et al. (2023), `salgia2023provably`: introduction; problem and assumptions;
  finite-network/NTK approximation and confidence; grouped-history algorithm and regret;
  experiments; conclusion.
- Deb et al. (2024), `deb2024contextual`: introduction and gap table; online-regression
  setup; quadratic-growth results; SquareCB/FastCB reductions; related work; experiments;
  conclusion.

All eight bibliography entries already existed, and `paper/references.bib` was not modified.

## Citation correction

The related-work reorganization in `360e07f` accidentally dropped
`mackay1992practical` and `martens2015optimizing`. Commit `43418e1` restored both citations at
the claims they support. `paper/validate.py` could not detect the loss because it checks that
present citation keys resolve, not whether citations present in an earlier revision were removed.

## Deliberately unchanged

- The full standard-Borel headline theorem and its path-based certificate interface.
- The corrected-center assumptions, including the fixed ex-ante reference parameter,
  pre-reward envelopes, and historical `1/sigma` scaling.
- The one-sided dynamic theorem and every legacy fallback condition.
- Generated table and figure bytes, locked evidence, numerical labels, and artifact hashes.
- The provisional AISTATS 2026 fallback style and absent target-year checklist behavior.
- Optional CODE post-review statistics, terminal quantiles, and new significance claims.

## Issue retained for scientific review

Low severity, definite typesetting defect: `paper/main.tex` currently writes
`\hat\gamma\gets\hat\gamma+log[1+\cdots]` in the detailed legacy algorithm rather than
`+\log[1+\cdots]`. TeX renders `log` as multiplied italic variables. The minimal correction
is the missing backslash. This pass leaves the formal algorithm unchanged, as required.

The build is provisional because the AISTATS 2027 style and official target-year checklist
are absent. This is an environment/venue-package limitation, not a compilation failure.

## Third-review bounded corrections, 2026-09-11

Starting commit: `8cbf3b4bf5f0943be84798ef98bbdcea10f9fea4`.

- F1 corrects newly written solver prose to identify the certified width as the square root
  of the inverse quadratic form. The relevant interface and construction are
  `eq:solver-interface-new` and `lem:inverse-quadratic-certificate-new`.
- F2 restores the median declaration in the caption for
  `tab:transport-instantiation-tightness` without changing its populations or counts.
- F3a--c add the three missing backslashes in `eq:approx-realizability-new` and
  `eq:scaled-tanh-constants`. These typesetting defects were already present at `daec199`;
  they were not introduced by the exposition rewrite.

The earlier byte-identical formal-block statement remains the historical record through
`8cbf3b4`. This patch is an explicit formal-freeze exception only for the three inherited
missing-backslash repairs. The changed files are `paper/transport_proofs.tex`,
`paper/transport_experiment_appendix.tex`, `paper/transport_theory.tex`, `paper/main.tex`,
and this revision record.

Baseline and candidate builds both ran
`latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex` with latexmk 4.70b and
TeX Live 2020. Both exited 0 at 64 pages, with the same five overfull boxes and no undefined
references, undefined citations, or multiply defined labels. `python3 paper/validate.py`
passed with 261 labels, 184 resolved reference targets, and 37 cited keys. The required
`grep -rn '[^\\]qquad' paper/*.tex` check returned no matches. All 64 candidate pages were
viewed in contact sheets; the four changed locations and their neighboring page breaks were
also viewed at full-page resolution.

The separately built candidate PDF is
`/tmp/cce-f3-artifacts.ix1q69/candidate/paper/main.pdf`; build and verification logs are
under `/tmp/cce-f3-artifacts.ix1q69/`. The tracked `paper/main.pdf` remains unchanged at blob
`4e977c49213c031111cdddcee03db90afcd17d48`, with SHA-256
`2545c368d6b97393f5c1e5bb61d4696f7fed6b8ae988ce42c9d7bc7ccab717e1`.
No experiment or evidence was regenerated, and nothing was published.

## Fourth-review bounded corrections

Reviewed SHA and execution START: `44aab62d7370c874a1ae485bb63ba811cb3fc658`.

- R4-F1 corrects the legacy centering description: `asm:optim` compares the current
  parameter with the auxiliary frozen-feature ridge estimator through an action-projected
  discrepancy. It is not a global nonlinear optimization certificate.
- R4-F2 states that restricted fine-tuning or a trust region can limit Taylor error but does
  not by itself establish $E_T=o(T)$. An exactly linear head on a frozen backbone has zero
  Taylor remainder; other cases need an explicit cumulative-error bound.
- R4-F3 removes the unmatched parenthesis from the categorical-curvature expression in
  `app:expfam`.

All three defects were already present at `daec199`; none was introduced by the exposition
rewrite or by `44aab62`. The R4-F2 prose replacement inside `asm:linear` and the one-character
R4-F3 inline-math repair are explicit exceptions to source-byte preservation. Earlier
preservation reports remain historical records for their stated revisions.

The changed files are `paper/legacy_dynamic.tex`, `paper/main.tex`, and this revision record.
Baseline and candidate builds both ran
`latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex` with latexmk 4.70b and
TeX Live 2020. Both exited 0 at 64 pages, with the same five overfull boxes and no undefined
references, undefined citations, or multiply defined labels. Baseline and candidate
`python3 paper/validate.py` runs passed with 261 labels, 184 resolved reference targets, and
37 cited keys. The whole-file expected-transform check passed for both edited TeX files;
labels and citations are unchanged, and the only changed formal block is `asm:linear`.

Ghostscript rendered all 64 candidate pages. All 16 contact sheets were viewed, followed by
full-page inspection of the edits on pages 18, 27, and 58 and their neighboring pages. No
clipping, overlap, malformed math, or new page-break problem was found. The separately built
candidate PDF is `/tmp/cce-r4-artifacts.kONmej/candidate/paper/main.pdf`; logs and verification
artifacts are under `/tmp/cce-r4-artifacts.kONmej/`.

The tracked `paper/main.pdf` and `paper/main.pdf.sha256` remain unchanged, as do the
bibliography, generated tables and figures, evidence, results, review bundles, and CODE
submission. The final remote check was deferred after the required fetch attempt returned
403. No experiment, unrelated CI, push, PR, synchronization to `main`, or publication ran.

## Fifth-review bounded corrections

Reviewed SHA and execution START: `6e0d4c62d9959960c7a927607cf7d724dcb6cff9`.

- R5-F1 changes the final linearization-bias relation in the proof of `lem:confidence` from
  equality to an upper bound: the realized remainder norm is at most the actionwise envelope
  sum $\sqrt{F_t}$.
- R5-F2 limits the constant CG-budget statement to a fixed target tolerance as well as a
  fixed unrescaled buffer size.
- R5-F3 describes $L_g^2RQ_t$ as an alternative trust-region bound, not a uniform
  improvement over the cubic expression.
- R5-F4 distinguishes $K$ CG solves from $KI$ iterations under a common per-solve budget.

All four defects were already present at `daec199`; none was introduced by the exposition
rewrite or later correction rounds. R5-F1 is an explicit one-relation exception to the proof
byte freeze. No theorem statement, confidence radius, constant, equation, algorithm, label,
citation, or empirical result changed. This bounded task did not audit the full legacy proof
or complexity analysis.

The authoritative `check_r5_source.py` passed in both `--apply` and `--verify` modes against
START. It produced candidate `main.tex` SHA-256
`e9d69e1cf4c89bc1a7edff71de8f40a09adbede21153d4ba202b515cf6e9758a`.
The supplemental preservation check found 178 formal blocks with one intentional difference,
the proof of `lem:confidence`; all 155 equation/align environments, three algorithms, 261
labels, and 63 citation occurrences remain unchanged.

Baseline and candidate builds both ran
`latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex` with latexmk 4.70b and
TeX Live 2020. Both exited 0 at 64 pages. Each final log has five overfull hboxes, ten
underfull hboxes, four underfull vboxes, and no undefined references, undefined citations, or
multiply defined labels. Baseline and candidate `python3 paper/validate.py` runs passed with
261 labels, 184 resolved reference targets, and 37 cited keys.

Ghostscript rendered all 64 candidate pages. All 16 contact sheets were viewed, followed by
full-page inspection of the edits on pages 23, 45, 53, and 57 and their neighboring pages. No
clipping, overlap, malformed math, or new page-break problem was found. The separately built
candidate PDF is `/tmp/cce-r5-artifacts.h7Sbrl/candidate/paper/main.pdf`; logs and verification
artifacts are under `/tmp/cce-r5-artifacts.h7Sbrl/`.

Only `paper/main.tex` and this revision record change. The tracked `paper/main.pdf`, its
sidecar, bibliography, generated tables and figures, evidence, results, review bundles, and
CODE submission remain unchanged. The closing remote fetch was deferred after the required
initial fetch returned 403. No experiment, evidence regeneration, push, PR, Overleaf update,
release, or publication ran.

# TMLR finalization, 2026-09-15

Records the bounded TMLR submission-candidate finalization based on
`b99b682ecc8f69552a3f57b1b85333378ed12ac1`. Nothing was submitted, uploaded or
pushed, no experiment ran, and no locked evidence was regenerated.

## Source layout

`paper/main.tex` was a 4,052-line file that was simultaneously the AISTATS shell
and the home of most of the appendix mathematics. A second venue entry point
could only reuse that material by copying it, which is exactly the failure mode
earlier review rounds kept finding: prose that drifts away from unchanged
formal blocks. It is now a 167-line shell, and the material it used to hold
lives in files both entry points `\input`:

| New file | Was `paper/main.tex` lines |
|---|---|
| `notation.tex` | 55-64 |
| `body_intro.tex` | 113-199 |
| `appendix_rates.tex` | 203-381 |
| `body_conclusion.tex` | 387-441 |
| `appendix_deferred.tex` | 473-2994 |
| `body_related.tex` | 2998-3133 |
| `appendix_protocol.tex` | 3135-3663 |
| `appendix_onesided_proof.tex` | 3667-3794 |
| `appendix_cg.tex` | 3796-3881 |
| `appendix_twosided.tex` | 3883-3969 |
| `appendix_ggn.tex` | 3973-3995 |
| `appendix_expfam.tex` | 3997-4028 |
| `broader_impact.tex` | 4035-4037 |
| `availability.tex` | 4040-4050 |

The extraction was mechanical and byte-preserving. Verified by rebuilding the
AISTATS entry point before applying any correction: 64 pages, five overfull
hboxes, and `pdftotext -layout` output byte-identical to the pre-extraction
build. `python3 paper/validate.py` reported the same 261 labels, 184 resolved
reference targets and 37 cited keys before and after.

`appendix_deferred.tex` wraps two blocks in `\iflegacyextras`: the
fixed-preconditioner CG lemma and the off-diagonal linear-Gram witness. The
AISTATS shell sets the switch true and keeps them; the TMLR shell sets it false
and omits them. `availability.tex`, `body_intro.tex` and `body_conclusion.tex`
use the same switch where they refer to the legacy-evidence appendix, which the
TMLR submission also omits.

## Content changes

Four inherited corrections, applied without touching any equation:

1. `lem:cg`. A fixed unrescaled buffer bounds the condition number only. The
   text now says that `alpha_t` is horizon-independent only under a fixed target
   tolerance, or a tolerance sequence uniformly bounded below one.
2. "Cost of the analyzed configuration". The simplified `O(K t^{3/2})` per-round
   and `O(K T^{5/2})` cumulative counts are now qualified by a fixed target
   tolerance and fixed problem constants, the `log(1/eps_t)` factor is required
   for a varying schedule, and the counts are stated as sufficient budgets
   rather than lower bounds on the work CG performs.
3. "Computable Curvature Operator". `O(I t)` is one action's solve; a round with
   `K_t` separate common-budget solves costs `O(K_t I t)`, and residual checks
   are charged separately.
4. Detailed pseudocode: `+log[` is now `+\log[`. Only the backslash was added.
   Verified in the rendered PDF: the operator is upright, not italic.

`transport_experiment.tex` gained three accuracy edits. The `e^{D_Q/2}` range is
now explicitly scoped to `T = 1000`; the adverse regret comparison names
sample-mean pseudo-regret against transport Hessian rather than "sample means";
and the endpoint ratio `D_Q/d_Th` is now reported, so the abstract's
five-to-six-orders-of-magnitude statement is checkable from the body. A sentence
was added recording that the outcomes show no causal or uniform advantage for
full curvature. In `body_related.tex`, a single-author citation's verb was
corrected.

One statement text changed, and only one: `lem:cg`, correction 1 above, which
now scopes the horizon-independence of `alpha_t` to a fixed target tolerance or
a tolerance sequence uniformly bounded below one. That is the sole
theorem/lemma/corollary/proposition statement-text exception in this revision,
and it is a scoping qualification: `lem:cg`'s equations and its conclusion are
unchanged, and so is its proof.

Nothing else moved. No other theorem, lemma, corollary, proposition or
assumption statement was touched, and no equation, constant, quantifier,
filtration or empirical number changed anywhere.

## Numerical provenance

`tools/verify_tmlr_submission_numbers.py` is a new executable ledger. It lists
every number the submission states about the controlled study once, with its
source and SHA-256, selector, unit, aggregation rule, population, unrounded
value and display rounding; it re-derives each from the locked aggregate,
requires it to round to the printed literal, and requires the literal to occur
in the file it is attributed to. It reports 103 PASS and two explicit
NOT EXECUTED, both raw-data dependent.

## Evidence tooling

`tools/transport_artifact_expectations.py` now holds the single copy of the
artifact-regeneration logic, extracted from the detached verifier so the
verifier and the anonymous supplement share it. It builds all 21 published
tables, figures and CSVs in memory and writes nothing; all 21 regenerate
byte-identically from the locked aggregate.

Five stale manuscript-literal checks in the detached verifier were replaced with
literals of the same scientific meaning against the current wording, and
negative checks were added: a prohibited-literal list catches an overclaim being
introduced or a de-anonymizing `tmlr.sty` option being set, and new tests prove
both directions fire. The additive, resource-only `experiments/BUCK` divergence
is acknowledged by a hash-exact pin held in the verifier, deliberately not in
the exporter's map, so the frozen review bundle's bytes do not change and any
other drift still fails closed.

## Build and inspection

The TMLR entry point builds through `submissions/tmlr_2026/build.sh` outside the
repository. 66 pages, zero unresolved references or citations, zero overfull
boxes, deterministic across rebuilds. All 66 pages were rendered and inspected
in eleven contact sheets, with full-resolution checks on the corrected
pseudocode line. `source.zip` is the staged project-local compile closure plus
the permitted style and licence inputs, and rebuilds the submitted PDF
byte-identically from a clean unpacked directory.

`paper/main.pdf` and its sidecar are unchanged and were not rebuilt. The
generated tables, figures, CSVs, sidecars, provenance records, locked aggregate,
selection record, review bundle and CODE submission are all unchanged.
