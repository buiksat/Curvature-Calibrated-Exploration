#!/usr/bin/env python3
r"""Pinned semantic units for every declared numeric occurrence in the submission.

GENERATED DATA.  Produced by `tools/verify_tmlr_submission_numbers.py
--regenerate-pins` from the frozen manuscript sources, and committed so that the
audit compares against a fixed, reviewed record rather than against whatever the
sources currently say.  Do not hand-edit: regenerate, and read the diff.

What a pin binds
----------------
Each key is `(repository path, literal-or-phrase)`.  Each value carries the
exact number of occurrences allowed in that file and, for each occurrence in
document order, the **complete normalized semantic unit** it sits in together
with its offset inside that unit.

A unit is the whole thing a reader would call one statement: a paragraph, a
table row or cell, a list item, a caption, a heading, or an equation
environment.  Boundaries come from the source itself -- a blank line, `\\`, an
unescaped `&`, `\item`, a sectioning command, `\begin`/`\end`, `\caption`, a
booktabs rule -- not from a character count.

Why not a fixed radius
----------------------
The previous record pinned forty characters on each side of the number.  That
cannot see a meaning-changing edit past its own edge: "the median is 126.7" and
"the median is 126.7, for the discarded pilot run" are identical inside the
window and say different things.  A unit has no edge to hide behind.  Every way
of getting it wrong -- moved, reworded, duplicated, missing, one more, or a
qualification added anywhere in the same sentence -- is a mismatch.

`FILE_PINS` adds a whole-file binding on top: a digest over the entire
normalized auditable text of each audited source, which catches a
meaning-changing edit in a part of the file that holds no pinned number.  It is
an addition, not a replacement -- a file digest says only "something changed",
and the units say what.

This record is not self-authorizing.  The module ships with the supplement
because the shipped ledger reads it, so its own SHA-256 is pinned in
`tools/anonymous_package_contract.py` and recorded again in the internal
`release_manifest.json`; the ledger checks that binding before it consults a
single pin.  Editing a manuscript source and regenerating its pin inside an
unpacked supplement therefore does not authorize itself.

`tools/verify_tmlr_submission_numbers.py --print-contexts` prints every unit in
full, with each category's rationale.

This module carries no repository, host or author information.

Layout
------
`UNITS` holds every distinct unit once; the pin tables cite them by index
through `_u`.  The same paragraph is the unit of a dozen different numbers, so
writing each one out per pin cost 1.6 MB of duplicated prose and made the
record harder to read, not easier.
"""

from __future__ import annotations

#: Every distinct semantic unit, once, sorted.
UNITS: tuple[str, ...] = (
    '$(1+\\chi_t)/(1-\\chi_t)$',
    '$1$',
    '$\\chi_t<1$',
    '$\\kappa_->0$',
    ', \\] so $\\mathcal D(\\bV)=d_{\\rm Th}(\\bVbar,\\bV)=D$. For $q_1=e_1$, $\\bar s(q_1)=1$ and $s(q_1)=e^{-D/2}$, so $\\bar s=e^{D/2}s$ is attained. For $q_2=e_2$, $s(q_2)=e^{D/2}$ and $\\bar s(q_2)=1$, so $s=e^{D/2}\\bar s$ is attained. Thus each one-way factor is sharp, and a uniform argument based only on the symmetric Thompson-distance bound cannot improve the resulting round-trip factor $e^D$. This is a metric-factor sharpness statement, not a contextual-bandit regret lower bound and not a claim that every trajectory attains the worst case.',
    '- **Numerical-provenance ledger:** derives every declared empirical literal from its pinned source, including the follow-up summaries, and checks its source context and display rounding. Every other numeric literal in the active compiled sources must have an explicit classification. Added or relocated numerical claims are rejected. - **Historical artifact regeneration:** regenerates all 21 published tables, figures and CSVs from the packaged historical aggregate and requires byte equality with the pinned artifacts. - **Follow-up terminal interval reconstruction:** independently resamples the complete per-seed evaluation summaries, verifies the configuration and selection bindings, and reconstructs all reported terminal intervals. The export manifest must describe exactly the files in its directory. - **Follow-up table regeneration:** regenerates the manuscript tables from the packaged summaries and fixed-history outputs, verifies the original-source attribution, and requires exact artifact bytes. - **Evidence coverage:** scans the actual evidence directories. Each file must have a valid checksum sidecar or an exact, independently checked contract pin. An added file without coverage is a failure. - **Study tests:** runs the shipped scientific algebra, seed, aggregation, artifact and follow-up configuration tests.',
    "- The historical controlled audit covers 2,400 trajectories, but its raw trajectories and original per-seed bootstrap inputs are absent. Its recorded bootstrap intervals therefore cannot be independently reconstructed here. The ledger reports that limitation as `NOT EXECUTED`. - The nonlinear follow-up's per-seed summaries are included, so its terminal intervals **are** independently reconstructed. Its raw trajectories are not included. Their recorded hashes are checkable provenance metadata; the underlying raw bytes, roundwise fixed-history scans and optimizer replay are not verified by this archive. No synthetic raw inputs replace them. - The raw follow-up archive is retained separately. This package does not assert a durable external download location or that a reviewer has received it. Analysis scripts are included for inspection and later replay with those original inputs and their recorded runtime. Running new adaptive experiments is a separate task and is not performed by `verify.sh`.",
    '0',
    '1,',
    ':=\\int_0^1\\!\\left\\| \\bV_t(\\tau)^{-1/2}\\dot\\bV_t(\\tau)\\bV_t(\\tau)^{-1/2} \\right\\|_{\\rm op}d\\tau',
    '=(1-m)\\lambda\\bI+\\sigma^{-2}\\sum_c(g_{t,c}-mf_{t,c})\\phi_c\\phi_c^\\top \\succeq0,',
    '=(M-1)\\lambda\\bI+\\sigma^{-2}\\sum_c(Mf_{t,c}-g_{t,c})\\phi_c\\phi_c^\\top \\succeq0.',
    '=-\\frac{2}{\\sqrt W}\\operatorname{sech}^2(u)\\tanh(u) \\phi(z)\\phi(z)^\\top.',
    '=2\\sqrt{P_T\\sum_{t=1}^T(\\beta_t^{\\rm corr})^2}-B_T^{\\rm base},',
    '=2\\sqrt{P_T\\sum_{t=1}^T(\\beta_t^{\\rm stat})^2},',
    '=2\\sum_{t=1}^Tb_t(a_t).',
    '=\\bVbar_t+\\sigma^{-2}\\bq_t(a_t)\\bq_t(a_t)^\\top, \\label{eq:reference-update-new}',
    '=\\bVbar_t^{-1}\\sigma^{-2}\\sum_{s<t}\\bq_s(a_s)y_s. \\label{eq:frozen-ridge-new}',
    '=\\bq_t(a)^\\top\\Calg_t^{-1}\\bq_t(a).',
    '=\\bq_t(a)^\\top\\bV_t^{-1}\\bq_t(a),',
    '=\\bq_t(a)^\\top\\bVbar_t^{-1}\\bq_t(a),',
    '=\\lambda\\bI+\\sigma^{-2}\\sum_{s<t} \\omega_{\\btheta_s}(z_s)^2\\phi(z_s)\\phi(z_s)^\\top,',
    '=\\lambda\\bI+\\sigma^{-2}\\sum_{s<t} \\omega_{\\btheta_t}(z_s)^2\\phi(z_s)\\phi(z_s)^\\top,',
    '=\\operatorname{sech}^2(u)\\phi(z),',
    '=\\sqrt{P_T\\sum_{t=1}^T(\\beta_t^{\\rm corr})^2 (1+e^{\\bar D_t^Q})^2}-B_T^{\\rm base}-B_T^{\\rm hist},',
    '=\\sqrt{\\gamma_{t-1}+2\\log(1/\\delta)}+\\sqrt\\lambda S',
    '=\\sum_{s<T}[\\epsilon_{\\rm lin}(s)+\\epsilon_{\\rm mis}(s)]^2,',
    '=\\sum_{t=1}^T [\\epsilon_{\\rm lin,t}(a_t)+\\epsilon_{\\rm mis,t}(a_t)].',
    'A documented development-only numerical refinement froze Gauss--Legendre quadrature order 2048 before tuning and evaluation. The full development gate compared orders 1024 and 2048 on all 24 declared trajectories; a separate development check also compared 2048 and 4096. No failed development check was reclassified as a passing evaluation. Quadrature checks, dense eigenvalue comparisons, and confidence/optimism checks remain floating-point diagnostics. They do not supply rigorous numerical enclosures for theorem assumptions.',
    "All policies use the corrected center and confidence radius of \\Cref{cor:corrected-center-new}. \\emph{Hessian} uses the analytic path certificate $\\bar D_t^Q$; \\emph{endpoint} substitutes the dense endpoint Thompson distance; \\emph{frozen reference} uses the reference width directly; and \\emph{naive current} uses the current width without transport, an uncertified control. All four policies update their representations: ``frozen'' describes the collection-time metric, not a fixed representation. They share contexts and potential-noise streams but have their own adaptive action histories. The common optimizer, learning rate $3\\times10^{-4}$ with 20 full-batch steps followed by projection each round, was selected from nine candidates by prediction MSE on uniform-random tuning histories. This controls one implementation choice; it does not establish policy-specific regret-optimal tuning.",
    "All quantities are evaluated on this policy's own selected history. No path, current-metric, or operator certificate is needed for this score. If its reference-confidence event has probability at least $1-\\delta$, so does this guarantee.",
    'Consequently, $W=\\Omega(T)$ with a sufficiently large problem-dependent constant keeps $D_{T,W}=O(1)$. For fixed $d$ and fixed problem constants, \\[ R_T=O(d\\sqrt T\\log T)+O(\\sqrt T). \\] This conclusion requires no $D_t<1$ condition. Here $W$ is an abstract near-linearity scale, not generic network width or parameter count, and the result is not an unrestricted neural-training theorem. No optimizer-residual rate is required because the corrected center is used.',
    'Dense float64 matrices and Cholesky solves implement the exact-operator abstraction, and finite action enumeration uses the smallest-index tie rule. This is a 29-parameter diagnostic study, not a test of approximate solvers, large-model scalability, or real-data performance. Further protocol and provenance details appear in \\Cref{app:transport-followup}.',
    'Exact current curvature has $\\kappa_{-,t}=\\kappa_{+,t}=1$. More generally, the operational relative-error certificate',
    'Fix $\\delta\\in(0,1)$. Let $\\rho_s^\\circ$ be the Taylor remainder of $\\mu_{\\btheta^\\circ}$ around $\\btheta_s$, and supply envelopes',
    'For completeness, an exact scalar endpoint distance does not generally give the actionwise equality. Set $\\bVbar=I_2$, $\\bV=\\operatorname{diag}(e^D,e^{-D})$ with $D>0$, and $\\bq=(0,1)^\\top$. Then $d_{\\rm Th}(\\bVbar,\\bV)=D$ and $\\bar s=1$, whereas the scalar corrected width is $e^{D/2}s=e^D>1$.',
    "For descriptive context, the online context-free mean-only benchmark has mean regrets 185.26, 183.06, and 176.67 at $W=16,1,0.25$, respectively; the best fixed action in hindsight has mean regrets 180.01, 177.97, and 171.84. These means use the same evaluation streams. Hessian's sample means are close to the context-free benchmark's, but no equivalence test was performed, and similar regret does not imply matching actions or identical use of context. \\Cref{app:transport-followup} defines both benchmarks.",
    "For each logged state, we evaluate all four original score rules using that state's matrices, centers, and radii, without changing its history. \\Cref{tab:transport-followup-same-history} includes all 12 combinations of condition and behavior policy. Each entry averages one-step pseudo-regret over 50,000 dependent states; the diagonal equals the actual mean cumulative pseudo-regret divided by 1000. Off-diagonal entries are recommendations on states visited by the row policy. They are not cumulative regret for an alternative adaptive policy: a changed action would generally change future observations, parameters, matrices, and decisions. The analysis was specified after the full-study outcomes were observed.",
    'For the category certificate, finite positive collection weights imply $f_{t,c}>0$ whenever $n_{t,c}>0$, and \\[ \\bVbar_t=\\lambda\\bI+\\sigma^{-2}\\sum_c f_{t,c}\\phi_c\\phi_c^\\top, \\qquad \\bV_t=\\lambda\\bI+\\sigma^{-2}\\sum_c g_{t,c}\\phi_c\\phi_c^\\top. \\] For $m=c_{-,t}$ and $M=c_{+,t}$, the definitions give',
    'For the fixed-band statement, the largest admissible mean is $m_t(a)+\\beta_t\\bar s_t(a)+b_t(a)$. Comparing this endpoint to the proposed score and using $\\beta_t>0$ proves necessity and sufficiency. When $\\beta_t=0$, this comparison imposes no restriction on the candidate width. It makes no assertion about uncertainty sets constrained by additional information or about distinct adaptive histories.',
    'For unit feature and parameter bounds, \\Cref{cor:tanh-relative-weights} gives the uniform endpoint bound $D_0=4\\log\\cosh(1/\\sqrt W)$, approximately $0.124$, $1.735$, and $5.300$ at the three conditions. The category-specific sandwich $c_{-,t}\\bVbar_t\\preceq\\bV_t\\preceq c_{+,t}\\bVbar_t$ gives a symmetric coefficient $\\exp(D_{{\\rm cat},t}/2)$, where $D_{{\\rm cat},t}=\\max\\{-\\log c_{-,t},\\log c_{+,t}\\}$, or the separate outward coefficient $\\sqrt{c_{+,t}}$ of \\Cref{cor:relative-endpoint-ucb}. The latter retains the separate return factor $c_{-,t}^{-1/2}$ in the cumulative bound. Neither category construction is an upper bound on the length of the original interpolated factor path.',
    'Here $\\lambda>0$ and $\\sigma>0$. Define the corresponding widths',
    'If the observed feature vectors belong to a finite set $\\{\\phi_c\\}$, let $n_{t,c}$ be their counts, let $f_{t,c}=\\sum_{s<t:\\phi(z_s)=\\phi_c}\\omega_{\\btheta_s}(z_s)^2$, and put $g_{t,c}=n_{t,c}\\operatorname{sech}^4(\\phi_c^\\top\\btheta_t/\\sqrt W)$. The sharper category certificate is',
    'Let $\\bu=\\Calg^{-1}\\bq$. Since $s_{\\Calg}^2=\\bq^\\top\\bu=\\|\\bu\\|_{\\Calg}^2$, \\[ \\left|\\bq^\\top\\tilde\\bu-s_{\\Calg}^2\\right| =\\left|\\langle\\bu,\\tilde\\bu-\\bu\\rangle_{\\Calg}\\right| \\le\\|\\bu\\|_{\\Calg}\\|\\tilde\\bu-\\bu\\|_{\\Calg} \\le\\varepsilon s_{\\Calg}^2. \\] This proves the pointwise two-sided quadratic-form comparison. Dividing its lower side by $1-\\varepsilon$ gives upper validity for this query, while combining both sides gives the displayed sharpness factor. Applying the lower inequality actionwise on the simultaneous family event gives the all-domain upper condition; only the played query uses the upper inequality for sharpness. For PCG the argument is unchanged once the certificate is expressed in the original $\\Calg$-energy norm.',
    'Let $\\mathcal J$ be a finite or countable certificate-source index set. For $j\\in\\mathcal J$, choose an $\\cHist_t^-$-measurable failure budget $\\delta_{j,t}$ before drawing its random object. Let $\\mathcal P_{j,t}$ be the pre-reward sigma-algebra immediately before that draw. It may equal $\\cHist_t^-$ for a round-start draw or include the selected action and earlier randomness for a post-selection check. It is sufficient that \\[ \\Pr(\\mathcal E_{j,t}^c\\mid\\mathcal P_{j,t})\\le\\delta_{j,t}, \\qquad \\sum_{j\\in\\mathcal J}\\sum_{t=1}^T\\delta_{j,t} \\le\\delta_{\\rm cert}\\quad\\text{almost surely}. \\] The tower property and a union bound give simultaneous validity at least $1-\\delta_{\\rm cert}$ without independence. Countability makes the joint event measurable, the nonnegative double sum well-defined, and the union bound valid. On an uncountable score domain, the solver upper event must already be simultaneous. A pointwise certificate cannot be union-bounded after adaptive selection unless it is separately verified at the selected action with the correct conditioning. Realized terminal spectral quantities may be used for post-hoc analysis, but they cannot be inserted into an earlier action-time radius unless a predictable prefix envelope was supplied at that time.',
    'Let $c_t=\\beta_t[1+\\alpha_te^{\\bar D_t} \\sqrt{\\kappa_{+,t}/\\kappa_{-,t}}]$. Summation and one Cauchy--Schwarz application give \\[ R_T-2\\sum_tb_t(a_t)-\\sum_t\\xi_t \\le\\sqrt{\\sum_tc_t^2}\\sqrt{\\sum_t\\bar s_t^2(a_t)}. \\] Since $\\bar s_t^2(a_t)\\le G^2/\\lambda$, the scalar inequality $x\\le(1+M)\\log(1+x)$ for $0\\le x\\le M$, with $x=\\sigma^{-2}\\bar s_t^2(a_t)$ and $M=G^2/(\\lambda\\sigma^2)$, yields',
    'More generally, fix an action and $m_t(a)$, $b_t(a)$, $\\beta_t>0$, and $\\bar s_t(a)$. If the only restriction on its mean is the full interval \\eqref{eq:abstract-confidence-new}, a score $m_t(a)+\\beta_t w_t(a)+b_t(a)$ is an upper bound for every mean in that interval if and only if $w_t(a)\\ge\\bar s_t(a)$.',
    'More generally, suppose there is a measurable function $\\nu_t:[0,1]\\to[0,\\infty)$ with $\\nu_t\\in L^1([0,1])$ such that \\[ \\dot\\Bmat(\\tau)^\\top\\dot\\Bmat(\\tau) \\preceq\\nu_t(\\tau)^2\\bV(\\tau) \\] almost everywhere. Then $\\mathcal D(\\bV)\\le2\\int_0^1\\nu_t(\\tau)d\\tau$. For nonnegative $\\nu_t$, the displayed PSD premise is equivalently the norm condition $\\|\\dot\\Bmat(\\tau)\\bV(\\tau)^{-1/2}\\|_{\\rm op}\\le\\nu_t(\\tau)$ almost everywhere.',
    "Sequential confidence in a contextual bandit can use features frozen when rewards are collected, while retraining changes the features used by current curvature. We study the guarantees and limitations of transporting confidence to this relinearized curvature. A conditional UCB theorem separates metric transport, approximate operators, and solver widths, and bounds regret through the frozen sequential information gain. For squared loss, a corrected prediction center supplies reference confidence along predictable parameter paths in a certified region, with explicit Taylor and misspecification error envelopes and no nonlinear optimizer-convergence requirement. The certified width cannot be smaller than the direct reference width on the same history; exact actionwise transport reproduces that width. This comparison does not order the realized regret of policies with different histories. We examine these distinctions in a 29-parameter scaled-tanh model, for which a relative-weight comparison also supplies a horizon-independent endpoint certificate. A prespecified follow-up evaluates four policies across three conditions with 50 paired seeds per condition. The Hessian-transport policy has higher mean pseudo-regret than every comparator in every condition; all nine pointwise paired confidence intervals exclude zero. Its regret bounds are vacuous and dominated by path inflation, while the reference policy's own bounds are also vacuous. Floating-point confidence and optimism diagnostics pass for all evaluated policies, including an uncertified control. Exploratory log analyses distinguish conditional validity, certificate usefulness, and observed policy behavior in this implementation.",
    'Set $\\gamma_0=0$, and define',
    'Set $\\hat s=\\sqrt{U}$. If $L>0$, the observable factor $\\alpha=\\sqrt{U/L}$ verifies played-action sharpness. If $L\\le0<U$, the interval supplies no finite positive multiplicative sharpness factor; the solve must continue or an additive-width theorem must be used. If $U=0$, the exact inverse quadratic form is zero and the solver returns $\\hat s=0$. For $\\bq=0$, skip the solve and return zero.',
    'Since $\\sup_u|2\\operatorname{sech}^2(u)\\tanh(u)|=4/(3\\sqrt3)$, \\Cref{cor:global-near-linear-new} applies with \\[ G=B_\\phi,\\qquad c_\\mu=c_g=c_h:=\\frac{4B_\\phi^2}{3\\sqrt3}. \\] The symbol $W$ is a smoothness scale here; it is not identified with hidden width or parameter count.',
    'The category certificate uses only scalar sums and current projections. After collecting category $c$ at time $t$, its count increases by one and its collection sum increases by $\\omega_{\\btheta_t}(z_t)^2$; other category sums are unchanged. These are sufficient statistics for this comparison, although the category factors need not be the tight spectral factors when feature outer products are linearly dependent.',
    'The earlier audit contributes 21 artifacts, each with its original provenance record and checksum sidecar. The follow-up contributes separately generated tables and a collective provenance record, all independently pinned in code. The excluded legacy appendix, symbolic rate table, autodiff-GGN benchmark and linear-bound benchmark are not evidence for the active manuscript and are not included.',
    'The earlier experiments did not execute the transported score or record its path, operator, and solver certificates. They therefore provide no evidence for the current theorem or its numerical performance. The present paper makes no empirical claim for a large neural model, an approximate operator, or an iterative solver: its reported study uses a 29-parameter model and dense Cholesky solves. These exclusions do not change the conditional operator and solver interfaces proved in the theorem.',
    'The exact solution is $\\Calg^{-1}\\bq=\\tilde\\bu+\\Calg^{-1}\\br$. Substitute this expression and $\\bq=\\Calg\\tilde\\bu+\\br$ into the quadratic form. The remainder is $\\br^\\top\\Calg^{-1}\\br$, which lies between zero and $\\|\\br\\|_2^2/\\lambda_{\\Calg}$.',
    "The existing cumulative decomposition in \\Cref{fig:transport-instantiation-bound} separates base confidence, historical linearization, path inflation, and current bias. At $T=1000$, the base component accounts for $79.4\\%$--$97.3\\%$ of the mean terminal sharp right-hand side across target cells; path inflation accounts for $2.0\\%$--$16.3\\%$. Each percentage divides a component's mean over the 50 transport-Hessian trajectories by the mean sharp right-hand side over those same trajectories. These are ratios of means, not medians of runwise shares. The base component alone has cell means of about $9{,}948$--$10{,}010$, already above the cap $2{,}000$. It includes the statistical and regularization/norm-bound terms together with the determinant-potential and Cauchy--Schwarz factors; its size cannot be attributed to the confidence radius alone. Thus most of the bound's size on this original near-linear grid is present before path inflation is added. This dominance statement does not describe the nonlinear follow-up. This is a decomposition along transport-Hessian histories, not a bound evaluated on the frozen-reference policy's different histories. The appendix defines the components and reports the complete tightness table.",
    "The full study fixes teacher seed 1729, development seeds 30000--30001, tuning seeds 30100--30109, and evaluation seeds 30200--30249. Contexts are normalized Rademacher vectors. The feature map concatenates the context, action indicator, and their tensor product, then normalizes it to unit norm; its dimension is $4+5+20=29$. The teacher has unit norm and a fixed regular-simplex construction in the interaction block. The learner starts at zero, uses training ridge one, and receives only the selected action's reward. The potential-noise table couples methods without revealing unselected rewards. The 24 development trajectories cover three conditions and four policies at both development seeds. The 270 tuning trajectories cover nine optimizer candidates, three conditions, and ten tuning seeds, using uniform-random actions. The nine candidates combine learning rates $\\{3\\times10^{-5},10^{-4},3\\times10^{-4}\\}$ with $\\{1,5,20\\}$ full-batch steps. All were eligible. Candidate 008, learning rate $3\\times10^{-4}$ and 20 steps, minimized equally weighted all-action prediction MSE over the 30 tuning seed--condition cells, with selected MSE $0.00392155$. Evaluation consists of $3\\times4\\times50=600$ further trajectories. The 294 development and tuning trajectories are not evaluation replicates.",
    'The historical deterministic term in \\eqref{eq:beta-corrected-new} follows from $\\Phi_t^\\top\\bVbar_t^{-1}\\Phi_t\\preceq I$ for $\\Phi_t=[\\bq_1/\\sigma,\\ldots,\\bq_{t-1}/\\sigma]$. Its scaling is $1/\\sigma$, not $1/\\sigma^2$. Fixed nonvanishing misspecification generally creates a linear current-bias term and can also make the historical radius vacuous. This is a graceful-degradation statement, not a robust misspecified-bandit guarantee.',
    'The inclusion of $1$ in the minimum and maximum accounts for the ridge. Each category ratio is a weighted average of sample ratios $r_s=\\widetilde\\omega_s^2/\\omega_s^2$, with weights $\\omega_s^2/f_{t,c}$. Therefore $\\ell^2\\le g_{t,c}/f_{t,c}\\le\\ell^{-2}$, which gives the asserted uniform bounds on $m,M$. It also shows that the category factors are no looser than the direct sample factors $\\min\\{1,\\min_{s<t}r_s\\}$ and $\\max\\{1,\\max_{s<t}r_s\\}$. For an empty history both metrics equal $\\lambda\\bI$.',
    "The locked grid contains horizons $T\\in\\{250,500,1000\\}$, 50 evaluation seeds, and target labels $D_{\\rm target}\\in\\{0.25,0.5,1,2\\}$. Each $(T,D_{\\rm target})$ cell is a separately executed model condition because both quantities enter the rule for $W$. The target label is neither realized transport distance nor generic network width, so trends across targets are not a dose response to certificate inflation. The four policies share contexts and potential-noise tables. The primary \\emph{transport Hessian} policy uses $\\bar D_t^Q$ in the score. The \\emph{transport endpoint} policy replaces it by the dense endpoint Thompson distance computed from the learner-known matrices $\\bVbar_t$ and $\\bV_t$ before the reward is observed; it is a dense diagnostic comparator. The \\emph{frozen reference} policy uses the frozen width directly. The \\emph{naive current} policy omits transport and is intentionally uncertified. Each policy has its own selected history and representation path; the frozen-reference policy also updates its representation. ``Frozen'' refers to its collection-time metric. Ten disjoint tuning seeds selected learning rate $3\\times10^{-4}$ and 20 full-batch steps followed by projection each round by preregistered all-action prediction MSE; evaluation seeds never entered that selection. The environment was not filtered after generation. Within each $T=1000$ target cell, the 50-seed means round to optimal-action entropy $1.579$, optimality gap $0.123$, best-fixed-action regret $180.4$, and online context-free mean-only regret $185.4$. All five actions are optimal somewhere in every evaluation stream. Entropy is measured in nats; its maximum for five actions is $\\log 5\\approx1.609$, so the mean entropy is close to its uniform-action maximum. These diagnostics were reported after the grid was fixed; they were not used to select seeds.",
    'The numerical scan reconstructs the recorded selected scores exactly and finds no nonfinite coefficients or scores and no zero widths. A separate 250-digit decimal calculation evaluates the final score arithmetic from the exact stored binary64 centers, widths, offsets, and \\emph{already rounded} coefficient $B_t$. It changes the primary recommendation at 16 states: five, five, and six in the respective conditions. Across all behavior histories there are 65 changes among 600,000 states. All occur at rounds 2--10, with score differences below 0.629 of a binary64 score ULP. The decimal calculation does not recompute upstream matrix solves, exponentials, coefficients, or fitted parameters. An early changed action could affect subsequent adaptive history; that effect has not been measured. Likewise, equality between the full score vector and its bonus-plus-offset part in binary64 arithmetic includes initially zero centers and is not, by itself, evidence that the selected action was corrupted.',
    'The paired-bootstrap intervals resample the 50 evaluation seeds within a condition, preserving the pairing between policies, with 10,000 resamples and the recorded deterministic bootstrap seed. The nine intervals in \\Cref{tab:transport-followup-outcomes} are comparisonwise rather than multiplicity-adjusted. Shared seeds across conditions do not make the 600 trajectories independent observations from one common population. The teacher, conditions, and shared optimizer are fixed in this uncertainty calculation.',
    'The post-outcome audit replays the original representation optimizer with fixed logged actions and rewards for all 600 trajectories; it never replaces a behavior action or generates a new observation. It reconstructs collection-time category weights and compares the resulting sandwich, effective widths, and recommendations at the stored states. Matrix, center, and endpoint reconstruction are checked at rounds 1, 2, 10, 100, 500, and 1000; the original float64 tolerances are retained. These computations check an implementation of the mathematical construction, without converting floating-point residuals into verified certificates. All declared checks passed; the largest residual divided by its original tolerance was below $0.005$. The per-seed variation in the preceding table was reproduced by this separate fixed-action replay.',
    'The previous additive stacked-design result remains a useful local corollary. If $\\chi_t<1$ and',
    "The primary bounds are dominated by path inflation in all three conditions. Every primary-policy bound exceeds the deterministic regret cap $2T\\min(1,\\sqrt W)$, which is 2000, 2000, and 1000 for the three conditions. The frozen policy's own reference-geometry bounds also exceed these caps in all 150 of its trajectories. Their mean right-hand sides are much smaller than the primary bounds but remain vacuous. Removing the path term along Hessian's histories would be an accounting decomposition, not the bound or outcome of a frozen policy following different histories. Base dominance reported for the original near-linear grid does not describe this follow-up.",
    "Their sum equals the sharp right-hand side in \\eqref{eq:sharp-transport-regret-new} for the experiment's $\\alpha_t=\\kappa_{-,t}=\\kappa_{+,t}=1$ and $\\xi_t=0$. The differences retain the same trajectory and the same potential factor; they do not rerun a policy with a component removed. The committed figure CSVs report the mean of each component over 50 primary-policy trajectories at each round. At $T=1000$, dividing those terminal component means by the corresponding mean sharp right-hand side gives base shares $97.33\\%,94.66\\%,89.39\\%,79.39\\%$ and path shares $2.01\\%,4.04\\%,8.16\\%,16.27\\%$ for $D_{\\rm target}=0.25,0.5,1,2$, respectively. These joint cumulative quantities establish the decomposition; marginal medians of $e^{\\bar D_t^Q/2}$ do not determine it.",
    'This appendix expands the original locked full aggregate summarized in \\Cref{sec:transport-instantiation}. The experiment protocol, configuration, selection record, aggregate, and every generated artifact carry provenance and         hashes. The figures use only the 50 evaluation seeds. Smoke and tuning results are absent. The original raw trajectories were unavailable for this revision; recorded hashes bind the retained artifacts but do not replace those missing inputs or establish an independent raw-data reproduction.',
    'This proves \\eqref{eq:sharp-transport-regret-new}. Finally, $\\alpha_te^{\\bar D_t}\\sqrt{\\kappa_{+,t}/\\kappa_{-,t}}\\ge1$, hence $1+x\\le2x$ gives \\eqref{eq:simple-transport-regret-new}. The probability statement follows by a union bound; independence is not required.',
    'This remains valid when $\\bar D_t\\ge1$. At $t=1$, the factor has zero rows, $Q_1=0$, and both metrics equal $\\lambda\\bI$.',
    'Use Python 3.12 with NumPy 2.2.3 and SciPy 1.15.2. These are the declared versions in `experiments/requirements.txt`. The supplied `experiments/requirements-python312.lock` additionally pins the portable Linux x86_64 wheel environment, including the test dependencies. A separate online installation may use `pip install --require-hashes --only-binary=:all: -r experiments/requirements-python312.lock`. The verification commands themselves do not install or download anything.',
    'We next instantiate the reference-confidence interface. The corrected center keeps statistical estimation in the predictable collection-time features while using the current nonlinear prediction as its anchor. The resulting identity does not assume that the representation parameter minimizes a nonlinear loss. Let $\\sigma>0$ and let the reward obey $r_t=\\mu_t^*(a_t)+\\eta_t$, where, for every $u\\in\\R$,',
    'We test whether valid confidence transport produces useful certificates and decisions in a controlled nonlinear model. The prespecified follow-up evaluates 600 policy trajectories; a separate 294 development and tuning trajectories precede evaluation. The original near-linear study is retained separately in \\Cref{sec:transport-instantiation}; its evidence is not pooled with this study.',
    'With exact realizability and a frozen linear model, $B_T=E_T^{\\rm cur}=0$. For fixed $d$ and problem constants, the leading term is then $O(e^D\\sqrt K\\,d\\sqrt T\\log T)$. Exact solves set $\\alpha=1$, exact current curvature sets $K=1$, and exact score maximization sets $\\xi_t=0$, recovering the standard LinUCB determinant-potential rate up to displayed constants.',
    'Write the primary score on a recorded state as $m_t(a)+B_t s_t(a)+b_t$, where $b_t$ is action independent and $B_t=\\beta_t^{\\rm corr}\\exp(\\bar D_t^Q/2)$. Let $s_{t,(1)}\\ge s_{t,(2)}$ be the largest two current widths. The strict condition \\[ B_t\\bigl(s_{t,(1)}-s_{t,(2)}\\bigr) >\\max_a m_t(a)-\\min_a m_t(a) \\] is sufficient for the unique largest-width action to maximize the score. Width-argmax agreement alone is weaker: prediction centers might favor the same action. The exact tie rule is the smallest action index.',
    '[1] \\STATE Observe the context and graph-measurable action correspondence $\\cA_t$; this defines $\\cHist_t^-$. \\STATE Take the prefix-determined $\\btheta_t$, $\\bVbar_t$, and $\\bV_t$; using the observed context, form $\\bq_t(a)$, $m_t^{\\rm corr}(a)$, and $b_t(a)$. \\STATE Choose $\\cHist_t^-$-measurable failure budgets before their corresponding draws; reveal the pre-reward randomness $\\Omega_t$. \\STATE Construct $\\Calg_t$ and obtain pre-reward certificates $\\bar D_t$, $\\kappa_{-,t}$, and $\\kappa_{+,t}$. \\STATE Obtain one jointly measurable solver upper-width map $\\hat s_t(a)$ over the score domain. \\STATE Return a $\\cHist_t$-measurable $\\xi_t$-approximate selector for the score in \\eqref{eq:transported-score-new}. \\STATE Observe the reward; update the frozen ridge estimator and \\eqref{eq:reference-update-new}.',
    '[Corrected-center confidence without optimizer assumptions] \\label{cor:corrected-center-new} With probability at least $1-\\delta$, simultaneously over rounds and actions,',
    '[Estimator- and solver-agnostic confidence transport] \\label{thm:transported-ucb} Under the protocol above with $\\lambda>0$ and $\\sigma>0$, suppose \\Cref{asm:abstract-transport} holds, the score obeys \\eqref{eq:transported-score-new}--\\eqref{eq:approx-score-oracle-new}, and $\\|\\bq_t(a)\\|_2\\le G$. On the joint confidence and certificate event, the instantaneous regret satisfies',
    '[Global near-linearity under exponential transport] \\label{cor:global-near-linear-new} Assume exact realizability, $\\mu^*(z)=\\mu_{\\btheta^\\circ}(z)$, and suppose $\\|\\btheta^\\circ\\|_2\\le R$ and $\\|\\btheta_t\\|_2\\le R$ for every $t$. On the certified convex radius-$R$ region, assume the prediction gradient is $L_\\mu$-Lipschitz for the Taylor envelopes and satisfies the replay-path Hessian bound $L_g$ in \\Cref{cor:hessian-path-new}, with \\[ L_\\mu\\le\\frac{c_\\mu}{\\sqrt W},\\qquad L_g\\le\\frac{c_g}{\\sqrt W}, \\] with $W>0$. Use the corrected center, exact current curvature, exact dense solves, and exact score maximization in finite parameter dimension $d$, and suppose $\\|\\bq_t(a)\\|_2\\le G$. Thus $\\alpha_t=1$, $\\kappa_{-,t}=\\kappa_{+,t}=1$, and $\\xi_t=0$. Define \\[ D_{T,W}:=\\frac{4c_gR\\sqrt{T-1}}{\\sigma\\sqrt{\\lambda W}}. \\] Then, with probability at least $1-\\delta$,',
    '[Hessian path certificate] \\label{cor:hessian-path-new} Suppose the parameter region is convex and $\\|\\nabla_\\theta^2\\mu_\\theta(x_s,a_s)\\|_{\\rm op}\\le L_g$ along every segment in \\eqref{eq:scalar-factor-path-new}. With',
    '[Inverse-quadratic interval from the original residual] \\label{lem:inverse-quadratic-certificate-new} Let $\\Calg=\\Calg^\\top\\succeq\\lambda_{\\Calg}\\bI$ with $\\lambda_{\\Calg}>0$. For an approximate solution $\\tilde\\bu$ to $\\Calg\\bu=\\bq$, recompute the original residual $\\br=\\bq-\\Calg\\tilde\\bu$. In exact arithmetic,',
    '[Logarithmic comparison along an SPD path] \\label{lem:log-spd-path} Let $\\bV:[0,1]\\to\\mathbb{S}_{++}^d$ be entrywise absolutely continuous and let $\\dot\\bV(\\tau)$ denote its almost-everywhere derivative. If',
    '[Measurably enumerated finite domains] \\label{cor:finite-enumeration-new} Suppose there is a positive $\\cHist_t^-$-measurable integer $K_t$ and $\\cHist_t^-$-measurable actions $a_{t,k}:\\Omega\\to\\mathsf A$, $k\\ge1$, such that \\[ \\cA_t=\\{a_{t,1},\\ldots,a_{t,K_t}\\}. \\] If the learner chooses the smallest index attaining the score maximum, then the selected action is $\\cHist_t$-measurable and \\eqref{eq:approx-score-oracle-new} holds with $\\xi_t=0$. The score and mean-reward suprema and the universal actionwise events reduce to measurable finite maxima and intersections. A fixed finite action set is the immediate special case.',
    '[Pointwise CG and PCG solver certificates] \\label{cor:cg-interface-new} Suppose CG or PCG supplies, in exact arithmetic, an original-system energy certificate $\\|\\bu-\\tilde\\bu\\|_{\\Calg}\\le\\varepsilon\\|\\bu\\|_{\\Calg}$ with $\\varepsilon<1$. Then \\[ (1-\\varepsilon)s_{\\Calg}^2 \\le\\bq^\\top\\tilde\\bu \\le(1+\\varepsilon)s_{\\Calg}^2. \\] Thus \\[ \\hat s=\\sqrt{\\frac{\\bq^\\top\\tilde\\bu}{1-\\varepsilon}}, \\qquad \\alpha=\\sqrt{\\frac{1+\\varepsilon}{1-\\varepsilon}} \\] give a pointwise upper-valid width and sharpness factor for this query. A jointly measurable action-indexed family of such solves, together with a simultaneous energy-certificate event for every scored action, supplies the all-domain upper condition in \\eqref{eq:solver-interface-new}; the sharpness conclusion is needed only at the played action. For a general standard-Borel domain, measurability of the family and simultaneous functional validity remain additional premises. A preconditioner may change the recurrence, but certificate checks must use the original operator.',
    '[Proof of \\Cref{cor:finite-d-rate-new}] Let $A_T=\\sigma^{-2}\\sum_{t=1}^T\\bq_t(a_t)\\bq_t(a_t)^\\top$. Its rank is at most $r_T=\\min\\{d,T\\}$ and its trace is at most $TG^2/\\sigma^2$. Concavity of $x\\mapsto\\log(1+x)$ over the nonzero eigenvalues gives \\[ \\gamma_T=\\log\\det(\\bI+A_T/\\lambda) \\le r_T\\log\\!\\left(1+\\frac{TG^2}{r_T\\lambda\\sigma^2}\\right). \\] The radius in \\eqref{eq:beta-corrected-new} is bounded by the bracketed term in \\eqref{eq:finite-d-rate-new-display}. Substitute this bound, the uniform transport factors, and \\eqref{eq:finite-d-gamma-new} into \\eqref{eq:simple-transport-regret-new}. The current bias envelope is exactly $b_t(a_t)=\\epsilon_{\\rm lin,t}(a_t)+\\epsilon_{\\rm mis,t}(a_t)$.',
    '[Proof of \\Cref{cor:finite-enumeration-new}] On the measurable event $\\{K_t=n\\}$, the finite vector $\\{U_t(a_{t,k})\\}_{k=1}^n$ is $\\cHist_t$-measurable by joint measurability on the graph. Its maximum and the smallest maximizing index are measurable. A countable partition over $n\\ge1$ therefore gives a $\\cHist_t$-measurable random index and hence a measurable selected action. The score maximum is attained, so $\\xi_t=0$. The same finite-max argument applies to the mean-reward supremum, and each universal event is a finite intersection on $\\{K_t=n\\}$.',
    "[Proof of \\Cref{cor:global-near-linear-new}] The radius bound gives \\[ Q_t\\le\\sum_{s<t} (\\|\\btheta_t\\|_2+\\|\\btheta_s\\|_2)^2 \\le4R^2(t-1). \\] Hence \\Cref{cor:hessian-path-new} gives $\\bar D_t\\le D_{T,W}$. Taylor's theorem and $\\|\\btheta^\\circ-\\btheta_s\\|_2\\le2R$ give \\[ \\epsilon_{\\rm lin}(s),\\ \\epsilon_{\\rm lin,t}(a) \\le\\frac{2c_\\mu R^2}{\\sqrt W}. \\] Exact realizability removes every misspecification envelope, so \\[ B_T\\le\\frac{4c_\\mu^2R^4T}{W},\\qquad E_T^{\\rm cur}\\le\\frac{2c_\\mu R^2T}{\\sqrt W}. \\] Substitute these inequalities, $S=R$, $\\alpha=1$, $K=1$, and $\\xi_t=0$ into \\Cref{cor:finite-d-rate-new}. The asymptotic statement follows from $\\Gamma_{T,d}=O(d\\log T)$ for fixed problem constants.",
    '[Proof of \\Cref{cor:hessian-path-new}] The $s$th factor-row derivative is \\[ \\sigma^{-1}\\left[ \\nabla_\\theta^2\\mu_{\\btheta_s+\\tau(\\btheta_t-\\btheta_s)}(x_s,a_s) (\\btheta_t-\\btheta_s)\\right]^\\top. \\] Hence $\\|\\dot\\Bmat_t(\\tau)\\|_F^2\\le L_g^2Q_t/\\sigma^2$. Since $\\bV_t(\\tau)\\succeq\\lambda\\bI$, \\[ \\dot\\Bmat_t(\\tau)^\\top\\dot\\Bmat_t(\\tau) \\preceq\\frac{L_g^2Q_t}{\\sigma^2\\lambda}\\bV_t(\\tau). \\] Apply \\Cref{lem:factor-spd-path} with the constant $\\nu_t=L_g\\sqrt{Q_t}/(\\sigma\\sqrt\\lambda)$.',
    '[Proof of \\Cref{cor:local-small-drift-new}] Inverting \\eqref{eq:local-additive-new} gives \\[ \\bar s_t(a)\\le(1+\\chi_t)s_t(a),\\qquad s_t(a)\\le(1-\\chi_t)^{-1}\\bar s_t(a). \\] The first inequality, the upper operator comparison, and solver upper validity make the local score optimistic. At the played action, solver sharpness, the lower operator comparison, and the second inequality bound its width term by \\[ \\alpha_t\\frac{1+\\chi_t}{1-\\chi_t} \\sqrt{\\frac{\\kappa_{+,t}}{\\kappa_{-,t}}}\\,\\bar s_t(a_t). \\] Repeat the proof of \\Cref{thm:transported-ucb} and apply \\eqref{eq:frozen-potential-proof}.',
    '[Proof of \\Cref{cor:relative-endpoint-ucb}] Inverting \\eqref{eq:relative-endpoint-sandwich} gives, for every query, \\[ \\bar s_t(a)\\le\\sqrt{c_{+,t}}s_t(a),\\qquad s_t(a)\\le c_{-,t}^{-1/2}\\bar s_t(a). \\] The first inequality, the outward operator inequality in \\eqref{eq:operator-width-proof}, and solver upper validity imply $\\bar s_t(a)\\le\\sqrt{c_{+,t}\\kappa_{+,t}}\\hat s_t(a)$. Consequently, \\eqref{eq:relative-endpoint-score} is optimistic on the reference confidence event. Its approximate-selector condition and lower reference confidence at the played action give',
    '[Proof of \\Cref{cor:tanh-relative-weights}] Write $\\omega_s=\\omega_{\\btheta_s}(z_s)$ and $\\widetilde\\omega_s=\\omega_{\\btheta_t}(z_s)$. Cauchy--Schwarz and the parameter and feature bounds give $\\ell\\le\\omega_s,\\widetilde\\omega_s\\le1$. Thus \\[ \\ell^2\\omega_s^2\\le\\widetilde\\omega_s^2 \\le\\ell^{-2}\\omega_s^2. \\] Multiplying by the positive semidefinite matrix $\\sigma^{-2}\\phi(z_s)\\phi(z_s)^\\top$ and summing proves the comparison for the data terms. Including the ridge preserves it because \\[ \\bV_t-\\ell^2\\bVbar_t\\succeq(1-\\ell^2)\\lambda\\bI\\succeq0, \\qquad \\ell^{-2}\\bVbar_t-\\bV_t \\succeq(\\ell^{-2}-1)\\lambda\\bI\\succeq0. \\] Since $-2\\log\\ell=4\\log\\cosh(B_\\phi R/\\sqrt W)$, this also proves the uniform Thompson distance bound.',
    '[Proof of \\Cref{lem:factor-spd-path}] Almost everywhere, $\\dot\\bV=\\dot\\Bmat^\\top\\Bmat+\\Bmat^\\top\\dot\\Bmat$. Put $E=\\dot\\Bmat\\bV^{-1/2}$ and $H=\\Bmat\\bV^{-1/2}$. Then \\[ \\bV^{-1/2}\\dot\\bV\\bV^{-1/2}=E^\\top H+H^\\top E. \\] Moreover, \\[ H^\\top H =\\bV^{-1/2}\\Bmat^\\top\\Bmat\\bV^{-1/2} =\\bI-\\lambda\\bV^{-1}\\preceq\\bI, \\] so $\\|H\\|_{\\rm op}\\le1$. Therefore the normalized SPD speed is at most $2\\|E\\|_{\\rm op}$, which proves \\eqref{eq:factor-path-bound-new} after integration. For the PSD form, congruence by $\\bV^{-1/2}$ gives \\[ \\|\\dot\\Bmat\\bV^{-1/2}\\|_{\\rm op}^2 =\\|\\bV^{-1/2}\\dot\\Bmat^\\top\\dot\\Bmat\\bV^{-1/2}\\|_{\\rm op} \\le\\nu_t(\\tau)^2. \\] Because $\\nu_t(\\tau)\\ge0$, taking square roots gives $\\|\\dot\\Bmat\\bV^{-1/2}\\|_{\\rm op}\\le\\nu_t(\\tau)$ almost everywhere. The assumed $L^1$ integrability permits integration in \\eqref{eq:factor-path-bound-new}.',
    '[Proof of \\Cref{lem:log-spd-path}] Fix $v\\ne0$ and set $f_v(\\tau)=v^\\top\\bV(\\tau)v$. The path is continuous and positive definite on a compact interval, so $f_v$ is absolutely continuous and bounded away from zero. Thus $\\log f_v$ is absolutely continuous and, almost everywhere, \\[ \\frac{d}{d\\tau}\\log f_v(\\tau) =\\frac{v^\\top\\dot\\bV(\\tau)v}{v^\\top\\bV(\\tau)v}. \\] With $w=\\bV(\\tau)^{1/2}v$, the absolute value of this derivative is at most $\\|\\bV(\\tau)^{-1/2}\\dot\\bV(\\tau) \\bV(\\tau)^{-1/2}\\|_{\\rm op}$. Integrating gives \\[ e^{-\\mathcal D(\\bV)}v^\\top\\bV(0)v \\le v^\\top\\bV(1)v \\le e^{\\mathcal D(\\bV)}v^\\top\\bV(0)v. \\] The inequality holds for every $v$, which is exactly \\eqref{eq:log-path-sandwich-new}. Inverting the sandwich gives the corresponding inverse-quadratic-form comparison. The proof never differentiates a matrix square root.',
    '[Proof of \\Cref{prop:reference-width-floor}] The outward inequalities in \\eqref{eq:path-width-proof} and \\eqref{eq:operator-width-proof}, followed by the all-action solver upper certificate, give \\[ \\bar s_t(a)\\le e^{\\bar D_t/2}s_t(a) \\le e^{\\bar D_t/2}\\sqrt{\\kappa_{+,t}}s_{\\Calg,t}(a) \\le w_t^{\\rm tr}(a). \\] For a nonzero query, positive definiteness makes both $\\bar s_t(a)$ and $s_t(a)$ strictly positive, so their ratio is well defined and gives the stated equality. For a zero query, both exact widths vanish, and the assigned multiplier $1$ avoids division by zero. This equality concerns exact widths; the solver interface may allow a positive upper estimate at an unplayed zero query.',
    '[Proof of \\Cref{prop:width-transport-new}] The logarithmic sandwich and inversion give \\[ \\bar s_t^2(a)\\le e^{\\bar D_t}s_t^2(a),\\qquad s_t^2(a)\\le e^{\\bar D_t}\\bar s_t^2(a). \\] Inverting the operator sandwich gives \\[ s_t^2(a)\\le\\kappa_{+,t}s_{\\Calg,t}^2(a),\\qquad s_{\\Calg,t}^2(a)\\le\\kappa_{-,t}^{-1}s_t^2(a). \\] Composition proves \\eqref{eq:two-way-width-new}. For \\eqref{eq:relative-operator-certificate-new}, congruence gives $-\\varepsilon_t\\bI\\preceq \\bV_t^{-1/2}(\\Calg_t-\\bV_t)\\bV_t^{-1/2} \\preceq\\varepsilon_t\\bI$; undoing the congruence gives the claimed factors.',
    '[Rectangular factor-path certificate] \\label{lem:factor-spd-path} Let $\\Bmat:[0,1]\\to\\R^{m\\times d}$ be absolutely continuous and set $\\bV(\\tau)=\\lambda\\bI+\\Bmat(\\tau)^\\top\\Bmat(\\tau)$, with $\\lambda>0$. Then',
    '[Relative weights for scaled tanh] \\label{cor:tanh-relative-weights} For the scaled-tanh model above, suppose $W>0$, $\\|\\phi(z_s)\\|_2\\le B_\\phi$, and $\\|\\btheta_s\\|_2,\\|\\btheta_t\\|_2\\le R$ for all $s<t$. Set $\\omega_\\theta(z)=\\operatorname{sech}^2(\\phi(z)^\\top\\theta/\\sqrt W)$ and $\\ell=\\operatorname{sech}^2(B_\\phi R/\\sqrt W)>0$. For',
    '[The reference band alone does not justify a smaller width] \\label{rem:naive-width-band-counterexample} Consider an abstract confidence-band instance with $D>0$, $\\bVbar=\\bI_2$, $\\bV=\\operatorname{diag}(e^D,e^{-D})$, and $\\bq=(1,0)^\\top$. Take $m=b=0$, $\\beta>0$, and $\\mu^*=\\beta$. Then $\\bar s=1$ and $s=e^{-D/2}$, so \\[ |\\mu^*-m|=\\beta\\bar s+b,\\qquad m+\\beta s+b=\\beta e^{-D/2}<\\mu^*. \\] Reference confidence therefore holds while the naive current-width score is not an upper bound. This illustrates the limited-information statement of \\Cref{prop:reference-width-floor}; it does not construct a realizable scaled-tanh learning trajectory or establish that this certificate family was necessary in the reported runs.',
    '[Thompson distance and selected-path length] The integrand in \\eqref{eq:generic-path-length-new} is the classical Thompson Finsler norm on the positive-definite cone \\citep{thompson1963certain,nussbaum1994finsler}. Its endpoint metric is \\[ d_{\\rm Th}(A,B) :=\\inf\\{r\\ge0:e^{-r}A\\preceq B\\preceq e^rA\\}. \\] Equivalently, \\[ d_{\\rm Th}(A,B) =\\left\\|\\log(A^{-1/2}BA^{-1/2})\\right\\|_{\\rm op}. \\] Therefore \\Cref{lem:log-spd-path} gives',
    "\\Cref{tab:transport-followup-mechanism-variation} reports per-seed variation instead of treating the pooled rounds as independent. In every row, the recommendation being diagnosed is the Hessian score evaluated on the row's behavior histories. Only Hessian rows describe that behavior policy's own score. The other rows do not establish width-dominated selection by endpoint, frozen-reference, or naive-current policies. Each fraction has 1000 rounds in its denominator, and the reported median and range summarize 50 seeds. These descriptive summaries are not confidence intervals.",
    '\\] Then \\[ \\bV(\\tau)^{-1/2}\\dot\\bV(\\tau)\\bV(\\tau)^{-1/2} =',
    '\\bVbar_{t+1}',
    '\\bar s_t^2(a)',
    '\\bq_t(a)=0',
    '\\label{eq:Qt-new} Q_t=\\sum_{s<t}\\|\\btheta_t-\\btheta_s\\|_2^2,',
    '\\label{eq:factor-path-bound-new} \\mathcal D(\\bV)\\le2\\int_0^1 \\|\\dot\\Bmat(\\tau)\\bV(\\tau)^{-1/2}\\|_{\\rm op}\\,d\\tau.',
    '\\label{eq:finite-d-gamma-new} \\gamma_T\\le\\Gamma_{T,d}:= r_T\\log\\!\\left(1+\\frac{TG^2}{r_T\\lambda\\sigma^2}\\right).',
    '\\label{eq:frozen-gamma-new} \\gamma_T :=\\log\\frac{\\det\\bVbar_{T+1}}{\\det\\bVbar_1} =\\sum_{t=1}^T\\log\\!\\left(1+\\sigma^{-2}\\bar s_t^2(a_t)\\right).',
    '\\label{eq:frozen-potential-proof} \\sum_{t=1}^T\\bar s_t^2(a_t) \\le\\left(\\sigma^2+\\frac{G^2}{\\lambda}\\right)\\gamma_T.',
    '\\label{eq:generic-path-length-new} \\mathcal D(\\bV)=\\int_0^1 \\|\\bV(\\tau)^{-1/2}\\dot\\bV(\\tau)\\bV(\\tau)^{-1/2}\\|_{\\rm op}\\,d\\tau,',
    '\\label{eq:hessian-path-sandwich-new} e^{-\\bar D_t}\\bVbar_t\\preceq\\bV_t\\preceq e^{\\bar D_t}\\bVbar_t, \\qquad \\bar D_t=\\frac{2L_g\\sqrt{Q_t}}{\\sigma\\sqrt\\lambda}.',
    '\\label{eq:instantaneous-transport-new} \\operatorname{reg}_t\\le \\beta_t\\!\\left[1+\\alpha_t e^{\\bar D_t} \\sqrt{\\frac{\\kappa_{+,t}}{\\kappa_{-,t}}}\\right]\\bar s_t(a_t) +2b_t(a_t)+\\xi_t.',
    '\\label{eq:inverse-quadratic-identity-new} \\bq^\\top\\Calg^{-1}\\bq =\\bq^\\top\\tilde\\bu+\\tilde\\bu^\\top\\br +\\br^\\top\\Calg^{-1}\\br.',
    '\\label{eq:inverse-quadratic-interval-new} L=\\bq^\\top\\tilde\\bu+\\tilde\\bu^\\top\\br \\le\\bq^\\top\\Calg^{-1}\\bq \\le L+\\frac{\\|\\br\\|_2^2}{\\lambda_{\\Calg}}=U.',
    '\\label{eq:local-additive-new} (1-\\chi_t)^2\\bVbar_t\\preceq\\bV_t \\preceq(1+\\chi_t)^2\\bVbar_t,',
    '\\label{eq:log-path-sandwich-new} e^{-\\mathcal D(\\bV)}\\bV(0)\\preceq\\bV(1) \\preceq e^{\\mathcal D(\\bV)}\\bV(0).',
    '\\label{eq:new-noise-condition} \\mathbb E[\\exp(u\\eta_t)\\mid\\cHist_t] \\le\\exp(u^2\\sigma^2/2).',
    '\\label{eq:operator-sandwich-new} 0<\\kappa_{-,t}\\le\\kappa_{+,t}<\\infty,\\qquad \\kappa_{-,t}\\bV_t\\preceq\\Calg_t\\preceq\\kappa_{+,t}\\bV_t.',
    '\\label{eq:operator-width-proof} s_t(a)\\le\\sqrt{\\kappa_{+,t}}s_{\\Calg,t}(a),\\qquad s_{\\Calg,t}(a)\\le\\kappa_{-,t}^{-1/2}s_t(a).',
    '\\label{eq:path-width-proof} \\bar s_t(a)\\le e^{\\bar D_t/2}s_t(a),\\qquad s_t(a)\\le e^{\\bar D_t/2}\\bar s_t(a).',
    '\\label{eq:reference-width-floor} w_t^{\\rm tr}(a):=e^{\\bar D_t/2}\\sqrt{\\kappa_{+,t}}\\hat s_t(a) \\ge \\bar s_t(a).',
    '\\label{eq:regret-definition-new} \\operatorname{reg}_t :=\\sup_{a\\in\\cA_t}\\mu_t^*(a)-\\mu_t^*(a_t), \\qquad R_T=\\sum_{t=1}^T\\operatorname{reg}_t.',
    '\\label{eq:relative-endpoint-sandwich} 0<c_{-,t}\\le c_{+,t}<\\infty,\\qquad c_{-,t}\\bVbar_t\\preceq\\bV_t\\preceq c_{+,t}\\bVbar_t.',
    '\\label{eq:relative-operator-certificate-new} \\|\\bV_t^{-1/2}(\\Calg_t-\\bV_t)\\bV_t^{-1/2}\\|_{\\rm op} \\le\\varepsilon_t<1',
    '\\label{eq:scalar-factor-path-new} \\sigma^{-1}\\nabla_\\theta\\mu_{\\btheta_s+ \\tau(\\btheta_t-\\btheta_s)}(x_s,a_s)^\\top.',
    '\\label{eq:tanh-category-relative} c_{-,t}=\\min\\!\\left\\{1,\\min_{c:n_{t,c}>0}\\frac{g_{t,c}}{f_{t,c}}\\right\\}, \\qquad c_{+,t}=\\max\\!\\left\\{1,\\max_{c:n_{t,c}>0}\\frac{g_{t,c}}{f_{t,c}}\\right\\},',
    '\\label{eq:tanh-uniform-relative} \\ell^2\\bVbar_t\\preceq\\bV_t\\preceq\\ell^{-2}\\bVbar_t, \\qquad d_{\\rm Th}(\\bVbar_t,\\bV_t) \\le4\\log\\cosh(B_\\phi R/\\sqrt W).',
    '\\label{eq:transported-score-new} U_t(a)=m_t(a) +\\beta_t e^{\\bar D_t/2}\\sqrt{\\kappa_{+,t}}\\,\\hat s_t(a) +b_t(a),',
    '\\le 2\\beta_t\\bar s_t(a_t)+2b_t(a_t)+\\xi_t,\\nonumber',
    '\\le 2\\sqrt{\\left(\\sigma^2+\\frac{G^2}{\\lambda}\\right) \\gamma_T\\sum_{t=1}^T\\beta_t^2} +2\\sum_{t=1}^Tb_t(a_t)+\\sum_{t=1}^T\\xi_t. \\label{eq:frozen-width-regret}',
    '\\le 2e^{D_{T,W}} \\Biggl[',
    '\\le \\sqrt{\\left(\\sigma^2+\\frac{G^2}{\\lambda}\\right)\\gamma_T \\sum_{t=1}^T\\beta_t^2 \\left[1+\\alpha_t e^{\\bar D_t} \\sqrt{\\frac{\\kappa_{+,t}}{\\kappa_{-,t}}}\\right]^2} \\nonumber',
    '\\le e^{\\bar D_t}\\kappa_{+,t}s_{\\Calg,t}^2(a),',
    '\\le e^{\\bar D_t}\\kappa_{-,t}^{-1}\\bar s_t^2(a). \\label{eq:two-way-width-new}',
    '\\le2\\sqrt{\\left(\\sigma^2+\\frac{G^2}{\\lambda}\\right)\\gamma_T \\sum_{t=1}^T\\alpha_t^2\\beta_t^2e^{2\\bar D_t} \\frac{\\kappa_{+,t}}{\\kappa_{-,t}}} \\nonumber',
    '\\le\\beta_t h_t\\bar s_t(a_t)+2b_t(a_t)+\\xi_t,\\nonumber',
    '\\le\\beta_t\\!\\left[1+\\alpha_te^{\\bar D_t} \\sqrt{\\frac{\\kappa_{+,t}}{\\kappa_{-,t}}}\\right]\\bar s_t(a_t) +2b_t(a_t)+\\xi_t,',
    '\\le\\beta_t\\bar s_t(a_t) +\\beta_t\\sqrt{c_{+,t}\\kappa_{+,t}}\\hat s_t(a_t) +2b_t(a_t)+\\xi_t',
    '\\le\\beta_t\\bar s_t(a_t) +\\beta_te^{\\bar D_t/2}\\sqrt{\\kappa_{+,t}}\\hat s_t(a_t) +2b_t(a_t)+\\xi_t',
    '\\le\\beta_t\\left[1+\\alpha_t \\sqrt{\\frac{c_{+,t}\\kappa_{+,t}}{c_{-,t}\\kappa_{-,t}}}\\right] \\bar s_t(a_t)+2b_t(a_t)+\\xi_t.',
    '\\le\\sqrt{\\left(\\sigma^2+\\frac{G^2}{\\lambda}\\right) \\gamma_T\\sum_{t=1}^T\\beta_t^2h_t^2} +2\\sum_{t=1}^Tb_t(a_t)+\\sum_{t=1}^T\\xi_t. \\label{eq:relative-endpoint-regret}',
    '\\le\\sqrt{\\left(\\sigma^2+\\frac{G^2}{\\lambda}\\right)\\gamma_T \\sum_{t=1}^T\\beta_t^2 \\left[1+\\alpha_t\\frac{1+\\chi_t}{1-\\chi_t} \\sqrt{\\frac{\\kappa_{+,t}}{\\kappa_{-,t}}}\\right]^2} \\nonumber',
    '\\nabla_\\theta^2\\mu_{\\btheta,W}(z)',
    '\\quad+2E_T^{\\rm cur}+\\sum_{t=1}^T\\xi_t. \\label{eq:finite-d-rate-new-display}',
    '\\quad+2\\sum_{t=1}^Tb_t(a_t)+\\sum_{t=1}^T\\xi_t \\label{eq:simple-transport-regret-new}',
    '\\quad+2\\sum_{t=1}^Tb_t(a_t)+\\sum_{t=1}^T\\xi_t. \\label{eq:local-small-drift-regret-new}',
    '\\quad+2\\sum_{t=1}^Tb_t(a_t)+\\sum_{t=1}^T\\xi_t.\\label{eq:sharp-transport-regret-new}',
    '\\quad+\\frac1\\sigma\\sqrt{\\sum_{s<t} [\\epsilon_{\\rm lin}(s)+\\epsilon_{\\rm mis}(s)]^2}.',
    '\\quad+\\frac{2c_\\mu R^2\\sqrt T}{\\sigma\\sqrt W}',
    '\\quad+\\frac{4c_\\mu R^2T}{\\sqrt W}. \\label{eq:global-near-linear-new}',
    '\\quad\\times \\sqrt{\\sigma^2+\\frac{G^2}{\\lambda}}\\, \\sqrt{T\\Gamma_{T,d}}\\nonumber',
    '\\quad{}\\times \\left[\\sqrt{\\Gamma_{T,d}+2\\log(1/\\delta)}+\\sqrt\\lambda S +\\frac{\\sqrt{B_T}}{\\sigma}\\right]\\nonumber',
    '\\quad{}\\times \\sqrt{\\left(\\sigma^2+\\frac{G^2}{\\lambda}\\right)T\\Gamma_{T,d}} \\nonumber',
    '\\sqrt{\\Gamma_{T,d}+2\\log(1/\\delta)}+\\sqrt\\lambda R',
    'and require the same finite measurable supremum and approximate-selector condition for this score. Keep every other hypothesis of that theorem. On the joint confidence and certificate event, writing $h_t=1+\\alpha_t\\sqrt{c_{+,t}\\kappa_{+,t}/(c_{-,t}\\kappa_{-,t})}$,',
    'd_{\\rm Th}(\\bV(0),\\bV(1))',
    'gives $\\kappa_{-,t}=1-\\varepsilon_t$ and $\\kappa_{+,t}=1+\\varepsilon_t$. An upper comparison alone does not imply a lower factor.',
    'holds. The bias envelope enters twice and the approximate-oracle error enters once. If the confidence event has probability at least $1-\\delta$ and the joint certificate event has probability at least $1-\\delta_{\\rm cert}$, these bounds hold with probability at least $1-\\delta-\\delta_{\\rm cert}$.',
    's_t^2(a)',
    's_{\\Calg,t}^2(a)',
    'use the local score obtained from \\eqref{eq:transported-score-new} by replacing $e^{\\bar D_t/2}$ with $1+\\chi_t$.',
    'where $\\Phi_t=[\\bq_1(a_1)/\\sigma,\\ldots, \\bq_{t-1}(a_{t-1})/\\sigma]$. The self-normalized martingale inequality bounds the middle term in $\\bVbar_t^{-1}$ norm by $\\sqrt{\\gamma_{t-1}+2\\log(1/\\delta)}$ simultaneously over $t$. The ridge term is at most $\\sqrt\\lambda S$. Finally, $\\bVbar_t=\\lambda\\bI+\\Phi_t\\Phi_t^\\top$ implies $\\Phi_t^\\top\\bVbar_t^{-1}\\Phi_t\\preceq\\bI$, so \\[ \\left\\|\\frac1\\sigma\\Phi_t e\\right\\|_{\\bVbar_t^{-1}} \\le\\frac{\\|e\\|_2}{\\sigma} \\le\\frac1\\sigma\\sqrt{\\sum_{s<t} [\\epsilon_{\\rm lin}(s)+\\epsilon_{\\rm mis}(s)]^2}. \\] Cauchy--Schwarz in the $\\bVbar_t$ metric bounds $|\\bq_t(a)^\\top(\\btheta^\\circ-\\hat\\btheta_t^{\\rm lin})|$ by $\\beta_t^{\\rm corr}\\bar s_t(a)$.',
    'with $c_{-,1}=c_{+,1}=1$ for an empty history. It satisfies \\eqref{eq:relative-endpoint-sandwich} and $\\ell^2\\le c_{-,t}\\le1\\le c_{+,t}\\le\\ell^{-2}$. Either certificate can be used in \\Cref{cor:relative-endpoint-ucb}.',
    '{An endpoint certificate need not bound the synthetic path.} Consider one sample with scalar feature $\\phi=1$, collection parameter $-R$, and current parameter $R$, where $R>0$. Write $\\ell=\\operatorname{sech}^2(R/\\sqrt W)$ with $W>0$. The endpoint metrics are equal to $\\lambda+\\sigma^{-2}\\ell^2$, so their Thompson distance is zero and the category factors are $m=M=1$. Along the synthetic interpolation \\eqref{eq:scalar-factor-path-new}, however, the scalar metric is \\[ V(\\tau)=\\lambda+\\sigma^{-2} \\operatorname{sech}^4((2\\tau-1)R/\\sqrt W). \\] It increases up to $\\tau=1/2$ and then decreases, giving path length \\[ \\int_0^1\\frac{|\\dot V(\\tau)|}{V(\\tau)}\\,d\\tau =2\\log\\!\\left(\\frac{\\lambda+\\sigma^{-2}} {\\lambda+\\sigma^{-2}\\ell^2}\\right)>0. \\] Thus \\Cref{cor:tanh-relative-weights} controls endpoint comparison, not the length used by the original synthetic-path certificate.',
    '{Bound nonvacuity.} The cumulative guarantee is vacuous in every original-study cell. The median of the per-trajectory terminal sharp-RHS/regret ratios is $126.7$--$155.7$ over the full grid and $126.7$--$135.0$ at $T=1000$. No run has zero regret. Since $|\\mu^*(z)|\\le\\|\\phi(z)\\|\\|\\btheta^\\circ\\|\\le1$, cumulative pseudo-regret has the deterministic cap $2T$. In every cell the theorem bound also exceeds this cap: the median right-hand sides are $3{,}989$--$12{,}607$, versus caps of $500$--$2{,}000$.',
    "{Certificate tightness.} At $T=1000$, the median of each trajectory's maximum realized $\\bar D_t^Q$ ranges from $0.0486$ to $0.384$ across target cells. The corresponding median of trajectory-maximum endpoint distances ranges from $1.31\\times10^{-7}$ to $8.74\\times10^{-6}$; both summaries have 50 trajectory-level observations per cell. At the 100 declared checkpoints per trajectory, pooling the 5,000 eligible seed--checkpoint ratios gives a median selected factor-path length only $1.20$--$1.22$ times the endpoint distance, while $\\bar D_t^Q$ is $2.51\\times10^5$--$1.88\\times10^6$ times the selected-path diagnostic. The large ratio accompanies extremely small realized metric motion. Measured directly against the endpoint distance rather than against the selected path, the median $\\bar D_t^Q/d_{\\rm Th}$ ratio is $3.07\\times10^5$--$2.24\\times10^6$ at $T=1000$, so the analytic certificate is conservative by five to six orders of magnitude on this grid. The reported median $e^{\\bar D_t^Q/2}$, by contrast, pools all 50,000 seed--round values in a $T=1000$ cell and ranges from $1.02$ to $1.18$ across the four target cells at that horizon; it is not a terminal or run-maximum summary.",
    "{Controlled evidence.} The prespecified nonlinear-regime follow-up uses a 29-parameter scaled-tanh model with dense matrices and direct Cholesky solves in float64 (\\Cref{sec:transport-followup}); the original near-linear audit is retained separately in \\Cref{sec:transport-instantiation}. Four policies are evaluated in three conditions, with 50 paired seeds per condition. All nine pointwise paired intervals favor the comparators over Hessian transport. Its bounds are dominated by path inflation in the follow-up, whereas the original grid's decomposition is base-dominated. The frozen policy's own-trajectory bounds also remain vacuous. All follow-up policies, including the uncertified naive control, pass the recorded optimism diagnostics; these floating-point checks do not establish verified numerical certification.",
    "{Exploratory decision analysis.} After observing these outcomes, we independently recomputed score diagnostics from all 600 preserved trajectories. On Hessian's own histories, its selected action equals the current-width argmax on 99.382\\%, 99.962\\%, and 99.982\\% of rounds for $W=16,1,0.25$. A stronger sufficient condition---the bonus gap between the two largest widths exceeding the entire range of prediction centers---holds on 97.104\\%, 99.372\\%, and 99.508\\% of rounds. These pooled fractions describe extensive width-dominated selection in the visited states, not an adaptive causal mechanism or an independent-round test. The per-seed mechanism table in \\Cref{app:transport-followup} applies this same Hessian score to all four behavior histories; it does not report width dominance of each behavior policy's own score. The appendix also compares alternative score recommendations on fixed histories and checks early numerical ranking sensitivity. The fixed-history comparisons respect \\Cref{prop:reference-width-floor}: tightening a transport certificate does not create additional statistical information or order policies' adaptive regret.",
    '{Exploratory per-seed variation in Hessian-score recommendations on all four behavior histories. Every row evaluates the Hessian score; row labels identify the history-generating policy. Entries are the median percentage of rounds and the minimum--maximum range across 50 seeds. Width argmax uses the exact smallest-index tie rule; the strict condition is the bonus-gap inequality above.} \\label{tab:transport-followup-mechanism-variation} \\input{tables/transport_followup_mechanism_variation.tex}',
    "{Exploratory relative certificates on Hessian's recorded histories. The upper panel averages effective-width/reference-width ratios over all five candidate actions and 1000 rounds, then over 50 seeds per condition; the direct reference ratio is identically one. The lower panel averages one-step pseudo-regret of recommendations on these same states. Uniform uses $D_0$; the category columns use symmetric and separate outward factors. These are fixed-history diagnostics, not adaptive policy outcomes.} \\label{tab:transport-followup-relative-audit} \\input{tables/transport_followup_relative_audit.tex}",
    '{Exploratory tighter endpoint certificates.} The relative-weight construction in \\Cref{cor:tanh-relative-weights} permits uniform and category-specific endpoint comparisons without using the Hessian path envelope. We audit these comparisons on the same 600 recorded histories, replaying representation updates with the recorded actions and rewards. On primary histories, the category-specific outward factor gives mean effective-width overheads of $0.28\\%$--$12.68\\%$ relative to the direct reference width, versus $0.16\\%$--$12.13\\%$ for the dense endpoint factor across conditions (\\Cref{app:transport-followup}). These are means of actionwise ratios, not ratios of mean widths. This analysis evaluates new scores on existing states; it does not evaluate a new adaptive policy or demonstrate an end-to-end computational advantage. The relative certificate bounds an endpoint comparison, not the original interpolated factor-path length, and does not remove the historical and current approximation-error charges.',
    '{Meaning of the cumulative bound decomposition.} For a transport-Hessian trajectory, write $P_T=(\\sigma^2+G^2/\\lambda)\\gamma_T$ and $\\beta_t^{\\rm stat}=\\sqrt{\\gamma_{t-1}+2\\log(1/\\delta)}+\\sqrt\\lambda S$. The reported components are',
    '{Model and prespecified protocol.} We use Gaussian observations with mean $\\mu_{\\btheta}(z)=\\sqrt W\\tanh(\\phi(z)^\\top\\btheta/\\sqrt W)$, with $\\|\\phi(z)\\|_2\\le1$ and projected parameters $\\|\\btheta\\|_2\\le1$. Contexts have dimension four, there are five actions, and the context--action feature map has dimension 29. Noise has standard deviation $0.25$, the metric ridge is one, and the confidence parameter is $\\delta=0.05$. A fixed teacher generates the rewards. We fix $T=1000$ and $W\\in\\{16,1,0.25\\}$, with 50 common evaluation seeds per condition and four policies. Changing $W$ changes both the reward function and its curvature; cross-condition trends do not isolate a causal effect of metric drift. The conditions were specified before their evaluation outcomes were observed. Development, tuning, and evaluation use disjoint seed sets.',
    '{Optimal experimental design.} Information-theoretic exploration objectives---such as maximizing $\\log\\det(\\bVbar_t)$ or minimizing the trace of~$\\bVbar_t^{-1}$---connect bandit exploration to the classical D-optimal and A-optimal design criteria \\citep{valko2013finite}. Stochastic trace and log-determinant estimators provide related matrix-free tools \\citep{ubaru2017fast}. Here the frozen log-determinant appears in the regret analysis; the audited policy selects actions by its UCB score and does not implement these estimators.',
    "{Original near-linear audit for the transport-Hessian policy. Coverage is run-level simultaneous coverage with exact Clopper--Pearson intervals. The two median-maximum columns first maximize within each trajectory, then take the median over 50 runs per cell. ``Event viol.'' counts theorem-bound violations only when the joint confidence premise holds. All values come from the full evaluation; smoke and tuning runs are excluded.} \\label{tab:transport-instantiation-validity} \\evidencetabular{@{} >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{     } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    }@{}}{ \\input{tables/transport_instantiation_validity.tex}}",
    '{Original near-linear study.} For \\Cref{sec:transport-instantiation}, the retained full aggregate, generated tables and figures, provenance sidecars, and detached verifier support aggregate-derived checks. The original per-run trajectories and per-seed observations remain unavailable. Their inventory digests do not establish access to or integrity of the missing raw bytes. In particular, the original paired bootstrap cannot be recomputed from the aggregate alone; no per-seed values have been synthesized to replace it. The historical dependency records also disagree: requirements specify SciPy 1.15.2 while a retained host-specific wheel link names SciPy 1.13.1. Two selection-time sources, the artifact renderer and Buck build declaration, differ from their recorded digests. The verifier reports these gaps explicitly. Fresh runs and dependency locks do not repair the historical runtime or source provenance.',
    "{Original-study certificate and bound tightness for the transport-Hessian policy. The reported summary statistics are medians over the following populations. Terminal historical-radius and cumulative current-bias entries, and terminal width/bound ratios summarize 50 runs per cell. Path ratios pool eligible seed--round or seed--checkpoint observations, while $e^{\\bar D_t^Q/2}$ pools all seed--round values. $n_0$ counts denominators at or below the preregistered ratio tolerance that are excluded from that ratio. ``Width/potential'' is the frozen squared-width sum divided by its elliptic-potential upper bound; ``Sharp/simple'' is the sharp cumulative right-hand side divided by the simpler right-hand side.} \\label{tab:transport-instantiation-tightness} \\evidencetabular{@{} >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    }@{}}{ \\input{tables/transport_instantiation_tightness.tex}}",
    '{Original-study mean cumulative pseudo-regret at $T=1000$. Shaded bands are pointwise paired-bootstrap 95\\% intervals over the 50 evaluation seeds, not simultaneous confidence bands. All four methods are plotted; curves can coincide where their selected actions agree.} \\label{fig:transport-instantiation-regret}',
    '{Original-study path-certificate conservatism on log--log axes. Blue circles bin the per-round Hessian/$Q_t$ certificate $\\bar D_t^Q$ against endpoint Thompson distance. Orange triangles bin the numerical selected factor-path length at preregistered checkpoints. Each target panel pools eligible observations from the three independently executed horizons. Markers are plotted at geometric bin centers, marker size encodes bin count, and the dashed line is equality. Values at or below the preregistered $10^{-12}$ ratio tolerance, including round-one zeros, are omitted from the log axes and counted in \\Cref{tab:transport-instantiation-tightness}. Quadrature and generalized-eigenvalue calculations are dense float64 diagnostics, not verified certificates.} \\label{fig:transport-instantiation-tightness}',
    '{Original-study per-round mean cumulative decomposition over 50 transport-Hessian trajectories at $T=1000$. On this near-linear grid, the base confidence component, which includes the regularization/norm-bound term, dominates; historical linearization, path inflation, and current bias are shown separately. The red sharp right-hand side remains far above realized regret in every target condition.} \\label{fig:transport-instantiation-bound}',
    '{Original-study policy outcomes at the primary horizon $T=1000$. Mean-regret and paired-difference intervals are comparisonwise deterministic paired-bootstrap 95\\% intervals over the same 50 evaluation seeds. Each difference is the row method minus transport Hessian, so negative values favor the row method. Transport endpoint is a dense diagnostic comparator; naive current is an uncertified negative control.} \\label{tab:transport-instantiation-performance} \\evidencetabular{@{} >{\\raggedleft\\arraybackslash}p{    } >{\\raggedright\\arraybackslash}p{     } >{\\raggedright\\arraybackslash}p{     } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{     } >{\\raggedleft\\arraybackslash}p{    }@{}}{ \\input{tables/transport_instantiation_performance.tex}}',
    "{Policy outcomes.} At $T=1000$, mean regret for the operational Hessian-certificate policy rises from $81.0$ to $94.0$ across the four target conditions (\\Cref{tab:transport-instantiation-performance}). All three comparison policies have lower sample-mean pseudo-regret than transport Hessian in every reported condition at this horizon. These are matched-stream total-policy comparisons: the policies share contexts and potential outcomes, but their actions, fitted parameters, centers, radii, and widths may diverge after the first disagreement. The endpoint comparison is consistent with conservatism in the analytic envelope, but it does not isolate a fixed-history mechanism and does not provide a scalable policy certificate; it is a dense diagnostic comparator rather than a deployable policy. The naive score's observed optimism does not make it theoretically valid. Since $D_{\\rm target}$ also changes $W$, the cross-condition pattern is not a causal dose response. Read in the intended direction, these outcomes do not show a causal or uniform advantage for full curvature, and the reverse ordering they record is specific to this environment, this certificate, and this horizon.",
    '{Positive-cone metric geometry.} \\citet{thompson1963certain} introduced the part metric now commonly called the Thompson metric on ordered cones. \\citet{nussbaum1994finsler} developed its Finsler structure and applications. On the positive-definite cone, the normalized operator norm $\\|V^{-1/2}\\dot V V^{-1/2}\\|_{\\rm op}$ is the corresponding tangent norm. Our contribution is not this geometry or its path-to-endpoint comparison. We instantiate it as an operational confidence-transport device linking frozen bandit confidence, current replayed GGN/Fisher curvature, approximate operators, and certified solver widths.',
    "{Prespecified drift and bound diagnostics. The maximum and threshold counts use Hessian's 50,000 seed--round observations per condition; thresholds use $\\ge$. Mean terminal right-hand sides (RHS) use each named policy's own 50 histories. All individual primary and frozen-policy bounds exceed the corresponding deterministic regret cap.} \\label{tab:transport-followup-drift-bounds} \\input{tables/transport_followup_drift_bounds.tex}",
    '{Prespecified follow-up.} For \\Cref{sec:transport-followup}, the retained portable export contains all 600 evaluation seed summaries, the development and tuning summaries, selected optimizer, exact source and execution configurations, run provenance, terminal bound decompositions, drift summaries, and a raw-input hash inventory. An independent verifier reconstructs the reported terminal intervals from the seed summaries. The pinned Python environment and scientific source digests are recorded. Identifying metadata is redacted in packaged copies without changing scientific values; the declarations record their original and packaged digests. Full raw trajectories are retained outside Git and are not included in the compact supplement. The portable export alone does not reproduce every roundwise audit or regret-curve interval. A durable public raw-bundle URL is not provided.',
    "{Prespecified full-study outcomes at $T=1000$, with 50 paired evaluation seeds per condition. $\\Delta$ is the row policy's cumulative pseudo-regret minus Hessian's. All nine intervals are pointwise 95\\% paired bootstrap intervals; no simultaneous coverage is asserted.} \\label{tab:transport-followup-outcomes} \\input{tables/transport_followup_outcomes.tex}",
    '{Prespecified policy outcomes.} Hessian transport has higher mean cumulative pseudo-regret than every comparator in every condition (\\Cref{tab:transport-followup-outcomes}). All nine paired 95\\% intervals for comparator-minus-Hessian regret exclude zero. These are pointwise intervals from 10,000 paired seed-bootstrap resamples per comparison, without multiplicity adjustment. They quantify evaluation-seed variation conditional on the fixed teacher, design, and selected optimizer; they do not include uncertainty from environment selection or tuning. The comparisons are total-policy outcomes on matched exogenous streams, not fixed-history interventions. They establish neither a universal policy ordering nor a causal attribution to the certificate alone.',
    '{Protocol and timing.} Let $(\\mathsf A,\\mathcal B)$ be a standard Borel action space. At round $t$, the learner observes a context and a nonempty random action correspondence $\\cA_t:\\Omega\\to 2^{\\mathsf A}$ whose graph \\[ \\operatorname{Gr}(\\cA_t) :=\\{(\\omega,a):a\\in\\cA_t(\\omega)\\} \\in\\cHist_t^-\\otimes\\mathcal B. \\] Here $\\cHist_t^-$ is the history after the context and action correspondence are observed but before fresh round-$t$ algorithmic randomization. The variable $\\Omega_t$ records all round-$t$ pre-reward randomization, which may be revealed in sequential stages, and $\\cHist_t=\\cHist_t^-\\vee\\sigma(\\Omega_t)$ contains that randomization but not the reward. The restrictions to $\\operatorname{Gr}(\\cA_t)$ of $(\\omega,a)\\mapsto\\mu_t^*(a),\\bq_t(a),m_t(a),b_t(a),\\hat s_t(a)$, and, once defined below, $U_t(a)$ are assumed jointly measurable with respect to $\\cHist_t\\otimes\\mathcal B$. We also assume explicitly that $\\sup_{a\\in\\cA_t}\\mu_t^*(a)$ and $\\sup_{a\\in\\cA_t}U_t(a)$ are finite $\\cHist_t$-measurable random variables, that the oracle below returns a $\\cHist_t$-measurable selector in $\\cA_t$, and that the simultaneous confidence and all certificate events below, including path, operator, all-domain solver-upper, and played-action sharpness validity, are measurable. These are substantive assumptions; standard-Borel structure and graph measurability alone do not make every supremum or selector measurable.',
    '{Protocol.} We use the finite-dimensional scaled-tanh Gaussian specialization of \\Cref{cor:global-near-linear-new}. Contexts have dimension $4$, there are five actions, and the normalized context--action feature map has dimension $29$. The frozen and current matrices are formed densely, all widths use float64 Cholesky solves, and finite enumeration uses the smallest-index tie rule. Thus the intended theorem interface has \\[ \\alpha_t=1,\\qquad \\kappa_{-,t}=\\kappa_{+,t}=1,\\qquad \\xi_t=0. \\] These equalities describe the exact operator, solve, and selection abstractions. The recorded floating-point checks are diagnostics, not verified numerical certificates.',
    '{Realized drift, validity diagnostics, and vacuous bounds.} The primary policy reaches endpoint distances above one in 16 of 50 seeds at $W=0.25$, including 286 of 50,000 seed--round observations (\\Cref{tab:transport-followup-drift-bounds}). These round counts describe dependent observations, not additional independent replications. Target labels used to encode $W$ are not realized distances. All 600 evaluation trajectories, including naive current, pass the recorded simultaneous reference-confidence, method-optimism, and deterministic diagnostics. Each policy--condition cell has 50 successes out of 50, with an exact 95\\% Clopper--Pearson interval of approximately $[92.9\\%,100\\%]$. This observation does not establish population coverage, validate the theorem, or show that transport is necessary. Float64 checks and converged quadrature are numerical diagnostics, not verified enclosures.',
    '{Validity audit.} For the primary policy, every one of the same 50 base seeds in each of the 12 horizon--target cells retained simultaneous reference confidence and transported optimism. The cellwise exact 95\\% Clopper--Pearson interval is $[92.9\\%,100\\%]$. Reusing base seeds across cells supports paired comparisons within a condition, not a pooled sample of 600 independent runs. The strict aggregate accepted all 2400 policy trajectories with no deterministic algebra or certificate-check failure, and the primary policy had no bound violation on the joint confidence event (\\Cref{tab:transport-instantiation-validity}). This finite-sample observation does not prove or empirically validate the theorem. In particular, ordinary float64 Cholesky, eigenvalue, and quadrature checks are not verified enclosures.',
    '} \\newcommand{\\ccetablesize}{} \\newcommand{\\evidencetabular}[2]{ \\begingroup \\let\\ccerealtabular\\tabular \\renewcommand{\\tabular}[2][c]{\\ccerealtabular[##1]{#1}} #2 \\endgroup}',
)


def _u(*cited: tuple[int, int]) -> tuple[tuple[str, int], ...]:
    """Resolve `(unit index, offset)` pairs against UNITS."""

    return tuple((UNITS[index], offset) for index, offset in cited)


#: (path, phrase) -> (occurrences, ((unit, offset-in-unit), ...))
PHRASE_PINS: dict[tuple[str, str], tuple[int, tuple[tuple[str, int], ...]]] = {
    # paper/availability.tex
    ('paper/availability.tex', '600 evaluation seed summaries'):
        (1, _u((184, 103))),
    # paper/body_intro.tex
    ('paper/body_intro.tex', '29-parameter'):
        (1, _u((166, 74))),
    ('paper/body_intro.tex', '50 paired seeds'):
        (1, _u((166, 343))),
    # paper/legacy_scope.tex
    ('paper/legacy_scope.tex', '29-parameter'):
        (1, _u((54, 350))),
    # paper/transport_experiment.tex
    ('paper/transport_experiment.tex', '$1.20$--$1.22$ times the endpoint distance'):
        (1, _u((165, 485))),
    ('paper/transport_experiment.tex', '$1.88\\times10^6$'):
        (1, _u((165, 569))),
    ('paper/transport_experiment.tex', '$126.7$--$135.0$ at $T=1000$'):
        (1, _u((164, 195))),
    ('paper/transport_experiment.tex', '$2.0\\%$--$16.3\\%$'):
        (1, _u((56, 325))),
    ('paper/transport_experiment.tex', '$2.24\\times10^6$'):
        (1, _u((165, 839))),
    ('paper/transport_experiment.tex', '$2.51\\times10^5$'):
        (1, _u((165, 551))),
    ('paper/transport_experiment.tex', '$3{,}989$--$12{,}607$'):
        (1, _u((164, 448))),
    ('paper/transport_experiment.tex', '$79.4\\%$--$97.3\\%$'):
        (1, _u((56, 214))),
    ('paper/transport_experiment.tex', '$8.74\\times10^{-6}$'):
        (1, _u((165, 254))),
    ('paper/transport_experiment.tex', '$9{,}948$--$10{,}010$'):
        (1, _u((56, 601))),
    ('paper/transport_experiment.tex', '$T=1000$'):
        (8, _u((60, 1373), (165, 28), (165, 859), (165, 1056), (164, 215), (56, 172), (181, 22), (180, 55))),
    ('paper/transport_experiment.tex', '$[92.9\\%,100\\%]$'):
        (1, _u((190, 240))),
    ('paper/transport_experiment.tex', '$\\log 5\\approx1.609$'):
        (1, _u((60, 1690))),
    ('paper/transport_experiment.tex', '$e^{\\bar D_t^Q/2}$'):
        (1, _u((165, 982))),
    ('paper/transport_experiment.tex', '100 declared checkpoints per trajectory'):
        (1, _u((165, 345))),
    ('paper/transport_experiment.tex', '20 full-batch steps'):
        (1, _u((60, 1165))),
    ('paper/transport_experiment.tex', '5,000\neligible seed--checkpoint ratios'):
        (1, _u((165, 398))),
    ('paper/transport_experiment.tex', '50 evaluation seeds'):
        (2, _u((60, 58), (180, 188))),
    ('paper/transport_experiment.tex', '50 runs per cell'):
        (1, _u((174, 241))),
    ('paper/transport_experiment.tex', '50 trajectory-level observations per cell'):
        (1, _u((165, 295))),
    ('paper/transport_experiment.tex', '50 transport-Hessian trajectories'):
        (1, _u((56, 396))),
    ('paper/transport_experiment.tex', '600 independent runs'):
        (1, _u((190, 361))),
    ('paper/transport_experiment.tex', 'All five actions are optimal somewhere in every'):
        (1, _u((60, 1562))),
    ('paper/transport_experiment.tex', 'Contexts have dimension $4$'):
        (1, _u((188, 116))),
    ('paper/transport_experiment.tex', 'No run has zero regret'):
        (1, _u((164, 225))),
    ('paper/transport_experiment.tex', 'Ten disjoint tuning seeds'):
        (1, _u((60, 1095))),
    ('paper/transport_experiment.tex', '\\alpha_t=1'):
        (1, _u((188, 428))),
    ('paper/transport_experiment.tex', '\\kappa_{-,t}=\\kappa_{+,t}=1'):
        (1, _u((188, 446))),
    ('paper/transport_experiment.tex', '\\xi_t=0'):
        (1, _u((188, 481))),
    ('paper/transport_experiment.tex', 'all 2400 policy\ntrajectories'):
        (1, _u((190, 413))),
    ('paper/transport_experiment.tex', 'best-fixed-action regret $180.4$'):
        (1, _u((60, 1478))),
    ('paper/transport_experiment.tex', 'cap $2{,}000$'):
        (1, _u((56, 642))),
    ('paper/transport_experiment.tex', 'deterministic cap $2T$'):
        (1, _u((164, 337))),
    ('paper/transport_experiment.tex', 'each of the 12\nhorizon--target cells'):
        (1, _u((190, 81))),
    ('paper/transport_experiment.tex', 'exact 95\\% Clopper--Pearson interval'):
        (1, _u((190, 200))),
    ('paper/transport_experiment.tex', 'feature map has dimension $29$'):
        (1, _u((188, 204))),
    ('paper/transport_experiment.tex', 'horizons $T\\in\\{250,500,1000\\}$'):
        (1, _u((60, 25))),
    ('paper/transport_experiment.tex', 'is $126.7$--$155.7$ over the'):
        (1, _u((164, 152))),
    ('paper/transport_experiment.tex', 'is $3.07\\times10^5$'):
        (1, _u((165, 818))),
    ('paper/transport_experiment.tex', 'learning rate $3\\times10^{-4}$'):
        (1, _u((60, 1130))),
    ('paper/transport_experiment.tex', 'mean-only regret $185.4$'):
        (1, _u((60, 1536))),
    ('paper/transport_experiment.tex', 'no bound violation on the joint confidence event'):
        (1, _u((190, 529))),
    ('paper/transport_experiment.tex', 'no deterministic algebra or certificate-check failure'):
        (1, _u((190, 447))),
    ('paper/transport_experiment.tex', 'optimal-action\nentropy $1.579$'):
        (1, _u((60, 1422))),
    ('paper/transport_experiment.tex', 'optimality\ngap $0.123$'):
        (1, _u((60, 1454))),
    ('paper/transport_experiment.tex', 'paired-bootstrap 95\\%'):
        (1, _u((180, 142))),
    ('paper/transport_experiment.tex', 'pools all 50,000 seed--round values'):
        (1, _u((165, 1015))),
    ('paper/transport_experiment.tex', 'ranges from\n$1.02$'):
        (1, _u((165, 1074))),
    ('paper/transport_experiment.tex', 'ranges from $0.0486$'):
        (1, _u((165, 100))),
    ('paper/transport_experiment.tex', 'ranges from $1.31\\times10^{-7}$'):
        (1, _u((165, 219))),
    ('paper/transport_experiment.tex', 'rises\nfrom $81.0$'):
        (1, _u((181, 91))),
    ('paper/transport_experiment.tex', 'target labels $D_{\\rm target}\\in\\{0.25,0.5,1,2\\}$'):
        (1, _u((60, 83))),
    ('paper/transport_experiment.tex', 'the 50-seed means'):
        (1, _u((60, 1395))),
    ('paper/transport_experiment.tex', 'the same 50 base seeds'):
        (1, _u((190, 55))),
    ('paper/transport_experiment.tex', 'there are five actions'):
        (1, _u((188, 145))),
    ('paper/transport_experiment.tex', 'to $0.384$'):
        (1, _u((165, 121))),
    ('paper/transport_experiment.tex', 'to $1.18$'):
        (1, _u((165, 1093))),
    ('paper/transport_experiment.tex', 'to $94.0$'):
        (1, _u((181, 109))),
    ('paper/transport_experiment.tex', 'versus caps of $500$--$2{,}000$'):
        (1, _u((164, 471))),
    # paper/transport_experiment_appendix.tex
    ('paper/transport_experiment_appendix.tex', '$2.01\\%,4.04\\%,8.16\\%,16.27\\%$'):
        (1, _u((66, 566))),
    ('paper/transport_experiment_appendix.tex', '$97.33\\%,94.66\\%,89.39\\%,79.39\\%$'):
        (1, _u((66, 516))),
    ('paper/transport_experiment_appendix.tex', '$D_{\\rm target}=0.25,0.5,1,2$'):
        (1, _u((66, 601))),
    ('paper/transport_experiment_appendix.tex', '$T=1000$'):
        (3, _u((66, 400), (177, 49), (179, 98))),
    ('paper/transport_experiment_appendix.tex', '$e^{\\bar D_t^Q/2}$'):
        (2, _u((66, 729), (176, 360))),
    ('paper/transport_experiment_appendix.tex', '50 evaluation seeds'):
        (2, _u((67, 267), (177, 127))),
    ('paper/transport_experiment_appendix.tex', '50 primary-policy trajectories'):
        (1, _u((66, 351))),
    ('paper/transport_experiment_appendix.tex', '50 runs per cell'):
        (1, _u((176, 264))),
    ('paper/transport_experiment_appendix.tex', '50 transport-Hessian trajectories'):
        (1, _u((179, 61))),
    ('paper/transport_experiment_appendix.tex', '\\kappa_{-,t}=\\kappa_{+,t}=1'):
        (1, _u((66, 115))),
    ('paper/transport_experiment_appendix.tex', '\\xi_t=0'):
        (1, _u((66, 149))),
    ('paper/transport_experiment_appendix.tex', 'paired-bootstrap 95\\%'):
        (1, _u((177, 86))),
    ('paper/transport_experiment_appendix.tex', 'preregistered $10^{-12}$ ratio tolerance'):
        (1, _u((178, 490))),
    # paper/transport_followup.tex
    ('paper/transport_followup.tex', '$0.16\\%$'):
        (1, _u((170, 515))),
    ('paper/transport_followup.tex', '$0.28\\%$'):
        (1, _u((170, 448))),
    ('paper/transport_followup.tex', '$12.13\\%$'):
        (1, _u((170, 525))),
    ('paper/transport_followup.tex', '$12.68\\%$'):
        (1, _u((170, 458))),
    ('paper/transport_followup.tex', '$T=1000$'):
        (2, _u((172, 470), (185, 37))),
    ('paper/transport_followup.tex', '$W=0.25$'):
        (1, _u((189, 137))),
    ('paper/transport_followup.tex', '$W=16,1,0.25$'):
        (2, _u((36, 116), (167, 278))),
    ('paper/transport_followup.tex', '$W\\in\\{16,1,0.25\\}$'):
        (1, _u((172, 483))),
    ('paper/transport_followup.tex', '$[92.9\\%,100\\%]$'):
        (1, _u((189, 673))),
    ('paper/transport_followup.tex', '$\\delta=0.05$'):
        (1, _u((172, 409))),
    ('paper/transport_followup.tex', '10,000'):
        (1, _u((186, 290))),
    ('paper/transport_followup.tex', '16 of 50 seeds'):
        (1, _u((189, 119))),
    ('paper/transport_followup.tex', '20 full-batch steps'):
        (1, _u((29, 653))),
    ('paper/transport_followup.tex', '2000, 2000, and 1000'):
        (1, _u((65, 170))),
    ('paper/transport_followup.tex', '286 of 50,000'):
        (1, _u((189, 157))),
    ('paper/transport_followup.tex', '29-parameter'):
        (1, _u((32, 159))),
    ('paper/transport_followup.tex', '294 development and tuning trajectories'):
        (1, _u((72, 192))),
    ('paper/transport_followup.tex', '50 common evaluation seeds'):
        (1, _u((172, 509))),
    ('paper/transport_followup.tex', '50 histories'):
        (1, _u((183, 224))),
    ('paper/transport_followup.tex', '50 paired evaluation seeds'):
        (1, _u((185, 52))),
    ('paper/transport_followup.tex', '50 successes out of 50'):
        (1, _u((189, 587))),
    ('paper/transport_followup.tex', '50,000 seed--round observations per condition'):
        (1, _u((183, 90))),
    ('paper/transport_followup.tex', '600 policy trajectories'):
        (1, _u((72, 156))),
    ('paper/transport_followup.tex', '97.104\\%'):
        (1, _u((167, 432))),
    ('paper/transport_followup.tex', '99.372\\%'):
        (1, _u((167, 442))),
    ('paper/transport_followup.tex', '99.382\\%'):
        (1, _u((167, 231))),
    ('paper/transport_followup.tex', '99.508\\%'):
        (1, _u((167, 456))),
    ('paper/transport_followup.tex', '99.962\\%'):
        (1, _u((167, 241))),
    ('paper/transport_followup.tex', '99.982\\%'):
        (1, _u((167, 255))),
    ('paper/transport_followup.tex', 'All 600 evaluation trajectories'):
        (1, _u((189, 396))),
    ('paper/transport_followup.tex', 'all 150 of its trajectories'):
        (1, _u((65, 293))),
    ('paper/transport_followup.tex', 'all 600 preserved trajectories'):
        (1, _u((167, 116))),
    ('paper/transport_followup.tex', 'dimension 29'):
        (1, _u((172, 301))),
    ('paper/transport_followup.tex', 'exact 95\\% Clopper--Pearson interval'):
        (1, _u((189, 619))),
    ('paper/transport_followup.tex', 'learning rate $3\\times10^{-4}$'):
        (1, _u((29, 617))),
    ('paper/transport_followup.tex', 'of 50,000 seed--round observations'):
        (1, _u((189, 161))),
    ('paper/transport_followup.tex', 'paired 95\\% intervals'):
        (1, _u((186, 183))),
    ('paper/transport_followup.tex', 'pointwise 95\\% paired'):
        (1, _u((185, 188))),
    ('paper/transport_followup.tex', 'regrets 180.01, 177.97, and 171.84'):
        (1, _u((36, 189))),
    ('paper/transport_followup.tex', 'regrets 185.26, 183.06, and 176.67'):
        (1, _u((36, 78))),
    ('paper/transport_followup.tex', 'same 600 recorded histories'):
        (1, _u((170, 248))),
    ('paper/transport_followup.tex', 'standard deviation $0.25$'):
        (1, _u((172, 325))),
    ('paper/transport_followup.tex', 'there are five actions'):
        (1, _u((172, 237))),
    # paper/transport_followup_appendix.tex
    ('paper/transport_followup_appendix.tex', '$0.00392155$'):
        (1, _u((57, 1147))),
    ('paper/transport_followup_appendix.tex', '$0.005$'):
        (1, _u((63, 731))),
    ('paper/transport_followup_appendix.tex', '$0.124$'):
        (1, _u((40, 148))),
    ('paper/transport_followup_appendix.tex', '$1.735$'):
        (1, _u((40, 157))),
    ('paper/transport_followup_appendix.tex', '$3\\times4\\times50=600$'):
        (1, _u((57, 1184))),
    ('paper/transport_followup_appendix.tex', '$4+5+20=29$'):
        (1, _u((57, 314))),
    ('paper/transport_followup_appendix.tex', '$5.300$'):
        (1, _u((40, 170))),
    ('paper/transport_followup_appendix.tex', '$\\{1,5,20\\}$'):
        (1, _u((57, 924))),
    ('paper/transport_followup_appendix.tex', '$\\{3\\times10^{-5},10^{-4},3\\times10^{-4}\\}$'):
        (1, _u((57, 875))),
    ('paper/transport_followup_appendix.tex', '10,000'):
        (1, _u((62, 130))),
    ('paper/transport_followup_appendix.tex', '1000 rounds in its denominator'):
        (1, _u((99, 439))),
    ('paper/transport_followup_appendix.tex', '1024'):
        (1, _u((28, 167))),
    ('paper/transport_followup_appendix.tex', '12 combinations'):
        (1, _u((37, 200))),
    ('paper/transport_followup_appendix.tex', '2--10'):
        (1, _u((61, 511))),
    ('paper/transport_followup_appendix.tex', '20 steps'):
        (1, _u((57, 1024))),
    ('paper/transport_followup_appendix.tex', '2048'):
        (3, _u((28, 90), (28, 176), (28, 257))),
    ('paper/transport_followup_appendix.tex', '24 declared trajectories'):
        (1, _u((28, 188))),
    ('paper/transport_followup_appendix.tex', '24 development trajectories'):
        (1, _u((57, 605))),
    ('paper/transport_followup_appendix.tex', '250-digit'):
        (1, _u((61, 146))),
    ('paper/transport_followup_appendix.tex', '270 tuning trajectories'):
        (1, _u((57, 705))),
    ('paper/transport_followup_appendix.tex', '294 development and tuning trajectories'):
        (1, _u((57, 1233))),
    ('paper/transport_followup_appendix.tex', '30 tuning'):
        (1, _u((57, 1096))),
    ('paper/transport_followup_appendix.tex', '30000--30001'):
        (1, _u((57, 58))),
    ('paper/transport_followup_appendix.tex', '30100--30109'):
        (1, _u((57, 85))),
    ('paper/transport_followup_appendix.tex', '30200--30249'):
        (1, _u((57, 120))),
    ('paper/transport_followup_appendix.tex', '4096'):
        (1, _u((28, 266))),
    ('paper/transport_followup_appendix.tex', '50 evaluation seeds'):
        (1, _u((62, 44))),
    ('paper/transport_followup_appendix.tex', '50 seeds per condition'):
        (1, _u((169, 191))),
    ('paper/transport_followup_appendix.tex', '50,000 dependent states'):
        (1, _u((37, 298))),
    ('paper/transport_followup_appendix.tex', '600,000 states'):
        (1, _u((61, 475))),
    ('paper/transport_followup_appendix.tex', '65 changes'):
        (1, _u((61, 458))),
    ('paper/transport_followup_appendix.tex', 'Candidate 008'):
        (1, _u((57, 974))),
    ('paper/transport_followup_appendix.tex', 'across 50 seeds'):
        (1, _u((168, 262))),
    ('paper/transport_followup_appendix.tex', 'all 600 trajectories'):
        (1, _u((63, 111))),
    ('paper/transport_followup_appendix.tex', 'and 1000 rounds'):
        (1, _u((169, 164))),
    ('paper/transport_followup_appendix.tex', 'at 16 states'):
        (1, _u((61, 354))),
    ('paper/transport_followup_appendix.tex', 'below 0.629'):
        (1, _u((61, 541))),
    ('paper/transport_followup_appendix.tex', 'divided by 1000'):
        (1, _u((37, 384))),
    ('paper/transport_followup_appendix.tex', 'learning rate $3\\times10^{-4}$'):
        (1, _u((57, 989))),
    ('paper/transport_followup_appendix.tex', 'rounds 1, 2, 10, 100, 500, and 1000'):
        (1, _u((63, 406))),
    ('paper/transport_followup_appendix.tex', 'summarize 50 seeds'):
        (1, _u((99, 505))),
    ('paper/transport_followup_appendix.tex', 'teacher seed 1729'):
        (1, _u((57, 21))),
    ('paper/transport_followup_appendix.tex', 'the 600\ntrajectories'):
        (1, _u((62, 352))),
    # paper/transport_proofs.tex
    ('paper/transport_proofs.tex', '\\xi_t=0'):
        (2, _u((85, 414), (86, 565))),
    # paper/transport_theory.tex
    ('paper/transport_theory.tex', '$D_t<1$'):
        (1, _u((31, 214))),
    ('paper/transport_theory.tex', '\\alpha_t=1'):
        (1, _u((78, 696))),
    ('paper/transport_theory.tex', '\\kappa_{-,t}=\\kappa_{+,t}=1'):
        (2, _u((33, 29), (78, 710))),
    ('paper/transport_theory.tex', '\\xi_t=0'):
        (3, _u((82, 439), (73, 270), (78, 745))),
    # submissions/tmlr_2026/main.tex
    ('submissions/tmlr_2026/main.tex', '29-parameter'):
        (1, _u((48, 933))),
    ('submissions/tmlr_2026/main.tex', '50 paired seeds'):
        (1, _u((48, 1140))),
    # submissions/tmlr_2026/supplement_README.md
    ('submissions/tmlr_2026/supplement_README.md', '2,400 trajectories'):
        (1, _u((6, 41))),
    ('submissions/tmlr_2026/supplement_README.md', '21 artifacts'):
        (1, _u((53, 30))),
    ('submissions/tmlr_2026/supplement_README.md', 'all 21 published tables, figures and CSVs'):
        (1, _u((5, 386))),
}

#: (path, literal) -> (category, occurrences, ((unit, offset-in-unit), ...))
CLASSIFIED_PINS: dict[tuple[str, str], tuple[str, int, tuple[tuple[str, int], ...]]] = {
    # paper/availability.tex
    ('paper/availability.tex', '1.13.1'):
        ('historical-dependency-version', 1, _u((175, 661))),
    ('paper/availability.tex', '1.15.2'):
        ('historical-dependency-version', 1, _u((175, 600))),
    # paper/body_related.tex
    ('paper/body_related.tex', '1'):
        ('math-constant', 3, _u((182, 291), (182, 306), (173, 157))),
    ('paper/body_related.tex', '2'):
        ('math-constant', 2, _u((182, 293), (182, 308))),
    # paper/notation.tex
    ('paper/notation.tex', '1'):
        ('math-constant', 2, _u((191, 153), (191, 157))),
    ('paper/notation.tex', '2'):
        ('math-constant', 3, _u((191, 61), (191, 129), (191, 162))),
    # paper/transport_experiment_appendix.tex
    ('paper/transport_experiment_appendix.tex', '1'):
        ('math-constant', 7, _u((171, 168), (171, 177), (14, 19), (13, 19), (24, 18), (24, 46), (15, 10))),
    ('paper/transport_experiment_appendix.tex', '2'):
        ('math-constant', 10, _u((171, 104), (171, 108), (171, 171), (14, 1), (14, 44), (13, 1), (13, 44), (24, 43), (24, 64), (15, 1))),
    # paper/transport_followup.tex
    ('paper/transport_followup.tex', '1'):
        ('math-constant', 1, _u((65, 148))),
    ('paper/transport_followup.tex', '2'):
        ('math-constant', 1, _u((65, 141))),
    # paper/transport_followup_appendix.tex
    ('paper/transport_followup_appendix.tex', '1'):
        ('math-constant', 4, _u((74, 165), (74, 257), (40, 121), (40, 551))),
    ('paper/transport_followup_appendix.tex', '2'):
        ('math-constant', 5, _u((74, 149), (74, 178), (74, 267), (40, 339), (40, 553))),
    ('paper/transport_followup_appendix.tex', '4'):
        ('math-constant', 1, _u((40, 110))),
    # paper/transport_proofs.tex
    ('paper/transport_proofs.tex', '0'):
        ('math-constant', 16, _u((45, 304), (39, 162), (39, 213), (35, 165), (92, 554), (92, 609), (38, 80), (38, 101), (163, 174), (163, 232), (163, 742), (80, 172), (50, 29), (50, 270), (50, 346), (50, 359))),
    ('paper/transport_proofs.tex', '0,1'):
        ('interval-endpoint', 1, _u((35, 179))),
    ('paper/transport_proofs.tex', '1'):
        ('math-constant', 80, _u((118, 114), (136, 18), (45, 17), (45, 284), (45, 293), (108, 42), (68, 127), (93, 546), (35, 235), (35, 291), (85, 121), (92, 383), (92, 455), (92, 485), (92, 572), (91, 130), (91, 154), (91, 175), (91, 192), (91, 248), (91, 273), (91, 296), (91, 507), (91, 539), (91, 566), (91, 599), (91, 707), (91, 772), (87, 86), (94, 299), (94, 464), (94, 491), (89, 181), (139, 16), (161, 48), (161, 56), (161, 150), (161, 179), (161, 188), (161, 349), (161, 424), (84, 68), (84, 207), (84, 305), (86, 134), (86, 549), (86, 556), (90, 521), (90, 599), (10, 2), (11, 4), (59, 18), (59, 398), (59, 428), (163, 107), (163, 368), (163, 531), (163, 573), (163, 627), (88, 108), (88, 141), (88, 153), (88, 421), (88, 431), (112, 58), (112, 118), (113, 99), (55, 31), (55, 55), (55, 178), (83, 234), (83, 247), (83, 298), (83, 374), (83, 417), (83, 432), (43, 17), (43, 342), (44, 529), (44, 670))),
    ('paper/transport_proofs.tex', '2'):
        ('math-constant', 110, _u((119, 55), (119, 93), (118, 116), (138, 44), (138, 80), (136, 103), (45, 134), (45, 181), (45, 204), (45, 232), (45, 244), (45, 335), (45, 346), (45, 363), (45, 380), (108, 55), (108, 78), (108, 88), (93, 226), (93, 251), (35, 283), (92, 385), (92, 457), (92, 487), (91, 132), (91, 156), (91, 177), (91, 194), (91, 250), (91, 275), (91, 385), (91, 509), (91, 541), (91, 555), (91, 568), (91, 601), (91, 630), (91, 709), (87, 109), (87, 230), (87, 239), (87, 251), (87, 353), (87, 366), (94, 99), (94, 123), (94, 139), (94, 168), (94, 222), (94, 253), (94, 277), (94, 305), (94, 466), (94, 493), (89, 183), (137, 73), (139, 103), (161, 182), (161, 532), (84, 58), (84, 167), (84, 176), (84, 316), (84, 336), (86, 122), (86, 130), (86, 327), (86, 336), (86, 438), (86, 477), (86, 486), (90, 248), (90, 258), (90, 281), (90, 293), (90, 304), (90, 368), (90, 504), (90, 528), (90, 564), (90, 596), (90, 632), (38, 141), (38, 209), (10, 26), (11, 26), (59, 155), (59, 166), (59, 193), (59, 221), (59, 251), (52, 203), (163, 210), (163, 288), (163, 295), (163, 499), (163, 525), (163, 575), (163, 667), (163, 703), (163, 725), (163, 732), (113, 127), (55, 225), (83, 271), (83, 322), (43, 42), (43, 72), (43, 113), (43, 245))),
    ('paper/transport_proofs.tex', '4'):
        ('math-constant', 4, _u((86, 431), (86, 441), (90, 642), (163, 522))),
    # paper/transport_theory.tex
    ('paper/transport_theory.tex', '0'):
        ('math-constant', 32, _u((41, 14), (41, 29), (49, 14), (117, 33), (77, 121), (77, 136), (103, 9), (46, 63), (97, 158), (97, 249), (97, 260), (115, 57), (115, 104), (155, 15), (7, 0), (7, 0), (7, 0), (7, 0), (7, 0), (7, 0), (95, 200), (47, 71), (69, 81), (122, 38), (71, 323), (73, 71), (78, 516), (96, 113), (96, 327), (125, 73), (125, 154), (3, 10))),
    ('paper/transport_theory.tex', '0,1'):
        ('interval-endpoint', 5, _u((81, 78), (95, 78), (47, 63), (47, 102), (34, 15))),
    ('paper/transport_theory.tex', '1'):
        ('math-constant', 95, _u((101, 10), (20, 25), (19, 22), (18, 24), (107, 63), (107, 90), (107, 106), (121, 116), (9, 9), (9, 34), (9, 67), (111, 78), (131, 68), (131, 88), (146, 15), (146, 36), (134, 68), (144, 15), (144, 36), (157, 134), (157, 202), (157, 269), (129, 69), (129, 94), (129, 115), (30, 203), (8, 0), (97, 296), (82, 241), (75, 1), (109, 58), (109, 74), (109, 103), (115, 70), (98, 356), (98, 365), (155, 22), (100, 23), (100, 52), (4, 80), (4, 189), (105, 59), (105, 90), (47, 99), (47, 242), (47, 378), (124, 43), (69, 46), (133, 31), (123, 55), (123, 82), (123, 115), (156, 20), (156, 55), (154, 204), (140, 67), (140, 97), (140, 118), (17, 12), (25, 17), (25, 26), (76, 120), (58, 103), (58, 162), (58, 191), (58, 207), (106, 71), (27, 9), (151, 45), (143, 29), (73, 195), (73, 231), (78, 793), (78, 858), (153, 25), (31, 98), (125, 55), (125, 136), (162, 11), (162, 19), (162, 22), (64, 89), (114, 31), (114, 71), (160, 103), (141, 67), (141, 87), (141, 103), (141, 113), (145, 15), (145, 36), (0, 2), (0, 13), (2, 8), (1, 1))),
    ('paper/transport_theory.tex', '1,0'):
        ('math-constant', 1, _u((97, 227))),
    ('paper/transport_theory.tex', '2'):
        ('math-constant', 107, _u((187, 192), (16, 19), (102, 9), (158, 4), (159, 12), (107, 117), (107, 128), (9, 36), (9, 69), (127, 68), (111, 164), (131, 23), (131, 33), (131, 80), (131, 160), (146, 6), (134, 23), (134, 33), (134, 81), (134, 90), (134, 94), (144, 6), (128, 4), (128, 26), (129, 4), (129, 24), (129, 34), (129, 81), (129, 85), (120, 62), (97, 312), (97, 378), (109, 76), (109, 105), (98, 358), (98, 367), (100, 25), (100, 54), (4, 101), (4, 122), (4, 168), (4, 204), (105, 92), (47, 177), (47, 380), (79, 116), (104, 58), (110, 122), (102, 9), (132, 40), (159, 12), (133, 42), (123, 57), (123, 84), (135, 28), (140, 22), (140, 32), (140, 79), (140, 84), (140, 88), (116, 78), (116, 86), (116, 88), (17, 23), (25, 20), (147, 81), (58, 216), (106, 82), (106, 102), (26, 57), (151, 39), (152, 33), (152, 43), (143, 6), (130, 4), (153, 19), (148, 12), (148, 21), (150, 25), (150, 35), (149, 21), (23, 21), (142, 14), (12, 8), (12, 39), (51, 14), (51, 35), (51, 158), (96, 246), (96, 307), (21, 21), (21, 58), (22, 21), (22, 58), (126, 38), (126, 73), (42, 164), (162, 108), (162, 145), (114, 41), (114, 81), (160, 93), (141, 22), (141, 32), (141, 79), (141, 171), (145, 6))),
    ('paper/transport_theory.tex', '3'):
        ('math-constant', 2, _u((51, 52), (51, 161))),
    ('paper/transport_theory.tex', '4'):
        ('math-constant', 5, _u((78, 780), (149, 12), (51, 49), (51, 150), (42, 212))),
    # submissions/tmlr_2026/supplement_README.md
    ('submissions/tmlr_2026/supplement_README.md', '1.15.2'):
        ('environment-version', 1, _u((70, 43))),
    ('submissions/tmlr_2026/supplement_README.md', '2.2.3'):
        ('environment-version', 1, _u((70, 27))),
    ('submissions/tmlr_2026/supplement_README.md', '3.12'):
        ('environment-version', 1, _u((70, 11))),
}

#: path -> SHA-256 of the whole normalized auditable text
FILE_PINS: dict[str, str] = {
    'paper/availability.tex':
        '805154682b8991ec58161e9dc13f66b017aacb39e35312513cccc87332964ca3',
    'paper/body_conclusion.tex':
        'c21843d8923d371ec7b7abed011900667fc7e6bd20c49d51380112289508ef2d',
    'paper/body_intro.tex':
        '54bbfbb005e3c99bcc8ddb98007cec60973074598d691194ad6b8ef12d47cbd2',
    'paper/body_related.tex':
        'ebfaa31d0a7766fee655c919ec3ac34ed6d3b822850442eb67d2c415521d696e',
    'paper/broader_impact.tex':
        '41c44900a31c1d4274da9f69facd14255cfc61108c1ec592805208be3b8c0605',
    'paper/legacy_scope.tex':
        'be156968b1bdb7a14e7451e7c45d747f5b5586fc6be2101ede15cd829f3b542a',
    'paper/macros.tex':
        '1129bd91c4ad4afdfb620e562fea7a496deca6dd9f9aab3900eda0855380323f',
    'paper/notation.tex':
        'bb6d009986893a068603fbaa0ae76ed5f0bd2ce6554b41db939ac7e0098bd727',
    'paper/transport_experiment.tex':
        'da30ea9dfffb29661b4ba40c4683e7952743dc2b444b32b9872f912937d52126',
    'paper/transport_experiment_appendix.tex':
        '22bd9ab1ae3ab1ccb14ef237fb5fa01d1a4464fe4ac90a595f77b0efee7ea2ad',
    'paper/transport_followup.tex':
        'a7b42b6c103971119af22ca786d679ee4c7f0636da3c17e4232ff28dbeb323b2',
    'paper/transport_followup_appendix.tex':
        'c170cf7e24d42e31491257384e8c8f9ca9d3797608be11cd16fe033764d77569',
    'paper/transport_proofs.tex':
        'd9ff00e05381876fd7a5a3adac2fafc0ec0cc2556feaef8ba32d6dfa3f750558',
    'paper/transport_theory.tex':
        'a3c5395d4e90e015e4df9072803028e0a85d888644a9d2be5abff8c8cf74d9fc',
    'submissions/tmlr_2026/main.tex':
        'fcc7f6f5714ecedc057456eae2199306c94430bf7614852f67465836482abee0',
    'submissions/tmlr_2026/supplement_README.md':
        'ffd557c3ce0335733a28259a0595c4675f9dc3c4501eae5dfedd0f0bd20b09ef',
}
