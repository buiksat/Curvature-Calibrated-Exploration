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
    '$\\Calg_t,\\ s_{\\Calg,t}(a)$}; \\node[object] (width) at (14.4,-1.15) {Numerical score width',
    '$\\bV_t,\\ s_t(a)$}; \\node[object] (operator) at (10.2,-1.15) {Applied SPD operator',
    '$\\bVbar_t,\\ \\bar s_t(a)$}; \\node[object] (current) at (6,-1.15) {Exact current metric',
    '$\\chi_t<1$',
    '$\\kappa_->0$',
    ', \\] so $\\mathcal D(\\bV)=d_{\\rm Th}(\\bVbar,\\bV)=D$. For $q_1=e_1$, $\\bar s(q_1)=1$ and $s(q_1)=e^{-D/2}$, so $\\bar s=e^{D/2}s$ is attained. For $q_2=e_2$, $s(q_2)=e^{D/2}$ and $\\bar s(q_2)=1$, so $s=e^{D/2}\\bar s$ is attained. Thus each one-way factor is sharp, and a uniform argument based only on the symmetric Thompson-distance bound cannot improve the resulting round-trip factor $e^D$. This is a metric-factor sharpness statement, not a contextual-bandit regret lower bound and not a claim that every trajectory attains the worst case.',
    '- **Numerical-provenance ledger:** derives every declared empirical literal from its pinned source, including the follow-up summaries, and checks its source context and display rounding. Every other numeric literal in the active compiled sources must have an explicit classification. Added or relocated numerical claims are rejected. - **Historical artifact regeneration:** regenerates all 21 published tables, figures and CSVs from the packaged historical aggregate and requires byte equality with the pinned artifacts. - **Follow-up terminal interval reconstruction:** independently resamples the complete per-seed evaluation summaries, verifies the configuration and selection bindings, and reconstructs all reported terminal intervals. The export manifest must describe exactly the files in its directory. - **Follow-up table regeneration:** regenerates the manuscript tables from the packaged summaries and fixed-history outputs, verifies the original-source attribution, and requires exact artifact bytes. - **Explanatory chart regeneration:** reconstructs every plotted mean, paired interval and bound-to-cap ratio from the fixed follow-up summaries, and requires exact TeX, CSV and provenance bytes. The outcome means are descriptive; the plotted intervals describe paired policy differences. The bound chart takes the logarithm after averaging the RHS, not before. - **Evidence coverage:** scans the actual evidence directories. Each file must have a valid checksum sidecar or an exact, independently checked contract pin. An added file without coverage is a failure. - **Study tests:** runs the shipped scientific algebra, seed, aggregation, artifact and follow-up configuration tests.',
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
    "After observing the outcomes, we audit these comparisons on the same 600 recorded histories, replaying representation updates with the recorded actions and rewards. On Hessian's histories, the category-specific outward factor gives mean effective-width overheads of $0.28\\%$--$12.68\\%$ relative to the direct reference width, versus $0.16\\%$--$12.13\\%$ for the dense endpoint factor across conditions (\\Cref{app:transport-followup}). These are means of actionwise ratios, not ratios of mean widths: for each candidate action at each recorded state, we divide its effective width by its reference width, then average over actions, rounds, and seeds.",
    "All quantities are evaluated on this policy's own selected history. No path, current-metric, or operator certificate is needed for this score. If its reference-confidence event has probability at least $1-\\delta$, so does this guarantee.",
    "At $W=16,1,0.25$, the base-ten logarithms of Hessian's mean terminal RHS divided by the cap are approximately 9.51, 37.19, and 80.91. The frozen policy's corresponding mean ratios, without taking logarithms, are approximately 19, 60, and 231. Each mean uses the named policy's own 50 histories. These summarize mean bound magnitudes; the statement that every individual bound exceeds its cap is a separate check.",
    'Bandit exploration also connects to classical D-optimal and A-optimal design through objectives such as maximizing $\\log\\det(\\bVbar_t)$ or minimizing the trace of $\\bVbar_t^{-1}$ \\citep{valko2013finite}. Stochastic trace and log-determinant estimators offer related matrix-free tools \\citep{ubaru2017fast}. Here the frozen log-determinant enters the regret analysis. The audited policy chooses actions by its UCB score and does not implement those estimators.',
    'Certified path-length envelope $\\bar D_t$.}; \\node[anchor=north west,align=left] at (5.5,-2.2) {\\textbf{B\\quad Operator comparison}',
    'Consequently, $W=\\Omega(T)$ with a sufficiently large problem-dependent constant keeps $D_{T,W}=O(1)$. For fixed $d$ and fixed problem constants, \\[ R_T=O(d\\sqrt T\\log T)+O(\\sqrt T). \\] This conclusion requires no $D_t<1$ condition. Here $W$ is an abstract near-linearity scale, not generic network width or parameter count, and the result is not an unrestricted neural-training theorem. No optimizer-residual rate is required because the corrected center is used.',
    'Each term records the contribution of the action actually chosen. This identity is why the regret proof returns to the frozen matrix even when the policy scores actions using the current matrix. Set $\\gamma_0=0$, and define regret as the mean reward lost relative to the best available action:',
    'Exact current curvature has $\\kappa_{-,t}=\\kappa_{+,t}=1$. More generally, the operational relative-error certificate',
    'For completeness, an exact scalar endpoint distance does not generally give the actionwise equality. Set $\\bVbar=I_2$, $\\bV=\\operatorname{diag}(e^D,e^{-D})$ with $D>0$, and $\\bq=(0,1)^\\top$. Then $d_{\\rm Th}(\\bVbar,\\bV)=D$ and $\\bar s=1$, whereas the scalar corrected width is $e^{D/2}s=e^D>1$.',
    "For descriptive context, the online context-free mean-only benchmark has mean regrets 185.26, 183.06, and 176.67 at $W=16,1,0.25$, respectively; the best fixed action in hindsight has mean regrets 180.01, 177.97, and 171.84. These means use the same evaluation streams. Hessian's sample means are close to the context-free benchmark's, but no equivalence test was performed. Similar regret does not imply matching actions or identical use of context, and these benchmarks do not bound the benefit available to another context-dependent policy. \\Cref{app:transport-followup} defines both benchmarks.",
    'For the category certificate, finite positive collection weights imply $f_{t,c}>0$ whenever $n_{t,c}>0$, and \\[ \\bVbar_t=\\lambda\\bI+\\sigma^{-2}\\sum_c f_{t,c}\\phi_c\\phi_c^\\top, \\qquad \\bV_t=\\lambda\\bI+\\sigma^{-2}\\sum_c g_{t,c}\\phi_c\\phi_c^\\top. \\] For $m=c_{-,t}$ and $M=c_{+,t}$, the definitions give',
    'For the fixed-band statement, the largest admissible mean is $m_t(a)+\\beta_t\\bar s_t(a)+b_t(a)$. Comparing this endpoint to the proposed score and using $\\beta_t>0$ proves necessity and sufficiency. When $\\beta_t=0$, this comparison imposes no restriction on the candidate width. It makes no assertion about uncertainty sets constrained by additional information or about distinct adaptive histories.',
    'Here $\\lambda>0$ is the ridge regularization and $\\sigma>0$ sets the scale of the updates; it is the noise scale in the squared-loss specialization. The reference update keeps each query as it was at collection time. For the same current query, the matrices can give different widths:',
    'If the observed feature vectors belong to a finite set $\\{\\phi_c\\}$, let $n_{t,c}$ be their counts, let $f_{t,c}=\\sum_{s<t:\\phi(z_s)=\\phi_c}\\omega_{\\btheta_s}(z_s)^2$, and put $g_{t,c}=n_{t,c}\\operatorname{sech}^4(\\phi_c^\\top\\btheta_t/\\sqrt W)$. The sharper category certificate is',
    'Install the exact Python 3.12 package lock using [`PYTHON_SETUP.md`](PYTHON_SETUP.md), then run the tests and the static manuscript validation directly:',
    'Let $\\bu=\\Calg^{-1}\\bq$. Since $s_{\\Calg}^2=\\bq^\\top\\bu=\\|\\bu\\|_{\\Calg}^2$, \\[ \\left|\\bq^\\top\\tilde\\bu-s_{\\Calg}^2\\right| =\\left|\\langle\\bu,\\tilde\\bu-\\bu\\rangle_{\\Calg}\\right| \\le\\|\\bu\\|_{\\Calg}\\|\\tilde\\bu-\\bu\\|_{\\Calg} \\le\\varepsilon s_{\\Calg}^2. \\] This proves the pointwise two-sided quadratic-form comparison. Dividing its lower side by $1-\\varepsilon$ gives upper validity for this query, while combining both sides gives the displayed sharpness factor. Applying the lower inequality actionwise on the simultaneous family event gives the all-domain upper condition; only the played query uses the upper inequality for sharpness. For PCG the argument is unchanged once the certificate is expressed in the original $\\Calg$-energy norm.',
    'Let $\\mathcal J$ be a finite or countable certificate-source index set. For $j\\in\\mathcal J$, choose an $\\cHist_t^-$-measurable failure budget $\\delta_{j,t}$ before drawing its random object. Let $\\mathcal P_{j,t}$ be the pre-reward sigma-algebra immediately before that draw. It may equal $\\cHist_t^-$ for a round-start draw or include the selected action and earlier randomness for a post-selection check. It is sufficient that \\[ \\Pr(\\mathcal E_{j,t}^c\\mid\\mathcal P_{j,t})\\le\\delta_{j,t}, \\qquad \\sum_{j\\in\\mathcal J}\\sum_{t=1}^T\\delta_{j,t} \\le\\delta_{\\rm cert}\\quad\\text{almost surely}. \\] The tower property and a union bound give simultaneous validity at least $1-\\delta_{\\rm cert}$ without independence. Countability makes the joint event measurable, the nonnegative double sum well-defined, and the union bound valid. On an uncountable score domain, the solver upper event must already be simultaneous. A pointwise certificate cannot be union-bounded after adaptive selection unless it is separately verified at the selected action with the correct conditioning. Realized terminal spectral quantities may be used for post-hoc analysis, but they cannot be inserted into an earlier action-time radius unless a predictable prefix envelope was supplied at that time.',
    'Let $c_t=\\beta_t[1+\\alpha_te^{\\bar D_t} \\sqrt{\\kappa_{+,t}/\\kappa_{-,t}}]$. Summation and one Cauchy--Schwarz application give \\[ R_T-2\\sum_tb_t(a_t)-\\sum_t\\xi_t \\le\\sqrt{\\sum_tc_t^2}\\sqrt{\\sum_t\\bar s_t^2(a_t)}. \\] Since $\\bar s_t^2(a_t)\\le G^2/\\lambda$, the scalar inequality $x\\le(1+M)\\log(1+x)$ for $0\\le x\\le M$, with $x=\\sigma^{-2}\\bar s_t^2(a_t)$ and $M=G^2/(\\lambda\\sigma^2)$, yields',
    'More generally, fix an action and $m_t(a)$, $b_t(a)$, $\\beta_t>0$, and $\\bar s_t(a)$. If the only restriction on its mean is the full interval \\eqref{eq:abstract-confidence-new}, a score $m_t(a)+\\beta_t w_t(a)+b_t(a)$ is an upper bound for every mean in that interval if and only if $w_t(a)\\ge\\bar s_t(a)$.',
    'More generally, suppose there is a measurable function $\\nu_t:[0,1]\\to[0,\\infty)$ with $\\nu_t\\in L^1([0,1])$ such that \\[ \\dot\\Bmat(\\tau)^\\top\\dot\\Bmat(\\tau) \\preceq\\nu_t(\\tau)^2\\bV(\\tau) \\] almost everywhere. Then $\\mathcal D(\\bV)\\le2\\int_0^1\\nu_t(\\tau)d\\tau$. For nonnegative $\\nu_t$, the displayed PSD premise is equivalently the norm condition $\\|\\dot\\Bmat(\\tau)\\bV(\\tau)^{-1/2}\\|_{\\rm op}\\le\\nu_t(\\tau)$ almost everywhere.',
    "Retraining a model can change its uncertainty estimates even when no new data are added. In a contextual bandit, we ask when recomputing past gradients at the current model preserves the confidence guarantee used to choose actions. We give a conditional upper confidence bound (UCB) theorem that starts from features fixed before each reward and accounts for changing the uncertainty matrix, approximating it, and computing its widths. A width gives the geometric scale of the uncertainty bonus. For squared loss, a correction based on stored features adjusts the prediction at the center of the confidence band. The resulting confidence guarantee does not require the nonlinear optimizer to converge. It does require predictable parameter paths in a certified region, together with explicit Taylor and misspecification error bounds. The conversion has a basic limit: with the same history, center, radius and bias, its certified width cannot be smaller than the direct reference width. Exact actionwise transport recovers that width; the result leaves the regret ordering of policies with different histories open. A prespecified study tests four policies in three conditions using a 29-parameter scaled-tanh model and 50 paired seeds per condition. Hessian transport, which bounds matrix changes using prediction Hessians, has higher mean pseudo-regret than every comparator in each condition; all nine pointwise paired confidence intervals for regret differences exclude zero. Transport inflation dominates its regret bounds, which give no improvement over a deterministic regret cap. The reference policy's own bounds are also vacuous. All policies, including an uncertified control, pass the recorded floating-point confidence and optimism checks. The study illustrates why a conditionally valid confidence score, a tight regret bound and a useful decision rule must be assessed separately.",
    'Set $\\hat s=\\sqrt{U}$. If $L>0$, the observable factor $\\alpha=\\sqrt{U/L}$ verifies played-action sharpness. If $L\\le0<U$, the interval supplies no finite positive multiplicative sharpness factor; the solve must continue or an additive-width theorem must be used. If $U=0$, the exact inverse quadratic form is zero and the solver returns $\\hat s=0$. For $\\bq=0$, skip the solve and return zero.',
    'Since $\\sup_u|2\\operatorname{sech}^2(u)\\tanh(u)|=4/(3\\sqrt3)$, \\Cref{cor:global-near-linear-new} applies with \\[ G=B_\\phi,\\qquad c_\\mu=c_g=c_h:=\\frac{4B_\\phi^2}{3\\sqrt3}. \\] The symbol $W$ is a smoothness scale here; it is not identified with hidden width or parameter count.',
    'The category certificate uses only scalar sums and current projections. After collecting category $c$ at time $t$, its count increases by one and its collection sum increases by $\\omega_{\\btheta_t}(z_t)^2$; other category sums are unchanged. These are sufficient statistics for this comparison, although the category factors need not be the tight spectral factors when feature outer products are linearly dependent.',
    'The earlier audit contributes 21 artifacts, each with its original provenance record and checksum sidecar. The follow-up contributes separately generated tables and explanatory charts with separate collective provenance records, all independently pinned in code. The conceptual diagrams are reviewed analytical schematics with separate source pins, not measured study outcomes. The excluded legacy appendix, symbolic rate table, autodiff-GGN benchmark and linear-bound benchmark are not evidence for the active manuscript and are not included.',
    'The earlier experiments did not execute the transported score or record its path, operator, and solver certificates. They therefore provide no evidence for the current theorem or its numerical performance. The present paper makes no empirical claim for a large neural model, an approximate operator, or an iterative solver: its reported study uses a 29-parameter model and dense Cholesky solves. These exclusions do not change the conditional operator and solver interfaces proved in the theorem.',
    'The exact solution is $\\Calg^{-1}\\bq=\\tilde\\bu+\\Calg^{-1}\\br$. Substitute this expression and $\\bq=\\Calg\\tilde\\bu+\\br$ into the quadratic form. The remainder is $\\br^\\top\\Calg^{-1}\\br$, which lies between zero and $\\|\\br\\|_2^2/\\lambda_{\\Calg}$.',
    "The existing cumulative decomposition in \\Cref{fig:transport-instantiation-bound} separates base confidence, historical linearization, path inflation, and current bias. At $T=1000$, the base component accounts for $79.4\\%$--$97.3\\%$ of the mean terminal sharp right-hand side across target cells; path inflation accounts for $2.0\\%$--$16.3\\%$. Each percentage divides a component's mean over the 50 transport-Hessian trajectories by the mean sharp right-hand side over those same trajectories. These are ratios of means, not medians of runwise shares. The base component alone has cell means of about $9{,}948$--$10{,}010$, already above the cap $2{,}000$. It includes the statistical and regularization/norm-bound terms together with the determinant-potential and Cauchy--Schwarz factors; its size cannot be attributed to the confidence radius alone. Thus most of the bound's size on this original near-linear grid is present before path inflation is added. This dominance statement does not describe the nonlinear follow-up. This is a decomposition along transport-Hessian histories, not a bound evaluated on the frozen-reference policy's different histories. The appendix defines the components and reports the complete tightness table.",
    'The historical deterministic term in \\eqref{eq:beta-corrected-new} follows from $\\Phi_t^\\top\\bVbar_t^{-1}\\Phi_t\\preceq I$ for $\\Phi_t=[\\bq_1/\\sigma,\\ldots,\\bq_{t-1}/\\sigma]$. Its scaling is $1/\\sigma$, not $1/\\sigma^2$. Fixed nonvanishing misspecification generally creates a linear current-bias term and can also make the historical radius vacuous. This is a graceful-degradation statement, not a robust misspecified-bandit guarantee.',
    'The inclusion of $1$ in the minimum and maximum accounts for the ridge. Each category ratio is a weighted average of sample ratios $r_s=\\widetilde\\omega_s^2/\\omega_s^2$, with weights $\\omega_s^2/f_{t,c}$. Therefore $\\ell^2\\le g_{t,c}/f_{t,c}\\le\\ell^{-2}$, which gives the asserted uniform bounds on $m,M$. It also shows that the category factors are no looser than the direct sample factors $\\min\\{1,\\min_{s<t}r_s\\}$ and $\\max\\{1,\\max_{s<t}r_s\\}$. For an empty history both metrics equal $\\lambda\\bI$.',
    "The locked grid contains horizons $T\\in\\{250,500,1000\\}$, 50 evaluation seeds, and target labels $D_{\\rm target}\\in\\{0.25,0.5,1,2\\}$. Each $(T,D_{\\rm target})$ cell is a separately executed model condition because both quantities enter the rule for $W$. The target label is neither realized transport distance nor generic network width, so trends across targets are not a dose response to certificate inflation. The four policies share contexts and potential-noise tables. The primary \\emph{transport Hessian} policy uses $\\bar D_t^Q$ in the score. The \\emph{transport endpoint} policy replaces it by the dense endpoint Thompson distance computed from the learner-known matrices $\\bVbar_t$ and $\\bV_t$ before the reward is observed; it is a dense diagnostic comparator. The \\emph{frozen reference} policy uses the frozen width directly. The \\emph{naive current} policy omits transport and is intentionally uncertified. Each policy has its own selected history and representation path; the frozen-reference policy also updates its representation. ``Frozen'' refers to its collection-time metric. Ten disjoint tuning seeds selected learning rate $3\\times10^{-4}$ and 20 full-batch steps followed by projection each round by preregistered all-action prediction MSE; evaluation seeds never entered that selection. The environment was not filtered after generation. Within each $T=1000$ target cell, the 50-seed means round to optimal-action entropy $1.579$, optimality gap $0.123$, best-fixed-action regret $180.4$, and online context-free mean-only regret $185.4$. All five actions are optimal somewhere in every evaluation stream. Entropy is measured in nats; its maximum for five actions is $\\log 5\\approx1.609$, so the mean entropy is close to its uniform-action maximum. These diagnostics were reported after the grid was fixed; they were not used to select seeds.",
    'The prespecified follow-up evaluates 600 policy trajectories. A separate set of 294 development and tuning trajectories precedes evaluation. We fix $T=1000$ and $W\\in\\{16,1,0.25\\}$, with 50 common evaluation seeds per condition and four policies. The model parameter $W$ changes both the reward function and its curvature, so comparisons across conditions do not isolate an effect of metric drift. The original near-linear study appears separately in \\Cref{sec:transport-instantiation}; its evidence is not pooled with this study.',
    'The shared optimizer uses learning rate $3\\times10^{-4}$ with 20 full-batch steps followed by projection each round. It was selected from nine candidates by prediction MSE on uniform-random tuning histories. This fixes one implementation choice across policies; it does not establish policy-specific regret-optimal tuning. Dense float64 matrices and Cholesky solves implement the exact-operator abstraction. Actions are enumerated, with ties resolved by the smallest action index. This 29-parameter study therefore examines dense numerical implementations. It does not test approximate solvers, large-model scalability, or real-data performance. \\Cref{app:transport-followup} records the protocol and provenance.',
    "Their sum equals the sharp right-hand side in \\eqref{eq:sharp-transport-regret-new} for the experiment's $\\alpha_t=\\kappa_{-,t}=\\kappa_{+,t}=1$ and $\\xi_t=0$. The differences retain the same trajectory and the same potential factor; they do not rerun a policy with a component removed. The committed figure CSVs report the mean of each component over 50 primary-policy trajectories at each round. At $T=1000$, dividing those terminal component means by the corresponding mean sharp right-hand side gives base shares $97.33\\%,94.66\\%,89.39\\%,79.39\\%$ and path shares $2.01\\%,4.04\\%,8.16\\%,16.27\\%$ for $D_{\\rm target}=0.25,0.5,1,2$, respectively. These joint cumulative quantities establish the decomposition; marginal medians of $e^{\\bar D_t^Q/2}$ do not determine it.",
    'There is measurable movement between the reference and current matrices. The Hessian policy reaches endpoint distances above one in 16 of 50 seeds at $W=0.25$. In that condition, distances are at least one in 286 of 50,000 seed--round observations (\\Cref{tab:transport-followup-drift-bounds}). These round counts describe dependent observations, not additional independent replications. The target labels used to encode $W$ are not measured endpoint distances.',
    "This analysis asks what different scores recommend when given the same information. For each logged state, we evaluate all four original score rules using that state's matrices, centers, and radii, without changing its history. \\Cref{tab:transport-followup-same-history} includes all 12 combinations of condition and behavior policy. Each entry averages one-step pseudo-regret over 50,000 dependent states; the diagonal equals the actual mean cumulative pseudo-regret divided by 1000. Off-diagonal entries are recommendations on states visited by the row policy. They describe a recommendation at a recorded state, not the subsequent trajectory of an alternative policy. Taking a different action would generally change future observations, parameters, matrices, and decisions. The analysis was specified after the full-study outcomes were observed.",
    'This appendix expands the original locked full aggregate summarized in \\Cref{sec:transport-instantiation}. The experiment protocol, configuration, selection record, aggregate, and every generated artifact carry provenance and         hashes. The figures use only the 50 evaluation seeds. Smoke and tuning results are absent. The original raw trajectories were unavailable for this revision; recorded hashes bind the retained artifacts but do not replace those missing inputs or establish an independent raw-data reproduction.',
    'This proves \\eqref{eq:sharp-transport-regret-new}. Finally, $\\alpha_te^{\\bar D_t}\\sqrt{\\kappa_{+,t}/\\kappa_{-,t}}\\ge1$, hence $1+x\\le2x$ gives \\eqref{eq:simple-transport-regret-new}. The probability statement follows by a union bound; independence is not required.',
    'This remains valid when $\\bar D_t\\ge1$. At $t=1$, the factor has zero rows, $Q_1=0$, and both metrics equal $\\lambda\\bI$.',
    'Two-sided SPD comparison.}; \\node[anchor=north west,align=left] at (11,-2.2) {\\textbf{C\\quad Solver certificate}',
    'Use Python 3.12 with NumPy 2.2.3 and SciPy 1.15.2. These are the declared versions in `experiments/requirements.txt`. The supplied `experiments/requirements-python312.lock` additionally pins the portable Linux x86_64 wheel environment, including the test dependencies. A separate online installation may use `pip install --require-hashes --only-binary=:all: -r experiments/requirements-python312.lock`. The verification commands themselves do not install or download anything.',
    'With exact realizability and a frozen linear model, $B_T=E_T^{\\rm cur}=0$. For fixed $d$ and problem constants, the leading term is then $O(e^D\\sqrt K\\,d\\sqrt T\\log T)$. Exact solves set $\\alpha=1$, exact current curvature sets $K=1$, and exact score maximization sets $\\xi_t=0$, recovering the standard LinUCB determinant-potential rate up to displayed constants.',
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
    '[x=   ,y=   , every node/.style={font=\\normalsize,inner sep=   }, cert/.style={draw=blue!55!black,line width=     ,->}, object/.style={draw=black!28,fill=black!2,rounded corners=   , minimum width=     ,minimum height=      ,align=center}] \\path[use as bounding box] (0,-6.8) rectangle (16.2,.3); \\node[anchor=west] at (0,0) {\\textbf{Before the reward: conditional certificate comparisons}};',
    '[x=   ,y=   , every node/.style={font=\\normalsize,inner sep=   }, reference/.style={blue!65!black,line width=   }, current/.style={orange!80!black,line width=   ,dashed}, transported/.style={teal!70!black,line width=   }] \\path[use as bounding box] (0,-8.35) rectangle (16.2,.25); \\node[anchor=west] at (0,0) {\\textbf{Abstract illustration}\\quad $\\bVbar=\\bI_2$, $\\bV=\\operatorname{diag}(e^D,e^{-D})$, $\\bq=(1,0)^\\top$, $m=b=0$.}; \\node[anchor=west] at (0,-.55) {Illustrative slice: $D=\\log 4$, $\\beta=1$; choose the allowed mean $\\mu^*=\\beta=1$.};',
    '\\Cref{fig:transport-confidence-geometry} shows the illustrative slice $D=\\log 4$ and $\\beta=1$. The support of a metric unit ball in direction $\\bq$ is the corresponding inverse-metric width. Here that support shrinks under the current metric even though the reference confidence band still allows its original upper endpoint.',
    '\\] Then \\[ \\bV(\\tau)^{-1/2}\\dot\\bV(\\tau)\\bV(\\tau)^{-1/2} =',
    '\\bVbar_{t+1}',
    '\\bar s_t^2(a)',
    '\\bq_t(a)=0',
    '\\draw[black!28,line width=    ] (0,-4.6) -- (16.2,-4.6); \\node[anchor=west] at (0,-4.95) {Selection and sharpness use the \\textbf{same realized width map} $\\hat s_t(\\cdot)$.}; \\node[anchor=west] at (0,-5.57) {\\textbf{Direct reference comparison}\\quad Same history, center, radius, and bias.}; \\node[anchor=west] at (0,-6.11) {$w_t^{\\rm tr}(a)=e^{\\bar D_t/2}\\sqrt{\\kappa_{+,t}}\\,\\hat s_t(a) \\ge\\bar s_t(a)$;\\quad exact actionwise correction gives $c_t(a)s_t(a)=\\bar s_t(a)$.}; \\node[anchor=west] at (0,-6.65) {These comparisons do not order the regret of policies with different adaptive histories.};',
    '\\draw[black!30,line width=     ] (11.5,-2.1) -- (11.5,-6.35); \\draw[black!55,densely dotted,line width=     ] (14.5,-1.95) -- (14.5,-6.35); \\node[anchor=south] at (14.5,-1.8) {$\\mu^*=1$};',
    '\\draw[black!40,->,line width=     ] (1.05,-4.35) -- (5.2,-4.35) node[right=   ] {$z_1$}; \\draw[black!40,->,line width=     ] (3,-6.7) -- (3,-2); \\node[anchor=west] at (3.6,-2.35) {$z_2$}; \\draw[reference,fill=blue!4] (3,-4.35) circle[radius=      ]; \\draw[current,fill=orange!6,fill opacity=.55] (3,-4.35) ellipse[x radius=      ,y radius=     ]; \\draw[black,->,line width=    ] (3,-4.35) -- (4.6,-4.35); \\node[anchor=north] at (4.6,-4.53) {$\\bq=\\mathbf e_1$}; \\fill[orange!80!black] (3.525,-4.35) circle[radius=   ]; \\fill[blue!65!black] (4.05,-4.35) circle[radius=   ]; \\draw[orange!80!black,line width=     ] (3.525,-4.32) -- (3.525,-3.6) -- (4.4,-3.6); \\node[anchor=west] at (4.47,-3.6) {$s=\\tfrac12$}; \\draw[blue!65!black,line width=     ] (4.05,-4.32) -- (4.05,-3.02) -- (4.4,-3.02); \\node[anchor=west] at (4.47,-3.02) {$\\bar s=1$}; \\draw[reference] (0,-7.15) -- (.65,-7.15); \\node[anchor=west] at (.82,-7.15) {Reference $E(\\bVbar)$}; \\draw[current] (3.55,-7.15) -- (4.2,-7.15); \\node[anchor=west] at (4.37,-7.15) {Current $E(\\bV)$};',
    '\\draw[black!50,line width=     ] (8.15,-6.7) -- (14.85,-6.7); \\foreach \\x/\\lab in {8.5/-1,10/-\\frac12,11.5/0,13/\\frac12,14.5/1}{ \\draw[black!50,line width=     ] (\\x,-6.64) -- (\\x,-6.76); \\node[anchor=north] at (\\x,-6.86) {$\\lab$}; } \\node[anchor=north] at (11.5,-7.4) {Mean / score value}; \\node[anchor=west] at (0,-7.85) {$\\bar s=1$, $s=e^{-D/2}$; transport restores $e^{D/2}s=\\bar s$ in this direction.}; \\node[anchor=west] at (0,-8.32) {This is not a realized learning trajectory or an observed policy failure.};',
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
    '\\label{eq:transported-score-new} U_t(a)=m_t(a) +\\beta_t e^{\\bar D_t/2}\\sqrt{\\kappa_{+,t}}\\,\\hat s_t(a) +b_t(a).',
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
    '\\node[anchor=north west,align=left] at (0,-2.2) {\\textbf{A\\quad Metric transport}',
    '\\node[anchor=west] at (0,-1.25) {\\textbf{Metric unit balls}}; \\node[anchor=west] at (0,-1.8) {$E(M)=\\{z:z^\\top Mz\\le1\\}$}; \\node[anchor=west] at (7,-1.25) {\\textbf{Bands along the query direction}};',
    '\\node[anchor=west] at (7,-2.25) {Reference: $m\\pm\\beta\\bar s$}; \\draw[reference] (8.5,-2.85) -- (14.5,-2.85); \\draw[reference] (8.5,-2.73) -- (8.5,-2.97); \\draw[reference] (14.5,-2.73) -- (14.5,-2.97); \\fill[black] (14.5,-2.85) circle[radius=     ];',
    '\\node[anchor=west] at (7,-3.75) {Naive: $m\\pm\\beta s$\\quad (uncertified)}; \\draw[current] (10,-4.35) -- (13,-4.35); \\draw[current] (10,-4.23) -- (10,-4.47); \\draw[current] (13,-4.23) -- (13,-4.47); \\fill[black] (14.5,-4.35) circle[radius=     ]; \\node[anchor=west] at (14.72,-4.35) {misses $\\mu^*$};',
    '\\node[anchor=west] at (7,-5.25) {Transported: $m\\pm\\beta e^{D/2}s$}; \\draw[transported] (8.5,-5.85) -- (14.5,-5.85); \\draw[transported] (8.5,-5.73) -- (8.5,-5.97); \\draw[transported] (14.5,-5.73) -- (14.5,-5.97); \\fill[black] (14.5,-5.85) circle[radius=     ];',
    '\\node[object] (reference) at (1.8,-1.15) {Frozen confidence',
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
    '{A local comparison when changes are small.} A local two-sided comparison gives another way to relate the same matrices. It replaces the exponential factors by a local sandwich that requires a smallness condition. If $\\chi_t<1$ and',
    '{Account for historical and current errors separately.} Fix $\\delta\\in(0,1)$. Let $\\rho_s^\\circ$ be the Taylor remainder of $\\mu_{\\btheta^\\circ}$ around $\\btheta_s$, and supply envelopes',
    '{An endpoint certificate need not bound the synthetic path.} Consider one sample with scalar feature $\\phi=1$, collection parameter $-R$, and current parameter $R$, where $R>0$. Write $\\ell=\\operatorname{sech}^2(R/\\sqrt W)$ with $W>0$. The endpoint metrics are equal to $\\lambda+\\sigma^{-2}\\ell^2$, so their Thompson distance is zero and the category factors are $m=M=1$. Along the synthetic interpolation \\eqref{eq:scalar-factor-path-new}, however, the scalar metric is \\[ V(\\tau)=\\lambda+\\sigma^{-2} \\operatorname{sech}^4((2\\tau-1)R/\\sqrt W). \\] It increases up to $\\tau=1/2$ and then decreases, giving path length \\[ \\int_0^1\\frac{|\\dot V(\\tau)|}{V(\\tau)}\\,d\\tau =2\\log\\!\\left(\\frac{\\lambda+\\sigma^{-2}} {\\lambda+\\sigma^{-2}\\ell^2}\\right)>0. \\] Thus \\Cref{cor:tanh-relative-weights} controls endpoint comparison, not the length used by the original synthetic-path certificate.',
    "{Both policies' mean regret bounds exceed the deterministic cap. Each point is the base-ten logarithm of the mean terminal theorem RHS divided by $2T\\min(1,\\sqrt W)$, using the named policy's own 50 histories. The zero line represents equality with the cap; positive values indicate that the mean bound is larger. These are descriptive means without uncertainty intervals. Every individual bound also exceeds its cap, as checked in the retained diagnostics. The comparison is not a decomposition of one policy's bound on another policy's history.} \\label{fig:transport-followup-bound-scale}",
    '{Bound nonvacuity.} The cumulative guarantee is vacuous in every original-study cell. The median of the per-trajectory terminal sharp-RHS/regret ratios is $126.7$--$155.7$ over the full grid and $126.7$--$135.0$ at $T=1000$. No run has zero regret. Since $|\\mu^*(z)|\\le\\|\\phi(z)\\|\\|\\btheta^\\circ\\|\\le1$, cumulative pseudo-regret has the deterministic cap $2T$. In every cell the theorem bound also exceeds this cap: the median right-hand sides are $3{,}989$--$12{,}607$, versus caps of $500$--$2{,}000$.',
    "{Certificate tightness.} At $T=1000$, the median of each trajectory's maximum realized $\\bar D_t^Q$ ranges from $0.0486$ to $0.384$ across target cells. The corresponding median of trajectory-maximum endpoint distances ranges from $1.31\\times10^{-7}$ to $8.74\\times10^{-6}$; both summaries have 50 trajectory-level observations per cell. At the 100 declared checkpoints per trajectory, pooling the 5,000 eligible seed--checkpoint ratios gives a median selected factor-path length only $1.20$--$1.22$ times the endpoint distance, while $\\bar D_t^Q$ is $2.51\\times10^5$--$1.88\\times10^6$ times the selected-path diagnostic. The large ratio accompanies extremely small realized metric motion. Measured directly against the endpoint distance rather than against the selected path, the median $\\bar D_t^Q/d_{\\rm Th}$ ratio is $3.07\\times10^5$--$2.24\\times10^6$ at $T=1000$, so the analytic certificate is conservative by five to six orders of magnitude on this grid. The reported median $e^{\\bar D_t^Q/2}$, by contrast, pools all 50,000 seed--round values in a $T=1000$ cell and ranges from $1.02$ to $1.18$ across the four target cells at that horizon; it is not a terminal or run-maximum summary.",
    "{Do the regret bounds give useful information?} We judge these regret bounds by whether they improve on what the reward range already guarantees. That range gives the deterministic regret cap $2T\\min(1,\\sqrt W)$, which is 2000, 2000, and 1000 for the three conditions. We call a larger bound \\emph{vacuous}: it adds no information beyond the cap. Every Hessian-policy bound is vacuous. The frozen policy's own reference-geometry bounds also exceed the caps in all 150 of its trajectories. \\Cref{fig:transport-followup-bound-scale} shows the size of their mean right-hand sides relative to the cap. The frozen policy's mean bounds are much smaller than Hessian's, but neither provides a useful regret upper bound in this study.",
    "{Environment and data splits.} The full study fixes teacher seed 1729, development seeds 30000--30001, tuning seeds 30100--30109, and evaluation seeds 30200--30249. Contexts are normalized Rademacher vectors. The feature map concatenates the context, action indicator, and their tensor product, then normalizes it to unit norm; its dimension is $4+5+20=29$. The teacher has unit norm and a fixed regular-simplex construction in the interaction block. The learner starts at zero, uses training ridge one, and receives only the selected action's reward. The potential-noise table couples methods without revealing unselected rewards. The 24 development trajectories cover three conditions and four policies at both development seeds.",
    '{Exploratory per-seed variation in Hessian-score recommendations on all four behavior histories. Every row evaluates the Hessian score; row labels identify the history-generating policy. Entries are the median percentage of rounds and the minimum--maximum range across 50 seeds. Width argmax uses the exact smallest-index tie rule; the strict condition is the bonus-gap inequality above.} \\label{tab:transport-followup-mechanism-variation} \\input{tables/transport_followup_mechanism_variation.tex}',
    "{Exploratory relative certificates on Hessian's recorded histories. The upper panel averages effective-width/reference-width ratios over all five candidate actions and 1000 rounds, then over 50 seeds per condition; the direct reference ratio is identically one. The lower panel averages one-step pseudo-regret of recommendations on these same states. Uniform uses $D_0$; the category columns use symmetric and separate outward factors. These are fixed-history diagnostics, not adaptive policy outcomes.} \\label{tab:transport-followup-relative-audit} \\input{tables/transport_followup_relative_audit.tex}",
    '{General protocol and timing.} Let $(\\mathsf A,\\mathcal B)$ be a standard Borel action space. At round $t$, the learner observes a context and a nonempty random action correspondence $\\cA_t:\\Omega\\to 2^{\\mathsf A}$ whose graph \\[ \\operatorname{Gr}(\\cA_t) :=\\{(\\omega,a):a\\in\\cA_t(\\omega)\\} \\in\\cHist_t^-\\otimes\\mathcal B. \\] Here $\\cHist_t^-$ is the history after the context and action correspondence are observed but before fresh round-$t$ algorithmic randomization. The variable $\\Omega_t$ records all round-$t$ pre-reward randomization, which may be revealed in sequential stages, and $\\cHist_t=\\cHist_t^-\\vee\\sigma(\\Omega_t)$ contains that randomization but not the reward. The restrictions to $\\operatorname{Gr}(\\cA_t)$ of $(\\omega,a)\\mapsto\\mu_t^*(a),\\bq_t(a),m_t(a),b_t(a),\\hat s_t(a)$, and, once defined below, $U_t(a)$ are assumed jointly measurable with respect to $\\cHist_t\\otimes\\mathcal B$. We also assume explicitly that $\\sup_{a\\in\\cA_t}\\mu_t^*(a)$ and $\\sup_{a\\in\\cA_t}U_t(a)$ are finite $\\cHist_t$-measurable random variables, that the oracle below returns a $\\cHist_t$-measurable selector in $\\cA_t$, and that the simultaneous confidence and all certificate events below, including path, operator, all-domain solver-upper, and played-action sharpness validity, are measurable. These are substantive assumptions; standard-Borel structure and graph measurability alone do not make every supremum or selector measurable.',
    '{Meaning of the cumulative bound decomposition.} For a transport-Hessian trajectory, write $P_T=(\\sigma^2+G^2/\\lambda)\\gamma_T$ and $\\beta_t^{\\rm stat}=\\sqrt{\\gamma_{t-1}+2\\log(1/\\delta)}+\\sqrt\\lambda S$. The reported components are',
    '{Model and implementation details.} The observations are Gaussian with mean $\\mu_{\\btheta}(z)=\\sqrt W\\tanh(\\phi(z)^\\top\\btheta/\\sqrt W)$, with $\\|\\phi(z)\\|_2\\le1$ and projected parameters $\\|\\btheta\\|_2\\le1$. Contexts have dimension four, there are five actions, and the context--action feature map has dimension 29. Noise has standard deviation $0.25$, the metric ridge is one, and the confidence parameter is $\\delta=0.05$. A fixed teacher generates the rewards. The conditions were specified before their evaluation outcomes were observed. Development, tuning, and evaluation use disjoint seed sets.',
    '{Noise and the reference model.} Let $\\sigma>0$ and let the reward obey $r_t=\\mu_t^*(a_t)+\\eta_t$, where, for every $u\\in\\R$,',
    '{Numerical checks before evaluation.} A documented development-only numerical refinement froze Gauss--Legendre quadrature order 2048 before tuning and evaluation. The full development gate compared orders 1024 and 2048 on all 24 declared trajectories; a separate development check also compared 2048 and 4096. No failed development check was reclassified as a passing evaluation. Quadrature checks, dense eigenvalue comparisons, and confidence/optimism checks remain floating-point diagnostics. They do not supply rigorous numerical enclosures for theorem assumptions.',
    "{Numerical values underlying \\Cref{fig:transport-followup-outcomes} at $T=1000$, with 50 paired evaluation seeds per condition. $\\Delta$ is the row policy's cumulative pseudo-regret minus Hessian's. All nine intervals are pointwise 95\\% paired bootstrap intervals; no simultaneous coverage is asserted.} \\label{tab:transport-followup-outcomes} \\input{tables/transport_followup_outcomes.tex}",
    "{Original near-linear audit for the transport-Hessian policy. Coverage is run-level simultaneous coverage with exact Clopper--Pearson intervals. The two median-maximum columns first maximize within each trajectory, then take the median over 50 runs per cell. ``Event viol.'' counts theorem-bound violations only when the joint confidence premise holds. All values come from the full evaluation; smoke and tuning runs are excluded.} \\label{tab:transport-instantiation-validity} \\evidencetabular{@{} >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{     } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    }@{}}{ \\input{tables/transport_instantiation_validity.tex}}",
    '{Original near-linear study.} For \\Cref{sec:transport-instantiation}, the retained full aggregate, generated tables and figures, provenance sidecars, and detached verifier support aggregate-derived checks. The original per-run trajectories and per-seed observations remain unavailable. Their inventory digests do not establish access to or integrity of the missing raw bytes. In particular, the original paired bootstrap cannot be recomputed from the aggregate alone; no per-seed values have been synthesized to replace it. The historical dependency records also disagree: requirements specify SciPy 1.15.2 while a retained host-specific wheel link names SciPy 1.13.1. Two selection-time sources, the artifact renderer and Buck build declaration, differ from their recorded digests. The verifier reports these gaps explicitly. Fresh runs and dependency locks do not repair the historical runtime or source provenance.',
    "{Original-study certificate and bound tightness for the transport-Hessian policy. The reported summary statistics are medians over the following populations. Terminal historical-radius and cumulative current-bias entries, and terminal width/bound ratios summarize 50 runs per cell. Path ratios pool eligible seed--round or seed--checkpoint observations, while $e^{\\bar D_t^Q/2}$ pools all seed--round values. $n_0$ counts denominators at or below the preregistered ratio tolerance that are excluded from that ratio. ``Width/potential'' is the frozen squared-width sum divided by its elliptic-potential upper bound; ``Sharp/simple'' is the sharp cumulative right-hand side divided by the simpler right-hand side.} \\label{tab:transport-instantiation-tightness} \\evidencetabular{@{} >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    }@{}}{ \\input{tables/transport_instantiation_tightness.tex}}",
    '{Original-study mean cumulative pseudo-regret at $T=1000$. Shaded bands are pointwise paired-bootstrap 95\\% intervals over the 50 evaluation seeds, not simultaneous confidence bands. All four methods are plotted; curves can coincide where their selected actions agree.} \\label{fig:transport-instantiation-regret}',
    '{Original-study path-certificate conservatism on log--log axes. Blue circles bin the per-round Hessian/$Q_t$ certificate $\\bar D_t^Q$ against endpoint Thompson distance. Orange triangles bin the numerical selected factor-path length at preregistered checkpoints. Each target panel pools eligible observations from the three independently executed horizons. Markers are plotted at geometric bin centers, marker size encodes bin count, and the dashed line is equality. Values at or below the preregistered $10^{-12}$ ratio tolerance, including round-one zeros, are omitted from the log axes and counted in \\Cref{tab:transport-instantiation-tightness}. Quadrature and generalized-eigenvalue calculations are dense float64 diagnostics, not verified certificates.} \\label{fig:transport-instantiation-tightness}',
    '{Original-study per-round mean cumulative decomposition over 50 transport-Hessian trajectories at $T=1000$. On this near-linear grid, the base confidence component, which includes the regularization/norm-bound term, dominates; historical linearization, path inflation, and current bias are shown separately. The red sharp right-hand side remains far above realized regret in every target condition.} \\label{fig:transport-instantiation-bound}',
    '{Original-study policy outcomes at the primary horizon $T=1000$. Mean-regret and paired-difference intervals are comparisonwise deterministic paired-bootstrap 95\\% intervals over the same 50 evaluation seeds. Each difference is the row method minus transport Hessian, so negative values favor the row method. Transport endpoint is a dense diagnostic comparator; naive current is an uncertified negative control.} \\label{tab:transport-instantiation-performance} \\evidencetabular{@{} >{\\raggedleft\\arraybackslash}p{    } >{\\raggedright\\arraybackslash}p{     } >{\\raggedright\\arraybackslash}p{     } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{     } >{\\raggedleft\\arraybackslash}p{    }@{}}{ \\input{tables/transport_instantiation_performance.tex}}',
    "{Policy outcomes and paired comparisons in every prespecified condition. Left: descriptive mean cumulative pseudo-regret at $T=1000$, without error bars. Right: each comparator's regret minus Hessian's, with pointwise 95\\% paired seed-bootstrap intervals from 10,000 resamples of 50 seeds per condition. Negative differences favor the comparator. The intervals condition on the fixed teacher, design and selected optimizer; they are not multiplicity-adjusted. Each policy follows its own adaptive history on matched exogenous streams. Changing $W$ changes the reward task as well as curvature, so the rows do not isolate an effect of drift.} \\label{fig:transport-followup-outcomes}",
    "{Policy outcomes.} At $T=1000$, mean regret for the operational Hessian-certificate policy rises from $81.0$ to $94.0$ across the four target conditions (\\Cref{tab:transport-instantiation-performance}). All three comparison policies have lower sample-mean pseudo-regret than transport Hessian in every reported condition at this horizon. These are matched-stream total-policy comparisons: the policies share contexts and potential outcomes, but their actions, fitted parameters, centers, radii, and widths may diverge after the first disagreement. The endpoint comparison is consistent with conservatism in the analytic envelope, but it does not isolate a fixed-history mechanism and does not provide a scalable policy certificate; it is a dense diagnostic comparator rather than a deployable policy. The naive score's observed optimism does not make it theoretically valid. Since $D_{\\rm target}$ also changes $W$, the cross-condition pattern is not a causal dose response. Read in the intended direction, these outcomes do not show a causal or uniform advantage for full curvature, and the reverse ordering they record is specific to this environment, this certificate, and this horizon.",
    "{Prespecified drift and bound diagnostics. The maximum and threshold counts use Hessian's 50,000 seed--round observations per condition; thresholds use $\\ge$. Mean terminal right-hand sides (RHS) use each named policy's own 50 histories. All individual primary and frozen-policy bounds exceed the corresponding deterministic regret cap.} \\label{tab:transport-followup-drift-bounds} \\input{tables/transport_followup_drift_bounds.tex}",
    '{Prespecified follow-up.} For \\Cref{sec:transport-followup}, the retained portable export contains all 600 evaluation seed summaries, the development and tuning summaries, selected optimizer, exact source and execution configurations, run provenance, terminal bound decompositions, drift summaries, and a raw-input hash inventory. An independent verifier reconstructs the reported terminal intervals from the seed summaries. The pinned Python environment and scientific source digests are recorded. Identifying metadata is redacted in packaged copies without changing scientific values; the declarations record their original and packaged digests. Full raw trajectories are retained outside Git and are not included in the compact supplement. The portable export alone does not reproduce every roundwise audit or regret-curve interval. A durable public raw-bundle URL is not provided.',
    '{Protocol.} We use the finite-dimensional scaled-tanh Gaussian specialization of \\Cref{cor:global-near-linear-new}. Contexts have dimension $4$, there are five actions, and the normalized context--action feature map has dimension $29$. The frozen and current matrices are formed densely, all widths use float64 Cholesky solves, and finite enumeration uses the smallest-index tie rule. Thus the intended theorem interface has \\[ \\alpha_t=1,\\qquad \\kappa_{-,t}=\\kappa_{+,t}=1,\\qquad \\xi_t=0. \\] These equalities describe the exact operator, solve, and selection abstractions. The recorded floating-point checks are diagnostics, not verified numerical certificates.',
    '{Reading the bound.} The instantaneous bound has a statistical radius $\\beta_t$, a frozen width $\\bar s_t(a_t)$, and a factor accounting for transport and computation. The exponential $e^{\\bar D_t}$ reflects two comparisons: a factor $e^{\\bar D_t/2}$ makes the current-width score optimistic, and another compares the selected current width back to the frozen width for the regret proof. The ratio $\\kappa_{+,t}/\\kappa_{-,t}$ accounts for operator distortion, and $\\alpha_t$ accounts for excess width from the solver. The additive terms charge current bias and approximate score maximization.',
    '{Replay and numerical checks.} The post-outcome audit replays the original representation optimizer with fixed logged actions and rewards for all 600 trajectories; it never replaces a behavior action or generates a new observation. It reconstructs collection-time category weights and compares the resulting sandwich, effective widths, and recommendations at the stored states. Matrix, center, and endpoint reconstruction are checked at rounds 1, 2, 10, 100, 500, and 1000; the original float64 tolerances are retained. These computations check an implementation of the mathematical construction, without converting floating-point residuals into verified certificates. All declared checks passed; the largest residual divided by its original tolerance was below $0.005$. The per-seed variation in the preceding table was reproduced by this separate fixed-action replay.',
    "{Selecting a shared optimizer.} We select the optimizer by prediction accuracy, using histories generated independently of the study policies' evaluation decisions. The 270 tuning trajectories cover nine optimizer candidates, three conditions, and ten tuning seeds, using uniform-random actions. The nine candidates combine learning rates $\\{3\\times10^{-5},10^{-4},3\\times10^{-4}\\}$ with $\\{1,5,20\\}$ full-batch steps. All were eligible. Candidate 008, learning rate $3\\times10^{-4}$ and 20 steps, minimized equally weighted all-action prediction MSE over the 30 tuning seed--condition cells, with selected MSE $0.00392155$. Evaluation consists of $3\\times4\\times50=600$ further trajectories. The 294 development and tuning trajectories are not evaluation replicates.",
    "{Sensitivity to score rounding.} We distinguish recomputing the final score from recomputing the quantities that enter it. This matters when two actions have nearly equal scores. The numerical scan reconstructs the recorded selected scores exactly and finds no nonfinite coefficients or scores and no zero widths. A separate 250-digit decimal calculation evaluates the final score arithmetic from the exact stored binary64 centers, widths, offsets, and \\emph{already rounded} coefficient $B_t$. It changes the primary recommendation at 16 states: five, five, and six in the respective conditions. Across all behavior histories there are 65 changes among 600,000 states. All occur at rounds 2--10, with score differences below 0.629 of a binary64 score ULP (the spacing of representable numbers at the score's magnitude). The decimal calculation does not recompute upstream matrix solves, exponentials, coefficients, or fitted parameters. An early changed action could affect subsequent adaptive history; that effect has not been measured. Likewise, equality between the full score vector and its bonus-plus-offset part in binary64 arithmetic includes initially zero centers and is not, by itself, evidence that the selected action was corrupted.",
    "{Start with an exact current matrix and exact widths.} For the moment, suppose the learner computes the current matrix and its width $s_t(a)$ exactly. Suppose also that a statistical argument bounds the absolute prediction error by $\\beta_t\\bar s_t(a)+b_t(a)$ in the frozen matrix. A \\emph{path certificate} bounds change along an auxiliary matrix path joining the frozen and current matrices; this need not be the learner's training trajectory. A valid certificate $\\bar D_t$ supplies the comparison $\\bar s_t(a)\\le e^{\\bar D_t/2}s_t(a)$ for every action. Thus the exact-case score is \\[ U_t(a)=m_t(a)+\\beta_t e^{\\bar D_t/2}s_t(a)+b_t(a). \\] On the joint confidence and certificate event, this score upper-bounds the mean reward. The multiplier enlarges the current width enough to retain the supplied reference confidence. The center must be the one justified by that confidence argument; it need not be the raw nonlinear prediction. \\Cref{sec:corrected-center} shows how to construct it.",
    '{The geometric and operator comparisons.} The metric geometry is established. \\citet{thompson1963certain} introduced the part metric now called the Thompson metric on ordered cones, and \\citet{nussbaum1994finsler} developed its Finsler structure and applications. On the positive-definite cone, the tangent norm is $\\|V^{-1/2}\\dot V V^{-1/2}\\|_{\\rm op}$. We use the resulting comparison between a path and its endpoints to connect frozen bandit confidence, current replayed GGN/Fisher curvature, approximate operators, and certified solver widths. The geometry and the path-to-endpoint comparison themselves are not contributions of this paper.',
    '{Validity audit.} For the primary policy, every one of the same 50 base seeds in each of the 12 horizon--target cells retained simultaneous reference confidence and transported optimism. The cellwise exact 95\\% Clopper--Pearson interval is $[92.9\\%,100\\%]$. Reusing base seeds across cells supports paired comparisons within a condition, not a pooled sample of 600 independent runs. The strict aggregate accepted all 2400 policy trajectories with no deterministic algebra or certificate-check failure, and the primary policy had no bound violation on the joint confidence event (\\Cref{tab:transport-instantiation-validity}). This finite-sample observation does not prove or empirically validate the theorem. In particular, ordinary float64 Cholesky, eigenvalue, and quadrature checks are not verified enclosures.',
    "{Variation across seeds and history-generating policies.} \\Cref{tab:transport-followup-mechanism-variation} reports per-seed variation instead of treating the pooled rounds as independent. The row label tells us which policy generated the history; the score being diagnosed is always Hessian's. Thus only Hessian rows describe the behavior policy's own score. The other rows ask what Hessian would recommend on states visited by endpoint, frozen reference, or naive current. They do not diagnose width dominance in those policies' own scores. Each fraction has 1000 rounds in its denominator, and the reported median and range summarize 50 seeds. These descriptive summaries are not confidence intervals.",
    "{What did the confidence and drift checks show?} The unfavorable policy outcomes did not coincide with a recorded failure of the confidence or optimism checks. The former check whether the reference bands contain the true mean rewards; the latter check whether the action scores upper-bound those means. All 600 evaluation trajectories, including naive current, pass the simultaneous reference-confidence, method-optimism, and deterministic diagnostics. Each policy--condition cell has 50 successes out of 50, with an exact 95\\% Clopper--Pearson interval of approximately $[92.9\\%,100\\%]$. These are observed checks, not proof of population coverage or of the need for transport. Float64 checks and converged quadrature are numerical diagnostics; they do not verify the theorem's assumptions through rigorous numerical enclosures.",
    "{What do the recorded decisions reveal?} After observing the policy outcomes, we examined how the Hessian score's width bonus related to its recommendations. We independently recomputed score diagnostics from all 600 preserved trajectories. On Hessian's own histories, its selected action equals the current-width argmax on 99.382\\%, 99.962\\%, and 99.982\\% of rounds for $W=16,1,0.25$. A stronger sufficient condition---the bonus gap between the two largest widths exceeding the entire range of prediction centers---holds on 97.104\\%, 99.372\\%, and 99.508\\% of rounds. Under this condition, differences in predicted reward cannot overturn the largest-width action's bonus advantage. Argmax agreement means that the policy chooses the action ranked first by current width under the same tie rule. The stronger condition identifies states where the bonus gap alone forces that choice. The rounds are dependent, and this retrospective calculation does not identify an adaptive causal mechanism.",
    "{What the experiments establish.} The main study uses a 29-parameter scaled-tanh model with dense matrices and direct Cholesky solves in float64 (\\Cref{sec:transport-followup}). It compares four policies in three prespecified conditions, with 50 paired seeds per condition. All nine pointwise paired intervals favor the comparators over Hessian transport. Transport inflation dominates Hessian's bound; the reference policy's own-trajectory bounds also remain vacuous. All policies, including the uncertified naive control, pass the recorded optimism diagnostics. These floating-point checks neither certify numerical enclosures nor establish that the correction was necessary in the observed runs.",
    '{What the intervals measure.} Pairing compares policies exposed to the same underlying context and potential-noise stream. It does not force them to select the same actions. The paired-bootstrap intervals resample the 50 evaluation seeds within a condition, preserving the pairing between policies, with 10,000 resamples and the recorded deterministic bootstrap seed. The nine intervals in \\Cref{tab:transport-followup-outcomes} are comparisonwise rather than multiplicity-adjusted. Shared seeds across conditions do not make the 600 trajectories independent observations from one common population. The teacher, conditions, and shared optimizer are fixed in this uncertainty calculation.',
    '{When the width bonus determines the action.} A large bonus can make the widest action win even when its predicted reward is lower. A sufficient check is that its bonus advantage exceeds the largest possible difference between prediction centers on the recorded state. Write the primary score on a recorded state as $m_t(a)+B_t s_t(a)+b_t$, where $b_t$ is action independent and $B_t=\\beta_t^{\\rm corr}\\exp(\\bar D_t^Q/2)$. Let $s_{t,(1)}\\ge s_{t,(2)}$ be the largest two current widths. The strict condition \\[ B_t\\bigl(s_{t,(1)}-s_{t,(2)}\\bigr) >\\max_a m_t(a)-\\min_a m_t(a) \\] is sufficient for the unique largest-width action to maximize the score. Width-argmax agreement alone is weaker: prediction centers might favor the same action. The exact tie rule is the smallest action index.',
    '{Which factors are compared?} For unit feature and parameter bounds, \\Cref{cor:tanh-relative-weights} gives the uniform endpoint bound $D_0=4\\log\\cosh(1/\\sqrt W)$, approximately $0.124$, $1.735$, and $5.300$ at the three conditions. The category-specific sandwich $c_{-,t}\\bVbar_t\\preceq\\bV_t\\preceq c_{+,t}\\bVbar_t$ gives a symmetric coefficient $\\exp(D_{{\\rm cat},t}/2)$, where $D_{{\\rm cat},t}=\\max\\{-\\log c_{-,t},\\log c_{+,t}\\}$, or the separate outward coefficient $\\sqrt{c_{+,t}}$ of \\Cref{cor:relative-endpoint-ucb}. The latter retains the separate return factor $c_{-,t}^{-1/2}$ in the cumulative bound. Neither category construction is an upper bound on the length of the original interpolated factor path.',
    "{Which policies incur less regret?} \\Cref{fig:transport-followup-outcomes} shows the higher mean regret of Hessian transport in each condition; \\Cref{tab:transport-followup-outcomes} gives the numerical values. The paired comparisons ask how much a comparator's regret differs from Hessian's on the same evaluation seed. All nine paired 95\\% intervals for this difference exclude zero in the comparator's favor. These are pointwise intervals from 10,000 paired seed-bootstrap resamples per comparison, without multiplicity adjustment. They describe evaluation-seed variation for the fixed teacher, design, and selected optimizer; they do not include uncertainty from choosing the environment or tuning the optimizer. Because policies follow their own adaptive histories, this comparison measures the outcome of each complete policy. It does not isolate the effect of changing only a certificate at a fixed state or establish a universal policy ordering.",
    '{Why the reference band alone does not justify a smaller current width. In this abstract instance, the reference and current metric unit balls have different supports in the query direction. With $D=\\log4$, $m=b=0$ and $\\beta=1$, the permitted mean $\\mu^*=1$ exceeds the naive score $1/2$, whereas multiplying the current width by $e^{D/2}$ recovers the reference width. The unit balls illustrate metric geometry; the current ball is not asserted to be a valid statistical confidence set. This is an analytic illustration, not an observed failure in the scaled-tanh study.} \\label{fig:transport-confidence-geometry}',
    '{Work with the gradients that form the matrix.} A replay matrix is a ridge term plus a Gram matrix of gradient features. Stack those features as rows of $\\Bmat$. It is often easier to bound how these rows change than to analyze the full SPD path directly. The next lemma turns a bound on the changing factor into a bound on matrix path length. Its normalization by $\\bV(\\tau)^{-1/2}$ retains information about which directions the data have already constrained.',
    '} \\newcommand{\\ccetablesize}{} \\newcommand{\\evidencetabular}[2]{ \\begingroup \\let\\ccerealtabular\\tabular \\renewcommand{\\tabular}[2][c]{\\ccerealtabular[##1]{#1}} #2 \\endgroup}',
)


def _u(*cited: tuple[int, int]) -> tuple[tuple[str, int], ...]:
    """Resolve `(unit index, offset)` pairs against UNITS."""

    return tuple((UNITS[index], offset) for index, offset in cited)


#: (path, phrase) -> (occurrences, ((unit, offset-in-unit), ...))
PHRASE_PINS: dict[tuple[str, str], tuple[int, tuple[tuple[str, int], ...]]] = {
    # paper/availability.tex
    ('paper/availability.tex', '600 evaluation seed summaries'):
        (1, _u((199, 103))),
    # paper/body_intro.tex
    ('paper/body_intro.tex', '29-parameter'):
        (1, _u((211, 56))),
    ('paper/body_intro.tex', '50 paired seeds'):
        (1, _u((211, 243))),
    # paper/legacy_scope.tex
    ('paper/legacy_scope.tex', '29-parameter'):
        (1, _u((56, 350))),
    # paper/transport_experiment.tex
    ('paper/transport_experiment.tex', '$1.20$--$1.22$ times the endpoint distance'):
        (1, _u((178, 485))),
    ('paper/transport_experiment.tex', '$1.88\\times10^6$'):
        (1, _u((178, 569))),
    ('paper/transport_experiment.tex', '$126.7$--$135.0$ at $T=1000$'):
        (1, _u((177, 195))),
    ('paper/transport_experiment.tex', '$2.0\\%$--$16.3\\%$'):
        (1, _u((58, 325))),
    ('paper/transport_experiment.tex', '$2.24\\times10^6$'):
        (1, _u((178, 839))),
    ('paper/transport_experiment.tex', '$2.51\\times10^5$'):
        (1, _u((178, 551))),
    ('paper/transport_experiment.tex', '$3{,}989$--$12{,}607$'):
        (1, _u((177, 448))),
    ('paper/transport_experiment.tex', '$79.4\\%$--$97.3\\%$'):
        (1, _u((58, 214))),
    ('paper/transport_experiment.tex', '$8.74\\times10^{-6}$'):
        (1, _u((178, 254))),
    ('paper/transport_experiment.tex', '$9{,}948$--$10{,}010$'):
        (1, _u((58, 601))),
    ('paper/transport_experiment.tex', '$T=1000$'):
        (8, _u((61, 1373), (178, 28), (178, 859), (178, 1056), (177, 215), (58, 172), (197, 22), (195, 55))),
    ('paper/transport_experiment.tex', '$[92.9\\%,100\\%]$'):
        (1, _u((207, 240))),
    ('paper/transport_experiment.tex', '$\\log 5\\approx1.609$'):
        (1, _u((61, 1690))),
    ('paper/transport_experiment.tex', '$e^{\\bar D_t^Q/2}$'):
        (1, _u((178, 982))),
    ('paper/transport_experiment.tex', '100 declared checkpoints per trajectory'):
        (1, _u((178, 345))),
    ('paper/transport_experiment.tex', '20 full-batch steps'):
        (1, _u((61, 1165))),
    ('paper/transport_experiment.tex', '5,000\neligible seed--checkpoint ratios'):
        (1, _u((178, 398))),
    ('paper/transport_experiment.tex', '50 evaluation seeds'):
        (2, _u((61, 58), (195, 188))),
    ('paper/transport_experiment.tex', '50 runs per cell'):
        (1, _u((189, 241))),
    ('paper/transport_experiment.tex', '50 trajectory-level observations per cell'):
        (1, _u((178, 295))),
    ('paper/transport_experiment.tex', '50 transport-Hessian trajectories'):
        (1, _u((58, 396))),
    ('paper/transport_experiment.tex', '600 independent runs'):
        (1, _u((207, 361))),
    ('paper/transport_experiment.tex', 'All five actions are optimal somewhere in every'):
        (1, _u((61, 1562))),
    ('paper/transport_experiment.tex', 'Contexts have dimension $4$'):
        (1, _u((200, 116))),
    ('paper/transport_experiment.tex', 'No run has zero regret'):
        (1, _u((177, 225))),
    ('paper/transport_experiment.tex', 'Ten disjoint tuning seeds'):
        (1, _u((61, 1095))),
    ('paper/transport_experiment.tex', '\\alpha_t=1'):
        (1, _u((200, 428))),
    ('paper/transport_experiment.tex', '\\kappa_{-,t}=\\kappa_{+,t}=1'):
        (1, _u((200, 446))),
    ('paper/transport_experiment.tex', '\\xi_t=0'):
        (1, _u((200, 481))),
    ('paper/transport_experiment.tex', 'all 2400 policy\ntrajectories'):
        (1, _u((207, 413))),
    ('paper/transport_experiment.tex', 'best-fixed-action regret $180.4$'):
        (1, _u((61, 1478))),
    ('paper/transport_experiment.tex', 'cap $2{,}000$'):
        (1, _u((58, 642))),
    ('paper/transport_experiment.tex', 'deterministic cap $2T$'):
        (1, _u((177, 337))),
    ('paper/transport_experiment.tex', 'each of the 12\nhorizon--target cells'):
        (1, _u((207, 81))),
    ('paper/transport_experiment.tex', 'exact 95\\% Clopper--Pearson interval'):
        (1, _u((207, 200))),
    ('paper/transport_experiment.tex', 'feature map has dimension $29$'):
        (1, _u((200, 204))),
    ('paper/transport_experiment.tex', 'horizons $T\\in\\{250,500,1000\\}$'):
        (1, _u((61, 25))),
    ('paper/transport_experiment.tex', 'is $126.7$--$155.7$ over the'):
        (1, _u((177, 152))),
    ('paper/transport_experiment.tex', 'is $3.07\\times10^5$'):
        (1, _u((178, 818))),
    ('paper/transport_experiment.tex', 'learning rate $3\\times10^{-4}$'):
        (1, _u((61, 1130))),
    ('paper/transport_experiment.tex', 'mean-only regret $185.4$'):
        (1, _u((61, 1536))),
    ('paper/transport_experiment.tex', 'no bound violation on the joint confidence event'):
        (1, _u((207, 529))),
    ('paper/transport_experiment.tex', 'no deterministic algebra or certificate-check failure'):
        (1, _u((207, 447))),
    ('paper/transport_experiment.tex', 'optimal-action\nentropy $1.579$'):
        (1, _u((61, 1422))),
    ('paper/transport_experiment.tex', 'optimality\ngap $0.123$'):
        (1, _u((61, 1454))),
    ('paper/transport_experiment.tex', 'paired-bootstrap 95\\%'):
        (1, _u((195, 142))),
    ('paper/transport_experiment.tex', 'pools all 50,000 seed--round values'):
        (1, _u((178, 1015))),
    ('paper/transport_experiment.tex', 'ranges from\n$1.02$'):
        (1, _u((178, 1074))),
    ('paper/transport_experiment.tex', 'ranges from $0.0486$'):
        (1, _u((178, 100))),
    ('paper/transport_experiment.tex', 'ranges from $1.31\\times10^{-7}$'):
        (1, _u((178, 219))),
    ('paper/transport_experiment.tex', 'rises\nfrom $81.0$'):
        (1, _u((197, 91))),
    ('paper/transport_experiment.tex', 'target labels $D_{\\rm target}\\in\\{0.25,0.5,1,2\\}$'):
        (1, _u((61, 83))),
    ('paper/transport_experiment.tex', 'the 50-seed means'):
        (1, _u((61, 1395))),
    ('paper/transport_experiment.tex', 'the same 50 base seeds'):
        (1, _u((207, 55))),
    ('paper/transport_experiment.tex', 'there are five actions'):
        (1, _u((200, 145))),
    ('paper/transport_experiment.tex', 'to $0.384$'):
        (1, _u((178, 121))),
    ('paper/transport_experiment.tex', 'to $1.18$'):
        (1, _u((178, 1093))),
    ('paper/transport_experiment.tex', 'to $94.0$'):
        (1, _u((197, 109))),
    ('paper/transport_experiment.tex', 'versus caps of $500$--$2{,}000$'):
        (1, _u((177, 471))),
    # paper/transport_experiment_appendix.tex
    ('paper/transport_experiment_appendix.tex', '$2.01\\%,4.04\\%,8.16\\%,16.27\\%$'):
        (1, _u((64, 566))),
    ('paper/transport_experiment_appendix.tex', '$97.33\\%,94.66\\%,89.39\\%,79.39\\%$'):
        (1, _u((64, 516))),
    ('paper/transport_experiment_appendix.tex', '$D_{\\rm target}=0.25,0.5,1,2$'):
        (1, _u((64, 601))),
    ('paper/transport_experiment_appendix.tex', '$T=1000$'):
        (3, _u((64, 400), (192, 49), (194, 98))),
    ('paper/transport_experiment_appendix.tex', '$e^{\\bar D_t^Q/2}$'):
        (2, _u((64, 729), (191, 360))),
    ('paper/transport_experiment_appendix.tex', '50 evaluation seeds'):
        (2, _u((67, 267), (192, 127))),
    ('paper/transport_experiment_appendix.tex', '50 primary-policy trajectories'):
        (1, _u((64, 351))),
    ('paper/transport_experiment_appendix.tex', '50 runs per cell'):
        (1, _u((191, 264))),
    ('paper/transport_experiment_appendix.tex', '50 transport-Hessian trajectories'):
        (1, _u((194, 61))),
    ('paper/transport_experiment_appendix.tex', '\\kappa_{-,t}=\\kappa_{+,t}=1'):
        (1, _u((64, 115))),
    ('paper/transport_experiment_appendix.tex', '\\xi_t=0'):
        (1, _u((64, 149))),
    ('paper/transport_experiment_appendix.tex', 'paired-bootstrap 95\\%'):
        (1, _u((192, 86))),
    ('paper/transport_experiment_appendix.tex', 'preregistered $10^{-12}$ ratio tolerance'):
        (1, _u((193, 490))),
    # paper/transport_followup.tex
    ('paper/transport_followup.tex', '$0.16\\%$'):
        (1, _u((31, 333))),
    ('paper/transport_followup.tex', '$0.28\\%$'):
        (1, _u((31, 266))),
    ('paper/transport_followup.tex', '$12.13\\%$'):
        (1, _u((31, 343))),
    ('paper/transport_followup.tex', '$12.68\\%$'):
        (1, _u((31, 276))),
    ('paper/transport_followup.tex', '$T=1000$'):
        (2, _u((62, 148), (196, 124))),
    ('paper/transport_followup.tex', '$W=0.25$'):
        (1, _u((65, 150))),
    ('paper/transport_followup.tex', '$W=16,1,0.25$'):
        (3, _u((40, 116), (33, 3), (210, 371))),
    ('paper/transport_followup.tex', '$W\\in\\{16,1,0.25\\}$'):
        (1, _u((62, 161))),
    ('paper/transport_followup.tex', '$[92.9\\%,100\\%]$'):
        (1, _u((209, 572))),
    ('paper/transport_followup.tex', '$\\delta=0.05$'):
        (1, _u((185, 411))),
    ('paper/transport_followup.tex', '10,000'):
        (2, _u((215, 447), (196, 260))),
    ('paper/transport_followup.tex', '16 of 50 seeds'):
        (1, _u((65, 132))),
    ('paper/transport_followup.tex', '20 full-batch steps'):
        (1, _u((63, 62))),
    ('paper/transport_followup.tex', '2000, 2000, and 1000'):
        (1, _u((179, 222))),
    ('paper/transport_followup.tex', '286 of 50,000'):
        (1, _u((65, 209))),
    ('paper/transport_followup.tex', '29-parameter'):
        (1, _u((63, 486))),
    ('paper/transport_followup.tex', '294 development and tuning trajectories'):
        (1, _u((62, 80))),
    ('paper/transport_followup.tex', '50 common evaluation seeds'):
        (1, _u((62, 187))),
    ('paper/transport_followup.tex', '50 histories'):
        (3, _u((33, 281), (176, 196), (198, 224))),
    ('paper/transport_followup.tex', '50 seeds per condition'):
        (1, _u((196, 280))),
    ('paper/transport_followup.tex', '50 successes out of 50'):
        (1, _u((209, 486))),
    ('paper/transport_followup.tex', '50,000 seed--round observations per condition'):
        (1, _u((198, 90))),
    ('paper/transport_followup.tex', '600 policy trajectories'):
        (1, _u((62, 37))),
    ('paper/transport_followup.tex', '97.104\\%'):
        (1, _u((210, 525))),
    ('paper/transport_followup.tex', '99.372\\%'):
        (1, _u((210, 535))),
    ('paper/transport_followup.tex', '99.382\\%'):
        (1, _u((210, 324))),
    ('paper/transport_followup.tex', '99.508\\%'):
        (1, _u((210, 549))),
    ('paper/transport_followup.tex', '99.962\\%'):
        (1, _u((210, 334))),
    ('paper/transport_followup.tex', '99.982\\%'):
        (1, _u((210, 348))),
    ('paper/transport_followup.tex', 'All 600 evaluation trajectories'):
        (1, _u((209, 304))),
    ('paper/transport_followup.tex', 'all 150 of its trajectories'):
        (1, _u((179, 460))),
    ('paper/transport_followup.tex', 'all 600 preserved trajectories'):
        (1, _u((210, 209))),
    ('paper/transport_followup.tex', 'approximately 19, 60, and 231'):
        (1, _u((33, 212))),
    ('paper/transport_followup.tex', 'approximately 9.51, 37.19, and 80.91'):
        (1, _u((33, 96))),
    ('paper/transport_followup.tex', 'dimension 29'):
        (1, _u((185, 303))),
    ('paper/transport_followup.tex', 'exact 95\\% Clopper--Pearson interval'):
        (1, _u((209, 518))),
    ('paper/transport_followup.tex', 'learning rate $3\\times10^{-4}$'):
        (1, _u((63, 26))),
    ('paper/transport_followup.tex', 'of 50,000 seed--round observations'):
        (1, _u((65, 213))),
    ('paper/transport_followup.tex', 'paired 95\\% intervals'):
        (1, _u((215, 330))),
    ('paper/transport_followup.tex', 'pointwise 95\\% paired'):
        (1, _u((196, 208))),
    ('paper/transport_followup.tex', 'regrets 180.01, 177.97, and 171.84'):
        (1, _u((40, 189))),
    ('paper/transport_followup.tex', 'regrets 185.26, 183.06, and 176.67'):
        (1, _u((40, 78))),
    ('paper/transport_followup.tex', 'same 600 recorded histories'):
        (1, _u((31, 64))),
    ('paper/transport_followup.tex', 'standard deviation $0.25$'):
        (1, _u((185, 327))),
    ('paper/transport_followup.tex', 'there are five actions'):
        (1, _u((185, 239))),
    # paper/transport_followup_appendix.tex
    ('paper/transport_followup_appendix.tex', '$0.00392155$'):
        (1, _u((203, 611))),
    ('paper/transport_followup_appendix.tex', '$0.005$'):
        (1, _u((202, 762))),
    ('paper/transport_followup_appendix.tex', '$0.124$'):
        (1, _u((214, 178))),
    ('paper/transport_followup_appendix.tex', '$1.735$'):
        (1, _u((214, 187))),
    ('paper/transport_followup_appendix.tex', '$3\\times4\\times50=600$'):
        (1, _u((203, 648))),
    ('paper/transport_followup_appendix.tex', '$4+5+20=29$'):
        (1, _u((180, 345))),
    ('paper/transport_followup_appendix.tex', '$5.300$'):
        (1, _u((214, 200))),
    ('paper/transport_followup_appendix.tex', '$T=1000$'):
        (1, _u((188, 71))),
    ('paper/transport_followup_appendix.tex', '$\\{1,5,20\\}$'):
        (1, _u((203, 388))),
    ('paper/transport_followup_appendix.tex', '$\\{3\\times10^{-5},10^{-4},3\\times10^{-4}\\}$'):
        (1, _u((203, 339))),
    ('paper/transport_followup_appendix.tex', '10,000'):
        (1, _u((212, 304))),
    ('paper/transport_followup_appendix.tex', '1000 rounds in its denominator'):
        (1, _u((208, 561))),
    ('paper/transport_followup_appendix.tex', '1024'):
        (1, _u((187, 205))),
    ('paper/transport_followup_appendix.tex', '12 combinations'):
        (1, _u((66, 284))),
    ('paper/transport_followup_appendix.tex', '2--10'):
        (1, _u((204, 690))),
    ('paper/transport_followup_appendix.tex', '20 steps'):
        (1, _u((203, 488))),
    ('paper/transport_followup_appendix.tex', '2048'):
        (3, _u((187, 128), (187, 214), (187, 295))),
    ('paper/transport_followup_appendix.tex', '24 declared trajectories'):
        (1, _u((187, 226))),
    ('paper/transport_followup_appendix.tex', '24 development trajectories'):
        (1, _u((180, 636))),
    ('paper/transport_followup_appendix.tex', '250-digit'):
        (1, _u((204, 325))),
    ('paper/transport_followup_appendix.tex', '270 tuning trajectories'):
        (1, _u((203, 169))),
    ('paper/transport_followup_appendix.tex', '294 development and tuning trajectories'):
        (1, _u((203, 697))),
    ('paper/transport_followup_appendix.tex', '30 tuning'):
        (1, _u((203, 560))),
    ('paper/transport_followup_appendix.tex', '30000--30001'):
        (1, _u((180, 89))),
    ('paper/transport_followup_appendix.tex', '30100--30109'):
        (1, _u((180, 116))),
    ('paper/transport_followup_appendix.tex', '30200--30249'):
        (1, _u((180, 151))),
    ('paper/transport_followup_appendix.tex', '4096'):
        (1, _u((187, 304))),
    ('paper/transport_followup_appendix.tex', '50 evaluation seeds'):
        (1, _u((212, 218))),
    ('paper/transport_followup_appendix.tex', '50 paired evaluation seeds'):
        (1, _u((188, 86))),
    ('paper/transport_followup_appendix.tex', '50 seeds per condition'):
        (1, _u((182, 191))),
    ('paper/transport_followup_appendix.tex', '50,000 dependent states'):
        (1, _u((66, 382))),
    ('paper/transport_followup_appendix.tex', '600,000 states'):
        (1, _u((204, 654))),
    ('paper/transport_followup_appendix.tex', '65 changes'):
        (1, _u((204, 637))),
    ('paper/transport_followup_appendix.tex', 'Candidate 008'):
        (1, _u((203, 438))),
    ('paper/transport_followup_appendix.tex', 'across 50 seeds'):
        (1, _u((181, 262))),
    ('paper/transport_followup_appendix.tex', 'all 600 trajectories'):
        (1, _u((202, 142))),
    ('paper/transport_followup_appendix.tex', 'and 1000 rounds'):
        (1, _u((182, 164))),
    ('paper/transport_followup_appendix.tex', 'at 16 states'):
        (1, _u((204, 533))),
    ('paper/transport_followup_appendix.tex', 'below 0.629'):
        (1, _u((204, 720))),
    ('paper/transport_followup_appendix.tex', 'divided by 1000'):
        (1, _u((66, 468))),
    ('paper/transport_followup_appendix.tex', 'learning rate $3\\times10^{-4}$'):
        (1, _u((203, 453))),
    ('paper/transport_followup_appendix.tex', 'pointwise 95\\% paired'):
        (1, _u((188, 222))),
    ('paper/transport_followup_appendix.tex', 'rounds 1, 2, 10, 100, 500, and 1000'):
        (1, _u((202, 437))),
    ('paper/transport_followup_appendix.tex', 'summarize 50 seeds'):
        (1, _u((208, 627))),
    ('paper/transport_followup_appendix.tex', 'teacher seed 1729'):
        (1, _u((180, 52))),
    ('paper/transport_followup_appendix.tex', 'the 600\ntrajectories'):
        (1, _u((212, 526))),
    # paper/transport_proofs.tex
    ('paper/transport_proofs.tex', '\\xi_t=0'):
        (2, _u((83, 414), (84, 565))),
    # paper/transport_theory.tex
    ('paper/transport_theory.tex', '$D_t<1$'):
        (1, _u((36, 214))),
    ('paper/transport_theory.tex', '\\alpha_t=1'):
        (1, _u((76, 696))),
    ('paper/transport_theory.tex', '\\kappa_{-,t}=\\kappa_{+,t}=1'):
        (2, _u((38, 29), (76, 710))),
    ('paper/transport_theory.tex', '\\xi_t=0'):
        (3, _u((80, 439), (72, 270), (76, 745))),
    # submissions/tmlr_2026/main.tex
    ('submissions/tmlr_2026/main.tex', '29-parameter'):
        (1, _u((51, 1185))),
    ('submissions/tmlr_2026/main.tex', '50 paired seeds'):
        (1, _u((51, 1220))),
    # submissions/tmlr_2026/supplement_README.md
    ('submissions/tmlr_2026/supplement_README.md', '2,400 trajectories'):
        (1, _u((9, 41))),
    ('submissions/tmlr_2026/supplement_README.md', '21 artifacts'):
        (1, _u((55, 30))),
    ('submissions/tmlr_2026/supplement_README.md', 'all 21 published tables, figures and CSVs'):
        (1, _u((8, 386))),
}

#: (path, literal) -> (category, occurrences, ((unit, offset-in-unit), ...))
CLASSIFIED_PINS: dict[tuple[str, str], tuple[str, int, tuple[tuple[str, int], ...]]] = {
    # README.md
    ('README.md', '1.15.2'):
        ('environment-version', 0, _u()),
    ('README.md', '2.2.3'):
        ('environment-version', 0, _u()),
    ('README.md', '3.12'):
        ('environment-version', 1, _u((45, 25))),
    # paper/availability.tex
    ('paper/availability.tex', '1.13.1'):
        ('historical-dependency-version', 1, _u((190, 661))),
    ('paper/availability.tex', '1.15.2'):
        ('historical-dependency-version', 1, _u((190, 600))),
    # paper/body_related.tex
    ('paper/body_related.tex', '1'):
        ('math-constant', 3, _u((206, 322), (206, 337), (34, 175))),
    ('paper/body_related.tex', '2'):
        ('math-constant', 2, _u((206, 324), (206, 339))),
    # paper/figures/transport_conceptual_geometry.tex
    ('paper/figures/transport_conceptual_geometry.tex', '.25'):
        ('analytic-schematic', 1, _u((98, 275))),
    ('paper/figures/transport_conceptual_geometry.tex', '.55'):
        ('analytic-schematic', 2, _u((98, 456), (106, 291))),
    ('paper/figures/transport_conceptual_geometry.tex', '.65'):
        ('analytic-schematic', 1, _u((106, 870))),
    ('paper/figures/transport_conceptual_geometry.tex', '.82'):
        ('analytic-schematic', 1, _u((106, 905))),
    ('paper/figures/transport_conceptual_geometry.tex', '0'):
        ('analytic-schematic', 8, _u((98, 250), (98, 424), (98, 453), (148, 23), (148, 85), (106, 857), (107, 314), (107, 431))),
    ('paper/figures/transport_conceptual_geometry.tex', '0,0'):
        ('analytic-schematic', 1, _u((98, 304))),
    ('paper/figures/transport_conceptual_geometry.tex', '0,13'):
        ('analytic-schematic', 1, _u((107, 107))),
    ('paper/figures/transport_conceptual_geometry.tex', '1'):
        ('analytic-schematic', 6, _u((98, 501), (98, 542), (106, 834), (105, 183), (107, 125), (107, 332))),
    ('paper/figures/transport_conceptual_geometry.tex', '1,0'):
        ('analytic-schematic', 1, _u((98, 407))),
    ('paper/figures/transport_conceptual_geometry.tex', '1,10'):
        ('analytic-schematic', 1, _u((107, 88))),
    ('paper/figures/transport_conceptual_geometry.tex', '1.05'):
        ('analytic-schematic', 1, _u((106, 37))),
    ('paper/figures/transport_conceptual_geometry.tex', '1.25'):
        ('analytic-schematic', 2, _u((148, 26), (148, 149))),
    ('paper/figures/transport_conceptual_geometry.tex', '1.8'):
        ('analytic-schematic', 2, _u((148, 88), (105, 170))),
    ('paper/figures/transport_conceptual_geometry.tex', '1.95'):
        ('analytic-schematic', 1, _u((105, 117))),
    ('paper/figures/transport_conceptual_geometry.tex', '10'):
        ('analytic-schematic', 3, _u((150, 91), (150, 132), (150, 146))),
    ('paper/figures/transport_conceptual_geometry.tex', '11.5'):
        ('analytic-schematic', 4, _u((105, 34), (105, 49), (107, 102), (107, 258))),
    ('paper/figures/transport_conceptual_geometry.tex', '13'):
        ('analytic-schematic', 3, _u((150, 105), (150, 173), (150, 187))),
    ('paper/figures/transport_conceptual_geometry.tex', '14.5'):
        ('analytic-schematic', 13, _u((105, 111), (105, 127), (105, 164), (149, 97), (149, 173), (149, 189), (149, 216), (150, 212), (151, 104), (151, 184), (151, 200), (151, 227), (107, 120))),
    ('paper/figures/transport_conceptual_geometry.tex', '14.72'):
        ('analytic-schematic', 1, _u((150, 269))),
    ('paper/figures/transport_conceptual_geometry.tex', '14.85'):
        ('analytic-schematic', 1, _u((107, 49))),
    ('paper/figures/transport_conceptual_geometry.tex', '16.2'):
        ('analytic-schematic', 1, _u((98, 270))),
    ('paper/figures/transport_conceptual_geometry.tex', '2'):
        ('analytic-schematic', 4, _u((106, 141), (151, 62), (107, 345), (107, 375))),
    ('paper/figures/transport_conceptual_geometry.tex', '2.1'):
        ('analytic-schematic', 1, _u((105, 40))),
    ('paper/figures/transport_conceptual_geometry.tex', '2.25'):
        ('analytic-schematic', 1, _u((149, 26))),
    ('paper/figures/transport_conceptual_geometry.tex', '2.35'):
        ('analytic-schematic', 1, _u((106, 173))),
    ('paper/figures/transport_conceptual_geometry.tex', '2.73'):
        ('analytic-schematic', 2, _u((149, 133), (149, 179))),
    ('paper/figures/transport_conceptual_geometry.tex', '2.85'):
        ('analytic-schematic', 3, _u((149, 87), (149, 103), (149, 222))),
    ('paper/figures/transport_conceptual_geometry.tex', '2.97'):
        ('analytic-schematic', 2, _u((149, 148), (149, 195))),
    ('paper/figures/transport_conceptual_geometry.tex', '3'):
        ('analytic-schematic', 5, _u((106, 126), (106, 138), (106, 218), (106, 297), (106, 380))),
    ('paper/figures/transport_conceptual_geometry.tex', '3.02'):
        ('analytic-schematic', 3, _u((106, 768), (106, 783), (106, 819))),
    ('paper/figures/transport_conceptual_geometry.tex', '3.525'):
        ('analytic-schematic', 3, _u((106, 485), (106, 613), (106, 630))),
    ('paper/figures/transport_conceptual_geometry.tex', '3.55'):
        ('analytic-schematic', 1, _u((106, 957))),
    ('paper/figures/transport_conceptual_geometry.tex', '3.6'):
        ('analytic-schematic', 4, _u((106, 168), (106, 637), (106, 651), (106, 686))),
    ('paper/figures/transport_conceptual_geometry.tex', '3.75'):
        ('analytic-schematic', 1, _u((150, 26))),
    ('paper/figures/transport_conceptual_geometry.tex', '30'):
        ('analytic-schematic', 1, _u((105, 12))),
    ('paper/figures/transport_conceptual_geometry.tex', '4'):
        ('analytic-schematic', 2, _u((98, 490), (106, 214))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.05'):
        ('analytic-schematic', 3, _u((106, 540), (106, 746), (106, 762))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.2'):
        ('analytic-schematic', 1, _u((106, 973))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.23'):
        ('analytic-schematic', 2, _u((150, 136), (150, 177))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.32'):
        ('analytic-schematic', 2, _u((106, 620), (106, 752))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.35'):
        ('analytic-schematic', 12, _u((106, 43), (106, 58), (106, 221), (106, 300), (106, 383), (106, 398), (106, 492), (106, 546), (150, 95), (150, 109), (150, 218), (150, 276))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.37'):
        ('analytic-schematic', 1, _u((106, 1008))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.4'):
        ('analytic-schematic', 2, _u((106, 646), (106, 778))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.47'):
        ('analytic-schematic', 4, _u((106, 680), (106, 813), (150, 150), (150, 191))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.53'):
        ('analytic-schematic', 1, _u((106, 434))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.6'):
        ('analytic-schematic', 2, _u((106, 393), (106, 429))),
    ('paper/figures/transport_conceptual_geometry.tex', '40'):
        ('analytic-schematic', 2, _u((106, 12), (106, 101))),
    ('paper/figures/transport_conceptual_geometry.tex', '5.2'):
        ('analytic-schematic', 1, _u((106, 53))),
    ('paper/figures/transport_conceptual_geometry.tex', '5.25'):
        ('analytic-schematic', 1, _u((151, 26))),
    ('paper/figures/transport_conceptual_geometry.tex', '5.73'):
        ('analytic-schematic', 2, _u((151, 142), (151, 190))),
    ('paper/figures/transport_conceptual_geometry.tex', '5.85'):
        ('analytic-schematic', 3, _u((151, 94), (151, 110), (151, 233))),
    ('paper/figures/transport_conceptual_geometry.tex', '5.97'):
        ('analytic-schematic', 2, _u((151, 157), (151, 206))),
    ('paper/figures/transport_conceptual_geometry.tex', '50'):
        ('analytic-schematic', 2, _u((107, 12), (107, 141))),
    ('paper/figures/transport_conceptual_geometry.tex', '55'):
        ('analytic-schematic', 1, _u((105, 74))),
    ('paper/figures/transport_conceptual_geometry.tex', '6'):
        ('analytic-schematic', 1, _u((106, 276))),
    ('paper/figures/transport_conceptual_geometry.tex', '6.35'):
        ('analytic-schematic', 2, _u((105, 55), (105, 133))),
    ('paper/figures/transport_conceptual_geometry.tex', '6.64'):
        ('analytic-schematic', 1, _u((107, 167))),
    ('paper/figures/transport_conceptual_geometry.tex', '6.7'):
        ('analytic-schematic', 3, _u((106, 129), (107, 40), (107, 56))),
    ('paper/figures/transport_conceptual_geometry.tex', '6.76'):
        ('analytic-schematic', 1, _u((107, 181))),
    ('paper/figures/transport_conceptual_geometry.tex', '6.86'):
        ('analytic-schematic', 1, _u((107, 216))),
    ('paper/figures/transport_conceptual_geometry.tex', '65'):
        ('analytic-schematic', 3, _u((98, 89), (106, 529), (106, 718))),
    ('paper/figures/transport_conceptual_geometry.tex', '7'):
        ('analytic-schematic', 4, _u((148, 146), (149, 23), (150, 23), (151, 23))),
    ('paper/figures/transport_conceptual_geometry.tex', '7.15'):
        ('analytic-schematic', 6, _u((106, 860), (106, 875), (106, 910), (106, 963), (106, 978), (106, 1014))),
    ('paper/figures/transport_conceptual_geometry.tex', '7.4'):
        ('analytic-schematic', 1, _u((107, 264))),
    ('paper/figures/transport_conceptual_geometry.tex', '7.85'):
        ('analytic-schematic', 1, _u((107, 317))),
    ('paper/figures/transport_conceptual_geometry.tex', '70'):
        ('analytic-schematic', 1, _u((98, 196))),
    ('paper/figures/transport_conceptual_geometry.tex', '8.15'):
        ('analytic-schematic', 1, _u((107, 34))),
    ('paper/figures/transport_conceptual_geometry.tex', '8.32'):
        ('analytic-schematic', 1, _u((107, 434))),
    ('paper/figures/transport_conceptual_geometry.tex', '8.35'):
        ('analytic-schematic', 1, _u((98, 253))),
    ('paper/figures/transport_conceptual_geometry.tex', '8.5'):
        ('analytic-schematic', 7, _u((149, 82), (149, 128), (149, 143), (151, 89), (151, 137), (151, 152), (107, 83))),
    ('paper/figures/transport_conceptual_geometry.tex', '80'):
        ('analytic-schematic', 3, _u((98, 138), (106, 474), (106, 585))),
    # paper/figures/transport_conceptual_interfaces.tex
    ('paper/figures/transport_conceptual_interfaces.tex', '.3'):
        ('analytic-schematic', 1, _u((97, 292))),
    ('paper/figures/transport_conceptual_interfaces.tex', '0'):
        ('analytic-schematic', 7, _u((97, 268), (147, 40), (104, 33), (104, 80), (104, 199), (104, 316), (104, 499))),
    ('paper/figures/transport_conceptual_interfaces.tex', '0,0'):
        ('analytic-schematic', 1, _u((97, 320))),
    ('paper/figures/transport_conceptual_interfaces.tex', '1.15'):
        ('analytic-schematic', 4, _u((152, 35), (4, 58), (3, 54), (2, 61))),
    ('paper/figures/transport_conceptual_interfaces.tex', '1.8'):
        ('analytic-schematic', 1, _u((152, 30))),
    ('paper/figures/transport_conceptual_interfaces.tex', '10.2'):
        ('analytic-schematic', 1, _u((3, 48))),
    ('paper/figures/transport_conceptual_interfaces.tex', '11'):
        ('analytic-schematic', 1, _u((70, 68))),
    ('paper/figures/transport_conceptual_interfaces.tex', '14.4'):
        ('analytic-schematic', 1, _u((2, 55))),
    ('paper/figures/transport_conceptual_interfaces.tex', '16.2'):
        ('analytic-schematic', 2, _u((97, 287), (104, 45))),
    ('paper/figures/transport_conceptual_interfaces.tex', '2'):
        ('analytic-schematic', 2, _u((97, 160), (104, 355))),
    ('paper/figures/transport_conceptual_interfaces.tex', '2.2'):
        ('analytic-schematic', 3, _u((147, 43), (35, 90), (70, 72))),
    ('paper/figures/transport_conceptual_interfaces.tex', '28'):
        ('analytic-schematic', 2, _u((97, 146), (104, 12))),
    ('paper/figures/transport_conceptual_interfaces.tex', '4.6'):
        ('analytic-schematic', 2, _u((104, 36), (104, 51))),
    ('paper/figures/transport_conceptual_interfaces.tex', '4.95'):
        ('analytic-schematic', 1, _u((104, 83))),
    ('paper/figures/transport_conceptual_interfaces.tex', '5.5'):
        ('analytic-schematic', 1, _u((35, 85))),
    ('paper/figures/transport_conceptual_interfaces.tex', '5.57'):
        ('analytic-schematic', 1, _u((104, 202))),
    ('paper/figures/transport_conceptual_interfaces.tex', '55'):
        ('analytic-schematic', 1, _u((97, 89))),
    ('paper/figures/transport_conceptual_interfaces.tex', '6'):
        ('analytic-schematic', 1, _u((4, 55))),
    ('paper/figures/transport_conceptual_interfaces.tex', '6.11'):
        ('analytic-schematic', 1, _u((104, 319))),
    ('paper/figures/transport_conceptual_interfaces.tex', '6.65'):
        ('analytic-schematic', 1, _u((104, 502))),
    ('paper/figures/transport_conceptual_interfaces.tex', '6.8'):
        ('analytic-schematic', 1, _u((97, 271))),
    # paper/notation.tex
    ('paper/notation.tex', '1'):
        ('math-constant', 2, _u((218, 153), (218, 157))),
    ('paper/notation.tex', '2'):
        ('math-constant', 3, _u((218, 61), (218, 129), (218, 162))),
    # paper/transport_experiment_appendix.tex
    ('paper/transport_experiment_appendix.tex', '1'):
        ('math-constant', 7, _u((184, 168), (184, 177), (17, 19), (16, 19), (27, 18), (27, 46), (18, 10))),
    ('paper/transport_experiment_appendix.tex', '2'):
        ('math-constant', 10, _u((184, 104), (184, 108), (184, 171), (17, 1), (17, 44), (16, 1), (16, 44), (27, 43), (27, 64), (18, 1))),
    # paper/transport_followup.tex
    ('paper/transport_followup.tex', '1'):
        ('math-constant', 2, _u((179, 200), (176, 154))),
    ('paper/transport_followup.tex', '2'):
        ('math-constant', 2, _u((179, 193), (176, 147))),
    # paper/transport_followup_appendix.tex
    ('paper/transport_followup_appendix.tex', '1'):
        ('math-constant', 4, _u((213, 434), (213, 526), (214, 151), (214, 581))),
    ('paper/transport_followup_appendix.tex', '2'):
        ('math-constant', 5, _u((213, 418), (213, 447), (213, 536), (214, 369), (214, 583))),
    ('paper/transport_followup_appendix.tex', '4'):
        ('math-constant', 1, _u((214, 140))),
    # paper/transport_proofs.tex
    ('paper/transport_proofs.tex', '0'):
        ('math-constant', 16, _u((48, 304), (42, 162), (42, 213), (39, 165), (90, 554), (90, 609), (41, 80), (41, 101), (175, 174), (175, 232), (175, 742), (78, 172), (52, 29), (52, 270), (52, 346), (52, 359))),
    ('paper/transport_proofs.tex', '0,1'):
        ('interval-endpoint', 1, _u((39, 179))),
    ('paper/transport_proofs.tex', '1'):
        ('math-constant', 80, _u((122, 114), (140, 18), (48, 17), (48, 284), (48, 293), (112, 42), (68, 127), (91, 546), (39, 235), (39, 291), (83, 121), (90, 383), (90, 455), (90, 485), (90, 572), (89, 130), (89, 154), (89, 175), (89, 192), (89, 248), (89, 273), (89, 296), (89, 507), (89, 539), (89, 566), (89, 599), (89, 707), (89, 772), (85, 86), (92, 299), (92, 464), (92, 491), (87, 181), (143, 16), (171, 48), (171, 56), (171, 150), (171, 179), (171, 188), (171, 349), (171, 424), (82, 68), (82, 207), (82, 305), (84, 134), (84, 549), (84, 556), (88, 521), (88, 599), (13, 2), (14, 4), (60, 18), (60, 398), (60, 428), (175, 107), (175, 368), (175, 531), (175, 573), (175, 627), (86, 108), (86, 141), (86, 153), (86, 421), (86, 431), (116, 58), (116, 118), (117, 99), (57, 31), (57, 55), (57, 178), (81, 234), (81, 247), (81, 298), (81, 374), (81, 417), (81, 432), (46, 17), (46, 342), (47, 529), (47, 670))),
    ('paper/transport_proofs.tex', '2'):
        ('math-constant', 110, _u((123, 55), (123, 93), (122, 116), (142, 44), (142, 80), (140, 103), (48, 134), (48, 181), (48, 204), (48, 232), (48, 244), (48, 335), (48, 346), (48, 363), (48, 380), (112, 55), (112, 78), (112, 88), (91, 226), (91, 251), (39, 283), (90, 385), (90, 457), (90, 487), (89, 132), (89, 156), (89, 177), (89, 194), (89, 250), (89, 275), (89, 385), (89, 509), (89, 541), (89, 555), (89, 568), (89, 601), (89, 630), (89, 709), (85, 109), (85, 230), (85, 239), (85, 251), (85, 353), (85, 366), (92, 99), (92, 123), (92, 139), (92, 168), (92, 222), (92, 253), (92, 277), (92, 305), (92, 466), (92, 493), (87, 183), (141, 73), (143, 103), (171, 182), (171, 532), (82, 58), (82, 167), (82, 176), (82, 316), (82, 336), (84, 122), (84, 130), (84, 327), (84, 336), (84, 438), (84, 477), (84, 486), (88, 248), (88, 258), (88, 281), (88, 293), (88, 304), (88, 368), (88, 504), (88, 528), (88, 564), (88, 596), (88, 632), (41, 141), (41, 209), (13, 26), (14, 26), (60, 155), (60, 166), (60, 193), (60, 221), (60, 251), (54, 203), (175, 210), (175, 288), (175, 295), (175, 499), (175, 525), (175, 575), (175, 667), (175, 703), (175, 725), (175, 732), (117, 127), (57, 225), (81, 271), (81, 322), (46, 42), (46, 72), (46, 113), (46, 245))),
    ('paper/transport_proofs.tex', '4'):
        ('math-constant', 4, _u((84, 431), (84, 441), (88, 642), (175, 522))),
    # paper/transport_theory.tex
    ('paper/transport_theory.tex', '0'):
        ('math-constant', 33, _u((43, 14), (43, 57), (37, 209), (121, 33), (75, 121), (75, 136), (103, 9), (49, 63), (95, 158), (95, 249), (95, 260), (216, 212), (119, 57), (119, 104), (165, 15), (10, 0), (10, 0), (10, 0), (10, 0), (10, 0), (10, 0), (93, 200), (50, 71), (69, 81), (126, 38), (186, 45), (72, 71), (76, 516), (94, 113), (94, 327), (129, 73), (129, 154), (6, 10))),
    ('paper/transport_theory.tex', '0,1'):
        ('interval-endpoint', 5, _u((79, 78), (93, 78), (50, 63), (50, 102), (174, 71))),
    ('paper/transport_theory.tex', '1'):
        ('math-constant', 100, _u((101, 10), (23, 25), (22, 22), (21, 24), (111, 63), (111, 90), (111, 106), (125, 116), (12, 9), (12, 34), (12, 67), (115, 78), (135, 68), (135, 88), (156, 15), (156, 36), (138, 68), (154, 15), (154, 36), (167, 134), (167, 202), (167, 269), (133, 69), (133, 94), (133, 115), (32, 203), (11, 0), (95, 296), (99, 92), (216, 226), (216, 256), (216, 284), (80, 241), (73, 1), (113, 58), (113, 74), (113, 103), (119, 70), (96, 356), (96, 365), (165, 22), (100, 23), (100, 52), (7, 80), (7, 189), (217, 378), (109, 59), (109, 90), (50, 99), (50, 242), (50, 378), (128, 43), (69, 46), (137, 31), (127, 55), (127, 82), (127, 115), (166, 20), (166, 55), (164, 204), (144, 67), (144, 97), (144, 118), (20, 12), (28, 17), (28, 26), (74, 120), (59, 103), (59, 162), (59, 191), (59, 207), (110, 71), (30, 9), (161, 45), (153, 29), (72, 195), (72, 231), (76, 793), (76, 858), (163, 25), (36, 98), (129, 55), (129, 136), (172, 11), (172, 19), (172, 22), (173, 225), (118, 31), (118, 71), (170, 103), (145, 67), (145, 87), (145, 103), (145, 113), (155, 15), (155, 36), (0, 2), (0, 13), (5, 8), (1, 1))),
    ('paper/transport_theory.tex', '1,0'):
        ('math-constant', 1, _u((95, 227))),
    ('paper/transport_theory.tex', '2'):
        ('math-constant', 113, _u((205, 529), (205, 623), (19, 19), (102, 9), (168, 4), (169, 12), (111, 117), (111, 128), (183, 200), (12, 36), (12, 69), (131, 68), (115, 164), (135, 23), (135, 33), (135, 80), (135, 160), (156, 6), (138, 23), (138, 33), (138, 81), (138, 90), (138, 94), (154, 6), (201, 247), (132, 4), (132, 26), (133, 4), (133, 24), (133, 34), (133, 81), (133, 85), (124, 62), (95, 312), (95, 378), (216, 286), (216, 337), (113, 76), (113, 105), (96, 358), (96, 367), (100, 25), (100, 54), (7, 101), (7, 122), (7, 168), (7, 204), (217, 380), (109, 92), (50, 177), (50, 380), (77, 116), (108, 58), (114, 122), (102, 9), (136, 40), (169, 12), (137, 42), (127, 57), (127, 84), (139, 28), (144, 22), (144, 32), (144, 79), (144, 84), (144, 88), (120, 78), (120, 86), (120, 88), (20, 23), (28, 20), (157, 81), (59, 216), (110, 82), (110, 102), (29, 57), (161, 39), (162, 33), (162, 43), (153, 6), (134, 4), (163, 19), (158, 12), (158, 21), (160, 25), (160, 35), (159, 21), (26, 21), (146, 14), (15, 8), (15, 39), (53, 14), (53, 35), (53, 158), (94, 246), (94, 307), (24, 21), (24, 58), (25, 21), (25, 58), (130, 38), (130, 73), (44, 164), (172, 108), (172, 145), (118, 41), (118, 81), (170, 93), (145, 22), (145, 32), (145, 79), (145, 171), (155, 6))),
    ('paper/transport_theory.tex', '3'):
        ('math-constant', 2, _u((53, 52), (53, 161))),
    ('paper/transport_theory.tex', '4'):
        ('math-constant', 6, _u((99, 78), (76, 780), (159, 12), (53, 49), (53, 150), (44, 212))),
    # submissions/tmlr_2026/supplement_README.md
    ('submissions/tmlr_2026/supplement_README.md', '1.15.2'):
        ('environment-version', 1, _u((71, 43))),
    ('submissions/tmlr_2026/supplement_README.md', '2.2.3'):
        ('environment-version', 1, _u((71, 27))),
    ('submissions/tmlr_2026/supplement_README.md', '3.12'):
        ('environment-version', 1, _u((71, 11))),
}

#: path -> SHA-256 of the whole normalized auditable text
FILE_PINS: dict[str, str] = {
    'README.md':
        '3dc113e7d7f09f873d1b4a1eace023794e616f2268421206ec39f377253f8801',
    'paper/availability.tex':
        '805154682b8991ec58161e9dc13f66b017aacb39e35312513cccc87332964ca3',
    'paper/body_conclusion.tex':
        'b372a84d535cb5d1fbf67e740f8c9470b8163fb98ddd1973d33f6330a368133a',
    'paper/body_intro.tex':
        '91616090202a9795e186b678f47d4ffe77845a10373aa8687ee9ba24025c0a4e',
    'paper/body_related.tex':
        '5dcba40a66d2d6892ee07e4f3dc5679e54c5a9c77a16c70a4fad3bfc2886c02f',
    'paper/broader_impact.tex':
        '41c44900a31c1d4274da9f69facd14255cfc61108c1ec592805208be3b8c0605',
    'paper/figures/transport_conceptual_geometry.tex':
        'ebff661954675d0d3732faf1e655b302dd934d6b6a60628a5fe4c0ce00d3218e',
    'paper/figures/transport_conceptual_interfaces.tex':
        '8887badd9f997fd3ac84d6affc65f0e44150b46bbedc3c9d45c66dec57e2a2c4',
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
        'b700b1329359d1773c37571eba444683a61d371beea9cecb40ebc69ab3e4b96c',
    'paper/transport_followup_appendix.tex':
        '966714a2ced59098263871881e360de19c772c843ad822388aeb614dedf69a89',
    'paper/transport_proofs.tex':
        'd9ff00e05381876fd7a5a3adac2fafc0ec0cc2556feaef8ba32d6dfa3f750558',
    'paper/transport_theory.tex':
        '966350070de33b27119fe8f1f9a682cb0af0b9dbc53fc792e97fe0e0ddfe6019',
    'submissions/tmlr_2026/main.tex':
        '43470533f05a3304baa0509e1715b4bf151bbecf1e70dec348c1e31e6ff98868',
    'submissions/tmlr_2026/supplement_README.md':
        '6dfcdf200d422579113cdf732e34ce98bc1b2f72f3d1a1997a7aafd6d2a9f9b0',
}
