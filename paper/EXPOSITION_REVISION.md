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
duplicates, 184 reference targets, zero unresolved references, 35 cited keys, and zero
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

All eight bibliography keys already existed. No reference was added or modified.

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
