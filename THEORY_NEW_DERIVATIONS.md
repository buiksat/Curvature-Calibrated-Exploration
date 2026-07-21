# New Theory Derivations

Audit date: 2026-07-20

This note derives the requested Phases 1A--1E, 2A--2C, and 3A--3B in the
notation of `paper/main.tex`.  It is not part of the manuscript.  Two different
quantities must remain distinct throughout:

- `\hat\gamma_t` is the transferred-CG surrogate for the frozen information
  gain used in the confidence radius (Corollary 13).
- `\widehat{\Lambda}^{\Calg}_T` is the CG surrogate for the realized
  algorithmic width complexity used in the regret bound (Corollary 8).

The symbol $R_T$ remains cumulative regret.  To avoid colliding with it, the
sum of squared collection residuals requested below is denoted
$R_t^{\rm col}$.

## Phase 1A: online displacement and residual statistics

Let $n=t-1$.  For $n>0$, define the pre-round displacement mean and scalar
scatter

\[
 \bar\btheta_{<t}:=\frac1n\sum_{s<t}\btheta_s,
 \qquad
 J_{<t}:=\sum_{s<t}\|\btheta_s-\bar\btheta_{<t}\|^2.
\]

Define

\[
 Q_t:=J_{<t}+n\|\btheta_t-\bar\btheta_{<t}\|^2,
 \qquad Q_1:=0.
\]

Then the exact parallel-axis identity is

\[
 \boxed{Q_t=\sum_{s<t}\|\btheta_t-\btheta_s\|^2.}
\]

Indeed, writing
$\btheta_t-\btheta_s=(\btheta_t-\bar\btheta_{<t})
 +(\bar\btheta_{<t}-\btheta_s)$, the cross term vanishes because
$\sum_{s<t}(\bar\btheta_{<t}-\btheta_s)=0$.

The mean and scatter have the Welford update.  Initialize
$m_1=\btheta_1$ and $J_1=0$.  If $m_k$ and $J_k$ summarize
$\btheta_1,\ldots,\btheta_k$, then for $k\ge2$ set

\[
 d_k:=\btheta_k-m_{k-1},\qquad
 m_k=m_{k-1}+\frac{d_k}{k},\qquad
 J_k=J_{k-1}+d_k^\top(\btheta_k-m_k)
     =J_{k-1}+\frac{k-1}{k}\|d_k\|^2.
\]

Thus $Q_t$ needs one $d$-vector and two scalars, not all past checkpoints.

For $z_s=(\bx_s,a_s)$ define the signed collection residual

\[
 c_s:=\mu_{\btheta_s}(z_s)-r_s,
 \qquad
 R_t^{\rm col}:=\sum_{s<t}c_s^2,
 \qquad R_1^{\rm col}:=0.
\]

It has the scalar update $R_{t+1}^{\rm col}=R_t^{\rm col}+c_t^2$.  Both $Q_t$
and $R_t^{\rm col}$ are $\cF_{t-1}$-measurable once $\btheta_t$ has been formed,
hence are $\cHist_t$-measurable.

## Phase 1B: operational whitened-drift transfer

Assume the Jacobian is globally $L_g$-Lipschitz on the certified parameter
region.  With the paper's
$\Delta_{s,t}=\|\btheta_t-\btheta_s\|$, Lemma 4 gives

\[
 \chi_t
 \le \frac{L_g}{\sigma\sqrt\lambda}
       \left(\sum_{s<t}\Delta_{s,t}^2\right)^{1/2}
 =\frac{L_g}{\sigma\sqrt\lambda}\sqrt{Q_t}
 =:\bar\chi_t.
\]

Consequently:

\[
 u_t=(1+\bar\chi_t)^2
\]

is a valid uniform actionwise transfer factor when
$\Calg_t=\bC_t$.  It is also valid for an unrescaled current-parameter subset
or window, because Proposition 15 gives $\Calg_t=\hat\bC_t\preceq\bC_t$ and
therefore $\kappa_{+,t}=1$.  For any other predictable approximate operator
with a certified

\[
 \hat\bC_t\preceq\kappa_{+,t}\bC_t,
\]

Theorem 16 gives

\[
 \boxed{u_t=\kappa_{+,t}(1+\bar\chi_t)^2.}
\]

The factor $\kappa_{+,t}$ must be a genuine $\cHist_t$-measurable upper
certificate, not an unenclosed eigenvalue estimate computed after the action.

## Phase 1C: operational centering certificate

Write $d_{s,t}:=\|\btheta_t-\btheta_s\|$.  In Lemma 3's notation,

\[
 \bar r_{s,t}
 =\mu_{\btheta_s}(z_s)+\bg_s^\top(\btheta_t-\btheta_s)-r_s
 =c_s+\bg_s^\top(\btheta_t-\btheta_s).
\]

Under $\|\bg_s\|\le G$ and an $L_g$-Lipschitz Jacobian,

\[
 |\bar r_{s,t}|\le |c_s|+Gd_{s,t},\qquad
 \|\delta_{s,t}\|\le L_gd_{s,t},\qquad
 |e_{s,t}|\le\frac{L_g}{2}d_{s,t}^2.
\]

The norm of one summand in $M_t$ is therefore at most

\[
\begin{aligned}
 &|\bar r_{s,t}|\,\|\delta_{s,t}\|
 +|e_{s,t}|\,\|\bg_s\|
 +|e_{s,t}|\,\|\delta_{s,t}\|\\
 &\quad\le
 L_g|c_s|d_{s,t}
 +\frac{3GL_g}{2}d_{s,t}^2
 +\frac{L_g^2}{2}d_{s,t}^3.
\end{aligned}
\]

The coefficient $3/2$ is the sum of $1$ from
$Gd_{s,t}\cdot L_gd_{s,t}$ and $1/2$ from
$(L_g/2)d_{s,t}^2\cdot G$.

Cauchy--Schwarz and monotonicity of finite-dimensional $\ell_p$ norms give

\[
 \sum_{s<t}|c_s|d_{s,t}\le\sqrt{R_t^{\rm col}Q_t},\qquad
 \sum_{s<t}d_{s,t}^2=Q_t,\qquad
 \sum_{s<t}d_{s,t}^3\le Q_t^{3/2}.
\]

Hence the fully online upper bound

\[
 \boxed{
 \bar M_t:=\frac1{\sigma^2}\left[
 L_g\sqrt{R_t^{\rm col}Q_t}
 +\frac{3GL_g}{2}Q_t
 +\frac{L_g^2}{2}Q_t^{3/2}
 \right]\ge\|M_t\|_2.}
\]

If the certified trust region gives
$\|\btheta_s\|,\|\btheta_t\|\le R$, then $d_{s,t}\le2R$ and the sharper

\[
 \sum_{s<t}d_{s,t}^3\le2RQ_t
\]

gives

\[
 \boxed{
 \bar M_t^{\rm tr}:=\frac1{\sigma^2}\left[
 L_g\sqrt{R_t^{\rm col}Q_t}
 +\frac{3GL_g}{2}Q_t
 +L_g^2RQ_t
 \right].}
\]

If $\|\nabla\cL_t(\btheta_t)\|_2\le\zeta_t$, then

\[
 \boxed{\bar\psi_t:=\frac{\zeta_t+\bar M_t}{\sqrt\lambda}}
\]

(or the trust-refined version with $\bar M_t^{\rm tr}$) is valid because

\[
 \psi_t=\frac{\zeta_t}{\sqrt\lambda}
       +\|M_t\|_{\bCbar_t^{-1}}
 \le\frac{\zeta_t+\|M_t\|_2}{\sqrt\lambda}
 \le\bar\psi_t.
\]

Unlike the residual envelope in the current Lemma 3, $R_t^{\rm col}$ is an
observed past-data statistic.  It need not be small; smallness is a separate
near-linear assumption in Phase 2.

## Phase 1D: linearization, confidence, and information schedules

Let $L_\mu$ be a certified Lipschitz constant for
$\nabla_\btheta\mu_\btheta(z)$ on the relevant region, and retain
$\|\btheta^*\|\le S$.  The local Taylor remainder satisfies

\[
 \epslin(t)
 \le\frac{L_\mu}{2}\|\btheta^*-\btheta_t\|^2
 \le\frac{L_\mu}{2}(S+\|\btheta_t\|)^2
 =:\bar\epslin(t).
\]

Define the predictable accumulators

\[
 \bar F_t:=\sum_{s<t}\bar\epslin(s)^2,
 \qquad
 \bar E_T:=\sum_{t=1}^T\bar\epslin(t).
\]

Then $F_t\le\bar F_t$ and $E_T\le\bar E_T$.  Critically, the current
$\bar\epslin(t)^2$ is not added to $\bar F_t$ until the schedule for round
$t+1$ is formed.

With the played-action CG proxy, define

\[
 \hat\gamma_{t-1}:=
 \sum_{s<t}\log\!\left(
 1+\frac{u_s(a_s)\tilde s_s^2(a_s)}
          {\sigma^2(1-\bar\varepsilon_s)}
 \right).
\]

The transfer and played-action CG lower sandwich imply

\[
 \bar s_s^2(a_s)
 \le u_s(a_s)s_{\Calg,s}^2(a_s)
 \le\frac{u_s(a_s)}{1-\bar\varepsilon_s}\tilde s_s^2(a_s),
\]

so $\gamma_{t-1}\le\hat\gamma_{t-1}$.  The corrected operational confidence
schedule is

\[
 \boxed{
 \bar\beta_t:=
 \sqrt{\hat\gamma_{t-1}+2\log(1/\delta)}
 +\sqrt\lambda S+\frac1\sigma\sqrt{\bar F_t}.}
\]

This fixes the missing premise in the current Corollary 13: both
$\bar F_t\ge F_t$ and predictability of $\bar F_t$ are required.

## Phase 1E: operational theorem and filtration order

Define

\[
 \omega_t:=\bar\beta_t+\bar\psi_t,
 \qquad
 \alpha_t:=\sqrt{\frac{1+\bar\varepsilon_t}
                         {1-\bar\varepsilon_t}},
 \qquad
 S_T^{\rm op}:=\sum_{t=1}^T
 \alpha_t^2u_t(a_t)\omega_t^2,
\]

and keep the confidence surrogate distinct from the dynamic-width surrogate

\[
 \widehat\Lamalg_T:=\sum_{t=1}^T
 \log\!\left(1+
 \frac{\tilde s_t^2(a_t)}{\sigma^2(1-\bar\varepsilon_t)}
 \right).
\]

### Operational regret statement

Assume the paper's conditional sub-Gaussian noise, realizability, bounded
features, full action enumeration, and predictable fixed SPD operator.  Suppose
the constants $L_\mu,L_g,S,G$ and the optimizer residual bounds $\zeta_t$ are
valid on the stated certificate event; every approximate operator factor
$\kappa_{+,t}$ is certified; and, for every candidate action,

\[
 \max_{a\in\cA_t}\varepsilon_{t,a}\le\bar\varepsilon_t<1.
\]

Use the Phase 1 schedules above in Algorithm 1.  On the confidence and
certificate events,

\[
\boxed{
 R_T
 \le2\sqrt{(\sigma^2+G^2/\lambda)\Lamalg_T S_T^{\rm op}}
       +2\bar E_T
 \le2\sqrt{(\sigma^2+G^2/\lambda)\widehat\Lamalg_T S_T^{\rm op}}
       +2\bar E_T.}
\]

The proof is Theorem 1 with the verified inequalities
$\bar\beta_t\ge\beta_t$, $\bar\psi_t\ge\psi_t$,
$u_t(a)s_{\Calg,t}^2(a)\ge\bar s_t^2(a)$,
$E_T\le\bar E_T$, and
$\Lamalg_T\le\widehat\Lamalg_T$.  Played-action CG accuracy is enough for
$\hat\gamma$ and $\widehat\Lamalg$, but uniform candidate-action accuracy is
still required for UCB optimism.

### Update order

An order compatible with `paper/main.tex:2264-2317` is:

1. At the start of round $t$, $\btheta_t$, the Welford summary of
   $\{\btheta_s:s<t\}$, $R_t^{\rm col}$, $\bar F_t$, and
   $\hat\gamma_{t-1}$ are $\cF_{t-1}$-measurable.
2. Reveal $(\bx_t,\cA_t)$ and draw $\Omega_t$.  The resulting sigma algebra is
   $\cHist_t$.
3. Before action selection, compute $Q_t$, $\bar\chi_t$, $u_t$, the operator,
   $\bar M_t$, $\bar\psi_t$, $\bar\epslin(t)$, and $\bar\beta_t$.  Run all CG
   solves to the uniform certified tolerance and select $a_t$.
4. The played width is already known before reward.  It may be used to prepare
   the next increment of $\hat\gamma$, but no reward-dependent value enters the
   current score.
5. Observe $r_t$, form $c_t=\mu_{\btheta_t}(z_t)-r_t$, and update
   $R_{t+1}^{\rm col}=R_t^{\rm col}+c_t^2$.
6. Add $\bar\epslin(t)^2$ to $\bar F_{t+1}$, add the played-width logarithm to
   $\hat\gamma_t$, and update the Welford summary to include $\btheta_t$.
7. Draw post-reward randomness $U_{t+1}$ and form $\btheta_{t+1}$.  These
   quantities are $\cF_t$-measurable and are available before round $t+1$.

The Welford update can occur earlier because $\btheta_t$ is already known, but
$Q_t$ must be computed from the summary excluding $\btheta_t$.

## Phase 2A: explicit near-linear bounds

Let $W$ denote model width, not the paper's operator-weight sum $W_t$.  Assume
for all $t\le T$

\[
 \|\btheta_t\|\le R,\quad \|\btheta^*\|\le R,\quad
 L_\mu\le\frac{c_\mu}{\sqrt W},\quad
 L_g\le\frac{c_g}{\sqrt W},\quad
 \zeta_t\le\frac{\zeta_0}{\sqrt W},
\]

and set $P_T:=\operatorname{polylog}(T/\delta)\ge1$ for the explicitly supplied
residual-energy envelope

\[
 R_t^{\rm col}\le C_RtP_T.
\]

Because every pair of trusted displacements is at distance at most $2R$,

\[
 Q_t\le4R^2(t-1).
\]

Therefore

\[
 \boxed{\bar\epslin(t)\le\frac{2c_\mu R^2}{\sqrt W},\qquad
 \bar E_T\le\frac{2c_\mu R^2T}{\sqrt W},\qquad
 \bar F_{T+1}\le\frac{4c_\mu^2R^4T}{W}.}
\]

The operational drift certificate obeys

\[
 \boxed{
 \bar\chi_t\le
 x_t:=\frac{2c_gR\sqrt{t-1}}
              {\sigma\sqrt{\lambda W}}.}
\]

The trust-refined centering certificate is

\[
\boxed{
\begin{aligned}
 \bar\psi_t
 \le\frac1{\sqrt\lambda}\Bigg\{
 &\frac{\zeta_0}{\sqrt W}
 +\frac1{\sigma^2}\Bigg[
 \frac{2c_gR\sqrt{C_Rt(t-1)P_T}}{\sqrt W}
 +\frac{6Gc_gR^2(t-1)}{\sqrt W}\\
 &\hspace{43mm}+\frac{4c_g^2R^3(t-1)}{W}
 \Bigg]\Bigg\}.
\end{aligned}}
\]

No factor of $t$ is hidden here.  In particular, the leading residual term is
of order $t\sqrt{P_T/W}$.

## Phase 2B: two-sided exact-curvature reduction and width requirements

Let

\[
 x_T:=\frac{2c_gR\sqrt{T-1}}{\sigma\sqrt{\lambda W}},
 \qquad
 \varepsilon_{\rm drift,T}:=2x_T+x_T^2.
\]

If $\varepsilon_{\rm drift,T}<1$, Lemma 4 and Corollary 5 give uniformly for
$t\le T$

\[
 \rho_-\bCbar_t\preceq\bC_t\preceq\rho_+\bCbar_t,
 \qquad
 \rho_-:=1-\varepsilon_{\rm drift,T},\quad
 \rho_+:=1+\varepsilon_{\rm drift,T}.
\]

For exact curvature $\Calg_t=\bC_t$, the original center, and
$\bar\varepsilon_t\le\bar\varepsilon<1$, Corollary 19 yields

\[
\boxed{
 R_T\le
 2\alpha_I\sqrt{\frac{\rho_+}{\rho_-}}\,
 \omega_{\max,T}^{\rm op}
 \sqrt{(\sigma^2+G^2/\lambda)T\gamma_T}
 +2\bar E_T,}
\]

where
$\alpha_I=\sqrt{(1+\bar\varepsilon)/(1-\bar\varepsilon)}$ and
$\omega_{\max,T}^{\rm op}:=\max_{t\le T}(\bar\beta_t+\bar\psi_t)$.
This two-sided formula does not automatically apply to a subset, stale, or
sketched operator; those need their own two-sided comparison with $\bCbar_t$.

The same two-sided sandwich controls the operational confidence surrogate by
the ordinary frozen information gain.  For every $s\le T$,

\[
 u_s\le(1+x_T)^2=\rho_+,
 \qquad
 \tilde s_s^2(a_s)\le(1+\bar\varepsilon)s_{\Calg,s}^2(a_s),
 \qquad
 s_{\Calg,s}^2(a_s)\le\rho_-^{-1}\bar s_s^2(a_s).
\]

Consequently, with

\[
 A_{\rm inf}:=\alpha_I^2\frac{\rho_+}{\rho_-}\ge1,
\]

each argument in $\hat\gamma_T$ is at most
$A_{\rm inf}\sigma^{-2}\bar s_s^2(a_s)$.  For $A\ge1$ and $x\ge0$,
$\log(1+Ax)\le A\log(1+x)$ (equivalently,
$\log(1+x)/x$ is decreasing).  Therefore

\[
 \boxed{\gamma_T\le\hat\gamma_T\le A_{\rm inf}\gamma_T.}
\]

This upper comparison is specific to a two-sided comparison with
$\bCbar_t$; the one-sided dynamic theorem alone does not provide it.

An explicit bound on the operational width factor is now

\[
\begin{aligned}
 \omega_{\max,T}^{\rm op}
 \le{}&\sqrt{A_{\rm inf}\gamma_T+2\log(1/\delta)}+\sqrt\lambda R
 +\frac{2c_\mu R^2\sqrt T}{\sigma\sqrt W}\\
 &+\frac{A_T}{\sqrt{\lambda W}}+\frac{B_T}{\sqrt\lambda W},
\end{aligned}
\]

where

\[
\begin{aligned}
 A_T&:=\zeta_0+\frac1{\sigma^2}\left[
 2c_gR\sqrt{C_RT(T-1)P_T}+6Gc_gR^2(T-1)
 \right],\\
 B_T&:=\frac{4c_g^2R^3(T-1)}{\sigma^2}.
\end{aligned}
\]

For comparison, there is also a valid but often useless dimension-free
worst-case bound.  If
$u_t(a_t)\le u_{\max,T}$, then Lemma 9 and
$s_{\Calg,t}^2(a_t)\le G^2/\lambda$ give

\[
 \hat\gamma_T
 \le T\log\!\left(
 1+\frac{\alpha_I^2u_{\max,T}G^2}{\lambda\sigma^2}
 \right).
\]

For exact curvature, $u_{\max,T}\le(1+x_T)^2$.  The refined bound
$\hat\gamma_T\le A_{\rm inf}\gamma_T$ should be used whenever the two-sided
sandwich holds.

The exact sufficient asymptotic requirements exposed by the displayed regret
bound are

\[
 \alpha_I^2\frac{\rho_+}{\rho_-}=O(1),\qquad
 (\omega_{\max,T}^{\rm op})^2\gamma_T=o(T),\qquad
 \bar E_T=o(T).
\]

Substituting the refined radius into the regret display gives the fully
explicit dependence

\[
\begin{aligned}
R_T\le{}&2\alpha_I\sqrt{\rho_+/\rho_-}
\Bigg[
 \sqrt{A_{\rm inf}\gamma_T+2\log(1/\delta)}+\sqrt\lambda R
 +\frac{2c_\mu R^2\sqrt T}{\sigma\sqrt W}\\
&\hspace{38mm}+\frac{A_T}{\sqrt{\lambda W}}
 +\frac{B_T}{\sqrt\lambda W}
\Bigg]
\sqrt{(\sigma^2+G^2/\lambda)T\gamma_T}
+2\bar E_T.
\end{aligned}
\]

If $A_{\rm inf}=O(1)$, the non-information terms in brackets are bounded, and
$\bar E_T=o(T)$, then

\[
 \boxed{\gamma_T=o(\sqrt T)}
\]

is sufficient for sublinear regret.  When $\gamma_T$ is polylogarithmic, the
leading dependence is $O(\sqrt T\,\gamma_T)$, the usual linear-UCB dependence
on $T$ up to information-gain factors.  A standard effective-dimension bound is

\[
 \gamma_T\le d\log\!\left(1+
 \frac{TG^2}{d\lambda\sigma^2}\right),
\]

so this route is sublinear whenever the right-hand side is $o(\sqrt T)$ and
the explicit near-linear terms above are controlled.  Width scaling controls
the transfer/centering terms but does not by itself control this ordinary
effective-dimension quantity; see the revised Blocker B3.

## Phase 2C: sufficient width scaling without hidden polylogarithms

Fix target drift $\bar\varepsilon_{\rm drift}\in(0,1)$, target centering factor
$\Psi>0$, target confidence-linearization contribution $b_F>0$, and target
normalized additive error $\eta_E>0$.  Put

\[
 x_*:=\sqrt{1+\bar\varepsilon_{\rm drift}}-1.
\]

The following explicit conditions are sufficient:

\[
\boxed{
 W\ge
 \frac{4c_g^2R^2(T-1)}
      {\lambda\sigma^2x_*^2}}
 \quad\Longrightarrow\quad
 \varepsilon_{\rm drift,T}\le\bar\varepsilon_{\rm drift},
\]

\[
\boxed{
 W\ge\frac{4c_\mu^2R^4T}{\sigma^2b_F^2}}
 \quad\Longrightarrow\quad
 \frac{\sqrt{\bar F_{T+1}}}{\sigma}\le b_F,
\]

\[
\boxed{
 W\ge\frac{4c_\mu^2R^4}{\eta_E^2}}
 \quad\Longrightarrow\quad
 \frac{\bar E_T}{T}\le\eta_E,
\]

and, by splitting the two terms in the bound for $\bar\psi_T$,

\[
\boxed{
 W\ge\max\left\{
 \frac{4A_T^2}{\lambda\Psi^2},
 \frac{2B_T}{\sqrt\lambda\Psi}
 \right\}
 \quad\Longrightarrow\quad
 \bar\psi_T\le\Psi.}
\]

Here $A_T$ contains the residual polylogarithm explicitly:

\[
 A_T=\zeta_0+
 \frac{2c_gR\sqrt{C_RT(T-1)\operatorname{polylog}(T/\delta)}}{\sigma^2}
 +\frac{6Gc_gR^2(T-1)}{\sigma^2}.
\]

The premise supplies only the placeholder
$\operatorname{polylog}(T/\delta)$, not its exponents, so no more specific
power of the logarithm can be derived without an additional residual-energy
assumption.  No such factor is absorbed into $\widetilde O$ notation here.

Thus the centering condition has leading sufficient scaling
$W$ proportional to $T^2\operatorname{polylog}(T/\delta)$, with the complete
constant retained above.  If

\[
 \frac{W}{T^2\operatorname{polylog}(T/\delta)}\longrightarrow\infty,
\]

then $\bar\psi_T\to0$, $\varepsilon_{\rm drift,T}\to0$,
$\bar F_{T+1}\to0$, and $\bar E_T/T\to0$.  Taking merely
$W=C_WT^2\operatorname{polylog}(T/\delta)$ keeps the leading residual part of
$\bar\psi_T$ bounded rather than vanishing.

These width conditions control nonlinearity, centering, and transfer.  They do
not control the ordinary $\gamma_T$.  In the exact two-sided regime Phase 2B
then controls $\hat\gamma_T$ by $A_{\rm inf}\gamma_T$, but an effective-
dimension/information-gain bound on $\gamma_T$ is still necessary for
sublinear regret.

## Phase 3A: scalar tanh constants

Let

\[
 \mu_\btheta(\bx,a)=\tanh(\phi(\bx,a)^\top\btheta),
 \qquad \|\phi(\bx,a)\|\le B.
\]

Writing $z=\phi^\top\btheta$,

\[
 \nabla_\btheta\mu_\btheta=\operatorname{sech}^2(z)\phi,
\]

so

\[
 \boxed{G\le B.}
\]

The Hessian is

\[
 \nabla_\btheta^2\mu_\btheta
 =-2\tanh(z)\operatorname{sech}^2(z)\,\phi\phi^\top.
\]

For $y=|\tanh z|\in[0,1]$,

\[
 2y(1-y^2)
\]

is maximized at $y=1/\sqrt3$ with value $4/(3\sqrt3)$.  Therefore

\[
\boxed{
 L_\mu\le\frac{4}{3\sqrt3}B^2,
 \qquad
 L_g\le\frac{4}{3\sqrt3}B^2.}
\]

The same Hessian norm controls both the Taylor remainder and Lipschitzness of
the gradient feature.  These constants are correct, but they do not decay as
$W^{-1/2}$ unless the feature normalization itself satisfies
$B^2=O(W^{-1/2})$ (or a wider-network parameterization supplies an equivalent
factor).

## Phase 3B: rank-controlled refresh potential

For a symmetric matrix $X$, let $X_-:=(-X)_+$ denote its negative part.

### Rank-refresh lemma

Suppose at round $t$

\[
 \operatorname{rank}((\Xi_t)_-)\le r_t,
 \qquad
 \lambda_{\min}(\bI+\Xi_t)\ge1-\nu_t,
 \qquad 0\le\nu_t<1.
\]

If $\xi_1,\ldots,\xi_d$ are the eigenvalues of $\Xi_t$, at most $r_t$ are
negative and every negative eigenvalue is at least $-\nu_t$.  Positive
eigenvalues contribute nonpositively to $-\log\det(\bI+\Xi_t)$.  Hence

\[
\boxed{
 [-\log\det(\bI+\Xi_t)]_+
 \le r_t\log\frac1{1-\nu_t}.}
\]

Summing gives

\[
 \Valg_T\le\sum_{t=1}^T r_t\log\frac1{1-\nu_t}.
\]

### Endpoint rank/trace bound

Suppose

\[
 \Calg_{T+1}=\lambda\bI+A_{\rm end},\qquad
 A_{\rm end}\succeq0,\qquad
 \operatorname{rank}(A_{\rm end})\le r_{\rm end},\qquad
 \operatorname{tr}(A_{\rm end})\le\frac{W_TG^2}{\sigma^2}.
\]

Here $W_T$ is the total nonnegative outer-product weight in the endpoint
operator, consistent with the paper's CG condition-number notation.

For $r_{\rm end}>0$, concavity of $x\mapsto\log(1+x)$ and monotonicity of
$f(r)=r\log(1+c/r)$ give the result below.  The latter follows from
$f'(r)=\log(1+c/r)-c/(r+c)\ge0$, using
$\log(1+y)\ge y/(1+y)$.

\[
\boxed{
 \log\frac{\det(\Calg_{T+1})}{\det(\lambda\bI)}
 \le r_{\rm end}\log\!\left(
 1+\frac{W_TG^2}{r_{\rm end}\lambda\sigma^2}
 \right).}
\]

If $r_{\rm end}=0$, then $A_{\rm end}=0$ and the endpoint term is zero.  Combining
the endpoint and refresh bounds with Lemma 7 yields

\[
\boxed{
 \Lamalg_T\le
 r_{\rm end}\log\!\left(
 1+\frac{W_TG^2}{r_{\rm end}\lambda\sigma^2}
 \right)
 +\sum_{t=1}^T r_t\log\frac1{1-\nu_t}.}
\]

The endpoint term in this combined display is read as zero in the separate
case $r_{\rm end}=0$; it is not evaluated by substituting zero into the
fraction.

### Valid corollaries and their exact scope

**Monotone updates.**  If
$\Calg_{t+1}\succeq\Calg_t^+$, then $\Xi_t\succeq0$ and the round contributes
zero to $\Valg_T$.  The standard rank-one Gram update has
$\Calg_{t+1}=\Calg_t^+$ exactly.

**Sparse refreshes.**  If only $J_T$ rounds have a negative component, and on
each such round $r_t\le r$ and $\nu_t\le\nu<1$, then

\[
 \Valg_T\le J_Tr\log\frac1{1-\nu}.
\]

**Low-rank replacement.**  Let
$\Delta_t=\Calg_{t+1}-\Calg_t^+$.  Congruence by
$(\Calg_t^+)^{-1/2}$ preserves inertia, so if the negative index of
$\Delta_t$ is at most $r$, then $r_t\le r$.  In particular, if

\[
 \Delta_t=A_t^{\rm new}-A_t^{\rm old},\qquad
 A_t^{\rm new},A_t^{\rm old}\succeq0,\qquad
 \operatorname{rank}(A_t^{\rm old})\le r,
\]

then the negative index is at most $r$: any subspace of dimension greater than
$r$ intersects $\ker(A_t^{\rm old})$, where the quadratic form of
$\Delta_t$ is nonnegative.  A separate spectral-floor bound
$\lambda_{\min}(\bI+\Xi_t)\ge1-\nu$ is still necessary.

**Frozen-feature sliding window.**  For a fixed-feature window of length $m$,
after the rank-one played update the only change is deletion of
$v_tv_t^\top$, where $v_t=\bg_{t-m}(z_{t-m})/\sigma$.  Write
$\Calg_t^+=B_t+v_tv_t^\top$ and $\Calg_{t+1}=B_t$, where
$B_t\succeq\lambda\bI$.  Then

\[
 \Xi_t=-w_tw_t^\top,\qquad
 w_t=(\Calg_t^+)^{-1/2}v_t,\qquad
 \ell_t:=\|w_t\|^2=v_t^\top(\Calg_t^+)^{-1}v_t<1,
\]

and the charge is exactly

\[
 [-\log\det(\bI+\Xi_t)]_+=-\log(1-\ell_t).
\]

Here $r_t=1$ and one may take $\nu_t=\ell_t$.  More sharply, let
$q_t:=v_t^\top B_t^{-1}v_t$.  Sherman--Morrison gives

\[
 \ell_t=\frac{q_t}{1+q_t},\qquad
 -\log(1-\ell_t)=\log(1+q_t).
\]

Since $B_t\succeq\lambda\bI$ and $\|v_t\|\le G/\sigma$,
$q_t\le G^2/(\lambda\sigma^2)$.  Equivalently, the normalized spectral floor is
\[
 1-\ell_t=\frac1{1+q_t}
 \ge\frac1{1+G^2/(\lambda\sigma^2)}.
\]
Therefore, with no small-width condition,

\[
 \boxed{\Valg_T\le
 N_{\rm drop}\log\!\left(1+\frac{G^2}{\lambda\sigma^2}\right).}
\]

This bound is generally $O(T)$ for a fixed-size window that deletes one point
per round; the rank-one fact alone does not make its variation polylogarithmic.

This rank-one statement is not valid for a current-parameter relinearized
window: moving from $\btheta_t$ to $\btheta_{t+1}$ changes every retained
Jacobian, so the refresh difference can have rank as large as the window size
or $d$.

**Geometric refresh.**  Refreshing at rounds $1,2,4,\ldots$ gives at most
$1+\lfloor\log_2T\rfloor$ noncanonical transitions.  If each refresh also
satisfies $r_t\le r$ and $\nu_t\le\nu<1$, then

\[
 \Valg_T\le(1+\lfloor\log_2T\rfloor)
 r\log\frac1{1-\nu}.
\]

Geometric timing controls only the number of refreshes.  It does not establish
their rank or spectral floor.  Generic full relinearization may have
$r_t=d$ and $\nu_t$ arbitrarily close to one; see Blocker B4.

## Roundwise scalar-invariance proposition

**Proposition (roundwise action-invariant width scaling).**  Fix a round and a
common history.  Suppose two UCB scores differ only in their width and scalar
bonus coefficient:

\[
 U_t(a)=m_t(a)+b_t s_t(a),
 \qquad
 \hat U_t(a)=m_t(a)+\hat b_t\hat s_t(a).
\]

If there is an action-independent, $\cHist_t$-measurable $c_t>0$ such that

\[
 \hat s_t(a)=c_ts_t(a)\qquad\forall a\in\cA_t,
\]

then choosing $\hat b_t=b_t/c_t$ gives

\[
 \hat U_t(a)=U_t(a)\qquad\forall a\in\cA_t.
\]

Thus the complete score vector, argmax set, and selected action under a common
tie-breaking rule are identical.  The proof is direct substitution.

The proposition is roundwise.  Induction gives identical trajectories only if
the policies start from the same history, use coupled rewards and optimizer
randomness, preserve the scalar relation at every subsequent common history,
and use the adjusted coefficient predictably.  It does not apply when scaling
is action-dependent, when means/damping/transfer factors differ, or when
coefficients are selected after observing outcomes.  If $c_t=0$, division is
invalid unless the original exploration term is already identically zero.

## Audit conclusion

- Phases 1A--1E are valid with the explicit `bar F_t>=F_t` premise and uniform
  all-action CG accuracy for regret, while played-action accuracy alone is
  enough for the two observable log sums.
- The near-linear constants are correct.  Width scaling of order
  $T^2\operatorname{polylog}(T/\delta)$ controls the explicit centering term,
  while the exact two-sided sandwich gives
  $\hat\gamma_T\le A_{\rm inf}\gamma_T$; ordinary $\gamma_T$ still needs an
  effective-dimension bound.
- The tanh constant is exactly $4/(3\sqrt3)$ times $B^2$.
- The rank-refresh lemma and endpoint bound are correct.  Sliding-window and
  geometric-refresh corollaries require the stated rank and spectral-floor
  hypotheses; they do not hold automatically for relinearized operators.
- Roundwise scalar invariance is exact under a positive action-independent
  scale and common tie-breaking.
