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
