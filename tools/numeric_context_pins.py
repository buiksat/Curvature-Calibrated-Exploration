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
    '$-$0.10',
    '$-$0.18',
    '$-$22.57',
    '$-$34.41',
    '$1$',
    '$W=1$',
    '$W=10$',
    '$W=100$',
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
    '12.30',
    '16.75',
    '1{,}003.8',
    '1{,}004.4',
    '1{,}004.5',
    '1{,}879.1',
    '1{,}886.9',
    '1{,}902.1',
    '2{,}396.8',
    '2{,}837.6',
    '31.63',
    '33.4',
    '340.0',
    '37.35',
    '3{,}784.6',
    '4.22',
    '42.8',
    '43.1',
    '43.2',
    '43.3',
    '43.4',
    '43.47',
    '43.5',
    '43.9',
    '44.1',
    '440.3',
    '440.9',
    '441.2',
    '4{,}789.0',
    '5.16',
    '5.53',
    '5.58',
    '5.86',
    '6.24',
    '65.87',
    '65.94',
    '66.04',
    '6{,}733.3',
    '82.79',
    '8{,}635.4',
    '8{,}667.5',
    '9.05',
    '95\\% interval',
    '9{,}294.0',
    '9{,}364.3',
    '9{,}372.05',
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
    'Algorithm~\\ref{alg:transported-ucb} allows a pre-reward $\\xi_t$-approximate selector. The main finite-action rule uses the smallest-index exact maximizer, so $\\xi_t=0$ as in \\Cref{cor:finite-enumeration-new}.',
    "All quantities are evaluated on this policy's own selected history. No path, current-metric, or operator certificate is needed for this score. If its reference-confidence event has probability at least $1-\\delta$, so does this guarantee.",
    'Certified path-length envelope $\\bar D_t$.}; \\node[anchor=north west,align=left] at (5.5,-2.2) {\\textbf{B\\quad Operator comparison}',
    'Consequently, $W=\\Omega(T)$ with a sufficiently large problem-dependent constant keeps $D_{T,W}=O(1)$. For fixed $d$ and fixed problem constants, \\[ R_T=O(d\\sqrt T\\log T)+O(\\sqrt T). \\] This conclusion requires no $D_t<1$ condition. Here $W$ is an abstract near-linearity scale, not generic network width or parameter count, and the result is not an unrestricted neural-training theorem. No optimizer-residual rate is required because the corrected center is used.',
    'Every certified bound in the first study is vacuous, so it cannot show what transport does where the theory is informative. A second prespecified study chooses a model and, in its design cell, a scale at which the frozen bound is below the cap on every trajectory, and adds two baselines: UCB-GLM \\citep{li2017provably} and a linear UCB. In its design cell, endpoint transport and naive current are equivalent to frozen scoring within the prespecified margin, the Hessian width costs 16.8 regret units relative to frozen, and UCB-GLM has 34.4 units less regret than frozen. In three descriptive cells with stronger curvature every certified bound is vacuous, and at $W=1$ UCB-GLM has about 7.7 times the regret of linear UCB.',
    "Every policy uses the Taylor envelope at the current parameter norm, $\\epslin=\\tfrac12(c_h/\\sqrt W)(R+\\|\\btheta_t\\|_2)^2$ with $c_h=4/(3\\sqrt3)$ and $R=B_\\phi=1$, both for the bias $b_t$ and for the historical terms of $\\beta_t$. At $\\|\\btheta_t\\|_2=R$ it equals the constant $2c_hR^2/\\sqrt W$ of \\Cref{cor:global-near-linear-new}: 0.385, 1.540 and 3.079 at $W=16,1,0.25$. The per-run mean envelope is 98.3\\%--98.5\\% of that constant (median over seeds, for every policy and condition). Three terms set the scale of the frozen bound $2\\sqrt{(\\sigma^2+G^2/\\lambda)\\gamma_T\\sum_t\\beta_t^2}+2\\sum_tb_t(a_t)$ of \\Cref{prop:frozen-width-ucb}: the exploration term with $\\beta_t$ reduced to its stochastic and ridge parts; the remainder of the exploration term, due to the historical Taylor part of $\\beta_t$; and the bias term. On the frozen policy's own histories their medians are 10,155, 26,898 and 758 at $W=16$; 10,122, 108,171 and 3,031 at $W=1$; and 10,001, 215,317 and 6,063 at $W=0.25$. The first term alone exceeds every cap: with $d=29$ and $T=1000$ the realized $\\gamma_T$ is about 151--153 (medians). It contains no Taylor term, and on the same queries a linear model's frozen matrix dominates the scaled-tanh one because every collection weight satisfies $\\operatorname{sech}^4\\le1$. On the 150 recorded context--action sequences, an exactly linear model's frozen bound would therefore exceed its own cap $2T=2000$ as well. The historical term grows as $1/\\sqrt W$ and is the largest term at every $W$; the bias term is about $2T$ times the mean envelope.",
    'Exact current curvature has $\\kappa_{-,t}=\\kappa_{+,t}=1$. More generally, the operational relative-error certificate',
    'Fix $\\delta\\in(0,1)$. Let $\\rho_s^\\circ$ be the Taylor remainder of $\\mu_{\\btheta^\\circ}$ around $\\btheta_s$. Supply historical Taylor and misspecification envelopes',
    'For completeness, an exact scalar endpoint distance does not generally give the actionwise equality. Set $\\bVbar=I_2$, $\\bV=\\operatorname{diag}(e^D,e^{-D})$ with $D>0$, and $\\bq=(0,1)^\\top$. Then $d_{\\rm Th}(\\bVbar,\\bV)=D$ and $\\bar s=1$, whereas the scalar corrected width is $e^{D/2}s=e^D>1$.',
    'For the category certificate, finite positive collection weights imply $f_{t,c}>0$ whenever $n_{t,c}>0$, and \\[ \\bVbar_t=\\lambda\\bI+\\sigma^{-2}\\sum_c f_{t,c}\\phi_c\\phi_c^\\top, \\qquad \\bV_t=\\lambda\\bI+\\sigma^{-2}\\sum_c g_{t,c}\\phi_c\\phi_c^\\top. \\] For $m=c_{-,t}$ and $M=c_{+,t}$, the definitions give',
    'For the fixed-band statement, the largest admissible mean is $m_t(a)+\\beta_t\\bar s_t(a)+b_t(a)$. Comparing this endpoint to the proposed score and using $\\beta_t>0$ proves necessity and sufficiency. When $\\beta_t=0$, this comparison imposes no restriction on the candidate width. It makes no assertion about uncertainty sets constrained by additional information or about distinct adaptive histories.',
    'Here $\\lambda>0$ is ridge regularization and $\\sigma>0$ is the update scale (the noise scale for squared loss). For the same query, define',
    'If the observed feature vectors belong to a finite set $\\{\\phi_c\\}$, let $n_{t,c}$ be their counts, let $f_{t,c}=\\sum_{s<t:\\phi(z_s)=\\phi_c}\\omega_{\\btheta_s}(z_s)^2$, and put $g_{t,c}=n_{t,c}\\operatorname{sech}^4(\\phi_c^\\top\\btheta_t/\\sqrt W)$. The sharper category certificate is',
    'Let $\\bu=\\Calg^{-1}\\bq$. Since $s_{\\Calg}^2=\\bq^\\top\\bu=\\|\\bu\\|_{\\Calg}^2$, \\[ \\left|\\bq^\\top\\tilde\\bu-s_{\\Calg}^2\\right| =\\left|\\langle\\bu,\\tilde\\bu-\\bu\\rangle_{\\Calg}\\right| \\le\\|\\bu\\|_{\\Calg}\\|\\tilde\\bu-\\bu\\|_{\\Calg} \\le\\varepsilon s_{\\Calg}^2. \\] This proves the pointwise two-sided quadratic-form comparison. Dividing its lower side by $1-\\varepsilon$ gives upper validity for this query, while combining both sides gives the displayed sharpness factor. Applying the lower inequality actionwise on the simultaneous family event gives the all-domain upper condition; only the played query uses the upper inequality for sharpness. For PCG the argument is unchanged once the certificate is expressed in the original $\\Calg$-energy norm.',
    'Let $\\mathcal J$ be a finite or countable certificate-source index set. For $j\\in\\mathcal J$, choose an $\\cHist_t^-$-measurable failure budget $\\delta_{j,t}$ before drawing its random object. Let $\\mathcal P_{j,t}$ be the pre-reward sigma-algebra immediately before that draw. It may equal $\\cHist_t^-$ for a round-start draw or include the selected action and earlier randomness for a post-selection check. It is sufficient that \\[ \\Pr(\\mathcal E_{j,t}^c\\mid\\mathcal P_{j,t})\\le\\delta_{j,t}, \\qquad \\sum_{j\\in\\mathcal J}\\sum_{t=1}^T\\delta_{j,t} \\le\\delta_{\\rm cert}\\quad\\text{almost surely}. \\] The tower property and a union bound give simultaneous validity at least $1-\\delta_{\\rm cert}$ without independence. Countability makes the joint event measurable, the nonnegative double sum well-defined, and the union bound valid. On an uncountable score domain, the solver upper event must already be simultaneous. A pointwise certificate cannot be union-bounded after adaptive selection unless it is separately verified at the selected action with the correct conditioning. Realized terminal spectral quantities may be used for post-hoc analysis, but they cannot be inserted into an earlier action-time radius unless a predictable prefix envelope was supplied at that time.',
    'Let $c_t=\\beta_t[1+\\alpha_te^{\\bar D_t} \\sqrt{\\kappa_{+,t}/\\kappa_{-,t}}]$. Summation and one Cauchy--Schwarz application give \\[ R_T-2\\sum_tb_t(a_t)-\\sum_t\\xi_t \\le\\sqrt{\\sum_tc_t^2}\\sqrt{\\sum_t\\bar s_t^2(a_t)}. \\] Since $\\bar s_t^2(a_t)\\le G^2/\\lambda$, the scalar inequality $x\\le(1+M)\\log(1+x)$ for $0\\le x\\le M$, with $x=\\sigma^{-2}\\bar s_t^2(a_t)$ and $M=G^2/(\\lambda\\sigma^2)$, yields',
    'More generally, fix an action and $m_t(a)$, $b_t(a)$, $\\beta_t>0$, and $\\bar s_t(a)$. If the only restriction on its mean is the full interval \\eqref{eq:abstract-confidence-new}, a score $m_t(a)+\\beta_t w_t(a)+b_t(a)$ is an upper bound for every mean in that interval if and only if $w_t(a)\\ge\\bar s_t(a)$.',
    'More generally, suppose there is a measurable function $\\nu_t:[0,1]\\to[0,\\infty)$ with $\\nu_t\\in L^1([0,1])$ such that \\[ \\dot\\Bmat(\\tau)^\\top\\dot\\Bmat(\\tau) \\preceq\\nu_t(\\tau)^2\\bV(\\tau) \\] almost everywhere. Then $\\mathcal D(\\bV)\\le2\\int_0^1\\nu_t(\\tau)d\\tau$. For nonnegative $\\nu_t$, the displayed PSD premise is equivalently the norm condition $\\|\\dot\\Bmat(\\tau)\\bV(\\tau)^{-1/2}\\|_{\\rm op}\\le\\nu_t(\\tau)$ almost everywhere.',
    "Post-outcome score diagnostics show that the Hessian policy's bonus determines its action by current width alone on almost all rounds: the gap between the two largest width bonuses exceeds the full center range on 97.104\\%, 99.372\\% and 99.508\\% of rounds at $W=16,1,0.25$. Its action agrees with the current-width argmax on 99.382\\%, 99.962\\% and 99.982\\% of rounds. Its mean pseudo-regret is close to the context-free benchmark's 185.26, 183.06 and 176.67. Endpoint, frozen reference and naive current are not separated by this study: their mean regrets are within about one unit in each condition (\\Cref{tab:transport-followup-outcomes}). No equivalence test was performed. All nine pointwise paired comparisons favor these comparators over Hessian. Both Hessian's bounds and the frozen policy's own bounds exceed the deterministic cap, while every recorded confidence and optimism check passes. \\Cref{sec:transport-v3} reports a second prespecified study in which the frozen bound is informative and two generalized-linear baselines are added.",
    "Relinearizing historical gradients changes a contextual-bandit uncertainty matrix without adding observations. For squared loss, we construct a corrected-center confidence band along predictable parameter paths in a certified region, with supplied approximation-error bounds and no optimizer convergence requirement. We establish a reference-width floor on fixed histories and sharp symmetric exponential transport factors. For scaled tanh, relative gradient weights give a horizon-independent endpoint certificate. A transported-UCB theorem connects these results through explicit statistical, matrix and solver conditions. A prespecified study compares four policies in three conditions of a synthetic 29-parameter scaled-tanh model, with 50 paired seeds per condition. Hessian transport has higher mean pseudo-regret than every comparator; all nine pointwise paired 95\\% intervals exclude zero. Its bonus usually determines its action, and its bounds and the frozen policy's own bounds exceed the deterministic cap. All four policies pass the recorded confidence and optimism checks. A second prespecified study, at a scale where the frozen bound is below the reward cap, finds endpoint transport equivalent to frozen scoring within a prespecified margin, a regret cost of 16.8 units for Hessian transport, and 34.4 units less regret for a generalized-linear UCB baseline, which has higher regret than linear UCB in the most curved descriptive cell.",
    'Set $\\gamma_0=0$. The determinant identity follows from the frozen rank-one update and uses the actions actually selected.',
    'Set $\\hat s=\\sqrt{U}$. If $L>0$, the observable factor $\\alpha=\\sqrt{U/L}$ verifies played-action sharpness. If $L\\le0<U$, the interval supplies no finite positive multiplicative sharpness factor; the solve must continue or an additive-width theorem must be used. If $U=0$, the exact inverse quadratic form is zero and the solver returns $\\hat s=0$. For $\\bq=0$, skip the solve and return zero.',
    'Since $\\sup_u|2\\operatorname{sech}^2(u)\\tanh(u)|=4/(3\\sqrt3)$, \\Cref{cor:global-near-linear-new} applies with \\[ G=B_\\phi,\\qquad c_\\mu=c_g=c_h:=\\frac{4B_\\phi^2}{3\\sqrt3}. \\] The symbol $W$ is a smoothness scale here; it is not identified with hidden width or parameter count.',
    'The category certificate uses only scalar sums and current projections. After collecting category $c$ at time $t$, its count increases by one and its collection sum increases by $\\omega_{\\btheta_t}(z_t)^2$; other category sums are unchanged. These are sufficient statistics for this comparison, although the category factors need not be the tight spectral factors when feature outer products are linearly dependent.',
    'The constant $2$ is asymptotically attained: for fixed $\\epsilon>0$, $\\cosh^2(u)/\\cosh^2(u-\\epsilon)\\to e^{2\\epsilon}$ as $u\\to\\infty$. That limit is excluded by the norm bounds used below; under them the refined constant $2\\tanh x$ is sharp as a Lipschitz constant (take $u_1,u_2\\to x$). Neither statement is a sharpness claim about $D_t^{\\rm lip}$.',
    'The earlier audit contributes 21 artifacts. Its tables, CSVs and inactive figure sources retain their original bytes, provenance records and checksum sidecars. The follow-up contributes separately generated tables and explanatory charts with separate collective provenance records, all independently pinned in code. The conceptual diagrams are reviewed analytical schematics with separate source pins, not measured study outcomes. The excluded legacy appendix, symbolic rate table, autodiff-GGN benchmark and linear-bound benchmark are not evidence for the active manuscript and are not included.',
    'The earlier experiments did not execute the transported score or record its path, operator, and solver certificates. They therefore provide no evidence for the current theorem or its numerical performance. The present paper makes no empirical claim for a large neural model, an approximate operator, or an iterative solver: its reported study uses a 29-parameter model and dense Cholesky solves. These exclusions do not change the conditional operator and solver interfaces proved in the theorem.',
    'The exact solution is $\\Calg^{-1}\\bq=\\tilde\\bu+\\Calg^{-1}\\br$. Substitute this expression and $\\bq=\\Calg\\tilde\\bu+\\br$ into the quadratic form. The remainder is $\\br^\\top\\Calg^{-1}\\br$, which lies between zero and $\\|\\br\\|_2^2/\\lambda_{\\Calg}$.',
    "The existing cumulative decomposition in \\Cref{fig:transport-instantiation-bound} separates base confidence, historical linearization, path inflation, and current bias. At $T=1000$, the base component accounts for $79.4\\%$--$97.3\\%$ of the mean terminal sharp right-hand side across target cells; path inflation accounts for $2.0\\%$--$16.3\\%$. Each percentage divides a component's mean over the 50 transport-Hessian trajectories by the mean sharp right-hand side over those same trajectories. These are ratios of means, not medians of runwise shares. The base component alone has cell means of about $9{,}948$--$10{,}010$, already above the cap $2{,}000$. It includes the statistical and regularization/norm-bound terms together with the determinant-potential and Cauchy--Schwarz factors; its size cannot be attributed to the confidence radius alone. Thus most of the bound's size on this original near-linear grid is present before path inflation is added. This dominance statement does not describe the nonlinear follow-up. This is a decomposition along transport-Hessian histories, not a bound evaluated on the frozen-reference policy's different histories. The appendix defines the components and reports the complete tightness charts.",
    'The historical deterministic term follows from $\\Phi_t^\\top\\bVbar_t^{-1}\\Phi_t\\preceq I$, with $\\Phi_t=[\\bq_1/\\sigma,\\ldots,\\bq_{t-1}/\\sigma]$; its scale is $1/\\sigma$.',
    'The inclusion of $1$ in the minimum and maximum accounts for the ridge. Each category ratio is a weighted average of sample ratios $r_s=\\widetilde\\omega_s^2/\\omega_s^2$, with weights $\\omega_s^2/f_{t,c}$. Therefore $\\ell^2\\le g_{t,c}/f_{t,c}\\le\\ell^{-2}$, which gives the asserted uniform bounds on $m,M$. It also shows that the category factors are no looser than the direct sample factors $\\min\\{1,\\min_{s<t}r_s\\}$ and $\\max\\{1,\\max_{s<t}r_s\\}$. For an empty history both metrics equal $\\lambda\\bI$.',
    "The locked grid contains horizons $T\\in\\{250,500,1000\\}$, 50 evaluation seeds, and target labels $D_{\\rm target}\\in\\{0.25,0.5,1,2\\}$. Each $(T,D_{\\rm target})$ cell is a separately executed model condition because both quantities enter the rule for $W$. The target label is neither realized transport distance nor generic network width, so trends across targets are not a dose response to certificate inflation. The four policies share contexts and potential-noise tables. The primary \\emph{transport Hessian} policy uses $\\bar D_t^Q$ in the score. The \\emph{transport endpoint} policy replaces it by the dense endpoint Thompson distance computed from the learner-known matrices $\\bVbar_t$ and $\\bV_t$ before the reward is observed; it is a dense diagnostic comparator. The \\emph{frozen reference} policy uses the frozen width directly. The \\emph{naive current} policy omits transport and is intentionally uncertified. Each policy has its own selected history and representation path; the frozen-reference policy also updates its representation. ``Frozen'' refers to its collection-time metric. Ten disjoint tuning seeds selected learning rate $3\\times10^{-4}$ and 20 full-batch steps followed by projection each round by preregistered all-action prediction MSE; evaluation seeds never entered that selection. The environment was not filtered after generation. Within each $T=1000$ target cell, the 50-seed means round to optimal-action entropy $1.579$, optimality gap $0.123$, best-fixed-action regret $180.4$, and online context-free mean-only regret $185.4$. All five actions are optimal somewhere in every evaluation stream. Entropy is measured in nats; its maximum for five actions is $\\log 5\\approx1.609$, so the mean entropy is close to its uniform-action maximum. These diagnostics were reported after the grid was fixed; they were not used to select seeds.",
    'The second study (\\Cref{sec:transport-v3}) shares these limits and adds its own. It covers one six-dimensional model with 12 feature categories and one optimizer, selected in the design cell and not retuned per cell. Its design checks hold by construction in a near-linear cell and test the setup, not transport. Its descriptive cells were chosen after development output was read and carry no test. UCB-GLM runs exactly as specified in every cell, with a random-phase stopping rule of our choosing, and its regret theorem does not apply; neither UCB-GLM nor linear UCB is certified here, and the bound comparison after \\Cref{cor:tanh-endpoint-regime} does not predict realized regret.',
    "Their sum equals the sharp right-hand side in \\eqref{eq:sharp-transport-regret-new} for the experiment's $\\alpha_t=\\kappa_{-,t}=\\kappa_{+,t}=1$ and $\\xi_t=0$. The differences retain the same trajectory and the same potential factor; they do not rerun a policy with a component removed. The committed figure CSVs report the mean of each component over 50 primary-policy trajectories at each round. At $T=1000$, dividing those terminal component means by the corresponding mean sharp right-hand side gives base shares $97.33\\%,94.66\\%,89.39\\%,79.39\\%$ and path shares $2.01\\%,4.04\\%,8.16\\%,16.27\\%$ for $D_{\\rm target}=0.25,0.5,1,2$, respectively. The remaining tightness summaries appear in \\Cref{fig:transport-original-components,fig:transport-original-bound-ratios}. These joint cumulative quantities establish the decomposition; marginal medians of $e^{\\bar D_t^Q/2}$ do not determine it.",
    "This analysis asks what different scores recommend when given the same information. For each logged state, we evaluate all four original score rules using that state's matrices, centers, and radii, without changing its history. \\Cref{fig:transport-followup-same-history} includes all 12 combinations of condition and behavior policy. Each point averages one-step pseudo-regret over 50,000 dependent states; the black-ringed points equal the actual mean cumulative pseudo-regret divided by 1000. The other points are recommendations on states visited by the row policy. The analysis was specified after the full-study outcomes were observed.",
    'This appendix expands the original locked full aggregate summarized in \\Cref{sec:transport-instantiation}. The experiment protocol, configuration, selection record, aggregate, and every generated artifact carry provenance and         hashes. The figures use only the 50 evaluation seeds. Smoke and tuning results are absent. The original raw trajectories were unavailable for this revision; recorded hashes bind the retained artifacts but do not replace those missing inputs or establish an independent raw-data reproduction.',
    'This proves \\eqref{eq:sharp-transport-regret-new}. Finally, $\\alpha_te^{\\bar D_t}\\sqrt{\\kappa_{+,t}/\\kappa_{-,t}}\\ge1$, hence $1+x\\le2x$ gives \\eqref{eq:simple-transport-regret-new}. The probability statement follows by a union bound; independence is not required.',
    'This remains valid when $\\bar D_t\\ge1$. At $t=1$, the factor has zero rows, $Q_1=0$, and both metrics equal $\\lambda\\bI$.',
    'Two-sided SPD comparison.}; \\node[anchor=north west,align=left] at (11,-2.2) {\\textbf{C\\quad Solver certificate}',
    'Use Python 3.12 with NumPy 2.2.3 and SciPy 1.15.2. These are the declared versions in `experiments/requirements.txt`. The supplied `experiments/requirements-python312.lock` additionally pins the portable Linux x86_64 wheel environment, including the test dependencies. A separate online installation may use `pip install --require-hashes --only-binary=:all: -r experiments/requirements-python312.lock`. The verification commands themselves do not install or download anything.',
    'With exact realizability and a frozen linear model, $B_T=E_T^{\\rm cur}=0$. For fixed $d$ and problem constants, the leading term is then $O(e^D\\sqrt K\\,d\\sqrt T\\log T)$. Exact solves set $\\alpha=1$, exact current curvature sets $K=1$, and exact score maximization sets $\\xi_t=0$, recovering the standard LinUCB determinant-potential rate up to displayed constants.',
    '[$-$1.10, 0.81]',
    '[$-$1.17, 0.72]',
    '[$-$24.03, $-$21.04]',
    '[$-$36.56, $-$32.26]',
    '[15.43, 18.00]',
    '[1] \\STATE Observe the context and measurably enumerated finite action list $\\cA_t$; this defines $\\cHist_t^-$. \\STATE Take the prefix-determined $\\btheta_t$, $\\bVbar_t$, and $\\bV_t$; using the observed context, form $\\bq_t(a)$, $m_t^{\\rm corr}(a)$, and $b_t(a)$. \\STATE Choose $\\cHist_t^-$-measurable failure budgets before their corresponding draws; reveal the pre-reward randomness $\\Omega_t$. \\STATE Construct $\\Calg_t$ and obtain pre-reward certificates $\\bar D_t$, $\\kappa_{-,t}$, and $\\kappa_{+,t}$. \\STATE Obtain one jointly measurable solver upper-width map $\\hat s_t(a)$ over the score domain. \\STATE Return a $\\cHist_t$-measurable $\\xi_t$-approximate selector for the score in \\eqref{eq:transported-score-new}. \\STATE Observe the reward; update the frozen ridge estimator and \\eqref{eq:reference-update-new}.',
    '[Corrected-center confidence without optimizer assumptions] \\label{cor:corrected-center-new} With probability at least $1-\\delta$, simultaneously over rounds and actions,',
    '[Estimator- and solver-agnostic confidence transport] \\label{thm:transported-ucb} Under the protocol above with $\\lambda>0$ and $\\sigma>0$, suppose \\Cref{asm:abstract-transport} holds, the score obeys \\eqref{eq:transported-score-new}--\\eqref{eq:approx-score-oracle-new}, and $\\|\\bq_t(a)\\|_2\\le G$. On the joint confidence and certificate event, the instantaneous regret satisfies',
    '[Global near-linearity under exponential transport] \\label{cor:global-near-linear-new} Assume exact realizability, $\\mu^*(z)=\\mu_{\\btheta^\\circ}(z)$, and suppose $\\|\\btheta^\\circ\\|_2\\le R$ and $\\|\\btheta_t\\|_2\\le R$ for every $t$. On the certified convex radius-$R$ region, assume the prediction gradient is $L_\\mu$-Lipschitz for the Taylor envelopes and satisfies the replay-path Hessian bound $L_g$ in \\Cref{cor:hessian-path-new}, with \\[ L_\\mu\\le\\frac{c_\\mu}{\\sqrt W},\\qquad L_g\\le\\frac{c_g}{\\sqrt W}, \\] with $W>0$. Use the corrected center, exact current curvature, exact dense solves, and exact score maximization in finite parameter dimension $d$, and suppose $\\|\\bq_t(a)\\|_2\\le G$. Thus $\\alpha_t=1$, $\\kappa_{-,t}=\\kappa_{+,t}=1$, and $\\xi_t=0$. Define \\[ D_{T,W}:=\\frac{4c_gR\\sqrt{T-1}}{\\sigma\\sqrt{\\lambda W}}. \\] Then, with probability at least $1-\\delta$,',
    '[Hessian path certificate] \\label{cor:hessian-path-new} Suppose the parameter region is convex and $\\|\\nabla_\\theta^2\\mu_\\theta(x_s,a_s)\\|_{\\rm op}\\le L_g$ along every segment in \\eqref{eq:scalar-factor-path-new}. With',
    '[Inverse-quadratic interval from the original residual] \\label{lem:inverse-quadratic-certificate-new} Let $\\Calg=\\Calg^\\top\\succeq\\lambda_{\\Calg}\\bI$ with $\\lambda_{\\Calg}>0$. For an approximate solution $\\tilde\\bu$ to $\\Calg\\bu=\\bq$, recompute the original residual $\\br=\\bq-\\Calg\\tilde\\bu$. In exact arithmetic,',
    '[Lipschitz endpoint certificate] \\label{cor:tanh-lipschitz-endpoint} Under the hypotheses of \\Cref{cor:tanh-relative-weights}, let $M_t=\\max_{s<t}|\\phi(z_s)^\\top(\\btheta_t-\\btheta_s)|$ ($M_1=0$) and $D_t^{\\rm lip}=4\\tanh(B_\\phi R/\\sqrt W)\\,M_t/\\sqrt W$. Then $e^{-D_t^{\\rm lip}}\\bVbar_t\\preceq\\bV_t\\preceq e^{D_t^{\\rm lip}}\\bVbar_t$, so $c_{\\mp,t}=e^{\\mp D_t^{\\rm lip}}$ satisfy \\eqref{eq:relative-endpoint-sandwich} and $d_{\\rm Th}(\\bVbar_t,\\bV_t)\\le D_t^{\\rm lip}\\le4M_t/\\sqrt W$. $D_t^{\\rm lip}$ is a measurable function of $\\btheta_t$ and $(\\btheta_s,z_s)_{s<t}$, hence predictable.',
    '[Logarithmic comparison along an SPD path] \\label{lem:log-spd-path} Let $\\bV:[0,1]\\to\\mathbb{S}_{++}^d$ be entrywise absolutely continuous and let $\\dot\\bV(\\tau)$ denote its almost-everywhere derivative. If',
    '[Measurably enumerated finite domains] \\label{cor:finite-enumeration-new} Suppose there is a positive $\\cHist_t^-$-measurable integer $K_t$ and $\\cHist_t^-$-measurable actions $a_{t,k}:\\Omega\\to\\mathsf A$, $k\\ge1$, such that \\[ \\cA_t=\\{a_{t,1},\\ldots,a_{t,K_t}\\}. \\] If the learner chooses the smallest index attaining the score maximum, then the selected action is $\\cHist_t$-measurable and \\eqref{eq:approx-score-oracle-new} holds with $\\xi_t=0$. The score and mean-reward suprema and the universal actionwise events reduce to measurable finite maxima and intersections. A fixed finite action set is the immediate special case.',
    '[Pointwise CG and PCG solver certificates] \\label{cor:cg-interface-new} Suppose CG or PCG supplies, in exact arithmetic, an original-system energy certificate $\\|\\bu-\\tilde\\bu\\|_{\\Calg}\\le\\varepsilon\\|\\bu\\|_{\\Calg}$ with $\\varepsilon<1$. Then \\[ (1-\\varepsilon)s_{\\Calg}^2 \\le\\bq^\\top\\tilde\\bu \\le(1+\\varepsilon)s_{\\Calg}^2. \\] Thus \\[ \\hat s=\\sqrt{\\frac{\\bq^\\top\\tilde\\bu}{1-\\varepsilon}}, \\qquad \\alpha=\\sqrt{\\frac{1+\\varepsilon}{1-\\varepsilon}} \\] give a pointwise upper-valid width and sharpness factor for this query. A jointly measurable action-indexed family of such solves, together with a simultaneous energy-certificate event for every scored action, supplies the all-domain upper condition in \\eqref{eq:solver-interface-new}; the sharpness conclusion is needed only at the played action. For a general standard-Borel domain, measurability of the family and simultaneous functional validity remain additional premises. A preconditioner may change the recurrence, but certificate checks must use the original operator.',
    '[Proof of \\Cref{cor:finite-d-rate-new}] Let $A_T=\\sigma^{-2}\\sum_{t=1}^T\\bq_t(a_t)\\bq_t(a_t)^\\top$. Its rank is at most $r_T=\\min\\{d,T\\}$ and its trace is at most $TG^2/\\sigma^2$. Concavity of $x\\mapsto\\log(1+x)$ over the nonzero eigenvalues gives \\[ \\gamma_T=\\log\\det(\\bI+A_T/\\lambda) \\le r_T\\log\\!\\left(1+\\frac{TG^2}{r_T\\lambda\\sigma^2}\\right). \\] The radius in \\eqref{eq:beta-corrected-new} is bounded by the bracketed term in \\eqref{eq:finite-d-rate-new-display}. Substitute this bound, the uniform transport factors, and \\eqref{eq:finite-d-gamma-new} into \\eqref{eq:simple-transport-regret-new}. The current bias envelope is exactly $b_t(a_t)=\\epsilon_{\\rm lin,t}(a_t)+\\epsilon_{\\rm mis,t}(a_t)$.',
    '[Proof of \\Cref{cor:finite-enumeration-new}] On the measurable event $\\{K_t=n\\}$, the finite vector $\\{U_t(a_{t,k})\\}_{k=1}^n$ is $\\cHist_t$-measurable by joint measurability on the graph. Its maximum and the smallest maximizing index are measurable. A countable partition over $n\\ge1$ therefore gives a $\\cHist_t$-measurable random index and hence a measurable selected action. The score maximum is attained, so $\\xi_t=0$. The same finite-max argument applies to the mean-reward supremum, and each universal event is a finite intersection on $\\{K_t=n\\}$.',
    "[Proof of \\Cref{cor:global-near-linear-new}] The radius bound gives \\[ Q_t\\le\\sum_{s<t} (\\|\\btheta_t\\|_2+\\|\\btheta_s\\|_2)^2 \\le4R^2(t-1). \\] Hence \\Cref{cor:hessian-path-new} gives $\\bar D_t\\le D_{T,W}$. Taylor's theorem and $\\|\\btheta^\\circ-\\btheta_s\\|_2\\le2R$ give \\[ \\epsilon_{\\rm lin}(s),\\ \\epsilon_{\\rm lin,t}(a) \\le\\frac{2c_\\mu R^2}{\\sqrt W}. \\] Exact realizability removes every misspecification envelope, so \\[ B_T\\le\\frac{4c_\\mu^2R^4T}{W},\\qquad E_T^{\\rm cur}\\le\\frac{2c_\\mu R^2T}{\\sqrt W}. \\] Substitute these inequalities, $S=R$, $\\alpha=1$, $K=1$, and $\\xi_t=0$ into \\Cref{cor:finite-d-rate-new}. The asymptotic statement follows from $\\Gamma_{T,d}=O(d\\log T)$ for fixed problem constants.",
    '[Proof of \\Cref{cor:hessian-path-new}] The $s$th factor-row derivative is \\[ \\sigma^{-1}\\left[ \\nabla_\\theta^2\\mu_{\\btheta_s+\\tau(\\btheta_t-\\btheta_s)}(x_s,a_s) (\\btheta_t-\\btheta_s)\\right]^\\top. \\] Hence $\\|\\dot\\Bmat_t(\\tau)\\|_F^2\\le L_g^2Q_t/\\sigma^2$. Since $\\bV_t(\\tau)\\succeq\\lambda\\bI$, \\[ \\dot\\Bmat_t(\\tau)^\\top\\dot\\Bmat_t(\\tau) \\preceq\\frac{L_g^2Q_t}{\\sigma^2\\lambda}\\bV_t(\\tau). \\] Apply \\Cref{lem:factor-spd-path} with the constant $\\nu_t=L_g\\sqrt{Q_t}/(\\sigma\\sqrt\\lambda)$.',
    '[Proof of \\Cref{cor:local-small-drift-new}] Inverting \\eqref{eq:local-additive-new} gives \\[ \\bar s_t(a)\\le(1+\\chi_t)s_t(a),\\qquad s_t(a)\\le(1-\\chi_t)^{-1}\\bar s_t(a). \\] The first inequality, the upper operator comparison, and solver upper validity make the local score optimistic. At the played action, solver sharpness, the lower operator comparison, and the second inequality bound its width term by \\[ \\alpha_t\\frac{1+\\chi_t}{1-\\chi_t} \\sqrt{\\frac{\\kappa_{+,t}}{\\kappa_{-,t}}}\\,\\bar s_t(a_t). \\] Repeat the proof of \\Cref{thm:transported-ucb} and apply \\eqref{eq:frozen-potential-proof}.',
    '[Proof of \\Cref{cor:relative-endpoint-ucb}] Inverting \\eqref{eq:relative-endpoint-sandwich} gives, for every query, \\[ \\bar s_t(a)\\le\\sqrt{c_{+,t}}s_t(a),\\qquad s_t(a)\\le c_{-,t}^{-1/2}\\bar s_t(a). \\] The first inequality, the outward operator inequality in \\eqref{eq:operator-width-proof}, and solver upper validity imply $\\bar s_t(a)\\le\\sqrt{c_{+,t}\\kappa_{+,t}}\\hat s_t(a)$. Consequently, \\eqref{eq:relative-endpoint-score} is optimistic on the reference confidence event. Its approximate-selector condition and lower reference confidence at the played action give',
    "[Proof of \\Cref{cor:tanh-endpoint-regime}] For $y\\ge0$ let $f(y)=y^2/2-\\log\\cosh y$; $f(0)=0$ and $f'(y)=y-\\tanh y\\ge0$, so $\\log\\cosh y\\le y^2/2$, and evenness extends this to all $y$. Hence $4\\log\\cosh(B_\\phi R/\\sqrt W)\\le2B_\\phi^2R^2/W\\le2B_\\phi^2R^2/(cT)$, and $\\exp$ is increasing.",
    '[Proof of \\Cref{cor:tanh-lipschitz-endpoint}] Put $c=e^{-D_t^{\\rm lip}}\\le1$. Then \\[ \\bV_t-c\\bVbar_t=\\lambda(1-c)\\bI+\\sigma^{-2}\\sum_{s<t} \\big(\\omega_{\\btheta_t}(z_s)^2-c\\,\\omega_{\\btheta_s}(z_s)^2\\big) \\phi(z_s)\\phi(z_s)^\\top. \\] The first term is positive semidefinite. By \\Cref{lem:tanh-weight-lipschitz} with the bounded index ($\\|\\phi\\|_2\\le B_\\phi$, $\\|\\btheta\\|_2\\le R$), $\\omega_{\\btheta_t}(z_s)^2/\\omega_{\\btheta_s}(z_s)^2\\ge e^{-4\\tanh(B_\\phi R/\\sqrt W)|\\phi(z_s)^\\top(\\btheta_t-\\btheta_s)|/\\sqrt W}\\ge c$, so every coefficient is nonnegative and each summand is positive semidefinite. The upper inequality is symmetric with $c^{-1}\\ge1$. The Thompson-distance statement is its definition; the last inequality uses $\\tanh\\le1$.',
    '[Proof of \\Cref{cor:tanh-relative-weights}] Write $\\omega_s=\\omega_{\\btheta_s}(z_s)$ and $\\widetilde\\omega_s=\\omega_{\\btheta_t}(z_s)$. Cauchy--Schwarz and the parameter and feature bounds give $\\ell\\le\\omega_s,\\widetilde\\omega_s\\le1$. Thus \\[ \\ell^2\\omega_s^2\\le\\widetilde\\omega_s^2 \\le\\ell^{-2}\\omega_s^2. \\] Multiplying by the positive semidefinite matrix $\\sigma^{-2}\\phi(z_s)\\phi(z_s)^\\top$ and summing proves the comparison for the data terms. Including the ridge preserves it because \\[ \\bV_t-\\ell^2\\bVbar_t\\succeq(1-\\ell^2)\\lambda\\bI\\succeq0, \\qquad \\ell^{-2}\\bVbar_t-\\bV_t \\succeq(\\ell^{-2}-1)\\lambda\\bI\\succeq0. \\] Since $-2\\log\\ell=4\\log\\cosh(B_\\phi R/\\sqrt W)$, this also proves the uniform Thompson distance bound.',
    '[Proof of \\Cref{lem:factor-spd-path}] Almost everywhere, $\\dot\\bV=\\dot\\Bmat^\\top\\Bmat+\\Bmat^\\top\\dot\\Bmat$. Put $E=\\dot\\Bmat\\bV^{-1/2}$ and $H=\\Bmat\\bV^{-1/2}$. Then \\[ \\bV^{-1/2}\\dot\\bV\\bV^{-1/2}=E^\\top H+H^\\top E. \\] Moreover, \\[ H^\\top H =\\bV^{-1/2}\\Bmat^\\top\\Bmat\\bV^{-1/2} =\\bI-\\lambda\\bV^{-1}\\preceq\\bI, \\] so $\\|H\\|_{\\rm op}\\le1$. Therefore the normalized SPD speed is at most $2\\|E\\|_{\\rm op}$, which proves \\eqref{eq:factor-path-bound-new} after integration. For the PSD form, congruence by $\\bV^{-1/2}$ gives \\[ \\|\\dot\\Bmat\\bV^{-1/2}\\|_{\\rm op}^2 =\\|\\bV^{-1/2}\\dot\\Bmat^\\top\\dot\\Bmat\\bV^{-1/2}\\|_{\\rm op} \\le\\nu_t(\\tau)^2. \\] Because $\\nu_t(\\tau)\\ge0$, taking square roots gives $\\|\\dot\\Bmat\\bV^{-1/2}\\|_{\\rm op}\\le\\nu_t(\\tau)$ almost everywhere. The assumed $L^1$ integrability permits integration in \\eqref{eq:factor-path-bound-new}.',
    '[Proof of \\Cref{lem:log-spd-path}] Fix $v\\ne0$ and set $f_v(\\tau)=v^\\top\\bV(\\tau)v$. The path is continuous and positive definite on a compact interval, so $f_v$ is absolutely continuous and bounded away from zero. Thus $\\log f_v$ is absolutely continuous and, almost everywhere, \\[ \\frac{d}{d\\tau}\\log f_v(\\tau) =\\frac{v^\\top\\dot\\bV(\\tau)v}{v^\\top\\bV(\\tau)v}. \\] With $w=\\bV(\\tau)^{1/2}v$, the absolute value of this derivative is at most $\\|\\bV(\\tau)^{-1/2}\\dot\\bV(\\tau) \\bV(\\tau)^{-1/2}\\|_{\\rm op}$. Integrating gives \\[ e^{-\\mathcal D(\\bV)}v^\\top\\bV(0)v \\le v^\\top\\bV(1)v \\le e^{\\mathcal D(\\bV)}v^\\top\\bV(0)v. \\] The inequality holds for every $v$, which is exactly \\eqref{eq:log-path-sandwich-new}. Inverting the sandwich gives the corresponding inverse-quadratic-form comparison. The proof never differentiates a matrix square root.',
    "[Proof of \\Cref{lem:tanh-weight-lipschitz}] Let $u_i=\\phi(z)^\\top\\theta_i/\\sqrt W$ and $h(u)=\\log\\operatorname{sech}^2u=-2\\log\\cosh u$. Then $h'(u)=-2\\tanh u$, so $|h'|\\le2$ on $\\R$ and $|h'|\\le2\\tanh x$ on $[-x,x]$ because $\\tanh$ is odd and increasing. By the mean value theorem, $|h(u_1)-h(u_2)|\\le\\sup|h'|\\,|u_1-u_2|$ over the segment between $u_1$ and $u_2$, which lies in $[-x,x]$ when both endpoints do. Exponentiating $h(u_1)-h(u_2)\\le|h(u_1)-h(u_2)|$ gives both claims.",
    '[Proof of \\Cref{prop:reference-width-floor}] The outward inequalities in \\eqref{eq:path-width-proof} and \\eqref{eq:operator-width-proof}, followed by the all-action solver upper certificate, give \\[ \\bar s_t(a)\\le e^{\\bar D_t/2}s_t(a) \\le e^{\\bar D_t/2}\\sqrt{\\kappa_{+,t}}s_{\\Calg,t}(a) \\le w_t^{\\rm tr}(a). \\] For a nonzero query, positive definiteness makes both $\\bar s_t(a)$ and $s_t(a)$ strictly positive, so their ratio is well defined and gives the stated equality. For a zero query, both exact widths vanish, and the assigned multiplier $1$ avoids division by zero. This equality concerns exact widths; the solver interface may allow a positive upper estimate at an unplayed zero query.',
    '[Proof of \\Cref{prop:width-transport-new}] The logarithmic sandwich and inversion give \\[ \\bar s_t^2(a)\\le e^{\\bar D_t}s_t^2(a),\\qquad s_t^2(a)\\le e^{\\bar D_t}\\bar s_t^2(a). \\] Inverting the operator sandwich gives \\[ s_t^2(a)\\le\\kappa_{+,t}s_{\\Calg,t}^2(a),\\qquad s_{\\Calg,t}^2(a)\\le\\kappa_{-,t}^{-1}s_t^2(a). \\] Composition proves \\eqref{eq:two-way-width-new}. For \\eqref{eq:relative-operator-certificate-new}, congruence gives $-\\varepsilon_t\\bI\\preceq \\bV_t^{-1/2}(\\Calg_t-\\bV_t)\\bV_t^{-1/2} \\preceq\\varepsilon_t\\bI$; undoing the congruence gives the claimed factors.',
    '[Rectangular factor-path certificate] \\label{lem:factor-spd-path} Let $\\Bmat:[0,1]\\to\\R^{m\\times d}$ be absolutely continuous and set $\\bV(\\tau)=\\lambda\\bI+\\Bmat(\\tau)^\\top\\Bmat(\\tau)$, with $\\lambda>0$. Then',
    '[Relative weights for scaled tanh] \\label{cor:tanh-relative-weights} For the scaled-tanh model above, suppose $W>0$, $\\|\\phi(z_s)\\|_2\\le B_\\phi$, and $\\|\\btheta_s\\|_2,\\|\\btheta_t\\|_2\\le R$ for all $s<t$. Set $\\omega_\\theta(z)=\\operatorname{sech}^2(\\phi(z)^\\top\\theta/\\sqrt W)$ and $\\ell=\\operatorname{sech}^2(B_\\phi R/\\sqrt W)>0$. For',
    '[Relative-weight Lipschitz bound] \\label{lem:tanh-weight-lipschitz} For every $z$, $W>0$ and $\\theta_1,\\theta_2$, \\[ \\frac{\\omega_{\\theta_1}(z)}{\\omega_{\\theta_2}(z)} \\le\\exp\\!\\Big(\\frac{2|\\phi(z)^\\top(\\theta_1-\\theta_2)|}{\\sqrt W}\\Big). \\] If moreover $|\\phi(z)^\\top\\theta_i|\\le B_\\phi R$ for $i=1,2$, the factor $2$ can be replaced by $2\\tanh(B_\\phi R/\\sqrt W)$.',
    '[The reference band alone does not justify a smaller width] \\label{rem:naive-width-band-counterexample} Consider an abstract confidence-band instance with $D>0$, $\\bVbar=\\bI_2$, $\\bV=\\operatorname{diag}(e^D,e^{-D})$, and $\\bq=(1,0)^\\top$. Take $m=b=0$, $\\beta>0$, and $\\mu^*=\\beta$. Then $\\bar s=1$ and $s=e^{-D/2}$, so \\[ |\\mu^*-m|=\\beta\\bar s+b,\\qquad m+\\beta s+b=\\beta e^{-D/2}<\\mu^*. \\] Reference confidence therefore holds while the naive current-width score is not an upper bound. This illustrates the limited-information statement of \\Cref{prop:reference-width-floor}; it does not construct a realizable scaled-tanh learning trajectory or establish that this certificate family was necessary in the reported runs.',
    '[Thompson distance and selected-path length] The integrand in \\eqref{eq:generic-path-length-new} is the classical Thompson Finsler norm on the positive-definite cone \\citep{thompson1963certain,nussbaum1994finsler}. Its endpoint metric is \\[ d_{\\rm Th}(A,B) :=\\inf\\{r\\ge0:e^{-r}A\\preceq B\\preceq e^rA\\}. \\] Equivalently, \\[ d_{\\rm Th}(A,B) =\\left\\|\\log(A^{-1/2}BA^{-1/2})\\right\\|_{\\rm op}. \\] Therefore \\Cref{lem:log-spd-path} gives',
    '[Uniform endpoint factor when $W\\ge cT$] \\label{cor:tanh-endpoint-regime} If $W\\ge cT$ for some $c>0$, then $\\exp(4\\log\\cosh(B_\\phi R/\\sqrt W))=\\cosh^4(B_\\phi R/\\sqrt W) \\le\\exp(2B_\\phi^2R^2/(cT))$.',
    '[x=   ,y=   , every node/.style={font=\\normalsize,inner sep=   }, cert/.style={draw=blue!55!black,line width=     ,->}, object/.style={draw=black!28,fill=black!2,rounded corners=   , minimum width=     ,minimum height=      ,align=center}] \\path[use as bounding box] (0,-6.8) rectangle (16.2,.3); \\node[anchor=west] at (0,0) {\\textbf{Before the reward: conditional certificate comparisons}};',
    '[x=   ,y=   , every node/.style={font=\\normalsize,inner sep=   }, reference/.style={blue!65!black,line width=   }, current/.style={orange!80!black,line width=   ,dashed}, transported/.style={teal!70!black,line width=   }] \\path[use as bounding box] (0,-8.35) rectangle (16.2,.25); \\node[anchor=west] at (0,0) {\\textbf{Abstract illustration}\\quad $\\bVbar=\\bI_2$, $\\bV=\\operatorname{diag}(e^D,e^{-D})$, $\\bq=(1,0)^\\top$, $m=b=0$.}; \\node[anchor=west] at (0,-.55) {Illustrative slice: $D=\\log 4$, $\\beta=1$; choose the allowed mean $\\mu^*=\\beta=1$.};',
    '\\Cref{fig:transport-confidence-geometry} illustrates the slice $D=\\log4$, $\\beta=1$: support in the query direction is the inverse-metric width.',
    '\\] Then \\[ \\bV(\\tau)^{-1/2}\\dot\\bV(\\tau)\\bV(\\tau)^{-1/2} =',
    '\\bVbar_{t+1}',
    '\\bar s_t^2(a)',
    '\\bq_t(a)=0',
    '\\draw[black!28,line width=    ] (0,-4.6) -- (16.2,-4.6); \\node[anchor=west] at (0,-4.95) {Selection and sharpness use the \\textbf{same realized width map} $\\hat s_t(\\cdot)$.}; \\node[anchor=west] at (0,-5.57) {\\textbf{Direct reference comparison}\\quad Same history, center, radius, and bias.}; \\node[anchor=west] at (0,-6.11) {$w_t^{\\rm tr}(a)=e^{\\bar D_t/2}\\sqrt{\\kappa_{+,t}}\\,\\hat s_t(a) \\ge\\bar s_t(a)$;\\quad exact actionwise correction gives $c_t(a)s_t(a)=\\bar s_t(a)$.}; \\node[anchor=west] at (0,-6.65) {These comparisons do not order the regret of policies with different adaptive histories.};',
    '\\draw[black!30,line width=     ] (11.5,-2.1) -- (11.5,-6.35); \\draw[black!55,densely dotted,line width=     ] (14.5,-1.95) -- (14.5,-6.35); \\node[anchor=south] at (14.5,-1.8) {$\\mu^*=1$};',
    '\\draw[black!40,->,line width=     ] (1.05,-4.35) -- (5.2,-4.35) node[right=   ] {$z_1$}; \\draw[black!40,->,line width=     ] (3,-6.7) -- (3,-2); \\node[anchor=west] at (3.6,-2.35) {$z_2$}; \\draw[reference,fill=blue!4] (3,-4.35) circle[radius=      ]; \\draw[current,fill=orange!6,fill opacity=.55] (3,-4.35) ellipse[x radius=      ,y radius=     ]; \\draw[black,->,line width=    ] (3,-4.35) -- (4.6,-4.35); \\node[anchor=north] at (4.6,-4.53) {$\\bq=\\mathbf e_1$}; \\fill[orange!80!black] (3.525,-4.35) circle[radius=   ]; \\fill[blue!65!black] (4.05,-4.35) circle[radius=   ]; \\draw[orange!80!black,line width=     ] (3.525,-4.32) -- (3.525,-3.6) -- (4.4,-3.6); \\node[anchor=west] at (4.47,-3.6) {$s=\\tfrac12$}; \\draw[blue!65!black,line width=     ] (4.05,-4.32) -- (4.05,-3.02) -- (4.4,-3.02); \\node[anchor=west] at (4.47,-3.02) {$\\bar s=1$}; \\draw[reference] (0,-7.15) -- (.65,-7.15); \\node[anchor=west] at (.82,-7.15) {Reference $E(\\bVbar)$}; \\draw[current] (3.55,-7.15) -- (4.2,-7.15); \\node[anchor=west] at (4.37,-7.15) {Current $E(\\bV)$};',
    '\\draw[black!50,line width=     ] (8.15,-6.7) -- (14.85,-6.7); \\foreach \\x/\\lab in {8.5/-1,10/-\\frac12,11.5/0,13/\\frac12,14.5/1}{ \\draw[black!50,line width=     ] (\\x,-6.64) -- (\\x,-6.76); \\node[anchor=north] at (\\x,-6.86) {$\\lab$}; } \\node[anchor=north] at (11.5,-7.4) {Mean / score value}; \\node[anchor=west] at (0,-7.85) {$\\bar s=1$, $s=e^{-D/2}$; transport restores $e^{D/2}s=\\bar s$ in this direction.};',
    '\\emph{Category certificate} \\eqref{eq:tanh-category-relative}. It is never looser than $D_t^{\\rm lip}$: for an observed category, $g_{t,c}/f_{t,c}=\\omega_{\\btheta_t}(c)^2\\big/\\big(n_{t,c}^{-1} \\sum_{s<t:\\phi(z_s)=\\phi_c}\\omega_{\\btheta_s}(c)^2\\big)$ divides by a mean of the $\\omega_{\\btheta_s}(c)^2$, which lies between their minimum and maximum, so $g_{t,c}/f_{t,c}\\in[e^{-D_t^{\\rm lip}},e^{D_t^{\\rm lip}}]$; adding $1$ to the minimum and maximum keeps both factors in that interval. The Lipschitz certificate does not need finite categories; it bounds the certificate by index movement and, through $M_t\\le B_\\phi\\max_{s<t}\\|\\btheta_t-\\btheta_s\\|_2$, by parameter movement.',
    '\\emph{Hessian path certificate} (\\Cref{cor:hessian-path-new}). With $L_g=c_h/\\sqrt W$, $c_h=4B_\\phi^2/(3\\sqrt3)$ and $\\max_{s<t}\\|\\btheta_t-\\btheta_s\\|_2\\le\\sqrt{Q_t}$, $4M_t/\\sqrt W\\le4B_\\phi\\sqrt{Q_t}/\\sqrt W =\\frac{3\\sqrt3\\,\\sigma\\sqrt\\lambda}{2B_\\phi}\\bar D_t$. With $\\sigma=0.25$ and $\\lambda=B_\\phi=1$ the factor is $0.650$.',
    '\\emph{Uniform certificate} $D^{\\rm unif}=4\\log\\cosh x$. $D_t^{\\rm lip}<D^{\\rm unif}$ if and only if $M_t<\\sqrt W\\log\\cosh(x)/\\tanh(x)$; with $B_\\phi=R=1$ the threshold is $0.505$, $0.570$ and $0.687$ at $W=16,1,0.25$. Since $M_t\\le2B_\\phi R$, the worst case of $D_t^{\\rm lip}$ is $8x\\tanh x$, which exceeds $D^{\\rm unif}$ for every $x>0$ because $\\log\\cosh x\\le x\\tanh x<2x\\tanh x$; the first inequality holds because $x\\tanh x-\\log\\cosh x$ vanishes at $0$ and has derivative $x\\operatorname{sech}^2x\\ge0$. So the uniform certificate is tighter for large index movement, and the Lipschitz certificate is tighter when $M_t$ is below the threshold.',
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
    '\\setcounter{table}{0} \\renewcommand{\\thetable}{\\thesection.\\arabic{table}} \\renewcommand{\\theHtable}{\\thesection.\\arabic{table}}',
    '\\setcounter{theorem}{10}',
    '\\setcounter{theorem}{11}',
    '\\setcounter{theorem}{13}',
    '\\setcounter{theorem}{14} \\input{transport_proofs}',
    '\\setcounter{theorem}{16}',
    '\\sqrt{\\Gamma_{T,d}+2\\log(1/\\delta)}+\\sqrt\\lambda R',
    'and require the same finite measurable supremum and approximate-selector condition for this score. Keep every other hypothesis of that theorem. On the joint confidence and certificate event, writing $h_t=1+\\alpha_t\\sqrt{c_{+,t}\\kappa_{+,t}/(c_{-,t}\\kappa_{-,t})}$,',
    'd_{\\rm Th}(\\bV(0),\\bV(1))',
    'gives $\\kappa_{-,t}=1-\\varepsilon_t$ and $\\kappa_{+,t}=1+\\varepsilon_t$. An upper comparison alone does not imply a lower factor.',
    'holds. The bias envelope enters twice and the approximate-oracle error enters once. If the confidence event has probability at least $1-\\delta$ and the joint certificate event has probability at least $1-\\delta_{\\rm cert}$, these bounds hold with probability at least $1-\\delta-\\delta_{\\rm cert}$.',
    'replace $e^{\\bar D_t/2}$ by $1+\\chi_t$ in \\eqref{eq:transported-score-new}.',
    's_t^2(a)',
    's_{\\Calg,t}^2(a)',
    'where $\\Phi_t=[\\bq_1(a_1)/\\sigma,\\ldots, \\bq_{t-1}(a_{t-1})/\\sigma]$. The self-normalized martingale inequality bounds the middle term in $\\bVbar_t^{-1}$ norm by $\\sqrt{\\gamma_{t-1}+2\\log(1/\\delta)}$ simultaneously over $t$. The ridge term is at most $\\sqrt\\lambda S$. Finally, $\\bVbar_t=\\lambda\\bI+\\Phi_t\\Phi_t^\\top$ implies $\\Phi_t^\\top\\bVbar_t^{-1}\\Phi_t\\preceq\\bI$, so \\[ \\left\\|\\frac1\\sigma\\Phi_t e\\right\\|_{\\bVbar_t^{-1}} \\le\\frac{\\|e\\|_2}{\\sigma} \\le\\frac1\\sigma\\sqrt{\\sum_{s<t} [\\epsilon_{\\rm lin}(s)+\\epsilon_{\\rm mis}(s)]^2}. \\] Cauchy--Schwarz in the $\\bVbar_t$ metric bounds $|\\bq_t(a)^\\top(\\btheta^\\circ-\\hat\\btheta_t^{\\rm lin})|$ by $\\beta_t^{\\rm corr}\\bar s_t(a)$.',
    'with $c_{-,1}=c_{+,1}=1$ for an empty history. It satisfies \\eqref{eq:relative-endpoint-sandwich} and $\\ell^2\\le c_{-,t}\\le1\\le c_{+,t}\\le\\ell^{-2}$. Either certificate can be used in \\Cref{cor:relative-endpoint-ucb}.',
    '{An endpoint certificate need not bound the synthetic path.} Consider one sample with scalar feature $\\phi=1$, collection parameter $-R$, and current parameter $R$, where $R>0$. Write $\\ell=\\operatorname{sech}^2(R/\\sqrt W)$ with $W>0$. The endpoint metrics are equal to $\\lambda+\\sigma^{-2}\\ell^2$, so their Thompson distance is zero and the category factors are $m=M=1$. Along the synthetic interpolation \\eqref{eq:scalar-factor-path-new}, however, the scalar metric is \\[ V(\\tau)=\\lambda+\\sigma^{-2} \\operatorname{sech}^4((2\\tau-1)R/\\sqrt W). \\] It increases up to $\\tau=1/2$ and then decreases, giving path length \\[ \\int_0^1\\frac{|\\dot V(\\tau)|}{V(\\tau)}\\,d\\tau =2\\log\\!\\left(\\frac{\\lambda+\\sigma^{-2}} {\\lambda+\\sigma^{-2}\\ell^2}\\right)>0. \\] Thus \\Cref{cor:tanh-relative-weights} controls endpoint comparison, not the length used by the original synthetic-path certificate.',
    "{Analysis.} The unit of analysis is the evaluation seed, and every comparison is paired by seed. The design checks are: one-sided paired $t$-tests of policy minus context-free benchmark, with Holm's procedure over the six policies at familywise level $0.05$; two one-sided tests with $\\Delta=3.0$ for endpoint minus frozen, naive minus frozen and endpoint minus naive, using the two-sided 90\\% paired-$t$ interval and holding only if all three pairs pass; and the frozen bound below the cap on every frozen run. The primary family is UCB-GLM minus frozen and Hessian minus frozen, each a two-sided paired $t$-test, with Holm's procedure over the two at familywise level $0.05$. Every reported interval is a 95\\% percentile bootstrap interval from 10,000 resamples of seed-paired differences with a fixed generator seed; intervals are descriptive, and decisions use the $t$-based procedures.",
    '{Bound nonvacuity.} The cumulative guarantee is vacuous in every original-study cell. The median of the per-trajectory terminal sharp-RHS/regret ratios is $126.7$--$155.7$ over the full grid and $126.7$--$135.0$ at $T=1000$. No run has zero regret. Since $|\\mu^*(z)|\\le\\|\\phi(z)\\|\\|\\btheta^\\circ\\|\\le1$, cumulative pseudo-regret has the deterministic cap $2T$. In every cell the theorem bound also exceeds this cap: the median right-hand sides are $3{,}989$--$12{,}607$, versus caps of $500$--$2{,}000$.',
    "{Bounds relative to the reward cap.} The reward range gives the deterministic cap $2T\\min(1,\\sqrt W)$, equal to 2000, 2000 and 1000. A bound above it is \\emph{vacuous}. Every Hessian bound and all 150 frozen-policy own-history bounds exceed their caps. The base-ten logarithms of Hessian's mean terminal RHS/cap are approximately 9.51, 37.19 and 80.91; the frozen policy's mean ratios are approximately 19, 60 and 231 (\\Cref{fig:transport-followup-bound-scale}). Path inflation is Hessian's largest bound contribution in all three conditions.",
    "{Certificate tightness.} At $T=1000$, the median of each trajectory's maximum realized $\\bar D_t^Q$ ranges from $0.0486$ to $0.384$ across target cells. The corresponding median of trajectory-maximum endpoint distances ranges from $1.31\\times10^{-7}$ to $8.74\\times10^{-6}$; both summaries have 50 trajectory-level observations per cell. At the 100 declared checkpoints per trajectory, pooling the 5,000 eligible seed--checkpoint ratios gives a median selected factor-path length only $1.20$--$1.22$ times the endpoint distance, while $\\bar D_t^Q$ is $2.51\\times10^5$--$1.88\\times10^6$ times the selected-path diagnostic. The large ratio accompanies extremely small realized metric motion. Measured directly against the endpoint distance rather than against the selected path, the median $\\bar D_t^Q/d_{\\rm Th}$ ratio is $3.07\\times10^5$--$2.24\\times10^6$ at $T=1000$, so the analytic certificate is conservative by five to six orders of magnitude on this grid. The reported median $e^{\\bar D_t^Q/2}$, by contrast, pools all 50,000 seed--round values in a $T=1000$ cell and ranges from $1.02$ to $1.18$ across the four target cells at that horizon; it is not a terminal or run-maximum summary.",
    '{Confidence and drift checks.} All 600 trajectories, including naive current, pass simultaneous reference confidence, method optimism and deterministic diagnostics: each policy--condition cell has 50/50 successes, with an exact 95\\% Clopper--Pearson interval of approximately $[92.9\\%,100\\%]$. Hessian reaches endpoint distance above one in 16/50 seeds at $W=0.25$; distances are at least one in 286/50,000 seed--round observations (\\Cref{fig:transport-followup-drift-bounds}).',
    "{Contributions.} First, for squared loss, a frozen ridge correction supplies a confidence band around the corrected center along any predictable parameter path in a certified region, using supplied Taylor and misspecification bounds and requiring no optimizer convergence (\\Cref{cor:corrected-center-new}). Second, on a fixed history with the same center, radius and bias, certified transported widths cannot improve on the reference width; an exact actionwise correction recovers it (\\Cref{prop:reference-width-floor}). The symmetric exponential width factors are sharp (Section~\\ref{sec:logarithmic-transport}). Third, scaled tanh admits a relative-weight endpoint certificate because its gradient directions stay fixed (\\Cref{cor:tanh-relative-weights}). A log-Lipschitz bound on the link derivative gives a further certificate controlled by index movement, and when $W\\ge cT$ the uniform endpoint factor is $1+O(1/(cT))$, so the endpoint-transported bound has the frozen bound's form (\\Cref{cor:tanh-lipschitz-endpoint,cor:tanh-endpoint-regime}). \\Cref{thm:transported-ucb} connects these results: reference confidence, metric transport, operator comparison and numerical-width certificates give an implemented UCB score and a regret bound.",
    "{Descriptive cells.} \\Cref{tab:transport-v3-descriptive} gives mean regret in the three curved cells; no test was run there, and the intervals below are descriptive. As $W$ decreases, the certified policies' regret grows (frozen: 440.9, 1,004.4 and 1,902.1), while the envelope-free policies and linear UCB stay between 43.1 and 44.1. Dropping the historical Taylor part of $\\beta_t$ and the bias thus brings frozen and naive to linear UCB's level; the two contributions were not separated. Among the frozen, endpoint and naive widths the choice matters less: at $W=100$ and $10$ both paired intervals against frozen include zero, while at $W=1$ endpoint minus frozen is $-15.3$ ($[-20.5,-10.2]$) and naive minus frozen is $-23.1$ ($[-28.3,-18.0]$), so the design cell's equivalence does not carry over to $W=1$. The Hessian width's cost relative to frozen grows to 2,396.8, 3,784.6 and 6,733.3. UCB-GLM has mean regret 33.4, 42.8 and 340.0. At $W=1$, where $\\kappa=0.0707$ makes its radius $\\alpha=19.19$ (against $1.36$ at $W=T$), it has about 7.7 times the regret of linear UCB (44.1); whether the radius causes this was not tested.",
    '{Design checks and primary comparisons.} \\Cref{tab:transport-v3-design} gives the design cell. All six policies have lower mean regret than the context-free benchmark (one-sided paired $t$-tests, Holm over six, every $p\\le1.2\\times10^{-108}$). Frozen reference, endpoint and naive current are equivalent within the prespecified margin $\\Delta=3.0$ regret units: for each of the three pairs the two-sided 90\\% paired-$t$ interval lies inside $(-1.0,1.0)$ (two one-sided tests, intersection--union). All 50 frozen bounds are below the cap; the largest is 0.761 of it. Both primary comparisons, two-sided paired $t$-tests with Holm over the two, reject: UCB-GLM minus frozen is $-34.4$ ($p=5.7\\times10^{-34}$) and Hessian minus frozen is $16.8$ ($p=5.3\\times10^{-30}$). These checks and comparisons concern one near-linear cell, in which equivalence of the first three policies is expected by construction.',
    "{Design.} Contexts are drawn uniformly from the four vectors $(\\pm1,\\pm1)/\\sqrt2$, there are $K=3$ actions, and $\\phi(x,a)=x\\otimes e_a\\in\\R^6$, so $\\|\\phi\\|_2=B_\\phi=1$ and there are 12 feature categories. The teacher has unit norm; rewards are Gaussian with scaled-tanh mean and $\\sigma=0.25$; $\\lambda=1$, $\\delta=0.05$, $R=1$ and $T=20{,}000$. The design cell sets $W=T$. There the a priori frozen bound, from \\eqref{eq:finite-d-gamma-new} and the envelopes of the first study, is 37,195, which is 0.93 of the cap $2T\\min(1,\\sqrt W)=40{,}000$; but curvature is negligible, since \\Cref{cor:tanh-relative-weights} gives $d_{\\rm Th}(\\bVbar_t,\\bV_t)\\le4\\log\\cosh(1/\\sqrt W)\\approx1.0\\times10^{-4}$. Three descriptive cells, $W=100,10,1$, have stronger curvature and vacuous certified bounds; they were chosen after development output was read and carry no test. Each cell has 50 paired evaluation seeds, and all policies in a cell share a seed's context and potential-outcome streams. One optimizer, selected in the design cell by prediction MSE on uniform-random histories, is used in every cell (Appendix~\\ref{app:transport-v3}).",
    "{Environment and data splits.} The full study fixes teacher seed 1729, development seeds 30000--30001, tuning seeds 30100--30109, and evaluation seeds 30200--30249. Contexts are normalized Rademacher vectors. The feature map concatenates the context, action indicator, and their tensor product, then normalizes it to unit norm; its dimension is $4+5+20=29$. The teacher has unit norm and a fixed regular-simplex construction in the interaction block. The learner starts at zero, uses training ridge one, and receives only the selected action's reward. Rewards are Gaussian with scaled-tanh mean, $\\|\\phi(z)\\|_2\\le1$, projected $\\|\\btheta\\|_2\\le1$, noise standard deviation $0.25$, metric ridge one and $\\delta=0.05$. Dense float64 Cholesky solves implement exact-current operators; action ties use the smallest index. The potential-noise table couples methods without revealing unselected rewards. The 24 development trajectories cover three conditions and four policies at both development seeds.",
    "{Exploratory endpoint audit.} The relative-weight certificate of \\Cref{cor:tanh-relative-weights} compares collection-time and current squared gradient multipliers within fixed feature categories. After outcomes were observed, replay with the recorded actions and rewards audits all 600 histories. On Hessian's histories, the category-specific outward factor has mean effective-width overheads $0.28\\%$--$12.68\\%$ relative to the reference width, versus $0.16\\%$--$12.13\\%$ for dense endpoint across conditions (Appendix~\\ref{app:transport-followup}).",
    '{Exploratory per-seed variation in Hessian-score recommendations on all four behavior histories. Every row evaluates the Hessian score; row labels identify the history-generating policy. Dots mark the median percentage of rounds; whiskers show the minimum--maximum range across 50 seeds. Width argmax uses the exact smallest-index tie rule; the strict condition is the bonus-gap inequality above.} \\label{fig:transport-followup-mechanism-variation}',
    "{Exploratory relative certificates on Hessian's recorded histories. The upper panel averages effective-width/reference-width ratios over all five candidate actions and 1000 rounds, then over 50 seeds per condition; the direct reference ratio is identically one. The lower panel averages one-step pseudo-regret of recommendations on these same states. Uniform uses $D_0$; the category methods use symmetric and separate outward factors. } \\label{fig:transport-followup-relative-audit}",
    "{Finite-action protocol and timing.} At round $t$, observe the context and a nonempty measurably enumerated list $\\cA_t=\\{a_{t,1},\\ldots,a_{t,K_t}\\}$, as in \\Cref{cor:finite-enumeration-new}; this defines the prefix history $\\cHist_t^-$. The representation $\\btheta_t$, reference matrix and exact current matrix are $\\cHist_t^-$-measurable. Reveal fresh pre-reward randomness $\\Omega_t$ and set $\\cHist_t=\\cHist_t^-\\vee\\sigma(\\Omega_t)$. At each enumerated action, $\\mu_t^*(a_{t,k})$, $\\bq_t(a_{t,k})$, centers, allowances, numerical widths and scores are $\\cHist_t$-measurable. Certificates, the applied operator and selector may use this randomness and are $\\cHist_t$-measurable. Choose the smallest index attaining the score maximum, then observe only its reward and update the frozen statistics. ``Predictable'' means $\\cHist_t^-$-measurable; ``pre-reward measurable'' permits $\\Omega_t$. Sections~\\ref{sec:abstract-transport}--\\ref{sec:closed-rates-new} also hold under the general standard-Borel protocol and measurability requirements in \\Cref{app:general-protocol}.",
    '{General protocol and timing.} Let $(\\mathsf A,\\mathcal B)$ be a standard Borel action space. At round $t$, the learner observes a context and a nonempty random action correspondence $\\cA_t:\\Omega\\to 2^{\\mathsf A}$ whose graph \\[ \\operatorname{Gr}(\\cA_t) :=\\{(\\omega,a):a\\in\\cA_t(\\omega)\\} \\in\\cHist_t^-\\otimes\\mathcal B. \\] Here $\\cHist_t^-$ is the history after the context and action correspondence are observed but before fresh round-$t$ algorithmic randomization. The variable $\\Omega_t$ records all round-$t$ pre-reward randomization, which may be revealed in sequential stages, and $\\cHist_t=\\cHist_t^-\\vee\\sigma(\\Omega_t)$ contains that randomization but not the reward. The restrictions to $\\operatorname{Gr}(\\cA_t)$ of $(\\omega,a)\\mapsto\\mu_t^*(a),\\bq_t(a),m_t(a),b_t(a),\\hat s_t(a)$, and, once defined below, $U_t(a)$ are assumed jointly measurable with respect to $\\cHist_t\\otimes\\mathcal B$. We also assume explicitly that $\\sup_{a\\in\\cA_t}\\mu_t^*(a)$ and $\\sup_{a\\in\\cA_t}U_t(a)$ are finite $\\cHist_t$-measurable random variables, that the oracle below returns a $\\cHist_t$-measurable selector in $\\cA_t$, and that the simultaneous confidence and all certificate events below, including path, operator, all-domain solver-upper, and played-action sharpness validity, are measurable. These are substantive assumptions; standard-Borel structure and graph measurability alone do not make every supremum or selector measurable.',
    '{Generalized linear and logistic bandits.} Scaled tanh is a single-index model with a known increasing link, the form studied by generalized linear bandits. \\citet{li2017provably} analyze UCB-GLM and SupCB-GLM under conditionally sub-Gaussian noise, a link with $\\inf\\dot\\mu=\\kappa>0$ near the true parameter, bounded first and second link derivatives, i.i.d.\\ contexts with a nondegenerate design, and an estimator that solves the GLM score equation; their bounds scale as $\\tilde O(d\\sqrt T/\\kappa)$ and $\\tilde O(\\sqrt{dT\\log K}/\\kappa)$. For the logistic link with Bernoulli rewards, \\citet{faury2020improved} remove $\\kappa$ from the leading $\\sqrt T$ term using a Bernstein-like inequality for self-normalized martingales, and \\citet{abeille2021instance} obtain a leading term $d\\sqrt{T/\\kappa_\\star}$ with a matching local lower bound. None of these results applies as stated to our setting: the logistic analyses assume Bernoulli rewards, and \\citet{li2017provably} state rewards in $[0,1]$. Our analysis also differs in its object: it allows an arbitrary predictable parameter fitted with squared loss and corrects the prediction with a frozen linear estimate, rather than analyzing a likelihood estimator. Section~\\ref{sec:transport-v3} runs UCB-GLM as a baseline.',
    '{Local small-drift comparison.} If $\\chi_t<1$ and',
    "{Matrices and numerical checks.} The current matrix is computed from category counts, $\\bV_t=\\lambda\\bI+\\sigma^{-2}\\sum_cn_{t,c}\\operatorname{sech}^4 (\\phi_c^\\top\\btheta_t/\\sqrt W)\\phi_c\\phi_c^\\top$, and $Q_t$ from a running mean and scatter of $\\btheta_1,\\ldots,\\btheta_{t-1}$, which avoids the cancellation of raw running sums at small $W$. At rounds 1, 10, 100, 1,000, 10,000 and 20,000 each corrected-center run rebuilds $\\bV_t$, the frozen matrix and $Q_t$ by dense per-observation replay; the tolerance per check is $4096\\,\\varepsilon_{\\rm mach}\\,d\\max(1,m)$, with $m$ the largest absolute entry of the two compared objects. UCB-GLM solves its score equation by Newton's method with Armijo backtracking on the convex objective $\\sum_c[n_cW\\log\\cosh(\\phi_c^\\top\\theta/\\sqrt W)-S_c\\phi_c^\\top\\theta]$, where $S_c$ is the reward sum of category $c$, warm-started and with at most 50 iterations. A replay excess, a Newton nonconvergence, an unreached random-phase stopping rule or an exception would have been recorded and the run retained; none occurred.",
    '{Mean cumulative pseudo-regret at $T=1000$ and comparator-minus-Hessian paired differences. Intervals are pointwise 95\\% paired seed-bootstrap intervals from 10,000 resamples of 50 seeds per condition.} \\label{tab:transport-followup-outcomes} \\input{figures/transport_followup_outcomes.tex}',
    "{Mean terminal theorem RHS relative to the deterministic cap $2T\\min(1,\\sqrt W)$, on each named policy's own 50 histories. Points plot the base-ten logarithm of the mean RHS/cap; zero is equality with the cap.} \\label{fig:transport-followup-bound-scale}",
    '{Meaning of the cumulative bound decomposition.} For a transport-Hessian trajectory, write $P_T=(\\sigma^2+G^2/\\lambda)\\gamma_T$ and $\\beta_t^{\\rm stat}=\\sqrt{\\gamma_{t-1}+2\\log(1/\\delta)}+\\sqrt\\lambda S$. The reported components are',
    '{Numerical checks before evaluation.} A documented development-only numerical refinement froze Gauss--Legendre quadrature order 2048 before tuning and evaluation. The full development gate compared orders 1024 and 2048 on all 24 declared trajectories; a separate development check also compared 2048 and 4096. No failed development check was reclassified as a passing evaluation.',
    "{Numerical checks.} All 1,500 evaluation runs completed with no crash and no recorded failure. UCB-GLM's Newton solves always converged, and its random phase lasted 12 to 34 rounds. In the 1,100 corrected-center runs, the category-count current matrix, the frozen matrix and the drift sum $Q_t$ of \\Cref{cor:hessian-path-new} were checked against dense replay at six rounds, 19,800 checks in all; the largest discrepancy was 0.039 of its tolerance. No run that records the optimism check failed it; UCB-GLM does not record it.",
    '{Optimizer.} Each corrected-center policy fits $\\btheta_t$ by projected full-batch gradient descent on $\\sum_{s<t}(r_s-\\mu_{\\btheta}(z_s))^2/(2\\sigma^2)+\\|\\btheta\\|_2^2/2$ from $\\btheta_1=0$: a fixed number of steps per round, then one projection onto $\\|\\btheta\\|_2\\le1$. Sixty tuning runs with uniform-random actions in the design cell compared learning rates $\\{3\\times10^{-6},10^{-5},3\\times10^{-5}\\}$ and $\\{5,20\\}$ steps by all-action prediction MSE after a 10\\% burn-in, averaged over the ten tuning seeds. All six candidates were eligible; learning rate $3\\times10^{-6}$ with 5 steps had the smallest mean MSE, $4.062\\times10^{-5}$, and the six means were within 0.2\\% of each other. The same optimizer is used in every cell.',
    '{Original near-linear audit for the transport-Hessian policy. Coverage is run-level simultaneous coverage with exact Clopper--Pearson intervals. The left panel first maximizes each distance within a trajectory, then takes the median over 50 runs per cell; the right panel shows terminal medians. Event violations count theorem-bound failures only when the joint confidence premise holds. All values come from the full evaluation; smoke and tuning runs are excluded.} \\label{fig:transport-instantiation-validity}',
    '{Original near-linear study.} For \\Cref{sec:transport-instantiation}, the retained full aggregate, generated tables and figures, provenance sidecars, and detached verifier support aggregate-derived checks. The original per-run trajectories and per-seed observations remain unavailable. Their inventory digests do not establish access to or integrity of the missing raw bytes. In particular, the original paired bootstrap cannot be recomputed from the aggregate alone; no per-seed values have been synthesized to replace it. The historical dependency records also disagree: requirements specify SciPy 1.15.2 while a retained host-specific wheel link names SciPy 1.13.1. Two selection-time sources, the artifact renderer and recorded build declaration, differ from their recorded digests. The verifier reports these gaps explicitly. Fresh runs and dependency locks do not repair the historical runtime or source provenance.',
    '{Original-study mean cumulative pseudo-regret at $T=1000$. Shaded bands are pointwise paired-bootstrap 95\\% intervals over the 50 evaluation seeds, not simultaneous confidence bands. All four methods are plotted; curves can coincide where their selected actions agree.} \\label{fig:transport-instantiation-regret}',
    '{Original-study path-certificate conservatism on log--log axes. Blue circles bin the per-round Hessian/$Q_t$ certificate $\\bar D_t^Q$ against endpoint Thompson distance. Orange triangles bin the numerical selected factor-path length at preregistered checkpoints. Each target panel pools eligible observations from the three independently executed horizons. Markers are plotted at geometric bin centers, marker size encodes bin count, and the dashed line is equality. Values at or below the preregistered $10^{-12}$ ratio tolerance, including round-one zeros, are omitted from the log axes and counted in \\Cref{fig:transport-original-path-ratios}. Quadrature and generalized-eigenvalue calculations are dense float64 diagnostics, not verified certificates.} \\label{fig:transport-instantiation-tightness}',
    '{Original-study per-round mean cumulative decomposition over 50 transport-Hessian trajectories at $T=1000$. On this near-linear grid, the base confidence component, which includes the regularization/norm-bound term, dominates; historical linearization, path inflation, and current bias are shown separately. The red sharp right-hand side remains far above realized regret in every target condition.} \\label{fig:transport-instantiation-bound}',
    '{Original-study policy outcomes at the primary horizon $T=1000$. Mean-regret and paired-difference intervals are comparisonwise deterministic paired-bootstrap 95\\% intervals over the same 50 evaluation seeds. Each difference is the row method minus transport Hessian, so negative values favor the row method. Transport endpoint is a dense diagnostic comparator; naive current is an uncertified negative control.} \\label{fig:transport-instantiation-performance}',
    "{Original-study terminal width and bound ratios, summarized by medians over 50 runs per cell. ``Width/potential'' is the frozen squared-width sum divided by its elliptic-potential upper bound; ``Sharp/simple'' is the sharp cumulative right-hand side divided by the simpler right-hand side.} \\label{fig:transport-original-bound-ratios}",
    '{Original-study transport multipliers and error summaries. Multipliers pool all seed--round values; terminal historical radii and cumulative current biases summarize 50 runs per cell. These different populations must not be combined into an additive median decomposition.} \\label{fig:transport-original-components}',
    '{Policies.} The four corrected-center policies are those of the first study. UCB-GLM is Algorithm~1 of \\citet{li2017provably} with link $\\mu(u)=\\sqrt W\\tanh(u/\\sqrt W)$. It plays uniformly random actions until the smallest eigenvalue of $\\sum_iX_iX_i^\\top$ reaches one, then plays the maximizer of $X^\\top\\hat\\theta_t+\\alpha\\|X\\|_{V_t^{-1}}$, where $\\hat\\theta_t$ solves the GLM score equation $\\sum_{i<t}(Y_i-\\mu(X_i^\\top\\theta))X_i=0$, $V_t=\\sum_{i<t}X_iX_i^\\top$, $\\alpha=(\\sigma/\\kappa)\\sqrt{(d/2)\\log(1+2T/d) +\\log(1/\\delta)}$ and $\\kappa=\\operatorname{sech}^2((R+1)/\\sqrt W)$. The rule that ends the random phase is ours: their theorem fixes its length only up to a universal constant. Their analysis states rewards in $[0,1]$, so its regret bound does not apply to these Gaussian rewards. Linear UCB fits ridge regression to raw rewards with metric $\\lambda\\bI+\\sigma^{-2}\\sum_{s<t}\\phi_s \\phi_s^\\top$ and radius $\\sqrt{\\gamma_{t-1}+2\\log(1/\\delta)}+\\sqrt\\lambda R$; under scaled-tanh means it is uncertified. The descriptive cells add envelope-free frozen and naive policies, which drop the historical Taylor part of $\\beta_t$ and the bias ($b_t=0$). They are uncertified ablations that show which terms make the certified bounds vacuous.',
    '{Policy outcomes at $T=1000$. Left: mean cumulative pseudo-regret. Right: comparator-minus-Hessian differences with pointwise 95\\% paired seed-bootstrap intervals. Negative differences favor the comparator.} \\label{fig:transport-followup-outcomes}',
    "{Policy outcomes.} At $T=1000$, mean regret for the operational Hessian-certificate policy rises from $81.0$ to $94.0$ across the four target conditions (\\Cref{fig:transport-instantiation-performance}). All three comparison policies have lower sample-mean pseudo-regret than transport Hessian in every reported condition at this horizon. These are matched-stream total-policy comparisons: the policies share contexts and potential outcomes, but their actions, fitted parameters, centers, radii, and widths may diverge after the first disagreement. The endpoint comparison is consistent with conservatism in the analytic envelope, but it does not isolate a fixed-history mechanism and does not provide a scalable policy certificate; it is a dense diagnostic comparator rather than a deployable policy. The naive score's observed optimism does not make it theoretically valid. Since $D_{\\rm target}$ also changes $W$, the cross-condition pattern is not a causal dose response. Read in the intended direction, these outcomes do not show a causal or uniform advantage for full curvature, and the reverse ordering they record is specific to this environment, this certificate, and this horizon.",
    "{Prespecified drift diagnostics. The maximum and threshold frequencies use Hessian's 50,000 seed--round observations per condition; thresholds use $\\ge$. Bound scales appear in \\Cref{fig:transport-followup-bound-scale}.} \\label{fig:transport-followup-drift-bounds}",
    '{Protocol and policies.} The prespecified study fixes $T=1000$, $W\\in\\{16,1,0.25\\}$ and 50 paired seeds per policy--condition cell (600 trajectories). A fixed teacher generates Gaussian scaled-tanh rewards. The shared projected optimizer was selected by prediction MSE before evaluation; the implementation uses dense float64 Cholesky solves. Appendix~\\ref{app:transport-followup} gives the full model, protocol, splits and checks.',
    '{Protocol.} We use the finite-dimensional scaled-tanh Gaussian specialization of \\Cref{cor:global-near-linear-new}. Contexts have dimension $4$, there are five actions, and the normalized context--action feature map has dimension $29$. The frozen and current matrices are formed densely, all widths use float64 Cholesky solves, and finite enumeration uses the smallest-index tie rule. Thus the intended theorem interface has \\[ \\alpha_t=1,\\qquad \\kappa_{-,t}=\\kappa_{+,t}=1,\\qquad \\xi_t=0. \\] These equalities describe the exact operator, solve, and selection abstractions. The recorded floating-point checks are diagnostics, not verified numerical certificates.',
    '{Reference and current metric unit balls in the abstract instance following \\Cref{prop:reference-width-floor}. With $D=\\log4$, $m=b=0$ and $\\beta=1$, the permitted mean $\\mu^*=1$ exceeds the naive score $1/2$; the multiplier $e^{D/2}$ recovers the reference width.} \\label{fig:transport-confidence-geometry}',
    "{Regret outcomes.} \\Cref{fig:transport-followup-outcomes} plots the policy outcomes; \\Cref{tab:transport-followup-outcomes} gives the numerical values. Each paired difference is a comparator's cumulative pseudo-regret minus Hessian's on the same evaluation seed. All nine 95\\% intervals exclude zero in the comparator's favor; they use 10,000 paired seed-bootstrap resamples. For descriptive context, the best-fixed-action-in-hindsight means are 180.01, 177.97 and 171.84 at $W=16,1,0.25$, using the same streams as the context-free benchmark defined in the appendix.",
    '{Replay and numerical checks.} The post-outcome audit replays the original representation optimizer with fixed logged actions and rewards for all 600 trajectories; it never replaces a behavior action or generates a new observation. It reconstructs collection-time category weights and compares the resulting sandwich, effective widths, and recommendations at the stored states. Matrix, center, and endpoint reconstruction are checked at rounds 1, 2, 10, 100, 500, and 1000; the original float64 tolerances are retained. All declared checks passed; the largest residual divided by its original tolerance was below $0.005$. The per-seed variation in the preceding figure was reproduced by this separate fixed-action replay.',
    '{Second study, descriptive cells: mean cumulative pseudo-regret at $T=20{,}000$ over 50 seeds, the Hessian-minus-frozen mean paired difference, and the largest frozen bound relative to the cap $40{,}000$. Envelope-free policies and linear UCB are uncertified.} \\label{tab:transport-v3-descriptive}',
    '{Second study, design cell ($W=T=20{,}000$): mean cumulative pseudo-regret at $T$, its standard deviation over 50 seeds, and the policy-minus-frozen paired difference with a pointwise 95\\% paired seed-bootstrap interval from 10,000 resamples.} \\label{tab:transport-v3-design}',
    "{Seeds and phases.} Development seeds 41000--41009, tuning seeds 41100--41109 and evaluation seeds 41200--41249 are disjoint from the first study's. Development runs fixed the design-cell scale, the margin and the numerical checks; development and tuning runs are not evaluation replicates. The design cell uses $c=1$ in $W=cT$, the smallest $c$ in $\\{1,10,100\\}$ for which every development frozen bound was at most 0.9 of the cap; no record of this rule predates the first development output. The margin $\\Delta=3.0$ is a quarter of the development mean Hessian-minus-frozen difference, 12.0, and was fixed before evaluation. Evaluation runs were not repeated.",
    "{Selecting a shared optimizer.} We select the optimizer by prediction accuracy, using histories generated independently of the study policies' evaluation decisions. The 270 tuning trajectories cover nine optimizer candidates, three conditions, and ten tuning seeds, using uniform-random actions. The nine candidates combine learning rates $\\{3\\times10^{-5},10^{-4},3\\times10^{-4}\\}$ with $\\{1,5,20\\}$ full-batch steps. All were eligible. Candidate 008, learning rate $3\\times10^{-4}$ and 20 steps, minimized equally weighted all-action prediction MSE over the 30 tuning seed--condition cells, with selected MSE $0.00392155$. Evaluation consists of $3\\times4\\times50=600$ further trajectories. The 294 development and tuning trajectories are not evaluation replicates.",
    "{Sensitivity to score rounding.} We distinguish recomputing the final score from recomputing the quantities that enter it. This matters when two actions have nearly equal scores. The numerical scan reconstructs the recorded selected scores exactly and finds no nonfinite coefficients or scores and no zero widths. A separate 250-digit decimal calculation evaluates the final score arithmetic from the exact stored binary64 centers, widths, offsets, and \\emph{already rounded} coefficient $B_t$. It changes the primary recommendation at 16 states: five, five, and six in the respective conditions. Across all behavior histories there are 65 changes among 600,000 states. All occur at rounds 2--10, with score differences below 0.629 of a binary64 score ULP (the spacing of representable numbers at the score's magnitude).",
    "{The endpoint-transported bound when $W\\ge cT$.} Under the assumptions of \\Cref{cor:global-near-linear-new} for scaled tanh ($c_\\mu=c_g=c_h$, $G=B_\\phi$, $\\kappa_{\\pm,t}=\\alpha_t=1$, $\\xi_t=0$), score with \\Cref{cor:relative-endpoint-ucb} using the uniform certificate $c_{\\pm,t}=\\ell^{\\mp2}$, $\\ell=\\operatorname{sech}^2(B_\\phi R/\\sqrt W)$. Then $h_t=1+\\ell^{-2}=1+\\cosh^4(B_\\phi R/\\sqrt W)\\le\\bar h:=1+e^{2B_\\phi^2R^2/(cT)}$ by \\Cref{cor:tanh-endpoint-regime}. By \\eqref{eq:relative-endpoint-regret} and \\Cref{prop:frozen-width-ucb}, \\[ R_T^{\\rm endpoint}\\le\\bar h\\sqrt{\\Big(\\sigma^2+\\frac{G^2}{\\lambda}\\Big) \\gamma_T\\sum_t\\beta_t^2}+2\\sum_tb_t(a_t), \\qquad R_T^{\\rm frozen}\\le2\\sqrt{\\Big(\\sigma^2+\\frac{G^2}{\\lambda}\\Big) \\gamma_T\\sum_t\\beta_t^2}+2\\sum_tb_t(a_t), \\] each on its own policy's trajectory. As functions of the same $\\gamma_T$, $\\beta_t$ and $b_t$, the transported exploration term is at most $\\bar h/2=1+O(1/(cT))$ times the frozen one, and the bias terms are identical; the realized $\\gamma_T$, $\\beta_t$ and $b_t$ differ between the two trajectories. Bounding $\\gamma_{t-1}\\le\\Gamma_{T,d}$ \\eqref{eq:finite-d-gamma-new}, $\\epslin(s),b_t\\le2c_hR^2/\\sqrt W$ (Taylor's theorem with $\\|\\btheta^\\circ-\\btheta_s\\|_2\\le2R$) and $\\epsilon_{\\rm mis}=0$ in \\eqref{eq:beta-corrected-new} gives, with probability at least $1-\\delta$, \\[ R_T^{\\rm endpoint}\\le\\bar h\\Big[\\sqrt{\\Gamma_{T,d}+2\\log(1/\\delta)} +\\sqrt\\lambda R+\\frac{2c_hR^2\\sqrt T}{\\sigma\\sqrt W}\\Big] \\sqrt{\\sigma^2+\\frac{G^2}{\\lambda}}\\sqrt{T\\Gamma_{T,d}} +\\frac{4c_hR^2T}{\\sqrt W}, \\] which is \\eqref{eq:global-near-linear-new} with $2e^{D_{T,W}}$ replaced by $\\bar h$. A score with the dense endpoint certificate $c_{\\pm,t}=e^{\\pm d_{\\rm Th}(\\bVbar_t,\\bV_t)}$ has $h_t=1+e^{d_{\\rm Th}}\\le\\bar h$, since $d_{\\rm Th}\\le4\\log\\cosh x$, so the same bound applies to it in exact arithmetic. With $W=cT$, $D_{T,W}=4c_hR\\sqrt{T-1}/(\\sigma\\sqrt{\\lambda cT})$ stays below $4c_hR/(\\sigma\\sqrt{\\lambda c})$, about $12.3/\\sqrt c$ at the first study's constants, while $\\bar h\\to2$. At that study's $T=1000$ and $W=16,1,0.25$, the Hessian factor $2e^{D_{T,W}}$ is approximately $10^{42.6}$, $10^{169.4}$ and $10^{338.4}$ ($D_{T,W}=97.3$, $389.3$ and $778.6$), against the uniform endpoint factor $1+\\cosh^4(1/\\sqrt W)=2.13$, $6.67$ and $201.3$; with $c=W/T$, $\\bar h$ is $2.13$, $8.39$ and $2982$. Nothing here concerns analyses other than this paper's.",
    '{Validity audit.} For the primary policy, every one of the same 50 base seeds in each of the 12 horizon--target cells retained simultaneous reference confidence and transported optimism. The cellwise exact 95\\% Clopper--Pearson interval is $[92.9\\%,100\\%]$. Reusing base seeds across cells supports paired comparisons within a condition, not a pooled sample of 600 independent runs. The strict aggregate accepted all 2400 policy trajectories with no deterministic algebra or certificate-check failure, and the primary policy had no bound violation on the joint confidence event (\\Cref{fig:transport-instantiation-validity}). This finite-sample observation does not prove or empirically validate the theorem. In particular, ordinary float64 Cholesky, eigenvalue, and quadrature checks are not verified enclosures.',
    "{Variation across seeds and history-generating policies.} \\Cref{fig:transport-followup-mechanism-variation} reports per-seed variation instead of treating the pooled rounds as independent. The row label tells us which policy generated the history; the score being diagnosed is always Hessian's. Thus only Hessian rows describe the behavior policy's own score. The other rows evaluate Hessian on states visited by endpoint, frozen reference or naive current. Each fraction has 1000 rounds in its denominator, and the reported median and range summarize 50 seeds.",
    '{What the intervals measure.} Pairing compares policies exposed to the same underlying context and potential-noise stream. The paired-bootstrap intervals resample the 50 evaluation seeds within a condition, preserving the pairing between policies, with 10,000 resamples and the recorded deterministic bootstrap seed.',
    "{What the second study shows.} Where the frozen bound is informative and curvature is negligible, endpoint transport and naive current match frozen scoring within the margin, which is consistent with the bound comparison after \\Cref{cor:tanh-endpoint-regime} (that comparison concerns bound expressions, not realized regret), and the Hessian path certificate costs regret even there. UCB-GLM, whose regret theorem does not cover Gaussian rewards, has the lowest mean regret in the design cell and at $W=100$ and $10$, but not at $W=1$. In the curved cells, removing the envelope terms lowers frozen's mean regret from 440.9--1,902.1 to 43.3--43.9, while the frozen, endpoint and naive widths differ in mean regret by at most 23.1 units. These are results for one synthetic model and one selected optimizer.",
    "{What transport adds in the near-linear regime.} Take the scaled-tanh specialization of \\Cref{cor:global-near-linear-new} with exact current curvature, exact solves and exact maximization, and score with \\Cref{cor:relative-endpoint-ucb} using the uniform certificate. By \\Cref{cor:tanh-endpoint-regime}, the endpoint-transported bound then has the frozen bound's form (\\Cref{prop:frozen-width-ucb}) with the factor $2$ replaced by $1+\\cosh^4(B_\\phi R/\\sqrt W)\\le1+e^{2B_\\phi^2R^2/(cT)}$, whereas the Hessian path certificate leaves the factor $2e^{D_{T,W}}$ with $D_{T,W}=O(1/\\sqrt c)$. When both bounds are written in the same $\\gamma_T$, $\\beta_t$ and $b_t$, the endpoint-transported exploration term is therefore at most a $1+O(1/(cT))$ multiple of the frozen one, and the bias terms are identical; the two bounds hold on different trajectories. In this analysis transport does not improve on frozen scoring. The appendix gives the resulting explicit bound and evaluates both factors at the first study's constants.",
    '{When the width bonus determines the action.} A large bonus can make the widest action win even when its predicted reward is lower. A sufficient check is that its bonus advantage exceeds the largest possible difference between prediction centers on the recorded state. Write the primary score on a recorded state as $m_t(a)+B_t s_t(a)+b_t$, where $b_t$ is action independent and $B_t=\\beta_t^{\\rm corr}\\exp(\\bar D_t^Q/2)$. Let $s_{t,(1)}\\ge s_{t,(2)}$ be the largest two current widths. The strict condition \\[ B_t\\bigl(s_{t,(1)}-s_{t,(2)}\\bigr) >\\max_a m_t(a)-\\min_a m_t(a) \\] is sufficient for the unique largest-width action to maximize the score. Width-argmax agreement alone is weaker: prediction centers might favor the same action. The exact tie rule is the smallest action index.',
    '{Which factors are compared?} For unit feature and parameter bounds, \\Cref{cor:tanh-relative-weights} gives the uniform endpoint bound $D_0=4\\log\\cosh(1/\\sqrt W)$, approximately $0.124$, $1.735$, and $5.300$ at the three conditions. The category-specific sandwich $c_{-,t}\\bVbar_t\\preceq\\bV_t\\preceq c_{+,t}\\bVbar_t$ gives a symmetric coefficient $\\exp(D_{{\\rm cat},t}/2)$, where $D_{{\\rm cat},t}=\\max\\{-\\log c_{-,t},\\log c_{+,t}\\}$, or the separate outward coefficient $\\sqrt{c_{+,t}}$ of \\Cref{cor:relative-endpoint-ucb}. The latter retains the separate return factor $c_{-,t}^{-1/2}$ in the cumulative bound.',
)


def _u(*cited: tuple[int, int]) -> tuple[tuple[str, int], ...]:
    """Resolve `(unit index, offset)` pairs against UNITS."""

    return tuple((UNITS[index], offset) for index, offset in cited)


#: (path, phrase) -> (occurrences, ((unit, offset-in-unit), ...))
PHRASE_PINS: dict[tuple[str, str], tuple[int, tuple[tuple[str, int], ...]]] = {
    # paper/legacy_scope.tex
    ('paper/legacy_scope.tex', '29-parameter'):
        (1, _u((110, 350))),
    # paper/transport_experiment.tex
    ('paper/transport_experiment.tex', '$1.20$--$1.22$ times the endpoint distance'):
        (1, _u((249, 485))),
    ('paper/transport_experiment.tex', '$1.88\\times10^6$'):
        (1, _u((249, 569))),
    ('paper/transport_experiment.tex', '$126.7$--$135.0$ at $T=1000$'):
        (1, _u((247, 195))),
    ('paper/transport_experiment.tex', '$2.0\\%$--$16.3\\%$'):
        (1, _u((112, 325))),
    ('paper/transport_experiment.tex', '$2.24\\times10^6$'):
        (1, _u((249, 839))),
    ('paper/transport_experiment.tex', '$2.51\\times10^5$'):
        (1, _u((249, 551))),
    ('paper/transport_experiment.tex', '$3{,}989$--$12{,}607$'):
        (1, _u((247, 448))),
    ('paper/transport_experiment.tex', '$79.4\\%$--$97.3\\%$'):
        (1, _u((112, 214))),
    ('paper/transport_experiment.tex', '$8.74\\times10^{-6}$'):
        (1, _u((249, 254))),
    ('paper/transport_experiment.tex', '$9{,}948$--$10{,}010$'):
        (1, _u((112, 601))),
    ('paper/transport_experiment.tex', '$T=1000$'):
        (8, _u((115, 1373), (249, 28), (249, 859), (249, 1056), (247, 215), (112, 172), (280, 22), (275, 55))),
    ('paper/transport_experiment.tex', '$[92.9\\%,100\\%]$'):
        (1, _u((293, 240))),
    ('paper/transport_experiment.tex', '$\\log 5\\approx1.609$'):
        (1, _u((115, 1690))),
    ('paper/transport_experiment.tex', '$e^{\\bar D_t^Q/2}$'):
        (1, _u((249, 982))),
    ('paper/transport_experiment.tex', '100 declared checkpoints per trajectory'):
        (1, _u((249, 345))),
    ('paper/transport_experiment.tex', '20 full-batch steps'):
        (1, _u((115, 1165))),
    ('paper/transport_experiment.tex', '5,000\neligible seed--checkpoint ratios'):
        (1, _u((249, 398))),
    ('paper/transport_experiment.tex', '50 evaluation seeds'):
        (2, _u((115, 58), (275, 188))),
    ('paper/transport_experiment.tex', '50 runs per cell'):
        (1, _u((270, 238))),
    ('paper/transport_experiment.tex', '50 trajectory-level observations per cell'):
        (1, _u((249, 295))),
    ('paper/transport_experiment.tex', '50 transport-Hessian trajectories'):
        (1, _u((112, 396))),
    ('paper/transport_experiment.tex', '600 independent runs'):
        (1, _u((293, 361))),
    ('paper/transport_experiment.tex', '95\\% intervals'):
        (1, _u((275, 159))),
    ('paper/transport_experiment.tex', 'All five actions are optimal somewhere in every'):
        (1, _u((115, 1562))),
    ('paper/transport_experiment.tex', 'Contexts have dimension $4$'):
        (1, _u((283, 116))),
    ('paper/transport_experiment.tex', 'No run has zero regret'):
        (1, _u((247, 225))),
    ('paper/transport_experiment.tex', 'Ten disjoint tuning seeds'):
        (1, _u((115, 1095))),
    ('paper/transport_experiment.tex', '\\alpha_t=1'):
        (1, _u((283, 428))),
    ('paper/transport_experiment.tex', '\\kappa_{-,t}=\\kappa_{+,t}=1'):
        (1, _u((283, 446))),
    ('paper/transport_experiment.tex', '\\xi_t=0'):
        (1, _u((283, 481))),
    ('paper/transport_experiment.tex', 'all 2400 policy\ntrajectories'):
        (1, _u((293, 413))),
    ('paper/transport_experiment.tex', 'best-fixed-action regret $180.4$'):
        (1, _u((115, 1478))),
    ('paper/transport_experiment.tex', 'cap $2{,}000$'):
        (1, _u((112, 642))),
    ('paper/transport_experiment.tex', 'deterministic cap $2T$'):
        (1, _u((247, 337))),
    ('paper/transport_experiment.tex', 'each of the 12\nhorizon--target cells'):
        (1, _u((293, 81))),
    ('paper/transport_experiment.tex', 'exact 95\\% Clopper--Pearson interval'):
        (1, _u((293, 200))),
    ('paper/transport_experiment.tex', 'feature map has dimension $29$'):
        (1, _u((283, 204))),
    ('paper/transport_experiment.tex', 'horizons $T\\in\\{250,500,1000\\}$'):
        (1, _u((115, 25))),
    ('paper/transport_experiment.tex', 'is $126.7$--$155.7$ over the'):
        (1, _u((247, 152))),
    ('paper/transport_experiment.tex', 'is $3.07\\times10^5$'):
        (1, _u((249, 818))),
    ('paper/transport_experiment.tex', 'learning rate $3\\times10^{-4}$'):
        (1, _u((115, 1130))),
    ('paper/transport_experiment.tex', 'mean-only regret $185.4$'):
        (1, _u((115, 1536))),
    ('paper/transport_experiment.tex', 'no bound violation on the joint confidence event'):
        (1, _u((293, 529))),
    ('paper/transport_experiment.tex', 'no deterministic algebra or certificate-check failure'):
        (1, _u((293, 447))),
    ('paper/transport_experiment.tex', 'optimal-action\nentropy $1.579$'):
        (1, _u((115, 1422))),
    ('paper/transport_experiment.tex', 'optimality\ngap $0.123$'):
        (1, _u((115, 1454))),
    ('paper/transport_experiment.tex', 'paired-bootstrap 95\\%'):
        (1, _u((275, 142))),
    ('paper/transport_experiment.tex', 'pools all 50,000 seed--round values'):
        (1, _u((249, 1015))),
    ('paper/transport_experiment.tex', 'ranges from\n$1.02$'):
        (1, _u((249, 1074))),
    ('paper/transport_experiment.tex', 'ranges from $0.0486$'):
        (1, _u((249, 100))),
    ('paper/transport_experiment.tex', 'ranges from $1.31\\times10^{-7}$'):
        (1, _u((249, 219))),
    ('paper/transport_experiment.tex', 'rises\nfrom $81.0$'):
        (1, _u((280, 91))),
    ('paper/transport_experiment.tex', 'target labels $D_{\\rm target}\\in\\{0.25,0.5,1,2\\}$'):
        (1, _u((115, 83))),
    ('paper/transport_experiment.tex', 'the 50-seed means'):
        (1, _u((115, 1395))),
    ('paper/transport_experiment.tex', 'the same 50 base seeds'):
        (1, _u((293, 55))),
    ('paper/transport_experiment.tex', 'there are five actions'):
        (1, _u((283, 145))),
    ('paper/transport_experiment.tex', 'to $0.384$'):
        (1, _u((249, 121))),
    ('paper/transport_experiment.tex', 'to $1.18$'):
        (1, _u((249, 1093))),
    ('paper/transport_experiment.tex', 'to $94.0$'):
        (1, _u((280, 109))),
    ('paper/transport_experiment.tex', 'versus caps of $500$--$2{,}000$'):
        (1, _u((247, 471))),
    # paper/transport_experiment_appendix.tex
    ('paper/transport_experiment_appendix.tex', '$2.01\\%,4.04\\%,8.16\\%,16.27\\%$'):
        (1, _u((117, 566))),
    ('paper/transport_experiment_appendix.tex', '$97.33\\%,94.66\\%,89.39\\%,79.39\\%$'):
        (1, _u((117, 516))),
    ('paper/transport_experiment_appendix.tex', '$D_{\\rm target}=0.25,0.5,1,2$'):
        (1, _u((117, 601))),
    ('paper/transport_experiment_appendix.tex', '$T=1000$'):
        (3, _u((117, 400), (272, 49), (274, 98))),
    ('paper/transport_experiment_appendix.tex', '$e^{\\bar D_t^Q/2}$'):
        (1, _u((117, 851))),
    ('paper/transport_experiment_appendix.tex', '50 evaluation seeds'):
        (2, _u((119, 267), (272, 127))),
    ('paper/transport_experiment_appendix.tex', '50 primary-policy trajectories'):
        (1, _u((117, 351))),
    ('paper/transport_experiment_appendix.tex', '50 runs per cell'):
        (2, _u((277, 166), (276, 76))),
    ('paper/transport_experiment_appendix.tex', '50 transport-Hessian trajectories'):
        (1, _u((274, 61))),
    ('paper/transport_experiment_appendix.tex', '95\\% intervals'):
        (1, _u((272, 103))),
    ('paper/transport_experiment_appendix.tex', '\\kappa_{-,t}=\\kappa_{+,t}=1'):
        (1, _u((117, 115))),
    ('paper/transport_experiment_appendix.tex', '\\xi_t=0'):
        (1, _u((117, 149))),
    ('paper/transport_experiment_appendix.tex', 'paired-bootstrap 95\\%'):
        (1, _u((272, 86))),
    ('paper/transport_experiment_appendix.tex', 'preregistered $10^{-12}$ ratio tolerance'):
        (1, _u((273, 490))),
    # paper/transport_followup.tex
    ('paper/transport_followup.tex', '$-$0.10'):
        (1, _u((1, 0))),
    ('paper/transport_followup.tex', '$-$0.18'):
        (1, _u((2, 0))),
    ('paper/transport_followup.tex', '$-$22.57'):
        (1, _u((3, 0))),
    ('paper/transport_followup.tex', '$-$34.41'):
        (1, _u((4, 0))),
    ('paper/transport_followup.tex', '$0.16\\%$'):
        (1, _u((256, 454))),
    ('paper/transport_followup.tex', '$0.28\\%$'):
        (1, _u((256, 394))),
    ('paper/transport_followup.tex', '$12.13\\%$'):
        (1, _u((256, 464))),
    ('paper/transport_followup.tex', '$12.68\\%$'):
        (1, _u((256, 404))),
    ('paper/transport_followup.tex', '$T=1000$'):
        (4, _u((282, 54), (264, 34), (279, 20), (89, 1047))),
    ('paper/transport_followup.tex', '$T=20{,}000$ over 50 seeds'):
        (1, _u((287, 67))),
    ('paper/transport_followup.tex', '$W=0.25$'):
        (2, _u((89, 981), (250, 356))),
    ('paper/transport_followup.tex', '$W=1$'):
        (7, _u((89, 941), (88, 666), (252, 640), (252, 806), (252, 945), (6, 0), (296, 529))),
    ('paper/transport_followup.tex', '$W=10$'):
        (1, _u((7, 0))),
    ('paper/transport_followup.tex', '$W=100$'):
        (3, _u((252, 563), (8, 0), (296, 500))),
    ('paper/transport_followup.tex', '$W=100$ and $10$'):
        (2, _u((252, 563), (296, 500))),
    ('paper/transport_followup.tex', '$W=16,1,0.25$'):
        (3, _u((102, 259), (285, 475), (89, 358))),
    ('paper/transport_followup.tex', '$W\\in\\{16,1,0.25\\}$'):
        (1, _u((282, 64))),
    ('paper/transport_followup.tex', '$[92.9\\%,100\\%]$'):
        (1, _u((250, 276))),
    ('paper/transport_followup.tex', '$\\delta=0.05$'):
        (1, _u((254, 309))),
    ('paper/transport_followup.tex', '$\\sigma=0.25$; $\\lambda=1$, $\\delta=0.05$, $R=1$ and $T=20{,}000$'):
        (1, _u((254, 281))),
    ('paper/transport_followup.tex', '$c_h=4/(3\\sqrt3)$'):
        (1, _u((89, 127))),
    ('paper/transport_followup.tex', '(frozen: 440.9, 1,004.4 and 1,902.1)'):
        (1, _u((252, 221))),
    ('paper/transport_followup.tex', '0.385, 1.540 and 3.079 at $W=16,1,0.25$'):
        (1, _u((89, 332))),
    ('paper/transport_followup.tex', '10,001, 215,317 and 6,063 at $W=0.25$'):
        (1, _u((89, 952))),
    ('paper/transport_followup.tex', '10,122, 108,171 and 3,031 at $W=1$'):
        (1, _u((89, 912))),
    ('paper/transport_followup.tex', '10,155, 26,898 and 758 at $W=16$'):
        (1, _u((89, 878))),
    ('paper/transport_followup.tex', '12.30'):
        (1, _u((19, 0))),
    ('paper/transport_followup.tex', '16.75'):
        (1, _u((20, 0))),
    ('paper/transport_followup.tex', '16/50 seeds'):
        (1, _u((250, 341))),
    ('paper/transport_followup.tex', '180.01,\n177.97 and 171.84'):
        (1, _u((285, 446))),
    ('paper/transport_followup.tex', '185.26,\n183.06 and 176.67'):
        (1, _u((102, 432))),
    ('paper/transport_followup.tex', '19, 60 and 231'):
        (1, _u((248, 403))),
    ('paper/transport_followup.tex', '19,800 checks in all; the largest discrepancy was 0.039 of its tolerance'):
        (1, _u((268, 375))),
    ('paper/transport_followup.tex', '1{,}003.8'):
        (1, _u((21, 0))),
    ('paper/transport_followup.tex', '1{,}004.4'):
        (1, _u((22, 0))),
    ('paper/transport_followup.tex', '1{,}004.5'):
        (1, _u((23, 0))),
    ('paper/transport_followup.tex', '1{,}879.1'):
        (1, _u((24, 0))),
    ('paper/transport_followup.tex', '1{,}886.9'):
        (1, _u((25, 0))),
    ('paper/transport_followup.tex', '1{,}902.1'):
        (1, _u((26, 0))),
    ('paper/transport_followup.tex', '2000, 2000 and 1000'):
        (1, _u((248, 112))),
    ('paper/transport_followup.tex', '286/50,000'):
        (1, _u((250, 396))),
    ('paper/transport_followup.tex', '2{,}396.8'):
        (1, _u((27, 0))),
    ('paper/transport_followup.tex', '2{,}837.6'):
        (1, _u((28, 0))),
    ('paper/transport_followup.tex', '31.63'):
        (1, _u((29, 0))),
    ('paper/transport_followup.tex', '33.4'):
        (2, _u((252, 920), (30, 0))),
    ('paper/transport_followup.tex', '340.0'):
        (2, _u((252, 935), (31, 0))),
    ('paper/transport_followup.tex', '37.35'):
        (1, _u((32, 0))),
    ('paper/transport_followup.tex', '3{,}784.6'):
        (1, _u((33, 0))),
    ('paper/transport_followup.tex', '4.22'):
        (1, _u((34, 0))),
    ('paper/transport_followup.tex', '42.8'):
        (2, _u((252, 926), (35, 0))),
    ('paper/transport_followup.tex', '43.1'):
        (2, _u((252, 320), (36, 0))),
    ('paper/transport_followup.tex', '43.2'):
        (2, _u((37, 0), (37, 0))),
    ('paper/transport_followup.tex', '43.3'):
        (3, _u((38, 0), (38, 0), (296, 636))),
    ('paper/transport_followup.tex', '43.4'):
        (2, _u((40, 0), (39, 0))),
    ('paper/transport_followup.tex', '43.47'):
        (1, _u((40, 0))),
    ('paper/transport_followup.tex', '43.5'):
        (1, _u((41, 0))),
    ('paper/transport_followup.tex', '43.9'):
        (2, _u((42, 0), (296, 642))),
    ('paper/transport_followup.tex', '44.1'):
        (3, _u((252, 329), (252, 1082), (43, 0))),
    ('paper/transport_followup.tex', '440.3'):
        (1, _u((44, 0))),
    ('paper/transport_followup.tex', '440.9'):
        (3, _u((252, 230), (45, 0), (296, 618))),
    ('paper/transport_followup.tex', '441.2'):
        (1, _u((46, 0))),
    ('paper/transport_followup.tex', '4\\log\\cosh(1/\\sqrt W)\\approx1.0\\times10^{-4}'):
        (1, _u((254, 652))),
    ('paper/transport_followup.tex', '4{,}789.0'):
        (1, _u((47, 0))),
    ('paper/transport_followup.tex', '5.16'):
        (1, _u((48, 0))),
    ('paper/transport_followup.tex', '5.53'):
        (1, _u((49, 0))),
    ('paper/transport_followup.tex', '5.58'):
        (1, _u((50, 0))),
    ('paper/transport_followup.tex', '5.86'):
        (1, _u((51, 0))),
    ('paper/transport_followup.tex', '50 paired'):
        (2, _u((282, 88), (254, 876))),
    ('paper/transport_followup.tex', '50 seeds per condition'):
        (1, _u((264, 178))),
    ('paper/transport_followup.tex', '50/50 successes'):
        (1, _u((250, 197))),
    ('paper/transport_followup.tex', '6.24'):
        (1, _u((52, 0))),
    ('paper/transport_followup.tex', '600 trajectories'):
        (2, _u((282, 132), (250, 35))),
    ('paper/transport_followup.tex', '65.87'):
        (1, _u((53, 0))),
    ('paper/transport_followup.tex', '65.94'):
        (1, _u((54, 0))),
    ('paper/transport_followup.tex', '66.04'):
        (1, _u((55, 0))),
    ('paper/transport_followup.tex', '6{,}733.3'):
        (1, _u((56, 0))),
    ('paper/transport_followup.tex', '82.79'):
        (1, _u((57, 0))),
    ('paper/transport_followup.tex', '8{,}635.4'):
        (1, _u((58, 0))),
    ('paper/transport_followup.tex', '8{,}667.5'):
        (1, _u((59, 0))),
    ('paper/transport_followup.tex', '9.05'):
        (1, _u((60, 0))),
    ('paper/transport_followup.tex', '9.51, 37.19 and 80.91'):
        (1, _u((248, 330))),
    ('paper/transport_followup.tex', '95\\% intervals'):
        (1, _u((285, 272))),
    ('paper/transport_followup.tex', '97.104\\%'):
        (1, _u((102, 214))),
    ('paper/transport_followup.tex', '99.372\\%'):
        (1, _u((102, 224))),
    ('paper/transport_followup.tex', '99.382\\%'):
        (1, _u((102, 325))),
    ('paper/transport_followup.tex', '99.508\\%'):
        (1, _u((102, 237))),
    ('paper/transport_followup.tex', '99.962\\%'):
        (1, _u((102, 335))),
    ('paper/transport_followup.tex', '99.982\\%'):
        (1, _u((102, 348))),
    ('paper/transport_followup.tex', '9{,}294.0'):
        (1, _u((62, 0))),
    ('paper/transport_followup.tex', '9{,}364.3'):
        (1, _u((63, 0))),
    ('paper/transport_followup.tex', '9{,}372.05'):
        (1, _u((64, 0))),
    ('paper/transport_followup.tex', 'Algorithm~1 of'):
        (1, _u((278, 88))),
    ('paper/transport_followup.tex', 'All 1,500 evaluation runs completed'):
        (1, _u((268, 20))),
    ('paper/transport_followup.tex', 'All 50 frozen bounds are below the cap; the largest is 0.761 of it.'):
        (1, _u((253, 498))),
    ('paper/transport_followup.tex', 'All 600 trajectories'):
        (1, _u((250, 31))),
    ('paper/transport_followup.tex', 'Each cell has 50 paired evaluation seeds'):
        (1, _u((254, 862))),
    ('paper/transport_followup.tex', 'In the 1,100 corrected-center runs'):
        (1, _u((268, 182))),
    ('paper/transport_followup.tex', 'Intervals are pointwise 95\\% paired'):
        (1, _u((264, 92))),
    ('paper/transport_followup.tex', 'On the 150 recorded context--action sequences'):
        (1, _u((89, 1293))),
    ('paper/transport_followup.tex', 'The per-run mean envelope is 98.3\\%--98.5\\% of that constant'):
        (1, _u((89, 373))),
    ('paper/transport_followup.tex', 'UCB-GLM has 34.4 units less regret than frozen'):
        (1, _u((88, 526))),
    ('paper/transport_followup.tex', 'UCB-GLM has mean regret 33.4, 42.8 and 340.0'):
        (1, _u((252, 896))),
    ('paper/transport_followup.tex', 'UCB-GLM minus frozen is $-34.4$ ($p=5.7\\times10^{-34}$)'):
        (1, _u((253, 651))),
    ('paper/transport_followup.tex', '[$-$1.10, 0.81]'):
        (1, _u((125, 0))),
    ('paper/transport_followup.tex', '[$-$1.17, 0.72]'):
        (1, _u((126, 0))),
    ('paper/transport_followup.tex', '[$-$24.03, $-$21.04]'):
        (1, _u((127, 0))),
    ('paper/transport_followup.tex', '[$-$36.56, $-$32.26]'):
        (1, _u((128, 0))),
    ('paper/transport_followup.tex', '[15.43, 18.00]'):
        (1, _u((129, 0))),
    ('paper/transport_followup.tex', 'all 150 frozen-policy'):
        (1, _u((248, 193))),
    ('paper/transport_followup.tex', 'all 600 histories'):
        (1, _u((256, 279))),
    ('paper/transport_followup.tex', 'at $W=1$ UCB-GLM has about 7.7 times the regret of linear UCB.'):
        (1, _u((88, 663))),
    ('paper/transport_followup.tex', 'by at most 23.1 units'):
        (1, _u((296, 714))),
    ('paper/transport_followup.tex', 'design cell ($W=T=20{,}000$)'):
        (1, _u((288, 15))),
    ('paper/transport_followup.tex', 'differences with pointwise 95\\% paired'):
        (1, _u((279, 99))),
    ('paper/transport_followup.tex', 'endpoint minus frozen is $-15.3$ ($[-20.5,-10.2]$)'):
        (1, _u((252, 646))),
    ('paper/transport_followup.tex', 'every $p\\le1.2\\times10^{-108}$'):
        (1, _u((253, 211))),
    ('paper/transport_followup.tex', 'exact 95\\% Clopper--Pearson interval'):
        (1, _u((250, 222))),
    ('paper/transport_followup.tex', 'from 440.9--1,902.1 to 43.3--43.9'):
        (1, _u((296, 613))),
    ('paper/transport_followup.tex', 'frozen is $16.8$ ($p=5.3\\times10^{-30}$)'):
        (1, _u((253, 725))),
    ('paper/transport_followup.tex', 'grows to 2,396.8, 3,784.6 and 6,733.3'):
        (1, _u((252, 857))),
    ('paper/transport_followup.tex', 'interval lies inside $(-1.0,1.0)$'):
        (1, _u((253, 420))),
    ('paper/transport_followup.tex', 'intervals from 10,000 resamples of 50 seeds per condition'):
        (1, _u((264, 143))),
    ('paper/transport_followup.tex', 'is 37,195, which is 0.93 of the cap $2T\\min(1,\\sqrt W)=40{,}000$'):
        (1, _u((254, 482))),
    ('paper/transport_followup.tex', 'it has about 7.7 times the regret of linear UCB (44.1)'):
        (1, _u((252, 1033))),
    ('paper/transport_followup.tex', 'its own cap $2T=2000$'):
        (1, _u((89, 1402))),
    ('paper/transport_followup.tex', 'its random phase lasted 12 to 34 rounds'):
        (1, _u((268, 141))),
    ('paper/transport_followup.tex', 'its standard deviation over 50 seeds'):
        (1, _u((288, 83))),
    ('paper/transport_followup.tex', 'naive minus frozen is $-23.1$ ($[-28.3,-18.0]$)'):
        (1, _u((252, 701))),
    ('paper/transport_followup.tex', 'prespecified margin $\\Delta=3.0$'):
        (1, _u((253, 315))),
    ('paper/transport_followup.tex', 'relative to the cap $40{,}000$'):
        (1, _u((287, 173))),
    ('paper/transport_followup.tex', 'stay between 43.1 and 44.1'):
        (1, _u((252, 307))),
    ('paper/transport_followup.tex', 'the realized $\\gamma_T$ is about 151--153 (medians)'):
        (1, _u((89, 1056))),
    ('paper/transport_followup.tex', 'they use 10,000 paired seed-bootstrap resamples'):
        (1, _u((285, 327))),
    ('paper/transport_followup.tex', 'where $\\kappa=0.0707$ makes its radius $\\alpha=19.19$ (against $1.36$ at $W=T$)'):
        (1, _u((252, 952))),
    ('paper/transport_followup.tex', 'width costs 16.8 regret units relative to frozen'):
        (1, _u((88, 472))),
    ('paper/transport_followup.tex', 'with $d=29$'):
        (1, _u((89, 1031))),
    # paper/transport_followup_appendix.tex
    ('paper/transport_followup_appendix.tex', '$0.00392155$'):
        (1, _u((290, 611))),
    ('paper/transport_followup_appendix.tex', '$0.005$'):
        (1, _u((286, 613))),
    ('paper/transport_followup_appendix.tex', '$0.124$'):
        (1, _u((299, 178))),
    ('paper/transport_followup_appendix.tex', '$1.735$'):
        (1, _u((299, 187))),
    ('paper/transport_followup_appendix.tex', '$3\\times4\\times50=600$'):
        (1, _u((290, 648))),
    ('paper/transport_followup_appendix.tex', '$4+5+20=29$'):
        (1, _u((255, 345))),
    ('paper/transport_followup_appendix.tex', '$5.300$'):
        (1, _u((299, 200))),
    ('paper/transport_followup_appendix.tex', '$\\delta=0.05$'):
        (1, _u((255, 702))),
    ('paper/transport_followup_appendix.tex', '$\\{1,5,20\\}$'):
        (1, _u((290, 388))),
    ('paper/transport_followup_appendix.tex', '$\\{3\\times10^{-5},10^{-4},3\\times10^{-4}\\}$'):
        (1, _u((290, 339))),
    ('paper/transport_followup_appendix.tex', '1000 rounds in its denominator'):
        (1, _u((294, 476))),
    ('paper/transport_followup_appendix.tex', '1024'):
        (1, _u((267, 205))),
    ('paper/transport_followup_appendix.tex', '12 combinations'):
        (1, _u((118, 284))),
    ('paper/transport_followup_appendix.tex', '2--10'):
        (1, _u((291, 690))),
    ('paper/transport_followup_appendix.tex', '20 steps'):
        (1, _u((290, 488))),
    ('paper/transport_followup_appendix.tex', '2048'):
        (3, _u((267, 128), (267, 214), (267, 295))),
    ('paper/transport_followup_appendix.tex', '2048 and 4096'):
        (1, _u((267, 295))),
    ('paper/transport_followup_appendix.tex', '24 declared trajectories'):
        (1, _u((267, 226))),
    ('paper/transport_followup_appendix.tex', '24 development trajectories'):
        (1, _u((255, 902))),
    ('paper/transport_followup_appendix.tex', '250-digit'):
        (1, _u((291, 325))),
    ('paper/transport_followup_appendix.tex', '270 tuning\ntrajectories'):
        (1, _u((290, 169))),
    ('paper/transport_followup_appendix.tex', '30 tuning'):
        (1, _u((290, 560))),
    ('paper/transport_followup_appendix.tex', '30000--30001'):
        (1, _u((255, 89))),
    ('paper/transport_followup_appendix.tex', '30100--30109'):
        (1, _u((255, 116))),
    ('paper/transport_followup_appendix.tex', '30200--30249'):
        (1, _u((255, 151))),
    ('paper/transport_followup_appendix.tex', '50 evaluation seeds'):
        (1, _u((295, 167))),
    ('paper/transport_followup_appendix.tex', '50 histories'):
        (1, _u((265, 109))),
    ('paper/transport_followup_appendix.tex', '50 seeds per condition'):
        (1, _u((258, 191))),
    ('paper/transport_followup_appendix.tex', '50,000 dependent states'):
        (1, _u((118, 382))),
    ('paper/transport_followup_appendix.tex', '50,000 seed--round observations per condition'):
        (1, _u((281, 85))),
    ('paper/transport_followup_appendix.tex', '600 trajectories'):
        (1, _u((286, 146))),
    ('paper/transport_followup_appendix.tex', '600,000 states'):
        (1, _u((291, 654))),
    ('paper/transport_followup_appendix.tex', '65 changes'):
        (1, _u((291, 637))),
    ('paper/transport_followup_appendix.tex', 'At rounds 1, 10, 100, 1,000, 10,000 and 20,000'):
        (1, _u((263, 343))),
    ('paper/transport_followup_appendix.tex', 'Candidate 008'):
        (1, _u((290, 438))),
    ('paper/transport_followup_appendix.tex', 'Development seeds 41000--41009'):
        (1, _u((289, 20))),
    ('paper/transport_followup_appendix.tex', 'The 294'):
        (1, _u((290, 693))),
    ('paper/transport_followup_appendix.tex', 'The design cell uses $c=1$'):
        (1, _u((289, 291))),
    ('paper/transport_followup_appendix.tex', 'The margin $\\Delta=3.0$ is a quarter'):
        (1, _u((289, 495))),
    ('paper/transport_followup_appendix.tex', 'across 50 seeds'):
        (1, _u((257, 271))),
    ('paper/transport_followup_appendix.tex', 'all 600 trajectories'):
        (1, _u((286, 142))),
    ('paper/transport_followup_appendix.tex', 'and 1000 rounds'):
        (1, _u((258, 164))),
    ('paper/transport_followup_appendix.tex', 'at 16 states'):
        (1, _u((291, 533))),
    ('paper/transport_followup_appendix.tex', 'below 0.629'):
        (1, _u((291, 720))),
    ('paper/transport_followup_appendix.tex', 'development mean Hessian-minus-frozen difference, 12.0,'):
        (1, _u((289, 539))),
    ('paper/transport_followup_appendix.tex', 'divided by 1000'):
        (1, _u((118, 478))),
    ('paper/transport_followup_appendix.tex', 'evaluation seeds 41200--41249'):
        (1, _u((289, 82))),
    ('paper/transport_followup_appendix.tex', 'learning rate $3\\times10^{-4}$'):
        (1, _u((290, 453))),
    ('paper/transport_followup_appendix.tex', 'learning rates $\\{3\\times10^{-6},10^{-5},3\\times10^{-5}\\}$ and $\\{5,20\\}$ steps'):
        (1, _u((269, 347))),
    ('paper/transport_followup_appendix.tex', 'rate $3\\times10^{-6}$ with 5 steps had the smallest mean MSE, $4.062\\times10^{-5}$, and the six means were within 0.2\\% of each other'):
        (1, _u((269, 557))),
    ('paper/transport_followup_appendix.tex', 'rounds 1, 2, 10, 100, 500, and 1000'):
        (1, _u((286, 437))),
    ('paper/transport_followup_appendix.tex', 'standard deviation $0.25$'):
        (1, _u((255, 654))),
    ('paper/transport_followup_appendix.tex', 'summarize 50 seeds'):
        (1, _u((294, 542))),
    ('paper/transport_followup_appendix.tex', 'teacher seed 1729'):
        (1, _u((255, 52))),
    ('paper/transport_followup_appendix.tex', 'tuning seeds 41100--41109'):
        (1, _u((289, 52))),
    ('paper/transport_followup_appendix.tex', 'two one-sided tests with $\\Delta=3.0$'):
        (1, _u((246, 259))),
    ('paper/transport_followup_appendix.tex', 'with 10,000 resamples and'):
        (1, _u((295, 248))),
    # paper/transport_proofs.tex
    ('paper/transport_proofs.tex', '$0.505$, $0.570$ and $0.687$ at $W=16,1,0.25$'):
        (1, _u((173, 171))),
    ('paper/transport_proofs.tex', '$1+\\cosh^4(1/\\sqrt W)=2.13$, $6.67$ and $201.3$'):
        (1, _u((292, 2254))),
    ('paper/transport_proofs.tex', '$T=1000$'):
        (1, _u((292, 2057))),
    ('paper/transport_proofs.tex', '$W=16,1,0.25$'):
        (2, _u((173, 203), (292, 2070))),
    ('paper/transport_proofs.tex', '$\\bar h$ is $2.13$, $8.39$ and $2982$'):
        (1, _u((292, 2317))),
    ('paper/transport_proofs.tex', "At that study's $T=1000$ and $W=16,1,0.25$"):
        (1, _u((292, 2041))),
    ('paper/transport_proofs.tex', 'With $\\sigma=0.25$ and $\\lambda=B_\\phi=1$ the factor is $0.650$'):
        (1, _u((172, 266))),
    ('paper/transport_proofs.tex', '\\alpha_t=1'):
        (1, _u((292, 170))),
    ('paper/transport_proofs.tex', '\\setcounter{table}{0}'):
        (1, _u((229, 0))),
    ('paper/transport_proofs.tex', '\\xi_t=0'):
        (3, _u((141, 414), (142, 565), (292, 184))),
    ('paper/transport_proofs.tex', 'about $12.3/\\sqrt c$'):
        (1, _u((292, 1968))),
    ('paper/transport_proofs.tex', 'approximately $10^{42.6}$, $10^{169.4}$ and $10^{338.4}$ ($D_{T,W}=97.3$, $389.3$ and $778.6$)'):
        (1, _u((292, 2122))),
    # paper/transport_support_appendix.tex
    ('paper/transport_support_appendix.tex', '\\xi_t=0'):
        (2, _u((84, 159), (124, 270))),
    # paper/transport_theory.tex
    ('paper/transport_theory.tex', '\\alpha_t=1'):
        (1, _u((133, 696))),
    ('paper/transport_theory.tex', '\\kappa_{-,t}=\\kappa_{+,t}=1'):
        (2, _u((90, 29), (133, 710))),
    ('paper/transport_theory.tex', '\\xi_t=0'):
        (2, _u((138, 439), (133, 745))),
    # submissions/tmlr_2026/main.tex
    ('submissions/tmlr_2026/main.tex', '29-parameter'):
        (1, _u((103, 704))),
    ('submissions/tmlr_2026/main.tex', '34.4 units less regret for a generalized-linear UCB baseline'):
        (1, _u((103, 1314))),
    ('submissions/tmlr_2026/main.tex', '50 paired'):
        (1, _u((103, 741))),
    ('submissions/tmlr_2026/main.tex', '95\\% intervals'):
        (1, _u((103, 869))),
    ('submissions/tmlr_2026/main.tex', 'a regret cost of 16.8 units for Hessian transport'):
        (1, _u((103, 1259))),
    ('submissions/tmlr_2026/main.tex', 'pointwise paired 95\\% intervals'):
        (1, _u((103, 852))),
    # submissions/tmlr_2026/supplement_README.md
    ('submissions/tmlr_2026/supplement_README.md', '2,400 trajectories'):
        (1, _u((16, 41))),
    ('submissions/tmlr_2026/supplement_README.md', '21 artifacts'):
        (1, _u((109, 30))),
    ('submissions/tmlr_2026/supplement_README.md', 'all 21 published tables, figures and CSVs'):
        (1, _u((15, 386))),
}

#: (path, literal) -> (category, occurrences, ((unit, offset-in-unit), ...))
CLASSIFIED_PINS: dict[tuple[str, str], tuple[str, int, tuple[tuple[str, int], ...]]] = {
    # paper/body_intro.tex
    ('paper/body_intro.tex', '1'):
        ('math-constant', 2, _u((251, 912), (251, 916))),
    # paper/body_related.tex
    ('paper/body_related.tex', '0'):
        ('math-constant', 1, _u((261, 282))),
    ('paper/body_related.tex', '0,1'):
        ('interval-endpoint', 1, _u((261, 993))),
    # paper/figures/transport_conceptual_geometry.tex
    ('paper/figures/transport_conceptual_geometry.tex', '.25'):
        ('analytic-schematic', 1, _u((161, 275))),
    ('paper/figures/transport_conceptual_geometry.tex', '.55'):
        ('analytic-schematic', 2, _u((161, 456), (169, 291))),
    ('paper/figures/transport_conceptual_geometry.tex', '.65'):
        ('analytic-schematic', 1, _u((169, 870))),
    ('paper/figures/transport_conceptual_geometry.tex', '.82'):
        ('analytic-schematic', 1, _u((169, 905))),
    ('paper/figures/transport_conceptual_geometry.tex', '0'):
        ('analytic-schematic', 7, _u((161, 250), (161, 424), (161, 453), (214, 23), (214, 85), (169, 857), (170, 314))),
    ('paper/figures/transport_conceptual_geometry.tex', '0,0'):
        ('analytic-schematic', 1, _u((161, 304))),
    ('paper/figures/transport_conceptual_geometry.tex', '0,13'):
        ('analytic-schematic', 1, _u((170, 107))),
    ('paper/figures/transport_conceptual_geometry.tex', '1'):
        ('analytic-schematic', 6, _u((161, 501), (161, 542), (169, 834), (168, 183), (170, 125), (170, 332))),
    ('paper/figures/transport_conceptual_geometry.tex', '1,0'):
        ('analytic-schematic', 1, _u((161, 407))),
    ('paper/figures/transport_conceptual_geometry.tex', '1,10'):
        ('analytic-schematic', 1, _u((170, 88))),
    ('paper/figures/transport_conceptual_geometry.tex', '1.05'):
        ('analytic-schematic', 1, _u((169, 37))),
    ('paper/figures/transport_conceptual_geometry.tex', '1.25'):
        ('analytic-schematic', 2, _u((214, 26), (214, 149))),
    ('paper/figures/transport_conceptual_geometry.tex', '1.8'):
        ('analytic-schematic', 2, _u((214, 88), (168, 170))),
    ('paper/figures/transport_conceptual_geometry.tex', '1.95'):
        ('analytic-schematic', 1, _u((168, 117))),
    ('paper/figures/transport_conceptual_geometry.tex', '10'):
        ('analytic-schematic', 3, _u((216, 91), (216, 132), (216, 146))),
    ('paper/figures/transport_conceptual_geometry.tex', '11.5'):
        ('analytic-schematic', 4, _u((168, 34), (168, 49), (170, 102), (170, 258))),
    ('paper/figures/transport_conceptual_geometry.tex', '13'):
        ('analytic-schematic', 3, _u((216, 105), (216, 173), (216, 187))),
    ('paper/figures/transport_conceptual_geometry.tex', '14.5'):
        ('analytic-schematic', 13, _u((168, 111), (168, 127), (168, 164), (215, 97), (215, 173), (215, 189), (215, 216), (216, 212), (217, 104), (217, 184), (217, 200), (217, 227), (170, 120))),
    ('paper/figures/transport_conceptual_geometry.tex', '14.72'):
        ('analytic-schematic', 1, _u((216, 269))),
    ('paper/figures/transport_conceptual_geometry.tex', '14.85'):
        ('analytic-schematic', 1, _u((170, 49))),
    ('paper/figures/transport_conceptual_geometry.tex', '16.2'):
        ('analytic-schematic', 1, _u((161, 270))),
    ('paper/figures/transport_conceptual_geometry.tex', '2'):
        ('analytic-schematic', 4, _u((169, 141), (217, 62), (170, 345), (170, 375))),
    ('paper/figures/transport_conceptual_geometry.tex', '2.1'):
        ('analytic-schematic', 1, _u((168, 40))),
    ('paper/figures/transport_conceptual_geometry.tex', '2.25'):
        ('analytic-schematic', 1, _u((215, 26))),
    ('paper/figures/transport_conceptual_geometry.tex', '2.35'):
        ('analytic-schematic', 1, _u((169, 173))),
    ('paper/figures/transport_conceptual_geometry.tex', '2.73'):
        ('analytic-schematic', 2, _u((215, 133), (215, 179))),
    ('paper/figures/transport_conceptual_geometry.tex', '2.85'):
        ('analytic-schematic', 3, _u((215, 87), (215, 103), (215, 222))),
    ('paper/figures/transport_conceptual_geometry.tex', '2.97'):
        ('analytic-schematic', 2, _u((215, 148), (215, 195))),
    ('paper/figures/transport_conceptual_geometry.tex', '3'):
        ('analytic-schematic', 5, _u((169, 126), (169, 138), (169, 218), (169, 297), (169, 380))),
    ('paper/figures/transport_conceptual_geometry.tex', '3.02'):
        ('analytic-schematic', 3, _u((169, 768), (169, 783), (169, 819))),
    ('paper/figures/transport_conceptual_geometry.tex', '3.525'):
        ('analytic-schematic', 3, _u((169, 485), (169, 613), (169, 630))),
    ('paper/figures/transport_conceptual_geometry.tex', '3.55'):
        ('analytic-schematic', 1, _u((169, 957))),
    ('paper/figures/transport_conceptual_geometry.tex', '3.6'):
        ('analytic-schematic', 4, _u((169, 168), (169, 637), (169, 651), (169, 686))),
    ('paper/figures/transport_conceptual_geometry.tex', '3.75'):
        ('analytic-schematic', 1, _u((216, 26))),
    ('paper/figures/transport_conceptual_geometry.tex', '30'):
        ('analytic-schematic', 1, _u((168, 12))),
    ('paper/figures/transport_conceptual_geometry.tex', '4'):
        ('analytic-schematic', 2, _u((161, 490), (169, 214))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.05'):
        ('analytic-schematic', 3, _u((169, 540), (169, 746), (169, 762))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.2'):
        ('analytic-schematic', 1, _u((169, 973))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.23'):
        ('analytic-schematic', 2, _u((216, 136), (216, 177))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.32'):
        ('analytic-schematic', 2, _u((169, 620), (169, 752))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.35'):
        ('analytic-schematic', 12, _u((169, 43), (169, 58), (169, 221), (169, 300), (169, 383), (169, 398), (169, 492), (169, 546), (216, 95), (216, 109), (216, 218), (216, 276))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.37'):
        ('analytic-schematic', 1, _u((169, 1008))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.4'):
        ('analytic-schematic', 2, _u((169, 646), (169, 778))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.47'):
        ('analytic-schematic', 4, _u((169, 680), (169, 813), (216, 150), (216, 191))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.53'):
        ('analytic-schematic', 1, _u((169, 434))),
    ('paper/figures/transport_conceptual_geometry.tex', '4.6'):
        ('analytic-schematic', 2, _u((169, 393), (169, 429))),
    ('paper/figures/transport_conceptual_geometry.tex', '40'):
        ('analytic-schematic', 2, _u((169, 12), (169, 101))),
    ('paper/figures/transport_conceptual_geometry.tex', '5.2'):
        ('analytic-schematic', 1, _u((169, 53))),
    ('paper/figures/transport_conceptual_geometry.tex', '5.25'):
        ('analytic-schematic', 1, _u((217, 26))),
    ('paper/figures/transport_conceptual_geometry.tex', '5.73'):
        ('analytic-schematic', 2, _u((217, 142), (217, 190))),
    ('paper/figures/transport_conceptual_geometry.tex', '5.85'):
        ('analytic-schematic', 3, _u((217, 94), (217, 110), (217, 233))),
    ('paper/figures/transport_conceptual_geometry.tex', '5.97'):
        ('analytic-schematic', 2, _u((217, 157), (217, 206))),
    ('paper/figures/transport_conceptual_geometry.tex', '50'):
        ('analytic-schematic', 2, _u((170, 12), (170, 141))),
    ('paper/figures/transport_conceptual_geometry.tex', '55'):
        ('analytic-schematic', 1, _u((168, 74))),
    ('paper/figures/transport_conceptual_geometry.tex', '6'):
        ('analytic-schematic', 1, _u((169, 276))),
    ('paper/figures/transport_conceptual_geometry.tex', '6.35'):
        ('analytic-schematic', 2, _u((168, 55), (168, 133))),
    ('paper/figures/transport_conceptual_geometry.tex', '6.64'):
        ('analytic-schematic', 1, _u((170, 167))),
    ('paper/figures/transport_conceptual_geometry.tex', '6.7'):
        ('analytic-schematic', 3, _u((169, 129), (170, 40), (170, 56))),
    ('paper/figures/transport_conceptual_geometry.tex', '6.76'):
        ('analytic-schematic', 1, _u((170, 181))),
    ('paper/figures/transport_conceptual_geometry.tex', '6.86'):
        ('analytic-schematic', 1, _u((170, 216))),
    ('paper/figures/transport_conceptual_geometry.tex', '65'):
        ('analytic-schematic', 3, _u((161, 89), (169, 529), (169, 718))),
    ('paper/figures/transport_conceptual_geometry.tex', '7'):
        ('analytic-schematic', 4, _u((214, 146), (215, 23), (216, 23), (217, 23))),
    ('paper/figures/transport_conceptual_geometry.tex', '7.15'):
        ('analytic-schematic', 6, _u((169, 860), (169, 875), (169, 910), (169, 963), (169, 978), (169, 1014))),
    ('paper/figures/transport_conceptual_geometry.tex', '7.4'):
        ('analytic-schematic', 1, _u((170, 264))),
    ('paper/figures/transport_conceptual_geometry.tex', '7.85'):
        ('analytic-schematic', 1, _u((170, 317))),
    ('paper/figures/transport_conceptual_geometry.tex', '70'):
        ('analytic-schematic', 1, _u((161, 196))),
    ('paper/figures/transport_conceptual_geometry.tex', '8.15'):
        ('analytic-schematic', 1, _u((170, 34))),
    ('paper/figures/transport_conceptual_geometry.tex', '8.35'):
        ('analytic-schematic', 1, _u((161, 253))),
    ('paper/figures/transport_conceptual_geometry.tex', '8.5'):
        ('analytic-schematic', 7, _u((215, 82), (215, 128), (215, 143), (217, 89), (217, 137), (217, 152), (170, 83))),
    ('paper/figures/transport_conceptual_geometry.tex', '80'):
        ('analytic-schematic', 3, _u((161, 138), (169, 474), (169, 585))),
    # paper/figures/transport_conceptual_interfaces.tex
    ('paper/figures/transport_conceptual_interfaces.tex', '.3'):
        ('analytic-schematic', 1, _u((160, 292))),
    ('paper/figures/transport_conceptual_interfaces.tex', '0'):
        ('analytic-schematic', 7, _u((160, 268), (213, 40), (167, 33), (167, 80), (167, 199), (167, 316), (167, 499))),
    ('paper/figures/transport_conceptual_interfaces.tex', '0,0'):
        ('analytic-schematic', 1, _u((160, 320))),
    ('paper/figures/transport_conceptual_interfaces.tex', '1.15'):
        ('analytic-schematic', 4, _u((218, 35), (11, 58), (10, 54), (9, 61))),
    ('paper/figures/transport_conceptual_interfaces.tex', '1.8'):
        ('analytic-schematic', 1, _u((218, 30))),
    ('paper/figures/transport_conceptual_interfaces.tex', '10.2'):
        ('analytic-schematic', 1, _u((10, 48))),
    ('paper/figures/transport_conceptual_interfaces.tex', '11'):
        ('analytic-schematic', 1, _u((122, 68))),
    ('paper/figures/transport_conceptual_interfaces.tex', '14.4'):
        ('analytic-schematic', 1, _u((9, 55))),
    ('paper/figures/transport_conceptual_interfaces.tex', '16.2'):
        ('analytic-schematic', 2, _u((160, 287), (167, 45))),
    ('paper/figures/transport_conceptual_interfaces.tex', '2'):
        ('analytic-schematic', 2, _u((160, 160), (167, 355))),
    ('paper/figures/transport_conceptual_interfaces.tex', '2.2'):
        ('analytic-schematic', 3, _u((213, 43), (86, 90), (122, 72))),
    ('paper/figures/transport_conceptual_interfaces.tex', '28'):
        ('analytic-schematic', 2, _u((160, 146), (167, 12))),
    ('paper/figures/transport_conceptual_interfaces.tex', '4.6'):
        ('analytic-schematic', 2, _u((167, 36), (167, 51))),
    ('paper/figures/transport_conceptual_interfaces.tex', '4.95'):
        ('analytic-schematic', 1, _u((167, 83))),
    ('paper/figures/transport_conceptual_interfaces.tex', '5.5'):
        ('analytic-schematic', 1, _u((86, 85))),
    ('paper/figures/transport_conceptual_interfaces.tex', '5.57'):
        ('analytic-schematic', 1, _u((167, 202))),
    ('paper/figures/transport_conceptual_interfaces.tex', '55'):
        ('analytic-schematic', 1, _u((160, 89))),
    ('paper/figures/transport_conceptual_interfaces.tex', '6'):
        ('analytic-schematic', 1, _u((11, 55))),
    ('paper/figures/transport_conceptual_interfaces.tex', '6.11'):
        ('analytic-schematic', 1, _u((167, 319))),
    ('paper/figures/transport_conceptual_interfaces.tex', '6.65'):
        ('analytic-schematic', 1, _u((167, 502))),
    ('paper/figures/transport_conceptual_interfaces.tex', '6.8'):
        ('analytic-schematic', 1, _u((160, 271))),
    # paper/scope_limitations.tex
    ('paper/scope_limitations.tex', '12'):
        ('protocol-constant', 1, _u((116, 122))),
    # paper/transport_experiment_appendix.tex
    ('paper/transport_experiment_appendix.tex', '1'):
        ('math-constant', 7, _u((266, 168), (266, 177), (70, 19), (69, 19), (80, 18), (80, 46), (71, 10))),
    ('paper/transport_experiment_appendix.tex', '1.13.1'):
        ('historical-dependency-version', 1, _u((271, 661))),
    ('paper/transport_experiment_appendix.tex', '1.15.2'):
        ('historical-dependency-version', 1, _u((271, 600))),
    ('paper/transport_experiment_appendix.tex', '2'):
        ('math-constant', 10, _u((266, 104), (266, 108), (266, 171), (70, 1), (70, 44), (69, 1), (69, 44), (80, 43), (80, 64), (71, 1))),
    # paper/transport_followup.tex
    ('paper/transport_followup.tex', '0'):
        ('math-constant', 2, _u((278, 434), (278, 1154))),
    ('paper/transport_followup.tex', '0,1'):
        ('interval-endpoint', 1, _u((278, 727))),
    ('paper/transport_followup.tex', '1'):
        ('math-constant', 10, _u((248, 90), (89, 159), (89, 1463), (254, 167), (278, 337), (278, 506), (278, 520), (278, 569), (278, 937), (278, 946))),
    ('paper/transport_followup.tex', '10,000'):
        ('protocol-constant', 1, _u((288, 225))),
    ('paper/transport_followup.tex', '100,10,1'):
        ('protocol-constant', 1, _u((254, 727))),
    ('paper/transport_followup.tex', '12'):
        ('protocol-constant', 1, _u((254, 184))),
    ('paper/transport_followup.tex', '2'):
        ('math-constant', 15, _u((248, 83), (89, 119), (89, 277), (89, 283), (89, 534), (89, 549), (89, 553), (89, 585), (89, 588), (89, 1536), (278, 499), (278, 508), (278, 564), (278, 877), (278, 940))),
    ('paper/transport_followup.tex', '3'):
        ('protocol-constant', 1, _u((254, 96))),
    ('paper/transport_followup.tex', '4'):
        ('math-constant', 1, _u((89, 1285))),
    ('paper/transport_followup.tex', '6'):
        ('protocol-constant', 1, _u((254, 141))),
    ('paper/transport_followup.tex', '90'):
        ('protocol-constant', 1, _u((253, 404))),
    ('paper/transport_followup.tex', '95'):
        ('protocol-constant', 2, _u((288, 184), (61, 0))),
    # paper/transport_followup_appendix.tex
    ('paper/transport_followup_appendix.tex', '0'):
        ('math-constant', 1, _u((269, 188))),
    ('paper/transport_followup_appendix.tex', '0.05'):
        ('protocol-constant', 2, _u((246, 252), (246, 671))),
    ('paper/transport_followup_appendix.tex', '0.9'):
        ('protocol-constant', 1, _u((289, 417))),
    ('paper/transport_followup_appendix.tex', '1'):
        ('math-constant', 7, _u((265, 69), (298, 434), (298, 526), (299, 151), (299, 581), (263, 274), (263, 559))),
    ('paper/transport_followup_appendix.tex', '1,10,100'):
        ('protocol-constant', 1, _u((289, 352))),
    ('paper/transport_followup_appendix.tex', '10'):
        ('protocol-constant', 1, _u((269, 464))),
    ('paper/transport_followup_appendix.tex', '10,000'):
        ('protocol-constant', 1, _u((246, 747))),
    ('paper/transport_followup_appendix.tex', '2'):
        ('math-constant', 12, _u((265, 62), (298, 418), (298, 447), (298, 536), (299, 369), (299, 583), (269, 139), (269, 142), (269, 150), (269, 167), (269, 169), (263, 113))),
    ('paper/transport_followup_appendix.tex', '4'):
        ('math-constant', 2, _u((299, 140), (263, 148))),
    ('paper/transport_followup_appendix.tex', '4096'):
        ('protocol-constant', 1, _u((263, 523))),
    ('paper/transport_followup_appendix.tex', '50'):
        ('protocol-constant', 1, _u((263, 883))),
    ('paper/transport_followup_appendix.tex', '90'):
        ('protocol-constant', 1, _u((246, 389))),
    ('paper/transport_followup_appendix.tex', '95'):
        ('protocol-constant', 1, _u((246, 707))),
    # paper/transport_proofs.tex
    ('paper/transport_proofs.tex', '0'):
        ('math-constant', 22, _u((99, 304), (94, 162), (94, 213), (92, 165), (150, 554), (150, 609), (93, 80), (93, 101), (245, 174), (245, 232), (245, 742), (108, 65), (173, 335), (173, 454), (146, 88), (146, 91), (292, 1260), (135, 172), (105, 29), (105, 270), (105, 346), (105, 359))),
    ('paper/transport_proofs.tex', '0,1'):
        ('interval-endpoint', 1, _u((92, 179))),
    ('paper/transport_proofs.tex', '1'):
        ('math-constant', 95, _u((188, 114), (206, 18), (99, 17), (99, 284), (99, 293), (178, 42), (120, 127), (152, 546), (92, 235), (92, 291), (141, 121), (150, 383), (150, 455), (150, 485), (150, 572), (149, 130), (149, 154), (149, 175), (149, 192), (149, 248), (149, 273), (149, 296), (149, 507), (149, 539), (149, 566), (149, 599), (149, 707), (149, 772), (143, 86), (153, 299), (153, 464), (153, 491), (145, 181), (209, 16), (243, 48), (243, 56), (243, 150), (243, 179), (243, 188), (243, 349), (243, 424), (140, 68), (140, 207), (140, 305), (142, 134), (142, 549), (142, 556), (148, 521), (148, 599), (66, 2), (67, 4), (114, 18), (114, 398), (114, 428), (245, 107), (245, 368), (245, 531), (245, 573), (245, 627), (147, 110), (147, 642), (173, 151), (171, 190), (171, 419), (292, 352), (292, 364), (292, 402), (292, 919), (292, 923), (292, 1090), (292, 1330), (292, 1401), (292, 1741), (292, 1892), (144, 108), (144, 141), (144, 153), (144, 421), (144, 431), (182, 58), (182, 118), (183, 99), (111, 31), (111, 55), (111, 178), (139, 234), (139, 247), (139, 298), (139, 374), (139, 417), (139, 432), (97, 17), (97, 342), (98, 529), (98, 670))),
    ('paper/transport_proofs.tex', '2'):
        ('math-constant', 161, _u((189, 55), (189, 93), (188, 116), (208, 44), (208, 80), (206, 103), (99, 134), (99, 181), (99, 204), (99, 232), (99, 244), (99, 335), (99, 346), (99, 363), (99, 380), (178, 55), (178, 78), (178, 88), (152, 226), (152, 251), (92, 283), (150, 385), (150, 457), (150, 487), (149, 132), (149, 156), (149, 177), (149, 194), (149, 250), (149, 275), (149, 385), (149, 509), (149, 541), (149, 555), (149, 568), (149, 601), (149, 630), (149, 709), (143, 109), (143, 230), (143, 239), (143, 251), (143, 353), (143, 366), (153, 99), (153, 123), (153, 139), (153, 168), (153, 222), (153, 253), (153, 277), (153, 305), (153, 466), (153, 493), (145, 183), (207, 73), (209, 103), (243, 182), (243, 532), (140, 58), (140, 167), (140, 176), (140, 316), (140, 336), (142, 122), (142, 130), (142, 327), (142, 336), (142, 438), (142, 477), (142, 486), (148, 248), (148, 258), (148, 281), (148, 293), (148, 304), (148, 368), (148, 504), (148, 528), (148, 564), (148, 596), (148, 632), (93, 141), (93, 209), (66, 26), (67, 26), (114, 155), (114, 166), (114, 193), (114, 221), (114, 251), (107, 203), (245, 210), (245, 288), (245, 295), (245, 499), (245, 525), (245, 575), (245, 667), (245, 703), (245, 725), (245, 732), (151, 117), (151, 121), (151, 149), (108, 14), (108, 76), (108, 87), (108, 107), (108, 223), (147, 127), (147, 169), (147, 198), (147, 406), (147, 432), (173, 371), (173, 498), (171, 169), (171, 242), (171, 298), (172, 100), (172, 247), (146, 67), (146, 69), (146, 142), (146, 144), (146, 232), (146, 235), (146, 249), (146, 252), (292, 320), (292, 361), (292, 407), (292, 415), (292, 418), (292, 584), (292, 594), (292, 633), (292, 636), (292, 698), (292, 708), (292, 747), (292, 750), (292, 917), (292, 1164), (292, 1395), (292, 1434), (292, 1440), (292, 1483), (292, 1493), (292, 1539), (292, 1605), (292, 2105), (183, 127), (111, 225), (139, 271), (139, 322), (97, 42), (97, 72), (97, 113), (97, 245))),
    ('paper/transport_proofs.tex', '3'):
        ('math-constant', 2, _u((172, 103), (172, 218))),
    ('paper/transport_proofs.tex', '4'):
        ('math-constant', 13, _u((142, 431), (142, 441), (148, 642), (245, 522), (147, 441), (173, 41), (172, 92), (172, 170), (146, 193), (292, 372), (292, 1533), (292, 1879), (292, 1935))),
    ('paper/transport_proofs.tex', '8'):
        ('math-constant', 1, _u((173, 281))),
    # paper/transport_protocol_appendix.tex
    ('paper/transport_protocol_appendix.tex', '2'):
        ('math-constant', 1, _u((260, 200))),
    # paper/transport_support_appendix.tex
    ('paper/transport_support_appendix.tex', '0'):
        ('math-constant', 2, _u((13, 10), (124, 71))),
    ('paper/transport_support_appendix.tex', '1'):
        ('math-constant', 20, _u((0, 2), (0, 13), (12, 8), (5, 1), (130, 1), (262, 43), (184, 31), (184, 71), (240, 29), (211, 67), (211, 87), (211, 103), (211, 113), (221, 15), (221, 36), (83, 9), (227, 45), (219, 29), (124, 195), (124, 231))),
    ('paper/transport_support_appendix.tex', '10'):
        ('document-structure', 1, _u((230, 21))),
    ('paper/transport_support_appendix.tex', '13'):
        ('document-structure', 1, _u((232, 21))),
    ('paper/transport_support_appendix.tex', '16'):
        ('document-structure', 2, _u((234, 21), (234, 21))),
    ('paper/transport_support_appendix.tex', '2'):
        ('math-constant', 13, _u((184, 41), (184, 81), (240, 21), (211, 22), (211, 32), (211, 79), (211, 171), (221, 6), (82, 57), (227, 39), (228, 33), (228, 43), (219, 6))),
    # paper/transport_theory.tex
    ('paper/transport_theory.tex', '0'):
        ('math-constant', 33, _u((95, 14), (95, 53), (104, 14), (187, 33), (132, 121), (132, 136), (166, 9), (100, 63), (157, 158), (157, 249), (157, 260), (284, 132), (185, 57), (185, 104), (237, 15), (17, 0), (17, 0), (17, 0), (17, 0), (17, 0), (17, 0), (154, 200), (101, 71), (121, 81), (192, 38), (133, 516), (155, 113), (155, 327), (195, 73), (195, 154), (156, 86), (136, 191), (159, 99))),
    ('paper/transport_theory.tex', '0,1'):
        ('interval-endpoint', 5, _u((137, 78), (154, 78), (101, 63), (101, 102), (91, 15))),
    ('paper/transport_theory.tex', '1'):
        ('math-constant', 84, _u((164, 10), (76, 25), (75, 22), (74, 24), (177, 63), (177, 90), (177, 106), (191, 116), (259, 127), (65, 9), (65, 34), (65, 67), (181, 78), (201, 68), (201, 88), (222, 15), (222, 36), (204, 68), (220, 15), (220, 36), (239, 134), (239, 202), (239, 269), (199, 69), (199, 94), (199, 115), (85, 203), (18, 0), (157, 296), (162, 81), (284, 146), (284, 176), (284, 204), (138, 241), (179, 58), (179, 74), (179, 103), (185, 70), (158, 356), (158, 365), (237, 22), (163, 23), (163, 52), (14, 80), (14, 189), (175, 59), (175, 90), (101, 99), (101, 242), (101, 378), (194, 43), (121, 46), (203, 31), (193, 55), (193, 82), (193, 115), (238, 20), (238, 55), (236, 204), (210, 67), (210, 97), (210, 118), (73, 12), (81, 17), (81, 26), (131, 120), (113, 70), (113, 131), (113, 158), (176, 71), (133, 793), (133, 858), (235, 25), (87, 98), (87, 219), (195, 55), (195, 136), (244, 11), (244, 19), (244, 22), (297, 432), (297, 574), (297, 727), (297, 731))),
    ('paper/transport_theory.tex', '1,0'):
        ('math-constant', 1, _u((157, 227))),
    ('paper/transport_theory.tex', '1,2'):
        ('math-constant', 1, _u((156, 297))),
    ('paper/transport_theory.tex', '11'):
        ('document-structure', 1, _u((231, 21))),
    ('paper/transport_theory.tex', '16'):
        ('document-structure', 1, _u((234, 21))),
    ('paper/transport_theory.tex', '2'):
        ('math-constant', 105, _u((72, 19), (165, 9), (241, 4), (242, 12), (177, 117), (177, 128), (65, 36), (65, 69), (197, 68), (181, 164), (201, 23), (201, 33), (201, 80), (201, 160), (222, 6), (204, 23), (204, 33), (204, 81), (204, 90), (204, 94), (220, 6), (198, 4), (198, 26), (199, 4), (199, 24), (199, 34), (199, 81), (199, 85), (190, 62), (157, 312), (157, 378), (284, 206), (284, 231), (179, 76), (179, 105), (158, 358), (158, 367), (163, 25), (163, 54), (14, 101), (14, 122), (14, 168), (14, 204), (175, 92), (101, 177), (101, 380), (134, 116), (174, 58), (180, 122), (165, 9), (202, 40), (242, 12), (203, 42), (193, 57), (193, 84), (205, 28), (210, 22), (210, 32), (210, 79), (210, 84), (210, 88), (186, 78), (186, 86), (186, 88), (73, 23), (81, 20), (223, 81), (176, 82), (176, 102), (200, 4), (235, 19), (224, 12), (224, 21), (226, 25), (226, 35), (225, 21), (79, 21), (212, 14), (68, 8), (68, 39), (106, 14), (106, 35), (106, 158), (155, 246), (155, 307), (77, 21), (77, 58), (78, 21), (78, 58), (196, 38), (196, 73), (96, 164), (244, 108), (244, 145), (156, 187), (156, 315), (156, 338), (159, 178), (159, 186), (159, 189), (297, 416), (297, 467), (297, 475), (297, 478), (297, 544))),
    ('paper/transport_theory.tex', '3'):
        ('math-constant', 2, _u((106, 52), (106, 161))),
    ('paper/transport_theory.tex', '4'):
        ('math-constant', 9, _u((133, 780), (225, 12), (106, 49), (106, 150), (96, 212), (136, 214), (159, 114), (159, 150), (297, 440))),
    # submissions/tmlr_2026/main.tex
    ('submissions/tmlr_2026/main.tex', '14'):
        ('document-structure', 1, _u((233, 21))),
    # submissions/tmlr_2026/supplement_README.md
    ('submissions/tmlr_2026/supplement_README.md', '1.15.2'):
        ('environment-version', 1, _u((123, 43))),
    ('submissions/tmlr_2026/supplement_README.md', '2.2.3'):
        ('environment-version', 1, _u((123, 27))),
    ('submissions/tmlr_2026/supplement_README.md', '3.12'):
        ('environment-version', 1, _u((123, 11))),
}

#: path -> SHA-256 of the whole normalized auditable text
FILE_PINS: dict[str, str] = {
    'README.md':
        '27d3ebdcbb6837d77545890cee27ec7a87442c415987e9a4f6723279176ecb47',
    'paper/availability.tex':
        '8a3abe9088168fe967b620101c8285084e49e2d8d5f733997fbc22775c141565',
    'paper/body_conclusion.tex':
        '5a4904497ef0c4ddd70270cff542aa2d4fa5245fb37a9bb0daa5c64e3a6ace54',
    'paper/body_intro.tex':
        '0c9f0a6c4078ca5160871266e65fb9e9a328274f8d6a7302c32f595be8163b92',
    'paper/body_related.tex':
        'fb4e967a31a0f371ed8593d10d3bf33da62fdc0d7b178a20494c9120d7bdc3fb',
    'paper/broader_impact.tex':
        '41c44900a31c1d4274da9f69facd14255cfc61108c1ec592805208be3b8c0605',
    'paper/figures/transport_conceptual_geometry.tex':
        '8939eab6c15a186346f16afd231a52d1a2f7ec32c160e064663477339f138066',
    'paper/figures/transport_conceptual_interfaces.tex':
        '8887badd9f997fd3ac84d6affc65f0e44150b46bbedc3c9d45c66dec57e2a2c4',
    'paper/legacy_scope.tex':
        'be156968b1bdb7a14e7451e7c45d747f5b5586fc6be2101ede15cd829f3b542a',
    'paper/macros.tex':
        '1129bd91c4ad4afdfb620e562fea7a496deca6dd9f9aab3900eda0855380323f',
    'paper/notation.tex':
        '147f3df725e99301e703b0f5e248534c0b5d08b52b8b287434c43c2b0917bc0c',
    'paper/scope_limitations.tex':
        '279eb8db066e09f3005e016411880b85d2a8c8caafbf13c72307010a688f3a0e',
    'paper/transport_experiment.tex':
        'ef99c6d6e08deb5c15b76b4a2dcfd0e1aed5050d73eb43e84add0eba4c0cdd1f',
    'paper/transport_experiment_appendix.tex':
        'f399e3e3a5f7fb00e4d2fe5bb046203d8e00b397908dc643f5ef95edb91e8bf4',
    'paper/transport_followup.tex':
        '689f84803f7f75849b356b5a5876a57aa31cb1d3785bf09023dc87b04da3d675',
    'paper/transport_followup_appendix.tex':
        '2a05716bd8ba523da237a3c106d95b24c3a44008b21b439b2117e2811dbb216e',
    'paper/transport_proofs.tex':
        '11ff45a36fb390d00df68f1c891cc89e70303511aa4f9fc06a6203c089d54402',
    'paper/transport_protocol_appendix.tex':
        'e7407e79bdd23ce3fdbac777de2ced313717f42a4b5e9bc9c06f34e524ef7897',
    'paper/transport_support_appendix.tex':
        '8784eda97729d8e6c789a94d6d5acf5bbe8d6aa9189b72ec8f6ce9d0b2d267a4',
    'paper/transport_theory.tex':
        '595105e2b98c5b38385e534cd8c51e6eaba8b324df0c034842f191c7fa940494',
    'submissions/tmlr_2026/main.tex':
        '5e591dc6ce8aa24d23c996ab0648306648600a00eca9c6d18e89b893ab74274f',
    'submissions/tmlr_2026/supplement_README.md':
        '6fe32ceabbdb6f3bd8eb265dec7349916e4628ab745ea97955813aa253e88884',
}
