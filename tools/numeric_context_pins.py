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
    '**That file is a claim, not an authority, and the tooling treats it that way.** `tools/anonymous_package_contract.py` pins the whole contract in code: the exact two paths, the field name, the placeholder, the original and sanitized         digests, the exact byte counts, the exact sidecar text, and the exact schema and record set of the declaration. Every check measures this supplement against those constants, and `ANONYMIZATION.json` is then validated against them too. So editing a packaged file, recomputing its sidecar and updating the declaration to match does not produce a passing supplement -- it produces three failures. Nor does deleting the declaration: every shipped checker takes a `--require-package` flag, `verify.sh` passes it and also exports `CCE_REQUIRE_ANONYMOUS_PACKAGE=1`, and in that mode a missing declaration is a failure rather than a fallback to repository semantics.',
    ', \\] so $\\mathcal D(\\bV)=d_{\\rm Th}(\\bVbar,\\bV)=D$. For $q_1=e_1$, $\\bar s(q_1)=1$ and $s(q_1)=e^{-D/2}$, so $\\bar s=e^{D/2}s$ is attained. For $q_2=e_2$, $s(q_2)=e^{D/2}$ and $\\bar s(q_2)=1$, so $s=e^{D/2}\\bar s$ is attained. Thus each one-way factor is sharp, and a uniform argument based only on the symmetric Thompson-distance bound cannot improve the resulting round-trip factor $e^D$. This is a metric-factor sharpness statement, not a contextual-bandit regret lower bound and not a claim that every trajectory attains the worst case.',
    "- **Raw per-run trajectories are not included.** They were never part of the distributed material: the full grid is 2,400 trajectories and the raw tree is far larger than the supplement limit. The aggregate carries a complete         inventory of every raw input it consumed, so the inventory's structure and digests are checkable, but the bytes those digests name are absent. The ledger reports that as NOT EXECUTED, not as a pass. - **The deterministic paired bootstrap is therefore not recomputable here.** It resamples per-seed totals. Its algorithm, level, resample count and derived child seeds are all recorded in the aggregate; no per-seed values are synthesized to fake the recomputation. - **Re-running the study from scratch is not a one-command operation.** The full grid is a multi-hour, multi-process job. `experiments/run_transport_instantiation_study.py` is included so the protocol can be read and executed, not because a reviewer is expected to run it.",
    '0',
    "0. **Anonymous-package contract, required (a gate, not a result).** `python3 tools/anonymous_package_contract.py --root . --require-package` Checks this supplement against the constants pinned in shipped code: the sanitized digests and byte counts, the redacted field's placeholder, the sidecar text, and the declaration's schema and record set. Nothing here reads an expectation out of `ANONYMIZATION.json`. If it fails, `verify.sh` exits nonzero immediately and the remaining checks are not run, because they would otherwise report on bytes this supplement does not vouch for.",
    '1. **Numerical-provenance ledger.** `python3 tools/verify_tmlr_submission_numbers.py --require-package` Every number the paper states about this study is listed once with its source file and        , its selector, unit, aggregation rule, population, unrounded value and display rounding. The tool re-derives each value from the locked aggregate, checks it rounds to the printed literal, and checks the literal really occurs in the manuscript file it is attributed to.',
    '2. **Artifact regeneration.** `python3 tools/transport_artifact_expectations.py --root . --require-package` Regenerates all 21 published tables, figures and CSVs from the packaged aggregate and requires byte equality with the committed copies. It first checks `ANONYMIZATION.json` against the files it describes, and it stamps the artifacts with the declared original-evidence digest, which is the digest the published artifacts and their provenance records actually carry.',
    '3. **        sidecars for every shipped evidence file.** Walks `paper/tables/`, `paper/figures/` and `results/derived/` as they actually arrive in this archive and checks each file against its sidecar. A file that ships without a sidecar is a failure, so the coverage is of the archive rather than of a list written in advance. This is what covers the one typeset table that is not generated from the aggregate (`tables/growing_window_pareto.tex`, whose cells are asymptotic rates, not measurements). The files the pinned contract already verifies from constants in shipped code are counted separately and skipped here; that is where the two `.provenance.json` records are checked, byte for byte and for whether they still name the digest of the artifact they describe.',
    "4. **Study tests.** `python3 -m pytest -q experiments/tests` The three transport-instantiation modules: the study's own algebra and seed-derivation tests, the aggregation tests, and the artifact tests.",
    ':=\\int_0^1\\!\\left\\| \\bV_t(\\tau)^{-1/2}\\dot\\bV_t(\\tau)\\bV_t(\\tau)^{-1/2} \\right\\|_{\\rm op}d\\tau',
    '=-\\frac{2}{\\sqrt W}\\operatorname{sech}^2(u)\\tanh(u) \\phi(z)\\phi(z)^\\top.',
    '=2\\sqrt{P_T\\sum_{t=1}^T(\\beta_t^{\\rm corr})^2}-B_T^{\\rm base},',
    '=2\\sqrt{P_T\\sum_{t=1}^T(\\beta_t^{\\rm stat})^2},',
    '=2\\sum_{t=1}^Tb_t(a_t).',
    '=\\bVbar_t+\\sigma^{-2}\\bq_t(a_t)\\bq_t(a_t)^\\top, \\label{eq:reference-update-new}',
    '=\\bVbar_t^{-1}\\sigma^{-2}\\sum_{s<t}\\bq_s(a_s)y_s. \\label{eq:frozen-ridge-new}',
    '=\\bq_t(a)^\\top\\Calg_t^{-1}\\bq_t(a).',
    '=\\bq_t(a)^\\top\\bV_t^{-1}\\bq_t(a),',
    '=\\bq_t(a)^\\top\\bVbar_t^{-1}\\bq_t(a),',
    '=\\operatorname{sech}^2(u)\\phi(z),',
    '=\\sqrt{P_T\\sum_{t=1}^T(\\beta_t^{\\rm corr})^2 (1+e^{\\bar D_t^Q})^2}-B_T^{\\rm base}-B_T^{\\rm hist},',
    '=\\sqrt{\\gamma_{t-1}+2\\log(1/\\delta)}+\\sqrt\\lambda S',
    '=\\sum_{s<T}[\\epsilon_{\\rm lin}(s)+\\epsilon_{\\rm mis}(s)]^2,',
    '=\\sum_{t=1}^T [\\epsilon_{\\rm lin,t}(a_t)+\\epsilon_{\\rm mis,t}(a_t)].',
    "All quantities are evaluated on this policy's own selected history. No path, current-metric, or operator certificate is needed for this score. If its reference-confidence event has probability at least $1-\\delta$, so does this guarantee.",
    'Consequently, $W=\\Omega(T)$ with a sufficiently large problem-dependent constant keeps $D_{T,W}=O(1)$. For fixed $d$ and fixed problem constants, \\[ R_T=O(d\\sqrt T\\log T)+O(\\sqrt T). \\] This conclusion requires no $D_t<1$ condition. Here $W$ is an abstract near-linearity scale, not generic network width or parameter count, and the result is not an unrestricted neural-training theorem. No optimizer-residual rate is required because the corrected center is used.',
    'Exact current curvature has $\\kappa_{-,t}=\\kappa_{+,t}=1$. More generally, the operational relative-error certificate',
    'Fix $\\delta\\in(0,1)$. Let $\\rho_s^\\circ$ be the Taylor remainder of $\\mu_{\\btheta^\\circ}$ around $\\btheta_s$, and supply envelopes',
    'For squared loss, the corrected center makes this chain independent of nonlinear optimizer convergence. The representation may follow any predictable path inside the certified region, while historical error, current bias, transport, operator distortion, solver accuracy, and approximate score maximization remain explicit charges. The construction reduces to the usual LinUCB determinant-potential argument for frozen linear features and exact solves. Under the assumptions of \\Cref{cor:global-near-linear-new}, for fixed $d$ and fixed problem constants, taking $W=\\Omega(T)$ with a sufficiently large problem-dependent constant yields $R_T=O(d\\sqrt T\\log T)+O(\\sqrt T)$ without requiring $D_t<1$. Here $W$ is an abstract smoothness scale, not generic network width.',
    'Here $\\lambda>0$ and $\\sigma>0$. Define the corresponding widths',
    'Let $\\bu=\\Calg^{-1}\\bq$. Since $s_{\\Calg}^2=\\bq^\\top\\bu=\\|\\bu\\|_{\\Calg}^2$, \\[ \\left|\\bq^\\top\\tilde\\bu-s_{\\Calg}^2\\right| =\\left|\\langle\\bu,\\tilde\\bu-\\bu\\rangle_{\\Calg}\\right| \\le\\|\\bu\\|_{\\Calg}\\|\\tilde\\bu-\\bu\\|_{\\Calg} \\le\\varepsilon s_{\\Calg}^2. \\] This proves the pointwise two-sided quadratic-form comparison. Dividing its lower side by $1-\\varepsilon$ gives upper validity for this query, while combining both sides gives the displayed sharpness factor. Applying the lower inequality actionwise on the simultaneous family event gives the all-domain upper condition; only the played query uses the upper inequality for sharpness. For PCG the argument is unchanged once the certificate is expressed in the original $\\Calg$-energy norm.',
    'Let $\\mathcal J$ be a finite or countable certificate-source index set. For $j\\in\\mathcal J$, choose an $\\cHist_t^-$-measurable failure budget $\\delta_{j,t}$ before drawing its random object. Let $\\mathcal P_{j,t}$ be the pre-reward sigma-algebra immediately before that draw. It may equal $\\cHist_t^-$ for a round-start draw or include the selected action and earlier randomness for a post-selection check. It is sufficient that \\[ \\Pr(\\mathcal E_{j,t}^c\\mid\\mathcal P_{j,t})\\le\\delta_{j,t}, \\qquad \\sum_{j\\in\\mathcal J}\\sum_{t=1}^T\\delta_{j,t} \\le\\delta_{\\rm cert}\\quad\\text{almost surely}. \\] The tower property and a union bound give simultaneous validity at least $1-\\delta_{\\rm cert}$ without independence. Countability makes the joint event measurable, the nonnegative double sum well-defined, and the union bound valid. On an uncountable score domain, the solver upper event must already be simultaneous. A pointwise certificate cannot be union-bounded after adaptive selection unless it is separately verified at the selected action with the correct conditioning. Realized terminal spectral quantities may be used for post-hoc analysis, but they cannot be inserted into an earlier action-time radius unless a predictable prefix envelope was supplied at that time.',
    'Let $c_t=\\beta_t[1+\\alpha_te^{\\bar D_t} \\sqrt{\\kappa_{+,t}/\\kappa_{-,t}}]$. Summation and one Cauchy--Schwarz application give \\[ R_T-2\\sum_tb_t(a_t)-\\sum_t\\xi_t \\le\\sqrt{\\sum_tc_t^2}\\sqrt{\\sum_t\\bar s_t^2(a_t)}. \\] Since $\\bar s_t^2(a_t)\\le G^2/\\lambda$, the scalar inequality $x\\le(1+M)\\log(1+x)$ for $0\\le x\\le M$, with $x=\\sigma^{-2}\\bar s_t^2(a_t)$ and $M=G^2/(\\lambda\\sigma^2)$, yields',
    'More generally, suppose there is a measurable function $\\nu_t:[0,1]\\to[0,\\infty)$ with $\\nu_t\\in L^1([0,1])$ such that \\[ \\dot\\Bmat(\\tau)^\\top\\dot\\Bmat(\\tau) \\preceq\\nu_t(\\tau)^2\\bV(\\tau) \\] almost everywhere. Then $\\mathcal D(\\bV)\\le2\\int_0^1\\nu_t(\\tau)d\\tau$. For nonnegative $\\nu_t$, the displayed PSD premise is equivalently the norm condition $\\|\\dot\\Bmat(\\tau)\\bV(\\tau)^{-1/2}\\|_{\\rm op}\\le\\nu_t(\\tau)$ almost everywhere.',
    'Python 3.12 with `numpy` and `scipy` (`experiments/requirements.txt` records the versions the study declared: NumPy 2.2.3, SciPy 1.15.2). `pytest` is needed only for the test suite. Nothing else is required, and nothing downloads anything.',
    'Retraining a contextual-bandit model changes the gradient features used to score actions, while sequential confidence rests on features fixed when rewards were collected. We study when this confidence can justify scores based on current relinearized generalized Gauss--Newton or Fisher curvature. Our conditional upper-confidence-bound theorem separates the frozen confidence metric, current metric, applied operator, and numerical solver width. It composes a Thompson--Finsler path certificate, a two-sided operator comparison, and a solver certificate to bound regret through frozen sequential information gain, allowing measurable approximate selection on standard-Borel action spaces. For differentiable squared-loss models, a corrected prediction center establishes reference confidence along any predictable parameter path inside the certified region, without assuming nonlinear optimizer convergence. Historical approximation errors enter the radius; current errors remain additive. A controlled audit of a 29-parameter scaled-tanh model uses dense matrices and Cholesky solves. All 600 transport-Hessian runs retain simultaneous float64 confidence and optimism, with no deterministic audit failure. However, the analytic path certificate exceeds the endpoint distance by five to six orders of magnitude, every reported numerical regret bound exceeds the deterministic cap, and all three comparison policies attain lower sample-mean pseudo-regret at the primary horizon. The base confidence component dominates the recorded bound decomposition. These findings separate certificate validity from bound tightness and policy performance; they establish no uniform regret ordering or practical curvature advantage.',
    'Set $\\gamma_0=0$, and define',
    'Set $\\hat s=\\sqrt{U}$. If $L>0$, the observable factor $\\alpha=\\sqrt{U/L}$ verifies played-action sharpness. If $L\\le0<U$, the interval supplies no finite positive multiplicative sharpness factor; the solve must continue or an additive-width theorem must be used. If $U=0$, the exact inverse quadratic form is zero and the solver returns $\\hat s=0$. For $\\bq=0$, skip the solve and return zero.',
    'Since $\\sup_u|2\\operatorname{sech}^2(u)\\tanh(u)|=4/(3\\sqrt3)$, \\Cref{cor:global-near-linear-new} applies with \\[ G=B_\\phi,\\qquad c_\\mu=c_g=c_h:=\\frac{4B_\\phi^2}{3\\sqrt3}. \\] The symbol $W$ is a smoothness scale here; it is not identified with hidden width or parameter count.',
    'The check that the redaction did not touch the numbers is step 2 below. The published tables, figures and CSVs are regenerated **from the packaged aggregate** and must come out byte-identical to the committed copies. They could not, if the redaction had perturbed anything they depend on.',
    'The controlled scaled-tanh audit uses dense current matrices and direct Cholesky solves in float64. All 600 transport-Hessian trajectories retained simultaneous reference confidence and transported optimism, and the locked grid recorded no deterministic audit failure. Yet the analytic path certificate exceeded the endpoint distance by five to six orders of magnitude in the reported medians, every reported theorem bound was vacuous relative to the deterministic cap, and the three comparison policies had lower sample mean regret at the primary horizon. The recorded decomposition is dominated by the base confidence component, which includes the regularization/norm-bound term; transport inflation alone does not explain the vacuity. These are findings about this certificate, environment, and horizon. Comparable worst-case guarantees do not order the realized regret of policies that generate different trajectories.',
    'The earlier experiments did not execute the transported score or record its path, operator, and solver certificates. They therefore provide no evidence for the current theorem or its numerical performance. The present paper makes no empirical claim for a large neural model, an approximate operator, or an iterative solver: its reported study uses a 29-parameter model and dense Cholesky solves. These exclusions do not change the conditional operator and solver interfaces proved in the theorem.',
    'The exact solution is $\\Calg^{-1}\\bq=\\tilde\\bu+\\Calg^{-1}\\br$. Substitute this expression and $\\bq=\\Calg\\tilde\\bu+\\br$ into the quadratic form. The remainder is $\\br^\\top\\Calg^{-1}\\br$, which lies between zero and $\\|\\br\\|_2^2/\\lambda_{\\Calg}$.',
    "The existing cumulative decomposition in \\Cref{fig:transport-instantiation-bound} separates base confidence, historical linearization, path inflation, and current bias. At $T=1000$, the base component accounts for $79.4\\%$--$97.3\\%$ of the mean terminal sharp right-hand side across target cells; path inflation accounts for $2.0\\%$--$16.3\\%$. Each percentage divides a component's mean over the 50 transport-Hessian trajectories by the mean sharp right-hand side over those same trajectories. These are ratios of means, not medians of runwise shares. The base component alone has cell means of about $9{,}948$--$10{,}010$, already above the cap $2{,}000$. It includes the statistical and regularization/norm-bound terms together with the determinant-potential and Cauchy--Schwarz factors; its size cannot be attributed to the confidence radius alone. Thus most of the bound's size on this grid is present before path inflation is added. This is a decomposition along transport-Hessian histories, not a bound evaluated on the frozen-reference policy's different histories. The appendix defines the components and reports the complete tightness table.",
    "The following reproducibility limits remain. First, the raw per-run trajectory files are not distributed: they are large and were never committed, so the detached verifier checks the aggregate's inventory structure and digests but cannot verify the raw bytes those digests name, and the verifier labels those checks accordingly instead of reporting them as passes. Consequently the deterministic paired bootstrap, which resamples per-seed values, is not recomputable from the retained aggregate alone; its algorithm, level, resample count and derived child seeds are recorded, and no per-seed values are synthesized in their place. Second, the inspected historical research snapshot specifies SciPy 1.15.2 in its dependency requirements but retains a host-specific SciPy 1.13.1 wheel link. These historical records do not establish a single matched runtime for the study. The portable dependency lock prepared for new runs does not recover the runtime used to generate the historical evidence. Two selection-time source files, the artifact renderer and the Buck build declaration, also differ from their recorded source digests. The verifier records both divergences explicitly; verifying the retained outputs does not restore the selection-time source tree. These dependency and source provenance limitations are distinct from agreement between the manuscript and the locked aggregate.",
    'The historical deterministic term in \\eqref{eq:beta-corrected-new} follows from $\\Phi_t^\\top\\bVbar_t^{-1}\\Phi_t\\preceq I$ for $\\Phi_t=[\\bq_1/\\sigma,\\ldots,\\bq_{t-1}/\\sigma]$. Its scaling is $1/\\sigma$, not $1/\\sigma^2$. Fixed nonvanishing misspecification generally creates a linear current-bias term and can also make the historical radius vacuous. This is a graceful-degradation statement, not a robust misspecified-bandit guarantee.',
    'The locked experiment audits the exact-current specialization in a 29-parameter scaled-tanh model with dense current and frozen matrices and direct Cholesky solves in float64. Approximate operators and CG are not evaluated. All declared confidence and optimism diagnostics pass, but the analytic path envelope is highly conservative, the numerical regret bound is vacuous, and all three comparison policies have lower sample mean regret in the reported primary-horizon conditions (\\Cref{sec:transport-instantiation}). The recorded decomposition shows that the base confidence component dominates the bound, so the observed vacuity cannot be attributed to transport inflation alone.',
    'The locked grid contains horizons $T\\in\\{250,500,1000\\}$, 50 evaluation seeds, and target labels $D_{\\rm target}\\in\\{0.25,0.5,1,2\\}$. Each $(T,D_{\\rm target})$ cell is a separately executed model condition because both quantities enter the rule for $W$. The target label is neither realized transport distance nor generic network width, so trends across targets are not a dose response to certificate inflation. The four policies share contexts and potential-noise tables. The primary \\emph{transport Hessian} policy uses $\\bar D_t^Q$ in the score. The \\emph{transport endpoint} policy replaces it by the dense endpoint Thompson distance computed from the learner-known matrices $\\bVbar_t$ and $\\bV_t$ before the reward is observed; it is a dense diagnostic comparator. The \\emph{frozen reference} policy uses the frozen width directly. The \\emph{naive current} policy omits transport and is intentionally uncertified. Each policy has its own selected history and representation path. Ten disjoint tuning seeds selected learning rate $3\\times10^{-4}$ and 20 full-batch steps followed by projection each round by preregistered all-action prediction MSE; evaluation seeds never entered that selection. The environment was not filtered after generation. Within each $T=1000$ target cell, the 50-seed means round to optimal-action entropy $1.579$, optimality gap $0.123$, best-fixed-action regret $180.4$, and online context-free mean-only regret $185.4$. All five actions are optimal somewhere in every evaluation stream. Entropy is measured in nats; its maximum for five actions is $\\log 5\\approx1.609$, so the mean entropy is close to its uniform-action maximum. These diagnostics were reported after the grid was fixed; they were not used to select seeds.',
    'The previous additive stacked-design result remains a useful local corollary. If $\\chi_t<1$ and',
    "Their sum equals the sharp right-hand side in \\eqref{eq:sharp-transport-regret-new} for the experiment's $\\alpha_t=\\kappa_{-,t}=\\kappa_{+,t}=1$ and $\\xi_t=0$. The differences retain the same trajectory and the same potential factor; they do not rerun a policy with a component removed. The committed figure CSVs report the mean of each component over 50 primary-policy trajectories at each round. At $T=1000$, dividing those terminal component means by the corresponding mean sharp right-hand side gives base shares $97.33\\%,94.66\\%,89.39\\%,79.39\\%$ and path shares $2.01\\%,4.04\\%,8.16\\%,16.27\\%$ for $D_{\\rm target}=0.25,0.5,1,2$, respectively. These joint cumulative quantities establish the decomposition; marginal medians of $e^{\\bar D_t^Q/2}$ do not determine it.",
    'This appendix expands the locked full aggregate summarized in \\Cref{sec:transport-instantiation}. The experiment protocol, configuration, selection record, aggregate, and every generated artifact carry provenance and         hashes. The figures use only the 50 evaluation seeds. Smoke and tuning results are absent.',
    'This proves \\eqref{eq:sharp-transport-regret-new}. Finally, $\\alpha_te^{\\bar D_t}\\sqrt{\\kappa_{+,t}/\\kappa_{-,t}}\\ge1$, hence $1+x\\le2x$ gives \\eqref{eq:simple-transport-regret-new}. The probability statement follows by a union bound; independence is not required.',
    'This remains valid when $\\bar D_t\\ge1$. At $t=1$, the factor has zero rows, $Q_1=0$, and both metrics equal $\\lambda\\bI$.',
    'We next instantiate the reference-confidence interface. The corrected center keeps statistical estimation in the predictable collection-time features while using the current nonlinear prediction as its anchor. The resulting identity does not assume that the representation parameter minimizes a nonlinear loss. Let $\\sigma>0$ and let the reward obey $r_t=\\mu_t^*(a_t)+\\eta_t$, where, for every $u\\in\\R$,',
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
    '[Proof of \\Cref{lem:factor-spd-path}] Almost everywhere, $\\dot\\bV=\\dot\\Bmat^\\top\\Bmat+\\Bmat^\\top\\dot\\Bmat$. Put $E=\\dot\\Bmat\\bV^{-1/2}$ and $H=\\Bmat\\bV^{-1/2}$. Then \\[ \\bV^{-1/2}\\dot\\bV\\bV^{-1/2}=E^\\top H+H^\\top E. \\] Moreover, \\[ H^\\top H =\\bV^{-1/2}\\Bmat^\\top\\Bmat\\bV^{-1/2} =\\bI-\\lambda\\bV^{-1}\\preceq\\bI, \\] so $\\|H\\|_{\\rm op}\\le1$. Therefore the normalized SPD speed is at most $2\\|E\\|_{\\rm op}$, which proves \\eqref{eq:factor-path-bound-new} after integration. For the PSD form, congruence by $\\bV^{-1/2}$ gives \\[ \\|\\dot\\Bmat\\bV^{-1/2}\\|_{\\rm op}^2 =\\|\\bV^{-1/2}\\dot\\Bmat^\\top\\dot\\Bmat\\bV^{-1/2}\\|_{\\rm op} \\le\\nu_t(\\tau)^2. \\] Because $\\nu_t(\\tau)\\ge0$, taking square roots gives $\\|\\dot\\Bmat\\bV^{-1/2}\\|_{\\rm op}\\le\\nu_t(\\tau)$ almost everywhere. The assumed $L^1$ integrability permits integration in \\eqref{eq:factor-path-bound-new}.',
    '[Proof of \\Cref{lem:log-spd-path}] Fix $v\\ne0$ and set $f_v(\\tau)=v^\\top\\bV(\\tau)v$. The path is continuous and positive definite on a compact interval, so $f_v$ is absolutely continuous and bounded away from zero. Thus $\\log f_v$ is absolutely continuous and, almost everywhere, \\[ \\frac{d}{d\\tau}\\log f_v(\\tau) =\\frac{v^\\top\\dot\\bV(\\tau)v}{v^\\top\\bV(\\tau)v}. \\] With $w=\\bV(\\tau)^{1/2}v$, the absolute value of this derivative is at most $\\|\\bV(\\tau)^{-1/2}\\dot\\bV(\\tau) \\bV(\\tau)^{-1/2}\\|_{\\rm op}$. Integrating gives \\[ e^{-\\mathcal D(\\bV)}v^\\top\\bV(0)v \\le v^\\top\\bV(1)v \\le e^{\\mathcal D(\\bV)}v^\\top\\bV(0)v. \\] The inequality holds for every $v$, which is exactly \\eqref{eq:log-path-sandwich-new}. Inverting the sandwich gives the corresponding inverse-quadratic-form comparison. The proof never differentiates a matrix square root.',
    '[Proof of \\Cref{prop:width-transport-new}] The logarithmic sandwich and inversion give \\[ \\bar s_t^2(a)\\le e^{\\bar D_t}s_t^2(a),\\qquad s_t^2(a)\\le e^{\\bar D_t}\\bar s_t^2(a). \\] Inverting the operator sandwich gives \\[ s_t^2(a)\\le\\kappa_{+,t}s_{\\Calg,t}^2(a),\\qquad s_{\\Calg,t}^2(a)\\le\\kappa_{-,t}^{-1}s_t^2(a). \\] Composition proves \\eqref{eq:two-way-width-new}. For \\eqref{eq:relative-operator-certificate-new}, congruence gives $-\\varepsilon_t\\bI\\preceq \\bV_t^{-1/2}(\\Calg_t-\\bV_t)\\bV_t^{-1/2} \\preceq\\varepsilon_t\\bI$; undoing the congruence gives the claimed factors.',
    '[Rectangular factor-path certificate] \\label{lem:factor-spd-path} Let $\\Bmat:[0,1]\\to\\R^{m\\times d}$ be absolutely continuous and set $\\bV(\\tau)=\\lambda\\bI+\\Bmat(\\tau)^\\top\\Bmat(\\tau)$, with $\\lambda>0$. Then',
    '[Thompson distance and selected-path length] The integrand in \\eqref{eq:generic-path-length-new} is the classical Thompson Finsler norm on the positive-definite cone \\citep{thompson1963certain,nussbaum1994finsler}. Its endpoint metric is \\[ d_{\\rm Th}(A,B) :=\\inf\\{r\\ge0:e^{-r}A\\preceq B\\preceq e^rA\\}. \\] Equivalently, \\[ d_{\\rm Th}(A,B) =\\left\\|\\log(A^{-1/2}BA^{-1/2})\\right\\|_{\\rm op}. \\] Therefore \\Cref{lem:log-spd-path} gives',
    '\\] Then \\[ \\bV(\\tau)^{-1/2}\\dot\\bV(\\tau)\\bV(\\tau)^{-1/2} =',
    '\\bVbar_{t+1}',
    '\\bar s_t^2(a)',
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
    '\\label{eq:regret-definition-new} \\operatorname{reg}_t :=\\sup_{a\\in\\cA_t}\\mu_t^*(a)-\\mu_t^*(a_t), \\qquad R_T=\\sum_{t=1}^T\\operatorname{reg}_t.',
    '\\label{eq:relative-operator-certificate-new} \\|\\bV_t^{-1/2}(\\Calg_t-\\bV_t)\\bV_t^{-1/2}\\|_{\\rm op} \\le\\varepsilon_t<1',
    '\\label{eq:scalar-factor-path-new} \\sigma^{-1}\\nabla_\\theta\\mu_{\\btheta_s+ \\tau(\\btheta_t-\\btheta_s)}(x_s,a_s)^\\top.',
    '\\label{eq:transported-score-new} U_t(a)=m_t(a) +\\beta_t e^{\\bar D_t/2}\\sqrt{\\kappa_{+,t}}\\,\\hat s_t(a) +b_t(a),',
    '\\le 2\\beta_t\\bar s_t(a_t)+2b_t(a_t)+\\xi_t,\\nonumber',
    '\\le 2\\sqrt{\\left(\\sigma^2+\\frac{G^2}{\\lambda}\\right) \\gamma_T\\sum_{t=1}^T\\beta_t^2} +2\\sum_{t=1}^Tb_t(a_t)+\\sum_{t=1}^T\\xi_t. \\label{eq:frozen-width-regret}',
    '\\le 2e^{D_{T,W}} \\Biggl[',
    '\\le \\sqrt{\\left(\\sigma^2+\\frac{G^2}{\\lambda}\\right)\\gamma_T \\sum_{t=1}^T\\beta_t^2 \\left[1+\\alpha_t e^{\\bar D_t} \\sqrt{\\frac{\\kappa_{+,t}}{\\kappa_{-,t}}}\\right]^2} \\nonumber',
    '\\le e^{\\bar D_t}\\kappa_{+,t}s_{\\Calg,t}^2(a),',
    '\\le e^{\\bar D_t}\\kappa_{-,t}^{-1}\\bar s_t^2(a). \\label{eq:two-way-width-new}',
    '\\le2\\sqrt{\\left(\\sigma^2+\\frac{G^2}{\\lambda}\\right)\\gamma_T \\sum_{t=1}^T\\alpha_t^2\\beta_t^2e^{2\\bar D_t} \\frac{\\kappa_{+,t}}{\\kappa_{-,t}}} \\nonumber',
    '\\le\\beta_t\\!\\left[1+\\alpha_te^{\\bar D_t} \\sqrt{\\frac{\\kappa_{+,t}}{\\kappa_{-,t}}}\\right]\\bar s_t(a_t) +2b_t(a_t)+\\xi_t,',
    '\\le\\beta_t\\bar s_t(a_t) +\\beta_te^{\\bar D_t/2}\\sqrt{\\kappa_{+,t}}\\hat s_t(a_t) +2b_t(a_t)+\\xi_t',
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
    '`paper/tables/` and `paper/figures/` carry the 21 artifacts this study generates, each with its sidecar and provenance record. The earlier symbolic growing-window rate table and nine legacy appendix sources are outside the current manuscript and are not shipped. The older autodiff-GGN and linear-bound benchmark outputs are also excluded: those were designed for an earlier one-sided theorem, do not execute the transported score, and are not evidence for any claim in this paper, so shipping them here would only invite them to be read as if they were. Check 3 below verifies every evidence file that is here.',
    'd_{\\rm Th}(\\bV(0),\\bV(1))',
    'gives $\\kappa_{-,t}=1-\\varepsilon_t$ and $\\kappa_{+,t}=1+\\varepsilon_t$. An upper comparison alone does not imply a lower factor.',
    'holds. The bias envelope enters twice and the approximate-oracle error enters once. If the confidence event has probability at least $1-\\delta$ and the joint certificate event has probability at least $1-\\delta_{\\rm cert}$, these bounds hold with probability at least $1-\\delta-\\delta_{\\rm cert}$.',
    's_t^2(a)',
    's_{\\Calg,t}^2(a)',
    'use the local score obtained from \\eqref{eq:transported-score-new} by replacing $e^{\\bar D_t/2}$ with $1+\\chi_t$.',
    'where $\\Phi_t=[\\bq_1(a_1)/\\sigma,\\ldots, \\bq_{t-1}(a_{t-1})/\\sigma]$. The self-normalized martingale inequality bounds the middle term in $\\bVbar_t^{-1}$ norm by $\\sqrt{\\gamma_{t-1}+2\\log(1/\\delta)}$ simultaneously over $t$. The ridge term is at most $\\sqrt\\lambda S$. Finally, $\\bVbar_t=\\lambda\\bI+\\Phi_t\\Phi_t^\\top$ implies $\\Phi_t^\\top\\bVbar_t^{-1}\\Phi_t\\preceq\\bI$, so \\[ \\left\\|\\frac1\\sigma\\Phi_t e\\right\\|_{\\bVbar_t^{-1}} \\le\\frac{\\|e\\|_2}{\\sigma} \\le\\frac1\\sigma\\sqrt{\\sum_{s<t} [\\epsilon_{\\rm lin}(s)+\\epsilon_{\\rm mis}(s)]^2}. \\] Cauchy--Schwarz in the $\\bVbar_t$ metric bounds $|\\bq_t(a)^\\top(\\btheta^\\circ-\\hat\\btheta_t^{\\rm lin})|$ by $\\beta_t^{\\rm corr}\\bar s_t(a)$.',
    '{Bound nonvacuity.} The cumulative guarantee is vacuous in every reported cell. The median of the per-trajectory terminal sharp-RHS/regret ratios is $126.7$--$155.7$ over the full grid and $126.7$--$135.0$ at $T=1000$. No run has zero regret. Since $|\\mu^*(z)|\\le\\|\\phi(z)\\|\\|\\btheta^\\circ\\|\\le1$, cumulative pseudo-regret has the deterministic cap $2T$. In every cell the theorem bound also exceeds this cap: the median right-hand sides are $3{,}989$--$12{,}607$, versus caps of $500$--$2{,}000$.',
    "{Certificate and bound tightness for the transport-Hessian policy. The reported summary statistics are medians over the following populations. Terminal historical-radius and cumulative current-bias entries, and terminal width/bound ratios summarize 50 runs per cell. Path ratios pool eligible seed--round or seed--checkpoint observations, while $e^{\\bar D_t^Q/2}$ pools all seed--round values. $n_0$ counts denominators at or below the preregistered ratio tolerance that are excluded from that ratio. ``Width/potential'' is the frozen squared-width sum divided by its elliptic-potential upper bound; ``Sharp/simple'' is the sharp cumulative right-hand side divided by the simpler right-hand side.} \\label{tab:transport-instantiation-tightness} \\evidencetabular{@{} >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    }@{}}{ \\input{tables/transport_instantiation_tightness.tex}}",
    "{Certificate tightness.} At $T=1000$, the median of each trajectory's maximum realized $\\bar D_t^Q$ ranges from $0.0486$ to $0.384$ across target cells. The corresponding median of trajectory-maximum endpoint distances ranges from $1.31\\times10^{-7}$ to $8.74\\times10^{-6}$; both summaries have 50 trajectory-level observations per cell. At the 100 declared checkpoints per trajectory, pooling the 5,000 eligible seed--checkpoint ratios gives a median selected factor-path length only $1.20$--$1.22$ times the endpoint distance, while $\\bar D_t^Q$ is $2.51\\times10^5$--$1.88\\times10^6$ times the selected-path diagnostic. The large ratio accompanies extremely small realized metric motion. Measured directly against the endpoint distance rather than against the selected path, the median $\\bar D_t^Q/d_{\\rm Th}$ ratio is $3.07\\times10^5$--$2.24\\times10^6$ at $T=1000$, so the analytic certificate is conservative by five to six orders of magnitude on this grid. The reported median $e^{\\bar D_t^Q/2}$, by contrast, pools all 50,000 seed--round values in a $T=1000$ cell and ranges from $1.02$ to $1.18$ across the four target cells at that horizon; it is not a terminal or run-maximum summary.",
    "{GGN--vector products, Hessian spectral analysis, and influence functions.} Pearlmutter's algorithm \\citep{pearlmutter1994fast} computes exact Hessian--vector products; the analogous GGN--vector product has the same Jacobian-transpose-times-Jacobian-times-vector structure \\citep{schraudolph2002fast}. Recent work on Krylov methods for Hessian spectral analysis \\citep{granziol2026hessian} demonstrates related distributed HVP/Krylov infrastructure at $>10^8$-parameter scale, but does not benchmark the exact per-example GGN operator or end-to-end transported-UCB latency. Influence functions \\citep{koh2017understanding} use inverse-curvature--vector products to attribute predictions to training points. A CG-based realization of our solver interface would use the same implicit-solve primitive. The present experiment uses direct dense solves and makes no matrix-free scalability claim.",
    "{Locked theorem-instantiation audit for the transport-Hessian policy. Coverage is run-level simultaneous coverage with exact Clopper--Pearson intervals. The two median-maximum columns first maximize within each trajectory, then take the median over 50 runs per cell. ``Event viol.'' counts theorem-bound violations only when the joint confidence premise holds. All values come from the full evaluation; smoke and tuning runs are excluded.} \\label{tab:transport-instantiation-validity} \\evidencetabular{@{} >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{     } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    }@{}}{ \\input{tables/transport_instantiation_validity.tex}}",
    '{Mean cumulative pseudo-regret at $T=1000$. Shaded bands are pointwise paired-bootstrap 95\\% intervals over the 50 evaluation seeds, not simultaneous confidence bands. All four methods are plotted; curves can coincide where their selected actions agree.} \\label{fig:transport-instantiation-regret}',
    '{Meaning of the cumulative bound decomposition.} For a transport-Hessian trajectory, write $P_T=(\\sigma^2+G^2/\\lambda)\\gamma_T$ and $\\beta_t^{\\rm stat}=\\sqrt{\\gamma_{t-1}+2\\log(1/\\delta)}+\\sqrt\\lambda S$. The reported components are',
    '{Optimal experimental design.} Information-theoretic exploration objectives---such as maximizing $\\log\\det(\\bVbar_t)$ or minimizing the trace of~$\\bVbar_t^{-1}$---connect bandit exploration to the classical D-optimal and A-optimal design criteria \\citep{valko2013finite}. Stochastic trace and log-determinant estimators provide related matrix-free tools \\citep{ubaru2017fast}. Here the frozen log-determinant appears in the regret analysis; the audited policy selects actions by its UCB score and does not implement these estimators.',
    '{Path-certificate conservatism on log--log axes. Blue circles bin the per-round Hessian/$Q_t$ certificate $\\bar D_t^Q$ against endpoint Thompson distance. Orange triangles bin the numerical selected factor-path length at preregistered checkpoints. Each target panel pools eligible observations from the three independently executed horizons. Markers are plotted at geometric bin centers, marker size encodes bin count, and the dashed line is equality. Values at or below the preregistered $10^{-12}$ ratio tolerance, including round-one zeros, are omitted from the log axes and counted in \\Cref{tab:transport-instantiation-tightness}. Quadrature and generalized-eigenvalue calculations are dense float64 diagnostics, not verified certificates.} \\label{fig:transport-instantiation-tightness}',
    '{Per-round mean cumulative decomposition over 50 transport-Hessian trajectories at $T=1000$. The base confidence component, which includes the regularization/norm-bound term, dominates; historical linearization, path inflation, and current bias are shown separately. The red sharp right-hand side remains far above realized regret in every target condition.} \\label{fig:transport-instantiation-bound}',
    '{Policy outcomes at the primary horizon $T=1000$. Mean-regret and paired-difference intervals are comparisonwise deterministic paired-bootstrap 95\\% intervals over the same 50 evaluation seeds. Each difference is the row method minus transport Hessian, so negative values favor the row method. Transport endpoint is a dense diagnostic comparator; naive current is an uncertified negative control.} \\label{tab:transport-instantiation-performance} \\evidencetabular{@{} >{\\raggedleft\\arraybackslash}p{    } >{\\raggedright\\arraybackslash}p{     } >{\\raggedright\\arraybackslash}p{     } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{    } >{\\raggedleft\\arraybackslash}p{     } >{\\raggedleft\\arraybackslash}p{    }@{}}{ \\input{tables/transport_instantiation_performance.tex}}',
    "{Policy outcomes.} At $T=1000$, mean regret for the operational Hessian-certificate policy rises from $81.0$ to $94.0$ across the four target conditions (\\Cref{tab:transport-instantiation-performance}). All three comparison policies have lower sample-mean pseudo-regret than transport Hessian in every reported condition at this horizon. These are matched-stream total-policy comparisons: the policies share contexts and potential outcomes, but their actions, fitted parameters, centers, radii, and widths may diverge after the first disagreement. The endpoint comparison is consistent with conservatism in the analytic envelope, but it does not isolate a fixed-history mechanism and does not provide a scalable policy certificate; it is a dense diagnostic comparator rather than a deployable policy. The naive score's observed optimism does not make it theoretically valid. Since $D_{\\rm target}$ also changes $W$, the cross-condition pattern is not a causal dose response. Read in the intended direction, these outcomes do not show a causal or uniform advantage for full curvature, and the reverse ordering they record is specific to this environment, this certificate, and this horizon.",
    '{Positive-cone metric geometry.} \\citet{thompson1963certain} introduced the part metric now commonly called the Thompson metric on ordered cones. \\citet{nussbaum1994finsler} developed its Finsler structure and applications. On the positive-definite cone, the normalized operator norm $\\|V^{-1/2}\\dot V V^{-1/2}\\|_{\\rm op}$ is the corresponding tangent norm. Our contribution is not this geometry or its path-to-endpoint comparison. We instantiate it as an operational confidence-transport device linking frozen bandit confidence, current replayed GGN/Fisher curvature, approximate operators, and certified solver widths.',
    '{Protocol and timing.} Let $(\\mathsf A,\\mathcal B)$ be a standard Borel action space. At round $t$, the learner observes a context and a nonempty random action correspondence $\\cA_t:\\Omega\\to 2^{\\mathsf A}$ whose graph \\[ \\operatorname{Gr}(\\cA_t) :=\\{(\\omega,a):a\\in\\cA_t(\\omega)\\} \\in\\cHist_t^-\\otimes\\mathcal B. \\] Here $\\cHist_t^-$ is the history after the context and action correspondence are observed but before fresh round-$t$ algorithmic randomization. The variable $\\Omega_t$ records all round-$t$ pre-reward randomization, which may be revealed in sequential stages, and $\\cHist_t=\\cHist_t^-\\vee\\sigma(\\Omega_t)$ contains that randomization but not the reward. The restrictions to $\\operatorname{Gr}(\\cA_t)$ of $(\\omega,a)\\mapsto\\mu_t^*(a),\\bq_t(a),m_t(a),b_t(a),\\hat s_t(a)$, and, once defined below, $U_t(a)$ are assumed jointly measurable with respect to $\\cHist_t\\otimes\\mathcal B$. We also assume explicitly that $\\sup_{a\\in\\cA_t}\\mu_t^*(a)$ and $\\sup_{a\\in\\cA_t}U_t(a)$ are finite $\\cHist_t$-measurable random variables, that the oracle below returns a $\\cHist_t$-measurable selector in $\\cA_t$, and that the simultaneous confidence and all certificate events below, including path, operator, all-domain solver-upper, and played-action sharpness validity, are measurable. These are substantive assumptions; standard-Borel structure and graph measurability alone do not make every supremum or selector measurable.',
    '{Protocol.} We use the finite-dimensional scaled-tanh Gaussian specialization of \\Cref{cor:global-near-linear-new}. Contexts have dimension $4$, there are five actions, and the normalized context--action feature map has dimension $29$. The frozen and current matrices are formed densely, all widths use float64 Cholesky solves, and finite enumeration uses the smallest-index tie rule. Thus the intended theorem interface has \\[ \\alpha_t=1,\\qquad \\kappa_{-,t}=\\kappa_{+,t}=1,\\qquad \\xi_t=0. \\] These equalities describe the exact operator, solve, and selection abstractions. The recorded floating-point checks are diagnostics, not verified numerical certificates.',
    '{Validity audit.} For the primary policy, every one of the same 50 base seeds in each of the 12 horizon--target cells retained simultaneous reference confidence and transported optimism. The cellwise exact 95\\% Clopper--Pearson interval is $[92.9\\%,100\\%]$. Reusing base seeds across cells supports paired comparisons within a condition, not a pooled sample of 600 independent runs. The strict aggregate accepted all 2400 policy trajectories with no deterministic algebra or certificate-check failure, and the primary policy had no bound violation on the joint confidence event (\\Cref{tab:transport-instantiation-validity}). This finite-sample observation does not prove or empirically validate the theorem. In particular, ordinary float64 Cholesky, eigenvalue, and quadrature checks are not verified enclosures.',
    '} \\newcommand{\\ccetablesize}{} \\newcommand{\\evidencetabular}[2]{ \\begingroup \\let\\ccerealtabular\\tabular \\renewcommand{\\tabular}[2][c]{\\ccerealtabular[##1]{#1}} #2 \\endgroup}',
)


def _u(*cited: tuple[int, int]) -> tuple[tuple[str, int], ...]:
    """Resolve `(unit index, offset)` pairs against UNITS."""

    return tuple((UNITS[index], offset) for index, offset in cited)


#: (path, phrase) -> (occurrences, ((unit, offset-in-unit), ...))
PHRASE_PINS: dict[tuple[str, str], tuple[int, tuple[tuple[str, int], ...]]] = {
    # paper/body_conclusion.tex
    ('paper/body_conclusion.tex', '$D_t<1$'):
        (1, _u((32, 689))),
    ('paper/body_conclusion.tex', 'All 600 transport-Hessian trajectories'):
        (1, _u((44, 100))),
    # paper/body_intro.tex
    ('paper/body_intro.tex', '29-parameter'):
        (1, _u((50, 67))),
    # paper/legacy_scope.tex
    ('paper/legacy_scope.tex', '29-parameter'):
        (1, _u((45, 350))),
    # paper/transport_experiment.tex
    ('paper/transport_experiment.tex', '$1.20$--$1.22$ times the endpoint distance'):
        (1, _u((133, 485))),
    ('paper/transport_experiment.tex', '$1.88\\times10^6$'):
        (1, _u((133, 569))),
    ('paper/transport_experiment.tex', '$126.7$--$135.0$ at $T=1000$'):
        (1, _u((131, 189))),
    ('paper/transport_experiment.tex', '$2.0\\%$--$16.3\\%$'):
        (1, _u((47, 325))),
    ('paper/transport_experiment.tex', '$2.24\\times10^6$'):
        (1, _u((133, 839))),
    ('paper/transport_experiment.tex', '$2.51\\times10^5$'):
        (1, _u((133, 551))),
    ('paper/transport_experiment.tex', '$3{,}989$--$12{,}607$'):
        (1, _u((131, 442))),
    ('paper/transport_experiment.tex', '$79.4\\%$--$97.3\\%$'):
        (1, _u((47, 214))),
    ('paper/transport_experiment.tex', '$8.74\\times10^{-6}$'):
        (1, _u((133, 254))),
    ('paper/transport_experiment.tex', '$9{,}948$--$10{,}010$'):
        (1, _u((47, 601))),
    ('paper/transport_experiment.tex', '$T=1000$'):
        (8, _u((51, 1263), (133, 28), (133, 859), (133, 1056), (131, 209), (47, 172), (142, 22), (141, 40))),
    ('paper/transport_experiment.tex', '$[92.9\\%,100\\%]$'):
        (1, _u((146, 240))),
    ('paper/transport_experiment.tex', '$\\log 5\\approx1.609$'):
        (1, _u((51, 1580))),
    ('paper/transport_experiment.tex', '$e^{\\bar D_t^Q/2}$'):
        (1, _u((133, 982))),
    ('paper/transport_experiment.tex', '100 declared checkpoints per trajectory'):
        (1, _u((133, 345))),
    ('paper/transport_experiment.tex', '20 full-batch steps'):
        (1, _u((51, 1055))),
    ('paper/transport_experiment.tex', '5,000\neligible seed--checkpoint ratios'):
        (1, _u((133, 398))),
    ('paper/transport_experiment.tex', '50 evaluation seeds'):
        (2, _u((51, 58), (141, 173))),
    ('paper/transport_experiment.tex', '50 runs per cell'):
        (1, _u((135, 249))),
    ('paper/transport_experiment.tex', '50 trajectory-level observations per cell'):
        (1, _u((133, 295))),
    ('paper/transport_experiment.tex', '50 transport-Hessian trajectories'):
        (1, _u((47, 396))),
    ('paper/transport_experiment.tex', '600 independent runs'):
        (1, _u((146, 361))),
    ('paper/transport_experiment.tex', 'All five actions are optimal somewhere in every'):
        (1, _u((51, 1452))),
    ('paper/transport_experiment.tex', 'Contexts have dimension $4$'):
        (1, _u((145, 116))),
    ('paper/transport_experiment.tex', 'No run has zero regret'):
        (1, _u((131, 219))),
    ('paper/transport_experiment.tex', 'Ten disjoint tuning seeds'):
        (1, _u((51, 985))),
    ('paper/transport_experiment.tex', '\\alpha_t=1'):
        (1, _u((145, 428))),
    ('paper/transport_experiment.tex', '\\kappa_{-,t}=\\kappa_{+,t}=1'):
        (1, _u((145, 446))),
    ('paper/transport_experiment.tex', '\\xi_t=0'):
        (1, _u((145, 481))),
    ('paper/transport_experiment.tex', 'all 2400 policy\ntrajectories'):
        (1, _u((146, 413))),
    ('paper/transport_experiment.tex', 'best-fixed-action regret $180.4$'):
        (1, _u((51, 1368))),
    ('paper/transport_experiment.tex', 'cap $2{,}000$'):
        (1, _u((47, 642))),
    ('paper/transport_experiment.tex', 'deterministic cap $2T$'):
        (1, _u((131, 331))),
    ('paper/transport_experiment.tex', 'each of the 12\nhorizon--target cells'):
        (1, _u((146, 81))),
    ('paper/transport_experiment.tex', 'exact 95\\% Clopper--Pearson interval'):
        (1, _u((146, 200))),
    ('paper/transport_experiment.tex', 'feature map has dimension $29$'):
        (1, _u((145, 204))),
    ('paper/transport_experiment.tex', 'horizons $T\\in\\{250,500,1000\\}$'):
        (1, _u((51, 25))),
    ('paper/transport_experiment.tex', 'is $126.7$--$155.7$ over the'):
        (1, _u((131, 146))),
    ('paper/transport_experiment.tex', 'is $3.07\\times10^5$'):
        (1, _u((133, 818))),
    ('paper/transport_experiment.tex', 'learning rate $3\\times10^{-4}$'):
        (1, _u((51, 1020))),
    ('paper/transport_experiment.tex', 'mean-only regret $185.4$'):
        (1, _u((51, 1426))),
    ('paper/transport_experiment.tex', 'no bound violation on the joint confidence event'):
        (1, _u((146, 529))),
    ('paper/transport_experiment.tex', 'no deterministic algebra or certificate-check failure'):
        (1, _u((146, 447))),
    ('paper/transport_experiment.tex', 'optimal-action\nentropy $1.579$'):
        (1, _u((51, 1312))),
    ('paper/transport_experiment.tex', 'optimality\ngap $0.123$'):
        (1, _u((51, 1344))),
    ('paper/transport_experiment.tex', 'paired-bootstrap 95\\%'):
        (1, _u((141, 127))),
    ('paper/transport_experiment.tex', 'pools all 50,000 seed--round values'):
        (1, _u((133, 1015))),
    ('paper/transport_experiment.tex', 'ranges from\n$1.02$'):
        (1, _u((133, 1074))),
    ('paper/transport_experiment.tex', 'ranges from $0.0486$'):
        (1, _u((133, 100))),
    ('paper/transport_experiment.tex', 'ranges from $1.31\\times10^{-7}$'):
        (1, _u((133, 219))),
    ('paper/transport_experiment.tex', 'rises\nfrom $81.0$'):
        (1, _u((142, 91))),
    ('paper/transport_experiment.tex', 'target labels $D_{\\rm target}\\in\\{0.25,0.5,1,2\\}$'):
        (1, _u((51, 83))),
    ('paper/transport_experiment.tex', 'the 50-seed means'):
        (1, _u((51, 1285))),
    ('paper/transport_experiment.tex', 'the same 50 base seeds'):
        (1, _u((146, 55))),
    ('paper/transport_experiment.tex', 'there are five\nactions'):
        (1, _u((145, 145))),
    ('paper/transport_experiment.tex', 'to $0.384$'):
        (1, _u((133, 121))),
    ('paper/transport_experiment.tex', 'to $1.18$'):
        (1, _u((133, 1093))),
    ('paper/transport_experiment.tex', 'to $94.0$'):
        (1, _u((142, 109))),
    ('paper/transport_experiment.tex', 'versus caps of $500$--$2{,}000$'):
        (1, _u((131, 465))),
    # paper/transport_experiment_appendix.tex
    ('paper/transport_experiment_appendix.tex', '$2.01\\%,4.04\\%,8.16\\%,16.27\\%$'):
        (1, _u((53, 566))),
    ('paper/transport_experiment_appendix.tex', '$97.33\\%,94.66\\%,89.39\\%,79.39\\%$'):
        (1, _u((53, 516))),
    ('paper/transport_experiment_appendix.tex', '$D_{\\rm target}=0.25,0.5,1,2$'):
        (1, _u((53, 601))),
    ('paper/transport_experiment_appendix.tex', '$T=1000$'):
        (3, _u((53, 400), (136, 34), (140, 83))),
    ('paper/transport_experiment_appendix.tex', '$e^{\\bar D_t^Q/2}$'):
        (2, _u((53, 729), (132, 345))),
    ('paper/transport_experiment_appendix.tex', '50 evaluation seeds'):
        (2, _u((54, 258), (136, 112))),
    ('paper/transport_experiment_appendix.tex', '50 primary-policy trajectories'):
        (1, _u((53, 351))),
    ('paper/transport_experiment_appendix.tex', '50 runs per cell'):
        (1, _u((132, 249))),
    ('paper/transport_experiment_appendix.tex', '50 transport-Hessian trajectories'):
        (1, _u((140, 46))),
    ('paper/transport_experiment_appendix.tex', '\\kappa_{-,t}=\\kappa_{+,t}=1'):
        (1, _u((53, 115))),
    ('paper/transport_experiment_appendix.tex', '\\xi_t=0'):
        (1, _u((53, 149))),
    ('paper/transport_experiment_appendix.tex', 'paired-bootstrap 95\\%'):
        (1, _u((136, 71))),
    ('paper/transport_experiment_appendix.tex', 'preregistered $10^{-12}$ ratio tolerance'):
        (1, _u((139, 475))),
    # paper/transport_proofs.tex
    ('paper/transport_proofs.tex', '\\xi_t=0'):
        (2, _u((69, 414), (70, 565))),
    # paper/transport_theory.tex
    ('paper/transport_theory.tex', '$D_t<1$'):
        (1, _u((29, 214))),
    ('paper/transport_theory.tex', '\\alpha_t=1'):
        (1, _u((62, 696))),
    ('paper/transport_theory.tex', '\\kappa_{-,t}=\\kappa_{+,t}=1'):
        (2, _u((30, 29), (62, 710))),
    ('paper/transport_theory.tex', '\\xi_t=0'):
        (3, _u((66, 439), (58, 270), (62, 745))),
    # submissions/tmlr_2026/main.tex
    ('submissions/tmlr_2026/main.tex', '29-parameter'):
        (1, _u((39, 1014))),
    ('submissions/tmlr_2026/main.tex', 'All 600 transport-Hessian runs'):
        (1, _u((39, 1086))),
    # submissions/tmlr_2026/supplement_README.md
    ('submissions/tmlr_2026/supplement_README.md', '2,400 trajectories'):
        (1, _u((6, 116))),
    ('submissions/tmlr_2026/supplement_README.md', '21 artifacts'):
        (1, _u((123, 47))),
    ('submissions/tmlr_2026/supplement_README.md', 'all 21 published tables, figures and CSVs'):
        (1, _u((10, 120))),
}

#: (path, literal) -> (category, occurrences, ((unit, offset-in-unit), ...))
CLASSIFIED_PINS: dict[tuple[str, str], tuple[str, int, tuple[tuple[str, int], ...]]] = {
    # paper/availability.tex
    ('paper/availability.tex', '1.13.1'):
        ('historical-dependency-version', 1, _u((48, 771))),
    ('paper/availability.tex', '1.15.2'):
        ('historical-dependency-version', 1, _u((48, 699))),
    # paper/body_related.tex
    ('paper/body_related.tex', '1'):
        ('math-constant', 3, _u((143, 291), (143, 306), (138, 157))),
    ('paper/body_related.tex', '10^8'):
        ('cited-scale', 1, _u((134, 454))),
    ('paper/body_related.tex', '2'):
        ('math-constant', 2, _u((143, 293), (143, 308))),
    # paper/notation.tex
    ('paper/notation.tex', '1'):
        ('math-constant', 2, _u((147, 153), (147, 157))),
    ('paper/notation.tex', '2'):
        ('math-constant', 3, _u((147, 61), (147, 129), (147, 162))),
    # paper/transport_experiment_appendix.tex
    ('paper/transport_experiment_appendix.tex', '1'):
        ('math-constant', 7, _u((137, 168), (137, 177), (16, 19), (15, 19), (24, 18), (24, 46), (17, 10))),
    ('paper/transport_experiment_appendix.tex', '2'):
        ('math-constant', 10, _u((137, 104), (137, 108), (137, 171), (16, 1), (16, 44), (15, 1), (15, 44), (24, 43), (24, 64), (17, 1))),
    # paper/transport_proofs.tex
    ('paper/transport_proofs.tex', '0'):
        ('math-constant', 8, _u((36, 304), (74, 554), (74, 609), (64, 172), (41, 29), (41, 270), (41, 346), (41, 359))),
    ('paper/transport_proofs.tex', '1'):
        ('math-constant', 63, _u((95, 114), (108, 18), (36, 17), (36, 284), (36, 293), (85, 42), (55, 127), (69, 121), (74, 383), (74, 455), (74, 485), (74, 572), (73, 130), (73, 154), (73, 175), (73, 192), (73, 248), (73, 273), (73, 296), (73, 507), (73, 539), (73, 566), (73, 599), (73, 707), (73, 772), (71, 86), (75, 299), (75, 464), (75, 491), (130, 48), (130, 56), (130, 150), (130, 179), (130, 188), (130, 349), (130, 424), (68, 68), (68, 207), (68, 305), (70, 134), (70, 549), (70, 556), (72, 108), (72, 141), (72, 153), (72, 421), (72, 431), (89, 58), (89, 118), (90, 99), (46, 31), (46, 55), (46, 178), (67, 234), (67, 247), (67, 298), (67, 374), (67, 417), (67, 432), (34, 17), (34, 342), (35, 529), (35, 670))),
    ('paper/transport_proofs.tex', '2'):
        ('math-constant', 73, _u((96, 55), (96, 93), (95, 116), (109, 44), (109, 80), (108, 103), (36, 134), (36, 181), (36, 204), (36, 232), (36, 244), (36, 335), (36, 346), (36, 363), (36, 380), (85, 55), (85, 78), (85, 88), (74, 385), (74, 457), (74, 487), (73, 132), (73, 156), (73, 177), (73, 194), (73, 250), (73, 275), (73, 385), (73, 509), (73, 541), (73, 555), (73, 568), (73, 601), (73, 630), (73, 709), (71, 109), (71, 230), (71, 239), (71, 251), (71, 353), (71, 366), (75, 99), (75, 123), (75, 139), (75, 168), (75, 222), (75, 253), (75, 277), (75, 305), (75, 466), (75, 493), (130, 182), (130, 532), (68, 58), (68, 167), (68, 176), (68, 316), (68, 336), (70, 122), (70, 130), (70, 327), (70, 336), (70, 438), (70, 477), (70, 486), (90, 127), (46, 225), (67, 271), (67, 322), (34, 42), (34, 72), (34, 113), (34, 245))),
    ('paper/transport_proofs.tex', '4'):
        ('math-constant', 2, _u((70, 431), (70, 441))),
    # paper/transport_theory.tex
    ('paper/transport_theory.tex', '0'):
        ('math-constant', 22, _u((33, 14), (33, 29), (40, 14), (94, 33), (61, 121), (61, 136), (92, 57), (92, 104), (124, 15), (7, 0), (7, 0), (7, 0), (7, 0), (7, 0), (7, 0), (76, 200), (37, 71), (56, 81), (57, 323), (58, 71), (62, 516), (3, 10))),
    ('paper/transport_theory.tex', '0,1'):
        ('interval-endpoint', 5, _u((65, 78), (76, 78), (37, 63), (37, 102), (31, 15))),
    ('paper/transport_theory.tex', '1'):
        ('math-constant', 84, _u((79, 10), (22, 25), (21, 22), (20, 24), (84, 63), (84, 90), (84, 106), (97, 116), (13, 9), (13, 34), (13, 67), (88, 78), (104, 68), (104, 88), (115, 15), (115, 36), (107, 68), (113, 15), (113, 36), (126, 134), (126, 202), (126, 269), (102, 69), (102, 94), (102, 115), (28, 203), (66, 241), (59, 1), (86, 58), (86, 74), (86, 103), (92, 70), (77, 356), (77, 365), (124, 22), (78, 23), (78, 52), (5, 80), (5, 189), (82, 59), (82, 90), (37, 99), (37, 242), (37, 378), (99, 43), (56, 46), (106, 31), (98, 55), (98, 82), (98, 115), (125, 20), (125, 55), (19, 12), (25, 17), (25, 26), (60, 120), (49, 103), (49, 162), (49, 191), (49, 207), (83, 71), (27, 9), (120, 45), (112, 29), (58, 195), (58, 231), (62, 793), (62, 858), (122, 25), (29, 98), (52, 89), (91, 31), (91, 71), (129, 103), (110, 67), (110, 87), (110, 103), (110, 113), (114, 15), (114, 36), (0, 2), (0, 13), (2, 8), (1, 1))),
    ('paper/transport_theory.tex', '2'):
        ('math-constant', 87, _u((144, 192), (18, 19), (80, 9), (127, 4), (128, 12), (84, 117), (84, 128), (13, 36), (13, 69), (100, 68), (88, 164), (104, 23), (104, 33), (104, 80), (104, 160), (115, 6), (107, 23), (107, 33), (107, 81), (107, 90), (107, 94), (113, 6), (101, 4), (101, 26), (102, 4), (102, 24), (102, 34), (102, 81), (102, 85), (86, 76), (86, 105), (77, 358), (77, 367), (78, 25), (78, 54), (5, 101), (5, 122), (5, 168), (5, 204), (82, 92), (37, 177), (37, 380), (63, 116), (81, 58), (87, 122), (80, 9), (105, 40), (128, 12), (106, 42), (98, 57), (98, 84), (93, 78), (93, 86), (93, 88), (19, 23), (25, 20), (116, 81), (49, 216), (83, 82), (83, 102), (26, 57), (120, 39), (121, 33), (121, 43), (112, 6), (103, 4), (122, 19), (117, 12), (117, 21), (119, 25), (119, 35), (118, 21), (23, 21), (111, 14), (14, 8), (14, 39), (42, 14), (42, 35), (42, 158), (91, 41), (91, 81), (129, 93), (110, 22), (110, 32), (110, 79), (110, 171), (114, 6))),
    ('paper/transport_theory.tex', '3'):
        ('math-constant', 2, _u((42, 52), (42, 161))),
    ('paper/transport_theory.tex', '4'):
        ('math-constant', 4, _u((62, 780), (118, 12), (42, 49), (42, 150))),
    # submissions/tmlr_2026/supplement_README.md
    ('submissions/tmlr_2026/supplement_README.md', '0'):
        ('document-structure', 1, _u((8, 0))),
    ('submissions/tmlr_2026/supplement_README.md', '1'):
        ('document-structure', 2, _u((4, 795), (9, 0))),
    ('submissions/tmlr_2026/supplement_README.md', '1.15.2'):
        ('environment-version', 1, _u((38, 129))),
    ('submissions/tmlr_2026/supplement_README.md', '2'):
        ('document-structure', 2, _u((43, 63), (10, 0))),
    ('submissions/tmlr_2026/supplement_README.md', '2.2.3'):
        ('environment-version', 1, _u((38, 116))),
    ('submissions/tmlr_2026/supplement_README.md', '3'):
        ('document-structure', 2, _u((123, 561), (11, 0))),
    ('submissions/tmlr_2026/supplement_README.md', '3.12'):
        ('environment-version', 1, _u((38, 7))),
    ('submissions/tmlr_2026/supplement_README.md', '4'):
        ('document-structure', 1, _u((12, 0))),
}

#: path -> SHA-256 of the whole normalized auditable text
FILE_PINS: dict[str, str] = {
    'paper/availability.tex':
        '6bc2c7725aa2967a3fcbc24646075e3bf3d9a9a0bd71a789d9c6f7039453c20c',
    'paper/body_conclusion.tex':
        'bba45e6c4cc8f47f4e56464d5f621a0d6b03e59910e668086749a130cb803f32',
    'paper/body_intro.tex':
        '7d52a17ae4b6c3b2332f45c3ee8f99a453729d2c3a2e1721c7d7528139739a6d',
    'paper/body_related.tex':
        'a1af9c40892930dbeaa4b98a8559fc01cb6eb1fd0c7036dda293fde2d8dc37c4',
    'paper/broader_impact.tex':
        '41c44900a31c1d4274da9f69facd14255cfc61108c1ec592805208be3b8c0605',
    'paper/legacy_scope.tex':
        'be156968b1bdb7a14e7451e7c45d747f5b5586fc6be2101ede15cd829f3b542a',
    'paper/macros.tex':
        '1129bd91c4ad4afdfb620e562fea7a496deca6dd9f9aab3900eda0855380323f',
    'paper/notation.tex':
        'bb6d009986893a068603fbaa0ae76ed5f0bd2ce6554b41db939ac7e0098bd727',
    'paper/transport_experiment.tex':
        '0b950ebb940e1a379278a1de4e5c85a3bb613a30eaebd91fe3ed455c77a0e7c6',
    'paper/transport_experiment_appendix.tex':
        '2b720128602065515a658c81702e8c930cb5a20b441791533fd78dbc7494084b',
    'paper/transport_proofs.tex':
        '604f998c8eb08d34afe3b2451739d8879e005e1730b8a4c10a0b31e1835d5a16',
    'paper/transport_theory.tex':
        '88e0068c14642e443b11f3d19b51368aa31dcfb07b48881c68c2a60d16c7faf9',
    'submissions/tmlr_2026/main.tex':
        'ed6a7fead151243885f14feb749e0840c6d3804359b54052c3aca142df32c6a4',
    'submissions/tmlr_2026/supplement_README.md':
        'c022f19f2635d25845d4dab1b8ad93eda1d50a1a22ce76030317d52e24ea4435',
}
