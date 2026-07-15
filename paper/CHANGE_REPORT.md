# Change Report — CC-UCB manuscript revision (14-point pass)

Target file: `paper/main.tex` (the repo file whose contents match the described
`main(14).tex`; no file literally named `main(14).tex` exists here). Shared
notation edited in `paper/macros.tex`. Timestamped backups created before editing:
`paper/main.tex.bak-20260714-164704`, `paper/macros.tex.bak-20260714-164704`.
No Git init/commit/push performed.

## 1. Mathematical corrections

- **Filtration (§1).** Rebuilt as a consistent construction: `Omega_t` = pre-action
  randomness only; `U_{t+1}` = post-reward randomness for `theta_{t+1}`;
  `H_t = F_{t-1} ∨ σ(x_t,A_t,Omega_t)`, `F_t = F_{t-1} ∨ σ(x_t,A_t,Omega_t,a_t,r_t,U_{t+1})`,
  so `theta_{t+1}` is `F_t`-measurable (the old text wrongly put `U_{t+1}` in
  `Omega_{t+1}`). Stated `a_t` is `H_t`-measurable (deterministic argmax with a
  fixed tie-break) hence `G_t = H_t`. Deleted the "determined before `a_t`" phrasing.
  Added: the randomized sketch/subsample is fixed before action selection and
  constant across all CG iterations that round (standard CG needs a fixed oracle).
- **Generic-curvature alignment (§2).** Method now defines the generic width
  `s_{C,t}^2(a)=g^T C_t^{-1} g` first; exact case `C_t`; replay/subsample/window/
  refresh/sketch as special cases. Algorithm 1 "forms or receives" a fixed
  `H_t`-measurable SPD oracle `v ↦ C_t v ⪰ λI`, with the weighted replayed-Jacobian
  demoted to a comment. The closed-form condition number `1+W_t G²/(λσ²)` is now
  restricted to nonnegative weighted outer-product operators everywhere the residual
  stopping rule appears (method intro, tolerance paragraph, `lem:cg`, `app:cg`);
  a general SPD operator requires a separately certified `κ̄_t`.
- **Per-action CG error (§3).** Introduced `ε_{t,a}` (per action); the enforced
  tolerance is `max_a ε_{t,a} ≤ ε̄_t < 1`. Updated `lem:cg`, Algorithm 1, `lem:bonus`,
  `thm:regret`, `cor:lam-observable`, `cor:gammahat`, `app:cg`, and all prose. The
  regret argument uses `ε_{t,a_t} ≤ ε̄_t` for the played action. Zero-gradient case
  handled: `g_t(a)=0 ⇒ s̃_t²(a)=0`, CG skipped, residual ratio undefined, and
  `ε_{t,a}:=0` by convention (so the uniform max is well-defined over all actions —
  fix from adversarial verification).
- **Dynamic potential (§4).** `I+Ξ_t` SPD is now stated as "eigenvalues of `Ξ_t`
  exceed −1, eigenvalues of `I+Ξ_t` positive." `C_{T+1}` fixed as an end-of-round-T,
  `F_T`-measurable terminal operator (not a function of `x_{T+1}`, `A_{T+1}`, future
  rewards; canonical choice `C_T^+`), so the identity is a-posteriori; `Ξ_T,V_T,Γ_T^dyn`
  are defined relative to that choice and `Λ_T ≤ Γ_T^dyn` holds for every valid choice
  (fix from adversarial verification). Removed all "equivalent"/"equivalently the
  variation" equating `Λ_T/Γ_T/V_T`; now states explicitly that `V_T` alone does not
  control `Λ_T/Γ_T` — the endpoint `log det(C_{T+1}/λI)` term also matters.
- **Legacy two-sided corollary (`cor:twosided`, §7).** Rewritten with a direct proof
  (variance sandwich → per-round regret → frozen-feature elliptic potential on `s̄_t`
  → inflation), not by substituting `ŝ_t` into the dynamic corollary. Uses
  `ω_max,T = max_t(β̄_t+ψ̄_t)` (not `β̄_max`) and `u_t = max{1,ρ_{+,t}}`. Displayed
  inflation is `√(ρ_+*/ρ_-)` with `ρ_+* := max{1,ρ_+}`, reducing to `√(ρ_+/ρ_-)`
  under the standard normalization `ρ_+ ≥ 1` (fix from adversarial verification: the
  bare `√(ρ_+/ρ_-)` is too optimistic when `ρ_+ < 1`).
- **`lem:primitive-pred` proof (§8).** Removed the stale "which proves the first
  bound. The second follows from…"; the proof now derives the geometric inequality,
  the certificate `ψ̄_t = (ζ_t+‖M_t‖₂)/√λ`, and the Lipschitz bound on `‖M_t‖₂`.

## 2. Theorem assumptions / statement changes

- **Probability (§5).** `thm:regret` now defines a single certificate event
  `E_cert` containing every non-deterministic guarantee (`F̄_t/β̄_t`, `ψ̄_t`, `u_t`,
  `χ̄_t/κ_{+,t}`, `κ̄_t` and CG tolerances, sketch/subsample spectral); with
  `E_conf ≥ 1−δ` and `E_cert ≥ 1−δ_cert`, the guarantee holds with prob
  `≥ 1−δ−δ_cert`; deterministic/a.s. certificates contribute 0.
- **`asm:optim` / centering** unchanged in role but the corrected-center path is now
  cleanly separated (see §9 below).
- **Sublinearity condition (§6).** Corrected to `Λ_T S_T = o(T²)` (equivalently
  `Λ_T = o(T²/S_T)`), `S_T := Σ_t α_t² u_t(a_t) ω_t²`, in both the discussion and
  Limitations item 4 (was the incorrect `o(T/S_T)`).
- **Wording (§6).** "exact dynamic bound" → "realized-complexity bound"; "strictly
  looser" → "weakly looser (no tighter, equality when per-round factors are constant)";
  the `√(σ²+G²/λ)` factor now attributed to the dynamic width-sum lemma, not an
  "elliptic-potential step"; "no √T is introduced" → "no horizon maximum before
  Cauchy–Schwarz; usual √T recovered when per-round factors are uniformly bounded."

## 3. Claim corrections

- **Empirical (§10).** `+3.5 → +3.1` (the full−Lanczos range in `tab:constructed` is
  +3.1 to +5.4) in abstract, intro, contributions, results, conclusion. Removed
  "never the worst method" everywhere; replaced by the actual reading of Table 3:
  full beats diagonal only at 7.5° and 15°, loses to both surrogates at 0° and 45°,
  loses to Lanczos at all four. De-identified the scalar-vs-geometry attribution
  everywhere ("separates/identifies scalar", "scalar, not geometric", "via metric
  geometry rather than scalar calibration") → "does not identify a unique mechanism;
  consistent with scale/damping/path/selection effects." Renamed "External validity
  on UCI covertype" → "UCI Covertype case study"; removed "corroborated / robust
  reference / external validity / not an artifact / top-line finding is robust."
  Matched-coverage now described as a retrospective oracle diagnostic whose
  per-method λ/α selection + isotonic interpolation + CIs would need independent
  tuning/eval data for formal inference. "invert the monotone curve" → isotonic
  projection with monotonicity imposed, not guaranteed (coverage is not
  auto-monotone in α for an adaptive bandit). Committed table numbers unchanged.
- **Novelty/systems (§12).** No longer implies prior neural bandits uniformly replace
  the full metric; acknowledges NeuralUCB's analyzed algorithm uses the full
  neural-gradient Gram; states the narrower contribution (current-parameter
  relinearized GGN reference operator; matrix-free inverse-vector via CG; separation
  of frozen confidence vs algorithmic curvature; conditional transfer for
  CG/centering/drift/operator changes). Removed the ~0.5 ms/CVP-on-A100 and ~32 s/round
  estimate (unbenchmarked; a Hessian-vector timing from another paper is not the
  per-example GGN JVP/VJP used here) — only an operation count remains. Replaced the
  `Ω(ε√d T)` misspecification claim with neutral wording (additive term linear in the
  cumulative approximation error).
- **Corrected center (§9).** Dropped the categorical "not matrix-free"; now states it
  is incompatible with the `O(d)`-memory / no-stored-feature design unless a
  frozen-feature oracle / replay / low-dim representation / certified sketch is
  supplied; is computable by a matrix-free iterative solve given frozen-feature
  access; a sketch error returns to `ψ̄_t`. Conclusion separates the original center
  (`ω_t = β̄_t + ψ̄_t`) from the corrected center (`ω_t = β̄_t`, `asm:optim` absent);
  no formula uses the corrected center with a nonzero `ψ̄_t`.

## 4. Anonymity / internal-material cleanup (§13)

- Deleted the author-comment macros `\diego,\bahram,\houssam,\brett` and the entire
  `\ifcomments` block; deleted `\iffinalresults`/`\finalresultsfalse`/`\resultTBD`;
  deleted unused stale macros `\epsdrift,\epsdriftbar,\Eopt` from `macros.tex`.
- Deleted the commented internal TODO figure block ("post Stage 2", "committed gate
  data", "uncomment", draft caption with "scalar, not geometric").
- `\author{Anonymous Author(s)}`, neutral title, no `\thanks`, acknowledgments,
  `\href`, file paths, or usernames in the submission files. Only `\input{macros}`.
- **Self-citation:** `granziol2026hessian` (references.bib) is authored by
  "Granziol, Diego and Juarev, Khurshid", matching the deleted comment macros — a
  concurrent self-citation. All four uses are third-person `\citep`. Per NeurIPS
  double-blind policy (cite own work in third person; do not anonymize the
  bibliography), the entry is KEPT unchanged. **Authors must confirm this complies
  with the venue's dual-submission/self-citation policy at submission time.**

## 5. Compilation status

**Not compiled — no LaTeX toolchain and no network in this environment.**
`pdflatex/xelatex/lualatex/latexmk/tectonic` are all absent; `dnf` has no base
env / no root; `conda` has no base env; `pip3` is administratively blocked; DNS
resolution fails (no outbound network). A PDF cannot be produced here.

Substitute static validation (`paper/validate.py`, re-runnable) passes:
- Braces net-balanced; `$` parity even (3010); `\left`/`\right` balanced (10/10);
  all 18 environments balanced; `algorithmic` control flow balanced (IF 1/1, FOR 2/2).
- 108 `\label`s, **0 duplicates**; 84 distinct `\ref/\Cref/\eqref` targets, **0 unresolved**.
- 29 distinct `\cite` keys, **0 missing** from `references.bib`.
- **0** uses of any deleted macro.
- Stale-token sweep clean: `η^pred`, `α_drift`, `β_max`, `never the worst`, `+3.5`,
  `scalar, not geometric`, `separates scalar`, `external validity`, `not an artifact`,
  `equivalently the variation`, `observable via`, `non-standard potential`,
  `strictly looser`, `no √T is introduced`, `elliptic-potential step`, `asm:drift`,
  `lem:drift-sufficient` → all 0. `P_T` remains only in the two sentences that state
  it was removed (historical, correct).

To compile once a TeX distribution is available:
```
latexmk -pdf -interaction=nonstopmode -halt-on-error paper/main.tex
# or: make pdf   (uses paper/Makefile: pdflatex → bibtex → pdflatex ×2)
```

## 6. Adversarial verification

An 11-agent verification workflow (8 requirement auditors + 3 math adversaries)
audited the final file. All 8 requirement groups returned PASS except one PARTIAL
(a lingering "external-validity check" phrase), now fixed. The math adversaries
confirmed the CG chain, dynamic-potential algebra, legacy-corollary proof, and
filtration/measurability are correct, and surfaced four precision items — all now
fixed: (a) `max_a ε_{t,a}` well-definedness under zero gradients; (b) the
`ρ_+ ≥ 1` normalization in `cor:twosided` (now `√(ρ_+*/ρ_-)`); (c) `Γ_T^dyn`
defined relative to a chosen terminal operator; (d) argmax tie-break for `a_t`
measurability. One minor pre-existing symbol overload (`ε_t` used for the legacy
drift tolerance and the ε-greedy probability) was clarified by renaming the
ε-greedy probability to `ε^eg_t`.
