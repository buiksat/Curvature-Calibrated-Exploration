# Revision Report: Dynamic-Transfer Refactor of the CC-UCB Theory

Scope: `paper/main.tex`. Backup at `paper/main.tex.bak` (pre-edit, 2873 lines;
post-edit 3149 lines). Empirical tables (`tab:constructed`, `tab:covertype`),
the results/discussion prose, and `references.bib` are byte-for-byte unchanged
(verified by diff). The prompt's `/mnt/data/main(13).tex` does not exist in this
environment; the target is the repo file `paper/main.tex`, which is the same
manuscript (same title, Theorem 10 = `thm:regret`, Assumption 4 = `asm:optim`,
Lemma 1 = `lem:primitive-pred`, Lemma 4 = old `lem:drift-sufficient`).

## Pre-insertion verification

Every requested new result was checked by an independent adversarial
verification pass (9 fresh-context provers, one per claim, asked to prove
rigorously or produce a counterexample). All nine returned **PROVEN** (four with
non-blocking caveats, which are now stated in the text). **No obstruction was
found; nothing requested was mathematically false.** Caveats folded in:

- (D) `\bar C_t^{-1/2}` is the symmetric principal root (stated in `lem:whitened`).
- (E) `\mathcal C_1 = \lambda I` is load-bearing for the `det(\lambda I)`
  denominator; the general-`\mathcal C_1` case uses `det(\mathcal C_1)` (stated).
- (G) needs `a_t^* \in \mathcal A_t`, uniformity of the per-round bounds over
  actions, and `u_t,\omega_t,\alpha_t \ge 0` (all stated in `thm:regret`).
- (A) multiple / per-round certificates compose by a union bound, so
  `\delta_cert` is a sum / horizon union (stated in the filtration and theorem).
- (H) the corrected center needs the exact frozen-feature ridge solve; it is
  `O(d^2)` memory and **not matrix-free at scale** (stated as a remark).

## Theorems / lemmas added or replaced

| Item | Change |
|---|---|
| `thm:regret` | **Replaced.** Was exact-curvature `2 α_I α_drift β̄_max √(TγT)+2E_T+2P_T`. Now the dynamic-transfer bound `R_T ≤ 2√((σ²+G²/λ) Λ_T Σ_t α_t² u_t(a_t) ω_t²) + 2E_T` for a general predictable SPD `𝒞_t`, plus `Γ_T^dyn` and observable `Λ̂_T` variants. |
| `lem:dynamic-potential` | **New (main device).** Exact pathwise identity `Λ_T = log det(𝒞_{T+1})/det(λI) − Σ log det(I+Ξ_t)`; `Λ_T ≤ Γ_T^dyn`; `Σ s_{𝒞,t}²(a_t) ≤ (σ²+G²/λ)Λ_T`. |
| `cor:lam-observable` | **New.** CG-observable upper bound `Λ_T ≤ Λ̂_T`. |
| `lem:whitened` | **Replaces** old `lem:drift-sufficient`. Whitened relative drift: `𝖦𝖦ᵀ=I−λC̄⁻¹⪯I`; `C̄⁻¹ᐟ²(C_t−C̄)C̄⁻¹ᐟ²=𝖦𝖣ᵀ+𝖣𝖦ᵀ+𝖣𝖣ᵀ`; one-sided `C_t ⪯ (1+χ_t)²C̄_t` (no smallness); primitive `χ_t ≤ ‖𝖣‖_F ≤ (L_g/σ√λ)(Σ‖θ_t−θ_s‖²)^{1/2}`. |
| `cor:drift-sandwich` | **New (legacy).** Two-sided `(1−ε)C̄⪯C_t⪯(1+ε)C̄`, `ε=2χ+χ²<1`, carries `eq:drift-sandwich`. |
| `lem:bonus` | **New.** `ω_t s̄_t(a) ≤ w_t(a) ≤ α_t ω_t √u_t(a) s_{𝒞,t}(a)`. |
| `cor:worstcase` | **New.** Looser `√(T Λ_T)` reduction under horizon maxima. |
| `cor:frozen` | **Rewritten (K).** Frozen features ⇒ `u_t=1, ψ̄_t=0, Ξ_t=0, V_T=0, Λ_T=γ_T` ⇒ `R_T ≤ 2√((σ²+G²/λ)γ_T Σ α_t² β̄_t²)`. |
| `cor:corrected-center` | **New (H).** Corrected center removes `ψ̄_t` exactly (`ω_t=β̄_t`), without `asm:optim`; remark documents the frozen-feature/`O(d²)` cost. |
| `thm:spectral-distortion` | **Refactored (J).** Now one-sided: `Ĉ_t⪯κ_{+,t}C_t` and `C_t⪯(1+χ̄_t)²C̄_t` ⇒ `u_t=κ_{+,t}(1+χ̄_t)²`; no lower spectral factor. |
| `cor:twosided` (`app:cor`) | **New (legacy).** Old two-sided `√(ρ₊/ρ₋)` result kept for comparison; states the assumption trade-off and that neither dominates. |
| App. proof `app:proof` | **Rewritten** to the 6-step chain (confidence+centering → bonus lower → per-round → bonus upper → Cauchy–Schwarz-after-sum → dynamic potential). |
| `cor:beta-constructive`, `cor:gammahat` | **Renamed/updated.** "Predictable … under an externally certified linearization bound"; surrogate now uses `u_s(a_s)`; explicitly not unconditionally computable. |

## Assumptions: removed / weakened / retained

- **Removed:** Assumption "Prediction stability" with the additive
  `η_t^pred` tolerance → replaced by `asm:optim` (**Action-scaled centering
  certificate**): `|g_t(a)ᵀ(θ_t−θ̂_lin)| ≤ ψ̄_t s̄_t(a)`. The additive `P_T`
  term is gone everywhere.
- **Removed:** two-sided feature-drift Assumption `asm:drift`
  (`(1±ε_drift)C̄_t`) as a main-theorem hypothesis. Replaced by the weaker
  one-sided `asm:transfer` (`s̄_t²(a) ≤ u_t(a) s_{𝒞,t}²(a)`, `u_t≥1`). The
  two-sided sandwich survives only as the legacy `cor:drift-sandwich` /
  `cor:twosided`.
- **Weakened:** the drift requirement is now one-sided (upper only) and
  `ℓ₂`-whitened, with **no smallness condition** for the main bound.
- **Retained:** sub-Gaussian noise (`asm:noise`), bounded features
  (`asm:bounded`), local linearization (`asm:linear`), realizability, finite
  action set. Filtration rewritten with explicit σ-algebra joins
  `ℋ_t = ℱ_{t−1} ∨ σ(x_t,𝒜_t,Ω_t)`, `𝒢_t = ℋ_t ∨ σ(a_t)`, with all
  algorithmic quantities required `ℋ_t`-measurable.

## Remaining unobservable / uncertified quantities (stated in Limitations)

1. `F̄_t ≥ F_t` — cumulative squared linearization bound (not data-computable).
2. `ψ̄_t` — centering certificate for the original nonlinear center (only
   `=0` provably in the convex last-layer regime; else external).
3. `u_t(a)` / `χ̄_t` / `κ_{+,t}` — the one-sided transfer factor.
4. `Λ_T` / `V_T` — realized dynamic complexity; `Λ̂_T` upper-bounds `Λ_T`
   from CG, but `V_T` needs determinant estimation and is **not** observable.
5. Corrected center at scale without storing frozen gradients / `O(d²)` Gram.

## Proof steps checked (all confirmed, independently)

D1–D7 (whitened lemma), E1–E6 (dynamic potential incl. exact telescoping),
F1–F2 (bonus sandwich), G1–G3 (regret chain, Cauchy–Schwarz applied only after
summing, no spurious `√T`), H (exact corrected-center identity), I (surrogate
monotonicity), J (one-sided transfer, no lower factor), K (frozen reductions),
A (measurability + `1−δ−δ_cert` composition). Matrix-inequality directions
were re-checked after every inversion.

## Compilation status

**Not run — no LaTeX toolchain is available in this environment and it cannot
be installed** (`pdflatex`/`xelatex`/`lualatex`/`latexmk`/`tectonic` absent; no
root for `dnf`; no outbound network for conda/tectonic — `curl` returns
`CURL_EXIT_6`, DNS failure). Substitute source-level validation performed and
passing:

- 104 `\label`s, **0 duplicates, 0 undefined `\ref`/`\Cref`/`\eqref` targets**.
- All theorem/lemma/proof/equation/align/itemize/enumerate/algorithm/table/quote
  environments balanced; `\left`/`\right` balanced; `$` parity even.
- New macros (`\bh,\Calg,\Lamalg,\Valg,\Gamdyn,\Gmat,\Dmat,\cHist`) defined once,
  no collision with `macros.tex`; no double sub/superscripts.
- Stale-token sweep clean: `η^pred`, `α_drift`, `ε_drift`, `ε̄_drift`,
  `asm:drift`, `cor:drift-uniform`, `lem:drift-sufficient`, `ρ₊^alg`,
  "non-standard potential", "main unresolved nonlinear term",
  "implementable confidence schedule" → all 0. `P_T` remains only in the two
  sentences that state it was removed.

**To compile (once a TeX distribution is available):**
```
latexmk -pdf -interaction=nonstopmode -halt-on-error paper/main.tex
# or: cd paper && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

## Claims weakened to match the theorem

1. Confidence schedule corollaries renamed from "Implementable …" to
   "Predictable … under an externally certified linearization bound"; explicit
   note that they are **not** unconditionally computable.
2. `cor:gammahat` now makes only the information-gain term observable, and only
   when `u_s` is certified — not `F̄_t` or `ψ̄_t`.
3. Abstract/intro: the confidence radius is not claimed fully computable unless
   `F̄_t, ψ̄_t, u_t` are certified; corrected center flagged as not matrix-free
   at foundation-model scale.
4. `thm:spectral-distortion`: dropped the claim of a general two-sided
   guarantee; the one-sided result is primary, and it is explicitly **not**
   claimed to dominate the legacy `√(ρ₊/ρ₋)` result.
5. Windowed/refresh operators: now require a verified one-sided transfer factor
   (previously "spectral sandwich"); still heuristics.
6. Limitations: removed the "non-standard potential remains open" claim (the
   dynamic potential now exists) and the "P_T = o(T)" open problem; replaced by
   the five explicit certificate gaps above; retained "no sublinear-regret
   claim for unrestricted fine-tuning."
