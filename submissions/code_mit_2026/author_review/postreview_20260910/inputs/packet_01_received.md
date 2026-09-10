## 1. Live Git state and files inspected

```text
Repository: buiksat/Curvature-Calibrated-Exploration
Branch:     cce-experiments
HEAD:       5718995cae80f34b5b98b464f3d9090758be4871
Commit:     paper: publish revised CODE@MIT draft and author review records
```

HEAD was resolved before inspection and rechecked afterward; it remained unchanged. All repository reads were pinned to this SHA.

**Scientific decision:** approve the direct-sandwich formulation with an explicit change of certificate interface; approve qualified endpoint-certificate terminology, the near-linearity inequality, and the within-condition policy-ablation interpretation. The numerical bound-decomposition paragraph remains **gated on 02's verification**. These decisions do not constitute author consent or final submission approval.

Inspected:

| FilesRelevant content                                                                     |                                                                                                                                                   |
| ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `submissions/code_mit_2026/main.tex`                                                      | Complete current source, including `thm:transfer`, `eq:certificates`, `eq:score`, `eq:experiment-scale`, and `tab:audit`                          |
| `author_review/records/AUTHOR_APPROVAL.md`, `OPTIONAL_ANALYSES.md`                        | Pending approvals, descriptive-reporting preference, existing decomposition and pooling definitions                                               |
| `paper/transport_theory.tex`, `paper/transport_proofs.tex`                                | Abstract theorem, path/endpoint geometry, corrected-center construction, solver and probability interfaces                                        |
| `experiments/transport_instantiation.py`                                                  | Scale rule, feature normalization, scores, generalized eigenvalues, path quadrature, common streams, selected-reward updates, bound decomposition |
| `experiments/TRANSPORT_INSTANTIATION_PROTOCOL.md`, `configs/transport_instantiation.yaml` | Frozen design, parameter bounds, policy definitions, tuning and evaluation separation                                                             |
| `experiments/aggregate_transport_instantiation.py:1180–1258`                              | Paired-comparison fields and trajectory-mean decomposition                                                                                        |

The author ledger explicitly requests descriptive absolute regret reporting and removal of the bootstrap zero-exclusion count. It also leaves author metadata, venue confirmation, pooled-inflation inclusion, and contribution wording unresolved.

No repository file, ledger, evidence, or branch state was changed. No experiment was run.

## 2. Decision table

Line numbers below refer to the current **`submissions/code_mit_2026/main.tex`**, not the external review's filename. Referenced blocks below are the exact replacement text; derivations and verification tables are review material, not proposed additions to the three-page paper.

| ID / locationDecisionMathematical or interpretive reasonExact replacement wording |                                                |                                                                                                                                                                                                                                                               |                                                                                        |
| --------------------------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| **A01 — lines 61–96,** **`thm:transfer`**                                         | **APPROVED WITH MODIFICATION**                 | Direct sandwiches suffice for every step of the existing regret proof. This changes the stated certificate interface; it is not merely deletion of the path premise.                                                                                          | **Block A01** below.                                                                   |
| **A02 — line 43, protocol**                                                       | **APPROVED WITH MODIFICATION**                 | Retain finite-action, pre-reward randomized-object scope with **supplied simultaneous event-probability bounds**. Do not claim to construct valid randomized certificates from point checks.                                                                  | **Block A02** below.                                                                   |
| **B01 — line 128, endpoint description**                                          | **APPROVED WITH MODIFICATION**                 | The endpoint quantity is learner-computable and supplies an exact-arithmetic certificate. Its float64 evaluation is not a verified enclosure.                                                                                                                 | **Block B01**, using "dense endpoint-certificate comparator."                          |
| **B02 — line 137, path terminology**                                              | **APPROVED**                                   | The deterministic ordering concerns the exact integral, not unenclosed quadrature.                                                                                                                                                                            | **Block B02** below.                                                                   |
| **C01 — after line 125,** **`eq:experiment-scale`**                               | **APPROVED**                                   | The inequality follows from integrating `\tanh^2 x\le x^2`; the domain bounds and four design values check out.                                                                                                                                               | **Block C01** below.                                                                   |
| **D01 — first sentence of line 159**                                              | **APPROVED WITH MODIFICATION**                 | Hessian versus naive current is a one-component policy intervention at a given state. History divergence is part of its total effect, not a confound that invalidates the contrast.                                                                           | **Block D01** below; preserve the remainder of line 159.                               |
| **E01 — optional addition after line 159**                                        | **APPROVED WITH MODIFICATION; NUMERICAL HOLD** | Same-trajectory removal is an algebraic attribution diagnostic. "Not principal" additionally requires the path-component share, not merely `B_0>2T`.                                                                                                          | **Block E01**, only after 02 verifies the summaries and the author approves inclusion. |
| **F01 — line 100**                                                                | **APPROVED**                                   | Remove overloaded notation without changing the frozen-query construction.                                                                                                                                                                                    | Replace `$q_s=q_s(a_s)$` by `$q_s:=q_{\theta_s}(x_s,a_s)$`.                            |
| **F02 — line 97; citation at line 169**                                           | **APPROVED WITH MODIFICATION**                 | Describe certificate composition rather than claiming the underlying geometry as new. No new neural-bandit comparison is needed.                                                                                                                              | **Block F02** below; retain the existing Nussbaum citation.                            |
| **R01 — review overclaims**                                                       | **REJECTED**                                   | Neither the theorem nor the experiment supports universal endpoint dominance, zero endpoint regret cost, naive optimism from small distance, a universal `10^{-5}` endpoint bound, machine-precision linearity, or a cross-condition inflation dose response. | Do not insert these claims. Qualified replacements are B01–E01.                        |

The current theorem indeed retains a path-length premise; the current experiment text calls the endpoint policy a diagnostic oracle. The changes above therefore need to be recorded as revisions, not described as text already present in the source.

## 3. Compact theorem and supporting assumptions

### Block A02 — replace line 43

This scope retains pre-reward randomization but assumes any claimed **joint certificate probability** directly. It does not establish a failure-allocation procedure for adaptive randomized verification. That construction remains in the full paper, where validity is conditioned on the sigma-algebra immediately preceding each draw.

```latex
At round $t\le T$, observe $x_t$, choose $a_t$ from a fixed finite
nonempty set $\mathcal A$, then observe $r_t$. Our confidence target
is the conditional mean reward $\mu_t^*(a)$ used for allocation,
not a treatment-effect estimand. Let
$\mathcal H_t^-$ precede fresh round-$t$ randomization $\Omega_t$ and
$\mathcal H_t=\mathcal H_t^-\vee\sigma(\Omega_t)$ contain all
pre-reward information. Queries $q_t(a)\in\R^d$ use fixed coordinates
and dimension. The reference and exact current metrics,
$\beta_t\ge0$, and $\theta_t$ when used are
$\mathcal H_t^-$-measurable (predictable). All remaining score inputs
and the selected action are finite and $\mathcal H_t$-measurable,
actionwise; each selected query is fixed before its reward.
All validity events are measurable, and any claimed certificate
probability is a supplied simultaneous bound.
```

Keep the existing geometry, pseudo-regret, information-gain, and width definitions in **lines 45–59**.

### Block A01 — replace lines 61–96

```latex
\begin{theorem}[Finite-action confidence transfer]\label{thm:transfer}
Under this protocol, suppose $\|q_t(a)\|_2\le G<\infty$.
Define $E_{\rm conf}$ as the event that, simultaneously for
$t\le T$ and $a\in\mathcal A$,
\begin{equation}
|\mu_t^*(a)-m_t(a)|
\le\beta_t\bar s_t(a)+b_t(a),\qquad b_t(a)\ge0.
\label{eq:refconf}
\end{equation}
Let $\Dbar_t\ge0$,
$0<\kappa_{-,t}\le\kappa_{+,t}<\infty$, and
$1\le\alpha_t<\infty$ be finite pre-reward factors.
Define $E_{\rm cert}$ as simultaneous validity, for every $t\le T$,
of the Loewner comparisons
\begin{equation}
e^{-\Dbar_t}\Vbar_t\preceq V_t\preceq e^{\Dbar_t}\Vbar_t,\qquad
\kappa_{-,t}V_t\preceq C_t\preceq\kappa_{+,t}V_t,
\label{eq:certificates}
\end{equation}
and, for a nonnegative pre-reward width map,
\begin{equation}
s_{C,t}(a)\le\shat_t(a)\quad(a\in\mathcal A),\qquad
\shat_t(a_t)\le\alpha_t s_{C,t}(a_t).
\label{eq:solver}
\end{equation}
Use this same realized width map in the score and selector:
\begin{equation}
U_t(a)=m_t(a)+\beta_t e^{\Dbar_t/2}
\sqrt{\kappa_{+,t}}\,\shat_t(a)+b_t(a),\qquad
U_t(a_t)\ge\max_{a\in\mathcal A}U_t(a)-\xi_t,\quad\xi_t\ge0.
\label{eq:score}
\end{equation}
Changing a scored width after selection requires rechecking the
selector inequality. On $E_{\rm conf}\cap E_{\rm cert}$,
$U_t(a)\ge\mu_t^*(a)$ for every action and round, and pathwise
\begin{equation}
\begin{aligned}
R_T\le{}&
\sqrt{\left(\sigma^2+\frac{G^2}{\lambda}\right)\gamma_T
\sum_{t=1}^T\beta_t^2
\left[1+\alpha_t e^{\Dbar_t}
\sqrt{\frac{\kappa_{+,t}}{\kappa_{-,t}}}\right]^2}\\
&+2\sum_{t=1}^T b_t(a_t)+\sum_{t=1}^T\xi_t.
\end{aligned}
\label{eq:regret}
\end{equation}
If $\Pr(E_{\rm conf})\ge1-\delta$ and
$\Pr(E_{\rm cert})\ge1-\delta_{\rm cert}$, these conclusions hold
with probability at least $1-\delta-\delta_{\rm cert}$;
independence is unnecessary.
\end{theorem}
```

This preserves the actual score, all-action upper validity, played-action-only sharpness, `2b_t(a_t)`, `\xi_t`, and the unchanged sharp regret expression. The abstract result still assumes reference confidence rather than deriving it from arbitrary model updates.

### Block F02 — replace line 97

```latex
Theorem~\ref{thm:transfer} states the certificate composition directly.
Classical Thompson geometry supplies endpoint and path-length
constructions of its first metric comparison
\cite{nussbaum1994finsler}. The corrected-center construction below
supplies reference confidence without nonlinear optimizer convergence.
```

Keep the corrected-center assumptions and equations in **lines 100–116**, apart from F01's explicit selected-query definition. In particular, retain the fixed ex-ante reference, noise conditioning on `\mathcal H_t`, pre-reward error envelopes, historical `1/\sigma` contribution, current bias, and exact auxiliary frozen-estimator access. Those are genuine obligations, not expendable exposition.

## 4. Short derivations

### Direct-sandwich sufficiency

The first sandwich gives, by inversion,

```math
\bar s_t(a)\le e^{\bar D_t/2}s_t(a), \qquad s_t(a)\le e^{\bar D_t/2}\bar s_t(a).
```

The operator sandwich gives

```math
s_t(a)\le\sqrt{\kappa_{+,t}}\,s_{C,t}(a), \qquad s_{C,t}(a)\le\kappa_{-,t}^{-1/2}s_t(a).
```

Consequently, all-action solver upper validity makes `U_t` optimistic. Approximate maximization and lower confidence at the played action yield

```math
\operatorname{reg}_t \le \beta_t\bar s_t(a_t) +\beta_te^{\bar D_t/2}\sqrt{\kappa_{+,t}}\widehat s_t(a_t) +2b_t(a_t)+\xi_t.
```

Played-action sharpness and transport back give exactly

```math
\operatorname{reg}_t \le \beta_t\!\left[ 1+\alpha_te^{\bar D_t} \sqrt{\kappa_{+,t}/\kappa_{-,t}} \right]\bar s_t(a_t) +2b_t(a_t)+\xi_t.
```

Cauchy–Schwarz and

```math
\sum_{t=1}^T\bar s_t(a_t)^2 \le \left(\sigma^2+\frac{G^2}{\lambda}\right)\gamma_T
```

finish the proof. These are precisely the existing proof steps after its initial path-to-sandwich implication.

**Classification:** a **sufficient-certificate reformulation justified by the existing proof**, requiring explicit approval of the revised CODE statement. It is not merely a typographical change.

There is an important nuance. On the full SPD cone, a sandwich is equivalent to the existence of *some* sufficiently short path: for `A=\bar V_t`, `M=A^{-1/2}V_tA^{-1/2}`, the path

```math
A^{1/2}M^\tau A^{1/2}
```

has Thompson length `\|\log M\|_{\rm op}`. But a sandwich does **not** upper-bound a specified replay path's length; a loop can have equal endpoints and positive length. The revision must not reinterpret the recorded selected-path certificate or its quadrature. The manuscript already distinguishes endpoint distance from selected-path length.

### Near-linearity

Set `x=|u|/\sqrt W`. For `x\ge0`, `0\le\tanh x\le x`, and

```math
x-\tanh x =\int_0^x\tanh^2 v\,dv \le\int_0^xv^2\,dv =\frac{x^3}{3}.
```

For `u\ne0`, oddness of `\tanh` therefore gives

```math
0\le1-\frac{\sqrt W\tanh(u/\sqrt W)}{u} \le\frac{u^2}{3W}.
```

At zero, define the ratio by its limit `1`, so the relative discrepancy is `0`.

The experiment's domain satisfies

```math
|u|=|\phi(z)^\top\theta| \le\|\phi(z)\|_2\|\theta\|_2\le1.
```

This applies to the reference parameter, scoring parameters, and segments between parameters in the radius-one ball. It does not assert that every intermediate unprojected gradient-descent iterate is inside that ball. Feature normalization and the end-of-update projection are explicit in the implementation.

At `T=1000`, the frozen rule simplifies in exact arithmetic to

```math
W=\frac{151552}{D_{\rm target}^2}.
```

| `D_{\rm target}W`Uniform relative-error upper bound `1/(3W)` |           |                             |
| ------------------------------------------------------------ | --------- | --------------------------- |
| 0.25                                                         | 2,424,832 | `1.3746656813\times10^{-7}` |
| 0.5                                                          | 606,208   | `5.4986627252\times10^{-7}` |
| 1                                                            | 151,552   | `2.1994650901\times10^{-6}` |
| 2                                                            | 37,888    | `8.7978603604\times10^{-6}` |

These are **verified design-rule calculations**, not newly estimated experimental statistics. The runner evaluates the real-valued formula in float64; the protocol does not round `W` to an integer.

### Block C01 — insert after `eq:experiment-scale`, line 125

```latex
At $T=1000$, the chosen scales make the model uniformly close to
its linear counterpart on the stated domain. For
$u=\phi(z)^\top\theta$, $|u|\le1$, and
$f_W(u)=\sqrt W\tanh(u/\sqrt W)$,
\[
0\le1-\frac{f_W(u)}u
\le\frac{u^2}{3W}\le\frac1{3W},
\]
with $f_W(u)/u=1$ by continuity at zero. The four conditionwise
uniform upper bounds range from $1.375\times10^{-7}$ to
$8.798\times10^{-6}$. This quantifies the study's near-linearity;
it is not floating-point exactness or a restriction on what
other transport certificates can achieve.
```

Do not replace this with "linear to numerical precision." Do not infer that useful transport certificates require nearly linear models.

## 5. Approved experiment wording and interpretation

### Endpoint certificate: exact scope

Let `\lambda_i(V_t,\bar V_t)` solve

```math
V_tv_i=\lambda_i\bar V_tv_i.
```

These are the eigenvalues of `M=\bar V_t^{-1/2}V_t\bar V_t^{-1/2}`. Thus

```math
e^{-r}\bar V_t\preceq V_t\preceq e^r\bar V_t \iff e^{-r}\le\lambda_i\le e^r\quad\forall i.
```

The smallest admissible common nonnegative exponent is therefore

```math
\boxed{ d_{\rm Th}(\bar V_t,V_t) =\max_i|\log\lambda_i(V_t,\bar V_t)|. }
```

The implementation calls `eigh(current_matrix, reference_matrix, ...)`, matching this orientation. SciPy's type-1 generalized problem is `Av=\lambda Bv`. Reversing the two matrices reciprocates the eigenvalues and leaves this symmetric distance unchanged, but swaps the one-sided comparisons. ([SciPy Documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.eigh.html "https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.eigh.html"))

The minimality claim is **only** about a common exponent for the symmetric all-direction sandwich. It is not optimality among action-specific, one-sided, statistical, or policy-dependent certificates.

Both matrices are available from learner history before the reward. Exact-arithmetic endpoint transport therefore does not require unknown rewards or the reference parameter. Ordinary float64 eigenvalues remain estimates; verified certification would need enclosing spectral bounds, including relevant matrix-construction error. The current runner performs this spectral calculation for every method, so its timing cannot establish the endpoint policy's incremental overhead.

### Block B01 — replace line 128, before the existing width array

```latex
The transport-endpoint policy is a dense endpoint-certificate
comparator. It substitutes
$d_{{\rm Th},t}=\max_i|\log\lambda_i(V_t,\Vbar_t)|$, where
$V_tv_i=\lambda_i\Vbar_tv_i$. This is the smallest nonnegative
common exponent for the symmetric all-direction sandwich in
\eqref{eq:certificates} \cite{nussbaum1994finsler}, not an optimum
over action-specific or statistical certificates. Both matrices
are learner-known before reward observation. The certificate is
valid in exact arithmetic; its float64 evaluation is not a verified
enclosure. Every method's runner computes these eigenvalues, so
reported runtime does not isolate the endpoint policy's incremental
cost. Each policy scores
$m_t^{\rm corr}(a)+\beta_t^{\rm corr}w_t(a)+b_t(a)$ on its own history:
```

Keep the existing four score definitions at **lines 129–136** unchanged.

### Block B02 — replace line 137

```latex
The primary policy uses $\Dbar_t=D_{Q,t}$; ``Hessian'' refers to
the envelope argument, not its GGN width. Frozen reference applies
the current query to the collection-time Gram; naive current omits
transport. Let $\mathcal D_{{\rm selected},t}$ be the exact
Thompson--Finsler length of the SPD path obtained by interpolating
each replay parameter from $\theta_s$ to $\theta_t$. Analytically,
$d_{{\rm Th},t}\le\mathcal D_{{\rm selected},t}\le D_{Q,t}$.
$\mathcal D_{{\rm quad},t}$ estimates this integral using 32-point
Gauss--Legendre quadrature at the declared checkpoints; unenclosed
quadrature cannot replace the exact integral in that inequality.
```

The implementation integrates the normalized **SPD derivative** along the synthetic replay path; it does not numerically integrate the looser factor-norm upper bound.

Reject all four endpoint overclaims specified in the task. In particular, the table reports **medians of trajectory maxima**, not a universal `d_{\rm Th}\le10^{-5}` bound. Small positive distance does not ensure that an uninflated current width covers the reference width.

### Within-condition policy interpretation

The executable scores are

```math
U_t^Q=m_t^{\rm corr}+\beta_t^{\rm corr}e^{D_{Q,t}/2}s_t+b_t, \qquad U_t^{\rm naive}=m_t^{\rm corr}+\beta_t^{\rm corr}s_t+b_t.
```

The state initialization, confidence construction, width computation, update rule, and selected-reward handling are shared. Method-independent child seeds generate the common context and potential-noise streams. These facts support a **total policy contrast** between enabling and omitting the analytic multiplier within a fixed `(T,D_{\rm target})` condition.

After actions diverge, realized centers, radii, widths, and training histories need not match. Those changes are downstream effects of the intervention. They prevent interpreting the contrast as a fixed-history geometric effect, but do not invalidate the total policy contrast.

### Block D01 — replace only the first sentence of line 159

```latex
Within each fixed $T=1000$ condition, enabling the analytic
transport multiplier in the otherwise matched current-width
policy increased sample mean cumulative pseudo-regret relative
to omitting it (Table~\ref{tab:audit}). The policies use the same
state-to-score and update rules apart from this multiplier, with
common context and potential-noise streams; their subsequent
histories may diverge. This descriptive total-policy contrast
does not identify a fixed-history mechanism, per-seed dominance,
or a cross-condition dose response, since $D_{\rm target}$ also
changes $W$.
```

The absolute means already in the source support the stated direction in all four conditions. Retain those means and the author's descriptive presentation. Do not restore significance language.

For uncertainty, the appropriate unit is the paired seed difference:

```math
\Delta_i=R^{Q}_{T,i}-R^{\rm naive}_{T,i},\qquad \widehat{\mathrm{SE}}(\bar\Delta)=s_\Delta/\sqrt{50}.
```

**Numerical paired standard errors await 02's extraction/verification.** Their possible inclusion is separate from approval of D01; no uncertainty values are invented here. The aggregator already records paired-difference summaries.

### Bound vacuity: interpretation approved, numerical insertion held

For each primary trajectory, write

```math
P=\left(\sigma^2+\frac{G^2}{\lambda}\right)\gamma_T,
```

```math
B_D=\sqrt{P\sum_t[\beta_t(1+e^{D_{Q,t}})]^2}+2\sum_tb_t, \qquad B_0=\sqrt{P\sum_t(2\beta_t)^2}+2\sum_tb_t.
```

The implementation's stored path increment is exactly `B_D-B_0`, and the aggregator averages the already computed per-trajectory components. It does not first average the inputs and then evaluate the nonlinear bound.

Two distinctions are necessary:

**First**, `B_0>2T` by itself establishes that vacuity persists without the explicit path term. It does not, alone, establish that transport is not the principal contributor: the removed term could still dwarf `B_0`.

**Second**, the available decomposition supports the stronger interpretation only after verifying its component shares. Arithmetic from the review ledger gives the following **candidate summaries, pending 02's independent verification**:

| TargetCandidate mean `B_0`Mean `B_0/(2T)(\overline{B_D}-\overline{B_0})/\overline{B_D}` |           |       |        |
| --------------------------------------------------------------------------------------- | --------- | ----- | ------ |
| 0.25                                                                                    | 10,016.38 | 5.008 | 2.01%  |
| 0.5                                                                                     | 10,093.72 | 5.047 | 4.04%  |
| 1                                                                                       | 10,252.50 | 5.126 | 8.16%  |
| 2                                                                                       | 10,556.24 | 5.278 | 16.27% |

The last column is a **ratio of means**, not a mean or median of trajectory-level component ratios. These calculations use the existing recorded mean components; publication must await 02's check.

### Block E01 — optional insertion after line 159; **do not apply before 02 verification**

```latex
A post-review same-trajectory attribution diagnostic sets every
$D_{Q,t}$ in the evaluated RHS to zero while retaining the recorded
history, $\beta_t$, $\gamma_T$, and $b_t$. At $T=1000$, the resulting
conditionwise means remain about $5.0$--$5.3$ times the cap $2T$.
The removed path increment accounts for about $2.0\%$--$16.3\%$
of the mean RHS, using ratios of means. Thus most of the reported
mean bound remains without the explicit path contribution.
These no-path values are attribution diagnostics, not guarantees
for the executed policy or results from a separately run linear policy.
```

The decomposition is ordered: its "statistical" component includes ridge bias, and its path increment includes interaction with the historical radius. Do not call it a unique causal decomposition of regret or infer that every trajectory has the reported mean pattern. No terminal or pooled-median inflation can replace the full sequence inside `B_D`.

## 6. Proposed abstract and conclusion revisions

These versions do **not** depend on the pending E01 numerical summary.

### Block ABSTRACT — replace lines 35–37

```latex
\begin{abstract}
Model updates change the sensitivities used for allocation, while
reward confidence may rely on sensitivities fixed when observations
were collected. We give a finite-action confidence-transfer result
under explicit pre-reward metric and solver certificates, yielding
reward optimism and a regret bound on their joint validity event.
Under fixed-reference and approximation-envelope assumptions, a
corrected center supplies confidence without nonlinear optimizer
convergence. A controlled nearly linear, 29-parameter simulation
records simultaneous float64 confidence and optimism diagnostics,
yet the evaluated regret bound is vacuous. Within each primary-horizon
condition, enabling the analytic transport multiplier increases sample
mean pseudo-regret relative to omitting it in an otherwise matched policy.
\end{abstract}
```

The corrected-center qualification follows its exact proof; the empirical direction and float64 qualification are supported by the current source and implementation.

### Block CONCLUSION — replace line 162

```latex
The theorem supplies reward optimism and a regret bound on the joint
confidence and certificate event; certificate validity alone does
not ensure useful allocation. In this nearly linear simulation,
the analytic multiplier increased sample mean pseudo-regret relative
to its omission within each fixed condition. This does not establish
a uniform policy ordering, a cross-condition dose response, or
treatment-effect inference after adaptive assignment.
```

### Citation disposition

**No new bibliography entry is necessary.** Retain `nussbaum1994finsler`, now attached to the endpoint/path certificate discussion. I checked the author-hosted primary paper: equation (1.5) gives the part/Thompson metric, equation (1.9) supplies the order-unit norm, and Theorem 1.2 and Remark 1.5 provide the Finsler length interpretation. These support the geometry, not the bandit theorem or empirical superiority. ([Department of Mathematics](https://sites.math.rutgers.edu/~nussbaum/Pubs/Finsler.pdf "https://sites.math.rutgers.edu/~nussbaum/Pubs/Finsler.pdf"))

A permissible completeness edit at line 169 is to end the existing entry with:

```latex
\emph{Differential and Integral Equations}, 7:1649--1707, 1994.
```

Do not add a named NeuralUCB convergence comparison in this revision. Do not identify the implemented frozen-reference comparator with a published neural-bandit algorithm: its definition is the current query applied to the collection-time Gram, with the same corrected-center construction.

## 7. Unresolved author decisions

There is no unresolved algebraic issue blocking A01–D01. The remaining decisions are consent and evidence-release decisions:

| DecisionStatus                                                                  |                                                                                                |
| ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Adopt the direct-certificate theorem interface and revised contribution wording | Scientifically approved here; author approval still required                                   |
| Adopt the stronger descriptive total-policy interpretation                      | Scientifically approved; no significance language proposed                                     |
| Include the new analytic near-linearity statement                               | Scientifically approved; author approval of the manuscript addition remains                    |
| Include E01 and any paired standard errors or terminal-inflation summary        | Await 02 verification and author approval; label new derived summaries as post-review analysis |
| Existing `AUTH01`, `AUTH02`, `C01`, `C02`                                       | Remain unresolved unless separately approved; this packet does not close them                  |

The visible author-review marker and current title must remain until the corresponding author decisions are resolved. Three-page fit has not been tested in this read-only review; 05 must rebuild and inspect rather than silently delete hypotheses or alter formatting to force a fit.

---

## 8. Scientific review packet for 05

**BEGIN SCIENTIFIC REVIEW PACKET FOR 05**

```text
Repository:
https://github.com/buiksat/Curvature-Calibrated-Exploration

Scientific branch:
cce-experiments

Reviewed starting SHA:
5718995cae80f34b5b98b464f3d9090758be4871

Target:
submissions/code_mit_2026/main.tex

Status:
Scientific approval of the specified changes, not author consent,
permission to modify now, or final submission approval.

Before implementation:
Resolve cce-experiments HEAD again. If the target or approval records
changed, reconcile against the reviewed SHA and these source labels.
Do not use main as the scientific source.

Approved replacement blocks in this packet:
A02: replace current line 43.
A01: replace lines 61–96, preserving thm:transfer and existing labels.
F02: replace line 97.
F01: at line 100 replace q_s=q_s(a_s) with
     q_s:=q_{theta_s}(x_s,a_s).
C01: insert after eq:experiment-scale, current line 125.
B01: replace current line 128; retain the score array at lines 129–136.
B02: replace current line 137.
D01: replace only the first sentence of current line 159;
     retain its remaining coverage and bound-reporting statements.
ABSTRACT: replace the abstract at lines 35–37.
CONCLUSION: replace current line 162.
Optional citation completion: add the page range to the existing
Nussbaum entry at line 169. No new neural-bandit citation/comparison.

E01 is on numerical hold:
Apply only after 02 verifies the same-trajectory decomposition,
conditionwise means, cap comparisons, and ratios-of-means definition,
and the author approves inclusion. Any new derived summary must be
labelled post-review analysis. Do not insert unverified paired SEs or
terminal-inflation summaries.

Scientific invariants:
- Direct sandwich is a sufficient-certificate formulation justified by
  the existing proof; do not call it an unchanged selected-path premise.
- Keep pathwise event conditioning and probability only under supplied
  simultaneous event-probability bounds.
- Keep all-action upper validity, played-action sharpness, the actual
  score, approximate selector, and one realized solver-width map.
- Retain fixed-reference corrected-center assumptions, pre-reward
  query/noise timing, historical 1/sigma scaling, current bias, and
  frozen-estimator access.
- Endpoint minimality is only for the common symmetric all-direction
  exponent. Float64 evaluation is not verified certification.
- Use d_Th <= D_selected <= D_Q only for exact quantities.
- The policy contrast is within-condition and includes downstream
  history divergence; D_target also changes W.
- No significance language, universal dominance, machine-precision
  linearity, or valid-no-path-guarantee claim.
- Keep method identifiers, locked artifacts, and historical provenance
  terminology unchanged; narrative terminology changes are CODE-local.

Implementation boundaries, once separately authorized:
Edit only approved CODE-local manuscript content and rebuild its PDF.
Do not change paper/, experiment code, configs, evidence, or historical
approval records. Do not mark scientific approval as author consent.
Do not regenerate locked artifacts or run new experiments.
Do not commit, push, mirror to main, or open a PR without permission.

Verification:
Check labels/citations and the source diff; rebuild from the CODE
directory with:
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

Inspect the rendered PDF, mathematical displays, table captions, and
three-page count. Report a page-fit problem rather than weakening
assumptions, shrinking the established format, or dropping qualifiers.
Retain the author-review marker while author decisions remain pending.

Only the marked replacement blocks belong in CODE. The derivations,
verification tables, implementation notes, and this packet are review
material.
```

**END SCIENTIFIC REVIEW PACKET FOR 05**