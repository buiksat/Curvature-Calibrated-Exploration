# CC-UCB manuscript — change summary and request for review

**To:** GPT Pro (expert second opinion)
**Re:** *Curvature-Calibrated Exploration for Differentiable-Model Bandits* (CC-UCB)
**What I want:** please **verify the math I added/changed, flag anything wrong or overstated, and correct it.** I am especially unsure about the items in §3 ("Please verify"). Be adversarial — assume there are errors and find them.

---

## 0. Context

- Single-column technical report (~50 pp) converted toward an **AISTATS** anonymous submission. There is now exactly one source, `paper/main.tex`, plus `macros.tex`, `references.bib`, and the official `aistats2026.sty` (used as a **provisional** baseline; the AISTATS 2027 kit is not yet published, so target-year compliance is unverified).
- The paper studies contextual bandits whose reward is a differentiable model; the exploration bonus is the predictive variance under the **full GGN/Fisher curvature**, solved matrix-free by CG. The headline empirical finding is *negative*: at matched coverage a cheaper curvature surrogate ties/beats full curvature.
- Central result **preserved unchanged** (do not re-derive, but sanity-check consistency):
  R_T ≤ 2·sqrt[ (σ² + G²/λ) · Λ_T^C · Σ_t α_t² u_t(a_t) ω_t² ] + 2 E_T,
  with sublinearity condition **Λ_T^C · S_T = o(T²)** and **E_T = o(T)**, where S_T = Σ_t α_t² u_t(a_t) ω_t²; ω_t = β̄_t + ψ̄_t (original center) or β̄_t (corrected center).

The current real-AISTATS build compiles clean (0 undefined refs/citations, 0 duplicate labels), two-column, ordered main → references → reproducibility checklist → appendix. **Main content is ~24 two-column pages; the AISTATS limit is 8** (condensation still pending).

---

## 1. Structural / venue changes (low math-risk — sanity check only)

- Consolidated a former two-file setup into one `main.tex`; removed all NeurIPS submission infrastructure (style, stub, checklist, `\answerYes/No/NA/Partial`, page-limit language, "checklist-last" framing, NeurIPS comments). NeurIPS **bibliography** entries kept.
- AISTATS style hook: anonymous by default, `\ifaccepted` toggle for camera-ready, fail-clear if the official style is absent, plus a clearly-labeled non-AISTATS provisional shell for local content review. Two-column `\aistatstitle/\aistatsauthor/\aistatsaddress` block (anonymous).
- AISTATS ordering: **main → references → reproducibility checklist → appendix** (not NeurIPS's checklist-last). The official AISTATS reproducibility checklist is **not available**, so there is an honest prose **placeholder** clearly marked "insert official checklist" — I did **not** fabricate AISTATS questions. **Q: is a placeholder acceptable, or should I reconstruct the AISTATS checklist from memory (I declined to, to avoid fabrication)?**

---

## 2. Claim / honesty corrections (please check accuracy, not just grammar)

1. **Window guarantee.** For an unrescaled current-parameter subset, Ĉ_t ⪯ C_t and κ_{+,t}=1 hold **deterministically**; the overall regret guarantee remains **conditional** on the full-to-frozen transfer and the other certificates. (Previously said "covered unconditionally.")
2. **Coverage metric renamed** to "top-two armwise oracle optimism coverage" / "true-label-arm oracle optimism coverage," with an explicit caveat that these are **armwise coverage averages** and do **not** measure correct action selection, decision-gap coverage, P(optimal arm), or deployable calibration. Written as explicit finite-sample empirical means.
3. **Covertype experiment relabeled** "full/diagonal **last-layer** covariance" (neural-linear / last-layer, d=196), explicitly **not** full-parameter GGN, and stated not to test backbone drift, the centering certificate, full relinearization, or the dynamic potential.
4. **Tables framed** as oracle-selected **interpolated response-surface estimates at α\*** (no policy is actually run at the interpolated α\*), with **nominal, selection-unadjusted** paired-t intervals (same runs for selection and reporting → **not** post-selection confidence intervals). Statistical-significance checklist answer = No. **Selection unit (per-seed vs pooled) is stated as not established** (no code/records).
5. **Diagnostics** χ_t, ψ_t described as "primitive diagnostic targets" **not directly observable** in the stated O(d)-memory implementation (need frozen-feature replay / checkpoints / a frozen-feature matvec oracle / a validated estimator).
6. **Systems positioning** softened: distributed HVP/Krylov work demonstrates related infrastructure but does **not** benchmark the exact per-example GGN operator or end-to-end CC-UCB latency. Kept the O(K·T^{5/2}) worst-case cumulative sample-CVP cost.
7. **Reproducibility = No** (grids given only by endpoints; Lanczos seed/cadence, selection unit, Covertype optimizer/preprocessing/hardware, and inverse-residual definition not stated; no code attached). Undefined Lanczos "relative residual" numbers (46, 2.3) **deleted** (definition unrecoverable); qualitative rank-sensitivity kept.
8. **NeuralUCB/NeuralTS** stated to use full neural-gradient Gram in their *theoretical* algorithms; diagonal versions labeled implementation approximations.
9. Anonymity: empty PDF metadata, "Anonymous Author/Institution," no names/paths/links/"our"-self-citation. `granziol2026hessian` (public arXiv, shares first name "Diego" with a deleted author macro → possible self-citation) kept as a third-person public citation. **Q: is that the right call under AISTATS double-blind?**

---

## 3. NEW / CHANGED MATH — **please verify each (highest priority)**

**(a) Gaussian bounded-feature event (added to the constructed experiment).**
The theory assumes bounded features G, but the constructed contexts are Gaussian (unbounded). I added, for x_t ~ N(0,Σ) i.i.d.:
> with prob ≥ 1−δ_G: max_{t≤T} ‖x_t‖₂ ≤ √(tr Σ) + √(2‖Σ‖_op·log(T/δ_G)),
> hence G_T(δ_G) = √(tr Σ) + √(2‖Σ‖_op·log(T/δ_G)) + b·max_a|δ_a|,
via Gaussian Lipschitz concentration of x ↦ ‖x‖₂ (mean ≤ √tr Σ by Jensen; sub-Gaussian parameter ‖Σ‖_op since ‖·‖₂ is √‖Σ‖_op-Lipschitz in the standard normal) + union bound over t≤T, with δ_G added to δ_cert.
**Verify:** the constant/exponent, the Lipschitz constant, and whether any dimension-dependent term is missing.

**(b) Constructed-instance scope.** With φ(x,a)=x+b·δ_a·e_align(θ) and θ\*=S·e_align(θ):
> μ\*(x,a) − μ\*(x,a') = S·b·(δ_a − δ_a'), independent of x ⇒ the optimal arm is the same for every context; with ν=0 the context contribution along θ\* is 0 a.s.
I renamed it a "linear-Gaussian **linear-bandit stress test with nuisance contextual covariates**," not a context-dependent arm-ranking problem. **Verify the derivation and the framing.**

**(c) Covariance geometry.** h(θ)⊥e_align(θ) for **every** θ (I removed a false "decision axis rotates toward the high-variance axis"). In the fixed basis the in-plane 2×2 block off-diagonal is **(κ−ν)·sinθ·cosθ = ½(κ−ν)·sin2θ**, maximal at 45°; ν=0 makes Σ degenerate (rank d−1). **Verify the off-diagonal expression.**

**(d) Lanczos inverse is exact.** For Ĉ_t = λI + Σ_{i≤k}(λ_i−λ)u_iu_i^T with orthonormal Q=[u_1..u_k]: Ĉ_t^{-1} = QΛ^{-1}Q^T + λ^{-1}(I−QQ^T) **exactly** (SMW; Ĉ_t approximates C_t but its inverse formula is exact). **Verify.**

**(e) CG when κ̄=1.** If κ̄ is the **true** condition number, κ̄=1 ⇒ C=c·I for a scalar c>0 (one CG step from zero is exact), **not** necessarily C=λI; with the paper's specific κ̄ := λ_max(C)/λ, κ̄=1 ⇒ (with C⪰λI) C=λI. Separate branch kept to avoid the log-denominator blowing up. **Verify both readings.**

**(f) Warm-start CG.** Added, for a warm start ũ_0≠0:
> ‖ũ_I − C^{-1}g‖_C / ‖C^{-1}g‖_C ≤ 2·q^I·(‖ũ_0 − C^{-1}g‖_C / ‖C^{-1}g‖_C), q=(√κ−1)/(√κ+1),
i.e. the zero-start bound times the initial relative energy error. Stated: adaptive residual stopping stays valid with a warm start, but the fixed-budget iteration count is valid **as written only** for zero init. **Verify the factor and the claim.**

**(g) Matrix-Bernstein sample size.** Changed "n = Θ(...)" / "scales quadratically" to: the RHS of the sufficient condition is **O( m²B²L/(ε²λ²) + mBL/(ελ) )** with a **quadratic leading dependence** on m=t−1, plus a finite-population caveat (if the threshold exceeds m, use all m; do not read it as requiring n>m). **Verify it is correctly stated as a sufficient upper bound, not a necessary complexity.**

**(h) Restricted-Krylov eigenvalue.** Relabeled the largest generalized eigenvalue of Ĉ_t C_t^{-1} maximized over a small Krylov subspace an "**empirical Krylov estimate**" of κ_{+,t}, stated it is generally a **lower** estimate of the global max (**not** a certified upper bound) and **not** sufficient to certify the approximate-curvature theorem. **Verify this direction (lower vs upper).**

---

## 4. Known-incomplete / blocked (feedback on approach welcome)

- **8-page condensation not done.** Main content ≈ 24 two-column pages. Plan: move all proofs/secondary lemmas/derivations/legacy/exp-family/CC-TS/future-protocols to the appendix; keep only abstract, problem+method, compact Algorithm 1, abbreviated assumptions, Theorem 13 + proof sketch, compact statements of the whitened-drift and dynamic-potential lemmas, the two experiment tables + calibrated interpretation, related work, limitations/conclusion. **Q: is this the right main-body selection for an 8-page AISTATS paper, and what would you cut first?**
- **39 overfull hboxes** (wide display equations + the 5-column results table exceed the ~3.25″ AISTATS column). **Q: reformat wide equations (multi-line / `\resizebox`?) and set the results table as full-width `table*` — any objection?**
- Missing experiment records (grids, seeds, Lanczos seed/cadence, Covertype training/hardware, selection unit) → left as explicit omissions; reproducibility answers negative.
- Provisional AISTATS 2026 style standing in for the 2027 target.

---

## 5. Questions for you

1. Are any of the added derivations in §3 **wrong, imprecise, or missing a constant/assumption**? Which would you rewrite?
2. Is the theorem-to-experiment consistency sound — in particular, does the constructed instance (degenerate Σ, fixed optimal arm, bounded-feature only on a high-probability event) legitimately *instantiate* Theorem 13, or should it be presented purely as a diagnostic?
3. Are the honesty/claim corrections in §2 accurate, or have I **over-corrected** (weakened a claim that is actually defensible) anywhere?
4. For the 8-page condensation, what is the minimal main-body content that keeps the primary claim self-contained?
5. Anything venue-specific for AISTATS (formatting, checklist, double-blind) I have gotten wrong?

*(All changes are local; no code was run to regenerate experiment numbers, and no numerical results were altered.)*
