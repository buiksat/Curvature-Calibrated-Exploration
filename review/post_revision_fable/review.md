# Review: "Confidence Transport under Relinearization: Guarantees, Conservatism, and Policy Behavior" (TMLR revision)

**Snapshots reviewed.** manuscript `fb95a696863326345be0823de399937fcbdb8af8` (entry `submissions/tmlr_2026/main.tex`); implementation `5f00be1b537eef476150c3115822f00cd95461ae`. I read LaTeX sources and committed JSON/table artifacts only. I could not execute code, rebuild the PDF, access the ~3.7 GB external raw logs, or search the literature. Build facts (PDF SHA-256, byte-identical rebuild, 38 pages) are the authors' recorded claims, not checks I performed.

---

## A. Executive assessment and recommendation

This is now a coherent, honest **theory + prespecified-negative-study + diagnostics** paper. Its contribution is threefold: (i) a conditional transported-UCB theorem that cleanly separates the four obligations (frozen confidence → current metric → applied operator → solver width) and closes regret through the frozen information gain; (ii) an explicit structural limitation — the same-history reference-width floor (`prop:reference-width-floor`) — showing that within this certificate family transport can never beat the direct frozen width and at best reproduces it; and (iii) a 600-trajectory prespecified study in which the certified Hessian-transport policy loses to every comparator in every condition (all nine paired CIs negative), its bounds are path-inflation-vacuous, and an uncertified control passes every recorded optimism diagnostic. The new relative-weight/endpoint certificates (`cor:relative-endpoint-ucb`, `cor:tanh-relative-weights`) quantify, on fixed histories, how close a cheap horizon-independent endpoint certificate gets to the floor (asymmetric category overheads ≈0.28%/4.27%/12.68%), which usefully converts "the analytic path bound is loose" into "the looseness is almost entirely avoidable — and even then you gain nothing over the frozen width."

All central proofs I verified line-by-line are correct (Section D). The empirical claims match the committed artifacts I inspected to the reported precision. The writing is scrupulous to a fault: the paper's main residual weakness is not overclaiming but (1) a missing *positive* demonstration that the certificate family has any content at all — the naive uncertified score never fails in any experiment, and the paper never exhibits even an analytic instance where it would — and (2) caveat-saturated prose that buries the one crisp lesson.

**Recommendation: minor-to-moderate revise, then submit.** No new large experiments are needed. The two substantive conditions are: add the (essentially free) analytic example showing the naive current width is not upper-valid under the frozen confidence event, and compress/restructure the hedging so the width-floor lesson is the paper's visible spine. The incomplete anonymous supplement and the missing original-study raw data are release tasks, properly disclosed; they are not scientific defects, but the supplement must exist before submission.

---

## B. What the revision fixed vs. what remains

Assessed independently, then cross-checked against `review/post_full_fable/review.md` and `REVISION_PLAN`-era materials.

**Fixed (verified in sources):**
- The follow-up is fully integrated (`transport_followup.tex`, five generated tables with input SHA-256 headers matching `review/.../aggregate_compact.json` etc.); table values match the artifacts I inspected (e.g., mean 185.10060 → "185.10"; paired Δ −32.5072 → "−32.51"; asymmetric ratios 1.002783/1.042708/1.126764 → 1.0028/1.0427/1.1268).
- The width floor is now a theorem with a correct proof, an equality case, a correctly scoped limited-information necessity statement, and the scalar-endpoint counterexample (`transport_proofs.tex:99–127`).
- Base-dominance is explicitly scoped to the original grid; the follow-up is reported as path-dominated (`transport_followup.tex:79–87`, `transport_experiment.tex:123–140`).
- Per-seed mechanism variation (not just pooled fractions), all four behavior histories, the Decimal tie-sensitivity audit, and the fixed-history recommendation matrix are all present with correct dependence caveats (`transport_followup_appendix.tex`).
- Two unverifiable 2026 citations were removed from active text (confirmed: `granziol2026hessian` appears only in the inactive `appendix_deferred.tex`, which `main.tex` does not `\input`).
- The relative-weight certificate goes beyond the prior review's suggestion by including the asymmetric outward/return split and the endpoint-vs-path counterexample (`transport_proofs.tex:397–415`).

**Remains:**
1. **No demonstration that certification is ever needed.** Every policy including the uncertified control passes optimism in 750 total evaluated trajectories across both studies. The prior review's "optimism-failure stress cell" was not run, and no analytic substitute was added. This is the paper's biggest open scientific hole (see F).
2. **Narrowness**: one 29-parameter synthetic model, one fixed teacher (seed 1729), one horizon, dense exact operators only. Acknowledged, but still limits the general lesson to "this certificate family in this family of models."
3. **Caveat density and length**: ~17 pages before references with near-identical disclaimers repeated in abstract, intro, §follow-up, conclusion, and appendix (e.g., "does not order realized regret" appears ≥6 times).
4. **Timing evidence is too weak for a table-level presence** (36 states, parallel load, kernel-only), and the paper already concedes it establishes nothing end-to-end.
5. Unverified 2026 BibTeX records remain in `references.bib` (harmless if uncited, but should be pruned from the submission archive).

---

## C. Claim-to-evidence map and prioritized findings

**Claim map (spot-checked):**

| Claim (location) | Evidence | Status |
|---|---|---|
| Transported-UCB theorem (`transport_theory.tex:174–212`) | proof `transport_proofs.tex:12–82` | verified correct |
| Width floor + equality + necessity (`:241–265`) | proof `:99–127` | verified correct |
| Endpoint corollary (`:474–502`) | proof `:225–254` | verified correct |
| tanh relative weights (`:734–766`) | proof `:344–395` | verified correct |
| Corrected-center confidence (`:581–592`) | proof `:256–302` | verified correct |
| Mean regret / paired CIs (Table outcomes) | `aggregate_compact.json → policy_outcomes` | matches (sampled) |
| Asymmetric width ratios 1.0028/1.0427/1.1268 | `transport_relative_diagnostics/full/analysis.json → groups` + `IMPLEMENTATION_REPORT.md:73` | matches |
| Score implementation = theory score | `experiments/transport_instantiation.py:259–290` | matches (β·e^{D/2}·current width; frozen uses frozen width) |
| Drift/bounds table (max d_Th 1.581; RHS 8.12e83) | drift diagnostics JSON (not independently re-opened this session; consistent with prior artifact inspection record) | reported, plausible |

**Findings table:**

| # | Pri | Location | Finding | Consequence | Fix | Effort | Conf. |
|---|---|---|---|---|---|---|---|
| 1 | P1 | whole paper | No analytic or empirical instance where the uncertified naive score violates upper validity; certificate family has no demonstrated content | Reader cannot tell whether the negative result is about *this* certificate or about certification per se | Add a 2–3 line analytic example (extend the existing `diag(e^D,e^{-D})` example: pick μ* at the top of the frozen band in the excited direction, show `m+βs < μ* ≤ m+βs̄`), stating naive current width is not upper-valid in general | ~hours, zero compute | High |
| 2 | P1 | `transport_followup_appendix.tex:166–180` | 36-state kernel timings under parallel load motivate nothing the paper claims | Invites a scalability reading the authors disclaim | Reduce to one sentence or delete; keep in artifact | trivial | High |
| 3 | P1 | `references.bib:212,235` | Unverified `granziol2026hessian`, `wen2026revisiting` entries remain in the submission bib | Submission archive carries unverifiable records | Remove from the submitted `.bib` (they are uncited in active text) | trivial | High |
| 4 | P1 | `prop:reference-width-floor` discussion (`transport_theory.tex:267–273`) | Circularity of exact actionwise transport (computing `c_t(a)` requires `s̄_t(a)`) is implicit only | The "exact transport recovers the floor" reading can look like an algorithm | One sentence: "computing `c_t(a)` requires the reference width itself, so exact transport offers no computational shortcut" | trivial | High |
| 5 | P2 | `transport_followup.tex:43–53` | At W=16 the Hessian policy's mean regret (185.10) ≈ the environment's context-free mean-only benchmark (reported in the aggregate's environment diagnostics); the paper surfaces this only for the original study | The most interpretable severity statement is omitted | Add the follow-up's environment baselines (best-fixed-action, context-free) to the outcomes table or text, as descriptive context | small | Medium (I did not re-open that JSON field this session) |
| 6 | P2 | `body_related.tex` | No positioning against weighted/nonstationary linear bandits (discounted/weighted Gram, e.g., Russac et al.-style reweighting), despite the relative-weight certificate being a reweighted-Gram comparison | Possible missed-priority perception | Add a short unverified-flagged paragraph; verify refs before camera-ready | small | Medium (cannot browse) |
| 7 | P2 | `transport_followup.tex:17–22` | Fixed single teacher; W changes task and curvature jointly (acknowledged) | Lesson scope limited | If anything cheap is added: 5–10 extra teacher seeds at W=1 only (CPU-hours), hypothesis "ordering is teacher-stable" | ~1 CPU-day | High |
| 8 | P3 | throughout | Repeated caveats; deep theorem layering (1 assumption, 1 theorem, 2 props, 6 corollaries, 5 remarks before experiments) | Readability | See E | moderate | High |
| 9 | P3 | `transport_followup_appendix.tex:94–105` | Decimal audit paragraph is hard to parse ("already rounded coefficient", "0.629 ULP") | Confusion | Rewrite as 3 bullet facts | trivial | High |

No P0 findings: I found no demonstrated error in any active proof or any manuscript number contradicting a committed artifact.

---

## D. Detailed assessment

### D.1 Theory

Verified line-by-line (correct, with the noted scoping):

- **`lem:log-spd-path`** (`transport_proofs.tex:139–160`): the scalar quadratic-form derivative argument is valid; it correctly avoids differentiating matrix square roots; absolute continuity + compactness justify the a.e. bound and integration.
- **`lem:factor-spd-path`** (`:162–187`): `‖H‖≤1` from `H^⊤H = I − λV^{-1} ⪯ I` is right; the factor-2 bound and the relative-ν form follow. The caveat that weight paths add a `d/dτ√w_s(τ)` obligation (`transport_theory.tex:424–429`) is correctly stated.
- **`cor:hessian-path-new`**: Frobenius-over-rows bound is valid though intentionally loose (the empirically observed 10⁵–10⁶ conservatism is consistent with the `λI ⪯ V(τ)` and Frobenius steps; the paper says this).
- **`thm:transported-ucb`**: the chain s̄ ≤ e^{D/2}s ≤ e^{D/2}√κ₊ s_C ≤ … and the return chain via α, κ₋, e^{D/2} are correct; the elliptic-potential step `x ≤ (1+M)log(1+x)` is standard and correctly instantiated; the "same realized width map" discipline (`:57–59`, Remark at `transport_theory.tex:141–150`) is a genuinely careful touch. The measurability assumptions are honestly flagged as substantive (`transport_theory.tex:28–35`).
- **`prop:reference-width-floor`**: correct, including the β_t=0 edge case and the zero-query convention; the necessity statement is properly limited to the full-interval uncertainty set, and the scalar-endpoint counterexample is right (q=(0,1), corrected width e^D > 1 = s̄).
- **`cor:relative-endpoint-ucb`**: correct; the distinction that max{−log c₋, log c₊} bounds the *endpoint* Thompson distance but not the synthetic path length is proved by the explicit sech⁴ example (`transport_proofs.tex:397–415`), which I checked (V(τ) rises and falls, path length `2log((λ+σ⁻²)/(λ+σ⁻²ℓ²)) > 0`, endpoints equal).
- **`cor:tanh-relative-weights`**: the weight-ratio sandwich ℓ² ≤ ω̃²/ω² ≤ ℓ⁻², the ridge-inclusion via the {min,max}∪{1} construction, the f_{t,c}>0 guarantee from ω_s ≥ ℓ > 0, the empty-history case, and the weighted-average tightness claim are all correct. The honest note that category factors need not be spectrally tight under linear dependence is appreciated.
- **`cor:corrected-center-new`**: the pseudo-response algebra, predictability of β_t^corr (uses γ_{t−1}), post-action/pre-reward noise conditioning (`eq:new-noise-condition`), the `Φ^⊤V̄⁻¹Φ ⪯ I` bias bound, and the exact center identity are all correct. The 1/σ (not 1/σ²) scaling remark is correct and useful.
- **Solver certificates** (`lem:inverse-quadratic-certificate-new`, `cor:cg-interface-new`): identities verified; the L≤0 failure mode and the float-vs-enclosure distinction are correctly handled.

Not inspected: `appendix_rates.tex`, `appendix_onesided_proof.tex`, `appendix_twosided.tex`, `appendix_cg.tex`, `appendix_expfam.tex`, `appendix_ggn.tex` — these are **not** `\input` by `main.tex` and are therefore inactive; likewise `appendix_deferred.tex` and `legacy_dynamic.tex`. I confirmed the active input list (`main.tex:106–127`).

**Assessment of novelty.** The geometry (Thompson/Finsler), the sandwich-to-regret reduction, and the misspecified-linear ingredients are standard, and the paper says so with unusual discipline (`body_related.tex:16–37`, Scope paragraph `transport_theory.tex:831–838`). What is plausibly distinctive is the *organization*: the four-interface decomposition with the one-realized-width-map discipline, the corrected center that removes optimizer-convergence assumptions, the width-floor necessity statement, and the endpoint-vs-path distinction with a concrete counterexample. The relative certificate materially improves the paper not as an algorithm (it cannot beat the floor, and the paper says it doesn't) but as the quantitative explanation of *where* the Hessian certificate's 10⁵–10⁶ slack lives. I cannot verify priority for the width floor or the relative-weight sandwich against the literature; both are elementary enough that a brief search for weighted-Gram comparisons in nonstationary bandits is warranted (Finding 6).

### D.2 Experiments and implementation

- **Implementation matches theory.** `policy_scores` (`transport_instantiation.py:259–290`) implements exactly the four scores with shared corrected centers, shared β, action-constant bias; transported widths are round-level scalar inflations of the *current* width, consistent with `eq:transported-score-new` with Ĉ=V, α=1, κ=1. The confidence radius (`:234–256`) matches `eq:beta-corrected-new`.
- **Protocol hygiene is good**: disjoint teacher/dev/tuning/eval seed sets (`transport_followup_appendix.tex:6–7`), shared optimizer selected on uniform-random histories by prediction MSE (config `tuning` block), prespecified quadrature freeze on development only, paired bootstrap with recorded seed. Tuning by prediction MSE is method-neutral but, as the paper notes, not per-policy regret-optimal; since all four policies share the representation machinery, this is acceptable for the comparison made.
- **Interpretation is careful and correct**: pointwise unadjusted CIs flagged (harmless given |Δ| ≳ 10–60× the CI half-width at W=16 and 1); W-as-task-change flagged; width-dominance fractions flagged as dependent rounds with per-seed variation given; fixed-history recommendations correctly not called counterfactual policy regret; mean-of-ratios flagged.
- **Residual weaknesses**: single teacher; the mechanism table shows width-argmax ≈ 99–100% for *all* policies, so "width-dominated selection" is a property of the whole β-scale regime, not specifically of Hessian inflation — the paper's text (`transport_followup.tex:100–113`) could state this more plainly (what distinguishes Hessian is *which* action has max width under current-width × scalar inflation, which equals naive's argmax ~99.4–99.98% of rounds; the regret gap therefore traces to the inflated-β trajectory divergence, a point the paper leaves slightly diffuse).
- **The relative audit** is a fixed-action optimizer replay, not new adaptive runs — correctly labeled; the 434 s / 600k rounds / 3,005-file hash inventory is documented (`analysis.json` top level). The Decimal audit's scope (stored-input re-evaluation, 65/600,000 flips at rounds 2–10, ≤0.629 ULP) is correctly bounded.
- **Timing**: correctly caveated but not worth manuscript space (Finding 2).

### D.3 Related work

Well-scoped and refreshingly non-defensive. The NeuralUCB/NeuralTS "no replay in the stated algorithm" claim is supported by the publisher-source check (`LITERATURE_CHECK.md:52`). Missing: weighted/discounted-Gram nonstationary linear bandits (closest formal relatives of `cor:tanh-relative-weights`), and perhaps online-to-confidence-set conversions as the natural "direction B" pointer. I could not verify any literature externally.

---

## E. Writing and organization

**Structural diagnosis.** The paper's spine is: *theorem (validity) → floor (no advantage) → study (cost) → relative certificate (slack is avoidable, floor still binds)*. That spine is present but obscured by (a) six+ repetitions of the same three caveats, (b) a long interface preamble before any result, and (c) the floor appearing as a proposition sandwiched between the theorem and a measurability corollary.

**Concrete reorganization (saves ~1.5–2 pages):**
1. Promote `prop:reference-width-floor` to a titled subsection "What transport cannot add" immediately after the theorem; move `cor:finite-enumeration-new` to the appendix.
2. Merge the three scope paragraphs (`body_intro.tex:112–127`, `transport_followup.tex:48–53`, conclusion `:40–62`) into one "Scope and non-claims" box stated once, cross-referenced elsewhere.
3. Collapse Remarks "Thompson distance and selected-path length" and "Sharpness of the symmetric exponential factors" into one remark; the sharpness example is also reused in the floor proof.
4. Drop the timing sentence block; move the Decimal audit to three bullets.
5. Keep Table `tab:transport-comparison-new` (good) but delete the assumption-ledger table (`tab:transport-assumption-ledger`) — its content duplicates the assumption statement.

**Replacement abstract (no strengthened claims, ~165 words):**

> Retraining a contextual-bandit model changes the gradient features used by current curvature, while sequential confidence is built from features frozen at collection time. We give a conditional UCB theorem that transports frozen confidence to current relinearized curvature through three explicit certificates — a metric path or endpoint comparison, a two-sided operator comparison, and a solver width certificate — and closes regret through the frozen information gain. For squared loss, a corrected prediction center supplies the confidence event along any predictable parameter path, without optimizer-convergence assumptions. The construction has an elementary limit: on the same history, any certified transported width is at least the direct reference width, which exact transport merely reproduces; this does not order the realized regret of policies with different histories. In a prespecified 600-trajectory study of a 29-parameter scaled-tanh model, the certified Hessian-transport policy has higher mean pseudo-regret than every comparator in all three conditions (nine negative paired intervals), its bounds are path-inflation vacuous, and an uncertified control passes all recorded optimism diagnostics. A horizon-independent relative-weight certificate removes most, but not all, of the avoidable inflation.

**Exact before/after edits:**
- `body_intro.tex:33–36`: "A completed controlled study motivates the distinction: the evaluated Hessian-transport policy has higher mean regret…" → "In our controlled study (Section 5), the evaluated Hessian-transport policy has higher mean regret than each comparator in every condition, even though every policy — including an uncertified control — passes the recorded optimism diagnostics; Section 3 explains why no outcome in the other direction was available to the certificate."
- `transport_followup.tex:100–106`: replace the two pooled percentages + strict-condition percentages with one sentence each plus a pointer to the per-seed table; currently four numbers are given twice (here and appendix `:87–90`).
- `transport_theory.tex:267–273` (floor discussion): append "Note that computing the exact actionwise multiplier requires the reference width itself, so exact transport provides no computational shortcut over direct reference scoring."
- `transport_followup_appendix.tex:95–99`: "A separate 250-digit decimal calculation … already rounded coefficient $B_t$" → "A 250-digit decimal re-evaluation of the final score expression (from stored binary64 inputs, including the already-rounded coefficient $B_t$) changes the recommended action at 65 of 600,000 states, all in rounds 2–10, with score differences below 0.63 binary64 ULP; upstream solves are not recomputed."

---

## F. Next steps and stop/go on experiments

**Stop/go verdict: agree with the authors' stop decision on large adaptive studies.** Another adaptive run approaching the frozen score answers no open question — the floor already proves the ceiling. Ranked additions:

1. **Analytic naive-invalidity example (essential; zero compute).** Hypothesis: the naive current-width score is not upper-valid under the frozen confidence event. Design: the existing 2-d sharpness example with μ* placed at the frozen band's upper endpoint in the drift-shrunk direction; show `m+βs < μ*`. Positive outcome: certificate family has provable content; there is no negative outcome (it is a construction). This single addition converts "certification was never needed in our runs" into "certification is needed in principle; our runs never entered that regime," which is the correct general lesson.
2. **One misspecification/optimism stress cell (recommended, not essential; ~CPU-hours–day).** Hypothesis: with `exact_realizability:false` and a controlled ε_mis (or W≲0.1), the naive control loses recorded optimism on some seeds while certified policies retain it. Design: 1–2 cells, 4 policies, 50 fresh seeds (never 30200–30249), T=1000, Clopper–Pearson per cell, paired bootstrap. Informative either way: failure of naive gives the positive counterpart; no failure sharpens the "no demonstrated practical necessity" limitation. Runs locally on CPU; the A100 server is irrelevant.
3. **Teacher robustness mini-ablation (optional; ~1 CPU-day).** 5–10 teacher seeds at W=1 only; hypothesis: sign of all three paired Δs is teacher-stable. Negative outcome (sign flips) would force a scope reduction — which is exactly why it is worth running.
4. **Not recommended:** real-data/GPU benchmarks, CG/approximate-operator evaluation, or any attempt to tune the Hessian policy to parity — all answer questions the paper correctly does not pose.

If (1) is added and (2) declined, the decline should be stated as an explicit limitation with the stress-cell design sketched, so reviewers see it was a decision, not an oversight.

---

## G. Verification record

**Read in full (manuscript):** `main.tex`, `body_intro.tex`, `transport_theory.tex` (all 838 lines over three chunks), `transport_proofs.tex` (all 572 lines over two chunks), `transport_followup.tex`, `transport_followup_appendix.tex`, `transport_experiment.tex`, `body_related.tex`, `body_conclusion.tex`, `availability.tex`, `REVISION_STATUS.md`, all five `tables/transport_followup_*.tex`.
**Read in part (implementation):** `experiments/transport_instantiation.py:200–360` plus targeted search (score/inflation code paths); `experiments/configs/transport_review_followup.yaml:1–120`; `review/post_full_revision/LITERATURE_CHECK.md` (all 66 lines); `review/post_full_revision/IMPLEMENTATION_REPORT.md:1–80`; `review/post_full_fable/review.md:1–130` (consulted after forming my own judgment).
**Inspected JSON:** `aggregate_compact.json` (top level; `policy_outcomes[0]`, `[0].cumulative_pseudo_regret`, `[1].paired_difference…`); `transport_relative_diagnostics/full/analysis.json` (top level; `groups[0]`).
**Not inspected / not verifiable:** `transport_experiment_appendix.tex`, `appendix_protocol.tex`, `notation.tex`, `macros.tex`, inactive legacy appendices; `run_transport_instantiation_study.py`, `tools/analyze_relative_transport.py`, `tools/make_transport_followup_paper.py` source, `transport_followup_provenance.json`, `per_seed.jsonl`, `FULL_RESULTS.md`, `TRANSPORT_REVIEW_FOLLOWUP_PROTOCOL.md`, `REVISION_VALIDATION.md`, `QUALIFICATIONS.md`, drift/decomposition JSONs (follow-up numbers for the drift table and 8.12e83 RHS are taken from the generated table + consistency with prior recorded artifacts, not re-derived); the compiled PDF; test-suite results (624/45, 565/4 ledger) are author declarations; external literature and venue policy; the 3.7 GB raw logs and missing original-study trajectories. I verified a *sample* of table numbers against artifacts, not all of them, and I verified the proofs listed in D.1 but no inactive-appendix mathematics.

---

## Five highest-value changes per unit effort

1. **Add the analytic naive-invalidity example** (one remark; proves the certificate family has content — the one scientific gap).
2. **Consolidate the repeated caveats into a single "Scope and non-claims" statement**, promoting the width floor to a titled subsection (clarity, ~2 pages saved).
3. **Delete/demote the 36-state timing results and the assumption-ledger table**; move the Decimal audit to three bullets.
4. **Prune the two unverified 2026 entries from the submitted `references.bib`** and add a short, flagged positioning paragraph on weighted/nonstationary-Gram linear bandits.
5. **Make the circularity of exact actionwise transport and the "all policies are width-dominated; Hessian ≈ inflated-β naive" mechanism statement explicit** in one or two sentences each — both facts are already in the authors' hands and sharpen the paper's lesson without any new computation.
