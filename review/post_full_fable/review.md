# Review: "Confidence Transport for Relinearized Curvature in Contextual Bandits" — post-follow-up assessment

**Snapshots.** Manuscript: `origin/main` @ `6a9ea20c3f1bdd91738984160d707b808061aa1f`, entry `submissions/tmlr_2026/main.tex`. Implementation: `origin/cce-review-revisions` @ `739067b17f1f93b032263bf5fbada6d9910c4871`. I inspected sources and committed artifacts only; I could not execute code, rebuild the PDF, access `/workspace/cce-full-local` raw trajectories, or check external literature. The follow-up numbers below are reported, host-verified execution artifacts, not experiments I ran.

---

## A. Candid verdict and recommended direction

**Verdict.** The theorem (`transport_theory.tex:174–212`) is, as far as I verified, a correct but elementary composition of a Thompson-metric sandwich, an operator sandwich, and the standard elliptic-potential argument. By itself it is not an interesting enough contribution. The completed follow-up study is a clean, prespecified, well-executed **negative result**: in all three W conditions the certified transport policy loses to every comparator (all nine paired bootstrap CIs negative, `review/transport_review_followup/FULL_RESULTS.md:17–27`), its theorem bound is astronomically vacuous (mean RHS up to 8.1e83 against a cap of 1000, `FULL_RESULTS.md:41`), and even the regime with genuinely large realized drift (W=0.25, max endpoint distance 1.581, 16/50 seeds reaching distance 1) does not rescue it.

**The strongest honest contribution** is not the theorem and not the experiments separately; it is the *structural explanation that links them*, which the authors have in their hands but have never stated as mathematics:

> **Within this certificate family — confidence stated in the frozen metric — no transported width can ever be sharper than the frozen width.** By the sandwich, $\bar s_t(a) \le e^{d_{\rm Th}/2}s_t(a) \le e^{\bar D_t/2}\hat s_t(a)\sqrt{\kappa_{+,t}}$, pointwise in $a$, with equality attainable (`transport_theory.tex:334–357`, `prop:width-transport-new` at lines 420–438). Exact transport, at its sharpest, *reproduces* the frozen reference width; everything else only widens it. The certified transport policy is therefore exactly the naive-current policy with a per-round scalar inflation of its exploration coefficient (see §B), and when the analytic certificate is loose it degenerates toward width-only, information-blind selection. The experiments are the empirical face of this fact, not an accident of one environment.

My recommendation is **direction (A)**: a focused theory + negative-results/diagnostics paper, built around the theorem, a new "frozen width is the sharp limit" proposition, and the full prespecified study. This fits TMLR's criteria (supported claims, interest to the neural-bandit/certified-UCB audience) without needing benchmark wins. Direction (B) — a genuinely new certified algorithm whose confidence lives natively in current geometry — is real research with an unsolved proof obstacle (current features are not predictable) and should not gate this paper. Direction (C) — real-data/GPU benchmarks — is premature: benchmarking a policy you can already prove is never sharper than its own frozen baseline answers no open question.

I do not promise acceptance; a negative-results paper at TMLR must be unusually crisp about *what general lesson it teaches*. The lesson exists here. The current draft does not yet state it, and does not yet contain the follow-up results at all.

---

## B. Diagnosis: verified facts, exact implications, hypotheses

### B.1 Verified facts (artifacts and code)

1. **Scoring structure.** In `experiments/transport_instantiation.py:1590–1603`, all four methods share the *same* corrected centers, the same $\beta$, and the same additive `current_bias` (a scalar, identical across actions). They differ only in the width term:
   - `transport_hessian`: $\beta\,e^{d_Q/2}\,s_t(a)$ (line 1590–1592),
   - `transport_endpoint`: $\beta\,e^{d_{\rm Th}/2}\,s_t(a)$,
   - `frozen_reference`: $\beta\,\bar s_t(a)$,
   - `naive_current`: $\beta\,s_t(a)$.
   Crucially, $e^{d_Q/2}$ and $e^{d_{\rm Th}/2}$ are **round-level scalars applied uniformly to all actions**.
2. **Outcomes.** Means per `FULL_RESULTS.md:9–13`: Hessian transport 185.10 / 182.90 / 176.44 vs. comparators ≈ 151.8–173.2 at W=16/1/0.25. All nine paired 95% bootstrap intervals exclude zero (pointwise, unadjusted — correctly flagged at `FULL_RESULTS.md:29`).
3. **The smoking gun.** At W=16 the aggregate's own environment diagnostic gives context-free *mean-only* regret of **185.256 ± 0.52 (SE)** (`aggregate_compact.json → environment_diagnostics[0].context_free_mean_only_regret`), while the certified policy's mean regret is **185.10**. The certified policy performs essentially at the level of a policy that ignores contexts entirely. (This near-coincidence is suggestive, not a formal paired test; see §D.1.)
4. **Bound accounting.** `terminal_bound_decomposition.json[0]`: at W=16, path inflation 6.51e12 vs. statistical 1.02e4 and historical 2.68e4. In the new regime the bound is **path-dominated** — the opposite of the old study's base-dominance finding (`transport_experiment.tex:117–133`). The frozen policy's own-trajectory reference bound is also vacuous (means 3.76e4–2.31e5 vs. caps 2000/1000; `drift_and_reference_diagnostics.json`, `FULL_RESULTS.md:41`).
5. **Coverage.** All 600 trajectories, including the uncertified naive control, kept confidence and optimism (`FULL_RESULTS.md:43`). So the study provides **no empirical evidence that certification is ever needed** in this family at these drifts.
6. **Protocol hygiene.** Disjoint seed splits, tuning by prediction MSE independent of evaluation, single selected optimizer shared across methods (`selection.json: seed_sets_disjoint=true`, `selection_metric=mean_all_action_prediction_mse_after_burn_in`; `TRANSPORT_REVIEW_FOLLOWUP_PROTOCOL.md:56–81`), and a prespecified quadrature amendment made on development seeds only (lines 135–181). This is genuinely good practice.

### B.2 Exact implications of the implemented equations (derivations, not conjecture)

1. **Frozen width is the pointwise sharp limit.** The only confidence event available is $|\mu^*_t(a)-m_t(a)|\le\beta_t\bar s_t(a)+b_t(a)$ (`eq:abstract-confidence-new`). Any width $w_t(a)$ that guarantees optimism against this event alone must satisfy $w_t(a)\ge\bar s_t(a)$. The sandwich gives $\bar s_t^2(a)\le e^{d_{\rm Th}}s_t^2(a)$, so every transported width (endpoint or Hessian) dominates $\bar s_t(a)$, with equality attained in the worst direction (sharpness example, `transport_theory.tex:334–357`). **Corollary: the "exact transport" policy is at best the frozen-reference policy on the same state; the min of the two valid widths is identically the frozen width.** An "intersection of confidence information" fix therefore collapses to the frozen reference — this answers Q3's first clause definitively.
2. **The certified policy is inflated-β naive scoring.** Because $e^{d_Q/2}$ is action-independent, `transport_hessian` ranks actions by $m(a)+(\beta e^{d_Q/2})s(a)$: identical to `naive_current` with an exploration coefficient multiplied by $e^{d_Q/2}$. As $d_Q$ grows, selection converges to $\arg\max_a s_t(a)$ — pure width-chasing. With mean RHS of 6.5e12 at W=16 driven by $e^{d_Q}$ terms, per-round $e^{d_Q/2}$ must frequently be orders of magnitude above 1 even where realized drift is 0.045. Fact B.1(3) is exactly what this predicts.
3. **No bound advantage either.** The transported coefficient $1+\alpha_t e^{\bar D_t}\sqrt{\kappa_{+,t}/\kappa_{-,t}}\ge 2$ (`eq:instantaneous-transport-new`) equals the frozen policy's coefficient 2 (`prop:frozen-width-ucb`, lines 214–239) only when the certificate is trivial. So the transported guarantee is never better than the frozen guarantee *under identical premises* — while correctly noting (as the qualifications file insists, `source_review_qualifications.md:17`) that comparable upper bounds do not order realized regret of policies with different histories.

### B.3 Hypotheses (untested, labeled as such)

- **H1 (over-exploration mechanism dominates).** The regret gap is caused by width-dominated selection, not by center degradation. Supported by B.1(3) but not yet established by a fixed-history diagnostic (§D.1). It is *not* proven by the across-policy comparison, because histories diverge after the first disagreement.
- **H2 (naive ≈ endpoint ≈ frozen is drift-smallness).** At W=16 the three comparators differ by <1 regret unit, consistent with $e^{d_{\rm Th}/2}\approx 1$; at W=0.25 drift is material yet comparators still tie — consistent with β already being slack enough to absorb drift. Untested.
- **H3 (confounds are secondary).** Tuning was method-shared and prediction-based, bias radii and `current_bias` are action-constant (no ranking effect), and W changes the reward function itself (`FULL_RESULTS.md:29`), so across-W trends are descriptive. None of these plausibly reverses the within-cell orderings, but this is judgment, not proof.

---

## C. Candidate mathematical/algorithmic fixes

For each: proof obligation, extra information needed, cost, and honest value.

1. **"Sharp-limit" proposition (do this; essentially free).** Formalize B.2(1)–(3): within frozen-metric confidence, the minimal valid width is $\bar s_t(a)$; exact transport reproduces it; any strict improvement requires information beyond the frozen confidence event. Proof obligation: three lines from the existing sandwich plus the equality example. Value: converts the negative experiments into a theorem-backed structural finding, and answers the prior review's F5 in the corrected form the qualifications demanded (no realized-regret ordering claimed).
2. **Valid width fallback / intersection.** Scoring with $\min(\bar s_t(a), e^{\bar D_t/2}\hat s_t(a))$ is trivially valid (both certificates hold on the same event) — but by item 1 it *equals* the frozen reference whenever both are computable. Only worth a remark; do not present as an algorithmic contribution.
3. **Relative/excitation-attenuated transport certificates** (`lem:factor-spd-path`, `transport_theory.tex:359–378`, and the remark at 415–418 that the relative form "can be much sharper than the ridge-only bound"). Proof obligation: a computable per-round $\nu_t(\tau)$ with $\dot B^\top\dot B\preceq\nu_t^2 V(\tau)$ exploiting excitation, plus a certified way to evaluate/bound the integral (the current quadrature is a diagnostic, not an enclosure — do not promote it). Extra information: per-sample Jacobian motion against the *current* metric. Value: tighter $\bar D_t$, hence less over-exploration — but by item 1 the ceiling is still the frozen width. **Its only genuine use case is when $\bar s_t(a)$ is unavailable** (frozen Gram not stored, sketched, or distributed). Caveat the paper already makes: the corrected center itself needs frozen-feature access (`body_intro.tex:75–77`), so a memory story requires redesigning the center too. This is a real but modest research direction; scope it as future work.
4. **Action-dependent transport.** The exact directional factor is $\bar s_t(a)/s_t(a)$; computing it requires $\bar s_t(a)$ — circular. Any certified action-dependent surrogate again upper-bounds $\bar s_t(a)$. Derivation closes this door for the current design; say so in the paper.
5. **Confidence natively in current geometry (direction B).** E.g., online-to-confidence-set conversions or a self-normalized argument over predictable *paths* of features rather than fixed features. Proof obligation: a new concentration result, because $\nabla_\theta\mu_{\theta_t}(x_s,a_s)$ is not predictable at time $s$ — this is the very obstacle the paper starts from (`body_intro.tex:15–20`). High risk, genuinely novel if solved. Separate paper.
6. **Tighter statistical estimators** (empirical-Bernstein radii, data-dependent $\gamma$, smaller $S$). These attack the *base* component, which dominated the original study but not the new one (path-dominated, B.1(4)). Useful only for the old regime's narrative; scope accordingly.
7. **Do not:** clip exponents, cap $e^{\bar D_t}$ heuristically, or treat Gauss–Legendre path quadrature as an exact enclosure — the protocol itself forbids this (`TRANSPORT_REVIEW_FOLLOWUP_PROTOCOL.md:93–100`), correctly.

---

## D. Minimal decisive analyses/experiments (prioritized)

**D.1 Width-domination diagnostic from existing raw data (no rerun; highest value).**
Hypothesis (H1): certified selection is width-dominated. From retained raw trajectories at `/workspace/cce-full-local`, compute per round, on the *transport-hessian policy's own states*: (i) the realized inflation $e^{d_Q/2}$; (ii) whether the selected action equals $\arg\max_a s_t(a)$; (iii) whether it equals the action the naive/frozen scores would pick *on that same state* (fixed-history, one-step counterfactual — all four scores are already computed per round, `transport_instantiation.py:1598–1603`, and appear in per-round records at lines 2015–2016). Metrics: per-seed fractions, 50 per cell, with bootstrap CIs. Also a formal paired comparison of transport-hessian regret vs. the context-free mean-only benchmark. Cost: aggregation only (CPU-minutes). Stopping rule: one pass. Outcomes: if ≥~80–90% of rounds are width-argmax at W=16, H1 is established as a fixed-history mechanism (clearly labeled: *not* closed-loop performance); if the fraction is low, the over-exploration story is wrong and the paper must say the mechanism is unresolved.

**D.2 Certificate-slack localization (prior review's E3; existing data).**
Hypothesis: the $10^5$–$10^6$ slack decomposes into (a) Frobenius-over-rows vs. operator norm, (b) $\lambda I$ vs. $V(\tau)$ lower-bounding, (c) worst-case Hessian constant $L_g$ vs. realized curvature. Compute the relative-form $2\int\nu_t$ alongside $d_Q$ and the endpoint distance at the existing 100 checkpoints. Cost: diagnostic rerun or raw-data pass. Outcome that changes decisions: if (b)-type slack dominates and an excitation-aware bound would close most of the gap, fix #3 in §C becomes a credible follow-up; if the slack is intrinsic, write that and stop.

**D.3 Optimism-failure stress cell (small new run, new protocol, new seeds).**
Hypothesis: there exists a drift/misspecification level where the *naive* control loses optimism/coverage, demonstrating that certification has practical content. Design: one or two cells (e.g., W≤0.1 and/or `exact_realizability:false` with controlled $\epsilon_{\rm mis}$), four methods, shared streams, fresh seed partition (never the 30200–30249 evaluation seeds), 50 seeds, T=1000, exact Clopper–Pearson per cell, paired bootstrap for regret. Cost: comparable to the ~100-minute evaluation phase per cell on CPU (`FULL_RESULTS.md:45`). Go/no-go: if naive never fails even here, the honest conclusion is that this certificate family has no demonstrated practical necessity in this model class — a publishable, if stark, negative finding; if it fails, you finally have the positive counterpart that motivates certified widths.

**D.4 Only if pursuing direction B:** a relative-certificate policy (C.3) evaluated under a *new* prespecified protocol with independent seeds; go/no-go: certified width within 2× the frozen width at W=0.25. Never tune anything against the existing 50 evaluation seeds.

I deliberately do not propose real-data runs (direction C) now.

---

## E. Paper revision

**Titles (options).**
1. "Confidence Transport for Relinearized Curvature in Contextual Bandits: Validity Without Advantage"
2. "The Frozen Width Is the Sharp Limit: Certified Confidence Transport for Retrained Bandit Models"
3. "When Can Frozen Confidence Justify Current Curvature? A Transport Theorem and a Prespecified Negative Study"

**Contribution statements (rewrite `body_intro.tex:79–102`).**
(i) A conditional transported-UCB theorem separating frozen confidence, current metric, applied operator, and solver width (keep, novelty disclaimed as now). (ii) **New:** a sharp-limit proposition: under frozen-metric confidence, every valid transported width dominates the frozen width pointwise, so certified transport cannot out-explore-exploit the frozen-reference policy on common states, and its closed bound is never better. (iii) The corrected-center confidence without optimizer convergence (keep). (iv) Two controlled studies — the locked near-linear grid and the prespecified stronger-drift follow-up — showing: validity holds everywhere (including the uncertified control), bounds are vacuous everywhere, base-component-dominance in the near-linear regime but **path-dominance in the stronger-drift regime**, and uniformly worse mean regret for the certified policy, consistent with the inflated-β mechanism.

**Required integration of the follow-up (currently absent from LaTeX — the abstract at `main.tex:93–102`, `transport_experiment.tex:135–151`, and `body_conclusion.tex:31–43` still report only the old grid):**
- Add a subsection "A prespecified stronger-drift follow-up" with the W∈{16,1,0.25} table, the nine paired differences (explicitly pointwise/unadjusted), realized drift thresholds, the per-method terminal decomposition, and the frozen policy's own-trajectory vacuous bound. Note W changes the reward function; no causal drift claims; no policy-dominance inference from bounds (`FULL_RESULTS.md:29,41`).
- **Scope the base-dominance claim** ("base component accounts for 79.4–97.3%", `transport_experiment.tex:120`; echoed in the abstract at `main.tex:99–100` and conclusion at `body_conclusion.tex:39–41`) to the original near-linear grid, and state that the follow-up regime is path-dominated (6.5e12 path vs. 3.7e4 base at W=16).
- Delete or narrow: any residual implication that larger drift might favor transport; the abstract's old-study-only framing; keep the "no uniform ordering" language.
- Add the D.1 mechanism diagnostic if completed; otherwise state the inflated-β mechanism as an exact property of the score plus the mean-only coincidence as suggestive.

**Outline.** 1 Introduction (+ sharp-limit statement up front). 2 Setup and transported-UCB theorem. 3 Certificates (path/operator/solver) + **sharp-limit proposition** immediately after `prop:width-transport-new`. 4 Corrected center and rates. 5 Controlled studies: 5.1 locked grid, 5.2 prespecified follow-up, 5.3 mechanism diagnostics. 6 Related work. 7 Conclusion/limitations. Appendices: proofs, both protocols, legacy scope note (keep the exclusion fencing exactly as now, `body_intro.tex:103–111`).

**Revised abstract (~230 words).**

> Retraining a contextual-bandit model changes every replayed gradient feature, while sequential confidence rests on features frozen when rewards were collected. We study when frozen confidence can justify scores computed with current relinearized Gauss–Newton or Fisher curvature. A conditional transported-UCB theorem composes a Thompson–Finsler path certificate, a two-sided operator comparison, and a solver certificate, closing regret through frozen information gain; for squared loss, a corrected prediction center supplies the confidence event along any predictable parameter path without optimizer-convergence assumptions. We then prove a structural limit: under frozen-metric confidence, every validly transported width dominates the frozen width pointwise, so exact transport at best reproduces the direct frozen-width policy, and the certified score is the naive current-width score with a uniformly inflated exploration coefficient. Two controlled studies of a 29-parameter scaled-tanh model instantiate the theorem exactly. Across a locked near-linear grid and a prespecified stronger-drift follow-up (894 trajectories; realized endpoint Thompson distances up to 1.58), all declared confidence and optimism diagnostics pass — including an uncertified control — yet every numerical regret bound exceeds a deterministic cap, bound mass shifts from the base confidence term to path inflation as drift grows, and the certified policy records higher mean pseudo-regret than all comparators in every condition, approaching an information-blind baseline where the certificate is loosest. Certificate validity, bound tightness, and policy performance are three separate properties; this certificate family cannot supply the second or third.

---

## F. Ordered implementation roadmap

1. **Week 1:** Prove and insert the sharp-limit proposition (§C.1); integrate the follow-up results into LaTeX (§E); re-scope base-dominance; update abstract/conclusion. *Dependency: none.*
2. **Weeks 1–2:** Run D.1 (width-domination diagnostic) and D.2 (slack localization) on retained raw data. *Go/no-go:* if D.1 confirms width domination, keep the mechanism paragraph; else report the mechanism as open.
3. **Weeks 2–4 (optional but recommended before submission):** D.3 stress cell under a new versioned protocol. *Go/no-go:* naive optimism failure ⇒ add a "when certification matters" subsection; no failure ⇒ strengthen the limitation that practical necessity is undemonstrated.
4. **Release work:** fix the strict packager/TeX-tree issue, publish the portable export as supplement, document the missing historical raw data and the non-replayable roundwise audits (`REVIEW_RESPONSE.md:29, 59–65`). *Dependency for submission.*
5. **Separate research (not this paper):** relative-certificate policy (C.3/D.4); current-geometry confidence (C.5); real-data/GPU (C) only after one of those yields a candidate with a plausible advantage.

---

## G. Verification record

**Read in full:** `main.tex`, `body_intro.tex`, `transport_experiment.tex`, `body_conclusion.tex` (manuscript); `FULL_RESULTS.md`, `REVIEW_RESPONSE.md`, `source_review_qualifications.md`, `TRANSPORT_REVIEW_FOLLOWUP_PROTOCOL.md` (lines 1–200 of 232) (implementation). **Read in part:** `transport_theory.tex:1–600` (of 722; rates section tail and related/proofs files not line-verified this session), `transport_instantiation.py:1500–1630` and targeted searches, `source_review.md:1–120` (of 194). **Inspected JSON:** `aggregate_compact.json` (top level; `environment_diagnostics[0]`; `policy_outcomes[0]`), `terminal_bound_decomposition.json[0]`, `drift_and_reference_diagnostics.json[0]`, `selection.json` (top level). I did **not** verify the proofs in `transport_proofs.tex` line-by-line this session, did not inspect `seed_summaries.jsonl` per-seed, and did not re-derive the bootstrap. I critiqued rather than accepted the prior machine review: its F3 wrongly described the decomposition as absent (it exists at `transport_experiment.tex:117–133`), its F5 needed the realized-regret caveat the qualifications file supplies, and a key/year mismatch alone (pascanu) is not a bibliography error.

**Gaps and unresolved items:** (1) raw trajectories are outside Git; the portable export cannot replay roundwise audits or curve CIs, and the older study's raw data remains missing — the availability statement must say both. (2) `granziol2026hessian` (`references.bib:212`) and the Wen entry remain externally unverified (`REVIEW_RESPONSE.md:26`); verify before submission. (3) Positioning claims versus misspecified-linear-bandit and nonstationary/weighted-bandit literature (prior review §D.3) need a live literature check I could not perform. (4) The follow-up aggregate records `git_revision 707c8243` and `publication_ready=true` as pipeline lineage/status only; state this once in the paper. (5) The manifest's retained `KeyboardInterrupt` is a documented pause, final status complete (`FULL_RESULTS.md:45`) — disclose, don't hide.

**Conjectures explicitly labeled:** H1–H3 in §B.3; the "near information-blind" reading of the 185.10 vs. 185.26 coincidence pending D.1's formal paired test; the claim that excitation-aware certificates would materially tighten $\bar D_t$ (pending D.2).

---

### Three actions to take first

1. **Prove and add the sharp-limit proposition** (frozen width is the pointwise minimum valid width; exact transport reproduces it; the certified score is inflated-β naive scoring) immediately after `prop:width-transport-new` — it is a few lines and it is the paper's thesis.
2. **Integrate the full follow-up into the LaTeX** (results tables, drift diagnostics, per-method decomposition, frozen-policy own-bound), rescoping base-dominance to the original grid and labeling the new regime path-dominated.
3. **Run the width-domination diagnostic (D.1) on the retained raw data** before it is lost, so the mechanism paragraph rests on measured fixed-history evidence rather than on the (currently suggestive) mean-only coincidence.
