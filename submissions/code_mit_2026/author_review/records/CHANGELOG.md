# Minimal LaTeX change log

Baseline: `original/main.tex`, matching the committed CODE blob `9837cd16e04fbb803ebe77d3d76b766b8631a43e`. Each block is an actual changed span; unchanged lines are omitted. The patch targets only `submissions/code_mit_2026/main.tex`. Numerical and contribution changes remain proposed, with authority status recorded in `AUTHOR_APPROVAL.md`.

## Change 1: original lines after 2; candidate lines 3 to 3

Reason: Load amsthm before newtxmath so the numbered theorem compiles without an openbox definition collision.

Old -> new:

```latex
% No previous lines (insertion).
```

```latex
\usepackage{amsmath,amsthm}
```

## Change 2: original lines 4 to 4; candidate lines 5 to 6

Reason: Add a numbered Theorem 1 without changing body typography or margins.

Old -> new:

```latex
\usepackage{amsmath}
```

```latex
\theoremstyle{definition}
\newtheorem{theorem}{Theorem}
```

## Change 3: original lines after 29; candidate lines 32 to 33

Reason: Label the candidate as a proposed review draft and leave author metadata to the author.

Old -> new:

```latex
% No previous lines (insertion).
```

```latex
\begin{center}\small Proposed revision for author review.\\
{[AUTHOR: supply final author order and affiliations]}\end{center}
```

## Change 4: original lines 32 to 32; candidate lines 36 to 36

Reason: Remove naturally, state the two contributions, and retain a single empirical sentence.

Old -> new:

```latex
Adaptive allocation policies may update a nonlinear prediction model before choosing the next action. Confidence is then naturally built from model sensitivities frozen when past rewards were collected, while current scores may use sensitivities recomputed under the updated model. We give conditions under which reward confidence transfers between these geometries and through approximate numerical components, yielding an optimistic score and a conditional regret bound. For squared-loss models, a corrected center supports any predictable parameter path inside a certified smoothness region without requiring nonlinear optimizer convergence. A controlled 29-parameter scaled-tanh audit records all declared float64 confidence and optimism diagnostics, yet its operational transport envelope is highly conservative, the numerically evaluated regret bound is vacuous, and comparison policies have lower mean pseudo-regret at the primary horizon. The result concerns reward confidence for action selection; it does not establish treatment-effect inference after adaptive assignment.
```

```latex
Updating an allocation model changes the sensitivities used to score actions, while reward confidence may rely on sensitivities fixed when observations were collected. We give a finite-action confidence-transfer result with explicit geometric and numerical certificates, an optimistic score, and a regret bound. A corrected-center construction supplies reference confidence without a nonlinear optimizer-convergence assumption. A controlled nearly linear simulation records simultaneous confidence and optimism diagnostics, but its regret bound is vacuous and all comparison policies have lower sample mean pseudo-regret at the primary horizon.
```

## Change 5: original lines 37 to 37; candidate lines 41 to 45

Reason: Replace the generic opening with a hypothetical allocation example and define the finite-action protocol, timing, queries, and positive scales.

Old -> new:

```latex
Contextual-bandit and adaptive-experimentation policies often score actions using a model that changes with incoming data \cite{abbasi2011improved,zhou2020neural,riquelme2018deep}. Let $q_t(a)$ denote the current model sensitivity for action $a$. The statistical reference geometry retains each historical sensitivity at its collection-time value:
```

```latex
An allocation policy might retrain an outcome model in batches, then use predicted rewards and uncertainty to choose an ad or ranking action. This illustration differs from our synthetic study. Learned reward models also appear in neural contextual bandits \cite{zhou2020neural,riquelme2018deep}. Recomputing past sensitivities changes the Gram matrix. Collection-time confidence alone gives no upper bound using the recomputed matrix: an inverse-metric comparison for the current query is missing.

At round $t\le T$, observe context $x_t$, choose $a_t$ from a fixed finite nonempty set $\mathcal A$, and then observe a reward. Write $\mu_t^*(a)$ for its true conditional mean under action $a$ and $m_t(a)$ for a generic prediction center. Queries $q_t(a)\in\R^d$ share a fixed dimension $d$. Let $\mathcal H_t^-$ be the history after observing $x_t$ but before fresh round-$t$ randomization $\Omega_t$, and let $\mathcal H_t=\mathcal H_t^-\vee\sigma(\Omega_t)$ contain all pre-reward information. Predictable means $\mathcal H_t^-$-measurable: the reference and exact current metrics, the representation parameter $\theta_t$ when used, and $\beta_t\ge0$ are predictable. Queries, means, centers, biases, algorithmic operators, certificates, scores, and the selector are finite and $\mathcal H_t$-measurable, actionwise. Historical selected queries are fixed before their own rewards. Assume all events below are measurable.

For $\lambda,\sigma>0$, with $I$ the $d$-dimensional identity, define reference geometry and widths by
```

## Change 6: original lines 45 to 45; candidate lines 53 to 53

Reason: Introduce pseudo-regret and information gain before the theorem uses them.

Old -> new:

```latex
The issue is that action selection may instead use a recomputed uncertainty geometry after the prediction model has moved. We assume a simultaneous reference-confidence event
```

```latex
Define cumulative pseudo-regret and frozen information gain, with $\gamma_0=0$, as
```

## Change 7: original lines 47 to 47; candidate lines 55 to 64

Reason: Define the full log-determinant ratio and all metric widths, then state the reference-confidence premise in Theorem 1.

Old -> new:

```latex
|\mu_t^*(a)-m_t(a)|\le \beta_t\bar s_t(a)+b_t(a),
```

```latex
R_T=\sum_{t=1}^T\left[\max_{a\in\mathcal A}\mu_t^*(a)-\mu_t^*(a_t)\right],\qquad
\gamma_T=\log\frac{\det\Vbar_{T+1}}{\det\Vbar_1}.
\label{eq:regret-gain}
\end{equation}
Let $V_t$ be the exact current metric and $C_t$ the algorithmic operator, both $d\times d$ symmetric positive-definite (SPD). Set $s_t(a)^2=q_t(a)^\top V_t^{-1}q_t(a)$ and $s_{C,t}(a)^2=q_t(a)^\top C_t^{-1}q_t(a)$.

\begin{theorem}[Finite-action confidence transfer]\label{thm:transfer}
Under this protocol, suppose $\|q_t(a)\|_2\le G<\infty$. On $E_{\rm conf}$, simultaneously for all $t\le T$ and $a\in\mathcal A$,
\begin{equation}
|\mu_t^*(a)-m_t(a)|\le\beta_t\bar s_t(a)+b_t(a),\qquad b_t(a)\ge0.
```

## Change 8: original lines 50 to 59; candidate lines 67 to 67

Reason: Replace the pipeline diagram and vague certificate prose with the canonical selected-path premise and geometry attribution.

Old -> new:

```latex
where $b_t(a)$ covers current approximation or misspecification error. This is a premise; it does not follow automatically from arbitrary adaptive neural training.

The operational chain is
\[
\begin{aligned}
\text{collection-time confidence}&\longrightarrow\text{current relinearized geometry}\\[-1mm]
&\longrightarrow\text{approximate operator / solve}\longrightarrow\text{optimistic action score}.
\end{aligned}
\]
Let $\Dbar_t$ upper-bound the frozen-to-current metric transport, let $\kappa_{-,t},\kappa_{+,t}$ give a two-sided distortion certificate for the operator used by the policy, and let $\shat_t(a)$ be an all-action upper-valid numerical width. The transported score is
```

```latex
On $E_{\rm cert}$, for each $t$, a finite pre-reward envelope $\Dbar_t\ge0$ bounds the Thompson Finsler length \cite{nussbaum1994finsler} of an absolutely continuous SPD path from $\Vbar_t$ to $V_t$. Consequently, in Loewner order,
```

## Change 9: original lines 61 to 61; candidate lines 69 to 82

Reason: Display the two-sided metric/operator comparisons, all-action solver validity, played-action sharpness, and the unchanged score with its oracle.

Old -> new:

```latex
U_t(a)=m_t(a)+\beta_t e^{\Dbar_t/2}\sqrt{\kappa_{+,t}}\,\shat_t(a)+b_t(a).
```

```latex
e^{-\Dbar_t}\Vbar_t\preceq V_t\preceq e^{\Dbar_t}\Vbar_t,\qquad
\kappa_{-,t}V_t\preceq C_t\preceq\kappa_{+,t}V_t,
\label{eq:certificates}
\end{equation}
where the second comparison is also required on $E_{\rm cert}$, with $0<\kappa_{-,t}\le\kappa_{+,t}<\infty$. The solver's nonnegative pre-reward width map satisfies, on that event,
\begin{equation}
s_{C,t}(a)\le\shat_t(a)\quad(a\in\mathcal A),\qquad
\shat_t(a_t)\le\alpha_t s_{C,t}(a_t),\quad\alpha_t\ge1.
\label{eq:solver}
\end{equation}
Use this same realized width map for the score and oracle:
\begin{equation}
U_t(a)=m_t(a)+\beta_t e^{\Dbar_t/2}\sqrt{\kappa_{+,t}}\,\shat_t(a)+b_t(a),\qquad
U_t(a_t)\ge\max_{a\in\mathcal A}U_t(a)-\xi_t,\quad\xi_t\ge0.
```

## Change 10: original lines 64 to 66; candidate lines 85 to 85

Reason: Move optimism and the pathwise event into Theorem 1 while retaining the exact regret display.

Old -> new:

```latex
At the played action, $\alpha_t\ge1$ controls how much the reported upper width may inflate the ideal algorithmic width; scoring and certification use the same realized width map. If score maximization is approximate, its error is $\xi_t$.

For a fixed finite action set, bounded $\|q_t(a)\|_2\le G$, and valid pre-reward certificates, the paper's transported-UCB theorem gives
```

```latex
Then $U_t(a)\ge\mu_t^*(a)$ for every action and round on $E_{\rm conf}\cap E_{\rm cert}$, and pathwise on that event,
```

## Change 11: original lines 76 to 76; candidate lines 95 to 97

Reason: State the union-bound probability once and replace the vague novelty sentence with two proposed contributions.

Old -> new:

```latex
where $\gamma_T=\log(\det\Vbar_{T+1}/\det\Vbar_1)$. \textbf{The bound holds on the joint reference-confidence and certificate event.} It is therefore a conditional transfer result, not an unconditional guarantee for unrestricted model updating. The novelty is the operational composition of the confidence, transport, numerical, and decision layers rather than the standard ingredients in isolation.
```

```latex
If $\Pr(E_{\rm conf})\ge1-\delta$ and $\Pr(E_{\rm cert})\ge1-\delta_{\rm cert}$, for failure levels $\delta,\delta_{\rm cert}\in[0,1]$, then \eqref{eq:regret} holds with probability at least $1-\delta-\delta_{\rm cert}$; independence is unnecessary.
\end{theorem}
Our contributions are Theorem~\ref{thm:transfer} with its explicit certificates, optimistic score, and regret bound, and the corrected-center confidence construction below; the geometry and confidence machinery are standard.
```

## Change 12: original lines 79 to 79; candidate lines 100 to 102

Reason: Define fixed coordinates, gradient queries, reference model, noise, approximation envelopes, and exact auxiliary-ridge access.

Old -> new:

```latex
For squared-loss models, fix before data collection a norm-bounded reference parameter $\theta^\circ$ in a certified smoothness region. Assume conditional sub-Gaussian reward noise and valid pre-reward envelopes for linearization and misspecification. For observation $s$, retain the collection-time sensitivity $q_s$ and define
```

```latex
Use a differentiable model mean $\mu_\theta(x,a)$ in fixed parameter coordinates $\theta\in\Theta\subseteq\R^d$, with $\Theta$ a convex smoothness region. For $z=(x,a)$, define $q_\theta(z)=\nabla_\theta\mu_\theta(z)$, $q_t(a)=q_{\theta_t}(x_t,a)$, $z_s=(x_s,a_s)$, and $q_s=q_s(a_s)$. The representation path $\theta_t\in\Theta$ is predictable. Fix before data collection $\theta^\circ\in\Theta$, $\|\theta^\circ\|_2\le S$, with $\mu_t^*(a)=\mu^*(x_t,a)$ and $\mu^*(z)=\mu_{\theta^\circ}(z)+m^\circ(z)$. Observed rewards obey $r_t=\mu_t^*(a_t)+\eta_t$ and $\mathbb E[e^{u\eta_t}\mid\mathcal H_t]\le e^{u^2\sigma^2/2}$ for every real $u$.

Supply nonnegative pre-reward bounds $\epsilon_{\rm lin}(s)$ on the absolute Taylor remainder of $\mu_{\theta^\circ}(z_s)$ about $\theta_s$, and $\epsilon_{\rm mis}(s)$ for $|m^\circ(z_s)|$. Define the current actionwise envelopes $\epsilon_{{\rm lin},t}(a),\epsilon_{{\rm mis},t}(a)$ analogously about $\theta_t$; the past sum below is known before selection. Containment alone does not make these errors small. With access to the exact auxiliary frozen ridge estimator, set
```

## Change 13: original lines 86 to 86; candidate lines 109 to 109

Reason: State simultaneous corrected-center confidence with its failure probability and self-normalized-confidence attribution.

Old -> new:

```latex
With $\|\theta^\circ\|_2\le S$, the reference radius is
```

```latex
For $\delta\in(0,1)$, self-normalization \cite{abbasi2011improved} and the Taylor envelopes give \eqref{eq:refconf} with probability at least $1-\delta$, simultaneously over rounds and actions, using $m_t=m_t^{\rm corr}$,
```

## Change 14: original lines after 89; candidate lines 113 to 113

Reason: Place the existing current-bias definition next to the unchanged corrected-radius formula.

Old -> new:

```latex
% No previous lines (insertion).
```

```latex
\quad b_t(a)=\epsilon_{{\rm lin},t}(a)+\epsilon_{{\rm mis},t}(a).
```

## Change 15: original lines 92 to 94; candidate lines 116 to 116

Reason: Remove the internal 1/sigma correction note and repeated assumptions; give the optimizer-independent statement and exact current GGN.

Old -> new:

```latex
and the current bias is $b_t(a)=\epsilon_{{\rm lin},t}(a)+\epsilon_{{\rm mis},t}(a)$. The historical deterministic term scales as $1/\sigma$, not $1/\sigma^2$.

Under a fixed norm-bounded reference model, conditional sub-Gaussian noise, a certified smoothness region, and valid pre-reward approximation-error envelopes, the corrected-center construction permits any predictable model-parameter path in that region without requiring nonlinear optimizer convergence. This does not license arbitrary coordinate or dimension changes, and nonvanishing misspecification can still make the bound uninformative.
```

```latex
No nonlinear optimizer-convergence assumption is used. The exact current squared-loss generalized Gauss-Newton (GGN) metric is $V_t=\lambda I+\sigma^{-2}\sum_{s<t}q_{\theta_t}(z_s)q_{\theta_t}(z_s)^\top$.
```

## Change 16: original lines 97 to 97; candidate lines 119 to 126

Reason: Describe the executed study directly and define its model, W target rule, smoothness bound, grid, tuning split, and numerical abstraction.

Old -> new:

```latex
The committed aggregate reports completion of the declared 2,400-trajectory evaluation grid with zero deterministic audit failures. Four policies were evaluated over 50 base seeds, three horizons, and four near-linearity conditions; tuning used disjoint seeds. The primary policy used the analytic transport envelope in its score, while comparison policies used a dense endpoint diagnostic, frozen reference widths, or uncertified current widths.
```

```latex
We ran four policies in a nearly linear scaled-tanh bandit with five actions and 29 parameters. For normalized features $\|\phi(z)\|_2\le1$, the mean is $\mu_{\theta,W}(z)=\sqrt W\tanh(\phi(z)^\top\theta/\sqrt W)$. Exact realizability holds with $\|\theta^\circ\|_2\le R=1$; parameters are projected to radius $R$, $\lambda=1$, and Gaussian noise has $\sigma=0.25$. For each horizon $T\in\{250,500,1000\}$ and target $D_{\rm target}\in\{0.25,0.5,1,2\}$, the predeclared rule sets
\begin{equation}
W=\left[\frac{4c_hR\sqrt{T-1}}{\sigma\sqrt\lambda D_{\rm target}}\right]^2,
\qquad c_h=\frac4{3\sqrt3},\qquad L_g=\frac{c_h}{\sqrt W},\qquad
Q_t=\sum_{s<t}\|\theta_t-\theta_s\|_2^2,\quad D_{Q,t}=\frac{2L_g\sqrt{Q_t}}{\sigma\sqrt\lambda}.
\label{eq:experiment-scale}
\end{equation}
Here $L_g$ bounds the operator norm of the mean Hessian along replay segments. The target is a worst-case trust-region label, not realized path length or parameter displacement; $W$ is a smoothness scale. Separate runs at each horizon and 50 evaluation seeds give 2,400 trajectories. Ten disjoint tuning seeds selected shared optimizer settings by mean squared prediction error. Policies share context and potential-noise streams but have their own histories, parameters, centers, radii, and metrics. All use dense float64 Cholesky solves and finite score maximization, with failure level $\delta=0.05$. The exact-arithmetic primary instantiation has $C_t=V_t$, $\kappa_{-,t}=\kappa_{+,t}=\alpha_t=1$, and $\xi_t=0$.
```

## Change 17: original lines 99 to 99; candidate lines 128 to 137

Reason: Replace the limitation heading with explicit own-history policy scores and endpoint/quadrature definitions.

Old -> new:

```latex
\textbf{Limitation before results.} Our evidence comes from a synthetic 29-parameter scaled-tanh bandit that is nearly linear under the chosen scaling, using dense float64 solves; it does not establish performance in strongly nonlinear models or deployed digital experiments.
```

```latex
The endpoint policy uses the dense Thompson distance $d_{{\rm Th},t}=\inf\{r\ge0:e^{-r}\Vbar_t\preceq V_t\preceq e^r\Vbar_t\}$ as a diagnostic oracle. Each policy scores $m_t^{\rm corr}(a)+\beta_t^{\rm corr}w_t(a)+b_t(a)$, with widths defined actionwise on its own history:
\[
\begin{array}{ll@{\qquad}ll}
\text{transport Hessian:}&w_t=e^{D_{Q,t}/2}s_t,&
\text{transport endpoint:}&w_t=e^{d_{{\rm Th},t}/2}s_t,\\
\text{frozen reference:}&w_t=\bar s_t,&
\text{naive current:}&w_t=s_t.
\end{array}
\]
The primary Hessian policy sets $\Dbar_t=D_{Q,t}$; its name refers to the envelope argument, not a Hessian width. Frozen reference applies the current query to the collection-time Gram. Naive current omits transport. $\mathcal D_{{\rm quad},t}$ is the 32-point Gauss-Legendre estimate of the selected SPD path length, evaluated every ten rounds and at declared horizons. The path interpolates each replay parameter from $\theta_s$ to $\theta_t$ before forming the stacked Gram.
```

## Change 18: original lines 102 to 104; candidate lines 140 to 141

Reason: Use one compact table without changing the original footnote-sized table typography.

Old -> new:

```latex
\centering
\footnotesize
\begin{tabularx}{\textwidth}{@{}>{\raggedright\arraybackslash}p{0.27\textwidth}X@{}}
```

```latex
\centering\footnotesize
\begin{tabular}{@{}lrrrr@{}}
```

## Change 19: original lines 106 to 106; candidate lines 143 to 143

Reason: Show all four predeclared target conditions as columns.

Old -> new:

```latex
Diagnostic & Locked full-evaluation result \\
```

```latex
$D_{\rm target}$ & $0.25$ & $0.5$ & $1$ & $2$ \\
```

## Change 20: original lines 108 to 111; candidate lines 145 to 152

Reason: Report every absolute policy mean and the three diagnostic rows; identify the pooled-inflation row as proposed evidence addition C01.

Old -> new:

```latex
Recorded confidence and optimism & Primary policy: 50/50 trajectories in each of 12 horizon--condition cells; cellwise exact 95\% Clopper--Pearson interval $[92.9\%,100\%]$. These are all-action, all-round tolerance-based float64 diagnostics. \\
Transport-envelope conservatism & At $T=1000$, $D_Q/\mathcal D_{\rm quad}=2.51\times10^5$--$1.88\times10^6$. Conditionwise medians of run-maximum endpoint distance are $1.31\times10^{-7}$--$8.74\times10^{-6}$. \\
Bound informativeness & Across the 12 primary cells, median per-trajectory sharp RHS / pseudo-regret is $126.7$--$155.7\times$. At every declared terminal horizon, the numerically evaluated theorem RHS exceeded the deterministic $2T$ pseudo-regret cap for every primary-policy trajectory. \\
Policy comparison & At $T=1000$, comparison-minus-Hessian mean pseudo-regret differences range from about $-12.3$ to $-1.96$. All 12 comparisonwise, unadjusted 95\% paired-bootstrap intervals exclude zero below. \\
```

```latex
Transport Hessian mean $R_{1000}$ & 81.05 & 82.44 & 87.04 & 93.99 \\
Transport endpoint mean $R_{1000}$ & 79.05 & 79.49 & 80.06 & 81.89 \\
Frozen reference mean $R_{1000}$ & 79.09 & 80.13 & 80.25 & 81.67 \\
Naive current mean $R_{1000}$ & 79.00 & 79.49 & 80.10 & 81.88 \\
\midrule
Median $D_Q/\mathcal D_{\rm quad}$ & $1.88\times10^6$ & $9.77\times10^5$ & $4.82\times10^5$ & $2.51\times10^5$ \\
Median trajectory-maximum $d_{\rm Th}$ & $1.31\times10^{-7}$ & $5.23\times10^{-7}$ & $2.10\times10^{-6}$ & $8.74\times10^{-6}$ \\
Median $e^{D_Q/2}$ & 1.02 & 1.04 & 1.09 & 1.18 \\
```

## Change 21: original lines 113 to 114; candidate lines 154 to 155

Reason: Explain checkpoint, trajectory-maximum, and seed-round aggregation separately in the table caption.

Old -> new:

```latex
\end{tabularx}
\caption{Controlled audit. Float64 diagnostics and the numerical path diagnostic $\mathcal D_{\rm quad}$ are not verified enclosures. The same 50 base evaluation seeds are reused across cells rather than forming 600 independent trials; bootstrap resampling is paired by seed within each condition. Checkpoint path ratios are descriptive summaries, not direct confidence-bonus inflation factors.}
```

```latex
\end{tabular}
\caption{Primary horizon $T=1000$. Regret means average 50 trajectories. The last three rows concern the primary policy: path ratios pool eligible seed-checkpoint pairs with $\mathcal D_{\rm quad}>10^{-12}$; endpoint distances are maximized within each trajectory before taking the median; inflation medians pool seeds and all rounds, not terminal rounds or run maxima.}
```

## Change 22: original lines 118 to 118; candidate lines 159 to 159

Reason: Keep coverage and numerical bound informativeness once in the results, using descriptive policy comparisons and the mean-reward 2T cap.

Old -> new:

```latex
The controlled experiment records the specified algebraic, confidence, and optimism diagnostics; it does not prove or empirically validate the theorem. The diagnostic event held throughout evaluation, but the operational path envelope was highly conservative, the numerically evaluated regret bound was vacuous, and the comparison policies had lower mean pseudo-regret at the primary horizon. The paired comparisons are descriptive for the evaluated conditions: they do not establish per-seed dominance, a uniform method ordering, or a causal effect of certificate looseness.
```

```latex
All three comparison policies have lower sample mean regret in every evaluated condition at $T=1000$. In each of the 12 horizon-target cells, 50/50 primary trajectories passed both all-action, all-round reference-confidence and optimism diagnostics, with cellwise exact 95\% Clopper-Pearson interval $[92.9\%,100\%]$. Base seeds are reused across cells; no deterministic audit failed. These tolerance-based float64 checks and quadrature values are diagnostics, not verified enclosures. Across the 12 primary cells, medians of per-trajectory ratios of the numerical right-hand side (RHS) of \eqref{eq:regret} to pseudo-regret range from $126.7$ to $155.7$. Every primary trajectory's terminal RHS exceeds $2T$, the pseudo-regret cap from $|\mu^*(z)|\le1$, despite unbounded Gaussian observations.
```

## Change 23: original lines 121 to 121; candidate lines 162 to 162

Reason: Replace the repeated result catalogue with the limited allocation-design implication.

Old -> new:

```latex
Under the stated confidence and certificate assumptions, transport yields an optimistic score and a conditional regret bound. In our controlled study, the float64 confidence and optimism diagnostics passed, while the numerically evaluated regret bound was vacuous and the comparison policies had lower mean pseudo-regret at the primary horizon. These observations do not verify exact membership in the mathematical events or establish that certificate looseness caused the regret differences. For adaptive experimentation, maintaining coherent uncertainty under model updates and obtaining a practically useful allocation rule are separate design problems.
```

```latex
Certificate validity and allocation performance require separate assessments. A large path-envelope ratio need not imply a comparably large bonus; the policy comparisons do not identify why regret differs.
```

## Change 24: original lines 125 to 127; candidate lines 166 to 169

Reason: Use verified exact reference titles and add the verified Nussbaum attribution for the existing geometric machinery.

Old -> new:

```latex
\bibitem{abbasi2011improved} Y. Abbasi-Yadkori, D. P\'al, and C. Szepesv\'ari. Improved algorithms for linear stochastic bandits. \emph{NeurIPS}, 2011.
\bibitem{zhou2020neural} D. Zhou, L. Li, and Q. Gu. Neural contextual bandits with UCB-based exploration. \emph{ICML}, 2020.
\bibitem{riquelme2018deep} C. Riquelme, G. Tucker, and J. Snoek. Deep Bayesian bandits showdown. \emph{ICLR}, 2018.
```

```latex
\bibitem{abbasi2011improved} Y. Abbasi-Yadkori, D. P\'al, and C. Szepesv\'ari. Improved Algorithms for Linear Stochastic Bandits. \emph{NeurIPS}, 2011.
\bibitem{zhou2020neural} D. Zhou, L. Li, and Q. Gu. Neural Contextual Bandits with UCB-based Exploration. \emph{ICML}, 2020.
\bibitem{riquelme2018deep} C. Riquelme, G. Tucker, and J. Snoek. Deep Bayesian Bandits Showdown: An Empirical Comparison of Bayesian Deep Networks for Thompson Sampling. \emph{ICLR}, 2018.
\bibitem{nussbaum1994finsler} R. D. Nussbaum. Finsler structures for the part metric and Hilbert's projective metric and applications to ordinary differential equations. \emph{Differential and Integral Equations}, 7, 1994.
```
