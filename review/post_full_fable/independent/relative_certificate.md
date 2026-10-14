# Exact endpoint certificates for the scaled-tanh audit

Independent exact-arithmetic derivation; no new experiments or repository
changes. The forthcoming Fable review was not consulted. Ordinary float64
evaluation of these expressions is not a verified numerical enclosure.

## Uniform certificate

The model has
\[
 \mu_\theta(z)=\sqrt W\tanh(\phi(z)^\top\theta/\sqrt W),\qquad
 q_\theta(z)=a_\theta(z)\phi(z),\quad
 a_\theta(z)=\operatorname{sech}^2(\phi(z)^\top\theta/\sqrt W).
\]
Assume \(W>0,\|\phi(z)\|\le B,\|\theta\|\le R\) for all collection/current
parameters. Set \(U=BR/\sqrt W\) and \(\ell=\operatorname{sech}^2U>0\).
Then \(\ell\le a_\theta(z)\le1\). With the same \(\lambda>0,\sigma>0\),
\[
 A=\bar V_t=\lambda I+\sigma^{-2}\sum_{s<t}a_{\theta_s}(z_s)^2\phi_s\phi_s^\top,
\quad
 C=V_t=\lambda I+\sigma^{-2}\sum_{s<t}a_{\theta_t}(z_s)^2\phi_s\phi_s^\top.
\]
Termwise,
\[
 \ell^2a_{\theta_s}(z_s)^2
 \le a_{\theta_t}(z_s)^2
 \le\ell^{-2}a_{\theta_s}(z_s)^2.
\]
Multiplication by each PSD outer product and summation, including the ridge,
give
\[
 C-\ell^2A\succeq(1-\ell^2)\lambda I\succeq0,\quad
 \ell^{-2}A-C\succeq(\ell^{-2}-1)\lambda I\succeq0.
\]
Thus
\[
 \boxed{\ell^2A\preceq C\preceq\ell^{-2}A},\qquad
 \boxed{d_{\rm Th}(A,C)\le -2\log\ell=4\log\cosh U=:D_0}.
\]
This horizon-independent certificate requires neither eigenvalues nor
quadrature. For the study's \(B=R=1\):

| W | \(D_0\) | Outward width factor \(e^{D_0/2}\) | Round-trip factor \(e^{D_0}\) |
| ---: | ---: | ---: | ---: |
| 16 | 0.123719214481 | 1.06381298260 | 1.13169806196 |
| 1 | 1.73512332193 | 2.38109784554 | 5.66962695004 |
| 0.25 | 5.30001098943 | 14.1541164180 | 200.339011575 |

These are uniform upper bounds, not claimed observed factors. Bounded
transport does not control the separate confidence and bias terms. Under the
paper's existing uniform Taylor envelopes, historical error energy has an
O(T/W) bound and accumulated current bias an O(T/sqrt(W)) bound; this new
certificate alone therefore gives no sublinear fixed-W guarantee.

## Tighter sample/category comparison without eigensolves

Define \(r_s=a_{\theta_t}(z_s)^2/a_{\theta_s}(z_s)^2>0\).
Then \(m_{\rm sam}=\min(1,\min_s r_s)\) and
\(M_{\rm sam}=\max(1,\max_s r_s)\) give
\(m_{\rm sam}A\preceq C\preceq M_{\rm sam}A\).
Including 1 accounts for the unchanged ridge. An empty history gives \(m=M=1\).
For numerical evaluation,
\[
 \log r_s=4[\log\cosh(\phi_s^\top\theta_s/\sqrt W)
                  -\log\cosh(\phi_s^\top\theta_t/\sqrt W)]
\]
avoids subtraction of nearly equal tanh values, but still requires conservative
enclosures for literal machine certification.

For each observed finite category c, use
\[
 n_c=\#\{s<t:c_s=c\},\quad
 f_c=\sum_{s<t:c_s=c}a_{\theta_s}(z_s)^2,\quad
 g_c=n_c a_{\theta_t}(c)^2,\quad r_c=g_c/f_c.
\]
Set \(m=\min(1,\min_{c:n_c>0}r_c)\) and
\(M=\max(1,\max_{c:n_c>0}r_c)\). The exact expansions are
\[
 A=\lambda I+\sigma^{-2}\sum_c f_c\phi_c\phi_c^\top,\qquad
 C=\lambda I+\sigma^{-2}\sum_c g_c\phi_c\phi_c^\top.
\]
Consequently
\[
 C-mA=(1-m)\lambda I+
 \sigma^{-2}\sum_c(g_c-mf_c)\phi_c\phi_c^\top\succeq0,
\]
and similarly \(MA-C\succeq0\). Each \(r_c\) is the weighted average of its
sample ratios, with weights \(a_{\theta_s}(z_s)^2/f_c\). Therefore
\[
 \boxed{mA\preceq C\preceq MA},\qquad
 \ell^2\le m_{\rm sam}\le m\le1\le M\le M_{\rm sam}\le\ell^{-2}.
\]
Category ratios are never looser than sample extrema. They need not be the
optimal spectral factors, since different outer products can overlap.

The code stores 80 category counts, features, collection parameters, and
collection queries. It does **not** store \(f_c\) as a dedicated accumulator.
It can be reconstructed in one pass over those records; for nonzero \(\phi_c\),
\(a_s=(q_s^\top\phi_c)/\|\phi_c\|^2\). A new implementation could maintain
80 scalars via \(f_{c_s}\leftarrow f_{c_s}+a_s^2\). Current multipliers are
already computed for the current metric, so the certificate then needs O(80)
additional scalar work beyond the existing O(80d) projections, with no
eigensolve or full-history traversal.

With only current multipliers and the global lower bound, the weaker factors
\[
 m_{\rm cur}=\min(1,\min_{c:n_c>0}a_{\theta_t}(c)^2),\quad
 M_{\rm cur}=\max(1,\max_{c:n_c>0}a_{\theta_t}(c)^2/\ell^2)
\]
also work and need no frozen-weight accumulator. Skip zero-count categories;
zero-feature categories contribute nothing.

An optional ridge improvement is also eigenvalue-free. Put
\[
 L=\sigma^{-2}\sum_c f_c\|\phi_c\|^2,\qquad A\preceq(\lambda+L)I.
\]
The stronger inequalities \(C\succeq mA+(1-m)\lambda I\) and
\(C\preceq MA-(M-1)\lambda I\) imply
\[
 \widetilde m A\preceq C\preceq\widetilde M A,\quad
 \widetilde m=\frac{\lambda+mL}{\lambda+L},\quad
 \widetilde M=\frac{\lambda+ML}{\lambda+L}.
\]
These factors improve m,M but may remain conservative when L is large.

## Endpoint versus the recorded synthetic path

\(D_{\rm end}=\max(-\log m,\log M)\) bounds endpoint Thompson distance, not
necessarily the length of the paper's stacked-factor interpolation. For one
sample in one dimension with \(\phi=1,\theta_s=-R,\theta_t=R\), endpoints are
equal, so \(m=M=1\); the synthetic path goes through \(\theta=0\) and has length
\[
 2\log\frac{\lambda+\sigma^{-2}}{\lambda+\sigma^{-2}\ell^2}>0
\]
for \(R>0\). A zero endpoint certificate does not bound that positive length.

Two rigorous uses are available:

1. State an endpoint-sandwich corollary and repeat the theorem's proof.
   The inequalities \(\bar s\le\sqrt M\,s\) and
   \(s\le m^{-1/2}\bar s\) yield score
   \[
   U_t(a)=m_t(a)+\beta_t\sqrt{M\kappa_{+,t}}\hat s_t(a)+b_t(a)
   \]
   and instantaneous regret
   \[
   \operatorname{reg}_t\le
   \beta_t[1+\alpha_t\sqrt{M\kappa_{+,t}/(m\kappa_{-,t})}]
   \bar s_t(a_t)+2b_t(a_t)+\xi_t.
   \]
   Here m,M are the scalar endpoint factors; \(m_t(a)\) remains the prediction
   center. The original frozen-potential argument gives the cumulative bound.
   Keeping the asymmetric factors is at least as sharp as symmetrizing them.
2. Satisfy the abstract theorem's existential path premise with
   \(A^{1/2}(A^{-1/2}CA^{-1/2})^\tau A^{1/2}\). Its Thompson-Finsler length
   equals \(d_{\rm Th}(A,C)\le D_{\rm end}\): congruence reduces the path to
   commuting powers, with constant logarithmic speed. This is an existence
   argument; evaluating the scalar certificate need not construct the path.
   It is a different path from the recorded synthetic interpolation.

Both routes retain all confidence, timing, selection, solver, and applied-
operator assumptions. Neither licenses relabeling saved \(D_Q\) or quadrature
values as the new certificate.

## What this adds, and does not add

The result exploits **fixed feature directions**: tanh relinearization only
changes scalar weights. It is a standard positive-coefficient PSD comparison,
not a new general rotating-Jacobian result. This controlled model therefore
admits an inexpensive alternative to its very loose Hessian/Q envelope.

The computational gain is avoiding endpoint eigensolves or path quadrature for
the certificate. It does not remove the current-metric solve or the frozen
estimator needed by the corrected center. No end-to-end speedup at d=29 is
established. New adaptive regret requires executing a new policy; rescoring
stored trajectories is only a diagnostic.

On one fixed history, with the same center/radius/bias and relying only on the
same reference confidence event, a certified width conversion must satisfy
\(c_t(a)s_t(a)\ge\bar s_t(a)\). The exact actionwise ratio recovers frozen UCB.
Better category factors remove excess above that floor, not create a narrower
justified interval. Different adaptive histories still rule out inferring
realized-regret dominance from this comparison.

Code evidence in experiments/transport_instantiation.py: feature normalization
at lines 316–339; scalar link/gradient at 398–437; category statistics/current
metric at 640–749; retained queries/frozen updates at 878–986; synthetic-path
diagnostic at 1042–1117. The follow-up config fixes B=R=1 and projection radius 1.
No implementation or evidence file was modified.
