# Symbol and definition checklist

Locations refer to the 171-line candidate `main.tex`. This checks transcription and definition coverage against the canonical statements, not a new scientific review. Standard real-number, expectation, determinant, norm, transpose, and Loewner-order notation is used.

| Object | Candidate definition and use | Check |
| --- | --- | --- |
| t, T, x_t | Line 43: round t through horizon T, observed context before selection | Defined before formulas |
| A, a, a_t | Line 43: fixed finite nonempty action set, candidate action a, selected action a_t | Maxima attained; actionwise measurability suffices on finite A |
| mu_t^*(a), m_t(a) | Line 43: true conditional mean and generic prediction center | Generic center retained in Theorem 1 |
| d, q_t(a) | Line 43: common fixed dimension and prediction query in R^d | Gradient identification deferred to specialization |
| H_t^-, Omega_t, H_t | Line 43: context-observed history before fresh randomization; pre-reward randomness; enlarged pre-reward information | Not indiscriminately replaced by F_(t-1) |
| Predictable versus pre-reward measurable | Line 43: reference/current metrics, beta, and representation parameter predictable; other realized maps may depend on Omega_t | Historical selected queries fixed before their own rewards |
| lambda, sigma, I | Line 45: positive scales and d-dimensional identity | Noise meaning added only in Section 2 |
| Vbar_t, sbar_t(a) | Lines 47 to 51, equation (1): reference recursion and current-query inverse-Gram width | Same recursion as baseline |
| R_T, gamma_T, gamma_0 | Lines 53 to 58, equation (2): cumulative pseudo-regret; full log-determinant ratio; gamma_0=0 | Defined before theorem; no factor 1/2 |
| V_t, C_t, s_t(a), s_C,t(a) | Line 59: exact current and algorithmic d by d SPD operators and their inverse-quadratic widths | Widths use the same current query |
| G | Line 62: uniform finite bound on query norm | Theorem bound retains G^2/lambda |
| E_conf, beta_t, b_t(a) | Lines 62 to 66: simultaneous reference confidence, beta predictable and nonnegative, bias pre-reward and nonnegative | No reward-noise assumption added to abstract transfer |
| E_cert, Dbar_t | Lines 67 to 73: certificate event, finite nonnegative pre-reward envelope on Thompson Finsler length of an absolutely continuous SPD path | Selected-path premise and exponential Loewner consequence both retained |
| kappa_-,t, kappa_+,t | Lines 69 to 73: strictly positive, ordered, finite factors and two-sided operator sandwich | Lower comparison retained |
| shat_t(a), alpha_t | Lines 73 to 77: nonnegative pre-reward solver width, all-action upper validity, played-action-only sharpness with alpha>=1 | Width inequalities, not squared-width inequalities |
| U_t(a), xi_t | Lines 79 to 83, equation (6): transported score and pre-reward approximate oracle, xi>=0 | One realized width map for score, solver, and oracle |
| delta, delta_cert | Line 95: failure levels for E_conf and E_cert | Probability at least 1-delta-delta_cert; no conditional-probability or independence claim |
| theta, Theta, theta_t, mu_theta | Line 100: fixed coordinates in R^d, convex smoothness region, differentiable model mean, predictable parameter path | Abstract query interface not restricted retroactively |
| z, z_s, q_theta, q_s | Line 100: context-action pair, selected pair, mean gradient, selected-query shorthand | z_s is not a second name for the context |
| theta_circ, S, mu^*, m_circ | Line 100: ex-ante norm-bounded reference model and approximate-realizability residual | No reference model added to abstract theorem |
| r_t, eta_t | Line 100: observed reward and conditional sub-Gaussian noise given all pre-reward information | Noise condition follows action selection |
| epsilon_lin(s), epsilon_mis(s) | Line 102: historical absolute Taylor and misspecification bounds | Supplied pre-reward; historical sum known before selection |
| epsilon_lin,t(a), epsilon_mis,t(a) | Line 102: current actionwise counterparts | Region containment does not imply small errors |
| y_s, theta_hat_lin,t, m_corr,t | Lines 102 to 107, equations (8) and (9): pseudo-response, exact auxiliary frozen ridge, corrected center | Exact estimator access explicit; no approximate-solve substitution |
| beta_corr,t, b_t(a) | Lines 109 to 114, equation (10): simultaneous confidence radius and current bias | Historical envelopes added before squaring; historical 1/sigma retained |
| Current squared-loss GGN | Line 116: lambda I + sigma^-2 sum current-relinearized selected-history query outer products | GGN, not the full nonlinear-loss Hessian |
| phi, W, R, c_h, L_g | Lines 119 to 126: normalized features, scaled-tanh mean, trust-region radius, predeclared W rule, global mean-Hessian norm bound | W is a smoothness scale; D_target is a design label |
| D_target, Q_t, D_Q,t | Lines 119 to 126, equation (11): targets, squared replay displacement sum, Hessian path envelope | Primary Dbar_t=D_Q,t |
| d_Th,t | Line 128: endpoint Thompson distance between Vbar_t and V_t | Not parameter displacement or selected-path length |
| w_t(a) and four policy names | Lines 128 to 137: common-form scores with each policy's own fitted components and history | Frozen reference uses current query against collection-time Gram |
| D_quad,t | Line 137: 32-point numerical selected-path integral, every ten rounds and declared horizons | Numerical SPD speed integral on per-replay interpolation, not an enclosure |
| R_1000 | Lines 145 to 148: terminal cumulative pseudo-regret at primary horizon | Mean over 50 seeds per policy and target |
| D_Q / D_quad table row | Lines 150 and 155 | Pooled eligible seed-checkpoint median; denominator >10^-12 |
| max d_Th table row | Lines 151 and 155 | Maximum within each trajectory, then median across trajectories |
| exp(D_Q/2) table row | Lines 152 and 155 | Pooled seed-round median; proposed evidence addition C01 |
| Numerical RHS | Line 159: right-hand side of equation (7) | Per-trajectory ratio, then cellwise median; not ratio of aggregate means |
| 2T | Line 159: deterministic pseudo-regret cap from bounded conditional means | Does not bound Gaussian observations |

## Scope checks

Theorem 1 contains no conditional sub-Gaussian-noise or fixed-reference-parameter premise. Section 2 supplies those assumptions for its confidence construction. All-action solver validity and played-action sharpness remain distinct. Exact-arithmetic operator/solver values in Section 3 are explicitly separated from tolerance-based float64 diagnostics.

No symbol remains as an unresolved mathematical author marker. The only visible manuscript marker concerns author order and affiliations. Metadata and contribution/evidence approvals remain in the approval ledger.
